"""
Report management functions - generating housing reports and analytics.
Handles various housing reports including occupancy, financials, and maintenance.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity
from education_system.university_system.core.i18n import get_text as _t
from education_system.university_system.core import paths
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.modules.domain.campus.housing.gui.housing_accommodation_gui.export_manager import export_data_gui
from education_system.university_system.modules.domain.campus.housing.gui.housing_accommodation_gui.scheduled_reports import show_scheduled_reports_manager

def show_reports(self):
        """Show reports and analytics interface"""
        self.clear_content()

        ttk.Label(self.content_frame, text="Reports & Analytics",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Reports menu
        reports_frame = ttk.Frame(self.content_frame)
        reports_frame.pack(fill='both', expand=True)

        # Left side - report buttons
        buttons_frame = ttk.LabelFrame(reports_frame, text="Available Reports", padding="20")
        buttons_frame.pack(side='left', fill='y', padx=(0, 20))

        report_buttons = [
            ("Occupancy Report", lambda: show_occupancy_report(self)),
            ("Financial Summary", lambda: show_financial_summary(self)),
            ("Maintenance Summary", lambda: show_maintenance_summary_gui(self)),
            ("Room Availability", lambda: show_room_availability(self)),
            ("Export Data", lambda: show_export_options(self)),
            ("─" * 20, None),  # Separator
            ("Schedule Reports", lambda: show_scheduled_reports_manager(self)),
            ("Template Settings", lambda: show_report_template_settings(self))
        ]

        for text, command in report_buttons:
            if command is None:
                # Separator
                ttk.Separator(buttons_frame, orient='horizontal').pack(fill='x', pady=10)
            else:
                ttk.Button(buttons_frame, text=text, width=20,
                          command=command).pack(pady=5)

        # Right side - report display area
        self.report_display_frame = ttk.LabelFrame(reports_frame, text="Report Output", padding="20")
        self.report_display_frame.pack(side='right', fill='both', expand=True)

        ttk.Label(self.report_display_frame,
                 text="Select a report from the menu to view results here").pack()

def open_report_window(self, title, report_content, report_type='text'):
        """Open a report in a new window with export and send options"""
        # Create new window
        report_window = tk.Toplevel(self.root)
        report_window.title(title)
        report_window.geometry("900x700")

        # Main frame
        main_frame = ttk.Frame(report_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Title
        ttk.Label(main_frame, text=title, font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Report content area with scrollbar
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill='both', expand=True, pady=(0, 10))

        report_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD,
                                               width=80, height=30, font=('Courier', 10))
        report_text.pack(fill='both', expand=True)
        report_text.insert('1.0', report_content)
        report_text.config(state='disabled')

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        # Export buttons
        ttk.Label(button_frame, text="Export as:", font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 10))

        ttk.Button(button_frame, text="TXT", width=10,
                  command=lambda: export_report_as_txt(self, title, report_content, report_window)).pack(side='left', padx=5)

        ttk.Button(button_frame, text="CSV", width=10,
                  command=lambda: export_report_as_csv(self, title, report_content, report_window)).pack(side='left', padx=5)

        ttk.Button(button_frame, text="PDF", width=10,
                  command=lambda: export_report_as_pdf(self, title, report_content, report_window)).pack(side='left', padx=5)

        # Separator
        ttk.Separator(button_frame, orient='vertical').pack(side='left', fill='y', padx=15)

        # Send to admin button
        ttk.Button(button_frame, text="Send to Admin", width=15,
                  command=lambda: send_report_to_admin(self, title, report_content, report_window)).pack(side='left', padx=5)

        # Close button
        ttk.Button(button_frame, text="Close", width=10,
                  command=report_window.destroy).pack(side='right', padx=5)

def export_report_as_txt(self, title, content, parent_window):
        """Export report as TXT file"""
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            parent=parent_window,
            title="Save Report as TXT",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Report exported to:\n{filename}", parent=parent_window)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export report:\n{str(e)}", parent=parent_window)

def export_report_as_csv(self, title, content, parent_window):
        """Export report as CSV file"""
        import csv
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            parent=parent_window,
            title="Save Report as CSV",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )

        if filename:
            try:
                # Parse report content into CSV format
                lines = content.split('\n')

                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)

                    # Write header
                    writer.writerow([title])
                    writer.writerow([])  # Empty row

                    # Write content line by line
                    for line in lines:
                        writer.writerow([line])

                messagebox.showinfo("Success", f"Report exported to:\n{filename}", parent=parent_window)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export report:\n{str(e)}", parent=parent_window)

def export_report_as_pdf(self, title, content, parent_window):
        """Export report as PDF file"""
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            parent=parent_window,
            title="Save Report as PDF",
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )

        if filename:
            try:
                # Try to use reportlab if available
                try:
                    from reportlab.lib.pagesizes import letter
                    from reportlab.pdfgen import canvas
                    from reportlab.lib.units import inch

                    c = canvas.Canvas(filename, pagesize=letter)
                    width, height = letter

                    # Title
                    c.setFont("Helvetica-Bold", 16)
                    c.drawString(1*inch, height - 1*inch, title)

                    # Content
                    c.setFont("Courier", 9)
                    y_position = height - 1.5*inch
                    line_height = 12

                    lines = content.split('\n')
                    for line in lines:
                        if y_position < 1*inch:
                            c.showPage()
                            c.setFont("Courier", 9)
                            y_position = height - 1*inch

                        # Truncate long lines
                        if len(line) > 100:
                            line = line[:100] + "..."

                        c.drawString(0.5*inch, y_position, line)
                        y_position -= line_height

                    c.save()
                    messagebox.showinfo("Success", f"Report exported to:\n{filename}", parent=parent_window)

                except ImportError:
                    # Fallback: save as text with .pdf extension
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(f"{title}\n{'='*60}\n\n{content}")
                    messagebox.showwarning("Limited PDF Support",
                                         f"reportlab not available. Report saved as text file with .pdf extension.\n\n"
                                         f"Install reportlab for proper PDF support:\n"
                                         f"pip install reportlab\n\n"
                                         f"File saved to: {filename}",
                                         parent=parent_window)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export report:\n{str(e)}", parent=parent_window)

def send_report_to_admin(self, title, content, parent_window):
        """Send report to admin via email"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get admin email from database
            cursor.execute('''
                SELECT email, first_name, last_name
                FROM users
                WHERE (role = 'admin' OR role = 'staff')
                AND email IS NOT NULL
                AND email != ''
                ORDER BY
                    CASE
                        WHEN id = 1 THEN 1
                        WHEN role = 'admin' THEN 2
                        WHEN role = 'staff' THEN 3
                        ELSE 4
                    END
                LIMIT 1
            ''')

            admin = cursor.fetchone()

            if not admin:
                messagebox.showerror("Error",
                                   "No administrator email found in database.\n"
                                   "Please ensure an administrator account exists.",
                                   parent=parent_window)
                conn.close()
                return

            admin_email = admin[0]
            admin_name = f"{admin[1]} {admin[2]}"
            conn.close()

            # Get current user info
            sender_name = "Housing System"
            try:
                if self.auth and hasattr(self.auth, 'is_logged_in') and self.auth.current_user:
                    current_user = self.auth.get_current_user()
                    if current_user and 'first_name' in current_user and 'last_name' in current_user:
                        sender_name = f"{current_user['first_name']} {current_user['last_name']}"
            except Exception as e:
                # If auth fails, just use default sender name
                print(f"Warning: Could not get current user: {e}")
                pass

            # Prepare email
            from education_system.university_system.infrastructure.email.email_service import send_email

            # Format email using template
            email_subject, email_body = render_template('housing_report_admin', {
                'admin_name': admin_name,
                'title': title,
                'sender_name': sender_name,
                'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'content': content
            })

            # Send email
            success = send_email(
                recipient_email=admin_email,
                subject=email_subject,
                body=email_body
            )

            if success:
                messagebox.showinfo("Success",
                                  f"Report sent successfully to:\n{admin_name} ({admin_email})",
                                  parent=parent_window)
            else:
                messagebox.showerror("Error",
                                   "Failed to send email. Please check email configuration.",
                                   parent=parent_window)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send report to admin:\n{str(e)}", parent=parent_window)

