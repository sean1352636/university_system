"""The Local Authority linked to the Primary and Secondary schools.

A school's notification (attendance referral, suspension or exclusion, child
missing education, elective home education, EHC needs assessment request)
becomes the authority's casework, alongside the school place; the
authority's decisions come back to the school (EHC decisions onto its SEN
record); a school place the authority allocates at a linked school lands in
that school's own admissions.

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
    for key in ("primary", "secondary", "local_authority"):
        L._register_phase_adapter(key)

    from education_system.platform.cross_system import identity_service
    from education_system.platform.cross_system import local_authority_links as svc
    from education_system.platform.cross_system import enrolments, transitions
    from education_system.systems.primary.domain.admissions import admissions as PA
    from education_system.systems.primary.domain.learners.pupils import pupils as PP
    from education_system.systems.primary.domain.learners.pupils import year6_transition as Y
    from education_system.systems.primary.domain.pastoral.send import send as PSEND
    from education_system.systems.secondary.modules.pupils.domain import pupils as SP
    from education_system.systems.secondary.modules.progression.domain import (
        incoming_primary as INC)
    from education_system.systems.secondary.core.permissions.access import Principal
    from education_system.systems.local_authority.core import dates as D
    from education_system.systems.local_authority.core import records as r
    from education_system.systems.local_authority.modules import (
        admissions, children, exclusions, reports, schools, send, welfare)

    today = datetime.date.today()
    day = lambda n: (today - datetime.timedelta(days=n)).isoformat()
    admin = Principal("admin2", "admin", 1)
    notices = []

    def save(rt, values, rid=None):
        i = r.save(rt, values, record_id=rid, actor="test")
        notices.extend(r.take_notices())
        return i

    def board(school):
        return [[x["pupil"], x["reason"], x["label"], x["latest"]]
                for x in svc.notifications_from(school)]

    def dob_for(year):   # a date of birth in National Curriculum Year *year* now
        return datetime.date(D.school_year_start(today).year - 4 - year, 1, 15).isoformat()

    def child(first):
        return [c for c in r.list_records(children.CHILDREN) if c["first_name"] == first][0]

    # 1. secondary: attendance referral, with consent
    ben = SP.create_pupil({"legal_first_name": "Ben", "legal_last_name": "Hart",
                           "date_of_birth": dob_for(8), "gender": "Male",
                           "year_group": 8, "fsm_eligible": True}, actor=admin)
    t = svc.notify("secondary", str(ben.pupil_id), kind=svc.ATTENDANCE,
                   details={"attendance_pct": "84.5", "sessions_missed": "14",
                            "support_tried": "Daily check-ins, parent meetings"},
                   referrer="Attendance lead", consent=True)
    c = child("Ben")
    case = r.list_records(welfare.ATTENDANCE_CASES, learner_id=c["id"])[0]
    linked = schools.linked_school("secondary")
    j = identity_service.get(t["journey_id"])
    out["attendance"] = {
        "transition": t["status"],
        "child": [c["education"], schools.school_name(c["school_id"]), c["free_school_meals"],
                  bool(c["journey_id"]), c["school_id"] == linked],
        "case": [case["status"], case["attendance_pct"], case["source_system"],
                 case["transition_id"] == t["transition_id"], "check-ins" in case["barriers"]],
        "current": j.get("current_system"),
        "board": board("secondary")}
    save(welfare.ATTENDANCE_CASES, {"stage": "Attendance contract",
                                    "officer": "J Officer"}, case["id"])
    out["attendance"]["latest"] = board("secondary")[0][3]

    # 2. secondary: a suspension; the authority records the sixth-day provision
    t2 = svc.notify("secondary", str(ben.pupil_id), kind=svc.SUSPENSION,
                    details={"start_date": day(1), "days": "6",
                             "reason": "Persistent or general disruptive behaviour"})
    ex = r.list_records(exclusions.EXCLUSIONS, learner_id=c["id"])[0]
    save(exclusions.EXCLUSIONS, {"provision_from": day(0), "provision": "Hub"}, ex["id"])
    out["suspension"] = {"transition": t2["status"], "record": [ex["kind"], ex["days"]],
                         "children": len(r.list_records(children.CHILDREN)),
                         "latest": [n["note"] for n in svc.updates_for(t2["transition_id"])]}
    try:
        svc.notify("secondary", str(ben.pupil_id), kind=svc.SUSPENSION,
                   details={"start_date": day(0), "days": "0.3", "reason": "Theft"})
        out["suspension"]["bad_days"] = "accepted"
    except svc.LinkError as exc:
        out["suspension"]["bad_days"] = str(exc)

    # 3. primary: an EHC needs assessment request (no consent); the authority's
    #    decisions reach the school's SEN record
    ava = PP.create_pupil({"first_name": "Ava", "last_name": "Pike",
                           "date_of_birth": dob_for(4), "gender": "Female",
                           "year_group": "4", "sen_status": "K"})
    t3 = svc.notify("primary", ava.pupil_id, kind=svc.EHCNA,
                    details={"summary": "Not progressing", "tried": "Two cycles"})
    a = child("Ava")
    req = r.list_records(send.EHC_REQUESTS, learner_id=a["id"])[0]
    year = Y._slash_year(Y.current_academic_year())
    out["ehc"] = {"transition": t3["status"], "child_sen": a["sen_status"],
                  "request": [req["requested_by"], schools.school_name(req["setting_id"])],
                  "stage_requested": PSEND.get_for(ava.pupil_id, year).provision_stage}
    save(send.EHC_REQUESTS, {"received_on": day(60)}, req["id"])   # as if sent in time
    save(send.EHC_REQUESTS, {"assess_decision": "Agreed to assess", "decided_on": day(30)},
         req["id"])
    save(send.EHC_REQUESTS, {"plan_decision": "Issue a plan", "draft_issued_on": day(20)},
         req["id"])
    save(send.EHC_REQUESTS, {"final_issued_on": day(0)}, req["id"])
    out["ehc"]["final"] = [PP.get_pupil(ava.pupil_id).sen_status,
                           PSEND.get_for(ava.pupil_id, year).provision_stage,
                           r.get(children.CHILDREN, a["id"])["sen_status"]]
    out["ehc"]["board"] = board("primary")

    # 4. primary: a child missing education, found
    cal = PP.create_pupil({"first_name": "Cal", "last_name": "Moss",
                           "date_of_birth": dob_for(5), "gender": "Male", "year_group": "5"})
    svc.notify("primary", cal.pupil_id, kind=svc.CME,
               details={"reason": svc.CME_REASONS[1], "last_seen": day(15),
                        "enquiries": "Calls, home visit"})
    k = child("Cal")
    cme = r.list_records(welfare.CME, learner_id=k["id"])[0]
    out["cme"] = {"open": [cme["status"], cme["source"], r.get(children.CHILDREN,
                                                               k["id"])["education"]]}
    save(welfare.CME, {"status": "Found - on a school roll",
                       "found_school_id": schools.linked_school("primary")}, cme["id"])
    out["cme"]["latest"] = [x[3] for x in board("primary") if x[0] == "Cal Moss"][0]

    # 5. elective home education for Ben: the same child, now home educated
    svc.notify("secondary", str(ben.pupil_id), kind=svc.EHE,
               details={"notice_date": day(0)})
    out["ehe"] = [len([x for x in r.list_records(children.CHILDREN)
                       if x["first_name"] == "Ben"]),
                  r.get(children.CHILDREN, c["id"])["education"],
                  r.list_records(welfare.EHE, learner_id=c["id"])[0]["status"]]

    # 6. a school place at the linked primary: an accepted application there,
    #    enrolled -> on roll, the authority keeps its record
    prim = schools.linked_school("primary")
    dee = save(children.CHILDREN, {"first_name": "Dee", "last_name": "Rowe",
                                   "dob": dob_for(3), "education": "Not in education"})
    save(children.CONTACTS, {"learner_id": dee, "name": "Pat Rowe", "relationship": "Mother",
                             "phone": "01234 567890", "is_primary": 1})
    app = save(admissions.APPLICATIONS, {"learner_id": dee, "round": "In-year",
                                         "received_on": day(2), "pref1_id": prim})
    save(admissions.APPLICATIONS, {"status": "Offered", "offered_school_id": prim}, app)
    save(admissions.APPLICATIONS, {"status": "Accepted"}, app)
    la_app = r.get(admissions.APPLICATIONS, app)
    papp = [x for x in PA.list_applications() if x.transition_id][0]
    places = svc.places_for("primary")
    out["primary_place"] = {
        "linked": bool(la_app["place_transition_id"]),
        "application": [papp.status, papp.year_applying, papp.parent_name, papp.source,
                        papp.applicant_first],
        "board": [places[0]["pupil"], places[0]["label"], places[0]["place"].get("basis")]}
    _app, pupil = PA.enrol_application(papp.application_id)
    tid = la_app["place_transition_id"]
    jd = transitions.get_transition(tid)["journey_id"]
    open_systems = sorted(e["system"] for e in enrolments.list_enrolments(
        jd, include_closed=False))
    out["primary_place"]["enrolled"] = [
        transitions.get_transition(tid)["status"], pupil.journey_id == jd,
        open_systems, svc.places_for("primary")[0]["label"],
        identity_service.get(jd).get("current_system")]

    # 7. a place declined after acceptance: withdrawn at the school too
    eve = save(children.CHILDREN, {"first_name": "Eve", "last_name": "Long",
                                   "dob": dob_for(2), "education": "Not in education"})
    app2 = save(admissions.APPLICATIONS, {"learner_id": eve, "round": "In-year",
                                          "received_on": day(1), "pref1_id": prim})
    save(admissions.APPLICATIONS, {"status": "Offered", "offered_school_id": prim}, app2)
    save(admissions.APPLICATIONS, {"status": "Accepted"}, app2)
    t_eve = r.get(admissions.APPLICATIONS, app2)["place_transition_id"]
    save(admissions.APPLICATIONS, {"status": "Declined"}, app2)
    eve_app = [x for x in PA.list_applications() if x.transition_id == t_eve][0]
    out["declined"] = [transitions.get_transition(t_eve)["status"], eve_app.status,
                       r.get(admissions.APPLICATIONS, app2)["place_transition_id"]]

    # 8. a fair access place at the linked secondary: Incoming pupils, from LA
    sec = schools.linked_school("secondary")
    eli = save(children.CHILDREN, {"first_name": "Eli", "last_name": "Ford",
                                   "dob": dob_for(9), "education": "Not in education"})
    fa = save(admissions.FAIR_ACCESS, {"learner_id": eli, "referred_on": day(3),
                                       "category": "Homeless"})
    save(admissions.FAIR_ACCESS, {"decision": "Allocated", "school_id": sec,
                                  "panel_on": day(1)}, fa)
    ftid = r.get(admissions.FAIR_ACCESS, fa)["place_transition_id"]
    item = INC.get(ftid, actor=admin)
    defaults = INC.new_pupil_defaults(ftid, actor=admin)
    made = INC.create_pupil(ftid, {"gender": "Male", "form_group": ""}, actor=admin)
    done = INC.complete(ftid, actor=admin)
    fj = transitions.get_transition(ftid)["journey_id"]
    out["secondary_place"] = {
        "queued": [item.from_la, item.tag, item.source_label],
        "year": defaults["year_group"], "pupil": made.pupil.year_group,
        "done": done.status,
        "open": sorted(e["system"] for e in enrolments.list_enrolments(
            fj, include_closed=False))}

    # 9. the authority's School Notifications page
    out["report"] = sorted({i.what for i in reports.school_notifications()})

    # 10. a child no school sent: nothing goes anywhere
    before = len(notices)
    zed = save(children.CHILDREN, {"first_name": "Zed", "last_name": "Quinn",
                                   "dob": dob_for(6), "education": "Not in education"})
    save(send.EHC_REQUESTS, {"learner_id": zed, "received_on": day(0),
                             "requested_by": "Parent"})
    save(welfare.ATTENDANCE_CASES, {"learner_id": zed, "referred_on": day(0)})
    out["unlinked_notices"] = notices[before:]
    out["notices"] = notices
    print("RESULT" + json.dumps(out, default=str))
''')


@pytest.fixture(scope="module")
def flow(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("la_link")
    env = {**os.environ, **{f"EDU_{k}_DATA_DIR": str(root / k.lower()) for k in _DIRS}}
    env.pop("EDU_DEV_SEED", None)
    done = subprocess.run([sys.executable, "-c", SCRIPT], env=env, capture_output=True,
                          text=True, timeout=600)
    line = next((ln for ln in done.stdout.splitlines() if ln.startswith("RESULT")), None)
    assert line, f"flow failed:\n{done.stdout[-3000:]}\n{done.stderr[-5000:]}"
    result = json.loads(line[len("RESULT"):])
    assert result["auth_db"].startswith(str(root)), "auth.db was not isolated"
    return result


def test_attendance_referral_opens_a_case_alongside_the_school_place(flow):
    a = flow["attendance"]
    assert a["transition"] == "completed"
    assert a["child"] == ["At school", "Secondary School", 1, True, True]
    assert a["case"] == ["Open", 84.5, "secondary", True, True]
    assert a["current"] == "secondary"           # the authority isn't where they're taught
    assert a["board"][0][2] == "With the LA"
    assert a["latest"].startswith("attendance case: attendance contract")


def test_suspension_and_provision_go_back_to_the_school(flow):
    s = flow["suspension"]
    assert s["transition"] == "completed"
    assert s["record"] == ["Suspension", 6.0]
    assert s["children"] == 1                     # the same child, not a second record
    assert any("full-time provision from" in n for n in s["latest"])
    assert "halves" in s["bad_days"]


def test_ehc_decisions_reach_the_primary_sen_record(flow):
    e = flow["ehc"]
    assert e["transition"] == "completed"
    assert e["child_sen"] == "EHC needs assessment"
    assert e["request"] == ["School / college", "Primary School"]
    assert e["stage_requested"] == "EHCP assessment in progress"
    assert e["final"] == ["E", "EHCP (Education, Health, Care Plan)", "EHC plan"]
    assert e["board"][0][3].startswith("EHC plan issued")


def test_child_missing_education(flow):
    assert flow["cme"]["open"] == ["Open", "School (unexplained absence)", "Not in education"]
    assert flow["cme"]["latest"].startswith("missing education case: found - on a school roll")


def test_home_education_is_the_same_child(flow):
    assert flow["ehe"] == [1, "Elective home education", "Active"]


def test_primary_place_is_an_accepted_application_then_on_roll(flow):
    p = flow["primary_place"]
    assert p["linked"] is True
    assert p["application"] == ["accepted", "3", "Pat Rowe", "local_authority", "Dee"]
    assert p["board"] == ["Dee Rowe", "Place allocated - to admit", "1st preference"]
    status, linked, open_systems, label, current = p["enrolled"]
    assert (status, linked, label, current) == ("completed", True, "On roll", "primary")
    assert open_systems == ["local_authority", "primary"]   # the authority keeps its record


def test_declined_place_is_withdrawn_at_the_school(flow):
    assert flow["declined"] == ["cancelled", "withdrawn", None]


def test_secondary_place_lands_in_incoming_pupils(flow):
    s = flow["secondary_place"]
    assert s["queued"] == [True, " (from LA)", "Local authority (school place)"]
    assert s["year"] == 9 and s["pupil"] == 9
    assert s["done"] == "completed"
    assert s["open"] == ["local_authority", "secondary"]


def test_school_notifications_page(flow):
    assert flow["report"] == [
        "Attendance referral", "Child missing education", "EHC needs assessment request",
        "Elective home education", "School place handed over (In-year)",
        "School place handed over (fair access)", "Suspension"]


def test_children_no_school_sent_stay_local(flow):
    assert flow["unlinked_notices"] == []


def test_no_platform_failures_were_swallowed(flow):
    assert not [n for n in flow["notices"] if n.startswith("Saved, but")]
    assert not [n for n in flow["notices"] if "couldn't" in n]
