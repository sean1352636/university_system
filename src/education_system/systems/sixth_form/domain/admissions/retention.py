"""Retention of unsuccessful applications.

Applications that never became students are kept only as long as the
college's retention policy says, then erased through the same erasure
path as a GDPR request (:func:`record_safety._erase`, which keeps an
erasure-log entry with who, when and why).

The policy is **off** by default. Turning it on, or changing it, needs
the ``governance`` capability; the person who enabled it is recorded as
the approver of every erasure it makes, and the scheduled job requests
them as "retention policy". Never touched: enrolled or converted
applicants, applications part-way through conversion, applications with
a pending erasure request, and anything not in the statuses the policy
names.

The clock starts at the later of the cycle's closing date and the
application's decision date (falling back to its last update).
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.admissions import _guard
from education_system.systems.sixth_form.domain.admissions import (
    admissions as _adm,
)

logger = logging.getLogger(__name__)

ValidationError = _adm.ValidationError

#: Statuses the policy may cover. "Archived" means an archived (or
#: merged-away) application that was never enrolled, whatever its status.
ELIGIBLE_STATUSES: tuple[str, ...] = ("Rejected", "Withdrawn",
                                      "Offer Declined", "Archived")
DEFAULT_MONTHS: int = 12
REQUESTED_BY: str = "retention policy"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions_retention_policy (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    enabled        INTEGER NOT NULL DEFAULT 0,
    months         INTEGER NOT NULL DEFAULT 12,
    statuses_json  TEXT NOT NULL,
    enabled_by     TEXT,
    enabled_at     TEXT,
    updated_by     TEXT,
    updated_at     TEXT
);

CREATE TABLE IF NOT EXISTS admissions_retention_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    at           TEXT NOT NULL DEFAULT (datetime('now')),
    run_by       TEXT,
    dry_run      INTEGER NOT NULL,
    candidates   INTEGER NOT NULL DEFAULT 0,
    erased       INTEGER NOT NULL DEFAULT 0,
    errors_json  TEXT
);
"""

_READY = False


