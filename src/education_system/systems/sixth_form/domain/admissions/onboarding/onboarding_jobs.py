"""Scheduled onboarding work: chasing overdue tasks and the record resync.

:func:`chase_overdue` puts one in-app notification (the sixth form
notifications inbox, channel In-App — no e-mail) in the inbox of each
member of staff who owns overdue onboarding tasks: the task's
``assigned_to``, else the checklist's, else the admissions staff. A
checklist is chased at most once every :data:`CHASE_EVERY_DAYS` days
(``onboarding_chase_log``). :func:`nightly_resync` runs
:func:`evidence_sources.resync_all`.

Both run under ``_guard.system_actor`` from the scheduler; called by a
person they need the onboarding write capability.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field

from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as ob,
)

logger = logging.getLogger(__name__)

CHASE_EVERY_DAYS = 7

_SCHEMA = """
CREATE TABLE IF NOT EXISTS onboarding_chase_log (
    chase_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    checklist_id  INTEGER NOT NULL,
    recipient     TEXT NOT NULL,
    tasks         INTEGER NOT NULL,
    chased_on     TEXT NOT NULL,
    FOREIGN KEY (checklist_id) REFERENCES onboarding_checklists(checklist_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ob_chase_chk ON onboarding_chase_log(checklist_id);
"""

_READY: set[str] = set()


def _init() -> None:
    key = str(ob.DB_PATH)
    if key in _READY:
        return
    ob.init_db()
    with ob._connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _READY.add(key)


@dataclass
class ChaseResult:
    checklists: int = 0
    tasks: int = 0
    notified: dict[str, int] = field(default_factory=dict)
    skipped_recent: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (f"{self.tasks} overdue task(s) on {self.checklists} "
                f"checklist(s); {len(self.notified)} member(s) of staff "
                f"notified in-app; {self.skipped_recent} checklist(s) chased "
                f"in the last {CHASE_EVERY_DAYS} days")


def admissions_staff() -> list[str]:
    """Active staff whose job role carries ``admissions``."""
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    from education_system.systems.sixth_form.domain.staff import staff as _staff
    roles = {r for r, caps in access.JOB_ROLE_CAPABILITIES.items()
             if access.ADMISSIONS in caps}
    return [s.staff_id for s in _staff.list_staff(active_only=True)
            if s.role in roles]


def _recently_chased(conn, checklist_id: int, since: str) -> bool:
    return conn.execute("SELECT 1 FROM onboarding_chase_log WHERE "
                        "checklist_id = ? AND chased_on >= ?",
                        (checklist_id, since)).fetchone() is not None


def chase_overdue(*, today: str | None = None) -> ChaseResult:
    """Notify the owners of overdue onboarding tasks (in-app only)."""
    ob._require_writer("chasing onboarding tasks")
    _init()
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        onboarding_reports as _rep,
    )
    day = today or _dt.date.today().isoformat()
    since = (_dt.date.fromisoformat(day)
             - _dt.timedelta(days=CHASE_EVERY_DAYS - 1)).isoformat()
    res = ChaseResult()
    tasks = [t for t in _rep.outstanding_tasks(overdue_only=True)
             if (t.due_date or "9999") < day]
    by_chk: dict[int, list] = {}
    for t in tasks:
        by_chk.setdefault(t.checklist_id, []).append(t)
    fallback: list[str] | None = None
    per_person: dict[str, list] = {}
    with ob._connect() as conn:
        for chk_id, rows in by_chk.items():
            if _recently_chased(conn, chk_id, since):
                res.skipped_recent += 1
                continue
            res.checklists += 1
            res.tasks += len(rows)
            for t in rows:
                owners = [t.assigned_to] if t.assigned_to else None
                if owners is None:
                    if fallback is None:
                        try:
                            fallback = admissions_staff()
                        except Exception as exc:  # noqa: BLE001
                            res.errors.append(f"admissions staff: {exc}")
                            fallback = []
                    owners = fallback
                if not owners:
                    res.errors.append(f"{t.student_id}: '{t.task}' has no "
                                      "owner and there are no admissions "
                                      "staff to tell")
                for who in owners:
                    per_person.setdefault(who, []).append(t)
    from education_system.systems.sixth_form.domains.communications.domain.notifications import (
        notifications as _n,
    )
    chased: dict[int, set[str]] = {}
    for who, rows in per_person.items():
        lines = [f"- {t.student_name or t.student_id} ({t.student_id}): "
                 + (f"{ob.RESTRICTED} — due {t.due_date}" if t.sensitive
                    else f"{t.task} — due {t.due_date}"
                    + (f", blocked: {t.blocked_reason}" if t.blocked_reason
                       else "")) for t in rows[:50]]
        if len(rows) > 50:
            lines.append(f"… and {len(rows) - 50} more")
        try:
            _n.create_notification({
                "recipient_type": "Staff", "recipient_id": who,
                "title": f"{len(rows)} overdue onboarding task(s)",
                "body": "\n".join(lines)
                + "\n\nOpen Student Management → Onboarding to update them.",
                "notification_type": "Reminder", "channel": "In-App",
                "status": "Sent",
                "sent_at": _dt.datetime.now().isoformat(timespec="minutes"),
                "sent_by": "onboarding", "requires_action": True,
                "linked_to": "onboarding:overdue",
            })
            res.notified[who] = len(rows)
            for t in rows:
                chased.setdefault(t.checklist_id, set()).add(who)
        except Exception as exc:  # noqa: BLE001 — one person never stops the rest
            logger.exception("Onboarding chase for %s", who)
            res.errors.append(f"{who}: {exc}")
    with ob._connect() as conn:
        for chk_id, people in chased.items():
            n = len(by_chk[chk_id])
            for who in people:
                conn.execute("INSERT INTO onboarding_chase_log (checklist_id, "
                             "recipient, tasks, chased_on) VALUES (?, ?, ?, ?)",
                             (chk_id, who, n, day))
        conn.commit()
    return res


def chase_log(checklist_id: int | None = None, limit: int = 200) -> list[dict]:
    _init()
    sql = "SELECT * FROM onboarding_chase_log"
    args: tuple = ()
    if checklist_id is not None:
        sql += " WHERE checklist_id = ?"
        args = (checklist_id,)
    with ob._connect() as conn:
        return [dict(r) for r in conn.execute(
            sql + " ORDER BY chase_id DESC LIMIT ?", (*args, limit))]


def nightly_resync():
    """Tick open tasks whose record now exists (see
    :func:`evidence_sources.resync_all`)."""
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        evidence_sources,
    )
    return evidence_sources.resync_all()
