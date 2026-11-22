"""Year 6 Transition planning (modules.progression.domain.year6_transition).

Like test_incoming_primary: the real platform transfer queue runs against a
temporary auth.db (passed as ``db_path`` and patched as the platform
default) and the test plays the primary school's part with the platform's
own calls, so neither the live platform DB nor the primary system is touched.
"""

from __future__ import annotations

import csv

import pytest

from education_system.platform.cross_system import identity_service as IDS
from education_system.platform.cross_system import transitions as T
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.database import connection as database
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.modules.admissions.domain import admissions as AD
from education_system.systems.secondary.modules.assessment.domain import headline_measures as HM
from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.progression.domain import incoming_primary as IP
from education_system.systems.secondary.modules.progression.domain import year6_allocation as YA
from education_system.systems.secondary.modules.progression.domain import year6_events as YE
from education_system.systems.secondary.modules.progression.domain import year6_transition as Y6
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="ann", role="teacher")
PARENT = Principal(username="mum", role="parent")
YEAR = "2026/27"


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
    yield platform_db
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _transfer(db, first, last, dob, sid, *, gender="Female", report=None, sen="N",
              pp=False, school="Oak Primary"):
    """Primary's side: a journey, a transfer to secondary, an approved handover."""
    jid = IDS.get_or_create_journey(first_name=first, last_name=last, date_of_birth=dob,
                                    system="primary", student_id=sid, db_path=db)
    t = T.start_transition(journey_id=jid, source_system="primary",
                           destination_system="secondary", effective_date="2026-09-03",
                           db_path=db)
    T.approve_handover(t["transition_id"], {
        "child_identity": {"first_name": first, "last_name": last, "date_of_birth": dob,
                           "gender": gender, "school_name": school,
                           "address_line1": "1 High Street", "town": "Leeds",
                           "postcode": "LS1 1AA"},
        "guardians": [{"name": f"Pat {last}", "relationship": "Mother",
                       "email": "pat@example.com", "phone": "07700 900123",
                       "parental_responsibility": True}],
        "ks2_results": {"reading_scaled": 108, "maths_scaled": 101},
        "send_provision": {"sen_status": sen, "ehcp": sen == "E"},
        "support_indicators": {"pupil_premium": pp, "fsm": pp, "lac": False, "plac": False,
                               "eal": False},
        "transition_report": report or {},
    }, db_path=db)
    return t["transition_id"]


def _offer(first="Sam", last="Lee", dob="2015-03-03"):
    AD.set_pan(YEAR, 7, 180, actor=ADMIN)
    app = AD.create_application({
        "route": "normal_round", "academic_year": YEAR, "year_group": 7,
        "legal_first_name": first, "legal_last_name": last, "date_of_birth": dob,
        "gender": "Male", "parent_name": "Jo Lee", "parent_relationship": "Father",
        "parent_email": "jo@example.com", "current_school": "Elm School"}, actor=ADMIN)
    app = getattr(app, "application", app)
    AD.offer(app.application_id, actor=ADMIN)
    return app.application_id


@pytest.fixture
def cohort(env):
    _transfer(env, "Mia", "Patel", "2015-02-10", "P1", sen="K", pp=True,
              report={"friendships": ["Leo Hart"], "keep_apart": ["Zoe"],
                      "enhanced_transition": True, "enhanced_reason": "anxious",
                      "strengths": "art"})
    _transfer(env, "Leo", "Hart", "2015-05-05", "P2", gender="Male")
    _transfer(env, "Zoe", "King", "2015-06-06", "P3")
    _offer()
    out = Y6.sync(YEAR, actor=ADMIN, db_path=env)
    return {r.first_name: r for r in Y6.cohort(YEAR, actor=ADMIN)}, out


