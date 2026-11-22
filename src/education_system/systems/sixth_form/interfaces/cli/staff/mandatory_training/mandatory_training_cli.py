"""CLI flows for the staff mandatory-training matrix."""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Callable

from education_system.systems.sixth_form.domain.staff.mandatory_training import (
    mandatory_training as data,
)
from education_system.systems.sixth_form.interfaces.cli.operations._ops_cli import (
    ask,
    ask_int,
    choose,
    choose_many,
    pause,
    pick_staff,
    run_menu,
    table,
    yes_no,
)

logger = logging.getLogger(__name__)

_MARK = {data.DONE: "ok", data.DUE_SOON: "due", data.OVERDUE: "OVER",
         data.MISSING: "--", data.NOT_REQUIRED: ""}


def _pick_type(active_only: bool = True) -> int:
    types = data.list_types(active_only=active_only)
    label = choose("Training", [f"{t.type_id} — {t.name}" for t in types])
    if label is None:
        raise ValueError("No training types yet — add some or install the "
                         "standard list")
    return int(label.split(" — ")[0])


def _cells(cells) -> None:
    table(["Staff", "Training", "State", "Last done", "Expires", "From"],
          [(c.staff_name, c.type_name, c.state or "n/a", c.completed_on,
            c.expires_on, c.latest.source if c.latest else "")
           for c in cells])


def matrix_flow() -> None:
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    dept = choose("Department (blank = all)", _staff.DEPARTMENTS,
                  allow_blank=True)
    types, rows = data.matrix(department=dept)
    print("\n  ok = in date · due = renew soon · OVER = expired · "
          "-- = never done · blank = not required")
    table(["Staff"] + [t.code for t in types],
          [[r[0].staff_name] + [_MARK[c.state] for c in r]
           for r in rows if r])
    pause()


def staff_flow() -> None:
    _cells(data.staff_status(pick_staff()))
    pause()


def my_flow() -> None:
    _cells(data.my_status())
    pause()


def expiring_flow() -> None:
    days = ask_int("Expiring within how many days", default=30)
    _cells(data.expiring(within_days=days,
                         include_missing=yes_no("Include never done?")))
    pause()


def record_flow() -> None:
    sid = pick_staff()
    tid = _pick_type()
    e = data.record_completion({
        "staff_id": sid, "type_id": tid,
        "completed_on": ask("Completed on (YYYY-MM-DD)",
                            default=_dt.date.today().isoformat()),
        "expires_on": ask("Expires on (blank = from renewal period)"),
        "provider": ask("Provider"),
        "evidence": ask("Certificate / evidence note")})
    print(f"\n  ✓ Recorded in {e.source}; expires {e.expires_on or 'never'}")
    pause()


def records_flow() -> None:
    sid = pick_staff() if yes_no("For one member of staff?") else None
    types = {t.type_id: t.name for t in data.list_types()}
    table(["#", "Staff", "Training", "Completed", "Expires", "Provider",
           "Evidence", "Archived"],
          [(c.completion_id, c.staff_id, types.get(c.type_id), c.completed_on,
            c.expires_on, c.provider, c.evidence, c.archived_reason)
           for c in data.list_completions(staff_id=sid,
                                          include_archived=True)])
    pause()


def archive_flow() -> None:
    cid = ask_int("Training record #")
    data.archive_completion(cid, ask("Reason", required=True))
    print("\n  ✓ Archived")
    pause()


def types_flow() -> None:
    table(["ID", "Code", "Name", "Renewal", "Warn", "Also counts",
           "Required by", "Active"],
          [(t.type_id, t.code, t.name, t.renewal_label, t.due_soon_days,
            t.evidence_source, "; ".join(t.requirements),
            "Y" if t.active else "N") for t in data.list_types()])
    pause()


