"""Year 11 A-level choices (domain.sixth_form_choices) and the portal section.

The real platform post-16 board runs on a temporary platform DB; a fake
sixth form adapter stands in for the sixth form's course list and entry
requirements (Mathematics needs GCSE maths 7, Physics maths 6, the others
nothing), so neither the live platform DB nor the sixth form's DBs are
touched.
"""

from __future__ import annotations

import datetime as dt
import json
import re

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
from education_system.systems.secondary.modules.portals.domain import portal as PT
from education_system.systems.secondary.infrastructure.integrations import (
    cross_system_adapter as XA,
)
from education_system.systems.secondary.modules.progression.domain import sixth_form_choices as SC
from education_system.systems.secondary.modules.progression.domain import (
    sixth_form_progression as SFP,
)
from education_system.systems.secondary.modules.pupils.domain import pupil_accounts as PAC
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="teacher1", role="teacher")
TODAY = dt.date.today()
COURSES = ("Mathematics", "Physics", "History", "Biology", "Chemistry")
NEEDS = {"Mathematics": 7, "Physics": 6}


class FakeSixthForm(PhaseAdapter):
    system = "sixth_form"

    def __init__(self):
        super().__init__()
        self.received, self.choices = [], []

    def create_applicant(self, handover):
        self.received.append(handover)
        return ApplicantResult(local_applicant_id=f"A{len(self.received):07d}")

    def create_enrolment(self, journey_id, application_id=None, **details):
        return EnrolmentResult(local_student_id="C0000001")

    def update_applicant_results(self, handover):
        pass

    def update_applicant_choices(self, handover):
        self.choices.append(handover.payload["application_details"]["subjects"])

    def offered_subjects(self):
        return COURSES

    def course_options(self, gcse_results):
        maths = next((int(r["grade"]) for r in gcse_results
                      if r["subject_code"] == "MATH" and r["grade"].isdigit()), None)
        out = []
        for c in COURSES:
            need = NEEDS.get(c)
            if need is None:
                out.append({"course": c, "outcome": "Met", "requirements": [], "checks": []})
                continue
            outcome = ("Pending" if maths is None else "Met" if maths >= need
                       else "Near miss" if maths == need - 1 else "Not met")
            out.append({"course": c, "outcome": outcome,
                        "requirements": [f"GCSE Mathematics grade {need} or above"],
                        "checks": [{"requirement": f"GCSE Mathematics grade {need} or above",
                                    "outcome": outcome, "detail": f"Maths {maths}",
                                    "programme": c}]})
        return out


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
    ava = P.create_pupil({"legal_first_name": "Ava", "legal_last_name": "Turner",
                          "date_of_birth": "2010-05-02", "gender": "Female", "year_group": 11,
                          "admission_date": "2021-09-01"}, actor=ADMIN)
    cy = P.create_pupil({"legal_first_name": "Cy", "legal_last_name": "Turner",
                         "date_of_birth": "2011-05-02", "gender": "Male", "year_group": 10,
                         "admission_date": "2022-09-01"}, actor=ADMIN)
    S.create({"code": "MATH", "name": "Maths", "exam_board": "AQA", "spec_code": "8300"},
             actor=ADMIN)
    S.create({"code": "ENGL", "name": "English Language", "exam_board": "AQA",
              "spec_code": "8700"}, actor=ADMIN)
    series = EE.create_series({"season": "June", "exam_year": TODAY.year + 1,
                               "entry_deadline": (TODAY + dt.timedelta(days=10)).isoformat()},
                              actor=ADMIN)
    EE.specs_from_subjects(actor=ADMIN)
    EE.set_candidate(ava.pupil_id, actor=ADMIN)
    entries = {code: EE.create_entry({
        "series_id": series.series_id, "pupil_id": ava.pupil_id,
        "spec_id": EE.find_spec(code).spec_id, "entry_status": "Final"}, actor=ADMIN)
        for code in ("8300", "8700")}
    C.add_contact(ava.pupil_id, {"full_name": "Mum Turner", "relationship": "Mother",
                                 "email": "mum@home.org"}, actor=ADMIN)
    acct = PAC.create_for_pupil(ava.pupil_id, actor=ADMIN, send_welcome=False)
    yield {"db": platform_db, "sixth_form": fake, "ava": ava, "cy": cy, "path": tmp_path,
           "sid": series.series_id, "e": entries,
           "student": Principal(acct.account.username, "student")}
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _results_day(env, maths="6", english="5"):
    ER.record_for_entry(env["e"]["8300"].entry_id, maths, actor=ADMIN)
    ER.record_for_entry(env["e"]["8700"].entry_id, english, actor=ADMIN)
    ER.release(env["sid"], actor=ADMIN)


