from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set

from .models import TransactionState


@dataclass(frozen=True)
class ExecutionResult:
    action_type: str
    status: str  # EXECUTED | ALREADY_EXECUTED | REJECTED
    message: str
    revenue_preserved: int = 0
    action_cost: int = 0
    idempotency_key: str = ""


@dataclass
class MerchantRecoveryStore:
    """In-memory merchant-side system for deterministic, safe MVP execution."""

    order_confirmed: Set[str] = field(default_factory=set)
    fulfillment_attempts: Dict[str, int] = field(default_factory=dict)
    refunded_payments: Set[str] = field(default_factory=set)


class RecoveryExecutor:
    def __init__(self, store: MerchantRecoveryStore | None = None) -> None:
        self.store = store or MerchantRecoveryStore()

    @staticmethod
    def _key(action_type: str, state: TransactionState) -> str:
        return f"{action_type}:{state.transaction_id}"

    def execute(self, action_type: str, state: TransactionState, *, approved: bool = False) -> ExecutionResult:
        """Execute only after explicit authorization from the policy/human gate.

        Deny-by-default is intentional: callers must explicitly pass approved=True
        after authorization rather than being able to execute by omission.
        """
        key = self._key(action_type, state)
        amount = state.payment.amount or state.order.amount or 0

        if not approved:
            return ExecutionResult(action_type, "REJECTED", "Execution was not authorized by the policy/human gate.", 0, 0, key)

        if action_type == "RECONSTRUCT_ORDER":
            if state.inventory.status != "AVAILABLE":
                return ExecutionResult(action_type, "REJECTED", "Inventory is not available; order reconstruction is unsafe.", 0, 0, key)
            if state.transaction_id in self.store.order_confirmed:
                return ExecutionResult(action_type, "ALREADY_EXECUTED", "Order reconstruction is already complete for this transaction.", amount, 50, key)
            self.store.order_confirmed.add(state.transaction_id)
            state.order.status = "PAID"
            state.fulfillment.status = "NOT_STARTED"
            return ExecutionResult(action_type, "EXECUTED", "Merchant order reconstructed and linked to the captured payment.", amount, 50, key)

        if action_type == "RETRY_FULFILLMENT":
            if state.fulfillment.status != "FAILED":
                return ExecutionResult(action_type, "REJECTED", "Fulfillment is not currently failed.", 0, 0, key)
            attempts = self.store.fulfillment_attempts.get(state.transaction_id, 0)
            if attempts >= 1:
                return ExecutionResult(action_type, "ALREADY_EXECUTED", "Bounded fulfillment retry has already been consumed.", amount, 100, key)
            self.store.fulfillment_attempts[state.transaction_id] = attempts + 1
            state.fulfillment.status = "COMPLETED"
            state.fulfillment.attempt_count += 1
            return ExecutionResult(action_type, "EXECUTED", "Fulfillment retry succeeded in the merchant simulator.", amount, 100, key)

        if action_type == "REFUND_DUPLICATE":
            payment_id = state.payment.payment_id or "unknown-payment"
            if payment_id in self.store.refunded_payments:
                return ExecutionResult(action_type, "ALREADY_EXECUTED", "Duplicate refund request was suppressed by idempotency protection.", 0, 25, key)
            # The MVP deliberately never executes a refund autonomously.
            if not approved:
                return ExecutionResult(action_type, "REJECTED", "Refund requires explicit human approval in the MVP.", 0, 0, key)
            self.store.refunded_payments.add(payment_id)
            return ExecutionResult(action_type, "EXECUTED", "Refund operation recorded in the merchant simulator after explicit approval.", 0, 25, key)

        return ExecutionResult(action_type, "REJECTED", "Unknown recovery action.", 0, 0, key)
