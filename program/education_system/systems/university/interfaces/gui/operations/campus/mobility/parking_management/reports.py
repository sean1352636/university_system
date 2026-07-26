"""Reports and analytics mixin for ParkingManagementGUI."""
import html
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from datetime import datetime
import logging
import io
import sys

from education_system.systems.university.interfaces.gui.operations.campus.mobility.parking_management import get_connection, _t, PARKING_ZONES, TEMPLATE_AVAILABLE, render_template


class ReportsMixin:
    """Mixin providing reporting and analytics functionality."""

    def generate_permit_report(self):
        """Generate permit report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Generate comprehensive permit report
            output = []
            output.append("PARKING PERMIT REPORT")
            output.append("=" * 80)
            output.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            output.append("")

            # Active Permits
            output.append("ACTIVE PERMITS")
            output.append("-" * 80)
            cursor.execute('''
                SELECT p.permit_id, p.full_name, p.zone, p.permit_type,
                       p.issue_date, p.end_date, v.license_plate
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE p.active_status = 'Active'
                ORDER BY p.zone, p.issue_date DESC
            ''')
            active_permits = cursor.fetchall()

            if active_permits:
                output.append(f"{'ID':<12} {'Name':<25} {'Zone':<6} {'Type':<12} {'License':<12} {'Issued':<12} {'Expires':<12}")
                output.append("-" * 80)
                for permit in active_permits:
                    output.append(f"{permit[0]:<12} {permit[1]:<25} {permit[2]:<6} {permit[3]:<12} {permit[6] or 'N/A':<12} {permit[4]:<12} {permit[5]:<12}")
                output.append(f"\nTotal Active Permits: {len(active_permits)}")
            else:
                output.append("No active permits found.")

            output.append("\n")

            # Permits by Zone
            output.append("PERMITS BY ZONE")
            output.append("-" * 80)
            cursor.execute('''
                SELECT zone, COUNT(*) as count,
                       SUM(CASE WHEN active_status = 'Active' THEN 1 ELSE 0 END) as active
                FROM parking_permits
                GROUP BY zone
                ORDER BY zone
            ''')
            zone_stats = cursor.fetchall()

            if zone_stats:
                output.append(f"{'Zone':<10} {'Total':<10} {'Active':<10}")
                output.append("-" * 30)
                for stat in zone_stats:
                    output.append(f"{stat[0]:<10} {stat[1]:<10} {stat[2]:<10}")
            else:
                output.append("No zone data available.")

            output.append("\n")

            # Permits by Type
            output.append("PERMITS BY TYPE")
            output.append("-" * 80)
            cursor.execute('''
                SELECT permit_type, COUNT(*) as count,
                       SUM(CASE WHEN active_status = 'Active' THEN 1 ELSE 0 END) as active
                FROM parking_permits
                GROUP BY permit_type
                ORDER BY count DESC
            ''')
            type_stats = cursor.fetchall()

            if type_stats:
                output.append(f"{'Type':<15} {'Total':<10} {'Active':<10}")
                output.append("-" * 35)
                for stat in type_stats:
                    output.append(f"{stat[0]:<15} {stat[1]:<10} {stat[2]:<10}")
            else:
                output.append("No type data available.")

            output.append("\n")

            # Expiring Soon (within 30 days)
            output.append("PERMITS EXPIRING SOON (Next 30 Days)")
            output.append("-" * 80)
            cursor.execute('''
                SELECT permit_id, full_name, zone, permit_type, end_date
                FROM parking_permits
                WHERE active_status = 'Active'
                AND date(end_date) BETWEEN date('now') AND date('now', '+30 days')
                ORDER BY end_date
            ''')
            expiring = cursor.fetchall()

            if expiring:
                output.append(f"{'ID':<12} {'Name':<30} {'Zone':<6} {'Type':<12} {'Expires':<12}")
                output.append("-" * 72)
                for permit in expiring:
                    output.append(f"{permit[0]:<12} {permit[1]:<30} {permit[2]:<6} {permit[3]:<12} {permit[4]:<12}")
                output.append(f"\nTotal Expiring Soon: {len(expiring)}")
            else:
                output.append("No permits expiring in the next 30 days.")

            conn.close()

            # Show in dialog
            self.show_text_dialog("Parking Permit Report", "\n".join(output))
        except Exception as e:
            logging.error(f"Error generating permit report: {e}")
            messagebox.showerror("Error", f"Failed to generate permit report: {e}")

    def generate_violation_report(self):
        """Generate violation report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            output = []
            output.append("PARKING VIOLATION REPORT")
            output.append("=" * 80)
            output.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            output.append("")

            # All Violations Summary
            output.append("VIOLATION SUMMARY")
            output.append("-" * 80)
            cursor.execute('''
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN payment_status = 'Paid' THEN 1 ELSE 0 END) as paid,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN 1 ELSE 0 END) as unpaid,
                       SUM(CASE WHEN payment_status = 'Pending' THEN 1 ELSE 0 END) as pending,
                       SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Paid' THEN fine_amount ELSE 0 END) as collected,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN fine_amount ELSE 0 END) as outstanding
                FROM parking_violations
            ''')
            summary = cursor.fetchone()

            output.append(f"Total Violations: {summary[0] or 0}")
            output.append(f"  - Paid: {summary[1] or 0}")
            output.append(f"  - Unpaid: {summary[2] or 0}")
            output.append(f"  - Pending: {summary[3] or 0}")
            output.append(f"Total Fines: £{summary[4] or 0:.2f}")
            output.append(f"  - Collected: £{summary[5] or 0:.2f}")
            output.append(f"  - Outstanding: £{summary[6] or 0:.2f}")

            output.append("\n")

            # Violations by Type
            output.append("VIOLATIONS BY TYPE")
            output.append("-" * 80)
            cursor.execute('''
                SELECT violation_type, COUNT(*) as count,
                       SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN 1 ELSE 0 END) as unpaid
                FROM parking_violations
                GROUP BY violation_type
                ORDER BY count DESC
            ''')
            type_stats = cursor.fetchall()

            if type_stats:
                output.append(f"{'Type':<30} {'Count':<10} {'Total Fines':<15} {'Unpaid':<10}")
                output.append("-" * 65)
                for stat in type_stats:
                    output.append(f"{stat[0]:<30} {stat[1]:<10} £{stat[2]:<14.2f} {stat[3]:<10}")
            else:
                output.append("No violation data available.")

            output.append("\n")

            # Recent Violations (last 30 days)
            output.append("RECENT VIOLATIONS (Last 30 Days)")
            output.append("-" * 80)
            cursor.execute('''
                SELECT v.violation_id, v.license_plate, v.violation_type,
                       v.violation_date, v.fine_amount, v.payment_status, v.location
                FROM parking_violations v
                WHERE date(v.violation_date) >= date('now', '-30 days')
                ORDER BY v.violation_date DESC
                LIMIT 50
            ''')
            recent = cursor.fetchall()

            if recent:
                output.append(f"{'ID':<12} {'Plate':<10} {'Type':<25} {'Date':<12} {'Fine':<10} {'Status':<10}")
                output.append("-" * 80)
                for violation in recent:
                    output.append(f"{violation[0]:<12} {violation[1]:<10} {violation[2]:<25} {violation[3]:<12} £{violation[4]:<9.2f} {violation[5]:<10}")
                output.append(f"\nTotal Recent Violations: {len(recent)}")
            else:
                output.append("No recent violations found.")

            output.append("\n")

            # Top Violators
            output.append("TOP VIOLATORS")
            output.append("-" * 80)
            cursor.execute('''
                SELECT license_plate, COUNT(*) as violations,
                       SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN fine_amount ELSE 0 END) as outstanding
                FROM parking_violations
                GROUP BY license_plate
                HAVING violations > 1
                ORDER BY violations DESC
                LIMIT 10
            ''')
            top_violators = cursor.fetchall()

            if top_violators:
                output.append(f"{'License Plate':<15} {'Violations':<12} {'Total Fines':<15} {'Outstanding':<15}")
                output.append("-" * 57)
                for violator in top_violators:
                    output.append(f"{violator[0]:<15} {violator[1]:<12} £{violator[2]:<14.2f} £{violator[3]:<14.2f}")
            else:
                output.append("No repeat violators found.")

            conn.close()

            self.show_text_dialog("Parking Violation Report", "\n".join(output))
        except Exception as e:
            logging.error(f"Error generating violation report: {e}")
            messagebox.showerror("Error", f"Failed to generate violation report: {e}")

    def show_analytics(self):
        """Show analytics dashboard"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            output = []
            output.append("PARKING ANALYTICS DASHBOARD")
            output.append("=" * 80)
            output.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            output.append("")

            # Overall Statistics
            output.append("OVERALL STATISTICS")
            output.append("-" * 80)

            cursor.execute("SELECT COUNT(*) FROM parking_permits WHERE active_status = 'Active'")
            active_permits = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM parking_permits")
            total_permits = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM vehicles")
            total_vehicles = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM parking_violations WHERE payment_status = 'Unpaid'")
            unpaid_violations = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(fine_amount) FROM parking_violations WHERE payment_status = 'Unpaid'")
            unpaid_fines = cursor.fetchone()[0] or 0

            cursor.execute("SELECT SUM(total_spaces) FROM parking_lots")
            total_spaces = cursor.fetchone()[0] or 0

            cursor.execute("SELECT SUM(available_spaces) FROM parking_lots")
            available_spaces = cursor.fetchone()[0] or 0

            output.append(f"Active Permits: {active_permits}")
            output.append(f"Total Permits (All Time): {total_permits}")
            output.append(f"Registered Vehicles: {total_vehicles}")
            output.append(f"Unpaid Violations: {unpaid_violations}")
            output.append(f"Unpaid Fines: £{unpaid_fines:.2f}")
            output.append(f"Total Parking Spaces: {total_spaces}")
            output.append(f"Available Spaces: {available_spaces}")
            output.append(f"Occupied Spaces: {total_spaces - available_spaces}")
            if total_spaces > 0:
                output.append(f"Occupancy Rate: {((total_spaces - available_spaces) / total_spaces * 100):.1f}%")

            output.append("\n")

            # Monthly Trends
            output.append("MONTHLY TRENDS (Last 6 Months)")
            output.append("-" * 80)
            cursor.execute('''
                SELECT strftime('%Y-%m', violation_date) as month,
                       COUNT(*) as violations,
                       SUM(fine_amount) as fines
                FROM parking_violations
                WHERE date(violation_date) >= date('now', '-6 months')
                GROUP BY month
                ORDER BY month DESC
            ''')
            monthly = cursor.fetchall()

            if monthly:
                output.append(f"{'Month':<10} {'Violations':<15} {'Fines':<15}")
                output.append("-" * 40)
                for month in monthly:
                    output.append(f"{month[0]:<10} {month[1]:<15} £{month[2]:<14.2f}")
            else:
                output.append("No monthly data available.")

            output.append("\n")

            # Zone Utilization
            output.append("ZONE UTILIZATION")
            output.append("-" * 80)
            cursor.execute('''
                SELECT zone, COUNT(*) as active_permits
                FROM parking_permits
                WHERE active_status = 'Active'
                GROUP BY zone
                ORDER BY active_permits DESC
            ''')
            zone_util = cursor.fetchall()

            if zone_util:
                output.append(f"{'Zone':<10} {'Active Permits':<20}")
                output.append("-" * 30)
                for zone in zone_util:
                    output.append(f"{zone[0]:<10} {zone[1]:<20}")
            else:
                output.append("No zone utilization data available.")

            output.append("\n")

            # Revenue Analysis
            output.append("REVENUE ANALYSIS")
            output.append("-" * 80)
            cursor.execute('''
                SELECT SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Paid' THEN fine_amount ELSE 0 END) as collected,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN fine_amount ELSE 0 END) as outstanding,
                       COUNT(*) as total_violations
                FROM parking_violations
            ''')
            revenue = cursor.fetchone()

            output.append(f"Total Fines Issued: £{revenue[0] or 0:.2f}")
            output.append(f"Fines Collected: £{revenue[1] or 0:.2f}")
            output.append(f"Outstanding Fines: £{revenue[2] or 0:.2f}")
            output.append(f"Collection Rate: {((revenue[1] or 0) / (revenue[0] or 1) * 100) if (revenue[0] or 0) > 0 else 0:.1f}%")

            conn.close()

            self.show_text_dialog("Parking Analytics Dashboard", "\n".join(output))
        except Exception as e:
            logging.error(f"Error generating analytics dashboard: {e}")
            messagebox.showerror("Error", f"Failed to generate analytics: {e}")

    def generate_occupancy_report(self):
        """Generate parking lot occupancy report"""
        try:
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()

            # Generate occupancy report content
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT lot_id, lot_name, total_spaces, available_spaces, zone
            FROM parking_lots
            ORDER BY lot_id
            ''')

            lots = cursor.fetchall()

            print("PARKING LOT OCCUPANCY REPORT")
            print("=" * 60)
            print(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print()

            total_spaces = 0
            total_available = 0

            print(f"{'Lot ID':<8} {'Lot Name':<25} {'Total':<8} {'Available':<10} {'Occupied':<10} {'Rate':<8} {'Zone':<6}")
            print("-" * 75)

            for lot in lots:
                occupied = lot[2] - lot[3]
                rate = (occupied / lot[2] * 100) if lot[2] > 0 else 0

                print(f"{lot[0]:<8} {lot[1]:<25} {lot[2]:<8} {lot[3]:<10} {occupied:<10} {rate:<7.1f}% {lot[4]:<6}")

                total_spaces += lot[2]
                total_available += lot[3]

            print("-" * 75)
            total_occupied = total_spaces - total_available
            overall_rate = (total_occupied / total_spaces * 100) if total_spaces > 0 else 0
            print(f"{'TOTAL':<34} {total_spaces:<8} {total_available:<10} {total_occupied:<10} {overall_rate:<7.1f}%")

            report_output = buffer.getvalue()
            sys.stdout = old_stdout
            conn.close()

            self.show_text_dialog("Parking Lot Occupancy Report", report_output)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate occupancy report: {e}")

    def generate_compliance_report(self):
        """Generate compliance and audit report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            output = []
            output.append("PARKING COMPLIANCE & AUDIT REPORT")
            output.append("=" * 80)
            output.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            output.append("")

            # Permit Compliance
            output.append("PERMIT COMPLIANCE")
            output.append("-" * 80)

            cursor.execute("SELECT COUNT(*) FROM parking_permits WHERE active_status = 'Active'")
            active_permits = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM parking_permits WHERE active_status = 'Expired'")
            expired_permits = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM parking_permits
                WHERE active_status = 'Active'
                AND date(end_date) < date('now')
            ''')
            expired_not_updated = cursor.fetchone()[0]

            output.append(f"Active Permits: {active_permits}")
            output.append(f"Expired Permits: {expired_permits}")
            output.append(f"Permits Expired but Not Updated: {expired_not_updated}")
            if expired_not_updated > 0:
                output.append(f"⚠ WARNING: {expired_not_updated} permits need status update!")

            output.append("\n")

            # Violation Compliance
            output.append("VIOLATION COMPLIANCE")
            output.append("-" * 80)

            cursor.execute('''
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN payment_status = 'Paid' THEN 1 ELSE 0 END) as paid,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN 1 ELSE 0 END) as unpaid,
                       SUM(CASE WHEN date(violation_date) < date('now', '-90 days')
                           AND payment_status = 'Unpaid' THEN 1 ELSE 0 END) as overdue
                FROM parking_violations
            ''')
            viol_compliance = cursor.fetchone()

            output.append(f"Total Violations: {viol_compliance[0]}")
            output.append(f"Paid Violations: {viol_compliance[1]}")
            output.append(f"Unpaid Violations: {viol_compliance[2]}")
            output.append(f"Overdue (>90 days): {viol_compliance[3]}")
            if viol_compliance[3] > 0:
                output.append(f"⚠ WARNING: {viol_compliance[3]} violations overdue for collection!")

            output.append("\n")

            # Parking Lot Compliance
            output.append("PARKING LOT COMPLIANCE")
            output.append("-" * 80)

            cursor.execute('''
                SELECT COUNT(*) FROM parking_lots
                WHERE available_spaces < 0
            ''')
            negative_spaces = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM parking_lots
                WHERE available_spaces > total_spaces
            ''')
            invalid_spaces = cursor.fetchone()[0]

            cursor.execute('''
                SELECT lot_id, lot_name, total_spaces, available_spaces
                FROM parking_lots
                WHERE total_spaces - available_spaces > total_spaces
            ''')
            overcapacity = cursor.fetchall()

            output.append(f"Lots with Negative Available Spaces: {negative_spaces}")
            output.append(f"Lots with Invalid Space Count: {invalid_spaces}")
            output.append(f"Lots Over Capacity: {len(overcapacity)}")

            if negative_spaces > 0 or invalid_spaces > 0:
                output.append("⚠ WARNING: Data integrity issues detected!")

            output.append("\n")

            # Audit Trail
            output.append("RECENT AUDIT TRAIL (Last 30 Days)")
            output.append("-" * 80)

            try:
                cursor.execute('''
                    SELECT timestamp, activity_type, activity_description, user_id
                    FROM user_activity_log
                    WHERE date(timestamp) >= date('now', '-30 days')
                    AND (activity_type LIKE '%parking%' OR activity_description LIKE '%parking%'
                         OR activity_description LIKE '%permit%' OR activity_description LIKE '%violation%')
                    ORDER BY timestamp DESC
                    LIMIT 20
                ''')
                audit_trail = cursor.fetchall()

                if audit_trail:
                    output.append(f"{'Date':<20} {'Activity':<20} {'Description':<30} {'User ID':<10}")
                    output.append("-" * 80)
                    for entry in audit_trail:
                        desc = entry[2][:27] + "..." if len(entry[2]) > 30 else entry[2]
                        output.append(f"{entry[0]:<20} {entry[1]:<20} {desc:<30} {entry[3]:<10}")
                else:
                    output.append("No recent parking-related audit trail available.")
            except Exception:
                output.append("Audit trail not available (table may not exist)")

            conn.close()

            self.show_text_dialog("Compliance & Audit Report", "\n".join(output))
        except Exception as e:
            logging.error(f"Error generating compliance report: {e}")
            messagebox.showerror("Error", f"Failed to generate compliance report: {e}")

    def generate_revenue_report(self):
        """Generate revenue report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            output = []
            output.append("PARKING REVENUE REPORT")
            output.append("=" * 80)
            output.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            output.append("")

            # Overall Revenue Summary
            output.append("OVERALL REVENUE SUMMARY")
            output.append("-" * 80)

            cursor.execute('''
                SELECT SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Paid' THEN fine_amount ELSE 0 END) as collected,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN fine_amount ELSE 0 END) as outstanding,
                       SUM(CASE WHEN payment_status = 'Pending' THEN fine_amount ELSE 0 END) as pending,
                       COUNT(*) as total_violations
                FROM parking_violations
            ''')
            overall = cursor.fetchone()

            output.append(f"Total Fines Issued: £{overall[0] or 0:.2f}")
            output.append(f"  - Collected: £{overall[1] or 0:.2f}")
            output.append(f"  - Outstanding: £{overall[2] or 0:.2f}")
            output.append(f"  - Pending: £{overall[3] or 0:.2f}")
            output.append(f"Total Violations: {overall[4]}")
            if overall[0] and overall[0] > 0:
                output.append(f"Collection Rate: {(overall[1] / overall[0] * 100):.1f}%")

            output.append("\n")

            # Monthly Revenue Breakdown
            output.append("MONTHLY REVENUE BREAKDOWN (Last 12 Months)")
            output.append("-" * 80)

            cursor.execute('''
                SELECT strftime('%Y-%m', violation_date) as month,
                       COUNT(*) as violations,
                       SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Paid' THEN fine_amount ELSE 0 END) as collected,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN fine_amount ELSE 0 END) as outstanding
                FROM parking_violations
                WHERE date(violation_date) >= date('now', '-12 months')
                GROUP BY month
                ORDER BY month DESC
            ''')
            monthly = cursor.fetchall()

            if monthly:
                output.append(f"{'Month':<10} {'Violations':<12} {'Fines':<15} {'Collected':<15} {'Outstanding':<15}")
                output.append("-" * 67)
                for month in monthly:
                    output.append(f"{month[0]:<10} {month[1]:<12} £{month[2]:<14.2f} £{month[3]:<14.2f} £{month[4]:<14.2f}")
            else:
                output.append("No monthly revenue data available.")

            output.append("\n")

            # Revenue by Violation Type
            output.append("REVENUE BY VIOLATION TYPE")
            output.append("-" * 80)

            cursor.execute('''
                SELECT violation_type,
                       COUNT(*) as violations,
                       SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Paid' THEN fine_amount ELSE 0 END) as collected,
                       AVG(fine_amount) as avg_fine
                FROM parking_violations
                GROUP BY violation_type
                ORDER BY total_fines DESC
            ''')
            by_type = cursor.fetchall()

            if by_type:
                output.append(f"{'Type':<30} {'Count':<8} {'Total':<15} {'Collected':<15} {'Avg Fine':<12}")
                output.append("-" * 80)
                for vtype in by_type:
                    output.append(f"{vtype[0]:<30} {vtype[1]:<8} £{vtype[2]:<14.2f} £{vtype[3]:<14.2f} £{vtype[4]:<11.2f}")
            else:
                output.append("No violation type data available.")

            output.append("\n")

            # Permit Revenue Estimate
            output.append("PERMIT REVENUE ESTIMATE")
            output.append("-" * 80)

            cursor.execute('''
                SELECT zone, permit_type, COUNT(*) as count
                FROM parking_permits
                WHERE active_status = 'Active'
                GROUP BY zone, permit_type
                ORDER BY zone, permit_type
            ''')
            permits = cursor.fetchall()

            if permits:
                total_permit_revenue = 0
                output.append(f"{'Zone':<8} {'Type':<15} {'Count':<10} {'Est. Revenue':<15}")
                output.append("-" * 48)
                for permit in permits:
                    zone = permit[0]
                    ptype = permit[1]
                    count = permit[2]

                    if zone in PARKING_ZONES:
                        est_revenue = count * PARKING_ZONES[zone].get('annual_fee', 0)
                    else:
                        est_revenue = count * 200

                    total_permit_revenue += est_revenue
                    output.append(f"{zone:<8} {ptype:<15} {count:<10} £{est_revenue:<14.2f}")

                output.append("-" * 48)
                output.append(f"{'TOTAL PERMIT REVENUE':<33} £{total_permit_revenue:<14.2f}")
            else:
                output.append("No permit revenue data available.")

            conn.close()

            self.show_text_dialog("Parking Revenue Report", "\n".join(output))
        except Exception as e:
            logging.error(f"Error generating revenue report: {e}")
            messagebox.showerror("Error", f"Failed to generate revenue report: {e}")

    def generate_user_activity_report(self):
        """Generate user activity report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            output = []
            output.append("USER ACTIVITY REPORT")
            output.append("=" * 80)
            output.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            output.append("")

            # Active Permit Holders
            output.append("ACTIVE PERMIT HOLDERS")
            output.append("-" * 80)

            cursor.execute('''
                SELECT COUNT(DISTINCT full_name) as unique_users,
                       COUNT(*) as total_permits
                FROM parking_permits
                WHERE active_status = 'Active'
            ''')
            permit_users = cursor.fetchone()

            output.append(f"Unique Active Permit Holders: {permit_users[0]}")
            output.append(f"Total Active Permits: {permit_users[1]}")

            output.append("\n")

            # Recent Permit Activity
            output.append("RECENT PERMIT ACTIVITY (Last 30 Days)")
            output.append("-" * 80)

            cursor.execute('''
                SELECT permit_id, full_name, zone, permit_type, issue_date
                FROM parking_permits
                WHERE date(issue_date) >= date('now', '-30 days')
                ORDER BY issue_date DESC
                LIMIT 20
            ''')
            recent_permits = cursor.fetchall()

            if recent_permits:
                output.append(f"{'Permit ID':<12} {'Name':<30} {'Zone':<6} {'Type':<12} {'Issued':<12}")
                output.append("-" * 72)
                for permit in recent_permits:
                    output.append(f"{permit[0]:<12} {permit[1]:<30} {permit[2]:<6} {permit[3]:<12} {permit[4]:<12}")
                output.append(f"\nTotal New Permits (30 days): {len(recent_permits)}")
            else:
                output.append("No recent permit activity.")

            output.append("\n")

            # Violation Activity by User
            output.append("TOP VIOLATORS (All Time)")
            output.append("-" * 80)

            cursor.execute('''
                SELECT license_plate,
                       COUNT(*) as violations,
                       SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN fine_amount ELSE 0 END) as unpaid,
                       MAX(violation_date) as last_violation
                FROM parking_violations
                GROUP BY license_plate
                HAVING violations > 0
                ORDER BY violations DESC
                LIMIT 15
            ''')
            violators = cursor.fetchall()

            if violators:
                output.append(f"{'License Plate':<15} {'Violations':<12} {'Total Fines':<15} {'Unpaid':<15} {'Last Violation':<15}")
                output.append("-" * 72)
                for violator in violators:
                    output.append(f"{violator[0]:<15} {violator[1]:<12} £{violator[2]:<14.2f} £{violator[3]:<14.2f} {violator[4]:<15}")
            else:
                output.append("No violation activity found.")

            output.append("\n")

            # Recent User Actions
            output.append("RECENT USER ACTIONS (Last 7 Days)")
            output.append("-" * 80)

            try:
                cursor.execute('''
                    SELECT timestamp, activity_type, activity_description, user_id
                    FROM user_activity_log
                    WHERE date(timestamp) >= date('now', '-7 days')
                    AND (activity_type LIKE '%parking%' OR activity_description LIKE '%parking%'
                         OR activity_description LIKE '%permit%' OR activity_description LIKE '%violation%')
                    ORDER BY timestamp DESC
                    LIMIT 30
                ''')
                recent_actions = cursor.fetchall()

                if recent_actions:
                    output.append(f"{'Date':<20} {'Activity Type':<25} {'Description':<30} {'User ID':<10}")
                    output.append("-" * 85)
                    for action in recent_actions:
                        desc = action[2][:27] + "..." if len(action[2]) > 30 else action[2]
                        output.append(f"{action[0]:<20} {action[1]:<25} {desc:<30} {action[3]:<10}")
                else:
                    output.append("No recent parking-related user actions found.")
            except Exception:
                output.append("User activity log not available (table may not exist)")

            output.append("\n")

            # User Statistics Summary
            output.append("USER STATISTICS SUMMARY")
            output.append("-" * 80)

            cursor.execute("SELECT COUNT(DISTINCT license_plate) FROM vehicles")
            unique_vehicles = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT license_plate) FROM parking_violations")
            vehicles_with_violations = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM parking_permits
                WHERE active_status = 'Active'
                AND date(end_date) BETWEEN date('now') AND date('now', '+30 days')
            ''')
            expiring_soon = cursor.fetchone()[0]

            output.append(f"Total Registered Vehicles: {unique_vehicles}")
            output.append(f"Vehicles with Violations: {vehicles_with_violations}")
            output.append(f"Permits Expiring Soon (30 days): {expiring_soon}")

            conn.close()

            self.show_text_dialog("User Activity Report", "\n".join(output))
        except Exception as e:
            logging.error(f"Error generating user activity report: {e}")
            messagebox.showerror("Error", f"Failed to generate user activity report: {e}")

    def show_text_dialog(self, title, content):
        """Show a dialog with text content"""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("800x600")

        # Main frame
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Text widget
        text_widget = ScrolledText(main_frame)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, content)
        text_widget.config(state=tk.DISABLED)

        # Button frame
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        # Export as TXT button
        ttk.Button(button_frame, text="Export as TXT",
                  command=lambda: self.export_report_as_txt(title, content)).pack(side=tk.LEFT, padx=5)

        # Send to Admin button
        ttk.Button(button_frame, text="Send Report to Admin",
                  command=lambda: self.send_report_to_admin(title, content)).pack(side=tk.LEFT, padx=5)

        # Close button
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def export_report_as_txt(self, title, content):
        """Export report content as a text file"""
        try:
            filename = filedialog.asksaveasfilename(
                title="Save Report",
                defaultextension=".txt",
                initialfile=f"{title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )

            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"{title}\n")
                    f.write("=" * len(title) + "\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write(content)

                messagebox.showinfo("Success", f"Report exported successfully to:\n{filename}")
                logging.info(f"Report '{title}' exported to {filename}")
        except Exception as e:
            logging.error(f"Failed to export report: {e}")
            messagebox.showerror("Error", f"Failed to export report: {e}")

    def send_report_to_admin(self, title, content):
        """Send report to admin via email"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT email, first_name, last_name
                FROM users
                WHERE role = 'admin'
                AND email IS NOT NULL
                AND email != ''
                ORDER BY id
                LIMIT 1
            ''')

            admin = cursor.fetchone()
            conn.close()

            if not admin or not admin[0]:
                messagebox.showwarning("No Admin Email",
                    "No admin email address found in the system.\n"
                    "Please contact your system administrator.")
                return

            admin_email = admin[0]
            admin_name = f"{admin[1]} {admin[2]}" if admin[1] else "Administrator"

            try:
                if TEMPLATE_AVAILABLE:
                    email_subject, email_body = render_template('parking_management_report', {
                        'admin_name': admin_name,
                        'report_title': title,
                        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'report_content': html.escape(content),
                        'separator': '=' * 80
                    })
                    if not email_subject or not email_body:
                        raise ValueError("template render returned no content")
                else:
                    raise Exception("Template not available")
            except Exception as template_error:
                logging.warning(f"Failed to render template: {template_error}. Using fallback email.")
                email_subject = f"Parking Management Report: {title}"
                email_body = f"""
Dear {admin_name},

Please find the attached parking management report below.

Report: {title}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Submitted by: {self.current_user.get('name', 'System')} ({self.current_user.get('id', 'N/A')})

{'=' * 80}

{content}

{'=' * 80}

This is an automated email from the University Parking Management System.

Best regards,
Parking Management System
"""

            try:
                from education_system.systems.university.infrastructure.email.email_service import send_email

                send_email(
                    recipient_email=admin_email,
                    subject=email_subject,
                    body=email_body
                )

                messagebox.showinfo("Report Sent",
                    f"Report successfully sent to {admin_name}'s inbox.\n\n"
                    f"The admin can view this report in their email inbox within the system.")
                logging.info(f"Report '{title}' sent to admin inbox: {admin_email}")

            except Exception as email_error:
                messagebox.showwarning("Email Failed",
                    f"Could not send report to admin inbox.\n\n"
                    f"Error: {str(email_error)}\n\n"
                    f"Please use 'Export as TXT' to save the report\n"
                    f"and send it manually.")
                logging.error(f"Failed to send report to {admin_email}: {email_error}")

        except Exception as e:
            logging.error(f"Failed to send report to admin: {e}")
            messagebox.showerror("Error", f"Failed to send report to admin: {e}")
