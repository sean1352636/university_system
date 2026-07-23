"""Tkinter views for Sixth Form Admissions.

Notebook with 4 tabs:
* Open Pipeline    — applicants still in process (filterable).
* All Applicants   — every applicant including terminal states.
* Interviews       — interview scheduling overview.
* Summary          — pipeline counts.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import subprocess
import sys
import tkinter as tk
from collections import Counter
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable
from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.students.admissions import (
    admissions as data,
)
from education_system.post_16.sixthform_system.modules.domain.students.admissions.admissions import (
    Applicant,
    DEFAULT_OFFER_TYPE,
    DEFAULT_SOURCE,
    DEFAULT_STATUS,
    DOCUMENT_TYPES,
    OFFER_TYPES,
    OPEN_STATUSES,
    RECOMMENDATIONS,
    REFERENCE_STATUSES,
    SOURCES,
    STATUSES,
    TERMINAL_STATUSES,
    ValidationError,
)

# Days an open applicant may sit in one stage before the row is flagged.
STALE_WARN_DAYS = 14
STALE_CRIT_DAYS = 30

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_admissions_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Admissions — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    ApplicantsTab(nb, open_only=True, label="Open Pipeline")
    all_tab = ApplicantsTab(nb, open_only=False, label="All Applicants")
    InterviewsTab(nb)
    OffersTab(nb)
    WaitlistTab(nb)
    TasksTab(nb)
    SummaryTab(nb, notebook=nb, drill_tab=all_tab)
    AnalyticsTab(nb)


def _today() -> str:
    return _dt.date.today().isoformat()


def _subject_options() -> list[str]:
    try:
        from education_system.post_16.sixthform_system.modules.domain.academics.subjects import (
            subjects as _subjects,
        )
        return [s.name for s in _subjects.list_subjects()]
    except Exception:
        return []


def _parse_date(value: str | None) -> _dt.date | None:
    """Best-effort parse of an ISO date (optionally with a time suffix)."""
    if not value:
        return None
    try:
        return _dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def _compute_age(dob: str | None) -> int | None:
    d = _parse_date(dob)
    if d is None:
        return None
    today = _dt.date.today()
    years = today.year - d.year - (
        (today.month, today.day) < (d.month, d.day))
    return years if 0 <= years < 130 else None


def _days_in_stage(applicant: Applicant) -> int | None:
    """Whole days since the applicant last changed (updated_at)."""
    d = _parse_date(applicant.updated_at)
    if d is None:
        return None
    return max(0, (_dt.date.today() - d).days)


def _prompt(parent: tk.Misc, title: str, text: str,
            initial: str = "") -> str | None:
    """Single-line text prompt; returns None on cancel."""
    return simpledialog.askstring(
        title, text, initialvalue=initial,
        parent=parent.winfo_toplevel())


def _open_path(path: str) -> None:
    """Open a file with the OS default handler."""
    try:
        if sys.platform.startswith("darwin"):
            subprocess.run(["open", path], check=False)
        elif os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception as e:  # noqa: BLE001 — surface, don't crash the GUI
        messagebox.showerror("Open file", f"Could not open file:\n{e}")


def _gcse_concerns(predicted: str | None, conditions: str | None) -> str | None:
    """Heuristic flag (delegates to the shared domain implementation)."""
    return data.gcse_concern(predicted, conditions)


# ── Sidecar JSON storage ──────────────────────────────────────────
# Small bits of GUI-only state (interview rooms, slot caps, saved views)
# live next to the admissions DB rather than in the schema.

def _sidecar_path(name: str) -> "Path":
    from pathlib import Path
    return Path(data.DB_PATH).parent / name


def _load_json(name: str, default):
    import json
    p = _sidecar_path(name)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a corrupt sidecar shouldn't break the GUI
        return default


def _store_json(name: str, obj) -> None:
    import json
    _sidecar_path(name).write_text(json.dumps(obj, indent=2), encoding="utf-8")


ROOMS_FILE = "admissions_interview_rooms.json"
CONFIG_FILE = "admissions_config.json"
DEFAULT_SLOT_CAP = 8

# Required document types for a complete applicant file (item 42).
REQUIRED_DOCS = ("Personal Statement", "Reference Letter", "Transcript")

# Rough probability that an applicant in a given open stage eventually
# enrols — feeds the pipeline forecast (item 34). Heuristic, tunable.
_ENROL_PROB = {
    "Submitted": 0.15,
    "Under Review": 0.25,
    "Interview Scheduled": 0.40,
    "Interviewed": 0.55,
    "Offer Made": 0.70,
    "Waitlisted": 0.20,
    "Offer Accepted": 0.95,
}


def _forecast_enrolment(applicants: list[Applicant]) -> dict:
    """Projected enrolments = already enrolled + expected from the pipeline."""
    enrolled = sum(1 for a in applicants if a.status == "Enrolled")
    expected = 0.0
    contributing = 0
    for a in applicants:
        p = _ENROL_PROB.get(a.status)
        if p:
            expected += p
            contributing += 1
    return {
        "enrolled": enrolled,
        "expected_additional": round(expected, 1),
        "projected_total": round(enrolled + expected),
        "in_pipeline": contributing,
    }


def _merge_ics(applicant_ids: list[str]) -> tuple[str, int]:
    """Combine each applicant's single-event calendar into one VCALENDAR."""
    events: list[str] = []
    for aid in applicant_ids:
        try:
            cal = data.interview_to_ics(aid)
        except Exception:  # noqa: BLE001 — skip applicants without an interview
            continue
        start = cal.find("BEGIN:VEVENT")
        end = cal.find("END:VEVENT")
        if start != -1 and end != -1:
            events.append(cal[start:end + len("END:VEVENT")])
    body = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0",
        "PRODID:-//SixthForm//Admissions//EN", *events, "END:VCALENDAR"])
    return body + "\r\n", len(events)


