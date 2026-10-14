"""Methods _process_approval through _new_request."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import admin_tools_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AdminToolsGUI:
    def _process_approval(self, action):
        """Process approval or rejection."""
        selected = self.doc_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.dialogs.please_select_a_document', default="Please select a document"))
            return

        item = self.doc_tree.item(selected[0])
        doc_id = item["values"][0]
        comments = self.approval_comments.get(1.0, tk.END).strip()

        user_id = self.current_user.get("user_id", "unknown") if self.current_user else "unknown"

        try:
            with transaction() as conn:
                # Update document status
                conn.execute("""
                    UPDATE document_approvals
                    SET status = ?, completed_date = ?
                    WHERE approval_id = ?
                """, (action, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), doc_id))

                # Add to history
                conn.execute("""
                    INSERT INTO document_approval_history
                    (approval_id, action, action_by, action_date, comments)
                    VALUES (?, ?, ?, ?, ?)
                """, (doc_id, action, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), comments))

            log_activity("update", "document_approval", approval_id=doc_id, details={"action": action})
            messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.dialogs.success', default="Success"), f"Document {action}")
            self.approval_comments.delete(1.0, tk.END)
            self._load_document_approvals()

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.dialogs.error', default="Error"), f"Failed to process approval: {e}")

    def _forward_approval(self):
        """Forward document to next approver in chain."""
        selected = self.doc_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.dialogs.please_select_a_document', default="Please select a document"))
            return

        item = self.doc_tree.item(selected[0])
        doc_id = item["values"][0]
        comments = self.approval_comments.get(1.0, tk.END).strip()

        user_id = self.current_user.get("user_id", "unknown") if self.current_user else "unknown"

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT approval_chain, current_step FROM document_approvals WHERE approval_id = ?", (doc_id,))
                row = cursor.fetchone()

                if row:
                    chain = json.loads(row[0]) if row[0] else []
                    current_step = row[1] or 1

                    if current_step < len(chain):
                        new_step = current_step + 1
                        next_approver = chain[new_step - 1] if new_step <= len(chain) else None

                        with transaction() as conn2:
                            conn2.execute("""
                                UPDATE document_approvals
                                SET current_step = ?, current_approver = ?, status = 'in_review'
                                WHERE approval_id = ?
                            """, (new_step, next_approver, doc_id))

                            conn2.execute("""
                                INSERT INTO document_approval_history
                                (approval_id, action, action_by, action_date, comments)
                                VALUES (?, ?, ?, ?, ?)
                            """, (doc_id, "forwarded", user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), comments))

                        log_activity("update", "document_approval", approval_id=doc_id, details={"action": "forwarded"})
                        messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.dialogs.success', default="Success"), f"Document forwarded to step {new_step}")
                        self.approval_comments.delete(1.0, tk.END)
                        self._load_document_approvals()
                    else:
                        messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.dialogs.info', default="Info"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.dialogs.this_is_the_final_approval_step_use_approve_or_reject', default="This is the final approval step. Use Approve or Reject."))

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.dialogs.error', default="Error"), f"Failed to forward: {e}")

    def _create_requests_tab(self):
        """Create interdepartmental requests tab."""
        self.req_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.req_tab, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.tabs.requests', default="Requests"))

        main_paned = ttk.PanedWindow(self.req_tab, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)

        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        # Left: Request list
        list_frame = ttk.LabelFrame(left_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.labels.interdepartmental_requests', default="Interdepartmental Requests"))
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Filter
        filter_frame = ttk.Frame(list_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.labels.status', default="Status:")).pack(side=tk.LEFT)
        self.req_status_filter = ttk.Combobox(filter_frame, values=[
            "All", "pending", "in_progress", "completed", "cancelled"
        ], state="readonly", width=15)
        self.req_status_filter.set("All")
        self.req_status_filter.pack(side=tk.LEFT, padx=5)
        self.req_status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_requests())

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.labels.priority', default="Priority:")).pack(side=tk.LEFT, padx=(15, 0))
        self.req_priority_filter = ttk.Combobox(filter_frame, values=[
            "All", "urgent", "high", "normal", "low"
        ], state="readonly", width=12)
        self.req_priority_filter.set("All")
        self.req_priority_filter.pack(side=tk.LEFT, padx=5)
        self.req_priority_filter.bind("<<ComboboxSelected>>", lambda e: self._load_requests())

        ttk.Button(filter_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.buttons.refresh', default="Refresh"), command=self._load_requests).pack(side=tk.RIGHT)

        # Treeview
        columns = ("id", "type", "title", "from_dept", "to_dept", "priority", "status", "due")
        self.req_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        self.req_tree.heading("id", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.headings.id', default="ID"))
        self.req_tree.heading("type", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.headings.type', default="Type"))
        self.req_tree.heading("title", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.headings.title', default="Title"))
        self.req_tree.heading("from_dept", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.headings.from', default="From"))
        self.req_tree.heading("to_dept", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.headings.to', default="To"))
        self.req_tree.heading("priority", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.headings.priority', default="Priority"))
        self.req_tree.heading("status", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.headings.status', default="Status"))
        self.req_tree.heading("due", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.headings.due_date', default="Due Date"))

        self.req_tree.column("id", width=50)
        self.req_tree.column("type", width=100)
        self.req_tree.column("title", width=180)
        self.req_tree.column("from_dept", width=100)
        self.req_tree.column("to_dept", width=100)
        self.req_tree.column("priority", width=80)
        self.req_tree.column("status", width=90)
        self.req_tree.column("due", width=90)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.req_tree.yview)
        self.req_tree.configure(yscrollcommand=scrollbar.set)

        self.req_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        self.req_tree.bind("<<TreeviewSelect>>", self._on_request_select)

        # Tag colors
        self.req_tree.tag_configure("urgent", background="#f8d7da")
        self.req_tree.tag_configure("high", background="#fff3cd")
        self.req_tree.tag_configure("normal", background="#ffffff")
        self.req_tree.tag_configure("low", background="#e7f1ff")

        # Buttons
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.buttons.new_request', default="New Request"), command=self._new_request).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.buttons.edit', default="Edit"), command=self._edit_request).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.buttons.cancel_request', default="Cancel Request"), command=self._cancel_request).pack(side=tk.LEFT, padx=2)

        # Right: Request details
        detail_frame = ttk.LabelFrame(right_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.labels.request_details', default="Request Details"))
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.req_detail_text = tk.Text(detail_frame, wrap=tk.WORD, height=15)
        self.req_detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.req_detail_text.config(state=tk.DISABLED)

        # Response section
        response_frame = ttk.LabelFrame(right_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.labels.response', default="Response"))
        response_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(response_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.labels.response_variant_2', default="Response:")).pack(anchor=tk.W, padx=5, pady=2)
        self.req_response = tk.Text(response_frame, height=4)
        self.req_response.pack(fill=tk.X, padx=5, pady=2)

        resp_btn_frame = ttk.Frame(response_frame)
        resp_btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(resp_btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.buttons.accept', default="Accept"), command=lambda: self._respond_request("in_progress")).pack(side=tk.LEFT, padx=2)
        ttk.Button(resp_btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.buttons.complete', default="Complete"), command=lambda: self._respond_request("completed")).pack(side=tk.LEFT, padx=2)

        self._load_requests()

    def _load_requests(self):
        """Load interdepartmental requests."""
        for item in self.req_tree.get_children():
            self.req_tree.delete(item)

        status_filter = self.req_status_filter.get()
        priority_filter = self.req_priority_filter.get()

        try:
            with get_connection() as conn:
                query = "SELECT * FROM interdepartmental_requests WHERE 1=1"
                params = []

                if status_filter != "All":
                    query += " AND status = ?"
                    params.append(status_filter)

                if priority_filter != "All":
                    query += " AND priority = ?"
                    params.append(priority_filter)

                query += " ORDER BY created_at DESC"

                cursor = conn.cursor()
                cursor.execute(query, params)

                for row in cursor.fetchall():
                    values = (
                        row[0],  # request_id
                        row[1] or "",  # request_type
                        row[5] or "Untitled",  # request_title
                        row[2] or "",  # from_department
                        row[3] or "",  # to_department
                        row[7] or "normal",  # priority
                        row[8] or "pending",  # status
                        row[10] or ""  # due_date
                    )
                    priority = row[7] or "normal"
                    self.req_tree.insert("", tk.END, values=values, tags=(priority,))

        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    def _on_request_select(self, event):
        """Handle request selection."""
        selected = self.req_tree.selection()
        if not selected:
            return

        item = self.req_tree.item(selected[0])
        req_id = item["values"][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM interdepartmental_requests WHERE request_id = ?", (req_id,))
                row = cursor.fetchone()

                if row:
                    self.req_detail_text.config(state=tk.NORMAL)
                    self.req_detail_text.delete(1.0, tk.END)

                    details = f"""Request ID: {row[0]}
