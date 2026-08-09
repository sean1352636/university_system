"""Extracted AcademicCalendarManager maintenance methods."""

from ._shared import *  # noqa: F401,F403


class MaintenanceMixin:
    def get_current_user_permissions(self):
        """Get current user's permissions for menu display"""
        try:
            if not self.auth_manager or not self.auth_manager.current_user:
                return set()

            # Get permissions from the main auth system
            from education_system.systems.university.infrastructure.auth import get_global_auth
            global_auth = get_global_auth()
            if global_auth and getattr(global_auth, "current_user", None):
                user_permissions = global_auth.current_user.get('permissions', [])
                return set(user_permissions)

            return set()

        except Exception as e:
            logger.warning(f"Could not get user permissions: {e}")
            return set()

    def verify_calendar_database_integrity(self):
        """Verify and repair calendar database integrity"""
        try:
            logger.info("Verifying calendar database integrity...")

            # Check for required tables
            required_tables = [
                'academic_years', 'semesters', 'academic_calendar_events', 'event_categories'
            ]

            from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
            missing_tables = []
            for table in required_tables:
                try:
                    safe_table = validate_identifier(table, "table")
                    self.db_manager.execute_query("SELECT COUNT(*) FROM [" + safe_table + "] LIMIT 1")
                except Exception:
                    missing_tables.append(table)

            if missing_tables:
                logger.warning(f"Missing tables detected: {missing_tables}")
                self._create_minimal_tables()
                logger.info("Created missing tables")

            # Check for data consistency
            self._check_data_consistency()

            logger.info("Database integrity verification completed")
            return True

        except Exception as e:
            logger.error(f"Database integrity check failed: {e}")
            return False

    def _check_data_consistency(self):
        """Check for data consistency issues"""
        try:
            # Check for orphaned events (events without valid academic year context)
            orphaned_events = self.db_manager.execute_query('''
                SELECT COUNT(*) as count FROM academic_calendar_events e
                WHERE e.date_start IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM semesters s
                    WHERE e.date_start BETWEEN s.start_date AND s.end_date
                )
            ''')

            if orphaned_events and orphaned_events[0]['count'] > 0:
                logger.warning(f"Found {orphaned_events[0]['count']} orphaned events")

            # Check for invalid date ranges
            invalid_ranges = self.db_manager.execute_query('''
                SELECT COUNT(*) as count FROM academic_calendar_events
                WHERE date_start IS NOT NULL AND date_end IS NOT NULL
                AND date_start > date_end
            ''')

            if invalid_ranges and invalid_ranges[0]['count'] > 0:
                logger.warning(f"Found {invalid_ranges[0]['count']} events with invalid date ranges")

        except Exception as e:
            logger.warning(f"Data consistency check had issues: {e}")

    def get_system_stats(self):
        """Get system statistics for dashboard"""
        try:
            stats = {}

            # Count events by type
            event_counts = self.db_manager.execute_query('''
                SELECT event_type, COUNT(*) as count
                FROM academic_calendar_events
                GROUP BY event_type
            ''')
            stats['events_by_type'] = {row['event_type']: row['count'] for row in event_counts}

            # Count total academic years
            year_count = self.db_manager.execute_query('SELECT COUNT(*) as count FROM academic_years')
            stats['total_academic_years'] = year_count[0]['count'] if year_count else 0

            # Count total semesters
            semester_count = self.db_manager.execute_query('SELECT COUNT(*) as count FROM semesters')
            stats['total_semesters'] = semester_count[0]['count'] if semester_count else 0

            # Get current academic period
            current_year = self.get_current_academic_year()
            current_semester = self.get_current_semester()

            stats['current_academic_year'] = current_year['id'] if current_year else 'None'
            stats['current_semester'] = current_semester['name'] if current_semester else 'None'

            # Count upcoming events (next 30 days)
            future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            current_date = datetime.now().strftime("%Y-%m-%d")

            upcoming_events = self.db_manager.execute_query('''
                SELECT COUNT(*) as count FROM academic_calendar_events
                WHERE COALESCE(date, date_start) BETWEEN ? AND ?
            ''', (current_date, future_date))

            stats['upcoming_events'] = upcoming_events[0]['count'] if upcoming_events else 0

            return stats

        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}

    def cleanup_old_data(self, days_old=365):
        """Clean up old data to maintain database performance"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions for data cleanup")

        try:
            cutoff_date = (datetime.now() - timedelta(days=days_old)).strftime("%Y-%m-%d")

            # Clean up old events
            old_events = self.db_manager.execute_update('''
                DELETE FROM academic_calendar_events
                WHERE COALESCE(date, date_end) < ?
                AND event_type NOT IN ('Holiday', 'Academic')
            ''', (cutoff_date,))

            # Clean up old notifications
            old_notifications = self.db_manager.execute_update('''
                DELETE FROM notification_queue
                WHERE scheduled_time < ? AND status IN ('sent', 'failed')
            ''', (cutoff_date,))

            # Clean up old audit logs (keep important ones)
            old_audit = self.db_manager.execute_update('''
                DELETE FROM audit_log
                WHERE timestamp < ? AND action NOT IN ('DELETE', 'CREATE')
            ''', (cutoff_date,))

            logger.info(f"Cleanup completed: {old_events} events, {old_notifications} notifications, {old_audit} audit logs")

            return {
                'success': True,
                'cleaned_events': old_events,
                'cleaned_notifications': old_notifications,
                'cleaned_audit_logs': old_audit
            }

        except Exception as e:
            logger.error(f"Data cleanup failed: {e}")
            return {'success': False, 'error': str(e)}

    def export_system_configuration(self):
        """Export system configuration for backup/migration"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions to export configuration")

        try:
            config_data = {
                'academic_years': [],
                'semesters': [],
                'event_categories': [],
                'export_timestamp': datetime.now().isoformat(),
                'system_version': '1.0'
            }

            # Export academic years
            years = self.db_manager.execute_query('SELECT * FROM academic_years ORDER BY start_date')
            config_data['academic_years'] = [dict(row) for row in years]

            # Export semesters
            semesters = self.db_manager.execute_query('SELECT * FROM semesters ORDER BY academic_year_id, start_date')
            config_data['semesters'] = [dict(row) for row in semesters]

            # Export event categories
            categories = self.db_manager.execute_query('SELECT * FROM event_categories ORDER BY name')
            config_data['event_categories'] = [dict(row) for row in categories]

            return config_data

        except Exception as e:
            logger.error(f"Configuration export failed: {e}")
            raise CalendarError(f"Configuration export failed: {e}")

    def import_system_configuration(self, config_data):
        """Import system configuration from backup"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions to import configuration")

        try:
            imported_counts = {'academic_years': 0, 'semesters': 0, 'event_categories': 0}

            with self.db_manager.transaction():
                # Import academic years
                for year_data in config_data.get('academic_years', []):
                    try:
                        self.db_manager.execute_update('''
                            INSERT OR IGNORE INTO academic_years (id, start_date, end_date, date_added)
                            VALUES (?, ?, ?, ?)
                        ''', (year_data['id'], year_data['start_date'], year_data['end_date'], year_data['date_added']))
                        imported_counts['academic_years'] += 1
                    except Exception as e:
                        logger.warning(f"Failed to import academic year {year_data.get('id')}: {e}")

                # Import semesters
                for semester_data in config_data.get('semesters', []):
                    try:
                        self.db_manager.execute_update('''
                            INSERT OR IGNORE INTO semesters (academic_year_id, name, start_date, end_date, date_added)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (semester_data['academic_year_id'], semester_data['name'],
                             semester_data['start_date'], semester_data['end_date'], semester_data['date_added']))
                        imported_counts['semesters'] += 1
                    except Exception as e:
                        logger.warning(f"Failed to import semester {semester_data.get('name')}: {e}")

                # Import event categories
                for category_data in config_data.get('event_categories', []):
                    try:
                        self.db_manager.execute_update('''
                            INSERT OR IGNORE INTO event_categories (name, color_code, description, date_added)
                            VALUES (?, ?, ?, ?)
                        ''', (category_data['name'], category_data.get('color_code'),
                             category_data.get('description'), category_data['date_added']))
                        imported_counts['event_categories'] += 1
                    except Exception as e:
                        logger.warning(f"Failed to import category {category_data.get('name')}: {e}")

            logger.info(f"Configuration import completed: {imported_counts}")
            return {'success': True, 'imported': imported_counts}

        except Exception as e:
            logger.error(f"Configuration import failed: {e}")
            return {'success': False, 'error': str(e)}
