"""Study Abroad & Exchange GUI.

Three tabs — Placements, Exchange Agreements, Credit Recognition — with a
compliance strip that surfaces the two things that quietly go wrong:
students abroad on an unsigned learning agreement, and returned students
whose credit was never recognised.
"""

from __future__ import annotations

import csv
import logging
import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)


class StudentMobilityGUI:
    """Top-level window over :class:`StudentMobilityService`."""

    def __init__(self, parent=None, app=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.app = app
        self.root.title(_t("gui.academics.student_mobility.windows.title",
                           default="===== WINDOWS ====="))
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        try:
            from education_system.systems.university.domains.curriculum.domain.student_mobility.services.student_mobility_service import (
                StudentMobilityService,
            )
            self.service = StudentMobilityService()
        except Exception as exc:  # noqa: BLE001
            logger.error("Student mobility service init failed: %s", exc)
            self.service = None

        self._build_ui()
        self.refresh_all()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        self.status_var = tk.StringVar()
        bar = ttk.Frame(self.root)
        bar.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Label(bar, textvariable=self.status_var,
                  font=("", 10, "bold")).pack(side=tk.LEFT)
        ttk.Button(bar, text=_t("common.refresh", default="Refresh"),
                   command=self.refresh_all).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bar, text=_t("gui.academics.student_mobility.buttons.export",
                                default="Export Placements"),
                   command=self._export).pack(side=tk.RIGHT, padx=2)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._build_placements_tab(notebook)
        self._build_agreements_tab(notebook)
        self._build_recognition_tab(notebook)

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

    def _selected_id(self, tree) -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showwarning(_t("common.selection", default="Selection"),
                                   _t("common.select_a_row_first",
                                      default="Select a row first."),
                                   parent=self.root)
            return None
        return int(tree.item(sel[0], "values")[0])

    # ---------------------------------------------------------- placements
    def _build_placements_tab(self, notebook) -> None:
        from education_system.systems.university.domains.curriculum.domain.student_mobility._db_init import (
            PLACEMENT_STATUSES,
        )
        tab = ttk.Frame(notebook)
        notebook.add(tab, text=_t("gui.academics.student_mobility.tabs.placements",
                                  default="Placements"))

        actions = ttk.Frame(tab)
        actions.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(actions, text=_t("common.add", default="Add"),
                   command=self._add_placement).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions,
                   text=_t("gui.academics.student_mobility.buttons.set_status",
                           default="Set Status"),
                   command=self._set_status).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions,
                   text=_t("gui.academics.student_mobility.buttons.learning_agreement",
                           default="Learning Agreement"),
                   command=self._learning_agreement).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions,
                   text=_t("gui.academics.student_mobility.buttons.preparation",
                           default="Preparation Gaps"),
                   command=self._show_preparation_gaps).pack(side=tk.LEFT, padx=12)

        self.status_filter = tk.StringVar(value="All")
        ttk.Label(actions, text=_t("common.status", default="Status")).pack(
            side=tk.LEFT, padx=(20, 4))
        combo = ttk.Combobox(actions, textvariable=self.status_filter,
                             values=["All", *PLACEMENT_STATUSES],
                             state="readonly", width=18)
        combo.pack(side=tk.LEFT)
        combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_placements())

        self.placements_tree = self._tree(
            tab, ("placement_id", "student_id", "direction", "host_institution",
                  "host_country", "academic_year", "start_date", "end_date",
                  "status", "credits_expected", "credits_recognised",
                  "recognition_state"),
            (70, 100, 90, 210, 110, 110, 100, 100, 130, 90, 100, 150))

    def _refresh_placements(self) -> None:
        if not self.service:
            return
        for row in self.placements_tree.get_children():
            self.placements_tree.delete(row)
        status = self.status_filter.get()
        for p in self.service.list_placements(status=status):
            self.placements_tree.insert("", tk.END, values=(
                p["placement_id"], p["student_id"], p["direction"],
                p.get("host_institution") or "", p.get("host_country") or "",
                p.get("academic_year") or "", p.get("start_date") or "",
                p.get("end_date") or "", p["status"],
                p.get("credits_expected") or "",
                p.get("credits_recognised") or 0,
                p.get("recognition_state") or ""))

    def _add_placement(self) -> None:
        from education_system.systems.university.domains.curriculum.domain.student_mobility._db_init import (
            DIRECTIONS, FUNDING_SCHEMES, MOBILITY_TYPES, RECOGNITION_MODES,
        )
        dlg = tk.Toplevel(self.root)
        dlg.title("Create Placement")
        dlg.geometry("560x560")
        dlg.transient(self.root)
        dlg.grab_set()
        body = ttk.Frame(dlg)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        agreements = self.service.list_agreements()
        agreement_labels = ["(none)"] + [
            f"{a['mobility_agreement_id']} — {a['host_institution']}"
            for a in agreements]

        text_vars = {k: tk.StringVar() for k in
                     ("student_id", "host_institution", "host_country",
                      "academic_year", "start_date", "end_date",
                      "credits_expected", "grant_amount")}
        agreement_var = tk.StringVar(value=agreement_labels[0])
        direction_var = tk.StringVar(value=DIRECTIONS[0])
        type_var = tk.StringVar(value=MOBILITY_TYPES[0])
        funding_var = tk.StringVar(value=FUNDING_SCHEMES[0])
        mode_var = tk.StringVar(value=RECOGNITION_MODES[0])

        rows = [("Student ID", text_vars["student_id"], None),
                ("Direction", direction_var, list(DIRECTIONS)),
                ("Exchange agreement", agreement_var, agreement_labels),
                ("Host institution", text_vars["host_institution"], None),
                ("Host country", text_vars["host_country"], None),
                ("Mobility type", type_var, list(MOBILITY_TYPES)),
                ("Funding scheme", funding_var, list(FUNDING_SCHEMES)),
                ("Grant amount", text_vars["grant_amount"], None),
                ("Academic year", text_vars["academic_year"], None),
                ("Start date", text_vars["start_date"], None),
                ("End date", text_vars["end_date"], None),
                ("Credits expected", text_vars["credits_expected"], None),
                ("Recognition mode", mode_var, list(RECOGNITION_MODES))]
        for i, (label, var, options) in enumerate(rows):
            ttk.Label(body, text=f"{label}:").grid(row=i, column=0, sticky=tk.E,
                                                   padx=6, pady=4)
            if options:
                ttk.Combobox(body, textvariable=var, values=options, width=38,
                             state="readonly").grid(row=i, column=1,
                                                    sticky=tk.W, padx=6, pady=4)
            else:
                ttk.Entry(body, textvariable=var, width=40).grid(
                    row=i, column=1, sticky=tk.W, padx=6, pady=4)

        def save() -> None:
            agreement = agreement_var.get()
            agreement_id = (int(agreement.split("—")[0].strip())
                            if agreement != "(none)" else None)
            credits = text_vars["credits_expected"].get().strip()
            grant = text_vars["grant_amount"].get().strip()
            try:
                self.service.create_placement(
                    text_vars["student_id"].get().strip(),
                    host_institution=text_vars["host_institution"].get().strip() or None,
                    direction=direction_var.get(),
                    mobility_agreement_id=agreement_id,
                    host_country=text_vars["host_country"].get().strip() or None,
                    mobility_type=type_var.get(),
                    funding_scheme=funding_var.get(),
                    grant_amount=float(grant) if grant else None,
                    academic_year=text_vars["academic_year"].get().strip() or None,
                    start_date=text_vars["start_date"].get().strip() or None,
                    end_date=text_vars["end_date"].get().strip() or None,
                    credits_expected=float(credits) if credits else None,
                    recognition_mode=mode_var.get())
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

    def _set_status(self) -> None:
        from education_system.systems.university.domains.curriculum.domain.student_mobility._db_init import (
            PLACEMENT_STATUSES,
        )
        pid = self._selected_id(self.placements_tree)
        if pid is None:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Set Placement Status")
        dlg.geometry("400x170")
        dlg.transient(self.root)
        dlg.grab_set()
        var = tk.StringVar(value=PLACEMENT_STATUSES[0])
        ttk.Label(dlg, text="New status:").pack(padx=12, pady=(16, 4), anchor=tk.W)
        ttk.Combobox(dlg, textvariable=var, values=list(PLACEMENT_STATUSES),
                     state="readonly", width=34).pack(padx=12)

        def save() -> None:
            try:
                self.service.set_status(pid, var.get())
            except Exception as exc:  # noqa: BLE001
                # The completion guard lands here — it is the message the
                # user needs, not a stack trace.
                messagebox.showwarning(_t("common.error", default="Error"),
                                       str(exc), parent=dlg)
                return
            dlg.destroy()
            self.refresh_all()

        ttk.Button(dlg, text=_t("common.save", default="Save"),
                   command=save).pack(pady=14)

    def _learning_agreement(self) -> None:
        pid = self._selected_id(self.placements_tree)
        if pid is None:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Learning Agreement — placement {pid}")
        dlg.geometry("980x520")
        dlg.transient(self.root)

        columns = ("line_id", "host_module_code", "host_module_title",
                   "host_credits", "home_module_code", "home_credits", "state")
        tree = ttk.Treeview(dlg, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=col.replace("_", " ").title())
            tree.column(col, width=130, anchor=tk.W)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def reload() -> None:
            for row in tree.get_children():
                tree.delete(row)
            for line in self.service.list_learning_agreement(pid):
                tree.insert("", tk.END, values=tuple(
                    line.get(c, "") or "" for c in columns))

        def add_line() -> None:
            sub = tk.Toplevel(dlg)
            sub.title("Add Learning Agreement Line")
            sub.geometry("440x330")
            sub.transient(dlg)
            sub.grab_set()
            body = ttk.Frame(sub)
            body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
            fields = (("Host module title", "host_module_title"),
                      ("Host module code", "host_module_code"),
                      ("Host credits", "host_credits"),
                      ("Home module code", "home_module_code"),
                      ("Home module title", "home_module_title"),
                      ("Home credits", "home_credits"))
            values = {key: tk.StringVar() for _, key in fields}
            for i, (label, key) in enumerate(fields):
                ttk.Label(body, text=f"{label}:").grid(row=i, column=0,
                                                       sticky=tk.E, padx=6, pady=6)
                ttk.Entry(body, textvariable=values[key], width=28).grid(
                    row=i, column=1, sticky=tk.W, padx=6, pady=6)

            def save() -> None:
                def num(key):
                    raw = values[key].get().strip()
                    return float(raw) if raw else None
                try:
                    self.service.add_learning_agreement_line(
                        pid, values["host_module_title"].get().strip(),
                        host_module_code=values["host_module_code"].get().strip() or None,
                        host_credits=num("host_credits"),
                        home_module_code=values["home_module_code"].get().strip() or None,
                        home_module_title=values["home_module_title"].get().strip() or None,
                        home_credits=num("home_credits"))
                except Exception as exc:  # noqa: BLE001
                    messagebox.showerror(_t("common.error", default="Error"),
                                         str(exc), parent=sub)
                    return
                sub.destroy()
                reload()

            ttk.Button(sub, text=_t("common.save", default="Save"),
                       command=save).pack(pady=10)

        def sign_all() -> None:
            signed = self.service.sign_learning_agreement(pid)
            messagebox.showinfo(_t("common.info", default="Info"),
                                f"{signed} line(s) signed.", parent=dlg)
            reload()
            self.refresh_all()

        buttons = ttk.Frame(dlg)
        buttons.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(buttons, text=_t("common.add", default="Add Line"),
                   command=add_line).pack(side=tk.LEFT, padx=2)
        ttk.Button(buttons, text=_t("gui.academics.student_mobility.buttons.sign",
                                    default="Sign All Lines"),
                   command=sign_all).pack(side=tk.LEFT, padx=2)
        reload()

    def _show_preparation_gaps(self) -> None:
        rows = self.service.preparation_gaps()
        if not rows:
            messagebox.showinfo(_t("common.info", default="Info"),
                                "Every approved placement has insurance and a "
                                "risk assessment recorded.", parent=self.root)
            return
        self._simple_report("Placements Missing Insurance / Risk Assessment",
                            rows, ("placement_id", "student_id",
                                   "host_institution", "start_date",
                                   "insurance_confirmed", "risk_assessed"))

    # ---------------------------------------------------------- agreements
    def _build_agreements_tab(self, notebook) -> None:
        tab = ttk.Frame(notebook)
        notebook.add(tab, text=_t("gui.academics.student_mobility.tabs.agreements",
                                  default="Exchange Agreements"))
        actions = ttk.Frame(tab)
        actions.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(actions, text=_t("common.add", default="Add"),
                   command=self._add_agreement).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions,
                   text=_t("gui.academics.student_mobility.buttons.availability",
                           default="Place Availability"),
                   command=self._show_availability).pack(side=tk.LEFT, padx=2)

        self.agreements_tree = self._tree(
            tab, ("mobility_agreement_id", "host_institution", "country",
                  "subject_area", "mobility_type", "places_outgoing",
                  "places_incoming", "valid_to", "coordinator"),
            (80, 240, 120, 170, 170, 120, 120, 110, 150))

    def _refresh_agreements(self) -> None:
        if not self.service:
            return
        for row in self.agreements_tree.get_children():
            self.agreements_tree.delete(row)
        for a in self.service.list_agreements(active_only=False):
            self.agreements_tree.insert("", tk.END, values=(
                a["mobility_agreement_id"], a["host_institution"],
                a.get("country") or "", a.get("subject_area") or "",
                a.get("mobility_type") or "", a.get("places_outgoing") or 0,
                a.get("places_incoming") or 0, a.get("valid_to") or "",
                a.get("coordinator") or ""))

    def _add_agreement(self) -> None:
        from education_system.systems.university.domains.curriculum.domain.student_mobility._db_init import (
            MOBILITY_TYPES,
        )
        dlg = tk.Toplevel(self.root)
        dlg.title("Add Exchange Agreement")
        dlg.geometry("520x440")
        dlg.transient(self.root)
        dlg.grab_set()
        body = ttk.Frame(dlg)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        text_vars = {k: tk.StringVar() for k in
                     ("host_institution", "country", "subject_area", "level",
                      "places_outgoing", "places_incoming", "valid_from",
                      "valid_to", "coordinator")}
        type_var = tk.StringVar(value=MOBILITY_TYPES[0])
        rows = [("Host institution", text_vars["host_institution"], None),
                ("Country", text_vars["country"], None),
                ("Subject area", text_vars["subject_area"], None),
                ("Level", text_vars["level"], None),
                ("Mobility type", type_var, list(MOBILITY_TYPES)),
                ("Outgoing places", text_vars["places_outgoing"], None),
                ("Incoming places", text_vars["places_incoming"], None),
                ("Valid from", text_vars["valid_from"], None),
                ("Valid to", text_vars["valid_to"], None),
                ("Coordinator", text_vars["coordinator"], None)]
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
            def num(key):
                raw = text_vars[key].get().strip()
                return int(raw) if raw.isdigit() else 0
            try:
                self.service.add_agreement(
                    text_vars["host_institution"].get().strip(),
                    country=text_vars["country"].get().strip() or None,
                    subject_area=text_vars["subject_area"].get().strip() or None,
                    level=text_vars["level"].get().strip() or None,
                    mobility_type=type_var.get(),
                    places_outgoing=num("places_outgoing"),
                    places_incoming=num("places_incoming"),
                    valid_from=text_vars["valid_from"].get().strip() or None,
                    valid_to=text_vars["valid_to"].get().strip() or None,
                    coordinator=text_vars["coordinator"].get().strip() or None)
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

    def _show_availability(self) -> None:
        rows = self.service.place_availability()
        self._simple_report("Outgoing Place Availability", rows,
                            ("mobility_agreement_id", "host_institution",
                             "country", "places", "taken", "remaining"))

    # --------------------------------------------------------- recognition
    def _build_recognition_tab(self, notebook) -> None:
        tab = ttk.Frame(notebook)
        notebook.add(tab, text=_t("gui.academics.student_mobility.tabs.recognition",
                                  default="Credit Recognition"))
        actions = ttk.Frame(tab)
        actions.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(actions,
                   text=_t("gui.academics.student_mobility.buttons.record_recognition",
                           default="Record Recognition"),
                   command=self._record_recognition).pack(side=tk.LEFT, padx=2)
        ttk.Label(actions, text=_t(
            "gui.academics.student_mobility.labels.awaiting",
            default="Concluded placements whose credit has not come home")).pack(
            side=tk.LEFT, padx=16)

        self.recognition_tree = self._tree(
            tab, ("placement_id", "student_id", "host_institution", "end_date",
                  "credits_expected", "credits_recognised", "recognition_state",
                  "status"),
            (80, 110, 240, 110, 130, 140, 170, 130))

    def _refresh_recognition(self) -> None:
        if not self.service:
            return
        for row in self.recognition_tree.get_children():
            self.recognition_tree.delete(row)
        for p in self.service.awaiting_recognition(older_than_days=0):
            self.recognition_tree.insert("", tk.END, values=(
                p["placement_id"], p["student_id"],
                p.get("host_institution") or "", p.get("end_date") or "",
                p.get("credits_expected") or "", p.get("credits_recognised") or 0,
                p.get("recognition_state") or "", p["status"]))

    def _record_recognition(self) -> None:
        from education_system.systems.university.domains.curriculum.domain.student_mobility._db_init import (
            RECOGNITION_MODES,
        )
        pid = self._selected_id(self.recognition_tree)
        if pid is None:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Record Credit Recognition — placement {pid}")
        dlg.geometry("470x400")
        dlg.transient(self.root)
        dlg.grab_set()
        body = ttk.Frame(dlg)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        fields = (("Host module code", "host_module_code"),
                  ("Host grade", "host_grade"),
                  ("Host credits", "host_credits"),
                  ("Home module code", "home_module_code"),
                  ("Home credits awarded", "home_credits"),
                  ("Converted mark", "converted_mark"))
        values = {key: tk.StringVar() for _, key in fields}
        mode_var = tk.StringVar(value=RECOGNITION_MODES[0])
        for i, (label, key) in enumerate(fields):
            ttk.Label(body, text=f"{label}:").grid(row=i, column=0, sticky=tk.E,
                                                   padx=6, pady=6)
            ttk.Entry(body, textvariable=values[key], width=26).grid(
                row=i, column=1, sticky=tk.W, padx=6, pady=6)
        ttk.Label(body, text="Mode:").grid(row=len(fields), column=0,
                                           sticky=tk.E, padx=6, pady=6)
        ttk.Combobox(body, textvariable=mode_var, values=list(RECOGNITION_MODES),
                     state="readonly", width=24).grid(
            row=len(fields), column=1, sticky=tk.W, padx=6, pady=6)

        def save() -> None:
            def num(key):
                raw = values[key].get().strip()
                return float(raw) if raw else None
            try:
                self.service.record_recognition(
                    pid, host_module_code=values["host_module_code"].get().strip() or None,
                    host_grade=values["host_grade"].get().strip() or None,
                    host_credits=num("host_credits"),
                    home_module_code=values["home_module_code"].get().strip() or None,
                    home_credits=num("home_credits"),
                    converted_mark=num("converted_mark"),
                    mode=mode_var.get())
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

    # -------------------------------------------------------------- shared
    def _simple_report(self, title: str, rows: list[dict],
                       columns: tuple[str, ...]) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.geometry("940x460")
        dlg.transient(self.root)
        tree = ttk.Treeview(dlg, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=col.replace("_", " ").title())
            tree.column(col, width=150, anchor=tk.W)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        for row in rows:
            tree.insert("", tk.END,
                        values=tuple(row.get(c, "") if row.get(c) is not None
                                     else "" for c in columns))

    def _export(self) -> None:
        if not self.service:
            return
        rows = self.service.list_placements()
        if not rows:
            messagebox.showinfo(_t("common.info", default="Info"),
                                "No placements to export.", parent=self.root)
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"mobility_placements_{date.today().isoformat()}.csv")
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
                            f"Exported {len(rows)} placements.", parent=self.root)

    def refresh_all(self) -> None:
        if not self.service:
            self.status_var.set("Service unavailable.")
            return
        self._refresh_placements()
        self._refresh_agreements()
        self._refresh_recognition()
        try:
            s = self.service.summary()
            text = (f"{s['agreements']} agreements · {s['outgoing']} outgoing · "
                    f"{s['incoming']} incoming · {s['away_now']} away now")
            if s["awaiting_recognition"]:
                text += f"   ⚠ {s['awaiting_recognition']} awaiting credit recognition"
            if s["unsigned_agreements"]:
                text += f"   ⚠ {s['unsigned_agreements']} unsigned learning agreement(s)"
            self.status_var.set(text)
        except Exception:  # noqa: BLE001
            logger.debug("mobility summary failed", exc_info=True)


__all__ = ["StudentMobilityGUI"]
