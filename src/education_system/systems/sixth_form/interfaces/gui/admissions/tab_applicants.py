"""Applicants tab of the Sixth Form Admissions window.

Split out of ``admissions_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable
import datetime as _dt
import os
from pathlib import Path
import subprocess
import tkinter as tk
from collections import Counter
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from typing import Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)
from education_system.systems.sixth_form.domain.admissions import (
    applicant_reports as reports,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
    OPEN_STATUSES,
    SOURCES,
    STATUSES,
    TERMINAL_STATUSES,
)
from . import applicant_actions as act
from . import applicant_email
from ._common import STALE_CRIT_DAYS, STALE_WARN_DAYS, _compute_age, _days_in_stage, _prompt, _subject_options, _today


# ══ Applicants tab ════════════════════════════════════════════════

class ApplicantsTab:
    # Treeview columns and their default header widths.
    COLS = ("id", "name", "age", "submitted", "days", "status",
            "offer", "source", "subjects", "interview")
    HEADINGS = {"id": "ID", "name": "Name", "age": "Age",
                "submitted": "Submitted", "days": "Days",
                "status": "Status", "offer": "Offer",
                "source": "Source", "subjects": "Subjects",
                "interview": "Interview"}
    WIDTHS = {"id": 80, "name": 170, "age": 48, "submitted": 100,
              "days": 52, "status": 140, "offer": 110, "source": 120,
              "subjects": 240, "interview": 100}

    def __init__(self, nb: ttk.Notebook, *,
                 open_only: bool, label: str) -> None:
        self.open_only = open_only
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        # View state.
        self._rows: list[Applicant] = []
        self._sort_col: str | None = "submitted"
        self._sort_reverse = True
        self._preset: Callable[[Applicant], bool] | None = None
        self._page = 0
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(bar, text="Search:").pack(side="left")
        self.f_search = ttk.Entry(bar, width=16)
        self.f_search.pack(side="left", padx=(2, 10))
        self.f_search.bind("<Return>", lambda _e: self.refresh())

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                       state="readonly", width=20)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Source:").pack(side="left")
        self.f_source = ttk.Combobox(bar, values=("",) + SOURCES,
                                       state="readonly", width=16)
        self.f_source.current(0)
        self.f_source.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Subject:").pack(side="left")
        self.f_subject = ttk.Combobox(
            bar, values=("",) + tuple(_subject_options()),
            state="readonly", width=18)
        self.f_subject.current(0)
        self.f_subject.pack(side="left", padx=(2, 10))

        # Live client-side quick-find (item 10) — filters loaded rows as you
        # type, without a database round-trip.
        ttk.Label(bar, text="Find:").pack(side="left")
        self.f_quick = ttk.Entry(bar, width=14)
        self.f_quick.pack(side="left", padx=(2, 10))
        self.f_quick.bind("<KeyRelease>", self._quick_search)

        # Age-range filter (item 15 — the Age column itself already exists).
        ttk.Label(bar, text="Age:").pack(side="left")
        self.f_age_min = ttk.Entry(bar, width=3)
        self.f_age_min.pack(side="left", padx=(2, 0))
        ttk.Label(bar, text="–").pack(side="left")
        self.f_age_max = ttk.Entry(bar, width=3)
        self.f_age_max.pack(side="left", padx=(0, 10))
        self.f_age_min.bind("<KeyRelease>", self._quick_search)
        self.f_age_max.bind("<KeyRelease>", self._quick_search)

        self.v_has_offer = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Has offer", variable=self.v_has_offer,
                         command=self.refresh).pack(side="left", padx=(0, 6))
        self.v_enrolled = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Enrolled", variable=self.v_enrolled,
                         command=self.refresh).pack(side="left", padx=(0, 8))

        ttk.Label(bar, text="Intake:").pack(side="left")
        self.f_intake = ttk.Combobox(bar, values=self._intake_options(),
                                     width=9)
        self.f_intake.pack(side="left", padx=(2, 6))
        self.f_intake.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.f_intake.bind("<Return>", lambda _e: self.refresh())
        self.v_archived = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Show archived", variable=self.v_archived,
                        command=self.refresh).pack(side="left", padx=(0, 8))

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(4, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        # Saved filter presets / quick chips.
        chips = ttk.Frame(self.frame)
        chips.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(chips, text="Quick:").pack(side="left")
        ttk.Button(chips, text="Awaiting decision",
                    command=self._preset_awaiting).pack(side="left", padx=2)
        ttk.Button(chips, text="Offers outstanding",
                    command=self._preset_offers).pack(side="left", padx=2)
        ttk.Button(chips, text="Interviews this week",
                    command=self._preset_interviews).pack(side="left", padx=2)
        if not self.open_only:
            ttk.Separator(chips, orient="vertical").pack(
                side="left", fill="y", padx=8)
            ttk.Button(chips, text="Open only",
                        command=lambda: self._preset_stage(OPEN_STATUSES)
                        ).pack(side="left", padx=2)
            ttk.Button(chips, text="Terminal only",
                        command=lambda: self._preset_stage(TERMINAL_STATUSES)
                        ).pack(side="left", padx=2)

        # Action rows are packed from the bottom up BEFORE the table, so
        # they stay visible on a short (1366x768) screen.
        tools = ttk.Frame(self.frame)
        tools.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        actions2 = ttk.Frame(self.frame)
        actions2.pack(side="bottom", fill="x", padx=8, pady=(0, 4))
        actions = ttk.Frame(self.frame)
        actions.pack(side="bottom", fill="x", padx=8, pady=(4, 4))
        pager = ttk.Frame(self.frame)
        pager.pack(side="bottom", fill="x", padx=8)
        self.count_var = tk.StringVar(value="")
        ttk.Label(pager, textvariable=self.count_var,
                  anchor="w").pack(side="left", fill="x", expand=True)
        self.page_next = ttk.Button(pager, text="Next ›",
                                    command=lambda: self._go_page(1))
        self.page_next.pack(side="right")
        self.page_var = tk.StringVar(value="")
        ttk.Label(pager, textvariable=self.page_var).pack(side="right",
                                                          padx=6)
        self.page_prev = ttk.Button(pager, text="‹ Prev",
                                    command=lambda: self._go_page(-1))
        self.page_prev.pack(side="right")

        ttk.Button(actions, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(actions, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Make offer",
                    command=self._offer_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Accept",
                    command=lambda: self._quick_status(
                        "Offer Accepted")).pack(side="left", padx=2)
        ttk.Button(actions, text="Decline",
                    command=lambda: self._withdraw_selected(True)).pack(
            side="left", padx=2)
        ttk.Button(actions, text="Reject",
                    command=lambda: self._quick_status(
                        "Rejected")).pack(side="left", padx=2)
        ttk.Button(actions, text="Convert",
                    command=self._convert_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

        # Safe record actions (reopen, withdraw, defer, archive, restore).
        for text, cmd in (
                ("Reopen…", self._reopen_selected),
                ("Withdraw…", lambda: self._withdraw_selected(False)),
                ("Defer…", self._defer_selected),
                ("Archive…", self._archive_selected),
                ("Restore", self._restore_selected)):
            ttk.Button(actions2, text=text, command=cmd).pack(
                side="left", padx=(0, 4))
        ttk.Label(actions2, foreground="#555", text=(
            "Keys: Ctrl+N new · Enter view · Ctrl+E edit · Delete delete/"
            "archive")).pack(side="right")

        ttk.Button(tools, text="Decision day…",
                    command=self._decision_day).pack(side="left")
        ttk.Button(tools, text="Bulk enrol accepted",
                    command=self._bulk_enrol).pack(side="left", padx=4)
        ttk.Button(tools, text="Email…",
                    command=self._email_selected).pack(side="left", padx=4)

        # Bulk actions over the current multi-selection (items 1–5, 11, 14).
        bulk_mb = ttk.Menubutton(tools, text="Bulk ▾")
        bulk = tk.Menu(bulk_mb, tearoff=0)
        bulk.add_command(label="Set status…", command=self._bulk_status)
        bulk.add_command(label="Reject with reason…",
                          command=self._bulk_reject)
        bulk.add_command(label="Add note…", command=self._bulk_add_note)
        bulk.add_command(label="Set source…", command=self._bulk_set_source)
        bulk.add_command(label="Assign interviewer…",
                          command=self._bulk_assign_interviewer)
        bulk.add_separator()
        bulk.add_command(label="Toggle follow-up",
                          command=self._toggle_follow_up)
        bulk.add_command(label="Copy emails", command=self._copy_email_list)
        bulk.add_command(label="GDPR export (batch)…",
                          command=self._gdpr_batch_export)
        bulk_mb["menu"] = bulk
        bulk_mb.pack(side="left", padx=4)
        self._bulk_menu = bulk

        # View controls (items 7, 8, 9).
        view_mb = ttk.Menubutton(tools, text="View ▾")
        vmenu = tk.Menu(view_mb, tearoff=0)
        vmenu.add_command(label="Choose columns…",
                           command=self._column_chooser)
        self.v_flag_dups = tk.BooleanVar(value=False)
        vmenu.add_checkbutton(label="Highlight duplicates",
                               variable=self.v_flag_dups,
                               command=self._flag_duplicates)
        vmenu.add_separator()
        vmenu.add_command(label="Saved views…", command=self._saved_views)
        view_mb["menu"] = vmenu
        view_mb.pack(side="left", padx=4)

        ttk.Button(tools, text="Merge dupes…",
                    command=self._merge_duplicates).pack(side="left", padx=4)
        ttk.Button(tools, text="Print",
                    command=self._print_list).pack(side="left", padx=4)
        ttk.Button(tools, text="Export PDF…",
                    command=self._export_selected_pdf).pack(side="left", padx=4)

        ttk.Button(tools, text="Export CSV…",
                    command=self._export_csv).pack(side="right")
        ttk.Button(tools, text="Import CSV…",
                    command=self._import_csv).pack(side="right", padx=4)

        # Columns currently shown (item 9 — column chooser toggles this).
        self._visible_cols = list(self.COLS)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        self.tree = ttk.Treeview(table_frame, columns=self.COLS,
                                  show="headings", selectmode="extended")
        for c in self.COLS:
            anchor = "center" if c in ("age", "days") else "w"
            self.tree.heading(
                c, text=self.HEADINGS[c],
                command=lambda col=c: self._sort_by(col))
            self.tree.column(c, width=self.WIDTHS[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        # Status colour bands (background).
        self.tree.tag_configure("Submitted",           background="#eef7ff")
        self.tree.tag_configure("Under Review",        background="#eef7ff")
        self.tree.tag_configure("Interview Scheduled", background="#fff7d0")
        self.tree.tag_configure("Interviewed",         background="#fff7d0")
        self.tree.tag_configure("Offer Made",          background="#fff7d0")
        self.tree.tag_configure("Offer Accepted",      background="#d8f4d8")
        self.tree.tag_configure("Enrolled",            background="#d8f4d8")
        self.tree.tag_configure("Offer Declined",     background="#eeeeee")
        self.tree.tag_configure("Rejected",            background="#ffd0d0")
        self.tree.tag_configure("Withdrawn",           background="#eeeeee")
        self.tree.tag_configure("Waitlisted",          background="#eef7ff")
        # Stale-stage indicators (foreground only, configured last so they
        # take precedence on the foreground option while the status tag
        # keeps owning the background).
        self.tree.tag_configure("stale_warn", foreground="#a06000")
        self.tree.tag_configure("stale_crit", foreground="#b00000")
        # Duplicate highlight (item 7). Configured after the status tags so it
        # wins the background option when both are present on a row.
        self.tree.tag_configure("dup", background="#ffd9b3")
        self.tree.tag_configure("archived", foreground="#888888")
        # Keyboard shortcuts (focus on the list).
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())
        self.tree.bind("<Return>", lambda _e: self._view_selected())
        self.tree.bind("<Control-n>", lambda _e: self._new())
        self.tree.bind("<Control-e>", lambda _e: self._edit_selected())
        self.tree.bind("<Delete>", lambda _e: self._delete_selected())
        self.tree.bind("<Button-3>", self._popup_menu)
        self.tree.bind("<Button-2>", self._popup_menu)  # macOS
        self._build_menu()
        self._apply_permissions()

    # Buttons by label → whether the signed-in person may use them.
    _ADMISSIONS_BUTTONS = (
        "New", "Edit", "Status", "Make offer", "Accept", "Decline", "Reject",
        "Delete", "Reopen…", "Withdraw…", "Defer…", "Archive…", "Restore",
        "Decision day…", "Email…", "Merge dupes…", "Import CSV…")
    _CONVERT_BUTTONS = ("Convert", "Bulk enrol accepted")
    _ADMISSIONS_MENU = ("Set status…", "Reject with reason…", "Add note…",
                        "Set source…", "Assign interviewer…",
                        "Toggle follow-up", "Change status…", "Make offer…",
                        "Accept offer", "Decline offer…", "Waitlist",
                        "Reject", "Merge duplicates…", "Delete", "Reopen…",
                        "Archive…", "Restore")

    def _apply_permissions(self) -> None:
        """Disable (keep visible) what the signed-in person cannot do."""
        adm, conv = act.can_admissions(), act.can_convert()

        def walk(w: tk.Misc):
            for c in w.winfo_children():
                yield c
                yield from walk(c)
        for w in walk(self.frame):
            if isinstance(w, ttk.Button):
                text = str(w.cget("text"))
                if text in self._ADMISSIONS_BUTTONS:
                    act.gate(w, adm)
                elif text in self._CONVERT_BUTTONS:
                    act.gate(w, conv)
        for menu in (self._bulk_menu, self._menu):
            for label in self._ADMISSIONS_MENU:
                act.gate_menu(menu, label, adm)
        act.gate_menu(self._menu, "Convert to student", conv)

    @staticmethod
    def _intake_options() -> tuple[str, ...]:
        names: set[str] = set()
        try:
            from education_system.systems.sixth_form.domain.admissions import (
                cycles,
            )
            names.update(c.cycle for c in cycles.list_cycles())
        except Exception:  # noqa: BLE001 — filter still accepts typing
            pass
        try:
            names.add(data.default_intake_year())
        except Exception:  # noqa: BLE001
            pass
        return ("",) + tuple(sorted(names, reverse=True))

    def _go_page(self, delta: int) -> None:
        self._page += delta
        self._render()

    # ── safe record actions ──────────────────────────────────────

    def _reopen_selected(self) -> None:
        aid = self._selected_id()
        if aid is None:
            messagebox.showinfo("Reopen", "Select an applicant first.")
            return
        act.reopen(self.frame, aid, self.refresh)

    def _withdraw_selected(self, decline: bool) -> None:
        act.withdraw_or_decline(self.frame, self._selected_ids(),
                                decline=decline, on_done=self.refresh)

    def _defer_selected(self) -> None:
        aid = self._selected_id()
        if aid is None:
            messagebox.showinfo("Defer", "Select an applicant first.")
            return
        act.defer(self.frame, aid, self.refresh)

    def _archive_selected(self) -> None:
        act.archive(self.frame, self._selected_ids(), self.refresh)

    def _restore_selected(self) -> None:
        act.restore(self.frame, self._selected_ids(), self.refresh)

    def _decision_day(self) -> None:
        queue = data.list_applicants(status="Interviewed")
        if not queue:
            messagebox.showinfo("Decision day",
                                  "No applicants are awaiting a decision "
                                  "(status 'Interviewed').")
            return
        DecisionDayDialog(self.frame.winfo_toplevel(), queue,
                          on_done=self.refresh)

    def _bulk_enrol(self) -> None:
        try:
            accepted = data.list_applicants(status="Offer Accepted")
        except Exception as e:  # noqa: BLE001 — shown
            act.show_error(self.frame, "Bulk enrol", e)
            return
        if not accepted:
            messagebox.showinfo("Bulk enrol",
                                  "No applicants in 'Offer Accepted'.")
            return
        from . import applicant_convert
        applicant_convert.convert_many(
            self.frame, [a.applicant_id for a in accepted], self.refresh,
            title="Bulk enrol accepted")

    def _email_selected(self) -> None:
        aid = self._selected_id()
        if aid is None:
            messagebox.showinfo("Email", "Select an applicant first.")
            return
        applicant_email.email_applicant(self.frame, aid, on_sent=self.refresh)

    def _export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.frame.winfo_toplevel(), defaultextension=".csv",
            initialfile="applicants.csv",
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        ok, n = act.attempt(self.frame, "Export CSV", reports.export_csv,
                            path, self._rows)
        if ok:
            messagebox.showinfo("Export CSV",
                                f"Exported {n} applicant(s) to {path}")

    def _import_csv(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.frame.winfo_toplevel(),
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            created, errors = reports.import_csv(path)
        except UnicodeDecodeError as e:
            messagebox.showerror(
                "Import CSV", f"The file is not UTF-8 text ({e.reason} at "
                f"byte {e.start}). Save it as 'CSV UTF-8' and try again.")
            return
        except Exception as e:  # noqa: BLE001 — file / CSV errors shown
            act.show_error(self.frame, "Import CSV", e)
            return
        self.refresh()
        if not errors:
            messagebox.showinfo("Import CSV",
                                f"Imported {created} applicant(s).")
            return
        from . import _admissions_ui as ui
        ui.show_text(self.frame.winfo_toplevel(), "Import CSV", "\n".join(
            [f"Imported {created} applicant(s); {len(errors)} row(s) were "
             "not imported:", ""] + errors))

    def _build_menu(self) -> None:
        m = tk.Menu(self.tree, tearoff=0)
        m.add_command(label="View", command=self._view_selected)
        m.add_command(label="Edit", command=self._edit_selected)
        m.add_separator()
        m.add_command(label="Change status…", command=self._status_selected)
        m.add_command(label="Make offer…", command=self._offer_selected)
        m.add_separator()
        m.add_command(label="Accept offer",
                       command=lambda: self._quick_status("Offer Accepted"))
        m.add_command(label="Decline offer…",
                       command=lambda: self._withdraw_selected(True))
        m.add_command(label="Waitlist",
                       command=lambda: self._quick_status("Waitlisted"))
        m.add_command(label="Reject",
                       command=lambda: self._quick_status("Rejected"))
        m.add_separator()
        m.add_command(label="Toggle follow-up",
                       command=self._toggle_follow_up)
        m.add_command(label="Merge duplicates…",
                       command=self._merge_duplicates)
        m.add_separator()
        m.add_command(label="Reopen…", command=self._reopen_selected)
        m.add_command(label="Archive…", command=self._archive_selected)
        m.add_command(label="Restore", command=self._restore_selected)
        m.add_separator()
        m.add_command(label="Convert to student",
                       command=self._convert_selected)
        m.add_command(label="Delete", command=self._delete_selected)
        self._menu = m

    def _popup_menu(self, event: tk.Event) -> None:
        row = self.tree.identify_row(event.y)
        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
        if not self.tree.selection():
            return
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    # ── filter presets ───────────────────────────────────────────

    def _preset_awaiting(self) -> None:
        self._reset_filters()
        self._preset = lambda a: a.status in ("Under Review", "Interviewed")
        self.refresh()

    def _preset_offers(self) -> None:
        self._reset_filters()
        self._preset = lambda a: a.status == "Offer Made"
        self.refresh()

    def _preset_interviews(self) -> None:
        self._reset_filters()
        today = _dt.date.today()
        end = (today + _dt.timedelta(days=7)).isoformat()
        start = today.isoformat()
        self._preset = lambda a: bool(
            a.interview_date and start <= a.interview_date[:10] <= end)
        self.refresh()

    def _preset_stage(self, statuses: tuple[str, ...]) -> None:
        self._reset_filters()
        allowed = set(statuses)
        self._preset = lambda a: a.status in allowed
        self.refresh()

    def _reset_filters(self) -> None:
        self.f_search.delete(0, "end")
        self.f_status.current(0)
        self.f_source.current(0)
        self.f_subject.current(0)
        self.f_quick.delete(0, "end")
        self.f_age_min.delete(0, "end")
        self.f_age_max.delete(0, "end")
        self.v_has_offer.set(False)
        self.v_enrolled.set(False)
        self.f_intake.set("")
        self.v_archived.set(False)

    def _clear(self) -> None:
        self._reset_filters()
        self._preset = None
        self.refresh()

    # ── sorting ──────────────────────────────────────────────────

    def _sort_by(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        self._render()

    @staticmethod
    def _sort_value(col: str, a: Applicant):
        if col == "id":
            return a.applicant_id
        if col == "name":
            return a.full_name.lower()
        if col == "age":
            age = _compute_age(a.dob)
            return age if age is not None else -1
        if col == "submitted":
            return a.submitted_at or ""
        if col == "days":
            d = _days_in_stage(a)
            return d if d is not None else -1
        if col == "status":
            return a.status
        if col == "offer":
            return a.offer_type or ""
        if col == "source":
            return a.application_source
        if col == "subjects":
            return ", ".join(a.subjects)
        if col == "interview":
            return a.interview_date or ""
        return ""

    def refresh(self) -> None:
        try:
            rows = data.list_applicants(
                status=self.f_status.get() or None,
                source=self.f_source.get() or None,
                search=self.f_search.get().strip() or None,
                open_only=self.open_only,
                has_offer=self.v_has_offer.get(),
                enrolled_only=self.v_enrolled.get(),
                intake_year=self.f_intake.get().strip() or None,
                include_archived=self.v_archived.get(),
            )
        except Exception as e:  # noqa: BLE001 — filter / permission errors
            act.show_error(self.frame, "Filter error", e)
            return
        subject = self.f_subject.get().strip()
        if subject:
            rows = [a for a in rows if subject in a.subjects]
        if self._preset is not None:
            rows = [a for a in rows if self._preset(a)]
        self._rows = rows
        self._page = 0
        self._render()

    PAGE_SIZE = 50

    def _render(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = self._visible_rows()
        if self._sort_col:
            rows.sort(key=lambda a: self._sort_value(self._sort_col, a),
                       reverse=self._sort_reverse)
        dup_ids = (self._duplicate_ids(rows)
                   if getattr(self, "v_flag_dups", None)
                   and self.v_flag_dups.get() else set())
        # Reflect sort direction in the heading text.
        for c in self.COLS:
            label = self.HEADINGS[c]
            if c == self._sort_col:
                label += " ▾" if self._sort_reverse else " ▴"
            self.tree.heading(c, text=label)

        total = len(rows)
        pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self._page = max(0, min(self._page, pages - 1))
        all_rows = rows
        rows = rows[self._page * self.PAGE_SIZE:
                    (self._page + 1) * self.PAGE_SIZE]
        self.page_var.set(f"Page {self._page + 1} / {pages}")
        act.gate(self.page_prev, self._page > 0)
        act.gate(self.page_next, self._page < pages - 1)
        for a in rows:
            age = _compute_age(a.dob)
            days = _days_in_stage(a)
            tags: tuple[str, ...] = (a.status,) if a.status in STATUSES else ()
            # Flag applicants stuck in an open stage too long.
            if a.is_open and days is not None:
                if days >= STALE_CRIT_DAYS:
                    tags += ("stale_crit",)
                elif days >= STALE_WARN_DAYS:
                    tags += ("stale_warn",)
            if a.applicant_id in dup_ids:
                tags += ("dup",)
            if a.is_archived:
                tags += ("archived",)
            self.tree.insert("", "end", iid=a.applicant_id, values=(
                a.applicant_id, a.full_name,
                age if age is not None else "—",
                a.submitted_at,
                days if days is not None else "—",
                a.status + (" (archived)" if a.is_archived else ""),
                a.offer_type or "—",
                a.application_source, ", ".join(a.subjects),
                a.interview_date or "—",
            ), tags=tags)
        self.count_var.set(self._count_summary(all_rows))

    @staticmethod
    def _count_summary(rows: list[Applicant]) -> str:
        if not rows:
            return "0 applicant(s)."
        counts = Counter(a.status for a in rows)
        # Show status tallies in canonical STATUSES order, skipping zeros.
        parts = [f"{n} {s}" for s in STATUSES if (n := counts.get(s, 0))]
        return f"{len(rows)} shown · " + " · ".join(parts)

    def _selected_ids(self) -> list[str]:
        return list(self.tree.selection())

    def _selected_id(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return sel[0]

    def _selected(self) -> Applicant | None:
        aid = self._selected_id()
        if aid is None:
            return None
        return data.get_applicant(aid)

    def _view_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("View", "Select an applicant first.")
            return
        DetailDialog(self.frame.winfo_toplevel(), a, on_change=self.refresh)

    def _new(self) -> None:
        ApplicantDialog(self.frame.winfo_toplevel(),
                          existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Edit", "Select an applicant first.")
            return
        ApplicantDialog(self.frame.winfo_toplevel(),
                          existing=a, on_save=self.refresh)

    def _status_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Status", "Select an applicant first.")
            return
        StatusDialog(self.frame.winfo_toplevel(), a,
                       on_save=self.refresh)

    def _offer_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Offer", "Select an applicant first.")
            return
        OfferDialog(self.frame.winfo_toplevel(), a,
                      on_save=self.refresh)

    def _quick_status(self, new_status: str) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo(new_status,
                                  "Select one or more applicants first.")
            return
        if len(ids) == 1:
            a = data.get_applicant(ids[0])
            who = f"{ids[0]} ({a.full_name})" if a else ids[0]
            prompt = f"Set {who} → {new_status}?"
        else:
            prompt = f"Set {len(ids)} applicants → {new_status}?"
        if not messagebox.askyesno(new_status, prompt):
            return
        failures = []
        for aid in ids:
            try:
                data.set_status(aid, new_status)
            except Exception as e:  # noqa: BLE001 — collect & report per row
                failures.append(f"{aid}: {e}")
        self.refresh()
        if failures:
            messagebox.showerror(
                new_status,
                f"{len(failures)} failed:\n" + "\n".join(failures))

    def _convert_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Convert",
                                  "Select one or more applicants first.")
            return
        from . import applicant_convert
        applicant_convert.convert_many(self.frame, ids, self.refresh)

    def _delete_selected(self) -> None:
        act.delete_or_archive(self.frame, self._selected_ids(), self.refresh)

    # ── selection / row helpers ──────────────────────────────────

    def _require_selection(self, title: str) -> list[str]:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo(title,
                                  "Select one or more applicants first.")
        return ids

    def _selected_applicants(self) -> list[Applicant]:
        by_id = {a.applicant_id: a for a in self._rows}
        return [by_id[i] for i in self._selected_ids() if i in by_id]

    def _apply_bulk(self, ids: list[str], title: str,
                    fn: Callable[[str], object], prompt: str) -> None:
        """Confirm, run ``fn`` over each id, refresh, then report failures."""
        if not messagebox.askyesno(title, prompt):
            return
        failures = []
        for aid in ids:
            try:
                fn(aid)
            except Exception as e:  # noqa: BLE001 — collect & report per row
                failures.append(f"{aid}: {act.describe(e).splitlines()[-1]}")
        self.refresh()
        if failures:
            messagebox.showerror(
                title, f"{len(failures)} of {len(ids)} failed:\n"
                + "\n".join(failures))
        else:
            messagebox.showinfo(title, f"Updated {len(ids)} applicant(s).")

    # ── bulk actions (items 1–5) ─────────────────────────────────

    def _bulk_status(self) -> None:
        ids = self._require_selection("Set status")
        if not ids:
            return
        # "Enrolled" is reached only by converting; each row is checked
        # against the workflow and refusals are reported per applicant.
        dlg = AskChoiceDialog(self.frame.winfo_toplevel(),
                              "Set status", "New status:",
                              [st for st in STATUSES if st != "Enrolled"])
        if not dlg.result:
            return
        self._apply_bulk(
            ids, "Set status",
            lambda aid: data.set_status(aid, dlg.result),
            f"Set {len(ids)} applicant(s) → {dlg.result}?")

    def _bulk_reject(self) -> None:
        ids = self._require_selection("Reject")
        if not ids:
            return
        reason = _prompt(self.frame, "Reject",
                          "Shared rejection reason (recorded on each):")
        if reason is None:
            return
        reason = reason.strip()
        self._apply_bulk(
            ids, "Reject",
            lambda aid: data.set_status(aid, "Rejected",
                                        decision_notes=reason or None),
            f"Reject {len(ids)} applicant(s)"
            + (f" — reason: {reason}?" if reason else "?"))

    def _bulk_add_note(self) -> None:
        ids = self._require_selection("Add note")
        if not ids:
            return
        body = _prompt(self.frame, "Add note",
                       "Note to append to each applicant:")
        if body is None or not body.strip():
            return
        body = body.strip()
        self._apply_bulk(
            ids, "Add note",
            lambda aid: data.add_note(aid, body, author=act.username()),
            f"Add this note to {len(ids)} applicant(s)?")

    def _bulk_set_source(self) -> None:
        ids = self._require_selection("Set source")
        if not ids:
            return
        dlg = AskChoiceDialog(self.frame.winfo_toplevel(),
                              "Set source", "Application source:",
                              list(SOURCES))
        if not dlg.result:
            return
        self._apply_bulk(
            ids, "Set source",
            lambda aid: data.update_applicant(
                aid, {"application_source": dlg.result}),
            f"Set source → {dlg.result} for {len(ids)} applicant(s)?")

    def _bulk_assign_interviewer(self) -> None:
        ids = self._require_selection("Assign interviewer")
        if not ids:
            return
        who = _prompt(self.frame, "Assign interviewer",
                      "Interviewer name (blank to clear):")
        if who is None:
            return
        who = who.strip()
        self._apply_bulk(
            ids, "Assign interviewer",
            lambda aid: data.update_applicant(aid, {"interviewer": who or None}),
            f"Assign interviewer '{who or '(cleared)'}' "
            f"to {len(ids)} applicant(s)?")

    # ── duplicates (items 6, 7) ──────────────────────────────────

    def _merge_duplicates(self) -> None:
        act.merge_dialog(self.frame, self._selected_applicants(),
                         self.refresh)

    def _flag_duplicates(self) -> None:
        # The checkbutton variable drives the highlight; just re-render.
        self._render()

    @staticmethod
    def _duplicate_ids(rows: list[Applicant]) -> set[str]:
        """Ids that share an email or phone with another shown row."""
        from collections import defaultdict
        by_key: dict[tuple[str, str], list[str]] = defaultdict(list)
        for a in rows:
            if a.email and a.email.strip():
                by_key[("e", a.email.strip().lower())].append(a.applicant_id)
            if a.phone and a.phone.strip():
                by_key[("p", a.phone.strip())].append(a.applicant_id)
        dupes: set[str] = set()
        for ids in by_key.values():
            if len(ids) > 1:
                dupes.update(ids)
        return dupes

    # ── saved views (item 8) ─────────────────────────────────────

    def _views_path(self) -> "Path":
        from pathlib import Path
        return Path(data.DB_PATH).parent / "admissions_saved_views.json"

    def _load_views(self) -> dict:
        import json
        p = self._views_path()
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — corrupt file shouldn't break the GUI
            return {}

    def _store_views(self, views: dict) -> None:
        import json
        self._views_path().write_text(
            json.dumps(views, indent=2), encoding="utf-8")

    def _capture_view(self) -> dict:
        return {
            "search": self.f_search.get(),
            "status": self.f_status.get(),
            "source": self.f_source.get(),
            "subject": self.f_subject.get(),
            "has_offer": self.v_has_offer.get(),
            "enrolled": self.v_enrolled.get(),
            "quick": self.f_quick.get(),
            "age_min": self.f_age_min.get(),
            "age_max": self.f_age_max.get(),
            "intake": self.f_intake.get(),
            "archived": self.v_archived.get(),
            "sort_col": self._sort_col,
            "sort_reverse": self._sort_reverse,
            "columns": list(self._visible_cols),
        }

    def _apply_saved_view(self, v: dict) -> None:
        self._preset = None
        for entry, value in ((self.f_search, v.get("search", "")),
                             (self.f_quick, v.get("quick", "")),
                             (self.f_age_min, v.get("age_min", "")),
                             (self.f_age_max, v.get("age_max", ""))):
            entry.delete(0, "end")
            entry.insert(0, value or "")
        self.f_status.set(v.get("status", ""))
        self.f_source.set(v.get("source", ""))
        self.f_subject.set(v.get("subject", ""))
        self.v_has_offer.set(bool(v.get("has_offer")))
        self.v_enrolled.set(bool(v.get("enrolled")))
        self.f_intake.set(v.get("intake", ""))
        self.v_archived.set(bool(v.get("archived")))
        self._sort_col = v.get("sort_col") or None
        self._sort_reverse = bool(v.get("sort_reverse"))
        cols = [c for c in self.COLS
                if c in set(v.get("columns", self.COLS))]
        self._visible_cols = cols or list(self.COLS)
        self.tree["displaycolumns"] = tuple(self._visible_cols)
        self.refresh()

    def _saved_views(self) -> None:
        top = self.frame.winfo_toplevel()
        win = tk.Toplevel(top)
        win.title("Saved views")
        win.transient(top)
        grab_when_viewable(win)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Saved views:").pack(anchor="w")
        lb = tk.Listbox(frm, height=8, width=40)
        lb.pack(fill="both", expand=True, pady=4)

        def reload_() -> None:
            lb.delete(0, "end")
            for name in sorted(self._load_views()):
                lb.insert("end", name)

        def apply_() -> None:
            sel = lb.curselection()
            if not sel:
                return
            v = self._load_views().get(lb.get(sel[0]))
            if v:
                self._apply_saved_view(v)
                win.destroy()

        def save_() -> None:
            name = _prompt(win, "Save view", "Name for this view:")
            if not name or not name.strip():
                return
            views = self._load_views()
            views[name.strip()] = self._capture_view()
            self._store_views(views)
            reload_()

        def delete_() -> None:
            sel = lb.curselection()
            if not sel:
                return
            views = self._load_views()
            views.pop(lb.get(sel[0]), None)
            self._store_views(views)
            reload_()

        reload_()
        lb.bind("<Double-1>", lambda _e: apply_())
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Apply", command=apply_).pack(side="left")
        ttk.Button(bar, text="Save current…",
                    command=save_).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete", command=delete_).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=win.destroy).pack(side="right")

    # ── column chooser (item 9) ──────────────────────────────────

    def _column_chooser(self) -> None:
        top = self.frame.winfo_toplevel()
        win = tk.Toplevel(top)
        win.title("Choose columns")
        win.transient(top)
        grab_when_viewable(win)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Show columns:").pack(anchor="w", pady=(0, 4))
        cvars: dict[str, tk.BooleanVar] = {}
        for c in self.COLS:
            var = tk.BooleanVar(value=c in self._visible_cols)
            cvars[c] = var
            ttk.Checkbutton(frm, text=self.HEADINGS[c],
                             variable=var).pack(anchor="w")

        def apply_() -> None:
            cols = [c for c in self.COLS if cvars[c].get()]
            if not cols:
                messagebox.showinfo("Choose columns",
                                      "Keep at least one column.")
                return
            self._visible_cols = cols
            self.tree["displaycolumns"] = tuple(cols)
            win.destroy()

        bar = ttk.Frame(frm)
        bar.pack(pady=(10, 0))
        ttk.Button(bar, text="Apply", command=apply_).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    # ── live quick-find + age filter (items 10, 15) ──────────────

    def _quick_search(self, _event: "tk.Event | None" = None) -> None:
        self._render()

    def _visible_rows(self) -> list[Applicant]:
        """``self._rows`` narrowed by the live quick-find and age range."""
        rows = list(self._rows)
        q = self.f_quick.get().strip().lower()
        if q:
            rows = [a for a in rows
                    if q in a.applicant_id.lower()
                    or q in a.full_name.lower()
                    or (a.email and q in a.email.lower())]
        lo = self._age_bound(self.f_age_min.get())
        hi = self._age_bound(self.f_age_max.get())
        if lo is not None or hi is not None:
            kept = []
            for a in rows:
                age = _compute_age(a.dob)
                if age is None:
                    continue
                if lo is not None and age < lo:
                    continue
                if hi is not None and age > hi:
                    continue
                kept.append(a)
            rows = kept
        return rows

    @staticmethod
    def _age_bound(text: str) -> int | None:
        text = (text or "").strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    # ── copy / follow-up (items 11, 14) ──────────────────────────

    def _copy_email_list(self) -> None:
        if not self._require_selection("Copy emails"):
            return
        emails = [a.email for a in self._selected_applicants()
                  if a.email and a.email.strip()]
        if not emails:
            messagebox.showinfo(
                "Copy emails",
                "None of the selected applicants have an email address.")
            return
        top = self.frame.winfo_toplevel()
        top.clipboard_clear()
        top.clipboard_append("; ".join(emails))
        messagebox.showinfo(
            "Copy emails",
            f"Copied {len(emails)} email address(es) to the clipboard.")

    def _toggle_follow_up(self) -> None:
        applicants = self._selected_applicants()
        if not applicants:
            messagebox.showinfo("Follow-up",
                                  "Select one or more applicants first.")
            return
        failures = []
        for a in applicants:
            try:
                data.set_follow_up(a.applicant_id, not a.follow_up)
            except Exception as e:  # noqa: BLE001 — collect & report per row
                failures.append(f"{a.applicant_id}: {e}")
        self.refresh()
        if failures:
            messagebox.showerror(
                "Follow-up", f"{len(failures)} failed:\n"
                + "\n".join(failures))

    # ── print / PDF export (items 12, 13) ────────────────────────

    def _export_selected_pdf(self) -> None:
        rows = self._selected_applicants() or self._visible_rows()
        if not rows:
            messagebox.showinfo("Export PDF", "No applicants to export.")
            return
        path = filedialog.asksaveasfilename(
            parent=self.frame.winfo_toplevel(), defaultextension=".pdf",
            initialfile="applicants.pdf", filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            self._write_pdf(path, rows)
        except Exception as e:  # noqa: BLE001 — surface, don't crash the GUI
            messagebox.showerror("Export PDF", f"Could not create PDF:\n{e}")
            return
        messagebox.showinfo("Export PDF",
                              f"Exported {len(rows)} applicant(s) to {path}")

    @staticmethod
    def _write_pdf(path: str, rows: list[Applicant]) -> None:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )

        styles = getSampleStyleSheet()
        cell = ParagraphStyle("cell", parent=styles["Normal"],
                              fontSize=8, leading=9)

        def P(text: str) -> "Paragraph":
            safe = (text or "—").replace("&", "&amp;").replace(
                "<", "&lt;").replace(">", "&gt;")
            return Paragraph(safe, cell)

        header = ["ID", "Name", "Age", "Status", "Offer", "Source",
                  "Subjects", "Interview"]
        table_rows: list[list] = [header]
        for a in rows:
            age = _compute_age(a.dob)
            table_rows.append([
                a.applicant_id, P(a.full_name),
                str(age) if age is not None else "—",
                P(a.status), a.offer_type or "—",
                P(a.application_source), P(", ".join(a.subjects)),
                a.interview_date or "—",
            ])
        widths = [2, 4, 1.2, 3.2, 2.6, 3, 7, 2.5]
        tbl = Table(table_rows, repeatRows=1,
                    colWidths=[w * cm for w in widths])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b63")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f0f4fa")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        doc = SimpleDocTemplate(
            path, pagesize=landscape(A4), leftMargin=1 * cm,
            rightMargin=1 * cm, topMargin=1 * cm, bottomMargin=1 * cm)
        doc.build([
            Paragraph(f"{branding.SYSTEM_NAME} — Admissions", styles["Title"]),
            Paragraph(f"{len(rows)} applicant(s) · generated {_today()}",
                      styles["Normal"]),
            Spacer(1, 8), tbl,
        ])

    def _print_list(self) -> None:
        rows = self._visible_rows()
        if not rows:
            messagebox.showinfo("Print", "Nothing to print.")
            return
        lines = [f"{branding.SYSTEM_NAME} — Admissions "
                 f"({len(rows)} applicants) — {_today()}", "",
                 f"{'ID':<8} {'Name':<22} {'Age':>3} {'Status':<18} "
                 f"{'Offer':<10} {'Source':<12} Subjects"]
        for a in rows:
            age = _compute_age(a.dob)
            lines.append(
                f"{a.applicant_id:<8} {a.full_name[:22]:<22} "
                f"{(str(age) if age is not None else '—'):>3} "
                f"{a.status:<18} {(a.offer_type or '—'):<10} "
                f"{a.application_source[:12]:<12} {', '.join(a.subjects)}")
        try:
            self._send_to_printer("\n".join(lines) + "\n")
        except Exception as e:  # noqa: BLE001 — surface, don't crash the GUI
            messagebox.showerror("Print", f"Could not print:\n{e}")
            return
        messagebox.showinfo(
            "Print",
            f"Sent {len(rows)} applicant(s) to the default printer.")

    def _gdpr_batch_export(self) -> None:
        ids = self._require_selection("GDPR export (batch)")
        if not ids:
            return
        path = filedialog.asksaveasfilename(
            parent=self.frame.winfo_toplevel(), defaultextension=".json",
            initialfile="gdpr_batch.json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        import json
        bundle, failures = {}, []
        for aid in ids:
            try:
                bundle[aid] = reports.gdpr_export(aid)
            except Exception as e:  # noqa: BLE001
                failures.append(f"{aid}: {e}")
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(bundle, fh, indent=2, default=str)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("GDPR export (batch)", str(e))
            return
        msg = f"Exported {len(bundle)} applicant bundle(s) to {path}"
        if failures:
            msg += "\n\nFailed:\n" + "\n".join(failures)
        messagebox.showinfo("GDPR export (batch)", msg)

    @staticmethod
    def _send_to_printer(text: str) -> None:
        import tempfile
        if os.name == "nt":
            fd, path = tempfile.mkstemp(suffix=".txt", text=True)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.startfile(path, "print")  # type: ignore[attr-defined]
            return
        proc = subprocess.run(["lpr"], input=text.encode("utf-8"),
                              stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                proc.stderr.decode("utf-8", "replace").strip()
                or f"lpr exited with status {proc.returncode}")


# Sibling names used only at call time; imported last so any import order works.
from .dialogs_actions import (  # noqa: E402
    AskChoiceDialog,
    DecisionDayDialog,
    OfferDialog,
    StatusDialog,
)
from .dialogs_detail import ApplicantDialog, DetailDialog  # noqa: E402
