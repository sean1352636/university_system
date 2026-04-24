"""CLI menu system for the enhanced reporting module."""

import os
import json
from datetime import datetime, timedelta

from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.config import CONFIG, AVAILABLE_SECTIONS, get_reporting_db_connection, logger
from education_system.university_system.modules.shared.services.analytics.enhanced_reporting._compat import get_log_file
from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.models import ReportTemplate, AdvancedScheduledReport
from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.cache import CacheManager
from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.data_quality import DataQualityMonitor
from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.predictive import PredictiveAnalytics
from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.visualization import AdvancedVisualization
from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.templates_db import save_template, load_templates, get_template
from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.report_generation import generate_report
from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.scheduler import (
    run_system_maintenance, cleanup_old_reports,
    load_scheduled_reports, save_scheduled_reports, start_scheduler,
)
from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.api import app
from education_system.university_system.core.sql_safety import validate_table_name


def display_enhanced_reporting_menu():
    """Display the advanced reporting menu with all features"""
    while True:
        print("\n" + "="*60)
        print("🔬 ADVANCED STUDENT REPORTING SYSTEM")
        print("="*60)
        print("📊 REPORT MANAGEMENT:")
        print("1.  Create Report Template")
        print("2.  View Templates")
        print("3.  Generate Report")
        print("4.  Generate Interactive Report")
        print("5.  Delete Template")
        print("")
        print("⏰ SCHEDULING:")
        print("6.  Schedule Regular Report")
        print("7.  View Scheduled Reports")
        print("8.  Manage Schedule")
        print("")
        print("🔍 ANALYTICS & INSIGHTS:")
        print("9.  Data Quality Dashboard")
        print("10. Predictive Analytics")
        print("11. Anomaly Detection")
        print("12. Correlation Analysis")
        print("")
        print("⚙️  SYSTEM:")
        print("17. System Maintenance")
        print("18. Performance Monitor")
        print("19. Export System Logs")
        print("")
        print("🌐 API SERVER:")
        print("20. Start REST API Server")
        print("")
        print("21. Return to Main Menu")
        print("="*60)

        choice = input("\nEnter your choice (1-21): ").strip()

        try:
            if choice == '1':
                create_advanced_template_menu()
            elif choice == '2':
                view_templates_menu()
                input("\nPress Enter to continue...")
            elif choice == '3':
                generate_advanced_report_menu()
            elif choice == '4':
                generate_interactive_report_menu()
            elif choice == '5':
                delete_template_menu()
            elif choice == '6':
                schedule_advanced_report_menu()
            elif choice == '7':
                view_scheduled_reports_menu()
            elif choice == '8':
                manage_schedule_menu()
            elif choice == '9':
                show_data_quality_dashboard()
            elif choice == '10':
                show_predictive_analytics()
            elif choice == '11':
                show_anomaly_detection()
            elif choice == '12':
                show_correlation_analysis()
            elif choice == '17':
                run_maintenance_menu()
            elif choice == '18':
                show_performance_monitor()
            elif choice == '19':
                export_logs_menu()
            elif choice == '20':
                start_api_server_menu()
            elif choice == '21':
                print("Returning to main menu...")
                break
            else:
                print("❌ Invalid choice. Please try again.")

        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
        except Exception as e:
            print(f"❌ An error occurred: {str(e)}")
            logger.error(f"Menu error: {str(e)}")


