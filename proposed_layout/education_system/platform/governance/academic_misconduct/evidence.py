"""Evidence management for the Academic Misconduct Panel."""

from education_system.platform.governance.academic_misconduct._imports import (
    tk, ttk, messagebox, scrolledtext, _t, datetime,
    sqlite3, DEFAULT_DB_PATH, SECURE_UPLOAD_AVAILABLE, validate_upload, secure_filename,
    compute_file_hash,
)

# Evidence categories — tailored for academic misconduct
EVIDENCE_CATEGORIES = [
    "Student Submission", "Turnitin Report", "Original Source",
    "Screenshot", "Email Correspondence", "Witness Statement",
    "Assessment Brief", "Mark Scheme", "Module Handbook",
    "Communication Log", "Meeting Notes", "Other Document",
]

# Document handling actions — education-appropriate
CUSTODY_ACTIONS = [
    "Collected by Staff", "Reviewed by Tutor", "Submitted to Panel",
    "Shared with Student", "Returned to Student", "Filed",
    "Copied for Records", "Forwarded to Head of Department",
    "Sent to External Examiner", "Archived", "Other",
]


class MisconductEvidenceMixin:
    """Mixin providing evidence tab and upload functionality."""

    def create_evidence_tab(self, parent):
        """Create the evidence tab content."""
        # Store reference to evidence frame for refresh
        self.evidence_parent = parent
        self.evidence_frame = tk.Frame(parent, bg=self.colors['light'])
        self.evidence_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.refresh_evidence_tab()

    def refresh_evidence_tab(self):
        """Refresh the evidence tab with current case data."""
        for widget in self.evidence_frame.winfo_children():
            widget.destroy()

        tk.Label(
            self.evidence_frame,
            text=_t("misconduct.evidence.title", "Supporting Documents & Evidence"),
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 5))

        tk.Label(
            self.evidence_frame,
            text="Upload, tag, and track documents related to academic misconduct cases.",
            font=('Segoe UI', 9),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 10))

        if not self.selected_case:
            tk.Label(self.evidence_frame, text="Select a case from the Cases view to manage its documents.",
                     font=('Segoe UI', 11), fg=self.colors['text_muted'],
                     bg=self.colors['light']).pack(pady=20)
            return

        # --- Filter / search bar ---
        filter_frame = tk.Frame(self.evidence_frame, bg=self.colors['light'])
        filter_frame.pack(fill=tk.X, pady=(0, 8))

        tk.Label(filter_frame, text="Search:", bg=self.colors['light']).pack(side=tk.LEFT, padx=(0, 5))
        self._ev_search_var = tk.StringVar()
        search_entry = tk.Entry(filter_frame, textvariable=self._ev_search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(filter_frame, text="Type:", bg=self.colors['light']).pack(side=tk.LEFT, padx=(0, 5))
        self._ev_cat_var = tk.StringVar(value="All")
        cat_combo = ttk.Combobox(filter_frame, textvariable=self._ev_cat_var,
                                  values=["All"] + EVIDENCE_CATEGORIES, state='readonly', width=18)
        cat_combo.pack(side=tk.LEFT)

        def _apply_filter(*_a):
            self._populate_evidence_tree()
        self._ev_search_var.trace_add('write', _apply_filter)
        cat_combo.bind('<<ComboboxSelected>>', _apply_filter)

        # --- Treeview ---
        tree_frame = tk.Frame(self.evidence_frame, bg=self.colors['light'])
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        cols = ('id', 'file', 'category', 'size', 'hash', 'tags', 'date')
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        self._ev_tree = ttk.Treeview(tree_frame, columns=cols, show='headings',
                                      yscrollcommand=vsb.set, height=8)
        vsb.config(command=self._ev_tree.yview)

        for c, text, w in [
            ('id', 'ID', 40), ('file', 'Document', 180), ('category', 'Type', 100),
            ('size', 'Size', 70), ('hash', 'Integrity', 110), ('tags', 'Labels', 120),
            ('date', 'Date Added', 130),
        ]:
            self._ev_tree.heading(c, text=text)
            self._ev_tree.column(c, width=w)

        self._ev_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._populate_evidence_tree()

        # --- Per-item action buttons ---
        action_frame = tk.Frame(self.evidence_frame, bg=self.colors['light'])
        action_frame.pack(fill=tk.X, pady=(0, 5))

        self.create_button(action_frame, "Add Label", self._add_tag_to_selected, 'info').pack(side=tk.LEFT, padx=(0, 6))
        self.create_button(action_frame, "Add Note", self._add_note_to_selected, 'secondary').pack(side=tk.LEFT, padx=(0, 6))
        self.create_button(action_frame, "Log Handling", self._log_custody_for_selected, 'warning').pack(side=tk.LEFT, padx=(0, 6))
        self.create_button(action_frame, "Check Integrity", self._verify_selected_evidence, 'info').pack(side=tk.LEFT, padx=(0, 6))
        self.create_button(action_frame, "Document Trail", self._show_custody_log, 'secondary').pack(side=tk.LEFT)

        # --- Main action buttons ---
        btn_frame = tk.Frame(self.evidence_frame, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(8, 0))

        self.create_button(btn_frame, "Upload Document", self.upload_evidence, 'primary').pack(side=tk.LEFT, padx=(0, 10))
        self.create_button(btn_frame, "Check All Files", self._verify_all_evidence, 'info').pack(side=tk.LEFT, padx=(0, 10))
        self.create_button(btn_frame, "Export Report", self._export_evidence_report, 'secondary').pack(side=tk.LEFT, padx=(0, 10))
        self.create_button(btn_frame, "Refresh", self.refresh_evidence_tab, 'secondary').pack(side=tk.LEFT)

    def _populate_evidence_tree(self):
        """Populate the evidence treeview, applying filters."""
        if not hasattr(self, '_ev_tree'):
            return
        for item in self._ev_tree.get_children():
            self._ev_tree.delete(item)

        search = self._ev_search_var.get().lower() if hasattr(self, '_ev_search_var') else ''
        cat_filter = self._ev_cat_var.get() if hasattr(self, '_ev_cat_var') else 'All'

        try:
            db = self._get_db_path() if hasattr(self, '_get_db_path') else str(DEFAULT_DB_PATH)
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT id, file_name, file_size, file_hash, category, notes, uploaded_date
                FROM academic_misconduct_evidence
                WHERE case_id = ?
                ORDER BY uploaded_date DESC
            ''', (self.selected_case['id'],)).fetchall()

            for row in rows:
                cat = row['category'] if 'category' in row.keys() else ''
                if cat_filter != 'All' and cat != cat_filter:
                    continue

                # Get tags
                tags = conn.execute(
                    "SELECT tag FROM academic_misconduct_evidence_tags WHERE evidence_id=?",
                    (row['id'],)
                ).fetchall()
                tag_str = ', '.join(t['tag'] for t in tags)

                name = row['file_name']
                notes = row['notes'] if 'notes' in row.keys() else ''

                # Apply text search
                if search:
                    haystack = f"{name} {cat} {tag_str} {notes}".lower()
                    if search not in haystack:
                        continue

                fhash = row['file_hash'] if 'file_hash' in row.keys() else ''
                hash_short = fhash[:16] + '...' if fhash else 'N/A'

                self._ev_tree.insert('', tk.END, iid=str(row['id']), values=(
                    row['id'], name, cat, row['file_size'] or '',
                    hash_short, tag_str, row['uploaded_date'] or '',
                ))
            conn.close()
        except Exception as e:
            print(f"Error loading evidence: {e}")

    def _get_selected_evidence_id(self):
        """Get the currently selected evidence ID from the treeview."""
        if not hasattr(self, '_ev_tree'):
            return None
        sel = self._ev_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a document from the list first.")
            return None
        return int(sel[0])

    # ------------------------------------------------------------------
    # Per-item actions (from Evidence Organizer)
    # ------------------------------------------------------------------

    def _add_tag_to_selected(self):
        """Add a label to the selected document."""
        ev_id = self._get_selected_evidence_id()
        if ev_id is None:
            return
        from tkinter import simpledialog
        tag = simpledialog.askstring("Add Label", "Enter a label for this document\n(e.g. 'plagiarised section', 'original source', 'key evidence'):", parent=self.root)
        if tag and tag.strip():
            self.add_evidence_tag(ev_id, tag.strip())
            self.add_case_history(self.selected_case['id'],
                                 f"Label '{tag.strip()}' added to document #{ev_id}", 'info')
            self._populate_evidence_tree()

    def _add_note_to_selected(self):
        """Add/edit notes on the selected document."""
        ev_id = self._get_selected_evidence_id()
        if ev_id is None:
            return
        from tkinter import simpledialog
        note = simpledialog.askstring("Add Note", "Enter a note about this document:", parent=self.root)
        if note is not None:
            try:
                db = self._get_db_path() if hasattr(self, '_get_db_path') else str(DEFAULT_DB_PATH)
                conn = sqlite3.connect(db)
                conn.execute(
                    "UPDATE academic_misconduct_evidence SET notes=? WHERE id=?",
                    (note, ev_id))
                conn.commit()
                conn.close()
                self._populate_evidence_tree()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save note: {e}")

    def _log_custody_for_selected(self):
        """Log a document handling entry for the selected document."""
        ev_id = self._get_selected_evidence_id()
        if ev_id is None:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Log Document Handling")
        dlg.geometry("420x320")
        dlg.configure(bg=self.colors['light'])
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="Document Handling Record", font=('Segoe UI', 12, 'bold'),
                 bg=self.colors['light']).pack(pady=(15, 10))

        form = tk.Frame(dlg, bg=self.colors['light'])
        form.pack(fill=tk.X, padx=20)

        tk.Label(form, text="Staff Member:", bg=self.colors['light']).grid(row=0, column=0, sticky='w', pady=5)
        handler_entry = tk.Entry(form, width=30)
        handler_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        tk.Label(form, text="Action Taken:", bg=self.colors['light']).grid(row=1, column=0, sticky='w', pady=5)
        action_var = tk.StringVar(value=CUSTODY_ACTIONS[0])
        action_combo = ttk.Combobox(form, textvariable=action_var, values=CUSTODY_ACTIONS,
                                     state='readonly', width=27)
        action_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        tk.Label(form, text="Notes:", bg=self.colors['light']).grid(row=2, column=0, sticky='nw', pady=5)
        details_text = tk.Text(form, width=30, height=4)
        details_text.grid(row=2, column=1, pady=5, padx=(10, 0))

        def _save():
            handler = handler_entry.get().strip()
            if not handler:
                messagebox.showwarning("Required", "Please enter the staff member's name.")
                return
            action = action_var.get()
            details = details_text.get('1.0', tk.END).strip()
            self.add_chain_of_custody(ev_id, handler, action, details)
            self.add_case_history(self.selected_case['id'],
                                 f"{action} by {handler} (document #{ev_id})", 'info')
            dlg.destroy()
            messagebox.showinfo("Recorded", "Document handling has been recorded.")

        btn_f = tk.Frame(dlg, bg=self.colors['light'])
        btn_f.pack(pady=15)
        self.create_button(btn_f, "Save", _save, 'primary').pack(side=tk.LEFT, padx=5)
        self.create_button(btn_f, "Cancel", dlg.destroy, 'secondary').pack(side=tk.LEFT, padx=5)

    def _verify_selected_evidence(self):
        """Check the integrity of the selected document."""
        ev_id = self._get_selected_evidence_id()
        if ev_id is None:
            return
        result = self.verify_evidence_integrity(ev_id)
        if result is True:
            messagebox.showinfo("File Intact", "This document has not been modified since it was uploaded.")
        elif result is False:
            messagebox.showwarning("File Modified", "This document has been modified since upload.\nThe original file may have been altered.")
        else:
            messagebox.showinfo("Cannot Check", "No integrity data stored for this document.")

    def _export_evidence_report(self):
        """Export a text report of all evidence for the selected case."""
        if not self.selected_case:
            messagebox.showwarning("No Case", "Select a case first.")
            return

        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            title="Export Evidence Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"evidence_report_{self.selected_case['id']}.txt",
        )
        if not path:
            return

        try:
            db = self._get_db_path() if hasattr(self, '_get_db_path') else str(DEFAULT_DB_PATH)
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row

            case = self.selected_case
            lines = [
                "ACADEMIC MISCONDUCT - SUPPORTING DOCUMENTS REPORT",
                f"{'=' * 60}",
                f"Case ID:      {case['id']}",
                f"Student:      {case['student']} ({case['student_id']})",
                f"Violation:    {case['type']}",
                f"Status:       {case['status']}",
                f"Date Filed:   {case['date_filed']}",
                f"Severity:     {case['severity']}",
                f"Report Date:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"{'=' * 60}",
                "",
                "DOCUMENTS & EVIDENCE",
                f"{'-' * 60}",
            ]

            ev_rows = conn.execute(
                "SELECT * FROM academic_misconduct_evidence WHERE case_id=? ORDER BY uploaded_date",
                (case['id'],)
            ).fetchall()

            for i, ev in enumerate(ev_rows, 1):
                lines.append(f"\n  [{i}] {ev['file_name']}")
                lines.append(f"      Category:  {ev['category'] if 'category' in ev.keys() else 'N/A'}")
                lines.append(f"      Size:      {ev['file_size'] or 'N/A'}")
                lines.append(f"      SHA-256:   {ev['file_hash'] if 'file_hash' in ev.keys() and ev['file_hash'] else 'N/A'}")
                lines.append(f"      Uploaded:  {ev['uploaded_date']}")
                lines.append(f"      Notes:     {ev['notes'] if 'notes' in ev.keys() and ev['notes'] else 'None'}")

                # Tags
                tags = conn.execute(
                    "SELECT tag FROM academic_misconduct_evidence_tags WHERE evidence_id=?",
                    (ev['id'],)
                ).fetchall()
                if tags:
                    lines.append(f"      Tags:      {', '.join(t['tag'] for t in tags)}")

                # Chain of custody
                custody = conn.execute(
                    "SELECT * FROM academic_misconduct_chain_of_custody WHERE evidence_id=? ORDER BY timestamp",
                    (ev['id'],)
                ).fetchall()
                if custody:
                    lines.append("      Handling Trail:")
                    for c in custody:
                        lines.append(f"        {c['timestamp']} | {c['handler']} | {c['action']} | {c['details']}")

            if not ev_rows:
                lines.append("  No documents uploaded.")

            lines.extend(["", f"{'=' * 60}", "END OF REPORT"])
            conn.close()

            with open(path, 'w') as f:
                f.write('\n'.join(lines))

            messagebox.showinfo("Exported", f"Report saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

    def upload_evidence(self):
        """Upload evidence files for the selected case."""
        if not self.selected_case:
            messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select a case to upload evidence for.")
            return

        from tkinter import filedialog
        import shutil
        import os

        case = self.selected_case

        # Create evidence upload dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Upload Evidence - {case['id']}")
        dialog.geometry("700x600")
        dialog.configure(bg=self.colors['light'])
        dialog.transient(self.root)
        dialog.grab_set()

        content = tk.Frame(dialog, bg=self.colors['light'])
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        tk.Label(
            content,
            text=f"Evidence for Case {case['id']}",
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 20))

        # Current evidence list
        tk.Label(
            content,
            text=_t("misconduct.labels.current_evidence"),
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 10))

        # Evidence list frame with scrollbar
        list_frame = tk.Frame(content, bg=self.colors['light'])
        list_frame.pack(fill=tk.BOTH, expand=True)

        evidence_listbox = tk.Listbox(
            list_frame,
            font=('Segoe UI', 10),
            bg=self.colors['light'],
            fg=self.colors['text_dark'],
            selectbackground=self.colors['accent'],
            selectforeground=self.colors['light'],
            relief='flat',
            height=10
        )
        evidence_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        list_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=evidence_listbox.yview)
        evidence_listbox.configure(yscrollcommand=list_scrollbar.set)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load existing evidence
        def load_evidence_list():
            evidence_listbox.delete(0, tk.END)
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, file_name, file_size, uploaded_date
                    FROM academic_misconduct_evidence
                    WHERE case_id = ?
                    ORDER BY uploaded_date DESC
                ''', (case['id'],))
                evidence = cursor.fetchall()
                conn.close()

                for e in evidence:
                    evidence_listbox.insert(tk.END, f"{e['file_name']} ({e['file_size']}) - {e['uploaded_date']}")

                if not evidence:
                    evidence_listbox.insert(tk.END, "No evidence files uploaded yet.")
            except Exception as ex:
                evidence_listbox.insert(tk.END, f"Error loading evidence: {str(ex)}")

        load_evidence_list()

        # Selected files for upload
        selected_files = []

        # File selection display
        tk.Label(
            content,
            text=_t("misconduct.labels.files_to_upload"),
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(20, 5))

        files_text = scrolledtext.ScrolledText(
            content,
            font=('Segoe UI', 9),
            bg=self.colors['light'],
            fg=self.colors['text_dark'],
            relief='flat',
            height=4,
            wrap=tk.WORD,
            state='disabled'
        )
        files_text.pack(fill=tk.X)

        def select_files():
            nonlocal selected_files
            filetypes = [
                ("All Files", "*.*"),
                ("Documents", "*.pdf *.doc *.docx *.txt"),
                ("Images", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("Spreadsheets", "*.xls *.xlsx *.csv"),
            ]
            files = filedialog.askopenfilenames(
                title="Select Evidence Files",
                filetypes=filetypes
            )
            if files:
                selected_files = list(files)
                files_text.configure(state='normal')
                files_text.delete('1.0', tk.END)
                for f in selected_files:
                    size = os.path.getsize(f)
                    size_str = f"{size / 1024:.1f} KB" if size < 1024*1024 else f"{size / (1024*1024):.1f} MB"
                    files_text.insert(tk.END, f"{os.path.basename(f)} ({size_str})\n")
                files_text.configure(state='disabled')

        def upload_files():
            if not selected_files:
                messagebox.showwarning(_t("misconduct.msg_titles.no_files"), "Please select files to upload first.")
                return

            # Create evidence directory if it doesn't exist
            try:
                evidence_dir = DEFAULT_DB_PATH.parent.parent / "evidence" / case['id'].replace('-', '_')
                evidence_dir.mkdir(parents=True, exist_ok=True)
                # Set restrictive permissions on evidence directory
                try:
                    os.chmod(evidence_dir, 0o700)
                except OSError:
                    pass
            except Exception as ex:
                messagebox.showerror(_t("misconduct.msg_titles.error"), f"Could not create evidence directory: {str(ex)}")
                return

            uploaded_count = 0
            skipped_files = []
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                for file_path in selected_files:
                    try:
                        file_name = os.path.basename(file_path)

                        # Read file content for secure validation
                        with open(file_path, 'rb') as f:
                            file_content = f.read()

                        file_size = len(file_content)
                        size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.1f} MB"

                        # Validate file using secure upload handler if available
                        if SECURE_UPLOAD_AVAILABLE and validate_upload:
                            validation = validate_upload(file_name, file_content, category='documents')
                            if not validation['valid']:
                                skipped_files.append(f"{file_name}: {validation['error']}")
                                continue
                            safe_name = validation['safe_filename']
                        else:
                            safe_name = secure_filename(file_name)

                        # Copy file to evidence directory with sanitized name
                        dest_path = evidence_dir / safe_name
                        counter = 1
                        while dest_path.exists():
                            name, ext = os.path.splitext(safe_name)
                            dest_path = evidence_dir / f"{name}_{counter}{ext}"
                            counter += 1

                        shutil.copy2(file_path, dest_path)

                        # Set restrictive permissions on uploaded file
                        try:
                            os.chmod(dest_path, 0o600)
                        except OSError:
                            pass

                        # Compute SHA-256 hash for integrity verification
                        file_hash = compute_file_hash(str(dest_path))

                        # Determine category from extension
                        ext = safe_name.rsplit('.', 1)[-1].lower() if '.' in safe_name else ''
                        cat_map = {
                            'pdf': 'Turnitin Report', 'doc': 'Student Submission',
                            'docx': 'Student Submission', 'txt': 'Other Document',
                            'rtf': 'Other Document', 'odt': 'Student Submission',
                            'png': 'Screenshot', 'jpg': 'Screenshot',
                            'jpeg': 'Screenshot', 'gif': 'Screenshot',
                            'bmp': 'Screenshot',
                            'eml': 'Email Correspondence', 'msg': 'Email Correspondence',
                            'csv': 'Assessment Brief', 'xlsx': 'Assessment Brief',
                            'pptx': 'Student Submission', 'ppt': 'Student Submission',
                        }
                        category = cat_map.get(ext, 'Other Document')

                        # Save to database with hash and category
                        cursor.execute('''
                            INSERT INTO academic_misconduct_evidence
                            (case_id, file_name, file_path, file_size, file_hash,
                             category, uploaded_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (case['id'], safe_name, str(dest_path), size_str,
                              file_hash, category,
                              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                        # Log initial chain-of-custody entry
                        ev_id = cursor.lastrowid
                        uploader = 'System'
                        try:
                            if hasattr(self, 'auth') and self.auth and hasattr(self.auth, 'current_user'):
                                cu = self.auth.current_user
                                if cu:
                                    uploader = cu.get('username', 'System')
                        except Exception:
                            pass
                        cursor.execute('''
                            INSERT INTO academic_misconduct_chain_of_custody
                            (evidence_id, handler, action, details, timestamp)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (ev_id, uploader, 'Collected by Staff',
                              f'Document uploaded: {safe_name}',
                              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                        uploaded_count += 1

                    except Exception as ex:
                        print(f"Error uploading {file_path}: {ex}")
                        skipped_files.append(f"{os.path.basename(file_path)}: {str(ex)}")

                conn.commit()
            finally:
                conn.close()

            # Show results
            if uploaded_count > 0:
                self.add_case_history(case['id'], f"{uploaded_count} evidence file(s) uploaded", 'info')
                msg = f"Successfully uploaded {uploaded_count} file(s)."
                if skipped_files:
                    msg += f"\n\n{len(skipped_files)} file(s) skipped due to security validation:\n"
                    msg += "\n".join(skipped_files[:5])  # Show first 5
                    if len(skipped_files) > 5:
                        msg += f"\n... and {len(skipped_files) - 5} more"
                messagebox.showinfo(_t("misconduct.msg_titles.upload_complete"), msg)
                load_evidence_list()

                # Clear selected files
                selected_files.clear()
                files_text.configure(state='normal')
                files_text.delete('1.0', tk.END)
                files_text.configure(state='disabled')
            elif skipped_files:
                messagebox.showwarning(_t("misconduct.msg_titles.upload_failed"),
                    "All files were rejected due to security validation:\n\n" +
                    "\n".join(skipped_files[:5])
                )
            else:
                messagebox.showerror(_t("misconduct.msg_titles.error"), "No files were uploaded. Please try again.")

        def delete_selected_evidence():
            selection = evidence_listbox.curselection()
            if not selection:
                messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select an evidence file to delete.")
                return

            selected_text = evidence_listbox.get(selection[0])
            if "No evidence" in selected_text or "Error" in selected_text:
                return

            if messagebox.askyesno(_t("misconduct.msg_titles.confirm_delete"), "Are you sure you want to delete this evidence file?"):
                try:
                    # Get the file name from the listbox text
                    file_name = selected_text.split(" (")[0]

                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    try:
                        cursor = conn.cursor()

                        # Get file path for deletion
                        cursor.execute('''
                            SELECT file_path FROM academic_misconduct_evidence
                            WHERE case_id = ? AND file_name = ?
                        ''', (case['id'], file_name))
                        result = cursor.fetchone()

                        if result and result[0]:
                            # Try to delete the physical file
                            try:
                                if os.path.exists(result[0]):
                                    os.remove(result[0])
                            except (OSError, IOError):
                                pass

                        # Delete from database
                        cursor.execute('''
                            DELETE FROM academic_misconduct_evidence
                            WHERE case_id = ? AND file_name = ?
                        ''', (case['id'], file_name))

                        conn.commit()
                    finally:
                        conn.close()

                    self.add_case_history(case['id'], f"Evidence file '{file_name}' deleted", 'warning')
                    load_evidence_list()
                    messagebox.showinfo(_t("misconduct.msg_titles.deleted"), "Evidence file deleted successfully.")

                except Exception as ex:
                    messagebox.showerror(_t("misconduct.msg_titles.error"), f"Failed to delete evidence: {str(ex)}")

        # Buttons
        btn_frame = tk.Frame(content, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.create_button(btn_frame, "Select Files", select_files, 'secondary').pack(side=tk.LEFT, padx=(0, 10))
        self.create_button(btn_frame, "Upload", upload_files, 'primary').pack(side=tk.LEFT, padx=(0, 10))
        self.create_button(btn_frame, "Delete Selected", delete_selected_evidence, 'danger').pack(side=tk.LEFT)
        self.create_button(btn_frame, "Close", dialog.destroy, 'secondary').pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # Evidence integrity verification (from Evidence Organizer)
    # ------------------------------------------------------------------

    def _verify_all_evidence(self):
        """Verify SHA-256 hashes of all evidence files for the selected case."""
        if not self.selected_case:
            messagebox.showwarning("No Case", "Select a case first.")
            return

        try:
            db = self._get_db_path() if hasattr(self, '_get_db_path') else str(DEFAULT_DB_PATH)
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, file_name, file_path, file_hash FROM academic_misconduct_evidence WHERE case_id=?",
                (self.selected_case['id'],)
            ).fetchall()
            conn.close()

            if not rows:
                messagebox.showinfo("File Check", "No documents uploaded for this case.")
                return

            results = []
            for row in rows:
                if not row['file_hash'] or not row['file_path']:
                    results.append(f"  {row['file_name']}: Skipped (no data)")
                    continue
                current = compute_file_hash(row['file_path'])
                if current == row['file_hash']:
                    results.append(f"  {row['file_name']}: Unchanged")
                else:
                    results.append(f"  {row['file_name']}: MODIFIED")

            messagebox.showinfo(
                "File Integrity Check",
                f"Document check for {self.selected_case['id']}:\n\n" + "\n".join(results)
            )
        except Exception as e:
            messagebox.showerror("Error", f"Verification failed: {e}")

    # ------------------------------------------------------------------
    # Chain-of-custody log viewer (from Evidence Organizer)
    # ------------------------------------------------------------------

    def _show_custody_log(self):
        """Show chain-of-custody log for the selected case's evidence."""
        if not self.selected_case:
            messagebox.showwarning("No Case", "Select a case first.")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Document Trail - {self.selected_case['id']}")
        dlg.geometry("750x500")
        dlg.configure(bg=self.colors['light'])
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text=f"Document Handling Trail - {self.selected_case['id']}",
                 font=('Segoe UI', 14, 'bold'), bg=self.colors['light'],
                 fg=self.colors['text_dark']).pack(padx=20, pady=(15, 5))

        tk.Label(dlg, text="A record of who has handled each document and when.",
                 font=('Segoe UI', 9), bg=self.colors['light'],
                 fg=self.colors['text_muted']).pack(padx=20, pady=(0, 10))

        # Treeview
        cols = ('timestamp', 'evidence', 'handler', 'action', 'details')
        tree_frame = tk.Frame(dlg, bg=self.colors['light'])
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        tree = ttk.Treeview(tree_frame, columns=cols, show='headings',
                            yscrollcommand=vsb.set, height=15)
        vsb.config(command=tree.yview)

        for c, w, heading in [
            ('timestamp', 140, 'Date/Time'), ('evidence', 150, 'Document'),
            ('handler', 110, 'Staff Member'), ('action', 130, 'Action Taken'),
            ('details', 200, 'Notes'),
        ]:
            tree.heading(c, text=heading)
            tree.column(c, width=w)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Load data
        try:
            db = self._get_db_path() if hasattr(self, '_get_db_path') else str(DEFAULT_DB_PATH)
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT c.timestamp, e.file_name, c.handler, c.action, c.details
                FROM academic_misconduct_chain_of_custody c
                JOIN academic_misconduct_evidence e ON c.evidence_id = e.id
                WHERE e.case_id = ?
                ORDER BY c.timestamp DESC
            ''', (self.selected_case['id'],)).fetchall()
            conn.close()

            for row in rows:
                tree.insert('', tk.END, values=(
                    row['timestamp'], row['file_name'],
                    row['handler'], row['action'], row['details']
                ))

            if not rows:
                tree.insert('', tk.END, values=('', 'No handling records yet', '', '', ''))
        except Exception as e:
            tree.insert('', tk.END, values=('', f'Error: {e}', '', '', ''))

        def _add_entry():
            from tkinter import simpledialog
            staff = simpledialog.askstring("Staff Member", "Who handled the documents?", parent=dlg)
            if not staff:
                return
            try:
                db2 = self._get_db_path() if hasattr(self, '_get_db_path') else str(DEFAULT_DB_PATH)
                conn2 = sqlite3.connect(db2)
                ev_rows = conn2.execute(
                    "SELECT id, file_name FROM academic_misconduct_evidence WHERE case_id=?",
                    (self.selected_case['id'],)
                ).fetchall()
                conn2.close()
                if not ev_rows:
                    messagebox.showinfo("Info", "No documents to log handling for.")
                    return
                for ev_id, fname in ev_rows:
                    self.add_chain_of_custody(ev_id, staff, "Reviewed by Tutor",
                                             f"Documents reviewed by {staff}")
                self.add_case_history(self.selected_case['id'],
                                     f"Documents reviewed by {staff}", 'info')
                dlg.destroy()
                self._show_custody_log()
            except Exception as ex:
                messagebox.showerror("Error", f"Failed: {ex}")

        btn_frame = tk.Frame(dlg, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        self.create_button(btn_frame, "Record Handling", _add_entry, 'primary').pack(side=tk.LEFT)
        self.create_button(btn_frame, "Close", dlg.destroy, 'secondary').pack(side=tk.RIGHT)