def _scaled(values: list[float], size: int) -> list[int]:
    """Scale values to pixel lengths in [0, size] against their own max."""
    top = max(values, default=0)
    return [int(round(size * v / top)) if top else 0 for v in values]


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
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())
        self.tree.bind("<Button-3>", self._popup_menu)
        self.tree.bind("<Button-2>", self._popup_menu)  # macOS
        self._build_menu()

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
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
                    command=lambda: self._quick_status(
                        "Offer Declined")).pack(side="left", padx=2)
        ttk.Button(actions, text="Reject",
                    command=lambda: self._quick_status(
                        "Rejected")).pack(side="left", padx=2)
        ttk.Button(actions, text="Convert",
                    command=self._convert_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

        tools = ttk.Frame(self.frame)
        tools.pack(fill="x", padx=8, pady=(0, 8))
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
        accepted = data.list_applicants(status="Offer Accepted")
        if not accepted:
            messagebox.showinfo("Bulk enrol",
                                  "No applicants in 'Offer Accepted'.")
            return
        if not messagebox.askyesno(
                "Bulk enrol",
                f"Attempt to enrol {len(accepted)} accepted applicant(s)?"):
            return
        done, failed = [], []
        for a in accepted:
            issues = data.pre_conversion_check(a.applicant_id)
            if issues:
                failed.append(f"{a.applicant_id}: {issues[0]}")
                continue
            try:
                _, sid = data.convert_to_student(a.applicant_id)
                done.append(f"{a.applicant_id} → {sid}")
            except Exception as e:  # noqa: BLE001
                failed.append(f"{a.applicant_id}: {e}")
        self.refresh()
        msg = (f"Enrolled {len(done)}:\n" + "\n".join(done)) if done else ""
        if failed:
            msg += ("\n\n" if msg else "") + "Skipped:\n" + "\n".join(failed)
        messagebox.showinfo("Bulk enrol", msg or "Nothing to do.")

    def _email_selected(self) -> None:
        aid = self._selected_id()
        if aid is None:
            messagebox.showinfo("Email", "Select an applicant first.")
            return
        EmailPreviewDialog(self.frame.winfo_toplevel(), aid)

    def _export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.frame.winfo_toplevel(), defaultextension=".csv",
            initialfile="applicants.csv",
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        n = data.export_csv(path, self._rows)
        messagebox.showinfo("Export CSV",
                              f"Exported {n} applicant(s) to {path}")

    def _import_csv(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.frame.winfo_toplevel(),
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        created, errors = data.import_csv(path)
        self.refresh()
        msg = f"Imported {created} applicant(s)."
        if errors:
            msg += f"\n\n{len(errors)} row(s) failed:\n" + "\n".join(
                errors[:12])
        messagebox.showinfo("Import CSV", msg)

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
        m.add_command(label="Decline offer",
                       command=lambda: self._quick_status("Offer Declined"))
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
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        subject = self.f_subject.get().strip()
        if subject:
            rows = [a for a in rows if subject in a.subjects]
        if self._preset is not None:
            rows = [a for a in rows if self._preset(a)]
        self._rows = rows
        self._render()

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
            self.tree.insert("", "end", iid=a.applicant_id, values=(
                a.applicant_id, a.full_name,
                age if age is not None else "—",
                a.submitted_at,
                days if days is not None else "—",
                a.status, a.offer_type or "—",
                a.application_source, ", ".join(a.subjects),
                a.interview_date or "—",
            ), tags=tags)
        self.count_var.set(self._count_summary(rows))

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
        # Pre-conversion checklist (items 37, 40).
        blocked = {aid: data.pre_conversion_check(aid) for aid in ids}
        ready = [aid for aid, iss in blocked.items() if not iss]
        not_ready = [(aid, iss) for aid, iss in blocked.items() if iss]
        lines = [f"Ready to enrol: {len(ready)} of {len(ids)}", ""]
        for aid in ready:
            lines.append(f"  ✓ {aid}")
        for aid, iss in not_ready:
            lines.append(f"  ✗ {aid}: {'; '.join(iss)}")
        if not ready:
            messagebox.showinfo("Convert to Student",
                                  "None are ready to enrol:\n\n"
                                  + "\n".join(lines))
            return
        if not messagebox.askyesno(
                "Convert to Student",
                "\n".join(lines) + f"\n\nEnrol the {len(ready)} ready "
                f"applicant(s)?"):
            return
        done, failures = [], [f"{aid}: {'; '.join(iss)}"
                              for aid, iss in not_ready]
        for aid in ready:
            try:
                _, sid = data.convert_to_student(aid)
                done.append(f"{aid} → {sid}")
            except Exception as e:  # noqa: BLE001 — collect & report per row
                failures.append(f"{aid}: {e}")
        self.refresh()
        msg = ""
        if done:
            msg += "Enrolled:\n" + "\n".join(done)
        if failures:
            msg += ("\n\n" if msg else "") + "Failed:\n" + "\n".join(failures)
        (messagebox.showwarning if failures else messagebox.showinfo)(
            "Convert", msg or "Nothing to convert.")

    def _delete_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Delete",
                                  "Select one or more applicants first.")
            return
        noun = (f"{len(ids)} applicants" if len(ids) > 1
                else f"applicant {ids[0]}")
        if not messagebox.askyesno(
                "Delete",
                f"Delete {noun}?\n"
                "If any are already enrolled, the student record "
                "is NOT removed — only the applicant audit row."):
            return
        failures = []
        for aid in ids:
            try:
                data.delete_applicant(aid)
            except Exception as e:  # noqa: BLE001 — collect & report per row
                failures.append(f"{aid}: {e}")
        self.refresh()
        if failures:
            messagebox.showerror(
                "Delete failed",
                f"{len(failures)} failed:\n" + "\n".join(failures))

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
                failures.append(f"{aid}: {e}")
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
        dlg = AskChoiceDialog(self.frame.winfo_toplevel(),
                              "Set status", "New status:", list(STATUSES))
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
            lambda aid: data.add_note(aid, body, author="admissions-gui"),
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
        sel = self._selected_applicants()
        if len(sel) == 1:
            a = sel[0]
            dupes = data.find_duplicates(
                email=a.email, first_name=a.first_name,
                last_name=a.last_name, dob=a.dob,
                exclude_id=a.applicant_id)
            if not dupes:
                messagebox.showinfo(
                    "Merge duplicates",
                    f"No potential duplicates found for {a.applicant_id}.")
                return
            labels = [f"{d.applicant_id} — {d.full_name} — "
                      f"{d.email or 'no email'}" for d in dupes]
            dlg = AskChoiceDialog(
                self.frame.winfo_toplevel(), "Merge duplicates",
                f"Merge which record into {a.applicant_id}?", labels)
            if not dlg.result:
                return
            self._do_merge(a, dupes[labels.index(dlg.result)])
            return
        if len(sel) == 2:
            primary, other = sel[0], sel[1]
            if not messagebox.askyesno(
                    "Merge duplicates",
                    f"Keep {primary.applicant_id} ({primary.full_name}) and "
                    f"merge {other.applicant_id} ({other.full_name}) into it?"
                    "\n\nBlank fields on the kept record are filled from the "
                    "other, notes are copied over, then the other record is "
                    "deleted."):
                return
            self._do_merge(primary, other)
            return
        messagebox.showinfo(
            "Merge duplicates",
            "Select one applicant to search for its duplicates, or exactly "
            "two applicants to merge the second into the first.")

    def _do_merge(self, primary: Applicant, other: Applicant) -> None:
        fields = ("dob", "email", "phone", "address", "previous_school",
                  "predicted_gcses", "subject_1", "subject_2", "subject_3",
                  "reference_name", "reference_contact")
        fill = {f: getattr(other, f) for f in fields
                if not getattr(primary, f) and getattr(other, f)}
        try:
            if fill:
                data.update_applicant(primary.applicant_id, fill)
            for note in reversed(data.list_notes(other.applicant_id)):
                data.add_note(
                    primary.applicant_id,
                    f"[merged from {other.applicant_id}] {note.body}",
                    author=note.author)
            data.add_note(
                primary.applicant_id,
                f"Merged duplicate {other.applicant_id} "
                f"({other.full_name}).", author="admissions-gui")
            data.delete_applicant(other.applicant_id)
        except Exception as e:  # noqa: BLE001 — surface, don't crash the GUI
            messagebox.showerror("Merge duplicates", f"Merge failed:\n{e}")
            return
        self.refresh()
        messagebox.showinfo(
            "Merge duplicates",
            f"Merged {other.applicant_id} into {primary.applicant_id} "
            f"({len(fill)} field(s) filled).")

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
        win.after_idle(win.grab_set)
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
        win.after_idle(win.grab_set)
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
                bundle[aid] = data.gdpr_export(aid)
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


# ══ Interviews tab ════════════════════════════════════════════════

class InterviewsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Interviews")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="From:").pack(side="left")
        self.from_e = ttk.Entry(bar, width=12)
        self.from_e.insert(0, _today())
        self.from_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="To:").pack(side="left")
        self.to_e = ttk.Entry(bar, width=12)
        plus = (_dt.date.today() + _dt.timedelta(days=30)).isoformat()
        self.to_e.insert(0, plus)
        self.to_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Next 7",
                    command=lambda: self._preset(7)
                    ).pack(side="left", padx=2)
        ttk.Button(bar, text="Next 30",
                    command=lambda: self._preset(30)
                    ).pack(side="left", padx=2)
        self.agenda_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Agenda view", variable=self.agenda_var,
                         command=self.refresh).pack(side="left", padx=8)
        ttk.Button(bar, text="Schedule…",
                    command=self._schedule).pack(side="left", padx=4)
        ttk.Button(bar, text="Record outcome…",
                    command=self._record_outcome).pack(side="left", padx=4)
        ttk.Button(bar, text="Reschedule…",
                    command=self._reschedule).pack(side="left", padx=2)
        ttk.Button(bar, text="Cancel…",
                    command=self._cancel).pack(side="left", padx=2)
        ttk.Button(bar, text="No-show",
                    command=self._no_show).pack(side="left", padx=2)
        ttk.Button(bar, text="Export .ics",
                    command=self._export_ics).pack(side="left", padx=2)

        # Extra scheduling tools (items 16–25).
        tools_mb = ttk.Menubutton(bar, text="Tools ▾")
        tmenu = tk.Menu(tools_mb, tearoff=0)
        tmenu.add_command(label="Calendar (month)…",
                           command=self._calendar_view)
        tmenu.add_command(label="Panel view (by interviewer)…",
                           command=self._panel_view)
        tmenu.add_command(label="Slot capacity…", command=self._slot_capacity)
        tmenu.add_separator()
        tmenu.add_command(label="Bulk schedule…", command=self._bulk_schedule)
        tmenu.add_command(label="Reschedule a whole day…",
                           command=self._reschedule_batch)
        tmenu.add_command(label="Assign room…", command=self._room_assignment)
        tmenu.add_separator()
        tmenu.add_command(label="Send reminders…", command=self._send_reminders)
        tmenu.add_command(label="Detect clashes", command=self._detect_clashes)
        tmenu.add_command(label="No-show report…", command=self._no_show_report)
        tmenu.add_command(label="Export all .ics…", command=self._export_all_ics)
        tools_mb["menu"] = tmenu
        tools_mb.pack(side="left", padx=(8, 2))

        body = ttk.Frame(self.frame)
        body.pack(fill="both", expand=True, padx=8, pady=4)
        table_frame = ttk.Frame(body)
        table_frame.pack(side="left", fill="both", expand=True)
        # #0 (tree column) shows date-group headers in agenda mode.
        cols = ("id", "name", "interviewer", "status", "subjects")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                  show="tree headings")
        self.tree.heading("#0", text="Date")
        self.tree.column("#0", width=150, anchor="w")
        widths = {"id": 80, "name": 180,
                  "interviewer": 150, "status": 150, "subjects": 260}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("done", background="#eeeeee")
        self.tree.tag_configure("clash", background="#ffd0d0")
        self.tree.tag_configure("group",
                                 font=("TkDefaultFont", 10, "bold"))

        # Interviewer workload panel (item 22).
        side = ttk.LabelFrame(body, text="Interviewer load")
        side.pack(side="right", fill="y", padx=(8, 0))
        self.load_tree = ttk.Treeview(side, columns=("n",), show="tree",
                                       height=18, selectmode="none")
        self.load_tree.column("#0", width=150, anchor="w")
        self.load_tree.pack(fill="both", expand=True, padx=4, pady=4)

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def _preset(self, days: int) -> None:
        today = _dt.date.today()
        self.from_e.delete(0, "end")
        self.from_e.insert(0, today.isoformat())
        self.to_e.delete(0, "end")
        self.to_e.insert(0,
                          (today + _dt.timedelta(days=days)).isoformat())
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        df = self.from_e.get().strip()
        dt = self.to_e.get().strip()
        rows = [a for a in data.list_applicants() if a.interview_date]
        rows = [a for a in rows
                 if (not df or a.interview_date >= df)
                 and (not dt or a.interview_date <= dt)]
        rows.sort(key=lambda a: (a.interview_date or "",
                                  a.interviewer or "", a.full_name))
        today = _today()
        # Detect clashes: same interviewer booked twice on the same day.
        slot_counts = Counter(
            (a.interview_date, a.interviewer)
            for a in rows if a.interviewer)
        clashes = {k for k, n in slot_counts.items() if n > 1}

        agenda = self.agenda_var.get()
        clash_n = 0
        current_group = None
        for a in rows:
            tags: tuple[str, ...] = ()
            if a.interview_date and a.interview_date < today:
                tags += ("done",)
            is_clash = (a.interview_date, a.interviewer) in clashes
            if is_clash:
                tags += ("clash",)
                clash_n += 1
            parent = ""
            if agenda:
                if a.interview_date != current_group:
                    current_group = a.interview_date
                    parent = self.tree.insert(
                        "", "end", text=a.interview_date or "—",
                        open=True, tags=("group",))
                    self._last_group = parent
                parent = self._last_group
            self.tree.insert(
                parent, "end", iid=a.applicant_id,
                text="" if agenda else (a.interview_date or "—"),
                values=(a.applicant_id, a.full_name,
                        a.interviewer or "—", a.status,
                        ", ".join(a.subjects)),
                tags=tags)

        # Workload panel.
        for i in self.load_tree.get_children():
            self.load_tree.delete(i)
        load = Counter(a.interviewer or "(unassigned)" for a in rows)
        for who, n in sorted(load.items(), key=lambda kv: (-kv[1], kv[0])):
            self.load_tree.insert("", "end", text=f"{who}: {n}")

        msg = f"{len(rows)} interview(s) between {df} and {dt}."
        if clash_n:
            msg += f"  ⚠ {clash_n} in clashing slots."
        self.count_var.set(msg)

    def _selected_applicant(self) -> Applicant | None:
        sel = self.tree.selection()
        if not sel:
            return None
        # Group header rows are not valid applicant ids.
        return data.get_applicant(sel[0])

    def _schedule(self) -> None:
        rows = data.list_applicants(open_only=True)
        if not rows:
            messagebox.showinfo("Schedule",
                                  "No open applicants.")
            return
        ScheduleDialog(self.frame.winfo_toplevel(), rows,
                          on_save=self.refresh)

    def _record_outcome(self) -> None:
        a = self._selected_applicant()
        if a is None:
            messagebox.showinfo(
                "Record outcome",
                "Select a scheduled interview row first.")
            return
        RecordOutcomeDialog(self.frame.winfo_toplevel(), a,
                            on_save=self.refresh)

    def _reschedule(self) -> None:
        a = self._selected_applicant()
        if a is None:
            messagebox.showinfo("Reschedule", "Select an interview row.")
            return
        date = _prompt(self.frame, "Reschedule",
                       "New interview date (YYYY-MM-DD):",
                       a.interview_date or _today())
        if not date:
            return
        reason = _prompt(self.frame, "Reschedule", "Reason (optional):", "")
        try:
            data.reschedule_interview(a.applicant_id, new_date=date,
                                       reason=reason or None,
                                       interviewer=a.interviewer)
        except ValidationError as e:
            messagebox.showerror("Reschedule", str(e))
            return
        self.refresh()

    def _cancel(self) -> None:
        a = self._selected_applicant()
        if a is None:
            messagebox.showinfo("Cancel", "Select an interview row.")
            return
        if not messagebox.askyesno(
                "Cancel interview",
                f"Cancel {a.full_name}'s interview and return them to "
                f"'Under Review'?"):
            return
        reason = _prompt(self.frame, "Cancel", "Reason (optional):", "")
        data.cancel_interview(a.applicant_id, reason=reason or None)
        self.refresh()

    def _no_show(self) -> None:
        a = self._selected_applicant()
        if a is None:
            messagebox.showinfo("No-show", "Select an interview row.")
            return
        if not messagebox.askyesno(
                "No-show",
                f"Record {a.full_name} as a no-show and flag for follow-up?"):
            return
        data.mark_no_show(a.applicant_id, follow_up=True)
        self.refresh()

    def _export_ics(self) -> None:
        a = self._selected_applicant()
        if a is None or not a.interview_date:
            messagebox.showinfo("Export .ics",
                                  "Select a row with a scheduled interview.")
            return
        path = filedialog.asksaveasfilename(
            parent=self.frame.winfo_toplevel(), defaultextension=".ics",
            initialfile=f"interview_{a.applicant_id}.ics",
            filetypes=[("Calendar", "*.ics")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(data.interview_to_ics(a.applicant_id))
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Export .ics", str(e))
            return
        messagebox.showinfo("Export .ics", f"Saved to {path}")

    # ── shared helpers ───────────────────────────────────────────

    def _range(self) -> tuple[str, str]:
        return self.from_e.get().strip(), self.to_e.get().strip()

    def _range_rows(self) -> list[Applicant]:
        df, dt = self._range()
        rows = [a for a in data.list_applicants() if a.interview_date]
        return sorted(
            (a for a in rows
             if (not df or a.interview_date >= df)
             and (not dt or a.interview_date <= dt)),
            key=lambda a: (a.interview_date or "", a.interviewer or "",
                           a.full_name))

    # ── calendar / panel / capacity (items 16, 22, 25) ──────────

    def _calendar_view(self) -> None:
        rows = self._range_rows()
        counts = Counter(a.interview_date[:10] for a in rows
                         if a.interview_date)
        anchor = _parse_date(self.from_e.get().strip()) or _dt.date.today()
        top = self.frame.winfo_toplevel()
        win = tk.Toplevel(top)
        win.title(f"Interview calendar — {anchor:%B %Y}")
        win.transient(top)
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"{anchor:%B %Y}",
                   font=("TkDefaultFont", 12, "bold")).grid(
            row=0, column=0, columnspan=7, pady=(0, 6))
        import calendar
        for c, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri",
                                    "Sat", "Sun")):
            ttk.Label(frm, text=name, width=10, anchor="center").grid(
                row=1, column=c, padx=1, pady=1)
        cal = calendar.Calendar(firstweekday=0)
        for r, week in enumerate(cal.monthdatescalendar(anchor.year,
                                                          anchor.month),
                                  start=2):
            for c, day in enumerate(week):
                n = counts.get(day.isoformat(), 0)
                muted = day.month != anchor.month
                cell = ttk.Label(
                    frm, relief="solid", borderwidth=1, anchor="nw",
                    width=10, justify="left",
                    text=f"{day.day}\n{('● ' + str(n)) if n else ''}",
                    foreground="#999" if muted else (
                        "#b00000" if n else "#333"))
                cell.grid(row=r, column=c, padx=1, pady=1, sticky="nsew",
                          ipady=8)
        ttk.Button(frm, text="Close", command=win.destroy).grid(
            row=99, column=6, pady=(8, 0), sticky="e")

    def _panel_view(self) -> None:
        rows = self._range_rows()
        by_who: dict[str, list[Applicant]] = {}
        for a in rows:
            by_who.setdefault(a.interviewer or "(unassigned)", []).append(a)
        top = self.frame.winfo_toplevel()
        win = tk.Toplevel(top)
        win.title("Interview panels")
        win.transient(top)
        tree = ttk.Treeview(win, show="tree", height=22)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for who in sorted(by_who):
            group = tree.insert("", "end",
                                 text=f"{who}  ({len(by_who[who])})",
                                 open=True)
            for a in by_who[who]:
                tree.insert(group, "end",
                             text=f"{a.interview_date or '—'}  ·  "
                                  f"{a.applicant_id}  {a.full_name}  "
                                  f"[{a.status}]")

    def _slot_capacity(self) -> None:
        cap = int(_load_json(CONFIG_FILE, {}).get(
            "daily_slot_cap", DEFAULT_SLOT_CAP))
        new = simpledialog.askinteger(
            "Slot capacity", "Interview slots available per day:",
            parent=self.frame.winfo_toplevel(), initialvalue=cap,
            minvalue=1, maxvalue=100)
        if new is not None and new != cap:
            cfg = _load_json(CONFIG_FILE, {})
            cfg["daily_slot_cap"] = new
            _store_json(CONFIG_FILE, cfg)
            cap = new
        counts = Counter(a.interview_date[:10] for a in self._range_rows()
                         if a.interview_date)
        lines = [f"Daily cap: {cap} slot(s)", ""]
        for day in sorted(counts):
            used = counts[day]
            free = cap - used
            flag = "  ⚠ OVER" if free < 0 else ""
            lines.append(f"  {day}   used {used:>2}  free {free:>3}{flag}")
        if not counts:
            lines.append("  (no interviews scheduled in range)")
        TextViewerDialog(self.frame.winfo_toplevel(),
                          "Slot capacity", "\n".join(lines))

    # ── bulk scheduling (items 17, 24) ──────────────────────────

    def _bulk_schedule(self) -> None:
        pool = data.list_applicants(status="Under Review") + \
            data.list_applicants(status="Submitted")
        if not pool:
            messagebox.showinfo(
                "Bulk schedule",
                "No applicants in 'Submitted' or 'Under Review' to schedule.")
            return
        start = _prompt(self.frame, "Bulk schedule",
                        f"Schedule {len(pool)} applicant(s) starting from "
                        f"date (YYYY-MM-DD):", _today())
        if not start:
            return
        start_d = _parse_date(start)
        if start_d is None:
            messagebox.showerror("Bulk schedule", "Invalid start date.")
            return
        per_day = simpledialog.askinteger(
            "Bulk schedule", "Interviews per day:",
            parent=self.frame.winfo_toplevel(), initialvalue=DEFAULT_SLOT_CAP,
            minvalue=1, maxvalue=50)
        if not per_day:
            return
        who = _prompt(self.frame, "Bulk schedule",
                      "Interviewer for all (blank = leave unset):", "")
        if who is None:
            return
        if not messagebox.askyesno(
                "Bulk schedule",
                f"Schedule {len(pool)} applicant(s), {per_day} per day, "
                f"from {start_d.isoformat()}?"):
            return
        failures = []
        for i, a in enumerate(pool):
            day = start_d + _dt.timedelta(days=i // per_day)
            try:
                data.schedule_interview(
                    a.applicant_id, interview_date=day.isoformat(),
                    interviewer=who.strip() or None)
            except Exception as e:  # noqa: BLE001
                failures.append(f"{a.applicant_id}: {e}")
        self.refresh()
        msg = f"Scheduled {len(pool) - len(failures)} of {len(pool)}."
        if failures:
            msg += "\n\nFailed:\n" + "\n".join(failures[:12])
        messagebox.showinfo("Bulk schedule", msg)

    def _reschedule_batch(self) -> None:
        day = _prompt(self.frame, "Reschedule a whole day",
                      "Which interview date to shift (YYYY-MM-DD)?", _today())
        if not day:
            return
        affected = [a for a in self._range_rows()
                    if a.interview_date and a.interview_date[:10] == day[:10]]
        if not affected:
            messagebox.showinfo("Reschedule a whole day",
                                  f"No interviews found on {day}.")
            return
        shift = simpledialog.askinteger(
            "Reschedule a whole day",
            f"Shift all {len(affected)} interview(s) by how many days?",
            parent=self.frame.winfo_toplevel(), initialvalue=1)
        if not shift:
            return
        base = _parse_date(day)
        new_day = (base + _dt.timedelta(days=shift)).isoformat()
        failures = []
        for a in affected:
            try:
                data.reschedule_interview(
                    a.applicant_id, new_date=new_day,
                    reason=f"Day moved {shift:+d}d", interviewer=a.interviewer)
            except Exception as e:  # noqa: BLE001
                failures.append(f"{a.applicant_id}: {e}")
        self.refresh()
        messagebox.showinfo(
            "Reschedule a whole day",
            f"Moved {len(affected) - len(failures)} interview(s) to "
            f"{new_day}." + ("\n\nFailed:\n" + "\n".join(failures)
                             if failures else ""))

    # ── rooms (item 21) ─────────────────────────────────────────

    def _room_assignment(self) -> None:
        a = self._selected_applicant()
        if a is None:
            messagebox.showinfo("Assign room", "Select an interview row.")
            return
        rooms = _load_json(ROOMS_FILE, {})
        current = rooms.get(a.applicant_id, "")
        room = _prompt(self.frame, "Assign room",
                       f"Room for {a.full_name}'s interview "
                       f"({a.interview_date or 'unscheduled'}):", current)
        if room is None:
            return
        room = room.strip()
        if room:
            rooms[a.applicant_id] = room
        else:
            rooms.pop(a.applicant_id, None)
        _store_json(ROOMS_FILE, rooms)
        messagebox.showinfo(
            "Assign room",
            f"Room for {a.applicant_id} set to '{room}'." if room
            else f"Room for {a.applicant_id} cleared.")

    # ── reminders / clashes / reports / bulk ics (18, 19, 20, 23) ─

    def _send_reminders(self) -> None:
        target = _prompt(
            self.frame, "Send reminders",
            "Send interview reminders for which date (YYYY-MM-DD)?",
            (_dt.date.today() + _dt.timedelta(days=1)).isoformat())
        if not target:
            return
        rooms = _load_json(ROOMS_FILE, {})
        due = [a for a in self._range_rows()
               if a.interview_date and a.interview_date[:10] == target[:10]]
        if not due:
            messagebox.showinfo("Send reminders",
                                  f"No interviews scheduled on {target}.")
            return
        lines = [f"Interview reminders for {target} "
                 f"({len(due)} applicant(s))", "=" * 52, ""]
        for a in due:
            room = rooms.get(a.applicant_id, "TBC")
            lines += [
                f"To: {a.email or '(no email on file)'}",
                f"Subject: Your sixth-form interview on {a.interview_date}",
                "",
                f"Dear {a.first_name},",
                "",
                f"This is a reminder of your interview on "
                f"{a.interview_date}. Interviewer: "
                f"{a.interviewer or 'TBC'}. Room: {room}.",
                "",
                "Please arrive 10 minutes early with your ID.",
                "",
                "-" * 52, ""]
        TextViewerDialog(
            self.frame.winfo_toplevel(),
            f"Reminders — {target}", "\n".join(lines),
            save_name=f"reminders_{target}.txt")

    def _detect_clashes(self) -> None:
        rows = self._range_rows()
        slots = Counter((a.interview_date, a.interviewer)
                        for a in rows if a.interviewer)
        clashes = {k for k, n in slots.items() if n > 1}
        if not clashes:
            messagebox.showinfo("Detect clashes",
                                  "No interviewer double-bookings in range.")
            return
        lines = ["Interviewer double-bookings:", ""]
        for (date, who) in sorted(clashes):
            who_rows = [a for a in rows
                        if a.interview_date == date and a.interviewer == who]
            lines.append(f"  {date}  {who}  ×{len(who_rows)}: "
                         + ", ".join(x.applicant_id for x in who_rows))
        TextViewerDialog(self.frame.winfo_toplevel(),
                          "Clashes", "\n".join(lines))

    def _no_show_report(self) -> None:
        flagged = [a for a in data.list_applicants() if a.follow_up]
        lines = [f"Follow-up / no-show list ({len(flagged)} applicant(s))",
                 "=" * 52, ""]
        for a in flagged:
            lines.append(f"  {a.applicant_id}  {a.full_name:<24} "
                         f"[{a.status}]  interview: "
                         f"{a.interview_date or '—'}  "
                         f"{a.email or ''}")
        if not flagged:
            lines.append("  (nobody currently flagged for follow-up)")
        TextViewerDialog(self.frame.winfo_toplevel(),
                          "No-show / follow-up report", "\n".join(lines),
                          save_name="follow_up_report.txt")

    def _export_all_ics(self) -> None:
        rows = self._range_rows()
        if not rows:
            messagebox.showinfo("Export all .ics",
                                  "No interviews in the current range.")
            return
        path = filedialog.asksaveasfilename(
            parent=self.frame.winfo_toplevel(), defaultextension=".ics",
            initialfile="interviews.ics", filetypes=[("Calendar", "*.ics")])
        if not path:
            return
        body, n = _merge_ics([a.applicant_id for a in rows])
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Export all .ics", str(e))
            return
        messagebox.showinfo("Export all .ics",
                              f"Wrote {n} interview event(s) to {path}")


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook, *,
                 notebook: ttk.Notebook | None = None,
                 drill_tab: "ApplicantsTab | None" = None) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._notebook = notebook
        self._drill_tab = drill_tab
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Upcoming interview window (days):").pack(
            side="left")
        self.window_e = ttk.Entry(bar, width=6)
        self.window_e.insert(0, "14")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left")

        # Drill-down jump buttons (item 46).
        drill = ttk.Frame(self.frame)
        drill.pack(fill="x", padx=8, pady=(0, 4))
        if self._drill_tab is not None:
            ttk.Label(drill, text="Jump to:").pack(side="left")
            for label, status in (("Awaiting interview", "Under Review"),
                                    ("Interviewed", "Interviewed"),
                                    ("Offers made", "Offer Made"),
                                    ("Accepted", "Offer Accepted"),
                                    ("Enrolled", "Enrolled")):
                ttk.Button(drill, text=label,
                            command=lambda s=status: self._drill(s)).pack(
                    side="left", padx=2)

        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")

    def _drill(self, status: str) -> None:
        tab = self._drill_tab
        if tab is None:
            return
        tab._preset = None
        tab._reset_filters()
        tab.f_status.set(status)
        tab.refresh()
        if self._notebook is not None:
            self._notebook.select(tab.frame)

    def refresh(self) -> None:
        try:
            win = int(self.window_e.get().strip() or "14")
        except ValueError:
            messagebox.showerror("Summary", "Window must be a number.")
            return
        summ = data.summary(upcoming_window_days=win)
        lines = [
            f"Total applicants     : {summ.total}",
            f"Open                 : {summ.open_count}",
            f"Awaiting decision    : {summ.awaiting_decision}",
            f"Pending offers       : {summ.pending_offers}",
            f"Converted to student : {summ.converted}",
            f"Rejected             : {summ.rejected}",
            f"Upcoming interviews  : {summ.upcoming_interviews}  "
            f"(next {win} days)",
        ]
        expiring = data.list_expiring_offers(within_days=win)
        if expiring:
            lines.append(f"⚠ Offers expiring ≤{win}d : {len(expiring)}  "
                         + ", ".join(f"{a.applicant_id}({a.offer_expiry})"
                                     for a in expiring[:6]))
        lines += [
            "",
            "═ Conversion funnel ═══════════════════ (item 41)",
        ]
        fn = data.funnel()
        top = fn[0][1] if fn else 0
        for stage, n in fn:
            bar_w = int(round(40 * n / top)) if top else 0
            pct = f"{round(100 * n / top)}%" if top else "—"
            lines.append(f"  {stage:<20} {n:>4}  {pct:>4} "
                         f"{'█' * bar_w}")

        lines += ["", "═ Source effectiveness ════════════════ (item 42)",
                  f"  {'Source':<18}{'Total':>6}{'Offers':>8}"
                  f"{'Enrolled':>10}{'Conv%':>8}"]
        for d in data.source_effectiveness():
            lines.append(f"  {d['source']:<18}{d['total']:>6}"
                         f"{d['offers']:>8}{d['enrolled']:>10}"
                         f"{d['conversion']:>7}%")

        ttd = data.time_to_decision_stats()
        lines += ["", "═ Time to decision (days) ═════════════ (item 43)"]
        if ttd["count"]:
            lines.append(f"  n={ttd['count']}  avg={ttd['avg']}  "
                         f"median={ttd['median']}  min={ttd['min']}  "
                         f"max={ttd['max']}")
        else:
            lines.append("  (no decisions recorded yet)")

        lines += ["", "═ Applications by week ════════════════ (item 44)"]
        weeks = data.applications_by_week()[-10:]
        wmax = max((n for _, n in weeks), default=0)
        for wk, n in weeks:
            bar_w = int(round(30 * n / wmax)) if wmax else 0
            lines.append(f"  {wk:<10} {n:>4} {'█' * bar_w}")
        if not weeks:
            lines.append("  (no applications)")

        lines += ["", "═ Subject demand ═════════════════════ (item 45)"]
        for subj, n in data.subject_demand()[:15]:
            lines.append(f"  {subj:<28} {n:>4}")
        if not data.subject_demand():
            lines.append("  (no subject choices recorded)")

        lines += ["", "═ By status ═══════════════════════════"]
        for s in STATUSES:
            lines.append(f"  {s:<22} : {summ.by_status.get(s, 0)}")

        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Analytics tab ══════════════════════════════════════════════════

