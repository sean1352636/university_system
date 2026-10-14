"""Closing a secondary pupil keeps the record.

The secondary adapter's ``close_enrolment`` used to write an alumni row
and then delete the pupil — the one thing the adapter contract forbids
(``PhaseAdapter.close_enrolment``: "Must not delete"). It now marks the
pupil ``left`` and keeps them. The destination side is covered too: an
arriving Year 7 pupil is an applicant, off the class lists, until
``create_enrolment`` puts them on roll.

Every database here is under ``tmp_path``.
"""

from __future__ import annotations

import inspect

import pytest

from education_system.platform.cross_system import identity_service
from education_system.platform.cross_system.adapters.base import HandoverRequest
from education_system.platform.identity.auth import db as auth_db
from education_system.platform.identity.auth.schema import initialise_auth_db
from education_system.systems.secondary.domain.admissions import (
    cross_system_adapter as secondary_adapter,
)
from education_system.systems.secondary.domain.learners.alumni import alumni
from education_system.systems.secondary.domain.learners.pupils import pupils


@pytest.fixture()
def secondary_db(tmp_path, monkeypatch):
    """The secondary pupils/alumni DB and auth.db, both under tmp_path.

    ``create_pupil`` registers the pupil's journey in the *default* auth
    database, so the default is redirected as well as passed explicitly.
    """
    auth_path = tmp_path / "auth.db"
    monkeypatch.setattr(auth_db, "PLATFORM_AUTH_DB_FILE", auth_path)
    initialise_auth_db(str(auth_path))
    identity_service._initialised.clear()
    monkeypatch.setattr(pupils, "DB_PATH", tmp_path / "secondary.db")
    monkeypatch.setattr(pupils, "_DB_READY", False)
    if hasattr(alumni, "_DB_READY"):
        monkeypatch.setattr(alumni, "_DB_READY", False)
    yield tmp_path
    identity_service._initialised.clear()


def _year11_pupil():
    return pupils.create_pupil({
        "first_name": "Jamie", "last_name": "Singh", "year_group": "11",
        "form_group": "11B", "date_of_birth": "2010-03-02", "phone": "",
        "parent_name": "Ravi Singh", "parent_phone": "07000 000000",
        "send_status": "no",
    })


def test_close_keeps_the_pupil_and_records_alumni(secondary_db):
    pupil = _year11_pupil()

    secondary_adapter.ADAPTER.close_enrolment(
        pupil.pupil_id, "Progressed to sixth_form", end_date="2026-07-20")

    kept = pupils.get_pupil(pupil.pupil_id)
    assert kept is not None, "close_enrolment must never delete the pupil"
    assert kept.roll_status == "left"
    assert kept.left_date == "2026-07-20"
    assert kept.exit_reason == "Progressed to sixth_form"
    assert secondary_adapter.alumni_id_for(pupil.pupil_id) is not None
    # Off the class lists, still findable for history.
    assert pupil.pupil_id not in {p.pupil_id for p in pupils.list_pupils()}
    assert pupil.pupil_id in {
        p.pupil_id for p in pupils.list_pupils(include_off_roll=True)}


def test_closing_twice_writes_one_alumni_row(secondary_db):
    pupil = _year11_pupil()

    for _ in range(2):
        secondary_adapter.ADAPTER.close_enrolment(
            pupil.pupil_id, "Progressed to fe_college")

    assert [a.pupil_id for a in alumni.list_alumni()].count(pupil.pupil_id) == 1


def test_close_enrolment_has_no_delete_path():
    source = inspect.getsource(secondary_adapter.SecondaryAdapter.close_enrolment)
    assert "delete_pupil" not in source


def test_arriving_pupil_is_an_applicant_until_enrolled(secondary_db, monkeypatch):
    monkeypatch.setattr(secondary_adapter, "_provision_login",
                        lambda pupil: (42, "first-password"))
    request = HandoverRequest(
        journey_id="journey-1", source_system="primary",
        destination_system="secondary", transition_id="transition-1",
        payload={
            "child_identity": {"first_name": "Ada", "last_name": "Obi",
                               "date_of_birth": "2014-09-01"},
            "guardians": [{"name": "Grace Obi", "phone": "07111 111111"}],
            "send_provision": {"send_status": "yes"},
        })

    applicant = secondary_adapter.ADAPTER.create_applicant(request)
    again = secondary_adapter.ADAPTER.create_applicant(request)

    assert again.local_applicant_id == applicant.local_applicant_id
    held = pupils.get_pupil(applicant.local_applicant_id)
    assert held.roll_status == "applicant"
    assert held.year_group == "7"
    assert held.send_status == "yes"
    assert held.pupil_id not in {p.pupil_id for p in pupils.list_pupils()}

    enrolled = secondary_adapter.ADAPTER.create_enrolment(
        "journey-1", form_group="7A", provision_login=True)

    assert enrolled.local_student_id == applicant.local_applicant_id
    assert enrolled.initial_password == "first-password"
    on_roll = pupils.get_pupil(applicant.local_applicant_id)
    assert on_roll.roll_status == "on_roll"
    assert on_roll.form_group == "7A"
