"""CLI: onboarding templates — list, view (tasks and saved versions),
create / edit (each save is a new version with a note), retire /
reactivate with a reason, and apply a template to a checklist."""

from __future__ import annotations

from typing import Any

from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    templates as tpl,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.onboarding.onboarding_cli import (
    _REFUSED,
    _ask_text,
    _input,
    _pause,
    _pick_checklist,
    _pick_from,
    _refused,
    _UserAbort,
    _writer,
    _yes_no,
)

_NONE = "(none)"


# ── Showing ───────────────────────────────────────────────────────

def _print_list(rows: list[tpl.Template]) -> None:
    if not rows:
        print("\n  (no templates)")
        return
    print(f"\n  {'#':>3}  {'Name':<30}  {'Kind':<6}  {'Learner type':<28}  "
          f"{'Ver':>3}  {'Tasks':>5}  State")
    print("  " + "-" * 96)
    for n, t in enumerate(rows, 1):
        print(f"  {n:>3}  {t.name[:30]:<30}  {t.kind:<6}  "
              f"{(t.learner_type or '—')[:28]:<28}  {t.version:>3}  "
              f"{len(t.items):>5}  {'active' if t.active else 'RETIRED'}")


def _print_items(items: list[tpl.TemplateItem]) -> None:
    if not items:
        print("    (no tasks)")
        return
    for n, i in enumerate(items, 1):
        req = "*" if i.required else " "
        sens = "  [sensitive]" if i.sensitive else ""
        key = f"  (rule: {i.key})" if i.key != i.task else ""
        print(f"    {n:>3}) {req} {i.category[:20]:<20}  "
              f"day {i.due_offset_days:>+4}  {(i.owner_role or '—'):<12}  "
              f"{i.task}{key}{sens}")


def _print_template(t: tpl.Template) -> None:
    print(f"\n    {t.name}  (version {t.version}, "
          f"{'active' if t.active else 'RETIRED'})")
    print(f"    Kind         : {t.kind}")
    print(f"    Learner type : {t.learner_type or '—'}")
    print(f"    Description  : {t.description or '—'}")
    print(f"    Saved        : {t.updated_at or '?'} by {t.updated_by or '?'}")
    print("    Tasks (* = required; day = due offset from the start date):")
    _print_items(t.items)


def _print_versions(name: str) -> None:
    rows = tpl.versions(name)
    print(f"\n    Versions of {name} (newest first):")
    for v in rows:
        print(f"      v{v['version']:<3} {v['saved_at'] or '?'}  "
              f"{v['saved_by'] or '?':<12}  {v['tasks']} task(s)  "
              f"{v['note'] or ''}")
        if v.get("changes"):
            print(f"            changes: {v['changes']}")


def show_templates() -> None:
    """Every active template with its tasks (the "Show Templates" option)."""
    print("\n═══ Templates ═══")
    for t in tpl.list_templates():
        req = sum(1 for i in t.items if i.required)
        print(f"\n  {t.name}  [{t.kind}"
              + (f", {t.learner_type}" if t.learner_type else "")
              + f", v{t.version}]  ({len(t.items)} items, {req} required)")
        _print_items(t.items)
    _pause()


def _pick_template(*, include_inactive: bool = True,
                   only: Any = None) -> tpl.Template:
    rows = tpl.list_templates(include_inactive=include_inactive)
    if only is not None:
        rows = [t for t in rows if only(t)]
    if not rows:
        print("    No matching templates.")
        raise _UserAbort
    _print_list(rows)
    while True:
        raw = _input(f"Pick 1..{len(rows)} (or #id)", allow_empty=False)
        if raw.startswith("#") and raw[1:].isdigit():
            match = next((t for t in rows
                          if t.template_id == int(raw[1:])), None)
            if match:
                return match
        elif raw.isdigit() and 1 <= int(raw) <= len(rows):
            return rows[int(raw) - 1]
        print("    No matching template.")


# ── Flows ─────────────────────────────────────────────────────────

def list_flow() -> None:
    print("\n═══ Onboarding Templates ═══")
    _print_list(tpl.list_templates(include_inactive=True))
    _pause()


def view_flow() -> None:
    print("\n═══ View Template ═══")
    t = _pick_template()
    _print_template(t)
    _print_versions(t.name)
    _pause()


