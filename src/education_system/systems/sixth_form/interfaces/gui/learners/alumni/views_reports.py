"""Reports, audit log, admin tab and its import/export/duplicates/trash/saved-search/survey dialogs."""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.learners.alumni import (
    bulk_io as alumni_bulk_io,
    models as alumni_models,
    outcomes as alumni_outcomes,
    records as alumni_records,
    surveys as alumni_surveys,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.learners.alumni.models import (
    ACHIEVEMENT_CATEGORIES,
    Alumnus,
    CAMPAIGN_STATUSES,
    APPLICATION_STATUSES,
    BEQUEST_STATUSES,
    CUSTOM_FIELD_TYPES,
    ERASURE_STATUSES,
    WEBHOOK_EVENT_TYPES,
    CHAPTER_ROLES,
    CONNECTION_KINDS,
    DIRECTORY_CONSENT_SCOPE,
    DONOR_STAGES,
    DRIP_STATUSES,
    JOB_STATUSES,
    JOB_TYPES,
    NEET_STATUSES,
    NEWSLETTER_STATUSES,
    PROFICIENCY_LEVELS,
    RECURRING_FREQS,
    RECURRING_STATUSES,
    SAFEGUARDING_STATUSES,
    SOCIAL_PLATFORMS,
    TRACK_KINDS,
    CONSENT_SCOPES,
    DEFAULT_CAMPAIGN_STATUS,
    DEFAULT_DESTINATION,
    DEFAULT_EDUCATION_STATUS,
    DEFAULT_EVENT_STATUS,
    DEFAULT_LEAVING_REASON,
    DEFAULT_PLEDGE_STATUS,
    DEFAULT_RSVP_STATUS,
    DEFAULT_STATUS,
    DESTINATION_TYPES,
    EDUCATION_STATUSES,
    EMAIL_LABELS,
    EVENT_STATUSES,
    EVENT_TYPES,
    GENDER_OPTIONS,
    LEAVING_REASONS,
    MENTORSHIP_STATUSES,
    PAYMENT_METHODS,
    PHONE_LABELS,
    PLEDGE_STATUSES,
    RSVP_STATUSES,
    SALARY_BANDS,
    SECTORS,
    SESSION_FORMATS,
    STATUSES,
    VOLUNTEER_ACTIVITY_TYPES,
)
from education_system.systems.sixth_form.domain.learners.alumni.integrations import MEDIA_KINDS
from education_system.systems.sixth_form.domain.learners.alumni.compliance import PROTECTED_CHARS
from education_system.systems.sixth_form.domain.learners.alumni.engagement import (
    CHAPTER_KINDS,
    MILESTONE_KINDS,
)
from education_system.systems.sixth_form.domain.learners.alumni.comms import (
    COMM_CHANNELS,
    COMM_STATUSES,
)
from education_system.systems.sixth_form.domain.learners.alumni.db import ValidationError


# ══ Reports tab (top-level) ══════════════════════════════════════

class ReportsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Reports")
        wrap = ttk.Frame(self.frame, padding=14)
        wrap.pack(fill="both", expand=True)
        ttk.Label(wrap, text="Alumni reports & analytics",
                    font=("TkDefaultFont", 12, "bold")
                    ).pack(anchor="w", pady=(0, 10))
        ttk.Label(wrap,
                    text=("Run a report to see the data, then use "
                           "Export where supported."),
                    foreground="#555"
                    ).pack(anchor="w", pady=(0, 8))

        reports: list[tuple[str, Callable[[], None]]] = [
            ("KS5 destinations CSV (DfE-style)",  self._ks5),
            ("Sustained destinations (1/3/5y)",  self._sustained),
            ("Cohort comparison",                  self._cohort),
            ("University success rates",           self._uni),
            ("Apprenticeship outcomes",            self._appren),
            ("Disadvantage gap",                   self._gap),
            ("Geographic distribution",            self._geo),
            ("Sector breakdown",                   self._sector),
            ("'Where are they now' site",         self._wan),
        ]
        grid = ttk.Frame(wrap); grid.pack(fill="x")
        for i, (label, cb) in enumerate(reports):
            ttk.Button(grid, text=label, command=cb, width=42
                         ).grid(row=i // 2, column=i % 2,
                                  padx=6, pady=4, sticky="w")

    # report launchers ------------------------------------------------

    def _prompt_year(self, title: str = "Leaving year"
                       ) -> str | None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title(title); win.transient(self.frame.winfo_toplevel())
        grab_when_viewable(win)
        form = ttk.Frame(win, padding=12); form.pack()
        ttk.Label(form, text="Leaving year (YYYY):").grid(
            row=0, column=0, sticky="e", padx=4)
        e = ttk.Entry(form, width=10); e.grid(row=0, column=1,
                                                  sticky="w")
        result: dict[str, str | None] = {"y": None}

        def ok() -> None:
            v = e.get().strip()
            if v: result["y"] = v
            win.destroy()

        bar = ttk.Frame(form); bar.grid(row=1, column=0, columnspan=2,
                                          pady=(8, 0))
        ttk.Button(bar, text="OK", command=ok).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)
        win.wait_window()
        return result["y"]

    def _ks5(self) -> None:
        year = self._prompt_year()
        if not year: return
        try:
            rows = alumni_outcomes.ks5_destinations_rows(leaving_year=year)
        except ValidationError as e:
            messagebox.showerror("KS5 destinations", str(e)); return
        cols = ["uln", "surname", "forename", "dob",
                "destination_category", "destination_type",
                "destination_detail", "country", "region"]
        ReportTableDialog(
            self.frame.winfo_toplevel(),
            title=f"KS5 destinations {year}",
            columns=cols,
            rows=[[r.get(c, "") for c in cols] for r in rows],
            csv_export=lambda path: alumni_outcomes.ks5_destinations_csv(
                leaving_year=year, out_path=path))

    def _sustained(self) -> None:
        year = self._prompt_year()
        if not year: return
        try:
            rows = alumni_outcomes.sustained_destinations(leaving_year=year)
        except ValidationError as e:
            messagebox.showerror("Sustained destinations",
                                    str(e)); return
        ReportTableDialog(
            self.frame.winfo_toplevel(),
            title=f"Sustained destinations — cohort {year}",
            columns=["alumni_id", "name", "+1y", "+3y", "+5y"],
            rows=[[r.alumni_id, r.full_name,
                    r.year_plus_1, r.year_plus_3, r.year_plus_5]
                   for r in rows])

    def _cohort(self) -> None:
        cc = alumni_outcomes.cohort_comparison()
        cols = ["year", "total"] + list(cc.destinations)
        rs: list[list] = []
        for y in cc.years:
            row = [y, cc.totals[y]]
            for d in cc.destinations:
                row.append(cc.counts.get(y, {}).get(d, 0))
            rs.append(row)
        ReportTableDialog(
            self.frame.winfo_toplevel(),
            title="Cohort comparison",
            columns=cols, rows=rs)

    def _uni(self) -> None:
        rows = alumni_outcomes.university_success_rates()

        def pct(n: int, total: int) -> str:
            return f"{100 * n / total:.0f}%" if total else "—"

        rs = [[r.leaving_year, r.uni_total,
                f"{r.russell} ({pct(r.russell, r.uni_total)})",
                f"{r.oxbridge} ({pct(r.oxbridge, r.uni_total)})",
                f"{r.top_third} ({pct(r.top_third, r.uni_total)})"]
               for r in rows]
        ReportTableDialog(
            self.frame.winfo_toplevel(),
            title="University success rates",
            columns=["year", "uni_total", "russell",
                      "oxbridge", "top_third"],
            rows=rs)

    def _appren(self) -> None:
        rows = alumni_outcomes.apprenticeship_outcomes()
        ReportTableDialog(
            self.frame.winfo_toplevel(),
            title="Apprenticeship outcomes",
            columns=["year", "level", "provider", "count"],
            rows=[[r.leaving_year, r.level, r.provider, r.count]
                   for r in rows])

    def _gap(self) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title("Disadvantage gap")
        win.transient(self.frame.winfo_toplevel()); grab_when_viewable(win)
        form = ttk.Frame(win, padding=12); form.pack()
        ttk.Label(form, text="Tag:").grid(row=0, column=0,
                                              sticky="e", padx=4)
        tag_e = ttk.Entry(form, width=24)
        tag_e.insert(0, "Bursary recipient")
        tag_e.grid(row=0, column=1, sticky="w")
        ttk.Label(form, text="Year (blank = all):").grid(
            row=1, column=0, sticky="e", padx=4)
        year_e = ttk.Entry(form, width=10)
        year_e.grid(row=1, column=1, sticky="w")

        def go() -> None:
            tag = tag_e.get().strip() or "Bursary recipient"
            year = year_e.get().strip() or None
            try:
                rows = alumni_outcomes.disadvantage_gap(tag_name=tag,
                                                 leaving_year=year)
            except ValidationError as e:
                messagebox.showerror("Disadvantage gap", str(e))
                return
            win.destroy()
            ReportTableDialog(
                self.frame.winfo_toplevel(),
                title=(f"Disadvantage gap — {tag}"
                         + (f", {year}" if year else "")),
                columns=["destination", "cohort",
                          "cohort %", "tagged", "tagged %", "gap %"],
                rows=[[r.destination_type, r.cohort_count,
                        f"{r.cohort_pct:.1f}%",
                        r.tagged_count,
                        f"{r.tagged_pct:.1f}%",
                        f"{r.gap_pct:+.1f}%"] for r in rows])

        bar = ttk.Frame(form); bar.grid(row=2, column=0, columnspan=2,
                                          pady=(10, 0))
        ttk.Button(bar, text="Run", command=go).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _geo(self) -> None:
        rows = alumni_outcomes.geographic_distribution()
        ReportTableDialog(
            self.frame.winfo_toplevel(),
            title="Geographic distribution",
            columns=["country", "region", "count"],
            rows=[[g.country, g.region, g.count] for g in rows])

    def _sector(self) -> None:
        rows = alumni_outcomes.sector_breakdown()
        ReportTableDialog(
            self.frame.winfo_toplevel(),
            title="Sector breakdown",
            columns=["sector", "count", "%"],
            rows=[[r.sector, r.count, f"{r.pct:.1f}%"]
                   for r in rows])

    def _wan(self) -> None:
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
        out = filedialog.askdirectory(
            parent=self.frame.winfo_toplevel(),
            title="Choose output folder")
        if not out: return
        try:
            n = alumni_outcomes.generate_where_are_they_now(out)
        except Exception as e:
            messagebox.showerror("Generation failed", str(e))
            return
        messagebox.showinfo(
            "Generated",
            f"Wrote {n} profile page(s) + index.html to:\n{out}\n\n"
            "Only alumni with active 'Photo Use' consent are "
            "included.")


