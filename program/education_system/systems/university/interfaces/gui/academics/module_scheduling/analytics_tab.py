from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
from education_system.systems.university.infrastructure.exceptions import (
    CourseNotFoundError,
    ValidationError,
)

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from education_system.systems.university.infrastructure.utils.gui_language_selector import (
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
from education_system.systems.university.infrastructure.database.db import sqlite3
# This ensures full backward compatibility
try:
    from education_system.systems.university.domain.academics.services.module_scheduling import (
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
        from education_system.systems.university.domain.academics.services.module_scheduling import (ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES, display_enhanced_scheduling_menu)
    except Exception:
        class ModuleScheduler: pass

from education_system.systems.university.interfaces.gui.academics.module_scheduling.main_gui import ModuleSchedulingGUI

def create_analytics_tab(self):
    """Create the analytics and reporting tab"""
    analytics_frame = ttk.Frame(self.notebook)
    self.notebook.add(analytics_frame, text=_t("scheduling.tabs.analytics"))

    # Controls frame
    controls_frame = ttk.Frame(analytics_frame)
    controls_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(controls_frame, text=_t("scheduling.room_utilization"),
              command=self.show_room_utilization).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("scheduling.instructor_workload"),
              command=self.show_instructor_workload).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("scheduling.peak_usage"),
              command=self.show_peak_usage).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("scheduling.generate_charts"),
              command=self.generate_charts).pack(side=tk.LEFT, padx=5)

    # Analytics display area
    display_frame = ttk.LabelFrame(analytics_frame, text=_t("scheduling.analytics_results"), padding=10)
    display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    self.analytics_text = scrolledtext.ScrolledText(display_frame, font=('Courier', 10))
    self.analytics_text.pack(fill=tk.BOTH, expand=True)

ModuleSchedulingGUI.create_analytics_tab = create_analytics_tab


def _aw_alive(widget):
    """True if *widget* still exists in Tk (not destroyed)."""
    try:
        return bool(widget) and bool(widget.winfo_exists())
    except Exception:
        return False


def _safe_parent(self):
    """Return self.root only if it's still a live window, else None — so a
    messagebox never crashes on a destroyed parent."""
    return self.root if _aw_alive(getattr(self, "root", None)) else None


def _analytics_ready(self):
    """Guard analytics actions against a closed window. Returns True when the
    analytics text area is alive; otherwise warns (safely) and returns False."""
    if _aw_alive(getattr(self, "analytics_text", None)):
        return True
    try:
        messagebox.showinfo(
            "Analytics",
            "The Scheduling Analytics view is no longer open. Reopen it and try again.",
            parent=_safe_parent(self))
    except Exception:
        pass
    return False


ModuleSchedulingGUI._safe_parent = _safe_parent
ModuleSchedulingGUI._analytics_ready = _analytics_ready


