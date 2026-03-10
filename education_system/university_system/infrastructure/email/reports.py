"""Reporting and analytics helpers for the email infrastructure."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta

from education_system.university_system.infrastructure.email.config import config
from education_system.university_system.infrastructure.email.email_db_utilities import execute_db_operation
from education_system.university_system.core.logs import handle_exception, log_event

# i18n support
try:
    from education_system.university_system.core.i18n import get_text as _t
except ImportError:
    def _t(key, **kwargs):
        return key


def _ensure_metrics_table(cursor):
    """Create the email_metrics table if the database does not have it yet."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_metrics'")
    if cursor.fetchone():
        return

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS email_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        sent_count INTEGER DEFAULT 0,
        failed_count INTEGER DEFAULT 0,
        opened_count INTEGER DEFAULT 0,
        clicked_count INTEGER DEFAULT 0
    )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_metrics_date ON email_metrics(date)')


@handle_exception
def log_email_metrics(status):
    """Log email metrics for reporting"""
    def _log_metrics(cursor):
        _ensure_metrics_table(cursor)
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Check if today's record exists
        cursor.execute('SELECT id FROM email_metrics WHERE date = ?', (today,))
        record = cursor.fetchone()
        
        if record:
            # Update existing record
            if status == 'sent':
                cursor.execute('UPDATE email_metrics SET sent_count = sent_count + 1 WHERE date = ?', (today,))
            elif status == 'failed':
                cursor.execute('UPDATE email_metrics SET failed_count = failed_count + 1 WHERE date = ?', (today,))
        else:
            # Create new record
            sent_count = 1 if status == 'sent' else 0
            failed_count = 1 if status == 'failed' else 0
            
            cursor.execute('''
            INSERT INTO email_metrics (date, sent_count, failed_count, opened_count, clicked_count)
            VALUES (?, ?, ?, ?, ?)
            ''', (today, sent_count, failed_count, 0, 0))
        
        return True
    
    try:
        return execute_db_operation(_log_metrics)
    except Exception as e:
        log_event('error', f"Error logging email metrics: {e}")
        return False



@handle_exception
def generate_report(start_date=None, end_date=None, output_format='json'):
    """Generate email metrics report for a date range"""
    def _generate_report(cursor):
        _ensure_metrics_table(cursor)
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        if not start_date:
            # Default to 30 days before end date
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            start_dt = end_dt - timedelta(days=30)
            start_date = start_dt.strftime('%Y-%m-%d')
        
        # Get metrics for date range
        cursor.execute('''
        SELECT date, sent_count, failed_count, opened_count, clicked_count
        FROM email_metrics
        WHERE date BETWEEN ? AND ?
        ORDER BY date
        ''', (start_date, end_date))
        
        records = cursor.fetchall()
        
        if not records:
            log_event('warning', f"No metrics found for date range {start_date} to {end_date}")
            return {'data': [], 'totals': {}}
        
        # Prepare report data
        report_data = []
        totals = {
            'sent': 0,
            'failed': 0,
            'opened': 0,
            'clicked': 0
        }
        
        for record in records:
            date, sent, failed, opened, clicked = record
            
            report_data.append({
                'date': date,
                'sent': sent,
                'failed': failed,
                'opened': opened,
                'clicked': clicked,
                'success_rate': (sent / (sent + failed)) * 100 if (sent + failed) > 0 else 0,
                'open_rate': (opened / sent) * 100 if sent > 0 else 0,
                'click_rate': (clicked / opened) * 100 if opened > 0 else 0
            })
            
            totals['sent'] += sent
            totals['failed'] += failed
            totals['opened'] += opened
            totals['clicked'] += clicked
        
        # Calculate overall rates
        if totals['sent'] + totals['failed'] > 0:
            totals['success_rate'] = (totals['sent'] / (totals['sent'] + totals['failed'])) * 100
        else:
            totals['success_rate'] = 0
        
        if totals['sent'] > 0:
            totals['open_rate'] = (totals['opened'] / totals['sent']) * 100
        else:
            totals['open_rate'] = 0
        
        if totals['opened'] > 0:
            totals['click_rate'] = (totals['clicked'] / totals['opened']) * 100
        else:
            totals['click_rate'] = 0
        
        return {
            'data': report_data,
            'totals': totals,
            'start_date': start_date,
            'end_date': end_date
        }
    
    try:
        report = execute_db_operation(_generate_report)
        
        # Generate report in requested format
        if output_format.lower() == 'csv':
            # Create CSV file
            csv_path = f"email_report_{report['start_date']}_to_{report['end_date']}.csv"
            
            with open(csv_path, 'w', newline='') as csvfile:
                fieldnames = ['date', 'sent', 'failed', 'opened', 'clicked', 'success_rate', 'open_rate', 'click_rate']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for row in report['data']:
                    writer.writerow(row)
                
                # Add totals row
                writer.writerow({
                    'date': 'TOTALS',
                    'sent': report['totals']['sent'],
                    'failed': report['totals']['failed'],
                    'opened': report['totals']['opened'],
                    'clicked': report['totals']['clicked'],
                    'success_rate': report['totals']['success_rate'],
                    'open_rate': report['totals']['open_rate'],
                    'click_rate': report['totals']['click_rate']
                })
            
            log_event('info', f"Email report generated as CSV: {csv_path}")
            return {'file_path': csv_path}
        else:
            # Return JSON data
            return report
            
    except Exception as e:
        log_event('error', f"Error generating report: {e}")
        return {'data': [], 'totals': {}}



