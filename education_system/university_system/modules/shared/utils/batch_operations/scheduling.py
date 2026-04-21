import os
import shutil
import datetime
from pathlib import Path
from typing import List

import schedule

from education_system.university_system.infrastructure.logging.log_config import configure_logging
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

logger = configure_logging(name=__name__)


class SchedulingMixin:
    """Mixin providing scheduling/automation and notification methods."""

    def schedule_automated_imports(self):
        """Set up scheduled automated imports"""
        print("\n" + _t("shared.utils.batch_operations.title_schedule_imports"))

        print(_t("shared.utils.batch_operations.schedule_options"))
        print(_t("shared.utils.batch_operations.option_daily_import"))
        print(_t("shared.utils.batch_operations.option_weekly_import"))
        print(_t("shared.utils.batch_operations.option_custom_schedule"))
        print(_t("shared.utils.batch_operations.option_view_scheduled"))
        print(_t("shared.utils.batch_operations.option_cancel_scheduled"))

        choice = input(_t("shared.utils.batch_operations.prompt_choose_1_5"))

        if choice == '1':
            self.setup_daily_import()
        elif choice == '2':
            self.setup_weekly_import()
        elif choice == '3':
            self.setup_custom_schedule()
        elif choice == '4':
            self.view_scheduled_tasks()
        elif choice == '5':
            self.cancel_scheduled_task()
        else:
            print(_t("shared.utils.batch_operations.invalid_choice"))

    def setup_daily_import(self):
        """Set up daily automated import"""
        print("\n" + _t("shared.utils.batch_operations.title_setup_daily"))

        import_dir = input(_t("shared.utils.batch_operations.prompt_monitor_directory"))
        if not os.path.exists(import_dir):
            print(_t("shared.utils.batch_operations.error_directory_not_found"))
            return

        import_time = input(_t("shared.utils.batch_operations.prompt_import_time"))
        try:
            # Validate time format
            datetime.datetime.strptime(import_time, '%H:%M')
        except ValueError:
            print(_t("shared.utils.batch_operations.invalid_time_format"))
            return

        # Schedule the task
        schedule.every().day.at(import_time).do(self.automated_import_job, import_dir)

        print(_t("shared.utils.batch_operations.daily_import_scheduled", directory=import_dir, time=import_time))
        print(_t("shared.utils.batch_operations.schedule_note"))

    def setup_weekly_import(self):
        """Set up weekly automated import with notifications"""
        print("\n" + _t("shared.utils.batch_operations.title_setup_weekly"))

        import_dir = input(_t("shared.utils.batch_operations.prompt_monitor_directory"))
        if not os.path.exists(import_dir):
            print(_t("shared.utils.batch_operations.error_directory_not_found"))
            return

        day_of_week = input(_t("shared.utils.batch_operations.prompt_day_of_week")).lower()
        import_time = input(_t("shared.utils.batch_operations.prompt_time"))
        email = input(_t("shared.utils.batch_operations.prompt_notification_email"))

        try:
            datetime.datetime.strptime(import_time, '%H:%M')
        except ValueError:
            print(_t("shared.utils.batch_operations.invalid_time_format"))
            return

        # Schedule weekly task
        getattr(schedule.every(), day_of_week).at(import_time).do(
            self.automated_import_job, import_dir, email
        )

        print(_t("shared.utils.batch_operations.weekly_import_scheduled", day=day_of_week, time=import_time))

    def setup_custom_schedule(self):
        """Set up custom schedule using cron-like syntax"""
        print("\n" + _t("shared.utils.batch_operations.title_setup_custom"))
        print(_t("shared.utils.batch_operations.cron_instruction"))
        cron_expr = input(_t("shared.utils.batch_operations.prompt_cron_expression"))
        task_name = input(_t("shared.utils.batch_operations.prompt_task_name"))
        print(_t("shared.utils.batch_operations.custom_schedule_created", name=task_name))
        print(f"{_t('shared.utils.batch_operations.schedule')}: {cron_expr}")
        # This would integrate with more advanced scheduling libraries

    def view_scheduled_tasks(self):
        """View all scheduled tasks"""
        print("\n" + _t("shared.utils.batch_operations.title_scheduled_tasks"))

        jobs = schedule.get_jobs()
        if not jobs:
            print(_t("shared.utils.batch_operations.no_scheduled_tasks"))
            return

        for i, job in enumerate(jobs, 1):
            print(f"{i}. {job}")

    def cancel_scheduled_task(self):
        """Cancel a scheduled task"""
        print("\n" + _t("shared.utils.batch_operations.title_cancel_task"))

        jobs = schedule.get_jobs()
        if not jobs:
            print(_t("shared.utils.batch_operations.no_tasks_to_cancel"))
            return

        print(_t("shared.utils.batch_operations.scheduled_tasks"))
        for i, job in enumerate(jobs, 1):
            print(f"{i}. {job}")

        try:
            choice = int(input(_t("shared.utils.batch_operations.prompt_select_task"))) - 1
            if 0 <= choice < len(jobs):
                schedule.cancel_job(jobs[choice])
                print(_t("shared.utils.batch_operations.task_cancelled"))
            else:
                print(_t("shared.utils.batch_operations.invalid_selection"))
        except ValueError:
            print(_t("shared.utils.batch_operations.invalid_input"))

    def automated_import_job(self, import_dir: str, notification_email: str = None):
        """Automated import job function"""
        try:
            logger.info(f"Starting automated import from {import_dir}")

            # Find files to import
            files_to_import = []
            for ext in ['.csv', '.xlsx', '.xls']:
                files_to_import.extend(Path(import_dir).glob(f"*{ext}"))

            if not files_to_import:
                logger.info("No files found for automated import")
                return

            # Create backup
            backup_path = self.create_database_backup(auto=True)

            # Process files
            total_imported = 0
            total_errors = 0

            for file_path in files_to_import:
                try:
                    logger.info(f"Processing {file_path}")

                    if file_path.suffix.lower() == '.csv':
                        records = self.read_csv_file(str(file_path))
                    else:
                        records = self.read_excel_file(str(file_path))

                    if records:
                        result = self.import_valid_records(records)
                        total_imported += result.successful_imports
                        total_errors += result.failed_imports

                        # Move processed file to archive
                        archive_dir = Path(import_dir) / 'processed'
                        archive_dir.mkdir(exist_ok=True)
                        shutil.move(str(file_path), str(archive_dir / file_path.name))

                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    total_errors += 1

            # Send notification email if configured
            if notification_email:
                self.send_notification_email(
                    notification_email,
                    f"Automated Import Complete: {total_imported} imported, {total_errors} errors"
                )

            logger.info(f"Automated import complete: {total_imported} imported, {total_errors} errors")

        except Exception as e:
            logger.error(f"Error in automated import job: {e}")

    def send_notification_email(self, email: str, message: str):
        """Send notification email using SMTP or email service."""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        try:
            # Try to get email configuration from environment variables
            smtp_server = os.getenv('SMTP_SERVER', 'localhost')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_username = os.getenv('SMTP_USERNAME')
            smtp_password = os.getenv('SMTP_PASSWORD')
            from_email = os.getenv('FROM_EMAIL', 'noreply@university.edu')

            # Prepare template variables
            template_vars = {
                'message': message
            }

            # Try to use template
            from education_system.university_system.infrastructure.email.template_utils import render_template
            subject, body = render_template('batch_notification', template_vars)

            if not (subject and body):
                logger.warning(f"Failed to load email template for {email}; falling back to plain text message.")
                subject = "Batch Import Notification"
                body = message

            # Create message
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain'))

            # Use centralized email system
            try:
                from education_system.university_system.infrastructure.email.smtp import send_email_via_smtp
                from datetime import datetime as dt

                current_time = dt.now().isoformat()
                success = send_email_via_smtp(
                    recipient_email=email,
                    subject=subject,
                    body=body,
                    cc=None,
                    bcc=None,
                    attachments=None,
                    current_time=current_time
                )

                if success:
                    logger.info(f"Email notification sent successfully to {email}")
                    print(_t("shared.utils.batch_operations.email_sent", email=email))
                    return True
                else:
                    logger.warning(f"Email notification failed for {email}")
                    print(_t("shared.utils.batch_operations.email_failed", email=email))
                    return False

            except ImportError:
                # Fallback to logging if email system not available
                logger.info(f"Email notification (email system not available) to {email}: {message}")
                print(_t("shared.utils.batch_operations.email_would_be_sent", email=email, message=message))
                return False

        except Exception as e:
            logger.error(f"Failed to send email notification to {email}: {e}")
            print(_t("shared.utils.batch_operations.email_send_failed", email=email, error=str(e)))
            return False
