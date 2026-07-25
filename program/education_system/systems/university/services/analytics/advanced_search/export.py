"""Export functions: CSV, JSON, Excel, custom format, single student export."""
import csv
import json
from datetime import datetime

from education_system.systems.university.services.analytics.advanced_search import _globals


def export_to_json(filename):
    """Export results to JSON format"""
    try:
        data = []
        for student in _globals.last_search_results:
            student_dict = {
                'student_id': student[0],
                'email': student[1],
                'title': student[2],
                'first_name': student[3],
                'middle_name': student[4],
                'last_name': student[5],
                'gender': student[6],
                'date_of_birth': student[7],
                'age': student[8],
                'course': student[9],
                'registration_datetime': student[10]
            }
            data.append(student_dict)

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        print(f"✅ Data exported to {filename}")

    except Exception as e:
        print(f"Export error: {e}")

def export_to_excel(filename):
    """Export results to Excel format (simulation)"""
    print(f"📊 Excel export simulation - would export to {filename}")
    print("Note: In production, would use libraries like openpyxl or xlswriter")

    # Simulate Excel export
    try:
        # Create CSV as Excel substitute
        csv_filename = filename.replace('.xlsx', '.csv')
        export_to_csv(csv_filename)
        print(f"✅ Exported as CSV instead: {csv_filename}")
    except Exception as e:
        print(f"Export error: {e}")

def export_to_csv(filename):
    """Export results to CSV format"""
    try:
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow([
                'Student ID', 'Email', 'Title', 'First Name', 'Middle Name',
                'Last Name', 'Gender', 'Date of Birth', 'Age', 'Course',
                'Registration Datetime'
            ])

            # Write data
            for student in _globals.last_search_results:
                writer.writerow(student)

        print(f"✅ Data exported to {filename}")

    except Exception as e:
        print(f"Export error: {e}")

def custom_format_export():
    """Custom format export with user-defined fields"""
    print("\n📋 CUSTOM FORMAT EXPORT")
    print("-" * 40)

    print("Available fields:")
    fields = [
        'student_id', 'email', 'title', 'first_name', 'middle_name',
        'last_name', 'gender', 'date_of_birth', 'age', 'course',
        'registration_datetime'
    ]

    for i, field in enumerate(fields, 1):
        print(f"{i:2d}. {field}")

    selected = input("\nEnter field numbers (comma-separated): ").strip()

    try:
        indices = [int(x.strip()) - 1 for x in selected.split(',')]
        selected_fields = [fields[i] for i in indices if 0 <= i < len(fields)]

        if not selected_fields:
            print("No valid fields selected.")
            return

        # Choose separator
        separator = input("Enter field separator (default: comma): ").strip()
        if not separator:
            separator = ","

        # Export
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"custom_export_{timestamp}.txt"

        with open(filename, 'w') as f:
            # Write header
            f.write(separator.join(selected_fields) + "\n")

            # Write data
            for student in _globals.last_search_results:
                values = [str(student[fields.index(field)]) for field in selected_fields]
                f.write(separator.join(values) + "\n")

        print(f"✅ Custom export saved to {filename}")

    except (ValueError, IndexError) as e:
        print(f"Error in custom export: {e}")

def export_single_student(student, modules):
    """Export single student data"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"student_{student[0]}_{timestamp}.json"

    student_data = {
        'student_info': {
            'student_id': student[0],
            'email': student[1],
            'title': student[2],
            'first_name': student[3],
            'middle_name': student[4],
            'last_name': student[5],
            'gender': student[6],
            'date_of_birth': student[7],
            'age': student[8],
            'course': student[9],
            'registration_datetime': student[10]
        },
        'modules': [
            {
                'type': m[0],
                'code': m[1],
                'name': m[2],
                'grade': m[3],
                'enrollment_date': m[4]
            } for m in modules
        ],
        'export_date': datetime.now().isoformat()
    }

    try:
        with open(filename, 'w') as f:
            json.dump(student_data, f, indent=2, default=str)
        print(f"✅ Student data exported to {filename}")
    except Exception as e:
        print(f"Export error: {e}")
