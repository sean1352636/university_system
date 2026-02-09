import os
from university_system.infrastructure.database.db import sqlite3, DatabaseManager
from university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
import datetime
import calendar
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import json
import qrcode
import hashlib
import uuid
import threading
import time
import smtplib
import requests
from pathlib import Path
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from collections import defaultdict, Counter
from datetime import timedelta, date
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import flask
from flask import Flask, request, jsonify, render_template_string
import schedule
import warnings
from university_system.infrastructure.database.db import get_connection
from university_system.modules.shared.constants.paths import QR_CODES_DIR
warnings.filterwarnings('ignore')

# Try to import optional dependencies
try:
    # Try to import the email helper from the refactored utils module
    from university_system.infrastructure.email import queue_template_email
    EMAIL_SUPPORT = True
except ImportError:
    EMAIL_SUPPORT = False

try:
    import cv2
    import face_recognition
    FACE_RECOGNITION_SUPPORT = True
except ImportError:
    FACE_RECOGNITION_SUPPORT = False

try:
    import geopy
    from geopy.distance import geodesic
    GEOFENCING_SUPPORT = True
except ImportError:
    GEOFENCING_SUPPORT = False

# Enhanced Database Schema
def init_enhanced_attendance_db():
    """Initialize enhanced attendance tracking database with all new features"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Original attendance records table (enhanced)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            date TEXT,
            status TEXT,
            notes TEXT,
            recorded_by TEXT,
            recorded_at TEXT,
            check_in_method TEXT DEFAULT 'manual',
            location_data TEXT,
            ip_address TEXT,
            session_id TEXT,
            makeup_for_date TEXT,
            verification_status TEXT DEFAULT 'verified',
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')
        
        # Enhanced attendance settings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_name TEXT UNIQUE,
            setting_value TEXT,
            description TEXT,
            category TEXT DEFAULT 'general',
            data_type TEXT DEFAULT 'string',
            last_modified TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Attendance sessions (for QR codes and geofencing)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE,
            module_code TEXT,
            date TEXT,
            start_time TEXT,
            end_time TEXT,
            location_name TEXT,
            latitude REAL,
            longitude REAL,
            geofence_radius INTEGER DEFAULT 50,
            qr_code_data TEXT,
            qr_code_expires TEXT,
            session_type TEXT DEFAULT 'lecture',
            max_capacity INTEGER,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')
        
        # Student biometric data
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_biometrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            face_encoding BLOB,
            face_photo_path TEXT,
            enrolled_date TEXT DEFAULT CURRENT_TIMESTAMP,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Attendance alerts and notifications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id TEXT UNIQUE,
            student_id TEXT,
            module_code TEXT,
            alert_type TEXT,
            severity TEXT,
            message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sent_at TEXT,
            acknowledged_at TEXT,
            status TEXT DEFAULT 'pending',
            recipient_email TEXT,
            recipient_phone TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')
        
        # Attendance policies and rules
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_id TEXT UNIQUE,
            name TEXT,
            description TEXT,
            module_code TEXT,
            course TEXT,
            min_attendance_percentage REAL,
            max_consecutive_absences INTEGER,
            late_tolerance_minutes INTEGER DEFAULT 15,
            makeup_allowed BOOLEAN DEFAULT 1,
            auto_fail_threshold REAL,
            grace_period_days INTEGER DEFAULT 0,
            effective_from TEXT,
            effective_until TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active'
        )
        ''')
        
        # Gamification system
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_gamification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            points INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            badges TEXT,
            achievements TEXT,
            streak_days INTEGER DEFAULT 0,
            best_streak INTEGER DEFAULT 0,
            last_attendance_date TEXT,
            total_rewards INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Attendance appeals
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appeal_id TEXT UNIQUE,
            student_id TEXT,
            module_code TEXT,
            attendance_record_id INTEGER,
            original_status TEXT,
            requested_status TEXT,
            reason TEXT,
            evidence_files TEXT,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            reviewed_by TEXT,
            reviewed_at TEXT,
            decision TEXT,
            decision_reason TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code),
            FOREIGN KEY (attendance_record_id) REFERENCES attendance_records (id)
        )
        ''')
        
        # System audit log
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT,
            table_name TEXT,
            record_id TEXT,
            old_values TEXT,
            new_values TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT
        )
        ''')
        
        # API keys and integrations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_name TEXT UNIQUE,
            api_key TEXT,
            endpoint_url TEXT,
            status TEXT DEFAULT 'active',
            last_sync TEXT,
            sync_frequency TEXT DEFAULT 'daily',
            config_data TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Predictive analytics data
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            prediction_date TEXT,
            predicted_attendance_rate REAL,
            risk_level TEXT,
            confidence_score REAL,
            factors TEXT,
            recommendations TEXT,
            model_version TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')
        
        # Insert enhanced default settings
        enhanced_settings = [
            # Original settings
            ('attendance_threshold_warning', '80', 'Attendance percentage below which a warning is issued', 'thresholds', 'integer'),
            ('attendance_threshold_critical', '70', 'Attendance percentage below which critical action is required', 'thresholds', 'integer'),
            ('consecutive_absences_warning', '2', 'Number of consecutive absences before a warning is issued', 'thresholds', 'integer'),
            ('consecutive_absences_critical', '3', 'Number of consecutive absences before critical action is required', 'thresholds', 'integer'),
            ('auto_email_warnings', 'False', 'Whether to automatically email students with attendance warnings', 'notifications', 'boolean'),
            ('attendance_statuses', 'Present,Late,Excused,Absent', 'Comma-separated list of valid attendance statuses', 'general', 'string'),
            
            # New enhanced settings
            ('enable_qr_checkin', 'True', 'Enable QR code check-in system', 'features', 'boolean'),
            ('qr_code_expiry_minutes', '15', 'QR code expiry time in minutes', 'qr_system', 'integer'),
            ('enable_geofencing', 'False', 'Enable location-based attendance', 'features', 'boolean'),
            ('geofence_radius_meters', '50', 'Geofence radius in meters', 'location', 'integer'),
            ('enable_face_recognition', 'False', 'Enable facial recognition for attendance', 'features', 'boolean'),
            ('enable_gamification', 'True', 'Enable gamification features', 'features', 'boolean'),
            ('points_per_attendance', '10', 'Points awarded for each attendance', 'gamification', 'integer'),
            ('streak_bonus_multiplier', '1.5', 'Bonus multiplier for attendance streaks', 'gamification', 'float'),
            ('enable_sms_notifications', 'False', 'Enable SMS notifications', 'notifications', 'boolean'),
            ('sms_api_key', '', 'SMS service API key', 'integrations', 'string'),
            ('enable_parent_portal', 'False', 'Enable parent access to attendance', 'features', 'boolean'),
            ('auto_backup_enabled', 'True', 'Enable automatic data backup', 'system', 'boolean'),
            ('backup_frequency_hours', '24', 'Backup frequency in hours', 'system', 'integer'),
            ('api_rate_limit', '1000', 'API requests per hour limit', 'api', 'integer'),
            ('enable_audit_log', 'True', 'Enable detailed audit logging', 'system', 'boolean'),
            ('session_timeout_minutes', '60', 'User session timeout in minutes', 'security', 'integer'),
            ('enable_two_factor_auth', 'False', 'Enable two-factor authentication', 'security', 'boolean'),
            ('dashboard_refresh_seconds', '30', 'Dashboard auto-refresh interval', 'ui', 'integer'),
            ('enable_dark_mode', 'False', 'Enable dark mode interface', 'ui', 'boolean'),
            ('language', 'en', 'Default system language', 'ui', 'string'),
            ('timezone', 'UTC', 'Default system timezone', 'system', 'string'),
            ('enable_predictive_analytics', 'True', 'Enable ML-based predictions', 'analytics', 'boolean'),
            ('prediction_model_accuracy_threshold', '0.75', 'Minimum model accuracy required', 'analytics', 'float'),
            ('enable_auto_interventions', 'False', 'Enable automatic intervention recommendations', 'analytics', 'boolean')
        ]
        
        for setting in enhanced_settings:
            cursor.execute('''
            INSERT OR IGNORE INTO attendance_settings 
            (setting_name, setting_value, description, category, data_type)
            VALUES (?, ?, ?, ?, ?)
            ''', setting)
        
        conn.commit()
        conn.close()
        print("Enhanced attendance database initialized successfully!")
        return True
        
    except sqlite3.Error as e:
        print(f"An error occurred while initializing the enhanced attendance database: {e}")
        return False

def create_missing_tables():
    """Create missing tables needed by reporting system"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create student_attendance table from attendance_records
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_attendance AS
        SELECT student_id, module_code, date, status, notes, recorded_at
        FROM attendance_records
        WHERE student_id IS NOT NULL
        ''')
        
        # Ensure registration_datetime exists in students table
        cursor.execute("PRAGMA table_info(students)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'registration_datetime' not in columns:
            cursor.execute('ALTER TABLE students ADD COLUMN registration_datetime TEXT')
            # Set default values
            cursor.execute('''
            UPDATE students 
            SET registration_datetime = datetime('now', '-' || (CAST(student_id AS INTEGER) * 7) || ' days')
            WHERE registration_datetime IS NULL
            ''')
        
        conn.commit()
        conn.close()
        print("✅ Missing tables created successfully")
        
    except Exception as e:
        print(f"Error creating missing tables: {e}")

# QR Code System
class QRAttendanceSystem:
    def __init__(self):
        self.active_sessions = {}
    
    def generate_session_qr(self, module_code, session_date, start_time, end_time, location=None):
        """Generate QR code for attendance session"""
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

            # Verify session exists and is valid
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT * FROM attendance_sessions
            WHERE session_id = ? AND status = 'active'
            ''', (session_id,))

            session = cursor.fetchone()

            if not session:
                return False, "Invalid or expired session"

            # Check if QR code has expired (from database, not from QR data)
            expiry_time = datetime.datetime.fromisoformat(session[7])  # qr_code_expires column
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
            conn.close()
            
            # Update gamification points
            update_gamification_points(student_id, 'attendance')
            
            return True, f"Successfully checked in as {status}"
            
        except Exception as e:
            print(f"Error processing QR check-in: {e}")
            return False, "Error processing check-in"

# Geofencing System
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

# Face Recognition System
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

