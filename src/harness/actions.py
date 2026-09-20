"""Governed execution of proposed incident actions.

This module is the boundary where a model proposal becomes a real write.  It
enforces the ordering that the whole harness depends on: build a typed
proposal, evaluate policy, and only then touch storage.  Identity is supplied
by the harness at construction time and is never read from model output, so a
model cannot name its own actor, mint its own action identifier, or attach its
own approval.

Every attempt produces exactly one audit event.  Field values and reasons are
redacted with the same rule that policy denies on, so a denied secret-bearing
proposal cannot leak the secret into the audit log.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping
from uuid import uuid4

from harness.logger import AuditLogger
from policies.action_contracts import (
    CREATE_FIELDS,
    ActionPolicy,
    ActionType,
    Actor,
    Approval,
    Incident,
    ProposedAction,
    contains_secret,
)
from policies.policy_engine import PolicyCheck
from servicenow.mock_api import IncidentRepository

REDACTED = "[redacted]"
REASON_ARGUMENT = "reason"


class ActionOutcome(str, Enum):
    """Terminal outcome of one governed action attempt."""

    DENIED = "denied"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ActionResult:
    """Outcome of a governed action, including its audit evidence."""

    outcome: ActionOutcome
    detail: str
    audit_event_id: str
    policy_check: PolicyCheck | None = None
    incident_id: str | None = None

    def as_tool_response(self) -> dict[str, object]:
        """Render the result as the payload returned to the model.

        Returns:
            A dictionary carrying the outcome, explanation, resulting record
            identifier, and audit event identifier.
        """
        return {
            "outcome": self.outcome.value,
            "detail": self.detail,
            "incident_id": self.incident_id,
            "audit_event_id": self.audit_event_id,
        }


def _redact(value: object) -> object:
    """Replace a value that trips the secret rule with a placeholder.

    Args:
        value: A proposed field value or reason.

    Returns:
        The original value, or :data:`REDACTED` when it may carry a secret.
    """
    return REDACTED if contains_secret(value) else value


def _redact_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    """Redact every proposed field value that may carry a secret.

    Args:
        fields: Proposed field values, which may include unknown field names.

    Returns:
        A dictionary safe to write to the audit log.  Field names are kept so
        reviewers can see what was attempted.
    """
    return {
        str(name): (REDACTED if contains_secret(name) else _redact(value))
        for name, value in fields.items()
    }


def _snapshot(incident: Incident) -> dict[str, Any]:
    """Capture the created values of an incident for audit evidence.

    Args:
        incident: The stored incident record.

    Returns:
        A JSON-serializable dictionary of the creatable fields.
    """
    snapshot: dict[str, Any] = {}
    for name in sorted(CREATE_FIELDS):
        value = getattr(incident, name)
        snapshot[name] = value.value if isinstance(value, Enum) else value
    return snapshot


class GovernedActionExecutor:
    """Evaluate and execute proposed incident actions, auditing every attempt."""

    def __init__(
        self,
        *,
        actor: Actor | None,
        repository: IncidentRepository,
        audit_logger: AuditLogger,
        action_id_factory: Callable[[], str] | None = None,
    ) -> None:
        """Bind the identity and systems a governed action runs against.

        Args:
            actor: The authenticated actor, or ``None`` when no identity was
                established.  A missing actor denies every action.
            repository: Incident storage to write through once policy allows.
            audit_logger: Append-only log receiving one event per attempt.
            action_id_factory: Source of action identifiers.  Defaults to
                random UUIDs; tests inject a deterministic factory.
        """
        self.actor = actor
        self.repository = repository
        self.audit_logger = audit_logger
        self.policy = ActionPolicy()
        self._action_id_factory = action_id_factory or (lambda: str(uuid4()))

    def create_incident(
        self,
        arguments: Mapping[str, Any],
        *,
        approval: Approval | None = None,
    ) -> ActionResult:
        """Propose, govern, and conditionally execute an incident creation.

        Args:
            arguments: Model-supplied field values plus a ``reason``.  Unknown
                names are passed through to policy so the attempt is audited
                rather than silently discarded.
            approval: A human approval bound to this exact action, supplied by
                the harness rather than by the model.

        Returns:
            An :class:`ActionResult` whose outcome is ``denied`` when policy
            refused, ``failed`` when an allowed write did not complete, and
            ``completed`` when the incident was stored.
        """
        if not isinstance(arguments, Mapping):
            arguments = {}
        fields = {
            name: value for name, value in arguments.items() if name != REASON_ARGUMENT
        }
        reason = arguments.get(REASON_ARGUMENT)
        action_id = self._action_id_factory()

        try:
            action = ProposedAction(
                action_id=action_id,
                action_type=ActionType.CREATE_INCIDENT,
                fields=fields,
                reason=reason,  # type: ignore[arg-type]
            )
        except (TypeError, ValueError) as exc:
            return self._record(
                outcome=ActionOutcome.DENIED,
                detail=f"Malformed action proposal: {exc}",
                action_id=action_id,
                fields=fields,
                reason=reason,
                approval=approval,
            )

        check = self.policy.evaluate(self.actor, action, approval=approval)
        if not check.passed:
            return self._record(
                outcome=ActionOutcome.DENIED,
                detail=check.detail,
                action_id=action_id,
                fields=fields,
                reason=reason,
                approval=approval,
                policy_check=check,
            )

        try:
            incident = self.repository.create(action.fields)
        except Exception as exc:  # Boundary layer: a storage failure must be
            # audited as a failed attempt, never raised past the governed path.
            return self._record(
                outcome=ActionOutcome.FAILED,
                detail=str(exc),
                action_id=action_id,
                fields=fields,
                reason=reason,
                approval=approval,
                policy_check=check,
            )

        return self._record(
            outcome=ActionOutcome.COMPLETED,
            detail="Incident created.",
            action_id=action_id,
            fields=fields,
            reason=reason,
            approval=approval,
            policy_check=check,
            incident=incident,
        )

    def _record(
        self,
        *,
        outcome: ActionOutcome,
        detail: str,
        action_id: str,
        fields: Mapping[str, Any],
        reason: object,
        approval: Approval | None,
        policy_check: PolicyCheck | None = None,
        incident: Incident | None = None,
    ) -> ActionResult:
        """Write one audit event and return the matching result.

        Args:
            outcome: Terminal outcome of the attempt.
            detail: Human-readable explanation drawn from policy or storage.
            action_id: Harness-generated identifier for this attempt.
            fields: Proposed field values, redacted before they are written.
            reason: Proposed justification, redacted before it is written.
            approval: Approval presented with the action, if any.
            policy_check: Policy decision, absent only for malformed proposals
                that never reached evaluation.
            incident: The stored record, present only on success.

        Returns:
            An :class:`ActionResult` carrying the audit event identifier.
        """
        event_id = self.audit_logger.append(
            {
                "event_type": "incident_action",
                "action_id": action_id,
                "action_type": ActionType.CREATE_INCIDENT.value,
                "actor_id": self.actor.actor_id if self.actor is not None else None,
                "actor_role": self.actor.role.value if self.actor is not None else None,
                "approval_id": approval.approval_id if approval is not None else None,
                "fields": _redact_fields(fields),
                "reason": _redact(reason),
                "policy_checks": (
                    [policy_check.as_dict()] if policy_check is not None else []
                ),
                "outcome": outcome.value,
                "detail": detail,
                "incident_id": incident.incident_id if incident is not None else None,
                "created": _snapshot(incident) if incident is not None else None,
            }
        )
        return ActionResult(
            outcome=outcome,
            detail=detail,
            audit_event_id=event_id,
            policy_check=policy_check,
            incident_id=incident.incident_id if incident is not None else None,
        )
