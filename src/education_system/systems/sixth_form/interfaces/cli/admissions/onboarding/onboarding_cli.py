"""CLI flows for Sixth Form Onboarding."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.admissions.onboarding.onboarding import (
    CATEGORIES,
    CHECKLIST_STATUSES,
    Checklist,
    DEFAULT_CATEGORY,
    DEFAULT_CHECKLIST_STATUS,
    DEFAULT_ITEM_STATUS,
    DEFAULT_TEMPLATE,
    Item,
    ITEM_STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_student() -> str:
    rows = student_data.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or student ID)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
            continue
        match = next((s for s in rows
                       if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _pick_checklist(*, archived: bool = False) -> Checklist:
    rows = data.list_checklists(archived_only=archived)
    if not rows:
        print("    No archived checklists." if archived
              else "    No checklists.")
        raise _UserAbort
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print("\n  Checklists:")
    for i, c in enumerate(rows, 1):
        year = f"  {c.academic_year}" if c.academic_year else ""
        print(f"    {i:>3}) #{c.checklist_id}  {c.student_id}  "
              f"{names.get(c.student_id, '?')[:22]:<22}  "
              f"[{c.status}]{year}")
    while True:
        raw = _input(f"  Pick 1..{len(rows)} (or #id)",
                      allow_empty=False).strip()
        if raw.startswith("#") and raw[1:].isdigit():
            match = next((c for c in rows
                          if c.checklist_id == int(raw[1:])), None)
            if match:
                return match
        elif raw.isdigit() and 1 <= int(raw) <= len(rows):
            return rows[int(raw) - 1]
        print("    No matching checklist.")


def _pick_item(checklist_id: int, *,
               only: Callable[[Item], bool] | None = None) -> Item:
    items = data.list_items(checklist_id=checklist_id)
    if only is not None:
        items = [it for it in items if only(it)]
    if not items:
        print("    No matching items on this checklist.")
        raise _UserAbort
    print("\n  Items:")
    for i, it in enumerate(items, 1):
        mark = "✓" if it.is_done else " "
        req = "*" if it.required else " "
        print(f"    {i:>3}) [{mark}]{req} #{it.item_id}  "
              f"{it.category[:20]:<20}  {it.task_name}")
    while True:
        # A bare number is the list position; "#<id>" is an item id, so
        # the two can never be confused on a filtered list.
        raw = _input(f"  Pick 1..{len(items)} (or #id)",
                      allow_empty=False).strip()
        if raw.startswith("#") and raw[1:].isdigit():
            match = next((it for it in items if it.item_id == int(raw[1:])),
                         None)
            if match:
                return match
        elif raw.isdigit() and 1 <= int(raw) <= len(items):
            return items[int(raw) - 1]
        print("    No matching item.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_checklists(rows: list[Checklist]) -> None:
    if not rows:
        print("\n  (no checklists)")
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Name':<22}  "
          f"{'Status':<14}  {'Due':<10}  {'Assigned':<14}  "
          f"Progress")
    print("  " + "-" * 100)
    detailed = {d.checklist.checklist_id: d
                 for d in data.list_checklists_with_detail(
                     include_archived=True)}
    for c in rows:
        d = detailed.get(c.checklist_id)
        prog = (f"{d.done}/{d.total} (req {d.required_done}/{d.required_total})"
                if d else "—")
        print(f"  {c.checklist_id:>4}  {c.student_id:<10}  "
              f"{names.get(c.student_id, '?')[:22]:<22}  "
              f"{c.status:<14}  {c.due_date or '—':<10}  "
              f"{(c.assigned_to or '—')[:14]:<14}  {prog}")
    print(f"\n  {len(rows)} checklist(s).")


def _item_extras(it: Item) -> list[str]:
    """The evidence / reason lines shown under a task."""
    out: list[str] = []
    if it.evidence_ref:
        out.append(f"record on file: {it.evidence_ref}")
    if it.evidence:
        out.append(f"evidence: {it.evidence}")
    if it.verified_by or it.verified_on:
        out.append(f"verified by {it.verified_by or '?'}"
                   f" on {it.verified_on or '?'}")
    if it.second_check_by:
        out.append(f"second check by {it.second_check_by}"
                   f" on {it.second_check_on or '?'}")
    elif it.awaiting_second_check:
        out.append("AWAITING SECOND CHECK by a different person")
    if it.na_reason and it.status == "N/A":
        out.append(f"N/A reason: {it.na_reason}")
    if it.blocked_reason and it.status == "Blocked":
        out.append(f"blocked: {it.blocked_reason}")
    if it.notes:
        out.append(f"notes: {it.notes}")
    return out


def _print_items(items: list[Item]) -> None:
    if not items:
        print("\n  (no items)")
        return
    print()
    for it in items:
        mark = "✓" if it.is_done else ("!" if it.status == "Blocked"
                                       else "·")
        req = "*" if it.required else " "
        due = f"  due {it.due_date}" if it.due_date else ""
        comp = (f"  done {it.completed_on}"
                f" by {it.completed_by or '?'}"
                if it.completed_on else "")
        print(f"    [{mark}]{req} #{it.item_id:<3}  "
              f"{it.category[:18]:<18}  "
              f"{it.task_name}  ({it.status}){due}{comp}")
        for line in _item_extras(it):
            print(f"                 - {line}")


# ── Checklist flows ────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Checklists ═══")
    _print_checklists(data.list_checklists())
    _pause()


def list_open() -> None:
    print("\n═══ Open Checklists ═══")
    _print_checklists(data.list_checklists(open_only=True))
    _pause()


def list_overdue() -> None:
    print("\n═══ Overdue Checklists ═══")
    _print_checklists(data.list_checklists(overdue_only=True))
    _pause()


def view_checklist() -> None:
    print("\n═══ View Checklist ═══")
    try:
        c = _pick_checklist()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    detail = data.get_checklist_detail(c.checklist_id)
    assert detail is not None
    print()
    print(f"    #{c.checklist_id}  {c.name}")
    print(f"    Student        : {c.student_id}  {detail.student_name}")
    print(f"    Template       : {c.template_name or '—'}")
    print(f"    Academic year  : {c.academic_year or '—'}")
    print(f"    Status         : {c.status}"
          + (f"  ({c.status_reason})" if c.status_reason else ""))
    if c.is_archived:
        print(f"    ARCHIVED       : {c.archived_at} by "
              f"{c.archived_by or '?'} — {c.archived_reason or ''}")
    print(f"    Assigned to    : {c.assigned_to or '—'}")
    print(f"    Started on     : {c.started_on or '—'}")
    print(f"    Due date       : {c.due_date or '—'}")
    print(f"    Completed on   : {c.completed_on or '—'}")
    print(f"    Progress       : {detail.done_items}/{detail.total_items} "
          f"({detail.percent_complete}%)  ·  "
          f"required {detail.required_done}/{detail.required_total}")
    if c.notes:
        print("\n    Notes:")
        for line in c.notes.splitlines():
            print(f"      {line}")
    _print_items(detail.items)
    _pause()


# ── Access / reason helpers ───────────────────────────────────────

READ_ONLY_MESSAGE = ("You have read-only access to onboarding. Changes "
                     "need the admissions or student-management "
                     "permission — ask someone who has it.")

#: Errors a write can raise that the user should simply be shown.
_REFUSED = (ValidationError, PermissionError, ValueError)


def _writer() -> bool:
    """True if the signed-in user may change onboarding; otherwise say
    so (no write prompts are shown)."""
    try:
        ok = data.can_write()
    except Exception:  # noqa: BLE001 — no principal = read-only
        ok = False
    if not ok:
        print(f"\n  {READ_ONLY_MESSAGE}")
        _pause()
    return ok


def _ask_text(prompt: str, *, minimum: int = 5, default: str = "") -> str:
    """A free-text answer of at least *minimum* real characters; blank
    cancels."""
    while True:
        raw = _input(f"{prompt} (blank = cancel)", default=default)
        if not raw:
            raise _UserAbort
        if len(raw.replace(" ", "")) >= minimum:
            return raw
        print(f"    Please say a bit more (at least {minimum} characters).")


def _ask_evidence(it: Item) -> str | None:
    """Written evidence, asked only when the task's record is not on file
    (the domain's evidence rule says so). Notes never count."""
    problem = data.evidence_problem(it)
    if problem is None:
        return None
    print(f"    ⚠ {problem}")
    if data.needs_second_check(it):
        print("    Written evidence for this task must then be confirmed "
              "by a different member of staff (Confirm Evidence).")
    return _ask_text("Where is the evidence?")


def _status_answers(it: Item, status: str) -> tuple[str | None, str | None]:
    """(evidence, reason) for moving *it* to *status*."""
    if status == "Done":
        return _ask_evidence(it), None
    if status == "N/A":
        if it.key in data.ID_ITEMS:
            raise ValidationError(
                f"'{it.task_name}' can't be N/A — an ID / right-to-study "
                "check always applies. Record it, or remove the task if it "
                "was added in error.")
        return None, _ask_text("Why does this task not apply?")
    if status == "Blocked":
        return None, _ask_text("What is blocking it?")
    return None, None


def _chk_reason(status: str, current: str | None = None) -> str | None:
    if status in ("Cancelled", "On Hold"):
        return _ask_text(f"Why is the checklist {status.lower()}?",
                         default=current or "")
    return None


def _refused(e: Exception) -> None:
    print(f"\n  ✗ {e}")
    _pause()


# ── Checklist write flows ─────────────────────────────────────────

def _suggest(sid: str) -> Any:
    """workflow.choose_template's suggestion for the learner, printed with
    its reasons and the signals it could not check (None if it failed)."""
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        workflow,
    )
    try:
        choice = workflow.choose_template(sid)
    except Exception as e:  # noqa: BLE001 — the suggestion is optional
        print(f"\n    (No suggestion: {e})")
        return None
    print(f"\n    Suggested: {choice.template}  —  {choice.label}")
    if choice.addons:
        print(f"    Add-ons  : {', '.join(choice.addons)}")
    for r in choice.reasons:
        print(f"      because {r}")
    for n in choice.not_checked:
        print(f"      not checked: {n}")
    for key, why in choice.not_applicable.items():
        print(f"      will be N/A: {key} ({why})")
    return choice


