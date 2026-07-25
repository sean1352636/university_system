"""CLI handlers for viewing records, student/module reports, and taking attendance."""

import datetime
from pathlib import Path
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domain.academics.services.attendance.records import (
    get_modules, get_attendance_records, get_student_attendance,
    get_module_attendance, record_attendance,
)
from education_system.systems.university.domain.academics.services.attendance.reporting import (
    generate_student_attendance_report, generate_module_attendance_report,
)


def take_attendance():
    """Traditional attendance taking function"""
    modules = get_modules()
    if not modules:
        print("No modules found.")
        return

    print("\nAvailable Modules:")
    for i, (code, name) in enumerate(modules, 1):
        print(f"{i}. {code} - {name}")

    try:
        module_idx = int(input("Select module number: ")) - 1
        if 0 <= module_idx < len(modules):
            module_code = modules[module_idx][0]

            date = input("Enter date (YYYY-MM-DD, leave empty for today): ")
            if not date:
                date = datetime.date.today().isoformat()

            # Get students for this module
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT DISTINCT s.student_id, s.first_name, s.last_name
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE sm.module_code = ?
            ORDER BY s.student_id
            ''', (module_code,))

            students = cursor.fetchall()
            conn.close()

            if not students:
                print("No students found for this module.")
                return

            print(f"\nTaking attendance for {module_code} on {date}")
            print("Available statuses: Present, Late, Excused, Absent")

            attendance_data = []

            for student_id, first_name, last_name in students:
                name = f"{first_name} {last_name}"
                status = input(f"Status for {student_id} ({name}): ").strip()

                if not status:
                    status = "Absent"

                notes = input(f"Notes for {student_id} (optional): ").strip()

                attendance_data.append((student_id, status, notes))

            if record_attendance(module_code, date, attendance_data, "Manual Entry"):
                print("✅ Attendance recorded successfully!")
            else:
                print("❌ Failed to record attendance.")

    except (ValueError, IndexError):
        print("Invalid selection.")


def handle_view_records():
    """Handle viewing attendance records"""
    print("\n📋 VIEW ATTENDANCE RECORDS")
    print("1. By Module")
    print("2. By Student")
    print("3. By Date")
    print("4. Recent Check-ins")

    choice = input("Enter your choice (1-4): ")

    if choice == '1':
        modules = get_modules()
        if not modules:
            print("No modules found.")
            return

        print("\nAvailable Modules:")
        for i, (code, name) in enumerate(modules, 1):
            print(f"{i}. {code} - {name}")

        try:
            module_idx = int(input("\nSelect module number: ")) - 1
            if 0 <= module_idx < len(modules):
                module_code = modules[module_idx][0]

                date_from = input("Enter start date (YYYY-MM-DD, leave empty for all): ")
                date_to = input("Enter end date (YYYY-MM-DD, leave empty for all): ")

                records = get_attendance_records(module_code=module_code, date_from=date_from, date_to=date_to)

                if records:
                    print(f"\n📊 ATTENDANCE RECORDS FOR {module_code}")
                    print("=" * 80)
                    print(f"{'Student ID':<12} {'Name':<25} {'Date':<12} {'Status':<10} {'Method':<12} {'Notes'}")
                    print("-" * 80)

                    for record in records[:50]:  # Limit to 50 records
                        student_id, first_name, last_name, _, _, date, status, notes = record
                        name = f"{first_name} {last_name}"

                        # Get check-in method
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute('SELECT check_in_method FROM attendance_records WHERE student_id = ? AND date = ?',
                                     (student_id, date))
                        method_result = cursor.fetchone()
                        method = method_result[0] if method_result else 'manual'
                        conn.close()

                        print(f"{student_id:<12} {name:<25} {date:<12} {status:<10} {method:<12} {notes or ''}")

                    if len(records) > 50:
                        print(f"\n... and {len(records) - 50} more records")
                else:
                    print("No records found.")
        except (ValueError, IndexError):
            print("Invalid selection.")

    elif choice == '2':
        student_id = input("Enter student ID: ")
        records = get_attendance_records(student_id=student_id)

        if records:
            print(f"\n📊 ATTENDANCE RECORDS FOR STUDENT {student_id}")
            print("=" * 70)
            print(f"{'Module':<12} {'Date':<12} {'Status':<10} {'Method':<12} {'Notes'}")
            print("-" * 70)

            for record in records[:50]:
                _, _, _, module_code, _, date, status, notes = record

                # Get check-in method
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT check_in_method FROM attendance_records WHERE student_id = ? AND date = ? AND module_code = ?',
                             (student_id, date, module_code))
                method_result = cursor.fetchone()
                method = method_result[0] if method_result else 'manual'
                conn.close()

                print(f"{module_code:<12} {date:<12} {status:<10} {method:<12} {notes or ''}")
        else:
            print("No records found.")

    elif choice == '3':
        date = input("Enter date (YYYY-MM-DD): ")

        try:
            datetime.datetime.strptime(date, '%Y-%m-%d')
            records = get_attendance_records(date_from=date, date_to=date)

            if records:
                print(f"\n📊 ATTENDANCE RECORDS FOR {date}")
                print("=" * 80)
                print(f"{'Module':<12} {'Student ID':<12} {'Name':<25} {'Status':<10} {'Method':<12}")
                print("-" * 80)

                for record in records:
                    student_id, first_name, last_name, module_code, _, _, status, _ = record
                    name = f"{first_name} {last_name}"

                    # Get check-in method
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('SELECT check_in_method FROM attendance_records WHERE student_id = ? AND date = ? AND module_code = ?',
                                 (student_id, date, module_code))
                    method_result = cursor.fetchone()
                    method = method_result[0] if method_result else 'manual'
                    conn.close()

                    print(f"{module_code:<12} {student_id:<12} {name:<25} {status:<10} {method:<12}")
            else:
                print("No records found.")
        except ValueError:
            print("Invalid date format.")

    elif choice == '4':
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT ar.student_id, s.first_name, s.last_name, ar.module_code,
                   ar.date, ar.status, ar.check_in_method, ar.recorded_at
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            WHERE ar.recorded_at >= datetime('now', '-24 hours')
            ORDER BY ar.recorded_at DESC
            LIMIT 20
            ''')

            recent_records = cursor.fetchall()
            conn.close()

            if recent_records:
                print("\n🕐 RECENT CHECK-INS (Last 24 hours)")
                print("=" * 90)
                print(f"{'Student ID':<12} {'Name':<25} {'Module':<10} {'Status':<10} {'Method':<12} {'Time'}")
                print("-" * 90)

                for record in recent_records:
                    student_id, first_name, last_name, module_code, date, status, method, recorded_at = record
                    name = f"{first_name} {last_name}"
                    time_str = recorded_at.split('T')[1][:5] if 'T' in recorded_at else recorded_at[-8:-3]

                    print(f"{student_id:<12} {name:<25} {module_code:<10} {status:<10} {method:<12} {time_str}")
            else:
                print("No recent check-ins found.")

        except Exception as e:
            print(f"Error retrieving recent records: {e}")


