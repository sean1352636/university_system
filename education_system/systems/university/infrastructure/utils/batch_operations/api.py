import datetime
import threading

from flask import Flask, request, jsonify

from education_system.systems.university.infrastructure.logging.log_config import configure_logging
from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = configure_logging(name=__name__)


class ApiMixin:
    """Mixin providing REST API server methods."""

    def start_api_server(self):
        """Start REST API server for external integrations"""
        print("\n" + _t("shared.utils.batch_operations.title_start_api"))

        if self.api_app is not None:
            print(_t("shared.utils.batch_operations.api_already_running"))
            return

        port = input(_t("shared.utils.batch_operations.prompt_port_number")).strip()
        if not port:
            port = 5000
        else:
            try:
                port = int(port)
            except ValueError:
                print(_t("shared.utils.batch_operations.invalid_port"))
                return

        # Create Flask app
        self.api_app = Flask(__name__)
        self.setup_api_routes()

        print(_t("shared.utils.batch_operations.starting_api_server", port=port))
        print(_t("shared.utils.batch_operations.available_endpoints"))
        print(_t("batch_ops.api.endpoint_import"))
        print(_t("batch_ops.api.endpoint_students"))
        print(_t("batch_ops.api.endpoint_update"))
        print(_t("batch_ops.api.endpoint_health"))

        # Run in separate thread
        def run_server():
            self.api_app.run(host='127.0.0.1', port=port, debug=False)

        api_thread = threading.Thread(target=run_server, daemon=True)
        api_thread.start()

        print(_t("shared.utils.batch_operations.api_started"))
        input(_t("shared.utils.batch_operations.press_enter_stop"))

        # Note: In a production environment, you'd want proper server management

    def setup_api_routes(self):
        """Set up API routes"""
        from education_system.systems.university.infrastructure.database.db import sqlite3

        @self.api_app.route('/api/health', methods=['GET'])
        def health_check():
            return jsonify({'status': 'healthy', 'timestamp': datetime.datetime.now().isoformat()})

        @self.api_app.route('/api/import', methods=['POST'])
        def api_import():
            try:
                data = request.get_json()

                if not data or 'records' not in data:
                    return jsonify({'error': _t("batch_ops.api.error_no_records")}), 400

                records = data['records']

                # Validate records
                valid_records = []
                errors = []

                for i, record in enumerate(records):
                    validation_errors = self.validate_student_data(record)
                    if validation_errors:
                        errors.append({'record_index': i, 'errors': validation_errors})
                    else:
                        valid_records.append(record)

                if valid_records:
                    # Import valid records
                    result = self.import_valid_records(valid_records)

                    return jsonify({
                        'success': True,
                        'imported': result.successful_imports,
                        'failed': result.failed_imports,
                        'validation_errors': errors
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': _t("batch_ops.api.error_no_valid_records"),
                        'validation_errors': errors
                    }), 400

            except Exception as e:
                logger.error("API import error: %s", e)
                return jsonify({'error': 'Internal server error'}), 500

        @self.api_app.route('/api/students', methods=['GET'])
        def api_get_students():
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                # Get query parameters
                course = request.args.get('course')
                limit = request.args.get('limit', 100, type=int)
                offset = request.args.get('offset', 0, type=int)

                # Build query
                query = "SELECT * FROM students"
                params = []

                if course:
                    query += " WHERE course = ?"
                    params.append(course)

                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                students = cursor.fetchall()

                # Convert to dict format
                columns = [desc[0] for desc in cursor.description]
                student_list = [dict(zip(columns, student)) for student in students]

                conn.close()

                return jsonify({
                    'students': student_list,
                    'count': len(student_list),
                    'limit': limit,
                    'offset': offset
                })

            except Exception as e:
                logger.error("API get students error: %s", e)
                return jsonify({'error': 'Internal server error'}), 500

        @self.api_app.route('/api/students/<student_id>', methods=['PUT'])
        def api_update_student(student_id):
            try:
                data = request.get_json()

                if not data:
                    return jsonify({'error': _t("batch_ops.api.error_no_data")}), 400

                # Add student_id to data for validation
                data['student_id'] = student_id

                # Validate update data
                errors = self.validate_student_data(data, is_update=True)
                if errors:
                    return jsonify({'error': _t("batch_ops.api.error_validation_failed"), 'details': errors}), 400

                # Update record
                self.update_existing_record(student_id, data)

                return jsonify({
                    'success': True,
                    'message': _t("batch_ops.api.student_updated", student_id=student_id)
                })

            except Exception as e:
                logger.error("API update student error: %s", e)
                return jsonify({'error': 'Internal server error'}), 500