def show_room_utilization(self):
    """Show room utilization analytics"""
    try:
        if not self._analytics_ready():
            return
        self.analytics_text.delete(1.0, tk.END)
        self.analytics_text.insert(tk.END, "Generating room utilization report...\n")
        self.root.update()

        # Get room utilization data
        room_data = self.scheduler.generate_room_utilization_report('data')

        if not room_data:
            self.analytics_text.insert(tk.END, "No room data available.")
            return

        # Build report text
        report_text = "Room Utilization Analytics\n"
        report_text += "=" * 100 + "\n"
        report_text += f"{'Room':<15} {'Type':<15} {'Capacity':<10} {'Sessions':<10} {'Utilization':<12} {'Avg Duration':<12}\n"
        report_text += "-" * 100 + "\n"

        def _s(v, default="-"):
            return default if v is None else str(v)

        for room in room_data:
            line = (
                f"{_s(room.get('Room')):<15} "
                f"{_s(room.get('Type')):<15} "
                f"{_s(room.get('Capacity'), '0'):<10} "
                f"{_s(room.get('Sessions'), '0'):<10} "
                f"{_s(room.get('Utilization Rate (%)'), '0'):<12} "
                f"{_s(room.get('Avg Duration (min)'), '0'):<12}\n"
            )
            report_text += line

        report_text += "=" * 100 + "\n"

        # Summary statistics
        if room_data:
            rates = [room.get('Utilization Rate (%)') or 0 for room in room_data]
            avg_utilization = sum(rates) / len(rates) if rates else 0
            report_text += "\nSummary:\n"
            report_text += f"Total Rooms: {len(room_data)}\n"
            report_text += f"Average Utilization: {avg_utilization:.2f}%\n"

            most_utilized = max(room_data, key=lambda x: x.get('Utilization Rate (%)') or 0)
            least_utilized = min(room_data, key=lambda x: x.get('Utilization Rate (%)') or 0)
            report_text += (
                f"Most Utilized: {_s(most_utilized.get('Room'))} "
                f"({_s(most_utilized.get('Utilization Rate (%)'), '0')}%)\n"
            )
            report_text += (
                f"Least Utilized: {_s(least_utilized.get('Room'))} "
                f"({_s(least_utilized.get('Utilization Rate (%)'), '0')}%)\n"
            )

        # Update analytics text area
        self.analytics_text.delete(1.0, tk.END)
        self.analytics_text.insert(tk.END, report_text)

        # Show report in window with email option
        self._show_report_with_email_option(
            "Room Utilization Report",
            report_text,
            "Room Utilization Analytics"
        )

        self.update_activity_log("Generated room utilization report")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate room utilization report: {str(e)}", parent=self._safe_parent())

ModuleSchedulingGUI.show_room_utilization = show_room_utilization

def show_instructor_workload(self):
    """Show instructor workload analytics"""
    try:
        if not self._analytics_ready():
            return
        self.analytics_text.delete(1.0, tk.END)
        self.analytics_text.insert(tk.END, "Generating instructor workload report...\n")
        self.root.update()

        # Get workload data
        workload_data = self.scheduler.generate_instructor_workload_report('data')

        if not workload_data:
            self.analytics_text.insert(tk.END, "No instructor data available.")
            return

        # Build report text
        report_text = "Instructor Workload Analytics\n"
        report_text += "=" * 120 + "\n"
        report_text += f"{'Instructor':<25} {'Department':<15} {'Sessions':<10} {'Hours':<8} {'Max':<8} {'Load %':<8} {'Status':<12}\n"
        report_text += "-" * 120 + "\n"

        for instructor in workload_data:
            line = f"{instructor['Instructor']:<25} {instructor['Department']:<15} {instructor['Sessions']:<10} {instructor['Total Hours']:<8} {instructor['Max Hours']:<8} {instructor['Workload (%)']:<8} {instructor['Status']:<12}\n"
            report_text += line

        report_text += "=" * 120 + "\n"

        # Highlight overloaded instructors
        overloaded = [i for i in workload_data if i['Status'] == 'Overloaded']
        if overloaded:
            report_text += f"\nWARNING: {len(overloaded)} instructor(s) are overloaded!\n"
            for instructor in overloaded:
                report_text += f"  - {instructor['Instructor']}: {instructor['Workload (%)']}% workload\n"

        # Update analytics text area
        self.analytics_text.delete(1.0, tk.END)
        self.analytics_text.insert(tk.END, report_text)

        # Show report in window with email option
        self._show_report_with_email_option(
            "Instructor Workload Report",
            report_text,
            "Instructor Workload Analytics"
        )

        self.update_activity_log("Generated instructor workload report")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate instructor workload report: {str(e)}", parent=self._safe_parent())

ModuleSchedulingGUI.show_instructor_workload = show_instructor_workload

def show_workload_report(self):
    """Show workload report and switch to analytics tab"""
    self.notebook.select(5)  # Switch to analytics tab
    self.show_instructor_workload()

ModuleSchedulingGUI.show_workload_report = show_workload_report

