"""Alumni rules (domain.alumni) on a scratch school DB.

auth.db, the activity log and e-mail delivery are redirected / not run, so
nothing touches live data and nothing is sent.
"""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.secondary.modules.pupils.domain import alumni as AL
from education_system.systems.secondary.modules.pupils.domain import enrolment as EN
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="teacher1", role="teacher")
TODAY = dt.date(2026, 11, 3)


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    activity_log.use_log_file(tmp_path / "activity.log")
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _leaver(first="Ava", last="Stone", year=11, dob="2011-01-15", reason=EN.END_OF_Y11,
            date="2026-10-20"):
    p = P.create_pupil({
        "legal_first_name": first, "legal_last_name": last, "date_of_birth": dob,
        "gender": "Female", "year_group": year, "admission_date": "2026-09-01",
        "town": "Leeds",
    }, actor=ADMIN)
    details = {"destination_school": "Hilltop"} if reason == EN.MOVED_SCHOOL else {}
    EN.record_leaver(p.pupil_id, leaving_date=date, reason=reason, details=details,
                     actor=ADMIN, today=TODAY)
    return P.get_pupil(p.pupil_id)


CONSENT = {"email": "ava@example.com", "contact_consent": "yes",
           "consent_date": "2026-10-21", "consent_source": "Leavers' form"}


# ── From a leaver ───────────────────────────────────────────────────

def test_add_from_pupil_copies_record_and_keeps_pupil():
    p = _leaver()
    a = AL.add_from_pupil(p.pupil_id, {"current_activity": "Apprenticeship"}, actor=ADMIN,
                          today=TODAY)
    assert a.alumni_ref == f"AL{a.alumni_id:06d}"
    assert (a.first_name, a.last_name, a.date_of_birth) == ("Ava", "Stone", "2011-01-15")
    assert a.admission_no == p.admission_no and a.pupil_id == p.pupil_id
    assert a.leaving_year == "2026/27" and a.last_year_group == 11
    assert a.leaving_date == "2026-10-20" and a.town == "Leeds"
    assert a.current_activity == "Apprenticeship"
    assert not a.contact_consent and not a.can_contact
    assert P.get_pupil(p.pupil_id) is not None  # pupil record kept
    assert AL.for_pupil(p.pupil_id) == a


def test_pupil_on_roll_or_already_alumni_refused():
    on_roll = P.create_pupil({"legal_first_name": "Cy", "legal_last_name": "Hall",
                              "date_of_birth": "2014-01-15", "gender": "Male",
                              "year_group": 8, "admission_date": "2026-09-01"}, actor=ADMIN)
    with pytest.raises(AL.ValidationError, match="still on roll"):
        AL.add_from_pupil(on_roll.pupil_id, actor=ADMIN, today=TODAY)
    p = _leaver()
    AL.add_from_pupil(p.pupil_id, actor=ADMIN, today=TODAY)
    with pytest.raises(AL.ValidationError, match="already an alumnus"):
        AL.add_from_pupil(p.pupil_id, actor=ADMIN, today=TODAY)
    with pytest.raises(AL.NotFound):
        AL.add_from_pupil(9999, actor=ADMIN, today=TODAY)


def test_add_from_pupil_cannot_override_identity():
    p = _leaver()
    with pytest.raises(AL.ValidationError, match="pupil record"):
        AL.add_from_pupil(p.pupil_id, {"first_name": "Zed"}, actor=ADMIN, today=TODAY)


def test_teacher_refused():
    p = _leaver()
    with pytest.raises(AL.PermissionDenied):
        AL.add_from_pupil(p.pupil_id, actor=TEACHER, today=TODAY)
    with pytest.raises(AL.PermissionDenied):
        AL.create_alumnus({"first_name": "A", "last_name": "B", "leaving_year": "2019/20"},
                          actor=TEACHER, today=TODAY)


def test_add_leavers_only_end_of_y11_of_that_year_and_only_once():
    y11 = _leaver(first="Ben")
    _leaver(first="Cal", year=8, dob="2014-01-15", reason=EN.MOVED_SCHOOL)
    assert [p.pupil_id for p in AL.leavers_not_alumni(academic_year="2026/27",
                                                      reasons=(EN.END_OF_Y11,))] == [y11.pupil_id]
    added = AL.add_leavers("2026/27", actor=ADMIN)
    assert [a.pupil_id for a in added] == [y11.pupil_id]
    assert AL.add_leavers("2026/27", actor=ADMIN) == []
    assert AL.add_leavers("2025/26", actor=ADMIN) == []


def test_pupil_link_notes():
    p = _leaver()
    EN.record_details(p.pupil_id, {"post16_destination": "FE college"}, actor=ADMIN,
                      today=TODAY)
    a = AL.add_from_pupil(p.pupil_id, actor=ADMIN, today=TODAY)
    link = AL.pupil_link(a)
    assert link.pupil.pupil_id == p.pupil_id and link.post16_destination == "FE college"
    assert link.note is None
    EN.reinstate(p.pupil_id, actor=ADMIN, note="Came back")
    assert "Back on roll" in AL.pupil_link(a).note
    P.delete_pupil(p.pupil_id, actor=ADMIN, reason="test")
    assert AL.get_alumnus(a.alumni_id) is not None  # alumni record outlives the pupil
    assert "removed" in AL.pupil_link(a).note


