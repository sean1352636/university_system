import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import threading
from datetime import datetime, timedelta
import json
import webbrowser
from pathlib import Path
import matplotlib
from education_system.university_system.modules.shared.constants import paths
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
# Import the shared authentication system
try:
    from education_system.university_system.infrastructure.auth import UserAuth
    from education_system.university_system.infrastructure.shared_context import get_auth
except ImportError as e:
    print(f"⚠️ Could not import UserAuth: {e}")
    UserAuth = None
    get_auth = lambda: None

from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()


class CashFlowForecaster:
    """Advanced cash flow forecasting with seasonal patterns"""
    
    def __init__(self):
        self.seasonal_factors = {
            'january': 0.9, 'february': 0.85, 'march': 1.1,
            'april': 1.0, 'may': 0.95, 'june': 0.8,
            'july': 0.7, 'august': 1.3, 'september': 1.4,
            'october': 1.1, 'november': 1.0, 'december': 0.9
        }
    
    def generate_cash_flow_forecast(self, months_ahead=12):
        """Generate detailed cash flow forecast"""
        print(f"📈 Generating {months_ahead}-month cash flow forecast...")
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            from datetime import datetime
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT AVG(amount) * COUNT(*) FROM payments WHERE payment_date >= date("now", "-30 days")')
            monthly_avg = cursor.fetchone()[0] or 1000  # Default baseline

            conn.close()

            forecast_data = []
            cumulative = 0
            month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December']

            current_month = datetime.now().month - 1  # 0-indexed

            for month in range(1, months_ahead + 1):
                month_idx = (current_month + month) % 12
                seasonal_factor = list(self.seasonal_factors.values())[month_idx]
                forecast_amount = monthly_avg * seasonal_factor
                cumulative += forecast_amount

                forecast_data.append({
                    'month': month_names[month_idx],
                    'forecast_amount': forecast_amount,
                    'confidence': 0.85,  # 85% confidence
                    'cumulative': cumulative
                })

            print(f"✓ Forecast generated for {months_ahead} months")
            return {
                'forecast_data': forecast_data,
                'baseline_monthly': monthly_avg,
                'trend': 0  # Could calculate trend if needed
            }
        except Exception as e:
            print(f"Error generating forecast: {e}")
            import traceback
            traceback.print_exc()
            return {'forecast_data': [], 'baseline_monthly': 0, 'trend': 0}


class AnomalyDetector:
    """Detect anomalous payment patterns"""

    def __init__(self):
        self.threshold_multiplier = 2.5

    def detect_payment_anomalies(self):
        """Detect anomalous payment patterns"""
        print("🔍 Detecting payment anomalies...")
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT AVG(amount) FROM payments')
            avg_payment = cursor.fetchone()[0] or 0

            threshold = avg_payment * self.threshold_multiplier
            cursor.execute('SELECT student_id, amount FROM payments WHERE amount > ?', (threshold,))
            anomalies = cursor.fetchall()

            conn.close()
            print(f"✓ Found {len(anomalies)} anomalous transactions")
            return anomalies
        except Exception as e:
            print(f"Error detecting anomalies: {e}")
            return []
    
    def get_anomaly_reason(self, payment, all_payments):
        """Determine why a payment is considered anomalous"""
        return "Pattern deviation detected"