def test_sync_builds_cohort_from_platform_and_admissions(env, cohort):
    rows, out = cohort
    assert (out["platform"], out["admissions"], out["new"]) == (3, 1, 4)
    assert rows["Sam"].source == "admissions" and rows["Sam"].feeder_school == "Elm School"
    assert rows["Mia"].feeder_school == "Oak Primary" and rows["Mia"].ks2_band == "Expected"
    assert out == {**out, "report_names": 2, "resolved": 2}
    again = Y6.sync(YEAR, actor=ADMIN, db_path=env)
    assert again["new"] == 0 and len(Y6.cohort(YEAR, actor=ADMIN)) == 4
    feeders = {d["school"]: d for d in Y6.feeder_schools(YEAR, actor=ADMIN)}
    assert feeders["Oak Primary"]["expected"] == 3 and feeders["Elm School"]["admissions"] == 1


def test_flags_are_masked_by_role(env, cohort):
    rows, _ = cohort
    assert rows["Mia"].sen_status == "K" and rows["Mia"].pupil_premium is True
    teacher = {r.first_name: r for r in Y6.cohort(YEAR, actor=TEACHER)}
    assert teacher["Mia"].sen_status is None and teacher["Mia"].pupil_premium is None
    assert teacher["Mia"].safeguarding is None
    assert teacher["Mia"].enhanced           # the flag itself is for all staff
    assert "SEN support" not in teacher["Mia"].enhanced_reasons
    assert "SEN support" in rows["Mia"].enhanced_reasons
    with pytest.raises(Y6.PermissionDenied):
        Y6.cohort(YEAR, actor=PARENT)
    with pytest.raises(Y6.PermissionDenied):
        Y6.sync(YEAR, actor=TEACHER, db_path=env)
    assert Y6.feeder_schools(YEAR, actor=TEACHER)[0]["sen"] is None


def test_report_prefills_friendships_and_keep_apart(env, cohort):
    rows, _ = cohort
    rels = Y6.relationships(YEAR, actor=ADMIN, cohort_id=rows["Mia"].cohort_id)
    got = {(r["kind"], r["other_cohort_id"]) for r in rels}
    assert got == {("friend", rows["Leo"].cohort_id), ("keep_apart", rows["Zoe"].cohort_id)}
    rep = Y6.transition_report(rows["Mia"].cohort_id, actor=TEACHER, db_path=env)
    assert rep["strengths"] == "art" and "anxious" in Y6.report_text(rep)
    with pytest.raises(Y6.ValidationError):           # already keep-apart
        Y6.add_relationship(rows["Mia"].cohort_id, "friend", actor=ADMIN,
                            other_cohort_id=rows["Zoe"].cohort_id)
    rid = Y6.add_relationship(rows["Leo"].cohort_id, "friend", actor=ADMIN,
                              other_cohort_id=rows["Sam"].cohort_id)
    Y6.remove_relationship(rid, actor=ADMIN)
    with pytest.raises(Y6.PermissionDenied):
        Y6.add_relationship(rows["Leo"].cohort_id, "friend", actor=TEACHER,
                            other_cohort_id=rows["Sam"].cohort_id)


def test_auto_suggest_honours_keep_apart_and_a_friendship(env, cohort):
    rows, _ = cohort
    with pytest.raises(Y6.ValidationError, match="form groups"):
        YA.suggest(YEAR, actor=ADMIN)
    for name in ("7A", "7B"):
        FG.create({"name": name, "year_group": 7, "capacity": 30}, actor=ADMIN)
    s = YA.suggest(YEAR, actor=ADMIN)
    mia, leo, zoe = (rows[n].cohort_id for n in ("Mia", "Leo", "Zoe"))
    assert s.plan[mia] == s.plan[leo] != s.plan[zoe]
    assert len(s.plan) == 4 and not s.unplaced
    YA.apply_plan(YEAR, s.plan, actor=ADMIN)
    assert not [w for w in YA.warnings(YEAR, actor=ADMIN) if w["level"] == "bad"]
    YA.move(zoe, s.plan[mia], actor=ADMIN)
    assert any(w["kind"] == "keep_apart" for w in YA.warnings(YEAR, actor=ADMIN))
    with pytest.raises(Y6.ValidationError, match="keep-apart"):
        YA.publish(YEAR, actor=ADMIN)
    YA.move(zoe, s.plan[zoe], actor=ADMIN)
    assert Y6.get(zoe, actor=ADMIN).form_how == "manual"
    YA.publish(YEAR, actor=ADMIN)
    with pytest.raises(Y6.ValidationError, match="published"):
        YA.move(zoe, None, actor=ADMIN)
    with pytest.raises(Y6.ValidationError):
        YA.unpublish(YEAR, actor=ADMIN, reason=" ")
    YA.unpublish(YEAR, actor=ADMIN, reason="late joiner")
    YA.move(zoe, None, actor=ADMIN)