def create_advanced_template_menu():
    """Enhanced template creation with all new features"""
    print("\n🔧 CREATE ADVANCED REPORT TEMPLATE")
    print("="*50)

    # Basic template info
    name = input("📝 Template name: ").strip()
    if not name:
        print("❌ Template name cannot be empty.")
        return

    if get_template(name):
        print(f"❌ Template '{name}' already exists.")
        return

    description = input("📋 Template description: ").strip()

    # Security level
    print("\n🔒 Security Level:")
    print("1. Normal")
    print("2. Confidential")
    print("3. Restricted")

    security_choice = input("Select security level (1-3): ").strip()
    security_levels = {'1': 'normal', '2': 'confidential', '3': 'restricted'}
    security_level = security_levels.get(security_choice, 'normal')

    # Visualization type
    print("\n📊 Visualization Type:")
    print("1. Standard (PNG charts)")
    print("2. Advanced (Enhanced styling)")
    print("3. Interactive (HTML charts)")

    viz_choice = input("Select visualization type (1-3): ").strip()
    viz_types = {'1': 'standard', '2': 'advanced', '3': 'interactive'}
    visualization_type = viz_types.get(viz_choice, 'standard')

    # Select sections
    print("\n📈 Available Report Sections:")
    for i, section in enumerate(AVAILABLE_SECTIONS, 1):
        print(f"{i:2d}. {section.replace('_', ' ').title()}")

    sections = []
    while True:
        section_input = input("\nSelect sections (comma-separated numbers, or 'all'): ").strip()
        if section_input.lower() == 'all':
            sections = AVAILABLE_SECTIONS.copy()
            break

        try:
            indices = [int(idx.strip()) - 1 for idx in section_input.split(',')]
            sections = [AVAILABLE_SECTIONS[idx] for idx in indices if 0 <= idx < len(AVAILABLE_SECTIONS)]
            if sections:
                break
            else:
                print("❌ No valid sections selected.")
        except (ValueError, IndexError):
            print("❌ Invalid input. Please enter comma-separated numbers.")

    # Filters
    filters = {}
    if input("\n🔍 Add filters? (y/n): ").lower() == 'y':
        if input("Filter by course? (y/n): ").lower() == 'y':
            course = input("Enter course (CS/DS): ").upper().strip()
            if course in ['CS', 'DS']:
                filters['course'] = course

        if input("Filter by date range? (y/n): ").lower() == 'y':
            days = input("Number of days to include (default 30): ").strip()
            try:
                filters['date_range_days'] = int(days) if days else 30
            except ValueError:
                filters['date_range_days'] = 30

    # Create template
    template = ReportTemplate(
        name=name,
        description=description,
        sections=sections,
        filters=filters,
        visualization_type=visualization_type,
        security_level=security_level
    )

    save_template(template)
    print(f"\n✅ Template '{name}' created successfully!")
    print(f"   Security Level: {security_level.title()}")
    print(f"   Visualization: {visualization_type.title()}")
    print(f"   Sections: {len(sections)} selected")


def show_data_quality_dashboard():
    """Display data quality dashboard"""
    print("\n🔍 DATA QUALITY DASHBOARD")
    print("="*50)

    try:
        quality_report = DataQualityMonitor.run_quality_checks()

        print(f"📅 Last Check: {quality_report['timestamp']}")
        print()

        checks = quality_report.get('checks', {})

        # Missing data summary
        if 'missing_data' in checks:
            missing = checks['missing_data']['students']
            total = missing['total_records']
            print("📊 MISSING DATA ANALYSIS:")
            print(f"   Total Records: {total}")
            print(f"   Missing Emails: {missing['missing_emails']}")
            print(f"   Missing Names: {missing['missing_names']}")
            print(f"   Missing Courses: {missing['missing_courses']}")

            if total > 0:
                completeness = ((total * 3) - (missing['missing_emails'] + missing['missing_names'] + missing['missing_courses'])) / (total * 3) * 100
                print(f"   Data Completeness: {completeness:.1f}%")

                if completeness < 90:
                    print("   ⚠️  Warning: Data completeness below 90%")
                else:
                    print("   ✅ Good data completeness")
            print()

        # Duplicates
        if 'duplicates' in checks:
            duplicates = checks['duplicates']
            print("👥 DUPLICATE ANALYSIS:")
            print(f"   Duplicate Emails: {duplicates['duplicate_emails']}")

            if duplicates['duplicate_emails'] > 0:
                print("   📋 Duplicate Email Details:")
                for detail in duplicates.get('duplicate_email_details', [])[:5]:
                    print(f"      {detail['email']}: {detail['count']} occurrences")
                print("   ⚠️  Action Required: Review duplicate emails")
            else:
                print("   ✅ No duplicate emails found")
            print()

        # Invalid data
        if 'invalid_data' in checks:
            invalid = checks['invalid_data']
            print("❌ INVALID DATA ANALYSIS:")
            print(f"   Invalid Ages: {invalid['invalid_ages']}")
            print(f"   Invalid Emails: {invalid['invalid_emails']}")

            if invalid['invalid_ages'] > 0 or invalid['invalid_emails'] > 0:
                print("   ⚠️  Action Required: Clean invalid data")
            else:
                print("   ✅ No invalid data found")
            print()

        # Data freshness
        if 'data_freshness' in checks:
            freshness = checks['data_freshness']
            if freshness['last_registration_date']:
                days_since = freshness['days_since_last_registration']
                print("📆 DATA FRESHNESS:")
                print(f"   Last Registration: {freshness['last_registration_date']}")
                print(f"   Days Since Last: {days_since}")

                if days_since > 7:
                    print("   ⚠️  Warning: No recent registrations")
                else:
                    print("   ✅ Recent data available")
            else:
                print("📆 DATA FRESHNESS:")
                print("   ❌ No registration data found")

    except Exception as e:
        print(f"❌ Error generating quality report: {str(e)}")

    input("\nPress Enter to continue...")


