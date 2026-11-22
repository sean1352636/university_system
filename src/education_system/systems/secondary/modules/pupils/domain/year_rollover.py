"""Year-end rollover: move every pupil up a year when a new academic year starts.

On the first launch of the secondary system on or after 1 September, for
each pupil on roll who joined before that date:

* Years 7-10 move up one year group. A form group named after its year
  follows them (``7K`` → ``8K``); any other form name is left alone. Form
  group records move up the same way and Year 11 forms are archived
  (:func:`domain.form_groups.roll_forward`).
* Year 11 leave: roll status ``left``, leaving date 31 August, reason
  "End of Year 11". Their record and history are kept; their login is closed
  and shows a "you have left" message if they try to sign in.

Each academic year is rolled over exactly once - recorded in
``year_rollovers`` and done in one transaction, so a crash or two windows
opening at once can't move anyone twice. If the system wasn't opened for
more than a year, each missed year is applied in turn.

The very first time this runs there is nothing to compare with, so it only
records the current year as the starting point and moves nobody: records
entered before then are taken to be correct for the current year.

Every change goes in each pupil's change history (as the "year-end
rollover") and the activity log.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
from dataclasses import dataclass, field, replace

from education_system.systems.secondary.modules.curriculum.domain import form_groups
from education_system.systems.secondary.modules.pupils.domain import enrolment
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.academic_calendar.school_year import label as academic_year_label
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

logger = logging.getLogger(__name__)

SYSTEM_ACTOR = Principal(username="year-end rollover", role="admin")
LEAVING_REASON = "End of Year 11"
LAST_YEAR = max(P.YEAR_GROUPS)
#: Marks a pupil_audit entry as made by the rollover (value: the new academic year).
ROLLOVER_KEY = "_year_end_rollover"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS year_rollovers (
    academic_year TEXT PRIMARY KEY,
    kind          TEXT NOT NULL CHECK (kind IN ('baseline', 'rollover')),
    run_at        TEXT NOT NULL DEFAULT (datetime('now')),
    run_by        TEXT,
    promoted      INTEGER NOT NULL DEFAULT 0,
    leavers       INTEGER NOT NULL DEFAULT 0
);
"""

database.register_schema("year_rollover", _SCHEMA)


@dataclass(frozen=True)
class Rollover:
    academic_year: str
    promoted: int
    leavers: int
    logins_closed: int = 0
    leaver_ids: tuple[int, ...] = field(default=(), repr=False)

    def summary(self) -> str:
        text = (f"New academic year {self.academic_year}: {self.promoted} pupil"
                f"{'s' if self.promoted != 1 else ''} moved up a year and {self.leavers} "
                f"Year {LAST_YEAR} pupil{'s' if self.leavers != 1 else ''} marked as leavers.")
        if self.logins_closed:
            text += (f" {self.logins_closed} leaver login"
                     f"{'s' if self.logins_closed != 1 else ''} closed.")
        return text


def _next_form(form: str | None, old_year: int) -> str | None:
    """``7K`` → ``8K``; a form not named after its year keeps its name."""
    if not form:
        return form
    m = re.fullmatch(rf"{old_year}(\D.*)", form)
    return f"{old_year + 1}{m.group(1)}" if m else form


def history() -> list[dict]:
    with database.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM year_rollovers ORDER BY academic_year")]


def run_if_due(*, triggered_by: Principal | None = None,
               today: _dt.date | None = None) -> list[Rollover]:
    """Roll over every academic year that has started since the last one.
    Returns what was done (empty when nothing was due). Never raises: a
    failure is logged and retried on the next launch."""
    try:
        done = _run(triggered_by, today)
    except Exception as e:  # noqa: BLE001 - must never stop the system opening
        logger.exception("Year-end rollover failed")
        activity_log.record("year.rollover", outcome="error", principal=triggered_by,
                            error=type(e).__name__)
        done = []
    try:
        close_leaver_logins()  # also retries any a previous launch couldn't close
    except Exception:  # noqa: BLE001
        logger.exception("Closing leaver logins failed")
    return done


def close_leaver_logins(pupil_ids: tuple[int, ...] | None = None) -> int:
    """Close the logins of leavers (all of them, or just *pupil_ids*) that are
    still open - also retries any that failed before. Returns how many closed."""
    from education_system.systems.secondary.modules.pupils.domain import pupil_accounts
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT p.pupil_id, p.leaving_date FROM pupils p JOIN pupil_accounts a "
            "USING (pupil_id) WHERE p.roll_status = 'left' AND a.status = 'active'"
            ).fetchall()
    closed = 0
    for r in rows:
        if pupil_ids is not None and r["pupil_id"] not in pupil_ids:
            continue
        if pupil_accounts.close_for_leaver(r["pupil_id"], actor=SYSTEM_ACTOR,
                                           left_on=r["leaving_date"]):
            closed += 1
    return closed


