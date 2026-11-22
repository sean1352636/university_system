"""Year 9 options: pupils choose their GCSE (KS4) subjects.

**Rounds.** An options round is for one year group (Year 9 by default) choosing
the subjects they will take from Year 10. As in the old screen, a round has a
name, opens / closes dates, how many choices and reserves each pupil makes and
a status - Draft -> Open -> Closed -> Finalised:

* Open needs enough subjects for a full set of choices and a closing date;
* back to Draft only while nobody has chosen;
* Finalised needs every pupil who chose to have their subjects allocated, and
  locks the allocation.

**Subjects and rules.** A round offers active subjects taught in the next year.
Core subjects (English, maths, science...) aren't options - everyone takes them.
Rules such as "at least 1 Humanities or Languages" (the EBacc categories on the
subject) are checked on each pupil's choices; the options lead can accept a
pupil's choices that break a rule, with a reason.

**Choices.** Staff (tutors) enter a pupil's ranked choices and reserves while
the round is open; the options lead can enter or change them until it is
finalised. Families of pupils who haven't chosen can be e-mailed a reminder.

**Blocks and allocation.** Option blocks are the timetable columns: each block
runs some subjects (a subject can run in more than one block), each with a
class size. Blocks can be suggested from the choices (subjects often chosen
together go in different blocks). Allocation then gives each pupil their
choices in different blocks with room, swapping in a reserve when a choice
can't fit; anyone who still can't fit is listed for the options lead to place
by hand. When finalised, families can be e-mailed the outcome and - after the
year rollover, when the pupils are in Year 10 - each block's subjects become
Year 10 option teaching groups with their pupils in them.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import OPTIONS_EDITORS, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

STATUSES: tuple[str, ...] = ("Draft", "Open", "Closed", "Finalised")
BLOCK_NAMES: tuple[str, ...] = tuple("ABCDEFGH")
DEFAULT_CLASS_SIZE = 28

_SCHEMA = """
CREATE TABLE IF NOT EXISTS option_rounds (
    round_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT NOT NULL UNIQUE COLLATE NOCASE,
    year_group         INTEGER NOT NULL DEFAULT 9 CHECK (year_group BETWEEN 7 AND 10),
    status             TEXT NOT NULL DEFAULT 'Draft'
                       CHECK (status IN ('Draft', 'Open', 'Closed', 'Finalised')),
    opens_on           TEXT,
    closes_on          TEXT,
    choices_required   INTEGER NOT NULL DEFAULT 4,
    reserves_required  INTEGER NOT NULL DEFAULT 1,
    blocks             INTEGER NOT NULL DEFAULT 4,
    class_size         INTEGER NOT NULL DEFAULT 28,
    notes              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    created_by         TEXT,
    updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by         TEXT
);
CREATE TABLE IF NOT EXISTS option_round_subjects (
    round_id    INTEGER NOT NULL REFERENCES option_rounds (round_id) ON DELETE CASCADE,
    subject_id  INTEGER NOT NULL REFERENCES subjects (subject_id),
    guidance    TEXT,
    PRIMARY KEY (round_id, subject_id)
);
CREATE TABLE IF NOT EXISTS option_rules (
    rule_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id    INTEGER NOT NULL REFERENCES option_rounds (round_id) ON DELETE CASCADE,
    categories  TEXT NOT NULL,
    min_count   INTEGER NOT NULL DEFAULT 1 CHECK (min_count BETWEEN 1 AND 10),
    UNIQUE (round_id, categories)
);
CREATE TABLE IF NOT EXISTS option_pupils (
    round_id      INTEGER NOT NULL REFERENCES option_rounds (round_id) ON DELETE CASCADE,
    pupil_id      INTEGER NOT NULL REFERENCES pupils (pupil_id),
    submitted_at  TEXT NOT NULL DEFAULT (datetime('now')),
    submitted_by  TEXT,
    override_reason TEXT,
    notes         TEXT,
    PRIMARY KEY (round_id, pupil_id)
);
CREATE TABLE IF NOT EXISTS option_choices (
    round_id    INTEGER NOT NULL,
    pupil_id    INTEGER NOT NULL,
    subject_id  INTEGER NOT NULL REFERENCES subjects (subject_id),
    rank        INTEGER NOT NULL,
    is_reserve  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (round_id, pupil_id, rank),
    UNIQUE (round_id, pupil_id, subject_id),
    FOREIGN KEY (round_id, pupil_id) REFERENCES option_pupils (round_id, pupil_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_option_choices_subject ON option_choices (round_id, subject_id);
CREATE TABLE IF NOT EXISTS option_blocks (
    round_id    INTEGER NOT NULL REFERENCES option_rounds (round_id) ON DELETE CASCADE,
    block       TEXT NOT NULL,
    subject_id  INTEGER NOT NULL REFERENCES subjects (subject_id),
    capacity    INTEGER NOT NULL CHECK (capacity BETWEEN 1 AND 40),
    PRIMARY KEY (round_id, block, subject_id)
);
CREATE TABLE IF NOT EXISTS option_allocations (
    round_id      INTEGER NOT NULL,
    pupil_id      INTEGER NOT NULL,
    block         TEXT NOT NULL,
    subject_id    INTEGER NOT NULL REFERENCES subjects (subject_id),
    from_reserve  INTEGER NOT NULL DEFAULT 0,
    manual        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (round_id, pupil_id, block),
    UNIQUE (round_id, pupil_id, subject_id),
    FOREIGN KEY (round_id, pupil_id) REFERENCES option_pupils (round_id, pupil_id)
        ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS option_audit (
    audit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id  INTEGER,
    pupil_id  INTEGER,
    action    TEXT NOT NULL CHECK (action IN (
        'create', 'update', 'status', 'delete', 'subject_add', 'subject_remove', 'rule_add',
        'rule_remove', 'choices', 'choices_clear', 'blocks', 'allocate', 'allocate_manual',
        'remind', 'results', 'groups')),
    actor     TEXT NOT NULL,
    detail    TEXT,
    at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

database.register_schema("options", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Round:
    round_id: int
    name: str
    year_group: int
    status: str
    opens_on: str | None
    closes_on: str | None
    choices_required: int
    reserves_required: int
    blocks: int
    class_size: int
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None

    @property
    def picks(self) -> int:
        return self.choices_required + self.reserves_required

    @property
    def next_year(self) -> int:
        return self.year_group + 1

    @property
    def block_names(self) -> tuple[str, ...]:
        return BLOCK_NAMES[:self.blocks]

    @property
    def is_open_today(self) -> bool:
        today = _today().isoformat()
        return (self.status == "Open" and (not self.opens_on or self.opens_on <= today)
                and (not self.closes_on or today <= self.closes_on))


@dataclass(frozen=True)
class Rule:
    rule_id: int
    round_id: int
    categories: tuple[str, ...]
    min_count: int

    @property
    def label(self) -> str:
        return f"At least {self.min_count} from {' or '.join(self.categories)}"


@dataclass(frozen=True)
class Choice:
    subject_id: int
    code: str
    name: str
    rank: int
    is_reserve: bool


@dataclass(frozen=True)
class PupilChoices:
    round_id: int
    pupil_id: int
    pupil_name: str
    admission_no: str
    form_group: str | None
    submitted_at: str
    submitted_by: str | None
    override_reason: str | None
    notes: str | None
    choices: tuple[Choice, ...]

    @property
    def primary(self) -> list[Choice]:
        return [c for c in self.choices if not c.is_reserve]

    @property
    def reserves(self) -> list[Choice]:
        return [c for c in self.choices if c.is_reserve]

    @property
    def label(self) -> str:
        return (", ".join(c.code for c in self.primary)
                + (f"  (reserve {', '.join(c.code for c in self.reserves)})"
                   if self.reserves else ""))


@dataclass(frozen=True)
class Allocation:
    pupil_id: int
    block: str
    subject_id: int
    code: str
    name: str
    from_reserve: bool
    manual: bool


# ── Helpers ──────────────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in OPTIONS_EDITORS


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if not actor.is_staff:
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only school staff can work with options.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only the options lead can do this - other staff can view "
                               "rounds and enter pupils' choices while a round is open.")


def _audit(conn, action: str, actor: Principal, *, round_id: int | None = None,
           pupil_id: int | None = None, detail: dict | None = None) -> None:
    conn.execute("INSERT INTO option_audit (round_id, pupil_id, action, actor, detail) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (round_id, pupil_id, action, actor.username or "unknown",
                  json.dumps(detail, default=str, sort_keys=True) if detail else None))


def _date(value: Any, label: str, problems: list[str]) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, _dt.date):
        return value.isoformat()
    try:
        return _dt.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _int(value: Any, label: str, lo: int, hi: int, problems: list[str]) -> int | None:
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        n = lo - 1
    if not lo <= n <= hi:
        problems.append(f"{label} must be a whole number from {lo} to {hi}")
        return None
    return n


def _row_round(r) -> Round:
    return Round(**{k: r[k] for k in Round.__dataclass_fields__})


# ── Rounds ───────────────────────────────────────────────────────────

def get_round(round_id: int) -> Round:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM option_rounds WHERE round_id = ?",
                         (int(round_id),)).fetchone()
    if r is None:
        raise NotFound(f"No options round #{round_id}")
    return _row_round(r)


def list_rounds(*, status: str | None = None, year_group: int | None = None) -> list[Round]:
    sql, where, params = "SELECT * FROM option_rounds", [], []
    if status:
        if status not in STATUSES:
            raise ValidationError([f"Status must be one of {', '.join(STATUSES)}"])
        where.append("status = ?")
        params.append(status)
    if year_group:
        where.append("year_group = ?")
        params.append(int(year_group))
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [_row_round(r) for r in conn.execute(sql + " ORDER BY round_id DESC", params)]


EDITABLE_FIELDS = ("name", "year_group", "opens_on", "closes_on", "choices_required",
                   "reserves_required", "blocks", "class_size", "notes")


def _clean_round(data: dict[str, Any], current: Round | None) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(EDITABLE_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    merged: dict[str, Any] = ({k: getattr(current, k) for k in EDITABLE_FIELDS} if current
                              else {"year_group": 9, "choices_required": 4,
                                    "reserves_required": 1, "class_size": DEFAULT_CLASS_SIZE})
    merged.update({k: v for k, v in data.items() if not (v in (None, "") and k in (
        "year_group", "choices_required", "reserves_required", "class_size", "blocks"))})
    out: dict[str, Any] = {}
    out["name"] = P._clean_text(merged.get("name"), 64)
    if not out["name"]:
        problems.append("Give the round a name (e.g. 'Year 9 options 2026/27')")
    out["year_group"] = _int(merged.get("year_group"), "Year group", 7, 10, problems)
    out["opens_on"] = _date(merged.get("opens_on"), "Opens on", problems)
    out["closes_on"] = _date(merged.get("closes_on"), "Closes on", problems)
    if out["opens_on"] and out["closes_on"] and out["closes_on"] < out["opens_on"]:
        problems.append("The closing date can't be before the opening date")
    out["choices_required"] = _int(merged.get("choices_required"), "Choices", 1, 8, problems)
    out["reserves_required"] = _int(merged.get("reserves_required"), "Reserves", 0, 4,
                                    problems)
    blocks = merged.get("blocks")
    if blocks in (None, ""):
        blocks = out["choices_required"] or 4
    out["blocks"] = _int(blocks, "Blocks", 1, len(BLOCK_NAMES), problems)
    if out["blocks"] and out["choices_required"] and out["blocks"] < out["choices_required"]:
        problems.append(f"There must be at least {out['choices_required']} blocks - one for "
                        "each choice")
    out["class_size"] = _int(merged.get("class_size"), "Class size", 5, 40, problems)
    out["notes"] = P._clean_text(merged.get("notes"), 2000)
    if problems:
        raise ValidationError(problems)
    return out


def create_round(data: dict[str, Any], *, actor: Principal) -> Round:
    _require_editor(actor, "options.create")
    clean = _clean_round(data, None)
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM option_rounds WHERE name = ?",
                        (clean["name"],)).fetchone():
            raise ValidationError([f"There's already a round called '{clean['name']}'"])
        cols = list(clean)
        rid = conn.execute(
            f"INSERT INTO option_rounds ({', '.join(cols)}, created_by, updated_by) "  # nosec B608 - columns from _clean_round
            f"VALUES ({', '.join('?' * len(cols))}, ?, ?)",
            (*clean.values(), actor.username, actor.username)).lastrowid
        _audit(conn, "create", actor, round_id=rid)
    activity_log.record("options.create", target=f"round:{rid}", principal=actor)
    return get_round(rid)


def update_round(round_id: int, changes: dict[str, Any], *, actor: Principal) -> Round:
    r = get_round(round_id)
    _require_editor(actor, "options.update", f"round:{r.round_id}")
    if r.status == "Finalised":
        raise ValidationError(["The round is finalised - nothing can change"])
    clean = _clean_round(changes, r)
    diff = {k: v for k, v in clean.items() if getattr(r, k) != v}
    if not diff:
        return r
    with database.connect() as conn:
        if "name" in diff and conn.execute(
                "SELECT 1 FROM option_rounds WHERE name = ? AND round_id != ?",
                (clean["name"], r.round_id)).fetchone():
            raise ValidationError([f"There's already a round called '{clean['name']}'"])
        chosen = conn.execute("SELECT COUNT(*) FROM option_pupils WHERE round_id = ?",
                              (r.round_id,)).fetchone()[0]
        locked = {"year_group", "choices_required", "reserves_required"} & set(diff)
        if chosen and locked:
            raise ValidationError([f"{chosen} pupil(s) have already chosen - the year and the "
                                   "number of choices can't change now"])
        if "blocks" in diff and conn.execute(
                "SELECT 1 FROM option_blocks WHERE round_id = ? AND block NOT IN "
                f"({', '.join('?' * clean['blocks'])})",  # nosec B608 - placeholders only
                (r.round_id, *BLOCK_NAMES[:clean["blocks"]])).fetchone():
            raise ValidationError(["Empty the blocks you're removing first"])
        sets = ", ".join(f"{k} = ?" for k in diff)
        conn.execute(f"UPDATE option_rounds SET {sets}, updated_at = datetime('now'), "  # nosec B608 - keys from _clean_round
                     "updated_by = ? WHERE round_id = ?",
                     (*diff.values(), actor.username, r.round_id))
        _audit(conn, "update", actor, round_id=r.round_id, detail={"fields": sorted(diff)})
    activity_log.record("options.update", target=f"round:{r.round_id}", principal=actor,
                        fields=sorted(diff))
    return get_round(r.round_id)


def status_problems(r: Round, status: str) -> list[str]:
    """Why *r* can't move to *status* (empty if it can)."""
    if status not in STATUSES:
        return [f"Status must be one of {', '.join(STATUSES)}"]
    if status == r.status:
        return []
    out = []
    if r.status == "Finalised":
        return ["The round is finalised - it can't change"]
    if status == "Draft" and summary(r.round_id)["pupils_submitted"]:
        out.append("Pupils have already chosen - it can't go back to Draft")
    if status == "Open":
        n = len(list_round_subjects(r.round_id))
        if n < r.picks:
            out.append(f"Offer at least {r.picks} subjects first ({r.choices_required} choices "
                       f"+ {r.reserves_required} reserve(s)); {n} so far")
        if not r.closes_on:
            out.append("Set the closing date first")
    if status == "Finalised":
        if r.status != "Closed":
            out.append("Close the round and allocate subjects first")
        else:
            a = allocation_status(r.round_id)
            if not a["allocated"]:
                out.append("Nobody has been allocated subjects yet - run the allocation")
            if a["unresolved"]:
                out.append(f"{len(a['unresolved'])} pupil(s) still need subjects - place them "
                           "by hand first")
    return out


def set_status(round_id: int, status: str, *, actor: Principal) -> Round:
    r = get_round(round_id)
    _require_editor(actor, "options.status", f"round:{r.round_id}")
    status = str(status or "").strip().title()
    problems = status_problems(r, status)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE option_rounds SET status = ?, updated_at = datetime('now'), "
                     "updated_by = ? WHERE round_id = ?", (status, actor.username, r.round_id))
        _audit(conn, "status", actor, round_id=r.round_id, detail={"from": r.status,
                                                                   "to": status})
    activity_log.record("options.status", target=f"round:{r.round_id}", principal=actor,
                        status=status)
    return get_round(r.round_id)


