"""Tests for the shared AdminService."""

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from education_system.shared.admin_portal.admin_service import AdminService


@pytest.fixture()
def temp_dbs(tmp_path):
    """Create temporary DBs for all 4 systems + auth."""
    db_paths = {}
    for system, table, id_col in [
        ("primary", "pupils", "pupil_id"),
        ("secondary", "students", "student_id"),
        ("college", "students", "student_id"),
        ("university", "students", "student_id"),
    ]:
        db_file = tmp_path / f"{system}.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute(
            f"CREATE TABLE {table} ({id_col} INTEGER PRIMARY KEY, name TEXT, status TEXT)"
        )
        conn.execute(f"INSERT INTO {table} (name, status) VALUES ('Alice', 'active')")
        conn.execute(f"INSERT INTO {table} (name, status) VALUES ('Bob', 'graduated')")
        if system != "primary":
            conn.execute("CREATE TABLE staff (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO staff (name) VALUES ('Prof X')")
        conn.commit()
        conn.close()
        db_paths[system] = db_file

    # Auth DB
    auth_db = tmp_path / "auth.db"
    conn = sqlite3.connect(str(auth_db))
    conn.execute(
        """CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            display_name TEXT,
            email TEXT,
            password_hash TEXT,
            is_active INTEGER DEFAULT 1,
            last_login TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE user_systems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            system_key TEXT,
            role TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            token TEXT,
            created_at TEXT,
            expires_at TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE cross_system_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_user_id INTEGER,
            sender_system TEXT,
            recipient_user_id INTEGER,
            recipient_system TEXT,
            title TEXT,
            message TEXT,
            priority TEXT DEFAULT 'normal',
            is_read INTEGER DEFAULT 0,
            created_at TEXT
        )"""
    )
    # Seed a test user
    conn.execute(
        "INSERT INTO users (username, display_name, email, password_hash, is_active) "
        "VALUES ('testadmin', 'Test Admin', 'admin@test.com', '$2b$12$fake', 1)"
    )
    conn.execute(
        "INSERT INTO user_systems (user_id, system_key, role) VALUES (1, 'university', 'admin')"
    )
    conn.execute(
        "INSERT INTO sessions (user_id, token, created_at, expires_at) "
        "VALUES (1, 'tok_abc123', '2026-01-01 00:00:00', '2099-12-31 23:59:59')"
    )
    conn.commit()
    conn.close()

    return db_paths, auth_db


@pytest.fixture()
def svc(temp_dbs):
    db_paths, auth_db = temp_dbs
    return AdminService(db_paths=db_paths, auth_db=str(auth_db))


class TestSystemHealth:
    def test_returns_all_systems(self, svc):
        health = svc.get_system_health()
        assert len(health) == 4
        systems = {h["system"] for h in health}
        assert systems == {"primary", "secondary", "college", "university"}

    def test_counts_students(self, svc):
        health = svc.get_system_health()
        for h in health:
            assert h["student_count"] == 2
            assert h["db_exists"] is True
            assert h["status"] == "online"

    def test_counts_staff(self, svc):
        health = svc.get_system_health()
        primary = next(h for h in health if h["system"] == "primary")
        uni = next(h for h in health if h["system"] == "university")
        assert primary["staff_count"] == 0  # no staff table in primary test DB
        assert uni["staff_count"] == 1


