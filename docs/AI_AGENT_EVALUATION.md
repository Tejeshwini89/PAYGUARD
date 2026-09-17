# PAYGUARD — AI Agent Execution Contract

## One-line description

**PAYGUARD is a tool-using financial incident investigation agent that turns verified transaction evidence into recovery recommendations, while a deterministic policy engine retains financial authorization.**

## What the AI agent actually does

The LLM is not a chatbot and is not the financial authority. For each detected incident it can:

1. Inspect projected payment state.
2. Inspect order state.
3. Inspect inventory state.
4. Inspect fulfillment state.
5. Inspect ordered event history.
6. Check for duplicate captured payments.
7. Read the structured evidence bundle.
8. Infer a root cause from verified evidence.
9. Produce evidence-backed candidate recovery actions.
10. Return confidence, expected recovery, expected cost, and a recommended action.

The tool set is read-only in the MVP. The model cannot directly execute a payment, refund, database mutation, or recovery operation.

## Authorization boundary

The execution path is intentionally:

```text
Transaction Events
      ↓
State Reconstruction
      ↓
Incident Detection
      ↓
AI Investigation Agent
      │
      ├── read-only tools
      ├── evidence claims
      ├── root-cause diagnosis
      └── candidate recovery actions
      ↓
LLM Output Sanitization
      ↓
Policy Engine
      │
      ├── ALLOW_AUTONOMOUS
      ├── REQUIRE_HUMAN
      └── DENY
      ↓
Recovery Executor
      ↓
Post-action Verification
      ↓
Decision Ledger
```

**Important:** the policy engine evaluates the **same AI diagnosis and candidate action produced by the investigator**. It does not silently replace an LLM diagnosis with the deterministic investigator before authorization. The deterministic investigator remains the reproducible fallback when no LLM is configured.

## Safety properties

- The model receives authoritative state and evidence through tools.
- Candidate actions are sanitized before policy evaluation.
- Unknown action types are removed.
- Recovery amounts are bounded by transaction evidence.
- Low-confidence diagnosis/action pairs require human review.
- High-value transactions require human review.
- Refunds require human approval.
- Risk flags can deny autonomous recovery.
- Recovery execution remains outside the LLM.
- Post-action verification is required.
- Decisions are recorded in the ledger.

## Evaluation scenarios

The repository includes controlled scenarios for:

- healthy transaction
- orphaned payment
- recoverable orphaned payment
- duplicate webhook/payment conditions
- fulfillment failure
- dangerous orphan / unsafe recovery conditions

The test suite also includes adversarial cases covering unknown actions, manipulated recovery amounts, duplicate and out-of-order events, insufficient evidence, human-approval boundaries, and verification failures.

## Demo boundary

The buildathon demo uses deterministic simulated transaction data. The Razorpay adapter is read/verify-only in this prototype and the demo executor does not move real merchant money.

## Regression test

`backend/tests/test_ai_policy_path.py` intentionally supplies a low-confidence AI diagnosis to the `/ai-investigate` path and verifies that the policy engine returns `REQUIRE_HUMAN`. This prevents a future implementation from accidentally evaluating a different deterministic diagnosis instead of the AI agent's output.