def _apply_addons(checklist_id: int, choice: Any) -> None:
    """Add the suggested add-on templates and mark add-on tasks that do not
    apply as N/A (as workflow.open_for_learner does)."""
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        templates as _tpl,
    )
    for name in choice.addons:
        try:
            added = _tpl.apply_template(checklist_id, name)
            print(f"    + {name}: {len(added)} task(s) added")
        except _REFUSED as e:
            print(f"    ✗ {name}: {e}")
    for it in data.list_items(checklist_id=checklist_id):
        why = choice.not_applicable.get(it.key)
        if why and it.status == "Pending":
            try:
                data.set_item_status(it.item_id, "N/A", reason=why)
                print(f"    N/A: {it.task_name}")
            except _REFUSED as e:
                print(f"    ✗ {it.task_name}: {e}")


def new_checklist() -> None:
    print("\n═══ New Checklist ═══")
    if not _writer():
        return
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        templates as _tpl,
    )
    try:
        sid = _pick_student()
        choice = _suggest(sid)
        templates = _tpl.template_names()
        suggested = (choice.template if choice is not None
                     and choice.template in templates else DEFAULT_TEMPLATE)
        template = _pick_from("Template", templates, default=suggested)
        use_addons = bool(choice is not None and choice.addons and _yes_no(
            f"Add the suggested add-ons ({', '.join(choice.addons)})?",
            default=True))
        year = _input("Academic year (blank = from the enrolment / "
                      "current year)")
        name = _input("Checklist name (blank = auto)",
                       default="")
        due = _input("Due date (YYYY-MM-DD)")
        assigned = _input("Assigned to")
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    payload: dict[str, Any] = {
        "student_id": sid,
        "template_name": template,
        "name": name or None,
        "due_date": due or None,
        "assigned_to": assigned or None,
        "notes": notes or None,
        "status": DEFAULT_CHECKLIST_STATUS,
    }
    if year:
        payload["academic_year"] = year
    if choice is not None:
        payload["learner_type"] = choice.label
    try:
        c = data.create_checklist(payload)
    except _REFUSED as e:
        return _refused(e)
    n = len(data.list_items(checklist_id=c.checklist_id))
    print(f"\n  ✓ Created checklist #{c.checklist_id} for "
          f"{c.academic_year or 'no year'} ({n} items seeded)")
    if use_addons:
        _apply_addons(c.checklist_id, choice)
    _pause()


