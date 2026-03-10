"""Evidence management for the Academic Misconduct Panel."""

from ._imports import (
    tk, ttk, messagebox, scrolledtext, _t, datetime,
    sqlite3, DEFAULT_DB_PATH, SECURE_UPLOAD_AVAILABLE, validate_upload, secure_filename,
)


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
        # Clear existing widgets
        for widget in self.evidence_frame.winfo_children():
            widget.destroy()

        tk.Label(
            self.evidence_frame,
            text=_t("misconduct.evidence.title", "Evidence & Documentation"),
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 15))

        # Load evidence from database for selected case
        evidence_items = []
        if self.selected_case:
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT file_name, file_size, uploaded_date
                    FROM academic_misconduct_evidence
                    WHERE case_id = ?
                    ORDER BY uploaded_date DESC
                ''', (self.selected_case['id'],))
                rows = cursor.fetchall()
                conn.close()

                for row in rows:
                    # Determine icon based on file extension
                    name = row['file_name']
                    ext = name.split('.')[-1].lower() if '.' in name else ''
                    if ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp']:
                        icon = "🖼️"
                    elif ext == 'pdf':
                        icon = "📄"
                    elif ext in ['doc', 'docx']:
                        icon = "📝"
                    else:
                        icon = "📎"
                    evidence_items.append((f"{icon} {name}", f"Uploaded {row['uploaded_date']}", row['file_size']))
            except Exception as e:
                print(f"Error loading evidence: {e}")

        if evidence_items:
            for name, date, size in evidence_items:
                item_frame = tk.Frame(self.evidence_frame, bg=self.colors['white'])
                item_frame.pack(fill=tk.X, pady=5)

                tk.Label(
                    item_frame,
                    text=name,
                    font=('Segoe UI', 10),
                    fg=self.colors['text_dark'],
                    bg=self.colors['white']
                ).pack(side=tk.LEFT, padx=15, pady=12)

                tk.Label(
                    item_frame,
                    text=size,
                    font=('Segoe UI', 9),
                    fg=self.colors['text_muted'],
                    bg=self.colors['white']
                ).pack(side=tk.RIGHT, padx=15)

                tk.Label(
                    item_frame,
                    text=date,
                    font=('Segoe UI', 9),
                    fg=self.colors['text_muted'],
                    bg=self.colors['white']
                ).pack(side=tk.RIGHT, padx=15)
        else:
            # Show message when no evidence
            no_evidence_frame = tk.Frame(self.evidence_frame, bg=self.colors['white'])
            no_evidence_frame.pack(fill=tk.X, pady=20)
            evidence_msg = _t("misconduct.evidence.no_evidence", "No evidence uploaded yet") if self.selected_case else _t("misconduct.evidence.select_case", "Select a case to view evidence")
            tk.Label(
                no_evidence_frame,
                text=evidence_msg,
                font=('Segoe UI', 11),
                fg=self.colors['text_muted'],
                bg=self.colors['white']
            ).pack(padx=20, pady=20)

        # Upload button
        btn_frame = tk.Frame(self.evidence_frame, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.create_button(btn_frame, _t("misconduct.buttons.upload_evidence", "Upload Evidence"), self.upload_evidence, 'primary').pack(side=tk.LEFT, padx=(0, 10))
        self.create_button(btn_frame, _t("misconduct.buttons.refresh", "Refresh"), self.refresh_evidence_tab, 'secondary').pack(side=tk.LEFT)

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

                    # Save to database with sanitized filename
                    cursor.execute('''
                        INSERT INTO academic_misconduct_evidence
                        (case_id, file_name, file_path, file_size, uploaded_date)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (case['id'], safe_name, str(dest_path), size_str,
                          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                    uploaded_count += 1

                except Exception as ex:
                    print(f"Error uploading {file_path}: {ex}")
                    skipped_files.append(f"{os.path.basename(file_path)}: {str(ex)}")

            conn.commit()
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
                    f"All files were rejected due to security validation:\n\n" +
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
                    conn.close()

                    self.add_case_history(case['id'], f"Evidence file '{file_name}' deleted", 'warning')
                    load_evidence_list()
                    messagebox.showinfo(_t("misconduct.msg_titles.deleted"), "Evidence file deleted successfully.")

                except Exception as ex:
                    messagebox.showerror(_t("misconduct.msg_titles.error"), f"Failed to delete evidence: {str(ex)}")

        # Buttons
        btn_frame = tk.Frame(content, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.create_button(btn_frame, "📂 Select Files", select_files, 'secondary').pack(side=tk.LEFT, padx=(0, 10))
        self.create_button(btn_frame, "⬆️ Upload", upload_files, 'primary').pack(side=tk.LEFT, padx=(0, 10))
        self.create_button(btn_frame, "🗑️ Delete Selected", delete_selected_evidence, 'danger').pack(side=tk.LEFT)
        self.create_button(btn_frame, "Close", dialog.destroy, 'secondary').pack(side=tk.RIGHT)
