"""Census learner aims (modules.reporting.domain.census_aims) on a scratch DB."""

from __future__ import annotations

import pytest

from education_system.systems.secondary.modules.reporting.domain import census as CE
from education_system.systems.secondary.modules.reporting.domain import census_aims as CA
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="ann", role="teacher")


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _pupil():
    return P.create_pupil({"legal_first_name": "Ada", "legal_last_name": "Aim",
                           "date_of_birth": "2010-03-01", "gender": "Female", "year_group": 11,
                           "form_group": "11A", "admission_date": "2021-09-01"}, actor=ADMIN)


def _aim(**extra):
    return CA.create_aim({"learner_ref": "L-1", "aim_reference": "60012345",
                          "start_date": "2026-09-01", **extra}, actor=ADMIN)


def test_create_links_pupil_and_return_and_keeps_free_text_refs():
    p = _pupil()
    ret = CE.create_return({"academic_year": "2026/27"}, actor=ADMIN)
    a = _aim(learner_ref=p.admission_no, return_id=ret["return_id"], aim_title="GCSE Maths")
    assert a.pupil_id == p.pupil_id and a.learner_name == p.display_name
    assert a.aim_type == CA.DEFAULT_AIM_TYPE and a.status == "Continuing" and a.is_active
    loose = _aim(learner_ref="EXT-99")
    assert loose.pupil_id is None and loose.learner_ref == "EXT-99"
    assert [x.aim_id for x in CA.aims_for_return(ret["return_id"], actor=ADMIN)] == [a.aim_id]
    assert [x.aim_id for x in CA.aims_for_learner(p.admission_no, actor=ADMIN)] == [a.aim_id]
    assert [x.aim_id for x in CA.aims_for_pupil(p.pupil_id, actor=ADMIN)] == [a.aim_id]
    # Deleting the return keeps the aim, unlinked.
    CE.delete_return(ret["return_id"], actor=ADMIN)
    assert CA.get_aim(a.aim_id, actor=ADMIN).return_id is None


def test_validation_reports_every_problem():
    with pytest.raises(CA.ValidationError) as e:
        CA.create_aim({"aim_type": "Nope", "start_date": "2026-13-01",
                       "planned_end_date": "2020-01-01", "completion_code": "4",
                       "planned_hours": "-3", "return_id": "999"}, actor=ADMIN)
    text = " ".join(e.value.problems)
    for bit in ("Learner ref", "Aim type", "Aim reference", "Start date", "Completion code",
                "Planned hours", "No census return #999"):
        assert bit in text
    with pytest.raises(CA.ValidationError, match="before the start"):
        _aim(actual_end_date="2026-08-01")
    with pytest.raises(CA.ValidationError, match="Unknown field"):
        _aim(colour="red")


def test_edit_delete_filters_and_summary():
    a = _aim()
    b = _aim(learner_ref="L-2", status="Withdrawn", completion_code="3")
    a = CA.update_aim(a.aim_id, {"status": "achieved", "actual_end_date": "2027-06-30"},
                      actor=ADMIN)
    assert a.status == "Achieved" and a.updated_by == "admin2" and not a.is_active
    assert CA.list_aims(actor=ADMIN, active_only=True) == []
    assert [x.aim_id for x in CA.list_aims(actor=ADMIN, status="Withdrawn")] == [b.aim_id]
    s = CA.summary(ADMIN)
    assert (s["total"], s["achieved"], s["withdrawn"], s["learners"]) == (2, 1, 1, 2)
    assert CA.delete_aim(b.aim_id, actor=ADMIN)
    with pytest.raises(CA.NotFound):
        CA.get_aim(b.aim_id, actor=ADMIN)


def test_data_managers_only():
    a = _aim()
    for call in (lambda: CA.list_aims(actor=TEACHER),
                 lambda: CA.get_aim(a.aim_id, actor=TEACHER),
                 lambda: CA.create_aim({"learner_ref": "x"}, actor=TEACHER),
                 lambda: CA.delete_aim(a.aim_id, actor=TEACHER)):
        with pytest.raises(P.PermissionDenied):
            call()
