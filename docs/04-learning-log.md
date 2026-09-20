# Decisions, Assumptions, and Learning Log

## Purpose

This is the project’s durable learning record. It captures assumptions, mistakes, failed attempts, evidence, decisions, and unresolved questions. Update it whenever an assumption changes, a test exposes unexpected behavior, or a design tradeoff becomes clearer. Do not sanitize away useful failures, but never include credentials or sensitive incident data.

## Entry Format

For future entries, record:

- **Date and context**
- **Assumption or intended outcome**
- **Observation, mistake, or failure**
- **Decision and evidence**
- **Lesson and follow-up**

## 2026-09-10 — Repository Baseline

**Assumption:** The README’s project tree described code already present in the repository.

**Observation:** The repository initially contained only `README.md` and `LICENSE`; the tree was aspirational.

**Decision:** Treat the README as design intent, then update it to distinguish implemented v0.1 components from planned architecture.

**Lesson:** Documentation must label current state and target state explicitly. A plausible architecture diagram is not implementation evidence.

## 2026-09-10 — Runtime and Dependency Setup

**Assumption:** The default `python3` and test tooling would satisfy the handoff’s Python 3.10+ requirement.

**Failure:** The default interpreter was Python 3.9.6. Python 3.11 was installed separately but initially lacked pytest. An isolated editable build also stalled while attempting dependency resolution under restricted network access.

**Decision:** Create `.venv` with Python 3.11, install declared dependencies there, and verify commands through that environment. Use `pyproject.toml` as the dependency source of truth.

**Lesson:** Verify interpreter version, dependency availability, and network constraints independently. “Python is installed” does not mean the project runtime is ready.

## 2026-09-10 — Retrieval Baseline

**Assumption:** A useful RAG prototype required embeddings or a vector database.

**Decision:** Use deterministic term-frequency cosine similarity over four small Markdown runbooks for v0.1.

**Evidence:** Offline tests retrieve the expected VPN and account-lockout sources.

**Lesson:** Start with the simplest observable baseline. It is easier to explain, test, and compare against a later embedding-based retriever. The tradeoff is weaker semantic matching and no production-scale indexing.

## 2026-09-10 — Citation Governance

**Assumption:** Prompting the model to cite sources might be sufficient.

**Decision:** Enforce citations outside the model. A citation is valid only when it exactly matches a source returned by `search_kb` during the same run.

**Lesson:** Prompts express desired behavior; policies determine whether output may proceed. Governance must not depend solely on model compliance.

## 2026-09-11 — Local Secret Handling

**Mistake:** Initial setup documented a shell `export` but did not provide the expected local `.env` workflow.

**Decision:** Add an ignored `.env`, a safe `.env.example`, automatic loading with `python-dotenv`, restrictive permissions on the local file, and precedence for already-set deployment variables.

**Lesson:** Environment variables are the application interface; `.env` is a local-development convenience. Production should inject secrets through a managed environment or secret manager. Secret-handling expectations must be documented before asking a user to configure credentials.

## 2026-09-11 — Live API Smoke Test

**Intended outcome:** Validate authentication, Responses API function calling, KB retrieval, citation enforcement, and audit logging with synthetic data.

**Failure:** The first attempt failed with a DNS connection error because the execution sandbox blocked network access. This was not an API-key or application failure.

**Decision:** Retry with explicitly approved network access. The request succeeded using `gpt-4o-mini`, invoked `search_kb`, cited `[vpn-access.md]`, passed policy, and wrote audit event `d55600ac-3e55-4ebd-93e7-6e15711aa3b5` to the ignored local smoke-test log. The key was verified absent from the audit record.

**Lesson:** Classify failures by layer—environment, network, authentication, provider, tool, policy, or application—before changing code. One successful live run proves the integration path, not production reliability.

## 2026-09-11 — v0.2 Action Contracts

**Assumption:** The mutation layer could begin with executable tools and add governance checks afterward.

**Decision:** Define typed actors, approvals, incidents, and proposed actions first. `ActionPolicy` now validates identity, role, fields, secrets, approval scope, and state transitions without calling an external system.

**Evidence:** Nine focused contract tests cover allowed creation and work notes plus denied identity, unknown fields, secret input in fields and reasons, self-approval, mismatched approval, invalid transitions, and malformed objects. The full suite passes 23 tests.

**Lesson:** A typed proposal boundary makes authorization testable before side effects exist. Approval is a property of the exact proposed action—not a general permission that can be reused for a different change. Regression tests should include natural-language variants of security-sensitive terms, not only serialized field names.

## 2026-09-19 — v0.2 Local Incident Mock

**Assumption:** A local mock and a real ServiceNow Personal Developer Instance were alternatives, and choosing the instance would make the mock unnecessary.

**Decision:** Treat them as two targets with different jobs, mirroring the v0.1 model layer. The mock backs the default suite because governed-denial cases must run repeatedly, offline, and deterministically; a developer instance would later prove wire-level facts the mock cannot — real field names, the actual `state` representation, and authentication. The mock is reached through an `IncidentRepository` protocol so a future instance client can occupy the same seam, exactly as `LLMProvider` does for model providers.

