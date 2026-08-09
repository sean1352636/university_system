"""Statutory mark codes and absence reasons for Sixth Form Attendance.

Sibling to :mod:`attendance`. That module owns the rows; this one owns
the *vocabulary* they are written in.

A four-way status — Present / Late / Absent / Authorised — is enough to
run a lesson and nowhere near enough to make a return. "Absent" covers a
learner in hospital, a learner on a university open day, and a learner
who simply did not turn up; a funding body needs those told apart, and
so does anyone deciding whether to phone home. So each row carries a
**mark code** alongside its status:

* :data:`MARK_CODES` — the twenty codes the sector actually uses, each
  with the *meaning* that decides how it counts.
* :data:`MEANINGS` — the five buckets a code can fall into. Present and
  Approved both count as attending; Authorised and Unauthorised are both
  absence; Not counted drops out of the denominator entirely.
* **Absence reasons** — a separate, editable lookup. The code says how
  an absence counts, the reason says what happened. They are related but
  not the same thing: `I` (illness) is one code and a dozen reasons.
* **Data sources** — where a mark came from, so a register full of
  kiosk check-ins can be told from one a teacher typed.

The status column is *kept*, not replaced. Everything already reading
``status`` keeps working, and :func:`attendance.resolve_marks` fills in
whichever of the pair the caller left out.

Codes are a fixed vocabulary — a college cannot invent `Q` — but reasons
are per-college and live in a table, because every college's list is
different and none of them are wrong.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Meanings ────────────────────────────────────────────────────────

# How a code counts. This — not the letter — is what every calculation
# should branch on.
PRESENT: str = "Present"                 # in the room
APPROVED: str = "Approved"               # off site but being taught
AUTHORISED: str = "Authorised"           # absent, with permission
UNAUTHORISED: str = "Unauthorised"       # absent, without
NOT_COUNTED: str = "Not counted"         # not a possible attendance at all

MEANINGS: tuple[str, ...] = (
    PRESENT, APPROVED, AUTHORISED, UNAUTHORISED, NOT_COUNTED,
)

# Meanings that count as the learner having attended.
ATTENDING_MEANINGS: frozenset[str] = frozenset({PRESENT, APPROVED})
# Meanings that count as absence (authorised or not).
ABSENCE_MEANINGS: frozenset[str] = frozenset({AUTHORISED, UNAUTHORISED})


@dataclass(frozen=True)
class MarkCode:
    """One statutory mark code."""

    code: str
    label: str
    meaning: str
    status: str        # the coarse `attendance.STATUSES` value it implies
    description: str

    @property
    def attending(self) -> bool:
        return self.meaning in ATTENDING_MEANINGS

    @property
    def absence(self) -> bool:
        return self.meaning in ABSENCE_MEANINGS

    @property
    def possible(self) -> bool:
        """Whether this code counts toward the attendance denominator."""
        return self.meaning != NOT_COUNTED

    def __str__(self) -> str:                      # pragma: no cover - display
        return f"{self.code} — {self.label}"


# The vocabulary. Order is display order: present, then approved
# activity, then authorised absence, then unauthorised, then the codes
# that do not count at all.
MARK_CODES: tuple[MarkCode, ...] = (
    MarkCode("/", "Present (AM)", PRESENT, "Present",
             "Present for the morning session."),
    MarkCode("\\", "Present (PM)", PRESENT, "Present",
             "Present for the afternoon session."),
    MarkCode("L", "Late (before register closed)", PRESENT, "Late",
             "Arrived late but within the registration window, so still "
             "a present mark."),
    MarkCode("U", "Late (after register closed)", UNAUTHORISED, "Late",
             "Arrived after the register closed. Recorded as late for "
             "pastoral purposes but counts as unauthorised absence."),

    MarkCode("B", "Off-site educational activity", APPROVED, "Present",
             "Supervised education off site, arranged by the college."),
    MarkCode("D", "Dual registered", APPROVED, "Present",
             "Attending the other establishment the learner is "
             "registered at."),
    MarkCode("V", "Educational visit or trip", APPROVED, "Present",
             "On a college trip, visit or residential."),
    MarkCode("W", "Work experience", APPROVED, "Present",
             "On a work placement."),

    MarkCode("I", "Illness", AUTHORISED, "Authorised",
             "Unwell and unable to attend."),
    MarkCode("M", "Medical or dental appointment", AUTHORISED, "Authorised",
             "At an appointment that could not be made outside college "
             "hours."),
    MarkCode("R", "Religious observance", AUTHORISED, "Authorised",
             "Day exclusively set apart for religious observance."),
    MarkCode("S", "Study leave", AUTHORISED, "Authorised",
             "Authorised study leave during a public-examination period."),
    MarkCode("T", "Traveller absence", AUTHORISED, "Authorised",
             "Traveller family travelling for occupational purposes."),
    MarkCode("H", "Agreed family holiday", AUTHORISED, "Authorised",
             "Leave of absence agreed in advance."),
    MarkCode("E", "Excluded, no alternative provision", AUTHORISED,
             "Authorised",
             "Excluded with no alternative provision made."),
    MarkCode("C", "Other authorised circumstances", AUTHORISED, "Authorised",
             "Authorised for a reason not covered by another code."),

    MarkCode("N", "No reason yet provided", UNAUTHORISED, "Absent",
             "Absent, reason not yet established. Recode once the "
             "reason is known — this should never survive a week."),
    MarkCode("O", "Unauthorised absence", UNAUTHORISED, "Absent",
             "Absent without permission, or the reason given was not "
             "accepted."),

    MarkCode("X", "Not required to be in college", NOT_COUNTED, "Authorised",
             "The session is not one this learner is required to attend."),
    MarkCode("Y", "Exceptional closure", NOT_COUNTED, "Authorised",
             "College closed, transport unavailable, or another "
             "exceptional circumstance outside the learner's control."),
)

CODE_INDEX: dict[str, MarkCode] = {m.code: m for m in MARK_CODES}
CODES: tuple[str, ...] = tuple(m.code for m in MARK_CODES)

# The code written when a caller gives only a coarse status. Each is the
# least presumptuous choice for its bucket: an uncoded absence is `N`
# ("we do not know yet"), never `O` ("we decided it was unauthorised").
DEFAULT_CODE_FOR_STATUS: dict[str, str] = {
    "Present":    "/",
    "Late":       "L",
    "Absent":     "N",
    "Authorised": "C",
}

# Codes that mean the learner was somewhere else but still in education,
# so :mod:`attendance` can set the off-site flag without being told.
OFFSITE_CODES: frozenset[str] = frozenset({"B", "D", "V", "W"})


# ── Data sources ────────────────────────────────────────────────────

# Where a mark came from. Worth recording because the answer to "why is
# this register wrong" is often "the kiosk was unplugged".
DATA_SOURCES: tuple[str, ...] = (
    "manual",        # a member of staff typed it
    "cover",         # a covering teacher, who does not know the class
    "kiosk",         # room terminal / tap-in
    "qr",            # scanned code
    "self-service",  # the learner declared it in the portal
    "import",        # bulk file
    "sync",          # pulled from another system
    "derived",       # inferred by the platform (roll-up, auto-mark)
)
DEFAULT_DATA_SOURCE: str = "manual"


# ── Absence reasons ─────────────────────────────────────────────────

REASON_CATEGORIES: tuple[str, ...] = (
    "Medical", "Personal", "Educational", "Unexplained", "Other",
)
DEFAULT_REASON_CATEGORY: str = "Other"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_absence_reasons (
    reason_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    category          TEXT NOT NULL DEFAULT 'Other',
    default_code      TEXT,
    requires_evidence INTEGER NOT NULL DEFAULT 0,
    active            INTEGER NOT NULL DEFAULT 1,
    sort_order        INTEGER NOT NULL DEFAULT 100,
    created_at        TEXT DEFAULT (datetime('now')),
    UNIQUE(name)
);

CREATE INDEX IF NOT EXISTS idx_att_reason_active
    ON attendance_absence_reasons(active);
"""