def show_occupancy_report(self):
        """Show occupancy report in new window"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Generate report content
            report_content = "HOUSING OCCUPANCY REPORT\n"
            report_content += "=" * 50 + "\n\n"

            # Overall statistics
            cursor.execute('SELECT COUNT(*) FROM housing_buildings')
            total_buildings = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_rooms')
            total_rooms = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE status = "Occupied"')
            occupied_rooms = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE status = "Available"')
            available_rooms = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_assignments WHERE status = "Active"')
            active_assignments = cursor.fetchone()[0]

            occupancy_rate = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0

            report_content += f"Total Buildings: {total_buildings}\n"
            report_content += f"Total Rooms: {total_rooms}\n"
            report_content += f"Occupied Rooms: {occupied_rooms}\n"
            report_content += f"Available Rooms: {available_rooms}\n"
            report_content += f"Active Assignments: {active_assignments}\n"
            report_content += f"Occupancy Rate: {occupancy_rate:.1f}%\n\n"

            # Building breakdown
            report_content += "BUILDING BREAKDOWN:\n"
            report_content += "-" * 80 + "\n"
            report_content += f"{'Building':<25} {'Total':<8} {'Occupied':<10} {'Available':<10} {'Rate':<8}\n"
            report_content += "-" * 80 + "\n"

            cursor.execute('''
            SELECT b.building_name, b.total_rooms, b.available_rooms,
                   (b.total_rooms - b.available_rooms) as occupied_rooms,
                   ROUND((CAST(b.total_rooms - b.available_rooms AS FLOAT) / b.total_rooms) * 100, 1) as occupancy_rate
            FROM housing_buildings b
            ORDER BY b.building_name
            ''')

            buildings = cursor.fetchall()

            for building in buildings:
                report_content += f"{building[0]:<25} {building[1]:<8} {building[3]:<10} {building[2]:<10} {building[4]:.1f}%\n"

            # Room type breakdown
            report_content += "\n\nROOM TYPE DISTRIBUTION:\n"
            report_content += "-" * 50 + "\n"
            report_content += f"{'Type':<12} {'Total':<8} {'Occupied':<10} {'Available':<10}\n"
            report_content += "-" * 50 + "\n"

            cursor.execute('''
            SELECT room_type, COUNT(*) as total,
                   SUM(CASE WHEN status = 'Occupied' THEN 1 ELSE 0 END) as occupied,
                   SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END) as available
            FROM housing_rooms
            GROUP BY room_type
            ORDER BY room_type
            ''')

            room_types = cursor.fetchall()

            for room_type in room_types:
                report_content += f"{room_type[0]:<12} {room_type[1]:<8} {room_type[2]:<10} {room_type[3]:<10}\n"

            conn.close()

            # Open report in new window
            open_report_window(self,"Housing Occupancy Report", report_content)

        except Exception as e:
            messagebox.showerror("Error", f"Error generating report: {str(e)}")

def show_financial_summary(self):
        """Show financial summary in new window"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            report_content = "HOUSING FINANCIAL SUMMARY\n"
            report_content += "=" * 50 + "\n\n"

            # Monthly revenue calculation
            cursor.execute('''
            SELECT SUM(monthly_rent) as monthly_revenue
            FROM housing_assignments
            WHERE status = 'Active'
            ''')

            monthly_revenue = cursor.fetchone()[0] or 0

            report_content += f"Current Monthly Revenue: £{monthly_revenue:,.2f}\n"
            report_content += f"Projected Annual Revenue: £{monthly_revenue * 12:,.2f}\n\n"

            # Payment statistics for current year
            current_year = datetime.now().year

            cursor.execute('''
            SELECT COUNT(*) as payment_count, SUM(amount) as total_amount
            FROM payments
            WHERE source_type = 'housing' AND strftime('%Y', payment_date) = ?
            ''', (str(current_year),))

            year_stats = cursor.fetchone()
            payment_count = year_stats[0] or 0
            total_collected = year_stats[1] or 0

            report_content += f"Payments Collected This Year ({current_year}):\n"
            report_content += f"Number of Payments: {payment_count}\n"
            report_content += f"Total Amount Collected: £{total_collected:,.2f}\n\n"

            # Revenue by building
            cursor.execute('''
            SELECT b.building_name, COUNT(a.assignment_id) as active_assignments,
                   SUM(a.monthly_rent) as monthly_revenue
            FROM housing_buildings b
            LEFT JOIN housing_rooms r ON b.building_id = r.building_id
            LEFT JOIN housing_assignments a ON r.room_id = a.room_id AND a.status = 'Active'
            GROUP BY b.building_id, b.building_name
            ORDER BY monthly_revenue DESC
            ''')

            building_revenue = cursor.fetchall()

            report_content += "REVENUE BY BUILDING:\n"
            report_content += "-" * 60 + "\n"
            report_content += f"{'Building':<25} {'Assignments':<12} {'Monthly Revenue':<15}\n"
            report_content += "-" * 60 + "\n"

            for building in building_revenue:
                assignments = building[1] or 0
                revenue = building[2] or 0
                report_content += f"{building[0]:<25} {assignments:<12} £{revenue:,.2f}\n"

            conn.close()

            # Open report in new window
            open_report_window(self,"Housing Financial Summary", report_content)

        except Exception as e:
            messagebox.showerror("Error", f"Error generating report: {str(e)}")

