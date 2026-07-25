"""Instructor-side Office Hours management GUI.

Provides a Treeview-based interface for instructors to create, edit, and
delete their office hours, as well as view bookings made by students.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

TIME_SLOTS = [f"{h:02d}:{m:02d}" for h in range(7, 22) for m in (0, 30)]

DAYS_OF_WEEK = [
    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
]


class InstructorManager:
    """Manages the instructor view for office hours."""

    def __init__(self, parent, service, auth):
        self.parent = parent
        self.service = service
        self.auth = auth
        self._setup_ui()
        self._refresh_hours()

    # ------------------------------------------------------------------ #
    #  UI setup
    # ------------------------------------------------------------------ #

    def _setup_ui(self):
        """Build the instructor management interface."""
        # Main container
        main_frame = ttk.Frame(self.parent, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ---- Office Hours list ---- #
        list_frame = ttk.LabelFrame(main_frame, text="My Office Hours", padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('id', 'day', 'start', 'end', 'location', 'capacity', 'active')
        self.hours_tree = ttk.Treeview(
            list_frame, columns=columns, show='headings', height=8,
        )
        for col in columns:
            self.hours_tree.heading(col, text=col.title())
            self.hours_tree.column(col, width=100)
        self.hours_tree.column('id', width=50)
        self.hours_tree.column('active', width=60)

        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.hours_tree.yview,
        )
        self.hours_tree.configure(yscrollcommand=scrollbar.set)
        self.hours_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Buttons ---- #
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(btn_frame, text="Create", command=self._create_hours).pack(
            side=tk.LEFT, padx=5,
        )
        ttk.Button(btn_frame, text="Edit", command=self._edit_hours).pack(
            side=tk.LEFT, padx=5,
        )
        ttk.Button(btn_frame, text="Delete", command=self._delete_hours).pack(
            side=tk.LEFT, padx=5,
        )
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_hours).pack(
            side=tk.LEFT, padx=5,
        )

        # ---- Bookings section ---- #
        bookings_frame = ttk.LabelFrame(
            main_frame, text="Bookings for My Hours", padding="5",
        )
        bookings_frame.pack(fill=tk.BOTH, expand=True)

        booking_cols = ('id', 'student', 'date', 'day', 'time', 'status', 'notes')
        self.bookings_tree = ttk.Treeview(
            bookings_frame, columns=booking_cols, show='headings', height=6,
        )
        for col in booking_cols:
            self.bookings_tree.heading(col, text=col.title())
            self.bookings_tree.column(col, width=100)
        self.bookings_tree.column('id', width=50)

        booking_scrollbar = ttk.Scrollbar(
            bookings_frame, orient=tk.VERTICAL, command=self.bookings_tree.yview,
        )
        self.bookings_tree.configure(yscrollcommand=booking_scrollbar.set)
        self.bookings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        booking_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        booking_btn_frame = ttk.Frame(bookings_frame)
        booking_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(
            booking_btn_frame, text="Refresh Bookings",
            command=self._refresh_bookings,
        ).pack(pady=5)

    # ------------------------------------------------------------------ #
    #  Data operations
    # ------------------------------------------------------------------ #

    def _get_instructor_id(self):
        """Return the current instructor's user ID."""
        if self.auth and self.auth.current_user:
            return self.auth.current_user.get('username', '')
        return ''

    def _refresh_hours(self):
        """Reload the instructor's office hours into the Treeview."""
        for item in self.hours_tree.get_children():
            self.hours_tree.delete(item)

        instructor_id = self._get_instructor_id()
        if not instructor_id:
            return

        try:
            hours = self.service.get_available_office_hours(
                instructor_id=instructor_id,
            )
            for h in hours:
                self.hours_tree.insert('', tk.END, values=(
                    h['id'],
                    h['day_of_week'],
                    h['start_time'],
                    h['end_time'],
                    h['location'],
                    h['capacity'],
                    'Yes' if h.get('is_active', 1) else 'No',
                ))
        except Exception as e:
            logger.error("Error refreshing office hours: %s", e)
            messagebox.showerror("Error", f"Failed to load office hours:\n{e}")

    def _refresh_bookings(self):
        """Reload bookings for the instructor's office hours."""
        for item in self.bookings_tree.get_children():
            self.bookings_tree.delete(item)

        instructor_id = self._get_instructor_id()
        if not instructor_id:
            return

        try:
            bookings = self.service.get_instructor_bookings(instructor_id)
            for b in bookings:
                time_str = f"{b['start_time']}-{b['end_time']}"
                self.bookings_tree.insert('', tk.END, values=(
                    b['id'],
                    b['student_id'],
                    b['booking_date'],
                    b['day_of_week'],
                    time_str,
                    b['status'],
                    b.get('notes', '') or '',
                ))
        except Exception as e:
            logger.error("Error refreshing bookings: %s", e)
            messagebox.showerror("Error", f"Failed to load bookings:\n{e}")

    # ------------------------------------------------------------------ #
    #  Create dialog
    # ------------------------------------------------------------------ #

    def _create_hours(self):
        """Show a dialog to create new office hours."""
        # Fetch buildings for location dropdown
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT building_name, building_code FROM buildings "
                "WHERE is_active = 1 ORDER BY building_name"
            )
            buildings = cursor.fetchall()
            conn.close()
        except Exception as e:
            logger.error("Error fetching buildings: %s", e)
            buildings = []

        if not buildings:
            messagebox.showwarning(
                "No Buildings",
                "No active buildings found. Cannot create office hours.",
            )
            return

        location_values = [
            f"{row['building_name']} ({row['building_code']})"
            for row in buildings
        ]

        dialog = tk.Toplevel(self.parent)
        dialog.title("Create Office Hours")
        dialog.geometry("400x350")
        dialog.transient(self.parent)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)

        # Day of week
        ttk.Label(frame, text="Day of Week:").grid(
            row=0, column=0, sticky=tk.W, pady=5,
        )
        day_var = tk.StringVar(value=DAYS_OF_WEEK[0])
        day_combo = ttk.Combobox(
            frame, textvariable=day_var, values=DAYS_OF_WEEK,
            state='readonly', width=20,
        )
        day_combo.grid(row=0, column=1, sticky=tk.W, pady=5)

        # Start time
        ttk.Label(frame, text="Start Time:").grid(
            row=1, column=0, sticky=tk.W, pady=5,
        )
        start_var = tk.StringVar(value=TIME_SLOTS[0])
        ttk.Combobox(
            frame, textvariable=start_var, values=TIME_SLOTS,
            state='readonly', width=20,
        ).grid(row=1, column=1, sticky=tk.W, pady=5)

        # End time
        ttk.Label(frame, text="End Time:").grid(
            row=2, column=0, sticky=tk.W, pady=5,
        )
        end_var = tk.StringVar(value=TIME_SLOTS[2])
        ttk.Combobox(
            frame, textvariable=end_var, values=TIME_SLOTS,
            state='readonly', width=20,
        ).grid(row=2, column=1, sticky=tk.W, pady=5)

        # Location
        ttk.Label(frame, text="Location:").grid(
            row=3, column=0, sticky=tk.W, pady=5,
        )
        location_var = tk.StringVar()
        ttk.Combobox(
            frame, textvariable=location_var, values=location_values,
            state='readonly', width=20,
        ).grid(row=3, column=1, sticky=tk.W, pady=5)

        # Capacity
        ttk.Label(frame, text="Capacity:").grid(
            row=4, column=0, sticky=tk.W, pady=5,
        )
        capacity_var = tk.StringVar(value='5')
        ttk.Entry(frame, textvariable=capacity_var, width=22).grid(
            row=4, column=1, sticky=tk.W, pady=5,
        )

        # Notes
        ttk.Label(frame, text="Notes (optional):").grid(
            row=5, column=0, sticky=tk.W, pady=5,
        )
        notes_var = tk.StringVar()
        ttk.Entry(frame, textvariable=notes_var, width=22).grid(
            row=5, column=1, sticky=tk.W, pady=5,
        )

        def _on_save():
            day = day_var.get().strip()
            start = start_var.get().strip()
            end = end_var.get().strip()
            location = location_var.get().strip()
            cap_str = capacity_var.get().strip()
            notes = notes_var.get().strip()

            if not start or not end or not location:
                messagebox.showwarning(
                    "Missing Fields",
                    "Start time, end time, and location are required.",
                    parent=dialog,
                )
                return

            try:
                capacity = int(cap_str) if cap_str else 5
            except ValueError:
                messagebox.showwarning(
                    "Invalid Capacity",
                    "Capacity must be a whole number.",
                    parent=dialog,
                )
                return

            instructor_id = self._get_instructor_id()
            try:
                oh_id = self.service.create_office_hours(
                    instructor_id=instructor_id,
                    day_of_week=day,
                    start_time=start,
                    end_time=end,
                    location=location,
                    capacity=capacity,
                    notes=notes,
                )
                messagebox.showinfo(
                    "Success",
                    f"Office hours created (ID: {oh_id}).",
                    parent=dialog,
                )
                dialog.destroy()
                self._refresh_hours()
            except ValueError as e:
                messagebox.showwarning("Validation Error", str(e), parent=dialog)
            except Exception as e:
                logger.error("Error creating office hours: %s", e)
                messagebox.showerror(
                    "Error", f"Failed to create office hours:\n{e}",
                    parent=dialog,
                )

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Save", command=_on_save).pack(
            side=tk.LEFT, padx=10,
        )
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(
            side=tk.LEFT, padx=10,
        )

    # ------------------------------------------------------------------ #
    #  Edit dialog
    # ------------------------------------------------------------------ #

    def _edit_hours(self):
        """Show a dialog to edit the selected office hours."""
        selected = self.hours_tree.selection()
        if not selected:
            messagebox.showwarning(
                "No Selection",
                "Please select an office hours entry to edit.",
            )
            return

        values = self.hours_tree.item(selected[0], 'values')
        oh_id = int(values[0])

        # Fetch current data
        try:
            current = self.service.get_office_hours(oh_id)
            if not current:
                messagebox.showerror("Error", "Office hours record not found.")
                return
        except Exception as e:
            logger.error("Error fetching office hours %s: %s", oh_id, e)
            messagebox.showerror("Error", f"Failed to load office hours:\n{e}")
            return

        # Fetch buildings for location dropdown
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT building_name, building_code FROM buildings "
                "WHERE is_active = 1 ORDER BY building_name"
            )
            buildings = cursor.fetchall()
            conn.close()
        except Exception as e:
            logger.error("Error fetching buildings: %s", e)
            buildings = []

        if not buildings:
            messagebox.showwarning(
                "No Buildings",
                "No active buildings found. Cannot edit office hours.",
            )
            return

        location_values = [
            f"{row['building_name']} ({row['building_code']})"
            for row in buildings
        ]

        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Edit Office Hours (ID: {oh_id})")
        dialog.geometry("400x350")
        dialog.transient(self.parent)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)

        # Day of week
        ttk.Label(frame, text="Day of Week:").grid(
            row=0, column=0, sticky=tk.W, pady=5,
        )
        day_var = tk.StringVar(value=current.get('day_of_week', ''))
        day_combo = ttk.Combobox(
            frame, textvariable=day_var, values=DAYS_OF_WEEK,
            state='readonly', width=20,
        )
        day_combo.grid(row=0, column=1, sticky=tk.W, pady=5)

        # Start time
        ttk.Label(frame, text="Start Time:").grid(
            row=1, column=0, sticky=tk.W, pady=5,
        )
        start_var = tk.StringVar(value=current.get('start_time', ''))
        ttk.Combobox(
            frame, textvariable=start_var, values=TIME_SLOTS,
            state='readonly', width=20,
        ).grid(row=1, column=1, sticky=tk.W, pady=5)

        # End time
        ttk.Label(frame, text="End Time:").grid(
            row=2, column=0, sticky=tk.W, pady=5,
        )
        end_var = tk.StringVar(value=current.get('end_time', ''))
        ttk.Combobox(
            frame, textvariable=end_var, values=TIME_SLOTS,
            state='readonly', width=20,
        ).grid(row=2, column=1, sticky=tk.W, pady=5)

        # Location
        ttk.Label(frame, text="Location:").grid(
            row=3, column=0, sticky=tk.W, pady=5,
        )
        location_var = tk.StringVar(value=current.get('location', ''))
        ttk.Combobox(
            frame, textvariable=location_var, values=location_values,
            state='readonly', width=20,
        ).grid(row=3, column=1, sticky=tk.W, pady=5)

        # Capacity
        ttk.Label(frame, text="Capacity:").grid(
            row=4, column=0, sticky=tk.W, pady=5,
        )
        capacity_var = tk.StringVar(value=str(current.get('capacity', 5)))
        ttk.Entry(frame, textvariable=capacity_var, width=22).grid(
            row=4, column=1, sticky=tk.W, pady=5,
        )

        # Notes
        ttk.Label(frame, text="Notes:").grid(
            row=5, column=0, sticky=tk.W, pady=5,
        )
        notes_var = tk.StringVar(value=current.get('notes', '') or '')
        ttk.Entry(frame, textvariable=notes_var, width=22).grid(
            row=5, column=1, sticky=tk.W, pady=5,
        )

        def _on_save():
            updates = {}

            day = day_var.get().strip()
            if day and day != current.get('day_of_week', ''):
                updates['day_of_week'] = day

            start = start_var.get().strip()
            if start and start != current.get('start_time', ''):
                updates['start_time'] = start

            end = end_var.get().strip()
            if end and end != current.get('end_time', ''):
                updates['end_time'] = end

            location = location_var.get().strip()
            if location and location != current.get('location', ''):
                updates['location'] = location

            cap_str = capacity_var.get().strip()
            if cap_str:
                try:
                    cap_int = int(cap_str)
                    if cap_int != current.get('capacity', 5):
                        updates['capacity'] = cap_int
                except ValueError:
                    messagebox.showwarning(
                        "Invalid Capacity",
                        "Capacity must be a whole number.",
                        parent=dialog,
                    )
                    return

            notes = notes_var.get().strip()
            if notes != (current.get('notes', '') or ''):
                updates['notes'] = notes

            if not updates:
                messagebox.showinfo(
                    "No Changes",
                    "No changes were made.",
                    parent=dialog,
                )
                dialog.destroy()
                return

            try:
                success = self.service.update_office_hours(oh_id, **updates)
                if success:
                    messagebox.showinfo(
                        "Success",
                        "Office hours updated successfully.",
                        parent=dialog,
                    )
                    dialog.destroy()
                    self._refresh_hours()
                else:
                    messagebox.showwarning(
                        "Not Updated",
                        "Office hours could not be updated.",
                        parent=dialog,
                    )
            except ValueError as e:
                messagebox.showwarning("Validation Error", str(e), parent=dialog)
            except Exception as e:
                logger.error("Error updating office hours %s: %s", oh_id, e)
                messagebox.showerror(
                    "Error", f"Failed to update office hours:\n{e}",
                    parent=dialog,
                )

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Save", command=_on_save).pack(
            side=tk.LEFT, padx=10,
        )
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(
            side=tk.LEFT, padx=10,
        )

    # ------------------------------------------------------------------ #
    #  Delete
    # ------------------------------------------------------------------ #

    def _delete_hours(self):
        """Delete (deactivate) the selected office hours."""
        selected = self.hours_tree.selection()
        if not selected:
            messagebox.showwarning(
                "No Selection",
                "Please select an office hours entry to delete.",
            )
            return

        values = self.hours_tree.item(selected[0], 'values')
        oh_id = int(values[0])
        day = values[1]
        start = values[2]
        end = values[3]

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete office hours {oh_id}\n"
            f"({day} {start}-{end})?",
        )
        if not confirm:
            return

        try:
            success = self.service.delete_office_hours(oh_id)
            if success:
                messagebox.showinfo("Success", "Office hours deleted.")
                self._refresh_hours()
            else:
                messagebox.showwarning(
                    "Not Deleted",
                    "Office hours not found or already inactive.",
                )
        except Exception as e:
            logger.error("Error deleting office hours %s: %s", oh_id, e)
            messagebox.showerror(
                "Error", f"Failed to delete office hours:\n{e}",
            )