@handle_exception
def generate_report_form():
    """Interactive form for generating email reports"""
    print(f"\n{_t('email.reports.generate_title')}")
    print(_t("email.reports.separator"))

    # Get date range
    today = datetime.now().strftime('%Y-%m-%d')

    print(f"\n{_t('email.reports.select_date_range')}:")
    print(f"1. {_t('email.reports.last_7_days')}")
    print(f"2. {_t('email.reports.last_30_days')}")
    print(f"3. {_t('email.reports.current_month')}")
    print(f"4. {_t('email.reports.custom_range')}")

    choice = input(_t("email.common.enter_choice") + " (1-4): ")
    
    end_date = today
    
    if choice == '1':
        # Last 7 days
        start_dt = datetime.now() - timedelta(days=7)
        start_date = start_dt.strftime('%Y-%m-%d')
    elif choice == '2':
        # Last 30 days
        start_dt = datetime.now() - timedelta(days=30)
        start_date = start_dt.strftime('%Y-%m-%d')
    elif choice == '3':
        # Current month
        now = datetime.now()
        start_date = f"{now.year}-{now.month:02d}-01"
    elif choice == '4':
        # Custom range
        try:
            start_year = int(input(_t("email.reports.start_year") + " (YYYY): "))
            start_month = int(input(_t("email.reports.start_month") + " (MM): "))
            start_day = int(input(_t("email.reports.start_day") + " (DD): "))

            start_dt = datetime(start_year, start_month, start_day)
            start_date = start_dt.strftime('%Y-%m-%d')

            end_year = int(input(_t("email.reports.end_year") + " (YYYY): "))
            end_month = int(input(_t("email.reports.end_month") + " (MM): "))
            end_day = int(input(_t("email.reports.end_day") + " (DD): "))

            end_dt = datetime(end_year, end_month, end_day)
            end_date = end_dt.strftime('%Y-%m-%d')

            if start_dt > end_dt:
                print(_t("email.reports.start_before_end"))
                return
        except ValueError:
            print(_t("email.reports.invalid_date"))
            return
    else:
        print(_t("email.common.invalid_choice"))
        return

    # Select output format
    print(f"\n{_t('email.reports.select_format')}:")
    print(f"1. {_t('email.reports.on_screen_json')}")
    print(f"2. {_t('email.reports.csv_file')}")

    format_choice = input(_t("email.common.enter_choice") + " (1-2): ")

    if format_choice == '1':
        output_format = 'json'
    elif format_choice == '2':
        output_format = 'csv'
    else:
        print(_t("email.reports.invalid_using_json"))
        output_format = 'json'
    
    # Generate the report
    report = generate_report(start_date, end_date, output_format)
    
    if output_format == 'json':
        # Display report on screen
        print(f"\n{_t('email.reports.report_for', start=start_date, end=end_date)}:")
        print(_t("email.reports.separator_long"))

        print(_t("email.reports.daily_metrics") + ":")
        print(f"{_t('email.reports.date'):<15}{_t('email.reports.sent'):<10}{_t('email.reports.failed'):<10}{_t('email.reports.success_rate'):<15}{_t('email.reports.opened'):<10}{_t('email.reports.clicked'):<10}")
        print(_t("email.reports.separator_dash"))

        for day in report['data']:
            print(f"{day['date']:<15}{day['sent']:<10}{day['failed']:<10}{day['success_rate']:.2f}%{day['opened']:<15}{day['clicked']:<10}")

        print(f"\n{_t('email.reports.total_metrics')}:")
        print(f"{_t('email.reports.total_sent')}: {report['totals']['sent']}")
        print(f"{_t('email.reports.total_failed')}: {report['totals']['failed']}")
        print(f"{_t('email.reports.overall_success_rate')}: {report['totals']['success_rate']:.2f}%")
        print(f"{_t('email.reports.total_opened')}: {report['totals']['opened']}")
        print(f"{_t('email.reports.total_clicked')}: {report['totals']['clicked']}")
        print(f"{_t('email.reports.overall_open_rate')}: {report['totals']['open_rate']:.2f}%")
        print(f"{_t('email.reports.overall_click_rate')}: {report['totals']['click_rate']:.2f}%")
    else:
        # CSV file was generated
        print(f"\n{_t('email.reports.report_saved', path=report['file_path'])}")

    input(f"\n{_t('email.common.press_enter')}...")



