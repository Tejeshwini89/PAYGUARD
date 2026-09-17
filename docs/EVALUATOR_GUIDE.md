# PAYGUARD — Evaluator Guide

## What is the agent?

PAYGUARD is an AI-assisted revenue-recovery investigator for payment/order incidents. It is designed for merchants operating payment workflows where a successful payment can become inconsistent with downstream order, inventory, or fulfillment state.

The core loop is:

`Event ingestion → state projection → incident detection → evidence gathering → LLM investigation → typed action proposal → non-LLM policy authorization → guarded execution → post-action verification → audit ledger`

The LLM is deliberately **not** the financial authority. It investigates evidence and proposes typed actions. A deterministic policy layer makes the authorization decision.

## Agent capabilities

The LLM investigator has read-only tools for:

- payment state
- order state
- inventory state
- fulfillment state
- chronological event history
- duplicate-payment detection
- evidence bundles

The structured agent output contains an incident type, root cause, confidence, evidence claims, and candidate actions. Unknown or malformed actions are rejected before policy evaluation.

## Safety model

PAYGUARD separates reasoning from authority:

1. Gateway/merchant evidence is authoritative for payment facts.
2. The LLM has read-only investigation access in the MVP.
3. Candidate actions are sanitized and validated before authorization.
4. Policy can return `ALLOW_AUTONOMOUS`, `REQUIRE_HUMAN`, or `DENY`.
5. Low-confidence and high-value cases require human approval.
6. Refunds require human approval.
7. Risk flags block autonomous recovery.
8. Recovery is bounded, idempotent, verified after execution, and recorded in the ledger.

## How to verify the agent path

Use the `/ai-investigate/{scenario}` endpoint. It returns the LLM diagnosis and the policy decision for the **same diagnosis**, making the relationship between agent reasoning and authorization explicit.

Useful scenarios include:

- `healthy`
- `orphaned_payment`
- `orphaned_payment_recoverable`
- `duplicate_webhook`
- `fulfillment_failure`
- `dangerous_orphan`

`llm_enabled` reports whether the configured LLM client is available. The repository also contains deterministic investigation logic for reproducible tests and fallback/demo behavior; this should not be confused with the LLM investigator.

## What the demo does not claim

PAYGUARD is an engineering MVP using simulated scenarios. It does not claim real merchant revenue recovery, production-scale reliability, or authorization to move real funds. Production deployment would require the controls documented in `docs/SECURITY_AND_EVALUATION.md`.