# Gamification System
def update_gamification_points(student_id, action, bonus_multiplier=1.0):
    """Update student gamification points and achievements"""
    try:
        if get_setting('enable_gamification') != 'True':
            return
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current gamification data
        cursor.execute('''
        SELECT * FROM attendance_gamification WHERE student_id = ?
        ''', (student_id,))
        
        current_data = cursor.fetchone()
        
        if not current_data:
            # Create new record
            cursor.execute('''
            INSERT INTO attendance_gamification (student_id, last_attendance_date)
            VALUES (?, ?)
            ''', (student_id, datetime.date.today().isoformat()))
            current_data = (None, student_id, 0, 1, '[]', '[]', 0, 0, 
                          datetime.date.today().isoformat(), 0, None, None)
        
        points_per_attendance = int(get_setting('points_per_attendance') or 10)
        streak_bonus_multiplier = float(get_setting('streak_bonus_multiplier') or 1.5)
        
        # Calculate new points
        base_points = points_per_attendance if action == 'attendance' else 0
        
        # Check for streak
        last_date = datetime.datetime.strptime(current_data[8], '%Y-%m-%d').date() if current_data[8] else None
        today = datetime.date.today()
        
        if last_date:
            days_diff = (today - last_date).days
            if days_diff == 1:
                # Continue streak
                new_streak = current_data[6] + 1
            elif days_diff == 0:
                # Same day, no streak change
                new_streak = current_data[6]
            else:
                # Streak broken
                new_streak = 1
        else:
            new_streak = 1
        
        # Apply streak bonus
        if new_streak > 1:
            streak_bonus = int(base_points * (streak_bonus_multiplier - 1) * min(new_streak / 7, 2))
            total_points = base_points + streak_bonus
        else:
            total_points = base_points
        
        total_points = int(total_points * bonus_multiplier)
        
        # Update best streak
        new_best_streak = max(current_data[7], new_streak)
        
        # Calculate new level (every 1000 points = 1 level)
        new_total_points = current_data[2] + total_points
        new_level = (new_total_points // 1000) + 1
        
        # Check for new achievements
        badges = json.loads(current_data[4]) if current_data[4] else []
        achievements = json.loads(current_data[5]) if current_data[5] else []
        
        # Award badges
        if new_streak >= 7 and 'week_streak' not in badges:
            badges.append('week_streak')
            achievements.append({'badge': 'week_streak', 'date': today.isoformat(), 'description': '7-day attendance streak'})
        
        if new_streak >= 30 and 'month_streak' not in badges:
            badges.append('month_streak')
            achievements.append({'badge': 'month_streak', 'date': today.isoformat(), 'description': '30-day attendance streak'})
        
        if new_total_points >= 1000 and 'point_master' not in badges:
            badges.append('point_master')
            achievements.append({'badge': 'point_master', 'date': today.isoformat(), 'description': '1000 points earned'})
        
        # Update database
        cursor.execute('''
        UPDATE attendance_gamification 
        SET points = ?, level = ?, badges = ?, achievements = ?, streak_days = ?, 
            best_streak = ?, last_attendance_date = ?, total_rewards = ?, updated_at = ?
        WHERE student_id = ?
        ''', (new_total_points, new_level, json.dumps(badges), json.dumps(achievements),
              new_streak, new_best_streak, today.isoformat(), current_data[9] + total_points,
              datetime.datetime.now().isoformat(), student_id))
        
        conn.commit()
        conn.close()
        
        if total_points > 0:
            print(f"Student {student_id} earned {total_points} points! Current level: {new_level}")
        
    except Exception as e:
        print(f"Error updating gamification points: {e}")

# Predictive Analytics System
class AttendancePredictiveAnalytics:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = [
            'current_attendance_rate', 'consecutive_absences', 'days_since_last_attendance',
            'total_sessions', 'week_of_term', 'day_of_week', 'previous_module_performance'
        ]
    
    def prepare_training_data(self):
        """Prepare training data for the predictive model"""
        try:
            conn = get_connection()
            
            # Get historical attendance data
            query = '''
            SELECT 
                ar.student_id,
                ar.module_code,
                ar.date,
                ar.status,
                COUNT(*) OVER (PARTITION BY ar.student_id, ar.module_code) as total_sessions,
                AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) 
                    OVER (PARTITION BY ar.student_id, ar.module_code 
                          ORDER BY ar.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as running_attendance_rate
            FROM attendance_records ar
            ORDER BY ar.student_id, ar.module_code, ar.date
            '''
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                return None, None
            
            # Feature engineering
            df['date'] = pd.to_datetime(df['date'])
            df['day_of_week'] = df['date'].dt.dayofweek
            df['week_of_term'] = df['date'].dt.isocalendar().week % 52
            df['is_present'] = df['status'].isin(['Present', 'Late']).astype(int)
            
            # Calculate features for each student-module combination
            features = []
            targets = []
            
            for (student_id, module_code), group in df.groupby(['student_id', 'module_code']):
                group = group.sort_values('date')
                
                for i in range(5, len(group)):  # Need at least 5 sessions for prediction
                    current_data = group.iloc[:i]
                    future_window = group.iloc[i:i+5]  # Predict next 5 sessions
                    
                    # Current features
                    current_attendance_rate = current_data['is_present'].mean()
                    consecutive_absences = self._calculate_consecutive_absences(current_data['is_present'].values)
                    days_since_last = (current_data['date'].iloc[-1] - current_data[current_data['is_present'] == 1]['date'].iloc[-1] if (current_data['is_present'] == 1).any() else pd.Timedelta(days=999)).days
                    
                    feature_row = [
                        current_attendance_rate,
                        consecutive_absences,
                        min(days_since_last, 30),  # Cap at 30 days
                        len(current_data),
                        current_data['week_of_term'].iloc[-1],
                        current_data['day_of_week'].iloc[-1],
                        current_attendance_rate  # Simplified previous performance
                    ]
                    
                    # Target: attendance rate in next 5 sessions
                    future_attendance_rate = future_window['is_present'].mean()
                    
                    features.append(feature_row)
                    targets.append(future_attendance_rate)
            
            return np.array(features), np.array(targets)
            
        except Exception as e:
            print(f"Error preparing training data: {e}")
            return None, None
    
    def _calculate_consecutive_absences(self, attendance_array):
        """Calculate consecutive absences from the end"""
        consecutive = 0
        for status in reversed(attendance_array):
            if status == 0:  # Absent
                consecutive += 1
            else:
                break
        return consecutive
    
    def train_model(self):
        """Train the predictive model"""
        try:
            if get_setting('enable_predictive_analytics') != 'True':
                return False
            
            X, y = self.prepare_training_data()
            
            if X is None or len(X) < 50:  # Need minimum data
                print("Insufficient data for training predictive model")
                return False
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train model
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)
            
            # Convert regression to classification (risk levels)
            y_train_class = np.where(y_train < 0.7, 2, np.where(y_train < 0.8, 1, 0))  # 2=high risk, 1=medium, 0=low
            y_test_class = np.where(y_test < 0.7, 2, np.where(y_test < 0.8, 1, 0))
            
            self.model.fit(X_train_scaled, y_train_class)
            
            # Evaluate model
            accuracy = self.model.score(X_test_scaled, y_test_class)
            print(f"Model accuracy: {accuracy:.3f}")
            
            accuracy_threshold = float(get_setting('prediction_model_accuracy_threshold') or 0.75)
            
            if accuracy >= accuracy_threshold:
                print("Model training successful!")
                return True
            else:
                print(f"Model accuracy ({accuracy:.3f}) below threshold ({accuracy_threshold})")
                return False
                
        except Exception as e:
            print(f"Error training model: {e}")
            return False
    
    def predict_student_risk(self, student_id, module_code):
        """Predict attendance risk for a student"""
        try:
            if self.model is None:
                return None
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get recent attendance data
            cursor.execute('''
            SELECT date, status FROM attendance_records
            WHERE student_id = ? AND module_code = ?
            ORDER BY date DESC
            LIMIT 20
            ''', (student_id, module_code))
            
            records = cursor.fetchall()
            conn.close()
            
            if len(records) < 5:
                return None
            
            # Prepare features
            dates = [datetime.datetime.strptime(r[0], '%Y-%m-%d') for r in records]
            statuses = [1 if r[1] in ['Present', 'Late'] else 0 for r in records]
            
            current_attendance_rate = sum(statuses) / len(statuses)
            consecutive_absences = self._calculate_consecutive_absences(statuses[::-1])
            
            last_present_dates = [d for d, s in zip(dates, statuses) if s == 1]
            days_since_last = (datetime.datetime.now() - last_present_dates[0]).days if last_present_dates else 999
            
            current_date = datetime.datetime.now()
            
            features = np.array([[
                current_attendance_rate,
                consecutive_absences,
                min(days_since_last, 30),
                len(records),
                current_date.isocalendar().week % 52,
                current_date.weekday(),
                current_attendance_rate
            ]])
            
            # Scale and predict
            features_scaled = self.scaler.transform(features)
            risk_level = self.model.predict(features_scaled)[0]
            confidence = max(self.model.predict_proba(features_scaled)[0])
            
            risk_labels = ['Low Risk', 'Medium Risk', 'High Risk']
            
            # Store prediction
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO attendance_predictions 
            (student_id, module_code, prediction_date, predicted_attendance_rate, 
             risk_level, confidence_score, factors, model_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, module_code, datetime.date.today().isoformat(),
                  current_attendance_rate, risk_labels[risk_level], confidence,
                  json.dumps({'consecutive_absences': consecutive_absences, 'days_since_last': days_since_last}),
                  '1.0'))
            
            conn.commit()
            conn.close()
            
            return {
                'risk_level': risk_labels[risk_level],
                'confidence': confidence,
                'current_attendance_rate': current_attendance_rate,
                'factors': {
                    'consecutive_absences': consecutive_absences,
                    'days_since_last_attendance': days_since_last
                }
            }
            
        except Exception as e:
            print(f"Error predicting student risk: {e}")
            return None

