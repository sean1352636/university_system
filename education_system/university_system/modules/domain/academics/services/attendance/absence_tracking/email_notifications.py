"""
Email notifications for absence requests.

Templates live as JSON files under ``university_system/templates/email/attendance/``
so a non-coder can edit subject + body without touching Python.

Public entry points (best-effort — never raise into the caller):

    notify_request_submitted(db, request_id) -> bool
    notify_request_decided(db, request_id, decision,
                           decision_reason="", decided_by="") -> bool

Internally:

    AbsenceEmailService                        — high-level send orchestrator
    EmailTemplateLoader                        — finds + parses + renders JSON

All output routes through ``infrastructure.logging.log_config.configure_logging``
so traceback / info lines join ``university_system/logs/app.log``.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Central logger.
try:
    from education_system.university_system.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="absence_tracker.emails")
except Exception:  # pragma: no cover
    logger = logging.getLogger("absence_tracker.emails")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)


# ===========================================================================
# Template loader
# ===========================================================================

# Resolve the templates directory relative to the project layout. Fall back
# to a sensible default if the import-time path arithmetic ever drifts.
def _default_template_dir() -> Path:
    here = Path(__file__).resolve()
    # absence_tracking/ -> .../university_system/modules/domain/...
    # Walk up to .../university_system/ then into templates/email/attendance/.
    for parent in here.parents:
        if parent.name == "university_system":
            return parent / "templates" / "email" / "attendance"
    return here.parent / "templates"


TEMPLATE_DIR = _default_template_dir()

TEMPLATE_FILES = {
    "submitted": "absence_request_submitted.json",
    "approved":  "absence_request_approved.json",
    "rejected":  "absence_request_rejected.json",
}


@dataclass(frozen=True)
class EmailTemplate:
    name: str
    subject: str
    body: str
    sender_name: str = "Absence Tracker"

    def render(self, ctx: dict) -> tuple[str, str]:
        """Substitute ``{placeholders}`` in subject + body. Missing keys
        render as their literal name in braces so output stays readable."""
        try:
            subject = self.subject.format_map(_SafeDict(ctx))
            body = self.body.format_map(_SafeDict(ctx))
            return subject, body
        except (IndexError, ValueError):
            logger.exception("template render failed name=%s", self.name)
            return self.subject, self.body


class _SafeDict(dict):
    """Dict that returns ``{key}`` for missing keys instead of KeyError —
    keeps the email readable even when the caller forgot a field."""
    def __missing__(self, key):
        return "{" + key + "}"


class EmailTemplateLoader:
    """Reads JSON templates from disk and caches them per process."""

    def __init__(self, directory: Optional[Path] = None) -> None:
        self.directory = directory or TEMPLATE_DIR
        self._cache: dict[str, EmailTemplate] = {}

    def load(self, key: str) -> Optional[EmailTemplate]:
        if key in self._cache:
            return self._cache[key]
        filename = TEMPLATE_FILES.get(key)
        if not filename:
            logger.error("unknown template key: %s", key)
            return None
        path = self.directory / filename
        if not path.is_file():
            logger.error("template file not found: %s", path)
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("template parse failed: %s", path)
            return None
        try:
            tpl = EmailTemplate(
                name=key,
                subject=data["subject"],
                body=data["body"],
                sender_name=data.get("sender_name", "Absence Tracker"),
            )
        except KeyError:
            logger.exception("template missing required keys: %s", path)
            return None
        self._cache[key] = tpl
        return tpl


# A single shared loader instance — templates are immutable on disk during
# a session, so cache hit-rate is always 1 after warm-up.
_loader = EmailTemplateLoader()


def reload_templates() -> None:
    """Drop the in-process cache so subsequent sends pick up edits."""
    _loader._cache.clear()
    logger.info("email template cache cleared")


# ===========================================================================
# AbsenceEmailService
# ===========================================================================

class AbsenceEmailService:
    """Sends absence-request emails using JSON templates.

    Wraps ``infrastructure.email.queue_email``; degrades gracefully if the
    email infrastructure isn't importable so a missing dependency can't
    break the absence-request flow.
    """

    def __init__(self, db,
                 loader: Optional[EmailTemplateLoader] = None) -> None:
        self.db = db
        self.loader = loader or _loader

    # ------- recipient + request lookup ------------------------------
    def _lookup_request(self, request_id: int) -> Optional[dict]:
        try:
            row = self.db.cur.execute(
                """SELECT r.id, r.student_id, r.module_code, r.date,
                          COALESCE(r.reason,'') AS reason,
                          COALESCE(r.status,'') AS status,
                          COALESCE(r.submitted_at,'') AS submitted_at,
                          COALESCE(m.module_name, r.module_code) AS module_name,
                          TRIM(COALESCE(s.first_name,'')||' '
                               ||COALESCE(s.last_name,'')) AS student_name,
                          COALESCE(s.email_address,'') AS email
                   FROM absence_requests r
                   LEFT JOIN modules m  ON m.module_code = r.module_code
                   LEFT JOIN students s ON s.student_id = r.student_id
                   WHERE r.id = ?""", (request_id,)).fetchone()
        except sqlite3.Error:
            logger.exception("request lookup failed rid=%s", request_id)
            return None
        if not row:
            logger.warning("request %s not found", request_id)
            return None
        keys = ("id", "student_id", "module_code", "date", "reason",
                "status", "submitted_at", "module_name",
                "student_name", "email")
        return dict(zip(keys, row))

    @staticmethod
    def _display_name(req: dict) -> str:
        name = (req.get("student_name") or "").strip()
        return name or req.get("student_id") or "Student"

    # ------- delivery ------------------------------------------------
    @staticmethod
    def _ensure_auth_initialised() -> None:
        """Initialise the shared auth singleton if it hasn't been already.

        The email infrastructure calls ``shared_context.get_auth()`` to
        attribute the sender. When the absence tracker is launched
        standalone (no main-system bootstrap), that call raises
        ``AuthenticationNotInitializedError`` and the resulting SECURITY
        log line shows up before every send. Initialising eagerly here
        means the email path works regardless of how we got here."""
        try:
            from education_system.university_system.infrastructure.shared_context import (  # noqa: E501
                is_auth_initialized, initialize_auth,
            )
        except Exception:
            logger.debug("shared_context unavailable", exc_info=True)
            return
        try:
            if is_auth_initialized():
                return
            initialize_auth()
            logger.info("auth singleton initialised by email_notifications")
        except Exception:
            logger.exception("auth init failed (continuing best-effort)")

    @classmethod
    def _queue_email(cls, recipient: str, subject: str, body: str) -> bool:
        """Best-effort dispatch via the shared email infrastructure.

        Returns True only when ``queue_email`` reports success — many
        configurations route to the synchronous ``send_email`` path which
        returns a truthy/falsy status; we honour that so the caller knows
        whether delivery actually happened."""
        cls._ensure_auth_initialised()
        try:
            from education_system.university_system.infrastructure.email import (
                queue_email,
            )
        except Exception:
            logger.exception("email infrastructure unavailable")
            return False
        try:
            result = queue_email(recipient, subject, body)
        except Exception:
            logger.exception("queue_email raised recipient=%s", recipient)
            return False
        # `queue_email` may return None (queued asynchronously), a truthy
        # task object, or False on failure — treat None as "queued ok".
        ok = result is None or bool(result)
        if not ok:
            logger.warning(
                "queue_email reported failure recipient=%s subject=%r "
                "result=%r",
                recipient, subject, result)
        else:
            logger.debug(
                "queue_email accepted recipient=%s subject=%r",
                recipient, subject)
        return ok

    def _send(self, template_key: str, request_id: int,
              extra: Optional[dict] = None) -> bool:
        req = self._lookup_request(request_id)
        if not req:
            return False
        recipient = req.get("email") or ""
        if not recipient:
            logger.warning(
                "no email address for student %s on request %s — skipping",
                req.get("student_id"), request_id)
            return False
        tpl = self.loader.load(template_key)
        if not tpl:
            return False
        ctx = {
            "request_id":   req["id"],
            "student_id":   req["student_id"],
            "student_name": self._display_name(req),
            "module_code":  req["module_code"] or "",
            "module_name":  req["module_name"] or req["module_code"] or "",
            "date":         req["date"] or "",
            "reason":       req["reason"] or "(no reason given)",
            "submitted_at": req["submitted_at"] or "",
            "decided_by":   "",
            "decision_reason": "",
        }
        if extra:
            ctx.update(extra)
        subject, body = tpl.render(ctx)
        ok = self._queue_email(recipient, subject, body)
        if ok:
            logger.info(
                "sent %s email rid=%s to=%s", template_key, request_id,
                recipient)
        return ok

    # ------- public entry points ------------------------------------
    def notify_submitted(self, request_id: int) -> bool:
        return self._send("submitted", request_id)

    def notify_decision(self, request_id: int, decision: str,
                        decision_reason: str = "",
                        decided_by: str = "") -> bool:
        key = "approved" if decision == "approved" else "rejected"
        return self._send(key, request_id, extra={
            "decided_by": decided_by or "(automated)",
            "decision_reason": decision_reason or "(no comment provided)",
        })


# ===========================================================================
# Module-level convenience wrappers
# ===========================================================================

def notify_request_submitted(db, request_id: int) -> bool:
    """Best-effort: send a 'request received' acknowledgement to the student."""
    try:
        return AbsenceEmailService(db).notify_submitted(request_id)
    except Exception:
        logger.exception("notify_request_submitted swallowed rid=%s",
                         request_id)
        return False


def notify_request_decided(db, request_id: int, decision: str,
                           decision_reason: str = "",
                           decided_by: str = "") -> bool:
    """Best-effort: send the approve/reject email after a decision is made."""
    try:
        return AbsenceEmailService(db).notify_decision(
            request_id, decision, decision_reason, decided_by)
    except Exception:
        logger.exception("notify_request_decided swallowed rid=%s",
                         request_id)
        return False


__all__ = [
    "EmailTemplate", "EmailTemplateLoader",
    "AbsenceEmailService",
    "notify_request_submitted", "notify_request_decided",
    "reload_templates", "TEMPLATE_DIR", "TEMPLATE_FILES",
]