class AnalyticsTab:
    """Visual dashboard — KPI tiles plus canvas charts (items 26–35)."""

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Analytics")
        self._auto_job: str | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.v_auto = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Auto-refresh (30s)",
                         variable=self.v_auto,
                         command=self._refresh_auto).pack(side="left", padx=8)
        ttk.Button(bar, text="Cohort compare…",
                    command=self._cohort_compare).pack(side="left", padx=4)
        ttk.Button(bar, text="Export summary PDF…",
                    command=self._export_summary_pdf).pack(side="left", padx=4)

        # KPI tile row (items 30, 31, 34).
        kpi = ttk.Frame(self.frame)
        kpi.pack(fill="x", padx=8, pady=(2, 6))
        self.kpi_vars: dict[str, tk.StringVar] = {}
        for key, title in (("conversion", "Offer→Enrol conversion"),
                            ("ttd", "Time to decision"),
                            ("forecast", "Projected enrolment")):
            lf = ttk.LabelFrame(kpi, text=title)
            lf.pack(side="left", fill="x", expand=True, padx=4)
            var = tk.StringVar(value="—")
            self.kpi_vars[key] = var
            ttk.Label(lf, textvariable=var, justify="center",
                       font=("TkDefaultFont", 11, "bold")).pack(
                padx=10, pady=8)

        grid = ttk.Frame(self.frame)
        grid.pack(fill="both", expand=True, padx=8, pady=4)
        self.canvases: dict[str, tk.Canvas] = {}
        specs = (("funnel", "Conversion funnel", 0, 0),
                 ("source", "Source conversion %", 0, 1),
                 ("weekly", "Applications by week", 1, 0),
                 ("subjects", "Subject demand", 1, 1))
        for key, title, r, c in specs:
            cell = ttk.LabelFrame(grid, text=title)
            cell.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)
            cv = tk.Canvas(cell, width=380, height=210,
                           highlightthickness=0, background="white")
            cv.pack(fill="both", expand=True, padx=4, pady=4)
            self.canvases[key] = cv
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

    # ── refresh + KPIs ──────────────────────────────────────────

    def refresh(self) -> None:
        apps = data.list_applicants()
        self._conversion_kpi(apps)
        self._time_to_decision_card()
        self._forecast_card(apps)
        self._funnel_chart()
        self._source_chart()
        self._weekly_trend()
        self._subject_demand_chart()

    def _conversion_kpi(self, apps: list[Applicant]) -> None:
        enrolled = sum(1 for a in apps if a.status == "Enrolled")
        offers = sum(1 for a in apps
                     if a.offer_type and a.offer_type != "Not Offered")
        pct = round(100 * enrolled / offers) if offers else 0
        self.kpi_vars["conversion"].set(
            f"{pct}%\n{enrolled} enrolled / {offers} offers")

    def _time_to_decision_card(self) -> None:
        ttd = data.time_to_decision_stats()
        if ttd["count"]:
            self.kpi_vars["ttd"].set(
                f"avg {ttd['avg']}d · median {ttd['median']}d\n"
                f"n={ttd['count']} (min {ttd['min']} / max {ttd['max']})")
        else:
            self.kpi_vars["ttd"].set("no decisions yet")

    def _forecast_card(self, apps: list[Applicant]) -> None:
        f = _forecast_enrolment(apps)
        self.kpi_vars["forecast"].set(
            f"~{f['projected_total']}\n{f['enrolled']} now "
            f"+ {f['expected_additional']} expected")

    # ── charts (items 26–29) ────────────────────────────────────

    def _funnel_chart(self) -> None:
        self._hbars(self.canvases["funnel"], data.funnel(), color="#2f6fb0")

    def _source_chart(self) -> None:
        pairs = [(d["source"], d["conversion"])
                 for d in data.source_effectiveness()]
        self._hbars(self.canvases["source"], pairs, color="#2e8b57",
                    suffix="%")

    def _weekly_trend(self) -> None:
        self._line(self.canvases["weekly"],
                   data.applications_by_week()[-12:], color="#b0562f")

    def _subject_demand_chart(self) -> None:
        self._hbars(self.canvases["subjects"], data.subject_demand()[:8],
                    color="#6a4fb0")

    @staticmethod
    def _hbars(cv: tk.Canvas, pairs: list, *, color: str,
               suffix: str = "") -> None:
        cv.delete("all")
        w = int(cv["width"])
        h = int(cv["height"])
        if not pairs:
            cv.create_text(w // 2, h // 2, text="(no data)", fill="#999")
            return
        rows = list(pairs)[:8]
        top = max((v for _, v in rows), default=0) or 1
        rh = (h - 8) / len(rows)
        label_w = 108
        for i, (k, v) in enumerate(rows):
            y = 4 + i * rh
            cv.create_text(4, y + rh / 2, text=str(k)[:16], anchor="w",
                           font=("TkDefaultFont", 8))
            bw = (w - label_w - 46) * v / top
            cv.create_rectangle(label_w, y + 2, label_w + bw, y + rh - 2,
                                fill=color, outline="")
            cv.create_text(label_w + bw + 4, y + rh / 2,
                           text=f"{v}{suffix}", anchor="w",
                           font=("TkDefaultFont", 8))

    @staticmethod
    def _line(cv: tk.Canvas, pairs: list, *, color: str) -> None:
        cv.delete("all")
        w = int(cv["width"])
        h = int(cv["height"])
        if len(pairs) < 2:
            cv.create_text(w // 2, h // 2, text="(not enough data)",
                           fill="#999")
            return
        vals = [v for _, v in pairs]
        top = max(vals) or 1
        pad_l, pad_r, pad_t, pad_b = 24, 10, 12, 26
        span = (w - pad_l - pad_r)
        base = h - pad_b
        n = len(pairs)
        pts = []
        for i, (_, v) in enumerate(pairs):
            x = pad_l + span * i / (n - 1)
            y = pad_t + (base - pad_t) * (1 - v / top)
            pts.append((x, y))
        cv.create_line(pad_l, base, w - pad_r, base, fill="#ccc")
        for i in range(len(pts) - 1):
            cv.create_line(*pts[i], *pts[i + 1], fill=color, width=2)
        for (x, y), (lbl, v) in zip(pts, pairs):
            cv.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color,
                           outline="")
        # First / mid / last x-axis labels.
        for idx in {0, n // 2, n - 1}:
            lbl = str(pairs[idx][0])[-5:]
            cv.create_text(pts[idx][0], base + 10, text=lbl,
                           font=("TkDefaultFont", 7), fill="#666")
        cv.create_text(pad_l - 4, pad_t, text=str(top), anchor="e",
                       font=("TkDefaultFont", 7), fill="#666")

    # ── cohort compare / auto-refresh (items 32, 35) ────────────

    def _cohort_compare(self) -> None:
        by_year: dict[str, dict[str, int]] = {}
        for a in data.list_applicants():
            year = (a.submitted_at or "????")[:4]
            d = by_year.setdefault(year, {"total": 0, "offers": 0,
                                          "enrolled": 0})
            d["total"] += 1
            if a.offer_type and a.offer_type != "Not Offered":
                d["offers"] += 1
            if a.status == "Enrolled":
                d["enrolled"] += 1
        lines = ["Cohort comparison by application year", "=" * 52, "",
                 f"  {'Year':<6}{'Total':>7}{'Offers':>8}"
                 f"{'Enrolled':>10}{'Conv%':>8}"]
        for year in sorted(by_year):
            d = by_year[year]
            conv = round(100 * d["enrolled"] / d["offers"]) if d["offers"] \
                else 0
            lines.append(f"  {year:<6}{d['total']:>7}{d['offers']:>8}"
                         f"{d['enrolled']:>10}{conv:>7}%")
        if not by_year:
            lines.append("  (no applicants)")
        TextViewerDialog(self.frame.winfo_toplevel(),
                          "Cohort comparison", "\n".join(lines),
                          save_name="cohort_comparison.txt")

    def _refresh_auto(self) -> None:
        if self._auto_job is not None:
            self.frame.after_cancel(self._auto_job)
            self._auto_job = None
        if self.v_auto.get():
            def tick() -> None:
                if not self.v_auto.get():
                    return
                self.refresh()
                self._auto_job = self.frame.after(30_000, tick)
            self._auto_job = self.frame.after(30_000, tick)

    # ── management PDF (item 33) ─────────────────────────────────

    def _export_summary_pdf(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.frame.winfo_toplevel(), defaultextension=".pdf",
            initialfile="admissions_summary.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            self._write_summary_pdf(path)
        except Exception as e:  # noqa: BLE001 — surface, don't crash the GUI
            messagebox.showerror("Export summary PDF",
                                  f"Could not create PDF:\n{e}")
            return
        messagebox.showinfo("Export summary PDF", f"Saved to {path}")

    @staticmethod
    def _write_summary_pdf(path: str) -> None:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
        styles = getSampleStyleSheet()
        summ = data.summary()
        elems = [
            Paragraph(f"{branding.SYSTEM_NAME} — Admissions summary",
                      styles["Title"]),
            Paragraph(f"Generated {_today()}", styles["Normal"]),
            Spacer(1, 10),
            Paragraph("Headline", styles["Heading2"]),
        ]
        head = [["Total", summ.total], ["Open", summ.open_count],
                ["Awaiting decision", summ.awaiting_decision],
                ["Pending offers", summ.pending_offers],
                ["Converted", summ.converted], ["Rejected", summ.rejected]]
        t1 = Table(head, colWidths=[6 * cm, 3 * cm])
        t1.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9)]))
        elems += [t1, Spacer(1, 10),
                  Paragraph("Conversion funnel", styles["Heading2"])]
        funnel_rows = [["Stage", "Count"]] + [[s, n] for s, n in data.funnel()]
        t2 = Table(funnel_rows, colWidths=[7 * cm, 3 * cm], repeatRows=1)
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b63")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9)]))
        elems += [t2, Spacer(1, 10),
                  Paragraph("Source effectiveness", styles["Heading2"])]
        src_rows = [["Source", "Total", "Offers", "Enrolled", "Conv%"]]
        for d in data.source_effectiveness():
            src_rows.append([d["source"], d["total"], d["offers"],
                             d["enrolled"], f"{d['conversion']}%"])
        t3 = Table(src_rows, repeatRows=1,
                   colWidths=[5 * cm, 2 * cm, 2 * cm, 2.5 * cm, 2 * cm])
        t3.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b63")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9)]))
        elems.append(t3)
        SimpleDocTemplate(path, pagesize=A4, leftMargin=2 * cm,
                          rightMargin=2 * cm, topMargin=2 * cm,
                          bottomMargin=2 * cm).build(elems)


