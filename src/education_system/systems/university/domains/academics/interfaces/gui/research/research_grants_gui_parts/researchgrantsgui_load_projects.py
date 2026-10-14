"""Methods _load_projects through _load_staff_list."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import research_grants_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ResearchGrantsGUI:
    def _load_projects(self):
        """Load all research projects"""
        try:
            self.projects_tree.delete(*self.projects_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT project_id, project_title, principal_investigator_id,
                           department, project_type, start_date, total_budget, status
                    FROM research_projects
                    ORDER BY created_at DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['project_id'],
                        row['project_title'],
                        row['principal_investigator_id'],
                        row['department'],
                        row['project_type'],
                        row['start_date'],
                        f"£{row['total_budget']:,.2f}" if row['total_budget'] else '£0.00',
                        row['status']
                    )
                    self.projects_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("research_grants.errors.load_projects_failed").format(error=e))

    def _load_grants(self):
        """Load all grant applications"""
        try:
            self.grants_tree.delete(*self.grants_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT application_id, grant_name, funding_agency,
                           principal_investigator_id, requested_amount, awarded_amount,
                           decision_status, application_deadline
                    FROM grant_applications
                    ORDER BY submission_date DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['application_id'],
                        row['grant_name'],
                        row['funding_agency'],
                        row['principal_investigator_id'],
                        f"£{row['requested_amount']:,.2f}",
                        f"£{row['awarded_amount']:,.2f}" if row['awarded_amount'] else _("common.na"),
                        row['decision_status'],
                        row['application_deadline']
                    )
                    self.grants_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("research_grants.errors.load_grants_failed").format(error=e))

    def _load_publications(self):
        """Load all publications"""
        try:
            self.publications_tree.delete(*self.publications_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT publication_id, title, authors, publication_type,
                           journal_name,
                           CASE
                               WHEN publication_date IS NOT NULL THEN substr(publication_date, 1, 4)
                               ELSE 'N/A'
                           END as publication_year,
                           citation_count
                    FROM research_publications
                    ORDER BY publication_date DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['publication_id'],
                        row['title'],
                        row['authors'] or _("common.na"),
                        row['publication_type'],
                        row['journal_name'] or _("common.na"),
                        row['publication_year'] or _("common.na"),
                        row['citation_count'] or 0
                    )
                    self.publications_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("research_grants.errors.load_publications_failed").format(error=e))

    def _load_milestones(self):
        """Load all project milestones"""
        try:
            self.milestones_tree.delete(*self.milestones_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT milestone_id, project_id, milestone_description,
                           target_date as due_date, completion_date, status
                    FROM research_milestones
                    ORDER BY target_date
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['milestone_id'],
                        row['project_id'],
                        row['milestone_description'] or _("common.na"),
                        row['due_date'],
                        row['completion_date'] or _("research_grants.status.not_completed"),
                        row['status']
                    )
                    self.milestones_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("research_grants.errors.load_milestones_failed").format(error=e))

    def _load_equipment(self):
        """Load all equipment"""
        try:
            self.equipment_tree.delete(*self.equipment_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT equipment_id, equipment_name, assigned_project_id as project_id,
                           purchase_date, purchase_cost as cost, current_location as location, status
                    FROM research_equipment
                    ORDER BY purchase_date DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['equipment_id'],
                        row['equipment_name'],
                        row['project_id'] or _("common.na"),
                        row['purchase_date'],
                        f"£{row['cost']:,.2f}" if row['cost'] else _("common.na"),
                        row['location'] or _("common.na"),
                        row['status']
                    )
                    self.equipment_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("research_grants.errors.load_equipment_failed").format(error=e))

    def _load_irb(self):
        """Load all IRB applications"""
        try:
            self.irb_tree.delete(*self.irb_tree.get_children())

            with get_connection() as conn:
                # Check if table exists first
                cursor = conn.execute('''
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='irb_applications'
                ''')

                if not cursor.fetchone():
                    # Table doesn't exist - show message
                    print("ℹ️  IRB applications table not yet created")
                    return

                cursor = conn.execute('''
                    SELECT application_id, project_id, protocol_number,
                           submission_date, review_type, decision, status
                    FROM irb_applications
                    ORDER BY submission_date DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['application_id'],
                        row['project_id'],
                        row['protocol_number'] or _("research_grants.status.pending"),
                        row['submission_date'],
                        row['review_type'],
                        row['decision'] or _("research_grants.status.under_review"),
                        row['status']
                    )
                    self.irb_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("research_grants.errors.load_irb_failed").format(error=e))

    def _generate_pi_id(self):
        """Generate a random Principal Investigator ID."""
        digits = ''.join(random.choices(string.digits, k=6))
        return f"PI-{digits}"

    def _load_departments_list(self):
        """Load departments from DB for dropdown."""
        departments = []
        try:
            conn = get_connection()
            cursor = conn.cursor()
            # Try departments table first
            cursor.execute("SELECT name FROM departments WHERE is_active = 1 ORDER BY name")
            departments = [row[0] for row in cursor.fetchall()]
            # If empty, try distinct departments from existing projects
            if not departments:
                cursor.execute("SELECT DISTINCT department FROM research_projects WHERE department IS NOT NULL ORDER BY department")
                departments = [row[0] for row in cursor.fetchall()]
            conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        # Always include common university departments as fallback
        defaults = [
            'Computer Science', 'Engineering', 'Mathematics', 'Physics', 'Chemistry',
            'Biology', 'Medicine', 'Psychology', 'Business', 'Economics',
            'Law', 'Education', 'Arts & Humanities', 'Social Sciences',
            'Environmental Science', 'Nursing', 'Architecture', 'Music',
            'Philosophy', 'History', 'Languages', 'Pharmacy'
        ]
        for d in defaults:
            if d not in departments:
                departments.append(d)
        departments.sort()
        return departments

    def _create_project(self):
        """Create a new research project"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.create_project.title"))
        dialog.geometry("550x520")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.create_project.header"), font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        row = 0

        # Project Title
        ttk.Label(form_frame, text=_("research_grants.fields.project_title")).grid(row=row, column=0, sticky=tk.W, pady=5)
        title_entry = ttk.Entry(form_frame, width=35)
        title_entry.grid(row=row, column=1, pady=5, padx=(10, 0))
        row += 1

        # PI ID — auto-generated
        ttk.Label(form_frame, text=_("research_grants.fields.pi_id")).grid(row=row, column=0, sticky=tk.W, pady=5)
        pi_frame = ttk.Frame(form_frame)
        pi_frame.grid(row=row, column=1, pady=5, padx=(10, 0), sticky=tk.W)
        pi_var = tk.StringVar(value=self._generate_pi_id())
        pi_entry = ttk.Entry(pi_frame, textvariable=pi_var, width=20)
        pi_entry.pack(side=tk.LEFT)
        ttk.Button(pi_frame, text=_t('gui.academics.research.research_grants_gui_parts.researchgrantsgui_load_projects.buttons.generate', default="Generate"),
                  command=lambda: pi_var.set(self._generate_pi_id())).pack(side=tk.LEFT, padx=5)
        row += 1

        # Department — dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.department")).grid(row=row, column=0, sticky=tk.W, pady=5)
        departments = self._load_departments_list()
        dept_var = tk.StringVar()
        dept_combo = ttk.Combobox(form_frame, textvariable=dept_var, values=departments, width=33)
        dept_combo.grid(row=row, column=1, pady=5, padx=(10, 0))
        if departments:
            dept_combo.current(0)
        row += 1

        # Project Type — dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.project_type")).grid(row=row, column=0, sticky=tk.W, pady=5)
        project_types = [
            'Basic Research', 'Applied Research', 'Clinical Trial',
            'Experimental Development', 'Action Research', 'Case Study',
            'Longitudinal Study', 'Cross-Sectional Study', 'Systematic Review',
            'Meta-Analysis', 'Collaborative Research', 'Interdisciplinary',
            'Industry Partnership', 'Community-Based', 'Other'
        ]
        type_var = tk.StringVar()
        type_combo = ttk.Combobox(form_frame, textvariable=type_var, values=project_types,
                                  state='readonly', width=33)
        type_combo.grid(row=row, column=1, pady=5, padx=(10, 0))
        type_combo.current(0)
        row += 1

        # Start Date
        ttk.Label(form_frame, text=_("research_grants.fields.start_date")).grid(row=row, column=0, sticky=tk.W, pady=5)
        start_entry = ttk.Entry(form_frame, width=35)
        start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        start_entry.grid(row=row, column=1, pady=5, padx=(10, 0))
        row += 1

        # Budget
        ttk.Label(form_frame, text=_("research_grants.fields.budget")).grid(row=row, column=0, sticky=tk.W, pady=5)
        budget_entry = ttk.Entry(form_frame, width=35)
        budget_entry.grid(row=row, column=1, pady=5, padx=(10, 0))
        row += 1

        # Activity tags (cross-domain risk register feed) — comma-
        # separated. Recognised tags: biosafety, human_subjects,
        # animal, chemical, radiation, clinical, data_protection,
        # field_work. Anything else falls under "Compliance".
        ttk.Label(form_frame, text=_t('gui.academics.research.research_grants_gui_parts.researchgrantsgui_load_projects.labels.activity_tags', default="Activity tags")).grid(row=row, column=0, sticky=tk.W, pady=5)
        tags_entry = ttk.Entry(form_frame, width=35)
        tags_entry.grid(row=row, column=1, pady=5, padx=(10, 0))
        ttk.Label(form_frame, text=_t('gui.academics.research.research_grants_gui_parts.researchgrantsgui_load_projects.labels.comma_sep_e_g_biosafety_human_subjects', default="(comma-sep; e.g. biosafety, human_subjects)"),
                  font=('Arial', 8), foreground='#666'
                  ).grid(row=row + 1, column=1, sticky=tk.W, padx=(10, 0))
        row += 2

        # Description
        ttk.Label(form_frame, text=_("research_grants.fields.description")).grid(row=row, column=0, sticky=tk.NW, pady=5)
        desc_text = scrolledtext.ScrolledText(form_frame, width=33, height=5)
        desc_text.grid(row=row, column=1, pady=5, padx=(10, 0))

        def create():
            try:
                tags_raw = tags_entry.get().strip()
                activity_tags = [t.strip() for t in tags_raw.split(',')
                                 if t.strip()] if tags_raw else None
                project_id = ResearchProjectManager.create_project(
                    project_title=title_entry.get(),
                    principal_investigator_id=pi_var.get(),
                    department=dept_var.get(),
                    project_type=type_var.get(),
                    start_date=start_entry.get(),
                    description=desc_text.get('1.0', tk.END).strip(),
                    total_budget=float(budget_entry.get() or 0),
                    activity_tags=activity_tags,
                )

                log_activity('create', 'research_project', project_id=project_id,
                            user_id=self.auth.current_user.get('username'))

                messagebox.showinfo(_("common.success"), _("research_grants.messages.project_created").format(id=project_id))
                self._load_projects()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"), _("research_grants.errors.create_project_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(15, 0))
        ttk.Button(btn_frame, text=_("common.create"), command=create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _load_staff_list(self):
        """Load staff/admin/instructor users from DB for dropdown."""
        staff = []
        staff_id_map = {}
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, first_name, last_name, role
                FROM users
                WHERE role IN ('staff', 'admin', 'instructor')
                ORDER BY last_name, first_name
            ''')
            for row in cursor.fetchall():
                uid, uname, first, last, role = row
                display = f"{uname} - {first} {last} ({role})"
                staff.append(display)
                staff_id_map[display] = str(uname)
            conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        return staff, staff_id_map
