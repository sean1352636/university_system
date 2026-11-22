"""Parent-facing window for the Sixth Form System.

The staff GUI (``interfaces/gui/gui_main``) exposes the whole college:
every student, safeguarding, finance, staff records. A parent must never
land there, so when someone signs in with the ``parent`` role the
launcher opens *this* window instead.

There is one tab per linked child, and everything on it comes from
:func:`~.parent_portal.child_detail` and the ``child_*`` helpers, which
refuse any student the account is not linked to. The actions a parent
can take — report an absence, trip consent, start a bursary
application, book parents' evening slots, ask the office to update
their contact details — all go through the same linked-child checks in
:mod:`.parent_portal`; nothing here edits a record directly.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form import SYSTEM_NAME
from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
    parent_portal as data,
)
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel

logger = logging.getLogger(__name__)

_RISK_COLOURS = {
    "Low": "#27ae60",
    "Medium": "#f39c12",
    "High": "#e67e22",
    "Critical": "#c0392b",
}


class ParentPortalGUI:
    """Read-only dashboard for one signed-in parent."""

    def __init__(self, auth, account, *, on_pay=None) -> None:
        self.auth = auth
        self.on_pay = on_pay
        self.account = account
        self.root = tk.Tk()
        self.root.title(f"{SYSTEM_NAME} — Parent Portal")
        window_sizing.fit(self.root, "1400x900", (1200, 800))

        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self._build_header()
        # Status bar first: it owns ``status_var``, which the body's
        # initial refresh writes the "showing N students" line into.
        self._build_status_bar()
        self._build_body()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Same inactivity cut-off as the staff GUI. A parent portal is
        # more likely to be left open on a shared home computer, so this
        # matters at least as much here.
        try:
            from education_system.systems.sixth_form.interfaces.gui.idle_timeout import (
                IdleTimeoutWatcher,
            )
            self._idle_watcher = IdleTimeoutWatcher(
                self.root, on_timeout=self._idle_logout)
            self._idle_watcher.start()
        except Exception:
            logger.exception("Could not start idle-timeout watcher")
            self._idle_watcher = None

    # ── Chrome ───────────────────────────────────────────────────────

    def _pay(self) -> None:
        """Pay fees, trips or catering top-ups for a linked student. The
        dialog lives in interfaces/, so the launcher passes it in."""
        if self.on_pay is None:
            messagebox.showwarning("Pay", "Online payments aren't available here.",
                                   parent=self.root)
            return
        self.on_pay(self.root, self.account, self.auth)

    def _build_header(self) -> None:
        header = ttk.Frame(self.root, padding=(12, 10, 12, 6))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        left = ttk.Frame(header)
        left.grid(row=0, column=0, sticky="w")
        ttk.Button(left, text="⟳ Refresh", command=self.refresh).pack(side="left")
        ttk.Button(left, text="📧 My Email",
                   command=self.open_email).pack(side="left", padx=(6, 0))
        ttk.Button(left, text="Change Password",
                   command=self._change_password).pack(side="left", padx=(6, 0))
        ttk.Button(left, text="Parents' Evenings",
                   command=self.open_parents_evenings).pack(side="left", padx=(6, 0))
        ttk.Button(left, text="Update My Details",
                   command=self._contact_request_dialog).pack(side="left", padx=(6, 0))
        ttk.Button(left, text="Pay…",
                   command=self._pay).pack(side="left", padx=(6, 0))

        title = ttk.Frame(header)
        title.grid(row=0, column=1)
        ttk.Label(title, text="Parent Portal", font=("", 15, "bold")).pack()
        ttk.Label(title, text=self.account.full_name,
                  foreground="#7f8c8d").pack()

        ttk.Button(header, text="Log Out", command=self._logout).grid(
            row=0, column=2, sticky="e")

    def _build_body(self) -> None:
        self.body = ttk.Frame(self.root, padding=(12, 0, 12, 0))
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)
        self.refresh()

    def _build_status_bar(self) -> None:
        ttk.Separator(self.root, orient="horizontal").grid(
            row=2, column=0, sticky="ew")
        bar = ttk.Frame(self.root, padding=(12, 4))
        bar.grid(row=3, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(bar, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Label(bar, text=f"Signed in as {self.account.username}",
                  foreground="#7f8c8d").grid(row=0, column=1, sticky="e")

    # ── Content ──────────────────────────────────────────────────────

    def refresh(self) -> None:
        for w in self.body.winfo_children():
            w.destroy()

        try:
            children = data.linked_students(self.account.account_id)
        except Exception:
            logger.exception("Could not load linked students for %s",
                             self.account.username)
            self._message("Your information could not be loaded just now. "
                          "Please try again, or contact the college office.")
            self.status_var.set("Could not load your information")
            return

        if not children:
            self._message(
                "No students are linked to your account yet.\n\n"
                "The college office links each parent account to their "
                "child's record. Please contact them if you were expecting "
                "to see someone here.")
            self.status_var.set("No students linked")
            return

        nb = ttk.Notebook(self.body)
        nb.grid(row=0, column=0, sticky="nsew", pady=(8, 8))
        for child in children:
            tab = ttk.Frame(nb, padding=12)
            nb.add(tab, text=child["full_name"])
            self._build_child_tab(tab, child)

        self.status_var.set(
            f"Showing {len(children)} linked "
            f"{'student' if len(children) == 1 else 'students'}")

    def _message(self, text: str) -> None:
        frame = ttk.Frame(self.body, padding=40)
        frame.grid(row=0, column=0)
        ttk.Label(frame, text=text, justify="center", wraplength=520,
                  font=("", 11)).pack()

    def _build_child_tab(self, tab: ttk.Frame, child: dict) -> None:
        try:
            detail = data.child_detail(self.account.account_id, child["student_id"])
        except data.ValidationError as exc:
            ttk.Label(tab, text=str(exc)).pack(anchor="w")
            return
        except Exception:
            logger.exception("Could not build detail for %s", child["student_id"])
            ttk.Label(
                tab,
                text="This student's information could not be loaded just now.",
            ).pack(anchor="w")
            return

        scroll = _ScrollableColumn(tab)
        scroll.pack(fill="both", expand=True)
        inner = scroll.inner

        self._build_summary_tiles(inner, detail, child["relationship"])
        self._build_actions(inner, child)
        self._build_subjects(inner, detail)
        self._build_attendance(inner, detail)
        self._build_behaviour(inner, detail)
        self._build_coursework(inner, detail)
        self._build_ucas_tracker(inner, detail)
        sid = child["student_id"]
        for label, builder in (("Timetable", self._build_timetable),
                               ("Reports", self._build_report_cards),
                               ("Trips", self._build_trips),
                               ("Bursary", self._build_bursaries),
                               ("Absence reports", self._build_absence_reports)):
            try:
                builder(inner, sid)
            except Exception:
                logger.exception("Parent portal %s section failed for %s", label, sid)
                box = ttk.LabelFrame(inner, text=label, padding=8)
                box.pack(fill="x", pady=(0, 12))
                ttk.Label(box, text="Unavailable just now.").pack(anchor="w")

    def _build_summary_tiles(self, parent, detail: dict, relationship: str) -> None:
        head = ttk.Frame(parent)
        head.pack(fill="x", pady=(0, 10))
        ttk.Label(head, text=detail["full_name"], font=("", 14, "bold")).pack(anchor="w")
        ttk.Label(
            head,
            text=f"{relationship} · {detail['student_id']} · {detail['status']}",
            foreground="#7f8c8d",
        ).pack(anchor="w")

        tiles = ttk.Frame(parent)
        tiles.pack(fill="x", pady=(0, 12))

        att = detail.get("attendance_pct")
        window = (detail.get("attendance") or {}).get("days")
        self._tile(tiles, "Attendance",
                   "—" if att is None else f"{att}%",
                   sub=f"last {window} days" if window else "")

        band = detail.get("risk_band") or "—"
        self._tile(tiles, "Overall standing", band,
                   colour=_RISK_COLOURS.get(band))

        beh = detail.get("behaviour_30d") or {}
        self._tile(tiles, "Behaviour (30 days)",
                   f"+{beh.get('positive', 0)} / −{beh.get('negative', 0)}")

        ucas = detail.get("ucas")
        if ucas:
            self._tile(tiles, "UCAS progress",
                       f"{ucas['percent']}%",
                       sub=f"{ucas['complete']} of {ucas['total']} steps")

    @staticmethod
    def _tile(parent, title: str, value: str, *, sub: str = "",
              colour: str | None = None) -> None:
        tile = ttk.LabelFrame(parent, text=title, padding=10)
        tile.pack(side="left", padx=(0, 10))
        label = ttk.Label(tile, text=value, font=("", 18, "bold"))
        if colour:
            label.configure(foreground=colour)
        label.pack(anchor="w")
        if sub:
            ttk.Label(tile, text=sub, foreground="#7f8c8d").pack(anchor="w")

    def _build_subjects(self, parent, detail: dict) -> None:
        subjects = detail.get("subjects") or []
        if not subjects:
            return
        box = ttk.LabelFrame(parent, text="Subjects", padding=8)
        box.pack(fill="x", pady=(0, 12))
        cols = ("subject", "predicted", "target", "mock", "forecast", "on_target")
        tree = ttk.Treeview(box, columns=cols, show="headings",
                            height=min(len(subjects), 8))
        for c, t, w in (("subject", "Subject", 200), ("predicted", "Predicted", 90),
                        ("target", "Target", 80), ("mock", "Latest mock", 100),
                        ("forecast", "Forecast", 90), ("on_target", "On target", 90)):
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor="w" if c == "subject" else "center")
        for s in subjects:
            on_target = ("—" if s.get("on_target") is None
                         else ("Yes" if s["on_target"] else "No"))
            tree.insert("", "end", values=(
                s["subject"], s.get("predicted") or "—", s.get("target") or "—",
                s.get("latest_mock") or "—", s.get("forecast") or "—", on_target))
        tree.pack(fill="x")

    def _build_attendance(self, parent, detail: dict) -> None:
        att = detail.get("attendance") or {}
        box = ttk.LabelFrame(
            parent, text=f"Attendance — last {att.get('days', 30)} days", padding=8)
        box.pack(fill="x", pady=(0, 12))

        counts = att.get("counts") or {}
        if not counts:
            ttk.Label(box, text="No attendance has been recorded in this period."
                      ).pack(anchor="w")
            return

        summary = "   ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        ttk.Label(box, text=summary).pack(anchor="w", pady=(0, 6))

        absences = att.get("absences") or []
        if not absences:
            ttk.Label(box, text="Full attendance — nothing missed.",
                      foreground="#27ae60").pack(anchor="w")
            return

        tree = ttk.Treeview(box, columns=("date", "status", "late"),
                            show="headings", height=min(len(absences), 8))
        for c, t, w in (("date", "Date", 120), ("status", "Status", 120),
                        ("late", "Minutes late", 100)):
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor="w" if c == "date" else "center")
        for a in absences:
            tree.insert("", "end", values=(
                a["date"], a["status"],
                "—" if a.get("minutes_late") in (None, 0) else a["minutes_late"]))
        tree.pack(fill="x")

    def _build_behaviour(self, parent, detail: dict) -> None:
        entries = detail.get("behaviour") or []
        box = ttk.LabelFrame(parent, text="Behaviour record", padding=8)
        box.pack(fill="x", pady=(0, 12))
        if not entries:
            ttk.Label(box, text="Nothing recorded.").pack(anchor="w")
            return

        cols = ("date", "type", "category", "points", "description")
        tree = ttk.Treeview(box, columns=cols, show="headings",
                            height=min(len(entries), 10))
        for c, t, w in (("date", "Date", 100), ("type", "Type", 90),
                        ("category", "Category", 130), ("points", "Points", 60),
                        ("description", "Details", 420)):
            tree.heading(c, text=t)
            tree.column(c, width=w,
                        anchor="w" if c in ("category", "description") else "center")
        tree.tag_configure("Positive", foreground="#27ae60")
        tree.tag_configure("Negative", foreground="#c0392b")
        for e in entries:
            tree.insert("", "end", tags=(e["type"] or "",), values=(
                e["date"], e["type"], e["category"], e.get("points") or 0,
                e.get("description") or ""))
        tree.pack(fill="x")

    def _build_coursework(self, parent, detail: dict) -> None:
        work = detail.get("coursework")
        if not work:
            return
        box = ttk.LabelFrame(parent, text="Coursework", padding=8)
        box.pack(fill="x", pady=(0, 12))

        summary = work.get("summary")
        if summary:
            ttk.Label(box, text=_format_summary(summary)).pack(anchor="w", pady=(0, 6))

        recent = work.get("recent") or []
        if not recent:
            ttk.Label(box, text="Nothing set recently.").pack(anchor="w")
            return

        cols = ("title", "subject", "due", "state", "mark")
        tree = ttk.Treeview(box, columns=cols, show="headings",
                            height=min(len(recent), 10))
        for c, t, w in (("title", "Assignment", 260), ("subject", "Subject", 150),
                        ("due", "Due", 100), ("state", "Status", 120),
                        ("mark", "Mark", 100)):
            tree.heading(c, text=t)
            tree.column(c, width=w,
                        anchor="w" if c in ("title", "subject") else "center")
        for r in recent:
            tree.insert("", "end", values=(
                r.get("title") or "—", r.get("subject") or "—",
                r.get("due_date") or "—", r.get("state") or "—",
                _format_mark(r)))
        tree.pack(fill="x")

    # ── Actions and extra sections ───────────────────────────────────

    #: tracker state -> (label, colour)
    _TRACK_STATES = {"done": ("Done", "#27ae60"), "current": ("Next", "#1a3f8c"),
                     "pending": ("Not yet", "#7f8c8d"),
                     "held": ("Held until results are released", "#b9770e"),
                     "n/a": ("Not applicable", "#aaaaaa")}

    def _build_ucas_tracker(self, parent, detail: dict) -> None:
        """Read-only: where the move to university has got to."""
        steps = detail.get("ucas_tracker")
        if not steps:
            return
        box = ttk.LabelFrame(parent, text="Move to university", padding=8)
        box.pack(fill="x", pady=(0, 12))
        for i, s in enumerate(steps):
            text, colour = self._TRACK_STATES.get(s["state"], (s["state"], "#333"))
            ttk.Label(box, text=s["label"]).grid(row=i, column=0, sticky="w", padx=(0, 12))
            ttk.Label(box, text=text, foreground=colour).grid(
                row=i, column=1, sticky="w", padx=(0, 12))
            ttk.Label(box, text=s.get("date") or "", foreground="#7f8c8d").grid(
                row=i, column=2, sticky="w", padx=(0, 12))
            ttk.Label(box, text=s.get("detail") or "", foreground="#7f8c8d").grid(
                row=i, column=3, sticky="w")

    def _build_actions(self, parent, child: dict) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 12))
        sid = child["student_id"]
        ttk.Button(bar, text="Report an absence…",
                   command=lambda: self._absence_dialog(child)).pack(side="left")
        ttk.Button(bar, text="Start a bursary application…",
                   command=lambda: self._bursary_dialog(child)).pack(side="left", padx=6)
        ttk.Button(bar, text="Book parents' evening…",
                   command=lambda: self.open_parents_evenings(sid)).pack(side="left")

    def _section_tree(self, parent, title: str, cols) -> ttk.Treeview:
        box = ttk.LabelFrame(parent, text=title, padding=8)
        box.pack(fill="x", pady=(0, 12))
        tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings",
                            height=6)
        for c, t, w in cols:
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="x")
        tree._box = box  # type: ignore[attr-defined]
        return tree

    def _build_timetable(self, parent, sid: str) -> None:
        rows = data.child_timetable(self.account.account_id, sid)
        tree = self._section_tree(parent, "Timetable", (
            ("day", "Day", 70), ("period", "Period", 70), ("time", "Time", 110),
            ("subject", "Subject", 220), ("room", "Room", 90), ("teacher", "Teacher", 160)))
        tree.configure(height=min(max(len(rows), 1), 12))
        for r in rows:
            tree.insert("", "end", values=(r["day_name"], f"P{r['period']}",
                                           f"{r['start_time']}–{r['end_time']}",
                                           r["subject"], r["room"] or "—",
                                           r["teacher"] or "—"))

    def _build_report_cards(self, parent, sid: str) -> None:
        cards = data.child_report_cards(self.account.account_id, sid)
        box = ttk.LabelFrame(parent, text="Reports", padding=8)
        box.pack(fill="x", pady=(0, 12))
        if not cards:
            ttk.Label(box, text="No reports have been published yet.").pack(anchor="w")
            return
        for c in cards:
            row = ttk.Frame(box)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=f"{c['period']} — published {c['published_at'] or ''}"
                      ).pack(side="left")
            ttk.Button(row, text="Read", command=lambda cid=c["card_id"]:
                       self._show_report(sid, cid)).pack(side="right")
            ttk.Button(row, text="Save", command=lambda cid=c["card_id"]:
                       self._save_report(sid, cid)).pack(side="right", padx=4)

    def _show_report(self, sid: str, card_id: int) -> None:
        try:
            text = data.child_report_card_text(self.account.account_id, sid, card_id)
        except data.ValidationError as e:
            messagebox.showerror("Report", str(e), parent=self.root)
            return
        win = make_toplevel(self.root)
        win.title("Report")
        window_sizing.fit(win, "1000x800", (800, 600))
        box = tk.Text(win, wrap="word", padx=12, pady=12)
        box.insert("1.0", text)
        box.configure(state="disabled")
        box.pack(fill="both", expand=True)

    def _save_report(self, sid: str, card_id: int) -> None:
        fmt = "pdf" if messagebox.askyesno(
            "Save report", "Save as PDF? (No saves a web page you can print.)",
            parent=self.root) else "html"
        try:
            path = data.child_report_card_file(self.account.account_id, sid, card_id,
                                               fmt=fmt)
        except Exception as e:
            messagebox.showerror("Save report", str(e), parent=self.root)
            return
        messagebox.showinfo("Save report", f"Saved to:\n{path}", parent=self.root)

    def _build_trips(self, parent, sid: str) -> None:
        rows = data.child_trips(self.account.account_id, sid)
        box = ttk.LabelFrame(parent, text="Trips", padding=8)
        box.pack(fill="x", pady=(0, 12))
        if not rows:
            ttk.Label(box, text="Not booked on any trips.").pack(anchor="w")
            return
        for t in rows:
            row = ttk.Frame(box)
            row.pack(fill="x", pady=2)
            consent = "Consent given" if t["consent"] else "CONSENT NEEDED"
            ttk.Label(row, text=f"{t['trip']} — {t['start_date']} · {t['booking_status']}"
                                f" · £{t['paid']:.2f} paid, £{t['balance']:.2f} to pay"
                                f" · {consent}",
                      foreground="#c0392b" if not t["consent"] else "").pack(side="left")
            ttk.Button(row, text="Consent…", command=lambda tr=t:
                       self._consent_dialog(sid, tr)).pack(side="right")

    def _build_bursaries(self, parent, sid: str) -> None:
        apps = data.child_bursaries(self.account.account_id, sid)
        tree = self._section_tree(parent, "Bursary", (
            ("type", "Bursary", 200), ("applied", "Applied", 100),
            ("status", "Status", 130), ("awarded", "Awarded", 100),
            ("paid", "Paid", 100), ("left", "Still to pay", 100)))
        if not apps:
            tree.pack_forget()
            ttk.Label(tree._box, text="No applications. Use “Start a bursary "  # type: ignore[attr-defined]
                      "application…” above if your child needs support.").pack(anchor="w")
            return
        money = lambda v: "—" if v is None else f"£{v:,.2f}"  # noqa: E731
        for a in apps:
            tree.insert("", "end", values=(a["type"], a["applied"], a["status"],
                                           money(a["awarded"]), money(a["paid"]),
                                           money(a["remaining"])))

    def _build_absence_reports(self, parent, sid: str) -> None:
        rows = data.child_absence_reports(self.account.account_id, sid)
        tree = self._section_tree(parent, "Absences you or your child reported", (
            ("dates", "Dates", 200), ("reason", "Reason", 280),
            ("by", "Reported by", 110), ("state", "Status", 120)))
        if not rows:
            tree.pack_forget()
            ttk.Label(tree._box, text="None.").pack(anchor="w")  # type: ignore[attr-defined]
            return
        for r in rows:
            tree.insert("", "end", values=(r["dates"], r["reason"] or "—",
                                           r["reported_by"], r["state"]))

    # Dialogs -------------------------------------------------------------

    def _form(self, title: str, fields, *, note: str = ""):
        """Small modal form; returns {key: value} or None if cancelled."""
        win = tk.Toplevel(self.root)
        win.title(title)
        win.transient(self.root)
        try:
            win.wait_visibility()
            win.grab_set()
        except tk.TclError:
            pass        # stays usable, just not modal
        frm = ttk.Frame(win, padding=14)
        frm.pack(fill="both", expand=True)
        widgets = {}
        row = 0
        if note:
            ttk.Label(frm, text=note, wraplength=440, foreground="#7f8c8d").grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
            row += 1
        for key, label, default, choices in fields:
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="nw", pady=3)
            if choices == "text":
                w = tk.Text(frm, width=44, height=4)
                w.insert("1.0", default or "")
            elif choices:
                w = ttk.Combobox(frm, values=list(choices), state="readonly", width=42)
                w.set(default or (choices[0] if choices else ""))
            else:
                w = ttk.Entry(frm, width=46)
                w.insert(0, default or "")
            w.grid(row=row, column=1, sticky="ew", pady=3)
            widgets[key] = w
            row += 1
        result: dict = {}

        def ok() -> None:
            for k, w in widgets.items():
                result[k] = (w.get("1.0", "end").strip() if isinstance(w, tk.Text)
                             else w.get().strip())
            win.destroy()

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="OK", command=ok).pack(side="left")
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="left", padx=6)
        self.root.wait_window(win)
        return result or None

    def _absence_dialog(self, child: dict) -> None:
        import datetime as _dt
        today = _dt.date.today().isoformat()
        vals = self._form(f"Report an absence — {child['full_name']}", (
            ("from", "First day (YYYY-MM-DD)", today, None),
            ("to", "Last day (YYYY-MM-DD)", today, None),
            ("reason", "Reason", "", None),
            ("message", "Anything else the college should know", "", "text")),
            note="The attendance office will record the absence and may contact "
                 "you if they need more information.")
        if not vals:
            return
        try:
            rep = data.report_child_absence(
                self.account.account_id, child["student_id"], vals["from"],
                date_to=vals["to"] or None, reason=vals["reason"],
                message=vals["message"])
        except Exception as e:      # ValidationError / AccessDenied
            messagebox.showerror("Report an absence", str(e), parent=self.root)
            return
        messagebox.showinfo("Report an absence",
                            f"Thank you — received for {rep.span}.", parent=self.root)
        self.refresh()

    def _consent_dialog(self, sid: str, trip: dict) -> None:
        vals = self._form(f"Consent — {trip['trip']}", (
            ("consent", "Do you give consent?",
             "Yes, I give consent" if not trip["consent"] else "Yes, I give consent",
             ("Yes, I give consent", "No — withdraw consent")),
            ("medical", "Medical needs / medication", trip.get("medical_note") or "", "text"),
            ("dietary", "Dietary needs", trip.get("dietary_note") or "", None),
            ("note", "Note for the trip leader", "", None)),
            note=f"{trip['trip']} to {trip.get('destination') or '—'}, "
                 f"{trip['start_date']}. Medical details are shared only with the "
                 "staff running the trip.")
        if not vals:
            return
        try:
            data.set_trip_consent(
                self.account.account_id, sid, trip["booking_id"],
                consent=vals["consent"].startswith("Yes"),
                medical_note=vals["medical"], dietary_note=vals["dietary"],
                note=vals["note"])
        except Exception as e:
            messagebox.showerror("Trip consent", str(e), parent=self.root)
            return
        messagebox.showinfo("Trip consent", "Saved — thank you.", parent=self.root)
        self.refresh()

    def _bursary_dialog(self, child: dict) -> None:
        types = data.bursary_types()
        vals = self._form(f"Bursary application — {child['full_name']}", (
            ("type", "Type of support", types[0] if types else "", types),
            ("amount", "Amount requested (£, optional)", "", None),
            ("income", "Household income (£ a year, optional)", "", None),
            ("size", "People in the household (optional)", "", None),
            ("reason", "What is the support for?", "", "text")),
            note="The finance office will assess the application and ask for "
                 "evidence (e.g. a benefits letter) if it is needed.")
        if not vals:
            return

        def num(v, cast=float):
            try:
                return cast(v) if v else None
            except ValueError:
                raise data.ValidationError(f"'{v}' is not a number") from None
        try:
            app = data.start_bursary_application(
                self.account.account_id, child["student_id"],
                bursary_type=vals["type"], reason=vals["reason"],
                amount_requested=num(vals["amount"]),
                household_income=num(vals["income"]),
                household_size=num(vals["size"], int))
        except Exception as e:
            messagebox.showerror("Bursary application", str(e), parent=self.root)
            return
        messagebox.showinfo("Bursary application",
                            f"Application #{app.application_id} sent to the finance "
                            "office.", parent=self.root)
        self.refresh()

    def _contact_request_dialog(self) -> None:
        fields = tuple((k, label, "", None)
                       for k, label in data.CONTACT_REQUEST_FIELDS.items())
        vals = self._form("Update my contact details",
                          fields + (("note", "Note for the office", "", "text"),),
                          note="Fill in only what has changed. The college office "
                               "checks each change before updating your record.")
        if not vals:
            return
        note = vals.pop("note", "")
        try:
            data.request_contact_update(self.account.account_id, vals, note=note)
        except data.ValidationError as e:
            messagebox.showerror("Update my details", str(e), parent=self.root)
            return
        pending = [r for r in data.my_contact_requests(self.account.account_id)
                   if r["status"] == data.REQUEST_PENDING]
        messagebox.showinfo("Update my details",
                            f"Sent to the college office ({len(pending)} request(s) "
                            "awaiting review).", parent=self.root)

    # ── Parents' evenings ────────────────────────────────────────────

    def open_parents_evenings(self, student_id: str | None = None) -> None:
        """Book and cancel appointments with your children's teachers."""
        for w in self.body.winfo_children():
            w.destroy()
        wrap = ttk.Frame(self.body)
        wrap.grid(row=0, column=0, sticky="nsew", pady=(8, 8))
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(3, weight=1)
        bar = ttk.Frame(wrap)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(bar, text="← Back to my children", command=self.refresh).pack(side="left")

        children = data.linked_students(self.account.account_id)
        events = data.parents_evening_events()
        if not children or not events:
            ttk.Label(wrap, text=("No parents' evenings are open for booking at the "
                                  "moment." if children else "No students are linked "
                                  "to your account.")).grid(row=1, column=0, sticky="w")
            self._build_my_bookings(wrap, row=3)
            return

        pick = ttk.Frame(wrap)
        pick.grid(row=1, column=0, sticky="ew")
        ev_var, ch_var = tk.StringVar(), tk.StringVar()
        ev_map = {f"{e.name} — {e.event_date} {e.start_time}-{e.end_time}"
                  f"{' · ' + e.location if e.location else ''}": e for e in events}
        ch_map = {c["full_name"]: c["student_id"] for c in children}
        ttk.Label(pick, text="Evening:").pack(side="left")
        ttk.Combobox(pick, textvariable=ev_var, values=list(ev_map), state="readonly",
                     width=55).pack(side="left", padx=4)
        ttk.Label(pick, text="Child:").pack(side="left", padx=(10, 0))
        ttk.Combobox(pick, textvariable=ch_var, values=list(ch_map), state="readonly",
                     width=28).pack(side="left", padx=4)
        ev_var.set(next(iter(ev_map)))
        default_child = next((n for n, s in ch_map.items() if s == student_id),
                             next(iter(ch_map)))
        ch_var.set(default_child)

        cols = ("teacher", "subject", "booked", "free")
        tree = ttk.Treeview(wrap, columns=cols, show="headings", height=8)
        for c, t, w in (("teacher", "Teacher", 200), ("subject", "Subject", 220),
                        ("booked", "Your appointment", 140), ("free", "Free times", 520)):
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor="w")
        tree.grid(row=2, column=0, sticky="nsew", pady=(8, 4))
        actions = ttk.Frame(wrap)
        actions.grid(row=4, column=0, sticky="w", pady=(4, 0))
        options: dict[str, object] = {}

        def load(*_a) -> None:
            tree.delete(*tree.get_children())
            options.clear()
            ev, sid = ev_map.get(ev_var.get()), ch_map.get(ch_var.get())
            if ev is None or sid is None:
                return
            try:
                opts = data.parents_evening_options(self.account.account_id,
                                                    ev.event_id, sid)
            except Exception as e:
                messagebox.showerror("Parents' evening", str(e), parent=self.root)
                return
            for o in opts:
                options[o.staff_id] = o
                tree.insert("", "end", iid=o.staff_id, values=(
                    o.staff_name, o.subject, o.booked_slot or "—",
                    ", ".join(o.free_slots[:24]) or "fully booked"))
            if not opts:
                tree.insert("", "end", values=("No teachers found for this child", "",
                                               "", ""))

        def book() -> None:
            sel = tree.selection()
            o = options.get(sel[0]) if sel else None
            if o is None:
                messagebox.showinfo("Parents' evening", "Choose a teacher first.",
                                    parent=self.root)
                return
            if not o.free_slots:
                messagebox.showinfo("Parents' evening", "No free times left.",
                                    parent=self.root)
                return
            vals = self._form(f"Book {o.staff_name}", (
                ("slot", "Time", o.free_slots[0], tuple(o.free_slots)),
                ("notes", "Anything you would like to discuss (optional)", "", None)))
            if not vals:
                return
            try:
                data.book_parents_evening(self.account.account_id,
                                          ev_map[ev_var.get()].event_id,
                                          ch_map[ch_var.get()], o.staff_id,
                                          vals["slot"], notes=vals["notes"] or None)
            except data.ValidationError as e:
                messagebox.showerror("Parents' evening", str(e), parent=self.root)
                return
            load()
            self._build_my_bookings(wrap, row=3)

        ttk.Button(actions, text="Book a time…", command=book).pack(side="left")
        ev_var.trace_add("write", load)
        ch_var.trace_add("write", load)
        load()
        self._build_my_bookings(wrap, row=3, on_change=load)
        self.status_var.set("Parents' evenings")

    def _build_my_bookings(self, wrap, *, row: int, on_change=None) -> None:
        old = getattr(self, "_bookings_box", None)
        if old is not None:
            try:
                old.destroy()
            except tk.TclError:
                pass
        box = ttk.LabelFrame(wrap, text="My appointments", padding=6)
        box.grid(row=row, column=0, sticky="nsew", pady=(8, 0))
        self._bookings_box = box
        cols = ("event", "date", "time", "child", "teacher", "status")
        tree = ttk.Treeview(box, columns=cols, show="headings", height=6)
        for c, t, w in (("event", "Evening", 220), ("date", "Date", 100),
                        ("time", "Time", 70), ("child", "Child", 170),
                        ("teacher", "Teacher", 170), ("status", "Status", 100)):
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True)
        for r in data.parents_evening_bookings(self.account.account_id):
            tree.insert("", "end", iid=str(r.booking.booking_id), values=(
                r.event_name, r.event_date, r.booking.slot_time, r.student_name,
                r.staff_name, r.booking.status))

        def cancel() -> None:
            sel = tree.selection()
            if not sel or not messagebox.askyesno("Cancel appointment",
                                                  "Cancel this appointment?",
                                                  parent=self.root):
                return
            try:
                data.cancel_parents_evening(self.account.account_id, int(sel[0]))
            except data.ValidationError as e:
                messagebox.showerror("Cancel appointment", str(e), parent=self.root)
                return
            if on_change:
                on_change()
            self._build_my_bookings(wrap, row=row, on_change=on_change)

        ttk.Button(box, text="Cancel selected appointment", command=cancel).pack(
            anchor="w", pady=(4, 0))

    # ── Email portal ─────────────────────────────────────────────────

    def open_email(self) -> None:
        """Show everything the college has emailed this parent."""
        for w in self.body.winfo_children():
            w.destroy()

        if not self.account.email:
            self._message(
                "There is no email address on your account, so there is "
                "nothing to show here.\n\nContact the college office to add "
                "one — they will then be able to email you directly.")
            self.status_var.set("No email address on file")
            return

        try:
            inbox = data.parent_messages(self.account.account_id)
        except Exception:
            logger.exception("Could not load the mailbox for %s",
                             self.account.username)
            self._message("Your email could not be loaded just now. "
                          "Please try again shortly.")
            self.status_var.set("Could not load your email")
            return

        wrap = ttk.Frame(self.body)
        wrap.grid(row=0, column=0, sticky="nsew", pady=(8, 8))
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(2, weight=1)

        bar = ttk.Frame(wrap)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(bar, text="← Back to my children",
                   command=self.refresh).pack(side="left")
        ttk.Label(bar, text=f"Delivered to {self.account.email}",
                  foreground="#7f8c8d").pack(side="left", padx=(10, 0))

        if not inbox:
            ttk.Label(
                wrap,
                text="No email yet.\n\nMessages the college sends you will "
                     "appear here as well as in your own inbox.",
                justify="left").grid(row=1, column=0, sticky="w")
            self.status_var.set("Mailbox empty")
            return

        panes = ttk.Panedwindow(wrap, orient="vertical")
        panes.grid(row=2, column=0, sticky="nsew")
        top = ttk.Frame(panes)
        bottom = ttk.Frame(panes)
        panes.add(top, weight=1)
        panes.add(bottom, weight=2)

        cols = ("sent", "from", "subject", "category")
        tree = ttk.Treeview(top, columns=cols, show="headings", height=8)
        for c, t, w in (("sent", "Sent", 150), ("from", "From", 200),
                        ("subject", "Subject", 420), ("category", "Category", 110)):
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor="w" if c != "category" else "center")
        for m in inbox:
            tree.insert("", "end", iid=str(m["message_id"]), values=(
                (m["sent_at"] or "")[:16], m["from_name"] or m["from_address"] or "—",
                m["subject"], m["category"]))
        tree.pack(fill="both", expand=True)

        reader = tk.Text(bottom, wrap="word", height=14, state="disabled",
                         padx=10, pady=10)
        scroll = ttk.Scrollbar(bottom, orient="vertical", command=reader.yview)
        reader.configure(yscrollcommand=scroll.set)
        reader.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        def show(_evt=None) -> None:
            sel = tree.selection()
            if not sel:
                return
            try:
                msg = data.parent_message(self.account.account_id, int(sel[0]))
            except data.ValidationError as exc:
                text = str(exc)
            except Exception:
                logger.exception("Could not open message %s", sel[0])
                text = "This message could not be opened."
            else:
                sender = msg["from_name"] or msg["from_address"] or "The college"
                text = (f"{msg['subject']}\n"
                        f"From: {sender}\n"
                        f"Sent: {msg['sent_at'] or '—'}\n"
                        f"{'-' * 60}\n\n{msg['body']}")
            reader.configure(state="normal")
            reader.delete("1.0", "end")
            reader.insert("1.0", text)
            reader.configure(state="disabled")

        tree.bind("<<TreeviewSelect>>", show)
        tree.selection_set(str(inbox[0]["message_id"]))
        show()

        self.status_var.set(
            f"{len(inbox)} {'message' if len(inbox) == 1 else 'messages'}")

    # ── Actions ──────────────────────────────────────────────────────

    def _change_password(self) -> None:
        from education_system.platform.delivery.gui.change_password_gui import (
            open_change_password_dialog,
        )
        open_change_password_dialog(self.root, auth=self.auth)

    def _logout(self) -> None:
        if not messagebox.askyesno("Log Out", "Log out of the Parent Portal?",
                                   parent=self.root):
            return
        from education_system import switch
        self._stop_idle_watcher()
        try:
            self.auth.logout()
        except Exception:
            logger.debug("Logout on the shared session failed", exc_info=True)
        switch.request_logout("gui")
        self.root.destroy()

    def _idle_logout(self) -> None:
        logger.info("Idle logout for parent=%s", self.account.username)
        from education_system import switch
        self._stop_idle_watcher()
        try:
            self.auth.logout()
        except Exception:
            logger.debug("Logout on the shared session failed", exc_info=True)
        messagebox.showinfo(
            "Signed Out",
            "You were signed out after a period of inactivity.",
            parent=self.root)
        switch.request_logout("gui")
        self.root.destroy()

    def _stop_idle_watcher(self) -> None:
        watcher = getattr(self, "_idle_watcher", None)
        if watcher is not None:
            try:
                watcher.stop()
            except Exception:
                logger.debug("Could not stop the idle watcher", exc_info=True)
            self._idle_watcher = None

    def _on_close(self) -> None:
        from education_system import switch
        self._stop_idle_watcher()
        switch.request_exit()
        self.root.destroy()


class _ScrollableColumn(ttk.Frame):
    """A vertically scrollable column — a child's tab is taller than the window."""

    def __init__(self, parent) -> None:
        super().__init__(parent)
        canvas = tk.Canvas(self, highlightthickness=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas)

        window = canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.configure(yscrollcommand=bar.set)

        canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")


def _format_summary(summary) -> str:
    if isinstance(summary, dict):
        return "   ·   ".join(
            f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in summary.items())
    return str(summary)


def _format_mark(row: dict) -> str:
    """A mark only appears once it has been released to the student.

    ``parent_view`` already withholds unreleased results, so a missing
    mark here means "not marked yet", not "hidden from you".
    """
    grade, marks, max_marks = row.get("grade"), row.get("marks"), row.get("max_marks")
    if grade:
        return str(grade)
    if marks is None:
        return "—"
    return f"{marks}/{max_marks}" if max_marks else str(marks)


def run(auth, account, *, on_pay=None) -> int:
    """Open the parent window for an already-authenticated parent."""
    gui = ParentPortalGUI(auth, account, on_pay=on_pay)
    gui.root.mainloop()
    return 0
