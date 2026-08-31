from __future__ import annotations

from dataclasses import dataclass

from .investigator import CandidateAction, Diagnosis
from .models import TransactionState


@dataclass(frozen=True)
class PolicyDecision:
    action_type: str
    decision: str  # ALLOW_AUTONOMOUS | REQUIRE_HUMAN | DENY
    reason: str


class RecoveryPolicy:
    def __init__(self, autonomous_limit: int = 10_000, min_confidence: float = 0.90) -> None:
        self.autonomous_limit = autonomous_limit
        self.min_confidence = min_confidence

    def evaluate(self, diagnosis: Diagnosis, action: CandidateAction, state: TransactionState) -> PolicyDecision:
        amount = state.payment.amount or state.order.amount or 0

        if diagnosis.confidence < self.min_confidence or action.confidence < self.min_confidence:
            return PolicyDecision(action.action_type, "REQUIRE_HUMAN", "Confidence below autonomous threshold.")

        if action.action_type == "REFUND_DUPLICATE":
            return PolicyDecision(action.action_type, "REQUIRE_HUMAN", "Refund is financially irreversible in the MVP.")

        if amount > self.autonomous_limit:
            return PolicyDecision(action.action_type, "REQUIRE_HUMAN", "Transaction exceeds autonomous value limit.")

        if action.action_type == "RECONSTRUCT_ORDER":
            if state.inventory.status != "AVAILABLE":
                return PolicyDecision(action.action_type, "DENY", "Inventory is not available for safe reconstruction.")
            return PolicyDecision(action.action_type, "ALLOW_AUTONOMOUS", "High-confidence recovery within policy and inventory is available.")

        if action.action_type == "RETRY_FULFILLMENT":
            if state.fulfillment.status != "FAILED":
                return PolicyDecision(action.action_type, "DENY", "Fulfillment is not currently failed.")
            return PolicyDecision(action.action_type, "ALLOW_AUTONOMOUS", "Retry is bounded and transaction value is within policy.")

        if action.action_type == "ESCALATE_HUMAN":
            return PolicyDecision(action.action_type, "REQUIRE_HUMAN", "Explicit human escalation action.")

        return PolicyDecision(action.action_type, "DENY", "Action is not permitted by policy.")
