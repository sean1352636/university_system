import csv
import os
import logging
from datetime import datetime, timedelta

from education_system.university_system.modules.domain.housing.services.accommodation._common import (
    sqlite3, DB_PATH, pd, canvas, get_auth, get_text,
)

# Conditional reportlab imports
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
except ImportError:
    pass

from education_system.university_system.modules.domain.housing.services.accommodation.db import init_accommodation_db


def show_dashboard_metrics():
    """Display summary metrics for dashboard with improved visualizations."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_dashboard", "You must be logged in to view dashboard metrics."))
        return

    if not auth.check_permission('view_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_dashboard", "You don't have permission to view dashboard metrics."))
        return

    init_accommodation_db()
    try:
        # Current date for active/expired calculations
        today = datetime.now().strftime('%Y-%m-%d')

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get counts by accommodation type
            cursor.execute('''
                SELECT accommodation_type, COUNT(*) as count
                FROM accommodations
                GROUP BY accommodation_type
                ORDER BY count DESC
            ''')
            by_type = cursor.fetchall()

            # Get counts by status
            cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM accommodations
                GROUP BY status
                ORDER BY count DESC
            ''')
            by_status = cursor.fetchall()

            # Count recently added accommodations (last 30 days)
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE created_at >= ?
            ''', (thirty_days_ago,))
            recent_count = cursor.fetchone()[0]

            # Count active accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE (end_date >= ? OR end_date IS NULL) AND status = 'active'
            ''', (today,))
            active_count = cursor.fetchone()[0]

            # Count expired accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE (end_date < ? OR status = 'expired')
            ''', (today,))
            expired_count = cursor.fetchone()[0]

            # Count pending accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE status = 'pending'
            ''')
            pending_count = cursor.fetchone()[0]

            # Count expiring soon (next 30 days)
            thirty_days_future = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE end_date BETWEEN ? AND ? AND status = 'active'
            ''', (today, thirty_days_future))
            expiring_soon = cursor.fetchone()[0]

            # Get total count
            cursor.execute('SELECT COUNT(*) FROM accommodations')
            total = cursor.fetchone()[0]

        # Display dashboard metrics
        print("\n" + "="*50)
        print(" "*15 + "ACCOMMODATION DASHBOARD")
        print("="*50)

        print("\nOVERVIEW:")
        print(f"Total Records: {total}")
        print(f"Active: {active_count} ({(active_count/total*100) if total > 0 else 0:.1f}%)")
        print(f"Expired: {expired_count} ({(expired_count/total*100) if total > 0 else 0:.1f}%)")
        print(f"Pending Approval: {pending_count} ({(pending_count/total*100) if total > 0 else 0:.1f}%)")
        print(f"Added in Last 30 Days: {recent_count}")
        print(f"Expiring in Next 30 Days: {expiring_soon}")

        print("\nBREAKDOWN BY TYPE:")
        print("-"*50)
        print(f"{'Type':<25} {'Count':<10} {'Percentage':<15}")
        print("-"*50)

        for type_row in by_type:
            type_name = type_row['accommodation_type']
            count = type_row['count']
            percent = (count/total*100) if total > 0 else 0

            # Create simple bar chart
            bar_length = int(percent / 2)  # Scale to max 50 chars
            bar = '\u2588' * bar_length

            print(f"{type_name[:25]:<25} {count:<10} {percent:.1f}% {bar}")

        print("\nBREAKDOWN BY STATUS:")
        print("-"*50)
        print(f"{'Status':<15} {'Count':<10} {'Percentage':<15}")
        print("-"*50)

        for status_row in by_status:
            status_name = status_row['status']
            count = status_row['count']
            percent = (count/total*100) if total > 0 else 0

            # Create simple bar chart
            bar_length = int(percent / 2)  # Scale to max 50 chars
            bar = '\u2588' * bar_length

            print(f"{status_name[:15]:<15} {count:<10} {percent:.1f}% {bar}")

        print("="*50)

        # Offer to generate PDF report
        generate_report = input("\n" + get_text("housing.accommodation.input.generate_pdf_report", "Would you like to generate a PDF report of these metrics? (y/n): ")).lower()
        if generate_report == 'y':
            export_dashboard_report()

    except Exception as e:
        logging.error(f"Error showing dashboard metrics: {e}")
        print(get_text("housing.accommodation.error.displaying_dashboard", "Error displaying dashboard metrics: {error}").format(error=e))


def export_dashboard_report():
    """Generate a PDF report of dashboard metrics."""
    try:
        # Check for reportlab
        if not canvas:
            print(get_text("housing.accommodation.error.reportlab_not_installed", "Error: reportlab module not installed. Cannot export to PDF."))
            return

        # Get save location
        filename = f"accommodation_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
        if path:
            full_path = os.path.join(path, filename)
        else:
            full_path = filename

        # Ensure directory exists
        directory = os.path.dirname(full_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        # Current date for active/expired calculations
        today = datetime.now().strftime('%Y-%m-%d')

        # Get data
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get counts by accommodation type
            cursor.execute('''
                SELECT accommodation_type, COUNT(*) as count
                FROM accommodations
                GROUP BY accommodation_type
                ORDER BY count DESC
            ''')
            by_type = cursor.fetchall()

            # Get counts by status
            cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM accommodations
                GROUP BY status
                ORDER BY count DESC
            ''')
            by_status = cursor.fetchall()

            # Count recently added accommodations (last 30 days)
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE created_at >= ?
            ''', (thirty_days_ago,))
            recent_count = cursor.fetchone()[0]

            # Count active accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE (end_date >= ? OR end_date IS NULL) AND status = 'active'
            ''', (today,))
            active_count = cursor.fetchone()[0]

            # Count expired accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE (end_date < ? OR status = 'expired')
            ''', (today,))
            expired_count = cursor.fetchone()[0]

            # Count pending accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE status = 'pending'
            ''')
            pending_count = cursor.fetchone()[0]

            # Count expiring soon (next 30 days)
            thirty_days_future = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE end_date BETWEEN ? AND ? AND status = 'active'
            ''', (today, thirty_days_future))
            expiring_soon = cursor.fetchone()[0]

            # Get total count
            cursor.execute('SELECT COUNT(*) FROM accommodations')
            total = cursor.fetchone()[0]

        # Create PDF document
        doc = SimpleDocTemplate(full_path, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Add title
        title = Paragraph("Accommodation Dashboard Report", styles['Title'])
        elements.append(title)

        # Add timestamp
        timestamp = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
        elements.append(timestamp)
        elements.append(Paragraph("<br/>", styles['Normal']))

        # Add overview
        elements.append(Paragraph("Overview", styles['Heading2']))
        overview_data = [
            ['Metric', 'Count', 'Percentage'],
            ['Total Records', str(total), '100%'],
            ['Active', str(active_count), f"{(active_count/total*100) if total > 0 else 0:.1f}%"],
            ['Expired', str(expired_count), f"{(expired_count/total*100) if total > 0 else 0:.1f}%"],
            ['Pending Approval', str(pending_count), f"{(pending_count/total*100) if total > 0 else 0:.1f}%"],
            ['Added in Last 30 Days', str(recent_count), f"{(recent_count/total*100) if total > 0 else 0:.1f}%"],
            ['Expiring in Next 30 Days', str(expiring_soon), f"{(expiring_soon/total*100) if total > 0 else 0:.1f}%"]
        ]

        overview_table = Table(overview_data, colWidths=[200, 100, 100])
        overview_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        elements.append(overview_table)
        elements.append(Paragraph("<br/><br/>", styles['Normal']))

        # Add type breakdown
        elements.append(Paragraph("Breakdown by Accommodation Type", styles['Heading2']))
        type_data = [['Type', 'Count', 'Percentage']]

        for type_row in by_type:
            type_name = type_row['accommodation_type']
            count = type_row['count']
            percent = (count/total*100) if total > 0 else 0
            type_data.append([type_name, str(count), f"{percent:.1f}%"])

        type_table = Table(type_data, colWidths=[200, 100, 100])
        type_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        elements.append(type_table)
        elements.append(Paragraph("<br/><br/>", styles['Normal']))

        # Add status breakdown
        elements.append(Paragraph("Breakdown by Status", styles['Heading2']))
        status_data = [['Status', 'Count', 'Percentage']]

        for status_row in by_status:
            status_name = status_row['status']
            count = status_row['count']
            percent = (count/total*100) if total > 0 else 0
            status_data.append([status_name, str(count), f"{percent:.1f}%"])

        status_table = Table(status_data, colWidths=[200, 100, 100])
        status_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        elements.append(status_table)

        # Build the PDF
        doc.build(elements)
        print(get_text("housing.accommodation.success.dashboard_exported", "Dashboard report exported to {path}").format(path=full_path))

    except Exception as e:
        logging.error(f"Error exporting dashboard report: {e}")
        print(get_text("housing.accommodation.error.exporting_dashboard", "Error exporting dashboard report: {error}").format(error=e))


def generate_statistics_report():
    """Generate detailed statistics about accommodations."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_reports", "You must be logged in to generate reports."))
        return

    if not auth.check_permission('view_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_reports", "You don't have permission to generate reports."))
        return

    init_accommodation_db()
    try:
        print("\n" + get_text("housing.accommodation.message.generating_statistics", "Generating Accommodation Statistics Report..."))

        # Current date for calculations
        today = datetime.now().strftime('%Y-%m-%d')
        current_year = datetime.now().year

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Total accommodations
            cursor.execute('SELECT COUNT(*) FROM accommodations')
            total_count = cursor.fetchone()[0]

            # Active accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE (end_date >= ? OR end_date IS NULL) AND status = 'active'
            ''', (today,))
            active_count = cursor.fetchone()[0]

            # Monthly trends for the current year
            cursor.execute('''
                SELECT strftime('%m', created_at) as month, COUNT(*) as count
                FROM accommodations
                WHERE created_at LIKE ?
                GROUP BY month
                ORDER BY month
            ''', (f"{current_year}%",))

            monthly_data = cursor.fetchall()

            # Number of students with multiple accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM (
                    SELECT student_id
                    FROM accommodations
                    WHERE status = 'active'
                    GROUP BY student_id
                    HAVING COUNT(*) > 1
                )
            ''')
            multiple_acc_count = cursor.fetchone()[0]

            # Course distribution of accommodations
            cursor.execute('''
                SELECT s.course, COUNT(*) as count
                FROM accommodations a
                JOIN students s ON a.student_id = s.student_id
                WHERE a.status = 'active'
                GROUP BY s.course
                ORDER BY count DESC
            ''')

            course_distribution = cursor.fetchall()

            # Average duration of accommodations
            cursor.execute('''
                SELECT AVG(julianday(end_date) - julianday(start_date)) as avg_days
                FROM accommodations
                WHERE start_date IS NOT NULL AND end_date IS NOT NULL
            ''')

            avg_duration = cursor.fetchone()['avg_days'] or 0

            # Approval rate for accommodations that require approval
            cursor.execute('''
                SELECT
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as approved
                FROM accommodations
                WHERE status IN ('active', 'rejected')
            ''')

            approval_data = cursor.fetchone()
            total_requests = approval_data['total_requests']
            approved = approval_data['approved']
            approval_rate = (approved / total_requests * 100) if total_requests > 0 else 0

        # Display the statistics
        print("\n" + "="*60)
        print(" "*15 + "ACCOMMODATION STATISTICS")
        print("="*60)

        print(f"\nTotal accommodations: {total_count}")
        print(f"Currently active: {active_count} ({(active_count/total_count*100) if total_count > 0 else 0:.1f}%)")
        print(f"Students with multiple accommodations: {multiple_acc_count}")
        print(f"Average accommodation duration: {avg_duration:.1f} days")
        print(f"Approval rate: {approval_rate:.1f}%")

        print("\nCourse Distribution:")
        for course in course_distribution:
            course_name = course['course'] or 'Unknown'
            count = course['count']
            percent = (count/active_count*100) if active_count > 0 else 0
            print(f" - {course_name}: {count} ({percent:.1f}%)")

        # Show monthly trends
        print("\nMonthly Trends for Current Year:")
        month_names = {
            '01': 'January', '02': 'February', '03': 'March', '04': 'April',
            '05': 'May', '06': 'June', '07': 'July', '08': 'August',
            '09': 'September', '10': 'October', '11': 'November', '12': 'December'
        }

        max_count = max([row['count'] for row in monthly_data]) if monthly_data else 0

        for month_data in monthly_data:
            month = month_data['month']
            count = month_data['count']
            month_name = month_names.get(month, month)

            # Generate simple bar chart
            bar_width = 40  # characters
            bar_length = int((count / max_count) * bar_width) if max_count > 0 else 0
            bar = '\u2588' * bar_length

            print(f"{month_name:10} ({count:3}): {bar}")

        print("="*60)

        # Ask to export the report
        export = input("\n" + get_text("housing.accommodation.input.export_report", "Would you like to export this report to a file? (y/n): ")).lower()
        if export == 'y':
            export_statistics_report(total_count, active_count, multiple_acc_count,
                                   avg_duration, approval_rate, course_distribution,
                                   monthly_data, month_names)

    except Exception as e:
        logging.error(f"Error generating statistics report: {e}")
        print(get_text("housing.accommodation.error.generating_statistics", "Error generating statistics report: {error}").format(error=e))


