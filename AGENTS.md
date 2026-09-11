# Repository Guidelines

## Project Structure & Module Organization

Place agent orchestration, provider boundaries, tools, and audit logging in `src/harness/`; retrieval code in `src/rag/`; and explicit governance rules in `src/policies/`. Approved sample runbooks live in `data/kb/`. Keep design decisions under `docs/`, reproducible investigations under `experiments/<number>-<topic>/`, and presentation-ready files under `assets/`. Mirror source behavior in `tests/`; scenario fixtures belong in `tests/test_scenarios/`.

## Build, Test, and Development Commands

Use Python 3.10 or newer. Create a virtual environment and install development dependencies with `python -m pip install -e '.[dev]'`. Key checks are:

- `python -m pytest` — run the complete test suite.
- `python -m pytest tests/test_policies.py` — run one focused module.
- `python -m compileall -q src` — catch Python syntax errors quickly.
- `python -m harness.loop "One user cannot connect to VPN"` — run local triage; requires `OPENAI_API_KEY`.
- `git diff --check` — detect whitespace errors before committing.

Document new setup or run commands in `README.md`. Record changed assumptions, failed attempts, decisions, and follow-ups in `docs/04-learning-log.md` in the same change that produces the learning.

## Coding Style & Naming Conventions

Use four-space indentation and PEP 8 conventions. Name modules, functions, variables, and tool identifiers with `snake_case` (`search_kb`, `policy_engine.py`); use `PascalCase` for classes and `UPPER_SNAKE_CASE` for constants. Keep tool interfaces small and explicit. Separate model reasoning, external-system access, policy decisions, and audit logging so each can be tested independently. The v0.1 baseline adds no formatter or linter; configure one in `pyproject.toml` before enforcing it.

## Testing Guidelines

Use `test_*.py` for test modules and descriptive `test_<behavior>` names. Cover successful actions and governed failure paths, especially denied permissions, missing citations, human-approval gates, malformed tool responses, and audit records. Keep scenario inputs deterministic; never require live ServiceNow credentials for the default suite.

## Commit & Pull Request Guidelines

Existing history uses short, imperative subjects such as `Add README for ITSM Agent Harness Lab`. Follow that style and keep commits focused. Pull requests should explain the problem, implementation, governance or security impact, and verification performed. Link relevant issues and include screenshots only for diagrams, slides, or other visual changes.

## Security & Configuration

Never commit credentials, production incident data, or sensitive audit logs. Store local secrets only in the ignored `.env`; keep `.env.example` limited to empty or non-sensitive defaults. Deployed environment variables must take precedence over local files. Use sanitized fixtures, and document required variable names without example secrets.
