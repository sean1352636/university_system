"""Tkinter GUI for university-side UCAS management.

Single window with two tabs:

* **Applicants** — filterable table of every sixth-form UCAS choice
  that names this university. Filter by decision status / application
  status / cycle year, plus a search box across name / id / course.
  Double-click opens the applicant-detail dialog.
* **Summary** — counts by decision, application status, course, cycle
  year.

The applicant-detail dialog shows the student's personal statement,
their full list of choices (with *our* choice flagged), and a
decision panel that writes back to the sixth-form ``ucas_choices``
row via the data layer.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from education_system.post_18.university_system.modules.domain.admissions.ucas import (
    ucas as data,
)
from education_system.post_18.university_system.modules.domain.admissions.ucas.ucas import (
    APP_STATUSES,
    Applicant,
    DECIDABLE,
    DECISION_STATUSES,
    UcasError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_DECISION_TAGS: dict[str, tuple[str, str]] = {
    "Awaiting":            ("#fff7e6", "#7a5800"),
    "Conditional Offer":   ("#e6f0ff", "#1a3f8c"),
    "Unconditional Offer": ("#e6f7e6", "#0d6b2a"),
    "Rejected":            ("#ffd1d1", "#8c0d0d"),
    "Withdrawn":           ("#eeeeee", "#666666"),
}


def open_directory(parent=None) -> None:
    """Entry point used by the uni GUI main menu."""
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"UCAS Management — {data.UNIVERSITY_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    applicants_tab = ApplicantsTab(nb, win)
    PipelineTab(nb, win, applicants_tab)
    SummaryTab(nb, applicants_tab)


# ─────────────────────────────────────────────────────────────────
# Applicants tab
# ─────────────────────────────────────────────────────────────────

class ApplicantsTab:
    def __init__(self, nb: ttk.Notebook, root: tk.Misc) -> None:
        self.root = root
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Applicants")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Decision:").pack(side="left")
        self.f_dec = ttk.Combobox(
            bar, values=("",) + DECISION_STATUSES,
            state="readonly", width=20)
        self.f_dec.current(0)
        self.f_dec.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="App status:").pack(side="left")
        self.f_app = ttk.Combobox(
            bar, values=("",) + APP_STATUSES,
            state="readonly", width=12)
        self.f_app.current(0)
        self.f_app.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Cycle:").pack(side="left")
        self.f_cycle = ttk.Entry(bar, width=6)
        self.f_cycle.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.f_search = ttk.Entry(bar, width=22)
        self.f_search.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="Awaiting only",
                    command=self._filter_awaiting).pack(
            side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("student", "name", "cycle", "course",
                "app_status", "decision", "terms", "submitted")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"student": 90, "name": 180, "cycle": 60,
                   "course": 240, "app_status": 100,
                   "decision": 160, "terms": 220, "submitted": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("cycle",
                                                  "app_status")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for decision, (bg, fg) in _DECISION_TAGS.items():
            self.tree.tag_configure(decision, background=bg,
                                       foreground=fg)
        self.tree.bind("<Double-Button-1>", lambda _e: self._open())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Decide", self._open),
                ("Refresh",        self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_dec.current(0)
        self.f_app.current(0)
        self.f_cycle.delete(0, "end")
        self.f_search.delete(0, "end")
        self.refresh()

    def _filter_awaiting(self) -> None:
        self.f_dec.set("Awaiting")
        self.refresh()

    def _filters(self) -> dict[str, Any]:
        f: dict[str, Any] = {}
        if self.f_dec.get():
            f["decision_status"] = self.f_dec.get()
        if self.f_app.get():
            f["app_status"] = self.f_app.get()
        cy = self.f_cycle.get().strip()
        if cy:
            try:
                f["cycle_year"] = int(cy)
            except ValueError:
                messagebox.showwarning(
                    "UCAS", "Cycle year must be a number.")
                self.f_cycle.delete(0, "end")
        if self.f_search.get().strip():
            f["search"] = self.f_search.get().strip()
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_applicants(**self._filters())
        except UcasError as e:
            messagebox.showwarning("UCAS", str(e))
            return
        except Exception as e:
            logger.exception("Applicants refresh failed")
            messagebox.showerror(
                "UCAS", f"Could not load applicants: {e}")
            return
        for a in rows:
            self.tree.insert(
                "", "end", iid=str(a.choice_id),
                values=(a.student_id, a.student_name,
                          a.cycle_year, a.course_name,
                          a.app_status, a.decision_status,
                          a.offer_terms or "—",
                          a.submitted_at or "—"),
                tags=(a.decision_status,),
            )
        self.count.configure(text=f"{len(rows)} applicant(s)")

    def _open(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("UCAS", "Select an applicant first.")
            return
        try:
            choice_id = int(sel[0])
        except (TypeError, ValueError):
            return
        # Re-fetch via list_applicants to get the current Applicant
        # row (we don't have a direct by-id getter for the flat
        # projection, but iterating the small list is fine).
        applicant = next(
            (a for a in data.list_applicants()
             if a.choice_id == choice_id),
            None,
        )
        if applicant is None:
            self.refresh()
            return
        ApplicantDetailDialog(self.root, applicant=applicant,
                                on_change=self.refresh)


# ─────────────────────────────────────────────────────────────────
# Applicant detail dialog
# ─────────────────────────────────────────────────────────────────

class ApplicantDetailDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, *,
                 applicant: Applicant, on_change) -> None:
        super().__init__(master)
        self.applicant = applicant
        self.on_change = on_change
        self.title(f"UCAS Applicant — {applicant.student_name} "
                    f"({applicant.student_id})")
        self.geometry("1000x820")
        self.minsize(900, 700)
        self.transient(master)

        try:
            full = data.get_full_application(applicant.application_id)
        except UcasError as e:
            messagebox.showwarning("UCAS", str(e), parent=self)
            full = None
        except Exception as e:
            logger.exception("Loading applicant detail failed")
            messagebox.showerror("UCAS",
                                   f"Could not load applicant: {e}",
                                   parent=self)
            full = None
        self.full = full

        self._build()

    def _build(self) -> None:
        # Pin Save / Close buttons outside the scrollable area so they
        # stay reachable even when the dialog is taller than the
        # screen. Pack the footer first (bottom) so the canvas above
        # doesn't push it off-screen on tight resizes.
        footer = ttk.Frame(self, padding=(12, 8))
        footer.pack(side="bottom", fill="x")
        ttk.Button(footer, text="Close",
                    command=self.destroy).pack(side="right", padx=4)
        ttk.Button(footer, text="Record decision",
                    command=self._save).pack(side="right", padx=4)

        # Scrollable body: Canvas + Scrollbar + inner Frame.
        outer = ttk.Frame(self)
        outer.pack(side="top", fill="both", expand=True)
        canvas = tk.Canvas(outer, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical",
                              command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        frm = ttk.Frame(canvas, padding=12)
        win_id = canvas.create_window((0, 0), window=frm, anchor="nw")
        frm.bind(
            "<Configure>",
            lambda _e: canvas.configure(
                scrollregion=canvas.bbox("all")))
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(win_id, width=e.width))

        # Mousewheel scrolls while the pointer is over the canvas.
        def _on_mw(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>",
                      lambda _e: canvas.bind_all("<MouseWheel>", _on_mw))
        canvas.bind("<Leave>",
                      lambda _e: canvas.unbind_all("<MouseWheel>"))

        # Header
        hdr = ttk.Frame(frm)
        hdr.pack(fill="x", pady=(0, 8))
        a = self.applicant
        f = self.full
        ttk.Label(hdr, text=f"{a.student_name}  ({a.student_id})",
                    font=("", 14, "bold")).grid(
            row=0, column=0, sticky="w")
        meta = (
            f"Course: {a.course_name}"
            f"   ·   Cycle: {a.cycle_year}"
            f"   ·   UCAS ID: {a.ucas_id or '—'}"
            f"   ·   Submitted: {a.submitted_at or '—'}"
        )
        ttk.Label(hdr, text=meta, foreground="#444").grid(
            row=1, column=0, sticky="w", pady=(2, 0))
        student_meta = (
            f"DOB: {a.student_dob or '—'}"
            f"   ·   Email: {a.student_email}"
            f"   ·   Student status: {a.student_status}"
        )
        ttk.Label(hdr, text=student_meta, foreground="#444").grid(
            row=2, column=0, sticky="w")
        if f is not None and f.subjects:
            ttk.Label(hdr,
                       text="A-Levels: " + ", ".join(f.subjects),
                       foreground="#444").grid(
                row=3, column=0, sticky="w")

        # Personal statement
        ps_frame = ttk.LabelFrame(frm, text="Personal statement",
                                     padding=8)
        ps_frame.pack(fill="both", expand=False, pady=(0, 8))
        ps = tk.Text(ps_frame, wrap="word", height=10,
                       state="normal")
        ps.pack(fill="both", expand=True)
        if f is not None and f.personal_statement:
            ps.insert("1.0", f.personal_statement)
        else:
            ps.insert("1.0", "(none on file)")
        ps.configure(state="disabled")

        # All choices
        choices_frame = ttk.LabelFrame(
            frm, text="All choices on this application",
            padding=8)
        choices_frame.pack(fill="both", expand=True, pady=(0, 8))
        cols = ("ours", "slot", "university", "course",
                "decision", "final", "terms")
        tree = ttk.Treeview(choices_frame, columns=cols,
                               show="headings", height=6)
        widths = {"ours": 40, "slot": 40, "university": 240,
                   "course": 220, "decision": 160, "final": 90,
                   "terms": 200}
        for c in cols:
            tree.heading(c, text=("•" if c == "ours"
                                     else c.replace("_", " ").title()))
            tree.column(c, width=widths[c],
                          anchor=("center" if c in ("ours", "slot",
                                                      "final")
                                   else "w"))
        tree.pack(fill="both", expand=True)
        for decision, (bg, fg) in _DECISION_TAGS.items():
            tree.tag_configure(decision, background=bg, foreground=fg)
        if f is not None:
            for c in f.choices:
                is_ours = (c.choice_id == f.our_choice_id)
                tree.insert(
                    "", "end",
                    values=("→" if is_ours else "",
                              c.choice_order, c.university,
                              c.course_name, c.decision_status,
                              c.final_decision or "—",
                              c.offer_terms or "—"),
                    tags=(c.decision_status,),
                )

        # Decision panel
        dec_frame = ttk.LabelFrame(
            frm,
            text="Record admissions decision for this university",
            padding=10)
        dec_frame.pack(fill="x", pady=(0, 4))

        ttk.Label(dec_frame, text="New decision:").grid(
            row=0, column=0, sticky="w", pady=4)
        self.cb_decision = ttk.Combobox(
            dec_frame, values=DECIDABLE, state="readonly", width=24)
        self.cb_decision.set(
            self.applicant.decision_status
            if self.applicant.decision_status in DECIDABLE
            else "Conditional Offer")
        self.cb_decision.grid(row=0, column=1, sticky="ew",
                                 pady=4, padx=(8, 16))
        self.cb_decision.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._update_terms_hint())

        ttk.Label(dec_frame, text="Offer terms:").grid(
            row=0, column=2, sticky="w", pady=4)
        self.e_terms = ttk.Entry(dec_frame, width=44)
        self.e_terms.grid(row=0, column=3, sticky="ew",
                            pady=4, padx=(8, 0))
        if self.applicant.offer_terms:
            self.e_terms.insert(0, self.applicant.offer_terms)

        self.terms_hint = ttk.Label(dec_frame, text="",
                                       foreground="#666")
        self.terms_hint.grid(row=1, column=0, columnspan=4,
                                sticky="w", pady=(2, 4))

        ttk.Label(dec_frame, text="Notes:").grid(
            row=2, column=0, sticky="nw", pady=4)
        self.t_notes = tk.Text(dec_frame, wrap="word", height=4,
                                  width=60)
        self.t_notes.grid(row=2, column=1, columnspan=3,
                            sticky="ew", pady=4, padx=(8, 0))
        if self.applicant.choice_notes:
            self.t_notes.insert("1.0", self.applicant.choice_notes)

        dec_frame.columnconfigure(3, weight=1)
        self._update_terms_hint()

        # Internal admissions notes — uni-only, not visible to the
        # sixth form. Wrapped in its own LabelFrame to make it
        # obvious from the public Notes field on the decision panel
        # above.
        self._build_internal_notes_panel(frm)

    def _build_internal_notes_panel(self, parent) -> None:
        """Build the internal-notes panel. Loads the existing link
        (if any) and lists all notes attached to it.
        """
        from education_system.post_18.university_system.modules.domain.admissions.ucas import (
            ucas_links as _links,
        )
        self._links_module = _links

        # ── Link metadata panel ──────────────────────────────────
        link_frame = ttk.LabelFrame(
            parent,
            text="Internal link metadata  ·  uni-only",
            padding=10,
        )
        link_frame.pack(fill="x", pady=(8, 4))
        for c in range(6):
            link_frame.columnconfigure(c, weight=(1 if c % 2 else 0))

        ttk.Label(link_frame, text="Link #:").grid(
            row=0, column=0, sticky="w", pady=2)
        self.link_id_label = ttk.Label(link_frame, text="—",
                                          foreground="#444")
        self.link_id_label.grid(row=0, column=1, sticky="w",
                                  padx=(6, 16), pady=2)
        ttk.Label(link_frame, text="Status:").grid(
            row=0, column=2, sticky="w", pady=2)
        self.cb_link_status = ttk.Combobox(
            link_frame,
            values=_links.LINK_STATUSES,
            state="readonly", width=14)
        self.cb_link_status.grid(row=0, column=3, sticky="w",
                                    padx=(6, 16), pady=2)
        ttk.Label(link_frame, text="Linked at:").grid(
            row=0, column=4, sticky="w", pady=2)
        self.link_at_label = ttk.Label(link_frame, text="—",
                                          foreground="#444")
        self.link_at_label.grid(row=0, column=5, sticky="w",
                                  padx=(6, 0), pady=2)

        ttk.Label(link_frame, text="Uni application_id:").grid(
            row=1, column=0, sticky="w", pady=2)
        self.e_uni_app = ttk.Entry(link_frame, width=12)
        self.e_uni_app.grid(row=1, column=1, sticky="w",
                              padx=(6, 16), pady=2)
        ttk.Label(link_frame, text="Uni student_id:").grid(
            row=1, column=2, sticky="w", pady=2)
        self.e_uni_student = ttk.Entry(link_frame, width=16)
        self.e_uni_student.grid(row=1, column=3, sticky="w",
                                   padx=(6, 16), pady=2)

        ttk.Button(link_frame, text="Update link",
                    command=self._update_link_metadata).grid(
            row=1, column=5, sticky="e", padx=(6, 0), pady=2)

        notes_frame = ttk.LabelFrame(
            parent,
            text="Internal admissions notes  ·  uni-only, not "
                 "visible to the sixth form",
            padding=10,
        )
        notes_frame.pack(fill="both", expand=False, pady=(8, 4))
        notes_frame.columnconfigure(0, weight=1)

        # List of existing notes
        list_frame = ttk.Frame(notes_frame)
        list_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        list_frame.columnconfigure(0, weight=1)
        cols = ("created", "author", "body")
        self.notes_tree = ttk.Treeview(
            list_frame, columns=cols, show="headings",
            selectmode="browse", height=5)
        self.notes_tree.heading("created", text="Created")
        self.notes_tree.column("created", width=140, anchor="w")
        self.notes_tree.heading("author", text="Author")
        self.notes_tree.column("author", width=110, anchor="w")
        self.notes_tree.heading("body", text="Note")
        self.notes_tree.column("body", width=600, anchor="w")
        vsb = ttk.Scrollbar(list_frame, orient="vertical",
                              command=self.notes_tree.yview)
        self.notes_tree.configure(yscrollcommand=vsb.set)
        self.notes_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # Add-note row + controls
        add_row = ttk.Frame(notes_frame)
        add_row.grid(row=1, column=0, sticky="ew")
        add_row.columnconfigure(0, weight=1)
        self.new_note = tk.Text(add_row, wrap="word", height=3)
        self.new_note.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        btn_col = ttk.Frame(add_row)
        btn_col.grid(row=0, column=1, sticky="ns")
        ttk.Button(btn_col, text="Add note",
                    command=self._add_internal_note).pack(
            side="top", fill="x", pady=(0, 2))
        ttk.Button(btn_col, text="Edit selected",
                    command=self._edit_internal_note).pack(
            side="top", fill="x", pady=(0, 2))
        ttk.Button(btn_col, text="Delete selected",
                    command=self._delete_internal_note).pack(
            side="top", fill="x")
        self.notes_tree.bind(
            "<Double-Button-1>",
            lambda _e: self._edit_internal_note())

        self._refresh_link_panel()
        self._refresh_internal_notes()

    def _refresh_link_panel(self) -> None:
        """Populate the link-metadata widgets from the current link
        (looked up by sf_choice_id). Falls back to empty values if no
        link exists yet — the panel still lets the user click Update
        to create one with their entered values."""
        link = self._links_module.get_link_by_choice(
            self.applicant.choice_id)
        if link is None:
            self.link_id_label.configure(text="(no link yet — "
                                             "Update creates it)")
            self.link_at_label.configure(text="—")
            self.cb_link_status.set(
                self._links_module.DEFAULT_LINK_STATUS)
            self.e_uni_app.delete(0, "end")
            self.e_uni_student.delete(0, "end")
            return
        self.link_id_label.configure(text=str(link.link_id))
        self.link_at_label.configure(text=link.linked_at)
        self.cb_link_status.set(link.status)
        self.e_uni_app.delete(0, "end")
        if link.uni_application_id is not None:
            self.e_uni_app.insert(0, str(link.uni_application_id))
        self.e_uni_student.delete(0, "end")
        if link.uni_student_id:
            self.e_uni_student.insert(0, link.uni_student_id)

    def _update_link_metadata(self) -> None:
        """Persist the link-metadata widget values to the data layer.
        Creates the link on demand if it doesn't exist yet."""
        link_id = self._current_link_id()
        if link_id is None:
            messagebox.showerror(
                "Update link",
                "Could not load or create a link for this applicant.",
                parent=self,
            )
            return

        # Status
        try:
            self._links_module.set_link_status(
                link_id, self.cb_link_status.get())
        except self._links_module.UcasLinkError as e:
            messagebox.showwarning("Update link", str(e), parent=self)
            return
        except Exception as e:
            logger.exception("set_link_status failed")
            messagebox.showerror("Update link",
                                   f"Status update failed: {e}",
                                   parent=self)
            return

        # Uni application id (blank → clear)
        raw_app = self.e_uni_app.get().strip()
        uni_app_id: int | None
        if raw_app:
            try:
                uni_app_id = int(raw_app)
            except ValueError:
                messagebox.showwarning(
                    "Update link",
                    "Uni application_id must be a number "
                    "(or blank to clear).",
                    parent=self,
                )
                return
        else:
            uni_app_id = None
        try:
            self._links_module.attach_uni_application(
                link_id, uni_app_id)
        except self._links_module.UcasLinkError as e:
            messagebox.showwarning("Update link", str(e), parent=self)
            return
        except Exception as e:
            logger.exception("attach_uni_application failed")
            messagebox.showerror("Update link",
                                   f"Could not attach uni "
                                   f"application: {e}", parent=self)
            return

        # Uni student id (blank → clear)
        raw_stu = self.e_uni_student.get().strip()
        uni_student_id = raw_stu or None
        try:
            self._links_module.attach_uni_student(
                link_id, uni_student_id)
        except self._links_module.UcasLinkError as e:
            messagebox.showwarning("Update link", str(e), parent=self)
            return
        except Exception as e:
            logger.exception("attach_uni_student failed")
            messagebox.showerror("Update link",
                                   f"Could not attach uni "
                                   f"student: {e}", parent=self)
            return

        self._refresh_link_panel()
        messagebox.showinfo("Update link",
                              "Link metadata saved.", parent=self)

    def _edit_internal_note(self) -> None:
        sel = self.notes_tree.selection()
        if not sel:
            return
        try:
            note_id = int(sel[0])
        except (TypeError, ValueError):
            return
        note = self._links_module.get_note(note_id)
        if note is None:
            self._refresh_internal_notes()
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Edit internal note #{note_id}")
        dlg.geometry("680x360")
        dlg.transient(self)
        dlg.grab_set()

        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(1, weight=1)
        ttk.Label(
            frm,
            text=f"by {note.author or '—'}  "
                 f"·  created {note.created_at}  "
                 f"·  last edited {note.updated_at}",
            foreground="#666",
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        text = tk.Text(frm, wrap="word")
        text.grid(row=1, column=0, sticky="nsew")
        text.insert("1.0", note.body)

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="Cancel",
                    command=dlg.destroy).pack(side="right", padx=4)

        def _save() -> None:
            new_body = text.get("1.0", "end").strip()
            try:
                self._links_module.update_note(note_id, new_body)
            except self._links_module.UcasLinkError as e:
                messagebox.showwarning("Edit note", str(e), parent=dlg)
                return
            except Exception as e:
                logger.exception("update_note failed")
                messagebox.showerror("Edit note",
                                       f"Save failed: {e}",
                                       parent=dlg)
                return
            self._refresh_internal_notes()
            dlg.destroy()

        ttk.Button(btns, text="Save",
                    command=_save).pack(side="right", padx=4)

    def _current_link_id(self) -> int | None:
        """Return the link_id for the current applicant's choice,
        creating one on demand. Returns None on failure (logged)."""
        try:
            link = self._links_module.ensure_link_for_choice(
                sf_application_id=self.applicant.application_id,
                sf_choice_id=self.applicant.choice_id,
                sf_student_id=self.applicant.student_id,
            )
            return link.link_id
        except Exception:
            logger.exception(
                "Could not ensure UCAS link for choice #%d",
                self.applicant.choice_id)
            return None

    def _refresh_internal_notes(self) -> None:
        for iid in self.notes_tree.get_children():
            self.notes_tree.delete(iid)
        link = self._links_module.get_link_by_choice(
            self.applicant.choice_id)
        if link is None:
            return
        for note in self._links_module.list_notes(link.link_id):
            preview = note.body.replace("\n", " ⏎ ")
            self.notes_tree.insert(
                "", "end", iid=str(note.note_id),
                values=(note.created_at, note.author or "—",
                          preview),
            )

    def _add_internal_note(self) -> None:
        body = self.new_note.get("1.0", "end").strip()
        if not body:
            messagebox.showwarning(
                "Internal note",
                "Write something in the note box first.",
                parent=self,
            )
            return
        link_id = self._current_link_id()
        if link_id is None:
            messagebox.showerror(
                "Internal note",
                "Could not load or create a link for this applicant.",
                parent=self,
            )
            return
        author = None
        try:
            cu = getattr(getattr(self.master, "auth", None),
                          "current_user", None)
            if isinstance(cu, dict):
                author = cu.get("username")
        except Exception:
            pass
        try:
            self._links_module.add_note(
                link_id, body, author=author)
        except Exception as e:
            logger.exception("Add internal note failed")
            messagebox.showerror("Internal note",
                                   f"Could not save note: {e}",
                                   parent=self)
            return
        self.new_note.delete("1.0", "end")
        self._refresh_internal_notes()

    def _delete_internal_note(self) -> None:
        sel = self.notes_tree.selection()
        if not sel:
            return
        try:
            note_id = int(sel[0])
        except (TypeError, ValueError):
            return
        if not messagebox.askyesno(
                "Internal note",
                f"Delete note #{note_id}?",
                parent=self):
            return
        try:
            self._links_module.delete_note(note_id)
        except Exception as e:
            logger.exception("Delete internal note failed")
            messagebox.showerror("Internal note",
                                   f"Could not delete: {e}",
                                   parent=self)
            return
        self._refresh_internal_notes()

    def _update_terms_hint(self) -> None:
        d = self.cb_decision.get()
        if d == "Conditional Offer":
            self.terms_hint.configure(
                text=("Offer terms are required for a conditional offer "
                       "(e.g. 'ABB including B in Mathematics')."))
        elif d == "Unconditional Offer":
            self.terms_hint.configure(
                text="Offer terms are optional for unconditional offers.")
        else:
            self.terms_hint.configure(
                text="Offer terms are optional; leave blank to clear.")

    def _save(self) -> None:
        decision = self.cb_decision.get()
        terms = self.e_terms.get().strip()
        notes = self.t_notes.get("1.0", "end").strip()
        try:
            data.record_decision(
                self.applicant.choice_id,
                decision,
                offer_terms=terms or None,
                notes=notes or None,
            )
        except UcasError as e:
            messagebox.showwarning("UCAS", str(e), parent=self)
            return
        except Exception as e:
            logger.exception("record_decision failed")
            messagebox.showerror("UCAS",
                                   f"Could not record decision: {e}",
                                   parent=self)
            return
        self.on_change()
        messagebox.showinfo(
            "UCAS",
            f"Decision recorded: {decision}"
            + (f"\nOffer terms: {terms}" if terms else ""),
            parent=self,
        )
        self.destroy()