def handle_student_reports():
    """Handle student attendance reports"""
    import pandas as pd
    print("\n📊 STUDENT ATTENDANCE REPORTS")
    print("1. Individual Student Report")
    print("2. Batch Student Reports")
    print("3. At-Risk Students Report")

    choice = input("Enter your choice (1-3): ")

    if choice == '1':
        student_id = input("Enter student ID: ")

        print("\nOutput Format:")
        print("1. Screen")
        print("2. Excel")
        print("3. PDF")

        format_choice = input("Enter format choice (1-3): ")

        if format_choice == '1':
            generate_student_attendance_report(student_id, 'screen')
        elif format_choice == '2':
            output_path = input("Enter output path (leave empty for default): ")
            generate_student_attendance_report(student_id, 'csv', output_path)
        elif format_choice == '3':
            output_path = input("Enter output path (leave empty for default): ")
            generate_student_attendance_report(student_id, 'pdf', output_path)

    elif choice == '2':
        print("Generating batch reports for all students...")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM students ORDER BY student_id')
            students = cursor.fetchall()
            conn.close()

            output_dir = Path("batch_reports")
            output_dir.mkdir(exist_ok=True)

            success_count = 0
            for student_id, in students:
                output_path = output_dir / f"attendance_report_{student_id}.pdf"

                if generate_student_attendance_report(student_id, 'pdf', str(output_path)):
                    success_count += 1

            print(f"✅ Generated {success_count} student reports in 'batch_reports' folder")

        except Exception as e:
            print(f"Error generating batch reports: {e}")

    elif choice == '3':
        threshold = input("Enter attendance threshold (default 75%): ") or "75"

        try:
            threshold = float(threshold)

            conn = get_connection()
            query = '''
            SELECT
                ar.student_id,
                s.first_name,
                s.last_name,
                s.email_address,
                AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as attendance_rate,
                COUNT(*) as total_sessions
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            WHERE ar.date >= date('now', '-30 days')
            GROUP BY ar.student_id, s.first_name, s.last_name, s.email_address
            HAVING attendance_rate < ?
            ORDER BY attendance_rate ASC
            '''

            at_risk_df = pd.read_sql_query(query, conn, params=[threshold])
            conn.close()

            if not at_risk_df.empty:
                print(f"\n⚠️  AT-RISK STUDENTS (Below {threshold}% attendance)")
                print("=" * 80)
                print(f"{'Student ID':<12} {'Name':<25} {'Email':<25} {'Rate':<8} {'Sessions'}")
                print("-" * 80)

                for _, row in at_risk_df.iterrows():
                    name = f"{row['first_name']} {row['last_name']}"
                    print(f"{row['student_id']:<12} {name:<25} {row['email_address']:<25} {row['attendance_rate']:<8.1f}% {row['total_sessions']}")

                # Save to Excel
                output_path = f"at_risk_students_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
                at_risk_df.to_excel(output_path, index=False)
                print(f"\n✅ Report saved to: {output_path}")
            else:
                print(f"✅ No students below {threshold}% attendance threshold.")

        except ValueError:
            print("Invalid threshold value.")
        except Exception as e:
            print(f"Error generating at-risk report: {e}")