class TestComparison:
    def test_one_row_per_system(self, svc):
        rows = svc.get_comparison()
        assert len(rows) == 4
        assert {r["system"] for r in rows} == {
            "primary", "secondary", "college", "university"
        }

    def test_row_shape(self, svc):
        row = svc.get_comparison()[0]
        for key in ("system", "label", "status", "student_count", "staff_count",
                    "user_count", "db_size_mb", "last_backup_days", "open_issues"):
            assert key in row

    def test_counts_match_health(self, svc):
        rows = svc.get_comparison()
        for r in rows:
            assert r["student_count"] == 2
            assert r["status"] == "online"

    def test_user_count_per_system(self, svc):
        rows = svc.get_comparison()
        uni = next(r for r in rows if r["system"] == "university")
        primary = next(r for r in rows if r["system"] == "primary")
        # Fixture seeds one university admin and no primary users.
        assert uni["user_count"] == 1
        assert primary["user_count"] == 0

    def test_never_backed_up_is_none(self, svc):
        rows = svc.get_comparison()
        assert all(r["last_backup_days"] is None for r in rows)

    def test_backup_updates_recency(self, svc):
        svc.backup_database("university")
        uni = next(r for r in svc.get_comparison() if r["system"] == "university")
        assert uni["last_backup_days"] == 0

    def test_open_issues_counts_backup_alert(self, svc):
        # No system is backed up, so each row carries its backup alert as an issue.
        rows = svc.get_comparison()
        assert all(r["open_issues"] >= 1 for r in rows)

    def test_missing_db_reflected(self, svc, temp_dbs):
        db_paths, _ = temp_dbs
        Path(db_paths["college"]).unlink()
        college = next(r for r in svc.get_comparison() if r["system"] == "college")
        assert college["status"] == "offline"


class _FakeJourney:
    """Stand-in JourneyService for unified-search tests."""

    def __init__(self, students=None):
        self._students = students or []

    def search_student(self, query):
        q = query.lower()
        return [s for s in self._students if q in s.get("name", "").lower()]


class TestSearch:
    def _svc(self, temp_dbs, students=None):
        db_paths, auth = temp_dbs
        return AdminService(
            db_paths=db_paths, auth_db=str(auth),
            journey_service=_FakeJourney(students or []),
        )

    def test_empty_query(self, temp_dbs):
        assert self._svc(temp_dbs).search("  ") == {
            "query": "", "users": [], "students": []
        }

    def test_finds_user_by_username(self, temp_dbs):
        res = self._svc(temp_dbs).search("testadmin")
        assert len(res["users"]) == 1
        user = res["users"][0]
        assert user["username"] == "testadmin"
        assert user["status"] == "active"
        assert {s["system_key"] for s in user["systems"]} == {"university"}

    def test_finds_user_by_email(self, temp_dbs):
        res = self._svc(temp_dbs).search("admin@test.com")
        assert any(u["username"] == "testadmin" for u in res["users"])

    def test_inactive_status(self, temp_dbs):
        svc = self._svc(temp_dbs)
        svc.deactivate_user(1)
        assert svc.search("testadmin")["users"][0]["status"] == "inactive"

    def test_students_come_from_journey(self, temp_dbs):
        students = [{
            "system": "university", "id": 1, "student_id": "U1",
            "name": "Alice Smith", "status": "active", "year_group": "Y1",
        }]
        res = self._svc(temp_dbs, students).search("alice")
        assert len(res["students"]) == 1
        assert res["students"][0]["name"] == "Alice Smith"
        # The query also matches no users here.
        assert res["users"] == []

    def test_ranking_exact_username_first(self, temp_dbs):
        svc = self._svc(temp_dbs)
        svc.create_user("admin", "Site Admin", "a@test.com", "pw",
                        [{"system_key": "college", "role": "admin"}])
        res = svc.search("admin")
        # 'admin' is an exact username match; 'testadmin' matches as a substring.
        assert res["users"][0]["username"] == "admin"
        assert len(res["users"]) >= 2

    def test_locked_status(self, tmp_path):
        auth = tmp_path / "auth_lock.db"
        conn = sqlite3.connect(str(auth))
        conn.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, "
            "display_name TEXT, email TEXT, is_active INTEGER DEFAULT 1, "
            "last_login TEXT, locked_until TEXT)"
        )
        conn.execute(
            "CREATE TABLE user_systems (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user_id INTEGER, system_key TEXT, role TEXT)"
        )
        conn.execute(
            "INSERT INTO users (username, locked_until) VALUES ('bob', ?)",
            ((datetime.utcnow() + timedelta(hours=1)).isoformat(),),
        )
        conn.commit()
        conn.close()
        svc = AdminService(db_paths={}, auth_db=str(auth), journey_service=_FakeJourney())
        assert svc.search("bob")["users"][0]["status"] == "locked"