def edit_checklist() -> None:
    print("\n═══ Edit Checklist ═══")
    if not _writer():
        return
    try:
        c = _pick_checklist()
        name = _input("Name", default=c.name, allow_empty=False)
        status = _pick_from("Status", list(CHECKLIST_STATUSES),
                              default=c.status)
        reason = (_chk_reason(status, c.status_reason)
                  if status != c.status else None)
        due = _input("Due date", default=c.due_date or "")
        assigned = _input("Assigned to", default=c.assigned_to or "")
        notes = _input("Notes", default=c.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_checklist(c.checklist_id, {
            "name": name, "status": status, "status_reason": reason,
            "due_date": due or None,
            "assigned_to": assigned or None,
            "notes": notes or None,
        })
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ Updated #{c.checklist_id}")
    _pause()


def set_chk_status_flow() -> None:
    print("\n═══ Change Checklist Status ═══")
    if not _writer():
        return
    try:
        c = _pick_checklist()
        new_status = _pick_from("New status",
                                   list(CHECKLIST_STATUSES),
                                   default=c.status)
        reason = _chk_reason(new_status, c.status_reason)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_checklist_status(c.checklist_id, new_status, reason=reason)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ #{c.checklist_id} → {new_status}"
          + (f" ({reason})" if reason else ""))
    _pause()


