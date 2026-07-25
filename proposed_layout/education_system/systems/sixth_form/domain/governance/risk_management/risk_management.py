"""Risk Management for the Sixth Form System.

A pragmatic risk register:

* ``risks`` — the register itself. Each risk has an inherent score
  (``likelihood × impact``, 1..5 each) and a residual score after
  controls; a ``treatment`` decision (tolerate / treat / transfer /
  terminate) and a review cadence.
* ``risk_actions`` — mitigation actions / treatments linked to a
  risk, with owner, due date and completion state.
* ``risk_reviews`` — periodic review log; an entry can carry a
  refreshed L/I score and a status change.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.RISK_MANAGEMENT_DB

# ── Vocabularies ──────────────────────────────────────────────────

CATEGORIES: tuple[str, ...] = (
    "Strategic", "Operational", "Financial", "Compliance",
    "Safeguarding", "Health & Safety", "IT / Cyber",
    "Reputational", "People / HR", "Estates",
    "Curriculum", "Other",
)
DEFAULT_CATEGORY: str = "Operational"

STATUSES: tuple[str, ...] = (
    "Identified", "Mitigating", "Monitoring",
    "Accepted", "Transferred", "Closed",
)
DEFAULT_STATUS: str = "Identified"
OPEN_STATUSES: tuple[str, ...] = (
    "Identified", "Mitigating", "Monitoring",
)

TREATMENTS: tuple[str, ...] = (
    "Tolerate", "Treat", "Transfer", "Terminate",
)
DEFAULT_TREATMENT: str = "Treat"

ACTION_STATUSES: tuple[str, ...] = (
    "Planned", "In Progress", "Done", "Cancelled", "Overdue",
)
DEFAULT_ACTION_STATUS: str = "Planned"

LIKELIHOOD_LABELS: dict[int, str] = {
    1: "Rare", 2: "Unlikely", 3: "Possible",
    4: "Likely", 5: "Almost Certain",
}
IMPACT_LABELS: dict[int, str] = {
    1: "Negligible", 2: "Minor", 3: "Moderate",
    4: "Major", 5: "Severe",
}
SCORE_BANDS: tuple[tuple[int, int, str], ...] = (
    # (min_inclusive, max_inclusive, label)
    (1, 4, "Low"),
    (5, 9, "Medium"),
    (10, 14, "High"),
    (15, 25, "Critical"),
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── DB plumbing ───────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS risks (
    risk_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    category         TEXT NOT NULL DEFAULT 'Operational',
    description      TEXT,
    owner            TEXT,
    identified_date  TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'Identified',
    likelihood       INTEGER NOT NULL DEFAULT 3 CHECK(likelihood BETWEEN 1 AND 5),
    impact           INTEGER NOT NULL DEFAULT 3 CHECK(impact BETWEEN 1 AND 5),
    controls         TEXT,
    residual_likelihood INTEGER CHECK(residual_likelihood IS NULL
                                       OR residual_likelihood BETWEEN 1 AND 5),
    residual_impact     INTEGER CHECK(residual_impact IS NULL
                                       OR residual_impact BETWEEN 1 AND 5),
    treatment        TEXT NOT NULL DEFAULT 'Treat',
    review_frequency_days INTEGER NOT NULL DEFAULT 90,
    last_reviewed    TEXT,
    next_review      TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS risk_actions (
    action_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    risk_id      INTEGER NOT NULL,
    description  TEXT NOT NULL,
    owner        TEXT,
    due_date     TEXT,
    status       TEXT NOT NULL DEFAULT 'Planned',
    completed_date TEXT,
    evidence     TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (risk_id) REFERENCES risks(risk_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS risk_reviews (
    review_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    risk_id      INTEGER NOT NULL,
    review_date  TEXT NOT NULL,
    reviewer     TEXT,
    summary      TEXT,
    new_likelihood INTEGER CHECK(new_likelihood IS NULL
                                  OR new_likelihood BETWEEN 1 AND 5),
    new_impact     INTEGER CHECK(new_impact IS NULL
                                  OR new_impact BETWEEN 1 AND 5),
    new_status   TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (risk_id) REFERENCES risks(risk_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_risks_status    ON risks(status);
CREATE INDEX IF NOT EXISTS idx_risks_category  ON risks(category);
CREATE INDEX IF NOT EXISTS idx_risks_next_rev  ON risks(next_review);
CREATE INDEX IF NOT EXISTS idx_act_risk        ON risk_actions(risk_id);
CREATE INDEX IF NOT EXISTS idx_act_status      ON risk_actions(status);
CREATE INDEX IF NOT EXISTS idx_act_due         ON risk_actions(due_date);
CREATE INDEX IF NOT EXISTS idx_rev_risk        ON risk_reviews(risk_id);
CREATE INDEX IF NOT EXISTS idx_rev_date        ON risk_reviews(review_date DESC);
"""


