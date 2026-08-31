from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .detector import IncidentDetector
from .evidence import build_evidence
from .investigator import CandidateAction, DeterministicInvestigator
from .llm_agent import OpenAIInvestigator
from .policy import RecoveryPolicy
from .executor import MerchantRecoveryStore, RecoveryExecutor
from .ledger import DecisionLedger
from .recovery import perform_recovery
from .projector import StateProjector
from pathlib import Path
import os

from .simulator import (
    duplicate_webhook,
    fulfillment_failure,
    healthy,
    orphaned_payment,
    orphaned_payment_inventory_available,
    dangerous_orphan,
)
from .tools import InvestigationTools
from .portfolio import run_portfolio
from .gateway import RazorpayGatewayClient, SimulatedGatewayClient
from .ingest import EventIngestor
from .razorpay_webhook import build_webhook_event
from .metrics import METRICS

app = FastAPI(title="PAYGUARD", version="1.0.0")
APP_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = APP_ROOT / "frontend"
app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
projector = StateProjector()
detector = IncidentDetector()
investigator = DeterministicInvestigator()
ai_investigator = OpenAIInvestigator()
policy = RecoveryPolicy()
recovery_store = MerchantRecoveryStore()
executor = RecoveryExecutor(recovery_store)
ledger = DecisionLedger()
razorpay_gateway = RazorpayGatewayClient()
sim_gateway = SimulatedGatewayClient()
razorpay_ingestor = EventIngestor()

SCENARIOS = {
    "healthy": healthy,
    "orphaned_payment": orphaned_payment,
    "orphaned_payment_recoverable": orphaned_payment_inventory_available,
    "duplicate_webhook": duplicate_webhook,
    "fulfillment_failure": fulfillment_failure,
    "dangerous_orphan": dangerous_orphan,
}


@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "service": "payguard-core", "version": "1.0.0", "metrics": METRICS.snapshot()}


@app.get("/gateway")
def gateway_status():
    return {
        "active_adapter": "simulator",
        "razorpay": razorpay_gateway.health(),
        "note": "Razorpay adapter is read/verify-only in this MVP; recovery execution remains behind PAYGUARD policy and merchant-side executor.",
    }


@app.get("/gateway/razorpay/payment/{payment_id}")
def razorpay_payment(payment_id: str):
    response = razorpay_gateway.fetch_payment(payment_id)
    return {"ok": response.ok, "status_code": response.status_code, "data": response.data, "error": response.error}


@app.get("/gateway/razorpay/order/{order_id}")
def razorpay_order(order_id: str):
    response = razorpay_gateway.fetch_order(order_id)
    return {"ok": response.ok, "status_code": response.status_code, "data": response.data, "error": response.error}


@app.get("/gateway/razorpay/order/{order_id}/payments")
def razorpay_order_payments(order_id: str):
    response = razorpay_gateway.fetch_order_payments(order_id)
    return {"ok": response.ok, "status_code": response.status_code, "data": response.data, "error": response.error}


@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, x_razorpay_signature: str = Header(default=""), x_razorpay_event_id: str = Header(default="")):
    raw_body = await request.body()
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="RAZORPAY_WEBHOOK_SECRET is not configured")
    if not x_razorpay_event_id:
        raise HTTPException(status_code=400, detail="Missing x-razorpay-event-id")

    event = build_webhook_event(raw_body, x_razorpay_event_id, x_razorpay_signature, secret)
    result = razorpay_ingestor.ingest(event)
    status = 200 if result.accepted or result.duplicate else 400
    return {
        "accepted": result.accepted,
        "duplicate": result.duplicate,
        "reason": result.reason,
        "event_id": event.event_id,
        "signature_verified": event.signature_verified,
        "status_code": status,
    }


def _run_scenario(scenario: str):
    events = SCENARIOS[scenario]()
    tx_id = events[0].transaction_id
    state = projector.project(tx_id, events)
    incidents = detector.detect(state, events)
    bundle = build_evidence(state, events)
    tools = InvestigationTools(state, events, bundle)
    investigations = []
    for incident in incidents:
        diagnosis = investigator.investigate(incident, tools)
        decisions = []
        for action in diagnosis.candidate_actions:
            decisions.append(policy.evaluate(diagnosis, action, state).__dict__)
        investigations.append({
            "incident": incident.__dict__,
            "diagnosis": {
                "incident_type": diagnosis.incident_type,
                "root_cause": diagnosis.root_cause,
                "confidence": diagnosis.confidence,
                "evidence": diagnosis.evidence,
                "candidate_actions": [a.__dict__ for a in diagnosis.candidate_actions],
            },
            "policy_decisions": decisions,
        })
    return state, incidents, investigations


