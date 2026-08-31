from __future__ import annotations

from dataclasses import dataclass, asdict
from random import Random
from typing import Dict, List, Tuple

from .detector import IncidentDetector
from .investigator import DeterministicInvestigator
from .models import Event, TransactionState
from .policy import RecoveryPolicy
from .projector import StateProjector
from .simulator import ev
from .tools import InvestigationTools
from .evidence import build_evidence
from .executor import MerchantRecoveryStore, RecoveryExecutor
from .ledger import DecisionLedger
from .recovery import perform_recovery
from .investigator import CandidateAction
from .llm_agent import OpenAIInvestigator


@dataclass(frozen=True)
class BenchmarkCase:
    transaction_id: str
    scenario: str
    amount: int
    ground_truth_incident: str | None
    expected_autonomous: bool


@dataclass
class PortfolioResult:
    total_transactions: int
    detected_incidents: int
    expected_incidents: int
    true_positives: int
    false_positives: int
    false_negatives: int
    detection_precision: float
    detection_recall: float
    autonomous_allowed: int
    human_required: int
    denied: int
    verified_recoveries: int
    revenue_at_risk: int
    revenue_recovered: int
    unsafe_autonomous_actions: int
    duplicate_events_injected: int
    out_of_order_cases: int
    breakdown: Dict[str, int]
    cases: List[dict]


