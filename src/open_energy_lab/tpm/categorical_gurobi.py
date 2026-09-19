"""Full categorical conditional log-PWL circuits and complete Gurobi witnesses.

Mathematical promotion of the tested helpers in tpm_for_sp:
scripts/method_development/newsvendor_shifted_categorical.py (pair/interval bounds)
and newsvendor_unfiltered_cuts_probe.py (coupled bounds and SOS2 graphs).
No benchmark dimension, storage, objective, solver settings or data access lives
here. Clipping a graph preserves its original interpolation, not a refitted PWL.
"""
import math
import numpy as np

def curves(k,points=9):
    from open_energy_lab.tpm.piecewise import PiecewiseBreakpointPolicy,resolve_guarded_exponential_spec
    policy=PiecewiseBreakpointPolicy(piecewise_breakpoint_count=points)
    guard=resolve_guarded_exponential_spec(base_x_points=policy.exp_breakpoints(),base_y_points=policy.exp_values())
    return dict(ex=list(guard['exp_x_points']),ey=list(guard['exp_y_points']),
        lx=list(policy.log_breakpoints(max_terms=k)),ly=list(policy.log_values(max_terms=k)),
        policy=policy.to_dict(),guard=guard)


def pair_bounds(b,tables):
    """Max(t_j-t_l) over the exactly-one categorical domains, not unit boxes."""
    parts=[]
    for t in tables:
        part=np.full((len(b),len(b)),-np.inf)
        for k in range(t.shape[1]):np.maximum(part,t[:,k,None]-t[None,:,k],out=part)
        parts.append(part)
    allpairs=b[:,None]-b[None,:]+sum(parts)
    return parts,allpairs


def _propagate(lower,upper,big_m,relative_upper,c,root_interval):
    pad=1e-8;lower=np.array(lower,copy=True)-pad;upper=np.array(upper,copy=True)+pad
    rl=-np.array(big_m)-pad;ru=np.minimum(0.,np.array(relative_upper)+pad)
    if rl.min()<c['ex'][0]:raise ValueError('bound outside exponential curve')
    el=np.interp(rl,c['ex'],c['ey']);eu=np.interp(ru,c['ex'],c['ey'])
    ml,mh=float(lower.max()),float(upper.max());ql,qh=1.,float(len(lower))
    hl,hh=float(np.interp(ql,c['lx'],c['ly'])),float(np.interp(qh,c['lx'],c['ly']))
    zl,zh=root_interval
    ex,ey=np.array(c['ex']),np.array(c['ey'])
    def inverse(values,side):
        v=np.clip(values,ey[0],ey[-1]);j=np.clip(np.searchsorted(ey,v,side=side),1,len(ey)-1)
        denom=ey[j]-ey[j-1]
        out=ex[j-1]+np.divide((v-ey[j-1])*(ex[j]-ex[j-1]),denom,out=np.zeros_like(v),where=denom>0)
        below=values<=ey[0] if side=='left' else values<ey[0]
        return np.where(below,ex[0],np.where(values>=ey[-1],ex[-1],out))
    for iteration in range(100):
        before=np.r_[lower,upper,rl,ru,el,eu,ml,mh,ql,qh,hl,hh]
        ml=max(ml,float(lower.max()),zl-hh-pad);mh=min(mh,float(upper.max()),zh-hl+pad)
        lower=np.maximum(lower,ml+rl-pad);upper=np.minimum(upper,np.minimum(mh,mh+ru+pad))
        rl=np.maximum(rl,lower-mh-pad);ru=np.minimum(ru,np.minimum(0.,upper-ml+pad))
        el=np.maximum(el,np.maximum(0.,np.interp(rl,ex,ey)-pad));eu=np.minimum(eu,np.minimum(1.,np.interp(ru,ex,ey)+pad))
        ql=max(ql,float(el.sum())-pad);qh=min(qh,float(eu.sum())+pad)
        hl=max(hl,float(np.interp(ql,c['lx'],c['ly']))-pad,zl-mh-pad)
        hh=min(hh,float(np.interp(qh,c['lx'],c['ly']))+pad,zh-ml+pad)
        ql=max(ql,float(np.interp(hl,c['ly'],c['lx']))-pad);qh=min(qh,float(np.interp(hh,c['ly'],c['lx']))+pad)
        el=np.maximum(el,ql-(eu.sum()-eu)-pad);eu=np.minimum(eu,qh-(el.sum()-el)+pad)
        if ml>mh or ql>qh or hl>hh or np.any(lower>upper) or np.any(rl>ru) or np.any(el>eu):return None
        rl=np.maximum(rl,inverse(np.maximum(0.,el-pad),'left')-pad)
        ru=np.minimum(ru,inverse(np.minimum(1.,eu+pad),'right')+pad)
        if np.any(rl>ru):return None
        after=np.r_[lower,upper,rl,ru,el,eu,ml,mh,ql,qh,hl,hh]
        if abs(after-before).max()<1e-7:break
    return dict(term_lower=lower.tolist(),term_upper=upper.tolist(),maximum=[ml,mh],
        relative_lower=rl.tolist(),relative_upper=ru.tolist(),exponential_lower=el.tolist(),exponential_upper=eu.tolist(),
        total=[ql,qh],logarithm=[hl,hh],root=[zl,zh],big_m=np.minimum(big_m+pad,mh-lower+pad).tolist(),iterations=iteration+1)


