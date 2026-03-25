"""
Inspection management functions - managing room and building inspections.
Handles inspection scheduling, recording findings, and follow-up actions.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity
from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.modules.domain.housing.services.housing_accommodation import generate_id

def show_inspections(self):
        """Show room inspections interface"""
        self.clear_content()

        ttk.Label(self.content_frame, text="Room Inspections",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Control buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill='x', pady=10)

        ttk.Button(button_frame, text="Schedule Inspection",
                  command=lambda: schedule_inspection_dialog(self)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Record Inspection",
                  command=lambda: record_inspection_dialog(self)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="View Details",
                  command=lambda: view_inspection_details(self, inspections_tree)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Edit Inspection",
                  command=lambda: edit_inspection(self, inspections_tree)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Delete Inspection",
                  command=lambda: delete_inspection(self, inspections_tree)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Refresh",
                  command=lambda: load_inspections(self, inspections_tree)).pack(side='left', padx=5)

        # Inspections list
        list_frame = ttk.Frame(self.content_frame)
        list_frame.pack(fill='both', expand=True, pady=10)

        inspections_tree = ttk.Treeview(list_frame,
                                       columns=('ID', 'Room', 'Date', 'Type', 'Inspector', 'Status', 'Issues'),
                                       show='headings', height=20)

        inspections_tree.heading('ID', text='Inspection ID')
        inspections_tree.heading('Room', text='Room')
        inspections_tree.heading('Date', text='Date')
        inspections_tree.heading('Type', text='Type')
        inspections_tree.heading('Inspector', text='Inspector')
        inspections_tree.heading('Status', text='Status')
        inspections_tree.heading('Issues', text='Issues Found')

        for col in ('ID', 'Room', 'Date', 'Type', 'Inspector', 'Status', 'Issues'):
            inspections_tree.column(col, width=120)

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=inspections_tree.yview)
        inspections_tree.configure(yscrollcommand=scrollbar.set)

        inspections_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Load inspections
        load_inspections(self, inspections_tree)

def schedule_inspection_dialog(self):
        """Schedule a new inspection"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Schedule Inspection")
        dialog.geometry("800x700")
        dialog.transient(self.root)

        ttk.Label(dialog, text="Schedule Room Inspection",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill='both', expand=True)

        # Building selection
        ttk.Label(form_frame, text="Building:").grid(row=0, column=0, sticky='w', pady=5)
        building_var = tk.StringVar()
        building_combo = ttk.Combobox(form_frame, textvariable=building_var, width=28, state='readonly')
        building_combo.grid(row=0, column=1, pady=5, padx=5)

        # Load buildings from database
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()
            conn.close()

            building_dict = {f"{row[1]} (ID: {row[0]})": row[0] for row in buildings}
            building_combo['values'] = list(building_dict.keys())
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load buildings: {str(e)}", parent=dialog)
            building_dict = {}

        # Inspection scope selection
        ttk.Label(form_frame, text="Inspection Scope:").grid(row=1, column=0, sticky='w', pady=5)
        scope_var = tk.StringVar(value="Single Room")
        scope_combo = ttk.Combobox(form_frame, textvariable=scope_var,
                                   values=['Single Room', 'Full Building'],
                                   width=28, state='readonly')
        scope_combo.grid(row=1, column=1, pady=5, padx=5)

        # Room selection (shown only for single room)
        room_label = ttk.Label(form_frame, text="Room Number:")
        room_label.grid(row=2, column=0, sticky='w', pady=5)
        room_var = tk.StringVar()
        room_combo = ttk.Combobox(form_frame, textvariable=room_var, width=28, state='readonly')
        room_combo.grid(row=2, column=1, pady=5, padx=5)

        def update_rooms(*args):
            """Update room dropdown based on selected building"""
            selected_building = building_var.get()
            if selected_building and selected_building in building_dict:
                building_id = building_dict[selected_building]
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT room_id, room_number
                        FROM housing_rooms
                        WHERE building_id = ?
                        ORDER BY room_number
                    ''', (building_id,))
                    rooms = cursor.fetchall()
                    conn.close()

                    room_dict[building_id] = {f"Room {row[1]}": row[0] for row in rooms}
                    room_combo['values'] = list(room_dict.get(building_id, {}).keys())
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load rooms: {str(e)}", parent=dialog)

        def toggle_room_selection(*args):
            """Show/hide room selection based on scope"""
            if scope_var.get() == "Single Room":
                room_label.grid(row=2, column=0, sticky='w', pady=5)
                room_combo.grid(row=2, column=1, pady=5, padx=5)
            else:
                room_label.grid_remove()
                room_combo.grid_remove()

        room_dict = {}
        building_var.trace('w', update_rooms)
        scope_var.trace('w', toggle_room_selection)

        # Date
        ttk.Label(form_frame, text="Inspection Date:").grid(row=3, column=0, sticky='w', pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        date_entry = ttk.Entry(form_frame, textvariable=date_var, width=30)
        date_entry.grid(row=3, column=1, pady=5, padx=5)

        # Time
        ttk.Label(form_frame, text="Inspection Time:").grid(row=4, column=0, sticky='w', pady=5)
        time_var = tk.StringVar(value="10:00 AM")
        time_entry = ttk.Entry(form_frame, textvariable=time_var, width=30)
        time_entry.grid(row=4, column=1, pady=5, padx=5)

        # Type
        ttk.Label(form_frame, text="Inspection Type:").grid(row=5, column=0, sticky='w', pady=5)
        type_var = tk.StringVar(value="Routine")
        type_combo = ttk.Combobox(form_frame, textvariable=type_var,
                                  values=['Routine', 'Move-in', 'Move-out', 'Maintenance', 'Safety'],
                                  width=28, state='readonly')
        type_combo.grid(row=5, column=1, pady=5, padx=5)

        # Inspector
        ttk.Label(form_frame, text="Inspector:").grid(row=6, column=0, sticky='w', pady=5)
        inspector_var = tk.StringVar()
        inspector_entry = ttk.Entry(form_frame, textvariable=inspector_var, width=30)
        inspector_entry.grid(row=6, column=1, pady=5, padx=5)

        # Notes
        ttk.Label(form_frame, text="Notes:").grid(row=7, column=0, sticky='nw', pady=5)
        notes_text = tk.Text(form_frame, height=4, width=30)
        notes_text.grid(row=7, column=1, pady=5, padx=5)

        # Email notification checkbox
        send_email_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Send email notification to affected students",
                       variable=send_email_var).grid(row=8, column=0, columnspan=2, sticky='w', pady=10)

        def save_inspection():
            # Validation
            selected_building = building_var.get()
            if not selected_building:
                messagebox.showwarning("Building Required", "Please select a building", parent=dialog)
                return

            if scope_var.get() == "Single Room" and not room_var.get().strip():
                messagebox.showwarning("Room Required", "Please select a room", parent=dialog)
                return

            if not inspector_var.get().strip():
                messagebox.showwarning("Inspector Required", "Please enter an inspector name", parent=dialog)
                return

            try:
                # Validate date format
                inspection_date = date_var.get().strip()
                datetime.strptime(inspection_date, '%Y-%m-%d')

                # Get the notes
                notes = notes_text.get("1.0", tk.END).strip()
                inspection_time = time_var.get().strip()

                # Save to database
                conn = get_connection()
                cursor = conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                building_id = building_dict[selected_building]

                # Get rooms to inspect
                if scope_var.get() == "Single Room":
                    # Get specific room_id
                    selected_room = room_var.get()
                    if selected_room in room_dict.get(building_id, {}):
                        room_ids = [room_dict[building_id][selected_room]]
                    else:
                        messagebox.showerror("Error", "Please select a valid room", parent=dialog)
                        conn.close()
                        return
                else:
                    # Get all rooms in building
                    cursor.execute('SELECT room_id FROM housing_rooms WHERE building_id = ?', (building_id,))
                    room_ids = [row[0] for row in cursor.fetchall()]

                if not room_ids:
                    messagebox.showerror("Error", "No rooms found for inspection", parent=dialog)
                    conn.close()
                    return

                inspection_ids = []
                # Insert inspection for each room
                for room_id in room_ids:
                    inspection_id = generate_id('INSP')
                    cursor.execute('''
                    INSERT INTO housing_inspections (
                        inspection_id, room_id, inspection_date, inspection_type,
                        inspector, findings, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'Scheduled', ?, ?)
                    ''', (inspection_id, room_id, inspection_date, type_var.get(),
                         inspector_var.get(), notes, timestamp, timestamp))
                    inspection_ids.append(inspection_id)

                conn.commit()

                # Send email notifications if requested
                if send_email_var.get():
                    send_inspection_emails(self, cursor, building_id, room_ids, inspection_date,
                                               inspection_time, type_var.get(), inspector_var.get(),
                                               notes, scope_var.get() == "Full Building")

                conn.close()

                messagebox.showinfo("Success",
                                  f"Inspection(s) scheduled successfully!\n\n"
                                  f"Total inspections: {len(inspection_ids)}\n"
                                  f"Building: {selected_building}\n"
                                  f"Date: {inspection_date}\n"
                                  f"Type: {type_var.get()}\n"
                                  f"{'Email notifications sent' if send_email_var.get() else 'No emails sent'}",
                                  parent=dialog)
                dialog.destroy()

            except ValueError:
                messagebox.showerror("Error", "Please enter a valid date (YYYY-MM-DD)", parent=dialog)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to schedule inspection: {str(e)}", parent=dialog)
                import traceback
                traceback.print_exc()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Schedule", command=save_inspection).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

def send_inspection_emails(self, cursor, building_id, room_ids, inspection_date,
                               inspection_time, inspection_type, inspector_name, notes, is_building_wide):
        """Send email notifications to students about scheduled inspections"""
        try:
            # Get building info
            cursor.execute('SELECT building_name FROM housing_buildings WHERE building_id = ?', (building_id,))
            building_result = cursor.fetchone()
            building_name = building_result[0] if building_result else "Unknown Building"

            # Get students in the affected rooms
            cursor.execute('''
                SELECT DISTINCT
                    s.student_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    s.email_address,
                    r.room_number
                FROM housing_assignments ha
                JOIN students s ON ha.student_id = s.student_id
                JOIN housing_rooms r ON ha.room_id = r.room_id
                WHERE ha.room_id IN ({})
                AND ha.status = 'Active'
            '''.format(','.join('?' * len(room_ids))), room_ids)

            students = cursor.fetchall()

            if not students:
                print("No active students found in selected rooms")
                return

            # Load appropriate email template
            template_name='housing/building_inspection_notice' if is_building_wide else 'inspection_scheduled'

            try:
                import json
                from education_system.university_system.modules.shared.constants import paths
                template_path = paths.PROJECT_ROOT / 'university_system' / 'templates' / 'email' / f'{template_name}.json'

                with open(template_path, 'r') as f:
                    template = json.load(f)

                # Send email to each student
                from education_system.university_system.infrastructure.email.email_service import send_email

                for student_id, student_name, email, room_number in students:
                    if not email:
                        continue

                    # Replace template variables
                    subject = template['subject'].replace('{{building_name}}', building_name).replace('{{room_number}}', room_number)

                    body = template['body']
                    replacements = {
                        '{{student_name}}': student_name,
                        '{{building_name}}': building_name,
                        '{{room_number}}': room_number,
                        '{{inspection_date}}': inspection_date,
                        '{{inspection_time}}': inspection_time,
                        '{{inspection_type}}': inspection_type,
                        '{{inspector_name}}': inspector_name,
                        '{{notes}}': notes if notes else '',
                        '{{additional_notes}}': notes if notes else ''
                    }

                    for key, value in replacements.items():
                        body = body.replace(key, value)

                    # Send email
                    send_email(
                        to_email=email,
                        subject=subject,
                        body=body,
                        email_type='inspection_notification'
                    )

                print(f"✓ Sent {len(students)} inspection notification emails")

            except Exception as email_error:
                print(f"Error sending emails: {email_error}")
                import traceback
                traceback.print_exc()

        except Exception as e:
            print(f"Error in send_inspection_emails: {e}")
            import traceback
            traceback.print_exc()

def send_post_inspection_email(self, cursor, room_id, inspection_id, inspection_date,
                                   inspection_type, inspector_name, findings, status, action_required, followup_date):
        """Send email notification to students after inspection is completed"""
        try:
            # Get room and building info
            cursor.execute('''
                SELECT r.room_number, b.building_name
                FROM housing_rooms r
                JOIN housing_buildings b ON r.building_id = b.building_id
                WHERE r.room_id = ?
            ''', (room_id,))

            room_info = cursor.fetchone()
            if not room_info:
                print(f"Room {room_id} not found")
                return

            room_number = room_info[0]
            building_name = room_info[1]

            # Get students assigned to this room
            cursor.execute('''
                SELECT DISTINCT
                    s.student_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    s.email_address
                FROM housing_assignments ha
                JOIN students s ON ha.student_id = s.student_id
                WHERE ha.room_id = ?
                AND ha.status = 'Active'
            ''', (room_id,))

            students = cursor.fetchall()

            if not students:
                print(f"No active students found for room {room_number}")
                return

            # Load email service
            from education_system.university_system.infrastructure.email.email_service import send_email

            # Determine which template to use based on status
            if status == 'Issues Found':
                template_name='housing/inspection_issues_found'
            else:
                template_name='housing/inspection_completed'

            # Load email template
            template_path = paths.EMAIL_TEMPLATES_DIR / f"{template_name}.json"
            try:
                with open(template_path, 'r') as f:
                    import json
                    template = json.load(f)
            except Exception as e:
                print(f"Failed to load email template {template_name}: {e}")
                return

            # Determine pass/fail result
            if status == 'Issues Found':
                pass_fail = "FAIL - Issues Identified"
            elif status == 'Completed':
                pass_fail = "PASS - No Issues"
            else:
                pass_fail = status

            # Send email to each student
            emails_sent = 0
            for student in students:
                student_id, student_name, email_address = student

                if not email_address:
                    print(f"No email address for student {student_name}")
                    continue

                # Prepare template variables
                variables = {
                    'student_name': student_name,
                    'building_name': building_name,
                    'room_number': room_number,
                    'inspection_date': inspection_date,
                    'inspection_type': inspection_type,
                    'inspector_name': inspector_name,
                    'status': status,
                    'pass_fail': pass_fail,
                    'findings': findings if findings else 'No issues found',
                    'issues': findings if findings else 'No issues identified',
                    'required_actions': action_required if action_required else 'No action required',
                    'action_required': action_required if action_required else 'No action required at this time',
                    'action_deadline': followup_date if followup_date else 'N/A',
                    'follow_up_instructions': f"A follow-up inspection is scheduled for {followup_date}" if followup_date else ""
                }

                # Render email subject and body
                subject = template['subject']
                body = template['body']

                for key, value in variables.items():
                    subject = subject.replace('{{' + key + '}}', str(value))
                    body = body.replace('{{' + key + '}}', str(value))

                # Send email
                success = send_email(
                    recipient_email=email_address,
                    subject=subject,
                    body=body
                )

                if success:
                    emails_sent += 1
                    print(f"✓ Sent inspection result email to {student_name} ({email_address})")

            print(f"✓ Sent {emails_sent} post-inspection notification emails")

        except Exception as e:
            print(f"Error in send_post_inspection_email: {e}")
            import traceback
            traceback.print_exc()

def record_inspection_dialog(self):
        """Record inspection results"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Record Inspection")
        dialog.geometry("600x500")
        dialog.transient(self.root)

        ttk.Label(dialog, text="Record Inspection Results",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill='both', expand=True)

        # Inspection ID
        ttk.Label(form_frame, text="Inspection ID:").grid(row=0, column=0, sticky='w', pady=5)
        id_var = tk.StringVar()
        id_entry = ttk.Entry(form_frame, textvariable=id_var, width=30)
        id_entry.grid(row=0, column=1, pady=5, padx=5)

        # Status
        ttk.Label(form_frame, text="Status:").grid(row=1, column=0, sticky='w', pady=5)
        status_var = tk.StringVar(value="Completed")
        status_combo = ttk.Combobox(form_frame, textvariable=status_var,
                                    values=['Completed', 'Issues Found', 'Follow-up Required'],
                                    width=28, state='readonly')
        status_combo.grid(row=1, column=1, pady=5, padx=5)

        # Issues found
        ttk.Label(form_frame, text="Issues Found:").grid(row=2, column=0, sticky='nw', pady=5)
        issues_text = tk.Text(form_frame, height=6, width=30)
        issues_text.grid(row=2, column=1, pady=5, padx=5)

        # Pass/Fail
        pass_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Inspection Passed", variable=pass_var).grid(row=3, column=1, sticky='w', pady=5)

        def save_results():
            if not id_var.get().strip():
                messagebox.showwarning("ID Required", "Please enter inspection ID", parent=dialog)
                return

            try:
                inspection_id = id_var.get().strip()
                status = status_var.get()
                issues = issues_text.get("1.0", tk.END).strip()
                passed = pass_var.get()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Update inspection in database
                conn = get_connection()
                cursor = conn.cursor()

                # Check if inspection exists
                cursor.execute('SELECT inspection_id FROM housing_inspections WHERE inspection_id = ?',
                             (inspection_id,))
                if not cursor.fetchone():
                    messagebox.showerror("Error", f"Inspection ID {inspection_id} not found", parent=dialog)
                    conn.close()
                    return

                # Update inspection with results
                cursor.execute('''
                UPDATE housing_inspections
                SET status = ?, findings = ?, action_required = ?, updated_at = ?
                WHERE inspection_id = ?
                ''', (status, issues, 'Follow-up Required' if not passed else 'None', timestamp, inspection_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success",
                                  f"Inspection results recorded successfully!\n\n"
                                  f"Inspection ID: {inspection_id}\n"
                                  f"Status: {status}\n"
                                  f"Passed: {'Yes' if passed else 'No'}",
                                  parent=dialog)
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to record inspection results: {str(e)}", parent=dialog)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Save", command=save_results).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

def view_inspection_details(self, tree):
        """View detailed inspection report"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an inspection to view")
            return

        values = tree.item(selection[0], 'values')
        messagebox.showinfo("Inspection Details",
                          f"Inspection ID: {values[0]}\n"
                          f"Room: {values[1]}\n"
                          f"Date: {values[2]}\n"
                          f"Type: {values[3]}\n"
                          f"Inspector: {values[4]}\n"
                          f"Status: {values[5]}\n"
                          f"Issues: {values[6]}")

def load_inspections(self, tree):
        """Load inspections from database"""
        # Clear existing
        for item in tree.get_children():
            tree.delete(item)

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT i.inspection_id, r.room_number, i.inspection_date, i.inspection_type,
                   i.inspector, i.status, COALESCE(i.findings, 'None')
            FROM housing_inspections i
            JOIN housing_rooms r ON i.room_id = r.room_id
            ORDER BY i.inspection_date DESC
            LIMIT 100
            ''')

            inspections = cursor.fetchall()
            conn.close()

            for inspection in inspections:
                # Convert sqlite3.Row to tuple to avoid errors
                if hasattr(inspection, '__iter__') and not isinstance(inspection, (str, bytes)):
                    values = tuple(inspection)
                else:
                    values = inspection
                tree.insert('', 'end', values=values)

            if not inspections:
                # Insert a message if no inspections found
                tree.insert('', 'end', values=('No inspections found', '', '', '', '', '', ''))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load inspections: {str(e)}")
            # Show sample data on error for demo purposes
            tree.insert('', 'end', values=(f'Error: {str(e)}', '', '', '', '', '', ''))
            import traceback
            traceback.print_exc()

