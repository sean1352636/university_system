"""Admissions applications (systems.primary.domain.admissions.admissions).

Applications run pending -> offered -> accepted -> enrolled (which creates the
pupil), or rejected / withdrawn.
"""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.admissions import admissions as A
from education_system.systems.primary.domain.learners.pupils import pupils as P

_n = 0


def _app(**extra):
    global _n
    _n += 1
    data = {"applicant_first": f"Child{_n}", "applicant_last": f"Family{_n:03d}",
            "year_applying": "R", "date_of_birth": "2022-03-01"}
    data.update(extra)
    return A.create_application(data)


def _accepted(**extra):
    a = _app(**extra)
    return A.set_status(a.application_id, "accepted")


# ── create / read ────────────────────────────────────────────────────

def test_create_application_stores_fields_and_starts_pending():
    a = _app(applicant_first=" Ada ", applicant_last="Lovelace", parent_name="Ann",
             parent_phone="01234 567890", parent_email="ann@example.org", notes=" sibling ")
    assert a.application_id.startswith("A") and len(a.application_id) == 8
    assert a.application_id[1:].isdigit()
    assert (a.applicant_first, a.applicant_last, a.applicant_name) == ("Ada", "Lovelace", "Ada Lovelace")
    assert (a.status, a.pupil_id, a.notes) == ("pending", None, "sibling")
    assert (a.parent_phone, a.parent_email) == ("01234 567890", "ann@example.org")
    assert a.application_date            # defaulted by the database
    assert A.get_application(a.application_id) == a


def test_blank_optional_fields_become_none():
    a = _app(parent_name="  ", parent_email="", date_of_birth="")
    assert (a.parent_name, a.parent_email, a.date_of_birth) == (None, None, None)


def test_get_missing_application_is_none():
    assert A.get_application("A0000000") is None


def test_generated_ids_are_unique():
    ids = {_app().application_id for _ in range(5)}
    assert len(ids) == 5


# ── validation ───────────────────────────────────────────────────────

def test_names_and_year_required():
    with pytest.raises(A.ValidationError, match="First name is required"):
        _app(applicant_first=" ")
    with pytest.raises(A.ValidationError, match="Last name is required"):
        _app(applicant_last=None)
    with pytest.raises(A.ValidationError, match="Year applying for is required"):
        _app(year_applying="")


def test_year_must_be_a_primary_year():
    with pytest.raises(A.ValidationError, match="Year applying must be one of"):
        _app(year_applying="7")
    assert _app(year_applying="6").year_applying == "6"


def test_date_phone_email_formats():
    with pytest.raises(A.ValidationError, match="Date of birth must be YYYY-MM-DD"):
        _app(date_of_birth="01/03/2022")
    with pytest.raises(A.ValidationError, match="Parent phone"):
        _app(parent_phone="call me")
    with pytest.raises(A.ValidationError, match="Parent email"):
        _app(parent_email="ann-at-example")
    assert A.list_applications() == []


# ── listing and counts ───────────────────────────────────────────────

def test_list_sorted_by_surname_within_a_day_and_filtered_by_status():
    b = _app(applicant_last="Brown")
    a = _app(applicant_last="Adams")
    c = _app(applicant_last="Clark")
    A.set_status(c.application_id, "offered")
    assert [x.application_id for x in A.list_applications()] == [
        a.application_id, b.application_id, c.application_id]
    assert [x.application_id for x in A.list_applications("offered")] == [c.application_id]
    assert A.list_applications("withdrawn") == []


def test_list_rejects_unknown_status_filter():
    with pytest.raises(A.ValidationError, match="Status filter"):
        A.list_applications("lost")


def test_status_counts():
    assert A.status_counts() == {s: 0 for s in A.STATUSES}
    _app()
    _app()
    x = _app()
    A.set_status(x.application_id, "rejected")
    counts = A.status_counts()
    assert counts["pending"] == 2 and counts["rejected"] == 1
    assert sum(counts.values()) == 3 and set(counts) == set(A.STATUSES)


# ── update ───────────────────────────────────────────────────────────

def test_update_application_rewrites_details():
    a = _app()
    u = A.update_application(a.application_id, {
        "applicant_first": "Bea", "applicant_last": "Smith", "year_applying": "2",
        "parent_email": "p@x.org"})
    assert (u.applicant_name, u.year_applying, u.parent_email) == ("Bea Smith", "2", "p@x.org")
    assert u.date_of_birth is None          # full rewrite, not a merge
    assert u.status == "pending"


