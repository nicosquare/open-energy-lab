"""Full categorical PWL bounds contain every admissible tiny-domain assignment."""
import itertools
import json
import math
import os
import numpy as np
import pytest

from open_energy_lab.tpm.categorical_gurobi import (
    curves, compile_categorical_log_ratio, evaluate_categorical_log_ratio,
    attach_categorical_log_ratio, categorical_attachment_witness,
)


def fixture():
    den=np.log([.2,.3,.5]);num=den+np.log([.01,.08,.2])
    tables=[np.log([[.6,.3,.1],[.1,.3,.6],[.3,.4,.3]]),
            np.log([[.8,.2],[.3,.7],[.5,.5]])]
    q=np.array(list(itertools.product(range(3),range(2))))
    return den,num,tables,q


def reference(q,b,tables,c):
    terms=b+sum(t[:,q[:,i]].T for i,t in enumerate(tables))
    maximum=terms.max(1)
    return maximum+np.interp(np.interp(terms-maximum[:,None],c['ex'],c['ey']).sum(1),c['lx'],c['ly'])


def test_direct_reference_roundtrip_and_outward_bounds():
    den,num,tables,q=fixture()
    records=compile_categorical_log_ratio(den,num,tables)
    restored=json.loads(json.dumps(records,allow_nan=False))
    detail=evaluate_categorical_log_ratio(restored,q,details=True)
    expected=reference(q,num,tables,records['curves'])-reference(q,den,tables,records['curves'])
    np.testing.assert_allclose(detail['log_ratio'],expected,atol=1e-12)
    for query,bound in zip(detail['queries'],records['bounds']):
        for field in ('maximum','total','logarithm','root'):
            assert query[field].min()>=bound[field][0]-1e-7
            assert query[field].max()<=bound[field][1]+1e-7
    with pytest.raises(ValueError,match='integer'):
        evaluate_categorical_log_ratio(records,[[.5,0]])


def test_conditional_restrictions_never_remove_feasible_tiny_orders():
    den,num,tables,q=fixture();records=compile_categorical_log_ratio(den,num,tables,log_limit=math.log(.1))
    scores=evaluate_categorical_log_ratio(records,q)
    for order,score in zip(q,scores):
        if score<=math.log(.1):
            for i,k in enumerate(order):
                assert records['conditional'][i][k] is not None
    assert records['allowed']==[[0,1,2],[0,1]]  # cold build did not invent an objective floor


def test_impossible_risk_keeps_explicit_full_attachment_disposition():
    den,num,tables,q=fixture();records=compile_categorical_log_ratio(den,num,tables,log_limit=math.log(.0001))
    assert records['infeasible']
    assert all(evaluate_categorical_log_ratio(records,q)>math.log(.0001))
    assert len(records['bounds'])==2


def test_external_curves_are_preserved_and_invalid_grids_rejected():
    den,num,tables,q=fixture();c=curves(3,points=5)
    records=compile_categorical_log_ratio(den,num,tables,curve_values=c,allowed=[[0,2],[0,1]])
    assert records['curves']==c
    invalid=dict(c,ex=[*c['ex'][:-1],1])
    with pytest.raises(ValueError,match='endpoints'):
        compile_categorical_log_ratio(den,num,tables,curve_values=invalid)


@pytest.mark.licensed_gurobi
@pytest.mark.skipif(os.environ.get('OEL_RUN_LICENSED_TESTS') != '1', reason='licensed check requires explicit opt-in')
def test_full_fixed_attachments_and_witnesses_match_direct_values():
    gp=pytest.importorskip('gurobipy')
    den,num,tables,orders=fixture()
    records=compile_categorical_log_ratio(den,num,tables)  # no chance row for high-risk checks
    with gp.Env(empty=True) as env:
        env.setParam('OutputFlag',0);env.start()
        with gp.Model(env=env) as model:
            q=[model.addVar(vtype=gp.GRB.INTEGER,lb=0,ub=t.shape[1]-1,name=f'q{i}') for i,t in enumerate(tables)]
            z=[[model.addVar(vtype=gp.GRB.BINARY,name=f'z{i}_{k}') for k in range(t.shape[1])] for i,t in enumerate(tables)]
            attachment=attach_categorical_log_ratio(model,q,z,records)
            model.Params.Threads=1;model.Params.FeasibilityTol=1e-8;model.Params.IntFeasTol=1e-8;model.Params.TimeLimit=5
            variables=model.getVars();constraints=model.getConstrs();matrix=model.getA()
            rhs=np.array([c.RHS for c in constraints]);sense=np.array([c.Sense for c in constraints])
            for order in orders:
                for i,value in enumerate(order):q[i].LB=q[i].UB=int(value)
                model.update()
                witness=categorical_attachment_witness(attachment,order)
                assert set(witness)=={v.VarName for v in variables}
                x=np.array([witness[v.VarName] for v in variables]);delta=matrix@x-rhs
                residual=np.where(sense=='=',abs(delta),np.where(sense=='<',np.maximum(delta,0),np.maximum(-delta,0)))
                assert max(residual)<1e-6
                for var,value in zip(variables,x):
                    assert var.LB-1e-6<=value<=var.UB+1e-6
                model.optimize();assert model.Status==gp.GRB.OPTIMAL
                actual=attachment['graphs'][1]['root'].X-attachment['graphs'][0]['root'].X
                assert actual==pytest.approx(evaluate_categorical_log_ratio(records,order)[0],abs=1e-6)


