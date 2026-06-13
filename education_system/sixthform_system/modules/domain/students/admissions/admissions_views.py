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
from education_system.sixthform_system.modules.domain.students.admissions import (
    admissions as data,
)
from education_system.sixthform_system.modules.domain.students.admissions.admissions import (
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
    WaitlistTab(nb)
    SummaryTab(nb, notebook=nb, drill_tab=all_tab)


def _today() -> str:
    return _dt.date.today().isoformat()


def _subject_options() -> list[str]:
    try:
        from education_system.sixthform_system.modules.domain.academics.subjects import (
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
        rows = list(self._rows)
        if self._sort_col:
            rows.sort(key=lambda a: self._sort_value(self._sort_col, a),
                       reverse=self._sort_reverse)
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
            from education_system.sixthform_system.modules.domain.students.students import (  # noqa: E501
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

        bar = ttk.Frame(dl)
        bar.pack(side="right", fill="y", padx=4, pady=4)
        ttk.Button(bar, text="Add…", command=self._add_doc).pack(
            fill="x", pady=2)
        ttk.Button(bar, text="Set photo…",
                    command=lambda: self._add_doc(force_type="Photo")).pack(
            fill="x", pady=2)
        ttk.Button(bar, text="Open", command=self._open_doc).pack(
            fill="x", pady=2)
        ttk.Button(bar, text="Remove", command=self._remove_doc).pack(
            fill="x", pady=2)

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
        ttk.Button(bar, text="Remove from list",
                    command=self._remove).pack(side="left")
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