def delete_checklist_flow() -> None:
    print("\n═══ Delete (Archive) Checklist ═══")
    if not _writer():
        return
    try:
        c = _pick_checklist()
        print(f"\n    Checklist #{c.checklist_id} and its tasks are kept as "
              "an archived record and can be restored later.")
        reason = _ask_text("Why is it being deleted?")
        if _input(f"Archive checklist #{c.checklist_id}? Type 'yes'",
                  default="no").lower() != "yes":
            raise _UserAbort
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        ok = data.delete_checklist(c.checklist_id, reason=reason)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ Archived #{c.checklist_id} (see Archived Checklists)"
          if ok else f"\n  #{c.checklist_id} was already archived.")
    _pause()


# ── Item flows ────────────────────────────────────────────────────

def _signed_in() -> str | None:
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or None
    except Exception:  # noqa: BLE001
        return None


def _report_item(it: Item, done: str) -> None:
    if it.awaiting_second_check:
        print(f"\n  ✓ Evidence recorded for #{it.item_id} ({it.task_name}). "
              "It stays In Progress until a different member of staff "
              "confirms it (Confirm Evidence).")
    else:
        print(f"\n  ✓ {done} #{it.item_id} ({it.task_name}) — now {it.status}")


def tick_item_flow() -> None:
    print("\n═══ Tick Off Item ═══")
    if not _writer():
        return
    try:
        c = _pick_checklist()
        it = _pick_item(c.checklist_id, only=lambda i: not i.is_done)
        who = _input("Completed by", default=_signed_in() or "")
        evidence = _ask_evidence(it)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = data.tick(it.item_id, completed_by=who or None,
                        evidence=evidence)
    except _REFUSED as e:
        return _refused(e)
    _report_item(out, "Ticked")
    _pause()


