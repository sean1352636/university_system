"""Staff Directory (systems.primary.domain.staff.staff)."""

from __future__ import annotations

import re

import pytest

from education_system.systems.primary.domain.staff import staff as S


def _staff(first="Amy", last="Adams", **extra):
    return S.create_staff({"first_name": first, "last_name": last, **extra})


# ── Create + defaults ────────────────────────────────────────────────

def test_create_defaults_id_and_derived_email():
    s = _staff(title="Mrs")
    assert re.fullmatch(r"T\d{7}", s.staff_id)
    assert s.email == f"{s.staff_id.lower()}@primary.sch.uk"
    assert (s.role, s.department, s.employment_status) == ("Teacher", "Other", "Full-time")
    assert s.full_name == "Mrs Amy Adams"
    assert s.is_active is True
    assert (s.is_tutor, s.is_dsl, s.is_examiner) == (False, False, False)
    assert S.get_staff(s.staff_id) == s


def test_create_stores_every_field_and_lowercases_email():
    s = _staff(email="Amy.Adams@School.Example", role="SENCO", department="SEND",
               employment_status="Part-time", work_phone="01234 567890",
               personal_phone="+44 (0)7700-900123", room=" 12 ", start_date="2020-09-01",
               end_date="2030-07-31", is_tutor=1, is_dsl=True, is_examiner="yes",
               qualifications=" QTS ", notes=" note ")
    assert s.email == "amy.adams@school.example"
    assert (s.role, s.department, s.employment_status) == ("SENCO", "SEND", "Part-time")
    assert (s.work_phone, s.personal_phone) == ("01234 567890", "+44 (0)7700-900123")
    assert (s.room, s.qualifications, s.notes) == ("12", "QTS", "note")
    assert (s.start_date, s.end_date) == ("2020-09-01", "2030-07-31")
    assert (s.is_tutor, s.is_dsl, s.is_examiner) == (True, True, True)
    assert s.full_name == "Amy Adams"


def test_generate_staff_email_helper():
    assert S.generate_staff_email("T1234567") == "t1234567@primary.sch.uk"
    assert re.fullmatch(r"T\d{7}", S.generate_staff_id())


def test_roles_and_departments_are_primary_school_values():
    for role in ("Headteacher", "EYFS Lead", "KS1 Lead", "KS2 Lead", "SENCO",
                 "Safeguarding Lead (DSL)", "Midday Supervisor", "Teaching Assistant"):
        assert role in S.ROLES
    for dept in ("EYFS", "KS1", "KS2", "Phonics & Reading", "SEND"):
        assert dept in S.DEPARTMENTS
    for secondary_only in ("Head of Year", "Sixth Form", "Exams Officer"):
        assert secondary_only not in S.ROLES and secondary_only not in S.DEPARTMENTS
    assert S.DEFAULT_ROLE in S.ROLES and S.DEFAULT_DEPARTMENT in S.DEPARTMENTS
    assert "Left" not in S.ACTIVE_STATUSES and "Sabbatical" not in S.ACTIVE_STATUSES
    assert "On Leave" in S.ACTIVE_STATUSES


# ── Validation ───────────────────────────────────────────────────────

@pytest.mark.parametrize("bad, msg", [
    ({"first_name": " "}, "First name is required"),
    ({"last_name": ""}, "Last name is required"),
    ({"role": "Head of Year"}, "Role must be one of"),
    ({"department": "Sixth Form"}, "Department must be one of"),
    ({"employment_status": "Retired"}, "Employment status must be one of"),
    ({"work_phone": "call me"}, "Work phone can only contain"),
    ({"personal_phone": "12"}, "Personal phone can only contain"),
    ({"start_date": "01/09/2020"}, "Start date must be YYYY-MM-DD"),
    ({"end_date": "2020-9-1"}, "End date must be YYYY-MM-DD"),
    ({"start_date": "2021-01-01", "end_date": "2020-12-31"}, "End date cannot be before"),
    ({"line_manager": "T0000000"}, "No staff with id T0000000"),
    ({"email": "not-an-email"}, "Email is not a valid address"),
])
def test_create_refusals(bad, msg):
    data = {"first_name": "Amy", "last_name": "Adams", **bad}
    with pytest.raises(S.ValidationError, match=re.escape(msg)):
        S.create_staff(data)
    assert S.list_staff() == []