def delete_round(round_id: int, *, actor: Principal) -> Round:
    r = get_round(round_id)
    _require_editor(actor, "options.delete", f"round:{r.round_id}")
    if r.status == "Finalised":
        raise ValidationError(["A finalised round is a record of pupils' subjects - it can't "
                               "be deleted"])
    with database.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM option_pupils WHERE round_id = ?",
                         (r.round_id,)).fetchone()[0]
        conn.execute("DELETE FROM option_rounds WHERE round_id = ?", (r.round_id,))
        _audit(conn, "delete", actor, round_id=r.round_id, detail={"name": r.name,
                                                                   "pupils": n})
    activity_log.record("options.delete", target=f"round:{r.round_id}", principal=actor)
    return r


def history(round_id: int, *, pupil_id: int | None = None,
            limit: int = 300) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM option_audit WHERE round_id = ?", [int(round_id)]
    if pupil_id is not None:
        sql += " AND pupil_id = ?"
        params.append(int(pupil_id))
    params.append(int(limit))
    with database.connect() as conn:
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "pupil_id": r["pupil_id"], "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?", params)]


# ── Subjects on offer ────────────────────────────────────────────────

def _editable(r: Round) -> None:
    if r.status == "Finalised":
        raise ValidationError(["The round is finalised - nothing can change"])


