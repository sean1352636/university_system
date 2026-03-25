"""System operations functions for the enhanced reporting GUI."""

from education_system.university_system.modules.shared.gui.enhanced_reporting.standalone.constants import (
    logging, os, json, datetime, timedelta, time,
    schedule, smtplib, threading,
    MIMEText, MIMEMultipart, MIMEBase, encoders,
    paths, get_db_connection,
    CONFIG, ENHANCED_AVAILABLE,
)


def run_system_maintenance():
    """Run comprehensive system maintenance"""
    try:
        maintenance_report = {
            'timestamp': datetime.now().isoformat(),
            'tasks_completed': [],
            'errors': []
        }

        # Clean old reports
        try:
            cleanup_old_reports()
            maintenance_report['tasks_completed'].append('Old reports cleaned')
        except Exception as e:
            maintenance_report['errors'].append(f'Report cleanup failed: {str(e)}')

        # Clear cache
        try:
            if ENHANCED_AVAILABLE:
                CacheManager.cleanup_cache()
            maintenance_report['tasks_completed'].append('Cache cleared')
        except Exception as e:
            maintenance_report['errors'].append(f'Cache cleanup failed: {str(e)}')

        # Run quality checks
        try:
            if ENHANCED_AVAILABLE:
                quality_report = DataQualityMonitor.run_quality_checks()
                maintenance_report['tasks_completed'].append('Data quality check completed')
                maintenance_report['quality_report'] = quality_report
        except Exception as e:
            maintenance_report['errors'].append(f'Quality check failed: {str(e)}')

        # Optimize database
        try:
            conn = get_db_connection()
            if conn:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
                conn.close()
                maintenance_report['tasks_completed'].append('Database optimized')
        except Exception as e:
            maintenance_report['errors'].append(f'Database optimization failed: {str(e)}')

        # Update statistics
        try:
            maintenance_report['system_stats'] = {
                'maintenance_completed': datetime.now().isoformat(),
                'tasks_successful': len(maintenance_report['tasks_completed']),
                'errors_encountered': len(maintenance_report['errors'])
            }
        except Exception as e:
            maintenance_report['errors'].append(f'Statistics update failed: {str(e)}')

        return maintenance_report

    except Exception as e:
        logging.error(f"System maintenance failed: {str(e)}")
        return {'error': str(e), 'timestamp': datetime.now().isoformat()}

