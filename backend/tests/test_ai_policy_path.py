from app import main
from app.llm_agent import AIAction, DiagnosisOutput, EvidenceClaim


def test_ai_diagnosis_is_the_input_to_policy(monkeypatch):
    """A low-confidence LLM diagnosis must not be replaced by the deterministic diagnosis."""

    def fake_investigate(incident, state, tools):
        return DiagnosisOutput(
            incident_type=incident.incident_type,
            root_cause="AI_LOW_CONFIDENCE_TEST",
            confidence=0.50,
            summary="Synthetic regression-test diagnosis.",
            evidence=[
                EvidenceClaim(
                    fact="payment.status",
                    value="CAPTURED",
                    source="projected_state",
                    confidence=0.50,
                )
            ],
            candidate_actions=[
                AIAction(
                    action_type="RECONSTRUCT_ORDER",
                    reason="Synthetic low-confidence action.",
                    expected_recovery=1000,
                    expected_cost=50,
                    confidence=0.50,
                )
            ],
            recommended_action="RECONSTRUCT_ORDER",
        )

    monkeypatch.setattr(main.ai_investigator, "investigate", fake_investigate)

    result = main.ai_investigate("orphaned_payment_recoverable")
    decisions = result["investigations"][0]["policy_decisions"]

    assert decisions[0]["decision"] == "REQUIRE_HUMAN"
    assert decisions[0]["reason"] == "Confidence below autonomous threshold."
