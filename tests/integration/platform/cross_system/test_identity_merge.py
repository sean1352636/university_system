"""Identity resolution, duplicate detection, merge, and the login link.

Every case runs against temp auth / audit / system databases; nothing
touches the running application's data.
"""

from __future__ import annotations

import json
import sqlite3
import uuid

import pytest

from education_system.platform.cross_system import (
    enrolment_schema,
    enrolments,
    identity_backfill,
    identity_service,
    person,
    qualifications,
    transitions,
)
from education_system.platform.identity.auth.db import connect
from education_system.platform.identity.auth.schema import initialise_auth_db

DOB = "2010-12-10"


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "auth.db")
    enrolment_schema.reset_schema_cache_for_test()
    qualifications.reset_schema_cache_for_test()
    identity_service._initialised.clear()
    enrolment_schema.ensure_enrolment_schema(path)
    yield path
    enrolment_schema.reset_schema_cache_for_test()
    qualifications.reset_schema_cache_for_test()
    identity_service._initialised.clear()


@pytest.fixture
def audit_db(tmp_path):
    return str(tmp_path / "audit.db")


def _journey(db, first, last, system, sid, dob=DOB, **kw):
    return identity_service.get_or_create_journey(
        first_name=first, last_name=last, date_of_birth=dob, system=system,
        student_id=sid, db_path=db, **kw)


def _insert_journey(db, first, last, dob=DOB, *, nhs=None, upn=None,
                    **slots) -> str:
    """A registry row exactly as given — for states resolution would not make."""
    jid = str(uuid.uuid4())
    cols = ["journey_id", "legal_first_name", "legal_last_name",
            "date_of_birth", "nhs_number", "upn", "current_system"]
    vals = [jid, first, last, dob, nhs, upn, next(iter(slots), "primary")]
    for system, sid in slots.items():
        cols.append(identity_service.SYSTEM_SLOTS[system][1])
        vals.append(sid)
    conn = connect(db)
    try:
        conn.execute(
            f"INSERT INTO student_journey ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(vals))})", vals)
        conn.commit()
    finally:
        conn.close()
    return jid


def _events(db, name=None):
    conn = connect(db)
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT event_name, journey_id, payload_json, idempotency_key "
            "FROM cross_system_event_outbox ORDER BY rowid").fetchall()]
    finally:
        conn.close()
    return [r for r in rows if name is None or r["event_name"] == name]


def _one(db, sql, args=()):
    conn = connect(db)
    try:
        return conn.execute(sql, args).fetchone()
    finally:
        conn.close()


# ── Schema migration ────────────────────────────────────────────────

def test_old_unique_name_dob_index_is_replaced(tmp_path):
    path = str(tmp_path / "old.db")
    initialise_auth_db(path)
    conn = sqlite3.connect(path)
    conn.execute("CREATE UNIQUE INDEX idx_journey_dob_name ON "
                 "student_journey(date_of_birth, legal_last_name, "
                 "legal_first_name)")
    conn.commit()
    conn.close()

    initialise_auth_db(path)          # the migration
    initialise_auth_db(path)          # ...and again: idempotent

    conn = sqlite3.connect(path)
    try:
        idx = {r[1]: r[2] for r in conn.execute(
            "PRAGMA index_list(student_journey)").fetchall()}
        users = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
        journey = {r[1] for r in conn.execute(
            "PRAGMA table_info(student_journey)")}
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert "idx_journey_dob_name" not in idx
    assert idx["idx_journey_identity"] == 0          # not unique
    assert "journey_id" in users
    assert {"merged_into", "merged_at"} <= journey
    assert {"student_journey_merges", "student_journey_distinct"} <= tables