# Shipped with the system so a fresh college is usable on day one, and
# so the seed can be pointed at sensible codes. Editable afterwards —
# nothing here is load-bearing.
SEED_REASONS: tuple[tuple[str, str, str, bool, int], ...] = (
    # (name, category, default_code, requires_evidence, sort_order)
    ("Illness",                  "Medical",     "I", False, 10),
    ("Medical appointment",      "Medical",     "M", True,  20),
    ("Dental appointment",       "Medical",     "M", True,  30),
    ("Mental health",            "Medical",     "I", False, 40),
    ("Bereavement",              "Personal",    "C", False, 50),
    ("Religious observance",     "Personal",    "R", False, 60),
    ("Transport failure",        "Personal",    "C", False, 70),
    ("Family holiday",           "Personal",    "H", False, 80),
    ("Public examination",       "Educational", "S", False, 90),
    ("Study leave",              "Educational", "S", False, 100),
    ("University open day",      "Educational", "C", True,  110),
    ("Interview",                "Educational", "C", True,  120),
    ("Work experience",          "Educational", "W", False, 130),
    ("College trip",             "Educational", "V", False, 140),
    ("Unexplained",              "Unexplained", "N", False, 150),
    ("Truancy",                  "Unexplained", "O", False, 160),
    ("Other",                    "Other",       "C", False, 999),
)


