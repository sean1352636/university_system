"""Linked-platform sections of the superadmin dashboard.

Eight sections that look across systems rather than into one:

* **Cross-system Tasks**  — what is waiting on this user, everywhere
* **Learner 360**         — search, then the learner's whole journey
* **Transfer Monitor**    — every transition, its step history, checklist,
  handover messages, and the approve / reject / acknowledge / complete actions
* **Transfer Boards**     — the per-boundary boards (university, post-16,
  apprenticeship applications) the systems already have, reachable here
* **Event Monitor**       — the durable bus, and its dead letters
* **System Registry**     — each system's manifest, adapter and intake health
* **Identity**            — duplicate learner records, merge, backfills
* **Cross-system Reports**— the warehouse, all-systems progression, outcomes

Kept out of ``superadmin_dashboard.py`` (already four thousand lines) as a
mixin the dashboard inherits. Read-mostly: every action is gated on the
cross-system permissions in ``role_manager``, even though only superadmins
reach this window today, so the gate is already right if staff consoles
embed a section later.

Several workflow functions these screens call are being built alongside
them (``transitions.reject``/``acknowledge``/checklists,
``identity_service.find_duplicate_candidates``/``merge_journeys``,
``identity_backfill.run_all``, ``learner_360.build_learner_360``,
``destinations.outcome_summary``). Each is looked up when a button is
pressed, and a missing one produces a message, not a traceback.

The dashboard is a ``tk.Tk`` subclass, where ``getattr`` on a missing
attribute can recurse; optional state is read with ``self.__dict__.get``.
"""

from __future__ import annotations

import json
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from education_system import paths as _paths
from education_system.platform.identity.auth.role_manager import (
    PERM_EVENTS_VIEW,
    PERM_IDENTITY_MERGE,
    PERM_LEARNER360_VIEW,
    PERM_TRANSFER_VIEW,
    has_cross_system_permission,
    is_superadmin_systems,
)

logger = logging.getLogger(__name__)

CONTENT_BG = "#ecf0f1"
TEXT_DARK = "#2c3e50"
TEXT_MUTED = "#7f8c8d"
ERROR_FG = "#c0392b"

SYSTEM_LABELS = dict(_paths.SYSTEM_LABELS)
SYSTEM_ORDER = list(_paths.SYSTEM_ORDER)

#: (section key, sidebar label). Keys double as alert/task ``action`` targets.
LINKED_SECTIONS: list[tuple[str, str]] = [
    ("tasks", "Cross-system Tasks"),
    ("learner360", "Learner 360"),
    ("transfers", "Transfer Monitor"),
    ("boards", "Transfer Boards"),
    ("events", "Event Monitor"),
    ("registry", "System Registry"),
    ("identity", "Identity"),
    ("xreports", "Cross-system Reports"),
]

#: (label, module under platform.cross_system, positional args to render).
TRANSFER_BOARDS: list[tuple[str, str, tuple[str, ...]]] = [
    ("University applications — Sixth Form", "university_applications_gui", ("sixth_form",)),
    ("University applications — FE College", "university_applications_gui", ("fe_college",)),
    ("University applications — Apprenticeships", "university_applications_gui",
     ("apprenticeships",)),
    ("Post-16 destinations — Secondary", "secondary_post16_gui", ()),
    ("Apprenticeship applications — Sixth Form", "apprenticeship_applications_gui",
     ("sixth_form",)),
    ("Apprenticeship applications — FE College", "apprenticeship_applications_gui",
     ("fe_college",)),
    ("Apprenticeship applications — University", "apprenticeship_applications_gui",
     ("university",)),
]


def _label(system) -> str:
    if not system:
        return "—"
    return SYSTEM_LABELS.get(system, str(system).replace("_", " ").title())


class _BoardHost:
    """The host surface the per-boundary board ``render`` functions expect.

    They were written for a system's main window (``content_frame``,
    ``root``, ``clear_content``, ``set_status``); this gives them a frame
    inside the dashboard instead, so they run unchanged.
    """

    def __init__(self, root, frame, status_label, username: str):
        self.root = root
        self.content_frame = frame
        self.current_username = username
        self._status_label = status_label

    def clear_content(self):
        for child in self.content_frame.winfo_children():
            child.destroy()

    def set_status(self, text):
        self._status_label.config(text=text)


