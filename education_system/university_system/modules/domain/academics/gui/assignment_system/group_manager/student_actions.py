"""Student-facing group actions: join, create, view, submit"""

import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system.university_system.modules.shared.constants import paths


class StudentActionsMixin:
    """Mixin for student-facing group functionality"""

    def _join_existing_group(self, assignment_id=None):
        """Student joins existing group for an assignment"""
        try:
            student_id = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None
            if not student_id:
                messagebox.showerror("Error", "You must be logged in")
                return

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Join Group")
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Join Existing Group", font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Assignment selection if not provided
            if not assignment_id:
                assignment_frame = ttk.LabelFrame(dialog, text="Select Assignment", padding=10)
                assignment_frame.pack(fill='x', padx=10, pady=(0, 10))

                ttk.Label(assignment_frame, text="Assignment:").pack(side='left', padx=(0, 10))
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
                    messagebox.showinfo("No Assignments", "No group assignments available to join")
                    dialog.destroy()
                    return

                assignment_combo['values'] = [f"{aid} - {title}" for aid, title in assignments]
                assignment_combo.current(0)
            else:
                assignment_var = tk.StringVar(value=str(assignment_id))

            # Available groups frame
            groups_frame = ttk.LabelFrame(dialog, text="Available Groups", padding=10)
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
                    FROM assignment_groups g
                    LEFT JOIN assignment_group_members gm ON g.id = gm.group_id
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
                    messagebox.showerror("Error", f"Failed to load groups: {e}")

            # Load button
            if not assignment_id:
                ttk.Button(assignment_frame, text="Load Groups", command=load_available_groups).pack(side='left', padx=(10, 0))
            else:
                load_available_groups()

            # Join button
            def join_selected_group():
                selection = groups_tree.selection()
                if not selection:
                    messagebox.showwarning("No Selection", "Please select a group to join")
                    return

                item = groups_tree.item(selection[0])
                group_id = item['tags'][0]
                group_name = item['values'][0]

                if messagebox.askyesno("Confirm Join", f"Join group '{group_name}'?"):
                    try:
                        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                        cursor = conn.cursor()

                        # Check if already in a group for this assignment
                        if assignment_id:
                            aid = assignment_id
                        else:
                            aid = assignment_var.get().split(' - ')[0]

                        cursor.execute('''
                        SELECT g.id FROM assignment_groups g
                        JOIN assignment_group_members gm ON g.id = gm.group_id
                        WHERE g.assignment_id = ? AND gm.student_id = ?
                        ''', (aid, student_id))

                        existing = cursor.fetchone()
                        if existing:
                            conn.close()
                            messagebox.showwarning("Already in Group", "You are already in a group for this assignment")
                            return

                        # Join the group
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        cursor.execute('''
                        INSERT INTO assignment_group_members (group_id, student_id, role, joined_at)
                        VALUES (?, ?, 'member', ?)
                        ''', (group_id, student_id, timestamp))

                        conn.commit()
                        conn.close()

                        messagebox.showinfo("Success", f"You have joined '{group_name}'")
                        dialog.destroy()

                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to join group: {e}")

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))

            ttk.Button(button_frame, text="Join Selected Group", command=join_selected_group,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open join group dialog: {e}")


    def _create_new_group(self, assignment_id=None):
        """Student creates new group for an assignment"""
        try:
            student_id = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None
            if not student_id:
                messagebox.showerror("Error", "You must be logged in")
                return

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Create New Group")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Create New Group", font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Assignment selection if not provided
            if not assignment_id:
                assignment_frame = ttk.LabelFrame(dialog, text="Select Assignment", padding=10)
                assignment_frame.pack(fill='x', padx=10, pady=(0, 10))

                ttk.Label(assignment_frame, text="Assignment:").grid(row=0, column=0, sticky='w', padx=5)
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
                    messagebox.showinfo("No Assignments", "No group assignments available")
                    dialog.destroy()
                    return

                assignment_combo['values'] = [f"{aid} - {title}" for aid, title in assignments]
                assignment_combo.current(0)

                assignment_frame.grid_columnconfigure(1, weight=1)
            else:
                assignment_var = tk.StringVar(value=str(assignment_id))

            # Group details frame
            details_frame = ttk.LabelFrame(dialog, text="Group Details", padding=10)
            details_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            ttk.Label(details_frame, text="Group Name:").grid(row=0, column=0, sticky='w', pady=5)
            group_name_var = tk.StringVar()
            ttk.Entry(details_frame, textvariable=group_name_var, width=40).grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 0))

            ttk.Label(details_frame, text="Description:").grid(row=1, column=0, sticky='nw', pady=5)
            desc_text = scrolledtext.ScrolledText(details_frame, height=6, width=40)
            desc_text.grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 0))

            details_frame.grid_columnconfigure(1, weight=1)

            # Info label
            info_var = tk.StringVar(value="You will be the group leader")
            ttk.Label(dialog, textvariable=info_var, style='Info.TLabel').pack(padx=10, pady=(0, 10))

            # Create button
            def create_group():
                try:
                    group_name = group_name_var.get().strip()
                    if not group_name:
                        messagebox.showerror("Error", "Group name is required", parent=dialog)
                        return

                    description = desc_text.get(1.0, tk.END).strip()

                    # Get assignment ID
                    if assignment_id:
                        aid = assignment_id
                    else:
                        combo_value = assignment_var.get()
                        if not combo_value:
                            messagebox.showerror("Error", "Please select an assignment", parent=dialog)
                            return
                        aid = combo_value.split(' - ')[0]

                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    # Check if student already in a group for this assignment
                    cursor.execute('''
                    SELECT g.id FROM assignment_groups g
                    JOIN assignment_group_members gm ON g.id = gm.group_id
                    WHERE g.assignment_id = ? AND gm.student_id = ?
                    ''', (aid, student_id))

                    existing = cursor.fetchone()
                    if existing:
                        conn.close()
                        messagebox.showwarning("Already in Group", "You are already in a group for this assignment", parent=dialog)
                        return

                    # Create group
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('''
                    INSERT INTO assignment_groups (assignment_id, group_name, description, created_at, created_by)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (aid, group_name, description, timestamp, student_id))

                    group_id = cursor.lastrowid

                    # Add creator as leader
                    cursor.execute('''
                    INSERT INTO assignment_group_members (group_id, student_id, role, joined_at)
                    VALUES (?, ?, 'leader', ?)
                    ''', (group_id, student_id, timestamp))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", f"Group '{group_name}' created successfully!\nYou are the group leader.", parent=dialog)
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create group: {e}", parent=dialog)

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))

            ttk.Button(button_frame, text="Create Group", command=create_group,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open create group dialog: {e}")


    def _view_group_details(self, group_id=None, assignment_id=None):
        """View group details and members (student version)"""
        try:
            student_id = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None
            if not student_id:
                messagebox.showerror("Error", "You must be logged in")
                return

            # If no group_id provided, find student's group for assignment
            if not group_id:
                if not assignment_id:
                    messagebox.showerror("Error", "Assignment ID required")
                    return

                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('''
                SELECT g.id FROM assignment_groups g
                JOIN assignment_group_members gm ON g.id = gm.group_id
                WHERE g.assignment_id = ? AND gm.student_id = ?
                ''', (assignment_id, student_id))

                result = cursor.fetchone()
                conn.close()

                if not result:
                    messagebox.showinfo("No Group", "You are not in a group for this assignment")
                    return

                group_id = result[0]

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Group Details")
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Group Details", font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Get group info
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT g.group_name, g.description, a.title, a.due_date
            FROM assignment_groups g
            JOIN assignments a ON g.assignment_id = a.id
            WHERE g.id = ?
            ''', (group_id,))

            group_info = cursor.fetchone()
            if not group_info:
                conn.close()
                messagebox.showerror("Error", "Group not found")
                dialog.destroy()
                return

            name, desc, assignment, due_date = group_info

            # Info frame
            info_frame = ttk.LabelFrame(dialog, text="Group Information", padding=10)
            info_frame.pack(fill='x', padx=10, pady=(0, 10))

            info_text = f"Group Name: {name}\n"
            info_text += f"Assignment: {assignment}\n"
            info_text += f"Due Date: {due_date}\n"
            info_text += f"Description: {desc or 'N/A'}"

            ttk.Label(info_frame, text=info_text, justify='left').pack(anchor='w')

            # Members frame
            members_frame = ttk.LabelFrame(dialog, text="Group Members", padding=10)
            members_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            columns = ('Name', 'Email', 'Role', 'Joined')
            members_tree = ttk.Treeview(members_frame, columns=columns, show='headings', height=10)

            for col in columns:
                members_tree.heading(col, text=col)
                members_tree.column(col, width=130)

            members_tree.pack(fill='both', expand=True)

            # Load members
            cursor.execute('''
            SELECT u.first_name || ' ' || u.last_name, u.email, gm.role, gm.joined_at
            FROM assignment_group_members gm
            JOIN users u ON gm.student_id = u.id
            WHERE gm.group_id = ?
            ORDER BY gm.role DESC, gm.joined_at
            ''', (group_id,))

            members = cursor.fetchall()
            conn.close()

            for member in members:
                members_tree.insert('', 'end', values=member)

            # Close button
            ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to view group details: {e}")


    def _handle_group_submission(self, assignment_id, group_id):
        """Handle submission from group - delegates to submission manager"""
        try:
            student_id = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None
            if not student_id:
                messagebox.showerror("Error", "You must be logged in")
                return

            # Verify student is in the group
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT role FROM assignment_group_members
            WHERE group_id = ? AND student_id = ?
            ''', (group_id, student_id))

            result = cursor.fetchone()
            conn.close()

            if not result:
                messagebox.showerror("Error", "You are not a member of this group")
                return

            role = result[0]

            # Create submission dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Submit Group Assignment")
            dialog.geometry("550x450")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Submit Group Assignment", font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Group info
            info_frame = ttk.LabelFrame(dialog, text="Submission Information", padding=10)
            info_frame.pack(fill='x', padx=10, pady=(0, 10))

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT g.group_name, a.title, a.due_date, a.file_types_allowed, a.max_file_size_mb
            FROM assignment_groups g
            JOIN assignments a ON g.assignment_id = a.id
            WHERE g.id = ?
            ''', (group_id,))

            info = cursor.fetchone()
            conn.close()

            if not info:
                messagebox.showerror("Error", "Group or assignment not found")
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
            file_frame = ttk.LabelFrame(dialog, text="Select File", padding=10)
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
                            messagebox.showerror("File Too Large",
                                               f"File size ({file_size_mb:.1f} MB) exceeds maximum ({max_size} MB)")
                            return

                    file_path_var.set(filename)

            ttk.Button(file_frame, text="Browse", command=browse_file).pack(side='left', padx=(10, 0))

            # Comments
            comments_frame = ttk.LabelFrame(dialog, text="Submission Comments (Optional)", padding=10)
            comments_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            comments_text = scrolledtext.ScrolledText(comments_frame, height=6)
            comments_text.pack(fill='both', expand=True)

            # Submit button
            def submit_assignment():
                file_path = file_path_var.get()
                if not file_path:
                    messagebox.showerror("Error", "Please select a file to submit", parent=dialog)
                    return

                comments = comments_text.get(1.0, tk.END).strip()

                try:
                    # Copy file to submissions directory
                    submissions_dir = paths.SUBMISSIONS_DIR / 'assignments' / str(assignment_id)
                    submissions_dir.mkdir(parents=True, exist_ok=True)

                    file_name = os.path.basename(file_path)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    dest_file = submissions_dir / f"{group_id}_{timestamp}_{file_name}"

                    shutil.copy2(file_path, dest_file)

                    # Save to database
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    submission_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    cursor.execute('''
                    INSERT INTO assignment_submissions
                    (assignment_id, student_id, group_id, file_name, file_path, submission_date, status, comments)
                    VALUES (?, ?, ?, ?, ?, ?, 'submitted', ?)
                    ''', (assignment_id, student_id, group_id, file_name, str(dest_file), submission_time, comments))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", f"Assignment submitted successfully!\n\nFile: {file_name}\nTime: {submission_time}", parent=dialog)
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to submit assignment: {e}", parent=dialog)

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))

            ttk.Button(button_frame, text="Submit Assignment", command=submit_assignment,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to handle group submission: {e}")
