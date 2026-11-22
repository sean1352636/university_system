"""Student-facing group actions: join, create, view, submit"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._dialogs import messagebox
from education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._dialogs import make_toplevel
from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system import paths


class StudentActionsMixin:
    """Mixin for student-facing group functionality"""

    def _my_student_id(self):
        """The signed-in student's student number. Group members and
        submissions are keyed by it (``group_members.student_id`` refers to
        ``students``), not by the login's numeric id, which differs between
        auth.db and this database."""
        user = (getattr(self, 'auth', None) and getattr(self.auth, 'current_user', None)) or {}
        if user.get('student_id'):
            return str(user['student_id'])
        username = user.get('username')
        if not username:
            return None
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        try:
            row = conn.execute("SELECT student_id FROM users WHERE username = ? COLLATE NOCASE "
                               "AND COALESCE(student_id, '') <> ''", (username,)).fetchone()
            if not row:
                row = conn.execute("SELECT student_id FROM students WHERE student_id = ?",
                                   (username,)).fetchone()
        finally:
            conn.close()
        return str(row[0]) if row else None

    def _join_existing_group(self, assignment_id=None):
        """Student joins existing group for an assignment"""
        try:
            student_id = self._my_student_id()
            if not student_id:
                messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.you_must_be_logged_in', default="You must be logged in"))
                return

            # Create dialog
            dialog = make_toplevel(self.root)
            dialog.title(_t('gui.academics.assignment_system.group_manager.student_actions.windows.join_group', default="Join Group"))
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.join_existing_group', default="Join Existing Group"), font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Assignment selection if not provided
            if not assignment_id:
                assignment_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.select_assignment', default="Select Assignment"), padding=10)
                assignment_frame.pack(fill='x', padx=10, pady=(0, 10))

                ttk.Label(assignment_frame, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.assignment', default="Assignment:")).pack(side='left', padx=(0, 10))
                assignment_var = tk.StringVar()
                assignment_combo = ttk.Combobox(assignment_frame, textvariable=assignment_var, width=40)
                assignment_combo.pack(side='left', fill='x', expand=True)

                # Load group assignments
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('''
                SELECT id, title FROM assignments
                WHERE assignment_type = 'group'
                AND due_date >= datetime('now')
                ORDER BY due_date
                ''')
                assignments = cursor.fetchall()
                conn.close()

                if not assignments:
                    messagebox.showinfo(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.no_assignments', default="No Assignments"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.no_group_assignments_available_to_join', default="No group assignments available to join"))
                    dialog.destroy()
                    return

                assignment_combo['values'] = [f"{aid} - {title}" for aid, title in assignments]
                assignment_combo.current(0)
            else:
                assignment_var = tk.StringVar(value=str(assignment_id))

            # Available groups frame
            groups_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.available_groups', default="Available Groups"), padding=10)
            groups_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            columns = ('Group Name', 'Members', 'Status', 'Description')
            groups_tree = ttk.Treeview(groups_frame, columns=columns, show='headings', height=12)

            for col in columns:
                groups_tree.heading(col, text=col)
                width = 200 if col == 'Description' else 120
                groups_tree.column(col, width=width)

            groups_tree.pack(fill='both', expand=True)

            def load_available_groups():
                # Clear tree
                for item in groups_tree.get_children():
                    groups_tree.delete(item)

                try:
                    # Get assignment ID
                    if assignment_id:
                        aid = assignment_id
                    else:
                        combo_value = assignment_var.get()
                        if not combo_value:
                            return
                        aid = combo_value.split(' - ')[0]

                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    # Get assignment group constraints
                    cursor.execute('SELECT group_size_min, group_size_max FROM assignments WHERE id = ?', (aid,))
                    constraints = cursor.fetchone()
                    if not constraints:
                        conn.close()
                        return

                    min_size, max_size = constraints

                    # Get available groups
                    cursor.execute('''
                    SELECT g.id, g.group_name, g.description,
                           COUNT(gm.student_id) as member_count
                    FROM groups g
                    LEFT JOIN group_members gm ON g.id = gm.group_id
                    WHERE g.assignment_id = ?
                    GROUP BY g.id
                    HAVING member_count < ?
                    ORDER BY g.group_name
                    ''', (aid, max_size))

                    groups = cursor.fetchall()
                    conn.close()

                    for gid, name, desc, count in groups:
                        status = f"{count}/{max_size}"
                        groups_tree.insert('', 'end', values=(name, status, 'Open', desc or 'N/A'), tags=(gid,))

                except Exception as e:
                    messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), f"Failed to load groups: {e}")

            # Load button
            if not assignment_id:
                ttk.Button(assignment_frame, text=_t('gui.academics.assignment_system.group_manager.student_actions.buttons.load_groups', default="Load Groups"), command=load_available_groups).pack(side='left', padx=(10, 0))
            else:
                load_available_groups()

            # Join button
            def join_selected_group():
                selection = groups_tree.selection()
                if not selection:
                    messagebox.showwarning(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.no_selection', default="No Selection"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.please_select_a_group_to_join', default="Please select a group to join"))
                    return

                item = groups_tree.item(selection[0])
                group_id = item['tags'][0]
                group_name = item['values'][0]

                if messagebox.askyesno(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.confirm_join', default="Confirm Join"), f"Join group '{group_name}'?"):
                    try:
                        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                        cursor = conn.cursor()

                        # Check if already in a group for this assignment
                        if assignment_id:
                            aid = assignment_id
                        else:
                            aid = assignment_var.get().split(' - ')[0]

                        cursor.execute('''
                        SELECT g.id FROM groups g
                        JOIN group_members gm ON g.id = gm.group_id
                        WHERE g.assignment_id = ? AND gm.student_id = ?
                        ''', (aid, student_id))

                        existing = cursor.fetchone()
                        if existing:
                            conn.close()
                            messagebox.showwarning(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.already_in_group', default="Already in Group"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.you_are_already_in_a_group_for_this_assignment', default="You are already in a group for this assignment"))
                            return

                        # Join the group
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        cursor.execute('''
                        INSERT INTO group_members (group_id, student_id, role, joined_at)
                        VALUES (?, ?, 'member', ?)
                        ''', (group_id, student_id, timestamp))

                        conn.commit()
                        conn.close()

                        messagebox.showinfo(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.success', default="Success"), f"You have joined '{group_name}'")
                        dialog.destroy()

                    except Exception as e:
                        messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), f"Failed to join group: {e}")

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))

            ttk.Button(button_frame, text=_t('gui.academics.assignment_system.group_manager.student_actions.buttons.join_selected_group', default="Join Selected Group"), command=join_selected_group,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text=_t('gui.academics.assignment_system.group_manager.student_actions.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='right')

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), f"Failed to open join group dialog: {e}")


    def _create_new_group(self, assignment_id=None):
        """Student creates new group for an assignment"""
        try:
            student_id = self._my_student_id()
            if not student_id:
                messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.you_must_be_logged_in', default="You must be logged in"))
                return

            # Create dialog
            dialog = make_toplevel(self.root)
            dialog.title(_t('gui.academics.assignment_system.group_manager.student_actions.windows.create_new_group', default="Create New Group"))
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.create_new_group', default="Create New Group"), font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Assignment selection if not provided
            if not assignment_id:
                assignment_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.select_assignment', default="Select Assignment"), padding=10)
                assignment_frame.pack(fill='x', padx=10, pady=(0, 10))

                ttk.Label(assignment_frame, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.assignment', default="Assignment:")).grid(row=0, column=0, sticky='w', padx=5)
                assignment_var = tk.StringVar()
                assignment_combo = ttk.Combobox(assignment_frame, textvariable=assignment_var, width=35)
                assignment_combo.grid(row=0, column=1, sticky='ew', padx=5)

                # Load group assignments
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('''
                SELECT id, title FROM assignments
                WHERE assignment_type = 'group'
                AND due_date >= datetime('now')
                ORDER BY due_date
                ''')
                assignments = cursor.fetchall()
                conn.close()

                if not assignments:
                    messagebox.showinfo(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.no_assignments', default="No Assignments"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.no_group_assignments_available', default="No group assignments available"))
                    dialog.destroy()
                    return

                assignment_combo['values'] = [f"{aid} - {title}" for aid, title in assignments]
                assignment_combo.current(0)

                assignment_frame.grid_columnconfigure(1, weight=1)
            else:
                assignment_var = tk.StringVar(value=str(assignment_id))

            # Group details frame
            details_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.group_details', default="Group Details"), padding=10)
            details_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            ttk.Label(details_frame, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.group_name', default="Group Name:")).grid(row=0, column=0, sticky='w', pady=5)
            group_name_var = tk.StringVar()
            ttk.Entry(details_frame, textvariable=group_name_var, width=40).grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 0))

            ttk.Label(details_frame, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.description', default="Description:")).grid(row=1, column=0, sticky='nw', pady=5)
            desc_text = scrolledtext.ScrolledText(details_frame, height=6, width=40)
            desc_text.grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 0))

            details_frame.grid_columnconfigure(1, weight=1)

            # Info label
            info_var = tk.StringVar(value=_t('gui.academics.assignment_system.group_manager.student_actions.values.you_will_be_the_group_leader', default="You will be the group leader"))
            ttk.Label(dialog, textvariable=info_var, style='Info.TLabel').pack(padx=10, pady=(0, 10))

            # Create button
            def create_group():
                try:
                    group_name = group_name_var.get().strip()
                    if not group_name:
                        messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.group_name_is_required', default="Group name is required"), parent=dialog)
                        return

                    description = desc_text.get(1.0, tk.END).strip()

                    # Get assignment ID
                    if assignment_id:
                        aid = assignment_id
                    else:
                        combo_value = assignment_var.get()
                        if not combo_value:
                            messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.please_select_an_assignment', default="Please select an assignment"), parent=dialog)
                            return
                        aid = combo_value.split(' - ')[0]

                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    # Check if student already in a group for this assignment
                    cursor.execute('''
                    SELECT g.id FROM groups g
                    JOIN group_members gm ON g.id = gm.group_id
                    WHERE g.assignment_id = ? AND gm.student_id = ?
                    ''', (aid, student_id))

                    existing = cursor.fetchone()
                    if existing:
                        conn.close()
                        messagebox.showwarning(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.already_in_group', default="Already in Group"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.you_are_already_in_a_group_for_this_assignment', default="You are already in a group for this assignment"), parent=dialog)
                        return

                    # Create group
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('''
                    INSERT INTO groups (assignment_id, group_name, description, created_at, created_by)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (aid, group_name, description, timestamp, student_id))

                    group_id = cursor.lastrowid

                    # Add creator as leader
                    cursor.execute('''
                    INSERT INTO group_members (group_id, student_id, role, joined_at)
                    VALUES (?, ?, 'leader', ?)
                    ''', (group_id, student_id, timestamp))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.success', default="Success"), f"Group '{group_name}' created successfully!\nYou are the group leader.", parent=dialog)
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), f"Failed to create group: {e}", parent=dialog)

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))

            ttk.Button(button_frame, text=_t('gui.academics.assignment_system.group_manager.student_actions.buttons.create_group', default="Create Group"), command=create_group,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text=_t('gui.academics.assignment_system.group_manager.student_actions.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='right')

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), f"Failed to open create group dialog: {e}")


    def _view_group_details(self, group_id=None, assignment_id=None):
        """View group details and members (student version)"""
        try:
            student_id = self._my_student_id()
            if not student_id:
                messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.you_must_be_logged_in', default="You must be logged in"))
                return

            # If no group_id provided, find student's group for assignment
            if not group_id:
                if not assignment_id:
                    messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.assignment_id_required', default="Assignment ID required"))
                    return

                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('''
                SELECT g.id FROM groups g
                JOIN group_members gm ON g.id = gm.group_id
                WHERE g.assignment_id = ? AND gm.student_id = ?
                ''', (assignment_id, student_id))

                result = cursor.fetchone()
                conn.close()

                if not result:
                    messagebox.showinfo(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.no_group', default="No Group"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.you_are_not_in_a_group_for_this_assignment', default="You are not in a group for this assignment"))
                    return

                group_id = result[0]

            # Create dialog
            dialog = make_toplevel(self.root)
            dialog.title(_t('gui.academics.assignment_system.group_manager.student_actions.windows.group_details', default="Group Details"))
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.group_details', default="Group Details"), font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Get group info
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT g.group_name, g.description, a.title, a.due_date
            FROM groups g
            JOIN assignments a ON g.assignment_id = a.id
            WHERE g.id = ?
            ''', (group_id,))

            group_info = cursor.fetchone()
            if not group_info:
                conn.close()
                messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.group_not_found', default="Group not found"))
                dialog.destroy()
                return

            name, desc, assignment, due_date = group_info

            # Info frame
            info_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.group_information', default="Group Information"), padding=10)
            info_frame.pack(fill='x', padx=10, pady=(0, 10))

            info_text = f"Group Name: {name}\n"
            info_text += f"Assignment: {assignment}\n"
            info_text += f"Due Date: {due_date}\n"
            info_text += f"Description: {desc or 'N/A'}"

            ttk.Label(info_frame, text=info_text, justify='left').pack(anchor='w')

            # Members frame
            members_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.group_members', default="Group Members"), padding=10)
            members_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            columns = ('Name', 'Email', 'Role', 'Joined')
            members_tree = ttk.Treeview(members_frame, columns=columns, show='headings', height=10)

            for col in columns:
                members_tree.heading(col, text=col)
                members_tree.column(col, width=130)

            members_tree.pack(fill='both', expand=True)

            # Load members
            cursor.execute('''
            SELECT TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')),
                   s.email_address, gm.role, gm.joined_at
            FROM group_members gm
            JOIN students s ON s.student_id = gm.student_id
            WHERE gm.group_id = ?
            ORDER BY gm.role DESC, gm.joined_at
            ''', (group_id,))

            members = cursor.fetchall()
            conn.close()

            for member in members:
                members_tree.insert('', 'end', values=member)

            # Close button
            ttk.Button(dialog, text=_t('gui.academics.assignment_system.group_manager.student_actions.buttons.close', default="Close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), f"Failed to view group details: {e}")


    def _handle_group_submission(self, assignment_id, group_id):
        """Handle submission from group - delegates to submission manager"""
        try:
            student_id = self._my_student_id()
            if not student_id:
                messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.you_must_be_logged_in', default="You must be logged in"))
                return

            # Verify student is in the group
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT role FROM group_members
            WHERE group_id = ? AND student_id = ?
            ''', (group_id, student_id))

            result = cursor.fetchone()
            conn.close()

            if not result:
                messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.you_are_not_a_member_of_this_group', default="You are not a member of this group"))
                return

            role = result[0]

            # Create submission dialog
            dialog = make_toplevel(self.root)
            dialog.title(_t('gui.academics.assignment_system.group_manager.student_actions.windows.submit_group_assignment', default="Submit Group Assignment"))
            dialog.geometry("550x450")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.submit_group_assignment', default="Submit Group Assignment"), font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Group info
            info_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.submission_information', default="Submission Information"), padding=10)
            info_frame.pack(fill='x', padx=10, pady=(0, 10))

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT g.group_name, a.title, a.due_date, a.file_types_allowed, a.max_file_size_mb
            FROM groups g
            JOIN assignments a ON g.assignment_id = a.id
            WHERE g.id = ?
            ''', (group_id,))

            info = cursor.fetchone()
            conn.close()

            if not info:
                messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.group_or_assignment_not_found', default="Group or assignment not found"))
                dialog.destroy()
                return

            group_name, title, due_date, file_types, max_size = info

            info_text = f"Group: {group_name}\n"
            info_text += f"Assignment: {title}\n"
            info_text += f"Due Date: {due_date}\n"
            info_text += f"Your Role: {role.title()}\n"
            info_text += f"Allowed Files: {file_types}\n"
            info_text += f"Max Size: {max_size} MB"

            ttk.Label(info_frame, text=info_text, justify='left').pack(anchor='w')

            # File selection
            file_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.select_file', default="Select File"), padding=10)
            file_frame.pack(fill='x', padx=10, pady=(0, 10))

            file_path_var = tk.StringVar()
            ttk.Entry(file_frame, textvariable=file_path_var, width=40, state='readonly').pack(side='left', fill='x', expand=True)

            def browse_file():
                # Parse allowed file types
                if file_types:
                    types = file_types.split(',')
                    filetypes = [(f"{t} files", f"*{t}") for t in types]
                    filetypes.append(("All files", "*.*"))
                else:
                    filetypes = [("All files", "*.*")]

                filename = filedialog.askopenfilename(filetypes=filetypes)
                if filename:
                    # Check file size
                    if max_size:
                        file_size_mb = os.path.getsize(filename) / (1024 * 1024)
                        if file_size_mb > max_size:
                            messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.file_too_large', default="File Too Large"),
                                               f"File size ({file_size_mb:.1f} MB) exceeds maximum ({max_size} MB)")
                            return

                    file_path_var.set(filename)

            ttk.Button(file_frame, text=_t('gui.academics.assignment_system.group_manager.student_actions.buttons.browse', default="Browse"), command=browse_file).pack(side='left', padx=(10, 0))

            # Comments
            comments_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.assignment_system.group_manager.student_actions.labels.submission_comments_optional', default="Submission Comments (Optional)"), padding=10)
            comments_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            comments_text = scrolledtext.ScrolledText(comments_frame, height=6)
            comments_text.pack(fill='both', expand=True)

            # Submit button
            def submit_assignment():
                file_path = file_path_var.get()
                if not file_path:
                    messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), _t('gui.academics.assignment_system.group_manager.student_actions.dialogs.please_select_a_file_to_submit', default="Please select a file to submit"), parent=dialog)
                    return

                comments = comments_text.get(1.0, tk.END).strip()

                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    from education_system.systems.university.domains.assessment.domain.assignments.assignment_rules import submitting as submission_rules
                    from education_system.systems.university.infrastructure.security import upload_scan
                    submission_rules.check_can_submit(conn, assignment_id, student_id)
                    scan_result = upload_scan.check_upload(file_path)
                except ValueError as refused:
                    messagebox.showwarning("Submit", str(refused))
                    return
                finally:
                    conn.close()

                try:
                    # Copy file to submissions directory
                    submissions_dir = paths.UNIVERSITY_SUBMISSIONS_DIR / 'assignments' / str(assignment_id)
                    submissions_dir.mkdir(parents=True, exist_ok=True)

                    file_name = os.path.basename(file_path)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    dest_file = submissions_dir / f"{group_id}_{timestamp}_{file_name}"

                    shutil.copy2(file_path, dest_file)

                    # Save to database
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    submission_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    cursor.execute(
                        "UPDATE assignment_submissions SET is_final_submission = 0 WHERE assignment_id = ? AND student_id = ?",
                        (assignment_id, student_id))
                    cursor.execute('''
                    INSERT INTO assignment_submissions
                    (assignment_id, student_id, group_id, file_name, file_path, submission_date, status, comments)
                    VALUES (?, ?, ?, ?, ?, ?, 'submitted', ?)
                    ''', (assignment_id, student_id, group_id, file_name, str(dest_file), submission_time, comments))

                    new_submission_id = cursor.lastrowid
                    submission_rules.record_declaration(conn, new_submission_id)
                    submission_rules.record_scan(conn, new_submission_id, scan_result)
                    conn.commit()
                    conn.close()

                    from education_system.systems.university.infrastructure.integrity import (
                        notice as integrity_notice, submission_hook,
                    )
                    integrity_notice.acknowledge(
                        (getattr(getattr(self, 'auth', None), 'current_user', None) or {}).get('username'))
                    submission_hook.after_submission(new_submission_id, path=str(dest_file))

                    messagebox.showinfo(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.success', default="Success"), f"Assignment submitted successfully!\n\nFile: {file_name}\nTime: {submission_time}", parent=dialog)
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), f"Failed to submit assignment: {e}", parent=dialog)

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))
            from education_system.systems.university.infrastructure.integrity import (
                notice as integrity_notice,
            )
            ttk.Label(dialog, text=integrity_notice.notice_text(), wraplength=520,
                      justify='left').pack(fill='x', padx=10, pady=(0, 6), before=button_frame)

            ttk.Button(button_frame, text=_t('gui.academics.assignment_system.group_manager.student_actions.buttons.submit_assignment', default="Submit Assignment"), command=submit_assignment,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text=_t('gui.academics.assignment_system.group_manager.student_actions.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='right')

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.group_manager.student_actions.dialogs.error', default="Error"), f"Failed to handle group submission: {e}")