class LinkedPlatformSectionsMixin:
    """Sections mixed into ``SuperAdminDashboard``."""

    # ------------------------------------------------------------------
    # plumbing
    # ------------------------------------------------------------------

    def _linked_builders(self) -> dict:
        return {
            "tasks": self._build_xs_tasks,
            "learner360": self._build_xs_learner360,
            "transfers": self._build_xs_transfers,
            "boards": self._build_xs_boards,
            "events": self._build_xs_events,
            "registry": self._build_xs_registry,
            "identity": self._build_xs_identity,
            "xreports": self._build_xs_reports,
        }

    def _xs_user(self) -> dict:
        return self.__dict__.get("user_info") or {}

    def _xs_systems(self) -> list:
        return list(self._xs_user().get("systems", []))

    def _xs_db(self):
        return self.__dict__.get("_auth_db_path")

    def _xs_can(self, permission: str, system: str | None = None) -> bool:
        return has_cross_system_permission(self._xs_systems(), permission, system)

    def _xs_superadmin(self) -> bool:
        return is_superadmin_systems(self._xs_systems())

    def _xs_actor(self) -> tuple[int | None, str]:
        user = self._xs_user()
        uid = user.get("user_id") or user.get("id")
        return (uid if isinstance(uid, int) else None), str(user.get("username") or "")

    def _xs_page(self, title: str, subtitle: str) -> tk.Frame:
        page = tk.Frame(self._content_frame, bg=CONTENT_BG)
        page.pack(fill=tk.BOTH, expand=True)
        tk.Label(page, text=title, font=("Segoe UI", 18, "bold"), bg=CONTENT_BG,
                 fg=TEXT_DARK).pack(anchor=tk.W, padx=24, pady=(20, 2))
        tk.Label(page, text=subtitle, font=("Segoe UI", 10), bg=CONTENT_BG,
                 fg=TEXT_MUTED, wraplength=1000, justify=tk.LEFT).pack(
            anchor=tk.W, padx=24, pady=(0, 10))
        body = tk.Frame(page, bg=CONTENT_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 16))
        return body

    @staticmethod
    def _xs_bar(parent) -> tk.Frame:
        bar = tk.Frame(parent, bg=CONTENT_BG)
        bar.pack(fill=tk.X, pady=(0, 6))
        return bar

    @staticmethod
    def _xs_status(parent) -> tk.Label:
        label = tk.Label(parent, text="", bg=CONTENT_BG, fg=TEXT_MUTED,
                         font=("Segoe UI", 9, "italic"))
        label.pack(side=tk.LEFT, padx=10)
        return label

    @staticmethod
    def _xs_tree(parent, columns, height=12) -> ttk.Treeview:
        holder = tk.Frame(parent, bg=CONTENT_BG)
        holder.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(holder, columns=[c[0] for c in columns],
                            show="headings", height=height)
        for key, heading, width in columns:
            tree.heading(key, text=heading)
            tree.column(key, width=width, minwidth=50, anchor=tk.W)
        vsb = ttk.Scrollbar(holder, orient=tk.VERTICAL, command=tree.yview)
        hsb = ttk.Scrollbar(holder, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        return tree

    @staticmethod
    def _xs_notice(parent, text: str, colour: str = ERROR_FG) -> None:
        tk.Label(parent, text=text, bg=CONTENT_BG, fg=colour, font=("Segoe UI", 11),
                 wraplength=900, justify=tk.LEFT).pack(anchor=tk.W, pady=12)

    @staticmethod
    def _xs_text(parent, height=12) -> tk.Text:
        text = tk.Text(parent, height=height, wrap=tk.NONE, font=("Consolas", 9))
        text.pack(fill=tk.BOTH, expand=True)
        return text

    def _xs_focus(self, key: str):
        """Pop a value another section left for this one (task -> section)."""
        focus = self.__dict__.get("_xs_focus_state") or {}
        return focus.pop(key, None)

    def _xs_set_focus(self, **values) -> None:
        state = self.__dict__.get("_xs_focus_state")
        if state is None:
            state = {}
            self._xs_focus_state = state
        state.update({k: v for k, v in values.items() if v})

    # ------------------------------------------------------------------
    # Cross-system Tasks
    # ------------------------------------------------------------------

    def _build_xs_tasks(self):
        body = self._xs_page(
            "Cross-system Tasks",
            "Transfers waiting on a system you can act for, outstanding checklist "
            "items, overdue transfers, possible duplicate learners and undelivered "
            "events. Double-click a task to open it.")
        bar = self._xs_bar(body)
        tree = self._xs_tree(body, [
            ("priority", "Priority", 70), ("kind", "Type", 100),
            ("title", "Task", 420), ("system", "System", 140),
            ("detail", "Detail", 320)], height=22)
        tasks: dict[str, dict] = {}

        def refresh():
            from education_system.platform.features.calendar.cross_system_tasks import (
                list_tasks,
            )
            try:
                rows = list_tasks(self._xs_systems(), db_path=self._xs_db())
            except Exception as exc:
                messagebox.showerror("Cross-system tasks", str(exc), parent=self)
                return
            tree.delete(*tree.get_children())
            tasks.clear()
            for i, task in enumerate(rows):
                tasks[str(i)] = task
                tree.insert("", tk.END, iid=str(i), values=(
                    task["priority"], task["kind"], task["title"],
                    _label(task.get("system")), task.get("detail", "")))
            status.config(text=f"{len(rows)} task(s)")

        def open_task(_event=None):
            sel = tree.selection()
            if not sel:
                return
            task = tasks[sel[0]]
            self._xs_set_focus(transition_id=task.get("transition_id"),
                               event_id=task.get("event_id"))
            if task.get("action"):
                self._show_section(task["action"])

        ttk.Button(bar, text="Refresh", command=refresh).pack(side=tk.LEFT)
        ttk.Button(bar, text="Open", command=open_task).pack(side=tk.LEFT, padx=6)
        status = self._xs_status(bar)
        tree.bind("<Double-1>", open_task)
        refresh()

    # ------------------------------------------------------------------
    # Learner 360
    # ------------------------------------------------------------------

    def _build_xs_learner360(self):
        body = self._xs_page(
            "Learner 360",
            "Find a learner by name, canonical journey id, or any system's student "
            "id, then see their whole journey: every phase, enrolment and transfer.")
        if not self._xs_can(PERM_LEARNER360_VIEW):
            self._xs_notice(body, "You do not hold learner360.view in any system.")
            return
        bar = self._xs_bar(body)
        query = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=query, width=36)
        entry.pack(side=tk.LEFT)
        results = self._xs_tree(body, [
            ("name", "Name", 220), ("dob", "Date of birth", 110),
            ("current", "Current system", 160), ("status", "Status", 90),
            ("journey", "Journey ID", 300)], height=6)
        notebook = ttk.Notebook(body)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        journey_tab = tk.Frame(notebook, bg=CONTENT_BG)
        transfers_tab = tk.Frame(notebook, bg=CONTENT_BG)
        raw_tab = tk.Frame(notebook, bg=CONTENT_BG)
        notebook.add(journey_tab, text="Journey")
        notebook.add(transfers_tab, text="Transfers")
        notebook.add(raw_tab, text="Learner 360 record")

        journey_frame = None
        try:
            from education_system.platform.cross_system.journey_gui import StudentJourneyFrame
            journey_frame = StudentJourneyFrame(journey_tab)
            journey_frame.pack(fill=tk.BOTH, expand=True)
        except Exception as exc:
            self._xs_notice(journey_tab, f"Journey view unavailable: {exc}")
        transfers = self._xs_tree(transfers_tab, [
            ("initiated", "Started", 140), ("route", "Route", 280),
            ("status", "Status", 130), ("awaiting", "Next action", 260),
            ("transition", "Transition", 280)], height=8)
        raw = self._xs_text(raw_tab)

        def search(_event=None):
            from education_system.platform.features.analytics import transfer_monitor as tm
            try:
                rows = tm.search_learners(query.get(), db_path=self._xs_db())
            except Exception as exc:
                messagebox.showerror("Learner search", str(exc), parent=self)
                return
            results.delete(*results.get_children())
            for row in rows:
                results.insert("", tk.END, iid=row["journey_id"], values=(
                    row["name"], row["date_of_birth"], _label(row["current_system"]),
                    row["status"], row["journey_id"]))
            status.config(text=f"{len(rows)} learner(s)" if rows else
                          "No match (enter at least two characters).")

        def show(_event=None):
            sel = results.selection()
            if sel:
                self._xs_load_learner(sel[0], journey_frame, transfers, raw)

        ttk.Button(bar, text="Search", command=search).pack(side=tk.LEFT, padx=6)
        status = self._xs_status(bar)
        entry.bind("<Return>", search)
        results.bind("<<TreeviewSelect>>", show)

    def _xs_load_learner(self, journey_id, journey_frame, transfers, raw):
        from education_system.platform.features.analytics import transfer_monitor as tm
        if journey_frame is not None:
            loader = getattr(type(journey_frame), "load_journey", None) \
                or getattr(type(journey_frame), "show_journey", None)
            try:
                if loader is not None:
                    loader(journey_frame, journey_id)
                else:
                    # The frame's own lookup, driven in "Journey ID" mode.
                    from education_system.platform.cross_system.journey_gui import (
                        _LOOKUP_MODES,
                    )
                    journey_frame._mode_var.set(_LOOKUP_MODES[0][0])
                    journey_frame._id_var.set(journey_id)
                    journey_frame._lookup()
            except Exception:
                logger.warning("Could not load journey %s into the journey view",
                               journey_id, exc_info=True)
        transfers.delete(*transfers.get_children())
        for row in tm.search_transitions(journey_id=journey_id, limit=500,
                                         db_path=self._xs_db()):
            transfers.insert("", tk.END, values=(
                str(row.get("initiated_at") or "")[:16],
                f"{row['source_label']} → {row['destination_label']}",
                row["status"], row.get("awaiting_action") or "—",
                row["transition_id"]))
        raw.delete("1.0", tk.END)
        try:
            record = tm.learner_360_record(journey_id, db_path=self._xs_db())
            if record is None:
                record = {"note": "learner_360.build_learner_360 is not available yet"}
        except Exception as exc:
            record = {"error": str(exc)}
        raw.insert("1.0", json.dumps(record, indent=2, default=str))

    # ------------------------------------------------------------------
    # Transfer Monitor
    # ------------------------------------------------------------------

    def _build_xs_transfers(self):
        from education_system.platform.cross_system.enrolment_schema import (
            TRANSITION_STATUSES,
        )
        from education_system.platform.features.analytics import transfer_monitor as tm

        body = self._xs_page(
            "Transfer Monitor",
            "Every transition on the platform. Select one to see its step history, "
            "checklist and handover messages. Actions are enabled only where you "
            "hold the permission in the system that has to take them.")
        if not self._xs_can(PERM_TRANSFER_VIEW):
            self._xs_notice(body, "You do not hold transfer.view in any system.")
            return

        filters = self._xs_bar(body)
        status_var, source_var, dest_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        journey_var, open_var = tk.StringVar(), tk.BooleanVar(value=True)
        for text, var, values in (
                ("Status", status_var, ["", *TRANSITION_STATUSES, "cancelled", "rejected"]),
                ("From", source_var, ["", *SYSTEM_ORDER]),
                ("To", dest_var, ["", *SYSTEM_ORDER])):
            tk.Label(filters, text=text, bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Combobox(filters, textvariable=var, values=values, width=16,
                         state="readonly").pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(filters, text="Journey", bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(filters, textvariable=journey_var, width=24).pack(side=tk.LEFT)
        ttk.Checkbutton(filters, text="Open only", variable=open_var).pack(
            side=tk.LEFT, padx=10)

        actions = self._xs_bar(body)
        buttons: dict[str, ttk.Button] = {}

        paned = ttk.PanedWindow(body, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)
        top = tk.Frame(paned, bg=CONTENT_BG)
        bottom = tk.Frame(paned, bg=CONTENT_BG)
        paned.add(top, weight=3)
        paned.add(bottom, weight=2)
        tree = self._xs_tree(top, [
            ("initiated", "Started", 130), ("route", "Route", 260),
            ("status", "Status", 120), ("awaiting", "Next action", 250),
            ("effective", "Effective", 90), ("journey", "Journey", 250),
            ("transition", "Transition", 250)], height=10)
        detail = ttk.Notebook(bottom)
        detail.pack(fill=tk.BOTH, expand=True)
        tabs = {name: tk.Frame(detail, bg=CONTENT_BG)
                for name in ("Step history", "Checklist", "Messages")}
        for name, frame in tabs.items():
            detail.add(frame, text=name)
        history = self._xs_tree(tabs["Step history"], [
            ("when", "When", 140), ("event", "Step / event", 220),
            ("route", "Detail", 260), ("delivery", "By / delivery", 140),
            ("effective", "Effective", 90)], height=7)
        checklist = self._xs_tree(tabs["Checklist"], [
            ("item", "Item", 360), ("done", "Done", 70), ("owner", "Owner", 160)],
            height=7)
        messages = self._xs_tree(tabs["Messages"], [
            ("when", "When", 140), ("from", "From", 160), ("to", "To", 160),
            ("subject", "Subject", 420)], height=7)
        rows: dict[str, dict] = {}
        checklist_keys: dict[str, str] = {}

        def selected():
            sel = tree.selection()
            return rows.get(sel[0]) if sel else None

        def refresh():
            try:
                found = tm.search_transitions(
                    status=status_var.get() or None,
                    source_system=source_var.get() or None,
                    destination_system=dest_var.get() or None,
                    journey_id=journey_var.get().strip() or None,
                    open_only=open_var.get(), limit=1000, db_path=self._xs_db())
            except Exception as exc:
                messagebox.showerror("Transfer monitor", str(exc), parent=self)
                return
            tree.delete(*tree.get_children())
            rows.clear()
            for row in found:
                rows[row["transition_id"]] = row
                tree.insert("", tk.END, iid=row["transition_id"], values=(
                    str(row.get("initiated_at") or "")[:16],
                    f"{row['source_label']} → {row['destination_label']}",
                    row["status"], row.get("awaiting_action") or "—",
                    row.get("effective_date") or "—", row["journey_id"],
                    row["transition_id"]))
            status.config(text=f"{len(found)} transfer(s)")
            focus = self._xs_focus("transition_id")
            if focus and focus in rows:
                tree.selection_set(focus)
                tree.see(focus)
            update_buttons()

        def load_detail(_event=None):
            row = selected()
            update_buttons()
            for widget in (history, checklist, messages):
                widget.delete(*widget.get_children())
            checklist_keys.clear()
            if row is None:
                return
            try:
                info = tm.transition_detail(row["transition_id"], db_path=self._xs_db())
            except Exception as exc:
                messagebox.showerror("Transfer monitor", str(exc), parent=self)
                return
            for event in (info or {}).get("events", []):
                shown = tm.event_display(event)
                history.insert("", tk.END, values=(
                    shown["when"], shown["what"], shown["detail"], shown["who"],
                    shown["effective_date"] or ""))
            items = (info or {}).get("checklist")
            if items is None:
                checklist.insert("", tk.END, values=(
                    "The transfer workflow has no checklist yet.", "", ""))
            owners = {"source": row["source_label"],
                      "destination": row["destination_label"],
                      "both": "Both"}
            for i, item in enumerate(items or []):
                iid = f"c{i}"
                checklist_keys[iid] = str(item.get("key") or "")
                checklist.insert("", tk.END, iid=iid, values=(
                    item.get("label") or checklist_keys[iid],
                    "Yes" if tm.checklist_item_done(item) else "No",
                    owners.get(item.get("owner"), item.get("owner") or "")))
            try:
                from education_system.platform.features.messaging.messaging_service import (
                    InterSystemMessagingService,
                )
                thread = InterSystemMessagingService(
                    db_path=self._xs_db()).list_by_transition(row["transition_id"])
            except Exception:
                logger.debug("Transition messages unavailable", exc_info=True)
                thread = []
            for msg in thread:
                messages.insert("", tk.END, values=(
                    str(msg.get("created_at") or "")[:16],
                    f"{msg.get('sender_name') or ''} ({_label(msg.get('sender_system'))})",
                    msg.get("recipient_name") or _label(msg.get("recipient_system")),
                    msg.get("subject") or ""))

        def update_buttons():
            row = selected()
            for action, button in buttons.items():
                enabled = False
                if row is not None and row["status"] not in tm.CLOSED_STATUSES:
                    if action in tm.ACTIONS:
                        enabled = self._xs_can(tm.action_permission(action),
                                               tm.action_system(action, row))
                    else:
                        enabled = self._xs_can(PERM_TRANSFER_VIEW)
                button.configure(state=tk.NORMAL if enabled else tk.DISABLED)

        def act(action):
            row = selected()
            if row is None:
                return
            reason = start_date = None
            if action == "reject":
                reason = simpledialog.askstring(
                    "Reject transfer", "Reason for rejecting:", parent=self)
                if not reason:
                    return
            elif action == "complete":
                start_date = simpledialog.askstring(
                    "Complete transfer", "Start date at the destination "
                    "(YYYY-MM-DD, blank for none):", parent=self) or None
            elif not messagebox.askyesno(
                    "Confirm", f"{action.title()} transfer "
                    f"{row['source_label']} → {row['destination_label']}?", parent=self):
                return
            uid, username = self._xs_actor()
            try:
                tm.perform_action(action, row["transition_id"], actor_user_id=uid,
                                  actor=username, reason=reason, start_date=start_date,
                                  db_path=self._xs_db())
            except tm.ActionUnavailable as exc:
                messagebox.showinfo("Not available", str(exc), parent=self)
                return
            except Exception as exc:
                messagebox.showerror("Transfer action failed", str(exc), parent=self)
                return
            refresh()

        def tick():
            row = selected()
            sel = checklist.selection()
            if row is None or not sel or not checklist_keys.get(sel[0]):
                messagebox.showinfo("Checklist", "Select a checklist item first.",
                                    parent=self)
                return
            uid, username = self._xs_actor()
            try:
                tm.tick_checklist(row["transition_id"], checklist_keys[sel[0]],
                                  actor_user_id=uid, actor=username, db_path=self._xs_db())
            except Exception as exc:
                messagebox.showerror("Checklist", str(exc), parent=self)
                return
            load_detail()

        def message():
            row = selected()
            if row is None:
                return
            self._xs_message_dialog(row, load_detail)

        for action, text in (("approve", "Approve handover"), ("reject", "Reject"),
                             ("acknowledge", "Acknowledge"), ("complete", "Complete"),
                             ("tick", "Tick checklist item"), ("message", "Message…")):
            command = {"tick": tick, "message": message}.get(
                action, lambda a=action: act(a))
            buttons[action] = ttk.Button(actions, text=text, command=command,
                                         state=tk.DISABLED)
            buttons[action].pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(filters, text="Refresh", command=refresh).pack(side=tk.LEFT, padx=6)
        status = self._xs_status(filters)
        tree.bind("<<TreeviewSelect>>", load_detail)
        refresh()

    def _xs_message_dialog(self, row: dict, after) -> None:
        """Post to a transition's handover thread, as one side or the other."""
        win = tk.Toplevel(self)
        win.title("Message about this transfer")
        win.transient(self)
        ends = [s for s in (row.get("source_system"), row.get("destination_system")) if s]
        side = tk.StringVar(value=ends[0] if ends else "")
        subject, text = tk.StringVar(), None
        frame = ttk.Frame(win, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Send as").grid(row=0, column=0, sticky="w")
        ttk.Combobox(frame, textvariable=side, values=ends, state="readonly",
                     width=24).grid(row=0, column=1, sticky="w")
        ttk.Label(frame, text="Subject").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=subject, width=50).grid(row=1, column=1, sticky="we")
        text = tk.Text(frame, width=60, height=8)
        text.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=4)
        ttk.Label(frame, text="Identify the learner by journey id only; handover "
                  "details belong in the approved handover, not here.",
                  foreground=TEXT_MUTED, wraplength=420).grid(
            row=3, column=0, columnspan=2, sticky="w")

        def send():
            if not subject.get().strip():
                messagebox.showinfo("Message", "Enter a subject.", parent=win)
                return
            uid, username = self._xs_actor()
            try:
                from education_system.platform.features.messaging.messaging_service import (
                    InterSystemMessagingService,
                )
                InterSystemMessagingService(db_path=self._xs_db()).send_transition_message(
                    row["transition_id"], sender_id=uid or 0, sender_system=side.get(),
                    sender_name=username, subject=subject.get().strip(),
                    body=text.get("1.0", tk.END).strip(),
                    allow_other_systems=self._xs_superadmin())
            except Exception as exc:
                messagebox.showerror("Message", str(exc), parent=win)
                return
            win.destroy()
            after()

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="Send", command=send).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side=tk.LEFT)

    # ------------------------------------------------------------------
    # Transfer Boards
    # ------------------------------------------------------------------

    def _build_xs_boards(self):
        body = self._xs_page(
            "Transfer Boards",
            "The per-boundary boards each system already has, opened here for any "
            "source. Actions on them are the systems' own and follow their rules.")
        bar = self._xs_bar(body)
        choice = tk.StringVar(value=TRANSFER_BOARDS[0][0])
        ttk.Combobox(bar, textvariable=choice, values=[b[0] for b in TRANSFER_BOARDS],
                     state="readonly", width=48).pack(side=tk.LEFT)
        board_frame = tk.Frame(body, bg=CONTENT_BG)

        def open_board():
            import importlib
            spec = next((b for b in TRANSFER_BOARDS if b[0] == choice.get()), None)
            if spec is None:
                return
            for child in board_frame.winfo_children():
                child.destroy()
            host = _BoardHost(self, board_frame, status, self._xs_actor()[1])
            try:
                module = importlib.import_module(
                    f"education_system.platform.cross_system.{spec[1]}")
                module.render(host, *spec[2])
            except Exception as exc:
                logger.warning("Board %s failed", spec[0], exc_info=True)
                self._xs_notice(board_frame, f"{spec[0]} could not be opened: {exc}")

        ttk.Button(bar, text="Open", command=open_board).pack(side=tk.LEFT, padx=6)
        status = self._xs_status(bar)
        board_frame.pack(fill=tk.BOTH, expand=True)
        open_board()

    # ------------------------------------------------------------------
    # Event Monitor
    # ------------------------------------------------------------------

    def _build_xs_events(self):
        from education_system.platform.integrations.external import cross_system_bus as bus

        body = self._xs_page(
            "Event Monitor",
            "The durable cross-system bus: what was published, whether every "
            "consumer took it, and the deliveries it gave up on.")
        if not self._xs_can(PERM_EVENTS_VIEW):
            self._xs_notice(body, "You do not hold events.view in any system.")
            return
        superadmin = self._xs_superadmin()
        bar = self._xs_bar(body)
        name_var, status_var, system_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        for text, var, values, width in (
                ("Event", name_var, ["", *sorted(bus.KNOWN_EVENTS)], 30),
                ("Delivery", status_var, ["", *bus.DELIVERY_STATUSES], 12),
                ("System", system_var, ["", *SYSTEM_ORDER], 14)):
            tk.Label(bar, text=text, bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Combobox(bar, textvariable=var, values=values, width=width,
                         state="readonly").pack(side=tk.LEFT, padx=(0, 10))

        paned = ttk.PanedWindow(body, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)
        top, middle, bottom = (tk.Frame(paned, bg=CONTENT_BG) for _ in range(3))
        paned.add(top, weight=3)
        paned.add(middle, weight=1)
        paned.add(bottom, weight=2)
        events = self._xs_tree(top, [
            ("when", "Published", 140), ("event", "Event", 230),
            ("route", "Source → target", 240), ("delivery", "Delivery", 100),
            ("receipts", "Receipts", 70), ("journey", "Journey", 250)], height=10)
        payload = self._xs_text(middle, height=6)
        dl_bar = self._xs_bar(bottom)
        tk.Label(dl_bar, text="Dead letters", font=("Segoe UI", 11, "bold"),
                 bg=CONTENT_BG, fg=TEXT_DARK).pack(side=tk.LEFT)
        dead = self._xs_tree(bottom, [
            ("event", "Event", 220), ("consumer", "Consumer", 110),
            ("handler", "Handler", 330), ("attempts", "Attempts", 70),
            ("error", "Last error", 360)], height=6)
        event_rows: dict[str, dict] = {}
        dead_rows: dict[str, dict] = {}
        allowed = None if superadmin else sorted(
            {s for s in SYSTEM_ORDER if self._xs_can(PERM_EVENTS_VIEW, s)})

        def refresh():
            system = system_var.get() or None
            try:
                found = bus.list_events(
                    event_name=name_var.get() or None, status=status_var.get() or None,
                    systems=[system] if system else allowed, limit=500,
                    include_payload=superadmin, db_path=self._xs_db())
                failed = bus.list_failed_deliveries(limit=200, db_path=self._xs_db())
            except Exception as exc:
                messagebox.showerror("Event monitor", str(exc), parent=self)
                return
            events.delete(*events.get_children())
            dead.delete(*dead.get_children())
            event_rows.clear()
            dead_rows.clear()
            for row in found:
                event_rows[row["event_id"]] = row
                events.insert("", tk.END, iid=row["event_id"], values=(
                    str(row["created_at"])[:16], row["event_name"],
                    f"{_label(row['source_system'])} → {_label(row['target_system'])}",
                    row["delivery_status"], row["receipts"], row.get("journey_id") or ""))
            for i, row in enumerate(failed):
                if allowed is not None and row.get("consumer_system") not in allowed:
                    continue
                dead_rows[str(i)] = row
                dead.insert("", tk.END, iid=str(i), values=(
                    row["event_name"], row["consumer_system"], row["consumer_handler"],
                    row["attempts"], (row.get("error_message") or "")[:200]))
            status.config(text=f"{len(found)} event(s), {len(dead_rows)} failed "
                               "delivery(ies)")

        def show_payload(_event=None):
            payload.delete("1.0", tk.END)
            sel = events.selection()
            if not sel:
                return
            row = event_rows.get(sel[0], {})
            if "payload" not in row:
                payload.insert("1.0", "Payloads are shown to platform superadmins only.")
                return
            payload.insert("1.0", json.dumps(row["payload"], indent=2, default=str))

        def delivery_action(kind):
            sel = dead.selection()
            if not sel:
                return
            row = dead_rows[sel[0]]
            key = (row["event_id"], row["consumer_system"], row["consumer_handler"])
            if kind == "retry":
                done = bus.retry_failed_delivery(*key, db_path=self._xs_db())
            else:
                reason = simpledialog.askstring(
                    "Abandon delivery", "Why is this delivery being abandoned?",
                    parent=self)
                if not reason:
                    return
                done = bus.abandon_failed_delivery(*key, reason=reason,
                                                   db_path=self._xs_db())
            if not done:
                messagebox.showinfo("Event monitor", "That delivery has already "
                                    "changed state.", parent=self)
            refresh()

        ttk.Button(bar, text="Refresh", command=refresh).pack(side=tk.LEFT)
        status = self._xs_status(bar)
        for kind, text in (("retry", "Retry"), ("abandon", "Abandon…")):
            ttk.Button(dl_bar, text=text, command=lambda k=kind: delivery_action(k),
                       state=tk.NORMAL if superadmin else tk.DISABLED).pack(
                side=tk.LEFT, padx=6)
        events.bind("<<TreeviewSelect>>", show_payload)
        refresh()
        focus = self._xs_focus("event_id")
        if focus and focus in event_rows:
            events.selection_set(focus)
            events.see(focus)

    # ------------------------------------------------------------------
    # System Registry
    # ------------------------------------------------------------------

    def _build_xs_registry(self):
        body = self._xs_page(
            "System Registry",
            "Each system's manifest, whether it has registered a transition adapter "
            "and which sides of the contract it implements, and how its bus intake "
            "is keeping up. \"Drainer here\" describes this console's process only.")
        bar = self._xs_bar(body)
        tree = self._xs_tree(body, [
            ("key", "Key", 120), ("name", "Name", 200), ("interfaces", "Interfaces", 130),
            ("adapter", "Adapter", 260), ("drainer", "Drainer here", 90),
            ("delivered", "Delivered", 80), ("failed", "Failed", 60),
            ("dead", "Dead", 50), ("undelivered", "Undelivered", 90),
            ("inbound", "Open in", 70), ("outbound", "Open out", 75)], height=14)

        def refresh():
            from education_system.platform.features.analytics.platform_registry import (
                describe_systems,
            )
            try:
                rows = describe_systems(db_path=self._xs_db())
            except Exception as exc:
                messagebox.showerror("System registry", str(exc), parent=self)
                return
            tree.delete(*tree.get_children())
            for row in rows:
                caps = row["adapter_capabilities"]
                adapter = (", ".join(k.replace("_", " ") for k, v in caps.items() if v)
                           or "registered, no capabilities") if row["adapter_registered"] \
                    else "not registered"
                intake = row["intake"]
                tree.insert("", tk.END, values=(
                    row["key"], row["display_name"], ", ".join(row["interfaces"]),
                    adapter, "yes" if intake.get("drainer_alive") else "no",
                    intake.get("delivered", "?"), intake.get("failed", "?"),
                    intake.get("dead_letter", "?"), intake.get("undelivered", "?"),
                    row["open_inbound_transitions"], row["open_outbound_transitions"]))
            error = rows[0].get("registry_error") if rows else None
            status.config(text=f"Registry unavailable, using paths: {error}" if error
                          else f"{len(rows)} system(s)")

        def drain():
            from education_system.platform.integrations.external.bus_drainer import (
                drain_platform_once,
            )
            try:
                n = drain_platform_once(db_path=self._xs_db())
            except Exception as exc:
                messagebox.showerror("Drain", str(exc), parent=self)
                return
            messagebox.showinfo("Drain", f"Dispatched {n} event/handler pair(s) to "
                                "the shared consumers.", parent=self)
            refresh()

        def sync_calendar():
            from education_system.platform.features.calendar.transition_sync import (
                sync_transition_dates,
            )
            try:
                result = sync_transition_dates(db_path=self._xs_db())
            except Exception as exc:
                messagebox.showerror("Calendar", str(exc), parent=self)
                return
            messagebox.showinfo("Calendar", f"Wrote {result['transitions']} transfer "
                                f"date(s) and {result['reminders']} reminder(s) to the "
                                "cross-system calendar.", parent=self)

        ttk.Button(bar, text="Refresh", command=refresh).pack(side=tk.LEFT)
        state = tk.NORMAL if self._xs_superadmin() else tk.DISABLED
        ttk.Button(bar, text="Drain shared consumers now", command=drain,
                   state=state).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="Sync transfer dates to calendar", command=sync_calendar,
                   state=state).pack(side=tk.LEFT, padx=6)
        status = self._xs_status(bar)
        refresh()

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def _build_xs_identity(self):
        body = self._xs_page(
            "Identity",
            "Possible duplicate learner records, merging them into one journey, and "
            "the identity backfills that link each system's existing records.")
        can_merge = self._xs_can(PERM_IDENTITY_MERGE)
        bar = self._xs_bar(body)
        tree = self._xs_tree(body, [
            ("a", "Journey A", 260), ("b", "Journey B", 260),
            ("why", "Why", 300), ("names", "Names", 260)], height=14)
        output = self._xs_text(body, height=8)
        pairs: dict[str, tuple[str, str]] = {}

        def _name(summary: dict) -> str:
            # The candidates carry masked summaries, not raw rows; show
            # whatever scalar fields the identity service chose to expose.
            return " ".join(str(v) for k, v in (summary or {}).items()
                            if v not in (None, "") and k != "journey_id"
                            and isinstance(v, (str, int)))[:80]

        def find():
            from education_system.platform.features.analytics import transfer_monitor as tm
            try:
                candidates = tm.duplicate_candidates(db_path=self._xs_db())
            except Exception as exc:
                messagebox.showerror("Identity", str(exc), parent=self)
                return
            if candidates is None:
                status.config(text="Duplicate detection is not available yet "
                                   "(identity_service.find_duplicate_candidates).")
                return
            tree.delete(*tree.get_children())
            pairs.clear()
            for i, cand in enumerate(candidates):
                # journey_id is the suggested survivor, duplicate_id the one
                # to fold into it; the merge dialog still asks.
                pairs[str(i)] = (str(cand["journey_id"]), str(cand["duplicate_id"]))
                tree.insert("", tk.END, iid=str(i), values=(
                    cand["journey_id"], cand["duplicate_id"],
                    f"{cand.get('score')}: " + "; ".join(cand.get("reasons") or []),
                    f"{_name(cand.get('journey') or {})} / "
                    f"{_name(cand.get('duplicate') or {})}"))
            status.config(text=f"{len(pairs)} candidate pair(s)")

        def merge():
            from education_system.platform.cross_system import identity_service
            from education_system.platform.features.analytics.transfer_monitor import (
                call_flexible,
            )
            sel = tree.selection()
            if not sel:
                return
            first, second = pairs[sel[0]]
            merger = getattr(identity_service, "merge_journeys", None)
            if merger is None:
                messagebox.showinfo("Identity", "Merging is not available yet "
                                    "(identity_service.merge_journeys).", parent=self)
                return
            keep_first = messagebox.askyesnocancel(
                "Merge journeys", f"Keep journey A ({first}, the suggested survivor) "
                "and merge B into it?\n\nYes keeps A, No keeps B. Every system's view "
                "of this learner is rewritten; this cannot be undone from here.",
                parent=self)
            if keep_first is None:
                return
            keep, drop = (first, second) if keep_first else (second, first)
            reason = simpledialog.askstring("Merge journeys", "Reason for the merge:",
                                            parent=self)
            if not reason:
                return
            _uid, username = self._xs_actor()
            try:
                # merge_journeys(survivor_id, duplicate_id, *, actor, reason, ...)
                result = call_flexible(merger, keep, drop, actor=username or "superadmin",
                                       reason=reason, db_path=self._xs_db())
            except Exception as exc:
                messagebox.showerror("Merge failed", str(exc), parent=self)
                return
            output.delete("1.0", tk.END)
            output.insert("1.0", json.dumps(result, indent=2, default=str))
            find()

        def backfill():
            from education_system.platform.features.analytics.transfer_monitor import (
                call_flexible,
            )
            try:
                from education_system.platform.cross_system import identity_backfill
            except Exception as exc:
                messagebox.showerror("Backfill", str(exc), parent=self)
                return
            runner = getattr(identity_backfill, "run_all", None)
            if runner is None:
                messagebox.showinfo("Backfill", "identity_backfill.run_all is not "
                                    "available yet.", parent=self)
                return
            if not messagebox.askyesno("Backfill", "Link every system's existing "
                                       "learner records to journeys now?", parent=self):
                return
            try:
                result = call_flexible(runner)
            except Exception as exc:
                messagebox.showerror("Backfill failed", str(exc), parent=self)
                return
            output.delete("1.0", tk.END)
            output.insert("1.0", json.dumps(result, indent=2, default=str))

        ttk.Button(bar, text="Find duplicates", command=find).pack(side=tk.LEFT)
        ttk.Button(bar, text="Merge selected…", command=merge,
                   state=tk.NORMAL if can_merge else tk.DISABLED).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="Run identity backfills", command=backfill,
                   state=tk.NORMAL if self._xs_superadmin() else tk.DISABLED).pack(
            side=tk.LEFT, padx=6)
        status = self._xs_status(bar)
        find()

    # ------------------------------------------------------------------
    # Cross-system Reports
    # ------------------------------------------------------------------

    def _build_xs_reports(self):
        body = self._xs_page(
            "Cross-system Reports",
            "Headcounts and the retention funnel across all seven systems, every "
            "observed progression route with its outcomes, and where learners went.")
        notebook = ttk.Notebook(body)
        notebook.pack(fill=tk.BOTH, expand=True)
        warehouse_tab, flow_tab, outcomes_tab = (
            tk.Frame(notebook, bg=CONTENT_BG) for _ in range(3))
        notebook.add(warehouse_tab, text="Warehouse")
        notebook.add(flow_tab, text="Progression (all systems)")
        notebook.add(outcomes_tab, text="Destination outcomes")

        try:
            from education_system.platform.features.analytics.warehouse_gui import (
                WarehouseFrame,
            )
            WarehouseFrame(warehouse_tab).pack(fill=tk.BOTH, expand=True)
        except Exception as exc:
            self._xs_notice(warehouse_tab, f"Warehouse unavailable: {exc}")

        from education_system.platform.features.analytics import journey_analytics
        try:
            flow = journey_analytics.cohort_flow_all_systems(db_path=self._xs_db())
        except Exception as exc:
            self._xs_notice(flow_tab, f"Progression statistics unavailable: {exc}")
            flow = None
        if flow is not None:
            tk.Label(flow_tab, text=f"{flow['total_journeys']} learner journey(s)",
                     bg=CONTENT_BG, fg=TEXT_DARK, font=("Segoe UI", 11, "bold")).pack(
                anchor=tk.W, pady=(6, 4))
            presence = self._xs_tree(flow_tab, [
                ("system", "System", 200), ("reached", "Ever reached", 110),
                ("active", "Active now", 100)], height=7)
            for row in flow["stage_presence"]:
                presence.insert("", tk.END, values=(row["label"], row["reached"],
                                                    row["active"]))
            routes = self._xs_tree(flow_tab, [
                ("route", "Route", 300), ("total", "Total", 70),
                ("completed", "Completed", 90), ("cancelled", "Cancelled", 90),
                ("progress", "In progress", 90), ("rate", "Completion %", 100)],
                height=8)
            for row in flow["boundaries"]:
                routes.insert("", tk.END, values=(
                    f"{row['source_label']} → {row['destination_label']}",
                    row["total"], row["completed"], row["cancelled"],
                    row["in_progress"],
                    "—" if row["completion_rate"] is None else row["completion_rate"]))

        try:
            outcomes = journey_analytics.destination_outcomes(db_path=self._xs_db())
        except Exception as exc:
            self._xs_notice(outcomes_tab, f"Destination outcomes unavailable: {exc}")
            return
        if outcomes.get("source") == "destinations":
            text = self._xs_text(outcomes_tab)
            text.insert("1.0", json.dumps(outcomes["summary"], indent=2, default=str))
            return
        tk.Label(outcomes_tab, text=(
            "From completed transfers (destinations.outcome_summary is not available "
            f"yet). destination.recorded events so far: "
            f"{outcomes['recorded_destination_events']}."),
            bg=CONTENT_BG, fg=TEXT_MUTED).pack(anchor=tk.W, pady=(6, 4))
        tree = self._xs_tree(outcomes_tab, [
            ("from", "From", 200), ("to", "To", 220),
            ("platform", "Within platform", 120), ("count", "Learners", 90)], height=12)
        for row in outcomes["by_destination"]:
            tree.insert("", tk.END, values=(
                row["source_label"], row["destination_label"],
                "yes" if row["within_platform"] else "no", row["count"]))


__all__ = ["LINKED_SECTIONS", "LinkedPlatformSectionsMixin", "TRANSFER_BOARDS"]