# Enhanced Notification System
class EnhancedNotificationSystem:
    def __init__(self):
        self.notification_queue = []
        self.sms_api_key = get_setting('sms_api_key')
    
    def send_email_notification(self, recipient, subject, message, template_name=None):
        """Send email notification"""
        try:
            if EMAIL_SUPPORT and template_name:
                template_vars = {
                    'recipient': recipient,
                    'subject': subject,
                    'message': message,
                    'timestamp': datetime.datetime.now().isoformat()
                }
                return queue_template_email(template_name, recipient, template_vars)
            else:
                # Basic email sending
                print(f"EMAIL TO {recipient}: {subject}\n{message}")
                return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
    
    def send_sms_notification(self, phone_number, message):
        """Send SMS notification"""
        try:
            if get_setting('enable_sms_notifications') != 'True':
                return False
            
            if not self.sms_api_key:
                print(f"SMS to {phone_number}: {message}")
                return True
            
            # Integration with SMS service (example using a generic REST API)
            payload = {
                'to': phone_number,
                'message': message,
                'api_key': self.sms_api_key
            }
            
            # This would be replaced with actual SMS service API call
            print(f"SMS to {phone_number}: {message}")
            return True
            
        except Exception as e:
            print(f"Error sending SMS: {e}")
            return False
    
    def create_attendance_alert(self, student_id, module_code, alert_type, severity, message):
        """Create and queue attendance alert"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get student contact info
            cursor.execute('''
            SELECT email_address, phone_number FROM students WHERE student_id = ?
            ''', (student_id,))
            
            student_info = cursor.fetchone()
            
            if not student_info:
                return False
            
            email, phone = student_info
            
            alert_id = str(uuid.uuid4())
            
            # Insert alert
            cursor.execute('''
            INSERT INTO attendance_alerts 
            (alert_id, student_id, module_code, alert_type, severity, message, 
             recipient_email, recipient_phone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (alert_id, student_id, module_code, alert_type, severity, message, email, phone))
            
            conn.commit()
            conn.close()
            
            # Send notifications based on severity
            if severity in ['high', 'critical']:
                if email:
                    self.send_email_notification(email, f"Attendance Alert - {alert_type}", message, 'attendance_alert')
                if phone and get_setting('enable_sms_notifications') == 'True':
                    self.send_sms_notification(phone, f"Attendance Alert: {message}")
            
            return True
            
        except Exception as e:
            print(f"Error creating attendance alert: {e}")
            return False
    
    def send_parent_notifications(self, student_id, message):
        """Send notifications to parents"""
        try:
            if get_setting('enable_parent_portal') != 'True':
                return False
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get parent contact info (assuming it's stored in students table)
            cursor.execute('''
            SELECT parent_email, parent_phone FROM students WHERE student_id = ?
            ''', (student_id,))
            
            parent_info = cursor.fetchone()
            conn.close()
            
            if parent_info and parent_info[0]:  # Parent email exists
                self.send_email_notification(parent_info[0], "Student Attendance Update", message, 'parent_notification')
                
            if parent_info and parent_info[1]:  # Parent phone exists
                self.send_sms_notification(parent_info[1], f"Student attendance update: {message}")
            
            return True
            
        except Exception as e:
            print(f"Error sending parent notifications: {e}")
            return False

# Real-time Dashboard System
class AttendanceDashboard:
    def __init__(self):
        self.app = dash.Dash(__name__)
        self.setup_layout()
        self.setup_callbacks()
    
    def setup_layout(self):
        """Setup dashboard layout"""
        self.app.layout = html.Div([
            html.H1("Attendance Tracking Dashboard", style={'textAlign': 'center'}),
            
            # Controls
            html.Div([
                html.Div([
                    html.Label("Select Module:"),
                    dcc.Dropdown(
                        id='module-dropdown',
                        options=[],
                        value=None
                    )
                ], className="six columns"),
                
                html.Div([
                    html.Label("Select Date Range:"),
                    dcc.DatePickerRange(
                        id='date-picker-range',
                        start_date=datetime.date.today() - timedelta(days=30),
                        end_date=datetime.date.today()
                    )
                ], className="six columns"),
            ], className="row"),
            
            # Key Metrics
            html.Div([
                html.Div([
                    html.H3("Overall Attendance Rate"),
                    html.H2(id="overall-rate", children="--")
                ], className="three columns", style={'textAlign': 'center'}),
                
                html.Div([
                    html.H3("Students at Risk"),
                    html.H2(id="at-risk-count", children="--")
                ], className="three columns", style={'textAlign': 'center'}),
                
                html.Div([
                    html.H3("Today's Sessions"),
                    html.H2(id="todays-sessions", children="--")
                ], className="three columns", style={'textAlign': 'center'}),
                
                html.Div([
                    html.H3("Active Alerts"),
                    html.H2(id="active-alerts", children="--")
                ], className="three columns", style={'textAlign': 'center'}),
            ], className="row"),
            
            # Charts
            html.Div([
                html.Div([
                    dcc.Graph(id="attendance-trend-chart")
                ], className="six columns"),
                
                html.Div([
                    dcc.Graph(id="status-distribution-chart")
                ], className="six columns"),
            ], className="row"),
            
            html.Div([
                html.Div([
                    dcc.Graph(id="student-performance-chart")
                ], className="twelve columns"),
            ], className="row"),
            
            # Auto-refresh
            dcc.Interval(
                id='interval-component',
                interval=int(get_setting('dashboard_refresh_seconds') or 30) * 1000,
                n_intervals=0
            )
        ])
    
    def setup_callbacks(self):
        """Setup dashboard callbacks"""
        @self.app.callback(
            [Output('module-dropdown', 'options'),
             Output('overall-rate', 'children'),
             Output('at-risk-count', 'children'),
             Output('todays-sessions', 'children'),
             Output('active-alerts', 'children'),
             Output('attendance-trend-chart', 'figure'),
             Output('status-distribution-chart', 'figure'),
             Output('student-performance-chart', 'figure')],
            [Input('interval-component', 'n_intervals'),
             Input('module-dropdown', 'value'),
             Input('date-picker-range', 'start_date'),
             Input('date-picker-range', 'end_date')]
        )
        def update_dashboard(n_intervals, selected_module, start_date, end_date):
            # Get modules
            modules = get_modules()
            module_options = [{'label': f"{code} - {name}", 'value': code} for code, name in modules]
            
            # Get dashboard data
            dashboard_data = self.get_dashboard_data(selected_module, start_date, end_date)
            
            return (
                module_options,
                f"{dashboard_data['overall_rate']:.1f}%",
                str(dashboard_data['at_risk_count']),
                str(dashboard_data['todays_sessions']),
                str(dashboard_data['active_alerts']),
                dashboard_data['trend_chart'],
                dashboard_data['status_chart'],
                dashboard_data['performance_chart']
            )
    
    def get_dashboard_data(self, module_code=None, start_date=None, end_date=None):
        """Get data for dashboard"""
        try:
            conn = get_connection()
            
            # Base query conditions
            conditions = []
            params = []
            
            if module_code:
                conditions.append("ar.module_code = ?")
                params.append(module_code)
            
            if start_date:
                conditions.append("ar.date >= ?")
                params.append(start_date)
            
            if end_date:
                conditions.append("ar.date <= ?")
                params.append(end_date)
            
            where_clause = " AND " + " AND ".join(conditions) if conditions else ""
            
            # Overall attendance rate
            query = f'''
            SELECT 
                AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as rate
            FROM attendance_records ar
            WHERE 1=1 {where_clause}
            '''
            
            overall_rate = pd.read_sql_query(query, conn, params=params)['rate'].iloc[0] or 0
            
            # Students at risk
            risk_query = f'''
            SELECT COUNT(DISTINCT ar.student_id) as count
            FROM attendance_records ar
            WHERE 1=1 {where_clause}
            GROUP BY ar.student_id
            HAVING AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) < 0.8
            '''
            
            at_risk_df = pd.read_sql_query(risk_query, conn, params=params)
            at_risk_count = len(at_risk_df) if not at_risk_df.empty else 0
            
            # Today's sessions
            today = datetime.date.today().isoformat()
            sessions_query = '''
            SELECT COUNT(*) as count FROM attendance_sessions 
            WHERE date = ? AND status = 'active'
            '''
            
            todays_sessions = pd.read_sql_query(sessions_query, conn, params=[today])['count'].iloc[0] or 0
            
            # Active alerts
            alerts_query = '''
            SELECT COUNT(*) as count FROM attendance_alerts 
            WHERE status = 'pending'
            '''
            
            active_alerts = pd.read_sql_query(alerts_query, conn)['count'].iloc[0] or 0
            
            # Trend chart data
            trend_query = f'''
            SELECT 
                ar.date,
                AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as rate
            FROM attendance_records ar
            WHERE 1=1 {where_clause}
            GROUP BY ar.date
            ORDER BY ar.date
            '''
            
            trend_df = pd.read_sql_query(trend_query, conn, params=params)
            
            if not trend_df.empty:
                trend_chart = px.line(trend_df, x='date', y='rate', 
                                    title='Attendance Trend Over Time',
                                    labels={'rate': 'Attendance Rate (%)', 'date': 'Date'})
            else:
                trend_chart = px.line(title='No data available')
            
            # Status distribution
            status_query = f'''
            SELECT ar.status, COUNT(*) as count
            FROM attendance_records ar
            WHERE 1=1 {where_clause}
            GROUP BY ar.status
            '''
            
            status_df = pd.read_sql_query(status_query, conn, params=params)
            
            if not status_df.empty:
                status_chart = px.pie(status_df, values='count', names='status',
                                    title='Attendance Status Distribution')
            else:
                status_chart = px.pie(title='No data available')
            
            # Student performance chart
            performance_query = f'''
            SELECT 
                ar.student_id,
                s.first_name || ' ' || s.last_name as name,
                AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as rate
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            WHERE 1=1 {where_clause}
            GROUP BY ar.student_id, s.first_name, s.last_name
            ORDER BY rate ASC
            LIMIT 20
            '''
            
            performance_df = pd.read_sql_query(performance_query, conn, params=params)
            
            if not performance_df.empty:
                performance_chart = px.bar(performance_df, x='rate', y='name',
                                         orientation='h',
                                         title='Student Attendance Rates (Lowest 20)',
                                         labels={'rate': 'Attendance Rate (%)', 'name': 'Student'})
            else:
                performance_chart = px.bar(title='No data available')
            
            conn.close()
            
            return {
                'overall_rate': overall_rate,
                'at_risk_count': at_risk_count,
                'todays_sessions': todays_sessions,
                'active_alerts': active_alerts,
                'trend_chart': trend_chart,
                'status_chart': status_chart,
                'performance_chart': performance_chart
            }
            
        except Exception as e:
            print(f"Error getting dashboard data: {e}")
            return {
                'overall_rate': 0,
                'at_risk_count': 0,
                'todays_sessions': 0,
                'active_alerts': 0,
                'trend_chart': px.line(title='Error loading data'),
                'status_chart': px.pie(title='Error loading data'),
                'performance_chart': px.bar(title='Error loading data')
            }
    
    def run_dashboard(self, host='127.0.0.1', port=8050, debug=False):
        """Run the dashboard server"""
        print(f"Starting dashboard server at http://{host}:{port}")
        self.app.run_server(host=host, port=port, debug=debug)

# API System
class AttendanceAPI:
    def __init__(self):
        self.app = Flask(__name__)
        self.setup_routes()
        self.rate_limits = {}
    
    def check_rate_limit(self, client_ip):
        """Check API rate limit"""
        rate_limit = int(get_setting('api_rate_limit') or 1000)
        current_hour = datetime.datetime.now().hour
        
        if client_ip not in self.rate_limits:
            self.rate_limits[client_ip] = {'hour': current_hour, 'requests': 0}
        
        client_data = self.rate_limits[client_ip]
        
        if client_data['hour'] != current_hour:
            client_data['hour'] = current_hour
            client_data['requests'] = 0
        
        if client_data['requests'] >= rate_limit:
            return False
        
        client_data['requests'] += 1
        return True
    
    def setup_routes(self):
        """Setup API routes"""
        
        @self.app.before_request
        def before_request():
            if not self.check_rate_limit(request.remote_addr):
                return jsonify({'error': 'Rate limit exceeded'}), 429
        
        @self.app.route('/api/attendance/record', methods=['POST'])
        def record_attendance_api():
            try:
                data = request.json
                required_fields = ['student_id', 'module_code', 'date', 'status']
                
                if not all(field in data for field in required_fields):
                    return jsonify({'error': 'Missing required fields'}), 400
                
                # Record attendance
                attendance_data = [(data['student_id'], data['status'], data.get('notes', ''))]
                success = record_attendance(data['module_code'], data['date'], 
                                          attendance_data, data.get('recorded_by', 'API'))
                
                if success:
                    return jsonify({'success': True, 'message': 'Attendance recorded'})
                else:
                    return jsonify({'success': False, 'message': 'Failed to record attendance'}), 500
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/attendance/student/<student_id>', methods=['GET'])
        def get_student_attendance_api(student_id):
            try:
                module_code = request.args.get('module_code')
                stats = get_student_attendance(student_id, module_code)
                return jsonify(stats)
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/qr/generate', methods=['POST'])
        def generate_qr_api():
            try:
                data = request.json
                qr_system = QRAttendanceSystem()
                
                session_id, qr_filename = qr_system.generate_session_qr(
                    data['module_code'], data['date'], data['start_time'], 
                    data['end_time'], data.get('location')
                )
                
                if session_id:
                    return jsonify({
                        'success': True,
                        'session_id': session_id,
                        'qr_filename': qr_filename
                    })
                else:
                    return jsonify({'success': False}), 500
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/qr/checkin', methods=['POST'])
        def qr_checkin_api():
            try:
                data = request.json
                qr_system = QRAttendanceSystem()
                
                success, message = qr_system.process_qr_checkin(
                    data['qr_data'], data['student_id'], data.get('location_data')
                )
                
                return jsonify({'success': success, 'message': message})
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/predictions/<student_id>/<module_code>', methods=['GET'])
        def get_prediction_api(student_id, module_code):
            try:
                analytics = AttendancePredictiveAnalytics()
                prediction = analytics.predict_student_risk(student_id, module_code)
                
                if prediction:
                    return jsonify(prediction)
                else:
                    return jsonify({'error': 'No prediction available'}), 404
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
    
    def run_api(self, host='127.0.0.1', port=5000, debug=False):
        """Run the API server"""
        print(f"Starting API server at http://{host}:{port}")
        self.app.run(host=host, port=port, debug=debug)

# Enhanced Reporting System
def generate_executive_summary_report(date_from=None, date_to=None, output_path=None):
    """Generate executive summary report"""
    try:
        conn = get_connection()
        
        # Date range
        if not date_from:
            date_from = (datetime.date.today() - timedelta(days=30)).isoformat()
        if not date_to:
            date_to = datetime.date.today().isoformat()
        
        # Overall statistics
        overall_query = '''
        SELECT 
            COUNT(DISTINCT ar.student_id) as total_students,
            COUNT(DISTINCT ar.module_code) as total_modules,
            COUNT(*) as total_sessions,
            AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as overall_attendance_rate
        FROM attendance_records ar
        WHERE ar.date BETWEEN ? AND ?
        '''
        
        overall_stats = pd.read_sql_query(overall_query, conn, params=[date_from, date_to])
        
        # Attendance trends by week
        trends_query = '''
        SELECT 
            strftime('%Y-W%W', ar.date) as week,
            AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as rate
        FROM attendance_records ar
        WHERE ar.date BETWEEN ? AND ?
        GROUP BY strftime('%Y-W%W', ar.date)
        ORDER BY week
        '''
        
        trends_df = pd.read_sql_query(trends_query, conn, params=[date_from, date_to])
        
        # Top performing modules
        module_performance_query = '''
        SELECT
            ar.module_code,
            COALESCE(m.module_name, ar.module_code) as module_name,
            AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as attendance_rate,
            COUNT(*) as total_sessions
        FROM attendance_records ar
        LEFT JOIN modules m ON ar.module_code = m.module_code
        WHERE ar.date BETWEEN ? AND ?
        GROUP BY ar.module_code
        ORDER BY attendance_rate DESC
        LIMIT 10
        '''
        
        module_performance_df = pd.read_sql_query(module_performance_query, conn, params=[date_from, date_to])
        
        # At-risk students
        at_risk_query = '''
        SELECT 
            ar.student_id,
            s.first_name || ' ' || s.last_name as student_name,
            AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as attendance_rate,
            COUNT(*) as sessions_count
        FROM attendance_records ar
        JOIN students s ON ar.student_id = s.student_id
        WHERE ar.date BETWEEN ? AND ?
        GROUP BY ar.student_id, s.first_name, s.last_name
        HAVING AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) < 0.75
        ORDER BY attendance_rate ASC
        '''
        
        at_risk_df = pd.read_sql_query(at_risk_query, conn, params=[date_from, date_to])
        
        # Generate visualizations
        plt.style.use('seaborn-v0_8' if 'seaborn-v0_8' in plt.style.available else 'default')
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        # Attendance trends
        if not trends_df.empty:
            ax1.plot(trends_df['week'], trends_df['rate'], marker='o', linewidth=2)
            ax1.set_title('Weekly Attendance Trends', fontsize=14, fontweight='bold')
            ax1.set_xlabel('Week')
            ax1.set_ylabel('Attendance Rate (%)')
            ax1.grid(True, alpha=0.3)
            ax1.set_ylim(0, 100)
            
            # Add threshold lines
            threshold_warning = int(get_setting('attendance_threshold_warning') or 80)
            threshold_critical = int(get_setting('attendance_threshold_critical') or 70)
            ax1.axhline(y=threshold_warning, color='orange', linestyle='--', alpha=0.7, label='Warning Threshold')
            ax1.axhline(y=threshold_critical, color='red', linestyle='--', alpha=0.7, label='Critical Threshold')
            ax1.legend()
        
        # Module performance
        if not module_performance_df.empty and len(module_performance_df) > 0:
            top_modules = module_performance_df.head(8)
            bars = ax2.barh(range(len(top_modules)), top_modules['attendance_rate'], 
                           color=plt.cm.RdYlGn(top_modules['attendance_rate']/100))
            ax2.set_yticks(range(len(top_modules)))
            ax2.set_yticklabels(top_modules['module_code'], fontsize=10)
            ax2.set_title('Top Performing Modules', fontsize=14, fontweight='bold')
            ax2.set_xlabel('Attendance Rate (%)')
            
            # Add percentage labels
            for i, (bar, rate) in enumerate(zip(bars, top_modules['attendance_rate'])):
                ax2.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2, 
                        f'{rate:.1f}%', va='center', fontsize=9)
        
        # Status distribution
        status_query = '''
        SELECT status, COUNT(*) as count
        FROM attendance_records
        WHERE date BETWEEN ? AND ?
        GROUP BY status
        '''
        
        status_df = pd.read_sql_query(status_query, conn, params=[date_from, date_to])
        
        if not status_df.empty:
            status_colors = {'Present': 'green', 'Late': 'yellow', 'Excused': 'blue', 'Absent': 'red'}
            pie_colors = [status_colors.get(status, 'gray') for status in status_df['status']]
            
            wedges, texts, autotexts = ax3.pie(status_df['count'], labels=status_df['status'], 
                                              autopct='%1.1f%%', colors=pie_colors, startangle=90)
            ax3.set_title('Attendance Status Distribution', fontsize=14, fontweight='bold')
        
        # At-risk students count by attendance range
        if not at_risk_df.empty:
            bins = [0, 50, 60, 70, 75, 80, 100]
            labels = ['<50%', '50-60%', '60-70%', '70-75%', '75-80%', '80%+']
            at_risk_df['range'] = pd.cut(at_risk_df['attendance_rate'], bins=bins, labels=labels, right=False)
            range_counts = at_risk_df['range'].value_counts().reindex(labels, fill_value=0)
            
            ax4.bar(range(len(range_counts)), range_counts.values, 
                   color=['red', 'orange', 'yellow', 'lightgreen', 'green', 'darkgreen'])
            ax4.set_xticks(range(len(range_counts)))
            ax4.set_xticklabels(range_counts.index, rotation=45)
            ax4.set_title('Students by Attendance Range', fontsize=14, fontweight='bold')
            ax4.set_ylabel('Number of Students')
        
        plt.tight_layout()
        
        # Save visualization
        viz_filename = f"executive_summary_viz_{datetime.date.today().strftime('%Y%m%d')}.png"
        plt.savefig(viz_filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        # Generate PDF report
        if not output_path:
            output_path = f"executive_summary_{datetime.date.today().strftime('%Y%m%d')}.pdf"
        
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        
        # Title
        title = Paragraph("Executive Attendance Summary Report", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 20))
        
        # Report period
        period_text = f"Report Period: {date_from} to {date_to}"
        period_para = Paragraph(period_text, styles['Normal'])
        elements.append(period_para)
        elements.append(Spacer(1, 20))
        
        # Key metrics
        elements.append(Paragraph("Key Metrics", styles['Heading2']))
        
        if not overall_stats.empty:
            metrics_data = [
                ['Total Students', f"{overall_stats['total_students'].iloc[0]:,}"],
                ['Total Modules', f"{overall_stats['total_modules'].iloc[0]:,}"],
                ['Total Sessions', f"{overall_stats['total_sessions'].iloc[0]:,}"],
                ['Overall Attendance Rate', f"{overall_stats['overall_attendance_rate'].iloc[0]:.1f}%"],
            ]
            
            metrics_table = Table(metrics_data, colWidths=[200, 150])
            metrics_table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
            ]))
            
            elements.append(metrics_table)
            elements.append(Spacer(1, 20))
        
        # Top performing modules
        if not module_performance_df.empty:
            elements.append(Paragraph("Top Performing Modules", styles['Heading2']))
            
            module_data = [['Module Code', 'Module Name', 'Attendance Rate', 'Sessions']]
            for _, row in module_performance_df.head(10).iterrows():
                module_data.append([
                    row['module_code'],
                    row['module_name'][:40] + '...' if len(str(row['module_name'])) > 40 else str(row['module_name']),
                    f"{row['attendance_rate']:.1f}%",
                    str(row['total_sessions'])
                ])
            
            module_table = Table(module_data, colWidths=[80, 200, 80, 60])
            module_table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
            ]))
            
            elements.append(module_table)
            elements.append(Spacer(1, 20))
        
        # At-risk students summary
        if not at_risk_df.empty:
            elements.append(Paragraph("Students Requiring Attention", styles['Heading2']))
            
            risk_summary_text = f"Number of students with attendance below 75%: {len(at_risk_df)}"
            elements.append(Paragraph(risk_summary_text, styles['Normal']))
            elements.append(Spacer(1, 10))
            
            if len(at_risk_df) > 0:
                at_risk_data = [['Student ID', 'Student Name', 'Attendance Rate', 'Sessions']]
                for _, row in at_risk_df.head(15).iterrows():
                    at_risk_data.append([
                        row['student_id'],
                        row['student_name'][:30] + '...' if len(row['student_name']) > 30 else row['student_name'],
                        f"{row['attendance_rate']:.1f}%",
                        str(row['sessions_count'])
                    ])
                
                at_risk_table = Table(at_risk_data, colWidths=[80, 180, 80, 60])
                at_risk_table.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                ]))
                
                elements.append(at_risk_table)
                elements.append(Spacer(1, 20))
        
        # Add visualization image
        try:
            from reportlab.platypus import Image
            img = Image(viz_filename, width=500, height=375)
            elements.append(img)
        except Exception:
            pass  # Skip if image can't be added
        
        # Build PDF
        doc.build(elements)
        
        conn.close()
        print(f"Executive summary report generated: {output_path}")
        return True
        
    except Exception as e:
        print(f"Error generating executive summary: {e}")
        return False

# Backup and Recovery System
class BackupRecoverySystem:
    def __init__(self):
        # Use centralized backup directory
        try:
            from university_system.modules.shared.constants.paths import BACKUP_DIR
            self.backup_dir = BACKUP_DIR
        except ImportError:
            # Fallback to project root relative path
            self.backup_dir = Path(__file__).resolve().parents[4] / "backups"
        self.backup_dir.mkdir(exist_ok=True)

        # Get the correct database path
        try:
            from university_system.modules.shared.cli.cli_main import DB_PATH
            self.db_path = DB_PATH
        except ImportError:
            # Fallback to centralized path
            from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
            self.db_path = str(DEFAULT_DB_PATH)
    
    def create_backup(self, backup_type="full"):
        """Create database backup"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"attendance_backup_{backup_type}_{timestamp}.db"
            backup_path = self.backup_dir / backup_filename
            
            # Copy database file
            import shutil
            shutil.copy2(self.db_path, backup_path)
            
            # Create metadata file
            metadata = {
                "backup_type": backup_type,
                "timestamp": timestamp,
                "file_size": backup_path.stat().st_size,
                "created_by": "System"
            }
            
            metadata_path = self.backup_dir / f"metadata_{timestamp}.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            print(f"Backup created successfully: {backup_filename}")
            return str(backup_path)
            
        except Exception as e:
            print(f"Error creating backup: {e}")
            return None
    
    def restore_backup(self, backup_path):
        """Restore from backup"""
        try:
            if not Path(backup_path).exists():
                return False, "Backup file not found"
            
            # Create current backup before restore
            current_backup = self.create_backup("pre_restore")
            
            # Restore backup
            import shutil
            shutil.copy2(backup_path, self.db_path)
            
            return True, f"Backup restored successfully. Previous backup saved as: {current_backup}"
            
        except Exception as e:
            return False, f"Error restoring backup: {e}"
    
    def schedule_automatic_backups(self):
        """Schedule automatic backups"""
        if get_setting('auto_backup_enabled') == 'True':
            frequency_hours = int(get_setting('backup_frequency_hours') or 24)
            
            def backup_job():
                self.create_backup("scheduled")
                self.cleanup_old_backups()
            
            schedule.every(frequency_hours).hours.do(backup_job)
            
            # Run scheduler in background thread
            def run_scheduler():
                while True:
                    schedule.run_pending()
                    time.sleep(60)
            
            scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
            scheduler_thread.start()
            
            print(f"Automatic backups scheduled every {frequency_hours} hours")
    
    def cleanup_old_backups(self, keep_days=30):
        """Clean up old backup files"""
        try:
            cutoff_date = datetime.datetime.now() - timedelta(days=keep_days)
            
            for backup_file in self.backup_dir.glob("*.db"):
                if backup_file.stat().st_mtime < cutoff_date.timestamp():
                    backup_file.unlink()
                    
                    # Also remove corresponding metadata
                    metadata_file = backup_file.with_suffix('.json')
                    if metadata_file.exists():
                        metadata_file.unlink()
            
            print(f"Cleaned up backups older than {keep_days} days")
            
        except Exception as e:
            print(f"Error cleaning up backups: {e}")