def show_predictive_analytics():
    """Display predictive analytics dashboard"""
    print("\n🔮 PREDICTIVE ANALYTICS")
    print("="*40)

    print("🎯 Analyzing dropout risk patterns...")

    try:
        predictions = PredictiveAnalytics.predict_dropout_risk()

        if 'error' in predictions:
            print(f"❌ Analysis unavailable: {predictions['error']}")
        else:
            print("\n📊 DROPOUT RISK ANALYSIS:")

            if 'model_accuracy' in predictions:
                accuracy = predictions['model_accuracy'] * 100
                print(f"   Model Accuracy: {accuracy:.1f}%")

                if accuracy > 80:
                    print("   ✅ High confidence predictions")
                elif accuracy > 60:
                    print("   ⚠️  Moderate confidence predictions")
                else:
                    print("   ❌ Low confidence - more data needed")

            if 'total_students_analyzed' in predictions:
                print(f"   Students Analyzed: {predictions['total_students_analyzed']}")

            if 'high_risk_students' in predictions:
                high_risk = predictions['high_risk_students']
                print(f"   High Risk Students: {len(high_risk)}")

                if high_risk:
                    print("\n   🚨 Students requiring attention:")
                    for student in high_risk[:10]:  # Show top 10
                        print(f"      Student ID: {student['student_id']} (Risk: {student['risk_score']:.2%})")

                    if len(high_risk) > 10:
                        print(f"      ... and {len(high_risk) - 10} more")

            if 'feature_importance' in predictions:
                importance = predictions['feature_importance']
                sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)

                print("\n   📈 Most Important Risk Factors:")
                for feature, score in sorted_features:
                    feature_name = feature.replace('_', ' ').title()
                    print(f"      {feature_name}: {score:.3f}")

    except Exception as e:
        print(f"❌ Error in predictive analysis: {str(e)}")
        logger.error(f"Predictive analytics error: {str(e)}")

    input("\nPress Enter to continue...")


def show_anomaly_detection():
    """Display anomaly detection results"""
    print("\n🔍 ANOMALY DETECTION")
    print("="*35)

    print("🔎 Scanning for unusual patterns...")

    try:
        anomalies = PredictiveAnalytics.detect_anomalies()

        if 'error' in anomalies:
            print(f"❌ Analysis unavailable: {anomalies['error']}")
        else:
            print("\n📊 ANOMALY DETECTION RESULTS:")

            anomaly_count = anomalies.get('total_anomalies', 0)
            anomaly_rate = anomalies.get('anomaly_rate', 0)

            print(f"   Anomalous Students: {anomaly_count}")
            print(f"   Anomaly Rate: {anomaly_rate:.2f}%")

            if anomaly_rate > 15:
                print("   ⚠️  High anomaly rate - investigate data quality")
            elif anomaly_rate > 5:
                print("   ⚠️  Moderate anomalies detected")
            else:
                print("   ✅ Normal anomaly rate")

            if 'anomalous_students' in anomalies and anomalies['anomalous_students']:
                print("\n   🔍 Anomalous Student Profiles:")

                for student in anomalies['anomalous_students'][:10]:
                    print(f"      Student ID: {student['student_id']}")
                    print(f"         Age: {student['age']}")
                    print(f"         Modules: {student['unique_modules']}")
                    print(f"         Avg Grade: {student.get('avg_grade', 'N/A')}")
                    print()

                if len(anomalies['anomalous_students']) > 10:
                    remaining = len(anomalies['anomalous_students']) - 10
                    print(f"      ... and {remaining} more anomalous profiles")

    except Exception as e:
        print(f"❌ Error in anomaly detection: {str(e)}")
        logger.error(f"Anomaly detection error: {str(e)}")

    input("\nPress Enter to continue...")