def _run(triggered_by: Principal | None, today: _dt.date | None) -> list[Rollover]:
    current_start = P.academic_year_start(today).year
    who = triggered_by.username if triggered_by else None
    with database.connect() as conn:
        last = conn.execute("SELECT MAX(academic_year) FROM year_rollovers").fetchone()[0]
        if last is None:
            conn.execute("INSERT OR IGNORE INTO year_rollovers (academic_year, kind, run_by) "
                         "VALUES (?, 'baseline', ?)", (academic_year_label(current_start), who))
            activity_log.record("year.rollover", target=academic_year_label(current_start),
                                outcome="baseline", principal=triggered_by)
            return []
    done = []
    for start_year in range(int(last[:4]) + 1, current_start + 1):
        result = _roll_one(start_year, who)
        if result is not None:
            result = replace(result, logins_closed=close_leaver_logins(result.leaver_ids))
            activity_log.record("year.rollover", target=result.academic_year,
                                principal=triggered_by, promoted=result.promoted,
                                leavers=result.leavers, logins_closed=result.logins_closed)
            done.append(result)
    return done


def _roll_one(start_year: int, who: str | None) -> Rollover | None:
    label = academic_year_label(start_year)
    start = _dt.date(start_year, 9, 1)
    leaving_date = (start - _dt.timedelta(days=1)).isoformat()
    with database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")  # one writer: two windows can't both roll over
        claimed = conn.execute(
            "INSERT OR IGNORE INTO year_rollovers (academic_year, kind, run_by) "
            "VALUES (?, 'rollover', ?)", (label, who)).rowcount
        if not claimed:
            return None  # already done by another session
        rows = conn.execute(
            "SELECT pupil_id, year_group, form_group FROM pupils WHERE roll_status = 'on_roll' "
            "AND admission_date < ? ORDER BY year_group DESC", (start.isoformat(),)).fetchall()
        promoted = leavers = 0
        leaver_ids: list[int] = []
        for r in rows:
            year, form = r["year_group"], r["form_group"]
            if year >= LAST_YEAR:
                conn.execute(
                    "UPDATE pupils SET roll_status = 'left', leaving_date = ?, "
                    "leaving_reason = ?, updated_at = datetime('now'), updated_by = ? "
                    "WHERE pupil_id = ?",
                    (leaving_date, LEAVING_REASON, SYSTEM_ACTOR.username, r["pupil_id"]))
                detail = {"roll_status": {"from": "on_roll", "to": "left"},
                          "leaving_date": {"from": None, "to": leaving_date},
                          "leaving_reason": {"from": None, "to": LEAVING_REASON}}
                leavers += 1
                leaver_ids.append(r["pupil_id"])
                # Leaving details, so their post-16 destination shows as to-do.
                enrolment._insert_leaving(r["pupil_id"], leaving_date, LEAVING_REASON, {},
                                          SYSTEM_ACTOR.username, conn=conn)
            else:
                new_form = _next_form(form, year)
                conn.execute(
                    "UPDATE pupils SET year_group = ?, form_group = ?, "
                    "updated_at = datetime('now'), updated_by = ? WHERE pupil_id = ?",
                    (year + 1, new_form, SYSTEM_ACTOR.username, r["pupil_id"]))
                detail = {"year_group": {"from": year, "to": year + 1}}
                if new_form != form:
                    detail["form_group"] = {"from": form, "to": new_form}
                promoted += 1
            conn.execute(
                "INSERT INTO pupil_audit (pupil_id, action, actor, detail) VALUES (?, ?, ?, ?)",
                # pupil_audit only allows create/update/delete: an update tagged as rollover.
                (r["pupil_id"], "update", SYSTEM_ACTOR.username,
                 json.dumps({ROLLOVER_KEY: label, **detail}, default=str, sort_keys=True)))
        # Form records move up with their pupils (7K -> 8K); Year 11 forms close.
        form_groups.roll_forward(conn, label, SYSTEM_ACTOR.username)
        conn.execute("UPDATE year_rollovers SET promoted = ?, leavers = ? WHERE academic_year = ?",
                     (promoted, leavers, label))
    logger.info("Year-end rollover %s: %d promoted, %d leavers", label, promoted, leavers)
    return Rollover(label, promoted, leavers, leaver_ids=tuple(leaver_ids))
