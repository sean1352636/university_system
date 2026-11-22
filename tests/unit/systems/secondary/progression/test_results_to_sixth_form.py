"""Exam results reaching the sixth form (exam_results -> sixth_form_progression).

Runs the real platform post-16 board and Secondary's adapter against a
temporary platform DB, with a fake sixth form adapter recording what it is
sent, so neither the live platform DB nor the sixth form's DBs are touched.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from education_system.platform.cross_system import secondary_post16 as post16
from education_system.platform.cross_system.adapters.base import (
    ApplicantResult,
    EnrolmentResult,
    PhaseAdapter,
)
from education_system.systems.secondary.modules.examinations.domain import exam_entries as EE
from education_system.systems.secondary.modules.examinations.domain import exam_results as ER
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.infrastructure.integrations import (
    cross_system_adapter as XA,
)
from education_system.systems.secondary.modules.progression.domain import (
    sixth_form_progression as SFP,
)
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="teacher1", role="teacher")
TODAY = dt.date.today()


class FakeSixthForm(PhaseAdapter):
    system = "sixth_form"

    def __init__(self):
        super().__init__()
        self.received, self.results = [], []

    def create_applicant(self, handover):
        self.received.append(handover)
        return ApplicantResult(local_applicant_id=f"A{len(self.received):07d}")

    def create_enrolment(self, journey_id, application_id=None, **details):
        return EnrolmentResult(local_student_id="C0000001")

    def update_applicant_results(self, handover):
        self.results.append(handover)


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
    monkeypatch.setattr(EE, "_today", lambda: TODAY)
    monkeypatch.setattr(ER, "_today", lambda: TODAY)
    ava, ben = (P.create_pupil({
        "legal_first_name": n, "legal_last_name": "Turner", "date_of_birth": "2010-05-02",
        "gender": "Female", "year_group": 11, "admission_date": "2021-09-01"}, actor=ADMIN)
        for n in ("Ava", "Ben"))
    S.create({"code": "MATH", "name": "Maths", "exam_board": "AQA", "spec_code": "8300"},
             actor=ADMIN)
    S.create({"code": "ENGL", "name": "English Language", "exam_board": "AQA",
              "spec_code": "8700"}, actor=ADMIN)
    series = EE.create_series({"season": "June", "exam_year": TODAY.year + 1,
                               "entry_deadline": (TODAY + dt.timedelta(days=10)).isoformat()},
                              actor=ADMIN)
    EE.specs_from_subjects(actor=ADMIN)
    EE.update_spec(EE.find_spec("8300").spec_id, {
        "tiered": True, "foundation_code": "8300F", "higher_code": "8300H"}, actor=ADMIN)
    entries = {}
    for p in (ava, ben):
        EE.set_candidate(p.pupil_id, actor=ADMIN)
        for code in ("8300", "8700"):
            entries[(p.legal_first_name, code)] = EE.create_entry({
                "series_id": series.series_id, "pupil_id": p.pupil_id,
                "spec_id": EE.find_spec(code).spec_id, "entry_status": "Final",
                "tier": "Higher" if code == "8300" else None}, actor=ADMIN)
    yield {"db": platform_db, "sixth_form": fake, "ava": ava, "ben": ben,
           "sid": series.series_id, "e": entries}
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _grade(env, who, code, grade):
    return ER.record_for_entry(env["e"][(who, code)].entry_id, grade, actor=ADMIN)


def _stored(env, pupil):
    app = SFP.application_for(pupil.pupil_id, db_path=env["db"])
    return json.loads(app["handover_json"])


def test_embargoed_grades_stay_out_of_the_handover(env):
    _grade(env, "Ava", "8300", "7")
    rec = XA.ADAPTER.export_handover(str(env["ava"].pupil_id)).record
    assert "gcse_results" not in rec  # recorded, but still under embargo
    entries = {e["subject_code"]: e for e in rec["gcse_entries"]}
    assert entries["MATH"]["result"] == "awaited" and entries["MATH"]["grade"] is None
    assert entries["MATH"]["entry_code"] == "8300H"
    ER.release(env["sid"], actor=ADMIN)
    rec = XA.ADAPTER.export_handover(str(env["ava"].pupil_id)).record
    assert [(r["subject_code"], r["grade"]) for r in rec["gcse_results"]] == [("MATH", "7")]
    states = {e["subject_code"]: e["result"] for e in rec["gcse_entries"]}
    assert states == {"MATH": "issued", "ENGL": "awaited"}


def test_release_updates_open_applications(env):
    ava, ben = env["ava"], env["ben"]
    SFP.send(ava.pupil_id, actor=ADMIN, db_path=env["db"])  # Ben is never sent
    _grade(env, "Ava", "8300", "7")
    _grade(env, "Ben", "8300", "5")
    assert env["sixth_form"].results == []  # nothing goes while embargoed
    out = ER.release(env["sid"], actor=ADMIN)
    assert out["sixth_form"]["sent"] == [ava.admission_no]
    assert out["sixth_form"]["skipped"] == {}  # Ben has no application: not listed
    sent = env["sixth_form"].results[-1]
    assert [(r["subject"], r["grade"]) for r in sent.payload["gcse_results"]] == [
        ("Maths", "7")]
    assert _stored(env, ava)["gcse_results"][0]["grade"] == "7"  # board copy updated
    assert _stored(env, ava)["student_identity"]["first_name"] == "Ava"


def test_later_changes_follow_once_released(env):
    ava = env["ava"]
    SFP.send(ava.pupil_id, actor=ADMIN, db_path=env["db"])
    r = _grade(env, "Ava", "8300", "6")
    ER.release(env["sid"], actor=ADMIN)
    n = len(env["sixth_form"].results)
    _grade(env, "Ava", "8700", "5")  # a late result
    assert len(env["sixth_form"].results) == n + 1
    v = ER.request_review(r.result_id, {"service": "Review of marking", "consent_by": "Ava"},
                          actor=ADMIN)
    under = {e["subject_code"]: e for e in env["sixth_form"].results[-1].payload[
        "gcse_entries"]}
    assert under["MATH"]["result"] == "under review" and under["MATH"]["grade"] == "6"
    ER.record_outcome(v.review_id, "Grade raised", new_grade="7", actor=ADMIN)
    last = env["sixth_form"].results[-1].payload["gcse_results"]
    assert {x["subject_code"]: x["grade"] for x in last} == {"MATH": "7", "ENGL": "5"}
    ER.record_for_entry(env["e"][("Ava", "8700")].entry_id, None, actor=ADMIN,
                        status="Withheld")
    last = env["sixth_form"].results[-1].payload["gcse_results"]
    assert {x["subject_code"] for x in last} == {"MATH"}  # withheld: taken back


def test_send_results_by_hand(env):
    ava, ben = env["ava"], env["ben"]
    SFP.send(ava.pupil_id, actor=ADMIN, db_path=env["db"])
    SFP.send(ben.pupil_id, actor=ADMIN, db_path=env["db"])
    SFP.withdraw(ben.pupil_id, actor=ADMIN, db_path=env["db"])
    out = SFP.send_results(actor=ADMIN, db_path=env["db"])
    assert out["sent"] == [ava.admission_no] and out["skipped"] == {}
    out = SFP.send_results([ben.pupil_id], actor=ADMIN, db_path=env["db"])
    assert out["sent"] == [] and "withdrawn" in out["skipped"][ben.admission_no]
    with pytest.raises(SFP.PermissionDenied):
        SFP.send_results(actor=TEACHER, db_path=env["db"])
    assert SFP.results_summary(ava.pupil_id) == "2 awaited"


def test_a_destination_that_cannot_take_results(env, monkeypatch):
    class Old(FakeSixthForm):
        update_applicant_results = PhaseAdapter.update_applicant_results
    monkeypatch.setattr(post16, "_destination_adapter", lambda d: Old())
    SFP.send(env["ava"].pupil_id, actor=ADMIN, db_path=env["db"])
    _grade(env, "Ava", "8300", "7")
    out = ER.release(env["sid"], actor=ADMIN)  # the release itself still happens
    assert ER.released(env["sid"]) is not None
    assert "can't receive exam results" in out["sixth_form"]["skipped"][
        env["ava"].admission_no]
