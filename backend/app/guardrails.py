from __future__ import annotations

from dataclasses import replace
from typing import Iterable, List, Tuple

from .investigator import CandidateAction, Diagnosis
from .models import TransactionState

ALLOWED_ACTIONS = {
    "RECONSTRUCT_ORDER",
    "RETRY_FULFILLMENT",
    "REFUND_DUPLICATE",
    "ESCALATE_HUMAN",
    "DO_NOTHING",
}


def sanitize_diagnosis(diagnosis: Diagnosis, state: TransactionState) -> Tuple[Diagnosis, List[str]]:
    """Apply non-LLM safety constraints to an LLM-produced diagnosis."""
    warnings: List[str] = []
    amount = state.payment.amount or state.order.amount or 0

    if diagnosis.confidence < 0 or diagnosis.confidence > 1:
        warnings.append("diagnosis_confidence_out_of_range")
        diagnosis = replace(diagnosis, confidence=max(0.0, min(1.0, diagnosis.confidence)))

    safe_actions: List[CandidateAction] = []
    for action in diagnosis.candidate_actions:
        if action.action_type not in ALLOWED_ACTIONS:
            warnings.append(f"unknown_action:{action.action_type}")
            continue
        expected = max(0, min(action.expected_recovery, amount))
        if expected != action.expected_recovery:
            warnings.append(f"recovery_clamped:{action.action_type}")
        safe_actions.append(replace(action, expected_recovery=expected))

    if diagnosis.incident_type == "DUPLICATE_PAYMENT":
        # A duplicate-payment diagnosis may recommend refund, but never as an
        # implicitly safe operation; the policy layer must gate it.
        pass

    if not safe_actions:
        warnings.append("no_safe_actions_after_validation")
        safe_actions = [CandidateAction("ESCALATE_HUMAN", "No validated recovery action remains.", 0, 0, min(diagnosis.confidence, 0.5))]

    return replace(diagnosis, candidate_actions=safe_actions), warnings