def list_round_subjects(round_id: int) -> list[S.Subject]:
    with database.connect() as conn:
        ids = [x[0] for x in conn.execute(
            "SELECT rs.subject_id FROM option_round_subjects rs JOIN subjects s USING "
            "(subject_id) WHERE rs.round_id = ? ORDER BY s.name COLLATE NOCASE",
            (int(round_id),))]
    return [S.get(i) for i in ids]


def guidance(round_id: int) -> dict[int, str]:
    with database.connect() as conn:
        return {r[0]: r[1] for r in conn.execute(
            "SELECT subject_id, guidance FROM option_round_subjects WHERE round_id = ? AND "
            "guidance IS NOT NULL", (int(round_id),))}


def available_subjects(round_id: int) -> list[S.Subject]:
    """Subjects that could be offered: active, taught next year, not core."""
    r = get_round(round_id)
    have = {s.subject_id for s in list_round_subjects(r.round_id)}
    return [s for s in S.list_subjects() if s.is_active and not s.is_core
            and r.next_year in s.years and s.subject_id not in have]


def add_round_subject(round_id: int, subject_id: int, *, actor: Principal,
                      guidance_text: str | None = None) -> S.Subject:
    r = get_round(round_id)
    _require_editor(actor, "options.subject_add", f"round:{r.round_id}")
    _editable(r)
    try:
        s = S.get(int(subject_id))
    except (TypeError, ValueError, S.NotFound):
        raise ValidationError(["Choose a subject"]) from None
    problems = []
    if not s.is_active:
        problems.append(f"{s.name} is inactive")
    if s.is_core:
        problems.append(f"{s.name} is core - everyone takes it, so it isn't an option")
    if r.next_year not in s.years:
        problems.append(f"{s.name} isn't taught in Year {r.next_year}")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM option_round_subjects WHERE round_id = ? AND "
                        "subject_id = ?", (r.round_id, s.subject_id)).fetchone():
            raise ValidationError([f"{s.name} is already offered"])
        conn.execute("INSERT INTO option_round_subjects (round_id, subject_id, guidance) "
                     "VALUES (?, ?, ?)",
                     (r.round_id, s.subject_id, P._clean_text(guidance_text, 1000)))
        _audit(conn, "subject_add", actor, round_id=r.round_id,
               detail={"subject": s.code})
    activity_log.record("options.subject_add", target=f"round:{r.round_id}", principal=actor)
    return s


def remove_round_subject(round_id: int, subject_id: int, *, actor: Principal) -> None:
    r = get_round(round_id)
    _require_editor(actor, "options.subject_remove", f"round:{r.round_id}")
    _editable(r)
    with database.connect() as conn:
        used = conn.execute("SELECT COUNT(*) FROM option_choices WHERE round_id = ? AND "
                            "subject_id = ?", (r.round_id, int(subject_id))).fetchone()[0]
        if used:
            raise ValidationError([f"{used} pupil(s) have chosen it - it can't be removed "
                                   "until their choices change"])
        conn.execute("DELETE FROM option_blocks WHERE round_id = ? AND subject_id = ?",
                     (r.round_id, int(subject_id)))
        n = conn.execute("DELETE FROM option_round_subjects WHERE round_id = ? AND "
                         "subject_id = ?", (r.round_id, int(subject_id))).rowcount
        if not n:
            raise NotFound("That subject isn't offered in this round")
        _audit(conn, "subject_remove", actor, round_id=r.round_id,
               detail={"subject_id": int(subject_id)})
    activity_log.record("options.subject_remove", target=f"round:{r.round_id}",
                        principal=actor)