# Advanced Settings Management
def get_enhanced_setting(setting_name, default_value=None, data_type='string'):
    """Get enhanced setting with type conversion"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT setting_value, data_type FROM attendance_settings 
        WHERE setting_name = ?
        ''', (setting_name,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            value, stored_type = result
            actual_type = stored_type or data_type
            
            # Type conversion
            if actual_type == 'boolean':
                return value.lower() in ('true', '1', 'yes', 'on')
            elif actual_type == 'integer':
                return int(value)
            elif actual_type == 'float':
                return float(value)
            else:
                return value
        
        return default_value
        
    except Exception as e:
        print(f"Error retrieving enhanced setting: {e}")
        return default_value

def set_enhanced_setting(setting_name, setting_value, description=None, category='general', data_type='string'):
    """Set enhanced setting with metadata"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR REPLACE INTO attendance_settings 
        (setting_name, setting_value, description, category, data_type, last_modified)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (setting_name, str(setting_value), description, category, data_type, 
              datetime.datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error setting enhanced setting: {e}")
        return False

# Audit Logging System
def log_audit_event(user_id, action, table_name, record_id, old_values=None, new_values=None):
    """Log audit event"""
    try:
        if get_enhanced_setting('enable_audit_log', True, 'boolean'):
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO attendance_audit_log 
            (user_id, action, table_name, record_id, old_values, new_values, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, action, table_name, str(record_id), 
                  json.dumps(old_values) if old_values else None,
                  json.dumps(new_values) if new_values else None,
                  '127.0.0.1'))  # Would get actual IP in web context
            
            conn.commit()
            conn.close()
    
    except Exception as e:
        print(f"Error logging audit event: {e}")

