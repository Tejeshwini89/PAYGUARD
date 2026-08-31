# PAYGUARD Adversarial Proof

This document records the safety properties intentionally attacked during the hardening phase. The demo remains deterministic and uses simulated transactions; no real merchant money is moved.

## Control boundary

```text
AI investigation / recommendation
        |
        v
Deterministic policy evaluation
        |
   +----+----+
   |    |    |
 ALLOW HUMAN DENY
   |    |    |
   |    v    v
   |  signed  stop
   |  one-time
   |  approval
   +----+----+
        |
        v
Executor
        |
        v
Post-action verification
        |
        v
Decision ledger
```

## Attacks covered

| Attack | Expected result |
| --- | --- |
| Unsupported action | DENY |
| Low diagnosis confidence | REQUIRE_HUMAN |
| Low action confidence | REQUIRE_HUMAN |
| Unknown inventory for reconstruction | DENY |
| Fulfillment retry when fulfillment is not failed | DENY |
| Executor called without authorization | REJECTED |
| Duplicate recovery | ALREADY_EXECUTED / suppressed |
| Mismatched verification action | FAILED, ₹0 recovered |
| Executor reports success without state mutation | FAILED verification, ₹0 recovered |
| High-value recovery above autonomous ceiling | REQUIRE_HUMAN |
| Refund action | REQUIRE_HUMAN |
| Bare `human_approved=true` without token | REJECTED |
| Forged approval token | REJECTED |
| Approval bound to wrong transaction | REJECTED |
| Approval token replay | REJECTED |
| Valid action-bound approval | EXECUTED then VERIFIED |
| Autonomous eligible recovery | EXECUTED then VERIFIED |

## Important invariants

### Authorization before execution
The executor is deny-by-default. A caller must pass explicit authorization after policy or human approval. A request that only sets the legacy boolean approval flag cannot authorize execution.

### Human approval is cryptographically bound
Approval grants contain the incident ID, transaction ID, action type, approver, issue time, and expiry. Validation checks the HMAC signature, expiry, request binding, and one-time-use state.

### Verification gates recovery credit
An executor success response is not enough. PAYGUARD verifies the resulting transaction state. If verification fails, simulated revenue recovered is zero and the ledger records the failed verification.

### High-value and sensitive actions remain gated
The autonomous recovery ceiling is ₹10,000 in the current MVP. Refund operations remain human-gated. These are policy decisions, not UI decorations.

## Evaluator interpretation

PAYGUARD is designed to make the following distinction explicit:

> **AI proposes. Policy authorizes. Executor acts. Verification proves. Ledger records.**

The adversarial suite is intended to demonstrate that the system does not blindly trust an AI recommendation, a caller-controlled approval flag, or an executor's success response.
