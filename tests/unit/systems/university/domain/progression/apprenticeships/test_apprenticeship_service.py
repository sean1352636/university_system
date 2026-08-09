"""Behavioral tests for the apprenticeship data/service layer.

``Database`` bootstraps its own canonical tables (students, employers,
apprenticeships, applications) over the shared ``get_connection`` path, so the
fixture only needs to point ``DEFAULT_DB_PATH`` at an empty **temp** DB (never
the live app DB). ``ApprenticeshipService`` is exercised end-to-end against that
real sqlite file; ``submit_as_apl``'s cross-service delegate is faked.
"""

import os
from unittest.mock import patch

import pytest

from education_system.systems.university.domain.progression.apprenticeships import (
    apprenticeship_service as mod,
)
from education_system.systems.university.domain.progression.apprenticeships.apprenticeship_service import (
    ApprenticeshipService,
    Database,
)

_DB_PATH_ATTR = (
    "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH"
)
_PLS_PATH = (
    "education_system.systems.university.domain.academics."
    "prior_learning_recognition.services.prior_learning_service.PriorLearningService"
)


@pytest.fixture()
def service(tmp_path, monkeypatch):
    """ApprenticeshipService backed by an empty temp DB it bootstraps itself."""
    db_path = str(tmp_path / "appr.db")
    monkeypatch.setattr(_DB_PATH_ATTR, db_path)
    svc = ApprenticeshipService()
    yield svc
    svc.close()


def _employer_and_appr(svc, *, company="Acme", title="Data Apprentice"):
    """Convenience: create an employer + apprenticeship, return (emp_id, appr_id)."""
    emp_id = svc.add_employer(company, "Pat Boss", "pat@acme.test")
    appr_id = svc.add_apprenticeship(title, emp_id, 12, salary=20000,
                                     location="Leeds", required_course="CS")
    return emp_id, appr_id


# ---------------------------------------------------------------------------
# _remove_legacy_db
# ---------------------------------------------------------------------------

class TestRemoveLegacyDb:
    def test_removes_all_siblings(self, tmp_path, monkeypatch):
        base = str(tmp_path / "apprenticeships.db")
        monkeypatch.setattr(mod, "_LEGACY_DB_FILE", base)
        for suffix in ("", "-wal", "-shm", "-journal"):
            with open(base + suffix, "w") as fh:
                fh.write("x")

        mod._remove_legacy_db()

        for suffix in ("", "-wal", "-shm", "-journal"):
            assert not os.path.exists(base + suffix)

    def test_missing_files_are_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "_LEGACY_DB_FILE", str(tmp_path / "nope.db"))
        mod._remove_legacy_db()  # must not raise

    def test_oserror_is_swallowed(self, tmp_path, monkeypatch):
        base = str(tmp_path / "apprenticeships.db")
        monkeypatch.setattr(mod, "_LEGACY_DB_FILE", base)
        with open(base, "w") as fh:
            fh.write("x")

        def _boom(path):
            raise OSError("permission denied")

        monkeypatch.setattr(mod.os, "remove", _boom)
        mod._remove_legacy_db()  # logs a warning, does not raise


# ---------------------------------------------------------------------------
# Database bootstrap
# ---------------------------------------------------------------------------