# ── Without a pupil record ──────────────────────────────────────────

def test_create_legacy_and_duplicate_guard():
    data = {"first_name": "Dee", "last_name": "Ray", "date_of_birth": "1990-05-01",
            "leaving_year": "2006/07", "last_year_group": "11"}
    a = AL.create_alumnus(data, actor=ADMIN, today=TODAY)
    assert a.pupil_id is None and a.last_year_group == 11
    with pytest.raises(AL.DuplicateAlumnus):
        AL.create_alumnus({**data, "first_name": "dee"}, actor=ADMIN, today=TODAY)
    b = AL.create_alumnus(data, actor=ADMIN, allow_duplicate=True, today=TODAY)
    assert b.alumni_id != a.alumni_id


@pytest.mark.parametrize("changes, expect", [
    ({"first_name": ""}, "First name is required"),
    ({"leaving_year": "2019"}, "academic year"),
    ({"leaving_year": "2019/21"}, "academic year"),
    ({"leaving_year": "2030/31"}, "future"),
    ({"last_year_group": "6"}, "7 to 11"),
    ({"email": "nope"}, "e-mail"),
    ({"email": "ava.stone@secondarysch.uk"}, "personal e-mail"),
    ({"phone": "abc"}, "phone"),
    ({"current_activity": "Pirate"}, "Now doing"),
    ({"can_help": "maybe"}, "yes or no"),
    ({"contact_consent": "yes"}, "date they agreed"),
    ({"contact_consent": "yes", "consent_date": "2026-10-01"}, "how they agreed"),
    ({"consent_date": "2027-01-01"}, "future"),
    ({"consent_source": "Telepathy"}, "Consent given by"),
    ({"date_of_birth": "2030-01-01"}, "future"),
    ({"colour": "red"}, "Unknown field"),
])
def test_create_validation(changes, expect):
    data = {"first_name": "Dee", "last_name": "Ray", "leaving_year": "2019/20", **changes}
    with pytest.raises(AL.ValidationError) as e:
        AL.create_alumnus(data, actor=ADMIN, today=TODAY)
    assert any(expect.lower() in p.lower() for p in e.value.problems), e.value.problems


# ── Update / consent / status / delete ───────────────────────────────

def test_update_and_consent():
    a = AL.add_from_pupil(_leaver().pupil_id, actor=ADMIN, today=TODAY)
    a, changed = AL.update_alumnus(a.alumni_id, CONSENT, actor=ADMIN, today=TODAY)
    assert changed == ["consent_date", "consent_source", "contact_consent", "email"]
    assert a.can_contact
    a, changed = AL.update_alumnus(a.alumni_id, {"organisation": "Leeds College"},
                                   actor=ADMIN, today=TODAY)
    assert changed == ["organisation"] and a.email == "ava@example.com"
    # Withdrawing consent clears when/how.
    a, _ = AL.update_alumnus(a.alumni_id, {"contact_consent": "no"}, actor=ADMIN, today=TODAY)
    assert not a.contact_consent and a.consent_date is None and a.consent_source is None
    # Agreeing again needs a fresh date.
    with pytest.raises(AL.ValidationError, match="date"):
        AL.update_alumnus(a.alumni_id, {"contact_consent": "yes",
                                        "consent_source": "E-mail"}, actor=ADMIN, today=TODAY)


def test_linked_identity_is_locked_but_unchanged_values_are_fine():
    a = AL.add_from_pupil(_leaver().pupil_id, actor=ADMIN, today=TODAY)
    with pytest.raises(AL.ValidationError, match="pupil record"):
        AL.update_alumnus(a.alumni_id, {"last_name": "Other"}, actor=ADMIN, today=TODAY)
    _a, changed = AL.update_alumnus(a.alumni_id, {"last_name": "Stone",
                                                  "preferred_name": "Avi"},
                                    actor=ADMIN, today=TODAY)
    assert changed == ["preferred_name"]


def test_status_rules():
    a = AL.add_from_pupil(_leaver().pupil_id, CONSENT, actor=ADMIN, today=TODAY)
    assert a.can_contact
    with pytest.raises(AL.ValidationError, match="Say why"):
        AL.set_status(a.alumni_id, "deceased", actor=ADMIN)
    with pytest.raises(AL.ValidationError, match="Already"):
        AL.set_status(a.alumni_id, "active", actor=ADMIN)
    a = AL.set_status(a.alumni_id, "inactive", actor=ADMIN, reason="Asked for a break")
    assert not a.can_contact and a.contact_problem == "Inactive"
    a = AL.set_status(a.alumni_id, "active", actor=ADMIN)
    assert a.can_contact


