"""Integer Gaussian lookup keeps native density and compiled floors distinct."""
from dataclasses import replace
import math

import pytest

from tpm import (
    TPMIntegerDecisionMapping, attach_conditional_mio_pair,
    evaluate_conditional_mio_pair, initialize_conditional_mio_attachment,
    publish_conditional_pair, load_conditional_pair,
)
from tests.unit.tpm.test_conditional_pair import _pair, _encoding


def lookup_pair():
    base = _pair()
    points = tuple((q - 40) / 120 for q in range(40, 161))
    # A narrow Gaussian deliberately exercises the compiler's density floor.
    native = tuple(-0.5 * ((x - .5) / .02) ** 2 - math.log(.02 * math.sqrt(2 * math.pi)) for x in points)
    values = tuple(max(v, math.log(1e-6)) for v in native)
    encoding = replace(_encoding('piecewise'), leaf_configuration={
        **base.encoding.leaf_configuration,
        'integer_grids': {'x': list(range(40, 161))},
    })
    def circuit(original):
        nodes = tuple(replace(node, parameters={'breakpoints': points, 'log_values': values})
                      if node.node_type == 'leaf_piecewise' else node for node in original.nodes)
        return replace(original, nodes=nodes)
    return replace(base, encoding=encoding, numerator=circuit(base.numerator),
                   denominator=circuit(base.denominator), attachment_formulation=None, pair_id='')


def lookup_caller(pair):
    import pyomo.environ as pyo
    model = pyo.ConcreteModel()
    model.q = pyo.Var(domain=pyo.Integers, bounds=(40, 160))
    model.z = pyo.Var(range(40, 161), domain=pyo.Binary)
    mapping = TPMIntegerDecisionMapping('x', model.q, tuple((k, model.z[k]) for k in model.z))
    attachment = attach_conditional_mio_pair(pair, model, mappings=(mapping,), namespace='risk')
    return model, attachment


def assign(model, value):
    model.q.set_value(value)
    for k in model.z:
        model.z[k].set_value(int(k == value))


def test_lookup_roundtrip_analytic_floor_and_fractional_rejection(tmp_path):
    pair = lookup_pair()
    publish_conditional_pair(pair, tmp_path / 'pair.json')
    loaded = load_conditional_pair(tmp_path / 'pair.json')
    assert loaded.pair_id == pair.pair_id
    assert tuple(loaded.encoding.leaf_configuration['integer_grids']['x']) == tuple(range(40, 161))
    for q in (40, 99, 100, 160):
        result = evaluate_conditional_mio_pair(loaded, declared_domain_assignments={'x': q})
        analytic = -.5 * (((q - 40) / 120 - .5) / .02) ** 2 - math.log(.02 * math.sqrt(2 * math.pi))
        assert result.denominator_log == pytest.approx(max(analytic, math.log(1e-6)))
        assert result.conditional_log_risk == pytest.approx(math.log(.3))
    assert analytic < math.log(1e-6)  # Native is unfloored, lookup intentionally is not.
    for assignments in ({'declared_domain_assignments': {'x': 40.5}},
                        {'model_coordinate_assignments': {'x': .001}}):
        with pytest.raises(ValueError, match='integer'):
            evaluate_conditional_mio_pair(loaded, **assignments)


def test_shared_selectors_complete_witness_preserves_caller_state():
    import pyomo.environ as pyo
    pair = lookup_pair()
    model, attachment = lookup_caller(pair)
    assign(model, 100)
    model.q.fix()
    initial = [(id(v), v.value, v.fixed, v.lb, v.ub) for v in (model.q, *model.z.values())]
    result = initialize_conditional_mio_attachment(pair, attachment, declared_domain_assignments={'x': 100})
    assert initial == [(id(v), v.value, v.fixed, v.lb, v.ub) for v in (model.q, *model.z.values())]
    assert pyo.value(attachment.conditional_log_risk) == pytest.approx(result.conditional_log_risk)
    assert all(v.value is not None and math.isfinite(v.value) for v in model.component_data_objects(pyo.Var))
    for row in model.component_data_objects(pyo.Constraint, active=True):
        value = pyo.value(row.body)
        assert row.lower is None or value >= pyo.value(row.lower) - 1e-6
        assert row.upper is None or value <= pyo.value(row.upper) + 1e-6
    assert not any('piecewise_leaf_' in c.name for c in model.component_objects())
    assert attachment.decision_links['x'].ordered_integer_indicators[0][1] is model.z[40]
    assert not tuple(model.component_objects(pyo.Objective))
    with pytest.raises(ValueError, match='caller'):
        initialize_conditional_mio_attachment(pair, attachment, declared_domain_assignments={'x': 99})


@pytest.mark.parametrize('kind', ['foreign', 'duplicate', 'wrong_order', 'continuous', 'missing', 'affine'])
def test_invalid_selector_mapping_rejected_before_caller_mutation(kind):
    import pyomo.environ as pyo
    pair = lookup_pair()
    model = pyo.ConcreteModel()
    model.q = pyo.Var(domain=pyo.Integers, bounds=(40, 160))
    model.z = pyo.Var(range(40, 161), domain=pyo.Binary)
    other = pyo.ConcreteModel()
    other.z = pyo.Var(domain=pyo.Binary)
    entries = [(k, model.z[k]) for k in model.z]
    expression = model.q
    if kind == 'foreign': entries[0] = (40, other.z)
    if kind == 'duplicate': entries[0] = (40, model.z[41])
    if kind == 'wrong_order': entries.reverse()
    if kind == 'missing': entries.pop()
    if kind == 'continuous': model.q.domain = pyo.Reals
    if kind == 'affine': expression = model.q / 120
    with pytest.raises((ValueError, TypeError)):
        mapping = TPMIntegerDecisionMapping('x', expression, tuple(entries))
        attach_conditional_mio_pair(pair, model, mappings=(mapping,), namespace='risk')
    assert not hasattr(model, 'risk')