# Enhanced Menu System
def display_attendance_menu():
    """Display the enhanced attendance tracking menu"""
    # Initialize enhanced database
    init_enhanced_attendance_db()
    
    # Initialize systems
    qr_system = QRAttendanceSystem()
    geo_system = GeofencingSystem()
    face_system = FaceRecognitionSystem()
    notification_system = EnhancedNotificationSystem()
    analytics = AttendancePredictiveAnalytics()
    backup_system = BackupRecoverySystem()
    
    # Start automatic backups
    backup_system.schedule_automatic_backups()
    
    while True:
        print("\n" + "="*100)
        print(get_text('attendance.title', default='ENHANCED ATTENDANCE TRACKING SYSTEM'))
        print("="*100)

        print(f"\n📋 {get_text('attendance.sections.management', default='ATTENDANCE MANAGEMENT')}:")
        print(f"{'1.  ' + get_text('attendance.menu.traditional', default='Traditional'):<25} {'2.  ' + get_text('attendance.menu.qr_checkin', default='QR Code Check-in'):<25} {'3.  ' + get_text('attendance.menu.geofencing', default='Geofencing'):<25} {'4.  ' + get_text('attendance.menu.face_recognition', default='Face Recognition'):<25}")
        print(f"{'5.  ' + get_text('attendance.menu.view_records', default='View Records'):<25}")

        print(f"\n📊 {get_text('attendance.sections.analytics', default='ANALYTICS & REPORTING')}:")
        print(f"{'6.  ' + get_text('attendance.menu.student_report', default='Student Report'):<25} {'7.  ' + get_text('attendance.menu.module_report', default='Module Report'):<25} {'8.  ' + get_text('attendance.menu.executive_summary', default='Executive Summary'):<25} {'9.  ' + get_text('attendance.menu.predictive', default='Predictive Analytics'):<25}")
        print(f"{'10. ' + get_text('attendance.menu.dashboard', default='Real-time Dashboard'):<25}")

        print(f"\n🎮 {get_text('attendance.sections.gamification', default='GAMIFICATION & ENGAGEMENT')}:")
        print(f"{'11. ' + get_text('attendance.menu.gamification', default='Gamification Portal'):<25} {'12. ' + get_text('attendance.menu.achievements', default='Achievements'):<25} {'13. ' + get_text('attendance.menu.leaderboards', default='Leaderboards'):<25}")

        print(f"\n🔔 {get_text('attendance.sections.notifications', default='NOTIFICATIONS & ALERTS')}:")
        print(f"{'14. ' + get_text('attendance.menu.alerts', default='Alerts Manager'):<25} {'15. ' + get_text('attendance.menu.parent_notif', default='Parent Notifications'):<25} {'16. ' + get_text('attendance.menu.sms_email', default='SMS/Email Settings'):<25}")

        print(f"\n🔧 {get_text('attendance.sections.system', default='SYSTEM MANAGEMENT')}:")
        print(f"{'17. ' + get_text('attendance.menu.settings', default='Enhanced Settings'):<25} {'18. ' + get_text('attendance.menu.backup', default='Backup & Recovery'):<25} {'19. ' + get_text('attendance.menu.api', default='API Management'):<25} {'20. ' + get_text('attendance.menu.audit', default='Audit Logs'):<25}")

        print(f"\n📱 {get_text('attendance.sections.integrations', default='INTEGRATIONS')}:")
        print(f"{'21. ' + get_text('attendance.menu.lms', default='LMS Integration'):<25} {'22. ' + get_text('attendance.menu.calendar', default='Calendar Sync'):<25} {'23. ' + get_text('attendance.menu.import_export', default='Import/Export Data'):<25}")

        print(f"\n🌐 {get_text('attendance.sections.settings', default='SETTINGS')}:")
        print(f"24. {get_text('attendance.menu.language', default='Language')}")

        print(f"\n🚪 {get_text('attendance.sections.exit', default='EXIT')}:")
        print(f"25. {get_text('attendance.menu.return_main', default='Return to Main Menu')}")

        choice = input(f"\n{get_text('attendance.enter_choice', default='Enter your choice')} (1-25): ")
        
        if choice == '1':
            take_attendance()
            
        elif choice == '2':
            handle_qr_system(qr_system)
            
        elif choice == '3':
            handle_geofencing_system(geo_system)
            
        elif choice == '4':
            handle_face_recognition_system(face_system)
            
        elif choice == '5':
            handle_view_records()
            
        elif choice == '6':
            handle_student_reports()
            
        elif choice == '7':
            handle_module_reports()
            
        elif choice == '8':
            create_missing_tables()  # Add this line
            print("\nGenerating Executive Summary Report...")
            date_from = input("Enter start date (YYYY-MM-DD, leave empty for last 30 days): ")
            date_to = input("Enter end date (YYYY-MM-DD, leave empty for today): ")
            output_path = input("Enter output path (leave empty for default): ")
            
            if not date_from:
                date_from = None
            if not date_to:
                date_to = None
            if not output_path:
                output_path = None
                
            generate_executive_summary_report(date_from, date_to, output_path)
            
        elif choice == '9':
            handle_predictive_analytics(analytics)
            
        elif choice == '10':
            print("\nStarting Real-time Dashboard...")
            dashboard = AttendanceDashboard()
            print("Dashboard will open in your web browser at http://localhost:8050")
            try:
                dashboard.run_dashboard(debug=False)
            except KeyboardInterrupt:
                print("\nDashboard stopped.")
            
        elif choice == '11':
            handle_gamification_portal()
            
        elif choice == '12':
            handle_achievements()
            
        elif choice == '13':
            handle_leaderboards()
            
        elif choice == '14':
            handle_alerts_manager(notification_system)
            
        elif choice == '15':
            handle_parent_notifications(notification_system)
            
        elif choice == '16':
            handle_notification_settings()
            
        elif choice == '17':
            handle_enhanced_settings()
            
        elif choice == '18':
            handle_backup_recovery(backup_system)
            
        elif choice == '19':
            handle_api_management()
            
        elif choice == '20':
            handle_audit_logs()
            
        elif choice == '21':
            handle_lms_integration()
            
        elif choice == '22':
            handle_calendar_sync()
            
        elif choice == '23':
            handle_import_export()

        elif choice == '24':
            display_language_menu_option()

        elif choice == '25':
            print(get_text('attendance.returning', default='Returning to main menu...'))
            break

        else:
            print(get_text('attendance.invalid_choice', default='Invalid choice. Please try again.'))

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
            
def handle_gamification_portal():
    """Handle gamification portal"""
    print("\n🎮 STUDENT GAMIFICATION PORTAL")
    print("1. View Student Points & Level")
    print("2. View Student Achievements")
    print("3. Award Manual Points")
    print("4. View Attendance Streaks")
    
    choice = input("Enter your choice (1-4): ")
    
    if choice == '1':
        student_id = input("Enter student ID: ")
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT ag.*, s.first_name, s.last_name
            FROM attendance_gamification ag
            JOIN students s ON ag.student_id = s.student_id
            WHERE ag.student_id = ?
            ''', (student_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                (_, student_id, points, level, badges, achievements, streak_days, 
                 best_streak, last_attendance, total_rewards, created_at, updated_at, 
                 first_name, last_name) = result
                
                print(f"\n🎮 GAMIFICATION PROFILE: {first_name} {last_name}")
                print("=" * 50)
                print(f"Student ID: {student_id}")
                print(f"Current Points: {points:,}")
                print(f"Level: {level}")
                print(f"Current Streak: {streak_days} days")
                print(f"Best Streak: {best_streak} days")
                print(f"Total Rewards: {total_rewards:,}")
                print(f"Last Attendance: {last_attendance}")
                
                # Display badges
                badge_list = json.loads(badges) if badges else []
                if badge_list:
                    print(f"\n🏆 BADGES: {', '.join(badge_list)}")
                else:
                    print("\n🏆 BADGES: None yet")
                
                # Display recent achievements
                achievement_list = json.loads(achievements) if achievements else []
                if achievement_list:
                    print("\n🎯 RECENT ACHIEVEMENTS:")
                    for achievement in achievement_list[-5:]:  # Show last 5
                        print(f"  • {achievement.get('description', 'Achievement')} ({achievement.get('date', 'Unknown date')})")
                
                # Progress to next level
                points_to_next_level = (level * 1000) - points
                if points_to_next_level > 0:
                    print(f"\n📈 Points to next level: {points_to_next_level}")
            else:
                print("Student not found in gamification system.")
                
        except Exception as e:
            print(f"Error retrieving gamification data: {e}")
    
    elif choice == '2':
        student_id = input("Enter student ID: ")
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT achievements FROM attendance_gamification WHERE student_id = ?
            ''', (student_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                achievement_list = json.loads(result[0])
                
                print(f"\n🎯 ALL ACHIEVEMENTS FOR STUDENT {student_id}")
                print("=" * 50)
                
                if achievement_list:
                    for i, achievement in enumerate(achievement_list, 1):
                        print(f"{i}. {achievement.get('badge', 'Unknown')}")
                        print(f"   Description: {achievement.get('description', 'No description')}")
                        print(f"   Earned: {achievement.get('date', 'Unknown date')}")
                        print()
                else:
                    print("No achievements yet.")
            else:
                print("Student not found or has no achievements.")
                
        except Exception as e:
            print(f"Error retrieving achievements: {e}")
    
    elif choice == '3':
        student_id = input("Enter student ID: ")
        
        try:
            points = int(input("Enter points to award: "))
            reason = input("Enter reason for points: ")
            
            update_gamification_points(student_id, 'manual', bonus_multiplier=1.0)
            
            # Manually add the specified points
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            UPDATE attendance_gamification 
            SET points = points + ?, total_rewards = total_rewards + ?, updated_at = ?
            WHERE student_id = ?
            ''', (points, points, datetime.datetime.now().isoformat(), student_id))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Awarded {points} points to student {student_id} for: {reason}")
            
        except ValueError:
            print("Invalid points value.")
        except Exception as e:
            print(f"Error awarding points: {e}")
    
    elif choice == '4':
        print("\n📅 ATTENDANCE STREAKS LEADERBOARD")
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT ag.student_id, s.first_name, s.last_name, ag.streak_days, ag.best_streak
            FROM attendance_gamification ag
            JOIN students s ON ag.student_id = s.student_id
            ORDER BY ag.streak_days DESC, ag.best_streak DESC
            LIMIT 20
            ''')
            
            results = cursor.fetchall()
            conn.close()
            
            if results:
                print(f"{'Rank':<5} {'Student ID':<12} {'Name':<25} {'Current':<10} {'Best':<10}")
                print("-" * 70)
                
                for rank, (student_id, first_name, last_name, current_streak, best_streak) in enumerate(results, 1):
                    name = f"{first_name} {last_name}"
                    print(f"{rank:<5} {student_id:<12} {name:<25} {current_streak:<10} {best_streak:<10}")
            else:
                print("No streak data available.")
                
        except Exception as e:
            print(f"Error retrieving streak data: {e}")

def handle_leaderboards():
    """Handle leaderboards"""
    print("\n🏆 ATTENDANCE LEADERBOARDS")
    print("1. Points Leaderboard")
    print("2. Attendance Rate Leaderboard")
    print("3. Module-specific Leaderboard")
    print("4. Weekly Performance")
    
    choice = input("Enter your choice (1-4): ")
    
    if choice == '1':
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT ag.student_id, s.first_name, s.last_name, ag.points, ag.level
            FROM attendance_gamification ag
            JOIN students s ON ag.student_id = s.student_id
            ORDER BY ag.points DESC
            LIMIT 20
            ''')
            
            results = cursor.fetchall()
            conn.close()
            
            if results:
                print("\n🏆 TOP 20 POINTS LEADERBOARD")
                print("=" * 60)
                print(f"{'Rank':<5} {'Student ID':<12} {'Name':<25} {'Points':<10} {'Level'}")
                print("-" * 60)
                
                for rank, (student_id, first_name, last_name, points, level) in enumerate(results, 1):
                    name = f"{first_name} {last_name}"
                    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else ""
                    print(f"{rank:<5} {student_id:<12} {name:<25} {points:<10,} {level} {medal}")
            else:
                print("No gamification data available.")
                
        except Exception as e:
            print(f"Error retrieving leaderboard: {e}")
    
    elif choice == '2':
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT 
                ar.student_id,
                s.first_name,
                s.last_name,
                AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as attendance_rate,
                COUNT(*) as total_sessions
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            WHERE ar.date >= date('now', '-30 days')
            GROUP BY ar.student_id, s.first_name, s.last_name
            HAVING COUNT(*) >= 5
            ORDER BY attendance_rate DESC
            LIMIT 20
            ''')
            
            results = cursor.fetchall()
            conn.close()
            
            if results:
                print("\n📊 TOP 20 ATTENDANCE RATE LEADERBOARD (Last 30 Days)")
                print("=" * 70)
                print(f"{'Rank':<5} {'Student ID':<12} {'Name':<25} {'Rate':<10} {'Sessions'}")
                print("-" * 70)
                
                for rank, (student_id, first_name, last_name, rate, sessions) in enumerate(results, 1):
                    name = f"{first_name} {last_name}"
                    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else ""
                    print(f"{rank:<5} {student_id:<12} {name:<25} {rate:<10.1f}% {sessions} {medal}")
            else:
                print("No attendance data available.")
                
        except Exception as e:
            print(f"Error retrieving attendance leaderboard: {e}")