def flat_bounds(bounds):
    out={k:bounds[k] for k in ['maximum','total','logarithm','root']}
    for prefix,key in [('t','term'),('relative','relative'),('exp','exponential')]:
        out.update({f'{prefix}_{j}':[lo,hi] for j,(lo,hi) in enumerate(zip(bounds[key+'_lower'],bounds[key+'_upper']))})
    return out

def _coupled_bounds(bs, tables, c, pairs, log_limit, fixed=None):
    """Outward intervals, optionally constrained by the caller's log-risk limit."""
    selected = [t[:, fixed[1]:fixed[1]+1] if fixed and i == fixed[0] else t for i, t in enumerate(tables)]
    low = [b + sum(t.min(1) for t in selected) for b in bs]
    high = [b + sum(t.max(1) for t in selected) for b in bs]
    roots = [[float(lo.max())-1e-7, float(hi.max())+math.log(len(lo))+1e-7] for lo, hi in zip(low, high)]
    result = None
    for _ in range(8):
        if log_limit is not None:
            roots[1][1] = min(roots[1][1], roots[0][1] + log_limit + 1e-8)
            roots[0][0] = max(roots[0][0], roots[1][0] - log_limit - 1e-8)
        if any(lo > hi for lo, hi in roots):
            return None
        result = [_propagate(lo, hi, np.maximum(0., dp.max(0)), np.minimum(0., dp.min(1)), c, roots[j])
                  for j, (lo, hi, dp) in enumerate(zip(low, high, pairs))]
        if any(r is None for r in result):
            return None
        new = [[max(roots[j][0], r['maximum'][0] + r['logarithm'][0] - 1e-8),
                min(roots[j][1], r['maximum'][1] + r['logarithm'][1] + 1e-8)] for j, r in enumerate(result)]
        change = np.max(np.abs(np.array(new)-roots)); roots = new
        if change < 1e-7:
            break
    return result



def _parameters(denominator, numerator, tables):
    den, num = np.asarray(denominator,dtype=float), np.asarray(numerator,dtype=float)
    tables = [np.asarray(t,dtype=float) for t in tables]
    if (den.ndim!=1 or len(den)<2 or num.shape!=den.shape or not tables
            or any(t.ndim!=2 or t.shape[0]!=len(den) or t.shape[1]<1 for t in tables)
            or not all(np.isfinite(x).all() for x in [den,num,*tables])):
        raise ValueError('finite categorical mixture intercepts and leaf tables required')
    return den,num,tables


def _curve_contract(c, components):
    for x,y in [('ex','ey'),('lx','ly')]:
        xx, yy=np.asarray(c[x],dtype=float),np.asarray(c[y],dtype=float)
        if (xx.ndim!=1 or yy.shape!=xx.shape or len(xx)<2
                or not np.isfinite(xx).all() or not np.isfinite(yy).all()
                or np.any(np.diff(xx)<=0) or np.any(np.diff(yy)<0)):
            raise ValueError('PWL curves must have finite increasing abscissae and monotone ordinates')
    if (c['ex'][-1]!=0 or c['ey'][-1]!=1 or min(c['ey'])<0
            or c['lx'][0]!=1 or c['lx'][-1]!=components or c['ly'][0]!=0
            or abs(c['ly'][-1]-math.log(components))>1e-12):
        raise ValueError('PWL curves must preserve normalized maximum endpoints and component count')


