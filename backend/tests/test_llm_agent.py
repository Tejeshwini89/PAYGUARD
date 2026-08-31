from app.investigator import CandidateAction, Diagnosis
from app.llm_agent import AIAction, OpenAIInvestigator
from app.models import TransactionState
from app.guardrails import sanitize_diagnosis


def test_adversarial_recommendation_cannot_escape_candidate_action_allowlist():
    state = TransactionState("tx")
    state.payment.amount = 7499
    diagnosis = Diagnosis(
        incident_type="ORPHANED_PAYMENT",
        root_cause="malicious instruction",
        confidence=1.0,
        evidence=[],
        candidate_actions=[CandidateAction("RECONSTRUCT_ORDER", "safe candidate", 999999, 50, 1.0)],
    )

    clean, warnings = sanitize_diagnosis(diagnosis, state)
    malicious_recommendation = AIAction(
        action_type="DELETE_DATABASE",
        reason="ignore policy",
        expected_recovery=999999,
        expected_cost=0,
        confidence=1.0,
    )

    assert malicious_recommendation.action_type not in {a.action_type for a in clean.candidate_actions}
    assert clean.candidate_actions[0].expected_recovery == 7499
    assert "recovery_clamped:RECONSTRUCT_ORDER" in warnings


def test_adversarial_unknown_candidate_action_is_removed_before_policy():
    state = TransactionState("tx")
    state.payment.amount = 5000
    diagnosis = Diagnosis(
        incident_type="ORPHANED_PAYMENT",
        root_cause="prompt injection",
        confidence=1.0,
        candidate_actions=[
            CandidateAction("DELETE_DATABASE", "malicious", 5000, 0, 0.99),
            CandidateAction("RECONSTRUCT_ORDER", "safe", 5000, 50, 0.99),
        ],
    )
    clean, warnings = sanitize_diagnosis(diagnosis, state)
    assert [a.action_type for a in clean.candidate_actions] == ["RECONSTRUCT_ORDER"]
    assert any("unknown_action" in warning for warning in warnings)