@pytest.mark.licensed_gurobi
@pytest.mark.skipif(os.environ.get('OEL_RUN_LICENSED_TESTS') != '1', reason='licensed check requires explicit opt-in')
def test_cold_chance_attachment_matches_exhaustive_optimum():
    gp=pytest.importorskip('gurobipy')
    den,num,tables,orders=fixture();limit=math.log(.1)
    records=compile_categorical_log_ratio(den,num,tables,log_limit=limit)
    values=orders@np.array([3,2]);safe=evaluate_categorical_log_ratio(records,orders)<=limit
    assert safe.any()
    with gp.Env(empty=True) as env:
        env.setParam('OutputFlag',0);env.start()
        with gp.Model(env=env) as model:
            q=[model.addVar(vtype=gp.GRB.INTEGER,lb=0,ub=t.shape[1]-1,name=f'q{i}') for i,t in enumerate(tables)]
            z=[[model.addVar(vtype=gp.GRB.BINARY,name=f'z{i}_{k}') for k in range(t.shape[1])] for i,t in enumerate(tables)]
            attach_categorical_log_ratio(model,q,z,records)
            model.setObjective(3*q[0]+2*q[1],gp.GRB.MAXIMIZE)
            model.Params.Threads=1;model.Params.TimeLimit=5
            assert model.NumStart==0
            model.optimize();assert model.Status==gp.GRB.OPTIMAL
            assert model.ObjVal==pytest.approx(values[safe].max())


def test_group_certification_preserves_every_legal_feasible_completion():
    from open_energy_lab.tpm.categorical_gurobi import CategoricalGroupSeparator
    orders=np.array(list(itertools.product(range(4),repeat=3)))
    scores=dict(zip(map(tuple,orders),np.random.default_rng(45).uniform(-5,-1,len(orders))))
    oracle=lambda q:np.array([scores[tuple(row)] for row in q])
    legal=lambda q:np.asarray(q)@np.array([1,2,3])<=10
    separator=CategoricalGroupSeparator(oracle,[range(4)]*3,legal,-3,evaluation_budget=17,dimension_order=[2,0,1])
    certificates=[]
    for order in orders:
        certificate=separator.certify(order)
        if certificate is None:continue
        certificates.append(certificate)
        assert certificate['evaluated']<=17
        assert separator.audit(certificate)['passed']
        for point in orders[legal(orders)]:
            if scores[tuple(point)]<=-3:
                assert sum(point[i] in group for i,group in enumerate(certificate['groups']))<=2
    assert certificates
    with pytest.raises(ValueError,match='Invalid group'):
        separator.audit(dict(groups=[list(range(4))]*3))
    with pytest.raises(ValueError,match='integer'):
        separator.certify([.5,0,0])


def test_group_guard_nonfinite_and_malformed_domains_fail_closed():
    from open_energy_lab.tpm.categorical_gurobi import CategoricalGroupSeparator
    legal=lambda q:np.ones(len(q),dtype=bool)
    for bad in (math.nan, math.inf):
        separator=CategoricalGroupSeparator(lambda q:np.full(len(q),bad),[range(2)]*2,legal,-3)
        with pytest.raises(ValueError,match='Nonfinite'):separator.certify([0,0])
    boundary=CategoricalGroupSeparator(lambda q:np.full(len(q),-3+1e-10),[range(2)]*2,legal,-3)
    assert boundary.certify([1,1]) is None
    with pytest.raises(ValueError):CategoricalGroupSeparator(lambda q:q,[[0,.5]],legal,-3)
    with pytest.raises(ValueError):CategoricalGroupSeparator(lambda q:q,[[0,0]],legal,-3)


def test_incumbent_restrictions_preserve_all_better_feasible_objectives():
    from open_energy_lab.tpm.categorical_gurobi import restrict_categorical_domains
    den,num,tables,orders=fixture();limit=math.log(.1)
    records=compile_categorical_log_ratio(den,num,tables,log_limit=limit)
    profits=[np.array([0.,-2.,4.]),np.array([0.,3.])]
    legal=lambda q:np.asarray(q).sum(1)<=2
    oracle=lambda q:evaluate_categorical_log_ratio(records,q)
    feasible=legal(orders)&(oracle(orders)<=limit)
    start=orders[feasible][0]
    restriction=restrict_categorical_domains(profits,start,oracle,legal,limit)
    values=sum(p[orders[:,i]] for i,p in enumerate(profits))
    for order in orders[feasible&(values>=restriction['incumbent_objective'])]:
        assert all(int(k) in domain for k,domain in zip(order,restriction['allowed']))
    assert restriction['floor']<=restriction['incumbent_objective']
    cold=restrict_categorical_domains(profits,None,oracle,legal,limit)
    assert cold['floor'] is None and cold['allowed']==[list(range(3)),list(range(2))]
    with pytest.raises(ValueError,match='feasible'):
        restrict_categorical_domains(profits,[2,1],oracle,legal,limit)
    with pytest.raises(ValueError,match='integer'):
        restrict_categorical_domains(profits,[.2,0],oracle,legal,limit)
