from education_system.systems.university.infrastructure.utils.document_manager._common import (
    datetime, timedelta, sqlite3,
    get_connection, _t,
)


class APIServerMixin:
    def api_server_menu(self):
        """API server management menu"""
        print("\n🌐 API SERVER MANAGEMENT")
        print("1. Start API Server")
        print("2. View API Endpoints")
        print("3. API Documentation")
        print("4. API Keys Management")
        print("5. API Usage Statistics")
        print("6. Return to Main Menu")

        choice = input("\nChoose option (1-6): ").strip()

        if choice == '1':
            self.start_api_server()
        elif choice == '2':
            self.view_api_endpoints()
        elif choice == '3':
            self.api_documentation()
        elif choice == '4':
            self.api_keys_management()
        elif choice == '5':
            self.api_usage_statistics()

    def start_api_server(self):
        """Start the REST API server"""
        print("\n🚀 STARTING API SERVER")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT setting_value FROM system_settings
            WHERE setting_name IN ('web_interface_port', 'web_interface_host')
            ''')

            settings = dict(cursor.fetchall()) if cursor.fetchall() else {}

            port = settings.get('web_interface_port', '5000')
            host = settings.get('web_interface_host', '127.0.0.1')

            print("\nAPI Server Configuration:")
            print(f"Host: {host}")
            print(f"Port: {port}")

            print("\nNote: The API server runs as a separate Flask application.")
            print("To start the API server, use:")
            print(f"  python -m shared.api.university.api_server --port {port}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def view_api_endpoints(self):
        """View all available API endpoints"""
        print("\n📋 API ENDPOINTS")
        print("=" * 60)

        endpoints = [
            ('GET', '/api/documents', 'List all documents'),
            ('GET', '/api/documents/{id}', 'Get document details'),
            ('POST', '/api/documents', 'Upload new document'),
            ('PUT', '/api/documents/{id}', 'Update document'),
            ('DELETE', '/api/documents/{id}', 'Delete document'),
            ('GET', '/api/documents/{id}/download', 'Download document'),
            ('GET', '/api/documents/{id}/versions', 'Get version history'),
            ('GET', '/api/students', 'List all students'),
            ('GET', '/api/students/{id}', 'Get student details'),
            ('GET', '/api/students/{id}/documents', 'Get student documents'),
            ('GET', '/api/document-types', 'List document types'),
            ('GET', '/api/reports/status', 'Get status report'),
            ('GET', '/api/reports/expiry', 'Get expiry report'),
            ('GET', '/api/reports/compliance', 'Get compliance report'),
            ('GET', '/api/workflows', 'List active workflows'),
            ('POST', '/api/workflows/{id}/complete', 'Complete workflow step'),
        ]

        print(f"{'Method':<8} {'Endpoint':<35} {'Description'}")
        print("-" * 60)

        for method, endpoint, description in endpoints:
            print(f"{method:<8} {endpoint:<35} {description}")

    def api_documentation(self):
        """Display API documentation"""
        print("\n📚 API DOCUMENTATION")
        print("=" * 80)

        print("""
API Endpoints:

Authentication:
  POST   /api/auth/login              - Authenticate user
  POST   /api/auth/logout             - Logout user

Documents:
  GET    /api/documents               - List all documents
  GET    /api/documents/{id}          - Get document details
  POST   /api/documents               - Upload new document
  PUT    /api/documents/{id}          - Update document
  DELETE /api/documents/{id}          - Delete document

  GET    /api/documents/{id}/download - Download document file
  GET    /api/documents/{id}/versions - Get version history

Students:
  GET    /api/students                - List all students
  GET    /api/students/{id}           - Get student details
  GET    /api/students/{id}/documents - Get student's documents

Document Types:
  GET    /api/document-types          - List document types
  GET    /api/document-types/{id}     - Get type details

Reports:
  GET    /api/reports/status          - Get status report
  GET    /api/reports/expiry          - Get expiry report
  GET    /api/reports/compliance      - Get compliance report

Workflows:
  GET    /api/workflows               - List active workflows
  GET    /api/workflows/{id}          - Get workflow details
  POST   /api/workflows/{id}/complete - Complete workflow step

Authentication:
  All API requests require an API key in the header:
  Authorization: Bearer YOUR_API_KEY

Response Format:
  All responses are in JSON format
  Success: {"status": "success", "data": {...}}
  Error: {"status": "error", "message": "Error description"}

Rate Limiting:
  - 1000 requests per hour per API key
  - 10000 requests per day per API key

For detailed documentation and examples, visit:
  http://your-server/api/docs
        """)

        save_doc = input("\nSave documentation to file? (y/n): ").strip().lower()
        if save_doc == 'y':
            filename = "api_documentation.txt"
            with open(filename, 'w') as f:
                f.write("API Documentation\n")
                f.write("=" * 80 + "\n\n")
                f.write("Refer to console output for full documentation.\n")
            print(f"✅ Documentation saved to {filename}")

    DOCUMENT_KEY_PREFIX = "documents: "

    def _key_manager(self):
        """The platform API key store (shared auth DB, PBKDF2-hashed, shown
        once) — the same one the admin API Management window uses."""
        from education_system import paths
        from education_system.platform.delivery.api.security.api_keys import APIKeyManager
        return APIKeyManager(str(paths.PLATFORM_AUTH_DB))

    def _retire_plaintext_keys(self):
        """Older builds stored raw keys in student_records ``api_keys.api_key``.
        Overwrite any such value and deactivate the row so it can never be
        read back or used. Runs whenever keys are managed; a no-op once clean."""
        conn = get_connection()
        try:
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                                  "AND name = 'api_keys'").fetchone()
            if not exists:
                return 0
            cols = {r[1] for r in conn.execute("PRAGMA table_info(api_keys)")}
            if 'api_key' not in cols or 'key_id' not in cols:
                return 0   # the platform-shaped table: hashes only
            active = ", is_active = 0" if 'is_active' in cols else ""
            # key_id keeps the value unique where the column is UNIQUE.
            # db-audit: ignore[DBW001] - fragment is a literal chosen from PRAGMA output
            n = conn.execute(f"UPDATE api_keys SET api_key = 'retired:' || key_id{active} "
                             "WHERE api_key IS NOT NULL AND api_key NOT LIKE 'retired:%'").rowcount
            conn.commit()
            return n
        finally:
            conn.close()

    def api_keys_management(self):
        """Manage Document Manager API keys (hashed at rest, shown once)."""
        print("\n🔑 API KEYS MANAGEMENT")

        try:
            retired = self._retire_plaintext_keys()
            if retired:
                print(f"\n⚠️  {retired} old plain-text API key(s) were retired and can no longer be used.")
            manager = self._key_manager()
        except Exception as e:
            print(f"The API key store could not be opened: {e}")
            return

        def document_keys():
            return [k for k in manager.list_keys()
                    if str(k["label"]).startswith(self.DOCUMENT_KEY_PREFIX)]

        print("\n1. List API Keys")
        print("2. Generate New API Key")
        print("3. Revoke API Key")
        print("4. Return to Main Menu")

        choice = input("\nChoose option (1-4): ").strip()

        try:
            if choice == '1':
                keys = document_keys()
                if not keys:
                    print("\nNo API keys found.")
                else:
                    print("\nAPI Keys:")
                    for key in keys:
                        status = "Active" if key["active"] else "Revoked"
                        name = key["label"][len(self.DOCUMENT_KEY_PREFIX):]
                        print(f"  {key['id']}. {name}: {key['prefix']}... ({status}) - "
                              f"Created: {(key['created_at'] or '')[:10]}")

            elif choice == '2':
                key_name = input("API key name/description: ").strip()
                if not key_name:
                    print("A name is required.")
                    return
                expiry_days = input("Valid for how many days? (default 365): ").strip()
                try:
                    expiry_days = int(expiry_days) if expiry_days else 365
                except ValueError:
                    print("Enter a whole number of days.")
                    return
                if expiry_days <= 0:
                    print("Enter a positive number of days.")
                    return

                raw_key = manager.create_key(self.DOCUMENT_KEY_PREFIX + key_name,
                                             systems=["university"], expires_in_days=expiry_days)
                expiry_date = (datetime.now() + timedelta(days=expiry_days)).strftime('%Y-%m-%d')

                print("\n✅ API Key Generated:")
                print(f"Name: {key_name}")
                print(f"Key: {raw_key}")
                print(f"Expires: {expiry_date}")
                print("\n⚠️  Save this key securely - only its hash is stored, it won't be shown again!")
                print("Note: no Document Manager endpoint accepts API keys yet.")

            elif choice == '3':
                key_id = input("Enter API key ID to revoke: ").strip()
                ids = {str(k["id"]) for k in document_keys()}
                if key_id not in ids:
                    print("No Document Manager API key with that ID.")
                elif manager.revoke_key(int(key_id)):
                    print("✅ API key revoked.")
                else:
                    print("That key was already revoked.")
        except Exception as e:
            print(f"API key operation failed: {e}")

    def api_usage_statistics(self):
        """View API usage statistics"""
        print("\n📊 API USAGE STATISTICS")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Check if we have API usage logs
            cursor.execute('''
            SELECT COUNT(*) FROM audit_log WHERE action LIKE 'API%'
            ''')

            api_log_count = cursor.fetchone()[0]

            if api_log_count == 0:
                print("\nNo API usage logs found.")
                print("API usage tracking requires proper logging setup.")
                conn.close()
                return

            days = input("View statistics for how many days? (default 30): ").strip()
            days = int(days) if days else 30

            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            # API calls by date
            cursor.execute('''
            SELECT date(timestamp) as call_date, COUNT(*) as call_count
            FROM audit_log
            WHERE action LIKE 'API%' AND timestamp >= ?
            GROUP BY date(timestamp)
            ORDER BY call_date DESC
            ''', (cutoff_date,))

            daily_stats = cursor.fetchall()

            print(f"\nAPI Calls by Date (Last {days} days):")
            for date, count in daily_stats:
                print(f"  {date}: {count} calls")

            # API calls by endpoint
            cursor.execute('''
            SELECT table_name, COUNT(*) as call_count
            FROM audit_log
            WHERE action LIKE 'API%' AND timestamp >= ?
            GROUP BY table_name
            ORDER BY call_count DESC
            ''', (cutoff_date,))

            endpoint_stats = cursor.fetchall()

            print("\nAPI Calls by Endpoint:")
            for endpoint, count in endpoint_stats:
                print(f"  {endpoint}: {count} calls")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")
