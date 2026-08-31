from datetime import datetime, timedelta, timezone

from app.executor import MerchantRecoveryStore, RecoveryExecutor
from app.guardrails import sanitize_diagnosis
from app.investigator import CandidateAction, Diagnosis, DeterministicInvestigator
from app.metrics import Metrics
from app.models import Event, TransactionState
from app.policy import RecoveryPolicy
from app.simulator import orphaned_payment_inventory_available
from app.projector import StateProjector
from app.detector import IncidentDetector
from app.tools import InvestigationTools
from app.evidence import build_evidence


def test_tampered_or_unknown_action_is_removed():
    state = StateProjector().project("tx", orphaned_payment_inventory_available())
    diagnosis = Diagnosis(
        incident_type="ORPHANED_PAYMENT",
        root_cause="x",
        confidence=0.99,
        candidate_actions=[
            CandidateAction("DELETE_DATABASE", "malicious", 999999, 0, 0.99),
            CandidateAction("RECONSTRUCT_ORDER", "safe", 9999, 50, 0.99),
        ],
    )
    clean, warnings = sanitize_diagnosis(diagnosis, state)
    assert "DELETE_DATABASE" not in [a.action_type for a in clean.candidate_actions]
    assert any("unknown_action" in w for w in warnings)
    assert all(a.expected_recovery <= 7499 for a in clean.candidate_actions)


def test_refund_is_never_autonomous():
    state = TransactionState("tx")
    state.payment.status = "CAPTURED"
    state.payment.amount = 5000
    state.order.status = "PAID"
    diagnosis = Diagnosis("DUPLICATE_PAYMENT", "duplicate", 0.99, [], [])
    action = CandidateAction("REFUND_DUPLICATE", "verified duplicate", 5000, 25, 0.99)
    decision = RecoveryPolicy().evaluate(diagnosis, action, state)
    assert decision.decision == "REQUIRE_HUMAN"


def test_high_value_requires_human():
    state = TransactionState("tx")
    state.payment.status = "CAPTURED"
    state.payment.amount = 50001
    state.order.status = "CREATED"
    state.inventory.status = "AVAILABLE"
    diagnosis = Diagnosis("ORPHANED_PAYMENT", "failure", 0.99, [], [])
    action = CandidateAction("RECONSTRUCT_ORDER", "recover", 50001, 50, 0.99)
    decision = RecoveryPolicy().evaluate(diagnosis, action, state)
    assert decision.decision == "REQUIRE_HUMAN"


def test_executor_denies_by_default():
    store = MerchantRecoveryStore()
    executor = RecoveryExecutor(store)
    state = TransactionState("tx")
    state.payment.status = "CAPTURED"
    state.payment.amount = 4999
    state.order.status = "CREATED"
    state.inventory.status = "AVAILABLE"

    result = executor.execute("RECONSTRUCT_ORDER", state)

    assert result.status == "REJECTED"
    assert result.revenue_preserved == 0
    assert state.order.status == "CREATED"
    assert state.transaction_id not in store.order_confirmed


def test_verifier_detects_failed_mutation():
    store = MerchantRecoveryStore()
    executor = RecoveryExecutor(store)
    state = TransactionState("tx")
    state.payment.status = "CAPTURED"
    state.payment.amount = 4999
    state.order.status = "CREATED"
    state.inventory.status = "AVAILABLE"
    result = executor.execute("RECONSTRUCT_ORDER", state, approved=True)
    # Corrupt state after execution to model partial downstream failure.
    state.order.status = "CREATED"
    from app.verifier import verify
    verification = verify("RECONSTRUCT_ORDER", state, result)
    assert verification.status == "FAILED"


def test_deterministic_investigation_stays_read_only():
    events = orphaned_payment_inventory_available()
    tx = events[0].transaction_id
    state = StateProjector().project(tx, events)
    incidents = IncidentDetector().detect(state, events)
    bundle = build_evidence(state, events)
    tools = InvestigationTools(state, events, bundle)
    before = (state.payment.status, state.order.status, state.inventory.status, state.fulfillment.status)
    DeterministicInvestigator().investigate(incidents[0], tools)
    after = (state.payment.status, state.order.status, state.inventory.status, state.fulfillment.status)
    assert before == after


def test_metrics_snapshot_is_serializable():
    m = Metrics()
    m.events_ingested = 3
    m.increment_incident("ORPHANED_PAYMENT")
    snapshot = m.snapshot()
    assert snapshot["events_ingested"] == 3
    assert snapshot["incidents_by_type"]["ORPHANED_PAYMENT"] == 1
