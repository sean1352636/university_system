"""The detector's tamper-evident audit trail: a hash chain kept in the
database (``ai_audit_chain``).

Each block records one event — a reading taken, a review, a model trained,
imported, activated or rolled back, a federated update — with who did it and
when, and its hash::

    hash = sha256(prev_hash + canonical JSON of the payload + at + actor)

so changing, removing or reordering any block breaks every hash after it,
which :func:`verify` finds. Blocks are written in the caller's transaction
the moment the event happens (there is no pending pool and no mining); the
first block's ``prev_hash`` is 64 zeros. This proves the record has not been
edited since; it is not a distributed ledger, and anyone who can rewrite the
whole table can rebuild it, so export :func:`head` regularly (the GUI's
chain-of-custody export does) to anchor it outside the database.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Dict

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger

GENESIS = "0" * 64


def _ensure(conn) -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        ai_detector_schema,
    )
    ai_detector_schema.apply_to_connection(conn)


def canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def block_hash(prev_hash, payload_json, at, actor) -> str:
    return hashlib.sha256(f"{prev_hash}{payload_json}{at}{actor}".encode("utf-8")).hexdigest()


def record(conn, event, payload, actor) -> str:
    """Append one block (no commit). Returns its hash."""
    _ensure(conn)
    last = conn.execute("SELECT idx, hash FROM ai_audit_chain ORDER BY idx DESC LIMIT 1"
                        ).fetchone()
    idx, prev = (int(last[0]) + 1, last[1]) if last else (0, GENESIS)
    body = canonical({"event": event, **(payload or {})})
    at = datetime.now().isoformat(timespec="microseconds")
    actor = str(actor or "system")
    digest = block_hash(prev, body, at, actor)
    conn.execute("INSERT INTO ai_audit_chain (idx, event, payload_json, actor, at, prev_hash, "
                 "hash) VALUES (?, ?, ?, ?, ?, ?, ?)", (idx, event, body, actor, at, prev, digest))
    return digest


def verify(conn) -> dict:
    """Walk the chain. ``first_bad`` is the first block whose link or hash is
    wrong (``None`` when the chain is intact)."""
    _ensure(conn)
    prev, expected_idx, count = GENESIS, 0, 0
    for idx, body, actor, at, prev_hash, digest in conn.execute(
            "SELECT idx, payload_json, actor, at, prev_hash, hash FROM ai_audit_chain "
            "ORDER BY idx"):
        count += 1
        problem = None
        if idx != expected_idx:
            problem = f"block {expected_idx} is missing"
        elif prev_hash != prev:
            problem = "its link to the previous block is wrong"
        elif block_hash(prev_hash, body, at, actor) != digest:
            problem = "its contents do not match its hash"
        if problem:
            return {"ok": False, "blocks": count, "first_bad": idx, "problem": problem}
        prev, expected_idx = digest, idx + 1
    return {"ok": True, "blocks": count, "first_bad": None, "head": prev if count else None}


def head(conn) -> dict:
    _ensure(conn)
    row = conn.execute("SELECT idx, hash, at FROM ai_audit_chain ORDER BY idx DESC LIMIT 1"
                       ).fetchone()
    return {"idx": row[0], "hash": row[1], "at": row[2]} if row else {"idx": None,
                                                                       "hash": GENESIS}


def blocks(conn, limit=100, event=None) -> list[dict]:
    """The newest blocks first."""
    _ensure(conn)
    sql = "SELECT idx, event, payload_json, actor, at, prev_hash, hash FROM ai_audit_chain"
    params: list = []
    if event:
        sql += " WHERE event = ?"
        params.append(event)
    rows = conn.execute(sql + " ORDER BY idx DESC LIMIT ?", params + [int(limit)]).fetchall()
    return [{"index": r[0], "event": r[1], "payload": json.loads(r[2]), "actor": r[3],
             "timestamp": r[4], "previous_hash": r[5], "hash": r[6]} for r in rows]


def find(conn, **match) -> list[dict]:
    """Blocks whose payload has every ``key=value`` in ``match``."""
    _ensure(conn)
    found = []
    for r in conn.execute("SELECT idx, event, payload_json, actor, at, prev_hash, hash FROM "
                          "ai_audit_chain ORDER BY idx"):
        payload = json.loads(r[2])
        if all(str(payload.get(k)) == str(v) for k, v in match.items()):
            found.append({"index": r[0], "event": r[1], "payload": payload, "actor": r[3],
                          "timestamp": r[4], "previous_hash": r[5], "hash": r[6]})
    return found


class BlockchainAuditTrail:
    """The detector's handle on the audit chain (its own short connections).

    ``blockchain`` lists the stored blocks; ``pending_transactions`` is
    always empty, because blocks are written immediately."""

    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.pending_transactions: list = []

    def _actor(self) -> str:
        user = getattr(self.detector, "current_user", None) or {}
        return str(user.get("username") or user.get("id") or "system")

    def _run(self, fn, *args, write=False, **kwargs):
        conn = self.detector._safe_db_connect()
        try:
            result = fn(conn, *args, **kwargs)
            if write:
                conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_detection_record(self, submission_id: int, detection_result: Dict) -> str:
        """Record a reading. Returns the hash of the reading's content (the
        value to quote when checking it later)."""
        detection_hash = hashlib.sha256(canonical(detection_result).encode()).hexdigest()
        try:
            self._run(record, "reading", {"submission_id": submission_id,
                                          "detection_hash": detection_hash}, self._actor(),
                      write=True)
        except Exception as exc:
            logger.error(f"Audit chain record failed: {exc}")
        return detection_hash

    def record_event(self, event: str, payload: Dict) -> str:
        return self._run(record, event, payload, self._actor(), write=True)

    def verify_detection_integrity(self, submission_id: int, claimed_hash: str) -> bool:
        """Is there a block for this reading with this content hash, in an
        intact chain?"""
        found = self._run(find, submission_id=submission_id, detection_hash=claimed_hash)
        return bool(found) and self._run(verify)["ok"]

    def verify_chain(self) -> Dict:
        return self._run(verify)

    def head(self) -> Dict:
        return self._run(head)

    def get_blocks(self, limit: int = 100, event: str = None) -> list:
        return self._run(blocks, limit, event)

    @property
    def blockchain(self) -> list:
        """Oldest first, in the shape the GUI shows."""
        try:
            rows = list(reversed(self._run(blocks, 1000)))
        except Exception as exc:
            logger.error(f"Audit chain read failed: {exc}")
            return []
        return [{**r, "transactions": [r["payload"]]} for r in rows]