# ══ Dialogs ═══════════════════════════════════════════════════════

class DetailDialog:
    """Read-only applicant record with grouped sections, documents,
    a threaded notes panel and an activity timeline."""

    def __init__(self, parent: tk.Misc, applicant: Applicant,
                 on_change: Callable[[], None]) -> None:
        self.aid = applicant.applicant_id
        self.on_change = on_change
        self._photo_img: tk.PhotoImage | None = None  # keep a reference
        self.win = tk.Toplevel(parent)
        self.win.title(f"Applicant {applicant.applicant_id} — "
                        f"{applicant.full_name}")
        self.win.geometry("820x640")
        self.win.transient(parent)
        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.profile = ttk.Frame(nb)
        self.docs_tab = ttk.Frame(nb)
        self.notes_tab = ttk.Frame(nb)
        self.timeline_tab = ttk.Frame(nb)
        nb.add(self.profile, text="Profile")
        nb.add(self.docs_tab, text="Documents & References")
        nb.add(self.notes_tab, text="Notes")
        nb.add(self.timeline_tab, text="Timeline")

        footer = ttk.Frame(self.win)
        footer.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(footer, text="Email applicant…",
                    command=self._email).pack(side="left")
        ttk.Button(footer, text="Offer letter…",
                    command=self._letter).pack(side="left", padx=4)
        ttk.Button(footer, text="Open student record",
                    command=self._open_student).pack(side="left", padx=4)

        # Extra single-applicant actions (items 36–45).
        more_mb = ttk.Menubutton(footer, text="More ▾")
        mmenu = tk.Menu(more_mb, tearoff=0)
        mmenu.add_command(label="Custom email…",
                           command=self._send_custom_email)
        mmenu.add_command(label="Quick standard offer",
                           command=self._quick_offer)
        mmenu.add_command(label="Print offer letter",
                           command=self._print_offer_letter)
        mmenu.add_command(label="Offer status / expiry…",
                           command=self._offer_expiry_reminder)
        mmenu.add_separator()
        mmenu.add_command(label="Communications log…",
                           command=self._communication_log)
        mmenu.add_command(label="Score vs cohort…",
                           command=self._score_comparison)
        mmenu.add_command(label="Chase all outstanding references…",
                           command=self._reference_chase_all)
        more_mb["menu"] = mmenu
        more_mb.pack(side="left", padx=4)

        ttk.Button(footer, text="GDPR export…",
                    command=self._gdpr_export).pack(side="right")
        ttk.Button(footer, text="Erase (GDPR)…",
                    command=self._gdpr_erase).pack(side="right", padx=4)
        self.refresh()

    def _email(self) -> None:
        EmailPreviewDialog(self.win, self.aid)

    def _letter(self) -> None:
        a = self._applicant()
        if a is None or not a.offer_type:
            messagebox.showinfo("Offer letter",
                                  "No offer has been made yet.")
            return
        TextViewerDialog(self.win, f"Offer letter — {self.aid}",
                          data.render_offer_letter(self.aid),
                          save_name=f"offer_{self.aid}.txt")

    def _open_student(self) -> None:
        a = self._applicant()
        if a is None or not a.converted_student_id:
            messagebox.showinfo("Student record",
                                  "This applicant has not been enrolled.")
            return
        try:
            from education_system.post_16.sixthform_system.modules.domain.students.students import (  # noqa: E501
                students as _students,
            )
            st = _students.get_student(a.converted_student_id)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Student record", str(e))
            return
        if st is None:
            messagebox.showinfo("Student record",
                                  f"Student {a.converted_student_id} "
                                  f"not found.")
            return
        messagebox.showinfo(
            f"Student {st.student_id}",
            f"{st.first_name} {st.last_name}\n"
            f"Email: {getattr(st, 'email', '—')}\n"
            f"Subjects: {getattr(st, 'subject_1', '—')}, "
            f"{getattr(st, 'subject_2', '—')}, "
            f"{getattr(st, 'subject_3', '—')}")

    def _gdpr_export(self) -> None:
        import json
        payload = json.dumps(data.gdpr_export(self.aid), indent=2,
                              default=str)
        TextViewerDialog(self.win, f"GDPR export — {self.aid}", payload,
                          save_name=f"gdpr_{self.aid}.json")

    def _gdpr_erase(self) -> None:
        if not messagebox.askyesno(
                "Erase all data",
                f"Permanently delete ALL data for {self.aid} "
                f"(applicant, notes, events, documents, scorecard)?\n\n"
                f"This cannot be undone."):
            return
        data.erase_applicant(self.aid)
        self.on_change()
        self.win.destroy()

    # ── data ────────────────────────────────────────────────────
    def _applicant(self) -> Applicant | None:
        return data.get_applicant(self.aid)

    def refresh(self) -> None:
        a = self._applicant()
        if a is None:
            self.win.destroy()
            return
        self._build_profile(a)
        self._build_docs(a)
        self._build_notes(a)
        self._build_timeline(a)

    @staticmethod
    def _clear(frame: ttk.Frame) -> None:
        for w in frame.winfo_children():
            w.destroy()

    # ── Profile tab (11, 14, 20, 25) ────────────────────────────
    def _build_profile(self, a: Applicant) -> None:
        self._clear(self.profile)
        top = ttk.Frame(self.profile)
        top.pack(fill="x", padx=10, pady=8)

        # Photo / avatar (item 20).
        photo = data.get_photo(self.aid)
        ph_frame = ttk.LabelFrame(top, text="Photo")
        ph_frame.pack(side="right", padx=(10, 0))
        img = None
        if photo:
            try:
                img = tk.PhotoImage(file=photo.path)
                # Downscale very large images crudely to fit.
                if img.width() > 160:
                    img = img.subsample(max(1, img.width() // 160))
            except Exception:
                img = None
        if img is not None:
            self._photo_img = img
            ttk.Label(ph_frame, image=img).pack(padx=4, pady=4)
        else:
            ttk.Label(ph_frame, text="(no photo)\nPNG/GIF",
                       width=14, anchor="center",
                       justify="center").pack(padx=12, pady=20)

        grid = ttk.Frame(top)
        grid.pack(side="left", fill="both", expand=True)

        def section(title: str, rows: list[tuple[str, str]]) -> None:
            lf = ttk.LabelFrame(grid, text=title)
            lf.pack(fill="x", pady=4)
            for i, (k, v) in enumerate(rows):
                ttk.Label(lf, text=f"{k}:", width=16, anchor="e").grid(
                    row=i, column=0, sticky="e", padx=4, pady=1)
                ttk.Label(lf, text=v or "—", anchor="w",
                           wraplength=460, justify="left").grid(
                    row=i, column=1, sticky="w", padx=4, pady=1)

        age = _compute_age(a.dob)
        section("Personal", [
            ("Applicant ID", a.applicant_id),
            ("Name", a.full_name),
            ("DOB", f"{a.dob or '—'}"
                    + (f"  (age {age})" if age is not None else "")),
            ("Email", a.email or "—"),
            ("Phone", a.phone or "—"),
            ("Address", a.address or "—"),
        ])
        section("Academic", [
            ("Previous school", a.previous_school or "—"),
            ("Predicted GCSEs", a.predicted_gcses or "—"),
            ("Subjects", ", ".join(a.subjects) if a.subjects else "—"),
        ])
        section("Application", [
            ("Source", a.application_source),
            ("Submitted", a.submitted_at),
            ("Status", a.status),
            ("Days in stage", str(_days_in_stage(a) or 0)),
        ])
        if a.offer_type or a.decision_by or a.decision_reason:
            section("Offer & Decision", [
                ("Offer", a.offer_type or "—"),
                ("Conditions", a.offer_conditions or "—"),
                ("Offer expiry", a.offer_expiry or "—"),
                ("Decided by", a.decision_by or "—"),
                ("Decision date", a.decision_date or "—"),
                ("Reason code", a.decision_reason or "—"),
                ("Decision notes", a.decision_notes or "—"),
                ("Follow-up flag", "Yes" if a.follow_up else "No"),
                ("Enrolled as", a.converted_student_id or "—"),
            ])

        # GCSE-vs-conditions heuristic (item 14).
        concern = _gcse_concerns(a.predicted_gcses, a.offer_conditions)
        if concern:
            warn = ttk.Label(self.profile, text="⚠ " + concern,
                              foreground="#b00000", wraplength=760,
                              justify="left")
            warn.pack(fill="x", padx=12, pady=(0, 4))

        # Interview scorecard summary (item 25).
        score = data.get_interview_score(self.aid)
        sf = ttk.LabelFrame(self.profile, text="Interview scorecard")
        sf.pack(fill="x", padx=10, pady=6)
        if score is None:
            ttk.Label(sf, text="No scorecard recorded.").pack(
                side="left", padx=6, pady=4)
        else:
            txt = (f"Motivation {score.motivation or '—'} · "
                   f"Subject fit {score.subject_fit or '—'} · "
                   f"Attainment {score.attainment or '—'}  "
                   f"→ avg {score.average if score.average is not None else '—'}"
                   f"   |   Recommendation: {score.recommendation or '—'}")
            ttk.Label(sf, text=txt).pack(side="left", padx=6, pady=4)
            if score.comments:
                ttk.Label(sf, text=score.comments, wraplength=740,
                           foreground="#444").pack(
                    fill="x", padx=6, pady=(0, 4))
        ttk.Button(sf, text="Edit scorecard…",
                    command=self._edit_score).pack(side="right", padx=6)

    # ── Documents & References tab (16, 17, 20) ─────────────────
    def _build_docs(self, a: Applicant) -> None:
        self._clear(self.docs_tab)

        # References (item 17).
        ref = ttk.LabelFrame(self.docs_tab, text="Reference")
        ref.pack(fill="x", padx=10, pady=8)
        ttk.Label(ref, text=f"Referee: {a.reference_name or '—'}  "
                             f"({a.reference_contact or '—'})").grid(
            row=0, column=0, columnspan=4, sticky="w", padx=6, pady=2)
        ttk.Label(ref, text="Status:").grid(row=1, column=0,
                                               sticky="e", padx=6)
        self.ref_cb = ttk.Combobox(ref, values=REFERENCE_STATUSES,
                                     state="readonly", width=16)
        self.ref_cb.set(a.reference_status)
        self.ref_cb.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Button(ref, text="Set",
                    command=self._set_ref_status).grid(row=1, column=2, padx=4)
        ttk.Button(ref, text="Chase referee",
                    command=lambda: self._chase(a)).grid(row=1, column=3,
                                                          padx=4)

        # Documents (item 16) + Photo (item 20).
        dl = ttk.LabelFrame(self.docs_tab, text="Documents")
        dl.pack(fill="both", expand=True, padx=10, pady=8)
        cols = ("type", "label", "added")
        self.doc_tree = ttk.Treeview(dl, columns=cols, show="headings",
                                      height=10)
        for c, w in (("type", 150), ("label", 380), ("added", 160)):
            self.doc_tree.heading(c, text=c.capitalize())
            self.doc_tree.column(c, width=w, anchor="w")
        self.doc_tree.pack(fill="both", expand=True, side="left",
                            padx=(4, 0), pady=4)
        self._docs = {d.id: d for d in data.list_documents(self.aid)}
        for d in self._docs.values():
            self.doc_tree.insert("", "end", iid=str(d.id), values=(
                d.doc_type, d.label or "—", d.added_at))
        self.doc_tree.bind("<Double-1>", lambda _e: self._open_doc())
        self.doc_tree.bind("<<TreeviewSelect>>",
                            lambda _e: self._document_preview())

        bar = ttk.Frame(dl)
        bar.pack(side="right", fill="y", padx=4, pady=4)
        ttk.Button(bar, text="Add…", command=self._add_doc).pack(
            fill="x", pady=2)
        ttk.Button(bar, text="Add several…",
                    command=self._bulk_upload_docs).pack(fill="x", pady=2)
        ttk.Button(bar, text="Set photo…",
                    command=lambda: self._add_doc(force_type="Photo")).pack(
            fill="x", pady=2)
        ttk.Button(bar, text="Open", command=self._open_doc).pack(
            fill="x", pady=2)
        ttk.Button(bar, text="Remove", command=self._remove_doc).pack(
            fill="x", pady=2)
        # Inline preview pane (item 40).
        self._preview_img: tk.PhotoImage | None = None
        self.doc_preview = ttk.Label(bar, text="(preview)", anchor="center",
                                      relief="solid", borderwidth=1,
                                      width=18)
        self.doc_preview.pack(fill="x", pady=(8, 2))

        # Required-document checklist (item 42).
        present = {d.doc_type for d in self._docs.values()}
        check = ttk.LabelFrame(self.docs_tab, text="Required documents")
        check.pack(fill="x", padx=10, pady=(0, 8))
        for req in REQUIRED_DOCS:
            ok = req in present
            ttk.Label(check, text=f"{'✓' if ok else '✗'}  {req}",
                       foreground="#2e7d32" if ok else "#b00000").pack(
                anchor="w", padx=8, pady=1)

    # ── Notes tab (18) ──────────────────────────────────────────
    def _build_notes(self, a: Applicant) -> None:
        self._clear(self.notes_tab)
        entry = ttk.Frame(self.notes_tab)
        entry.pack(fill="x", padx=10, pady=8)
        ttk.Label(entry, text="Author:").pack(side="left")
        self.note_author = ttk.Entry(entry, width=16)
        self.note_author.pack(side="left", padx=(2, 8))
        ttk.Label(entry, text="Note:").pack(side="left")
        self.note_body = ttk.Entry(entry, width=46)
        self.note_body.pack(side="left", padx=2, fill="x", expand=True)
        self.note_body.bind("<Return>", lambda _e: self._add_note())
        ttk.Button(entry, text="Add note",
                    command=self._add_note).pack(side="left", padx=6)

        thread = tk.Text(self.notes_tab, wrap="word", state="disabled",
                          font=("TkDefaultFont", 10))
        thread.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        notes = data.list_notes(self.aid)
        thread.configure(state="normal")
        if not notes:
            thread.insert("end", "No notes yet.")
        for n in notes:
            thread.insert("end", f"{n.at}  —  {n.author or 'unknown'}\n",
                           ("hdr",))
            thread.insert("end", f"{n.body}\n\n")
        thread.tag_configure("hdr", foreground="#205080",
                              font=("TkDefaultFont", 9, "bold"))
        thread.configure(state="disabled")

    # ── Timeline tab (12) ───────────────────────────────────────
    def _build_timeline(self, a: Applicant) -> None:
        self._clear(self.timeline_tab)
        cols = ("at", "kind", "detail")
        tree = ttk.Treeview(self.timeline_tab, columns=cols,
                             show="headings")
        for c, w in (("at", 150), ("kind", 90), ("detail", 540)):
            tree.heading(c, text=c.capitalize())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for e in data.list_events(self.aid):
            tree.insert("", "end", values=(e.at, e.kind, e.detail))

    # ── actions ─────────────────────────────────────────────────
    def _notify(self) -> None:
        self.refresh()
        self.on_change()

    def _set_ref_status(self) -> None:
        try:
            data.set_reference_status(self.aid, self.ref_cb.get())
        except ValidationError as e:
            messagebox.showerror("Reference", str(e))
            return
        self._notify()

    def _chase(self, a: Applicant) -> None:
        if not a.reference_contact:
            messagebox.showinfo("Chase referee",
                                  "No referee contact on file.")
            return
        data.set_reference_status(self.aid, "Requested")
        messagebox.showinfo(
            "Chase referee",
            f"Reminder to send to {a.reference_name or 'referee'} "
            f"({a.reference_contact}):\n\n"
            f"Dear {a.reference_name or 'Sir/Madam'},\n\n"
            f"We are still awaiting your reference for {a.full_name}'s "
            f"sixth-form application. We'd be grateful if you could "
            f"return it at your earliest convenience.\n\n"
            f"Reference status set to 'Requested'.")
        self._notify()

    def _selected_doc(self) -> data.Document | None:
        sel = self.doc_tree.selection()
        if not sel:
            return None
        return self._docs.get(int(sel[0]))

    def _add_doc(self, force_type: str | None = None) -> None:
        path = filedialog.askopenfilename(parent=self.win,
                                           title="Choose a document")
        if not path:
            return
        if force_type:
            doc_type, label = force_type, None
        else:
            doc_type = AskChoiceDialog(
                self.win, "Document type", "Type:",
                list(DOCUMENT_TYPES)).result
            if doc_type is None:
                return
            label = None
        try:
            data.add_document(self.aid, path, doc_type=doc_type, label=label)
        except ValidationError as e:
            messagebox.showerror("Add document", str(e))
            return
        self._notify()

    def _open_doc(self) -> None:
        d = self._selected_doc()
        if d is None:
            messagebox.showinfo("Open", "Select a document first.")
            return
        _open_path(d.path)

    def _remove_doc(self) -> None:
        d = self._selected_doc()
        if d is None:
            messagebox.showinfo("Remove", "Select a document first.")
            return
        if not messagebox.askyesno("Remove document",
                                     f"Remove '{d.label or d.doc_type}'?"):
            return
        data.remove_document(d.id)
        self._notify()

    def _add_note(self) -> None:
        body = self.note_body.get().strip()
        if not body:
            return
        try:
            data.add_note(self.aid, body,
                          author=self.note_author.get().strip() or None)
        except ValidationError as e:
            messagebox.showerror("Add note", str(e))
            return
        self.note_body.delete(0, "end")
        self._notify()

    def _edit_score(self) -> None:
        ScorecardDialog(self.win, self.aid, on_save=self._notify)

    # ── documents: preview + bulk upload (items 40, 41) ─────────

    def _document_preview(self) -> None:
        d = self._selected_doc()
        if d is None:
            return
        ext = os.path.splitext(d.path)[1].lower()
        if ext in (".png", ".gif", ".pgm", ".ppm"):
            try:
                img = tk.PhotoImage(file=d.path)
                if img.width() > 160:
                    img = img.subsample(max(1, img.width() // 160))
                self._preview_img = img
                self.doc_preview.configure(image=img, text="")
                return
            except Exception:  # noqa: BLE001 — fall back to a text label
                pass
        self._preview_img = None
        self.doc_preview.configure(
            image="", text=f"{d.doc_type}\n{ext or 'file'}\n(no preview)")

    def _bulk_upload_docs(self) -> None:
        paths = filedialog.askopenfilenames(
            parent=self.win, title="Choose one or more documents")
        if not paths:
            return
        doc_type = AskChoiceDialog(self.win, "Document type",
                                    "Type for all:",
                                    list(DOCUMENT_TYPES)).result
        if doc_type is None:
            return
        added, failures = 0, []
        for p in paths:
            try:
                data.add_document(self.aid, p, doc_type=doc_type)
                added += 1
            except Exception as e:  # noqa: BLE001
                failures.append(f"{os.path.basename(p)}: {e}")
        self._notify()
        msg = f"Added {added} document(s)."
        if failures:
            msg += "\n\nFailed:\n" + "\n".join(failures)
        messagebox.showinfo("Add several", msg)

    # ── email / offer actions (items 36, 37, 39, 45) ────────────

    def _send_custom_email(self) -> None:
        a = self._applicant()
        if a is None:
            return
        try:
            subject, body = data.render_status_email(self.aid)
        except Exception:  # noqa: BLE001 — start from a blank template
            subject, body = "", f"Dear {a.first_name},\n\n"
        top = self.win
        win = tk.Toplevel(top)
        win.title(f"Custom email — {self.aid}")
        win.transient(top)
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"To: {a.email or '(no email on file)'}").pack(
            anchor="w")
        ttk.Label(frm, text="Subject:").pack(anchor="w", pady=(6, 0))
        subj_e = ttk.Entry(frm, width=70)
        subj_e.insert(0, subject)
        subj_e.pack(fill="x")
        ttk.Label(frm, text="Body:").pack(anchor="w", pady=(6, 0))
        body_t = tk.Text(frm, wrap="word", width=70, height=16)
        body_t.insert("1.0", body)
        body_t.pack(fill="both", expand=True)

        def copy_() -> None:
            win.clipboard_clear()
            win.clipboard_append(
                f"Subject: {subj_e.get()}\n\n"
                + body_t.get("1.0", "end").strip())
            messagebox.showinfo("Custom email",
                                  "Email copied to the clipboard.")
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Copy to clipboard",
                    command=copy_).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=win.destroy).pack(side="right")

    def _offer_expiry_reminder(self) -> None:
        a = self._applicant()
        if a is None:
            return
        if not a.offer_type or a.offer_type == "Not Offered":
            messagebox.showinfo("Offer status", "No offer has been made.")
            return
        if not a.offer_expiry:
            if messagebox.askyesno(
                    "Offer status",
                    "This offer has no expiry date. Set one now?"):
                new = _prompt(self.win, "Offer expiry",
                              "Expiry date (YYYY-MM-DD):",
                              (_dt.date.today()
                               + _dt.timedelta(days=14)).isoformat())
                if new:
                    try:
                        data.set_offer_expiry(self.aid, new)
                        self._notify()
                    except ValidationError as e:
                        messagebox.showerror("Offer expiry", str(e))
            return
        exp = _parse_date(a.offer_expiry)
        days = (exp - _dt.date.today()).days if exp else None
        state = ("EXPIRED" if days is not None and days < 0
                 else f"{days} day(s) remaining" if days is not None
                 else "unknown")
        if messagebox.askyesno(
                "Offer status",
                f"Offer ({a.offer_type}) expires {a.offer_expiry} — {state}."
                f"\n\nSend a reminder to {a.email or 'the applicant'} now?"):
            self._send_custom_email()

    def _print_offer_letter(self) -> None:
        a = self._applicant()
        if a is None or not a.offer_type:
            messagebox.showinfo("Print offer letter",
                                  "No offer has been made yet.")
            return
        try:
            ApplicantsTab._send_to_printer(data.render_offer_letter(self.aid))
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Print offer letter",
                                  f"Could not print:\n{e}")
            return
        messagebox.showinfo("Print offer letter",
                              "Offer letter sent to the default printer.")

    def _quick_offer(self) -> None:
        a = self._applicant()
        if a is None:
            return
        conditions = "Achieve at least grade 6 in your chosen subjects."
        if not messagebox.askyesno(
                "Quick standard offer",
                f"Make a standard {DEFAULT_OFFER_TYPE} offer to "
                f"{a.full_name}?\n\nConditions: {conditions}"):
            return
        try:
            data.make_offer(self.aid, offer_type=DEFAULT_OFFER_TYPE,
                            conditions=conditions, decided_by="admissions-gui")
        except ValidationError as e:
            messagebox.showerror("Quick standard offer", str(e))
            return
        self._notify()

    # ── logs / comparisons / references (items 38, 43, 44) ──────

    def _communication_log(self) -> None:
        entries: list[tuple[str, str, str]] = []
        for n in data.list_notes(self.aid):
            entries.append((n.at, "note",
                            f"{n.author or 'unknown'}: {n.body}"))
        for e in data.list_events(self.aid):
            if e.kind in ("note", "email", "offer", "status", "reference"):
                entries.append((e.at, e.kind, e.detail))
        entries.sort(key=lambda t: t[0], reverse=True)
        lines = [f"Communications log — {self.aid}", "=" * 52, ""]
        for at, kind, detail in entries:
            lines.append(f"{at}  [{kind}]  {detail}")
        if not entries:
            lines.append("(no communications recorded)")
        TextViewerDialog(self.win, f"Communications — {self.aid}",
                          "\n".join(lines),
                          save_name=f"comms_{self.aid}.txt")

    def _score_comparison(self) -> None:
        mine = data.get_interview_score(self.aid)
        if mine is None or mine.average is None:
            messagebox.showinfo("Score vs cohort",
                                  "This applicant has no interview score yet.")
            return
        averages = []
        for a in data.list_applicants():
            s = data.get_interview_score(a.applicant_id)
            if s is not None and s.average is not None:
                averages.append(s.average)
        cohort = round(sum(averages) / len(averages), 1) if averages else 0
        rank = sum(1 for v in averages if v > mine.average) + 1
        delta = round(mine.average - cohort, 1)
        messagebox.showinfo(
            "Score vs cohort",
            f"Applicant average : {mine.average}\n"
            f"Cohort average    : {cohort}  (n={len(averages)})\n"
            f"Difference        : {delta:+}\n"
            f"Rank              : {rank} of {len(averages)}")

    def _reference_chase_all(self) -> None:
        outstanding = [a for a in data.list_applicants()
                       if a.reference_status in ("Not requested", "Requested")
                       and a.reference_contact]
        if not outstanding:
            messagebox.showinfo(
                "Chase references",
                "No applicants have an outstanding reference with a "
                "contact on file.")
            return
        if not messagebox.askyesno(
                "Chase references",
                f"Mark {len(outstanding)} outstanding reference(s) as "
                f"'Requested' and generate a chase list?"):
            return
        lines = [f"Reference chase list ({len(outstanding)})", "=" * 52, ""]
        for a in outstanding:
            try:
                data.set_reference_status(a.applicant_id, "Requested")
            except Exception:  # noqa: BLE001
                pass
            lines.append(f"To: {a.reference_contact}  (re: {a.full_name}, "
                         f"{a.applicant_id})")
        self._notify()
        TextViewerDialog(self.win, "Reference chase list", "\n".join(lines),
                          save_name="reference_chase.txt")