class ReportTableDialog:
    """Generic results window — a treeview + Export CSV button. Pass
    ``csv_export`` to override the default in-memory CSV with a
    bespoke writer (e.g. the DfE one)."""

    def __init__(self, parent: tk.Misc, *, title: str,
                 columns: list[str], rows: list[list],
                 csv_export: Callable[[str], str] | None = None
                 ) -> None:
        self.columns = columns
        self.rows = rows
        self.csv_export = csv_export
        self.win = tk.Toplevel(parent)
        self.win.title(title); self.win.geometry("1000x600")
        self.win.transient(parent)
        tree = ttk.Treeview(self.win, columns=columns,
                               show="headings")
        for c in columns:
            tree.heading(c, text=str(c).replace("_", " ").title())
            tree.column(c, width=max(90, min(360,
                                              len(str(c)) * 18)),
                         anchor="w")
        for r in rows:
            tree.insert("", "end", values=tuple(r))
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Label(self.win, text=f"{len(rows)} row(s)",
                    foreground="#555",
                    padding=(8, 0)).pack(anchor="w")
        bar = ttk.Frame(self.win); bar.pack(fill="x", padx=8,
                                                pady=(4, 8))
        ttk.Button(bar, text="Export CSV…",
                    command=self._export).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")

    def _export(self) -> None:
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            if self.csv_export is not None:
                self.csv_export(path)
            else:
                # Generic CSV from displayed columns/rows
                import csv as _csv
                with open(path, "w", newline="",
                            encoding="utf-8") as f:
                    w = _csv.writer(f)
                    w.writerow(self.columns)
                    for r in self.rows:
                        w.writerow(r)
        except Exception as e:
            messagebox.showerror("Export failed", str(e)); return
        messagebox.showinfo("Exported", f"Wrote {path}")