# ── Rules ────────────────────────────────────────────────────────────

def list_rules(round_id: int) -> list[Rule]:
    with database.connect() as conn:
        return [Rule(r["rule_id"], r["round_id"], tuple(r["categories"].split("|")),
                     r["min_count"])
                for r in conn.execute("SELECT * FROM option_rules WHERE round_id = ? "
                                      "ORDER BY rule_id", (int(round_id),))]


def add_rule(round_id: int, categories: list[str] | str, min_count: Any = 1, *,
             actor: Principal) -> Rule:
    """E.g. at least 1 from Humanities or Languages (the subjects' EBacc categories)."""
    r = get_round(round_id)
    _require_editor(actor, "options.rule_add", f"round:{r.round_id}")
    _editable(r)
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.replace(",", "|").split("|")]
    cats = []
    problems: list[str] = []
    for c in categories:
        hit = next((x for x in S.EBACC_CATEGORIES if x.lower() == (c or "").lower()), None)
        if c and hit is None:
            problems.append(f"'{c}' isn't a category ({', '.join(S.EBACC_CATEGORIES)})")
        elif hit and hit not in cats:
            cats.append(hit)
    if not cats and not problems:
        problems.append("Choose at least one category")
    # One stored order, so "Languages, Humanities" is the same rule as
    # "Humanities, Languages" (the UNIQUE key compares the joined text).
    cats.sort(key=S.EBACC_CATEGORIES.index)
    n = _int(min_count, "At least", 1, r.choices_required, problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        try:
            rid = conn.execute("INSERT INTO option_rules (round_id, categories, min_count) "
                               "VALUES (?, ?, ?)", (r.round_id, "|".join(cats), n)).lastrowid
        except database.IntegrityError:
            raise ValidationError(["There's already a rule for those categories"]) from None
        _audit(conn, "rule_add", actor, round_id=r.round_id,
               detail={"categories": cats, "min": n})
    return next(x for x in list_rules(r.round_id) if x.rule_id == rid)


def remove_rule(rule_id: int, *, actor: Principal) -> None:
    with database.connect() as conn:
        row = conn.execute("SELECT round_id FROM option_rules WHERE rule_id = ?",
                           (int(rule_id),)).fetchone()
    if row is None:
        raise NotFound("No such rule")
    r = get_round(row[0])
    _require_editor(actor, "options.rule_remove", f"round:{r.round_id}")
    _editable(r)
    with database.connect() as conn:
        conn.execute("DELETE FROM option_rules WHERE rule_id = ?", (int(rule_id),))
        _audit(conn, "rule_remove", actor, round_id=r.round_id,
               detail={"rule_id": int(rule_id)})


def rule_problems(round_id: int, subject_ids: list[int]) -> list[str]:
    """Which rules the (primary) choices break."""
    subjects = {s.subject_id: s for s in list_round_subjects(round_id)}
    out = []
    for rule in list_rules(round_id):
        n = sum(1 for sid in subject_ids
                if sid in subjects and subjects[sid].ebacc_category in rule.categories)
        if n < rule.min_count:
            out.append(f"{rule.label} (has {n})")
    return out


# ── Pupils' choices ──────────────────────────────────────────────────

_CHOICES_SELECT = """
SELECT op.*, p.legal_last_name, p.legal_first_name, p.preferred_name, p.admission_no,
       p.form_group
FROM option_pupils op JOIN pupils p USING (pupil_id)
"""


def _pupil_choices(conn, r) -> PupilChoices:
    choices = tuple(Choice(c["subject_id"], c["code"], c["name"], c["rank"],
                           bool(c["is_reserve"]))
                    for c in conn.execute(
                        "SELECT c.*, s.code, s.name FROM option_choices c JOIN subjects s "
                        "USING (subject_id) WHERE c.round_id = ? AND c.pupil_id = ? ORDER BY "
                        "c.rank", (r["round_id"], r["pupil_id"])))
    first = r["preferred_name"] or r["legal_first_name"]
    return PupilChoices(r["round_id"], r["pupil_id"], f"{r['legal_last_name']}, {first}",
                        r["admission_no"], r["form_group"], r["submitted_at"],
                        r["submitted_by"], r["override_reason"], r["notes"], choices)


def get_choices(round_id: int, pupil_id: int) -> PupilChoices | None:
    with database.connect() as conn:
        r = conn.execute(_CHOICES_SELECT + " WHERE op.round_id = ? AND op.pupil_id = ?",
                         (int(round_id), int(pupil_id))).fetchone()
        return _pupil_choices(conn, r) if r else None


def list_choices(round_id: int, *, form_group: str | None = None) -> list[PupilChoices]:
    sql, params = _CHOICES_SELECT + " WHERE op.round_id = ?", [int(round_id)]
    if form_group:
        sql += " AND upper(p.form_group) = upper(?)"
        params.append(form_group)
    sql += " ORDER BY p.legal_last_name COLLATE NOCASE, p.legal_first_name COLLATE NOCASE"
    with database.connect() as conn:
        return [_pupil_choices(conn, r) for r in conn.execute(sql, params).fetchall()]


def cohort(round_id: int) -> list[P.Pupil]:
    """The pupils choosing: on roll in the round's year group."""
    return P.list_pupils(year_group=get_round(round_id).year_group)


def not_submitted(round_id: int) -> list[P.Pupil]:
    with database.connect() as conn:
        done = {x[0] for x in conn.execute("SELECT pupil_id FROM option_pupils WHERE "
                                           "round_id = ?", (int(round_id),))}
    return [p for p in cohort(round_id) if p.pupil_id not in done]


def submit_choices(round_id: int, pupil_id: int, choices: list[int],
                   reserves: list[int] | None = None, *, actor: Principal,
                   override_reason: str | None = None, notes: str | None = None
                   ) -> PupilChoices:
    """Replace a pupil's ranked choices (subject ids) and reserves (the old
    'Submit choices'). Breaking a rule needs the options lead and a reason.
    The pupil or a parent can also choose from their portal while the round
    is open."""
    r = get_round(round_id)
    if actor.is_staff:
        _require_staff(actor, "options.choices", f"round:{r.round_id}")
    else:
        # A pupil or parent choosing online from the portal: their own child only,
        # and only while the round is open, like any non-lead.
        from education_system.systems.secondary.modules.portals.domain import portal_accounts
        portal_accounts.require_pupil(actor, pupil_id)
    if r.status == "Finalised":
        raise ValidationError(["The round is finalised - choices can't change"])
    if not is_editor(actor):
        if r.status != "Open":
            raise ValidationError([f"The round is {r.status} - choices can only be entered "
                                   "while it's open (ask the options lead)"])
        if r.closes_on and _today().isoformat() > r.closes_on:
            raise ValidationError([f"Choices closed on {r.closes_on} - ask the options lead"])
    elif r.status == "Draft":
        raise ValidationError(["Open the round first"])
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound("No such pupil")
    problems = []
    if p.roll_status != "on_roll" or p.year_group != r.year_group:
        problems.append(f"{p.display_name} isn't in Year {r.year_group}")
    choices = [int(x) for x in (choices or [])]
    reserves = [int(x) for x in (reserves or [])]
    if len(choices) != r.choices_required:
        problems.append(f"Choose exactly {r.choices_required} subjects (got {len(choices)})")
    if len(reserves) != r.reserves_required:
        problems.append(f"Choose exactly {r.reserves_required} reserve(s) (got "
                        f"{len(reserves)})")
    picks = choices + reserves
    if len(set(picks)) != len(picks):
        problems.append("Each subject can only be chosen once")
    offered = {s.subject_id: s for s in list_round_subjects(r.round_id)}
    bad = [str(x) for x in picks if x not in offered]
    if bad:
        problems.append(f"Not offered in this round: subject(s) {', '.join(bad)}")
    if problems:
        raise ValidationError(problems)
    broken = rule_problems(r.round_id, choices)
    reason = P._clean_text(override_reason, 300)
    if broken:
        if not is_editor(actor):
            raise ValidationError(["The choices don't meet the round's rules:", *broken])
        if not reason:
            raise ValidationError(["The choices don't meet the round's rules - give a reason "
                                   "to accept them anyway:", *broken])
    else:
        reason = None
    with database.connect() as conn:
        had = conn.execute("SELECT 1 FROM option_pupils WHERE round_id = ? AND pupil_id = ?",
                           (r.round_id, p.pupil_id)).fetchone()
        conn.execute("DELETE FROM option_allocations WHERE round_id = ? AND pupil_id = ?",
                     (r.round_id, p.pupil_id))
        conn.execute("DELETE FROM option_choices WHERE round_id = ? AND pupil_id = ?",
                     (r.round_id, p.pupil_id))
        conn.execute(
            "INSERT INTO option_pupils (round_id, pupil_id, submitted_by, override_reason, "
            "notes) VALUES (?, ?, ?, ?, ?) ON CONFLICT (round_id, pupil_id) DO UPDATE SET "
            "submitted_at = datetime('now'), submitted_by = excluded.submitted_by, "
            "override_reason = excluded.override_reason, notes = COALESCE(excluded.notes, "
            "notes)", (r.round_id, p.pupil_id, actor.username, reason,
                       P._clean_text(notes, 1000)))
        conn.executemany(
            "INSERT INTO option_choices (round_id, pupil_id, subject_id, rank, is_reserve) "
            "VALUES (?, ?, ?, ?, ?)",
            [(r.round_id, p.pupil_id, sid, i, int(i > len(choices)))
             for i, sid in enumerate(picks, 1)])
        _audit(conn, "choices", actor, round_id=r.round_id, pupil_id=p.pupil_id,
               detail={"choices": [offered[x].code for x in choices],
                       "reserves": [offered[x].code for x in reserves],
                       "changed": bool(had), "override": bool(reason)})
    activity_log.record("options.choices", target=f"round:{r.round_id}", principal=actor)
    out = get_choices(r.round_id, p.pupil_id)
    assert out is not None
    return out


def clear_choices(round_id: int, pupil_id: int, *, actor: Principal) -> int:
    """The old 'Clear all'. Returns how many choices were removed."""
    r = get_round(round_id)
    _require_staff(actor, "options.choices_clear", f"round:{r.round_id}")
    _editable(r)
    if not is_editor(actor) and r.status != "Open":
        raise ValidationError(["Only the options lead can change choices now"])
    with database.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM option_choices WHERE round_id = ? AND "
                         "pupil_id = ?", (r.round_id, int(pupil_id))).fetchone()[0]
        conn.execute("DELETE FROM option_pupils WHERE round_id = ? AND pupil_id = ?",
                     (r.round_id, int(pupil_id)))
        if n:
            _audit(conn, "choices_clear", actor, round_id=r.round_id, pupil_id=int(pupil_id))
    activity_log.record("options.choices_clear", target=f"round:{r.round_id}",
                        principal=actor)
    return n


