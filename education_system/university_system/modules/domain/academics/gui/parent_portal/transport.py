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



from .base import ParentPortalGUI

def show_transport_interface(self):
    """Show transportation information interface"""
    self.clear_content()
    self.update_status("Transportation Information")

    title = ttk.Label(self.content_frame, text="Transportation Information", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    if not self.children:
        ttk.Label(self.content_frame, text="No students linked to your guardian account.").pack(pady=50)
        return

    # Child selection
    child_frame = ttk.Frame(self.content_frame)
    child_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(child_frame, text="Select Student:").pack(side=tk.LEFT, padx=5)
    child_var = tk.StringVar()
    child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
    child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
    if child_combo['values']:
        child_combo.set(child_combo['values'][0])
    child_combo.pack(side=tk.LEFT, padx=5)

    # Transportation display frame
    transport_frame = ttk.LabelFrame(self.content_frame, text="Transportation Details", padding=15)
    transport_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def load_transport_info():
        for widget in transport_frame.winfo_children():
            widget.destroy()

        selected_child = child_var.get()
        if not selected_child:
            ttk.Label(transport_frame, text="Please select a child").pack(pady=20)
            return

        student_id = selected_child.split("ID: ")[1].rstrip(")")

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='transportation'
            """)

            if cursor.fetchone():
                # Correct column names: route_name, bus_number, pickup_time, dropoff_time,
                # pickup_location, dropoff_location, driver_name, driver_phone, active
                cursor.execute("""
                SELECT route_name, bus_number, pickup_time, dropoff_time,
                       pickup_location, dropoff_location, driver_name, driver_phone
                FROM transportation
                WHERE student_id = ? AND active = 1
                """, (student_id,))

                transport_data = cursor.fetchone()

                if transport_data:
                    # Display transportation information
                    info_frame = ttk.Frame(transport_frame)
                    info_frame.pack(fill=tk.BOTH, expand=True)

                    # Route information
                    route_frame = ttk.LabelFrame(info_frame, text="Route Information", padding=10)
                    route_frame.pack(fill=tk.X, pady=(0, 10))

                    ttk.Label(route_frame, text=f"Route Name: {transport_data[0] or 'Not specified'}",
                             font=('Arial', 10, 'bold')).pack(anchor='w', pady=3)
                    ttk.Label(route_frame, text=f"Bus Number: {transport_data[1] or 'N/A'}",
                             font=('Arial', 10)).pack(anchor='w', pady=3)

                    # Schedule information
                    schedule_frame = ttk.LabelFrame(info_frame, text="Schedule", padding=10)
                    schedule_frame.pack(fill=tk.X, pady=(0, 10))

                    ttk.Label(schedule_frame, text=f"Pickup Time: {transport_data[2] or 'Not specified'}",
                             font=('Arial', 10)).pack(anchor='w', pady=3)
                    ttk.Label(schedule_frame, text=f"Pickup Location: {transport_data[4] or 'Not specified'}",
                             font=('Arial', 10)).pack(anchor='w', pady=3)
                    ttk.Label(schedule_frame, text=f"Drop-off Time: {transport_data[3] or 'Not specified'}",
                             font=('Arial', 10)).pack(anchor='w', pady=3)
                    ttk.Label(schedule_frame, text=f"Drop-off Location: {transport_data[5] or 'Not specified'}",
                             font=('Arial', 10)).pack(anchor='w', pady=3)

                    # Driver information
                    driver_frame = ttk.LabelFrame(info_frame, text="Driver Information", padding=10)
                    driver_frame.pack(fill=tk.X)

                    ttk.Label(driver_frame, text=f"Driver Name: {transport_data[6] or 'Not assigned'}",
                             font=('Arial', 10)).pack(anchor='w', pady=3)
                    ttk.Label(driver_frame, text=f"Driver Phone: {transport_data[7] or 'Not available'}",
                             font=('Arial', 10)).pack(anchor='w', pady=3)

                    # Action buttons
                    btn_frame = ttk.Frame(transport_frame)
                    btn_frame.pack(pady=10)
                    ttk.Button(btn_frame, text="Update Transportation",
                              command=lambda: self.update_transport_info(student_id)).pack(side=tk.LEFT, padx=5)
                    ttk.Button(btn_frame, text="Report Issue",
                              command=lambda: self.report_transport_issue(student_id)).pack(side=tk.LEFT, padx=5)
                else:
                    ttk.Label(transport_frame, text="No transportation information found",
                             font=('Arial', 11)).pack(pady=50)
                    ttk.Button(transport_frame, text="Request Transportation",
                              command=lambda: self.request_transportation(student_id)).pack()
            else:
                ttk.Label(transport_frame, text="Transportation system not configured",
                         font=('Arial', 11)).pack(pady=20)
                ttk.Label(transport_frame, text="Please contact university administration for transportation services.",
                         font=('Arial', 9, 'italic')).pack()

            conn.close()

        except Exception as e:
            ttk.Label(transport_frame, text=f"Error loading transportation info: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    ttk.Button(child_frame, text="Load Transport Info", command=load_transport_info).pack(side=tk.LEFT, padx=5)
    load_transport_info()
ParentPortalGUI.show_transport_interface = show_transport_interface

def update_transport_info(self, student_id):
    """Update transportation information"""
    # Create dialog window
    dialog = tk.Toplevel(self.root)
    dialog.title("Update Transportation Information")
    dialog.geometry("600x550")
    dialog.transient(self.root)
    dialog.grab_set()

    # Main frame with padding
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Update Transportation Information",
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Fetch existing transportation info
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='transportation'
        """)

        if not cursor.fetchone():
            messagebox.showwarning("Not Available", "Transportation system not configured.")
            conn.close()
            dialog.destroy()
            return

        cursor.execute("""
        SELECT route_number, bus_number, pickup_time, pickup_location,
               dropoff_time, dropoff_location
        FROM transportation WHERE student_id = ?
        """, (student_id,))

        existing_data = cursor.fetchone()
        conn.close()

        if not existing_data:
            messagebox.showwarning("No Record", "No transportation record found. Please request transportation first.")
            dialog.destroy()
            return

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load transportation information: {str(e)}")
        dialog.destroy()
        return

    # Create form fields
    fields = {}

    # Route Number
    ttk.Label(main_frame, text="Route Number:").pack(anchor='w', pady=(5, 0))
    fields['route_number'] = ttk.Entry(main_frame, width=50)
    fields['route_number'].pack(fill=tk.X, pady=(0, 10))
    if existing_data and existing_data[0]:
        fields['route_number'].insert(0, existing_data[0])

    # Bus Number
    ttk.Label(main_frame, text="Bus Number:").pack(anchor='w', pady=(5, 0))
    fields['bus_number'] = ttk.Entry(main_frame, width=50)
    fields['bus_number'].pack(fill=tk.X, pady=(0, 10))
    if existing_data and existing_data[1]:
        fields['bus_number'].insert(0, existing_data[1])

    # Pickup Time
    ttk.Label(main_frame, text="Pickup Time (HH:MM AM/PM):").pack(anchor='w', pady=(5, 0))
    fields['pickup_time'] = ttk.Entry(main_frame, width=50)
    fields['pickup_time'].pack(fill=tk.X, pady=(0, 10))
    if existing_data and existing_data[2]:
        fields['pickup_time'].insert(0, existing_data[2])

    # Pickup Location
    ttk.Label(main_frame, text="Pickup Location:").pack(anchor='w', pady=(5, 0))
    fields['pickup_location'] = ttk.Entry(main_frame, width=50)
    fields['pickup_location'].pack(fill=tk.X, pady=(0, 10))
    if existing_data and existing_data[3]:
        fields['pickup_location'].insert(0, existing_data[3])

    # Dropoff Time
    ttk.Label(main_frame, text="Dropoff Time (HH:MM AM/PM):").pack(anchor='w', pady=(5, 0))
    fields['dropoff_time'] = ttk.Entry(main_frame, width=50)
    fields['dropoff_time'].pack(fill=tk.X, pady=(0, 10))
    if existing_data and existing_data[4]:
        fields['dropoff_time'].insert(0, existing_data[4])

    # Dropoff Location
    ttk.Label(main_frame, text="Dropoff Location:").pack(anchor='w', pady=(5, 0))
    fields['dropoff_location'] = ttk.Entry(main_frame, width=50)
    fields['dropoff_location'].pack(fill=tk.X, pady=(0, 10))
    if existing_data and existing_data[5]:
        fields['dropoff_location'].insert(0, existing_data[5])

    def save_info():
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Update existing record
            cursor.execute("""
            UPDATE transportation
            SET route_number = ?, bus_number = ?, pickup_time = ?,
                pickup_location = ?, dropoff_time = ?, dropoff_location = ?
            WHERE student_id = ?
            """, (
                fields['route_number'].get(),
                fields['bus_number'].get(),
                fields['pickup_time'].get(),
                fields['pickup_location'].get(),
                fields['dropoff_time'].get(),
                fields['dropoff_location'].get(),
                student_id
            ))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Transportation information updated successfully!")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update transportation information: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text="Save", command=save_info).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.update_transport_info = update_transport_info

