"""Alumni Network GUI frame for managing alumni records, events, and surveys."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.alumni.services.alumni_service import AlumniService


class AlumniFrame(tk.Frame):
    """Alumni Network management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = AlumniService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Alumni Network",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._rec_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._rec_tab, text="Alumni Records")
        self._build_records_tab()

        self._evt_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._evt_tab, text="Events")
        self._build_events_tab()

        self._srv_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._srv_tab, text="Surveys")
        self._build_surveys_tab()

        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._stats_tab, text="Statistics")
        self._build_stats_tab()

    # ---- Records Tab ----

    def _build_records_tab(self):
        toolbar = tk.Frame(self._rec_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text="Search:", bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._rec_search = tk.Entry(toolbar, width=20)
        self._rec_search.pack(side="left", padx=2)
        self._rec_search.bind("<Return>", lambda e: self._load_records())

        tk.Label(toolbar, text="Year:", bg="#ecf0f1").pack(side="left", padx=(10, 2))
        self._rec_year = tk.Entry(toolbar, width=8)
        self._rec_year.pack(side="left", padx=2)

        ttk.Button(toolbar, text="Search", command=self._load_records).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Refresh", command=self._load_records).pack(side="left", padx=2)
        ttk.Button(toolbar, text="New Alumni", command=self._new_record).pack(side="right", padx=5)
        ttk.Button(toolbar, text="Delete", command=self._delete_record).pack(side="right", padx=2)
        ttk.Button(toolbar, text="Edit", command=self._edit_record).pack(side="right", padx=2)
        ttk.Button(toolbar, text="View", command=self._view_record).pack(side="right", padx=2)

        cols = ("id", "name", "email", "grad_year", "employer", "role", "university", "mentor", "speaker")
        self._rec_tree = ttk.Treeview(self._rec_tab, columns=cols, show="headings", height=18)
        for c, w, label in [
            ("id", 40, "ID"), ("name", 150, "Name"), ("email", 160, "Email"),
            ("grad_year", 70, "Grad Year"), ("employer", 130, "Employer"),
            ("role", 110, "Role"), ("university", 130, "University"),
            ("mentor", 55, "Mentor"), ("speaker", 55, "Speaker"),
        ]:
            self._rec_tree.heading(c, text=label)
            self._rec_tree.column(c, width=w, anchor="center" if w < 70 else "w")
        self._rec_tree.bind("<Double-1>", lambda e: self._view_record())

        vsb = ttk.Scrollbar(self._rec_tab, orient="vertical", command=self._rec_tree.yview)
        self._rec_tree.configure(yscrollcommand=vsb.set)
        self._rec_tree.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def _load_records(self):
        for item in self._rec_tree.get_children():
            self._rec_tree.delete(item)
        try:
            search = self._rec_search.get().strip() or None
            year = self._rec_year.get().strip() or None
            records = self._svc.list_records(search=search, graduation_year=year)
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
                self._rec_tree.insert("", "end", iid=r["id"], values=(
                    r["id"], name, r.get("email", ""),
                    r.get("graduation_year", ""), r.get("current_employer", ""),
                    r.get("current_role", ""), r.get("university_attended", ""),
                    "Yes" if r.get("willing_to_mentor") else "No",
                    "Yes" if r.get("willing_to_speak") else "No"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_record_id(self):
        sel = self._rec_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an alumni record first.")
            return None
        return int(sel[0])

    def _new_record(self):
        win = tk.Toplevel(self)
        win.title("New Alumni Record")
        win.geometry("480x520")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            ("First Name*:", "first_name"), ("Last Name*:", "last_name"),
            ("Email:", "email"), ("Phone:", "phone"),
            ("Graduation Year:", "graduation_year"),
            ("Courses Studied:", "courses_studied"),
            ("Current Employer:", "current_employer"),
            ("Current Role:", "current_role"),
            ("Further Education:", "further_education"),
            ("University Attended:", "university_attended"),
            ("Degree Achieved:", "degree_achieved"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=4, sticky="e")
            e = tk.Entry(win, width=30)
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        mentor_var = tk.BooleanVar()
        ttk.Checkbutton(win, text="Willing to Mentor", variable=mentor_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        speaker_var = tk.BooleanVar()
        ttk.Checkbutton(win, text="Willing to Speak", variable=speaker_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        tk.Label(win, text="Notes:").grid(row=row, column=0, padx=10, pady=4, sticky="ne")
        notes_txt = tk.Text(win, width=30, height=3)
        notes_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            fn = fields["first_name"].get().strip()
            ln = fields["last_name"].get().strip()
            if not fn or not ln:
                messagebox.showwarning("Validation", "First and last name are required.")
                return
            try:
                self._svc.create_record(
                    fn, ln,
                    email=fields["email"].get().strip() or None,
                    phone=fields["phone"].get().strip() or None,
                    graduation_year=fields["graduation_year"].get().strip() or None,
                    courses_studied=fields["courses_studied"].get().strip() or None,
                    current_employer=fields["current_employer"].get().strip() or None,
                    current_role=fields["current_role"].get().strip() or None,
                    further_education=fields["further_education"].get().strip() or None,
                    university_attended=fields["university_attended"].get().strip() or None,
                    degree_achieved=fields["degree_achieved"].get().strip() or None,
                    willing_to_mentor=1 if mentor_var.get() else 0,
                    willing_to_speak=1 if speaker_var.get() else 0,
                    notes=notes_txt.get("1.0", "end-1c").strip() or None)
                messagebox.showinfo("Success", "Alumni record created.")
                win.destroy()
                self._load_records()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _view_record(self):
        rid = self._selected_record_id()
        if not rid:
            return
        rec = self._svc.get_record(rid)
        if not rec:
            messagebox.showwarning("Not Found", "Record not found.")
            return

        win = tk.Toplevel(self)
        win.title(f"Alumni: {rec.get('first_name', '')} {rec.get('last_name', '')}")
        win.geometry("450x480")
        win.resizable(False, False)

        display = [
            ("ID", rec.get("id")),
            ("Name", f"{rec.get('first_name', '')} {rec.get('last_name', '')}"),
            ("Email", rec.get("email", "")),
            ("Phone", rec.get("phone", "")),
            ("Graduation Year", rec.get("graduation_year", "")),
            ("Courses Studied", rec.get("courses_studied", "")),
            ("Current Employer", rec.get("current_employer", "")),
            ("Current Role", rec.get("current_role", "")),
            ("Further Education", rec.get("further_education", "")),
            ("University", rec.get("university_attended", "")),
            ("Degree", rec.get("degree_achieved", "")),
            ("Willing to Mentor", "Yes" if rec.get("willing_to_mentor") else "No"),
            ("Willing to Speak", "Yes" if rec.get("willing_to_speak") else "No"),
            ("Consent to Contact", "Yes" if rec.get("consent_to_contact") else "No"),
            ("Last Contacted", rec.get("last_contacted", "")),
            ("Notes", rec.get("notes", "")),
            ("Created", rec.get("created_at", "")),
        ]

        frame = tk.Frame(win, padx=15, pady=10)
        frame.pack(fill="both", expand=True)
        for i, (lbl, val) in enumerate(display):
            tk.Label(frame, text=f"{lbl}:", font=("Helvetica", 10, "bold"),
                     anchor="e").grid(row=i, column=0, sticky="ne", padx=(0, 8), pady=2)
            tk.Label(frame, text=str(val or ""), anchor="w",
                     wraplength=280).grid(row=i, column=1, sticky="w", pady=2)

    def _edit_record(self):
        rid = self._selected_record_id()
        if not rid:
            return
        rec = self._svc.get_record(rid)
        if not rec:
            messagebox.showwarning("Not Found", "Record not found.")
            return

        win = tk.Toplevel(self)
        win.title(f"Edit Alumni #{rid}")
        win.geometry("480x520")
        win.resizable(False, False)

        fields = {}
        row = 0
        field_defs = [
            ("First Name*:", "first_name"), ("Last Name*:", "last_name"),
            ("Email:", "email"), ("Phone:", "phone"),
            ("Graduation Year:", "graduation_year"),
            ("Courses Studied:", "courses_studied"),
            ("Current Employer:", "current_employer"),
            ("Current Role:", "current_role"),
            ("Further Education:", "further_education"),
            ("University Attended:", "university_attended"),
            ("Degree Achieved:", "degree_achieved"),
        ]
        for label, key in field_defs:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=4, sticky="e")
            e = tk.Entry(win, width=30)
            e.insert(0, rec.get(key, "") or "")
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        mentor_var = tk.BooleanVar(value=bool(rec.get("willing_to_mentor")))
        ttk.Checkbutton(win, text="Willing to Mentor", variable=mentor_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        speaker_var = tk.BooleanVar(value=bool(rec.get("willing_to_speak")))
        ttk.Checkbutton(win, text="Willing to Speak", variable=speaker_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        tk.Label(win, text="Notes:").grid(row=row, column=0, padx=10, pady=4, sticky="ne")
        notes_txt = tk.Text(win, width=30, height=3)
        notes_txt.insert("1.0", rec.get("notes", "") or "")
        notes_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            fn = fields["first_name"].get().strip()
            ln = fields["last_name"].get().strip()
            if not fn or not ln:
                messagebox.showwarning("Validation", "First and last name are required.")
                return
            try:
                self._svc.update_record(
                    rid,
                    first_name=fn, last_name=ln,
                    email=fields["email"].get().strip() or None,
                    phone=fields["phone"].get().strip() or None,
                    graduation_year=fields["graduation_year"].get().strip() or None,
                    courses_studied=fields["courses_studied"].get().strip() or None,
                    current_employer=fields["current_employer"].get().strip() or None,
                    current_role=fields["current_role"].get().strip() or None,
                    further_education=fields["further_education"].get().strip() or None,
                    university_attended=fields["university_attended"].get().strip() or None,
                    degree_achieved=fields["degree_achieved"].get().strip() or None,
                    willing_to_mentor=1 if mentor_var.get() else 0,
                    willing_to_speak=1 if speaker_var.get() else 0,
                    notes=notes_txt.get("1.0", "end-1c").strip() or None)
                messagebox.showinfo("Success", "Alumni record updated.")
                win.destroy()
                self._load_records()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_record(self):
        rid = self._selected_record_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete alumni record #{rid}? This will also remove associated surveys."):
            return
        try:
            self._svc.delete_record(rid)
            messagebox.showinfo("Deleted", "Alumni record deleted.")
            self._load_records()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Events Tab ----

    def _build_events_tab(self):
        toolbar = tk.Frame(self._evt_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text="Type:", bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._evt_type = ttk.Combobox(toolbar, width=12, state="readonly",
                                       values=["", "reunion", "networking", "careers_talk",
                                                "fundraiser", "open_day", "other"])
        self._evt_type.pack(side="left", padx=2)
        self._evt_type.set("")

        ttk.Button(toolbar, text="Refresh", command=self._load_events).pack(side="left", padx=5)
        ttk.Button(toolbar, text="New Event", command=self._new_event).pack(side="right", padx=5)
        ttk.Button(toolbar, text="Delete", command=self._delete_event).pack(side="right", padx=2)
        ttk.Button(toolbar, text="Edit", command=self._edit_event).pack(side="right", padx=2)

        cols = ("id", "name", "date", "type", "location", "attendees", "status")
        self._evt_tree = ttk.Treeview(self._evt_tab, columns=cols, show="headings", height=18)
        for c, w, label in [
            ("id", 40, "ID"), ("name", 200, "Event Name"), ("date", 100, "Date"),
            ("type", 100, "Type"), ("location", 150, "Location"),
            ("attendees", 70, "Attendees"), ("status", 80, "Status"),
        ]:
            self._evt_tree.heading(c, text=label)
            self._evt_tree.column(c, width=w, anchor="center" if w < 100 else "w")

        vsb = ttk.Scrollbar(self._evt_tab, orient="vertical", command=self._evt_tree.yview)
        self._evt_tree.configure(yscrollcommand=vsb.set)
        self._evt_tree.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def _load_events(self):
        for item in self._evt_tree.get_children():
            self._evt_tree.delete(item)
        try:
            et = self._evt_type.get().strip() or None
            events = self._svc.list_events(event_type=et)
            for ev in events:
                self._evt_tree.insert("", "end", iid=ev["id"], values=(
                    ev["id"], ev.get("event_name", ""), ev.get("event_date", ""),
                    ev.get("event_type", ""), ev.get("location", ""),
                    ev.get("attendee_count", 0), ev.get("status", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_event_id(self):
        sel = self._evt_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an event first.")
            return None
        return int(sel[0])

    def _new_event(self):
        win = tk.Toplevel(self)
        win.title("New Alumni Event")
        win.geometry("420x320")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            ("Event Name*:", "event_name"), ("Date* (YYYY-MM-DD):", "event_date"),
            ("Location:", "location"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=28)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        tk.Label(win, text="Type:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        type_cb = ttk.Combobox(win, width=25, state="readonly",
                                values=["reunion", "networking", "careers_talk",
                                        "fundraiser", "open_day", "other"])
        type_cb.set("reunion")
        type_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Description:").grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        desc_txt = tk.Text(win, width=28, height=3)
        desc_txt.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            name = fields["event_name"].get().strip()
            date = fields["event_date"].get().strip()
            if not name or not date:
                messagebox.showwarning("Validation", "Event name and date are required.")
                return
            try:
                self._svc.create_event(
                    name, date,
                    event_type=type_cb.get(),
                    description=desc_txt.get("1.0", "end-1c").strip() or None,
                    location=fields["location"].get().strip() or None)
                messagebox.showinfo("Success", "Event created.")
                win.destroy()
                self._load_events()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _edit_event(self):
        eid = self._selected_event_id()
        if not eid:
            return
        ev = self._svc.get_event(eid)
        if not ev:
            messagebox.showwarning("Not Found", "Event not found.")
            return

        win = tk.Toplevel(self)
        win.title(f"Edit Event #{eid}")
        win.geometry("420x380")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            ("Event Name*:", "event_name"), ("Date* (YYYY-MM-DD):", "event_date"),
            ("Location:", "location"), ("Attendee Count:", "attendee_count"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=28)
            e.insert(0, str(ev.get(key, "") or ""))
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        tk.Label(win, text="Type:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        type_cb = ttk.Combobox(win, width=25, state="readonly",
                                values=["reunion", "networking", "careers_talk",
                                        "fundraiser", "open_day", "other"])
        type_cb.set(ev.get("event_type", "reunion"))
        type_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Status:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        status_cb = ttk.Combobox(win, width=25, state="readonly",
                                  values=["planned", "confirmed", "completed", "cancelled"])
        status_cb.set(ev.get("status", "planned"))
        status_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Description:").grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        desc_txt = tk.Text(win, width=28, height=3)
        desc_txt.insert("1.0", ev.get("description", "") or "")
        desc_txt.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            name = fields["event_name"].get().strip()
            date = fields["event_date"].get().strip()
            if not name or not date:
                messagebox.showwarning("Validation", "Event name and date are required.")
                return
            try:
                ac = fields["attendee_count"].get().strip()
                self._svc.update_event(
                    eid,
                    event_name=name, event_date=date,
                    event_type=type_cb.get(),
                    status=status_cb.get(),
                    description=desc_txt.get("1.0", "end-1c").strip() or None,
                    location=fields["location"].get().strip() or None,
                    attendee_count=int(ac) if ac else 0)
                messagebox.showinfo("Success", "Event updated.")
                win.destroy()
                self._load_events()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_event(self):
        eid = self._selected_event_id()
        if not eid:
            return
        if not messagebox.askyesno("Confirm", f"Delete event #{eid}?"):
            return
        try:
            self._svc.delete_event(eid)
            messagebox.showinfo("Deleted", "Event deleted.")
            self._load_events()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Surveys Tab ----

    def _build_surveys_tab(self):
        toolbar = tk.Frame(self._srv_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text="Alumni ID:", bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._srv_alumni = tk.Entry(toolbar, width=8)
        self._srv_alumni.pack(side="left", padx=2)

        tk.Label(toolbar, text="Year:", bg="#ecf0f1").pack(side="left", padx=(10, 2))
        self._srv_year = tk.Entry(toolbar, width=8)
        self._srv_year.pack(side="left", padx=2)

        ttk.Button(toolbar, text="Refresh", command=self._load_surveys).pack(side="left", padx=5)
        ttk.Button(toolbar, text="New Survey", command=self._new_survey).pack(side="right", padx=5)
        ttk.Button(toolbar, text="Delete", command=self._delete_survey).pack(side="right", padx=2)

        cols = ("id", "alumni", "year", "employment", "satisfaction", "recommend", "feedback")
        self._srv_tree = ttk.Treeview(self._srv_tab, columns=cols, show="headings", height=18)
        for c, w, label in [
            ("id", 40, "ID"), ("alumni", 150, "Alumni"),
            ("year", 60, "Year"), ("employment", 110, "Employment"),
            ("satisfaction", 80, "Rating"), ("recommend", 80, "Recommend"),
            ("feedback", 250, "Feedback"),
        ]:
            self._srv_tree.heading(c, text=label)
            self._srv_tree.column(c, width=w, anchor="center" if w < 100 else "w")

        vsb = ttk.Scrollbar(self._srv_tab, orient="vertical", command=self._srv_tree.yview)
        self._srv_tree.configure(yscrollcommand=vsb.set)
        self._srv_tree.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def _load_surveys(self):
        for item in self._srv_tree.get_children():
            self._srv_tree.delete(item)
        try:
            aid = self._srv_alumni.get().strip()
            year = self._srv_year.get().strip() or None
            surveys = self._svc.list_surveys(
                alumni_id=int(aid) if aid else None, survey_year=year)
            for s in surveys:
                name = f"{s.get('first_name', '')} {s.get('last_name', '')}".strip() or str(s.get("alumni_id", ""))
                self._srv_tree.insert("", "end", iid=s["id"], values=(
                    s["id"], name, s.get("survey_year", ""),
                    s.get("employment_status", ""),
                    s.get("satisfaction_rating", ""),
                    "Yes" if s.get("would_recommend") else "No",
                    (s.get("feedback", "") or "")[:80]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _new_survey(self):
        win = tk.Toplevel(self)
        win.title("New Alumni Survey")
        win.geometry("420x350")
        win.resizable(False, False)

        row = 0
        tk.Label(win, text="Alumni ID*:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        alumni_entry = tk.Entry(win, width=10)
        alumni_entry.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        row += 1

        tk.Label(win, text="Survey Year:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        year_entry = tk.Entry(win, width=10)
        year_entry.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        row += 1

        tk.Label(win, text="Employment Status:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        emp_cb = ttk.Combobox(win, width=25, state="readonly",
                               values=["employed", "self_employed", "further_education",
                                       "unemployed", "gap_year", "other"])
        emp_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Satisfaction (1-5):").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        sat_sb = ttk.Spinbox(win, from_=1, to=5, width=5)
        sat_sb.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        row += 1

        rec_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(win, text="Would Recommend", variable=rec_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        tk.Label(win, text="Feedback:").grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        fb_txt = tk.Text(win, width=28, height=4)
        fb_txt.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            aid = alumni_entry.get().strip()
            if not aid:
                messagebox.showwarning("Validation", "Alumni ID is required.")
                return
            try:
                sat = sat_sb.get().strip()
                self._svc.create_survey(
                    int(aid),
                    survey_year=year_entry.get().strip() or None,
                    employment_status=emp_cb.get() or None,
                    satisfaction_rating=int(sat) if sat else None,
                    would_recommend=1 if rec_var.get() else 0,
                    feedback=fb_txt.get("1.0", "end-1c").strip() or None)
                messagebox.showinfo("Success", "Survey recorded.")
                win.destroy()
                self._load_surveys()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_survey(self):
        sel = self._srv_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a survey first.")
            return
        sid = int(sel[0])
        if not messagebox.askyesno("Confirm", f"Delete survey #{sid}?"):
            return
        try:
            self._svc.delete_survey(sid)
            messagebox.showinfo("Deleted", "Survey deleted.")
            self._load_surveys()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Statistics Tab ----

    def _build_stats_tab(self):
        self._stats_frame = tk.Frame(self._stats_tab, bg="#ecf0f1", padx=20, pady=20)
        self._stats_frame.pack(fill="both", expand=True)

        ttk.Button(self._stats_frame, text="Refresh Statistics",
                   command=self._load_stats).pack(anchor="w", pady=(0, 15))

        self._stats_labels = {}
        for key, label in [
            ("total_alumni", "Total Alumni Records"),
            ("willing_to_mentor", "Willing to Mentor"),
            ("willing_to_speak", "Willing to Speak"),
            ("at_university", "Went to University"),
            ("employed", "Currently Employed"),
            ("total_events", "Total Events"),
            ("total_surveys", "Total Surveys"),
            ("avg_satisfaction", "Avg Satisfaction Rating"),
        ]:
            row_frame = tk.Frame(self._stats_frame, bg="#ecf0f1")
            row_frame.pack(fill="x", pady=3)
            tk.Label(row_frame, text=f"{label}:", font=("Helvetica", 11, "bold"),
                     bg="#ecf0f1", width=25, anchor="e").pack(side="left")
            lbl = tk.Label(row_frame, text="—", font=("Helvetica", 11),
                           bg="#ecf0f1", anchor="w")
            lbl.pack(side="left", padx=(10, 0))
            self._stats_labels[key] = lbl

    def _load_stats(self):
        try:
            stats = self._svc.get_stats()
            for key, lbl in self._stats_labels.items():
                val = stats.get(key)
                lbl.config(text=str(val) if val is not None else "—")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Refresh ----

    def refresh(self):
        self._load_records()
        self._load_events()
        self._load_surveys()
        self._load_stats()
