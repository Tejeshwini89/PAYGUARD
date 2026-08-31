from app.detector import IncidentDetector
from app.evidence import build_evidence
from app.llm_agent import OpenAIInvestigator, DiagnosisOutput
from app.projector import StateProjector
from app.simulator import orphaned_payment_inventory_available, fulfillment_failure
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
