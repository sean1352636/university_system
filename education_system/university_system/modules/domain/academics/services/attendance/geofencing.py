"""Geofencing attendance system."""

import datetime
import json
import uuid
from education_system.university_system.infrastructure.database.db import get_connection

try:
    import geopy
    from geopy.distance import geodesic
    GEOFENCING_SUPPORT = True
except ImportError:
    GEOFENCING_SUPPORT = False


class GeofencingSystem:
    def __init__(self):
        self.active_locations = {}

    def create_geofenced_session(self, module_code, date, location_name, latitude, longitude, radius=50):
        """Create a geofenced attendance session"""
        try:
            session_id = str(uuid.uuid4())

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO attendance_sessions
            (session_id, module_code, date, location_name, latitude, longitude,
             geofence_radius, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (session_id, module_code, date, location_name, latitude, longitude, radius, 'System'))

            conn.commit()
            conn.close()

            self.active_locations[session_id] = {
                'module_code': module_code,
                'date': date,
                'location': (latitude, longitude),
                'radius': radius
            }

            return session_id

        except Exception as e:
            print(f"Error creating geofenced session: {e}")
            return None

    def check_location_attendance(self, student_id, latitude, longitude, session_id=None):
        """Check if student is within geofenced area for attendance"""
        if not GEOFENCING_SUPPORT:
            return False, "Geofencing not supported"

        try:
            student_location = (latitude, longitude)

            if session_id:
                # Check specific session
                if session_id in self.active_locations:
                    session_data = self.active_locations[session_id]
                    distance = geodesic(student_location, session_data['location']).meters

                    if distance <= session_data['radius']:
                        # Record attendance
                        return self.record_geofence_attendance(student_id, session_id, distance)
            else:
                # Check all active sessions
                for sid, session_data in self.active_locations.items():
                    distance = geodesic(student_location, session_data['location']).meters

                    if distance <= session_data['radius']:
                        return self.record_geofence_attendance(student_id, sid, distance)

            return False, "Not within any geofenced area"

        except Exception as e:
            print(f"Error checking location attendance: {e}")
            return False, "Error checking location"

    def record_geofence_attendance(self, student_id, session_id, distance):
        """Record attendance via geofencing"""
        try:
            session_data = self.active_locations[session_id]

            conn = get_connection()
            cursor = conn.cursor()

            # Check if already recorded
            cursor.execute('''
            SELECT id FROM attendance_records
            WHERE student_id = ? AND session_id = ?
            ''', (student_id, session_id))

            if cursor.fetchone():
                return False, "Already checked in via geofencing"

            # Record attendance
            cursor.execute('''
            INSERT INTO attendance_records
            (student_id, module_code, date, status, notes, recorded_by, recorded_at,
             check_in_method, location_data, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, session_data['module_code'], session_data['date'], 'Present',
                  f"Geofence check-in, distance: {distance:.1f}m", 'Geofence System',
                  datetime.datetime.now().isoformat(), 'geofencing',
                  json.dumps({'distance': distance}), session_id))

            conn.commit()
            conn.close()

            return True, f"Checked in via geofencing ({distance:.1f}m from center)"

        except Exception as e:
            print(f"Error recording geofence attendance: {e}")
            return False, "Error recording attendance"
