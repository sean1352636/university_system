from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
from education_system.university_system.infrastructure.exceptions import (
    CourseNotFoundError,
    ValidationError,
)

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from education_system.university_system.modules.shared.utils.gui_language_selector import (
        show_gui_language_selector,
    )
    I18N_AVAILABLE = True
    GUI_LANG_SELECTOR_AVAILABLE = True
    # Initialize i18n if not already done
    init_i18n()
except ImportError:
    I18N_AVAILABLE = False
    GUI_LANG_SELECTOR_AVAILABLE = False
    _t = lambda key, **kwargs: key  # Fallback: return key as-is
    get_current_language = lambda: "en"
    get_current_language_name = lambda: "English"
    set_language = lambda lang, save=True: False
    get_available_language_list = lambda: [("en", "English")]
    show_gui_language_selector = lambda parent=None: "en"

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import os
import sys
from datetime import datetime, timedelta
import threading
import subprocess
import webbrowser
from pathlib import Path
from education_system.university_system.infrastructure.database.db import sqlite3
# This ensures full backward compatibility
try:
    from education_system.university_system.modules.domain.academics.services.module_scheduling import (
        ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES,
        display_enhanced_scheduling_menu  # Keep CLI available
    )
except ImportError:
    # If the original module isn't available, we'll define basic constants
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']
    ROOM_TYPES = ['Lecture Hall', 'Lab', 'Tutorial Room', 'Seminar Room', 'Workshop Room', 'Computer Lab', 'Other']

    # Import the ModuleScheduler class from the document
    try:
        from education_system.university_system.modules.domain.academics.services.module_scheduling import (ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES, display_enhanced_scheduling_menu)
    except Exception:
        class ModuleScheduler: pass

from education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui import ModuleSchedulingGUI

