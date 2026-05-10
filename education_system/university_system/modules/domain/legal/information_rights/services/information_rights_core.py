"""
Information Rights Core - SAR / FOI / EIR request lifecycle.

Owns its own SQLite tables (`ir_*`) so the module can be developed and
tested independently of the central student / finance schema. When given
no db_path, the service writes to the central university database
(``DEFAULT_DB_PATH``) so requests are visible to the GUI dashboard and
the audit / scheduler infrastructure.

Statutory deadlines:

* SAR (UK GDPR Art. 12(3) / DPA 2018):
    - one calendar month from the day after the request is received and
      identity is verified;
    - extendable by a further two calendar months when the request is
      complex or numerous (must notify the data subject of the extension
      within the original month).
* FOI (FOIA 2000 s.10(1)) and EIR (EIR 2004 reg.5(2)):
    - 20 working days from the day after the request is received.

The service tracks the deadline as an ISO date string and exposes
``days_remaining`` for dashboards.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterator, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants — kept module-level so callers (CLI, GUI, tests) can import them
# without going through a manager instance.
# ---------------------------------------------------------------------------

REQUEST_TYPES = ("SAR", "FOI", "EIR")

# Lifecycle states. Keep flat — UI surfaces them in a dropdown.
REQUEST_STATUSES = (
    "received",            # logged in the system, not yet triaged
    "awaiting_id",         # SAR only — identity not yet verified
    "in_progress",         # clock running, locating records
    "awaiting_clarity",    # paused — clarification requested from requester
    "extended",            # SAR: 2-month extension applied
    "ready_to_disclose",   # response drafted, awaiting sign-off
    "completed",           # response issued
    "refused",             # exemptions applied / vexatious / cost limit
    "withdrawn",           # requester withdrew
)

OUTCOMES = (
    "fully_disclosed",
    "partially_disclosed",
    "refused_exemption",
    "refused_vexatious",
    "refused_cost_limit",        # FOIA s.12 appropriate limit
    "info_not_held",
    "withdrawn",
    "transferred",               # forwarded to another public authority
)

IDENTITY_STATUSES = ("not_required", "pending", "verified", "failed")

# FOIA 2000 absolute & qualified exemptions. Section / short label only —
# the textual rationale is captured per-request in ir_exemptions.reason.
FOIA_EXEMPTIONS = {
    "s.21": "Information accessible by other means",
    "s.22": "Information intended for future publication",
    "s.22A": "Research information",
    "s.23": "Security bodies",
    "s.24": "National security",
    "s.26": "Defence",
    "s.27": "International relations",
    "s.28": "Relations within the UK",
    "s.29": "The economy",
    "s.30": "Investigations and proceedings",
    "s.31": "Law enforcement",
    "s.32": "Court records",
    "s.33": "Audit functions",
    "s.34": "Parliamentary privilege",
    "s.35": "Formulation of government policy",
    "s.36": "Prejudice to effective conduct of public affairs",
    "s.37": "Communications with the Royal Family / honours",
    "s.38": "Health and safety",
    "s.39": "Environmental information (use EIR)",
    "s.40": "Personal information (use UK GDPR)",
    "s.41": "Information provided in confidence",
    "s.42": "Legal professional privilege",
    "s.43": "Commercial interests",
    "s.44": "Prohibitions on disclosure",
    "s.12": "Cost of compliance exceeds appropriate limit",
    "s.14": "Vexatious or repeated request",
}

# DPA 2018 / UK GDPR exemptions commonly applied to SARs.
DPA_EXEMPTIONS = {
    "Sch.2 Pt.1 para.2": "Crime and taxation",
    "Sch.2 Pt.2 para.7": "Functions designed to protect the public",
    "Sch.2 Pt.3 para.16": "Health, social work, education",
    "Sch.2 Pt.4 para.19": "Confidential references",
    "Sch.2 Pt.4 para.20": "Exam scripts and marks",
    "Sch.2 Pt.4 para.21": "Legal professional privilege",
    "Sch.2 Pt.4 para.24": "Negotiations with the data subject",
    "Sch.3 Pt.4": "Health data — serious harm test",
    "Art.15(4)": "Rights and freedoms of others (third-party data)",
    "Manifestly unfounded / excessive": "Art. 12(5)",
}

# EIR 2004 exceptions (regulation 12).
EIR_EXCEPTIONS = {
    "reg.12(4)(a)": "Information not held",
    "reg.12(4)(b)": "Manifestly unreasonable",
    "reg.12(4)(c)": "Request too general",
    "reg.12(4)(d)": "Material in the course of completion",
    "reg.12(4)(e)": "Internal communications",
    "reg.12(5)(a)": "International relations / defence / public security",
    "reg.12(5)(b)": "Course of justice",
    "reg.12(5)(c)": "Intellectual property rights",
    "reg.12(5)(d)": "Confidentiality of proceedings",
    "reg.12(5)(e)": "Confidentiality of commercial information",
    "reg.12(5)(f)": "Interests of the information provider",
    "reg.12(5)(g)": "Protection of the environment",
    "reg.13":      "Personal data",
}


class InformationRightsError(Exception):
    """Domain error raised by :class:`InformationRightsService`."""


# ---------------------------------------------------------------------------
# Deadline arithmetic — pulled out so tests can pin behaviour.
# ---------------------------------------------------------------------------

def _add_calendar_months(start: date, months: int) -> date:
    """Add `months` calendar months to `start`, clamping at month-end.

    Used for SAR's "one calendar month" rule, which the ICO interprets as
    the corresponding date in the next month (or the last day of that
    month if the corresponding date does not exist).
    """
    month0 = start.month - 1 + months
    year = start.year + month0 // 12
    month = month0 % 12 + 1
    # Clamp: e.g. 31 Jan + 1 month -> 28/29 Feb.
    for day in (start.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise InformationRightsError("could not compute calendar month deadline")


def _add_working_days(start: date, days: int) -> date:
    """Add `days` UK-business days to `start`, skipping Sat/Sun.

    Bank holidays are not modelled — the ICO accepts working-day counts
    that exclude weekends only as a defensible default. A holiday
    calendar can be slotted in by overriding this function.
    """
    cur = start
    added = 0
    while added < days:
        cur += timedelta(days=1)
        if cur.weekday() < 5:           # 0=Mon .. 4=Fri
            added += 1
    return cur


def compute_deadline(request_type: str, received_on: date,
                     extended: bool = False) -> date:
    """Return the statutory due date for a request of `request_type`.

    The clock starts on the day **after** receipt, per ICO guidance.
    """
    if request_type == "SAR":
        months = 3 if extended else 1
        return _add_calendar_months(received_on, months)
    if request_type in ("FOI", "EIR"):
        return _add_working_days(received_on, 20)
    raise InformationRightsError(f"unknown request_type: {request_type!r}")


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

@dataclass
class _Request:
    """In-memory view of a row in `ir_requests`. Returned by getters."""
    request_id: str
    reference: str
    request_type: str
    requester_name: str
    requester_email: str
    requester_phone: Optional[str]
    subject_summary: str
    scope_details: Optional[str]
    received_on: str
    deadline_on: str
    identity_status: str
    status: str
    outcome: Optional[str]
    extended: int
    extension_reason: Optional[str]
    extension_notified_on: Optional[str]
    assigned_officer: Optional[str]
    fee_charged: float
    closed_on: Optional[str]
    created_at: str
    updated_at: str


def _row_to_request(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


class InformationRightsService:
    """SAR / FOI / EIR request lifecycle service.

    Parameters
    ----------
    db_path:
        SQLite file. When ``None`` (the default), the service writes to
        the central university database. Tests should pass a tmp path.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            from education_system.university_system.modules.shared.constants.paths import (  # noqa: E501
                DEFAULT_DB_PATH,
            )
            db_path = DEFAULT_DB_PATH
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".",
                    exist_ok=True)
        self._init_schema()

    # ------------------------------------------------------------------ db
    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS ir_requests (
                    request_id           TEXT PRIMARY KEY,
                    reference            TEXT UNIQUE NOT NULL,
                    request_type         TEXT NOT NULL CHECK
                        (request_type IN ('SAR','FOI','EIR')),
                    requester_name       TEXT NOT NULL,
                    requester_email      TEXT NOT NULL,
                    requester_phone      TEXT,
                    subject_summary      TEXT NOT NULL,
                    scope_details        TEXT,
                    received_on          TEXT NOT NULL,   -- ISO date
                    deadline_on          TEXT NOT NULL,   -- ISO date
                    identity_status      TEXT NOT NULL DEFAULT 'pending',
                    status               TEXT NOT NULL DEFAULT 'received',
                    outcome              TEXT,
                    extended             INTEGER NOT NULL DEFAULT 0,
                    extension_reason     TEXT,
                    extension_notified_on TEXT,
                    assigned_officer     TEXT,
                    fee_charged          REAL NOT NULL DEFAULT 0.0,
                    closed_on            TEXT,
                    created_at           TEXT NOT NULL,
                    updated_at           TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ir_status
                    ON ir_requests(status);
                CREATE INDEX IF NOT EXISTS idx_ir_deadline
                    ON ir_requests(deadline_on);

                CREATE TABLE IF NOT EXISTS ir_communications (
                    comm_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id   TEXT NOT NULL REFERENCES ir_requests(request_id)
                                 ON DELETE CASCADE,
                    direction    TEXT NOT NULL CHECK
                        (direction IN ('inbound','outbound','internal')),
                    channel      TEXT NOT NULL,        -- email/post/phone/portal
                    occurred_at  TEXT NOT NULL,
                    author       TEXT,
                    summary      TEXT NOT NULL,
                    body         TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_ir_comm_request
                    ON ir_communications(request_id);

                CREATE TABLE IF NOT EXISTS ir_exemptions (
                    exemption_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id   TEXT NOT NULL REFERENCES ir_requests(request_id)
                                 ON DELETE CASCADE,
                    regime       TEXT NOT NULL CHECK
                        (regime IN ('FOIA','DPA','EIR')),
                    code         TEXT NOT NULL,
                    label        TEXT NOT NULL,
                    reason       TEXT NOT NULL,         -- public-interest test,
                                                        -- harm rationale, etc.
                    applied_at   TEXT NOT NULL,
                    applied_by   TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_ir_exempt_request
                    ON ir_exemptions(request_id);

                CREATE TABLE IF NOT EXISTS ir_redactions (
                    redaction_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id    TEXT NOT NULL REFERENCES ir_requests(request_id)
                                  ON DELETE CASCADE,
                    document_ref  TEXT NOT NULL,        -- file name / path
                    page          TEXT,                 -- page or section ref
                    location      TEXT,                 -- e.g. "para 3, line 4"
                    redaction_type TEXT NOT NULL,       -- third_party_pii,
                                                        -- exempt_info, legally_privileged
                    rationale     TEXT NOT NULL,
                    exemption_id  INTEGER REFERENCES ir_exemptions(exemption_id),
                    redacted_at   TEXT NOT NULL,
                    redacted_by   TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_ir_redact_request
                    ON ir_redactions(request_id);

                CREATE TABLE IF NOT EXISTS ir_audit (
                    audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id  TEXT NOT NULL REFERENCES ir_requests(request_id)
                                ON DELETE CASCADE,
                    event       TEXT NOT NULL,
                    detail      TEXT,
                    actor       TEXT,
                    occurred_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ir_audit_request
                    ON ir_audit(request_id);
                """
            )

    # ----------------------------------------------------------- helpers
    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat(timespec="seconds")

    @staticmethod
    def _today() -> date:
        return date.today()

    def _audit(self, conn: sqlite3.Connection, request_id: str,
               event: str, detail: str = "", actor: str = "") -> None:
        conn.execute(
            "INSERT INTO ir_audit(request_id,event,detail,actor,occurred_at)"
            " VALUES (?,?,?,?,?)",
            (request_id, event, detail, actor, self._now()),
        )

    def _generate_reference(self, conn: sqlite3.Connection,
                            request_type: str, received_on: date) -> str:
        """Build a human-readable reference: e.g. SAR-2026-0007."""
        year = received_on.year
        prefix = f"{request_type}-{year}-"
        row = conn.execute(
            "SELECT reference FROM ir_requests "
            "WHERE reference LIKE ? ORDER BY reference DESC LIMIT 1",
            (prefix + "%",),
        ).fetchone()
        if row is None:
            seq = 1
        else:
            try:
                seq = int(row["reference"].rsplit("-", 1)[-1]) + 1
            except ValueError:
                seq = 1
        return f"{prefix}{seq:04d}"

    # -------------------------------------------------------------- intake
    def create_request(
        self,
        request_type: str,
        requester_name: str,
        requester_email: str,
        subject_summary: str,
        scope_details: str = "",
        requester_phone: str = "",
        received_on: Optional[date] = None,
        assigned_officer: str = "",
        actor: str = "",
    ) -> Dict[str, Any]:
        """Log a new request and start the statutory clock.

        For SARs ``identity_status`` defaults to ``pending`` — the clock
        only starts when identity is confirmed. The deadline is still
        computed from ``received_on`` so dashboards show the worst case;
        callers wanting strict ICO behaviour should call
        :meth:`mark_identity_verified` to reset the clock.
        """
        if request_type not in REQUEST_TYPES:
            raise InformationRightsError(
                f"request_type must be one of {REQUEST_TYPES}")
        if not requester_name.strip():
            raise InformationRightsError("requester_name is required")
        if "@" not in requester_email:
            raise InformationRightsError("requester_email looks invalid")
        if not subject_summary.strip():
            raise InformationRightsError("subject_summary is required")

        received_on = received_on or self._today()
        deadline = compute_deadline(request_type, received_on)
        request_id = uuid.uuid4().hex
        identity_status = "pending" if request_type == "SAR" else "not_required"
        status = "awaiting_id" if request_type == "SAR" else "received"
        now = self._now()

        with self._conn() as c:
            reference = self._generate_reference(c, request_type, received_on)
            c.execute(
                """INSERT INTO ir_requests(
                    request_id,reference,request_type,
                    requester_name,requester_email,requester_phone,
                    subject_summary,scope_details,
                    received_on,deadline_on,
                    identity_status,status,
                    assigned_officer,
                    created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    request_id, reference, request_type,
                    requester_name.strip(), requester_email.strip(),
                    requester_phone.strip() or None,
                    subject_summary.strip(), scope_details.strip() or None,
                    received_on.isoformat(), deadline.isoformat(),
                    identity_status, status,
                    assigned_officer.strip() or None,
                    now, now,
                ),
            )
            self._audit(c, request_id, "created",
                        f"{request_type} {reference}", actor)
            row = c.execute(
                "SELECT * FROM ir_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        return _row_to_request(row)

    # ------------------------------------------------------ identity verify
    def mark_identity_verified(self, request_id: str,
                               verified_on: Optional[date] = None,
                               actor: str = "",
                               restart_clock: bool = True) -> Dict[str, Any]:
        """Record successful identity verification on a SAR.

        If ``restart_clock`` is True (the default), the deadline is
        recomputed from ``verified_on`` — this is the ICO position when
        the original receipt could not be acted on without ID.
        """
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM ir_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if row is None:
                raise InformationRightsError("request not found")
            if row["request_type"] != "SAR":
                raise InformationRightsError(
                    "identity verification only applies to SARs")
            verified_on = verified_on or self._today()
            new_deadline = (
                compute_deadline("SAR", verified_on,
                                 extended=bool(row["extended"]))
                if restart_clock else row["deadline_on"]
            )
            new_status = ("extended" if row["extended"]
                          else "in_progress")
            c.execute(
                "UPDATE ir_requests SET identity_status='verified',"
                " status=?, deadline_on=?, updated_at=? WHERE request_id=?",
                (new_status,
                 new_deadline if isinstance(new_deadline, str)
                 else new_deadline.isoformat(),
                 self._now(), request_id),
            )
            self._audit(c, request_id, "identity_verified",
                        f"clock restarted={restart_clock}", actor)
            return _row_to_request(
                c.execute("SELECT * FROM ir_requests WHERE request_id=?",
                          (request_id,)).fetchone()
            )

    def mark_identity_failed(self, request_id: str, reason: str,
                             actor: str = "") -> Dict[str, Any]:
        with self._conn() as c:
            row = c.execute(
                "SELECT request_type FROM ir_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
            if row is None:
                raise InformationRightsError("request not found")
            c.execute(
                "UPDATE ir_requests SET identity_status='failed',"
                " updated_at=? WHERE request_id=?",
                (self._now(), request_id),
            )
            self._audit(c, request_id, "identity_failed", reason, actor)
            return _row_to_request(
                c.execute("SELECT * FROM ir_requests WHERE request_id=?",
                          (request_id,)).fetchone()
            )

    # -------------------------------------------------------- status moves
    def set_status(self, request_id: str, new_status: str,
                   actor: str = "", note: str = "") -> Dict[str, Any]:
        if new_status not in REQUEST_STATUSES:
            raise InformationRightsError(
                f"status must be one of {REQUEST_STATUSES}")
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM ir_requests WHERE request_id=?",
                (request_id,)
            ).fetchone()
            if row is None:
                raise InformationRightsError("request not found")
            if row["status"] in ("completed", "refused", "withdrawn") \
                    and new_status != row["status"]:
                raise InformationRightsError(
                    f"request already {row['status']}; cannot change status")
            c.execute(
                "UPDATE ir_requests SET status=?, updated_at=?"
                " WHERE request_id=?",
                (new_status, self._now(), request_id),
            )
            self._audit(c, request_id, "status_changed",
                        f"{row['status']} -> {new_status} {note}".strip(),
                        actor)
            return _row_to_request(
                c.execute("SELECT * FROM ir_requests WHERE request_id=?",
                          (request_id,)).fetchone()
            )

    def assign_officer(self, request_id: str, officer: str,
                       actor: str = "") -> None:
        with self._conn() as c:
            res = c.execute(
                "UPDATE ir_requests SET assigned_officer=?, updated_at=?"
                " WHERE request_id=?",
                (officer.strip() or None, self._now(), request_id),
            )
            if res.rowcount == 0:
                raise InformationRightsError("request not found")
            self._audit(c, request_id, "assigned", officer, actor)

    # ---------------------------------------------------------- extensions
    def apply_extension(self, request_id: str, reason: str,
                        notified_on: Optional[date] = None,
                        actor: str = "") -> Dict[str, Any]:
        """Apply the SAR 2-month extension under UK GDPR Art. 12(3).

        Recomputes the deadline from the original ``received_on`` (or
        identity verification date, whichever is later) plus 3 months.
        """
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM ir_requests WHERE request_id=?",
                (request_id,)
            ).fetchone()
            if row is None:
                raise InformationRightsError("request not found")
            if row["request_type"] != "SAR":
                raise InformationRightsError(
                    "extension only applies to SARs")
            if row["extended"]:
                raise InformationRightsError(
                    "extension already applied")
            if not reason.strip():
                raise InformationRightsError(
                    "extension requires a written reason")
            base = date.fromisoformat(row["received_on"])
            new_deadline = compute_deadline("SAR", base, extended=True)
            notified = (notified_on or self._today()).isoformat()
            c.execute(
                "UPDATE ir_requests SET extended=1, extension_reason=?,"
                " extension_notified_on=?, deadline_on=?, status='extended',"
                " updated_at=? WHERE request_id=?",
                (reason.strip(), notified, new_deadline.isoformat(),
                 self._now(), request_id),
            )
            self._audit(c, request_id, "extension_applied",
                        f"new deadline {new_deadline.isoformat()}: {reason}",
                        actor)
            return _row_to_request(
                c.execute("SELECT * FROM ir_requests WHERE request_id=?",
                          (request_id,)).fetchone()
            )

    # ------------------------------------------------------- communications
    def log_communication(self, request_id: str, direction: str,
                          channel: str, summary: str, body: str = "",
                          author: str = "",
                          occurred_at: Optional[datetime] = None) -> int:
        if direction not in ("inbound", "outbound", "internal"):
            raise InformationRightsError("invalid direction")
        with self._conn() as c:
            row = c.execute(
                "SELECT 1 FROM ir_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
            if row is None:
                raise InformationRightsError("request not found")
            cur = c.execute(
                "INSERT INTO ir_communications(request_id,direction,"
                " channel,occurred_at,author,summary,body)"
                " VALUES (?,?,?,?,?,?,?)",
                (request_id, direction, channel,
                 (occurred_at or datetime.utcnow()).isoformat(timespec="seconds"),
                 author or None, summary, body or None),
            )
            self._audit(c, request_id, f"comm_{direction}",
                        f"{channel}: {summary}", author)
            return int(cur.lastrowid)

    # ----------------------------------------------------------- exemptions
    def apply_exemption(self, request_id: str, regime: str, code: str,
                        reason: str, actor: str = "") -> int:
        """Record an exemption / exception relied on for non-disclosure.

        The catalogue lookup is permissive: callers may pass codes not
        in :data:`FOIA_EXEMPTIONS` etc. (e.g. for a niche EIR clause)
        and the label is auto-derived where possible.
        """
        regime = regime.upper()
        if regime not in ("FOIA", "DPA", "EIR"):
            raise InformationRightsError(
                "regime must be FOIA, DPA or EIR")
        if not reason.strip():
            raise InformationRightsError(
                "exemption requires a documented reason "
                "(harm test / public-interest balance)")
        catalogue = {
            "FOIA": FOIA_EXEMPTIONS,
            "DPA": DPA_EXEMPTIONS,
            "EIR": EIR_EXCEPTIONS,
        }[regime]
        label = catalogue.get(code, code)
        with self._conn() as c:
            row = c.execute(
                "SELECT 1 FROM ir_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
            if row is None:
                raise InformationRightsError("request not found")
            cur = c.execute(
                "INSERT INTO ir_exemptions(request_id,regime,code,label,"
                "reason,applied_at,applied_by) VALUES (?,?,?,?,?,?,?)",
                (request_id, regime, code, label, reason.strip(),
                 self._now(), actor or None),
            )
            self._audit(c, request_id, "exemption_applied",
                        f"{regime} {code}: {reason}", actor)
            return int(cur.lastrowid)

    # ----------------------------------------------------------- redactions
    def log_redaction(self, request_id: str, document_ref: str,
                      redaction_type: str, rationale: str,
                      page: str = "", location: str = "",
                      exemption_id: Optional[int] = None,
                      actor: str = "") -> int:
        """Record a redaction made to a disclosed document.

        Required so the university can demonstrate to the ICO *what* was
        withheld, *where*, and *why* — without retaining the content of
        the redacted material itself.
        """
        if not document_ref.strip():
            raise InformationRightsError("document_ref is required")
        if not rationale.strip():
            raise InformationRightsError("rationale is required")
        if redaction_type not in (
                "third_party_pii", "exempt_info",
                "legally_privileged", "out_of_scope", "other"):
            raise InformationRightsError(
                "redaction_type must be one of: third_party_pii,"
                " exempt_info, legally_privileged, out_of_scope, other")
        with self._conn() as c:
            row = c.execute(
                "SELECT 1 FROM ir_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
            if row is None:
                raise InformationRightsError("request not found")
            if exemption_id is not None:
                er = c.execute(
                    "SELECT request_id FROM ir_exemptions"
                    " WHERE exemption_id=?", (exemption_id,)).fetchone()
                if er is None or er["request_id"] != request_id:
                    raise InformationRightsError(
                        "exemption_id does not belong to this request")
            cur = c.execute(
                "INSERT INTO ir_redactions(request_id,document_ref,page,"
                "location,redaction_type,rationale,exemption_id,"
                "redacted_at,redacted_by) VALUES (?,?,?,?,?,?,?,?,?)",
                (request_id, document_ref.strip(), page or None,
                 location or None, redaction_type, rationale.strip(),
                 exemption_id, self._now(), actor or None),
            )
            self._audit(c, request_id, "redaction_logged",
                        f"{document_ref} ({redaction_type})", actor)
            return int(cur.lastrowid)

    # --------------------------------------------------------------- close
    def close_request(self, request_id: str, outcome: str,
                      actor: str = "", note: str = "",
                      closed_on: Optional[date] = None) -> Dict[str, Any]:
        if outcome not in OUTCOMES:
            raise InformationRightsError(
                f"outcome must be one of {OUTCOMES}")
        terminal = "completed"
        if outcome.startswith("refused_"):
            terminal = "refused"
        elif outcome == "withdrawn":
            terminal = "withdrawn"
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM ir_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
            if row is None:
                raise InformationRightsError("request not found")
            if row["status"] in ("completed", "refused", "withdrawn"):
                raise InformationRightsError(
                    f"request already closed as {row['status']}")
            c.execute(
                "UPDATE ir_requests SET status=?, outcome=?, closed_on=?,"
                " updated_at=? WHERE request_id=?",
                (terminal, outcome,
                 (closed_on or self._today()).isoformat(),
                 self._now(), request_id),
            )
            self._audit(c, request_id, "closed",
                        f"{outcome}: {note}".strip(": "), actor)
            return _row_to_request(
                c.execute("SELECT * FROM ir_requests WHERE request_id=?",
                          (request_id,)).fetchone()
            )

    # ------------------------------------------------------------ readers
    def get_request(self, request_id: str) -> Dict[str, Any]:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM ir_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
            if row is None:
                raise InformationRightsError("request not found")
            return _row_to_request(row)

    def get_by_reference(self, reference: str) -> Dict[str, Any]:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM ir_requests WHERE reference=?",
                (reference,),
            ).fetchone()
            if row is None:
                raise InformationRightsError("request not found")
            return _row_to_request(row)

    def list_requests(self, status: Optional[str] = None,
                      request_type: Optional[str] = None,
                      include_closed: bool = True,
                      limit: int = 200) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM ir_requests WHERE 1=1"
        args: List[Any] = []
        if status:
            sql += " AND status = ?"
            args.append(status)
        if request_type:
            sql += " AND request_type = ?"
            args.append(request_type)
        if not include_closed:
            sql += " AND status NOT IN ('completed','refused','withdrawn')"
        sql += " ORDER BY deadline_on ASC LIMIT ?"
        args.append(int(limit))
        with self._conn() as c:
            return [_row_to_request(r)
                    for r in c.execute(sql, args).fetchall()]

    def list_communications(self, request_id: str) -> List[Dict[str, Any]]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM ir_communications"
                " WHERE request_id=? ORDER BY occurred_at",
                (request_id,)).fetchall()]

    def list_exemptions(self, request_id: str) -> List[Dict[str, Any]]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM ir_exemptions"
                " WHERE request_id=? ORDER BY applied_at",
                (request_id,)).fetchall()]

    def list_redactions(self, request_id: str) -> List[Dict[str, Any]]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM ir_redactions"
                " WHERE request_id=? ORDER BY redacted_at",
                (request_id,)).fetchall()]

    def list_audit(self, request_id: str) -> List[Dict[str, Any]]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM ir_audit"
                " WHERE request_id=? ORDER BY occurred_at",
                (request_id,)).fetchall()]

    # ---------------------------------------------------------- dashboard
    def days_remaining(self, request: Dict[str, Any],
                       today: Optional[date] = None) -> int:
        """Calendar days until ``deadline_on``. Negative if overdue."""
        today = today or self._today()
        return (date.fromisoformat(request["deadline_on"]) - today).days

    def overdue(self, today: Optional[date] = None) -> List[Dict[str, Any]]:
        today = today or self._today()
        return [
            r for r in self.list_requests(include_closed=False)
            if self.days_remaining(r, today) < 0
        ]

    def due_within(self, days: int,
                   today: Optional[date] = None) -> List[Dict[str, Any]]:
        today = today or self._today()
        out = []
        for r in self.list_requests(include_closed=False):
            rem = self.days_remaining(r, today)
            if 0 <= rem <= days:
                out.append(r)
        return out

    def dashboard_summary(self,
                          today: Optional[date] = None) -> Dict[str, Any]:
        today = today or self._today()
        rows = self.list_requests(include_closed=True)
        open_rows = [r for r in rows
                     if r["status"] not in
                     ("completed", "refused", "withdrawn")]
        by_type: Dict[str, int] = {t: 0 for t in REQUEST_TYPES}
        by_status: Dict[str, int] = {}
        for r in open_rows:
            by_type[r["request_type"]] = by_type.get(r["request_type"], 0) + 1
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        overdue = [r for r in open_rows
                   if self.days_remaining(r, today) < 0]
        due_soon = [r for r in open_rows
                    if 0 <= self.days_remaining(r, today) <= 7]
        return {
            "as_of": today.isoformat(),
            "total_open": len(open_rows),
            "total_closed": len(rows) - len(open_rows),
            "by_type": by_type,
            "by_status": by_status,
            "overdue_count": len(overdue),
            "due_within_7_days": len(due_soon),
            "overdue": overdue,
            "due_soon": due_soon,
        }
