from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

from .executor import RecoveryExecutor
from .investigator import CandidateAction, Diagnosis
from .ledger import DecisionLedger
from .models import Incident, TransactionState
from .policy import PolicyDecision, RecoveryPolicy
from .verifier import verify, VerificationResult


@dataclass(frozen=True)
class RecoveryOutcome:
    incident_type: str
    transaction_id: str
    action_type: str
    policy: PolicyDecision
    execution: Dict[str, Any]
    verification: VerificationResult
    ledger: Dict[str, Any]


def perform_recovery(
    incident: Incident,
    diagnosis: Diagnosis,
    action: CandidateAction,
    state: TransactionState,
    policy: RecoveryPolicy,
    executor: RecoveryExecutor,
    ledger: DecisionLedger,
    incident_id: str,
    human_approved: bool = False,
) -> RecoveryOutcome:
    policy_decision = policy.evaluate(diagnosis, action, state)

    authorized = policy_decision.decision == "ALLOW_AUTONOMOUS" or (
        policy_decision.decision == "REQUIRE_HUMAN" and human_approved
    )

    execution = executor.execute(action.action_type, state, approved=authorized)
    verification = verify(action.action_type, state, execution)

    entry = ledger.record(
        incident_id=incident_id,
        transaction_id=state.transaction_id,
        action_type=action.action_type,
        policy_decision=policy_decision.decision,
        execution_status=execution.status,
        verification_status=verification.status,
        revenue_recovered=verification.revenue_recovered,
        action_cost=execution.action_cost,
        details={
            "policy_reason": policy_decision.reason,
            "action_reason": action.reason,
            "action_confidence": action.confidence,
            "expected_recovery": action.expected_recovery,
            "expected_cost": action.expected_cost,
            "execution_message": execution.message,
            "verification_message": verification.message,
        },
    )

    return RecoveryOutcome(
        incident_type=incident.incident_type,
        transaction_id=state.transaction_id,
        action_type=action.action_type,
        policy=policy_decision,
        execution=execution.__dict__,
        verification=verification,
        ledger=entry.__dict__,
    )