# ══ Audit log dialog ═════════════════════════════════════════════

class AuditLogDialog:
    def __init__(self, parent: tk.Misc, alumni_id: int) -> None:
        a = alumni_records.get_alumnus(alumni_id)
        self.win = tk.Toplevel(parent)
        self.win.title(f"Audit log — #{alumni_id} "
                         f"{a.display_name if a else ''}")
        self.win.geometry("960x520"); self.win.transient(parent)
        cols = ("changed_at", "changed_by", "field",
                "old_value", "new_value")
        tree = ttk.Treeview(self.win, columns=cols, show="headings")
        widths = {"changed_at": 160, "changed_by": 110,
                  "field": 180, "old_value": 220,
                  "new_value": 220}
        for c in cols:
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=widths[c], anchor="w")
        for r in alumni_records.list_audit_log(alumni_id):
            tree.insert("", "end", values=(
                r["changed_at"], r["changed_by"] or "—",
                r["field"], r["old_value"] or "",
                r["new_value"] or ""))
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(self.win, text="Close",
                    command=self.win.destroy).pack(pady=(0, 8))


# ══ Admin tab (top-level) ════════════════════════════════════════

class AdminTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Admin")
        wrap = ttk.Frame(self.frame, padding=14)
        wrap.pack(fill="both", expand=True)
        ttk.Label(wrap, text="Operational tools",
                    font=("TkDefaultFont", 12, "bold")
                    ).pack(anchor="w", pady=(0, 10))
        ttk.Label(
            wrap,
            text=("Bulk import / export, deduplication, soft-delete "
                   "trash, saved searches and surveys."),
            foreground="#555"
        ).pack(anchor="w", pady=(0, 8))
        buttons: list[tuple[str, Callable[[], None]]] = [
            ("Bulk CSV import…",  self._import),
            ("Bulk CSV export…",  self._export),
            ("Find duplicates",    self._dedupe),
            ("Merge by id…",       self._merge),
            ("Soft-delete trash",   self._trash),
            ("Saved searches",     self._saved),
            ("Surveys",             self._surveys),
        ]
        grid = ttk.Frame(wrap); grid.pack(fill="x")
        for i, (label, cb) in enumerate(buttons):
            ttk.Button(grid, text=label, width=32,
                         command=cb
                         ).grid(row=i // 2, column=i % 2,
                                  padx=6, pady=4, sticky="w")

    # action handlers --------------------------------------------------

    def _import(self) -> None:
        ImportCsvDialog(self.frame.winfo_toplevel())

    def _export(self) -> None:
        ExportCsvDialog(self.frame.winfo_toplevel())

    def _dedupe(self) -> None:
        DuplicatesDialog(self.frame.winfo_toplevel())

    def _merge(self) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title("Merge alumni")
        win.transient(self.frame.winfo_toplevel()); grab_when_viewable(win)
        form = ttk.Frame(win, padding=12); form.pack()
        ttk.Label(form, text="Keep #id (survivor):").grid(
            row=0, column=0, sticky="e", padx=4, pady=3)
        keep_e = ttk.Entry(form, width=10); keep_e.grid(
            row=0, column=1, sticky="w")
        ttk.Label(form, text="Merge #id (absorbed):").grid(
            row=1, column=0, sticky="e", padx=4, pady=3)
        other_e = ttk.Entry(form, width=10); other_e.grid(
            row=1, column=1, sticky="w")

        def go() -> None:
            try:
                keep = int(keep_e.get().strip())
                other = int(other_e.get().strip())
            except ValueError:
                messagebox.showerror("Merge", "IDs must be integers")
                return
            if not messagebox.askyesno(
                    "Merge", f"Merge #{other} into #{keep}? "
                                "Irreversible."):
                return
            try:
                alumni_records.merge_alumni(keep, other)
            except Exception as e:
                messagebox.showerror("Merge failed", str(e)); return
            messagebox.showinfo("Merged",
                                  f"Result: alumnus #{keep}")
            win.destroy()

        bar = ttk.Frame(form); bar.grid(row=2, column=0,
                                          columnspan=2,
                                          pady=(10, 0))
        ttk.Button(bar, text="Merge", command=go).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _trash(self) -> None:
        TrashDialog(self.frame.winfo_toplevel())

    def _saved(self) -> None:
        SavedSearchesDialog(self.frame.winfo_toplevel())

    def _surveys(self) -> None:
        SurveysDialog(self.frame.winfo_toplevel())


