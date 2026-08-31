from datetime import datetime, timezone

from app.executor import MerchantRecoveryStore, RecoveryExecutor
from app.investigator import CandidateAction, Diagnosis
from app.ledger import DecisionLedger
from app.models import Event, Incident, TransactionState
from app.policy import RecoveryPolicy
from app.projector import StateProjector
from app.recovery import perform_recovery


def _context(amount=7499):
    state = TransactionState("txn_safety_boundary")
    state.payment.status = "CAPTURED"
    state.payment.amount = amount
    state.order.status = "CREATED"
    state.inventory.status = "UNKNOWN"
    state.fulfillment.status = "NOT_STARTED"
    incident = Incident(
        incident_type="ORPHANED_PAYMENT",
        transaction_id=state.transaction_id,
        severity="HIGH",
        expected_state={"payment": "CAPTURED", "order": "PAID"},
        observed_state={"payment": "CAPTURED", "order": "CREATED"},
        revenue_at_risk=amount,
        reason="Payment captured but order confirmation is incomplete.",
        confidence=0.96,
    )
    diagnosis = Diagnosis("ORPHANED_PAYMENT", "MERCHANT_ORDER_CONFIRMATION_FAILURE", 0.97)
    action = CandidateAction("RECONSTRUCT_ORDER", "attempt recovery", amount, 50, 0.97)
    return state, incident, diagnosis, action


def test_deny_policy_cannot_execute_recovery():
    state, incident, diagnosis, action = _context()
    ledger = DecisionLedger()
    outcome = perform_recovery(
        incident, diagnosis, action, state, RecoveryPolicy(),
        RecoveryExecutor(MerchantRecoveryStore()), ledger,
        "deny:txn_safety_boundary:RECONSTRUCT_ORDER",
    )
    assert outcome.policy.decision == "DENY"
    assert outcome.execution["status"] == "REJECTED"
    assert outcome.verification.status == "FAILED"
    assert outcome.verification.revenue_recovered == 0
    assert state.order.status == "CREATED"
    assert outcome.ledger["execution_status"] == "REJECTED"
    assert outcome.ledger["revenue_recovered"] == 0


def test_failed_verification_never_credits_revenue():
    class LyingExecutor(RecoveryExecutor):
        def execute(self, action_type, state, *, approved=False):
            result = super().execute(action_type, state, approved=approved)
            state.order.status = "CREATED"
            return result

    state, incident, diagnosis, action = _context()
    state.inventory.status = "AVAILABLE"
    outcome = perform_recovery(
        incident, diagnosis, action, state, RecoveryPolicy(),
        LyingExecutor(MerchantRecoveryStore()), DecisionLedger(),
        "verify:txn_safety_boundary:RECONSTRUCT_ORDER",
    )
    assert outcome.execution["status"] == "EXECUTED"
    assert outcome.verification.status == "FAILED"
    assert outcome.verification.revenue_recovered == 0
    assert outcome.ledger["verification_status"] == "FAILED"
    assert outcome.ledger["revenue_recovered"] == 0


def test_unknown_inventory_is_hard_stop_even_with_high_confidence():
    state, _, diagnosis, action = _context()
    decision = RecoveryPolicy().evaluate(diagnosis, action, state)
    assert decision.decision == "DENY"
    assert "Inventory" in decision.reason


def test_high_risk_fraud_signal_blocks_autonomous_recovery():
    now = datetime.now(timezone.utc)
    events = [
        Event("e1", "txn_risky", "order.created", "sim", "ord", now, now, {"order_id": "ord", "amount": 7499}),
        Event("e2", "txn_risky", "payment.captured", "sim", "pay", now, now, {"payment_id": "pay", "amount": 7499, "method": "card"}),
        Event("e3", "txn_risky", "inventory.released", "sim", "prod", now, now, {"fraud_signal": "HIGH", "available_quantity": 0, "reserved_quantity": 0}),
    ]
    state = StateProjector().project("txn_risky", events)
    diagnosis = Diagnosis("ORPHANED_PAYMENT", "MERCHANT_ORDER_CONFIRMATION_FAILURE", 0.99)
    action = CandidateAction("RECONSTRUCT_ORDER", "high confidence candidate", 7499, 0, 0.99)

    assert state.inventory.status == "AVAILABLE"
    assert "HIGH" in state.risk_flags
    decision = RecoveryPolicy().evaluate(diagnosis, action, state)
    assert decision.decision == "DENY"
    assert "Risk signal" in decision.reason
