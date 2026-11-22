"""Adult Education linked to FE College and University.

* Adult Education → FE College: an adult moves onto an FE course
  (``fe_applications``); FE makes a 19+ adult learner and enrols them
  alongside the adult course.
* FE College → Adult Education: the college refers an adult
  (``adult_education_applications``); Adult Education records an enquiry
  and a referral, and enrolling the learner on a class - or declining -
  goes back to the college.
* Adult Education → University: an Access to HE learner applies through
  UCAS (``university_applications``); confirming the place records the
  destination at Adult Education.

Every path is resolved when ``education_system.paths`` is imported, so the
flow runs in a fresh interpreter with every ``EDU_*_DATA_DIR`` (auth.db
included) under ``tmp_path``: nothing here can reach a live database. The
university end is a stand-in adapter (a fresh university schema can't be
built from the migrations), so this checks the platform and Adult
Education ends. The script prints one JSON object; the tests read it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytestmark = pytest.mark.slow

_DIRS = ("PLATFORM", "PRIMARY", "SECONDARY", "ALTERNATIVE_PROVISION", "NURSERY", "SIXTHFORM",
         "FE_COLLEGE", "APPRENTICESHIPS", "SPECIAL_EDUCATION", "LOCAL_AUTHORITY",
         "ADULT_EDUCATION", "TRAINING_PROVIDER")

SCRIPT = textwrap.dedent('''
    import datetime, json
    from education_system import paths
    out = {"auth_db": str(paths.PLATFORM_AUTH_DB_FILE)}
    from education_system.platform.identity.auth.schema import initialise_auth_db
    paths.PLATFORM_DB_FILES_DIR.mkdir(parents=True, exist_ok=True)
    initialise_auth_db(str(paths.PLATFORM_AUTH_DB_FILE))
    import education_system.launcher.systems as L
    for key in ("fe_college", "adult_education"):
        L._register_phase_adapter(key)

    # A stand-in university: records what it was sent.
    from education_system.platform.cross_system.adapters import registry
    from education_system.platform.cross_system.adapters.base import (
        ApplicantResult, EnrolmentResult, ExportResult, PhaseAdapter)
    class Uni(PhaseAdapter):
        system = "university"
        def __init__(self):
            self.sent, self.apps = [], {}
        def create_applicant(self, h):
            self.sent.append(h.payload)
            self.apps[h.journey_id] = {"application_id": 7, "status": "submitted"}
            return ApplicantResult(local_applicant_id="7")
        def find_application(self, journey_id):
            return self.apps.get(journey_id)
        def record_decision(self, *a, **k): pass
        def accept_choice(self, *a, **k): pass
        def create_enrolment(self, journey_id, application_id=None, **k):
            return EnrolmentResult(local_student_id="U1", start_date=k.get("start_date"))
        def export_handover(self, *a, **k):
            return ExportResult(record={}, local_student_id="U1")
        def close_enrolment(self, *a, **k): pass
    uni = Uni()
    registry.register(uni, replace=True)

    from education_system.platform.cross_system import (
        adult_education_applications as to_ae, fe_applications as to_fe,
        university_applications as to_uni, transitions)
    from education_system.systems.adult_education.app import routing
    routing.load_areas()
    from education_system.systems.adult_education.core import records as r
    from education_system.systems.adult_education.modules import (
        courses, enrolments, learners, progress, referrals, support)
    from education_system.systems.fe_college.domain.students.models import Student
    from education_system.systems.fe_college.services import student_service as fe

    today = datetime.date.today()
    day = lambda n: (today + datetime.timedelta(days=n)).isoformat()
    notices = []

    def save(rt, values, rid=None):
        i = r.save(rt, values, record_id=rid, actor="test")
        notices.extend(r.take_notices())
        return i

    course = save(courses.COURSES, {"code": "ACC3", "title": "Access to HE Diploma",
                                    "subject": "English", "level": "Level 3",
                                    "mode": "Classroom", "status": "Active"})
    esol = save(courses.COURSES, {"code": "ESOL3", "title": "ESOL Entry 3",
                                  "subject": "ESOL", "level": "Entry 3",
                                  "mode": "Classroom", "status": "Active"})
    klass = save(courses.CLASSES, {"course_id": course, "start_date": day(-30),
                                   "end_date": day(200), "capacity": 10})
    eklass = save(courses.CLASSES, {"course_id": esol, "start_date": day(-5),
                                    "end_date": day(90), "capacity": 10})

    # 1. Adult Education -> FE College
    ann = save(learners.LEARNERS, {"first_name": "Ann", "last_name": "Rowe",
                                   "dob": "1990-05-04", "gender": "Female",
                                   "email": "ann@example.test", "status": "Active",
                                   "support_needs": "Dyslexia"})
    save(learners.PRIOR, {"learner_id": ann, "title": "GCSE English Language",
                          "level": "Level 2", "grade": "5"})
    save(support.SUPPORT, {"learner_id": ann, "need": "Dyslexia / SpLD",
                           "support": "Coloured overlays", "start_date": day(-20)})
    ann_enr = save(enrolments.ENROLMENTS, {"learner_id": ann, "class_id": klass,
                                           "enrolled_on": day(-30)})
    ref = r.get(learners.LEARNERS, ann)["learner_ref"]
    t = to_fe.refer("adult_education", ref, pathway="Level 3 Health and Social Care",
                    reason="Progression to FE", consent=True)
    applicant = [s for s in fe.search("") if s.first_name == "Ann"][0]
    to_fe.accept_referral(t["transition_id"], accepted_by="FE admissions", consent=True)
    done = to_fe.enrol_referral(t["transition_id"], concurrent=True)
    out["to_fe"] = {"offered": t["status"], "completed": done["status"],
                    "learner_type": applicant.learner_type,
                    "prior": applicant.prior_attainment,
                    "support": applicant.learning_support,
                    "ae_status": r.get(learners.LEARNERS, ann)["status"],
                    "labels": [to_fe.SOURCE_LABELS[x["source_system"]] for x in
                               transitions.pending_transitions("fe_college",
                                                               status="completed")]}

    # 2. FE College -> Adult Education, enrolled
    ben = fe.create(Student(student_id=fe.next_reference(), first_name="Ben",
                            last_name="Okafor", date_of_birth=datetime.date(1985, 2, 1),
                            email="ben@example.test", status="enrolled",
                            learning_support="Hearing loop"))
    t2 = to_ae.refer("fe_college", ben.student_id, course="ESOL", reason="English for work",
                     intended_start=day(0), referrer="Tutor", consent=True)
    again = to_ae.refer("fe_college", ben.student_id, course="ESOL", reason="again")
    lrn = [x for x in r.list_records(learners.LEARNERS) if x["first_name"] == "Ben"][0]
    rref = referrals.for_transition(t2["transition_id"])
    out["to_ae"] = {"status": t2["status"], "same": again["transition_id"] ==
                    t2["transition_id"],
                    "learner": [lrn["status"], lrn["gender"], bool(lrn["journey_id"]),
                                lrn["support_needs"]],
                    "referral": [rref["status"], rref["course"], rref["college"],
                                 rref["consent_to_share"],
                                 len(r.list_records(referrals.FE_REFERRALS))],
                    "board": [[x["learner"], x["course"], x["label"]]
                              for x in to_ae.referrals_from("fe_college")]}
    before = len(notices)
    save(enrolments.ENROLMENTS, {"learner_id": lrn["id"], "class_id": eklass,
                                 "enrolled_on": day(0)})
    out["enrolled"] = {
        "notices": notices[before:],
        "referral": r.get(referrals.FE_REFERRALS, rref["id"])["status"],
        "course_id": r.get(referrals.FE_REFERRALS, rref["id"])["course_id"] == esol,
        "transition": transitions.get_transition(t2["transition_id"])["status"],
        "learner": r.get(learners.LEARNERS, lrn["id"])["status"],
        "fe_still": [s.status for s in fe.search("") if s.first_name == "Ben"][0],
        "board": [x["label"] for x in to_ae.referrals_from("fe_college")]}

    # 3. FE College -> Adult Education, declined
    cara = fe.create(Student(student_id=fe.next_reference(), first_name="Cara",
                             last_name="Lund", date_of_birth=datetime.date(1979, 9, 9),
                             status="enrolled"))
    t3 = to_ae.refer("fe_college", cara.student_id, course="Digital skills",
                     reason="Job search")
    cref = referrals.for_transition(t3["transition_id"])
    try:
        save(referrals.FE_REFERRALS, {"status": "Declined"}, cref["id"])
        out["decline_without_reason"] = "saved"
    except r.ValidationError as exc:
        out["decline_without_reason"] = str(exc)
    before = len(notices)
    save(referrals.FE_REFERRALS, {"status": "Declined",
                                  "decision_reason": "Course full this term"}, cref["id"])
    row = transitions.get_transition(t3["transition_id"])
    out["declined"] = {"notices": notices[before:], "status": row["status"],
                       "decision": row.get("decision"),
                       "label": [x["label"] for x in to_ae.referrals_from("fe_college")
                                 if x["transition_id"] == t3["transition_id"]][0]}
    try:
        save(referrals.FE_REFERRALS, {"status": "New"}, cref["id"])
        out["reopen_declined"] = "saved"
    except r.ValidationError as exc:
        out["reopen_declined"] = str(exc)

    # 4. Adult Education -> University (Access to HE)
    save(enrolments.ENROLMENTS, {"status": "Completed", "outcome": "Achieved"}, ann_enr)
    consent = to_uni.consent_record(recorded_by="aetutor1", scope=("reference",))
    fields = {"ucas_application": {"ucas_id": "123 456 7890"},
              "choices": [{"university": "Example University", "course_code": "N1",
                           "course_name": "Nursing", "entry_year": str(today.year + 1)}],
              "handover_consent": consent, "personal_statement": "Care work",
              "academic_reference": "Strong", "consent": True}
    pv = to_uni.preview("adult_education", ref, **fields)
    sub = to_uni.submit("adult_education", ref, **fields)
    tid = sub["transition_id"]
    to_uni.record_offer(tid, unconditional=True)
    to_uni.select_firm_choice(tid, choice_id=1, accepted_by="Ann",
                              consent_payload=pv, consent_reference="c1")
    to_uni.confirm_place(tid, actor_id="admissions", start_date=day(0))
    sent = uni.sent[0]
    dests = r.list_records(progress.DESTINATIONS, learner_id=ann)
    out["to_uni"] = {
        "ready": pv.ready, "missing": list(pv.missing_required),
        "identity": [sent["student_identity"]["first_name"],
                     sent["student_identity"]["college_student_id"]],
        "ucas": sent["ucas_application"]["ucas_id"],
        "achieved": [q["course"] for q in sent.get("achieved_qualifications") or []],
        "prior": [q["title"] for q in sent.get("recognised_prior_learning") or []],
        "support": bool(sent.get("support_referral")),
        "status": transitions.get_transition(tid)["status"],
        "destination": [d["destination"] for d in dests],
        "learner": r.get(learners.LEARNERS, ann)["status"]}

    # 5. a learner nobody referred: enrolling tells nobody
    before = len(notices)
    z = save(learners.LEARNERS, {"first_name": "Zed", "last_name": "Quinn",
                                 "dob": "1970-01-01", "gender": "Male",
                                 "phone": "07700900123"})
    save(enrolments.ENROLMENTS, {"learner_id": z, "class_id": eklass,
                                 "enrolled_on": day(0)})
    out["unlinked_notices"] = notices[before:]
    out["notices"] = notices
    print("RESULT" + json.dumps(out, default=str))
''')


@pytest.fixture(scope="module")
def flow(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("ae_link")
    env = {**os.environ, **{f"EDU_{k}_DATA_DIR": str(root / k.lower()) for k in _DIRS}}
    env.pop("EDU_DEV_SEED", None)
    done = subprocess.run([sys.executable, "-c", SCRIPT], env=env, capture_output=True,
                          text=True, timeout=600)
    line = next((ln for ln in done.stdout.splitlines() if ln.startswith("RESULT")), None)
    assert line, f"flow failed:\n{done.stdout[-3000:]}\n{done.stderr[-5000:]}"
    result = json.loads(line[len("RESULT"):])
    assert result["auth_db"].startswith(str(root)), "auth.db was not isolated"
    return result


def test_adult_moves_onto_an_fe_course_alongside(flow):
    fe = flow["to_fe"]
    assert (fe["offered"], fe["completed"]) == ("offered", "completed")
    assert fe["learner_type"] == "19+ Adult Learner"
    assert "GCSE English Language" in fe["prior"]
    assert "Dyslexia" in fe["support"]          # consented
    assert fe["ae_status"] == "Active"          # the adult course carries on
    assert "Adult Education" in fe["labels"]


def test_fe_referral_arrives_as_an_enquiry(flow):
    ae = flow["to_ae"]
    assert ae["status"] == "offered" and ae["same"]
    assert ae["learner"] == ["Enquiry", "Prefer not to say", True, ae["learner"][3]]
    assert "Hearing loop" in ae["learner"][3]
    assert ae["referral"] == ["New", "ESOL", "FE College", 1, 1]
    assert ae["board"] == [["Ben Okafor", "ESOL", "With Adult Education"]]


def test_enrolling_completes_the_referral_and_keeps_the_fe_place(flow):
    e = flow["enrolled"]
    assert e["referral"] == "Enrolled" and e["course_id"]
    assert e["transition"] == "completed"
    assert e["learner"] == "Active"
    assert e["fe_still"] == "enrolled"
    assert e["board"][0] == "Enrolled"
    assert any("has been told the learner enrolled" in n for n in e["notices"])


def test_declining_tells_the_college(flow):
    assert "Say why" in flow["decline_without_reason"]
    d = flow["declined"]
    assert (d["status"], d["decision"], d["label"]) == ("cancelled", "rejected", "Declined")
    assert d["notices"] == ["FE College has been told the referral was declined."]
    assert "Record a new referral" in flow["reopen_declined"]


def test_access_to_he_application_and_destination(flow):
    u = flow["to_uni"]
    assert u["ready"], u["missing"]
    assert u["identity"][0] == "Ann" and u["identity"][1]
    assert u["ucas"] == "1234567890"
    assert u["achieved"] == ["Access to HE Diploma"]
    assert u["prior"] == ["GCSE English Language"]
    assert u["support"]
    assert u["status"] == "completed"
    assert u["destination"] == ["Higher education"]
    assert u["learner"] == "Completed"           # no adult course still open


def test_learners_nobody_referred_stay_local(flow):
    assert flow["unlinked_notices"] == []


def test_no_platform_failures_were_swallowed(flow):
    assert not [n for n in flow["notices"] if n.startswith("Saved, but")]
