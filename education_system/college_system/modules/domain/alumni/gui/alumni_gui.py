"""Alumni Network GUI frame for managing alumni records, events, and surveys."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
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
        tk.Label(header, text=t("alumni.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._rec_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._rec_tab, text=t("alumni.management"))
        self._build_records_tab()

        self._evt_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._evt_tab, text=t("common.date"))
        self._build_events_tab()

        self._srv_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._srv_tab, text=t("common.report"))
        self._build_surveys_tab()

        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._stats_tab, text=t("common.summary"))
        self._build_stats_tab()

    # ---- Records Tab ----

    def _build_records_tab(self):
        toolbar = tk.Frame(self._rec_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("common.search_colon"), bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._rec_search = tk.Entry(toolbar, width=20)
        self._rec_search.pack(side="left", padx=2)
        self._rec_search.bind("<Return>", lambda e: self._load_records())

        tk.Label(toolbar, text=t("alumni.graduation_year") + ":", bg="#ecf0f1").pack(side="left", padx=(10, 2))
        self._rec_year = tk.Entry(toolbar, width=8)
        self._rec_year.pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("common.search"), command=self._load_records).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_records).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("alumni.add"), command=self._new_record).pack(side="right", padx=5)
        ttk.Button(toolbar, text=t("common.delete"), command=self._delete_record).pack(side="right", padx=2)
        ttk.Button(toolbar, text=t("common.edit"), command=self._edit_record).pack(side="right", padx=2)
        ttk.Button(toolbar, text=t("common.view"), command=self._view_record).pack(side="right", padx=2)
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side="right", padx=2)

        cols = ("id", "name", "email", "grad_year", "employer", "role", "university", "mentor", "speaker")
        self._rec_tree = ttk.Treeview(self._rec_tab, columns=cols, show="headings", height=18)
        for c, w, label in [
            ("id", 40, t("common.id")), ("name", 150, t("alumni.name")), ("email", 160, t("common.email")),
            ("grad_year", 70, t("alumni.graduation_year")), ("employer", 130, t("common.name")),
            ("role", 110, t("alumni.current_role")), ("university", 130, t("common.name")),
            ("mentor", 55, t("common.yes")), ("speaker", 55, t("common.yes")),
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
            messagebox.showerror(t("common.error"), str(e))

    def _selected_record_id(self):
        sel = self._rec_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return int(sel[0])

    def _new_record(self):
        win = tk.Toplevel(self)
        win.title(t("alumni.add"))
        win.geometry("480x520")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            (t("common.name") + "*:", "first_name"), (t("common.name") + "*:", "last_name"),
            (t("common.email") + ":", "email"), (t("common.phone") + ":", "phone"),
            (t("alumni.graduation_year") + ":", "graduation_year"),
            (t("common.course_title") + ":", "courses_studied"),
            (t("common.name") + ":", "current_employer"),
            (t("alumni.current_role") + ":", "current_role"),
            (t("common.description") + ":", "further_education"),
            (t("common.name") + ":", "university_attended"),
            (t("common.description") + ":", "degree_achieved"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=4, sticky="e")
            e = tk.Entry(win, width=30)
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        mentor_var = tk.BooleanVar()
        ttk.Checkbutton(win, text=t("common.yes"), variable=mentor_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        speaker_var = tk.BooleanVar()
        ttk.Checkbutton(win, text=t("common.yes"), variable=speaker_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        tk.Label(win, text=t("common.notes") + ":").grid(row=row, column=0, padx=10, pady=4, sticky="ne")
        notes_txt = tk.Text(win, width=30, height=3)
        notes_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            fn = fields["first_name"].get().strip()
            ln = fields["last_name"].get().strip()
            if not fn or not ln:
                messagebox.showwarning(t("common.validation"), t("common.both_required"))
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
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_records()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _view_record(self):
        rid = self._selected_record_id()
        if not rid:
            return
        rec = self._svc.get_record(rid)
        if not rec:
            messagebox.showwarning(t("common.warning"), t("common.no_data"))
            return

        win = tk.Toplevel(self)
        win.title(f"{t('alumni.management')}: {rec.get('first_name', '')} {rec.get('last_name', '')}")
        win.geometry("450x480")
        win.resizable(False, False)

        display = [
            (t("common.id"), rec.get("id")),
            (t("alumni.name"), f"{rec.get('first_name', '')} {rec.get('last_name', '')}"),
            (t("common.email"), rec.get("email", "")),
            (t("common.phone"), rec.get("phone", "")),
            (t("alumni.graduation_year"), rec.get("graduation_year", "")),
            (t("common.course_title"), rec.get("courses_studied", "")),
            (t("common.name"), rec.get("current_employer", "")),
            (t("alumni.current_role"), rec.get("current_role", "")),
            (t("common.description"), rec.get("further_education", "")),
            (t("common.name"), rec.get("university_attended", "")),
            (t("common.description"), rec.get("degree_achieved", "")),
            (t("common.yes"), t("common.yes") if rec.get("willing_to_mentor") else t("common.no")),
            (t("common.yes"), t("common.yes") if rec.get("willing_to_speak") else t("common.no")),
            (t("common.yes"), t("common.yes") if rec.get("consent_to_contact") else t("common.no")),
            (t("common.date"), rec.get("last_contacted", "")),
            (t("common.notes"), rec.get("notes", "")),
            (t("common.created_at"), rec.get("created_at", "")),
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
            messagebox.showwarning(t("common.warning"), t("common.no_data"))
            return

        win = tk.Toplevel(self)
        win.title(f"{t('common.edit')} #{rid}")
        win.geometry("480x520")
        win.resizable(False, False)

        fields = {}
        row = 0
        field_defs = [
            (t("common.name") + "*:", "first_name"), (t("common.name") + "*:", "last_name"),
            (t("common.email") + ":", "email"), (t("common.phone") + ":", "phone"),
            (t("alumni.graduation_year") + ":", "graduation_year"),
            (t("common.course_title") + ":", "courses_studied"),
            (t("common.name") + ":", "current_employer"),
            (t("alumni.current_role") + ":", "current_role"),
            (t("common.description") + ":", "further_education"),
            (t("common.name") + ":", "university_attended"),
            (t("common.description") + ":", "degree_achieved"),
        ]
        for label, key in field_defs:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=4, sticky="e")
            e = tk.Entry(win, width=30)
            e.insert(0, rec.get(key, "") or "")
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        mentor_var = tk.BooleanVar(value=bool(rec.get("willing_to_mentor")))
        ttk.Checkbutton(win, text=t("common.yes"), variable=mentor_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        speaker_var = tk.BooleanVar(value=bool(rec.get("willing_to_speak")))
        ttk.Checkbutton(win, text=t("common.yes"), variable=speaker_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        tk.Label(win, text=t("common.notes") + ":").grid(row=row, column=0, padx=10, pady=4, sticky="ne")
        notes_txt = tk.Text(win, width=30, height=3)
        notes_txt.insert("1.0", rec.get("notes", "") or "")
        notes_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            fn = fields["first_name"].get().strip()
            ln = fields["last_name"].get().strip()
            if not fn or not ln:
                messagebox.showwarning(t("common.validation"), t("common.both_required"))
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
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
                win.destroy()
                self._load_records()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_record(self):
        rid = self._selected_record_id()
        if not rid:
            return
        if not messagebox.askyesno(t("common.confirm_delete"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_record(rid)
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_records()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ---- Events Tab ----

    def _build_events_tab(self):
        toolbar = tk.Frame(self._evt_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("common.type") + ":", bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._evt_type = ttk.Combobox(toolbar, width=12, state="readonly",
                                       values=["", "reunion", "networking", "careers_talk",
                                                "fundraiser", "open_day", "other"])
        self._evt_type.pack(side="left", padx=2)
        self._evt_type.set("")

        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_events).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.add"), command=self._new_event).pack(side="right", padx=5)
        ttk.Button(toolbar, text=t("common.delete"), command=self._delete_event).pack(side="right", padx=2)
        ttk.Button(toolbar, text=t("common.edit"), command=self._edit_event).pack(side="right", padx=2)

        cols = ("id", "name", "date", "type", "location", "attendees", "status")
        self._evt_tree = ttk.Treeview(self._evt_tab, columns=cols, show="headings", height=18)
        for c, w, label in [
            ("id", 40, t("common.id")), ("name", 200, t("common.name")), ("date", 100, t("common.date")),
            ("type", 100, t("common.type")), ("location", 150, t("common.address")),
            ("attendees", 70, t("common.total")), ("status", 80, t("common.status")),
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
            messagebox.showerror(t("common.error"), str(e))

    def _selected_event_id(self):
        sel = self._evt_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return int(sel[0])

    def _new_event(self):
        win = tk.Toplevel(self)
        win.title(t("common.add"))
        win.geometry("420x320")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            (t("common.name") + "*:", "event_name"), (t("common.date") + "*:", "event_date"),
            (t("common.address") + ":", "location"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=28)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        tk.Label(win, text=t("common.type") + ":").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        type_cb = ttk.Combobox(win, width=25, state="readonly",
                                values=["reunion", "networking", "careers_talk",
                                        "fundraiser", "open_day", "other"])
        type_cb.set("reunion")
        type_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text=t("common.description") + ":").grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        desc_txt = tk.Text(win, width=28, height=3)
        desc_txt.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            name = fields["event_name"].get().strip()
            date = fields["event_date"].get().strip()
            if not name or not date:
                messagebox.showwarning(t("common.validation"), t("common.both_required"))
                return
            try:
                self._svc.create_event(
                    name, date,
                    event_type=type_cb.get(),
                    description=desc_txt.get("1.0", "end-1c").strip() or None,
                    location=fields["location"].get().strip() or None)
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_events()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _edit_event(self):
        eid = self._selected_event_id()
        if not eid:
            return
        ev = self._svc.get_event(eid)
        if not ev:
            messagebox.showwarning(t("common.warning"), t("common.no_data"))
            return

        win = tk.Toplevel(self)
        win.title(f"{t('common.edit')} #{eid}")
        win.geometry("420x380")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            (t("common.name") + "*:", "event_name"), (t("common.date") + "*:", "event_date"),
            (t("common.address") + ":", "location"), (t("common.total") + ":", "attendee_count"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=28)
            e.insert(0, str(ev.get(key, "") or ""))
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        tk.Label(win, text=t("common.type") + ":").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        type_cb = ttk.Combobox(win, width=25, state="readonly",
                                values=["reunion", "networking", "careers_talk",
                                        "fundraiser", "open_day", "other"])
        type_cb.set(ev.get("event_type", "reunion"))
        type_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text=t("common.status") + ":").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        status_cb = ttk.Combobox(win, width=25, state="readonly",
                                  values=["planned", "confirmed", "completed", "cancelled"])
        status_cb.set(ev.get("status", "planned"))
        status_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text=t("common.description") + ":").grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        desc_txt = tk.Text(win, width=28, height=3)
        desc_txt.insert("1.0", ev.get("description", "") or "")
        desc_txt.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            name = fields["event_name"].get().strip()
            date = fields["event_date"].get().strip()
            if not name or not date:
                messagebox.showwarning(t("common.validation"), t("common.both_required"))
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
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
                win.destroy()
                self._load_events()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_event(self):
        eid = self._selected_event_id()
        if not eid:
            return
        if not messagebox.askyesno(t("common.confirm_delete"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_event(eid)
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_events()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ---- Surveys Tab ----

    def _build_surveys_tab(self):
        toolbar = tk.Frame(self._srv_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("common.id") + ":", bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._srv_alumni = tk.Entry(toolbar, width=8)
        self._srv_alumni.pack(side="left", padx=2)

        tk.Label(toolbar, text=t("alumni.graduation_year") + ":", bg="#ecf0f1").pack(side="left", padx=(10, 2))
        self._srv_year = tk.Entry(toolbar, width=8)
        self._srv_year.pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_surveys).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.add"), command=self._new_survey).pack(side="right", padx=5)
        ttk.Button(toolbar, text=t("common.delete"), command=self._delete_survey).pack(side="right", padx=2)

        cols = ("id", "alumni", "year", "employment", "satisfaction", "recommend", "feedback")
        self._srv_tree = ttk.Treeview(self._srv_tab, columns=cols, show="headings", height=18)
        for c, w, label in [
            ("id", 40, t("common.id")), ("alumni", 150, t("alumni.management")),
            ("year", 60, t("alumni.graduation_year")), ("employment", 110, t("common.status")),
            ("satisfaction", 80, t("common.score")), ("recommend", 80, t("common.yes")),
            ("feedback", 250, t("common.comments")),
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
                    t("common.yes") if s.get("would_recommend") else t("common.no"),
                    (s.get("feedback", "") or "")[:80]))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _new_survey(self):
        win = tk.Toplevel(self)
        win.title(t("common.add"))
        win.geometry("420x350")
        win.resizable(False, False)

        row = 0
        tk.Label(win, text=t("common.id") + "*:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        alumni_entry = tk.Entry(win, width=10)
        alumni_entry.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        row += 1

        tk.Label(win, text=t("alumni.graduation_year") + ":").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        year_entry = tk.Entry(win, width=10)
        year_entry.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        row += 1

        tk.Label(win, text=t("common.status") + ":").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        emp_cb = ttk.Combobox(win, width=25, state="readonly",
                               values=["employed", "self_employed", "further_education",
                                       "unemployed", "gap_year", "other"])
        emp_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text=t("common.score") + ":").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        sat_sb = ttk.Spinbox(win, from_=1, to=5, width=5)
        sat_sb.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        row += 1

        rec_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(win, text=t("common.yes"), variable=rec_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        tk.Label(win, text=t("common.comments") + ":").grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        fb_txt = tk.Text(win, width=28, height=4)
        fb_txt.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            aid = alumni_entry.get().strip()
            if not aid:
                messagebox.showwarning(t("common.validation"), t("common.field_required"))
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
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_surveys()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_survey(self):
        sel = self._srv_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return
        sid = int(sel[0])
        if not messagebox.askyesno(t("common.confirm_delete"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_survey(sid)
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_surveys()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ---- Statistics Tab ----

    def _build_stats_tab(self):
        self._stats_frame = tk.Frame(self._stats_tab, bg="#ecf0f1", padx=20, pady=20)
        self._stats_frame.pack(fill="both", expand=True)

        ttk.Button(self._stats_frame, text=t("common.refresh"),
                   command=self._load_stats).pack(anchor="w", pady=(0, 15))

        self._stats_labels = {}
        for key, label in [
            ("total_alumni", t("common.total")),
            ("willing_to_mentor", t("common.yes")),
            ("willing_to_speak", t("common.yes")),
            ("at_university", t("common.name")),
            ("employed", t("common.active")),
            ("total_events", t("common.total")),
            ("total_surveys", t("common.total")),
            ("avg_satisfaction", t("common.average")),
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
            messagebox.showerror(t("common.error"), str(e))

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._rec_tree, "alumni.csv")

    # ---- Refresh ----

    def refresh(self):
        self._load_records()
        self._load_events()
        self._load_surveys()
        self._load_stats()