@dataclass
class AbsenceReason:
    """One entry in the college's editable reason list."""

    reason_id: int
    name: str
    category: str
    default_code: str | None
    requires_evidence: bool
    active: bool
    sort_order: int
    created_at: str | None = None

    @property
    def label(self) -> str:
        suffix = " (evidence required)" if self.requires_evidence else ""
        return f"{self.name}{suffix}"


@dataclass
class CodeCount:
    """How often one code was used over a window."""

    code: str
    label: str
    meaning: str
    count: int


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    # The reason list is pointed at by attendance_records.reason_id, and
    # the code columns live on that table, so its schema comes first.
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _DB_READY = True
    seed_reasons()
    logger.debug("Attendance code schema ready at %s", DB_PATH)


def _row_reason(r: sqlite3.Row) -> AbsenceReason:
    return AbsenceReason(
        reason_id=r["reason_id"],
        name=r["name"],
        category=r["category"],
        default_code=r["default_code"],
        requires_evidence=bool(r["requires_evidence"]),
        active=bool(r["active"]),
        sort_order=r["sort_order"],
        created_at=r["created_at"],
    )


# ── Code lookups ────────────────────────────────────────────────────

def get_code(code: str | None) -> MarkCode | None:
    """The :class:`MarkCode` for a letter, or ``None`` if unknown."""
    if not isinstance(code, str):
        return None
    return CODE_INDEX.get(code.strip())


def validate_code(value: Any) -> str:
    """Normalise and check a mark code, raising if it is not one of ours."""
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        raise ValidationError("Mark code is required")
    if s not in CODE_INDEX:
        raise ValidationError(
            f"Unknown mark code {s!r}. Valid codes: " + " ".join(CODES))
    return s


def status_for_code(code: str) -> str:
    """The coarse `attendance` status a code implies."""
    return CODE_INDEX[validate_code(code)].status


def default_code_for_status(status: str) -> str:
    """The code to write when a caller gave only a status."""
    s = (status or "").strip()
    if s not in DEFAULT_CODE_FOR_STATUS:
        raise ValidationError(
            f"Status must be one of: {', '.join(DEFAULT_CODE_FOR_STATUS)}")
    return DEFAULT_CODE_FOR_STATUS[s]


def meaning_for_code(code: str) -> str:
    return CODE_INDEX[validate_code(code)].meaning


def counts_as_present(code: str | None) -> bool:
    """Present or approved off-site activity — the learner attended."""
    mark = get_code(code)
    return bool(mark and mark.attending)


def counts_toward_possible(code: str | None) -> bool:
    """Whether the session belongs in the attendance denominator.

    An unknown or missing code counts, on the principle that a session
    nobody coded is still a session that was supposed to happen.
    """
    mark = get_code(code)
    return True if mark is None else mark.possible