class PortfolioSimulator:
    """Deterministically creates a merchant traffic storm for evaluation."""

    def __init__(self, seed: int = 20260825) -> None:
        self.seed = seed
        self.rng = Random(seed)
        self.base_cases: List[BenchmarkCase] = []

    def _tx(self, i: int) -> str:
        return f"txn_portfolio_{i:04d}"

    def _base(self, tx: str, amount: int, suffix: str) -> List[Event]:
        offset = 1
        return [
            ev(f"{tx}-1", tx, "order.created", offset, offset, {"order_id": f"ord_{tx}", "amount": amount}),
            ev(f"{tx}-2", tx, "payment.captured", offset + 1, offset + 1, {"payment_id": f"pay_{tx}", "amount": amount, "method": "upi"}),
            ev(f"{tx}-3", tx, "order.paid", offset + 2, offset + 2, {"order_id": f"ord_{tx}"}),
            ev(f"{tx}-4", tx, "inventory.reserved", offset + 3, offset + 3, {"product_id": f"prod_{suffix}", "available_quantity": 10, "reserved_quantity": 1}),
        ]

    def _healthy(self, tx: str, amount: int, i: int) -> List[Event]:
        events = self._base(tx, amount, str(i))
        events.extend([
            ev(f"{tx}-5", tx, "fulfillment.started", 5, 5),
            ev(f"{tx}-6", tx, "fulfillment.completed", 6, 6),
        ])
        return events

    def _delayed(self, tx: str, amount: int, i: int) -> List[Event]:
        events = self._base(tx, amount, str(i))[:3]
        events[1] = ev(f"{tx}-2", tx, "payment.captured", 2, 9, {"payment_id": f"pay_{tx}", "amount": amount, "method": "card"})
        events[2] = ev(f"{tx}-3", tx, "order.paid", 3, 4, {"order_id": f"ord_{tx}"})
        return events

    def _duplicate_webhook(self, tx: str, amount: int, i: int) -> List[Event]:
        events = self._delayed(tx, amount, i)
        events.append(ev(f"{tx}-3", tx, "order.paid", 3, 12, {"order_id": f"ord_{tx}"}))
        return events

    def _orphan_recoverable(self, tx: str, amount: int, i: int) -> List[Event]:
        return [
            ev(f"{tx}-1", tx, "order.created", 1, 1, {"order_id": f"ord_{tx}", "amount": amount}),
            ev(f"{tx}-2", tx, "payment.captured", 2, 2, {"payment_id": f"pay_{tx}", "amount": amount, "method": "upi"}),
            ev(f"{tx}-3", tx, "inventory.released", 3, 3, {"product_id": f"prod_{i}", "available_quantity": 8, "reserved_quantity": 0}),
        ]

    def _fulfillment_failure(self, tx: str, amount: int, i: int) -> List[Event]:
        events = self._base(tx, amount, str(i))
        events.append(ev(f"{tx}-5", tx, "fulfillment.failed", 5, 5, {"error": "carrier_timeout"}))
        return events

    def _duplicate_payment(self, tx: str, amount: int, i: int) -> List[Event]:
        events = self._base(tx, amount, str(i))
        events.append(ev(f"{tx}-5", tx, "payment.captured", 5, 5, {"payment_id": f"pay_{tx}_DUP", "amount": amount, "method": "upi"}))
        return events

    def _dangerous(self, tx: str, amount: int, i: int) -> List[Event]:
        return [
            ev(f"{tx}-1", tx, "order.created", 1, 1, {"order_id": f"ord_{tx}", "amount": amount}),
            ev(f"{tx}-2", tx, "payment.captured", 2, 2, {"payment_id": f"pay_{tx}", "amount": amount, "method": "card"}),
            ev(f"{tx}-3", tx, "inventory.released", 3, 3, {"product_id": f"prod_{i}", "available_quantity": 0, "reserved_quantity": 0, "fraud_signal": "HIGH"}),
        ]

    def build(self, total: int = 100) -> Tuple[List[Event], List[BenchmarkCase]]:
        if total != 100:
            raise ValueError("MVP benchmark is intentionally fixed at 100 transactions for a stable demo.")

        distributions = (
            [("healthy", 60),
             ("delayed_webhook", 8),
             ("duplicate_webhook", 6),
             ("fulfillment_failure", 8),
             ("orphaned_recoverable", 8),
             ("duplicate_payment", 5),
             ("dangerous", 5)]
        )
        cases: List[BenchmarkCase] = []
        all_events: List[Event] = []
        i = 1
        for scenario, count in distributions:
            for _ in range(count):
                tx = self._tx(i)
                amount = self.rng.choice([1999, 4999, 7499, 9999, 12999, 17999])
                if scenario == "healthy":
                    events = self._healthy(tx, amount, i)
                    gt, auto = None, False
                elif scenario == "delayed_webhook":
                    events = self._delayed(tx, amount, i)
                    gt, auto = None, False
                elif scenario == "duplicate_webhook":
                    events = self._duplicate_webhook(tx, amount, i)
                    gt, auto = None, False
                elif scenario == "fulfillment_failure":
                    events = self._fulfillment_failure(tx, amount, i)
                    gt, auto = "FULFILLMENT_FAILURE", amount <= 10000
                elif scenario == "orphaned_recoverable":
                    events = self._orphan_recoverable(tx, amount, i)
                    gt, auto = "ORPHANED_PAYMENT", amount <= 10000
                elif scenario == "duplicate_payment":
                    events = self._duplicate_payment(tx, amount, i)
                    gt, auto = "DUPLICATE_PAYMENT", False
                else:
                    events = self._dangerous(tx, amount, i)
                    gt, auto = "ORPHANED_PAYMENT", False
                cases.append(BenchmarkCase(tx, scenario, amount, gt, auto))
                all_events.extend(events)
                i += 1
        return all_events, cases


