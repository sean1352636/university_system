"""Scholarship Finder mixin - the finder pages the CLI has that the portal lacked.

Three pages over the scholarship-finder service (the same classes
``ScholarshipFinderCLI`` uses, so there is no second copy of the rules):

* ``show_scholarship_search`` - filtered search of ``scholarship_opportunities``
  (organisation type, academic level, major, minimum award, merit-only,
  deadline-after, sort order) with lookup-by-ID, details and start-application.
* ``show_application_tracker`` - the finder's own applications
  (``student_scholarship_applications``) filtered by status, with update-progress
  and submit. The portal's "My Applications" page reads the legacy
  ``scholarship_applications`` table, which is a different thing.
* ``show_award_history`` - finder applications that reached ``awarded``. The CLI
  still prints "coming soon" here; the data is already in the service.

Everything keys on ``self.student_id`` like the rest of the portal (the finder
tables carry a foreign key to ``students.student_id``, and foreign keys are on).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from education_system.platform.delivery.gui.form_dialog import Field, ask_form
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.university.domains.finance.interfaces.gui.financial_aid.common_imports import (
    clear_frame,
    create_data_table,
    format_date,
    tk,
    ttk,
)
from education_system.systems.university.infrastructure.i18n import get_text as _get_text

logger = logging.getLogger(__name__)

_ANY = "Any"
ORGANIZATION_TYPES = ["university", "government", "private", "corporate",
                      "foundation", "nonprofit", "community"]
ACADEMIC_LEVELS = ["freshman", "sophomore", "junior", "senior", "graduate"]
SORT_OPTIONS = {
    "Deadline (earliest first)": "deadline",
    "Award amount (highest first)": "amount",
    "Competition (lowest first)": "competition",
    "Most recent": "recent",
}
APPLICATION_STATUSES = ["draft", "in-progress", "submitted", "under-review",
                        "finalist", "awarded", "denied", "withdrawn"]
MAX_RESULTS = 200


def get_text(key: str, default: str, **kwargs: Any) -> str:
    """``get_text`` whose *default* is formatted too.

    The platform ``t()`` only formats a string it found in a locale file; a
    missing key returns the default verbatim, placeholders and all.
    """
    text = _get_text(key, default, **kwargs)
    if kwargs and "{" in text:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def _service():
    """The finder service module, imported on first use (it opens the DB)."""
    from education_system.systems.university.domains.finance.domain.scholarship_finder.services import (
        scholarship_service,
    )
    return scholarship_service


def _award_range(row: dict[str, Any]) -> str:
    text = f"£{row.get('award_amount_min') or 0:,.0f}"
    if row.get("award_amount_max"):
        text += f" - £{row['award_amount_max']:,.0f}"
    return text


def _yes_no(value: Any) -> str:
    return "Yes" if value else "No"


class ScholarshipFinderMixin:
    """Filtered search, finder application tracker and award history."""

    # ------------------------------------------------------------------ search

    def show_scholarship_search(self):
        """Search scholarship opportunities with the CLI's filters."""
        clear_frame(self.parent_frame)
        self._finder_title(get_text("financial_aid.student_portal.finder.search_title",
                                    "Search Scholarships"))
        self._build_search_filters()

        # Action bar packed before the expanding table, so it is always visible.
        actions = ttk.Frame(self.parent_frame)
        actions.pack(fill="x", padx=10, pady=5)
        ttk.Button(actions, text=get_text("financial_aid.student_portal.buttons.view_details", "View Details"),
                   command=self._finder_view_details).pack(side="left", padx=5)
        ttk.Button(actions, text=get_text("financial_aid.student_portal.buttons.start_application", "Start Application"),
                   command=self._finder_start_application, style="Success.TButton").pack(side="left", padx=5)
        ttk.Label(actions, text=get_text("financial_aid.student_portal.finder.lookup_id", "Scholarship ID:")).pack(side="left", padx=(20, 5))
        self.finder_lookup_var = tk.StringVar()
        ttk.Entry(actions, textvariable=self.finder_lookup_var, width=10).pack(side="left")
        ttk.Button(actions, text=get_text("financial_aid.student_portal.finder.lookup", "Look Up"),
                   command=self._finder_lookup_by_id).pack(side="left", padx=5)
        self.finder_count_var = tk.StringVar(value="")
        ttk.Label(actions, textvariable=self.finder_count_var).pack(side="right", padx=5)

        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        columns = ["ID", "Name", "Organisation", "Type", "Award", "Deadline", "Min GPA", "Competition"]
        self.finder_tree = create_data_table(table_frame, columns, {
            "ID": 60, "Name": 280, "Organisation": 180, "Type": 90,
            "Award": 130, "Deadline": 100, "Min GPA": 70, "Competition": 100,
        })
        self.finder_tree.bind("<Double-1>", lambda _e: self._finder_view_details())
        self._finder_rows: dict[str, dict[str, Any]] = {}
        self._run_scholarship_search()

    def _finder_title(self, title: str) -> None:
        frame = ttk.Frame(self.parent_frame)
        frame.pack(fill="x", padx=10, pady=10)
        ttk.Label(frame, text=title, style="Title.TLabel").pack(side="left")
        ttk.Button(frame, text=get_text("financial_aid.student_portal.buttons.back_to_dashboard", "Back to Dashboard"),
                   command=self.show_dashboard).pack(side="right")

    def _build_search_filters(self) -> None:
        box = ttk.LabelFrame(self.parent_frame, text=get_text("financial_aid.student_portal.finder.filters", "Filters"), padding=8)
        box.pack(fill="x", padx=10, pady=5)

        self.finder_org_var = tk.StringVar(value=_ANY)
        self.finder_level_var = tk.StringVar(value=_ANY)
        self.finder_major_var = tk.StringVar()
        self.finder_min_award_var = tk.StringVar()
        self.finder_merit_var = tk.BooleanVar(value=False)
        self.finder_deadline_var = tk.StringVar()
        self.finder_sort_var = tk.StringVar(value=next(iter(SORT_OPTIONS)))

        row1 = [
            ("Organisation:", ttk.Combobox(box, textvariable=self.finder_org_var, state="readonly",
                                           values=[_ANY] + ORGANIZATION_TYPES, width=14)),
            ("Level:", ttk.Combobox(box, textvariable=self.finder_level_var, state="readonly",
                                    values=[_ANY] + ACADEMIC_LEVELS, width=12)),
            ("Major:", ttk.Entry(box, textvariable=self.finder_major_var, width=18)),
            ("Min award £:", ttk.Entry(box, textvariable=self.finder_min_award_var, width=10)),
        ]
        row2 = [
            ("Deadline after (YYYY-MM-DD):", ttk.Entry(box, textvariable=self.finder_deadline_var, width=12)),
            ("Sort by:", ttk.Combobox(box, textvariable=self.finder_sort_var, state="readonly",
                                      values=list(SORT_OPTIONS), width=26)),
        ]
        for row, widgets in enumerate((row1, row2)):
            for col, (label, widget) in enumerate(widgets):
                ttk.Label(box, text=label).grid(row=row, column=col * 2, sticky="w", padx=(8, 2), pady=3)
                widget.grid(row=row, column=col * 2 + 1, sticky="w", padx=(0, 8), pady=3)
        ttk.Checkbutton(box, text=get_text("financial_aid.student_portal.finder.merit_only", "Merit-based only"),
                        variable=self.finder_merit_var).grid(row=1, column=4, columnspan=2, sticky="w", padx=8)
        ttk.Button(box, text=get_text("financial_aid.student_portal.buttons.search", "Search"),
                   command=self._run_scholarship_search).grid(row=1, column=6, padx=5)
        ttk.Button(box, text=get_text("financial_aid.student_portal.buttons.clear", "Clear"),
                   command=self._clear_search_filters).grid(row=1, column=7, padx=5)

    def _clear_search_filters(self) -> None:
        self.finder_org_var.set(_ANY)
        self.finder_level_var.set(_ANY)
        self.finder_major_var.set("")
        self.finder_min_award_var.set("")
        self.finder_merit_var.set(False)
        self.finder_deadline_var.set("")
        self.finder_sort_var.set(next(iter(SORT_OPTIONS)))
        self._run_scholarship_search()

    def _search_filters(self) -> dict[str, Any]:
        """The filter dict the service expects; same keys the CLI builds."""
        filters: dict[str, Any] = {}
        if self.finder_org_var.get() != _ANY:
            filters["organization_type"] = self.finder_org_var.get()
        if self.finder_level_var.get() != _ANY:
            filters["academic_level"] = self.finder_level_var.get()
        major = self.finder_major_var.get().strip()
        if major:
            filters["major"] = major
        min_award = self.finder_min_award_var.get().strip()
        if min_award:
            filters["min_award"] = float(min_award)
        if self.finder_merit_var.get():
            filters["merit_based"] = 1
        deadline = self.finder_deadline_var.get().strip()
        if deadline:
            datetime.strptime(deadline, "%Y-%m-%d")
            filters["deadline_after"] = deadline
        return filters

    def _run_scholarship_search(self) -> None:
        try:
            filters = self._search_filters()
        except ValueError:
            messagebox.showerror(get_text("financial_aid.student_portal.errors.title", "Error"),
                                 get_text("financial_aid.student_portal.finder.bad_filters",
                                          "Minimum award must be a number and the deadline YYYY-MM-DD."))
            return
        sort_by = SORT_OPTIONS.get(self.finder_sort_var.get(), "deadline")
        try:
            rows = _service().ScholarshipDatabase.search_scholarships(filters, sort_by)
        except Exception as exc:
            logger.error("Scholarship search failed: %s", exc)
            messagebox.showerror(get_text("financial_aid.student_portal.errors.title", "Error"),
                                 f"Search failed: {exc}")
            return
        self._fill_finder_tree(rows)

    def _fill_finder_tree(self, rows: list[dict[str, Any]]) -> None:
        self.finder_tree.delete(*self.finder_tree.get_children())
        self._finder_rows = {}
        for row in rows[:MAX_RESULTS]:
            iid = str(row["scholarship_id"])
            self._finder_rows[iid] = row
            self.finder_tree.insert("", "end", iid=iid, values=(
                row["scholarship_id"], row.get("scholarship_name", ""), row.get("organization", ""),
                row.get("organization_type", ""), _award_range(row),
                format_date(row.get("application_deadline")), row.get("min_gpa") or "",
                row.get("competition_level") or "",
            ))
        shown = min(len(rows), MAX_RESULTS)
        self.finder_count_var.set(get_text("financial_aid.student_portal.finder.result_count",
                                           "{shown} of {total} scholarships", shown=shown, total=len(rows)))

    def _finder_selected_id(self) -> int | None:
        selection = self.finder_tree.selection()
        if not selection:
            messagebox.showwarning(get_text("financial_aid.student_portal.warnings.selection_required_title", "Selection Required"),
                                   get_text("financial_aid.student_portal.warnings.select_scholarship_view",
                                            "Please select a scholarship to view details"))
            return None
        return int(selection[0])

    def _finder_view_details(self) -> None:
        scholarship_id = self._finder_selected_id()
        if scholarship_id is not None:
            self._show_scholarship_details_dialog(scholarship_id)

    def _finder_lookup_by_id(self) -> None:
        raw = self.finder_lookup_var.get().strip()
        if not raw.isdigit():
            messagebox.showwarning(get_text("financial_aid.student_portal.errors.title", "Error"),
                                   get_text("financial_aid.student_portal.finder.bad_id", "Enter a numeric scholarship ID."))
            return
        self._show_scholarship_details_dialog(int(raw))

    def _finder_start_application(self) -> None:
        scholarship_id = self._finder_selected_id()
        if scholarship_id is None:
            return
        name = self._finder_rows.get(str(scholarship_id), {}).get("scholarship_name", scholarship_id)
        if not messagebox.askyesno(get_text("financial_aid.student_portal.confirm", "Confirm"),
                                   get_text("financial_aid.student_portal.finder.confirm_start",
                                            "Start an application for {name}?", name=name)):
            return
        try:
            app_id = _service().ApplicationManager.start_application(self.student_id, scholarship_id)
        except Exception as exc:
            logger.error("Could not start application: %s", exc)
            messagebox.showerror(get_text("financial_aid.student_portal.errors.title", "Error"),
                                 get_text("financial_aid.student_portal.errors.failed_start_application",
                                          "Failed to start application: {error}", error=str(exc)))
            return
        messagebox.showinfo(get_text("financial_aid.student_portal.success.title", "Success"),
                            get_text("financial_aid.student_portal.success.application_started",
                                     "Application started! ID: {id}", id=app_id))
        self.show_application_tracker()

    # ------------------------------------------------------- application tracker

    def show_application_tracker(self):
        """The finder's applications, filtered by status, with progress + submit."""
        clear_frame(self.parent_frame)
        self._finder_title(get_text("financial_aid.student_portal.finder.tracker_title",
                                    "Scholarship Application Tracker"))

        controls = ttk.Frame(self.parent_frame)
        controls.pack(fill="x", padx=10, pady=5)
        ttk.Label(controls, text=get_text("financial_aid.student_portal.finder.status", "Status:")).pack(side="left", padx=5)
        self.tracker_status_var = tk.StringVar(value="All")
        ttk.Combobox(controls, textvariable=self.tracker_status_var, state="readonly",
                     values=["All"] + APPLICATION_STATUSES, width=14).pack(side="left")
        ttk.Button(controls, text=get_text("financial_aid.student_portal.buttons.refresh", "Refresh"),
                   command=self._load_finder_applications).pack(side="left", padx=10)

        actions = ttk.Frame(self.parent_frame)
        actions.pack(fill="x", padx=10, pady=5)
        ttk.Button(actions, text=get_text("financial_aid.student_portal.finder.update_progress", "Update Progress"),
                   command=self._update_finder_application).pack(side="left", padx=5)
        ttk.Button(actions, text=get_text("financial_aid.student_portal.buttons.submit_application", "Submit Application"),
                   command=self._submit_finder_application, style="Success.TButton").pack(side="left", padx=5)
        ttk.Button(actions, text=get_text("financial_aid.student_portal.finder.view_scholarship", "View Scholarship"),
                   command=self._tracker_view_scholarship).pack(side="left", padx=5)

        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        columns = ["App ID", "Scholarship", "Organisation", "Status", "Deadline",
                   "Progress", "Essay", "Transcript", "Documents", "Rec. Letters"]
        self.tracker_tree = create_data_table(table_frame, columns, {
            "App ID": 60, "Scholarship": 260, "Organisation": 160, "Status": 100,
            "Deadline": 100, "Progress": 80, "Essay": 60, "Transcript": 80,
            "Documents": 80, "Rec. Letters": 90,
        })
        self._tracker_rows: dict[str, dict[str, Any]] = {}
        self._load_finder_applications()

    def _load_finder_applications(self) -> None:
        status = self.tracker_status_var.get()
        try:
            rows = _service().ApplicationManager.get_student_applications(
                self.student_id, None if status == "All" else status)
        except Exception as exc:
            logger.error("Could not load finder applications: %s", exc)
            messagebox.showerror(get_text("financial_aid.student_portal.errors.title", "Error"),
                                 f"Failed to load applications: {exc}")
            return
        self.tracker_tree.delete(*self.tracker_tree.get_children())
        self._tracker_rows = {}
        for row in rows:
            iid = str(row["application_id"])
            self._tracker_rows[iid] = row
            self.tracker_tree.insert("", "end", iid=iid, values=(
                row["application_id"], row.get("scholarship_name", ""), row.get("organization", ""),
                (row.get("status") or "").upper(), row.get("deadline_date", ""),
                f"{row.get('application_progress') or 0:.0f}%",
                _yes_no(row.get("essay_completed")), _yes_no(row.get("transcript_uploaded")),
                _yes_no(row.get("documents_completed")),
                f"{row.get('recommendations_obtained') or 0}/{row.get('recommendations_required') or 0}",
            ), tags=(row.get("status") or "",))
        self.tracker_tree.tag_configure("awarded", background="#d4edda")
        self.tracker_tree.tag_configure("submitted", background="#e2e3e5")
        self.tracker_tree.tag_configure("denied", foreground="darkred")

    def _tracker_selected(self) -> dict[str, Any] | None:
        selection = self.tracker_tree.selection()
        if not selection:
            messagebox.showwarning(get_text("financial_aid.student_portal.warnings.selection_required_title", "Selection Required"),
                                   get_text("financial_aid.student_portal.finder.select_application",
                                            "Please select an application."))
            return None
        return self._tracker_rows.get(selection[0])

    def _tracker_view_scholarship(self) -> None:
        row = self._tracker_selected()
        if row is not None:
            self._show_scholarship_details_dialog(int(row["scholarship_id"]))

    def _update_finder_application(self) -> None:
        row = self._tracker_selected()
        if row is None:
            return
        values = ask_form(self.parent_frame.winfo_toplevel(),
                          get_text("financial_aid.student_portal.finder.update_progress", "Update Progress"), [
            Field("essay_completed", "Essay completed", kind="bool", default="1" if row.get("essay_completed") else "0"),
            Field("transcript_uploaded", "Transcript uploaded", kind="bool", default="1" if row.get("transcript_uploaded") else "0"),
            Field("documents_completed", "All documents completed", kind="bool", default="1" if row.get("documents_completed") else "0"),
            Field("recommendations_obtained", "Recommendation letters obtained", kind="int",
                  default=str(row.get("recommendations_obtained") or 0), optional=True),
            Field("notes", "Notes", kind="text", default=row.get("notes") or "", optional=True),
        ])
        if values is None:
            return
        updates = {key: int(values[key]) for key in ("essay_completed", "transcript_uploaded", "documents_completed")}
        if values.get("recommendations_obtained") is not None:
            updates["recommendations_obtained"] = values["recommendations_obtained"]
        if values.get("notes"):
            updates["notes"] = values["notes"]
        try:
            ok = _service().ApplicationManager.update_application_progress(row["application_id"], **updates)
        except Exception as exc:
            logger.error("Could not update application: %s", exc)
            messagebox.showerror(get_text("financial_aid.student_portal.errors.title", "Error"), f"Update failed: {exc}")
            return
        if ok:
            messagebox.showinfo(get_text("financial_aid.student_portal.success.title", "Success"),
                                get_text("financial_aid.student_portal.finder.updated", "Application updated."))
        self._load_finder_applications()

    def _submit_finder_application(self) -> None:
        row = self._tracker_selected()
        if row is None:
            return
        if not messagebox.askyesno(get_text("financial_aid.student_portal.confirm", "Confirm"),
                                   get_text("financial_aid.student_portal.finder.confirm_submit",
                                            "Submit this application? Make sure it is complete.")):
            return
        try:
            ok = _service().ApplicationManager.submit_application(row["application_id"])
        except Exception as exc:
            # ValidationError("Application is not complete") lands here: the service
            # refuses anything under 100% progress, which is the message to show.
            messagebox.showerror(get_text("financial_aid.student_portal.errors.title", "Error"), str(exc))
            return
        if ok:
            messagebox.showinfo(get_text("financial_aid.student_portal.success.title", "Success"),
                                get_text("financial_aid.student_portal.finder.submitted",
                                         "Application submitted. You will be notified of the outcome."))
        self._load_finder_applications()

    # ------------------------------------------------------------ award history

    def show_award_history(self):
        """Finder applications that reached 'awarded'."""
        clear_frame(self.parent_frame)
        self._finder_title(get_text("financial_aid.student_portal.finder.awards_title", "Scholarship Award History"))

        summary = ttk.LabelFrame(self.parent_frame, text=get_text("financial_aid.student_portal.award_summary", "Award Summary"), padding=10)
        summary.pack(fill="x", padx=10, pady=5)
        self.award_summary_var = tk.StringVar(value="")
        ttk.Label(summary, textvariable=self.award_summary_var, font=("Arial", 10)).pack(anchor="w")

        actions = ttk.Frame(self.parent_frame)
        actions.pack(fill="x", padx=10, pady=5)
        ttk.Button(actions, text=get_text("financial_aid.student_portal.buttons.refresh", "Refresh"),
                   command=self._load_award_history).pack(side="left", padx=5)
        ttk.Button(actions, text=get_text("financial_aid.student_portal.finder.view_scholarship", "View Scholarship"),
                   command=self._award_view_scholarship).pack(side="left", padx=5)

        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        columns = ["App ID", "Scholarship", "Organisation", "Award", "Notified", "Accepted", "Accepted On"]
        self.award_tree = create_data_table(table_frame, columns, {
            "App ID": 60, "Scholarship": 280, "Organisation": 180, "Award": 110,
            "Notified": 100, "Accepted": 80, "Accepted On": 100,
        })
        self._award_rows: dict[str, dict[str, Any]] = {}
        self._load_award_history()

    def _load_award_history(self) -> None:
        try:
            rows = _service().ApplicationManager.get_student_applications(self.student_id, "awarded")
        except Exception as exc:
            logger.error("Could not load award history: %s", exc)
            messagebox.showerror(get_text("financial_aid.student_portal.errors.title", "Error"),
                                 f"Failed to load award history: {exc}")
            return
        self.award_tree.delete(*self.award_tree.get_children())
        self._award_rows = {}
        total = 0.0
        for row in rows:
            iid = str(row["application_id"])
            self._award_rows[iid] = row
            amount = row.get("award_amount")
            total += float(amount or 0)
            self.award_tree.insert("", "end", iid=iid, values=(
                row["application_id"], row.get("scholarship_name", ""), row.get("organization", ""),
                f"£{amount:,.2f}" if amount is not None else _award_range(row),
                format_date(row.get("notification_date")) if row.get("notification_date") else "",
                _yes_no(row.get("award_accepted")),
                format_date(row.get("acceptance_date")) if row.get("acceptance_date") else "",
            ))
        self.award_summary_var.set(get_text("financial_aid.student_portal.finder.awards_summary",
                                            "Awards: {count}    Total awarded: £{total:,.2f}",
                                            count=len(rows), total=total))

    def _award_view_scholarship(self) -> None:
        selection = self.award_tree.selection()
        if not selection:
            messagebox.showwarning(get_text("financial_aid.student_portal.warnings.selection_required_title", "Selection Required"),
                                   get_text("financial_aid.student_portal.finder.select_award", "Please select an award."))
            return
        row = self._award_rows.get(selection[0])
        if row is not None:
            self._show_scholarship_details_dialog(int(row["scholarship_id"]))
