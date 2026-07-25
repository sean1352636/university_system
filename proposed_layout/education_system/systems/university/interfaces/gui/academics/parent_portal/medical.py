from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from education_system.systems.university.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from education_system.systems.university.domain.academics.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility



from education_system.systems.university.interfaces.gui.academics.parent_portal.base import ParentPortalGUI

def show_medical_interface(self):
    """Show medical information interface"""
    self.clear_content()
    self.update_status("Medical Information")

    title = ttk.Label(self.content_frame, text="Medical Information", style='Title.TLabel', font=('Arial', 20, 'bold'))
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

    # Medical information display frame
    medical_frame = ttk.LabelFrame(self.content_frame, text="Medical Information", padding=15)
    medical_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def load_medical_info():
        # Clear existing widgets
        for widget in medical_frame.winfo_children():
            widget.destroy()

        selected_child = child_var.get()
        if not selected_child:
            ttk.Label(medical_frame, text="Please select a child").pack(pady=20)
            return

        student_id = selected_child.split("ID: ")[1].rstrip(")")

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Load medical data from multiple tables
            has_data = False
            info_container = ttk.Frame(medical_frame)
            info_container.pack(fill=tk.BOTH, expand=True)

            # Left column - Conditions and Allergies
            left_frame = ttk.LabelFrame(info_container, text="Medical Conditions & Allergies", padding=10)
            left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

            # Load medical conditions
            cursor.execute("""
                SELECT condition_name, severity, status, notes
                FROM medical_conditions
                WHERE student_id = ? AND status = 'active'
            """, (student_id,))
            conditions = cursor.fetchall()

            if conditions:
                has_data = True
                ttk.Label(left_frame, text="Active Conditions:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=3)
                for cond in conditions:
                    cond_text = f"• {cond[0]} ({cond[1] or 'severity unknown'})"
                    ttk.Label(left_frame, text=cond_text, font=('Arial', 10)).pack(anchor='w', pady=1)
            else:
                ttk.Label(left_frame, text="No active medical conditions", font=('Arial', 10)).pack(anchor='w', pady=3)

            # Load allergies
            cursor.execute("""
                SELECT allergen, severity, reaction_description
                FROM allergies
                WHERE student_id = ?
            """, (student_id,))
            allergies = cursor.fetchall()

            if allergies:
                has_data = True
                ttk.Label(left_frame, text="\nAllergies:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=3)
                for allergy in allergies:
                    allergy_text = f"• {allergy[0]} ({allergy[1] or 'unknown severity'})"
                    ttk.Label(left_frame, text=allergy_text, font=('Arial', 10)).pack(anchor='w', pady=1)
                    if allergy[2]:
                        ttk.Label(left_frame, text=f"  Reaction: {allergy[2]}", font=('Arial', 9, 'italic')).pack(anchor='w')
            else:
                ttk.Label(left_frame, text="\nNo allergies on record", font=('Arial', 10)).pack(anchor='w', pady=3)

            # Right column - Medications & Emergency Contact
            right_frame = ttk.LabelFrame(info_container, text="Medications & Contacts", padding=10)
            right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

            # Load student_medical_info for medications and contacts
            cursor.execute("""
                SELECT medication_name, dosage, administration_time, emergency_contact, doctor_contact, notes
                FROM student_medical_info
                WHERE student_id = ?
            """, (student_id,))
            med_info = cursor.fetchall()

            if med_info:
                has_data = True
                medications = [m for m in med_info if m[0]]
                if medications:
                    ttk.Label(right_frame, text="Medications:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=3)
                    for med in medications:
                        med_text = f"• {med[0]}"
                        if med[1]:
                            med_text += f" - {med[1]}"
                        if med[2]:
                            med_text += f" ({med[2]})"
                        ttk.Label(right_frame, text=med_text, font=('Arial', 10)).pack(anchor='w', pady=1)

                # Get emergency contact from first record
                if med_info[0][3]:
                    ttk.Label(right_frame, text=f"\nEmergency Contact: {med_info[0][3]}", font=('Arial', 10)).pack(anchor='w', pady=3)
                if med_info[0][4]:
                    ttk.Label(right_frame, text=f"Doctor Contact: {med_info[0][4]}", font=('Arial', 10)).pack(anchor='w', pady=3)
            else:
                ttk.Label(right_frame, text="No medication information on record", font=('Arial', 10)).pack(anchor='w', pady=3)

            # Load health_records for recent records
            cursor.execute("""
                SELECT record_type, record_date, description, provider
                FROM health_records
                WHERE student_id = ? AND confidential = 0
                ORDER BY record_date DESC LIMIT 5
            """, (student_id,))
            health_recs = cursor.fetchall()

            if health_recs:
                has_data = True
                records_frame = ttk.LabelFrame(medical_frame, text="Recent Health Records", padding=10)
                records_frame.pack(fill=tk.X, pady=(10, 0))

                for rec in health_recs:
                    rec_text = f"• {rec[1] or 'N/A'} - {rec[0]}: {rec[2] or 'No description'}"
                    ttk.Label(records_frame, text=rec_text, font=('Arial', 9)).pack(anchor='w', pady=1)

            if not has_data:
                ttk.Label(medical_frame, text="No medical information found for this student",
                         font=('Arial', 11)).pack(pady=20)

            # Update button
            ttk.Button(medical_frame, text="Update Medical Information",
                      command=lambda: self.update_medical_info(student_id)).pack(pady=10)

            conn.close()

        except Exception as e:
            ttk.Label(medical_frame, text=f"Error loading medical information: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    ttk.Button(child_frame, text="Load Medical Info", command=load_medical_info).pack(side=tk.LEFT, padx=5)

    # Load initial data
    load_medical_info()
ParentPortalGUI.show_medical_interface = show_medical_interface

def update_medical_info(self, student_id):
    """Update medical information for a student"""
    # Create dialog window
    dialog = tk.Toplevel(self.root)
    dialog.title("Update Medical Information")
    dialog.geometry("650x750")
    dialog.minsize(600, 600)
    dialog.transient(self.root)
    dialog.grab_set()

    # Create scrollable canvas for main content
    canvas_container = ttk.Frame(dialog)
    canvas_container.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(canvas_container)
    scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)
    main_frame = ttk.Frame(canvas, padding=20)

    main_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=main_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Bind mousewheel scrolling
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    ttk.Label(main_frame, text="Update Medical Information",
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Fetch existing medical info
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='medical_info'
        """)

        if not cursor.fetchone():
            # Create table if it doesn't exist
            cursor.execute("""
            CREATE TABLE medical_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                blood_type TEXT,
                allergies TEXT,
                medications TEXT,
                conditions TEXT,
                doctor_name TEXT,
                doctor_phone TEXT,
                insurance_provider TEXT,
                insurance_policy TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()

        cursor.execute("""
        SELECT blood_type, allergies, medications, conditions,
               doctor_name, doctor_phone, insurance_provider, insurance_policy
        FROM medical_info WHERE student_id = ?
        """, (student_id,))

        existing_data = cursor.fetchone()
        conn.close()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load medical information: {str(e)}")
        dialog.destroy()
        return

    # Create form fields
    fields = {}

    # Blood Type
    ttk.Label(main_frame, text="Blood Type:").pack(anchor='w', pady=(5, 0))
    fields['blood_type'] = ttk.Combobox(main_frame, width=50, state="readonly")
    fields['blood_type']['values'] = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'Unknown']
    fields['blood_type'].pack(fill=tk.X, pady=(0, 10))
    if existing_data and existing_data[0]:
        fields['blood_type'].set(existing_data[0])

    # Allergies
    ttk.Label(main_frame, text="Allergies (one per line):").pack(anchor='w', pady=(5, 0))
    fields['allergies'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
    fields['allergies'].pack(fill=tk.X, pady=(0, 10))
    if existing_data and existing_data[1]:
        fields['allergies'].insert('1.0', existing_data[1])

    # Medications
    ttk.Label(main_frame, text="Current Medications (one per line):").pack(anchor='w', pady=(5, 0))
    fields['medications'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
    fields['medications'].pack(fill=tk.X, pady=(0, 10))
    if existing_data and existing_data[2]:
        fields['medications'].insert('1.0', existing_data[2])

    # Conditions
    ttk.Label(main_frame, text="Medical Conditions (one per line):").pack(anchor='w', pady=(5, 0))
    fields['conditions'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
    fields['conditions'].pack(fill=tk.X, pady=(0, 10))
    if existing_data and existing_data[3]:
        fields['conditions'].insert('1.0', existing_data[3])

    # Doctor Name
    ttk.Label(main_frame, text="Doctor Name:").pack(anchor='w', pady=(5, 0))
    fields['doctor_name'] = ttk.Entry(main_frame, width=50)
    fields['doctor_name'].pack(fill=tk.X, pady=(0, 10))
    if existing_data and existing_data[4]:
        fields['doctor_name'].insert(0, existing_data[4])

    # Doctor Phone
    ttk.Label(main_frame, text="Doctor Phone:").pack(anchor='w', pady=(5, 0))
    fields['doctor_phone'] = ttk.Entry(main_frame, width=50)
    fields['doctor_phone'].pack(fill=tk.X, pady=(0, 10))
    if existing_data and existing_data[5]:
        fields['doctor_phone'].insert(0, existing_data[5])

    # Insurance Provider
    ttk.Label(main_frame, text="Insurance Provider:").pack(anchor='w', pady=(5, 0))
    fields['insurance_provider'] = ttk.Entry(main_frame, width=50)
    fields['insurance_provider'].pack(fill=tk.X, pady=(0, 10))
    if existing_data and existing_data[6]:
        fields['insurance_provider'].insert(0, existing_data[6])

    # Insurance Policy
    ttk.Label(main_frame, text="Insurance Policy Number:").pack(anchor='w', pady=(5, 0))
    fields['insurance_policy'] = ttk.Entry(main_frame, width=50)
    fields['insurance_policy'].pack(fill=tk.X, pady=(0, 10))
    if existing_data and existing_data[7]:
        fields['insurance_policy'].insert(0, existing_data[7])

    def save_info():
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Update existing record
            cursor.execute("""
            UPDATE medical_info
            SET blood_type = ?, allergies = ?, medications = ?, conditions = ?,
                doctor_name = ?, doctor_phone = ?, insurance_provider = ?,
                insurance_policy = ?, last_updated = CURRENT_TIMESTAMP
            WHERE student_id = ?
            """, (
                fields['blood_type'].get(),
                fields['allergies'].get('1.0', tk.END).strip(),
                fields['medications'].get('1.0', tk.END).strip(),
                fields['conditions'].get('1.0', tk.END).strip(),
                fields['doctor_name'].get(),
                fields['doctor_phone'].get(),
                fields['insurance_provider'].get(),
                fields['insurance_policy'].get(),
                student_id
            ))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Medical information updated successfully!")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update medical information: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text="Save", command=save_info).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.update_medical_info = update_medical_info

def add_medical_info(self, student_id):
    """Add medical information for a student"""
    # Create dialog window
    dialog = tk.Toplevel(self.root)
    dialog.title("Add Medical Information")
    dialog.geometry("600x700")
    dialog.transient(self.root)
    dialog.grab_set()

    # Main frame with padding
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Add Medical Information",
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Ensure table exists
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='medical_info'
        """)

        if not cursor.fetchone():
            cursor.execute("""
            CREATE TABLE medical_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                blood_type TEXT,
                allergies TEXT,
                medications TEXT,
                conditions TEXT,
                doctor_name TEXT,
                doctor_phone TEXT,
                insurance_provider TEXT,
                insurance_policy TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    # Blood Type
    ttk.Label(main_frame, text="Blood Type:").pack(anchor='w', pady=(5, 0))
    fields['blood_type'] = ttk.Combobox(main_frame, width=50, state="readonly")
    fields['blood_type']['values'] = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'Unknown']
    fields['blood_type'].pack(fill=tk.X, pady=(0, 10))

    # Allergies
    ttk.Label(main_frame, text="Allergies (one per line):").pack(anchor='w', pady=(5, 0))
    fields['allergies'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
    fields['allergies'].pack(fill=tk.X, pady=(0, 10))

    # Medications
    ttk.Label(main_frame, text="Current Medications (one per line):").pack(anchor='w', pady=(5, 0))
    fields['medications'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
    fields['medications'].pack(fill=tk.X, pady=(0, 10))

    # Conditions
    ttk.Label(main_frame, text="Medical Conditions (one per line):").pack(anchor='w', pady=(5, 0))
    fields['conditions'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
    fields['conditions'].pack(fill=tk.X, pady=(0, 10))

    # Doctor Name
    ttk.Label(main_frame, text="Doctor Name:").pack(anchor='w', pady=(5, 0))
    fields['doctor_name'] = ttk.Entry(main_frame, width=50)
    fields['doctor_name'].pack(fill=tk.X, pady=(0, 10))

    # Doctor Phone
    ttk.Label(main_frame, text="Doctor Phone:").pack(anchor='w', pady=(5, 0))
    fields['doctor_phone'] = ttk.Entry(main_frame, width=50)
    fields['doctor_phone'].pack(fill=tk.X, pady=(0, 10))

    # Insurance Provider
    ttk.Label(main_frame, text="Insurance Provider:").pack(anchor='w', pady=(5, 0))
    fields['insurance_provider'] = ttk.Entry(main_frame, width=50)
    fields['insurance_provider'].pack(fill=tk.X, pady=(0, 10))

    # Insurance Policy
    ttk.Label(main_frame, text="Insurance Policy Number:").pack(anchor='w', pady=(5, 0))
    fields['insurance_policy'] = ttk.Entry(main_frame, width=50)
    fields['insurance_policy'].pack(fill=tk.X, pady=(0, 10))

    def save_info():
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Insert new record
            cursor.execute("""
            INSERT INTO medical_info (student_id, blood_type, allergies, medications, conditions,
                                    doctor_name, doctor_phone, insurance_provider, insurance_policy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                student_id,
                fields['blood_type'].get(),
                fields['allergies'].get('1.0', tk.END).strip(),
                fields['medications'].get('1.0', tk.END).strip(),
                fields['conditions'].get('1.0', tk.END).strip(),
                fields['doctor_name'].get(),
                fields['doctor_phone'].get(),
                fields['insurance_provider'].get(),
                fields['insurance_policy'].get()
            ))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Medical information added successfully!")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add medical information: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text="Save", command=save_info).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.add_medical_info = add_medical_info
