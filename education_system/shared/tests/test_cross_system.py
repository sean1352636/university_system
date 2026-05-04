"""Cross-system integration tests.

Improvement #10: Tests for scenarios spanning multiple systems —
shared auth, audit logging, migration framework, student portability,
reporting, rate limiting, and health checks.
"""

import pytest


class TestSharedAuthentication:
    def test_superadmin_has_access_to_all_systems(self, shared_auth_db):
        from education_system.shared.auth.core import UserAuth
        auth = UserAuth(shared_auth_db)
        result = auth.login("superadmin", "SuperAdmin@123")
        assert result is not None
        system_keys = {s["system_key"] for s in result.get("systems", [])}
        assert system_keys >= {"university", "college", "school", "primary"}

    def test_password_hashing_consistent(self, shared_auth_db):
        from education_system.shared.auth.core import UserAuth
        from education_system.shared.auth.exceptions import AuthError
        auth = UserAuth(shared_auth_db)
        assert auth.login("superadmin", "SuperAdmin@123") is not None
        with pytest.raises(AuthError):
            auth.login("superadmin", "wrong")


class TestAuditLogging:
    def test_write_and_query(self, tmp_path):
        from education_system.shared.audit.logger import AuditLogger, AuditAction
        audit = AuditLogger("college", db_path=str(tmp_path / "audit.db"))
        eid = audit.log(AuditAction.LOGIN, user_id=1, username="admin")
        assert eid > 0
        entries = audit.query(action=AuditAction.LOGIN)
        assert len(entries) >= 1
        assert entries[0]["username"] == "admin"

    def test_cross_system_isolation(self, tmp_path):
        from education_system.shared.audit.logger import AuditLogger, AuditAction
        db = str(tmp_path / "audit.db")
        c = AuditLogger("college", db_path=db)
        s = AuditLogger("school", db_path=db)
        c.log(AuditAction.CREATE, username="a1", target_type="student")
        s.log(AuditAction.CREATE, username="a2", target_type="student")
        assert len(c.query()) == 1
        assert len(s.query()) == 1


class TestStudentPortability:
    def test_json_roundtrip(self, tmp_path):
        from education_system.shared.transfer.portability import StudentDataExporter, StudentDataImporter
        students = [{"student_id": "SFC0001", "first_name": "John", "last_name": "Doe"}]
        StudentDataExporter("Test", "college").save(tmp_path / "out.json", students)
        imported = StudentDataImporter().load(tmp_path / "out.json")
        assert len(imported) == 1
        assert imported[0]["first_name"] == "John"

    def test_csv_roundtrip(self, tmp_path):
        from education_system.shared.transfer.portability import StudentDataExporter, StudentDataImporter
        students = [{"student_id": "SEC0001", "first_name": "Alice", "last_name": "B"}]
        StudentDataExporter("Test", "school").save(tmp_path / "out.csv", students)
        imported = StudentDataImporter().load(tmp_path / "out.csv")
        assert imported[0]["first_name"] == "Alice"

    def test_ctf_xml(self, tmp_path):
        from education_system.shared.transfer.portability import StudentDataExporter, StudentDataImporter
        students = [{"student_id": "PRI0001", "first_name": "Tom", "last_name": "G", "date_of_birth": "2018-05-15"}]
        StudentDataExporter("Test", "primary").save(tmp_path / "out.xml", students)
        imported = StudentDataImporter().load(tmp_path / "out.xml")
        assert imported[0]["date_of_birth"] == "2018-05-15"


class TestReportingEngine:
    def test_csv_report(self):
        from education_system.shared.reporting.engine import ReportEngine, ReportFormat
        data = ReportEngine().generate("Test", ["Name", "Score"], [["A", "1"]], ReportFormat.CSV)
        assert b"Name,Score" in data


class TestRateLimiter:
    def test_within_limit(self):
        from education_system.shared.api.rate_limiter import RateLimiter
        lim = RateLimiter()
        for _ in range(5):
            ok, _ = lim._check_rate("k", 5, 60)
            assert ok
        ok, _ = lim._check_rate("k", 5, 60)
        assert not ok


class TestHealthCheck:
    def test_liveness(self):
        from flask import Flask
        from education_system.shared.api.health import health_bp, init_health
        app = Flask(__name__)
        init_health(system_name="Test")
        app.register_blueprint(health_bp)
        with app.test_client() as c:
            r = c.get("/api/health/live")
            assert r.status_code == 200
            assert r.get_json()["alive"] is True


class TestDemoSeeder:
    def test_generate_students(self):
        from education_system.shared.seeding.seeder import DemoSeeder
        students = DemoSeeder("college").generate_students(10)
        assert len(students) == 10
        assert all(s["student_id"].startswith("SFC") for s in students)