def show_correlation_analysis():
    """Display correlation analysis"""
    print("\n📈 CORRELATION ANALYSIS")
    print("="*40)

    try:
        conn = get_reporting_db_connection()
        chart_path = AdvancedVisualization.create_correlation_matrix(conn)

        if chart_path:
            print("✅ Correlation matrix generated successfully!")
            print(f"📊 Chart saved to: {chart_path}")

            # Open the chart if possible
            try:
                import webbrowser
                webbrowser.open(f"file://{os.path.abspath(chart_path)}")
                print("🔗 Chart opened in default image viewer")
            except Exception:
                print("💡 Please open the chart file manually to view correlations")
        else:
            print("❌ Unable to generate correlation matrix - insufficient data")

    except Exception as e:
        print(f"❌ Error generating correlation analysis: {str(e)}")
        logger.error(f"Correlation analysis error: {str(e)}")

    input("\nPress Enter to continue...")


def start_api_server_menu():
    """Start the REST API server"""
    print("\n🌐 REST API SERVER")
    print("="*30)

    print("API Endpoints available:")
    print("• POST /api/login - User authentication")
    print("• GET  /api/templates - List templates")
    print("• POST /api/templates - Create template")
    print("• POST /api/reports/generate - Generate report")
    print("• GET  /api/analytics/quality - Data quality")
    print("• GET  /api/analytics/predictions - Predictions")
    print("• GET  /api/analytics/anomalies - Anomaly detection")

    if input("\nStart API server? (y/n): ").lower() == 'y':
        host = input("Host (localhost): ").strip() or "localhost"
        port_input = input("Port (5000): ").strip()
        port = int(port_input) if port_input else 5000

        print(f"\n🚀 Starting API server on http://{host}:{port}")
        print("Press Ctrl+C to stop the server")

        try:
            app.run(host=host, port=port, debug=False)
        except KeyboardInterrupt:
            print("\n🛑 API server stopped")


def view_templates_menu():
    """Display all available templates"""
    print("\n📋 REPORT TEMPLATES")
    print("="*40)

    templates = load_templates()

    if not templates:
        print("No templates found.")
        return

    for i, template_data in enumerate(templates, 1):
        print(f"{i}. {template_data['name']}")
        print(f"   Description: {template_data['description']}")
        print(f"   Sections: {len(template_data['sections'])} sections")
        print(f"   Security: {template_data.get('security_level', 'normal').title()}")
        print(f"   Visualization: {template_data.get('visualization_type', 'standard').title()}")
        print(f"   Version: {template_data.get('version', '1.0')}")
        print(f"   Created: {template_data.get('created_at', 'Unknown')}")
        print()


