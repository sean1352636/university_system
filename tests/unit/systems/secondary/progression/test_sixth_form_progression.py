"""Moving Year 11 pupils to the sixth form (domain.sixth_form_progression).

Runs the real platform post-16 board and Secondary's adapter against a
temporary auth.db (passed as ``db_path`` and patched as the default), with
a fake sixth form adapter standing in for the destination, so neither the
live platform DB nor the sixth form's DBs are touched.
"""

from __future__ import annotations

import pytest

from education_system.platform.cross_system import secondary_post16 as post16
from education_system.platform.cross_system.adapters.base import (
    ApplicantResult,
    EnrolmentResult,
    PhaseAdapter,
)
from education_system.systems.secondary.modules.examinations.domain import gcse_results as G
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.infrastructure.integrations import (
    cross_system_adapter as XA,
)
from education_system.systems.secondary.modules.progression.domain import (
    sixth_form_progression as SFP,
)
from education_system.systems.secondary.modules.pupils.domain import enrolment as E
from education_system.systems.secondary.modules.pupils.domain import sen_details as SEN
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="teacher1", role="teacher")


class FakeSixthForm(PhaseAdapter):
    system = "sixth_form"

    def __init__(self):
        super().__init__()
        self.received = []

    def create_applicant(self, handover):
        self.received.append(handover)
        return ApplicantResult(local_applicant_id=f"A{len(self.received):07d}")

    def create_enrolment(self, journey_id, application_id=None, **details):
        return EnrolmentResult(local_student_id="C0000001")

    def offered_subjects(self):
        return ("Mathematics", "Biology")

    def course_options(self, gcse_results):
        return [{"course": c, "outcome": "Met", "requirements": [], "checks": []}
                for c in ("Mathematics", "Biology", "Chemistry")]


@pytest.fixture
def env(tmp_path, monkeypatch):
    from education_system.platform.identity.auth import db as auth_db
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    platform_db = str(tmp_path / "platform_auth.db")
    monkeypatch.setattr(auth_db, "PLATFORM_AUTH_DB_FILE", platform_db)
    initialise_auth_db(platform_db)
    XA.register()
    fake = FakeSixthForm()
    monkeypatch.setattr(post16, "_destination_adapter", lambda d: fake)
    yield {"db": platform_db, "sixth_form": fake}
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _pupil(first="Amelia", year=11, sen="N", **extra):
    return P.create_pupil({
        "legal_first_name": first, "legal_last_name": "Turner", "middle_names": "Rose",
        "date_of_birth": f"{2026 - year - 4}-05-02", "gender": "Female", "year_group": year,
        "admission_date": "2021-09-01", "sen_status": sen, **extra}, actor=ADMIN)


@pytest.fixture
def amelia(env):
    S.create({"code": "MATH", "name": "Maths", "ebacc_category": "Maths"}, actor=ADMIN)
    p = _pupil(sen="E")
    G.record(p.pupil_id, {"subject": "MATH", "grade": "7"}, actor=ADMIN)
    SEN.save(p.pupil_id, {"primary_need": "ASD", "ehcp_reference": "EHC-1",
                          "exam_access": "25% extra time"}, actor=ADMIN)
    return p


def test_export_carries_full_name_gcses_and_sen(amelia):
    rec = XA.ADAPTER.export_handover(str(amelia.pupil_id)).record
    ident = rec["student_identity"]
    assert ident["full_name"] == "Amelia Rose Turner"
    assert ident["first_name"] == "Amelia" and ident["last_name"] == "Turner"
    assert ident["date_of_birth"] == amelia.date_of_birth
    assert rec["gcse_results"][0]["subject"] == "Maths"
    assert rec["gcse_results"][0]["grade"] == "7"
    assert rec["access_arrangements"]["primary_need"] == "ASD"


def test_sen_is_held_back_without_consent(amelia, env):
    pv = SFP.preview(amelia.pupil_id, actor=ADMIN)
    assert "access_arrangements" in pv.withheld_no_consent
    assert "gcse_results" in pv.included
    pv = SFP.preview(amelia.pupil_id, actor=ADMIN, consent_sen=True, consent_reference="F1")
    assert "access_arrangements" in pv.included