class TestTrends:
    def _svc(self, temp_dbs, tmp_path):
        db_paths, auth = temp_dbs
        return AdminService(
            db_paths=db_paths, auth_db=str(auth),
            metrics_db=str(tmp_path / "metrics.db"),
        )

    def test_snapshot_records_metrics(self, temp_dbs, tmp_path):
        svc = self._svc(temp_dbs, tmp_path)
        n = svc.record_metrics_snapshot(as_of="2026-06-01")
        assert n == 4
        series = svc.get_metric_series("students")
        assert len(series) == 1
        # 4 systems x 2 students each in the fixture.
        assert series[0]["value"] == 8
        assert series[0]["date"] == "2026-06-01"

    def test_snapshot_idempotent_per_day(self, temp_dbs, tmp_path):
        svc = self._svc(temp_dbs, tmp_path)
        svc.record_metrics_snapshot(as_of="2026-06-01")
        svc.record_metrics_snapshot(as_of="2026-06-01")
        assert len(svc.get_metric_series("students")) == 1

    def test_series_ordered_oldest_first(self, temp_dbs, tmp_path):
        svc = self._svc(temp_dbs, tmp_path)
        for date in ("2026-06-03", "2026-06-01", "2026-06-02"):
            svc.record_metrics_snapshot(as_of=date)
        dates = [p["date"] for p in svc.get_metric_series("students")]
        assert dates == ["2026-06-01", "2026-06-02", "2026-06-03"]

    def test_get_trends_computes_change(self, temp_dbs, tmp_path):
        db_paths, _ = temp_dbs
        svc = self._svc(temp_dbs, tmp_path)
        svc.record_metrics_snapshot(as_of="2026-06-01")
        # Add a university student, then snapshot the next day.
        conn = sqlite3.connect(str(db_paths["university"]))
        conn.execute("INSERT INTO students (name, status) VALUES ('New', 'active')")
        conn.commit()
        conn.close()
        svc.record_metrics_snapshot(as_of="2026-06-02")

        trends = {t["metric"]: t for t in svc.get_trends()}
        students = trends["students"]
        assert students["values"] == [8, 9]
        assert students["current"] == 9
        assert students["change"] == 1
        assert students["change_pct"] == 12.5
        assert students["count"] == 2

    def test_no_history_yet(self, temp_dbs, tmp_path):
        svc = self._svc(temp_dbs, tmp_path)
        trends = svc.get_trends()
        assert len(trends) == 4
        assert all(t["values"] == [] for t in trends)
        assert all(t["count"] == 0 for t in trends)
        assert all(t["change"] == 0 for t in trends)


class TestUserManagement:
    def test_get_user_summary(self, svc):
        summary = svc.get_user_summary()
        assert summary["total_users"] == 1
        assert "university" in summary["by_system"]

    def test_get_all_users(self, svc):
        users = svc.get_all_users()
        assert len(users) == 1
        assert users[0]["username"] == "testadmin"
        assert len(users[0]["systems"]) == 1

    def test_get_all_users_filter_by_system(self, svc):
        assert len(svc.get_all_users(system="university")) == 1
        assert len(svc.get_all_users(system="primary")) == 0

    def test_get_all_users_filter_by_role(self, svc):
        assert len(svc.get_all_users(role="admin")) == 1
        assert len(svc.get_all_users(role="student")) == 0

    def test_create_user(self, svc):
        uid = svc.create_user(
            "newuser", "New User", "new@test.com", "Pass123!",
            [{"system_key": "college", "role": "staff"}],
        )
        assert uid is not None
        users = svc.get_all_users()
        assert len(users) == 2
        new = next(u for u in users if u["username"] == "newuser")
        assert new["display_name"] == "New User"
        assert new["systems"][0]["system_key"] == "college"

    def test_create_duplicate_user_raises(self, svc):
        with pytest.raises(ValueError, match="already exists"):
            svc.create_user("testadmin", "Dup", "dup@test.com", "pw", [])

    def test_update_user(self, svc):
        svc.update_user(1, display_name="Updated Admin", email="updated@test.com")
        users = svc.get_all_users()
        assert users[0]["display_name"] == "Updated Admin"
        assert users[0]["email"] == "updated@test.com"

    def test_deactivate_user(self, svc):
        svc.deactivate_user(1)
        users = svc.get_all_users()
        assert users[0]["is_active"] is False

    def test_reset_password(self, svc):
        # Should not raise
        svc.reset_password(1, "NewPassword123!")

    def test_update_user_systems(self, svc):
        svc.update_user_systems(1, [
            {"system_key": "primary", "role": "admin"},
            {"system_key": "secondary", "role": "staff"},
        ])
        users = svc.get_all_users()
        assert len(users[0]["systems"]) == 2
        sys_keys = {s["system_key"] for s in users[0]["systems"]}
        assert sys_keys == {"primary", "secondary"}


