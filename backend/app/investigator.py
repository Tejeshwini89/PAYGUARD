from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .models import Incident, TransactionState
from .tools import InvestigationTools


@dataclass(frozen=True)
class CandidateAction:
    action_type: str
    reason: str
    expected_recovery: int
    expected_cost: int
    confidence: float


@dataclass
class Diagnosis:
    incident_type: str
    root_cause: str
    confidence: float
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    candidate_actions: List[CandidateAction] = field(default_factory=list)


class DeterministicInvestigator:
    """
    Pre-LLM investigation contract.

    This is intentionally deterministic. It establishes the evidence/diagnosis
    contract before an LLM is granted tool access.
    """

    def investigate(self, incident: Incident, tools: InvestigationTools) -> Diagnosis:
        payment = tools.get_payment()
        order = tools.get_order()
        inventory = tools.get_inventory()
        fulfillment = tools.get_fulfillment()
        duplicate = tools.check_duplicate_payment()
        amount = incident.revenue_at_risk

        evidence = [
            {"fact": "payment.status", "value": payment["status"], "source": "projected_state"},
            {"fact": "order.status", "value": order["status"], "source": "projected_state"},
            {"fact": "inventory.status", "value": inventory["status"], "source": "projected_state"},
            {"fact": "fulfillment.status", "value": fulfillment["status"], "source": "projected_state"},
            {"fact": "duplicate_payment", "value": duplicate["duplicate_detected"], "source": "event_history"},
        ]

        if incident.incident_type == "ORPHANED_PAYMENT":
            if inventory["status"] == "SOLD_OUT":
                return Diagnosis(
                    incident_type=incident.incident_type,
                    root_cause="PAYMENT_CAPTURED_WITHOUT_CONFIRMABLE_ORDER_AND_NO_INVENTORY",
                    confidence=0.99,
                    evidence=evidence,
                    candidate_actions=[
                        CandidateAction("ESCALATE_HUMAN", "Order reconstruction is unsafe without inventory.", 0, 50, 0.99),
                        CandidateAction("DO_NOTHING", "Avoid autonomous fulfillment/refund until merchant review.", 0, 0, 0.99),
                    ],
                )
            return Diagnosis(
                incident_type=incident.incident_type,
                root_cause="MERCHANT_ORDER_CONFIRMATION_FAILURE",
                confidence=0.97,
                evidence=evidence,
                candidate_actions=[
                    CandidateAction("RECONSTRUCT_ORDER", "Payment is captured and inventory is available.", amount, 50, 0.97),
                    CandidateAction("ESCALATE_HUMAN", "Fallback if order reconstruction cannot be verified.", amount, 100, 0.80),
                ],
            )

        if incident.incident_type == "FULFILLMENT_FAILURE":
            error = fulfillment.get("last_error") or "unknown"
            return Diagnosis(
                incident_type=incident.incident_type,
                root_cause=f"FULFILLMENT_FAILURE:{error}",
                confidence=0.96,
                evidence=evidence,
                candidate_actions=[
                    CandidateAction("RETRY_FULFILLMENT", "Paid order has reserved inventory and fulfillment failed.", amount, 100, 0.96),
                    CandidateAction("ESCALATE_HUMAN", "Fallback if retry cannot be verified.", amount, 150, 0.80),
                ],
            )

        if incident.incident_type == "DUPLICATE_PAYMENT":
            return Diagnosis(
                incident_type=incident.incident_type,
                root_cause="MULTIPLE_CAPTURED_PAYMENTS_FOR_TRANSACTION",
                confidence=0.99,
                evidence=evidence,
                candidate_actions=[
                    CandidateAction("REFUND_DUPLICATE", "Refund only after duplicate relationship is verified.", amount, 25, 0.90),
                    CandidateAction("ESCALATE_HUMAN", "Require review for ambiguous duplicate relationships.", amount, 100, 0.85),
                ],
            )

        return Diagnosis(
            incident_type=incident.incident_type,
            root_cause="UNKNOWN",
            confidence=0.50,
            evidence=evidence,
            candidate_actions=[CandidateAction("ESCALATE_HUMAN", "Unknown incident type.", 0, 0, 0.50)],
        )