def test_delete_keeps_no_personal_data_in_audit():
    p = _leaver()
    a = AL.add_from_pupil(p.pupil_id, CONSENT, actor=ADMIN, today=TODAY)
    AL.update_alumnus(a.alumni_id, {"organisation": "Acme Ltd"}, actor=ADMIN, today=TODAY)
    with pytest.raises(AL.ValidationError):
        AL.delete_alumnus(a.alumni_id, actor=ADMIN, reason=" ")
    AL.delete_alumnus(a.alumni_id, actor=ADMIN, reason="Erasure request")
    assert AL.get_alumnus(a.alumni_id) is None
    assert P.get_pupil(p.pupil_id) is not None
    with database.connect() as conn:
        dump = " ".join(str(tuple(r)) for r in conn.execute("SELECT * FROM alumni_audit"))
    for personal in ("ava@example.com", "Acme", "Stone", "2011-01-15"):
        assert personal not in dump
    # They can be added again later.
    assert AL.add_from_pupil(p.pupil_id, actor=ADMIN, today=TODAY).pupil_id == p.pupil_id


# ── Lists, summary, e-mail ───────────────────────────────────────────

def test_list_filters_and_summary():
    a = AL.add_from_pupil(_leaver().pupil_id, {**CONSENT, "can_help": "yes",
                                               "current_activity": "Employed",
                                               "organisation": "Acme"},
                          actor=ADMIN, today=TODAY)
    b = AL.create_alumnus({"first_name": "Dee", "last_name": "Ray",
                           "leaving_year": "2019/20"}, actor=ADMIN, today=TODAY)
    ids = lambda rows: [x.alumni_id for x in rows]  # noqa: E731
    assert ids(AL.list_alumni()) == [a.alumni_id, b.alumni_id]  # newest year first
    assert ids(AL.list_alumni(leaving_year="2019/20")) == [b.alumni_id]
    assert ids(AL.list_alumni(search="acme")) == [a.alumni_id]
    assert ids(AL.list_alumni(search=a.alumni_ref.lower())) == [a.alumni_id]
    assert ids(AL.list_alumni(contactable=True)) == [a.alumni_id]
    assert ids(AL.list_alumni(activity="Employed")) == [a.alumni_id]
    assert ids(AL.list_alumni(can_help=True)) == [a.alumni_id]
    assert AL.find_by_reference(a.admission_no).alumni_id == a.alumni_id
    s = AL.summary()
    assert (s.total, s.contactable, s.can_help) == (2, 1, 1)
    assert s.by_year == {"2026/27": 1, "2019/20": 1}
    assert "2019/20" in AL.leaving_year_choices(TODAY)


def test_send_email_only_to_contactable_and_personalised():
    a = AL.add_from_pupil(_leaver().pupil_id, {**CONSENT, "preferred_name": "Avi"},
                          actor=ADMIN, today=TODAY)
    same = AL.create_alumnus({"first_name": "Twin", "last_name": "Stone",
                              "leaving_year": "2019/20", **CONSENT}, actor=ADMIN, today=TODAY)
    no_consent = AL.create_alumnus({"first_name": "Dee", "last_name": "Ray",
                                    "leaving_year": "2019/20", "email": "dee@example.com"},
                                   actor=ADMIN, today=TODAY)
    message_id, plan = AL.send_email("Hello {first_name}", "Reunion for {leaving_year}.",
                                     [a.alumni_id, same.alumni_id, no_consent.alumni_id],
                                     actor=ADMIN)
    assert [x.alumni_id for x in plan.recipients] == [a.alumni_id]
    assert {x.alumni_id: why for x, why in plan.skipped} == {
        same.alumni_id: "Same e-mail as another alumnus", no_consent.alumni_id: "No consent"}
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM email_recipients WHERE message_id = ?",
                            (message_id,)).fetchall()
        kind = conn.execute("SELECT audience_kind FROM email_messages WHERE message_id = ?",
                            (message_id,)).fetchone()[0]
    assert kind == "alumni" and len(rows) == 1
    assert rows[0]["address"] == "ava@example.com" and rows[0]["status"] == "queued"
    assert rows[0]["subject"] == "Hello Avi"
    assert rows[0]["body"].startswith("Reunion for 2026/27.")
    assert "To stop" in rows[0]["body"]
    assert AL.history(a.alumni_id)[0]["action"] == "email"


def test_send_email_validation():
    a = AL.create_alumnus({"first_name": "Dee", "last_name": "Ray",
                           "leaving_year": "2019/20"}, actor=ADMIN, today=TODAY)
    with pytest.raises(AL.ValidationError) as e:
        AL.send_email("", "Hi {pupil_name}", [a.alumni_id], actor=ADMIN)
    text = " ".join(e.value.problems)
    assert "subject" in text and "{pupil_name}" in text
    with pytest.raises(AL.ValidationError, match="None of the chosen"):
        AL.send_email("Hi", "Hello", [a.alumni_id], actor=ADMIN)
    with pytest.raises(AL.PermissionDenied):
        AL.send_email("Hi", "Hello", [a.alumni_id], actor=TEACHER)
