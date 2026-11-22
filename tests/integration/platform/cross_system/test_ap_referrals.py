"""Alternative Provision linked to the Primary and Secondary schools.

School → AP referral (dual or sole registration), the AP's decision and
placement flowing back to the school, and the AP sending the pupil back
(home school, a new primary / secondary admission, or leaving).

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
    import datetime, json, sys
    from education_system import paths
    out = {"auth_db": str(paths.PLATFORM_AUTH_DB_FILE)}
    from education_system.platform.identity.auth.schema import initialise_auth_db
    paths.PLATFORM_DB_FILES_DIR.mkdir(parents=True, exist_ok=True)
    initialise_auth_db(str(paths.PLATFORM_AUTH_DB_FILE))
    import education_system.launcher.systems as L
    for key in ("primary", "secondary", "alternative_provision"):
        L._register_phase_adapter(key)

    from education_system.platform.cross_system import ap_referrals as svc, transitions
    from education_system.systems.primary.domain.learners.pupils import pupils as PP
    from education_system.systems.secondary.modules.pupils.domain import pupils as SP
    from education_system.systems.secondary.core.permissions.access import Principal
    from education_system.systems.secondary.modules.progression.domain import (
        incoming_primary as IP)
    from education_system.systems.alternative_provision.core import records as r
    from education_system.systems.alternative_provision.infrastructure import database as apdb
    from education_system.systems.alternative_provision.modules import (
        behaviour, learners, placements, referrals, reintegration)

    today = datetime.date.today().isoformat()
    admin = Principal("admin2", "admin", 1)
    notices = []

    def save(rt, values, rid=None):
        i = r.save(rt, values, record_id=rid, actor="test")
        notices.extend(r.take_notices())
        return i

    def ap_ref(tid):
        with apdb.connect() as c:
            return dict(c.execute("SELECT * FROM referrals WHERE transition_id = ?",
                                  (tid,)).fetchone())

    def status(tid):
        return transitions.get_transition(tid)["status"]

    def place(ref, registration, start=today):
        return save(placements.PLACEMENTS, {
            "learner_id": ref["learner_id"], "provider_id": prov, "referral_id": ref["id"],
            "start_date": start, "hours_per_week": 25, "registration": registration,
            "status": "Active"})

    def reintegrate(ref, where):
        save(reintegration.REINTEGRATION, {
            "learner_id": ref["learner_id"], "target_school": "School", "return_to": where,
            "readiness": reintegration.READINESS[0], "status": "Completed",
            "full_return": today})

    prov = save(placements.PROVIDERS, {"name": "Bridge PRU", "kind": placements.KINDS[0]})

    # 1. primary, dual registration, back to the home school
    ava = PP.create_pupil({"first_name": "Ava", "last_name": "Pike",
                           "date_of_birth": "2016-03-02", "gender": "Female",
                           "year_group": "5"})
    t = svc.refer("primary", ava.pupil_id, reason=svc.REASONS[2], referrer="Head",
                  consent=True)
    ref = ap_ref(t["transition_id"])
    out["dual"] = {"after_refer": t["status"], "ap_status": ref["status"],
                   "ap_registration": ref["registration"], "source": ref["source_system"]}
    save(referrals.REFERRALS, {"status": "Accepted"}, ref["id"])
    out["dual"]["after_accept"] = status(t["transition_id"])
    place(ref, "Dual registration")
    out["dual"]["after_place"] = status(t["transition_id"])
    out["dual"]["school_roll"] = PP.get_pupil(ava.pupil_id).roll_status
    out["dual"]["label_placed"] = svc.referrals_from("primary")[0]["label"]
    reintegrate(ref, reintegration.RETURN_TO[0])
    out["dual"]["ap_after_return"] = r.get(learners.LEARNERS, ref["learner_id"])["status"]
    out["dual"]["label_after_return"] = svc.referrals_from("primary")[0]["label"]

    # 2. secondary, sole (permanent exclusion): refused, retried, placed, back as new
    ben = SP.create_pupil({"legal_first_name": "Ben", "legal_last_name": "Hart",
                           "date_of_birth": "2011-01-10", "gender": "Male",
                           "year_group": 9}, actor=admin)
    try:
        svc.refer("secondary", str(ben.pupil_id), reason=svc.REASONS[0],
                  registration=svc.SOLE, excluded_from=today, referrer="Head")
        out["refused"] = None
    except svc.ReferralError as exc:
        out["refused"] = str(exc)
    SP.update_pupil(ben.pupil_id, {"year_group": 11}, actor=admin)
    t2 = svc.refer("secondary", str(ben.pupil_id), reason=svc.REASONS[0],
                   registration=svc.SOLE, excluded_from=today, referrer="Head")
    ref2 = ap_ref(t2["transition_id"])
    out["sole"] = {"after_retry": t2["status"], "ap_registration": ref2["registration"]}
    save(referrals.REFERRALS, {"status": "Accepted"}, ref2["id"])
    before = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    place(ref2, "Single registration", start=before)   # before the pupil's admission
    out["sole"]["after_refused_close"] = status(t2["transition_id"])
    out["sole"]["roll_after_refused_close"] = SP.get_pupil(ben.pupil_id).roll_status
    with apdb.connect() as c:
        pid = c.execute("SELECT id FROM placements WHERE referral_id = ?",
                        (ref2["id"],)).fetchone()[0]
    save(placements.PLACEMENTS, {"start_date": today}, pid)
    out["sole"]["after_retry_place"] = status(t2["transition_id"])
    out["sole"]["school_roll"] = SP.get_pupil(ben.pupil_id).roll_status
    reintegrate(ref2, reintegration.RETURN_TO[2])
    incoming = [i for i in IP.queue(actor=admin, include_closed=True) if i.from_ap]
    out["sole"]["incoming"] = [(i.source_label, i.status) for i in incoming]
    made = IP.create_pupil(incoming[0].transition_id, actor=admin, allow_duplicate=True)
    out["sole"]["new_pupil"] = {"year": made.pupil.year_group,
                                "roll": made.pupil.roll_status,
                                "note": made.pupil.notes}

    # 3. declined
    cal = SP.create_pupil({"legal_first_name": "Cal", "legal_last_name": "Dunn",
                           "date_of_birth": "2013-05-10", "gender": "Male",
                           "year_group": 9}, actor=admin)
    t3 = svc.refer("secondary", str(cal.pupil_id), reason=svc.REASONS[2], referrer="Head")
    ref3 = ap_ref(t3["transition_id"])
    save(referrals.REFERRALS, {"status": "Declined", "decision_reason": "No places"},
         ref3["id"])
    row = [x for x in svc.referrals_from("secondary")
           if x["transition_id"] == t3["transition_id"]][0]
    out["declined"] = {"label": row["label"], "reason": row.get("decision_reason")}

    # 4. primary, sole, back to the same primary as a re-admission
    dee = PP.create_pupil({"first_name": "Dee", "last_name": "Moss",
                           "date_of_birth": "2017-02-02", "gender": "Female",
                           "year_group": "4"})
    t4 = svc.refer("primary", dee.pupil_id, reason=svc.REASONS[4], registration=svc.SOLE,
                   referrer="Head", consent=True)
    ref4 = ap_ref(t4["transition_id"])
    save(referrals.REFERRALS, {"status": "Accepted"}, ref4["id"])
    place(ref4, "Single registration")
    out["readmit"] = {"roll_after_place": PP.get_pupil(dee.pupil_id).roll_status}
    reintegrate(ref4, reintegration.RETURN_TO[1])
    out["readmit"]["records"] = [
        (p.pupil_id == dee.pupil_id, p.year_group, p.roll_status)
        for p in PP.list_pupils(include_off_roll=True) if p.last_name == "Moss"]

    # 5. permanently excluded from the AP while dual registered
    eli = PP.create_pupil({"first_name": "Eli", "last_name": "Ross",
                           "date_of_birth": "2016-07-07", "gender": "Male",
                           "year_group": "5"})
    t5 = svc.refer("primary", eli.pupil_id, reason=svc.REASONS[2], referrer="Head")
    ref5 = ap_ref(t5["transition_id"])
    save(referrals.REFERRALS, {"status": "Accepted"}, ref5["id"])
    place(ref5, "Dual registration")
    save(behaviour.SUSPENSIONS, {"learner_id": ref5["learner_id"],
                                 "kind": "Permanent exclusion", "start_date": today,
                                 "reason": behaviour.EXCLUSION_REASONS[0],
                                 "decided_by": "Head", "status": "Confirmed"})
    out["ap_exclusion"] = {
        "ap": r.get(learners.LEARNERS, ref5["learner_id"])["status"],
        "school_roll": PP.get_pupil(eli.pupil_id).roll_status,
        "label": [x for x in svc.referrals_from("primary")
                  if x["transition_id"] == t5["transition_id"]][0]["label"]}
    out["notices"] = notices
    print("RESULT" + json.dumps(out))
''')


@pytest.fixture(scope="module")
def flow(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("ap_link")
    env = {**os.environ, **{f"EDU_{k}_DATA_DIR": str(root / k.lower()) for k in _DIRS}}
    env.pop("EDU_DEV_SEED", None)
    done = subprocess.run([sys.executable, "-c", SCRIPT], env=env, capture_output=True,
                          text=True, timeout=600)
    line = next((ln for ln in done.stdout.splitlines() if ln.startswith("RESULT")), None)
    assert line, f"flow failed:\n{done.stdout[-3000:]}\n{done.stderr[-5000:]}"
    result = json.loads(line[len("RESULT"):])
    assert result["auth_db"].startswith(str(root)), "auth.db was not isolated"
    return result


def test_dual_referral_reaches_the_ap_and_flows_back(flow):
    d = flow["dual"]
    assert d["after_refer"] == "offered"
    assert (d["ap_status"], d["ap_registration"], d["source"]) == ("New", "Dual", "primary")
    assert d["after_accept"] == "handover_approved"
    assert d["after_place"] == "completed"
    assert d["school_roll"] == "on_roll"          # dual: stays on the school's roll
    assert d["label_placed"] == "Placed"
    assert d["ap_after_return"] == "Reintegrated"
    assert d["label_after_return"] == "Left the AP"


def test_a_referral_the_ap_refuses_can_be_sent_again(flow):
    assert flow["refused"] and "send it again" in flow["refused"]
    assert flow["sole"]["after_retry"] == "offered"
    assert flow["sole"]["ap_registration"] == "Sole"


def test_sole_placement_waits_for_the_school_to_record_the_leaver(flow):
    s = flow["sole"]
    assert s["after_refused_close"] == "admitted"
    assert s["roll_after_refused_close"] == "on_roll"
    assert s["after_retry_place"] == "completed"
    assert s["school_roll"] == "left"


def test_ap_return_to_secondary_arrives_on_incoming(flow):
    s = flow["sole"]
    assert s["incoming"] == [["Alternative provision", "handover_approved"]]
    assert s["new_pupil"]["year"] == 11
    assert s["new_pupil"]["roll"] == "on_roll"
    assert "alternative provision" in s["new_pupil"]["note"]


def test_declined_referral_shows_the_reason_to_the_school(flow):
    assert flow["declined"] == {"label": "Declined", "reason": "No places"}


def test_ap_return_to_the_same_primary_reopens_the_record(flow):
    assert flow["readmit"]["roll_after_place"] == "left"
    assert flow["readmit"]["records"] == [[True, "4", "on_roll"]]   # one record, reopened


def test_permanent_exclusion_from_the_ap_closes_only_the_ap_record(flow):
    assert flow["ap_exclusion"] == {"ap": "Left", "school_roll": "on_roll",
                                    "label": "Left the AP"}


def test_no_platform_failures_were_swallowed(flow):
    failed = [n for n in flow["notices"] if n.startswith("Saved, but")]
    # The one expected failure: the sole placement starting before admission.
    assert len(failed) == 1 and "leaver" in failed[0]