def is_absence(code: str | None) -> bool:
    mark = get_code(code)
    return bool(mark and mark.absence)


def is_authorised_absence(code: str | None) -> bool:
    mark = get_code(code)
    return bool(mark and mark.meaning == AUTHORISED)


def is_unauthorised_absence(code: str | None) -> bool:
    mark = get_code(code)
    return bool(mark and mark.meaning == UNAUTHORISED)


def implies_offsite(code: str | None) -> bool:
    """Whether the code itself says the learner was away from college."""
    return isinstance(code, str) and code.strip() in OFFSITE_CODES


def codes_for_meaning(meaning: str) -> tuple[MarkCode, ...]:
    if meaning not in MEANINGS:
        raise ValidationError(
            f"Meaning must be one of: {', '.join(MEANINGS)}")
    return tuple(m for m in MARK_CODES if m.meaning == meaning)


def describe(code: str) -> str:
    """A one-line explanation, for a tooltip or a CLI listing."""
    mark = CODE_INDEX[validate_code(code)]
    return f"{mark.code} · {mark.label} · counts as {mark.meaning} — " \
           f"{mark.description}"


def validate_source(value: Any) -> str:
    s = (value or "").strip().lower() if isinstance(value, str) else ""
    if not s:
        return DEFAULT_DATA_SOURCE
    if s not in DATA_SOURCES:
        raise ValidationError(
            f"Data source must be one of: {', '.join(DATA_SOURCES)}")
    return s


# ── Reason CRUD ─────────────────────────────────────────────────────

def seed_reasons() -> int:
    """Insert the shipped reason list, skipping any that already exist.

    Idempotent: an edited or archived reason is left exactly as the
    college left it, because the insert is keyed on the unique name.
    """
    with _connect() as conn:
        before = conn.execute(
            "SELECT COUNT(*) AS n FROM attendance_absence_reasons"
        ).fetchone()["n"]
        conn.executemany(
            """INSERT OR IGNORE INTO attendance_absence_reasons
                   (name, category, default_code, requires_evidence,
                    sort_order)
               VALUES (?, ?, ?, ?, ?)""",
            [(name, category, code, 1 if evidence else 0, order)
             for name, category, code, evidence, order in SEED_REASONS])
        conn.commit()
        after = conn.execute(
            "SELECT COUNT(*) AS n FROM attendance_absence_reasons"
        ).fetchone()["n"]
    added = int(after) - int(before)
    if added:
        logger.info("Seeded %d absence reason(s)", added)
    return added


def _validate_reason_payload(data: dict[str, Any], *,
                             partial: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {}

    if "name" in data or not partial:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValidationError("Reason name is required")
        if len(name) > 80:
            raise ValidationError("Reason name must be 80 characters or fewer")
        out["name"] = name

    if "category" in data or not partial:
        category = (data.get("category") or DEFAULT_REASON_CATEGORY).strip()
        if category not in REASON_CATEGORIES:
            raise ValidationError(
                f"Category must be one of: {', '.join(REASON_CATEGORIES)}")
        out["category"] = category

    if "default_code" in data or not partial:
        raw = data.get("default_code")
        code = (raw or "").strip() if isinstance(raw, str) else None
        out["default_code"] = validate_code(code) if code else None

    if "requires_evidence" in data or not partial:
        out["requires_evidence"] = 1 if data.get("requires_evidence") else 0

    if "sort_order" in data or not partial:
        raw = data.get("sort_order", 100)
        try:
            out["sort_order"] = int(raw if raw not in (None, "") else 100)
        except (TypeError, ValueError):
            raise ValidationError(
                "Sort order must be a whole number") from None

    if "active" in data:
        out["active"] = 1 if data.get("active") else 0
    return out


def create_reason(data: dict[str, Any]) -> AbsenceReason:
    init_db()
    payload = _validate_reason_payload(data)
    columns = ", ".join(payload)
    placeholders = ", ".join("?" * len(payload))
    try:
        with _connect() as conn:
            cur = conn.execute(
                f"INSERT INTO attendance_absence_reasons ({columns}) "
                f"VALUES ({placeholders})", list(payload.values()))
            conn.commit()
            reason_id = int(cur.lastrowid or 0)
    except sqlite3.IntegrityError:
        raise ValidationError(
            f"A reason named {payload['name']!r} already exists") from None
    logger.info("Created absence reason #%d (%s)", reason_id, payload["name"])
    out = get_reason(reason_id)
    assert out is not None
    return out


def get_reason(reason_id: int) -> AbsenceReason | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_absence_reasons WHERE reason_id = ?",
            (reason_id,)).fetchone()
    return _row_reason(r) if r else None


