"""GUI tabs for attendance capture and the off-register routines.

Five panels, mounted as extra tabs on the Attendance screen. Each one is
a screen over a domain module that until now was only reachable from
the CLI sub-menus:

* **Kiosk** — :mod:`attendance_kiosk`: terminals, their health, the
  cards and badges learners tap, a desk check-in for the forgotten card,
  and the day's taps.
* **Offline & sync** — :mod:`attendance_offline`: pack the day's
  registers for a device (and save them to a file), load a captured
  batch back in, the queue, sync, and the held batches that need a
  person to decide.
* **Import** — :mod:`attendance_import`: preview a CSV, apply it as an
  undoable batch, roll a batch back, and the file format.
* **Punctuality** — :mod:`attendance_punctuality`: the league in minutes
  lost, when lateness happens, raising triggers and working the
  outstanding sanctions.
* **Activities & study** — :mod:`attendance_activities`: supervised
  private study, tutorials and enrichment — activities, rosters,
  registers, summaries and the registers nobody took.

Like :mod:`attendance_codes_views`, this module does not import
:mod:`attendance_views`; the import graph stays one-way. Nothing here
touches a database until a tab is built.
"""

from __future__ import annotations

import json
import logging
import tkinter as tk
from datetime import date as _date, timedelta as _timedelta
from pathlib import Path
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox, simpledialog
from typing import Any, Callable

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_activities as activities,
    attendance_codes as codes,
    attendance_import as importer,
    attendance_kiosk as kiosk,
    attendance_offline as offline,
    attendance_punctuality as punctuality,
)
from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_groups as cg_data,
)
from education_system.systems.sixth_form.domain.academics.courses import (
    courses as course_data,
)
from education_system.systems.sixth_form.domain.academics.timetable.timetable import (
    day_name,
)
from education_system.systems.sixth_form.interfaces.gui._ui import (
    grab_when_viewable,
)

logger = logging.getLogger(__name__)

_WINDOW_DAYS: int = 28


# ── Shared helpers ──────────────────────────────────────────────────

def _today() -> str:
    return _date.today().isoformat()


def _days_ago(days: int) -> str:
    return (_date.today() - _timedelta(days=days)).isoformat()


def _actor(gui) -> str | None:
    auth = getattr(gui, "auth", None)
    return ((getattr(auth, "current_user", None) or {}).get("username")
            if auth else None)


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _hint(parent, text: str) -> None:
    ttk.Label(parent, text=text, foreground="#666", wraplength=900,
              justify="left").pack(anchor="w", pady=(0, 8))


def _tree(parent, columns: list[tuple[str, str, int]],
          height: int = 12) -> ttk.Treeview:
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    tree = ttk.Treeview(holder, columns=[c[0] for c in columns],
                        show="headings", height=height)
    for key, text, width in columns:
        tree.heading(key, text=text)
        tree.column(key, width=width, anchor="w")
    scroll = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return tree


def _fill(tree: ttk.Treeview, rows: list[tuple]) -> None:
    tree.delete(*tree.get_children())
    for row in rows:
        tree.insert("", "end", values=row)


def _selected_value(tree: ttk.Treeview, parent, column: int = 0) -> str | None:
    selection = tree.selection()
    if not selection:
        messagebox.showinfo("Nothing selected", "Pick a row first.",
                            parent=parent)
        return None
    values = tree.item(selection[0], "values")
    return str(values[column]) if len(values) > column else None


def _selected_id(tree: ttk.Treeview, parent) -> int | None:
    raw = _selected_value(tree, parent)
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


def _bar(parent) -> ttk.Frame:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    return bar


def _labelled_entry(bar, label: str, var: tk.StringVar, width: int = 12) -> None:
    ttk.Label(bar, text=label).pack(side="left")
    ttk.Entry(bar, textvariable=var, width=width).pack(
        side="left", padx=(4, 12))


def _run(gui, action: Callable[[], Any], *, title: str = "Not done") -> Any:
    """Run a domain call, turning a ValidationError into a dialog."""
    try:
        return action()
    except ValidationError as e:
        messagebox.showerror(title, str(e), parent=gui.root)
    except Exception as e:                       # pragma: no cover - UI guard
        logger.exception("Attendance capture action failed")
        messagebox.showerror(title, f"Unexpected error: {e}", parent=gui.root)
    return None


def _form(gui, title: str,
          fields: list[tuple[str, str, Any]]) -> dict[str, Any] | None:
    """A small modal form.

    ``fields`` is ``(key, label, spec)`` where spec is a default string,
    a ``list``/``tuple`` of choices (first is the default), or a bool
    for a checkbox. Returns the values, or ``None`` if cancelled.
    """
    win = tk.Toplevel(gui.root)
    win.title(title)
    win.transient(gui.root)
    grab_when_viewable(win)
    body = ttk.Frame(win, padding=12)
    body.pack(fill="both", expand=True)
    holders: dict[str, tk.Variable] = {}
    for row, (key, label, spec) in enumerate(fields):
        ttk.Label(body, text=label).grid(row=row, column=0, sticky="w",
                                         pady=3, padx=(0, 8))
        if isinstance(spec, bool):
            var: tk.Variable = tk.BooleanVar(value=spec)
            ttk.Checkbutton(body, variable=var).grid(row=row, column=1,
                                                     sticky="w")
        elif isinstance(spec, (list, tuple)):
            var = tk.StringVar(value=(spec[0] if spec else ""))
            ttk.Combobox(body, textvariable=var, values=list(spec),
                         state="readonly", width=30).grid(
                row=row, column=1, sticky="w")
        else:
            var = tk.StringVar(value=str(spec or ""))
            ttk.Entry(body, textvariable=var, width=32).grid(
                row=row, column=1, sticky="w")
        holders[key] = var
    result: dict[str, Any] = {}

    def ok() -> None:
        for key, var in holders.items():
            value = var.get()
            result[key] = value.strip() if isinstance(value, str) else value
        win.destroy()

    buttons = ttk.Frame(body)
    buttons.grid(row=len(fields), column=0, columnspan=2, sticky="e",
                 pady=(10, 0))
    ttk.Button(buttons, text="OK", command=ok).pack(side="right")
    ttk.Button(buttons, text="Cancel", command=win.destroy).pack(
        side="right", padx=(0, 6))
    win.bind("<Return>", lambda _e: ok())
    win.bind("<Escape>", lambda _e: win.destroy())
    win.wait_window()
    return result or None


def _group_choices() -> tuple[list[str], dict[str, int]]:
    groups = cg_data.list_groups()
    courses = {c.course_id: c for c in course_data.list_courses()}
    labels = [
        f"#{g.group_id} {g.group_name} "
        f"({courses[g.course_id].course_code if g.course_id in courses else '?'})"
        for g in groups
    ]
    return labels, {label: g.group_id for label, g in zip(labels, groups)}


def _show_text(gui, title: str, text: str) -> None:
    win = tk.Toplevel(gui.root)
    win.title(title)
    win.transient(gui.root)
    box = tk.Text(win, width=90, height=24, wrap="none")
    box.insert("1.0", text)
    box.configure(state="disabled")
    box.pack(fill="both", expand=True, padx=8, pady=8)
    ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 8))


# ═══ Kiosk ══════════════════════════════════════════════════════════

def build_kiosk_tab(gui, parent: ttk.Frame) -> None:
    inner = ttk.Notebook(parent)
    inner.pack(fill="both", expand=True)
    devices_tab = ttk.Frame(inner, padding=8)
    tokens_tab = ttk.Frame(inner, padding=8)
    checkin_tab = ttk.Frame(inner, padding=8)
    events_tab = ttk.Frame(inner, padding=8)
    inner.add(devices_tab, text="Terminals")
    inner.add(tokens_tab, text="Cards & badges")
    inner.add(checkin_tab, text="Desk check-in")
    inner.add(events_tab, text="Taps")
    _build_kiosk_devices(gui, devices_tab)
    _build_kiosk_tokens(gui, tokens_tab)
    _build_kiosk_checkin(gui, checkin_tab)
    _build_kiosk_events(gui, events_tab)


