"""Methods for the Registers & RIDDOR tab: RIDDOR assessment and reporting,
the first-aider certificate register and coverage by location, the kit /
AED register with inspections, training course sessions and the campus
phone numbers. Rules live in ``application/health/first_aid``."""

from .. import first_aid_portal_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _rules():
    from education_system.systems.university.domains.health.application.health import (
        first_aid,
    )
    return first_aid


def _connect():
    from education_system.systems.university.domains.health.infrastructure.health.storage import (
        get_connection,
    )
    conn = get_connection()
    conn.row_factory = None
    return conn


class FirstAidPortal:
    # ------------------------------------------------------------ plumbing

    def _fa_who(self):
        from education_system.systems.university.domains.health.application.health import access
        return access.from_user(self.user)

    def _fa_read(self, fn, *args, **kwargs):
        try:
            conn = _connect()
            try:
                return fn(conn, *args, **kwargs)
            finally:
                conn.close()
        except Exception:
            logger.exception("First aid register read failed")
            return []

    def _fa_write(self, parent, fn, *args, **kwargs):
        """Run a rule in one transaction; e-mails it returns are sent after
        the commit. Returns the result, or None (error shown)."""
        conn = _connect()
        try:
            result = fn(conn, *args, **kwargs)
            conn.commit()
        except (PermissionError, ValueError) as exc:
            conn.rollback()
            messagebox.showerror("First Aid", str(exc), parent=parent)
            return None
        except Exception as exc:
            conn.rollback()
            logger.exception("First aid register write failed")
            messagebox.showerror("First Aid", f"Could not save: {exc}", parent=parent)
            return None
        finally:
            conn.close()
        if isinstance(result, list) and result and isinstance(result[0], tuple):
            try:
                from education_system.systems.university.infrastructure.ui.record_screens import (
                    send_emails,
                )
                send_emails(result)
            except Exception:
                logger.debug("First aid notices not sent", exc_info=True)
        return True if result is None or result == [] else result

    @staticmethod
    def _fa_tree(parent, columns, widths=None, height=12):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=8, pady=6)
        tree = ttk.Treeview(frame, columns=[c for c, _ in columns], show="headings",
                            height=height)
        for (key, heading), width in zip(columns, widths or [110] * len(columns)):
            tree.heading(key, text=heading)
            tree.column(key, width=width, anchor="w")
        bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=bar.set)
        tree.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        return tree

    @staticmethod
    def _fa_fill(tree, rows, values):
        for item in tree.get_children():
            tree.delete(item)
        for row in rows:
            tree.insert("", "end", iid=str(row["id"]), values=values(row))

    def _fa_form(self, title, fields, initial=None, parent=None):
        """A small modal form; ``fields`` = [(key, label, choices|None)].
        Returns the entered values, or None when cancelled."""
        initial = initial or {}
        win = tk.Toplevel(parent or self.root)
        win.title(title)
        win.configure(bg=self.colors["bg"])
        win.transient(parent or self.root)
        body = tk.Frame(win, bg=self.colors["card"], relief="raised", bd=1)
        body.pack(fill="both", expand=True, padx=15, pady=15)
        vars_ = {}
        for row, (key, label, choices) in enumerate(fields):
            tk.Label(body, text=label, bg=self.colors["card"], fg=self.colors["text"],
                     font=("Segoe UI", 10, "bold"), anchor="w").grid(
                row=row, column=0, sticky="w", padx=10, pady=4)
            var = tk.StringVar(value="" if initial.get(key) is None else str(initial[key]))
            if choices:
                widget = ttk.Combobox(body, textvariable=var, values=list(choices), width=40,
                                      state="readonly")
                if not var.get():
                    var.set(list(choices)[0])
            else:
                widget = ttk.Entry(body, textvariable=var, width=43)
            widget.grid(row=row, column=1, sticky="we", padx=10, pady=4)
            vars_[key] = var
        result = {}

        def _ok():
            result.update({k: v.get().strip() for k, v in vars_.items()})
            win.destroy()

        btns = tk.Frame(body, bg=self.colors["card"])
        btns.grid(row=len(fields), column=0, columnspan=2, pady=10)
        tk.Button(btns, text="Save", bg=self.colors["accent"], fg="white", relief="flat",
                  padx=16, command=_ok).pack(side="left", padx=5)
        tk.Button(btns, text="Cancel", bg="#bdc3c7", fg="white", relief="flat", padx=16,
                  command=win.destroy).pack(side="left", padx=5)
        win.grab_set()
        win.wait_window()
        return result or None

    # ------------------------------------------------------------ the tab

    def _create_registers_tab(self):
        tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        self.notebook.add(tab, text="⚖ Registers & RIDDOR")
        who = self._fa_who()
        if who is None or not who.is_clinician:
            tk.Label(tab, text="The RIDDOR queue and the first aid registers are kept by the "
                               "health team and first aiders.\n\nFirst aid kits, AEDs and "
                               "course dates are listed under Resources.",
                     font=("Segoe UI", 11), bg=self.colors["bg"], fg=self.colors["text"],
                     justify="center").pack(pady=60)
            return
        inner = ttk.Notebook(tab)
        inner.pack(fill="both", expand=True, padx=6, pady=6)
        for title, build in (("RIDDOR", self._build_riddor_tab),
                             ("First aiders", self._build_first_aiders_tab),
                             ("Coverage", self._build_coverage_tab),
                             ("Kits & AEDs", self._build_kits_tab),
                             ("Course sessions", self._build_sessions_tab),
                             ("Campus numbers", self._build_campus_numbers_tab)):
            frame = tk.Frame(inner, bg=self.colors["bg"])
            inner.add(frame, text=title)
            build(frame)

    # ------------------------------------------------------------ RIDDOR

    def _build_riddor_tab(self, frame):
        rules = _rules()
        summary = tk.Label(frame, bg=self.colors["bg"], fg=self.colors["text"],
                           font=("Segoe UI", 10, "bold"), justify="left")
        summary.pack(anchor="w", padx=10, pady=(8, 0))
        tk.Label(frame, text="Serious incidents not yet assessed, and reportable incidents not "
                             "yet reported to the HSE (report at hse.gov.uk/riddor).",
                 bg=self.colors["bg"], fg="#7f8c8d", font=("Segoe UI", 9)).pack(
            anchor="w", padx=10)
        tree = self._fa_tree(frame, [("id", "Incident"), ("date", "Date"),
                                     ("location", "Location"), ("severity", "Severity"),
                                     ("category", "Category"), ("state", "RIDDOR")],
                             [80, 90, 140, 80, 220, 200])

        def load():
            rows = self._fa_read(rules.riddor_queue)
            self._fa_fill(tree, rows, lambda r: (
                f"INC-{r['id']:04d}", r.get("incident_date") or str(r["submitted_at"])[:10],
                r.get("location") or "", r.get("severity") or "",
                rules.CATEGORIES.get(r.get("riddor_category"), "—"), r["riddor_state"]))
            state["rows"] = {str(r["id"]): r for r in rows}
            counts = self._fa_read(rules.riddor_summary) or {}
            summary.config(text=(f"Overdue: {counts.get('overdue', 0)}    Due within "
                                 f"{rules.DUE_SOON_DAYS} days: {counts.get('due_soon', 0)}    "
                                 f"Reported: {counts.get('by_status', {}).get('reported', 0)}"))

        state = {"rows": {}}

        def selected():
            sel = tree.selection()
            row = state["rows"].get(sel[0]) if sel else None
            if row is None:
                messagebox.showinfo("RIDDOR", "Select an incident first.", parent=frame)
            return row

        btns = tk.Frame(frame, bg=self.colors["bg"])
        btns.pack(fill="x", padx=10, pady=6)
        ttk.Button(btns, text="Assess…", command=lambda: (
            (row := selected()) and self._riddor_dialog(row, frame, load))).pack(side="left")
        ttk.Button(btns, text="Record HSE report…", command=lambda: (
            (row := selected()) and self._riddor_reported_dialog(row, frame, load))).pack(
            side="left", padx=6)
        ttk.Button(btns, text="Refresh", command=load).pack(side="left")
        load()

    def _riddor_dialog(self, incident, parent, on_done=None):
        rules = _rules()
        persons = {v: k for k, v in rules.PERSON_TYPES.items()}
        categories = {v: k for k, v in rules.CATEGORIES.items()}
        values = self._fa_form(
            f"RIDDOR assessment — INC-{incident['id']:04d}",
            [("person", "Person affected:", list(persons)),
             ("category", "Category:", list(categories)),
             ("incident_date", "Incident date (YYYY-MM-DD):", None),
             ("notes", "Notes:", None)],
            {"person": rules.PERSON_TYPES.get(incident.get("person_type") or "non_worker"),
             "category": rules.CATEGORIES.get(incident.get("riddor_category") or
                                              "not_reportable"),
             "incident_date": incident.get("incident_date") or
             str(incident.get("submitted_at") or "")[:10],
             "notes": incident.get("riddor_notes") or ""}, parent)
        if not values:
            return
        result = self._fa_write(parent, rules.assess_riddor, self._fa_who(), incident["id"],
                                person_type=persons[values["person"]],
                                category=categories[values["category"]],
                                notes=values["notes"], incident_date=values["incident_date"])
        if result:
            messagebox.showinfo(
                "RIDDOR",
                ("Reportable under RIDDOR — report to the HSE by " + str(result["deadline"])
                 + ".\nDeaths and specified injuries must also be notified without delay.")
                if result["status"] == "reportable" else
                {"reported": "Already reported to the HSE.",
                 "record_only": "Not reportable — keep the record (over-3-day injury).",
                 "not_reportable": "Not reportable under RIDDOR."}.get(result["status"], ""),
                parent=parent)
            if on_done:
                on_done()

    def _riddor_reported_dialog(self, incident, parent, on_done=None):
        values = self._fa_form(
            f"HSE report — INC-{incident['id']:04d}",
            [("hse_reference", "HSE reference:", None),
             ("reported_on", "Reported on (YYYY-MM-DD):", None)],
            {"hse_reference": incident.get("hse_reference") or "",
             "reported_on": datetime.now().strftime("%Y-%m-%d")}, parent)
        if values and self._fa_write(parent, _rules().mark_reported, self._fa_who(),
                                     incident["id"], values["hse_reference"],
                                     values["reported_on"]) and on_done:
            on_done()

    # ------------------------------------------------------------ first aiders

    def _build_first_aiders_tab(self, frame):
        rules = _rules()
        tree = self._fa_tree(frame, [("name", "Name"), ("qualification", "Qualification"),
                                     ("location", "Location"), ("expires", "Expires"),
                                     ("state", "Certificate"), ("status", "Status")],
                             [150, 220, 140, 90, 120, 80])
        state = {"rows": {}}

        def load():
            rows = self._fa_read(rules.first_aiders, include_withdrawn=True)
            state["rows"] = {str(r["id"]): r for r in rows}
            self._fa_fill(tree, rows, lambda r: (r["name"], r["qualification"],
                                                 r.get("location") or "", r["expires_on"],
                                                 r["certificate_state"], r["status"]))

        fields = [("name", "Name:", None), ("username", "Username (optional):", None),
                  ("email", "Email:", None), ("qualification", "Qualification:",
                                              rules.QUALIFICATIONS),
                  ("certificate_number", "Certificate number:", None),
                  ("issued_on", "Issued (YYYY-MM-DD):", None),
                  ("expires_on", "Expires (YYYY-MM-DD):", None),
                  ("location", "Usual location:", None),
                  ("status", "Status:", ("active", "lapsed", "withdrawn")),
                  ("notes", "Notes:", None)]

        def edit(new):
            row = None
            if not new:
                sel = tree.selection()
                row = state["rows"].get(sel[0]) if sel else None
                if row is None:
                    messagebox.showinfo("First aiders", "Select a first aider.", parent=frame)
                    return
            values = self._fa_form("First aider", fields, row, frame)
            if values and self._fa_write(frame, rules.save_first_aider, self._fa_who(), values,
                                         None if new else row["id"]):
                load()

        btns = tk.Frame(frame, bg=self.colors["bg"])
        btns.pack(fill="x", padx=10, pady=6)
        ttk.Button(btns, text="Add…", command=lambda: edit(True)).pack(side="left")
        ttk.Button(btns, text="Edit / renew…", command=lambda: edit(False)).pack(
            side="left", padx=6)
        ttk.Button(btns, text="Refresh", command=load).pack(side="left")
        load()

    def _build_coverage_tab(self, frame):
        rules = _rules()
        tk.Label(frame, text="Valid first aiders by location. Places with incidents or kits but "
                             "no valid first aider are listed first.",
                 bg=self.colors["bg"], fg="#7f8c8d", font=("Segoe UI", 9)).pack(
            anchor="w", padx=10, pady=(8, 0))
        tree = self._fa_tree(frame, [("location", "Location"), ("valid", "Valid"),
                                     ("expiring", "Expiring ≤30d"), ("expired", "Expired"),
                                     ("incidents", "Incidents 90d"), ("kits", "Kits"),
                                     ("aeds", "AEDs"), ("gap", "Coverage")],
                             [200, 60, 100, 70, 100, 50, 50, 100])

        def load():
            rows = self._fa_read(rules.coverage_by_location)
            for item in tree.get_children():
                tree.delete(item)
            for i, r in enumerate(rows):
                tree.insert("", "end", iid=str(i), values=(
                    r["location"], r["valid"], r["expiring"], r["expired"], r["incidents_90d"],
                    r["kits"], r["aeds"], "⚠ NO COVER" if r["gap"] else "OK"))

        ttk.Button(frame, text="Refresh", command=load).pack(anchor="w", padx=10, pady=6)
        load()

    # ------------------------------------------------------------ kits / AEDs

    def _build_kits_tab(self, frame):
        rules = _rules()
        tree = self._fa_tree(frame, [("label", "Item"), ("kind", "Kind"),
                                     ("location", "Location"), ("checked", "Last checked"),
                                     ("next", "Next check"), ("attention", "Attention")],
                             [150, 120, 160, 90, 90, 260])
        state = {"rows": {}}
        kinds = {v: k for k, v in rules.KIT_KINDS.items()}

        def load():
            rows = self._fa_read(rules.kits, include_retired=True)
            state["rows"] = {str(r["id"]): r for r in rows}
            self._fa_fill(tree, rows, lambda r: (
                r["label"], rules.KIT_KINDS.get(r["kind"], r["kind"]), r["location"],
                r.get("last_checked") or "never", r["next_check"], r["attention"]))

        def chosen():
            sel = tree.selection()
            row = state["rows"].get(sel[0]) if sel else None
            if row is None:
                messagebox.showinfo("Kits & AEDs", "Select an item.", parent=frame)
            return row

        def edit(new):
            row = None if new else chosen()
            if not new and row is None:
                return
            initial = dict(row or {})
            if row:
                initial["kind"] = rules.KIT_KINDS.get(row["kind"])
            values = self._fa_form("Kit / AED", [
                ("kind", "Kind:", list(kinds)), ("label", "Label:", None),
                ("location", "Location:", None), ("detail", "Where exactly:", None),
                ("check_every_days", "Check every (days):", None),
                ("contents_expiry", "Contents expire (YYYY-MM-DD):", None),
                ("aed_pads_expiry", "AED pads expire (YYYY-MM-DD):", None),
                ("aed_battery_expiry", "AED battery expires (YYYY-MM-DD):", None),
                ("status", "Status:", ("in_service", "needs_restock", "out_of_service",
                                       "retired"))], initial, frame)
            if not values:
                return
            values["kind"] = kinds[values["kind"]]
            if row:
                values["last_checked"] = row.get("last_checked")
            if self._fa_write(frame, rules.save_kit, self._fa_who(), values,
                              None if new else row["id"]):
                load()

        def inspect():
            row = chosen()
            if row is None:
                return
            values = self._fa_form(f"Check — {row['label']}", [
                ("outcome", "Outcome:", ("ok", "restocked", "faulty")),
                ("notes", "Notes:", None)], None, frame)
            if values and self._fa_write(frame, rules.inspect_kit, self._fa_who(), row["id"],
                                         values["outcome"], values["notes"]):
                load()

        def history():
            row = chosen()
            if row is None:
                return
            rows = self._fa_read(rules.kit_inspections, row["id"])
            text = "\n".join(f"{r['inspected_at']}  {r['outcome']:<10} {r['inspected_by']}"
                             f"{'  — ' + r['notes'] if r.get('notes') else ''}" for r in rows)
            messagebox.showinfo(f"Checks — {row['label']}", text or "No checks recorded yet.",
                                parent=frame)

        btns = tk.Frame(frame, bg=self.colors["bg"])
        btns.pack(fill="x", padx=10, pady=6)
        for label, command in (("Add…", lambda: edit(True)), ("Edit…", lambda: edit(False)),
                               ("Record check…", inspect), ("Check history", history),
                               ("Refresh", load)):
            ttk.Button(btns, text=label, command=command).pack(side="left", padx=(0, 6))
        load()

    # ------------------------------------------------------------ course sessions

    def _build_sessions_tab(self, frame):
        rules = _rules()
        tree = self._fa_tree(frame, [("when", "Starts"), ("course", "Course"),
                                     ("location", "Location"), ("trainer", "Trainer"),
                                     ("places", "Booked / capacity"), ("status", "Status")],
                             [130, 220, 150, 120, 110, 90])
        state = {"rows": {}}
        show_all = tk.BooleanVar(value=False)

        def load():
            rows = self._fa_read(rules.sessions, upcoming_only=not show_all.get())
            state["rows"] = {str(r["id"]): r for r in rows}
            self._fa_fill(tree, rows, lambda r: (
                str(r["starts_at"])[:16], r["course"], r.get("location") or "",
                r.get("trainer") or "", f"{r['booked']} / {r['capacity']}", r["status"]))

        def chosen():
            sel = tree.selection()
            row = state["rows"].get(sel[0]) if sel else None
            if row is None:
                messagebox.showinfo("Course sessions", "Select a session.", parent=frame)
            return row

        fields = [("course", "Course:", rules.COURSES),
                  ("starts_at", "Starts (YYYY-MM-DD HH:MM):", None),
                  ("ends_at", "Ends (YYYY-MM-DD HH:MM):", None),
                  ("location", "Location:", None), ("trainer", "Trainer:", None),
                  ("capacity", "Capacity:", None), ("description", "Description:", None)]

        def edit(new):
            row = None if new else chosen()
            if not new and row is None:
                return
            values = self._fa_form("Course session", fields, row or {"capacity": 12}, frame)
            if values and self._fa_write(frame, rules.save_session, self._fa_who(), values,
                                         None if new else row["id"]):
                load()

        def set_status(status):
            row = chosen()
            if row is None:
                return
            if status == "cancelled" and not messagebox.askyesno(
                    "Cancel session", f"Cancel {row['course']} on {row['starts_at']}? The "
                    f"{row['booked']} people booked will be e-mailed.", parent=frame):
                return
            if self._fa_write(frame, rules.set_session_status, self._fa_who(), row["id"],
                              status):
                load()

        def bookings():
            row = chosen()
            if row is None:
                return
            regs = [r for r in (self.db.fetch_registrations() if self.db else [])
                    if r.get("session_id") == row["id"]]
            text = "\n".join(f"{r['name']}  {r.get('email') or ''}  {r.get('phone') or ''}"
                             for r in regs)
            messagebox.showinfo(f"Booked — {row['course']}", text or "Nobody booked yet.",
                                parent=frame)

        btns = tk.Frame(frame, bg=self.colors["bg"])
        btns.pack(fill="x", padx=10, pady=6)
        for label, command in (("Schedule…", lambda: edit(True)), ("Edit…", lambda: edit(False)),
                               ("Cancel session", lambda: set_status("cancelled")),
                               ("Mark completed", lambda: set_status("completed")),
                               ("Bookings", bookings), ("Refresh", load)):
            ttk.Button(btns, text=label, command=command).pack(side="left", padx=(0, 6))
        ttk.Checkbutton(btns, text="Include past / cancelled", variable=show_all,
                        command=load).pack(side="left", padx=10)
        load()

    # ------------------------------------------------------------ campus numbers

    def _build_campus_numbers_tab(self, frame):
        tk.Label(frame, text="The university's own phone numbers, shown in the Emergency "
                             "Contacts tab and the CLI directory. 999 and NHS 111 are fixed.",
                 bg=self.colors["bg"], fg="#7f8c8d", font=("Segoe UI", 9),
                 wraplength=700, justify="left").pack(anchor="w", padx=10, pady=(10, 6))
        current = campus_numbers()
        labels = {c["key"]: c["name"] for c in EMERGENCY_CONTACTS if c.get("key")}
        form = tk.Frame(frame, bg=self.colors["bg"])
        form.pack(anchor="w", padx=10)
        vars_ = {}
        for row, key in enumerate(CAMPUS_NUMBER_KEYS):
            tk.Label(form, text=labels.get(key, key) + ":", bg=self.colors["bg"],
                     fg=self.colors["text"], font=("Segoe UI", 10, "bold")).grid(
                row=row, column=0, sticky="w", pady=4)
            vars_[key] = tk.StringVar(value=current.get(key, ""))
            ttk.Entry(form, textvariable=vars_[key], width=30).grid(row=row, column=1, padx=10,
                                                                    pady=4)

        def save():
            for key, var in vars_.items():
                number = var.get().strip()
                if number and not _is_valid_phone(number):
                    messagebox.showerror("Campus numbers", f"{labels.get(key, key)}: enter a "
                                         "valid phone number.", parent=frame)
                    return
            try:
                for key, var in vars_.items():
                    set_campus_number(key, var.get())
            except Exception as exc:
                messagebox.showerror("Campus numbers", f"Could not save: {exc}", parent=frame)
                return
            self.emergency_contacts = self._load_emergency_contacts()
            messagebox.showinfo("Campus numbers", "Saved. Reopen the portal to refresh the "
                                "Emergency Contacts tab.", parent=frame)

        ttk.Button(frame, text="Save numbers", command=save).pack(anchor="w", padx=10, pady=10)
