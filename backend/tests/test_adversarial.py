from app.executor import MerchantRecoveryStore, RecoveryExecutor
from app.investigator import CandidateAction, Diagnosis
from app.models import TransactionState
from app.policy import RecoveryPolicy
from app.verifier import verify


def _state(amount=7499):
    state = TransactionState("txn_adversarial")
    state.payment.status = "CAPTURED"
    state.payment.amount = amount
    state.order.status = "CREATED"
    state.inventory.status = "AVAILABLE"
    state.fulfillment.status = "NOT_STARTED"
    return state


def test_unknown_action_is_denied_by_policy():
    state = _state()
    diagnosis = Diagnosis("ORPHANED_PAYMENT", "failure", 0.99)
    action = CandidateAction("TRANSFER_FUNDS", "tampered", 7499, 0, 0.99)
    decision = RecoveryPolicy().evaluate(diagnosis, action, state)
    assert decision.decision == "DENY"


def test_low_diagnosis_confidence_requires_human():
    state = _state()
    diagnosis = Diagnosis("ORPHANED_PAYMENT", "uncertain", 0.89)
    action = CandidateAction("RECONSTRUCT_ORDER", "recover", 7499, 50, 0.99)
    decision = RecoveryPolicy().evaluate(diagnosis, action, state)
    assert decision.decision == "REQUIRE_HUMAN"


def test_low_action_confidence_requires_human():
    state = _state()
    diagnosis = Diagnosis("ORPHANED_PAYMENT", "failure", 0.99)
    action = CandidateAction("RECONSTRUCT_ORDER", "uncertain action", 7499, 50, 0.89)
    decision = RecoveryPolicy().evaluate(diagnosis, action, state)
    assert decision.decision == "REQUIRE_HUMAN"


def test_reconstruct_with_unknown_inventory_is_denied():
    state = _state()
    state.inventory.status = "UNKNOWN"
    diagnosis = Diagnosis("ORPHANED_PAYMENT", "failure", 0.99)
    action = CandidateAction("RECONSTRUCT_ORDER", "recover", 7499, 50, 0.99)
    decision = RecoveryPolicy().evaluate(diagnosis, action, state)
    assert decision.decision == "DENY"


def test_retry_when_fulfillment_is_not_failed_is_denied():
    state = _state()
    diagnosis = Diagnosis("FULFILLMENT_FAILURE", "failure", 0.99)
    action = CandidateAction("RETRY_FULFILLMENT", "retry", 7499, 100, 0.99)
    decision = RecoveryPolicy().evaluate(diagnosis, action, state)
    assert decision.decision == "DENY"


def test_executor_requires_explicit_authorization():
    store = MerchantRecoveryStore()
    executor = RecoveryExecutor(store)
    state = _state()
    result = executor.execute("RECONSTRUCT_ORDER", state)
    assert result.status == "REJECTED"
    assert state.order.status == "CREATED"


def test_recovery_is_idempotent():
    store = MerchantRecoveryStore()
    executor = RecoveryExecutor(store)
    state = _state()
    first = executor.execute("RECONSTRUCT_ORDER", state, approved=True)
    second = executor.execute("RECONSTRUCT_ORDER", state, approved=True)
    assert first.status == "EXECUTED"
    assert second.status == "ALREADY_EXECUTED"
    assert second.revenue_preserved == 7499


def test_verification_rejects_wrong_action_and_preserves_zero_recovery():
    store = MerchantRecoveryStore()
    executor = RecoveryExecutor(store)
    state = _state()
    result = executor.execute("RECONSTRUCT_ORDER", state, approved=True)
    verification = verify("RETRY_FULFILLMENT", state, result)
    assert verification.status == "FAILED"
    assert verification.revenue_recovered == 0


def test_exact_autonomous_limit_is_allowed():
    state = _state(amount=10_000)
    diagnosis = Diagnosis("ORPHANED_PAYMENT", "failure", 0.99)
    action = CandidateAction("RECONSTRUCT_ORDER", "recover", 10_000, 50, 0.99)
    decision = RecoveryPolicy().evaluate(diagnosis, action, state)
    assert decision.decision == "ALLOW_AUTONOMOUS"