@handle_exception
def get_user_communication_stats(dashboard, user_id=None):
    """Get communication statistics for a user"""
    if not dashboard.auth or not dashboard.auth.current_user:
        return None
    
    target_user_id = user_id or dashboard.auth.current_user['id']
    
    def _get_stats(cursor):
        stats = {}
        
        # Message stats
        cursor.execute('''
        SELECT COUNT(*) FROM messages WHERE sender_id = ?
        ''', (target_user_id,))
        stats['messages_sent'] = cursor.fetchone()[0]
        
        cursor.execute('''
        SELECT COUNT(*) FROM messages WHERE recipient_id = ?
        ''', (target_user_id,))
        stats['messages_received'] = cursor.fetchone()[0]
        
        cursor.execute('''
        SELECT COUNT(*) FROM messages 
        WHERE recipient_id = ? AND is_read = 0
        ''', (target_user_id,))
        stats['unread_messages'] = cursor.fetchone()[0]
        
        # Announcement stats (if user can create them)
        cursor.execute('''
        SELECT COUNT(*) FROM announcements WHERE creator_id = ?
        ''', (target_user_id,))
        stats['announcements_created'] = cursor.fetchone()[0]
        
        # Chat room stats
        cursor.execute('''
        SELECT COUNT(*) FROM chat_room_members WHERE user_id = ?
        ''', (target_user_id,))
        stats['chat_rooms_joined'] = cursor.fetchone()[0]
        
        cursor.execute('''
        SELECT COUNT(*) FROM chat_rooms WHERE created_by = ?
        ''', (target_user_id,))
        stats['chat_rooms_created'] = cursor.fetchone()[0]
        
        return stats
    
    try:
        return execute_db_operation(_get_stats)
    except Exception as e:
        log_event('error', f"Error getting communication stats: {e}")
        return None



@handle_exception
def get_recent_communication_activity(dashboard, limit=10):
    """Get recent communication activity for the current user"""
    if not dashboard.auth or not dashboard.auth.current_user:
        return []
    
    user_id = dashboard.auth.current_user['id']
    
    def _get_activity(cursor):
        cursor.execute('''
        SELECT action_type, action_details, performed_at
        FROM communication_log
        WHERE user_id = ?
        ORDER BY performed_at DESC
        LIMIT ?
        ''', (user_id, limit))
        
        activities = []
        for row in cursor.fetchall():
            activities.append({
                'action_type': row[0],
                'details': row[1],
                'performed_at': row[2]
            })
        
        return activities
    
    try:
        return execute_db_operation(_get_activity)
    except Exception as e:
        log_event('error', f"Error getting communication activity: {e}")
        return []



@handle_exception
def get_system_health_info():
    """Get system health information for communication components"""
    from .email_service import email_queue, worker_threads  # Local import to avoid circular dependency

    health_info = {
        'email_system': 'operational',
        'message_system': 'operational',
        'chat_system': 'operational',
        'database_status': 'operational',
        'queue_size': 0,
        'last_check': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    try:
        # Check email queue
        if not config.get('database_only_mode', True):
            health_info['queue_size'] = email_queue.qsize()
            
            # Check if workers are running
            if not worker_threads:
                health_info['email_system'] = 'degraded'
        
        # Test database connection
        def _test_db(cursor):
            cursor.execute('SELECT 1')
            return cursor.fetchone() is not None
        
        if not execute_db_operation(_test_db):
            health_info['database_status'] = 'error'
        
    except Exception as e:
        log_event('error', f"Error checking system health: {e}")
        health_info['database_status'] = 'error'
    
    return health_info
