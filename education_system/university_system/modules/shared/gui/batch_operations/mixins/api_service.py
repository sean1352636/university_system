"""API/Web service mixin."""

import threading

from education_system.university_system.modules.shared.gui.batch_operations.constants import (
    datetime, logging,
    Flask, request, jsonify,
    logger,
)

from education_system.university_system.modules.shared.gui.batch_operations.models import ImportResult


class ApiServiceMixin:
    """Mixin providing Flask API server and route setup methods."""

    def start_api_server_gui(self, host: str = "localhost", port: int = 5000,
                             progress_callback=None) -> bool:
        """Start Flask API server - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, f"Starting API server on {host}:{port}...")

            # Create Flask app
            app = Flask('UniversityBatchAPI')

            # Setup routes
            self.setup_api_routes_gui(app, progress_callback)

            if progress_callback:
                progress_callback(50, "Setting up API routes...")

            # Run server in background thread
            def run_server():
                try:
                    app.run(host=host, port=port, threaded=True)
                except Exception as e:
                    logger.error(f"API server error: {e}")

            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()

            if progress_callback:
                progress_callback(100, f"API server started at http://{host}:{port}")

            logger.info(f"Started API server at http://{host}:{port}")
            return True

        except Exception as e:
            logger.error(f"Error starting API server: {e}")
            raise

    def setup_api_routes_gui(self, app: Flask, progress_callback=None):
        """Setup Flask API routes - GUI version"""
        try:
            # Health check endpoint
            @app.route('/api/health', methods=['GET'])
            def health_check():
                """Health check endpoint - Returns API status"""
                return jsonify({
                    'status': 'healthy',
                    'service': 'University Batch Operations API',
                    'version': '1.0',
                    'timestamp': datetime.datetime.now().isoformat()
                }), 200

            # Import endpoint
            @app.route('/api/import', methods=['POST'])
            def api_import():
                """Import data via API - POST endpoint for imports"""
                try:
                    data = request.get_json()

                    if not data or 'records' not in data:
                        return jsonify({'error': 'Missing records in request'}), 400

                    records = data['records']
                    import_type = data.get('type', 'student')

                    # Process based on type
                    if import_type == 'student':
                        result = ImportResult()
                        result.total_records = len(records)

                        with self.db_manager.get_connection() as conn:
                            cursor = conn.cursor()

                            for record in records:
                                try:
                                    cleaned = self.clean_student_data(record)
                                    errors = self.validate_student_data(cleaned)

                                    if errors:
                                        result.failed_imports += 1
                                        result.errors.append(errors)
                                        continue

                                    # Insert student
                                    cursor.execute("""
                                        INSERT INTO students (student_id, first_name, last_name,
                                        date_of_birth, email, phone_number, address, course,
                                        enrollment_date, status)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (
                                        cleaned.get('student_id'),
                                        cleaned.get('first_name'),
                                        cleaned.get('last_name'),
                                        cleaned.get('date_of_birth'),
                                        cleaned.get('email'),
                                        cleaned.get('phone_number'),
                                        cleaned.get('address'),
                                        cleaned.get('course', 'GENERAL'),
                                        cleaned.get('enrollment_date', datetime.date.today().isoformat()),
                                        cleaned.get('status', 'Active')
                                    ))
                                    result.successful_imports += 1

                                except Exception as e:
                                    result.failed_imports += 1
                                    result.errors.append(str(e))

                            conn.commit()

                        return jsonify({
                            'status': 'success',
                            'total_records': result.total_records,
                            'successful_imports': result.successful_imports,
                            'failed_imports': result.failed_imports,
                            'errors': result.errors[:10]  # First 10 errors
                        }), 200

                    else:
                        return jsonify({'error': f'Unsupported import type: {import_type}'}), 400

                except Exception as e:
                    logger.error("API import error: %s", e)
                    return jsonify({'error': 'Internal server error'}), 500

            # Get students endpoint
            @app.route('/api/students', methods=['GET'])
            def api_get_students():
                """Get students via API - GET endpoint with filtering"""
                try:
                    # Get query parameters
                    course = request.args.get('course')
                    status = request.args.get('status')
                    limit = int(request.args.get('limit', 100))
                    offset = int(request.args.get('offset', 0))

                    with self.db_manager.get_connection() as conn:
                        cursor = conn.cursor()

                        # Build query
                        query = "SELECT * FROM students WHERE 1=1"
                        params = []

                        if course:
                            query += " AND course = ?"
                            params.append(course)

                        if status:
                            query += " AND status = ?"
                            params.append(status)

                        query += f" LIMIT {limit} OFFSET {offset}"

                        cursor.execute(query, params)
                        students = cursor.fetchall()

                        # Convert to list of dicts
                        student_list = []
                        for student in students:
                            student_list.append({
                                'student_id': student[0],
                                'first_name': student[1],
                                'last_name': student[2],
                                'date_of_birth': student[3],
                                'email': student[4],
                                'phone_number': student[5],
                                'address': student[6],
                                'course': student[7],
                                'enrollment_date': student[8],
                                'status': student[9]
                            })

                        return jsonify({
                            'status': 'success',
                            'count': len(student_list),
                            'students': student_list
                        }), 200

                except Exception as e:
                    logger.error("API get students error: %s", e)
                    return jsonify({'error': 'Internal server error'}), 500

            # Update student endpoint
            @app.route('/api/students/<student_id>', methods=['PUT'])
            def api_update_student(student_id):
                """Update student via API - PUT endpoint for updates"""
                try:
                    data = request.get_json()

                    if not data:
                        return jsonify({'error': 'Missing update data'}), 400

                    with self.db_manager.get_connection() as conn:
                        cursor = conn.cursor()

                        # Verify student exists
                        cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
                        if not cursor.fetchone():
                            return jsonify({'error': f'Student {student_id} not found'}), 404

                        # Build update query
                        update_fields = []
                        update_values = []

                        for field in ['first_name', 'last_name', 'email', 'phone_number',
                                     'address', 'course', 'status']:
                            if field in data:
                                update_fields.append(f"{field} = ?")
                                update_values.append(data[field])

                        if not update_fields:
                            return jsonify({'error': 'No valid fields to update'}), 400

                        update_values.append(student_id)
                        query = f"UPDATE students SET {', '.join(update_fields)} WHERE student_id = ?"

                        cursor.execute(query, update_values)
                        conn.commit()

                        return jsonify({
                            'status': 'success',
                            'student_id': student_id,
                            'updated_fields': len(update_fields)
                        }), 200

                except Exception as e:
                    logger.error("API update student error: %s", e)
                    return jsonify({'error': 'Internal server error'}), 500

            logger.info("API routes configured successfully")

        except Exception as e:
            logger.error(f"Error setting up API routes: {e}")
            raise
