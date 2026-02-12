"""TA Permissions management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

# Permission types that can be granted to TAs
PERMISSION_TYPES = [
    'grade_assignments',
    'take_attendance',
    'upload_materials',
    'manage_discussions',
    'view_student_info',
]

# Human-readable labels for each permission
PERMISSION_LABELS = {
    'grade_assignments': 'Grade Assignments',
    'take_attendance': 'Take Attendance',
    'upload_materials': 'Upload Materials',
    'manage_discussions': 'Manage Discussions',
    'view_student_info': 'View Student Info',
}


class PermissionsManager:
    """Manages TA permissions UI for granting and revoking module-level permissions."""

    def __init__(self, parent, service, auth):
        self.parent = parent
        self.service = service
        self.auth = auth
        self._perm_vars = {}
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the permissions management panel."""
        # Top section: TA and module selection
        selector_frame = ttk.LabelFrame(self.parent, text="Select TA and Module", padding=10)
        selector_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        row_frame_1 = ttk.Frame(selector_frame)
        row_frame_1.pack(fill=tk.X, pady=2)

        ttk.Label(row_frame_1, text="TA Assignment ID:").pack(side=tk.LEFT, padx=(0, 5))
        self.ta_id_var = tk.StringVar()
        ttk.Entry(row_frame_1, textvariable=self.ta_id_var, width=15).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(row_frame_1, text="Load TA", command=self._load_ta_info).pack(side=tk.LEFT, padx=5)

        row_frame_2 = ttk.Frame(selector_frame)
        row_frame_2.pack(fill=tk.X, pady=2)

        ttk.Label(row_frame_2, text="Module Code:").pack(side=tk.LEFT, padx=(0, 5))
        self.module_var = tk.StringVar()
        self.module_entry = ttk.Entry(row_frame_2, textvariable=self.module_var, width=20)
        self.module_entry.pack(side=tk.LEFT, padx=(0, 10))

        # TA info display
        self.info_frame = ttk.LabelFrame(self.parent, text="TA Information", padding=10)
        self.info_frame.pack(fill=tk.X, padx=10, pady=5)

        self.info_var = tk.StringVar(value="No TA loaded. Enter a TA Assignment ID and click 'Load TA'.")
        ttk.Label(self.info_frame, textvariable=self.info_var, wraplength=800).pack(anchor=tk.W)

        # Permissions section
        perm_outer_frame = ttk.LabelFrame(self.parent, text="Permissions", padding=10)
        perm_outer_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        desc_label = ttk.Label(
            perm_outer_frame,
            text="Select the permissions to grant to this TA for the specified module:",
        )
        desc_label.pack(anchor=tk.W, pady=(0, 10))

        # Checkbuttons for each permission
        self._perm_vars = {}
        for perm in PERMISSION_TYPES:
            var = tk.BooleanVar(value=False)
            self._perm_vars[perm] = var
            label = PERMISSION_LABELS.get(perm, perm)
            cb = ttk.Checkbutton(perm_outer_frame, text=label, variable=var)
            cb.pack(anchor=tk.W, padx=20, pady=2)

        # Current permissions display
        current_frame = ttk.LabelFrame(self.parent, text="Current Permissions", padding=10)
        current_frame.pack(fill=tk.X, padx=10, pady=5)

        self.current_perms_var = tk.StringVar(value="Load a TA to see current permissions.")
        ttk.Label(current_frame, textvariable=self.current_perms_var, wraplength=800).pack(anchor=tk.W)

        # Action buttons
        btn_frame = ttk.Frame(self.parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        ttk.Button(btn_frame, text="Save Permissions", command=self._save_permissions).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Select All", command=self._select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Clear All", command=self._clear_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_current_permissions).pack(side=tk.RIGHT, padx=5)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _load_ta_info(self):
        """Load TA details and populate the module code and info display."""
        ta_id_str = self.ta_id_var.get().strip()
        if not ta_id_str:
            messagebox.showwarning("Validation", "Please enter a TA Assignment ID.")
            return

        try:
            ta_id = int(ta_id_str)
        except ValueError:
            messagebox.showwarning("Validation", "TA Assignment ID must be a number.")
            return

        try:
            ta = self.service.get_ta(ta_id)
        except Exception as e:
            logger.error(f"Error loading TA info: {e}")
            messagebox.showerror("Error", f"Failed to load TA info:\n{e}")
            return

        if not ta:
            self.info_var.set(f"No TA assignment found with ID {ta_id}.")
            messagebox.showwarning("Not Found", f"No TA assignment found with ID {ta_id}.")
            return

        # Populate the info display
        info_text = (
            f"ID: {ta.get('id')}  |  "
            f"Student: {ta.get('student_id')}  |  "
            f"Module: {ta.get('module_code')}  |  "
            f"Role: {ta.get('role_type')}  |  "
            f"Hours/Week: {ta.get('hours_per_week')}  |  "
            f"Status: {ta.get('status')}"
        )
        self.info_var.set(info_text)

        # Auto-fill the module code if empty
        if not self.module_var.get().strip():
            self.module_var.set(ta.get('module_code', ''))

        # Load current permissions for this TA
        self._load_current_permissions()

    def _load_current_permissions(self):
        """Load and display current permissions for the selected TA and module."""
        ta_id_str = self.ta_id_var.get().strip()
        module_code = self.module_var.get().strip()

        if not ta_id_str:
            self.current_perms_var.set("Enter a TA Assignment ID first.")
            return

        try:
            ta_id = int(ta_id_str)
        except ValueError:
            self.current_perms_var.set("Invalid TA Assignment ID.")
            return

        if not module_code:
            # Try to get module from TA record
            try:
                ta = self.service.get_ta(ta_id)
                if ta:
                    module_code = ta.get('module_code', '')
                    self.module_var.set(module_code)
            except Exception:
                pass

        if not module_code:
            self.current_perms_var.set("Enter a module code to load permissions.")
            return

        try:
            current_permissions = self._fetch_permissions(ta_id, module_code)
        except Exception as e:
            logger.error(f"Error loading current permissions: {e}")
            self.current_perms_var.set(f"Error loading permissions: {e}")
            return

        # Update checkboxes to reflect current state
        for perm in PERMISSION_TYPES:
            self._perm_vars[perm].set(perm in current_permissions)

        # Update current permissions display
        if current_permissions:
            labels = [PERMISSION_LABELS.get(p, p) for p in sorted(current_permissions)]
            self.current_perms_var.set(f"Current permissions for module '{module_code}': {', '.join(labels)}")
        else:
            self.current_perms_var.set(f"No permissions currently set for module '{module_code}'.")

    def _fetch_permissions(self, ta_id, module_code):
        """Fetch current permission types for a TA on a module from the database.

        Args:
            ta_id: The TA assignment ID.
            module_code: The module code.

        Returns:
            A set of permission type strings currently granted.
        """
        permissions = set()
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT permission_type FROM ta_permissions WHERE ta_id = ? AND module_code = ?",
                    (ta_id, module_code),
                )
                rows = cursor.fetchall()
                for row in rows:
                    permissions.add(row[0])
        except Exception as e:
            logger.error(f"Error fetching permissions for ta_id={ta_id}, module={module_code}: {e}")
            raise
        return permissions

    def _save_permissions(self):
        """Save the selected permissions for the TA on the specified module."""
        ta_id_str = self.ta_id_var.get().strip()
        module_code = self.module_var.get().strip()

        if not ta_id_str:
            messagebox.showwarning("Validation", "Please enter a TA Assignment ID.")
            return

        try:
            ta_id = int(ta_id_str)
        except ValueError:
            messagebox.showwarning("Validation", "TA Assignment ID must be a number.")
            return

        if not module_code:
            messagebox.showwarning("Validation", "Please enter a module code.")
            return

        # Verify the TA exists and is active
        try:
            ta = self.service.get_ta(ta_id)
            if not ta:
                messagebox.showwarning("Not Found", f"No TA assignment found with ID {ta_id}.")
                return
            if ta.get('status') != 'active':
                messagebox.showwarning(
                    "Inactive TA",
                    f"TA assignment {ta_id} is not active. Cannot set permissions.",
                )
                return
        except Exception as e:
            logger.error(f"Error verifying TA: {e}")
            messagebox.showerror("Error", f"Failed to verify TA:\n{e}")
            return

        # Collect selected permissions
        selected = [perm for perm, var in self._perm_vars.items() if var.get()]

        # Determine the granting user
        granted_by = ''
        if self.auth and self.auth.current_user:
            granted_by = self.auth.current_user.get('username', '')

        # Confirm before saving
        if selected:
            labels = [PERMISSION_LABELS.get(p, p) for p in sorted(selected)]
            msg = (
                f"Set the following permissions for TA {ta_id} on module '{module_code}'?\n\n"
                + "\n".join(f"  - {lbl}" for lbl in labels)
            )
        else:
            msg = (
                f"Remove ALL permissions for TA {ta_id} on module '{module_code}'?\n\n"
                "This will clear all existing permissions."
            )

        if not messagebox.askyesno("Confirm Permissions", msg):
            return

        try:
            success = self.service.set_ta_permissions(
                ta_id=ta_id,
                permission_types=selected,
                module_code=module_code,
                granted_by=granted_by,
            )
            if success:
                messagebox.showinfo("Success", "Permissions updated successfully.")
                self._load_current_permissions()
            else:
                messagebox.showwarning("Failed", "Permissions could not be updated.")
        except ValueError as e:
            messagebox.showerror("Validation Error", str(e))
        except Exception as e:
            logger.error(f"Error saving permissions: {e}")
            messagebox.showerror("Error", f"Failed to save permissions:\n{e}")

    def _select_all(self):
        """Select all permission checkboxes."""
        for var in self._perm_vars.values():
            var.set(True)

    def _clear_all(self):
        """Clear all permission checkboxes."""
        for var in self._perm_vars.values():
            var.set(False)