def generate_advanced_report_menu():
    """Enhanced report generation menu"""
    print("\n📊 GENERATE ADVANCED REPORT")
    print("="*45)

    templates = load_templates()
    if not templates:
        print("No templates available. Create a template first.")
        return

    # Select template
    print("Available templates:")
    for i, template_data in enumerate(templates, 1):
        print(f"{i}. {template_data['name']} ({template_data.get('visualization_type', 'standard')})")

    try:
        choice = int(input(f"\nSelect template (1-{len(templates)}): ")) - 1
        if choice < 0 or choice >= len(templates):
            print("❌ Invalid selection")
            return

        template_name = templates[choice]['name']

        # Date range
        print(f"\n📅 Date Range (leave empty for last 30 days):")
        start_date = input("Start date (YYYY-MM-DD): ").strip()
        end_date = input("End date (YYYY-MM-DD): ").strip()

        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_dt = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=30)
            start_date = start_dt.strftime("%Y-%m-%d")

        # Format selection
        print(f"\n📄 Output Format:")
        print("1. PDF Report")
        print("2. Excel Spreadsheet")
        print("3. Interactive HTML")

        format_choice = input("Select format (1-3): ").strip()
        formats = {'1': 'pdf', '2': 'excel', '3': 'interactive'}
        output_format = formats.get(format_choice, 'pdf')

        # Generate report
        print(f"\n🔄 Generating {output_format.upper()} report...")

        try:
            report_path = generate_report(template_name, start_date, end_date, output_format)

            if report_path:
                print(f"✅ Report generated successfully!")
                print(f"📁 File location: {report_path}")

                # Offer to open the report
                if input("Open report now? (y/n): ").lower() == 'y':
                    import webbrowser
                    webbrowser.open(f"file://{os.path.abspath(report_path)}")
            else:
                print("❌ Failed to generate report")

        except Exception as e:
            print(f"❌ Error generating report: {str(e)}")

    except (ValueError, IndexError):
        print("❌ Invalid selection")


def generate_interactive_report_menu():
    """Generate interactive HTML report menu"""
    print("\n🌐 GENERATE INTERACTIVE REPORT")
    print("="*45)

    templates = load_templates()
    if not templates:
        print("No templates available. Create a template first.")
        return

    # Filter templates that support interactive visualization
    interactive_templates = [t for t in templates if t.get('visualization_type') in ['interactive', 'advanced']]

    if not interactive_templates:
        print("No templates configured for interactive visualization.")
        print("Create a template with 'Interactive' or 'Advanced' visualization type.")
        return

    print("Templates with interactive support:")
    for i, template_data in enumerate(interactive_templates, 1):
        print(f"{i}. {template_data['name']} ({template_data.get('visualization_type', 'standard')})")

    try:
        choice = int(input(f"\nSelect template (1-{len(interactive_templates)}): ")) - 1
        if choice < 0 or choice >= len(interactive_templates):
            print("❌ Invalid selection")
            return

        template_name = interactive_templates[choice]['name']

        # Generate with default date range
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        print(f"\n🔄 Generating interactive report for last 30 days...")

        report_path = generate_report(template_name, start_date, end_date, 'interactive')

        if report_path:
            print(f"✅ Interactive report generated!")
            print(f"📁 File location: {report_path}")

            # Automatically open in browser
            import webbrowser
            webbrowser.open(f"file://{os.path.abspath(report_path)}")
            print("🔗 Report opened in default browser")
        else:
            print("❌ Failed to generate interactive report")

    except (ValueError, IndexError):
        print("❌ Invalid selection")


def delete_template_menu():
    """Delete a report template"""
    print("\n🗑️  DELETE TEMPLATE")
    print("="*30)

    templates = load_templates()
    if not templates:
        print("No templates to delete.")
        return

    print("Available templates:")
    for i, template_data in enumerate(templates, 1):
        print(f"{i}. {template_data['name']}")

    try:
        choice = int(input(f"\nSelect template to delete (1-{len(templates)}): ")) - 1
        if choice < 0 or choice >= len(templates):
            print("❌ Invalid selection")
            return

        template_name = templates[choice]['name']

        confirm = input(f"⚠️  Are you sure you want to delete '{template_name}'? (yes/no): ").strip().lower()
        if confirm == 'yes':
            del templates[choice]

            # Save updated templates
            with open(os.path.join(CONFIG['templates_dir'], "templates.json"), 'w') as f:
                json.dump(templates, f, indent=4)

            print(f"✅ Template '{template_name}' deleted successfully!")
        else:
            print("❌ Deletion cancelled")

    except (ValueError, IndexError):
        print("❌ Invalid selection")


