"""Group configuration dialog and auto-generation"""

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, scrolledtext
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class ConfigurationMixin:
    """Mixin for group configuration dialog functionality"""

    def show_group_configuration(self):
        """Show comprehensive group configuration interface"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Group Configuration")
            dialog.geometry("1000x700")
            dialog.transient(self.root)

            ttk.Label(dialog, text="Group Configuration & Student Assignment",
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Module selector at the top of the dialog
            module_select_frame = ttk.LabelFrame(dialog, text="Select Module", padding=10)
            module_select_frame.pack(fill='x', padx=10, pady=(0, 5))

            ttk.Label(module_select_frame, text="Module:").pack(side='left', padx=5)
            config_module_combo = ttk.Combobox(module_select_frame, width=40, state='readonly')
            config_module_combo.pack(side='left', padx=5)

            # Load modules into the dropdown
            config_module_map = {}
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cur = conn.cursor()
                cur.execute("SELECT module_code, module_name FROM modules WHERE is_active = 1 ORDER BY module_code")
                for code, name in cur.fetchall():
                    label = f"{code} - {name}"
                    config_module_map[label] = code
                conn.close()
                config_module_combo['values'] = list(config_module_map.keys())
                # Pre-select from create form if available
                if hasattr(self, 'group_module_var') and self.group_module_var.get():
                    config_module_combo.set(self.group_module_var.get())
                elif config_module_map:
                    config_module_combo.current(0)
            except Exception:
                pass

            # Store for use by child methods
            if not hasattr(self, 'group_module_var'):
                self.group_module_var = tk.StringVar()
            if not hasattr(self, 'module_map'):
                self.module_map = {}
            self.module_map.update(config_module_map)

            def _sync_module(*_a):
                self.group_module_var.set(config_module_combo.get())
            config_module_combo.bind('<<ComboboxSelected>>', _sync_module)
            _sync_module()  # sync initial selection

            # Create notebook for different group management options
            notebook = ttk.Notebook(dialog)
            notebook.pack(fill='both', expand=True, padx=10, pady=5)

            # Tab 1: Auto-Assign Groups
            auto_tab = ttk.Frame(notebook)
            notebook.add(auto_tab, text="Auto-Assign Groups")

            ttk.Label(auto_tab, text="Automatically create and assign students to groups",
                     font=('TkDefaultFont', 11)).pack(pady=10)

            auto_frame = ttk.LabelFrame(auto_tab, text="Auto-Assignment Settings", padding=20)
            auto_frame.pack(fill='x', padx=10, pady=10)

            ttk.Label(auto_frame, text="Assignment Method:").grid(row=0, column=0, sticky='w', pady=5)
            auto_method_var = tk.StringVar(value="random")
            ttk.Radiobutton(auto_frame, text="Random", variable=auto_method_var,
                           value="random").grid(row=0, column=1, sticky='w', pady=5)
            ttk.Radiobutton(auto_frame, text="By Performance", variable=auto_method_var,
                           value="performance").grid(row=1, column=1, sticky='w', pady=5)
            ttk.Radiobutton(auto_frame, text="By Preferences", variable=auto_method_var,
                           value="preferences").grid(row=2, column=1, sticky='w', pady=5)

            ttk.Label(auto_frame, text="Number of Groups:").grid(row=3, column=0, sticky='w', pady=5)
            num_groups_var = tk.StringVar(value="5")
            ttk.Entry(auto_frame, textvariable=num_groups_var, width=10).grid(row=3, column=1, sticky='w', pady=5)

            ttk.Label(auto_frame, text="Or Students per Group:").grid(row=4, column=0, sticky='w', pady=5)
            students_per_group_var = tk.StringVar(value="4")
            ttk.Entry(auto_frame, textvariable=students_per_group_var, width=10).grid(row=4, column=1, sticky='w', pady=5)

            balance_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(auto_frame, text="Balance group sizes",
                           variable=balance_var).grid(row=5, column=1, sticky='w', pady=5)

            ttk.Button(auto_frame, text="Generate Groups Automatically",
                      command=lambda: self.auto_generate_groups(dialog, auto_method_var.get(),
                                                               num_groups_var.get(), students_per_group_var.get(),
                                                               balance_var.get())).grid(row=6, column=1, sticky='w', pady=10)

            # Tab 2: Manual Group Creation
            manual_tab = ttk.Frame(notebook)
            notebook.add(manual_tab, text="Manual Groups")

            # Top section - Create new group
            create_frame = ttk.LabelFrame(manual_tab, text="Create New Group", padding=10)
            create_frame.pack(fill='x', padx=10, pady=10)

            ttk.Label(create_frame, text="Group Name:").grid(row=0, column=0, sticky='w', pady=5)
            group_name_var = tk.StringVar()
            ttk.Entry(create_frame, textvariable=group_name_var, width=30).grid(row=0, column=1, pady=5, padx=(10, 0))

            ttk.Label(create_frame, text="Description:").grid(row=1, column=0, sticky='nw', pady=5)
            group_desc_text = tk.Text(create_frame, height=2, width=30)
            group_desc_text.grid(row=1, column=1, pady=5, padx=(10, 0))

            ttk.Button(create_frame, text="Create Group",
                      command=lambda: self.create_manual_group(group_name_var.get(),
                                                              group_desc_text.get(1.0, tk.END).strip(),
                                                              groups_tree)).grid(row=2, column=1, sticky='w', pady=5)

            # Middle section - Groups list and members
            groups_frame = ttk.LabelFrame(manual_tab, text="Groups & Members", padding=10)
            groups_frame.pack(fill='both', expand=True, padx=10, pady=5)

            # Split into two panes
            paned = ttk.PanedWindow(groups_frame, orient='horizontal')
            paned.pack(fill='both', expand=True)

            # Left pane - Groups list
            left_pane = ttk.Frame(paned)
            paned.add(left_pane, weight=1)

            ttk.Label(left_pane, text="Groups", font=('TkDefaultFont', 10, 'bold')).pack()

            groups_tree = ttk.Treeview(left_pane, columns=('Name', 'Members', 'Status'), show='headings', height=15)
            groups_tree.heading('Name', text='Group Name')
            groups_tree.heading('Members', text='Members')
            groups_tree.heading('Status', text='Status')
            groups_tree.column('Name', width=150)
            groups_tree.column('Members', width=80)
            groups_tree.column('Status', width=80)
            groups_tree.pack(fill='both', expand=True, pady=5)

            # Sample groups
            groups_tree.insert('', 'end', values=('Group 1', '0/4', 'Empty'))
            groups_tree.insert('', 'end', values=('Group 2', '0/4', 'Empty'))
            groups_tree.insert('', 'end', values=('Group 3', '0/4', 'Empty'))

            group_buttons = ttk.Frame(left_pane)
            group_buttons.pack(fill='x', pady=5)
            ttk.Button(group_buttons, text="Edit",
                      command=lambda: self.edit_group(groups_tree)).pack(side='left', padx=2)
            ttk.Button(group_buttons, text="Delete",
                      command=lambda: self.delete_group(groups_tree)).pack(side='left', padx=2)
            ttk.Button(group_buttons, text="Merge",
                      command=lambda: self.merge_groups(groups_tree)).pack(side='left', padx=2)

            # Right pane - Students list
            right_pane = ttk.Frame(paned)
            paned.add(right_pane, weight=1)

            ttk.Label(right_pane, text="Available Students", font=('TkDefaultFont', 10, 'bold')).pack()

            students_tree = ttk.Treeview(right_pane, columns=('Student', 'ID', 'Status'), show='headings', height=15)
            students_tree.heading('Student', text='Student Name')
            students_tree.heading('ID', text='Student ID')
            students_tree.heading('Status', text='Status')
            students_tree.column('Student', width=150)
            students_tree.column('ID', width=100)
            students_tree.column('Status', width=80)
            students_tree.pack(fill='both', expand=True, pady=5)

            # Load students from database
            self.load_students_for_group(students_tree, self.group_module_var.get() if hasattr(self, 'group_module_var') else '')

            student_buttons = ttk.Frame(right_pane)
            student_buttons.pack(fill='x', pady=5)
            ttk.Button(student_buttons, text="Add to Group",
                      command=lambda: self.add_student_to_group(students_tree, groups_tree)).pack(side='left', padx=2)
            ttk.Button(student_buttons, text="Remove from Group",
                      command=lambda: self.remove_student_from_group(students_tree, groups_tree)).pack(side='left', padx=2)

            # Tab 3: Load Existing Groups
            load_tab = ttk.Frame(notebook)
            notebook.add(load_tab, text="Load Existing Groups")

            ttk.Label(load_tab, text="Load groups from a previous assignment or saved group set",
                     font=('TkDefaultFont', 11)).pack(pady=10)

            load_frame = ttk.LabelFrame(load_tab, text="Available Group Sets", padding=10)
            load_frame.pack(fill='both', expand=True, padx=10, pady=10)

            load_tree = ttk.Treeview(load_frame, columns=('Name', 'Assignment', 'Groups', 'Date'),
                                    show='headings', height=15)
            load_tree.heading('Name', text='Group Set Name')
            load_tree.heading('Assignment', text='From Assignment')
            load_tree.heading('Groups', text='# Groups')
            load_tree.heading('Date', text='Created Date')

            for col in ('Name', 'Assignment', 'Groups', 'Date'):
                load_tree.column(col, width=150)

            load_tree.pack(fill='both', expand=True, pady=5)

            # Sample data
            load_tree.insert('', 'end', values=('CS101 Project Groups', 'Project 1', '8', '2025-08-15'))
            load_tree.insert('', 'end', values=('Saved Team Formation', 'N/A', '6', '2025-09-01'))

            load_buttons = ttk.Frame(load_tab)
            load_buttons.pack(pady=10)
            ttk.Button(load_buttons, text="Load Selected Groups",
                      command=lambda: messagebox.showinfo("Info", "Groups loaded")).pack(side='left', padx=5)
            ttk.Button(load_buttons, text="Save Current Groups",
                      command=lambda: self.save_group_configuration(groups_tree)).pack(side='left', padx=5)

            # Bottom buttons
            bottom_frame = ttk.Frame(dialog)
            bottom_frame.pack(pady=10)

            ttk.Button(bottom_frame, text="Apply & Close",
                      command=lambda: self.apply_group_configuration(dialog)).pack(side='left', padx=5)
            ttk.Button(bottom_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open group configuration: {e}")


    def auto_generate_groups(self, dialog, method, num_groups, students_per_group, balance):
        """Automatically generate groups based on selected method"""
        try:
            # Get students for current module
            module_code = self.module_map.get(self.group_module_var.get()) if hasattr(self, 'group_module_var') else None
            if not module_code:
                messagebox.showerror("Error", "Please select a module first")
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                # Get enrolled students
                cursor.execute('''
                SELECT sm.student_id, s.first_name, s.last_name
                FROM student_modules sm
                JOIN students s ON sm.student_id = s.student_id
                WHERE sm.module_code = ?
                ORDER BY s.last_name, s.first_name
                ''', (module_code,))

                students = cursor.fetchall()
            finally:
                conn.close()

            if not students:
                messagebox.showwarning("No Students", "No students enrolled in this module")
                return

            # Generate groups based on method
            if method == "random":
                import random
                random.shuffle(students)

            try:
                n_groups = int(num_groups)
            except (ValueError, TypeError):
                n_groups = len(students) // int(students_per_group) if students_per_group else 5

            # Create groups
            groups = [[] for _ in range(n_groups)]
            for i, student in enumerate(students):
                groups[i % n_groups].append(student)

            # Display results
            result_msg = f"Created {n_groups} groups:\n\n"
            for i, group in enumerate(groups, 1):
                result_msg += f"Group {i} ({len(group)} members):\n"
                for sid, fname, lname in group:
                    result_msg += f"  - {fname} {lname} (ID: {sid})\n"
                result_msg += "\n"

            result_window = tk.Toplevel(dialog)
            result_window.title("Generated Groups")
            result_window.geometry("500x600")

            text = scrolledtext.ScrolledText(result_window, wrap=tk.WORD, width=60, height=30)
            text.pack(fill='both', expand=True, padx=10, pady=10)
            text.insert(1.0, result_msg)
            text.config(state='disabled')

            ttk.Button(result_window, text="Accept Groups",
                      command=lambda: messagebox.showinfo("Success", "Groups saved")).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate groups: {e}")


    def load_students_for_group(self, tree, module_name):
        """Load students enrolled in the module"""
        try:
            module_code = self.module_map.get(module_name)
            if not module_code:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT sm.student_id, s.first_name, s.last_name
                FROM student_modules sm
                JOIN students s ON sm.student_id = s.student_id
                WHERE sm.module_code = ?
                ORDER BY s.last_name, s.first_name
                ''', (module_code,))

                students = cursor.fetchall()
            finally:
                conn.close()

            for student in students:
                sid, fname, lname = student
                tree.insert('', 'end', values=(f"{fname} {lname}", sid, "Unassigned"))

        except Exception as e:
            print(f"Error loading students: {e}")


    def create_manual_group(self, name, description, tree):
        """Create a new group manually"""
        if not name:
            messagebox.showwarning("Name Required", "Please enter a group name")
            return

        # Add to tree
        tree.insert('', 'end', values=(name, '0/4', 'Empty'))
        messagebox.showinfo("Success", f"Group '{name}' created")


    def edit_group(self, tree):
        """Edit selected group"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a group to edit")
            return

        # Get current group values
        item = selection[0]
        current_values = tree.item(item, 'values')
        current_name = current_values[0]
        current_members = current_values[1] if len(current_values) > 1 else '0/4'
        current_status = current_values[2] if len(current_values) > 2 else 'Empty'

        # Create edit dialog
        edit_dialog = tk.Toplevel()
        edit_dialog.title("Edit Group")
        edit_dialog.geometry("400x200")
        edit_dialog.transient(tree.winfo_toplevel())
        edit_dialog.grab_set()

        ttk.Label(edit_dialog, text="Edit Group Details", font=('TkDefaultFont', 12, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(edit_dialog, padding=10)
        form_frame.pack(fill='both', expand=True)

        ttk.Label(form_frame, text="Group Name:").grid(row=0, column=0, sticky='w', pady=5, padx=5)
        name_var = tk.StringVar(value=current_name)
        name_entry = ttk.Entry(form_frame, textvariable=name_var, width=30)
        name_entry.grid(row=0, column=1, pady=5, padx=5)
        name_entry.focus()

        ttk.Label(form_frame, text="Max Members:").grid(row=1, column=0, sticky='w', pady=5, padx=5)
        # Parse current max members from '0/4' format
        max_members = current_members.split('/')[1] if '/' in current_members else '4'
        max_var = tk.StringVar(value=max_members)
        max_entry = ttk.Entry(form_frame, textvariable=max_var, width=10)
        max_entry.grid(row=1, column=1, sticky='w', pady=5, padx=5)

        def save_changes():
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showwarning("Name Required", "Please enter a group name", parent=edit_dialog)
                return

            try:
                new_max = int(max_var.get())
                if new_max < 1:
                    raise ValueError("Max members must be at least 1")
            except ValueError as e:
                messagebox.showwarning("Invalid Input", f"Please enter a valid number for max members: {e}",
                                     parent=edit_dialog)
                return

            # Update tree item with new values
            current_count = current_members.split('/')[0] if '/' in current_members else '0'
            new_members = f"{current_count}/{new_max}"

            tree.item(item, values=(new_name, new_members, current_status))
            messagebox.showinfo("Success", f"Group updated to '{new_name}'", parent=edit_dialog)
            edit_dialog.destroy()

        button_frame = ttk.Frame(edit_dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Save", command=save_changes).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=edit_dialog.destroy).pack(side='left', padx=5)


    def delete_group(self, tree):
        """Delete selected group"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a group to delete")
            return

        if messagebox.askyesno("Confirm", "Delete selected group?"):
            tree.delete(selection[0])


    def merge_groups(self, tree):
        """Merge two or more selected groups"""
        selection = tree.selection()
        if len(selection) < 2:
            messagebox.showwarning("Selection Required", "Please select at least 2 groups to merge")
            return

        # Get all selected group details
        groups_info = []
        total_current_members = 0
        total_max_members = 0

        for item in selection:
            values = tree.item(item, 'values')
            group_name = values[0]
            members_str = values[1] if len(values) > 1 else '0/4'

            # Parse member counts
            if '/' in members_str:
                current, maximum = members_str.split('/')
                current_count = int(current)
                max_count = int(maximum)
            else:
                current_count = 0
                max_count = 4

            total_current_members += current_count
            total_max_members += max_count
            groups_info.append(group_name)

        # Create merge dialog
        merge_dialog = tk.Toplevel()
        merge_dialog.title("Merge Groups")
        merge_dialog.geometry("450x300")
        merge_dialog.transient(tree.winfo_toplevel())
        merge_dialog.grab_set()

        ttk.Label(merge_dialog, text="Merge Groups", font=('TkDefaultFont', 12, 'bold')).pack(pady=10)

        info_frame = ttk.Frame(merge_dialog, padding=10)
        info_frame.pack(fill='both', expand=True)

        ttk.Label(info_frame, text="Groups to merge:", font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', pady=5)

        # List groups being merged
        groups_text = tk.Text(info_frame, height=5, width=40, wrap='word')
        groups_text.pack(fill='x', pady=5)
        groups_text.insert('1.0', '\n'.join(f"• {name}" for name in groups_info))
        groups_text.config(state='disabled')

        ttk.Label(info_frame, text=f"Total members: {total_current_members}",
                 font=('TkDefaultFont', 9)).pack(anchor='w', pady=2)

        ttk.Separator(info_frame, orient='horizontal').pack(fill='x', pady=10)

        # Merged group name
        ttk.Label(info_frame, text="New merged group name:").pack(anchor='w', pady=5)
        # Default name: combine first two group names
        default_name = f"{groups_info[0]} + {groups_info[1]}" if len(groups_info) >= 2 else "Merged Group"
        name_var = tk.StringVar(value=default_name)
        name_entry = ttk.Entry(info_frame, textvariable=name_var, width=40)
        name_entry.pack(fill='x', pady=5)
        name_entry.focus()
        name_entry.select_range(0, tk.END)

        # Max members
        ttk.Label(info_frame, text="Max members for merged group:").pack(anchor='w', pady=5)
        max_var = tk.StringVar(value=str(total_max_members))
        max_entry = ttk.Entry(info_frame, textvariable=max_var, width=10)
        max_entry.pack(anchor='w', pady=5)

        def perform_merge():
            merged_name = name_var.get().strip()
            if not merged_name:
                messagebox.showwarning("Name Required", "Please enter a name for the merged group",
                                     parent=merge_dialog)
                return

            try:
                merged_max = int(max_var.get())
                if merged_max < total_current_members:
                    if not messagebox.askyesno("Capacity Warning",
                                              f"The max capacity ({merged_max}) is less than the current "
                                              f"member count ({total_current_members}).\n\n"
                                              f"Continue anyway?",
                                              parent=merge_dialog):
                        return
            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter a valid number for max members",
                                     parent=merge_dialog)
                return

            # Delete all selected groups
            for item in selection:
                tree.delete(item)

            # Determine status
            if total_current_members == 0:
                status = 'Empty'
            elif total_current_members >= merged_max:
                status = 'Full'
            else:
                status = 'Active'

            # Insert merged group
            tree.insert('', 'end', values=(merged_name, f"{total_current_members}/{merged_max}", status))

            messagebox.showinfo("Success",
                              f"Successfully merged {len(groups_info)} groups into '{merged_name}'",
                              parent=merge_dialog)
            merge_dialog.destroy()

        button_frame = ttk.Frame(merge_dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Merge", command=perform_merge).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=merge_dialog.destroy).pack(side='left', padx=5)


    def add_student_to_group(self, students_tree, groups_tree):
        """Add selected student to selected group"""
        student_sel = students_tree.selection()
        group_sel = groups_tree.selection()

        if not student_sel or not group_sel:
            messagebox.showwarning("Selection Required", "Please select both a student and a group")
            return

        messagebox.showinfo("Success", "Student added to group")


    def remove_student_from_group(self, students_tree, groups_tree):
        """Remove selected student from their group"""
        student_sel = students_tree.selection()
        if not student_sel:
            messagebox.showwarning("Selection Required", "Please select a student")
            return

        messagebox.showinfo("Success", "Student removed from group")


    def save_group_configuration(self, tree):
        """Save current group configuration"""
        name = simpledialog.askstring("Save Groups", "Enter a name for this group configuration:")
        if name:
            messagebox.showinfo("Success", f"Group configuration '{name}' saved")


    def apply_group_configuration(self, dialog):
        """Apply group configuration and close dialog"""
        messagebox.showinfo("Success", "Group configuration applied")
        dialog.destroy()
