from app.portfolio import run_portfolio


def test_benchmark_dangerous_cases_cannot_be_autonomous():
    result = run_portfolio(total=100, seed=20260825, execute_autonomous=True)
    dangerous = [case for case in result.cases if case["scenario"] == "dangerous"]

    assert dangerous
    assert all(not case["actions"] or all(action["policy"] != "ALLOW_AUTONOMOUS" for action in case["actions"]) for case in dangerous)
    assert result.unsafe_autonomous_actions == 0


def test_benchmark_recovery_counts_match_case_outcomes():
    result = run_portfolio(total=100, seed=20260825, execute_autonomous=True)
    verified = sum(
        1
        for case in result.cases
        for action in case["actions"]
        if action.get("verification") == "VERIFIED"
    )
    recovered = sum(
        int(action.get("revenue_recovered", 0) or 0)
        for case in result.cases
        for action in case["actions"]
    )
    assert result.verified_recoveries == verified
    assert result.revenue_recovered == recovered