def summary(round_id: int) -> dict[str, Any]:
    """The old Summary: who has chosen, and each subject's first-choice and reserve
    demand (with places in the blocks)."""
    r = get_round(round_id)
    rows = list_choices(r.round_id)
    complete = sum(1 for x in rows if len(x.choices) == r.picks)
    places: Counter = Counter()
    for b in list_blocks(r.round_id):
        places[b["subject_id"]] += b["capacity"]
    primary: Counter = Counter(c.subject_id for x in rows for c in x.primary)
    reserve: Counter = Counter(c.subject_id for x in rows for c in x.reserves)
    first: Counter = Counter(x.primary[0].subject_id for x in rows if x.primary)
    picks = [{"subject_id": s.subject_id, "code": s.code, "name": s.name,
              "primary": primary[s.subject_id], "reserve": reserve[s.subject_id],
              "first": first[s.subject_id], "places": places.get(s.subject_id),
              "groups": math.ceil(primary[s.subject_id] / r.class_size)
              if primary[s.subject_id] else 0}
             for s in list_round_subjects(r.round_id)]
    return {"round": r, "cohort": len(cohort(r.round_id)), "pupils_submitted": len(rows),
            "pupils_complete": complete, "pupils_partial": len(rows) - complete,
            "overrides": sum(1 for x in rows if x.override_reason),
            "subject_picks": sorted(picks, key=lambda x: (-x["primary"], x["name"].lower()))}


def remind_families(round_id: int, *, actor: Principal, body: str | None = None):
    """E-mail the contacts of pupils who haven't chosen yet. Returns the outbox
    ``SendResult`` (run delivery next)."""
    r = get_round(round_id)
    _require_editor(actor, "options.remind", f"round:{r.round_id}")
    if r.status != "Open":
        raise ValidationError(["Reminders are for an open round"])
    missing = not_submitted(r.round_id)
    if not missing:
        raise ValidationError(["Every pupil has chosen"])
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    result = E.send_message(f"{r.name}: please return {{pupil_first_name}}'s option choices",
                            body or reminder_body(r),
                            E.Audience(kind="pupils", pupil_ids=[p.pupil_id for p in missing]),
                            actor=actor)
    with database.connect() as conn:
        _audit(conn, "remind", actor, round_id=r.round_id,
               detail={"pupils": len(missing), "message_id": result.message_id})
    return result


def reminder_body(r: Round) -> str:
    when = (f" by {_dt.date.fromisoformat(r.closes_on):%A %d %B}" if r.closes_on else "")
    return ("Dear {contact_name},\n\n"
            "We haven't yet received {pupil_first_name}'s option choices for "
            f"Year {r.next_year}. Please make sure they hand in their choices{when}: "
            f"{r.choices_required} subjects in order of preference"
            + (f" and {r.reserves_required} reserve(s)" if r.reserves_required else "")
            + ".\n\nIf you have any questions, please contact {pupil_first_name}'s tutor."
            "\n\nThank you.")


# ── Blocks ───────────────────────────────────────────────────────────

