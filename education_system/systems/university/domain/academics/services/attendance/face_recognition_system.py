"""Face recognition attendance system."""

import datetime
import numpy as np
from education_system.systems.university.infrastructure.database.db import get_connection

try:
    import cv2
    import face_recognition
    FACE_RECOGNITION_SUPPORT = True
except ImportError:
    FACE_RECOGNITION_SUPPORT = False


class FaceRecognitionSystem:
    def __init__(self):
        self.known_encodings = {}
        self.load_known_faces()

    def load_known_faces(self):
        """Load known face encodings from database"""
        if not FACE_RECOGNITION_SUPPORT:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT student_id, face_encoding FROM student_biometrics
            WHERE status = 'active' AND face_encoding IS NOT NULL
            ''')

            for student_id, encoding_blob in cursor.fetchall():
                if encoding_blob:
                    encoding = np.frombuffer(encoding_blob, dtype=np.float64)
                    self.known_encodings[student_id] = encoding

            conn.close()
            print(f"Loaded {len(self.known_encodings)} face encodings")

        except Exception as e:
            print(f"Error loading face encodings: {e}")

    def enroll_student_face(self, student_id, image_path):
        """Enroll a student's face for recognition"""
        if not FACE_RECOGNITION_SUPPORT:
            return False, "Face recognition not supported"

        try:
            # Load image and extract face encoding
            image = face_recognition.load_image_file(image_path)
            encodings = face_recognition.face_encodings(image)

            if not encodings:
                return False, "No face found in image"

            if len(encodings) > 1:
                return False, "Multiple faces found in image"

            encoding = encodings[0]

            # Store in database
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            INSERT OR REPLACE INTO student_biometrics
            (student_id, face_encoding, face_photo_path, last_updated)
            VALUES (?, ?, ?, ?)
            ''', (student_id, encoding.tobytes(), image_path, datetime.datetime.now().isoformat()))

            conn.commit()
            conn.close()

            # Update known encodings
            self.known_encodings[student_id] = encoding

            return True, "Face enrolled successfully"

        except Exception as e:
            print(f"Error enrolling face: {e}")
            return False, "Error enrolling face"

    def recognize_face_attendance(self, image_path, module_code, session_date):
        """Recognize face and record attendance"""
        if not FACE_RECOGNITION_SUPPORT:
            return False, "Face recognition not supported", None

        try:
            # Load image
            image = face_recognition.load_image_file(image_path)
            face_encodings = face_recognition.face_encodings(image)

            if not face_encodings:
                return False, "No face found in image", None

            # Compare with known faces
            for student_id, known_encoding in self.known_encodings.items():
                matches = face_recognition.compare_faces([known_encoding], face_encodings[0])

                if matches[0]:
                    # Record attendance
                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                    INSERT INTO attendance_records
                    (student_id, module_code, date, status, notes, recorded_by, recorded_at,
                     check_in_method)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (student_id, module_code, session_date, 'Present',
                          "Face recognition check-in", 'Face Recognition System',
                          datetime.datetime.now().isoformat(), 'face_recognition'))

                    conn.commit()
                    conn.close()

                    return True, "Face recognized and attendance recorded", student_id

            return False, "Face not recognized", None

        except Exception as e:
            print(f"Error in face recognition: {e}")
            return False, "Error in face recognition", None
