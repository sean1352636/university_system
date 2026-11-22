"""Privacy controls for the AI detector: consent records, the retention
policy and its runs, and the access log.

* **Consent** (``privacy_consent``) — for processing beyond the checks every
  student is told about in the integrity notice (for example keeping a
  student's own self-checks, or including their reviewed readings in a
  model shared with partner universities). One row per student and consent
  type; withdrawing sets ``granted = 0``.
* **Retention** — AI-writing readings follow the integrity retention period
  (``integrity_access`` setting ``retention_years``): the text of older
  readings is removed by ``integrity_ai.purge`` (run daily with the other
  integrity jobs). :meth:`PrivacyManager.apply_retention` runs it now and
  every run is recorded in ``data_retention``.
* **Access log** (``privacy_audit_log``) — who looked at which student's
  data and why.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Dict, List

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger

CONSENT_TYPES = ("self_check_history", "federated_training", "research_use")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _ensure(conn) -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        ai_detector_schema,
    )
    ai_detector_schema.apply_to_connection(conn)


def record_consent(conn, student_id, consent_type, granted, *, version="2026-2",
                   expires_at=None) -> None:
    if consent_type not in CONSENT_TYPES:
        raise ValueError(f"consent_type must be one of {', '.join(CONSENT_TYPES)}")
    _ensure(conn)
    conn.execute("INSERT INTO privacy_consent (student_id, consent_type, granted, granted_at, "
                 "expires_at, version) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(student_id, "
                 "consent_type) DO UPDATE SET granted = excluded.granted, granted_at = "
                 "excluded.granted_at, expires_at = excluded.expires_at, version = "
                 "excluded.version", (str(student_id), consent_type, 1 if granted else 0,
                                      _now(), expires_at, version))


def has_consent(conn, student_id, consent_type) -> bool:
    _ensure(conn)
    row = conn.execute("SELECT granted, expires_at FROM privacy_consent WHERE student_id = ? "
                       "AND consent_type = ?", (str(student_id), consent_type)).fetchone()
    if not row or not row[0]:
        return False
    if row[1]:
        try:
            if datetime.now() > datetime.fromisoformat(str(row[1])):
                return False
        except ValueError:
            return False
    return True


def consents(conn, student_id) -> list[dict]:
    _ensure(conn)
    return [{"consent_type": r[0], "granted": bool(r[1]), "granted_at": r[2],
             "expires_at": r[3], "version": r[4]} for r in conn.execute(
        "SELECT consent_type, granted, granted_at, expires_at, version FROM privacy_consent "
        "WHERE student_id = ? ORDER BY consent_type", (str(student_id),))]


def retention_policy(conn) -> dict:
    from education_system.systems.university.application.integrity import access
    years = int(access.number(conn, "retention_years"))
    return {"ai_readings_years": years, "similarity_text_years": years,
            "self_checks": "the text is never kept; only a hashed use counter for the daily "
                           "limit",
            "access_log_years": years}


def apply_retention(conn, by, as_of=None) -> dict:
    """Remove the text of AI-writing readings past the retention period now
    and record the run (no commit)."""
    _ensure(conn)
    from education_system.systems.university.application.integrity import ai as integrity_ai
    years = retention_policy(conn)["ai_readings_years"]
    day = as_of or datetime.now()
    cutoff = day.replace(year=day.year - years).strftime("%Y-%m-%d %H:%M:%S")
    removed = integrity_ai.purge(conn, cutoff)
    conn.execute("DELETE FROM privacy_audit_log WHERE timestamp < ?", (cutoff,))
    conn.execute("INSERT INTO data_retention (data_type, retention_period, deletion_date, "
                 "status, cutoff, removed, run_by, run_at) VALUES ('ai_readings', ?, ?, "
                 "'applied', ?, ?, ?, ?)", (years * 365, _now()[:10], cutoff, removed, by,
                                           _now()))
    return {"cutoff": cutoff, "readings_purged": removed, "years": years}


def retention_runs(conn, limit=20) -> list[dict]:
    _ensure(conn)
    return [{"id": r[0], "data_type": r[1], "cutoff": r[2], "removed": r[3], "run_by": r[4],
             "run_at": r[5]} for r in conn.execute(
        "SELECT id, data_type, cutoff, removed, run_by, run_at FROM data_retention ORDER BY "
        "id DESC LIMIT ?", (int(limit),))]


def log_access(conn, action, student_id, user_id, data_accessed, ip_address=None) -> None:
    _ensure(conn)
    conn.execute("INSERT INTO privacy_audit_log (action, student_id, user_id, data_accessed, "
                 "timestamp, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
                 (action, student_id, user_id, data_accessed, _now(), ip_address))


class PrivacyManager:
    """The detector's handle on privacy (its own short connections)."""

    def __init__(self, detector_instance):
        self.detector = detector_instance

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

    def _user(self) -> dict:
        return getattr(self.detector, "current_user", None) or {}

    def initialize_privacy_tables(self):
        try:
            self._run(_ensure, write=True)
        except Exception as e:
            logger.error(f"Error initializing privacy tables: {e}")

    def check_consent(self, student_id: str, consent_type: str) -> bool:
        try:
            return self._run(has_consent, student_id, consent_type)
        except Exception as e:
            logger.error(f"Error checking consent: {e}")
            return False

    def record_consent(self, student_id: str, consent_type: str, granted: bool,
                       expires_at: str = None) -> None:
        self._run(record_consent, student_id, consent_type, granted, expires_at=expires_at,
                  write=True)
        self.record_data_access("consent " + ("granted" if granted else "withdrawn"),
                                student_id, consent_type)

    def get_consents(self, student_id: str) -> list:
        return self._run(consents, student_id)

    def record_data_access(self, action: str, student_id: str = None, data_accessed: str = None):
        try:
            self._run(log_access, action, student_id, self._user().get("id"), data_accessed,
                      write=True)
        except Exception as e:
            logger.error(f"Error recording data access: {e}")

    def get_retention_policy(self) -> Dict:
        return self._run(retention_policy)

    def apply_retention(self) -> Dict:
        return self._run(apply_retention, self._user().get("username") or "system", write=True)

    def get_retention_runs(self, limit: int = 20) -> list:
        return self._run(retention_runs, limit)

    def anonymize_data(self, data: Dict, fields_to_anonymize: List[str]) -> Dict:
        """A copy of ``data`` with the named fields hashed or masked."""
        anonymized = data.copy()
        for field in fields_to_anonymize:
            if field not in anonymized:
                continue
            if field == 'student_id':
                anonymized[field] = hashlib.sha256(str(data[field]).encode()).hexdigest()[:8]
            elif field in ['ip_address', 'device_fingerprint']:
                value = str(data[field])
                if len(value) > 4:
                    anonymized[field] = value[:4] + '*' * (len(value) - 4)
            else:
                anonymized[field] = '[ANONYMIZED]'
        return anonymized