def list_blocks(round_id: int) -> list[dict[str, Any]]:
    """Each block's subjects: [{block, subject_id, code, name, capacity}]."""
    with database.connect() as conn:
        return [{"block": b["block"], "subject_id": b["subject_id"], "code": b["code"],
                 "name": b["name"], "capacity": b["capacity"]}
                for b in conn.execute(
                    "SELECT b.*, s.code, s.name FROM option_blocks b JOIN subjects s USING "
                    "(subject_id) WHERE b.round_id = ? ORDER BY b.block, s.name COLLATE NOCASE",
                    (int(round_id),))]


def set_blocks(round_id: int, blocks: dict[str, list[tuple[int, int | None]]], *,
               actor: Principal) -> list[dict[str, Any]]:
    """Replace the blocks: {"A": [(subject_id, capacity or None = class size)], ...}.
    Clears the automatic allocation (hand placements outside the new blocks too)."""
    r = get_round(round_id)
    _require_editor(actor, "options.blocks", f"round:{r.round_id}")
    _editable(r)
    offered = {s.subject_id: s for s in list_round_subjects(r.round_id)}
    problems: list[str] = []
    rows = []
    for name, entries in blocks.items():
        b = str(name).strip().upper()
        if b not in r.block_names:
            problems.append(f"Block {name} isn't one of {', '.join(r.block_names)}")
            continue
        seen = set()
        for sid, cap in entries:
            sid = int(sid)
            if sid not in offered:
                problems.append(f"Block {b}: subject {sid} isn't offered in this round")
                continue
            if sid in seen:
                problems.append(f"Block {b}: {offered[sid].code} is in it twice")
                continue
            seen.add(sid)
            size = _int(cap if cap not in (None, "") else r.class_size,
                        f"Block {b} {offered[sid].code} class size", 1, 40, problems)
            if size:
                rows.append((r.round_id, b, sid, size))
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("DELETE FROM option_blocks WHERE round_id = ?", (r.round_id,))
        conn.executemany("INSERT INTO option_blocks (round_id, block, subject_id, capacity) "
                         "VALUES (?, ?, ?, ?)", rows)
        conn.execute("DELETE FROM option_allocations WHERE round_id = ? AND (manual = 0 OR "
                     "NOT EXISTS (SELECT 1 FROM option_blocks b WHERE b.round_id = "
                     "option_allocations.round_id AND b.block = option_allocations.block AND "
                     "b.subject_id = option_allocations.subject_id))", (r.round_id,))
        _audit(conn, "blocks", actor, round_id=r.round_id, detail={"entries": len(rows)})
    activity_log.record("options.blocks", target=f"round:{r.round_id}", principal=actor)
    return list_blocks(r.round_id)


def suggest_blocks(round_id: int) -> dict[str, list[tuple[int, int]]]:
    """A block plan from the first choices: each subject gets enough classes for
    its demand, placed so subjects often chosen together are in different blocks
    and the blocks are even. Nothing is saved - pass it to :func:`set_blocks`."""
    r = get_round(round_id)
    rows = list_choices(r.round_id)
    demand: Counter = Counter()
    together: dict[tuple[int, int], int] = defaultdict(int)
    for x in rows:
        ids = [c.subject_id for c in x.primary]
        demand.update(ids)
        for a, b in combinations(sorted(ids), 2):
            together[(a, b)] += 1
    plan: dict[str, list[tuple[int, int]]] = {b: [] for b in r.block_names}
    slots = []
    for sid, n in demand.items():
        groups = math.ceil(n / r.class_size)
        if groups > len(plan):
            groups = len(plan)
        size = max(r.class_size, math.ceil(n / groups))   # room for reserves too
        slots += [(n, sid, min(40, size))] * groups
    slots.sort(key=lambda x: (-x[0], x[1]))

    def clash(block: str, sid: int) -> tuple[int, int, int]:
        here = [s for s, _c in plan[block]]
        if sid in here:
            return (1, 0, 0)
        return (0, sum(together[tuple(sorted((sid, s)))] for s in here),  # type: ignore[index]
                sum(c for _s, c in plan[block]))
    for _n, sid, size in slots:
        best = min(plan, key=lambda b: (*clash(b, sid), b))
        plan[best].append((sid, size))
    return _improve(plan, [[c.subject_id for c in x.primary] for x in rows])


def _fits(plan: dict[str, list[tuple[int, int]]], wanted: list[list[int]]) -> int:
    """How many pupils' choices go into different blocks (ignoring class sizes)."""
    where: dict[int, list[str]] = defaultdict(list)
    for b, items in plan.items():
        for sid, _size in items:
            where[sid].append(b)
    room = {(b, sid): 1 for b, items in plan.items() for sid, _size in items}
    return sum(1 for ids in wanted if _fit(ids, where, room) is not None)


def _improve(plan: dict[str, list[tuple[int, int]]], wanted: list[list[int]],
             passes: int = 3) -> dict[str, list[tuple[int, int]]]:
    """Move single classes to other blocks while that lets more pupils fit."""
    best = _fits(plan, wanted)
    for _ in range(passes):
        moved = False
        for b in list(plan):
            for item in list(plan[b]):
                for other in plan:
                    if other == b or any(sid == item[0] for sid, _s in plan[other]):
                        continue
                    plan[b].remove(item)
                    plan[other].append(item)
                    score = _fits(plan, wanted)
                    if score > best:
                        best, moved = score, True
                        break
                    plan[other].remove(item)
                    plan[b].append(item)
        if not moved:
            break
    return {b: sorted(items, key=lambda x: x[0]) for b, items in plan.items()}


def _fit(subjects: list[int], where: dict[int, list[str]], room: dict[tuple[str, int], int]
         ) -> dict[int, str] | None:
    """Give each subject a different block with room (bipartite matching)."""
    match: dict[str, int] = {}

    def place(sid: int, seen: set[str]) -> bool:
        for b in where.get(sid, []):
            if b in seen or room.get((b, sid), 0) <= 0:
                continue
            seen.add(b)
            if b not in match or place(match[b], seen):
                match[b] = sid
                return True
        return False
    for sid in subjects:
        if not place(sid, set()):
            return None
    return {sid: b for b, sid in match.items()}


