"""Dialog windows for the Exam Scheduling System."""

import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict

# i18n import
try:
    from education_system.post_18.university_system.core.i18n import get_text as _
except ImportError:
    def _(key, **kwargs):
        return key


class DialogsMixin:
    """Mixin providing dialog windows and advanced features."""

    def check_room_availability(self):
        """Check if the selected room is available at the selected time."""
        date = self.exam_vars['date'].get()
        start = self.exam_vars['start_time'].get()
        end = self.exam_vars['end_time'].get()
        room_selection = self.room_var.get()

        if not all([date, start, end, room_selection]):
            messagebox.showwarning("Incomplete", "Please fill in date, start time, end time, and room")
            return

        room_name = room_selection.split(' (')[0]

        # Get conflicting exams
        conflicts = self.data_manager.get_conflicting_exams(
            date, start, end, room_name,
            exclude_id=self.selected_exam_id
        )

        if conflicts:
            conflict_info = "\n".join([
                f"• {e.module_code} ({e.start_time}-{e.end_time})"
                for e in conflicts
            ])
            messagebox.showwarning(
                "Room Conflict",
                f"Room {room_name} has conflicts:\n\n{conflict_info}"
            )
        else:
            messagebox.showinfo(
                "Available",
                f"✓ Room {room_name} is available on {date} from {start} to {end}"
            )

    def validate_room_capacity(self):
        """Check if room capacity is sufficient for enrolled students."""
        room_selection = self.room_var.get()
        if not room_selection:
            messagebox.showwarning("No Room", "Please select a room first")
            return

        # Find the room
        room_name = room_selection.split(' (')[0]
        room = next((r for r in self.data_manager.rooms if r.name == room_name), None)

        if not room:
            return

        student_count = len(self.enrolled_student_ids)

        if student_count == 0:
            messagebox.showinfo("No Students", "No students enrolled yet")
            return

        if room.capacity < student_count:
            messagebox.showwarning(
                "Insufficient Capacity",
                f"⚠ Room capacity: {room.capacity}\n"
                f"Students enrolled: {student_count}\n"
                f"Shortage: {student_count - room.capacity} seats"
            )
        else:
            spare = room.capacity - student_count
            messagebox.showinfo(
                "Capacity OK",
                f"✓ Room capacity: {room.capacity}\n"
                f"Students enrolled: {student_count}\n"
                f"Spare seats: {spare}"
            )

    def check_instructor_availability(self):
        """Check if the selected instructor has conflicts."""
        date = self.exam_vars['date'].get()
        start = self.exam_vars['start_time'].get()
        end = self.exam_vars['end_time'].get()
        instructor_id = self.get_selected_instructor_id()

        if not all([date, start, end]):
            messagebox.showwarning("Incomplete", "Please fill in date, start time, and end time first")
            return

        if not instructor_id:
            messagebox.showwarning("No Instructor", "Please select an instructor first")
            return

        # Get conflicting exams
        conflicts = self.data_manager.check_instructor_conflict(
            date, start, end, instructor_id,
            exclude_id=self.selected_exam_id
        )

        instructor_name = self.get_instructor_display_name()

        if conflicts:
            conflict_info = "\n".join([
                f"• {e.module_code} in {e.room} ({e.start_time}-{e.end_time})"
                for e in conflicts
            ])
            messagebox.showwarning(
                "Instructor Conflict",
                f"{instructor_name} has conflicts on {date}:\n\n{conflict_info}"
            )
        else:
            messagebox.showinfo(
                "Available",
                f"✓ {instructor_name} is available on {date} from {start} to {end}"
            )

    def show_advanced_filters(self):
        """Show advanced filtering dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Advanced Filters")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Date range filter
        ttk.Label(frame, text="Date Range:", font=('Helvetica', 10, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )

        ttk.Label(frame, text="From:").grid(row=1, column=0, sticky=tk.W, pady=5)
        start_date_var = tk.StringVar()
        ttk.Entry(frame, textvariable=start_date_var, width=15).grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Label(frame, text="To:").grid(row=2, column=0, sticky=tk.W, pady=5)
        end_date_var = tk.StringVar()
        ttk.Entry(frame, textvariable=end_date_var, width=15).grid(row=2, column=1, sticky=tk.W, pady=5)

        # Instructor filter
        ttk.Label(frame, text="Instructor:", font=('Helvetica', 10, 'bold')).grid(
            row=3, column=0, columnspan=2, sticky=tk.W, pady=(15, 10)
        )

        instructor_var = tk.StringVar()
        instructor_combo = ttk.Combobox(frame, textvariable=instructor_var, state='readonly', width=25)
        instructor_names = ["All"] + [f"{i['display_name']}" for i in self.data_manager.get_instructors()]
        instructor_combo['values'] = instructor_names
        instructor_combo.set("All")
        instructor_combo.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Room filter
        ttk.Label(frame, text="Room:", font=('Helvetica', 10, 'bold')).grid(
            row=5, column=0, columnspan=2, sticky=tk.W, pady=(15, 10)
        )

        room_var = tk.StringVar()
        room_combo = ttk.Combobox(frame, textvariable=room_var, state='readonly', width=25)
        room_names = ["All"] + [r.name for r in self.data_manager.rooms]
        room_combo['values'] = room_names
        room_combo.set("All")
        room_combo.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=5)

        def apply_filters():
            """Apply the selected filters."""
            # Clear current view
            for item in self.schedule_tree.get_children():
                self.schedule_tree.delete(item)

            # Start with all exams
            filtered_exams = list(self.data_manager.exams)

            # Apply date range filter
            start_date = start_date_var.get().strip()
            end_date = end_date_var.get().strip()
            if start_date and end_date:
                try:
                    filtered_exams = self.data_manager.get_exams_by_date_range(start_date, end_date)
                except (ValueError, TypeError):
                    messagebox.showerror("Error", "Invalid date range")
                    return

            # Apply instructor filter
            instructor_sel = instructor_var.get()
            if instructor_sel and instructor_sel != "All":
                instructor_id = None
                for inst in self.data_manager.get_instructors():
                    if inst['display_name'] == instructor_sel:
                        instructor_id = inst['id']
                        break
                if instructor_id:
                    filtered_exams = [e for e in filtered_exams if e.instructor_id == instructor_id]

            # Apply room filter
            room_sel = room_var.get()
            if room_sel and room_sel != "All":
                filtered_exams = [e for e in filtered_exams if e.room == room_sel]

            # Display filtered results
            for exam in sorted(filtered_exams, key=lambda x: (x.date, x.start_time)):
                time_str = f"{exam.start_time} - {exam.end_time}"
                self.schedule_tree.insert('', tk.END, values=(
                    exam.id, exam.module_code, exam.module_name, exam.date,
                    time_str, exam.room, exam.instructor_name, exam.students_enrolled
                ))

            messagebox.showinfo("Filters Applied", f"Showing {len(filtered_exams)} exams")
            dialog.destroy()

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="Apply", command=apply_filters).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def export_selected_exams(self):
        """Export selected exams from the schedule view."""
        selected_items = self.schedule_tree.selection()

        if not selected_items:
            messagebox.showwarning("No Selection", "Please select exams to export")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="selected_exams.csv"
        )

        if not filepath:
            return

        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Module Code', 'Module Name', 'Date', 'Start Time',
                               'End Time', 'Room', 'Instructor', 'Students'])

                for item in selected_items:
                    values = self.schedule_tree.item(item)['values']
                    exam_id = values[0]
                    exam = next((e for e in self.data_manager.exams if e.id == exam_id), None)
                    if exam:
                        writer.writerow([
                            exam.module_code, exam.module_name, exam.date,
                            exam.start_time, exam.end_time, exam.room,
                            exam.instructor_name, exam.students_enrolled
                        ])

            messagebox.showinfo("Success", f"Exported {len(selected_items)} exams to:\n{filepath}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")

    def suggest_available_rooms(self):
        """Show available rooms based on current date/time/capacity requirements."""
        date = self.exam_vars['date'].get()
        start = self.exam_vars['start_time'].get()
        end = self.exam_vars['end_time'].get()

        if not all([date, start, end]):
            messagebox.showwarning("Incomplete", "Please fill in date, start time, and end time first")
            return

        # Get minimum capacity requirement
        min_capacity = len(self.enrolled_student_ids)

        # Get available rooms — route through the shared cross-services
        # finder so Exam, Module, and Course schedulers all use the same
        # algorithm. Falls back to the legacy data-manager helper if the
        # shared service can't be loaded.
        try:
            from education_system.post_18.university_system.modules.domain.academics.gui._cross_services import (
                find_free_rooms,
            )
            free_rows = find_free_rooms(
                on_date=date,
                start_time=start, end_time=end,
                min_capacity=min_capacity,
                exclude_exam_id=self.selected_exam_id,
            )
            # Adapt the dict rows to objects the existing render loop
            # below understands (it accesses .name, .building, etc.).
            class _R:
                def __init__(self, d):
                    self.name = d.get("name", "")
                    self.building = d.get("building", "")
                    self.capacity = d.get("capacity", 0) or 0
                    self.has_projector = bool(d.get("has_projector"))
                    self.has_computers = bool(d.get("has_computers"))
            available_rooms = [_R(r) for r in free_rows] if free_rows else None
        except Exception:
            available_rooms = None

        if available_rooms is None:
            available_rooms = self.data_manager.get_available_rooms(
                date, start, end, min_capacity,
                exclude_id=self.selected_exam_id
            )

        if not available_rooms:
            messagebox.showinfo(
                "No Rooms Available",
                f"No rooms available on {date} from {start} to {end}\n"
                f"with capacity >= {min_capacity}"
            )
            return

        # Show dialog with available rooms
        dialog = tk.Toplevel(self.root)
        dialog.title("Available Rooms")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text=f"Available rooms on {date} from {start} to {end}:",
            font=('Helvetica', 11, 'bold')
        ).pack(pady=(0, 10))

        # Create treeview for rooms
        columns = ('name', 'building', 'capacity', 'facilities')
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=12)

        tree.heading('name', text='Room')
        tree.heading('building', text='Building')
        tree.heading('capacity', text='Capacity')
        tree.heading('facilities', text='Facilities')

        tree.column('name', width=100)
        tree.column('building', width=120)
        tree.column('capacity', width=80)
        tree.column('facilities', width=180)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Populate with available rooms
        for room in sorted(available_rooms, key=lambda r: r.capacity, reverse=True):
            facilities = []
            if room.has_computers:
                facilities.append("Computers")
            if room.has_projector:
                facilities.append("Projector")
            facilities_str = ", ".join(facilities) if facilities else "None"

            # Highlight if capacity is just right
            tag = 'suitable' if min_capacity > 0 and room.capacity >= min_capacity and room.capacity < min_capacity * 1.5 else ''

            tree.insert('', tk.END, values=(
                room.name, room.building, room.capacity, facilities_str
            ), tags=(tag,))

        tree.tag_configure('suitable', background='lightgreen')

        def select_room():
            """Select the room from the dialog."""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a room")
                return

            item = tree.item(selection[0])
            room_name = item['values'][0]
            room = next((r for r in available_rooms if r.name == room_name), None)
            if room:
                self.room_var.set(f"{room.name} ({room.building}) - Cap: {room.capacity}")
                dialog.destroy()

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="Select Room", command=select_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        if min_capacity > 0:
            ttk.Label(
                frame,
                text=f"Rooms highlighted in green are suitable for {min_capacity} students",
                font=('Helvetica', 8, 'italic'),
                foreground='darkgreen'
            ).pack(pady=(5, 0))

    def find_all_conflicts(self):
        """Find and display all scheduling conflicts."""
        conflicts_found = []

        # Check for room conflicts
        for i, exam1 in enumerate(self.data_manager.exams):
            for exam2 in self.data_manager.exams[i+1:]:
                # Same room and date
                if exam1.date == exam2.date and exam1.room == exam2.room:
                    # Check time overlap
                    if not (exam2.end_time <= exam1.start_time or exam2.start_time >= exam1.end_time):
                        conflicts_found.append({
                            'type': 'Room',
                            'location': exam1.room,
                            'date': exam1.date,
                            'exam1': f"{exam1.module_code} ({exam1.start_time}-{exam1.end_time})",
                            'exam2': f"{exam2.module_code} ({exam2.start_time}-{exam2.end_time})"
                        })

                # Same instructor and date
                if (exam1.date == exam2.date and
                    exam1.instructor_id and exam2.instructor_id and
                    exam1.instructor_id == exam2.instructor_id):
                    # Check time overlap
                    if not (exam2.end_time <= exam1.start_time or exam2.start_time >= exam1.end_time):
                        conflicts_found.append({
                            'type': 'Instructor',
                            'location': exam1.instructor_name,
                            'date': exam1.date,
                            'exam1': f"{exam1.module_code} in {exam1.room} ({exam1.start_time}-{exam1.end_time})",
                            'exam2': f"{exam2.module_code} in {exam2.room} ({exam2.start_time}-{exam2.end_time})"
                        })

        if not conflicts_found:
            messagebox.showinfo("No Conflicts", "✓ No scheduling conflicts found!")
            return

        # Show conflicts dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Scheduling Conflicts")
        dialog.geometry("700x400")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text=f"⚠ Found {len(conflicts_found)} conflict(s):",
            font=('Helvetica', 12, 'bold'),
            foreground='red'
        ).pack(pady=(0, 10))

        # Create treeview for conflicts
        columns = ('type', 'location', 'date', 'exam1', 'exam2')
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=12)

        tree.heading('type', text='Type')
        tree.heading('location', text='Resource')
        tree.heading('date', text='Date')
        tree.heading('exam1', text='Exam 1')
        tree.heading('exam2', text='Exam 2')

        tree.column('type', width=80)
        tree.column('location', width=120)
        tree.column('date', width=100)
        tree.column('exam1', width=180)
        tree.column('exam2', width=180)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Populate with conflicts
        for conflict in conflicts_found:
            tree.insert('', tk.END, values=(
                conflict['type'],
                conflict['location'],
                conflict['date'],
                conflict['exam1'],
                conflict['exam2']
            ))

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="Export to CSV", command=lambda: self.export_conflicts(conflicts_found)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def export_conflicts(self, conflicts: List[Dict]):
        """Export conflicts to CSV file."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="exam_conflicts.csv"
        )

        if not filepath:
            return

        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['type', 'location', 'date', 'exam1', 'exam2'])
                writer.writeheader()
                writer.writerows(conflicts)

            messagebox.showinfo("Success", f"Exported {len(conflicts)} conflicts to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")