def test_duplicate_email_refused_case_insensitively():
    _staff(email="dup@school.example")
    with pytest.raises(S.ValidationError, match="already exists"):
        _staff("Ben", "Brown", email="DUP@school.example")


def test_line_manager_is_normalised_and_cannot_be_self():
    boss = _staff("Hana", "Head", role="Headteacher")
    s = _staff(line_manager=boss.staff_id.lower())
    assert s.line_manager == boss.staff_id
    with pytest.raises(S.ValidationError, match="cannot be the same"):
        S.update_staff(s.staff_id, {"line_manager": s.staff_id})


# ── Get / list / search ──────────────────────────────────────────────

def test_get_missing_and_case_insensitive():
    s = _staff()
    assert S.get_staff(f"  {s.staff_id.lower()} ").staff_id == s.staff_id
    assert S.get_staff("T0000000") is None


def test_list_empty_and_ordering():
    assert S.list_staff() == []
    _staff("Zed", "Brown")
    _staff("Amy", "Brown")
    _staff("Cat", "Adams")
    assert [(s.first_name, s.last_name) for s in S.list_staff()] == [
        ("Cat", "Adams"), ("Amy", "Brown"), ("Zed", "Brown")]


def test_list_filters():
    a = _staff("A", "One", role="Teacher", department="KS1", is_tutor=True)
    b = _staff("B", "Two", role="SENCO", department="SEND", is_dsl=True)
    c = _staff("C", "Three", role="Teacher", department="KS2", employment_status="Left",
               is_examiner=True)
    d = _staff("D", "Four", employment_status="Sabbatical")
    ids = lambda rows: {s.staff_id for s in rows}  # noqa: E731
    assert ids(S.list_staff(role="Teacher")) == {a.staff_id, c.staff_id, d.staff_id}
    assert ids(S.list_staff(department="SEND")) == {b.staff_id}
    assert ids(S.list_staff(employment_status="Left")) == {c.staff_id}
    assert ids(S.list_staff(is_tutor=True)) == {a.staff_id}
    assert ids(S.list_staff(is_dsl=True)) == {b.staff_id}
    assert ids(S.list_staff(is_examiner=True)) == {c.staff_id}
    assert ids(S.list_staff(is_tutor=False)) == {b.staff_id, c.staff_id, d.staff_id}
    assert ids(S.list_staff(active_only=True)) == {a.staff_id, b.staff_id}
    assert ids(S.list_staff(role="Teacher", department="KS2")) == {c.staff_id}


@pytest.mark.parametrize("kw, msg", [
    ({"role": "Dean"}, "Role must be one of"),
    ({"department": "Faculty"}, "Department must be one of"),
    ({"employment_status": "Gone"}, "Status must be one of"),
])
def test_list_rejects_unknown_filter_values(kw, msg):
    with pytest.raises(S.ValidationError, match=msg):
        S.list_staff(**kw)


def test_search_matches_name_id_email_role_department():
    a = _staff("Amy", "Adams", email="amy@school.example")
    b = _staff("Ben", "Brown", role="SENCO", department="SEND")
    assert [s.staff_id for s in S.search_staff("adams")] == [a.staff_id]
    assert [s.staff_id for s in S.search_staff(a.staff_id)] == [a.staff_id]
    assert [s.staff_id for s in S.search_staff("amy@")] == [a.staff_id]
    assert [s.staff_id for s in S.search_staff("senco")] == [b.staff_id]
    assert [s.staff_id for s in S.search_staff("SEND")] == [b.staff_id]
    assert S.search_staff("nobody") == []
    assert len(S.search_staff("  ")) == 2


# ── Update / leave / delete ──────────────────────────────────────────

def test_update_merges_only_given_fields():
    s = _staff(room="4", work_phone="01234 567890")
    out = S.update_staff(s.staff_id, {"role": "KS2 Lead", "department": "KS2"})
    assert (out.role, out.department) == ("KS2 Lead", "KS2")
    assert (out.room, out.work_phone, out.first_name) == ("4", "01234 567890", "Amy")
    assert S.get_staff(s.staff_id).role == "KS2 Lead"


