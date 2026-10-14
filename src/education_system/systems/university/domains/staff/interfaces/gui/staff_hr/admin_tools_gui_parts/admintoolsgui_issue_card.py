"""Methods _issue_card through _assign_key."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import admin_tools_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AdminToolsGUI:
    def _issue_card(self):
        """Issue a new access card."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.windows.issue_new_access_card', default="Issue New Access Card"))
        dialog.geometry("450x500")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.labels.card_number', default="Card Number:")).pack(anchor=tk.W, padx=10, pady=5)
        card_num = ttk.Entry(dialog)
        card_num.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.labels.user_id', default="User ID:")).pack(anchor=tk.W, padx=10, pady=5)
        user_id = ttk.Entry(dialog)
        user_id.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.labels.card_type', default="Card Type:")).pack(anchor=tk.W, padx=10, pady=5)
        card_type = ttk.Combobox(dialog, values=["staff", "contractor", "visitor", "temporary"], state="readonly")
        card_type.pack(fill=tk.X, padx=10)
        card_type.set("staff")

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.labels.access_level', default="Access Level:")).pack(anchor=tk.W, padx=10, pady=5)
        access_level = ttk.Combobox(dialog, values=["basic", "standard", "elevated", "full", "restricted"], state="readonly")
        access_level.pack(fill=tk.X, padx=10)
        access_level.set("standard")

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.labels.buildings_access_comma_separated', default="Buildings Access (comma-separated):")).pack(anchor=tk.W, padx=10, pady=5)
        buildings = ttk.Entry(dialog)
        buildings.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.labels.expiry_date_yyyy_mm_dd', default="Expiry Date (YYYY-MM-DD):")).pack(anchor=tk.W, padx=10, pady=5)
        expiry = ttk.Entry(dialog)
        expiry.pack(fill=tk.X, padx=10)
        # Default to 1 year from now
        default_expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        expiry.insert(0, default_expiry)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.labels.notes', default="Notes:")).pack(anchor=tk.W, padx=10, pady=5)
        notes = tk.Text(dialog, height=4)
        notes.pack(fill=tk.X, padx=10)

        def issue():
            card_number = card_num.get().strip()
            if not card_number:
                messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.error', default="Error"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.card_number_is_required', default="Card number is required"))
                return

            issuer = self.current_user.get("user_id", "unknown") if self.current_user else "unknown"
            buildings_list = [b.strip() for b in buildings.get().split(",") if b.strip()]

            try:
                with transaction() as conn:
                    conn.execute("""
                        INSERT INTO access_cards
                        (card_number, user_id, card_type, access_level, buildings_access,
                         issue_date, expiry_date, status, issued_by, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        card_number,
                        user_id.get().strip(),
                        card_type.get(),
                        access_level.get(),
                        json.dumps(buildings_list) if buildings_list else None,
                        datetime.now().strftime("%Y-%m-%d"),
                        expiry.get().strip() or None,
                        "active",
                        issuer,
                        notes.get(1.0, tk.END).strip() or None,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))

                log_activity("create", "access_card", user_id=issuer, details={"card_number": card_number})
                messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.success', default="Success"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.access_card_issued', default="Access card issued"))
                dialog.destroy()
                self._load_access_cards()

            except Exception as e:
                messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.error', default="Error"), f"Failed to issue card: {e}")

        ttk.Button(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.buttons.issue_card', default="Issue Card"), command=issue).pack(pady=10)

    def _deactivate_card(self):
        """Deactivate selected card."""
        selected = self.cards_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.please_select_a_card', default="Please select a card"))
            return

        if not messagebox.askyesno(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.confirm', default="Confirm"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.deactivate_this_card', default="Deactivate this card?")):
            return

        item = self.cards_tree.item(selected[0])
        card_id = item["values"][0]

        try:
            with transaction() as conn:
                conn.execute("UPDATE access_cards SET status = 'inactive' WHERE card_id = ?", (card_id,))

            log_activity("update", "access_card", card_id=card_id, details={"action": "deactivated"})
            messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.success', default="Success"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.card_deactivated', default="Card deactivated"))
            self._load_access_cards()

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.error', default="Error"), f"Failed to deactivate: {e}")

    def _report_card_lost(self):
        """Report card as lost."""
        selected = self.cards_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.please_select_a_card', default="Please select a card"))
            return

        if not messagebox.askyesno(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.confirm', default="Confirm"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.report_this_card_as_lost_it_will_be_deactivated', default="Report this card as lost? It will be deactivated.")):
            return

        item = self.cards_tree.item(selected[0])
        card_id = item["values"][0]

        try:
            with transaction() as conn:
                conn.execute("UPDATE access_cards SET status = 'lost' WHERE card_id = ?", (card_id,))

            log_activity("update", "access_card", card_id=card_id, details={"action": "reported_lost"})
            messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.success', default="Success"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.card_reported_as_lost_and_deactivated', default="Card reported as lost and deactivated"))
            self._load_access_cards()

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.error', default="Error"), f"Failed to update: {e}")

    def _update_card_access(self):
        """Update card access level and buildings."""
        selected = self.cards_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.please_select_a_card', default="Please select a card"))
            return

        item = self.cards_tree.item(selected[0])
        card_id = item["values"][0]

        buildings_list = [b.strip() for b in self.buildings_entry.get().split(",") if b.strip()]

        try:
            with transaction() as conn:
                conn.execute("""
                    UPDATE access_cards
                    SET access_level = ?, buildings_access = ?
                    WHERE card_id = ?
                """, (
                    self.new_access_level.get(),
                    json.dumps(buildings_list) if buildings_list else None,
                    card_id
                ))

            log_activity("update", "access_card", card_id=card_id, details={"access_level": self.new_access_level.get()})
            messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.success', default="Success"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.card_access_updated', default="Card access updated"))
            self._load_access_cards()

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.error', default="Error"), f"Failed to update: {e}")

    def _create_key_assignments_subtab(self, parent):
        """Create key assignments sub-tab."""
        keys_tab = ttk.Frame(parent)
        parent.add(keys_tab, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.tabs.key_assignments', default="Key Assignments"))

        main_paned = ttk.PanedWindow(keys_tab, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)

        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        # Left: Key list
        list_frame = ttk.LabelFrame(left_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.labels.key_assignments', default="Key Assignments"))
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Filter
        filter_frame = ttk.Frame(list_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.labels.status', default="Status:")).pack(side=tk.LEFT)
        self.key_status_filter = ttk.Combobox(filter_frame, values=[
            "All", "assigned", "returned", "lost"
        ], state="readonly", width=12)
        self.key_status_filter.set("assigned")
        self.key_status_filter.pack(side=tk.LEFT, padx=5)
        self.key_status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_keys())

        ttk.Button(filter_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.buttons.refresh', default="Refresh"), command=self._load_keys).pack(side=tk.RIGHT)

        # Treeview
        columns = ("id", "key_number", "type", "room", "assigned_to", "assigned_date", "status")
        self.keys_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        self.keys_tree.heading("id", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.headings.id', default="ID"))
        self.keys_tree.heading("key_number", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.headings.key', default="Key #"))
        self.keys_tree.heading("type", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.headings.type', default="Type"))
        self.keys_tree.heading("room", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.headings.room_location', default="Room/Location"))
        self.keys_tree.heading("assigned_to", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.headings.assigned_to', default="Assigned To"))
        self.keys_tree.heading("assigned_date", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.headings.assigned', default="Assigned"))
        self.keys_tree.heading("status", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.headings.status', default="Status"))

        self.keys_tree.column("id", width=50)
        self.keys_tree.column("key_number", width=100)
        self.keys_tree.column("type", width=80)
        self.keys_tree.column("room", width=120)
        self.keys_tree.column("assigned_to", width=120)
        self.keys_tree.column("assigned_date", width=100)
        self.keys_tree.column("status", width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.keys_tree.yview)
        self.keys_tree.configure(yscrollcommand=scrollbar.set)

        self.keys_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        self.keys_tree.bind("<<TreeviewSelect>>", self._on_key_select)

        # Tag colors
        self.keys_tree.tag_configure("assigned", background="#cfe2ff")
        self.keys_tree.tag_configure("returned", background="#d1e7dd")
        self.keys_tree.tag_configure("lost", background="#f8d7da")

        # Buttons
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.buttons.assign_key', default="Assign Key"), command=self._assign_key).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.buttons.return_key', default="Return Key"), command=self._return_key).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.buttons.report_lost', default="Report Lost"), command=self._report_key_lost).pack(side=tk.LEFT, padx=2)

        # Right: Key details
        detail_frame = ttk.LabelFrame(right_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.labels.key_details', default="Key Details"))
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.key_detail_text = tk.Text(detail_frame, wrap=tk.WORD)
        self.key_detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.key_detail_text.config(state=tk.DISABLED)

        self._load_keys()

    def _load_keys(self):
        """Load key assignments from database."""
        for item in self.keys_tree.get_children():
            self.keys_tree.delete(item)

        status_filter = self.key_status_filter.get()

        try:
            with get_connection() as conn:
                query = "SELECT * FROM key_assignments WHERE 1=1"
                params = []

                if status_filter != "All":
                    query += " AND status = ?"
                    params.append(status_filter)

                query += " ORDER BY created_at DESC"

                cursor = conn.cursor()
                cursor.execute(query, params)

                for row in cursor.fetchall():
                    values = (
                        row[0],  # assignment_id
                        row[1] or "",  # key_number
                        row[2] or "",  # key_type
                        row[3] or "",  # room_location
                        row[4] or "",  # assigned_to
                        row[5] or "",  # assigned_date
                        row[7] or "assigned"  # status
                    )
                    status = row[7] or "assigned"
                    self.keys_tree.insert("", tk.END, values=values, tags=(status,))

        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    def _on_key_select(self, event):
        """Handle key selection."""
        selected = self.keys_tree.selection()
        if not selected:
            return

        item = self.keys_tree.item(selected[0])
        key_id = item["values"][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM key_assignments WHERE assignment_id = ?", (key_id,))
                row = cursor.fetchone()

                if row:
                    self.key_detail_text.config(state=tk.NORMAL)
                    self.key_detail_text.delete(1.0, tk.END)

                    details = f"""Assignment ID: {row[0]}
Key Number: {row[1]}
Key Type: {row[2]}
Room/Location: {row[3]}

Assigned To: {row[4]}
Assigned Date: {row[5]}
Return Date: {row[6] or 'Not returned'}
Status: {row[7]}

Issued By: {row[8]}
Notes: {row[9] or 'None'}
Created: {row[10]}
"""
                    self.key_detail_text.insert(1.0, details)
                    self.key_detail_text.config(state=tk.DISABLED)

        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    def _assign_key(self):
        """Assign a new key."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.windows.assign_key', default="Assign Key"))
        dialog.geometry("400x400")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.labels.key_number', default="Key Number:")).pack(anchor=tk.W, padx=10, pady=5)
        key_num = ttk.Entry(dialog)
        key_num.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.labels.key_type', default="Key Type:")).pack(anchor=tk.W, padx=10, pady=5)
        key_type = ttk.Combobox(dialog, values=["master", "room", "cabinet", "building", "parking"], state="readonly")
        key_type.pack(fill=tk.X, padx=10)
        key_type.set("room")

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.labels.room_location', default="Room/Location:")).pack(anchor=tk.W, padx=10, pady=5)
        room = ttk.Entry(dialog)
        room.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.labels.assign_to_user_id', default="Assign To (User ID):")).pack(anchor=tk.W, padx=10, pady=5)
        assign_to = ttk.Entry(dialog)
        assign_to.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.labels.notes', default="Notes:")).pack(anchor=tk.W, padx=10, pady=5)
        notes = tk.Text(dialog, height=4)
        notes.pack(fill=tk.X, padx=10)

        def assign():
            key_number = key_num.get().strip()
            if not key_number:
                messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.error', default="Error"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.key_number_is_required', default="Key number is required"))
                return

            assigned_to = assign_to.get().strip()
            if not assigned_to:
                messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.error', default="Error"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.user_id_is_required', default="User ID is required"))
                return

            issuer = self.current_user.get("user_id", "unknown") if self.current_user else "unknown"

            try:
                with transaction() as conn:
                    conn.execute("""
                        INSERT INTO key_assignments
                        (key_number, key_type, room_location, assigned_to, assigned_date,
                         status, issued_by, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        key_number,
                        key_type.get(),
                        room.get().strip(),
                        assigned_to,
                        datetime.now().strftime("%Y-%m-%d"),
                        "assigned",
                        issuer,
                        notes.get(1.0, tk.END).strip() or None,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))

                log_activity("create", "key_assignment", user_id=issuer, details={"key_number": key_number, "assigned_to": assigned_to})
                messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.success', default="Success"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.key_assigned', default="Key assigned"))
                dialog.destroy()
                self._load_keys()

            except Exception as e:
                messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.dialogs.error', default="Error"), f"Failed to assign key: {e}")

        ttk.Button(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_issue_card.buttons.assign', default="Assign"), command=assign).pack(pady=10)
