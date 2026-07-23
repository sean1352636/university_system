"""Group assignment management"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH

from education_system.post_18.university_system.modules.domain.academics.gui.assignment_system.group_manager.assignment_creation import AssignmentCreationMixin
from education_system.post_18.university_system.modules.domain.academics.gui.assignment_system.group_manager.configuration import ConfigurationMixin
from education_system.post_18.university_system.modules.domain.academics.gui.assignment_system.group_manager.management import ManagementMixin
from education_system.post_18.university_system.modules.domain.academics.gui.assignment_system.group_manager.student_actions import StudentActionsMixin


class GroupManager(AssignmentCreationMixin, ConfigurationMixin,
                   ManagementMixin, StudentActionsMixin):
    """Group assignment management"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def load_modules(self, combo):
        """Load available modules"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT module_code, module_name FROM modules ORDER BY module_code')
            modules = cursor.fetchall()

            module_list = [f"{code} - {name}" for code, name in modules]
            combo['values'] = module_list

            # Create mapping for easy lookup
            self.module_map = {f"{code} - {name}": code for code, name in modules}

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load modules: {e}")

    def load_assignments_for_group_filter(self, combo):
        """Load assignments that have groups"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT DISTINCT a.id, a.title
            FROM assignments a
            WHERE a.assignment_type = 'group'
            ORDER BY a.title
            ''')

            assignments = cursor.fetchall()
            conn.close()

            combo_values = ["All Assignments"] + [f"{aid} - {title}" for aid, title in assignments]
            combo['values'] = combo_values
            if combo_values:
                combo.current(0)

        except Exception as e:
            print(f"Error loading assignments: {e}")

    def create_group_assignment(self, *args, **kwargs):
        """Open the group assignment creation wizard."""
        self._launch_gui_feature(self.show_create_group_assignment, "group assignment creation")

    def show_manage_groups(self):
        """Entry point from navigation to the full group management interface."""
        self.manage_groups()