def test_update_refuses_missing_and_invalid():
    a = _app()
    good = {"applicant_first": "X", "applicant_last": "Y", "year_applying": "1"}
    with pytest.raises(A.ValidationError, match="No application with id A1"):
        A.update_application("A1", good)
    with pytest.raises(A.ValidationError, match="Year applying must be one of"):
        A.update_application(a.application_id, {**good, "year_applying": "9"})


@pytest.mark.parametrize("status", ["rejected", "withdrawn"])
def test_update_refused_once_final(status):
    a = _app()
    A.set_status(a.application_id, status)
    with pytest.raises(A.ValidationError, match=f"status '{status}'"):
        A.update_application(a.application_id, {
            "applicant_first": "X", "applicant_last": "Y", "year_applying": "1"})


def test_update_refused_once_enrolled():
    a = _accepted()
    A.enrol_application(a.application_id)
    with pytest.raises(A.ValidationError, match="status 'enrolled'"):
        A.update_application(a.application_id, {
            "applicant_first": "X", "applicant_last": "Y", "year_applying": "1"})


# ── status changes ───────────────────────────────────────────────────

def test_set_status_moves_through_the_pipeline():
    a = _app()
    assert A.set_status(a.application_id, "offered").status == "offered"
    assert A.set_status(a.application_id, "accepted").status == "accepted"


def test_set_status_refuses_unknown_status_and_missing_application():
    a = _app()
    with pytest.raises(A.ValidationError, match="Status must be one of"):
        A.set_status(a.application_id, "lost")
    with pytest.raises(A.ValidationError, match="No application with id A1"):
        A.set_status("A1", "offered")


def test_enrolled_application_cannot_be_restatused():
    a = _accepted()
    A.enrol_application(a.application_id)
    with pytest.raises(A.ValidationError, match="cannot be re-statused"):
        A.set_status(a.application_id, "withdrawn")
    assert A.get_application(a.application_id).status == "enrolled"


def test_set_status_cannot_mark_enrolled_without_creating_the_pupil():
    # 'enrolled' is reached only through enrol_application, which creates the
    # pupil and stamps pupil_id; set_status would leave an enrolled
    # application with no pupil behind it.
    a = _accepted()
    with pytest.raises(A.ValidationError):
        A.set_status(a.application_id, "enrolled")
    got = A.get_application(a.application_id)
    assert got.status == "accepted" and got.pupil_id is None


# ── enrolment ────────────────────────────────────────────────────────

def test_enrol_creates_the_pupil_and_links_it():
    a = _accepted(applicant_first="Ada", applicant_last="Lovelace", year_applying="1",
                  parent_name="Ann", parent_phone="01234 567890")
    app, pupil = A.enrol_application(a.application_id)
    assert (app.status, app.pupil_id) == ("enrolled", pupil.pupil_id)
    stored = P.get_pupil(pupil.pupil_id)
    assert (stored.first_name, stored.last_name, stored.year_group) == ("Ada", "Lovelace", "1")
    assert (stored.date_of_birth, stored.parent_name, stored.parent_phone) == (
        "2022-03-01", "Ann", "01234 567890")
    assert stored.roll_status == "on_roll"


@pytest.mark.parametrize("status", ["pending", "offered", "rejected", "withdrawn"])
def test_only_accepted_applications_enrol(status):
    a = _app()
    if status != "pending":
        A.set_status(a.application_id, status)
    with pytest.raises(A.ValidationError, match=f"currently '{status}'"):
        A.enrol_application(a.application_id)
    assert P.list_pupils() == []


def test_enrol_twice_refused_and_no_second_pupil():
    a = _accepted()
    _app_, pupil = A.enrol_application(a.application_id)
    with pytest.raises(A.ValidationError, match=f"already enrolled as pupil {pupil.pupil_id}"):
        A.enrol_application(a.application_id)
    assert [p.pupil_id for p in P.list_pupils()] == [pupil.pupil_id]


def test_enrol_missing_application():
    with pytest.raises(A.ValidationError, match="No application with id A1"):
        A.enrol_application("A1")


# ── delete ───────────────────────────────────────────────────────────

def test_delete_application():
    a = _app()
    assert A.delete_application(a.application_id) is True
    assert A.get_application(a.application_id) is None
    assert A.delete_application(a.application_id) is False


def test_deleting_an_enrolled_application_keeps_the_pupil():
    a = _accepted()
    _app_, pupil = A.enrol_application(a.application_id)
    assert A.delete_application(a.application_id) is True
    assert P.get_pupil(pupil.pupil_id) is not None