def run_portfolio(total: int = 100, seed: int = 20260825, execute_autonomous: bool = False) -> PortfolioResult:
    simulator = PortfolioSimulator(seed=seed)
    events, cases = simulator.build(total=total)
    by_tx: Dict[str, List[Event]] = {}
    for event in events:
        by_tx.setdefault(event.transaction_id, []).append(event)

    projector = StateProjector()
    detector = IncidentDetector()
    investigator = DeterministicInvestigator()
    policy = RecoveryPolicy()
    ai_investigator = OpenAIInvestigator()
    store = MerchantRecoveryStore()
    executor = RecoveryExecutor(store)
    ledger = DecisionLedger()

    expected_incidents = sum(c.ground_truth_incident is not None for c in cases)
    detected = 0
    true_positive = 0
    false_positive = 0
    false_negative = 0
    autonomous_allowed = 0
    human_required = 0
    denied = 0
    verified_recoveries = 0
    revenue_at_risk = 0
    revenue_recovered = 0
    unsafe_autonomous = 0
    duplicate_events_injected = 6
    out_of_order_cases = 14
    by_scenario: Dict[str, int] = {}
    case_results: List[dict] = []

    for case in cases:
        tx_events = by_tx[case.transaction_id]
        state = projector.project(case.transaction_id, tx_events)
        incidents = detector.detect(state, tx_events)
        predicted_types = {inc.incident_type for inc in incidents}
        by_scenario[case.scenario] = by_scenario.get(case.scenario, 0) + len(incidents)

        if incidents:
            detected += 1
            revenue_at_risk += sum(i.revenue_at_risk for i in incidents)
        if case.ground_truth_incident in predicted_types:
            true_positive += 1
        elif case.ground_truth_incident is not None and not incidents:
            false_negative += 1
        elif case.ground_truth_incident is None and incidents:
            false_positive += 1

        action_outcomes = []
        for incident in incidents:
            deterministic = investigator.investigate(incident, InvestigationTools(state, tx_events, build_evidence(state, tx_events)))
            diagnosis = ai_investigator.investigate(incident, state, InvestigationTools(state, tx_events, build_evidence(state, tx_events)))
            for action_model in diagnosis.candidate_actions:
                candidate = CandidateAction(**action_model.model_dump())
                decision = policy.evaluate(deterministic, candidate, state)
                if decision.decision == "ALLOW_AUTONOMOUS":
                    autonomous_allowed += 1
                    if not case.expected_autonomous:
                        unsafe_autonomous += 1
                    if execute_autonomous and case.expected_autonomous and candidate.action_type in {"RECONSTRUCT_ORDER", "RETRY_FULFILLMENT"}:
                        outcome = perform_recovery(
                            incident, deterministic, candidate, state, policy, executor, ledger,
                            incident_id=f"benchmark:{case.transaction_id}:{candidate.action_type}",
                        )
                        action_outcomes.append({
                            "action": candidate.action_type,
                            "policy": decision.decision,
                            "verification": outcome.verification.status,
                            "revenue_recovered": outcome.verification.revenue_recovered,
                        })
                        if outcome.verification.status == "VERIFIED":
                            verified_recoveries += 1
                            revenue_recovered += outcome.verification.revenue_recovered
                    else:
                        action_outcomes.append({"action": candidate.action_type, "policy": decision.decision})
                elif decision.decision == "REQUIRE_HUMAN":
                    human_required += 1
                    action_outcomes.append({"action": candidate.action_type, "policy": decision.decision})
                else:
                    denied += 1
                    action_outcomes.append({"action": candidate.action_type, "policy": decision.decision})

        case_results.append({
            "transaction_id": case.transaction_id,
            "scenario": case.scenario,
            "amount": case.amount,
            "ground_truth_incident": case.ground_truth_incident,
            "detected": bool(incidents),
            "predicted_incidents": sorted(predicted_types),
            "autonomous_expected": case.expected_autonomous,
            "actions": action_outcomes,
        })

    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 1.0
    recall = true_positive / expected_incidents if expected_incidents else 1.0
    breakdown = {
        "healthy": 0,
        "delayed_webhook": 0,
        "duplicate_webhook": 0,
        "fulfillment_failure": 0,
        "orphaned_recoverable": 0,
        "duplicate_payment": 0,
        "dangerous": 0,
    }
    breakdown.update(by_scenario)

    return PortfolioResult(
        total_transactions=total,
        detected_incidents=detected,
        expected_incidents=expected_incidents,
        true_positives=true_positive,
        false_positives=false_positive,
        false_negatives=false_negative,
        detection_precision=round(precision, 4),
        detection_recall=round(recall, 4),
        autonomous_allowed=autonomous_allowed,
        human_required=human_required,
        denied=denied,
        verified_recoveries=verified_recoveries,
        revenue_at_risk=revenue_at_risk,
        revenue_recovered=revenue_recovered,
        unsafe_autonomous_actions=unsafe_autonomous,
        duplicate_events_injected=duplicate_events_injected,
        out_of_order_cases=out_of_order_cases,
        breakdown=breakdown,
        cases=case_results,
    )
