"""Late submission policy management"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
from datetime import datetime, timedelta
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


POLICY_TEMPLATES = {
    "Strict": {
        "description": "No tolerance for late submissions",
        "penalty_type": "percentage",
        "penalty_per_day": 20.0,
        "max_late_days": 3,
        "grace_period_hours": 0,
        "min_grade_floor": 0.0,
    },
    "Lenient": {
        "description": "Generous late submission allowance",
        "penalty_type": "percentage",
        "penalty_per_day": 5.0,
        "max_late_days": 7,
        "grace_period_hours": 24,
        "min_grade_floor": 40.0,
    },
    "Standard": {
        "description": "Balanced late submission policy",
        "penalty_type": "percentage",
        "penalty_per_day": 10.0,
        "max_late_days": 5,
        "grace_period_hours": 1,
        "min_grade_floor": 0.0,
    },
    "Fixed Deduction": {
        "description": "Fixed point deduction per day late",
        "penalty_type": "fixed",
        "penalty_per_day": 5.0,
        "max_late_days": 5,
        "grace_period_hours": 2,
        "min_grade_floor": 0.0,
    },
    "No Penalty": {
        "description": "Accept late work without penalty",
        "penalty_type": "none",
        "penalty_per_day": 0.0,
        "max_late_days": 14,
        "grace_period_hours": 0,
        "min_grade_floor": 0.0,
    },
}


class LatePolicyManager:
    """Late submission policy management"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style
        self._ensure_tables()

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def _ensure_tables(self):
        """Create required database tables if they don't exist"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS late_policies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        penalty_type TEXT NOT NULL DEFAULT 'percentage'
                            CHECK(penalty_type IN ('percentage', 'fixed', 'none')),
                        penalty_per_day REAL NOT NULL DEFAULT 10.0,
                        max_late_days INTEGER NOT NULL DEFAULT 5,
                        grace_period_hours INTEGER NOT NULL DEFAULT 0,
                        min_grade_floor REAL NOT NULL DEFAULT 0.0,
                        is_default INTEGER NOT NULL DEFAULT 0,
                        created_by TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS assignment_late_policies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assignment_id INTEGER NOT NULL,
                        policy_id INTEGER NOT NULL,
                        applied_at TEXT NOT NULL DEFAULT (datetime('now')),
                        FOREIGN KEY (policy_id) REFERENCES late_policies(id)
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS late_passes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        assignment_id INTEGER,
                        used INTEGER NOT NULL DEFAULT 0,
                        granted_by TEXT,
                        granted_at TEXT NOT NULL DEFAULT (datetime('now')),
                        reason TEXT
                    )
                ''')
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Error ensuring late policy tables: {e}")

    # ------------------------------------------------------------------ #
    #  Main dashboard                                                     #
    # ------------------------------------------------------------------ #

    def show_late_policies(self):
        """Main policy management dashboard"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied",
                                   "You do not have permission to manage late policies.")
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area,
                          text="Late Submission Policy Management",
                          style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Toolbar
        toolbar = ttk.Frame(self.gui.layout.content_area)
        toolbar.pack(fill='x', pady=(0, 10))

        ttk.Button(toolbar, text="Create Policy",
                   command=self.create_policy).pack(side='left', padx=(0, 5))
        ttk.Button(toolbar, text="Create from Template",
                   command=self._create_from_template).pack(side='left', padx=(0, 5))
        ttk.Button(toolbar, text="Apply Penalties (Batch)",
                   command=self.apply_late_penalties).pack(side='left', padx=(0, 5))
        ttk.Button(toolbar, text="Late Submission Report",
                   command=self.show_late_submission_report).pack(side='left', padx=(0, 5))
        ttk.Button(toolbar, text="Manage Late Passes",
                   command=self._show_late_passes).pack(side='left', padx=(0, 5))
        ttk.Button(toolbar, text="Refresh",
                   command=self.show_late_policies).pack(side='right')

        # Policies treeview
        tree_frame = ttk.LabelFrame(self.gui.layout.content_area,
                                    text="Configured Policies", padding=10)
        tree_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Name', 'Type', 'Penalty/Day', 'Max Days',
                   'Grace (hrs)', 'Min Grade', 'Default', 'Created')
        self.policy_tree = ttk.Treeview(tree_frame, columns=columns,
                                        show='headings', height=12)

        col_widths = {
            'ID': 40, 'Name': 150, 'Type': 90, 'Penalty/Day': 90,
            'Max Days': 70, 'Grace (hrs)': 80, 'Min Grade': 80,
            'Default': 60, 'Created': 130,
        }
        for col in columns:
            self.policy_tree.heading(col, text=col)
            self.policy_tree.column(col, width=col_widths.get(col, 100), anchor='center')

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical',
                                  command=self.policy_tree.yview)
        self.policy_tree.configure(yscrollcommand=scrollbar.set)
        self.policy_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Context buttons below the tree
        btn_frame = ttk.Frame(self.gui.layout.content_area)
        btn_frame.pack(fill='x', pady=(0, 10))

        ttk.Button(btn_frame, text="Edit Selected",
                   command=self._edit_selected_policy).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Delete Selected",
                   command=self._delete_selected_policy).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Set as Default",
                   command=self._set_default_policy).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Apply to Assignment",
                   command=self._prompt_apply_to_assignment).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Apply to Module",
                   command=self._prompt_apply_to_module).pack(side='left', padx=(0, 5))

        self._load_policies()

    def _load_policies(self):
        """Load policies into the treeview"""
        for item in self.policy_tree.get_children():
            self.policy_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, name, penalty_type, penalty_per_day, max_late_days,
                           grace_period_hours, min_grade_floor, is_default, created_at
                    FROM late_policies
                    ORDER BY is_default DESC, name
                ''')
                for row in cursor.fetchall():
                    pid, name, ptype, ppd, mld, gph, mgf, isd, cat = row
                    default_str = "Yes" if isd else "No"
                    penalty_str = f"{ppd}%" if ptype == 'percentage' else (
                        f"{ppd} pts" if ptype == 'fixed' else "None")
                    self.policy_tree.insert('', 'end', iid=str(pid),
                                            values=(pid, name, ptype.title(),
                                                    penalty_str, mld, gph, mgf,
                                                    default_str, cat))
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load policies: {e}")

    # ------------------------------------------------------------------ #
    #  Create / Edit policy                                               #
    # ------------------------------------------------------------------ #

    def create_policy(self):
        """Form to create a new late policy"""
        self._show_policy_form(policy_id=None)

    def edit_policy(self, policy_id):
        """Edit an existing policy"""
        self._show_policy_form(policy_id=policy_id)

    def _show_policy_form(self, policy_id=None):
        """Show create / edit form for a late policy"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied",
                                   "You do not have permission to manage late policies.")
            return

        self.gui.layout.clear_content_area()
        editing = policy_id is not None
        form_title = "Edit Late Policy" if editing else "Create Late Policy"

        title = ttk.Label(self.gui.layout.content_area, text=form_title,
                          style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        form_frame = ttk.LabelFrame(self.gui.layout.content_area,
                                    text="Policy Details", padding=15)
        form_frame.pack(fill='x', pady=(0, 10))

        # Fields
        row = 0
        ttk.Label(form_frame, text="Policy Name:").grid(
            row=row, column=0, sticky='w', padx=5, pady=5)
        name_var = tk.StringVar()
        name_entry = ttk.Entry(form_frame, textvariable=name_var, width=40)
        name_entry.grid(row=row, column=1, sticky='w', padx=5, pady=5)

        row += 1
        ttk.Label(form_frame, text="Description:").grid(
            row=row, column=0, sticky='nw', padx=5, pady=5)
        desc_text = scrolledtext.ScrolledText(form_frame, width=38, height=3)
        desc_text.grid(row=row, column=1, sticky='w', padx=5, pady=5)

        row += 1
        ttk.Label(form_frame, text="Penalty Type:").grid(
            row=row, column=0, sticky='w', padx=5, pady=5)
        type_var = tk.StringVar(value='percentage')
        type_combo = ttk.Combobox(form_frame, textvariable=type_var,
                                  values=['percentage', 'fixed', 'none'],
                                  state='readonly', width=20)
        type_combo.grid(row=row, column=1, sticky='w', padx=5, pady=5)

        row += 1
        ttk.Label(form_frame, text="Penalty Per Day:").grid(
            row=row, column=0, sticky='w', padx=5, pady=5)
        penalty_var = tk.StringVar(value='10.0')
        ttk.Entry(form_frame, textvariable=penalty_var, width=15).grid(
            row=row, column=1, sticky='w', padx=5, pady=5)

        row += 1
        ttk.Label(form_frame, text="Max Late Days:").grid(
            row=row, column=0, sticky='w', padx=5, pady=5)
        max_days_var = tk.StringVar(value='5')
        ttk.Entry(form_frame, textvariable=max_days_var, width=15).grid(
            row=row, column=1, sticky='w', padx=5, pady=5)

        row += 1
        ttk.Label(form_frame, text="Grace Period (hours):").grid(
            row=row, column=0, sticky='w', padx=5, pady=5)
        grace_var = tk.StringVar(value='0')
        ttk.Entry(form_frame, textvariable=grace_var, width=15).grid(
            row=row, column=1, sticky='w', padx=5, pady=5)

        row += 1
        ttk.Label(form_frame, text="Min Grade Floor:").grid(
            row=row, column=0, sticky='w', padx=5, pady=5)
        floor_var = tk.StringVar(value='0.0')
        ttk.Entry(form_frame, textvariable=floor_var, width=15).grid(
            row=row, column=1, sticky='w', padx=5, pady=5)

        row += 1
        default_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="Set as default policy",
                        variable=default_var).grid(
            row=row, column=1, sticky='w', padx=5, pady=5)

        # Pre-fill when editing
        if editing:
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT name, description, penalty_type, penalty_per_day,
                               max_late_days, grace_period_hours, min_grade_floor, is_default
                        FROM late_policies WHERE id = ?
                    ''', (policy_id,))
                    result = cursor.fetchone()
                    if result:
                        name_var.set(result[0])
                        desc_text.insert('1.0', result[1] or '')
                        type_var.set(result[2])
                        penalty_var.set(str(result[3]))
                        max_days_var.set(str(result[4]))
                        grace_var.set(str(result[5]))
                        floor_var.set(str(result[6]))
                        default_var.set(bool(result[7]))
                finally:
                    conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load policy: {e}")
                return

        # Buttons
        btn_frame = ttk.Frame(self.gui.layout.content_area)
        btn_frame.pack(fill='x', pady=10)

        def save_policy():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Validation", "Policy name is required.")
                return
            try:
                penalty_per_day = float(penalty_var.get())
                max_late_days = int(max_days_var.get())
                grace_period_hours = int(grace_var.get())
                min_grade_floor = float(floor_var.get())
            except ValueError:
                messagebox.showwarning("Validation",
                                       "Numeric fields must contain valid numbers.")
                return

            description = desc_text.get('1.0', 'end-1c').strip()
            penalty_type = type_var.get()
            is_default = 1 if default_var.get() else 0
            created_by = ''
            try:
                if self.auth and self.auth.current_user:
                    created_by = (self.auth.current_user.get('username', '')
                                  or self.auth.current_user.get('id', ''))
            except Exception:
                pass

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()
                    # If setting as default, clear previous default
                    if is_default:
                        cursor.execute(
                            'UPDATE late_policies SET is_default = 0 WHERE is_default = 1')
                    if editing:
                        cursor.execute('''
                            UPDATE late_policies
                            SET name=?, description=?, penalty_type=?, penalty_per_day=?,
                                max_late_days=?, grace_period_hours=?, min_grade_floor=?,
                                is_default=?
                            WHERE id=?
                        ''', (name, description, penalty_type, penalty_per_day,
                              max_late_days, grace_period_hours, min_grade_floor,
                              is_default, policy_id))
                    else:
                        cursor.execute('''
                            INSERT INTO late_policies
                            (name, description, penalty_type, penalty_per_day,
                             max_late_days, grace_period_hours, min_grade_floor,
                             is_default, created_by)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (name, description, penalty_type, penalty_per_day,
                              max_late_days, grace_period_hours, min_grade_floor,
                              is_default, created_by))
                    conn.commit()
                finally:
                    conn.close()

                action = "updated" if editing else "created"
                messagebox.showinfo("Success", f"Policy '{name}' {action} successfully.")
                self.show_late_policies()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error",
                                     f"A policy named '{name}' already exists.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save policy: {e}")

        ttk.Button(btn_frame, text="Save Policy", command=save_policy).pack(
            side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Cancel",
                   command=self.show_late_policies).pack(side='left')

    # ------------------------------------------------------------------ #
    #  Template helpers                                                   #
    # ------------------------------------------------------------------ #

    def _create_from_template(self):
        """Show dialog to pick and create a policy from a template"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Policy from Template")
        dialog.geometry("400x320")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Select a template:").pack(
            anchor='w', padx=10, pady=(10, 5))

        template_var = tk.StringVar()
        template_combo = ttk.Combobox(dialog, textvariable=template_var,
                                      values=list(POLICY_TEMPLATES.keys()),
                                      state='readonly', width=30)
        template_combo.pack(padx=10, pady=(0, 10))
        template_combo.current(0)

        info_text = scrolledtext.ScrolledText(dialog, width=45, height=8,
                                              state='disabled')
        info_text.pack(padx=10, fill='both', expand=True)

        def on_template_change(*_args):
            tpl = POLICY_TEMPLATES.get(template_var.get(), {})
            info_text.configure(state='normal')
            info_text.delete('1.0', 'end')
            for k, v in tpl.items():
                info_text.insert('end', f"{k}: {v}\n")
            info_text.configure(state='disabled')

        template_combo.bind('<<ComboboxSelected>>', on_template_change)
        on_template_change()

        def apply_template():
            tpl_name = template_var.get()
            tpl = POLICY_TEMPLATES.get(tpl_name)
            if not tpl:
                return

            created_by = ''
            try:
                if self.auth and self.auth.current_user:
                    created_by = (self.auth.current_user.get('username', '')
                                  or self.auth.current_user.get('id', ''))
            except Exception:
                pass

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO late_policies
                        (name, description, penalty_type, penalty_per_day,
                         max_late_days, grace_period_hours, min_grade_floor,
                         is_default, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                    ''', (tpl_name, tpl['description'], tpl['penalty_type'],
                          tpl['penalty_per_day'], tpl['max_late_days'],
                          tpl['grace_period_hours'], tpl['min_grade_floor'],
                          created_by))
                    conn.commit()
                finally:
                    conn.close()
                dialog.destroy()
                messagebox.showinfo("Success",
                                    f"Policy '{tpl_name}' created from template.")
                self.show_late_policies()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error",
                                     f"A policy named '{tpl_name}' already exists.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create policy: {e}")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill='x', padx=10, pady=10)
        ttk.Button(btn_frame, text="Create", command=apply_template).pack(
            side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left')

    # ------------------------------------------------------------------ #
    #  Edit / delete helpers                                              #
    # ------------------------------------------------------------------ #

    def _edit_selected_policy(self):
        """Edit the policy currently selected in the treeview"""
        sel = self.policy_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a policy to edit.")
            return
        policy_id = int(self.policy_tree.item(sel[0], 'values')[0])
        self.edit_policy(policy_id)

    def _delete_selected_policy(self):
        """Delete the selected policy"""
        sel = self.policy_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a policy to delete.")
            return
        policy_id = int(self.policy_tree.item(sel[0], 'values')[0])
        name = self.policy_tree.item(sel[0], 'values')[1]

        if not messagebox.askyesno("Confirm Delete",
                                   f"Delete policy '{name}'? This cannot be undone."):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM assignment_late_policies WHERE policy_id = ?',
                               (policy_id,))
                cursor.execute('DELETE FROM late_policies WHERE id = ?', (policy_id,))
                conn.commit()
            finally:
                conn.close()
            messagebox.showinfo("Deleted", f"Policy '{name}' deleted.")
            self._load_policies()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete policy: {e}")

    def _set_default_policy(self):
        """Set selected policy as the default"""
        sel = self.policy_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a policy.")
            return
        policy_id = int(self.policy_tree.item(sel[0], 'values')[0])
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('UPDATE late_policies SET is_default = 0 WHERE is_default = 1')
                cursor.execute('UPDATE late_policies SET is_default = 1 WHERE id = ?',
                               (policy_id,))
                conn.commit()
            finally:
                conn.close()
            messagebox.showinfo("Success", "Default policy updated.")
            self._load_policies()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set default: {e}")

    # ------------------------------------------------------------------ #
    #  Apply policy to assignment / module                                #
    # ------------------------------------------------------------------ #

    def apply_policy_to_assignment(self, assignment_id, policy_id):
        """Assign a late policy to an assignment"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                # Remove any existing policy link for this assignment
                cursor.execute(
                    'DELETE FROM assignment_late_policies WHERE assignment_id = ?',
                    (assignment_id,))
                cursor.execute('''
                    INSERT INTO assignment_late_policies (assignment_id, policy_id)
                    VALUES (?, ?)
                ''', (assignment_id, policy_id))
                conn.commit()
            finally:
                conn.close()
            return True
        except Exception as e:
            messagebox.showerror("Error",
                                 f"Failed to apply policy to assignment: {e}")
            return False

    def apply_policy_to_module(self, module_code, policy_id):
        """Apply a late policy to all assignments in a module"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id FROM assignments WHERE module_code = ?',
                    (module_code,))
                assignment_ids = [r[0] for r in cursor.fetchall()]

                for aid in assignment_ids:
                    cursor.execute(
                        'DELETE FROM assignment_late_policies WHERE assignment_id = ?',
                        (aid,))
                    cursor.execute('''
                        INSERT INTO assignment_late_policies (assignment_id, policy_id)
                        VALUES (?, ?)
                    ''', (aid, policy_id))
                conn.commit()
            finally:
                conn.close()

            messagebox.showinfo("Success",
                                f"Policy applied to {len(assignment_ids)} assignment(s) "
                                f"in module {module_code}.")
            return True
        except Exception as e:
            messagebox.showerror("Error",
                                 f"Failed to apply policy to module: {e}")
            return False

    def _prompt_apply_to_assignment(self):
        """Dialog to select an assignment and apply the selected policy"""
        sel = self.policy_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a policy first.")
            return
        policy_id = int(self.policy_tree.item(sel[0], 'values')[0])

        dialog = tk.Toplevel(self.root)
        dialog.title("Apply Policy to Assignment")
        dialog.geometry("450x200")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Select Assignment:").pack(
            anchor='w', padx=10, pady=(10, 5))

        assignment_var = tk.StringVar()
        assignment_combo = ttk.Combobox(dialog, textvariable=assignment_var,
                                        state='readonly', width=50)
        assignment_combo.pack(padx=10, pady=(0, 10))

        assignment_map = {}
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, title, module_code FROM assignments
                    WHERE is_active = 1 ORDER BY title
                ''')
                items = []
                for aid, atitle, mcode in cursor.fetchall():
                    display = f"{atitle} ({mcode}) [ID: {aid}]"
                    items.append(display)
                    assignment_map[display] = aid
                assignment_combo['values'] = items
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assignments: {e}")
            dialog.destroy()
            return

        def do_apply():
            key = assignment_var.get()
            aid = assignment_map.get(key)
            if aid is None:
                messagebox.showwarning("Selection", "Please select an assignment.")
                return
            if self.apply_policy_to_assignment(aid, policy_id):
                messagebox.showinfo("Success", "Policy applied to assignment.")
                dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill='x', padx=10, pady=10)
        ttk.Button(btn_frame, text="Apply", command=do_apply).pack(
            side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left')

    def _prompt_apply_to_module(self):
        """Dialog to select a module and apply the selected policy"""
        sel = self.policy_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a policy first.")
            return
        policy_id = int(self.policy_tree.item(sel[0], 'values')[0])

        dialog = tk.Toplevel(self.root)
        dialog.title("Apply Policy to Module")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Select Module:").pack(
            anchor='w', padx=10, pady=(10, 5))

        module_var = tk.StringVar()
        module_combo = ttk.Combobox(dialog, textvariable=module_var,
                                    state='readonly', width=40)
        module_combo.pack(padx=10, pady=(0, 10))

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT DISTINCT module_code FROM assignments
                    WHERE is_active = 1 ORDER BY module_code
                ''')
                modules = [r[0] for r in cursor.fetchall()]
                module_combo['values'] = modules
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load modules: {e}")
            dialog.destroy()
            return

        def do_apply():
            mcode = module_var.get().strip()
            if not mcode:
                messagebox.showwarning("Selection", "Please select a module.")
                return
            self.apply_policy_to_module(mcode, policy_id)
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill='x', padx=10, pady=10)
        ttk.Button(btn_frame, text="Apply", command=do_apply).pack(
            side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left')

    # ------------------------------------------------------------------ #
    #  Late penalty calculation                                           #
    # ------------------------------------------------------------------ #

    def _get_policy_for_assignment(self, cursor, assignment_id):
        """Return the policy row for an assignment, falling back to default"""
        cursor.execute('''
            SELECT lp.id, lp.name, lp.penalty_type, lp.penalty_per_day,
                   lp.max_late_days, lp.grace_period_hours, lp.min_grade_floor
            FROM assignment_late_policies alp
            JOIN late_policies lp ON alp.policy_id = lp.id
            WHERE alp.assignment_id = ?
            ORDER BY alp.applied_at DESC LIMIT 1
        ''', (assignment_id,))
        row = cursor.fetchone()
        if row:
            return row

        # Fallback to default policy
        cursor.execute('''
            SELECT id, name, penalty_type, penalty_per_day,
                   max_late_days, grace_period_hours, min_grade_floor
            FROM late_policies WHERE is_default = 1 LIMIT 1
        ''')
        return cursor.fetchone()

    def _compute_penalty(self, cursor, submission_id):
        """Compute penalty details for a submission.

        Returns a dict with keys: submission_id, student_id, assignment_id,
        original_grade, days_late, penalty_amount, adjusted_grade, policy_name,
        has_late_pass, grace_applied  or None if not applicable.
        """
        cursor.execute('''
            SELECT s.id, s.student_id, s.assignment_id, s.grade,
                   s.submission_date, a.due_date
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            WHERE s.id = ?
        ''', (submission_id,))
        sub = cursor.fetchone()
        if not sub:
            return None

        sid, student_id, assignment_id, original_grade, sub_date_str, due_date_str = sub
        if original_grade is None:
            original_grade = 0.0

        try:
            sub_date = datetime.strptime(sub_date_str, '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            try:
                sub_date = datetime.strptime(sub_date_str, '%Y-%m-%dT%H:%M:%S')
            except (ValueError, TypeError):
                return None

        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M:%S')
            except (ValueError, TypeError):
                return None

        policy = self._get_policy_for_assignment(cursor, assignment_id)
        if not policy:
            return None

        (policy_id, policy_name, penalty_type, penalty_per_day,
         max_late_days, grace_period_hours, min_grade_floor) = policy

        # Check for unused late pass
        cursor.execute('''
            SELECT id FROM late_passes
            WHERE student_id = ? AND assignment_id = ? AND used = 0
            LIMIT 1
        ''', (student_id, assignment_id))
        late_pass = cursor.fetchone()
        has_late_pass = late_pass is not None

        # Apply grace period
        effective_due = due_date + timedelta(hours=grace_period_hours)
        grace_applied = sub_date <= effective_due and sub_date > due_date

        if sub_date <= effective_due:
            # Within grace period or on time
            return {
                'submission_id': sid,
                'student_id': student_id,
                'assignment_id': assignment_id,
                'original_grade': original_grade,
                'days_late': 0,
                'penalty_amount': 0.0,
                'adjusted_grade': original_grade,
                'policy_name': policy_name,
                'has_late_pass': has_late_pass,
                'grace_applied': grace_applied,
                'late_pass_id': None,
            }

        # Calculate days late (ceiling: any fraction of a day counts as a full day)
        delta = sub_date - effective_due
        days_late = int(delta.total_seconds() // 86400)
        if delta.total_seconds() % 86400 > 0:
            days_late += 1

        # Cap at max late days
        if days_late > max_late_days:
            # Beyond max: could be rejected entirely -- treat as max penalty
            days_late = max_late_days

        # Late pass exemption
        late_pass_id = None
        if has_late_pass:
            late_pass_id = late_pass[0]
            return {
                'submission_id': sid,
                'student_id': student_id,
                'assignment_id': assignment_id,
                'original_grade': original_grade,
                'days_late': days_late,
                'penalty_amount': 0.0,
                'adjusted_grade': original_grade,
                'policy_name': policy_name,
                'has_late_pass': True,
                'grace_applied': False,
                'late_pass_id': late_pass_id,
            }

        # Calculate penalty
        if penalty_type == 'percentage':
            penalty_amount = penalty_per_day * days_late
            adjusted_grade = original_grade - (original_grade * penalty_amount / 100.0)
        elif penalty_type == 'fixed':
            penalty_amount = penalty_per_day * days_late
            adjusted_grade = original_grade - penalty_amount
        else:
            penalty_amount = 0.0
            adjusted_grade = original_grade

        # Enforce floor
        if adjusted_grade < min_grade_floor:
            adjusted_grade = min_grade_floor

        return {
            'submission_id': sid,
            'student_id': student_id,
            'assignment_id': assignment_id,
            'original_grade': original_grade,
            'days_late': days_late,
            'penalty_amount': round(penalty_amount, 2),
            'adjusted_grade': round(adjusted_grade, 2),
            'policy_name': policy_name,
            'has_late_pass': False,
            'grace_applied': False,
            'late_pass_id': None,
        }

    def calculate_late_penalty(self, submission_id):
        """Calculate and display what the penalty would be for a submission"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                result = self._compute_penalty(cursor, submission_id)
            finally:
                conn.close()

            if result is None:
                messagebox.showinfo("Info",
                                    "No penalty data available for this submission.\n"
                                    "Check that a policy is assigned and the submission exists.")
                return result

            lines = [
                f"Submission ID: {result['submission_id']}",
                f"Student: {result['student_id']}",
                f"Policy: {result['policy_name']}",
                f"Days Late: {result['days_late']}",
            ]
            if result['grace_applied']:
                lines.append("Grace period applied: Yes")
            if result['has_late_pass']:
                lines.append("Late pass available: Yes (penalty waived)")
            lines.append(f"Original Grade: {result['original_grade']}")
            lines.append(f"Penalty: {result['penalty_amount']}")
            lines.append(f"Adjusted Grade: {result['adjusted_grade']}")

            messagebox.showinfo("Late Penalty Calculation", "\n".join(lines))
            return result

        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate penalty: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Batch apply penalties                                              #
    # ------------------------------------------------------------------ #

    def apply_late_penalties(self):
        """Batch apply penalties to all late submissions"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied",
                                   "You do not have permission to apply penalties.")
            return

        if not messagebox.askyesno(
                "Confirm",
                "This will apply late penalties to all graded late submissions "
                "that have an assigned policy. Continue?"):
            return

        applied = 0
        errors = 0
        skipped = 0
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                # Find all submissions that were submitted after due date
                cursor.execute('''
                    SELECT s.id
                    FROM assignment_submissions s
                    JOIN assignments a ON s.assignment_id = a.id
                    WHERE s.grade IS NOT NULL
                      AND s.submission_date > a.due_date
                ''')
                late_ids = [r[0] for r in cursor.fetchall()]

                for sub_id in late_ids:
                    result = self._compute_penalty(cursor, sub_id)
                    if result is None:
                        skipped += 1
                        continue

                    if result['days_late'] == 0:
                        skipped += 1
                        continue

                    # Mark late pass as used if applicable
                    if result['late_pass_id']:
                        cursor.execute(
                            'UPDATE late_passes SET used = 1 WHERE id = ?',
                            (result['late_pass_id'],))
                        skipped += 1
                        continue

                    # Apply adjusted grade
                    try:
                        cursor.execute('''
                            UPDATE assignment_submissions
                            SET grade = ?, feedback = COALESCE(feedback, '') ||
                                char(10) || '[Late penalty applied: -' || ? ||
                                ' (' || ? || ' day(s) late, policy: ' || ? || ')]'
                            WHERE id = ?
                        ''', (result['adjusted_grade'],
                              result['penalty_amount'],
                              result['days_late'],
                              result['policy_name'],
                              sub_id))
                        applied += 1
                    except Exception:
                        errors += 1

                conn.commit()
            finally:
                conn.close()

            messagebox.showinfo(
                "Batch Apply Complete",
                f"Penalties applied: {applied}\n"
                f"Skipped (on time / late pass / no policy): {skipped}\n"
                f"Errors: {errors}")
        except Exception as e:
            messagebox.showerror("Error", f"Batch apply failed: {e}")

    # ------------------------------------------------------------------ #
    #  Late submission report                                             #
    # ------------------------------------------------------------------ #

    def show_late_submission_report(self):
        """Report of all late submissions with penalties applied"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied",
                                   "You do not have permission to view this report.")
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area,
                          text="Late Submission Report",
                          style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Toolbar
        toolbar = ttk.Frame(self.gui.layout.content_area)
        toolbar.pack(fill='x', pady=(0, 10))
        ttk.Button(toolbar, text="Back to Policies",
                   command=self.show_late_policies).pack(side='left', padx=(0, 5))
        ttk.Button(toolbar, text="Refresh",
                   command=self.show_late_submission_report).pack(side='left')

        # Report treeview
        report_frame = ttk.Frame(self.gui.layout.content_area)
        report_frame.pack(fill='both', expand=True)

        columns = ('Sub ID', 'Student', 'Assignment', 'Due Date',
                   'Submitted', 'Days Late', 'Original', 'Adjusted', 'Policy',
                   'Late Pass')
        report_tree = ttk.Treeview(report_frame, columns=columns,
                                   show='headings', height=18)
        col_widths = {
            'Sub ID': 55, 'Student': 100, 'Assignment': 150,
            'Due Date': 130, 'Submitted': 130, 'Days Late': 70,
            'Original': 70, 'Adjusted': 70, 'Policy': 110, 'Late Pass': 70,
        }
        for col in columns:
            report_tree.heading(col, text=col)
            report_tree.column(col, width=col_widths.get(col, 90), anchor='center')

        v_scroll = ttk.Scrollbar(report_frame, orient='vertical',
                                 command=report_tree.yview)
        h_scroll = ttk.Scrollbar(report_frame, orient='horizontal',
                                 command=report_tree.xview)
        report_tree.configure(yscrollcommand=v_scroll.set,
                              xscrollcommand=h_scroll.set)
        report_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')
        report_frame.columnconfigure(0, weight=1)
        report_frame.rowconfigure(0, weight=1)

        # Summary label
        summary_var = tk.StringVar(value="Loading...")
        ttk.Label(self.gui.layout.content_area,
                  textvariable=summary_var).pack(anchor='w', pady=(10, 0))

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT s.id, s.student_id, a.title, a.due_date,
                           s.submission_date, s.grade
                    FROM assignment_submissions s
                    JOIN assignments a ON s.assignment_id = a.id
                    WHERE s.submission_date > a.due_date
                    ORDER BY s.submission_date DESC
                ''')
                rows = cursor.fetchall()

                total_late = len(rows)
                total_penalised = 0

                for row in rows:
                    sub_id, student_id, atitle, due, submitted, grade = row
                    result = self._compute_penalty(cursor, sub_id)

                    if result:
                        days_late = result['days_late']
                        original = result['original_grade']
                        adjusted = result['adjusted_grade']
                        policy_name = result['policy_name']
                        has_pass = "Yes" if result['has_late_pass'] else "No"
                        if result['penalty_amount'] > 0:
                            total_penalised += 1
                    else:
                        days_late = '?'
                        original = grade if grade is not None else 'N/A'
                        adjusted = 'N/A'
                        policy_name = 'None'
                        has_pass = 'N/A'

                    report_tree.insert('', 'end', values=(
                        sub_id, student_id, atitle, due, submitted,
                        days_late, original, adjusted, policy_name, has_pass))

                summary_var.set(
                    f"Total late submissions: {total_late}  |  "
                    f"Penalised: {total_penalised}  |  "
                    f"Unpenalised: {total_late - total_penalised}")
            finally:
                conn.close()
        except Exception as e:
            summary_var.set(f"Error loading report: {e}")

    # ------------------------------------------------------------------ #
    #  Late passes                                                        #
    # ------------------------------------------------------------------ #

    def _show_late_passes(self):
        """Show and manage late passes"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied",
                                   "You do not have permission to manage late passes.")
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area,
                          text="Late Pass Management",
                          style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        toolbar = ttk.Frame(self.gui.layout.content_area)
        toolbar.pack(fill='x', pady=(0, 10))
        ttk.Button(toolbar, text="Grant Late Pass",
                   command=self._grant_late_pass_dialog).pack(side='left', padx=(0, 5))
        ttk.Button(toolbar, text="Back to Policies",
                   command=self.show_late_policies).pack(side='left', padx=(0, 5))
        ttk.Button(toolbar, text="Refresh",
                   command=self._show_late_passes).pack(side='right')

        # Late passes treeview
        tree_frame = ttk.Frame(self.gui.layout.content_area)
        tree_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Student', 'Assignment', 'Used', 'Granted By',
                   'Granted At', 'Reason')
        self.passes_tree = ttk.Treeview(tree_frame, columns=columns,
                                        show='headings', height=14)
        col_widths = {
            'ID': 40, 'Student': 100, 'Assignment': 140, 'Used': 50,
            'Granted By': 100, 'Granted At': 130, 'Reason': 200,
        }
        for col in columns:
            self.passes_tree.heading(col, text=col)
            self.passes_tree.column(col, width=col_widths.get(col, 100))

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical',
                                  command=self.passes_tree.yview)
        self.passes_tree.configure(yscrollcommand=scrollbar.set)
        self.passes_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Revoke button
        ttk.Button(self.gui.layout.content_area, text="Revoke Selected Pass",
                   command=self._revoke_late_pass).pack(anchor='w', pady=(10, 0))

        self._load_late_passes()

    def _load_late_passes(self):
        """Load late passes into the treeview"""
        for item in self.passes_tree.get_children():
            self.passes_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT lp.id, lp.student_id, a.title, lp.used,
                           lp.granted_by, lp.granted_at, lp.reason
                    FROM late_passes lp
                    LEFT JOIN assignments a ON lp.assignment_id = a.id
                    ORDER BY lp.granted_at DESC
                ''')
                for row in cursor.fetchall():
                    pid, student, atitle, used, granted_by, granted_at, reason = row
                    used_str = "Yes" if used else "No"
                    atitle = atitle or "Any"
                    self.passes_tree.insert('', 'end', iid=str(pid),
                                            values=(pid, student, atitle,
                                                    used_str, granted_by or '',
                                                    granted_at, reason or ''))
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load late passes: {e}")

    def _grant_late_pass_dialog(self):
        """Dialog to grant a late pass to a student"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Grant Late Pass")
        dialog.geometry("420x320")
        dialog.transient(self.root)
        dialog.grab_set()

        row = 0
        ttk.Label(dialog, text="Student ID:").grid(
            row=row, column=0, sticky='w', padx=10, pady=5)
        student_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=student_var, width=30).grid(
            row=row, column=1, sticky='w', padx=10, pady=5)

        row += 1
        ttk.Label(dialog, text="Assignment (optional):").grid(
            row=row, column=0, sticky='w', padx=10, pady=5)
        assignment_var = tk.StringVar()
        assignment_combo = ttk.Combobox(dialog, textvariable=assignment_var,
                                        state='readonly', width=28)
        assignment_combo.grid(row=row, column=1, sticky='w', padx=10, pady=5)

        assignment_map = {'(Any Assignment)': None}
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, title, module_code FROM assignments
                    WHERE is_active = 1 ORDER BY title
                ''')
                items = ['(Any Assignment)']
                for aid, atitle, mcode in cursor.fetchall():
                    display = f"{atitle} ({mcode}) [ID: {aid}]"
                    items.append(display)
                    assignment_map[display] = aid
                assignment_combo['values'] = items
                assignment_combo.current(0)
            finally:
                conn.close()
        except Exception:
            assignment_combo['values'] = ['(Any Assignment)']
            assignment_combo.current(0)

        row += 1
        ttk.Label(dialog, text="Reason:").grid(
            row=row, column=0, sticky='nw', padx=10, pady=5)
        reason_text = scrolledtext.ScrolledText(dialog, width=28, height=4)
        reason_text.grid(row=row, column=1, sticky='w', padx=10, pady=5)

        def do_grant():
            sid = student_var.get().strip()
            if not sid:
                messagebox.showwarning("Validation", "Student ID is required.")
                return
            aid = assignment_map.get(assignment_var.get())
            reason = reason_text.get('1.0', 'end-1c').strip()

            granted_by = ''
            try:
                if self.auth and self.auth.current_user:
                    granted_by = (self.auth.current_user.get('username', '')
                                  or self.auth.current_user.get('id', ''))
            except Exception:
                pass

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO late_passes
                        (student_id, assignment_id, used, granted_by, reason)
                        VALUES (?, ?, 0, ?, ?)
                    ''', (sid, aid, granted_by, reason))
                    conn.commit()
                finally:
                    conn.close()
                dialog.destroy()
                messagebox.showinfo("Success", "Late pass granted.")
                self._load_late_passes()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to grant late pass: {e}")

        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=row + 1, column=0, columnspan=2, pady=10, padx=10,
                       sticky='w')
        ttk.Button(btn_frame, text="Grant", command=do_grant).pack(
            side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left')

    def _revoke_late_pass(self):
        """Revoke (delete) the selected late pass"""
        sel = self.passes_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a late pass to revoke.")
            return
        pass_id = int(self.passes_tree.item(sel[0], 'values')[0])

        if not messagebox.askyesno("Confirm", "Revoke this late pass?"):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM late_passes WHERE id = ?', (pass_id,))
                conn.commit()
            finally:
                conn.close()
            messagebox.showinfo("Revoked", "Late pass revoked.")
            self._load_late_passes()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to revoke late pass: {e}")
