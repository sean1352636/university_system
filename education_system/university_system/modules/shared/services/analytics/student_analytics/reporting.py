import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
try:
    from matplotlib.backends.backend_pdf import PdfPages
except ImportError:
    PdfPages = None
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, Fill, PatternFill, Alignment

from .config import CONFIG


class ReportingMixin:

    def custom_report_builder(self):
        """Interactive custom report builder"""
        print("\n" + "="*60)
        print("CUSTOM REPORT BUILDER")
        print("="*60)

        print("Available report components:")
        components = {
            '1': 'Student Demographics',
            '2': 'Grade Distribution',
            '3': 'Module Popularity',
            '4': 'Performance Trends',
            '5': 'Engagement Analysis',
            '6': 'Risk Assessment',
            '7': 'Cohort Analysis',
            '8': 'Correlation Analysis'
        }

        for key, value in components.items():
            print(f"  {key}. {value}")

        selected = input("\nSelect components (comma-separated, e.g., 1,3,5): ").split(',')

        # Get report parameters
        report_name = input("Enter report name: ") or "Custom_Report"
        include_summary = input("Include executive summary? (y/n): ").lower() == 'y'

        print(f"\nGenerating custom report: {report_name}...")

        # Create custom report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.reports_dir}/{report_name}_{timestamp}.pdf"

        with PdfPages(filename) as pdf:
            # Title page
            plt.figure(figsize=(12, 8))
            plt.axis('off')
            plt.text(0.5, 0.6, f'Custom Analytics Report: {report_name}',
                    horizontalalignment='center', verticalalignment='center', fontsize=24)
            plt.text(0.5, 0.5, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                    horizontalalignment='center', verticalalignment='center', fontsize=14)
            plt.text(0.5, 0.4, f'Components: {", ".join([components[s.strip()] for s in selected if s.strip() in components])}',
                    horizontalalignment='center', verticalalignment='center', fontsize=12)
            pdf.savefig()
            plt.close()

            # Generate selected components
            for component in selected:
                component = component.strip()
                if component in components:
                    print(f"Adding {components[component]}...")

                    if component == '1':
                        self.analyze_student_demographics()
                    elif component == '2':
                        self.analyze_grade_distribution()
                    elif component == '3':
                        self.analyze_module_popularity()
                    elif component == '4':
                        self.analyze_performance_trends()
                    elif component == '5':
                        self.analyze_engagement()
                    elif component == '6':
                        self.analyze_academic_risk()
                    elif component == '7':
                        self.analyze_cohorts()
                    elif component == '8':
                        self.analyze_correlations()

                    # Save current figure to PDF
                    pdf.savefig()
                    plt.close()

        print(f"\nCustom report generated: {filename}")

    def export_data(self):
        """Enhanced data export functionality"""
        print("\n" + "="*60)
        print("DATA EXPORT OPTIONS")
        print("="*60)

        print("Available export formats:")
        print("1. Excel (with multiple sheets)")
        print("2. CSV (separate files)")
        print("3. JSON")
        print("4. Statistical Summary Report")

        choice = input("Select export format (1-4): ")

        students_df = self.get_all_students(self.custom_filters)
        modules_df = self.get_all_modules(self.custom_filters)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if choice == '1':
            # Excel export with multiple sheets
            filename = f"{self.reports_dir}/student_data_export_{timestamp}.xlsx"

            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                # Student data
                students_df.to_excel(writer, sheet_name='Students', index=False)

                # Module data
                if not modules_df.empty:
                    modules_df.to_excel(writer, sheet_name='Modules', index=False)

                # Summary statistics
                summary_data = {
                    'Metric': ['Total Students', 'Average GPA', 'Average Engagement', 'Completion Rate'],
                    'Value': [
                        len(students_df),
                        students_df['gpa'].mean(),
                        students_df['engagement_score'].mean(),
                        (students_df['completion_status'] == 'Completed').mean() * 100
                    ]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

                # Course breakdown
                course_summary = students_df.groupby('course').agg({
                    'student_id': 'count',
                    'gpa': 'mean',
                    'engagement_score': 'mean'
                }).round(2)
                course_summary.to_excel(writer, sheet_name='Course_Summary')

            print(f"Excel export completed: {filename}")

        elif choice == '2':
            # CSV export
            students_filename = f"{self.reports_dir}/students_{timestamp}.csv"
            students_df.to_csv(students_filename, index=False)
            print(f"Students CSV exported: {students_filename}")

            if not modules_df.empty:
                modules_filename = f"{self.reports_dir}/modules_{timestamp}.csv"
                modules_df.to_csv(modules_filename, index=False)
                print(f"Modules CSV exported: {modules_filename}")

        elif choice == '3':
            # JSON export
            filename = f"{self.reports_dir}/student_data_{timestamp}.json"
            export_data = {
                'students': students_df.to_dict('records'),
                'modules': modules_df.to_dict('records') if not modules_df.empty else [],
                'export_metadata': {
                    'timestamp': timestamp,
                    'total_students': len(students_df),
                    'total_modules': len(modules_df)
                }
            }

            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)

            print(f"JSON export completed: {filename}")

        elif choice == '4':
            # Statistical summary report
            self.generate_statistical_summary_report(students_df, modules_df, timestamp)

    def generate_statistical_summary_report(self, students_df, modules_df, timestamp):
        """Generate comprehensive statistical summary report"""
        filename = f"{self.reports_dir}/statistical_summary_{timestamp}.txt"

        with open(filename, 'w') as f:
            f.write("COMPREHENSIVE STATISTICAL SUMMARY REPORT\n")
            f.write("="*60 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # Student Statistics
            f.write("STUDENT DEMOGRAPHICS STATISTICS\n")
            f.write("-"*40 + "\n")
            f.write(f"Total Students: {len(students_df)}\n")
            f.write(f"Age - Mean: {students_df['age'].mean():.2f}, Median: {students_df['age'].median():.2f}, Std: {students_df['age'].std():.2f}\n")
            f.write(f"GPA - Mean: {students_df['gpa'].mean():.3f}, Median: {students_df['gpa'].median():.3f}, Std: {students_df['gpa'].std():.3f}\n")
            f.write(f"Engagement - Mean: {students_df['engagement_score'].mean():.2f}, Median: {students_df['engagement_score'].median():.2f}, Std: {students_df['engagement_score'].std():.2f}\n\n")

            # Gender distribution
            f.write("Gender Distribution:\n")
            gender_counts = students_df['gender'].value_counts()
            for gender, count in gender_counts.items():
                f.write(f"  {gender}: {count} ({count/len(students_df)*100:.1f}%)\n")
            f.write("\n")

            # Course distribution
            f.write("Course Distribution:\n")
            course_counts = students_df['course'].value_counts()
            for course, count in course_counts.items():
                f.write(f"  {course}: {count} ({count/len(students_df)*100:.1f}%)\n")
            f.write("\n")

            # Performance statistics
            f.write("PERFORMANCE STATISTICS\n")
            f.write("-"*40 + "\n")
            grade_counts = students_df['overall_grade'].value_counts()
            for grade in ['A', 'B', 'C', 'D', 'F']:
                if grade in grade_counts:
                    count = grade_counts[grade]
                    f.write(f"Grade {grade}: {count} ({count/len(students_df)*100:.1f}%)\n")

            pass_rate = (students_df['overall_grade'] != 'F').mean() * 100
            f.write(f"Overall Pass Rate: {pass_rate:.1f}%\n\n")

            # Module statistics
            if not modules_df.empty:
                f.write("MODULE STATISTICS\n")
                f.write("-"*40 + "\n")
                f.write(f"Total Module Enrollments: {len(modules_df)}\n")
                f.write(f"Unique Modules: {modules_df['module_name'].nunique()}\n")
                f.write(f"Average Modules per Student: {len(modules_df) / modules_df['student_id'].nunique():.1f}\n")

                module_type_counts = modules_df['module_type'].value_counts()
                f.write("Module Type Distribution:\n")
                for module_type, count in module_type_counts.items():
                    f.write(f"  {module_type}: {count} ({count/len(modules_df)*100:.1f}%)\n")
                f.write("\n")

            # Correlation analysis
            f.write("CORRELATION ANALYSIS\n")
            f.write("-"*40 + "\n")
            correlations = [
                ('Age vs GPA', students_df['age'].corr(students_df['gpa'])),
                ('Engagement vs GPA', students_df['engagement_score'].corr(students_df['gpa'])),
                ('Age vs Engagement', students_df['age'].corr(students_df['engagement_score']))
            ]

            for desc, corr in correlations:
                f.write(f"{desc}: {corr:.3f}\n")

        print(f"Statistical summary report generated: {filename}")

    def email_reports(self):
        """Email report functionality"""
        print("\n" + "="*60)
        print("EMAIL REPORTS")
        print("="*60)

        # Check if email configuration is set
        if not CONFIG['email_config']['sender_email']:
            print("Email configuration not set. Please configure email settings first.")
            print("Go to Configuration Settings to set up email.")
            return

        recipient = input("Enter recipient email address: ")
        subject = input("Enter email subject: ") or "Student Analytics Report"

        print("\nAvailable reports to send:")
        print("1. Latest complete analytics report")
        print("2. Summary statistics only")
        print("3. Generate and send custom report")

        choice = input("Select option (1-3): ")

        if choice == '1':
            self.send_email_with_attachment(recipient, subject, "complete_report")
        elif choice == '2':
            self.send_email_with_attachment(recipient, subject, "summary_only")
        elif choice == '3':
            self.custom_report_builder()
            self.send_email_with_attachment(recipient, subject, "custom_report")

    def send_email_with_attachment(self, recipient, subject, report_type):
        """Send email with report attachment"""
        try:
            from education_system.university_system.infrastructure.email.smtp import send_email_via_smtp
            from education_system.university_system.infrastructure.email.template_utils import render_template

            # Email body from template
            _, body = render_template("student_analytics_report", {
                "subject": subject,
                "report_type": report_type.replace('_', ' ').title(),
                "generated_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            if not body:
                body = "Please find attached the requested student analytics report."

            # Find latest report file
            report_files = []
            for file in os.listdir(self.reports_dir):
                if file.endswith('.pdf'):
                    report_files.append(os.path.join(self.reports_dir, file))

            attachments = None
            if report_files:
                latest_report = max(report_files, key=os.path.getctime)
                attachments = [latest_report]

            # Send email using centralized system
            current_time = datetime.now().isoformat()
            success = send_email_via_smtp(
                recipient_email=recipient,
                subject=subject,
                body=body,
                cc=None,
                bcc=None,
                attachments=attachments,
                current_time=current_time
            )

            if success:
                print(f"Email sent successfully to {recipient}")
            else:
                print(f"Failed to send email to {recipient}")

        except Exception as e:
            print(f"Failed to send email: {e}")
            print("Please check your email configuration and internet connection.")

    def generate_complete_report(self):
        """Generate the most comprehensive analytics report possible"""
        students_df = self.get_all_students(self.custom_filters)
        modules_df = self.get_all_modules(self.custom_filters)

        if students_df.empty:
            print("No data available for generating the report.")
            return

        print("\nGenerating comprehensive analytics report...")
        print("This may take a few minutes...")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.reports_dir}/comprehensive_analytics_report_{timestamp}.pdf"

        with PdfPages(filename) as pdf:
            # Title Page
            plt.figure(figsize=(12, 8))
            plt.axis('off')
            plt.text(0.5, 0.7, 'Comprehensive Student Analytics Report',
                    horizontalalignment='center', verticalalignment='center', fontsize=28, weight='bold')
            plt.text(0.5, 0.6, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                    horizontalalignment='center', verticalalignment='center', fontsize=16)
            plt.text(0.5, 0.5, f'Total Students Analyzed: {len(students_df)}',
                    horizontalalignment='center', verticalalignment='center', fontsize=16)
            if not modules_df.empty:
                plt.text(0.5, 0.45, f'Total Module Enrollments: {len(modules_df)}',
                        horizontalalignment='center', verticalalignment='center', fontsize=16)
            plt.text(0.5, 0.3, 'Enhanced Student Analytics System',
                    horizontalalignment='center', verticalalignment='center', fontsize=14, style='italic')
            pdf.savefig()
            plt.close()

            # Executive Summary Page
            plt.figure(figsize=(12, 10))
            plt.axis('off')
            plt.text(0.5, 0.95, 'Executive Summary', horizontalalignment='center', fontsize=20, weight='bold')

            # Key metrics
            avg_gpa = students_df['gpa'].mean()
            avg_engagement = students_df['engagement_score'].mean()
            completion_rate = (students_df['completion_status'] == 'Completed').mean() * 100
            pass_rate = (students_df['overall_grade'] != 'F').mean() * 100

            y_pos = 0.85
            key_metrics = [
                f"Average GPA: {avg_gpa:.2f}",
                f"Average Engagement Score: {avg_engagement:.1f}",
                f"Overall Pass Rate: {pass_rate:.1f}%",
                f"Completion Rate: {completion_rate:.1f}%",
                f"Total Active Students: {len(students_df[students_df['completion_status'] == 'Active'])}",
                f"Students at Risk: {(students_df['gpa'] < 2.0).sum()}"
            ]

            for metric in key_metrics:
                plt.text(0.1, y_pos, f"• {metric}", fontsize=14, weight='bold')
                y_pos -= 0.06

            # Key insights
            y_pos -= 0.05
            plt.text(0.1, y_pos, 'Key Insights:', fontsize=16, weight='bold')
            y_pos -= 0.05

            # Safely compute insights with fallbacks for empty/invalid data
            course_gpa = students_df.groupby('course')['gpa'].mean()
            highest_course = course_gpa.idxmax() if not course_gpa.empty else 'N/A'

            # Handle None/NaN age values for age group analysis
            students_with_age = students_df[students_df['age'].notna()]
            if not students_with_age.empty:
                age_groups = pd.cut(students_with_age['age'], bins=[0, 25, 35, 45, 100],
                                   labels=['18-25', '26-35', '36-45', '46+'])
                mode_result = age_groups.mode()
                popular_age_group = mode_result.iloc[0] if not mode_result.empty else 'N/A'
            else:
                popular_age_group = 'N/A'

            correlation = students_df['engagement_score'].corr(students_df['gpa'])
            correlation_str = f"{correlation:.3f}" if pd.notna(correlation) else 'N/A'

            insights = [
                f"Highest performing course: {highest_course}",
                f"Most popular age group: {popular_age_group}",
                f"Engagement-GPA correlation: {correlation_str}",
                "Recommended actions: Focus on low-engagement students and academic support"
            ]

            for insight in insights:
                plt.text(0.1, y_pos, f"• {insight}", fontsize=12)
                y_pos -= 0.05

            pdf.savefig()
            plt.close()

            # Generate all analysis components
            analyses = [
                ('Student Demographics', self.analyze_student_demographics),
                ('Grade Distribution', self.analyze_grade_distribution),
                ('Module Popularity', self.analyze_module_popularity),
                ('Academic Risk Assessment', self.analyze_academic_risk),
                ('Module Difficulty', self.analyze_module_difficulty),
                ('Performance Trends', self.analyze_performance_trends),
                ('Correlation Analysis', self.analyze_correlations),
                ('Engagement Analysis', self.analyze_engagement),
                ('Cohort Analysis', self.analyze_cohorts),
                ('Predictive Analytics', self.predictive_analytics)
            ]

            for name, analysis_func in analyses:
                print(f"Generating {name}...")
                try:
                    analysis_func()
                    pdf.savefig()
                    plt.close()
                except Exception as e:
                    print(f"Error generating {name}: {e}")
                    continue

        print(f"\nComprehensive analytics report generated successfully!")
        print(f"Report saved as: {filename}")
        print(f"File size: {os.path.getsize(filename) / (1024*1024):.1f} MB")