def view_version_flow() -> None:
    print("\n═══ View an Earlier Version ═══")
    t = _pick_template()
    _print_versions(t.name)
    raw = _input("Version number", default=str(t.version))
    if not raw.isdigit():
        print("    Enter a version number.")
        return _pause()
    try:
        old = tpl.get_template(t.name, version=int(raw))
    except _REFUSED as e:
        return _refused(e)
    if old is not None:
        _print_template(old)
    _pause()


def _item_dict(i: tpl.TemplateItem) -> dict[str, Any]:
    return {"key": i.key, "task": i.task, "category": i.category,
            "required": i.required, "due_offset_days": i.due_offset_days,
            "owner_role": i.owner_role, "sensitive": i.sensitive}


def _ask_task(cur: dict[str, Any] | None = None) -> dict[str, Any]:
    cur = dict(cur or {})
    task = _input("Task name", default=cur.get("task", ""),
                  allow_empty=False)
    cat = _pick_from("Category", list(data.CATEGORIES),
                     default=cur.get("category") or data.DEFAULT_CATEGORY)
    required = _yes_no("Required?", default=cur.get("required", True))
    while True:
        raw = _input("Due offset in days from the start date",
                     default=str(cur.get("due_offset_days",
                                         tpl.CATEGORY_OFFSET.get(cat, 14))))
        try:
            offset = int(raw)
            break
        except ValueError:
            print("    Enter a whole number of days (e.g. 7 or -3).")
    owner = _pick_from("Owner (whose queue it lands in)",
                       [_NONE, *tpl.OWNER_ROLES],
                       default=(cur.get("owner_role") or _NONE) if cur
                       else tpl.CATEGORY_OWNER.get(cat, _NONE))
    sensitive = _yes_no("Sensitive (hidden from readers without rights)?",
                        default=bool(cur.get("sensitive")))
    out = {"task": task, "category": cat, "required": required,
           "due_offset_days": offset,
           "owner_role": None if owner == _NONE else owner,
           "sensitive": sensitive}
    if cur.get("key"):
        out["key"] = cur["key"]          # a rename keeps the evidence rule
    return out


def _pick_row(items: list[dict[str, Any]], label: str) -> int:
    if not items:
        print("    No tasks yet.")
        raise _UserAbort
    for n, d in enumerate(items, 1):
        print(f"    {n:>3}) {d['task']}")
    while True:
        raw = _input(f"{label} 1..{len(items)}", allow_empty=False)
        if raw.isdigit() and 1 <= int(raw) <= len(items):
            return int(raw) - 1
        print("    Out of range.")


def _show_draft(items: list[dict[str, Any]]) -> None:
    print("\n    Draft tasks:")
    _print_items([tpl.TemplateItem(
        key=d.get("key") or d["task"], task=d["task"],
        category=d["category"], required=d["required"],
        due_offset_days=d["due_offset_days"], owner_role=d["owner_role"],
        sensitive=d["sensitive"]) for d in items])


def _edit_tasks(items: list[dict[str, Any]], details: dict[str, Any]
                ) -> bool:
    """Edit the draft in place; True = save, False = discard."""
    actions = ["Add task", "Edit task", "Remove task", "Move task",
               "Change details (kind / learner type / description)",
               "Save", "Discard"]
    while True:
        _show_draft(items)
        action = _pick_from("Action", actions, default="Save")
        try:
            if action == "Add task":
                items.append(_ask_task())
            elif action == "Edit task":
                n = _pick_row(items, "Task")
                items[n] = _ask_task(items[n])
            elif action == "Remove task":
                n = _pick_row(items, "Remove task")
                if _yes_no(f"Remove '{items[n]['task']}'?", default=False):
                    items.pop(n)
            elif action == "Move task":
                n = _pick_row(items, "Move task")
                to = _input(f"New position 1..{len(items)}",
                            allow_empty=False)
                if to.isdigit() and 1 <= int(to) <= len(items):
                    items.insert(int(to) - 1, items.pop(n))
                else:
                    print("    Out of range.")
            elif action.startswith("Change details"):
                details.update(_ask_details(details))
            elif action == "Save":
                return True
            else:
                return False
        except _UserAbort:
            print("    (no change)")