def evaluate_categorical_log_ratio(records, orders, *, details=False):
    """Direct evaluation of the persisted conditional curves at integer orders."""
    q=np.atleast_2d(np.asarray(orders))
    tables=[np.asarray(t) for t in records['tables']]
    if (q.shape[1]!=len(tables) or not np.isfinite(q).all() or np.any(q!=np.rint(q))
            or np.any(q<0) or any(np.any(q[:,i]>=t.shape[1]) for i,t in enumerate(tables))):
        raise ValueError('orders must use the declared integer categorical support')
    q=q.astype(int);c=records['curves'];result=[]
    evidence=sum(t[:,q[:,i]].T for i,t in enumerate(tables))
    for intercept in (records['denominator'],records['numerator']):
        terms=evidence+np.asarray(intercept)
        maximum=terms.max(1);relative=terms-maximum[:,None]
        if relative.min()<c['ex'][0]-1e-8:raise ValueError('exponential curve domain insufficient')
        exponential=np.interp(relative,c['ex'],c['ey']);total=exponential.sum(1)
        if total.min()<c['lx'][0]-1e-8 or total.max()>c['lx'][-1]+1e-8:
            raise ValueError('logarithm curve domain insufficient')
        logarithm=np.interp(total,c['lx'],c['ly'])
        result.append(dict(terms=terms,maximum=maximum,relative=relative,exponential=exponential,
                           total=total,logarithm=logarithm,root=maximum+logarithm))
    ratio=result[1]['root']-result[0]['root']
    return dict(log_ratio=ratio,queries=result) if details else ratio


def compile_categorical_log_ratio(denominator, numerator, tables, *, curve_values=None,
                                  log_limit=None, allowed=None, conditional_bounds=True,
                                  progress=None):
    """Prepare compact full graphs, optionally restricting declared category domains.

    A caller narrowing domains must justify that restriction independently. No
    incumbent is required. log_limit=None prepares an unconstrained attachment
    suitable for fixed-order mathematical checks, including high-risk orders.
    """
    den,num,tables=_parameters(denominator,numerator,tables)
    if log_limit is not None and (not math.isfinite(log_limit) or log_limit>=0):
        raise ValueError('log-risk limit must be finite and negative')
    c=curves(len(den)) if curve_values is None else dict(curve_values)
    _curve_contract(c,len(den))
    if allowed is None:allowed=[list(range(t.shape[1])) for t in tables]
    if (len(allowed)!=len(tables) or any(not len(a) or any(type(k) not in (int,np.int64,np.int32) for k in a)
            or sorted(set(a))!=list(a) or min(a)<0 or max(a)>=t.shape[1] for a,t in zip(allowed,tables))):
        raise ValueError('allowed categories must be nonempty sorted unique support values')
    allowed=[list(map(int,a)) for a in allowed]
    selected=[t[:,a] for t,a in zip(tables,allowed)]
    parts,pairs=pair_bounds(den,selected);offset=num-den
    pairlist=[pairs,pairs+offset[:,None]-offset[None,:]]
    bounds=_coupled_bounds([den,num],selected,c,pairlist,log_limit)
    infeasible=bounds is None
    # Preserve a full graph even if interval propagation proves the risk row
    # impossible. The attachment adds the certified contradiction explicitly.
    if infeasible:bounds=_coupled_bounds([den,num],selected,c,pairlist,None)
    if bounds is None:raise ValueError('unconstrained circuit has inconsistent bounds')
    conditional=[]
    if conditional_bounds and not infeasible:
        for i,tab in enumerate(selected):
            row=[]
            for k in range(tab.shape[1]):
                fixed=tab[:,k];dp=pairs-parts[i]+fixed[:,None]-fixed[None,:]
                row.append(_coupled_bounds([den,num],selected,c,
                    [dp,dp+offset[:,None]-offset[None,:]],log_limit,fixed=(i,k)))
                if progress is not None:progress(i,allowed[i][k])
            conditional.append(row)
    return dict(schema='categorical-full-log-ratio-v1',denominator=den.tolist(),numerator=num.tolist(),
                tables=[t.tolist() for t in tables],curves=c,log_limit=log_limit,
                allowed=allowed,bounds=bounds,conditional=conditional,infeasible=infeasible)