def reason_by_name(name: str) -> AbsenceReason | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_absence_reasons "
            "WHERE LOWER(name) = LOWER(?)", ((name or "").strip(),)).fetchone()
    return _row_reason(r) if r else None


def list_reasons(*, active_only: bool = True,
                 category: str | None = None) -> list[AbsenceReason]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if active_only:
        clauses.append("active = 1")
    if category:
        if category not in REASON_CATEGORIES:
            raise ValidationError(
                f"Category must be one of: {', '.join(REASON_CATEGORIES)}")
        clauses.append("category = ?")
        args.append(category)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_absence_reasons {where} "
            "ORDER BY sort_order, name", args).fetchall()
    return [_row_reason(r) for r in rows]


def validate_reason_id(value: Any) -> int:
    """Check a reason id exists and is usable, returning it."""
    try:
        reason_id = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Reason must be a reason id") from None
    reason = get_reason(reason_id)
    if reason is None:
        raise ValidationError(f"No absence reason with id {reason_id}")
    if not reason.active:
        raise ValidationError(
            f"Absence reason {reason.name!r} has been archived")
    return reason_id


def update_reason(reason_id: int, data: dict[str, Any]) -> AbsenceReason:
    init_db()
    if get_reason(reason_id) is None:
        raise ValidationError(f"No absence reason with id {reason_id}")
    payload = _validate_reason_payload(data, partial=True)
    if not payload:
        out = get_reason(reason_id)
        assert out is not None
        return out
    sets = ", ".join(f"{k} = ?" for k in payload)
    try:
        with _connect() as conn:
            conn.execute(
                f"UPDATE attendance_absence_reasons SET {sets} "
                "WHERE reason_id = ?", [*payload.values(), reason_id])
            conn.commit()
    except sqlite3.IntegrityError:
        raise ValidationError(
            "Another reason already uses that name") from None
    logger.info("Updated absence reason #%d", reason_id)
    out = get_reason(reason_id)
    assert out is not None
    return out


def archive_reason(reason_id: int) -> AbsenceReason:
    """Retire a reason without deleting it.

    Deleting would orphan every historic row that points at it, so a
    retired reason is merely hidden from the pickers.
    """
    return update_reason(reason_id, {"active": False})


def restore_reason(reason_id: int) -> AbsenceReason:
    return update_reason(reason_id, {"active": True})