def allocate(round_id: int, *, actor: Principal) -> dict[str, Any]:
    """Give every pupil who chose their subjects in the blocks, earliest choices
    first. A choice that can't fit (not in a free block, or full) is swapped for a
    reserve; hand placements are kept. Returns a report."""
    r = get_round(round_id)
    _require_editor(actor, "options.allocate", f"round:{r.round_id}")
    if r.status != "Closed":
        raise ValidationError(["Close the round before allocating subjects"])
    blocks = list_blocks(r.round_id)
    if not blocks:
        raise ValidationError(["Set up the option blocks first"])
    where: dict[int, list[str]] = defaultdict(list)
    room: dict[tuple[str, int], int] = {}
    for b in blocks:
        where[b["subject_id"]].append(b["block"])
        room[(b["block"], b["subject_id"])] = b["capacity"]
    with database.connect() as conn:
        manual: dict[int, list[tuple[str, int]]] = defaultdict(list)
        for a in conn.execute("SELECT pupil_id, block, subject_id FROM option_allocations "
                              "WHERE round_id = ? AND manual = 1", (r.round_id,)):
            manual[a[0]].append((a[1], a[2]))
            room[(a[1], a[2])] = room.get((a[1], a[2]), 0) - 1
        order = [x[0] for x in conn.execute(
            "SELECT pupil_id FROM option_pupils WHERE round_id = ? ORDER BY submitted_at, "
            "pupil_id", (r.round_id,))]
    by_id = {x.pupil_id: x for x in list_choices(r.round_id)}
    placed: dict[int, list[tuple[str, int, bool]]] = {}
    unresolved: list[dict[str, Any]] = []
    reserves_used = 0
    for pid in order:
        if pid in manual:
            continue
        x = by_id[pid]
        prim = [c.subject_id for c in x.primary]
        res = [c.subject_id for c in x.reserves]
        got = _fit(prim, where, room)
        used: set[int] = set()
        if got is None:
            for n in range(1, len(res) + 1):
                for drop in combinations(prim[::-1], n):
                    for add in combinations(res, n):
                        trial = [s for s in prim if s not in drop] + list(add)
                        got = _fit(trial, where, room)
                        if got is not None:
                            used = set(add)
                            break
                    if got is not None:
                        break
                if got is not None:
                    break
        if got is None:
            stuck = [c.code for c in x.primary if _fit([c.subject_id], where, room) is None]
            unresolved.append({"pupil_id": pid, "name": x.pupil_name,
                               "why": ("full or not in a block: " + ", ".join(stuck)) if stuck
                               else ("can't fit " + ", ".join(c.code for c in x.primary)
                                     + " into different blocks with room (reserves "
                                     "didn't help)")})
            continue
        for sid, b in got.items():
            room[(b, sid)] -= 1
        reserves_used += len(used)
        placed[pid] = [(b, sid, sid in used) for sid, b in got.items()]
    with database.connect() as conn:
        conn.execute("DELETE FROM option_allocations WHERE round_id = ? AND manual = 0",
                     (r.round_id,))
        conn.executemany(
            "INSERT INTO option_allocations (round_id, pupil_id, block, subject_id, "
            "from_reserve) VALUES (?, ?, ?, ?, ?)",
            [(r.round_id, pid, b, sid, int(rv)) for pid, items in placed.items()
             for b, sid, rv in items])
        _audit(conn, "allocate", actor, round_id=r.round_id,
               detail={"placed": len(placed), "unresolved": len(unresolved),
                       "reserves": reserves_used, "manual": len(manual)})
    activity_log.record("options.allocate", target=f"round:{r.round_id}", principal=actor,
                        placed=len(placed), unresolved=len(unresolved))
    return {"placed": len(placed), "manual": len(manual), "reserves_used": reserves_used,
            "unresolved": unresolved}


def allocations(round_id: int, pupil_id: int | None = None) -> list[Allocation]:
    sql = ("SELECT a.*, s.code, s.name FROM option_allocations a JOIN subjects s USING "
           "(subject_id) WHERE a.round_id = ?")
    params: list[Any] = [int(round_id)]
    if pupil_id is not None:
        sql += " AND a.pupil_id = ?"
        params.append(int(pupil_id))
    with database.connect() as conn:
        return [Allocation(a["pupil_id"], a["block"], a["subject_id"], a["code"], a["name"],
                           bool(a["from_reserve"]), bool(a["manual"]))
                for a in conn.execute(sql + " ORDER BY a.pupil_id, a.block", params)]


def allocation_status(round_id: int) -> dict[str, Any]:
    """Who has subjects, who doesn't, and how full each block class is."""
    r = get_round(round_id)
    alloc: dict[int, list[Allocation]] = defaultdict(list)
    for a in allocations(r.round_id):
        alloc[a.pupil_id].append(a)
    rows = list_choices(r.round_id)
    unresolved = [x for x in rows if len(alloc.get(x.pupil_id, [])) < r.choices_required]
    stuck = {x.pupil_id for x in unresolved}
    fill: Counter = Counter((a.block, a.subject_id) for items in alloc.values() for a in items)
    classes = [{**b, "pupils": fill[(b["block"], b["subject_id"])]}
               for b in list_blocks(r.round_id)]
    first_choice = sum(1 for x in rows if alloc.get(x.pupil_id)
                       and not any(a.from_reserve for a in alloc[x.pupil_id]))
    return {"allocated": sum(1 for x in rows if x.pupil_id not in stuck),
            "unresolved": unresolved,
            "all_first_choices": first_choice, "classes": classes}


def place_by_hand(round_id: int, pupil_id: int, placements: dict[str, int], *,
                  actor: Principal) -> tuple[list[Allocation], list[str]]:
    """The options lead places a pupil: {block: subject_id}. Returns (allocation,
    warnings) - a full class is a warning, not an error."""
    r = get_round(round_id)
    _require_editor(actor, "options.allocate_manual", f"round:{r.round_id}")
    if r.status != "Closed":
        raise ValidationError(["Pupils are placed while the round is closed"])
    x = get_choices(r.round_id, pupil_id)
    if x is None:
        raise ValidationError(["The pupil hasn't chosen yet - enter their choices first"])
    blocks = {(b["block"], b["subject_id"]): b for b in list_blocks(r.round_id)}
    problems, warnings = [], []
    clean = {str(b).strip().upper(): int(s) for b, s in placements.items() if s not in
             (None, "")}
    if len(clean) != r.choices_required:
        problems.append(f"Place them in {r.choices_required} subjects (got {len(clean)})")
    if len(set(clean.values())) != len(clean):
        problems.append("A subject can only be taken once")
    status = allocation_status(r.round_id)
    fill = {(c["block"], c["subject_id"]): c["pupils"] for c in status["classes"]}
    mine = {(a.block, a.subject_id) for a in allocations(r.round_id, pupil_id)}
    chosen = {c.subject_id for c in x.choices}
    for b, sid in clean.items():
        cls = blocks.get((b, sid))
        if cls is None:
            try:
                label = S.get(sid).code
            except S.NotFound:
                label = f"subject {sid}"
            problems.append(f"{label} doesn't run in block {b}")
            continue
        if (b, sid) not in mine and fill.get((b, sid), 0) >= cls["capacity"]:
            warnings.append(f"{cls['code']} in block {b} is full ({cls['capacity']}) - over "
                            "the class size")
        if sid not in chosen:
            warnings.append(f"{x.pupil_name.split(', ')[-1]} didn't choose {cls['code']}")
    if problems:
        raise ValidationError(problems)
    reserves = {c.subject_id for c in x.reserves}
    with database.connect() as conn:
        conn.execute("DELETE FROM option_allocations WHERE round_id = ? AND pupil_id = ?",
                     (r.round_id, x.pupil_id))
        conn.executemany(
            "INSERT INTO option_allocations (round_id, pupil_id, block, subject_id, "
            "from_reserve, manual) VALUES (?, ?, ?, ?, ?, 1)",
            [(r.round_id, x.pupil_id, b, sid, int(sid in reserves)) for b, sid in clean.items()])
        _audit(conn, "allocate_manual", actor, round_id=r.round_id, pupil_id=x.pupil_id,
               detail={b: blocks[(b, s)]["code"] for b, s in clean.items()})
    activity_log.record("options.allocate_manual", target=f"round:{r.round_id}",
                        principal=actor)
    return allocations(r.round_id, x.pupil_id), warnings