def _type_form(existing=None) -> dict:
    g = (lambda k, d="": str(getattr(existing, k) or d)) if existing \
        else (lambda k, d="": d)
    return {
        "code": ask("Code", default=g("code"), required=True),
        "name": ask("Name", default=g("name"), required=True),
        "renewal_months": ask("Renew every N months (blank = once)",
                              default=g("renewal_months")),
        "due_soon_days": ask("Warn 'due soon' days before",
                             default=g("due_soon_days", "60")),
        "evidence_source": choose(
            "Also count (blank = records/CPD only)",
            [s for s in data.EVIDENCE_SOURCES if s], allow_blank=True) or "",
        "description": ask("Description", default=g("description")),
        "active": yes_no("Active", default=existing.active
                         if existing else True),
    }


def new_type_flow() -> None:
    t = data.create_type(_type_form())
    print(f"\n  ✓ Created {t.name}")
    requirements_flow(t.type_id)


def edit_type_flow() -> None:
    t = data.get_type(_pick_type(active_only=False))
    t = data.update_type(t.type_id, _type_form(t))
    print(f"\n  ✓ Updated {t.name}")
    pause()


def requirements_flow(type_id: int | None = None) -> None:
    tid = type_id or _pick_type()
    t = data.get_type(tid)
    chosen = data.requirement_targets()
    current = [x for x in t.requirements if not x.startswith("Staff: ")]
    picks = set(choose_many("Who needs it", chosen, current))
    people = [x for x in t.requirements if x.startswith("Staff: ")]
    while yes_no("Add a named person (e.g. fire marshal)?"):
        people.append(f"Staff: {pick_staff()}")
    t = data.set_requirements(tid, sorted(picks) + people)
    print(f"\n  ✓ {t.name}: {'; '.join(t.requirements) or 'nobody'}")
    pause()


def install_flow() -> None:
    if yes_no("Add the standard UK list of training types (existing ones "
              "unchanged, nothing marked complete)?", default=True):
        made = data.install_default_types()
        print(f"\n  ✓ Added {len(made)} type(s)")
    pause()


def cpd_links_flow() -> None:
    table(["Activity", "Date", "Counts as"],
          [(r["activity"], r["date"], r["type"])
           for r in data.list_cpd_links()])
    pause()


def link_cpd_flow() -> None:
    from education_system.systems.sixth_form.domain.staff.cpd import cpd
    acts = cpd.list_activities()
    label = choose("CPD activity", [f"{a.activity_id} — {a.title} "
                                    f"({a.activity_date})" for a in acts])
    if label is None:
        raise ValueError("No CPD activities yet")
    data.link_cpd_activity(int(label.split(" — ")[0]), _pick_type())
    print("\n  ✓ Linked — attendance now counts in the matrix")
    pause()


def compliance_flow() -> None:
    table(["Training", "Needed", "In date", "Due soon", "Overdue", "Never",
           "%"],
          [(r.name, r.required, r.done, r.due_soon, r.overdue, r.missing,
            r.percent) for r in data.compliance_by_type()])
    if yes_no("Update the governance compliance register?"):
        item = data.update_compliance_register()
        print(f"\n  ✓ Compliance item #{item.item_id}: {item.status}")
    pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Training matrix",            matrix_flow),
    ("Expiring / overdue",         expiring_flow),
    ("One member of staff",        staff_flow),
    ("My training",                my_flow),
    ("─" * 6,                      lambda: None),
    ("Record completion",          record_flow),
    ("List training records",      records_flow),
    ("Archive a record",           archive_flow),
    ("─" * 6,                      lambda: None),
    ("Training types",             types_flow),
    ("New training type",          new_type_flow),
    ("Edit training type",         edit_type_flow),
    ("Who needs a training type",  requirements_flow),
    ("Add standard UK list",       install_flow),
    ("CPD links",                  cpd_links_flow),
    ("Link CPD activity",          link_cpd_flow),
    ("─" * 6,                      lambda: None),
    ("Compliance by training",     compliance_flow),
]


def run() -> None:
    data.init_db()
    run_menu("Mandatory Training", _MENU)


def mandatory_training_menu() -> None:
    """Entry point for the main CLI menu."""
    run()


def dispatch(label: str) -> bool:
    if label != "Mandatory Training":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Mandatory training CLI crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        pause()
    return True