class AskChoiceDialog:
    """Tiny modal that returns a single choice from a combobox."""

    def __init__(self, parent: tk.Misc, title: str, label: str,
                 choices: list[str]) -> None:
        self.result: str | None = None
        win = tk.Toplevel(parent)
        win.title(title)
        win.transient(parent)
        win.after_idle(win.grab_set)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=label).grid(row=0, column=0, sticky="e", padx=4)
        cb = ttk.Combobox(frm, values=choices, state="readonly", width=24)
        cb.current(0)
        cb.grid(row=0, column=1, sticky="w", padx=4)
        bar = ttk.Frame(frm)
        bar.grid(row=1, column=0, columnspan=2, pady=(10, 0))

        def ok() -> None:
            self.result = cb.get()
            win.destroy()
        ttk.Button(bar, text="OK", command=ok).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)
        win.wait_window()


class ScorecardDialog:
    """Capture/edit the structured interview scorecard (item 25)."""

    def __init__(self, parent: tk.Misc, applicant_id: str,
                 on_save: Callable[[], None]) -> None:
        self.aid = applicant_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Interview scorecard — {applicant_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        existing = data.get_interview_score(applicant_id)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        scale = ("", "1", "2", "3", "4", "5")
        self.cbs: dict[str, ttk.Combobox] = {}
        for i, (attr, lbl) in enumerate((
                ("motivation", "Motivation"),
                ("subject_fit", "Subject fit"),
                ("attainment", "Attainment"))):
            ttk.Label(form, text=f"{lbl} (1–5):").grid(
                row=i, column=0, sticky="e", pady=4)
            cb = ttk.Combobox(form, values=scale, state="readonly", width=6)
            cb.set(str(getattr(existing, attr) or "") if existing else "")
            cb.grid(row=i, column=1, sticky="w", padx=6)
            self.cbs[attr] = cb
        ttk.Label(form, text="Recommendation:").grid(row=3, column=0,
                                                        sticky="e", pady=4)
        self.rec_cb = ttk.Combobox(form, values=("",) + RECOMMENDATIONS,
                                     state="readonly", width=18)
        self.rec_cb.set(existing.recommendation if existing
                         and existing.recommendation else "")
        self.rec_cb.grid(row=3, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Scored by:").grid(row=4, column=0,
                                                  sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=24)
        if existing and existing.scored_by:
            self.by_e.insert(0, existing.scored_by)
        self.by_e.grid(row=4, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Comments:").grid(row=5, column=0,
                                                 sticky="ne", pady=4)
        self.comments_t = tk.Text(form, width=44, height=4)
        if existing and existing.comments:
            self.comments_t.insert("1.0", existing.comments)
        self.comments_t.grid(row=5, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=6, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.save_interview_score(
                self.aid,
                motivation=self.cbs["motivation"].get() or None,
                subject_fit=self.cbs["subject_fit"].get() or None,
                attainment=self.cbs["attainment"].get() or None,
                recommendation=self.rec_cb.get() or None,
                scored_by=self.by_e.get().strip() or None,
                comments=self.comments_t.get("1.0", "end").strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Scorecard", str(e))
            return
        self.win.destroy()
        self.on_save()


class TextViewerDialog:
    """Read-only text viewer with Copy and Save-to-file (items 31, 47, 50)."""

    def __init__(self, parent: tk.Misc, title: str, text: str,
                 save_name: str | None = None) -> None:
        self.text = text
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.geometry("620x520")
        self.win.transient(parent)
        box = tk.Text(self.win, wrap="word", font=("TkFixedFont", 10))
        box.insert("1.0", text)
        box.configure(state="disabled")
        box.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(bar, text="Copy",
                    command=self._copy).pack(side="left")
        if save_name:
            ttk.Button(bar, text="Save…",
                        command=lambda: self._save(save_name)).pack(
                side="left", padx=6)
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")

    def _copy(self) -> None:
        self.win.clipboard_clear()
        self.win.clipboard_append(self.text)

    def _save(self, name: str) -> None:
        ext = os.path.splitext(name)[1] or ".txt"
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=ext, initialfile=name)
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.text)
        messagebox.showinfo("Saved", f"Saved to {path}")


class EmailPreviewDialog(TextViewerDialog):
    """Render a templated applicant email (item 49)."""

    def __init__(self, parent: tk.Misc, applicant_id: str) -> None:
        try:
            subject, body = data.render_status_email(applicant_id)
        except ValidationError as e:
            messagebox.showerror("Email", str(e))
            raise
        super().__init__(parent, f"Email — {applicant_id}",
                          f"Subject: {subject}\n\n{body}",
                          save_name=f"email_{applicant_id}.txt")


class StatusDialog:
    def __init__(self, parent: tk.Misc, existing: Applicant,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — {existing.applicant_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text=f"Applicant: {existing.applicant_id} — "
                         f"{existing.full_name}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(form, text="New status:").grid(row=1, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=STATUSES,
                                  state="readonly", width=22)
        self.cb.set(existing.status)
        self.cb.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Decided by:").grid(row=2, column=0,
                                                    sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        if existing.decision_by:
            self.by_e.insert(0, existing.decision_by)
        self.by_e.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Reason code:").grid(row=3, column=0,
                                                    sticky="e", pady=4)
        self.reason_cb = ttk.Combobox(
            form, values=("",) + data.DECISION_REASONS,
            state="readonly", width=30)
        self.reason_cb.set(existing.decision_reason or "")
        self.reason_cb.grid(row=3, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Notes:").grid(row=4, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=40, height=4)
        if existing.decision_notes:
            self.notes_t.insert("1.0", existing.decision_notes)
        self.notes_t.grid(row=4, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=5, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Save + email…",
                    command=lambda: self._save(email=True)).pack(
            side="left", padx=6)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self, email: bool = False) -> None:
        try:
            data.record_decision(
                self.existing.applicant_id, self.cb.get(),
                reason=self.reason_cb.get() or None,
                decided_by=self.by_e.get().strip() or None,
                notes=self.notes_t.get("1.0", "end").strip() or None,
            )
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        if email:
            EmailPreviewDialog(self.win.master, self.existing.applicant_id)
        self.on_save()


class OfferDialog:
    def __init__(self, parent: tk.Misc, existing: Applicant,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Make offer — {existing.applicant_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text=f"Applicant: {existing.applicant_id} — "
                         f"{existing.full_name}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(form, text="Offer type:").grid(row=1, column=0,
                                                    sticky="e", pady=4)
        self.type_cb = ttk.Combobox(form, values=OFFER_TYPES,
                                       state="readonly", width=18)
        self.type_cb.set(existing.offer_type or DEFAULT_OFFER_TYPE)
        self.type_cb.grid(row=1, column=1, sticky="w", padx=6)
        # Structured conditions builder (item 29): per-subject grade rows
        # that compose into the free-text conditions box.
        builder = ttk.LabelFrame(form, text="Conditions builder")
        builder.grid(row=2, column=0, columnspan=2, sticky="we",
                      padx=4, pady=4)
        self._cond_rows: list[tuple[ttk.Combobox, ttk.Combobox]] = []
        subjects = existing.subjects or ["", "", ""]
        grades = ("A*", "A", "B", "C", "D", "E", "9", "8", "7", "6", "5", "4")
        for i in range(max(3, len(subjects))):
            ttk.Label(builder, text=f"Subject {i+1}:").grid(
                row=i, column=0, sticky="e", padx=4, pady=1)
            subj = ttk.Combobox(builder, width=24,
                                  values=tuple(existing.subjects))
            if i < len(subjects):
                subj.set(subjects[i])
            subj.grid(row=i, column=1, padx=4, pady=1)
            ttk.Label(builder, text="grade ≥").grid(row=i, column=2, padx=2)
            gr = ttk.Combobox(builder, width=5, values=("",) + grades,
                               state="readonly")
            gr.grid(row=i, column=3, padx=4, pady=1)
            self._cond_rows.append((subj, gr))
        ttk.Button(builder, text="Build conditions text",
                    command=self._build_conditions).grid(
            row=99, column=0, columnspan=4, pady=4)

        ttk.Label(form, text="Conditions:").grid(row=3, column=0,
                                                    sticky="ne", pady=4)
        self.cond_t = tk.Text(form, width=44, height=3)
        if existing.offer_conditions:
            self.cond_t.insert("1.0", existing.offer_conditions)
        self.cond_t.grid(row=3, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Offer expiry:").grid(row=4, column=0,
                                                      sticky="e", pady=4)
        self.expiry_e = ttk.Entry(form, width=14)
        self.expiry_e.insert(0, existing.offer_expiry
                              or (_dt.date.today()
                                  + _dt.timedelta(days=28)).isoformat())
        self.expiry_e.grid(row=4, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Decided by:").grid(row=5, column=0,
                                                    sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        if existing.decision_by:
            self.by_e.insert(0, existing.decision_by)
        self.by_e.grid(row=5, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=6, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Make offer",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Preview letter…",
                    command=self._preview_letter).pack(side="left", padx=6)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _build_conditions(self) -> None:
        parts = []
        for subj, gr in self._cond_rows:
            s, g = subj.get().strip(), gr.get().strip()
            if s and g:
                parts.append(f"{s} grade {g} or above")
        if not parts:
            messagebox.showinfo("Conditions",
                                  "Pick at least one subject + grade.")
            return
        self.cond_t.delete("1.0", "end")
        self.cond_t.insert("1.0", "; ".join(parts))

    def _save(self) -> None:
        try:
            data.make_offer(
                self.existing.applicant_id,
                offer_type=self.type_cb.get(),
                conditions=self.cond_t.get("1.0", "end").strip() or None,
                decided_by=self.by_e.get().strip() or None,
            )
            expiry = self.expiry_e.get().strip()
            if self.type_cb.get() == "Unconditional":
                expiry = expiry  # still allowed to set a response deadline
            data.set_offer_expiry(self.existing.applicant_id,
                                   expiry or None)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Offer", str(e))
            return
        self.win.destroy()
        self.on_save()

    def _preview_letter(self) -> None:
        # Persist the in-progress offer first so the letter reflects it.
        try:
            data.make_offer(
                self.existing.applicant_id,
                offer_type=self.type_cb.get(),
                conditions=self.cond_t.get("1.0", "end").strip() or None,
                decided_by=self.by_e.get().strip() or None,
            )
            data.set_offer_expiry(self.existing.applicant_id,
                                   self.expiry_e.get().strip() or None)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Offer", str(e))
            return
        TextViewerDialog(
            self.win, f"Offer letter — {self.existing.applicant_id}",
            data.render_offer_letter(self.existing.applicant_id),
            save_name=f"offer_{self.existing.applicant_id}.txt")
        self.on_save()


class ScheduleDialog:
    def __init__(self, parent: tk.Misc, applicants: list[Applicant],
                 on_save: Callable[[], None]) -> None:
        self.applicants = applicants
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Schedule interview")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Applicant:").grid(row=0, column=0,
                                                   sticky="e", pady=4)
        self._ids = [a.applicant_id for a in applicants]
        self.cb = ttk.Combobox(
            form,
            values=[f"{a.applicant_id} — {a.full_name}"
                     for a in applicants],
            state="readonly", width=44)
        self.cb.current(0)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Date:").grid(row=1, column=0,
                                              sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, _today())
        self.date_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Interviewer:").grid(row=2, column=0,
                                                     sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        self.by_e.grid(row=2, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Schedule",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.cb.current()
        if idx < 0:
            messagebox.showerror("Schedule", "Pick an applicant")
            return
        date = self.date_e.get().strip()
        interviewer = self.by_e.get().strip() or None
        # Clash detection (item 23): same interviewer, same day.
        if interviewer:
            clashes = [
                a for a in data.list_applicants()
                if a.interviewer == interviewer
                and a.interview_date == date
                and a.applicant_id != self._ids[idx]]
            if clashes:
                who = ", ".join(a.full_name for a in clashes)
                if not messagebox.askyesno(
                        "Possible clash",
                        f"{interviewer} already interviews {who} on "
                        f"{date}.\nSchedule anyway?"):
                    return
        try:
            data.schedule_interview(
                self._ids[idx],
                interview_date=date,
                interviewer=interviewer,
            )
        except Exception as e:
            messagebox.showerror("Schedule failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class RecordOutcomeDialog:
    """Record an interview outcome (item 24): notes move the applicant to
    'Interviewed' and the scorecard (item 25) can be filled in one place."""

    def __init__(self, parent: tk.Misc, applicant: Applicant,
                 on_save: Callable[[], None]) -> None:
        self.aid = applicant.applicant_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Interview outcome — {applicant.applicant_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text=f"{applicant.full_name} — interviewed "
                              f"{applicant.interview_date or '—'} by "
                              f"{applicant.interviewer or '—'}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(form, text="Interview notes:").grid(
            row=1, column=0, sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=50, height=5)
        if applicant.interview_notes:
            self.notes_t.insert("1.0", applicant.interview_notes)
        self.notes_t.grid(row=1, column=1, sticky="w", padx=6)

        # Inline scorecard.
        score = data.get_interview_score(self.aid)
        scale = ("", "1", "2", "3", "4", "5")
        self.cbs: dict[str, ttk.Combobox] = {}
        for i, (attr, lbl) in enumerate((
                ("motivation", "Motivation"),
                ("subject_fit", "Subject fit"),
                ("attainment", "Attainment"))):
            ttk.Label(form, text=f"{lbl} (1–5):").grid(
                row=2 + i, column=0, sticky="e", pady=2)
            cb = ttk.Combobox(form, values=scale, state="readonly", width=6)
            cb.set(str(getattr(score, attr) or "") if score else "")
            cb.grid(row=2 + i, column=1, sticky="w", padx=6)
            self.cbs[attr] = cb
        ttk.Label(form, text="Recommendation:").grid(
            row=5, column=0, sticky="e", pady=2)
        self.rec_cb = ttk.Combobox(form, values=("",) + RECOMMENDATIONS,
                                     state="readonly", width=18)
        self.rec_cb.set(score.recommendation if score
                         and score.recommendation else "")
        self.rec_cb.grid(row=5, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Scored by:").grid(row=6, column=0,
                                                  sticky="e", pady=2)
        self.by_e = ttk.Entry(form, width=24)
        if score and score.scored_by:
            self.by_e.insert(0, score.scored_by)
        elif applicant.interviewer:
            self.by_e.insert(0, applicant.interviewer)
        self.by_e.grid(row=6, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=7, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save outcome",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.record_interview(
                self.aid,
                interview_notes=self.notes_t.get("1.0", "end").strip()
                or None)
            if any(self.cbs[a].get() for a in self.cbs) or self.rec_cb.get():
                data.save_interview_score(
                    self.aid,
                    motivation=self.cbs["motivation"].get() or None,
                    subject_fit=self.cbs["subject_fit"].get() or None,
                    attainment=self.cbs["attainment"].get() or None,
                    recommendation=self.rec_cb.get() or None,
                    scored_by=self.by_e.get().strip() or None,
                )
        except ValidationError as e:
            messagebox.showerror("Record outcome", str(e))
            return
        self.win.destroy()
        self.on_save()


class DecisionDayDialog:
    """Step through interviewed applicants making a decision each (item 35)."""

    def __init__(self, parent: tk.Misc, queue: list[Applicant],
                 on_done: Callable[[], None]) -> None:
        self.queue = queue
        self.on_done = on_done
        self.i = 0
        self.win = tk.Toplevel(parent)
        self.win.title("Decision day")
        self.win.geometry("580x560")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self.body = ttk.Frame(self.win, padding=12)
        self.body.pack(fill="both", expand=True)
        self._render()

    def _render(self) -> None:
        for w in self.body.winfo_children():
            w.destroy()
        if self.i >= len(self.queue):
            ttk.Label(self.body, text="All applicants reviewed.",
                       font=("TkDefaultFont", 12)).pack(pady=30)
            ttk.Button(self.body, text="Close",
                        command=self._close).pack()
            return
        a = data.get_applicant(self.queue[self.i].applicant_id)
        if a is None:  # erased mid-session
            self.i += 1
            self._render()
            return
        ttk.Label(self.body, text=f"Applicant {self.i + 1} of "
                                   f"{len(self.queue)}",
                   foreground="#666").pack(anchor="w")
        ttk.Label(self.body, text=f"{a.full_name}  ({a.applicant_id})",
                   font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        ttk.Label(self.body, text=f"Subjects: {', '.join(a.subjects) or '—'}"
                                   ).pack(anchor="w")
        ttk.Label(self.body, text=f"Predicted GCSEs: "
                                   f"{a.predicted_gcses or '—'}").pack(
            anchor="w")
        score = data.get_interview_score(a.applicant_id)
        if score:
            ttk.Label(
                self.body,
                text=f"Scorecard avg: {score.average} · "
                     f"Recommendation: {score.recommendation or '—'}",
                foreground="#205080").pack(anchor="w", pady=(4, 0))
        if a.interview_notes:
            ttk.Label(self.body, text=f"Interview notes: {a.interview_notes}",
                       wraplength=540, foreground="#444").pack(
                anchor="w", pady=(2, 0))

        form = ttk.Frame(self.body)
        form.pack(fill="x", pady=10)
        ttk.Label(form, text="Decided by:").grid(row=0, column=0, sticky="e")
        self.by_e = ttk.Entry(form, width=22)
        self.by_e.grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(form, text="Conditions:").grid(row=1, column=0, sticky="e")
        self.cond_e = ttk.Entry(form, width=40)
        self.cond_e.grid(row=1, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(form, text="Reason:").grid(row=2, column=0, sticky="e")
        self.reason_cb = ttk.Combobox(form, values=("",) + data.DECISION_REASONS,
                                        state="readonly", width=30)
        self.reason_cb.grid(row=2, column=1, sticky="w", padx=4)

        bar = ttk.Frame(self.body)
        bar.pack(fill="x", pady=8)
        ttk.Button(bar, text="Make offer",
                    command=self._offer).pack(side="left")
        ttk.Button(bar, text="Waitlist",
                    command=self._waitlist).pack(side="left", padx=4)
        ttk.Button(bar, text="Reject",
                    command=self._reject).pack(side="left", padx=4)
        ttk.Button(bar, text="Skip",
                    command=self._advance).pack(side="left", padx=4)
        ttk.Button(bar, text="Finish",
                    command=self._close).pack(side="right")

    def _current(self) -> str:
        return self.queue[self.i].applicant_id

    def _offer(self) -> None:
        try:
            data.make_offer(self._current(),
                            conditions=self.cond_e.get().strip() or None,
                            decided_by=self.by_e.get().strip() or None)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Make offer", str(e))
            return
        self._advance()

    def _waitlist(self) -> None:
        try:
            data.set_status(self._current(), "Waitlisted",
                            decision_by=self.by_e.get().strip() or None)
            existing = data.get_waitlist()
            data.set_waitlist_rank(self._current(), len(existing))
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Waitlist", str(e))
            return
        self._advance()

    def _reject(self) -> None:
        try:
            data.record_decision(self._current(), "Rejected",
                                  reason=self.reason_cb.get() or None,
                                  decided_by=self.by_e.get().strip() or None)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Reject", str(e))
            return
        self._advance()

    def _advance(self) -> None:
        self.i += 1
        self._render()

    def _close(self) -> None:
        self.win.destroy()
        self.on_done()


class OffersTab:
    """Pending offers with expiry alerts and quick decisions (item 46)."""

    COLS = ("id", "name", "offer", "expiry", "left", "conditions", "email")

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Offers")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="View…", command=self._view).pack(side="left")
        ttk.Button(bar, text="Mark accepted",
                    command=lambda: self._decide("Offer Accepted")).pack(
            side="left", padx=4)
        ttk.Button(bar, text="Mark declined",
                    command=lambda: self._decide("Offer Declined")).pack(
            side="left", padx=2)
        ttk.Button(bar, text="Set/extend expiry…",
                    command=self._set_expiry).pack(side="left", padx=4)
        ttk.Button(bar, text="Email…", command=self._email).pack(
            side="left", padx=2)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

        table = ttk.Frame(self.frame)
        table.pack(fill="both", expand=True, padx=8, pady=4)
        self.tree = ttk.Treeview(table, columns=self.COLS, show="headings")
        widths = {"id": 80, "name": 180, "offer": 110, "expiry": 100,
                  "left": 60, "conditions": 260, "email": 200}
        for c in self.COLS:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("expiring", background="#fff2cc")
        self.tree.tag_configure("expired", background="#ffd0d0")
        self.tree.bind("<Double-1>", lambda _e: self._view())
        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = data.list_applicants(status="Offer Made")
        today = _dt.date.today()
        expiring = 0
        for a in rows:
            exp = _parse_date(a.offer_expiry)
            left = (exp - today).days if exp else None
            tags: tuple[str, ...] = ()
            if left is not None and left < 0:
                tags = ("expired",)
                expiring += 1
            elif left is not None and left <= 7:
                tags = ("expiring",)
                expiring += 1
            self.tree.insert("", "end", iid=a.applicant_id, values=(
                a.applicant_id, a.full_name, a.offer_type or "—",
                a.offer_expiry or "—",
                left if left is not None else "—",
                a.offer_conditions or "—", a.email or "—"), tags=tags)
        self.count_var.set(
            f"{len(rows)} pending offer(s)."
            + (f"  ⚠ {expiring} expiring or expired." if expiring else ""))

    def _sel(self) -> Applicant | None:
        sel = self.tree.selection()
        return data.get_applicant(sel[0]) if sel else None

    def _view(self) -> None:
        a = self._sel()
        if a is None:
            messagebox.showinfo("View", "Select an offer first.")
            return
        DetailDialog(self.frame.winfo_toplevel(), a, on_change=self.refresh)

    def _decide(self, status: str) -> None:
        a = self._sel()
        if a is None:
            messagebox.showinfo(status, "Select an offer first.")
            return
        if not messagebox.askyesno(status,
                                     f"Set {a.applicant_id} → {status}?"):
            return
        try:
            data.set_status(a.applicant_id, status)
        except ValidationError as e:
            messagebox.showerror(status, str(e))
            return
        self.refresh()

    def _set_expiry(self) -> None:
        a = self._sel()
        if a is None:
            messagebox.showinfo("Expiry", "Select an offer first.")
            return
        new = _prompt(self.frame, "Offer expiry",
                      "Expiry date (YYYY-MM-DD, blank to clear):",
                      a.offer_expiry or (_dt.date.today()
                                         + _dt.timedelta(days=14)).isoformat())
        if new is None:
            return
        try:
            data.set_offer_expiry(a.applicant_id, new.strip() or None)
        except ValidationError as e:
            messagebox.showerror("Offer expiry", str(e))
            return
        self.refresh()

    def _email(self) -> None:
        a = self._sel()
        if a is None:
            messagebox.showinfo("Email", "Select an offer first.")
            return
        EmailPreviewDialog(self.frame.winfo_toplevel(), a.applicant_id)


class TasksTab:
    """Actionable worklist across the pipeline (items 47, 50)."""

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Tasks")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Open selected…",
                    command=self._open).pack(side="left")
        ttk.Button(bar, text="Activity feed…",
                    command=self._activity_feed).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

        self.tree = ttk.Treeview(self.frame, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True, padx=8, pady=4)
        self.tree.bind("<Double-1>", lambda _e: self._open())
        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        apps = data.list_applicants()
        today = _dt.date.today()

        def bucket(title: str, items: list[tuple[str, str]]) -> None:
            node = self.tree.insert("", "end",
                                     text=f"{title}  ({len(items)})",
                                     open=True)
            for aid, label in items:
                self.tree.insert(node, "end", iid=f"{node}:{aid}",
                                  text=label)

        refs = [(a.applicant_id, f"{a.applicant_id}  {a.full_name} — "
                 f"reference {a.reference_status}")
                for a in apps
                if a.reference_status in ("Not requested", "Requested")
                and a.status in OPEN_STATUSES]
        follow = [(a.applicant_id, f"{a.applicant_id}  {a.full_name} — "
                   f"[{a.status}]")
                  for a in apps if a.follow_up]
        expiring = []
        for a in apps:
            if a.status != "Offer Made":
                continue
            exp = _parse_date(a.offer_expiry)
            if exp and (exp - today).days <= 7:
                left = (exp - today).days
                expiring.append((a.applicant_id,
                                 f"{a.applicant_id}  {a.full_name} — "
                                 f"expires {a.offer_expiry} ({left}d)"))
        awaiting = [(a.applicant_id, f"{a.applicant_id}  {a.full_name}")
                    for a in apps if a.status == "Interviewed"]
        unscheduled = [(a.applicant_id, f"{a.applicant_id}  {a.full_name}")
                       for a in apps
                       if a.status == "Under Review" and not a.interview_date]

        bucket("Outstanding references", refs)
        bucket("Flagged for follow-up / no-show", follow)
        bucket("Offers expiring ≤7 days", expiring)
        bucket("Interviewed — awaiting decision", awaiting)
        bucket("Under review — no interview booked", unscheduled)
        total = len(refs) + len(follow) + len(expiring) + len(awaiting) \
            + len(unscheduled)
        self.count_var.set(f"{total} open task(s).")

    def _open(self) -> None:
        sel = self.tree.selection()
        if not sel or ":" not in sel[0]:
            messagebox.showinfo("Open", "Select a task row (not a heading).")
            return
        aid = sel[0].split(":", 1)[1]
        a = data.get_applicant(aid)
        if a is not None:
            DetailDialog(self.frame.winfo_toplevel(), a,
                          on_change=self.refresh)

    def _activity_feed(self, limit: int = 100) -> None:
        events = []
        for a in data.list_applicants():
            for e in data.list_events(a.applicant_id):
                events.append((e.at, a.applicant_id, e.kind, e.detail))
        events.sort(key=lambda t: t[0], reverse=True)
        lines = [f"Recent activity (latest {limit})", "=" * 60, ""]
        for at, aid, kind, detail in events[:limit]:
            lines.append(f"{at}  {aid:<8} [{kind}]  {detail}")
        if not events:
            lines.append("(no activity recorded)")
        TextViewerDialog(self.frame.winfo_toplevel(),
                          "Activity feed", "\n".join(lines))


class WaitlistTab:
    """Ranked waitlist with promote/demote and make-offer (item 34)."""

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Waitlist")
        self._build()
        self.refresh()

    def _build(self) -> None:
        cols = ("rank", "id", "name", "subjects", "submitted")
        table = ttk.Frame(self.frame)
        table.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(table, columns=cols, show="headings")
        for c, w in (("rank", 60), ("id", 90), ("name", 200),
                      ("subjects", 320), ("submitted", 110)):
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=w, anchor="w")
        vs = ttk.Scrollbar(table, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(bar, text="▲ Up",
                    command=lambda: self._move(-1)).pack(side="left")
        ttk.Button(bar, text="▼ Down",
                    command=lambda: self._move(1)).pack(side="left", padx=4)
        ttk.Button(bar, text="Make offer",
                    command=self._offer).pack(side="left", padx=12)
        ttk.Button(bar, text="Auto-promote top",
                    command=self._waitlist_auto_promote).pack(side="left")
        ttk.Button(bar, text="Remove from list",
                    command=self._remove).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")
        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = data.get_waitlist()
        for r, a in enumerate(rows, start=1):
            self.tree.insert("", "end", iid=a.applicant_id, values=(
                a.waitlist_rank if a.waitlist_rank else r,
                a.applicant_id, a.full_name,
                ", ".join(a.subjects), a.submitted_at))
        self.count_var.set(f"{len(rows)} waitlisted applicant(s).")

    def _sel(self) -> str | None:
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _move(self, direction: int) -> None:
        aid = self._sel()
        if aid is None:
            return
        try:
            data.move_waitlist(aid, direction)
        except ValidationError as e:
            messagebox.showerror("Waitlist", str(e))
            return
        self.refresh()
        if self.tree.exists(aid):
            self.tree.selection_set(aid)

    def _offer(self) -> None:
        aid = self._sel()
        if aid is None:
            messagebox.showinfo("Make offer", "Select an applicant.")
            return
        a = data.get_applicant(aid)
        if a is not None:
            OfferDialog(self.frame.winfo_toplevel(), a,
                         on_save=self.refresh)

    def _remove(self) -> None:
        aid = self._sel()
        if aid is None:
            return
        data.set_waitlist_rank(aid, None)
        self.refresh()

    def _waitlist_auto_promote(self) -> None:
        rows = data.get_waitlist()
        if not rows:
            messagebox.showinfo("Auto-promote", "The waitlist is empty.")
            return
        top = rows[0]
        if not messagebox.askyesno(
                "Auto-promote top of waitlist",
                f"A place has opened up — make an offer to the top-ranked "
                f"waitlisted applicant?\n\n"
                f"{top.applicant_id} — {top.full_name} "
                f"(rank {top.waitlist_rank or 1})"):
            return
        try:
            data.make_offer(top.applicant_id,
                            offer_type=DEFAULT_OFFER_TYPE,
                            conditions="Promoted from waitlist.",
                            decided_by="admissions-gui")
            data.set_waitlist_rank(top.applicant_id, None)
        except ValidationError as e:
            messagebox.showerror("Auto-promote", str(e))
            return
        self.refresh()
        messagebox.showinfo(
            "Auto-promote",
            f"Offer made to {top.applicant_id} ({top.full_name}) and removed "
            f"from the waitlist.")


class ApplicantDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Applicant | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Applicant" if existing else "New Applicant")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        ttk.Label(form, text="First name:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.first_e = ttk.Entry(form, width=22)
        if self.existing:
            self.first_e.insert(0, self.existing.first_name)
        self.first_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Last name:").grid(row=r, column=2,
                                                   sticky="e", pady=4)
        self.last_e = ttk.Entry(form, width=22)
        if self.existing:
            self.last_e.insert(0, self.existing.last_name)
        self.last_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="DOB:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.dob_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.dob:
            self.dob_e.insert(0, self.existing.dob)
        self.dob_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Email:").grid(row=r, column=2,
                                               sticky="e", pady=4)
        self.email_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.email:
            self.email_e.insert(0, self.existing.email)
        self.email_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Phone:").grid(row=r, column=0,
                                               sticky="e", pady=4)
        self.phone_e = ttk.Entry(form, width=18)
        if self.existing and self.existing.phone:
            self.phone_e.insert(0, self.existing.phone)
        self.phone_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Address:").grid(row=r, column=2,
                                                 sticky="e", pady=4)
        self.addr_e = ttk.Entry(form, width=40)
        if self.existing and self.existing.address:
            self.addr_e.insert(0, self.existing.address)
        self.addr_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Previous school:").grid(row=r, column=0,
                                                          sticky="e", pady=4)
        self.prev_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.previous_school:
            self.prev_e.insert(0, self.existing.previous_school)
        self.prev_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Predicted GCSEs:").grid(row=r, column=2,
                                                          sticky="e", pady=4)
        self.gcse_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.predicted_gcses:
            self.gcse_e.insert(0, self.existing.predicted_gcses)
        self.gcse_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        opts = _subject_options()
        # Chip-style subject editor (item 13): add/remove, capped at 3.
        ttk.Label(form, text="Subjects (max 3):").grid(
            row=r, column=0, sticky="ne", pady=4)
        self.subj_list = tk.Listbox(form, height=3, width=30,
                                     exportselection=False)
        self.subj_list.grid(row=r, column=1, sticky="w", padx=6)
        self._subjects: list[str] = (list(self.existing.subjects)
                                     if self.existing else [])
        for s in self._subjects:
            self.subj_list.insert("end", s)
        picker = ttk.Frame(form)
        picker.grid(row=r, column=2, columnspan=2, sticky="w", padx=6)
        self.subj_pick = ttk.Combobox(picker, values=tuple(opts), width=26)
        self.subj_pick.grid(row=0, column=0, columnspan=2, pady=2)
        self.subj_pick.bind("<Return>", lambda _e: self._add_subject())
        ttk.Button(picker, text="Add", width=9,
                    command=self._add_subject).grid(row=1, column=0, pady=2)
        ttk.Button(picker, text="Remove", width=9,
                    command=self._remove_subject).grid(row=1, column=1,
                                                        pady=2)

        r += 1
        ttk.Label(form, text="Reference name:").grid(row=r, column=0,
                                                        sticky="e", pady=4)
        self.refname_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.reference_name:
            self.refname_e.insert(0, self.existing.reference_name)
        self.refname_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Reference contact:").grid(row=r, column=2,
                                                            sticky="e", pady=4)
        self.refcontact_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.reference_contact:
            self.refcontact_e.insert(0, self.existing.reference_contact)
        self.refcontact_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Source:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.source_cb = ttk.Combobox(form, values=SOURCES,
                                         state="readonly", width=18)
        self.source_cb.set(self.existing.application_source
                              if self.existing else DEFAULT_SOURCE)
        self.source_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Submitted:").grid(row=r, column=2,
                                                   sticky="e", pady=4)
        self.sub_e = ttk.Entry(form, width=14)
        self.sub_e.insert(0, (self.existing.submitted_at
                                if self.existing else _today()))
        self.sub_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                         state="readonly", width=22)
        self.status_cb.set(self.existing.status
                              if self.existing else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=70, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        # Inline contact-field validation feedback (item 19).
        r += 1
        self.fb_lbl = ttk.Label(form, text="", foreground="#b00000")
        self.fb_lbl.grid(row=r, column=0, columnspan=4, sticky="w", padx=6)
        for w in (self.email_e, self.phone_e, self.dob_e):
            w.bind("<KeyRelease>", lambda _e: self._revalidate())
            w.bind("<FocusOut>", lambda _e: self._revalidate())

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=4, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _add_subject(self) -> None:
        s = self.subj_pick.get().strip()
        if not s or s in self._subjects:
            return
        if len(self._subjects) >= 3:
            messagebox.showinfo("Subjects", "Maximum of 3 subjects.")
            return
        self._subjects.append(s)
        self.subj_list.insert("end", s)
        self.subj_pick.set("")

    def _remove_subject(self) -> None:
        sel = self.subj_list.curselection()
        if not sel:
            return
        idx = sel[0]
        self.subj_list.delete(idx)
        del self._subjects[idx]

    def _revalidate(self) -> None:
        problems: list[str] = []
        for getter, validator, args in (
                (self.email_e, data._validate_email, ()),
                (self.phone_e, data._validate_phone, ()),
                (self.dob_e, data._validate_date, ("Date of birth",))):
            try:
                validator(getter.get().strip(), *args)
            except ValidationError as e:
                problems.append(str(e))
        if problems:
            self.fb_lbl.configure(text="⚠ " + " · ".join(problems),
                                   foreground="#b00000")
        else:
            self.fb_lbl.configure(text="✓ contact fields look valid",
                                   foreground="#207020")

    def _collect(self) -> dict:
        return {
            "first_name":         self.first_e.get().strip(),
            "last_name":          self.last_e.get().strip(),
            "dob":                self.dob_e.get().strip(),
            "email":              self.email_e.get().strip(),
            "phone":              self.phone_e.get().strip(),
            "address":            self.addr_e.get().strip(),
            "previous_school":    self.prev_e.get().strip(),
            "predicted_gcses":    self.gcse_e.get().strip(),
            "subject_1":          (self._subjects[0]
                                   if len(self._subjects) > 0 else None),
            "subject_2":          (self._subjects[1]
                                   if len(self._subjects) > 1 else None),
            "subject_3":          (self._subjects[2]
                                   if len(self._subjects) > 2 else None),
            "reference_name":     self.refname_e.get().strip(),
            "reference_contact":  self.refcontact_e.get().strip(),
            "application_source": self.source_cb.get().strip(),
            "submitted_at":       self.sub_e.get().strip(),
            "status":             self.status_cb.get().strip(),
            "notes":              self.notes_t.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        payload = self._collect()
        # Required-field check: list EVERY missing field at once.
        missing = data.missing_required(payload)
        if missing:
            messagebox.showerror(
                "Missing required fields",
                "Please complete the following before saving:\n\n  • "
                + "\n  • ".join(missing))
            return
        # Duplicate detection (item 15): warn before persisting.
        dups = data.find_duplicates(
            email=payload["email"] or None,
            first_name=payload["first_name"],
            last_name=payload["last_name"],
            dob=payload["dob"] or None,
            exclude_id=(self.existing.applicant_id
                        if self.existing else None))
        if dups:
            lines = "\n".join(
                f"  {d.applicant_id} — {d.full_name} "
                f"({d.email or 'no email'})" for d in dups)
            if not messagebox.askyesno(
                    "Possible duplicate",
                    f"{len(dups)} existing applicant(s) look similar:\n"
                    f"{lines}\n\nSave anyway?"):
                return
        try:
            if self.existing:
                data.update_applicant(self.existing.applicant_id, payload)
            else:
                data.create_applicant(payload)
        except Exception as e:  # noqa: BLE001 — surface any save failure
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
