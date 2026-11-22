"""Teaching assistant records (systems.primary.domain.staff.teaching_assistants)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.staff.teaching_assistants import (
    teaching_assistants as TA,
)


def _ta(first="Tia", last="Assist", **extra):
    return TA.create({"first_name": first, "last_name": last, **extra})


def test_roles_are_primary_ta_roles_with_labels():
    assert set(TA.ROLE_LABELS) == set(TA.ROLES)
    assert TA.ROLE_LABELS["HLTA"] == "Higher Level Teaching Assistant"
    assert "EYFS TA" in TA.ROLES and "SEND TA" in TA.ROLES


# ── Create ───────────────────────────────────────────────────────────

def test_create_defaults_and_read_back():
    t = _ta(email=" tia@school.example ", phone="01234 567890", assigned_class=" 2B ",
            hours_per_week="32.5", start_date="2024-09-01", notes=" 1:1 support ")
    assert (t.full_name, t.email, t.phone, t.assigned_class) == (
        "Tia Assist", "tia@school.example", "01234 567890", "2B")
    assert (t.role, t.employment_type, t.hours_per_week) == ("TA", "permanent", 32.5)
    assert (t.dbs_checked, t.safeguarding_trained, t.is_active) == (False, False, True)
    assert (t.start_date, t.end_date, t.notes) == ("2024-09-01", None, "1:1 support")
    assert TA.get(t.ta_id) == t
    assert TA.get(999) is None


def test_employment_type_is_case_insensitive():
    assert _ta(employment_type="Fixed_Term").employment_type == "fixed_term"


def test_inactive_on_create():
    assert _ta(is_active=False).is_active is False


@pytest.mark.parametrize("bad, msg", [
    ({"first_name": " "}, "First name is required"),
    ({"last_name": ""}, "Last name is required"),
    ({"first_name": "x" * 61}, "60 characters or fewer"),
    ({"email": "not-an-email"}, "Email is not a valid address"),
    ({"phone": "call me"}, "Phone contains invalid characters"),
    ({"role": "Teacher"}, "Role must be one of"),
    ({"employment_type": "zero_hours"}, "Employment type must be one of"),
    ({"hours_per_week": "lots"}, "Hours per week must be a number"),
    ({"hours_per_week": 61}, "Hours per week must be between 0 and 60"),
    ({"hours_per_week": -1}, "Hours per week must be between 0 and 60"),
    ({"start_date": "1/9/2024"}, "Start date must be YYYY-MM-DD"),
    ({"end_date": "2025/07/20"}, "End date must be YYYY-MM-DD"),
    ({"start_date": "2024-09-01", "end_date": "2024-08-31"}, "End date cannot be before"),
])
def test_create_refusals(bad, msg):
    data = {"first_name": "Tia", "last_name": "Assist", **bad}
    with pytest.raises(TA.ValidationError, match=msg):
        TA.create(data)
    assert TA.list_all() == []


def test_duplicate_email_refused():
    first = _ta(email="ta@school.example")
    with pytest.raises(TA.ValidationError, match=f"already exists \\(#{first.ta_id}\\)"):
        _ta("Bea", "Other", email="ta@school.example")
    # TAs without an e-mail never clash
    assert _ta("No", "Email").email is None and _ta("Also", "None").email is None


# ── Update / toggle / delete ─────────────────────────────────────────

def test_update_merges_and_validates():
    t = _ta(role="HLTA", hours_per_week=30)
    up = TA.update(t.ta_id, {"assigned_class": "R1", "dbs_checked": True})
    assert (up.assigned_class, up.dbs_checked, up.role, up.hours_per_week) == (
        "R1", True, "HLTA", 30.0)
    with pytest.raises(TA.ValidationError, match="No TA #999"):
        TA.update(999, {"notes": "x"})
    with pytest.raises(TA.ValidationError, match="Role must be one of"):
        TA.update(t.ta_id, {"role": "Head"})
    other = _ta("Bea", "Other", email="bea@school.example")
    with pytest.raises(TA.ValidationError, match="Another TA with email"):
        TA.update(t.ta_id, {"email": "bea@school.example"})
    assert TA.update(other.ta_id, {"email": "bea@school.example"}).email == "bea@school.example"


def test_toggle_active_and_delete():
    t = _ta()
    assert TA.toggle_active(t.ta_id).is_active is False
    assert TA.toggle_active(t.ta_id).is_active is True
    with pytest.raises(TA.ValidationError, match="No TA #999"):
        TA.toggle_active(999)
    assert TA.delete(t.ta_id) is True
    assert TA.get(t.ta_id) is None
    assert TA.delete(t.ta_id) is False


# ── Listing ──────────────────────────────────────────────────────────

def test_list_filters_and_order():
    a = _ta("Zoe", "baker", role="HLTA", dbs_checked=True, safeguarding_trained=True,
            assigned_class="3A")
    b = _ta("Amy", "Baker", role="SEND TA", email="amy@school.example")
    c = _ta("Cal", "Adams", is_active=False, dbs_checked=True)
    ids = lambda rows: [x.ta_id for x in rows]  # noqa: E731
    # surname then first name, case-insensitively
    assert ids(TA.list_all()) == [c.ta_id, b.ta_id, a.ta_id]
    assert ids(TA.list_all(role="HLTA")) == [a.ta_id]
    assert ids(TA.list_all(active_only=True)) == [b.ta_id, a.ta_id]
    assert ids(TA.list_all(search="amy@")) == [b.ta_id]
    assert ids(TA.list_all(search="3a")) == [a.ta_id]
    assert ids(TA.list_all(needs_dbs=True)) == [b.ta_id]
    assert ids(TA.list_all(needs_dbs=False)) == [c.ta_id, a.ta_id]
    assert ids(TA.list_all(needs_safeguarding=True)) == [c.ta_id, b.ta_id]
    assert ids(TA.list_all(needs_safeguarding=False)) == [a.ta_id]
    with pytest.raises(TA.ValidationError, match="Role filter"):
        TA.list_all(role="Teacher")


# ── Summary ──────────────────────────────────────────────────────────

def test_summary_empty():
    sm = TA.summary()
    assert (sm["total"], sm["active"], sm["total_hours_per_week"]) == (0, 0, 0.0)
    assert sm["by_role"] == {r: 0 for r in TA.ROLES}


def test_summary_counts_active_only():
    _ta("A", "A", role="HLTA", hours_per_week=32.5, dbs_checked=True,
        safeguarding_trained=True)
    _ta("B", "B", hours_per_week=20, dbs_checked=True)
    _ta("C", "C", role="EYFS TA")
    _ta("D", "D", hours_per_week=40, is_active=False)
    sm = TA.summary()
    assert (sm["total"], sm["active"]) == (4, 3)
    assert (sm["needs_dbs"], sm["needs_safeguarding"]) == (1, 2)
    assert sm["total_hours_per_week"] == 52.5
    assert sm["by_role"] == {**{r: 0 for r in TA.ROLES}, "HLTA": 1, "TA": 1, "EYFS TA": 1}
