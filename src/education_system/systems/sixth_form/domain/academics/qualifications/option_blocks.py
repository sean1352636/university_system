"""Option blocks and subject choices.

A sixth form timetables its subjects in *option blocks*: every subject
in block A is taught at the same times, so a learner takes at most one
subject from each block. Two subjects offered only in the same block
can never be taken together — a *block clash*.

Tables (students database):

* ``option_block_subjects`` — (academic year, block letter, subject,
  qualification type, capacity). A subject may run in more than one
  block.
* ``option_choices`` — a learner's choice for a year: block letter ->
  subject, with status Pending / Applied.

:func:`validate_choices` checks a learner's per-block choices;
:func:`find_block_assignment` places a plain list of subjects into
blocks (or reports the clash); :func:`apply_choices` turns the choices
into learning aims through ``learning_aims.add_aim``.
"""

from __future__ import annotations

import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.systems.sixth_form.domain.academics.qualifications import (
    grade_scales,
    learning_aims,
)

logger = logging.getLogger(__name__)

DB_PATH: Path | None = None

BLOCK_LETTERS: tuple[str, ...] = ("A", "B", "C", "D", "E", "F")
_YEAR_RE = re.compile(r"^\d{4}/\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS option_block_subjects (
    entry_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    academic_year      TEXT NOT NULL,
    block_letter       TEXT NOT NULL,
    subject            TEXT NOT NULL,
    qualification_type TEXT NOT NULL DEFAULT 'A Level',
    capacity           INTEGER,
    created_at         TEXT DEFAULT (datetime('now')),
    UNIQUE (academic_year, block_letter, subject)
);
CREATE INDEX IF NOT EXISTS idx_obs_year ON option_block_subjects(academic_year);

