# PAYGUARD
## AI Revenue Recovery & Transaction Incident Agent

PAYGUARD is an AI-assisted revenue recovery control plane for payment-driven businesses. It detects revenue-threatening inconsistencies across the payment, order, inventory, and fulfillment lifecycle; reconstructs transaction state from events; investigates incidents using structured evidence; evaluates recovery options economically; applies policy guardrails; executes only authorized recovery actions; verifies the result; and records an auditable decision ledger.

The core idea is simple:

```text
Detect -> Investigate -> Diagnose -> Quantify -> Govern -> Recover -> Verify -> Audit
```

> **Demo boundary:** The benchmark and War Room use deterministic simulated transaction data. No real merchant money is moved by the demo executor.

## Architecture

```text
Razorpay / Simulator
        |
        v
Event Ingestion + Deduplication
        |
        v
Transaction State Reconstruction
        |
        v
Incident Detection
        |
        v
Evidence + Investigation
        |
        v
Economic Recovery Planning
        |
        v
AI Guardrails + Policy Engine
        |
        v
Recovery Executor
        |
        v
Post-action Verification
        |
        v
Decision Ledger + Merchant Dashboard
```

PAYGUARD deliberately separates AI investigation and recommendation from recovery authorization. AI can analyze evidence and propose a recovery action, but the policy engine determines whether that action can execute. Unsupported, unsafe, insufficiently evidenced, or high-value actions can be denied or routed for human approval.

## Transaction Model

A successful payment does not always mean a successful order lifecycle. A transaction can reach a state such as:

```text
Payment       = CAPTURED
Order         = CREATED
Inventory     = AVAILABLE
Fulfillment   = NOT_STARTED
```

This type of cross-system divergence can represent revenue at risk.

PAYGUARD reconstructs transaction state from events, handles duplicate and out-of-order events, detects lifecycle inconsistencies, gathers evidence, diagnoses the likely failure, calculates recovery economics, and applies policy before any recovery execution.

## Project Structure

```text
PAYGUARD/
├── backend/
│   ├── app/
│   │   ├── detector.py
│   │   ├── evidence.py
│   │   ├── executor.py
│   │   ├── gateway.py
│   │   ├── guardrails.py
│   │   ├── ingest.py
│   │   ├── investigator.py
│   │   ├── ledger.py
│   │   ├── llm_agent.py
│   │   ├── main.py
│   │   ├── metrics.py
│   │   ├── models.py
│   │   ├── normalizer.py
│   │   ├── policy.py
│   │   ├── portfolio.py
│   │   ├── projector.py
│   │   ├── razorpay_webhook.py
│   │   ├── recovery.py
│   │   ├── simulator.py
│   │   ├── tools.py
│   │   └── verifier.py
│   └── tests/
├── frontend/
├── docs/
├── .env.example
├── .gitignore
├── README.md
└── run_payguard.bat
```

## Windows Quick Start

The recommended way to run PAYGUARD is the included launcher.

From the project root:

```powershell
.\run_payguard.bat
```

The launcher creates the local virtual environment if necessary, installs the required dependencies, and starts the FastAPI application.

Wait until the terminal reports that the application has started successfully, then open:

```text
http://127.0.0.1:8000/
```

PAYGUARD serves its frontend and backend from the same FastAPI application.

You do **not** need to start a separate frontend server for the normal PAYGUARD demo.

## Manual Setup

If you prefer to start PAYGUARD manually:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
uvicorn backend.app.main:app --reload
```

If PowerShell blocks script activation:

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/
```

## Run Tests

From the project root:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

The repository currently contains a deterministic test suite covering transaction handling, incident detection, investigation, policy enforcement, recovery, gateway behavior, and hardening scenarios.

The validated development environment currently reports:

```text
36 passed
```

## Investigation

PAYGUARD supports a deterministic investigation path and an optional LLM-powered investigation path.

The deterministic investigator provides reproducible structured diagnoses without requiring an external AI API. This makes the core demonstration repeatable and allows the recovery and policy layers to be evaluated consistently.

The optional LLM investigator can be enabled by creating a local `.env` file from `.env.example` and configuring:

```text
OPENAI_API_KEY=...
```

The `.env` file is excluded from version control.

Regardless of investigation mode, recovery authorization remains inside PAYGUARD's structured policy and execution layers.

## Razorpay Integration Boundary

PAYGUARD includes a Razorpay gateway adapter and webhook handling path.

For optional Razorpay Test Mode configuration:

