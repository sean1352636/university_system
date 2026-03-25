"""Staff Absence GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.staff_absence.services.staff_absence_service import StaffAbsenceService
from education_system.college_system.core.i18n import t


class StaffAbsenceFrame(tk.Frame):
    """Staff Absence management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = StaffAbsenceService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("staff_absence.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_absences_tab()
        self._build_triggers_tab()
        self._build_stats_tab()

    # ------------------------------------------------------------------ #
    #  Tab 1: Absences                                                    #
    # ------------------------------------------------------------------ #

    def _build_absences_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("staff_absence.management"))

        # Toolbar
        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        ttk.Button(toolbar, text=t("common.create"), command=self._new_absence).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("common.view"), command=self._view_absence).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("common.edit"), command=self._edit_absence).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("common.close"), command=self._close_absence).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("common.delete"), command=self._delete_absence).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Export CSV", command=self._export_absences_csv).pack(side="left", padx=2)

        # Filters
        filter_frame = tk.Frame(tab, bg="#ecf0f1")
        filter_frame.pack(fill="x", padx=5, pady=2)

        tk.Label(filter_frame, text=t("common.type"), bg="#ecf0f1").pack(side="left", padx=2)
        self._abs_type_var = tk.StringVar(value="All")
        ttk.Combobox(filter_frame, textvariable=self._abs_type_var,
                     values=["All", "sickness", "personal", "compassionate",
                             "maternity", "paternity", "unauthorised", "other"],
                     state="readonly", width=14).pack(side="left", padx=2)

        tk.Label(filter_frame, text=t("common.status"), bg="#ecf0f1").pack(side="left", padx=2)
        self._abs_status_var = tk.StringVar(value="All")
        ttk.Combobox(filter_frame, textvariable=self._abs_status_var,
                     values=["All", "current", "closed"],
                     state="readonly", width=10).pack(side="left", padx=2)

        tk.Label(filter_frame, text=t("common.search_colon"), bg="#ecf0f1").pack(side="left", padx=2)
        self._abs_search_var = tk.StringVar()
        tk.Entry(filter_frame, textvariable=self._abs_search_var, width=18).pack(side="left", padx=2)

        ttk.Button(filter_frame, text=t("common.filter"), command=self._load_absences).pack(side="left", padx=5)

        # Treeview
        cols = ("id", "staff", "type", "start", "end", "days_lost", "status")
        self._abs_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for c, heading, w in zip(
            cols,
            ("ID", "Staff", "Type", "Start", "End", "Days Lost", "Status"),
            (50, 160, 100, 100, 100, 80, 80),
        ):
            self._abs_tree.heading(c, text=heading)
            self._abs_tree.column(c, width=w, minwidth=40)
        self._abs_tree.pack(fill="both", expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=self._abs_tree.yview)
        self._abs_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    def _load_absences(self):
        for item in self._abs_tree.get_children():
            self._abs_tree.delete(item)
        try:
            atype = self._abs_type_var.get()
            status = self._abs_status_var.get()
            search = self._abs_search_var.get().strip()
            rows = self._svc.list_absences(
                absence_type=None if atype == "All" else atype,
                status=None if status == "All" else status,
                search=search or None,
            )
            for r in rows:
                staff_name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
                self._abs_tree.insert("", "end", iid=str(r["id"]), values=(
                    r["id"],
                    staff_name or f"Staff #{r.get('staff_id', '')}",
                    r.get("absence_type", ""),
                    r.get("start_date", ""),
                    r.get("end_date", "") or "",
                    r.get("days_lost", 0),
                    r.get("status", ""),
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _new_absence(self):
        win = tk.Toplevel(self)
        win.title(t("staff_absence.log_absence"))
        win.geometry("420x480")
        win.resizable(False, False)

        entries = {}
        row = 0
        for label, key in [
            ("Staff ID*:", "staff_id"),
            ("Start Date* (YYYY-MM-DD):", "start_date"),
            ("End Date:", "end_date"),
            ("Days Lost:", "days_lost"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=4, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=4)
            entries[key] = e
            row += 1

        tk.Label(win, text="Type:").grid(row=row, column=0, padx=10, pady=4, sticky="e")
        type_var = tk.StringVar(value="sickness")
        ttk.Combobox(win, textvariable=type_var,
                     values=["sickness", "personal", "compassionate",
                             "maternity", "paternity", "unauthorised", "other"],
                     state="readonly", width=22).grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Reason:").grid(row=row, column=0, padx=10, pady=4, sticky="e")
        reason_entry = tk.Entry(win, width=25)
        reason_entry.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        bool_vars = {}
        for label, key in [
            ("Self Certified", "self_certified"),
            ("Fit Note Received", "fit_note_received"),
            ("OH Referral", "occupational_health_referral"),
        ]:
            var = tk.IntVar(value=0)
            ttk.Checkbutton(win, text=label, variable=var).grid(
                row=row, column=0, columnspan=2, padx=10, pady=2, sticky="w"
            )
            bool_vars[key] = var
            row += 1

        tk.Label(win, text="Notes:").grid(row=row, column=0, padx=10, pady=4, sticky="ne")
        notes_text = tk.Text(win, width=25, height=3)
        notes_text.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            try:
                staff_id = int(entries["staff_id"].get().strip())
                start_date = entries["start_date"].get().strip()
                if not start_date:
                    messagebox.showwarning(t("common.warning"), t("common.field_required"))
                    return
                kwargs = {"absence_type": type_var.get()}
                end = entries["end_date"].get().strip()
                if end:
                    kwargs["end_date"] = end
                dl = entries["days_lost"].get().strip()
                if dl:
                    kwargs["days_lost"] = float(dl)
                reason = reason_entry.get().strip()
                if reason:
                    kwargs["reason"] = reason
                notes = notes_text.get("1.0", "end").strip()
                if notes:
                    kwargs["notes"] = notes
                for k, var in bool_vars.items():
                    kwargs[k] = var.get()
                self._svc.create_absence(staff_id, start_date, **kwargs)
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_absences()
            except ValueError:
                messagebox.showerror(t("common.error"), t("common.invalid_input"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=15
        )

    def _view_absence(self):
        sel = self._abs_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        absence = self._svc.get_absence(int(sel[0]))
        if not absence:
            messagebox.showerror(t("common.error"), t("common.no_data"))
            return

        win = tk.Toplevel(self)
        win.title(f"Absence #{absence['id']}")
        win.geometry("450x520")
        win.resizable(False, False)

        staff_name = f"{absence.get('first_name', '')} {absence.get('last_name', '')}".strip()
        details = [
            ("ID", absence["id"]),
            ("Staff", staff_name or f"#{absence.get('staff_id', '')}"),
            ("Type", absence.get("absence_type", "")),
            ("Start Date", absence.get("start_date", "")),
            ("End Date", absence.get("end_date", "") or ""),
            ("Days Lost", absence.get("days_lost", 0)),
            ("Reason", absence.get("reason", "") or ""),
            ("Status", absence.get("status", "")),
            ("Self Certified", "Yes" if absence.get("self_certified") else "No"),
            ("Fit Note Received", "Yes" if absence.get("fit_note_received") else "No"),
            ("Fit Note Expiry", absence.get("fit_note_expiry", "") or ""),
            ("RTW Done", "Yes" if absence.get("return_to_work_done") else "No"),
            ("RTW Date", absence.get("rtw_date", "") or ""),
            ("RTW Notes", absence.get("rtw_notes", "") or ""),
            ("OH Referral", "Yes" if absence.get("occupational_health_referral") else "No"),
            ("Trigger Reached", "Yes" if absence.get("trigger_point_reached") else "No"),
            ("Notes", absence.get("notes", "") or ""),
            ("Created", absence.get("created_at", "")),
            ("Updated", absence.get("updated_at", "")),
        ]
        for i, (lbl, val) in enumerate(details):
            tk.Label(win, text=f"{lbl}:", font=("Helvetica", 10, "bold"),
                     anchor="e").grid(row=i, column=0, padx=10, pady=2, sticky="ne")
            tk.Label(win, text=str(val), wraplength=280,
                     anchor="w").grid(row=i, column=1, padx=10, pady=2, sticky="w")

        ttk.Button(win, text=t("common.close"), command=win.destroy).grid(
            row=len(details), column=0, columnspan=2, pady=10
        )

    def _edit_absence(self):
        sel = self._abs_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        absence_id = int(sel[0])
        absence = self._svc.get_absence(absence_id)
        if not absence:
            messagebox.showerror(t("common.error"), t("common.no_data"))
            return

        win = tk.Toplevel(self)
        win.title(f"Edit Absence #{absence_id}")
        win.geometry("420x480")
        win.resizable(False, False)

        entries = {}
        row = 0
        for label, key, default in [
            ("Start Date:", "start_date", absence.get("start_date", "")),
            ("End Date:", "end_date", absence.get("end_date", "") or ""),
            ("Days Lost:", "days_lost", str(absence.get("days_lost", 0))),
            ("Reason:", "reason", absence.get("reason", "") or ""),
            ("Fit Note Expiry:", "fit_note_expiry", absence.get("fit_note_expiry", "") or ""),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=4, sticky="e")
            e = tk.Entry(win, width=25)
            e.insert(0, default)
            e.grid(row=row, column=1, padx=10, pady=4)
            entries[key] = e
            row += 1

        tk.Label(win, text="Type:").grid(row=row, column=0, padx=10, pady=4, sticky="e")
        type_var = tk.StringVar(value=absence.get("absence_type", "sickness"))
        ttk.Combobox(win, textvariable=type_var,
                     values=["sickness", "personal", "compassionate",
                             "maternity", "paternity", "unauthorised", "other"],
                     state="readonly", width=22).grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Status:").grid(row=row, column=0, padx=10, pady=4, sticky="e")
        status_var = tk.StringVar(value=absence.get("status", "current"))
        ttk.Combobox(win, textvariable=status_var,
                     values=["current", "closed"],
                     state="readonly", width=22).grid(row=row, column=1, padx=10, pady=4)
        row += 1

        bool_vars = {}
        for label, key in [
            ("Self Certified", "self_certified"),
            ("Fit Note Received", "fit_note_received"),
            ("OH Referral", "occupational_health_referral"),
            ("Trigger Point Reached", "trigger_point_reached"),
        ]:
            var = tk.IntVar(value=1 if absence.get(key) else 0)
            ttk.Checkbutton(win, text=label, variable=var).grid(
                row=row, column=0, columnspan=2, padx=10, pady=2, sticky="w"
            )
            bool_vars[key] = var
            row += 1

        tk.Label(win, text="Notes:").grid(row=row, column=0, padx=10, pady=4, sticky="ne")
        notes_text = tk.Text(win, width=25, height=3)
        notes_text.insert("1.0", absence.get("notes", "") or "")
        notes_text.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            try:
                kwargs = {
                    "absence_type": type_var.get(),
                    "status": status_var.get(),
                }
                for key in ("start_date", "end_date", "reason", "fit_note_expiry"):
                    val = entries[key].get().strip()
                    kwargs[key] = val if val else None
                dl = entries["days_lost"].get().strip()
                kwargs["days_lost"] = float(dl) if dl else 0
                notes = notes_text.get("1.0", "end").strip()
                kwargs["notes"] = notes if notes else None
                for k, var in bool_vars.items():
                    kwargs[k] = var.get()
                self._svc.update_absence(absence_id, **kwargs)
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
                win.destroy()
                self._load_absences()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=15
        )

    def _close_absence(self):
        sel = self._abs_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        absence_id = int(sel[0])
        absence = self._svc.get_absence(absence_id)
        if not absence:
            messagebox.showerror(t("common.error"), t("common.no_data"))
            return
        if absence.get("status") == "closed":
            messagebox.showinfo(t("common.info"), "This absence is already closed.")
            return

        win = tk.Toplevel(self)
        win.title(f"Close Absence #{absence_id}")
        win.geometry("380x250")
        win.resizable(False, False)

        tk.Label(win, text="End Date* (YYYY-MM-DD):").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        end_entry = tk.Entry(win, width=20)
        end_entry.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(win, text="Days Lost*:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        days_entry = tk.Entry(win, width=20)
        days_entry.insert(0, str(absence.get("days_lost", 0)))
        days_entry.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(win, text="RTW Notes:").grid(row=2, column=0, padx=10, pady=5, sticky="ne")
        rtw_text = tk.Text(win, width=22, height=4)
        rtw_text.grid(row=2, column=1, padx=10, pady=5)

        def save():
            try:
                end_date = end_entry.get().strip()
                if not end_date:
                    messagebox.showwarning(t("common.warning"), t("common.field_required"))
                    return
                days_lost = float(days_entry.get().strip())
                rtw_notes = rtw_text.get("1.0", "end").strip() or None
                self._svc.close_absence(absence_id, end_date, days_lost, rtw_notes)
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
                win.destroy()
                self._load_absences()
            except ValueError:
                messagebox.showerror(t("common.error"), t("common.invalid_input"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.close"), command=save).grid(
            row=3, column=0, columnspan=2, pady=15
        )

    def _delete_absence(self):
        sel = self._abs_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        if messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            try:
                self._svc.delete_absence(int(sel[0]))
                self._load_absences()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

    # ------------------------------------------------------------------ #
    #  Tab 2: Triggers                                                    #
    # ------------------------------------------------------------------ #

    def _build_triggers_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text="Triggers")

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("common.create"), command=self._new_trigger).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("common.edit"), command=self._edit_trigger).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("common.delete"), command=self._delete_trigger).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Export CSV", command=self._export_triggers_csv).pack(side="left", padx=2)

        cols = ("id", "name", "type", "threshold", "period", "action", "status")
        self._trig_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c, heading, w in zip(
            cols,
            ("ID", "Name", "Type", "Threshold", "Period (months)", "Action Required", "Status"),
            (50, 180, 80, 80, 110, 200, 80),
        ):
            self._trig_tree.heading(c, text=heading)
            self._trig_tree.column(c, width=w, minwidth=40)
        self._trig_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_triggers(self):
        for item in self._trig_tree.get_children():
            self._trig_tree.delete(item)
        try:
            rows = self._svc.list_triggers()
            for r in rows:
                self._trig_tree.insert("", "end", iid=str(r["id"]), values=(
                    r["id"],
                    r.get("trigger_name", ""),
                    r.get("trigger_type", ""),
                    r.get("threshold", ""),
                    r.get("period_months", ""),
                    r.get("action_required", "") or "",
                    r.get("status", ""),
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _new_trigger(self):
        win = tk.Toplevel(self)
        win.title("New Trigger")
        win.geometry("400x320")
        win.resizable(False, False)

        entries = {}
        row = 0
        for label, key in [
            ("Trigger Name*:", "trigger_name"),
            ("Threshold*:", "threshold"),
            ("Period (months):", "period_months"),
            ("Action Required:", "action_required"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            entries[key] = e
            row += 1

        tk.Label(win, text="Type:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        type_var = tk.StringVar(value="days")
        ttk.Combobox(win, textvariable=type_var,
                     values=["days", "occasions"],
                     state="readonly", width=22).grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Status:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        status_var = tk.StringVar(value="active")
        ttk.Combobox(win, textvariable=status_var,
                     values=["active", "inactive"],
                     state="readonly", width=22).grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            try:
                name = entries["trigger_name"].get().strip()
                threshold = entries["threshold"].get().strip()
                if not name or not threshold:
                    messagebox.showwarning(t("common.warning"), t("common.both_required"))
                    return
                kwargs = {"trigger_type": type_var.get(), "status": status_var.get()}
                pm = entries["period_months"].get().strip()
                if pm:
                    kwargs["period_months"] = int(pm)
                action = entries["action_required"].get().strip()
                if action:
                    kwargs["action_required"] = action
                self._svc.create_trigger(name, int(threshold), **kwargs)
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_triggers()
            except ValueError:
                messagebox.showerror(t("common.error"), t("common.invalid_input"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=15
        )

    def _edit_trigger(self):
        sel = self._trig_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        trigger_id = int(sel[0])
        trigger = self._svc.get_trigger(trigger_id)
        if not trigger:
            messagebox.showerror(t("common.error"), t("common.no_data"))
            return

        win = tk.Toplevel(self)
        win.title(f"Edit Trigger #{trigger_id}")
        win.geometry("400x320")
        win.resizable(False, False)

        entries = {}
        row = 0
        for label, key, default in [
            ("Trigger Name:", "trigger_name", trigger.get("trigger_name", "")),
            ("Threshold:", "threshold", str(trigger.get("threshold", ""))),
            ("Period (months):", "period_months", str(trigger.get("period_months", 12))),
            ("Action Required:", "action_required", trigger.get("action_required", "") or ""),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.insert(0, default)
            e.grid(row=row, column=1, padx=10, pady=5)
            entries[key] = e
            row += 1

        tk.Label(win, text="Type:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        type_var = tk.StringVar(value=trigger.get("trigger_type", "days"))
        ttk.Combobox(win, textvariable=type_var,
                     values=["days", "occasions"],
                     state="readonly", width=22).grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Status:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        status_var = tk.StringVar(value=trigger.get("status", "active"))
        ttk.Combobox(win, textvariable=status_var,
                     values=["active", "inactive"],
                     state="readonly", width=22).grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            try:
                kwargs = {
                    "trigger_name": entries["trigger_name"].get().strip(),
                    "trigger_type": type_var.get(),
                    "threshold": int(entries["threshold"].get().strip()),
                    "period_months": int(entries["period_months"].get().strip() or 12),
                    "action_required": entries["action_required"].get().strip() or None,
                    "status": status_var.get(),
                }
                self._svc.update_trigger(trigger_id, **kwargs)
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
                win.destroy()
                self._load_triggers()
            except ValueError:
                messagebox.showerror(t("common.error"), t("common.invalid_input"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=15
        )

    def _delete_trigger(self):
        sel = self._trig_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        if messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            try:
                self._svc.delete_trigger(int(sel[0]))
                self._load_triggers()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

    # ------------------------------------------------------------------ #
    #  Tab 3: Statistics                                                  #
    # ------------------------------------------------------------------ #

    def _build_stats_tab(self):
        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._stats_tab, text=t("common.summary"))

        self._stats_container = tk.Frame(self._stats_tab, bg="#ecf0f1")
        self._stats_container.pack(fill="both", expand=True, padx=20, pady=20)

    def _load_stats(self):
        for widget in self._stats_container.winfo_children():
            widget.destroy()
        try:
            stats = self._svc.get_stats()

            # Summary cards
            summary_frame = tk.LabelFrame(self._stats_container, text=t("common.summary"),
                                          bg="#ecf0f1", font=("Helvetica", 11, "bold"))
            summary_frame.pack(fill="x", pady=5)

            labels = [
                ("Total Absences:", stats.get("total_absences", 0)),
                ("Current:", stats.get("current", 0)),
                ("Closed:", stats.get("closed", 0)),
                ("Total Days Lost:", stats.get("total_days_lost", 0)),
                ("Staff Currently Absent:", stats.get("staff_on_absence", 0)),
                ("Active Triggers:", stats.get("active_triggers", 0)),
            ]
            for i, (lbl, val) in enumerate(labels):
                r, c = divmod(i, 3)
                tk.Label(summary_frame, text=lbl, font=("Helvetica", 10, "bold"),
                         bg="#ecf0f1", anchor="e").grid(row=r, column=c * 2, padx=8, pady=4, sticky="e")
                tk.Label(summary_frame, text=str(val), font=("Helvetica", 10),
                         bg="#ecf0f1", anchor="w").grid(row=r, column=c * 2 + 1, padx=8, pady=4, sticky="w")

            # By-type breakdown
            type_frame = tk.LabelFrame(self._stats_container, text="Absences by Type",
                                       bg="#ecf0f1", font=("Helvetica", 11, "bold"))
            type_frame.pack(fill="x", pady=10)

            by_type = stats.get("by_type", [])
            if by_type:
                tk.Label(type_frame, text="Type", font=("Helvetica", 10, "bold"),
                         bg="#ecf0f1").grid(row=0, column=0, padx=10, pady=2)
                tk.Label(type_frame, text="Count", font=("Helvetica", 10, "bold"),
                         bg="#ecf0f1").grid(row=0, column=1, padx=10, pady=2)
                tk.Label(type_frame, text="Days Lost", font=("Helvetica", 10, "bold"),
                         bg="#ecf0f1").grid(row=0, column=2, padx=10, pady=2)
                for i, bt in enumerate(by_type, start=1):
                    tk.Label(type_frame, text=bt.get("absence_type", ""),
                             bg="#ecf0f1").grid(row=i, column=0, padx=10, pady=2)
                    tk.Label(type_frame, text=str(bt.get("cnt", 0)),
                             bg="#ecf0f1").grid(row=i, column=1, padx=10, pady=2)
                    tk.Label(type_frame, text=str(bt.get("days", 0)),
                             bg="#ecf0f1").grid(row=i, column=2, padx=10, pady=2)
            else:
                tk.Label(type_frame, text=t("common.no_data"),
                         bg="#ecf0f1").pack(padx=10, pady=10)
        except Exception as e:
            tk.Label(self._stats_container, text=f"{t('common.error')}: {e}",
                     bg="#ecf0f1", fg="red").pack(pady=20)

    def _export_absences_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._abs_tree, "staff_absences_export.csv")

    def _export_triggers_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._trig_tree, "staff_absence_triggers_export.csv")

    # ------------------------------------------------------------------ #
    #  Refresh                                                            #
    # ------------------------------------------------------------------ #

    def refresh(self):
        self._load_absences()
        self._load_triggers()
        self._load_stats()
