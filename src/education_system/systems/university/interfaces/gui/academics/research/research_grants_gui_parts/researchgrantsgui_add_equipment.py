"""Methods _add_equipment through _refresh_ui_language."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import research_grants_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ResearchGrantsGUI:
    def _add_equipment(self):
        """Add equipment"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.add_equipment.title"))
        dialog.geometry("600x600")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.add_equipment.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        entries = {}
        fields = [
            (_("research_grants.fields.equipment_name"), "equipment_name"),
            (_("research_grants.fields.equipment_type"), "equipment_type"),
            (_("research_grants.fields.model_number"), "model_number"),
            (_("research_grants.fields.serial_number"), "serial_number"),
            (_("research_grants.fields.purchase_date"), "purchase_date"),
            (_("research_grants.fields.purchase_cost"), "purchase_cost"),
            (_("research_grants.fields.current_location"), "location"),
            (_("research_grants.fields.assigned_project_id"), "project_id"),
        ]

        for i, (label, field) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            entry = ttk.Entry(form_frame, width=42)
            entry.grid(row=i, column=1, pady=5, padx=(10, 0))
            entries[field] = entry

        # Status dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.status")).grid(
            row=len(fields), column=0, sticky=tk.W, pady=5)
        status_var = tk.StringVar(value=_t('gui.academics.research.research_grants_gui_parts.researchgrantsgui_add_equipment.values.available', default='Available'))
        status_combo = ttk.Combobox(form_frame, textvariable=status_var, width=40,
                                    values=['Available', 'In Use', 'Under Maintenance', 'Retired'],
                                    state='readonly')
        status_combo.grid(row=len(fields), column=1, pady=5, padx=(10, 0))

        # Maintenance schedule field
        ttk.Label(form_frame, text=_("research_grants.fields.maintenance_schedule")).grid(
            row=len(fields) + 1, column=0, sticky=tk.NW, pady=5)
        maintenance_text = scrolledtext.ScrolledText(form_frame, width=39, height=5)
        maintenance_text.grid(row=len(fields) + 1, column=1, pady=5, padx=(10, 0))

        def add():
            try:
                # Validate required fields
                if not entries['equipment_name'].get() or not entries['equipment_type'].get():
                    messagebox.showerror(_("common.error"),
                                       _("research_grants.errors.required_fields"))
                    return

                # Parse purchase cost
                purchase_cost = 0
                if entries['purchase_cost'].get().strip():
                    try:
                        purchase_cost = float(entries['purchase_cost'].get())
                    except ValueError:
                        messagebox.showerror(_("common.error"),
                                           _("research_grants.errors.invalid_cost"))
                        return

                # Parse project_id (optional)
                assigned_project_id = None
                if entries['project_id'].get().strip():
                    try:
                        assigned_project_id = int(entries['project_id'].get().strip())
                    except ValueError:
                        messagebox.showerror(_("common.error"),
                                           _("research_grants.errors.invalid_project_id"))
                        return

                # Register the equipment
                equipment_id = EquipmentManager.register_equipment(
                    equipment_name=entries['equipment_name'].get(),
                    equipment_type=entries['equipment_type'].get(),
                    serial_number=entries['serial_number'].get(),
                    purchase_cost=purchase_cost
                )

                # Update additional fields
                with transaction() as conn:
                    conn.execute('''
                        UPDATE research_equipment
                        SET model_number = ?, purchase_date = ?, current_location = ?,
                            assigned_project_id = ?, status = ?, maintenance_schedule = ?
                        WHERE equipment_id = ?
                    ''', (entries['model_number'].get(),
                          entries['purchase_date'].get(),
                          entries['location'].get(),
                          assigned_project_id,
                          status_var.get(),
                          maintenance_text.get('1.0', tk.END).strip(),
                          equipment_id))

                log_activity('create', 'equipment', equipment_id=equipment_id,
                           user_id=self.auth.current_user.get('username'))

                # Grant spend → Finance bus. Restricted-fund posting,
                # not a student charge, so we bypass raise_charge() and
                # publish the event directly. Finance subscribers map the
                # grant reference to the right restricted ledger.
                try:
                    if assigned_project_id and purchase_cost:
                        from education_system.systems.university.interfaces.gui.academics._event_bus import (
                            publish, EVENT_CHARGE_RAISED,
                        )
                        publish(
                            EVENT_CHARGE_RAISED,
                            source="research_grant",
                            account=f"grant:{assigned_project_id}",
                            amount=float(purchase_cost),
                            description=(
                                f"Equipment purchase #{equipment_id} — "
                                f"{entries['equipment_name'].get()}"
                            ),
                            reference_id=str(assigned_project_id),
                            posted_by=self.auth.current_user.get('username'),
                        )
                except Exception as grant_bus_err:
                    print(f"Warning: grant spend bus publish failed: {grant_bus_err}")

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.equipment_added").format(id=equipment_id))
                self._load_equipment()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.add_equipment_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text=_("common.add"), command=add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _submit_irb(self):
        """Submit IRB application"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.submit_irb.title"))
        dialog.geometry("600x600")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.submit_irb.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        entries = {}
        fields = [
            (_("research_grants.fields.project_id"), "project_id"),
            (_("research_grants.fields.protocol_number"), "protocol_number"),
            (_("research_grants.fields.submission_date"), "submission_date"),
        ]

        for i, (label, field) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            entry = ttk.Entry(form_frame, width=42)
            if field == 'submission_date':
                entry.insert(0, datetime.now().date().isoformat())
            entry.grid(row=i, column=1, pady=5, padx=(10, 0))
            entries[field] = entry

        # Review type dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.review_type")).grid(
            row=len(fields), column=0, sticky=tk.W, pady=5)
        review_type_var = tk.StringVar()
        review_type_combo = ttk.Combobox(form_frame, textvariable=review_type_var, width=40,
                                         values=['Expedited', 'Full Board', 'Exempt', 'Continuation'],
                                         state='readonly')
        review_type_combo.current(0)
        review_type_combo.grid(row=len(fields), column=1, pady=5, padx=(10, 0))

        # Study description
        ttk.Label(form_frame, text=_("research_grants.fields.study_description")).grid(
            row=len(fields) + 1, column=0, sticky=tk.NW, pady=5)
        study_desc_text = scrolledtext.ScrolledText(form_frame, width=39, height=6)
        study_desc_text.grid(row=len(fields) + 1, column=1, pady=5, padx=(10, 0))

        # Risk assessment
        ttk.Label(form_frame, text=_("research_grants.fields.risk_assessment")).grid(
            row=len(fields) + 2, column=0, sticky=tk.NW, pady=5)
        risk_text = scrolledtext.ScrolledText(form_frame, width=39, height=5)
        risk_text.grid(row=len(fields) + 2, column=1, pady=5, padx=(10, 0))

        def submit():
            try:
                # Validate required fields
                if not entries['project_id'].get() or not entries['submission_date'].get():
                    messagebox.showerror(_("common.error"),
                                       _("research_grants.errors.required_fields"))
                    return

                # Parse project_id
                try:
                    project_id = int(entries['project_id'].get())
                except ValueError:
                    messagebox.showerror(_("common.error"),
                                       _("research_grants.errors.invalid_project_id"))
                    return

                # Create irb_applications table if it doesn't exist
                with transaction() as conn:
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS irb_applications (
                            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            project_id INTEGER NOT NULL,
                            protocol_number TEXT,
                            submission_date TEXT NOT NULL,
                            review_type TEXT NOT NULL,
                            decision TEXT DEFAULT 'Pending',
                            decision_date TEXT,
                            status TEXT DEFAULT 'Submitted',
                            study_description TEXT,
                            risk_assessment TEXT,
                            reviewer_comments TEXT,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
                        )
                    ''')

                    # Submit the IRB application
                    cursor = conn.execute('''
                        INSERT INTO irb_applications (
                            project_id, protocol_number, submission_date, review_type,
                            study_description, risk_assessment
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (project_id,
                          entries['protocol_number'].get(),
                          entries['submission_date'].get(),
                          review_type_var.get(),
                          study_desc_text.get('1.0', tk.END).strip(),
                          risk_text.get('1.0', tk.END).strip()))

                    application_id = cursor.lastrowid

                log_activity('create', 'irb_application', application_id=application_id,
                           user_id=self.auth.current_user.get('username'))

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.irb_submitted").format(id=application_id))
                self._load_irb()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.submit_irb_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text=_("common.submit"), command=submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _update_irb_decision(self):
        """Update IRB decision"""
        selection = self.irb_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), _("research_grants.errors.select_irb"))
            return

        item = self.irb_tree.item(selection[0])
        application_id = item['values'][0]
        protocol_number = item['values'][2]

        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.update_irb_decision.title"))
        dialog.geometry("550x450")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.update_irb_decision.header").format(
            protocol=protocol_number), font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Decision dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.decision")).grid(
            row=0, column=0, sticky=tk.W, pady=5)
        decision_var = tk.StringVar()
        decision_combo = ttk.Combobox(form_frame, textvariable=decision_var, width=37,
                                     values=['Approved', 'Approved with Conditions', 'Deferred',
                                            'Disapproved', 'Pending'],
                                     state='readonly')
        decision_combo.current(0)
        decision_combo.grid(row=0, column=1, pady=5, padx=(10, 0))

        # Status dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.status")).grid(
            row=1, column=0, sticky=tk.W, pady=5)
        status_var = tk.StringVar()
        status_combo = ttk.Combobox(form_frame, textvariable=status_var, width=37,
                                   values=['Submitted', 'Under Review', 'Approved', 'Closed'],
                                   state='readonly')
        status_combo.current(1)
        status_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        # Decision date
        ttk.Label(form_frame, text=_("research_grants.fields.decision_date")).grid(
            row=2, column=0, sticky=tk.W, pady=5)
        date_entry = ttk.Entry(form_frame, width=40)
        date_entry.insert(0, datetime.now().date().isoformat())
        date_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        # Reviewer comments
        ttk.Label(form_frame, text=_("research_grants.fields.reviewer_comments")).grid(
            row=3, column=0, sticky=tk.NW, pady=5)
        comments_text = scrolledtext.ScrolledText(form_frame, width=37, height=8)
        comments_text.grid(row=3, column=1, pady=5, padx=(10, 0))

        def update():
            try:
                # Update the IRB decision
                with transaction() as conn:
                    conn.execute('''
                        UPDATE irb_applications
                        SET decision = ?, status = ?, decision_date = ?,
                            reviewer_comments = ?
                        WHERE application_id = ?
                    ''', (decision_var.get(),
                          status_var.get(),
                          date_entry.get(),
                          comments_text.get('1.0', tk.END).strip(),
                          application_id))

                log_activity('update', 'irb_application', application_id=application_id,
                           user_id=self.auth.current_user.get('username'),
                           details={'decision': decision_var.get()})

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.irb_decision_updated"))
                self._load_irb()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.update_irb_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text=_("common.update"), command=update).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _on_language_change(self):
        """Handle language change request"""
        old_lang = get_current_language()
        show_gui_language_selector(self.window)
        new_lang = get_current_language()

        if old_lang != new_lang:
            messagebox.showinfo(
                _("research_grants.language.changed_title"),
                _("research_grants.language.restart_for_full_effect")
            )
            self._refresh_ui_language()

    def _refresh_ui_language(self):
        """Refresh all UI text elements with current language translations"""
        try:
            # Update window title
            self.window.title(_("research_grants.title"))

            # Note: For a full refresh, the window would need to be recreated
            # This is a simplified version that updates what's easily accessible

        except Exception as e:
            print(f"Error refreshing UI language: {e}")
