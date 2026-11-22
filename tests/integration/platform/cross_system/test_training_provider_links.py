"""Training Provider linked to Apprenticeships and FE College.

* Apprenticeships / FE College → Training Provider
  (``training_provider_requests``): a sender asks for a learner to be
  trained on a short course. Booking them on a session (or a place coming
  up off the waiting list) tells the sender; the certificate goes back -
  an apprenticeship as off-the-job hours awaiting approval, FE College on
  the learner's prior attainment; a fail or decline goes back too.
* Training Provider → Apprenticeships (``apprenticeship_applications``) and
  → FE College (``fe_applications``): a learner trained here goes on; the
  training provider's record stays open.

Every path is resolved when ``education_system.paths`` is imported, so the
flow runs in a fresh interpreter with every ``EDU_*_DATA_DIR`` (auth.db
included) under ``tmp_path``: nothing here can reach a live database. The
script prints one JSON object; the tests read it.
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
    for key in ("fe_college", "apprenticeships", "training_provider"):
        L._register_phase_adapter(key)

    from education_system.platform.cross_system import (
        apprenticeship_applications as to_app, fe_applications as to_fe,
        training_provider_requests as to_tp, transitions)
    from education_system.systems.training_provider.app import routing
    routing.load_areas()
    from education_system.systems.training_provider.core import records as r
    from education_system.systems.training_provider.modules import (
        assessment, clients, courses, learners, requests, sessions)
    from education_system.systems.apprenticeships.infrastructure.persistence.schema import (
        connect as app_connect, init_db as app_init)
    from education_system.systems.fe_college.domain.students.models import Student
    from education_system.systems.fe_college.services import student_service as fe
    from education_system.systems.fe_college.infrastructure.persistence.schema import (
        init_db as fe_init)
    fe_init()

    today = datetime.date.today()
    def weekday(back):
        d = today - datetime.timedelta(days=back)
        while d.weekday() >= 5:
            d -= datetime.timedelta(days=1)
        return d.isoformat()
    notices = []

    def save(rt, values, rid=None):
        i = r.save(rt, values, record_id=rid, actor="test")
        notices.extend(r.take_notices())
        return i

    venue = save(courses.VENUES, {"name": "Main centre", "kind": "Our training centre"})
    fa = save(courses.COURSES, {"code": "FAW", "title": "First Aid at Work",
                                "category": "First aid", "kind": "Non-accredited / CPD",
                                "delivery": "Classroom", "duration_days": 1,
                                "max_delegates": 12, "price": 100, "guided_hours": 6,
                                "valid_months": 36})
    mh = save(courses.COURSES, {"code": "MH1", "title": "Manual Handling",
                                "category": "Health & safety", "kind": "Non-accredited / CPD",
                                "delivery": "Classroom", "duration_days": 1,
                                "max_delegates": 12, "price": 80, "pass_mark": 70})
    s1 = save(sessions.SESSIONS, {"course_id": fa, "start_date": weekday(7),
                                  "venue_id": venue, "status": "Confirmed"})
    s2 = save(sessions.SESSIONS, {"course_id": mh, "start_date": weekday(3),
                                  "venue_id": venue, "status": "Confirmed", "capacity": 1})

    # Apprenticeships set-up: an employer, a programme, an apprentice on programme
    app_init()
    with app_connect() as c:
        emp = c.execute("INSERT INTO employers (name) VALUES ('Acme Ltd')").lastrowid
        prog = c.execute("INSERT INTO programmes (reference, title, level, funding_band, "
                         "duration_months) VALUES ('ST0001', 'Engineering Technician', 3, "
                         "10, 24)").lastrowid
        ana = c.execute("INSERT INTO apprentices (given_name, family_name, date_of_birth, "
                        "status, employer_id, programme_id) VALUES ('Ana', 'Ruiz', "
                        "'2003-03-03', 'On Programme', ?, ?)", (emp, prog)).lastrowid

    # 1. Apprenticeships -> Training Provider: booked, attended, certificated
    t1 = to_tp.request("apprenticeships", str(ana), course="First Aid at Work",
                       reason="Site first aider", payer="Employer pays", consent=True)
    again = to_tp.request("apprenticeships", str(ana), course="First Aid", reason="again")
    lrn = [x for x in r.list_records(learners.LEARNERS) if x["first_name"] == "Ana"][0]
    req = requests.for_transition(t1["transition_id"])
    acme = r.get(clients.CLIENTS, req["bill_to"]) if req["bill_to"] else {}
    out["request"] = {"status": t1["status"], "same": again["transition_id"] ==
                      t1["transition_id"],
                      "learner": [lrn["funding"], lrn["client_id"] == req["bill_to"],
                                  bool(lrn["journey_id"])],
                      "request": [req["status"], req["sender"], req["payer"],
                                  acme.get("name"), len(r.list_records(
                                      requests.TRAINING_REQUESTS))],
                      "board": [[x["learner"], x["course"], x["label"]]
                                for x in to_tp.requests_from("apprenticeships")]}
    before = len(notices)
    b1 = save(sessions.BOOKINGS, {"learner_id": lrn["id"], "session_id": s1})
    out["booked"] = {"notices": notices[before:],
                     "request": requests.for_transition(t1["transition_id"])["status"],
                     "transition": transitions.get_transition(t1["transition_id"])["status"],
                     "billed": r.get(sessions.BOOKINGS, b1)["client_id"] == req["bill_to"]}
    save(sessions.BOOKINGS, {"status": "Attended"}, b1)
    before = len(notices)
    save(assessment.CERTIFICATES, {"learner_id": lrn["id"], "session_id": s1})
    with app_connect() as c:
        otj = [dict(x) for x in c.execute("SELECT hours, status, description FROM "
                                          "otj_entries WHERE apprentice_id = ?", (ana,))]
        notes = c.execute("SELECT notes FROM apprentices WHERE apprentice_id = ?",
                          (ana,)).fetchone()[0]
    out["certificate"] = {
        "notices": notices[before:],
        "request": requests.for_transition(t1["transition_id"])["status"],
        "otj": [[o["hours"], o["status"]] for o in otj],
        "notes": notes,
        "board": [[x["label"], x["latest"]] for x in to_tp.requests_from("apprenticeships")]}

    # 2. FE College -> Training Provider: waiting list, promoted, failed
    fay = fe.create(Student(student_id=fe.next_reference(), first_name="Fay",
                            last_name="Moss", date_of_birth=datetime.date(2007, 6, 1),
                            email="fay@example.test", status="enrolled"))
    other = save(learners.LEARNERS, {"first_name": "Oli", "last_name": "Grant",
                                     "dob": "1990-01-01"})
    ob = save(sessions.BOOKINGS, {"learner_id": other, "session_id": s2})
    t2 = to_tp.request("fe_college", fay.student_id, course="Manual Handling",
                       reason="Placement needs it", po_number="PO-77")
    flrn = [x for x in r.list_records(learners.LEARNERS) if x["first_name"] == "Fay"][0]
    before = len(notices)
    fb = save(sessions.BOOKINGS, {"learner_id": flrn["id"], "session_id": s2})
    out["waiting"] = {"booking": r.get(sessions.BOOKINGS, fb)["status"],
                      "request": requests.for_transition(t2["transition_id"])["status"],
                      "transition": transitions.get_transition(t2["transition_id"])["status"],
                      "po": r.get(sessions.BOOKINGS, fb)["po_number"],
                      "bill_to": (r.get(clients.CLIENTS, r.get(sessions.BOOKINGS, fb)
                                        ["client_id"]) or {}).get("name")}
    save(sessions.BOOKINGS, {"status": "Cancelled"}, ob)
    out["promoted"] = {"notices": notices[before:],
                       "booking": r.get(sessions.BOOKINGS, fb)["status"],
                       "request": requests.for_transition(t2["transition_id"])["status"],
                       "transition": transitions.get_transition(t2["transition_id"])["status"]}
    before = len(notices)
    save(assessment.RESULTS, {"learner_id": flrn["id"], "session_id": s2,
                              "assessed_on": weekday(3), "score": 40})
    fe_row = [s for s in fe.search("") if s.first_name == "Fay"][0]
    out["failed"] = {"notices": notices[before:],
                     "request": requests.for_transition(t2["transition_id"])["status"],
                     "fe_notes": fe_row.notes, "fe_status": fe_row.status,
                     "board": [x["label"] for x in to_tp.requests_from("fe_college")]}

    # 3. FE College -> Training Provider, declined
    gus = fe.create(Student(student_id=fe.next_reference(), first_name="Gus",
                            last_name="Hale", date_of_birth=datetime.date(2006, 1, 9),
                            status="enrolled"))
    t3 = to_tp.request("fe_college", gus.student_id, course="Forklift", reason="Job",
                       payer="Learner pays")
    greq = requests.for_transition(t3["transition_id"])
    try:
        save(requests.TRAINING_REQUESTS, {"status": "Declined"}, greq["id"])
        out["decline_without_reason"] = "saved"
    except r.ValidationError as exc:
        out["decline_without_reason"] = str(exc)
    before = len(notices)
    save(requests.TRAINING_REQUESTS, {"status": "Declined",
                                      "decision_reason": "We don't run forklift"}, greq["id"])
    row = transitions.get_transition(t3["transition_id"])
    out["declined"] = {"notices": notices[before:], "status": row["status"],
                       "decision": row.get("decision"), "bill_to": greq["bill_to"]}

    # 4. Training Provider -> Apprenticeships (Ana's colleague, trained here first)
    hal = save(learners.LEARNERS, {"first_name": "Hal", "last_name": "Venn",
                                   "dob": "1995-02-02", "email": "hal@example.test",
                                   "phone": "07700900000"})
    hb = save(sessions.BOOKINGS, {"learner_id": hal, "session_id": s1})
    save(sessions.BOOKINGS, {"status": "Attended"}, hb)
    save(assessment.CERTIFICATES, {"learner_id": hal, "session_id": s1})
    ref = r.get(learners.LEARNERS, hal)["learner_ref"]
    fields = {"intended_programme": {"title": "Engineering Technician", "level": "3"},
              "eligibility_evidence": "Right to work checked", "consent": True,
              "prior_attainment": "GCSE maths 5, English 5"}
    sub = to_app.submit("training_provider", ref, reason="Wants an apprenticeship", **fields)
    to_app.accept_offer(sub["transition_id"], accepted_by="Hal", **fields)
    done = to_app.start_programme(sub["transition_id"], programme_id=prog, employer_id=emp)
    with app_connect() as c:
        app_row = dict(c.execute("SELECT status, prior_learning FROM apprentices WHERE "
                                 "given_name = 'Hal'").fetchone())
    out["to_app"] = {"status": done["status"], "apprentice": app_row["status"],
                     "prior": app_row["prior_learning"],
                     "tp_learner": r.get(learners.LEARNERS, hal)["status"]}

    # 5. Training Provider -> FE College
    t5 = to_fe.refer("training_provider", ref, pathway="Level 3 Engineering",
                     reason="Evening course", consent=True)
    hal_fe = [s for s in fe.search("") if s.first_name == "Hal"][0]
    out["to_fe"] = {"status": t5["status"], "learner_type": hal_fe.learner_type,
                    "prior": hal_fe.prior_attainment}

    # 6. a learner nobody sent: booking tells nobody
    before = len(notices)
    z = save(learners.LEARNERS, {"first_name": "Zed", "last_name": "Quinn"})
    zb = save(sessions.BOOKINGS, {"learner_id": z, "session_id": s1})
    save(sessions.BOOKINGS, {"status": "Attended"}, zb)
    save(assessment.CERTIFICATES, {"learner_id": z, "session_id": s1})
    out["unlinked_notices"] = notices[before:]
    out["notices"] = notices
    print("RESULT" + json.dumps(out, default=str))
''')


@pytest.fixture(scope="module")
def flow(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("tp_link")
    env = {**os.environ, **{f"EDU_{k}_DATA_DIR": str(root / k.lower()) for k in _DIRS}}
    env.pop("EDU_DEV_SEED", None)
    done = subprocess.run([sys.executable, "-c", SCRIPT], env=env, capture_output=True,
                          text=True, timeout=600)
    line = next((ln for ln in done.stdout.splitlines() if ln.startswith("RESULT")), None)
    assert line, f"flow failed:\n{done.stdout[-3000:]}\n{done.stderr[-5000:]}"
    result = json.loads(line[len("RESULT"):])
    assert result["auth_db"].startswith(str(root)), "auth.db was not isolated"
    return result


def test_request_arrives_with_the_employer_as_payer(flow):
    q = flow["request"]
    assert q["status"] == "offered" and q["same"]
    assert q["learner"] == ["Employer", True, True]
    assert q["request"] == ["New", "Apprenticeships", "Employer pays", "Acme Ltd", 1]
    assert q["board"] == [["Ana Ruiz", "First Aid at Work", "With the training provider"]]


def test_booking_tells_the_sender_and_bills_the_payer(flow):
    b = flow["booked"]
    assert (b["request"], b["transition"]) == ("Booked", "completed")
    assert b["billed"]
    assert any("told the learner is booked" in n for n in b["notices"])


def test_certificate_becomes_otj_hours_awaiting_approval(flow):
    c = flow["certificate"]
    assert c["request"] == "Certificated"
    assert c["otj"] == [[6.0, "Submitted"]]
    assert "First Aid at Work - certificate" in c["notes"]
    assert c["board"][0][0] == "Certificated"
    assert c["board"][0][1].startswith("certificate")
    assert any("off-the-job hours submitted" in n for n in c["notices"])


def test_waiting_list_then_promoted(flow):
    w = flow["waiting"]
    assert (w["booking"], w["request"], w["transition"]) == ("Waiting list", "Waiting list",
                                                            "offered")
    assert (w["po"], w["bill_to"]) == ("PO-77", "FE College")
    p = flow["promoted"]
    assert (p["booking"], p["request"], p["transition"]) == ("Booked", "Booked", "completed")


def test_a_fail_goes_back_to_the_college(flow):
    f = flow["failed"]
    assert f["request"] == "Not passed"
    assert "Manual Handling: not passed" in f["fe_notes"]
    assert f["fe_status"] == "enrolled"
    assert f["board"][0] == "Booked"           # newest first: Fay's request


def test_declining_tells_the_sender(flow):
    assert "Say why" in flow["decline_without_reason"]
    d = flow["declined"]
    assert (d["status"], d["decision"]) == ("cancelled", "rejected")
    assert d["bill_to"] is None                 # the learner pays: no client set up
    assert d["notices"] == ["FE College has been told the request was declined."]


def test_trained_learner_starts_an_apprenticeship(flow):
    a = flow["to_app"]
    assert (a["status"], a["apprentice"]) == ("completed", "On Programme")
    assert "First Aid at Work" in a["prior"]
    assert a["tp_learner"] == "Active"


def test_trained_learner_goes_to_fe(flow):
    f = flow["to_fe"]
    assert f["status"] == "offered"
    assert f["learner_type"] == "19+ Adult Learner"
    assert "First Aid at Work" in f["prior"]


def test_learners_nobody_sent_stay_local(flow):
    assert flow["unlinked_notices"] == []


def test_no_platform_failures_were_swallowed(flow):
    assert not [n for n in flow["notices"] if n.startswith("Saved, but")]