def test_update_refusals():
    a = _staff(email="a@school.example")
    _staff("Ben", "Brown", email="b@school.example")
    with pytest.raises(S.ValidationError, match="No staff with id"):
        S.update_staff("T0000000", {"room": "1"})
    with pytest.raises(S.ValidationError, match="Another staff member already has email"):
        S.update_staff(a.staff_id, {"email": "B@School.example"})
    with pytest.raises(S.ValidationError, match="Role must be one of"):
        S.update_staff(a.staff_id, {"role": "Professor"})
    assert S.get_staff(a.staff_id).email == "a@school.example"


def test_update_email_to_new_unique_value():
    a = _staff(email="a@school.example")
    assert S.update_staff(a.staff_id, {"email": "New@School.Example"}).email == \
        "new@school.example"


def test_mark_left_sets_status_and_end_date():
    s = _staff(start_date="2019-09-01")
    out = S.mark_left(s.staff_id, "2025-07-22")
    assert (out.employment_status, out.end_date, out.is_active) == ("Left", "2025-07-22", False)
    with pytest.raises(S.ValidationError, match="End date cannot be before"):
        S.mark_left(s.staff_id, "2018-01-01")


def test_delete_and_line_manager_set_null():
    boss = _staff("Hana", "Head", role="Headteacher")
    s = _staff(line_manager=boss.staff_id)
    assert S.delete_staff(boss.staff_id.lower()) is True
    assert S.get_staff(boss.staff_id) is None
    assert S.get_staff(s.staff_id).line_manager is None
    assert S.delete_staff(boss.staff_id) is False


def test_reports_to():
    boss = _staff("Hana", "Head", role="Headteacher")
    b = _staff("Ben", "Brown", line_manager=boss.staff_id)
    a = _staff("Amy", "Adams", line_manager=boss.staff_id)
    _staff("Cat", "Cole")
    assert [s.staff_id for s in S.reports_to(boss.staff_id.lower())] == [a.staff_id, b.staff_id]
    assert S.reports_to(a.staff_id) == []


# ── Summary + critical roles ─────────────────────────────────────────

def test_summary_empty_lists_every_critical_role_unfilled():
    sm = S.summary()
    assert (sm.total, sm.active, sm.left, sm.tutors, sm.dsls, sm.examiners) == (0,) * 6
    assert sm.unfilled_critical == list(S._CRITICAL_ROLES)
    assert set(sm.by_role) == set(S.ROLES) and set(sm.by_role.values()) == {0}
    assert set(sm.by_department) == set(S.DEPARTMENTS)
    assert set(sm.by_status) == set(S.EMPLOYMENT_STATUSES)


def test_summary_counts_and_flags_only_active():
    _staff("A", "A", role="Headteacher", is_tutor=True, is_dsl=True)
    _staff("B", "B", role="SENCO", department="SEND", is_examiner=True)
    _staff("C", "C", role="Safeguarding Lead (DSL)", employment_status="Left", is_dsl=True,
           is_tutor=True)
    _staff("D", "D", employment_status="Sabbatical", is_tutor=True)
    sm = S.summary()
    assert (sm.total, sm.active, sm.left) == (4, 2, 1)
    assert (sm.tutors, sm.dsls, sm.examiners) == (1, 1, 1)
    assert sm.by_role["Headteacher"] == 1 and sm.by_role["Teacher"] == 1
    assert sm.by_department["SEND"] == 1 and sm.by_department["Other"] == 3
    assert sm.by_status == {**{s: 0 for s in S.EMPLOYMENT_STATUSES},
                            "Full-time": 2, "Left": 1, "Sabbatical": 1}
    # the DSL has left, so the post is unfilled even though a record exists
    assert sm.unfilled_critical == ["Safeguarding Lead (DSL)"]


def test_critical_roles_filled_by_active_staff_only():
    assert S._CRITICAL_ROLES == ("Headteacher", "Safeguarding Lead (DSL)", "SENCO")
    head = _staff("H", "H", role="Headteacher")
    _staff("D", "D", role="Safeguarding Lead (DSL)", employment_status="On Leave")
    _staff("S", "S", role="SENCO", employment_status="Part-time")
    assert S.summary().unfilled_critical == []
    S.mark_left(head.staff_id, "2025-08-31")
    assert S.summary().unfilled_critical == ["Headteacher"]
