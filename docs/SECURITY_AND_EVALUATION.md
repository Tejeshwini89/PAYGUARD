# PAYGUARD — Security, Safety & Evaluation v0.1

PAYGUARD treats the language model as an investigator and planner, not as the source of financial authority.

## Safety boundaries

1. Authoritative payment/order reads come from gateway or merchant evidence, not model inference.
2. The LLM has read-only investigation tools in the MVP.
3. Candidate actions are validated by a non-LLM guardrail before policy evaluation.
4. Unknown action types are dropped.
5. Expected recovery is capped at the transaction amount.
6. Refunds require human approval.
7. High-value transactions require human approval.
8. Missing/contradictory evidence must escalate rather than guess.
9. Recovery execution is idempotent.
10. Every action is followed by post-action verification.

## Adversarial evaluation suite

The hardening suite covers:

- malformed/tampered webhook signatures
- duplicate webhook delivery
- out-of-order events
- stale/partial evidence
- hallucinated or unknown recovery actions
- hallucinated recovery amounts
- high-value transactions
- irreversible refunds
- post-execution state corruption
- read-only investigation integrity

## Claims policy

Benchmark precision/recall and simulated revenue recovery are engineering test results only. They must never be presented as real merchant outcomes.

## Production gaps

Before production, PAYGUARD would still require persistent storage, durable queues, distributed locks/idempotency keys, authenticated merchant users, secrets management, audit-log retention, rate limiting, retry/backoff policies, alerting, PCI/security review as applicable, and real-world evaluation against labeled merchant incidents.
