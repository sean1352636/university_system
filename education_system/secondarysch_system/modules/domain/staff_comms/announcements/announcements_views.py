"""Tkinter views for Secondary School Announcements."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.shared import branding
from education_system.secondarysch_system.modules.domain.staff_comms.announcements import (
    announcements as data,
)
from education_system.secondarysch_system.modules.domain.staff_comms.announcements.announcements import (
    AUDIENCES,
    Announcement,
    CATEGORIES,
    DEFAULT_AUDIENCES,
    DEFAULT_CATEGORY,
    DEFAULT_STATUS,
    PRIORITIES,
    STATUSES,
    ValidationError,
    priority_label,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Draft":     ("#fff7e6", "#7a5800"),
    "Scheduled": ("#e6f0ff", "#1a3f8c"),
    "Published": ("#e6f7e6", "#0d6b2a"),
    "Expired":   ("#eeeeee", "#444444"),
    "Archived":  ("#dddddd", "#444444"),
    "Withdrawn": ("#ffd1d1", "#8c0d0d"),
}


def open_announcements_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Announcements — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    AnnouncementsTab(nb, scope="live",      label="Live Now")
    AnnouncementsTab(nb, scope="scheduled", label="Scheduled")
    AnnouncementsTab(nb, scope="pinned",    label="Pinned")
    AnnouncementsTab(nb, scope="banners",   label="Banners")
    AnnouncementsTab(nb, scope="expired",   label="Expired")
    AnnouncementsTab(nb, scope="all",       label="All")
    SummaryTab(nb)


class AnnouncementsTab:
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
        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_cat = ttk.Combobox(bar,
                                    values=("",) + CATEGORIES,
                                    state="readonly", width=20)
        self.f_cat.current(0)
        self.f_cat.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly",
                                           width=14)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Audience:").pack(side="left")
        self.f_aud = ttk.Combobox(bar,
                                    values=("",) + AUDIENCES,
                                    state="readonly", width=12)
        self.f_aud.current(0)
        self.f_aud.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Min P:").pack(side="left")
        self.f_pri = ttk.Combobox(bar,
                                    values=("",) + tuple(str(p)
                                                           for p in PRIORITIES),
                                    state="readonly", width=4)
        self.f_pri.current(0)
        self.f_pri.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Title:").pack(side="left")
        self.f_title = ttk.Entry(bar, width=20)
        self.f_title.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "pin", "ban", "category", "priority",
                "title", "audiences", "publish", "expires",
                "status", "views")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "pin": 40, "ban": 40,
                   "category": 150, "priority": 90,
                   "title": 280, "audiences": 200,
                   "publish": 100, "expires": 100,
                   "status": 110, "views": 70}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "pin",
                                                  "ban",
                                                  "priority",
                                                  "views")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("urgent", background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.tag_configure("live", background="#d6ffd6",
                                  foreground="#0d6b2a")
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",          self._edit),
                ("Publish",       self._publish),
                ("Schedule",      self._schedule),
                ("Withdraw",      self._withdraw),
                ("Archive",       self._archive),
                ("Toggle pin",    self._toggle_pin),
                ("Toggle banner", self._toggle_banner),
                ("Change status", self._set_status),
                ("Auto-expire",   self._auto_expire),
                ("Delete",        self._delete),
                ("Refresh",       self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_cat.get():
            f["category"] = self.f_cat.get()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.f_aud.get():
            f["audience"] = self.f_aud.get()
        if self.f_pri.get():
            f["priority_min"] = int(self.f_pri.get())
        if self.f_title.get().strip():
            f["title_like"] = self.f_title.get().strip()
        if self.scope == "live":
            f["live_only"] = True
        elif self.scope == "scheduled":
            f["scheduled_only"] = True
        elif self.scope == "pinned":
            f["pinned_only"] = True
        elif self.scope == "banners":
            f["banner_only"] = True
        elif self.scope == "expired":
            f["expired_unarchived"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_announcements(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Announcements", str(e),
                                    parent=self.frame)
            return
        for a in rows:
            tag = ("urgent" if a.priority >= 4
                     else "live" if a.is_live
                     else a.status)
            self.tree.insert(
                "", "end", iid=str(a.announcement_id),
                values=(a.announcement_id,
                         "★" if a.pinned else "",
                         "B" if a.banner else "",
                         a.category,
                         f"{a.priority} "
                         f"{priority_label(a.priority)[:3]}",
                         a.title, ",".join(a.audience_list),
                         a.publish_on or "—",
                         a.expires_on or "—",
                         a.status, a.view_count),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} announcement(s)")

    def _selected(self) -> Announcement | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Announcements",
                                  "Select an announcement first.",
                                  parent=self.frame)
            return None
        return data.get_announcement(int(sel[0]))

    def _new(self) -> None:
        if AnnouncementEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        a = self._selected()
        if a and AnnouncementEditor(
                self.frame,
                announcement=a).result is not None:
            self.refresh()

    def _publish(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.publish(a.announcement_id)
        except ValidationError as e:
            messagebox.showerror("Announcements", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _schedule(self) -> None:
        a = self._selected()
        if not a:
            return
        when = _prompt_text(self.frame,
                              "Publish on (YYYY-MM-DD)",
                              initial=a.publish_on or "")
        if not when:
            return
        try:
            data.schedule(a.announcement_id, publish_on=when)
        except ValidationError as e:
            messagebox.showerror("Announcements", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _withdraw(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.withdraw(a.announcement_id)
        except ValidationError as e:
            messagebox.showerror("Announcements", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _archive(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.archive(a.announcement_id)
        except ValidationError as e:
            messagebox.showerror("Announcements", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _toggle_pin(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.toggle_pin(a.announcement_id)
        except ValidationError as e:
            messagebox.showerror("Announcements", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _toggle_banner(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.toggle_banner(a.announcement_id)
        except ValidationError as e:
            messagebox.showerror("Announcements", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        a = self._selected()
        if not a:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES),
                                default=a.status)
        if not new:
            return
        try:
            data.set_status(a.announcement_id, new)
        except ValidationError as e:
            messagebox.showerror("Announcements", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _auto_expire(self) -> None:
        n = data.auto_expire()
        messagebox.showinfo("Announcements",
                              f"{n} announcement(s) moved to "
                              "Expired.",
                              parent=self.frame)
        self.refresh()

    def _delete(self) -> None:
        a = self._selected()
        if not a:
            return
        if not messagebox.askyesno(
                "Announcements",
                f"Delete announcement #{a.announcement_id}?",
                parent=self.frame):
            return
        data.delete_announcement(a.announcement_id)
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
        self.text.insert("end", "Announcements Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total              : {s.total}\n"
                            f"Drafts             : {s.drafts}\n"
                            f"Scheduled          : {s.scheduled}\n"
                            f"Published          : {s.published}\n"
                            f"Live now           : {s.live_now}\n"
                            f"Expired unarchived : {s.expired_unarchived}\n"
                            f"Pinned             : {s.pinned}\n"
                            f"Banners            : {s.banners}\n"
                            f"Urgent (P>=4)      : {s.urgent_count}\n"
                            f"Total views        : {s.total_views}\n\n")
        self.text.insert("end", "By category:\n")
        for k in CATEGORIES:
            n = s.by_category.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy priority:\n")
        for p in PRIORITIES:
            n = s.by_priority.get(p, 0)
            if n:
                self.text.insert("end",
                                    f"  {p}  {priority_label(p):<12}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy audience:\n")
        for k in AUDIENCES:
            n = s.by_audience.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.config(state="disabled")


# ── Editor ──────────────────────────────────────────────

class AnnouncementEditor:
    def __init__(self, parent, *,
                 announcement: Announcement | None = None) -> None:
        self.announcement = announcement
        self.result: Announcement | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit announcement #{announcement.announcement_id}"
            if announcement else "New announcement")
        self.win.geometry("860x820")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if announcement:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.bools: dict[str, tk.BooleanVar] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        entry(0, 0, "Title*", "title", width=48)
        combo(1, 0, "Category*", "category", CATEGORIES)
        combo(1, 2, "Priority*", "priority",
                 tuple(str(p) for p in PRIORITIES))
        entry(2, 0, "Author", "author")
        combo(2, 2, "Status*", "status", STATUSES)
        entry(3, 0, "Publish on (YYYY-MM-DD)", "publish_on")
        entry(3, 2, "Expires on (YYYY-MM-DD)", "expires_on")
        entry(4, 0, "Published on", "published_on")
        entry(4, 2, "Attachments ref", "attachments_ref")
        entry(5, 0, "Linked to", "linked_to", width=48)

        # Audiences panel
        aud_frame = ttk.LabelFrame(body, text="Audiences")
        aud_frame.grid(row=6, column=0, columnspan=4,
                          sticky="ew", padx=4, pady=(8, 4))
        self.audience_vars: dict[str, tk.BooleanVar] = {}
        for i, aud in enumerate(AUDIENCES):
            v = tk.BooleanVar()
            self.audience_vars[aud] = v
            ttk.Checkbutton(aud_frame, text=aud,
                             variable=v).grid(
                row=0, column=i, sticky="w", padx=6, pady=4)

        flags = ttk.LabelFrame(body, text="Flags")
        flags.grid(row=7, column=0, columnspan=4,
                     sticky="ew", padx=4, pady=(8, 4))
        for col, (key, label) in enumerate((
                ("pinned",                   "Pinned"),
                ("banner",                   "Banner"),
                ("requires_acknowledgement", "Requires ack."),
                ("comments_enabled",         "Comments enabled"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=0, column=col, sticky="w", padx=6, pady=4)

        row = 8
        for key, label in (
                ("summary", "Summary"),
                ("body",    "Body"),
                ("notes",   "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            h = 5 if key == "body" else 3
            t = tk.Text(body, height=h, width=74, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["category"].set(DEFAULT_CATEGORY)
        self.vars["priority"].set("2")
        self.vars["status"].set(DEFAULT_STATUS)
        for aud in DEFAULT_AUDIENCES:
            self.audience_vars[aud].set(True)

    def _load(self) -> None:
        a = self.announcement
        assert a is not None
        for key in ("title", "category", "author", "status",
                     "publish_on", "expires_on",
                     "published_on", "attachments_ref",
                     "linked_to"):
            self.vars[key].set(getattr(a, key) or "")
        self.vars["priority"].set(str(a.priority))
        for aud in AUDIENCES:
            self.audience_vars[aud].set(
                aud in a.audience_list)
        for k in self.bools:
            self.bools[k].set(getattr(a, k))
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(a, k) or "")

    def _save(self) -> None:
        auds = [a for a, v in self.audience_vars.items()
                 if v.get()]
        payload: dict = {
            "audiences": auds,
        }
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.announcement:
                self.result = data.update_announcement(
                    self.announcement.announcement_id, payload)
            else:
                self.result = data.create_announcement(payload)
        except ValidationError as exc:
            messagebox.showerror("Announcements", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


def _prompt_text(parent, title: str, *,
                  initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("360x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    ttk.Entry(win, textvariable=var).pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get().strip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("320x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_announcements_window"]