def show_maintenance_summary_gui(self):
        """Show maintenance summary in new window"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            report_content = "MAINTENANCE REQUESTS SUMMARY\n"
            report_content += "=" * 40 + "\n\n"

            # Overall statistics
            cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests')
            total_requests = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status = "Open"')
            open_requests = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status = "In Progress"')
            in_progress = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status = "Complete"')
            completed = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE priority = "Emergency"')
            emergency_requests = cursor.fetchone()[0]

            report_content += f"Total Requests: {total_requests}\n"
            report_content += f"Open Requests: {open_requests}\n"
            report_content += f"In Progress: {in_progress}\n"
            report_content += f"Completed: {completed}\n"
            report_content += f"Emergency Priority: {emergency_requests}\n\n"

            # Requests by status
            cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM housing_maintenance_requests
            GROUP BY status
            ORDER BY
                CASE status
                    WHEN 'Open' THEN 1
                    WHEN 'In Progress' THEN 2
                    WHEN 'Pending Parts' THEN 3
                    WHEN 'Complete' THEN 4
                    ELSE 5
                END
            ''')

            status_breakdown = cursor.fetchall()

            report_content += "REQUESTS BY STATUS:\n"
            report_content += "-" * 25 + "\n"
            for status, count in status_breakdown:
                report_content += f"{status}: {count}\n"
            report_content += "\n"

            # Requests by priority
            cursor.execute('''
            SELECT priority, COUNT(*) as count
            FROM housing_maintenance_requests
            GROUP BY priority
            ORDER BY
                CASE priority
                    WHEN 'Emergency' THEN 1
                    WHEN 'High' THEN 2
                    WHEN 'Medium' THEN 3
                    WHEN 'Low' THEN 4
                    ELSE 5
                END
            ''')

            priority_breakdown = cursor.fetchall()

            report_content += "REQUESTS BY PRIORITY:\n"
            report_content += "-" * 25 + "\n"
            for priority, count in priority_breakdown:
                report_content += f"{priority}: {count}\n"
            report_content += "\n"

            # Outstanding emergency requests
            cursor.execute('''
            SELECT COUNT(*) FROM housing_maintenance_requests
            WHERE priority = 'Emergency' AND status != 'Complete'
            ''')

            outstanding_emergency = cursor.fetchone()[0]

            if outstanding_emergency > 0:
                report_content += f"⚠️ URGENT: {outstanding_emergency} outstanding emergency request(s)\n"

            conn.close()

            # Open report in new window
            open_report_window(self,"Maintenance Requests Summary", report_content)

        except Exception as e:
            messagebox.showerror("Error", f"Error generating report: {str(e)}")

def show_room_availability(self):
        """Show room availability report in new window"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            report_content = "ROOM AVAILABILITY REPORT\n"
            report_content += "=" * 35 + "\n\n"

            # All available rooms
            cursor.execute('''
            SELECT r.room_number, b.building_name, r.floor_number, r.room_type,
                   r.max_occupants, r.monthly_rent, r.is_accessible
            FROM housing_rooms r
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE r.status = 'Available'
            ORDER BY b.building_name, r.floor_number, r.room_number
            ''')

            available_rooms = cursor.fetchall()

            report_content += f"AVAILABLE ROOMS ({len(available_rooms)} total):\n"
            report_content += "-" * 90 + "\n"
            report_content += f"{'Room':<8} {'Building':<20} {'Floor':<8} {'Type':<12} {'Max Occ.':<10} {'Rent':<10} {'Accessible':<12}\n"
            report_content += "-" * 90 + "\n"

            for room in available_rooms:
                accessible = "Yes" if room[6] else "No"
                report_content += f"{room[0]:<8} {room[1]:<20} {room[2]:<8} {room[3]:<12} {room[4]:<10} £{room[5]:<9.2f} {accessible:<12}\n"

            # Summary by type
            cursor.execute('''
            SELECT room_type, COUNT(*) as count
            FROM housing_rooms
            WHERE status = 'Available'
            GROUP BY room_type
            ORDER BY room_type
            ''')

            type_summary = cursor.fetchall()

            report_content += "\n\nAVAILABILITY SUMMARY BY TYPE:\n"
            report_content += "-" * 30 + "\n"
            for room_type, count in type_summary:
                report_content += f"{room_type}: {count} rooms\n"

            conn.close()

            # Open report in new window
            open_report_window(self,"Room Availability Report", report_content)

        except Exception as e:
            messagebox.showerror("Error", f"Error generating report: {str(e)}")

