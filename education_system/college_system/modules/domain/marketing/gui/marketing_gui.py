"""Marketing & Open Days GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.marketing.services.marketing_service import MarketingService


class MarketingFrame(tk.Frame):
    """Marketing & Open Days management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = MarketingService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Marketing & Open Days",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_events_tab()
        self._build_registrations_tab()
        self._build_campaigns_tab()
        self._build_stats_tab()

    # ── Tab 1: Open Days ──

    def _build_events_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Open Days")

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 5))

        tk.Label(toolbar, text="Status:", bg="#ecf0f1").pack(side="left")
        self._ev_status_var = tk.StringVar(value="all")
        ev_status_cb = ttk.Combobox(toolbar, textvariable=self._ev_status_var, width=12,
                                     values=["all", "planned", "confirmed", "completed", "cancelled"],
                                     state="readonly")
        ev_status_cb.pack(side="left", padx=5)
        ev_status_cb.bind("<<ComboboxSelected>>", lambda e: self._load_events())

        tk.Button(toolbar, text="New Event", bg="#27ae60", fg="white",
                  command=self._new_event_dialog).pack(side="right", padx=2)
        tk.Button(toolbar, text="Delete", bg="#e74c3c", fg="white",
                  command=self._delete_event).pack(side="right", padx=2)
        tk.Button(toolbar, text="Edit", bg="#2980b9", fg="white",
                  command=self._edit_event_dialog).pack(side="right", padx=2)
        tk.Button(toolbar, text="View", bg="#8e44ad", fg="white",
                  command=self._view_event).pack(side="right", padx=2)

        cols = ("id", "event_name", "event_date", "type", "capacity", "registrations", "attendees", "status")
        self._ev_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("event_name", "Event Name", 180),
                         ("event_date", "Date", 90), ("type", "Type", 80),
                         ("capacity", "Capacity", 70), ("registrations", "Regs", 50),
                         ("attendees", "Attended", 60), ("status", "Status", 80)]:
            self._ev_tree.heading(c, text=h)
            self._ev_tree.column(c, width=w, anchor="center")
        self._ev_tree.pack(fill="both", expand=True)

        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._ev_tree.yview)
        self._ev_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

    def _load_events(self):
        self._ev_tree.delete(*self._ev_tree.get_children())
        try:
            status = self._ev_status_var.get()
            events = self._svc.list_events(
                status=status if status != "all" else None,
            )
            for ev in events:
                self._ev_tree.insert("", "end", values=(
                    ev["id"], ev["event_name"], ev["event_date"],
                    ev.get("event_type") or "-",
                    ev.get("capacity") or "-",
                    ev.get("registrations", 0),
                    ev.get("attendees", 0),
                    ev.get("status", "planned"),
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_event_id(self):
        sel = self._ev_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Please select an event.")
            return None
        return self._ev_tree.item(sel[0])["values"][0]

    def _new_event_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Open Day Event")
        dlg.geometry("420x480")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        for i, (label, key, default) in enumerate([
            ("Event Name*:", "event_name", ""),
            ("Date* (YYYY-MM-DD):", "event_date", ""),
            ("Type:", "event_type", "open_day"),
            ("Start Time (HH:MM):", "start_time", ""),
            ("End Time (HH:MM):", "end_time", ""),
            ("Capacity:", "capacity", ""),
            ("Location:", "location", ""),
            ("Target Audience:", "target_audience", ""),
        ]):
            tk.Label(dlg, text=label).grid(row=i, column=0, sticky="e", padx=10, pady=4)
            var = tk.StringVar(value=default)
            tk.Entry(dlg, textvariable=var, width=30).grid(row=i, column=1, padx=10, pady=4)
            fields[key] = var

        tk.Label(dlg, text="Description:").grid(row=8, column=0, sticky="ne", padx=10, pady=4)
        desc_text = tk.Text(dlg, width=30, height=4)
        desc_text.grid(row=8, column=1, padx=10, pady=4)

        def _save():
            name = fields["event_name"].get().strip()
            date = fields["event_date"].get().strip()
            if not name or not date:
                messagebox.showwarning("Validation", "Event name and date are required.", parent=dlg)
                return
            try:
                cap = fields["capacity"].get().strip()
                self._svc.create_event(
                    event_name=name,
                    event_date=date,
                    event_type=fields["event_type"].get().strip() or "open_day",
                    start_time=fields["start_time"].get().strip() or None,
                    end_time=fields["end_time"].get().strip() or None,
                    capacity=int(cap) if cap else None,
                    location=fields["location"].get().strip() or None,
                    description=desc_text.get("1.0", "end-1c").strip() or None,
                    target_audience=fields["target_audience"].get().strip() or None,
                )
                messagebox.showinfo("Success", "Event created.", parent=dlg)
                dlg.destroy()
                self._load_events()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        tk.Button(dlg, text="Save", bg="#27ae60", fg="white", command=_save
                  ).grid(row=9, column=0, columnspan=2, pady=15)

    def _view_event(self):
        eid = self._selected_event_id()
        if eid is None:
            return
        try:
            ev = self._svc.get_event(int(eid))
            if not ev:
                messagebox.showwarning("Warning", "Event not found.")
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"Event: {ev['event_name']}")
            dlg.geometry("400x400")
            dlg.transient(self)
            text = tk.Text(dlg, wrap="word", padx=10, pady=10)
            text.pack(fill="both", expand=True)
            for k, v in ev.items():
                text.insert("end", f"{k}: {v}\n")
            text.configure(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _edit_event_dialog(self):
        eid = self._selected_event_id()
        if eid is None:
            return
        try:
            ev = self._svc.get_event(int(eid))
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if not ev:
            messagebox.showwarning("Warning", "Event not found.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Edit Event")
        dlg.geometry("420x520")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        edit_fields = [
            ("Event Name:", "event_name"),
            ("Date (YYYY-MM-DD):", "event_date"),
            ("Type:", "event_type"),
            ("Start Time:", "start_time"),
            ("End Time:", "end_time"),
            ("Capacity:", "capacity"),
            ("Location:", "location"),
            ("Target Audience:", "target_audience"),
            ("Status:", "status"),
        ]
        for i, (label, key) in enumerate(edit_fields):
            tk.Label(dlg, text=label).grid(row=i, column=0, sticky="e", padx=10, pady=4)
            var = tk.StringVar(value=str(ev.get(key) or ""))
            tk.Entry(dlg, textvariable=var, width=30).grid(row=i, column=1, padx=10, pady=4)
            fields[key] = var

        tk.Label(dlg, text="Description:").grid(row=len(edit_fields), column=0, sticky="ne", padx=10, pady=4)
        desc_text = tk.Text(dlg, width=30, height=4)
        desc_text.grid(row=len(edit_fields), column=1, padx=10, pady=4)
        desc_text.insert("1.0", ev.get("description") or "")

        def _save():
            try:
                cap = fields["capacity"].get().strip()
                updates = {
                    "event_name": fields["event_name"].get().strip() or None,
                    "event_date": fields["event_date"].get().strip() or None,
                    "event_type": fields["event_type"].get().strip() or None,
                    "start_time": fields["start_time"].get().strip() or None,
                    "end_time": fields["end_time"].get().strip() or None,
                    "capacity": int(cap) if cap else None,
                    "location": fields["location"].get().strip() or None,
                    "description": desc_text.get("1.0", "end-1c").strip() or None,
                    "target_audience": fields["target_audience"].get().strip() or None,
                    "status": fields["status"].get().strip() or None,
                }
                self._svc.update_event(int(eid), **updates)
                messagebox.showinfo("Success", "Event updated.", parent=dlg)
                dlg.destroy()
                self._load_events()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        tk.Button(dlg, text="Save", bg="#2980b9", fg="white", command=_save
                  ).grid(row=len(edit_fields) + 1, column=0, columnspan=2, pady=15)

    def _delete_event(self):
        eid = self._selected_event_id()
        if eid is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this event and all its registrations?"):
            return
        try:
            self._svc.delete_event(int(eid))
            messagebox.showinfo("Success", "Event deleted.")
            self._load_events()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Tab 2: Registrations ──

    def _build_registrations_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Registrations")

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 5))

        tk.Label(toolbar, text="Event ID:", bg="#ecf0f1").pack(side="left")
        self._reg_event_var = tk.StringVar()
        tk.Entry(toolbar, textvariable=self._reg_event_var, width=8).pack(side="left", padx=5)

        tk.Label(toolbar, text="Search:", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._reg_search_var = tk.StringVar()
        tk.Entry(toolbar, textvariable=self._reg_search_var, width=15).pack(side="left", padx=5)

        tk.Button(toolbar, text="Load", bg="#2980b9", fg="white",
                  command=self._load_registrations).pack(side="left", padx=2)

        tk.Button(toolbar, text="New", bg="#27ae60", fg="white",
                  command=self._new_registration_dialog).pack(side="right", padx=2)
        tk.Button(toolbar, text="Delete", bg="#e74c3c", fg="white",
                  command=self._delete_registration).pack(side="right", padx=2)
        tk.Button(toolbar, text="Mark Attended", bg="#f39c12", fg="white",
                  command=self._mark_attended).pack(side="right", padx=2)
        tk.Button(toolbar, text="Edit", bg="#2980b9", fg="white",
                  command=self._edit_registration_dialog).pack(side="right", padx=2)

        cols = ("id", "event_id", "student_name", "email", "school", "year_group",
                "attended", "follow_up", "applied")
        self._reg_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("event_id", "Event", 50),
                         ("student_name", "Name", 140), ("email", "Email", 150),
                         ("school", "School", 120), ("year_group", "Year", 50),
                         ("attended", "Attended", 60), ("follow_up", "Follow-up", 65),
                         ("applied", "Applied", 55)]:
            self._reg_tree.heading(c, text=h)
            self._reg_tree.column(c, width=w, anchor="center")
        self._reg_tree.pack(fill="both", expand=True)

        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._reg_tree.yview)
        self._reg_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

    def _load_registrations(self):
        self._reg_tree.delete(*self._reg_tree.get_children())
        try:
            eid_str = self._reg_event_var.get().strip()
            eid = int(eid_str) if eid_str else None
            search = self._reg_search_var.get().strip() or None
            regs = self._svc.list_registrations(event_id=eid, search=search)
            for r in regs:
                self._reg_tree.insert("", "end", values=(
                    r["id"], r["event_id"], r["student_name"],
                    r.get("email") or "-", r.get("school") or "-",
                    r.get("year_group") or "-",
                    "Yes" if r["attended"] else "No",
                    "Yes" if r["follow_up_sent"] else "No",
                    "Yes" if r["applied"] else "No",
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_reg_id(self):
        sel = self._reg_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Please select a registration.")
            return None
        return self._reg_tree.item(sel[0])["values"][0]

    def _new_registration_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Registration")
        dlg.geometry("400x360")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        for i, (label, key, default) in enumerate([
            ("Event ID*:", "event_id", self._reg_event_var.get().strip()),
            ("Student Name*:", "student_name", ""),
            ("Email:", "email", ""),
            ("Phone:", "phone", ""),
            ("School:", "school", ""),
            ("Year Group:", "year_group", ""),
            ("Interests:", "interests", ""),
        ]):
            tk.Label(dlg, text=label).grid(row=i, column=0, sticky="e", padx=10, pady=4)
            var = tk.StringVar(value=default)
            tk.Entry(dlg, textvariable=var, width=30).grid(row=i, column=1, padx=10, pady=4)
            fields[key] = var

        def _save():
            eid_str = fields["event_id"].get().strip()
            name = fields["student_name"].get().strip()
            if not eid_str or not name:
                messagebox.showwarning("Validation", "Event ID and student name are required.", parent=dlg)
                return
            try:
                self._svc.create_registration(
                    event_id=int(eid_str),
                    student_name=name,
                    email=fields["email"].get().strip() or None,
                    phone=fields["phone"].get().strip() or None,
                    school=fields["school"].get().strip() or None,
                    year_group=fields["year_group"].get().strip() or None,
                    interests=fields["interests"].get().strip() or None,
                )
                messagebox.showinfo("Success", "Registration created.", parent=dlg)
                dlg.destroy()
                self._load_registrations()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        tk.Button(dlg, text="Save", bg="#27ae60", fg="white", command=_save
                  ).grid(row=7, column=0, columnspan=2, pady=15)

    def _edit_registration_dialog(self):
        rid = self._selected_reg_id()
        if rid is None:
            return

        dlg = tk.Toplevel(self)
        dlg.title("Edit Registration")
        dlg.geometry("400x360")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        for i, (label, key, default) in enumerate([
            ("Student Name:", "student_name", ""),
            ("Email:", "email", ""),
            ("Phone:", "phone", ""),
            ("School:", "school", ""),
            ("Year Group:", "year_group", ""),
            ("Interests:", "interests", ""),
            ("Applied (0/1):", "applied", ""),
        ]):
            tk.Label(dlg, text=label).grid(row=i, column=0, sticky="e", padx=10, pady=4)
            var = tk.StringVar(value=default)
            tk.Entry(dlg, textvariable=var, width=30).grid(row=i, column=1, padx=10, pady=4)
            fields[key] = var

        def _save():
            try:
                updates = {}
                for key in ["student_name", "email", "phone", "school", "year_group", "interests"]:
                    val = fields[key].get().strip()
                    if val:
                        updates[key] = val
                applied = fields["applied"].get().strip()
                if applied in ("0", "1"):
                    updates["applied"] = int(applied)
                if not updates:
                    messagebox.showwarning("Validation", "No changes to save.", parent=dlg)
                    return
                self._svc.update_registration(int(rid), **updates)
                messagebox.showinfo("Success", "Registration updated.", parent=dlg)
                dlg.destroy()
                self._load_registrations()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        tk.Button(dlg, text="Save", bg="#2980b9", fg="white", command=_save
                  ).grid(row=7, column=0, columnspan=2, pady=15)

    def _delete_registration(self):
        rid = self._selected_reg_id()
        if rid is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this registration?"):
            return
        try:
            self._svc.delete_registration(int(rid))
            messagebox.showinfo("Success", "Registration deleted.")
            self._load_registrations()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _mark_attended(self):
        rid = self._selected_reg_id()
        if rid is None:
            return
        try:
            self._svc.mark_attended(int(rid))
            messagebox.showinfo("Success", "Marked as attended.")
            self._load_registrations()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Tab 3: Campaigns ──

    def _build_campaigns_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Campaigns")

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 5))

        tk.Label(toolbar, text="Status:", bg="#ecf0f1").pack(side="left")
        self._camp_status_var = tk.StringVar(value="all")
        camp_cb = ttk.Combobox(toolbar, textvariable=self._camp_status_var, width=12,
                                values=["all", "planned", "active", "completed", "cancelled"],
                                state="readonly")
        camp_cb.pack(side="left", padx=5)
        camp_cb.bind("<<ComboboxSelected>>", lambda e: self._load_campaigns())

        tk.Button(toolbar, text="New Campaign", bg="#27ae60", fg="white",
                  command=self._new_campaign_dialog).pack(side="right", padx=2)
        tk.Button(toolbar, text="Delete", bg="#e74c3c", fg="white",
                  command=self._delete_campaign).pack(side="right", padx=2)
        tk.Button(toolbar, text="Edit", bg="#2980b9", fg="white",
                  command=self._edit_campaign_dialog).pack(side="right", padx=2)

        cols = ("id", "campaign_name", "type", "start_date", "end_date",
                "budget", "spend", "enquiries", "applications", "status")
        self._camp_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("campaign_name", "Campaign", 160),
                         ("type", "Type", 70), ("start_date", "Start", 85),
                         ("end_date", "End", 85), ("budget", "Budget", 70),
                         ("spend", "Spend", 70), ("enquiries", "Enquiries", 65),
                         ("applications", "Apps", 50), ("status", "Status", 80)]:
            self._camp_tree.heading(c, text=h)
            self._camp_tree.column(c, width=w, anchor="center")
        self._camp_tree.pack(fill="both", expand=True)

        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._camp_tree.yview)
        self._camp_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

    def _load_campaigns(self):
        self._camp_tree.delete(*self._camp_tree.get_children())
        try:
            status = self._camp_status_var.get()
            campaigns = self._svc.list_campaigns(
                status=status if status != "all" else None,
            )
            for c in campaigns:
                self._camp_tree.insert("", "end", values=(
                    c["id"], c["campaign_name"],
                    c.get("campaign_type") or "-",
                    c.get("start_date") or "-", c.get("end_date") or "-",
                    f"{c.get('budget', 0):.2f}",
                    f"{c.get('spend', 0):.2f}",
                    c.get("enquiries", 0), c.get("applications", 0),
                    c.get("status", "planned"),
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_campaign_id(self):
        sel = self._camp_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Please select a campaign.")
            return None
        return self._camp_tree.item(sel[0])["values"][0]

    def _new_campaign_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Campaign")
        dlg.geometry("420x440")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        for i, (label, key, default) in enumerate([
            ("Campaign Name*:", "campaign_name", ""),
            ("Type:", "campaign_type", "digital"),
            ("Start Date (YYYY-MM-DD):", "start_date", ""),
            ("End Date (YYYY-MM-DD):", "end_date", ""),
            ("Budget:", "budget", "0"),
            ("Target Audience:", "target_audience", ""),
            ("Channels:", "channels", ""),
        ]):
            tk.Label(dlg, text=label).grid(row=i, column=0, sticky="e", padx=10, pady=4)
            var = tk.StringVar(value=default)
            tk.Entry(dlg, textvariable=var, width=30).grid(row=i, column=1, padx=10, pady=4)
            fields[key] = var

        tk.Label(dlg, text="Notes:").grid(row=7, column=0, sticky="ne", padx=10, pady=4)
        notes_text = tk.Text(dlg, width=30, height=4)
        notes_text.grid(row=7, column=1, padx=10, pady=4)

        def _save():
            name = fields["campaign_name"].get().strip()
            if not name:
                messagebox.showwarning("Validation", "Campaign name is required.", parent=dlg)
                return
            try:
                budget_str = fields["budget"].get().strip()
                self._svc.create_campaign(
                    campaign_name=name,
                    campaign_type=fields["campaign_type"].get().strip() or "digital",
                    start_date=fields["start_date"].get().strip() or None,
                    end_date=fields["end_date"].get().strip() or None,
                    budget=float(budget_str) if budget_str else 0,
                    target_audience=fields["target_audience"].get().strip() or None,
                    channels=fields["channels"].get().strip() or None,
                    notes=notes_text.get("1.0", "end-1c").strip() or None,
                )
                messagebox.showinfo("Success", "Campaign created.", parent=dlg)
                dlg.destroy()
                self._load_campaigns()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        tk.Button(dlg, text="Save", bg="#27ae60", fg="white", command=_save
                  ).grid(row=8, column=0, columnspan=2, pady=15)

    def _edit_campaign_dialog(self):
        cid = self._selected_campaign_id()
        if cid is None:
            return
        try:
            camp = self._svc.get_campaign(int(cid))
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if not camp:
            messagebox.showwarning("Warning", "Campaign not found.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Edit Campaign")
        dlg.geometry("420x520")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        edit_fields = [
            ("Campaign Name:", "campaign_name"),
            ("Type:", "campaign_type"),
            ("Start Date:", "start_date"),
            ("End Date:", "end_date"),
            ("Budget:", "budget"),
            ("Spend:", "spend"),
            ("Target Audience:", "target_audience"),
            ("Channels:", "channels"),
            ("Impressions:", "impressions"),
            ("Enquiries:", "enquiries"),
            ("Applications:", "applications"),
            ("Status:", "status"),
        ]
        for i, (label, key) in enumerate(edit_fields):
            tk.Label(dlg, text=label).grid(row=i, column=0, sticky="e", padx=10, pady=3)
            var = tk.StringVar(value=str(camp.get(key) or ""))
            tk.Entry(dlg, textvariable=var, width=30).grid(row=i, column=1, padx=10, pady=3)
            fields[key] = var

        tk.Label(dlg, text="Notes:").grid(row=len(edit_fields), column=0, sticky="ne", padx=10, pady=3)
        notes_text = tk.Text(dlg, width=30, height=3)
        notes_text.grid(row=len(edit_fields), column=1, padx=10, pady=3)
        notes_text.insert("1.0", camp.get("notes") or "")

        def _save():
            try:
                updates = {}
                for key in ["campaign_name", "campaign_type", "start_date", "end_date",
                            "target_audience", "channels", "status"]:
                    val = fields[key].get().strip()
                    if val:
                        updates[key] = val
                for key in ["budget", "spend"]:
                    val = fields[key].get().strip()
                    if val:
                        updates[key] = float(val)
                for key in ["impressions", "enquiries", "applications"]:
                    val = fields[key].get().strip()
                    if val:
                        updates[key] = int(val)
                notes_val = notes_text.get("1.0", "end-1c").strip()
                if notes_val:
                    updates["notes"] = notes_val
                if not updates:
                    messagebox.showwarning("Validation", "No changes to save.", parent=dlg)
                    return
                self._svc.update_campaign(int(cid), **updates)
                messagebox.showinfo("Success", "Campaign updated.", parent=dlg)
                dlg.destroy()
                self._load_campaigns()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        tk.Button(dlg, text="Save", bg="#2980b9", fg="white", command=_save
                  ).grid(row=len(edit_fields) + 1, column=0, columnspan=2, pady=15)

    def _delete_campaign(self):
        cid = self._selected_campaign_id()
        if cid is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this campaign?"):
            return
        try:
            self._svc.delete_campaign(int(cid))
            messagebox.showinfo("Success", "Campaign deleted.")
            self._load_campaigns()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Tab 4: Statistics ──

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Statistics")

        self._stats_frame = tk.Frame(tab, bg="#ecf0f1")
        self._stats_frame.pack(fill="both", expand=True)

        tk.Button(tab, text="Refresh Statistics", bg="#2980b9", fg="white",
                  command=self._load_stats).pack(pady=10)

    def _load_stats(self):
        for w in self._stats_frame.winfo_children():
            w.destroy()
        try:
            stats = self._svc.get_stats()

            sections = [
                ("Open Day Events", [
                    ("Total Events", stats["total_events"]),
                    ("Total Registrations", stats["total_registrations"]),
                    ("Total Attended", stats["total_attended"]),
                    ("Attendance Rate", f"{stats['attendance_rate']}%"),
                    ("Follow-ups Sent", stats["total_followed_up"]),
                    ("Applied After Visit", stats["total_applied"]),
                    ("Application Rate", f"{stats['application_rate']}%"),
                ]),
                ("Marketing Campaigns", [
                    ("Total Campaigns", stats["total_campaigns"]),
                    ("Total Budget", f"${stats['total_budget']:,.2f}"),
                    ("Total Spend", f"${stats['total_spend']:,.2f}"),
                    ("Budget Utilisation", f"{stats['budget_utilisation']}%"),
                    ("Total Impressions", f"{stats['total_impressions']:,}"),
                    ("Total Enquiries", stats["total_enquiries"]),
                    ("Total Applications", stats["total_applications"]),
                ]),
            ]

            for section_title, items in sections:
                lf = tk.LabelFrame(self._stats_frame, text=section_title,
                                   bg="#ecf0f1", font=("Helvetica", 11, "bold"),
                                   padx=15, pady=10)
                lf.pack(fill="x", pady=8)
                for label, value in items:
                    row = tk.Frame(lf, bg="#ecf0f1")
                    row.pack(fill="x", pady=2)
                    tk.Label(row, text=f"{label}:", bg="#ecf0f1",
                             font=("Helvetica", 10), anchor="w", width=22
                             ).pack(side="left")
                    tk.Label(row, text=str(value), bg="#ecf0f1",
                             font=("Helvetica", 10, "bold"), anchor="w"
                             ).pack(side="left")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Public refresh ──

    def refresh(self):
        self._load_events()
        self._load_registrations()
        self._load_campaigns()
        self._load_stats()
