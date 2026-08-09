from education_system.systems.university.infrastructure.utils.document_manager._common import (
    datetime, timedelta, sqlite3,
    get_connection, _t,
    EMAIL_SYSTEM_AVAILABLE,
)


class SettingsMixin:
    def system_settings(self):
        """System settings management"""
        print("\n⚙️ SYSTEM SETTINGS")
        print("1. View Current Settings")
        print("2. Backup Settings")
        print("3. Security Settings")
        print("4. Email Configuration")
        print("5. OCR Settings")
        print("6. Web Interface Settings")
        print("7. Return to Main Menu")

        choice = input("\nChoose option (1-7): ").strip()

        if choice == '1':
            self.view_current_settings()
        elif choice == '2':
            self.backup_settings()
        elif choice == '3':
            self.security_settings()
        elif choice == '4':
            self.email_configuration()
        elif choice == '5':
            self.ocr_settings()
        elif choice == '6':
            self.web_interface_settings()

    def view_current_settings(self):
        """View current system settings"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT setting_name, setting_value, description, updated_date
            FROM system_settings
            ORDER BY setting_name
            ''')

            settings = cursor.fetchall()

            print("\n⚙️ SYSTEM SETTINGS")
            print("=" * 80)

            if not settings:
                print("No settings found.")
                conn.close()
                return

            for setting_name, setting_value, description, updated_date in settings:
                # Mask sensitive values
                display_value = '***' if 'password' in setting_name.lower() or 'secret' in setting_name.lower() else setting_value
                print(f"\n{setting_name}: {display_value}")
                if description:
                    print(f"  Description: {description}")
                if updated_date:
                    print(f"  Last Updated: {updated_date}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def email_settings(self):
        """Configure email settings - delegates to email manager"""
        print("\n📧 EMAIL SETTINGS")

        if not EMAIL_SYSTEM_AVAILABLE:
            print("❌ Email system is not available.")
            print("Please ensure the email infrastructure is properly installed.")
            return

        print("\nEmail settings are managed by the centralized email system.")
        print("To configure email settings:")
        print("1. Navigate to: university_system/infrastructure/email/")
        print("2. Run the email manager configuration")
        print("3. Or use the main system settings menu")

        view_current = input("\nView current email configuration? (y/n): ").strip().lower()

        if view_current == 'y':
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT setting_name, setting_value, description
                FROM system_settings
                WHERE setting_name LIKE '%email%' OR setting_name LIKE '%smtp%'
                   OR setting_name LIKE '%notification%'
                ORDER BY setting_name
                ''')

                settings = cursor.fetchall()

                if settings:
                    print("\nCurrent Email-Related Settings:")
                    for name, value, desc in settings:
                        # Mask password if present
                        display_value = '***' if 'password' in name.lower() else value
                        print(f"  {name}: {display_value}")
                        if desc:
                            print(f"    ({desc})")
                else:
                    print("\nNo email settings found in system_settings table.")

                conn.close()

            except sqlite3.Error as e:
                print(f"Database error: {e}")

    def email_configuration(self):
        """Alias for email_settings"""
        self.email_settings()

    def backup_settings(self):
        """Configure backup settings"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n💾 BACKUP SETTINGS")

            # Get current settings
            cursor.execute('''
            SELECT setting_name, setting_value
            FROM system_settings
            WHERE setting_name LIKE '%backup%'
            ''')

            current_settings = dict(cursor.fetchall())

            print("\nCurrent Backup Settings:")
            for key, value in current_settings.items():
                print(f"  {key}: {value}")

            print("\nModify Settings:")

            auto_backup = input(f"Enable automatic backups? (y/n) [{current_settings.get('auto_backup_enabled', 'false')}]: ").strip().lower()
            if auto_backup:
                new_value = 'true' if auto_backup == 'y' else 'false'
                cursor.execute('''
                UPDATE system_settings SET setting_value = ?, updated_date = ?
                WHERE setting_name = 'auto_backup_enabled'
                ''', (new_value, datetime.now().strftime('%Y-%m-%d')))

            frequency = input(f"Backup frequency (days) [{current_settings.get('backup_frequency_days', '7')}]: ").strip()
            if frequency:
                cursor.execute('''
                UPDATE system_settings SET setting_value = ?, updated_date = ?
                WHERE setting_name = 'backup_frequency_days'
                ''', (frequency, datetime.now().strftime('%Y-%m-%d')))

            retention = input("Backup retention period (days, default 30): ").strip()
            if retention:
                cursor.execute('''
                INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
                VALUES ('backup_retention_days', ?, 'Days to keep old backups', ?)
                ''', (retention, datetime.now().strftime('%Y-%m-%d')))

            conn.commit()
            conn.close()

            print("\n✅ Backup settings updated.")

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def security_settings(self):
        """Configure security settings"""
        print("\n🔒 SECURITY SETTINGS")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\nSecurity Configuration:")
            print("1. Password Policy")
            print("2. Session Timeout")
            print("3. Access Control")
            print("4. Audit Logging")
            print("5. File Upload Restrictions")
            print("6. View Access Logs")
            print("7. Return to Main Menu")

            choice = input("\nChoose option (1-7): ").strip()

            if choice == '1':
                print("\nPassword Policy Settings:")
                min_length = input("Minimum password length (default 8): ").strip() or "8"
                require_special = input("Require special characters? (y/n): ").strip().lower() == 'y'

                cursor.execute('''
                INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
                VALUES ('password_min_length', ?, 'Minimum password length', ?)
                ''', (min_length, datetime.now().strftime('%Y-%m-%d')))

                cursor.execute('''
                INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
                VALUES ('password_require_special', ?, 'Require special characters', ?)
                ''', ('true' if require_special else 'false', datetime.now().strftime('%Y-%m-%d')))

                conn.commit()
                print("✅ Password policy updated.")

            elif choice == '2':
                timeout = input("Session timeout (minutes, default 30): ").strip() or "30"
                cursor.execute('''
                INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
                VALUES ('session_timeout_minutes', ?, 'Session timeout in minutes', ?)
                ''', (timeout, datetime.now().strftime('%Y-%m-%d')))
                conn.commit()
                print("✅ Session timeout updated.")

            elif choice == '4':
                audit_enabled = input("Enable audit logging? (y/n): ").strip().lower() == 'y'
                cursor.execute('''
                INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
                VALUES ('audit_logging_enabled', ?, 'Enable audit trail logging', ?)
                ''', ('true' if audit_enabled else 'false', datetime.now().strftime('%Y-%m-%d')))
                conn.commit()
                print("✅ Audit logging setting updated.")

            elif choice == '5':
                max_size = input("Maximum file upload size (MB, default 50): ").strip() or "50"
                cursor.execute('''
                UPDATE system_settings SET setting_value = ?, updated_date = ?
                WHERE setting_name = 'max_file_size_mb'
                ''', (max_size, datetime.now().strftime('%Y-%m-%d')))
                conn.commit()
                print("✅ File upload restrictions updated.")

            elif choice == '6':
                self.view_access_logs()

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def view_access_logs(self):
        """View system access logs"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            days = input("View logs for how many days? (default 7): ").strip()
            days = int(days) if days else 7

            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            cursor.execute('''
            SELECT user_id, action, table_name, record_id, timestamp, ip_address
            FROM audit_log
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT 100
            ''', (cutoff_date,))

            logs = cursor.fetchall()

            print(f"\n🔍 ACCESS LOGS (Last {days} days)")
            print("=" * 80)

            if not logs:
                print("No logs found.")
                conn.close()
                return

            for log in logs:
                user, action, table, record, timestamp, ip = log
                print(f"\n{timestamp} | User: {user} | Action: {action}")
                print(f"  Table: {table} | Record: {record}")
                if ip:
                    print(f"  IP: {ip}")

            print(f"\n{'='*80}")
            print(f"Total Log Entries: {len(logs)}")

            # Summary by user
            cursor.execute('''
            SELECT user_id, COUNT(*) as action_count
            FROM audit_log
            WHERE timestamp >= ?
            GROUP BY user_id
            ORDER BY action_count DESC
            ''', (cutoff_date,))

            user_summary = cursor.fetchall()

            print("\nActivity by User:")
            for user, count in user_summary:
                print(f"  {user}: {count} actions")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def ocr_settings(self):
        """Configure OCR settings"""
        print("\n👁️  OCR SETTINGS")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\nOCR (Optical Character Recognition) Configuration:")

            ocr_enabled = input("Enable OCR processing? (y/n): ").strip().lower() == 'y'
            cursor.execute('''
            INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
            VALUES ('ocr_enabled', ?, 'Enable OCR text extraction', ?)
            ''', ('true' if ocr_enabled else 'false', datetime.now().strftime('%Y-%m-%d')))

            if ocr_enabled:
                print("\nOCR Engine Options:")
                print("1. Tesseract OCR (Open Source)")
                print("2. Google Cloud Vision API")
                print("3. AWS Textract")
                print("4. Azure Computer Vision")

                engine_choice = input("Select OCR engine (1-4): ").strip()

                engines = {
                    '1': 'tesseract',
                    '2': 'google_vision',
                    '3': 'aws_textract',
                    '4': 'azure_vision'
                }

                engine = engines.get(engine_choice, 'tesseract')

                cursor.execute('''
                INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
                VALUES ('ocr_engine', ?, 'OCR engine to use', ?)
                ''', (engine, datetime.now().strftime('%Y-%m-%d')))

                auto_ocr = input("Automatically OCR all uploaded documents? (y/n): ").strip().lower() == 'y'
                cursor.execute('''
                INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
                VALUES ('ocr_auto_process', ?, 'Automatically OCR uploaded documents', ?)
                ''', ('true' if auto_ocr else 'false', datetime.now().strftime('%Y-%m-%d')))

            conn.commit()
            conn.close()

            print("\n✅ OCR settings updated.")

            if ocr_enabled:
                print("\nNote: Ensure the selected OCR engine is properly installed and configured.")

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def web_interface_settings(self):
        """Configure web interface settings"""
        print("\n🌐 WEB INTERFACE SETTINGS")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\nWeb Interface Configuration:")

            port = input("Web server port (default 5000): ").strip() or "5000"
            cursor.execute('''
            INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
            VALUES ('web_interface_port', ?, 'Web interface port number', ?)
            ''', (port, datetime.now().strftime('%Y-%m-%d')))

            host = input("Host address (default 127.0.0.1): ").strip() or "127.0.0.1"
            cursor.execute('''
            INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
            VALUES ('web_interface_host', ?, 'Web interface host address', ?)
            ''', (host, datetime.now().strftime('%Y-%m-%d')))

            ssl_enabled = input("Enable SSL/HTTPS? (y/n): ").strip().lower() == 'y'
            cursor.execute('''
            INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
            VALUES ('web_interface_ssl', ?, 'Enable SSL for web interface', ?)
            ''', ('true' if ssl_enabled else 'false', datetime.now().strftime('%Y-%m-%d')))

            conn.commit()
            conn.close()

            print("\n✅ Web interface settings updated.")
            print(f"Access URL: http{'s' if ssl_enabled else ''}://{host}:{port}")

        except sqlite3.Error as e:
            print(f"Database error: {e}")
