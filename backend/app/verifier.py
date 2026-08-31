from __future__ import annotations

from dataclasses import dataclass

from .models import TransactionState
from .executor import ExecutionResult


@dataclass(frozen=True)
class VerificationResult:
    status: str  # VERIFIED | FAILED
    message: str
    revenue_recovered: int = 0


def verify(action_type: str, state: TransactionState, result: ExecutionResult) -> VerificationResult:
    if result.status not in {"EXECUTED", "ALREADY_EXECUTED"}:
        return VerificationResult("FAILED", "Recovery action did not execute.", 0)

    amount = state.payment.amount or state.order.amount or 0

    if action_type == "RECONSTRUCT_ORDER":
        ok = state.payment.status == "CAPTURED" and state.order.status == "PAID"
        return VerificationResult("VERIFIED" if ok else "FAILED", "Payment and order relationship verified." if ok else "Order state is still inconsistent.", amount if ok else 0)

    if action_type == "RETRY_FULFILLMENT":
        ok = state.order.status == "PAID" and state.fulfillment.status == "COMPLETED"
        return VerificationResult("VERIFIED" if ok else "FAILED", "Fulfillment reached completed state." if ok else "Fulfillment remains incomplete.", amount if ok else 0)

    if action_type == "REFUND_DUPLICATE":
        return VerificationResult("VERIFIED", "Duplicate refund operation recorded after approval.", 0)

    return VerificationResult("FAILED", "No verifier exists for this action.", 0)
