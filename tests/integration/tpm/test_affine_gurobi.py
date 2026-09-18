"""Optional licensed attachment checks; no commercial solver in routine imports."""
from copy import deepcopy
from itertools import product
import math
import numpy as np
import pytest
from open_energy_lab.tpm.affine import compile_binary_mixture_log_ratio,evaluate_binary_log_ratio
from open_energy_lab.tpm.affine_gurobi import attach_affine_log_ratio,check_affine_sos_assignments


def test_generic_attachment_shares_decisions_preserves_objective_and_all_assignments():
    import gurobipy as gp
    rng=np.random.default_rng(9)
    records=compile_binary_mixture_log_ratio(rng.normal(size=(4,3)),rng.normal(size=4),np.array([1.,-2.,0.,3.]))
    env=gp.Env(empty=True);env.setParam('OutputFlag',0);env.start()
    model=gp.Model(env=env)
    try:
        decisions=[model.addVar(vtype='B',name=f'business_{i}') for i in range(3)]
        model.setObjective(decisions[0]+2*decisions[1]+3*decisions[2],gp.GRB.MINIMIZE)
        model.update();before=str(model.getObjective())
        attachment=attach_affine_log_ratio(model,decisions,records,namespace='event0')
        assert str(model.getObjective())==before and model.ModelSense==gp.GRB.MINIMIZE
        assert math.isinf(model.Params.TimeLimit)
        assert model.NumBinVars==3+2*4
        assert attachment.root.LB==-math.inf and attachment.root.UB==math.inf
        assert all(v.BranchPriority==0 for v in decisions)
        points=np.array(list(product((0,1),repeat=3)))
        values=evaluate_binary_log_ratio(records,points,full=True)
        assigned={variable.VarName:values[key] for key,variable in attachment.variables.items()}
        vector=np.vstack([assigned[v.VarName] for v in model.getVars()])
        rows=model.getConstrs();rhs=np.array([c.RHS for c in rows])[:,None]
        sense=np.array([c.Sense for c in rows])[:,None]
        diff=model.getA()@vector-rhs
        residual=np.where(sense=='=',abs(diff),np.where(sense=='<',np.maximum(diff,0),np.maximum(-diff,0)))
        assert residual.max()<1e-6
        lo=np.array([v.LB for v in model.getVars()])[:,None];hi=np.array([v.UB for v in model.getVars()])[:,None]
        assert np.maximum(lo-vector,0).max()<1e-6 and np.maximum(vector-hi,0).max()<1e-6
        check_affine_sos_assignments(model,assigned)
        before=(model.NumVars,model.NumConstrs)
        with pytest.raises(ValueError,match='namespace'):
            attach_affine_log_ratio(model,decisions,records,namespace='event0')
        assert (model.NumVars,model.NumConstrs)==before
        malformed=deepcopy(records)
        malformed['queries']['numerator'][-1]['ys'][0]+=1
        with pytest.raises(ValueError,match='PWL'):
            attach_affine_log_ratio(model,decisions,malformed,namespace='bad')
        assert (model.NumVars,model.NumConstrs)==before
        second=attach_affine_log_ratio(model,decisions,records,namespace='another_event')
        assert model.NumBinVars==3+4*4
        assert second.root.VarName=='another_event__root'
    finally:model.dispose();env.dispose()