def show_peak_usage(self):
    """Show peak usage analysis"""
    try:
        if not self._analytics_ready():
            return
        # Build report text
        report_text = "Peak Usage Analysis\n"
        report_text += "=" * 60 + "\n"

        peak_times = self.scheduler._analyze_peak_usage()

        for day, times in peak_times.items():
            report_text += f"{day}: {', '.join(times) if times else 'No data'}\n"

        # Module distribution
        module_stats = self.scheduler._analyze_module_distribution()
        report_text += "\nModule Distribution:\n"
        report_text += f"Total Modules: {module_stats['total']}\n"
        report_text += f"Most Common Session Type: {module_stats['most_common_type']}\n"
        report_text += f"Average Sessions per Module: {module_stats['avg_sessions']:.2f}\n"

        # Update analytics text area
        self.analytics_text.delete(1.0, tk.END)
        self.analytics_text.insert(tk.END, report_text)

        # Show report in window with email option
        self._show_report_with_email_option(
            "Peak Usage Analysis",
            report_text,
            "Peak Usage Analytics"
        )

        self.update_activity_log("Generated peak usage analysis")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate peak usage analysis: {str(e)}", parent=self._safe_parent())

ModuleSchedulingGUI.show_peak_usage = show_peak_usage

def generate_charts(self):
    """Generate visual charts"""
    try:
        self.update_status("Generating charts...")
        chart_path = self.scheduler.generate_utilization_charts()

        if chart_path and os.path.exists(chart_path):
            # Build report text
            report_text = "Visual Charts Generated Successfully\n"
            report_text += "=" * 60 + "\n\n"
            report_text += f"Chart Location: {chart_path}\n\n"
            report_text += "The following charts have been generated:\n"
            report_text += "  - Room Utilization Chart\n"
            report_text += "  - Instructor Workload Chart\n"
            report_text += "  - Peak Usage Analysis Chart\n\n"
            report_text += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

            # Show report in window with email option
            self._show_report_with_email_option(
                "Chart Generation Report",
                report_text,
                "Visual Charts"
            )

            # Ask if user wants to open charts
            if messagebox.askyesno("Open Charts", f"Charts generated successfully!\n\nPath: {chart_path}\n\nWould you like to open the charts?", parent=self._safe_parent()):
                webbrowser.open(f"file://{os.path.abspath(chart_path)}")

            self.update_activity_log("Generated utilization charts")
        else:
            messagebox.showinfo("Info", "Charts generated. Check the analytics folder.", parent=self._safe_parent())

        self.update_status("Ready")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate charts: {str(e)}", parent=self._safe_parent())
        self.update_status("Ready")

ModuleSchedulingGUI.generate_charts = generate_charts

