"""Methods _add_team_member through _update_grant_decision."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import research_grants_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ResearchGrantsGUI:
    def _add_team_member(self):
        """Add team member to project"""
        selection = self.projects_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), _("research_grants.errors.select_project"))
            return

        item = self.projects_tree.item(selection[0])
        project_id = item['values'][0]

        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.add_team_member.title"))
        dialog.geometry("500x300")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.add_team_member.header").format(project_id=project_id),
                 font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.X)

        # Staff member dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.staff_id")).grid(row=0, column=0, sticky=tk.W, pady=8)
        staff_list, staff_id_map = self._load_staff_list()
        staff_var = tk.StringVar()
        staff_combo = ttk.Combobox(form_frame, textvariable=staff_var, values=staff_list,
                                   state='readonly', width=38)
        staff_combo.grid(row=0, column=1, pady=8, padx=(10, 0))
        if staff_list:
            staff_combo.current(0)

        # Role dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.role")).grid(row=1, column=0, sticky=tk.W, pady=8)
        team_roles = [
            'Principal Investigator', 'Co-Investigator', 'Research Associate',
            'Research Assistant', 'Post-Doctoral Researcher', 'PhD Student',
            'Lab Technician', 'Data Analyst', 'Project Manager',
            'Statistician', 'Clinical Coordinator', 'Consultant', 'Other'
        ]
        role_var = tk.StringVar()
        role_combo = ttk.Combobox(form_frame, textvariable=role_var, values=team_roles,
                                  state='readonly', width=38)
        role_combo.grid(row=1, column=1, pady=8, padx=(10, 0))
        role_combo.current(0)

        def add():
            selected_staff = staff_var.get()
            selected_role = role_var.get()
            if not selected_staff:
                messagebox.showwarning(_("common.warning"), _t('gui.academics.research.research_grants_gui_parts.researchgrantsgui_add_team_member.dialogs.please_select_a_staff_member', default="Please select a staff member."))
                return
            if not selected_role:
                messagebox.showwarning(_("common.warning"), _t('gui.academics.research.research_grants_gui_parts.researchgrantsgui_add_team_member.dialogs.please_select_a_role', default="Please select a role."))
                return

            staff_id = staff_id_map.get(selected_staff, selected_staff)

            try:
                member_id = ResearchProjectManager.add_team_member(
                    project_id=project_id,
                    staff_id=staff_id,
                    role=selected_role
                )

                log_activity('create', 'team_member', member_id=member_id,
                            user_id=self.auth.current_user.get('username'))

                messagebox.showinfo(_("common.success"), _("research_grants.messages.team_member_added"))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"), _("research_grants.errors.add_member_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text=_("common.add"), command=add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _load_available_grants(self):
        """Load existing grant names for dropdown."""
        grants = []
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT application_id, grant_name, funding_agency
                FROM grant_applications
                ORDER BY grant_name
            ''')
            for row in cursor.fetchall():
                grants.append(f"#{row[0]} - {row[1]} ({row[2]})")
            conn.close()
        except Exception:
            pass
        return grants

    def _load_projects_list(self):
        """Load research projects for dropdown."""
        projects = []
        project_id_map = {}
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT project_id, project_title, department
                FROM research_projects
                WHERE status = 'active'
                ORDER BY project_title
            ''')
            for row in cursor.fetchall():
                display = f"#{row[0]} - {row[1]} ({row[2]})"
                projects.append(display)
                project_id_map[display] = row[0]
            conn.close()
        except Exception:
            pass
        return projects, project_id_map

    def _submit_grant(self):
        """Submit grant application"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.submit_grant.title"))
        dialog.geometry("620x680")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.submit_grant.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        row = 0

        # Grant Name — dropdown of existing grants + free text for new
        ttk.Label(form_frame, text=_("research_grants.fields.grant_name")).grid(row=row, column=0, sticky=tk.W, pady=5)
        existing_grants = self._load_available_grants()
        grant_name_var = tk.StringVar()
        grant_name_combo = ttk.Combobox(form_frame, textvariable=grant_name_var, width=40)
        # Allow free text for new grant names, but show existing ones
        common_grants = [
            'UKRI Future Leaders Fellowship', 'EPSRC Standard Grant',
            'AHRC Research Grant', 'BBSRC Responsive Mode', 'MRC Programme Grant',
            'NERC Standard Grant', 'ESRC Research Grant', 'Innovate UK Smart Grant',
            'Wellcome Trust Investigator Award', 'Leverhulme Trust Research Grant',
            'Royal Society University Research Fellowship', 'EU Horizon Europe',
            'NIH R01 Research Grant', 'NSF Standard Grant',
        ]
        grant_name_combo['values'] = common_grants
        grant_name_combo.grid(row=row, column=1, pady=5, padx=(10, 0))
        row += 1

        # Funding Agency — dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.funding_agency")).grid(row=row, column=0, sticky=tk.W, pady=5)
        funding_agencies = [
            'UKRI', 'EPSRC', 'AHRC', 'BBSRC', 'MRC', 'NERC', 'ESRC', 'STFC',
            'Innovate UK', 'Wellcome Trust', 'Leverhulme Trust', 'Royal Society',
            'British Academy', 'Nuffield Foundation', 'European Commission',
            'NIH', 'NSF', 'Gates Foundation', 'Cancer Research UK',
            'British Heart Foundation', 'Alzheimer\'s Research UK',
            'Industry Partner', 'Internal University Fund', 'Other'
        ]
        agency_var = tk.StringVar()
        agency_combo = ttk.Combobox(form_frame, textvariable=agency_var,
                                    values=funding_agencies, width=40)
        agency_combo.grid(row=row, column=1, pady=5, padx=(10, 0))
        row += 1

        # PI — dropdown of staff
        ttk.Label(form_frame, text=_("research_grants.fields.pi_id")).grid(row=row, column=0, sticky=tk.W, pady=5)
        staff_list, staff_id_map = self._load_staff_list()
        pi_var = tk.StringVar()
        pi_combo = ttk.Combobox(form_frame, textvariable=pi_var, values=staff_list,
                                state='readonly', width=40)
        pi_combo.grid(row=row, column=1, pady=5, padx=(10, 0))
        if staff_list:
            pi_combo.current(0)
        row += 1

        # Co-Investigators — dropdown of staff (multi-select via repeated add)
        ttk.Label(form_frame, text=_("research_grants.fields.co_investigators")).grid(row=row, column=0, sticky=tk.W, pady=5)
        co_inv_frame = ttk.Frame(form_frame)
        co_inv_frame.grid(row=row, column=1, pady=5, padx=(10, 0), sticky=tk.W)
        co_inv_var = tk.StringVar()
        co_inv_combo = ttk.Combobox(co_inv_frame, textvariable=co_inv_var,
                                     values=staff_list, state='readonly', width=30)
        co_inv_combo.pack(side=tk.LEFT)
        co_inv_list_var = tk.StringVar(value="")

        def add_co_inv():
            selected = co_inv_var.get()
            if selected:
                sid = staff_id_map.get(selected, selected)
                current = co_inv_list_var.get()
                if sid not in current:
                    co_inv_list_var.set(f"{current}, {sid}" if current else sid)

        ttk.Button(co_inv_frame, text=_t('gui.academics.research.research_grants_gui_parts.researchgrantsgui_add_team_member.buttons.add', default="Add"), command=add_co_inv, width=5).pack(side=tk.LEFT, padx=3)
        row += 1

        # Show selected co-investigators
        ttk.Label(form_frame, text=_t('gui.academics.research.research_grants_gui_parts.researchgrantsgui_add_team_member.labels.selected', default="Selected:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        co_inv_display = ttk.Label(form_frame, textvariable=co_inv_list_var, wraplength=350,
                                   font=('Arial', 8))
        co_inv_display.grid(row=row, column=1, sticky=tk.W, padx=(10, 0), pady=2)
        row += 1

        # Requested Amount
        ttk.Label(form_frame, text=_("research_grants.fields.requested_amount")).grid(row=row, column=0, sticky=tk.W, pady=5)
        amount_entry = ttk.Entry(form_frame, width=42)
        amount_entry.grid(row=row, column=1, pady=5, padx=(10, 0))
        row += 1

        # Application Deadline
        ttk.Label(form_frame, text=_("research_grants.fields.application_deadline")).grid(row=row, column=0, sticky=tk.W, pady=5)
        deadline_entry = ttk.Entry(form_frame, width=42)
        deadline_entry.grid(row=row, column=1, pady=5, padx=(10, 0))
        row += 1

        # Project — dropdown of available projects
        ttk.Label(form_frame, text=_("research_grants.fields.project_id_optional")).grid(row=row, column=0, sticky=tk.W, pady=5)
        projects_list, project_id_map = self._load_projects_list()
        project_var = tk.StringVar()
        project_combo = ttk.Combobox(form_frame, textvariable=project_var,
                                     values=['(None)'] + projects_list,
                                     state='readonly', width=40)
        project_combo.grid(row=row, column=1, pady=5, padx=(10, 0))
        project_combo.current(0)
        row += 1

        # Application Documents
        ttk.Label(form_frame, text=_("research_grants.fields.application_documents")).grid(
            row=row, column=0, sticky=tk.NW, pady=5)
        docs_text = scrolledtext.ScrolledText(form_frame, width=38, height=4)
        docs_text.grid(row=row, column=1, pady=5, padx=(10, 0))

        def submit():
            try:
                grant_name = grant_name_var.get().strip()
                agency = agency_var.get().strip()
                pi_selected = pi_var.get()
                pi_id = staff_id_map.get(pi_selected, pi_selected)
                amount_str = amount_entry.get().strip()
                deadline = deadline_entry.get().strip()

                if not grant_name or not agency or not pi_id or not amount_str or not deadline:
                    messagebox.showerror(_("common.error"),
                                       _("research_grants.errors.required_fields"))
                    return

                # Parse project_id (optional)
                project_id = None
                selected_project = project_var.get()
                if selected_project and selected_project != '(None)':
                    project_id = project_id_map.get(selected_project)

                # Submit the grant application
                application_id = GrantApplicationManager.submit_application(
                    grant_name=grant_name,
                    funding_agency=agency,
                    principal_investigator_id=pi_id,
                    requested_amount=float(amount_str),
                    application_deadline=deadline,
                    project_id=project_id
                )

                # Update additional fields
                with transaction() as conn:
                    conn.execute('''
                        UPDATE grant_applications
                        SET co_investigators = ?, submission_date = ?,
                            application_documents = ?
                        WHERE application_id = ?
                    ''', (co_inv_list_var.get(),
                          datetime.now().date().isoformat(),
                          docs_text.get('1.0', tk.END).strip(),
                          application_id))

                log_activity('create', 'grant_application', application_id=application_id,
                           user_id=self.auth.current_user.get('username'))

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.grant_submitted").format(id=application_id))
                self._load_grants()
                dialog.destroy()
            except ValueError:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.invalid_amount"))
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.submit_grant_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(10, 0))
        ttk.Button(btn_frame, text=_("common.submit"), command=submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _update_grant_decision(self):
        """Update grant decision"""
        selection = self.grants_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), _("research_grants.errors.select_grant"))
            return

        item = self.grants_tree.item(selection[0])
        application_id = item['values'][0]
        grant_name = item['values'][1]

        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.update_grant_decision.title"))
        dialog.geometry("500x450")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.update_grant_decision.header").format(
            grant_name=grant_name), font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Decision status
        ttk.Label(form_frame, text=_("research_grants.fields.decision_status")).grid(
            row=0, column=0, sticky=tk.W, pady=5)
        decision_var = tk.StringVar()
        decision_combo = ttk.Combobox(form_frame, textvariable=decision_var, width=37,
                                     values=['Approved', 'Rejected', 'Under Review', 'Pending'],
                                     state='readonly')
        decision_combo.current(0)
        decision_combo.grid(row=0, column=1, pady=5, padx=(10, 0))

        # Awarded amount
        ttk.Label(form_frame, text=_("research_grants.fields.awarded_amount")).grid(
            row=1, column=0, sticky=tk.W, pady=5)
        awarded_entry = ttk.Entry(form_frame, width=40)
        awarded_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

        # Grant period start
        ttk.Label(form_frame, text=_("research_grants.fields.grant_period_start")).grid(
            row=2, column=0, sticky=tk.W, pady=5)
        start_entry = ttk.Entry(form_frame, width=40)
        start_entry.insert(0, datetime.now().date().isoformat())
        start_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        # Grant period end
        ttk.Label(form_frame, text=_("research_grants.fields.grant_period_end")).grid(
            row=3, column=0, sticky=tk.W, pady=5)
        end_entry = ttk.Entry(form_frame, width=40)
        end_entry.grid(row=3, column=1, pady=5, padx=(10, 0))

        # Comments
        ttk.Label(form_frame, text=_("research_grants.fields.comments")).grid(
            row=4, column=0, sticky=tk.NW, pady=5)
        comments_text = scrolledtext.ScrolledText(form_frame, width=37, height=6)
        comments_text.grid(row=4, column=1, pady=5, padx=(10, 0))

        def update():
            try:
                awarded_amount = 0
                if awarded_entry.get().strip():
                    try:
                        awarded_amount = float(awarded_entry.get())
                    except ValueError:
                        messagebox.showerror(_("common.error"),
                                           _("research_grants.errors.invalid_amount"))
                        return

                # Update the grant decision
                GrantApplicationManager.update_decision(
                    application_id=application_id,
                    decision_status=decision_var.get(),
                    awarded_amount=awarded_amount,
                    grant_period_start=start_entry.get(),
                    grant_period_end=end_entry.get()
                )

                log_activity('update', 'grant_application', application_id=application_id,
                           user_id=self.auth.current_user.get('username'),
                           details={'decision': decision_var.get()})

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.grant_decision_updated"))
                self._load_grants()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.update_decision_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text=_("common.update"), command=update).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)