# ── Import dialog ────────────────────────────────────────────────

class ImportCsvDialog:
    def __init__(self, parent: tk.Misc) -> None:
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
        path = filedialog.askopenfilename(
            parent=parent, title="Choose CSV to import",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.rows = alumni_bulk_io.parse_import_csv(path)
        except Exception as e:
            messagebox.showerror("Import", str(e)); return
        if not self.rows:
            messagebox.showinfo("Import", "CSV is empty.")
            return
        self.headers = list(self.rows[0].keys())
        self.mapping = alumni_bulk_io.suggest_import_mapping(self.headers)
        self.win = tk.Toplevel(parent); self.win.title(
            f"Bulk import — {len(self.rows)} row(s)")
        self.win.geometry("780x540")
        self.win.transient(parent); grab_when_viewable(self.win)

        top = ttk.Frame(self.win, padding=10); top.pack(fill="x")
        ttk.Label(top,
                    text=("Map CSV columns to alumnus fields. "
                           "Leave blank to ignore a column."),
                    foreground="#555"
                    ).pack(anchor="w")
        ttk.Label(top,
                    text=f"Source: {path}",
                    foreground="#888").pack(anchor="w", pady=(2, 0))

        body = ttk.Frame(self.win, padding=(10, 4, 10, 4))
        body.pack(fill="both", expand=True)
        self.combos: dict[str, ttk.Combobox] = {}
        field_options = ("",) + tuple(
            f for f in alumni_records._AUDITABLE_FIELDS) + (
            "original_student_id",)
        # Dedup the options (original_student_id is in
        # _AUDITABLE_FIELDS already on this codebase, but include
        # explicitly for safety).
        seen: set[str] = set()
        options: list[str] = []
        for f in field_options:
            if f not in seen:
                seen.add(f); options.append(f)
        for i, h in enumerate(self.headers):
            ttk.Label(body, text=h,
                        anchor="e").grid(row=i, column=0,
                                            sticky="e", padx=4,
                                            pady=2)
            cb = ttk.Combobox(body, values=options,
                                 state="readonly", width=24)
            cb.set(self.mapping.get(h, ""))
            cb.grid(row=i, column=1, sticky="w", padx=4)
            self.combos[h] = cb

        bar = ttk.Frame(self.win, padding=10); bar.pack(fill="x")
        ttk.Button(bar, text="Dry-run preview",
                    command=self._preview).pack(side="left")
        ttk.Button(bar, text="Commit import",
                    command=self._apply).pack(side="left", padx=6)
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")

    def _current_mapping(self) -> dict[str, str]:
        return {h: cb.get().strip()
                  for h, cb in self.combos.items() if cb.get().strip()}

    def _preview(self) -> None:
        try:
            prev = alumni_bulk_io.preview_import(
                self.rows, self._current_mapping())
        except Exception as e:
            messagebox.showerror("Preview failed", str(e)); return
        msg = (f"create: {prev.will_create}\n"
                f"update: {prev.will_update}\n"
                f"skip:   {prev.will_skip}")
        if prev.errors:
            msg += "\n\nFirst issues:\n" + "\n".join(
                f"  row {r}: {m}" for r, m in prev.errors[:5])
        messagebox.showinfo("Dry-run preview", msg)

    def _apply(self) -> None:
        if not messagebox.askyesno(
                "Commit",
                "Apply this import? The dry-run will run first."):
            return
        mapping = self._current_mapping()
        try:
            prev = alumni_bulk_io.preview_import(self.rows, mapping)
            if prev.errors and not messagebox.askyesno(
                    "Continue?",
                    f"{prev.will_skip} row(s) will be skipped due "
                    "to errors. Continue?"):
                return
            result = alumni_bulk_io.apply_import(self.rows, mapping)
        except Exception as e:
            messagebox.showerror("Import failed", str(e)); return
        messagebox.showinfo(
            "Imported",
            f"created={result.created}  updated={result.updated}  "
            f"skipped={result.skipped}")
        self.win.destroy()


# ── Export dialog ────────────────────────────────────────────────

class ExportCsvDialog:
    def __init__(self, parent: tk.Misc) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title("Bulk CSV export"); self.win.geometry(
            "500x520")
        self.win.transient(parent); grab_when_viewable(self.win)
        ttk.Label(self.win,
                    text="Pick the columns to include in the export.",
                    foreground="#555", padding=(12, 10, 12, 4)
                    ).pack(anchor="w")
        body = ttk.Frame(self.win, padding=(12, 4, 12, 4))
        body.pack(fill="both", expand=True)
        self.vars: dict[str, tk.BooleanVar] = {}
        for i, (field, sens) in enumerate(alumni_models.EXPORT_FIELDS):
            v = tk.BooleanVar(value=sens not in
                                ("internal", "sensitive"))
            ttk.Checkbutton(body, text=f"{field} ({sens})",
                              variable=v
                              ).grid(row=i // 2, column=i % 2,
                                       sticky="w", padx=6, pady=1)
            self.vars[field] = v
        self.redact_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.win,
                          text="Apply consent-based PII redaction",
                          variable=self.redact_var).pack(
            anchor="w", padx=12, pady=(6, 0))
        bar = ttk.Frame(self.win, padding=12); bar.pack(fill="x")
        ttk.Button(bar, text="Export…",
                    command=self._export).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")

    def _export(self) -> None:
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
        cols = [f for f, v in self.vars.items() if v.get()]
        if not cols:
            messagebox.showerror("Export", "Pick at least one column.")
            return
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            alumni_bulk_io.export_alumni_csv(
                out_path=path, columns=cols,
                respect_consent=self.redact_var.get())
        except Exception as e:
            messagebox.showerror("Export failed", str(e)); return
        messagebox.showinfo("Exported", f"Wrote {path}")
        self.win.destroy()