def test_learner_enrolment_gains_its_new_columns_on_an_old_db(tmp_path):
    path = str(tmp_path / "old_enrol.db")
    initialise_auth_db(path)
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE learner_enrolment (
        enrolment_id TEXT PRIMARY KEY, journey_id TEXT NOT NULL,
        system TEXT NOT NULL, institution_id TEXT, local_student_id TEXT,
        start_date TEXT, end_date TEXT, status TEXT NOT NULL DEFAULT
        'applicant', year_group TEXT, exit_reason TEXT, notes TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')))""")
    conn.commit()
    conn.close()
    enrolment_schema.reset_schema_cache_for_test()
    enrolment_schema.ensure_enrolment_schema(path)
    conn = sqlite3.connect(path)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(learner_enrolment)")}
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    enrolment_schema.reset_schema_cache_for_test()
    assert {"programme", "outcome", "source_system"} <= cols
    assert "enrolment_year_history" in tables


# ── Resolution ──────────────────────────────────────────────────────

def test_same_person_in_another_system_still_links_despite_case(db):
    a = _journey(db, "Ada", "Lovelace", "nursery", "N1")
    b = _journey(db, "  ada ", "LOVELACE", "primary", "P1")
    assert a == b
    assert identity_service.get(a, db_path=db)["primary_student_id"] == "P1"


def test_same_name_and_dob_but_different_nhs_number_is_two_people(db):
    a = _journey(db, "Oliver", "Smith", "primary", "P1", nhs_number="111 222 3333")
    b = _journey(db, "Oliver", "Smith", "secondary", "S1", nhs_number="999 888 7777")
    assert a != b


def test_second_open_record_in_the_same_system_is_not_folded_in(db):
    a = _journey(db, "Oliver", "Smith", "secondary", "S1")
    b = _journey(db, "Oliver", "Smith", "secondary", "S2")
    # Two open secondary records with one name and birthday: two people,
    # until an administrator says otherwise.
    assert a != b
    assert identity_service.get(a, db_path=db)["school_student_id"] == "S1"


def test_returning_under_a_new_id_after_leaving_links_to_the_same_journey(db):
    a = _journey(db, "Ada", "Lovelace", "secondary", "S1")
    enrolments.end_local_enrolment("secondary", "S1", reason="moved away",
                                   status="withdrawn", db_path=db)
    b = _journey(db, "Ada", "Lovelace", "secondary", "S9")
    assert a == b
    spells = enrolments.list_enrolments(a, system="secondary", db_path=db)
    assert [s["local_student_id"] for s in spells] == ["S1", "S9"]


def test_nhs_number_beats_a_different_name(db):
    a = _journey(db, "Ada", "Lovelace", "nursery", "N1", nhs_number="943 476 5919")
    b = _journey(db, "Augusta", "King", "primary", "P1", dob="2010-12-11",
                 nhs_number="9434765919")
    assert a == b


def test_reregistering_a_linked_record_is_idempotent(db):
    a = _journey(db, "Ada", "Lovelace", "secondary", "S1")
    b = _journey(db, "Ada", "Lovelace", "secondary", "S1")
    assert a == b
    assert len(enrolments.list_enrolments(a, db_path=db)) == 1


def test_find_by_student_reaches_an_earlier_spell_through_enrolments(db):
    a = _journey(db, "Ada", "Lovelace", "primary", "P1")
    enrolments.end_local_enrolment("primary", "P1", reason="moved",
                                   status="transferred", db_path=db)
    _journey(db, "Ada", "Lovelace", "primary", "P2")   # slot now holds P2
    assert identity_service.find_by_student("primary", "P1",
                                            db_path=db)["journey_id"] == a


def test_minting_publishes_journey_registered_exactly_once(db):
    jid = _journey(db, "Ada", "Lovelace", "secondary", "S1")
    assert len(_events(db, "journey.registered")) == 1
    # The system's own create path announces with the same key: no second.
    identity_service.publish_registered(jid, "secondary", "S1", db_path=db)
    assert len(_events(db, "journey.registered")) == 1
    _journey(db, "Grace", "Hopper", "primary", "P7", announce=False)
    assert len(_events(db, "journey.registered")) == 1


# ── Duplicate candidates ────────────────────────────────────────────

def test_split_same_name_records_are_offered_as_a_duplicate(db):
    a = _journey(db, "Oliver", "Smith", "secondary", "S1")
    b = _journey(db, "  oliver", "SMITH ", "secondary", "S2")
    [cand] = identity_service.find_duplicate_candidates(db_path=db)
    assert {cand.journey_id, cand.duplicate_id} == {a, b}
    assert cand.score >= 90
    assert any("normalised" in r for r in cand.reasons)


@pytest.mark.parametrize("left, right, expected_reason", [
    (dict(first="Ada", last="Lovelace", nhs="9434765919"),
     dict(first="Augusta", last="King", nhs="943 476 5919"), "same NHS number"),
    (dict(first="Ada", last="Lovelace", upn="A123"),
     dict(first="Ann", last="Byron", upn="a123"), "same UPN"),
    (dict(first="Jon", last="Smith"),
     dict(first="John", last="Smith"), "similar first name"),
    (dict(first="Smith", last="John"),
     dict(first="John", last="Smith"), "swapped"),
    (dict(first="Alex", last="Brown"),
     dict(first="Alexander", last="Brown"), "similar first name"),
])
def test_duplicate_signals(db, left, right, expected_reason):
    _insert_journey(db, left["first"], left["last"], nhs=left.get("nhs"),
                    upn=left.get("upn"), primary="P1")
    _insert_journey(db, right["first"], right["last"], nhs=right.get("nhs"),
                    upn=right.get("upn"), secondary="S1")
    [cand] = identity_service.find_duplicate_candidates(db_path=db)
    assert any(expected_reason in r for r in cand.reasons), cand.reasons


def test_transposed_day_and_month_is_a_candidate(db):
    _insert_journey(db, "Ada", "Lovelace", "2010-03-04", primary="P1")
    _insert_journey(db, "Ada", "Lovelace", "2010-04-03", secondary="S1")
    [cand] = identity_service.find_duplicate_candidates(db_path=db)
    assert cand.score == 65
    assert "transposed" in cand.reasons[0]


def test_conflicting_nhs_numbers_pull_the_score_down(db):
    _insert_journey(db, "Oliver", "Smith", nhs="1112223333", primary="P1")
    _insert_journey(db, "Oliver", "Smith", nhs="9998887777", secondary="S1")
    # 90 for the name+DOB match, less 40: below any threshold above 50.
    assert identity_service.find_duplicate_candidates(min_score=60,
                                                      db_path=db) == []
    [cand] = identity_service.find_duplicate_candidates(min_score=0,
                                                        db_path=db)
    assert cand.score == 50
    assert "NHS numbers differ" in cand.reasons


def test_marked_distinct_pairs_are_not_proposed_again(db):
    a = _insert_journey(db, "Oliver", "Smith", primary="P1")
    b = _insert_journey(db, "Oliver", "Smith", secondary="S1")
    identity_service.mark_not_duplicate(a, b, actor="admin", reason="twins",
                                        db_path=db)
    assert identity_service.find_duplicate_candidates(db_path=db) == []


def test_candidates_suggest_the_better_linked_journey_as_survivor(db):
    rich = _insert_journey(db, "Ada", "Lovelace", nursery="N1", primary="P1")
    thin = _insert_journey(db, "Ada", "Lovelace", secondary="S1")
    [cand] = identity_service.find_duplicate_candidates(db_path=db)
    assert (cand.journey_id, cand.duplicate_id) == (rich, thin)
    assert cand.as_dict()["journey"]["systems"] == ["nursery", "primary"]


def test_candidate_summaries_mask_identifiers(db):
    _insert_journey(db, "Ada", "Lovelace", nhs="9434765919", primary="P1")
    _insert_journey(db, "Ada", "Lovelace", nhs="9434765919", secondary="S1")
    [cand] = identity_service.find_duplicate_candidates(db_path=db)
    assert cand.journey["nhs_number"] == "…5919"


def test_limit_is_respected(db):
    for i in range(4):
        _insert_journey(db, "Oliver", f"Smith{i}", primary=f"P{i}a")
        _insert_journey(db, "Oliver", f"Smith{i}", secondary=f"S{i}b")
    assert len(identity_service.find_duplicate_candidates(limit=2,
                                                          db_path=db)) == 2


# ── Merge ───────────────────────────────────────────────────────────

@pytest.fixture
def pair(db, tmp_path):
    """A survivor (secondary) and a duplicate (nursery) with history."""
    survivor = _journey(db, "Ada", "Lovelace", "secondary", "S1")
    duplicate = _insert_journey(db, "ada", "lovelace", nursery="N1")
    enrolments.create_enrolment(journey_id=duplicate, system="nursery",
                                local_student_id="N1", status="completed",
                                db_path=db)
    identity_service.record_transition(duplicate, to_system="nursery",
                                       db_path=db)
    transitions.start_transition(journey_id=duplicate,
                                 destination_system="primary", db_path=db)
    conn = connect(db)
    try:
        conn.execute(
            "INSERT INTO safeguarding_alerts (alert_id, journey_id, "
            "source_system, summary) VALUES ('A1', ?, 'nursery', 'x')",
            (duplicate,))
        conn.commit()
    finally:
        conn.close()
    qualifications.record_qualification(
        duplicate, source_system="nursery", title="Swimming badge",
        source_ref="nursery:test:1", publish=False, db_path=db)

    nursery_db = tmp_path / "nursery.db"
    sconn = sqlite3.connect(str(nursery_db))
    sconn.execute("CREATE TABLE pupils (pupil_id TEXT PRIMARY KEY, "
                  "journey_id TEXT)")
    sconn.execute("INSERT INTO pupils VALUES ('N1', ?)", (duplicate,))
    sconn.commit()
    sconn.close()
    return survivor, duplicate, {"nursery": str(nursery_db)}


def test_merge_repoints_history_and_tombstones_the_duplicate(db, audit_db, pair):
    survivor, duplicate, system_dbs = pair
    result = identity_service.merge_journeys(
        survivor, duplicate, actor="admin", reason="same child",
        db_path=db, audit_db_path=audit_db, system_db_paths=system_dbs)

    assert result["slots_moved"] == ["nursery"]
    for table in ("learner_enrolment", "learner_transition",
                  "student_journey_transitions", "safeguarding_alerts",
                  "learner_qualification"):
        assert result["moved"][table] >= 1, table
        assert _one(db, f"SELECT COUNT(*) FROM {table} WHERE journey_id = ?",
                    (duplicate,))[0] == 0

    live = identity_service.get(survivor, db_path=db)
    assert live["nursery_student_id"] == "N1"
    tomb = identity_service.get(duplicate, db_path=db)
    assert tomb["status"] == "merged"
    assert tomb["merged_into"] == survivor
    assert tomb["nursery_student_id"] is None

    log = identity_service.list_merges(survivor, db_path=db)
    assert [m["duplicate_id"] for m in log] == [duplicate]
    assert log[0]["actor"] == "admin"

    # The local nursery row now carries the survivor's id.
    conn = sqlite3.connect(system_dbs["nursery"])
    assert conn.execute("SELECT journey_id FROM pupils").fetchone()[0] == survivor
    conn.close()
    assert result["restamped"] == 1

    # Audited, and announced.
    aconn = sqlite3.connect(audit_db)
    try:
        rows = aconn.execute(
            "SELECT action, resource_id FROM audit_log").fetchall()
    finally:
        aconn.close()
    assert ("cross_system.identity_merge", survivor) in rows
    [merged] = _events(db, "journey.merged")
    assert merged["journey_id"] == survivor
    assert json.loads(merged["payload_json"])["duplicate_journey_id"] == duplicate


def test_a_merged_id_keeps_resolving_to_the_survivor(db, audit_db, pair):
    survivor, duplicate, system_dbs = pair
    identity_service.merge_journeys(survivor, duplicate, actor="admin",
                                    db_path=db, audit_db_path=audit_db,
                                    system_db_paths=system_dbs)
    assert identity_service.resolve_journey_id(duplicate, db_path=db) == survivor
    assert person.get(duplicate, db_path=db).journey_id == survivor
    assert identity_service.find_by_student(
        "nursery", "N1", db_path=db)["journey_id"] == survivor
    assert identity_service.find_duplicate_candidates(db_path=db) == []


def test_merge_refusals(db, audit_db, pair):
    survivor, duplicate, _dbs = pair
    with pytest.raises(identity_service.MergeError):
        identity_service.merge_journeys(survivor, survivor, actor="admin",
                                        db_path=db, audit_db_path=audit_db)
    with pytest.raises(identity_service.MergeError):
        identity_service.merge_journeys(survivor, "nope", actor="admin",
                                        db_path=db, audit_db_path=audit_db)
    with pytest.raises(identity_service.MergeError):
        identity_service.merge_journeys(survivor, duplicate, actor=" ",
                                        db_path=db, audit_db_path=audit_db)
    identity_service.merge_journeys(survivor, duplicate, actor="admin",
                                    db_path=db, audit_db_path=audit_db)
    with pytest.raises(identity_service.MergeError):
        identity_service.merge_journeys(survivor, duplicate, actor="admin",
                                        db_path=db, audit_db_path=audit_db)


def test_conflicting_nhs_numbers_need_force(db, audit_db):
    a = _insert_journey(db, "Oliver", "Smith", nhs="1112223333", primary="P1")
    b = _insert_journey(db, "Oliver", "Smith", nhs="9998887777", secondary="S1")
    with pytest.raises(identity_service.MergeError, match="NHS"):
        identity_service.merge_journeys(a, b, actor="admin", db_path=db,
                                        audit_db_path=audit_db)
    identity_service.merge_journeys(a, b, actor="admin", force=True,
                                    db_path=db, audit_db_path=audit_db)
    assert identity_service.get(b, db_path=db)["status"] == "merged"


def test_merge_that_cannot_be_audited_is_rolled_back(db, audit_db, pair,
                                                     monkeypatch):
    survivor, duplicate, _dbs = pair

    def boom(**_kw):
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(identity_service, "_audit_merge", boom)
    with pytest.raises(RuntimeError):
        identity_service.merge_journeys(survivor, duplicate, actor="admin",
                                        db_path=db, audit_db_path=audit_db)
    assert identity_service.get(duplicate, db_path=db)["status"] == "active"
    assert _one(db, "SELECT COUNT(*) FROM learner_enrolment WHERE "
                "journey_id = ?", (duplicate,))[0] == 1
    assert _events(db, "journey.merged") == []


# ── Login link ──────────────────────────────────────────────────────

def _user(db, username="ada"):
    conn = connect(db)
    try:
        cur = conn.execute("INSERT INTO users (username, password_hash) "
                           "VALUES (?, 'x')", (username,))
        uid = cur.lastrowid
        conn.execute("INSERT INTO user_systems (user_id, system_key, role) "
                     "VALUES (?, 'secondary', 'student')", (uid,))
        conn.commit()
    finally:
        conn.close()
    return uid


def test_link_user_account(db):
    jid = _journey(db, "Ada", "Lovelace", "secondary", "S1")
    uid = _user(db)
    identity_service.link_user_account(uid, jid, actor="admin", db_path=db)
    assert identity_service.journey_for_user(uid, db_path=db) == jid
    [linked] = identity_service.users_for_journey(jid, db_path=db)
    assert linked["username"] == "ada"
    assert linked["systems"] == [{"system_key": "secondary", "role": "student"}]
    audit = _one(db, "SELECT event_type, username, user_id FROM "
                 "security_audit_log WHERE event_type = 'identity.user_linked'")
    assert tuple(audit) == ("identity.user_linked", "admin", uid)

    identity_service.unlink_user_account(uid, actor="admin", db_path=db)
    assert identity_service.journey_for_user(uid, db_path=db) is None


def test_link_user_account_rejects_unknowns_and_follows_merges(db, audit_db):
    uid = _user(db)
    with pytest.raises(ValueError):
        identity_service.link_user_account(uid, "no-such-journey",
                                           actor="admin", db_path=db)
    jid = _journey(db, "Ada", "Lovelace", "secondary", "S1")
    with pytest.raises(ValueError):
        identity_service.link_user_account(999, jid, actor="admin", db_path=db)
    dup = _insert_journey(db, "Ada", "Lovelace", nursery="N1")
    identity_service.merge_journeys(jid, dup, actor="admin", db_path=db,
                                    audit_db_path=audit_db)
    identity_service.link_user_account(uid, dup, actor="admin", db_path=db)
    assert identity_service.journey_for_user(uid, db_path=db) == jid


def test_a_login_linked_to_a_duplicate_moves_with_the_merge(db, audit_db):
    keep = _journey(db, "Ada", "Lovelace", "secondary", "S1")
    dup = _insert_journey(db, "Ada", "Lovelace", nursery="N1")
    uid = _user(db)
    identity_service.link_user_account(uid, dup, actor="admin", db_path=db)
    identity_service.merge_journeys(keep, dup, actor="admin", db_path=db,
                                    audit_db_path=audit_db)
    assert _one(db, "SELECT journey_id FROM users WHERE id = ?",
                (uid,))[0] == keep


# ── Local stamping and the backfill entry point ─────────────────────

def test_link_local_record_never_creates_a_missing_database(tmp_path):
    missing = tmp_path / "absent.db"
    assert person.link_local_record("primary", "P1", "J",
                                    db_path=str(missing)) is False
    assert not missing.exists()


def _pupils_db(path, rows):
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE pupils (pupil_id TEXT PRIMARY KEY, "
                 "first_name TEXT, last_name TEXT, date_of_birth TEXT)")
    conn.executemany("INSERT INTO pupils VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()
    return str(path)


def test_run_all_is_idempotent_and_silent(db, tmp_path):
    db_paths = {
        "nursery": _pupils_db(tmp_path / "n.db", [
            ("N1", "Noah", "Campbell", "2019-06-21")]),
        "primary": _pupils_db(tmp_path / "p.db", [
            ("P1", "Noah", "Campbell", "2019-06-21"),
            ("P2", "Mia", "Jones", "2018-02-02")]),
    }
    first = identity_backfill.run_all(db_paths=db_paths, auth_db=db)
    assert first["identity_linked"] == 3
    # Systems missing from db_paths are skipped, never read from live paths.
    assert first["identity_db_missing"] == 5
    journeys = _one(db, "SELECT COUNT(*) FROM student_journey")[0]
    assert journeys == 2

    second = identity_backfill.run_all(db_paths=db_paths, auth_db=db)
    assert second["enrolments_created"] == 0
    assert second["qualifications_created"] == 0
    assert _one(db, "SELECT COUNT(*) FROM student_journey")[0] == journeys
    # Backfilling history is not news.
    assert _events(db, "journey.registered") == []


def test_run_all_dry_run_writes_nothing(db, tmp_path):
    db_paths = {"primary": _pupils_db(tmp_path / "p.db", [
        ("P1", "Noah", "Campbell", "2019-06-21")])}
    out = identity_backfill.run_all(db_paths=db_paths, auth_db=db,
                                    dry_run=True)
    assert out["identity_linked"] == 1
    assert "enrolments_created" not in out
    assert _one(db, "SELECT COUNT(*) FROM student_journey")[0] == 0
