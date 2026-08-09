import numpy as np

from education_system.systems.university.services.analytics.student_analytics.config import CONFIG


class UtilitiesMixin:
    def data_quality_check(self):
        """Comprehensive data quality assessment"""
        import pandas as pd
        print("\n" + "="*60)
        print("DATA QUALITY ASSESSMENT")
        print("="*60)

        students_df = self.get_all_students()
        modules_df = self.get_all_modules()

        print("Analyzing data quality...")

        # Student data quality checks
        print("\nSTUDENT DATA QUALITY:")
        print("-" * 30)

        total_students = len(students_df)
        print(f"Total student records: {total_students}")

        # Missing data analysis
        missing_data = students_df.isnull().sum()
        print("\nMissing data by field:")
        for field, count in missing_data.items():
            if count > 0:
                percentage = (count / total_students) * 100
                print(f"  {field}: {count} ({percentage:.1f}%)")

        # Data type validation
        print("\nData type validation:")
        expected_types = {
            'age': 'numeric',
            'gpa': 'numeric',
            'engagement_score': 'numeric'
        }

        for field, expected_type in expected_types.items():
            if field in students_df.columns:
                if expected_type == 'numeric':
                    non_numeric = pd.to_numeric(students_df[field], errors='coerce').isnull().sum()
                    if non_numeric > 0:
                        print(f"  {field}: {non_numeric} non-numeric values found")
                    else:
                        print(f"  {field}: All values are numeric ✓")

        # Range validation
        print("\nRange validation:")
        validations = [
            ('age', 16, 100),
            ('gpa', 0.0, 4.0),
            ('engagement_score', 0, 100)
        ]

        for field, min_val, max_val in validations:
            if field in students_df.columns:
                out_of_range = ((students_df[field] < min_val) | (students_df[field] > max_val)).sum()
                if out_of_range > 0:
                    print(f"  {field}: {out_of_range} values outside range [{min_val}, {max_val}]")
                else:
                    print(f"  {field}: All values within expected range ✓")

        # Duplicate detection
        duplicates = students_df.duplicated().sum()
        print(f"\nDuplicate records: {duplicates}")

        if duplicates > 0:
            print("  Action needed: Remove duplicate records")
        else:
            print("  No duplicates found ✓")

        # Module data quality (if available)
        if not modules_df.empty:
            print("\nMODULE DATA QUALITY:")
            print("-" * 30)

            total_modules = len(modules_df)
            print(f"Total module records: {total_modules}")

            # Check for orphaned modules (students not in student table)
            if 'student_id' in modules_df.columns and 'student_id' in students_df.columns:
                orphaned = ~modules_df['student_id'].isin(students_df['student_id'])
                orphaned_count = orphaned.sum()

                if orphaned_count > 0:
                    print(f"Orphaned module records: {orphaned_count}")
                    print("  Action needed: Clean up module records with invalid student IDs")
                else:
                    print("All module records have valid student IDs ✓")

        # Generate data quality score
        total_issues = missing_data.sum() + duplicates
        if not modules_df.empty and 'student_id' in modules_df.columns:
            orphaned_count = (~modules_df['student_id'].isin(students_df['student_id'])).sum()
            total_issues += orphaned_count

        quality_score = max(0, 100 - (total_issues / total_students * 10))

        print(f"\nOVERALL DATA QUALITY SCORE: {quality_score:.1f}/100")

        if quality_score >= 90:
            print("Status: Excellent data quality ✓")
        elif quality_score >= 75:
            print("Status: Good data quality - minor issues to address")
        elif quality_score >= 60:
            print("Status: Fair data quality - several issues need attention")
        else:
            print("Status: Poor data quality - significant cleanup required")

        print("\nRecommendations:")
        if missing_data.sum() > 0:
            print("- Address missing data in critical fields")
        if duplicates > 0:
            print("- Remove duplicate student records")
        if total_issues == 0:
            print("- Data quality is excellent, no immediate action required")

    def configuration_settings(self):
        """Configuration settings management"""
        print("\n" + "="*60)
        print("CONFIGURATION SETTINGS")
        print("="*60)

        print("Current settings:")
        print("1. Color scheme")
        print("2. Export formats")
        print("3. Email configuration")
        print("4. Display preferences")
        print("5. Reset to defaults")
        print("6. Return to main menu")

        choice = input("Select option (1-6): ")

        if choice == '1':
            print("\nColor scheme options:")
            print("1. Default blue theme")
            print("2. Green theme")
            print("3. Red theme")
            print("4. Custom colors")

            color_choice = input("Select color scheme (1-4): ")

            if color_choice == '1':
                CONFIG['colors'] = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
            elif color_choice == '2':
                CONFIG['colors'] = ['#2ca02c', '#98df8a', '#1f77b4', '#aec7e8', '#ff7f0e', '#ffbb78']
            elif color_choice == '3':
                CONFIG['colors'] = ['#d62728', '#ff9896', '#1f77b4', '#aec7e8', '#ff7f0e', '#ffbb78']
            elif color_choice == '4':
                print("Enter 6 hex color codes (e.g., #1f77b4):")
                custom_colors = []
                for i in range(6):
                    color = input(f"Color {i+1}: ")
                    custom_colors.append(color)
                CONFIG['colors'] = custom_colors

            print("Color scheme updated!")

        elif choice == '2':
            print("\nCurrent export formats:", CONFIG['export_formats'])
            print("Available formats: png, pdf, svg, excel")

            formats = input("Enter desired formats (comma-separated): ").split(',')
            CONFIG['export_formats'] = [f.strip() for f in formats if f.strip()]
            print("Export formats updated!")

        elif choice == '3':
            print("\nEmail Configuration:")
            CONFIG['email_config']['sender_email'] = input("Sender email address: ")
            CONFIG['email_config']['sender_password'] = input("Email password: ")
            CONFIG['email_config']['smtp_server'] = input("SMTP server (default: smtp.gmail.com): ") or 'smtp.gmail.com'
            CONFIG['email_config']['smtp_port'] = int(input("SMTP port (default: 587): ") or 587)
            print("Email configuration updated!")

        elif choice == '4':
            print("\nDisplay Preferences:")
            CONFIG['figure_size'] = tuple(map(int, input("Figure size (width,height): ").split(',')))
            CONFIG['dpi'] = int(input("DPI for saved plots: ") or 300)
            print("Display preferences updated!")

        elif choice == '5':
            CONFIG['colors'] = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
            CONFIG['figure_size'] = (15, 10)
            CONFIG['dpi'] = 300
            CONFIG['export_formats'] = ['png', 'pdf', 'svg', 'excel']
            print("Settings reset to defaults!")

        elif choice == '6':
            return
