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
    "frequent_absence": "frequent_absence_alert.json",
}

FREQUENT_ABSENCE_THRESHOLD = 5
# Quiet window after the most recent send to the same student. Even if the
# bucket logic would normally re-alert, no second email goes out inside this
# window — protects against runaway sends in heavy-absence cases.
FREQUENT_ABSENCE_COOLDOWN_DAYS = 7
# Higher bar to auto-create a wellbeing referral (vs. just emailing the
# student). Rationale: 5 absences/month is a "you should hear from us";
# crossing this threshold says "wellbeing staff should know about this".
WELLBEING_REFERRAL_THRESHOLD = 10


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

    # ------- frequent-absence alerts --------------------------------
    @staticmethod
    def _ensure_alert_table(db) -> None:
        try:
            db.cur.execute(
                """CREATE TABLE IF NOT EXISTS frequent_absence_alerts (
                       student_id    TEXT NOT NULL,
                       year_month    TEXT NOT NULL,
                       sent_at       TEXT NOT NULL,
                       count_at_send INTEGER NOT NULL,
                       PRIMARY KEY (student_id, year_month)
                   )"""
            )
            db.conn.commit()
        except sqlite3.Error:
            logger.exception("could not ensure frequent_absence_alerts table")

    @staticmethod
    def _ensure_prefs_table(db) -> None:
        try:
            db.cur.execute(
                """CREATE TABLE IF NOT EXISTS frequent_absence_email_prefs (
                       student_id  TEXT PRIMARY KEY,
                       opted_out   INTEGER NOT NULL DEFAULT 0,
                       updated_at  TEXT
                   )"""
            )
            db.conn.commit()
        except sqlite3.Error:
            logger.exception("could not ensure frequent_absence_email_prefs table")

    def is_opted_out(self, student_id) -> bool:
        self._ensure_prefs_table(self.db)
        try:
            row = self.db.cur.execute(
                "SELECT opted_out FROM frequent_absence_email_prefs "
                "WHERE student_id = ?",
                (student_id,),
            ).fetchone()
        except sqlite3.Error:
            logger.exception("opt-out lookup failed sid=%s", student_id)
            return False
        return bool(row and row[0])

    def set_opt_out(self, student_id, opted_out: bool = True) -> None:
        self._ensure_prefs_table(self.db)
        from datetime import datetime as _dt
        try:
            self.db.cur.execute(
                """INSERT INTO frequent_absence_email_prefs
                       (student_id, opted_out, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(student_id) DO UPDATE SET
                       opted_out  = excluded.opted_out,
                       updated_at = excluded.updated_at""",
                (student_id, 1 if opted_out else 0, _dt.utcnow().isoformat()),
            )
            self.db.conn.commit()
        except sqlite3.Error:
            logger.exception("opt-out write failed sid=%s", student_id)

    def _last_send_at(self, student_id) -> Optional["datetime.datetime"]:
        from datetime import datetime as _dt
        try:
            row = self.db.cur.execute(
                "SELECT MAX(sent_at) FROM frequent_absence_alerts "
                "WHERE student_id = ?",
                (student_id,),
            ).fetchone()
        except sqlite3.Error:
            logger.exception("last-send lookup failed sid=%s", student_id)
            return None
        last = (row or [None])[0]
        if not last:
            return None
        try:
            return _dt.fromisoformat(last)
        except ValueError:
            return None

    def _lookup_student(self, student_id) -> Optional[dict]:
        try:
            row = self.db.cur.execute(
                """SELECT student_id,
                          TRIM(COALESCE(first_name,'')||' '||COALESCE(last_name,'')) AS name,
                          COALESCE(email_address,'') AS email
                   FROM students
                   WHERE student_id = ?""",
                (student_id,),
            ).fetchone()
        except sqlite3.Error:
            logger.exception("student lookup failed sid=%s", student_id)
            return None
        if not row:
            return None
        return {"student_id": row[0], "name": row[1], "email": row[2]}

    def _upcoming_exams_for_modules(self, modules: list[str], limit: int = 6) -> str:
        if not modules:
            return "  (none scheduled)"
        try:
            placeholders = ",".join("?" * len(modules))
            from datetime import date as _date
            rows = self.db.cur.execute(
                f"""SELECT date, start_time, end_time, module_code,
                          COALESCE(module_name, module_code), COALESCE(room,'')
                   FROM exams
                   WHERE module_code IN ({placeholders})
                     AND date >= ?
                   ORDER BY date, start_time
                   LIMIT ?""",
                (*modules, _date.today().isoformat(), limit),
            ).fetchall()
        except sqlite3.Error:
            logger.exception("upcoming exam lookup failed modules=%r", modules)
            return "  (none scheduled)"
        if not rows:
            return "  (none scheduled)"
        return "\n".join(
            f"  • {d} {st}-{et} — {code} ({name}){' in ' + room if room else ''}"
            for (d, st, et, code, name, room) in rows
        )

    def _absences_in_month(self, student_id, year_month: str) -> list[tuple]:
        try:
            return list(self.db.cur.execute(
                """SELECT a.date,
                          a.module_code,
                          COALESCE(m.module_name, a.module_code),
                          COALESCE(a.status,'')
                   FROM attendance a
                   LEFT JOIN modules m ON m.module_code = a.module_code
                   WHERE a.student_id = ?
                     AND substr(a.date, 1, 7) = ?
                     AND LOWER(COALESCE(a.status,'')) IN ('absent','late','excused')
                   ORDER BY a.date""",
                (student_id, year_month),
            ).fetchall())
        except sqlite3.Error:
            logger.exception("absence lookup failed sid=%s ym=%s",
                             student_id, year_month)
            return []

    def notify_frequent_absences(
        self, student_id, year_month: Optional[str] = None,
        threshold: int = FREQUENT_ABSENCE_THRESHOLD,
        force: bool = False,
    ) -> bool:
        """If *student_id* has >= threshold absences in *year_month*, email
        them — at most once per (student, month) unless ``force=True``."""
        from datetime import date as _date, datetime as _dt, timedelta as _td
        ym = year_month or _date.today().strftime("%Y-%m")
        self._ensure_alert_table(self.db)

        # Hard opt-out wins regardless of bucket — set via set_opt_out().
        if not force and self.is_opted_out(student_id):
            logger.debug("frequent-absence email skipped: sid=%s opted out",
                         student_id)
            return False

        rows = self._absences_in_month(student_id, ym)
        count = len(rows)
        if count < threshold:
            return False
        # Escalating cadence: alert each time the count crosses a new
        # multiple of *threshold* (5, 10, 15, ...). The bucket is
        # ``count // threshold``; we re-alert only when it has grown
        # since the last send.
        current_bucket = count // threshold
        last_bucket = 0
        if not force:
            try:
                row = self.db.cur.execute(
                    "SELECT MAX(count_at_send) FROM frequent_absence_alerts "
                    "WHERE student_id = ? AND year_month = ?",
                    (student_id, ym),
                ).fetchone()
                last_count = (row or [0])[0] or 0
                last_bucket = last_count // threshold
            except sqlite3.Error:
                logger.exception("alert dedup check failed")
            if current_bucket <= last_bucket:
                logger.debug(
                    "frequent-absence alert already sent for this bucket "
                    "sid=%s ym=%s count=%d last_bucket=%d",
                    student_id, ym, count, last_bucket)
                return False
            # Cooldown: even if the bucket has advanced, don't send another
            # email within FREQUENT_ABSENCE_COOLDOWN_DAYS of the most recent
            # send to this student (cross-month, regardless of bucket).
            last_sent = self._last_send_at(student_id)
            if last_sent is not None:
                age = _dt.utcnow() - last_sent
                if age < _td(days=FREQUENT_ABSENCE_COOLDOWN_DAYS):
                    logger.info(
                        "frequent-absence email suppressed by cooldown "
                        "sid=%s last_sent=%s age=%s",
                        student_id, last_sent.isoformat(), age)
                    return False

        student = self._lookup_student(student_id)
        if not student:
            logger.warning("student %s not found — no alert", student_id)
            return False
        recipient = (student.get("email") or "").strip()
        if not recipient:
            logger.warning("no email for student %s — skipping alert", student_id)
            return False

        tpl = self.loader.load("frequent_absence")
        if not tpl:
            return False

        from datetime import datetime as _dt
        try:
            month_name = _dt.strptime(ym, "%Y-%m").strftime("%B %Y")
        except ValueError:
            month_name = ym
        absence_list = "\n".join(
            f"  • {d} — {code} ({name}) — {status or 'absent'}"
            for (d, code, name, status) in rows
        ) or "  (none on file)"
        affected_modules = sorted({code for (_d, code, _n, _s) in rows})
        upcoming_exams = self._upcoming_exams_for_modules(affected_modules)
        ctx = {
            "student_id":     student["student_id"],
            "student_name":   (student.get("name") or "").strip()
                              or student["student_id"],
            "count":          len(rows),
            "threshold":      threshold,
            "year_month":     ym,
            "month_name":     month_name,
            "absence_list":   absence_list,
            "upcoming_exams": upcoming_exams,
        }
        subject, body = tpl.render(ctx)
        ok = self._queue_email(recipient, subject, body)
        if ok:
            try:
                from datetime import datetime as _dt2
                self.db.cur.execute(
                    """INSERT OR REPLACE INTO frequent_absence_alerts
                       (student_id, year_month, sent_at, count_at_send)
                       VALUES (?, ?, ?, ?)""",
                    (student_id, ym, _dt2.utcnow().isoformat(), len(rows)),
                )
                self.db.conn.commit()
            except sqlite3.Error:
                logger.exception("alert dedup record failed")
            logger.info("sent frequent-absence email sid=%s ym=%s count=%d",
                        student_id, ym, len(rows))
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