def test_send_creates_an_applicant_with_the_data(amelia, env):
    app = SFP.send(amelia.pupil_id, actor=ADMIN, consent_sen=True,
                   consent_reference="Form 12",
                   subjects=["Mathematics", "Biology", "Chemistry"], db_path=env["db"])
    assert app["stage"] == "Application submitted"
    assert app["programme_label"] == "Mathematics, Biology, Chemistry"
    [h] = env["sixth_form"].received
    assert h.source_system == "secondary"
    assert h.get("student_identity")["full_name"] == "Amelia Rose Turner"
    assert h.get("gcse_results")[0]["grade"] == "7"
    assert h.get("access_arrangements")["ehcp_reference"] == "EHC-1"
    assert h.get("application_details")["subjects"] == ["Mathematics", "Biology",
                                                        "Chemistry"]
    from education_system.systems.secondary.modules.progression.domain import (
        sixth_form_choices as SC,
    )
    assert SC.courses_for(amelia.pupil_id) == ["Mathematics", "Biology", "Chemistry"]
    # The pupil stays on roll until the sixth form enrols them.
    assert P.get_pupil(amelia.pupil_id).roll_status == "on_roll"
    [c] = [c for c in SFP.cohort(db_path=env["db"]) if c.pupil.pupil_id == amelia.pupil_id]
    assert c.stage == "Application submitted" and not c.can_send


def test_send_without_consent_strips_sen(amelia, env):
    SFP.send(amelia.pupil_id, actor=ADMIN, db_path=env["db"])
    [h] = env["sixth_form"].received
    assert h.get("access_arrangements") is None


def test_send_rules(amelia, env):
    with pytest.raises(SFP.PermissionDenied):
        SFP.send(amelia.pupil_id, actor=TEACHER, db_path=env["db"])
    y10 = _pupil("Cy", year=10)
    with pytest.raises(SFP.ValidationError) as e:
        SFP.send(y10.pupil_id, actor=ADMIN, db_path=env["db"])
    assert "only Year 11" in e.value.problems[0]
    with pytest.raises(SFP.ValidationError) as e:
        SFP.send(amelia.pupil_id, actor=ADMIN, consent_sen=True, db_path=env["db"])
    assert "consent reference" in e.value.problems[0]
    with pytest.raises(SFP.ValidationError):
        SFP.send(amelia.pupil_id, actor=ADMIN, subjects=["Maths", "maths"],
                 db_path=env["db"])
    with pytest.raises(SFP.ValidationError) as e:  # three A-levels, or none
        SFP.send(amelia.pupil_id, actor=ADMIN, subjects=["Mathematics"], db_path=env["db"])
    assert "three A-levels" in e.value.problems[0]
    SFP.send(amelia.pupil_id, actor=ADMIN, db_path=env["db"])
    with pytest.raises(SFP.ValidationError) as e:
        SFP.send(amelia.pupil_id, actor=ADMIN, db_path=env["db"])
    assert "already sent" in e.value.problems[0]
    assert len(env["sixth_form"].received) == 1


def test_withdraw_then_send_again(amelia, env):
    SFP.send(amelia.pupil_id, actor=ADMIN, db_path=env["db"])
    assert SFP.withdraw(amelia.pupil_id, actor=ADMIN, reason="error",
                        db_path=env["db"])["stage"] == "Withdrawn"
    SFP.send(amelia.pupil_id, actor=ADMIN, db_path=env["db"])
    assert len(env["sixth_form"].received) == 2


def test_send_many_reports_each(amelia, env):
    y10 = _pupil("Cy", year=10)
    out = SFP.send_many([amelia.pupil_id, y10.pupil_id], actor=ADMIN, db_path=env["db"])
    assert out["sent"] == [amelia.admission_no]
    assert list(out["failed"]) == [y10.admission_no]


def test_sixth_form_reports_back_and_enrolment_takes_pupil_off_roll(amelia, env):
    app = SFP.send(amelia.pupil_id, actor=ADMIN, db_path=env["db"])
    journey = app["journey_id"]
    assert post16.destination_update("other-journey", "sixth_form", "Conditional offer",
                                     db_path=env["db"]) is None
    assert post16.destination_update(journey, "sixth_form", "Conditional offer",
                                     details="Offer Made", db_path=env["db"]
                                     )["stage"] == "Conditional offer"
    done = post16.destination_update(journey, "sixth_form", "Enrolled / On Programme",
                                     local_student_id="C0000001", db_path=env["db"])
    assert done["stage"] == "Enrolled / On Programme" and done["confirmed"] == 1
    p = P.get_pupil(amelia.pupil_id)
    assert p.roll_status == "left"
    lv = E.current_leaving(amelia.pupil_id)
    assert lv.reason == E.END_OF_Y11
    assert lv.post16_destination == "Sixth form college"
    # Nothing open any more: a repeat report is a no-op.
    assert post16.destination_update(journey, "sixth_form", "Enrolled / On Programme",
                                     db_path=env["db"]) is None


def test_close_is_idempotent(amelia, env):
    assert SFP.close_for_sixth_form(amelia.pupil_id) is True
    assert SFP.close_for_sixth_form(amelia.pupil_id) is False


def test_offered_subjects_come_from_the_sixth_form(env, monkeypatch):
    from education_system.platform.cross_system import route_support
    monkeypatch.setattr(route_support, "adapter_for", lambda s: env["sixth_form"])
    assert SFP.offered_subjects() == ("Mathematics", "Biology")
