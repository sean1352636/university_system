"""The sixth form's University Progression dashboard.

Renders :mod:`university_progression`. All the judgement lives in that
module; this file decides only what is on screen and in what order.

Three things drive the layout:

* **Trouble sorts to the top.** The board's own state order puts stranded
  transfers first, then blocked, then the ones needing a look. On results
  day the useful screen is not an alphabetical roll.
* **Prepare before Submit.** Submitting is irreversible from here — it
  closes the sixth-form enrolment — so the dry run sits next to it and
  shows exactly which fields would cross before anything does.
* **Bulk without blindness.** "Submit all ready" is the reason the board
  exists, but it reports one line per learner, successes and failures
  alike, rather than a single count.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.systems.sixth_form.domain.progression.university import (
    board as board_service,
)
from education_system.systems.sixth_form.domain.progression.university_handover import (
    HANDOVER_CONSENT_PURPOSE as _CONSENT_PURPOSE,
)

logger = logging.getLogger(__name__)

#: Row colours, keyed by board state. Muted rather than traffic-light:
#: most of this table is fine most of the time, and a screen that shouts
#: at every row shouts at none of them.
_STATE_COLOURS: dict[str, str] = {
    board_service.STRANDED:  "#8c0d0d",
    board_service.BLOCKED:   "#8b0000",
    board_service.ATTENTION: "#8a6d00",
    board_service.READY:     "#14532d",
    board_service.SUBMITTED: "#1a3f8c",
    board_service.ENROLLED:  "#0d6b2a",
    board_service.DEPARTED:  "#666666",
}


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


#: What to do about each failing check, keyed on ``Check.key``.
#:
#: The board was already precise about *what* is missing and silent about
#: where it is fixed — and for most of these that is a different screen,
#: in one case a different system. "Confirmed destination" is a true
#: description of the problem and a useless instruction; "set the Firm
#: reply, which the university records" is the same fact said to somebody
#: who has to act on it.
#:
#: ``action`` names a method on the dashboard, or is ``None`` where the
#: fix is genuinely somewhere this window cannot go.
_REMEDIES: dict[str, tuple[str, str | None]] = {
    "identity": (
        "Fill in the learner's name and date of birth on their student "
        "record.",
        None),
    "destination": (
        "The learner needs a Firm reply on a UCAS choice. Firm / "
        "Insurance / Declined is recorded by the university that made "
        "the offer, in its own UCAS Management screen — not here.",
        "_open_application"),
    "offer": (
        "Same cause as the destination check: no Firm reply on any "
        "choice. A choice must hold an offer before it can be replied "
        "to.",
        "_open_application"),
    "conditions": (
        "Advisory. The offer's conditions have not been met or recorded "
        "yet; the handover can still go.",
        "_open_application"),
    "results": (
        "Advisory. No released exam results are on record — enter them "
        "under Assessment & Grades → Results Day when they exist.",
        None),
    "consent": (
        "Record a GDPR consent for this learner with the purpose "
        f"'{_CONSENT_PURPOSE}', under System → GDPR. Without it the "
        "handover carries the routine fields only.",
        "_open_gdpr"),
    "not_transferred": (
        "This learner has already been handed over. Re-submitting is "
        "only for a stranded transfer.",
        None),
    "not_already_here": (
        "The learner already has a university record on their journey, "
        "so there is nothing to create.",
        None),
}


def _actor(gui) -> str:
    """Who is doing this, for the audit trail on the other side."""
    for attr in ("current_username", "username"):
        value = getattr(gui, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    user = getattr(gui, "current_user", None)
    if isinstance(user, dict) and user.get("username"):
        return str(user["username"])
    return "sixth-form progression board"


def open_dashboard(gui) -> None:
    """Entry point used by the sixth-form GUI navigation."""
    frame = _clear(gui)
    ttk.Label(frame, text="University Progression",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 2))
    ttk.Label(
        frame,
        text=("Everyone on the way to university — the Year 13 cohort, "
              "anyone holding a UCAS application, and any leaver whose "
              "handover never landed — and what is stopping them. "
              "Submitting hands the learner over and closes their "
              "sixth-form enrolment; use Prepare first to see exactly "
              "what would cross."),
        foreground="#555", wraplength=900, justify="left",
    ).pack(anchor="w", pady=(0, 8))

    _Dashboard(gui, frame)


class _Dashboard:
    COLUMNS = (
        ("state",       "Status",        130),
        ("student_id",  "Student ID",    100),
        ("name",        "Name",          190),
        ("destination", "Destination",   170),
        ("course",      "Course",        200),
        ("outstanding", "Outstanding",   260),
    )

    def __init__(self, gui, parent: ttk.Frame) -> None:
        self.gui = gui
        self.parent = parent
        self.board: board_service.Board | None = None
        self._build()
        self.refresh()

    # ── layout ──────────────────────────────────────────────────────

    def _build(self) -> None:
        # Action bars are packed before the table so the expanding tree
        # cannot squeeze them off the bottom of a short window.
        self.bar = ttk.Frame(self.parent)
        self.bar.pack(fill="x", pady=(0, 6))
        ttk.Button(self.bar, text="Refresh",
                   command=self.refresh).pack(side="left")
        ttk.Button(
            self.bar, text="UCAS-linked workflow",
            command=self._open_shared_workflow,
        ).pack(side="left", padx=(6, 0))
        self.summary = ttk.Label(self.bar, text="", foreground="#444")
        self.summary.pack(side="left", padx=(12, 0))

        bulk = ttk.Frame(self.bar)
        bulk.pack(side="right")
        ttk.Button(bulk, text="Retry stranded",
                   command=self._retry_stranded).pack(side="right", padx=4)
        ttk.Button(bulk, text="Submit all ready",
                   command=self._submit_all_ready).pack(side="right", padx=4)

        self.only_actionable = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.bar, text="Hide finished",
            variable=self.only_actionable,
            command=self._render,
        ).pack(side="right", padx=(0, 16))

        self.footer = ttk.Frame(self.parent)
        self.footer.pack(side="bottom", fill="x", pady=(6, 0))
        self.status = ttk.Label(self.footer, text="", foreground="#666",
                                 wraplength=880, justify="left")
        self.status.pack(side="left")
        actions = ttk.Frame(self.footer)
        actions.pack(side="right")
        ttk.Button(actions, text="Submit handover",
                   command=self._submit_selected).pack(side="right", padx=4)
        ttk.Button(actions, text="Prepare handover",
                   command=self._prepare_selected).pack(side="right", padx=4)

        detail_box = ttk.LabelFrame(self.parent, text="Selected learner",
                                     padding=(8, 6))
        detail_box.pack(side="bottom", fill="x", pady=(6, 0))
        self.detail = tk.Text(detail_box, height=9, wrap="word",
                               font=("Courier", 9), relief="flat")
        self.detail.configure(state="disabled")
        self.detail.pack(fill="both", expand=True)
        # Buttons for the blockers this window can act on. Populated per
        # selection by ``_render_fix_bar`` — empty for a learner whose
        # only failures are fixed elsewhere.
        self.fix_bar = ttk.Frame(detail_box)
        self.fix_bar.pack(fill="x", pady=(4, 0))

        table = ttk.Frame(self.parent)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            table, columns=[c[0] for c in self.COLUMNS],
            show="headings", selectmode="browse", height=14)
        for key, heading, width in self.COLUMNS:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width,
                              anchor="w" if key != "state" else "center")
        scroll = ttk.Scrollbar(table, orient="vertical",
                                command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for state, colour in _STATE_COLOURS.items():
            self.tree.tag_configure(state, foreground=colour)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._show_detail())
        self.tree.bind("<Double-Button-1>",
                       lambda _e: self._prepare_selected())

    def _open_shared_workflow(self) -> None:
        from education_system.platform.cross_system.university_applications_gui import render
        render(self.gui, "sixth_form")

    # ── data ────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._set_status("Loading…")
        try:
            self.board = board_service.board()
        except Exception as exc:
            logger.exception("Could not build the progression board")
            self.board = board_service.Board(rows=[])
            messagebox.showerror("University Progression",
                                 f"Could not load the board:\n\n{exc}")
        self._render()

    def _render(self) -> None:
        self.tree.delete(*self.tree.get_children())
        if self.board is None:
            return
        hide_done = self.only_actionable.get()
        shown = 0
        for row in self.board.rows:
            if hide_done and row.is_done:
                continue
            shown += 1
            self.tree.insert(
                "", "end", iid=row.student_id,
                values=(row.state, row.student_id, row.full_name,
                        row.destination or "—", row.course or "—",
                        ", ".join(row.outstanding) or "—"),
                tags=(row.state,))
        hidden = len(self.board.rows) - shown
        self.summary.config(
            text=self.board.summary_line()
                 + (f"  ·  {hidden} finished hidden" if hidden else ""))
        self._show_detail()
        self._set_status("")

    def _selected(self) -> board_service.Row | None:
        selection = self.tree.selection()
        if not selection or self.board is None:
            return None
        return self.board.get(selection[0])

    def _show_detail(self) -> None:
        row = self._selected()
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        if row is None:
            self.detail.insert("end", "Select a learner.")
        else:
            self.detail.insert(
                "end",
                f"{row.full_name} ({row.student_id})    {row.state}\n"
                f"Destination : {row.destination or '—'}\n"
                f"Course      : {row.course or '—'}\n"
                f"Journey     : {row.journey_id or 'not yet anchored'}\n")
            if row.university_student_id:
                self.detail.insert(
                    "end",
                    f"University  : student {row.university_student_id}\n")
            if row.transferred_at:
                self.detail.insert(
                    "end", f"Handed over : {row.transferred_at}\n")
            self.detail.insert("end", "\n")
            for warning in row.warnings:
                self.detail.insert("end", f"!!  {warning}\n")
            if row.readiness is not None:
                for check in row.readiness.checks:
                    mark = ("OK  " if check.passed
                            else ("✗   " if check.blocking else "!   "))
                    self.detail.insert(
                        "end", f"{mark}{check.label}: {check.detail}\n")
                    # The remedy goes under the failure it belongs to,
                    # rather than in a block at the bottom that has to
                    # name each check again to be read.
                    if not check.passed:
                        remedy = _REMEDIES.get(check.key)
                        if remedy:
                            self.detail.insert(
                                "end", f"      → {remedy[0]}\n")
        self.detail.configure(state="disabled")
        self._render_fix_bar(row)

    def _render_fix_bar(self, row) -> None:
        """Buttons for the failures this window can actually do something
        about. Rebuilt per selection: which ones apply is a property of
        the learner, not of the screen."""
        for widget in self.fix_bar.winfo_children():
            widget.destroy()
        if row is None or row.readiness is None:
            return

        seen: set[str] = set()
        for check in row.readiness.checks:
            if check.passed:
                continue
            remedy = _REMEDIES.get(check.key)
            if not remedy or remedy[1] is None:
                continue
            action = remedy[1]
            # 'destination' and 'offer' fail together and share a fix;
            # two identical buttons would suggest two different jobs.
            if action in seen:
                continue
            seen.add(action)
            label = {"_open_application": "Open the application",
                     "_open_gdpr": "Record handover consent"}.get(
                action, action)
            ttk.Button(self.fix_bar, text=label,
                       command=getattr(self, action)).pack(side="left",
                                                            padx=(0, 6))

    def _open_application(self) -> None:
        """The learner's UCAS application, in a window of its own.

        A dialog rather than a page. The board is embedded in the
        Overview tab of the University & UCAS window, and the full-page
        application view clears the content frame — which would destroy
        the notebook this button was clicked in, and leave the Back
        button pointing at a screen that no longer exists.
        """
        row = self._selected()
        if row is None:
            return
        try:
            from education_system.systems.sixth_form.domain.progression.university import (
                ucas as ucas_data,
            )
            from education_system.systems.sixth_form.domain.progression.university.views import (
                ucas as ucas_views,
            )
            application = ucas_data.get_application_for_student(
                row.student_id)
        except Exception as exc:
            logger.exception("Could not open the UCAS application")
            messagebox.showerror("University Progression",
                                 f"Could not open it: {exc}")
            return
        if application is None:
            messagebox.showinfo(
                "University Progression",
                f"{row.student_id} has no UCAS application, so there is "
                "no choice to reply to.")
            return

        win = tk.Toplevel(self.gui.root)
        win.title(f"UCAS application #{application.application_id} — "
                  f"{row.full_name}")
        win.transient(self.gui.root)
        body = ttk.Frame(win, padding=12)
        body.pack(fill="both", expand=True)

        def render() -> None:
            for widget in body.winfo_children():
                widget.destroy()
            ucas_views._render_application_detail(
                self.gui, body, application.application_id,
                on_changed=render)
            # The board's verdict is derived from this application, so a
            # change made in here can clear the very blocker that opened
            # it. Refreshing on close would be too late to see.
            ttk.Button(body, text="Close",
                       command=lambda: (win.destroy(), self.refresh())
                       ).pack(anchor="w", pady=(12, 0))

        render()

    def _open_gdpr(self) -> None:
        """The consent register, where the handover consent is recorded."""
        try:
            from education_system.systems.sixth_form.domain.governance.gdpr import (
                gdpr_views,
            )
        except Exception as exc:
            logger.exception("Could not load the GDPR screen")
            messagebox.showerror("University Progression",
                                 f"Could not open the GDPR screen: {exc}")
            return
        messagebox.showinfo(
            "Handover consent",
            "Record a consent for this learner with the purpose "
            f"'{_CONSENT_PURPOSE}'.\n\nIt is in the purpose dropdown; "
            "the exact value is what the eligibility check looks for.")
        gdpr_views.open_gdpr_window(self.gui)

    def _set_status(self, text: str) -> None:
        self.status.config(text=text)
        status_var = getattr(self.gui, "status_var", None)
        if status_var is not None and text:
            status_var.set(text)

    # ── actions ─────────────────────────────────────────────────────

    def _prepare_selected(self) -> None:
        row = self._selected()
        if row is None:
            self._set_status("Select a learner first.")
            return
        try:
            prepared = board_service.prepare(row.student_id)
        except Exception as exc:
            logger.exception("Prepare failed for %s", row.student_id)
            messagebox.showerror("Prepare handover", f"Failed:\n\n{exc}")
            return
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert(
            "end",
            f"DRY RUN — nothing has been sent.\n"
            f"{row.full_name} ({row.student_id})\n\n"
            + prepared.describe())
        self.detail.configure(state="disabled")
        self._set_status(
            "Dry run complete — this is what Submit would send."
            if prepared.ok else
            "Dry run complete — this learner cannot be submitted yet.")

    def _submit_selected(self) -> None:
        row = self._selected()
        if row is None:
            self._set_status("Select a learner first.")
            return
        if row.is_done and row.state != board_service.STRANDED:
            messagebox.showinfo(
                "Submit handover",
                f"{row.full_name} has already been handed over "
                f"({row.state.lower()}).")
            return
        if not messagebox.askyesno(
            "Submit handover",
            f"Hand {row.full_name} over to the university?\n\n"
            "This closes their sixth-form enrolment and removes their "
            "sixth-form access. Their sign-in account stays active — it is "
            "the same person.\n\n"
            + ("Outstanding: " + ", ".join(row.outstanding) + "\n\n"
               if row.outstanding else "")
            + "Continue?",
        ):
            return
        result = board_service.submit(row.student_id, moved_by=_actor(self.gui))
        if result.ok:
            messagebox.showinfo("Submit handover",
                                f"{row.full_name}: {result.detail}")
        else:
            messagebox.showwarning("Submit handover",
                                   f"{row.full_name}: {result.detail}")
        self.refresh()

    def _submit_all_ready(self) -> None:
        if self.board is None:
            return
        ready = [r for r in self.board.rows if r.state == board_service.READY]
        if not ready:
            messagebox.showinfo(
                "Submit all ready",
                "Nothing is fully ready. Learners with outstanding items are "
                "left out of a bulk run on purpose — submit those "
                "individually so their gaps are seen.")
            return
        if not messagebox.askyesno(
            "Submit all ready",
            f"Hand over {len(ready)} learner(s) whose checks all pass?\n\n"
            "Each one's sixth-form enrolment is closed. Learners needing "
            "attention are not included.",
        ):
            return
        results = board_service.submit_many(
            [r.student_id for r in ready], moved_by=_actor(self.gui))
        self._report_bulk("Submit all ready", results)

    def _retry_stranded(self) -> None:
        if self.board is None:
            return
        stranded = self.board.stranded
        if not stranded:
            messagebox.showinfo(
                "Retry stranded",
                "No stranded transfers. Every learner marked Left has a "
                "completed handover.")
            return
        if not messagebox.askyesno(
            "Retry stranded",
            f"{len(stranded)} learner(s) were marked Left but never reached "
            f"the university.\n\nRetry their handovers? This is safe to "
            f"repeat — an announcement that did land is a no-op.",
        ):
            return
        results = board_service.retry_stranded(moved_by=_actor(self.gui))
        self._report_bulk("Retry stranded", results)

    def _report_bulk(self, title: str, results) -> None:
        """One line per learner. A bulk run that reports only a count is
        how a failed handover goes unnoticed until the learner rings up."""
        ok = [r for r in results if r.ok]
        bad = [r for r in results if not r.ok]
        lines = [f"Succeeded : {len(ok)}", f"Failed    : {len(bad)}", ""]
        if bad:
            lines.append("Failures:")
            lines += [f"  {r.student_id}: {r.detail}" for r in bad[:25]]
            if len(bad) > 25:
                lines.append(f"  …plus {len(bad) - 25} more")
            lines.append("")
        if ok:
            lines.append("Handed over:")
            lines += [f"  {r.student_id}: {r.detail}" for r in ok[:25]]
            if len(ok) > 25:
                lines.append(f"  …plus {len(ok) - 25} more")
        body = "\n".join(lines)
        (messagebox.showwarning if bad else messagebox.showinfo)(title, body)
        self.refresh()


__all__ = ["open_dashboard"]