def generate_room_utilization_report(self):
    """Generate comprehensive room utilization analytics in a dialog"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Get room utilization data
        cursor.execute('''
        SELECT r.id, r.building, r.room_number, r.capacity, r.room_type,
               COUNT(ms.id) as scheduled_sessions,
               AVG(CASE
                   WHEN ms.end_time IS NOT NULL AND ms.start_time IS NOT NULL
                   THEN (CAST(SUBSTR(ms.end_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.end_time, 4, 2) AS INTEGER)) -
                        (CAST(SUBSTR(ms.start_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.start_time, 4, 2) AS INTEGER))
                   ELSE 0 END) as avg_session_duration
        FROM rooms r
        LEFT JOIN module_schedule ms ON r.id = ms.room_id
        WHERE r.is_active = 1
        GROUP BY r.id, r.building, r.room_number, r.capacity, r.room_type
        ORDER BY scheduled_sessions DESC
        ''')

        room_data = cursor.fetchall()

    if not room_data:
        messagebox.showinfo("No Data", "No room data available.", parent=self._safe_parent())
        return

    # Calculate utilization metrics
    total_possible_slots = len(DAYS_OF_WEEK) * len(TIME_SLOTS)

    analytics_data = []
    for room in room_data:
        room_id, building, room_number, capacity, room_type, sessions, avg_duration = room
        utilization_rate = (sessions / total_possible_slots) * 100 if total_possible_slots > 0 else 0

        analytics_data.append({
            'Room': f"{building}-{room_number}",
            'Type': room_type,
            'Capacity': capacity,
            'Sessions': sessions,
            'Utilization': round(utilization_rate, 2),
            'Avg Duration': round(avg_duration or 0, 2)
        })

    # Create dialog
    dialog = tk.Toplevel(self.root)
    dialog.title("Room Utilization Report")
    dialog.geometry("1000x600")
    dialog.transient(self.root)

    # Create treeview
    columns = ('Room', 'Type', 'Capacity', 'Sessions', 'Utilization %', 'Avg Duration (min)')
    tree = ttk.Treeview(dialog, columns=columns, show='headings')

    for col in columns:
        tree.heading(col, text=col)

    tree.column('Room', width=120)
    tree.column('Type', width=150)
    tree.column('Capacity', width=80)
    tree.column('Sessions', width=80)
    tree.column('Utilization %', width=120)
    tree.column('Avg Duration (min)', width=150)

    for data in analytics_data:
        tree.insert('', tk.END, values=(
            data['Room'], data['Type'], data['Capacity'],
            data['Sessions'], data['Utilization'], data['Avg Duration']
        ))

    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Summary frame
    summary_frame = ttk.Frame(dialog)
    summary_frame.pack(fill=tk.X, padx=10, pady=5)

    if analytics_data:
        avg_util = sum(d['Utilization'] for d in analytics_data) / len(analytics_data)
        most_used = max(analytics_data, key=lambda x: x['Utilization'])
        least_used = min(analytics_data, key=lambda x: x['Utilization'])

        summary_text = f"Total Rooms: {len(analytics_data)} | " \
                      f"Avg Utilization: {avg_util:.2f}% | " \
                      f"Most Used: {most_used['Room']} ({most_used['Utilization']:.2f}%) | " \
                      f"Least Used: {least_used['Room']} ({least_used['Utilization']:.2f}%)"

        ttk.Label(summary_frame, text=summary_text).pack()

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

ModuleSchedulingGUI.generate_room_utilization_report = generate_room_utilization_report

def generate_instructor_workload_report(self):
    """Generate instructor workload analysis in a dialog"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
        SELECT i.id, i.first_name, i.last_name, i.department, i.max_hours_per_week,
               COUNT(ms.id) as total_sessions,
               SUM(CASE
                   WHEN ms.end_time IS NOT NULL AND ms.start_time IS NOT NULL
                   THEN (CAST(SUBSTR(ms.end_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.end_time, 4, 2) AS INTEGER)) -
                        (CAST(SUBSTR(ms.start_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.start_time, 4, 2) AS INTEGER))
                   ELSE 0 END) / 60.0 as total_hours
        FROM instructors i
        LEFT JOIN module_schedule ms ON i.id = ms.instructor_id
        WHERE i.is_active = 1
        GROUP BY i.id, i.first_name, i.last_name, i.department, i.max_hours_per_week
        ORDER BY total_hours DESC
        ''')

        instructor_data = cursor.fetchall()

    workload_data = []
    for instructor in instructor_data:
        inst_id, first_name, last_name, dept, max_hours, sessions, total_hours = instructor
        name = f"{first_name} {last_name}"
        total_hours = total_hours or 0
        max_hours = max_hours or 40
        workload_percentage = (total_hours / max_hours) * 100

        workload_data.append({
            'Instructor': name,
            'Department': dept,
            'Sessions': sessions,
            'Hours': round(total_hours, 2),
            'Max': max_hours,
            'Workload': round(workload_percentage, 2),
            'Status': 'Overloaded' if workload_percentage > 100 else 'Normal'
        })

    # Create dialog
    dialog = tk.Toplevel(self.root)
    dialog.title("Instructor Workload Report")
    dialog.geometry("1100x600")
    dialog.transient(self.root)

    # Create treeview
    columns = ('Instructor', 'Department', 'Sessions', 'Hours', 'Max Hours', 'Workload %', 'Status')
    tree = ttk.Treeview(dialog, columns=columns, show='headings')

    for col in columns:
        tree.heading(col, text=col)

    tree.column('Instructor', width=180)
    tree.column('Department', width=140)
    tree.column('Sessions', width=80)
    tree.column('Hours', width=80)
    tree.column('Max Hours', width=80)
    tree.column('Workload %', width=100)
    tree.column('Status', width=100)

    overloaded_count = 0
    for data in workload_data:
        # Color code overloaded instructors
        tag = 'overloaded' if data['Status'] == 'Overloaded' else ''
        if data['Status'] == 'Overloaded':
            overloaded_count += 1

        tree.insert('', tk.END, values=(
            data['Instructor'], data['Department'], data['Sessions'],
            data['Hours'], data['Max'], data['Workload'], data['Status']
        ), tags=(tag,))

    # Configure tag colors
    tree.tag_configure('overloaded', background='#ffcccc')

    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Warning if overloaded
    if overloaded_count > 0:
        warning_frame = ttk.Frame(dialog)
        warning_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(warning_frame, text=f"⚠ WARNING: {overloaded_count} instructor(s) are overloaded!",
                 foreground='red', font=('Arial', 10, 'bold')).pack()

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

ModuleSchedulingGUI.generate_instructor_workload_report = generate_instructor_workload_report

def generate_scheduling_analytics_dashboard(self):
    """Generate comprehensive scheduling analytics dashboard"""
    # This combines multiple analytics into one dashboard
    dialog = tk.Toplevel(self.root)
    dialog.title("Scheduling Analytics Dashboard")
    dialog.geometry("1200x700")
    dialog.transient(self.root)

    # Create notebook for different analytics
    notebook = ttk.Notebook(dialog)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Tab 1: Peak Usage Analysis
    peak_frame = ttk.Frame(notebook)
    notebook.add(peak_frame, text="Peak Usage")

    peak_data = self._analyze_peak_usage()
    if peak_data:
        text_widget = scrolledtext.ScrolledText(peak_frame, wrap=tk.WORD, width=80, height=20)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_widget.insert(tk.END, "Peak Usage Analysis\n")
        text_widget.insert(tk.END, "=" * 60 + "\n\n")

        for day, times in peak_data.items():
            text_widget.insert(tk.END, f"{day}:\n")
            for time, count in times.items():
                text_widget.insert(tk.END, f"  {time}: {count} sessions\n")
            text_widget.insert(tk.END, "\n")

        text_widget.config(state=tk.DISABLED)

    # Tab 2: Module Distribution
    dist_frame = ttk.Frame(notebook)
    notebook.add(dist_frame, text="Module Distribution")

    dist_data = self._analyze_module_distribution()
    if dist_data:
        text_widget2 = scrolledtext.ScrolledText(dist_frame, wrap=tk.WORD, width=80, height=20)
        text_widget2.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_widget2.insert(tk.END, "Module Distribution Analysis\n")
        text_widget2.insert(tk.END, "=" * 60 + "\n\n")

        for category, data in dist_data.items():
            text_widget2.insert(tk.END, f"{category}: {data}\n")

        text_widget2.config(state=tk.DISABLED)

    # Tab 3: Room Efficiency
    efficiency_frame = ttk.Frame(notebook)
    notebook.add(efficiency_frame, text="Room Efficiency")

    efficiency_data = self._analyze_room_efficiency()
    if efficiency_data:
        columns = ('Room', 'Efficiency %', 'Total Sessions', 'Avg Duration')
        tree = ttk.Treeview(efficiency_frame, columns=columns, show='headings')

        for col in columns:
            tree.heading(col, text=col)

        for room_data in efficiency_data:
            tree.insert('', tk.END, values=(
                room_data['room'],
                room_data['efficiency'],
                room_data['sessions'],
                room_data['avg_duration']
            ))

        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

ModuleSchedulingGUI.generate_scheduling_analytics_dashboard = generate_scheduling_analytics_dashboard

def _analyze_room_efficiency(self):
    """Analyze room efficiency"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
        SELECT r.building || '-' || r.room_number as room,
               COUNT(ms.id) as sessions,
               AVG(CASE
                   WHEN ms.end_time IS NOT NULL AND ms.start_time IS NOT NULL
                   THEN (CAST(SUBSTR(ms.end_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.end_time, 4, 2) AS INTEGER)) -
                        (CAST(SUBSTR(ms.start_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.start_time, 4, 2) AS INTEGER))
                   ELSE 0 END) as avg_duration
        FROM rooms r
        LEFT JOIN module_schedule ms ON r.id = ms.room_id
        WHERE r.is_active = 1
        GROUP BY r.id, r.building, r.room_number
        ''')

        results = cursor.fetchall()

    efficiency_data = []
    max_possible = len(DAYS_OF_WEEK) * len(TIME_SLOTS)

    for room, sessions, avg_dur in results:
        efficiency = (sessions / max_possible * 100) if max_possible > 0 else 0
        efficiency_data.append({
            'room': room,
            'efficiency': round(efficiency, 2),
            'sessions': sessions,
            'avg_duration': round(avg_dur or 0, 2)
        })

    return efficiency_data

