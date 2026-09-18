"""Strengthened affine-input log-sums over binary decisions.

Extracted from tpm_for_sp/knapsack_tpm/filtered/encoding.py and bounds.py,
validated in the paired knapsack campaign. No objective, probability threshold,
solver, fitting policy, or decision dimension is selected by this module.
"""
import math
import numpy as np
from .piecewise import PiecewiseBreakpointPolicy, resolve_guarded_exponential_spec


def clip_table(xs, ys, lower, upper):
    """Restrict a PWL graph without replacing its endpoint values by f(x)."""
    if not xs[0] <= lower < upper <= xs[-1]:
        raise ValueError('A nonempty interval within the PWL table is required')
    knots = [lower, *(x for x in xs if lower < x < upper), upper]
    return knots, np.interp(knots, xs, ys).tolist()


def tighten_affine_logsum_bounds(intercepts, coefficients, ex, ey, lx, ly, *,
                                 root_interval, q_cap=None, affine_max=None):
    """Box-valid affine differences and interval propagation; no action enumeration."""
    b, a = np.asarray(intercepts), np.asarray(coefficients)
    pad = 1e-8
    maximize = affine_max if affine_max is not None else lambda c: np.maximum(c, 0).sum(1)
    lower = b - maximize(-a) - pad
    upper = b + maximize(a) + pad
    maxlo, maxhi = float(max(lower)), float(max(upper))
    original = dict(maximum=[maxlo, maxhi], total=[1., float(len(b))],
                    big_m=(maxhi - lower).tolist())
    big_m, relative_upper = [], []
    for k in range(len(b)):
        big_m.append(max(0., float(np.max(b - b[k] + maximize(a - a[k])))) + pad)
        relative_upper.append(min(0., float(np.min(b[k] - b + maximize(a[k] - a))) + pad))
    big_m = np.asarray(big_m)
    rl, ru = -big_m, np.asarray(relative_upper)
    el, eu = np.interp(rl, ex, ey), np.interp(ru, ex, ey)
    ql, qu = 1., min(float(len(b)), float(q_cap) if q_cap is not None else float(len(b)))
    hl, hu = float(np.interp(ql, lx, ly)), float(np.interp(qu, lx, ly))
    zl, zu = root_interval[0] - pad, root_interval[1] + pad

    def inverse_lower(value):
        if value <= ey[0]:
            return ex[0]
        j = int(np.searchsorted(ey, value, side='left'))
        if j >= len(ey):
            raise ValueError('empty exponential range')
        return ex[j - 1] + (value - ey[j - 1]) * (ex[j] - ex[j - 1]) / (ey[j] - ey[j - 1])

    def inverse_upper(value):
        if value >= ey[-1]:
            return ex[-1]
        j = int(np.searchsorted(ey, value, side='right'))
        if j == 0:
            raise ValueError('empty exponential range')
        return ex[j - 1] + (value - ey[j - 1]) * (ex[j] - ex[j - 1]) / (ey[j] - ey[j - 1])

    for iteration in range(100):
        previous = np.concatenate([lower, upper, rl, ru, el, eu, [maxlo, maxhi, ql, qu, hl, hu]])
        maxlo = max(maxlo, float(max(lower)), zl - hu - pad)
        maxhi = min(maxhi, float(max(upper)), zu - hl + pad)
        lower = np.maximum(lower, maxlo + rl - pad)
        upper = np.minimum(upper, np.minimum(maxhi, maxhi + ru + pad))
        rl = np.maximum(rl, lower - maxhi - pad)
        ru = np.minimum(ru, np.minimum(0., upper - maxlo + pad))
        el = np.maximum(el, np.maximum(0., np.interp(rl, ex, ey) - pad))
        eu = np.minimum(eu, np.minimum(1., np.interp(ru, ex, ey) + pad))
        ql = max(ql, float(el.sum()) - pad)
        qu = min(qu, float(eu.sum()) + pad)
        hl = max(hl, float(np.interp(ql, lx, ly)) - pad, zl - maxhi - pad)
        hu = min(hu, float(np.interp(qu, lx, ly)) + pad, zu - maxlo + pad)
        ql = max(ql, float(np.interp(hl, ly, lx)) - pad)
        qu = min(qu, float(np.interp(hu, ly, lx)) + pad)
        el = np.maximum(el, ql - (eu.sum() - eu) - pad)
        eu = np.minimum(eu, qu - (el.sum() - el) + pad)
        rl = np.maximum(rl, np.array([inverse_lower(max(0., v - pad)) for v in el]) - pad)
        ru = np.minimum(ru, np.array([inverse_upper(min(1., v + pad)) for v in eu]) + pad)
        if (maxlo > maxhi or ql > qu or hl > hu or np.any(lower > upper) or
                np.any(rl > ru) or np.any(el > eu)):
            raise ValueError('empty propagated interval')
        current = np.concatenate([lower, upper, rl, ru, el, eu, [maxlo, maxhi, ql, qu, hl, hu]])
        if np.max(abs(current - previous)) < 1e-7:
            break
    return dict(original=original, term_lower=lower.tolist(), term_upper=upper.tolist(),
        maximum=[maxlo, maxhi], relative_lower=rl.tolist(), relative_upper=ru.tolist(),
        exponential_lower=el.tolist(), exponential_upper=eu.tolist(), total=[ql, qu],
        logarithm=[hl, hu], root=[zl, zu], big_m=np.minimum(big_m, maxhi - lower + pad).tolist(),
        iterations=iteration + 1, outward_padding=pad, q_cap=q_cap,
        method=('custom affine-domain forward/difference bounds, root backward interval propagation'
                if affine_max is not None else
                'affine-box forward bounds, shared-decision difference bounds, root backward interval propagation'))


