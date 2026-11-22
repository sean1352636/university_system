"""SHA-256 signatures over uploaded evidence — #35."""

from __future__ import annotations

import hashlib
import sqlite3
from typing import Optional

from .log import logger


# ===========================================================================
# EvidenceService — #35 SHA-256 signatures
# ===========================================================================

class EvidenceService:
    """SHA-256 digital signatures of evidence files attached to requests."""

    CHUNK = 65536

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    @classmethod
    def _hash_file(cls, file_path: str) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(cls.CHUNK), b""):
                h.update(chunk)
        return h.hexdigest()

    def sign(self, request_id: int, file_path: str,
             signed_by: str) -> Optional[str]:
        try:
            digest = self._hash_file(file_path)
        except OSError:
            logger.exception("sign read failed path=%s", file_path)
            raise
        try:
            self.conn.execute(
                """INSERT INTO absence_evidence_signatures
                     (request_id, file_path, sha256, signed_by)
                   VALUES(?,?,?,?)""",
                (request_id, file_path, digest, signed_by))
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("sign insert failed rid=%s", request_id)
            raise
        logger.info("evidence signed rid=%s by=%s sha=%s",
                    request_id, signed_by, digest[:12])
        return digest

    def verify(self, request_id: int, file_path: str) -> bool:
        try:
            row = self.conn.execute(
                """SELECT sha256 FROM absence_evidence_signatures
                   WHERE request_id=? AND file_path=?
                   ORDER BY id DESC LIMIT 1""",
                (request_id, file_path)).fetchone()
        except sqlite3.Error:
            logger.exception("verify lookup failed rid=%s", request_id)
            return False
        if not row:
            return False
        try:
            return self._hash_file(file_path) == row[0]
        except OSError:
            logger.exception("verify read failed path=%s", file_path)
            return False


def sign_evidence(conn, request_id: int, file_path: str,
                  signed_by: str) -> str:
    return EvidenceService(conn).sign(request_id, file_path, signed_by) or ""


def verify_evidence(conn, request_id: int, file_path: str) -> bool:
    return EvidenceService(conn).verify(request_id, file_path)


__all__ = [
    "EvidenceService",
    "sign_evidence",
    "verify_evidence",
]
