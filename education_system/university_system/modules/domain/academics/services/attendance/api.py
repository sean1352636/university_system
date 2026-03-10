"""REST API for attendance tracking system."""

import datetime
from flask import Flask, request, jsonify
from education_system.university_system.modules.domain.academics.services.attendance.settings import get_setting
from education_system.university_system.modules.domain.academics.services.attendance.records import (
    get_student_attendance, record_attendance,
)
from education_system.university_system.modules.domain.academics.services.attendance.qr_system import QRAttendanceSystem
from education_system.university_system.modules.domain.academics.services.attendance.predictive_analytics import AttendancePredictiveAnalytics


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
