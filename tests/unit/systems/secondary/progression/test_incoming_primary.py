"""Year 6 -> Year 7 arrivals (modules.progression.domain.incoming_primary).

Runs the real platform transfer queue against a temporary auth.db (passed
as ``db_path`` and patched as the platform default), playing the primary
school's part with the platform's own calls, so neither the live platform
DB nor the primary system is touched.
"""

from __future__ import annotations

import csv

import pytest

from education_system.platform.cross_system import identity_service as IDS
from education_system.platform.cross_system import transitions as T
from education_system.systems.secondary.modules.assessment.domain import headline_measures as HM
from education_system.systems.secondary.modules.progression.domain import incoming_primary as IP
from education_system.systems.secondary.modules.admissions.domain import admissions as AD
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="ann", role="teacher")
PARENT = Principal(username="mum", role="parent")

PAYLOAD = {
    "child_identity": {"first_name": "Mia", "last_name": "Patel", "date_of_birth": "2015-02-10",
                       "primary_pupil_id": "P0001", "year_group": "6"},
    "guardians": [{"name": "Asha Patel", "phone": "07700 900123", "email": "asha@example.com",
                   "relationship": "Mother"}],
    "ks2_results": {"reading_scaled": 108, "maths_scaled": 104},
    "attendance_summary": {"pct": 96.1},
    "send_provision": {"send_status": "yes"},
    "medical_requirements": "Asthma - inhaler",
    "safeguarding_reference": "DSL-2026-17",
}


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


def _transfer(db, payload=PAYLOAD, *, approve=True, first="Mia", last="Patel",
              dob="2015-02-10", student="P0001"):
    """Primary's side: a journey, a transfer to secondary, an approved handover."""
    jid = IDS.get_or_create_journey(first_name=first, last_name=last, date_of_birth=dob,
                                    system="primary", student_id=student, db_path=db)
    t = T.start_transition(journey_id=jid, source_system="primary",
                           destination_system="secondary", effective_date="2026-09-03",
                           db_path=db)
    if approve:
        T.approve_handover(t["transition_id"], dict(payload), db_path=db)
    return t["transition_id"]


def test_queue_lists_primary_transfers_only(env):
    tid = _transfer(env)
    _transfer(env, approve=False, first="Leo", last="Hart", student="P0002")
    jid = IDS.get_or_create_journey(first_name="Zed", last_name="Ox", date_of_birth="2010-01-01",
                                    system="sixth_form", student_id="C1", db_path=env)
    T.start_transition(journey_id=jid, source_system="sixth_form",
                       destination_system="secondary", db_path=env)
    rows = IP.queue(actor=TEACHER, db_path=env)
    assert [r.name for r in rows] == ["Patel, Mia", "Hart, Leo"]
    mia = rows[0]
    assert mia.transition_id == tid and mia.handover_ready and mia.status_label == "Handover ready"
    assert not rows[1].handover_ready
    assert IP.counts(actor=ADMIN, db_path=env)["Not acknowledged"] == 1
    with pytest.raises(IP.PermissionDenied):
        IP.queue(actor=PARENT, db_path=env)


def test_handover_is_tiered_and_safeguarding_only_for_leads(env):
    tid = _transfer(env)
    admin = IP.handover(tid, actor=ADMIN, db_path=env)
    assert admin["payload"]["ks2_results"]["reading_scaled"] == 108
    assert "send_provision" in admin["payload"]
    assert "safeguarding_reference" not in admin["payload"]
    assert admin["safeguarding"] == {"exists": True, "reference": None}   # DSL to DSL
    teacher = IP.handover(tid, actor=TEACHER, db_path=env)
    assert "ks2_results" in teacher["payload"]
    assert "send_provision" not in teacher["payload"]
    assert "send_provision" in teacher["withheld"]
    assert teacher["safeguarding"] is None
    assert "safeguarding_reference" not in teacher["withheld"]
    assert "Safeguarding" not in IP.handover_text(teacher)
    assert "safeguarding file exists" in IP.handover_text(admin)
    assert IP.handover(_transfer(env, approve=False, first="Leo", student="P9"),
                       actor=ADMIN, db_path=env) is None


