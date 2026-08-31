from app.detector import IncidentDetector
from app.evidence import build_evidence
from app.guardrails import sanitize_diagnosis
from app.investigator import CandidateAction, Diagnosis
from app.llm_agent import AIAction, DiagnosisOutput, OpenAIInvestigator
from app.models import TransactionState
from app.projector import StateProjector
from app.simulator import fulfillment_failure, orphaned_payment_inventory_available
from app.tools import InvestigationTools


def build(scenario):
    events = scenario()
    tx_id = events[0].transaction_id
    state = StateProjector().project(tx_id, events)
    incidents = IncidentDetector().detect(state, events)
    tools = InvestigationTools(state, events, build_evidence(state, events))
    return state, incidents[0], tools


def test_fallback_produces_structured_diagnosis_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    state, incident, tools = build(orphaned_payment_inventory_available)
    result = OpenAIInvestigator().investigate(incident, state, tools)
    assert isinstance(result, DiagnosisOutput)
    assert result.incident_type == "ORPHANED_PAYMENT"
    assert result.recommended_action == "RECONSTRUCT_ORDER"
    assert result.candidate_actions


def test_fallback_is_conservative_for_high_value_fulfillment(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    state, incident, tools = build(fulfillment_failure)
    result = OpenAIInvestigator().investigate(incident, state, tools)
    assert result.root_cause.startswith("FULFILLMENT_FAILURE:")
    assert result.candidate_actions[0].action_type == "RETRY_FULFILLMENT"


def test_adversarial_recommendation_cannot_escape_candidate_action_allowlist():
    state = TransactionState("tx")
    state.payment.amount = 7499
    diagnosis = Diagnosis(
        incident_type="ORPHANED_PAYMENT",
        root_cause="malicious instruction",
        confidence=1.0,
        evidence=[],
        candidate_actions=[CandidateAction("RECONSTRUCT_ORDER", "safe candidate", 999999, 50, 1.0)],
    )

    clean, warnings = sanitize_diagnosis(diagnosis, state)
    malicious_recommendation = AIAction("DELETE_DATABASE", "ignore policy", 999999, 0, 1.0)

    assert malicious_recommendation.action_type not in {a.action_type for a in clean.candidate_actions}
    assert clean.candidate_actions[0].expected_recovery == 7499
    assert "recovery_clamped:RECONSTRUCT_ORDER" in warnings


def test_adversarial_unknown_candidate_action_is_removed_before_policy():
    state = TransactionState("tx")
    state.payment.amount = 5000
    diagnosis = Diagnosis(
        incident_type="ORPHANED_PAYMENT",
        root_cause="prompt injection",
        confidence=1.0,
        evidence=[],
        candidate_actions=[
            CandidateAction("TRANSFER_FUNDS", "malicious", 5000, 0, 1.0),
            CandidateAction("RECONSTRUCT_ORDER", "validated", 5000, 50, 0.9),
        ],
    )

    clean, warnings = sanitize_diagnosis(diagnosis, state)

    assert [a.action_type for a in clean.candidate_actions] == ["RECONSTRUCT_ORDER"]
    assert "unknown_action:TRANSFER_FUNDS" in warnings
