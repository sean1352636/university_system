"""Advanced student search: permission scoping, the data model (course code
or name, legacy statuses, erased records, marks and attendance), safe
queries, paging and sorting, exports and the audit, saved searches,
scheduled reports and bulk actions. Temporary databases only."""

import csv
import sqlite3
from datetime import datetime, timedelta

import pytest

from education_system.systems.university.application.students import bulk_actions as bulk
from education_system.systems.university.application.students import search as ss
from education_system.systems.university.application.students import search_saved as sv
from education_system.systems.university.application.students.search import Viewer

SCHEMA = [
    """CREATE TABLE students (student_id TEXT PRIMARY KEY, email_address TEXT, first_name TEXT,
        last_name TEXT, gender TEXT, dob TEXT, course TEXT, status TEXT, year_of_study INTEGER,
        mode_of_study TEXT, fee_status TEXT, entry_route TEXT, registration_datetime TEXT,
        phone TEXT, personal_email TEXT, address TEXT, nationality TEXT)""",
    "CREATE TABLE courses (course_code TEXT, code TEXT, course_name TEXT, name TEXT)",
    "INSERT INTO courses VALUES ('CS', 'CS', 'Computer Science', 'Computer Science')",
    "INSERT INTO courses VALUES ('DS', 'DS', 'Data Science', 'Data Science')",
    "CREATE TABLE module_grades (student_id TEXT, module_code TEXT, final_score REAL)",
    "CREATE TABLE attendance_records (student_id TEXT, status TEXT)",
    "CREATE TABLE student_modules (student_id TEXT, module_code TEXT, status TEXT)",
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT)",
    "INSERT INTO users (username, role) VALUES ('lead', 'staff'), ('boss', 'admin')",
]
STUDENTS = [
    ("S1", "s1@uni.uk", "Ana", "López", "female", "2003-01-01", "CS", "Active", 1, "full-time",
     "home", "a_levels", "2025-09-20 10:00:00", "0770", "ana@x.uk", "1 Rd", "Spanish"),
    ("S2", "s2@uni.uk", "John", "Smith", "male", "2002-02-02", "Computer Science", "Active", 2,
     "part-time", "international", "ib", "2024-09-20 10:00:00", None, None, None, "British"),
    ("S3", "s3@uni.uk", "Zoe", "Quinn_%", "female", "2001-03-03", "DS", "Graduated", 3,
     "full-time", "home", "access", "2023-09-20 10:00:00", None, None, None, None),
    ("ERASED-AB12", "erased@erased.invalid", "Erased", "record", None, None, "CS", "Closed",
     None, None, None, None, None, None, None, None, None),
]
ADMIN = Viewer("boss", "admin", True, True, True, True, True)
STAFF = Viewer("lead", "staff", True, False, True, True, False)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    for ddl in SCHEMA:
        c.execute(ddl)
    c.executemany(f"INSERT INTO students VALUES ({', '.join('?' * 17)})", STUDENTS)
    c.executemany("INSERT INTO module_grades VALUES (?, 'M1', ?)", [("S1", 72), ("S1", 58),
                                                                    ("S2", 35)])
    c.executemany("INSERT INTO attendance_records VALUES (?, ?)",
                  [("S2", "present"), ("S2", "absent"), ("S2", "absent"), ("S1", "late")])
    c.execute("INSERT INTO student_modules VALUES ('S2', 'CS101', 'Enrolled')")
    yield c
    c.close()


def _ids(result):
    return sorted(r["student_id"] for r in result["rows"])


def _find(conn, viewer=ADMIN, **criteria):
    return ss.search(conn, criteria, viewer, page_size=50)


def test_staff_do_not_see_personal_fields_students_only_see_themselves(conn):
    assert "phone" in _find(conn)["columns"]
    assert "phone" not in _find(conn, STAFF)["columns"]
    with pytest.raises(ValueError, match="cannot search on 'nationality'"):
        _find(conn, STAFF, conditions=[{"field": "nationality", "op": "contains", "value": "S"}])
    assert _ids(_find(conn, Viewer("S1", "student", student_id="S1"))) == ["S1"]


def test_course_by_code_or_name_legacy_status_and_erased_records(conn):
    assert _ids(_find(conn)) == ["S1", "S2", "S3"]
    cs = _find(conn, conditions=[{"field": "course", "op": "is", "value": "CS"}])
    assert _ids(cs) == ["S1", "S2"] and {r["course"] for r in cs["rows"]} == {"CS"}
    done = _find(conn, conditions=[{"field": "status", "op": "is", "value": "Completed"}])
    assert _ids(done) == ["S3"]


def test_marks_and_attendance_come_from_their_tables(conn):
    rows = {r["student_id"]: r for r in _find(conn)["rows"]}
    assert rows["S1"]["average_mark"] == 65.0 and rows["S2"]["average_mark"] == 35.0
    assert rows["S1"]["attendance"] == 100.0 and rows["S2"]["attendance"] == 33.3
    at_risk = _find(conn, **sv.PRESETS["At risk: average mark under 40"])
    assert _ids(at_risk) == ["S2"]
    assert _ids(_find(conn, conditions=[{"field": "module", "op": "has", "value": "cs101"}])) \
        == ["S2"]


