import os
import csv
import logging
from datetime import datetime
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.infrastructure.i18n import get_text
from education_system.systems.university.infrastructure.logging.log_config import configure_logging
from education_system.systems.university.domain.operations.campus.mobility.services.parking_management.constants import PARKING_ZONES, PERMIT_TYPES
from education_system.systems.university.domain.operations.campus.mobility.services.parking_management.permits import display_permit_details
from education_system.systems.university.domain.operations.campus.mobility.services.parking_management.violations import display_violation_details
from education_system.systems.university.domain.operations.campus.mobility.services.parking_management.helpers import get_file_path
from education_system.systems.university.domain.operations.campus.mobility.services.parking_management import core

_t = get_text
logger = configure_logging(name=__name__)


def generate_permit_report():
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    auth = core.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return

    if not auth.check_permission('generate_reports'):
        print(_t("parking.auth.no_permission"))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n" + _t("parking.section.permit_status_report") + ":")
        print("1. " + _t("parking.menu.active_permits"))
        print("2. " + _t("parking.menu.expired_permits"))
        print("3. " + _t("parking.menu.permits_by_zone"))
        print("4. " + _t("parking.menu.permits_by_type"))
        print("5. " + _t("parking.menu.all_permits"))

        choice = input("Enter your choice (1-5): ")

        report_title = ""
        query = ""
        params = ()

        if choice == '1':
            report_title = "Active Permits Report"
            query = '''
            SELECT p.*, v.license_plate, v.make, v.model
            FROM parking_permits p
            LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
            WHERE p.active_status = 'Active' AND p.end_date >= date('now')
            ORDER BY p.zone, p.end_date
            '''
        elif choice == '2':
            report_title = "Expired Permits Report"
            query = '''
            SELECT p.*, v.license_plate, v.make, v.model
            FROM parking_permits p
            LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
            WHERE p.end_date < date('now')
            ORDER BY p.end_date DESC
            '''
        elif choice == '3':
            report_title = "Permits by Zone Report"
            zone = input("Enter zone code (leave blank for all zones): ").upper()

            if zone:
                if zone not in PARKING_ZONES:
                    print(f"Invalid zone code. Please enter one of: {', '.join(PARKING_ZONES.keys())}")
                    conn.close()
                    return

                report_title = f"Permits for Zone {zone} Report"
                query = '''
                SELECT p.*, v.license_plate, v.make, v.model
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE p.zone = ?
                ORDER BY p.issue_date DESC
                '''
                params = (zone,)
            else:
                query = '''
                SELECT p.*, v.license_plate, v.make, v.model
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                ORDER BY p.zone, p.issue_date DESC
                '''
        elif choice == '4':
            report_title = "Permits by Type Report"
            print(_t("parking.permit.types_available") + ":", ", ".join(PERMIT_TYPES))
            permit_type = input("Enter permit type (leave blank for all types): ")

            if permit_type:
                if permit_type not in PERMIT_TYPES:
                    print(f"Invalid permit type. Please choose from {', '.join(PERMIT_TYPES)}")
                    conn.close()
                    return

                report_title = f"{permit_type} Permits Report"
                query = '''
                SELECT p.*, v.license_plate, v.make, v.model
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE p.permit_type = ?
                ORDER BY p.issue_date DESC
                '''
                params = (permit_type,)
            else:
                query = '''
                SELECT p.*, v.license_plate, v.make, v.model
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                ORDER BY p.permit_type, p.issue_date DESC
                '''
        elif choice == '5':
            report_title = "All Permits Report"
            query = '''
            SELECT p.*, v.license_plate, v.make, v.model
            FROM parking_permits p
            LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
            ORDER BY p.issue_date DESC
            '''
        else:
            print(_t("common.invalid_choice"))
            conn.close()
            return

        # Execute query
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        permits = cursor.fetchall()

        if not permits:
            print(_t("parking.report.no_permits_found"))
            conn.close()
            return

        # Ask for report format
        print("\n" + _t("parking.section.select_report_format") + ":")
        print("1. " + _t("parking.menu.display_on_screen"))
        print("2. " + _t("parking.menu.export_to_csv"))
        print("3. " + _t("parking.menu.export_to_pdf"))

        format_choice = input("Enter your choice (1-3): ")

        if format_choice == '1':
            # Display on screen
            print(f"\n{report_title}")
            print("=" * 100)

            for permit in permits:
                # Display permit details
                display_permit_details(permit)
                print("-" * 100)

        elif format_choice == '2':
            # Export to CSV
            filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
            file_path = get_file_path('CSV', filename)

            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow([
                    'Permit ID', 'User ID', 'Name', 'Email', 'Zone', 'Type',
                    'Start Date', 'End Date', 'Status', 'Vehicle ID', 'Issue Date',
                    'License Plate', 'Vehicle Make', 'Vehicle Model'
                ])

                # Write data
                for permit in permits:
                    writer.writerow([
                        permit[0], permit[1], permit[2], permit[3], permit[4],
                        permit[5], permit[6], permit[7], permit[8], permit[9],
                        permit[10], permit[11] if len(permit) > 11 else '',
                        permit[12] if len(permit) > 12 else '',
                        permit[13] if len(permit) > 13 else ''
                    ])

            print(f"Report exported to {file_path}")

        elif format_choice == '3':
            # Export to PDF
            filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
            file_path = get_file_path('PDF', filename)

            # Create PDF document
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            elements = []

            # Add title
            styles = getSampleStyleSheet()
            elements.append(Paragraph(report_title, styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Paragraph(" ", styles['Normal']))  # Add some space

            # Create table for data
            data = [['Permit ID', 'User', 'Zone', 'Type', 'Valid Period', 'Status', 'Vehicle']]

            for permit in permits:
                # Format data for table
                vehicle_info = f"{permit[12]} {permit[13]} ({permit[11]})" if len(permit) > 11 and permit[11] else "N/A"
                valid_period = f"{permit[6]} to {permit[7]}"

                data.append([
                    permit[0],  # Permit ID
                    permit[2],  # Name
                    permit[4],  # Zone
                    permit[5],  # Type
                    valid_period,  # Valid Period
                    permit[8],  # Status
                    vehicle_info  # Vehicle
                ])

            # Create table
            table = Table(data, colWidths=[60, 80, 40, 60, 100, 50, 120])

            # Style the table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8)
            ]))

            elements.append(table)

            # Build the PDF
            doc.build(elements)

            print(f"Report exported to {file_path}")

        else:
            print(_t("common.invalid_choice"))

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in generate_permit_report: {e}")
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in generate_permit_report: {e}")
        print(f"An unexpected error occurred: {e}")