def schedule_advanced_report_menu():
    """Schedule automatic report generation"""
    print("\n⏰ SCHEDULE AUTOMATIC REPORT")
    print("="*45)

    templates = load_templates()
    if not templates:
        print("No templates available for scheduling.")
        return

    # Select template
    print("Available templates:")
    for i, template_data in enumerate(templates, 1):
        print(f"{i}. {template_data['name']}")

    try:
        choice = int(input(f"\nSelect template (1-{len(templates)}): ")) - 1
        if choice < 0 or choice >= len(templates):
            print("❌ Invalid selection")
            return

        template_name = templates[choice]['name']

        # Schedule configuration
        print(f"\n📅 Schedule Configuration:")
        print("1. Daily")
        print("2. Weekly")
        print("3. Monthly")

        schedule_choice = input("Select frequency (1-3): ").strip()
        schedules = {'1': 'daily', '2': 'weekly', '3': 'monthly'}
        frequency = schedules.get(schedule_choice, 'weekly')

        # Time configuration
        hour = input("Hour to run (0-23, default 9): ").strip()
        hour = int(hour) if hour.isdigit() and 0 <= int(hour) <= 23 else 9

        # Recipients
        recipients = []
        print(f"\n📧 Email Recipients:")
        while True:
            email = input("Enter email address (or press Enter to finish): ").strip()
            if not email:
                break
            if '@' in email:
                recipients.append(email)
            else:
                print("❌ Invalid email format")

        if not recipients:
            print("⚠️  No email recipients specified. Report will be generated but not sent.")

        # Create schedule configuration
        schedule_config = {
            'frequency': frequency,
            'hour': hour,
            'enabled': True,
            'last_run': None,
            'next_run': None
        }

        # Save scheduled report
        scheduled_report = AdvancedScheduledReport(
            template_name=template_name,
            schedule_config=schedule_config,
            recipients=recipients
        )

        scheduled_reports = load_scheduled_reports()
        scheduled_reports.append(scheduled_report.to_dict())
        save_scheduled_reports(scheduled_reports)

        print(f"✅ Report '{template_name}' scheduled for {frequency} generation at {hour}:00")
        if recipients:
            print(f"📧 Will be sent to: {', '.join(recipients)}")

    except (ValueError, IndexError):
        print("❌ Invalid input")


def view_scheduled_reports_menu():
    """View all scheduled reports"""
    print("\n📅 SCHEDULED REPORTS")
    print("="*35)

    scheduled_reports = load_scheduled_reports()

    if not scheduled_reports:
        print("No scheduled reports found.")
        return

    for i, report_data in enumerate(scheduled_reports, 1):
        config = report_data['schedule_config']
        print(f"{i}. {report_data['template_name']}")
        print(f"   Frequency: {config['frequency'].title()}")
        print(f"   Time: {config['hour']}:00")
        print(f"   Status: {'Enabled' if config.get('enabled', True) else 'Disabled'}")
        print(f"   Recipients: {len(report_data.get('recipients', []))}")
        print(f"   Last Run: {report_data.get('last_run', 'Never')}")
        print(f"   Run Count: {report_data.get('run_count', 0)}")
        print()


