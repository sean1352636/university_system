"""CLI handler for QR code attendance operations."""

import datetime
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.academics.services.attendance.records import get_modules


def handle_qr_system(qr_system):
    """Handle QR code system operations"""
    print("\n🔲 QR CODE ATTENDANCE SYSTEM")
    print("1. Generate QR Code for Session")
    print("2. Process QR Check-in")
    print("3. View Active QR Sessions")

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

                date = input("Enter date (YYYY-MM-DD, leave empty for today): ")
                if not date:
                    date = datetime.date.today().isoformat()

                start_time = input("Enter start time (HH:MM): ")
                end_time = input("Enter end time (HH:MM): ")
                location = input("Enter location (optional): ")

                session_id, qr_filename = qr_system.generate_session_qr(
                    module_code, date, start_time, end_time, location
                )

                if session_id:
                    print(f"✅ QR code generated successfully!")
                    print(f"Session ID: {session_id}")
                    print(f"QR Code saved as: {qr_filename}")
                else:
                    print("❌ Failed to generate QR code")
        except (ValueError, IndexError):
            print("Invalid selection.")

    elif choice == '2':
        student_id = input("Enter student ID: ")
        qr_data = input("Enter QR code data (JSON string): ")

        success, message = qr_system.process_qr_checkin(qr_data, student_id)

        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")

    elif choice == '3':
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT session_id, module_code, date, start_time, end_time, location_name, status
            FROM attendance_sessions
            WHERE status = 'active'
            ORDER BY date DESC, start_time DESC
            ''')

            active_sessions = cursor.fetchall()
            conn.close()

            if active_sessions:
                print("\n📋 ACTIVE QR SESSIONS")
                print("=" * 80)
                print(f"{'Session ID':<12} {'Module':<10} {'Date':<12} {'Start':<8} {'End':<8} {'Location':<20}")
                print("-" * 80)

                for session in active_sessions:
                    session_id, module_code, date, start_time, end_time, location_name, status = session
                    location_display = location_name[:18] + '..' if location_name and len(location_name) > 20 else (location_name or 'N/A')
                    print(f"{session_id[:10]:<12} {module_code:<10} {date:<12} {start_time:<8} {end_time:<8} {location_display:<20}")
            else:
                print("No active QR sessions found.")

        except Exception as e:
            print(f"Error retrieving QR sessions: {e}")
