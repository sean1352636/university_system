"""CLI handler for API management."""

import uuid
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domain.academics.services.attendance.settings import (
    get_enhanced_setting, set_enhanced_setting,
)
from education_system.systems.university.domain.academics.services.attendance.api import AttendanceAPI


def handle_api_management():
    """Handle API management"""
    print("\n🔌 API MANAGEMENT")
    print("1. Start API Server")
    print("2. View API Documentation")
    print("3. API Rate Limiting Settings")
    print("4. Generate API Key")

    choice = input("Enter your choice (1-4): ")

    if choice == '1':
        host = input("Enter host (default 127.0.0.1): ") or "127.0.0.1"
        port = input("Enter port (default 5000): ") or "5000"

        try:
            port = int(port)
            print(f"Starting API server at http://{host}:{port}")

            api = AttendanceAPI()
            api.run_api(host=host, port=port, debug=False)

        except KeyboardInterrupt:
            print("\nAPI server stopped.")
        except ValueError:
            print("Invalid port number.")
        except Exception as e:
            print(f"Error starting API server: {e}")

    elif choice == '2':
        print("\n📖 API DOCUMENTATION")
        print("="*50)

        endpoints = [
            ("POST", "/api/attendance/record", "Record attendance for a student"),
            ("GET", "/api/attendance/student/<id>", "Get student attendance statistics"),
            ("POST", "/api/qr/generate", "Generate QR code for session"),
            ("POST", "/api/qr/checkin", "Process QR code check-in"),
            ("GET", "/api/predictions/<student_id>/<module>", "Get risk prediction"),
        ]

        for method, endpoint, description in endpoints:
            print(f"{method:<6} {endpoint:<35} {description}")

        print("\nExample Usage:")
        print("curl -X POST http://localhost:5000/api/attendance/record \\")
        print("  -H 'Content-Type: application/json' \\")
        print("  -d '{\"student_id\":\"S001\",\"module_code\":\"CS101\",\"date\":\"2025-01-01\",\"status\":\"Present\"}'")

    elif choice == '3':
        current_limit = get_enhanced_setting('api_rate_limit', 1000, 'integer')
        print(f"Current API rate limit: {current_limit} requests per hour")

        try:
            new_limit = int(input("Enter new rate limit (requests per hour): "))
            if set_enhanced_setting('api_rate_limit', new_limit, data_type='integer'):
                print(f"✅ API rate limit updated to {new_limit} requests per hour!")
            else:
                print("❌ Failed to update rate limit.")
        except ValueError:
            print("Invalid rate limit value.")

    elif choice == '4':
        api_key = str(uuid.uuid4())
        service_name = input("Enter service name: ")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO api_integrations (integration_name, api_key, status)
            VALUES (?, ?, 'active')
            ''', (service_name, api_key))

            conn.commit()
            conn.close()

            print(f"✅ API key generated for {service_name}:")
            print(f"🔑 {api_key}")
            print("⚠️  Keep this key secure!")

        except Exception as e:
            print(f"Error generating API key: {e}")
