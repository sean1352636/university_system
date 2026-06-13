"""
Export management functions - exporting housing data to various formats.
Handles CSV, PDF, and Excel exports for housing data.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import csv
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity
from education_system.university_system.core.i18n import get_text as _t

def export_data_gui(self, data_type):
        """Export data to CSV with GUI feedback"""
        try:
            import csv
            from tkinter import filedialog

            # Let user choose save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title=f"Save {data_type.title()} Data"
            )

            if not filename:
                return

            conn = get_connection()
            cursor = conn.cursor()

            if data_type == 'buildings':
                cursor.execute('''
                SELECT building_id, building_name, address, campus_location, total_rooms, available_rooms,
                       has_elevator, has_accessible_rooms, has_kitchen, has_laundry, created_at
                FROM housing_buildings
                ORDER BY building_name
                ''')
                headers = ['Building ID', 'Building Name', 'Address', 'Campus Location',
                          'Total Rooms', 'Available Rooms', 'Has Elevator', 'Has Accessible Rooms',
                          'Has Kitchen', 'Has Laundry', 'Created At']

            elif data_type == 'rooms':
                cursor.execute('''
                SELECT r.room_id, b.building_name, r.room_number, r.floor_number, r.room_type,
                       r.max_occupants, r.current_occupants, r.is_accessible, r.status, r.monthly_rent
                FROM housing_rooms r
                JOIN housing_buildings b ON r.building_id = b.building_id
                ORDER BY b.building_name, r.floor_number, r.room_number
                ''')
                headers = ['Room ID', 'Building', 'Room Number', 'Floor', 'Type',
                          'Max Occupants', 'Current Occupants', 'Accessible', 'Status', 'Monthly Rent']

            elif data_type == 'assignments':
                cursor.execute('''
                SELECT a.assignment_id, a.student_id, s.first_name, s.last_name,
                       b.building_name, r.room_number, a.move_in_date, a.planned_move_out_date,
                       a.monthly_rent, a.status, a.assigned_by
                FROM housing_assignments a
                JOIN students s ON a.student_id = s.student_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                ORDER BY a.created_at DESC
                ''')
                headers = ['Assignment ID', 'Student ID', 'First Name', 'Last Name',
                          'Building', 'Room', 'Move In Date', 'Planned Move Out',
                          'Monthly Rent', 'Status', 'Assigned By']

            elif data_type == 'applications':
                cursor.execute('''
                SELECT app.application_id, app.student_id, s.first_name, s.last_name,
                       app.application_date, b.building_name, app.preferred_room_type,
                       app.requested_move_in_date, app.requested_duration_months, app.status
                FROM housing_applications app
                JOIN students s ON app.student_id = s.student_id
                LEFT JOIN housing_buildings b ON app.preferred_building_id = b.building_id
                ORDER BY app.application_date DESC
                ''')
                headers = ['Application ID', 'Student ID', 'First Name', 'Last Name',
                          'Application Date', 'Preferred Building', 'Preferred Room Type',
                          'Requested Move In', 'Duration (Months)', 'Status']

            elif data_type == 'payments':
                cursor.execute('''
                SELECT p.source_payment_id, p.student_id, s.first_name, s.last_name,
                       COALESCE(p.payment_type, 'Rent'),
                       p.amount, p.payment_date, p.payment_method, p.payment_period_start,
                       p.payment_period_end, p.status, b.building_name, r.room_number
                FROM payments p
                JOIN students s ON p.student_id = s.student_id
                JOIN housing_assignments a ON p.reference_id = a.assignment_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                WHERE p.source_type = 'housing'
                ORDER BY p.payment_date DESC
                ''')
                headers = ['Payment ID', 'Student ID', 'First Name', 'Last Name',
                          'Type',
                          'Amount', 'Payment Date', 'Payment Method', 'Period Start',
                          'Period End', 'Status', 'Building', 'Room']

            elif data_type == 'maintenance':
                cursor.execute('''
                SELECT m.request_id, m.student_id, s.first_name, s.last_name,
                       b.building_name, r.room_number, m.request_date, m.issue_type,
                       m.description, m.priority, m.status, m.assigned_to, m.completion_date
                FROM housing_maintenance_requests m
                JOIN students s ON m.student_id = s.student_id
                JOIN housing_rooms r ON m.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                ORDER BY m.request_date DESC
                ''')
                headers = ['Request ID', 'Student ID', 'First Name', 'Last Name',
                          'Building', 'Room', 'Request Date', 'Issue Type',
                          'Description', 'Priority', 'Status', 'Assigned To', 'Completion Date']

            data = cursor.fetchall()
            conn.close()

            # Write to CSV
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                writer.writerows(data)

            messagebox.showinfo("Success", f"{data_type.title()} data exported successfully to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export data: {str(e)}")
