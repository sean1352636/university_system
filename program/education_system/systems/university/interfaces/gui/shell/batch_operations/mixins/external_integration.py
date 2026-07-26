"""External system integration mixin."""

from education_system.systems.university.interfaces.gui.shell.batch_operations.constants import (
    datetime, json, logging,
    List, Tuple,
    Path,
    requests,
    logger,
    EXTERNAL_DB_CONFIG_PATH,
    EXTERNAL_API_CONFIG_PATH,
)


class ExternalIntegrationMixin:
    """Mixin providing external DB, REST API, file share integration and export methods."""

    def external_system_integration_gui(self, callback=None) -> str:
        """Main menu for external integrations - GUI version"""
        message = """
EXTERNAL SYSTEM INTEGRATION

Available Integration Options:
1. External Database - Connect to MySQL/PostgreSQL/SQL Server
2. REST API - Integrate with external REST APIs
3. File Share Monitoring - Auto-import from shared folders
4. Export Options - Export data to external systems

Configuration:
- Database connections require credentials
- REST API requires endpoint URLs and auth tokens
- File share requires network path access
- All integrations support scheduling

Note: Ensure proper network connectivity and credentials.
"""

        if callback:
            callback(message)

        return message

    def setup_database_integration_gui(self, db_type: str, host: str, port: int,
                                       database: str, username: str, password: str,
                                       progress_callback=None) -> bool:
        """Setup external database connection - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, f"Connecting to {db_type} database...")

            config = {
                'type': db_type,
                'host': host,
                'port': port,
                'database': database,
                'username': username,
                'password': password,
                'created_at': datetime.datetime.now().isoformat()
            }

            # Test connection based on type
            if db_type == 'mysql':
                try:
                    import mysql.connector
                    conn = mysql.connector.connect(
                        host=host,
                        port=port,
                        database=database,
                        user=username,
                        password=password
                    )
                    conn.close()
                except Exception as e:
                    raise ConnectionError(f"MySQL connection failed: {e}")

            elif db_type == 'postgresql':
                try:
                    import psycopg2
                    conn = psycopg2.connect(
                        host=host,
                        port=port,
                        database=database,
                        user=username,
                        password=password
                    )
                    conn.close()
                except Exception as e:
                    raise ConnectionError(f"PostgreSQL connection failed: {e}")

            elif db_type == 'sqlserver':
                try:
                    import pyodbc
                    conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={host},{port};DATABASE={database};UID={username};PWD={password}"
                    conn = pyodbc.connect(conn_str)
                    conn.close()
                except Exception as e:
                    raise ConnectionError(f"SQL Server connection failed: {e}")

            else:
                raise ValueError(f"Unsupported database type: {db_type}")

            if progress_callback:
                progress_callback(50, "Saving configuration...")

            # Save configuration
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS external_db_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_data TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                config_json = json.dumps(config)
                cursor.execute("""
                    INSERT INTO external_db_config (config_data)
                    VALUES (?)
                """, (config_json,))

                conn.commit()

            if progress_callback:
                progress_callback(100, f"External database configured: {db_type}")

            logger.info(f"Configured external {db_type} database connection")
            return True

        except Exception as e:
            logger.error(f"Error setting up database integration: {e}")
            raise

    def setup_rest_api_integration_gui(self, api_url: str, api_key: str,
                                       auth_type: str = 'bearer',
                                       progress_callback=None) -> bool:
        """Setup REST API integration - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, f"Testing connection to {api_url}...")

            config = {
                'api_url': api_url,
                'api_key': api_key,
                'auth_type': auth_type,
                'created_at': datetime.datetime.now().isoformat()
            }

            # Test connection
            headers = {}
            if auth_type == 'bearer':
                headers['Authorization'] = f'Bearer {api_key}'
            elif auth_type == 'apikey':
                headers['X-API-Key'] = api_key
            elif auth_type == 'basic':
                import base64
                headers['Authorization'] = f'Basic {base64.b64encode(api_key.encode()).decode()}'

            try:
                response = requests.get(f"{api_url}/health", headers=headers, timeout=10)
                if response.status_code not in [200, 404]:  # 404 ok if no health endpoint
                    raise ConnectionError(f"API returned status {response.status_code}")
            except requests.exceptions.RequestException as e:
                raise ConnectionError(f"API connection failed: {e}")

            if progress_callback:
                progress_callback(50, "Saving configuration...")

            # Save configuration
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS external_api_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_data TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                config_json = json.dumps(config)
                cursor.execute("""
                    INSERT INTO external_api_config (config_data)
                    VALUES (?)
                """, (config_json,))

                conn.commit()

            if progress_callback:
                progress_callback(100, f"REST API configured: {api_url}")

            logger.info(f"Configured REST API integration: {api_url}")
            return True

        except Exception as e:
            logger.error(f"Error setting up REST API integration: {e}")
            raise

    def setup_file_share_monitoring_gui(self, share_path: str,
                                        file_pattern: str = "*.csv",
                                        check_interval: int = 300,
                                        progress_callback=None) -> bool:
        """Setup file share monitoring - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, "Configuring file share monitoring...")

            # Verify path exists
            share_path_obj = Path(share_path)
            if not share_path_obj.exists():
                raise FileNotFoundError(f"Share path does not exist: {share_path}")

            config = {
                'share_path': share_path,
                'file_pattern': file_pattern,
                'check_interval': check_interval,
                'created_at': datetime.datetime.now().isoformat()
            }

            if progress_callback:
                progress_callback(50, "Saving configuration...")

            # Save configuration
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS file_share_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_data TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                config_json = json.dumps(config)
                cursor.execute("""
                    INSERT INTO file_share_config (config_data)
                    VALUES (?)
                """, (config_json,))

                conn.commit()

            if progress_callback:
                progress_callback(100, f"File share monitoring configured: {share_path}")

            logger.info(f"Configured file share monitoring: {share_path}")
            return True

        except Exception as e:
            logger.error(f"Error setting up file share monitoring: {e}")
            raise

    def export_to_external_system_gui(self, callback=None) -> str:
        """Main menu for external exports - GUI version"""
        message = """
