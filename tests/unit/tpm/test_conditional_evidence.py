"""Contracts for post-solve diagnostics and separate conditional evidence."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import math

import pytest

from open_energy_lab.tpm.conditional import (
    TPMBinaryDecisionLink,
    TPMCompilerFidelityEvidence,
    TPMConditionalAttachment,
    TPMConditionalAttachmentDiagnostics,
    TPMEmbeddingParityEvidence,
    TPMNativeConditionalEvaluation,
    load_conditional_evidence,
    publish_conditional_evidence,
)
from open_energy_lab.tpm.conditional_mio import (
    TPMConditionalDiagnosticsError,
    build_compiler_fidelity_evidence,
    build_embedding_parity_evidence,
    evaluate_conditional_mio_pair,
    inspect_conditional_mio_attachment,
)
from tests.unit.tpm.test_conditional_pair import _pair


def _attachment(*, numerator: float = -2.0, denominator: float = -1.0):
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.primary = pyo.Var(domain=pyo.Binary, initialize=0)
    model.risk = pyo.Block(concrete=True)
    model.risk.numerator = pyo.Var(initialize=numerator)
    model.risk.denominator = pyo.Var(initialize=denominator)
    model.risk.auxiliary = pyo.Var(initialize=-1.0)
    model.risk.root_equality = pyo.Constraint(
        expr=model.risk.numerator == numerator
    )
    model.risk.lower = pyo.Constraint(expr=model.risk.auxiliary >= -2.0)
    model.risk.upper = pyo.Constraint(expr=model.risk.auxiliary <= -0.5)
    model.risk.ranged = pyo.Constraint(
        expr=pyo.inequality(-2.0, model.risk.auxiliary, -0.5)
    )
    model.risk.inactive = pyo.Constraint(expr=model.risk.auxiliary == 100.0)
    model.risk.inactive.deactivate()
    model.risk.conditional_log_risk = pyo.Expression(
        expr=model.risk.numerator - model.risk.denominator
    )
    attachment = TPMConditionalAttachment(
        pair_id="a" * 64,
        namespace="risk",
        retained_decisions=("activation",),
        block=model.risk,
        numerator_root=model.risk.numerator,
        denominator_root=model.risk.denominator,
        conditional_log_risk=model.risk.conditional_log_risk,
        decision_links={
            "activation": TPMBinaryDecisionLink(
                feature_name="activation",
                caller_variable=model.primary,
                declared_ordering=("off", "on"),
            )
        },
        pair_metadata={
            "numerical_policy": {
                "tolerances": {
                    "embedding_parity_absolute_tolerance": 1e-6,
                    "constraint_residual_absolute_tolerance": 1e-6,
                    "positive_log_risk_limit": 1e-6,
                    "domain_membership_tolerance": 0.0,
                }
            }
        },
        diagnostic_components=("risk.root_equality", "risk.lower", "risk.upper"),
    )
    return model, attachment


def _solver_metadata() -> dict[str, object]:
    return {
        "solver_name": "highs",
        "solver_version": "1.15.1",
        "status": "ok",
        "termination_condition": "optimal",
    }


def _diagnostics(
    *,
    pair_id: str,
    numerator: float,
    denominator: float,
    residual: float = 0.0,
) -> TPMConditionalAttachmentDiagnostics:
    risk = numerator - denominator
    return TPMConditionalAttachmentDiagnostics(
        pair_id=pair_id,
        namespace="risk",
        solver_metadata=_solver_metadata(),
        numerator_log=numerator,
        denominator_log=denominator,
        conditional_log_risk=risk,
        conditional_probability=math.exp(risk),
        classification="valid" if risk <= 0.0 else "positive-numerical-noise",
        constraint_residuals={"risk.root": residual},
        maximum_constraint_residual=residual,
    )


def test_post_solve_inspector_reports_attachment_only_violation_magnitudes() -> None:
    model, attachment = _attachment()

    diagnostics = inspect_conditional_mio_attachment(
        attachment, solver_metadata=_solver_metadata()
    )

    assert diagnostics.numerator_log == -2.0
    assert diagnostics.denominator_log == -1.0
    assert diagnostics.conditional_log_risk == -1.0
    assert diagnostics.conditional_probability == pytest.approx(math.exp(-1.0))
    assert diagnostics.solver_metadata == _solver_metadata()
    assert diagnostics.maximum_constraint_residual == 0.0
    assert all(value == 0.0 for value in diagnostics.constraint_residuals.values())
    assert "risk.inactive" not in diagnostics.constraint_residuals

    model.risk.auxiliary.set_value(-3.0)
    violated = inspect_conditional_mio_attachment(
        attachment, solver_metadata=_solver_metadata()
    )
    assert violated.constraint_residuals["risk.lower"] == pytest.approx(1.0)
    assert violated.constraint_residuals["risk.upper"] == 0.0
    assert violated.constraint_residuals["risk.ranged"] == pytest.approx(1.0)
    assert violated.maximum_constraint_residual == pytest.approx(1.0)


def test_post_solve_inspector_preserves_positive_noise_and_rejects_invalid_values() -> None:
    model, attachment = _attachment(numerator=-1.0 + 5e-7, denominator=-1.0)
    diagnostics = inspect_conditional_mio_attachment(
        attachment, solver_metadata=_solver_metadata()
    )
    assert diagnostics.conditional_log_risk == pytest.approx(5e-7)
    assert diagnostics.classification == "positive-numerical-noise"

    model.risk.numerator.set_value(-1.0 + 2e-6)
    with pytest.raises(TPMConditionalDiagnosticsError, match="positive numerical") as error:
        inspect_conditional_mio_attachment(
            attachment, solver_metadata=_solver_metadata()
        )
    assert error.value.diagnostics.conditional_log_risk == pytest.approx(2e-6)

    model.risk.numerator.set_value(math.nan)
    with pytest.raises(ValueError, match="finite|evaluate"):
        inspect_conditional_mio_attachment(
            attachment, solver_metadata=_solver_metadata()
        )


def test_embedding_parity_builder_gates_only_identical_compiled_semantics() -> None:
    pair = _pair()
    direct = evaluate_conditional_mio_pair(
        pair, declared_domain_assignments={"x": 100.0}
    )
    accepted_diagnostics = _diagnostics(
        pair_id=pair.pair_id,
        numerator=direct.numerator_log + 1e-6,
        denominator=direct.denominator_log - 1e-6,
    )
    rejected_diagnostics = _diagnostics(
        pair_id=pair.pair_id,
        numerator=direct.numerator_log + 1.1e-6,
        denominator=direct.denominator_log,
    )

    accepted = build_embedding_parity_evidence(
        pair,
        case_results={"midpoint": (direct, accepted_diagnostics)},
        provenance={"purpose": "unit parity"},
    )
    rejected = build_embedding_parity_evidence(
        pair,
        case_results={"midpoint": (direct, rejected_diagnostics)},
        provenance={"purpose": "unit parity"},
    )

    assert isinstance(accepted, TPMEmbeddingParityEvidence)
    assert accepted.cases[0]["accepted"] is False
    # The root deltas are individually at tolerance, but their difference is 2e-6.
    assert accepted.cases[0]["absolute_errors"]["numerator_log"] == pytest.approx(
        1e-6
    )
    assert accepted.cases[0]["absolute_errors"]["conditional_log_risk"] == pytest.approx(
        2e-6
    )
    assert rejected.cases[0]["accepted"] is False
    assert rejected.accepted is False

    exact = build_embedding_parity_evidence(
        pair,
        case_results={
            "midpoint": (
                direct,
                _diagnostics(
                    pair_id=pair.pair_id,
                    numerator=direct.numerator_log,
                    denominator=direct.denominator_log,
                ),
            )
        },
        provenance={"purpose": "unit parity"},
    )
    assert exact.accepted is True
    assert exact.cases[0]["accepted"] is True
    assert exact.metric_definitions["acceptance_gate"] == "absolute-1e-6"


def test_compiler_fidelity_builder_retains_four_signed_differences_without_gate() -> None:
    pair = _pair()
    compiled = evaluate_conditional_mio_pair(
        pair, declared_domain_assignments={"x": 100.0}
    )
    native = TPMNativeConditionalEvaluation(
        pair_id=pair.pair_id,
        artifact_id=pair.source.artifact_id,
        assignments={"x": 100.0},
        numerator_log=compiled.numerator_log - 2.0,
        denominator_log=compiled.denominator_log + 3.0,
        conditional_log_risk=compiled.conditional_log_risk - 5.0,
        conditional_probability=math.exp(compiled.conditional_log_risk - 5.0),
        backend_generation="current-spflow",
        backend_api_version="1.1.0",
    )

    evidence = build_compiler_fidelity_evidence(
        pair,
        case_results={"midpoint": (compiled, native)},
        provenance={"purpose": "unit fidelity"},
    )

    assert isinstance(evidence, TPMCompilerFidelityEvidence)
    differences = evidence.cases[0]["differences"]
    assert differences["numerator_log"] == pytest.approx(2.0)
    assert differences["denominator_log"] == pytest.approx(-3.0)
    assert differences["conditional_log_risk"] == pytest.approx(5.0)
    assert differences["conditional_probability"] == pytest.approx(
        compiled.conditional_probability - native.conditional_probability
    )
    serialized = evidence.to_dict()
    assert "accepted" not in serialized
    assert "adequacy" not in str(serialized).casefold()
    assert "threshold" not in str(serialized).casefold()


def test_evidence_records_are_immutable_identified_and_create_or_verify(tmp_path) -> None:
    pair = _pair()
    direct = evaluate_conditional_mio_pair(
        pair, declared_domain_assignments={"x": 100.0}
    )
    parity = build_embedding_parity_evidence(
        pair,
        case_results={
            "midpoint": (
                direct,
                _diagnostics(
                    pair_id=pair.pair_id,
                    numerator=direct.numerator_log,
                    denominator=direct.denominator_log,
                ),
            )
        },
        provenance={"purpose": "round trip"},
    )
    output = tmp_path / "parity.json"

    first = publish_conditional_evidence(parity, output)
    original = output.read_bytes()
    second = publish_conditional_evidence(parity, output)
    loaded = load_conditional_evidence(output)

    assert first.created and not first.reused
    assert second.reused and not second.created
    assert loaded == parity
    assert output.read_bytes() == original
    assert len(parity.evidence_id) == 64
    with pytest.raises(FrozenInstanceError):
        parity.evidence_id = "changed"
    with pytest.raises(TypeError):
        parity.cases[0]["assignments"]["x"] = 0.0
    with pytest.raises(TypeError):
        parity.cases[0]["direct"]["assignments"]["x"] = 40.0
    with pytest.raises(TypeError):
        parity.metric_definitions["acceptance_gate"] = "changed"
    with pytest.raises(TypeError):
        parity.provenance["purpose"] = "changed"

    changed = build_embedding_parity_evidence(
        pair,
        case_results={
            "changed-name": (
                direct,
                _diagnostics(
                    pair_id=pair.pair_id,
                    numerator=direct.numerator_log,
                    denominator=direct.denominator_log,
                ),
            )
        },
        provenance={"purpose": "round trip"},
    )
    assert changed.evidence_id != parity.evidence_id
    with pytest.raises(FileExistsError, match="conflicts"):
        publish_conditional_evidence(changed, output)
    assert output.read_bytes() == original


def test_evidence_construction_rejects_pair_assignment_and_solver_mismatch() -> None:
    pair = _pair()
    direct = evaluate_conditional_mio_pair(
        pair, declared_domain_assignments={"x": 100.0}
    )
    wrong_pair = _diagnostics(
        pair_id="d" * 64,
        numerator=direct.numerator_log,
        denominator=direct.denominator_log,
    )
    with pytest.raises(ValueError, match="pair"):
        build_embedding_parity_evidence(
            pair, case_results={"wrong": (direct, wrong_pair)}
        )

    invalid_solver = _diagnostics(
        pair_id=pair.pair_id,
        numerator=direct.numerator_log,
        denominator=direct.denominator_log,
    ).to_dict()
    invalid_solver["solver_metadata"]["status"] = "error"
    diagnostics = TPMConditionalAttachmentDiagnostics.from_dict(invalid_solver)
    evidence = build_embedding_parity_evidence(
        pair, case_results={"solver-error": (direct, diagnostics)}
    )
    assert evidence.accepted is False
    assert evidence.cases[0]["accepted"] is False