def manage_schedule_menu():
    """Manage scheduled reports"""
    print("\n⚙️  MANAGE SCHEDULED REPORTS")
    print("="*40)

    scheduled_reports = load_scheduled_reports()

    if not scheduled_reports:
        print("No scheduled reports to manage.")
        return

    print("Scheduled reports:")
    for i, report_data in enumerate(scheduled_reports, 1):
        status = "Enabled" if report_data['schedule_config'].get('enabled', True) else "Disabled"
        print(f"{i}. {report_data['template_name']} ({status})")

    try:
        choice = int(input(f"\nSelect report to manage (1-{len(scheduled_reports)}): ")) - 1
        if choice < 0 or choice >= len(scheduled_reports):
            print("❌ Invalid selection")
            return

        report = scheduled_reports[choice]

        print(f"\n📋 Managing: {report['template_name']}")
        print("1. Enable/Disable")
        print("2. Modify Schedule")
        print("3. Update Recipients")
        print("4. Delete Schedule")
        print("5. Run Now")

        action = input("Select action (1-5): ").strip()

        if action == '1':
            current_status = report['schedule_config'].get('enabled', True)
            report['schedule_config']['enabled'] = not current_status
            new_status = "Enabled" if not current_status else "Disabled"
            print(f"✅ Schedule {new_status.lower()}")

        elif action == '2':
            print("New frequency:")
            print("1. Daily")
            print("2. Weekly")
            print("3. Monthly")

            freq_choice = input("Select (1-3): ").strip()
            frequencies = {'1': 'daily', '2': 'weekly', '3': 'monthly'}
            new_freq = frequencies.get(freq_choice)

            if new_freq:
                report['schedule_config']['frequency'] = new_freq

                new_hour = input("New hour (0-23): ").strip()
                if new_hour.isdigit() and 0 <= int(new_hour) <= 23:
                    report['schedule_config']['hour'] = int(new_hour)

                print(f"✅ Schedule updated to {new_freq} at {report['schedule_config']['hour']}:00")

        elif action == '3':
            new_recipients = []
            print("Current recipients:", report.get('recipients', []))
            print("Enter new recipients (press Enter when done):")

            while True:
                email = input("Email: ").strip()
                if not email:
                    break
                if '@' in email:
                    new_recipients.append(email)

            report['recipients'] = new_recipients
            print(f"✅ Recipients updated ({len(new_recipients)} recipients)")

        elif action == '4':
            confirm = input("⚠️  Delete this schedule? (yes/no): ").strip().lower()
            if confirm == 'yes':
                del scheduled_reports[choice]
                print("✅ Schedule deleted")
            else:
                print("❌ Deletion cancelled")
                return

        elif action == '5':
            print("🔄 Running report now...")
            try:
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

                report_path = generate_report(report['template_name'], start_date, end_date, 'pdf')

                if report_path and report.get('recipients'):
                    EmailManager.send_email(
                        report['recipients'],
                        f"Scheduled Report: {report['template_name']}",
                        f"<h2>Scheduled Report</h2><p>Report generated at {datetime.now()}</p>",
                        [report_path]
                    )

                    if success:
                        print("✅ Report generated and sent successfully!")
                    else:
                        print(f"⚠️  Report generated but email failed: {message}")
                else:
                    print("✅ Report generated successfully!")

            except Exception as e:
                print(f"❌ Error running report: {str(e)}")
                return

        # Save changes
        save_scheduled_reports(scheduled_reports)

    except (ValueError, IndexError):
        print("❌ Invalid selection")


def run_maintenance_menu():
    """Run system maintenance tasks"""
    print("\n🔧 SYSTEM MAINTENANCE")
    print("="*35)

    print("Available maintenance tasks:")
    print("1. Clean old reports (30+ days)")
    print("2. Clear cache")
    print("3. Run data quality check")
    print("4. Optimize database")
    print("5. Run all maintenance")

    choice = input("Select task (1-5): ").strip()

    try:
        if choice == '1':
            print("🗂️  Cleaning old report files...")
            cleanup_old_reports()
            print("✅ Old reports cleaned")

        elif choice == '2':
            print("🧹 Clearing cache...")
            CacheManager.cleanup_cache()
            print("✅ Cache cleared")

        elif choice == '3':
            print("🔍 Running data quality check...")
            quality_report = DataQualityMonitor.run_quality_checks()
            print("✅ Data quality check completed")

            # Show brief summary
            checks = quality_report.get('checks', {})
            if 'missing_data' in checks:
                total = checks['missing_data']['students']['total_records']
                print(f"   📊 {total} total records analyzed")

        elif choice == '4':
            print("🗃️  Optimizing database...")
            conn = get_reporting_db_connection()
            try:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
                print("✅ Database optimized")
            finally:
                conn.close()

        elif choice == '5':
            print("🔄 Running all maintenance tasks...")
            quality_report = run_system_maintenance()
            print("✅ All maintenance tasks completed")

        else:
            print("❌ Invalid selection")

    except Exception as e:
        print(f"❌ Maintenance error: {str(e)}")