def _build_kiosk_devices(gui, parent: ttk.Frame) -> None:
    _hint(parent, "Every terminal that can mark a register. A quiet "
                  "terminal usually means an empty register, so the health "
                  "columns are the ones to watch.")
    bar = _bar(parent)
    tree = _tree(parent, [
        ("id", "#", 50), ("name", "Name", 180), ("mode", "Mode", 90),
        ("room", "Room", 80), ("location", "Location", 160),
        ("active", "Active", 60), ("taps", "Taps today", 80),
        ("seen", "Last seen", 150), ("health", "Status", 80),
    ])

    def refresh() -> None:
        health = {h.device.device_id: h for h in kiosk.device_health()}
        rows = []
        for d in kiosk.list_devices():
            h = health.get(d.device_id)
            seen = d.last_seen_at or "never"
            if h is not None and h.hours_since_seen is not None:
                seen = f"{h.hours_since_seen:.1f}h ago"
            rows.append((d.device_id, d.name, d.mode, d.room or "—",
                         d.location or "", "yes" if d.active else "no",
                         h.taps_today if h else 0, seen,
                         ("stale" if h and h.stale else "ok")))
        _fill(tree, rows)

    def register() -> None:
        modes = list(kiosk.DEVICE_MODES)
        values = _form(gui, "Register a terminal", [
            ("name", "Device name", ""),
            ("mode", "Mode", modes),
            ("room", "Room (room mode)", ""),
            ("location", "Location (optional)", ""),
            ("enforce", "Refuse taps for the wrong room", True),
        ])
        if not values or not values["name"]:
            return
        device = _run(gui, lambda: kiosk.register_device(
            values["name"], mode=values["mode"],
            room=values["room"] or None,
            location=values["location"] or None,
            enforce_room=bool(values["enforce"]), actor=_actor(gui)))
        if device is None:
            return
        refresh()
        _show_text(gui, "Terminal key",
                   f"Registered #{device.device_id} — {device.name}\n\n"
                   f"API key: {device.api_key}\n\n"
                   "Copy it now; it is not shown again.")

    def rotate() -> None:
        device_id = _selected_id(tree, gui.root)
        if device_id is None:
            return
        if not messagebox.askyesno(
                "Rotate key", "Issue a new key? The old one stops working "
                "immediately.", parent=gui.root):
            return
        device = _run(gui, lambda: kiosk.rotate_key(device_id,
                                                    actor=_actor(gui)))
        if device is not None:
            _show_text(gui, "New terminal key",
                       f"{device.name}\n\nAPI key: {device.api_key}\n\n"
                       "Copy it now; it is not shown again.")

    def toggle() -> None:
        device_id = _selected_id(tree, gui.root)
        if device_id is None:
            return
        device = kiosk.get_device(device_id)
        if device is None:
            return
        if _run(gui, lambda: kiosk.set_device_active(
                device_id, not device.active)) is not None:
            refresh()

    def delete() -> None:
        device_id = _selected_id(tree, gui.root)
        if device_id is None:
            return
        if not messagebox.askyesno(
                "Remove terminal", f"Remove terminal #{device_id}? Its past "
                "taps stay in the log.", parent=gui.root, default="no"):
            return
        if _run(gui, lambda: kiosk.delete_device(device_id)):
            refresh()

    ttk.Button(bar, text="Refresh", command=refresh).pack(side="left")
    ttk.Button(bar, text="Register terminal…", command=register).pack(
        side="left", padx=(6, 0))
    ttk.Button(bar, text="Rotate key", command=rotate).pack(
        side="left", padx=(6, 0))
    ttk.Button(bar, text="Activate / deactivate", command=toggle).pack(
        side="left", padx=(6, 0))
    ttk.Button(bar, text="Remove", command=delete).pack(
        side="left", padx=(6, 0))
    refresh()


def _build_kiosk_tokens(gui, parent: ttk.Frame) -> None:
    _hint(parent, "Cards and QR badges. Issuing a new one revokes any live "
                  "token the learner already holds — a lost card that still "
                  "marks its owner present is worse than no card.")
    bar = _bar(parent)
    sid_var = tk.StringVar()
    live_var = tk.BooleanVar(value=False)
    _labelled_entry(bar, "Student ID (blank = all):", sid_var, 14)
    ttk.Checkbutton(bar, text="Live only", variable=live_var).pack(
        side="left", padx=(0, 12))
    tree = _tree(parent, [
        ("token", "Token", 200), ("student", "Student", 100),
        ("kind", "Kind", 60), ("label", "Label", 140),
        ("expires", "Expires", 100), ("status", "Status", 80),
        ("issued", "Issued", 150), ("by", "Issued by", 100),
    ])

    def refresh() -> None:
        rows = []
        for t in kiosk.list_tokens(student_id=sid_var.get().strip() or None,
                                   active_only=live_var.get()):
            status = "revoked" if t.revoked else (
                "valid" if t.is_valid() else "expired")
            rows.append((t.token, t.student_id, t.kind, t.label or "",
                         t.expires_on or "—", status, t.issued_at or "",
                         t.issued_by or ""))
        _fill(tree, rows)

    def issue() -> None:
        values = _form(gui, "Issue a card or badge", [
            ("student_id", "Student ID", sid_var.get().strip()),
            ("kind", "Kind", list(kiosk.TOKEN_KINDS)),
            ("label", "Label (optional)", ""),
            ("expires", "Expires on YYYY-MM-DD (optional)", ""),
            ("token", "Existing card number (blank = generate)", ""),
        ])
        if not values or not values["student_id"]:
            return
        token = _run(gui, lambda: kiosk.issue_token(
            values["student_id"], kind=values["kind"],
            label=values["label"] or None,
            expires_on=values["expires"] or None,
            token=values["token"] or None, actor=_actor(gui)))
        if token is not None:
            messagebox.showinfo("Issued", f"Issued {token.token}",
                                parent=gui.root)
            refresh()

    def revoke() -> None:
        value = _selected_value(tree, gui.root)
        if value is None:
            return
        reason = simpledialog.askstring("Revoke", "Reason (optional):",
                                        parent=gui.root)
        if reason is None:
            return
        if kiosk.revoke_token(value, actor=_actor(gui),
                              reason=reason.strip() or None):
            refresh()
        else:
            messagebox.showinfo("Revoke", "That token is not live.",
                                parent=gui.root)

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    ttk.Button(bar, text="Issue…", command=issue).pack(
        side="left", padx=(6, 0))
    ttk.Button(bar, text="Revoke selected", command=revoke).pack(
        side="left", padx=(6, 0))
    refresh()


