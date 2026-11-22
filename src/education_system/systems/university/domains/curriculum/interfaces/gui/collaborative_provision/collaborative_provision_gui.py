"""Collaborative (Partner) Provision GUI.

Four tabs — Partners, Agreements, Programmes & Cohorts, Reviews — plus a
compliance strip across the top that shows the three things that go wrong
with partner provision: reviews nobody did, agreements about to expire,
and recruitment past the contracted cap.

``app`` is the ``UnifiedManagementGUI`` instance when launched in-process.
"""

from __future__ import annotations

import csv
import logging
import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)


class CollaborativeProvisionGUI:
    """Top-level window over :class:`CollaborativeProvisionService`."""

    def __init__(self, parent=None, app=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.app = app
        self.root.title(_t(
            "gui.academics.collaborative_provision.windows.title",
            default="===== WINDOWS ====="))
        # Project window-sizing convention.
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        try:
            from education_system.systems.university.domains.curriculum.domain.collaborative_provision.services.collaborative_provision_service import (
                CollaborativeProvisionService,
            )
            self.service = CollaborativeProvisionService()
        except Exception as exc:  # noqa: BLE001
            logger.error("Collaborative provision service init failed: %s", exc)
            self.service = None

        self._build_ui()
        self.refresh_all()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        self.status_var = tk.StringVar(value="")
        bar = ttk.Frame(self.root)
        bar.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Label(bar, textvariable=self.status_var,
                  font=("", 10, "bold")).pack(side=tk.LEFT)
        ttk.Button(bar, text=_t("common.refresh", default="Refresh"),
                   command=self.refresh_all).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bar, text=_t("gui.academics.collaborative_provision.buttons.export",
                                default="Export Provision Map"),
                   command=self._export_map).pack(side=tk.RIGHT, padx=2)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._build_partners_tab(notebook)
        self._build_agreements_tab(notebook)
        self._build_programmes_tab(notebook)
        self._build_reviews_tab(notebook)

    def _tree(self, parent, columns, widths=None):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for i, col in enumerate(columns):
            tree.heading(col, text=col.replace("_", " ").title())
            tree.column(col, width=(widths[i] if widths else 140), anchor=tk.W)
        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    # ------------------------------------------------------------ partners
    def _build_partners_tab(self, notebook) -> None:
        tab = ttk.Frame(notebook)
        notebook.add(tab, text=_t("gui.academics.collaborative_provision.tabs.partners",
                                  default="Partners"))

        # Action bar first so it survives a cramped screen (see the
        # project's window-sizing convention).
        actions = ttk.Frame(tab)
        actions.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(actions, text=_t("common.add", default="Add"),
                   command=self._add_partner).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions, text=_t("common.edit", default="Edit"),
                   command=self._edit_partner).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions,
                   text=_t("gui.academics.collaborative_provision.buttons.deactivate",
                           default="Deactivate"),
                   command=self._deactivate_partner).pack(side=tk.LEFT, padx=2)

        self.partner_search = tk.StringVar()
        ttk.Label(actions, text=_t("common.search", default="Search")).pack(
            side=tk.LEFT, padx=(20, 4))
        entry = ttk.Entry(actions, textvariable=self.partner_search, width=24)
        entry.pack(side=tk.LEFT)
        entry.bind("<Return>", lambda _e: self._refresh_partners())
        ttk.Button(actions, text=_t("common.go", default="Go"),
                   command=self._refresh_partners).pack(side=tk.LEFT, padx=2)

        self.partners_tree = self._tree(
            tab, ("partner_id", "name", "partner_type", "country", "city",
                  "risk_level", "due_diligence_due", "agreement_count"),
            (60, 240, 200, 110, 110, 80, 130, 90))

    def _refresh_partners(self) -> None:
        if not self.service:
            return
        for row in self.partners_tree.get_children():
            self.partners_tree.delete(row)
        for p in self.service.list_partners(
                active_only=False, search=self.partner_search.get().strip() or None):
            self.partners_tree.insert("", tk.END, values=(
                p["partner_id"], p["name"], p.get("partner_type") or "",
                p.get("country") or "", p.get("city") or "",
                p.get("risk_level") or "", p.get("due_diligence_due") or "",
                p.get("agreement_count", 0)))

    def _selected_id(self, tree) -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showwarning(_t("common.selection", default="Selection"),
                                   _t("common.select_a_row_first",
                                      default="Select a row first."),
                                   parent=self.root)
            return None
        return int(tree.item(sel[0], "values")[0])

    def _add_partner(self) -> None:
        self._partner_dialog()

    def _edit_partner(self) -> None:
        pid = self._selected_id(self.partners_tree)
        if pid is not None:
            self._partner_dialog(self.service.get_partner(pid))

    def _deactivate_partner(self) -> None:
        pid = self._selected_id(self.partners_tree)
        if pid is None:
            return
        if messagebox.askyesno(
                _t("common.confirm", default="Confirm"),
                _t("gui.academics.collaborative_provision.dialogs.confirm_deactivate",
                   default="Deactivate this partner? Its agreements and "
                           "history are kept."),
                parent=self.root):
            self.service.deactivate_partner(pid)
            self.refresh_all()

    def _partner_dialog(self, existing=None) -> None:
        from education_system.systems.university.domains.curriculum.domain.collaborative_provision._db_init import (
            PARTNER_TYPES, RISK_LEVELS,
        )
        dlg = tk.Toplevel(self.root)
        dlg.title("Edit Partner" if existing else "Add Partner")
        dlg.geometry("520x520")
        dlg.transient(self.root)
        dlg.grab_set()

        fields = (
            ("Name", "name", None), ("Type", "partner_type", PARTNER_TYPES),
            ("Country", "country", None), ("City", "city", None),
            ("UKPRN", "ukprn", None), ("Website", "website", None),
            ("Contact name", "contact_name", None),
            ("Contact email", "contact_email", None),
            ("Risk level", "risk_level", RISK_LEVELS),
            ("Due diligence date", "due_diligence_date", None),
            ("Next due diligence", "due_diligence_due", None),
        )
        widgets: dict[str, tk.Variable] = {}
        body = ttk.Frame(dlg)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        for i, (label, key, options) in enumerate(fields):
            ttk.Label(body, text=f"{label}:").grid(row=i, column=0, sticky=tk.E,
                                                   padx=6, pady=5)
            var = tk.StringVar(value=str((existing or {}).get(key) or ""))
            widgets[key] = var
            if options:
                ttk.Combobox(body, textvariable=var, values=list(options),
                             width=32, state="readonly").grid(
                    row=i, column=1, sticky=tk.W, padx=6, pady=5)
            else:
                ttk.Entry(body, textvariable=var, width=34).grid(
                    row=i, column=1, sticky=tk.W, padx=6, pady=5)

        def save() -> None:
            values = {k: (v.get().strip() or None) for k, v in widgets.items()}
            if not values["name"]:
                messagebox.showerror(_t("common.error", default="Error"),
                                     "Name is required.", parent=dlg)
                return
            try:
                if existing:
                    self.service.update_partner(existing["partner_id"], **values)
                else:
                    self.service.add_partner(**values)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror(_t("common.error", default="Error"),
                                     str(exc), parent=dlg)
                return
            dlg.destroy()
            self.refresh_all()

        buttons = ttk.Frame(dlg)
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(buttons, text=_t("common.save", default="Save"),
                   command=save).pack(side=tk.RIGHT, padx=4)
        ttk.Button(buttons, text=_t("common.cancel", default="Cancel"),
                   command=dlg.destroy).pack(side=tk.RIGHT)

    # ---------------------------------------------------------- agreements
    def _build_agreements_tab(self, notebook) -> None:
        tab = ttk.Frame(notebook)
        notebook.add(tab, text=_t("gui.academics.collaborative_provision.tabs.agreements",
                                  default="Agreements"))

        actions = ttk.Frame(tab)
        actions.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(actions, text=_t("common.add", default="Add"),
                   command=self._add_agreement).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions,
                   text=_t("gui.academics.collaborative_provision.buttons.set_status",
                           default="Set Status"),
                   command=self._set_agreement_status).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions,
                   text=_t("gui.academics.collaborative_provision.buttons.over_recruited",
                           default="Over-Recruited"),
                   command=self._show_over_recruited).pack(side=tk.LEFT, padx=12)

        self.agreements_tree = self._tree(
            tab, ("agreement_id", "partner_name", "delivery_model", "status",
                  "start_date", "end_date", "review_due", "max_students"),
            (70, 240, 190, 140, 100, 100, 100, 90))

    def _refresh_agreements(self) -> None:
        if not self.service:
            return
        for row in self.agreements_tree.get_children():
            self.agreements_tree.delete(row)
        today = date.today().isoformat()
        for a in self.service.list_agreements():
            overdue = (a.get("review_due") or "") and a["review_due"] < today
            self.agreements_tree.insert(
                "", tk.END,
                values=(a["agreement_id"], a["partner_name"],
                        a["delivery_model"], a["status"],
                        a.get("start_date") or "", a.get("end_date") or "",
                        (a.get("review_due") or "") + (" ⚠" if overdue else ""),
                        a.get("max_students") or ""))

    def _add_agreement(self) -> None:
        from education_system.systems.university.domains.curriculum.domain.collaborative_provision._db_init import (
            AGREEMENT_STATUSES, DELIVERY_MODELS,
        )
        partners = self.service.list_partners(active_only=True)
        if not partners:
            messagebox.showinfo(_t("common.info", default="Info"),
                                "Add a partner first.", parent=self.root)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Add Agreement")
        dlg.geometry("520x440")
        dlg.transient(self.root)
        dlg.grab_set()
        body = ttk.Frame(dlg)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        labels = [f"{p['partner_id']} — {p['name']}" for p in partners]
        partner_var = tk.StringVar(value=labels[0])
        model_var = tk.StringVar(value=DELIVERY_MODELS[0])
        status_var = tk.StringVar(value=AGREEMENT_STATUSES[0])
        text_vars = {k: tk.StringVar() for k in
                     ("reference", "start_date", "end_date", "review_due",
                      "max_students", "fee_share_pct")}

        rows = [("Partner", partner_var, labels),
                ("Delivery model", model_var, list(DELIVERY_MODELS)),
                ("Status", status_var, list(AGREEMENT_STATUSES)),
                ("Reference", text_vars["reference"], None),
                ("Start date", text_vars["start_date"], None),
                ("End date", text_vars["end_date"], None),
                ("Review due", text_vars["review_due"], None),
                ("Max students", text_vars["max_students"], None),
                ("Fee share %", text_vars["fee_share_pct"], None)]
        for i, (label, var, options) in enumerate(rows):
            ttk.Label(body, text=f"{label}:").grid(row=i, column=0, sticky=tk.E,
                                                   padx=6, pady=5)
            if options:
                ttk.Combobox(body, textvariable=var, values=options, width=34,
                             state="readonly").grid(row=i, column=1,
                                                    sticky=tk.W, padx=6, pady=5)
            else:
                ttk.Entry(body, textvariable=var, width=36).grid(
                    row=i, column=1, sticky=tk.W, padx=6, pady=5)

        def save() -> None:
            cap = text_vars["max_students"].get().strip()
            share = text_vars["fee_share_pct"].get().strip()
            try:
                self.service.add_agreement(
                    int(partner_var.get().split("—")[0].strip()),
                    model_var.get(), status=status_var.get(),
                    reference=text_vars["reference"].get().strip() or None,
                    start_date=text_vars["start_date"].get().strip() or None,
                    end_date=text_vars["end_date"].get().strip() or None,
                    review_due=text_vars["review_due"].get().strip() or None,
                    max_students=int(cap) if cap.isdigit() else None,
                    fee_share_pct=float(share) if share else None)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror(_t("common.error", default="Error"),
                                     str(exc), parent=dlg)
                return
            dlg.destroy()
            self.refresh_all()

        buttons = ttk.Frame(dlg)
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(buttons, text=_t("common.save", default="Save"),
                   command=save).pack(side=tk.RIGHT, padx=4)
        ttk.Button(buttons, text=_t("common.cancel", default="Cancel"),
                   command=dlg.destroy).pack(side=tk.RIGHT)

    def _set_agreement_status(self) -> None:
        from education_system.systems.university.domains.curriculum.domain.collaborative_provision._db_init import (
            AGREEMENT_STATUSES,
        )
        aid = self._selected_id(self.agreements_tree)
        if aid is None:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Set Agreement Status")
        dlg.geometry("380x160")
        dlg.transient(self.root)
        dlg.grab_set()
        var = tk.StringVar(value=AGREEMENT_STATUSES[0])
        ttk.Label(dlg, text="New status:").pack(padx=12, pady=(16, 4), anchor=tk.W)
        ttk.Combobox(dlg, textvariable=var, values=list(AGREEMENT_STATUSES),
                     state="readonly", width=32).pack(padx=12)

        def save() -> None:
            self.service.set_agreement_status(aid, var.get())
            dlg.destroy()
            self.refresh_all()

        ttk.Button(dlg, text=_t("common.save", default="Save"),
                   command=save).pack(pady=14)

    def _show_over_recruited(self) -> None:
        rows = self.service.over_recruited()
        if not rows:
            messagebox.showinfo(
                _t("common.info", default="Info"),
                "No agreement is recruiting above its contracted cap.",
                parent=self.root)
            return
        self._simple_report("Over-Recruited Agreements", rows,
                            ("agreement_id", "partner_name", "delivery_model",
                             "max_students", "enrolled"))

    # ------------------------------------------------- programmes & cohorts
    def _build_programmes_tab(self, notebook) -> None:
        tab = ttk.Frame(notebook)
        notebook.add(tab,
                     text=_t("gui.academics.collaborative_provision.tabs.programmes",
                             default="Programmes & Cohorts"))

        actions = ttk.Frame(tab)
        actions.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(actions,
                   text=_t("gui.academics.collaborative_provision.buttons.add_programme",
                           default="Add Programme"),
                   command=self._add_programme).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions,
                   text=_t("gui.academics.collaborative_provision.buttons.add_cohort",
                           default="Record Cohort"),
                   command=self._add_cohort).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions,
                   text=_t("gui.academics.collaborative_provision.buttons.unlinked",
                           default="Not Linked to Governance"),
                   command=self._show_unlinked).pack(side=tk.LEFT, padx=12)

        paned = ttk.PanedWindow(tab, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)
        top = ttk.Frame(paned)
        bottom = ttk.Frame(paned)
        paned.add(top, weight=3)
        paned.add(bottom, weight=2)

        self.programmes_tree = self._tree(
            top, ("collab_programme_id", "partner_name", "programme_title",
                  "programme_code", "award", "delivery_model", "delivery_site",
                  "link_tutor"),
            (70, 200, 260, 110, 130, 170, 160, 140))
        self.programmes_tree.bind("<<TreeviewSelect>>",
                                  lambda _e: self._refresh_cohorts())
        ttk.Label(bottom, text=_t(
            "gui.academics.collaborative_provision.labels.cohorts",
            default="Cohorts for the selected programme")).pack(
            anchor=tk.W, padx=8, pady=(6, 0))
        self.cohorts_tree = self._tree(
            bottom, ("cohort_id", "academic_year", "intake_month",
                     "planned_headcount", "actual_headcount",
                     "completed_headcount"),
            (70, 120, 110, 130, 130, 140))

    def _refresh_programmes(self) -> None:
        if not self.service:
            return
        for row in self.programmes_tree.get_children():
            self.programmes_tree.delete(row)
        for p in self.service.list_programmes():
            self.programmes_tree.insert("", tk.END, values=(
                p["collab_programme_id"], p["partner_name"],
                p["programme_title"], p.get("programme_code") or "",
                p.get("award") or "", p.get("delivery_model") or "",
                p.get("delivery_site") or "", p.get("link_tutor") or ""))
        self._refresh_cohorts()

    def _refresh_cohorts(self) -> None:
        for row in self.cohorts_tree.get_children():
            self.cohorts_tree.delete(row)
        sel = self.programmes_tree.selection()
        if not sel or not self.service:
            return
        cpid = int(self.programmes_tree.item(sel[0], "values")[0])
        for c in self.service.list_cohorts(collab_programme_id=cpid):
            self.cohorts_tree.insert("", tk.END, values=(
                c["cohort_id"], c["academic_year"], c.get("intake_month") or "",
                c.get("planned_headcount") or "", c.get("actual_headcount") or "",
                c.get("completed_headcount") or ""))

    def _add_programme(self) -> None:
        agreements = self.service.list_agreements()
        if not agreements:
            messagebox.showinfo(_t("common.info", default="Info"),
                                "Add an agreement first.", parent=self.root)
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Add Partner Programme")
        dlg.geometry("540x420")
        dlg.transient(self.root)
        dlg.grab_set()
        body = ttk.Frame(dlg)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        labels = [f"{a['agreement_id']} — {a['partner_name']} "
                  f"({a['delivery_model']})" for a in agreements]
        agreement_var = tk.StringVar(value=labels[0])
        text_vars = {k: tk.StringVar() for k in
                     ("programme_title", "programme_code", "award", "level",
                      "delivery_site", "link_tutor", "external_examiner")}
        rows = [("Agreement", agreement_var, labels),
                ("Programme title", text_vars["programme_title"], None),
                ("Programme code", text_vars["programme_code"], None),
                ("Award", text_vars["award"], None),
                ("Level", text_vars["level"], None),
                ("Delivery site", text_vars["delivery_site"], None),
                ("Link tutor", text_vars["link_tutor"], None),
                ("External examiner", text_vars["external_examiner"], None)]
        for i, (label, var, options) in enumerate(rows):
            ttk.Label(body, text=f"{label}:").grid(row=i, column=0, sticky=tk.E,
                                                   padx=6, pady=5)
            if options:
                ttk.Combobox(body, textvariable=var, values=options, width=40,
                             state="readonly").grid(row=i, column=1,
                                                    sticky=tk.W, padx=6, pady=5)
            else:
                ttk.Entry(body, textvariable=var, width=42).grid(
                    row=i, column=1, sticky=tk.W, padx=6, pady=5)

        def save() -> None:
            try:
                self.service.add_programme(
                    int(agreement_var.get().split("—")[0].strip()),
                    text_vars["programme_title"].get().strip(),
                    programme_code=text_vars["programme_code"].get().strip() or None,
                    award=text_vars["award"].get().strip() or None,
                    level=text_vars["level"].get().strip() or None,
                    delivery_site=text_vars["delivery_site"].get().strip() or None,
                    link_tutor=text_vars["link_tutor"].get().strip() or None,
                    external_examiner=text_vars["external_examiner"].get().strip() or None)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror(_t("common.error", default="Error"),
                                     str(exc), parent=dlg)
                return
            dlg.destroy()
            self.refresh_all()

        buttons = ttk.Frame(dlg)
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(buttons, text=_t("common.save", default="Save"),
                   command=save).pack(side=tk.RIGHT, padx=4)
        ttk.Button(buttons, text=_t("common.cancel", default="Cancel"),
                   command=dlg.destroy).pack(side=tk.RIGHT)

    def _add_cohort(self) -> None:
        cpid = self._selected_id(self.programmes_tree)
        if cpid is None:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Record Cohort")
        dlg.geometry("420x300")
        dlg.transient(self.root)
        dlg.grab_set()
        body = ttk.Frame(dlg)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        text_vars = {k: tk.StringVar() for k in
                     ("academic_year", "intake_month", "planned_headcount",
                      "actual_headcount", "completed_headcount")}
        for i, (label, key) in enumerate((
                ("Academic year", "academic_year"),
                ("Intake month", "intake_month"),
                ("Planned headcount", "planned_headcount"),
                ("Actual headcount", "actual_headcount"),
                ("Completed headcount", "completed_headcount"))):
            ttk.Label(body, text=f"{label}:").grid(row=i, column=0, sticky=tk.E,
                                                   padx=6, pady=6)
            ttk.Entry(body, textvariable=text_vars[key], width=22).grid(
                row=i, column=1, sticky=tk.W, padx=6, pady=6)

        def save() -> None:
            def num(key):
                raw = text_vars[key].get().strip()
                return int(raw) if raw.isdigit() else None
            year = text_vars["academic_year"].get().strip()
            if not year:
                messagebox.showerror(_t("common.error", default="Error"),
                                     "Academic year is required.", parent=dlg)
                return
            self.service.add_cohort(
                cpid, year,
                intake_month=text_vars["intake_month"].get().strip() or None,
                planned_headcount=num("planned_headcount"),
                actual_headcount=num("actual_headcount"),
                completed_headcount=num("completed_headcount"))
            dlg.destroy()
            self.refresh_all()

        ttk.Button(dlg, text=_t("common.save", default="Save"),
                   command=save).pack(pady=10)

    def _show_unlinked(self) -> None:
        rows = self.service.unlinked_programmes()
        if not rows:
            messagebox.showinfo(
                _t("common.info", default="Info"),
                "Every partner programme maps to a governed programme.",
                parent=self.root)
            return
        self._simple_report("Partner Programmes Not Linked to Governance", rows,
                            ("collab_programme_id", "partner_name",
                             "programme_title", "programme_code"))

    # ------------------------------------------------------------- reviews
    def _build_reviews_tab(self, notebook) -> None:
        tab = ttk.Frame(notebook)
        notebook.add(tab, text=_t("gui.academics.collaborative_provision.tabs.reviews",
                                  default="Reviews"))
        actions = ttk.Frame(tab)
        actions.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(actions,
                   text=_t("gui.academics.collaborative_provision.buttons.record_review",
                           default="Record Review"),
                   command=self._add_review).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions,
                   text=_t("gui.academics.collaborative_provision.buttons.overdue",
                           default="Overdue Reviews"),
                   command=self._show_overdue).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions,
                   text=_t("gui.academics.collaborative_provision.buttons.expiring",
                           default="Expiring Agreements"),
                   command=self._show_expiring).pack(side=tk.LEFT, padx=2)

        self.reviews_tree = self._tree(
            tab, ("review_id", "partner_name", "review_type", "review_date",
                  "reviewer", "outcome", "next_review_due"),
            (70, 220, 200, 110, 150, 200, 130))

    def _refresh_reviews(self) -> None:
        if not self.service:
            return
        for row in self.reviews_tree.get_children():
            self.reviews_tree.delete(row)
        for r in self.service.list_reviews():
            self.reviews_tree.insert("", tk.END, values=(
                r["review_id"], r["partner_name"], r["review_type"],
                r["review_date"], r.get("reviewer") or "",
                r.get("outcome") or "", r.get("next_review_due") or ""))

    def _add_review(self) -> None:
        from education_system.systems.university.domains.curriculum.domain.collaborative_provision._db_init import (
            REVIEW_OUTCOMES, REVIEW_TYPES,
        )
        partners = self.service.list_partners(active_only=False)
        if not partners:
            messagebox.showinfo(_t("common.info", default="Info"),
                                "Add a partner first.", parent=self.root)
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Record Review")
        dlg.geometry("560x460")
        dlg.transient(self.root)
        dlg.grab_set()
        body = ttk.Frame(dlg)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        labels = [f"{p['partner_id']} — {p['name']}" for p in partners]
        partner_var = tk.StringVar(value=labels[0])
        type_var = tk.StringVar(value=REVIEW_TYPES[0])
        outcome_var = tk.StringVar(value=REVIEW_OUTCOMES[0])
        date_var = tk.StringVar(value=date.today().isoformat())
        reviewer_var = tk.StringVar()
        next_var = tk.StringVar()

        rows = [("Partner", partner_var, labels),
                ("Review type", type_var, list(REVIEW_TYPES)),
                ("Review date", date_var, None),
                ("Reviewer", reviewer_var, None),
                ("Outcome", outcome_var, list(REVIEW_OUTCOMES)),
                ("Next review due", next_var, None)]
        for i, (label, var, options) in enumerate(rows):
            ttk.Label(body, text=f"{label}:").grid(row=i, column=0, sticky=tk.E,
                                                   padx=6, pady=5)
            if options:
                ttk.Combobox(body, textvariable=var, values=options, width=40,
                             state="readonly").grid(row=i, column=1,
                                                    sticky=tk.W, padx=6, pady=5)
            else:
                ttk.Entry(body, textvariable=var, width=42).grid(
                    row=i, column=1, sticky=tk.W, padx=6, pady=5)

        ttk.Label(body, text="Findings:").grid(row=len(rows), column=0,
                                               sticky=tk.NE, padx=6, pady=5)
        findings = tk.Text(body, width=42, height=6)
        findings.grid(row=len(rows), column=1, sticky=tk.W, padx=6, pady=5)

        def save() -> None:
            self.service.add_review(
                int(partner_var.get().split("—")[0].strip()),
                type_var.get(), date_var.get().strip(),
                reviewer=reviewer_var.get().strip() or None,
                outcome=outcome_var.get(),
                findings=findings.get("1.0", tk.END).strip() or None,
                next_review_due=next_var.get().strip() or None)
            dlg.destroy()
            self.refresh_all()

        buttons = ttk.Frame(dlg)
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(buttons, text=_t("common.save", default="Save"),
                   command=save).pack(side=tk.RIGHT, padx=4)
        ttk.Button(buttons, text=_t("common.cancel", default="Cancel"),
                   command=dlg.destroy).pack(side=tk.RIGHT)

    def _show_overdue(self) -> None:
        rows = self.service.overdue_reviews()
        if not rows:
            messagebox.showinfo(_t("common.info", default="Info"),
                                "No agreement is overdue a review.",
                                parent=self.root)
            return
        self._simple_report("Overdue Partner Reviews", rows,
                            ("agreement_id", "partner_name", "delivery_model",
                             "risk_level", "review_due"))

    def _show_expiring(self) -> None:
        rows = self.service.expiring_agreements()
        if not rows:
            messagebox.showinfo(_t("common.info", default="Info"),
                                "No agreement expires in the next 180 days.",
                                parent=self.root)
            return
        self._simple_report("Agreements Expiring Within 180 Days", rows,
                            ("agreement_id", "partner_name", "delivery_model",
                             "status", "end_date"))

    # ------------------------------------------------------------- shared
    def _simple_report(self, title: str, rows: list[dict],
                       columns: tuple[str, ...]) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.geometry("900x460")
        dlg.transient(self.root)
        tree = ttk.Treeview(dlg, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=col.replace("_", " ").title())
            tree.column(col, width=160, anchor=tk.W)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        for row in rows:
            tree.insert("", tk.END,
                        values=tuple(row.get(c, "") or "" for c in columns))

    def _export_map(self) -> None:
        if not self.service:
            return
        rows = self.service.provision_map()
        if not rows:
            messagebox.showinfo(_t("common.info", default="Info"),
                                "No collaborative provision to export.",
                                parent=self.root)
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"collaborative_provision_{date.today().isoformat()}.csv")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
        except OSError as exc:
            messagebox.showerror(_t("common.error", default="Error"), str(exc),
                                 parent=self.root)
            return
        messagebox.showinfo(_t("common.info", default="Info"),
                            f"Exported {len(rows)} rows.", parent=self.root)

    def refresh_all(self) -> None:
        if not self.service:
            self.status_var.set("Service unavailable.")
            return
        self._refresh_partners()
        self._refresh_agreements()
        self._refresh_programmes()
        self._refresh_reviews()
        try:
            s = self.service.summary()
            text = (f"{s['partners']} partners · {s['agreements_live']} live "
                    f"agreements · {s['programmes']} programmes · "
                    f"{s['students']} students")
            if s["overdue_reviews"]:
                text += f"   ⚠ {s['overdue_reviews']} overdue review(s)"
            if s["high_risk"]:
                text += f"   ⚠ {s['high_risk']} high-risk partner(s)"
            self.status_var.set(text)
        except Exception:  # noqa: BLE001
            logger.debug("summary failed", exc_info=True)


__all__ = ["CollaborativeProvisionGUI"]