def generate_violation_report():
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    auth = core.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return

    if not auth.check_permission('generate_reports'):
        print(_t("parking.auth.no_permission"))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n" + _t("parking.section.violation_summary_report") + ":")
        print("1. " + _t("parking.menu.all_violations"))
        print("2. " + _t("parking.menu.violations_by_type"))
        print("3. " + _t("parking.menu.violations_by_date_range"))
        print("4. " + _t("parking.menu.violations_by_payment_status"))
        print("5. " + _t("parking.menu.violations_by_location"))

        choice = input("Enter your choice (1-5): ")

        report_title = ""
        query = ""
        params = ()

        if choice == '1':
            report_title = "All Violations Report"
            query = '''
            SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
            FROM parking_violations v
            LEFT JOIN users u ON v.officer_id = u.id
            ORDER BY v.violation_date DESC
            '''
        elif choice == '2':
            report_title = "Violations by Type Report"
            print("\n" + _t("parking.section.common_violation_types") + ":")
            print("1. " + _t("parking.violation_types.no_permit"))
            print("2. " + _t("parking.violation_types.expired_permit"))
            print("3. " + _t("parking.violation_types.wrong_zone"))
            print("4. " + _t("parking.violation_types.improper_parking"))
            print("5. " + _t("parking.violation_types.blocking_access"))
            print("6. " + _t("parking.violation_types.fire_lane"))
            print("7. " + _t("parking.violation_types.handicap_zone"))
            print("8. " + _t("parking.violation_types.other"))
            print("9. " + _t("parking.violation_types.custom"))

            type_choice = input("Select violation type (1-9): ")

            violation_types = [
                "No Permit", "Expired Permit", "Wrong Zone", "Improper Parking",
                "Blocking Access", "Fire Lane", "Handicap Zone", "Other"
            ]

            if type_choice in ['1', '2', '3', '4', '5', '6', '7', '8']:
                violation_type = violation_types[int(type_choice) - 1]
            elif type_choice == '9':
                violation_type = input("Enter specific violation type: ")
            else:
                print(_t("common.invalid_choice"))
                conn.close()
                return

            report_title = f"{violation_type} Violations Report"
            query = '''
            SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
            FROM parking_violations v
            LEFT JOIN users u ON v.officer_id = u.id
            WHERE v.violation_type = ?
            ORDER BY v.violation_date DESC
            '''
            params = (violation_type,)

        elif choice == '3':
            report_title = "Violations by Date Range Report"

            start_date = input("Enter start date (YYYY-MM-DD): ")
            try:
                # Validate date format
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                print(_t("parking.error.invalid_date_format"))
                conn.close()
                return

            end_date = input("Enter end date (YYYY-MM-DD): ")
            try:
                # Validate date format
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                print(_t("parking.error.invalid_date_format"))
                conn.close()
                return

            report_title = f"Violations from {start_date} to {end_date} Report"
            query = '''
            SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
            FROM parking_violations v
            LEFT JOIN users u ON v.officer_id = u.id
            WHERE date(v.violation_date) BETWEEN date(?) AND date(?)
            ORDER BY v.violation_date DESC
            '''
            params = (start_date, end_date)

        elif choice == '4':
            report_title = "Violations by Payment Status Report"
            print(_t("parking.violation.payment_statuses"))
            status = input("Enter payment status: ")

            if status not in ['Paid', 'Unpaid', 'Appealed', 'Waived']:
                print(_t("parking.error.invalid_status_using_unpaid"))
                status = "Unpaid"

            report_title = f"{status} Violations Report"
            query = '''
            SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
            FROM parking_violations v
            LEFT JOIN users u ON v.officer_id = u.id
            WHERE v.payment_status = ?
            ORDER BY v.violation_date DESC
            '''
            params = (status,)

        elif choice == '5':
            report_title = "Violations by Location Report"
            location = input("Enter location: ")

            report_title = f"Violations at {location} Report"
            query = '''
            SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
            FROM parking_violations v
            LEFT JOIN users u ON v.officer_id = u.id
            WHERE v.location LIKE ?
            ORDER BY v.violation_date DESC
            '''
            params = (f"%{escape_like(location)}%",)

        else:
            print(_t("common.invalid_choice"))
            conn.close()
            return

        # Execute query
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        violations = cursor.fetchall()

        if not violations:
            print(_t("parking.report.no_violations_found"))
            conn.close()
            return

        # Ask for report format
        print("\n" + _t("parking.section.select_report_format") + ":")
        print("1. " + _t("parking.menu.display_on_screen"))
        print("2. " + _t("parking.menu.export_to_csv"))
        print("3. " + _t("parking.menu.export_to_pdf"))

        format_choice = input("Enter your choice (1-3): ")

        if format_choice == '1':
            # Display on screen
            print(f"\n{report_title}")
            print("=" * 100)

            for violation in violations:
                # Display violation details
                display_violation_details(violation)
                print("-" * 100)

        elif format_choice == '2':
            # Export to CSV
            filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
            file_path = get_file_path('CSV', filename)

            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow([
                    'Violation ID', 'Vehicle ID', 'License Plate', 'Violation Type',
                    'Violation Date', 'Fine Amount', 'Payment Status', 'Location', 'Officer'
                ])

                # Write data
                for violation in violations:
                    writer.writerow([
                        violation[0], violation[1], violation[2], violation[3],
                        violation[4], violation[5], violation[6], violation[7],
                        violation[9] if len(violation) > 9 else violation[8]
                    ])

            print(f"Report exported to {file_path}")

        elif format_choice == '3':
            # Export to PDF
            filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
            file_path = get_file_path('PDF', filename)

            # Create PDF document
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            elements = []

            # Add title
            styles = getSampleStyleSheet()
            elements.append(Paragraph(report_title, styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Paragraph(" ", styles['Normal']))  # Add some space

            # Create table for data
            data = [['Violation ID', 'License Plate', 'Type', 'Date', 'Fine', 'Status', 'Location', 'Officer']]

            for violation in violations:
                # Format data for table
                fine = f"£{violation[5]:.2f}"

                data.append([
                    violation[0],  # Violation ID
                    violation[2],  # License Plate
                    violation[3],  # Type
                    violation[4],  # Date
                    fine,  # Fine
                    violation[6],  # Status
                    violation[7],  # Location
                    violation[9] if len(violation) > 9 else 'N/A'   # Officer
                ])

            # Create table
            table = Table(data, colWidths=[60, 60, 60, 70, 40, 50, 80, 80])

            # Style the table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (4, 1), (4, -1), 'RIGHT')  # Align fine amount to right
            ]))

            elements.append(table)

            # Add summary
            elements.append(Paragraph(" ", styles['Normal']))  # Add space
            elements.append(Paragraph("Summary", styles['Heading2']))

            # Calculate totals
            total_violations = len(violations)
            total_fines = sum(v[5] for v in violations)
            paid_violations = sum(1 for v in violations if v[6] == 'Paid')
            unpaid_violations = sum(1 for v in violations if v[6] == 'Unpaid')

            elements.append(Paragraph(f"Total Violations: {total_violations}", styles['Normal']))
            elements.append(Paragraph(f"Total Fines: £{total_fines:.2f}", styles['Normal']))
            elements.append(Paragraph(f"Paid Violations: {paid_violations}", styles['Normal']))
            elements.append(Paragraph(f"Unpaid Violations: {unpaid_violations}", styles['Normal']))

            # Build the PDF
            doc.build(elements)

            print(f"Report exported to {file_path}")

        else:
            print(_t("common.invalid_choice"))

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in generate_violation_report: {e}")
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in generate_violation_report: {e}")
        print(f"An unexpected error occurred: {e}")