@app.get("/demo/{scenario}")
def demo(scenario: str):
    if scenario not in SCENARIOS:
        return {"error": "unknown_scenario", "available": list(SCENARIOS)}
    state, incidents, _ = _run_scenario(scenario)
    return {
        "transaction_id": state.transaction_id,
        "state": {
            "payment": state.payment.status,
            "order": state.order.status,
            "inventory": state.inventory.status,
            "fulfillment": state.fulfillment.status,
        },
        "incidents": [i.__dict__ for i in incidents],
        "events_applied": state.event_ids_applied,
    }


@app.get("/investigate/{scenario}")
def investigate(scenario: str):
    if scenario not in SCENARIOS:
        return {"error": "unknown_scenario", "available": list(SCENARIOS)}
    state, _, investigations = _run_scenario(scenario)
    return {
        "transaction_id": state.transaction_id,
        "state": {
            "payment": state.payment.status,
            "order": state.order.status,
            "inventory": state.inventory.status,
            "fulfillment": state.fulfillment.status,
        },
        "investigations": investigations,
    }

@app.get("/ai-investigate/{scenario}")
def ai_investigate(scenario: str):
    if scenario not in SCENARIOS:
        return {"error": "unknown_scenario", "available": list(SCENARIOS)}
    events = SCENARIOS[scenario]()
    tx_id = events[0].transaction_id
    state = projector.project(tx_id, events)
    incidents = detector.detect(state, events)
    if not incidents:
        return {
            "transaction_id": tx_id,
            "mode": "no_incident",
            "message": "No revenue-threatening incident detected.",
        }
    bundle = build_evidence(state, events)
    tools = InvestigationTools(state, events, bundle)
    results = []
    for incident in incidents:
        diagnosis = ai_investigator.investigate(incident, state, tools)
        decisions = []
        for action in diagnosis.candidate_actions:
            candidate = CandidateAction(**action.model_dump())
            decisions.append(policy.evaluate(
                DeterministicInvestigator().investigate(incident, tools), candidate, state
            ).__dict__)
        results.append({
            "incident": incident.__dict__,
            "diagnosis": diagnosis.model_dump(),
            "policy_decisions": decisions,
            "llm_enabled": ai_investigator.client is not None,
        })
    return {
        "transaction_id": tx_id,
        "state": {
            "payment": state.payment.status,
            "order": state.order.status,
            "inventory": state.inventory.status,
            "fulfillment": state.fulfillment.status,
        },
        "investigations": results,
    }


@app.post("/recover/{scenario}/{action_type}")
def recover(scenario: str, action_type: str, human_approved: bool = False, approval_token: str | None = None):
    if scenario not in SCENARIOS:
        return {"error": "unknown_scenario", "available": list(SCENARIOS)}
    events = SCENARIOS[scenario]()
    tx_id = events[0].transaction_id
    state = projector.project(tx_id, events)
    incidents = detector.detect(state, events)
    if not incidents:
        return {"error": "no_incident", "transaction_id": tx_id}
    incident = incidents[0]
    bundle = build_evidence(state, events)
    tools = InvestigationTools(state, events, bundle)
    diagnosis = ai_investigator.investigate(incident, state, tools)
    selected = next((a for a in diagnosis.candidate_actions if a.action_type == action_type), None)
    if selected is None:
        return {"error": "action_not_proposed", "proposed_actions": [a.model_dump() for a in diagnosis.candidate_actions]}
    outcome = perform_recovery(
        incident,
        DeterministicInvestigator().investigate(incident, tools),
        CandidateAction(**selected.model_dump()),
        state,
        policy,
        executor,
        ledger,
        incident_id=f"{scenario}:{tx_id}:{action_type}",
        human_approved=human_approved,
        approval_token=approval_token,
    )
    return {
        "incident": incident.__dict__,
        "diagnosis": diagnosis.model_dump(),
        "outcome": {
            "policy": outcome.policy.__dict__,
            "execution": outcome.execution,
            "verification": outcome.verification.__dict__,
            "ledger": outcome.ledger,
        },
        "state_after": {
            "payment": state.payment.status,
            "order": state.order.status,
            "inventory": state.inventory.status,
            "fulfillment": state.fulfillment.status,
        },
    }


@app.get("/metrics")
def get_metrics():
    return METRICS.snapshot()


@app.get("/ledger")
def get_ledger():
    return {"entries": [entry.__dict__ for entry in ledger.entries]}


@app.get("/portfolio/benchmark")
def portfolio_benchmark(execute_autonomous: bool = False):
    result = run_portfolio(total=100, seed=20260825, execute_autonomous=execute_autonomous)
    return result.__dict__
