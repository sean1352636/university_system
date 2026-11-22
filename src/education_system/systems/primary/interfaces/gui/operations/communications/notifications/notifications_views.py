"""Tkinter views for Primary School Notifications."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox
from education_system.systems.primary.interfaces.gui import kit
from education_system.systems.primary.domain.operations.communications.notifications import (
    notifications as data,
)
from education_system.systems.primary.domain.operations.communications.notifications.notifications import (
    CHANNELS,
    DEFAULT_CHANNEL,
    DEFAULT_NOTIFICATION_TYPE,
    DEFAULT_RECIPIENT_TYPE,
    DEFAULT_STATUS,
    Notification,
    NOTIFICATION_TYPES,
    PRIORITIES,
    RECIPIENT_TYPES,
    STATUSES,
    ValidationError,
    priority_label,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Draft":        ("#fff7e6", "#7a5800"),
    "Scheduled":    ("#e6f0ff", "#1a3f8c"),
    "Sent":         ("#e6f7ff", "#0a5575"),
    "Delivered":    ("#e6f7e6", "#0d6b2a"),
    "Read":         ("#dddddd", "#444444"),
    "Acknowledged": ("#d6ffd6", "#0d6b2a"),
    "Dismissed":    ("#eeeeee", "#666666"),
    "Failed":       ("#ffd1d1", "#8c0d0d"),
    "Expired":      ("#eeeeee", "#888888"),
}


# ── Pickers local to this screen ────────────────────────────────────

def _priority_choices() -> list[tuple[str, str]]:
    return [(str(p), f"{p} - {priority_label(p)}") for p in PRIORITIES]


def _contact_choices() -> list[tuple[str, str]]:
    """Parent contacts as ``(contact id, "Name (Mother of Pupil)")``."""
    try:
        from education_system.systems.primary.domain.operations.communications.parent_contacts import (
            parent_contacts as pc,
        )
        rows = pc.list_contacts_with_detail()
    except Exception:  # noqa: BLE001 - an empty list beats a broken form
        logger.exception("parent contact list for picker failed")
        return []
    rows.sort(key=lambda r: (r.contact.last_name.lower(), r.contact.first_name.lower()))
    return [(str(r.contact.contact_id),
             f"{r.contact.full_name} ({r.contact.relationship} of {r.student_name})")
            for r in rows]


def _recipient_choices(recipient_type: str) -> list[tuple[str, str]] | None:
    """The people a recipient id can be picked from for *recipient_type*;
    ``None`` for types that are not a list of people (Group / Other)."""
    if recipient_type == "Student":
        return kit._pupil_choices()
    if recipient_type in ("Staff", "Tutor"):
        return kit._staff_choices(by="id", active_only=True, role=None, dsl_only=False)
    if recipient_type == "Parent":
        return _contact_choices()
    return None


def _name_from_label(label: str) -> str:
    """"Smith, Amy (P001) · Year 3" / "Amy Smith (S01) · Teacher" → the name."""
    name = label.split(" (", 1)[0].strip()
    if ", " in name:
        last, first = name.split(", ", 1)
        name = f"{first} {last}"
    return name


class _RecipientField(ttk.Frame):
    """Recipient id picked from the list that fits the recipient type
    (pupils, staff, parent contacts); typed for Group / Other. Holds the id
    in *var*; when *name_var* is given it is filled with the picked name."""

    def __init__(self, master, var: tk.StringVar, type_var: tk.StringVar,
                 name_var: tk.StringVar | None = None) -> None:
        super().__init__(master)
        self.var, self.type_var, self.name_var = var, type_var, name_var
        self._child: tk.Misc | None = None
        self._labels: dict[str, str] = {}
        self._build()
        self._trace = type_var.trace_add("write", lambda *_a: self._build())

    def _build(self) -> None:
        if self._child is not None:
            self._child.destroy()
        choices = _recipient_choices(self.type_var.get())
        if choices is None:
            self._labels = {}
            self._child = ttk.Entry(self, textvariable=self.var, width=24)
        else:
            self._labels = dict(choices)
            # type part of a name to narrow the list, as the kit's pupil / staff pickers
            self._child = kit._SearchPicker(self, self.var, choices=choices, width=44,
                                            on_change=self._picked)
        self._child.pack(side="left", fill="x", expand=True)

    def _picked(self, value: str) -> None:
        if self.name_var is not None and value in self._labels:
            self.name_var.set(_name_from_label(self._labels[value]))

    def destroy(self) -> None:
        try:
            self.type_var.trace_remove("write", self._trace)
        except (tk.TclError, ValueError):
            pass
        super().destroy()


class _DateTimeField(ttk.Frame):
    """Date + time drop-downs bound to one ISO StringVar: ``YYYY-MM-DDTHH:MM``,
    just ``YYYY-MM-DD`` when no time is picked, "" when no date."""

    def __init__(self, master, var: tk.StringVar) -> None:
        super().__init__(master)
        self.var = var
        self._busy = False
        self._d = tk.StringVar()
        self._t = tk.StringVar()
        self._show()
        kit.DateField(self, self._d).pack(side="left")
        ttk.Label(self, text="at").pack(side="left", padx=4)
        kit.TimeField(self, self._t).pack(side="left")
        for v in (self._d, self._t):
            v.trace_add("write", lambda *_a: self._sync())
        self._trace = var.trace_add("write", lambda *_a: self._show())

    def _show(self) -> None:
        if self._busy:
            return
        self._busy = True
        try:
            cur = (self.var.get() or "").strip()
            self._d.set(cur[:10])
            self._t.set(cur[11:16] if len(cur) >= 16 else "")
        finally:
            self._busy = False

    def _sync(self) -> None:
        if self._busy:
            return
        self._busy = True
        try:
            d, t = self._d.get().strip(), self._t.get().strip()
            self.var.set(f"{d}T{t}" if d and t else d)
        finally:
            self._busy = False

    def destroy(self) -> None:
        try:
            self.var.trace_remove("write", self._trace)
        except (tk.TclError, ValueError):
            pass
        super().destroy()


def open_notifications_window(parent=None) -> None:
    data.init_db()
    kit.show_page(parent, "Notifications",
                  lambda frame: _draw_notifications(frame, parent))


def _draw_notifications(parent: ttk.Frame, host=None) -> None:
    kit.page_heading(parent, "Notifications",
                     "Notices to pupils, staff and parents - schedule, send, track reads "
                     "and actions.")
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)

    NotificationsTab(nb, scope="unread",       label="Unread")
    NotificationsTab(nb, scope="needs_action", label="Needs Action")
    NotificationsTab(nb, scope="urgent",       label="Urgent")
    NotificationsTab(nb, scope="pending",      label="Scheduled/Drafts")
    NotificationsTab(nb, scope="all",          label="All")
    SummaryTab(nb)


class NotificationsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 scope: str, label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Recipient type:").pack(side="left")
        self.f_rt = kit.ChoiceField(bar, tk.StringVar(), choices=RECIPIENT_TYPES,
                                     blank=True, width=10)
        self.f_rt.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = kit.ChoiceField(bar, tk.StringVar(), choices=NOTIFICATION_TYPES,
                                     blank=True, width=14)
        self.f_type.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Channel:").pack(side="left")
        self.f_ch = kit.ChoiceField(bar, tk.StringVar(), choices=CHANNELS,
                                     blank=True, width=10)
        self.f_ch.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = kit.ChoiceField(bar, tk.StringVar(), choices=STATUSES,
                                            blank=True, width=12)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Min P:").pack(side="left")
        self.f_pri = kit.ChoiceField(bar, tk.StringVar(), choices=_priority_choices(),
                                     blank=True, width=12)
        self.f_pri.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Title:").pack(side="left")
        self.f_title = ttk.Entry(bar, width=20)
        self.f_title.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left",
                                              padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True,
                            padx=8, pady=4)
        cols = ("id", "action", "read", "priority",
                "recipient", "type", "channel", "title",
                "sent_at", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "action": 40, "read": 40,
                   "priority": 80, "recipient": 200,
                   "type": 140, "channel": 100,
                   "title": 280, "sent_at": 150,
                   "status": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "action",
                                                  "read",
                                                  "priority")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("urgent_unread",
                                  background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.tag_configure("needs_action_tag",
                                  background="#fff0c2",
                                  foreground="#7a5800")
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",            self._edit),
                ("Schedule",        self._schedule),
                ("Mark sent",       self._mark_sent),
                ("Mark delivered",  self._mark_delivered),
                ("Mark read",       self._mark_read),
                ("Acknowledge",     self._acknowledge),
                ("Dismiss",         self._dismiss),
                ("Action done",     self._mark_action_done),
                ("Mark failed",     self._mark_failed),
                ("Change status",   self._set_status),
                ("Broadcast",       self._broadcast),
                ("Auto-expire",     self._auto_expire),
                ("Delete",          self._delete),
                ("Refresh",         self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_rt.get():
            f["recipient_type"] = self.f_rt.get()
        if self.f_type.get():
            f["notification_type"] = self.f_type.get()
        if self.f_ch.get():
            f["channel"] = self.f_ch.get()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.f_pri.get():
            f["priority_min"] = int(self.f_pri.get())
        if self.f_title.get().strip():
            f["title_like"] = self.f_title.get().strip()
        if self.scope == "unread":
            f["unread_only"] = True
        elif self.scope == "needs_action":
            f["needs_action_only"] = True
        elif self.scope == "urgent":
            f["urgent_only"] = True
        elif self.scope == "pending":
            f["pending_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_notifications(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Notifications", str(e),
                                    parent=self.frame)
            return
        for n in rows:
            if (n.priority >= 4 and n.read_at is None
                    and n.status in ("Sent", "Delivered")):
                tag = "urgent_unread"
            elif n.needs_action:
                tag = "needs_action_tag"
            else:
                tag = n.status
            rcpt = f"{n.recipient_type}: {n.recipient_id}"
            if n.recipient_name:
                rcpt = f"{rcpt} ({n.recipient_name})"
            self.tree.insert(
                "", "end", iid=str(n.notification_id),
                values=(n.notification_id,
                         "!" if n.needs_action else "",
                         "·" if n.is_read else "•",
                         f"{n.priority} "
                         f"{priority_label(n.priority)[:3]}",
                         rcpt, n.notification_type, n.channel,
                         n.title, n.sent_at or "—",
                         n.status),
                tags=(tag,))
        self.count.config(
            text=f"{len(rows)} notification(s)")

    def _selected(self) -> Notification | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Notifications",
                                  "Select a notification first.",
                                  parent=self.frame)
            return None
        return data.get_notification(int(sel[0]))

    def _new(self) -> None:
        if NotificationEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        n = self._selected()
        if n and NotificationEditor(
                self.frame,
                notification=n).result is not None:
            self.refresh()

    def _schedule(self) -> None:
        n = self._selected()
        if not n:
            return
        when = _prompt_datetime(self.frame, "Scheduled for",
                                initial=n.scheduled_for or "")
        if not when:
            return
        try:
            data.schedule(n.notification_id,
                              scheduled_for=when)
        except ValidationError as e:
            messagebox.showerror("Notifications", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _mark_sent(self) -> None:
        n = self._selected()
        if not n:
            return
        try:
            data.mark_sent(n.notification_id)
        except ValidationError as e:
            messagebox.showerror("Notifications", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _mark_delivered(self) -> None:
        n = self._selected()
        if not n:
            return
        try:
            data.mark_delivered(n.notification_id)
        except ValidationError as e:
            messagebox.showerror("Notifications", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _mark_read(self) -> None:
        n = self._selected()
        if not n:
            return
        try:
            data.mark_read(n.notification_id)
        except ValidationError as e:
            messagebox.showerror("Notifications", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _acknowledge(self) -> None:
        n = self._selected()
        if not n:
            return
        try:
            data.acknowledge(n.notification_id)
        except ValidationError as e:
            messagebox.showerror("Notifications", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _dismiss(self) -> None:
        n = self._selected()
        if not n:
            return
        try:
            data.dismiss(n.notification_id)
        except ValidationError as e:
            messagebox.showerror("Notifications", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _mark_action_done(self) -> None:
        n = self._selected()
        if not n:
            return
        try:
            data.mark_action_completed(n.notification_id)
        except ValidationError as e:
            messagebox.showerror("Notifications", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _mark_failed(self) -> None:
        n = self._selected()
        if not n:
            return
        try:
            data.mark_failed(n.notification_id)
        except ValidationError as e:
            messagebox.showerror("Notifications", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        n = self._selected()
        if not n:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES),
                                default=n.status)
        if not new:
            return
        try:
            data.set_status(n.notification_id, new)
        except ValidationError as e:
            messagebox.showerror("Notifications", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _auto_expire(self) -> None:
        k = data.auto_expire()
        messagebox.showinfo("Notifications",
                              f"{k} notification(s) moved to "
                              "Expired.",
                              parent=self.frame)
        self.refresh()

    def _broadcast(self) -> None:
        if BroadcastDialog(self.frame).result:
            self.refresh()

    def _delete(self) -> None:
        n = self._selected()
        if not n:
            return
        if not messagebox.askyesno(
                "Notifications",
                f"Delete notification #{n.notification_id}?",
                parent=self.frame):
            return
        data.delete_notification(n.notification_id)
        self.refresh()


class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8,
                          pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Notifications Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total                : {s.total}\n"
                            f"Unread               : {s.unread}\n"
                            f"Pending              : {s.pending}\n"
                            f"Sent / Active        : {s.sent}\n"
                            f"Scheduled            : {s.scheduled}\n"
                            f"Needs action         : {s.needs_action}\n"
                            f"Urgent unread        : {s.urgent_unread}\n"
                            f"Expired unprocessed  : {s.expired_unprocessed}\n"
                            f"Distinct recipients  : {s.distinct_recipients}\n\n")
        self.text.insert("end", "By type:\n")
        for k in NOTIFICATION_TYPES:
            n = s.by_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy priority:\n")
        for p in PRIORITIES:
            n = s.by_priority.get(p, 0)
            if n:
                self.text.insert("end",
                                    f"  {p}  {priority_label(p):<12}: {n}\n")
        self.text.insert("end", "\nBy channel:\n")
        for k in CHANNELS:
            n = s.by_channel.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy recipient type:\n")
        for k in RECIPIENT_TYPES:
            n = s.by_recipient_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.config(state="disabled")


# ── Editor ──────────────────────────────────────────────

class NotificationEditor:
    def __init__(self, parent, *,
                 notification: Notification | None = None
                 ) -> None:
        self.notification = notification
        self.result: Notification | None = None
        self.win = make_toplevel(parent.winfo_toplevel())
        self.win.title(
            f"Edit notification #{notification.notification_id}"
            if notification else "New notification")
        self.win.geometry("900x700")
        self.win.after_idle(self.win.grab_set)
        self._build()
        if notification:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body, footer = kit.scrolled_form(self.win)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.bools: dict[str, tk.BooleanVar] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            kit.ChoiceField(body, v, choices=values, width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        def picker(row, col, label, key, make, span=1):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            make(v).grid(row=row, column=col + 1, columnspan=span,
                         sticky="w", padx=4, pady=2)

        combo(0, 0, "Recipient type*", "recipient_type",
                 RECIPIENT_TYPES)
        entry(1, 0, "Recipient name", "recipient_name", width=48)
        picker(0, 2, "Recipient*", "recipient_id",
               lambda v: _RecipientField(body, v, self.vars["recipient_type"],
                                         self.vars["recipient_name"]))
        entry(2, 0, "Title*", "title", width=48)
        combo(3, 0, "Type*", "notification_type",
                 NOTIFICATION_TYPES)
        combo(3, 2, "Channel*", "channel", CHANNELS)
        combo(4, 0, "Priority*", "priority", _priority_choices())
        combo(4, 2, "Status*", "status", STATUSES)
        picker(5, 0, "Sent by", "sent_by",
               lambda v: kit.StaffPicker(body, v, by="name", width=30))
        entry(5, 2, "Linked to", "linked_to")
        picker(6, 0, "Scheduled for", "scheduled_for",
               lambda v: _DateTimeField(body, v), span=3)
        picker(7, 0, "Expires on", "expires_on", lambda v: kit.DateField(body, v), span=3)
        entry(8, 0, "Icon", "icon")
        entry(8, 2, "URL", "url")
        entry(9, 0, "Action label", "action_label")
        entry(9, 2, "Action URL", "action_url")

        flags = ttk.LabelFrame(body, text="Flags")
        flags.grid(row=10, column=0, columnspan=4,
                     sticky="ew", padx=4, pady=(8, 4))
        for col, (key, label) in enumerate((
                ("requires_action",  "Requires action"),
                ("action_completed", "Action completed"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=0, column=col, sticky="w",
                padx=6, pady=4)

        row = 11
        for key, label in (
                ("body",  "Body"),
                ("notes", "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw",
                padx=4, pady=(6, 2))
            h = 6 if key == "body" else 3
            t = tk.Text(body, height=h, width=74, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        ttk.Button(footer, text="Save",
                    command=self._save).pack(side="right",
                                               padx=4)
        ttk.Button(footer, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["recipient_type"].set(DEFAULT_RECIPIENT_TYPE)
        self.vars["notification_type"].set(
            DEFAULT_NOTIFICATION_TYPE)
        self.vars["channel"].set(DEFAULT_CHANNEL)
        self.vars["priority"].set("2")
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        n = self.notification
        assert n is not None
        for key in ("recipient_type", "recipient_id",
                     "recipient_name", "title",
                     "notification_type", "channel",
                     "status", "sent_by", "linked_to",
                     "scheduled_for", "expires_on", "icon",
                     "url", "action_label", "action_url"):
            self.vars[key].set(getattr(n, key) or "")
        self.vars["priority"].set(str(n.priority))
        for k in self.bools:
            self.bools[k].set(getattr(n, k))
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(n, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.notification:
                self.result = data.update_notification(
                    self.notification.notification_id, payload)
            else:
                self.result = data.create_notification(payload)
        except ValidationError as exc:
            messagebox.showerror("Notifications", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class BroadcastDialog:
    def __init__(self, parent) -> None:
        self.result: list | None = None
        self.win = make_toplevel(parent.winfo_toplevel())
        self.win.title("Broadcast Notification")
        self.win.geometry("760x680")
        self.win.after_idle(self.win.grab_set)
        self._build()
        self.win.wait_window()

    def _build(self) -> None:
        body, footer = kit.scrolled_form(self.win)
        body.grid_columnconfigure(1, weight=1)

        self.vars: dict[str, tk.Variable] = {}

        def entry(row, label, key, width=40):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=1, sticky="ew",
                padx=4, pady=2)

        def combo(row, label, key, values):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            kit.ChoiceField(body, v, choices=values).grid(
                row=row, column=1, sticky="ew",
                padx=4, pady=2)

        combo(0, "Recipient type", "recipient_type",
                 RECIPIENT_TYPES)
        ttk.Label(body, text="Recipients*").grid(
            row=1, column=0, sticky="nw", padx=4, pady=2)
        self.vars["recipient_ids"] = tk.StringVar()
        self.recip_holder = ttk.Frame(body)
        self.recip_holder.grid(row=1, column=1, sticky="ew", padx=4, pady=2)
        self.recip_multi: kit.MultiPicker | None = None
        entry(2, "Title*", "title")
        combo(3, "Notification type", "notification_type",
                 NOTIFICATION_TYPES)
        combo(4, "Channel", "channel", CHANNELS)
        combo(5, "Priority", "priority", _priority_choices())
        combo(6, "Status", "status", STATUSES)
        ttk.Label(body, text="Sent by").grid(
            row=7, column=0, sticky="w", padx=4, pady=2)
        self.vars["sent_by"] = tk.StringVar()
        kit.StaffPicker(body, self.vars["sent_by"], by="name").grid(
            row=7, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(body, text="Expires on").grid(
            row=8, column=0, sticky="w", padx=4, pady=2)
        self.vars["expires_on"] = tk.StringVar()
        kit.DateField(body, self.vars["expires_on"]).grid(
            row=8, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(body, text="Body").grid(
            row=9, column=0, sticky="nw", padx=4, pady=(6, 2))
        self.body_text = tk.Text(body, height=8, width=60,
                                    wrap="word")
        self.body_text.grid(row=9, column=1, sticky="ew",
                                padx=4, pady=(6, 2))

        self.vars["recipient_type"].set(DEFAULT_RECIPIENT_TYPE)
        self.vars["notification_type"].set(
            DEFAULT_NOTIFICATION_TYPE)
        self.vars["channel"].set(DEFAULT_CHANNEL)
        self.vars["priority"].set("2")
        self.vars["status"].set(DEFAULT_STATUS)
        self._build_recipients()
        self.vars["recipient_type"].trace_add(
            "write", lambda *_a: self._build_recipients())

        ttk.Button(footer, text="Broadcast",
                    command=self._send).pack(side="right",
                                                padx=4)
        ttk.Button(footer, text="Cancel",
                    command=self.win.destroy).pack(side="right")

    def _build_recipients(self) -> None:
        """Tick-list of the people for the recipient type; typed ids
        (comma-separated) for Group / Other."""
        for child in self.recip_holder.winfo_children():
            child.destroy()
        choices = _recipient_choices(self.vars["recipient_type"].get())
        if choices is None:
            self.recip_multi = None
            ttk.Entry(self.recip_holder, textvariable=self.vars["recipient_ids"],
                      width=40).pack(fill="x")
            ttk.Label(self.recip_holder, text="comma-separated ids",
                      foreground="#888").pack(anchor="w")
            return
        self.recip_multi = kit.MultiPicker(self.recip_holder, choices, height=8)
        self.recip_multi.pack(fill="both", expand=True)
        row = ttk.Frame(self.recip_holder)
        row.pack(fill="x")
        ttk.Button(row, text="Select all",
                   command=lambda: self.recip_multi.box.selection_set(0, "end")
                   ).pack(side="left")
        ttk.Button(row, text="Clear",
                   command=lambda: self.recip_multi.box.selection_clear(0, "end")
                   ).pack(side="left", padx=4)

    def _send(self) -> None:
        rt = self.vars["recipient_type"].get()
        if self.recip_multi is not None:
            self.vars["recipient_ids"].set(",".join(self.recip_multi.get()))
        ids_raw = self.vars["recipient_ids"].get().strip()
        title = self.vars["title"].get().strip()
        if not ids_raw or not title:
            messagebox.showerror(
                "Notifications",
                "Recipients and title are required.",
                parent=self.win)
            return
        recipients = [(rt, rid.strip(), None)
                       for rid in ids_raw.split(",")
                       if rid.strip()]
        try:
            self.result = data.broadcast(
                recipients=recipients,
                title=title,
                body=self.body_text.get("1.0", "end").rstrip()
                    or None,
                notification_type=self.vars[
                    "notification_type"].get(),
                priority=int(self.vars["priority"].get()
                                 or "2"),
                channel=self.vars["channel"].get(),
                sent_by=self.vars["sent_by"].get().strip()
                    or None,
                status=self.vars["status"].get(),
                expires_on=self.vars["expires_on"].get().strip()
                    or None,
            )
        except (ValidationError, ValueError) as exc:
            messagebox.showerror("Notifications", str(exc),
                                    parent=self.win)
            return
        messagebox.showinfo(
            "Notifications",
            f"Broadcast to {len(self.result)} recipient(s).",
            parent=self.win)
        self.win.destroy()


def _prompt_datetime(parent, title: str, *,
                     initial: str = "") -> str | None:
    """Ask for a date and (optional) time; returns ISO text."""
    win = make_toplevel(parent.winfo_toplevel())
    win.title(title)
    win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    _DateTimeField(win, var).pack(anchor="w", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get().strip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right",
                                                    padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = make_toplevel(parent.winfo_toplevel())
    win.title(title); win.geometry("360x140")
    win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(
        value=default or (options[0] if options else ""))
    kit.ChoiceField(win, var, choices=options).pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right",
                                                    padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_notifications_window"]
