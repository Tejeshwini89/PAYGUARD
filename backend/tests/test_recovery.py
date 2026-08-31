from app.detector import IncidentDetector
from app.evidence import build_evidence
from app.executor import ExecutionResult, MerchantRecoveryStore, RecoveryExecutor
from app.investigator import DeterministicInvestigator
from app.ledger import DecisionLedger
from app.policy import RecoveryPolicy
from app.recovery import perform_recovery
from app.projector import StateProjector
from app.simulator import fulfillment_failure, orphaned_payment_inventory_available


def _context(events):
    projector = StateProjector()
    state = projector.project(events[0].transaction_id, events)
    incidents = IncidentDetector().detect(state, events)
    bundle = build_evidence(state, events)
    from app.tools import InvestigationTools
    tools = InvestigationTools(state, events, bundle)
    diagnosis = DeterministicInvestigator().investigate(incidents[0], tools)
    return state, incidents[0], diagnosis, tools


def test_reconstruct_order_executes_and_verifies():
    state, incident, diagnosis, _ = _context(orphaned_payment_inventory_available())
    action = next(a for a in diagnosis.candidate_actions if a.action_type == "RECONSTRUCT_ORDER")
    outcome = perform_recovery(incident, diagnosis, action, state, RecoveryPolicy(), RecoveryExecutor(), DecisionLedger(), "inc-1")
    assert outcome.policy.decision == "ALLOW_AUTONOMOUS"
    assert outcome.execution["status"] == "EXECUTED"
    assert outcome.verification.status == "VERIFIED"
    assert outcome.verification.revenue_recovered == 7499


def test_recovery_is_idempotent():
    state, incident, diagnosis, _ = _context(orphaned_payment_inventory_available())
    action = next(a for a in diagnosis.candidate_actions if a.action_type == "RECONSTRUCT_ORDER")
    executor = RecoveryExecutor()
    ledger = DecisionLedger()
    first = perform_recovery(incident, diagnosis, action, state, RecoveryPolicy(), executor, ledger, "inc-2")
    second = perform_recovery(incident, diagnosis, action, state, RecoveryPolicy(), executor, ledger, "inc-2")
    assert first.execution["status"] == "EXECUTED"
    assert second.execution["status"] == "ALREADY_EXECUTED"
    assert second.verification.status == "VERIFIED"


def test_fulfillment_retry_is_bounded_and_idempotent():
    state, incident, diagnosis, _ = _context(fulfillment_failure())
    action = next(a for a in diagnosis.candidate_actions if a.action_type == "RETRY_FULFILLMENT")
    executor = RecoveryExecutor()
    ledger = DecisionLedger()

    first = perform_recovery(
        incident, diagnosis, action, state, RecoveryPolicy(), executor, ledger, "inc-retry-1"
    )
    second = perform_recovery(
        incident, diagnosis, action, state, RecoveryPolicy(), executor, ledger, "inc-retry-2"
    )

    assert first.execution["status"] == "EXECUTED"
    assert first.verification.status == "VERIFIED"
    assert second.execution["status"] == "REJECTED"
    assert state.fulfillment.attempt_count == 1


def test_high_value_retry_requires_human():
    state, incident, diagnosis, _ = _context(fulfillment_failure())
    action = next(a for a in diagnosis.candidate_actions if a.action_type == "RETRY_FULFILLMENT")
    policy = RecoveryPolicy(autonomous_limit=10_000)
    executor = RecoveryExecutor()
    ledger = DecisionLedger()
    denied = perform_recovery(incident, diagnosis, action, state, policy, executor, ledger, "inc-3", human_approved=False)
    assert denied.policy.decision == "REQUIRE_HUMAN"
    assert denied.execution["status"] == "REJECTED"
    approved = perform_recovery(incident, diagnosis, action, state, policy, executor, ledger, "inc-3a", human_approved=True)
    assert approved.execution["status"] == "EXECUTED"
    assert approved.verification.status == "VERIFIED"


def test_recovery_records_ledger():
    state, incident, diagnosis, _ = _context(orphaned_payment_inventory_available())
    action = next(a for a in diagnosis.candidate_actions if a.action_type == "RECONSTRUCT_ORDER")
    ledger = DecisionLedger()
    perform_recovery(incident, diagnosis, action, state, RecoveryPolicy(), RecoveryExecutor(), ledger, "inc-4")
    assert len(ledger.entries) == 1
    assert ledger.entries[0].revenue_recovered == 7499


def test_failed_verification_never_credits_recovered_revenue():
    class LyingExecutor:
        def execute(self, action_type, state, *, approved=False):
            return ExecutionResult(
                action_type=action_type,
                status="EXECUTED",
                message="Claimed success without changing downstream state.",
                revenue_preserved=state.payment.amount,
                action_cost=50,
                idempotency_key=f"{action_type}:{state.transaction_id}",
            )

    state, incident, diagnosis, _ = _context(orphaned_payment_inventory_available())
    action = next(a for a in diagnosis.candidate_actions if a.action_type == "RECONSTRUCT_ORDER")
    ledger = DecisionLedger()

    outcome = perform_recovery(
        incident,
        diagnosis,
        action,
        state,
        RecoveryPolicy(),
        LyingExecutor(),
        ledger,
        "inc-5",
    )

    assert outcome.execution["status"] == "EXECUTED"
    assert outcome.verification.status == "FAILED"
    assert outcome.verification.revenue_recovered == 0
    assert ledger.entries[0].verification_status == "FAILED"
    assert ledger.entries[0].revenue_recovered == 0