ModuleSchedulingGUI._analyze_room_efficiency = _analyze_room_efficiency

def generate_reports(self):
    """Generate comprehensive reports and automatically email to admin"""
    try:
        self.update_status("Generating reports...")

        # Generate data reports for display
        room_data = self.scheduler.generate_room_utilization_report('data')
        workload_data = self.scheduler.generate_instructor_workload_report('data')

        # Build comprehensive report text
        report_text = "COMPREHENSIVE MODULE SCHEDULING REPORTS\n"
        report_text += "=" * 100 + "\n\n"

        # Room Utilization Report
        if room_data:
            report_text += "ROOM UTILIZATION REPORT\n"
            report_text += "-" * 100 + "\n"
            report_text += f"{'Room':<15} {'Type':<15} {'Capacity':<10} {'Sessions':<10} {'Utilization':<12} {'Avg Duration':<12}\n"
            report_text += "-" * 100 + "\n"

            for room in room_data:
                line = f"{room['Room']:<15} {room['Type']:<15} {room['Capacity']:<10} {room['Sessions']:<10} {room['Utilization Rate (%)']:<12} {room['Avg Duration (min)']:<12}\n"
                report_text += line

            # Summary statistics
            avg_utilization = sum(room['Utilization Rate (%)'] for room in room_data) / len(room_data)
            report_text += "\nRoom Utilization Summary:\n"
            report_text += f"  Total Rooms: {len(room_data)}\n"
            report_text += f"  Average Utilization: {avg_utilization:.2f}%\n"

            most_utilized = max(room_data, key=lambda x: x['Utilization Rate (%)'])
            least_utilized = min(room_data, key=lambda x: x['Utilization Rate (%)'])
            report_text += f"  Most Utilized: {most_utilized['Room']} ({most_utilized['Utilization Rate (%)']}%)\n"
            report_text += f"  Least Utilized: {least_utilized['Room']} ({least_utilized['Utilization Rate (%)']}%)\n"
            report_text += "\n"

        # Instructor Workload Report
        if workload_data:
            report_text += "\nINSTRUCTOR WORKLOAD REPORT\n"
            report_text += "-" * 100 + "\n"
            report_text += f"{'Instructor':<25} {'Department':<15} {'Sessions':<10} {'Hours':<8} {'Max':<8} {'Load %':<8} {'Status':<12}\n"
            report_text += "-" * 100 + "\n"

            for instructor in workload_data:
                line = f"{instructor['Instructor']:<25} {instructor['Department']:<15} {instructor['Sessions']:<10} {instructor['Total Hours']:<8} {instructor['Max Hours']:<8} {instructor['Workload (%)']:<8} {instructor['Status']:<12}\n"
                report_text += line

            # Overloaded instructors warning
            overloaded = [i for i in workload_data if i['Status'] == 'Overloaded']
            if overloaded:
                report_text += f"\n⚠️ WARNING: {len(overloaded)} instructor(s) are overloaded!\n"
                for instructor in overloaded:
                    report_text += f"  - {instructor['Instructor']}: {instructor['Workload (%)']}% workload\n"
            report_text += "\n"

        report_text += "=" * 100 + "\n"
        report_text += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        # Show report in window with email option
        self._show_report_with_email_option(
            "Comprehensive Module Scheduling Reports",
            report_text,
            "Management Reports"
        )

        # Automatically send email to admin
        try:
            admin_email = self._get_admin_email()

            # Render email from template
            from education_system.systems.university.infrastructure.email.email_service import send_email
            from education_system.systems.university.infrastructure.email.template_utils import render_template

            subject, email_body = render_template('academics/module_scheduling_comprehensive_reports', {
                'report_content': f"""Comprehensive Module Scheduling Reports

{'=' * 80}
{report_text}
{'=' * 80}

This email was automatically sent from the Module Scheduling GUI Management tab."""
            })

            # Fallback if template not found
            if not subject or not email_body:
                subject = "Module Scheduling - Comprehensive Reports"
                email_body = f"""Comprehensive Module Scheduling Reports

{'=' * 80}
{report_text}
{'=' * 80}

This email was automatically sent from the Module Scheduling GUI Management tab.
"""

            # Send email
            send_email(
                recipient_email=admin_email,
                subject=subject,
                body=email_body
            )

            messagebox.showinfo("Reports Generated & Emailed",
                              f"✅ Reports generated and automatically emailed to {admin_email}\n\n"
                              f"A detailed report window has also been opened for your review.", parent=self._safe_parent())

            self.update_activity_log(f"Generated comprehensive reports and emailed to {admin_email}")

        except Exception as email_error:
            print(f"Note: Could not auto-send email: {email_error}")
            messagebox.showinfo("Reports Generated",
                              "Reports generated successfully!\n\n"
                              "Note: Automatic email failed. You can send manually from the report window.", parent=self._safe_parent())
            self.update_activity_log("Generated comprehensive reports")

        self.update_status("Ready")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate reports: {str(e)}", parent=self._safe_parent())
        self.update_status("Ready")