def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Risk-management schema ready at %s", DB_PATH)

    _DB_READY = True


# ── Types ─────────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def score_band(score: int | None) -> str:
    if score is None:
        return "—"
    for lo, hi, label in SCORE_BANDS:
        if lo <= score <= hi:
            return label
    return "—"


@dataclass
class Risk:
    risk_id: int
    title: str
    category: str
    description: str | None
    owner: str | None
    identified_date: str
    status: str
    likelihood: int
    impact: int
    controls: str | None
    residual_likelihood: int | None
    residual_impact: int | None
    treatment: str
    review_frequency_days: int
    last_reviewed: str | None
    next_review: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def inherent_score(self) -> int:
        return int(self.likelihood) * int(self.impact)

    @property
    def residual_score(self) -> int | None:
        if (self.residual_likelihood is None
                or self.residual_impact is None):
            return None
        return int(self.residual_likelihood) * int(
            self.residual_impact)

    @property
    def inherent_band(self) -> str:
        return score_band(self.inherent_score)

    @property
    def residual_band(self) -> str:
        return score_band(self.residual_score)

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def is_review_due(self) -> bool:
        if not self.next_review:
            return False
        try:
            return _dt.date.fromisoformat(self.next_review) \
                <= _dt.date.today()
        except ValueError:
            return False


@dataclass
class Action:
    action_id: int
    risk_id: int
    description: str
    owner: str | None
    due_date: str | None
    status: str
    completed_date: str | None
    evidence: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_done(self) -> bool:
        return self.status in ("Done", "Cancelled")

    @property
    def is_overdue(self) -> bool:
        if self.is_done or not self.due_date:
            return False
        try:
            return _dt.date.fromisoformat(self.due_date) \
                < _dt.date.today()
        except ValueError:
            return False


@dataclass
class Review:
    review_id: int
    risk_id: int
    review_date: str
    reviewer: str | None
    summary: str | None
    new_likelihood: int | None
    new_impact: int | None
    new_status: str | None
    notes: str | None
    created_at: str


# ── Validation helpers ────────────────────────────────────────────

def _today() -> str:
    return _dt.date.today().isoformat()


def _require(v: Any, label: str) -> Any:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"{label} is required")
    return v


def _validate_date(v: Any, label: str, *,
                    required: bool = False) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(v).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_int_range(v: Any, label: str, *,
                          lo: int, hi: int,
                          required: bool = True,
                          default: int | None = None) -> int | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if not required:
            return default
        raise ValidationError(f"{label} is required ({lo}..{hi})")
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ValidationError(
            f"{label} must be a whole number {lo}..{hi}") from None
    if not (lo <= n <= hi):
        raise ValidationError(f"{label} must be {lo}..{hi}")
    return n


def _validate_in(v: Any, options: tuple[str, ...], label: str,
                  *, default: str | None = None,
                  required: bool = True) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if default is not None:
            return default
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(v).strip()
    if s not in options:
        raise ValidationError(
            f"{label} must be one of: {', '.join(options)}")
    return s


# ── Risk CRUD ─────────────────────────────────────────────────────

