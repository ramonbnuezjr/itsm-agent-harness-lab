# ITSM Agent Harness Lab

A hands-on lab for building governed AI agents in IT service management. This project implements a minimal but real agent harness—RAG, tool use, policy enforcement, and audit logging—wired to a ServiceNow-style incident workflow. It’s a concrete experiment in what work looks like when AI executes triage and resolution, and humans focus on planning and review.

This is part of my broader exploration of the **future of work**: as AI executes more, human work shifts to designing systems, setting constraints, and reviewing outcomes.

- Repo: https://github.com/ramonbnuezjr/itsm-agent-harness-lab  
- Builds page: https://www.ramonbnuezjr.com/builds  
- Future of Work: https://www.ramonbnuezjr.com  

---

## Problem

IT teams are deploying AI agents for incident triage, resolution, and workflow automation, but without clear governance, auditability, or policy enforcement. In regulated and public-sector environments, “move fast and break things” is not an option.

This lab asks: **What does a governed, auditable AI agent for ITSM actually look like in code?**

---

## Why this matters

- AI agents will execute an increasing share of ITSM work.  
- Leaders need patterns for **governance by design**: identity, tool permissions, policy checks, and audit trails on every action.  
- This lab produces reusable patterns and reference code for building agents that are safe, explainable, and aligned to real processes.

---

## What this lab explores

- **Models & inference**: Choosing and swapping models for different tasks.  
- **RAG**: Retrieval-augmented generation over ITSM knowledge bases and runbooks.  
- **Agents & tool use**: ReAct-style loops that call tools (search, create, update).  
- **MCP-style tooling**: Exposing capabilities as composable, governed tools.  
- **Workflows**: Encoding incident triage and resolution as executable processes.  
- **Governance**: Policies, guardrails, and audit logs as first-class citizens in the harness.  
- **Edge considerations**: What parts of this can run under real cost and latency constraints.

---

## Architecture (high level)

```text
[Incident Input]
      ↓
[Agent Harness Loop]
  - Reason (LLM)
  - Tools: search_kb, create_incident, update_incident, check_governance
  - Memory: short-term context + long-term skills/runbooks
  - Guardrails: policy checks, citations, human-in-the-loop gates
      ↓
[ServiceNow-style API / Mock]
      ↓
[Audit Log (JSONL)]
```

A more detailed diagram and rationale live in `docs/`.

---

## Current status

- [x] Repo created, vision and scope defined  
- [ ] v0.1: Basic RAG + one tool (`search_kb`) + simple agent loop  
- [ ] v0.2: Add `create_incident` / `update_incident` tools + basic policies  
- [ ] v1.0: Governance policies enforced + audit logging + sample scenarios  
- [ ] Iterating: More tools, better observability, real ServiceNow integration  

See `docs/` and `experiments/` for ongoing notes and results.

---

## How to use this repo

### For builders

- Treat this as reference code and a thinking partner.
- Clone, experiment, and adapt patterns to your own ITSM or workflow context.
- Open issues or PRs if you extend this in interesting ways.

### For leaders and architects

- Use the patterns here to:
  - Design your own agent harnesses.
  - Frame governance conversations with security, risk, and compliance.
  - Pilot small, governed agents before scaling.

---

## Project structure

```text
itsm-agent-harness-lab/
  docs/
    01-problem-and-outcomes.md
    02-architecture.md
    03-governance-model.md
    04-runbook.md
  src/
    harness/
      loop.py
      tools.py
      memory.py
      guardrails.py
      logger.py
    rag/
      ingest.py
      retrieve.py
    servicenow/
      client.py
      mock_api.py
    policies/
      policy_engine.py
      sample_policies.md
  tests/
    test_harness_loop.py
    test_policies.py
    test_scenarios/
      incident_triage_p1.yaml
      incident_triage_p3.yaml
  experiments/
    001-basic-triage/
      notes.md
      results.md
  assets/
    diagrams/
      harness-architecture.png
    slides/
      itsm-harness-snug-talk.pptx
  README.md
```

---

## What I assumed → How my thinking changed

- **Assumption:** Governance is mostly policy docs and human review.  
  **Now:** Governance must be encoded in the harness: tool permissions, policy checks, mandatory citations, and audit logs on every action.

- **Assumption:** Agents are mostly about prompts.  
  **Now:** The harness (loop, tools, memory, guardrails) matters more than the model for real-world behavior.

- **Assumption:** Public-sector constraints slow innovation.  
  **Now:** They force better design: explicit identities, clear policies, and auditable execution—exactly what enterprise AI needs.

---

## Next steps

- Implement v0.1: basic RAG + one tool + simple loop.  
- Write `docs/01-problem-and-outcomes.md` and `docs/03-governance-model.md`.  
- Generate an architecture infographic and slide deck for talks.  
- Share early findings on the blog and at NYC SNUG / AI meetups.

---

## License

MIT License — see [LICENSE](LICENSE).

---

**Future of Work**

This lab is one piece of a larger question: **What does work look like when AI executes more, and humans focus on planning and review?**  
See more at: https://www.ramonbnuezjr.com
