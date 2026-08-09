"""Methods __init__ through _view_document."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import admin_tools_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AdminToolsGUI:
    def __init__(self, root, auth, parent_notebook=None):
        """Initialize the Admin Tools GUI.

        Args:
            root: The root Tkinter window
            auth: Authentication instance
            parent_notebook: Optional parent notebook to embed in
        """
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth else None

        if parent_notebook:
            self.tab = ttk.Frame(parent_notebook)
            parent_notebook.add(self.tab, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.tabs.admin_tools', default="Admin Tools"))
            self._create_content(self.tab)
        else:
            self.root.title(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.windows.administrative_tools', default="Administrative Tools"))
            self.root.geometry("1400x800")
            self._create_content(self.root)

    def _create_content(self, parent):
        """Create the main content with tabbed interface."""
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_document_approvals_tab()
        self._create_requests_tab()
        self._create_keys_access_tab()
        self._create_visitors_tab()

    def _create_document_approvals_tab(self):
        """Create document approvals tab."""
        self.doc_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.doc_tab, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.tabs.document_approvals', default="Document Approvals"))

        main_paned = ttk.PanedWindow(self.doc_tab, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)

        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        # Left: Document list
        list_label = ttk.LabelFrame(left_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.labels.document_approval_requests', default="Document Approval Requests"))
        list_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Filter frame
        filter_frame = ttk.Frame(list_label)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.labels.status', default="Status:")).pack(side=tk.LEFT)
        self.doc_status_filter = ttk.Combobox(filter_frame, values=[
            "All", "pending", "in_review", "approved", "rejected"
        ], state="readonly", width=15)
        self.doc_status_filter.set("pending")
        self.doc_status_filter.pack(side=tk.LEFT, padx=5)
        self.doc_status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_document_approvals())

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.labels.type', default="Type:")).pack(side=tk.LEFT, padx=(15, 0))
        self.doc_type_filter = ttk.Combobox(filter_frame, values=[
            "All", "policy", "budget", "contract", "report", "proposal", "memo", "other"
        ], state="readonly", width=15)
        self.doc_type_filter.set("All")
        self.doc_type_filter.pack(side=tk.LEFT, padx=5)
        self.doc_type_filter.bind("<<ComboboxSelected>>", lambda e: self._load_document_approvals())

        ttk.Button(filter_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.buttons.refresh', default="Refresh"), command=self._load_document_approvals).pack(side=tk.RIGHT)

        # Treeview
        columns = ("id", "title", "type", "submitted_by", "date", "step", "status")
        self.doc_tree = ttk.Treeview(list_label, columns=columns, show="headings", height=15)

        self.doc_tree.heading("id", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.headings.id', default="ID"))
        self.doc_tree.heading("title", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.headings.document_title', default="Document Title"))
        self.doc_tree.heading("type", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.headings.type', default="Type"))
        self.doc_tree.heading("submitted_by", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.headings.submitted_by', default="Submitted By"))
        self.doc_tree.heading("date", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.headings.date', default="Date"))
        self.doc_tree.heading("step", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.headings.step', default="Step"))
        self.doc_tree.heading("status", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.headings.status', default="Status"))

        self.doc_tree.column("id", width=50)
        self.doc_tree.column("title", width=200)
        self.doc_tree.column("type", width=100)
        self.doc_tree.column("submitted_by", width=120)
        self.doc_tree.column("date", width=100)
        self.doc_tree.column("step", width=60)
        self.doc_tree.column("status", width=100)

        scrollbar = ttk.Scrollbar(list_label, orient=tk.VERTICAL, command=self.doc_tree.yview)
        self.doc_tree.configure(yscrollcommand=scrollbar.set)

        self.doc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        self.doc_tree.bind("<<TreeviewSelect>>", self._on_doc_select)

        # Tag colors
        self.doc_tree.tag_configure("pending", background="#fff3cd")
        self.doc_tree.tag_configure("in_review", background="#cfe2ff")
        self.doc_tree.tag_configure("approved", background="#d1e7dd")
        self.doc_tree.tag_configure("rejected", background="#f8d7da")

        # Button frame
        btn_frame = ttk.Frame(list_label)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.buttons.submit_new_document', default="Submit New Document"), command=self._submit_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.buttons.view_document', default="View Document"), command=self._view_document).pack(side=tk.LEFT, padx=2)

        # Right: Document details and approval
        detail_frame = ttk.LabelFrame(right_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.labels.document_details', default="Document Details"))
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.doc_detail_text = tk.Text(detail_frame, wrap=tk.WORD, height=15)
        self.doc_detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.doc_detail_text.config(state=tk.DISABLED)

        # Approval actions
        action_frame = ttk.LabelFrame(right_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.labels.approval_actions', default="Approval Actions"))
        action_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(action_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.labels.comments', default="Comments:")).pack(anchor=tk.W, padx=5, pady=2)
        self.approval_comments = tk.Text(action_frame, height=4)
        self.approval_comments.pack(fill=tk.X, padx=5, pady=2)

        btn_action_frame = ttk.Frame(action_frame)
        btn_action_frame.pack(fill=tk.X, padx=5, pady=5)

        self.approve_btn = ttk.Button(btn_action_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.buttons.approve', default="Approve"), command=lambda: self._process_approval("approved"))
        self.approve_btn.pack(side=tk.LEFT, padx=2)

        self.reject_btn = ttk.Button(btn_action_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.buttons.reject', default="Reject"), command=lambda: self._process_approval("rejected"))
        self.reject_btn.pack(side=tk.LEFT, padx=2)

        self.forward_btn = ttk.Button(btn_action_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.buttons.forward_to_next', default="Forward to Next"), command=self._forward_approval)
        self.forward_btn.pack(side=tk.LEFT, padx=2)

        # History
        history_frame = ttk.LabelFrame(right_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.labels.approval_history', default="Approval History"))
        history_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.history_tree = ttk.Treeview(history_frame, columns=("date", "action", "by", "comments"), show="headings", height=5)
        self.history_tree.heading("date", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.headings.date', default="Date"))
        self.history_tree.heading("action", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.headings.action', default="Action"))
        self.history_tree.heading("by", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.headings.by', default="By"))
        self.history_tree.heading("comments", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.headings.comments', default="Comments"))

        self.history_tree.column("date", width=100)
        self.history_tree.column("action", width=80)
        self.history_tree.column("by", width=100)
        self.history_tree.column("comments", width=150)

        self.history_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._load_document_approvals()

    def _load_document_approvals(self):
        """Load document approvals from database."""
        for item in self.doc_tree.get_children():
            self.doc_tree.delete(item)

        status_filter = self.doc_status_filter.get()
        type_filter = self.doc_type_filter.get()

        try:
            with get_connection() as conn:
                query = "SELECT * FROM document_approvals WHERE 1=1"
                params = []

                if status_filter != "All":
                    query += " AND status = ?"
                    params.append(status_filter)

                if type_filter != "All":
                    query += " AND document_type = ?"
                    params.append(type_filter)

                query += " ORDER BY submitted_date DESC"

                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()

                for row in rows:
                    values = (
                        row[0],  # approval_id
                        row[2] or "Untitled",  # document_title
                        row[1] or "",  # document_type
                        row[4] or "",  # submitted_by
                        row[5][:10] if row[5] else "",  # submitted_date
                        f"{row[7] or 1}",  # current_step
                        row[8] or "pending"  # status
                    )
                    status = row[8] or "pending"
                    self.doc_tree.insert("", tk.END, values=values, tags=(status,))

        except Exception:
            pass  # Table may not exist yet

    def _on_doc_select(self, event):
        """Handle document selection."""
        selected = self.doc_tree.selection()
        if not selected:
            return

        item = self.doc_tree.item(selected[0])
        doc_id = item["values"][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM document_approvals WHERE approval_id = ?", (doc_id,))
                row = cursor.fetchone()

                if row:
                    self.doc_detail_text.config(state=tk.NORMAL)
                    self.doc_detail_text.delete(1.0, tk.END)

                    details = f"""Document ID: {row[0]}
