"""WellbeingFrame GUI for the University System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.post_18.university_system.modules.domain.student_affairs.student_wellbeing.services.wellbeing_service import WellbeingService


class WellbeingFrame(tk.Frame):
    """GUI for managing wellbeing."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = WellbeingService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Wellbeing",
                 fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Tabs
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self._referrals_tab = tk.Frame(self._notebook)
        self._notebook.add(self._referrals_tab, text="Referrals")
        self._check_ins_tab = tk.Frame(self._notebook)
        self._notebook.add(self._check_ins_tab, text="Check-ins")
        self._counselling_tab = tk.Frame(self._notebook)
        self._notebook.add(self._counselling_tab, text="Counselling")
        self._summary_tab = tk.Frame(self._notebook)
        self._notebook.add(self._summary_tab, text="Summary")

        self._build_list_tab()
        self._build_check_ins_tab()
        self._build_counselling_tab()
        self._build_summary_tab()

    def _build_counselling_tab(self):
        """Embed the shared CounsellingPanel (staff role) into the Counselling tab."""
        from education_system.post_18.university_system.modules.domain.student_affairs.gui.counselling_panel import (
            CounsellingPanel,
        )
        panel = CounsellingPanel(self._counselling_tab, auth=self._auth, role="staff")
        panel.pack(fill="both", expand=True)

    # --------------------------------------------------------------- check-ins
    _CHECKIN_COLS = ("id", "student_id", "mood_rating", "logged_by",
                     "created_at", "notes")
    _CHECKIN_WIDTHS = {"id": 50, "student_id": 100, "mood_rating": 80,
                       "logged_by": 110, "created_at": 150, "notes": 320}

    def _build_check_ins_tab(self):
        frame = self._check_ins_tab

        # Cache (label -> student_id) populated from the students table.
        self._student_options = self._service.list_student_ids()
        self._student_label_to_id = {label: sid for sid, label in self._student_options}
        labels = [label for _sid, label in self._student_options]

        form = tk.Frame(frame, bg="#d5dbdb", padx=6, pady=6)
        form.pack(fill="x")
        tk.Label(form, text="Student:", bg="#d5dbdb").pack(side="left")
        self._chk_student = tk.StringVar()
        self._chk_student_cb = ttk.Combobox(form, textvariable=self._chk_student,
                                            values=labels, width=32, state="readonly")
        self._chk_student_cb.pack(side="left", padx=(2, 4))
        tk.Button(form, text="↻", width=2,
                  command=self._reload_students).pack(side="left", padx=(0, 8))
        tk.Label(form, text="Mood (1–10):", bg="#d5dbdb").pack(side="left")
        self._chk_mood = tk.StringVar()
        ttk.Combobox(form, textvariable=self._chk_mood,
                     values=[str(i) for i in range(1, 11)],
                     width=4, state="readonly").pack(side="left", padx=(2, 8))
        tk.Label(form, text="Notes:", bg="#d5dbdb").pack(side="left")
        self._chk_notes = tk.StringVar()
        tk.Entry(form, textvariable=self._chk_notes, width=40).pack(side="left", padx=2,
                                                                    fill="x", expand=True)
        tk.Button(form, text="Log check-in", command=self._add_checkin).pack(side="left", padx=4)

        toolbar = tk.Frame(frame, bg="#ecf0f1", padx=6, pady=4)
        toolbar.pack(fill="x")
        tk.Label(toolbar, text="Filter by student:", bg="#ecf0f1").pack(side="left")
        self._chk_filter = tk.StringVar()
        self._chk_filter_cb = ttk.Combobox(toolbar, textvariable=self._chk_filter,
                                           values=["(all)"] + labels, width=32,
                                           state="readonly")
        self._chk_filter_cb.pack(side="left", padx=4)
        self._chk_filter.set("(all)")
        tk.Button(toolbar, text="Apply", command=self._refresh_checkins).pack(side="left")
        tk.Button(toolbar, text="Show all",
                  command=lambda: (self._chk_filter.set("(all)"),
                                   self._refresh_checkins())).pack(side="left", padx=4)

        self._chk_tree = ttk.Treeview(frame, columns=self._CHECKIN_COLS,
                                      show="headings", selectmode="browse")
        for c in self._CHECKIN_COLS:
            self._chk_tree.heading(c, text=c.replace("_", " ").title())
            self._chk_tree.column(c, width=self._CHECKIN_WIDTHS.get(c, 100), anchor="w")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self._chk_tree.yview)
        self._chk_tree.configure(yscrollcommand=vsb.set)
        self._chk_tree.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        vsb.pack(side="left", fill="y", pady=4)

        self._chk_status = tk.StringVar(value="Ready")
        tk.Label(frame, textvariable=self._chk_status, anchor="w",
                 bg="#ecf0f1", padx=8).pack(fill="x", side="bottom")

        self._refresh_checkins()

    def _reload_students(self):
        """Re-pull the students list and update both comboboxes."""
        try:
            self._student_options = self._service.list_student_ids()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self._student_label_to_id = {label: sid for sid, label in self._student_options}
        labels = [label for _sid, label in self._student_options]
        prev_form = self._chk_student.get()
        prev_filter = self._chk_filter.get()
        self._chk_student_cb.configure(values=labels)
        self._chk_filter_cb.configure(values=["(all)"] + labels)
        if prev_form not in labels:
            self._chk_student.set("")
        if prev_filter not in (["(all)"] + labels):
            self._chk_filter.set("(all)")
        self._chk_status.set(f"Loaded {len(labels)} student(s)")

    def _add_checkin(self):
        label = self._chk_student.get().strip()
        sid = self._student_label_to_id.get(label)
        if not sid:
            messagebox.showwarning("Missing", "Select a student from the dropdown.")
            return
        mood_raw = self._chk_mood.get().strip()
        try:
            mood = int(mood_raw) if mood_raw else None
        except ValueError:
            messagebox.showwarning("Invalid", "Mood must be a number 1–10.")
            return
        logged_by = None
        if self._auth:
            try:
                user = self._auth.get_current_user()
                logged_by = (user or {}).get("username")
            except Exception:
                logged_by = None
        try:
            self._service.create_checkin(
                student_id=sid, mood_rating=mood,
                notes=self._chk_notes.get().strip() or None,
                logged_by=logged_by,
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self._chk_student.set("")
        self._chk_mood.set("")
        self._chk_notes.set("")
        self._refresh_checkins()

    def _refresh_checkins(self):
        for r in self._chk_tree.get_children():
            self._chk_tree.delete(r)
        try:
            label = self._chk_filter.get().strip()
            sid = self._student_label_to_id.get(label) if label and label != "(all)" else None
            rows = self._service.list_checkins(student_id=sid)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        for r in rows:
            self._chk_tree.insert("", "end",
                                  values=tuple(r.get(c, "") for c in self._CHECKIN_COLS))
        self._chk_status.set(
            f"{len(rows)} check-in(s)" + (f" for {sid}" if sid else "")
        )

    # ------------------------------------------------------------------ summary
    def _build_summary_tab(self):
        frame = self._summary_tab
        toolbar = tk.Frame(frame, bg="#d5dbdb", padx=6, pady=4)
        toolbar.pack(fill="x")
        tk.Button(toolbar, text="Refresh", command=self._refresh_summary).pack(side="left")

        body = tk.Frame(frame)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        self._sum_text = tk.Text(body, height=22, wrap="word",
                                 font=("Helvetica", 10), bg="#fbfcfc")
        self._sum_text.tag_configure("h", font=("Helvetica", 11, "bold"),
                                     foreground="#1a5276", spacing3=4)
        self._sum_text.tag_configure("k", font=("Helvetica", 10, "bold"))
        vsb = ttk.Scrollbar(body, orient="vertical", command=self._sum_text.yview)
        self._sum_text.configure(yscrollcommand=vsb.set)
        self._sum_text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        self._refresh_summary()

    def _refresh_summary(self):
        try:
            data = self._service.summary()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        t = self._sum_text
        t.config(state="normal")
        t.delete("1.0", "end")

        t.insert("end", "Referrals\n", "h")
        t.insert("end", "  Total: ", "k")
        t.insert("end", f"{data['referrals_total']}\n")
        t.insert("end", "  Auto (absence tracker): ", "k")
        t.insert("end", f"{data['referrals_auto']}\n")
        t.insert("end", "  Manual: ", "k")
        t.insert("end", f"{data['referrals_manual']}\n")

        t.insert("end", "\nBy status\n", "h")
        for k, v in sorted(data["referrals_by_status"].items()):
            t.insert("end", f"  {k}: ", "k")
            t.insert("end", f"{v}\n")
        if not data["referrals_by_status"]:
            t.insert("end", "  (none)\n")

        t.insert("end", "\nBy urgency\n", "h")
        for k, v in sorted(data["referrals_by_urgency"].items()):
            t.insert("end", f"  {k}: ", "k")
            t.insert("end", f"{v}\n")
        if not data["referrals_by_urgency"]:
            t.insert("end", "  (none)\n")

        t.insert("end", "\nCheck-ins\n", "h")
        t.insert("end", "  Total: ", "k")
        t.insert("end", f"{data['checkins_total']}\n")
        t.insert("end", "  Average mood: ", "k")
        t.insert("end", f"{data['avg_mood'] if data['avg_mood'] is not None else '—'}\n")

        t.insert("end", "\nMost recent referrals\n", "h")
        if not data["recent_referrals"]:
            t.insert("end", "  (none)\n")
        for r in data["recent_referrals"]:
            t.insert(
                "end",
                f"  #{r['id']}  {r['created_at']}  "
                f"{r['student_id']}  {r['concern_type']}  "
                f"[{r['urgency']}/{r['status']}]\n",
            )
        t.config(state="disabled")

    # Filter labels → corresponding referred_by SQL filter (None = all rows).
    _SOURCE_FILTERS = {
        "All sources":              None,
        "Auto (absence tracker)":   "absence_tracker",
        "Manual referrals":         "__not_absence_tracker__",
    }

    _COLUMNS = ("id", "student_id", "concern_type", "urgency",
                "status", "referred_by", "created_at")
    _COL_WIDTHS = {"id": 60, "student_id": 110, "concern_type": 130,
                   "urgency": 80, "status": 80, "referred_by": 140,
                   "created_at": 160}

    def _build_list_tab(self):
        """Build the main list tab with toolbar, filter, and treeview."""
        tab = self._notebook.tabs()[0]
        frame = self._notebook.nametowidget(tab)

        toolbar = tk.Frame(frame, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")
        tk.Button(toolbar, text="Refresh",
                  command=self.refresh).pack(side="left", padx=3)
        tk.Button(toolbar, text="Create",
                  command=self._create_referral).pack(side="left", padx=3)
        tk.Button(toolbar, text="View",
                  command=self._view_referral).pack(side="left", padx=3)
        tk.Button(toolbar, text="Update",
                  command=self._update_referral).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete",
                  command=self._delete_referral).pack(side="left", padx=3)
        tk.Label(toolbar, text="Source:",
                 bg="#d5dbdb").pack(side="left", padx=(20, 4))
        self._source_var = tk.StringVar(value="All sources")
        cb = ttk.Combobox(toolbar, textvariable=self._source_var,
                          values=list(self._SOURCE_FILTERS.keys()),
                          state="readonly", width=22)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        self._tree = ttk.Treeview(
            frame, columns=self._COLUMNS, show="headings",
            selectmode="browse")
        for col in self._COLUMNS:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=self._COL_WIDTHS.get(col, 100),
                              minwidth=40, anchor="w")
        self._tree.tag_configure("auto", background="#fff7d6")
        self._tree.tag_configure("high", foreground="#b91c1c")

        vsb = ttk.Scrollbar(frame, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True,
                        padx=5, pady=5)
        vsb.pack(side="right", fill="y", pady=5)

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(frame, textvariable=self._status_var, anchor="w",
                 bg="#ecf0f1", padx=10).pack(fill="x", side="bottom")

        # Initial populate
        self.refresh()

    def refresh(self):
        """Reload referrals into the tree, honouring the source filter."""
        try:
            for item in self._tree.get_children():
                self._tree.delete(item)
            choice = self._source_var.get() if hasattr(self, "_source_var") \
                                            else "All sources"
            sentinel = self._SOURCE_FILTERS.get(choice)
            if sentinel == "__not_absence_tracker__":
                # Pull everything, exclude auto rows in Python — the service
                # doesn't currently support a NOT-EQUAL filter and we'd
                # rather not bypass its identifier validation.
                records = [
                    r for r in self._service.list_all()
                    if (r.get("referred_by") or "") != "absence_tracker"
                ]
            elif sentinel:
                records = self._service.list_all(referred_by=sentinel)
            else:
                records = self._service.list_all()

            for rec in records:
                values = tuple(rec.get(c, "") for c in self._COLUMNS)
                tags = []
                if (rec.get("referred_by") or "") == "absence_tracker":
                    tags.append("auto")
                if (rec.get("urgency") or "").lower() == "high":
                    tags.append("high")
                self._tree.insert("", "end", values=values, tags=tags)

            self._status_var.set(
                f"{len(records)} record(s) — filter: {choice}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ------------------------------------------------------------- referral CRUD
    # Fields the create/update forms expose (mapped to referral columns).
    _REFERRAL_FIELDS = ("student_id", "referred_by", "concern_type",
                        "description", "urgency", "status")

    def _selected_referral_id(self):
        """Return the id of the selected referral row, or None."""
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Select a referral first.")
            return None
        return self._tree.item(sel[0], "values")[0]

    def _referral_form(self, title, record=None):
        """Modal form for a referral. Returns dict of field->value or None."""
        record = record or {}
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        entries = {}
        for i, field in enumerate(self._REFERRAL_FIELDS):
            tk.Label(dialog, text=field.replace("_", " ").title() + ":",
                     anchor="w").grid(row=i, column=0, sticky="w", padx=8, pady=4)
            var = tk.StringVar(value=str(record.get(field, "") or ""))
            tk.Entry(dialog, textvariable=var, width=44).grid(
                row=i, column=1, padx=8, pady=4)
            entries[field] = var

        result = {}

        def _save():
            for field, var in entries.items():
                val = var.get().strip()
                if val:
                    result[field] = val
            dialog.destroy()

        btns = tk.Frame(dialog)
        btns.grid(row=len(self._REFERRAL_FIELDS), column=0, columnspan=2, pady=8)
        tk.Button(btns, text="Save", command=_save).pack(side="left", padx=6)
        tk.Button(btns, text="Cancel",
                  command=dialog.destroy).pack(side="left", padx=6)

        dialog.wait_window()
        return result or None

    def _create_referral(self):
        """Prompt for a new referral and create it via the service."""
        data = self._referral_form("Create Referral")
        if not data:
            return
        try:
            new_id = self._service.create(**data)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self.refresh()
        messagebox.showinfo("Created", f"Referral #{new_id} created.")

    def _view_referral(self):
        """Show the full record for the selected referral."""
        rid = self._selected_referral_id()
        if rid is None:
            return
        record = self._service.get(rid)
        if not record:
            messagebox.showinfo("Not found", "Referral not found.")
            return
        detail = "\n".join(f"{k}: {v}" for k, v in record.items())
        messagebox.showinfo(f"Referral #{rid}", detail)

    def _update_referral(self):
        """Edit the selected referral via the service."""
        rid = self._selected_referral_id()
        if rid is None:
            return
        record = self._service.get(rid)
        if not record:
            messagebox.showinfo("Not found", "Referral not found.")
            return
        data = self._referral_form(f"Update Referral #{rid}", record)
        if not data:
            return
        try:
            self._service.update(rid, **data)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self.refresh()
        messagebox.showinfo("Updated", f"Referral #{rid} updated.")

    def _delete_referral(self):
        """Delete the selected referral after confirmation."""
        rid = self._selected_referral_id()
        if rid is None:
            return
        if not messagebox.askyesno("Confirm delete",
                                   f"Delete referral #{rid}?"):
            return
        try:
            self._service.delete(rid)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self.refresh()
        messagebox.showinfo("Deleted", f"Referral #{rid} deleted.")