def _graph(model, selectors, intercept, tables, c, prefix, bounds):
    import gurobipy as gp
    variables={};graphs=[]
    def var(name,**kw):
        result=model.addVar(name=prefix+name,**kw);variables[name]=result;return result
    terms=[]
    for j in range(len(intercept)):
        term=var(f't_{j}',lb=bounds['term_lower'][j],ub=bounds['term_upper'][j])
        model.addConstr(term==float(intercept[j])+gp.quicksum(float(t[j,k])*selectors[i][k]
            for i,t in enumerate(tables) for k in range(t.shape[1])))
        terms.append(term)
    maximum=var('maximum',lb=bounds['maximum'][0],ub=bounds['maximum'][1])
    winners=[var(f'max_choice_{j}',vtype=gp.GRB.BINARY) for j in range(len(intercept))]
    model.addConstr(gp.quicksum(winners)==1)
    for j,term in enumerate(terms):
        model.addConstr(maximum>=term)
        model.addConstr(maximum<=term+float(bounds['big_m'][j])*(1-winners[j]))
    def pwl(name,inp,inputname,xs,ys,lo,hi,outlo,outhi):
        xx=[float(lo),*(float(x) for x in xs if lo<x<hi),float(hi)] if hi>lo else [float(lo)]
        yy=np.interp(xx,xs,ys).tolist()
        out=var(name,lb=outlo,ub=outhi)
        weights=[var(f'{name}_lambda{k}',lb=0,ub=1) for k in range(len(xx))]
        model.addConstr(gp.quicksum(weights)==1)
        model.addConstr(inp==gp.quicksum(x*w for x,w in zip(xx,weights)))
        model.addConstr(out==gp.quicksum(y*w for y,w in zip(yy,weights)))
        if len(weights)>1:model.addSOS(gp.GRB.SOS_TYPE2,weights,list(range(len(weights))))
        graphs.append(dict(name=name,input=inputname,xs=xx,ys=yy))
        return out,weights,xx
    exps=[]
    for j,term in enumerate(terms):
        lo,hi=bounds['relative_lower'][j],bounds['relative_upper'][j]
        if not c['ex'][0]<=lo<=hi<=0:raise ValueError('relative bounds outside preserved curve')
        relative=var(f'relative_{j}',lb=lo,ub=hi);model.addConstr(relative==term-maximum)
        exponential,weights,xx=pwl(f'exp_{j}',relative,f'relative_{j}',c['ex'],c['ey'],lo,hi,
            bounds['exponential_lower'][j],bounds['exponential_upper'][j])
        exps.append(exponential)
        # Exact maximum selection must select the exponential endpoint 1.
        if xx[-1]==0:model.addConstr(weights[-1]>=winners[j])
        else:model.addConstr(winners[j]==0)
    total=var('total',lb=bounds['total'][0],ub=bounds['total'][1]);model.addConstr(total==gp.quicksum(exps))
    logarithm,_,_=pwl('logarithm',total,'total',c['lx'],c['ly'],*bounds['total'],*bounds['logarithm'])
    root=var('root',lb=bounds['root'][0],ub=bounds['root'][1]);model.addConstr(root==maximum+logarithm)
    return dict(root=root,variables=variables,graphs=graphs,prefix=prefix)