def untick_item_flow() -> None:
    print("\n═══ Un-tick Item ═══")
    if not _writer():
        return
    try:
        c = _pick_checklist()
        it = _pick_item(c.checklist_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.untick(it.item_id)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ Re-opened #{it.item_id}")
    _pause()


def set_item_status_flow() -> None:
    print("\n═══ Change Item Status ═══")
    if not _writer():
        return
    try:
        c = _pick_checklist()
        it = _pick_item(c.checklist_id)
        new_status = _pick_from("New status", list(ITEM_STATUSES),
                                  default=it.status)
        evidence, reason = _status_answers(it, new_status)
        who = _input("Completed by",
                     default=it.completed_by or _signed_in() or "") \
            if new_status in ("Done", "N/A") else ""
    except _UserAbort:
        print("\n  Cancelled.")
        return
    except _REFUSED as e:
        return _refused(e)
    try:
        out = data.set_item_status(it.item_id, new_status,
                                   completed_by=who or None,
                                   evidence=evidence, reason=reason)
    except _REFUSED as e:
        return _refused(e)
    _report_item(out, "Changed")
    _pause()


def confirm_evidence_flow() -> None:
    print("\n═══ Confirm Evidence (second check) ═══")
    if not _writer():
        return
    try:
        c = _pick_checklist()
        it = _pick_item(c.checklist_id,
                        only=lambda i: i.awaiting_second_check)
        print(f"\n    {it.task_name}")
        print(f"    Evidence    : {it.evidence}")
        print(f"    Recorded by : {it.verified_by or '?'} on "
              f"{it.verified_on or '?'}")
        if it.verified_by and it.verified_by == _signed_in():
            print("\n  ✗ You recorded this evidence — the second check must "
                  "be made by someone else.")
            return _pause()
        note = _input("Note (optional)")
        if not _yes_no("Confirm you have seen this evidence?", default=False):
            raise _UserAbort
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = data.confirm_evidence(it.item_id, note=note or None)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ Second check recorded — #{out.item_id} is now {out.status}")
    _pause()


def new_item_flow() -> None:
    print("\n═══ New Item ═══")
    if not _writer():
        return
    try:
        c = _pick_checklist()
        task = _input("Task name", allow_empty=False)
        cat = _pick_from("Category", list(CATEGORIES),
                            default=DEFAULT_CATEGORY)
        required = _yes_no("Required for completion?", default=True)
        due = _input("Due date (YYYY-MM-DD)")
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        it = data.create_item({
            "checklist_id": c.checklist_id,
            "task_name": task, "category": cat,
            "required": required, "status": DEFAULT_ITEM_STATUS,
            "due_date": due or None, "notes": notes or None,
            "source": "manual",
        })
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ Added item #{it.item_id} {task!r}")
    _pause()


def edit_item_flow() -> None:
    print("\n═══ Edit Item ═══")
    if not _writer():
        return
    try:
        c = _pick_checklist()
        it = _pick_item(c.checklist_id)
        task = _input("Task name", default=it.task_name,
                        allow_empty=False)
        cat = _pick_from("Category", list(CATEGORIES),
                            default=it.category)
        required = _yes_no("Required?", default=it.required)
        status = _pick_from("Status", list(ITEM_STATUSES),
                              default=it.status)
        evidence = reason = None
        if status != it.status:
            evidence, reason = _status_answers(it, status)
        due = _input("Due date", default=it.due_date or "")
        notes = _input("Notes (never counts as evidence)",
                       default=it.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    except _REFUSED as e:
        return _refused(e)
    payload: dict[str, Any] = {
        "task_name": task, "category": cat,
        "required": required,
        "due_date": due or None, "notes": notes or None,
    }
    if status != it.status:
        payload["status"] = status
        if evidence:
            payload["evidence"] = evidence
        if status == "N/A":
            payload["na_reason"] = reason
        elif status == "Blocked":
            payload["blocked_reason"] = reason
    try:
        data.update_item(it.item_id, payload)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ Updated #{it.item_id}")
    _pause()


def delete_item_flow() -> None:
    print("\n═══ Delete Item ═══")
    if not _writer():
        return
    try:
        c = _pick_checklist()
        it = _pick_item(c.checklist_id)
        if _input(f"Delete item #{it.item_id} ({it.task_name})? Type 'yes'",
                  default="no").lower() != "yes":
            raise _UserAbort
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        ok = data.delete_item(it.item_id)
    except _REFUSED as e:
        return _refused(e)
    if ok:
        print(f"\n  ✓ Deleted #{it.item_id}")
    _pause()


# ── Templates / Summary ───────────────────────────────────────────

def show_templates() -> None:
    _cli("templates_cli").show_templates()


def summary_flow() -> None:
    print("\n═══ Onboarding Summary ═══")
    try:
        win = int(_input("Upcoming-due window (days)", default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=win)
    print(f"\n  Total checklists   : {summ.total_checklists}")
    print(f"  Open               : {summ.open_count}")
    print(f"  Completed          : {summ.completed_count}")
    print(f"  Overdue            : {summ.overdue}")
    print(f"  Upcoming due ({win}d) : {summ.upcoming_due}")
    print(f"\n  Items total        : {summ.items_total}")
    print(f"  Items done         : {summ.items_done}")
    print(f"  Items overdue      : {summ.items_overdue}")
    print("\n  By checklist status:")
    for s in CHECKLIST_STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    print("\n  Items by category:")
    for c in CATEGORIES:
        n = summ.by_category.get(c, 0)
        if n:
            print(f"    {c:<24} : {n}")
    _pause()


def _records():
    from education_system.systems.sixth_form.interfaces.cli.admissions.onboarding import (
        records_cli,
    )
    return records_cli


def _cli(name: str) -> Any:
    """A sibling CLI module, imported on first use."""
    import importlib
    return importlib.import_module(
        "education_system.systems.sixth_form.interfaces.cli.admissions."
        f"onboarding.{name}")


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Open",              list_open),
    ("List Overdue",           list_overdue),
    ("List All",               list_all),
    ("View Checklist",         view_checklist),
    ("New Checklist",          new_checklist),
    ("Edit Checklist",         edit_checklist),
    ("Change Status",          set_chk_status_flow),
    ("Delete Checklist",       delete_checklist_flow),
    ("─" * 6,                  lambda: None),
    ("Tick Off Item",          tick_item_flow),
    ("Un-tick Item",           untick_item_flow),
    ("Change Item Status",     set_item_status_flow),
    ("New Item",               new_item_flow),
    ("Edit Item",              edit_item_flow),
    ("Delete Item",            delete_item_flow),
    ("─" * 6,                  lambda: None),
    ("Consents (GDPR)",        lambda: __import__(
        "education_system.systems.sixth_form.interfaces.cli.admissions."
        "onboarding.consent_cli", fromlist=["x"]).consents_flow()),
    ("Show Templates",         show_templates),
    ("Summary",                summary_flow),
    ("Confirm Evidence (second check)", confirm_evidence_flow),
    ("Archived Checklists",    lambda: _records().list_archived()),
    ("Restore Checklist",      lambda: _records().restore_flow()),
    ("History",                lambda: _records().history_flow()),
    ("Photo & ID Check",       lambda: _records().identity_flow()),
    ("Outstanding Tasks",      lambda: _records().outstanding_flow()),
    ("Sync Consents with GDPR Records",
     lambda: _records().sync_consents_flow()),
    ("Templates (view / edit / retire)",
     lambda: _cli("templates_cli").manage_flow()),
    ("Apply Template to Checklist",
     lambda: _cli("templates_cli").apply_flow()),
    ("My Queue",               lambda: _cli("workflow_cli").queue_flow()),
    ("Bulk Set Task Status",
     lambda: _cli("workflow_cli").bulk_status_flow()),
    ("Bulk Assign Tasks",
     lambda: _cli("workflow_cli").bulk_assign_flow()),
    ("Open Checklists for a Cohort",
     lambda: _cli("workflow_cli").cohort_flow()),
    ("Year 13 Re-onboarding",
     lambda: _cli("workflow_cli").reonboard_flow()),
    ("Re-check Tasks from Records",
     lambda: _cli("workflow_cli").resync_flow()),
    ("Induction Sessions",     lambda: _cli("induction_cli").run()),
    ("Dashboard",              lambda: _cli("reports_cli").dashboard_flow()),
    ("Outstanding Tasks Report",
     lambda: _cli("reports_cli").outstanding_report_flow()),
    ("Export Report (CSV / PDF)",
     lambda: _cli("reports_cli").export_flow()),
    ("Link Bursary Application",
     lambda: _cli("workflow_cli").bursary_flow()),
    ("Chase Log",              lambda: _cli("reports_cli").chase_log_flow()),
]


def run() -> None:
    while True:
        print("\n── Onboarding ──")
        if not data.can_write():
            print("  (read-only access: you can view, not change)")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
                print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Onboarding CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Onboarding":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Onboarding CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
