"""Deterministic, offline stand-in for the ServiceNow incident table.

The mock exists so governed write paths can be exercised repeatedly without
credentials, network access, or real ticket data.  It enforces *integrity*:
the record must exist, the field must be real, the value must be legal, and a
rejected write must leave no trace.  It deliberately does not enforce
*authorization* -- identity, role, approval binding, and legal state
transitions stay in :mod:`policies.action_contracts` so that removing the
policy layer breaks policy tests rather than silently passing here.

Field names and enumerations are imported from the action contracts to keep a
single vocabulary for an incident across policy and storage.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping, Protocol

from policies.action_contracts import (
    CREATE_FIELDS,
    UPDATE_FIELDS,
    Incident,
    IncidentPriority,
    IncidentState,
)

ID_PREFIX = "INC"
ID_DIGITS = 7
ENUM_FIELDS: dict[str, type[Enum]] = {
    "priority": IncidentPriority,
    "state": IncidentState,
}
JOURNAL_FIELDS = frozenset({"work_notes"})
REQUIRED_CREATE_FIELDS = ("short_description",)


class IncidentWriteError(ValueError):
    """Raised when a write is malformed for the incident table."""


class IncidentNotFoundError(LookupError):
    """Raised when a referenced incident does not exist."""


def _jsonable(value: object) -> object:
    """Convert a stored value into a JSON-serializable equivalent.

    Args:
        value: A stored incident field value.

    Returns:
        The value as a primitive, list, or dictionary suitable for audit logs.
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (tuple, list, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class ChangeRecord:
    """Before and after values for the fields a single write actually changed."""

    incident_id: str
    before: Mapping[str, Any]
    after: Mapping[str, Any]
    changed_fields: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Render the change as an audit-log-safe dictionary.

        Returns:
            A dictionary containing only the fields this write changed.
        """
        return {
            "incident_id": self.incident_id,
            "changed_fields": list(self.changed_fields),
            "before": {name: _jsonable(value) for name, value in self.before.items()},
            "after": {name: _jsonable(value) for name, value in self.after.items()},
        }


class IncidentRepository(Protocol):
    """Storage boundary the harness uses to reach an incident system."""

    def create(self, fields: Mapping[str, Any]) -> Incident:
        """Create an incident and return the stored record."""

    def get(self, incident_id: str) -> Incident:
        """Return the stored incident with the given identifier."""

    def update(self, incident_id: str, fields: Mapping[str, Any]) -> ChangeRecord:
        """Apply a field update and return what changed."""


class MockServiceNowAPI:
    """In-memory incident table with deterministic identifiers."""

    def __init__(self, *, start_sequence: int = 1) -> None:
        """Initialize an empty incident table.

        Args:
            start_sequence: First numeric suffix used for generated record IDs.

        Raises:
            ValueError: If ``start_sequence`` is not positive.
        """
        if start_sequence < 1:
            raise ValueError("start_sequence must be at least 1")
        self._incidents: dict[str, Incident] = {}
        self._sequence = start_sequence

    def create(self, fields: Mapping[str, Any]) -> Incident:
        """Create a new incident record.

        Args:
            fields: Field values drawn from
                :data:`policies.action_contracts.CREATE_FIELDS`.

        Returns:
            The stored :class:`~policies.action_contracts.Incident`.

        Raises:
            IncidentWriteError: If a field is unknown, missing, or illegal.
        """
        self._reject_unknown(fields, CREATE_FIELDS, "created")
        for name in REQUIRED_CREATE_FIELDS:
            if name not in fields:
                raise IncidentWriteError(f"{name} is required to create an incident")
        values = self._coerce(fields)
        incident_id = self._next_incident_id()
        try:
            incident = Incident(incident_id=incident_id, **values)
        except ValueError as exc:
            raise IncidentWriteError(str(exc)) from exc
        self._incidents[incident_id] = incident
        return incident

    def get(self, incident_id: str) -> Incident:
        """Return a stored incident.

        Args:
            incident_id: Identifier returned by :meth:`create`.

        Returns:
            The stored :class:`~policies.action_contracts.Incident`.

        Raises:
            IncidentNotFoundError: If no such incident exists.
        """
        try:
            return self._incidents[incident_id]
        except KeyError as exc:
            raise IncidentNotFoundError(f"Incident {incident_id} does not exist") from exc

    def update(self, incident_id: str, fields: Mapping[str, Any]) -> ChangeRecord:
        """Apply a guarded field update to an existing incident.

        Every field is validated before any value is stored, so a rejected
        update leaves the record untouched.  Journal fields such as
        ``work_notes`` are appended to rather than replaced.

        Args:
            incident_id: Identifier of the incident to update.
            fields: Field values drawn from
                :data:`policies.action_contracts.UPDATE_FIELDS`.

        Returns:
            A :class:`ChangeRecord` describing only the fields that changed.

        Raises:
            IncidentNotFoundError: If no such incident exists.
            IncidentWriteError: If a field is unknown or illegal.
        """
        incident = self.get(incident_id)
        self._reject_unknown(fields, UPDATE_FIELDS, "updated")
        values = self._coerce(fields)

        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
        changes: dict[str, Any] = {}
        for name in sorted(values):
            current = getattr(incident, name)
            if name in JOURNAL_FIELDS:
                new_value: Any = tuple(current) + (values[name],)
            else:
                new_value = values[name]
                if current == new_value:
                    continue
            before[name] = current
            after[name] = new_value
            changes[name] = new_value

        if changes:
            self._incidents[incident_id] = replace(incident, **changes)
        return ChangeRecord(
            incident_id=incident_id,
            before=before,
            after=after,
            changed_fields=tuple(sorted(changes)),
        )

    def _next_incident_id(self) -> str:
        """Return the next deterministic record identifier."""
        incident_id = f"{ID_PREFIX}{self._sequence:0{ID_DIGITS}d}"
        self._sequence += 1
        return incident_id

    @staticmethod
    def _reject_unknown(
        fields: Mapping[str, Any], allowed: frozenset[str], verb: str
    ) -> None:
        """Raise when any supplied field is outside the allowed set.

        Args:
            fields: Supplied field values.
            allowed: Field names the operation accepts.
            verb: Past-tense operation name used in the error message.

        Raises:
            IncidentWriteError: If ``fields`` is not a mapping or names an
                unsupported field.
        """
        if not isinstance(fields, Mapping):
            raise IncidentWriteError("fields must be a mapping")
        unknown = sorted(set(fields) - allowed)
        if unknown:
            raise IncidentWriteError(
                f"Fields cannot be {verb} on an incident: {', '.join(unknown)}"
            )

    @staticmethod
    def _coerce(fields: Mapping[str, Any]) -> dict[str, Any]:
        """Validate and normalize supplied field values.

        Args:
            fields: Supplied field values.

        Returns:
            A new dictionary of validated values, detached from the caller's
            mapping so later caller mutation cannot reach the store.

        Raises:
            IncidentWriteError: If any value has the wrong type or is not a
                legal member of its enumeration.
        """
        values: dict[str, Any] = {}
        for name in sorted(fields):
            value = fields[name]
            enum_type = ENUM_FIELDS.get(name)
            if enum_type is not None:
                try:
                    values[name] = enum_type(value)
                except (TypeError, ValueError) as exc:
                    allowed = ", ".join(str(member.value) for member in enum_type)
                    raise IncidentWriteError(
                        f"{name} must be one of: {allowed}"
                    ) from exc
                continue
            if not isinstance(value, str):
                raise IncidentWriteError(f"{name} must be a string")
            if name in JOURNAL_FIELDS or name in REQUIRED_CREATE_FIELDS:
                if not value.strip():
                    raise IncidentWriteError(f"{name} must be a non-empty string")
            values[name] = value
        return values
