"""Group management interface - filters, table, CRUD, communication, export"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import csv
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class ManagementMixin:
    """Mixin for the Manage Groups page and all group CRUD operations"""

    def manage_groups(self, *args, **kwargs):
        """Comprehensive group management interface"""
        if not self._check_permission('manage_assignments'):
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text="Manage Groups", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Filter frame
        filter_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Filters", padding=10)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text="Assignment:").grid(row=0, column=0, sticky='w', padx=5)
        self.group_assignment_filter_var = tk.StringVar()
        assignment_combo = ttk.Combobox(filter_frame, textvariable=self.group_assignment_filter_var, width=30)
        assignment_combo.grid(row=0, column=1, padx=5)
        self.load_assignments_for_group_filter(assignment_combo)

        ttk.Label(filter_frame, text="Status:").grid(row=0, column=2, sticky='w', padx=5)
        self.group_status_filter_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(filter_frame, textvariable=self.group_status_filter_var,
                                    values=["All", "Complete", "Incomplete", "Empty"], width=15)
        status_combo.grid(row=0, column=3, padx=5)

        ttk.Button(filter_frame, text="Apply Filters",
                  command=self.load_filtered_groups).grid(row=0, column=4, padx=10)

        # Groups table
        groups_frame = ttk.Frame(self.gui.layout.content_area)
        groups_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Group Name', 'Assignment', 'Members', 'Submitted', 'Status')
        self.manage_groups_tree = ttk.Treeview(groups_frame, columns=columns, show='headings')

        for col in columns:
            self.manage_groups_tree.heading(col, text=col)
            self.manage_groups_tree.column(col, width=120)

        # Scrollbars
        v_scroll = ttk.Scrollbar(groups_frame, orient='vertical', command=self.manage_groups_tree.yview)
        h_scroll = ttk.Scrollbar(groups_frame, orient='horizontal', command=self.manage_groups_tree.xview)
        self.manage_groups_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.manage_groups_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        groups_frame.grid_rowconfigure(0, weight=1)
        groups_frame.grid_columnconfigure(0, weight=1)

        # Bind selection event
        self.manage_groups_tree.bind('<<TreeviewSelect>>', self.on_group_select)

        # Action buttons
        action_frame = ttk.Frame(self.gui.layout.content_area)
        action_frame.pack(fill='x', pady=(10, 0))

        ttk.Label(action_frame, text="Group Actions:", font=('TkDefaultFont', 9, 'bold')).pack(side='left', padx=(0, 10))

        ttk.Button(action_frame, text="View Members",
                  command=self.view_group_members).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Edit Group",
                  command=self.edit_group_details).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Add Members",
                  command=self.add_members_to_group).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Remove Members",
                  command=self.remove_members_from_group).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Merge Groups",
                  command=self.merge_selected_groups).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Split Group",
                  command=self.split_selected_group).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Delete Group",
                  command=self.delete_selected_group).pack(side='left', padx=(0, 5))

        # Second row of actions
        action_frame2 = ttk.Frame(self.gui.layout.content_area)
        action_frame2.pack(fill='x', pady=(5, 0))

        ttk.Label(action_frame2, text="Communication:", font=('TkDefaultFont', 9, 'bold')).pack(side='left', padx=(0, 10))

        ttk.Button(action_frame2, text="Send Message to Group",
                  command=self.send_message_to_group).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame2, text="View Submission",
                  command=self.view_group_submission).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame2, text="Export Group List",
                  command=self.export_group_list).pack(side='left', padx=(0, 5))

        # Group details frame
        self.group_details_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Group Details", padding=10)
        self.group_details_frame.pack(fill='x', pady=(10, 0))

        # Load groups
        self.load_filtered_groups()


    def load_filtered_groups(self):
        """Load groups based on filters"""
        # Clear existing data
        for item in self.manage_groups_tree.get_children():
            self.manage_groups_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check if groups table exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignment_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER NOT NULL,
                group_name TEXT NOT NULL,
                description TEXT,
                max_members INTEGER DEFAULT 4,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assignment_id) REFERENCES assignments(id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignment_group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                role TEXT DEFAULT 'member',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES assignment_groups(id),
                FOREIGN KEY (student_id) REFERENCES users(id)
            )
            ''')

            # Build query based on filters
            query = '''
            SELECT g.id, g.group_name, a.title, COUNT(DISTINCT gm.student_id) as member_count,
                   CASE WHEN s.id IS NOT NULL THEN 'Yes' ELSE 'No' END as submitted,
                   CASE
                       WHEN COUNT(DISTINCT gm.student_id) = 0 THEN 'Empty'
                       WHEN COUNT(DISTINCT gm.student_id) >= g.max_members THEN 'Complete'
                       ELSE 'Incomplete'
                   END as status
            FROM assignment_groups g
            JOIN assignments a ON g.assignment_id = a.id
            LEFT JOIN assignment_group_members gm ON g.id = gm.group_id
            LEFT JOIN assignment_submissions s ON g.assignment_id = s.assignment_id AND g.id = s.group_id
            '''

            conditions = []
            params = []

            # Apply assignment filter
            assignment_filter = self.group_assignment_filter_var.get()
            if assignment_filter and assignment_filter != "All Assignments":
                assignment_id = assignment_filter.split(' - ')[0]
                conditions.append("g.assignment_id = ?")
                params.append(assignment_id)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " GROUP BY g.id ORDER BY a.title, g.group_name"

            cursor.execute(query, params)
            groups = cursor.fetchall()

            # Apply status filter in code (since it's calculated)
            status_filter = self.group_status_filter_var.get()
            for group in groups:
                gid, name, assignment, members, submitted, status = group

                if status_filter != "All" and status != status_filter:
                    continue

                tags = []
                if status == 'Empty':
                    tags = ['empty']
                elif status == 'Complete':
                    tags = ['complete']

                self.manage_groups_tree.insert('', 'end',
                                              values=(gid, name, assignment, members, submitted, status),
                                              tags=tags)

            # Configure tags
            self.manage_groups_tree.tag_configure('empty', background='#ffebee')
            self.manage_groups_tree.tag_configure('complete', background='#e8f5e8')

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load groups: {e}")


    def on_group_select(self, event):
        """Handle group selection"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            return

        item = self.manage_groups_tree.item(selection[0])
        group_id = item['values'][0]
        self.show_group_details(group_id)


    def show_group_details(self, group_id):
        """Show detailed group information"""
        # Clear existing details
        for widget in self.group_details_frame.winfo_children():
            widget.destroy()

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get group info
            cursor.execute('''
            SELECT g.group_name, g.description, a.title, g.max_members
            FROM assignment_groups g
            JOIN assignments a ON g.assignment_id = a.id
            WHERE g.id = ?
            ''', (group_id,))

            group_info = cursor.fetchone()
            if not group_info:
                return

            name, desc, assignment, max_members = group_info

            # Get members
            cursor.execute('''
            SELECT u.first_name, u.last_name, u.email, gm.role
            FROM assignment_group_members gm
            JOIN users u ON gm.student_id = u.id
            WHERE gm.group_id = ?
            ORDER BY gm.joined_at
            ''', (group_id,))

            members = cursor.fetchall()
            conn.close()

            # Display details
            details_text = f"Group: {name}\n"
            details_text += f"Assignment: {assignment}\n"
            details_text += f"Description: {desc or 'N/A'}\n"
            details_text += f"Members: {len(members)}/{max_members}\n\n"
            details_text += "Members:\n"

            for fname, lname, email, role in members:
                details_text += f"  - {fname} {lname} ({email}) - {role}\n"

            ttk.Label(self.group_details_frame, text=details_text,
                     font=('TkDefaultFont', 10), justify='left').pack(anchor='w')

        except Exception as e:
            ttk.Label(self.group_details_frame, text=f"Error loading details: {e}").pack()


    def view_group_members(self):
        """View members of selected group in detail"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group")
            return

        item = self.manage_groups_tree.item(selection[0])
        group_id = item['values'][0]
        group_name = item['values'][1]

        # Create members window
        members_window = tk.Toplevel(self.root)
        members_window.title(f"Members - {group_name}")
        members_window.geometry("700x500")
        members_window.transient(self.root)

        ttk.Label(members_window, text=f"Group Members: {group_name}",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=10)

        # Members list
        members_frame = ttk.Frame(members_window)
        members_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('Name', 'Email', 'Student ID', 'Role', 'Joined')
        members_tree = ttk.Treeview(members_frame, columns=columns, show='headings', height=15)

        for col in columns:
            members_tree.heading(col, text=col)
            members_tree.column(col, width=120)

        members_tree.pack(fill='both', expand=True)

        # Load members
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT u.first_name || ' ' || u.last_name, u.email, u.id, gm.role, gm.joined_at
            FROM assignment_group_members gm
            JOIN users u ON gm.student_id = u.id
            WHERE gm.group_id = ?
            ORDER BY gm.joined_at
            ''', (group_id,))

            members = cursor.fetchall()
            conn.close()

            for member in members:
                members_tree.insert('', 'end', values=member)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load members: {e}")

        ttk.Button(members_window, text="Close", command=members_window.destroy).pack(pady=10)


    def edit_group_details(self):
        """Edit selected group details"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group to edit")
            return

        item = self.manage_groups_tree.item(selection[0])
        group_id = item['values'][0]

        messagebox.showinfo("Edit Group", f"Edit group functionality - Group ID: {group_id}")


    def add_members_to_group(self):
        """Add members to selected group"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group")
            return

        item = self.manage_groups_tree.item(selection[0])
        group_id = item['values'][0]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT g.assignment_id, g.group_name, g.max_members,
                       COUNT(gm.id) as member_count
                FROM assignment_groups g
                LEFT JOIN assignment_group_members gm ON g.id = gm.group_id
                WHERE g.id = ?
                GROUP BY g.id
                ''',
                (group_id,)
            )
            group_row = cursor.fetchone()
            if not group_row:
                conn.close()
                messagebox.showerror("Error", "Selected group no longer exists.")
                return

            assignment_id, group_name, max_members, current_members = group_row

            # Determine module for assignment
            cursor.execute('SELECT module_code, description FROM assignments WHERE id = ?', (assignment_id,))
            assignment_row = cursor.fetchone()
            if not assignment_row:
                conn.close()
                messagebox.showerror("Error", "Assignment associated with this group was not found.")
                return

            module_code, assignment_desc = assignment_row

            # Fetch existing member user IDs
            cursor.execute(
                'SELECT student_id FROM assignment_group_members WHERE group_id = ?',
                (group_id,)
            )
            existing_user_ids = {row[0] for row in cursor.fetchall()}

            # Fetch available students for module
            cursor.execute(
                '''
                SELECT u.id, s.student_id, s.first_name, s.last_name
                FROM students s
                JOIN student_modules sm ON s.student_id = sm.student_id
                JOIN users u ON s.user_id = u.id
                WHERE sm.module_code = ?
                ORDER BY s.last_name, s.first_name
                ''',
                (module_code,)
            )
            all_candidates = cursor.fetchall()
            conn.close()

            available_students = [
                candidate for candidate in all_candidates if candidate[0] not in existing_user_ids
            ]

            if not available_students:
                messagebox.showinfo("Add Members", "No available students to add to this group.")
                return

            capacity_remaining = None
            if max_members and max_members > 0:
                capacity_remaining = max_members - current_members
                if capacity_remaining <= 0:
                    messagebox.showinfo(
                        "Group Full",
                        f"Group '{group_name}' already has {current_members} member(s) "
                        "and cannot accept additional members."
                    )
                    return

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Add Members - {group_name}")
            dialog.geometry("420x460")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text=f"Assignment Module: {module_code}",
                     font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 0))
            if assignment_desc:
                ttk.Label(dialog, text=f"Assignment: {assignment_desc}",
                         wraplength=380, justify='left').pack(anchor='w', padx=10, pady=(0, 10))

            if capacity_remaining is not None:
                ttk.Label(dialog, text=f"Available slots: {capacity_remaining}",
                         style='Info.TLabel').pack(anchor='w', padx=10)

            listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE, exportselection=False)
            listbox.pack(fill='both', expand=True, padx=10, pady=10)

            # Map from index to candidate
            candidate_map = {}
            for index, (user_id, student_id, first_name, last_name) in enumerate(available_students):
                display = f"{student_id} - {first_name} {last_name}"
                listbox.insert(tk.END, display)
                candidate_map[index] = (user_id, student_id, first_name, last_name)

            status_var = tk.StringVar(value="")
            status_label = ttk.Label(dialog, textvariable=status_var, style='Info.TLabel')
            status_label.pack(anchor='w', padx=10)

            def add_selected_members():
                indices = listbox.curselection()
                if not indices:
                    status_var.set("Select at least one student to add.")
                    return

                if capacity_remaining is not None and len(indices) > capacity_remaining:
                    status_var.set(f"Only {capacity_remaining} slot(s) remaining.")
                    return

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                try:
                    conn_inner = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor_inner = conn_inner.cursor()

                    for idx in indices:
                        user_id, student_id_value, _, _ = candidate_map[idx]
                        cursor_inner.execute(
                            '''
                            INSERT OR IGNORE INTO assignment_group_members
                                (group_id, student_id, role, joined_at)
                            VALUES (?, ?, ?, ?)
                            ''',
                            (group_id, user_id, 'member', timestamp)
                        )

                    conn_inner.commit()
                    conn_inner.close()

                    dialog.destroy()
                    self.load_filtered_groups()
                    self.show_group_details(group_id)
                    messagebox.showinfo("Members Added", f"Added {len(indices)} member(s) to '{group_name}'.")
                except Exception as exc:
                    status_var.set(f"Failed to add members: {exc}")

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))
            ttk.Button(button_frame, text="Add Selected", command=add_selected_members,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load available members: {exc}")


    def remove_members_from_group(self):
        """Remove members from selected group"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group")
            return

        item = self.manage_groups_tree.item(selection[0])
        group_id = item['values'][0]
        group_name = item['values'][1]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT gm.id, u.first_name, u.last_name, u.email
                FROM assignment_group_members gm
                JOIN users u ON gm.student_id = u.id
                WHERE gm.group_id = ?
                ORDER BY u.last_name, u.first_name
                ''',
                (group_id,)
            )
            members = cursor.fetchall()
            conn.close()

            if not members:
                messagebox.showinfo("Remove Members", "This group has no members.")
                return

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Remove Members - {group_name}")
            dialog.geometry("420x420")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text=f"Select members to remove from {group_name}:",
                     wraplength=380, justify='left').pack(anchor='w', padx=10, pady=(10, 10))

            listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE, exportselection=False)
            listbox.pack(fill='both', expand=True, padx=10, pady=10)

            member_map = {}
            for index, (member_id, first_name, last_name, email) in enumerate(members):
                display = f"{first_name} {last_name} ({email})"
                listbox.insert(tk.END, display)
                member_map[index] = member_id

            status_var = tk.StringVar(value="")
            status_label = ttk.Label(dialog, textvariable=status_var, style='Info.TLabel')
            status_label.pack(anchor='w', padx=10)

            def remove_selected():
                indices = listbox.curselection()
                if not indices:
                    status_var.set("Select at least one member to remove.")
                    return

                try:
                    conn_inner = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor_inner = conn_inner.cursor()
                    for idx in indices:
                        cursor_inner.execute(
                            "DELETE FROM assignment_group_members WHERE id = ?",
                            (member_map[idx],)
                        )
                    conn_inner.commit()
                    conn_inner.close()

                    dialog.destroy()
                    self.load_filtered_groups()
                    self.show_group_details(group_id)
                    messagebox.showinfo("Members Removed", f"Removed {len(indices)} member(s) from '{group_name}'.")
                except Exception as exc:
                    status_var.set(f"Failed to remove members: {exc}")

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))
            ttk.Button(button_frame, text="Remove Selected", command=remove_selected,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load group members: {exc}")


    def merge_selected_groups(self):
        """Merge multiple selected groups"""
        selections = self.manage_groups_tree.selection()
        if len(selections) < 2:
            messagebox.showwarning("Warning", "Please select at least 2 groups to merge")
            return

        group_ids = [self.manage_groups_tree.item(item)['values'][0] for item in selections]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            placeholder = ','.join('?' * len(group_ids))
            cursor.execute(
                f'''
                SELECT id, assignment_id, group_name
                FROM assignment_groups
                WHERE id IN ({placeholder})
                ''',
                group_ids
            )
            group_data = cursor.fetchall()

            if len(group_data) != len(group_ids):
                conn.close()
                messagebox.showerror("Error", "One or more selected groups no longer exist.")
                return

            assignment_ids = {row[1] for row in group_data}
            if len(assignment_ids) != 1:
                conn.close()
                messagebox.showwarning(
                    "Cannot Merge",
                    "Selected groups belong to different assignments."
                )
                return

            target_group_id = group_data[0][0]
            target_group_name = group_data[0][2]
            other_groups = [row[0] for row in group_data[1:]]

            if not messagebox.askyesno(
                    "Confirm Merge",
                    f"Merge {len(group_ids)} groups into '{target_group_name}'?\n\n"
                    "All members will be moved into the first selected group.") :
                conn.close()
                return

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for other_id in other_groups:
                cursor.execute(
                    '''
                    UPDATE assignment_group_members
                    SET group_id = ?, joined_at = COALESCE(joined_at, ?)
                    WHERE group_id = ?
                    ''',
                    (target_group_id, timestamp, other_id)
                )
                cursor.execute("DELETE FROM assignment_groups WHERE id = ?", (other_id,))

            conn.commit()
            conn.close()

            self.load_filtered_groups()
            self.show_group_details(target_group_id)
            messagebox.showinfo("Groups Merged", f"Groups merged into '{target_group_name}'.")

        except Exception as exc:
            messagebox.showerror("Error", f"Failed to merge groups: {exc}")


    def split_selected_group(self):
        """Split selected group into multiple groups"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group to split")
            return

        item = self.manage_groups_tree.item(selection[0])
        group_id = item['values'][0]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT g.assignment_id, g.group_name, g.description, g.max_members
                FROM assignment_groups g
                WHERE g.id = ?
                ''',
                (group_id,)
            )
            group_info = cursor.fetchone()

            cursor.execute(
                '''
                SELECT gm.id, u.first_name, u.last_name, u.email
                FROM assignment_group_members gm
                JOIN users u ON gm.student_id = u.id
                WHERE gm.group_id = ?
                ''',
                (group_id,)
            )
            members = cursor.fetchall()

            if not group_info:
                conn.close()
                messagebox.showerror("Error", "Group not found.")
                return

            if len(members) < 2:
                conn.close()
                messagebox.showinfo("Split Group", "At least two members are required to split a group.")
                return

            assignment_id, group_name, description, max_members = group_info
            conn.close()

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Split Group - {group_name}")
            dialog.geometry("480x420")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text=f"Move members from '{group_name}' into a new group:",
                     wraplength=440, justify='left').pack(anchor='w', padx=10, pady=(10, 10))

            new_name_var = tk.StringVar(value=f"{group_name} - Split")
            ttk.Label(dialog, text="New Group Name:").pack(anchor='w', padx=10)
            ttk.Entry(dialog, textvariable=new_name_var).pack(fill='x', padx=10, pady=(0, 10))

            listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE, exportselection=False, height=12)
            listbox.pack(fill='both', expand=True, padx=10, pady=10)

            member_map = {}
            for index, (member_id, first_name, last_name, email) in enumerate(members):
                listbox.insert(tk.END, f"{first_name} {last_name} ({email})")
                member_map[index] = member_id

            status_var = tk.StringVar(value="Select members to move into the new group.")
            ttk.Label(dialog, textvariable=status_var, style='Info.TLabel').pack(anchor='w', padx=10)

            def perform_split():
                indices = listbox.curselection()
                if not indices:
                    status_var.set("Select at least one member to move.")
                    return
                if len(indices) >= len(members):
                    status_var.set("At least one member must remain in the original group.")
                    return

                new_group_name = new_name_var.get().strip()
                if not new_group_name:
                    status_var.set("New group name cannot be empty.")
                    return

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                try:
                    conn_inner = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor_inner = conn_inner.cursor()

                    # Ensure unique group name
                    suffix = 1
                    base_name = new_group_name
                    cursor_inner.execute(
                        'SELECT 1 FROM assignment_groups WHERE assignment_id = ? AND group_name = ?',
                        (assignment_id, new_group_name)
                    )
                    while cursor_inner.fetchone():
                        suffix += 1
                        new_group_name = f"{base_name} ({suffix})"
                        cursor_inner.execute(
                            'SELECT 1 FROM assignment_groups WHERE assignment_id = ? AND group_name = ?',
                            (assignment_id, new_group_name)
                        )

                    cursor_inner.execute(
                        '''
                        INSERT INTO assignment_groups (assignment_id, group_name, description, max_members, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        ''',
                        (assignment_id, new_group_name, description, max_members, timestamp)
                    )
                    new_group_id = cursor_inner.lastrowid

                    member_ids = [member_map[idx] for idx in indices]
                    placeholders = ','.join('?' for _ in member_ids)
                    cursor_inner.execute(
                        f'''
                        UPDATE assignment_group_members
                        SET group_id = ?, joined_at = COALESCE(joined_at, ?)
                        WHERE id IN ({placeholders})
                        ''',
                        (new_group_id, timestamp, *member_ids)
                    )

                    conn_inner.commit()
                    conn_inner.close()

                    dialog.destroy()
                    self.load_filtered_groups()
                    self.show_group_details(group_id)
                    messagebox.showinfo("Group Split",
                                        f"Created '{new_group_name}' with {len(indices)} member(s).")
                except Exception as exc:
                    status_var.set(f"Failed to split group: {exc}")

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))
            ttk.Button(button_frame, text="Create New Group", command=perform_split,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

        except Exception as exc:
            messagebox.showerror("Error", f"Failed to split group: {exc}")


    def delete_selected_group(self):
        """Delete selected group"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group to delete")
            return

        item = self.manage_groups_tree.item(selection[0])
        group_id = item['values'][0]
        group_name = item['values'][1]

        if not messagebox.askyesno("Confirm Delete",
                                   f"Delete group '{group_name}'?\n\nThis will remove all members from the group."):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Delete members first
            cursor.execute("DELETE FROM assignment_group_members WHERE group_id = ?", (group_id,))
            # Delete group
            cursor.execute("DELETE FROM assignment_groups WHERE id = ?", (group_id,))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Group '{group_name}' deleted")
            self.load_filtered_groups()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete group: {e}")


    def send_message_to_group(self):
        """Send message to all group members"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group")
            return

        item = self.manage_groups_tree.item(selection[0])
        group_name = item['values'][1]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT u.id, u.first_name, u.last_name
                FROM assignment_group_members gm
                JOIN users u ON gm.student_id = u.id
                WHERE gm.group_id = ?
                ''',
                (item['values'][0],)
            )
            recipients = cursor.fetchall()
            conn.close()

            if not recipients:
                messagebox.showinfo("Send Message", "Group has no members to message.")
                return

            sender_id = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None
            if not sender_id:
                messagebox.showerror("Error", "You must be logged in to send messages.")
                return

            self.gui.db._ensure_messages_table()

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Message Group - {group_name}")
            dialog.geometry("520x420")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text=f"Send message to {len(recipients)} member(s) in {group_name}:",
                     font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 5))

            ttk.Label(dialog, text="\n".join(f"• {fn} {ln}" for _, fn, ln in recipients),
                     justify='left').pack(anchor='w', padx=10)

            ttk.Label(dialog, text="Subject:").pack(anchor='w', padx=10, pady=(15, 5))
            subject_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=subject_var).pack(fill='x', padx=10)

            ttk.Label(dialog, text="Message:").pack(anchor='w', padx=10, pady=(10, 5))
            body_text = scrolledtext.ScrolledText(dialog, height=8, wrap=tk.WORD)
            body_text.pack(fill='both', expand=True, padx=10)

            status_var = tk.StringVar(value="")
            ttk.Label(dialog, textvariable=status_var, style='Info.TLabel').pack(anchor='w', padx=10, pady=(5, 0))

            def send():
                subject = subject_var.get().strip()
                body = body_text.get("1.0", tk.END).strip()
                if not subject or not body:
                    status_var.set("Subject and message are required.")
                    return

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                try:
                    conn_inner = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor_inner = conn_inner.cursor()
                    for recipient_id, _, _ in recipients:
                        cursor_inner.execute(
                            '''
                            INSERT INTO messages (sender_id, recipient_id, subject, message, content, sent_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            ''',
                            (sender_id, recipient_id, subject, body, body, timestamp)
                        )
                    conn_inner.commit()
                    conn_inner.close()
                    dialog.destroy()
                    messagebox.showinfo("Message Sent",
                                        f"Message sent to {len(recipients)} member(s) in {group_name}.")
                except Exception as exc:
                    status_var.set(f"Failed to send message: {exc}")

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=10)
            ttk.Button(button_frame, text="Send Message", command=send, style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

        except Exception as exc:
            messagebox.showerror("Error", f"Failed to prepare message: {exc}")


    def view_group_submission(self):
        """View submission for selected group"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group")
            return

        group_item = self.manage_groups_tree.item(selection[0])
        group_id = group_item['values'][0]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT g.assignment_id, g.group_name
                FROM assignment_groups g
                WHERE g.id = ?
                ''',
                (group_id,)
            )
            group_row = cursor.fetchone()
            if not group_row:
                conn.close()
                messagebox.showerror("Error", "Group not found.")
                return
            assignment_id, group_name = group_row

            cursor.execute(
                '''
                SELECT s.student_id
                FROM assignment_group_members gm
                JOIN students s ON s.user_id = gm.student_id
                WHERE gm.group_id = ?
                ''',
                (group_id,)
            )
            student_ids = [row[0] for row in cursor.fetchall()]

            if not student_ids:
                conn.close()
                messagebox.showinfo("No Submission", "This group has no enrolled student IDs.")
                return

            placeholders = ','.join('?' for _ in student_ids)
            cursor.execute(
                f'''
                SELECT id, file_name, file_path, submission_date, status, grade, feedback, student_id
                FROM assignment_submissions
                WHERE assignment_id = ?
                AND student_id IN ({placeholders})
                ORDER BY submission_date DESC
                LIMIT 1
                ''',
                (assignment_id, *student_ids)
            )
            submission = cursor.fetchone()
            conn.close()

            if not submission:
                messagebox.showinfo("No Submission", "No submissions found for members of this group.")
                return

            sub_id, file_name, file_path, submitted_at, status, grade, feedback, submitter_id = submission

            window = tk.Toplevel(self.root)
            window.title(f"Group Submission - {group_name}")
            window.geometry("520x360")
            window.transient(self.root)
            window.grab_set()

            details = [
                f"Submission ID: {sub_id}",
                f"File: {file_name}",
                f"Submitter: {submitter_id}",
                f"Submitted at: {submitted_at}",
                f"Status: {status}",
                f"Grade: {grade if grade is not None else 'Not graded'}"
            ]
            ttk.Label(window, text="\n".join(details),
                     justify='left', font=('TkDefaultFont', 10)).pack(anchor='w', padx=10, pady=10)

            if feedback:
                feedback_frame = ttk.LabelFrame(window, text="Feedback", padding=10)
                feedback_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
                feedback_text = scrolledtext.ScrolledText(feedback_frame, height=6, wrap=tk.WORD)
                feedback_text.pack(fill='both', expand=True)
                feedback_text.insert(tk.END, feedback)
                feedback_text.config(state='disabled')

            action_frame = ttk.Frame(window)
            action_frame.pack(fill='x', padx=10, pady=10)

            ttk.Button(action_frame, text="Open File",
                      command=lambda: self.open_submission_file(file_path)).pack(side='left')
            ttk.Button(action_frame, text="Download File",
                      command=lambda: self.download_file(file_path)).pack(side='left', padx=10)
            ttk.Button(action_frame, text="Close", command=window.destroy).pack(side='right')

        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load group submission: {exc}")


    def export_group_list(self):
        """Export group list to CSV"""
        try:
            save_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                initialfile="groups_export.csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not save_path:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT g.id, g.group_name, a.title,
                   GROUP_CONCAT(u.first_name || ' ' || u.last_name, '; ') as members
            FROM assignment_groups g
            JOIN assignments a ON g.assignment_id = a.id
            LEFT JOIN assignment_group_members gm ON g.id = gm.group_id
            LEFT JOIN users u ON gm.student_id = u.id
            GROUP BY g.id
            ORDER BY a.title, g.group_name
            ''')

            groups = cursor.fetchall()
            conn.close()

            with open(save_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Group ID', 'Group Name', 'Assignment', 'Members'])
                writer.writerows(groups)

            messagebox.showinfo("Success", f"Exported {len(groups)} groups to:\n{save_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export groups: {e}")
