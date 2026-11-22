"""CLI: onboarding work queues, bulk task changes, opening checklists for
a cohort, Year 13 re-onboarding, re-checking tasks from records and
linking a bursary application."""

from __future__ import annotations

import re
from typing import Any

from education_system.systems.sixth_form.domain.admissions.onboarding import (
    bursary_link,
    evidence_sources,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    templates as tpl,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    workflow as wf,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.onboarding.onboarding_cli import (
    _REFUSED,
    _ask_text,
    _input,
    _pause,
    _pick_checklist,
    _pick_from,
    _refused,
    _signed_in,
    _UserAbort,
    _writer,
    _yes_no,
)

_KEEP = "(keep as is)"
_CLEAR = "(clear)"
_EACH = "(each learner's suggested template)"


# ── Shared helpers ────────────────────────────────────────────────

def current_year() -> str:
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _enr,
    )
    return _enr.current_academic_year()


def previous_year(year: str) -> str:
    """"2026/27" -> "2025/26" (the year before, same format)."""
    m = re.fullmatch(r"(\d{4})([/-])(\d{2}|\d{4})", (year or "").strip())
    if not m:
        return ""
    start = int(m.group(1)) - 1
    end = str(start + 1)
    return f"{start}{m.group(2)}{end[-len(m.group(3)):]}"


def parse_multi(raw: str, ids: list[Any]) -> list[Any]:
    """Positions ("1,3,5-7"), ids ("#12") or "all" -> chosen ids, in list
    order. ``ids`` is the list in display order. Raises ValueError."""
    raw = (raw or "").strip().lower()
    if raw == "all":
        return list(ids)
    chosen: list[Any] = []
    for tok in (t.strip() for t in raw.replace(" ", ",").split(",")):
        if not tok:
            continue
        if tok.startswith("#"):
            hit = next((i for i in ids if str(i).lower() == tok[1:]), None)
            if hit is None:
                raise ValueError(f"no {tok} in the list")
            chosen.append(hit)
        elif re.fullmatch(r"\d+-\d+", tok):
            a, b = (int(x) for x in tok.split("-"))
            if not (1 <= a <= b <= len(ids)):
                raise ValueError(f"{tok} is out of range")
            chosen += ids[a - 1:b]
        elif tok.isdigit() and 1 <= int(tok) <= len(ids):
            chosen.append(ids[int(tok) - 1])
        else:
            raise ValueError(f"{tok!r} is not a position, #id or range")
    return list(dict.fromkeys(chosen))


def ask_multi(label: str, ids: list[Any]) -> list[Any]:
    while True:
        raw = _input(f"{label} (e.g. 1,3,5-7 or #id; 'all')",
                     allow_empty=False)
        try:
            out = parse_multi(raw, ids)
        except ValueError as e:
            print(f"    {e}")
            continue
        if out:
            return out
        print("    Nothing chosen.")


def _queue_who() -> str:
    roles = list(tpl.OWNER_ROLES)
    who = _pick_from("Whose queue", ["Me", *roles, "Another member of staff"],
                     default="Me")
    if who == "Me":
        me = _signed_in()
        if not me:
            print("    You are not signed in as a member of staff — pick a "
                  "role queue instead.")
            raise _UserAbort
        return me
    if who == "Another member of staff":
        return _input("Staff id, login or e-mail", allow_empty=False)
    return who


def _print_queue(rows: list[wf.QueueRow]) -> None:
    if not rows:
        print("\n  (nothing in this queue)")
        return
    print(f"\n  {'#':>3}  {'Item':>5}  {'Due':<10}  {'Student':<10}  "
          f"{'Name':<20}  {'Status':<11}  {'Why':<12}  Task")
    print("  " + "-" * 104)
    for n, q in enumerate(rows, 1):
        it = q.item
        late = "LATE " if q.overdue else ""
        print(f"  {n:>3}  {it.item_id:>5}  {it.due_date or '—':<10}  "
              f"{q.student_id:<10}  {q.student_name[:20]:<20}  "
              f"{it.status:<11}  {q.why[:12]:<12}  {late}{it.task_name}")


def _load_queue() -> list[wf.QueueRow]:
    who = _queue_who()
    overdue = _yes_no("Overdue only?", default=False)
    year = _input("Academic year ('all' for every year)",
                  default=current_year())
    rows = wf.my_queue(who, overdue_only=overdue,
                       academic_year=None if year.lower() == "all" else year)
    print(f"\n  Queue for {who}"
          + (" (overdue only)" if overdue else "") + ":")
    _print_queue(rows)
    return rows