**Decision:** Split enforcement by layer. `MockServiceNowAPI` enforces integrity — the record exists, the field is real, the value is a legal enum member, and a rejected write leaves no trace. It does not enforce identity, role, approval, or transition legality. `test_update_does_not_enforce_state_transitions` deliberately asserts that the mock permits `new` to `closed`, so that deleting `ActionPolicy` would break policy tests instead of passing silently against a mock strict enough to hide the loss.

**Evidence:** Eighteen tests cover deterministic identifiers, retrieval, append-only work notes, changed-field reporting, unknown and non-updatable fields, invalid enum values, missing records, caller-mutation isolation, and audit serialization. Validation completes before any value is stored, so a partially invalid update leaves the record untouched. The full suite passes 41 tests offline.

**Decision:** `ChangeRecord` carries only the fields a write actually changed, not the whole record. This is a first answer to learning question 4: a reviewer can reconstruct the delta without the audit log accumulating unchanged incident content.

**Lesson:** A mock is a test instrument, and its strictness is a design choice rather than a fidelity goal. Making it stricter than the real system would have produced passing tests that no longer depended on the governance layer being present.

**Follow-up:** `src/servicenow/mock_api.py` imports field names and enums from `src/policies/action_contracts.py` to keep one vocabulary for an incident. The dependency arguably runs backwards, since field names and states are properties of the external system rather than of policy. Revisit when a real instance client exists and the true field vocabulary is known.

## 2026-09-19 — v0.2 Governed Creation

**Assumption:** With contracts and storage both in place, wiring `create_incident` would be plumbing.

**Mistake caught during implementation:** The first audit design wrote the proposed fields verbatim. A proposal denied for carrying a secret would therefore have copied that secret into the audit log — the policy would refuse the action while the logging path preserved exactly the value the policy objected to. Denial is not containment if the rejected input is retained.

**Decision:** Redact before writing, using the same predicate the policy denies on. `_contains_secret` is now also exported as `contains_secret` so redaction and denial cannot drift apart; if one is loosened, both are. Field *names* are kept unredacted so a reviewer can still see what was attempted. `test_secret_bearing_field_value_is_never_written_to_the_audit_log` asserts against the raw log text rather than the parsed event, so a future serialization change cannot reintroduce the leak silently.

**Decision:** Identity is constructor-bound, never model-supplied. `GovernedActionExecutor` holds the actor; the action identifier is generated by an injected factory; approvals are passed by harness code. The tool schema omits `actor_id`, `role`, `action_id`, and `approval_id` entirely, and a test asserts their absence. A model that can name its own actor or mint its own action identifier can bind a stale approval to a new action, so the defense is the absence of the field rather than validation of it.

**Decision:** A denied action returns a structured outcome instead of raising. Raising would abort before the audit write, so the governed path would lose exactly the attempts most worth recording.

**Observation:** OpenAI strict function schemas require every declared property to appear in `required`. Optional incident fields are therefore declared nullable and the tool drops nulls before building the proposal, rather than omitting the properties.

**Observation:** Creating a P1 or P2 incident, or naming an assignment group at creation, already requires a bound approval under the existing `_requires_approval` rule. Governed creation inherited the approval gate before the approval flow of milestone 4 exists; tests cover both the denial and a correctly bound approval.

**Evidence:** Eighteen tests cover the allowed path, unauthenticated and wrong-role denial, unknown fields, invalid enum values, malformed proposals, both secret-redaction paths, approval and self-approval, storage failure, and schema shape. The full suite passes 59 tests offline. A manual run confirmed a denied secret-bearing proposal produced `outcome: denied`, no stored record, and no occurrence of the secret in the log file.

**Lesson:** Audit logging is an egress path and deserves the same scrutiny as any other. The governance question is not only "was this action refused" but "what did refusing it cause the system to retain".

**Follow-up:** `short_description` is required by storage but not by `ActionPolicy`, so omitting it produces `failed` after policy allowed the action rather than `denied` before execution. Fail-closed ordering argues for policy validating required creation fields. Deferred rather than changed, because it alters committed policy behavior; revisit alongside milestone 4.

## Current Assumptions to Test

- Four synthetic runbooks are enough to validate architecture, not retrieval quality at scale.
- `gpt-4o-mini` remains an appropriate learning baseline; model choice should be reevaluated with cost, latency, and quality measurements rather than novelty.
- Local JSONL is adequate for single-process experiments but not concurrent or production audit storage.
- Citation presence is necessary but does not prove the recommendation faithfully represents the source.
- Deterministic unit tests plus one live smoke test do not establish broad behavioral consistency; scenario evaluations and repeated runs are still needed.
- The v0.2 permission and approval matrix is a design hypothesis until implemented and tested.
- The initial action contracts use a deliberately small incident state machine and role set; the mock API may expose additional fields only after policy tests define them.
- A developer instance is expected to contradict some mock assumptions, particularly the string incident states and the simplified field set; the mock is a governance instrument, not a fidelity claim.

## Next Learning Questions

1. Which incident fields can an agent safely update without approval?
2. How should approval be bound to a specific proposed action and expire?
3. How often does lexical retrieval miss semantically relevant guidance?
4. What audit fields help reviewers reconstruct decisions without over-collecting data?
5. How should policy versions and model versions be compared across experiments?