def _build_kiosk_checkin(gui, parent: ttk.Frame) -> None:
    _hint(parent, "What a terminal does when a card is tapped — useful from "
                  "a desk when somebody has forgotten theirs. Leave the time "
                  "blank for now.")
    form = ttk.Frame(parent)
    form.pack(anchor="w", pady=(0, 8))
    by_var = tk.StringVar(value="Student ID")
    value_var = tk.StringVar()
    device_var = tk.StringVar()
    date_var = tk.StringVar(value=_today())
    time_var = tk.StringVar()

    device_names = [""] + [d.name for d in kiosk.list_devices(active_only=True)]
    rows = [
        ("Identify by:", ttk.Combobox(form, textvariable=by_var,
                                      values=["Student ID", "Card / token"],
                                      state="readonly", width=16)),
        ("Value:", ttk.Entry(form, textvariable=value_var, width=24)),
        ("Device (optional):", ttk.Combobox(form, textvariable=device_var,
                                            values=device_names, width=22)),
        ("Date:", ttk.Entry(form, textvariable=date_var, width=12)),
        ("Time HH:MM:", ttk.Entry(form, textvariable=time_var, width=8)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", pady=2)
        widget.grid(row=i, column=1, sticky="w", padx=(6, 0), pady=2)

    result_var = tk.StringVar()
    ttk.Label(parent, textvariable=result_var, font=("", 12, "bold"),
              wraplength=800, justify="left").pack(anchor="w", pady=(8, 0))

    def go() -> None:
        value = value_var.get().strip()
        if not value:
            messagebox.showinfo("Check in", "Enter a student ID or card.",
                                parent=gui.root)
            return
        kwargs = {"device": device_var.get().strip() or None,
                  "date": date_var.get().strip() or None,
                  "at_time": time_var.get().strip() or None,
                  "source": "desk"}
        if by_var.get() == "Card / token":
            result = _run(gui, lambda: kiosk.check_in(value, **kwargs))
        else:
            result = _run(gui, lambda: kiosk.check_in_student(value, **kwargs))
        if result is None:
            return
        extra = ""
        if result.slot_id:
            extra = f"   (slot #{result.slot_id}" + (
                f", {result.minutes_late} min late" if result.minutes_late
                else "") + ")"
        result_var.set(f"[{result.outcome}] {result.message}{extra}")
        value_var.set("")

    ttk.Button(form, text="Check in", command=go).grid(
        row=len(rows), column=1, sticky="w", padx=(6, 0), pady=(6, 0))


def _build_kiosk_events(gui, parent: ttk.Frame) -> None:
    bar = _bar(parent)
    date_var = tk.StringVar(value=_today())
    outcome_var = tk.StringVar(value="")
    _labelled_entry(bar, "Date:", date_var)
    ttk.Label(bar, text="Outcome:").pack(side="left")
    ttk.Combobox(bar, textvariable=outcome_var,
                 values=[""] + list(kiosk.OUTCOMES), state="readonly",
                 width=20).pack(side="left", padx=(4, 12))
    breakdown_var = tk.StringVar()
    ttk.Label(parent, textvariable=breakdown_var, foreground="#555").pack(
        anchor="w", pady=(0, 6))
    tree = _tree(parent, [
        ("time", "Time", 60), ("student", "Student", 100),
        ("device", "Device", 140), ("slot", "Slot", 50),
        ("outcome", "Outcome", 150), ("status", "Status", 80),
        ("late", "Min late", 70), ("detail", "Detail", 260),
    ])

    def refresh() -> None:
        date_s = date_var.get().strip() or None
        breakdown = _run(gui, lambda: kiosk.outcome_breakdown(date=date_s))
        breakdown_var.set("   ".join(f"{k}: {v}"
                                     for k, v in (breakdown or {}).items())
                          or "No taps.")
        events = _run(gui, lambda: kiosk.list_events(
            date=date_s, outcome=outcome_var.get() or None, limit=500)) or []
        _fill(tree, [(e.time, e.student_id or "—", e.device_name or "—",
                      e.slot_id or "—", e.outcome, e.status or "",
                      e.minutes_late or "", e.detail or "") for e in events])

    def unrecognised() -> None:
        rows = _run(gui, lambda: kiosk.unrecognised_cards(
            date_from=_days_ago(_WINDOW_DAYS), date_to=_today())) or []
        _fill(tree, [(e.time, e.token or "—", e.device_name or "—",
                      e.slot_id or "—", e.outcome, e.date, "",
                      e.detail or "") for e in rows])
        breakdown_var.set(f"{len(rows)} unrecognised tap(s) in the last "
                          f"{_WINDOW_DAYS} days (Student column shows the "
                          "card, Status the date).")

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    ttk.Button(bar, text="Unrecognised cards", command=unrecognised).pack(
        side="left", padx=(6, 0))
    refresh()


# ═══ Offline ════════════════════════════════════════════════════════

def build_offline_tab(gui, parent: ttk.Frame) -> None:
    inner = ttk.Notebook(parent)
    inner.pack(fill="both", expand=True)
    pack_tab = ttk.Frame(inner, padding=8)
    queue_tab = ttk.Frame(inner, padding=8)
    held_tab = ttk.Frame(inner, padding=8)
    inner.add(pack_tab, text="Pack for a device")
    inner.add(queue_tab, text="Queue & sync")
    inner.add(held_tab, text="Held batches")
    _build_offline_pack(gui, pack_tab)
    _build_offline_queue(gui, queue_tab)
    _build_offline_held(gui, held_tab)


def _build_offline_pack(gui, parent: ttk.Frame) -> None:
    _hint(parent, "What a device takes away: the roster, the marks so far, "
                  "and a digest so conflicts can be spotted on the way back. "
                  "Save the bundles to a file for the device to load.")
    bar = _bar(parent)
    date_var = tk.StringVar(value=_today())
    group_var = tk.StringVar(value="")
    group_labels, group_ids = _group_choices()
    _labelled_entry(bar, "Date:", date_var)
    ttk.Label(bar, text="Group (optional):").pack(side="left")
    ttk.Combobox(bar, textvariable=group_var, values=[""] + group_labels,
                 state="readonly", width=30).pack(side="left", padx=(4, 12))
    tree = _tree(parent, [
        ("slot", "Slot", 60), ("period", "Period", 60), ("room", "Room", 80),
        ("roster", "Roster", 60), ("locked", "Locked", 60),
        ("digest", "Digest", 300),
    ])
    current: dict[str, list] = {"bundles": []}

    def refresh() -> None:
        bundles = _run(gui, lambda: offline.pack_day(
            date=date_var.get().strip() or None,
            group_id=group_ids.get(group_var.get()))) or []
        current["bundles"] = bundles
        _fill(tree, [(b.slot_id, b.period or "—", b.room or "—",
                      len(b.students), "yes" if b.locked else "no", b.digest)
                     for b in bundles])

    def save() -> None:
        if not current["bundles"]:
            messagebox.showinfo("Save", "Nothing packed for that date.",
                                parent=gui.root)
            return
        path = filedialog.asksaveasfilename(
            parent=gui.root, title="Save bundles", defaultextension=".json",
            initialfile=f"attendance_bundles_{date_var.get().strip()}.json",
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        payload = [json.loads(b.to_json()) for b in current["bundles"]]
        Path(path).write_text(json.dumps(payload, indent=1), encoding="utf-8")
        messagebox.showinfo("Saved", f"{len(payload)} bundle(s) saved.",
                            parent=gui.root)

    ttk.Button(bar, text="Pack", command=refresh).pack(side="left")
    ttk.Button(bar, text="Save to file…", command=save).pack(
        side="left", padx=(6, 0))
    refresh()


def _build_offline_queue(gui, parent: ttk.Frame) -> None:
    _hint(parent, "server-wins keeps the office's mark where they disagree; "
                  "device-wins keeps the teacher's; hold applies nothing "
                  "contested and parks it for a person. Loading a captured "
                  "file only queues it — nothing is written until a sync.")
    bar = _bar(parent)
    policy_var = tk.StringVar(value=offline.DEFAULT_POLICY)
    state_var = tk.StringVar(value="Open")
    ttk.Label(bar, text="Show:").pack(side="left")
    ttk.Combobox(bar, textvariable=state_var,
                 values=["Open", "All"] + list(offline.STATES),
                 state="readonly", width=12).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Sync policy:").pack(side="left")
    ttk.Combobox(bar, textvariable=policy_var, values=list(offline.POLICIES),
                 state="readonly", width=12).pack(side="left", padx=(4, 12))
    backlog_var = tk.StringVar()
    ttk.Label(parent, textvariable=backlog_var, foreground="#555",
              wraplength=900, justify="left").pack(anchor="w", pady=(0, 6))
    tree = _tree(parent, [
        ("id", "#", 50), ("slot", "Slot", 60), ("date", "Date", 100),
        ("marks", "Marks", 60), ("device", "Device", 140),
        ("state", "State", 90), ("written", "Written", 70),
        ("captured", "Captured", 150), ("detail", "Detail", 220),
    ])

    def refresh() -> None:
        choice = state_var.get()
        batches = offline.list_batches(
            open_only=(choice == "Open"),
            state=(choice if choice in offline.STATES else None))
        _fill(tree, [(b.queue_id, b.slot_id, b.date, b.size,
                      b.device_name or "—", b.state, b.written,
                      b.captured_at, b.detail or "") for b in batches])
        backlog = offline.device_backlog()
        stale = offline.stale_batches()
        text = "   ".join(f"{r.device_name or '—'}: {r.pending} pending, "
                          f"{r.conflicts} held" for r in backlog) or \
            "Nothing waiting to sync."
        if stale:
            text += f"   ⚠ {len(stale)} batch(es) captured over " \
                    f"{offline.STALE_BATCH_DAYS} days ago."
        backlog_var.set(text)

    def sync() -> None:
        report = _run(gui, lambda: offline.sync(policy=policy_var.get(),
                                                actor=_actor(gui)))
        if report is None:
            return
        lines = [report.summary]
        for result in report.results:
            if result.state != offline.APPLIED or result.conflicts:
                lines.append(f"#{result.queue_id}: {result.state}"
                             + (f" — {result.detail}" if result.detail else ""))
                lines.extend(f"    {c.label}" for c in result.conflicts)
        messagebox.showinfo("Sync", "\n".join(lines[:30]), parent=gui.root)
        refresh()

    def load_file() -> None:
        path = filedialog.askopenfilename(
            parent=gui.root, title="Load captured batch",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            messagebox.showerror("Load", f"Could not read the file: {e}",
                                 parent=gui.root)
            return
        items = data if isinstance(data, list) else [data]
        queued, errors = 0, []
        for i, item in enumerate(items, 1):
            try:
                offline.queue_batch(
                    int(item["slot_id"]), str(item["date"]),
                    item.get("payload") or item.get("marks") or {},
                    client_uuid=str(item.get("client_uuid") or ""),
                    device_name=item.get("device_name"),
                    actor=item.get("actor") or _actor(gui),
                    base_digest=item.get("base_digest") or item.get("digest"),
                    captured_at=item.get("captured_at"))
                queued += 1
            except (KeyError, TypeError, ValueError, ValidationError) as e:
                errors.append(f"Item {i}: {e}")
        message = f"{queued} batch(es) queued."
        if errors:
            message += "\n\n" + "\n".join(errors[:15])
        messagebox.showinfo("Load", message, parent=gui.root)
        refresh()

    def purge() -> None:
        before = simpledialog.askstring(
            "Purge", "Drop applied/discarded batches captured before "
                     "(YYYY-MM-DD):", initialvalue=_days_ago(90),
            parent=gui.root)
        if not before:
            return
        n = _run(gui, lambda: offline.purge_resolved(before_date=before,
                                                     dry_run=True))
        if n is None:
            return
        if n and messagebox.askyesno("Purge", f"Remove {n} resolved batch(es)?",
                                     parent=gui.root):
            _run(gui, lambda: offline.purge_resolved(before_date=before))
        elif not n:
            messagebox.showinfo("Purge", "Nothing to purge.", parent=gui.root)
        refresh()

    ttk.Button(bar, text="Refresh", command=refresh).pack(side="left")
    ttk.Button(bar, text="Sync now", command=sync).pack(
        side="left", padx=(6, 0))
    ttk.Button(bar, text="Load captured file…", command=load_file).pack(
        side="left", padx=(6, 0))
    ttk.Button(bar, text="Purge resolved…", command=purge).pack(
        side="left", padx=(6, 0))
    refresh()


def _build_offline_held(gui, parent: ttk.Frame) -> None:
    _hint(parent, "Batches where the device and the office disagree. Pick a "
                  "batch to see each contested learner, then keep one side "
                  "or discard the batch.")
    bar = _bar(parent)
    tree = _tree(parent, [
        ("id", "#", 50), ("label", "Batch", 280), ("device", "Device", 140),
        ("conflicts", "Contested", 80), ("captured", "Captured", 150),
    ], height=8)
    ttk.Label(parent, text="Contested learners:").pack(anchor="w",
                                                       pady=(8, 2))
    detail = _tree(parent, [
        ("student", "Student", 100), ("server", "Office mark", 140),
        ("device", "Device mark", 140), ("when", "Office recorded", 160),
    ], height=8)
    held: dict[int, Any] = {}

    def refresh() -> None:
        held.clear()
        rows = []
        for b in offline.conflicts():
            held[b.queue_id] = b
            rows.append((b.queue_id, b.label, b.device_name or "?",
                         len(b.conflicts), b.captured_at))
        _fill(tree, rows)
        _fill(detail, [])

    def show(_event=None) -> None:
        sel = tree.selection()
        if not sel:
            return
        batch = held.get(int(tree.item(sel[0], "values")[0]))
        if batch is None:
            return
        _fill(detail, [(c.student_id,
                        f"{c.server_status or '—'} ({c.server_code or '—'})",
                        f"{c.device_status or '—'} ({c.device_code or '—'})",
                        c.server_recorded_at or "") for c in batch.conflicts])

    def resolve(policy: str) -> None:
        queue_id = _selected_id(tree, gui.root)
        if queue_id is None:
            return
        result = _run(gui, lambda: offline.resolve(queue_id, policy=policy,
                                                   actor=_actor(gui)))
        if result is not None:
            messagebox.showinfo("Resolved", f"{result.state}: {result.written} "
                                f"written, {result.skipped} skipped",
                                parent=gui.root)
            refresh()

    def discard() -> None:
        queue_id = _selected_id(tree, gui.root)
        if queue_id is None:
            return
        reason = simpledialog.askstring("Discard", "Reason:", parent=gui.root)
        if not reason:
            return
        if _run(gui, lambda: offline.discard(queue_id, reason=reason,
                                             actor=_actor(gui))) is not None:
            refresh()

    tree.bind("<<TreeviewSelect>>", show)
    ttk.Button(bar, text="Refresh", command=refresh).pack(side="left")
    ttk.Button(bar, text="Keep office marks",
               command=lambda: resolve(offline.SERVER_WINS)).pack(
        side="left", padx=(6, 0))
    ttk.Button(bar, text="Keep device marks",
               command=lambda: resolve(offline.DEVICE_WINS)).pack(
        side="left", padx=(6, 0))
    ttk.Button(bar, text="Discard batch…", command=discard).pack(
        side="left", padx=(6, 0))
    refresh()


# ═══ Import ═════════════════════════════════════════════════════════

def build_import_tab(gui, parent: ttk.Frame) -> None:
    inner = ttk.Notebook(parent)
    inner.pack(fill="both", expand=True)
    preview_tab = ttk.Frame(inner, padding=8)
    batches_tab = ttk.Frame(inner, padding=8)
    format_tab = ttk.Frame(inner, padding=8)
    inner.add(preview_tab, text="Preview & apply")
    inner.add(batches_tab, text="Batches")
    inner.add(format_tab, text="File format")
    refresh_batches = _build_import_batches(gui, batches_tab)
    _build_import_preview(gui, preview_tab, refresh_batches)
    _build_import_format(gui, format_tab)


def _build_import_preview(gui, parent: ttk.Frame,
                          on_applied: Callable[[], None]) -> None:
    _hint(parent, "Nothing is written by a preview. Applying records enough "
                  "to undo the whole batch from the Batches tab.")
    bar = _bar(parent)
    path_var = tk.StringVar()
    skip_var = tk.BooleanVar(value=False)
    ttk.Label(bar, text="File:").pack(side="left")
    ttk.Entry(bar, textvariable=path_var, width=50).pack(
        side="left", padx=(4, 6))
    summary_var = tk.StringVar()
    ttk.Label(parent, textvariable=summary_var, foreground="#555",
              wraplength=900, justify="left").pack(anchor="w", pady=(0, 6))
    actions = _bar(parent)
    ttk.Checkbutton(actions, text="Keep existing marks where they clash",
                    variable=skip_var).pack(side="left", padx=(0, 12))
    tree = _tree(parent, [
        ("line", "Line", 50), ("student", "Student", 100),
        ("date", "Date", 100), ("slot", "Slot", 60), ("code", "Code", 50),
        ("status", "Status", 90), ("outcome", "Outcome", 80),
        ("existing", "Overwrites", 80), ("detail", "Detail", 260),
    ])
    state: dict[str, Any] = {"plan": None}

    def browse() -> None:
        path = filedialog.askopenfilename(
            parent=gui.root, title="Attendance CSV",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if path:
            path_var.set(path)
            preview()

    def preview() -> None:
        path = path_var.get().strip()
        if not path:
            return
        plan = _run(gui, lambda: importer.plan(importer.parse_file(path)))
        state["plan"] = plan
        if plan is None:
            summary_var.set("")
            _fill(tree, [])
            return
        parts = [plan.summary]
        if plan.date_from:
            parts.append(f"Dates {plan.date_from} → {plan.date_to}.")
        if plan.unknown_students:
            parts.append(f"Unknown learners ({len(plan.unknown_students)}): "
                         + ", ".join(sorted(plan.unknown_students)[:8]))
        if plan.unknown_slots:
            parts.append(f"Unknown slots: {sorted(plan.unknown_slots)[:8]}")
        if plan.locked_registers:
            parts.append(f"Submitted registers skipped: "
                         f"{len(plan.locked_registers)}")
        if plan.duplicates:
            parts.append(f"Duplicate lines: {plan.duplicates}")
        summary_var.set("  ".join(parts))
        rows = sorted(list(plan.rows) + list(plan.errors),
                      key=lambda r: r.line_no)
        _fill(tree, [(r.line_no, r.student_id or "", r.date or "",
                      r.slot_id or "", r.code or "", r.status or "",
                      r.outcome, "yes" if r.existing else "",
                      r.detail or "") for r in rows])

    def apply() -> None:
        plan = state["plan"]
        if plan is None or not plan.writable:
            messagebox.showinfo("Apply", "Preview a file with writable rows "
                                "first.", parent=gui.root)
            return
        path = path_var.get().strip()
        label = simpledialog.askstring("Apply", "Label for this import:",
                                       initialvalue=Path(path).name,
                                       parent=gui.root)
        if not label:
            return
        if not messagebox.askyesno(
                "Apply", f"Write {len(plan.writable)} row(s)?",
                parent=gui.root):
            return
        batch = _run(gui, lambda: importer.apply_plan(
            plan, label=label, source=path, actor=_actor(gui),
            skip_overwrites=skip_var.get()))
        if batch is None:
            return
        messagebox.showinfo(
            "Applied", f"Batch #{batch.batch_id}: {batch.rows_written} "
            f"written, {batch.rows_skipped} skipped, {batch.rows_errored} "
            "errored.\n\nUndo it from the Batches tab if it looks wrong.",
            parent=gui.root)
        state["plan"] = None
        _fill(tree, [])
        summary_var.set("")
        on_applied()

    ttk.Button(bar, text="Browse…", command=browse).pack(side="left")
    ttk.Button(bar, text="Preview", command=preview).pack(
        side="left", padx=(6, 0))
    ttk.Button(actions, text="Apply…", command=apply).pack(side="left")


def _build_import_batches(gui, parent: ttk.Frame) -> Callable[[], None]:
    bar = _bar(parent)
    tree = _tree(parent, [
        ("id", "#", 50), ("label", "Label", 200), ("state", "State", 90),
        ("read", "Read", 60), ("written", "Written", 70),
        ("skipped", "Skipped", 70), ("errored", "Errored", 70),
        ("dates", "Dates", 180), ("by", "By", 100), ("at", "When", 150),
    ], height=10)
    ttk.Label(parent, text="Lines in the selected batch:").pack(
        anchor="w", pady=(8, 2))
    lines = _tree(parent, [
        ("line", "Line", 50), ("student", "Student", 100),
        ("date", "Date", 100), ("slot", "Slot", 60), ("code", "Code", 50),
        ("outcome", "Outcome", 80), ("detail", "Detail", 300),
    ], height=8)

    def refresh() -> None:
        _fill(tree, [(b.batch_id, b.label, b.state, b.rows_read,
                      b.rows_written, b.rows_skipped, b.rows_errored,
                      f"{b.date_from or '—'} → {b.date_to or '—'}",
                      b.imported_by or "", b.created_at or "")
                     for b in importer.list_batches(limit=200)])
        _fill(lines, [])

    def show(_event=None) -> None:
        sel = tree.selection()
        if not sel:
            return
        batch_id = int(tree.item(sel[0], "values")[0])
        _fill(lines, [(r.line_no, r.student_id or "", r.date or "",
                       r.slot_id or "", r.code or "", r.outcome,
                       r.detail or "") for r in importer.batch_rows(batch_id)])

    def rollback() -> None:
        batch_id = _selected_id(tree, gui.root)
        if batch_id is None:
            return
        if not messagebox.askyesno(
                "Roll back", f"Undo every mark batch #{batch_id} wrote?",
                parent=gui.root, default="no"):
            return
        result = _run(gui, lambda: importer.rollback(batch_id,
                                                     actor=_actor(gui)))
        if result is not None:
            messagebox.showinfo("Rolled back", f"{result.restored} row(s) "
                                f"restored, {result.deleted} removed.",
                                parent=gui.root)
            refresh()

    tree.bind("<<TreeviewSelect>>", show)
    ttk.Button(bar, text="Refresh", command=refresh).pack(side="left")
    ttk.Button(bar, text="Roll back selected…", command=rollback).pack(
        side="left", padx=(6, 0))
    refresh()
    return refresh


def _build_import_format(gui, parent: ttk.Frame) -> None:
    _hint(parent, "Columns are matched by name and most aliases are "
                  "accepted. A file needs a learner column, a date column "
                  "and a mark (code or status). Name the slot outright, or "
                  "give a group and a period and it is resolved against the "
                  f"timetable. Up to {importer.MAX_ROWS} rows per file.")
    tree = _tree(parent, [("ours", "Column", 140),
                          ("aliases", "Also accepted", 600)], height=10)
    _fill(tree, [(ours, ", ".join(aliases))
                 for ours, aliases in importer.COLUMN_ALIASES.items()])
    ttk.Label(parent, text="Example:").pack(anchor="w", pady=(8, 2))
    sample = tk.Text(parent, height=5, wrap="none")
    sample.insert("1.0", importer.template_csv())
    sample.configure(state="disabled")
    sample.pack(fill="x")

    def save() -> None:
        path = filedialog.asksaveasfilename(
            parent=gui.root, title="Save template", defaultextension=".csv",
            initialfile="attendance_import_template.csv",
            filetypes=[("CSV", "*.csv")])
        if path:
            Path(path).write_text(importer.template_csv(), encoding="utf-8")

    ttk.Button(parent, text="Save template…", command=save).pack(
        anchor="w", pady=(6, 0))


# ═══ Punctuality ════════════════════════════════════════════════════

def build_punctuality_tab(gui, parent: ttk.Frame) -> None:
    inner = ttk.Notebook(parent)
    inner.pack(fill="both", expand=True)
    league_tab = ttk.Frame(inner, padding=8)
    patterns_tab = ttk.Frame(inner, padding=8)
    triggers_tab = ttk.Frame(inner, padding=8)
    inner.add(league_tab, text="League")
    inner.add(patterns_tab, text="When lateness happens")
    inner.add(triggers_tab, text="Triggers & sanctions")
    _build_punctuality_league(gui, league_tab)
    _build_punctuality_patterns(gui, patterns_tab)
    _build_punctuality_triggers(gui, triggers_tab)


def _build_punctuality_league(gui, parent: ttk.Frame) -> None:
    _hint(parent, "Counted in minutes of teaching missed, which is the "
                  "figure that makes the case. 'After close' arrivals are "
                  "present in the room but absent in the data.")
    bar = _bar(parent)
    window_var = tk.StringVar(value=str(punctuality.DEFAULT_WINDOW_DAYS))
    to_var = tk.StringVar(value=_today())
    group_var = tk.StringVar(value="")
    group_labels, group_ids = _group_choices()
    _labelled_entry(bar, "Window (days):", window_var, 6)
    _labelled_entry(bar, "Up to:", to_var)
    ttk.Label(bar, text="Group:").pack(side="left")
    ttk.Combobox(bar, textvariable=group_var, values=[""] + group_labels,
                 state="readonly", width=28).pack(side="left", padx=(4, 12))
    summary_var = tk.StringVar()
    ttk.Label(parent, textvariable=summary_var, foreground="#555",
              wraplength=900, justify="left").pack(anchor="w", pady=(0, 6))
    tree = _tree(parent, [
        ("student", "Student", 100), ("name", "Name", 180),
        ("lessons", "Lessons", 70), ("late", "Late", 60),
        ("rate", "Late rate", 80), ("after", "After close", 80),
        ("hours", "Hours lost", 80), ("avg", "Avg min", 70),
        ("worst", "Worst", 60),
    ])

    def refresh() -> None:
        try:
            window = int(window_var.get())
        except ValueError:
            messagebox.showerror("League", "Window must be a number.",
                                 parent=gui.root)
            return
        date_to = to_var.get().strip() or None
        rows = _run(gui, lambda: punctuality.league(
            window_days=window, date_to=date_to,
            group_id=group_ids.get(group_var.get()))) or []
        _fill(tree, [(e.student_id, e.student_name or "", e.lessons, e.late,
                      _pct(e.late_rate), e.after_close, e.hours_lost,
                      f"{(e.average_minutes or 0):.0f}", e.worst_minutes)
                     for e in rows])
        summary = _run(gui, lambda: punctuality.college_summary(
            window_days=window, date_to=date_to))
        if summary:
            summary_var.set(
                f"College: {summary['late_marks']} late mark(s) from "
                f"{summary['learners_late']} learner(s), "
                f"{summary['hours_lost']}h lost "
                f"(~{summary['teaching_days_lost']} teaching days); "
                f"{summary['after_register_closed']} arrival(s) after the "
                "register closed.")

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    refresh()


def _build_punctuality_patterns(gui, parent: ttk.Frame) -> None:
    _hint(parent, "Period 1 lateness is transport; period 5 is lunch; "
                  "Monday is the weekend. They need different answers.")
    bar = _bar(parent)
    sid_var = tk.StringVar()
    window_var = tk.StringVar(value=str(punctuality.DEFAULT_WINDOW_DAYS))
    _labelled_entry(bar, "Student ID (blank = college):", sid_var, 14)
    _labelled_entry(bar, "Window (days):", window_var, 6)
    note_var = tk.StringVar()
    ttk.Label(parent, textvariable=note_var, foreground="#555").pack(
        anchor="w", pady=(0, 6))
    tables = ttk.Frame(parent)
    tables.pack(fill="both", expand=True)
    left = ttk.Frame(tables)
    right = ttk.Frame(tables)
    left.pack(side="left", fill="both", expand=True, padx=(0, 6))
    right.pack(side="left", fill="both", expand=True)
    by_day = _tree(left, [("day", "Day", 120), ("n", "Late marks", 100)])
    by_period = _tree(right, [("period", "Period", 120),
                              ("n", "Late marks", 100)])

    def refresh() -> None:
        try:
            window = int(window_var.get())
        except ValueError:
            messagebox.showerror("Patterns", "Window must be a number.",
                                 parent=gui.root)
            return
        insight = _run(gui, lambda: punctuality.patterns(
            window_days=window, student_id=sid_var.get().strip() or None))
        if insight is None:
            return
        _fill(by_day, [(day_name(d), n)
                       for d, n in sorted(insight.by_weekday.items())])
        _fill(by_period, [(f"P{p}", n)
                          for p, n in sorted(insight.by_period.items())])
        share = insight.first_period_share
        if not (insight.by_weekday or insight.by_period):
            note_var.set("No lateness recorded in the window.")
        else:
            note_var.set(
                (f"Period 1 is {share:.0f}% of all lateness. "
                 if share is not None else "")
                + (f"Worst day: {day_name(insight.worst_weekday)}. "
                   if insight.worst_weekday else "")
                + (f"Worst period: P{insight.worst_period}."
                   if insight.worst_period else ""))

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    refresh()


def _build_punctuality_triggers(gui, parent: ttk.Frame) -> None:
    ladder = ", ".join(f"{n}+ late → {action}"
                       for n, action in punctuality.ACTION_LADDER)
    _hint(parent, f"The ladder: {ladder}. A sweep raises a trigger for "
                  "everybody who has crossed a rung; preview first.")
    bar = _bar(parent)
    state_var = tk.StringVar(value="Outstanding")
    ttk.Label(bar, text="Show:").pack(side="left")
    ttk.Combobox(bar, textvariable=state_var,
                 values=["Outstanding", "All"]
                 + list(punctuality.TRIGGER_STATES),
                 state="readonly", width=14).pack(side="left", padx=(4, 12))
    tree = _tree(parent, [
        ("id", "#", 50), ("student", "Student", 100),
        ("raised", "Raised", 100), ("late", "Late", 50),
        ("mins", "Min lost", 70), ("action", "Action", 170),
        ("state", "State", 80), ("due", "Due", 100),
        ("served", "Served", 100), ("by", "By", 100), ("note", "Note", 200),
    ])

    def refresh() -> None:
        choice = state_var.get()
        if choice == "Outstanding":
            rows = punctuality.outstanding()
        else:
            rows = punctuality.list_triggers(
                state=(choice if choice in punctuality.TRIGGER_STATES
                       else None))
        _fill(tree, [(t.trigger_id, t.student_id, t.raised_on, t.late_count,
                      t.minutes_lost, t.action, t.state, t.due_on or "",
                      t.served_on or "", t.actioned_by or "", t.note or "")
                     for t in rows])

    def sweep() -> None:
        preview = _run(gui, lambda: punctuality.sweep(dry_run=True))
        if preview is None:
            return
        if not preview.raised:
            messagebox.showinfo(
                "Sweep", f"{preview.checked} learner(s) checked; nothing to "
                f"raise ({preview.skipped_existing} already open).",
                parent=gui.root)
            return
        if not messagebox.askyesno(
                "Sweep", f"{preview.checked} learner(s) checked; "
                f"{preview.raised} trigger(s) would be raised "
                f"({preview.skipped_existing} already open).\n\nRaise them?",
                parent=gui.root):
            return
        result = _run(gui, lambda: punctuality.sweep(dry_run=False))
        if result is not None:
            messagebox.showinfo("Sweep", f"{result.raised} raised.",
                                parent=gui.root)
            refresh()

    def raise_one() -> None:
        values = _form(gui, "Raise a trigger", [
            ("student_id", "Student ID", ""),
            ("action", "Action (blank = from the ladder)",
             [""] + list(punctuality.ACTIONS)),
            ("due", "Due on YYYY-MM-DD (optional)", ""),
            ("note", "Note (optional)", ""),
        ])
        if not values or not values["student_id"]:
            return
        if _run(gui, lambda: punctuality.raise_trigger(
                values["student_id"], action=values["action"] or None,
                due_on=values["due"] or None,
                note=values["note"] or None)) is not None:
            refresh()

    def act(kind: str) -> None:
        trigger_id = _selected_id(tree, gui.root)
        if trigger_id is None:
            return
        who = _actor(gui)
        if kind == "action":
            due = simpledialog.askstring("Action", "Due on (YYYY-MM-DD, "
                                         "optional):", parent=gui.root)
            if due is None:
                return
            note = simpledialog.askstring("Action", "Note (optional):",
                                          parent=gui.root)
            call = lambda: punctuality.action_trigger(  # noqa: E731
                trigger_id, actioned_by=who or "staff",
                due_on=due.strip() or None, note=(note or "").strip() or None)
        elif kind == "serve":
            call = lambda: punctuality.serve(trigger_id,  # noqa: E731
                                             actioned_by=who)
        elif kind == "missed":
            note = simpledialog.askstring("Missed", "Note (optional):",
                                          parent=gui.root)
            if note is None:
                return
            call = lambda: punctuality.mark_missed(  # noqa: E731
                trigger_id, note=note.strip() or None)
        else:
            reason = simpledialog.askstring("Waive", "Reason:",
                                            parent=gui.root)
            if not reason:
                return
            call = lambda: punctuality.waive(trigger_id,  # noqa: E731
                                             reason=reason)
        if _run(gui, call) is not None:
            refresh()

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    ttk.Button(bar, text="Sweep…", command=sweep).pack(
        side="left", padx=(6, 0))
    ttk.Button(bar, text="Raise one…", command=raise_one).pack(
        side="left", padx=(6, 0))
    actions = _bar(parent)
    ttk.Label(actions, text="Selected:").pack(side="left")
    for text, kind in (("Arrange…", "action"), ("Served", "serve"),
                       ("Missed…", "missed"), ("Waive…", "waive")):
        ttk.Button(actions, text=text,
                   command=lambda k=kind: act(k)).pack(side="left",
                                                       padx=(6, 0))
    # The action bar was packed after the table holder; keep it above.
    actions.pack_forget()
    actions.pack(anchor="w", fill="x", pady=(0, 8),
                 before=tree.master)
    refresh()


# ═══ Activities & supervised study ══════════════════════════════════

def build_activities_tab(gui, parent: ttk.Frame) -> None:
    inner = ttk.Notebook(parent)
    inner.pack(fill="both", expand=True)
    list_tab = ttk.Frame(inner, padding=8)
    roster_tab = ttk.Frame(inner, padding=8)
    register_tab = ttk.Frame(inner, padding=8)
    summary_tab = ttk.Frame(inner, padding=8)
    gaps_tab = ttk.Frame(inner, padding=8)
    inner.add(list_tab, text="Activities")
    inner.add(roster_tab, text="Roster")
    inner.add(register_tab, text="Take register")
    inner.add(summary_tab, text="Summary")
    inner.add(gaps_tab, text="Unmarked")

    pickers: list[Callable[[], None]] = []

    def changed() -> None:
        for reload in pickers:
            reload()

    _build_activity_list(gui, list_tab, changed)
    pickers.append(_build_activity_roster(gui, roster_tab))
    pickers.append(_build_activity_register(gui, register_tab))
    pickers.append(_build_activity_summary(gui, summary_tab))
    _build_activity_gaps(gui, gaps_tab)


def _activity_picker(bar) -> tuple[tk.StringVar, Callable[[], int | None],
                                   Callable[[], None]]:
    """A combobox of live activities; returns (var, selected_id, reload)."""
    var = tk.StringVar()
    ttk.Label(bar, text="Activity:").pack(side="left")
    box = ttk.Combobox(bar, textvariable=var, state="readonly", width=44)
    box.pack(side="left", padx=(4, 12))
    index: dict[str, int] = {}

    def reload() -> None:
        index.clear()
        for a in activities.list_activities():
            index[f"#{a.activity_id} {a.label}"] = a.activity_id
        box.configure(values=list(index))
        if var.get() not in index:
            var.set(next(iter(index), ""))

    reload()
    return var, (lambda: index.get(var.get())), reload


def _when(a) -> str:
    if not a.day:
        return "ad hoc"
    return day_name(a.day) + (f" P{a.period}" if a.period else "")


def _activity_form(gui, title: str, existing=None) -> dict[str, Any] | None:
    kinds = list(activities.KINDS)
    if existing is not None:
        if existing.kind in kinds:
            kinds.remove(existing.kind)
        kinds.insert(0, existing.kind)
    weeks = ["Both", "A", "B"]
    if existing is not None and existing.week in weeks:
        weeks.remove(existing.week)
        weeks.insert(0, existing.week)
    values = _form(gui, title, [
        ("name", "Name", existing.name if existing else ""),
        ("kind", "Kind", kinds),
        ("day", "Day 1=Mon..5=Fri (blank = ad hoc)",
         str(existing.day or "") if existing else ""),
        ("period", "Period (optional)",
         str(existing.period or "") if existing else ""),
        ("start_time", "Start HH:MM (optional)",
         existing.start_time or "" if existing else ""),
        ("end_time", "End HH:MM (optional)",
         existing.end_time or "" if existing else ""),
        ("room", "Room", existing.room or "" if existing else ""),
        ("staff", "Staff", existing.staff or "" if existing else ""),
        ("week", "Week", weeks),
        ("start_date", "Runs from YYYY-MM-DD (optional)",
         existing.start_date or "" if existing else ""),
        ("end_date", "Runs to YYYY-MM-DD (optional)",
         existing.end_date or "" if existing else ""),
        ("required", "Required (missing it counts against a learner)",
         existing.required if existing else True),
        ("notes", "Notes", existing.notes or "" if existing else ""),
    ])
    if not values or not values["name"]:
        return None
    return {k: (v if v != "" else None) for k, v in values.items()}


def _build_activity_list(gui, parent: ttk.Frame,
                         changed: Callable[[], None]) -> None:
    _hint(parent, "Tutorials, assemblies, enrichment and supervised private "
                  "study. 'Required' decides whether missing it counts "
                  "against a learner.")
    bar = _bar(parent)
    kind_var = tk.StringVar(value="")
    archived_var = tk.BooleanVar(value=False)
    ttk.Label(bar, text="Kind:").pack(side="left")
    ttk.Combobox(bar, textvariable=kind_var,
                 values=[""] + list(activities.KINDS), state="readonly",
                 width=18).pack(side="left", padx=(4, 12))
    ttk.Checkbutton(bar, text="Include archived",
                    variable=archived_var).pack(side="left", padx=(0, 12))
    tree = _tree(parent, [
        ("id", "#", 50), ("name", "Name", 200), ("kind", "Kind", 130),
        ("when", "When", 100), ("week", "Week", 50), ("room", "Room", 70),
        ("staff", "Staff", 100), ("required", "Req", 40),
        ("active", "Active", 50), ("roster", "Roster", 60),
    ])

    def refresh() -> None:
        rows = activities.list_activities(
            kind=kind_var.get() or None, active_only=not archived_var.get())
        _fill(tree, [(a.activity_id, a.name, a.kind, _when(a), a.week,
                      a.room or "", a.staff or "",
                      "yes" if a.required else "no",
                      "yes" if a.active else "no",
                      activities.count_members(a.activity_id))
                     for a in rows])

    def create() -> None:
        values = _activity_form(gui, "New activity")
        if values is None:
            return
        activity = _run(gui, lambda: activities.create_activity(values))
        if activity is None:
            return
        refresh()
        changed()
        labels, ids = _group_choices()
        if labels and messagebox.askyesno(
                "Roster", "Add a whole class group to the roster now?",
                parent=gui.root):
            picked = _form(gui, "Add class group", [("group", "Group",
                                                      labels)])
            if picked and picked["group"] in ids:
                n = _run(gui, lambda: activities.enrol_class_group(
                    activity.activity_id, ids[picked["group"]]))
                if n is not None:
                    messagebox.showinfo("Roster", f"Added {n} learner(s).",
                                        parent=gui.root)
                    refresh()

    def edit() -> None:
        activity_id = _selected_id(tree, gui.root)
        if activity_id is None:
            return
        existing = activities.get_activity(activity_id)
        if existing is None:
            return
        values = _activity_form(gui, f"Edit {existing.name}", existing)
        if values is None:
            return
        if _run(gui, lambda: activities.update_activity(
                activity_id, values)) is not None:
            refresh()
            changed()

    def archive() -> None:
        activity_id = _selected_id(tree, gui.root)
        if activity_id is None:
            return
        if not messagebox.askyesno(
                "Archive", "Archive this activity? Its registers are kept.",
                parent=gui.root):
            return
        if _run(gui, lambda: activities.archive_activity(
                activity_id)) is not None:
            refresh()
            changed()

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    ttk.Button(bar, text="New…", command=create).pack(
        side="left", padx=(6, 0))
    ttk.Button(bar, text="Edit…", command=edit).pack(
        side="left", padx=(6, 0))
    ttk.Button(bar, text="Archive", command=archive).pack(
        side="left", padx=(6, 0))
    refresh()


def _build_activity_roster(gui, parent: ttk.Frame) -> Callable[[], None]:
    bar = _bar(parent)
    var, selected, reload = _activity_picker(bar)
    tree = _tree(parent, [("student", "Student ID", 140)])

    def refresh(_event=None) -> None:
        activity_id = selected()
        _fill(tree, [(sid,) for sid in
                     (activities.list_members(activity_id)
                      if activity_id else [])])

    def add() -> None:
        activity_id = selected()
        if activity_id is None:
            return
        sid = simpledialog.askstring("Add", "Student ID:", parent=gui.root)
        if sid and _run(gui, lambda: activities.add_member(
                activity_id, sid.strip())) is not None:
            refresh()

    def remove() -> None:
        activity_id = selected()
        sid = _selected_value(tree, gui.root)
        if activity_id is None or sid is None:
            return
        if _run(gui, lambda: activities.remove_member(activity_id, sid)):
            refresh()

    def add_group() -> None:
        activity_id = selected()
        labels, ids = _group_choices()
        if activity_id is None or not labels:
            return
        picked = _form(gui, "Add class group", [("group", "Group", labels)])
        if picked and picked["group"] in ids:
            n = _run(gui, lambda: activities.enrol_class_group(
                activity_id, ids[picked["group"]]))
            if n is not None:
                messagebox.showinfo("Roster", f"Added {n} learner(s).",
                                    parent=gui.root)
                refresh()

    def reload_all() -> None:
        reload()
        refresh()

    var.trace_add("write", lambda *_a: refresh())
    ttk.Button(bar, text="Add learner…", command=add).pack(side="left")
    ttk.Button(bar, text="Remove selected", command=remove).pack(
        side="left", padx=(6, 0))
    ttk.Button(bar, text="Add class group…", command=add_group).pack(
        side="left", padx=(6, 0))
    refresh()
    return reload_all


def _build_activity_register(gui, parent: ttk.Frame) -> Callable[[], None]:
    bar = _bar(parent)
    var, selected, reload = _activity_picker(bar)
    date_var = tk.StringVar(value=_today())
    _labelled_entry(bar, "Date:", date_var)
    code_labels = [f"{m.code} — {m.label}" for m in codes.MARK_CODES]
    code_of = {label: label.split(" — ", 1)[0] for label in code_labels}
    label_of = {code: label for label, code in code_of.items()}
    banner = ttk.Label(parent, text="", foreground="#a60")
    banner.pack(anchor="w", pady=(0, 4))
    actions = _bar(parent)
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    rows: dict[str, tk.StringVar] = {}

    def load() -> None:
        for w in holder.winfo_children():
            w.destroy()
        rows.clear()
        activity_id = selected()
        if activity_id is None:
            banner.configure(text="No activities yet — create one first.")
            return
        date_s = date_var.get().strip()
        entries = _run(gui, lambda: activities.register_view(activity_id,
                                                             date_s))
        if entries is None:
            return
        if not entries:
            banner.configure(text="Nobody on the roster for that date.")
            return
        banner.configure(text=("" if activities.meets_on(activity_id, date_s)
                               else "This activity is not scheduled to meet "
                                    "that day — marks will still be saved."))
        canvas = tk.Canvas(holder, highlightthickness=0)
        scroll = ttk.Scrollbar(holder, orient="vertical",
                               command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda _e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for i, entry in enumerate(entries):
            ttk.Label(inner, text=entry.student_id, width=12).grid(
                row=i, column=0, sticky="w", pady=1)
            ttk.Label(inner, text=entry.full_name, width=28).grid(
                row=i, column=1, sticky="w")
            current = entry.mark.code if entry.mark else "/"
            v = tk.StringVar(value=label_of.get(current, code_labels[0]))
            ttk.Combobox(inner, textvariable=v, values=code_labels,
                         state="readonly", width=40).grid(
                row=i, column=2, sticky="w", padx=(6, 0))
            rows[entry.student_id] = v

    def set_all() -> None:
        if not rows:
            return
        picked = _form(gui, "Mark everyone", [("code", "Code", code_labels)])
        if picked:
            for v in rows.values():
                v.set(picked["code"])

    def save() -> None:
        activity_id = selected()
        if activity_id is None or not rows:
            return
        payload = {sid: {"code": code_of[v.get()]} for sid, v in rows.items()}
        n = _run(gui, lambda: activities.save_register(
            activity_id, date_var.get().strip(), payload, actor=_actor(gui)))
        if n is not None:
            messagebox.showinfo("Saved", f"Saved {n} mark(s).",
                                parent=gui.root)
            load()

    def reload_all() -> None:
        reload()
        load()

    ttk.Button(bar, text="Load", command=load).pack(side="left")
    ttk.Button(actions, text="Mark everyone as…", command=set_all).pack(
        side="left")
    ttk.Button(actions, text="Save register", command=save).pack(
        side="left", padx=(6, 0))
    load()
    return reload_all


def _build_activity_summary(gui, parent: ttk.Frame) -> Callable[[], None]:
    bar = _bar(parent)
    var, selected, reload = _activity_picker(bar)
    from_var = tk.StringVar(value=_days_ago(_WINDOW_DAYS))
    to_var = tk.StringVar(value=_today())
    _labelled_entry(bar, "From:", from_var)
    _labelled_entry(bar, "To:", to_var)
    overall_var = tk.StringVar()
    ttk.Label(parent, textvariable=overall_var, foreground="#555").pack(
        anchor="w", pady=(0, 6))
    tree = _tree(parent, [
        ("student", "Student", 120), ("sessions", "Sessions", 80),
        ("attending", "Attended", 80), ("auth", "Authorised", 80),
        ("unauth", "Unauthorised", 90), ("nc", "Not counted", 90),
        ("pct", "%", 70),
    ])

    def refresh() -> None:
        activity_id = selected()
        if activity_id is None:
            _fill(tree, [])
            overall_var.set("")
            return
        kwargs = {"date_from": from_var.get().strip() or None,
                  "date_to": to_var.get().strip() or None}
        overall = _run(gui, lambda: activities.summary_for_activity(
            activity_id, **kwargs))
        per = _run(gui, lambda: activities.per_student_summary(
            activity_id, **kwargs)) or {}
        if overall is not None:
            overall_var.set(f"Overall: {overall.attending}/{overall.possible} "
                            f"({_pct(overall.percentage)}) across "
                            f"{overall.sessions} mark(s)")
        _fill(tree, [(sid, s.sessions, s.attending, s.authorised,
                      s.unauthorised, s.not_counted, _pct(s.percentage))
                     for sid, s in sorted(per.items())])

    def reload_all() -> None:
        reload()
        refresh()

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    refresh()
    return reload_all


def _build_activity_gaps(gui, parent: ttk.Frame) -> None:
    _hint(parent, "Nobody chases a club register unprompted. This is the "
                  "list of sessions that met and were not (fully) marked.")
    bar = _bar(parent)
    from_var = tk.StringVar(value=_days_ago(_WINDOW_DAYS))
    to_var = tk.StringVar(value=_today())
    kind_var = tk.StringVar(value="")
    _labelled_entry(bar, "From:", from_var)
    _labelled_entry(bar, "To:", to_var)
    ttk.Label(bar, text="Kind:").pack(side="left")
    ttk.Combobox(bar, textvariable=kind_var,
                 values=[""] + list(activities.KINDS), state="readonly",
                 width=18).pack(side="left", padx=(4, 12))
    tree = _tree(parent, [
        ("date", "Date", 100), ("id", "#", 50), ("name", "Activity", 220),
        ("kind", "Kind", 130), ("staff", "Staff", 120),
        ("marked", "Marked", 70), ("expected", "Expected", 70),
    ])

    def refresh() -> None:
        missing = _run(gui, lambda: activities.missing_registers(
            date_from=from_var.get().strip(), date_to=to_var.get().strip(),
            kind=kind_var.get() or None)) or []
        _fill(tree, [(m.date, m.activity.activity_id, m.activity.name,
                      m.activity.kind, m.activity.staff or "", m.marked,
                      m.expected) for m in missing])

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    refresh()