def test_choosing_three_a_levels(env):
    ava, me = env["ava"], env["student"]
    for bad in (["Mathematics", "Physics"], ["Mathematics", "Physics", "physics"],
                ["Mathematics", "Physics", "Latin"]):
        with pytest.raises(SC.ValidationError):
            SC.save(ava.pupil_id, bad, actor=me)
    out = SC.save(ava.pupil_id, ["mathematics", "Physics", "History"], actor=me)
    assert out == {"choices": ["Mathematics", "Physics", "History"],
                   "sixth_form": "not sent yet"}
    assert SC.get(ava.pupil_id).chosen_as == "pupil"
    with pytest.raises(SC.PermissionDenied):
        SC.save(ava.pupil_id, ["Biology", "Physics", "History"], actor=TEACHER)
    with pytest.raises(SC.ValidationError) as e:  # Year 10: not yet
        SC.save(env["cy"].pupil_id, ["Biology", "Physics", "History"], actor=ADMIN)
    assert "Year 11" in e.value.problems[0]
    assert SC.history(ava.pupil_id)[0]["detail"]["to"] == ["Mathematics", "Physics",
                                                           "History"]


def test_before_results_each_choice_shows_what_it_needs(env):
    SC.save(env["ava"].pupil_id, ["Mathematics", "Physics", "History"], actor=ADMIN)
    st = SC.status(env["ava"].pupil_id)
    assert not st["results_known"] and st["all_met"] is None
    assert SC.summary(st) == "Results awaited"
    assert st["chosen"][0]["requirements"] == ["GCSE Mathematics grade 7 or above"]
    assert st["can_choose_from"] == []
    ER.record_for_entry(env["e"]["8300"].entry_id, "9", actor=ADMIN)  # embargoed
    assert not SC.status(env["ava"].pupil_id)["results_known"]


def test_results_met_means_they_can_study_their_choices(env):
    SC.save(env["ava"].pupil_id, ["Mathematics", "Physics", "History"], actor=ADMIN)
    _results_day(env, maths="8")
    st = SC.status(env["ava"].pupil_id)
    assert st["results_known"] and st["all_met"] is True and SC.summary(st) == "All met"


def test_results_not_met_show_the_courses_to_choose_from(env):
    ava, me = env["ava"], env["student"]
    SC.save(ava.pupil_id, ["Mathematics", "Physics", "History"], actor=me)
    _results_day(env, maths="4")
    st = SC.status(ava.pupil_id)
    assert st["all_met"] is False and SC.summary(st) == "2 not met"
    assert st["can_choose_from"] == ["Biology", "Chemistry"]
    with pytest.raises(SC.ValidationError) as e:  # Physics needs maths 6
        SC.save(ava.pupil_id, ["Physics", "Biology", "History"], actor=me)
    assert "entry requirements for Physics" in e.value.problems[0]
    out = SC.save(ava.pupil_id, ["Biology", "Chemistry", "History"], actor=me)
    assert out["choices"] == ["Biology", "Chemistry", "History"]
    assert SC.status(ava.pupil_id)["all_met"] is True
    assert [s["pupil"].pupil_id for s in SC.cohort(show="needs new choices")] == []


