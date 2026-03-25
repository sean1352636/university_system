from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.academics.services.module_scheduling.constants import DAYS_OF_WEEK, TIME_SLOTS
from datetime import datetime, timedelta
import os
import csv
import pandas as pd
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch


class TimetablesMixin:
    def generate_student_timetable(self, student_id, output_format='display'):
        """Generate a timetable for a specific student"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Check if student exists
        cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        student = cursor.fetchone()

        if not student:
            print(f"Student ID {student_id} does not exist.")
            conn.close()
            return

        # Get modules the student is enrolled in
        cursor.execute('''
        SELECT module_code FROM student_modules WHERE student_id = ?
        ''', (student_id,))

        enrolled_modules = [row[0] for row in cursor.fetchall()]

        if not enrolled_modules:
            print(f"Student {student_id} is not enrolled in any modules.")
            conn.close()
            return

        # Get schedule for the enrolled modules
        placeholders = ','.join(['?'] * len(enrolled_modules))
        query = f'''
        SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
               r.building, r.room_number,
               i.first_name, i.last_name,
               ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE ms.module_code IN ({placeholders})
        ORDER BY ms.day_of_week, ms.start_time
        '''

        cursor.execute(query, enrolled_modules)
        schedules = cursor.fetchall()

        if not schedules:
            print(f"No schedules found for the modules that student {student_id} is enrolled in.")
            conn.close()
            return

        # Get student name
        cursor.execute('''
        SELECT first_name, last_name FROM students WHERE student_id = ?
        ''', (student_id,))

        student_name_info = cursor.fetchone()
        first_name, last_name = student_name_info
        student_name = f"{first_name} {last_name}"

        # Format schedule data
        timetable_data = []
        for schedule in schedules:
            module_code, module_name, day, start, end, building, room, instr_first, instr_last, session_type = schedule
            module_name = module_name or "Unknown"  # Handle None values
            room_str = f"{building}-{room}" if building and room else "TBA"
            instructor = f"{instr_first} {instr_last}" if instr_first and instr_last else "TBA"

            timetable_data.append({
                'module_code': module_code,
                'module_name': module_name,
                'day': day,
                'start_time': start,
                'end_time': end,
                'room': room_str,
                'instructor': instructor,
                'session_type': session_type
            })

        conn.close()

        # Generate output based on format
        if output_format == 'display':
            self._display_timetable(student_id, student_name, timetable_data)
        elif output_format == 'pdf':
            return self._generate_pdf_timetable(student_id, student_name, timetable_data)
        elif output_format == 'csv':
            return self._export_to_csv(student_id, student_name, timetable_data, 'student')
        elif output_format == 'txt':
            return self._export_to_txt(student_id, student_name, timetable_data, 'student')
        elif output_format == 'excel':
            return self._export_to_excel(student_id, student_name, timetable_data, 'student')
        elif output_format == 'grid':
            self._display_grid_timetable(student_id, student_name, timetable_data)
        else:
            print(f"Unsupported format: {output_format}")

    def generate_instructor_timetable(self, instructor_id, output_format='display'):
        """Generate a timetable for a specific instructor"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Check if instructor exists
        cursor.execute('SELECT * FROM instructors WHERE id = ?', (instructor_id,))
        instructor = cursor.fetchone()

        if not instructor:
            print(f"Instructor ID {instructor_id} does not exist.")
            conn.close()
            return

        # Get instructor name - Fixed: properly handle the instructor tuple
        instructor_id_db, first_name, last_name = instructor[0], instructor[1], instructor[2]
        instructor_name = f"{first_name} {last_name}"

        # Get schedule for the instructor
        query = '''
        SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
               r.building, r.room_number,
               ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE ms.instructor_id = ?
        ORDER BY ms.day_of_week, ms.start_time
        '''

        cursor.execute(query, (instructor_id,))
        schedules = cursor.fetchall()

        if not schedules:
            print(f"No schedules found for instructor {instructor_name}.")
            conn.close()
            return

        # Format schedule data
        timetable_data = []
        for schedule in schedules:
            module_code, module_name, day, start, end, building, room, session_type = schedule
            module_name = module_name or "Unknown"  # Handle None values
            room_str = f"{building}-{room}" if building and room else "TBA"

            timetable_data.append({
                'module_code': module_code,
                'module_name': module_name,
                'day': day,
                'start_time': start,
                'end_time': end,
                'room': room_str,
                'instructor': instructor_name,
                'session_type': session_type
            })

        conn.close()

        # Generate output based on format
        if output_format == 'display':
            self._display_timetable(instructor_id, instructor_name, timetable_data)
        elif output_format == 'pdf':
            return self._generate_pdf_timetable(instructor_id, instructor_name, timetable_data, user_type='instructor')
        elif output_format == 'csv':
            return self._export_to_csv(instructor_id, instructor_name, timetable_data, 'instructor')
        elif output_format == 'txt':
            return self._export_to_txt(instructor_id, instructor_name, timetable_data, 'instructor')
        elif output_format == 'excel':
            return self._export_to_excel(instructor_id, instructor_name, timetable_data, 'instructor')
        elif output_format == 'grid':
            self._display_grid_timetable(instructor_id, instructor_name, timetable_data)
        else:
            print(f"Unsupported format: {output_format}")

    def _display_timetable(self, user_id, user_name, timetable_data):
        """Display a timetable in a list format"""
        print(f"\nTimetable for {user_name} (ID: {user_id}):")
        print("="*120)

        print(f"{'Day':<10} {'Time':<15} {'Module':<10} {'Module Name':<30} {'Room':<15} {'Instructor':<20} {'Type':<10}")
        print("-"*120)

        # Sort by day of week and start time
        day_order = {day: idx for idx, day in enumerate(DAYS_OF_WEEK)}
        timetable_data.sort(key=lambda x: (day_order.get(x['day'], 999), x['start_time']))

        for entry in timetable_data:
            time_slot = f"{entry['start_time']}-{entry['end_time']}"
            print(f"{entry['day']:<10} {time_slot:<15} {entry['module_code']:<10} "
                  f"{entry['module_name'][:28]:<30} {entry['room']:<15} "
                  f"{entry['instructor'][:18]:<20} {entry['session_type']:<10}")

        print("="*120)

    def _display_grid_timetable(self, user_id, user_name, timetable_data):
        """Display a timetable in a grid format"""
        print(f"\nTimetable for {user_name} (ID: {user_id}):")
        print("="*120)

        # Create a grid of days and time slots
        grid = {}
        for day in DAYS_OF_WEEK:
            grid[day] = {}
            for time_slot in TIME_SLOTS:
                grid[day][time_slot] = []

        # Populate the grid with schedule data
        for entry in timetable_data:
            day = entry['day']
            start_time = entry['start_time']
            # Find the closest time slot
            closest_slot = min(TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))

            # Add the entry to the grid
            session_info = f"{entry['module_code']} {entry['session_type'][0]} ({entry['room']})"
            if day in grid and closest_slot in grid[day]:
                grid[day][closest_slot].append(session_info)

        # Print the grid
        print(f"{'Time/Day':<10}", end="")
        for day in DAYS_OF_WEEK:
            print(f"{day:<20}", end="")
        print()

        print("-"*120)

        for time_slot in TIME_SLOTS:
            print(f"{time_slot:<10}", end="")
            for day in DAYS_OF_WEEK:
                entries = grid[day][time_slot]
                if entries:
                    print(f"{', '.join(entries):<20}", end="")
                else:
                    print(f"{'---':<20}", end="")
            print()

        print("="*120)

    def _generate_pdf_timetable(self, user_id, user_name, timetable_data, user_type='student'):
        """Generate a PDF timetable with an improved grid-based weekly schedule view"""
        # Create reports directory if it doesn't exist
        from education_system.university_system.modules.shared.constants import paths
        reports_dir = str(paths.REPORTS_DIR / 'timetable_reports')

        # Ensure directory exists
        os.makedirs(reports_dir, exist_ok=True)

        # Create PDF filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{reports_dir}/{user_type}_timetable_{user_id}_{timestamp}.pdf"

        # Create PDF document
        doc = SimpleDocTemplate(filename, pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        elements = []

        # Add title with better styling
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a2e'),
            spaceAfter=10,
            alignment=1  # Center alignment
        )
        elements.append(Paragraph(f"Weekly Timetable", title_style))

        # Add subtitle with user info
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=14,
            textColor=colors.HexColor('#16213e'),
            spaceAfter=20,
            alignment=1
        )
        elements.append(Paragraph(f"{user_name} (ID: {user_id})", subtitle_style))

        # Calculate current week dates
        today = datetime.now()
        # Find Monday of current week
        days_since_monday = today.weekday()  # 0=Monday, 6=Sunday
        monday = today - timedelta(days=days_since_monday)

        # Generate dates for each day of the week
        week_dates = []
        for i in range(5):  # Monday to Friday
            day_date = monday + timedelta(days=i)
            week_dates.append(day_date.strftime("%d/%m"))

        # Add week date range info
        week_info_style = ParagraphStyle(
            'WeekInfo',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#0f3460'),
            spaceAfter=15,
            alignment=1
        )
        week_start = monday.strftime("%d %B %Y")
        week_end = (monday + timedelta(days=4)).strftime("%d %B %Y")
        elements.append(Paragraph(f"Week: {week_start} - {week_end}", week_info_style))
        elements.append(Spacer(1, 0.2*inch))

        # Sort timetable data by day and time
        day_order = {day: idx for idx, day in enumerate(DAYS_OF_WEEK)}
        timetable_data.sort(key=lambda x: (day_order.get(x['day'], 999), x['start_time']))

        # Define session type colors
        session_colors = {
            'Lecture': colors.HexColor('#3498db'),      # Blue
            'Lab': colors.HexColor('#e74c3c'),          # Red
            'Tutorial': colors.HexColor('#2ecc71'),     # Green
            'Seminar': colors.HexColor('#f39c12'),      # Orange
            'Workshop': colors.HexColor('#9b59b6')      # Purple
        }

        # Create grid structure with time blocks
        grid = {}
        session_details = {}  # Store full details for each grid cell

        for day in DAYS_OF_WEEK:
            grid[day] = {}
            session_details[day] = {}
            for time_slot in TIME_SLOTS:
                grid[day][time_slot] = []
                session_details[day][time_slot] = []

        # Populate the grid with schedule data
        for entry in timetable_data:
            day = entry['day']
            start_time = entry['start_time']

            # Find the closest time slot
            closest_slot = min(TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))

            if day in grid and closest_slot in grid[day]:
                # Create compact session info for display
                session_type = entry['session_type']

                # Format the cell content
                cell_content = f"<b>{entry['module_code']}</b>"
                cell_content += f"<br/><font size=9>{session_type}</font>"
                cell_content += f"<br/><font size=8>{entry['room']}</font>"

                grid[day][closest_slot].append(cell_content)
                session_details[day][closest_slot].append({
                    'type': session_type,
                    'entry': entry
                })

        # Build grid table data with headers including dates
        header_row = ["Time"]
        for i, day in enumerate(DAYS_OF_WEEK):
            header_row.append(f"{day}\n{week_dates[i]}")

        grid_data = [header_row]

        # Build rows for each time slot
        for time_slot in TIME_SLOTS:
            row = [time_slot]
            for day in DAYS_OF_WEEK:
                entries = grid[day][time_slot]
                if entries:
                    # Join multiple entries if there are conflicts
                    cell_text = "<br/>---<br/>".join(entries)
                    row.append(Paragraph(cell_text, styles['Normal']))
                else:
                    row.append("")
            grid_data.append(row)

        # Create the enhanced grid table
        col_width = 1.4 * inch
        grid_table = Table(grid_data, colWidths=[0.7*inch] + [col_width]*5)

        # Build table style with colored cells
        table_style = [
            # Header styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),

            # Time column styling
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#ecf0f1')),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (0, -1), 9),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),

            # Grid and alignment
            ('GRID', (0, 0), (-1, -1), 1.5, colors.HexColor('#bdc3c7')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('FONTSIZE', (1, 1), (-1, -1), 8),

            # Cell padding
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (1, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (1, 1), (-1, -1), 8),
        ]

        # Add colored backgrounds for session cells
        for row_idx, time_slot in enumerate(TIME_SLOTS, start=1):
            for col_idx, day in enumerate(DAYS_OF_WEEK, start=1):
                if session_details[day][time_slot]:
                    # Use the color of the first session type if multiple sessions
                    session_type = session_details[day][time_slot][0]['type']
                    bg_color = session_colors.get(session_type, colors.HexColor('#95a5a6'))

                    # Apply lighter version of color for better readability
                    table_style.append(
                        ('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), bg_color)
                    )
                    table_style.append(
                        ('TEXTCOLOR', (col_idx, row_idx), (col_idx, row_idx), colors.white)
                    )
                else:
                    # Empty cells with light gray background
                    table_style.append(
                        ('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.HexColor('#f8f9fa'))
                    )

        grid_table.setStyle(TableStyle(table_style))
        elements.append(grid_table)

        # Add legend for session types
        elements.append(Spacer(1, 0.3*inch))
        legend_style = ParagraphStyle(
            'Legend',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=5
        )
        elements.append(Paragraph("<b>Session Type Legend:</b>", legend_style))

        # Create legend table
        legend_data = []
        legend_row = []
        for i, (session_type, color) in enumerate(session_colors.items()):
            legend_row.append(Paragraph(f"<font color='{color.hexval()}'>\u25A0</font> {session_type}", styles['Normal']))
            if (i + 1) % 5 == 0:  # 5 items per row
                legend_data.append(legend_row)
                legend_row = []
        if legend_row:  # Add remaining items
            legend_data.append(legend_row)

        legend_table = Table(legend_data)
        legend_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(legend_table)

        # Add footer note
        elements.append(Spacer(1, 0.3*inch))
        note_style = ParagraphStyle(
            'Note',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=1
        )
        note_text = f"Generated on: {datetime.now().strftime('%d %B %Y at %H:%M:%S')}"
        if user_type == 'student':
            note_text += "<br/>Please check for any scheduling conflicts and report them to the administration office."
        elements.append(Paragraph(note_text, note_style))

        # Build the PDF
        doc.build(elements)
        print(f"PDF timetable generated: {filename}")
        return filename

    def _export_to_csv(self, user_id, user_name, timetable_data, user_type='student'):
        """Export timetable to CSV format"""
        # Create reports directory if it doesn't exist
        from education_system.university_system.modules.shared.constants import paths
        reports_dir = str(paths.REPORTS_DIR / 'timetable_reports')

        # Create CSV filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{reports_dir}/{user_type}_timetable_{user_id}_{timestamp}.csv"

        # Ensure directory exists
        os.makedirs(reports_dir, exist_ok=True)

        # Sort timetable data by day and time
        day_order = {day: idx for idx, day in enumerate(DAYS_OF_WEEK)}
        timetable_data.sort(key=lambda x: (day_order.get(x['day'], 999), x['start_time']))

        # Write CSV file
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Day', 'Time', 'Module Code', 'Module Name', 'Room', 'Instructor', 'Session Type']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Write header
            writer.writerow({'Day': f'Timetable for {user_name} (ID: {user_id})'})
            writer.writerow({})  # Empty row
            writer.writeheader()

            # Write timetable data
            for entry in timetable_data:
                writer.writerow({
                    'Day': entry['day'],
                    'Time': f"{entry['start_time']}-{entry['end_time']}",
                    'Module Code': entry['module_code'],
                    'Module Name': entry['module_name'],
                    'Room': entry['room'],
                    'Instructor': entry['instructor'],
                    'Session Type': entry['session_type']
                })

        print(f"CSV timetable generated: {filename}")
        return filename

    def _export_to_txt(self, user_id, user_name, timetable_data, user_type='student'):
        """Export timetable to TXT format"""
        # Create reports directory if it doesn't exist
        from education_system.university_system.modules.shared.constants import paths
        reports_dir = str(paths.REPORTS_DIR / 'timetable_reports')

        # Create TXT filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{reports_dir}/{user_type}_timetable_{user_id}_{timestamp}.txt"

        # Ensure directory exists
        os.makedirs(reports_dir, exist_ok=True)

        # Sort timetable data by day and time
        day_order = {day: idx for idx, day in enumerate(DAYS_OF_WEEK)}
        timetable_data.sort(key=lambda x: (day_order.get(x['day'], 999), x['start_time']))

        # Write TXT file
        with open(filename, 'w', encoding='utf-8') as txtfile:
            # Write header
            txtfile.write(f"Timetable for {user_name} (ID: {user_id})\n")
            txtfile.write("=" * 100 + "\n")
            txtfile.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            txtfile.write("=" * 100 + "\n\n")

            # Write column headers
            headers = f"{'Day':<12} {'Time':<15} {'Module':<12} {'Module Name':<30} {'Room':<15} {'Instructor':<20} {'Type':<12}"
            txtfile.write(headers + "\n")
            txtfile.write("-" * 100 + "\n")

            # Write timetable data
            for entry in timetable_data:
                time_slot = f"{entry['start_time']}-{entry['end_time']}"
                line = f"{entry['day']:<12} {time_slot:<15} {entry['module_code']:<12} "
                line += f"{entry['module_name'][:28]:<30} {entry['room']:<15} "
                line += f"{entry['instructor'][:18]:<20} {entry['session_type']:<12}"
                txtfile.write(line + "\n")

            txtfile.write("\n" + "=" * 100 + "\n")

        print(f"TXT timetable generated: {filename}")
        return filename

    def _export_to_excel(self, user_id, user_name, timetable_data, user_type='student'):
        """Export timetable to Excel format"""
        # Create reports directory if it doesn't exist
        from education_system.university_system.modules.shared.constants import paths
        reports_dir = str(paths.REPORTS_DIR / 'timetable_reports')

        # Create Excel filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{reports_dir}/{user_type}_timetable_{user_id}_{timestamp}.xlsx"

        # Ensure directory exists
        os.makedirs(reports_dir, exist_ok=True)

        # Sort timetable data by day and time
        day_order = {day: idx for idx, day in enumerate(DAYS_OF_WEEK)}
        timetable_data.sort(key=lambda x: (day_order.get(x['day'], 999), x['start_time']))

        # Create DataFrame for list view
        list_data = []
        for entry in timetable_data:
            list_data.append({
                'Day': entry['day'],
                'Time': f"{entry['start_time']}-{entry['end_time']}",
                'Module Code': entry['module_code'],
                'Module Name': entry['module_name'],
                'Room': entry['room'],
                'Instructor': entry['instructor'],
                'Session Type': entry['session_type']
            })

        df_list = pd.DataFrame(list_data)

        # Create DataFrame for grid view
        grid_data = {}
        for day in DAYS_OF_WEEK:
            grid_data[day] = {}
            for time_slot in TIME_SLOTS:
                grid_data[day][time_slot] = []

        # Populate the grid with schedule data
        for entry in timetable_data:
            day = entry['day']
            start_time = entry['start_time']
            # Find the closest time slot
            closest_slot = min(TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))

            # Add the entry to the grid
            session_info = f"{entry['module_code']} {entry['session_type'][0]} ({entry['room']})"
            if day in grid_data and closest_slot in grid_data[day]:
                grid_data[day][closest_slot].append(session_info)

        # Convert grid to DataFrame
        grid_df_data = []
        for time_slot in TIME_SLOTS:
            row = {'Time': time_slot}
            for day in DAYS_OF_WEEK:
                entries = grid_data[day][time_slot]
                row[day] = '\n'.join(entries) if entries else ''
            grid_df_data.append(row)

        df_grid = pd.DataFrame(grid_df_data)

        # Write to Excel with multiple sheets
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Sheet 1: Info
            info_data = {
                'Information': ['Timetable for', 'User ID', 'Generated on'],
                'Value': [user_name, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
            }
            df_info = pd.DataFrame(info_data)
            df_info.to_excel(writer, sheet_name='Info', index=False)

            # Sheet 2: List View
            df_list.to_excel(writer, sheet_name='List View', index=False)

            # Sheet 3: Grid View
            df_grid.to_excel(writer, sheet_name='Grid View', index=False)

            # Auto-adjust column widths
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column_cells in worksheet.columns:
                    max_length = 0
                    for cell in column_cells:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except Exception:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_cells[0].column_letter].width = adjusted_width

        print(f"Excel timetable generated: {filename}")
        return filename
