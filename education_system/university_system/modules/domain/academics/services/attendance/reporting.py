"""Reporting and report generation for attendance tracking."""

import datetime
import pandas as pd
import matplotlib.pyplot as plt
from datetime import timedelta
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.academics.services.attendance.settings import get_setting
from education_system.university_system.modules.domain.academics.services.attendance.records import (
    get_student_attendance, get_module_attendance,
)


def generate_executive_summary_report(date_from=None, date_to=None, output_path=None):
    """Generate executive summary report"""
    try:
        conn = get_connection()

        # Date range
        if not date_from:
            date_from = (datetime.date.today() - timedelta(days=30)).isoformat()
        if not date_to:
            date_to = datetime.date.today().isoformat()

        # Overall statistics
        overall_query = '''
        SELECT
            COUNT(DISTINCT ar.student_id) as total_students,
            COUNT(DISTINCT ar.module_code) as total_modules,
            COUNT(*) as total_sessions,
            AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as overall_attendance_rate
        FROM attendance_records ar
        WHERE ar.date BETWEEN ? AND ?
        '''

        overall_stats = pd.read_sql_query(overall_query, conn, params=[date_from, date_to])

        # Attendance trends by week
        trends_query = '''
        SELECT
            strftime('%Y-W%W', ar.date) as week,
            AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as rate
        FROM attendance_records ar
        WHERE ar.date BETWEEN ? AND ?
        GROUP BY strftime('%Y-W%W', ar.date)
        ORDER BY week
        '''

        trends_df = pd.read_sql_query(trends_query, conn, params=[date_from, date_to])

        # Top performing modules
        module_performance_query = '''
        SELECT
            ar.module_code,
            COALESCE(m.module_name, ar.module_code) as module_name,
            AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as attendance_rate,
            COUNT(*) as total_sessions
        FROM attendance_records ar
        LEFT JOIN modules m ON ar.module_code = m.module_code
        WHERE ar.date BETWEEN ? AND ?
        GROUP BY ar.module_code
        ORDER BY attendance_rate DESC
        LIMIT 10
        '''

        module_performance_df = pd.read_sql_query(module_performance_query, conn, params=[date_from, date_to])

        # At-risk students
        at_risk_query = '''
        SELECT
            ar.student_id,
            s.first_name || ' ' || s.last_name as student_name,
            AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as attendance_rate,
            COUNT(*) as sessions_count
        FROM attendance_records ar
        JOIN students s ON ar.student_id = s.student_id
        WHERE ar.date BETWEEN ? AND ?
        GROUP BY ar.student_id, s.first_name, s.last_name
        HAVING AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) < 0.75
        ORDER BY attendance_rate ASC
        '''

        at_risk_df = pd.read_sql_query(at_risk_query, conn, params=[date_from, date_to])

        # Generate visualizations
        plt.style.use('seaborn-v0_8' if 'seaborn-v0_8' in plt.style.available else 'default')
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

        # Attendance trends
        if not trends_df.empty:
            ax1.plot(trends_df['week'], trends_df['rate'], marker='o', linewidth=2)
            ax1.set_title('Weekly Attendance Trends', fontsize=14, fontweight='bold')
            ax1.set_xlabel('Week')
            ax1.set_ylabel('Attendance Rate (%)')
            ax1.grid(True, alpha=0.3)
            ax1.set_ylim(0, 100)

            # Add threshold lines
            threshold_warning = int(get_setting('attendance_threshold_warning') or 80)
            threshold_critical = int(get_setting('attendance_threshold_critical') or 70)
            ax1.axhline(y=threshold_warning, color='orange', linestyle='--', alpha=0.7, label='Warning Threshold')
            ax1.axhline(y=threshold_critical, color='red', linestyle='--', alpha=0.7, label='Critical Threshold')
            ax1.legend()

        # Module performance
        if not module_performance_df.empty and len(module_performance_df) > 0:
            top_modules = module_performance_df.head(8)
            bars = ax2.barh(range(len(top_modules)), top_modules['attendance_rate'],
                           color=plt.cm.RdYlGn(top_modules['attendance_rate']/100))
            ax2.set_yticks(range(len(top_modules)))
            ax2.set_yticklabels(top_modules['module_code'], fontsize=10)
            ax2.set_title('Top Performing Modules', fontsize=14, fontweight='bold')
            ax2.set_xlabel('Attendance Rate (%)')

            # Add percentage labels
            for i, (bar, rate) in enumerate(zip(bars, top_modules['attendance_rate'])):
                ax2.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
                        f'{rate:.1f}%', va='center', fontsize=9)

        # Status distribution
        status_query = '''
        SELECT status, COUNT(*) as count
        FROM attendance_records
        WHERE date BETWEEN ? AND ?
        GROUP BY status
        '''

        status_df = pd.read_sql_query(status_query, conn, params=[date_from, date_to])

        if not status_df.empty:
            status_colors = {'Present': 'green', 'Late': 'yellow', 'Excused': 'blue', 'Absent': 'red'}
            pie_colors = [status_colors.get(status, 'gray') for status in status_df['status']]

            wedges, texts, autotexts = ax3.pie(status_df['count'], labels=status_df['status'],
                                              autopct='%1.1f%%', colors=pie_colors, startangle=90)
            ax3.set_title('Attendance Status Distribution', fontsize=14, fontweight='bold')

        # At-risk students count by attendance range
        if not at_risk_df.empty:
            bins = [0, 50, 60, 70, 75, 80, 100]
            labels = ['<50%', '50-60%', '60-70%', '70-75%', '75-80%', '80%+']
            at_risk_df['range'] = pd.cut(at_risk_df['attendance_rate'], bins=bins, labels=labels, right=False)
            range_counts = at_risk_df['range'].value_counts().reindex(labels, fill_value=0)

            ax4.bar(range(len(range_counts)), range_counts.values,
                   color=['red', 'orange', 'yellow', 'lightgreen', 'green', 'darkgreen'])
            ax4.set_xticks(range(len(range_counts)))
            ax4.set_xticklabels(range_counts.index, rotation=45)
            ax4.set_title('Students by Attendance Range', fontsize=14, fontweight='bold')
            ax4.set_ylabel('Number of Students')

        plt.tight_layout()

        # Save visualization
        viz_filename = f"executive_summary_viz_{datetime.date.today().strftime('%Y%m%d')}.png"
        plt.savefig(viz_filename, dpi=300, bbox_inches='tight')
        plt.close()

        # Generate PDF report
        if not output_path:
            output_path = f"executive_summary_{datetime.date.today().strftime('%Y%m%d')}.pdf"

        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Title
        title = Paragraph("Executive Attendance Summary Report", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 20))

        # Report period
        period_text = f"Report Period: {date_from} to {date_to}"
        period_para = Paragraph(period_text, styles['Normal'])
        elements.append(period_para)
        elements.append(Spacer(1, 20))

        # Key metrics
        elements.append(Paragraph("Key Metrics", styles['Heading2']))

        if not overall_stats.empty:
            metrics_data = [
                ['Total Students', f"{overall_stats['total_students'].iloc[0]:,}"],
                ['Total Modules', f"{overall_stats['total_modules'].iloc[0]:,}"],
                ['Total Sessions', f"{overall_stats['total_sessions'].iloc[0]:,}"],
                ['Overall Attendance Rate', f"{overall_stats['overall_attendance_rate'].iloc[0]:.1f}%"],
            ]

            metrics_table = Table(metrics_data, colWidths=[200, 150])
            metrics_table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
            ]))

            elements.append(metrics_table)
            elements.append(Spacer(1, 20))

        # Top performing modules
        if not module_performance_df.empty:
            elements.append(Paragraph("Top Performing Modules", styles['Heading2']))

            module_data = [['Module Code', 'Module Name', 'Attendance Rate', 'Sessions']]
            for _, row in module_performance_df.head(10).iterrows():
                module_data.append([
                    row['module_code'],
                    row['module_name'][:40] + '...' if len(str(row['module_name'])) > 40 else str(row['module_name']),
                    f"{row['attendance_rate']:.1f}%",
                    str(row['total_sessions'])
                ])

            module_table = Table(module_data, colWidths=[80, 200, 80, 60])
            module_table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
            ]))

            elements.append(module_table)
            elements.append(Spacer(1, 20))

        # At-risk students summary
        if not at_risk_df.empty:
            elements.append(Paragraph("Students Requiring Attention", styles['Heading2']))

            risk_summary_text = f"Number of students with attendance below 75%: {len(at_risk_df)}"
            elements.append(Paragraph(risk_summary_text, styles['Normal']))
            elements.append(Spacer(1, 10))

            if len(at_risk_df) > 0:
                at_risk_data = [['Student ID', 'Student Name', 'Attendance Rate', 'Sessions']]
                for _, row in at_risk_df.head(15).iterrows():
                    at_risk_data.append([
                        row['student_id'],
                        row['student_name'][:30] + '...' if len(row['student_name']) > 30 else row['student_name'],
                        f"{row['attendance_rate']:.1f}%",
                        str(row['sessions_count'])
                    ])

                at_risk_table = Table(at_risk_data, colWidths=[80, 180, 80, 60])
                at_risk_table.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                ]))

                elements.append(at_risk_table)
                elements.append(Spacer(1, 20))

        # Add visualization image
        try:
            from reportlab.platypus import Image
            img = Image(viz_filename, width=500, height=375)
            elements.append(img)
        except Exception:
            pass  # Skip if image can't be added

        # Build PDF
        doc.build(elements)

        conn.close()
        print(f"Executive summary report generated: {output_path}")
        return True

    except Exception as e:
        print(f"Error generating executive summary: {e}")
        return False