```text
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
```

The Razorpay adapter in this build is read/verify-only.

Recovery authorization remains inside PAYGUARD's policy and merchant-side execution layers. The buildathon demo does not move real merchant money.

## Demo Flow

1. Start PAYGUARD using `.\run_payguard.bat`.
2. Open the dashboard at `http://127.0.0.1:8000/`.
3. Click **Run incident sweep**.
4. Watch the controlled transaction replay in the War Room.
5. Inspect the surfaced incidents.
6. Open an incident in the Investigation Console.
7. Review payment, order, inventory, and fulfillment state.
8. Review the evidence and AI diagnosis.
9. Review the economic recovery recommendation.
10. Observe the policy decision.
11. Show the Decision Ledger.
12. Review the deterministic benchmark results.

The intended operational flow is:

```text
Transaction Events
        |
        v
State Reconstruction
        |
        v
Incident Detection
        |
        v
Evidence Collection
        |
        v
Investigation
        |
        v
Recovery Economics
        |
        v
Policy Decision
        |
        v
Authorized Execution
        |
        v
Verification
        |
        v
Audit
```

## Engineering Safeguards

PAYGUARD includes automated tests for important failure and safety cases, including duplicate event handling, out-of-order event arrival, transaction state reconstruction, healthy transactions producing no incident, revenue-threatening incident detection, read-only investigation, unknown or tampered recovery actions, AI output sanitization, insufficient evidence causing denial, refunds requiring human approval, high-value recovery requiring human approval, recovery idempotency, execution failure detection, post-action verification, decision ledger recording, and gateway behavior.

The system is intentionally not designed to automate every recovery action.

The goal is to automate only what can be safely justified.

## Recovery and Governance

PAYGUARD separates the recovery lifecycle into explicit stages:

```text
Diagnosis
    |
    v
Candidate Recovery Action
    |
    v
Policy Evaluation
    |
    +------> DENY
    |
    +------> REQUIRE HUMAN
    |
    +------> ALLOW AUTONOMOUS
                    |
                    v
              Recovery Executor
                    |
                    v
              Verification
                    |
                    v
              Decision Ledger
```

This allows PAYGUARD to use AI for investigation and decision support without giving the AI unrestricted authority over financial actions.

The policy layer can enforce constraints such as:

- insufficient evidence
- unsupported recovery actions
- sensitive actions such as refunds
- high-value recovery thresholds
- human approval requirements

## Deterministic Benchmark

PAYGUARD includes a controlled portfolio benchmark using deterministic simulated transaction data.

The portfolio benchmark uses a fixed seed so that the same controlled transaction portfolio can be replayed and evaluated consistently.

The benchmark is intended to measure system behavior rather than claim real merchant performance.

The UI may display metrics such as incident detection, recovery outcomes, simulated revenue recovered, human-review routing, and unsafe autonomous actions.

These figures are **simulation results**, not claims of real merchant revenue recovery.

No real merchant money is moved by the demo executor.

## API Surface

The FastAPI application exposes endpoints for application health, gateway status, Razorpay read/verify operations, webhook ingestion, deterministic demonstrations, investigation, AI investigation, recovery, metrics, ledger access, and portfolio benchmarking.

```text
GET  /
GET  /health
GET  /gateway

GET  /gateway/razorpay/payment/{payment_id}
GET  /gateway/razorpay/order/{order_id}
GET  /gateway/razorpay/order/{order_id}/payments

POST /webhooks/razorpay

GET  /demo/{scenario}
GET  /investigate/{scenario}
GET  /ai-investigate/{scenario}

POST /recover/{scenario}/{action_type}

GET  /metrics
GET  /ledger
GET  /portfolio/benchmark
```

## Production Path

PAYGUARD is a buildathon prototype with a deterministic simulation environment. The current demonstration does not move real merchant money.

A production deployment would require additional infrastructure and controls, including production-grade persistence, distributed event processing, stronger authentication and authorization, secrets management, observability and alerting, distributed idempotency guarantees, production payment-provider integration, operational approval workflows, comprehensive failure recovery, load and resilience testing, security review, and applicable compliance and audit controls.

The architecture is intentionally designed so that these production concerns can be introduced without giving an AI model unrestricted authority over financial actions.

## Project Goal

PAYGUARD's goal is simple:

> **Recover revenue without blind automation.**

Detect the divergence.

Investigate the evidence.

Quantify the opportunity.

Apply policy.

Recover safely.

Verify the result.

Preserve the decision trail.