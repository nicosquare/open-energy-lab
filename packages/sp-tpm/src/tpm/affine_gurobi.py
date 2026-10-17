"""Optional Gurobi attachment of strengthened binary affine PWL log ratios.

Extracted from tpm_for_sp/knapsack_tpm/{compilation.py,filtered/bounds.py,
filtered/sos2.py}. The caller owns model/environment lifetime, business variables,
objective, probability threshold, solver parameters, starts and optimization.
"""
from dataclasses import dataclass
from types import MappingProxyType
import math


@dataclass(frozen=True)
class AffineConditionalAttachment:
    root: object
    numerator_root: object
    denominator_root: object
    variables: object
    decision_variables: tuple
    namespace: str


def attach_affine_log_ratio(model, decisions, records, *, namespace='', encoding='pwl'):
    """Attach both queries with shared binary decisions and no solver invocation.

    Uses curve-preserving SOS2 interpolation, common-decision difference bounds,
    disaggregated maxima, winner-endpoint links and one-bit conditional bounds.
    Only the caller can impose an event threshold or change the objective.
    ``encoding='nonlinear'`` replaces the exp and log PWLs by Gurobi nonlinear
    constraints, with every bound propagated through the exact functions.
    """
    import gurobipy as gp
    import numpy as np
    from .affine import conditional_affine_bounds, exact_affine_logsum_bounds, validate_affine_logsum
    if encoding not in ('pwl', 'nonlinear'):
        raise ValueError("encoding must be 'pwl' or 'nonlinear'")
    exact = encoding == 'nonlinear'
    if set(records['queries']) != {'numerator', 'denominator'}:
        raise ValueError('Exactly numerator and denominator queries are required')
    for graph in records['queries'].values():
        validate_affine_logsum(graph)
    dimensions = {len(r['coeff']) for q in records['queries'].values() for r in q if r['kind']=='affine'}
    if len(dimensions) != 1 or len(decisions) != next(iter(dimensions)):
        raise ValueError('Shared decisions must match the dimension of both queries')
    if not isinstance(namespace, str) or (namespace and (not namespace.isascii() or not namespace.replace('_','').isalnum())):
        raise ValueError('Namespace must contain only ASCII letters, digits and underscores')
    model.update()
    owned = model.getVars()
    if (any(v.VType != gp.GRB.BINARY for v in decisions)
            or any(v.index < 0 or v.index >= len(owned) or not v.sameAs(owned[v.index]) for v in decisions)
            or len({v.index for v in decisions}) != len(decisions)):
        raise ValueError('Distinct caller-owned binary decision variables required')
    prefix = namespace+'__' if namespace else ''
    if any(v.VarName.startswith((prefix+'numerator__', prefix+'denominator__'))
           or v.VarName == prefix+'root' for v in owned):
        raise ValueError('Attachment namespace already exists in the model')
    # Compute all bound propagation before mutating the caller model.
    conditional = {name: conditional_affine_bounds(query, exact=exact) for name,query in records['queries'].items()}
    # PWL-propagated bounds can cut off exact exp/log values, so the nonlinear encoding recomputes them.
    tightened = {name: exact_affine_logsum_bounds(query) if exact else query[-1]['tightened_bounds']
                 for name,query in records['queries'].items()}
    assigned = {f'x_{i}': v for i,v in enumerate(decisions)}

    def query_attachment(name, graph):
        local = {}
        def var(key, lower, upper, kind=gp.GRB.CONTINUOUS):
            v = model.addVar(lb=float(lower), ub=float(upper), vtype=kind, name=prefix+name+'__'+key)
            local[key] = v
            assigned[name+'__'+key] = v
            return v
        def row(expr, key):
            model.addConstr(expr, name=prefix+name+'__'+key)
        terms = [r for r in graph if r['kind']=='affine']
        bounds = tightened[name]
        values = []
        for j,term in enumerate(terms):
            v = var(f't_{j}', bounds['term_lower'][j], bounds['term_upper'][j])
            row(v == term['intercept']+gp.quicksum(float(c)*x for c,x in zip(term['coeff'],decisions)), f'term_{j}')
            values.append(v)
        maximum = var('maximum', *bounds['maximum'])
        selectors = [var(f'max_choice_{j}',0,1,gp.GRB.BINARY) for j in range(len(terms))]
        row(gp.quicksum(selectors)==1, 'maximum_one_hot')
        for j,v in enumerate(values):
            row(maximum>=v, f'maximum_lower_{j}')
            row(maximum<=v+bounds['big_m'][j]*(1-selectors[j]), f'maximum_upper_{j}')
        def pwl(key, argument, xs, ys, lower, upper):
            output = var(key, lower, upper)
            weights = [var(f'{key}_lambda{i}',0,1) for i in range(len(xs))]
            row(gp.quicksum(weights)==1, key+'_sos2_normalization')
            row(argument==gp.quicksum(float(v)*w for v,w in zip(xs,weights)), key+'_sos2_input')
            row(output==gp.quicksum(float(v)*w for v,w in zip(ys,weights)), key+'_sos2_output')
            model.addSOS(gp.GRB.SOS_TYPE2, weights, list(range(len(weights))))
            return output, weights
        expvars = []
        for j,r in enumerate(r for r in graph if r['kind']=='exp'):
            lo,hi = bounds['relative_lower'][j],bounds['relative_upper'][j]
            relative = var(f'relative_{j}',lo,hi)
            coordinate = var(f'coordinate_{j}',(lo+500)/500,(hi+500)/500)
            row(relative==values[j]-maximum, f'relative_{j}')
            row(500*coordinate==relative+500, f'coordinate_{j}')
            if exact:
                output = var(r['name'], bounds['exponential_lower'][j], bounds['exponential_upper'][j])
                model.addGenConstrNL(output, gp.nlfunc.exp(relative), name=prefix+name+'__'+r['name'])
                expvars.append(output)
                # A winner has relative 0 and exp 1 through the maximum rows; no endpoint link is needed.
                if hi < 0:
                    row(selectors[j]==0, f'cannot_win_{j}')
                continue
            output, weights = pwl(r['name'],relative,r['xs'],r['ys'],
                                 bounds['exponential_lower'][j],bounds['exponential_upper'][j])
            expvars.append(output)
            if r['xs'][-1] < 0:
                row(selectors[j]==0, f'cannot_win_{j}')
            else:
                if r['xs'][-1] != 0 or r['ys'][-1] != 1:
                    raise ValueError('Winning shifted exponential endpoint must be (0,1)')
                row(weights[-1]>=selectors[j], f'winner_endpoint_{j}')
        total = var('total', *bounds['total'])
        row(total==gp.quicksum(expvars), 'sum_exponentials')
        r = graph[-1]
        if exact:
            logarithm = var('logarithm', *bounds['logarithm'])
            model.addGenConstrNL(logarithm, gp.nlfunc.log(total), name=prefix+name+'__logarithm')
        else:
            logarithm,_ = pwl('logarithm',total,r['xs'],r['ys'],*bounds['logarithm'])
        root = var('root', *bounds['root'])
        row(root==maximum+logarithm, 'root')
        copies = [[var(f'disagg_{j}_{i}',0,1) for i in range(len(decisions))] for j in range(len(terms))]
        for j,copy in enumerate(copies):
            for i,v in enumerate(copy):
                row(v<=selectors[j], f'disagg_cap_{j}_{i}')
        for i,x in enumerate(decisions):
            row(gp.quicksum(copy[i] for copy in copies)==x, f'disagg_decision_{i}')
        row(maximum==gp.quicksum(r['intercept']*selectors[j]+
            gp.quicksum(float(c)*v for c,v in zip(r['coeff'],copies[j])) for j,r in enumerate(terms)), 'disagg_maximum')
        for i,(zero,one) in enumerate(conditional[name]):
            for key,(lo0,hi0) in zero.items():
                lo1,hi1 = one[key]
                row(local[key]>=lo0+(lo1-lo0)*decisions[i], f'conditional_lo_{i}_{key}')
                row(local[key]<=hi0+(hi1-hi0)*decisions[i], f'conditional_hi_{i}_{key}')
        return root
    numerator = query_attachment('numerator',records['queries']['numerator'])
    denominator = query_attachment('denominator',records['queries']['denominator'])
    root = model.addVar(lb=-gp.GRB.INFINITY,name=prefix+'root')
    model.addConstr(root==numerator-denominator,name=prefix+'conditional_ratio')
    assigned['root'] = root
    model.update()
    return AffineConditionalAttachment(root,numerator,denominator,MappingProxyType(assigned),tuple(decisions),namespace)


def check_affine_sos_assignments(model, values, *, tolerance=1e-8):
    """Audit saved SOS2 membership without optimizing or running presolve."""
    import gurobipy as gp
    import numpy as np
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('Finite nonnegative support tolerance required')
    for sos in model.getSOSs():
        kind, variables, weights = model.getSOS(sos)
        if kind != gp.GRB.SOS_TYPE2:
            raise ValueError('Expected SOS2 interpolation membership')
        order = np.argsort(weights)
        vector = np.vstack([np.atleast_1d(values[variables[i].VarName]) for i in order])
        for column in vector.T:
            support = np.flatnonzero(abs(column)>tolerance)
            if len(support)>2 or (len(support)==2 and support[1]-support[0]!=1):
                raise ValueError('Assignment violates adjacent SOS2 support')


__all__ = ['AffineConditionalAttachment', 'attach_affine_log_ratio', 'check_affine_sos_assignments']