def generate_student_attendance_report(student_id, output_format='screen', output_path=None):
    """Generate attendance report for a student"""
    try:
        stats = get_student_attendance(student_id)

        if not stats:
            print(f"No attendance data found for student {student_id}")
            return False

        # Get student info
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT first_name, last_name, email_address FROM students
        WHERE student_id = ?
        ''', (student_id,))

        student_info = cursor.fetchone()
        conn.close()

        if not student_info:
            print(f"Student {student_id} not found")
            return False

        first_name, last_name, email = student_info

        if output_format == 'screen':
            print(f"\n📊 ATTENDANCE REPORT: {first_name} {last_name} ({student_id})")
            print("=" * 60)

            for module_code, data in stats.items():
                print(f"\nModule: {module_code}")
                print(f"Total Sessions: {data['total_sessions']}")
                print(f"Attended: {data['attended']}")
                print(f"Attendance Rate: {data['percentage']:.1f}%")

            overall_rate = sum(data['percentage'] for data in stats.values()) / len(stats)
            print(f"\nOverall Attendance Rate: {overall_rate:.1f}%")

        elif output_format == 'csv':
            if not output_path:
                output_path = f"student_report_{student_id}_{datetime.date.today().strftime('%Y%m%d')}.csv"

            data_rows = []
            for module_code, data in stats.items():
                data_rows.append({
                    'Student ID': student_id,
                    'Name': f"{first_name} {last_name}",
                    'Module': module_code,
                    'Total Sessions': data['total_sessions'],
                    'Attended': data['attended'],
                    'Attendance Rate': f"{data['percentage']:.1f}%"
                })

            df = pd.DataFrame(data_rows)
            df.to_csv(output_path, index=False)
            print(f"✅ Report saved to: {output_path}")

        return True

    except Exception as e:
        print(f"Error generating student report: {e}")
        return False


def generate_module_attendance_report(module_code, date_from=None, date_to=None, output_format='screen', output_path=None):
    """Generate attendance report for a module"""
    try:
        stats = get_module_attendance(module_code)

        if not stats['students']:
            print(f"No attendance data found for module {module_code}")
            return False

        if output_format == 'screen':
            print(f"\n📊 MODULE ATTENDANCE REPORT: {module_code}")
            print("=" * 60)
            print(f"Total Students: {stats['total_students']}")
            print(f"Total Sessions: {stats['total_sessions']}")
            print(f"Overall Attendance Rate: {stats['overall_percentage']:.1f}%")

            print(f"\n{'Student ID':<12} {'Name':<25} {'Sessions':<10} {'Attended':<10} {'Rate'}")
            print("-" * 70)

            for student in stats['students']:
                print(f"{student['student_id']:<12} {student['name']:<25} {student['sessions']:<10} "
                      f"{student['attended']:<10} {student['percentage']:.1f}%")

        elif output_format == 'csv':
            if not output_path:
                output_path = f"module_report_{module_code}_{datetime.date.today().strftime('%Y%m%d')}.csv"

            df = pd.DataFrame(stats['students'])
            df.to_csv(output_path, index=False)
            print(f"✅ Report saved to: {output_path}")

        return True

    except Exception as e:
        print(f"Error generating module report: {e}")
        return False
