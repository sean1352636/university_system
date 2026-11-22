"""The SEND service linked to the Primary and Secondary schools.

A school's request (SEND advice, or an EHC needs assessment request) opens
a case at the SEND service alongside the school place; the service's EHCP
decisions come back onto the school's SEN record; archiving closes the case.

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
    for key in ("primary", "secondary", "special_education"):
        L._register_phase_adapter(key)

    from education_system.platform.cross_system import send_referrals as svc
    from education_system.systems.primary.domain.learners.pupils import pupils as PP
    from education_system.systems.primary.domain.learners.pupils import year6_transition as Y
    from education_system.systems.primary.domain.pastoral.send import send as PSEND
    from education_system.systems.secondary.modules.pupils.domain import pupils as SP
    from education_system.systems.secondary.modules.send.domain import send as SSEND
    from education_system.systems.secondary.core.permissions.access import Principal
    from education_system.systems.special_education.core import records as r
    from education_system.systems.special_education.modules import ehcp, learners, requests

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
                for x in svc.requests_from(school)]

    # 1. secondary: an EHC needs assessment request, with consent
    ben = SP.create_pupil({"legal_first_name": "Ben", "legal_last_name": "Hart",
                           "date_of_birth": "2013-01-10", "gender": "Male",
                           "year_group": 8}, actor=admin)
    SSEND.save_record(ben.pupil_id, {"stage": SSEND.SUPPORT, "primary_need": "ASD"},
                      actor=admin)
    t = svc.refer("secondary", str(ben.pupil_id), request=svc.EHCNA,
                  summary="Not progressing", tried="Two SEN support cycles",
                  referrer="SENCO", consent=True)
    lrn = r.list_records(learners.LEARNERS)[0]
    req = r.list_records(requests.SCHOOL_REQUESTS)[0]
    plan = r.list_records(ehcp.EHCPS)[0]
    rec = SSEND.get(ben.pupil_id)
    out["request"] = {
        "transition": t["status"],
        "learner": [lrn["year_group"], lrn["setting"], lrn["sen_status"],
                    lrn["primary_need"], bool(lrn["journey_id"])],
        "school_request": [req["request"], req["status"], req["source_system"],
                           req["consent_to_share"]],
        "ehcp": plan["stage"],
        "school": [rec.sen_status, rec.ehcna_status],
        "board": board("secondary")}

    # 2. the EHCP runs its course
    save(ehcp.EHCPS, {"request_date": day(60)}, plan["id"])
    save(ehcp.EHCPS, {"stage": "Assessing", "decision_date": day(40)}, plan["id"])
    out["assessing"] = SSEND.get(ben.pupil_id).ehcna_status
    save(ehcp.EHCPS, {"draft_date": day(20)}, plan["id"])
    save(ehcp.EHCPS, {"final_date": day(0)}, plan["id"])
    rec = SSEND.get(ben.pupil_id)
    out["final"] = [rec.sen_status, rec.ehcna_status, rec.ehcna_plan_on,
                    rec.ehcp_issued_on]
    save(ehcp.REVIEWS, {"ehcp_id": plan["id"], "meeting_date": day(0),
                        "recommendation": "Maintain"})
    save(ehcp.EHCPS, {"stage": "Ceased", "cease_date": day(0)}, plan["id"])
    out["ceased"] = SP.get_pupil(ben.pupil_id).sen_status
    out["updates"] = [n["note"] for n in svc.updates_for(t["transition_id"])]

    # 3. archived, then a new request re-opens the same learner
    save(learners.LEARNERS, {"status": "Archived"}, lrn["id"])
    out["archived_label"] = board("secondary")[0][2]
    t2 = svc.refer("secondary", str(ben.pupil_id), request=svc.ADVICE, summary="Advice")
    out["reopened"] = [t2["status"], r.get(learners.LEARNERS, lrn["id"])["status"],
                       len(r.list_records(learners.LEARNERS))]
    out["board_after"] = [row[2] for row in board("secondary")]

    # 4. primary: advice without consent; the service opens an EHCP itself
    ava = PP.create_pupil({"first_name": "Ava", "last_name": "Pike",
                           "date_of_birth": "2017-03-02", "gender": "Female",
                           "year_group": "4", "sen_status": "K"})
    t3 = svc.refer("primary", ava.pupil_id, request=svc.ADVICE, summary="Reading",
                   referrer="Head")
    alrn = [x for x in r.list_records(learners.LEARNERS) if x["first_name"] == "Ava"][0]
    out["primary"] = {"transition": t3["status"],
                      "learner": [alrn["year_group"], alrn["setting"],
                                  len(r.list_records(ehcp.EHCPS, learner_id=alrn["id"]))]}
    p2 = save(ehcp.EHCPS, {"learner_id": alrn["id"], "request_date": day(60),
                           "stage": "Requested"})
    year = Y._slash_year(Y.current_academic_year())
    out["primary"]["stage_requested"] = PSEND.get_for(ava.pupil_id, year).provision_stage
    save(ehcp.EHCPS, {"stage": "Assessing", "decision_date": day(40),
                      "draft_date": day(20), "final_date": day(0)}, p2)
    out["primary"]["final"] = [PP.get_pupil(ava.pupil_id).sen_status,
                               PSEND.get_for(ava.pupil_id, year).provision_stage]
    out["primary"]["board"] = board("primary")

    # 5. a learner no school sent: nothing goes anywhere
    before = len(notices)
    u = save(learners.LEARNERS, {"first_name": "Zed", "last_name": "Quinn",
                                 "dob": "2015-01-01", "sen_status": "SEN Support"})
    save(ehcp.EHCPS, {"learner_id": u, "request_date": day(0), "stage": "Requested"})
    out["unlinked_notices"] = notices[before:]
    out["notices"] = notices
    print("RESULT" + json.dumps(out))
''')


@pytest.fixture(scope="module")
def flow(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("send_link")
    env = {**os.environ, **{f"EDU_{k}_DATA_DIR": str(root / k.lower()) for k in _DIRS}}
    env.pop("EDU_DEV_SEED", None)
    done = subprocess.run([sys.executable, "-c", SCRIPT], env=env, capture_output=True,
                          text=True, timeout=600)
    line = next((ln for ln in done.stdout.splitlines() if ln.startswith("RESULT")), None)
    assert line, f"flow failed:\n{done.stdout[-3000:]}\n{done.stderr[-5000:]}"
    result = json.loads(line[len("RESULT"):])
    assert result["auth_db"].startswith(str(root)), "auth.db was not isolated"
    return result


def test_request_opens_a_case_alongside_the_school_place(flow):
    req = flow["request"]
    assert req["transition"] == "completed"
    assert req["learner"] == ["Year 8", "Secondary School", "SEN Support",
                              "ASD - Autistic spectrum disorder", True]
    assert req["school_request"] == ["EHC needs assessment request", "New", "secondary", 1]
    assert req["ehcp"] == "Requested"
    assert req["school"] == ["K", "Requested"]      # still SEN support, on the school roll
    assert req["board"][0][2] == "Open case"


def test_ehcp_decisions_reach_the_school_send_register(flow):
    assert flow["assessing"] == "Agreed to assess"
    sen, ehcna, plan_on, issued = flow["final"]
    assert (sen, ehcna) == ("E", "Plan issued")
    assert plan_on and issued == plan_on
    assert flow["ceased"] == "K"


def test_the_school_sees_each_update(flow):
    notes = flow["updates"]
    assert any("agreed to assess" in n for n in notes)
    assert any("EHC plan issued" in n for n in notes)
    assert any("annual review held" in n for n in notes)
    assert notes[-1].startswith("SEND service: EHC plan ceased")


def test_archiving_closes_the_case_and_a_new_request_reopens_it(flow):
    assert flow["archived_label"] == "Case closed"
    assert flow["reopened"] == ["completed", "Active", 1]   # same learner, no duplicate
    assert flow["board_after"] == ["Open case", "Case closed"]


def test_primary_request_and_plan(flow):
    p = flow["primary"]
    assert p["transition"] == "completed"
    assert p["learner"] == ["Year 4", "Primary School", 0]   # advice: no EHCP opened
    assert p["stage_requested"] == "EHCP assessment in progress"
    assert p["final"] == ["E", "EHCP (Education, Health, Care Plan)"]
    assert p["board"][0][3].startswith("EHC plan issued")


def test_learners_no_school_sent_stay_local(flow):
    assert flow["unlinked_notices"] == []


def test_no_platform_failures_were_swallowed(flow):
    assert not [n for n in flow["notices"] if n.startswith("Saved, but")]
    assert not [n for n in flow["notices"] if "couldn't" in n]