def test_staff_may_choose_a_near_miss_pupils_may_not(env):
    ava, me = env["ava"], env["student"]
    SC.save(ava.pupil_id, ["Biology", "Chemistry", "History"], actor=me)
    _results_day(env, maths="6")  # Mathematics needs 7: near miss
    assert SC.status(ava.pupil_id)["near_miss"] == ["Mathematics"]
    with pytest.raises(SC.ValidationError):
        SC.save(ava.pupil_id, ["Mathematics", "Chemistry", "History"], actor=me)
    assert SC.save(ava.pupil_id, ["Mathematics", "Chemistry", "History"],
                   actor=ADMIN)["choices"][0] == "Mathematics"
    st = SC.status(ava.pupil_id)
    assert SC.summary(st) == "1 near miss"
    assert SC.cohort(show="needs new choices")[0]["pupil"].pupil_id == ava.pupil_id


def test_choices_go_with_the_pupil_and_changes_follow(env):
    ava, me = env["ava"], env["student"]
    SC.save(ava.pupil_id, ["Mathematics", "Physics", "History"], actor=me)
    app = SFP.send(ava.pupil_id, actor=ADMIN, db_path=env["db"])  # saved choices used
    assert app["programme_label"] == "Mathematics, Physics, History"
    [h] = env["sixth_form"].received
    assert h.get("application_details")["subjects"] == ["Mathematics", "Physics", "History"]
    _results_day(env, maths="4")
    out = SC.save(ava.pupil_id, ["Biology", "Chemistry", "History"], actor=me)
    assert out["sixth_form"] == "updated"
    assert env["sixth_form"].choices[-1] == ["Biology", "Chemistry", "History"]
    app = SFP.application_for(ava.pupil_id, db_path=env["db"])
    assert app["programme_label"] == "Biology, Chemistry, History"
    assert json.loads(app["handover_json"])["application_details"]["subjects"][0] == "Biology"


def test_portal_section_pupil_chooses_parent_looks(env):
    ava, me = env["ava"], env["student"]
    st = PT.sixth_form(me, ava.pupil_id)
    assert st["can_choose"] and st["choices"] == []
    PT.choose_sixth_form(me, ava.pupil_id, ["Mathematics", "Physics", "History"])
    _results_day(env, maths="4")
    st = PT.sixth_form(me, ava.pupil_id)
    assert st["summary"] == "2 not met" and st["can_choose_from"] == ["Biology", "Chemistry"]
    with pytest.raises(PT.PermissionDenied):
        PT.sixth_form(me, env["cy"].pupil_id)
    log = (env["path"] / "activity.log").read_text()
    assert not re.search(r"[\w.]+@[\w.]+", log) and "Ava" not in log


def test_parent_sees_but_cannot_choose(env):
    mum = Principal("mum.turner", "parent")  # linked from the contact's e-mail
    assert [p.pupil_id for p in PT.pupils(mum)] == [env["ava"].pupil_id]
    st = PT.sixth_form(mum, env["ava"].pupil_id)
    assert st["can_choose"] is False
    with pytest.raises(PT.PermissionDenied):
        PT.choose_sixth_form(mum, env["ava"].pupil_id, ["Mathematics", "Physics", "History"])
    with pytest.raises(SC.PermissionDenied):
        SC.save(env["ava"].pupil_id, ["Mathematics", "Physics", "History"], actor=mum)


# ── Option blocks ────────────────────────────────────────────────────

BLOCKS = {"A": ["Mathematics", "History"], "B": ["Physics", "Biology"],
          "C": ["Chemistry", "History"]}


