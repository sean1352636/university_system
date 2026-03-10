"""CLI handler for face recognition attendance system."""

import datetime
import os
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.academics.services.attendance.records import get_modules
from education_system.university_system.modules.domain.academics.services.attendance.face_recognition_system import FACE_RECOGNITION_SUPPORT


def handle_face_recognition_system(face_system):
    """Handle face recognition system operations"""
    if not FACE_RECOGNITION_SUPPORT:
        print("❌ Face recognition not supported. Please install face_recognition and opencv-python packages.")
        return

    print("\n👤 FACE RECOGNITION ATTENDANCE SYSTEM")
    print("1. Enroll Student Face")
    print("2. Recognize Face for Attendance")
    print("3. View Enrolled Students")

    choice = input("Enter your choice (1-3): ")

    if choice == '1':
        student_id = input("Enter student ID: ")
        image_path = input("Enter path to student photo: ")

        if not os.path.exists(image_path):
            print("❌ Image file not found.")
            return

        success, message = face_system.enroll_student_face(student_id, image_path)

        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")

    elif choice == '2':
        image_path = input("Enter path to image for recognition: ")

        if not os.path.exists(image_path):
            print("❌ Image file not found.")
            return

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

                success, message, student_id = face_system.recognize_face_attendance(image_path, module_code, date)

                if success:
                    print(f"✅ {message} - Student ID: {student_id}")
                else:
                    print(f"❌ {message}")
        except (ValueError, IndexError):
            print("Invalid selection.")

    elif choice == '3':
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT sb.student_id, s.first_name, s.last_name, sb.enrolled_date
            FROM student_biometrics sb
            JOIN students s ON sb.student_id = s.student_id
            WHERE sb.status = 'active'
            ORDER BY sb.enrolled_date DESC
            ''')

            enrolled_students = cursor.fetchall()
            conn.close()

            if enrolled_students:
                print("\nEnrolled Students (Face Recognition):")
                print(f"{'Student ID':<12} {'Name':<30} {'Enrolled Date'}")
                print("-" * 60)

                for student_id, first_name, last_name, enrolled_date in enrolled_students:
                    name = f"{first_name} {last_name}"
                    print(f"{student_id:<12} {name:<30} {enrolled_date}")
            else:
                print("No students enrolled for face recognition.")

        except Exception as e:
            print(f"Error retrieving enrolled students: {e}")
