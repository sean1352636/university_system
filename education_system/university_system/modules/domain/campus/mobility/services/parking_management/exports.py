import os
import csv
import logging
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.core.i18n import get_text
from education_system.university_system.infrastructure.logging.log_config import configure_logging
from education_system.university_system.modules.domain.campus.mobility.services.parking_management.constants import PARKING_ZONES
from education_system.university_system.modules.domain.campus.mobility.services.parking_management.helpers import get_file_path
from education_system.university_system.modules.domain.campus.mobility.services.parking_management import core

_t = get_text
logger = configure_logging(name=__name__)


def export_permits(format_type):
    auth = core.auth

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get permits with vehicle info
        cursor.execute('''
        SELECT
            p.permit_id, p.user_id, p.full_name, p.email,
            p.zone, p.permit_type, p.start_date, p.end_date,
            p.active_status, p.issue_date,
            v.license_plate, v.make, v.model, v.year
        FROM parking_permits p
        LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
        ORDER BY p.issue_date DESC
        ''')

        permits = cursor.fetchall()

        if not permits:
            print(_t("parking.export.no_permits"))
            conn.close()
            return

        filename = f"parking_permits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
        file_path = get_file_path(format_type.upper(), filename)

        if format_type == 'csv':
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow([
                    'Permit ID', 'User ID', 'Name', 'Email', 'Zone',
                    'Permit Type', 'Start Date', 'End Date', 'Status',
                    'Issue Date', 'License Plate', 'Vehicle Make', 'Vehicle Model', 'Year'
                ])

                # Write data
                for permit in permits:
                    writer.writerow(permit)

            print(f"Permits exported to {file_path}")

        elif format_type == 'excel':
            # Create DataFrame
            df = pd.DataFrame(permits, columns=[
                'Permit ID', 'User ID', 'Name', 'Email', 'Zone',
                'Permit Type', 'Start Date', 'End Date', 'Status',
                'Issue Date', 'License Plate', 'Vehicle Make', 'Vehicle Model', 'Year'
            ])

            # Write to Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Permits', index=False)

                # Create summary sheet
                summary_df = df.groupby(['Zone', 'Permit Type']).size().reset_index(name='Count')
                summary_df.to_excel(writer, sheet_name='Summary', index=False)

            print(f"Permits exported to {file_path}")

        elif format_type == 'pdf':
            # Create PDF document
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            elements = []

            # Add title
            styles = getSampleStyleSheet()
            elements.append(Paragraph("Parking Permits Export", styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Paragraph(" ", styles['Normal']))

            # Create table data
            data = [['Permit ID', 'Name', 'Zone', 'Type', 'Valid Period', 'Status', 'Vehicle']]

            for permit in permits:
                vehicle_info = f"{permit[11]} {permit[12]} ({permit[10]})" if permit[10] else "N/A"
                valid_period = f"{permit[6]} to {permit[7]}"

                data.append([
                    permit[0],  # Permit ID
                    permit[2],  # Name
                    permit[4],  # Zone
                    permit[5],  # Type
                    valid_period,
                    permit[8],  # Status
                    vehicle_info
                ])

            # Create table
            table = Table(data, colWidths=[60, 100, 40, 60, 100, 50, 100])

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

            print(f"Permits exported to {file_path}")

        elif format_type == 'txt':
            with open(file_path, 'w') as txtfile:
                txtfile.write("PARKING PERMITS EXPORT\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                for permit in permits:
                    txtfile.write(f"Permit ID: {permit[0]}\n")
                    txtfile.write(f"User: {permit[2]} (ID: {permit[1]})\n")
                    txtfile.write(f"Email: {permit[3]}\n")
                    txtfile.write(f"Zone: {permit[4]} - {PARKING_ZONES[permit[4]]['name']}\n")
                    txtfile.write(f"Type: {permit[5]}\n")
                    txtfile.write(f"Valid: {permit[6]} to {permit[7]}\n")
                    txtfile.write(f"Status: {permit[8]}\n")
                    txtfile.write(f"Issued: {permit[9]}\n")

                    if permit[10]:
                        txtfile.write(f"Vehicle: {permit[11]} {permit[12]} ({permit[10]})\n")
                    else:
                        txtfile.write("Vehicle: Not assigned\n")

                    txtfile.write("-" * 60 + "\n")

            print(f"Permits exported to {file_path}")

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in export_permits: {e}")
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Error in export_permits: {e}")
        print(_t("parking.error.exporting_permits") + f": {e}")


def export_vehicles(format_type):
    auth = core.auth

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get vehicles with owner info
        cursor.execute('''
        SELECT
            v.vehicle_id, v.license_plate, v.make, v.model,
            v.year, v.color, v.vehicle_type, v.registration_state,
            u.id as owner_id, u.first_name, u.last_name, u.email
        FROM vehicles v
        LEFT JOIN users u ON v.owner_id = u.id
        ORDER BY v.vehicle_id
        ''')

        vehicles = cursor.fetchall()

        if not vehicles:
            print(_t("parking.export.no_vehicles"))
            conn.close()
            return

        filename = f"vehicles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
        file_path = get_file_path(format_type.upper(), filename)

        if format_type == 'csv':
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow([
                    'Vehicle ID', 'License Plate', 'Make', 'Model', 'Year',
                    'Color', 'Type', 'Registration State', 'Owner ID',
                    'Owner First Name', 'Owner Last Name', 'Owner Email'
                ])

                # Write data
                for vehicle in vehicles:
                    writer.writerow(vehicle)

            print(f"Vehicles exported to {file_path}")

        elif format_type == 'excel':
            # Create DataFrame
            df = pd.DataFrame(vehicles, columns=[
                'Vehicle ID', 'License Plate', 'Make', 'Model', 'Year',
                'Color', 'Type', 'Registration State', 'Owner ID',
                'Owner First Name', 'Owner Last Name', 'Owner Email'
            ])

            # Write to Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Vehicles', index=False)

                # Create summary sheet
                summary_data = {
                    'Vehicle Type': df['Type'].value_counts(),
                    'Make': df['Make'].value_counts().head(10),
                    'Registration State': df['Registration State'].value_counts()
                }

                for sheet_name, data in summary_data.items():
                    summary_df = pd.DataFrame(data).reset_index()
                    summary_df.columns = [sheet_name, 'Count']
                    summary_df.to_excel(writer, sheet_name=sheet_name, index=False)

            print(f"Vehicles exported to {file_path}")

        elif format_type == 'pdf':
            # Create PDF document
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            elements = []

            # Add title
            styles = getSampleStyleSheet()
            elements.append(Paragraph("Vehicles Export", styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Paragraph(" ", styles['Normal']))

            # Create table data
            data = [['Vehicle ID', 'License Plate', 'Make/Model', 'Year', 'Type', 'Owner']]

            for vehicle in vehicles:
                owner_info = f"{vehicle[9]} {vehicle[10]}" if vehicle[9] else "N/A"

                data.append([
                    vehicle[0],  # Vehicle ID
                    vehicle[1],  # License Plate
                    f"{vehicle[2]} {vehicle[3]}",  # Make/Model
                    vehicle[4],  # Year
                    vehicle[6],  # Type
                    owner_info
                ])

            # Create table
            table = Table(data, colWidths=[60, 80, 120, 50, 80, 120])

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

            print(f"Vehicles exported to {file_path}")

        elif format_type == 'txt':
            with open(file_path, 'w') as txtfile:
                txtfile.write("VEHICLES EXPORT\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                for vehicle in vehicles:
                    txtfile.write(f"Vehicle ID: {vehicle[0]}\n")
                    txtfile.write(f"License Plate: {vehicle[1]}\n")
                    txtfile.write(f"Make/Model: {vehicle[2]} {vehicle[3]}\n")
                    txtfile.write(f"Year: {vehicle[4]}\n")
                    txtfile.write(f"Color: {vehicle[5]}\n")
                    txtfile.write(f"Type: {vehicle[6]}\n")
                    txtfile.write(f"Registration State: {vehicle[7]}\n")

                    if vehicle[9]:
                        txtfile.write(f"Owner: {vehicle[9]} {vehicle[10]} (ID: {vehicle[8]})\n")
                        txtfile.write(f"Owner Email: {vehicle[11]}\n")
                    else:
                        txtfile.write("Owner: Not assigned\n")

                    txtfile.write("-" * 60 + "\n")

            print(f"Vehicles exported to {file_path}")

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in export_vehicles: {e}")
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Error in export_vehicles: {e}")
        print(_t("parking.error.exporting_vehicles") + f": {e}")


def export_violations(format_type):
    auth = core.auth

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get violations with officer info
        cursor.execute('''
        SELECT
            v.violation_id, v.license_plate, v.violation_type,
            v.violation_date, v.fine_amount, v.payment_status,
            v.location, v.vehicle_id,
            u.first_name || ' ' || u.last_name as officer_name
        FROM parking_violations v
        LEFT JOIN users u ON v.officer_id = u.id
        ORDER BY v.violation_date DESC
        ''')

        violations = cursor.fetchall()

        if not violations:
            print(_t("parking.export.no_violations"))
            conn.close()
            return

        filename = f"parking_violations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
        file_path = get_file_path(format_type.upper(), filename)

        if format_type == 'csv':
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow([
                    'Violation ID', 'License Plate', 'Violation Type',
                    'Date/Time', 'Fine Amount', 'Payment Status',
                    'Location', 'Vehicle ID', 'Officer'
                ])

                # Write data
                for violation in violations:
                    writer.writerow(violation)

            print(f"Violations exported to {file_path}")

        elif format_type == 'excel':
            # Create DataFrame
            df = pd.DataFrame(violations, columns=[
                'Violation ID', 'License Plate', 'Violation Type',
                'Date/Time', 'Fine Amount', 'Payment Status',
                'Location', 'Vehicle ID', 'Officer'
            ])

            # Write to Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Violations', index=False)

                # Create summary sheets
                summary_data = {
                    'Violation Types': df.groupby('Violation Type')['Fine Amount'].agg(['count', 'sum']),
                    'Payment Status': df.groupby('Payment Status')['Fine Amount'].agg(['count', 'sum']),
                    'Officers': df.groupby('Officer')['Fine Amount'].agg(['count', 'sum'])
                }

                for sheet_name, data in summary_data.items():
                    summary_df = data.reset_index()
                    summary_df.columns = [sheet_name.rstrip('s'), 'Count', 'Total Fines']
                    summary_df.to_excel(writer, sheet_name=sheet_name, index=False)

            print(f"Violations exported to {file_path}")

        elif format_type == 'pdf':
            # Create PDF document
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            elements = []

            # Add title
            styles = getSampleStyleSheet()
            elements.append(Paragraph("Parking Violations Export", styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Paragraph(" ", styles['Normal']))

            # Create table data
            data = [['Violation ID', 'License Plate', 'Type', 'Date', 'Fine', 'Status', 'Location']]

            for violation in violations:
                data.append([
                    violation[0],  # Violation ID
                    violation[1],  # License Plate
                    violation[2][:15] + '...' if len(violation[2]) > 15 else violation[2],  # Type (truncated)
                    violation[3][:10],  # Date only
                    f"£{violation[4]:.2f}",  # Fine
                    violation[5],  # Status
                    violation[6][:20] + '...' if len(violation[6]) > 20 else violation[6]  # Location (truncated)
                ])

            # Create table
            table = Table(data, colWidths=[60, 70, 80, 60, 50, 60, 120])

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
                ('ALIGN', (4, 1), (4, -1), 'RIGHT')  # Right-align fine amounts
            ]))

            elements.append(table)

            # Build the PDF
            doc.build(elements)

            print(f"Violations exported to {file_path}")

        elif format_type == 'txt':
            with open(file_path, 'w') as txtfile:
                txtfile.write("PARKING VIOLATIONS EXPORT\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                total_fines = 0
                paid_fines = 0
                unpaid_fines = 0

                for violation in violations:
                    txtfile.write(f"Violation ID: {violation[0]}\n")
                    txtfile.write(f"License Plate: {violation[1]}\n")
                    txtfile.write(f"Type: {violation[2]}\n")
                    txtfile.write(f"Date/Time: {violation[3]}\n")
                    txtfile.write(f"Fine Amount: £{violation[4]:.2f}\n")
                    txtfile.write(f"Payment Status: {violation[5]}\n")
                    txtfile.write(f"Location: {violation[6]}\n")
                    txtfile.write(f"Officer: {violation[8]}\n")
                    txtfile.write("-" * 60 + "\n")

                    total_fines += violation[4]
                    if violation[5] == 'Paid':
                        paid_fines += violation[4]
                    else:
                        unpaid_fines += violation[4]

                # Add summary
                txtfile.write("\nSUMMARY\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Total Violations: {len(violations)}\n")
                txtfile.write(f"Total Fines: £{total_fines:.2f}\n")
                txtfile.write(f"Paid Fines: £{paid_fines:.2f}\n")
                txtfile.write(f"Unpaid Fines: £{unpaid_fines:.2f}\n")

            print(f"Violations exported to {file_path}")

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in export_violations: {e}")
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Error in export_violations: {e}")
        print(_t("parking.error.exporting_violations") + f": {e}")


def export_parking_lots(format_type):
    auth = core.auth

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get parking lots
        cursor.execute('''
        SELECT * FROM parking_lots
        ORDER BY lot_id
        ''')

        lots = cursor.fetchall()

        if not lots:
            print(_t("parking.export.no_parking_lots"))
            conn.close()
            return

        filename = f"parking_lots_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
        file_path = get_file_path(format_type.upper(), filename)

        if format_type == 'csv':
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow([
                    'Lot ID', 'Lot Name', 'Location', 'Total Spaces',
                    'Available Spaces', 'Zone', 'Hours of Operation'
                ])

                # Write data
                for lot in lots:
                    writer.writerow(lot)

            print(f"Parking lots exported to {file_path}")

        elif format_type == 'excel':
            # Create DataFrame
            df = pd.DataFrame(lots, columns=[
                'Lot ID', 'Lot Name', 'Location', 'Total Spaces',
                'Available Spaces', 'Zone', 'Hours of Operation'
            ])

            # Write to Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Parking Lots', index=False)

                # Create occupancy summary
                df['Occupied Spaces'] = df['Total Spaces'] - df['Available Spaces']
                df['Occupancy %'] = (df['Occupied Spaces'] / df['Total Spaces'] * 100).round(1)

                summary_df = df[['Lot ID', 'Lot Name', 'Total Spaces', 'Occupied Spaces', 'Available Spaces', 'Occupancy %']]
                summary_df.to_excel(writer, sheet_name='Occupancy Summary', index=False)

                # Zone summary
                zone_summary = df.groupby('Zone').agg({
                    'Total Spaces': 'sum',
                    'Available Spaces': 'sum'
                }).reset_index()
                zone_summary['Occupied Spaces'] = zone_summary['Total Spaces'] - zone_summary['Available Spaces']
                zone_summary['Occupancy %'] = (zone_summary['Occupied Spaces'] / zone_summary['Total Spaces'] * 100).round(1)
                zone_summary.to_excel(writer, sheet_name='Zone Summary', index=False)

            print(f"Parking lots exported to {file_path}")

        elif format_type == 'pdf':
            # Create PDF document
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            elements = []

            # Add title
            styles = getSampleStyleSheet()
            elements.append(Paragraph("Parking Lots Export", styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Paragraph(" ", styles['Normal']))

            # Create table data
            data = [['Lot ID', 'Lot Name', 'Location', 'Total', 'Available', 'Zone', 'Hours']]

            for lot in lots:
                data.append([
                    lot[0],  # Lot ID
                    lot[1],  # Lot Name
                    lot[2],  # Location
                    lot[3],  # Total Spaces
                    lot[4],  # Available Spaces
                    lot[5],  # Zone
                    lot[6]   # Hours
                ])

            # Create table
            table = Table(data, colWidths=[50, 100, 100, 50, 60, 40, 100])

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
                ('ALIGN', (3, 1), (4, -1), 'CENTER')  # Center numeric columns
            ]))

            elements.append(table)

            # Add summary
            elements.append(Paragraph(" ", styles['Normal']))
            elements.append(Paragraph("Summary", styles['Heading2']))

            total_spaces = sum(lot[3] for lot in lots)
            total_available = sum(lot[4] for lot in lots)
            total_occupied = total_spaces - total_available
            occupancy_rate = (total_occupied / total_spaces * 100) if total_spaces > 0 else 0

            summary_text = f"""
            Total Parking Lots: {len(lots)}<br/>
            Total Spaces: {total_spaces}<br/>
            Occupied Spaces: {total_occupied}<br/>
            Available Spaces: {total_available}<br/>
            Overall Occupancy Rate: {occupancy_rate:.1f}%
            """

            elements.append(Paragraph(summary_text, styles['Normal']))

            # Build the PDF
            doc.build(elements)

            print(f"Parking lots exported to {file_path}")

        elif format_type == 'txt':
            with open(file_path, 'w') as txtfile:
                txtfile.write("PARKING LOTS EXPORT\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                total_spaces = 0
                total_available = 0

                for lot in lots:
                    txtfile.write(f"Lot ID: {lot[0]}\n")
                    txtfile.write(f"Lot Name: {lot[1]}\n")
                    txtfile.write(f"Location: {lot[2]}\n")
                    txtfile.write(f"Total Spaces: {lot[3]}\n")
                    txtfile.write(f"Available Spaces: {lot[4]}\n")
                    txtfile.write(f"Zone: {lot[5]} - {PARKING_ZONES[lot[5]]['name']}\n")
                    txtfile.write(f"Hours of Operation: {lot[6]}\n")

                    occupancy = ((lot[3] - lot[4]) / lot[3] * 100) if lot[3] > 0 else 0
                    txtfile.write(f"Occupancy Rate: {occupancy:.1f}%\n")
                    txtfile.write("-" * 60 + "\n")

                    total_spaces += lot[3]
                    total_available += lot[4]

                # Add summary
                txtfile.write("\nSUMMARY\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Total Parking Lots: {len(lots)}\n")
                txtfile.write(f"Total Spaces: {total_spaces}\n")
                txtfile.write(f"Total Available: {total_available}\n")
                txtfile.write(f"Total Occupied: {total_spaces - total_available}\n")

                overall_occupancy = ((total_spaces - total_available) / total_spaces * 100) if total_spaces > 0 else 0
                txtfile.write(f"Overall Occupancy Rate: {overall_occupancy:.1f}%\n")

            print(f"Parking lots exported to {file_path}")

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in export_parking_lots: {e}")
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Error in export_parking_lots: {e}")
        print(_t("parking.error.exporting_lots") + f": {e}")


def export_users(format_type):
    auth = core.auth

    # Check permission
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return

    if not auth.check_permission('export_data'):
        print(_t("parking.auth.no_permission"))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if parking_permits table has user_id column
        cursor.execute("PRAGMA table_info(parking_permits)")
        permit_columns = [col[1] for col in cursor.fetchall()]
        has_user_id = 'user_id' in permit_columns

        # Get users with parking-related data
        if has_user_id:
            # Original query with user_id
            cursor.execute('''
            SELECT
                u.id, u.username, u.first_name, u.last_name, u.email, u.role,
                COUNT(DISTINCT p.permit_id) as permit_count,
                COUNT(DISTINCT v.vehicle_id) as vehicle_count,
                COUNT(DISTINCT vl.violation_id) as violation_count,
                SUM(CASE WHEN vl.payment_status = 'Unpaid' THEN vl.fine_amount ELSE 0 END) as unpaid_fines
            FROM users u
            LEFT JOIN parking_permits p ON u.id = p.user_id
            LEFT JOIN vehicles v ON u.id = v.owner_id
            LEFT JOIN parking_violations vl ON v.vehicle_id = vl.vehicle_id
            GROUP BY u.id
            ORDER BY u.last_name, u.first_name
            ''')
        else:
            # Alternative query without user_id - match by email/name
            cursor.execute('''
            SELECT
                u.id, u.username, u.first_name, u.last_name, u.email, u.role,
                COUNT(DISTINCT p.permit_id) as permit_count,
                COUNT(DISTINCT v.vehicle_id) as vehicle_count,
                COUNT(DISTINCT vl.violation_id) as violation_count,
                SUM(CASE WHEN vl.payment_status = 'Unpaid' THEN vl.fine_amount ELSE 0 END) as unpaid_fines
            FROM users u
            LEFT JOIN parking_permits p ON u.email = p.email OR (u.first_name || ' ' || u.last_name) = p.full_name
            LEFT JOIN vehicles v ON u.id = v.owner_id
            LEFT JOIN parking_violations vl ON v.vehicle_id = vl.vehicle_id
            GROUP BY u.id
            ORDER BY u.last_name, u.first_name
            ''')

        users = cursor.fetchall()

        if not users:
            print(_t("parking.export.no_users"))
            conn.close()
            return

        filename = f"parking_users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
        file_path = get_file_path(format_type.upper(), filename)

        if format_type == 'csv':
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow([
                    'User ID', 'Username', 'First Name', 'Last Name', 'Email', 'Role',
                    'Permits', 'Vehicles', 'Violations', 'Unpaid Fines'
                ])

                # Write data
                for user in users:
                    writer.writerow(user)

            print(f"Users exported to {file_path}")

        elif format_type == 'excel':
            # Create DataFrame
            df = pd.DataFrame(users, columns=[
                'User ID', 'Username', 'First Name', 'Last Name', 'Email', 'Role',
                'Permits', 'Vehicles', 'Violations', 'Unpaid Fines'
            ])

            # Write to Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Users', index=False)

                # Create role summary
                role_summary = df.groupby('Role').agg({
                    'User ID': 'count',
                    'Permits': 'sum',
                    'Vehicles': 'sum',
                    'Violations': 'sum',
                    'Unpaid Fines': 'sum'
                }).reset_index()
                role_summary.columns = ['Role', 'User Count', 'Total Permits', 'Total Vehicles', 'Total Violations', 'Total Unpaid Fines']
                role_summary.to_excel(writer, sheet_name='Role Summary', index=False)

            print(f"Users exported to {file_path}")

        elif format_type == 'pdf':
            # Create PDF document
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            elements = []

            # Add title
            styles = getSampleStyleSheet()
            elements.append(Paragraph("Parking System Users Export", styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Paragraph(" ", styles['Normal']))

            # Create table data
            data = [['ID', 'Name', 'Username', 'Role', 'Permits', 'Vehicles', 'Violations', 'Unpaid']]

            for user in users:
                data.append([
                    user[0],  # ID
                    f"{user[2]} {user[3]}",  # Name
                    user[1],  # Username
                    user[5],  # Role
                    user[6],  # Permits
                    user[7],  # Vehicles
                    user[8],  # Violations
                    f"£{user[9]:.2f}" if user[9] else "£0.00"  # Unpaid fines
                ])

            # Create table
            table = Table(data, colWidths=[40, 100, 80, 60, 50, 50, 60, 60])

            # Style the table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (4, 1), (7, -1), 'CENTER')  # Center numeric columns
            ]))

            elements.append(table)

            # Build the PDF
            doc.build(elements)

            print(f"Users exported to {file_path}")

        elif format_type == 'txt':
            with open(file_path, 'w') as txtfile:
                txtfile.write("PARKING SYSTEM USERS EXPORT\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                total_permits = 0
                total_vehicles = 0
                total_violations = 0
                total_unpaid = 0

                for user in users:
                    txtfile.write(f"User ID: {user[0]}\n")
                    txtfile.write(f"Username: {user[1]}\n")
                    txtfile.write(f"Name: {user[2]} {user[3]}\n")
                    txtfile.write(f"Email: {user[4]}\n")
                    txtfile.write(f"Role: {user[5]}\n")
                    txtfile.write(f"Active Permits: {user[6]}\n")
                    txtfile.write(f"Registered Vehicles: {user[7]}\n")
                    txtfile.write(f"Total Violations: {user[8]}\n")
                    txtfile.write(f"Unpaid Fines: £{user[9]:.2f}\n")
                    txtfile.write("-" * 60 + "\n")

                    total_permits += user[6]
                    total_vehicles += user[7]
                    total_violations += user[8]
                    total_unpaid += user[9] if user[9] else 0

                # Add summary
                txtfile.write("\nSUMMARY\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Total Users: {len(users)}\n")
                txtfile.write(f"Total Permits: {total_permits}\n")
                txtfile.write(f"Total Vehicles: {total_vehicles}\n")
                txtfile.write(f"Total Violations: {total_violations}\n")
                txtfile.write(f"Total Unpaid Fines: £{total_unpaid:.2f}\n")

            print(f"Users exported to {file_path}")

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in export_users: {e}")
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Error in export_users: {e}")
        print(_t("parking.error.exporting_users") + f": {e}")


def export_data(format_type):
    """Export parking data in the specified format"""
    auth = core.auth

    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to export data")
        print(_t("parking.auth.login_required"))
        return

    if not auth.check_permission('export_data'):
        logging.warning(f"User {auth.current_user['username']} attempted to export data without permission")
        print(_t("parking.auth.no_permission"))
        return

    print("\n" + _t("parking.section.export_options") + ":")
    print("1. " + _t("parking.menu.permits"))
    print("2. " + _t("parking.menu.vehicles"))
    print("3. " + _t("parking.menu.violations"))
    print("4. " + _t("parking.menu.parking_lots"))
    print("5. " + _t("parking.menu.users"))

    choice = input("Enter your choice (1-5): ")

    if choice == '1':
        export_permits(format_type)
    elif choice == '2':
        export_vehicles(format_type)
    elif choice == '3':
        export_violations(format_type)
    elif choice == '4':
        export_parking_lots(format_type)
    elif choice == '5':
        export_users(format_type)
    else:
        print(_t("common.invalid_choice"))
