"""Staff Absence screen (HR).

The old Staff Absence window's tabs come first, in their order - Active
Today, Open, Critical, Cover Pending, Return Overdue, RTW Overdue, All and
Summary - each with its toolbar (Staff, Type, Status on All, Cover; Apply,
New), its columns (Id, Date, Staff, Type, Exp Return, Act Return, Status,
Cover, Days Lost, Flags), its row colours and its actions (Edit, Confirm,
Arrange cover, Record return, Complete RTW, Close, Cancel, Change status,
Delete, Refresh). The absence form keeps every old field and flag.

Added: Last day, periods, paid, fit note and RTW notes on the form; Still
off (extend), Certificate, Sickness record, Cover lessons, History and
Export CSV; new tabs Requests (approve / decline planned absence), Sickness
(Bradford factor and trigger points, with the trigger settings), Calendar
and Reports. Every absence is the one the Cover screen covers - saving here
makes or moves its cover. Rules: :mod:`modules.staff.domain.staff_absence`.
"""

from __future__ import annotations

import datetime as _dt
import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.curriculum.domain import cover as CV
from education_system.systems.secondary.modules.staff.domain import staff_absence as SA
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

_ERRORS = W.ERRORS
_STATUS_TAGS = {"Reported": ("#fff7e6", "#7a5800"), "Confirmed": ("#e6f0ff", "#1a3f8c"),
                "Active": ("#fff0d6", "#7a5800"), "Returned": ("#e6f7e6", "#0d6b2a"),
                "Closed": ("#eeeeee", "#444444"), "Cancelled": ("#dddddd", "#444444")}
_SCOPES = {"Active Today": {"active_today": True}, "Open": {"open_only": True},
           "Critical": {"critical_only": True, "open_only": True},
           "Cover Pending": {"cover_outstanding": True},
           "Return Overdue": {"return_overdue": True}, "RTW Overdue": {"rtw_overdue": True},
           "All": {}}
_COLUMNS = [("id", "Id", 50), ("date", "Date", 90), ("last", "Last day", 90),
            ("staff", "Staff", 170), ("type", "Type", 160), ("exp", "Exp Return", 95),
            ("act", "Act Return", 95), ("status", "Status", 90), ("cover", "Cover", 120),
            ("days", "Days Lost", 70), ("flags", "Flags", 130)]


def _staff_label(p: dict) -> str:
    return f"{p['name']} ({p['username']})" if p.get("username") else p["name"]


def _who(text: str, choices: list[dict]) -> dict[str, Any]:
    """A staff drop-down value -> staff_username / staff_name."""
    text = (text or "").strip()
    hit = next((p for p in choices if _staff_label(p) == text or
                (p.get("username") or "").lower() == text.lower()), None)
    if hit:
        return {"staff_username": hit["username"], "staff_name": hit["name"]}
    return {"staff_username": None, "staff_name": text or None}


def _fields(r: SA.Record | None, choices: list[dict]) -> list:
    """The old editor's fields in its order, then the new ones."""
    labels = [_staff_label(p) for p in choices]
    staff = "" if r is None else (f"{r.staff_name} ({r.staff_username})"
                                  if r.staff_username else r.staff_name)
    g = (lambda k, d="": (getattr(r, k) if r is not None and getattr(r, k) is not None
                          else d))
    return [
        ("staff", "Staff*", staff, ("edit", labels)),
        ("start_date", "Absence date*", g("start_date", _dt.date.today().isoformat()), None),
        ("absence_type", "Absence type*", g("absence_type", SA.DEFAULT_ABSENCE_TYPE),
         SA.ABSENCE_TYPES),
        ("expected_return", "Expected return", g("expected_return"), None),
        ("actual_return", "Actual return", g("actual_return"), None),
        ("reason", "Reason (HR only)", g("reason"), None),
        ("notified_on", "Notified on", g("notified_on"), None),
        ("notification_method", "Notification",
         g("notification_method", SA.DEFAULT_NOTIFICATION_METHOD), SA.NOTIFICATION_METHODS),
        ("notified_by", "Notified by", g("notified_by"), None),
        ("certificate_type", "Certificate", g("certificate_type", SA.DEFAULT_CERTIFICATE_TYPE),
         SA.CERTIFICATE_TYPES),
        ("cert_received_on", "Cert received on", g("cert_received_on"), None),
        ("cover_source", "Cover source*", g("cover_source", SA.DEFAULT_COVER_SOURCE),
         SA.COVER_SOURCES),
        ("cover_arranged_by", "Cover arranged by", g("cover_arranged_by"), None),
        ("status", "Status*", g("status", SA.DEFAULT_STATUS), SA.STATUSES),
        ("rtw_meeting_on", "RTW meeting on", g("rtw_meeting_on"), None),
        ("rtw_completed_by", "RTW completed by", g("rtw_completed_by"), None),
        ("days_lost", "Days lost (blank = weekdays)", g("days_lost"), None),
        ("cover_required", "Cover required", r.cover_required if r else True, "check"),
        ("critical", "Critical absence", r.critical if r else False, "check"),
        ("parents_informed", "Parents informed", r.parents_informed if r else False, "check"),
        ("slt_informed", "SLT informed", r.slt_informed if r else False, "check"),
        ("rtw_required", "RTW required", r.rtw_required if r else True, "check"),
        ("cover_notes", "Cover notes", g("cover_notes"), "text"),
        ("notes", "Notes", g("notes"), "text"),
        ("end_date", "Last day off (blank = from expected return)", g("end_date"), None),
        ("from_period", "From period (blank = all day)", g("from_period"), None),
        ("to_period", "To period", g("to_period"), None),
        ("paid", "Paid", r.paid if r else True, "check"),
        ("fit_note_from", "Fit note from", g("fit_note_from"), None),
        ("fit_note_to", "Fit note to", g("fit_note_to"), None),
        ("rtw_notes", "RTW interview notes", g("rtw_notes"), "text"),
    ]


