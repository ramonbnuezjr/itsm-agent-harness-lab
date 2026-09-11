from datetime import datetime, timezone

import pytest

from policies.action_contracts import (
    ActionPolicy,
    ActionType,
    Actor,
    ActorRole,
    Approval,
    Incident,
    IncidentState,
    ProposedAction,
)


def _actor(actor_id: str = "agent-1") -> Actor:
    return Actor(actor_id, ActorRole.SERVICE_DESK_AGENT)


def _incident() -> Incident:
    return Incident("INC1001", "VPN unavailable")


def _approval(action: ProposedAction, approver_id: str = "manager-1") -> Approval:
    return Approval(
        approval_id="APR-1",
        approver=Actor(approver_id, ActorRole.INCIDENT_MANAGER),
        action_id=action.action_id,
        incident_id=action.incident_id,
        approved_fields=action.fields,
        approved_at=datetime.now(timezone.utc),
    )


def test_create_action_passes_for_authenticated_service_desk_agent() -> None:
    action = ProposedAction(
        "ACT-1",
        ActionType.CREATE_INCIDENT,
        {"short_description": "VPN unavailable", "description": "Synthetic incident"},
        "Create the incident from the user report",
    )

    check = ActionPolicy().evaluate(_actor(), action)

    assert check.passed


def test_missing_actor_is_denied() -> None:
    action = ProposedAction("ACT-1", ActionType.CREATE_INCIDENT, {}, "Create incident")

    check = ActionPolicy().evaluate(None, action)

    assert not check.passed
    assert "actor" in check.detail.lower()


def test_unknown_fields_are_denied() -> None:
    action = ProposedAction(
        "ACT-1", ActionType.CREATE_INCIDENT, {"caller_password": "secret"}, "Create incident"
    )

    check = ActionPolicy().evaluate(_actor(), action)

    assert not check.passed
    assert "unknown" in check.detail.lower()


def test_secret_bearing_input_is_denied_even_in_an_allowed_field() -> None:
    action = ProposedAction(
        "ACT-1",
        ActionType.CREATE_INCIDENT,
        {"description": "The password is hunter2"},
        "Create incident",
    )

    check = ActionPolicy().evaluate(_actor(), action)

    assert not check.passed
    assert "secret" in check.detail.lower()


def test_secret_bearing_reason_is_denied() -> None:
    action = ProposedAction(
        "ACT-1",
        ActionType.CREATE_INCIDENT,
        {"short_description": "VPN unavailable"},
        "Use the user's API key to investigate",
    )

    check = ActionPolicy().evaluate(_actor(), action)

    assert not check.passed
    assert "secret" in check.detail.lower()


def test_low_risk_work_note_update_does_not_require_approval() -> None:
    action = ProposedAction(
        "ACT-2",
        ActionType.UPDATE_INCIDENT,
        {"work_notes": "Contacted the user; awaiting a retest."},
        "Record troubleshooting progress",
        incident_id="INC1001",
    )

    check = ActionPolicy().evaluate(_actor(), action, _incident())

    assert check.passed


def test_assignment_update_requires_matching_non_self_approval() -> None:
    action = ProposedAction(
        "ACT-3",
        ActionType.UPDATE_INCIDENT,
        {"assignment_group": "network-support"},
        "Route the incident to the network team",
        incident_id="INC1001",
    )

    assert not ActionPolicy().evaluate(_actor(), action, _incident()).passed
    assert ActionPolicy().evaluate(_actor(), action, _incident(), _approval(action)).passed
    assert not ActionPolicy().evaluate(_actor(), action, _incident(), _approval(action, "agent-1")).passed


def test_high_priority_update_requires_exact_approval_scope() -> None:
    action = ProposedAction(
        "ACT-4",
        ActionType.UPDATE_INCIDENT,
        {"priority": "P1"},
        "Escalate based on impact and urgency",
        incident_id="INC1001",
    )
    mismatched = Approval(
        approval_id="APR-2",
        approver=Actor("manager-1", ActorRole.INCIDENT_MANAGER),
        action_id=action.action_id,
        incident_id=action.incident_id,
        approved_fields={"priority": "P2"},
        approved_at=datetime.now(timezone.utc),
    )

    check = ActionPolicy().evaluate(_actor(), action, _incident(), mismatched)

    assert not check.passed
    assert "match" in check.detail.lower()


def test_invalid_state_transition_is_denied() -> None:
    action = ProposedAction(
        "ACT-5",
        ActionType.UPDATE_INCIDENT,
        {"state": IncidentState.CLOSED},
        "Close the incident",
        incident_id="INC1001",
    )

    check = ActionPolicy().evaluate(_actor(), action, _incident())

    assert not check.passed
    assert "transition" in check.detail.lower()


def test_contracts_reject_invalid_action_shape() -> None:
    with pytest.raises(ValueError, match="incident_id"):
        ProposedAction("ACT-6", ActionType.UPDATE_INCIDENT, {}, "Update")

    with pytest.raises(ValueError, match="timezone-aware"):
        Approval(
            "APR-3",
            Actor("manager-1", ActorRole.INCIDENT_MANAGER),
            "ACT-1",
            None,
            {},
            datetime.now(),
        )