# ─────────────────────────────────────────────────────────────────
# Pipeline tab (uni-internal links view)
# ─────────────────────────────────────────────────────────────────

class PipelineTab:
    """Flat view of every uni-internal UCAS link — useful when the
    admissions team wants to filter by status, jump to a specific
    link_id, or see which links still need a uni_application_id /
    uni_student_id attached."""

    def __init__(self, nb: ttk.Notebook, root: tk.Misc,
                  applicants_tab: ApplicantsTab) -> None:
        from education_system.post_18.university_system.modules.domain.admissions.ucas import (
            ucas_links as _links,
        )
        self._links = _links
        self.root = root
        self.applicants_tab = applicants_tab
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Pipeline")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(
            bar, values=("",) + self._links.LINK_STATUSES,
            state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Student id:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=14)
        self.f_student.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="Open applicant",
                    command=self._open_applicant).pack(
            side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("link", "sf_app", "sf_choice", "sf_student",
                "uni_app", "uni_student", "status", "linked_at")
        self.tree = ttk.Treeview(
            table_frame, columns=cols, show="headings",
            selectmode="browse")
        widths = {"link": 60, "sf_app": 70, "sf_choice": 80,
                   "sf_student": 110, "uni_app": 80,
                   "uni_student": 120, "status": 100,
                   "linked_at": 160}
        labels = {"link": "Link #", "sf_app": "sf-app",
                   "sf_choice": "sf-choice",
                   "sf_student": "sf-student",
                   "uni_app": "uni-app",
                   "uni_student": "uni-student",
                   "status": "Status", "linked_at": "Linked at"}
        for c in cols:
            self.tree.heading(c, text=labels[c])
            self.tree.column(c, width=widths[c],
                              anchor=("w"
                                       if c in ("sf_student",
                                                  "uni_student",
                                                  "linked_at")
                                       else "center"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure(
            "withdrawn", background="#fff7e6", foreground="#7a5800")
        self.tree.tag_configure(
            "archived", background="#eeeeee", foreground="#666666")
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._open_applicant())

        self.count = ttk.Label(self.frame, text="")
        self.count.pack(anchor="e", padx=8, pady=(0, 8))

    def _clear(self) -> None:
        self.f_status.current(0)
        self.f_student.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        kw = {}
        if self.f_status.get():
            kw["status"] = self.f_status.get()
        if self.f_student.get().strip():
            kw["sf_student_id"] = self.f_student.get().strip()
        try:
            rows = self._links.list_links(**kw)
        except self._links.UcasLinkError as e:
            messagebox.showwarning("UCAS", str(e))
            return
        except Exception as e:
            logger.exception("Pipeline refresh failed")
            messagebox.showerror("UCAS",
                                   f"Could not load pipeline: {e}")
            return
        for l in rows:
            tags: tuple[str, ...] = ()
            if l.status in ("withdrawn", "archived"):
                tags = (l.status,)
            self.tree.insert(
                "", "end", iid=str(l.link_id),
                values=(l.link_id, l.sf_application_id,
                          l.sf_choice_id, l.sf_student_id,
                          l.uni_application_id or "—",
                          l.uni_student_id or "—",
                          l.status, l.linked_at),
                tags=tags,
            )
        self.count.configure(text=f"{len(rows)} link(s)")

    def _open_applicant(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(
                "UCAS",
                "Select a link first, then click Open applicant.")
            return
        try:
            link_id = int(sel[0])
        except (TypeError, ValueError):
            return
        link = self._links.get_link(link_id)
        if link is None:
            self.refresh()
            return
        # Find the matching Applicant by choice_id so we can open the
        # detail dialog. If our uni-name filter no longer matches
        # (e.g. uni was renamed), surface that to the user.
        applicant = next(
            (a for a in data.list_applicants()
             if a.choice_id == link.sf_choice_id),
            None,
        )
        if applicant is None:
            messagebox.showinfo(
                "UCAS",
                f"Could not find an applicant for sf_choice_id="
                f"{link.sf_choice_id}. The choice may have been "
                "deleted on the sixth-form side, or no longer names "
                "this university.")
            return
        ApplicantDetailDialog(
            self.root, applicant=applicant,
            on_change=lambda: (self.refresh(),
                                self.applicants_tab.refresh()),
        )


# ─────────────────────────────────────────────────────────────────
# Summary tab
# ─────────────────────────────────────────────────────────────────

class SummaryTab:
    def __init__(self, nb: ttk.Notebook,
                  applicants_tab: ApplicantsTab) -> None:
        self.applicants_tab = applicants_tab
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        top = ttk.Frame(self.frame, padding=12)
        top.pack(fill="both", expand=True)
        ttk.Button(top, text="Refresh",
                    command=self.refresh).pack(anchor="e")
        self.body = tk.Text(top, wrap="word", font=("Courier", 10),
                             height=30, state="disabled")
        self.body.pack(fill="both", expand=True, pady=(8, 0))

    def refresh(self) -> None:
        try:
            s = data.summary()
        except UcasError as e:
            messagebox.showwarning("UCAS", str(e))
            return
        except Exception as e:
            logger.exception("Summary failed")
            messagebox.showerror("UCAS",
                                   f"Summary failed: {e}")
            return
        lines: list[str] = []
        lines.append(f"University           : {s.university_name}")
        lines.append(f"Total applicants     : {s.total_applicants}")
        lines.append(f"Awaiting decision    : {s.awaiting_decision}")
        lines.append(f"Offers made          : {s.offers_made}")
        lines.append("")
        lines.append("By decision:")
        for k, v in s.by_decision.items():
            lines.append(f"  {k:<22} {v:>4}")
        lines.append("")
        lines.append("By application status:")
        for k, v in s.by_app_status.items():
            if v:
                lines.append(f"  {k:<14} {v:>4}")
        if s.by_course:
            lines.append("")
            lines.append("By course:")
            for k, v in sorted(s.by_course.items(),
                                 key=lambda kv: -kv[1]):
                lines.append(f"  {k[:28]:<28} {v:>4}")
        if s.by_cycle:
            lines.append("")
            lines.append("By cycle year:")
            for k, v in sorted(s.by_cycle.items()):
                lines.append(f"  {k:<6} {v:>4}")
        self.body.configure(state="normal")
        self.body.delete("1.0", "end")
        self.body.insert("1.0", "\n".join(lines))
        self.body.configure(state="disabled")
