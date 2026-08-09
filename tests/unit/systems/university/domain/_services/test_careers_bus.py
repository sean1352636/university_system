"""Unit tests for the careers / engagement bus (``modules.services.careers_bus``).

``careers_bus`` owns the ``engagements`` schema and reaches the DB through the
shared ``get_connection`` helper, which resolves its target file from the
module-level ``DEFAULT_DB_PATH``. Repointing that constant at a per-test temp
file gives full isolation; the bus creates the ``engagements`` schema on every
call (``_ensure_schema``).

Unlike ``engagements``, the *employer*, *job board*, *alumni* and *attendance*
surfaces read/write tables the bus does NOT create itself (``employers``,
``job_postings``, ``alumni``, ``attendance_records`` — and the legacy
``posted_date`` column referenced by ``recent_jobs``). The fixture seeds those
empty stand-ins so the SQL stays valid.

``_publish`` (the academics event-bus fan-out) is neutralised per test, and the
cross-bus seams (``finance_bus.has_active_hold`` / ``finance_bus.raise_charge``)
are stubbed at their modules, exactly like the cert_bus template.
"""

from datetime import datetime, timedelta

import pytest

from education_system.systems.university.infrastructure.database.db import (
    sqlite3,
    get_connection,
)
from education_system.systems.university.services.bus import careers_bus


