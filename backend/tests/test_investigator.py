from app.detector import IncidentDetector
from app.evidence import build_evidence
from app.investigator import DeterministicInvestigator
from app.policy import RecoveryPolicy
from app.projector import StateProjector
from app.simulator import fulfillment_failure, orphaned_payment, orphaned_payment_inventory_available
from app.tools import InvestigationTools
from app.models import Event
from datetime import datetime, timedelta, timezone


def run(events):
    state = StateProjector().project(events[0].transaction_id, events)
    incidents = IncidentDetector().detect(state, events)
    bundle = build_evidence(state, events)
    tools = InvestigationTools(state, events, bundle)
    return state, incidents, DeterministicInvestigator().investigate(incidents[0], tools), tools


def test_orphaned_payment_investigation_selects_reconstruction():
    state, incidents, diagnosis, tools = run(orphaned_payment_inventory_available())
    assert diagnosis.root_cause == "MERCHANT_ORDER_CONFIRMATION_FAILURE"
    assert diagnosis.candidate_actions[0].action_type == "RECONSTRUCT_ORDER"
    decision = RecoveryPolicy().evaluate(diagnosis, diagnosis.candidate_actions[0], state)
    assert decision.decision == "ALLOW_AUTONOMOUS"


def test_fulfillment_failure_investigation_selects_retry():
    state, incidents, diagnosis, tools = run(fulfillment_failure())
    assert diagnosis.root_cause.startswith("FULFILLMENT_FAILURE:")
    assert diagnosis.candidate_actions[0].action_type == "RETRY_FULFILLMENT"
    decision = RecoveryPolicy().evaluate(diagnosis, diagnosis.candidate_actions[0], state)
    assert decision.decision == "REQUIRE_HUMAN"


def test_evidence_contains_projected_state_and_event_history():
    state, incidents, diagnosis, tools = run(orphaned_payment())
    evidence = tools.list_evidence()
    assert any(x["fact"] == "payment.status" for x in evidence)
    assert any(x["event_id"] == "o2" for x in evidence)


def test_high_value_recovery_requires_human():
    events = orphaned_payment()
    events = [
        Event(
            event_id=e.event_id,
            transaction_id=e.transaction_id,
            event_type=e.event_type,
            source=e.source,
            entity_id=e.entity_id,
            occurred_at=e.occurred_at,
            received_at=e.received_at,
            payload={**e.payload, **({"amount": 25000} if e.event_type == "payment.captured" else {"amount": 25000} if e.event_type == "order.created" else {})},
            signature_verified=e.signature_verified,
        )
        for e in events
    ]
    state, incidents, diagnosis, _ = run(events)
    decision = RecoveryPolicy().evaluate(diagnosis, diagnosis.candidate_actions[0], state)
    assert decision.decision == "REQUIRE_HUMAN"


def test_fulfillment_over_limit_requires_human():
    state, incidents, diagnosis, _ = run(fulfillment_failure())
    decision = RecoveryPolicy().evaluate(diagnosis, diagnosis.candidate_actions[0], state)
    assert decision.decision == "REQUIRE_HUMAN"
