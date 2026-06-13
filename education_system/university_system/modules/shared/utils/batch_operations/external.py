import csv
import json
import datetime
from typing import Dict, List

import pandas as pd
import requests

from education_system.university_system.infrastructure.logging.log_config import configure_logging
from education_system.university_system.core.i18n import get_text as _t

logger = configure_logging(name=__name__)


class ExternalMixin:
    """Mixin providing external system integration methods."""

    def external_system_integration(self):
        """Integration with external systems"""
        print("\n" + _t("shared.utils.batch_operations.title_external_integration"))

        print(_t("shared.utils.batch_operations.integration_options"))
        print(_t("shared.utils.batch_operations.option_database_connection"))
        print(_t("shared.utils.batch_operations.option_rest_api"))
        print(_t("shared.utils.batch_operations.option_file_share"))
        print(_t("shared.utils.batch_operations.option_export_external"))

        choice = input(_t("shared.utils.batch_operations.prompt_choose_integration"))

        if choice == '1':
            self.setup_database_integration()
        elif choice == '2':
            self.setup_rest_api_integration()
        elif choice == '3':
            self.setup_file_share_monitoring()
        elif choice == '4':
            self.export_to_external_system()
        else:
            print(_t("shared.utils.batch_operations.invalid_choice"))

    def setup_database_integration(self):
        """Set up external database integration"""
        print(_t("batch_ops.external.db_integration_title"))

        db_type = input(_t("batch_ops.external.prompt_db_type")).lower()
        if db_type not in ['mysql', 'postgresql']:
            print(_t("batch_ops.external.error_db_type_unsupported"))
            return

        host = input(_t("batch_ops.external.prompt_db_host"))
        port = input(_t("batch_ops.external.prompt_db_port"))
        database = input(_t("batch_ops.external.prompt_db_name"))
        username = input(_t("batch_ops.external.prompt_username"))
        password = input(_t("batch_ops.external.prompt_password"))

        # Store connection config (in production, use secure storage)
        config = {
            'type': db_type,
            'host': host,
            'port': port,
            'database': database,
            'username': username,
            'password': password
        }

        # Test connection
        try:
            if db_type == 'mysql':
                import mysql.connector
                conn = mysql.connector.connect(**{
                    'host': host,
                    'port': port,
                    'database': database,
                    'user': username,
                    'password': password
                })
                conn.close()
            elif db_type == 'postgresql':
                import psycopg2
                conn = psycopg2.connect(
                    host=host, port=port, database=database,
                    user=username, password=password
                )
                conn.close()

            print(_t("batch_ops.external.db_connection_success"))

            # Save config
            with open('external_db_config.json', 'w') as f:
                json.dump(config, f, indent=2)

        except Exception as e:
            print(_t("batch_ops.external.db_connection_failed", error=str(e)))

    def setup_rest_api_integration(self):
        """Set up REST API integration"""
        print(_t("batch_ops.external.api_integration_title"))

        api_url = input(_t("batch_ops.external.prompt_api_url"))
        api_key = input(_t("batch_ops.external.prompt_api_key"))

        # Test API connection
        try:
            headers = {}
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'

            response = requests.get(f"{api_url}/health", headers=headers, timeout=10)

            if response.status_code == 200:
                print(_t("batch_ops.external.api_connection_success"))

                # Save config
                config = {
                    'url': api_url,
                    'api_key': api_key,
                    'headers': headers
                }

                with open('external_api_config.json', 'w') as f:
                    json.dump(config, f, indent=2)
            else:
                print(_t("batch_ops.external.api_connection_failed_status", status=response.status_code))

        except requests.RequestException as e:
            print(_t("batch_ops.external.api_connection_failed", error=str(e)))

    def setup_file_share_monitoring(self):
        """Set up file share monitoring"""
        print(_t("batch_ops.external.file_share_title"))
        print(_t("batch_ops.external.ftp_setup_title"))
        host = input(_t("batch_ops.external.prompt_ftp_host"))
        username = input(_t("batch_ops.external.prompt_ftp_username"))
        remote_path = input(_t("batch_ops.external.prompt_ftp_path"))
        print(_t("batch_ops.external.monitoring_setup_success", host=host, path=remote_path))
        print(_t("batch_ops.external.monitoring_interval"))

        # This would implement file share monitoring
        # - Connect to FTP/SFTP servers
        # - Monitor for new files
        # - Automatically download and process
        # - Move processed files to archive

    def export_to_external_system(self):
        """Export data to external systems"""
        print(_t("batch_ops.external.export_title"))

        print(_t("batch_ops.external.export_targets"))
        print(_t("batch_ops.external.option_database"))
        print(_t("batch_ops.external.option_api"))
        print(_t("batch_ops.external.option_file_share"))
        print(_t("batch_ops.external.option_email"))

        choice = input(_t("batch_ops.external.prompt_export_target"))

        if choice == '1':
            self.export_to_external_database()
        elif choice == '2':
            self.export_via_rest_api()
        elif choice == '3':
            self.export_to_file_share()
        elif choice == '4':
            self.export_via_email()
        else:
            print(_t("batch_ops.external.error_invalid_choice"))

    def export_to_external_database(self):
        """Export data to external database"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        print(_t("batch_ops.external.export_db_title"))

        try:
            with open('external_db_config.json', 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            print(_t("batch_ops.external.error_db_not_configured"))
            return

        # Get data to export
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM students")
            students = cursor.fetchall()
        finally:
            conn.close()

        print(_t("batch_ops.external.exporting_records", count=len(students)))

        # This would implement the actual export logic
        # based on the configured database type
        print(_t("batch_ops.external.export_config_title"))
        format_type = input(_t("batch_ops.external.prompt_export_format"))
        output_path = input(_t("batch_ops.external.prompt_output_path"))
        print(_t("batch_ops.external.export_config_saved"))
        print(_t("batch_ops.external.export_config_summary", format=format_type, output=output_path))

    def export_via_rest_api(self):
        """Export data via REST API"""
        print(_t("batch_ops.external.export_api_title"))

        try:
            with open('external_api_config.json', 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            print(_t("batch_ops.external.error_api_not_configured"))
            return

        # Implementation would send data to external API
        print(_t("batch_ops.external.api_export_setup_title"))
        api_url = input(_t("batch_ops.external.prompt_api_endpoint"))
        api_key = input(_t("batch_ops.external.prompt_api_key_export"))
        print(_t("batch_ops.external.api_export_configured", url=api_url))

    def export_to_file_share(self):
        """Export to file share"""
        print(_t("batch_ops.external.export_file_share_title"))
        print(_t("batch_ops.external.file_share_setup_title"))
        share_path = input(_t("batch_ops.external.prompt_share_path"))
        print(_t("batch_ops.external.file_share_configured", path=share_path))

    def export_via_email(self):
        """Export data via email"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        print(_t("batch_ops.external.export_email_title"))

        email_to = input(_t("batch_ops.external.prompt_recipient_email"))
        file_format = input(_t("batch_ops.external.prompt_email_format")).lower()

        if file_format not in ['csv', 'excel', 'json']:
            print(_t("batch_ops.external.error_invalid_format"))
            return

        # Export data to temporary file
        temp_filename = f"student_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM students")
            students = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            conn.close()

            if file_format == 'csv':
                temp_filename += '.csv'
                with open(temp_filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)
                    writer.writerows(students)
            elif file_format == 'excel':
                temp_filename += '.xlsx'
                df = pd.DataFrame(students, columns=columns)
                df.to_excel(temp_filename, index=False)
            elif file_format == 'json':
                temp_filename += '.json'
                data = [dict(zip(columns, student)) for student in students]
                with open(temp_filename, 'w') as f:
                    json.dump(data, f, indent=2, default=str)

            print(_t("batch_ops.external.export_file_created", filename=temp_filename))
            print(_t("batch_ops.external.email_would_send", email=email_to))

            # In production, this would integrate with email service

        except Exception as e:
            print(_t("batch_ops.external.export_failed", error=str(e)))
