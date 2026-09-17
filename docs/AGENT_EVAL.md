# Agent Evaluation Notes

PAYGUARD's agent boundary is intentional: the language model investigates and proposes; deterministic policy authorizes.

For the live LLM investigation endpoint, the exact `Diagnosis` returned by the LLM is converted into the internal diagnosis/action schema and passed to the policy layer. The policy therefore evaluates the agent's actual proposed action rather than silently substituting a deterministic diagnosis.

The deterministic investigator remains available for reproducible benchmark/testing paths.