def evaluate_affine_logsum(records, x, full=False):
    x = np.atleast_2d(x)
    dimension = len(next(r for r in records if r['kind'] == 'affine')['coeff'])
    if x.ndim != 2 or x.shape[1] != dimension or not np.isfinite(x).all() or not len(x):
        raise ValueError('Finite nonempty decision matrix with the declared dimension required')
    values = {f'x_{i}': x[:, i] for i in range(dimension)}
    def interpolate(name, argument, xs, ys):
        xs, ys = np.asarray(xs), np.asarray(ys)
        if argument.min() < xs[0]-1e-8 or argument.max() > xs[-1]+1e-8:
            raise ValueError('Decision leaves the compiled PWL domain')
        value = np.interp(argument, xs, ys)
        if full:
            segment = np.clip(np.searchsorted(xs, argument, side='right') - 1, 0, len(xs) - 2)
            fraction = (argument - xs[segment]) / (xs[segment + 1] - xs[segment])
            for i in range(len(xs) - 1):
                active = segment == i
                values[f'{name}_b{i}'] = active.astype(float)
                values[f'{name}_l{i}'] = (1 - fraction) * active
                values[f'{name}_r{i}'] = fraction * active
            if records[-1].get('pwl_encoding') == 'sos2':
                for i in range(len(xs)):
                    values[f'{name}_lambda{i}'] = ((segment == i) * (1 - fraction)
                                                  + (segment + 1 == i) * fraction)
        return value
    for r in records:
        name = r['name']
        if r['kind'] == 'affine':
            values[name] = r['intercept'] + x @ np.asarray(r['coeff'])
        elif r['kind'] == 'maximum':
            children = np.vstack([values[n] for n in r['children']])
            values[name] = children.max(axis=0)
            if full:
                choice = children.argmax(axis=0)
                for k, n in enumerate(r['choices']):
                    values[n] = (choice == k).astype(float)
        elif r['kind'] == 'exp':
            relative = values[r['term']] - values[r['maximum']]
            xs, ys = (r['xs'], r['ys']) if full else (r.get('evaluation_xs', r['xs']), r.get('evaluation_ys', r['ys']))
            values[name] = interpolate(name, relative, xs, ys)
            if full:
                values[r['relative']] = relative
                values[r['coordinate']] = (relative + 500.) / 500.
        elif r['kind'] == 'logsum':
            total = np.sum([values[n] for n in r['children']], axis=0)
            xs, ys = (r['xs'], r['ys']) if full else (r.get('evaluation_xs', r['xs']), r.get('evaluation_ys', r['ys']))
            logarithm = interpolate(r['logarithm'], total, xs, ys)
            values[name] = values[r['maximum']] + logarithm
            if full:
                values[r['total']] = total
                values[r['logarithm']] = logarithm
        else:
            raise ValueError(r['kind'])
    return values