# ── Duplicates dialog ────────────────────────────────────────────

class DuplicatesDialog:
    def __init__(self, parent: tk.Misc) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title("Duplicate candidates")
        self.win.geometry("900x520")
        self.win.transient(parent); grab_when_viewable(self.win)
        top = ttk.Frame(self.win, padding=8); top.pack(fill="x")
        ttk.Label(top, text="Threshold:").pack(side="left")
        self.thresh_e = ttk.Entry(top, width=6)
        self.thresh_e.insert(0, "0.85")
        self.thresh_e.pack(side="left", padx=4)
        ttk.Button(top, text="Scan",
                    command=self.refresh).pack(side="left")
        cols = ("score", "keep", "keep_name", "keep_dob",
                "merge", "merge_name", "merge_dob")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"score": 60, "keep": 50, "keep_name": 180,
                  "keep_dob": 100, "merge": 60,
                  "merge_name": 180, "merge_dob": 100}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win, padding=8); bar.pack(fill="x")
        ttk.Button(bar, text="Merge selected (keep → absorb)",
                    command=self._merge).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        try:
            t = float(self.thresh_e.get())
        except ValueError:
            t = 0.85
        for i in self.tree.get_children(): self.tree.delete(i)
        for c in alumni_records.find_duplicates(threshold=t):
            self.tree.insert("", "end",
                              iid=f"{c.primary.alumni_id}:"
                                    f"{c.other.alumni_id}",
                              values=(f"{c.score:.2f}",
                                       c.primary.alumni_id,
                                       c.primary.full_name,
                                       c.primary.dob or "—",
                                       c.other.alumni_id,
                                       c.other.full_name,
                                       c.other.dob or "—"))

    def _merge(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        keep_id, other_id = sel[0].split(":")
        if not messagebox.askyesno(
                "Merge", f"Merge #{other_id} into #{keep_id}? "
                            "Irreversible."):
            return
        try:
            alumni_records.merge_alumni(int(keep_id), int(other_id))
        except Exception as e:
            messagebox.showerror("Merge failed", str(e)); return
        self.refresh()


# ── Trash dialog ─────────────────────────────────────────────────

class TrashDialog:
    def __init__(self, parent: tk.Misc) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title("Soft-delete trash"); self.win.geometry(
            "780x440")
        self.win.transient(parent); grab_when_viewable(self.win)
        cols = ("id", "name", "leaving_year", "deleted_at")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"id": 60, "name": 220, "leaving_year": 100,
                  "deleted_at": 200}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win, padding=8); bar.pack(fill="x")
        ttk.Button(bar, text="Restore",
                    command=self._restore).pack(side="left")
        ttk.Button(bar, text="Purge",
                    command=self._purge).pack(side="left", padx=4)
        ttk.Button(bar, text="Purge all expired",
                    command=self._purge_expired).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for a in alumni_records.list_soft_deleted():
            self.tree.insert("", "end", iid=str(a.alumni_id),
                              values=(a.alumni_id, a.full_name,
                                       a.leaving_year or "—",
                                       a.deleted_at or "—"))

    def _restore(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        try:
            alumni_records.restore_alumnus(int(sel[0]))
        except Exception as e:
            messagebox.showerror("Restore failed", str(e)); return
        self.refresh()

    def _purge(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        if not messagebox.askyesno(
                "Purge", "Permanently delete this alumnus? "
                            "Irreversible."):
            return
        alumni_records.purge_alumnus(int(sel[0]))
        self.refresh()

    def _purge_expired(self) -> None:
        n = alumni_records.purge_expired_soft_deletes()
        messagebox.showinfo(
            "Purged", f"Removed {n} alumnus/alumni older than "
                       f"{alumni_models.SOFT_DELETE_UNDO_DAYS} days.")
        self.refresh()


# ── Saved searches dialog ────────────────────────────────────────

class SavedSearchesDialog:
    def __init__(self, parent: tk.Misc) -> None:
        self.parent = parent
        self.win = tk.Toplevel(parent)
        self.win.title("Saved searches"); self.win.geometry(
            "780x440")
        self.win.transient(parent); grab_when_viewable(self.win)
        cols = ("id", "name", "filters", "owner", "created_at")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 180, "filters": 300,
                  "owner": 80, "created_at": 160}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win, padding=8); bar.pack(fill="x")
        ttk.Button(bar, text="New…",
                    command=self._new).pack(side="left")
        ttk.Button(bar, text="Run",
                    command=self._run).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in alumni_bulk_io.list_saved_searches():
            self.tree.insert(
                "", "end", iid=str(s.search_id),
                values=(s.search_id, s.name,
                         ", ".join(f"{k}={v}" for k, v
                                    in s.filters.items()),
                         s.owner_staff_id or "",
                         s.created_at))

    def _selected_name(self) -> str | None:
        sel = self.tree.selection()
        if not sel: return None
        sid = int(sel[0])
        rows = alumni_bulk_io.list_saved_searches()
        m = next((s for s in rows if s.search_id == sid), None)
        return m.name if m else None

    def _new(self) -> None:
        win = tk.Toplevel(self.win); win.title("New saved search")
        win.transient(self.win); grab_when_viewable(win)
        form = ttk.Frame(win, padding=12); form.pack()
        entries: dict[str, ttk.Widget] = {}

        def row(label: str, w: tk.Widget) -> None:
            r = len(entries)
            ttk.Label(form, text=label + ":").grid(
                row=r, column=0, sticky="e", padx=4, pady=2)
            w.grid(row=r, column=1, sticky="w", padx=4)
            entries[label] = w

        row("Name",        ttk.Entry(form, width=28))
        row("Year",        ttk.Entry(form, width=12))
        dest_cb = ttk.Combobox(form, values=("",) + DESTINATION_TYPES,
                                  state="readonly", width=22)
        row("Destination", dest_cb)
        row("Employer",    ttk.Entry(form, width=28))
        row("University",  ttk.Entry(form, width=28))
        sec_cb = ttk.Combobox(form, values=("",) + SECTORS,
                                 state="readonly", width=22)
        row("Sector",      sec_cb)
        row("Country",     ttk.Entry(form, width=20))
        row("Tag",         ttk.Entry(form, width=20))
        opt_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Contactable only",
                          variable=opt_var).grid(
            row=len(entries), column=1, sticky="w", padx=4)

        def get(label: str) -> str:
            w = entries[label]
            if isinstance(w, ttk.Combobox):
                return w.get().strip()
            return w.get().strip()  # type: ignore[attr-defined]

        def save() -> None:
            name = get("Name")
            if not name:
                messagebox.showerror("Save", "Name is required")
                return
            filters: dict[str, Any] = {}
            mappings = (
                ("Year",        "leaving_year"),
                ("Destination", "destination_type"),
                ("Employer",    "employer"),
                ("University",  "university"),
                ("Sector",      "sector"),
                ("Country",     "country"),
                ("Tag",         "tag"),
            )
            for lbl, key in mappings:
                v = get(lbl)
                if v:
                    filters[key] = v
            if opt_var.get():
                filters["contactable_only"] = True
            try:
                alumni_bulk_io.save_search(name, filters, replace=True)
            except Exception as e:
                messagebox.showerror("Save failed", str(e))
                return
            win.destroy(); self.refresh()

        bar = ttk.Frame(form); bar.grid(row=len(entries) + 1,
                                          column=0, columnspan=2,
                                          pady=(10, 0))
        ttk.Button(bar, text="Save", command=save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _run(self) -> None:
        name = self._selected_name()
        if not name: return
        try:
            rows = alumni_bulk_io.run_saved_search(name)
        except Exception as e:
            messagebox.showerror("Run failed", str(e)); return
        ReportTableDialog(
            self.win, title=f"Saved search — {name}",
            columns=["id", "name", "year", "destination",
                      "employer", "email", "status"],
            rows=[[a.alumni_id, a.full_name, a.leaving_year or "—",
                    a.destination_type,
                    a.current_employer or "—", a.email or "—",
                    a.status] for a in rows])

    def _delete(self) -> None:
        name = self._selected_name()
        if not name: return
        if not messagebox.askyesno(
                "Delete", f"Delete saved search '{name}'?"):
            return
        alumni_bulk_io.delete_saved_search(name)
        self.refresh()


# ── Surveys dialog ───────────────────────────────────────────────

class SurveysDialog:
    def __init__(self, parent: tk.Misc) -> None:
        self.parent = parent
        self.win = tk.Toplevel(parent)
        self.win.title("Surveys"); self.win.geometry("860x500")
        self.win.transient(parent); grab_when_viewable(self.win)
        cols = ("id", "name", "status", "invited", "sent",
                "completed", "created_at")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 220, "status": 90,
                  "invited": 70, "sent": 70, "completed": 80,
                  "created_at": 160}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win, padding=8); bar.pack(fill="x")
        ttk.Button(bar, text="New survey…",
                    command=self._new).pack(side="left")
        ttk.Button(bar, text="Invite cohort…",
                    command=self._invite).pack(side="left", padx=4)
        ttk.Button(bar, text="Responses",
                    command=self._responses).pack(side="left",
                                                     padx=4)
        ttk.Button(bar, text="Close survey",
                    command=self._close).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left")
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in alumni_surveys.list_surveys():
            st = alumni_surveys.survey_stats(s.survey_id)
            self.tree.insert("", "end", iid=str(s.survey_id),
                              values=(s.survey_id, s.name, s.status,
                                       st.invited, st.sent,
                                       st.completed, s.created_at))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _new(self) -> None:
        win = tk.Toplevel(self.win); win.title("New survey")
        win.transient(self.win); grab_when_viewable(win)
        form = ttk.Frame(win, padding=12); form.pack(fill="both",
                                                          expand=True)
        ttk.Label(form, text="Name:").grid(row=0, column=0,
                                                sticky="e", padx=4,
                                                pady=3)
        name_e = ttk.Entry(form, width=40)
        name_e.grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(form, text="Description:").grid(
            row=1, column=0, sticky="ne", padx=4, pady=3)
        desc_t = tk.Text(form, width=40, height=2)
        desc_t.grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(form,
                    text="Questions (one per line: key | prompt | "
                          "type):",
                    foreground="#555").grid(
            row=2, column=0, columnspan=2,
            sticky="w", padx=4, pady=(8, 0))
        ttk.Label(form,
                    text=(f"Allowed types: "
                           f"{', '.join(sorted(alumni_surveys.SURVEY_QUESTION_TARGETS))}"),
                    foreground="#888").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=4)
        qs_t = tk.Text(form, width=60, height=10)
        qs_t.insert("1.0",
                       "role | What's your current role? | "
                       "current_role\n"
                       "employer | Who do you work for? | "
                       "current_employer\n"
                       "feedback | Anything to share? | freeform\n")
        qs_t.grid(row=4, column=0, columnspan=2,
                    sticky="w", padx=4)

        def save() -> None:
            qs: list[dict[str, str]] = []
            for line in qs_t.get("1.0", "end").splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 2:
                    continue
                qs.append({
                    "key":    parts[0],
                    "prompt": parts[1],
                    "type":   parts[2] if len(parts) >= 3
                                else "freeform",
                })
            try:
                alumni_surveys.create_survey(
                    name_e.get().strip(), qs,
                    description=desc_t.get("1.0",
                                              "end").strip() or None)
            except Exception as e:
                messagebox.showerror("Save failed", str(e))
                return
            win.destroy(); self.refresh()

        bar = ttk.Frame(form); bar.grid(row=5, column=0,
                                          columnspan=2,
                                          pady=(12, 0))
        ttk.Button(bar, text="Create",
                    command=save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _invite(self) -> None:
        sid = self._selected_id()
        if sid is None: return
        win = tk.Toplevel(self.win); win.title("Invite cohort")
        win.transient(self.win); grab_when_viewable(win)
        form = ttk.Frame(win, padding=12); form.pack()
        ttk.Label(form, text="Leaving year (blank = all):").grid(
            row=0, column=0, sticky="e", padx=4, pady=3)
        year_e = ttk.Entry(form, width=8)
        year_e.grid(row=0, column=1, sticky="w")
        ttk.Label(form, text="Sender staff id:").grid(
            row=1, column=0, sticky="e", padx=4, pady=3)
        staff_e = ttk.Entry(form, width=12)
        staff_e.grid(row=1, column=1, sticky="w")

        def go() -> None:
            filters: dict[str, Any] = {"status": "Active"}
            if year_e.get().strip():
                filters["leaving_year"] = year_e.get().strip()
            try:
                sent, skipped = alumni_surveys.send_survey_invitations(
                    sid, filters,
                    staff_id=staff_e.get().strip() or None)
            except Exception as e:
                messagebox.showerror("Invite failed", str(e))
                return
            messagebox.showinfo(
                "Invitations sent",
                f"sent={sent}  skipped={skipped}")
            win.destroy(); self.refresh()

        bar = ttk.Frame(form); bar.grid(row=2, column=0,
                                          columnspan=2,
                                          pady=(10, 0))
        ttk.Button(bar, text="Send", command=go).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _responses(self) -> None:
        sid = self._selected_id()
        if sid is None: return
        resps = alumni_surveys.list_survey_responses(sid)
        win = tk.Toplevel(self.win)
        win.title(f"Responses — survey #{sid}")
        win.geometry("760x500"); win.transient(self.win)
        txt = tk.Text(win, wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        if not resps:
            txt.insert("end", "(no responses)")
        for r in resps:
            txt.insert("end",
                          f"Invitation #{r.invitation_id}  "
                          f"submitted {r.submitted_at}\n")
            for k, v in r.answers.items():
                txt.insert("end", f"  {k}: {v}\n")
            txt.insert("end", "\n")
        txt.configure(state="disabled")
        ttk.Button(win, text="Close",
                    command=win.destroy).pack(pady=(0, 8))

    def _close(self) -> None:
        sid = self._selected_id()
        if sid is None: return
        try:
            alumni_surveys.close_survey(sid)
        except Exception as e:
            messagebox.showerror("Close failed", str(e)); return
        self.refresh()

    def _delete(self) -> None:
        sid = self._selected_id()
        if sid is None: return
        if not messagebox.askyesno(
                "Delete",
                "Delete survey + invitations + responses?"):
            return
        alumni_surveys.delete_survey(sid)
        self.refresh()