def queue_flow() -> None:
    print("\n═══ My Queue ═══")
    try:
        rows = _load_queue()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  {len(rows)} open task(s), "
          f"{sum(1 for q in rows if q.overdue)} overdue.")
    _pause()


def _pick_tasks() -> list[int]:
    """Item ids chosen from a queue or from one checklist."""
    src = _pick_from("Choose tasks from", ["A queue", "A checklist"],
                     default="A queue")
    if src == "A queue":
        rows = _load_queue()
        ids = [q.item.item_id for q in rows]
    else:
        c = _pick_checklist()
        items = data.list_items(checklist_id=c.checklist_id)
        print()
        for n, it in enumerate(items, 1):
            print(f"    {n:>3}) #{it.item_id:<5} [{it.status:<11}] "
                  f"{it.task_name}")
        ids = [it.item_id for it in items]
    if not ids:
        print("    No tasks to choose from.")
        raise _UserAbort
    return ask_multi("Tasks", ids)


def _show_bulk(res: wf.BulkResult) -> None:
    print()
    for line in res.lines():
        print(f"  {'✓' if not line.startswith('#') else '✗'} {line}")
    _pause()


def bulk_status_flow() -> None:
    print("\n═══ Bulk Set Task Status ═══")
    if not _writer():
        return
    try:
        ids = _pick_tasks()
        status = _pick_from("New status", list(data.ITEM_STATUSES))
        reason = evidence = None
        if status == "N/A":
            reason = _ask_text("Why do these tasks not apply?")
        elif status == "Blocked":
            reason = _ask_text("What is blocking them?")
        elif status == "Done":
            print("    Tasks whose record is on file tick from the record; "
                  "others need written evidence (or are refused).")
            evidence = _input("Written evidence for the rest (blank = none)"
                              ) or None
        who = (_input("Completed by", default=_signed_in() or "")
               if status in ("Done", "N/A") else "")
        if not _yes_no(f"Set {len(ids)} task(s) to {status}?", default=True):
            raise _UserAbort
    except _UserAbort:
        print("\n  Cancelled.")
        return
    except _REFUSED as e:
        return _refused(e)
    try:
        res = wf.bulk_set_status(ids, status, reason=reason,
                                 evidence=evidence,
                                 completed_by=who or None)
    except _REFUSED as e:
        return _refused(e)
    _show_bulk(res)


def bulk_assign_flow() -> None:
    print("\n═══ Bulk Assign Tasks ═══")
    if not _writer():
        return
    try:
        ids = _pick_tasks()
        raw = _input("Assign to (staff id / login / e-mail; '-' = clear; "
                     "blank = keep)")
        owner = _pick_from("Owner role", [_KEEP, _CLEAR, *tpl.OWNER_ROLES],
                           default=_KEEP)
        kw: dict[str, Any] = {}
        if raw == "-":
            kw["assignee"] = None
        elif raw:
            kw["assignee"] = raw
        if owner == _CLEAR:
            kw["owner_role"] = None
        elif owner != _KEEP:
            kw["owner_role"] = owner
        if not kw:
            print("    Nothing to change.")
            raise _UserAbort
        if not _yes_no(f"Change {len(ids)} task(s)?", default=True):
            raise _UserAbort
    except _UserAbort:
        print("\n  Cancelled.")
        return
    except _REFUSED as e:
        return _refused(e)
    try:
        res = wf.bulk_assign(ids, **kw)
    except _REFUSED as e:
        return _refused(e)
    _show_bulk(res)


# ── Cohorts ───────────────────────────────────────────────────────

def _print_lines(lines: list[wf.CohortLine]) -> None:
    print()
    for ln in lines:
        mark = {"opened": "✓", "failed": "✗"}.get(ln.result, "·")
        print(f"  {mark} {ln.line()}")
    counts: dict[str, int] = {}
    for ln in lines:
        counts[ln.result] = counts.get(ln.result, 0) + 1
    print("\n  " + (", ".join(f"{n} {k}" for k, n in counts.items())
                    or "No learners matched."))
    _pause()


def cohort_flow() -> None:
    print("\n═══ Open Checklists for a Cohort ═══")
    if not _writer():
        return
    try:
        year = _input("Academic year", default=current_year())
        yg = _pick_from("Year group", ["All", "12", "13"], default="All")
        tg = _input("Tutor group (blank = all)")
        template = _pick_from("Template", [_EACH, *tpl.template_names()],
                              default=_EACH)
        print("    Learners who already have a checklist for that year are "
              "skipped, so running this again is safe.")
        if not _yes_no(f"Open checklists for live enrolments in {year}?",
                       default=True):
            raise _UserAbort
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        lines = wf.bulk_open_for_cohort(
            year, year_group=None if yg == "All" else int(yg),
            tutor_group=tg or None,
            template=None if template == _EACH else template)
    except _REFUSED as e:
        return _refused(e)
    _print_lines(lines)


