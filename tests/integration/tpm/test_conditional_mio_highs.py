"""Consumer-owned Pyomo composition around an attached conditional pair."""

from __future__ import annotations

import math

import pytest

from open_energy_lab.tpm.conditional import TPMContinuousDecisionMapping
from open_energy_lab.tpm.conditional_mio import (
    attach_conditional_mio_pair,
    evaluate_conditional_mio_pair,
)
from tests.unit.tpm.test_conditional_pair import _pair


def test_consumer_owns_objective_deterministic_policy_and_chance_threshold() -> None:
    import pyomo.environ as pyo

    pair = _pair()
    model = pyo.ConcreteModel()
    model.quantity = pyo.Var(domain=pyo.NonNegativeReals, bounds=(40.0, 160.0))
    model.reserve = pyo.Var(domain=pyo.NonNegativeReals, initialize=0.0)
    model.reserve.fix(0.0)
    attachment = attach_conditional_mio_pair(
        pair,
        model,
        mappings=(
            TPMContinuousDecisionMapping(
                "x", model.quantity + model.reserve
            ),
        ),
        namespace="oel_conditional_risk",
    )

    model.alpha = pyo.Param(initialize=0.2)
    model.storage_limit = pyo.Constraint(expr=model.quantity <= 150.0)
    model.risk_limit = pyo.Constraint(
        expr=attachment.conditional_log_risk <= math.log(pyo.value(model.alpha))
    )
    model.cost = pyo.Objective(expr=3.0 * model.quantity + model.reserve)

    direct = evaluate_conditional_mio_pair(
        pair, declared_domain_assignments={"x": 100.0}
    )
    model.quantity.set_value(100.0)
    link = attachment.decision_links["x"]
    link.model_coordinate.set_value(0.5)
    attachment.numerator_root.set_value(direct.numerator_log)
    attachment.denominator_root.set_value(direct.denominator_log)

    assert math.isfinite(pyo.value(model.cost.expr))
    assert pyo.value(attachment.conditional_log_risk) == pytest.approx(
        direct.conditional_log_risk
    )
    assert math.isfinite(pyo.value(model.risk_limit.body))
    assert not model.quantity.fixed
    assert model.quantity.domain is pyo.NonNegativeReals
    assert model.storage_limit.parent_block() is model
    assert model.risk_limit.parent_block() is model
    assert model.cost.parent_block() is model
    assert not tuple(
        attachment.block.component_objects(pyo.Objective, descend_into=True)
    )
    assert not hasattr(attachment.block, "alpha")
    assert not hasattr(attachment.block, "risk_limit")
    assert not hasattr(attachment.block, "storage_limit")
