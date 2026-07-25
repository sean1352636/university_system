"""Policy register for the Primary School System.

A two-table register tracking the school's formal policies:

* ``policies``           — one row per policy (Safeguarding,
                            Behaviour, Data Protection, Health & Safety,
                            etc.) with current version, owner, status
                            and next review date.
* ``policy_revisions``   — every approval/revision is appended here so
                            you keep a full audit trail of who approved
                            what and when.

Stored status is what staff set; ``view_policy`` / ``list_views`` flip
items to "Overdue review" when ``next_review`` is in the past.

Cascades: deleting a policy removes its revisions via FK.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.POLICIES_DB

CATEGORIES: tuple[str, ...] = (
    "Safeguarding", "Behaviour", "Curriculum", "Data Protection",
    "Health & Safety", "HR", "Finance", "Admissions", "SEND",
    "Equality", "IT & Online", "Other",
)
DEFAULT_CATEGORY: str = "Other"

STATUSES: tuple[str, ...] = (
    "Draft", "Approved", "Under review", "Archived",
)
DEFAULT_STATUS: str = "Draft"

DERIVED_STATUSES: tuple[str, ...] = (*STATUSES, "Overdue review")

REVIEW_CYCLES: tuple[str, ...] = (
    "Annual", "Biennial", "Triennial", "Ad-hoc",
)
DEFAULT_REVIEW_CYCLE: str = "Annual"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VERSION_RE = re.compile(r"^\d+(\.\d+){0,2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS policies (
    policy_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT 'Other',
    version       TEXT NOT NULL DEFAULT '1.0',
    owner         TEXT,
    status        TEXT NOT NULL DEFAULT 'Draft',
    review_cycle  TEXT NOT NULL DEFAULT 'Annual',
    approved_on   TEXT,
    next_review   TEXT,
    summary       TEXT,
    document_ref  TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pol_status   ON policies(status);
CREATE INDEX IF NOT EXISTS idx_pol_category ON policies(category);
CREATE INDEX IF NOT EXISTS idx_pol_next     ON policies(next_review);

CREATE TABLE IF NOT EXISTS policy_revisions (
    revision_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_id    INTEGER NOT NULL,
    version      TEXT NOT NULL,
    revised_on   TEXT NOT NULL,
    revised_by   TEXT,
    changes      TEXT,
    approved_by  TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (policy_id) REFERENCES policies(policy_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rev_policy ON policy_revisions(policy_id);
CREATE INDEX IF NOT EXISTS idx_rev_date   ON policy_revisions(revised_on);
"""


# ── Result types ───────────────────────────────────────────────────

@dataclass
class Policy:
    policy_id: int
    title: str
    category: str
    version: str
    owner: str | None
    status: str
    review_cycle: str
    approved_on: str | None
    next_review: str | None
    summary: str | None
    document_ref: str | None
    created_at: str
    updated_at: str


@dataclass
class Revision:
    revision_id: int
    policy_id: int
    version: str
    revised_on: str
    revised_by: str | None
    changes: str | None
    approved_by: str | None
    created_at: str


@dataclass
class PolicyView:
    policy: Policy
    derived_status: str
    days_until_review: int | None
    revisions_count: int