def _row_risk(r: sqlite3.Row) -> Risk:
    return Risk(
        risk_id=r["risk_id"], title=r["title"],
        category=r["category"], description=r["description"],
        owner=r["owner"], identified_date=r["identified_date"],
        status=r["status"], likelihood=r["likelihood"],
        impact=r["impact"], controls=r["controls"],
        residual_likelihood=r["residual_likelihood"],
        residual_impact=r["residual_impact"],
        treatment=r["treatment"],
        review_frequency_days=r["review_frequency_days"],
        last_reviewed=r["last_reviewed"],
        next_review=r["next_review"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _compute_next_review(last: str | None,
                          freq_days: int) -> str | None:
    base_s = last or _today()
    try:
        base = _dt.date.fromisoformat(base_s)
    except ValueError:
        base = _dt.date.today()
    return (base + _dt.timedelta(days=max(1, freq_days))).isoformat()


def _validate_risk(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["title"] = str(_require(d.get("title"), "Title")).strip()
    out["category"] = _validate_in(
        d.get("category"), CATEGORIES, "Category",
        default=DEFAULT_CATEGORY)
    out["description"] = (d.get("description") or "").strip() or None
    out["owner"] = (d.get("owner") or "").strip() or None
    out["identified_date"] = _validate_date(
        d.get("identified_date") or _today(),
        "Identified date", required=True)
    out["status"] = _validate_in(
        d.get("status"), STATUSES, "Status",
        default=DEFAULT_STATUS)
    out["likelihood"] = _validate_int_range(
        d.get("likelihood"), "Likelihood", lo=1, hi=5,
        required=False, default=3) or 3
    out["impact"] = _validate_int_range(
        d.get("impact"), "Impact", lo=1, hi=5,
        required=False, default=3) or 3
    out["controls"] = (d.get("controls") or "").strip() or None
    out["residual_likelihood"] = _validate_int_range(
        d.get("residual_likelihood"), "Residual likelihood",
        lo=1, hi=5, required=False, default=None)
    out["residual_impact"] = _validate_int_range(
        d.get("residual_impact"), "Residual impact",
        lo=1, hi=5, required=False, default=None)
    out["treatment"] = _validate_in(
        d.get("treatment"), TREATMENTS, "Treatment",
        default=DEFAULT_TREATMENT)
    freq = _validate_int_range(
        d.get("review_frequency_days"),
        "Review frequency (days)", lo=1, hi=3650,
        required=False, default=90) or 90
    out["review_frequency_days"] = freq
    out["last_reviewed"] = _validate_date(
        d.get("last_reviewed"), "Last reviewed")
    nr_in = d.get("next_review")
    if nr_in in (None, "") or (isinstance(nr_in, str)
                                  and not nr_in.strip()):
        out["next_review"] = _compute_next_review(
            out["last_reviewed"] or out["identified_date"], freq)
    else:
        out["next_review"] = _validate_date(nr_in, "Next review")
    out["notes"] = (d.get("notes") or "").strip() or None
    # Closed risks should not have residuals lower than 1×1 — no-op.
    if out["status"] == "Closed" and out["residual_likelihood"] is None:
        # Allow but unusual; leave for review.
        pass
    return out


def create_risk(d: dict[str, Any]) -> Risk:
    init_db()
    p = _validate_risk(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO risks (
                  title, category, description, owner,
                  identified_date, status, likelihood, impact,
                  controls, residual_likelihood, residual_impact,
                  treatment, review_frequency_days,
                  last_reviewed, next_review, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?)""",
            (p["title"], p["category"], p["description"], p["owner"],
             p["identified_date"], p["status"], p["likelihood"],
             p["impact"], p["controls"],
             p["residual_likelihood"], p["residual_impact"],
             p["treatment"], p["review_frequency_days"],
             p["last_reviewed"], p["next_review"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_risk(new_id)
    assert out is not None
    logger.info(
        "Created risk #%d (%s, L=%d I=%d score=%d, status=%s)",
        new_id, p["title"], p["likelihood"], p["impact"],
        p["likelihood"] * p["impact"], p["status"])
    return out


def get_risk(risk_id: int) -> Risk | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM risks WHERE risk_id = ?",
            (risk_id,)).fetchone()
    return _row_risk(r) if r else None


def list_risks(
    *,
    status: str | None = None,
    category: str | None = None,
    owner: str | None = None,
    open_only: bool = False,
    review_due_only: bool = False,
    min_score: int | None = None,
    search: str | None = None,
) -> list[Risk]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if status:
        clauses.append("status = ?")
        args.append(status)
    if category:
        clauses.append("category = ?")
        args.append(category)
    if owner:
        clauses.append("owner LIKE ?")
        args.append(f"%{owner.strip()}%")
    if open_only:
        ph = ",".join("?" * len(OPEN_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_STATUSES)
    if min_score is not None:
        clauses.append("(likelihood * impact) >= ?")
        args.append(int(min_score))
    if search:
        like = f"%{search.strip()}%"
        clauses.append(
            "(title LIKE ? OR description LIKE ? "
            "OR controls LIKE ? OR notes LIKE ?)")
        args.extend([like, like, like, like])
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    sql = (f"SELECT * FROM risks {where} "
           "ORDER BY (likelihood * impact) DESC, "
           "next_review ASC, risk_id DESC")
    with _connect() as conn:
        rows = [_row_risk(r)
                for r in conn.execute(sql, args).fetchall()]
    if review_due_only:
        rows = [r for r in rows if r.is_review_due]
    return rows


def update_risk(risk_id: int, d: dict[str, Any]) -> Risk:
    init_db()
    existing = get_risk(risk_id)
    if existing is None:
        raise ValidationError(f"No risk #{risk_id}")
    merged: dict[str, Any] = {
        "title":           d.get("title",           existing.title),
        "category":        d.get("category",        existing.category),
        "description":     d.get("description",
                                   existing.description),
        "owner":           d.get("owner",           existing.owner),
        "identified_date": d.get("identified_date",
                                   existing.identified_date),
        "status":          d.get("status",          existing.status),
        "likelihood":      d.get("likelihood",      existing.likelihood),
        "impact":          d.get("impact",          existing.impact),
        "controls":        d.get("controls",        existing.controls),
        "residual_likelihood": d.get("residual_likelihood",
                                       existing.residual_likelihood),
        "residual_impact": d.get("residual_impact",
                                   existing.residual_impact),
        "treatment":       d.get("treatment",       existing.treatment),
        "review_frequency_days": d.get(
            "review_frequency_days",
            existing.review_frequency_days),
        "last_reviewed":   d.get("last_reviewed",
                                   existing.last_reviewed),
        "next_review":     d.get("next_review",
                                   existing.next_review),
        "notes":           d.get("notes",           existing.notes),
    }
    p = _validate_risk(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE risks SET
                  title=?, category=?, description=?, owner=?,
                  identified_date=?, status=?, likelihood=?, impact=?,
                  controls=?, residual_likelihood=?, residual_impact=?,
                  treatment=?, review_frequency_days=?,
                  last_reviewed=?, next_review=?, notes=?,
                  updated_at=datetime('now')
               WHERE risk_id=?""",
            (p["title"], p["category"], p["description"], p["owner"],
             p["identified_date"], p["status"], p["likelihood"],
             p["impact"], p["controls"], p["residual_likelihood"],
             p["residual_impact"], p["treatment"],
             p["review_frequency_days"], p["last_reviewed"],
             p["next_review"], p["notes"], risk_id),
        )
        conn.commit()
    out = get_risk(risk_id)
    assert out is not None
    logger.info("Updated risk #%d (status=%s, score=%d)",
                risk_id, out.status, out.inherent_score)
    return out


def delete_risk(risk_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM risks WHERE risk_id = ?", (risk_id,))
        conn.commit()
    if cur.rowcount:
        logger.info("Deleted risk #%d", risk_id)
        return True
    return False


# ── Action CRUD ───────────────────────────────────────────────────

def _row_action(r: sqlite3.Row) -> Action:
    return Action(
        action_id=r["action_id"], risk_id=r["risk_id"],
        description=r["description"], owner=r["owner"],
        due_date=r["due_date"], status=r["status"],
        completed_date=r["completed_date"],
        evidence=r["evidence"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_action(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["description"] = str(
        _require(d.get("description"), "Description")).strip()
    out["owner"] = (d.get("owner") or "").strip() or None
    out["due_date"] = _validate_date(d.get("due_date"), "Due date")
    out["status"] = _validate_in(
        d.get("status"), ACTION_STATUSES, "Status",
        default=DEFAULT_ACTION_STATUS)
    out["completed_date"] = _validate_date(
        d.get("completed_date"), "Completed date")
    out["evidence"] = (d.get("evidence") or "").strip() or None
    out["notes"] = (d.get("notes") or "").strip() or None
    if out["status"] == "Done" and not out["completed_date"]:
        out["completed_date"] = _today()
    return out


def add_action(risk_id: int, d: dict[str, Any]) -> Action:
    init_db()
    if get_risk(risk_id) is None:
        raise ValidationError(f"No risk #{risk_id}")
    p = _validate_action(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO risk_actions (
                  risk_id, description, owner, due_date, status,
                  completed_date, evidence, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (risk_id, p["description"], p["owner"], p["due_date"],
             p["status"], p["completed_date"], p["evidence"],
             p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_action(new_id)
    assert out is not None
    logger.info("Added risk action #%d on risk #%d",
                new_id, risk_id)
    return out


def get_action(action_id: int) -> Action | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM risk_actions WHERE action_id = ?",
            (action_id,)).fetchone()
    return _row_action(r) if r else None


def list_actions(*, risk_id: int | None = None,
                   status: str | None = None,
                   open_only: bool = False,
                   overdue_only: bool = False) -> list[Action]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if risk_id is not None:
        clauses.append("risk_id = ?")
        args.append(risk_id)
    if status:
        clauses.append("status = ?")
        args.append(status)
    if open_only:
        clauses.append("status NOT IN ('Done', 'Cancelled')")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    sql = (f"SELECT * FROM risk_actions {where} "
           "ORDER BY due_date ASC NULLS LAST, action_id DESC")
    # sqlite supports `NULLS LAST` from 3.30+. Wrap with a fallback.
    try:
        with _connect() as conn:
            rows = [_row_action(r)
                    for r in conn.execute(sql, args).fetchall()]
    except sqlite3.OperationalError:
        sql = (f"SELECT * FROM risk_actions {where} "
               "ORDER BY CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,"
               " due_date ASC, action_id DESC")
        with _connect() as conn:
            rows = [_row_action(r)
                    for r in conn.execute(sql, args).fetchall()]
    if overdue_only:
        rows = [r for r in rows if r.is_overdue]
    return rows


def update_action(action_id: int, d: dict[str, Any]) -> Action:
    init_db()
    existing = get_action(action_id)
    if existing is None:
        raise ValidationError(f"No action #{action_id}")
    merged = {
        "description":    d.get("description",    existing.description),
        "owner":          d.get("owner",          existing.owner),
        "due_date":       d.get("due_date",       existing.due_date),
        "status":         d.get("status",         existing.status),
        "completed_date": d.get("completed_date",
                                  existing.completed_date),
        "evidence":       d.get("evidence",       existing.evidence),
        "notes":          d.get("notes",          existing.notes),
    }
    p = _validate_action(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE risk_actions SET
                  description=?, owner=?, due_date=?, status=?,
                  completed_date=?, evidence=?, notes=?,
                  updated_at=datetime('now')
               WHERE action_id=?""",
            (p["description"], p["owner"], p["due_date"],
             p["status"], p["completed_date"], p["evidence"],
             p["notes"], action_id),
        )
        conn.commit()
    out = get_action(action_id)
    assert out is not None
    logger.info("Updated risk action #%d (status=%s)",
                action_id, out.status)
    return out


def delete_action(action_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM risk_actions WHERE action_id = ?",
            (action_id,))
        conn.commit()
    if cur.rowcount:
        logger.info("Deleted risk action #%d", action_id)
        return True
    return False


# ── Review CRUD ───────────────────────────────────────────────────

def _row_review(r: sqlite3.Row) -> Review:
    return Review(
        review_id=r["review_id"], risk_id=r["risk_id"],
        review_date=r["review_date"], reviewer=r["reviewer"],
        summary=r["summary"], new_likelihood=r["new_likelihood"],
        new_impact=r["new_impact"], new_status=r["new_status"],
        notes=r["notes"], created_at=r["created_at"],
    )


def _validate_review(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["review_date"] = _validate_date(
        d.get("review_date") or _today(),
        "Review date", required=True)
    out["reviewer"] = (d.get("reviewer") or "").strip() or None
    out["summary"] = (d.get("summary") or "").strip() or None
    out["new_likelihood"] = _validate_int_range(
        d.get("new_likelihood"), "New likelihood",
        lo=1, hi=5, required=False, default=None)
    out["new_impact"] = _validate_int_range(
        d.get("new_impact"), "New impact",
        lo=1, hi=5, required=False, default=None)
    out["new_status"] = _validate_in(
        d.get("new_status"), STATUSES, "New status",
        required=False)
    out["notes"] = (d.get("notes") or "").strip() or None
    return out


def add_review(risk_id: int, d: dict[str, Any]) -> Review:
    init_db()
    risk = get_risk(risk_id)
    if risk is None:
        raise ValidationError(f"No risk #{risk_id}")
    p = _validate_review(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO risk_reviews (
                  risk_id, review_date, reviewer, summary,
                  new_likelihood, new_impact, new_status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (risk_id, p["review_date"], p["reviewer"], p["summary"],
             p["new_likelihood"], p["new_impact"],
             p["new_status"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid

    # Roll fields on the risk forward.
    updates: dict[str, Any] = {
        "last_reviewed": p["review_date"],
        # Recompute next review from this date.
        "next_review": _compute_next_review(
            p["review_date"], risk.review_frequency_days),
    }
    if p["new_likelihood"] is not None:
        updates["likelihood"] = p["new_likelihood"]
    if p["new_impact"] is not None:
        updates["impact"] = p["new_impact"]
    if p["new_status"]:
        updates["status"] = p["new_status"]
    update_risk(risk_id, updates)

    out = get_review(new_id)
    assert out is not None
    logger.info("Added review #%d on risk #%d", new_id, risk_id)
    return out


def get_review(review_id: int) -> Review | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM risk_reviews WHERE review_id = ?",
            (review_id,)).fetchone()
    return _row_review(r) if r else None


def list_reviews(*, risk_id: int | None = None,
                   limit: int = 200) -> list[Review]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if risk_id is not None:
        clauses.append("risk_id = ?")
        args.append(risk_id)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    sql = (f"SELECT * FROM risk_reviews {where} "
           f"ORDER BY review_date DESC, review_id DESC "
           f"LIMIT {int(limit)}")
    with _connect() as conn:
        return [_row_review(r)
                for r in conn.execute(sql, args).fetchall()]


def delete_review(review_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM risk_reviews WHERE review_id = ?",
            (review_id,))
        conn.commit()
    if cur.rowcount:
        logger.info("Deleted review #%d", review_id)
        return True
    return False


# ── Views / summary ───────────────────────────────────────────────

@dataclass
class RiskView:
    risk: Risk
    action_total: int
    action_open: int
    action_overdue: int
    last_review: str | None


def view_risk(risk_id: int) -> RiskView | None:
    r = get_risk(risk_id)
    if r is None:
        return None
    acts = list_actions(risk_id=risk_id)
    open_n = sum(1 for a in acts if not a.is_done)
    overdue_n = sum(1 for a in acts if a.is_overdue)
    revs = list_reviews(risk_id=risk_id, limit=1)
    return RiskView(
        risk=r, action_total=len(acts),
        action_open=open_n, action_overdue=overdue_n,
        last_review=revs[0].review_date if revs else None,
    )


@dataclass
class RiskOverview:
    total: int
    open: int
    closed: int
    reviews_due: int
    by_category: dict[str, int]
    by_status: dict[str, int]
    by_band: dict[str, int]
    high_or_critical: int
    actions_total: int
    actions_open: int
    actions_overdue: int
    top_risks: list[tuple[int, str, int, str]]
    # (risk_id, title, inherent_score, status)


def overview() -> RiskOverview:
    init_db()
    risks = list_risks()
    by_cat: dict[str, int] = {c: 0 for c in CATEGORIES}
    by_status: dict[str, int] = {s: 0 for s in STATUSES}
    by_band: dict[str, int] = {b: 0 for _, _, b in SCORE_BANDS}
    open_n = closed_n = reviews_due_n = hi_n = 0
    for r in risks:
        by_cat[r.category] = by_cat.get(r.category, 0) + 1
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_band[r.inherent_band] = by_band.get(r.inherent_band, 0) + 1
        if r.is_open:
            open_n += 1
        if r.status == "Closed":
            closed_n += 1
        if r.is_review_due and r.is_open:
            reviews_due_n += 1
        if r.inherent_band in ("High", "Critical"):
            hi_n += 1
    actions = list_actions()
    a_open = sum(1 for a in actions if not a.is_done)
    a_over = sum(1 for a in actions if a.is_overdue)
    top = sorted(risks, key=lambda r: -r.inherent_score)[:10]
    return RiskOverview(
        total=len(risks), open=open_n, closed=closed_n,
        reviews_due=reviews_due_n,
        by_category=by_cat, by_status=by_status,
        by_band=by_band,
        high_or_critical=hi_n,
        actions_total=len(actions),
        actions_open=a_open, actions_overdue=a_over,
        top_risks=[(r.risk_id, r.title,
                    r.inherent_score, r.status) for r in top],
    )


def heatmap() -> dict[tuple[int, int], int]:
    """Return a {(likelihood, impact): count} matrix for open
    risks — useful for plotting a 5×5 grid."""
    init_db()
    grid: dict[tuple[int, int], int] = {
        (l, i): 0 for l in range(1, 6) for i in range(1, 6)
    }
    with _connect() as conn:
        ph = ",".join("?" * len(OPEN_STATUSES))
        rows = conn.execute(
            f"SELECT likelihood, impact, COUNT(*) AS n "
            f"FROM risks WHERE status IN ({ph}) "
            f"GROUP BY likelihood, impact",
            OPEN_STATUSES).fetchall()
    for r in rows:
        grid[(int(r["likelihood"]), int(r["impact"]))] = int(r["n"])
    return grid
