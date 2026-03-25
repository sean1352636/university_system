from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.academics.services.module_scheduling.constants import DAYS_OF_WEEK, TIME_SLOTS
import os
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch


class AnalyticsMixin:
    def generate_room_utilization_report(self, output_format='display'):
        """Generate comprehensive room utilization analytics"""
        with get_connection(self.db_path, row_factory=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
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
            print("No room data available.")
            conn.close()
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
                'Utilization Rate (%)': round(utilization_rate, 2),
                'Avg Duration (min)': round(avg_duration or 0, 2)
            })

        if output_format == 'display':
            self._display_room_analytics(analytics_data)
        elif output_format == 'pdf':
            return self._generate_analytics_pdf(analytics_data, 'Room Utilization Report')
        elif output_format == 'csv':
            return self._export_analytics_csv(analytics_data, 'room_utilization')

        return analytics_data

    def _display_room_analytics(self, data):
        """Display room analytics in console"""
        print("\nRoom Utilization Analytics")
        print("=" * 100)
        print(f"{'Room':<15} {'Type':<15} {'Capacity':<10} {'Sessions':<10} {'Utilization':<12} {'Avg Duration':<12}")
        print("-" * 100)

        for room in data:
            print(f"{room['Room']:<15} {room['Type']:<15} {room['Capacity']:<10} "
                  f"{room['Sessions']:<10} {room['Utilization Rate (%)']:<12} {room['Avg Duration (min)']:<12}")

        print("=" * 100)

        # Summary statistics
        if data:
            avg_utilization = sum(room['Utilization Rate (%)'] for room in data) / len(data)
            print(f"\nSummary:")
            print(f"Total Rooms: {len(data)}")
            print(f"Average Utilization: {avg_utilization:.2f}%")
            print(f"Most Utilized: {max(data, key=lambda x: x['Utilization Rate (%)'])['Room']}")
            print(f"Least Utilized: {min(data, key=lambda x: x['Utilization Rate (%)'])['Room']}")

    def generate_instructor_workload_report(self, output_format='display'):
        """Generate instructor workload analysis"""
        with get_connection(self.db_path, row_factory=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
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
                'Total Hours': round(total_hours, 2),
                'Max Hours': max_hours,
                'Workload (%)': round(workload_percentage, 2),
                'Status': 'Overloaded' if workload_percentage > 100 else 'Normal'
            })

        if output_format == 'display':
            self._display_workload_analytics(workload_data)
        elif output_format == 'pdf':
            return self._generate_analytics_pdf(workload_data, 'Instructor Workload Report')
        elif output_format == 'csv':
            return self._export_analytics_csv(workload_data, 'instructor_workload')

        return workload_data

    def _display_workload_analytics(self, data):
        """Display workload analytics in console"""
        print("\nInstructor Workload Analytics")
        print("=" * 120)
        print(f"{'Instructor':<25} {'Department':<15} {'Sessions':<10} {'Hours':<8} {'Max':<8} {'Load %':<8} {'Status':<12}")
        print("-" * 120)

        for instructor in data:
            print(f"{instructor['Instructor']:<25} {instructor['Department']:<15} "
                  f"{instructor['Sessions']:<10} {instructor['Total Hours']:<8} "
                  f"{instructor['Max Hours']:<8} {instructor['Workload (%)']:<8} {instructor['Status']:<12}")

        print("=" * 120)

        # Highlight overloaded instructors
        overloaded = [i for i in data if i['Status'] == 'Overloaded']
        if overloaded:
            print(f"\nWARNING: {len(overloaded)} instructor(s) are overloaded!")
            for instructor in overloaded:
                print(f"  - {instructor['Instructor']}: {instructor['Workload (%)']}% workload")

    def generate_scheduling_analytics_dashboard(self):
        """Generate comprehensive scheduling analytics dashboard"""
        print("\nScheduling Analytics Dashboard")
        print("=" * 60)

        # Peak usage analysis
        peak_times = self._analyze_peak_usage()
        print(f"\nPeak Usage Times:")
        for day, times in peak_times.items():
            print(f"  {day}: {', '.join(times)}")

        # Module distribution
        module_stats = self._analyze_module_distribution()
        print(f"\nModule Distribution:")
        print(f"  Total Modules Scheduled: {module_stats['total']}")
        print(f"  Most Common Session Type: {module_stats['most_common_type']}")
        print(f"  Average Sessions per Module: {module_stats['avg_sessions']:.2f}")

        # Room efficiency
        room_efficiency = self._analyze_room_efficiency()
        print(f"\nRoom Efficiency:")
        print(f"  Average Room Utilization: {room_efficiency['avg_utilization']:.2f}%")
        print(f"  Most Efficient Room Type: {room_efficiency['best_type']}")

        # Conflict summary
        conflicts = self._get_all_conflicts()
        print(f"\nConflict Summary:")
        print(f"  Active Conflicts: {len([c for c in conflicts if not c['resolved']])}")
        print(f"  Resolved Conflicts: {len([c for c in conflicts if c['resolved']])}")

    def _analyze_peak_usage(self):
        """Analyze peak usage times"""
        with get_connection(self.db_path, row_factory=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

        cursor.execute('''
        SELECT day_of_week, start_time, COUNT(*) as session_count
        FROM module_schedule
        GROUP BY day_of_week, start_time
        ORDER BY day_of_week, session_count DESC
        ''')

        usage_data = cursor.fetchall()

        peak_times = {}
        for day in DAYS_OF_WEEK:
            day_data = [row for row in usage_data if row[0] == day]
            if day_data:
                max_count = max(row[2] for row in day_data)
                peak_slots = [row[1] for row in day_data if row[2] == max_count]
                peak_times[day] = peak_slots[:3]  # Top 3 peak times
            else:
                peak_times[day] = []

        return peak_times

    def _analyze_module_distribution(self):
        """Analyze module scheduling distribution"""
        with get_connection(self.db_path, row_factory=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

        cursor.execute('SELECT COUNT(DISTINCT module_code) FROM module_schedule')
        total_modules = cursor.fetchone()[0]

        cursor.execute('''
        SELECT session_type, COUNT(*) as count
        FROM module_schedule
        GROUP BY session_type
        ORDER BY count DESC
        ''')
        session_types = cursor.fetchall()

        cursor.execute('''
        SELECT module_code, COUNT(*) as sessions
        FROM module_schedule
        GROUP BY module_code
        ''')
        module_sessions = cursor.fetchall()

        most_common_type = session_types[0][0] if session_types else "None"
        avg_sessions = sum(row[1] for row in module_sessions) / len(module_sessions) if module_sessions else 0

        return {
            'total': total_modules,
            'most_common_type': most_common_type,
            'avg_sessions': avg_sessions
        }

    def _analyze_room_efficiency(self):
        """Analyze room efficiency metrics"""
        room_data = self.generate_room_utilization_report(output_format='data')

        if not room_data:
            return {'avg_utilization': 0, 'best_type': 'None'}

        avg_utilization = sum(room['Utilization Rate (%)'] for room in room_data) / len(room_data)

        # Group by room type
        type_utilization = {}
        for room in room_data:
            room_type = room['Type']
            if room_type not in type_utilization:
                type_utilization[room_type] = []
            type_utilization[room_type].append(room['Utilization Rate (%)'])

        # Find best performing room type
        best_type = max(type_utilization.keys(),
                       key=lambda t: sum(type_utilization[t]) / len(type_utilization[t])) if type_utilization else 'None'

        return {
            'avg_utilization': avg_utilization,
            'best_type': best_type
        }

    def _export_analytics_csv(self, data, filename_prefix):
        """Export analytics data to CSV"""
        from education_system.university_system.modules.shared.constants import paths
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(str(paths.ANALYTICS_DIR), f"{filename_prefix}_{timestamp}.csv")

        # Ensure directory exists (already created via paths._ensure)
        os.makedirs(str(paths.ANALYTICS_DIR), exist_ok=True)

        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)

        print(f"Analytics exported to CSV: {filename}")
        return filename

    def _generate_analytics_pdf(self, data, title):
        """Generate analytics PDF report"""
        from education_system.university_system.modules.shared.constants import paths
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(str(paths.ANALYTICS_DIR), f"{title.lower().replace(' ', '_')}_{timestamp}.pdf")

        # Ensure directory exists (already created via paths._ensure)
        os.makedirs(str(paths.ANALYTICS_DIR), exist_ok=True)

        doc = SimpleDocTemplate(filename, pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        elements = []

        # Add title
        title_style = styles["Title"]
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 0.25*inch))

        # Add generation info
        info_text = f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        elements.append(Paragraph(info_text, styles["Normal"]))
        elements.append(Spacer(1, 0.25*inch))

        # Convert data to table format
        if data:
            headers = list(data[0].keys())
            table_data = [headers]

            for row in data:
                table_data.append([str(row[key]) for key in headers])

            # Create table
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            elements.append(table)

        # Build PDF
        doc.build(elements)
        print(f"Analytics PDF generated: {filename}")
        return filename
