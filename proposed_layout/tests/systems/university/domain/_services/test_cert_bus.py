"""Unit tests for the shared certification-expiry bus (``modules.services.cert_bus``).

``cert_bus`` owns the ``staff_certifications`` schema and reaches the DB through the
shared ``get_connection`` helper, which resolves its target file from the module-level
``DEFAULT_DB_PATH``. Repointing that constant at a per-test temp file gives full
isolation; the bus creates its own schema on every call (``_ensure_schema``), so a
fresh path always initialises cleanly.

``_publish`` (the event-bus fan-out) is neutralised per test so writes don't reach the
academics GUI event bus, and ``notify_expiring``'s cross-domain fan-out
(email_bus / risk_bus / trip_bus) is stubbed at the seams.
"""

from datetime import datetime, timedelta

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.services.bus import cert_bus


def _date(offset_days: int) -> str:
    return (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


@pytest.fixture()
def cert_db(tmp_path, monkeypatch):
    """Point the shared DB layer at a temp file and silence event publishing.

    cert_bus creates ``staff_certifications`` itself, so no seeding is required.
    Returns the db path in case a test wants to inspect rows directly.
    """
    db_path = str(tmp_path / "cert.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    # Don't fan out to the real academics-GUI event bus during unit tests.
    monkeypatch.setattr(cert_bus, "_publish", lambda *a, **k: None)
    return db_path


# ---------------------------------------------------------------------------
# add_certification
# ---------------------------------------------------------------------------

class TestAddCertification:
    def test_returns_cert_id_and_persists(self, cert_db):
        cert_id = cert_bus.add_certification(
            "S001", "First Aid", expires_on=_date(10), issuer="Red Cross"
        )
        assert isinstance(cert_id, int)

        rows = cert_bus.list_certifications_for("S001")
        assert len(rows) == 1
        assert rows[0]["kind"] == "First Aid"
        assert rows[0]["issuer"] == "Red Cross"

    def test_coerces_int_staff_id_to_str(self, cert_db):
        cert_id = cert_bus.add_certification(1234, "Fire Warden", expires_on=_date(5))
        assert cert_id is not None
        # Stored/queried as string.
        assert cert_bus.list_certifications_for("1234")
        assert cert_bus.list_certifications_for(1234)  # int arg also coerced

    @pytest.mark.parametrize(
        "staff_id, kind",
        [("", "First Aid"), ("S001", ""), (None, "First Aid"), ("S001", None)],
    )
    def test_missing_required_fields_returns_none(self, cert_db, staff_id, kind):
        assert cert_bus.add_certification(staff_id, kind) is None


# ---------------------------------------------------------------------------
# list_certifications_for
# ---------------------------------------------------------------------------

class TestListCertificationsFor:
    def test_empty_for_unknown_staff(self, cert_db):
        assert cert_bus.list_certifications_for("nobody") == []

    def test_empty_for_falsy_staff_id(self, cert_db):
        assert cert_bus.list_certifications_for("") == []
        assert cert_bus.list_certifications_for(None) == []

    def test_excludes_soft_deleted(self, cert_db):
        cid = cert_bus.add_certification("S001", "Manual Handling", expires_on=_date(20))
        assert len(cert_bus.list_certifications_for("S001")) == 1
        cert_bus.delete_certification(cid)
        assert cert_bus.list_certifications_for("S001") == []


# ---------------------------------------------------------------------------
# delete_certification
# ---------------------------------------------------------------------------

class TestDeleteCertification:
    def test_soft_deletes_and_returns_true(self, cert_db):
        cid = cert_bus.add_certification("S001", "DSE Assessor", expires_on=_date(15))
        assert cert_bus.delete_certification(cid) is True
        # Row still present but flagged inactive.
        conn = sqlite3.connect(cert_db)
        active = conn.execute(
            "SELECT is_active FROM staff_certifications WHERE cert_id = ?", (cid,)
        ).fetchone()[0]
        conn.close()
        assert active == 0

    def test_unknown_cert_returns_false(self, cert_db):
        # Schema exists (created on first call) but no such row.
        cert_bus.add_certification("S001", "First Aid", expires_on=_date(5))
        assert cert_bus.delete_certification(999999) is False


# ---------------------------------------------------------------------------
# expiring_certifications
# ---------------------------------------------------------------------------

class TestExpiringCertifications:
    def test_includes_within_window_excludes_beyond(self, cert_db):
        cert_bus.add_certification("S001", "First Aid", expires_on=_date(10))
        cert_bus.add_certification("S002", "Fire Warden", expires_on=_date(90))

        soon = cert_bus.expiring_certifications(within_days=30)
        kinds = {c["kind"] for c in soon}
        assert "First Aid" in kinds
        assert "Fire Warden" not in kinds

    def test_already_expired_flag(self, cert_db):
        cert_bus.add_certification("S001", "First Aid", expires_on=_date(-3))
        cert_bus.add_certification("S002", "Fire Warden", expires_on=_date(10))

        by_kind = {c["kind"]: c for c in cert_bus.expiring_certifications(within_days=30)}
        assert by_kind["First Aid"]["already_expired"] is True
        assert by_kind["Fire Warden"]["already_expired"] is False

    def test_kind_filter_is_case_insensitive(self, cert_db):
        cert_bus.add_certification("S001", "First Aid", expires_on=_date(10))
        cert_bus.add_certification("S002", "Fire Warden", expires_on=_date(10))

        only = cert_bus.expiring_certifications(within_days=30, kind="first aid")
        assert [c["kind"] for c in only] == ["First Aid"]

    def test_excludes_soft_deleted(self, cert_db):
        cid = cert_bus.add_certification("S001", "First Aid", expires_on=_date(5))
        cert_bus.delete_certification(cid)
        assert cert_bus.expiring_certifications(within_days=30) == []

    def test_normalises_subject_id_and_source(self, cert_db):
        cert_bus.add_certification("S001", "First Aid", expires_on=_date(5))
        (row,) = cert_bus.expiring_certifications(within_days=30)
        assert row["subject_id"] == "S001"
        assert row["source"] == "staff_certifications"

    def test_ignores_null_expiry(self, cert_db):
        cert_bus.add_certification("S001", "First Aid")  # no expires_on
        assert cert_bus.expiring_certifications(within_days=365) == []


# ---------------------------------------------------------------------------
# notify_expiring  (cross-domain fan-out stubbed at the seams)
# ---------------------------------------------------------------------------

class TestNotifyExpiring:
    def test_reviews_and_emails_each_expiring(self, cert_db, monkeypatch):
        cert_bus.add_certification("S001", "Manual Handling", expires_on=_date(5))
        cert_bus.add_certification("S002", "Fire Warden", expires_on=_date(10))

        sent = []
        from education_system.systems.university.services.bus import email_bus
        monkeypatch.setattr(
            email_bus, "send_templated",
            lambda staff_id, template, ctx: sent.append((staff_id, template)) or True,
        )

        out = cert_bus.notify_expiring(within_days=30)
        assert out["reviewed"] == 2
        assert out["emailed"] == 2
        assert {s[0] for s in sent} == {"S001", "S002"}
        assert all(t == "cert_expiring" for _, t in sent)

    def test_email_failure_does_not_count(self, cert_db, monkeypatch):
        cert_bus.add_certification("S001", "Manual Handling", expires_on=_date(5))
        from education_system.systems.university.services.bus import email_bus
        monkeypatch.setattr(email_bus, "send_templated", lambda *a, **k: False)

        out = cert_bus.notify_expiring(within_days=30)
        assert out["reviewed"] == 1
        assert out["emailed"] == 0

    def test_nothing_expiring_is_noop(self, cert_db, monkeypatch):
        cert_bus.add_certification("S001", "Fire Warden", expires_on=_date(400))
        from education_system.systems.university.services.bus import email_bus
        monkeypatch.setattr(email_bus, "send_templated", lambda *a, **k: True)

        out = cert_bus.notify_expiring(within_days=30)
        assert out == {"emailed": 0, "trip_risks_raised": 0, "reviewed": 0}

    def test_first_aid_raises_trip_risk_when_upcoming_trip(self, cert_db, monkeypatch):
        cert_bus.add_certification("S001", "First Aid", expires_on=_date(7))

        from education_system.systems.university.services.bus import (
            email_bus, risk_bus, trip_bus,
        )
        monkeypatch.setattr(email_bus, "send_templated", lambda *a, **k: True)
        monkeypatch.setattr(risk_bus, "list_risks_for", lambda ref: [])
        raised = []
        monkeypatch.setattr(risk_bus, "raise_risk", lambda **kw: raised.append(kw) or 1)
        monkeypatch.setattr(
            trip_bus, "list_trips",
            lambda *a, **k: [{"created_by": "S001", "start_date": _date(14),
                              "trip_name": "Field Study"}],
        )

        out = cert_bus.notify_expiring(within_days=30)
        assert out["trip_risks_raised"] == 1
        assert len(raised) == 1
        assert raised[0]["category"] == "Safety"
        assert raised[0]["reference_id"] == "staff_cert:1"

    def test_first_aid_risk_is_idempotent(self, cert_db, monkeypatch):
        cert_bus.add_certification("S001", "First Aid", expires_on=_date(7))

        from education_system.systems.university.services.bus import (
            email_bus, risk_bus, trip_bus,
        )
        monkeypatch.setattr(email_bus, "send_templated", lambda *a, **k: True)
        # A risk already exists for this cert reference → must skip.
        monkeypatch.setattr(risk_bus, "list_risks_for", lambda ref: [{"id": 1}])
        raised = []
        monkeypatch.setattr(risk_bus, "raise_risk", lambda **kw: raised.append(kw))
        monkeypatch.setattr(
            trip_bus, "list_trips",
            lambda *a, **k: [{"created_by": "S001", "start_date": _date(14)}],
        )

        out = cert_bus.notify_expiring(within_days=30)
        assert out["trip_risks_raised"] == 0
        assert raised == []

    def test_first_aid_no_trip_no_risk(self, cert_db, monkeypatch):
        cert_bus.add_certification("S001", "First Aid", expires_on=_date(7))

        from education_system.systems.university.services.bus import (
            email_bus, risk_bus, trip_bus,
        )
        monkeypatch.setattr(email_bus, "send_templated", lambda *a, **k: True)
        monkeypatch.setattr(risk_bus, "list_risks_for", lambda ref: [])
        raised = []
        monkeypatch.setattr(risk_bus, "raise_risk", lambda **kw: raised.append(kw))
        monkeypatch.setattr(trip_bus, "list_trips", lambda *a, **k: [])  # no trips

        out = cert_bus.notify_expiring(within_days=30)
        assert out["trip_risks_raised"] == 0
        assert raised == []