def _date(offset_days: int) -> str:
    return (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


@pytest.fixture()
def careers_db(tmp_path, monkeypatch):
    """Point the shared DB layer at a temp file, seed non-owned tables, silence publish."""
    db_path = str(tmp_path / "careers.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    monkeypatch.setattr(careers_bus, "_publish", lambda *a, **k: None)

    # Seed tables the bus reads/writes but does not create itself.
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE employers (
                employer_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT,
                industry     TEXT,
                contact_email TEXT,
                contact_phone TEXT,
                address      TEXT,
                description  TEXT,
                is_verified  INTEGER DEFAULT 0,
                created_at   TEXT
            );
            CREATE TABLE job_postings (
                job_id            INTEGER PRIMARY KEY AUTOINCREMENT,
                posted_by         TEXT,
                company_name      TEXT,
                job_title         TEXT,
                job_description   TEXT,
                location          TEXT,
                job_type          TEXT,
                category          TEXT,
                employer_id       INTEGER,
                post_date         TEXT,
                posted_date       TEXT,
                expiry_date       TEXT,
                is_active         INTEGER DEFAULT 1,
                applications_count INTEGER DEFAULT 0
            );
            CREATE TABLE alumni (
                student_id       TEXT,
                current_employer TEXT,
                job_title        TEXT
            );
            CREATE TABLE attendance_records (
                student_id TEXT,
                status     TEXT
            );
            """
        )
        conn.commit()
    return db_path


# ---------------------------------------------------------------------------
# start_engagement
# ---------------------------------------------------------------------------

class TestStartEngagement:
    def test_returns_id_and_persists(self, careers_db):
        eid = careers_bus.start_engagement(
            kind="internship", student_id="S001", role="Analyst",
            employer_id=None, hours_required=100,
        )
        assert isinstance(eid, int)
        rows = careers_bus.list_engagements("S001")
        assert len(rows) == 1
        assert rows[0]["kind"] == "internship"
        assert rows[0]["role"] == "Analyst"
        assert rows[0]["status"] == "active"

    def test_coerces_int_student_id(self, careers_db):
        eid = careers_bus.start_engagement(kind="job", student_id=42)
        assert eid is not None
        assert careers_bus.list_engagements("42")

    def test_invalid_kind_returns_none(self, careers_db):
        assert careers_bus.start_engagement(kind="banana", student_id="S001") is None

    def test_missing_student_returns_none(self, careers_db):
        assert careers_bus.start_engagement(kind="job", student_id="") is None
        assert careers_bus.start_engagement(kind="job", student_id=None) is None


# ---------------------------------------------------------------------------
# end_engagement
# ---------------------------------------------------------------------------

class TestEndEngagement:
    def test_ends_and_returns_true(self, careers_db):
        eid = careers_bus.start_engagement(kind="placement", student_id="S001")
        assert careers_bus.end_engagement(eid, status="completed") is True
        (row,) = careers_bus.list_engagements("S001")
        assert row["status"] == "completed"
        assert row["ended_on"]

    def test_unknown_returns_false(self, careers_db):
        careers_bus.start_engagement(kind="job", student_id="S001")
        assert careers_bus.end_engagement(999999) is False

    def test_falsy_id_returns_false(self, careers_db):
        assert careers_bus.end_engagement(0) is False


# ---------------------------------------------------------------------------
# log_hours
# ---------------------------------------------------------------------------

class TestLogHours:
    def test_accumulates_hours(self, careers_db):
        eid = careers_bus.start_engagement(
            kind="placement", student_id="S001", hours_required=50,
        )
        out = careers_bus.log_hours(eid, 20)
        assert out["ok"] is True
        assert out["hours_logged"] == 20.0
        assert out["completed"] is False
        out2 = careers_bus.log_hours(eid, 5)
        assert out2["hours_logged"] == 25.0

    def test_completes_when_reaching_required(self, careers_db):
        eid = careers_bus.start_engagement(
            kind="placement", student_id="S001", hours_required=10,
        )
        out = careers_bus.log_hours(eid, 10)
        assert out["completed"] is True
        assert out["hours_logged"] == 10.0
        assert out["hours_required"] == 10

    def test_no_required_never_completes(self, careers_db):
        eid = careers_bus.start_engagement(kind="job", student_id="S001")
        out = careers_bus.log_hours(eid, 99)
        assert out["ok"] is True
        assert out["completed"] is False

    def test_unknown_engagement_returns_default(self, careers_db):
        careers_bus.start_engagement(kind="job", student_id="S001")
        out = careers_bus.log_hours(999999, 5)
        assert out["ok"] is False

    def test_none_hours_returns_default(self, careers_db):
        eid = careers_bus.start_engagement(kind="job", student_id="S001")
        out = careers_bus.log_hours(eid, None)
        assert out["ok"] is False


# ---------------------------------------------------------------------------
# list_engagements
# ---------------------------------------------------------------------------

class TestListEngagements:
    def _seed(self):
        careers_bus.start_engagement(kind="job", student_id="S001")
        careers_bus.start_engagement(kind="internship", student_id="S001")
        careers_bus.start_engagement(kind="job", student_id="S002")

    def test_filter_by_student(self, careers_db):
        self._seed()
        assert len(careers_bus.list_engagements("S001")) == 2
        assert len(careers_bus.list_engagements("S002")) == 1

    def test_filter_by_kind(self, careers_db):
        self._seed()
        rows = careers_bus.list_engagements("S001", kind="internship")
        assert [r["kind"] for r in rows] == ["internship"]

    def test_only_active_excludes_completed(self, careers_db):
        eid = careers_bus.start_engagement(kind="job", student_id="S003")
        careers_bus.end_engagement(eid)
        assert careers_bus.list_engagements("S003", only_active=True) == []
        assert len(careers_bus.list_engagements("S003")) == 1

    def test_no_student_returns_all(self, careers_db):
        self._seed()
        assert len(careers_bus.list_engagements()) == 3


# ---------------------------------------------------------------------------
# engagement_progress
# ---------------------------------------------------------------------------

class TestEngagementProgress:
    def test_percent_calculation(self, careers_db):
        eid = careers_bus.start_engagement(
            kind="placement", student_id="S001", hours_required=40,
        )
        careers_bus.log_hours(eid, 10)
        prog = careers_bus.engagement_progress(eid)
        assert prog["percent"] == 25.0
        assert prog["hours_required"] == 40

    def test_no_required_percent_none(self, careers_db):
        eid = careers_bus.start_engagement(kind="job", student_id="S001")
        prog = careers_bus.engagement_progress(eid)
        assert prog["percent"] is None

    def test_apprenticeship_includes_off_job_hours(self, careers_db):
        eid = careers_bus.start_engagement(
            kind="apprenticeship", student_id="S001", hours_required=100,
        )
        with get_connection() as conn:
            conn.executemany(
                "INSERT INTO attendance_records (student_id, status) VALUES (?, ?)",
                [("S001", "present"), ("S001", "Present"), ("S001", "absent")],
            )
            conn.commit()
        prog = careers_bus.engagement_progress(eid)
        assert prog["off_job_hours"] == 2.0

    def test_unknown_returns_empty(self, careers_db):
        assert careers_bus.engagement_progress(999999) == {}


# ---------------------------------------------------------------------------
# apprenticeship_off_job_hours
# ---------------------------------------------------------------------------

class TestOffJobHours:
    def test_counts_present_case_insensitive(self, careers_db):
        eid = careers_bus.start_engagement(kind="apprenticeship", student_id="S001")
        with get_connection() as conn:
            conn.executemany(
                "INSERT INTO attendance_records (student_id, status) VALUES (?, ?)",
                [("S001", "present"), ("S001", "PRESENT"), ("S002", "present")],
            )
            conn.commit()
        assert careers_bus.apprenticeship_off_job_hours(eid) == 2.0

    def test_unknown_engagement_zero(self, careers_db):
        assert careers_bus.apprenticeship_off_job_hours(999999) == 0.0


# ---------------------------------------------------------------------------
# Employers
# ---------------------------------------------------------------------------

class TestEmployers:
    def test_upsert_insert_then_get(self, careers_db):
        emp_id = careers_bus.upsert_employer(
            company_name="Acme", industry="Tech", contact_email="hr@acme.test",
        )
        assert isinstance(emp_id, int)
        row = careers_bus.get_employer(emp_id)
        assert row["company_name"] == "Acme"
        assert row["industry"] == "Tech"

    def test_upsert_update_returns_same_id(self, careers_db):
        emp_id = careers_bus.upsert_employer(company_name="Acme", industry="Tech")
        same = careers_bus.upsert_employer(
            employer_id=emp_id, company_name="Acme Corp", industry="Finance",
        )
        assert same == emp_id
        assert careers_bus.get_employer(emp_id)["company_name"] == "Acme Corp"

    def test_get_none_for_missing(self, careers_db):
        assert careers_bus.get_employer(999999) is None

    def test_get_none_for_none_id(self, careers_db):
        assert careers_bus.get_employer(None) is None

    def test_list_industry_filter(self, careers_db):
        careers_bus.upsert_employer(company_name="Acme", industry="Tech")
        careers_bus.upsert_employer(company_name="Globex", industry="Finance")
        rows = careers_bus.list_employers(industry="tech")
        assert [r["company_name"] for r in rows] == ["Acme"]

    def test_list_verified_only(self, careers_db):
        careers_bus.upsert_employer(company_name="Acme", industry="Tech")
        vid = careers_bus.upsert_employer(company_name="Globex", industry="Finance")
        with get_connection() as conn:
            conn.execute(
                "UPDATE employers SET is_verified = 1 WHERE employer_id = ?", (vid,)
            )
            conn.commit()
        rows = careers_bus.list_employers(verified_only=True)
        assert [r["company_name"] for r in rows] == ["Globex"]


# ---------------------------------------------------------------------------
# Job board
# ---------------------------------------------------------------------------

class TestJobBoard:
    def test_post_returns_id_and_recent_lists_it(self, careers_db):
        jid = careers_bus.post_job(
            job_title="Engineer", company_name="Acme", category="Tech",
        )
        assert isinstance(jid, int)
        jobs = careers_bus.recent_jobs()
        assert [j["job_title"] for j in jobs] == ["Engineer"]

    def test_missing_title_returns_none(self, careers_db):
        assert careers_bus.post_job(job_title="") is None

    def test_recent_category_filter(self, careers_db):
        careers_bus.post_job(job_title="Engineer", category="Tech")
        careers_bus.post_job(job_title="Nurse", category="Health")
        rows = careers_bus.recent_jobs(category="health")
        assert [j["job_title"] for j in rows] == ["Nurse"]

    def test_recent_excludes_inactive(self, careers_db):
        careers_bus.post_job(job_title="Engineer")
        with get_connection() as conn:
            conn.execute("UPDATE job_postings SET is_active = 0")
            conn.commit()
        assert careers_bus.recent_jobs() == []

    def test_recent_since_filter(self, careers_db):
        jid_old = careers_bus.post_job(job_title="Old")
        careers_bus.post_job(job_title="New")
        with get_connection() as conn:
            conn.execute(
                "UPDATE job_postings SET post_date = ? WHERE job_id = ?",
                (_date(-40), jid_old),
            )
            conn.commit()
        rows = careers_bus.recent_jobs(since=_date(-10))
        assert [j["job_title"] for j in rows] == ["New"]


# ---------------------------------------------------------------------------
# can_apply  (finance seam stubbed)
# ---------------------------------------------------------------------------

class TestCanApply:
    def test_refused_on_active_hold(self, careers_db, monkeypatch):
        from education_system.systems.university.services.bus import finance_bus
        monkeypatch.setattr(finance_bus, "has_active_hold", lambda sid: True)
        out = careers_bus.can_apply("S001")
        assert out["ok"] is False
        assert "hold" in out["reason"].lower()

    def test_ok_without_hold(self, careers_db, monkeypatch):
        from education_system.systems.university.services.bus import finance_bus
        monkeypatch.setattr(finance_bus, "has_active_hold", lambda sid: False)
        out = careers_bus.can_apply("S001")
        assert out == {"ok": True, "reason": ""}


# ---------------------------------------------------------------------------
# post_apprenticeship_levy_charge  (finance seam stubbed)
# ---------------------------------------------------------------------------

class TestLevyCharge:
    def test_routes_charge_for_engagement_student(self, careers_db, monkeypatch):
        eid = careers_bus.start_engagement(kind="apprenticeship", student_id="S001")
        captured = {}
        from education_system.systems.university.services.bus import finance_bus
        monkeypatch.setattr(
            finance_bus, "raise_charge",
            lambda sid, amount, **kw: captured.update(sid=sid, amount=amount, **kw) or 77,
        )
        result = careers_bus.post_apprenticeship_levy_charge(eid, 250.0)
        assert result == 77
        assert captured["sid"] == "S001"
        assert captured["amount"] == 250.0
        assert captured["reference_id"] == f"engagement:{eid}"

    def test_unknown_engagement_returns_none(self, careers_db, monkeypatch):
        from education_system.systems.university.services.bus import finance_bus
        monkeypatch.setattr(finance_bus, "raise_charge", lambda *a, **k: 1)
        assert careers_bus.post_apprenticeship_levy_charge(999999, 100.0) is None

    def test_zero_amount_returns_none(self, careers_db):
        eid = careers_bus.start_engagement(kind="apprenticeship", student_id="S001")
        assert careers_bus.post_apprenticeship_levy_charge(eid, 0) is None


# ---------------------------------------------------------------------------
# snapshot_alumni_employer
# ---------------------------------------------------------------------------

class TestSnapshotAlumni:
    def test_updates_current_employer(self, careers_db):
        emp_id = careers_bus.upsert_employer(company_name="Acme")
        careers_bus.start_engagement(
            kind="job", student_id="S001", employer_id=emp_id, role="Analyst",
        )
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO alumni (student_id, current_employer, job_title) "
                "VALUES ('S001', NULL, NULL)"
            )
            conn.commit()
        assert careers_bus.snapshot_alumni_employer("S001") is True
        with get_connection() as conn:
            row = conn.execute(
                "SELECT current_employer, job_title FROM alumni WHERE student_id = 'S001'"
            ).fetchone()
        assert row["current_employer"] == "Acme"
        assert row["job_title"] == "Analyst"

    def test_no_engagement_returns_false(self, careers_db):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO alumni (student_id) VALUES ('S001')"
            )
            conn.commit()
        assert careers_bus.snapshot_alumni_employer("S001") is False

    def test_falsy_id_returns_false(self, careers_db):
        assert careers_bus.snapshot_alumni_employer("") is False