def _ask_details(cur: dict[str, Any]) -> dict[str, Any]:
    kind = _pick_from("Kind (base = a checklist opens from it; addon = "
                      "added on top)", list(tpl.KINDS),
                      default=cur.get("kind") or "base")
    ltype = _pick_from("Learner type", [_NONE, *tpl.LEARNER_TYPES],
                       default=cur.get("learner_type") or _NONE)
    desc = _input("Description", default=cur.get("description") or "")
    return {"kind": kind, "learner_type": None if ltype == _NONE else ltype,
            "description": desc or None}


def _save(name: str, items: list[dict[str, Any]],
          details: dict[str, Any]) -> None:
    note = _ask_text("Note for this version (what changed and why)")
    try:
        t = tpl.save_template(name, items=items, note=note, **details)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ Saved {t.name} as version {t.version} "
          f"({len(t.items)} tasks). Checklists already made keep the "
          "version they were made from.")
    _pause()


def edit_flow() -> None:
    print("\n═══ Edit Template ═══")
    if not _writer():
        return
    t = _pick_template(include_inactive=False)
    _print_template(t)
    items = [_item_dict(i) for i in t.items]
    details = {"kind": t.kind, "learner_type": t.learner_type,
               "description": t.description}
    if not _edit_tasks(items, details):
        print("\n  Discarded — nothing saved.")
        return _pause()
    _save(t.name, items, details)


def new_flow() -> None:
    print("\n═══ New Template ═══")
    if not _writer():
        return
    name = _input("Template name (80 characters max)", allow_empty=False)
    if tpl.get_template(name) is not None:
        print(f"    {name!r} already exists — use Edit Template.")
        return _pause()
    details = _ask_details({})
    items: list[dict[str, Any]] = []
    if _yes_no("Start from a copy of another template's tasks?",
               default=False):
        src = _pick_template()
        items = [_item_dict(i) for i in src.items]
    if not _edit_tasks(items, details):
        print("\n  Discarded — nothing saved.")
        return _pause()
    _save(name, items, details)


def _set_active_flow(active: bool) -> None:
    word = "Reactivate" if active else "Retire"
    print(f"\n═══ {word} Template ═══")
    if not _writer():
        return
    t = _pick_template(only=lambda x: x.active != active)
    if not active:
        print("    A retired template is kept (checklists made from it "
              "still point at it) but can't be chosen for new ones.")
    reason = _ask_text(f"Why {word.lower()} {t.name!r}?")
    try:
        out = tpl.set_active(t.name, active, reason=reason)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ {out.name} is now {'active' if out.active else 'retired'}")
    _pause()


def apply_flow() -> None:
    print("\n═══ Apply Template to a Checklist ═══")
    if not _writer():
        return
    try:
        c = _pick_checklist()
        used = tpl.templates_used(c.checklist_id)
        if used:
            print("    Made from: " + ", ".join(
                f"{u['template_name']} v{u['version']}" for u in used))
        t = _pick_template(include_inactive=False)
        print(f"    Tasks it already has (by rule key) are kept; a "
              f"required task in {t.name!r} makes the existing one "
              "required.")
        if not _yes_no(f"Add {t.name!r} to checklist #{c.checklist_id}?",
                       default=True):
            raise _UserAbort
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        added = tpl.apply_template(c.checklist_id, t.name)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ {len(added)} task(s) added"
          + (": " + ", ".join(added) if added else " (it had them all)"))
    _pause()


_MENU = [
    ("List templates", list_flow),
    ("View template (tasks and versions)", view_flow),
    ("View an earlier version", view_version_flow),
    ("New template", new_flow),
    ("Edit template (saves a new version)", edit_flow),
    ("Retire template", lambda: _set_active_flow(False)),
    ("Reactivate template", lambda: _set_active_flow(True)),
    ("Apply template to a checklist", apply_flow),
]


def manage_flow() -> None:
    while True:
        print("\n── Onboarding Templates ──")
        for n, (label, _) in enumerate(_MENU, 1):
            print(f"  {n:>2}) {label}")
        print("   0) Back")
        try:
            raw = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if raw == "0":
            return
        if not raw.isdigit() or not 1 <= int(raw) <= len(_MENU):
            print("  Invalid selection.")
            continue
        try:
            _MENU[int(raw) - 1][1]()
        except _UserAbort:
            print("\n  Cancelled.")
        except _REFUSED as e:
            _refused(e)
