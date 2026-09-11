# Governance Model

## Status and Scope

The citation control is implemented in v0.1. The mutation controls below are the proposed contract for v0.2 and must be implemented before `create_incident` or `update_incident` can execute.

## Principles

- **Fail closed:** missing identity, malformed arguments, unknown fields, unavailable policy evaluation, or missing approval results in denial.
- **Separate proposal from execution:** model output is never itself authorization.
- **Least privilege:** expose only the tools and fields needed for the current task.
- **Ground recommendations:** citations must match sources returned by `search_kb` during the same run.
- **Audit decisions:** record attempts, denials, approvals, executions, and failures without recording credentials.
- **Keep humans accountable:** high-impact changes require an identified approver.

## Decision Flow

Every action follows the same sequence:

`propose → validate schema → authenticate actor → evaluate policy → obtain approval when required → execute → audit`

No later stage may run if an earlier stage fails.

## Tool Policy Matrix

| Tool or action | Default decision | Required controls |
| --- | --- | --- |
| `search_kb` | Allow | Non-empty query; approved local KB only |
| `create_incident` in local mock | Allow for `service_desk_agent` | Valid schema, synthetic data, generated record ID |
| Add sanitized `work_notes` | Allow for `service_desk_agent` | Existing incident and append-only note |
| Change category or urgency | Conditional | Allowed values and reason recorded |
| Change assignment group | Human approval | Actor, approver, reason, before/after values |
| Set P1/P2 priority | Human approval | Impact/urgency evidence and approver |
| Resolve or close an incident | Human approval | Resolution evidence and approver |
| Unknown field, invalid transition, or secret-bearing input | Deny | Record denial reason; do not execute |

## v0.1 Citation Policy

A recommendation passes only when it contains an exact label such as `[vpn-access.md]` and that source was returned by `search_kb` in the same run. A plausible-looking but unreturned citation fails. Failed recommendations are replaced with a safe escalation message while the raw model output and policy result remain in the local audit record.

## Identity and Approval Contract for v0.2

Each mutation request must include an authenticated actor ID and role. Approval-required actions must additionally include an approver ID, approval timestamp, and scope matching the proposed action. Self-approval is not permitted in the lab model. Approval is single-use and must be bound to the incident, fields, and proposed values.

## Audit Requirements

Each event must include a unique ID, UTC timestamp, actor, input, requested tool and arguments, policy version, decision, reason, approval reference when applicable, execution result, and final user-visible output. Secrets, passwords, MFA codes, API keys, and production incident content are prohibited.

## Verification Requirements

Tests must cover allowed and denied behavior, unknown fields, invalid transitions, missing identity, missing or mismatched approval, secret detection, execution failures, and immutable before/after audit evidence. Live ServiceNow access remains out of scope until the mock and policies are stable.