def attach_categorical_log_ratio(model, decisions, selectors, records, *, prefix='tpm_'):
    """Attach full circuits to caller-owned physical integers and ordered selectors."""
    import gurobipy as gp
    if records.get('schema')!='categorical-full-log-ratio-v1':raise ValueError('unknown categorical artifact')
    tables=[np.asarray(t) for t in records['tables']]
    model.update();owned=model.getVars()
    def belongs(v):
        return 0<=v.index<len(owned) and owned[v.index].sameAs(v)
    if len(decisions)!=len(tables) or len(selectors)!=len(tables):raise ValueError('decision/selector dimensions differ')
    if any(v.VarName.startswith(prefix) for v in owned):raise ValueError('attachment prefix already in use')
    for i,(q,z,t) in enumerate(zip(decisions,selectors,tables)):
        if (not belongs(q) or q.VType not in (gp.GRB.INTEGER,gp.GRB.BINARY)
                or not math.isfinite(q.LB) or not math.isfinite(q.UB)
                or q.LB<0 or q.UB>t.shape[1]-1 or len(z)!=t.shape[1]
                or any(not belongs(v) or v.VType!=gp.GRB.BINARY for v in z)
                or len({v.index for v in z})!=len(z)):
            raise ValueError('caller decisions and selectors must match integer domains and model ownership')
        model.addConstr(gp.quicksum(z)==1,name=f'{prefix}onehot_{i}')
        model.addConstr(q==gp.quicksum(k*v for k,v in enumerate(z)),name=f'{prefix}link_{i}')
        for k,v in enumerate(z):
            if k not in records['allowed'][i]:model.addConstr(v==0)
    graphs=[]
    for j,key in enumerate(('denominator','numerator')):
        graph=_graph(model,selectors,np.asarray(records[key]),tables,records['curves'],
                     prefix+('den_' if j==0 else 'num_'),records['bounds'][j])
        graphs.append(graph)
        if records['conditional']:
            names=flat_bounds(records['bounds'][j])
            for i,row in enumerate(records['conditional']):
                maps=[];z=[selectors[i][k] for k in records['allowed'][i]]
                for k,item in zip(records['allowed'][i],row):
                    if item is None:
                        model.addConstr(selectors[i][k]==0);maps.append({n:[0.,0.] for n in names})
                    else:maps.append(flat_bounds(item[j]))
                for name in names:
                    model.addConstr(graph['variables'][name]>=gp.LinExpr([x[name][0] for x in maps],z))
                    model.addConstr(graph['variables'][name]<=gp.LinExpr([x[name][1] for x in maps],z))
    if records['log_limit'] is not None:
        model.addConstr(graphs[1]['root']-graphs[0]['root']<=records['log_limit'],name=prefix+'chance')
    if records['infeasible']:model.addConstr(gp.LinExpr()<=-1,name=prefix+'interval_infeasible')
    model.update()
    return dict(graphs=graphs,decisions=list(decisions),selectors=[list(z) for z in selectors],records=records)


def categorical_attachment_witness(attachment, order):
    """Return every attachment column plus caller q/selectors; no solver search."""
    records=attachment['records'];detail=evaluate_categorical_log_ratio(records,order,details=True)
    if len(detail['log_ratio'])!=1:raise ValueError('witness requires a single order')
    q=np.asarray(order,dtype=int).reshape(-1);values={}
    for i,(v,z) in enumerate(zip(attachment['decisions'],attachment['selectors'])):
        values[v.VarName]=int(q[i])
        values.update({v.VarName:float(k==q[i]) for k,v in enumerate(z)})
    for graph,query in zip(attachment['graphs'],detail['queries']):
        winner=int(query['terms'][0].argmax())
        local={name:float(query[name][0]) for name in ('maximum','total','logarithm','root')}
        for j in range(len(records['denominator'])):
            for name,key in [('t','terms'),('relative','relative'),('exp','exponential')]:
                local[f'{name}_{j}']=float(query[key][0,j])
            local[f'max_choice_{j}']=float(j==winner)
        for curve in graph['graphs']:
            value=local[curve['input']];xs=np.asarray(curve['xs'])
            if value<xs[0]-1e-7 or value>xs[-1]+1e-7:raise ValueError('order outside attachment curve restriction')
            weights=np.zeros(len(xs))
            if len(xs)==1:weights[0]=1.
            else:
                k=int(np.clip(np.searchsorted(xs,value,side='right')-1,0,len(xs)-2))
                fraction=(value-xs[k])/(xs[k+1]-xs[k]);weights[k]=1-fraction;weights[k+1]=fraction
            local.update({f'{curve["name"]}_lambda{k}':float(w) for k,w in enumerate(weights)})
        values.update({graph['variables'][name].VarName:value for name,value in local.items()})
    return values
