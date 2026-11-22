"""CLI flows for destinations the university itself confirmed. Listed in
the Destinations menu after the sustained-destination entries.
"""

from __future__ import annotations

import datetime as _dt
import logging

from education_system.systems.sixth_form.domain.progression.destinations import (
    university_confirmations as data,
)
from education_system.systems.sixth_form.interfaces.cli.progression import _record_menus as rm

logger = logging.getLogger(__name__)


def _year() -> int:
    today = _dt.date.today()
    default = today.year if today.month >= 8 else today.year - 1
    return rm.ask_int("Leaver year (summer left)", default=default) or default


def cohort() -> None:
    year = _year()
    rows = [r.as_row() for r in data.cohort(year)]
    rm.print_table(rows, (("student_id", "ID", 10), ("student_name", "Student", 22),
                          ("destination", "Destination", 30), ("basis", "Basis", 24),
                          ("university_status", "University reports", 22),
                          ("conflict", "", 6)))
    counts = data.cohort_summary(year)
    total = counts.get("Leavers", 0)
    print()
    for k in (data.BASIS_CONFIRMED, data.BASIS_SELF, data.BASIS_NONE):
        pct = f" ({round(100 * counts[k] / total)}%)" if total else ""
        print(f"  {k:<44} {counts[k]:>4}{pct}")
    for k in ("Needs review (differs from university)",
              "Sustained (university reports progression)",
              "Withdrew (university reports)"):
        print(f"  {k:<44} {counts[k]:>4}")
    rm.pause()


def one_learner() -> None:
    sid = rm.pick_student()
    confs = data.confirmations_for(sid)
    if not confs:
        print("\n  The university has not reported on this learner.")
    for c in confs:
        reason = (f"  (reason: {data.REASON_LABELS.get(c['reason_category'] or '', '—')})"
                  if c["event_type"] == "withdrawn" else "")
        print(f"\n  {c['event_date'] or '?'}  {c['outcome']}{reason}")
        print(f"      {c['institution'] or ''} {c['course'] or ''}".rstrip())
        print(f"      {c['applied'] or ''}"
              f"{'; ' + str(c['months_recorded']) + ' HE month(s) recorded' if c['months_recorded'] else ''}"
              f"{'  — DIFFERS from recorded destination, review it' if c['conflict'] else ''}")
    rm.pause()


def updates() -> None:
    rows = data.list_confirmations()
    rm.print_table(rows, (("event_date", "Date", 10), ("student_id", "ID", 10),
                          ("student_name", "Student", 22), ("outcome", "Outcome", 22),
                          ("institution", "Institution", 24), ("reason", "Reason", 13),
                          ("applied", "Applied", 30)))
    rm.pause()


MENU = (
    ("Confirmed vs self-reported destinations", cohort),
    ("University updates — one learner", one_learner),
    ("University updates — all", updates),
)

__all__ = ["MENU"]