def request_transportation(self, student_id):
    """Request transportation for a student"""
    # Create dialog window
    dialog = tk.Toplevel(self.root)
    dialog.title("Request Transportation")
    dialog.geometry("600x500")
    dialog.transient(self.root)
    dialog.grab_set()

    # Main frame with padding
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Request Transportation",
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Ensure table exists
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='transportation_requests'
        """)

        if not cursor.fetchone():
            cursor.execute("""
            CREATE TABLE transportation_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                service_type TEXT,
                route_preference TEXT,
                special_needs TEXT,
                start_date TEXT,
                request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'Pending'
            )
            """)
            conn.commit()

        conn.close()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to initialize database: {str(e)}")
        dialog.destroy()
        return

    # Create form fields
    fields = {}

    # Service Type
    ttk.Label(main_frame, text="Service Type:").pack(anchor='w', pady=(5, 0))
    fields['service_type'] = ttk.Combobox(main_frame, width=50, state="readonly")
    fields['service_type']['values'] = ['Bus Service', 'Van Service', 'Special Needs Transport', 'Other']
    fields['service_type'].pack(fill=tk.X, pady=(0, 10))

    # Route Preference
    ttk.Label(main_frame, text="Route Preference:").pack(anchor='w', pady=(5, 0))
    fields['route_preference'] = ttk.Entry(main_frame, width=50)
    fields['route_preference'].pack(fill=tk.X, pady=(0, 10))

    # Special Needs
    ttk.Label(main_frame, text="Special Needs/Accommodations:").pack(anchor='w', pady=(5, 0))
    fields['special_needs'] = scrolledtext.ScrolledText(main_frame, width=50, height=6)
    fields['special_needs'].pack(fill=tk.X, pady=(0, 10))

    # Start Date
    ttk.Label(main_frame, text="Requested Start Date (YYYY-MM-DD):").pack(anchor='w', pady=(5, 0))
    fields['start_date'] = ttk.Entry(main_frame, width=50)
    fields['start_date'].pack(fill=tk.X, pady=(0, 10))
    # Set default to today
    fields['start_date'].insert(0, datetime.datetime.now().strftime('%Y-%m-%d'))

    def submit_request():
        # Validate required fields
        if not fields['service_type'].get():
            messagebox.showwarning("Validation Error", "Please select a service type.")
            return

        if not fields['start_date'].get():
            messagebox.showwarning("Validation Error", "Please enter a start date.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Insert new request
            cursor.execute("""
            INSERT INTO transportation_requests (student_id, service_type, route_preference,
                                                special_needs, start_date)
            VALUES (?, ?, ?, ?, ?)
            """, (
                student_id,
                fields['service_type'].get(),
                fields['route_preference'].get(),
                fields['special_needs'].get('1.0', tk.END).strip(),
                fields['start_date'].get()
            ))

            conn.commit()

            # Get student info for email
            cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
            student_info = cursor.fetchone()
            student_name = f"{student_info[0]} {student_info[1]}" if student_info else student_id

            # Get admin email
            cursor.execute("""
                SELECT email FROM users
                WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                LIMIT 1
            """)
            admin_row = cursor.fetchone()
            admin_email = admin_row[0] if admin_row and admin_row[0] else None

            conn.close()

            # Send email notification to admin
            if admin_email and EMAIL_SERVICE_AVAILABLE:
                current_user = self.get_current_user()
                sender_name = "Parent/Guardian"
                if current_user:
                    sender_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or current_user.get('username', 'Parent/Guardian')

                # Render email from template
                from education_system.university_system.infrastructure.email.template_utils import render_template

                email_subject, email_body = render_template('parent_portal/transportation_request', {
                    'student_name': student_name,
                    'student_id': student_id,
                    'service_type': fields['service_type'].get(),
                    'route_preference': fields['route_preference'].get() or 'Not specified',
                    'special_needs': fields['special_needs'].get('1.0', tk.END).strip() or 'None',
                    'start_date': fields['start_date'].get(),
                    'sender_name': sender_name,
                    'request_datetime': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
                })

                # Fallback if template not found
                if not email_subject or not email_body:
                    email_subject = f"New Transportation Request - {student_name}"
                    email_body = f"Dear Transportation Administrator,\n\nA new transportation request has been submitted through the Guardian Portal.\n\nStudent: {student_name} (ID: {student_id})\nService Type: {fields['service_type'].get()}\nRoute Preference: {fields['route_preference'].get() or 'Not specified'}\nSpecial Needs: {fields['special_needs'].get('1.0', tk.END).strip() or 'None'}\nRequested Start Date: {fields['start_date'].get()}\n\nSubmitted by: {sender_name}\nDate: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\nBest regards,\nUniversity Guardian Portal"

                try:
                    send_email(admin_email, email_subject, email_body)
                except Exception as email_error:
                    print(f"Email notification error: {email_error}")

            messagebox.showinfo("Success", "Transportation request submitted successfully!\n\n"
                                          "The transportation office will review your request and contact you.")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit request: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text="Submit Request", command=submit_request).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.request_transportation = request_transportation

def report_transport_issue(self, student_id):
    """Report transportation issue"""
    # Create dialog window
    dialog = tk.Toplevel(self.root)
    dialog.title("Report Transportation Issue")
    dialog.geometry("600x450")
    dialog.transient(self.root)
    dialog.grab_set()

    # Main frame with padding
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Report Transportation Issue",
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Ensure table exists
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='transport_issues'
        """)

        if not cursor.fetchone():
            cursor.execute("""
            CREATE TABLE transport_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                issue_type TEXT,
                issue_date TEXT,
                issue_time TEXT,
                description TEXT,
                report_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'Open'
            )
            """)
            conn.commit()

        conn.close()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to initialize database: {str(e)}")
        dialog.destroy()
        return

    # Create form fields
    fields = {}

    # Issue Type
    ttk.Label(main_frame, text="Issue Type:").pack(anchor='w', pady=(5, 0))
    fields['issue_type'] = ttk.Combobox(main_frame, width=50, state="readonly")
    fields['issue_type']['values'] = ['Late Arrival', 'Missed Pickup', 'Safety Concern', 'Driver Behavior', 'Vehicle Condition', 'Other']
    fields['issue_type'].pack(fill=tk.X, pady=(0, 10))

    # Issue Date
    ttk.Label(main_frame, text="Date of Issue (YYYY-MM-DD):").pack(anchor='w', pady=(5, 0))
    fields['issue_date'] = ttk.Entry(main_frame, width=50)
    fields['issue_date'].pack(fill=tk.X, pady=(0, 10))
    fields['issue_date'].insert(0, datetime.datetime.now().strftime('%Y-%m-%d'))

    # Issue Time
    ttk.Label(main_frame, text="Time of Issue (HH:MM AM/PM):").pack(anchor='w', pady=(5, 0))
    fields['issue_time'] = ttk.Entry(main_frame, width=50)
    fields['issue_time'].pack(fill=tk.X, pady=(0, 10))

    # Description
    ttk.Label(main_frame, text="Description:").pack(anchor='w', pady=(5, 0))
    fields['description'] = scrolledtext.ScrolledText(main_frame, width=50, height=8)
    fields['description'].pack(fill=tk.X, pady=(0, 10))

    def submit_report():
        # Validate required fields
        if not fields['issue_type'].get():
            messagebox.showwarning("Validation Error", "Please select an issue type.")
            return

        if not fields['description'].get('1.0', tk.END).strip():
            messagebox.showwarning("Validation Error", "Please provide a description of the issue.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Insert new issue report
            cursor.execute("""
            INSERT INTO transport_issues (student_id, issue_type, issue_date,
                                         issue_time, description)
            VALUES (?, ?, ?, ?, ?)
            """, (
                student_id,
                fields['issue_type'].get(),
                fields['issue_date'].get(),
                fields['issue_time'].get(),
                fields['description'].get('1.0', tk.END).strip()
            ))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Transportation issue reported successfully!\n\n"
                                          "The transportation office will review your report and contact you.")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit report: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text="Submit Report", command=submit_report).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.report_transport_issue = report_transport_issue