def test_events_invitations_and_register(env, cohort, tmp_path):
    rows, _ = cohort
    with pytest.raises(Y6.ValidationError):
        YE.create_event(YEAR, {"event_type": "Disco", "event_date": "2026-07-01",
                               "audience": "Whole cohort"}, actor=ADMIN)
    with pytest.raises(Y6.ValidationError, match="end time"):
        YE.create_event(YEAR, {"event_type": "Induction day", "event_date": "2026-07-01",
                               "start_time": "15:00", "end_time": "09:00",
                               "audience": "Whole cohort"}, actor=ADMIN)
    eid = YE.create_event(YEAR, {"event_type": "Induction day", "event_date": "2026-07-01",
                                 "start_time": "09:00", "end_time": "15:00",
                                 "audience": "Whole cohort"}, actor=ADMIN)
    assert YE.invite(eid, actor=ADMIN) == 4
    assert YE.invite(eid, actor=ADMIN) == 0
    YE.mark(eid, [rows["Mia"].cohort_id], "attended", actor=ADMIN)
    reg = {d["row"].first_name: d["attendance"] for d in YE.register(eid, actor=TEACHER)}
    assert reg["Mia"] == "attended" and reg["Leo"] == "invited"
    assert ("Attended an induction / taster event", True) in Y6.checklist(
        rows["Mia"].cohort_id, actor=ADMIN)
    enh = YE.create_event(YEAR, {"event_type": "Enhanced transition visit",
                                 "event_date": "2026-06-20",
                                 "audience": "Enhanced transition group"}, actor=ADMIN)
    assert YE.invite(enh, actor=ADMIN) == 1                       # Mia only
    path = tmp_path / "reg.csv"
    assert YE.export_register(eid, path, actor=TEACHER) == 4
    assert list(csv.reader(open(path, encoding="utf-8")))[1][0] == "surname"
    YE.delete_event(eid, actor=ADMIN)
    assert [e["event_id"] for e in YE.events(YEAR, actor=ADMIN)] == [enh]


def test_liaison_and_enhanced_plan(env, cohort):
    rows, _ = cohort
    with pytest.raises(Y6.ValidationError):
        Y6.add_liaison(YEAR, {"school": "Oak Primary", "kind": "Visit to primary",
                              "held_on": "2026-06-01"}, actor=ADMIN)   # no summary
    Y6.add_liaison(YEAR, {"school": "Oak Primary", "kind": "Visit to primary",
                          "held_on": "2026-06-01", "summary": "Met the Y6 team"}, actor=ADMIN)
    Y6.add_liaison(YEAR, {"kind": "Y6 teacher conversation", "held_on": "2026-06-02",
                          "summary": "Quiet, loves art"}, actor=ADMIN,
                   cohort_id=rows["Mia"].cohort_id)
    oak = next(d for d in Y6.feeder_schools(YEAR, actor=ADMIN) if d["school"] == "Oak Primary")
    assert oak["contacts"] == 1 and oak["last_contact"] == "2026-06-01"
    notes = Y6.liaison(YEAR, actor=TEACHER, cohort_id=rows["Mia"].cohort_id)
    assert notes[0]["school"] == "Oak Primary"
    enh = {d["row"].first_name: d for d in Y6.enhanced(YEAR, actor=ADMIN)}
    assert set(enh) == {"Mia"}
    Y6.set_plan(rows["Mia"].cohort_id, {"status": "Plan agreed", "extra_visits": "2",
                                        "key_adult": "Ms Khan", "social_story_sent": True},
                actor=ADMIN)
    with pytest.raises(Y6.PermissionDenied):
        Y6.set_plan(rows["Mia"].cohort_id, {"status": "Completed"}, actor=TEACHER)
    Y6.add_to_enhanced(rows["Sam"].cohort_id, actor=ADMIN, reason="bereavement")
    enh = {d["row"].first_name: d for d in Y6.enhanced(YEAR, actor=ADMIN)}
    assert enh["Mia"]["key_adult"] == "Ms Khan" and enh["Sam"]["manual"]
    Y6.remove_from_enhanced(rows["Sam"].cohort_id, actor=ADMIN)
    assert "Sam" not in {d["row"].first_name for d in Y6.enhanced(YEAR, actor=ADMIN)}