def handle_predictive_analytics(analytics):
    """Handle predictive analytics"""
    print("\n🔮 PREDICTIVE ANALYTICS")
    print("1. Train Prediction Model")
    print("2. Predict Student Risk")
    print("3. Batch Risk Assessment")
    print("4. View Prediction History")
    
    choice = input("Enter your choice (1-4): ")
    
    if choice == '1':
        print("Training predictive model...")
        success = analytics.train_model()
        
        if success:
            print("✅ Model trained successfully!")
        else:
            print("❌ Model training failed or insufficient data.")
    
    elif choice == '2':
        student_id = input("Enter student ID: ")
        
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
                
                prediction = analytics.predict_student_risk(student_id, module_code)
                
                if prediction:
                    print(f"\n🔮 PREDICTION FOR STUDENT {student_id} IN {module_code}")
                    print("=" * 50)
                    print(f"Risk Level: {prediction['risk_level']}")
                    print(f"Confidence: {prediction['confidence']:.3f}")
                    print(f"Current Attendance Rate: {prediction['current_attendance_rate']:.1f}%")
                    print(f"Consecutive Absences: {prediction['factors']['consecutive_absences']}")
                    print(f"Days Since Last Attendance: {prediction['factors']['days_since_last_attendance']}")
                    
                    if prediction['risk_level'] in ['Medium Risk', 'High Risk']:
                        print("\n⚠️  RECOMMENDED ACTIONS:")
                        if prediction['factors']['consecutive_absences'] >= 3:
                            print("• Contact student immediately about consecutive absences")
                        if prediction['factors']['days_since_last_attendance'] > 7:
                            print("• Schedule academic advisor meeting")
                        print("• Send attendance warning notification")
                        print("• Consider academic support referral")
                else:
                    print("Unable to generate prediction. Insufficient data or model not trained.")
        except (ValueError, IndexError):
            print("Invalid selection.")
    
    elif choice == '3':
        print("Performing batch risk assessment...")
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get all active student-module combinations
            cursor.execute('''
            SELECT DISTINCT ar.student_id, ar.module_code, s.first_name, s.last_name
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            WHERE ar.date >= date('now', '-60 days')
            ''')
            
            combinations = cursor.fetchall()
            conn.close()
            
            high_risk_students = []
            medium_risk_students = []
            
            for student_id, module_code, first_name, last_name in combinations:
                prediction = analytics.predict_student_risk(student_id, module_code)
                
                if prediction:
                    if prediction['risk_level'] == 'High Risk':
                        high_risk_students.append((student_id, module_code, first_name, last_name, prediction))
                    elif prediction['risk_level'] == 'Medium Risk':
                        medium_risk_students.append((student_id, module_code, first_name, last_name, prediction))
            
            print(f"\n🚨 BATCH RISK ASSESSMENT RESULTS")
            print("=" * 60)
            
            if high_risk_students:
                print(f"\n⚠️  HIGH RISK STUDENTS ({len(high_risk_students)}):")
                print(f"{'Student ID':<12} {'Name':<25} {'Module':<12} {'Confidence'}")
                print("-" * 60)
                for student_id, module_code, first_name, last_name, pred in high_risk_students:
                    name = f"{first_name} {last_name}"
                    print(f"{student_id:<12} {name:<25} {module_code:<12} {pred['confidence']:.3f}")
            
            if medium_risk_students:
                print(f"\n⚠️  MEDIUM RISK STUDENTS ({len(medium_risk_students)}):")
                print(f"{'Student ID':<12} {'Name':<25} {'Module':<12} {'Confidence'}")
                print("-" * 60)
                for student_id, module_code, first_name, last_name, pred in medium_risk_students:
                    name = f"{first_name} {last_name}"
                    print(f"{student_id:<12} {name:<25} {module_code:<12} {pred['confidence']:.3f}")
            
            if not high_risk_students and not medium_risk_students:
                print("No at-risk students identified.")
                
        except Exception as e:
            print(f"Error performing batch assessment: {e}")