def show_performance_monitor():
    """Show system performance metrics"""
    print("\n📊 PERFORMANCE MONITOR")
    print("="*35)

    try:
        # Database size
        db_size = os.path.getsize(CONFIG['database']) / (1024 * 1024)  # MB
        print(f"📀 Database size: {db_size:.2f} MB")

        # Reports directory size
        reports_size = 0
        for root, dirs, files in os.walk(CONFIG['reports_dir']):
            for file in files:
                reports_size += os.path.getsize(os.path.join(root, file))
        reports_size = reports_size / (1024 * 1024)  # MB
        print(f"📁 Reports size: {reports_size:.2f} MB")

        # Cache directory size
        cache_size = 0
        if os.path.exists(CONFIG['cache_dir']):
            for root, dirs, files in os.walk(CONFIG['cache_dir']):
                for file in files:
                    cache_size += os.path.getsize(os.path.join(root, file))
        cache_size = cache_size / (1024 * 1024)  # MB
        print(f"💾 Cache size: {cache_size:.2f} MB")

        # Record counts
        conn = get_reporting_db_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM students")
            student_count = cursor.fetchone()[0]
            print(f"👥 Total students: {student_count}")

            # Whitelist of allowed tables for SQL injection prevention
            ALLOWED_TABLES = {'student_modules', 'student_grades', 'student_attendance'}

            # Check if other tables exist
            tables = ['student_modules', 'student_grades', 'student_attendance']
            for table in tables:
                # Validate table name against whitelist before using in query
                if table not in ALLOWED_TABLES:
                    continue
                try:
                    safe_table = validate_table_name(table)
                    cursor.execute("SELECT COUNT(*) FROM [" + safe_table + "]")
                    count = cursor.fetchone()[0]
                    table_name = table.replace('_', ' ').title()
                    print(f"📚 {table_name}: {count}")
                except Exception:
                    pass  # Table might not exist

        finally:
            conn.close()

        # Template and schedule counts
        templates = load_templates()
        print(f"📋 Templates: {len(templates)}")

        scheduled_reports = load_scheduled_reports()
        print(f"⏰ Scheduled reports: {len(scheduled_reports)}")

        # Users
        UserManager.load_users()
        users = UserManager.load_users()
        active_users = sum(1 for u in users.values() if u.get('is_active', True))
        print(f"👤 Active users: {active_users}/{len(users)}")

    except Exception as e:
        print(f"❌ Error gathering performance data: {str(e)}")

    input("\nPress Enter to continue...")


def export_logs_menu():
    """Export system logs"""
    print("\n📄 EXPORT SYSTEM LOGS")
    print("="*35)

    log_file = get_log_file('app.log')

    if not os.path.exists(log_file):
        print("❌ No log file found")
        return

    # Get log file info
    log_size = os.path.getsize(log_file) / 1024  # KB
    mod_time = datetime.fromtimestamp(os.path.getmtime(log_file))

    print(f"📊 Log file size: {log_size:.2f} KB")
    print(f"📅 Last modified: {mod_time}")

    export_choice = input("\nExport options:\n1. Last 100 lines\n2. Last 24 hours\n3. Full log\nSelect (1-3): ").strip()

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = os.path.join(CONFIG['reports_dir'], f"system_logs_{timestamp}.txt")

        with open(log_file, 'r') as f:
            lines = f.readlines()

        if export_choice == '1':
            # Last 100 lines
            export_lines = lines[-100:] if len(lines) > 100 else lines

        elif export_choice == '2':
            # Last 24 hours
            cutoff_time = datetime.now() - timedelta(hours=24)
            export_lines = []

            for line in reversed(lines):
                try:
                    # Extract timestamp from log line
                    if line.strip() and ' - ' in line:
                        timestamp_str = line.split(' - ')[0]
                        log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                        if log_time >= cutoff_time:
                            export_lines.append(line)
                        else:
                            break
                except (ValueError, IndexError):
                    export_lines.append(line)  # Include lines without valid timestamps

            export_lines.reverse()

        else:
            # Full log
            export_lines = lines

        # Write export file
        with open(export_file, 'w') as f:
            f.writelines(export_lines)

        print(f"✅ Logs exported successfully!")
        print(f"📁 File: {export_file}")
        print(f"📊 Lines exported: {len(export_lines)}")

    except Exception as e:
        print(f"❌ Error exporting logs: {str(e)}")
