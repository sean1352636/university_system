"""The university's University Progression dashboard.

Renders :mod:`handover_board`. The judgement lives there; this file
decides only what is on screen.

The shape mirrors the sixth-form board on purpose — same states-first
sort, same detail pane, same one-line-per-learner bulk report — because
the two are halves of one workflow and staff on either side end up
describing it to each other.

What differs is the verbs. The sixth form *prepares* and *submits*; the
university *accepts*, *requests information* and *completes enrolment*.
That last one never creates a student here: it calls
``admissions_lifecycle.convert_to_student``, which refuses until offer
conditions, right to study and registration are all settled, and this
screen shows the refusal rather than working around it.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.systems.university.domains.admissions.domain.services import (
    handover_board as board_service,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATE_COLOURS: dict[str, str] = {
    board_service.NEEDS_ATTENTION: "#8b0000",
    board_service.AWAITING_REVIEW: "#8a6d00",
    board_service.IN_PROGRESS:     "#1a3f8c",
    board_service.READY_TO_ENROL:  "#14532d",
    board_service.ENROLLED:        "#0d6b2a",
}


def _actor(parent) -> str:
    for attr in ("current_username", "username"):
        value = getattr(parent, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    user = getattr(parent, "current_user", None)
    if isinstance(user, dict) and user.get("username"):
        return str(user["username"])
    return "admissions"


def open_dashboard(parent=None) -> None:
    """Entry point used by the university GUI navigation."""
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title("University Progression — incoming sixth-form handovers")
    # The launcher installs the global geometry clamp, so these are the
    # requested size rather than the final one on a small screen. Matching
    # the university's other windows (see ucas_views) on purpose.
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    _Dashboard(win, actor=_actor(parent))
    return None


class _Dashboard:
    COLUMNS = (
        ("state",   "Status",        130),
        ("name",    "Applicant",     180),
        ("source",  "Sixth form",    170),
        ("course",  "Programme",     190),
        ("offer",   "Offer",         200),
        ("quals",   "Qualifications", 230),
        ("app",     "Application",   90),
    )

    def __init__(self, win: tk.Misc, *, actor: str) -> None:
        self.win = win
        self.actor = actor
        self.board: board_service.Board | None = None
        self._build()
        self.refresh()

    # ── layout ──────────────────────────────────────────────────────

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=10)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Incoming sixth-form handovers",
                  font=("", 15, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text=("Applicants staged from the sixth form's progression "
                  "handover. Completing enrolment runs the full admissions "
                  "conversion — it will refuse while conditions, right to "
                  "study or registration are outstanding, and say why."),
            foreground="#555", wraplength=1300, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        # Action bars first, so the expanding table cannot push them off.
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left")
        self.summary = ttk.Label(bar, text="", foreground="#444")
        self.summary.pack(side="left", padx=(12, 0))
        ttk.Button(bar, text="Enrol all ready",
                   command=self._enrol_all_ready).pack(side="right", padx=4)
        self.hide_done = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Hide enrolled", variable=self.hide_done,
                        command=self._render).pack(side="right", padx=(0, 16))

        footer = ttk.Frame(outer)
        footer.pack(side="bottom", fill="x", pady=(6, 0))
        self.status = ttk.Label(footer, text="", foreground="#666",
                                 wraplength=900, justify="left")
        self.status.pack(side="left")
        actions = ttk.Frame(footer)
        actions.pack(side="right")
        ttk.Button(actions, text="Complete enrolment",
                   command=self._enrol_selected).pack(side="right", padx=4)
        ttk.Button(actions, text="Request information",
                   command=self._request_selected).pack(side="right", padx=4)
        ttk.Button(actions, text="Accept handover",
                   command=self._accept_selected).pack(side="right", padx=4)

        detail_box = ttk.LabelFrame(outer, text="Handover detail",
                                     padding=(8, 6))
        detail_box.pack(side="bottom", fill="x", pady=(6, 0))
        self.detail = tk.Text(detail_box, height=12, wrap="word",
                               font=("Courier", 9), relief="flat")
        self.detail.configure(state="disabled")
        self.detail.pack(fill="both", expand=True)

        table = ttk.Frame(outer)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            table, columns=[c[0] for c in self.COLUMNS],
            show="headings", selectmode="browse", height=14)
        for key, heading, width in self.COLUMNS:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width,
                              anchor="center" if key in ("state", "app")
                                     else "w")
        scroll = ttk.Scrollbar(table, orient="vertical",
                                command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for state, colour in _STATE_COLOURS.items():
            self.tree.tag_configure(state, foreground=colour)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._show_detail())

    # ── data ────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self.status.config(text="Loading…")
        try:
            self.board = board_service.board()
        except Exception as exc:
            logger.exception("Could not build the handover board")
            self.board = board_service.Board(rows=[])
            messagebox.showerror("University Progression",
                                 f"Could not load the board:\n\n{exc}",
                                 parent=self.win)
        self._render()

    def _render(self) -> None:
        self.tree.delete(*self.tree.get_children())
        if self.board is None:
            return
        hide = self.hide_done.get()
        shown = 0
        for row in self.board.rows:
            if hide and row.state == board_service.ENROLLED:
                continue
            shown += 1
            self.tree.insert(
                "", "end", iid=str(row.application_id),
                values=(row.state, row.full_name, row.source_sixth_form or "—",
                        row.programme or "—", row.offer_status or "—",
                        row.qualification_status or "—", row.application_id),
                tags=(row.state,))
        hidden = len(self.board.rows) - shown
        self.summary.config(
            text=self.board.summary_line()
                 + (f"  ·  {hidden} enrolled hidden" if hidden else ""))
        self._show_detail()
        self.status.config(text="")

    def _selected(self) -> board_service.Row | None:
        selection = self.tree.selection()
        if not selection or self.board is None:
            return None
        try:
            return self.board.get(int(selection[0]))
        except (TypeError, ValueError):
            return None

    def _show_detail(self) -> None:
        row = self._selected()
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        if row is None:
            self.detail.insert("end", "Select an applicant.")
            self.detail.configure(state="disabled")
            return

        self.detail.insert(
            "end",
            f"{row.full_name}    application #{row.application_id}    "
            f"{row.state} ({row.status or 'no status'})\n"
            f"Sixth form  : {row.source_sixth_form or '—'}"
            f"   (their id: {row.sixth_form_student_id or '—'})\n"
            f"UCAS        : {row.ucas_id or '—'}\n"
            f"Programme   : {row.programme or '—'}  "
            f"entry {row.entry_year or '—'}\n"
            f"Journey     : {row.journey_id or '—'}\n")
        if row.converted_student_id:
            self.detail.insert(
                "end", f"Enrolled as : {row.converted_student_id}\n")
        self.detail.insert("end", "\n")

        for warning in row.warnings:
            self.detail.insert("end", f"!!  {warning}\n")
        if row.warnings:
            self.detail.insert("end", "\n")

        self.detail.insert(
            "end",
            f"Handover fields received ({len(row.included)}): "
            + (", ".join(row.included) or "none") + "\n"
            f"Not received ({len(row.withheld)}): "
            + (", ".join(row.withheld) or "none") + "\n")
        if row.withheld:
            self.detail.insert(
                "end",
                "    A field can be absent because the sixth form withheld "
                "it for want of consent or because they simply do not hold "
                "it — the payload does not say which. Request information "
                "to put the question on the application's checklist.\n")
        self.detail.insert("end", "\n")

        if row.outstanding:
            self.detail.insert("end", "Outstanding before enrolment:\n")
            for item in row.outstanding:
                self.detail.insert("end", f"    • {item}\n")
        else:
            self.detail.insert("end", "No outstanding requirements or "
                                       "conditions recorded.\n")
        self.detail.configure(state="disabled")

    # ── actions ─────────────────────────────────────────────────────

    def _accept_selected(self) -> None:
        row = self._selected()
        if row is None:
            self.status.config(text="Select an applicant first.")
            return
        result = board_service.accept(row.application_id, actor_id=self.actor)
        (messagebox.showinfo if result.ok else messagebox.showwarning)(
            "Accept handover", f"{row.full_name}: {result.detail}",
            parent=self.win)
        self.refresh()

    def _request_selected(self) -> None:
        row = self._selected()
        if row is None:
            self.status.config(text="Select an applicant first.")
            return
        if not row.withheld:
            messagebox.showinfo(
                "Request information",
                f"Every declared handover field arrived for "
                f"{row.full_name} — there is nothing to chase.",
                parent=self.win)
            return
        _RequestDialog(self.win, row, actor=self.actor, on_done=self.refresh)

    def _enrol_selected(self) -> None:
        row = self._selected()
        if row is None:
            self.status.config(text="Select an applicant first.")
            return
        if row.converted_student_id:
            messagebox.showinfo(
                "Complete enrolment",
                f"{row.full_name} is already university student "
                f"{row.converted_student_id}.", parent=self.win)
            return
        blockers = board_service.enrolment_blockers(row.application_id)
        if blockers:
            messagebox.showwarning(
                "Complete enrolment",
                f"{row.full_name} cannot be enrolled yet:\n\n"
                + "\n".join(f"  • {b}" for b in blockers)
                + "\n\nThese are the admissions gates — settle them on the "
                  "application, then try again.",
                parent=self.win)
            return
        if not messagebox.askyesno(
            "Complete enrolment",
            f"Convert {row.full_name} into a university student?\n\n"
            "This creates the student record, registration and programme "
            "registration in one transaction, links their cross-system "
            "journey, and copies their sixth-form health record if consent "
            "allows.",
            parent=self.win,
        ):
            return
        result = board_service.complete_enrolment(row.application_id,
                                                   actor_id=self.actor)
        (messagebox.showinfo if result.ok else messagebox.showwarning)(
            "Complete enrolment", f"{row.full_name}: {result.detail}",
            parent=self.win)
        self.refresh()

    def _enrol_all_ready(self) -> None:
        if self.board is None:
            return
        ready = self.board.enrollable
        if not ready:
            messagebox.showinfo(
                "Enrol all ready",
                "No applicant has cleared every admissions gate. Applicants "
                "still in progress are left out of a bulk run on purpose — "
                "enrol those individually so their blockers are seen.",
                parent=self.win)
            return
        if not messagebox.askyesno(
            "Enrol all ready",
            f"Convert {len(ready)} applicant(s) who have cleared every "
            f"gate?\n\nEach conversion is independent — one failure does "
            f"not stop the rest.",
            parent=self.win,
        ):
            return
        results = board_service.complete_enrolment_many(
            [r.application_id for r in ready], actor_id=self.actor)
        by_id = {r.application_id: r for r in ready}
        ok = [r for r in results if r.ok]
        bad = [r for r in results if not r.ok]
        lines = [f"Enrolled : {len(ok)}", f"Refused  : {len(bad)}", ""]
        if bad:
            lines.append("Refused:")
            lines += [
                f"  {by_id[r.application_id].full_name if r.application_id in by_id else r.application_id}: {r.detail}"
                for r in bad[:25]]
            if len(bad) > 25:
                lines.append(f"  …plus {len(bad) - 25} more")
            lines.append("")
        if ok:
            lines.append("Enrolled:")
            lines += [
                f"  {by_id[r.application_id].full_name if r.application_id in by_id else r.application_id}: {r.detail}"
                for r in ok[:25]]
        (messagebox.showwarning if bad else messagebox.showinfo)(
            "Enrol all ready", "\n".join(lines), parent=self.win)
        self.refresh()


class _RequestDialog:
    """Pick which missing handover fields to raise as requirements."""

    def __init__(self, master: tk.Misc, row: board_service.Row, *,
                 actor: str, on_done) -> None:
        self.row = row
        self.actor = actor
        self.on_done = on_done
        self.win = tk.Toplevel(master)
        self.win.title(f"Request information — {row.full_name}")
        self.win.transient(master)
        self.win.after_idle(self.win.grab_set)

        frm = ttk.Frame(self.win, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(
            frm,
            text=("These declared handover fields did not arrive. Raising "
                  "one adds a required item to the application's checklist, "
                  "which the enrolment gate consults — so the chase holds "
                  "the door closed rather than sitting in an inbox."),
            wraplength=460, justify="left", foreground="#555",
        ).pack(anchor="w", pady=(0, 8))

        self.vars: dict[str, tk.BooleanVar] = {}
        for key in row.withheld:
            var = tk.BooleanVar(value=True)
            self.vars[key] = var
            ttk.Checkbutton(frm, text=key.replace("_", " "),
                            variable=var).pack(anchor="w")

        bar = ttk.Frame(frm)
        bar.pack(anchor="e", pady=(12, 0))
        ttk.Button(bar, text="Request", command=self._submit).pack(
            side="left", padx=(0, 6))
        ttk.Button(bar, text="Cancel", command=self.win.destroy).pack(
            side="left")

    def _submit(self) -> None:
        wanted = [k for k, v in self.vars.items() if v.get()]
        result = board_service.request_information(
            self.row.application_id, wanted, actor_id=self.actor)
        (messagebox.showinfo if result.ok else messagebox.showwarning)(
            "Request information", result.detail, parent=self.win)
        self.win.destroy()
        self.on_done()


__all__ = ["open_dashboard"]
