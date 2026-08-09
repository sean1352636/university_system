import csv
import json
import datetime
from typing import Dict, List
from pathlib import Path
import shutil
import re
import threading
import time

import requests

from education_system.systems.university.infrastructure.logging.log_config import configure_logging
from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = configure_logging(name=__name__)


def export_rows_to_database(config, columns, rows):
    """Write rows through a configured SQLite, PostgreSQL or MySQL adapter."""
    db_type = str(config.get('type', '')).lower()
    table = config.get('table', 'students')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', table):
        raise ValueError("Invalid destination table name")
    safe_columns = [column for column in columns
                    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', column)]
    if len(safe_columns) != len(columns):
        raise ValueError("Invalid destination column name")
    if db_type == 'sqlite':
        import sqlite3
        connection = sqlite3.connect(config['path'])
        placeholder = '?'
    elif db_type == 'postgresql':
        import psycopg2
        connection = psycopg2.connect(host=config['host'], port=config.get('port', 5432),
                                      dbname=config['database'], user=config['username'],
                                      password=config['password'])
        placeholder = '%s'
    elif db_type == 'mysql':
        import mysql.connector
        connection = mysql.connector.connect(host=config['host'], port=config.get('port', 3306),
                                             database=config['database'], user=config['username'],
                                             password=config['password'])
        placeholder = '%s'
    else:
        raise ValueError(f"Unsupported external database type: {db_type}")
    try:
        cursor = connection.cursor()
        definitions = ', '.join(f'{column} TEXT' for column in safe_columns)
        cursor.execute(f"CREATE TABLE IF NOT EXISTS {table} ({definitions})")
        values_sql = ', '.join(placeholder for _ in safe_columns)
        cursor.executemany(
            f"INSERT INTO {table} ({', '.join(safe_columns)}) VALUES ({values_sql})",
            rows,
        )
        connection.commit()
        return len(rows)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def poll_file_share(config, destination):
    """Fetch matching local or SFTP files into a controlled inbox."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    pattern = config.get('pattern', '*.csv')
    downloaded = []
    if config.get('type', 'local') == 'local':
        source = Path(config['path'])
        if not source.is_dir():
            raise FileNotFoundError(source)
        for item in source.glob(pattern):
            if item.is_file():
                target = destination / item.name
                shutil.copy2(item, target)
                downloaded.append(str(target))
        return downloaded
    if config.get('type') == 'sftp':
        import fnmatch
        import paramiko
        transport = paramiko.Transport((config['host'], int(config.get('port', 22))))
        try:
            transport.connect(username=config['username'], password=config.get('password'),
                              pkey=config.get('pkey'))
            client = paramiko.SFTPClient.from_transport(transport)
            remote = config.get('remote_path', '.')
            for name in client.listdir(remote):
                if fnmatch.fnmatch(name, pattern):
                    target = destination / Path(name).name
                    client.get(f"{remote.rstrip('/')}/{name}", str(target))
                    downloaded.append(str(target))
            client.close()
        finally:
            transport.close()
        return downloaded
    raise ValueError("File share type must be local or sftp")


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
        share_type = input("Share type (local/sftp): ").strip().lower() or 'local'
        pattern = input("File pattern [*.csv]: ").strip() or '*.csv'
        interval = max(5, int(input("Polling interval in seconds [300]: ").strip() or '300'))
        if share_type == 'local':
            config = {'type': 'local', 'path': input("Directory path: ").strip(),
                      'pattern': pattern}
        elif share_type == 'sftp':
            config = {
                'type': 'sftp', 'host': input("SFTP host: ").strip(),
                'port': int(input("Port [22]: ").strip() or '22'),
                'username': input("Username: ").strip(),
                'password': input("Password: "),
                'remote_path': input("Remote path: ").strip() or '.',
                'pattern': pattern,
            }
        else:
            print("Unsupported share type.")
            return []
        from education_system import paths
        config_path = Path(paths.UNIVERSITY_DATA_DIR) / 'batch_file_share.json'
        config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
        inbox = Path(paths.UNIVERSITY_DATA_DIR) / 'batch_import_inbox'
        files = poll_file_share(config, inbox)
        if files:
            # The existing automated importer performs validation, creates a
            # database backup, and archives successful files under processed/.
            self.automated_import_job(str(inbox))
        stop_event = getattr(self, '_file_share_monitor_stop', None)
        if stop_event is not None:
            stop_event.set()
        self._file_share_monitor_stop = threading.Event()

        def monitor():
            while not self._file_share_monitor_stop.wait(interval):
                try:
                    fetched = poll_file_share(config, inbox)
                    if fetched:
                        self.automated_import_job(str(inbox))
                except Exception as exc:
                    logger.error("File-share monitor failed: %s", exc)

        self._file_share_monitor_thread = threading.Thread(
            target=monitor, name='batch-file-share-monitor', daemon=True
        )
        self._file_share_monitor_thread.start()
        print(f"Monitoring configured; fetched {len(files)} matching file(s).")
        return files

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
        from education_system.systems.university.infrastructure.database.db import sqlite3
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
            columns = [description[0] for description in cursor.description]
        finally:
            conn.close()

        print(_t("batch_ops.external.exporting_records", count=len(students)))

        count = export_rows_to_database(config, columns, students)
        print(f"Exported {count} record(s) to the configured {config.get('type')} database.")
        return count

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
        import pandas as pd
        from education_system.systems.university.infrastructure.database.db import sqlite3
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