# ── After finalising ─────────────────────────────────────────────────

def results_text(r: Round, x: PupilChoices, items: list[Allocation]) -> str:
    core = ", ".join(s.name for s in S.list_subjects() if s.is_core and s.is_active
                     and r.next_year in s.years)
    lines = ["Dear {contact_name},", "",
             f"Here are {{pupil_first_name}}'s subjects for Year {r.next_year}:", ""]
    lines += [f"  Block {a.block}: {a.name}" + (" (a reserve choice)" if a.from_reserve
                                               else "") for a in items]
    if core:
        lines += ["", f"Everyone also studies: {core}."]
    if any(a.from_reserve for a in items):
        lines += ["", "We weren't able to offer every first choice, so a reserve subject has "
                  "been used. Please contact the school if you'd like to discuss this."]
    lines += ["", "Thank you."]
    return "\n".join(lines)


def email_results(round_id: int, *, actor: Principal) -> tuple[list[int], list[str]]:
    """E-mail each family their child's subjects. Returns (message ids, names of
    pupils with no contact e-mail)."""
    r = get_round(round_id)
    _require_editor(actor, "options.results", f"round:{r.round_id}")
    if r.status != "Finalised":
        raise ValidationError(["Finalise the round first"])
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    alloc: dict[int, list[Allocation]] = defaultdict(list)
    for a in allocations(r.round_id):
        alloc[a.pupil_id].append(a)
    rows = [x for x in list_choices(r.round_id) if alloc.get(x.pupil_id)]
    contacts = C.emailable_for_pupils([x.pupil_id for x in rows])
    ids, no_email = [], []
    for x in rows:
        people = contacts.get(x.pupil_id) or []
        if not people:
            no_email.append(x.pupil_name)
            continue
        pupil = P.get_pupil(x.pupil_id)
        for c in people:
            text = results_text(r, x, alloc[x.pupil_id]).replace(
                "{contact_name}", c.full_name).replace(
                "{pupil_first_name}", (pupil.preferred_name or pupil.legal_first_name)
                if pupil else "your child")
            ids.append(E.send_to_address(c.email or "", c.full_name,
                                         f"{r.name}: Year {r.next_year} subjects", text,
                                         actor=actor, kind="options_results",
                                         label=f"options:{r.round_id}", pupil=pupil))
    with database.connect() as conn:
        _audit(conn, "results", actor, round_id=r.round_id,
               detail={"messages": len(ids), "no_email": len(no_email)})
    return ids, no_email


def group_code(r: Round, block: str, subject: S.Subject) -> str:
    return f"{r.next_year}{block}/{subject.code}"


def create_groups(round_id: int, *, actor: Principal) -> dict[str, Any]:
    """After the year rollover: each block's subjects become Year 10 option
    teaching groups with their pupils. Run it again to add anyone missing."""
    from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
    r = get_round(round_id)
    _require_editor(actor, "options.groups", f"round:{r.round_id}")
    if r.status != "Finalised":
        raise ValidationError(["Finalise the round first"])
    alloc = allocations(r.round_id)
    pupils = {pid: P.get_pupil(pid) for pid in {a.pupil_id for a in alloc}}
    if not any(p and p.year_group == r.next_year for p in pupils.values()):
        raise ValidationError([f"These pupils aren't in Year {r.next_year} yet - run this "
                               "after the year rollover"])
    by_class: dict[tuple[str, int], list[int]] = defaultdict(list)
    for a in alloc:
        by_class[(a.block, a.subject_id)].append(a.pupil_id)
    caps = {(b["block"], b["subject_id"]): b["capacity"] for b in list_blocks(r.round_id)}
    created, added, refused = [], 0, []
    for (block, sid), ids in sorted(by_class.items()):
        subject = S.get(sid)
        code = group_code(r, block, subject)
        g = TG.find(code)
        if g is None:
            g = TG.create({"code": code, "subject_id": sid, "year_group": r.next_year,
                           "kind": "Option", "capacity": max(caps.get((block, sid), 0),
                                                             len(ids)),
                           "notes": f"Option block {block} from {r.name}"}, actor=actor)
            created.append(code)
        ok, no = TG.add_pupils(ids, g.group_id, actor=actor, allow_over_capacity=True)
        added += len(ok)
        refused += [(code, adm, why) for adm, why in no if why != f"already in {g.code}"]
    with database.connect() as conn:
        _audit(conn, "groups", actor, round_id=r.round_id,
               detail={"created": len(created), "added": added, "refused": len(refused)})
    return {"created": created, "added": added, "refused": refused}


# ── Export ───────────────────────────────────────────────────────────

def export_choices(round_id: int, path: str | Path, *, actor: Principal) -> int:
    """Every pupil's choices and allocation as CSV. Returns the number of pupils."""
    r = get_round(round_id)
    _require_staff(actor, "options.export", f"round:{r.round_id}")
    alloc: dict[int, dict[str, str]] = defaultdict(dict)
    for a in allocations(r.round_id):
        alloc[a.pupil_id][a.block] = a.code
    rows = list_choices(r.round_id)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Admission no", "Pupil", "Form",
                    *[f"Choice {i}" for i in range(1, r.choices_required + 1)],
                    *[f"Reserve {i}" for i in range(1, r.reserves_required + 1)],
                    *[f"Block {b}" for b in r.block_names], "Rules accepted because",
                    "Entered by", "Entered"])
        for x in rows:
            prim = [c.code for c in x.primary] + [""] * r.choices_required
            res = [c.code for c in x.reserves] + [""] * r.reserves_required
            w.writerow([_safe(v) for v in (
                x.admission_no, x.pupil_name, x.form_group,
                *prim[:r.choices_required], *res[:r.reserves_required],
                *[alloc[x.pupil_id].get(b, "") for b in r.block_names], x.override_reason,
                x.submitted_by, x.submitted_at)])
    activity_log.record("options.export", target=f"round:{r.round_id}", principal=actor,
                        rows=len(rows))
    return len(rows)


def for_pupil(pupil_id: int) -> list[tuple[Round, PupilChoices, list[Allocation]]]:
    """A pupil's options in every round (for their profile)."""
    with database.connect() as conn:
        rids = [x[0] for x in conn.execute("SELECT round_id FROM option_pupils WHERE "
                                           "pupil_id = ? ORDER BY round_id DESC",
                                           (int(pupil_id),))]
    out = []
    for rid in rids:
        x = get_choices(rid, pupil_id)
        if x:
            out.append((get_round(rid), x, allocations(rid, pupil_id)))
    return out


S.register_usage("option_round_subjects", "subject_id", "options round subject(s)")
S.register_usage("option_choices", "subject_id", "pupils' option choice(s)")
S.register_usage("option_blocks", "subject_id", "option block place(s)")
S.register_usage("option_allocations", "subject_id", "option allocation(s)")
