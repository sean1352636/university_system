"""SQLite adapter for atomic university domain-event publication."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from education_system.platform.kernel.core.correlation import get_correlation_id


class SQLiteTransactionalPublisher:
    """Append an event using the caller's open source-decision transaction."""

    def publish(
        self,
        connection: Any,
        event_name: str,
        payload: Mapping[str, Any],
        *,
        aggregate_id: str,
        idempotency_key: str,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        cursor = connection.execute(
            """INSERT INTO university_event_outbox
                 (event_id, event_name, event_version, aggregate_id,
                  correlation_id, causation_id, idempotency_key, payload_json,
                  available_at)
               VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(idempotency_key) DO NOTHING""",
            (
                event_id,
                event_name,
                aggregate_id,
                correlation_id or get_correlation_id() or str(uuid.uuid4()),
                causation_id,
                idempotency_key,
                json.dumps(dict(payload), default=str, sort_keys=True),
                datetime.now(UTC).isoformat(),
            ),
        )
        if cursor.rowcount == 0:
            row = connection.execute(
                "SELECT event_id FROM university_event_outbox WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row is None:
                raise RuntimeError("Outbox idempotency conflict could not be resolved")
            return str(row[0])
        return event_id


transactional_publisher = SQLiteTransactionalPublisher()

__all__ = ["SQLiteTransactionalPublisher", "transactional_publisher"]
