from datetime import datetime
import json

from education_system.post_18.university_system.infrastructure.database.db import get_connection


class FinancialAlertSystem:
    """Advanced alert system for financial monitoring"""

    def __init__(self):
        self.alert_thresholds = {
            'collection_rate_min': 85.0,
            'daily_payment_min': 1000.0,
            'large_payment_threshold': 5000.0,
            'overdue_balance_max': 10000.0,
            'cash_flow_warning': 50000.0
        }
        self.notification_emails = ['finance@university.edu', 'admin@university.edu']

    def check_collection_rate_alert(self):
        """Check if collection rate falls below threshold"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get current collection rate
            cursor.execute('''
            SELECT
                SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as collected,
                SUM(sf.amount) as total
            FROM student_fees sf
            JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
            WHERE ft.academic_year = ?
            ''', (self.get_current_academic_year(),))

            result = cursor.fetchone()
            # Handle None values from empty tables
            collected = result[0] if result and result[0] is not None else 0
            total = result[1] if result and result[1] is not None else 0

            if total > 0:
                collection_rate = (collected / total) * 100

                if collection_rate < self.alert_thresholds['collection_rate_min']:
                    self.send_alert('COLLECTION_RATE_LOW', {
                        'current_rate': collection_rate,
                        'threshold': self.alert_thresholds['collection_rate_min'],
                        'collected': collected,
                        'total': total
                    })

            conn.close()
        except Exception as e:
            print(f"Error checking collection rate: {e}")

    def check_daily_payments(self):
        """Check daily payment volume"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('''
            SELECT SUM(amount) FROM payments WHERE payment_date = ?
            ''', (today,))

            daily_total = cursor.fetchone()[0] or 0

            if daily_total < self.alert_thresholds['daily_payment_min']:
                self.send_alert('DAILY_PAYMENTS_LOW', {
                    'daily_total': daily_total,
                    'threshold': self.alert_thresholds['daily_payment_min'],
                    'date': today
                })

            conn.close()
        except Exception as e:
            print(f"Error checking daily payments: {e}")

    def check_large_payments(self):
        """Monitor for unusually large payments"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('''
            SELECT p.amount, s.student_id, s.first_name, s.last_name, p.payment_method
            FROM payments p
            JOIN students s ON p.student_id = s.student_id
            WHERE p.payment_date = ? AND p.amount > ?
            ''', (today, self.alert_thresholds['large_payment_threshold']))

            large_payments = cursor.fetchall()

            for payment in large_payments:
                self.send_alert('LARGE_PAYMENT_DETECTED', {
                    'amount': payment[0],
                    'student_id': payment[1],
                    'student_name': f"{payment[2]} {payment[3]}",
                    'payment_method': payment[4],
                    'date': today
                })

            conn.close()
        except Exception as e:
            print(f"Error checking large payments: {e}")

    def send_alert(self, alert_type, data):
        """Send alert notification"""
        # Build message based on alert type to avoid KeyError on missing keys
        if alert_type == 'COLLECTION_RATE_LOW':
            message = f"Collection rate ({data.get('current_rate', 0):.1f}%) below threshold ({data.get('threshold', 0):.1f}%)"
        elif alert_type == 'DAILY_PAYMENTS_LOW':
            message = f"Daily payments (£{data.get('daily_total', 0):,.2f}) below threshold (£{data.get('threshold', 0):,.2f})"
        elif alert_type == 'LARGE_PAYMENT_DETECTED':
            message = f"Large payment detected: £{data.get('amount', 0):,.2f} from {data.get('student_name', 'Unknown')} via {data.get('payment_method', 'Unknown')}"
        elif alert_type == 'CASH_FLOW_WARNING':
            message = f"Cash flow warning: {data.get('message', 'No details')}"
        elif alert_type == 'ANOMALY_DETECTED':
            message = f"Payment anomaly detected: {data.get('description', 'No details')}"
        else:
            message = f"Unknown alert: {alert_type}"

        # Log alert to database
        self.log_alert(alert_type, message, data)

        # Send email notification (simplified - would need SMTP configuration)
        print(f"ALERT [{alert_type}]: {message}")

        # In production, implement actual email sending:
        # self.send_email_alert(alert_type, message, data)

    def log_alert(self, alert_type, message, data):
        """Log alert to database"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Create alerts table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS financial_alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                data TEXT,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved BOOLEAN DEFAULT FALSE
            )
            ''')

            cursor.execute('''
            INSERT INTO financial_alerts (alert_type, message, data)
            VALUES (?, ?, ?)
            ''', (alert_type, message, json.dumps(data)))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error logging alert: {e}")

    def get_current_academic_year(self):
        """Get current academic year"""
        current_date = datetime.now()
        if current_date.month >= 9:
            return f"{current_date.year}-{current_date.year + 1}"
        else:
            return f"{current_date.year - 1}-{current_date.year}"