def _blocked(env, monkeypatch, full=()):
    """The fake sixth form, with option blocks and the courses in *full*
    out of places. Records the journey it was asked about."""
    import itertools
    fake, asked = env["sixth_form"], []

    def option_blocks(subjects, journey_id=None):
        asked.append(journey_id)
        courses = {c: {"blocks": [b for b, cs in BLOCKS.items() if c in cs],
                       "capacity": 10, "taken": 10 if c in full else 3, "full": c in full}
                   for cs in BLOCKS.values() for c in cs}
        wanted = [s for s in subjects if s]
        placement = next((dict(zip(bs, wanted)) for bs in itertools.permutations(
            BLOCKS, len(wanted)) if all(s in BLOCKS[b] for b, s in zip(bs, wanted))), None)
        return {"academic_year": "2027/28", "published": True, "blocks": BLOCKS,
                "courses": courses, "placement": placement,
                "full": [s for s in wanted if s in full],
                "clashes": [] if placement is not None else
                ["Block clash: these subjects cannot all be placed in different blocks"]}
    monkeypatch.setattr(fake, "option_blocks", option_blocks, raising=False)
    return asked


def test_option_blocks_refuse_clashes_and_full_courses(env, monkeypatch):
    ava, me = env["ava"], env["student"]
    _blocked(env, monkeypatch, full=("Chemistry",))
    with pytest.raises(SC.ValidationError) as e:  # Physics and Biology: both block B
        SC.save(ava.pupil_id, ["Mathematics", "Physics", "Biology"], actor=me)
    assert any("Block clash" in x for x in e.value.problems)
    assert any("Physics (block B)" in x for x in e.value.problems)
    with pytest.raises(SC.ValidationError) as e:
        SC.save(ava.pupil_id, ["Mathematics", "Physics", "Chemistry"], actor=me)
    assert e.value.problems == ["Chemistry is full - there are no places left (choose "
                                "another course)"]
    assert SC.save(ava.pupil_id, ["Mathematics", "Physics", "History"],
                   actor=me)["choices"] == ["Mathematics", "Physics", "History"]
    st = SC.status(ava.pupil_id)
    chem = next(o for o in st["options"] if o["course"] == "Chemistry")
    assert chem["full"] and chem["blocks"] == ["C"] and chem["places"] == 0
    assert SC.block_lines(st["blocks"]) == ["Block A: Mathematics, History",
                                            "Block B: Physics, Biology",
                                            "Block C: Chemistry (full), History"]
    assert SC.summary(st) == "Results awaited"


def test_a_course_already_chosen_is_kept_when_it_fills(env, monkeypatch):
    ava, me = env["ava"], env["student"]
    SC.save(ava.pupil_id, ["Mathematics", "Physics", "Chemistry"], actor=me)
    _blocked(env, monkeypatch, full=("Chemistry",))  # filled since
    _results_day(env, maths="4")  # Mathematics and Physics no longer met
    st = SC.status(ava.pupil_id)
    assert st["can_choose_from"] == ["History", "Biology"]  # Chemistry is theirs already
    out = SC.save(ava.pupil_id, ["History", "Biology", "Chemistry"], actor=me)
    assert out["choices"] == ["History", "Biology", "Chemistry"]
    assert "Chemistry" in SC.status(ava.pupil_id)["eligible"]  # still theirs to keep


def test_a_clash_shows_in_lists_and_the_journey_is_passed(env, monkeypatch):
    ava = env["ava"]
    SC.save(ava.pupil_id, ["Mathematics", "Physics", "Biology"], actor=ADMIN)  # no blocks yet
    asked = _blocked(env, monkeypatch)
    assert SC.summary(SC.status(ava.pupil_id)) == "Results awaited, block clash"
    SFP.send(ava.pupil_id, actor=ADMIN, db_path=env["db"])
    SC.status(ava.pupil_id)
    assert asked[0] is None and asked[-1]  # once sent, its own place is left out
    assert SFP.application_for(ava.pupil_id)["journey_id"] == asked[-1]
