# ITSM Agent Harness Lab

A hands-on lab for building governed AI agents in IT service management. The project explores what work looks like when AI executes more tasks while humans design constraints, approve consequential actions, and review outcomes.

- Repository: https://github.com/ramonbnuezjr/itsm-agent-harness-lab
- Builds: https://www.ramonbnuezjr.com/builds
- Future of Work: https://www.ramonbnuezjr.com

## Why This Exists

An agent that can recommend or execute ITSM work is not automatically safe. Regulated and public-sector environments need explicit tool permissions, grounded recommendations, human approval gates, and evidence that reconstructs every decision.

This lab asks: **What does a minimal, governed, and auditable ITSM agent look like in code?**

## Current Status: v0.1 Complete

The implemented baseline:

- Loads four synthetic Markdown ITSM runbooks.
- Ranks them with deterministic term-frequency cosine similarity.
- Exposes one strict tool: `search_kb(query)`.
- Uses a swappable `LLMProvider` with an OpenAI Responses API implementation.
- Requires recommendations to cite a source returned during the same run.
- Withholds recommendations that fail policy.
- Records input, tool calls, raw and final output, and policy results in JSONL.
- Loads local secrets from an ignored `.env` without overriding deployed variables.
- Passes 13 offline tests and one live synthetic smoke test.

v0.1 is read-only: it does not modify incidents or connect to ServiceNow.

## v0.1 Architecture

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

## Quickstart

Python 3.10 or newer is required; Python 3.11 is the verified local runtime.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Edit `.env` and provide a project API key:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

Then run a synthetic incident:

```bash
itsm-triage "One user cannot connect to the corporate VPN gateway"
```

The model can also be selected with `--model`. Audit events default to `var/audit.jsonl`.

## Verification

Run all offline checks without calling the OpenAI API:

```bash
python -m pytest
python -m compileall -q src tests
git diff --check
```

The live smoke-test record is summarized in `experiments/001-basic-triage/notes.md`. Local JSONL logs are ignored and may contain synthetic incident content.

## Security Boundaries

- Never commit `.env`, API keys, passwords, MFA codes, or production incident data.
- Commit only the empty `.env.example` template.
- Use synthetic fixtures and incidents throughout v0.1 and v0.2.
- Existing environment variables take precedence over `.env`.
- OpenAI requests set `store=False` explicitly.
- Treat local JSONL as development evidence, not production-grade audit storage.

## Project Structure

```text
data/kb/                         Synthetic approved runbooks
docs/                            Product, governance, and learning records
experiments/001-basic-triage/    Reproducible observations
src/harness/                     Loop, tools, provider, config, and logger
src/policies/                    Executable governance checks
src/rag/                         KB ingestion and retrieval
tests/                           Offline unit tests and scenario fixtures
AGENTS.md                        Contributor guide
pyproject.toml                   Package and dependency configuration
```

## Documentation Map

- `docs/00-codex-handoff.md` — product and architecture handoff.
- `docs/01-problem-and-outcomes.md` — stakeholders, outcomes, and non-goals.
- `docs/02-v0.1-plan.md` — completed implementation and verification record.
- `docs/03-governance-model.md` — current citation policy and proposed mutation controls.
- `docs/04-learning-log.md` — assumptions, mistakes, failures, decisions, and open questions.
- `docs/05-v0.2-plan.md` — sequenced plan and acceptance criteria for governed mutation.

The learning log is intentionally candid. A failed attempt is useful evidence when it is classified correctly and does not expose sensitive data.

## Roadmap

### v0.2 — Governed Incident Mutation

1. Implement identity and action schemas.
2. Add a local ServiceNow-style mock.
3. Add `create_incident` behind validation and authorization.
4. Add `update_incident` behind field permissions, transition rules, and approval gates.
5. Audit attempted, denied, approved, completed, and failed actions.

The required execution sequence is:

`propose → validate → authenticate → authorize → approve if required → execute → audit`

### Later

- Compare lexical retrieval with embeddings using measured scenarios.
- Add production-grade observability and audit storage patterns.
- Evaluate real ServiceNow integration only after mock policies are stable.
- Explore local and edge models as a separate phase.

## License

MIT License — see [LICENSE](LICENSE).
