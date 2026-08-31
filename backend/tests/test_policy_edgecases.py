from app.detector import IncidentDetector
from app.evidence import build_evidence
from app.investigator import DeterministicInvestigator
from app.policy import RecoveryPolicy
from app.projector import StateProjector
from app.simulator import orphaned_payment
from app.tools import InvestigationTools
from app.models import Event


def test_orphaned_without_inventory_proof_cannot_execute():
    events = orphaned_payment()
    state = StateProjector().project(events[0].transaction_id, events)
    incident = IncidentDetector().detect(state, events)[0]
    tools = InvestigationTools(state, events, build_evidence(state, events))
    diagnosis = DeterministicInvestigator().investigate(incident, tools)
    action = diagnosis.candidate_actions[0]
    decision = RecoveryPolicy().evaluate(diagnosis, action, state)
    assert decision.decision == "DENY"
    assert "inventory" in decision.reason.lower()


def test_refund_is_never_autonomous():
    # Minimal synthetic state exposing the action policy directly.
    from app.investigator import CandidateAction, Diagnosis
    from app.models import TransactionState
    state = TransactionState("txn_x")
    state.payment.status = "CAPTURED"
    state.payment.amount = 5000
    diagnosis = Diagnosis("DUPLICATE_PAYMENT", "MULTIPLE_CAPTURED_PAYMENTS_FOR_TRANSACTION", 0.99)
    action = CandidateAction("REFUND_DUPLICATE", "verified duplicate", 5000, 25, 0.99)
    decision = RecoveryPolicy().evaluate(diagnosis, action, state)
    assert decision.decision == "REQUIRE_HUMAN"