def compile_affine_logsum(intercepts, coefficients, *, breakpoint_count=9):
    """Compile an unconstrained binary affine log-sum using the original PWL grid.

    Bounds use common-decision affine differences and preserve the original
    exponential/logarithm curves, including guard segments. No event threshold
    is imposed on a numerator or denominator separately.
    """
    b, a = np.asarray(intercepts, dtype=float), np.asarray(coefficients, dtype=float)
    if (b.ndim != 1 or len(b) < 2 or a.ndim != 2 or a.shape[0] != len(b)
            or a.shape[1] < 1 or not np.isfinite(b).all() or not np.isfinite(a).all()):
        raise ValueError('At least two finite affine terms with matching nonzero dimension required')
    policy = PiecewiseBreakpointPolicy(piecewise_breakpoint_count=breakpoint_count)
    guard = resolve_guarded_exponential_spec(base_x_points=policy.exp_breakpoints(),
                                            base_y_points=policy.exp_values())
    ex, ey = list(guard['exp_x_points']), list(guard['exp_y_points'])
    lx, ly = list(policy.log_breakpoints(max_terms=len(b))), list(policy.log_values(max_terms=len(b)))
    interval = [float(np.max(b+np.minimum(a, 0).sum(1)))-1e-7,
                float(np.max(b+np.maximum(a, 0).sum(1)))+math.log(len(b))+1e-7]
    bounds = tighten_affine_logsum_bounds(b, a, ex, ey, lx, ly, root_interval=interval)
    records = [dict(kind='affine', name=f't_{j}', intercept=float(v), coeff=a[j].tolist()) for j,v in enumerate(b)]
    records.append(dict(kind='maximum', name='maximum', children=[f't_{j}' for j in range(len(b))],
                        choices=[f'max_choice_{j}' for j in range(len(b))]))
    for j in range(len(b)):
        lo, hi = bounds['relative_lower'][j], bounds['relative_upper'][j]
        xs, ys = clip_table(ex, ey, lo, hi)
        records.append(dict(kind='exp', name=f'exp_{j}', term=f't_{j}', maximum='maximum',
            relative=f'relative_{j}', coordinate=f'coordinate_{j}', xs=xs, ys=ys,
            evaluation_xs=ex, evaluation_ys=ey))
    xs, ys = clip_table(lx, ly, *bounds['total'])
    records.append(dict(kind='logsum', name='root', maximum='maximum', total='total', logarithm='logarithm',
        children=[f'exp_{j}' for j in range(len(b))], xs=xs, ys=ys, evaluation_xs=lx, evaluation_ys=ly,
        breakpoint_policy=policy.to_dict(), exponential_guard=guard, tightened_bounds=bounds,
        pwl_encoding='sos2', binary_dimension=a.shape[1], root_interval=interval))
    return records


def _bound_map(bounds):
    result = {name: bounds[name] for name in ('maximum', 'total', 'logarithm', 'root')}
    for prefix, key in [('t', 'term'), ('relative', 'relative'), ('exp', 'exponential')]:
        result.update({f'{prefix}_{j}': [lo, hi] for j, (lo, hi) in
            enumerate(zip(bounds[key+'_lower'], bounds[key+'_upper']))})
    return result


def conditional_affine_bounds(records):
    """Propagate each one-bit restriction without enumerating complete decisions."""
    terms = [r for r in records if r['kind'] == 'affine']
    b = np.array([r['intercept'] for r in terms])
    a = np.array([r['coeff'] for r in terms])
    exp = next(r for r in records if r['kind'] == 'exp')
    log = records[-1]
    result = []
    for i in range(a.shape[1]):
        pair = []
        for bit in (0, 1):
            fixed = a.copy()
            fixed[:, i] = 0
            bounds = tighten_affine_logsum_bounds(b+bit*a[:,i], fixed,
                exp['evaluation_xs'], exp['evaluation_ys'], log['evaluation_xs'], log['evaluation_ys'],
                root_interval=log['root_interval'], q_cap=log['tightened_bounds']['q_cap'])
            pair.append(_bound_map(bounds))
        result.append(pair)
    return result


def compile_binary_mixture_log_ratio(binary_logits, mixture_logits, event_logits, *, event_value=0,
                                      breakpoint_count=9):
    """Marginalize Gaussian leaves and compile fitted numerator and denominator.

    Each component contains independent Bernoulli business features and one
    Bernoulli event. Event value is caller-owned; no uniform-denominator shortcut
    or post hoc probability clipping is used.
    """
    b = np.asarray(binary_logits, dtype=float)
    mix = np.asarray(mixture_logits, dtype=float)
    event = np.asarray(event_logits, dtype=float)
    if (b.ndim != 2 or mix.ndim != 1 or event.shape != mix.shape or b.shape[0] != len(mix)
            or not np.isfinite(b).all() or not np.isfinite(mix).all() or not np.isfinite(event).all()
            or event_value not in (0, 1)):
        raise ValueError('Finite matching binary/mixture/event logits and binary event value required')
    # Preserve the qualified probability-coordinate conversion and its rounding.
    from scipy.special import expit, logsumexp
    p = expit(b)
    w = np.exp(mix-logsumexp(mix))
    event_probability = expit(event if event_value else -event)
    if not np.all((p > 0) & (p < 1)) or not np.all(w > 0) or not np.all(event_probability > 0):
        raise ValueError('Strictly positive representable leaf/mixture probabilities required')
    a = np.log(p)-np.log1p(-p)
    queries = {}
    for name, weights in [('numerator', w*event_probability), ('denominator', w)]:
        intercepts = np.log1p(-p).sum(1)+np.log(weights)
        queries[name] = compile_affine_logsum(intercepts, a, breakpoint_count=breakpoint_count)
    return dict(kind='conditional_log_ratio', queries=queries, binary_dimension=b.shape[1], event_value=int(event_value))


