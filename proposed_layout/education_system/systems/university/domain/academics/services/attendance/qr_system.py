"""QR code attendance system."""

import datetime
import json
import sqlite3
import uuid
from datetime import timedelta
from pathlib import Path
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.paths import QR_CODES_DIR
from education_system.systems.university.domain.academics.services.attendance.settings import get_setting
from education_system.systems.university.domain.academics.services.attendance.gamification import update_gamification_points


class QRAttendanceSystem:
    def __init__(self):
        self.active_sessions = {}

    def generate_session_qr(self, module_code, session_date, start_time, end_time, location=None):
        """Generate QR code for attendance session"""
        import qrcode
        try:
            session_id = str(uuid.uuid4())
            expiry_minutes = int(get_setting('qr_code_expiry_minutes') or 15)
            expiry_time = (datetime.datetime.now() + timedelta(minutes=expiry_minutes)).isoformat()

            # Create session data
            session_data = {
                'session_id': session_id,
                'module_code': module_code,
                'date': session_date,
                'start_time': start_time,
                'end_time': end_time,
                'expires': expiry_time,
                'location': location
            }

            # Store in database
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO attendance_sessions
            (session_id, module_code, date, start_time, end_time, location_name,
             qr_code_data, qr_code_expires, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (session_id, module_code, session_date, start_time, end_time,
                  location, json.dumps(session_data), expiry_time, 'System'))

            conn.commit()
            conn.close()

            # Generate QR code with URL format instead of raw JSON
            # This creates a URL that can be opened in a browser or handled by a mobile app
            # Format: attendance://checkin?session=SESSION_ID&module=MODULE_CODE&date=DATE
            qr_data = f"attendance://checkin?session={session_id}&module={module_code}&date={session_date}&time={start_time}-{end_time}"
            if location:
                # URL-encode location for safety
                from urllib.parse import quote
                qr_data += f"&location={quote(location)}"

            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_data)
            qr.make(fit=True)

            qr_image = qr.make_image(fill_color="black", back_color="white")

            # Save QR code image to QR codes directory
            qr_filename = Path(QR_CODES_DIR) / f"qr_session_{session_id}.png"
            qr_image.save(str(qr_filename))

            print(f"QR code generated: {qr_filename}")
            print(f"Session ID: {session_id}")
            print(f"QR data: {qr_data}")
            print(f"Expires: {expiry_time}")

            return session_id, str(qr_filename)

        except Exception as e:
            print(f"Error generating QR code: {e}")
            return None, None

    def process_qr_checkin(self, qr_data, student_id, location_data=None):
        """Process QR code check-in"""
        try:
            # Handle both new URI format and old JSON format
            if qr_data.startswith('attendance://checkin?'):
                # Parse new URI format
                from urllib.parse import parse_qs, urlparse
                parsed = urlparse(qr_data)
                params = parse_qs(parsed.query)

                session_id = params.get('session', [None])[0]
                module_code = params.get('module', [None])[0]
                date = params.get('date', [None])[0]

                if not session_id:
                    return False, "Invalid QR code format"

                session_data = {
                    'session_id': session_id,
                    'module_code': module_code,
                    'date': date
                }
            else:
                # Old JSON format
                session_data = json.loads(qr_data)
                session_id = session_data['session_id']

            # Verify session exists and is valid. Wrap all DB work in
            # try/finally so the connection is released on every exit path
            # (a leaked connection here was causing "database is locked"
            # on the next check-in).
            conn = get_connection()
            # Access columns by name so the expiry check can't drift if the
            # table's column order ever differs from the INSERT's order.
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT * FROM attendance_sessions
                WHERE session_id = ? AND status = 'active'
                ''', (session_id,))

                session = cursor.fetchone()

                if not session:
                    return False, "Invalid or expired session"

                # Check if QR code has expired (from database, not from QR
                # data). A NULL/blank expiry means "no expiry recorded" —
                # don't block.
                expires_raw = session['qr_code_expires']
                if expires_raw:
                    expiry_time = datetime.datetime.fromisoformat(expires_raw)
                    if datetime.datetime.now() > expiry_time:
                        return False, "QR code has expired"

                # Check if student already checked in for this session
                cursor.execute('''
                SELECT id FROM attendance_records
                WHERE student_id = ? AND module_code = ? AND date = ? AND session_id = ?
                ''', (student_id, session_data['module_code'], session_data['date'], session_id))

                if cursor.fetchone():
                    return False, "Already checked in for this session"

                # Determine attendance status based on time
                current_time = datetime.datetime.now().time()
                start_time = datetime.datetime.strptime(session_data['start_time'], '%H:%M').time()
                late_tolerance = int(get_setting('late_tolerance_minutes') or 15)
                late_threshold = (datetime.datetime.combine(datetime.date.today(), start_time) +
                                timedelta(minutes=late_tolerance)).time()

                if current_time <= start_time:
                    status = 'Present'
                elif current_time <= late_threshold:
                    status = 'Late'
                else:
                    status = 'Late'  # Could be configured to mark as absent after certain time

                # Record attendance
                cursor.execute('''
                INSERT INTO attendance_records
                (student_id, module_code, date, status, notes, recorded_by, recorded_at,
                 check_in_method, location_data, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, session_data['module_code'], session_data['date'], status,
                      f"QR check-in at {current_time}", 'QR System', datetime.datetime.now().isoformat(),
                      'qr_code', json.dumps(location_data) if location_data else None, session_id))

                conn.commit()
            finally:
                conn.close()

            # Update gamification points (after the connection is closed so
            # we don't hold a write lock during the gamification update).
            update_gamification_points(student_id, 'attendance')

            return True, f"Successfully checked in as {status}"

        except Exception as e:
            print(f"Error processing QR check-in: {e}")
            return False, "Error processing check-in"