# ── DB plumbing ────────────────────────────────────────────────────

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
    logger.debug("Policies schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_p(r: sqlite3.Row) -> Policy:
    return Policy(
        policy_id=r["policy_id"], title=r["title"], category=r["category"],
        version=r["version"], owner=r["owner"], status=r["status"],
        review_cycle=r["review_cycle"], approved_on=r["approved_on"],
        next_review=r["next_review"], summary=r["summary"],
        document_ref=r["document_ref"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_r(r: sqlite3.Row) -> Revision:
    return Revision(
        revision_id=r["revision_id"], policy_id=r["policy_id"],
        version=r["version"], revised_on=r["revised_on"],
        revised_by=r["revised_by"], changes=r["changes"],
        approved_by=r["approved_by"], created_at=r["created_at"],
    )


# ── Validation ─────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _validate_date(v: Any, label: str, *, required: bool = False) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(v).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_in(v: Any, options: tuple[str, ...], label: str) -> str:
    s = (v or "").strip()
    if s not in options:
        raise ValidationError(f"{label} must be one of: {', '.join(options)}")
    return s


def _validate_version(v: Any) -> str:
    s = (v or "").strip()
    if not s:
        raise ValidationError("Version is required (e.g. '1.0', '2.3.1')")
    if not _VERSION_RE.match(s):
        raise ValidationError(
            "Version must be numeric (e.g. '1', '1.0', '2.3.1')")
    return s


def _validate_policy(data: dict[str, Any], *, partial: bool = False
                       ) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "title" in data or not partial:
        t = (data.get("title") or "").strip()
        if not t:
            raise ValidationError("Title is required")
        if len(t) > 200:
            raise ValidationError("Title must be 200 chars or fewer")
        out["title"] = t
    if "category" in data or not partial:
        out["category"] = _validate_in(
            data.get("category") or DEFAULT_CATEGORY, CATEGORIES, "Category")
    if "version" in data or not partial:
        out["version"] = _validate_version(data.get("version") or "1.0")
    if "owner" in data:
        out["owner"] = (data.get("owner") or "").strip() or None
    if "status" in data or not partial:
        out["status"] = _validate_in(
            data.get("status") or DEFAULT_STATUS, STATUSES, "Status")
    if "review_cycle" in data or not partial:
        out["review_cycle"] = _validate_in(
            data.get("review_cycle") or DEFAULT_REVIEW_CYCLE,
            REVIEW_CYCLES, "Review cycle")
    if "approved_on" in data:
        out["approved_on"] = _validate_date(
            data.get("approved_on"), "Approved on")
    if "next_review" in data:
        out["next_review"] = _validate_date(
            data.get("next_review"), "Next review")
    if "summary" in data:
        s = (data.get("summary") or "").strip() or None
        if s and len(s) > 2000:
            raise ValidationError("Summary must be 2000 chars or fewer")
        out["summary"] = s
    if "document_ref" in data:
        out["document_ref"] = (data.get("document_ref") or "").strip() or None
    return out


def _validate_revision(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": _validate_version(data.get("version")),
        "revised_on": _validate_date(
            data.get("revised_on"), "Revised on", required=True),
        "revised_by": (data.get("revised_by") or "").strip() or None,
        "changes":    (data.get("changes")    or "").strip() or None,
        "approved_by": (data.get("approved_by") or "").strip() or None,
    }


# ── Review-cycle helpers ───────────────────────────────────────────

_CYCLE_DAYS: dict[str, int] = {
    "Annual":     365,
    "Biennial":   730,
    "Triennial":  1095,
    "Ad-hoc":     0,
}


def _bump(date_s: str, cycle: str) -> str | None:
    days = _CYCLE_DAYS.get(cycle, 0)
    if days <= 0:
        return None
    try:
        d = _dt.date.fromisoformat(date_s)
    except ValueError:
        return None
    return (d + _dt.timedelta(days=days)).isoformat()


# ── Policy CRUD ────────────────────────────────────────────────────

def create_policy(data: dict[str, Any]) -> Policy:
    init_db()
    cleaned = _validate_policy(data, partial=False)
    if (not cleaned.get("next_review")) and cleaned.get("approved_on"):
        bumped = _bump(cleaned["approved_on"], cleaned["review_cycle"])
        if bumped:
            cleaned["next_review"] = bumped
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO policies
                (title, category, version, owner, status, review_cycle,
                 approved_on, next_review, summary, document_ref)
               VALUES (:title, :category, :version, :owner, :status,
                       :review_cycle, :approved_on, :next_review,
                       :summary, :document_ref)""",
            {
                "title": cleaned["title"], "category": cleaned["category"],
                "version": cleaned["version"], "owner": cleaned.get("owner"),
                "status": cleaned["status"],
                "review_cycle": cleaned["review_cycle"],
                "approved_on": cleaned.get("approved_on"),
                "next_review": cleaned.get("next_review"),
                "summary": cleaned.get("summary"),
                "document_ref": cleaned.get("document_ref"),
            })
        pid = cur.lastrowid
        conn.commit()
    out = get_policy(pid)
    assert out is not None
    logger.info("Created policy #%d (%s)", pid, cleaned["title"])
    return out


def get_policy(policy_id: int) -> Policy | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM policies WHERE policy_id = ?",
            (policy_id,)).fetchone()
        return _row_p(r) if r else None


def list_policies(
    *,
    category: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    overdue_only: bool = False,
    query: str | None = None,
) -> list[Policy]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if category:
        clauses.append("category = ?")
        args.append(_validate_in(category, CATEGORIES, "Category"))
    if status:
        clauses.append("status = ?")
        args.append(_validate_in(status, STATUSES, "Status"))
    if owner:
        clauses.append("owner LIKE ?")
        args.append(f"%{owner.strip()}%")
    if overdue_only:
        today = _dt.date.today().isoformat()
        clauses.append(
            "next_review IS NOT NULL AND next_review < ? "
            "AND status NOT IN ('Archived')")
        args.append(today)
    if query:
        like = f"%{query.strip()}%"
        clauses.append("(title LIKE ? OR summary LIKE ?)")
        args.extend([like, like])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM policies {where} "
           "ORDER BY COALESCE(next_review, '9999-12-31') ASC, title ASC")
    with _connect() as conn:
        return [_row_p(r) for r in conn.execute(sql, args).fetchall()]


def update_policy(policy_id: int, data: dict[str, Any]) -> Policy:
    init_db()
    if get_policy(policy_id) is None:
        raise ValidationError(f"No policy #{policy_id}")
    cleaned = _validate_policy(data, partial=True)
    if not cleaned:
        out = get_policy(policy_id)
        assert out is not None
        return out
    sets = ", ".join(f"{k} = :{k}" for k in cleaned)
    cleaned["policy_id"] = policy_id
    with _connect() as conn:
        conn.execute(
            f"UPDATE policies SET {sets}, "
            "updated_at = datetime('now') WHERE policy_id = :policy_id",
            cleaned)
        conn.commit()
    out = get_policy(policy_id)
    assert out is not None
    logger.info("Updated policy #%d", policy_id)
    return out


def delete_policy(policy_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM policies WHERE policy_id = ?", (policy_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted policy #%d", policy_id)
            return True
        return False


# ── Revision log ───────────────────────────────────────────────────

def add_revision(policy_id: int, data: dict[str, Any]) -> Revision:
    """Append a revision entry and, if approved, sync the policy's
    current ``version``, ``status='Approved'``, ``approved_on``, and
    bump ``next_review`` by the review cycle."""
    init_db()
    policy = get_policy(policy_id)
    if policy is None:
        raise ValidationError(f"No policy #{policy_id}")
    cleaned = _validate_revision(data)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO policy_revisions
                (policy_id, version, revised_on, revised_by, changes,
                 approved_by)
               VALUES (:policy_id, :version, :revised_on, :revised_by,
                       :changes, :approved_by)""",
            {**cleaned, "policy_id": policy_id})
        rid = cur.lastrowid
        # If this revision carries an approver, treat it as the new
        # current state of the policy.
        if cleaned.get("approved_by"):
            bumped = _bump(cleaned["revised_on"], policy.review_cycle)
            conn.execute(
                """UPDATE policies SET version = ?, status = 'Approved',
                                       approved_on = ?, next_review = ?,
                                       updated_at = datetime('now')
                   WHERE policy_id = ?""",
                (cleaned["version"], cleaned["revised_on"], bumped,
                 policy_id))
        conn.commit()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM policy_revisions WHERE revision_id = ?",
            (rid,)).fetchone()
    assert r is not None
    logger.info("Added revision #%d to policy #%d", rid, policy_id)
    return _row_r(r)


def list_revisions(policy_id: int) -> list[Revision]:
    init_db()
    with _connect() as conn:
        return [
            _row_r(r) for r in conn.execute(
                "SELECT * FROM policy_revisions WHERE policy_id = ? "
                "ORDER BY revised_on DESC, revision_id DESC",
                (policy_id,)).fetchall()
        ]


def delete_revision(revision_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM policy_revisions WHERE revision_id = ?",
            (revision_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Views ──────────────────────────────────────────────────────────

def _count_revisions(conn: sqlite3.Connection, policy_id: int) -> int:
    r = conn.execute(
        "SELECT COUNT(*) AS n FROM policy_revisions WHERE policy_id = ?",
        (policy_id,)).fetchone()
    return int(r["n"]) if r else 0


def _view(policy: Policy, today: _dt.date,
            revisions: int) -> PolicyView:
    derived = policy.status
    days: int | None = None
    if policy.next_review:
        try:
            t = _dt.date.fromisoformat(policy.next_review)
            days = (t - today).days
            if days < 0 and policy.status not in ("Archived",):
                derived = "Overdue review"
        except ValueError:
            pass
    return PolicyView(policy=policy, derived_status=derived,
                       days_until_review=days, revisions_count=revisions)


def view_policy(policy_id: int) -> PolicyView | None:
    policy = get_policy(policy_id)
    if policy is None:
        return None
    with _connect() as conn:
        n = _count_revisions(conn, policy_id)
    return _view(policy, _dt.date.today(), n)


def list_views(**kwargs) -> list[PolicyView]:
    today = _dt.date.today()
    policies = list_policies(**kwargs)
    if not policies:
        return []
    ids = [p.policy_id for p in policies]
    placeholders = ",".join("?" * len(ids))
    counts: dict[int, int] = {pid: 0 for pid in ids}
    with _connect() as conn:
        for r in conn.execute(
                f"SELECT policy_id, COUNT(*) AS n FROM policy_revisions "
                f"WHERE policy_id IN ({placeholders}) GROUP BY policy_id",
                ids).fetchall():
            counts[r["policy_id"]] = int(r["n"])
    return [_view(p, today, counts.get(p.policy_id, 0)) for p in policies]


# ── Summary ────────────────────────────────────────────────────────

@dataclass
class Summary:
    total: int
    by_category: dict[str, int]
    by_status: dict[str, int]      # derived (Overdue review included)
    overdue: int
    due_soon: int                  # within 30 days, not yet overdue
    no_review_date: int
    total_revisions: int


def summary(*, due_soon_days: int = 30) -> Summary:
    init_db()
    views = list_views()
    by_cat: dict[str, int] = {c: 0 for c in CATEGORIES}
    by_status: dict[str, int] = {s: 0 for s in DERIVED_STATUSES}
    overdue = 0
    due_soon = 0
    no_review = 0
    total_revs = 0
    for v in views:
        by_cat[v.policy.category] = by_cat.get(v.policy.category, 0) + 1
        by_status[v.derived_status] = by_status.get(v.derived_status, 0) + 1
        total_revs += v.revisions_count
        if v.derived_status == "Overdue review":
            overdue += 1
        elif (v.days_until_review is not None
                and 0 <= v.days_until_review <= due_soon_days):
            due_soon += 1
        if not v.policy.next_review:
            no_review += 1
    return Summary(
        total=len(views), by_category=by_cat, by_status=by_status,
        overdue=overdue, due_soon=due_soon, no_review_date=no_review,
        total_revisions=total_revs,
    )
