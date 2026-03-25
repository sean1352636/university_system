from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from education_system.university_system.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from education_system.university_system.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from education_system.university_system.modules.domain.academics.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility



from education_system.university_system.modules.domain.academics.gui.parent_portal.base import ParentPortalGUI

class AbsenceReportDialog:
    """Dialog for reporting absence with timetable selection"""

    def __init__(self, parent, children, db_path=None, is_admin=False, search_student_id=None):
        self.result = None
        self.db_path = db_path or DEFAULT_DB_PATH
        self.is_admin = is_admin
        self.children = children
        self.timetable_data = []
        self.selected_sessions = []

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Report Absence")
        self.dialog.geometry("800x750")
        self.dialog.minsize(750, 600)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center the dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 30, parent.winfo_rooty() + 20))

        # Create outer frame to hold canvas and scrollbar
        outer_frame = ttk.Frame(self.dialog)
        outer_frame.pack(fill=tk.BOTH, expand=True)

        # Create canvas for scrolling
        canvas = tk.Canvas(outer_frame, highlightthickness=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add scrollbar
        main_scrollbar = ttk.Scrollbar(outer_frame, orient="vertical", command=canvas.yview)
        main_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        canvas.configure(yscrollcommand=main_scrollbar.set)

        # Create main frame inside canvas
        main_frame = ttk.Frame(canvas, padding=20)
        canvas_window = canvas.create_window((0, 0), window=main_frame, anchor="nw")

        # Configure canvas scrolling
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def configure_canvas_width(event):
            canvas.itemconfig(canvas_window, width=event.width)

        main_frame.bind("<Configure>", configure_scroll_region)
        canvas.bind("<Configure>", configure_canvas_width)

        # Enable mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)
        canvas.bind_all("<Button-4>", on_mousewheel_linux)
        canvas.bind_all("<Button-5>", on_mousewheel_linux)

        # Unbind mousewheel when dialog closes
        def on_close():
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")
            self.dialog.destroy()

        self.dialog.protocol("WM_DELETE_WINDOW", on_close)

        ttk.Label(main_frame, text="Report Student Absence", font=('Arial', 16, 'bold')).pack(pady=10)

        # Student selection frame
        selection_frame = ttk.LabelFrame(main_frame, text="Select Student", padding=10)
        selection_frame.pack(fill=tk.X, pady=5)

        if is_admin:
            # Admin: Search by student ID
            ttk.Label(selection_frame, text="Search Student ID:").pack(anchor='w')
            search_frame = ttk.Frame(selection_frame)
            search_frame.pack(fill=tk.X, pady=5)

            self.search_var = tk.StringVar(value=search_student_id or "")
            self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
            self.search_entry.pack(side=tk.LEFT, padx=(0, 5))

            ttk.Button(search_frame, text="Search", command=self.search_student).pack(side=tk.LEFT)

            self.student_info_label = ttk.Label(selection_frame, text="", foreground="blue")
            self.student_info_label.pack(anchor='w', pady=5)

            self.selected_student = None
        else:
            # Parent: Select from children
            ttk.Label(selection_frame, text="Select Student:").pack(anchor='w')
            self.child_var = tk.StringVar()
            self.child_combo = ttk.Combobox(selection_frame, textvariable=self.child_var, width=50, state="readonly")
            self.child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in children]
            if children:
                self.child_combo.set(self.child_combo['values'][0])
            self.child_combo.pack(fill=tk.X, pady=5)
            self.child_combo.bind("<<ComboboxSelected>>", self.on_child_selected)

        # Date selection
        date_frame = ttk.LabelFrame(main_frame, text="Absence Date", padding=10)
        date_frame.pack(fill=tk.X, pady=5)

        ttk.Label(date_frame, text="Select Date:").pack(anchor='w')
        self.date_var = tk.StringVar(value=datetime.datetime.now().strftime('%Y-%m-%d'))
        self.date_entry = ttk.Entry(date_frame, textvariable=self.date_var, width=20)
        self.date_entry.pack(anchor='w', pady=5)
        ttk.Label(date_frame, text="(Format: YYYY-MM-DD)", font=('Arial', 8)).pack(anchor='w')

        # Timetable frame
        timetable_frame = ttk.LabelFrame(main_frame, text="Select Sessions to Mark Absent", padding=10)
        timetable_frame.pack(fill=tk.X, pady=5)

        # Timetable treeview with increased height
        columns = ("Select", "Module", "Day", "Time", "Room", "Instructor")
        self.timetable_tree = ttk.Treeview(timetable_frame, columns=columns, show='headings', height=12)

        self.timetable_tree.heading("Select", text="✓")
        self.timetable_tree.heading("Module", text="Module")
        self.timetable_tree.heading("Day", text="Day")
        self.timetable_tree.heading("Time", text="Time")
        self.timetable_tree.heading("Room", text="Room")
        self.timetable_tree.heading("Instructor", text="Instructor")

        self.timetable_tree.column("Select", width=40, anchor='center')
        self.timetable_tree.column("Module", width=180)
        self.timetable_tree.column("Day", width=90)
        self.timetable_tree.column("Time", width=110)
        self.timetable_tree.column("Room", width=90)
        self.timetable_tree.column("Instructor", width=120)

        timetable_scroll = ttk.Scrollbar(timetable_frame, orient="vertical", command=self.timetable_tree.yview)
        self.timetable_tree.configure(yscrollcommand=timetable_scroll.set)

        self.timetable_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        timetable_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.timetable_tree.bind("<ButtonRelease-1>", self.toggle_session_selection)

        # Load timetable button
        load_btn_frame = ttk.Frame(main_frame)
        load_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(load_btn_frame, text="Load/Refresh Timetable", command=self.load_timetable).pack(side=tk.LEFT)
        ttk.Label(load_btn_frame, text="  (Click on rows to select/deselect sessions)", font=('Arial', 9)).pack(side=tk.LEFT)

        # Reason
        reason_frame = ttk.LabelFrame(main_frame, text="Reason for Absence", padding=10)
        reason_frame.pack(fill=tk.X, pady=5)

        self.reason_text = scrolledtext.ScrolledText(reason_frame, height=4, width=70)
        self.reason_text.pack(fill=tk.X, pady=5)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)

        submit_btn = ttk.Button(btn_frame, text="Submit Absence Report", command=self.submit)
        submit_btn.pack(side=tk.LEFT, padx=10)

        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=on_close)
        cancel_btn.pack(side=tk.LEFT, padx=10)

        # Load timetable for first child if available
        if not is_admin and children:
            self.load_timetable()

        self.dialog.wait_window()

    def search_student(self):
        """Search for student by ID (admin function)"""
        student_id = self.search_var.get().strip()
        if not student_id:
            messagebox.showwarning("Missing ID", "Please enter a student ID.")
            return

        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT student_id, first_name, last_name, course, email_address
                FROM students WHERE student_id = ?
            ''', (student_id,))
            student = cursor.fetchone()
            conn.close()

            if student:
                self.selected_student = student
                self.student_info_label.config(
                    text=f"Found: {student[1]} {student[2]} - {student[3]}",
                    foreground="green"
                )
                self.load_timetable()
            else:
                self.selected_student = None
                self.student_info_label.config(text="Student not found", foreground="red")
                self.clear_timetable()
        except Exception as e:
            messagebox.showerror("Error", f"Error searching student: {e}")

    def on_child_selected(self, event=None):
        """Handle child selection change"""
        self.load_timetable()

    def get_selected_student_id(self):
        """Get the currently selected student ID"""
        if self.is_admin:
            return self.selected_student[0] if self.selected_student else None
        else:
            selected = self.child_var.get()
            if selected:
                # Extract ID from "Name (ID: xxx)"
                try:
                    return selected.split("ID: ")[1].rstrip(")")
                except (IndexError, AttributeError):
                    return None
        return None

    def clear_timetable(self):
        """Clear the timetable tree"""
        for item in self.timetable_tree.get_children():
            self.timetable_tree.delete(item)
        self.timetable_data = []
        self.selected_sessions = []

    def load_timetable(self):
        """Load timetable for selected student"""
        student_id = self.get_selected_student_id()
        if not student_id:
            return

        self.clear_timetable()

        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30)
            cursor = conn.cursor()

            # Get student timetable with module names
            cursor.execute('''
                SELECT st.id, st.module_code, m.module_name, st.day_of_week, st.time_slot,
                       st.room, i.first_name || ' ' || i.last_name as instructor_name
                FROM student_timetables st
                LEFT JOIN modules m ON st.module_code = m.module_code OR st.module_code = m.module_id
                LEFT JOIN instructors i ON st.instructor_id = i.id
                WHERE st.student_id = ?
                ORDER BY
                    CASE st.day_of_week
                        WHEN 'Monday' THEN 1
                        WHEN 'Tuesday' THEN 2
                        WHEN 'Wednesday' THEN 3
                        WHEN 'Thursday' THEN 4
                        WHEN 'Friday' THEN 5
                        WHEN 'Saturday' THEN 6
                        WHEN 'Sunday' THEN 7
                    END, st.time_slot
            ''', (student_id,))

            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                session_id, module_code, module_name, day, time_slot, room, instructor = row
                display_module = module_name or module_code
                instructor = instructor or "TBA"
                room = room or "TBA"

                item_id = self.timetable_tree.insert("", tk.END, values=(
                    "☐", display_module, day, time_slot, room, instructor
                ))
                self.timetable_data.append({
                    'item_id': item_id,
                    'session_id': session_id,
                    'module_code': module_code,
                    'module_name': display_module,
                    'day': day,
                    'time_slot': time_slot,
                    'room': room,
                    'instructor': instructor,
                    'selected': False
                })

            if not rows:
                self.timetable_tree.insert("", tk.END, values=(
                    "", "No timetable data found", "", "", "", ""
                ))

        except Exception as e:
            messagebox.showerror("Error", f"Error loading timetable: {e}")

    def toggle_session_selection(self, event):
        """Toggle selection of a timetable session"""
        item = self.timetable_tree.identify_row(event.y)
        if not item:
            return

        # Find and toggle the session
        for session in self.timetable_data:
            if session['item_id'] == item:
                session['selected'] = not session['selected']
                check_mark = "☑" if session['selected'] else "☐"
                current_values = list(self.timetable_tree.item(item, 'values'))
                current_values[0] = check_mark
                self.timetable_tree.item(item, values=current_values)
                break

    def submit(self):
        """Submit the absence report"""
        student_id = self.get_selected_student_id()
        if not student_id:
            messagebox.showwarning("Missing Information", "Please select a student.")
            return

        absence_date = self.date_var.get().strip()
        reason = self.reason_text.get(1.0, tk.END).strip()

        if not reason:
            messagebox.showwarning("Missing Information", "Please provide a reason for absence.")
            return

        # Get selected sessions
        self.selected_sessions = [s for s in self.timetable_data if s['selected']]

        # Find the child data
        selected_child = None
        if self.is_admin and self.selected_student:
            selected_child = self.selected_student
        else:
            for child in self.children:
                if child[0] == student_id:
                    selected_child = child
                    break

        self.result = {
            'student_id': student_id,
            'student_data': selected_child,
            'absence_date': absence_date,
            'reason': reason,
            'sessions': self.selected_sessions
        }

        self.dialog.destroy()

    def cancel(self):
        self.dialog.destroy()


class EmergencyContactDialog:
    """Dialog for managing emergency contacts with full CRUD operations"""

    def __init__(self, parent, children=None, db_path=None, current_user=None):
        self.result = None
        self.db_path = db_path or DEFAULT_DB_PATH
        self.children = children or []
        self.current_user = current_user
        self.contacts = []
        self.editing_contact_id = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Manage Emergency Contacts")
        self.dialog.geometry("900x750")
        self.dialog.minsize(850, 700)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center the dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Emergency Contacts Management", font=('Arial', 14, 'bold')).pack(pady=10)

        # Student selection (for parents with multiple children)
        if self.children:
            selection_frame = ttk.LabelFrame(main_frame, text="Select Student", padding=10)
            selection_frame.pack(fill=tk.X, pady=5)

            self.student_var = tk.StringVar()
            self.student_combo = ttk.Combobox(selection_frame, textvariable=self.student_var, width=50, state="readonly")
            self.student_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
            if self.children:
                self.student_combo.set(self.student_combo['values'][0])
            self.student_combo.pack(fill=tk.X, pady=5)
            self.student_combo.bind("<<ComboboxSelected>>", self.on_student_selected)

        # Contacts list frame
        list_frame = ttk.LabelFrame(main_frame, text="Existing Emergency Contacts", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Contacts treeview
        columns = ("Priority", "Name", "Relationship", "Primary Phone", "Email", "Medical Decision")
        self.contacts_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=6)

        self.contacts_tree.heading("Priority", text="#")
        self.contacts_tree.heading("Name", text="Name")
        self.contacts_tree.heading("Relationship", text="Relationship")
        self.contacts_tree.heading("Primary Phone", text="Primary Phone")
        self.contacts_tree.heading("Email", text="Email")
        self.contacts_tree.heading("Medical Decision", text="Medical Auth")

        self.contacts_tree.column("Priority", width=30)
        self.contacts_tree.column("Name", width=150)
        self.contacts_tree.column("Relationship", width=100)
        self.contacts_tree.column("Primary Phone", width=120)
        self.contacts_tree.column("Email", width=150)
        self.contacts_tree.column("Medical Decision", width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.contacts_tree.yview)
        self.contacts_tree.configure(yscrollcommand=scrollbar.set)

        self.contacts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.contacts_tree.bind("<<TreeviewSelect>>", self.on_contact_selected)

        # Action buttons for list
        list_btn_frame = ttk.Frame(list_frame)
        list_btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(list_btn_frame, text="Edit Selected", command=self.edit_contact).pack(side=tk.LEFT, padx=2)
        ttk.Button(list_btn_frame, text="Delete Selected", command=self.delete_contact).pack(side=tk.LEFT, padx=2)
        ttk.Button(list_btn_frame, text="Move Up", command=lambda: self.change_priority(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(list_btn_frame, text="Move Down", command=lambda: self.change_priority(1)).pack(side=tk.LEFT, padx=2)

        # Form frame for adding/editing contacts
        form_frame = ttk.LabelFrame(main_frame, text="Add/Edit Contact", padding=10)
        form_frame.pack(fill=tk.X, pady=5)

        # Form fields in grid layout
        form_grid = ttk.Frame(form_frame)
        form_grid.pack(fill=tk.X)

        ttk.Label(form_grid, text="Contact Name:").grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.name_entry = ttk.Entry(form_grid, width=30)
        self.name_entry.grid(row=0, column=1, sticky='w', padx=5, pady=2)

        ttk.Label(form_grid, text="Relationship:").grid(row=0, column=2, sticky='w', padx=5, pady=2)
        self.relationship_var = tk.StringVar()
        self.relationship_combo = ttk.Combobox(form_grid, textvariable=self.relationship_var, width=20)
        self.relationship_combo['values'] = ['Parent', 'Guardian', 'Grandparent', 'Sibling', 'Aunt/Uncle', 'Other Family', 'Friend', 'Other']
        self.relationship_combo.grid(row=0, column=3, sticky='w', padx=5, pady=2)

        ttk.Label(form_grid, text="Primary Phone:").grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.phone_primary_entry = ttk.Entry(form_grid, width=30)
        self.phone_primary_entry.grid(row=1, column=1, sticky='w', padx=5, pady=2)

        ttk.Label(form_grid, text="Secondary Phone:").grid(row=1, column=2, sticky='w', padx=5, pady=2)
        self.phone_secondary_entry = ttk.Entry(form_grid, width=20)
        self.phone_secondary_entry.grid(row=1, column=3, sticky='w', padx=5, pady=2)

        ttk.Label(form_grid, text="Email:").grid(row=2, column=0, sticky='w', padx=5, pady=2)
        self.email_entry = ttk.Entry(form_grid, width=30)
        self.email_entry.grid(row=2, column=1, sticky='w', padx=5, pady=2)

        self.medical_var = tk.BooleanVar()
        ttk.Checkbutton(form_grid, text="Medical Decision Maker", variable=self.medical_var).grid(row=2, column=2, columnspan=2, sticky='w', padx=5, pady=2)

        ttk.Label(form_grid, text="Address:").grid(row=3, column=0, sticky='w', padx=5, pady=2)
        self.address_entry = ttk.Entry(form_grid, width=60)
        self.address_entry.grid(row=3, column=1, columnspan=3, sticky='w', padx=5, pady=2)

        # Form buttons
        form_btn_frame = ttk.Frame(form_frame)
        form_btn_frame.pack(fill=tk.X, pady=10)

        self.save_btn = ttk.Button(form_btn_frame, text="Add Contact", command=self.save_contact)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(form_btn_frame, text="Clear Form", command=self.clear_form).pack(side=tk.LEFT, padx=5)

        # Close button
        ttk.Button(main_frame, text="Close", command=self.close_dialog).pack(pady=10)

        # Load contacts for first student
        if self.children:
            self.load_contacts()

        self.dialog.wait_window()

    def get_selected_student_id(self):
        """Get the currently selected student ID"""
        if not self.children:
            return None
        selected = self.student_var.get()
        if selected:
            try:
                return selected.split("ID: ")[1].rstrip(")")
            except (IndexError, AttributeError):
                return None
        return None

    def on_student_selected(self, event=None):
        """Handle student selection change"""
        self.load_contacts()
        self.clear_form()

    def load_contacts(self):
        """Load emergency contacts for selected student"""
        student_id = self.get_selected_student_id()
        if not student_id:
            return

        # Clear existing items
        for item in self.contacts_tree.get_children():
            self.contacts_tree.delete(item)
        self.contacts = []

        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, contact_name, relationship, phone_primary, phone_secondary,
                       email, address, priority_order, medical_decision_maker
                FROM emergency_contacts
                WHERE student_id = ?
                ORDER BY priority_order ASC
            ''', (student_id,))

            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                contact_id, name, relationship, phone_primary, phone_secondary, email, address, priority, medical = row
                medical_text = "Yes" if medical else "No"

                self.contacts_tree.insert("", tk.END, values=(
                    priority or "-", name or "", relationship or "", phone_primary or "",
                    email or "", medical_text
                ), iid=str(contact_id))

                self.contacts.append({
                    'id': contact_id,
                    'name': name,
                    'relationship': relationship,
                    'phone_primary': phone_primary,
                    'phone_secondary': phone_secondary,
                    'email': email,
                    'address': address,
                    'priority': priority,
                    'medical_decision_maker': medical
                })

        except Exception as e:
            messagebox.showerror("Error", f"Error loading contacts: {e}")

    def on_contact_selected(self, event=None):
        """Handle contact selection in treeview"""
        pass  # Selection handled by buttons

    def edit_contact(self):
        """Edit the selected contact"""
        selection = self.contacts_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a contact to edit.")
            return

        contact_id = int(selection[0])
        self.editing_contact_id = contact_id

        # Find and populate form with contact data
        for contact in self.contacts:
            if contact['id'] == contact_id:
                self.name_entry.delete(0, tk.END)
                self.name_entry.insert(0, contact['name'] or "")

                self.relationship_var.set(contact['relationship'] or "")

                self.phone_primary_entry.delete(0, tk.END)
                self.phone_primary_entry.insert(0, contact['phone_primary'] or "")

                self.phone_secondary_entry.delete(0, tk.END)
                self.phone_secondary_entry.insert(0, contact['phone_secondary'] or "")

                self.email_entry.delete(0, tk.END)
                self.email_entry.insert(0, contact['email'] or "")

                self.address_entry.delete(0, tk.END)
                self.address_entry.insert(0, contact['address'] or "")

                self.medical_var.set(contact['medical_decision_maker'] or False)

                self.save_btn.config(text="Update Contact")
                break

    def delete_contact(self):
        """Delete the selected contact"""
        selection = self.contacts_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a contact to delete.")
            return

        contact_id = int(selection[0])

        if not messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this contact?"):
            return

        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM emergency_contacts WHERE id = ?", (contact_id,))
            conn.commit()
            conn.close()

            self.load_contacts()
            self.clear_form()
            messagebox.showinfo("Success", "Contact deleted successfully.")

        except Exception as e:
            messagebox.showerror("Error", f"Error deleting contact: {e}")

    def change_priority(self, direction):
        """Change priority of selected contact (move up or down)"""
        selection = self.contacts_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a contact to move.")
            return

        contact_id = int(selection[0])
        student_id = self.get_selected_student_id()

        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30)
            cursor = conn.cursor()

            # Get current priority
            cursor.execute("SELECT priority_order FROM emergency_contacts WHERE id = ?", (contact_id,))
            current = cursor.fetchone()
            if not current:
                conn.close()
                return

            current_priority = current[0] or 1
            new_priority = max(1, current_priority + direction)

            # Swap priorities
            cursor.execute('''
                UPDATE emergency_contacts
                SET priority_order = ?
                WHERE student_id = ? AND priority_order = ?
            ''', (current_priority, student_id, new_priority))

            cursor.execute('''
                UPDATE emergency_contacts
                SET priority_order = ?
                WHERE id = ?
            ''', (new_priority, contact_id))

            conn.commit()
            conn.close()

            self.load_contacts()

        except Exception as e:
            messagebox.showerror("Error", f"Error changing priority: {e}")

    def save_contact(self):
        """Save (add or update) contact"""
        student_id = self.get_selected_student_id()
        if not student_id:
            messagebox.showwarning("No Student", "Please select a student first.")
            return

        name = self.name_entry.get().strip()
        relationship = self.relationship_var.get()
        phone_primary = self.phone_primary_entry.get().strip()
        phone_secondary = self.phone_secondary_entry.get().strip()
        email = self.email_entry.get().strip()
        address = self.address_entry.get().strip()
        medical = 1 if self.medical_var.get() else 0

        if not name:
            messagebox.showwarning("Missing Information", "Contact name is required.")
            return

        if not phone_primary and not email:
            messagebox.showwarning("Missing Information", "Please provide at least a phone number or email.")
            return

        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30)
            cursor = conn.cursor()

            if self.editing_contact_id:
                # Update existing contact
                cursor.execute('''
                    UPDATE emergency_contacts
                    SET contact_name = ?, relationship = ?, phone_primary = ?,
                        phone_secondary = ?, email = ?, address = ?, medical_decision_maker = ?
                    WHERE id = ?
                ''', (name, relationship, phone_primary, phone_secondary, email, address, medical, self.editing_contact_id))
                message = "Contact updated successfully."
            else:
                # Get next priority
                cursor.execute('''
                    SELECT COALESCE(MAX(priority_order), 0) + 1
                    FROM emergency_contacts WHERE student_id = ?
                ''', (student_id,))
                next_priority = cursor.fetchone()[0]

                # Insert new contact
                cursor.execute('''
                    INSERT INTO emergency_contacts
                    (student_id, contact_name, relationship, phone_primary, phone_secondary,
                     email, address, priority_order, medical_decision_maker, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, name, relationship, phone_primary, phone_secondary,
                      email, address, next_priority, medical, datetime.datetime.now().isoformat()))
                message = "Contact added successfully."

            conn.commit()
            conn.close()

            self.load_contacts()
            self.clear_form()
            messagebox.showinfo("Success", message)

        except Exception as e:
            messagebox.showerror("Error", f"Error saving contact: {e}")

    def clear_form(self):
        """Clear the form fields"""
        self.editing_contact_id = None
        self.name_entry.delete(0, tk.END)
        self.relationship_var.set("")
        self.phone_primary_entry.delete(0, tk.END)
        self.phone_secondary_entry.delete(0, tk.END)
        self.email_entry.delete(0, tk.END)
        self.address_entry.delete(0, tk.END)
        self.medical_var.set(False)
        self.save_btn.config(text="Add Contact")

    def close_dialog(self):
        """Close the dialog"""
        self.result = {'action': 'closed'}
        self.dialog.destroy()


def run_parent_portal_gui(auth=None):
    """
    Main function to run the Parent Portal GUI.
    This function maintains backwards compatibility with the CLI version.
    """
    try:
        # Try to create GUI version
        app = ParentPortalGUI(auth)
        root = app.create_main_window()
        
        if root:
            root.mainloop()
        else:
            # Fallback to CLI version
            print("GUI unavailable, falling back to CLI version...")
            from parent_portal import ParentPortal
            ParentPortal.display_parent_portal_menu(auth)
            
    except ImportError as e:
        print(f"Error importing required modules: {e}")
        print("Falling back to CLI version...")
        try:
            from parent_portal import ParentPortal
            ParentPortal.display_parent_portal_menu(auth)
        except ImportError:
            print("CLI version also unavailable. Please check your installation.")
    
    except Exception as e:
        print(f"Error running GUI: {e}")
        print("Falling back to CLI version...")
        try:
            from parent_portal import ParentPortal
            ParentPortal.display_parent_portal_menu(auth)
        except Exception as cli_error:
            print(f"CLI version also failed: {cli_error}")


class ParentPortalCompat:
    """
    Backwards compatibility wrapper that provides both GUI and CLI interfaces.
    This ensures existing code continues to work while adding GUI functionality.
    """
    
    def __init__(self, auth=None):
        self.auth = auth
        self.gui_available = True
        
        try:
            import tkinter
        except ImportError:
            self.gui_available = False
    
    def display_parent_portal_menu(self, auth=None, use_gui=True):
        """
        Display the parent portal menu.
        
        Args:
            auth: Authentication object
            use_gui: Boolean to determine if GUI should be used (default: True)
        """
        if auth:
            self.auth = auth
        
        if use_gui and self.gui_available:
            try:
                run_parent_portal_gui(self.auth)
            except Exception as e:
                print(f"GUI failed: {e}")
                print("Falling back to CLI...")
                self._run_cli_version()
        else:
            self._run_cli_version()
    
    def _run_cli_version(self):
        """Run the original CLI version"""
        try:
            from parent_portal import ParentPortal
            ParentPortal.display_parent_portal_menu(self.auth)
        except ImportError:
            print("Original parent portal module not found.")
            self._run_embedded_cli()
    
    def _run_embedded_cli(self):
        """Run embedded CLI version if original is not available"""
        print("\n" + "=" * 60)
        print("PARENT PORTAL (CLI Mode)")
        print("=" * 60)
        
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to access the parent portal.")
            return
        
        if self.auth.current_user.get('role') != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        while True:
            print("\n1. View Children")
            print("2. View Grades")
            print("3. View Attendance")
            print("4. Send Message")
            print("5. View Reports")
            print("6. Update Contact Info")
            print("0. Exit")
            
            choice = input("\nEnter your choice: ")
            
            if choice == '0':
                break
            elif choice == '1':
                print("View Children - Feature available in full version")
            elif choice == '2':
                print("View Grades - Feature available in full version")
            elif choice == '3':
                print("View Attendance - Feature available in full version")
            elif choice == '4':
                print("Send Message - Feature available in full version")
            elif choice == '5':
                print("View Reports - Feature available in full version")
            elif choice == '6':
                print("Update Contact Info - Feature available in full version")
            else:
                print("Invalid choice.")


class ModernMessageBox:
    """Custom message box with modern styling"""
    
    @staticmethod
    def show_info(parent, title, message):
        """Show info message with custom styling"""
        dialog = tk.Toplevel(parent)
        dialog.title(title)
        dialog.geometry("400x200")
        dialog.transient(parent)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 100, parent.winfo_rooty() + 100))
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Icon and title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(title_frame, text="ℹ️", font=('Arial', 20)).pack(side=tk.LEFT)
        ttk.Label(title_frame, text=title, font=('Arial', 14, 'bold')).pack(side=tk.LEFT, padx=(10, 0))
        
        # Message
        ttk.Label(main_frame, text=message, wraplength=350).pack(pady=10)
        
        # OK button
        ttk.Button(main_frame, text="OK", command=dialog.destroy).pack(pady=10)
        
        dialog.wait_window()


class ProgressDialog:
    """Progress dialog for long-running operations"""
    
    def __init__(self, parent, title="Processing..."):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("300x120")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 150, parent.winfo_rooty() + 150))
        
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.label = ttk.Label(main_frame, text="Please wait...")
        self.label.pack(pady=10)
        
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=10)
        self.progress.start()
    
    def update_text(self, text):
        """Update the progress text"""
        self.label.config(text=text)
        self.dialog.update()
    
    def close(self):
        """Close the progress dialog"""
        self.progress.stop()
        self.dialog.destroy()


class NotificationCenter:
    """Notification center for displaying alerts and messages"""
    
    def __init__(self, parent):
        self.parent = parent
        self.notifications = []
    
    def show_notification(self, title, message, type="info"):
        """Show a notification popup"""
        notification = tk.Toplevel(self.parent)
        notification.title("Notification")
        notification.geometry("350x120")
        notification.attributes('-topmost', True)
        
        # Position in top-right corner
        notification.geometry("+%d+%d" % (self.parent.winfo_rootx() + self.parent.winfo_width() - 370, 
                                         self.parent.winfo_rooty() + 50))
        
        # Style based on type - use ttk widgets to reduce X pixmap usage
        type_prefixes = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅"
        }

        prefix = type_prefixes.get(type, "ℹ️")

        main_frame = ttk.Frame(notification, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(main_frame, text=f"{prefix} {title}", font=('Arial', 12, 'bold'))
        title_label.pack(anchor='w')

        message_label = ttk.Label(main_frame, text=message, font=('Arial', 10), wraplength=300)
        message_label.pack(anchor='w', pady=(5, 0))
        
        # Auto-close after 5 seconds
        notification.after(5000, notification.destroy)
        
        # Close on click
        def close_notification(event):
            notification.destroy()
        
        notification.bind("<Button-1>", close_notification)
        main_frame.bind("<Button-1>", close_notification)
        title_label.bind("<Button-1>", close_notification)
        message_label.bind("<Button-1>", close_notification)

