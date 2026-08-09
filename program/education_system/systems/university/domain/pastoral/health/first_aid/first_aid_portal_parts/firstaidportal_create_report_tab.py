"""Methods _create_report_tab through _resource_window."""

from .. import first_aid_portal_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class FirstAidPortal:
    def _create_report_tab(self):
        rep_tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        self.notebook.add(rep_tab, text="📝 Report Incident")

        tk.Label(
            rep_tab,
            text="Incident Report Form",
            font=("Segoe UI", 18, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"],
        ).pack(pady=15)

        form_frame = tk.Frame(rep_tab, bg=self.colors["card"], relief="raised", bd=1)
        form_frame.pack(padx=40, pady=10, fill="both", expand=True)

        # Form fields
        fields = [
            ("Reporter Name:", "name"),
            ("Student/Staff ID:", "id"),
            ("Email:", "email"),
            ("Contact Number:", "phone"),
            ("Location of Incident:", "location"),
        ]

        self.form_vars = {}
        for label, key in fields:
            row = tk.Frame(form_frame, bg=self.colors["card"])
            row.pack(fill="x", padx=30, pady=8)

            tk.Label(
                row,
                text=label,
                font=("Segoe UI", 10, "bold"),
                bg=self.colors["card"],
                fg=self.colors["text"],
                width=20,
                anchor="w",
            ).pack(side="left")

            var = tk.StringVar()
            self.form_vars[key] = var
            tk.Entry(row, textvariable=var, font=("Segoe UI", 10), relief="solid", bd=1, width=40).pack(
                side="left", fill="x", expand=True
            )

        # Pre-fill reporter identity from the signed-in user. The email is
        # used to send the reporter a confirmation receipt on submit, so
        # pre-fill it from the resolved address where possible.
        if self.user:
            self.form_vars["name"].set(self.user_display)
            uid = (self.user.get('user_id') or self.user.get('id') or '')
            if uid:
                self.form_vars["id"].set(str(uid))
        prefill_email = self._resolve_user_email(
            self.form_vars["id"].get().strip())
        if prefill_email:
            self.form_vars["email"].set(prefill_email)
        # Phone isn't in EDU_AUTH_*; leave blank rather than guess.

        # Incident type
        row = tk.Frame(form_frame, bg=self.colors["card"])
        row.pack(fill="x", padx=30, pady=8)
        tk.Label(
            row,
            text="Incident Type:",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["card"],
            fg=self.colors["text"],
            width=20,
            anchor="w",
        ).pack(side="left")

        self.form_vars["type"] = tk.StringVar(value="Minor Injury")
        types = ["Minor Injury", "Major Injury", "Illness", "Allergic Reaction", "Mental Health", "Other"]
        ttk.Combobox(row, textvariable=self.form_vars["type"], values=types, state="readonly", width=38).pack(
            side="left", fill="x", expand=True
        )

        # Severity
        row = tk.Frame(form_frame, bg=self.colors["card"])
        row.pack(fill="x", padx=30, pady=8)
        tk.Label(
            row,
            text="Severity Level:",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["card"],
            fg=self.colors["text"],
            width=20,
            anchor="w",
        ).pack(side="left")

        self.form_vars["severity"] = tk.StringVar(value="Low")
        for sev in ["Low", "Medium", "High", "Critical"]:
            tk.Radiobutton(
                row,
                text=sev,
                variable=self.form_vars["severity"],
                value=sev,
                bg=self.colors["card"],
                font=("Segoe UI", 9),
            ).pack(side="left", padx=5)

        # Description
        desc_row = tk.Frame(form_frame, bg=self.colors["card"])
        desc_row.pack(fill="both", expand=True, padx=30, pady=8)
        tk.Label(
            desc_row,
            text="Description:",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["card"],
            fg=self.colors["text"],
            anchor="w",
        ).pack(anchor="w")

        self.description_text = tk.Text(desc_row, font=("Segoe UI", 10), relief="solid", bd=1, height=5)
        self.description_text.pack(fill="both", expand=True, pady=5)

        # Buttons
        btn_row = tk.Frame(form_frame, bg=self.colors["card"])
        btn_row.pack(pady=15)

        tk.Button(
            btn_row,
            text="📤  Submit Report",
            font=("Segoe UI", 11, "bold"),
            bg=self.colors["primary"],
            fg="white",
            relief="flat",
            padx=25,
            pady=8,
            cursor="hand2",
            command=self._submit_report,
        ).pack(side="left", padx=10)

        tk.Button(
            btn_row,
            text="🗑  Clear Form",
            font=("Segoe UI", 11),
            bg="#95a5a6",
            fg="white",
            relief="flat",
            padx=25,
            pady=8,
            cursor="hand2",
            command=self._clear_form,
        ).pack(side="left", padx=10)

        tk.Button(
            btn_row,
            text="📋  View Log",
            font=("Segoe UI", 11),
            bg=self.colors["secondary"],
            fg="white",
            relief="flat",
            padx=25,
            pady=8,
            cursor="hand2",
            command=self._view_incident_log,
        ).pack(side="left", padx=10)

    def _create_resources_tab(self):
        res_tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        self.notebook.add(res_tab, text="📚 Resources")

        tk.Label(
            res_tab,
            text="First Aid Resources & Training",
            font=("Segoe UI", 18, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"],
        ).pack(pady=15)

        resources_frame = tk.Frame(res_tab, bg=self.colors["bg"])
        resources_frame.pack(padx=30, pady=10, fill="both", expand=True)

        resources = [
            ("🎓", "CPR Certification", "Sign up for CPR/AED certification courses held every semester at the University Health Center.", "Register", lambda: self._resource_register_course("CPR / AED Certification")),
            ("📖", "First Aid Handbook", "Download the official university first aid handbook with detailed procedures and emergency contacts.", "Download", self._resource_download_handbook),
            ("🎥", "Training Videos", "Watch training videos on common emergency procedures and response techniques.", "Watch", self._resource_watch_videos),
            ("🗓", "Workshop Schedule", "View upcoming first aid workshops, Red Cross events, and safety seminars on campus.", "View Schedule", self._resource_view_schedule),
            ("🧰", "First Aid Kit Locations", "Campus directory of all first aid kit and AED locations.", "Open Map", self._resource_kit_locations),
            ("📱", "Mobile App", "Get the University Safety App for on-the-go emergency information.", "Get App", self._resource_get_app),
        ]

        for i, (icon, title, desc, btn_text, command) in enumerate(resources):
            row = i // 2
            col = i % 2

            card = tk.Frame(resources_frame, bg=self.colors["card"], relief="raised", bd=1)
            card.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)
            resources_frame.grid_columnconfigure(col, weight=1, uniform="col")

            tk.Label(card, text=icon, font=("Segoe UI", 28), bg=self.colors["card"]).pack(pady=(15, 5))
            tk.Label(
                card,
                text=title,
                font=("Segoe UI", 12, "bold"),
                bg=self.colors["card"],
                fg=self.colors["text"],
            ).pack()
            tk.Label(
                card,
                text=desc,
                font=("Segoe UI", 9),
                bg=self.colors["card"],
                fg="#7f8c8d",
                wraplength=350,
                justify="center",
            ).pack(padx=15, pady=5)

            tk.Button(
                card,
                text=btn_text,
                font=("Segoe UI", 9, "bold"),
                bg=self.colors["accent"],
                fg="white",
                relief="flat",
                padx=15,
                pady=5,
                cursor="hand2",
                command=command,
            ).pack(pady=10)

        # Admin/staff: review who has signed up for training courses.
        if self._is_staff():
            tk.Button(
                res_tab,
                text="👥 View Course Registrations (Admin)",
                font=("Segoe UI", 10, "bold"),
                bg=self.colors["text"],
                fg="white",
                relief="flat",
                padx=20,
                pady=6,
                cursor="hand2",
                command=self._view_registrations,
            ).pack(pady=(0, 15))

    def _view_registrations(self):
        """Admin/staff view of training-course sign-ups, with CSV export."""
        win = self._resource_window("Course Registrations",
                                    "👥  Training Course Registrations",
                                    width=760, height=540)

        log_text = scrolledtext.ScrolledText(win, font=("Consolas", 10),
                                             wrap="word")
        log_text.pack(fill="both", expand=True, padx=15, pady=10)

        regs = []
        if self.db:
            try:
                regs = self.db.fetch_registrations()
            except sqlite3.Error:
                logger.exception("Could not load course registrations")

        if not regs:
            log_text.insert("1.0", "No course registrations yet.\n")
        else:
            for r in regs:
                log_text.insert(
                    "end",
                    f"── Registration REG-{r['id']:04d} ──\n"
                    f"Course:      {r['course']}\n"
                    f"Registered:  {r['submitted_at']}\n"
                    f"Name:        {r['name']} (ID: {r.get('user_id') or '—'})\n"
                    f"Email:       {r.get('email') or '—'}\n"
                    f"Phone:       {r.get('phone') or '—'}\n"
                    f"Preferred:   {r.get('preferred_date') or '—'}\n\n",
                )
        log_text.config(state="disabled")

        def _export():
            if not regs:
                messagebox.showinfo("Export", "Nothing to export.", parent=win)
                return
            import csv
            fname = (f"first_aid_course_registrations_"
                     f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            downloads = os.path.join(os.path.expanduser("~"), "Downloads")
            target_dir = downloads if os.path.isdir(downloads) else tempfile.gettempdir()
            path = os.path.join(target_dir, fname)
            cols = ["id", "submitted_at", "course", "name", "user_id",
                    "email", "phone", "preferred_date"]
            try:
                with open(path, "w", newline="", encoding="utf-8") as fh:
                    writer = csv.DictWriter(fh, fieldnames=cols,
                                            extrasaction="ignore")
                    writer.writeheader()
                    for r in regs:
                        writer.writerow({c: r.get(c, "") for c in cols})
            except OSError:
                logger.exception("Could not export registrations")
                messagebox.showerror("Export Failed",
                                     "Could not write the export file.",
                                     parent=win)
                return
            logger.info("Registrations exported (%s rows) to %s by user=%s",
                        len(regs), path, self.user_display)
            self._open_path(path)
            messagebox.showinfo("Export Complete",
                                f"✓ Exported {len(regs)} registration(s) to:"
                                f"\n\n{path}", parent=win)

        tk.Button(win, text="⤓ Export CSV", font=("Segoe UI", 9, "bold"),
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=12, pady=5, cursor="hand2",
                  command=_export).pack(pady=(0, 12))

    def _resource_window(self, title, heading, width=640, height=520):
        """Create a styled Toplevel for a resource, returning the
        scrollable body frame. Matches the portal's colour scheme."""
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry(f"{width}x{height}")
        win.configure(bg=self.colors["bg"])
        try:
            win.transient(self.root)
        except tk.TclError:
            pass
        tk.Label(
            win,
            text=heading,
            font=("Segoe UI", 16, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"],
        ).pack(pady=12)
        return win
