from app.executor import ExecutionResult, RecoveryExecutor
from app.investigator import CandidateAction, Diagnosis
from app.ledger import DecisionLedger
from app.models import Incident, TransactionState
from app.policy import RecoveryPolicy
from app.recovery import perform_recovery


class LyingExecutor(RecoveryExecutor):
    """Simulate a downstream adapter claiming success without mutating state."""

    def execute(self, action_type, state, *, approved=False):
        return ExecutionResult(
            action_type=action_type,
            status="EXECUTED",
            message="Adapter reported success but state was not changed.",
            revenue_preserved=state.payment.amount,
            action_cost=50,
            idempotency_key=f"{action_type}:{state.transaction_id}",
        )


def test_recovery_does_not_credit_revenue_when_execution_lies():
    state = TransactionState("txn_verification_failure")
    state.payment.status = "CAPTURED"
    state.payment.amount = 7499
    state.order.status = "CREATED"
    state.inventory.status = "AVAILABLE"

    incident = Incident(
        incident_type="ORPHANED_PAYMENT",
        transaction_id=state.transaction_id,
        severity="HIGH",
        expected_state={"payment": "CAPTURED", "order": "PAID"},
        observed_state={"payment": "CAPTURED", "order": "CREATED"},
        revenue_at_risk=7499,
        reason="Payment is captured but order confirmation is incomplete.",
        confidence=0.96,
    )
    diagnosis = Diagnosis(
        incident_type="ORPHANED_PAYMENT",
        root_cause="MERCHANT_ORDER_CONFIRMATION_FAILURE",
        confidence=0.97,
        evidence=[],
        candidate_actions=[],
    )
    action = CandidateAction(
        "RECONSTRUCT_ORDER", "Payment is captured and inventory is available.", 7499, 50, 0.97
    )

    outcome = perform_recovery(
        incident,
        diagnosis,
        action,
        state,
        RecoveryPolicy(),
        LyingExecutor(),
        DecisionLedger(),
        "verification-failure:txn_verification_failure:RECONSTRUCT_ORDER",
    )

    assert outcome.policy.decision == "ALLOW_AUTONOMOUS"
    assert outcome.execution["status"] == "EXECUTED"
    assert outcome.verification.status == "FAILED"
    assert outcome.verification.revenue_recovered == 0
    assert outcome.ledger["verification_status"] == "FAILED"
    assert outcome.ledger["revenue_recovered"] == 0
    assert state.order.status == "CREATED"