ModuleSchedulingGUI.generate_reports = generate_reports

def quick_generate_report(self):
    """Quick generate report from dashboard"""
    self.notebook.select(5)  # Switch to analytics tab
    self.show_room_utilization()

ModuleSchedulingGUI.quick_generate_report = quick_generate_report

def _show_report_with_email_option(self, report_title, report_text, report_type="Report"):
    """Show report in a window with email send option"""
    # Create dialog window
    report_dialog = tk.Toplevel(self.root)
    report_dialog.title(report_title)
    report_dialog.geometry("1000x700")
    report_dialog.transient(self.root)

    # Main frame
    main_frame = ttk.Frame(report_dialog, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Report display
    ttk.Label(main_frame, text=report_title, font=('Arial', 14, 'bold')).pack(pady=(0, 10))

    report_display = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=('Courier', 10))
    report_display.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    report_display.insert('1.0', report_text)
    report_display.config(state='disabled')

    # Email section
    email_frame = ttk.LabelFrame(main_frame, text="Email Report to Admin", padding=10)
    email_frame.pack(fill=tk.X, pady=(10, 0))

    # Get admin email
    admin_email = self._get_admin_email()

    # Email input
    email_input_frame = ttk.Frame(email_frame)
    email_input_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(email_input_frame, text="Admin Email:").pack(side=tk.LEFT, padx=(0, 5))
    email_var = tk.StringVar(value=admin_email)
    email_entry = ttk.Entry(email_input_frame, textvariable=email_var, width=40)
    email_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

    def refresh_admin_email():
        """Refresh admin email from database"""
        try:
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT username, email FROM users WHERE LOWER(role) = 'admin' ORDER BY username")
                admins = cursor.fetchall()

            if admins:
                if len(admins) > 1:
                    # Show selection dialog
                    admin_select_dialog = tk.Toplevel(report_dialog)
                    admin_select_dialog.title("Select Admin")
                    admin_select_dialog.geometry("400x300")
                    admin_select_dialog.transient(report_dialog)
                    admin_select_dialog.grab_set()

                    ttk.Label(admin_select_dialog, text="Select Admin User:",
                             font=('Arial', 12, 'bold')).pack(pady=10)

                    admin_listbox = tk.Listbox(admin_select_dialog, height=10)
                    admin_listbox.pack(fill='both', expand=True, padx=20, pady=10)

                    for username, email in admins:
                        admin_listbox.insert(tk.END, f"{username} ({email})")

                    def select_admin():
                        selection = admin_listbox.curselection()
                        if selection:
                            selected_email = admins[selection[0]][1]
                            email_var.set(selected_email)
                        admin_select_dialog.destroy()

                    ttk.Button(admin_select_dialog, text="Select",
                              command=select_admin).pack(pady=10)
                else:
                    email_var.set(admins[0][1])
                    messagebox.showinfo("Admin Email", f"Using admin email: {admins[0][1]}", parent=self._safe_parent())
            else:
                messagebox.showwarning("No Admins", "No admin users found in database.", parent=self._safe_parent())
        except Exception as e:
            messagebox.showerror("Database Error", f"Could not fetch admin emails: {str(e)}", parent=self._safe_parent())

    ttk.Button(email_input_frame, text="🔄", command=refresh_admin_email, width=3).pack(side=tk.LEFT)

    # Send email function
    def send_report_email():
        try:
            recipient_email = email_var.get().strip()

            if not recipient_email or '@' not in recipient_email:
                messagebox.showwarning("Invalid Email", "Please enter a valid admin email address.", parent=self._safe_parent())
                return

            # Render email from template
            from education_system.systems.university.infrastructure.email.email_service import send_email
            from education_system.systems.university.infrastructure.email.template_utils import render_template

            subject, email_body = render_template('academics/module_scheduling_report', {
                'report_title': report_title,
                'report_content': f"""{report_title}

{'=' * 80}
{report_text}
{'=' * 80}

Report Type: {report_type}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This email was sent from the Module Scheduling GUI."""
            })

            # Fallback if template not found
            if not subject or not email_body:
                subject = f"Module Scheduling Report - {report_title}"
                email_body = f"""{report_title}

{'=' * 80}
{report_text}
{'=' * 80}

Report Type: {report_type}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This email was sent from the Module Scheduling GUI.
"""

            # Send email
            send_email(
                recipient_email=recipient_email,
                subject=subject,
                body=email_body
            )

            messagebox.showinfo("Email Sent",
                              f"✅ Report sent successfully to {recipient_email}\n\n"
                              f"Report: {report_title}", parent=self._safe_parent())
            self.update_activity_log(f"Emailed {report_type} report to {recipient_email}")

        except Exception as e:
            messagebox.showerror("Email Error",
                               f"Failed to send email: {str(e)}\n\n"
                               f"Please check email configuration.", parent=self._safe_parent())
            print(f"Email error: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(email_frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text="📧 Send Email",
              command=send_report_email).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Button(button_frame, text="❌ Close",
              command=report_dialog.destroy).pack(side=tk.LEFT)

ModuleSchedulingGUI._show_report_with_email_option = _show_report_with_email_option