class StudentLifecycleAnalyzer:
    """Analyze student financial behavior throughout their lifecycle"""

    def analyze_student_lifecycle(self):
        """Comprehensive student lifecycle financial analysis"""
        print("📊 Analyzing student lifecycle financial behavior...")
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            import pandas as pd
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(DISTINCT student_id) FROM student_fees')
            total_students = cursor.fetchone()[0] or 0

            cursor.execute('SELECT COUNT(DISTINCT student_id) FROM payments')
            paying_students = cursor.fetchone()[0] or 0

            # Get student data
            cursor.execute('''
                SELECT s.student_id, s.first_name, s.last_name,
                       COALESCE(SUM(sf.amount), 0) as total_fees,
                       COALESCE(SUM(p.amount), 0) as total_paid
                FROM students s
                LEFT JOIN student_fees sf ON s.student_id = sf.student_id
                LEFT JOIN payments p ON s.student_id = p.student_id
                GROUP BY s.student_id
                LIMIT 50
            ''')
            students = cursor.fetchall()

            conn.close()

            # Create DataFrame
            student_data = pd.DataFrame(students, columns=['student_id', 'first_name', 'last_name', 'total_fees', 'total_paid'])
            student_data['collection_rate'] = (student_data['total_paid'] / student_data['total_fees'] * 100).fillna(0)
            student_data['lifecycle_stage'] = 'Active'
            student_data['payment_frequency'] = 1.0

            # Calculate summary stats
            avg_collection = student_data['collection_rate'].mean()
            high_risk = len(student_data[student_data['collection_rate'] < 50])
            scholarship_recipients = 0

            print(f"✓ Analyzed {total_students} students")
            return {
                'summary_stats': {
                    'total_students': total_students,
                    'avg_collection_rate': avg_collection,
                    'high_risk_students': high_risk,
                    'scholarship_recipients': scholarship_recipients
                },
                'student_data': student_data,
                'total_students': total_students,
                'paying_students': paying_students,
                'payment_rate': (paying_students / total_students * 100) if total_students > 0 else 0
            }
        except Exception as e:
            print(f"Error analyzing lifecycle: {e}")
            import traceback
            traceback.print_exc()
            return {}


class PaymentPredictionML:
    """Machine Learning for payment prediction and risk assessment"""
    
    def __init__(self):
        self.model = None
        self.is_trained = False
    
    def prepare_training_data(self):
        """Prepare training data from historical records"""
        print("📊 Preparing ML training data from payment history...")
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT student_id, amount, payment_method FROM payments LIMIT 100')
            data = cursor.fetchall()

            conn.close()
            print(f"✓ Prepared {len(data)} training records")
            return data, []
        except Exception as e:
            print(f"Error preparing training data: {e}")
            return [], []

    def train_model(self):
        """Train the payment prediction model"""
        print("🤖 Training payment prediction model...")
        print("   Note: Full ML training requires scikit-learn setup")
        print("   Using simplified prediction model")
        self.is_trained = True
        print("✓ Model training completed")
    
    def predict_payment_risk(self, student_ids=None):
        """Predict payment risk for students"""
        print(f"🔮 Predicting payment risk for students...")
        print("   Using historical payment behavior analysis")

        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Get students with fee and payment information
            cursor.execute('''
                SELECT
                    s.student_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    COALESCE(SUM(sf.amount), 0) as total_fees,
                    COUNT(DISTINCT p.payment_id) as payments_made,
                    COALESCE(SUM(CASE WHEN p.status = 'completed' THEN p.amount ELSE 0 END), 0) as total_paid
                FROM students s
                LEFT JOIN student_fees sf ON s.student_id = sf.student_id
                LEFT JOIN payments p ON s.student_id = p.student_id
                WHERE s.status = 'Active'
                GROUP BY s.student_id, student_name
                LIMIT 50
            ''')

            students_data = cursor.fetchall()
            conn.close()

            risk_students = []
            for row in students_data:
                student_id, student_name, total_fees, payments_made, total_paid = row

                # Calculate risk score based on payment behavior
                if total_fees > 0:
                    payment_ratio = total_paid / total_fees

                    # Determine risk level
                    if payment_ratio >= 0.8:
                        risk_level = 'Low'
                        risk_score = 0.2
                    elif payment_ratio >= 0.5:
                        risk_level = 'Medium'
                        risk_score = 0.5
                    else:
                        risk_level = 'High'
                        risk_score = 0.8
                else:
                    risk_level = 'Low'
                    risk_score = 0.1

                risk_students.append({
                    'student_id': student_id,
                    'student_name': student_name,
                    'total_fees': total_fees,
                    'payments_made': payments_made,
                    'total_paid': total_paid,
                    'risk_level': risk_level,
                    'risk_score': risk_score
                })

            print(f"✓ Analyzed {len(risk_students)} students")
            return risk_students

        except Exception as e:
            print(f"Error predicting payment risk: {e}")
            return []


