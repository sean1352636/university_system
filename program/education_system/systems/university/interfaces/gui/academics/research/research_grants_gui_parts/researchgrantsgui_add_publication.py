"""Methods _add_publication through _update_milestone."""

from .. import research_grants_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ResearchGrantsGUI:
    def _add_publication(self):
        """Add publication"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.add_publication.title"))
        dialog.geometry("650x700")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.add_publication.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        entries = {}
        fields = [
            (_("research_grants.fields.publication_title"), "title"),
            (_("research_grants.fields.authors"), "authors"),
            (_("research_grants.fields.publication_type"), "pub_type"),
            (_("research_grants.fields.journal_name"), "journal"),
            (_("research_grants.fields.conference_name"), "conference"),
            (_("research_grants.fields.publication_date"), "pub_date"),
            (_("research_grants.fields.doi"), "doi"),
            (_("research_grants.fields.url"), "url"),
            (_("research_grants.fields.project_id_optional"), "project_id"),
        ]

        for i, (label, field) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            entry = ttk.Entry(form_frame, width=45)
            entry.grid(row=i, column=1, pady=5, padx=(10, 0))
            entries[field] = entry

        # Peer reviewed checkbox
        is_peer_reviewed = tk.BooleanVar()
        ttk.Checkbutton(form_frame, text=_("research_grants.fields.peer_reviewed"),
                       variable=is_peer_reviewed).grid(row=len(fields), column=1, sticky=tk.W, pady=5, padx=(10, 0))

        # Abstract field
        ttk.Label(form_frame, text=_("research_grants.fields.abstract")).grid(
            row=len(fields) + 1, column=0, sticky=tk.NW, pady=5)
        abstract_text = scrolledtext.ScrolledText(form_frame, width=42, height=5)
        abstract_text.grid(row=len(fields) + 1, column=1, pady=5, padx=(10, 0))

        # Keywords field
        ttk.Label(form_frame, text=_("research_grants.fields.keywords")).grid(
            row=len(fields) + 2, column=0, sticky=tk.W, pady=5)
        keywords_entry = ttk.Entry(form_frame, width=45)
        keywords_entry.grid(row=len(fields) + 2, column=1, pady=5, padx=(10, 0))

        def add():
            try:
                # Validate required fields
                if not entries['title'].get() or not entries['authors'].get() or \
                   not entries['pub_type'].get():
                    messagebox.showerror(_("common.error"),
                                       _("research_grants.errors.required_fields"))
                    return

                # Parse project_id (optional)
                project_id = None
                if entries['project_id'].get().strip():
                    try:
                        project_id = int(entries['project_id'].get().strip())
                    except ValueError:
                        messagebox.showerror(_("common.error"),
                                           _("research_grants.errors.invalid_project_id"))
                        return

                # Record the publication
                publication_id = PublicationManager.record_publication(
                    title=entries['title'].get(),
                    authors=entries['authors'].get(),
                    publication_type=entries['pub_type'].get(),
                    project_id=project_id,
                    journal_name=entries['journal'].get(),
                    publication_date=entries['pub_date'].get(),
                    doi=entries['doi'].get()
                )

                # Update additional fields
                with transaction() as conn:
                    conn.execute('''
                        UPDATE research_publications
                        SET conference_name = ?, url = ?, abstract = ?,
                            keywords = ?, is_peer_reviewed = ?
                        WHERE publication_id = ?
                    ''', (entries['conference'].get(),
                          entries['url'].get(),
                          abstract_text.get('1.0', tk.END).strip(),
                          keywords_entry.get(),
                          1 if is_peer_reviewed.get() else 0,
                          publication_id))

                log_activity('create', 'publication', publication_id=publication_id,
                           user_id=self.auth.current_user.get('username'))

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.publication_added").format(id=publication_id))
                self._load_publications()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.add_publication_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text=_("common.add"), command=add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _add_milestone(self):
        """Add project milestone"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.add_milestone.title"))
        dialog.geometry("550x450")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.add_milestone.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        entries = {}
        fields = [
            (_("research_grants.fields.project_id"), "project_id"),
            (_("research_grants.fields.milestone_name"), "milestone_name"),
            (_("research_grants.fields.target_date"), "target_date"),
        ]

        for i, (label, field) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            entry = ttk.Entry(form_frame, width=40)
            entry.grid(row=i, column=1, pady=5, padx=(10, 0))
            entries[field] = entry

        # Description field
        ttk.Label(form_frame, text=_("research_grants.fields.description")).grid(
            row=len(fields), column=0, sticky=tk.NW, pady=5)
        desc_text = scrolledtext.ScrolledText(form_frame, width=37, height=6)
        desc_text.grid(row=len(fields), column=1, pady=5, padx=(10, 0))

        # Deliverables field
        ttk.Label(form_frame, text=_("research_grants.fields.deliverables")).grid(
            row=len(fields) + 1, column=0, sticky=tk.NW, pady=5)
        deliverables_text = scrolledtext.ScrolledText(form_frame, width=37, height=5)
        deliverables_text.grid(row=len(fields) + 1, column=1, pady=5, padx=(10, 0))

        def add():
            try:
                # Validate required fields
                if not entries['project_id'].get() or not entries['milestone_name'].get() or \
                   not entries['target_date'].get():
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

                # Create the milestone
                milestone_id = MilestoneManager.create_milestone(
                    project_id=project_id,
                    milestone_name=entries['milestone_name'].get(),
                    target_date=entries['target_date'].get(),
                    description=desc_text.get('1.0', tk.END).strip()
                )

                # Update deliverables if provided
                if deliverables_text.get('1.0', tk.END).strip():
                    with transaction() as conn:
                        conn.execute('''
                            UPDATE research_milestones
                            SET deliverables = ?
                            WHERE milestone_id = ?
                        ''', (deliverables_text.get('1.0', tk.END).strip(), milestone_id))

                log_activity('create', 'milestone', milestone_id=milestone_id,
                           user_id=self.auth.current_user.get('username'))

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.milestone_added").format(id=milestone_id))
                self._load_milestones()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.add_milestone_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text=_("common.add"), command=add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _update_milestone(self):
        """Update milestone status"""
        selection = self.milestones_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), _("research_grants.errors.select_milestone"))
            return

        item = self.milestones_tree.item(selection[0])
        milestone_id = item['values'][0]
        milestone_name = item['values'][2]

        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.update_milestone.title"))
        dialog.geometry("500x350")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.update_milestone.header").format(
            milestone_name=milestone_name), font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Status dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.status")).grid(
            row=0, column=0, sticky=tk.W, pady=5)
        status_var = tk.StringVar()
        status_combo = ttk.Combobox(form_frame, textvariable=status_var, width=37,
                                    values=['Pending', 'In Progress', 'Completed', 'Delayed', 'Cancelled'],
                                    state='readonly')
        status_combo.current(0)
        status_combo.grid(row=0, column=1, pady=5, padx=(10, 0))

        # Completion date
        ttk.Label(form_frame, text=_("research_grants.fields.completion_date")).grid(
            row=1, column=0, sticky=tk.W, pady=5)
        completion_entry = ttk.Entry(form_frame, width=40)
        completion_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

        # Notes field
        ttk.Label(form_frame, text=_("research_grants.fields.notes")).grid(
            row=2, column=0, sticky=tk.NW, pady=5)
        notes_text = scrolledtext.ScrolledText(form_frame, width=37, height=8)
        notes_text.grid(row=2, column=1, pady=5, padx=(10, 0))

        def update():
            try:
                # Update the milestone
                with transaction() as conn:
                    if status_var.get() == 'Completed' and completion_entry.get().strip():
                        conn.execute('''
                            UPDATE research_milestones
                            SET status = ?, completion_date = ?
                            WHERE milestone_id = ?
                        ''', (status_var.get(), completion_entry.get(), milestone_id))
                    else:
                        conn.execute('''
                            UPDATE research_milestones
                            SET status = ?
                            WHERE milestone_id = ?
                        ''', (status_var.get(), milestone_id))

                log_activity('update', 'milestone', milestone_id=milestone_id,
                           user_id=self.auth.current_user.get('username'),
                           details={'status': status_var.get()})

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.milestone_updated"))
                self._load_milestones()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.update_milestone_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text=_("common.update"), command=update).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)