def show_pickup_interface(self):
    """Show pickup authorization interface"""
    self.clear_content()
    self.update_status("Authorized Representatives")

    title = ttk.Label(self.content_frame, text="Authorized Representatives", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    if not self.children:
        ttk.Label(self.content_frame, text="No students linked to your guardian account.").pack(pady=50)
        return

    # Child selection
    child_frame = ttk.Frame(self.content_frame)
    child_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(child_frame, text="Select Student:").pack(side=tk.LEFT, padx=5)
    child_var = tk.StringVar()
    child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
    child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
    if child_combo['values']:
        child_combo.set(child_combo['values'][0])
    child_combo.pack(side=tk.LEFT, padx=5)

    # Authorized persons display frame
    pickup_frame = ttk.LabelFrame(self.content_frame, text="Authorized Representatives", padding=15)
    pickup_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def load_pickup_info():
        for widget in pickup_frame.winfo_children():
            widget.destroy()

        selected_child = child_var.get()
        if not selected_child:
            ttk.Label(pickup_frame, text="Please select a child").pack(pady=20)
            return

        student_id = selected_child.split("ID: ")[1].rstrip(")")

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS authorized_pickup (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    relationship TEXT,
                    phone TEXT,
                    id_number TEXT,
                    photo_on_file INTEGER DEFAULT 0,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

            cursor.execute("""
                SELECT name, relationship, phone, id_number, photo_on_file, notes
                FROM authorized_pickup
                WHERE student_id = ?
                ORDER BY name
            """, (student_id,))

            authorized_persons = cursor.fetchall()

            if authorized_persons:
                    # Display authorized persons
                    columns = ("Name", "Relationship", "Phone", "ID Number", "Photo on File")
                    tree = ttk.Treeview(pickup_frame, columns=columns, show="headings", height=10)

                    for col in columns:
                        tree.heading(col, text=col)
                        tree.column(col, width=120)

                    for person in authorized_persons:
                        tree.insert('', tk.END, values=person[:5])

                    scrollbar = ttk.Scrollbar(pickup_frame, orient=tk.VERTICAL, command=tree.yview)
                    tree.configure(yscrollcommand=scrollbar.set)

                    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                    # Action buttons
                    btn_frame = ttk.Frame(pickup_frame)
                    btn_frame.pack(pady=10, fill=tk.X)
                    ttk.Button(btn_frame, text="Add Person",
                              command=lambda: self.add_authorized_person(student_id)).pack(side=tk.LEFT, padx=5)
                    ttk.Button(btn_frame, text="Remove Person",
                              command=lambda: self.remove_authorized_person(student_id, tree)).pack(side=tk.LEFT, padx=5)
                    ttk.Button(btn_frame, text="Emergency Contact Request",
                              command=lambda: self.emergency_pickup_request(student_id)).pack(side=tk.LEFT, padx=5)
            else:
                ttk.Label(pickup_frame, text="No authorized pickup persons found",
                         font=('Arial', 11)).pack(pady=30)
                ttk.Label(pickup_frame, text="Add people who are authorized to pick up this student.",
                         font=('Arial', 9, 'italic')).pack(pady=5)
                ttk.Button(pickup_frame, text="Add Authorized Person",
                          command=lambda: self.add_authorized_person(student_id)).pack(pady=10)

            conn.close()

        except Exception as e:
            ttk.Label(pickup_frame, text=f"Error loading pickup authorization: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    ttk.Button(child_frame, text="Load Authorized Persons", command=load_pickup_info).pack(side=tk.LEFT, padx=5)
    load_pickup_info()
ParentPortalGUI.show_pickup_interface = show_pickup_interface

def add_authorized_person(self, student_id):
    """Add authorized pickup person"""
    # Create dialog window
    dialog = tk.Toplevel(self.root)
    dialog.title("Add Authorized Pickup Person")
    dialog.geometry("650x650")
    dialog.minsize(600, 600)
    dialog.transient(self.root)
    dialog.grab_set()

    # Main frame with padding
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Add Authorized Pickup Person",
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Ensure table exists
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='authorized_pickup'
        """)

        if not cursor.fetchone():
            cursor.execute("""
            CREATE TABLE authorized_pickup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                name TEXT NOT NULL,
                relationship TEXT,
                phone TEXT,
                id_number TEXT,
                photo_on_file TEXT DEFAULT 'No',
                notes TEXT,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()

        conn.close()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to initialize database: {str(e)}")
        dialog.destroy()
        return

    # Create form fields
    fields = {}

    # Name
    ttk.Label(main_frame, text="Full Name: *").pack(anchor='w', pady=(5, 0))
    fields['name'] = ttk.Entry(main_frame, width=50)
    fields['name'].pack(fill=tk.X, pady=(0, 10))

    # Relationship
    ttk.Label(main_frame, text="Relationship to Student:").pack(anchor='w', pady=(5, 0))
    fields['relationship'] = ttk.Combobox(main_frame, width=50, state="readonly")
    fields['relationship']['values'] = ['Parent', 'Guardian', 'Grandparent', 'Aunt/Uncle', 'Sibling', 'Family Friend', 'Other']
    fields['relationship'].pack(fill=tk.X, pady=(0, 10))

    # Phone
    ttk.Label(main_frame, text="Phone Number: *").pack(anchor='w', pady=(5, 0))
    fields['phone'] = ttk.Entry(main_frame, width=50)
    fields['phone'].pack(fill=tk.X, pady=(0, 10))

    # ID Number
    ttk.Label(main_frame, text="ID Number (Driver's License, etc.):").pack(anchor='w', pady=(5, 0))
    fields['id_number'] = ttk.Entry(main_frame, width=50)
    fields['id_number'].pack(fill=tk.X, pady=(0, 10))

    # Photo on File
    ttk.Label(main_frame, text="Photo ID on File:").pack(anchor='w', pady=(5, 0))
    fields['photo_on_file'] = ttk.Combobox(main_frame, width=50, state="readonly")
    fields['photo_on_file']['values'] = ['Yes', 'No']
    fields['photo_on_file'].set('No')
    fields['photo_on_file'].pack(fill=tk.X, pady=(0, 10))

    # Notes
    ttk.Label(main_frame, text="Notes:").pack(anchor='w', pady=(5, 0))
    fields['notes'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
    fields['notes'].pack(fill=tk.X, pady=(0, 10))

    def save_person():
        # Validate required fields
        if not fields['name'].get():
            messagebox.showwarning("Validation Error", "Please enter a name.")
            return

        if not fields['phone'].get():
            messagebox.showwarning("Validation Error", "Please enter a phone number.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Insert new authorized person
            cursor.execute("""
            INSERT INTO authorized_pickup (student_id, name, relationship, phone,
                                          id_number, photo_on_file, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                student_id,
                fields['name'].get(),
                fields['relationship'].get(),
                fields['phone'].get(),
                fields['id_number'].get(),
                fields['photo_on_file'].get(),
                fields['notes'].get('1.0', tk.END).strip()
            ))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Authorized person added successfully!")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add authorized person: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text="Save", command=save_person).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.add_authorized_person = add_authorized_person

def remove_authorized_person(self, student_id, tree):
    """Remove authorized pickup person"""
    selected = tree.selection()
    if not selected:
        messagebox.showwarning("No Selection", "Please select a person to remove.")
        return

    # Get the selected person's name
    item = tree.item(selected[0])
    person_name = item['values'][0]

    # Confirm deletion
    if not messagebox.askyesno("Confirm Removal",
                               f"Are you sure you want to remove '{person_name}' from the authorized pickup list?\n\n"
                               "This person will no longer be able to pick up the student."):
        return

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Delete the authorized person
        cursor.execute("""
        DELETE FROM authorized_pickup
        WHERE student_id = ? AND name = ?
        """, (student_id, person_name))

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", f"'{person_name}' has been removed from the authorized pickup list.")

        # Remove from treeview
        tree.delete(selected[0])

    except Exception as e:
        messagebox.showerror("Error", f"Failed to remove authorized person: {str(e)}")
ParentPortalGUI.remove_authorized_person = remove_authorized_person

def emergency_pickup_request(self, student_id):
    """Request emergency pickup"""
    # Create dialog window
    dialog = tk.Toplevel(self.root)
    dialog.title("Emergency Contact Request")
    dialog.geometry("600x450")
    dialog.transient(self.root)
    dialog.grab_set()

    # Main frame with padding
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Emergency Contact Request",
             font=('Arial', 14, 'bold'), foreground='red').pack(pady=(0, 20))

    # Ensure table exists
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='emergency_pickup_requests'
        """)

        if not cursor.fetchone():
            cursor.execute("""
            CREATE TABLE emergency_pickup_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                pickup_person TEXT NOT NULL,
                reason TEXT,
                time_needed TEXT,
                contact_phone TEXT,
                request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'Pending'
            )
            """)
            conn.commit()

        conn.close()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to initialize database: {str(e)}")
        dialog.destroy()
        return

    # Create form fields
    fields = {}

    # Pickup Person
    ttk.Label(main_frame, text="Who will be picking up the student? *").pack(anchor='w', pady=(5, 0))
    fields['pickup_person'] = ttk.Entry(main_frame, width=50)
    fields['pickup_person'].pack(fill=tk.X, pady=(0, 10))

    # Reason
    ttk.Label(main_frame, text="Reason for emergency pickup: *").pack(anchor='w', pady=(5, 0))
    fields['reason'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
    fields['reason'].pack(fill=tk.X, pady=(0, 10))

    # Time Needed
    ttk.Label(main_frame, text="Time needed (HH:MM AM/PM): *").pack(anchor='w', pady=(5, 0))
    fields['time_needed'] = ttk.Entry(main_frame, width=50)
    fields['time_needed'].pack(fill=tk.X, pady=(0, 10))
    # Set default to current time
    fields['time_needed'].insert(0, datetime.datetime.now().strftime('%I:%M %p'))

    # Contact Phone
    ttk.Label(main_frame, text="Contact Phone Number: *").pack(anchor='w', pady=(5, 0))
    fields['contact_phone'] = ttk.Entry(main_frame, width=50)
    fields['contact_phone'].pack(fill=tk.X, pady=(0, 10))

    def submit_request():
        # Validate required fields
        if not fields['pickup_person'].get():
            messagebox.showwarning("Validation Error", "Please enter who will pick up the student.")
            return

        if not fields['reason'].get('1.0', tk.END).strip():
            messagebox.showwarning("Validation Error", "Please provide a reason for the emergency pickup.")
            return

        if not fields['time_needed'].get():
            messagebox.showwarning("Validation Error", "Please enter the time needed.")
            return

        if not fields['contact_phone'].get():
            messagebox.showwarning("Validation Error", "Please enter a contact phone number.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Insert emergency pickup request
            cursor.execute("""
            INSERT INTO emergency_pickup_requests (student_id, pickup_person, reason,
                                                   time_needed, contact_phone)
            VALUES (?, ?, ?, ?, ?)
            """, (
                student_id,
                fields['pickup_person'].get(),
                fields['reason'].get('1.0', tk.END).strip(),
                fields['time_needed'].get(),
                fields['contact_phone'].get()
            ))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Emergency pickup request submitted!\n\n"
                                          "The university administration has been notified and will assist your student.\n"
                                          "You will be contacted shortly.")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit request: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text="Submit Request", command=submit_request).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.emergency_pickup_request = emergency_pickup_request