def test_values_are_parameters_and_like_wildcards_are_literal(conn):
    hostile = "x' OR '1'='1"
    assert _find(conn, conditions=[{"field": "last_name", "op": "equals",
                                    "value": hostile}])["total"] == 0
    assert _ids(_find(conn, text="_%")) == ["S3"]
    assert conn.execute("SELECT COUNT(*) FROM students").fetchone() == (4,)


def test_bad_fields_operators_and_values_are_refused(conn):
    for cond, msg in (({"field": "password", "op": "is", "value": "x"}, "cannot search"),
                      ({"field": "average_mark", "op": "contains", "value": "1"}, "does not apply"),
                      ({"field": "average_mark", "op": "<", "value": "lots"}, "not a number"),
                      ({"field": "registration", "op": "before", "value": "soon"}, "not a date"),
                      ({"field": "average_mark", "op": "between", "value": "40"}, "two values")):
        with pytest.raises(ValueError, match=msg):
            _find(conn, conditions=[cond])


def test_sounds_like_paging_and_sorting_with_empties_last(conn):
    assert _ids(_find(conn, conditions=[{"field": "name", "op": "sounds like",
                                         "value": "jon smyth"}])) == ["S2"]
    page = ss.search(conn, {}, ADMIN, page=1, page_size=2)
    assert page["total"] == 3 and len(page["rows"]) == 1
    for sort in ("average_mark", "average_mark desc"):
        marks = [r["average_mark"] for r in ss.search(conn, {}, ADMIN, sort=sort)["rows"]]
        assert marks[-1] is None


def test_export_needs_permission_writes_visible_fields_and_is_audited(conn, tmp_path):
    with pytest.raises(ValueError, match="permission"):
        ss.export(conn, {}, Viewer("x", "staff", True), str(tmp_path / "no.csv"))
    path = tmp_path / "out.csv"
    assert ss.export(conn, {}, STAFF, str(path)) == 3
    header = next(csv.reader(path.open()))
    assert "Phone" not in header and "Average mark" in header
    actions = [(a["actor"], a["action"], a["count"]) for a in ss.audit_tail(conn)]
    assert ("lead", "export", 3) in actions


def test_saved_searches_are_private_until_shared_and_owner_controlled(conn):
    sid = sv.save(conn, STAFF, "CS", {"conditions": [{"field": "course", "op": "is",
                                                       "value": "CS"}]})
    other = Viewer("other", "staff", True)
    assert sv.saved(conn, other) == []
    sv.set_shared(conn, STAFF, sid, True)
    assert [s["name"] for s in sv.saved(conn, other)] == ["CS"]
    with pytest.raises(ValueError, match="owner"):
        sv.delete(conn, other, sid)
    assert sv.save(conn, STAFF, "CS", {"text": "Ana"}) == sid    # same name overwrites


def test_scheduled_report_runs_when_due_and_emails_a_summary(conn, tmp_path):
    sid = sv.save(conn, STAFF, "Everyone", {})
    with pytest.raises(ValueError, match="email"):
        sv.schedule(conn, STAFF, sid, "weekly", "nobody")
    sv.schedule(conn, STAFF, sid, "weekly", "lead@uni.uk")
    result = sv.run_due(conn, str(tmp_path))
    assert result["ran"] == 1 and result["failures"] == []
    (address, _subject, body), = result["emails"]
    assert address == "lead@uni.uk" and "Students: 3" in body and "ana@x.uk" not in body
    assert len(list(tmp_path.glob("*.csv"))) == 1
    assert sv.run_due(conn, str(tmp_path))["ran"] == 0
    assert sv.run_due(conn, str(tmp_path), now=datetime.now() + timedelta(days=7))["ran"] == 1


class _FakeService:
    def __init__(self):
        self.calls = []

    def update(self, sid, changes, **kw):
        if sid == "S2":
            raise ValueError("refused for S2")
        self.calls.append((sid, changes, kw["reason"]))


def test_bulk_actions_check_permission_reason_and_report_each_student(conn, monkeypatch):
    fake = _FakeService()
    monkeypatch.setattr(bulk, "_service", lambda *a: fake)
    monkeypatch.setattr(bulk, "_audit", lambda *a: None)
    with pytest.raises(ValueError, match="permission"):
        bulk.run("withdraw", ["S1"], STAFF, reason="x")
    with pytest.raises(ValueError, match="reason"):
        bulk.run("set_field", ["S1"], STAFF, value=("fee_status", "home"))
    with pytest.raises(ValueError, match="Only"):
        bulk.run("set_field", ["S1"], STAFF, value=("first_name", "X"), reason="r")
    result = bulk.run("set_field", ["S1", "S2", "S1"], STAFF,
                      value=("fee_status", "international"), reason="Fee review")
    assert result == {"done": 1, "failed": [("S2", "refused for S2")]}
    assert fake.calls == [("S1", {"fee_status": "international"}, "Fee review")]
