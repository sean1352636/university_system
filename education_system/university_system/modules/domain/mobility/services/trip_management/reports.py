from education_system.university_system.modules.domain.mobility.services.trip_management import _common
from education_system.university_system.modules.domain.mobility.services.trip_management._common import (
    sqlite3, get_text, logging, datetime, os, log_create,
    REPORTS_DIR, PDF_AVAILABLE,
)
from education_system.university_system.modules.domain.mobility.services.trip_management.database import safe_db_operation, get_db_connection

# Conditional reportlab imports
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
except ImportError:
    pass


class TripReportGenerator:
    """Class to handle trip report generation in multiple formats"""

    def __init__(self, auth_instance):
        self.auth = auth_instance
        self.reports_dir = str(REPORTS_DIR)
        self.ensure_reports_directory()

    def ensure_reports_directory(self):
        """Ensure the reports directory exists"""
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            logging.info(f"Reports directory ready: {self.reports_dir}")
        except OSError as e:
            logging.error(f"Failed to create reports directory: {e}")
            raise

    def generate_filename(self, report_type, format_type):
        """Generate a unique filename for the report"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            username = self.auth.current_user['username'] if self.auth.current_user else 'unknown'
            filename = f"{report_type}_{username}_{timestamp}.{format_type.lower()}"
            return os.path.join(self.reports_dir, filename)
        except Exception as e:
            logging.error(f"Error generating filename: {e}")
            return os.path.join(self.reports_dir, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type.lower()}")

    def get_trip_summary_data(self, conn):
        """Get comprehensive trip summary data"""
        try:
            cursor = conn.cursor()

            # Get basic trip statistics
            cursor.execute('''
            SELECT
                COUNT(*) as total_trips,
                COUNT(CASE WHEN status = 'planning' THEN 1 END) as planning_trips,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open_trips,
                COUNT(CASE WHEN status = 'full' THEN 1 END) as full_trips,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_trips,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_trips,
                SUM(cost) as total_revenue_potential,
                AVG(cost) as average_cost
            FROM trips
            ''')

            summary_stats = cursor.fetchone()

            # Get detailed trip information
            cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date,
                   t.max_participants, t.cost, t.status,
                   COUNT(tp.id) as current_participants,
                   SUM(CASE WHEN tp.payment_status = 'paid' THEN t.cost ELSE 0 END) as revenue_collected,
                   u.first_name || ' ' || u.last_name as created_by_name
            FROM trips t
            LEFT JOIN trip_participants tp ON t.id = tp.trip_id AND tp.status = 'registered'
            LEFT JOIN users u ON t.created_by = u.id
            GROUP BY t.id
            ORDER BY t.start_date DESC
            ''')

            trip_details = cursor.fetchall()

            # Get participant statistics
            cursor.execute('''
            SELECT
                COUNT(*) as total_registrations,
                COUNT(CASE WHEN status = 'registered' THEN 1 END) as active_registrations,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_registrations,
                COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as paid_registrations,
                COUNT(CASE WHEN payment_status = 'pending' THEN 1 END) as pending_payments
            FROM trip_participants
            ''')

            participant_stats = cursor.fetchone()

            return {
                'summary_stats': summary_stats,
                'trip_details': trip_details,
                'participant_stats': participant_stats,
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'generated_by': self.auth.current_user['username'] if self.auth.current_user else 'Unknown'
            }

        except sqlite3.Error as e:
            logging.error(f"Database error getting trip summary data: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error getting trip summary data: {e}")
            raise

    def get_participant_report_data(self, conn, trip_id=None):
        """Get participant report data"""
        try:
            cursor = conn.cursor()

            if trip_id:
                # Specific trip participants
                cursor.execute('''
                SELECT tp.id, t.trip_name, tp.student_id,
                       s.first_name || ' ' || s.last_name as student_name,
                       s.email_address, tp.registration_date, tp.payment_status,
                       tp.status, tp.emergency_contact, tp.medical_info, tp.dietary_requirements
                FROM trip_participants tp
                JOIN trips t ON tp.trip_id = t.id
                LEFT JOIN students s ON tp.student_id = s.student_id
                WHERE tp.trip_id = ?
                ORDER BY tp.registration_date
                ''', (trip_id,))
            else:
                # All participants
                cursor.execute('''
                SELECT tp.id, t.trip_name, tp.student_id,
                       s.first_name || ' ' || s.last_name as student_name,
                       s.email_address, tp.registration_date, tp.payment_status,
                       tp.status, tp.emergency_contact, tp.medical_info, tp.dietary_requirements
                FROM trip_participants tp
                JOIN trips t ON tp.trip_id = t.id
                LEFT JOIN students s ON tp.student_id = s.student_id
                ORDER BY t.trip_name, tp.registration_date
                ''')

            participants = cursor.fetchall()

            return {
                'participants': participants,
                'trip_id': trip_id,
                'total_participants': len(participants),
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'generated_by': self.auth.current_user['username'] if self.auth.current_user else 'Unknown'
            }

        except sqlite3.Error as e:
            logging.error(f"Database error getting participant data: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error getting participant data: {e}")
            raise

    def get_financial_report_data(self, conn):
        """Get financial report data"""
        try:
            cursor = conn.cursor()

            # Revenue summary
            cursor.execute('''
            SELECT
                t.id, t.trip_name, t.cost, t.max_participants,
                COUNT(tp.id) as registered_participants,
                SUM(CASE WHEN tp.payment_status = 'paid' THEN t.cost ELSE 0 END) as revenue_collected,
                SUM(CASE WHEN tp.payment_status = 'pending' THEN t.cost ELSE 0 END) as revenue_pending,
                t.cost * COUNT(tp.id) as revenue_potential
            FROM trips t
            LEFT JOIN trip_participants tp ON t.id = tp.trip_id AND tp.status = 'registered'
            GROUP BY t.id
            HAVING registered_participants > 0
            ORDER BY revenue_collected DESC
            ''')

            revenue_data = cursor.fetchall()

            # Expense summary (if expenses table has data)
            cursor.execute('''
            SELECT t.trip_name, te.category, SUM(te.amount) as total_amount
            FROM trip_expenses te
            JOIN trips t ON te.trip_id = t.id
            GROUP BY t.id, te.category
            ORDER BY t.trip_name, te.category
            ''')

            expense_data = cursor.fetchall()

            # Overall financial summary
            cursor.execute('''
            SELECT
                SUM(CASE WHEN tp.payment_status = 'paid' THEN t.cost ELSE 0 END) as total_revenue_collected,
                SUM(CASE WHEN tp.payment_status = 'pending' THEN t.cost ELSE 0 END) as total_revenue_pending,
                COUNT(DISTINCT t.id) as trips_with_revenue,
                COUNT(tp.id) as total_paid_participants
            FROM trips t
            LEFT JOIN trip_participants tp ON t.id = tp.trip_id AND tp.status = 'registered'
            ''')

            financial_summary = cursor.fetchone()

            return {
                'revenue_data': revenue_data,
                'expense_data': expense_data,
                'financial_summary': financial_summary,
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'generated_by': self.auth.current_user['username'] if self.auth.current_user else 'Unknown'
            }

        except sqlite3.Error as e:
            logging.error(f"Database error getting financial data: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error getting financial data: {e}")
            raise

    def generate_txt_report(self, data, report_type, filename):
        """Generate a text format report"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # Header
                f.write("=" * 80 + "\n")
                f.write(f"TRIP MANAGEMENT SYSTEM - {report_type.upper()} REPORT\n")
                f.write("=" * 80 + "\n")
                f.write(f"Generated: {data['generated_at']}\n")
                f.write(f"Generated by: {data['generated_by']}\n")
                f.write("=" * 80 + "\n\n")

                if report_type == "TRIP_SUMMARY":
                    self._write_trip_summary_txt(f, data)
                elif report_type == "PARTICIPANT_LIST":
                    self._write_participant_list_txt(f, data)
                elif report_type == "FINANCIAL_REPORT":
                    self._write_financial_report_txt(f, data)

                # Footer
                f.write("\n" + "=" * 80 + "\n")
                f.write("End of Report\n")
                f.write("=" * 80 + "\n")

            logging.info(f"TXT report generated successfully: {filename}")
            return True

        except IOError as e:
            logging.error(f"IO error writing TXT report: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error generating TXT report: {e}")
            raise

    def _write_trip_summary_txt(self, f, data):
        """Write trip summary section for TXT report"""
        try:
            summary_stats = data['summary_stats']
            trip_details = data['trip_details']
            participant_stats = data['participant_stats']

            # Summary statistics
            f.write("TRIP SUMMARY STATISTICS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Trips: {summary_stats[0]}\n")
            f.write(f"Planning: {summary_stats[1]}\n")
            f.write(f"Open for Registration: {summary_stats[2]}\n")
            f.write(f"Full: {summary_stats[3]}\n")
            f.write(f"Completed: {summary_stats[4]}\n")
            f.write(f"Cancelled: {summary_stats[5]}\n")
            f.write(f"Total Revenue Potential: £{summary_stats[6] or 0:.2f}\n")
            f.write(f"Average Trip Cost: £{summary_stats[7] or 0:.2f}\n\n")

            # Participant statistics
            f.write("PARTICIPANT STATISTICS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Registrations: {participant_stats[0]}\n")
            f.write(f"Active Registrations: {participant_stats[1]}\n")
            f.write(f"Cancelled Registrations: {participant_stats[2]}\n")
            f.write(f"Paid Registrations: {participant_stats[3]}\n")
            f.write(f"Pending Payments: {participant_stats[4]}\n\n")

            # Detailed trip list
            f.write("DETAILED TRIP INFORMATION\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'ID':<5} {'Name':<20} {'Destination':<15} {'Start Date':<12} {'Participants':<12} {'Revenue':<12} {'Status':<10}\n")
            f.write("-" * 80 + "\n")

            for trip in trip_details:
                trip_id, name, destination, start_date, end_date, max_parts, cost, status, current_parts, revenue, created_by = trip
                participants_info = f"{current_parts}/{max_parts}"
                revenue_info = f"£{revenue:.2f}" if revenue else "£0.00"

                f.write(f"{trip_id:<5} {name[:19]:<20} {destination[:14]:<15} {start_date:<12} {participants_info:<12} {revenue_info:<12} {status.title():<10}\n")

        except Exception as e:
            logging.error(f"Error writing trip summary TXT section: {e}")
            raise

    def _write_participant_list_txt(self, f, data):
        """Write participant list section for TXT report"""
        try:
            participants = data['participants']

            f.write(f"PARTICIPANT LIST REPORT\n")
            f.write(f"Total Participants: {data['total_participants']}\n")
            if data['trip_id']:
                f.write(f"Trip ID: {data['trip_id']}\n")
            f.write("-" * 100 + "\n")

            f.write(f"{'ID':<5} {'Trip':<20} {'Student Name':<25} {'Email':<25} {'Payment':<10} {'Status':<10}\n")
            f.write("-" * 100 + "\n")

            for participant in participants:
                p_id, trip_name, student_id, student_name, email, reg_date, payment_status, status, emergency, medical, dietary = participant
                name = student_name if student_name else f"Student {student_id}"
                email = email if email else "N/A"

                f.write(f"{p_id:<5} {trip_name[:19]:<20} {name[:24]:<25} {email[:24]:<25} {payment_status.title():<10} {status.title():<10}\n")

            # Additional details section
            f.write("\n" + "-" * 100 + "\n")
            f.write("DETAILED PARTICIPANT INFORMATION\n")
            f.write("-" * 100 + "\n")

            for participant in participants:
                p_id, trip_name, student_id, student_name, email, reg_date, payment_status, status, emergency, medical, dietary = participant
                name = student_name if student_name else f"Student {student_id}"

                f.write(f"\nParticipant ID: {p_id}\n")
                f.write(f"Name: {name}\n")
                f.write(f"Trip: {trip_name}\n")
                f.write(f"Registration Date: {reg_date}\n")
                f.write(f"Emergency Contact: {emergency if emergency else 'Not provided'}\n")
                f.write(f"Medical Info: {medical if medical else 'None'}\n")
                f.write(f"Dietary Requirements: {dietary if dietary else 'None'}\n")
                f.write("-" * 50 + "\n")

        except Exception as e:
            logging.error(f"Error writing participant list TXT section: {e}")
            raise

    def _write_financial_report_txt(self, f, data):
        """Write financial report section for TXT report"""
        try:
            revenue_data = data['revenue_data']
            expense_data = data['expense_data']
            financial_summary = data['financial_summary']

            # Financial summary
            f.write("FINANCIAL SUMMARY\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Revenue Collected: £{financial_summary[0] or 0:.2f}\n")
            f.write(f"Total Revenue Pending: £{financial_summary[1] or 0:.2f}\n")
            f.write(f"Trips with Revenue: {financial_summary[2]}\n")
            f.write(f"Total Paid Participants: {financial_summary[3]}\n\n")

            # Revenue by trip
            f.write("REVENUE BY TRIP\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'ID':<5} {'Trip Name':<25} {'Cost':<10} {'Participants':<12} {'Collected':<12} {'Pending':<12}\n")
            f.write("-" * 80 + "\n")

            for revenue in revenue_data:
                trip_id, trip_name, cost, max_parts, participants, collected, pending, potential = revenue
                f.write(f"{trip_id:<5} {trip_name[:24]:<25} £{(cost or 0):<9.2f} {participants:<12} £{(collected or 0):<11.2f} £{(pending or 0):<11.2f}\n")

            # Expenses by trip
            if expense_data:
                f.write("\nEXPENSES BY TRIP\n")
                f.write("-" * 60 + "\n")
                f.write(f"{'Trip Name':<30} {'Category':<20} {'Amount':<10}\n")
                f.write("-" * 60 + "\n")

                for expense in expense_data:
                    trip_name, category, amount = expense
                    f.write(f"{trip_name[:29]:<30} {category[:19]:<20} £{amount:<9.2f}\n")
            else:
                f.write("\nNo expense data recorded.\n")

        except Exception as e:
            logging.error(f"Error writing financial report TXT section: {e}")
            raise

    def generate_pdf_report(self, data, report_type, filename):
        """Generate a PDF format report"""
        if not PDF_AVAILABLE:
            raise ImportError("ReportLab library not available. Cannot generate PDF reports.")

        try:
            doc = SimpleDocTemplate(filename, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []

            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                alignment=TA_CENTER
            )

            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=12,
                spaceAfter=12,
                spaceBefore=12
            )

            # Title
            story.append(Paragraph(f"Trip Management System - {report_type.replace('_', ' ').title()} Report", title_style))
            story.append(Spacer(1, 12))

            # Header info
            header_data = [
                ['Generated:', data['generated_at']],
                ['Generated by:', data['generated_by']]
            ]
            header_table = Table(header_data, colWidths=[1.5*inch, 4*inch])
            header_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
            ]))
            story.append(header_table)
            story.append(Spacer(1, 20))

            if report_type == "TRIP_SUMMARY":
                self._build_trip_summary_pdf(story, data, styles, heading_style)
            elif report_type == "PARTICIPANT_LIST":
                self._build_participant_list_pdf(story, data, styles, heading_style)
            elif report_type == "FINANCIAL_REPORT":
                self._build_financial_report_pdf(story, data, styles, heading_style)

            doc.build(story)
            logging.info(f"PDF report generated successfully: {filename}")
            return True

        except Exception as e:
            logging.error(f"Error generating PDF report: {e}")
            raise

    def _build_trip_summary_pdf(self, story, data, styles, heading_style):
        """Build trip summary section for PDF report"""
        try:
            summary_stats = data['summary_stats']
            trip_details = data['trip_details']
            participant_stats = data['participant_stats']

            # Summary statistics
            story.append(Paragraph("Trip Summary Statistics", heading_style))

            summary_data = [
                ['Metric', 'Value'],
                ['Total Trips', str(summary_stats[0])],
                ['Planning', str(summary_stats[1])],
                ['Open for Registration', str(summary_stats[2])],
                ['Full', str(summary_stats[3])],
                ['Completed', str(summary_stats[4])],
                ['Cancelled', str(summary_stats[5])],
                ['Total Revenue Potential', f'£{summary_stats[6] or 0:.2f}'],
                ['Average Trip Cost', f'£{summary_stats[7] or 0:.2f}']
            ]

            summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 20))

            # Participant statistics
            story.append(Paragraph("Participant Statistics", heading_style))

            participant_data = [
                ['Metric', 'Value'],
                ['Total Registrations', str(participant_stats[0])],
                ['Active Registrations', str(participant_stats[1])],
                ['Cancelled Registrations', str(participant_stats[2])],
                ['Paid Registrations', str(participant_stats[3])],
                ['Pending Payments', str(participant_stats[4])]
            ]

            participant_table = Table(participant_data, colWidths=[3*inch, 2*inch])
            participant_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(participant_table)
            story.append(Spacer(1, 20))

            # Trip details
            story.append(Paragraph("Detailed Trip Information", heading_style))

            trip_headers = ['ID', 'Name', 'Destination', 'Start Date', 'Participants', 'Revenue', 'Status']
            trip_data = [trip_headers]

            for trip in trip_details[:15]:  # Limit to first 15 trips for PDF
                trip_id, name, destination, start_date, end_date, max_parts, cost, status, current_parts, revenue, created_by = trip
                participants_info = f"{current_parts}/{max_parts}"
                revenue_info = f"£{revenue:.2f}" if revenue else "£0.00"

                trip_data.append([
                    str(trip_id),
                    name[:15] + "..." if len(name) > 15 else name,
                    destination[:10] + "..." if len(destination) > 10 else destination,
                    start_date,
                    participants_info,
                    revenue_info,
                    status.title()
                ])

            trip_table = Table(trip_data, colWidths=[0.5*inch, 1.5*inch, 1*inch, 1*inch, 0.8*inch, 0.8*inch, 0.8*inch])
            trip_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(trip_table)

            if len(trip_details) > 15:
                story.append(Spacer(1, 12))
                story.append(Paragraph(f"Note: Showing first 15 trips of {len(trip_details)} total trips.", styles['Normal']))

        except Exception as e:
            logging.error(f"Error building trip summary PDF section: {e}")
            raise

    def _build_participant_list_pdf(self, story, data, styles, heading_style):
        """Build participant list section for PDF report"""
        try:
            participants = data['participants']

            story.append(Paragraph(f"Participant List Report (Total: {data['total_participants']})", heading_style))

            if data['trip_id']:
                story.append(Paragraph(f"Trip ID: {data['trip_id']}", styles['Normal']))
                story.append(Spacer(1, 12))

            # Participant table
            headers = ['ID', 'Trip', 'Student Name', 'Email', 'Payment', 'Status']
            participant_data = [headers]

            for participant in participants[:20]:  # Limit for PDF
                p_id, trip_name, student_id, student_name, email, reg_date, payment_status, status, emergency, medical, dietary = participant
                name = student_name if student_name else f"Student {student_id}"
                email = email if email else "N/A"

                participant_data.append([
                    str(p_id),
                    trip_name[:12] + "..." if len(trip_name) > 12 else trip_name,
                    name[:15] + "..." if len(name) > 15 else name,
                    email[:18] + "..." if len(email) > 18 else email,
                    payment_status.title(),
                    status.title()
                ])

            participant_table = Table(participant_data, colWidths=[0.5*inch, 1.2*inch, 1.5*inch, 1.8*inch, 0.8*inch, 0.8*inch])
            participant_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(participant_table)

            if len(participants) > 20:
                story.append(Spacer(1, 12))
                story.append(Paragraph(f"Note: Showing first 20 participants of {len(participants)} total participants.", styles['Normal']))

        except Exception as e:
            logging.error(f"Error building participant list PDF section: {e}")
            raise

    def _build_financial_report_pdf(self, story, data, styles, heading_style):
        """Build financial report section for PDF report"""
        try:
            revenue_data = data['revenue_data']
            expense_data = data['expense_data']
            financial_summary = data['financial_summary']

            # Financial summary
            story.append(Paragraph("Financial Summary", heading_style))

            summary_data = [
                ['Metric', 'Value'],
                ['Total Revenue Collected', f'£{financial_summary[0] or 0:.2f}'],
                ['Total Revenue Pending', f'£{financial_summary[1] or 0:.2f}'],
                ['Trips with Revenue', str(financial_summary[2])],
                ['Total Paid Participants', str(financial_summary[3])]
            ]

            summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 20))

            # Revenue by trip
            story.append(Paragraph("Revenue by Trip", heading_style))

            revenue_headers = ['ID', 'Trip Name', 'Cost', 'Participants', 'Collected', 'Pending']
            revenue_table_data = [revenue_headers]

            for revenue in revenue_data[:15]:  # Limit for PDF
                trip_id, trip_name, cost, max_parts, participants, collected, pending, potential = revenue
                revenue_table_data.append([
                    str(trip_id),
                    trip_name[:15] + "..." if len(trip_name) > 15 else trip_name,
                    f'£{cost or 0:.2f}',
                    str(participants),
                    f'£{collected or 0:.2f}',
                    f'£{pending or 0:.2f}'
                ])

            revenue_table = Table(revenue_table_data, colWidths=[0.5*inch, 1.5*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch])
            revenue_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(revenue_table)

            if len(revenue_data) > 15:
                story.append(Spacer(1, 12))
                story.append(Paragraph(f"Note: Showing first 15 trips of {len(revenue_data)} total trips with revenue.", styles['Normal']))

        except Exception as e:
            logging.error(f"Error building financial report PDF section: {e}")
            raise

    def generate_report_content_as_string(self, data, report_type):
        """Generate report content as a string (for display in window)"""
        from io import StringIO

        try:
            content = StringIO()

            # Header
            content.write("=" * 80 + "\n")
            content.write(f"TRIP MANAGEMENT SYSTEM - {report_type.upper()} REPORT\n")
            content.write("=" * 80 + "\n")
            content.write(f"Generated: {data['generated_at']}\n")
            content.write(f"Generated by: {data['generated_by']}\n")
            content.write("=" * 80 + "\n\n")

            if report_type == "TRIP_SUMMARY":
                self._write_trip_summary_txt(content, data)
            elif report_type == "PARTICIPANT_LIST":
                self._write_participant_list_txt(content, data)
            elif report_type == "FINANCIAL_REPORT":
                self._write_financial_report_txt(content, data)

            # Footer
            content.write("\n" + "=" * 80 + "\n")
            content.write("End of Report\n")
            content.write("=" * 80 + "\n")

            return content.getvalue()

        except Exception as e:
            logging.error(f"Error generating report content as string: {e}")
            raise

    def get_admin_emails(self):
        """Get email addresses of all admin users"""
        try:
            def get_admins_operation(conn):
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT DISTINCT u.email, u.username, u.first_name, u.last_name
                    FROM users u
                    JOIN roles r ON u.role = r.role_name
                    WHERE r.role_name = 'admin' AND u.email IS NOT NULL AND u.email != ''
                    ORDER BY u.username
                ''')
                return cursor.fetchall()

            admins = safe_db_operation(get_admins_operation)

            if not admins:
                logging.warning("No admin users with email addresses found")
                return []

            return [
                {
                    'email': admin[0],
                    'username': admin[1],
                    'name': f"{admin[2]} {admin[3]}" if admin[2] and admin[3] else admin[1]
                }
                for admin in admins
            ]

        except Exception as e:
            logging.error(f"Error getting admin emails: {e}")
            return []


@log_create(module="trips", description="Generating trip report")
def generate_trip_report():
    """Main function to generate trip reports"""
    auth = _common.auth

    if not auth or not auth.current_user:
        print(get_text("mobility.trip_management.auth.must_login_generate_reports", "You must be logged in to generate reports."))
        return False

    if not auth.check_permission('generate_trip_reports'):
        print(get_text("mobility.trip_management.auth.no_permission_generate_reports", "You don't have permission to generate trip reports."))
        return False

    try:
        # Initialize report generator
        report_generator = TripReportGenerator(auth)

        print("\n" + get_text("mobility.trip_management.reports.title", "Trip Report Generator"))
        print("=" * 50)

        # Report type selection
        report_types = [
            ("TRIP_SUMMARY", get_text("mobility.trip_management.reports.trip_summary", "Trip Summary Report")),
            ("PARTICIPANT_LIST", get_text("mobility.trip_management.reports.participant_list", "Participant List Report")),
            ("FINANCIAL_REPORT", get_text("mobility.trip_management.reports.financial", "Financial Report"))
        ]

        print(get_text("mobility.trip_management.reports.available_types", "Available Report Types:"))
        for i, (code, description) in enumerate(report_types, 1):
            print(f"{i}. {description}")

        while True:
            try:
                choice = int(input(get_text("mobility.trip_management.reports.select_type", "\nSelect report type (1-{max}): ").format(max=len(report_types))))
                if 1 <= choice <= len(report_types):
                    report_code, report_description = report_types[choice - 1]
                    break
                print(get_text("mobility.trip_management.validation.invalid_choice_try_again", "Invalid choice. Please try again."))
            except ValueError:
                print(get_text("mobility.trip_management.validation.enter_valid_number", "Please enter a valid number."))

        # Format selection
        format_types = ["TXT", "PDF"] if PDF_AVAILABLE else ["TXT"]

        print(get_text("mobility.trip_management.reports.available_formats", "\nAvailable Formats:"))
        for i, fmt in enumerate(format_types, 1):
            print(f"{i}. {fmt}")

        while True:
            try:
                format_choice = int(input(get_text("mobility.trip_management.reports.select_format", "\nSelect format (1-{max}): ").format(max=len(format_types))))
                if 1 <= format_choice <= len(format_types):
                    format_type = format_types[format_choice - 1]
                    break
                print(get_text("mobility.trip_management.validation.invalid_choice_try_again", "Invalid choice. Please try again."))
            except ValueError:
                print(get_text("mobility.trip_management.validation.enter_valid_number", "Please enter a valid number."))

        # Special handling for participant reports
        trip_id = None
        if report_code == "PARTICIPANT_LIST":
            choice = input(get_text("mobility.trip_management.reports.specific_trip_prompt", "\nGenerate for specific trip? (y/n): ")).lower()
            if choice == 'y':
                try:
                    trip_id = int(input(get_text("mobility.trip_management.reports.enter_trip_id", "Enter Trip ID: ")))
                except ValueError:
                    print(get_text("mobility.trip_management.reports.invalid_id_all_trips", "Invalid trip ID. Generating report for all trips."))
                    trip_id = None

        # Check financial report permissions
        if report_code == "FINANCIAL_REPORT" and not auth.check_permission('view_financial_reports'):
            print(get_text("mobility.trip_management.auth.no_permission_financial_reports", "You don't have permission to generate financial reports."))
            return False

        # Generate the report
        def generate_report_operation(conn):
            try:
                print(get_text("mobility.trip_management.reports.generating", "\nGenerating {report} in {format} format...").format(report=report_description, format=format_type))

                # Get report data
                if report_code == "TRIP_SUMMARY":
                    data = report_generator.get_trip_summary_data(conn)
                elif report_code == "PARTICIPANT_LIST":
                    data = report_generator.get_participant_report_data(conn, trip_id)
                elif report_code == "FINANCIAL_REPORT":
                    data = report_generator.get_financial_report_data(conn)
                else:
                    raise ValueError(get_text("mobility.trip_management.errors.unknown_report_type", "Unknown report type: {type}").format(type=report_code))

                # Generate filename
                filename = report_generator.generate_filename(report_code, format_type)

                # Generate report based on format
                if format_type == "TXT":
                    success = report_generator.generate_txt_report(data, report_code, filename)
                elif format_type == "PDF":
                    success = report_generator.generate_pdf_report(data, report_code, filename)
                else:
                    raise ValueError(get_text("mobility.trip_management.errors.unknown_format_type", "Unknown format type: {type}").format(type=format_type))

                if success:
                    print(get_text("mobility.trip_management.reports.success", "\nReport generated successfully!"))
                    print(get_text("mobility.trip_management.reports.file_saved", "File saved as: {filename}").format(filename=filename))
                    print(get_text("mobility.trip_management.reports.report_type", "Report type: {type}").format(type=report_description))
                    print(get_text("mobility.trip_management.reports.format", "Format: {format}").format(format=format_type))
                    print(get_text("mobility.trip_management.reports.generated_at", "Generated at: {time}").format(time=data['generated_at']))

                    # Show file size
                    try:
                        file_size = os.path.getsize(filename)
                        print(get_text("mobility.trip_management.reports.file_size", "File size: {size} bytes").format(size=f"{file_size:,}"))
                    except OSError:
                        pass

                    return True
                else:
                    print(get_text("mobility.trip_management.reports.failed", "Failed to generate report."))
                    return False

            except Exception as e:
                logging.error(get_text("mobility.trip_management.errors.in_generate_report", "Error in generate_report_operation: {error}").format(error=e))
                print(get_text("mobility.trip_management.errors.generating_report", "Error generating report: {error}").format(error=e))
                return False

        return safe_db_operation(generate_report_operation)

    except ImportError as e:
        print(get_text("mobility.trip_management.errors.library_error", "Library error: {error}").format(error=e))
        return False
    except Exception as e:
        logging.error(get_text("mobility.trip_management.errors.in_generate_trip_report", "Error in generate_trip_report: {error}").format(error=e))
        print(get_text("mobility.trip_management.errors.unexpected_generating_report", "Unexpected error generating report: {error}").format(error=e))
        return False
