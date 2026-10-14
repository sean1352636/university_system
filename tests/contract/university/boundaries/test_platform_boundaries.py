from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from education_system.platform.kernel.adapters import ClassifiedStorage
from education_system.platform.kernel.deprecations import legacy_usage, record_legacy_call
from education_system.systems.university.domains.governance.application.data_lifecycle import (
    LegalHoldActive,
    LifecycleService,
    UNIVERSITY_POLICIES,
)
from education_system.systems.university.infrastructure.events import (
    SQLiteTransactionalPublisher,
)


OUTBOX_DDL = """
CREATE TABLE university_event_outbox (
 event_id TEXT PRIMARY KEY, event_name TEXT, event_version INTEGER,
 aggregate_id TEXT, correlation_id TEXT, causation_id TEXT,
 idempotency_key TEXT UNIQUE, payload_json TEXT, available_at TEXT,
 attempts INTEGER DEFAULT 0, delivered_at TEXT, dead_lettered_at TEXT,
 last_error TEXT
)"""


def test_sensitive_storage_is_physically_separate(tmp_path: Path) -> None:
    storage = ClassifiedStorage(tmp_path)
    general = storage.database_path("general")
    health = storage.database_path("health")
    safeguarding = storage.database_path("safeguarding")
    assert len({general, health, safeguarding}) == 3
    assert health.parent.name == "health"
    assert safeguarding.parent.name == "safeguarding"


def test_outbox_row_rolls_back_with_source_decision() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE decisions(id TEXT PRIMARY KEY)")
    connection.execute(OUTBOX_DDL)
    publisher = SQLiteTransactionalPublisher()

    connection.execute("BEGIN")
    connection.execute("INSERT INTO decisions VALUES ('A1')")
    publisher.publish(
        connection,
        "admissions.decision.recorded",
        {"decision": "offer"},
        aggregate_id="A1",
        idempotency_key="admissions:A1:offer",
    )
    connection.rollback()

    assert connection.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM university_event_outbox").fetchone()[0] == 0


class LifecycleRepository:
    def __init__(self, held: bool = False) -> None:
        self.held = held
        self.calls: list[tuple] = []

    def has_active_hold(self, record_type, record_id):
        return self.held

    def redact(self, *args, **kwargs):
        self.calls.append(("redact", args, kwargs))

    def delete(self, *args, **kwargs):
        self.calls.append(("delete", args, kwargs))

    def archive(self, *args, **kwargs):
        self.calls.append(("archive", args, kwargs))

    def record_disposition(self, *args, **kwargs):
        self.calls.append(("record", args, kwargs))


def test_every_sensitive_record_type_has_an_explicit_policy() -> None:
    assert {"student_record", "finance", "health", "safeguarding"} <= UNIVERSITY_POLICIES.keys()
    assert all(policy.legal_basis for policy in UNIVERSITY_POLICIES.values())


def test_legal_hold_blocks_redaction_and_deletion() -> None:
    repository = LifecycleRepository(held=True)
    with pytest.raises(LegalHoldActive):
        LifecycleService(repository).dispose("health", "H1", actor_id="dpo")
    assert repository.calls == []


def test_deprecated_implementation_usage_is_measurable() -> None:
    with pytest.warns(DeprecationWarning):
        record_legacy_call("email", "university.local_email")
    assert legacy_usage()["email:university.local_email"] >= 1