@pytest.mark.parametrize('grid', [[40, 42, 160], [40, 40, 160], [40., 41., 42.], [False, 1], []])
def test_illegal_grids_rejected(grid):
    with pytest.raises((ValueError, TypeError), match='integer'):
        replace(_encoding(), leaf_configuration={**_encoding().leaf_configuration, 'integer_grids': {'x': grid}})


def test_grid_must_cover_domain_and_actual_leaf_points():
    pair = lookup_pair()
    for grid in (list(range(41, 161)), list(range(40, 162))):
        encoding = replace(pair.encoding, leaf_configuration={**pair.encoding.leaf_configuration, 'integer_grids': {'x': grid}})
        with pytest.raises(ValueError, match='integer'):
            replace(pair, encoding=encoding, attachment_formulation=None, pair_id='')


def compile_gaussian_lookup(monkeypatch, bounds=(40, 160)):
    """Real compiler/math; inject a constructed supported model, never load pickle."""
    import torch
    from spflow.modules.leaves import Bernoulli, Categorical, Normal
    from spflow.modules.products import Product
    from spflow.modules.sums import Sum
    import tpm.conditional_mio as cm
    from tpm.artifact import load_tpm_artifact
    from tests.unit.tpm.test_conditional_mio import TPM_FIXTURE_DIRECTORY, _compilation_request
    from tpm.piecewise import PiecewiseBreakpointPolicy, resolve_guarded_exponential_spec

    def tensor(value):
        return torch.tensor([[[value]]], dtype=torch.float64)
    def component(mean, probability):
        return Product([
            Normal(0, loc=tensor(mean), scale=tensor(.02)),
            Bernoulli(1, probs=tensor(.5)),
            Categorical(2, K=3, probs=torch.tensor([[[[.2, .3, .5]]]], dtype=torch.float64)),
            Normal(3, loc=tensor(.4), scale=tensor(.3)),
            Bernoulli(4, probs=tensor(probability)),
        ])
    model = Sum([component(.4, .2), component(.6, .8)], weights=torch.tensor([.4, .6], dtype=torch.float64))
    artifact = load_tpm_artifact(TPM_FIXTURE_DIRECTORY / 'tpm_artifact_domains_v3.json')
    monkeypatch.setattr(cm, 'load_tpm_artifact', lambda _path: artifact)
    monkeypatch.setattr(cm, 'load_spflow_payload', lambda _artifact: dict(
        payload_kind='current-spflow-model-sidecar', backend_generation='current-spflow',
        backend_api_version='1.1.0', query_strategy='spflow', model=model))
    policy = replace(_encoding('piecewise'), leaf_configuration={
        **_encoding().leaf_configuration, 'breakpoint_count': 3,
        'integer_grids': {'x': list(range(bounds[0], bounds[1] + 1))}})
    sums = PiecewiseBreakpointPolicy(policy_name='legacy-logspace-v1', piecewise_breakpoint_count=17,
                                    exp_probability_floor=.001, exp_breakpoint_start=.3)
    guard = resolve_guarded_exponential_spec(base_x_points=sums.exp_breakpoints(),
                                           base_y_points=sums.exp_values(), domain_floor=-500)
    policy = replace(policy, sum_configuration={**guard, 'sum_big_m': 1e100,
        'log_x_points': sums.log_breakpoints(max_terms=2), 'log_y_points': sums.log_values(max_terms=2),
        'declared_resolution': 17})
    request = _compilation_request(retained_decisions=('x',), encoding=policy,
        approximation_domains=({'feature_name': 'x', 'lower': bounds[0], 'upper': bounds[1],
                                'source': 'integer-unit', 'encoding': 'piecewise-log-density'},))
    return cm.compile_conditional_mio_pair(request), model


@pytest.mark.parametrize('bounds', [(40, 160), (40, 140), (40, 41)])
def test_real_gaussian_compilation_preserves_all_legal_density_values(monkeypatch, bounds):
    pair, _ = compile_gaussian_lookup(monkeypatch, bounds)
    leaves = [n for n in pair.denominator.nodes if n.node_type == 'leaf_piecewise']
    assert len(leaves) == 2
    for leaf, mean in zip(leaves, (.4, .6), strict=True):
        assert tuple(leaf.parameters['breakpoints']) == tuple((k - 40) / 120 for k in range(bounds[0], bounds[1] + 1))
        expected = [max(-.5 * (((k - 40) / 120 - mean) / .02) ** 2
                        - math.log(.02 * math.sqrt(2 * math.pi)), math.log(1e-6)) for k in range(bounds[0], bounds[1] + 1)]
        assert tuple(leaf.parameters['log_values']) == pytest.approx(expected, abs=1e-10)
