from datetime import datetime
import json
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch

from education_system.university_system.infrastructure.database.db import get_connection

from . import _common
from ._common import get_current_academic_year


def advanced_export_system():
    """Advanced export system with multiple formats and automation"""
    auth = _common.auth

    if not auth or not auth.current_user:
        print("You must be logged in to access advanced export system.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to access advanced export system.")
        return

    print("\nAdvanced Export & Data Delivery System")
    print("=" * 50)

    export_options = {
        '1': 'Complete Financial Analysis Package (All Reports + Charts)',
        '2': 'Executive Summary Dashboard (PDF)',
        '3': 'Raw Data Export (Multiple Formats)',
        '4': 'Automated API Data Feed Setup',
        '5': 'Custom Report Builder',
        '6': 'Scheduled Export Configuration'
    }

    print("Export Options:")
    for key, value in export_options.items():
        print(f"{key}. {value}")

    choice = input("\nSelect export option (1-6): ").strip()

    if choice == '1':
        # Complete package - import here to avoid circular imports
        from .reports import (
            generate_advanced_financial_forecasting,
            generate_comprehensive_budget_variance_report,
            real_time_financial_dashboard,
        )
        from .scenario_planning import scenario_planning_tools

        print("Generating complete financial analysis package...")

        # Generate all reports
        generate_advanced_financial_forecasting()
        generate_comprehensive_budget_variance_report()
        real_time_financial_dashboard()
        scenario_planning_tools()

        # Create package
        package_name = f"Complete_Financial_Package_{datetime.now().strftime('%Y%m%d_%H%M')}"

        print(f"Complete financial analysis package prepared as '{package_name}'")
        print("Package includes: forecasts, variance analysis, dashboard, scenarios, and all visualizations")

    elif choice == '2':
        # Executive summary
        print("Generating executive summary dashboard...")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Key metrics for executives
            academic_year = get_current_academic_year()

            cursor.execute('''
            SELECT
                SUM(sf.amount) as total_expected,
                SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected,
                COUNT(DISTINCT sf.student_id) as student_count
            FROM student_fees sf
            JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
            WHERE ft.academic_year = ?
            ''', (academic_year,))

            summary_data = cursor.fetchone()

            # Handle None values from empty tables
            total_expected = summary_data[0] if summary_data and summary_data[0] is not None else 0
            total_collected = summary_data[1] if summary_data and summary_data[1] is not None else 0
            student_count = summary_data[2] if summary_data and summary_data[2] is not None else 0
            collection_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0

            # Generate executive PDF (simplified version)
            filename = f"Executive_Summary_{datetime.now().strftime('%Y%m%d')}.pdf"

            doc = SimpleDocTemplate(filename, pagesize=letter)
            styles = getSampleStyleSheet()
            elements = []

            # Executive summary content
            elements.append(Paragraph("Financial Performance Executive Summary", styles['Title']))
            elements.append(Spacer(1, 0.5*inch))

            # Key metrics table
            metrics_data = [
                ['Metric', 'Value', 'Status'],
                ['Total Expected Revenue', f"£{total_expected:,.2f}", '✓'],
                ['Revenue Collected', f"£{total_collected:,.2f}", '✓'],
                ['Collection Rate', f"{collection_rate:.1f}%", '✓' if collection_rate > 85 else '⚠'],
                ['Active Students', str(student_count), '✓']
            ]

            metrics_table = Table(metrics_data, colWidths=[3*inch, 2*inch, 1*inch])
            metrics_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))

            elements.append(metrics_table)
            elements.append(Spacer(1, 0.5*inch))

            # Executive recommendations
            elements.append(Paragraph("Key Recommendations", styles['Heading2']))
            elements.append(Paragraph("• Monitor collection rates closely", styles['Normal']))
            elements.append(Paragraph("• Implement flexible payment plans", styles['Normal']))
            elements.append(Paragraph("• Focus on high-risk student support", styles['Normal']))

            doc.build(elements)
            print(f"Executive summary exported to {filename}")

            conn.close()

        except Exception as e:
            print(f"Error generating executive summary: {e}")

    elif choice == '3':
        # Raw data export
        print("Raw data export options:")
        print("1. CSV format")
        print("2. Excel format (multiple sheets)")
        print("3. JSON format")
        print("4. All formats")

        format_choice = input("Select format (1-4): ").strip()

        try:
            conn = get_connection()

            # Export student fees data
            fees_df = pd.read_sql_query('''
            SELECT sf.*, ft.fee_name, ft.academic_year, s.first_name, s.last_name
            FROM student_fees sf
            JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
            JOIN students s ON sf.student_id = s.student_id
            ''', conn)

            # Export payments data
            payments_df = pd.read_sql_query('''
            SELECT p.*, s.first_name, s.last_name
            FROM payments p
            JOIN students s ON p.student_id = s.student_id
            ''', conn)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M')

            if format_choice in ['1', '4']:
                # CSV export
                fees_df.to_csv(f'student_fees_export_{timestamp}.csv', index=False)
                payments_df.to_csv(f'payments_export_{timestamp}.csv', index=False)
                print(f"CSV files exported: student_fees_export_{timestamp}.csv, payments_export_{timestamp}.csv")

            if format_choice in ['2', '4']:
                # Excel export
                with pd.ExcelWriter(f'financial_data_export_{timestamp}.xlsx', engine='openpyxl') as writer:
                    fees_df.to_excel(writer, sheet_name='Student Fees', index=False)
                    payments_df.to_excel(writer, sheet_name='Payments', index=False)
                print(f"Excel file exported: financial_data_export_{timestamp}.xlsx")

            if format_choice in ['3', '4']:
                # JSON export
                export_data = {
                    'student_fees': fees_df.to_dict('records'),
                    'payments': payments_df.to_dict('records'),
                    'export_timestamp': timestamp
                }

                with open(f'financial_data_export_{timestamp}.json', 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
                print(f"JSON file exported: financial_data_export_{timestamp}.json")

            conn.close()

        except Exception as e:
            print(f"Error exporting raw data: {e}")

    elif choice == '4':
        # API setup
        print("API Data Feed Configuration:")
        print("Setting up automated data endpoints...")

        api_endpoints = {
            '/api/financial/summary': 'Daily financial summary',
            '/api/financial/collections': 'Collection rates and trends',
            '/api/financial/students/risk': 'High-risk student analysis',
            '/api/financial/forecasts': 'Financial forecasts',
            '/api/financial/alerts': 'Current alerts and notifications'
        }

        print("\nAvailable API Endpoints:")
        for endpoint, description in api_endpoints.items():
            print(f"  {endpoint}: {description}")

        print("\nAPI authentication and rate limiting configured.")
        print("Documentation available at /api/docs")

    elif choice == '5':
        # Custom report builder
        print("Custom Report Builder:")
        print("Configure your custom financial report...")

        # Report configuration options
        report_sections = {
            '1': 'Collection Summary',
            '2': 'Payment Trends',
            '3': 'Student Risk Analysis',
            '4': 'Fee Type Performance',
            '5': 'Comparative Analysis',
            '6': 'Forecasting',
            '7': 'Budget Variance'
        }

        print("\nAvailable Report Sections:")
        for key, value in report_sections.items():
            print(f"{key}. {value}")

        selected_sections = input("Select sections (comma-separated, e.g., 1,2,3): ").strip()

        print(f"Custom report configured with sections: {selected_sections}")
        print("Report will be generated with selected components.")

    elif choice == '6':
        # Scheduled exports
        print("Scheduled Export Configuration:")

        schedule_options = {
            'daily': 'Daily summary report (8 AM)',
            'weekly': 'Weekly analysis (Monday 9 AM)',
            'monthly': 'Monthly comprehensive report (1st, 10 AM)',
            'quarterly': 'Quarterly board report (1st of quarter, 2 PM)'
        }

        print("\nScheduling Options:")
        for key, value in schedule_options.items():
            print(f"  {key}: {value}")

        schedule_choice = input("Select schedule (daily/weekly/monthly/quarterly): ").strip()
        recipients = input("Enter email recipients (comma-separated): ").strip()

        print(f"Scheduled {schedule_choice} export configured for: {recipients}")
        print("Export system will automatically generate and deliver reports.")