def handle_module_reports():
    """Handle module attendance reports"""
    import pandas as pd
    print("\n📊 MODULE ATTENDANCE REPORTS")
    print("1. Individual Module Report")
    print("2. All Modules Summary")
    print("3. Module Comparison")

    choice = input("Enter your choice (1-3): ")

    if choice == '1':
        modules = get_modules()
        if not modules:
            print("No modules found.")
            return

        print("\nAvailable Modules:")
        for i, (code, name) in enumerate(modules, 1):
            print(f"{i}. {code} - {name}")

        try:
            module_idx = int(input("Select module number: ")) - 1
            if 0 <= module_idx < len(modules):
                module_code = modules[module_idx][0]

                date_from = input("Enter start date (YYYY-MM-DD, leave empty for all): ")
                date_to = input("Enter end date (YYYY-MM-DD, leave empty for all): ")

                print("\nOutput Format:")
                print("1. Screen")
                print("2. Excel")
                print("3. PDF")

                format_choice = input("Enter format choice (1-3): ")

                if format_choice == '1':
                    generate_module_attendance_report(module_code, date_from, date_to, 'screen')
                elif format_choice == '2':
                    output_path = input("Enter output path (leave empty for default): ")
                    generate_module_attendance_report(module_code, date_from, date_to, 'csv', output_path)
                elif format_choice == '3':
                    output_path = input("Enter output path (leave empty for default): ")
                    generate_module_attendance_report(module_code, date_from, date_to, 'pdf', output_path)
        except (ValueError, IndexError):
            print("Invalid selection.")

    elif choice == '2':
        try:
            conn = get_connection()

            query = '''
            SELECT
                ar.module_code,
                COALESCE(sm.module_name, ar.module_code) as module_name,
                COUNT(DISTINCT ar.student_id) as enrolled_students,
                COUNT(*) as total_sessions,
                AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as attendance_rate
            FROM attendance_records ar
            LEFT JOIN (SELECT DISTINCT module_code, module_name FROM student_modules) sm
                ON ar.module_code = sm.module_code
            GROUP BY ar.module_code
            ORDER BY attendance_rate DESC
            '''

            summary_df = pd.read_sql_query(query, conn)
            conn.close()

            if not summary_df.empty:
                print("\n📊 ALL MODULES ATTENDANCE SUMMARY")
                print("=" * 80)
                print(f"{'Module':<12} {'Name':<30} {'Students':<10} {'Rate':<8} {'Sessions'}")
                print("-" * 80)

                for _, row in summary_df.iterrows():
                    module_name = row['module_name'][:28] + '..' if len(str(row['module_name'])) > 30 else str(row['module_name'])

                    print(f"{row['module_code']:<12} {module_name:<30} {row['enrolled_students']:<10} " +
                          f"{row['attendance_rate']:<8.1f}% {row['total_sessions']}")

                # Save to Excel
                output_path = f"all_modules_summary_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
                summary_df.to_excel(output_path, index=False)
                print(f"\n✅ Summary saved to: {output_path}")
            else:
                print("No module data found.")

        except Exception as e:
            print(f"Error generating modules summary: {e}")

    elif choice == '3':
        modules = get_modules()
        if len(modules) < 2:
            print("Need at least 2 modules for comparison.")
            return

        print("\nSelect modules to compare:")
        for i, (code, name) in enumerate(modules, 1):
            print(f"{i}. {code} - {name}")

        try:
            selections = input("Enter module numbers separated by commas (e.g., 1,2,3): ")
            selected_indices = [int(x.strip()) - 1 for x in selections.split(',')]

            selected_modules = [modules[i] for i in selected_indices if 0 <= i < len(modules)]

            if len(selected_modules) < 2:
                print("Please select at least 2 modules.")
                return

            # Generate comparison data
            comparison_data = []

            for module_code, module_name in selected_modules:
                stats = get_module_attendance(module_code)

                comparison_data.append({
                    'Module Code': module_code,
                    'Module Name': module_name,
                    'Total Sessions': stats['total_sessions'],
                    'Overall Attendance': f"{stats['overall_percentage']:.1f}%",
                    'Number of Students': len(stats['students'])
                })

            # Display comparison
            print("\n🔍 MODULE COMPARISON")
            print("=" * 80)

            df = pd.DataFrame(comparison_data)
            print(df.to_string(index=False))

            # Save comparison
            output_path = f"module_comparison_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
            df.to_excel(output_path, index=False)
            print(f"\n✅ Comparison saved to: {output_path}")

        except (ValueError, IndexError):
            print("Invalid module selection.")
        except Exception as e:
            print(f"Error generating comparison: {e}")