CREATE TABLE IF NOT EXISTS option_choices (
    choice_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    academic_year  TEXT NOT NULL,
    block_letter   TEXT NOT NULL,
    subject        TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Pending',
    aim_id         INTEGER,
    chosen_at      TEXT DEFAULT (datetime('now')),
    applied_at     TEXT,
    UNIQUE (student_id, academic_year, block_letter),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (aim_id) REFERENCES learning_aims(aim_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_choices_student ON option_choices(student_id);
"""


class ValidationError(ValueError):
    """Raised for invalid option-block input."""


@dataclass
class BlockEntry:
    entry_id: int
    academic_year: str
    block_letter: str
    subject: str
    qualification_type: str
    capacity: int | None


@dataclass
class Choice:
    choice_id: int
    student_id: str
    academic_year: str
    block_letter: str
    subject: str
    status: str
    aim_id: int | None
    chosen_at: str | None
    applied_at: str | None


@dataclass
class ChoiceCheck:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ── DB plumbing ────────────────────────────────────────────────────

def _students():
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _s,
    )
    return _s


def _db_path() -> Path:
    return Path(DB_PATH) if DB_PATH is not None else Path(_students().DB_PATH)


_READY_PATHS: set[str] = set()


def _connect() -> _sql.Connection:
    from education_system import paths
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(_db_path()))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    key = str(_db_path())
    if key in _READY_PATHS:
        return
    learning_aims.init_db()     # option_choices references learning_aims
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _READY_PATHS.add(key)


def _row(r: _sql.Row) -> BlockEntry:
    return BlockEntry(entry_id=r["entry_id"], academic_year=r["academic_year"],
                      block_letter=r["block_letter"], subject=r["subject"],
                      qualification_type=r["qualification_type"],
                      capacity=r["capacity"])


def _row_choice(r: _sql.Row) -> Choice:
    return Choice(choice_id=r["choice_id"], student_id=r["student_id"],
                  academic_year=r["academic_year"],
                  block_letter=r["block_letter"], subject=r["subject"],
                  status=r["status"], aim_id=r["aim_id"],
                  chosen_at=r["chosen_at"], applied_at=r["applied_at"])


def _year(value: Any) -> str:
    y = (str(value).strip() if value else "")
    if not _YEAR_RE.match(y):
        raise ValidationError("Academic year must look like '2025/26'")
    return y


def _letter(value: Any) -> str:
    letter = (str(value).strip().upper() if value else "")
    if letter not in BLOCK_LETTERS:
        raise ValidationError(f"Block must be one of: {', '.join(BLOCK_LETTERS)}")
    return letter


# ── Block definitions ─────────────────────────────────────────────

def add_block_subject(academic_year: str, block_letter: str, subject: str, *,
                      qualification_type: str | None = None,
                      capacity: Any = None) -> BlockEntry:
    """Offer ``subject`` in a block for a year."""
    init_db()
    year, letter = _year(academic_year), _letter(block_letter)
    name = (subject or "").strip()
    if not name:
        raise ValidationError("Subject is required")
    qtype = grade_scales.canonical_type(qualification_type or "") or None
    if qtype is None:
        if qualification_type:
            raise ValidationError(f"Unknown qualification type {qualification_type!r}")
        try:
            from education_system.systems.sixth_form.domain.academics.subjects import (
                subjects as _subjects,
            )
            qtype = _subjects.qualification_type_for_subject(name) or "A Level"
        except Exception:
            qtype = "A Level"
    cap = None
    if capacity not in (None, ""):
        try:
            cap = int(capacity)
        except (TypeError, ValueError):
            raise ValidationError("Capacity must be a whole number") from None
        if cap <= 0:
            raise ValidationError("Capacity must be positive")
    with _connect() as conn:
        try:
            conn.execute(
                """INSERT INTO option_block_subjects
                       (academic_year, block_letter, subject,
                        qualification_type, capacity)
                   VALUES (?, ?, ?, ?, ?)""",
                (year, letter, name, qtype, cap))
        except _sql.IntegrityError:
            raise ValidationError(
                f"{name} is already in block {letter} for {year}") from None
        conn.commit()
        r = conn.execute(
            "SELECT * FROM option_block_subjects WHERE academic_year = ? "
            "AND block_letter = ? AND subject = ?", (year, letter, name)).fetchone()
    logger.info("Option block %s %s: added %s", year, letter, name)
    return _row(r)


def remove_block_subject(entry_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM option_block_subjects WHERE entry_id = ?",
                           (int(entry_id),))
        conn.commit()
    return cur.rowcount > 0


def list_block_entries(academic_year: str) -> list[BlockEntry]:
    init_db()
    with _connect() as conn:
        return [_row(r) for r in conn.execute(
            "SELECT * FROM option_block_subjects WHERE academic_year = ? "
            "ORDER BY block_letter, subject", (_year(academic_year),)).fetchall()]


def blocks(academic_year: str) -> dict[str, list[str]]:
    """{block letter: [subjects]} for a year."""
    out: dict[str, list[str]] = {}
    for e in list_block_entries(academic_year):
        out.setdefault(e.block_letter, []).append(e.subject)
    return out


def list_years() -> list[str]:
    init_db()
    with _connect() as conn:
        return [r["academic_year"] for r in conn.execute(
            "SELECT DISTINCT academic_year FROM option_block_subjects "
            "ORDER BY academic_year DESC")]


def copy_blocks(from_year: str, to_year: str) -> int:
    """Copy a year's block pattern into another year (skips duplicates)."""
    init_db()
    src, dst = _year(from_year), _year(to_year)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO option_block_subjects
                   (academic_year, block_letter, subject, qualification_type,
                    capacity)
               SELECT ?, block_letter, subject, qualification_type, capacity
                 FROM option_block_subjects WHERE academic_year = ?""",
            (dst, src))
        conn.commit()
    return cur.rowcount


def block_uptake(academic_year: str) -> list[tuple[BlockEntry, int]]:
    """Each block entry with the number of learners who chose it."""
    entries = list_block_entries(academic_year)
    with _connect() as conn:
        counts = {(r["block_letter"], r["subject"]): r["n"] for r in conn.execute(
            "SELECT block_letter, subject, COUNT(*) AS n FROM option_choices "
            "WHERE academic_year = ? GROUP BY block_letter, subject",
            (academic_year,))}
    return [(e, counts.get((e.block_letter, e.subject), 0)) for e in entries]


# ── Validating choices ────────────────────────────────────────────

def validate_choices(academic_year: str, choices: dict[str, str], *,
                     student_id: str | None = None) -> ChoiceCheck:
    """Check per-block choices: one subject per block, offered in that
    block, no subject twice, within capacity.

    ``choices`` maps block letter -> subject (blank = free block).
    """
    year = _year(academic_year)
    pattern = blocks(year)
    check = ChoiceCheck(ok=True)
    if not pattern:
        check.errors.append(f"No option blocks are defined for {year}")
    seen: dict[str, str] = {}
    for letter_raw, subject in choices.items():
        subject = (subject or "").strip()
        if not subject:
            continue
        try:
            letter = _letter(letter_raw)
        except ValidationError as e:
            check.errors.append(str(e))
            continue
        if subject not in pattern.get(letter, []):
            where = [b for b, subs in pattern.items() if subject in subs]
            check.errors.append(
                f"{subject} is not offered in block {letter}"
                + (f" (it runs in block {', '.join(where)})" if where else ""))
        if subject in seen:
            check.errors.append(
                f"{subject} chosen twice (blocks {seen[subject]} and {letter})")
        seen[subject] = letter
    # Capacity: count other learners' choices.
    caps = {(e.block_letter, e.subject): e.capacity
            for e in list_block_entries(year) if e.capacity}
    if caps:
        with _connect() as conn:
            for letter, subject in ((_l, s) for _l, s in choices.items() if s):
                cap = caps.get((letter.upper(), subject))
                if not cap:
                    continue
                n = conn.execute(
                    "SELECT COUNT(*) AS n FROM option_choices WHERE "
                    "academic_year = ? AND block_letter = ? AND subject = ? "
                    "AND student_id != ?",
                    (year, letter.upper(), subject, student_id or "")).fetchone()["n"]
                if n >= cap:
                    check.warnings.append(
                        f"{subject} in block {letter.upper()} is full ({n}/{cap})")
    if len(seen) < 3:
        check.warnings.append(
            f"Only {len(seen)} subject(s) chosen — a full A-level programme "
            "is normally three")
    check.ok = not check.errors
    return check


def find_block_assignment(academic_year: str, subjects: list[str]
                          ) -> tuple[dict[str, str] | None, list[str]]:
    """Place subjects into distinct blocks, or explain the clash.

    Returns ({block: subject}, []) when a placement exists, otherwise
    (None, [reasons]).
    """
    pattern = blocks(_year(academic_year))
    wanted = [s.strip() for s in subjects if s and s.strip()]
    options = {s: [b for b, subs in sorted(pattern.items()) if s in subs]
               for s in wanted}
    missing = [s for s, bl in options.items() if not bl]
    if missing:
        return None, [f"{s} is not offered in any block" for s in missing]
    order = sorted(wanted, key=lambda s: len(options[s]))
    placed: dict[str, str] = {}

    def solve(i: int) -> bool:
        if i == len(order):
            return True
        subj = order[i]
        for b in options[subj]:
            if b not in placed:
                placed[b] = subj
                if solve(i + 1):
                    return True
                del placed[b]
        return False

    if solve(0):
        return dict(sorted(placed.items())), []
    # Hall's condition: some group of k subjects is offered in fewer than
    # k blocks between them. Report the smallest such group.
    from itertools import combinations
    reasons: list[str] = []
    for k in range(2, len(wanted) + 1):
        for group in combinations(wanted, k):
            union = sorted({b for s in group for b in options[s]})
            if len(union) < k:
                reasons.append(
                    f"Block clash: {', '.join(group)} need {k} different "
                    f"blocks but are only offered in block(s) {', '.join(union)}")
        if reasons:
            break
    if not reasons:
        reasons.append("Block clash: these subjects cannot all be placed in "
                       "different blocks")
    return None, reasons


# ── Recording and applying choices ────────────────────────────────

def save_choices(student_id: str, academic_year: str,
                 choices: dict[str, str]) -> ChoiceCheck:
    """Validate and store a learner's per-block choices (replacing any
    pending ones for that year). Applied choices are left untouched."""
    init_db()
    year = _year(academic_year)
    if _students().get_student(student_id) is None:
        raise ValidationError(f"No student with id {student_id}")
    check = validate_choices(year, choices, student_id=student_id)
    if not check.ok:
        return check
    with _connect() as conn:
        conn.execute("DELETE FROM option_choices WHERE student_id = ? AND "
                     "academic_year = ? AND status = 'Pending'",
                     (student_id, year))
        applied = {r["block_letter"] for r in conn.execute(
            "SELECT block_letter FROM option_choices WHERE student_id = ? "
            "AND academic_year = ?", (student_id, year))}
        for letter, subject in choices.items():
            subject = (subject or "").strip()
            if not subject or letter.upper() in applied:
                continue
            conn.execute(
                "INSERT INTO option_choices (student_id, academic_year, "
                "block_letter, subject) VALUES (?, ?, ?, ?)",
                (student_id, year, letter.upper(), subject))
        conn.commit()
    logger.info("Saved option choices for %s (%s)", student_id, year)
    return check


def list_choices(student_id: str | None = None,
                 academic_year: str | None = None) -> list[Choice]:
    init_db()
    clauses, args = [], []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id)
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(_year(academic_year))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_row_choice(r) for r in conn.execute(
            f"SELECT * FROM option_choices {where} "
            "ORDER BY academic_year DESC, student_id, block_letter", args)]


def apply_choices(student_id: str, academic_year: str, *,
                  start_date: str | None = None,
                  planned_end_date: str | None = None,
                  recorded_by: str | None = None) -> list[learning_aims.LearningAim]:
    """Create a learning aim for every pending choice.

    Start date defaults to 1 September of the academic year; planned end
    to 30 June two years later for A levels and one year later for
    anything else. A choice the learner already holds an active aim for
    is linked to that aim instead of duplicating it.
    """
    init_db()
    year = _year(academic_year)
    start = start_date or learning_aims.academic_year_start(year).isoformat()
    first = int(year[:4])
    qtypes = {(e.block_letter, e.subject): e.qualification_type
              for e in list_block_entries(year)}
    created: list[learning_aims.LearningAim] = []
    pending = [c for c in list_choices(student_id, year) if c.status == "Pending"]
    existing = {(a.qualification_type, a.subject): a
                for a in learning_aims.active_aims(student_id)}
    for order, c in enumerate(sorted(pending, key=lambda c: c.block_letter)):
        qtype = qtypes.get((c.block_letter, c.subject), "A Level")
        aim = existing.get((qtype, c.subject))
        if aim is None:
            years = 2 if qtype == "A Level" else 1
            aim = learning_aims.add_aim(student_id, {
                "qualification_type": qtype, "subject": c.subject,
                "start_date": start, "academic_year": year,
                "planned_end_date": planned_end_date or f"{first + years}-06-30",
                "display_order": order, "source": "option_blocks",
                "notes": f"Option block {c.block_letter} ({year})",
            }, recorded_by=recorded_by, reason="Applied from option-block choices")
            created.append(aim)
        with _connect() as conn:
            conn.execute(
                "UPDATE option_choices SET status = 'Applied', aim_id = ?, "
                "applied_at = datetime('now') WHERE choice_id = ?",
                (aim.aim_id, c.choice_id))
            conn.commit()
    logger.info("Applied %d option choice(s) for %s (%s): %d new aim(s)",
                len(pending), student_id, year, len(created))
    return created



# ── Programme check (for an applicant not yet enrolled) ─────────────
#
# The blocks say which subjects can be taken together. Whether a subject
# has room is the admissions *places* for the intake cycle
# (``admissions.capacity``: places per programme, held by applicants at
# Offer Made / Accepted / Deferred / Enrolled) - not counted again here.


def intake_year(today: Any = None) -> str:
    """The academic year a new applicant starts in (admissions' rule:
    an open cycle, else the coming September)."""
    from education_system.systems.sixth_form.domain.admissions import admissions as _adm
    return _adm.default_intake_year(today)


def _places(cycle: str, own: Any = None) -> dict[str, dict[str, Any]]:
    """{subject (lower case): {capacity, taken}} for A-level programmes
    with places set in *cycle*; a place *own* (an applicant) holds is
    left out of ``taken``."""
    from education_system.systems.sixth_form.domain.admissions import capacity
    mine: set[str] = set()
    if own is not None and own.status in capacity.HOLDING_STATUSES:
        mine = {(x or "").strip().lower() for x in (own.subject_1, own.subject_2,
                                                     own.subject_3)} - {""}
    out = {}
    for pp in capacity.programme_places(cycle, only_limited=True):
        if grade_scales.canonical_type(pp.qualification_type) != "A Level":
            continue
        key = pp.subject.strip().lower()
        out[key] = {"capacity": pp.places,
                    "taken": max(pp.held - (1 if key in mine else 0), 0)}
    return out


def programme_check(subjects: list[str], *, academic_year: str | None = None,
                    exclude_applicant: str | None = None) -> dict[str, Any]:
    """Can these subjects be taken together, with places left?

    Returns ``academic_year``; ``published`` (False when no blocks are set
    up for that year - then nothing is checked); ``blocks`` ({letter:
    [subjects]}); ``courses`` ({subject: {blocks, capacity, taken, full}})
    for every subject in a block, with places from admissions (capacity
    None = no limit set); ``placement`` ({letter: subject}, or None);
    ``full`` (the chosen subjects with no places left); ``clashes``
    (subjects in no block, block clashes); and ``problems`` (both, as
    sentences - empty when the programme fits). *exclude_applicant*'s own
    place doesn't count against them.
    """
    from education_system.systems.sixth_form.domain.admissions import admissions as _adm
    own = _adm.get_applicant(exclude_applicant) if exclude_applicant else None
    year = _year(academic_year or (own.intake_year if own and own.intake_year else None)
                 or intake_year())
    entries = list_block_entries(year)
    out: dict[str, Any] = {"academic_year": year, "published": bool(entries),
                           "blocks": {}, "courses": {}, "placement": None, "full": [],
                           "clashes": [], "problems": []}
    if not entries:
        return out
    places = _places(year, own)
    courses: dict[str, dict[str, Any]] = {}
    for e in entries:
        out["blocks"].setdefault(e.block_letter, []).append(e.subject)
        p = places.get(e.subject.lower(), {"capacity": None, "taken": 0})
        c = courses.setdefault(e.subject, {"blocks": [], **p})
        c["blocks"].append(e.block_letter)
    for c in courses.values():
        c["full"] = c["capacity"] is not None and c["taken"] >= c["capacity"]
    out["courses"] = courses
    by_lower = {s.lower(): s for s in courses}
    wanted = [by_lower.get(s.strip().lower(), s.strip()) for s in subjects or []
              if s and s.strip()]
    for s in wanted:
        c = courses.get(s)
        if c and c["full"]:
            out["full"].append(s)
            out["problems"].append(f"{s} is full ({c['taken']} of {c['capacity']} places "
                                   "taken)")
    placement, reasons = find_block_assignment(year, wanted)
    out["placement"] = placement
    out["clashes"] = reasons
    out["problems"].extend(reasons)
    return out
