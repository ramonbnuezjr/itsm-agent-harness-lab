# Codex Handoff: ITSM Agent Harness Lab

This is the primary handoff for coding agents working in this repository. It defines the vision, implemented baseline, constraints, governance posture, and required working behavior. Read `AGENTS.md` as the contributor guide and this document as the product and architecture brief.

## 1. Project Vision

Build a governed AI agent harness for IT service management. The goal is not merely an agent that can triage incidents; it must operate under explicit policies, expose bounded tools, record auditable evidence, and keep model providers replaceable.

The broader question is how work changes when AI executes more tasks and humans increasingly design constraints, approve consequential actions, and review outcomes.

## 2. Current State

v0.1 is implemented and tested. It includes:

- Four synthetic ITSM runbooks in `data/kb/`.
- Deterministic term-frequency cosine retrieval.
- A strict `search_kb` function tool.
- A swappable `LLMProvider` boundary and OpenAI implementation.
- Citation validation against sources returned during the current run.
- Fail-closed replacement of noncompliant recommendations.
- Append-only local JSONL audit logging.
- `.env`-based local configuration with deployment-variable precedence.
- Thirteen offline tests and one successful live synthetic smoke test.

v0.1 does not mutate incidents or connect to ServiceNow. v0.2 will add governed mutation against a local mock only.

## 3. Role and Working Style

Act as a senior Python engineer and AI architect. Prefer clarity over cleverness, small composable modules, explicit contracts, and tests that include denied behavior. Ask how every feature will be governed, audited, and explained to a risk officer.

For non-trivial changes:

1. State the intent and smallest coherent scope.
2. Identify new files, dependencies, and security implications.
3. Implement policy before exposing consequential capability.
4. Test success, denial, malformed input, and failure paths.
5. Update the relevant docs and `docs/04-learning-log.md`.

## 4. Runtime and Configuration

- Machine: Mac Mini (2023), Apple M2, 8 GB.
- OS: macOS.
- Python: 3.10+; the verified local environment uses Python 3.11.
- Local models and Raspberry Pi deployment are out of scope for v0.1 and v0.2.
- Secrets: local values belong only in ignored `.env`; `.env.example` contains no secret.
- Production-style environment variables override `.env` values.
- Never use production incident data in this lab.

## 5. Model and API Strategy

The v0.1 provider uses the OpenAI Responses API. The default remains `gpt-4o-mini`, with `gpt-4o` available as an explicit heavier-reasoning alternative. Preserve these handoff choices unless a model evaluation or migration is requested.

The provider:

- Implements the generic `LLMProvider` boundary in `src/harness/providers.py`.
- Uses strict JSON-schema function tools and disables parallel calls for the v0.1 loop.
- Sets `store=False` explicitly rather than relying on the Responses API storage default.
- Records tool arguments and results, but never credentials or hidden reasoning.

Official references:

- [GPT-4o Mini model capabilities](https://developers.openai.com/api/docs/models/gpt-4o-mini)
- [Responses API create reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- [Function-calling guide](https://developers.openai.com/api/docs/guides/function-calling)

## 6. Architecture

```text
[Synthetic Incident]
        |
        v
[Agent Harness]
  |-- LLMProvider / OpenAI Responses API
  |-- search_kb tool
  |-- citation policy
  `-- JSONL audit logger
        |
        v
[Local Markdown KB + deterministic retriever]
```

Planned v0.2 adds a ServiceNow-style local mock plus `create_incident` and `update_incident`. Its control flow must be:

`propose → validate → authenticate → authorize → approve if required → execute → audit`

## 7. Governance Requirements

Governance is executable behavior, not prompt text. The model may propose an action; code determines whether it is allowed. Unknown tools, fields, transitions, identities, or approval states fail closed.

v0.1 recommendations require a citation matching a source returned by `search_kb` in the same run. v0.2 mutation rules are defined in `docs/03-governance-model.md` and must be implemented before mutation tools are exposed.

Audit records must make the decision reconstructable while minimizing data. Keep raw and final output distinct so reviewers can see what policy changed. Never record API keys, passwords, MFA codes, or unsanitized production content.

## 8. Documentation Map

- `README.md` — public overview, setup, current status, and roadmap.
- `AGENTS.md` — concise contributor instructions.
- `docs/01-problem-and-outcomes.md` — problem statement, stakeholders, outcomes, and non-goals.
- `docs/02-v0.1-plan.md` — completed v0.1 scope and verification evidence.
- `docs/03-governance-model.md` — implemented citation rule and proposed v0.2 mutation controls.
- `docs/04-learning-log.md` — assumptions, mistakes, failures, decisions, and open questions.
- `docs/05-v0.2-plan.md` — sequenced v0.2 milestones and acceptance criteria.
- `experiments/` — reproducible test observations and interpretations.

## 9. Next Milestone

Checkpoint v0.1 in Git, then implement v0.2 against a local mock. Start with identity, action schemas, state-transition rules, approval objects, and audit requirements. Add `create_incident` first; add `update_incident` only after create, denial, and audit paths are stable.

Do not connect to a live ServiceNow instance until the mock, policy matrix, and tests are mature and a separate integration decision is documented.
