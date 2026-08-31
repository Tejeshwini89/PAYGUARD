from app.portfolio import PortfolioSimulator, run_portfolio


def test_portfolio_has_stable_100_transaction_distribution():
    events, cases = PortfolioSimulator(seed=20260825).build()
    assert len(cases) == 100
    counts = {}
    for c in cases:
        counts[c.scenario] = counts.get(c.scenario, 0) + 1
    assert counts == {
        "healthy": 60,
        "delayed_webhook": 8,
        "duplicate_webhook": 6,
        "fulfillment_failure": 8,
        "orphaned_recoverable": 8,
        "duplicate_payment": 5,
        "dangerous": 5,
    }
    assert len(events) > 100


def test_portfolio_reconstructs_and_detects_expected_incidents_without_false_positives():
    result = run_portfolio()
    assert result.total_transactions == 100
    assert result.true_positives == result.expected_incidents
    assert result.false_negatives == 0
    assert result.false_positives == 0
    assert result.detection_precision == 1.0
    assert result.detection_recall == 1.0


def test_portfolio_execution_has_zero_unsafe_autonomous_actions():
    result = run_portfolio(execute_autonomous=True)
    assert result.unsafe_autonomous_actions == 0
    assert result.verified_recoveries > 0
    assert result.revenue_recovered > 0
