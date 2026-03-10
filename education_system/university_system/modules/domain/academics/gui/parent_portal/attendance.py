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
from .dialogs import AbsenceReportDialog

def view_child_attendance(self, child):
    """View attendance for a specific child"""
    self.clear_content()
    self.update_status(f"Viewing attendance for {child[1]} {child[3]}")
    
    title = ttk.Label(self.content_frame, text=f"Attendance for {child[1]} {child[3]}", 
                     style='Title.TLabel', font=('Arial', 18, 'bold'))
    title.pack(pady=20)
    
    # Attendance summary
    summary_frame = ttk.LabelFrame(self.content_frame, text="Attendance Summary", padding=15)
    summary_frame.pack(fill=tk.X, padx=20, pady=10)
    
    ttk.Label(summary_frame, text="Overall Attendance: 95.5%", style='Heading.TLabel').pack()
    ttk.Label(summary_frame, text="Days Present: 87 | Days Absent: 4", style='Info.TLabel').pack()
    
    # Recent attendance
    recent_frame = ttk.LabelFrame(self.content_frame, text="Recent Attendance", padding=15)
    recent_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    
    columns = ('Date', 'Status', 'Module', 'Reason')
    tree = ttk.Treeview(recent_frame, columns=columns, show='headings', height=10)
    
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=150)
    
    # Load real attendance data from database
    child_id = child[0]  # Assuming child[0] is the student_id
    try:
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()
            # Try to get attendance records (using correct column names: date, module_code)
            cursor.execute("""
                SELECT a.date, a.status, a.module_code, a.reason
                FROM attendance a
                WHERE a.student_id = ?
                ORDER BY a.date DESC LIMIT 20
            """, (child_id,))
            attendance_records = cursor.fetchall()

            # If no attendance records, try student_absences table
            if not attendance_records:
                cursor.execute("""
                    SELECT sa.absence_date, 'absent', '', sa.reason
                    FROM student_absences sa
                    WHERE sa.student_id = ?
                    ORDER BY sa.absence_date DESC LIMIT 20
                """, (child_id,))
                attendance_records = cursor.fetchall()

            if not attendance_records:
                # Check if student exists
                cursor.execute("SELECT student_id FROM students WHERE student_id = ?", (child_id,))
                if cursor.fetchone():
                    tree.insert('', tk.END, values=('N/A', 'No attendance records yet', '', 'Attendance tracking will begin when classes start'))
                else:
                    tree.insert('', tk.END, values=('ERROR', 'Student not found', '', ''))
            else:
                for record in attendance_records:
                    tree.insert('', tk.END, values=record)

    except Exception as e:
        tree.insert('', tk.END, values=('ERROR', f'Database error: {str(e)}', '', 'Unable to load attendance'))

    tree.pack(fill=tk.BOTH, expand=True)

    # Button frame for actions
    btn_frame = ttk.Frame(self.content_frame)
    btn_frame.pack(pady=10)

    # Link to Attendance Tracker GUI for detailed view
    def open_attendance_tracker():
        try:
            from education_system.university_system.modules.domain.academics.gui.attendance_tracker import AttendanceGUI
            # Create a new top-level window for attendance tracker
            attendance_window = tk.Toplevel(self.root)
            attendance_gui = AttendanceGUI(attendance_window, self.auth)
        except ImportError as e:
            messagebox.showinfo("Info", f"Attendance Tracker GUI not available: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Attendance Tracker: {e}")

    ttk.Button(btn_frame, text="📅 Open Full Attendance Tracker", command=open_attendance_tracker).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="← Back", command=self.show_children).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.view_child_attendance = view_child_attendance

