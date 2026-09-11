# Problem and Outcomes

## Problem

ITSM agents can recommend or execute work faster than traditional automation, but model capability alone does not make an agent trustworthy. In regulated or public-sector environments, every recommendation and action must be attributable, policy-checked, explainable, and reviewable.

This lab asks: **What is the smallest useful agent harness that makes governance part of execution rather than a document beside it?**

## Users and Stakeholders

- **Service-desk analysts** need grounded recommendations that accelerate triage without concealing uncertainty.
- **Platform engineers** need explicit tool and provider interfaces that can evolve safely.
- **Security, risk, and audit teams** need evidence of inputs, tool calls, policy decisions, and outputs.
- **Leaders and architects** need a concrete pattern they can inspect and explain.

## Desired Outcomes

The project should demonstrate that an ITSM agent can:

1. Retrieve approved operational knowledge before recommending an action.
2. Cite a source actually returned by the approved retrieval tool.
3. Withhold output when a mandatory policy fails.
4. Record a complete local audit event without recording credentials.
5. Swap model providers without rewriting the governance layer.
6. Add write-capable tools only behind identity, authorization, validation, and approval controls.

## v0.1 Evidence

The current implementation loads four synthetic Markdown runbooks, ranks them using deterministic term-frequency cosine similarity, exposes a strict `search_kb` tool, validates citations, and writes JSONL audit events. Thirteen offline tests cover retrieval, tool contracts, provider behavior, policy allow/deny paths, configuration precedence, and audit output. A live synthetic VPN test completed successfully on September 11, 2026.

## Non-Goals

v0.1 does not connect to ServiceNow, mutate incident records, use production data, provide production-grade secret management, or claim that a single live smoke test proves production reliability. Those boundaries are intentional.

## Next Hypothesis

v0.2 will test whether an agent can create and update records in a local ServiceNow-style mock while remaining inside an explicit action envelope. The governance contract is defined in `docs/03-governance-model.md` before those mutation tools are implemented.
