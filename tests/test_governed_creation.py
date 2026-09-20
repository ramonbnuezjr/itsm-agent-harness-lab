"""Behavior tests for governed incident creation.

Identity is supplied by the harness, never by the model.  Every attempt --
allowed, denied, completed, or failed -- produces exactly one audit event, and
a denied or failed attempt leaves the incident store unchanged.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pytest

from harness.actions import ActionOutcome, GovernedActionExecutor
from harness.logger import AuditLogger
from harness.tools import build_create_incident_tool
from policies.action_contracts import (
    CREATE_FIELDS,
    Actor,
    ActorRole,
    Approval,
    IncidentPriority,
)
from servicenow.mock_api import ChangeRecord, IncidentWriteError, MockServiceNowAPI


def _executor(
    tmp_path: Path,
    *,
    actor: Actor | None = None,
    repository: Any | None = None,
) -> GovernedActionExecutor:
    return GovernedActionExecutor(
        actor=actor if actor is not None else Actor("agent-1", ActorRole.SERVICE_DESK_AGENT),
        repository=repository if repository is not None else MockServiceNowAPI(),
        audit_logger=AuditLogger(tmp_path / "audit.jsonl"),
        action_id_factory=lambda: "ACT-1",
    )


def _events(tmp_path: Path) -> list[dict[str, Any]]:
    log = tmp_path / "audit.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def _arguments(**overrides: Any) -> dict[str, Any]:
    arguments = {
        "short_description": "VPN unavailable",
        "description": "One user cannot connect to VPN",
        "reason": "Create the incident from the user report",
    }
    arguments.update(overrides)
    return arguments


def test_allowed_creation_stores_the_incident(tmp_path: Path) -> None:
    repository = MockServiceNowAPI()
    executor = _executor(tmp_path, repository=repository)

    result = executor.create_incident(_arguments())

    assert result.outcome is ActionOutcome.COMPLETED
    assert result.incident_id == "INC0000001"
    assert result.policy_check is not None and result.policy_check.passed
    assert repository.get("INC0000001").short_description == "VPN unavailable"


def test_completed_attempt_writes_one_audit_event_with_evidence(tmp_path: Path) -> None:
    executor = _executor(tmp_path)

    result = executor.create_incident(_arguments())
    events = _events(tmp_path)

    assert len(events) == 1
    event = events[0]
    assert event["event_id"] == result.audit_event_id
    assert event["outcome"] == "completed"
    assert event["action_id"] == "ACT-1"
    assert event["action_type"] == "create_incident"
    assert event["actor_id"] == "agent-1"
    assert event["actor_role"] == "service_desk_agent"
    assert event["incident_id"] == "INC0000001"
    assert event["created"]["short_description"] == "VPN unavailable"
    assert event["policy_checks"][0]["passed"] is True


def test_unauthenticated_actor_is_denied(tmp_path: Path) -> None:
    repository = MockServiceNowAPI()
    executor = GovernedActionExecutor(
        actor=None,
        repository=repository,
        audit_logger=AuditLogger(tmp_path / "audit.jsonl"),
        action_id_factory=lambda: "ACT-1",
    )

    result = executor.create_incident(_arguments())

    assert result.outcome is ActionOutcome.DENIED
    assert result.incident_id is None
    assert _events(tmp_path)[0]["outcome"] == "denied"
    with pytest.raises(LookupError):
        repository.get("INC0000001")


def test_wrong_role_is_denied(tmp_path: Path) -> None:
    executor = _executor(tmp_path, actor=Actor("manager-1", ActorRole.INCIDENT_MANAGER))

    result = executor.create_incident(_arguments())

    assert result.outcome is ActionOutcome.DENIED
    assert "role" in result.detail.lower()


def test_unknown_field_is_denied_and_audited(tmp_path: Path) -> None:
    repository = MockServiceNowAPI()
    executor = _executor(tmp_path, repository=repository)

    result = executor.create_incident(_arguments(caller_manager="someone"))

    assert result.outcome is ActionOutcome.DENIED
    assert "caller_manager" in result.detail
    assert _events(tmp_path)[0]["fields"]["caller_manager"] == "someone"


def test_invalid_priority_is_denied(tmp_path: Path) -> None:
    executor = _executor(tmp_path)

    result = executor.create_incident(_arguments(priority="P9"))

    assert result.outcome is ActionOutcome.DENIED
    assert "priority" in result.detail


def test_missing_reason_is_denied_rather_than_raised(tmp_path: Path) -> None:
    executor = _executor(tmp_path)
    arguments = _arguments()
    del arguments["reason"]

    result = executor.create_incident(arguments)

    assert result.outcome is ActionOutcome.DENIED
    assert result.policy_check is None
    assert _events(tmp_path)[0]["outcome"] == "denied"


def test_secret_bearing_field_value_is_never_written_to_the_audit_log(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path)

    result = executor.create_incident(
        _arguments(description="The user password is hunter2-correct-horse")
    )
    raw_log = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")

    assert result.outcome is ActionOutcome.DENIED
    assert "hunter2-correct-horse" not in raw_log
    assert _events(tmp_path)[0]["fields"]["description"] == "[redacted]"


def test_secret_bearing_reason_is_redacted_in_the_audit_log(tmp_path: Path) -> None:
    executor = _executor(tmp_path)

    result = executor.create_incident(
        _arguments(reason="Rotate the api_key sk-live-000111222")
    )
    raw_log = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")

    assert result.outcome is ActionOutcome.DENIED
    assert "sk-live-000111222" not in raw_log
    assert _events(tmp_path)[0]["reason"] == "[redacted]"


def test_high_impact_priority_is_denied_without_approval(tmp_path: Path) -> None:
    repository = MockServiceNowAPI()
    executor = _executor(tmp_path, repository=repository)

    result = executor.create_incident(_arguments(priority="P1"))

    assert result.outcome is ActionOutcome.DENIED
    assert "approval" in result.detail.lower()
    with pytest.raises(LookupError):
        repository.get("INC0000001")


def test_high_impact_priority_succeeds_with_a_bound_approval(tmp_path: Path) -> None:
    executor = _executor(tmp_path)
    arguments = _arguments(priority="P1")
    approval = Approval(
        approval_id="APR-1",
        approver=Actor("manager-1", ActorRole.INCIDENT_MANAGER),
        action_id="ACT-1",
        incident_id=None,
        approved_fields={
            name: value for name, value in arguments.items() if name in CREATE_FIELDS
        },
        approved_at=datetime.now(timezone.utc),
    )

    result = executor.create_incident(arguments, approval=approval)

    assert result.outcome is ActionOutcome.COMPLETED
    assert _events(tmp_path)[0]["approval_id"] == "APR-1"


def test_self_approval_is_denied(tmp_path: Path) -> None:
    executor = _executor(tmp_path)
    arguments = _arguments(priority="P1")
    approval = Approval(
        approval_id="APR-1",
        approver=Actor("agent-1", ActorRole.INCIDENT_MANAGER),
        action_id="ACT-1",
        incident_id=None,
        approved_fields={
            name: value for name, value in arguments.items() if name in CREATE_FIELDS
        },
        approved_at=datetime.now(timezone.utc),
    )

    result = executor.create_incident(arguments, approval=approval)

    assert result.outcome is ActionOutcome.DENIED
    assert "self-approval" in result.detail.lower()


class _FailingRepository:
    """Stand-in whose writes always fail after policy has allowed the action."""

    def create(self, fields: Mapping[str, Any]) -> Any:
        raise IncidentWriteError("incident table unavailable")

    def get(self, incident_id: str) -> Any:
        raise LookupError(incident_id)

    def update(self, incident_id: str, fields: Mapping[str, Any]) -> ChangeRecord:
        raise IncidentWriteError("incident table unavailable")


def test_execution_failure_after_an_allowed_policy_is_audited_as_failed(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, repository=_FailingRepository())

    result = executor.create_incident(_arguments())
    event = _events(tmp_path)[0]

    assert result.outcome is ActionOutcome.FAILED
    assert result.incident_id is None
    assert event["outcome"] == "failed"
    assert event["policy_checks"][0]["passed"] is True
    assert "incident table unavailable" in event["detail"]


def test_storage_rejection_of_a_policy_allowed_action_is_audited_as_failed(
    tmp_path: Path,
) -> None:
    """short_description is required by storage but not yet checked by policy."""
    executor = _executor(tmp_path)
    arguments = _arguments()
    del arguments["short_description"]

    result = executor.create_incident(arguments)

    assert result.outcome is ActionOutcome.FAILED
    assert "short_description" in result.detail


def test_create_incident_tool_exposes_a_strict_schema_of_create_fields_only(
    tmp_path: Path,
) -> None:
    tool = build_create_incident_tool(_executor(tmp_path))
    schema = tool.as_openai_tool()

    assert schema["name"] == "create_incident"
    assert schema["strict"] is True
    assert schema["parameters"]["additionalProperties"] is False
    assert set(schema["parameters"]["properties"]) == set(CREATE_FIELDS) | {"reason"}
    assert set(schema["parameters"]["required"]) == set(CREATE_FIELDS) | {"reason"}
    assert schema["parameters"]["properties"]["priority"]["enum"] == [
        member.value for member in IncidentPriority
    ] + [None]


def test_tool_schema_does_not_let_the_model_supply_identity(tmp_path: Path) -> None:
    properties = build_create_incident_tool(_executor(tmp_path)).parameters["properties"]

    assert "actor_id" not in properties
    assert "role" not in properties
    assert "approval_id" not in properties
    assert "action_id" not in properties


def test_tool_returns_a_structured_denial_instead_of_raising(tmp_path: Path) -> None:
    tool = build_create_incident_tool(_executor(tmp_path))

    response = tool.invoke(_arguments(caller_manager="someone"))

    assert response["outcome"] == "denied"
    assert response["incident_id"] is None
    assert response["audit_event_id"]


def test_tool_drops_null_optional_fields_before_proposing_the_action(
    tmp_path: Path,
) -> None:
    tool = build_create_incident_tool(_executor(tmp_path))

    response = tool.invoke(
        _arguments(category=None, impact=None, urgency=None, assignment_group=None, priority=None)
    )

    assert response["outcome"] == "completed"
    assert "category" not in _events(tmp_path)[0]["fields"]