def evaluate_binary_log_ratio(records, decisions, full=False):
    decisions = np.atleast_2d(decisions)
    dimension = len(next(r for r in records['queries']['denominator'] if r['kind']=='affine')['coeff'])
    if decisions.ndim != 2 or decisions.shape[1] != dimension:
        raise ValueError('Decision dimension differs from the compiled binary domain')
    values = {f'x_{i}': decisions[:,i] for i in range(dimension)}
    for name, query in records['queries'].items():
        computed = evaluate_affine_logsum(query, decisions, full)
        if full:
            for j in range(sum(r['kind']=='affine' for r in query)):
                for i in range(dimension):
                    computed[f'disagg_{j}_{i}'] = computed[f'max_choice_{j}']*decisions[:,i]
        values.update({f'{name}__{k}': v for k,v in computed.items() if not k.startswith('x_')})
    values['root'] = values['numerator__root']-values['denominator__root']
    return values


def validate_affine_logsum(records):
    """Validate the serialized specialized graph before mutating a solver model."""
    terms = [r for r in records if r['kind']=='affine']
    exps = [r for r in records if r['kind']=='exp']
    maxima = [r for r in records if r['kind']=='maximum']
    if not terms or len(exps)!=len(terms) or len(maxima)!=1 or records[-1]['kind']!='logsum':
        raise ValueError('Malformed affine log-sum graph')
    if ([r['name'] for r in terms]!=[f't_{j}' for j in range(len(terms))]
            or [r['name'] for r in exps]!=[f'exp_{j}' for j in range(len(terms))]):
        raise ValueError('Affine and exponential term order differs from the compiled graph')
    log = records[-1]
    bounds = log['tightened_bounds']
    for field in ('term','relative','exponential'):
        lo,hi = np.array(bounds[field+'_lower']),np.array(bounds[field+'_upper'])
        if lo.shape!=(len(terms),) or hi.shape!=lo.shape or not np.isfinite([lo,hi]).all() or np.any(lo>hi):
            raise ValueError('Invalid compiled term bounds')
    for field in ('maximum','total','logarithm','root'):
        pair = np.asarray(bounds[field])
        if pair.shape!=(2,) or not np.isfinite(pair).all() or pair[0]>pair[1]:
            raise ValueError('Invalid compiled aggregate bounds')
    for record in exps+[log]:
        xs,ys,ex,ey = [np.asarray(record[k],dtype=float) for k in ('xs','ys','evaluation_xs','evaluation_ys')]
        if (xs.ndim!=1 or xs.shape!=ys.shape or len(xs)<2 or ex.ndim!=1 or ex.shape!=ey.shape or len(ex)<2
                or not all(np.isfinite(v).all() for v in (xs,ys,ex,ey))
                or np.any(np.diff(xs)<=0) or np.any(np.diff(ex)<=0)
                or np.any(np.diff(ys)<0) or np.any(np.diff(ey)<0)
                or xs[0]<ex[0] or xs[-1]>ex[-1]
                or not np.allclose(ys,np.interp(xs,ex,ey),atol=1e-14,rtol=0)):
            raise ValueError('PWL restrictions must preserve the original monotone curve')
        if record['kind']=='exp' and (ex[0]!=-500 or ex[-1]!=0 or ey[0]!=0 or ey[-1]!=1 or xs[-1]>0):
            raise ValueError('The guarded exponential domain must span [-500,0] with values [0,1]')
    # Conditional propagation validates affine coefficients and the root interval;
    # all referenced variable names must belong to this canonical local graph.
    if log['name']!='root' or log['total']!='total' or log['logarithm']!='logarithm':
        raise ValueError('Invalid aggregate variable names')
    for j,record in enumerate(exps):
        if record['relative']!=f'relative_{j}' or record['coordinate']!=f'coordinate_{j}':
            raise ValueError('Invalid exponential attachment variable names')


__all__ = ['compile_affine_logsum', 'compile_binary_mixture_log_ratio', 'conditional_affine_bounds', 'evaluate_affine_logsum', 'evaluate_binary_log_ratio', 'validate_affine_logsum']