class TestDatabase:
    def test_schema_tables_created(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_DB_PATH_ATTR, str(tmp_path / "d.db"))
        db = Database()
        names = {
            r[0]
            for r in db.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"students", "employers", "apprenticeships", "applications"} <= names
        # optional columns added by ALTER
        cols = {r[1] for r in db.fetch_all("PRAGMA table_info(students)")}
        assert "gpa" in cols
        cols_e = {r[1] for r in db.fetch_all("PRAGMA table_info(employers)")}
        assert "address" in cols_e
        db.close()

    def test_init_idempotent(self, tmp_path, monkeypatch):
        path = str(tmp_path / "d.db")
        monkeypatch.setattr(_DB_PATH_ATTR, path)
        Database().close()
        Database().close()  # second bootstrap over same DB must not raise

    def test_cleanup_drops_empty_legacy_table(self, tmp_path, monkeypatch):
        path = str(tmp_path / "d.db")
        monkeypatch.setattr(_DB_PATH_ATTR, path)
        db = Database()
        db.execute("CREATE TABLE apprenticeship_listings (id INTEGER)")
        db.close()
        # Re-open: cleanup should drop the empty legacy table.
        db2 = Database()
        names = {
            r[0]
            for r in db2.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "apprenticeship_listings" not in names
        db2.close()

    def test_cleanup_keeps_nonempty_legacy_table(self, tmp_path, monkeypatch):
        path = str(tmp_path / "d.db")
        monkeypatch.setattr(_DB_PATH_ATTR, path)
        db = Database()
        db.execute("CREATE TABLE apprenticeship_students (id INTEGER)")
        db.execute("INSERT INTO apprenticeship_students (id) VALUES (1)")
        db.close()
        db2 = Database()
        names = {
            r[0]
            for r in db2.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "apprenticeship_students" in names  # left in place
        db2.close()

    def test_close_is_safe_to_call_twice(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_DB_PATH_ATTR, str(tmp_path / "d.db"))
        db = Database()
        db.close()
        db.close()  # swallowed

    def test_close_swallows_connection_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_DB_PATH_ATTR, str(tmp_path / "d.db"))
        db = Database()
        real = db.conn

        class _Boom:
            def close(self):
                raise RuntimeError("cannot close")

        db.conn = _Boom()
        db.close()  # exception swallowed
        real.close()

    def test_cleanup_swallows_sqlite_error(self, tmp_path, monkeypatch):
        import sqlite3 as _sq

        monkeypatch.setattr(_DB_PATH_ATTR, str(tmp_path / "d.db"))
        db = Database()
        db.execute("CREATE TABLE apprenticeship_employers (id INTEGER)")
        real = db.conn

        class _FlakyConn:
            def execute(self, query, *a, **k):
                if "COUNT(*)" in query:
                    raise _sq.Error("boom")
                return real.execute(query, *a, **k)

            def commit(self):
                return real.commit()

        db.conn = _FlakyConn()
        db._cleanup_module_private_tables()  # sqlite3.Error swallowed
        db.conn = real
        db.close()


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

class TestStudents:
    def test_add_and_list(self, service):
        service.add_student("S1", "Ann", "Smith", "ann@x.test", "CS",
                            year_of_study=2, gpa=3.5)
        students = service.list_students()
        assert len(students) == 1
        s = students[0]
        assert s["student_id"] == "S1"
        assert s["first_name"] == "Ann"
        assert s["gpa"] == 3.5

    def test_list_ordered_by_last_name(self, service):
        service.add_student("S1", "Ann", "Zephyr", "a@x.test", "CS")
        service.add_student("S2", "Bob", "Adams", "b@x.test", "CS")
        names = [s["last_name"] for s in service.list_students()]
        assert names == ["Adams", "Zephyr"]

    def test_list_with_search(self, service):
        service.add_student("S1", "Ann", "Smith", "ann@x.test", "CS")
        service.add_student("S2", "Bob", "Jones", "bob@x.test", "Maths")
        assert {s["student_id"] for s in service.list_students("Smith")} == {"S1"}
        assert {s["student_id"] for s in service.list_students("Maths")} == {"S2"}
        assert service.list_students("nomatch") == []

    def test_update_student_and_cascade_clears_applications(self, service):
        service.add_student("S1", "Ann", "Smith", "ann@x.test", "CS")
        _, appr_id = _employer_and_appr(service)
        service.submit_application("S1", appr_id)
        assert len(service.list_applications()) == 1

        service.update_student("S1", "S1", "Ann", "Smyth", "ann2@x.test", "Maths")
        # applications for the old id were cleared
        assert service.list_applications() == []
        updated = service.list_students()[0]
        assert updated["last_name"] == "Smyth"
        assert updated["course"] == "Maths"

    def test_delete_student_clears_applications(self, service):
        service.add_student("S1", "Ann", "Smith", "ann@x.test", "CS")
        _, appr_id = _employer_and_appr(service)
        service.submit_application("S1", appr_id)
        service.delete_student("S1")
        assert service.list_students() == []
        assert service.list_applications() == []


# ---------------------------------------------------------------------------
# Employers
# ---------------------------------------------------------------------------

class TestEmployers:
    def test_add_returns_id_and_list(self, service):
        eid = service.add_employer("Acme", "Pat", "pat@acme.test",
                                   phone="123", industry="Tech", address="1 St")
        assert isinstance(eid, int)
        emps = service.list_employers()
        assert len(emps) == 1
        assert emps[0]["company_name"] == "Acme"
        assert emps[0]["address"] == "1 St"

    def test_update_employer(self, service):
        eid = service.add_employer("Acme", "Pat", "pat@acme.test")
        service.update_employer(eid, "Acme Ltd", "Pat B", "new@acme.test",
                               phone="999", industry="Eng", address="2 Rd")
        emp = service.list_employers()[0]
        assert emp["company_name"] == "Acme Ltd"
        assert emp["contact_email"] == "new@acme.test"
        assert emp["industry"] == "Eng"

    def test_delete_employer_cascades_apprenticeships_and_applications(self, service):
        service.add_student("S1", "Ann", "Smith", "ann@x.test", "CS")
        eid, appr_id = _employer_and_appr(service)
        service.submit_application("S1", appr_id)

        service.delete_employer(eid)
        assert service.list_employers() == []
        assert service.list_apprenticeships() == []
        assert service.list_applications() == []


# ---------------------------------------------------------------------------
# Apprenticeships
# ---------------------------------------------------------------------------

class TestApprenticeships:
    def test_add_and_list_joins_employer(self, service):
        eid, appr_id = _employer_and_appr(service, company="Acme",
                                          title="Data Apprentice")
        rows = service.list_apprenticeships()
        assert len(rows) == 1
        assert rows[0]["title"] == "Data Apprentice"
        assert rows[0]["company_name"] == "Acme"
        assert rows[0]["salary"] == 20000

    def test_list_filtered_by_status(self, service):
        eid = service.add_employer("Acme", "Pat", "pat@acme.test")
        service.add_apprenticeship("Open Role", eid, 12, status="Open")
        service.add_apprenticeship("Closed Role", eid, 12, status="Closed")
        open_titles = {a["title"] for a in service.list_apprenticeships(status="Open")}
        assert open_titles == {"Open Role"}

    def test_update_apprenticeship(self, service):
        eid, appr_id = _employer_and_appr(service)
        service.update_apprenticeship(appr_id, "Senior Apprentice", eid, 24,
                                     salary=30000, status="Closed")
        row = service.list_apprenticeships()[0]
        assert row["title"] == "Senior Apprentice"
        assert row["duration_months"] == 24
        assert row["status"] == "Closed"

    def test_delete_apprenticeship_clears_applications(self, service):
        service.add_student("S1", "Ann", "Smith", "ann@x.test", "CS")
        eid, appr_id = _employer_and_appr(service)
        service.submit_application("S1", appr_id)
        service.delete_apprenticeship(appr_id)
        assert service.list_apprenticeships() == []
        assert service.list_applications() == []


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

class TestApplications:
    def test_submit_and_list_joins(self, service):
        service.add_student("S1", "Ann", "Smith", "ann@x.test", "CS")
        eid, appr_id = _employer_and_appr(service, company="Acme",
                                          title="Data Apprentice")
        app_id = service.submit_application("S1", appr_id, notes="keen")
        assert isinstance(app_id, int)
        rows = service.list_applications()
        assert len(rows) == 1
        r = rows[0]
        assert r["student_name"] == "Ann Smith"
        assert r["student_id"] == "S1"
        assert r["title"] == "Data Apprentice"
        assert r["company_name"] == "Acme"
        assert r["status"] == "Pending"

    def test_list_filtered_by_status(self, service):
        service.add_student("S1", "Ann", "Smith", "ann@x.test", "CS")
        eid, appr_id = _employer_and_appr(service)
        a1 = service.submit_application("S1", appr_id, status="Pending")
        service.update_application_status(a1, "Accepted")
        assert len(service.list_applications(status="Accepted")) == 1
        assert service.list_applications(status="Pending") == []

    def test_update_status_without_notes(self, service):
        service.add_student("S1", "Ann", "Smith", "ann@x.test", "CS")
        eid, appr_id = _employer_and_appr(service)
        a1 = service.submit_application("S1", appr_id, notes="original")
        service.update_application_status(a1, "Reviewed")
        row = service.db.fetch_one(
            "SELECT status, notes FROM applications WHERE id=?", (a1,))
        assert row[0] == "Reviewed"
        assert row[1] == "original"  # notes untouched

    def test_update_status_with_notes(self, service):
        service.add_student("S1", "Ann", "Smith", "ann@x.test", "CS")
        eid, appr_id = _employer_and_appr(service)
        a1 = service.submit_application("S1", appr_id)
        service.update_application_status(a1, "Rejected", notes="not a fit")
        row = service.db.fetch_one(
            "SELECT status, notes FROM applications WHERE id=?", (a1,))
        assert row[0] == "Rejected"
        assert row[1] == "not a fit"

    def test_delete_application(self, service):
        service.add_student("S1", "Ann", "Smith", "ann@x.test", "CS")
        eid, appr_id = _employer_and_appr(service)
        a1 = service.submit_application("S1", appr_id)
        service.delete_application(a1)
        assert service.list_applications() == []


# ---------------------------------------------------------------------------
# submit_as_apl
# ---------------------------------------------------------------------------

class _FakePLS:
    """Records the placement-evidence call and returns a fixed claim id."""

    calls = []

    def create_evidence_from_placement(self, student_id, **kwargs):
        _FakePLS.calls.append((student_id, kwargs))
        return 4242


class TestSubmitAsApl:
    def setup_method(self):
        _FakePLS.calls = []

    def test_resolves_employer_from_latest_application(self, service):
        service.add_student("S1", "Ann", "Smith", "ann@x.test", "CS")
        eid, appr_id = _employer_and_appr(service, company="Acme Corp")
        service.submit_application("S1", appr_id)

        with patch(_PLS_PATH, _FakePLS):
            claim_id = service.submit_as_apl("S1", course="CS")

        assert claim_id == 4242
        student_id, kwargs = _FakePLS.calls[0]
        assert student_id == "S1"
        assert kwargs["employer"] == "Acme Corp"
        assert kwargs["target_course"] == "CS"
        assert kwargs["total_hours"] == 0.0

    def test_defaults_employer_when_no_application(self, service):
        service.add_student("S2", "Bea", "Jones", "bea@x.test", "CS")

        with patch(_PLS_PATH, _FakePLS):
            claim_id = service.submit_as_apl("S2")

        assert claim_id == 4242
        _, kwargs = _FakePLS.calls[0]
        assert kwargs["employer"] == "Apprenticeship employer"

    def test_query_error_falls_back_to_default_employer(self, service, monkeypatch):
        # Force the employer-resolution query to raise; method must still submit.
        def _boom(query, params=()):
            raise RuntimeError("db exploded")

        monkeypatch.setattr(service.db, "fetch_one", _boom)
        with patch(_PLS_PATH, _FakePLS):
            claim_id = service.submit_as_apl("S3")

        assert claim_id == 4242
        _, kwargs = _FakePLS.calls[0]
        assert kwargs["employer"] == "Apprenticeship employer"