class TestBackup:
    def test_backup_creates_file(self, svc, temp_dbs):
        db_paths, _ = temp_dbs
        backup_path = svc.backup_database("university")
        assert Path(backup_path).exists()
        assert "backup_" in backup_path

    def test_backup_missing_system_raises(self, svc):
        with pytest.raises(ValueError):
            svc.backup_database("nonexistent")


class TestAuditLog:
    def test_empty_audit(self, svc):
        entries = svc.get_audit_summary()
        assert isinstance(entries, list)

    def test_audit_filters(self, svc):
        # Should not raise with any filter combo
        entries = svc.get_audit_summary(
            type_filter="notification",
            search_text="test",
            date_from="2020-01-01",
            date_to="2030-12-31",
        )
        assert isinstance(entries, list)


class TestSessions:
    def test_get_active_sessions(self, svc):
        sessions = svc.get_active_sessions()
        assert len(sessions) >= 1
        assert sessions[0]["username"] == "testadmin"

    def test_force_logout(self, svc):
        svc.force_logout_user(1)
        sessions = svc.get_active_sessions()
        assert len(sessions) == 0


class TestSystemConfig:
    def test_get_system_config(self, svc):
        cfg = svc.get_system_config("university")
        assert cfg["system"] == "university"
        assert cfg["db_exists"] is True
        assert cfg["db_size_mb"] >= 0


class TestAlerts:
    def test_returns_list(self, svc):
        assert isinstance(svc.get_alerts(), list)

    def test_flags_missing_backups(self, svc):
        # No system has been backed up yet, so each should raise a backup alert.
        alerts = svc.get_alerts()
        backup_alerts = [a for a in alerts if a["category"] == "backup"]
        # 4 systems in the fixture, none backed up
        assert len(backup_alerts) == 4
        assert all(a["severity"] == "warning" for a in backup_alerts)
        assert all(a["action"] == "backup" for a in backup_alerts)

    def test_recent_backup_clears_alert(self, svc):
        svc.backup_database("university")
        alerts = svc.get_alerts()
        uni_backup = [
            a for a in alerts
            if a["category"] == "backup" and a["system"] == "university"
        ]
        assert uni_backup == []

    def test_missing_db_is_critical(self, svc, temp_dbs):
        db_paths, _ = temp_dbs
        Path(db_paths["college"]).unlink()
        alerts = svc.get_alerts()
        college = [a for a in alerts if a["system"] == "college" and a["category"] == "health"]
        assert len(college) == 1
        assert college[0]["severity"] == "critical"
        assert college[0]["action"] == "health"

    def test_critical_sorted_first(self, svc, temp_dbs):
        db_paths, _ = temp_dbs
        Path(db_paths["college"]).unlink()
        alerts = svc.get_alerts()
        assert alerts[0]["severity"] == "critical"

    def test_db_size_threshold(self, svc):
        # Tiny test DBs trip the threshold when it's set very low.
        alerts = svc.get_alerts(db_size_warn_mb=0.0001)
        storage = [a for a in alerts if a["category"] == "storage"]
        assert len(storage) == 4
        # Disabling the check removes them.
        alerts = svc.get_alerts(db_size_warn_mb=0)
        assert [a for a in alerts if a["category"] == "storage"] == []

    def test_stale_session_flagged(self, svc):
        # The seeded session was created 2026-01-01; relative to "now" it is stale.
        alerts = svc.get_alerts()
        session_alerts = [a for a in alerts if a["category"] == "sessions"]
        assert len(session_alerts) == 1
        assert session_alerts[0]["severity"] == "warning"
        assert session_alerts[0]["action"] == "sessions"

    def test_no_security_alert_when_column_absent(self, svc):
        # Fixture users table has no locked_until column -> no lockout alerts.
        assert [a for a in svc.get_alerts() if a["category"] == "security"] == []