def generate_compliance_report():
    """Generate a compliance and audit report"""
    report_title = "Compliance Report"
    auth = core.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return

    if not auth.check_permission('generate_reports'):
        print(_t("parking.auth.no_permission"))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n" + "="*80)
        print(_t("parking.report.compliance_header"))
        print("="*80)
        print(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # 1. Permit Compliance
        print("📋 PERMIT COMPLIANCE")
        print("-" * 40)

        # Expired permits
        cursor.execute('''
        SELECT COUNT(*)
        FROM parking_permits
        WHERE date(end_date) < date('now') AND active_status = 'Active'
        ''')
        expired_active = cursor.fetchone()[0]

        # Permits expiring soon (within 30 days)
        cursor.execute('''
        SELECT COUNT(*)
        FROM parking_permits
        WHERE date(end_date) BETWEEN date('now') AND date('now', '+30 days')
        AND active_status = 'Active'
        ''')
        expiring_soon = cursor.fetchone()[0]

        # Permits without vehicles
        cursor.execute('''
        SELECT COUNT(*)
        FROM parking_permits
        WHERE vehicle_id IS NULL AND active_status = 'Active'
        ''')
        no_vehicle = cursor.fetchone()[0]

        print(f"⚠️  Expired but Active Permits: {expired_active}")
        print(f"📅 Expiring in 30 Days: {expiring_soon}")
        print(f"🚗 Permits Without Vehicles: {no_vehicle}")

        if expired_active > 0:
            print("\n" + _t("parking.section.expired_active_permits") + ":")
            cursor.execute('''
            SELECT permit_id, full_name, zone, end_date
            FROM parking_permits
            WHERE date(end_date) < date('now') AND active_status = 'Active'
            ORDER BY end_date
            LIMIT 10
            ''')

            expired_permits = cursor.fetchall()
            for permit in expired_permits:
                print(f"  • {permit[0]} - {permit[1]} - Zone {permit[2]} - Expired: {permit[3]}")
        print()

        # 2. Vehicle Registration Compliance
        print("🚗 VEHICLE REGISTRATION COMPLIANCE")
        print("-" * 40)

        # Vehicles without permits
        cursor.execute('''
        SELECT COUNT(DISTINCT v.vehicle_id)
        FROM vehicles v
        LEFT JOIN parking_permits p ON v.vehicle_id = p.vehicle_id AND p.active_status = 'Active'
        WHERE p.vehicle_id IS NULL
        ''')
        vehicles_no_permits = cursor.fetchone()[0]

        # Duplicate license plates
        cursor.execute('''
        SELECT license_plate, COUNT(*) as count
        FROM vehicles
        GROUP BY license_plate
        HAVING count > 1
        ''')
        duplicate_plates = cursor.fetchall()

        print(f"🎫 Vehicles Without Active Permits: {vehicles_no_permits}")
        print(f"🔄 Duplicate License Plates: {len(duplicate_plates)}")

        if duplicate_plates:
            print("\n" + _t("parking.section.duplicate_plates") + ":")
            for plate, count in duplicate_plates:
                print(f"  • {plate}: {count} vehicles")
        print()

        # 3. Violation Compliance
        print("🚫 VIOLATION COMPLIANCE")
        print("-" * 40)

        # Old unpaid violations
        cursor.execute('''
        SELECT COUNT(*)
        FROM parking_violations
        WHERE payment_status = 'Unpaid'
        AND date(violation_date) < date('now', '-90 days')
        ''')
        old_unpaid = cursor.fetchone()[0]

        # High-value unpaid violations
        cursor.execute('''
        SELECT COUNT(*)
        FROM parking_violations
        WHERE payment_status = 'Unpaid' AND fine_amount >= 100
        ''')
        high_value_unpaid = cursor.fetchone()[0]

        # Repeat offenders
        cursor.execute('''
        SELECT license_plate, COUNT(*) as violation_count
        FROM parking_violations
        WHERE violation_date >= date('now', '-365 days')
        GROUP BY license_plate
        HAVING violation_count >= 5
        ORDER BY violation_count DESC
        ''')
        repeat_offenders = cursor.fetchall()

        print(f"⏰ Old Unpaid Violations (90+ days): {old_unpaid}")
        print(f"💰 High-Value Unpaid (£100+): {high_value_unpaid}")
        print(f"🔄 Repeat Offenders (5+ violations): {len(repeat_offenders)}")

        if repeat_offenders:
            print("\n" + _t("parking.section.top_repeat_offenders") + ":")
            for plate, count in repeat_offenders[:5]:
                print(f"  • {plate}: {count} violations")
        print()

        # 4. Data Integrity Issues
        print("🔍 DATA INTEGRITY ISSUES")
        print("-" * 40)

        # Permits with invalid zones
        cursor.execute('''
        SELECT COUNT(*)
        FROM parking_permits
        WHERE zone NOT IN ('A', 'B', 'C', 'V', 'H', 'M', 'R')
        ''')
        invalid_zones = cursor.fetchone()[0]

        # Violations without corresponding vehicles
        cursor.execute('''
        SELECT COUNT(*)
        FROM parking_violations v
        LEFT JOIN vehicles vh ON v.license_plate = vh.license_plate
        WHERE vh.license_plate IS NULL
        ''')
        violations_no_vehicles = cursor.fetchone()[0]

        # Users with missing information
        cursor.execute('''
        SELECT COUNT(*)
        FROM users
        WHERE email IS NULL OR email = '' OR first_name IS NULL OR first_name = ''
        ''')
        incomplete_users = cursor.fetchone()[0]

        print(f"🎯 Invalid Permit Zones: {invalid_zones}")
        print(f"🚗 Violations for Unregistered Vehicles: {violations_no_vehicles}")
        print(f"👤 Users with Missing Info: {incomplete_users}")
        print()

        # 5. Financial Compliance
        print("💰 FINANCIAL COMPLIANCE")
        print("-" * 40)

        # Total outstanding debt
        cursor.execute('''
        SELECT SUM(fine_amount)
        FROM parking_violations
        WHERE payment_status = 'Unpaid'
        ''')
        total_debt = cursor.fetchone()[0] or 0

        # Outstanding debt by age
        cursor.execute('''
        SELECT
            CASE
                WHEN date(violation_date) >= date('now', '-30 days') THEN '0-30 days'
                WHEN date(violation_date) >= date('now', '-90 days') THEN '31-90 days'
                WHEN date(violation_date) >= date('now', '-365 days') THEN '91-365 days'
                ELSE '365+ days'
            END as age_group,
            COUNT(*) as count,
            SUM(fine_amount) as amount
        FROM parking_violations
        WHERE payment_status = 'Unpaid'
        GROUP BY age_group
        ''')

        debt_aging = cursor.fetchall()

        print(f"💸 Total Outstanding Debt: £{total_debt:,.2f}")
        print("\n" + _t("parking.section.debt_aging_analysis") + ":")
        print(f"{'Age Group':<15} {'Count':<8} {'Amount':<15}")
        print("-" * 40)

        for age, count, amount in debt_aging:
            print(f"{age:<15} {count:<8} £{amount:<14.2f}")
        print()

        # 6. Audit Trail
        print("📊 AUDIT SUMMARY")
        print("-" * 40)

        # Activity in last 30 days
        cursor.execute('''
        SELECT COUNT(*) FROM parking_permits
        WHERE date(issue_date) >= date('now', '-30 days')
        ''')
        recent_permits = cursor.fetchone()[0]

        cursor.execute('''
        SELECT COUNT(*) FROM parking_violations
        WHERE date(violation_date) >= date('now', '-30 days')
        ''')
        recent_violations = cursor.fetchone()[0]

        cursor.execute('''
        SELECT COUNT(*) FROM vehicles
        WHERE vehicle_id IN (
            SELECT vehicle_id FROM parking_permits
            WHERE date(issue_date) >= date('now', '-30 days')
        )
        ''')
        recent_vehicles = cursor.fetchone()[0]

        print(f"📋 New Permits (30 days): {recent_permits}")
        print(f"🚫 New Violations (30 days): {recent_violations}")
        print(f"🚗 New Vehicles (30 days): {recent_vehicles}")
        print()

        # 7. Compliance Score
        print("📈 OVERALL COMPLIANCE SCORE")
        print("-" * 40)

        # Calculate compliance score (0-100)
        score = 100

        # Deduct points for issues
        if expired_active > 0:
            score -= min(expired_active * 2, 20)  # Max 20 points
        if old_unpaid > 0:
            score -= min(old_unpaid * 1, 15)  # Max 15 points
        if len(repeat_offenders) > 0:
            score -= min(len(repeat_offenders) * 3, 15)  # Max 15 points
        if duplicate_plates:
            score -= min(len(duplicate_plates) * 5, 10)  # Max 10 points
        if violations_no_vehicles > 0:
            score -= min(violations_no_vehicles * 2, 10)  # Max 10 points

        score = max(score, 0)  # Ensure score doesn't go below 0

        # Determine grade
        if score >= 90:
            grade = "A (Excellent)"
            status = "✅"
        elif score >= 80:
            grade = "B (Good)"
            status = "✅"
        elif score >= 70:
            grade = "C (Fair)"
            status = "⚠️"
        elif score >= 60:
            grade = "D (Poor)"
            status = "❌"
        else:
            grade = "F (Critical)"
            status = "🚨"

        print(f"{status} Compliance Score: {score}/100")
        print(f"Grade: {grade}")
        print()

        # 8. Action Items
        print("✅ RECOMMENDED ACTIONS")
        print("-" * 40)

        actions = []

        if expired_active > 0:
            actions.append(f"1. Deactivate {expired_active} expired permits")
        if old_unpaid > 0:
            actions.append(f"2. Follow up on {old_unpaid} old unpaid violations")
        if len(repeat_offenders) > 0:
            actions.append(f"3. Review {len(repeat_offenders)} repeat offenders for escalation")
        if duplicate_plates:
            actions.append(f"4. Resolve {len(duplicate_plates)} duplicate license plate entries")
        if violations_no_vehicles > 0:
            actions.append(f"5. Register {violations_no_vehicles} vehicles with violations")
        if incomplete_users > 0:
            actions.append(f"6. Complete information for {incomplete_users} user records")

        if actions:
            for action in actions:
                print(action)
        else:
            print(_t("parking.report.system_compliant"))

        print("\n" + "="*80)

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in generate_compliance_report: {e}")
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in generate_compliance_report: {e}")
        try:
            cursor.execute("SELECT * FROM parking_permits WHERE active_status = 'Active'")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            active_permits = cursor.fetchone()[0]

            # Unpaid violations
            cursor.execute("SELECT COUNT(*) FROM parking_violations WHERE payment_status = 'Unpaid'")
            unpaid_violations = cursor.fetchone()[0]

            # Total unpaid fines
            cursor.execute("SELECT SUM(fine_amount) FROM parking_violations WHERE payment_status = 'Unpaid'")
            unpaid_fines = cursor.fetchone()[0] or 0

            print("\n" + _t("parking.section.current_status") + ":")
            print("-" * 50)
            print(f"Active Permits: {active_permits}")
            print(f"Unpaid Violations: {unpaid_violations}")
            print(f"Total Unpaid Fines: £{unpaid_fines:.2f}")

            # Usage by role
            cursor.execute('''
            SELECT role, COUNT(*)
            FROM users
            GROUP BY role
            ORDER BY COUNT(*) DESC
            ''')

            roles = cursor.fetchall()

            print("\n" + _t("parking.section.users_by_role") + ":")
            print("-" * 50)
            for role, count in roles:
                print(f"{role}: {count}")

            # Permits by zone
            cursor.execute('''
            SELECT zone, COUNT(*)
            FROM parking_permits
            GROUP BY zone
            ORDER BY COUNT(*) DESC
            ''')

            zones = cursor.fetchall()

            print("\n" + _t("parking.section.permits_by_zone") + ":")
            print("-" * 50)
            for zone, count in zones:
                zone_name = PARKING_ZONES.get(zone, {}).get('name', 'Unknown')
                print(f"Zone {zone} ({zone_name}): {count}")

        else:
            print(_t("common.invalid_choice"))
            conn.close()
            return

        # Ask if user wants to export the report
        export = input("\nExport this report? (y/n): ")
        if export.lower() == 'y':
            print("\n" + _t("parking.section.export_format") + ":")
            print("1. " + _t("parking.menu.csv"))
            print("2. " + _t("parking.menu.pdf"))

            format_choice = input("Enter your choice (1-2): ")

            if format_choice == '1':
                filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
                file_path = get_file_path('CSV', filename)
                print(f"Report exported to {file_path}")
            elif format_choice == '2':
                filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                file_path = get_file_path('PDF', filename)
                print(f"Report exported to {file_path}")

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in generate_user_activity_report: {e}")
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in generate_user_activity_report: {e}")
        print(f"An unexpected error occurred: {e}")

def generate_analytics_dashboard():
    """Generate a comprehensive analytics dashboard"""
    auth = core.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return

    if not auth.check_permission('generate_reports'):
        print(_t("parking.auth.no_permission"))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if parking_permits table has user_id column
        cursor.execute("PRAGMA table_info(parking_permits)")
        permit_columns = [col[1] for col in cursor.fetchall()]
        has_user_id = 'user_id' in permit_columns

        print("\n" + "="*80)
        print(_t("parking.report.analytics_header"))
        print("="*80)
        print(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # 1. Key Performance Indicators
        print("📊 KEY PERFORMANCE INDICATORS")
        print("-" * 40)

        # Total revenue
        cursor.execute("SELECT SUM(fine_amount) FROM parking_violations WHERE payment_status = 'Paid'")
        violation_revenue = cursor.fetchone()[0] or 0

        # Estimate permit revenue (simplified calculation)
        cursor.execute("SELECT COUNT(*), permit_type, zone FROM parking_permits GROUP BY permit_type, zone")
        permit_revenue = 0
        for count, permit_type, zone in cursor.fetchall():
            if zone in PARKING_ZONES:
                if permit_type == 'Annual':
                    permit_revenue += PARKING_ZONES[zone]['annual_fee'] * count
                elif permit_type == 'Semester':
                    permit_revenue += PARKING_ZONES[zone]['annual_fee'] * 0.6 * count
                else:
                    permit_revenue += 10 * count  # Default

        total_revenue = violation_revenue + permit_revenue

        cursor.execute("SELECT COUNT(*) FROM parking_permits WHERE active_status = 'Active'")
        active_permits = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM parking_violations WHERE payment_status = 'Unpaid'")
        unpaid_violations = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(fine_amount) FROM parking_violations WHERE payment_status = 'Unpaid'")
        unpaid_fines = cursor.fetchone()[0] or 0

        cursor.execute("SELECT SUM(total_spaces), SUM(available_spaces) FROM parking_lots")
        space_data = cursor.fetchone()
        total_spaces = space_data[0] or 0
        available_spaces = space_data[1] or 0
        occupancy_rate = ((total_spaces - available_spaces) / total_spaces * 100) if total_spaces > 0 else 0

        print(f"💰 Total Revenue: £{total_revenue:,.2f}")
        print(f"🎫 Active Permits: {active_permits:,}")
        print(f"⚠️  Unpaid Violations: {unpaid_violations:,}")
        print(f"💸 Outstanding Fines: £{unpaid_fines:,.2f}")
        print(f"🏠 Parking Occupancy: {occupancy_rate:.1f}%")
        print()

        # 2. Recent Activity (Last 7 Days)
        print("🕒 RECENT ACTIVITY (Last 7 Days)")
        print("-" * 40)

        cursor.execute('''
        SELECT COUNT(*)
        FROM parking_permits
        WHERE date(issue_date) >= date('now', '-7 days')
        ''')
        new_permits = cursor.fetchone()[0]

        cursor.execute('''
        SELECT COUNT(*)
        FROM parking_violations
        WHERE date(violation_date) >= date('now', '-7 days')
        ''')
        new_violations = cursor.fetchone()[0]

        cursor.execute('''
        SELECT COUNT(*)
        FROM vehicles
        WHERE vehicle_id IN (
            SELECT DISTINCT vehicle_id FROM parking_permits
            WHERE date(issue_date) >= date('now', '-7 days')
            AND vehicle_id IS NOT NULL
        )
        ''')
        new_vehicles = cursor.fetchone()[0]

        print(f"📋 New Permits Issued: {new_permits}")
        print(f"🚗 New Vehicles Registered: {new_vehicles}")
        print(f"🚫 New Violations Recorded: {new_violations}")
        print()

        # 3. Top Violation Types
        print("🚫 TOP VIOLATION TYPES")
        print("-" * 40)

        cursor.execute('''
        SELECT violation_type, COUNT(*) as count, SUM(fine_amount) as total_fines
        FROM parking_violations
        GROUP BY violation_type
        ORDER BY count DESC
        LIMIT 5
        ''')

        top_violations = cursor.fetchall()

        if top_violations:
            print(f"{'Violation Type':<20} {'Count':<8} {'Total Fines':<15}")
            print("-" * 45)
            for vtype, count, fines in top_violations:
                print(f"{vtype:<20} {count:<8} £{fines:<14.2f}")
        else:
            print(_t("parking.report.no_violation_data"))
        print()

        # 4. Zone Analysis
        print("🅿️  PARKING ZONE ANALYSIS")
        print("-" * 40)

        cursor.execute('''
        SELECT zone, COUNT(*) as permits
        FROM parking_permits
        WHERE active_status = 'Active'
        GROUP BY zone
        ORDER BY permits DESC
        ''')

        zone_permits = cursor.fetchall()

        if zone_permits:
            print(f"{'Zone':<6} {'Name':<20} {'Active Permits':<15}")
            print("-" * 45)
            for zone, permits in zone_permits:
                zone_name = PARKING_ZONES.get(zone, {}).get('name', 'Unknown')
                print(f"{zone:<6} {zone_name:<20} {permits:<15}")
        else:
            print(_t("parking.report.no_permit_data"))
        print()

        # 5. System Health Check
        print("🔍 SYSTEM HEALTH CHECK")
        print("-" * 40)

        # Check for expired permits
        cursor.execute('''
        SELECT COUNT(*)
        FROM parking_permits
        WHERE date(end_date) < date('now') AND active_status = 'Active'
        ''')
        expired_active = cursor.fetchone()[0]

        # Check for duplicate license plates
        cursor.execute('''
        SELECT COUNT(*) FROM (
            SELECT license_plate
            FROM vehicles
            GROUP BY license_plate
            HAVING COUNT(*) > 1
        )
        ''')
        duplicate_plates = cursor.fetchone()[0]

        # Check for permits without vehicles
        cursor.execute('''
        SELECT COUNT(*)
        FROM parking_permits
        WHERE vehicle_id IS NULL AND active_status = 'Active'
        ''')
        permits_no_vehicle = cursor.fetchone()[0]

        issues = []
        if expired_active > 0:
            issues.append(f"⚠️  {expired_active} expired permits still active")
        if duplicate_plates > 0:
            issues.append(f"⚠️  {duplicate_plates} duplicate license plates")
        if permits_no_vehicle > 0:
            issues.append(f"⚠️  {permits_no_vehicle} permits without vehicles")

        if issues:
            for issue in issues:
                print(issue)
        else:
            print("✅ No system issues detected")

        print("\n" + "="*80)

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in generate_analytics_dashboard: {e}")
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in generate_analytics_dashboard: {e}")
        print(f"An unexpected error occurred: {e}")

def generate_revenue_report():
    auth = core.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return

    if not auth.check_permission('generate_reports'):
        print(_t("parking.auth.no_permission"))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n" + _t("parking.section.revenue_report_options") + ":")
        print("1. " + _t("parking.menu.permit_revenue_report"))
        print("2. " + _t("parking.menu.violation_revenue_report"))
        print("3. " + _t("parking.menu.combined_revenue_report"))
        print("4. " + _t("parking.menu.revenue_by_zone"))
        print("5. " + _t("parking.menu.revenue_by_month"))

        choice = input("Enter your choice (1-5): ")

        report_title = ""

        if choice == '1':
            # Permit Revenue Report
            report_title = "Permit Revenue Report"

            # Get permits with calculated fees
            cursor.execute('''
            SELECT
                p.permit_type,
                p.zone,
                COUNT(*) as count,
                p.start_date,
                p.end_date
            FROM parking_permits p
            GROUP BY p.permit_type, p.zone
            ORDER BY p.zone, p.permit_type
            ''')

            permit_data = cursor.fetchall()

            print(f"\n{report_title}")
            print("=" * 100)

            total_revenue = 0

            print(f"{'Zone':<6} {'Type':<10} {'Count':<8} {'Unit Fee':<10} {'Total':<15}")
            print("-" * 100)

            for permit_type, zone, count, start_date, end_date in permit_data:
                # Calculate fee based on permit type and zone
                if permit_type == 'Annual':
                    unit_fee = PARKING_ZONES[zone]['annual_fee']
                elif permit_type == 'Semester':
                    unit_fee = PARKING_ZONES[zone]['annual_fee'] * 0.6
                elif permit_type == 'Monthly':
                    unit_fee = PARKING_ZONES[zone]['annual_fee'] * 0.15
                elif permit_type == 'Daily':
                    unit_fee = PARKING_ZONES[zone]['hourly_rate'] * 8 if PARKING_ZONES[zone]['hourly_rate'] > 0 else 10
                else:  # Temporary
                    unit_fee = PARKING_ZONES[zone]['hourly_rate'] * 8 if PARKING_ZONES[zone]['hourly_rate'] > 0 else 10

                total_fee = unit_fee * count
                total_revenue += total_fee

                print(f"{zone:<6} {permit_type:<10} {count:<8} £{unit_fee:<9.2f} £{total_fee:<14.2f}")

            print("-" * 100)
            print(f"{'TOTAL REVENUE':<35} £{total_revenue:.2f}")

        elif choice == '2':
            # Violation Revenue Report
            report_title = "Violation Revenue Report"

            cursor.execute('''
            SELECT
                violation_type,
                payment_status,
                COUNT(*) as count,
                SUM(fine_amount) as total_fines
            FROM parking_violations
            GROUP BY violation_type, payment_status
            ORDER BY violation_type, payment_status
            ''')

            violation_data = cursor.fetchall()

            print(f"\n{report_title}")
            print("=" * 100)

            total_fines = 0
            paid_fines = 0
            unpaid_fines = 0

            print(f"{'Violation Type':<20} {'Status':<10} {'Count':<8} {'Total Fines':<15}")
            print("-" * 100)

            for vtype, status, count, total in violation_data:
                print(f"{vtype:<20} {status:<10} {count:<8} £{total:<14.2f}")

                total_fines += total
                if status == 'Paid':
                    paid_fines += total
                else:
                    unpaid_fines += total

            print("-" * 100)
            print(f"{'Total Fines:':<40} £{total_fines:.2f}")
            print(f"{'Paid Fines:':<40} £{paid_fines:.2f}")
            print(f"{'Unpaid Fines:':<40} £{unpaid_fines:.2f}")
            print(f"{'Collection Rate:':<40} {(paid_fines/total_fines*100) if total_fines > 0 else 0:.1f}%")

        elif choice == '3':
            # Combined revenue report
            report_title = "Combined Revenue Report"

            print(f"\n{report_title}")
            print("=" * 100)

            # Get permit revenue
            cursor.execute('''
            SELECT COUNT(*) as count, permit_type, zone
            FROM parking_permits
            GROUP BY permit_type, zone
            ''')

            permit_revenue = 0
            for count, permit_type, zone in cursor.fetchall():
                if permit_type == 'Annual':
                    permit_revenue += PARKING_ZONES[zone]['annual_fee'] * count
                elif permit_type == 'Semester':
                    permit_revenue += PARKING_ZONES[zone]['annual_fee'] * 0.6 * count
                elif permit_type == 'Monthly':
                    permit_revenue += PARKING_ZONES[zone]['annual_fee'] * 0.15 * count
                else:
                    permit_revenue += 10 * count  # Default daily rate

            # Get violation revenue
            cursor.execute('''
            SELECT SUM(fine_amount)
            FROM parking_violations
            WHERE payment_status = 'Paid'
            ''')

            violation_revenue = cursor.fetchone()[0] or 0

            print(f"{'Revenue Source':<30} {'Amount':<15}")
            print("-" * 50)
            print(f"{'Parking Permits:':<30} £{permit_revenue:.2f}")
            print(f"{'Paid Violations:':<30} £{violation_revenue:.2f}")
            print("-" * 50)
            print(f"{'TOTAL REVENUE:':<30} £{permit_revenue + violation_revenue:.2f}")

        elif choice == '4':
            # Revenue by Zone
            report_title = "Revenue by Zone Report"

            print(f"\n{report_title}")
            print("=" * 100)

            zone_revenues = {}

            # Get permit revenue by zone
            cursor.execute('''
            SELECT zone, permit_type, COUNT(*) as count
            FROM parking_permits
            GROUP BY zone, permit_type
            ''')

            for zone, permit_type, count in cursor.fetchall():
                if zone not in zone_revenues:
                    zone_revenues[zone] = {'permits': 0, 'violations': 0}

                if permit_type == 'Annual':
                    zone_revenues[zone]['permits'] += PARKING_ZONES[zone]['annual_fee'] * count
                elif permit_type == 'Semester':
                    zone_revenues[zone]['permits'] += PARKING_ZONES[zone]['annual_fee'] * 0.6 * count
                else:
                    zone_revenues[zone]['permits'] += 10 * count

            # Get violation revenue by location/zone
            for zone in PARKING_ZONES:
                cursor.execute('''
                SELECT SUM(fine_amount)
                FROM parking_violations
                WHERE payment_status = 'Paid'
                AND location LIKE ?
                ''', (f'%Zone {zone}%',))

                revenue = cursor.fetchone()[0] or 0
                if zone not in zone_revenues:
                    zone_revenues[zone] = {'permits': 0, 'violations': 0}
                zone_revenues[zone]['violations'] = revenue

            print(f"{'Zone':<6} {'Zone Name':<20} {'Permit Revenue':<15} {'Violation Revenue':<18} {'Total':<15}")
            print("-" * 80)

            total_permit_rev = 0
            total_violation_rev = 0

            for zone, zone_name in sorted(PARKING_ZONES.items()):
                permits = zone_revenues.get(zone, {}).get('permits', 0)
                violations = zone_revenues.get(zone, {}).get('violations', 0)
                total = permits + violations

                total_permit_rev += permits
                total_violation_rev += violations

                print(f"{zone:<6} {zone_name['name']:<20} £{permits:<14.2f} £{violations:<17.2f} £{total:<14.2f}")

            print("-" * 80)
            print(f"{'TOTAL':<27} £{total_permit_rev:<14.2f} £{total_violation_rev:<17.2f} £{total_permit_rev + total_violation_rev:<14.2f}")

        elif choice == '5':
            # Revenue by Month
            start_date = input("Enter start date (YYYY-MM-DD): ")
            end_date = input("Enter end date (YYYY-MM-DD): ")

            report_title = f"Revenue by Month Report ({start_date} to {end_date})"

            print(f"\n{report_title}")
            print("=" * 100)

            # Get monthly permit revenue
            cursor.execute('''
            SELECT
                strftime('%Y-%m', issue_date) as month,
                permit_type,
                zone,
                COUNT(*) as count
            FROM parking_permits
            WHERE date(issue_date) BETWEEN date(?) AND date(?)
            GROUP BY month, permit_type, zone
            ORDER BY month
            ''', (start_date, end_date))

            monthly_data = {}

            for month, permit_type, zone, count in cursor.fetchall():
                if month not in monthly_data:
                    monthly_data[month] = {'permits': 0, 'violations': 0}

                if permit_type == 'Annual':
                    monthly_data[month]['permits'] += PARKING_ZONES[zone]['annual_fee'] * count
                elif permit_type == 'Semester':
                    monthly_data[month]['permits'] += PARKING_ZONES[zone]['annual_fee'] * 0.6 * count
                else:
                    monthly_data[month]['permits'] += 10 * count

            # Get monthly violation revenue
            cursor.execute('''
            SELECT
                strftime('%Y-%m', violation_date) as month,
                SUM(fine_amount) as total
            FROM parking_violations
            WHERE payment_status = 'Paid'
            AND date(violation_date) BETWEEN date(?) AND date(?)
            GROUP BY month
            ORDER BY month
            ''', (start_date, end_date))

            for month, total in cursor.fetchall():
                if month not in monthly_data:
                    monthly_data[month] = {'permits': 0, 'violations': 0}
                monthly_data[month]['violations'] = total

            print(f"{'Month':<10} {'Permit Revenue':<15} {'Violation Revenue':<18} {'Total':<15}")
            print("-" * 60)

            total_permits = 0
            total_violations = 0

            for month in sorted(monthly_data.keys()):
                permits = monthly_data[month]['permits']
                violations = monthly_data[month]['violations']
                total = permits + violations

                total_permits += permits
                total_violations += violations

                print(f"{month:<10} £{permits:<14.2f} £{violations:<17.2f} £{total:<14.2f}")

            print("-" * 60)
            print(f"{'TOTAL':<10} £{total_permits:<14.2f} £{total_violations:<17.2f} £{total_permits + total_violations:<14.2f}")

        else:
            print(_t("common.invalid_choice"))
            conn.close()
            return

        # Ask if user wants to export the report
        export = input("\nExport this report? (y/n): ")
        if export.lower() == 'y':
            print("\n" + _t("parking.section.export_format") + ":")
            print("1. " + _t("parking.menu.csv"))
            print("2. " + _t("parking.menu.pdf"))

            format_choice = input("Enter your choice (1-2): ")

            if format_choice == '1':
                # Export to CSV
                filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
                file_path = get_file_path('CSV', filename)
                print(f"Report exported to {file_path}")
            elif format_choice == '2':
                # Export to PDF
                filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                file_path = get_file_path('PDF', filename)
                print(f"Report exported to {file_path}")

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in generate_revenue_report: {e}")
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in generate_revenue_report: {e}")
        print(f"An unexpected error occurred: {e}")

def generate_user_activity_report():
    auth = core.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return

    if not auth.check_permission('generate_reports'):
        print(_t("parking.auth.no_permission"))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if parking_permits table has user_id column
        cursor.execute("PRAGMA table_info(parking_permits)")
        permit_columns = [col[1] for col in cursor.fetchall()]
        has_user_id = 'user_id' in permit_columns

        print("\n" + _t("parking.section.user_activity_options") + ":")
        print("1. " + _t("parking.menu.user_parking_history"))
        print("2. " + _t("parking.menu.officer_activity_report"))
        print("3. " + _t("parking.menu.most_active_users"))
        print("4. " + _t("parking.menu.user_violations_history"))
        print("5. " + _t("parking.menu.system_usage_stats"))

        choice = input("Enter your choice (1-5): ")

        report_title = ""

        if choice == '1':
            # User Parking History
            user_id = input("Enter user ID: ")

            report_title = f"User Parking History - User {user_id}"

            # Get user info
            cursor.execute('''
            SELECT first_name, last_name, email, role
            FROM users
            WHERE id = ?
            ''', (user_id,))

            user = cursor.fetchone()
            if not user:
                print(f"No user found with ID: {user_id}")
                conn.close()
                return

            print(f"\n{report_title}")
            print("=" * 100)
            print(f"Name: {user[0]} {user[1]}")
            print(f"Email: {user[2]}")
            print(f"Role: {user[3]}")
            print()

            # Get permits
            print(_t("parking.permit.permits_header"))
            print("-" * 50)

            if has_user_id:
                cursor.execute('''
                SELECT permit_id, zone, permit_type, start_date, end_date, active_status
                FROM parking_permits
                WHERE user_id = ?
                ORDER BY issue_date DESC
                ''', (user_id,))
            else:
                # Fallback to email/name matching
                user_email = user[2]
                user_name = f"{user[0]} {user[1]}"
                cursor.execute('''
                SELECT permit_id, zone, permit_type, start_date, end_date, active_status
                FROM parking_permits
                WHERE email = ? OR full_name = ?
                ORDER BY issue_date DESC
                ''', (user_email, user_name))

            permits = cursor.fetchall()
            if permits:
                for permit in permits:
                    print(f"Permit: {permit[0]} - Zone {permit[1]} - {permit[2]} - {permit[3]} to {permit[4]} - {permit[5]}")
            else:
                print(_t("parking.msg.no_permits_found"))

            # Get vehicles
            print("\n" + _t("parking.section.registered_vehicles") + ":")
            print("-" * 50)

            cursor.execute('''
            SELECT vehicle_id, license_plate, make, model, year
            FROM vehicles
            WHERE owner_id = ?
            ''', (user_id,))

            vehicles = cursor.fetchall()
            if vehicles:
                for vehicle in vehicles:
                    print(f"Vehicle: {vehicle[0]} - {vehicle[1]} - {vehicle[2]} {vehicle[3]} ({vehicle[4]})")
            else:
                print(_t("parking.msg.no_vehicles_found"))

            # Get violations
            print("\n" + _t("parking.section.violations") + ":")
            print("-" * 50)

            cursor.execute('''
            SELECT v.violation_id, v.license_plate, v.violation_type,
                   v.violation_date, v.fine_amount, v.payment_status
            FROM parking_violations v
            JOIN vehicles vh ON v.license_plate = vh.license_plate
            WHERE vh.owner_id = ?
            ORDER BY v.violation_date DESC
            ''', (user_id,))

            violations = cursor.fetchall()
            if violations:
                for violation in violations:
                    print(f"Violation: {violation[0]} - {violation[1]} - {violation[2]} - {violation[3]} - £{violation[4]:.2f} - {violation[5]}")
            else:
                print(_t("parking.msg.no_violations_found"))

        elif choice == '2':
            # Officer Activity Report
            officer_id = input("Enter officer ID (leave blank for all officers): ")

            if officer_id:
                report_title = f"Officer Activity Report - Officer {officer_id}"

                cursor.execute('''
                SELECT
                    u.first_name || ' ' || u.last_name as officer_name,
                    COUNT(v.violation_id) as total_violations,
                    SUM(v.fine_amount) as total_fines,
                    MIN(v.violation_date) as first_violation,
                    MAX(v.violation_date) as last_violation
                FROM parking_violations v
                JOIN users u ON v.officer_id = u.id
                WHERE v.officer_id = ?
                GROUP BY v.officer_id
                ''', (officer_id,))
            else:
                report_title = "All Officers Activity Report"

                cursor.execute('''
                SELECT
                    u.first_name || ' ' || u.last_name as officer_name,
                    v.officer_id,
                    COUNT(v.violation_id) as total_violations,
                    SUM(v.fine_amount) as total_fines,
                    MIN(v.violation_date) as first_violation,
                    MAX(v.violation_date) as last_violation
                FROM parking_violations v
                JOIN users u ON v.officer_id = u.id
                GROUP BY v.officer_id
                ORDER BY total_violations DESC
                ''')

            officers = cursor.fetchall()

            print(f"\n{report_title}")
            print("=" * 100)

            if officer_id:
                print(f"{'Officer':<25} {'Violations':<12} {'Total Fines':<15} {'First':<12} {'Last':<12}")
                print("-" * 80)
                for officer in officers:
                    print(f"{officer[0]:<25} {officer[1]:<12} £{officer[2]:<14.2f} {officer[3]:<12} {officer[4]:<12}")
            else:
                print(f"{'Officer':<25} {'ID':<8} {'Violations':<12} {'Total Fines':<15} {'First':<12} {'Last':<12}")
                print("-" * 100)
                for officer in officers:
                    print(f"{officer[0]:<25} {officer[1]:<8} {officer[2]:<12} £{officer[3]:<14.2f} {officer[4]:<12} {officer[5]:<12}")

        elif choice == '3':
            # Most Active Users
            report_title = "Most Active Users Report"

            if has_user_id:
                cursor.execute('''
                SELECT
                    u.id,
                    u.first_name || ' ' || u.last_name as name,
                    u.role,
                    COUNT(DISTINCT p.permit_id) as permit_count,
                    COUNT(DISTINCT v.vehicle_id) as vehicle_count,
                    COUNT(DISTINCT vl.violation_id) as violation_count
                FROM users u
                LEFT JOIN parking_permits p ON u.id = p.user_id
                LEFT JOIN vehicles v ON u.id = v.owner_id
                LEFT JOIN parking_violations vl ON v.vehicle_id = vl.vehicle_id
                GROUP BY u.id
                HAVING (permit_count + vehicle_count + violation_count) > 0
                ORDER BY (permit_count + vehicle_count + violation_count) DESC
                LIMIT 20
                ''')
            else:
                # Alternative query without user_id
                cursor.execute('''
                SELECT
                    u.id,
                    u.first_name || ' ' || u.last_name as name,
                    u.role,
                    COUNT(DISTINCT p.permit_id) as permit_count,
                    COUNT(DISTINCT v.vehicle_id) as vehicle_count,
                    COUNT(DISTINCT vl.violation_id) as violation_count
                FROM users u
                LEFT JOIN parking_permits p ON u.email = p.email OR (u.first_name || ' ' || u.last_name) = p.full_name
                LEFT JOIN vehicles v ON u.id = v.owner_id
                LEFT JOIN parking_violations vl ON v.vehicle_id = vl.vehicle_id
                GROUP BY u.id
                HAVING (permit_count + vehicle_count + violation_count) > 0
                ORDER BY (permit_count + vehicle_count + violation_count) DESC
                LIMIT 20
                ''')

            users = cursor.fetchall()

            print(f"\n{report_title}")
            print("=" * 100)
            print(f"{'ID':<8} {'Name':<25} {'Role':<10} {'Permits':<10} {'Vehicles':<10} {'Violations':<12}")
            print("-" * 100)

            for user in users:
                print(f"{user[0]:<8} {user[1]:<25} {user[2]:<10} {user[3]:<10} {user[4]:<10} {user[5]:<12}")

        elif choice == '4':
            # User Violations History
            report_title = "User Violations History Report"

            print("\n" + _t("parking.section.options") + ":")
            print("1. " + _t("parking.menu.by_specific_user"))
            print("2. " + _t("parking.menu.all_users_with_violations"))

            sub_choice = input("Enter your choice (1-2): ")

            if sub_choice == '1':
                user_id = input("Enter user ID: ")

                cursor.execute('''
                SELECT
                    u.first_name || ' ' || u.last_name as name,
                    vl.violation_id,
                    vl.license_plate,
                    vl.violation_type,
                    vl.violation_date,
                    vl.fine_amount,
                    vl.payment_status
                FROM users u
                JOIN vehicles v ON u.id = v.owner_id
                JOIN parking_violations vl ON v.vehicle_id = vl.vehicle_id
                WHERE u.id = ?
                ORDER BY vl.violation_date DESC
                ''', (user_id,))

                violations = cursor.fetchall()

                if violations:
                    print(f"\nViolations for {violations[0][0]}")
                    print("=" * 100)
                    print(f"{'Violation ID':<15} {'License':<12} {'Type':<20} {'Date':<12} {'Fine':<10} {'Status':<10}")
                    print("-" * 100)

                    for v in violations:
                        print(f"{v[1]:<15} {v[2]:<12} {v[3]:<20} {v[4]:<12} £{v[5]:<9.2f} {v[6]:<10}")
                else:
                    print(_t("parking.msg.no_violations_for_user"))

            else:
                cursor.execute('''
                SELECT
                    u.id,
                    u.first_name || ' ' || u.last_name as name,
                    COUNT(vl.violation_id) as violation_count,
                    SUM(vl.fine_amount) as total_fines,
                    SUM(CASE WHEN vl.payment_status = 'Paid' THEN vl.fine_amount ELSE 0 END) as paid_fines,
                    SUM(CASE WHEN vl.payment_status = 'Unpaid' THEN vl.fine_amount ELSE 0 END) as unpaid_fines
                FROM users u
                JOIN vehicles v ON u.id = v.owner_id
                JOIN parking_violations vl ON v.vehicle_id = vl.vehicle_id
                GROUP BY u.id
                ORDER BY violation_count DESC
                ''')

                users = cursor.fetchall()

                print(f"\n{report_title}")
                print("=" * 100)
                print(f"{'ID':<8} {'Name':<25} {'Violations':<12} {'Total Fines':<12} {'Paid':<12} {'Unpaid':<12}")
                print("-" * 100)

                for user in users:
                    print(f"{user[0]:<8} {user[1]:<25} {user[2]:<12} £{user[3]:<11.2f} £{user[4]:<11.2f} £{user[5]:<11.2f}")

        elif choice == '5':
            # System Usage Statistics
            report_title = "System Usage Statistics"

            print(f"\n{report_title}")
            print("=" * 100)

            # Total counts
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM parking_permits')
            total_permits = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM vehicles')
            total_vehicles = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM parking_violations')
            total_violations = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM parking_lots')
            total_lots = cursor.fetchone()[0]

            print(_t("parking.report.overall_statistics"))
            print("-" * 50)
            print(f"Total Users: {total_users}")
            print(f"Total Permits: {total_permits}")
            print(f"Total Vehicles: {total_vehicles}")
            print(f"Total Violations: {total_violations}")
            print(f"Total Parking Lots: {total_lots}")

            # Active permits
            cursor.execute("SELECT COUNT(*) FROM parking_permits WHERE active_status = 'Active'")
            active_permits = cursor.fetchone()[0]

            # Unpaid violations
            cursor.execute("SELECT COUNT(*) FROM parking_violations WHERE payment_status = 'Unpaid'")
            unpaid_violations = cursor.fetchone()[0]

            # Total unpaid fines
            cursor.execute("SELECT SUM(fine_amount) FROM parking_violations WHERE payment_status = 'Unpaid'")
            unpaid_fines = cursor.fetchone()[0] or 0

            print("\n" + _t("parking.section.current_status") + ":")
            print("-" * 50)
            print(f"Active Permits: {active_permits}")
            print(f"Unpaid Violations: {unpaid_violations}")
            print(f"Total Unpaid Fines: £{unpaid_fines:.2f}")

            # Usage by role
            cursor.execute('''
            SELECT role, COUNT(*)
            FROM users
            GROUP BY role
            ORDER BY COUNT(*) DESC
            ''')

            roles = cursor.fetchall()

            print("\n" + _t("parking.section.users_by_role") + ":")
            print("-" * 50)
            for role, count in roles:
                print(f"{role}: {count}")

            # Permits by zone
            cursor.execute('''
            SELECT zone, COUNT(*)
            FROM parking_permits
            GROUP BY zone
            ORDER BY COUNT(*) DESC
            ''')

            zones = cursor.fetchall()

            print("\n" + _t("parking.section.permits_by_zone") + ":")
            print("-" * 50)
            for zone, count in zones:
                zone_name = PARKING_ZONES.get(zone, {}).get('name', 'Unknown')
                print(f"Zone {zone} ({zone_name}): {count}")

        else:
            print(_t("common.invalid_choice"))
            conn.close()
            return

        # Ask if user wants to export the report
        export = input("\nExport this report? (y/n): ")
        if export.lower() == 'y':
            print("\n" + _t("parking.section.export_format") + ":")
            print("1. " + _t("parking.menu.csv"))
            print("2. " + _t("parking.menu.pdf"))

            format_choice = input("Enter your choice (1-2): ")

            if format_choice == '1':
                filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
                file_path = get_file_path('CSV', filename)
                print(f"Report exported to {file_path}")
            elif format_choice == '2':
                filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                file_path = get_file_path('PDF', filename)
                print(f"Report exported to {file_path}")

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in generate_user_activity_report: {e}")
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in generate_user_activity_report: {e}")
        print(f"An unexpected error occurred: {e}")
