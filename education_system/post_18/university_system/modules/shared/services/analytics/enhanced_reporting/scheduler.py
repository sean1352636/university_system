"""Scheduling, maintenance and system management."""

import os
import json
import time
import threading
from datetime import datetime, timedelta

from education_system.post_18.university_system.modules.shared.services.analytics.enhanced_reporting._compat import schedule
from education_system.post_18.university_system.modules.shared.services.analytics.enhanced_reporting.config import CONFIG, logger
from education_system.post_18.university_system.modules.shared.services.analytics.enhanced_reporting.cache import CacheManager
from education_system.post_18.university_system.modules.shared.services.analytics.enhanced_reporting.data_quality import DataQualityMonitor

try:
    from education_system.post_18.university_system.infrastructure.email.email_service import send_email
except ImportError:
    send_email = None


def run_system_maintenance():
    """Run system maintenance tasks"""
    logger.info("Running system maintenance...")

    # Clean up old report files
    cleanup_old_reports()

    # Clean up cache
    CacheManager.cleanup_cache()

    # Run data quality checks
    quality_report = DataQualityMonitor.run_quality_checks()

    # Log maintenance completion
    logger.info("System maintenance completed")

    return quality_report


def cleanup_old_reports(days_to_keep=30):
    """Clean up old report files"""
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)

    for root, dirs, files in os.walk(CONFIG['reports_dir']):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.getctime(file_path) < cutoff_date.timestamp():
                try:
                    os.remove(file_path)
                    logger.info(f"Removed old report file: {file}")
                except Exception as e:
                    logger.error(f"Error removing file {file}: {str(e)}")


def load_scheduled_reports():
    """Load scheduled reports from file"""
    try:
        with open(CONFIG['scheduled_reports_file'], 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_scheduled_reports(scheduled_reports):
    """Save scheduled reports to file"""
    with open(CONFIG['scheduled_reports_file'], 'w') as f:
        json.dump(scheduled_reports, f, indent=4)


def start_scheduler():
    """Start the background scheduler for automatic reports"""
    from education_system.post_18.university_system.modules.shared.services.analytics.enhanced_reporting.report_generation import generate_report

    def run_scheduler():
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Scheduler error: {str(e)}")
                time.sleep(60)

    # Load and schedule all reports
    def schedule_report(report_data):
        """Schedule a single report"""
        def run_report():
            try:
                template_name = report_data['template_name']
                recipients = report_data.get('recipients', [])

                # Generate report
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

                report_path = generate_report(template_name, start_date, end_date, 'pdf')

                if report_path:
                    # Update run statistics
                    report_data['last_run'] = datetime.now().isoformat()
                    report_data['run_count'] = report_data.get('run_count', 0) + 1

                    # Send email if recipients configured
                    if recipients:
                        from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
                        subject, body = render_template("scheduled_report", {
                            "template_name": template_name,
                            "generated_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            "start_date": start_date,
                            "end_date": end_date
                        })
                        if subject and body and send_email is not None:
                            for recipient in recipients:
                                send_email(recipient, subject, body, attachments=[report_path])

                    logger.info(f"Scheduled report '{template_name}' generated successfully")
                else:
                    logger.error(f"Failed to generate scheduled report '{template_name}'")

            except Exception as e:
                logger.error(f"Error running scheduled report '{template_name}': {str(e)}")

    # Schedule all reports
    scheduled_reports = load_scheduled_reports()
    for report_data in scheduled_reports:
        if not report_data['schedule_config'].get('enabled', True):
            continue

        frequency = report_data['schedule_config']['frequency']
        hour = report_data['schedule_config']['hour']

        if frequency == 'daily':
            schedule.every().day.at(f"{hour:02d}:00").do(lambda r=report_data: schedule_report(r))
        elif frequency == 'weekly':
            schedule.every().monday.at(f"{hour:02d}:00").do(lambda r=report_data: schedule_report(r))
        elif frequency == 'monthly':
            schedule.every().month.at(f"{hour:02d}:00").do(lambda r=report_data: schedule_report(r))

    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    logger.info(f"Background scheduler started with {len(scheduled_reports)} scheduled reports")