def edit_inspection(self, tree):
        """Edit an existing inspection"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an inspection to edit")
            return

        values = tree.item(selection[0], 'values')
        inspection_id = values[0]

        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Inspection")
        dialog.geometry("700x600")
        dialog.transient(self.root)

        ttk.Label(dialog, text=f"Edit Inspection {inspection_id}",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill='both', expand=True)

        # Get current data from database
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT i.room_id, r.room_number, i.inspection_date, i.inspection_type,
                   i.inspector, i.findings, i.status, i.action_required, i.follow_up_date
            FROM housing_inspections i
            JOIN housing_rooms r ON i.room_id = r.room_id
            WHERE i.inspection_id = ?
            ''', (inspection_id,))

            inspection_data = cursor.fetchone()
            conn.close()

            if not inspection_data:
                messagebox.showerror("Error", "Inspection not found")
                dialog.destroy()
                return

            # Room Number (read-only)
            ttk.Label(form_frame, text="Room Number:").grid(row=0, column=0, sticky='w', pady=5)
            ttk.Label(form_frame, text=inspection_data[1]).grid(row=0, column=1, sticky='w', pady=5, padx=5)

            # Date
            ttk.Label(form_frame, text="Inspection Date:").grid(row=1, column=0, sticky='w', pady=5)
            date_var = tk.StringVar(value=inspection_data[2])
            ttk.Entry(form_frame, textvariable=date_var, width=30).grid(row=1, column=1, pady=5, padx=5)

            # Type
            ttk.Label(form_frame, text="Inspection Type:").grid(row=2, column=0, sticky='w', pady=5)
            type_var = tk.StringVar(value=inspection_data[3])
            ttk.Combobox(form_frame, textvariable=type_var, width=28,
                        values=['Routine', 'Move-in', 'Move-out', 'Maintenance', 'Safety'],
                        state='readonly').grid(row=2, column=1, pady=5, padx=5)

            # Inspector
            ttk.Label(form_frame, text="Inspector:").grid(row=3, column=0, sticky='w', pady=5)
            inspector_var = tk.StringVar(value=inspection_data[4])
            ttk.Entry(form_frame, textvariable=inspector_var, width=30).grid(row=3, column=1, pady=5, padx=5)

            # Status
            ttk.Label(form_frame, text="Status:").grid(row=4, column=0, sticky='w', pady=5)
            status_var = tk.StringVar(value=inspection_data[6])
            ttk.Combobox(form_frame, textvariable=status_var, width=28,
                        values=['Scheduled', 'Completed', 'Issues Found', 'Follow-up Required'],
                        state='readonly').grid(row=4, column=1, pady=5, padx=5)

            # Findings
            ttk.Label(form_frame, text="Findings:").grid(row=5, column=0, sticky='nw', pady=5)
            findings_text = tk.Text(form_frame, height=4, width=30)
            findings_text.grid(row=5, column=1, pady=5, padx=5)
            if inspection_data[5]:
                findings_text.insert("1.0", inspection_data[5])

            # Action Required
            ttk.Label(form_frame, text="Action Required:").grid(row=6, column=0, sticky='nw', pady=5)
            action_text = tk.Text(form_frame, height=4, width=30)
            action_text.grid(row=6, column=1, pady=5, padx=5)
            if inspection_data[7]:
                action_text.insert("1.0", inspection_data[7])

            # Follow-up Date
            ttk.Label(form_frame, text="Follow-up Date:").grid(row=7, column=0, sticky='w', pady=5)
            followup_var = tk.StringVar(value=inspection_data[8] if inspection_data[8] else '')
            ttk.Entry(form_frame, textvariable=followup_var, width=30).grid(row=7, column=1, pady=5, padx=5)

            # Email notification checkbox
            ttk.Label(form_frame, text="Email Notification:").grid(row=8, column=0, sticky='w', pady=5)
            email_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(form_frame, text="Send email notification to student(s)",
                           variable=email_var).grid(row=8, column=1, sticky='w', pady=5, padx=5)

            def save_changes():
                try:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    findings = findings_text.get("1.0", tk.END).strip()
                    action = action_text.get("1.0", tk.END).strip()
                    followup = followup_var.get().strip() if followup_var.get().strip() else None
                    new_status = status_var.get()
                    old_status = inspection_data[6]  # Get the original status

                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                    UPDATE housing_inspections
                    SET inspection_date = ?, inspection_type = ?, inspector = ?,
                        findings = ?, status = ?, action_required = ?, follow_up_date = ?,
                        updated_at = ?
                    WHERE inspection_id = ?
                    ''', (date_var.get(), type_var.get(), inspector_var.get(),
                         findings, new_status, action, followup,
                         timestamp, inspection_id))

                    conn.commit()

                    # Send email notification if status changed and checkbox is checked
                    if email_var.get() and new_status != old_status and new_status in ['Completed', 'Issues Found']:
                        send_post_inspection_email(
                            self, cursor, inspection_data[0], inspection_id,
                            date_var.get(), type_var.get(), inspector_var.get(),
                            findings, new_status, action, followup
                        )

                    conn.close()

                    messagebox.showinfo("Success", "Inspection updated successfully!")
                    dialog.destroy()
                    load_inspections(self, tree)

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update inspection: {str(e)}")

            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load inspection data: {str(e)}")
            dialog.destroy()

def delete_inspection(self, tree):
        """Delete an inspection"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an inspection to delete")
            return

        values = tree.item(selection[0], 'values')
        inspection_id = values[0]
        room = values[1]

        result = messagebox.askyesno("Confirm Delete",
                                     f"Delete inspection {inspection_id} for room {room}?")
        if result:
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('DELETE FROM housing_inspections WHERE inspection_id = ?',
                             (inspection_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Inspection {inspection_id} deleted successfully")
                load_inspections(self, tree)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete inspection: {str(e)}")