def test_september_start_creates_pupil_with_identity_and_completes(env, cohort):
    rows, _ = cohort
    FG.create({"name": "7A", "year_group": 7}, actor=ADMIN)
    YA.move(rows["Mia"].cohort_id, "7A", actor=ADMIN)
    YA.publish(YEAR, actor=ADMIN)
    notes = Y6.start_pupil(rows["Mia"].cohort_id, actor=ADMIN, start_date="2026-09-03",
                           db_path=env)
    assert "platform transfer completed" in notes
    row = Y6.get(rows["Mia"].cohort_id, actor=ADMIN)
    p = P.get_pupil(row.pupil_id)
    assert (p.form_group, p.gender, p.town, p.postcode, p.sen_status, p.fsm_eligible) == \
        ("7A", "Female", "Leeds", "LS1 1AA", "K", True)
    assert [(c.full_name, c.relationship, c.email) for c in C.list_for_pupil(p.pupil_id)] == \
        [("Pat Patel", "Mother", "pat@example.com")]
    assert HM.get_ks2(p.pupil_id).reading_scaled == 108
    assert IP.get(row.transition_id, actor=ADMIN, db_path=env).status == "completed"
    with pytest.raises(Y6.ValidationError, match="accept"):     # offer not accepted yet
        Y6.start_pupil(rows["Sam"].cohort_id, actor=ADMIN, start_date="2026-09-03",
                       db_path=env)


def test_incoming_defaults_carry_the_new_identity_fields(env):
    tid = _transfer(env, "Ava", "Stone", "2015-01-01", "P9", gender="girl", sen="E", pp=True)
    d = IP.new_pupil_defaults(tid, actor=ADMIN, db_path=env)
    assert (d["gender"], d["town"], d["postcode"], d["sen_status"], d["fsm_eligible"]) == \
        ("Female", "Leeds", "LS1 1AA", "E", True)


def test_update_row_is_kept_on_sync_and_exports(env, cohort, tmp_path):
    rows, _ = cohort
    Y6.update_row(rows["Sam"].cohort_id, {"ks2_reading": "112", "ks2_maths": "110",
                                          "feeder_school": "Elm Primary"}, actor=ADMIN)
    with pytest.raises(Y6.ValidationError):
        Y6.update_row(rows["Sam"].cohort_id, {"ks2_reading": "200"}, actor=ADMIN)
    with pytest.raises(Y6.PermissionDenied):
        Y6.update_row(rows["Sam"].cohort_id, {"notes": "x"}, actor=TEACHER)
    Y6.sync(YEAR, actor=ADMIN, db_path=env)
    sam = Y6.get(rows["Sam"].cohort_id, actor=ADMIN)
    assert (sam.feeder_school, sam.ks2_band) == ("Elm Primary", "Higher")
    path = tmp_path / "cohort.csv"
    assert Y6.export_cohort_csv(YEAR, path, actor=TEACHER) == 4
    head = next(csv.reader(open(path, encoding="utf-8")))
    assert "sen" not in head
    Y6.export_cohort_csv(YEAR, path, actor=ADMIN)
    assert "sen" in next(csv.reader(open(path, encoding="utf-8")))