def maybe_create_wellbeing_referral(
    db, student_id, year_month: Optional[str] = None,
    threshold: int = WELLBEING_REFERRAL_THRESHOLD,
) -> Optional[int]:
    """When a student crosses *threshold* absences in a calendar month,
    open a wellbeing referral so support staff can reach out.

    Dedup'd: at most one **open** referral with concern_type='attendance'
    per student at a time. Returns the new referral id, an existing
    referral id (already on file), or None if the threshold isn't met.
    """
    from datetime import date as _date
    ym = year_month or _date.today().strftime("%Y-%m")
    try:
        # Count this month's non-present rows
        count_row = db.cur.execute(
            """SELECT COUNT(*) FROM attendance
               WHERE student_id = ?
                 AND substr(date, 1, 7) = ?
                 AND LOWER(COALESCE(status,'')) IN ('absent','late','excused')""",
            (student_id, ym),
        ).fetchone()
        count = (count_row or [0])[0] or 0
        if count < threshold:
            return None

        # Skip if there's already an open attendance referral for this student
        existing = db.cur.execute(
            """SELECT id FROM wellbeing_referrals
               WHERE student_id = ?
                 AND concern_type = 'attendance'
                 AND COALESCE(status, 'open') = 'open'
               ORDER BY id DESC LIMIT 1""",
            (student_id,),
        ).fetchone()
        if existing:
            logger.debug(
                "wellbeing referral already open sid=%s ref=%s — skipping",
                student_id, existing[0])
            return existing[0]

        urgency = "high" if count >= threshold * 2 else "normal"
        description = (
            f"Auto-referral: {count} absence/late/excused row(s) recorded "
            f"in {ym}, exceeding the {threshold}/month threshold. "
            "Recommend a wellbeing check-in."
        )
        db.cur.execute(
            """INSERT INTO wellbeing_referrals
                   (student_id, referred_by, concern_type, description,
                    urgency, status)
               VALUES (?, 'absence_tracker', 'attendance', ?, ?, 'open')""",
            (student_id, description, urgency),
        )
        db.conn.commit()
        new_id = db.cur.lastrowid
        logger.info(
            "wellbeing referral opened sid=%s ref=%s ym=%s count=%d urgency=%s",
            student_id, new_id, ym, count, urgency)
        return new_id
    except sqlite3.Error:
        logger.exception("maybe_create_wellbeing_referral failed sid=%s",
                         student_id)
        return None


