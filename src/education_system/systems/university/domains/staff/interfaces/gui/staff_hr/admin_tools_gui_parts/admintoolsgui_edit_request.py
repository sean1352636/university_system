"""Methods _edit_request through _on_card_select."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import admin_tools_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AdminToolsGUI:
    def _edit_request(self):
        """Edit selected request."""
        selected = self.req_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.please_select_a_request', default="Please select a request"))
            return

        item = self.req_tree.item(selected[0])
        req_id = item["values"][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM interdepartmental_requests WHERE request_id = ?", (req_id,))
                row = cursor.fetchone()

                if row:
                    dialog = tk.Toplevel(self.root)
                    dialog.title(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.windows.edit_request', default="Edit Request"))
                    dialog.geometry("500x400")
                    dialog.transient(self.root)
                    dialog.grab_set()

                    ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.labels.title', default="Title:")).pack(anchor=tk.W, padx=10, pady=5)
                    title_entry = ttk.Entry(dialog)
                    title_entry.pack(fill=tk.X, padx=10)
                    title_entry.insert(0, row[5] or "")

                    ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.labels.description', default="Description:")).pack(anchor=tk.W, padx=10, pady=5)
                    desc_text = tk.Text(dialog, height=5)
                    desc_text.pack(fill=tk.X, padx=10)
                    desc_text.insert(1.0, row[6] or "")

                    ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.labels.priority', default="Priority:")).pack(anchor=tk.W, padx=10, pady=5)
                    priority = ttk.Combobox(dialog, values=["low", "normal", "high", "urgent"], state="readonly")
                    priority.pack(fill=tk.X, padx=10)
                    priority.set(row[7] or "normal")

                    ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.labels.status', default="Status:")).pack(anchor=tk.W, padx=10, pady=5)
                    status = ttk.Combobox(dialog, values=["pending", "in_progress", "completed", "cancelled"], state="readonly")
                    status.pack(fill=tk.X, padx=10)
                    status.set(row[8] or "pending")

                    ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.labels.due_date_yyyy_mm_dd', default="Due Date (YYYY-MM-DD):")).pack(anchor=tk.W, padx=10, pady=5)
                    due_entry = ttk.Entry(dialog)
                    due_entry.pack(fill=tk.X, padx=10)
                    due_entry.insert(0, row[10] or "")

                    def save():
                        try:
                            with transaction() as conn2:
                                conn2.execute("""
                                    UPDATE interdepartmental_requests
                                    SET request_title = ?, request_description = ?,
                                        priority = ?, status = ?, due_date = ?
                                    WHERE request_id = ?
                                """, (
                                    title_entry.get().strip(),
                                    desc_text.get(1.0, tk.END).strip(),
                                    priority.get(),
                                    status.get(),
                                    due_entry.get().strip() or None,
                                    req_id
                                ))

                            log_activity("update", "interdepartmental_request", details={"request_id": req_id})
                            messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.success', default="Success"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.request_updated', default="Request updated"))
                            dialog.destroy()
                            self._load_requests()

                        except Exception as e:
                            messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.error', default="Error"), f"Failed to update: {e}")

                    ttk.Button(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.buttons.save', default="Save"), command=save).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.error', default="Error"), f"Failed to load request: {e}")

    def _cancel_request(self):
        """Cancel selected request."""
        selected = self.req_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.please_select_a_request', default="Please select a request"))
            return

        if not messagebox.askyesno(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.confirm', default="Confirm"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.cancel_this_request', default="Cancel this request?")):
            return

        item = self.req_tree.item(selected[0])
        req_id = item["values"][0]

        try:
            with transaction() as conn:
                conn.execute("UPDATE interdepartmental_requests SET status = 'cancelled' WHERE request_id = ?", (req_id,))

            log_activity("update", "interdepartmental_request", details={"action": "cancelled", "request_id": req_id})
            messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.success', default="Success"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.request_cancelled', default="Request cancelled"))
            self._load_requests()

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.error', default="Error"), f"Failed to cancel: {e}")

    def _respond_request(self, new_status):
        """Respond to a request."""
        selected = self.req_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.please_select_a_request', default="Please select a request"))
            return

        item = self.req_tree.item(selected[0])
        req_id = item["values"][0]
        response = self.req_response.get(1.0, tk.END).strip()

        user_id = self.current_user.get("user_id", "unknown") if self.current_user else "unknown"

        try:
            with transaction() as conn:
                completed_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_status == "completed" else None
                conn.execute("""
                    UPDATE interdepartmental_requests
                    SET status = ?, assigned_to = ?, response = ?, completed_date = ?
                    WHERE request_id = ?
                """, (new_status, user_id, response, completed_date, req_id))

            log_activity("update", "interdepartmental_request", details={"status": new_status, "request_id": req_id})
            messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.success', default="Success"), f"Request marked as {new_status}")
            self.req_response.delete(1.0, tk.END)
            self._load_requests()

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.dialogs.error', default="Error"), f"Failed to update request: {e}")

    def _get_departments(self):
        """Get list of departments."""
        try:
            from education_system.systems.university.domains.staff.infrastructure.database.staff_hr_schemas_all import get_departments
            return get_departments()
        except ImportError:
            return [
                "Computer Science", "Mathematics", "Physics", "Chemistry", "Biology",
                "Engineering", "Business", "Economics", "Psychology", "Sociology",
                "History", "English", "Philosophy", "Art", "Music", "IT Services",
                "Human Resources", "Finance", "Facilities", "Library", "Admissions"
            ]

    def _create_keys_access_tab(self):
        """Create keys and access cards management tab."""
        self.keys_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.keys_tab, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.tabs.keys_access', default="Keys & Access"))

        sub_notebook = ttk.Notebook(self.keys_tab)
        sub_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Access Cards sub-tab
        self._create_access_cards_subtab(sub_notebook)

        # Key Assignments sub-tab
        self._create_key_assignments_subtab(sub_notebook)

    def _create_access_cards_subtab(self, parent):
        """Create access cards management sub-tab."""
        cards_tab = ttk.Frame(parent)
        parent.add(cards_tab, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.tabs.access_cards', default="Access Cards"))

        main_paned = ttk.PanedWindow(cards_tab, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)

        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        # Left: Card list
        list_frame = ttk.LabelFrame(left_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.labels.access_cards', default="Access Cards"))
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Filter
        filter_frame = ttk.Frame(list_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.labels.status', default="Status:")).pack(side=tk.LEFT)
        self.card_status_filter = ttk.Combobox(filter_frame, values=[
            "All", "active", "inactive", "lost", "expired"
        ], state="readonly", width=12)
        self.card_status_filter.set("active")
        self.card_status_filter.pack(side=tk.LEFT, padx=5)
        self.card_status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_access_cards())

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.labels.search', default="Search:")).pack(side=tk.LEFT, padx=(15, 0))
        self.card_search = ttk.Entry(filter_frame, width=20)
        self.card_search.pack(side=tk.LEFT, padx=5)
        self.card_search.bind("<Return>", lambda e: self._load_access_cards())

        ttk.Button(filter_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.buttons.search', default="Search"), command=self._load_access_cards).pack(side=tk.LEFT, padx=2)

        # Treeview
        columns = ("id", "card_number", "user_id", "type", "access_level", "issue_date", "expiry", "status")
        self.cards_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        self.cards_tree.heading("id", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.headings.id', default="ID"))
        self.cards_tree.heading("card_number", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.headings.card', default="Card #"))
        self.cards_tree.heading("user_id", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.headings.user', default="User"))
        self.cards_tree.heading("type", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.headings.type', default="Type"))
        self.cards_tree.heading("access_level", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.headings.access_level', default="Access Level"))
        self.cards_tree.heading("issue_date", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.headings.issued', default="Issued"))
        self.cards_tree.heading("expiry", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.headings.expires', default="Expires"))
        self.cards_tree.heading("status", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.headings.status', default="Status"))

        self.cards_tree.column("id", width=50)
        self.cards_tree.column("card_number", width=100)
        self.cards_tree.column("user_id", width=100)
        self.cards_tree.column("type", width=80)
        self.cards_tree.column("access_level", width=100)
        self.cards_tree.column("issue_date", width=90)
        self.cards_tree.column("expiry", width=90)
        self.cards_tree.column("status", width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.cards_tree.yview)
        self.cards_tree.configure(yscrollcommand=scrollbar.set)

        self.cards_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        self.cards_tree.bind("<<TreeviewSelect>>", self._on_card_select)

        # Tag colors
        self.cards_tree.tag_configure("active", background="#d1e7dd")
        self.cards_tree.tag_configure("inactive", background="#e7e8e9")
        self.cards_tree.tag_configure("lost", background="#f8d7da")
        self.cards_tree.tag_configure("expired", background="#fff3cd")

        # Buttons
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.buttons.issue_new_card', default="Issue New Card"), command=self._issue_card).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.buttons.deactivate', default="Deactivate"), command=self._deactivate_card).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.buttons.report_lost', default="Report Lost"), command=self._report_card_lost).pack(side=tk.LEFT, padx=2)

        # Right: Card details
        detail_frame = ttk.LabelFrame(right_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.labels.card_details', default="Card Details"))
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.card_detail_text = tk.Text(detail_frame, wrap=tk.WORD, height=15)
        self.card_detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.card_detail_text.config(state=tk.DISABLED)

        # Edit card access
        edit_frame = ttk.LabelFrame(right_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.labels.modify_access', default="Modify Access"))
        edit_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(edit_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.labels.access_level', default="Access Level:")).pack(anchor=tk.W, padx=5, pady=2)
        self.new_access_level = ttk.Combobox(edit_frame, values=[
            "basic", "standard", "elevated", "full", "restricted"
        ], state="readonly")
        self.new_access_level.pack(fill=tk.X, padx=5, pady=2)
        self.new_access_level.set("standard")

        ttk.Label(edit_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.labels.buildings_access_comma_separated', default="Buildings Access (comma-separated):")).pack(anchor=tk.W, padx=5, pady=2)
        self.buildings_entry = ttk.Entry(edit_frame)
        self.buildings_entry.pack(fill=tk.X, padx=5, pady=2)

        ttk.Button(edit_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_edit_request.buttons.update_access', default="Update Access"), command=self._update_card_access).pack(pady=5)

        self._load_access_cards()

    def _load_access_cards(self):
        """Load access cards from database."""
        for item in self.cards_tree.get_children():
            self.cards_tree.delete(item)

        status_filter = self.card_status_filter.get()
        search_term = self.card_search.get().strip()

        try:
            with get_connection() as conn:
                query = "SELECT * FROM access_cards WHERE 1=1"
                params = []

                if status_filter != "All":
                    query += " AND status = ?"
                    params.append(status_filter)

                if search_term:
                    query += " AND (card_number LIKE ? OR user_id LIKE ?)"
                    params.extend([f"%{escape_like(search_term)}%", f"%{escape_like(search_term)}%"])

                query += " ORDER BY created_at DESC"

                cursor = conn.cursor()
                cursor.execute(query, params)

                for row in cursor.fetchall():
                    values = (
                        row[0],  # card_id
                        row[1] or "",  # card_number
                        row[2] or "",  # user_id
                        row[3] or "",  # card_type
                        row[4] or "",  # access_level
                        row[6] or "",  # issue_date
                        row[7] or "",  # expiry_date
                        row[8] or "active"  # status
                    )
                    status = row[8] or "active"
                    self.cards_tree.insert("", tk.END, values=values, tags=(status,))

        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    def _on_card_select(self, event):
        """Handle card selection."""
        selected = self.cards_tree.selection()
        if not selected:
            return

        item = self.cards_tree.item(selected[0])
        card_id = item["values"][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM access_cards WHERE card_id = ?", (card_id,))
                row = cursor.fetchone()

                if row:
                    buildings = row[5]
                    if buildings:
                        try:
                            buildings = ", ".join(json.loads(buildings))
                        except (ValueError, json.JSONDecodeError):
                            pass

                    self.card_detail_text.config(state=tk.NORMAL)
                    self.card_detail_text.delete(1.0, tk.END)

                    details = f"""Card ID: {row[0]}
Card Number: {row[1]}
User ID: {row[2]}
Card Type: {row[3]}
Access Level: {row[4]}

Buildings Access: {buildings or 'All'}

Issue Date: {row[6]}
Expiry Date: {row[7]}
Status: {row[8]}

Issued By: {row[9]}
Notes: {row[10] or 'None'}
Created: {row[11]}
"""
                    self.card_detail_text.insert(1.0, details)
                    self.card_detail_text.config(state=tk.DISABLED)

                    # Update edit fields
                    self.new_access_level.set(row[4] or "standard")
                    self.buildings_entry.delete(0, tk.END)
                    if buildings:
                        self.buildings_entry.insert(0, buildings)

        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
