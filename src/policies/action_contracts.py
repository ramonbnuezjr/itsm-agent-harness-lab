"""Typed, deterministic contracts for v0.2 incident actions.

This module deliberately contains no ServiceNow or model-provider code.  It
answers only whether a proposed action is well-formed and governed enough to
reach a future execution adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from policies.policy_engine import PolicyCheck


class ActorRole(str, Enum):
    SERVICE_DESK_AGENT = "service_desk_agent"
    INCIDENT_MANAGER = "incident_manager"


class ActionType(str, Enum):
    CREATE_INCIDENT = "create_incident"
    UPDATE_INCIDENT = "update_incident"


class IncidentPriority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class IncidentState(str, Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


CREATE_FIELDS = frozenset(
    {
        "short_description",
        "description",
        "category",
        "impact",
        "urgency",
        "assignment_group",
        "priority",
    }
)
UPDATE_FIELDS = frozenset(
    {
        "category",
        "urgency",
        "assignment_group",
        "priority",
        "state",
        "work_notes",
    }
)
HIGH_IMPACT_PRIORITIES = frozenset({IncidentPriority.P1, IncidentPriority.P2})
ALLOWED_TRANSITIONS = {
    IncidentState.NEW: frozenset({IncidentState.IN_PROGRESS}),
    IncidentState.IN_PROGRESS: frozenset({IncidentState.RESOLVED}),
    IncidentState.RESOLVED: frozenset({IncidentState.CLOSED}),
    IncidentState.CLOSED: frozenset(),
}


def _required_text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _coerce_enum(value: object, enum_type: type[Enum], name: str) -> Enum:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(member.value for member in enum_type)
        raise ValueError(f"{name} must be one of: {allowed}") from exc


@dataclass(frozen=True)
class Actor:
    actor_id: str
    role: ActorRole

    def __post_init__(self) -> None:
        _required_text(self.actor_id, "actor_id")
        object.__setattr__(self, "role", _coerce_enum(self.role, ActorRole, "role"))


@dataclass(frozen=True)
class Incident:
    incident_id: str
    short_description: str
    description: str = ""
    category: str = ""
    impact: str = ""
    urgency: str = ""
    priority: IncidentPriority = IncidentPriority.P3
    assignment_group: str = ""
    state: IncidentState = IncidentState.NEW
    work_notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _required_text(self.incident_id, "incident_id")
        _required_text(self.short_description, "short_description")
        object.__setattr__(
            self, "priority", _coerce_enum(self.priority, IncidentPriority, "priority")
        )
        object.__setattr__(self, "state", _coerce_enum(self.state, IncidentState, "state"))


@dataclass(frozen=True)
class ProposedAction:
    action_id: str
    action_type: ActionType
    fields: Mapping[str, Any]
    reason: str
    incident_id: str | None = None

    def __post_init__(self) -> None:
        _required_text(self.action_id, "action_id")
        _required_text(self.reason, "reason")
        object.__setattr__(
            self, "action_type", _coerce_enum(self.action_type, ActionType, "action_type")
        )
        if not isinstance(self.fields, Mapping):
            raise ValueError("fields must be a mapping")
        object.__setattr__(self, "fields", dict(self.fields))
        if self.action_type is ActionType.CREATE_INCIDENT and self.incident_id is not None:
            raise ValueError("create_incident cannot include incident_id")
        if self.action_type is ActionType.UPDATE_INCIDENT:
            _required_text(self.incident_id, "incident_id")


@dataclass(frozen=True)
class Approval:
    approval_id: str
    approver: Actor
    action_id: str
    incident_id: str | None
    approved_fields: Mapping[str, Any]
    approved_at: datetime

    def __post_init__(self) -> None:
        _required_text(self.approval_id, "approval_id")
        _required_text(self.action_id, "action_id")
        if not isinstance(self.approver, Actor):
            raise ValueError("approver must be an Actor")
        if self.approver.role is not ActorRole.INCIDENT_MANAGER:
            raise ValueError("approver must have the incident_manager role")
        if self.incident_id is not None:
            _required_text(self.incident_id, "incident_id")
        if not isinstance(self.approved_fields, Mapping):
            raise ValueError("approved_fields must be a mapping")
        if not isinstance(self.approved_at, datetime):
            raise ValueError("approved_at must be a datetime")
        if self.approved_at.tzinfo is None:
            raise ValueError("approved_at must be timezone-aware")
        object.__setattr__(self, "approved_fields", dict(self.approved_fields))


def _contains_secret(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_secret(key) or _contains_secret(item) for key, item in value.items())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_secret(item) for item in value)
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    markers = ("api_key", "api key", "apikey", "password", "secret", "mfa_code", "token")
    return any(marker in lowered for marker in markers) or "sk-" in lowered


class ActionPolicy:
    """Evaluate action contracts before any execution adapter is called."""

    name = "governed_incident_action_contract"

    def evaluate(
        self,
        actor: Actor | None,
        action: ProposedAction,
        incident: Incident | None = None,
        approval: Approval | None = None,
    ) -> PolicyCheck:
        if actor is None:
            return self._deny("Authenticated actor is required.")
        if actor.role is not ActorRole.SERVICE_DESK_AGENT:
            return self._deny("Actor role is not authorized for incident actions.")

        allowed_fields = (
            CREATE_FIELDS if action.action_type is ActionType.CREATE_INCIDENT else UPDATE_FIELDS
        )
        unknown = sorted(set(action.fields) - allowed_fields)
        if unknown:
            return self._deny(f"Unknown fields are not permitted: {', '.join(unknown)}.")
        if _contains_secret(action.fields) or _contains_secret(action.reason):
            return self._deny("Secret-bearing input is not permitted.")

        if action.action_type is ActionType.UPDATE_INCIDENT and incident is None:
            return self._deny("An existing incident is required for updates.")
        if incident is not None and action.incident_id != incident.incident_id:
            return self._deny("Action incident_id does not match the existing incident.")

        value_error = self._validate_values(action, incident)
        if value_error:
            return self._deny(value_error)

        if self._requires_approval(action):
            if approval is None:
                return self._deny("Human approval is required for this action.")
            if approval.approver.actor_id == actor.actor_id:
                return self._deny("Self-approval is not permitted.")
            if not self._approval_matches(action, approval):
                return self._deny("Approval does not match the proposed action.")

        return PolicyCheck(self.name, True, "Action contract passed.")

    def _validate_values(self, action: ProposedAction, incident: Incident | None) -> str | None:
        for field_name in ("short_description", "description", "reason"):
            if field_name in action.fields and (not isinstance(action.fields[field_name], str) or not action.fields[field_name].strip()):
                return f"{field_name} must be a non-empty string."
        if "work_notes" in action.fields and (
            not isinstance(action.fields["work_notes"], str)
            or not action.fields["work_notes"].strip()
        ):
            return "work_notes must be a non-empty string."
        if "priority" in action.fields:
            try:
                priority = _coerce_enum(action.fields["priority"], IncidentPriority, "priority")
            except ValueError as exc:
                return str(exc)
            if priority in HIGH_IMPACT_PRIORITIES and incident is None and action.action_type is ActionType.UPDATE_INCIDENT:
                return "An existing incident is required for priority changes."
        if "state" in action.fields:
            try:
                new_state = _coerce_enum(action.fields["state"], IncidentState, "state")
            except ValueError as exc:
                return str(exc)
            if incident is None:
                return "An existing incident is required for state changes."
            if new_state not in ALLOWED_TRANSITIONS[incident.state]:
                return f"Invalid state transition: {incident.state.value} to {new_state.value}."
        return None

    def _requires_approval(self, action: ProposedAction) -> bool:
        if "assignment_group" in action.fields or "state" in action.fields:
            return True
        if "priority" in action.fields:
            try:
                return _coerce_enum(action.fields["priority"], IncidentPriority, "priority") in HIGH_IMPACT_PRIORITIES
            except ValueError:
                return False
        return False

    @staticmethod
    def _approval_matches(action: ProposedAction, approval: Approval) -> bool:
        return (
            approval.action_id == action.action_id
            and approval.incident_id == action.incident_id
            and dict(approval.approved_fields) == dict(action.fields)
        )

    def _deny(self, detail: str) -> PolicyCheck:
        return PolicyCheck(self.name, False, detail)
