"""Behavioural tests for equality_diversity.integrations."""

from __future__ import annotations

from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity import (
    integrations,
    schema,
)


def _student(student_id, **kw):
    base = dict(student_id=student_id, first_name="F", last_name="L",
                email_address=f"{student_id}@x.ac.uk", gender=None, dob=None,
                course=None, year_of_study=None, status="active")
    base.update(kw)
    return base


def _insert_person(raw, ref_code, **cols):
    conn = raw()
    keys = ["ref_code"] + list(cols)
    vals = [ref_code] + list(cols.values())
    placeholders = ", ".join("?" for _ in keys)
    conn.execute(
        f"INSERT INTO ed_people ({', '.join(keys)}) VALUES ({placeholders})",
        vals,
    )
    conn.commit()
    pid = conn.execute("SELECT id FROM ed_people WHERE ref_code=?",
                       (ref_code,)).fetchone()[0]
    conn.close()
    return pid


# --- audit (feature 31) ---------------------------------------------------- #

def test_audit_writes_ed_log_and_swallows_missing_main_log(raw):
    # audit_log table does not exist → inner insert raises, is swallowed.
    integrations.audit("alice", "create", "person", 7, {"ref": "R1"})
    integrations.audit("alice", "noop", "person", None, None)  # details None branch
    conn = raw()
    try:
        rows = conn.execute(
            "SELECT actor, action, entity, entity_id, details FROM ed_audit_log "
            "ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    assert rows[0] == ("alice", "create", "person", "7", '{"ref": "R1"}')
    assert rows[1] == ("alice", "noop", "person", None, None)


def test_audit_also_writes_main_audit_log_when_present(raw):
    conn = raw()
    conn.execute(
        "CREATE TABLE audit_log (user_id INTEGER, action TEXT, table_name TEXT, "
        "record_id INTEGER, new_values TEXT, timestamp TEXT, details TEXT)"
    )
    conn.commit()
    conn.close()
    integrations.audit("bob", "update", "incident", 3, {"x": 1})
    conn = raw()
    try:
        main = conn.execute(
            "SELECT action, table_name, record_id FROM audit_log"
        ).fetchall()
    finally:
        conn.close()
    assert main == [("update", "ed_incident", 3)]


# --- link_person_by_ref / sync_link (features 10/29) ----------------------- #

def test_link_person_by_ref_no_tables_returns_none():
    # students table absent → OperationalError caught → None
    assert integrations.link_person_by_ref("whoever") is None


def test_link_person_by_ref_student_and_staff(mk_students, mk_staff):
    mk_students([_student("S1", first_name="Ann", last_name="Lee")])
    mk_staff([{"id": 11, "username": "jdoe", "name": "J Doe",
               "email": "j@x.ac.uk", "role": "lecturer",
               "department": "Physics", "status": "active"}])
    hit = integrations.link_person_by_ref("S1")
    assert hit["kind"] == "student" and hit["name"] == "Ann Lee"
    staff_hit = integrations.link_person_by_ref("jdoe")
    assert staff_hit["kind"] == "staff" and staff_hit["staff_id"] == 11
    # neither
    assert integrations.link_person_by_ref("nobody") is None


def test_sync_link_updates_person(raw, mk_students, mk_staff):
    mk_students([_student("S1")])
    mk_staff([{"id": 22, "username": "u2", "name": "N", "email": "n@x",
               "role": "r", "department": "D", "status": "active"}])
    pid_stu = _insert_person(raw, "S1", person_type="Student")
    pid_staff = _insert_person(raw, "u2", person_type="Staff")
    assert integrations.sync_link(pid_stu, "S1")["kind"] == "student"
    assert integrations.sync_link(pid_staff, "u2")["kind"] == "staff"
    assert integrations.sync_link(pid_stu, "unmatched") is None
    conn = raw()
    try:
        assert conn.execute("SELECT student_id FROM ed_people WHERE id=?",
                            (pid_stu,)).fetchone()[0] == "S1"
        assert conn.execute("SELECT staff_id FROM ed_people WHERE id=?",
                            (pid_staff,)).fetchone()[0] == 22
    finally:
        conn.close()


# --- derivation helpers ---------------------------------------------------- #

def test_derive_age_group_bands():
    from datetime import datetime
    yr = datetime.now().year
    assert integrations._derive_age_group(None) is None
    assert integrations._derive_age_group("not-a-date") is None
    assert integrations._derive_age_group(f"{yr - 10}-01-01") == "Under 18"
    assert integrations._derive_age_group(f"{yr - 19}-01-01") == "18-20"
    assert integrations._derive_age_group(f"{yr - 22}-01-01") == "21-24"
    assert integrations._derive_age_group(f"{yr - 27}-01-01") == "25-29"
    assert integrations._derive_age_group(f"{yr - 35}-01-01") == "30-39"
    assert integrations._derive_age_group(f"{yr - 45}-01-01") == "40-49"
    assert integrations._derive_age_group(f"{yr - 55}-01-01") == "50-64"
    assert integrations._derive_age_group(f"{yr - 70}-01-01") == "65+"


def test_derive_programme_level():
    dp = integrations._derive_programme_level
    assert dp("PhD Physics", None) == "Postgraduate (Research)"
    assert dp("MSc Data Science", None) == "Postgraduate (Taught)"
    assert dp("BSc Biology", None) == "Undergraduate"
    assert dp("Unknown Course", 2) == "Undergraduate"
    assert dp("Unknown Course", 6) == "Postgraduate"
    assert dp(None, None) is None


# --- sync_from_students (feature) ------------------------------------------ #

def test_sync_from_students_create_update_skip_error(raw, mk_students):
    mk_students([
        _student("S1", gender="female", dob="2000-01-01",
                 course="BSc Biology", year_of_study=2),
        _student("S2", status="withdrawn"),          # filtered out by WHERE
        _student(None),                              # sid falsy → skipped
    ])
    # pre-existing analyst-entered row (gender already set → must not overwrite)
    _insert_person(raw, "S1", person_type="Student", gender="Male",
                   deleted_at=None)
    # a soft-deleted row that collides on ref_code to force an INSERT UNIQUE
    # error for a *different* student.
    mk_students([_student("S3")])
    _insert_person(raw, "S3", person_type="Student", deleted_at="2020-01-01")

    result = integrations.sync_from_students()
    assert result["updated"] >= 1        # S1 updated in place
    assert result["skipped"] >= 1        # None sid skipped
    assert result["errors"] >= 1         # S3 UNIQUE collision
    conn = raw()
    try:
        # analyst-entered Male preserved despite roster saying female
        assert conn.execute(
            "SELECT gender FROM ed_people WHERE ref_code='S1' "
            "AND deleted_at IS NULL"
        ).fetchone()[0] == "Male"
    finally:
        conn.close()


def test_sync_from_students_creates_new_row(raw, mk_students):
    mk_students([_student("NEW1", gender="m", dob="1999-05-05",
                          course="MSc AI", year_of_study=5)])
    result = integrations.sync_from_students()
    assert result["created"] == 1
    conn = raw()
    try:
        row = conn.execute(
            "SELECT gender, programme_level, person_type FROM ed_people "
            "WHERE ref_code='NEW1'"
        ).fetchone()
    finally:
        conn.close()
    assert row == ("Male", "Postgraduate (Taught)", "Student")


def test_sync_from_students_refresh_disabled_skips(raw, mk_students):
    mk_students([_student("S1")])
    _insert_person(raw, "S1", person_type="Student")
    result = integrations.sync_from_students(refresh_existing=False)
    assert result["skipped"] >= 1 and result["updated"] == 0


# --- sync_from_staff ------------------------------------------------------- #

def test_sync_from_staff_full_create_and_update(raw, mk_staff):
    mk_staff([
        {"id": 1, "username": "new.staff", "name": "N", "email": "n@x",
         "role": "r", "department": "Physics", "status": "active"},
        {"id": 2, "username": "old.staff", "name": "O", "email": "o@x",
         "role": "r", "department": "Maths", "status": "active"},
    ])
    _insert_person(raw, "old.staff", person_type="Staff")
    result = integrations.sync_from_staff()
    assert result["created"] == 1 and result["updated"] == 1
    conn = raw()
    try:
        assert conn.execute("SELECT staff_id FROM ed_people WHERE ref_code='new.staff'").fetchone()[0] == 1
    finally:
        conn.close()


def test_sync_from_staff_fallback_and_skip(raw, mk_staff):
    # bare staff table (no department/status) forces OperationalError fallback;
    # a row with no username/email is skipped.
    mk_staff([
        {"id": 1, "username": "u1", "name": "N", "email": "e1", "role": "r"},
        {"id": 2, "username": "", "name": "N", "email": "", "role": "r"},
    ], full=False)
    result = integrations.sync_from_staff()
    assert result["created"] == 1 and result["skipped"] == 1


def test_sync_from_staff_refresh_disabled_skips(raw, mk_staff):
    mk_staff([{"id": 3, "username": "s3", "name": "N", "email": "e",
               "role": "r", "department": "D", "status": "active"}])
    _insert_person(raw, "s3", person_type="Staff")
    result = integrations.sync_from_staff(refresh_existing=False)
    assert result["skipped"] >= 1 and result["updated"] == 0


def test_sync_all_rosters(mk_students, mk_staff):
    mk_students([_student("S1")])
    mk_staff([{"id": 9, "username": "s9", "name": "N", "email": "e",
               "role": "r", "department": "D", "status": "active"}])
    out = integrations.sync_all_rosters()
    assert out["total_created"] == 2
    assert "students" in out and "staff" in out


# --- monitoring_completeness (feature 30) ---------------------------------- #

def test_monitoring_completeness(raw, mk_students):
    mk_students([_student("S1"), _student("S2")])
    _insert_person(raw, "S1", person_type="Student", gender="Female",
                   ethnicity="Mixed")
    stats = integrations.monitoring_completeness()
    assert stats["student_roster"] == 2
    assert stats["students_monitored"] == 1
    assert stats["coverage_pct"] == 50.0
    assert stats["per_field"]["gender"][0] == 1


def test_monitoring_completeness_empty_roster(mk_students):
    mk_students([])  # creates empty students table
    stats = integrations.monitoring_completeness()
    assert stats["coverage_pct"] == 0.0


# --- sar_export (feature 32) ----------------------------------------------- #

def test_sar_export_not_found():
    assert integrations.sar_export("ghost") == {"ref_code": "ghost", "found": False}


def test_sar_export_full(raw):
    pid = _insert_person(raw, "P1", person_type="Student", gender="Female")
    conn = raw()
    conn.execute(
        "INSERT INTO ed_incidents (date_reported, category, reported_by) "
        "VALUES ('2024-01-01', 'Harassment', 'P1')")
    conn.execute(
        "INSERT INTO ed_view_log (entity, entity_id, viewer, viewed_at) "
        "VALUES ('person', ?, 'watcher', '2024-01-02')", (pid,))
    conn.execute(
        "INSERT INTO ed_consent (person_id, consent_flags, updated_at) "
        "VALUES (?, 'analytics=1', '2024-01-03')", (pid,))
    conn.commit()
    conn.close()
    out = integrations.sar_export("P1")
    assert out["found"] is True
    assert out["record"]["ref_code"] == "P1"
    assert out["incidents"][0]["category"] == "Harassment"
    assert out["view_log"] == [{"viewer": "watcher", "viewed_at": "2024-01-02"}]
    assert out["consent"] == {"flags": "analytics=1", "updated_at": "2024-01-03"}


# --- erase_person (feature 33) --------------------------------------------- #

def test_erase_person_not_found():
    assert integrations.erase_person("ghost", "admin") == 0


def test_erase_person_removes_everything(raw):
    pid = _insert_person(raw, "E1", person_type="Student")
    conn = raw()
    conn.execute("INSERT INTO ed_view_log (entity, entity_id, viewer, viewed_at) "
                 "VALUES ('person', ?, 'v', 't')", (pid,))
    conn.execute("INSERT INTO ed_consent (person_id, consent_flags, updated_at) "
                 "VALUES (?, 'x', 't')", (pid,))
    conn.execute("INSERT INTO ed_incidents (date_reported, category, reported_by, "
                 "respondent) VALUES ('t', 'c', 'E1', 'E1')")
    conn.commit()
    conn.close()
    total = integrations.erase_person("E1", "admin")
    assert total >= 4
    conn = raw()
    try:
        assert conn.execute("SELECT COUNT(*) FROM ed_people WHERE ref_code='E1'").fetchone()[0] == 0
        assert conn.execute("SELECT reported_by FROM ed_incidents").fetchone()[0] == "[erased]"
    finally:
        conn.close()


# --- refer_to_safeguarding (feature 34) ------------------------------------ #

def test_refer_to_safeguarding_success(raw):
    conn = raw()
    conn.execute("INSERT INTO ed_incidents (date_reported, category) "
                 "VALUES ('t', 'Serious')")
    iid = conn.execute("SELECT id FROM ed_incidents").fetchone()[0]
    conn.commit()
    conn.close()
    assert integrations.refer_to_safeguarding(iid, "admin", "escalation") is True
    conn = raw()
    try:
        assert conn.execute("SELECT COUNT(*) FROM safeguarding_referrals").fetchone()[0] == 1
        assert conn.execute("SELECT referred_to FROM ed_incidents WHERE id=?",
                            (iid,)).fetchone()[0] == "safeguarding"
    finally:
        conn.close()


def test_refer_to_safeguarding_failure(raw):
    # Remove ed_incidents so the UPDATE inside the try fails → ok=False.
    conn = raw()
    conn.execute("ALTER TABLE ed_incidents RENAME TO ed_incidents_gone")
    conn.commit()
    conn.close()
    assert integrations.refer_to_safeguarding(1, "admin", "reason") is False


# --- staff_roster_for_monitoring (feature 35) ------------------------------ #

def test_staff_roster_for_monitoring(mk_staff):
    mk_staff([{"id": 1, "username": "u", "name": "N", "email": "e",
               "role": "r", "department": "D", "status": "active"},
              {"id": 2, "username": "u2", "name": "N2", "email": "e2",
               "role": "r", "department": "D", "status": "inactive"}])
    roster = integrations.staff_roster_for_monitoring()
    assert [r[0] for r in roster] == [1]


# --- applicant_monitoring_seed (feature 36) -------------------------------- #

def test_applicant_seed_no_students_table_returns_zero():
    assert integrations.applicant_monitoring_seed() == 0


def test_applicant_seed_creates_and_skips_existing(raw, mk_students):
    mk_students([
        _student("A1", gender="Female", status="applicant"),
        _student("A2", gender=None, status="applied"),
        _student("A3", status="active"),   # not an applicant → ignored
    ])
    _insert_person(raw, "A1", person_type="Student")  # already tracked → skip
    created = integrations.applicant_monitoring_seed()
    assert created == 1
    conn = raw()
    try:
        assert conn.execute(
            "SELECT gender FROM ed_people WHERE ref_code='A2'"
        ).fetchone()[0] == "Prefer not to say"
    finally:
        conn.close()