def reason_usage(reason_id: int) -> int:
    """How many live attendance rows point at this reason."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COUNT(*) AS n FROM attendance_records "
            "WHERE reason_id = ? AND voided = 0", (reason_id,)).fetchone()
    return int(r["n"])


# ── Applying codes to rows ──────────────────────────────────────────

def set_code(record_id: int, code: str, *,
             reason_id: int | None = None,
             actor: str | None = None,
             note: str | None = None) -> core.AttendanceRecord:
    """Recode one attendance row, re-deriving its status from the code.

    The usual path from `N` ("no reason yet") to whatever actually
    happened. Routes through :func:`attendance.update_record`, so the
    register lock and the amendment trail both apply.
    """
    init_db()
    code = validate_code(code)
    payload: dict[str, Any] = {"code": code, "status": status_for_code(code)}
    if reason_id is not None:
        payload["reason_id"] = validate_reason_id(reason_id)
    return core.update_record(
        record_id, payload, actor=actor,
        reason=note or f"Recoded to {code}", allow_retro=True)


def suggest_code(reason_id: int) -> str | None:
    """The code this reason is normally recorded under, if it names one."""
    reason = get_reason(reason_id)
    return reason.default_code if reason else None


def backfill_codes(*, date_from: str | None = None,
                   date_to: str | None = None) -> int:
    """Give a code to rows written before the column existed.

    Uses :data:`DEFAULT_CODE_FOR_STATUS`, so every backfilled absence
    lands on `N` rather than being guessed at as authorised or not.
    Returns the number of rows touched. Only rows with no code at all
    are considered, so this is safe to re-run.
    """
    init_db()
    clauses = ["code IS NULL"]
    args: list[Any] = []
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    where = " AND ".join(clauses)

    touched = 0
    with _connect() as conn:
        for status, code in DEFAULT_CODE_FOR_STATUS.items():
            cur = conn.execute(
                f"UPDATE attendance_records SET code = ? "
                f"WHERE {where} AND status = ?", [code, *args, status])
            touched += cur.rowcount
        conn.commit()
    if touched:
        logger.info("Backfilled mark codes on %d row(s)", touched)
    return touched


def uncoded_count(*, date_from: str | None = None,
                  date_to: str | None = None) -> int:
    """Live rows still carrying no mark code — what backfill would fix."""
    init_db()
    clauses = ["code IS NULL", "voided = 0"]
    args: list[Any] = []
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    with _connect() as conn:
        r = conn.execute(
            "SELECT COUNT(*) AS n FROM attendance_records "
            f"WHERE {' AND '.join(clauses)}", args).fetchone()
    return int(r["n"])


# ── Reporting ───────────────────────────────────────────────────────

def _window_clauses(student_id: str | None, group_id: int | None,
                    date_from: str | None, date_to: str | None
                    ) -> tuple[list[str], list[Any]]:
    clauses = ["voided = 0"]
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id)
    if group_id is not None:
        clauses.append("slot_id IN (SELECT slot_id FROM timetable_slots "
                       "WHERE group_id = ?)")
        args.append(group_id)
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    return clauses, args


def code_breakdown(*, student_id: str | None = None,
                   group_id: int | None = None,
                   date_from: str | None = None,
                   date_to: str | None = None) -> list[CodeCount]:
    """How many of each code were recorded over a window, commonest first.

    Rows with no code are reported under the empty code, because a gap
    in the coding is exactly the thing worth seeing.
    """
    init_db()
    clauses, args = _window_clauses(student_id, group_id, date_from, date_to)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT COALESCE(code, '') AS code, COUNT(*) AS n "
            f"FROM attendance_records WHERE {' AND '.join(clauses)} "
            "GROUP BY COALESCE(code, '') ORDER BY n DESC", args).fetchall()
    out: list[CodeCount] = []
    for r in rows:
        mark = get_code(r["code"])
        out.append(CodeCount(
            code=r["code"],
            label=mark.label if mark else "(no code)",
            meaning=mark.meaning if mark else "Unknown",
            count=int(r["n"]),
        ))
    return out


def meaning_breakdown(*, student_id: str | None = None,
                      group_id: int | None = None,
                      date_from: str | None = None,
                      date_to: str | None = None) -> dict[str, int]:
    """The same window rolled up to the five meanings.

    This is the shape a percentage wants: attending over possible.
    """
    counts = {meaning: 0 for meaning in MEANINGS}
    counts["Unknown"] = 0
    for row in code_breakdown(student_id=student_id, group_id=group_id,
                              date_from=date_from, date_to=date_to):
        counts[row.meaning] = counts.get(row.meaning, 0) + row.count
    return counts


def source_breakdown(*, student_id: str | None = None,
                     group_id: int | None = None,
                     date_from: str | None = None,
                     date_to: str | None = None) -> dict[str, int]:
    """How marks in this window were captured, by data source."""
    init_db()
    clauses, args = _window_clauses(student_id, group_id, date_from, date_to)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT COALESCE(data_source, 'manual') AS src, COUNT(*) AS n "
            f"FROM attendance_records WHERE {' AND '.join(clauses)} "
            "GROUP BY src ORDER BY n DESC", args).fetchall()
    return {r["src"]: int(r["n"]) for r in rows}