def handle_enhanced_settings():
    """Handle enhanced settings management"""
    print("\n⚙️  ENHANCED SETTINGS MANAGEMENT")
    print("1. View All Settings")
    print("2. Update Setting")
    print("3. Feature Toggles")
    print("4. Reset to Defaults")
    
    choice = input("Enter your choice (1-4): ")
    
    if choice == '1':
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT setting_name, setting_value, description, category, data_type
            FROM attendance_settings
            ORDER BY category, setting_name
            ''')
            
            settings = cursor.fetchall()
            conn.close()
            
            if settings:
                current_category = None
                for setting_name, setting_value, description, category, data_type in settings:
                    if category != current_category:
                        print(f"\n📂 {category.upper()} SETTINGS:")
                        print("-" * 50)
                        current_category = category
                    
                    print(f"{setting_name}: {setting_value} ({data_type})")
                    if description:
                        print(f"  {description}")
                    print()
            else:
                print("No settings found.")
                
        except Exception as e:
            print(f"Error retrieving settings: {e}")
    
    elif choice == '2':
        setting_name = input("Enter setting name: ")
        current_value = get_enhanced_setting(setting_name)
        
        if current_value is not None:
            print(f"Current value: {current_value}")
            new_value = input("Enter new value: ")
            
            if set_enhanced_setting(setting_name, new_value):
                print("✅ Setting updated successfully!")
            else:
                print("❌ Failed to update setting.")
        else:
            print("Setting not found.")
    
    elif choice == '3':
        print("\n🔧 FEATURE TOGGLES")
        
        features = [
            ('enable_qr_checkin', 'QR Code Check-in'),
            ('enable_geofencing', 'Geofencing'),
            ('enable_face_recognition', 'Face Recognition'),
            ('enable_gamification', 'Gamification'),
            ('enable_sms_notifications', 'SMS Notifications'),
            ('enable_parent_portal', 'Parent Portal'),
            ('enable_predictive_analytics', 'Predictive Analytics'),
            ('enable_audit_log', 'Audit Logging'),
            ('auto_backup_enabled', 'Automatic Backups')
        ]
        
        for setting_name, feature_name in features:
            current_value = get_enhanced_setting(setting_name, False, 'boolean')
            status = "✅ ON" if current_value else "❌ OFF"
            print(f"{feature_name}: {status}")
        
        print("\nEnter feature name to toggle (or 'back' to return):")
        feature_input = input().strip()
        
        if feature_input != 'back':
            for setting_name, feature_name in features:
                if feature_name.lower() == feature_input.lower():
                    current_value = get_enhanced_setting(setting_name, False, 'boolean')
                    new_value = not current_value
                    
                    if set_enhanced_setting(setting_name, new_value, data_type='boolean'):
                        status = "enabled" if new_value else "disabled"
                        print(f"✅ {feature_name} {status}!")
                    else:
                        print("❌ Failed to update feature setting.")
                    break
            else:
                print("Feature not found.")

def handle_backup_recovery(backup_system):
    """Handle backup and recovery operations"""
    print("\n💾 BACKUP & RECOVERY SYSTEM")
    print("1. Create Manual Backup")
    print("2. List Available Backups")
    print("3. Restore from Backup")
    print("4. Backup Settings")
    print("5. Cleanup Old Backups")
    
    choice = input("Enter your choice (1-5): ")
    
    if choice == '1':
        backup_type = input("Enter backup type (full/partial): ") or "manual"
        backup_path = backup_system.create_backup(backup_type)
        
        if backup_path:
            print(f"✅ Backup created: {backup_path}")
        else:
            print("❌ Backup creation failed.")
    
    elif choice == '2':
        # Use centralized backup directory
        try:
            from university_system.modules.shared.constants.paths import BACKUP_DIR
            backup_dir = BACKUP_DIR
        except ImportError:
            # Fallback to project root relative path
            backup_dir = Path(__file__).resolve().parents[4] / "backups"
        
        if backup_dir.exists():
            backups = sorted(backup_dir.glob("*.db"), key=lambda x: x.stat().st_mtime, reverse=True)
            
            if backups:
                print("\n📁 AVAILABLE BACKUPS:")
                print(f"{'Filename':<40} {'Size':<10} {'Date'}")
                print("-" * 70)
                
                for backup_file in backups[:20]:  # Show last 20 backups
                    size = backup_file.stat().st_size
                    size_mb = size / (1024 * 1024)
                    date = datetime.datetime.fromtimestamp(backup_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                    
                    print(f"{backup_file.name:<40} {size_mb:<10.1f}MB {date}")
            else:
                print("No backups found.")
        else:
            print("Backup directory not found.")
    
    elif choice == '3':
        backup_path = input("Enter backup file path: ")
        
        confirm = input(f"⚠️  This will restore from '{backup_path}' and overwrite current data. Continue? (yes/no): ")
        
        if confirm.lower() == 'yes':
            success, message = backup_system.restore_backup(backup_path)
            
            if success:
                print(f"✅ {message}")
            else:
                print(f"❌ {message}")
        else:
            print("Restore cancelled.")
    
    elif choice == '4':
        print("\n💾 BACKUP SETTINGS:")
        
        auto_backup = get_enhanced_setting('auto_backup_enabled', True, 'boolean')
        frequency = get_enhanced_setting('backup_frequency_hours', 24, 'integer')
        
        print(f"Automatic Backups: {'Enabled' if auto_backup else 'Disabled'}")
        print(f"Backup Frequency: Every {frequency} hours")
        
        print("\n1. Toggle Automatic Backups")
        print("2. Change Backup Frequency")
        
        setting_choice = input("Enter choice (1-2): ")
        
        if setting_choice == '1':
            new_value = not auto_backup
            if set_enhanced_setting('auto_backup_enabled', new_value, data_type='boolean'):
                status = "enabled" if new_value else "disabled"
                print(f"✅ Automatic backups {status}!")
            else:
                print("❌ Failed to update setting.")
        
        elif setting_choice == '2':
            try:
                new_frequency = int(input("Enter new frequency in hours: "))
                if set_enhanced_setting('backup_frequency_hours', new_frequency, data_type='integer'):
                    print(f"✅ Backup frequency set to {new_frequency} hours!")
                else:
                    print("❌ Failed to update setting.")
            except ValueError:
                print("Invalid frequency value.")
    
    elif choice == '5':
        try:
            keep_days = int(input("Enter number of days to keep backups (default 30): ") or 30)
            backup_system.cleanup_old_backups(keep_days)
            print(f"✅ Cleaned up backups older than {keep_days} days.")
        except ValueError:
            print("Invalid number of days.")

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
            print(f"\n🔍 MODULE COMPARISON")
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

def handle_achievements():
    """Handle achievement management"""
    print("\n🎯 ACHIEVEMENT MANAGEMENT")
    print("1. View All Achievements")
    print("2. Student Achievement History")
    print("3. Award Custom Achievement")
    print("4. Achievement Statistics")
    
    choice = input("Enter your choice (1-4): ")
    
    if choice == '1':
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get all unique achievements
            cursor.execute('''
            SELECT achievements FROM attendance_gamification 
            WHERE achievements IS NOT NULL AND achievements != '[]'
            ''')
            
            all_achievements = []
            for result in cursor.fetchall():
                if result[0]:
                    achievements = json.loads(result[0])
                    all_achievements.extend(achievements)
            
            conn.close()
            
            # Count achievements
            achievement_counts = Counter(achievement['badge'] for achievement in all_achievements)
            
            if achievement_counts:
                print("\n🏆 ALL ACHIEVEMENTS")
                print("=" * 50)
                print(f"{'Achievement':<30} {'Earned Count'}")
                print("-" * 50)
                
                for badge, count in achievement_counts.most_common():
                    print(f"{badge:<30} {count}")
            else:
                print("No achievements found.")
                
        except Exception as e:
            print(f"Error retrieving achievements: {e}")
    
    elif choice == '2':
        student_id = input("Enter student ID: ")
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT achievements, s.first_name, s.last_name
            FROM attendance_gamification ag
            JOIN students s ON ag.student_id = s.student_id
            WHERE ag.student_id = ?
            ''', (student_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                achievements, first_name, last_name = result
                achievement_list = json.loads(achievements)
                
                print(f"\n🎯 ACHIEVEMENT HISTORY: {first_name} {last_name}")
                print("=" * 60)
                
                if achievement_list:
                    for i, achievement in enumerate(achievement_list, 1):
                        print(f"{i}. {achievement.get('badge', 'Unknown Badge')}")
                        print(f"   Description: {achievement.get('description', 'No description')}")
                        print(f"   Earned: {achievement.get('date', 'Unknown date')}")
                        print()
                else:
                    print("No achievements yet.")
            else:
                print("Student not found or has no achievements.")
                
        except Exception as e:
            print(f"Error retrieving student achievements: {e}")

def handle_alerts_manager(notification_system):
    """Handle attendance alerts management"""
    print("\n🔔 ATTENDANCE ALERTS MANAGER")
    print("1. View Pending Alerts")
    print("2. Create Custom Alert")
    print("3. Acknowledge Alerts")
    print("4. Alert Statistics")
    
    choice = input("Enter your choice (1-4): ")
    
    if choice == '1':
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT aa.alert_id, aa.student_id, s.first_name, s.last_name, 
                   aa.module_code, aa.alert_type, aa.severity, aa.message, aa.created_at
            FROM attendance_alerts aa
            JOIN students s ON aa.student_id = s.student_id
            WHERE aa.status = 'pending'
            ORDER BY aa.created_at DESC
            LIMIT 20
            ''')
            
            alerts = cursor.fetchall()
            conn.close()
            
            if alerts:
                print("\n🚨 PENDING ALERTS")
                print("=" * 100)
                print(f"{'Alert ID':<8} {'Student':<20} {'Module':<10} {'Type':<15} {'Severity':<10} {'Created'}")
                print("-" * 100)
                
                for alert in alerts:
                    alert_id, student_id, first_name, last_name, module_code, alert_type, severity, message, created_at = alert
                    student_name = f"{first_name} {last_name} ({student_id})"
                    created_date = created_at.split('T')[0] if 'T' in created_at else created_at[:10]
                    
                    print(f"{alert_id[:8]:<8} {student_name:<20} {module_code:<10} {alert_type:<15} {severity:<10} {created_date}")
                
                # Show alert details
                alert_id = input("\nEnter alert ID to view details (or press Enter to return): ")
                if alert_id:
                    for alert in alerts:
                        if alert[0].startswith(alert_id):
                            print(f"\n📋 ALERT DETAILS:")
                            print(f"Student: {alert[2]} {alert[3]} ({alert[1]})")
                            print(f"Module: {alert[4]}")
                            print(f"Type: {alert[5]}")
                            print(f"Severity: {alert[6]}")
                            print(f"Message: {alert[7]}")
                            print(f"Created: {alert[8]}")
                            break
                    else:
                        print("Alert not found.")
            else:
                print("No pending alerts.")
                
        except Exception as e:
            print(f"Error retrieving alerts: {e}")
    
    elif choice == '2':
        student_id = input("Enter student ID: ")
        
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
                
                alert_type = input("Enter alert type (attendance_warning/custom): ") or "custom"
                severity = input("Enter severity (low/medium/high/critical): ") or "medium"
                message = input("Enter alert message: ")
                
                success = notification_system.create_attendance_alert(
                    student_id, module_code, alert_type, severity, message
                )
                
                if success:
                    print("✅ Alert created successfully!")
                else:
                    print("❌ Failed to create alert.")
        except (ValueError, IndexError):
            print("Invalid selection.")

def handle_parent_notifications(notification_system):
    """Handle parent notification system"""
    print("\n👨‍👩‍👧‍👦 PARENT NOTIFICATION SYSTEM")
    
    if get_enhanced_setting('enable_parent_portal', False, 'boolean'):
        print("1. Send Attendance Summary to Parents")
        print("2. Configure Parent Contacts")
        print("3. View Parent Notification History")
        
        choice = input("Enter your choice (1-3): ")
        
        if choice == '1':
            student_id = input("Enter student ID (or 'all' for all students): ")
            
            if student_id.lower() == 'all':
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute('SELECT student_id FROM students WHERE parent_email IS NOT NULL')
                    students = cursor.fetchall()
                    conn.close()
                    
                    success_count = 0
                    for student_id, in students:
                        # Generate attendance summary message
                        stats = get_student_attendance(student_id)
                        
                        if stats:
                            overall_rate = sum(data['percentage'] for data in stats.values()) / len(stats)
                            message = f"Weekly attendance summary for your child (Student ID: {student_id}). "
                            message += f"Overall attendance rate: {overall_rate:.1f}%. "
                            
                            if overall_rate < 80:
                                message += "Please ensure regular attendance for academic success."
                            else:
                                message += "Great attendance! Keep up the good work."
                            
                            if notification_system.send_parent_notifications(student_id, message):
                                success_count += 1
                    
                    print(f"✅ Sent notifications to {success_count} parents.")
                    
                except Exception as e:
                    print(f"Error sending batch notifications: {e}")
            else:
                # Single student
                stats = get_student_attendance(student_id)
                
                if stats:
                    overall_rate = sum(data['percentage'] for data in stats.values()) / len(stats)
                    message = f"Attendance update for your child (Student ID: {student_id}). "
                    message += f"Current attendance rate: {overall_rate:.1f}%. "
                    
                    if overall_rate < 80:
                        message += "Please ensure regular attendance for academic success."
                    else:
                        message += "Great attendance! Keep up the good work."
                    
                    if notification_system.send_parent_notifications(student_id, message):
                        print("✅ Parent notification sent successfully!")
                    else:
                        print("❌ Failed to send parent notification.")
                else:
                    print("No attendance data found for student.")
    else:
        print("❌ Parent portal is disabled. Enable it in Enhanced Settings to use this feature.")

def handle_notification_settings():
    """Handle notification settings"""
    print("\n📨 NOTIFICATION SETTINGS")
    print("1. Email Settings")
    print("2. SMS Settings")
    print("3. Alert Thresholds")
    print("4. Test Notifications")
    
    choice = input("Enter your choice (1-4): ")
    
    if choice == '1':
        print("\n📧 EMAIL SETTINGS")
        
        auto_email = get_enhanced_setting('auto_email_warnings', False, 'boolean')
        print(f"Automatic Email Warnings: {'Enabled' if auto_email else 'Disabled'}")
        
        toggle = input("Toggle automatic email warnings? (y/n): ")
        if toggle.lower() == 'y':
            new_value = not auto_email
            if set_enhanced_setting('auto_email_warnings', new_value, data_type='boolean'):
                status = "enabled" if new_value else "disabled"
                print(f"✅ Automatic email warnings {status}!")
    
    elif choice == '2':
        print("\n📱 SMS SETTINGS")
        
        sms_enabled = get_enhanced_setting('enable_sms_notifications', False, 'boolean')
        sms_api_key = get_enhanced_setting('sms_api_key', '', 'string')
        
        print(f"SMS Notifications: {'Enabled' if sms_enabled else 'Disabled'}")
        print(f"API Key: {'Configured' if sms_api_key else 'Not configured'}")
        
        print("\n1. Toggle SMS notifications")
        print("2. Configure SMS API key")
        
        sms_choice = input("Enter choice (1-2): ")
        
        if sms_choice == '1':
            new_value = not sms_enabled
            if set_enhanced_setting('enable_sms_notifications', new_value, data_type='boolean'):
                status = "enabled" if new_value else "disabled"
                print(f"✅ SMS notifications {status}!")
        
        elif sms_choice == '2':
            new_api_key = input("Enter SMS API key: ")
            if set_enhanced_setting('sms_api_key', new_api_key, data_type='string'):
                print("✅ SMS API key updated!")
    
    elif choice == '3':
        print("\n⚠️  ALERT THRESHOLDS")
        
        warning_threshold = get_enhanced_setting('attendance_threshold_warning', 80, 'integer')
        critical_threshold = get_enhanced_setting('attendance_threshold_critical', 70, 'integer')
        consecutive_warning = get_enhanced_setting('consecutive_absences_warning', 2, 'integer')
        consecutive_critical = get_enhanced_setting('consecutive_absences_critical', 3, 'integer')
        
        print(f"Attendance Warning Threshold: {warning_threshold}%")
        print(f"Attendance Critical Threshold: {critical_threshold}%")
        print(f"Consecutive Absences Warning: {consecutive_warning}")
        print(f"Consecutive Absences Critical: {consecutive_critical}")
        
        print("\n1. Update attendance thresholds")
        print("2. Update consecutive absence thresholds")
        
        threshold_choice = input("Enter choice (1-2): ")
        
        if threshold_choice == '1':
            try:
                new_warning = int(input(f"Enter new warning threshold (current: {warning_threshold}%): "))
                new_critical = int(input(f"Enter new critical threshold (current: {critical_threshold}%): "))
                
                if 0 <= new_critical <= new_warning <= 100:
                    if set_enhanced_setting('attendance_threshold_warning', new_warning, data_type='integer'):
                        if set_enhanced_setting('attendance_threshold_critical', new_critical, data_type='integer'):
                            print("✅ Attendance thresholds updated successfully!")
                        else:
                            print("❌ Failed to update critical threshold.")
                    else:
                        print("❌ Failed to update warning threshold.")
                else:
                    print("❌ Invalid thresholds. Critical must be ≤ Warning, and both must be 0-100%.")
            except ValueError:
                print("❌ Invalid threshold values.")
        
        elif threshold_choice == '2':
            try:
                new_warning = int(input(f"Enter new consecutive absences warning (current: {consecutive_warning}): "))
                new_critical = int(input(f"Enter new consecutive absences critical (current: {consecutive_critical}): "))
                
                if 0 <= new_warning <= new_critical <= 10:
                    if set_enhanced_setting('consecutive_absences_warning', new_warning, data_type='integer'):
                        if set_enhanced_setting('consecutive_absences_critical', new_critical, data_type='integer'):
                            print("✅ Consecutive absence thresholds updated successfully!")
                        else:
                            print("❌ Failed to update critical threshold.")
                    else:
                        print("❌ Failed to update warning threshold.")
                else:
                    print("❌ Invalid thresholds. Warning must be ≤ Critical, and both must be 0-10.")
            except ValueError:
                print("❌ Invalid threshold values.")
    
    elif choice == '4':
        print("\n🧪 TEST NOTIFICATIONS")
        
        test_email = input("Enter test email address: ")
        if test_email:
            notification_system = EnhancedNotificationSystem()
            
            success = notification_system.send_email_notification(
                test_email, 
                "Test Notification", 
                "This is a test notification from the Enhanced Attendance System."
            )
            
            if success:
                print("✅ Test email sent successfully!")
            else:
                print("❌ Failed to send test email.")
        
        test_phone = input("Enter test phone number (optional): ")
        if test_phone:
            if get_enhanced_setting('enable_sms_notifications', False, 'boolean'):
                success = notification_system.send_sms_notification(
                    test_phone,
                    "Test SMS from Enhanced Attendance System."
                )
                
                if success:
                    print("✅ Test SMS sent successfully!")
                else:
                    print("❌ Failed to send test SMS.")
            else:
                print("❌ SMS notifications are disabled.")

def handle_geofencing_system(geo_system):
    """Handle geofencing system operations"""
    if not GEOFENCING_SUPPORT:
        print("❌ Geofencing not supported. Please install geopy package.")
        return
    
    print("\n🌍 GEOFENCING ATTENDANCE SYSTEM")
    print("1. Create Geofenced Session")
    print("2. Check Location Attendance")
    print("3. View Geofenced Locations")
    
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
                
                location_name = input("Enter location name: ")
                latitude = float(input("Enter latitude: "))
                longitude = float(input("Enter longitude: "))
                radius = int(input("Enter geofence radius in meters (default 50): ") or 50)
                
                session_id = geo_system.create_geofenced_session(
                    module_code, date, location_name, latitude, longitude, radius
                )
                
                if session_id:
                    print(f"✅ Geofenced session created successfully!")
                    print(f"Session ID: {session_id}")
                else:
                    print("❌ Failed to create geofenced session")
        except (ValueError, IndexError):
            print("Invalid input.")
    
    elif choice == '2':
        student_id = input("Enter student ID: ")
        latitude = float(input("Enter current latitude: "))
        longitude = float(input("Enter current longitude: "))
        
        success, message = geo_system.check_location_attendance(student_id, latitude, longitude)
        
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")

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

# Missing helper functions that are referenced in the code
def get_setting(setting_name, default_value=None):
    """Get setting value from database or return default"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT setting_value FROM attendance_settings 
        WHERE setting_name = ?
        ''', (setting_name,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else default_value
        
    except Exception as e:
        print(f"Error getting setting: {e}")
        return default_value

def get_modules():
    """Get list of available modules"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if student_modules table exists and has module_name column
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_modules'")
        student_modules_exists = cursor.fetchone() is not None

        if student_modules_exists:
            # Check if module_name column exists
            cursor.execute("PRAGMA table_info(student_modules)")
            columns = [row[1] for row in cursor.fetchall()]
            has_module_name = 'module_name' in columns

            if has_module_name:
                # Use the original query with module_name
                cursor.execute('''
                SELECT DISTINCT module_code,
                       COALESCE(module_name, module_code) as module_name
                FROM (
                    SELECT DISTINCT module_code, NULL as module_name
                    FROM attendance_records
                    UNION
                    SELECT DISTINCT module_code, module_name
                    FROM student_modules
                )
                ORDER BY module_code
                ''')
            else:
                # Use simplified query without module_name
                cursor.execute('''
                SELECT DISTINCT module_code, module_code as module_name
                FROM (
                    SELECT DISTINCT module_code FROM attendance_records
                    UNION
                    SELECT DISTINCT module_code FROM student_modules
                )
                ORDER BY module_code
                ''')
        else:
            # Only use attendance_records
            cursor.execute('''
            SELECT DISTINCT module_code, module_code as module_name
            FROM attendance_records
            ORDER BY module_code
            ''')

        modules = cursor.fetchall()
        conn.close()

        return modules

    except Exception as e:
        print(f"Error getting modules: {e}")
        return []

def get_attendance_records(student_id=None, module_code=None, date_from=None, date_to=None):
    """Get attendance records with optional filters"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = '''
        SELECT ar.student_id, s.first_name, s.last_name, ar.module_code, 
               ar.id, ar.date, ar.status, ar.notes
        FROM attendance_records ar
        JOIN students s ON ar.student_id = s.student_id
        WHERE 1=1
        '''
        
        params = []
        
        if student_id:
            query += ' AND ar.student_id = ?'
            params.append(student_id)
        
        if module_code:
            query += ' AND ar.module_code = ?'
            params.append(module_code)
        
        if date_from:
            query += ' AND ar.date >= ?'
            params.append(date_from)
        
        if date_to:
            query += ' AND ar.date <= ?'
            params.append(date_to)
        
        query += ' ORDER BY ar.date DESC, ar.student_id'
        
        cursor.execute(query, params)
        records = cursor.fetchall()
        conn.close()
        
        return records
        
    except Exception as e:
        print(f"Error getting attendance records: {e}")
        return []

def get_student_attendance(student_id, module_code=None):
    """Get student attendance statistics"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if module_code:
            query = '''
            SELECT ar.module_code,
                   COUNT(*) as total_sessions,
                   SUM(CASE WHEN ar.status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended,
                   AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as percentage
            FROM attendance_records ar
            WHERE ar.student_id = ? AND ar.module_code = ?
            GROUP BY ar.module_code
            '''
            cursor.execute(query, (student_id, module_code))
        else:
            query = '''
            SELECT ar.module_code,
                   COUNT(*) as total_sessions,
                   SUM(CASE WHEN ar.status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended,
                   AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as percentage
            FROM attendance_records ar
            WHERE ar.student_id = ?
            GROUP BY ar.module_code
            '''
            cursor.execute(query, (student_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        stats = {}
        for module_code, total, attended, percentage in results:
            stats[module_code] = {
                'total_sessions': total,
                'attended': attended,
                'percentage': percentage or 0
            }
        
        return stats
        
    except Exception as e:
        print(f"Error getting student attendance: {e}")
        return {}

def get_module_attendance(module_code):
    """Get module attendance statistics"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Overall module stats
        cursor.execute('''
        SELECT 
            COUNT(DISTINCT ar.student_id) as total_students,
            COUNT(*) as total_sessions,
            AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as overall_percentage
        FROM attendance_records ar
        WHERE ar.module_code = ?
        ''', (module_code,))
        
        overall_stats = cursor.fetchone()
        
        # Per student stats
        cursor.execute('''
        SELECT 
            ar.student_id,
            s.first_name,
            s.last_name,
            COUNT(*) as sessions,
            SUM(CASE WHEN ar.status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended,
            AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as percentage
        FROM attendance_records ar
        JOIN students s ON ar.student_id = s.student_id
        WHERE ar.module_code = ?
        GROUP BY ar.student_id, s.first_name, s.last_name
        ORDER BY percentage DESC
        ''', (module_code,))
        
        student_stats = cursor.fetchall()
        conn.close()
        
        return {
            'total_students': overall_stats[0] or 0,
            'total_sessions': overall_stats[1] or 0,
            'overall_percentage': overall_stats[2] or 0,
            'students': [
                {
                    'student_id': row[0],
                    'name': f"{row[1]} {row[2]}",
                    'sessions': row[3],
                    'attended': row[4],
                    'percentage': row[5] or 0
                }
                for row in student_stats
            ]
        }
        
    except Exception as e:
        print(f"Error getting module attendance: {e}")
        return {'total_students': 0, 'total_sessions': 0, 'overall_percentage': 0, 'students': []}

def record_attendance(module_code, date, attendance_data, recorded_by="System"):
    """Record attendance for multiple students"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        for student_id, status, notes in attendance_data:
            cursor.execute('''
            INSERT OR REPLACE INTO attendance_records 
            (student_id, module_code, date, status, notes, recorded_by, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, module_code, date, status, notes, recorded_by, 
                  datetime.datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"Error recording attendance: {e}")
        return False

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

def generate_student_attendance_report(student_id, output_format='screen', output_path=None):
    """Generate attendance report for a student"""
    try:
        stats = get_student_attendance(student_id)
        
        if not stats:
            print(f"No attendance data found for student {student_id}")
            return False
        
        # Get student info
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT first_name, last_name, email_address FROM students 
        WHERE student_id = ?
        ''', (student_id,))
        
        student_info = cursor.fetchone()
        conn.close()
        
        if not student_info:
            print(f"Student {student_id} not found")
            return False
        
        first_name, last_name, email = student_info
        
        if output_format == 'screen':
            print(f"\n📊 ATTENDANCE REPORT: {first_name} {last_name} ({student_id})")
            print("=" * 60)
            
            for module_code, data in stats.items():
                print(f"\nModule: {module_code}")
                print(f"Total Sessions: {data['total_sessions']}")
                print(f"Attended: {data['attended']}")
                print(f"Attendance Rate: {data['percentage']:.1f}%")
            
            overall_rate = sum(data['percentage'] for data in stats.values()) / len(stats)
            print(f"\nOverall Attendance Rate: {overall_rate:.1f}%")
        
        elif output_format == 'csv':
            if not output_path:
                output_path = f"student_report_{student_id}_{datetime.date.today().strftime('%Y%m%d')}.csv"
            
            data_rows = []
            for module_code, data in stats.items():
                data_rows.append({
                    'Student ID': student_id,
                    'Name': f"{first_name} {last_name}",
                    'Module': module_code,
                    'Total Sessions': data['total_sessions'],
                    'Attended': data['attended'],
                    'Attendance Rate': f"{data['percentage']:.1f}%"
                })
            
            df = pd.DataFrame(data_rows)
            df.to_csv(output_path, index=False)
            print(f"✅ Report saved to: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"Error generating student report: {e}")
        return False

def generate_module_attendance_report(module_code, date_from=None, date_to=None, output_format='screen', output_path=None):
    """Generate attendance report for a module"""
    try:
        stats = get_module_attendance(module_code)
        
        if not stats['students']:
            print(f"No attendance data found for module {module_code}")
            return False
        
        if output_format == 'screen':
            print(f"\n📊 MODULE ATTENDANCE REPORT: {module_code}")
            print("=" * 60)
            print(f"Total Students: {stats['total_students']}")
            print(f"Total Sessions: {stats['total_sessions']}")
            print(f"Overall Attendance Rate: {stats['overall_percentage']:.1f}%")
            
            print(f"\n{'Student ID':<12} {'Name':<25} {'Sessions':<10} {'Attended':<10} {'Rate'}")
            print("-" * 70)
            
            for student in stats['students']:
                print(f"{student['student_id']:<12} {student['name']:<25} {student['sessions']:<10} "
                      f"{student['attended']:<10} {student['percentage']:.1f}%")
        
        elif output_format == 'csv':
            if not output_path:
                output_path = f"module_report_{module_code}_{datetime.date.today().strftime('%Y%m%d')}.csv"
            
            df = pd.DataFrame(stats['students'])
            df.to_csv(output_path, index=False)
            print(f"✅ Report saved to: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"Error generating module report: {e}")
        return False

def handle_audit_logs():
    """Handle audit logs viewing"""
    print("\n📋 AUDIT LOGS")
    print("1. View Recent Logs")
    print("2. Search Logs")
    print("3. Export Logs")
    
    choice = input("Enter your choice (1-3): ")
    
    if choice == '1':
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT user_id, action, table_name, record_id, timestamp
            FROM attendance_audit_log
            ORDER BY timestamp DESC
            LIMIT 50
            ''')
            
            logs = cursor.fetchall()
            conn.close()
            
            if logs:
                print("\n📋 RECENT AUDIT LOGS")
                print("=" * 80)
                print(f"{'User':<15} {'Action':<20} {'Table':<20} {'Record ID':<15} {'Timestamp'}")
                print("-" * 80)
                
                for log in logs:
                    user_id, action, table_name, record_id, timestamp = log
                    timestamp_display = timestamp.split('T')[0] + ' ' + timestamp.split('T')[1][:8]
                    print(f"{user_id:<15} {action:<20} {table_name:<20} {record_id:<15} {timestamp_display}")
            else:
                print("No audit logs found.")
                
        except Exception as e:
            print(f"Error retrieving audit logs: {e}")

def handle_lms_integration():
    """Handle LMS integration"""
    print("\n🔗 LMS INTEGRATION")
    print("This feature would integrate with learning management systems")
    print("like Moodle, Canvas, Blackboard, etc.")
    print("Implementation depends on specific LMS APIs and requirements.")

def handle_calendar_sync():
    """Handle calendar synchronization"""
    print("\n📅 CALENDAR SYNC")
    print("This feature would sync with calendar systems")
    print("like Google Calendar, Outlook, etc.")
    print("Implementation requires calendar API access.")

def handle_import_export():
    """Handle data import/export"""
    print("\n📁 IMPORT/EXPORT DATA")
    print("1. Export Attendance Data")
    print("2. Import Student Data")
    print("3. Backup Database")
    
    choice = input("Enter your choice (1-3): ")
    
    if choice == '1':
        print("Exporting attendance data...")
        
        try:
            conn = get_connection()
            
            query = '''
            SELECT ar.student_id, s.first_name, s.last_name, ar.module_code,
                   ar.date, ar.status, ar.notes, ar.check_in_method, ar.recorded_at
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            ORDER BY ar.date DESC, ar.student_id
            '''
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if not df.empty:
                output_path = f"attendance_export_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
                df.to_excel(output_path, index=False)
                print(f"✅ Attendance data exported to: {output_path}")
            else:
                print("No attendance data to export.")
                
        except Exception as e:
            print(f"Error exporting data: {e}")


# GUI Launcher using factory pattern
try:
    from university_system.modules.shared.feature_gui_factory import create_gui_launcher

    launch_advanced_attendance_gui = create_gui_launcher(
        title="Advanced Attendance System",
        description="""Advanced attendance tracking with QR codes, geolocation, facial recognition, and analytics.

Features:
• QR code check-in
• Geolocation verification
• Facial recognition
• Predictive analytics
• Automated notifications
• Gamification system
• Real-time dashboard
• Attendance reports
• Backup & recovery
• Parent notifications""",
        cli_instruction="Use CLI: Advanced Attendance System"
    )
except ImportError:
    # Fallback if factory not available
    def launch_advanced_attendance_gui(root, auth):
        from tkinter import messagebox
        messagebox.showinfo("Attendance System", "Please use the CLI: Advanced Attendance System")


# Export public API
__all__ = [
    # Classes
    'QRAttendanceSystem',
    'GeofencingSystem',
    'FaceRecognitionSystem',
    'AttendancePredictiveAnalytics',
    'EnhancedNotificationSystem',
    'AttendanceDashboard',
    'AttendanceAPI',
    'BackupRecoverySystem',
    # Functions
    'init_enhanced_attendance_db',
    'create_missing_tables',
    'display_attendance_menu',
    'launch_advanced_attendance_gui',
    'get_modules',
    'get_student_attendance',
    'get_module_attendance',
    'record_attendance',
    'get_enhanced_setting',
    'set_enhanced_setting',
    'generate_executive_summary_report',
]


# Main function to run the enhanced attendance system
if __name__ == "__main__":
    print("🎓 ENHANCED ATTENDANCE TRACKING SYSTEM")
    print("=" * 50)
    display_attendance_menu()