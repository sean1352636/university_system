"""
Scheduled reports functions - automated report generation and distribution.
Handles scheduled report generation, email distribution, and report archiving.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity
from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.modules.domain.housing.services.housing_accommodation import generate_id

def show_scheduled_reports_manager(self):
        """Show scheduled reports management window"""
        # Create window
        manager_window = tk.Toplevel(self.root)
        manager_window.title("Scheduled Reports Manager")
        manager_window.geometry("1000x600")

        # Main frame
        main_frame = ttk.Frame(manager_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Title
        ttk.Label(main_frame, text="Scheduled Reports Manager",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(0, 10))

        ttk.Button(button_frame, text="Add Schedule", width=15,
                  command=lambda: add_scheduled_report(self, manager_window, tree)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Edit Schedule", width=15,
                  command=lambda: edit_scheduled_report(self, tree, manager_window)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Delete Schedule", width=15,
                  command=lambda: delete_scheduled_report(self, tree)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Run Now", width=15,
                  command=lambda: run_scheduled_report_now(self, tree)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Refresh", width=15,
                  command=lambda: load_scheduled_reports(self, tree)).pack(side='left', padx=5)

        # Tree view for scheduled reports
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True)

        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side='right', fill='y')

        tree = ttk.Treeview(tree_frame, yscrollcommand=scrollbar.set,
                           columns=('ID', 'Name', 'Type', 'Frequency', 'Recipients', 'Last Run', 'Next Run', 'Status'),
                           show='headings', height=15)

        tree.heading('ID', text='ID')
        tree.heading('Name', text='Report Name')
        tree.heading('Type', text='Report Type')
        tree.heading('Frequency', text='Frequency')
        tree.heading('Recipients', text='Recipients')
        tree.heading('Last Run', text='Last Run')
        tree.heading('Next Run', text='Next Run')
        tree.heading('Status', text='Status')

        tree.column('ID', width=50)
        tree.column('Name', width=150)
        tree.column('Type', width=120)
        tree.column('Frequency', width=100)
        tree.column('Recipients', width=200)
        tree.column('Last Run', width=100)
        tree.column('Next Run', width=100)
        tree.column('Status', width=80)

        tree.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=tree.yview)

        # Load data
        load_scheduled_reports(self, tree)

        # Close button
        ttk.Button(main_frame, text="Close", command=manager_window.destroy).pack(pady=(10, 0))

def load_scheduled_reports(self, tree):
        """Load scheduled reports into tree view"""
        for item in tree.get_children():
            tree.delete(item)

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT report_id, report_name, report_type, schedule_frequency,
                       recipients, last_run_date, next_run_date, is_active
                FROM scheduled_reports
                ORDER BY report_id DESC
            ''')

            reports = cursor.fetchall()
            conn.close()

            for report in reports:
                status = "Active" if report[7] else "Inactive"
                values = (
                    report[0],  # ID
                    report[1],  # Name
                    report[2],  # Type
                    report[3],  # Frequency
                    report[4],  # Recipients
                    report[5] if report[5] else 'Never',  # Last Run
                    report[6] if report[6] else 'Not Set',  # Next Run
                    status
                )
                tree.insert('', 'end', values=values)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load scheduled reports: {str(e)}")

def add_scheduled_report(self, parent_window, tree):
        """Add a new scheduled report"""
        dialog = tk.Toplevel(parent_window)
        dialog.title("Add Scheduled Report")
        dialog.geometry("600x550")
        dialog.transient(parent_window)

        ttk.Label(dialog, text="Add Scheduled Report",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill='both', expand=True)

        # Report Name
        ttk.Label(form_frame, text="Report Name:").grid(row=0, column=0, sticky='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, width=40).grid(row=0, column=1, pady=5, padx=5)

        # Report Type
        ttk.Label(form_frame, text="Report Type:").grid(row=1, column=0, sticky='w', pady=5)
        type_var = tk.StringVar(value="Occupancy Report")
        ttk.Combobox(form_frame, textvariable=type_var, width=38,
                    values=['Occupancy Report', 'Financial Summary', 'Maintenance Summary', 'Room Availability'],
                    state='readonly').grid(row=1, column=1, pady=5, padx=5)

        # Frequency
        ttk.Label(form_frame, text="Frequency:").grid(row=2, column=0, sticky='w', pady=5)
        frequency_var = tk.StringVar(value="Weekly")
        ttk.Combobox(form_frame, textvariable=frequency_var, width=38,
                    values=['Daily', 'Weekly', 'Monthly', 'Quarterly'],
                    state='readonly').grid(row=2, column=1, pady=5, padx=5)

        # Recipients
        ttk.Label(form_frame, text="Recipients:").grid(row=3, column=0, sticky='nw', pady=5)
        ttk.Label(form_frame, text="(comma-separated emails)", font=('TkDefaultFont', 8)).grid(row=4, column=0, sticky='w')
        recipients_text = tk.Text(form_frame, height=4, width=40)
        recipients_text.grid(row=3, column=1, rowspan=2, pady=5, padx=5)

        # Active
        active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Active", variable=active_var).grid(row=5, column=1, sticky='w', pady=5)

        # Description
        ttk.Label(form_frame, text="Description:").grid(row=6, column=0, sticky='nw', pady=5)
        desc_text = tk.Text(form_frame, height=4, width=40)
        desc_text.grid(row=6, column=1, pady=5, padx=5)

        def save_schedule():
            if not name_var.get().strip():
                messagebox.showwarning("Missing Info", "Please enter a report name", parent=dialog)
                return

            recipients = recipients_text.get("1.0", tk.END).strip()
            if not recipients:
                messagebox.showwarning("Missing Info", "Please enter at least one recipient email", parent=dialog)
                return

            try:
                # Calculate next run date based on frequency
                from datetime import datetime, timedelta
                now = datetime.now()
                frequency = frequency_var.get()

                if frequency == 'Daily':
                    next_run = (now + timedelta(days=1)).strftime('%Y-%m-%d 08:00:00')
                elif frequency == 'Weekly':
                    next_run = (now + timedelta(weeks=1)).strftime('%Y-%m-%d 08:00:00')
                elif frequency == 'Monthly':
                    next_run = (now + timedelta(days=30)).strftime('%Y-%m-%d 08:00:00')
                else:  # Quarterly
                    next_run = (now + timedelta(days=90)).strftime('%Y-%m-%d 08:00:00')

                config = {
                    'description': desc_text.get("1.0", tk.END).strip()
                }

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO scheduled_reports
                    (report_name, report_type, schedule_frequency, recipients, next_run_date, is_active, report_config)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (name_var.get().strip(), type_var.get(), frequency_var.get(),
                     recipients, next_run, int(active_var.get()), str(config)))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Scheduled report added successfully!", parent=dialog)
                dialog.destroy()
                load_scheduled_reports(self, tree)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add scheduled report: {str(e)}", parent=dialog)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Save", command=save_schedule).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

def edit_scheduled_report(self, tree, parent_window):
        """Edit an existing scheduled report"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a scheduled report to edit", parent=parent_window)
            return

        report_id = tree.item(selection[0], 'values')[0]

        # Fetch existing report data
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT report_name, report_type, schedule_frequency, recipients,
                       is_active, report_config
                FROM scheduled_reports
                WHERE report_id = ?
            ''', (report_id,))

            report = cursor.fetchone()
            conn.close()

            if not report:
                messagebox.showerror("Error", "Report not found", parent=parent_window)
                return

            report_name, report_type, frequency, recipients, is_active, report_config = report

            # Parse config for description
            description = ''
            if report_config:
                try:
                    import ast
                    config_dict = ast.literal_eval(report_config) if isinstance(report_config, str) else report_config
                    description = config_dict.get('description', '')
                except (ValueError, SyntaxError):
                    description = ''

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load report: {str(e)}", parent=parent_window)
            return

        # Create edit dialog
        dialog = tk.Toplevel(parent_window)
        dialog.title(f"Edit Scheduled Report - ID: {report_id}")
        dialog.geometry("600x550")
        dialog.transient(parent_window)
        dialog.grab_set()

        ttk.Label(dialog, text="Edit Scheduled Report",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill='both', expand=True)

        # Report Name
        ttk.Label(form_frame, text="Report Name:").grid(row=0, column=0, sticky='w', pady=5)
        name_var = tk.StringVar(value=report_name)
        ttk.Entry(form_frame, textvariable=name_var, width=40).grid(row=0, column=1, pady=5, padx=5)

        # Report Type
        ttk.Label(form_frame, text="Report Type:").grid(row=1, column=0, sticky='w', pady=5)
        type_var = tk.StringVar(value=report_type)
        ttk.Combobox(form_frame, textvariable=type_var, width=38,
                    values=['Occupancy Report', 'Financial Summary', 'Maintenance Summary', 'Room Availability'],
                    state='readonly').grid(row=1, column=1, pady=5, padx=5)

        # Frequency
        ttk.Label(form_frame, text="Frequency:").grid(row=2, column=0, sticky='w', pady=5)
        frequency_var = tk.StringVar(value=frequency)
        ttk.Combobox(form_frame, textvariable=frequency_var, width=38,
                    values=['Daily', 'Weekly', 'Monthly', 'Quarterly'],
                    state='readonly').grid(row=2, column=1, pady=5, padx=5)

        # Recipients
        ttk.Label(form_frame, text="Recipients:").grid(row=3, column=0, sticky='nw', pady=5)
        ttk.Label(form_frame, text="(comma-separated emails)", font=('TkDefaultFont', 8)).grid(row=4, column=0, sticky='w')
        recipients_text = tk.Text(form_frame, height=4, width=40)
        recipients_text.insert('1.0', recipients or '')
        recipients_text.grid(row=3, column=1, rowspan=2, pady=5, padx=5)

        # Active
        active_var = tk.BooleanVar(value=bool(is_active))
        ttk.Checkbutton(form_frame, text="Active", variable=active_var).grid(row=5, column=1, sticky='w', pady=5)

        # Description
        ttk.Label(form_frame, text="Description:").grid(row=6, column=0, sticky='nw', pady=5)
        desc_text = tk.Text(form_frame, height=4, width=40)
        desc_text.insert('1.0', description)
        desc_text.grid(row=6, column=1, pady=5, padx=5)

        def save_changes():
            if not name_var.get().strip():
                messagebox.showwarning("Missing Info", "Please enter a report name", parent=dialog)
                return

            new_recipients = recipients_text.get("1.0", tk.END).strip()
            if not new_recipients:
                messagebox.showwarning("Missing Info", "Please enter at least one recipient email", parent=dialog)
                return

            try:
                # Calculate next run date based on frequency
                from datetime import datetime, timedelta
                now = datetime.now()
                new_frequency = frequency_var.get()

                if new_frequency == 'Daily':
                    next_run = (now + timedelta(days=1)).strftime('%Y-%m-%d 08:00:00')
                elif new_frequency == 'Weekly':
                    next_run = (now + timedelta(weeks=1)).strftime('%Y-%m-%d 08:00:00')
                elif new_frequency == 'Monthly':
                    next_run = (now + timedelta(days=30)).strftime('%Y-%m-%d 08:00:00')
                else:  # Quarterly
                    next_run = (now + timedelta(days=90)).strftime('%Y-%m-%d 08:00:00')

                config = {
                    'description': desc_text.get("1.0", tk.END).strip()
                }

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE scheduled_reports
                    SET report_name = ?, report_type = ?, schedule_frequency = ?,
                        recipients = ?, next_run_date = ?, is_active = ?, report_config = ?
                    WHERE report_id = ?
                ''', (name_var.get().strip(), type_var.get(), new_frequency,
                     new_recipients, next_run, int(active_var.get()), str(config), report_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Scheduled report updated successfully!", parent=dialog)
                dialog.destroy()
                load_scheduled_reports(self, tree)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update scheduled report: {str(e)}", parent=dialog)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

def delete_scheduled_report(self, tree):
        """Delete a scheduled report"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a scheduled report to delete")
            return

        values = tree.item(selection[0], 'values')
        report_id = values[0]
        report_name = values[1]

        result = messagebox.askyesno("Confirm Delete",
                                     f"Delete scheduled report '{report_name}'?\n\nThis will stop all future report generation and emails.")
        if result:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM scheduled_reports WHERE report_id = ?', (report_id,))
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Scheduled report '{report_name}' deleted successfully")
                load_scheduled_reports(self, tree)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete scheduled report: {str(e)}")

def run_scheduled_report_now(self, tree):
        """Run a scheduled report immediately"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a scheduled report to run")
            return

        values = tree.item(selection[0], 'values')
        report_id = values[0]
        report_name = values[1]
        report_type = values[2]
        recipients = values[4]

        result = messagebox.askyesno("Confirm Run",
                                     f"Run '{report_name}' now and email to:\n{recipients}?")
        if result:
            try:
                # Generate report content based on type
                if report_type == 'Occupancy Report':
                    report_content = generate_occupancy_report_content(self)
                elif report_type == 'Financial Summary':
                    report_content = generate_financial_report_content(self)
                elif report_type == 'Maintenance Summary':
                    report_content = generate_maintenance_report_content(self)
                elif report_type == 'Room Availability':
                    report_content = generate_room_availability_content(self)
                else:
                    messagebox.showerror("Error", "Unknown report type")
                    return

                # Send email to recipients
                from education_system.university_system.infrastructure.email.email_service import send_email

                recipient_list = [email.strip() for email in recipients.split(',')]

                for recipient in recipient_list:
                    if recipient:
                        success = send_email(
                            recipient_email=recipient,
                            subject=f"Housing Report: {report_name}",
                            body=f"Automated Housing Report\n\n{report_content}"
                        )

                # Update last run date
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE scheduled_reports
                    SET last_run_date = datetime('now')
                    WHERE report_id = ?
                ''', (report_id,))
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Report '{report_name}' generated and emailed successfully!")
                load_scheduled_reports(self, tree)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to run report: {str(e)}")

def generate_occupancy_report_content(self):
        """Generate occupancy report content (returns string)"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            report_content = "HOUSING OCCUPANCY REPORT\n"
            report_content += "=" * 50 + "\n\n"

            cursor.execute('SELECT COUNT(*) FROM housing_buildings')
            total_buildings = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_rooms')
            total_rooms = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE status = "Occupied"')
            occupied_rooms = cursor.fetchone()[0]

            occupancy_rate = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0

            report_content += f"Total Buildings: {total_buildings}\n"
            report_content += f"Total Rooms: {total_rooms}\n"
            report_content += f"Occupied Rooms: {occupied_rooms}\n"
            report_content += f"Occupancy Rate: {occupancy_rate:.1f}%\n"

            conn.close()
            return report_content

        except Exception as e:
            return f"Error generating report: {str(e)}"

def generate_financial_report_content(self):
        """Generate financial report content (returns string)"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            report_content = "HOUSING FINANCIAL SUMMARY\n"
            report_content += "=" * 50 + "\n\n"

            cursor.execute('SELECT SUM(monthly_rent) FROM housing_assignments WHERE status = "Active"')
            monthly_revenue = cursor.fetchone()[0] or 0

            report_content += f"Current Monthly Revenue: £{monthly_revenue:,.2f}\n"
            report_content += f"Projected Annual Revenue: £{monthly_revenue * 12:,.2f}\n"

            conn.close()
            return report_content

        except Exception as e:
            return f"Error generating report: {str(e)}"

def generate_maintenance_report_content(self):
        """Generate maintenance report content (returns string)"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            report_content = "MAINTENANCE REQUESTS SUMMARY\n"
            report_content += "=" * 40 + "\n\n"

            cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests')
            total_requests = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status = "Open"')
            open_requests = cursor.fetchone()[0]

            report_content += f"Total Requests: {total_requests}\n"
            report_content += f"Open Requests: {open_requests}\n"

            conn.close()
            return report_content

        except Exception as e:
            return f"Error generating report: {str(e)}"

def generate_room_availability_content(self):
        """Generate room availability report content (returns string)"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            report_content = "ROOM AVAILABILITY REPORT\n"
            report_content += "=" * 35 + "\n\n"

            cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE status = "Available"')
            available_rooms = cursor.fetchone()[0]

            report_content += f"Available Rooms: {available_rooms}\n"

            conn.close()
            return report_content

        except Exception as e:
            return f"Error generating report: {str(e)}"