EXPORT TO EXTERNAL SYSTEMS

Available Export Destinations:
1. External Database - Export to MySQL/PostgreSQL/SQL Server
2. REST API - Push data to external REST API
3. File Share - Export to network file share
4. Email - Send exports via email

Export Options:
- Full export or filtered by criteria
- Multiple formats (CSV, JSON, Excel)
- Scheduling support
- Progress tracking

Note: Ensure external systems are configured before exporting.
"""

        if callback:
            callback(message)

        return message

    def export_to_external_database_gui(self, students: List[Tuple] = None,
                                        progress_callback=None) -> bool:
        """Export data to external database - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, "Loading external database configuration...")

            # Load configuration
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT config_data FROM external_db_config
                    ORDER BY created_at DESC LIMIT 1
                """)
                config_row = cursor.fetchone()

                if not config_row:
                    raise ValueError("No external database configured")

                config = json.loads(config_row[0])

                # Get students if not provided
                if students is None:
                    cursor.execute("SELECT * FROM students")
                    students = cursor.fetchall()

            if progress_callback:
                progress_callback(20, f"Connecting to {config['type']} database...")

            # Export based on database type
            if config['type'] == 'mysql':
                import mysql.connector
                ext_conn = mysql.connector.connect(
                    host=config['host'],
                    port=config['port'],
                    database=config['database'],
                    user=config['username'],
                    password=config['password']
                )
            elif config['type'] == 'postgresql':
                import psycopg2
                ext_conn = psycopg2.connect(
                    host=config['host'],
                    port=config['port'],
                    database=config['database'],
                    user=config['username'],
                    password=config['password']
                )
            else:
                raise ValueError(f"Unsupported database type: {config['type']}")

            ext_cursor = ext_conn.cursor()

            if progress_callback:
                progress_callback(40, "Creating external table if needed...")

            # Create table if not exists
            ext_cursor.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    student_id VARCHAR(50) PRIMARY KEY,
                    first_name VARCHAR(100),
                    last_name VARCHAR(100),
                    date_of_birth DATE,
                    email VARCHAR(100),
                    phone_number VARCHAR(20),
                    address TEXT,
                    course VARCHAR(100),
                    enrollment_date DATE,
                    status VARCHAR(20)
                )
            """)

            if progress_callback:
                progress_callback(60, f"Exporting {len(students)} students...")

            # Insert students
            for i, student in enumerate(students):
                try:
                    ext_cursor.execute("""
                        INSERT INTO students VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        first_name = VALUES(first_name),
                        last_name = VALUES(last_name),
                        email = VALUES(email)
                    """ if config['type'] == 'mysql' else """
                        INSERT INTO students VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (student_id) DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        email = EXCLUDED.email
                    """, student[:10])

                    if progress_callback and i % 10 == 0:
                        progress = 60 + int((i / len(students)) * 30)
                        progress_callback(progress, f"Exporting: {i}/{len(students)}")

                except Exception as e:
                    logger.error(f"Error exporting student {student[0]}: {e}")

            ext_conn.commit()
            ext_conn.close()

            if progress_callback:
                progress_callback(100, f"Exported {len(students)} students to external database")

            logger.info(f"Exported {len(students)} students to external {config['type']} database")
            return True

        except Exception as e:
            logger.error(f"Error exporting to external database: {e}")
            raise

    def export_via_rest_api_gui(self, students: List[Tuple] = None,
                                progress_callback=None) -> bool:
        """Export data via REST API - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, "Loading REST API configuration...")

            # Load configuration
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT config_data FROM external_api_config
                    ORDER BY created_at DESC LIMIT 1
                """)
                config_row = cursor.fetchone()

                if not config_row:
                    raise ValueError("No REST API configured")

                config = json.loads(config_row[0])

                # Get students if not provided
                if students is None:
                    cursor.execute("SELECT * FROM students")
                    students = cursor.fetchall()

            if progress_callback:
                progress_callback(20, "Preparing data for export...")

            # Convert to JSON
            student_data = []
            for student in students:
                student_data.append({
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

            # Prepare headers
            headers = {'Content-Type': 'application/json'}
            if config['auth_type'] == 'bearer':
                headers['Authorization'] = f"Bearer {config['api_key']}"
            elif config['auth_type'] == 'apikey':
                headers['X-API-Key'] = config['api_key']

            if progress_callback:
                progress_callback(50, f"Sending {len(student_data)} students to API...")

            # Send to API
            response = requests.post(
                f"{config['api_url']}/students/bulk",
                json={'students': student_data},
                headers=headers,
                timeout=60
            )

            if response.status_code not in [200, 201]:
                raise Exception(f"API returned status {response.status_code}: {response.text}")

            if progress_callback:
                progress_callback(100, f"Exported {len(student_data)} students via REST API")

            logger.info(f"Exported {len(student_data)} students via REST API")
            return True

        except Exception as e:
            logger.error(f"Error exporting via REST API: {e}")
            raise

    def export_to_file_share_gui(self, filename: str, file_format: str = 'csv',
                                 progress_callback=None) -> str:
        """Export to network file share - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, "Loading file share configuration...")

            # Load configuration
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT config_data FROM file_share_config
                    ORDER BY created_at DESC LIMIT 1
                """)
                config_row = cursor.fetchone()

                if not config_row:
                    raise ValueError("No file share configured")

                config = json.loads(config_row[0])

                # Get students
                cursor.execute("SELECT * FROM students")
                students = cursor.fetchall()

            if progress_callback:
                progress_callback(30, f"Exporting {len(students)} students...")

            # Prepare export path
            share_path = Path(config['share_path'])
            export_file = share_path / filename

            # Export data
            columns = ['student_id', 'first_name', 'last_name', 'date_of_birth', 'email',
                      'phone_number', 'address', 'course', 'enrollment_date', 'status']

            export_path = self.export_data_to_file(students, columns, str(export_file),
                                                   file_format, None)

            if progress_callback:
                progress_callback(100, f"Exported to file share: {export_path}")

            logger.info(f"Exported data to file share: {export_path}")
            return export_path

        except Exception as e:
            logger.error(f"Error exporting to file share: {e}")
            raise

    def export_via_email_gui(self, email: str, subject: str = "Student Data Export",
                            file_format: str = 'csv', progress_callback=None) -> bool:
        """Export and send via email - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, "Generating export file...")

            # Generate export file
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'student_export_{timestamp}'

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM students")
                students = cursor.fetchall()

            columns = ['student_id', 'first_name', 'last_name', 'date_of_birth', 'email',
                      'phone_number', 'address', 'course', 'enrollment_date', 'status']

            export_path = self.export_data_to_file(students, columns, filename,
                                                   file_format, None)

            if progress_callback:
                progress_callback(50, f"Sending email to {email}...")

            message = f"""
Please find attached the student data export.

Export Details:
- Total Students: {len(students)}
- Format: {file_format.upper()}
- Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

File: {export_path}
"""

            # Send notification (in production, attach file)
            self.send_notification_email_gui(email, message, None)

            if progress_callback:
                progress_callback(100, f"Export sent to {email}")

            logger.info(f"Sent data export to {email}")
            return True

        except Exception as e:
            logger.error(f"Error exporting via email: {e}")
            raise

    def save_external_db_config(self, config: dict):
        """Save external database configuration to file."""
        with open(EXTERNAL_DB_CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info("Saved external database configuration")

    def save_rest_api_config(self, config: dict):
        """Save REST API configuration to file."""
        with open(EXTERNAL_API_CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info("Saved REST API configuration")

    def test_rest_api_connection(self, url: str, api_key: str) -> bool:
        """Test REST API connection."""
        try:
            headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
            response = requests.get(url, headers=headers, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"REST API connection test failed: {e}")
            return False