class StaffAbsencePage:
    TABS = (*_SCOPES, "Summary", "Requests", "Sickness", "Calendar", "Reports")
    HR_ONLY = frozenset({"Sickness", "Reports"})

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.editor = SA.is_editor(principal)
        activity_log.record("staff_absence.view", principal=principal)
        ttk.Label(parent, text="Staff Absence", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        self.lists: dict[str, dict[str, Any]] = {}
        start = state.get("tab") if state.get("tab") in self.TABS else "Active Today"
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, W.problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def _button(self, bar, text: str, command, editor_only: bool = True) -> None:
        b = ttk.Button(bar, text=text, command=command)
        if editor_only and not self.editor:
            b.state(["disabled"])
        b.pack(side="left", padx=2)

    def _run(self, title: str, fn, done: str | None = None) -> Any:
        try:
            out = fn()
        except _ERRORS as e:
            self._err(title, e)
            return None
        self._refresh_all()
        if done:
            self._info(title, done if "{" not in done else done.format(out=out))
        return out

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name in self.HR_ONLY and not self.editor:
            if name not in self._built:
                self._built.add(name)
                ttk.Label(self.tabs[name], text="Only HR can see this.",
                          foreground="#777").pack(anchor="w")
            return
        if name not in self._built:
            self._built.add(name)
            {"Summary": self._build_summary, "Requests": self._build_requests,
             "Sickness": self._build_sickness, "Calendar": self._build_calendar,
             "Reports": self._build_reports}.get(name, lambda t: self._build_list(name, t))(
                self.tabs[name])
        self._refresh(name)

    def _refresh(self, name: str) -> None:
        if name in self.HR_ONLY and not self.editor:
            return
        fn = {"Summary": self.refresh_summary, "Requests": self.refresh_requests,
              "Sickness": self.refresh_sickness, "Calendar": self.refresh_calendar,
              "Reports": self.refresh_reports}.get(name)
        if fn:
            fn()
        else:
            self.refresh_list(name)
        try:
            s = SA.summary(actor=self.principal)
            self.summary_var.set(
                f"Off today: {s['active_today']}    Open: {s['open']}    Cover pending: "
                f"{s['cover_outstanding']}    RTW to do: {s['rtw_outstanding']}    Fit notes "
                f"needed: {s['awaiting_cert']}    Requests waiting: {s['requests_waiting']}")
        except _ERRORS:
            self.summary_var.set("")

    def _refresh_all(self) -> None:
        for name in self._built:
            self._refresh(name)

    # ── The old list tabs ────────────────────────────────────────────

    def _build_list(self, name: str, tab) -> None:
        ctx: dict[str, Any] = {"rows": {}}
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        saved = self.state.setdefault("filters", {}).get(name, {})
        ctx["staff"] = tk.StringVar(value=saved.get("staff", ""))
        ctx["type"] = tk.StringVar(value=saved.get("type", ""))
        ctx["status"] = tk.StringVar(value=saved.get("status", ""))
        ctx["cover"] = tk.StringVar(value=saved.get("cover", ""))
        ttk.Label(bar, text="Staff id:").pack(side="left")
        ttk.Entry(bar, textvariable=ctx["staff"], width=12).pack(side="left", padx=(2, 8))
        combos = [("Type:", ctx["type"], SA.ABSENCE_TYPES, 22)]
        if name == "All":
            combos.append(("Status:", ctx["status"], SA.STATUSES, 12))
        combos.append(("Cover:", ctx["cover"], SA.COVER_SOURCES, 14))
        for label, var, values, width in combos:
            ttk.Label(bar, text=label).pack(side="left")
            cb = ttk.Combobox(bar, textvariable=var, values=["", *values], state="readonly",
                              width=width)
            cb.pack(side="left", padx=(2, 8))
            cb.bind("<<ComboboxSelected>>", lambda _e, n=name: self.refresh_list(n))
        ttk.Button(bar, text="Apply", command=lambda: self.refresh_list(name)).pack(
            side="left", padx=4)
        self._button(bar, "New", self.new)
        tree = W.tree(tab, _COLUMNS, height=16, stretch={"staff", "type", "flags"})
        for st, (bg, fg) in _STATUS_TAGS.items():
            tree.tag_configure(st, background=bg, foreground=fg)
        tree.tag_configure("critical", background="#ffd1d1", foreground="#8c0d0d")
        tree.tag_configure("alert", background="#ffe6cc", foreground="#a04400")
        tree.bind("<Double-1>", lambda _e: self.edit())
        ctx["tree"] = tree
        acts = ttk.Frame(tab)
        acts.pack(fill="x", pady=(4, 0))
        for text, cmd in (("Edit", self.edit), ("Confirm", self.confirm),
                          ("Arrange cover", self.arrange_cover),
                          ("Record return", self.record_return),
                          ("Complete RTW", self.complete_rtw), ("Close", self.close),
                          ("Cancel", self.cancel), ("Change status", self.change_status),
                          ("Delete", self.delete)):
            self._button(acts, text, cmd)
        self._button(acts, "Refresh", lambda: self.refresh_list(name), editor_only=False)
        ctx["count"] = ttk.Label(acts, text="")
        ctx["count"].pack(side="right")
        more = ttk.Frame(tab)
        more.pack(fill="x", pady=(4, 0))
        for text, cmd, ed in (("Still off…", self.extend, True),
                              ("Certificate…", self.certificate, True),
                              ("Sickness record", self.sickness_record, False),
                              ("Cover lessons", self.cover_lessons, False),
                              ("History", self.history, False),
                              ("Export CSV…", lambda: self.export(name), True)):
            self._button(more, text, cmd, ed)
        self.lists[name] = ctx

    def _filters(self, name: str) -> dict[str, Any]:
        ctx = self.lists[name]
        vals = {k: ctx[k].get().strip() for k in ("staff", "type", "status", "cover")}
        self.state.setdefault("filters", {})[name] = vals
        f: dict[str, Any] = dict(_SCOPES[name])
        for k, key in (("staff", "staff"), ("type", "absence_type"), ("status", "status"),
                       ("cover", "cover_source")):
            if vals[k]:
                f[key] = vals[k]
        return f

    def refresh_list(self, name: str) -> None:
        ctx = self.lists[name]
        try:
            rows = SA.list_absences(actor=self.principal, **self._filters(name))
        except _ERRORS as e:
            self._err("Staff Absence", e)
            return
        tree = ctx["tree"]
        tree.delete(*tree.get_children())
        ctx["rows"] = {}
        for r in rows:
            ctx["rows"][str(r.absence_id)] = r
            flags = r.flags
            tag = "critical" if r.critical and r.is_open else "alert" if any(
                f.isupper() for f in flags) else r.status
            cover = r.cover_source + (f" ({r.cover_pending} to do)" if r.cover_pending else "")
            tree.insert("", "end", iid=str(r.absence_id), tags=(tag,), values=(
                r.absence_id, r.start_date, r.end_date, r.staff_name, r.absence_type,
                r.expected_return or "—", r.actual_return or "—", r.status, cover,
                f"{r.days:g}", ",".join(flags)))
        ctx["count"].config(text=f"{len(rows)} absence(s)")

    def _selected(self, title: str) -> SA.Record | None:
        name = self.state.get("tab")
        ctx = self.lists.get(name or "")
        sel = ctx["tree"].selection() if ctx else ()
        if not sel:
            self._info(title, "Select an absence first.")
            return None
        return ctx["rows"][sel[0]]

    # ── Old actions ──────────────────────────────────────────────────

    def new(self) -> None:
        choices = SA.staff_choices()

        def save(v):
            data = {k: x for k, x in v.items() if k != "staff" and x not in ("", None)}
            data.update(_who(v["staff"], choices))
            rec, lessons = SA.create_absence(data, actor=self.principal)
            self._refresh_all()
            self._info("New absence", f"Absence #{rec.absence_id} recorded for "
                                      f"{rec.staff_name}: {rec.dates_label}.\n\n"
                                      f"{lessons} lesson(s) need cover - see the Cover screen.")
        W.form_dialog(self.parent, "New absence", _fields(None, choices), save,
                      note="Cover is made for the person's lessons in these dates. The reason "
                           "is seen only by HR; the Cover screen shows the category.")

    def edit(self) -> None:
        r = self._selected("Edit absence")
        if r is None:
            return
        choices = SA.staff_choices()

        def save(v):
            data = dict(v)
            data.update(_who(data.pop("staff"), choices))
            changes = {k: x for k, x in data.items() if str(x if x is not None else "") !=
                       str(getattr(r, k) if getattr(r, k) is not None else "")}
            for k in ("days_lost", "from_period", "to_period"):
                if changes.get(k) == "":
                    changes[k] = None
            _rec, added, cancelled = SA.update_absence(r.absence_id, changes,
                                                       actor=self.principal)
            self._refresh_all()
            if added or cancelled:
                self._info("Edit absence", f"Cover: {added} lesson(s) added, {cancelled} "
                                           "cancelled.")
        W.form_dialog(self.parent, f"Edit absence #{r.absence_id}", _fields(r, choices), save)

    def confirm(self) -> None:
        r = self._selected("Confirm")
        if r:
            self._run("Confirm", lambda: SA.confirm(r.absence_id, actor=self.principal))

    def arrange_cover(self) -> None:
        r = self._selected("Arrange cover")
        if r is None:
            return

        def save(v):
            SA.arrange_cover(r.absence_id, source=v["source"], arranged_by=v["by"],
                             notes=v["notes"], actor=self.principal)
            self._refresh_all()
        W.form_dialog(self.parent, f"Arrange cover - #{r.absence_id}", [
            ("source", "Source*", r.cover_source, SA.COVER_SOURCES),
            ("by", "Arranged by", r.cover_arranged_by or self.principal.username, None),
            ("notes", "Cover notes", r.cover_notes or "", "text")], save,
            note=f"{r.cover_total} lesson(s) on the Cover screen, {r.cover_pending} still "
                 "unassigned.")

    def record_return(self) -> None:
        r = self._selected("Record return")
        if r is None:
            return

        def save(v):
            rec, added, cancelled = SA.record_return(
                r.absence_id, returned_on=v["on"] or None, days_lost=v["days"] or None,
                actor=self.principal)
            self._refresh_all()
            self._info("Record return", f"{rec.staff_name} back on {rec.actual_return}. "
                                        f"Cover cancelled for {cancelled} lesson(s), added for "
                                        f"{added}." + ("\n\nA return-to-work interview is "
                                                       "due." if rec.rtw_outstanding else ""))
        W.form_dialog(self.parent, f"Record return - #{r.absence_id}", [
            ("on", "Returned on", _dt.date.today().isoformat(), None),
            ("days", "Days lost (blank=auto)", "", None)], save)

    def complete_rtw(self) -> None:
        r = self._selected("Complete RTW")
        if r is None:
            return

        def save(v):
            SA.complete_rtw(r.absence_id, completed_by=v["by"], meeting_on=v["on"] or None,
                            notes=v["notes"], actor=self.principal)
            self._refresh_all()
        W.form_dialog(self.parent, f"Return-to-work interview - #{r.absence_id}", [
            ("by", "Completed by*", self.principal.username, None),
            ("on", "Meeting on", _dt.date.today().isoformat(), None),
            ("notes", "Interview notes (HR only)", r.rtw_notes or "", "text")], save)

    def close(self) -> None:
        r = self._selected("Close")
        if r:
            self._run("Close", lambda: SA.close(r.absence_id, actor=self.principal))

    def cancel(self) -> None:
        r = self._selected("Cancel")
        if r and messagebox.askyesno("Cancel absence", f"Cancel {r.staff_name}'s absence "
                                     f"({r.dates_label}) and its open cover?",
                                     parent=self._top()):
            self._run("Cancel", lambda: SA.cancel(r.absence_id, actor=self.principal))

    def change_status(self) -> None:
        r = self._selected("Change status")
        if r is None:
            return

        def save(v):
            SA.set_status(r.absence_id, v["status"], actor=self.principal)
            self._refresh_all()
        W.form_dialog(self.parent, f"Change status - #{r.absence_id}",
                      [("status", "Status", r.status, SA.STATUSES)], save)

    def delete(self) -> None:
        r = self._selected("Delete")
        if r and messagebox.askyesno("Delete absence", f"Delete absence #{r.absence_id} "
                                     "(recorded in error) and its unassigned cover?",
                                     parent=self._top()):
            self._run("Delete", lambda: SA.delete(r.absence_id, actor=self.principal),
                      "Deleted, with {out} cover request(s).")

    # ── New actions ──────────────────────────────────────────────────

    def extend(self) -> None:
        r = self._selected("Still off")
        if r is None:
            return

        def save(v):
            _rec, added, _c = SA.extend(r.absence_id, last_day=v["last"] or None,
                                        expected_return=v["exp"] or None, actor=self.principal)
            self._refresh_all()
            self._info("Still off", f"Cover added for {added} lesson(s).")
        W.form_dialog(self.parent, f"Still off - #{r.absence_id}", [
            ("exp", "Expected return", r.expected_return or "", None),
            ("last", "Or: new last day off", "", None)], save,
            note="The last day moves; cover is made for the extra lessons.")

    def certificate(self) -> None:
        r = self._selected("Certificate")
        if r is None:
            return

        def save(v):
            SA.record_certificate(r.absence_id, certificate_type=v["type"],
                                  received_on=v["on"] or None, fit_from=v["from"] or None,
                                  fit_to=v["to"] or None, actor=self.principal)
            self._refresh_all()
        W.form_dialog(self.parent, f"Certificate - #{r.absence_id}", [
            ("type", "Certificate", "Fit Note" if r.calendar_days > SA.SELF_CERT_DAYS
             else r.certificate_type, SA.CERTIFICATE_TYPES),
            ("on", "Received on", _dt.date.today().isoformat(), None),
            ("from", "Fit note from", r.fit_note_from or "", None),
            ("to", "Fit note to", r.fit_note_to or "", None)], save,
            note=f"A self-certificate covers up to {SA.SELF_CERT_DAYS} calendar days of "
                 "sickness; after that a fit note is needed.")

    def sickness_record(self, staff: str | None = None) -> None:
        if staff is None:
            r = self._selected("Sickness record")
            if r is None:
                return
            staff = r.staff_username or r.staff_name
        try:
            rec = SA.sickness_record(staff, actor=self.principal)
        except _ERRORS as e:
            self._err("Sickness record", e)
            return
        lines = [f"Sickness record - {staff}", f"Rolling 12 months {rec['from']} to {rec['to']}",
                 "", f"Episodes (S): {rec['episodes']}    Days (D): {rec['days']:g}    "
                 f"Bradford factor (S x S x D): {rec['bradford']:g}", "",
                 "Trigger points reached: " + ("; ".join(rec["triggers"]) or "none"), "",
                 "Episodes in the window:"]
        for a in rec["absences"]:
            lines.append(f"  #{a.absence_id:<5} {a.dates_label:<26} {a.days:>4g} day(s)  "
                         f"{a.status:<10} RTW: {a.rtw_meeting_on or ('due' if a.rtw_required else '-')}")
        older = [a for a in rec["all"] if a not in rec["absences"]]
        if older:
            lines += ["", f"Earlier sickness: {len(older)} episode(s)"]
        W.text_window(self.parent, "Sickness record", "\n".join(lines),
                      save_name="sickness_record.txt")

    def cover_lessons(self) -> None:
        r = self._selected("Cover lessons")
        if r is None:
            return
        rows = CV.list_covers(absence_id=r.absence_id)
        lines = [f"Cover for {r.staff_name}, {r.dates_label} ({r.periods_label})", ""]
        lines += [f"{c.date} P{c.period:<3} {c.group_code:<10} {c.status:<10} "
                  f"{c.cover_name or 'unassigned'}" for c in rows] or ["No lessons to cover."]
        W.text_window(self.parent, "Cover lessons", "\n".join(lines))

    def history(self) -> None:
        r = self._selected("History")
        if r is None:
            return
        W.text_window(self.parent, "History", "\n".join(
            f"{h['at']}  {h['actor']:<14} {h['action']:<20} "
            + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
            for h in SA.history(r.absence_id)) or "No changes recorded.")

    def export(self, name: str) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="staff_absence.csv")
        if path:
            self._run("Export", lambda: SA.export_csv(path, actor=self.principal,
                                                      **self._filters(name)),
                      "Exported {out} absence(s).")

    # ── Summary (old) ────────────────────────────────────────────────

    def _build_summary(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Button(bar, text="Refresh", command=self.refresh_summary).pack(side="left")
        self.sum_text = tk.Text(tab, wrap="word", font=("TkFixedFont", 10))
        self.sum_text.pack(fill="both", expand=True)

    def refresh_summary(self) -> None:
        try:
            s = SA.summary(actor=self.principal)
        except _ERRORS as e:
            self._err("Summary", e)
            return
        lines = ["Staff Absence Summary", "=" * 60, ""]
        for label, key in (("Total", "total"), ("Open", "open"),
                           ("Active today", "active_today"),
                           ("Cover outstanding", "cover_outstanding"),
                           ("Critical open", "critical_open"), ("RTW overdue", "rtw_overdue"),
                           ("RTW outstanding", "rtw_outstanding"),
                           ("Return overdue", "return_overdue"),
                           ("Awaiting certificate", "awaiting_cert"),
                           ("Parents pending", "parents_pending"),
                           ("Distinct staff", "distinct_staff"),
                           ("Total days lost", "total_days_lost"),
                           ("Requests waiting", "requests_waiting")):
            lines.append(f"{label:<21}: {s[key]}")
        for head, key, order in (("By type", "by_type", SA.ABSENCE_TYPES),
                                 ("By status", "by_status", SA.STATUSES),
                                 ("By cover source", "by_cover_source", SA.COVER_SOURCES)):
            lines += ["", f"{head}:"] + [f"  {k:<26}: {s[key][k]}" for k in order
                                         if s[key].get(k)]
        self.sum_text.config(state="normal")
        self.sum_text.delete("1.0", "end")
        self.sum_text.insert("1.0", "\n".join(lines))
        self.sum_text.config(state="disabled")

    # ── Requests ─────────────────────────────────────────────────────

    def _build_requests(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.rq_status = tk.StringVar(value=self.state.get("rq_status", "Requested"))
        ttk.Label(bar, text="Status:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.rq_status, state="readonly", width=12,
                          values=["", *SA.REQUEST_STATUSES])
        cb.pack(side="left", padx=(2, 8))
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_requests())
        self._button(bar, "New request…", self.new_request, editor_only=False)
        self._button(bar, "Approve", self.approve)
        self._button(bar, "Decline…", self.decline)
        self._button(bar, "Withdraw", self.withdraw, editor_only=False)
        self._button(bar, "Refresh", self.refresh_requests, editor_only=False)
        self.rq_tree = W.tree(tab, [("id", "Id", 50), ("staff", "Staff", 170),
                                    ("type", "Type", 150), ("dates", "Dates", 170),
                                    ("days", "Days", 50), ("paid", "Paid", 50),
                                    ("status", "Status", 90), ("by", "Decided by", 100),
                                    ("note", "Reason / decision", 260)], height=16,
                              stretch={"note"}, tags=W.STANDARD_TAGS)
        self.rq_rows: dict[str, SA.Request] = {}

    def refresh_requests(self) -> None:
        self.state["rq_status"] = self.rq_status.get()
        try:
            rows = SA.list_requests(actor=self.principal, status=self.rq_status.get() or None)
        except _ERRORS as e:
            self._err("Requests", e)
            return
        self.rq_tree.delete(*self.rq_tree.get_children())
        self.rq_rows = {}
        for q in rows:
            self.rq_rows[str(q.request_id)] = q
            tag = {"Requested": "warn", "Approved": "good", "Declined": "bad"}.get(q.status,
                                                                                 "muted")
            self.rq_tree.insert("", "end", iid=str(q.request_id), tags=(tag,), values=(
                q.request_id, q.staff_name, q.absence_type, q.dates_label, f"{q.days:g}",
                "yes" if q.paid else "no", q.status, q.decided_by or "",
                " / ".join(x for x in (q.reason, q.decision_note) if x)))

    def _request(self, title: str) -> SA.Request | None:
        sel = self.rq_tree.selection()
        if not sel:
            self._info(title, "Select a request first.")
            return None
        return self.rq_rows[sel[0]]

    def new_request(self) -> None:
        choices = SA.staff_choices()
        planned = [t for t in SA.ABSENCE_TYPES if t not in SA.SICKNESS_TYPES]

        def save(v):
            data = {k: x for k, x in v.items() if k != "staff" and x not in ("", None)}
            data.update(_who(v["staff"], choices))
            SA.request_absence(data, actor=self.principal)
            self._refresh_all()
        me = next((_staff_label(p) for p in choices
                   if (p["username"] or "").lower() == self.principal.username.lower()), "")
        W.form_dialog(self.parent, "Request planned absence", [
            ("staff", "For", me, ("edit", [_staff_label(p) for p in choices])),
            ("absence_type", "Type", "Training / CPD", planned),
            ("start_date", "First day", "", None), ("end_date", "Last day (blank = same)", "",
                                                    None),
            ("from_period", "From period (blank = all day)", "", None),
            ("to_period", "To period", "", None), ("paid", "Paid", True, "check"),
            ("reason", "Reason", "", "text")], save,
            note="Nothing is covered until the request is approved.")

    def approve(self) -> None:
        q = self._request("Approve")
        if q is None:
            return

        def save(v):
            _q, rec, lessons = SA.approve_request(q.request_id, note=v["note"],
                                                  actor=self.principal)
            self._refresh_all()
            self._info("Approve", f"Approved - absence #{rec.absence_id} recorded; "
                                  f"{lessons} lesson(s) need cover.")
        W.form_dialog(self.parent, f"Approve request #{q.request_id}",
                      [("note", "Note (optional)", "", "text")], save)

    def decline(self) -> None:
        q = self._request("Decline")
        if q is None:
            return

        def save(v):
            SA.decline_request(q.request_id, note=v["note"], actor=self.principal)
            self._refresh_all()
        W.form_dialog(self.parent, f"Decline request #{q.request_id}",
                      [("note", "Why (required)", "", "text")], save)

    def withdraw(self) -> None:
        q = self._request("Withdraw")
        if q and messagebox.askyesno("Withdraw", f"Withdraw request #{q.request_id}?",
                                     parent=self._top()):
            self._run("Withdraw", lambda: SA.withdraw_request(q.request_id,
                                                              actor=self.principal))

    # ── Sickness (Bradford factor) ───────────────────────────────────

    def _build_sickness(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.sk_only = tk.BooleanVar(value=bool(self.state.get("sk_only")))
        ttk.Checkbutton(bar, text="Trigger points reached only", variable=self.sk_only,
                        command=self.refresh_sickness).pack(side="left", padx=(0, 8))
        self._button(bar, "Sickness record", self._sk_record, editor_only=False)
        self._button(bar, "Trigger settings…", self.trigger_settings)
        self._button(bar, "Refresh", self.refresh_sickness, editor_only=False)
        self.sk_note = tk.StringVar()
        ttk.Label(tab, textvariable=self.sk_note, foreground="#666").pack(anchor="w")
        self.sk_tree = W.tree(tab, [("staff", "Staff", 200), ("dept", "Department", 140),
                                    ("eps", "Episodes", 70), ("days", "Days", 60),
                                    ("bf", "Bradford", 80), ("trig", "Triggers", 360)],
                              height=16, stretch={"trig"}, tags=W.STANDARD_TAGS)
        self.sk_tree.bind("<Double-1>", lambda _e: self._sk_record())

    def refresh_sickness(self) -> None:
        self.state["sk_only"] = self.sk_only.get()
        try:
            rows = SA.sickness_overview(actor=self.principal,
                                        triggered_only=self.sk_only.get())
            st = SA.settings()
        except _ERRORS as e:
            self._err("Sickness", e)
            return
        self.sk_note.set(f"Rolling 12 months. Triggers: {st['trigger_episodes']} episodes, "
                         f"{st['trigger_days']} days or a Bradford score of "
                         f"{st['bradford_trigger']}.")
        self.sk_tree.delete(*self.sk_tree.get_children())
        for i, x in enumerate(rows):
            self.sk_tree.insert("", "end", iid=f"{i}:{x['username'] or x['staff']}",
                                tags=("bad",) if x["triggers"] else (), values=(
                                    x["staff"], x["department"], x["episodes"],
                                    f"{x['days']:g}", f"{x['bradford']:g}",
                                    "; ".join(x["triggers"])))

    def _sk_record(self) -> None:
        sel = self.sk_tree.selection()
        if not sel:
            self._info("Sickness record", "Select a member of staff first.")
            return
        self.sickness_record(sel[0].split(":", 1)[1])

    def trigger_settings(self) -> None:
        st = SA.settings()

        def save(v):
            SA.set_settings(v, actor=self.principal)
            self._refresh_all()
        W.form_dialog(self.parent, "Trigger settings", [
            ("trigger_episodes", "Episodes in 12 months", st["trigger_episodes"], None),
            ("trigger_days", "Days in 12 months", st["trigger_days"], None),
            ("bradford_trigger", "Bradford score", st["bradford_trigger"], None),
            ("rtw_overdue_days", "RTW overdue after (days back)", st["rtw_overdue_days"],
             None)], save)

    # ── Calendar ─────────────────────────────────────────────────────

    def _build_calendar(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        today = _dt.date.today()
        self.cal_month = self.state.get("cal_month") or f"{today:%Y-%m}"
        ttk.Button(bar, text="◀", width=3, command=lambda: self._move_month(-1)).pack(
            side="left")
        self.cal_label = ttk.Label(bar, text="", width=16, anchor="center",
                                   font=("", 11, "bold"))
        self.cal_label.pack(side="left", padx=4)
        ttk.Button(bar, text="▶", width=3, command=lambda: self._move_month(1)).pack(
            side="left")
        ttk.Button(bar, text="This month", command=lambda: self._move_month(0)).pack(
            side="left", padx=8)
        self.cal_tree = W.tree(tab, [("date", "Date", 100), ("day", "Day", 50),
                                     ("n", "Off", 40), ("who", "Who (type)", 600)],
                               height=20, stretch={"who"}, tags=W.STANDARD_TAGS)

    def _move_month(self, step: int) -> None:
        y, m = (int(x) for x in self.cal_month.split("-"))
        if step == 0:
            t = _dt.date.today()
            y, m = t.year, t.month
        else:
            m += step
            y, m = (y + (m - 1) // 12, (m - 1) % 12 + 1)
        self.cal_month = self.state["cal_month"] = f"{y:04d}-{m:02d}"
        self.refresh_calendar()

    def refresh_calendar(self) -> None:
        y, m = (int(x) for x in self.cal_month.split("-"))
        self.cal_label.config(text=f"{_dt.date(y, m, 1):%B %Y}")
        try:
            days = SA.calendar(y, m, actor=self.principal)
        except _ERRORS as e:
            self._err("Calendar", e)
            return
        self.cal_tree.delete(*self.cal_tree.get_children())
        today = _dt.date.today().isoformat()
        for d, rows in days.items():
            day = _dt.date.fromisoformat(d)
            tags = ("muted",) if day.weekday() >= 5 else ("warn",) if d == today else ()
            self.cal_tree.insert("", "end", iid=d, tags=tags, values=(
                d, f"{day:%a}", len(rows) or "",
                ", ".join(f"{r.staff_name} ({r.absence_type}"
                          + (f", {r.periods_label}" if r.partial_day else "") + ")"
                          for r in rows)))

    # ── Reports ──────────────────────────────────────────────────────

    def _build_reports(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.rep_by = tk.StringVar(value=self.state.get("rep_by", "type"))
        today = _dt.date.today()
        self.rep_from = tk.StringVar(value=self.state.get(
            "rep_from", (today - _dt.timedelta(days=364)).isoformat()))
        self.rep_to = tk.StringVar(value=self.state.get("rep_to", today.isoformat()))
        ttk.Label(bar, text="Group by:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.rep_by, state="readonly", width=12,
                          values=list(SA.REPORT_GROUPS))
        cb.pack(side="left", padx=(4, 8))
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_reports())
        for label, var in (("From:", self.rep_from), ("To:", self.rep_to)):
            ttk.Label(bar, text=label).pack(side="left")
            ttk.Entry(bar, textvariable=var, width=11).pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply", command=self.refresh_reports).pack(side="left")
        self._button(bar, "Export CSV…", self._export_period)
        self.rep_tree = W.tree(tab, [("group", "Group", 260), ("n", "Absences", 80),
                                     ("days", "Days", 70), ("sick", "Sickness days", 100),
                                     ("unpaid", "Unpaid days", 90), ("people", "People", 70)],
                               height=16, stretch={"group"})

    def refresh_reports(self) -> None:
        self.state.update(rep_by=self.rep_by.get(), rep_from=self.rep_from.get(),
                          rep_to=self.rep_to.get())
        try:
            rows = SA.report(by=self.rep_by.get(), actor=self.principal,
                             date_from=self.rep_from.get() or None,
                             date_to=self.rep_to.get() or None)
        except _ERRORS as e:
            self._err("Reports", e)
            return
        self.rep_tree.delete(*self.rep_tree.get_children())
        for g in rows:
            self.rep_tree.insert("", "end", values=(g["group"], g["absences"], f"{g['days']:g}",
                                                    f"{g['sickness_days']:g}",
                                                    f"{g['unpaid_days']:g}", g["people"]))

    def _export_period(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="staff_absence.csv")
        if path:
            self._run("Export", lambda: SA.export_csv(
                path, actor=self.principal, date_from=self.rep_from.get() or None,
                date_to=self.rep_to.get() or None), "Exported {out} absence(s).")


def draw_staff_absence(parent: ttk.Frame, *, principal: Principal, state: dict
                       ) -> StaffAbsencePage:
    return StaffAbsencePage(parent, principal=principal, state=state)
