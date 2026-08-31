# PAYGUARD Core Architecture v0.1

```text
Raw Events
   -> Verification
   -> Deduplication
   -> Normalization
   -> Event-Time Ordering
   -> State Projection
   -> State Divergence Detection
   -> Incident Queue
   -> AI Investigation Agent (next milestone)
```

The deterministic core must remain independent from the LLM. The LLM will receive reconstructed state plus evidence and will not directly mutate financial state.

## Milestone 6 — Evaluation Harness
PAYGUARD includes a fixed, deterministic 100-transaction benchmark so every code change can be evaluated against the same adversarial traffic mix. The benchmark separates ground-truth incident labels from detector output and measures precision, recall, policy outcomes, verified recoveries, and recovered simulated revenue.


## Gateway boundary (Milestone 7)
PAYGUARD now exposes a provider adapter interface. The deterministic simulator and Razorpay share the same read contract. Razorpay is used for authoritative verification while merchant recovery remains policy-controlled.

Webhook path:
`Razorpay -> raw body -> HMAC verification -> event idempotency -> canonical Event -> StateProjector`

This preserves the core principle that the gateway is an evidence source, not the agent's decision authority.