Type: {row[1]}
From Department: {row[2]}
To Department: {row[3]}
Requested By: {row[4]}

Title: {row[5]}
Description:
{row[6] or 'No description'}

Priority: {row[7]}
Status: {row[8]}
Assigned To: {row[9] or 'Unassigned'}
Due Date: {row[10] or 'Not set'}

Response: {row[12] or 'No response yet'}
Created: {row[13]}
"""
                    self.req_detail_text.insert(1.0, details)
                    self.req_detail_text.config(state=tk.DISABLED)

        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    def _new_request(self):
        """Create a new interdepartmental request."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.windows.new_interdepartmental_request', default="New Interdepartmental Request"))
        dialog.geometry("500x500")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.labels.request_type', default="Request Type:")).pack(anchor=tk.W, padx=10, pady=5)
        type_combo = ttk.Combobox(dialog, values=[
            "information", "support", "resource", "approval", "collaboration", "other"
        ], state="readonly")
        type_combo.pack(fill=tk.X, padx=10)
        type_combo.set("information")

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.labels.from_department', default="From Department:")).pack(anchor=tk.W, padx=10, pady=5)
        from_dept = ttk.Combobox(dialog, values=self._get_departments())
        from_dept.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.labels.to_department', default="To Department:")).pack(anchor=tk.W, padx=10, pady=5)
        to_dept = ttk.Combobox(dialog, values=self._get_departments())
        to_dept.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.labels.title', default="Title:")).pack(anchor=tk.W, padx=10, pady=5)
        title_entry = ttk.Entry(dialog)
        title_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.labels.description', default="Description:")).pack(anchor=tk.W, padx=10, pady=5)
        desc_text = tk.Text(dialog, height=5)
        desc_text.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.labels.priority', default="Priority:")).pack(anchor=tk.W, padx=10, pady=5)
        priority = ttk.Combobox(dialog, values=["low", "normal", "high", "urgent"], state="readonly")
        priority.pack(fill=tk.X, padx=10)
        priority.set("normal")

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.labels.due_date_yyyy_mm_dd', default="Due Date (YYYY-MM-DD):")).pack(anchor=tk.W, padx=10, pady=5)
        due_entry = ttk.Entry(dialog)
        due_entry.pack(fill=tk.X, padx=10)

        def submit():
            title = title_entry.get().strip()
            if not title:
                messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.dialogs.error', default="Error"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.dialogs.title_is_required', default="Title is required"))
                return

            user_id = self.current_user.get("user_id", "unknown") if self.current_user else "unknown"

            try:
                with transaction() as conn:
                    conn.execute("""
                        INSERT INTO interdepartmental_requests
                        (request_type, from_department, to_department, requested_by,
                         request_title, request_description, priority, status, due_date, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        type_combo.get(),
                        from_dept.get(),
                        to_dept.get(),
                        user_id,
                        title,
                        desc_text.get(1.0, tk.END).strip(),
                        priority.get(),
                        "pending",
                        due_entry.get().strip() or None,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))

                log_activity("create", "interdepartmental_request", user_id=user_id, details={"title": title})
                messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.dialogs.success', default="Success"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.dialogs.request_submitted', default="Request submitted"))
                dialog.destroy()
                self._load_requests()

            except Exception as e:
                messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.dialogs.error', default="Error"), f"Failed to create request: {e}")

        ttk.Button(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_process_approval.buttons.submit', default="Submit"), command=submit).pack(pady=10)