def export_statistics_report(total_count, active_count, multiple_acc_count,
                           avg_duration, approval_rate, course_distribution,
                           monthly_data, month_names):
    """Export the statistics report to a file."""
    try:
        # Ask for export format
        print("\n" + get_text("housing.accommodation.export.format", "Export format:"))
        print("1. CSV")
        print("2. PDF")
        print("3. TXT")

        format_choice = input(get_text("housing.accommodation.input.select_format", "Select format (1-3): ")).strip()

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename_base = f"accommodation_statistics_{timestamp}"

        if format_choice == '1':  # CSV
            filename = filename_base + ".csv"

            # Get save location
            path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
            if path:
                full_path = os.path.join(path, filename)
            else:
                full_path = filename

            # Ensure directory exists
            directory = os.path.dirname(full_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)

            # Write to CSV
            with open(full_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                # Write summary
                writer.writerow(['Accommodation Statistics Report', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                writer.writerow([])
                writer.writerow(['Metric', 'Value'])
                writer.writerow(['Total Accommodations', total_count])
                writer.writerow(['Active Accommodations', active_count])
                writer.writerow(['Active Percentage', f"{(active_count/total_count*100) if total_count > 0 else 0:.1f}%"])
                writer.writerow(['Students with Multiple Accommodations', multiple_acc_count])
                writer.writerow(['Average Duration (days)', f"{avg_duration:.1f}"])
                writer.writerow(['Approval Rate', f"{approval_rate:.1f}%"])
                writer.writerow([])

                # Write course distribution
                writer.writerow(['Course Distribution'])
                writer.writerow(['Course', 'Count', 'Percentage'])
                for course in course_distribution:
                    course_name = course['course'] or 'Unknown'
                    count = course['count']
                    percent = (count/active_count*100) if active_count > 0 else 0
                    writer.writerow([course_name, count, f"{percent:.1f}%"])
                writer.writerow([])

                # Write monthly trends
                writer.writerow(['Monthly Trends'])
                writer.writerow(['Month', 'Count'])
                for month_data in monthly_data:
                    month = month_data['month']
                    count = month_data['count']
                    month_name = month_names.get(month, month)
                    writer.writerow([month_name, count])

            print(get_text("housing.accommodation.success.statistics_exported", "Statistics exported to {path}").format(path=full_path))

        elif format_choice == '2':  # PDF
            if not canvas:
                print(get_text("housing.accommodation.error.reportlab_not_installed", "Error: reportlab module not installed. Cannot export to PDF."))
                return

            filename = filename_base + ".pdf"

            # Get save location
            path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
            if path:
                full_path = os.path.join(path, filename)
            else:
                full_path = filename

            # Ensure directory exists
            directory = os.path.dirname(full_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)

            # Create PDF document
            doc = SimpleDocTemplate(full_path, pagesize=letter)
            styles = getSampleStyleSheet()
            elements = []

            # Add title
            title = Paragraph("Accommodation Statistics Report", styles['Title'])
            elements.append(title)

            # Add timestamp
            timestamp = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
            elements.append(timestamp)
            elements.append(Paragraph("<br/>", styles['Normal']))

            # Add summary
            elements.append(Paragraph("Summary", styles['Heading2']))
            summary_data = [
                ['Metric', 'Value'],
                ['Total Accommodations', str(total_count)],
                ['Active Accommodations', str(active_count)],
                ['Active Percentage', f"{(active_count/total_count*100) if total_count > 0 else 0:.1f}%"],
                ['Students with Multiple Accommodations', str(multiple_acc_count)],
                ['Average Duration (days)', f"{avg_duration:.1f}"],
                ['Approval Rate', f"{approval_rate:.1f}%"]
            ]

            summary_table = Table(summary_data, colWidths=[300, 100])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            elements.append(summary_table)
            elements.append(Paragraph("<br/><br/>", styles['Normal']))

            # Add course distribution
            elements.append(Paragraph("Course Distribution", styles['Heading2']))
            course_data = [['Course', 'Count', 'Percentage']]

            for course in course_distribution:
                course_name = course['course'] or 'Unknown'
                count = course['count']
                percent = (count/active_count*100) if active_count > 0 else 0
                course_data.append([course_name, str(count), f"{percent:.1f}%"])

            course_table = Table(course_data, colWidths=[200, 100, 100])
            course_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            elements.append(course_table)
            elements.append(Paragraph("<br/><br/>", styles['Normal']))

            # Add monthly trends
            elements.append(Paragraph("Monthly Trends", styles['Heading2']))
            month_table_data = [['Month', 'Count']]

            for month_info in monthly_data:
                month = month_info['month']
                count = month_info['count']
                month_name = month_names.get(month, month)
                month_table_data.append([month_name, str(count)])

            month_table = Table(month_table_data, colWidths=[200, 100])
            month_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            elements.append(month_table)

            # Build the PDF
            doc.build(elements)
            print(get_text("housing.accommodation.success.statistics_exported", "Statistics exported to {path}").format(path=full_path))

        elif format_choice == '3':  # TXT
            filename = filename_base + ".txt"

            # Get save location
            path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
            if path:
                full_path = os.path.join(path, filename)
            else:
                full_path = filename

            # Ensure directory exists
            directory = os.path.dirname(full_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)

            # Write to text file
            with open(full_path, 'w') as txtfile:
                txtfile.write("ACCOMMODATION STATISTICS REPORT\n")
                txtfile.write("="*60 + "\n\n")
                txtfile.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                txtfile.write("SUMMARY:\n")
                txtfile.write("-"*60 + "\n")
                txtfile.write(f"Total accommodations: {total_count}\n")
                txtfile.write(f"Currently active: {active_count} ({(active_count/total_count*100) if total_count > 0 else 0:.1f}%)\n")
                txtfile.write(f"Students with multiple accommodations: {multiple_acc_count}\n")
                txtfile.write(f"Average accommodation duration: {avg_duration:.1f} days\n")
                txtfile.write(f"Approval rate: {approval_rate:.1f}%\n\n")

                txtfile.write("COURSE DISTRIBUTION:\n")
                txtfile.write("-"*60 + "\n")
                for course in course_distribution:
                    course_name = course['course'] or 'Unknown'
                    count = course['count']
                    percent = (count/active_count*100) if active_count > 0 else 0
                    txtfile.write(f"{course_name}: {count} ({percent:.1f}%)\n")

                txtfile.write("\nMONTHLY TRENDS:\n")
                txtfile.write("-"*60 + "\n")
                for month_data in monthly_data:
                    month = month_data['month']
                    count = month_data['count']
                    month_name = month_names.get(month, month)
                    txtfile.write(f"{month_name}: {count}\n")

            print(get_text("housing.accommodation.success.statistics_exported", "Statistics exported to {path}").format(path=full_path))

        else:
            print(get_text("housing.accommodation.error.invalid_format_selection", "Invalid format selection."))

    except Exception as e:
        logging.error(f"Error exporting statistics report: {e}")
        print(get_text("housing.accommodation.error.exporting_statistics", "Error exporting statistics report: {error}").format(error=e))
