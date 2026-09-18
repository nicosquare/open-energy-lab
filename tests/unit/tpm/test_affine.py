"""Curve-preserving affine queries, partial binary bounds and group cuts."""
from itertools import product
import json
import numpy as np
import pytest
from open_energy_lab.tpm.affine import (compile_affine_logsum,conditional_affine_bounds,
    compile_binary_mixture_log_ratio,evaluate_binary_log_ratio,evaluate_affine_logsum)
from open_energy_lab.tpm.binary_cuts import CompiledProbabilitySeparator,ConditionalFaceCertifier


def test_affine_and_one_bit_bounds_cover_every_three_dimensional_assignment():
    rng=np.random.default_rng(9)
    b=rng.normal(size=5)-4;a=rng.normal(size=(5,3))
    graph=compile_affine_logsum(b,a)
    points=np.array(list(product((0,1),repeat=3)))
    values=evaluate_affine_logsum(graph,points,full=True)
    exp=next(r for r in graph if r['kind']=='exp');log=graph[-1]
    terms=b+points@a.T;maximum=terms.max(1)
    expected=maximum+np.interp(np.interp(terms-maximum[:,None],exp['evaluation_xs'],exp['evaluation_ys']).sum(1),log['evaluation_xs'],log['evaluation_ys'])
    np.testing.assert_allclose(values['root'],expected,atol=1e-12,rtol=0)
    conditional=conditional_affine_bounds(graph)
    for i,pair in enumerate(conditional):
        for bit,bounds in enumerate(pair):
            selected=points[:,i]==bit
            for name,(lo,hi) in bounds.items():
                assert np.all(values[name][selected]>=lo-1e-7),(name,lo)
                assert np.all(values[name][selected]<=hi+1e-7),(name,hi)
    reloaded=json.loads(json.dumps(graph,allow_nan=False))
    np.testing.assert_array_equal(evaluate_affine_logsum(reloaded,points,full=True)['root'],values['root'])


def test_ratio_has_fitted_denominator_and_dimension_independent_certificates():
    rng=np.random.default_rng(3)
    binary=rng.normal(size=(4,3));mix=rng.normal(size=4);event=np.array([1.,2.,3.,-1.])
    records=compile_binary_mixture_log_ratio(binary,mix,event)
    points=np.array(list(product((0,1),repeat=3)))
    log=evaluate_binary_log_ratio(records,points)['root']
    den=evaluate_affine_logsum(records['queries']['denominator'],points)['root']
    assert np.ptp(den)>.1
    certifier=ConditionalFaceCertifier(records,log_lower=np.log(.8))
    certificates=[]
    for point in points:
        for depth in range(4):
            fixed=np.arange(3)<depth
            covered=np.all(points[:,fixed]==point[fixed],axis=1)
            assert log[covered].max()<=certifier.log_upper(point,fixed)
        certificate=certifier.certify(point)
        if certificate:
            fixed=list(certificate.fixed_indices)
            covered=np.all(points[:,fixed]==point[fixed],axis=1)
            assert log[covered].max()<=certificate.log_upper_bound<np.log(.8)
            certificates.append(certificate)
    assert certificates
    one=compile_binary_mixture_log_ratio(binary,mix,event,event_value=1)
    # Event-one and event-zero are each compiled from the same fitted denominator.
    np.testing.assert_array_equal(evaluate_affine_logsum(one['queries']['denominator'],points)['root'],den)


def test_solver_independent_cuts_use_compiled_probability_and_cache_queries():
    queries=[]
    def evaluate(bits):
        queries.append(bits)
        return np.log(.2) if bits==(1,0,1) else np.log(.95)
    separator=CompiledProbabilitySeparator(3,evaluate,log_lower=np.log(.9))
    cut=separator.separate([.9,.1,.9]);assert cut is not None
    assert sum(a*b for a,b in zip(cut.coefficients,cut.bits))<cut.rhs
    assert separator.separate([1,0,1])==cut
    assert queries==[(1,0,1)]
    for point in product((0,1),repeat=3):
        if point!=cut.bits:assert sum(a*b for a,b in zip(cut.coefficients,point))>=cut.rhs


@pytest.mark.parametrize('b,a', [([1],[[1,2]]),([1,2],[[1],[2,3]]),([1,float('nan')],[[1],[2]])])
def test_invalid_affine_inputs_fail_closed(b,a):
    with pytest.raises(ValueError):compile_affine_logsum(b,a)


def test_specialized_modules_import_without_optional_backends():
    import subprocess
    import sys
    result = subprocess.run([sys.executable, '-c', '''
import importlib.abc, sys
sys.path.insert(0, sys.argv[1])
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch','spflow','gurobipy','pyomo','highspy'}:
            raise AssertionError('Eager optional backend: '+fullname)
sys.meta_path.insert(0, Block())
import open_energy_lab.tpm.product_mixture
import open_energy_lab.tpm.affine
import open_energy_lab.tpm.affine_gurobi
import open_energy_lab.tpm.binary_cuts
''', str(__import__('pathlib').Path(__file__).resolve().parents[3] / 'src')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