def set_frequent_absence_opt_out(db, student_id, opted_out: bool = True) -> None:
    """Set or clear a student's opt-out for frequent-absence emails."""
    try:
        AbsenceEmailService(db).set_opt_out(student_id, opted_out)
    except Exception:
        logger.exception("set_frequent_absence_opt_out swallowed sid=%s",
                         student_id)


def is_frequent_absence_opted_out(db, student_id) -> bool:
    """Check whether a student has opted out of frequent-absence emails."""
    try:
        return AbsenceEmailService(db).is_opted_out(student_id)
    except Exception:
        logger.exception("is_frequent_absence_opted_out swallowed sid=%s",
                         student_id)
        return False


def notify_frequent_absences(db, student_id, year_month: Optional[str] = None,
                             threshold: int = FREQUENT_ABSENCE_THRESHOLD,
                             force: bool = False) -> bool:
    """Best-effort: email a student who has hit the absence threshold this
    calendar month. At most one email per (student, month)."""
    try:
        return AbsenceEmailService(db).notify_frequent_absences(
            student_id, year_month=year_month, threshold=threshold, force=force)
    except Exception:
        logger.exception("notify_frequent_absences swallowed sid=%s ym=%s",
                         student_id, year_month)
        return False


__all__ = [
    "EmailTemplate", "EmailTemplateLoader",
    "AbsenceEmailService",
    "notify_request_submitted", "notify_request_decided",
    "notify_frequent_absences",
    "set_frequent_absence_opt_out", "is_frequent_absence_opted_out",
    "maybe_create_wellbeing_referral",
    "FREQUENT_ABSENCE_THRESHOLD", "FREQUENT_ABSENCE_COOLDOWN_DAYS",
    "WELLBEING_REFERRAL_THRESHOLD",
    "reload_templates", "TEMPLATE_DIR", "TEMPLATE_FILES",
]
