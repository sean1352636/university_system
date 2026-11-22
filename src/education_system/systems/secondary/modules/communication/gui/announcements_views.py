"""Announcements screen.

The old window's tabs keep their place: **Live Now**, **Scheduled**,
**Pinned**, **Banners**, **Expired**, **All** and **Summary**. Each list keeps
its filters (Category, Status, Audience, Min P; Apply), its columns (ID, Pin,
Ban, Category, Priority, Title, Audiences, Publish, Expires, Status, Views)
and its buttons (New, Edit, Publish, Schedule, Withdraw, Archive, Toggle pin,
Toggle banner, Change status, Auto-expire, Delete, Refresh). Added to each
list: a search box, View, Read receipts, E-mail audience…, Duplicate, Export
CSV… and History.

New tabs: **Drafts** (drafts waiting to be published, yours first) and
**Feed** (what an audience sees now, as the old notices feed did; "Me" is
what you see, with Mark read and Acknowledge). The rules are in
:mod:`modules.communication.domain.announcements`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.communication.domain import announcements as AN
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
_ERRORS = W.ERRORS
_problems = W.problems
_text_window = W.text_window
_form = W.form_dialog
_PRIORITY_CHOICES = [f"{p} - {AN.PRIORITY_LABELS[p]}" for p in AN.PRIORITIES]
_TAGS = {**W.STANDARD_TAGS, "urgent": {"background": "#ffd9d9"},
         "high": {"background": "#fff0d6"}, "pinned": {"background": "#eef5ff"}}
#: tab -> list scope
_SCOPES = {"Live Now": "live", "Scheduled": "scheduled", "Pinned": "pinned",
           "Banners": "banners", "Expired": "expired", "All": "all", "Drafts": "drafts"}


def _fields(a: AN.Announcement | None) -> list:
    choices = AN.audience_choices()
    return [
        ("title", "Title", a.title if a else "", None),
        ("body", "Announcement", a.body if a else "", "text"),
        ("summary", "Summary (one line)", a.summary if a else "", None),
        ("category", "Category", a.category if a else AN.DEFAULT_CATEGORY, list(AN.CATEGORIES)),
        ("priority", "Priority", _PRIORITY_CHOICES[(a.priority if a else AN.DEFAULT_PRIORITY)
                                                   - 1], _PRIORITY_CHOICES),
        ("audiences", "Audience (pick one or more)", a.audience_list if a else [],
         ("pupils", choices)),
        ("pinned", "Pinned", a.pinned if a else False, "check"),
        ("banner", "Banner", a.banner if a else False, "check"),
        ("requires_acknowledgement", "Needs acknowledgement",
         a.requires_acknowledgement if a else False, "check"),
        ("publish_on", "Publish on (blank = when published)", a.publish_on if a else "", None),
        ("expires_on", "Expires on", a.expires_on if a else "", None),
        ("linked_to", "Linked to (event, page…)", a.linked_to if a else "", None),
        ("attachments_ref", "Attachments note", a.attachments_ref if a else "", None),
        ("notes", "Notes (staff only)", a.notes if a else "", "text"),
    ]


class AnnouncementsPage:
    TABS = ("Live Now", "Scheduled", "Pinned", "Banners", "Expired", "All", "Summary",
            "Drafts", "Feed")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.editor = AN.is_editor(principal)
        activity_log.record("announcements.view")
        ttk.Label(parent, text="Announcements", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self.lists: dict[str, dict[str, Any]] = {}
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else "Live Now"
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, _problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def _run(self, title: str, fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except _ERRORS as e:
            self._err(title, e)
            return None

    def _button(self, bar, text: str, command, enabled: bool = True) -> None:
        b = ttk.Button(bar, text=text, command=command)
        if not enabled:
            b.state(["disabled"])
        b.pack(side="left", padx=2)

    def _current(self) -> str:
        return self.TABS[self.book.index(self.book.select())]

    def _on_tab(self, _e=None) -> None:
        name = self._current()
        self.state["tab"] = name
        if name not in self._built:
            self._built.add(name)
            {"Summary": self._build_summary, "Feed": self._build_feed}.get(
                name, lambda tab: self._build_list(name, tab))(self.tabs[name])
        self._refresh(name)

    def _refresh(self, name: str) -> None:
        if name == "Summary":
            self.refresh_summary()
        elif name == "Feed":
            self.refresh_feed()
        else:
            self.refresh_list(name)

    def _refresh_all(self) -> None:
        for name in self._built:
            self._refresh(name)

    # ── the lists (the old tabs) ─────────────────────────────────────

    def _build_list(self, name: str, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        v = {"cat": tk.StringVar(), "status": tk.StringVar(), "aud": tk.StringVar(),
             "minp": tk.StringVar(), "search": tk.StringVar()}
        auds = {lab: tok for tok, lab in AN.audience_choices()}
        for label, var, values, width in (
                ("Category:", v["cat"], ["", *AN.CATEGORIES], 16),
                ("Status:", v["status"], ["", *AN.STATUSES], 11),
                ("Audience:", v["aud"], ["", *auds], 12),
                ("Min P:", v["minp"], ["", *(str(p) for p in AN.PRIORITIES)], 3)):
            ttk.Label(bar, text=label).pack(side="left", padx=(0, 2))
            ttk.Combobox(bar, textvariable=var, values=values, state="readonly",
                         width=width).pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="Search:").pack(side="left")
        ent = ttk.Entry(bar, textvariable=v["search"], width=14)
        ent.pack(side="left", padx=(2, 4))
        ent.bind("<Return>", lambda _e: self.refresh_list(name))
        self._button(bar, "Apply", lambda: self.refresh_list(name))
        tree = W.tree(tab, [("id", "ID", 45), ("pin", "Pin", 35), ("ban", "Ban", 35),
                            ("category", "Category", 110), ("priority", "Priority", 80),
                            ("title", "Title", 260), ("audiences", "Audiences", 170),
                            ("publish", "Publish", 85), ("expires", "Expires", 85),
                            ("status", "Status", 85), ("views", "Views", 50)],
                      height=14, stretch={"title", "audiences"}, tags=_TAGS)
        tree.bind("<Double-1>", lambda _e: self.view())
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(4, 0))
        ed = self.editor
        for text, cmd, ok in (("New", self.new, True), ("Edit", self.edit, True),
                              ("Publish", self.publish, True), ("Schedule", self.schedule, True),
                              ("Withdraw", self.withdraw, True), ("Archive", self.archive, True),
                              ("Toggle pin", self.toggle_pin, True),
                              ("Toggle banner", self.toggle_banner, True),
                              ("Change status", self.set_status, True),
                              ("Auto-expire", self.auto_expire, ed),
                              ("Delete", self.delete, True),
                              ("Refresh", lambda: self.refresh_list(name), True)):
            self._button(bar2, text, cmd, ok)
        bar3 = ttk.Frame(tab)
        bar3.pack(fill="x", pady=(4, 0))
        for text, cmd in (("View", self.view), ("Read receipts", self.receipts),
                          ("E-mail audience…", self.email), ("Duplicate", self.duplicate),
                          ("Export CSV…", lambda: self.export(name)),
                          ("History", self.history)):
            self._button(bar3, text, cmd)
        self.lists[name] = {"tree": tree, "vars": v, "rows": {}, "auds": auds}

    def refresh_list(self, name: str) -> None:
        x = self.lists.get(name)
        if x is None:
            return
        v = x["vars"]
        try:
            rows = AN.list_announcements(
                scope=_SCOPES[name], category=v["cat"].get() or None,
                status=v["status"].get() or None, audience=x["auds"].get(v["aud"].get()),
                priority_min=int(v["minp"].get()) if v["minp"].get() else None,
                search=v["search"].get() or None)
        except _ERRORS as e:
            self._err("Announcements", e)
            return
        if name == "Drafts":
            me = (self.principal.username or "").lower()
            rows.sort(key=lambda a: (a.author or "").lower() != me)
        tree = x["tree"]
        tree.delete(*tree.get_children())
        x["rows"] = {}
        for a in rows:
            x["rows"][str(a.announcement_id)] = a
            tag = "urgent" if a.priority == 5 else ("high" if a.priority == 4 else (
                "pinned" if a.pinned else ("muted" if a.shown_status in (
                    "Expired", "Archived", "Withdrawn") else "")))
            tree.insert("", "end", iid=str(a.announcement_id), tags=(tag,) if tag else (),
                        values=(a.announcement_id, "★" if a.pinned else "",
                                "▀" if a.banner else "", a.category,
                                f"{a.priority} {a.priority_label}", a.title, a.audience_text,
                                a.publish_on or (a.published_on or ""), a.expires_on or "",
                                a.shown_status, a.view_count))
        s = AN.summary()
        self.summary_var.set(f"Live now: {s.live_now}    Scheduled: {s.scheduled}    Drafts: "
                             f"{s.drafts}    Pinned: {s.pinned}    Urgent: {s.urgent_count}")

    def _selected(self, title: str) -> AN.Announcement | None:
        x = self.lists.get(self._current())
        sel = x["tree"].selection() if x else ()
        if not sel:
            self._info(title, "Select an announcement first.")
            return None
        return x["rows"][sel[0]]

    @staticmethod
    def _values(v: dict[str, Any]) -> dict[str, Any]:
        out = dict(v)
        out["priority"] = str(v.get("priority") or "2")[:1]
        return out

    def new(self) -> None:
        def save(v):
            a = AN.create(self._values(v), actor=self.principal)
            self._refresh_all()
            if AN.can_publish(self.principal, a.audience_list) and messagebox.askyesno(
                    "New announcement", f"Draft #{a.announcement_id} saved.\n\nPublish it now?",
                    parent=self._top()):
                self._run("Publish", lambda: AN.publish(a.announcement_id,
                                                        actor=self.principal))
                self._refresh_all()
        _form(self.parent, "New announcement", _fields(None), save,
              note="Saved as a draft. Editors publish to anyone; a head of year publishes to "
                   "their own year and forms.")

    def edit(self) -> None:
        a = self._selected("Edit")
        if a is None:
            return

        def save(v):
            AN.update(a.announcement_id, self._values(v), actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Edit announcement #{a.announcement_id}", _fields(a), save)

    def _act(self, title: str, fn: Callable[[AN.Announcement], Any]) -> None:
        a = self._selected(title)
        if a and self._run(title, lambda: fn(a)) is not None:
            self._refresh_all()

    def publish(self) -> None:
        self._act("Publish", lambda a: AN.publish(a.announcement_id, actor=self.principal))

    def schedule(self) -> None:
        a = self._selected("Schedule")
        if a is None:
            return

        def save(v):
            AN.schedule(a.announcement_id, v["day"], actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Schedule #{a.announcement_id}",
              [("day", "Publish on (YYYY-MM-DD)", a.publish_on or "", None)], save)

    def withdraw(self) -> None:
        self._act("Withdraw", lambda a: AN.withdraw(a.announcement_id, actor=self.principal))

    def archive(self) -> None:
        self._act("Archive", lambda a: AN.archive(a.announcement_id, actor=self.principal))

    def toggle_pin(self) -> None:
        self._act("Toggle pin", lambda a: AN.toggle_pin(a.announcement_id,
                                                        actor=self.principal))

    def toggle_banner(self) -> None:
        self._act("Toggle banner", lambda a: AN.toggle_banner(a.announcement_id,
                                                              actor=self.principal))

    def set_status(self) -> None:
        a = self._selected("Change status")
        if a is None:
            return

        def save(v):
            AN.set_status(a.announcement_id, v["status"], actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Status - #{a.announcement_id}",
              [("status", "Status", a.status, list(AN.STATUSES))], save)

    def auto_expire(self) -> None:
        n = self._run("Auto-expire", lambda: AN.auto_expire(actor=self.principal))
        if n is not None:
            self._refresh_all()
            self._info("Auto-expire", f"{n} announcement(s) marked Expired.")

    def delete(self) -> None:
        a = self._selected("Delete")
        if a and messagebox.askyesno("Delete", f"Delete '{a.title}'?", parent=self._top()):
            self._act("Delete", lambda a: AN.delete(a.announcement_id, actor=self.principal))

    def view(self) -> None:
        a = self._selected("View")
        if a is None:
            return
        AN.mark_read(a.announcement_id, self.principal)
        self._show(a)
        self._refresh_all()

    def _show(self, a: AN.Announcement) -> None:
        lines = [a.title, "=" * min(len(a.title), 70),
                 f"{a.category} · priority {a.priority_label} · for {a.audience_text}",
                 f"Status: {a.shown_status}   Publish: {a.publish_on or a.published_on or '-'}"
                 f"   Expires: {a.expires_on or '-'}",
                 f"By {a.author_name or a.author or '-'}   Views: {a.view_count}"
                 + ("   Needs acknowledgement" if a.requires_acknowledgement else ""), ""]
        if a.summary:
            lines += [a.summary, ""]
        lines.append(a.body)
        for label, val in (("Linked to", a.linked_to), ("Attachments", a.attachments_ref),
                           ("E-mailed", (a.emailed_at or "")[:16]), ("Notes", a.notes)):
            if val:
                lines.append(f"\n{label}: {val}")
        _text_window(self.parent, f"Announcement #{a.announcement_id}", "\n".join(lines))

    def receipts(self) -> None:
        a = self._selected("Read receipts")
        if a is None:
            return
        r = self._run("Read receipts", lambda: AN.receipts(a.announcement_id,
                                                           actor=self.principal))
        if r is None:
            return
        lines = [f"{a.title}: read by {len(r['read'])}, acknowledged by {r['acknowledged']}",
                 ""]
        lines += [f"{x['read_at'][:16]}  {x['name']:<28} {x['role'] or '':<8} "
                  + (f"acknowledged {x['acknowledged_at'][:16]}" if x["acknowledged_at"]
                     else "") for x in r["read"]]
        if r["staff_not_read"]:
            lines += ["", f"Staff who haven't read it ({len(r['staff_not_read'])}):"]
            lines += [f"  {n}" for n in r["staff_not_read"]]
        _text_window(self.parent, "Read receipts", "\n".join(lines), save_name="receipts.txt")

    def email(self) -> None:
        a = self._selected("E-mail audience")
        if a is None:
            return
        who = AN.email_recipients(a.announcement_id)
        if not messagebox.askyesno(
                "E-mail audience", f"E-mail '{a.title}' to {len(who['to'])} address(es) "
                f"({a.audience_text})?" + (f"\n\n{who['pupils_without']} pupil(s) have no "
                                           "contact with an e-mail address."
                                           if who["pupils_without"] else "")
                + ("\n\nIt was e-mailed before, on " + a.emailed_at[:16] if a.emailed_at
                   else ""), parent=self._top()):
            return
        res = self._run("E-mail audience", lambda: AN.email_audience(a.announcement_id,
                                                                     actor=self.principal))
        if not res:
            return
        self._refresh_all()
        from education_system.systems.secondary.modules.communication.gui import email_views
        text = f"{res['emails']} e-mail(s) prepared."

        def done(_report, error) -> None:
            try:
                self._info("E-mail audience", text + (f"\n\nQueued - delivery failed: {error}"
                                                      if error else "\n\nSent."))
            except tk.TclError:
                pass
        email_views.deliver_in_background(self.parent, res["message_id"], self.principal, done)

    def duplicate(self) -> None:
        self._act("Duplicate", lambda a: AN.duplicate(a.announcement_id, actor=self.principal))

    def export(self, name: str) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="announcements.csv")
        if path:
            n = self._run("Export", lambda: AN.export_csv(path, actor=self.principal,
                                                          scope=_SCOPES.get(name, "all")))
            if n is not None:
                self._info("Export", f"Exported {n} announcement(s).")

    def history(self) -> None:
        a = self._selected("History")
        if a:
            _text_window(self.parent, "History", "\n".join(
                f"{h['at']}  {h['actor']:<14} {h['action']:<12} "
                + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
                for h in AN.history(a.announcement_id)) or "No changes recorded.")

    # ── Summary (the old Summary tab) ────────────────────────────────

    def _build_summary(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._button(bar, "Refresh", self.refresh_summary)
        self.text = tk.Text(tab, wrap="word", font=("TkFixedFont", 10), state="disabled")
        self.text.pack(fill="both", expand=True)

    def refresh_summary(self) -> None:
        s = AN.summary()
        lines = ["Announcements", "-------------"]
        for label, n in (("Total", s.total), ("Drafts", s.drafts), ("Scheduled", s.scheduled),
                         ("Published", s.published), ("Live now", s.live_now),
                         ("Expired (unarchived)", s.expired_unarchived), ("Pinned", s.pinned),
                         ("Banners", s.banners), ("Urgent & live", s.urgent_count),
                         ("Total views", s.total_views)):
            lines.append(f"  {label:<22}: {n}")
        for title, d in (("By category", s.by_category), ("By status", s.by_status),
                         ("By audience", s.by_audience)):
            lines += ["", title, "-" * len(title)]
            lines += [f"  {k:<22}: {v}" for k, v in sorted(d.items())]
        lines += ["", "By priority", "-----------"]
        lines += [f"  {p} {AN.priority_label(p):<20}: {s.by_priority[p]}"
                  for p in sorted(s.by_priority)]
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")

    # ── Feed ─────────────────────────────────────────────────────────

    def _build_feed(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Feed for:").pack(side="left")
        self.feed_choices = {"Me": None, **{lab: tok for tok, lab in AN.audience_choices()}}
        self.feed_for = tk.StringVar(value=self.state.get("feed", "Me"))
        cb = ttk.Combobox(bar, textvariable=self.feed_for, values=list(self.feed_choices),
                          state="readonly", width=14)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_feed())
        self._button(bar, "Refresh", self.refresh_feed)
        self._button(bar, "Mark read", self.feed_read)
        self._button(bar, "Acknowledge", self.feed_ack)
        self.feed_note = tk.StringVar()
        ttk.Label(tab, textvariable=self.feed_note, foreground="#666").pack(anchor="w")
        self.feed_tree = W.tree(tab, [("pin", "", 30), ("priority", "Priority", 80),
                                      ("title", "Title", 320), ("for", "For", 160),
                                      ("date", "Published", 90), ("seen", "Seen", 90)],
                                height=16, stretch={"title"}, tags=_TAGS)
        self.feed_tree.bind("<Double-1>", lambda _e: self.feed_read(show=True))
        self.feed_rows: dict[str, AN.Announcement] = {}

    def refresh_feed(self) -> None:
        if not hasattr(self, "feed_tree"):
            return
        self.state["feed"] = self.feed_for.get()
        tok = self.feed_choices.get(self.feed_for.get())
        rows = AN.active_for(self.principal) if tok is None else AN.feed_for_audience(tok)
        unread = {a.announcement_id for a in AN.unread_for(self.principal)}
        ack = {a.announcement_id for a in AN.needs_acknowledgement(self.principal)}
        self.feed_tree.delete(*self.feed_tree.get_children())
        self.feed_rows = {}
        for a in rows:
            self.feed_rows[str(a.announcement_id)] = a
            seen = "needs ack" if a.announcement_id in ack else (
                "new" if a.announcement_id in unread else "read")
            self.feed_tree.insert("", "end", iid=str(a.announcement_id),
                                  tags=("urgent",) if a.priority == 5 else (
                                      ("warn",) if seen != "read" else ()),
                                  values=("★" if a.pinned else "", a.priority_label, a.title,
                                          a.audience_text, a.published_on or "", seen))
        self.feed_note.set(f"{len(rows)} showing now; {len(unread)} unread, {len(ack)} to "
                           "acknowledge (yours)")

    def _feed_selected(self) -> AN.Announcement | None:
        sel = self.feed_tree.selection()
        if not sel:
            self._info("Feed", "Select an announcement first.")
            return None
        return self.feed_rows[sel[0]]

    def feed_read(self, show: bool = False) -> None:
        a = self._feed_selected()
        if a:
            AN.mark_read(a.announcement_id, self.principal)
            if show:
                self._show(a)
            self.refresh_feed()

    def feed_ack(self) -> None:
        a = self._feed_selected()
        if a:
            self._run("Acknowledge", lambda: AN.acknowledge(a.announcement_id, self.principal))
            self.refresh_feed()


def draw_announcements(parent: ttk.Frame, *, principal: Principal, state: dict
                       ) -> AnnouncementsPage:
    return AnnouncementsPage(parent, principal=principal, state=state)