def init_db() -> None:
    global _READY
    if _READY:
        return
    from education_system.systems.sixth_form.domain.admissions import (
        cycles,
        record_safety,
    )
    record_safety.init_db()
    cycles.init_db()
    with _adm._connect() as conn:
        conn.executescript(_SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO admissions_retention_policy (id, enabled, "
            "months, statuses_json) VALUES (1, 0, ?, ?)",
            (DEFAULT_MONTHS, json.dumps(list(ELIGIBLE_STATUSES))))
        conn.commit()
    _READY = True


def _access():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access


@dataclass
class Policy:
    enabled: bool
    months: int
    statuses: tuple[str, ...]
    enabled_by: str | None
    enabled_at: str | None
    updated_by: str | None
    updated_at: str | None

    @property
    def text(self) -> str:
        return (f"Retention policy: unsuccessful applications "
                f"({', '.join(self.statuses)}) are erased {self.months} "
                f"month(s) after the cycle closes or the decision, "
                f"whichever is later")


def get_policy() -> Policy:
    init_db()
    _guard.require_any((_access().ADMISSIONS, _access().GOVERNANCE),
                       "the retention policy")
    with _adm._connect() as conn:
        r = conn.execute("SELECT * FROM admissions_retention_policy "
                         "WHERE id = 1").fetchone()
    return Policy(enabled=bool(r["enabled"]), months=r["months"],
                  statuses=tuple(json.loads(r["statuses_json"] or "[]")),
                  enabled_by=r["enabled_by"], enabled_at=r["enabled_at"],
                  updated_by=r["updated_by"], updated_at=r["updated_at"])


def set_policy(*, enabled: bool | None = None, months: int | None = None,
               statuses: Any = None) -> Policy:
    """Change the policy (``governance`` capability). Enabling it records
    you as the approver of the erasures it makes."""
    init_db()
    p = _guard.require("changing the admissions retention policy",
                       _access().GOVERNANCE)
    cur = get_policy()
    new_months = cur.months
    if months is not None:
        try:
            new_months = int(months)
        except (TypeError, ValueError):
            raise ValidationError("Months must be a whole number") from None
        if not 1 <= new_months <= 120:
            raise ValidationError("Months must be between 1 and 120")
    new_statuses = cur.statuses
    if statuses is not None:
        new_statuses = tuple(dict.fromkeys(statuses))
        bad = set(new_statuses) - set(ELIGIBLE_STATUSES)
        if bad:
            raise ValidationError(
                f"Statuses must be from: {', '.join(ELIGIBLE_STATUSES)}")
        if not new_statuses:
            raise ValidationError("Choose at least one status")
    new_enabled = cur.enabled if enabled is None else bool(enabled)
    who = p.username or None
    if new_enabled and not who:
        raise ValidationError("A named person must enable the policy.")
    enabled_by, enabled_at = cur.enabled_by, cur.enabled_at
    if new_enabled and not cur.enabled:
        enabled_by = who
        enabled_at = _dt.datetime.now().isoformat(timespec="seconds")
    elif not new_enabled:
        enabled_by = enabled_at = None
    with _adm._connect() as conn:
        conn.execute(
            "UPDATE admissions_retention_policy SET enabled = ?, months = ?, "
            "statuses_json = ?, enabled_by = ?, enabled_at = ?, "
            "updated_by = ?, updated_at = datetime('now') WHERE id = 1",
            (int(new_enabled), new_months, json.dumps(list(new_statuses)),
             enabled_by, enabled_at, who))
        conn.commit()
    logger.info("Admissions retention policy %s by %s (%s months, %s)",
                "enabled" if new_enabled else "disabled", who, new_months,
                ", ".join(new_statuses))
    return get_policy()


# ── Candidates ─────────────────────────────────────────────────────

@dataclass
class Candidate:
    applicant_id: str
    name: str
    status: str
    intake_year: str | None
    archived: bool
    clock_from: str
    due_on: str


def _add_months(d: _dt.date, months: int) -> _dt.date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    for day in (d.day, 30, 29, 28):
        try:
            return _dt.date(year, month, day)
        except ValueError:
            continue
    return _dt.date(year, month, 28)


def candidates(*, today: _dt.date | None = None,
               policy: Policy | None = None) -> list[Candidate]:
    """Applications the policy would erase now (works whether or not the
    policy is on, so it can be previewed)."""
    init_db()
    pol = policy or get_policy()
    day = today or _dt.date.today()
    statuses = set(pol.statuses)
    with _adm._connect() as conn:
        rows = conn.execute(
            "SELECT a.*, c.closes_on AS cycle_closes FROM admissions_applicants a "
            "LEFT JOIN admissions_cycles c ON c.cycle = a.intake_year "
            "WHERE a.converted_student_id IS NULL AND a.status <> 'Enrolled' "
            "AND a.converting_at IS NULL "
            "AND NOT EXISTS (SELECT 1 FROM admissions_conversions v "
            "  WHERE v.applicant_id = a.applicant_id) "
            "AND NOT EXISTS (SELECT 1 FROM admissions_erasure_requests r "
            "  WHERE r.applicant_id = a.applicant_id AND r.status IN "
            "  ('Pending', 'Approved'))").fetchall()
    out = []
    for r in rows:
        archived = bool(r["archived_at"])
        if not ((archived and "Archived" in statuses)
                or (r["status"] in statuses and r["status"] != "Archived")):
            continue
        dates = [x[:10] for x in (r["cycle_closes"], r["decision_date"])
                 if x]
        if not dates:
            dates = [x[:10] for x in (r["updated_at"], r["submitted_at"]) if x]
        if archived and r["archived_at"]:
            dates.append(r["archived_at"][:10])
        try:
            start = max(_dt.date.fromisoformat(x) for x in dates)
        except ValueError:
            continue
        due = _add_months(start, pol.months)
        if due > day:
            continue
        out.append(Candidate(
            applicant_id=r["applicant_id"],
            name=f"{r['first_name']} {r['last_name']}".strip(),
            status=r["status"], intake_year=r["intake_year"],
            archived=archived, clock_from=start.isoformat(),
            due_on=due.isoformat()))
    out.sort(key=lambda c: (c.due_on, c.applicant_id))
    return out


# ── Run ────────────────────────────────────────────────────────────

@dataclass
class RetentionRun:
    dry_run: bool
    enabled: bool
    candidates: list[Candidate] = field(default_factory=list)
    erased: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if not self.enabled and not self.dry_run:
            return "Retention policy is off — nothing erased"
        verb = "would be erased" if self.dry_run else "erased"
        n = len(self.candidates) if self.dry_run else len(self.erased)
        return (f"{n} unsuccessful application(s) {verb} under the retention "
                f"policy" + (f"; {len(self.errors)} error(s)"
                             if self.errors else ""))


def run(*, dry_run: bool = True, today: _dt.date | None = None
        ) -> RetentionRun:
    """Preview (default) or carry out the policy. A real run needs the
    policy on and the ``governance`` capability (the scheduled job runs
    as a system actor holding it)."""
    init_db()
    pol = get_policy()
    result = RetentionRun(dry_run=dry_run, enabled=pol.enabled)
    if not dry_run:
        _guard.require("running the admissions retention policy",
                       _access().GOVERNANCE)
        if not pol.enabled:
            return result
        if not pol.enabled_by:
            result.errors.append("The policy has no recorded approver; turn it "
                                 "off and on again.")
            return result
    result.candidates = candidates(today=today, policy=pol)
    if dry_run:
        return result
    from education_system.systems.sixth_form.domain.admissions import (
        record_safety,
    )
    reason = pol.text
    for c in result.candidates:
        try:
            record_safety._erase(
                c.applicant_id, requested_by=REQUESTED_BY,
                approved_by=pol.enabled_by,
                reason=f"{reason} (due {c.due_on}; {c.status}"
                       f"{', archived' if c.archived else ''})")
            result.erased.append(c.applicant_id)
        except Exception as e:  # noqa: BLE001 — one record failing must not stop the rest
            logger.exception("Retention erase of %s failed", c.applicant_id)
            result.errors.append(f"{c.applicant_id}: {e}")
    with _adm._connect() as conn:
        conn.execute(
            "INSERT INTO admissions_retention_runs (run_by, dry_run, "
            "candidates, erased, errors_json) VALUES (?, 0, ?, ?, ?)",
            (_guard.actor(), len(result.candidates), len(result.erased),
             json.dumps(result.errors) if result.errors else None))
        conn.commit()
    return result


def run_history(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    _guard.require_any((_access().ADMISSIONS, _access().GOVERNANCE),
                       "retention runs")
    with _adm._connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM admissions_retention_runs ORDER BY id DESC LIMIT ?",
            (limit,))]
