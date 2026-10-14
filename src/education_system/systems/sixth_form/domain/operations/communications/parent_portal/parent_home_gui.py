"""Parent-facing window for the Sixth Form System.

The staff GUI (``interfaces/gui/gui_main``) exposes the whole college:
every student, safeguarding, finance, staff records. A parent must never
land there, so when someone signs in with the ``parent`` role the
launcher opens *this* window instead.

It is deliberately small and read-only. There is one tab per linked
child, and everything on it comes from
:func:`~.parent_portal.child_detail`, which refuses any student the
account is not linked to.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form import SYSTEM_NAME
from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
    parent_portal as data,
)

logger = logging.getLogger(__name__)

_RISK_COLOURS = {
    "Low": "#27ae60",
    "Medium": "#f39c12",
    "High": "#e67e22",
    "Critical": "#c0392b",
}


class ParentPortalGUI:
    """Read-only dashboard for one signed-in parent."""

    def __init__(self, auth, account) -> None:
        self.auth = auth
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
        self._build_subjects(inner, detail)
        self._build_attendance(inner, detail)
        self._build_behaviour(inner, detail)
        self._build_coursework(inner, detail)

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


def run(auth, account) -> int:
    """Open the parent window for an already-authenticated parent."""
    gui = ParentPortalGUI(auth, account)
    gui.root.mainloop()
    return 0