def cleanup_old_reports(days_to_keep=30):
    """Clean up old report files"""
    try:
        reports_dir = CONFIG.get('reports_dir', 'reports') if ENHANCED_AVAILABLE else 'reports'

        if not os.path.exists(reports_dir):
            return

        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        deleted_count = 0

        for root, dirs, files in os.walk(reports_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_stat = os.stat(file_path)
                    file_date = datetime.fromtimestamp(file_stat.st_mtime)

                    if file_date < cutoff_date:
                        os.remove(file_path)
                        deleted_count += 1

                except Exception as e:
                    logging.warning(f"Could not process file {file_path}: {str(e)}")

        logging.info(f"Cleaned up {deleted_count} old report files")

    except Exception as e:
        logging.error(f"Error cleaning up old reports: {str(e)}")

def load_scheduled_reports():
    """Load scheduled reports from storage"""
    try:
        if not ENHANCED_AVAILABLE:
            return []

        schedules_file = os.path.join(CONFIG.get('reports_dir', str(paths.REPORTS_DIR)), 'scheduled_reports.json')

        if os.path.exists(schedules_file):
            with open(schedules_file, 'r') as f:
                return json.load(f)
        return []

    except Exception as e:
        logging.error(f"Error loading scheduled reports: {str(e)}")
        return []

def save_scheduled_reports(scheduled_reports):
    """Save scheduled reports to storage"""
    try:
        if not ENHANCED_AVAILABLE:
            return

        schedules_dir = CONFIG.get('reports_dir', str(paths.REPORTS_DIR))
        os.makedirs(schedules_dir, exist_ok=True)

        schedules_file = os.path.join(schedules_dir, 'scheduled_reports.json')

        with open(schedules_file, 'w') as f:
            json.dump(scheduled_reports, f, indent=4, default=str)

    except Exception as e:
        logging.error(f"Error saving scheduled reports: {str(e)}")

def start_scheduler():
    """Start the background scheduler for automated reports"""
    try:
        if not ENHANCED_AVAILABLE:
            return

        def run_scheduler():
            """Background scheduler function"""
            while True:
                try:
                    schedule.run_pending()
                    time.sleep(60)  # Check every minute
                except Exception as e:
                    logging.error(f"Scheduler error: {str(e)}")
                    time.sleep(300)  # Wait 5 minutes on error

        def schedule_report(report_data):
            """Schedule a specific report"""
            try:
                def run_report():
                    """Execute the scheduled report"""
                    try:
                        template_name = report_data['template_name']

                        # Generate date range
                        end_date = datetime.now().strftime("%Y-%m-%d")

                        # Default to 30 days if no specific range
                        days_back = report_data.get('date_range_days', 30)
                        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

                        # Generate report
                        if ENHANCED_AVAILABLE:
                            report_path = generate_report(template_name, start_date, end_date, 'pdf')

                            if report_path:
                                # Update last run time
                                report_data['last_run'] = datetime.now().isoformat()
                                report_data['run_count'] = report_data.get('run_count', 0) + 1

                                # Save updated schedule
                                scheduled_reports = load_scheduled_reports()
                                for i, existing in enumerate(scheduled_reports):
                                    if existing.get('template_name') == template_name:
                                        scheduled_reports[i] = report_data
                                        break
                                save_scheduled_reports(scheduled_reports)

                                # Send email if recipients specified
                                if report_data.get('recipients'):
                                    send_report_email(report_path, report_data['recipients'], template_name)

                                logging.info(f"Scheduled report '{template_name}' completed successfully")
                            else:
                                logging.error(f"Scheduled report '{template_name}' generation failed")

                    except Exception as e:
                        logging.error(f"Error running scheduled report: {str(e)}")

                # Schedule based on frequency
                config = report_data.get('schedule_config', {})
                frequency = config.get('frequency', 'weekly').lower()
                hour = config.get('hour', 9)

                if frequency == 'daily':
                    schedule.every().day.at(f"{hour:02d}:00").do(run_report)
                elif frequency == 'weekly':
                    schedule.every().monday.at(f"{hour:02d}:00").do(run_report)
                elif frequency == 'monthly':
                    schedule.every().month.at(f"{hour:02d}:00").do(run_report)

            except Exception as e:
                logging.error(f"Error scheduling report: {str(e)}")

        # Load and schedule all reports
        scheduled_reports = load_scheduled_reports()
        for report_data in scheduled_reports:
            if report_data.get('schedule_config', {}).get('enabled', True):
                schedule_report(report_data)

        # Start scheduler in background thread
        import threading
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()

        logging.info("Background scheduler started")

    except Exception as e:
        logging.error(f"Error starting scheduler: {str(e)}")

def send_report_email(report_path, recipients, template_name):
    """Send report via email to recipients"""
    try:
        from education_system.university_system.infrastructure.email.email_service import send_email
        from education_system.university_system.infrastructure.email.template_utils import render_template

        # Email body
        try:
            _, body = render_template("automated_report_delivery", {
                "template_name": template_name,
                "generated_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        except Exception:
            body = None

        if not body:
            body = f"""Dear Recipient,

Please find attached the automated report: {template_name}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This is an automated report from the University Management System.

Best regards,
University Reporting System"""

        # Prepare attachment - convert to comma-separated string
        attachments = report_path if os.path.exists(report_path) else None

        # Send to each recipient
        success_count = 0
        for recipient_email in recipients:
            try:
                success = send_email(
                    recipient_email=recipient_email,
                    subject=f"Automated Report: {template_name}",
                    body=body,
                    attachments=attachments
                )
                if success:
                    success_count += 1
            except Exception as e:
                logging.error(f"Failed to send to {recipient_email}: {str(e)}")

        if success_count > 0:
            logging.info(f"Report emailed to {success_count} of {len(recipients)} recipients")
        else:
            logging.error(f"Failed to email report to any recipients")

    except Exception as e:
        logging.error(f"Error sending report email: {str(e)}")