def show_export_options(self):
        """Show data export options"""
        for widget in self.report_display_frame.winfo_children():
            widget.destroy()

        ttk.Label(self.report_display_frame, text="Data Export Options",
                 font=('Arial', 14, 'bold')).pack(pady=20)

        export_buttons = [
            ("Export Building Data", lambda: export_data_gui(self,'buildings')),
            ("Export Room Data", lambda: export_data_gui(self,'rooms')),
            ("Export Assignment Data", lambda: export_data_gui(self,'assignments')),
            ("Export Application Data", lambda: export_data_gui(self,'applications')),
            ("Export Payment Data", lambda: export_data_gui(self,'payments')),
            ("Export Maintenance Requests", lambda: export_data_gui(self,'maintenance'))
        ]

        for text, command in export_buttons:
            ttk.Button(self.report_display_frame, text=text, width=25,
                      command=command).pack(pady=5)

def show_report_template_settings(self):
        """Show report template customization settings"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Report Template Settings")
        settings_window.geometry("700x650")

        main_frame = ttk.Frame(settings_window, padding="20")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Report Template Settings",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Load current settings or create defaults
        template_file = paths.DATA_DIR / "report_templates.json"
        default_settings = {
            'title_font': 'Arial',
            'title_size': 16,
            'content_font': 'Courier',
            'content_size': 10,
            'line_spacing': 1.2,
            'page_width': 80,
            'include_timestamp': True,
            'include_generator_name': True,
            'section_separator': '=',
            'subsection_separator': '-',
            'currency_symbol': '£',
            'date_format': '%Y-%m-%d',
            'header_text': 'Housing Management Report',
            'footer_text': 'Generated by University Housing System'
        }

        try:
            import json
            import os
            if os.path.exists(template_file):
                with open(template_file, 'r') as f:
                    current_settings = json.load(f)
            else:
                current_settings = default_settings.copy()
        except (OSError, IOError, ValueError, json.JSONDecodeError):
            current_settings = default_settings.copy()

        # Create form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True)

        # Title Font
        ttk.Label(form_frame, text="Title Font:").grid(row=0, column=0, sticky='w', pady=5)
        title_font_var = tk.StringVar(value=current_settings.get('title_font', 'Arial'))
        ttk.Combobox(form_frame, textvariable=title_font_var, width=30,
                    values=['Arial', 'Helvetica', 'Times New Roman', 'Courier', 'Verdana'],
                    state='readonly').grid(row=0, column=1, pady=5, padx=5, sticky='w')

        # Title Size
        ttk.Label(form_frame, text="Title Size:").grid(row=1, column=0, sticky='w', pady=5)
        title_size_var = tk.IntVar(value=current_settings.get('title_size', 16))
        ttk.Spinbox(form_frame, from_=10, to=24, textvariable=title_size_var, width=10).grid(row=1, column=1, pady=5, padx=5, sticky='w')

        # Content Font
        ttk.Label(form_frame, text="Content Font:").grid(row=2, column=0, sticky='w', pady=5)
        content_font_var = tk.StringVar(value=current_settings.get('content_font', 'Courier'))
        ttk.Combobox(form_frame, textvariable=content_font_var, width=30,
                    values=['Arial', 'Helvetica', 'Times New Roman', 'Courier', 'Verdana'],
                    state='readonly').grid(row=2, column=1, pady=5, padx=5, sticky='w')

        # Content Size
        ttk.Label(form_frame, text="Content Size:").grid(row=3, column=0, sticky='w', pady=5)
        content_size_var = tk.IntVar(value=current_settings.get('content_size', 10))
        ttk.Spinbox(form_frame, from_=8, to=14, textvariable=content_size_var, width=10).grid(row=3, column=1, pady=5, padx=5, sticky='w')

        # Line Spacing
        ttk.Label(form_frame, text="Line Spacing:").grid(row=4, column=0, sticky='w', pady=5)
        line_spacing_var = tk.DoubleVar(value=current_settings.get('line_spacing', 1.2))
        ttk.Spinbox(form_frame, from_=1.0, to=2.0, increment=0.1, textvariable=line_spacing_var, width=10).grid(row=4, column=1, pady=5, padx=5, sticky='w')

        # Page Width
        ttk.Label(form_frame, text="Page Width (chars):").grid(row=5, column=0, sticky='w', pady=5)
        page_width_var = tk.IntVar(value=current_settings.get('page_width', 80))
        ttk.Spinbox(form_frame, from_=60, to=120, textvariable=page_width_var, width=10).grid(row=5, column=1, pady=5, padx=5, sticky='w')

        # Section Separator
        ttk.Label(form_frame, text="Section Separator:").grid(row=6, column=0, sticky='w', pady=5)
        section_sep_var = tk.StringVar(value=current_settings.get('section_separator', '='))
        ttk.Combobox(form_frame, textvariable=section_sep_var, width=30,
                    values=['=', '-', '#', '*', '_', '~'],
                    state='readonly').grid(row=6, column=1, pady=5, padx=5, sticky='w')

        # Subsection Separator
        ttk.Label(form_frame, text="Subsection Separator:").grid(row=7, column=0, sticky='w', pady=5)
        subsection_sep_var = tk.StringVar(value=current_settings.get('subsection_separator', '-'))
        ttk.Combobox(form_frame, textvariable=subsection_sep_var, width=30,
                    values=['=', '-', '#', '*', '_', '~'],
                    state='readonly').grid(row=7, column=1, pady=5, padx=5, sticky='w')

        # Currency Symbol
        ttk.Label(form_frame, text="Currency Symbol:").grid(row=8, column=0, sticky='w', pady=5)
        currency_var = tk.StringVar(value=current_settings.get('currency_symbol', '£'))
        ttk.Entry(form_frame, textvariable=currency_var, width=10).grid(row=8, column=1, pady=5, padx=5, sticky='w')

        # Date Format
        ttk.Label(form_frame, text="Date Format:").grid(row=9, column=0, sticky='w', pady=5)
        date_format_var = tk.StringVar(value=current_settings.get('date_format', '%Y-%m-%d'))
        ttk.Combobox(form_frame, textvariable=date_format_var, width=30,
                    values=['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%B %d, %Y'],
                    state='readonly').grid(row=9, column=1, pady=5, padx=5, sticky='w')

        # Include Timestamp
        include_timestamp_var = tk.BooleanVar(value=current_settings.get('include_timestamp', True))
        ttk.Checkbutton(form_frame, text="Include Timestamp", variable=include_timestamp_var).grid(row=10, column=1, sticky='w', pady=5)

        # Include Generator Name
        include_generator_var = tk.BooleanVar(value=current_settings.get('include_generator_name', True))
        ttk.Checkbutton(form_frame, text="Include Generator Name", variable=include_generator_var).grid(row=11, column=1, sticky='w', pady=5)

        # Header Text
        ttk.Label(form_frame, text="Header Text:").grid(row=12, column=0, sticky='w', pady=5)
        header_var = tk.StringVar(value=current_settings.get('header_text', 'Housing Management Report'))
        ttk.Entry(form_frame, textvariable=header_var, width=40).grid(row=12, column=1, pady=5, padx=5, sticky='w')

        # Footer Text
        ttk.Label(form_frame, text="Footer Text:").grid(row=13, column=0, sticky='w', pady=5)
        footer_var = tk.StringVar(value=current_settings.get('footer_text', 'Generated by University Housing System'))
        ttk.Entry(form_frame, textvariable=footer_var, width=40).grid(row=13, column=1, pady=5, padx=5, sticky='w')

        def save_settings():
            try:
                new_settings = {
                    'title_font': title_font_var.get(),
                    'title_size': title_size_var.get(),
                    'content_font': content_font_var.get(),
                    'content_size': content_size_var.get(),
                    'line_spacing': line_spacing_var.get(),
                    'page_width': page_width_var.get(),
                    'include_timestamp': include_timestamp_var.get(),
                    'include_generator_name': include_generator_var.get(),
                    'section_separator': section_sep_var.get(),
                    'subsection_separator': subsection_sep_var.get(),
                    'currency_symbol': currency_var.get(),
                    'date_format': date_format_var.get(),
                    'header_text': header_var.get(),
                    'footer_text': footer_var.get()
                }

                import json
                import os
                os.makedirs(os.path.dirname(template_file), exist_ok=True)
                with open(template_file, 'w') as f:
                    json.dump(new_settings, f, indent=4)

                messagebox.showinfo("Success", "Report template settings saved successfully!", parent=settings_window)
                settings_window.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to save settings: {str(e)}", parent=settings_window)

        def reset_to_defaults():
            result = messagebox.askyesno("Reset to Defaults",
                                         "Reset all template settings to default values?",
                                         parent=settings_window)
            if result:
                try:
                    import json
                    with open(template_file, 'w') as f:
                        json.dump(default_settings, f, indent=4)

                    messagebox.showinfo("Success", "Settings reset to defaults. Please reopen this window to see changes.",
                                      parent=settings_window)
                    settings_window.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to reset settings: {str(e)}", parent=settings_window)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Save Settings", width=15, command=save_settings).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Reset to Defaults", width=18, command=reset_to_defaults).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", width=15, command=settings_window.destroy).pack(side='left', padx=5)

        # Preview section
        preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding="10")
        preview_frame.pack(fill='x', pady=(10, 0))

        preview_text = f"""Font: {content_font_var.get()} {content_size_var.get()}pt
Header: {header_var.get()}
Section Sep: {section_sep_var.get() * 20}
Currency: {currency_var.get()}1,234.56
Footer: {footer_var.get()}"""

        ttk.Label(preview_frame, text=preview_text, font=(current_settings.get('content_font', 'Courier'), 9)).pack()

def get_report_template_settings(self):
        """Load report template settings from file"""
        template_file = paths.DATA_DIR / "report_templates.json"
        default_settings = {
            'title_font': 'Arial',
            'title_size': 16,
            'content_font': 'Courier',
            'content_size': 10,
            'line_spacing': 1.2,
            'page_width': 80,
            'include_timestamp': True,
            'include_generator_name': True,
            'section_separator': '=',
            'subsection_separator': '-',
            'currency_symbol': '£',
            'date_format': '%Y-%m-%d',
            'header_text': 'Housing Management Report',
            'footer_text': 'Generated by University Housing System'
        }

        try:
            import json
            import os
            if os.path.exists(template_file):
                with open(template_file, 'r') as f:
                    return json.load(f)
        except (OSError, IOError, ValueError, json.JSONDecodeError):
            pass

        return default_settings

