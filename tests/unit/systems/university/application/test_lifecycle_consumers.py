from __future__ import annotations

import json

from education_system.systems.university.application.lifecycle_consumers import (
    consume_action,
)
from education_system.systems.university.infrastructure.database import db as db_module


def test_every_downstream_consumer_is_replay_safe(tmp_path, monkeypatch) -> None:
    path = str(tmp_path / "consumers.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", path)
    with db_module.transaction() as conn:
        conn.executescript("""
            CREATE TABLE student_lifecycle_actions (
                action_id INTEGER PRIMARY KEY, history_id INTEGER,
                student_id TEXT, target_system TEXT, action TEXT,
                payload_json TEXT, status TEXT DEFAULT 'pending',
                attempts INTEGER DEFAULT 0, last_error TEXT, completed_at TEXT
            );
            CREATE TABLE student_lifecycle_consumer_receipts (
                action_id INTEGER, target_system TEXT, handler_version INTEGER,
                outcome TEXT, processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(action_id, target_system, handler_version)
            );
        """)
        targets = (
            "finance", "module_enrolments", "visa_monitoring",
            "accommodation", "library", "student_account",
        )
        for action_id, target in enumerate(targets, 1):
            conn.execute(
                """INSERT INTO student_lifecycle_actions
                     (action_id, student_id, target_system, action, payload_json)
                   VALUES (?, 'S1', ?, 'initial_registration', ?)""",
                (action_id, target, json.dumps({"target": target})),
            )

    effects: list[str] = []
    for action_id, target in enumerate(targets, 1):
        handler = lambda payload: effects.append(payload["target"])
        assert consume_action(action_id, target, handler) is True
        assert consume_action(action_id, target, handler) is False

    assert effects == list(targets)