def test_acknowledge_and_reject(env):
    tid = _transfer(env)
    with pytest.raises(IP.PermissionDenied):
        IP.acknowledge(tid, actor=TEACHER, db_path=env)
    item = IP.acknowledge(tid, actor=ADMIN, db_path=env)
    assert item.acknowledged_at
    done = {i["key"]: i["done"] for i in IP.checklist(tid, actor=ADMIN, db_path=env)}
    assert done["documents_received"] and done["handover_received"]
    other = _transfer(env, first="Leo", last="Hart", student="P0002")
    with pytest.raises(IP.ValidationError):
        IP.reject(other, actor=ADMIN, reason="  ", db_path=env)
    r = IP.reject(other, actor=ADMIN, reason="Place declined by parent", db_path=env)
    assert r.status_label == "Rejected" and r.reason == "Place declined by parent"
    assert [i.name for i in IP.queue(actor=ADMIN, db_path=env)] == ["Patel, Mia"]
    assert IP.queue(actor=ADMIN, status="Rejected", db_path=env)[0].name == "Hart, Leo"
    steps = [s["step"] for s in IP.step_log(other, actor=ADMIN, db_path=env)]
    assert "rejected" in steps and "reject" in steps


def test_create_pupil_from_handover_admits_and_links(env):
    tid = _transfer(env)
    with pytest.raises(IP.ValidationError) as e:          # primary sends no gender
        IP.create_pupil(tid, actor=ADMIN, db_path=env)
    assert "Gender" in " ".join(e.value.problems)
    d = IP.new_pupil_defaults(tid, actor=ADMIN, db_path=env)
    assert (d["legal_first_name"], d["year_group"], d["sen_status"]) == ("Mia", 7, "K")
    out = IP.create_pupil(tid, {"gender": "Female", "admission_date": "2026-09-03"},
                          actor=ADMIN, db_path=env)
    p = out.pupil
    assert (p.legal_last_name, p.year_group, p.sen_status) == ("Patel", 7, "K")
    assert [c.full_name for c in C.list_for_pupil(p.pupil_id)] == ["Asha Patel"]
    assert out.item.pupil_id == p.pupil_id and out.item.status == "admitted"
    assert IDS.find_by_student("secondary", str(p.pupil_id), db_path=env)["journey_id"] \
        == out.item.journey_id
    with pytest.raises(IP.ValidationError):
        IP.create_pupil(tid, {"gender": "Female"}, actor=ADMIN, db_path=env)


def test_match_existing_pupil_and_application(env):
    tid = _transfer(env)
    p = P.create_pupil({"legal_first_name": "Mia", "legal_last_name": "Patel",
                        "date_of_birth": "2015-02-10", "gender": "Female", "year_group": 7,
                        "admission_date": "2026-09-01"}, actor=ADMIN)
    cands = IP.match_candidates(tid, actor=ADMIN, db_path=env)
    assert cands[0]["kind"] == "pupil" and cands[0]["id"] == p.pupil_id
    other = P.create_pupil({"legal_first_name": "Ann", "legal_last_name": "Patel",
                            "date_of_birth": "2014-02-10", "gender": "Female", "year_group": 7,
                            "admission_date": "2026-09-01"}, actor=ADMIN)
    with pytest.raises(IP.ValidationError, match="date of birth"):
        IP.match_pupil(tid, other.pupil_id, actor=ADMIN, db_path=env)
    with pytest.raises(IP.PermissionDenied):
        IP.match_pupil(tid, p.pupil_id, actor=TEACHER, db_path=env)
    out = IP.match_pupil(tid, p.pupil_id, actor=ADMIN, db_path=env)
    assert out.item.pupil_id == p.pupil_id and out.item.admitted
    item = IP.unmatch(tid, actor=ADMIN, reason="wrong child", db_path=env)
    assert item.pupil_id is None
    # an application: linked now, matched once admitted
    tid2 = _transfer(env, first="Leo", last="Hart", dob="2015-05-05", student="P0002")
    app = AD.create_application({
        "route": "normal_round", "academic_year": AD.next_academic_year(), "year_group": 7,
        "legal_first_name": "Leo", "legal_last_name": "Hart", "date_of_birth": "2015-05-05",
        "gender": "Male", "parent_name": "Sam Hart", "parent_relationship": "Father",
        "parent_email": "sam@example.com"}, actor=ADMIN)
    app = getattr(app, "application", app)
    c = IP.match_candidates(tid2, actor=ADMIN, db_path=env)
    assert any(x["kind"] == "application" and x["id"] == app.application_id for x in c)
    out = IP.match_application(tid2, app.application_id, actor=ADMIN, db_path=env)
    assert out.pupil is None and out.item.application_id == app.application_id