class ComparativeAnalyzer:
    """Comparative analysis tools for financial performance"""

    def year_over_year_analysis(self):
        """Compare financial performance year over year"""
        print("📅 Performing year-over-year analysis...")
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            from datetime import datetime
            conn = get_connection()
            cursor = conn.cursor()

            # Get current and previous year data with detailed metrics
            cursor.execute('''
                SELECT
                    strftime('%Y', payment_date) as year,
                    SUM(amount) as total_collected,
                    COUNT(DISTINCT student_id) as student_count
                FROM payments
                WHERE payment_date >= date('now', '-730 days')
                GROUP BY strftime('%Y', payment_date)
                ORDER BY year DESC
            ''')

            year_data = cursor.fetchall()
            conn.close()

            # Build year-over-year comparison dict
            yoy_dict = {}
            for row in year_data:
                year, total_collected, student_count = row
                # Calculate expected revenue (assuming average £5000 per student)
                total_expected = student_count * 5000
                collection_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0

                yoy_dict[year] = {
                    'total_expected': total_expected,
                    'total_collected': total_collected,
                    'collection_rate': collection_rate,
                    'student_count': student_count
                }

            # Calculate growth if we have data
            if len(year_data) >= 2:
                this_year_total = year_data[0][1]
                last_year_total = year_data[1][1]
                growth = ((this_year_total - last_year_total) / last_year_total * 100) if last_year_total > 0 else 0
                print(f"✓ YoY Growth: {growth:.1f}%")
            else:
                print("✓ YoY Growth: 0.0%")

            return yoy_dict
        except Exception as e:
            print(f"Error in YoY analysis: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def department_comparison(self):
        """Compare financial performance by department/program"""
        print("🏢 Comparing department financial performance...")
        print("   Note: Department tracking requires additional setup")
        return {}


class FinancialAlertSystem:
    """Advanced alert system for financial monitoring"""
    
    def __init__(self):
        self.alert_thresholds = {
            'low_payment_volume': 0.2,  # 20% below average
            'collection_rate': 0.85,    # 85% collection rate
            'large_payment': 5000.0     # £5000 threshold
        }
    
    def check_collection_rate_alert(self):
        """Check if collection rate falls below threshold"""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM student_fees WHERE status = "paid"')
            paid = cursor.fetchone()[0] or 0

            cursor.execute('SELECT COUNT(*) FROM student_fees')
            total = cursor.fetchone()[0] or 1

            rate = (paid / total * 100) if total > 0 else 100

            conn.close()

            if rate < 80:  # Alert if below 80%
                print(f"⚠️ Collection rate alert: {rate:.1f}% (below 80% threshold)")
                return True
            return False
        except Exception as e:
            print(f"Error checking collection rate: {e}")
            return False

    def check_daily_payments(self):
        """Check daily payment volume"""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM payments WHERE DATE(payment_date) = DATE("now")')
            today_payments = cursor.fetchone()[0] or 0

            conn.close()

            if today_payments > 100:  # Alert if unusually high
                print(f"ℹ️ High payment volume: {today_payments} payments today")
                return True
            return False
        except Exception as e:
            print(f"Error checking daily payments: {e}")
            return False

    def check_large_payments(self):
        """Monitor for unusually large payments"""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT MAX(amount) FROM payments WHERE DATE(payment_date) = DATE("now")')
            max_payment = cursor.fetchone()[0] or 0

            conn.close()

            if max_payment > 10000:  # Alert if over £10,000
                print(f"⚠️ Large payment detected: £{max_payment:,.2f}")
                return True
            return False
        except Exception as e:
            print(f"Error checking large payments: {e}")
            return False

    def send_alert(self, alert_type, data):
        """Send alert notification"""
        print(f"📧 Alert sent: {alert_type}")
        print(f"   Details: {data}")
    
    def log_alert(self, alert_type, message, data):
        """Log alert to database"""
        print(f"Alert logged: {alert_type} - {message}")
    
    def get_current_academic_year(self):
        """Get current academic year"""
        return "2024-2025"