def _export_text_to_pdf(self, content):
    """Export text content to PDF"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet

        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Save PDF"
        )

        if filename:
            doc = SimpleDocTemplate(filename, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            for line in content.split('\n'):
                story.append(Paragraph(line or ' ', styles['Normal']))

            doc.build(story)
            messagebox.showinfo("Success", f"PDF exported to {filename}", parent=self.root)

    except ImportError:
        messagebox.showerror("Error", "ReportLab library not available for PDF export.", parent=self.root)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export PDF: {str(e)}", parent=self.root)

ModuleSchedulingGUI._export_text_to_pdf = _export_text_to_pdf

def _export_text_to_csv(self, content):
    """Export text content to CSV"""
    try:
        import csv

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Save CSV"
        )

        if filename:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                for line in content.split('\n'):
                    if line.strip():
                        writer.writerow([line])

            messagebox.showinfo("Success", f"CSV exported to {filename}", parent=self.root)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to export CSV: {str(e)}", parent=self.root)

ModuleSchedulingGUI._export_text_to_csv = _export_text_to_csv

def _export_text_to_excel(self, content):
    """Export text content to Excel"""
    try:
        import pandas as pd

        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            title="Save Excel"
        )

        if filename:
            lines = [line for line in content.split('\n') if line.strip()]
            df = pd.DataFrame(lines, columns=['Content'])
            df.to_excel(filename, index=False)

            messagebox.showinfo("Success", f"Excel file exported to {filename}", parent=self.root)

    except ImportError:
        messagebox.showerror("Error", "Pandas library not available for Excel export.", parent=self.root)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export Excel: {str(e)}", parent=self.root)

ModuleSchedulingGUI._export_text_to_excel = _export_text_to_excel

def _export_timetable_to_ical(self, timetable_data):
    """Export timetable to iCal format"""
    try:
        from datetime import datetime, timedelta
        import hashlib

        filename = filedialog.asksaveasfilename(
            defaultextension=".ics",
            filetypes=[("iCalendar files", "*.ics"), ("All files", "*.*")],
            title="Save iCalendar File"
        )

        if not filename:
            return

        # Generate iCal content
        ical_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//University Management System//Module Scheduling//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:Module Schedule",
            "X-WR-TIMEZONE:UTC"
        ]

        # Get current week's Monday as base date
        today = datetime.now()
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)

        # Day name to offset mapping
        day_offsets = {
            'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
            'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
        }

        # Create events for each session
        for entry in timetable_data:
            try:
                day = entry.get('day', entry.get('day_of_week', ''))
                start_time_str = entry.get('start_time', '')
                end_time_str = entry.get('end_time', '')
                module_code = entry.get('module_code', 'N/A')
                session_type = entry.get('session_type', 'Session')
                room = entry.get('room', 'TBA')

                if not day or not start_time_str or not end_time_str:
                    continue

                # Calculate the date for this event
                day_offset = day_offsets.get(day, 0)
                event_date = monday + timedelta(days=day_offset)

                # Parse times
                start_hour, start_min = map(int, start_time_str.split(':'))
                end_hour, end_min = map(int, end_time_str.split(':'))

                start_dt = event_date.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
                end_dt = event_date.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)

                # Generate unique UID
                uid_source = f"{module_code}-{day}-{start_time_str}-{end_time_str}"
                uid = hashlib.sha256(uid_source.encode()).hexdigest()

                # Format timestamps for iCal (UTC format)
                dtstart = start_dt.strftime("%Y%m%dT%H%M%S")
                dtend = end_dt.strftime("%Y%m%dT%H%M%S")

                # Add event
                ical_lines.extend([
                    "BEGIN:VEVENT",
                    f"UID:{uid}@university.edu",
                    f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}",
                    f"DTSTART:{dtstart}",
                    f"DTEND:{dtend}",
                    f"SUMMARY:{module_code} - {session_type}",
                    f"LOCATION:{room}",
                    f"DESCRIPTION:{module_code} {session_type}\\nRoom: {room}",
                    "STATUS:CONFIRMED",
                    f"RRULE:FREQ=WEEKLY;COUNT=15",  # Repeat for 15 weeks (semester)
                    "END:VEVENT"
                ])

            except Exception as e:
                print(f"Error processing entry for iCal: {e}")
                continue

        ical_lines.append("END:VCALENDAR")

        # Write to file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\r\n'.join(ical_lines))

        messagebox.showinfo("Success", f"iCalendar file exported to {filename}\n\nYou can import this into Google Calendar, Outlook, Apple Calendar, or any calendar application.", parent=self.root)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to export iCalendar: {str(e)}", parent=self.root)

ModuleSchedulingGUI._export_timetable_to_ical = _export_timetable_to_ical

def _export_timetable_to_pdf(self, timetable_data):
    """Export timetable to PDF"""
    try:
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors

        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Save PDF"
        )

        if not filename:
            return

        doc = SimpleDocTemplate(filename, pagesize=landscape(letter))
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title = Paragraph("Module Timetable", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 20))

        # Convert timetable data to table format
        table_data = [['Day', 'Time', 'Module', 'Type', 'Room']]

        for entry in timetable_data:
            day = entry.get('day', entry.get('day_of_week', 'N/A'))
            time_str = f"{entry.get('start_time', '')}-{entry.get('end_time', '')}"
            module = entry.get('module_code', 'N/A')
            session_type = entry.get('session_type', 'N/A')
            room = entry.get('room', 'TBA')

            table_data.append([day, time_str, module, session_type, room])

        # Create table
        table = Table(table_data, colWidths=[100, 120, 100, 100, 120])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        elements.append(table)
        doc.build(elements)

        messagebox.showinfo("Success", f"PDF exported to {filename}", parent=self.root)

    except ImportError:
        messagebox.showerror("Error", "ReportLab library not available for PDF export.", parent=self.root)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export PDF: {str(e)}", parent=self.root)

ModuleSchedulingGUI._export_timetable_to_pdf = _export_timetable_to_pdf

def _export_timetable_to_csv(self, timetable_data):
    """Export timetable to CSV"""
    try:
        import csv

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Save CSV"
        )

        if not filename:
            return

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Day', 'Start Time', 'End Time', 'Module Code', 'Session Type', 'Room'])

            for entry in timetable_data:
                day = entry.get('day', entry.get('day_of_week', 'N/A'))
                start_time = entry.get('start_time', '')
                end_time = entry.get('end_time', '')
                module = entry.get('module_code', 'N/A')
                session_type = entry.get('session_type', 'N/A')
                room = entry.get('room', 'TBA')

                writer.writerow([day, start_time, end_time, module, session_type, room])

        messagebox.showinfo("Success", f"CSV exported to {filename}", parent=self.root)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to export CSV: {str(e)}", parent=self.root)

ModuleSchedulingGUI._export_timetable_to_csv = _export_timetable_to_csv

def _export_timetable_to_excel(self, timetable_data):
    """Export timetable to Excel"""
    try:
        import pandas as pd

        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            title="Save Excel"
        )

        if not filename:
            return

        # Convert to DataFrame
        data = []
        for entry in timetable_data:
            data.append({
                'Day': entry.get('day', entry.get('day_of_week', 'N/A')),
                'Start Time': entry.get('start_time', ''),
                'End Time': entry.get('end_time', ''),
                'Module Code': entry.get('module_code', 'N/A'),
                'Session Type': entry.get('session_type', 'N/A'),
                'Room': entry.get('room', 'TBA')
            })

        df = pd.DataFrame(data)
        df.to_excel(filename, index=False, engine='openpyxl')

        messagebox.showinfo("Success", f"Excel file exported to {filename}", parent=self.root)

    except ImportError:
        messagebox.showerror("Error", "Pandas library not available for Excel export.", parent=self.root)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export Excel: {str(e)}", parent=self.root)

ModuleSchedulingGUI._export_timetable_to_excel = _export_timetable_to_excel

def export_to_ical(self, entity_type, entity_id, filename=None):
    """Export schedule to iCal format"""
    try:
        from icalendar import Calendar, Event
    except ImportError:
        messagebox.showerror("Error", "icalendar library not installed. Run: pip install icalendar", parent=self.root)
        return None

    cal = Calendar()
    cal.add('prodid', '-//University Schedule//EN')
    cal.add('version', '2.0')

    # Get schedule data
    if entity_type == 'student':
        schedules = self._get_student_schedule_data(entity_id)
        cal.add('x-wr-calname', f'Student {entity_id} Schedule')
    elif entity_type == 'instructor':
        schedules = self._get_instructor_schedule_data(entity_id)
        cal.add('x-wr-calname', f'Instructor {entity_id} Schedule')
    else:
        messagebox.showerror("Error", "Invalid entity type", parent=self.root)
        return None

    # Add events
    for schedule in schedules:
        event = Event()
        event.add('summary', f"{schedule['module_code']} - {schedule['session_type']}")
        event.add('description', f"Module: {schedule['module_name']}\nRoom: {schedule['room']}\nInstructor: {schedule['instructor']}")

        # Calculate event times (recurring weekly)
        start_time = datetime.strptime(schedule['start_time'], "%H:%M").time()
        end_time = datetime.strptime(schedule['end_time'], "%H:%M").time()

        # Get day index (Monday = 0)
        day_index = DAYS_OF_WEEK.index(schedule['day'])

        # Find next occurrence of this day
        today = datetime.now().date()
        days_ahead = day_index - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7

        event_date = today + timedelta(days=days_ahead)
        event_start = datetime.combine(event_date, start_time)
        event_end = datetime.combine(event_date, end_time)

        event.add('dtstart', event_start)
        event.add('dtend', event_end)
        event.add('location', schedule['room'])

        # Add recurrence rule (weekly for the semester)
        event.add('rrule', {'freq': 'weekly', 'count': 15})  # 15 weeks typical semester

        cal.add_component(event)

    # Save to file
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = filedialog.asksaveasfilename(
            defaultextension=".ics",
            filetypes=[("iCalendar files", "*.ics"), ("All files", "*.*")],
            initialfile=f"{entity_type}_{entity_id}_schedule_{timestamp}.ics"
        )

    if filename:
        with open(filename, 'wb') as f:
            f.write(cal.to_ical())

        messagebox.showinfo("Success", f"iCal file exported: {filename}", parent=self.root)
        return filename

    return None

ModuleSchedulingGUI.export_to_ical = export_to_ical

def _export_analytics_csv(self, data, filename_prefix):
    """Export analytics data to CSV"""
    filename = filedialog.asksaveasfilename(
        title="Export Analytics to CSV",
        defaultextension=".csv",
        initialfile=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )

    if not filename:
        return None

    try:
        import csv

        with open(filename, 'w', newline='') as f:
            if data:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)

        messagebox.showinfo("Export Complete", f"Analytics exported to:\n{filename}", parent=self.root)
        return filename

    except Exception as e:
        messagebox.showerror("Export Error", f"Failed to export analytics: {str(e)}", parent=self.root)
        return None

ModuleSchedulingGUI._export_analytics_csv = _export_analytics_csv

def _generate_analytics_pdf(self, data, title):
    """Generate analytics PDF report (requires reportlab)"""
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors

        filename = filedialog.asksaveasfilename(
            title="Save PDF Report",
            defaultextension=".pdf",
            initialfile=f"{title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )

        if not filename:
            return None

        # Create PDF
        doc = SimpleDocTemplate(filename, pagesize=letter)
        elements = []

        # Add title
        styles = getSampleStyleSheet()
        elements.append(Paragraph(title, styles['Title']))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
        elements.append(Paragraph("<br/><br/>", styles['Normal']))

        # Add data table
        if data:
            table_data = [list(data[0].keys())]  # Header
            table_data.extend([list(row.values()) for row in data])

            t = Table(table_data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            elements.append(t)

        doc.build(elements)

        messagebox.showinfo("PDF Generated", f"PDF report generated:\n{filename}", parent=self.root)
        return filename

    except ImportError:
        messagebox.showerror("Error", "reportlab library not installed.\nRun: pip install reportlab", parent=self.root)
        return None
    except Exception as e:
        messagebox.showerror("PDF Error", f"Failed to generate PDF: {str(e)}", parent=self.root)
        return None

ModuleSchedulingGUI._generate_analytics_pdf = _generate_analytics_pdf

