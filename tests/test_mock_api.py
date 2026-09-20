"""Behavior tests for the local ServiceNow incident mock.

The mock enforces *integrity* (does this record exist, is this a real field,
is this a legal value).  It deliberately does not enforce *authorization*;
that remains the job of ``policies.action_contracts.ActionPolicy``.
"""

import pytest

from policies.action_contracts import IncidentPriority, IncidentState
from servicenow.mock_api import (
    IncidentNotFoundError,
    IncidentWriteError,
    MockServiceNowAPI,
)


def _api() -> MockServiceNowAPI:
    return MockServiceNowAPI()


def _created(api: MockServiceNowAPI) -> str:
    return api.create({"short_description": "VPN unavailable"}).incident_id


def test_create_assigns_deterministic_sequential_ids() -> None:
    api = _api()

    first = api.create({"short_description": "VPN unavailable"})
    second = api.create({"short_description": "Account locked"})

    assert first.incident_id == "INC0000001"
    assert second.incident_id == "INC0000002"


def test_two_fresh_mocks_produce_identical_ids() -> None:
    assert _created(_api()) == _created(_api())


def test_create_stores_retrievable_record_with_defaults() -> None:
    api = _api()

    incident_id = api.create(
        {"short_description": "VPN unavailable", "category": "network"}
    ).incident_id
    stored = api.get(incident_id)

    assert stored.short_description == "VPN unavailable"
    assert stored.category == "network"
    assert stored.priority is IncidentPriority.P3
    assert stored.state is IncidentState.NEW
    assert stored.work_notes == ()


def test_create_rejects_unknown_fields() -> None:
    with pytest.raises(IncidentWriteError, match="caller_manager"):
        _api().create({"short_description": "VPN unavailable", "caller_manager": "x"})


def test_create_requires_short_description() -> None:
    with pytest.raises(IncidentWriteError, match="short_description"):
        _api().create({"description": "No summary supplied"})


def test_create_rejects_invalid_enum_value() -> None:
    with pytest.raises(IncidentWriteError, match="priority"):
        _api().create({"short_description": "VPN unavailable", "priority": "P9"})


def test_create_rejects_work_notes_as_a_create_field() -> None:
    with pytest.raises(IncidentWriteError, match="work_notes"):
        _api().create({"short_description": "VPN unavailable", "work_notes": "note"})


def test_get_raises_for_unknown_incident() -> None:
    with pytest.raises(IncidentNotFoundError, match="INC0009999"):
        _api().get("INC0009999")


def test_update_returns_before_and_after_for_changed_fields_only() -> None:
    api = _api()
    incident_id = _created(api)

    change = api.update(incident_id, {"category": "network", "urgency": "high"})

    assert change.incident_id == incident_id
    assert change.changed_fields == ("category", "urgency")
    assert change.before == {"category": "", "urgency": ""}
    assert change.after == {"category": "network", "urgency": "high"}


def test_update_records_no_change_when_value_is_unchanged() -> None:
    api = _api()
    incident_id = api.create(
        {"short_description": "VPN unavailable", "category": "network"}
    ).incident_id

    change = api.update(incident_id, {"category": "network"})

    assert change.changed_fields == ()
    assert change.before == {}
    assert change.after == {}


def test_update_appends_work_notes_instead_of_replacing_them() -> None:
    api = _api()
    incident_id = _created(api)

    api.update(incident_id, {"work_notes": "Checked VPN concentrator"})
    change = api.update(incident_id, {"work_notes": "Escalated to network team"})

    assert api.get(incident_id).work_notes == (
        "Checked VPN concentrator",
        "Escalated to network team",
    )
    assert change.before == {"work_notes": ("Checked VPN concentrator",)}


def test_update_persists_state_and_priority_changes() -> None:
    api = _api()
    incident_id = _created(api)

    api.update(incident_id, {"state": "in_progress", "priority": "P1"})
    stored = api.get(incident_id)

    assert stored.state is IncidentState.IN_PROGRESS
    assert stored.priority is IncidentPriority.P1


def test_update_does_not_enforce_state_transitions() -> None:
    """Transition legality is a policy decision, not a storage guarantee."""
    api = _api()
    incident_id = _created(api)

    api.update(incident_id, {"state": "closed"})

    assert api.get(incident_id).state is IncidentState.CLOSED


def test_update_raises_for_unknown_incident() -> None:
    with pytest.raises(IncidentNotFoundError, match="INC0009999"):
        _api().update("INC0009999", {"category": "network"})


def test_update_rejects_fields_that_cannot_be_updated() -> None:
    api = _api()
    incident_id = _created(api)

    with pytest.raises(IncidentWriteError, match="short_description"):
        api.update(incident_id, {"short_description": "Rewritten summary"})


def test_rejected_update_leaves_the_record_untouched() -> None:
    api = _api()
    incident_id = api.create(
        {"short_description": "VPN unavailable", "category": "network"}
    ).incident_id

    with pytest.raises(IncidentWriteError):
        api.update(incident_id, {"urgency": "high", "priority": "P9"})

    stored = api.get(incident_id)
    assert stored.urgency == ""
    assert stored.category == "network"


def test_returned_records_do_not_share_state_with_the_store() -> None:
    api = _api()
    incident_id = _created(api)

    fields = {"category": "network"}
    api.update(incident_id, fields)
    fields["category"] = "mutated after the call"

    assert api.get(incident_id).category == "network"


def test_change_record_serializes_for_audit_logging() -> None:
    api = _api()
    incident_id = _created(api)

    record = api.update(incident_id, {"category": "network"}).as_dict()

    assert record == {
        "incident_id": incident_id,
        "changed_fields": ["category"],
        "before": {"category": ""},
        "after": {"category": "network"},
    }
