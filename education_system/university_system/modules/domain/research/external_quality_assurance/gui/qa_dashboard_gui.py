"""External Quality Assurance dashboard — OfS / TEF / REF.

Four tabs (Overview, OfS, TEF, REF). Each framework tab combines computed
metrics, full data-entry CRUD for the relevant tables, and an "Export
submission" button that writes a CSV / JSON to disk.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, simpledialog, ttk

from education_system.university_system.modules.domain.research.external_quality_assurance.services import (
    qa_service as qa,
)

logger = logging.getLogger(__name__)


def _user_id_from_auth(auth) -> int | None:
    if not auth or not getattr(auth, "current_user", None):
        return None
    u = auth.current_user
    if isinstance(u, dict):
        return u.get("id") or u.get("user_id")
    return getattr(u, "id", None)


class _TextEditor(tk.Toplevel):
    """Modal multi-line text editor used by TEF / Environment narrative add."""

    def __init__(self, parent, title: str, initial: str = ""):
        super().__init__(parent)
        self.title(title)
        self.geometry("700x500")
        self.transient(parent)
        self.grab_set()
        self.result: str | None = None

        ttk.Label(self, text=title, font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=10, pady=8)
        self.txt = tk.Text(self, wrap=tk.WORD)
        self.txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        if initial:
            self.txt.insert("1.0", initial)

        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(bar, text="Save", command=self._save).pack(side=tk.RIGHT)
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=6)

    def _save(self):
        self.result = self.txt.get("1.0", tk.END).rstrip()
        self.destroy()


class QADashboardGUI:
    def __init__(self, parent=None, app=None):
        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("External Quality Assurance — OfS / TEF / REF")
        self.window.geometry("1300x820")
        self.window.minsize(1100, 720)

        # Reference to the UnifiedManagementGUI so the "Open in…" bar can
        # invoke sibling launchers (show_grade_tracking_gui, etc.).
        self.app = app

        try:
            from education_system.university_system.infrastructure.shared_context import get_auth
            self.auth = get_auth()
        except Exception:
            self.auth = None

        self._build_open_in_bar(self.window)
        self.nb = ttk.Notebook(self.window)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self._build_overview_tab(self.nb)
        self._build_ofs_tab(self.nb)
        self._build_tef_tab(self.nb)
        self._build_ref_tab(self.nb)
        self._refresh_all()

        # #17 — register the live dashboard on the parent app so
        # ``with_qa_context`` can locate it. Cleared on window destroy.
        if self.app is not None:
            try:
                self.app._eqa_dash = self
                self.window.bind("<Destroy>", self._on_destroy, add="+")
            except Exception:
                pass

    def _on_destroy(self, event) -> None:
        if event.widget is not self.window:
            return
        try:
            if getattr(self.app, "_eqa_dash", None) is self:
                self.app._eqa_dash = None
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Open-in bar — deep-links to sibling UnifiedManagementGUI launchers
    # ------------------------------------------------------------------

    _OPEN_IN_TARGETS = (
        ("Grades", "show_grade_tracking_gui"),
        ("Predictive Analytics", "show_predictive_analytics_gui"),
        ("Analytics Dashboard", "show_analytics_dashboard_gui"),
        ("Business Intel", "show_business_intelligence_gui"),
        ("HESA Export", "show_hesa_export_gui"),
        ("Security Dashboard", "show_security_dashboard"),
    )

    def _build_open_in_bar(self, parent):
        bar = ttk.Frame(parent, padding=(10, 6, 10, 0))
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="Open in:",
                  font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        for label, method in self._OPEN_IN_TARGETS:
            btn = ttk.Button(bar, text=label,
                             command=lambda m=method, lab=label: self._open_in(m, lab))
            btn.pack(side=tk.LEFT, padx=2)
            if not (self.app and hasattr(self.app, method)):
                btn.state(["disabled"])

    def _open_in(self, method_name: str, label: str) -> None:
        self._dispatch_with_context(method_name, label, context=None)

    # ------------------------------------------------------------------
    # #7 set_focus + #18 register_open_in
    # ------------------------------------------------------------------

    _TAB_INDEX = {"overview": 0, "ofs": 1, "tef": 2, "ref": 3}

    def set_focus(self, framework: str | None = None,
                   year: int | None = None,
                   uoa: str | None = None) -> None:
        """#7 — Programmatic focus API: switch tab and prefill state vars.

        ``framework`` accepts ``"OfS" | "TEF" | "REF" | "overview"``
        (case-insensitive). ``year`` is applied to whichever tab is
        relevant (B3 spinner for OfS, narrative spinner for TEF).
        ``uoa`` selects the REF combobox value."""
        try:
            if framework:
                key = framework.lower()
                if key in ("ofs", "office for students"):
                    key = "ofs"
                idx = self._TAB_INDEX.get(key)
                if idx is not None:
                    self.nb.select(idx)
            if year is not None:
                if framework and framework.lower() == "tef":
                    self.tef_year.set(int(year))
                else:
                    self.b3_year.set(int(year))
            if uoa:
                self.ref_uoa.set(uoa)
                # Trigger summary refresh if the REF tab provides it
                fn = getattr(self, "_ref_load_summary", None) or getattr(
                    self, "_refresh_uoa_summary", None)
                if callable(fn):
                    try:
                        fn()
                    except Exception:
                        logger.exception("set_focus: REF summary refresh failed")
        except Exception:
            logger.exception("set_focus failed")

    @classmethod
    def register_open_in(cls, label: str,
                           method_name: str,
                           replace: bool = False) -> None:
        """#18 — Extension point: append (or replace) a target on the
        Open-in bar. ``method_name`` must be the name of a method on
        ``UnifiedManagementGUI`` so existing instances dispatch to it."""
        new = list(cls._OPEN_IN_TARGETS)
        if replace:
            new = [(lab, m) for lab, m in new if lab != label]
        else:
            for lab, _ in new:
                if lab == label:
                    return
        new.append((label, method_name))
        cls._OPEN_IN_TARGETS = tuple(new)

    def _dispatch_with_context(self, method_name: str, label: str,
                                context: dict | None) -> None:
        """Stash ``context`` on the parent app (matches the codebase's
        ``_last_academic_context`` convention) then invoke its ``show_*``
        launcher. Receivers that read the context prefilter; receivers
        that don't simply open at their default state."""
        if not self.app:
            messagebox.showinfo(
                "Not available",
                "Cross-module navigation requires the main GUI; open this dashboard "
                "from the main menu rather than standalone.",
                parent=self.window,
            )
            return
        fn = getattr(self.app, method_name, None)
        if fn is None:
            messagebox.showwarning("Not available",
                                   f"{label} is not registered on this build.",
                                   parent=self.window)
            return
        try:
            self.app._last_academic_context = context
        except Exception:
            pass
        try:
            fn()
        except Exception as exc:
            logger.exception("Open-in %s failed", method_name)
            messagebox.showerror("Failed to open",
                                 f"Could not open {label}: {exc}",
                                 parent=self.window)

    # ------------------------------------------------------------------
    # Drill-through helpers (EQA → other GUIs)
    #
    # Each returns the context dict it would push, so unit tests / callers
    # can verify the payload without launching a Toplevel. The context
    # contract is a flat dict; all keys are optional from the receiver's
    # point of view.
    # ------------------------------------------------------------------

    def _selected_b3(self) -> dict | None:
        sel = getattr(self, "b3_tree", None) and self.b3_tree.selection()
        if not sel:
            return None
        v = self.b3_tree.item(sel[0])["values"]
        return {
            "cohort_year": int(v[0]) if str(v[0]).isdigit() else None,
            "course": None if v[1] in ("", "(all)") else str(v[1]),
            "metric": str(v[2]),
            "value_pct": v[3],
        }

    def _selected_submission(self) -> dict | None:
        sel = getattr(self, "sub_tree", None) and self.sub_tree.selection()
        if not sel:
            return None
        v = self.sub_tree.item(sel[0])["values"]
        return {"submission_id": int(v[0]), "framework": str(v[1]),
                "submission_year": int(v[2]), "status": str(v[3])}

    def drill_through_b3(self) -> dict | None:
        """1. Open Grades filtered to the cohort behind a B3 row."""
        ctx = self._selected_b3()
        if not ctx:
            messagebox.showinfo("Pick a row",
                                "Select a B3 metric row first.", parent=self.window)
            return None
        payload = {"source": "eqa.b3", "cohort_year": ctx["cohort_year"],
                   "course": ctx["course"], "metric": ctx["metric"]}
        self._dispatch_with_context("show_grade_tracking_gui", "Grades", payload)
        return payload

    def open_predictive_for_cohort(self) -> dict:
        """2. Open Predictive Analytics scoped to the OfS cohort year spinner."""
        try:
            year = int(self.b3_year.get())
        except Exception:
            year = date.today().year - 1
        payload = {"source": "eqa.b3", "cohort_year": year,
                   "focus": "continuation_forecast"}
        self._dispatch_with_context("show_predictive_analytics_gui",
                                     "Predictive Analytics", payload)
        return payload

    def open_audit_for_submission(self) -> dict | None:
        """4. Open the Security Dashboard filtered to ``qa.submission_*``
        events for the selected submission."""
        ctx = self._selected_submission()
        if not ctx:
            messagebox.showinfo("Pick a row",
                                "Select a submission first.", parent=self.window)
            return None
        payload = {
            "source": "eqa.submissions",
            "audit_action_prefix": "qa.submission_",
            "resource_type": "qa",
            "resource_id": str(ctx["submission_id"]),
            "framework": ctx["framework"],
            "submission_year": ctx["submission_year"],
        }
        self._dispatch_with_context("show_security_dashboard",
                                     "Security Dashboard", payload)
        return payload

    def open_hesa_for_year(self) -> dict:
        """5. Open the HESA Export GUI pre-selected to the OfS B3 year."""
        try:
            year = int(self.b3_year.get())
        except Exception:
            year = date.today().year - 1
        payload = {"source": "eqa.ofs", "cohort_year": year,
                   "academic_year": f"{year}/{(year + 1) % 100:02d}"}
        self._dispatch_with_context("show_hesa_export_gui", "HESA Export", payload)
        return payload

    def open_bi_for_kpi(self) -> dict:
        """6. Open Business Intelligence filtered to EQA KPIs."""
        payload = {"source": "eqa.kpis", "kpi_category": "external_qa"}
        self._dispatch_with_context("show_business_intelligence_gui",
                                     "Business Intel", payload)
        return payload

    # ------------------------------------------------------------------
    # Overview tab — submissions tracker + KPI button
    # ------------------------------------------------------------------

    def _build_overview_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="Overview")

        ttk.Label(f, text="Submissions tracker",
                  font=("Arial", 12, "bold")).pack(anchor=tk.W)
        self.sub_tree = ttk.Treeview(
            f, columns=("id", "framework", "year", "status", "date", "notes"),
            show="headings", height=10,
        )
        for col, txt, w in [("id", "ID", 50), ("framework", "Framework", 80),
                            ("year", "Year", 70), ("status", "Status", 110),
                            ("date", "Submission date", 120), ("notes", "Notes", 600)]:
            self.sub_tree.heading(col, text=txt)
            self.sub_tree.column(col, width=w)
        self.sub_tree.pack(fill=tk.BOTH, expand=True, pady=(6, 4))

        bar = ttk.Frame(f)
        bar.pack(fill=tk.X, pady=(4, 8))
        ttk.Button(bar, text="New / update submission",
                   command=self._sub_create).pack(side=tk.LEFT)
        ttk.Button(bar, text="Sign off selected",
                   command=self._sub_sign_off).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="Refresh",
                   command=self._refresh_submissions).pack(side=tk.LEFT)
        ttk.Button(bar, text="View audit log",
                   command=self.open_audit_for_submission).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="Open in BI",
                   command=self.open_bi_for_kpi).pack(side=tk.RIGHT, padx=6)
        ttk.Button(bar, text="Recompute & publish KPIs",
                   command=self._publish_kpis).pack(side=tk.RIGHT)

        # Mitigating Circumstances (MC/EC) summary card. Volume and approval
        # rate feed Student Outcomes / B3 narratives so reviewers see them
        # alongside the submissions tracker.
        mc_card = ttk.LabelFrame(f, text="Mitigating Circumstances (MC/EC)",
                                 padding=8)
        mc_card.pack(fill=tk.X, pady=(8, 4))
        self._mc_summary_var = tk.StringVar(value="Loading…")
        ttk.Label(mc_card, textvariable=self._mc_summary_var,
                  font=("Arial", 10)).pack(anchor=tk.W)
        ttk.Button(mc_card, text="Open MC GUI",
                   command=self._open_mc_gui).pack(anchor=tk.E)
        self._refresh_mc_summary()

    def _refresh_mc_summary(self):
        try:
            from education_system.university_system.modules.domain.academics.mitigating_circumstances.integration import (
                aggregate_stats,
            )
            stats = aggregate_stats()
        except Exception:
            self._mc_summary_var.set("MC stats unavailable.")
            return
        by_status = stats.get('by_status') or {}
        approved = by_status.get('approved', 0)
        rejected = by_status.get('rejected', 0)
        in_flight = sum(by_status.get(s, 0) for s in
                        ('submitted', 'evidence_pending',
                         'under_review', 'panel_scheduled'))
        rate = stats.get('approval_rate', 0.0)
        self._mc_summary_var.set(
            f"Total claims: {stats.get('total_claims', 0)}  ·  "
            f"in-flight: {in_flight}  ·  approved: {approved}  ·  "
            f"rejected: {rejected}  ·  approval rate: {rate * 100:.1f}%  ·  "
            f"extensions granted: {stats.get('extensions_granted', 0)}"
        )

    def _open_mc_gui(self):
        try:
            from education_system.university_system.modules.domain.academics.mitigating_circumstances.integration import (
                open_mc_gui_for_student,
            )
            open_mc_gui_for_student(self.window)
        except Exception as exc:
            try:
                from tkinter import messagebox
                messagebox.showerror("MC", f"Could not open MC GUI: {exc}",
                                     parent=self.window)
            except Exception:
                pass

    def _refresh_submissions(self):
        self.sub_tree.delete(*self.sub_tree.get_children())
        for s in qa.list_submissions():
            self.sub_tree.insert("", tk.END, values=(
                s["id"], s["framework"], s["submission_year"], s["status"],
                s.get("submission_date") or "", s.get("notes") or "",
            ))

    def _sub_create(self):
        framework = simpledialog.askstring(
            "Framework", f"Framework ({'/'.join(qa.FRAMEWORKS)}):",
            parent=self.window,
        )
        if not framework or framework not in qa.FRAMEWORKS:
            return
        year = simpledialog.askinteger(
            "Year", "Submission year:", parent=self.window,
            initialvalue=date.today().year,
        )
        if not year:
            return
        notes = simpledialog.askstring("Notes", "Notes (optional):",
                                       parent=self.window) or None
        try:
            qa.upsert_submission(framework, year, notes=notes)
            self._refresh_submissions()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _sub_sign_off(self):
        sel = self.sub_tree.selection()
        if not sel:
            messagebox.showinfo("Pick one", "Select a submission first.")
            return
        sub_id = int(self.sub_tree.item(sel[0])["values"][0])
        signer = _user_id_from_auth(self.auth) or 0
        ok, kpi_n = qa.sign_off_submission_and_publish(sub_id, signer)
        if ok:
            self._refresh_submissions()
            messagebox.showinfo(
                "Signed off",
                f"Submission marked submitted. {kpi_n} KPI(s) republished.",
            )
        else:
            messagebox.showwarning("Already signed off",
                                    "This submission was already submitted.")

    def _publish_kpis(self):
        try:
            n = qa.record_external_qa_kpis()
            messagebox.showinfo("KPIs", f"Recorded {n} KPI metric(s).")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ------------------------------------------------------------------
    # OfS tab — B3 metrics, APP milestones, Protection plans
    # ------------------------------------------------------------------

    def _build_ofs_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="OfS")

        # B3 metrics row
        b3 = ttk.LabelFrame(f, text="B3 metrics — continuation / completion / progression",
                              padding=8)
        b3.pack(fill=tk.X)
        ttk.Label(b3, text="Cohort year:").grid(row=0, column=0, padx=4)
        self.b3_year = tk.IntVar(value=date.today().year - 1)
        ttk.Spinbox(b3, from_=2000, to=2100, textvariable=self.b3_year,
                    width=8).grid(row=0, column=1, padx=4)
        ttk.Button(b3, text="Compute & store snapshot",
                   command=self._b3_compute).grid(row=0, column=2, padx=8)
        ttk.Button(b3, text="Export OfS return (CSV)",
                   command=self._ofs_export).grid(row=0, column=3, padx=4)

        drill = ttk.Frame(b3)
        drill.grid(row=2, column=0, columnspan=4, sticky=tk.W, pady=(6, 0))
        ttk.Label(drill, text="Drill-through:",
                  font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(drill, text="Cohort in Grades",
                   command=self.drill_through_b3).pack(side=tk.LEFT, padx=2)
        ttk.Button(drill, text="Forecast in Predictive",
                   command=self.open_predictive_for_cohort).pack(side=tk.LEFT, padx=2)
        ttk.Button(drill, text="HESA for year",
                   command=self.open_hesa_for_year).pack(side=tk.LEFT, padx=2)

        self.b3_tree = ttk.Treeview(
            b3, columns=("year", "course", "metric", "pct", "num", "denom", "computed"),
            show="headings", height=6,
        )
        for col, txt, w in [("year", "Year", 70), ("course", "Course", 100),
                            ("metric", "Metric", 120), ("pct", "Value %", 90),
                            ("num", "Num", 70), ("denom", "Denom", 70),
                            ("computed", "Computed at", 160)]:
            self.b3_tree.heading(col, text=txt)
            self.b3_tree.column(col, width=w)
        self.b3_tree.grid(row=1, column=0, columnspan=4,
                            sticky=(tk.W, tk.E), pady=(8, 0))

        # APP milestones
        app = ttk.LabelFrame(f, text="Access & Participation Plan milestones", padding=8)
        app.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.app_tree = ttk.Treeview(
            app, columns=("id", "year", "text", "target", "current", "achieved", "due"),
            show="headings", height=8,
        )
        for col, txt, w in [("id", "ID", 50), ("year", "Year", 70),
                            ("text", "Milestone", 460), ("target", "Target", 90),
                            ("current", "Current", 90), ("achieved", "✓", 40),
                            ("due", "Target date", 110)]:
            self.app_tree.heading(col, text=txt)
            self.app_tree.column(col, width=w)
        self.app_tree.pack(fill=tk.BOTH, expand=True)

        bar = ttk.Frame(app)
        bar.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(bar, text="Add milestone", command=self._app_add).pack(side=tk.LEFT)
        ttk.Button(bar, text="Mark selected achieved",
                   command=self._app_mark_done).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="Update current value",
                   command=self._app_set_current).pack(side=tk.LEFT)
        ttk.Button(bar, text="Delete selected",
                   command=self._app_delete).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="Refresh", command=self._refresh_app).pack(side=tk.RIGHT)

        # Protection plans
        prot = ttk.LabelFrame(f, text="Student Protection Plans (versions)", padding=8)
        prot.pack(fill=tk.X, pady=(10, 0))
        self.prot_tree = ttk.Treeview(
            prot, columns=("id", "version", "from", "to", "approved"),
            show="headings", height=4,
        )
        for col, txt, w in [("id", "ID", 50), ("version", "Version", 100),
                            ("from", "In force from", 120),
                            ("to", "In force to", 120),
                            ("approved", "Approved at", 160)]:
            self.prot_tree.heading(col, text=txt)
            self.prot_tree.column(col, width=w)
        self.prot_tree.pack(fill=tk.X)
        ttk.Button(prot, text="Add new plan version",
                   command=self._prot_add).pack(anchor=tk.W, pady=(6, 0))

    def _b3_compute(self):
        try:
            n = qa.record_b3_snapshot(int(self.b3_year.get()))
            self._refresh_b3()
            messagebox.showinfo("B3", f"Stored {n} metric snapshot(s).")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _refresh_b3(self):
        self.b3_tree.delete(*self.b3_tree.get_children())
        for s in qa.list_b3_snapshots():
            pct = s["value_pct"]
            pct_disp = "n/a" if pct is None or pct < 0 else f"{pct:.2f}"
            self.b3_tree.insert("", tk.END, values=(
                s["cohort_year"], s.get("course") or "(all)", s["metric_type"],
                pct_disp, s["numerator"], s["denominator"], s.get("computed_at") or "",
            ))

    def _ofs_export(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile=f"ofs_b3_{int(self.b3_year.get())}.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            n = qa.export_ofs_return(int(self.b3_year.get()), path)
            messagebox.showinfo("Export", f"Wrote {n} row(s) to {path}.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _refresh_app(self):
        self.app_tree.delete(*self.app_tree.get_children())
        for m in qa.list_app_milestones():
            self.app_tree.insert("", tk.END, values=(
                m["id"], m["plan_year"], m["milestone_text"],
                m.get("target_value") or "", m.get("current_value") or "",
                "✓" if m.get("achieved") else "", m.get("target_date") or "",
            ))

    def _app_add(self):
        year = simpledialog.askinteger("Plan year", "Plan year:",
                                        parent=self.window,
                                        initialvalue=date.today().year)
        if not year:
            return
        text = simpledialog.askstring("Milestone", "Milestone text:",
                                       parent=self.window)
        if not text:
            return
        target = simpledialog.askfloat("Target", "Target value (blank = none):",
                                        parent=self.window)
        target_date = simpledialog.askstring("Target date",
                                              "Target date YYYY-MM-DD (blank = none):",
                                              parent=self.window) or None
        try:
            qa.create_app_milestone(year, text, target_value=target,
                                     target_date=target_date,
                                     owner_id=_user_id_from_auth(self.auth))
            self._refresh_app()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _app_mark_done(self):
        sel = self.app_tree.selection()
        if not sel:
            return
        mid = int(self.app_tree.item(sel[0])["values"][0])
        if qa.update_app_milestone(mid, achieved=True, achieved_date=date.today().isoformat()):
            self._refresh_app()

    def _app_set_current(self):
        sel = self.app_tree.selection()
        if not sel:
            return
        mid = int(self.app_tree.item(sel[0])["values"][0])
        v = simpledialog.askfloat("Current value", "Current value:", parent=self.window)
        if v is None:
            return
        if qa.update_app_milestone(mid, current_value=v):
            self._refresh_app()

    def _app_delete(self):
        sel = self.app_tree.selection()
        if not sel:
            return
        mid = int(self.app_tree.item(sel[0])["values"][0])
        if not messagebox.askyesno("Delete", f"Delete milestone #{mid}?"):
            return
        if qa.delete_app_milestone(mid):
            self._refresh_app()

    def _refresh_prot(self):
        self.prot_tree.delete(*self.prot_tree.get_children())
        for p in qa.list_protection_plans():
            self.prot_tree.insert("", tk.END, values=(
                p["id"], p["version"], p["in_force_from"],
                p.get("in_force_to") or "", p.get("approved_at") or "",
            ))

    def _prot_add(self):
        version = simpledialog.askstring("Version", "Version label (e.g. 2026-v1):",
                                          parent=self.window)
        if not version:
            return
        in_force_from = simpledialog.askstring(
            "In force from", "Effective from YYYY-MM-DD:", parent=self.window,
            initialvalue=date.today().isoformat(),
        )
        if not in_force_from:
            return
        editor = _TextEditor(self.window, "Plan text", "")
        self.window.wait_window(editor)
        if not editor.result:
            return
        try:
            qa.create_protection_plan(
                version=version, in_force_from=in_force_from,
                plan_text=editor.result,
                approved_by=_user_id_from_auth(self.auth),
            )
            self._refresh_prot()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ------------------------------------------------------------------
    # TEF tab — provider narratives + indicators
    # ------------------------------------------------------------------

    def _build_tef_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="TEF")

        ind = ttk.LabelFrame(f, text="Computed indicators", padding=8)
        ind.pack(fill=tk.X)
        self.tef_indicators_text = tk.Text(ind, height=6, wrap=tk.WORD,
                                            state=tk.DISABLED, bg=self.window.cget("bg"),
                                            relief="flat")
        self.tef_indicators_text.pack(fill=tk.X)

        narr = ttk.LabelFrame(f, text="Provider narrative drafts", padding=8)
        narr.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        bar = ttk.Frame(narr)
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="Submission year:").pack(side=tk.LEFT)
        self.tef_year = tk.IntVar(value=date.today().year)
        ttk.Spinbox(bar, from_=2000, to=2100, textvariable=self.tef_year,
                    width=8, command=self._refresh_tef).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Refresh", command=self._refresh_tef).pack(side=tk.LEFT)
        ttk.Button(bar, text="Add new version (selected section)",
                   command=self._tef_add).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="Export TEF JSON",
                   command=self._tef_export).pack(side=tk.RIGHT)

        self.tef_tree = ttk.Treeview(
            narr, columns=("id", "section", "version", "drafted_at", "preview"),
            show="headings", height=10,
        )
        for col, txt, w in [("id", "ID", 50), ("section", "Section", 160),
                            ("version", "v", 50),
                            ("drafted_at", "Drafted at", 160),
                            ("preview", "Preview", 700)]:
            self.tef_tree.heading(col, text=txt)
            self.tef_tree.column(col, width=w)
        self.tef_tree.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    def _refresh_tef(self):
        # Indicators
        ind = qa.compute_tef_indicators()
        self.tef_indicators_text.config(state=tk.NORMAL)
        self.tef_indicators_text.delete("1.0", tk.END)
        for k, v in ind.items():
            self.tef_indicators_text.insert(tk.END, f"{k}:  {v}\n")
        self.tef_indicators_text.config(state=tk.DISABLED)

        # Narratives
        self.tef_tree.delete(*self.tef_tree.get_children())
        for n in qa.list_tef_narratives(submission_year=int(self.tef_year.get())):
            self.tef_tree.insert("", tk.END, values=(
                n["id"], n["section"], n["version"], n.get("created_at") or "",
                (n.get("narrative_text") or "")[:120].replace("\n", " "),
            ))

    def _tef_add(self):
        section = simpledialog.askstring(
            "Section", f"Section ({'/'.join(qa.TEF_SECTIONS)}):",
            parent=self.window,
        )
        if not section or section not in qa.TEF_SECTIONS:
            return
        editor = _TextEditor(self.window, f"TEF — {section}", "")
        self.window.wait_window(editor)
        if not editor.result:
            return
        try:
            qa.add_tef_narrative(int(self.tef_year.get()), section, editor.result,
                                  drafted_by=_user_id_from_auth(self.auth))
            self._refresh_tef()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _tef_export(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile=f"tef_{int(self.tef_year.get())}.json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            n = qa.export_tef_submission(int(self.tef_year.get()), path)
            messagebox.showinfo("Export", f"Wrote {n} section(s) to {path}.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ------------------------------------------------------------------
    # REF tab — UoA summary, impact cases, environment statements
    # ------------------------------------------------------------------

    def _build_ref_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="REF")

        bar = ttk.Frame(f)
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="Unit of Assessment:").pack(side=tk.LEFT)
        self.ref_uoa = tk.StringVar(value=qa.REF_UOAS[0])
        ttk.Combobox(bar, textvariable=self.ref_uoa,
                     values=qa.REF_UOAS, width=10).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Refresh", command=self._refresh_ref).pack(side=tk.LEFT)
        ttk.Button(bar, text="Export REF CSV",
                   command=self._ref_export).pack(side=tk.RIGHT)

        sumf = ttk.LabelFrame(f, text="UoA summary", padding=8)
        sumf.pack(fill=tk.X, pady=(8, 0))
        self.ref_summary_text = tk.Text(sumf, height=5, wrap=tk.WORD,
                                          state=tk.DISABLED, bg=self.window.cget("bg"),
                                          relief="flat")
        self.ref_summary_text.pack(fill=tk.X)

        impact = ttk.LabelFrame(f, text="Impact case studies", padding=8)
        impact.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.impact_tree = ttk.Treeview(
            impact, columns=("id", "title", "status", "lead", "rating"),
            show="headings", height=8,
        )
        for col, txt, w in [("id", "ID", 50), ("title", "Title", 540),
                            ("status", "Status", 100),
                            ("lead", "Lead", 120),
                            ("rating", "Rating", 80)]:
            self.impact_tree.heading(col, text=txt)
            self.impact_tree.column(col, width=w)
        self.impact_tree.pack(fill=tk.BOTH, expand=True)

        ibar = ttk.Frame(impact)
        ibar.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(ibar, text="Add case", command=self._impact_add).pack(side=tk.LEFT)
        ttk.Button(ibar, text="Set status of selected",
                   command=self._impact_set_status).pack(side=tk.LEFT, padx=6)
        ttk.Button(ibar, text="Set quality rating of selected",
                   command=self._impact_set_rating).pack(side=tk.LEFT)
        ttk.Button(ibar, text="Delete selected",
                   command=self._impact_delete).pack(side=tk.LEFT, padx=6)

        env = ttk.LabelFrame(f, text="Environment statement (latest 3 versions)", padding=8)
        env.pack(fill=tk.X, pady=(8, 0))
        self.env_tree = ttk.Treeview(
            env, columns=("id", "version", "drafted_at", "preview"),
            show="headings", height=4,
        )
        for col, txt, w in [("id", "ID", 50), ("version", "v", 50),
                            ("drafted_at", "Drafted at", 160),
                            ("preview", "Preview", 760)]:
            self.env_tree.heading(col, text=txt)
            self.env_tree.column(col, width=w)
        self.env_tree.pack(fill=tk.X)
        ttk.Button(env, text="Add new version",
                   command=self._env_add).pack(anchor=tk.W, pady=(6, 0))

    def _refresh_ref(self):
        uoa = self.ref_uoa.get().strip()
        if not uoa:
            return
        s = qa.compute_uoa_summary(uoa)
        self.ref_summary_text.config(state=tk.NORMAL)
        self.ref_summary_text.delete("1.0", tk.END)
        self.ref_summary_text.insert(tk.END, (
            f"UoA:                      {s['uoa']}\n"
            f"Outputs total / submitted: {s['outputs_total']} / {s['outputs_submitted']}\n"
            f"Open access:              {s['open_access_pct']} %\n"
            f"Average quality (*):       {s['avg_quality']}\n"
            f"Impact cases:             {s['impact_cases']}\n"
            f"Environment versions:      {s['environment_statement_versions']}"
        ))
        self.ref_summary_text.config(state=tk.DISABLED)

        self.impact_tree.delete(*self.impact_tree.get_children())
        for c in qa.list_impact_cases(uoa=uoa):
            self.impact_tree.insert("", tk.END, values=(
                c["id"], c["title"], c["status"],
                c.get("lead_author_id") or "", c.get("quality_rating") or "",
            ))

        self.env_tree.delete(*self.env_tree.get_children())
        for e in qa.list_environment_statements(uoa=uoa)[:3]:
            self.env_tree.insert("", tk.END, values=(
                e["id"], e["version"], e.get("created_at") or "",
                (e.get("narrative_text") or "")[:120].replace("\n", " "),
            ))

    def _impact_add(self):
        title = simpledialog.askstring("Title", "Case study title:",
                                        parent=self.window)
        if not title:
            return
        editor = _TextEditor(self.window, "Summary", "")
        self.window.wait_window(editor)
        try:
            qa.create_impact_case(uoa=self.ref_uoa.get().strip(), title=title,
                                   summary=(editor.result or None),
                                   lead_author_id=_user_id_from_auth(self.auth))
            self._refresh_ref()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _impact_set_status(self):
        sel = self.impact_tree.selection()
        if not sel:
            return
        cid = int(self.impact_tree.item(sel[0])["values"][0])
        s = simpledialog.askstring(
            "Status", f"New status ({'/'.join(qa.REF_IMPACT_STATUSES)}):",
            parent=self.window,
        )
        if not s or s not in qa.REF_IMPACT_STATUSES:
            return
        if qa.update_impact_case(cid, status=s):
            self._refresh_ref()

    def _impact_set_rating(self):
        sel = self.impact_tree.selection()
        if not sel:
            return
        cid = int(self.impact_tree.item(sel[0])["values"][0])
        r = simpledialog.askstring("Rating", "Quality rating (1*–4*):",
                                    parent=self.window)
        if not r:
            return
        if qa.update_impact_case(cid, quality_rating=r):
            self._refresh_ref()

    def _impact_delete(self):
        sel = self.impact_tree.selection()
        if not sel:
            return
        cid = int(self.impact_tree.item(sel[0])["values"][0])
        if not messagebox.askyesno("Delete", f"Delete impact case #{cid}?"):
            return
        if qa.delete_impact_case(cid):
            self._refresh_ref()

    def _env_add(self):
        editor = _TextEditor(self.window, "Environment statement", "")
        self.window.wait_window(editor)
        if not editor.result:
            return
        try:
            qa.add_environment_statement(self.ref_uoa.get().strip(), editor.result,
                                          drafted_by=_user_id_from_auth(self.auth))
            self._refresh_ref()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _ref_export(self):
        uoa = self.ref_uoa.get().strip()
        if not uoa:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile=f"ref_{uoa}.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            n = qa.export_ref_submission(uoa, path)
            messagebox.showinfo("Export", f"Wrote {n} row(s) to {path}.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ------------------------------------------------------------------
    # Refresh all tabs after init
    # ------------------------------------------------------------------

    def _refresh_all(self):
        try:
            self._refresh_submissions()
            self._refresh_b3()
            self._refresh_app()
            self._refresh_prot()
            self._refresh_tef()
            self._refresh_ref()
        except Exception:
            logger.exception("initial refresh")