def reonboard_flow() -> None:
    print("\n═══ Year 13 Re-onboarding ═══")
    if not _writer():
        return
    try:
        to_year = _input("Year 13 academic year", default=current_year())
        from_year = _input("Their Year 12 academic year",
                           default=previous_year(to_year),
                           allow_empty=False)
        print("    Opens a short 'Year 13 return' checklist for each learner "
              f"in Year 13 in {to_year} who was in Year 12 here in "
              f"{from_year}. Transfers-in and learners who already have a "
              "checklist are skipped.")
        if not _yes_no("Go ahead?", default=True):
            raise _UserAbort
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        lines = wf.reonboard_cohort(from_year, to_year)
    except _REFUSED as e:
        return _refused(e)
    _print_lines(lines)


# ── Re-check from records ─────────────────────────────────────────

def resync_flow() -> None:
    print("\n═══ Re-check Tasks from Records ═══")
    if not _writer():
        return
    try:
        scope = _pick_from("Re-check", ["One checklist",
                                        "All open checklists"],
                           default="One checklist")
        if scope == "One checklist":
            c = _pick_checklist()
            year = None
        else:
            raw = _input("Academic year ('all' for every year)",
                         default=current_year())
            year = None if raw.lower() == "all" else raw
            c = None
        print("    Open tasks whose record now exists are ticked; tasks "
              "ticked from a record that has gone are re-opened. Written "
              "evidence, N/A, consent and ID tasks are left alone.")
        if not _yes_no("Go ahead?", default=True):
            raise _UserAbort
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        res = (evidence_sources.resync(c.checklist_id) if c is not None
               else evidence_sources.resync_all(academic_year=year))
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ {res.summary}")
    for t in res.ticked:
        print(f"    ticked: {t}")
    for t in res.reopened:
        print(f"    re-opened: {t}")
    for t in res.errors:
        print(f"    ✗ {t}")
    _pause()


# ── Bursary ───────────────────────────────────────────────────────

def _link_application() -> None:
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries,
    )
    c = _pick_checklist()
    apps = bursaries.list_applications(student_id=c.student_id)
    if not apps:
        print(f"    {c.student_id} has no bursary applications — open one "
              "in Bursaries first.")
        raise _UserAbort
    print()
    for n, a in enumerate(apps, 1):
        print(f"    {n:>3}) #{a.application_id:<5} {a.academic_year or '—':<9} "
              f"{a.bursary_type[:24]:<24}  {a.status}")
    while True:
        raw = _input(f"Pick 1..{len(apps)} (or #id)", allow_empty=False)
        if raw.startswith("#") and raw[1:].isdigit():
            app = next((a for a in apps
                        if a.application_id == int(raw[1:])), None)
        elif raw.isdigit() and 1 <= int(raw) <= len(apps):
            app = apps[int(raw) - 1]
        else:
            app = None
        if app is not None:
            break
        print("    No matching application.")
    if c.academic_year and app.academic_year and \
            app.academic_year != c.academic_year:
        print(f"    Note: the application is for {app.academic_year}, the "
              f"checklist for {c.academic_year}.")
    required = _yes_no("Make the bursary task required?", default=True)
    try:
        it = bursary_link.link_application(c.checklist_id, app.application_id,
                                           required=required)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ '{it.task_name}' (#{it.item_id}) linked to application "
          f"#{app.application_id} ({app.status}); task is {it.status}."
          + ("" if it.is_done else " It ticks once the application is "
             "submitted (or use Sync submitted applications)."))
    _pause()


def _sync_bursaries() -> None:
    raw = _input("Academic year ('all' for every year)",
                 default=current_year())
    try:
        lines = bursary_link.sync_open_items(
            None if raw.lower() == "all" else raw)
    except _REFUSED as e:
        return _refused(e)
    print()
    for ln in lines or ["No open bursary tasks had a submitted application."]:
        print(f"  {ln}")
    _pause()


def bursary_flow() -> None:
    print("\n═══ Bursary Application ↔ Onboarding ═══")
    if not _writer():
        return
    try:
        action = _pick_from("Action", [
            "Link a bursary application to a checklist",
            "Sync: tick tasks whose application has been submitted"],
            default="Link a bursary application to a checklist")
        if action.startswith("Link"):
            _link_application()
        else:
            _sync_bursaries()
    except _UserAbort:
        print("\n  Cancelled.")
