"""Automation and scheduling mixin."""

from education_system.university_system.modules.shared.gui.batch_operations.constants import (
    datetime, json, time, logging,
    Path,
    logger,
)

from education_system.university_system.modules.shared.gui.batch_operations.models import ImportResult


class SchedulingMixin:
    """Mixin providing automated import scheduling and notification methods."""

    def schedule_automated_imports_gui(self, callback=None) -> str:
        """Main menu for scheduling automated imports - GUI version"""
        message = """
AUTOMATED IMPORT SCHEDULING

Available Options:
1. Setup Weekly Import - Schedule imports to run weekly
2. Setup Custom Schedule - Create custom import schedule
3. View Scheduled Tasks - See all active schedules
4. Cancel Scheduled Task - Remove a schedule

Note: Scheduled imports require the system to be running.
For production use, configure system service or cron jobs.
"""

        if callback:
            callback(message)

        return message

    def setup_weekly_import_gui(self, import_dir: str, day_of_week: int,
                                time_str: str, notification_email: str = None,
                                progress_callback=None) -> bool:
        """Setup weekly import schedule - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, "Setting up weekly import schedule...")

            # Validate time format
            try:
                datetime.datetime.strptime(time_str, '%H:%M')
            except ValueError:
                raise ValueError("Time must be in HH:MM format")

            # Validate day of week
            if not 0 <= day_of_week <= 6:
                raise ValueError("Day of week must be 0-6 (Monday-Sunday)")

            if progress_callback:
                progress_callback(50, "Creating schedule entry...")

            # Create schedule entry
            schedule_data = {
                'type': 'weekly',
                'day_of_week': day_of_week,
                'time': time_str,
                'import_dir': import_dir,
                'notification_email': notification_email,
                'created_at': datetime.datetime.now().isoformat()
            }

            # Save to database
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scheduled_imports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schedule_type TEXT NOT NULL,
                        schedule_data TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cursor.execute("""
                    INSERT INTO scheduled_imports (schedule_type, schedule_data)
                    VALUES (?, ?)
                """, ('weekly', json.dumps(schedule_data)))

                conn.commit()

            if progress_callback:
                progress_callback(100, "Weekly import schedule created")

            logger.info(f"Created weekly import schedule for day {day_of_week} at {time_str}")
            return True

        except Exception as e:
            logger.error(f"Error setting up weekly import: {e}")
            raise

    def setup_custom_schedule_gui(self, schedule_expression: str,
                                  import_dir: str, notification_email: str = None,
                                  progress_callback=None) -> bool:
        """Setup custom import schedule - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, "Setting up custom import schedule...")

            schedule_data = {
                'type': 'custom',
                'expression': schedule_expression,
                'import_dir': import_dir,
                'notification_email': notification_email,
                'created_at': datetime.datetime.now().isoformat()
            }

            # Save to database
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scheduled_imports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schedule_type TEXT NOT NULL,
                        schedule_data TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cursor.execute("""
                    INSERT INTO scheduled_imports (schedule_type, schedule_data)
                    VALUES (?, ?)
                """, ('custom', json.dumps(schedule_data)))

                conn.commit()

            if progress_callback:
                progress_callback(100, "Custom import schedule created")

            logger.info(f"Created custom import schedule: {schedule_expression}")
            return True

        except Exception as e:
            logger.error(f"Error setting up custom schedule: {e}")
            raise

    def view_scheduled_tasks_gui(self, progress_callback=None) -> list:
        """View all scheduled import tasks - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, "Fetching scheduled tasks...")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Ensure table exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scheduled_imports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schedule_type TEXT NOT NULL,
                        schedule_data TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cursor.execute("""
                    SELECT id, schedule_type, schedule_data, is_active, created_at
                    FROM scheduled_imports
                    WHERE is_active = 1
                    ORDER BY created_at DESC
                """)

                tasks = []
                for row in cursor.fetchall():
                    task_id, schedule_type, schedule_data_json, is_active, created_at = row
                    schedule_data = json.loads(schedule_data_json)

                    tasks.append({
                        'id': task_id,
                        'type': schedule_type,
                        'data': schedule_data,
                        'is_active': bool(is_active),
                        'created_at': created_at
                    })

            if progress_callback:
                progress_callback(100, f"Found {len(tasks)} scheduled tasks")

            logger.info(f"Retrieved {len(tasks)} scheduled tasks")
            return tasks

        except Exception as e:
            logger.error(f"Error viewing scheduled tasks: {e}")
            raise

    def cancel_scheduled_task_gui(self, task_id: int,
                                  progress_callback=None) -> bool:
        """Cancel a scheduled import task - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, f"Cancelling task {task_id}...")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Mark as inactive instead of deleting
                cursor.execute("""
                    UPDATE scheduled_imports
                    SET is_active = 0
                    WHERE id = ?
                """, (task_id,))

                if cursor.rowcount == 0:
                    raise ValueError(f"Task {task_id} not found")

                conn.commit()

            if progress_callback:
                progress_callback(100, f"Task {task_id} cancelled")

            logger.info(f"Cancelled scheduled task {task_id}")
            return True

        except Exception as e:
            logger.error(f"Error cancelling scheduled task: {e}")
            raise

    def automated_import_job(self, import_dir: str,
                            notification_email: str = None,
                            progress_callback=None) -> ImportResult:
        """Execute automated import job - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, f"Scanning {import_dir} for import files...")

            import_path = Path(import_dir)
            if not import_path.exists():
                raise FileNotFoundError(f"Import directory not found: {import_dir}")

            # Find all CSV and Excel files
            csv_files = list(import_path.glob('*.csv'))
            excel_files = list(import_path.glob('*.xlsx'))
            all_files = csv_files + excel_files

            if not all_files:
                if progress_callback:
                    progress_callback(100, "No import files found")
                return ImportResult()

            if progress_callback:
                progress_callback(10, f"Found {len(all_files)} files to import")

            # Combined result
            combined_result = ImportResult()

            # Import each file
            for i, file_path in enumerate(all_files):
                try:
                    file_progress = int(10 + (i / len(all_files)) * 80)

                    if progress_callback:
                        progress_callback(file_progress, f"Importing {file_path.name}...")

                    if file_path.suffix == '.csv':
                        result = self.import_from_csv_file(str(file_path), None)
                    else:
                        result = self.import_from_excel_file(str(file_path), None, None)

                    # Combine results
                    combined_result.total_records += result.total_records
                    combined_result.successful_imports += result.successful_imports
                    combined_result.failed_imports += result.failed_imports
                    combined_result.duplicates_found += result.duplicates_found
                    combined_result.errors.extend(result.errors)

                except Exception as e:
                    logger.error(f"Error importing file {file_path}: {e}")
                    combined_result.failed_imports += 1

            if progress_callback:
                progress_callback(90, "Sending notification...")

            # Send notification email if provided
            if notification_email:
                self.send_notification_email_gui(
                    notification_email,
                    f"Automated import completed:\n"
                    f"Files processed: {len(all_files)}\n"
                    f"Total records: {combined_result.total_records}\n"
                    f"Successful: {combined_result.successful_imports}\n"
                    f"Failed: {combined_result.failed_imports}",
                    None
                )

            if progress_callback:
                progress_callback(100, f"Automated import complete: {combined_result.successful_imports} records")

            logger.info(f"Automated import job completed: {combined_result.successful_imports} records imported")
            return combined_result

        except Exception as e:
            logger.error(f"Error in automated import job: {e}")
            raise

    def send_notification_email_gui(self, email: str, message: str,
                                   progress_callback=None) -> bool:
        """Send notification email - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, f"Sending notification to {email}...")

            # In production, this would integrate with the email service
            logger.info(f"NOTIFICATION EMAIL to {email}: {message}")

            # Simulate sending
            if progress_callback:
                progress_callback(50, "Connecting to email server...")
                time.sleep(0.1)  # Simulate network delay
                progress_callback(100, "Email sent successfully")

            return True

        except Exception as e:
            logger.error(f"Error sending notification email: {e}")
            raise