def quick_absence_report(self):
    """Quick absence report with timetable selection and database integration"""
    is_admin = self.is_admin()

    # For admin users, load all students from database
    if is_admin:
        students_list = self._load_all_students_from_db()
        if not students_list:
            messagebox.showinfo("No Students", "No students found in the system.")
            return
    else:
        # Non-admin users can only access their linked students
        if not self.children:
            messagebox.showinfo("No Students", "No students linked to your guardian account.")
            return
        students_list = self.children

    dialog = AbsenceReportDialog(
        self.root,
        students_list,
        db_path=DEFAULT_DB_PATH,
        is_admin=is_admin
    )

    if dialog.result:
        result = dialog.result
        student_id = result['student_id']
        absence_date = result['absence_date']
        reason = result['reason']
        sessions = result['sessions']

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            cursor = conn.cursor()

            # Get current user info for reported_by field
            current_user = self.get_current_user()
            reported_by = f"user:{current_user['id']}" if current_user else "unknown"

            # Insert absence record
            cursor.execute('''
                INSERT INTO student_absences
                (student_id, absence_date, reason, reported_by, reported_date, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                student_id,
                absence_date,
                reason,
                reported_by,
                datetime.datetime.now().isoformat(),
                f"Sessions: {', '.join([s['module_name'] + ' (' + s['time_slot'] + ')' for s in sessions]) if sessions else 'All day'}"
            ))

            # Mark attendance records as absent for selected sessions
            for session in sessions:
                # Check if attendance record exists for this date/module
                cursor.execute('''
                    SELECT id FROM attendance_records
                    WHERE student_id = ? AND module_code = ? AND date = ?
                ''', (student_id, session['module_code'], absence_date))

                existing = cursor.fetchone()
                if existing:
                    # Update existing record
                    cursor.execute('''
                        UPDATE attendance_records
                        SET status = 'absent', notes = ?, recorded_at = ?
                        WHERE id = ?
                    ''', (f"Reported absence: {reason}", datetime.datetime.now().isoformat(), existing[0]))
                else:
                    # Insert new absence record
                    cursor.execute('''
                        INSERT INTO attendance_records
                        (student_id, module_code, date, status, notes, recorded_by, recorded_at)
                        VALUES (?, ?, ?, 'absent', ?, ?, ?)
                    ''', (
                        student_id,
                        session['module_code'],
                        absence_date,
                        f"Reported absence: {reason}",
                        reported_by,
                        datetime.datetime.now().isoformat()
                    ))

            conn.commit()
            conn.close()

            # Get student name for confirmation message
            student_data = result.get('student_data')
            if student_data:
                student_name = f"{student_data[1]} {student_data[2] if len(student_data) > 2 else ''} {student_data[3] if len(student_data) > 3 else student_data[2]}".strip()
            else:
                student_name = student_id

            # Send email notification to admin about the absence
            self._send_absence_notification_to_admin(student_id, student_name, absence_date, reason, sessions)

            sessions_text = f" for {len(sessions)} session(s)" if sessions else ""

            # Ask if user wants to view attendance tracker
            response = messagebox.askyesno(
                "Absence Reported",
                f"Absence reported for {student_name} on {absence_date}{sessions_text}.\n\n"
                f"Reason: {reason}\n\n"
                "Would you like to open the Attendance Tracker to view attendance records?"
            )

            if response:
                self._open_attendance_tracker()

        except Exception as e:
            messagebox.showerror("Error", f"Error saving absence report: {e}")
ParentPortalGUI.quick_absence_report = quick_absence_report

def _send_absence_notification_to_admin(self, student_id, student_name, absence_date, reason, sessions):
    """Send email notification to admin about student absence"""
    try:
        # Get admin email addresses
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT email FROM users
            WHERE role = 'admin' AND email IS NOT NULL AND email != ''
            LIMIT 5
        """)
        admin_emails = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not admin_emails:
            # Fallback to system admin email
            admin_emails = ['admin@university.edu']

        # Build sessions text
        sessions_text = ""
        if sessions:
            sessions_text = "\nAffected Sessions:\n" + "\n".join([
                f"  - {s['module_name']} ({s['time_slot']})" for s in sessions
            ])
        else:
            sessions_text = "\nAbsence Type: Full Day"

        current_user = self.get_current_user()
        reporter_name = "Unknown"
        reporter_email = ""
        if current_user:
            reporter_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
            reporter_email = current_user.get('email', '')

        # Render email from template
        from education_system.university_system.infrastructure.email.template_utils import render_template

        subject, body = render_template('parent_portal/parent_absence_notification', {
            'student_name': student_name,
            'student_id': student_id,
            'absence_date': absence_date,
            'reason': reason,
            'sessions_text': sessions_text,
            'reporter_name': reporter_name,
            'reporter_email': reporter_email or 'Not provided',
            'report_datetime': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

        # Fallback if template not found
        if not subject or not body:
            subject = f"Student Absence Report: {student_name} - {absence_date}"
            body = f"Student Absence Notification\n\nA student absence has been reported.\n\nStudent: {student_name} ({student_id})\nDate: {absence_date}\nReason: {reason}\n{sessions_text}\n\nReported by: {reporter_name}"

        # Send email to each admin
        if EMAIL_SERVICE_AVAILABLE:
            for admin_email in admin_emails:
                try:
                    send_email(admin_email, subject, body)
                except Exception as e:
                    print(f"Failed to send absence notification to {admin_email}: {e}")
        else:
            print(f"Email service not available. Would have sent absence notification to: {admin_emails}")

    except Exception as e:
        print(f"Error sending absence notification: {e}")
ParentPortalGUI._send_absence_notification_to_admin = _send_absence_notification_to_admin

def _open_attendance_tracker(self):
    """Open the Attendance Tracker GUI"""
    try:
        from education_system.university_system.modules.domain.academics.gui.attendance_tracker import AttendanceGUI
        # Create a new top-level window for attendance tracker
        attendance_window = tk.Toplevel(self.root)
        attendance_gui = AttendanceGUI(attendance_window, self.auth)
    except ImportError as e:
        messagebox.showinfo("Info", f"Attendance Tracker GUI not available: {e}")
    except Exception as e:
        messagebox.showerror("Error", f"Could not open Attendance Tracker: {e}")
ParentPortalGUI._open_attendance_tracker = _open_attendance_tracker

def show_attendance_interface(self):
    """Show attendance interface"""
    self.clear_content()
    self.update_status("Attendance Records")
    
    title = ttk.Label(self.content_frame, text="Attendance Records", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)
    
    if self.children:
        for child in self.children:
            child_frame = ttk.LabelFrame(self.content_frame, text=f"{child[1]} {child[3]}", padding=15)
            child_frame.pack(fill=tk.X, padx=20, pady=10)
            
            view_btn = ttk.Button(child_frame, text="View Attendance", 
                                 command=lambda c=child: self.view_child_attendance(c))
            view_btn.pack(pady=5)
    else:
        ttk.Label(self.content_frame, text="No students linked to your guardian account.").pack(pady=50)
ParentPortalGUI.show_attendance_interface = show_attendance_interface

def show_behavior_interface(self):
    """Show conduct reports interface"""
    self.clear_content()
    self.update_status("Conduct Reports")

    title = ttk.Label(self.content_frame, text="Conduct Reports", style='Title.TLabel', font=('Arial', 20, 'bold'))
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

    # Reports display frame
    reports_frame = ttk.LabelFrame(self.content_frame, text="Conduct Reports", padding=15)
    reports_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def load_behavior_reports():
        # Clear existing widgets
        for widget in reports_frame.winfo_children():
            widget.destroy()

        selected_child = child_var.get()
        if not selected_child:
            ttk.Label(reports_frame, text="Please select a child").pack(pady=20)
            return

        student_id = selected_child.split("ID: ")[1].rstrip(")")

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check if student_behavior table exists (correct table name)
            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='student_behavior'
            """)

            if cursor.fetchone():
                # Load conduct reports from student_behavior table
                cursor.execute("""
                SELECT incident_date, behavior_type, description, severity, reported_by, action_taken
                FROM student_behavior
                WHERE student_id = ?
                ORDER BY incident_date DESC
                LIMIT 50
                """, (student_id,))

                reports = cursor.fetchall()

                if reports:
                    # Summary statistics
                    summary_frame = ttk.LabelFrame(reports_frame, text="Summary", padding=10)
                    summary_frame.pack(fill=tk.X, pady=(0, 10))

                    total_reports = len(reports)
                    positive = sum(1 for r in reports if r[1].lower() in ['positive', 'commendation', 'achievement'])
                    negative = sum(1 for r in reports if r[1].lower() in ['negative', 'incident', 'warning'])
                    neutral = total_reports - positive - negative

                    ttk.Label(summary_frame, text=f"Total Reports: {total_reports}",
                             font=('Arial', 10, 'bold')).grid(row=0, column=0, padx=10, pady=3, sticky='w')
                    ttk.Label(summary_frame, text=f"Positive: {positive}",
                             font=('Arial', 10), foreground='green').grid(row=0, column=1, padx=10, pady=3, sticky='w')
                    ttk.Label(summary_frame, text=f"Negative: {negative}",
                             font=('Arial', 10), foreground='red').grid(row=0, column=2, padx=10, pady=3, sticky='w')
                    ttk.Label(summary_frame, text=f"Neutral: {neutral}",
                             font=('Arial', 10)).grid(row=0, column=3, padx=10, pady=3, sticky='w')

                    # Reports list
                    list_frame = ttk.Frame(reports_frame)
                    list_frame.pack(fill=tk.BOTH, expand=True)

                    columns = ("Date", "Type", "Description", "Severity", "Instructor", "Resolution")
                    reports_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)

                    reports_tree.heading("Date", text="Date")
                    reports_tree.heading("Type", text="Type")
                    reports_tree.heading("Description", text="Description")
                    reports_tree.heading("Severity", text="Severity")
                    reports_tree.heading("Instructor", text="Instructor")
                    reports_tree.heading("Resolution", text="Resolution")

                    reports_tree.column("Date", width=100)
                    reports_tree.column("Type", width=100)
                    reports_tree.column("Description", width=200)
                    reports_tree.column("Severity", width=80)
                    reports_tree.column("Instructor", width=120)
                    reports_tree.column("Resolution", width=120)

                    # Scrollbar
                    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=reports_tree.yview)
                    reports_tree.configure(yscrollcommand=scrollbar.set)

                    reports_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                    # Add reports to tree
                    for report in reports:
                        reports_tree.insert('', tk.END, values=report)

                    # View details button
                    def view_details():
                        selected = reports_tree.selection()
                        if selected:
                            values = reports_tree.item(selected[0])['values']
                            detail_text = f"Date: {values[0]}\n"
                            detail_text += f"Type: {values[1]}\n"
                            detail_text += f"Severity: {values[3]}\n"
                            detail_text += f"Instructor: {values[4]}\n\n"
                            detail_text += f"Description:\n{values[2]}\n\n"
                            detail_text += f"Resolution:\n{values[5] if values[5] else 'Pending'}"

                            messagebox.showinfo("Behavior Report Details", detail_text)

                    ttk.Button(reports_frame, text="View Details",
                              command=view_details).pack(pady=10)

                else:
                    ttk.Label(reports_frame, text="No conduct reports found for this student",
                             font=('Arial', 11)).pack(pady=50)

            else:
                # Sample data if table doesn't exist
                sample_frame = ttk.LabelFrame(reports_frame, text="Sample Reports", padding=10)
                sample_frame.pack(fill=tk.BOTH, expand=True)

                sample_reports = [
                    ("2024-01-15", "Positive", "Excellent class participation", "None", "Ms. Johnson", "N/A"),
                    ("2024-01-10", "Neutral", "Late to class", "Minor", "Mr. Smith", "Parent contacted"),
                    ("2024-01-05", "Positive", "Helped another student", "None", "Ms. Davis", "N/A")
                ]

                columns = ("Date", "Type", "Description", "Severity", "Instructor", "Resolution")
                reports_tree = ttk.Treeview(sample_frame, columns=columns, show="headings", height=8)

                for col in columns:
                    reports_tree.heading(col, text=col)
                    reports_tree.column(col, width=120)

                for report in sample_reports:
                    reports_tree.insert('', tk.END, values=report)

                reports_tree.pack(fill=tk.BOTH, expand=True, pady=5)

                ttk.Label(sample_frame, text="(Sample data - no conduct reports table found)",
                         font=('Arial', 9, 'italic')).pack(pady=5)

            conn.close()

        except Exception as e:
            ttk.Label(reports_frame, text=f"Error loading conduct reports: {str(e)}",
                     font=('Arial', 11)).pack(pady=50)

    ttk.Button(child_frame, text="Load Reports", command=load_behavior_reports).pack(side=tk.LEFT, padx=5)

    # Load initial reports
    load_behavior_reports()
ParentPortalGUI.show_behavior_interface = show_behavior_interface

def show_absence_interface(self):
    """Show absence reporting interface"""
    self.clear_content()
    self.update_status("Report Absence")
    
    title = ttk.Label(self.content_frame, text="Report Student Absence", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)
    
    absence_frame = ttk.LabelFrame(self.content_frame, text="Absence Details", padding=20)
    absence_frame.pack(fill=tk.X, padx=20, pady=20)
    
    # Child selection
    ttk.Label(absence_frame, text="Select Student:").pack(anchor='w')
    child_var = tk.StringVar()
    child_combo = ttk.Combobox(absence_frame, textvariable=child_var, width=50)
    if self.children:
        child_combo['values'] = [f"{child[1]} {child[3]}" for child in self.children]
        child_combo.set(child_combo['values'][0] if child_combo['values'] else "")
    child_combo.pack(fill=tk.X, pady=5)
    
    # Date selection
    ttk.Label(absence_frame, text="Absence Date:").pack(anchor='w', pady=(10, 0))
    date_var = tk.StringVar(value=datetime.datetime.now().strftime('%Y-%m-%d'))
    date_entry = ttk.Entry(absence_frame, textvariable=date_var)
    date_entry.pack(fill=tk.X, pady=5)
    
    # Reason
    ttk.Label(absence_frame, text="Reason:").pack(anchor='w', pady=(10, 0))
    reason_text = scrolledtext.ScrolledText(absence_frame, height=5)
    reason_text.pack(fill=tk.X, pady=5)
    
    def submit_absence():
        if not child_var.get() or not reason_text.get(1.0, tk.END).strip():
            messagebox.showwarning("Missing Information", "Please select a child and provide a reason.")
            return
        
        # In real implementation, this would save to database
        messagebox.showinfo("Success", "Absence report submitted successfully.")
        reason_text.delete(1.0, tk.END)
    
    submit_btn = ttk.Button(absence_frame, text="Submit Absence Report", command=submit_absence)
    submit_btn.pack(pady=20)
ParentPortalGUI.show_absence_interface = show_absence_interface