Type: {row[1]}
Title: {row[2]}
File Path: {row[3] or 'N/A'}

Submitted By: {row[4]}
Submitted Date: {row[5]}

Current Approver: {row[6] or 'N/A'}
Current Step: {row[7]}
Status: {row[8]}

Approval Chain: {row[9] or 'N/A'}
Comments: {row[10] or 'None'}
"""
                    self.doc_detail_text.insert(1.0, details)
                    self.doc_detail_text.config(state=tk.DISABLED)

                    # Load history
                    self._load_approval_history(doc_id)

        except Exception:
            pass

    def _load_approval_history(self, doc_id):
        """Load approval history for a document."""
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT action_date, action, action_by, comments
                    FROM document_approval_history
                    WHERE approval_id = ?
                    ORDER BY action_date DESC
                """, (doc_id,))

                for row in cursor.fetchall():
                    values = (
                        row[0][:16] if row[0] else "",
                        row[1] or "",
                        row[2] or "",
                        row[3] or ""
                    )
                    self.history_tree.insert("", tk.END, values=values)
        except Exception:
            pass

    def _submit_document(self):
        """Submit a new document for approval."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.windows.submit_document_for_approval', default="Submit Document for Approval"))
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.labels.document_type', default="Document Type:")).pack(anchor=tk.W, padx=10, pady=5)
        doc_type = ttk.Combobox(dialog, values=[
            "policy", "budget", "contract", "report", "proposal", "memo", "other"
        ], state="readonly")
        doc_type.pack(fill=tk.X, padx=10)
        doc_type.set("memo")

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.labels.document_title', default="Document Title:")).pack(anchor=tk.W, padx=10, pady=5)
        title_entry = ttk.Entry(dialog)
        title_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.labels.file_path_optional', default="File Path (optional):")).pack(anchor=tk.W, padx=10, pady=5)
        file_frame = ttk.Frame(dialog)
        file_frame.pack(fill=tk.X, padx=10)
        file_entry = ttk.Entry(file_frame)
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def browse_file():
            path = filedialog.askopenfilename()
            if path:
                file_entry.delete(0, tk.END)
                file_entry.insert(0, path)

        ttk.Button(file_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.buttons.browse', default="Browse"), command=browse_file).pack(side=tk.RIGHT, padx=5)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.labels.approval_chain_comma_separated_user_ids', default="Approval Chain (comma-separated user IDs):")).pack(anchor=tk.W, padx=10, pady=5)
        chain_entry = ttk.Entry(dialog)
        chain_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.labels.comments', default="Comments:")).pack(anchor=tk.W, padx=10, pady=5)
        comments_text = tk.Text(dialog, height=5)
        comments_text.pack(fill=tk.X, padx=10, pady=5)

        def submit():
            title = title_entry.get().strip()
            if not title:
                messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.dialogs.error', default="Error"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.dialogs.document_title_is_required', default="Document title is required"))
                return

            chain = chain_entry.get().strip()
            chain_list = [c.strip() for c in chain.split(",") if c.strip()] if chain else []
            first_approver = chain_list[0] if chain_list else None

            user_id = self.current_user.get("user_id", "unknown") if self.current_user else "unknown"

            try:
                with transaction() as conn:
                    conn.execute("""
                        INSERT INTO document_approvals
                        (document_type, document_title, document_path, submitted_by,
                         submitted_date, current_approver, approval_chain, current_step, status, comments)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        doc_type.get(),
                        title,
                        file_entry.get().strip() or None,
                        user_id,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        first_approver,
                        json.dumps(chain_list) if chain_list else None,
                        1,
                        "pending",
                        comments_text.get(1.0, tk.END).strip() or None
                    ))

                log_activity("create", "document_approval", user_id=user_id, details={"title": title})
                messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.dialogs.success', default="Success"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.dialogs.document_submitted_for_approval', default="Document submitted for approval"))
                dialog.destroy()
                self._load_document_approvals()

            except Exception as e:
                messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.dialogs.error', default="Error"), f"Failed to submit document: {e}")

        ttk.Button(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.buttons.submit', default="Submit"), command=submit).pack(pady=10)

    def _view_document(self):
        """View the selected document file."""
        selected = self.doc_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.dialogs.please_select_a_document', default="Please select a document"))
            return

        item = self.doc_tree.item(selected[0])
        doc_id = item["values"][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT document_path FROM document_approvals WHERE approval_id = ?", (doc_id,))
                row = cursor.fetchone()

                if row and row[0]:
                    path = row[0]
                    if os.path.exists(path):
                        import subprocess
                        if os.name == 'nt':
                            os.startfile(path)
                        elif os.name == 'posix':
                            subprocess.run(['xdg-open', path], check=False)
                    else:
                        messagebox.showwarning(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.dialogs.warning', default="Warning"), f"File not found: {path}")
                else:
                    messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.dialogs.info', default="Info"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.dialogs.no_file_attached_to_this_document', default="No file attached to this document"))

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_init.dialogs.error', default="Error"), f"Failed to open document: {e}")