class TestFailedLoginAlerts:
    @staticmethod
    def _auth_with_lockout(tmp_path, locked_until):
        auth = tmp_path / "auth_lock.db"
        conn = sqlite3.connect(str(auth))
        conn.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, "
            "is_active INTEGER DEFAULT 1, failed_login_attempts INTEGER DEFAULT 0, "
            "locked_until TEXT)"
        )
        conn.execute(
            "INSERT INTO users (username, failed_login_attempts, locked_until) "
            "VALUES ('bob', 5, ?)",
            (locked_until,),
        )
        conn.commit()
        conn.close()
        return auth

    def test_active_lockout_flagged(self, tmp_path):
        future = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        auth = self._auth_with_lockout(tmp_path, future)
        svc = AdminService(db_paths={}, auth_db=str(auth))
        sec = [a for a in svc.get_alerts() if a["category"] == "security"]
        assert len(sec) == 1
        assert sec[0]["severity"] == "warning"
        assert sec[0]["action"] == "users"

    def test_expired_lockout_not_flagged(self, tmp_path):
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        auth = self._auth_with_lockout(tmp_path, past)
        svc = AdminService(db_paths={}, auth_db=str(auth))
        assert [a for a in svc.get_alerts() if a["category"] == "security"] == []


class TestMisconductAlerts:
    @staticmethod
    def _misconduct_db(tmp_path, rows):
        mdb = tmp_path / "misconduct.db"
        conn = sqlite3.connect(str(mdb))
        conn.execute(
            "CREATE TABLE academic_misconduct_cases (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "case_id TEXT, status TEXT, severity TEXT, date_filed TEXT)"
        )
        for status, severity, date_filed in rows:
            conn.execute(
                "INSERT INTO academic_misconduct_cases (case_id, status, severity, date_filed) "
                "VALUES ('AMC-1', ?, ?, ?)",
                (status, severity, date_filed),
            )
        conn.commit()
        conn.close()
        return mdb

    def _svc(self, tmp_path, mdb):
        # Empty db_paths + non-existent auth DB isolate the misconduct checks.
        return AdminService(
            db_paths={}, auth_db=str(tmp_path / "none.db"), misconduct_db=str(mdb)
        )

    def test_overdue_case_flagged(self, tmp_path):
        mdb = self._misconduct_db(tmp_path, [("Under Review", "Low", "2026-01-01")])
        alerts = self._svc(tmp_path, mdb).get_alerts(misconduct_sla_days=30)
        mc = [a for a in alerts if a["category"] == "misconduct"]
        assert any("unresolved for over" in a["message"] for a in mc)

    def test_resolved_case_not_flagged(self, tmp_path):
        mdb = self._misconduct_db(tmp_path, [("Resolved", "Critical", "2020-01-01")])
        alerts = self._svc(tmp_path, mdb).get_alerts(misconduct_sla_days=30)
        assert [a for a in alerts if a["category"] == "misconduct"] == []

    def test_critical_open_flagged_even_if_recent(self, tmp_path):
        recent = datetime.utcnow().strftime("%Y-%m-%d")
        mdb = self._misconduct_db(tmp_path, [("Pending Hearing", "Critical", recent)])
        alerts = self._svc(tmp_path, mdb).get_alerts(misconduct_sla_days=30)
        mc = [a for a in alerts if a["category"] == "misconduct"]
        assert any("critical misconduct" in a["message"] for a in mc)
        # Recent, so it should NOT be counted as overdue.
        assert not any("unresolved for over" in a["message"] for a in mc)

    def test_missing_table_no_alert(self, tmp_path):
        empty = tmp_path / "misconduct.db"
        sqlite3.connect(str(empty)).close()
        alerts = self._svc(tmp_path, empty).get_alerts()
        assert [a for a in alerts if a["category"] == "misconduct"] == []