def test_checklist_ks2_sen_and_safeguarding(env):
    tid = _transfer(env)
    keys = [i["key"] for i in IP.checklist(tid, actor=ADMIN, db_path=env)]
    assert keys[:4] == ["transition_report_sent", "visit_held", "support_meeting_held",
                        "documents_received"]
    assert "safeguarding_file" in keys
    assert "safeguarding_file" not in [i["key"] for i in IP.checklist(
        tid, actor=TEACHER, db_path=env)]
    IP.tick(tid, "visit_held", actor=ADMIN, db_path=env)
    with pytest.raises(IP.ValidationError):
        IP.tick(tid, "ks2_imported", actor=ADMIN, db_path=env)
    with pytest.raises(IP.ValidationError, match="Match the pupil"):
        IP.import_ks2(tid, actor=ADMIN, db_path=env)
    out = IP.create_pupil(tid, {"gender": "Female"}, actor=ADMIN, db_path=env)
    ks2 = IP.import_ks2(tid, actor=ADMIN, db_path=env)
    assert (ks2.reading_scaled, ks2.maths_scaled, ks2.source) == (108, 104, "Primary school")
    assert HM.get_ks2(out.pupil.pupil_id).prior == 106.0
    with pytest.raises(IP.ValidationError):
        IP.pass_sen_to_senco(tid, to="", actor=ADMIN, db_path=env)
    IP.pass_sen_to_senco(tid, to="Mrs Senco", actor=ADMIN, db_path=env)
    with pytest.raises(IP.PermissionDenied):
        IP.record_safeguarding_file(tid, actor=TEACHER, db_path=env)
    items = {i["key"]: i for i in IP.tick(tid, "safeguarding_file", actor=ADMIN, db_path=env)}
    for key in ("visit_held", "matched", "ks2_imported", "sen_to_senco", "safeguarding_file"):
        assert items[key]["done"], key
    assert "Mrs Senco" in items["sen_to_senco"]["label"]
    log = IP.step_log(tid, actor=ADMIN, db_path=env)
    assert {s["source"] for s in log} == {"platform", "school"}


def test_complete_and_export(env, tmp_path):
    tid = _transfer(env)
    with pytest.raises(IP.ValidationError, match="Match the pupil"):
        IP.complete(tid, actor=ADMIN, db_path=env)
    IP.create_pupil(tid, {"gender": "Female"}, actor=ADMIN, db_path=env)
    item = IP.complete(tid, actor=ADMIN, db_path=env)
    assert item.status == "completed" and not item.is_open
    path = tmp_path / "incoming.csv"
    assert IP.export_csv(path, actor=ADMIN, db_path=env) == 1
    rows = list(csv.reader(path.open()))
    assert rows[1][1] == "Patel" and rows[1][5] == "Completed"
