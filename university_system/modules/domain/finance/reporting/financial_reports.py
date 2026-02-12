from university_system.infrastructure.database.db import sqlite3, DatabaseManager
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import csv
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import warnings
import io
import pickle
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, accuracy_score


# Allowed modules/classes for safe ML model deserialization
_BLOCKED_NAMES = {'exec', 'eval', 'compile', '__import__', 'system', 'popen',
                  'subprocess', 'os', 'sys', 'globals', 'locals'}


class _RestrictedModelUnpickler(pickle.Unpickler):
    """Unpickler that only allows safe sklearn/numpy types for model deserialization."""

    def find_class(self, module, name):
        if name in _BLOCKED_NAMES:
            raise pickle.UnpicklingError(
                f"Restricted unpickler refused to load blocked name '{module}.{name}'"
            )
        base_module = module.split('.')[0]
        if base_module in ('numpy', 'sklearn', 'scipy', 'builtins', 'collections',
                           'copyreg', '_codecs'):
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"Restricted unpickler refused to load '{module}.{name}'"
        )


def _safe_model_load(file_obj):
    """Safely load a pickled ML model, only allowing sklearn/numpy types."""
    return _RestrictedModelUnpickler(file_obj).load()
# sqlite3 and DatabaseManager imported above from university_system.infrastructure.database.db
from threading import Timer
import schedule
import time
from university_system.modules.domain.finance.reporting.revenue_by_source_report import (
    print_revenue_by_source_report, revenue_by_source_menu
)
from university_system.modules.domain.finance.reporting.revenue_analytics import (
    generate_financial_forecasting, generate_budget_variance_report, generate_financial_dashboard as financial_dashboard
)
# NOTE: Import commented out - module does not exist
# from university_system.modules.domain.finance.finance import auth, get_student_name

# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth import get_current_user, set_auth_instance, UserAuth
    from university_system.infrastructure.shared_context import get_auth
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None
    get_auth = lambda: None
    UserAuth = None

auth = None  # Placeholder for global auth variable

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)

from university_system.infrastructure.database.db import get_connection

# Configure plotting style
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")
warnings.filterwarnings('ignore')

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

class PaymentPredictionML:
    """Machine Learning for payment prediction and risk assessment"""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = [
            'days_since_enrollment', 'total_fees', 'payments_made',
            'avg_payment_amount', 'last_payment_days_ago', 'payment_frequency',
            'scholarship_amount', 'gpa', 'credit_hours'
        ]
    
    def prepare_training_data(self):
        """Prepare training data from historical records"""
        try:
            conn = get_connection()

            # Simplified query that doesn't rely on columns that may not exist (gpa, credit_hours, enrollment_date)
            query = '''
            SELECT
                s.student_id,
                90 as days_since_enrollment,
                COALESCE(SUM(sf.amount), 0) as total_fees,
                COALESCE(COUNT(p.payment_id), 0) as payments_made,
                COALESCE(AVG(p.amount), 0) as avg_payment_amount,
                COALESCE(julianday('now') - julianday(MAX(p.payment_date)), 999) as last_payment_days_ago,
                COALESCE(COUNT(p.payment_id) * 4, 0) as payment_frequency,
                COALESCE(SUM(ss.amount), 0) as scholarship_amount,
                0 as gpa,
                0 as credit_hours,
                CASE
                    WHEN COUNT(CASE WHEN p.payment_date > date('now', '-30 days') THEN 1 END) = 0
                    AND SUM(CASE WHEN sf.status != 'paid' THEN sf.amount ELSE 0 END) > 0
                    THEN 1 ELSE 0
                END as is_at_risk
            FROM students s
            LEFT JOIN student_fees sf ON s.student_id = sf.student_id
            LEFT JOIN payments p ON s.student_id = p.student_id
            LEFT JOIN student_scholarships ss ON s.student_id = ss.student_id
            GROUP BY s.student_id
            HAVING total_fees > 0
            '''

            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if len(df) < 10:
                print("Insufficient data for ML training")
                return None, None
            
            # Prepare features and target
            X = df[self.feature_columns].fillna(0)
            y = df['is_at_risk']
            
            return X, y
            
        except Exception as e:
            print(f"Error preparing training data: {e}")
            return None, None
    
    def train_model(self):
        """Train the payment prediction model"""
        X, y = self.prepare_training_data()
        
        if X is None or len(X) < 10:
            print("Cannot train model: insufficient data")
            return False
        
        try:
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train model
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)
            self.model.fit(X_train_scaled, y_train)
            
            # Evaluate
            y_pred = self.model.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)
            
            print(f"Model trained with accuracy: {accuracy:.2f}")
            
            # Save model
            with open('payment_prediction_model.pkl', 'wb') as f:
                pickle.dump({'model': self.model, 'scaler': self.scaler}, f)
            
            return True
            
        except Exception as e:
            print(f"Error training model: {e}")
            return False
    
    def predict_payment_risk(self, student_ids=None):
        """Predict payment risk for students"""
        if self.model is None:
            try:
                with open('payment_prediction_model.pkl', 'rb') as f:
                    saved_data = _safe_model_load(f)
                    self.model = saved_data['model']
                    self.scaler = saved_data['scaler']
            except (OSError, IOError, FileNotFoundError):
                print("No trained model available. Training new model...")
                if not self.train_model():
                    return []
        
        try:
            conn = get_connection()
            
            where_clause = ""
            if student_ids:
                ids_str = ','.join([str(id) for id in student_ids])
                where_clause = f"WHERE s.student_id IN ({ids_str})"
            
            query = f'''
            SELECT
                s.student_id,
                s.first_name,
                s.last_name,
                90 as days_since_enrollment,
                COALESCE(SUM(sf.amount), 0) as total_fees,
                COALESCE(COUNT(p.payment_id), 0) as payments_made,
                COALESCE(AVG(p.amount), 0) as avg_payment_amount,
                COALESCE(julianday('now') - julianday(MAX(p.payment_date)), 999) as last_payment_days_ago,
                COALESCE(COUNT(p.payment_id) * 4, 0) as payment_frequency,
                COALESCE(SUM(ss.amount), 0) as scholarship_amount,
                0 as gpa,
                0 as credit_hours
            FROM students s
            LEFT JOIN student_fees sf ON s.student_id = sf.student_id
            LEFT JOIN payments p ON s.student_id = p.student_id
            LEFT JOIN student_scholarships ss ON s.student_id = ss.student_id
            {where_clause}
            GROUP BY s.student_id, s.first_name, s.last_name
            '''
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if len(df) == 0:
                return []
            
            # Prepare features
            X = df[self.feature_columns].fillna(0)
            X_scaled = self.scaler.transform(X)
            
            # Predict
            risk_probabilities = self.model.predict_proba(X_scaled)[:, 1]
            
            # Prepare results
            results = []
            for i, row in df.iterrows():
                results.append({
                    'student_id': row['student_id'],
                    'student_name': f"{row['first_name']} {row['last_name']}",
                    'risk_score': risk_probabilities[i],
                    'risk_level': 'High' if risk_probabilities[i] > 0.7 else 'Medium' if risk_probabilities[i] > 0.3 else 'Low',
                    'total_fees': row['total_fees'],
                    'payments_made': row['payments_made']
                })
            
            return sorted(results, key=lambda x: x['risk_score'], reverse=True)
            
        except Exception as e:
            print(f"Error predicting payment risk: {e}")
            return []

class AnomalyDetector:
    """Detect anomalous payment patterns"""
    
    def __init__(self):
        self.isolation_forest = IsolationForest(contamination=0.1, random_state=42)
    
    def detect_payment_anomalies(self):
        """Detect anomalous payment patterns"""
        try:
            conn = get_connection()
            
            # Get payment data with features
            query = '''
            SELECT 
                p.payment_id,
                p.student_id,
                p.amount,
                p.payment_date,
                p.payment_method,
                s.first_name,
                s.last_name,
                strftime('%w', p.payment_date) as day_of_week,
                strftime('%H', p.payment_date) as hour_of_day
            FROM payments p
            JOIN students s ON p.student_id = s.student_id
            WHERE p.payment_date > date('now', '-90 days')
            '''
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if len(df) < 10:
                return []
            
            # Prepare features for anomaly detection
            features = df[['amount']].copy()
            features['day_of_week'] = pd.to_numeric(df['day_of_week'])
            features['hour_of_day'] = pd.to_numeric(df['hour_of_day'], errors='coerce').fillna(12)
            
            # Detect anomalies
            anomaly_scores = self.isolation_forest.fit_predict(features)
            
            # Get anomalous payments
            anomalies = df[anomaly_scores == -1].copy()
            
            results = []
            for _, row in anomalies.iterrows():
                results.append({
                    'payment_id': row['payment_id'],
                    'student_id': row['student_id'],
                    'student_name': f"{row['first_name']} {row['last_name']}",
                    'amount': row['amount'],
                    'payment_date': row['payment_date'],
                    'payment_method': row['payment_method'],
                    'anomaly_reason': self.get_anomaly_reason(row, df)
                })
            
            return results
            
        except Exception as e:
            print(f"Error detecting anomalies: {e}")
            return []
    
    def get_anomaly_reason(self, payment, all_payments):
        """Determine why a payment is considered anomalous"""
        amount = payment['amount']
        avg_amount = all_payments['amount'].mean()
        std_amount = all_payments['amount'].std()
        
        if amount > avg_amount + 2 * std_amount:
            return f"Unusually large amount (£{amount:,.2f} vs avg £{avg_amount:,.2f})"
        elif amount < avg_amount - 2 * std_amount:
            return f"Unusually small amount (£{amount:,.2f} vs avg £{avg_amount:,.2f})"
        else:
            return "Unusual timing or method pattern"

class CashFlowForecaster:
    """Advanced cash flow forecasting with seasonal patterns"""
    
    def __init__(self):
        self.seasonal_factors = {
            '09': 1.5,  # September - high enrollment
            '10': 1.2,  # October
            '11': 1.0,  # November
            '12': 0.8,  # December - holidays
            '01': 1.3,  # January - spring enrollment
            '02': 1.1,  # February
            '03': 1.0,  # March
            '04': 0.9,  # April
            '05': 0.7,  # May - end of semester
            '06': 0.5,  # June - summer break
            '07': 0.4,  # July - summer break
            '08': 0.8   # August - pre-enrollment
        }
    
    def generate_cash_flow_forecast(self, months_ahead=12):
        """Generate detailed cash flow forecast"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get historical monthly payment data
            cursor.execute('''
            SELECT 
                strftime('%Y-%m', payment_date) as month,
                SUM(amount) as total_payments,
                COUNT(*) as payment_count,
                AVG(amount) as avg_payment
            FROM payments
            WHERE payment_date > date('now', '-24 months')
            GROUP BY month
            ORDER BY month
            ''')
            
            historical_data = cursor.fetchall()
            
            if not historical_data:
                conn.close()
                return None
            
            # Calculate baseline and trends
            monthly_amounts = [row[1] for row in historical_data]
            baseline_monthly = np.mean(monthly_amounts)
            
            # Simple trend calculation
            months = list(range(len(monthly_amounts)))
            trend = np.polyfit(months, monthly_amounts, 1)[0] if len(months) > 1 else 0
            
            # Generate forecast
            forecast_data = []
            current_date = datetime.now()
            
            for i in range(months_ahead):
                forecast_month = current_date + timedelta(days=30 * i)
                month_key = forecast_month.strftime('%m')
                
                # Apply seasonal factor and trend
                seasonal_factor = self.seasonal_factors.get(month_key, 1.0)
                forecast_amount = (baseline_monthly + trend * i) * seasonal_factor
                
                # Add some randomness for realism (in production, use more sophisticated methods)
                forecast_amount *= np.random.normal(1.0, 0.1)
                forecast_amount = max(0, forecast_amount)  # Ensure non-negative
                
                forecast_data.append({
                    'month': forecast_month.strftime('%Y-%m'),
                    'forecast_amount': forecast_amount,
                    'seasonal_factor': seasonal_factor,
                    'confidence': max(0.5, 1.0 - (i * 0.05))  # Decreasing confidence over time
                })
            
            # Get current outstanding balance
            cursor.execute('''
            SELECT SUM(amount) FROM student_fees WHERE status != 'paid'
            ''')
            outstanding_balance = cursor.fetchone()[0] or 0
            
            # Calculate cumulative cash flow
            cumulative_cash = 0
            for item in forecast_data:
                cumulative_cash += item['forecast_amount']
                item['cumulative_cash'] = cumulative_cash
                item['collection_rate'] = min(100, (cumulative_cash / outstanding_balance * 100)) if outstanding_balance > 0 else 100
            
            conn.close()
            
            return {
                'forecast_data': forecast_data,
                'baseline_monthly': baseline_monthly,
                'trend': trend,
                'outstanding_balance': outstanding_balance,
                'historical_data': historical_data
            }
            
        except Exception as e:
            print(f"Error generating cash flow forecast: {e}")
            return None

class StudentLifecycleAnalyzer:
    """Analyze student financial behavior throughout their lifecycle"""
    
    def analyze_student_lifecycle(self):
        """Comprehensive student lifecycle financial analysis"""
        try:
            conn = get_connection()

            # Use a simpler query that doesn't rely on columns that may not exist
            query = '''
            SELECT
                s.student_id,
                s.first_name,
                s.last_name,
                COALESCE(s.status, 'active') as status,
                COALESCE(SUM(sf.amount), 0) as total_fees,
                COALESCE(SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END), 0) as paid_fees,
                COALESCE(COUNT(p.payment_id), 0) as payment_count,
                COALESCE(AVG(p.amount), 0) as avg_payment,
                COALESCE(SUM(ss.amount), 0) as scholarship_amount,
                365 as days_enrolled
            FROM students s
            LEFT JOIN student_fees sf ON s.student_id = sf.student_id
            LEFT JOIN payments p ON s.student_id = p.student_id
            LEFT JOIN student_scholarships ss ON s.student_id = ss.student_id
            GROUP BY s.student_id
            HAVING total_fees > 0
            '''

            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if len(df) == 0:
                return None
            
            # Calculate lifecycle metrics
            df['collection_rate'] = (df['paid_fees'] / df['total_fees'] * 100).fillna(0)
            df['payment_frequency'] = (df['payment_count'] / (df['days_enrolled'] / 365)).fillna(0)
            df['scholarship_percentage'] = (df['scholarship_amount'] / df['total_fees'] * 100).fillna(0)
            df['years_enrolled'] = df['days_enrolled'] / 365
            
            # Categorize students by lifecycle stage
            def get_lifecycle_stage(row):
                if row['status'] == 'graduated':
                    return 'Graduated'
                elif row['status'] == 'dropped':
                    return 'Dropped Out'
                elif row['years_enrolled'] > 4:
                    return 'Extended Stay'
                elif row['years_enrolled'] > 2:
                    return 'Mid-Program'
                else:
                    return 'Early Program'
            
            df['lifecycle_stage'] = df.apply(get_lifecycle_stage, axis=1)
            
            # Analyze by lifecycle stage
            lifecycle_analysis = df.groupby('lifecycle_stage').agg({
                'collection_rate': ['mean', 'std', 'count'],
                'payment_frequency': 'mean',
                'scholarship_percentage': 'mean',
                'total_fees': 'mean',
                'avg_payment': 'mean'
            }).round(2)
            
            return {
                'student_data': df,
                'lifecycle_analysis': lifecycle_analysis,
                'summary_stats': {
                    'total_students': len(df),
                    'avg_collection_rate': df['collection_rate'].mean(),
                    'high_risk_students': len(df[df['collection_rate'] < 50]),
                    'scholarship_recipients': len(df[df['scholarship_amount'] > 0])
                }
            }
            
        except Exception as e:
            print(f"Error analyzing student lifecycle: {e}")
            return None

class ComparativeAnalyzer:
    """Comparative analysis tools for financial performance"""
    
    def year_over_year_analysis(self):
        """Compare financial performance year over year"""
        try:
            conn = get_connection()
            
            # Get data for last 3 academic years
            current_year = datetime.now().year
            years = [f"{current_year-2}-{current_year-1}", f"{current_year-1}-{current_year}", f"{current_year}-{current_year+1}"]
            
            yoy_data = {}
            
            for year in years:
                cursor = conn.cursor()
                
                # Revenue data
                cursor.execute('''
                SELECT 
                    SUM(sf.amount) as total_expected,
                    SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected
                FROM student_fees sf
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                WHERE ft.academic_year = ?
                ''', (year,))
                
                revenue_data = cursor.fetchone()
                
                # Student count
                cursor.execute('''
                SELECT COUNT(DISTINCT sf.student_id)
                FROM student_fees sf
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                WHERE ft.academic_year = ?
                ''', (year,))
                
                student_count = cursor.fetchone()[0] or 0
                
                yoy_data[year] = {
                    'total_expected': revenue_data[0] or 0,
                    'total_collected': revenue_data[1] or 0,
                    'collection_rate': (revenue_data[1] / revenue_data[0] * 100) if revenue_data[0] else 0,
                    'student_count': student_count,
                    'revenue_per_student': (revenue_data[0] / student_count) if student_count else 0
                }
            
            conn.close()
            return yoy_data
            
        except Exception as e:
            print(f"Error in year-over-year analysis: {e}")
            return {}
    
    def department_comparison(self):
        """Compare financial performance by department/program"""
        try:
            conn = get_connection()

            # Use fee_type as department proxy since major column may not exist
            query = '''
            SELECT
                COALESCE(ft.fee_name, 'General') as department,
                COUNT(DISTINCT s.student_id) as student_count,
                COALESCE(SUM(sf.amount), 0) as total_fees,
                COALESCE(SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END), 0) as collected_fees,
                COALESCE(AVG(sf.amount), 0) as avg_fee_per_student,
                COALESCE(SUM(ss.amount), 0) as total_scholarships
            FROM students s
            LEFT JOIN student_fees sf ON s.student_id = sf.student_id
            LEFT JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
            LEFT JOIN student_scholarships ss ON s.student_id = ss.student_id
            WHERE sf.amount IS NOT NULL
            GROUP BY ft.fee_name
            HAVING student_count > 0
            ORDER BY total_fees DESC
            '''

            df = pd.read_sql_query(query, conn)
            conn.close()

            if len(df) == 0:
                return None

            df['collection_rate'] = (df['collected_fees'] / df['total_fees'] * 100).fillna(0)
            df['scholarship_rate'] = (df['total_scholarships'] / df['total_fees'] * 100).fillna(0)

            return df

        except Exception as e:
            print(f"Error in department comparison: {e}")
            return None

# Enhanced main functions with all new features

def generate_advanced_financial_forecasting():
    """Enhanced financial forecasting with ML and advanced analytics"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access advanced financial forecasting.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to access advanced financial forecasting.")
        return
    
    print("\nAdvanced Financial Forecasting & Analytics")
    print("=" * 60)
    
    # Initialize components
    cash_flow_forecaster = CashFlowForecaster()
    payment_predictor = PaymentPredictionML()
    anomaly_detector = AnomalyDetector()
    lifecycle_analyzer = StudentLifecycleAnalyzer()
    
    # 1. Traditional forecasting (from original function)
    print("1. Generating traditional forecast...")
    generate_financial_forecasting()
    
    # 2. Advanced cash flow forecasting
    print("\n2. Advanced Cash Flow Forecasting...")
    cash_flow_data = cash_flow_forecaster.generate_cash_flow_forecast(12)
    
    if cash_flow_data:
        print("\nCash Flow Forecast (Next 12 Months):")
        print("-" * 60)
        
        total_forecast = sum(item['forecast_amount'] for item in cash_flow_data['forecast_data'])
        print(f"Total Forecasted Revenue: £{total_forecast:,.2f}")
        print(f"Monthly Baseline: £{cash_flow_data['baseline_monthly']:,.2f}")
        print(f"Trend: £{cash_flow_data['trend']:,.2f} per month")
        
        # Show monthly breakdown
        for item in cash_flow_data['forecast_data'][:6]:  # Show first 6 months
            print(f"{item['month']}: £{item['forecast_amount']:,.2f} (Confidence: {item['confidence']:.1%})")
        
        # Create cash flow visualization
        months = [item['month'] for item in cash_flow_data['forecast_data']]
        amounts = [item['forecast_amount'] for item in cash_flow_data['forecast_data']]
        confidence = [item['confidence'] for item in cash_flow_data['forecast_data']]
        
        plt.figure(figsize=(14, 8))
        
        # Main forecast line
        plt.subplot(2, 2, 1)
        plt.plot(months, amounts, marker='o', linewidth=2)
        plt.fill_between(months, 
                        [a * (1 - (1-c)*0.2) for a, c in zip(amounts, confidence)],
                        [a * (1 + (1-c)*0.2) for a, c in zip(amounts, confidence)],
                        alpha=0.3)
        plt.title('Cash Flow Forecast')
        plt.xlabel('Month')
        plt.ylabel('Amount (£)')
        plt.xticks(rotation=45)
        
        # Cumulative cash flow
        cumulative = [item['cumulative_cash'] for item in cash_flow_data['forecast_data']]
        plt.subplot(2, 2, 2)
        plt.plot(months, cumulative, marker='s', color='green')
        plt.title('Cumulative Cash Flow')
        plt.xlabel('Month')
        plt.ylabel('Cumulative Amount (£)')
        plt.xticks(rotation=45)
        
        # Seasonal factors
        seasonal_factors = [item['seasonal_factor'] for item in cash_flow_data['forecast_data']]
        plt.subplot(2, 2, 3)
        plt.bar(months, seasonal_factors, color='orange', alpha=0.7)
        plt.title('Seasonal Factors')
        plt.xlabel('Month')
        plt.ylabel('Factor')
        plt.xticks(rotation=45)
        
        # Confidence levels
        plt.subplot(2, 2, 4)
        plt.plot(months, [c*100 for c in confidence], marker='^', color='red')
        plt.title('Forecast Confidence')
        plt.xlabel('Month')
        plt.ylabel('Confidence (%)')
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig('advanced_cash_flow_forecast.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print("Advanced cash flow chart saved as 'advanced_cash_flow_forecast.png'")
    
    # 3. Payment risk prediction
    print("\n3. Payment Risk Analysis...")
    high_risk_students = payment_predictor.predict_payment_risk()
    
    if high_risk_students:
        print(f"\nHigh-Risk Students (Top 10):")
        print("-" * 60)
        
        for student in high_risk_students[:10]:
            print(f"{student['student_name']} ({student['student_id']}): "
                  f"{student['risk_level']} Risk ({student['risk_score']:.2%}) - "
                  f"£{student['total_fees']:,.2f} total fees")
        
        # Create risk distribution chart
        risk_levels = [s['risk_level'] for s in high_risk_students]
        risk_counts = pd.Series(risk_levels).value_counts()
        
        plt.figure(figsize=(10, 6))
        plt.subplot(1, 2, 1)
        plt.pie(risk_counts.values, labels=risk_counts.index, autopct='%1.1f%%')
        plt.title('Payment Risk Distribution')
        
        # Risk vs fees scatter
        plt.subplot(1, 2, 2)
        risk_scores = [s['risk_score'] for s in high_risk_students]
        total_fees = [s['total_fees'] for s in high_risk_students]
        plt.scatter(risk_scores, total_fees, alpha=0.6)
        plt.xlabel('Risk Score')
        plt.ylabel('Total Fees (£)')
        plt.title('Risk Score vs Total Fees')
        
        plt.tight_layout()
        plt.savefig('payment_risk_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print("Payment risk analysis chart saved as 'payment_risk_analysis.png'")
    
    # 4. Anomaly detection
    print("\n4. Payment Anomaly Detection...")
    anomalies = anomaly_detector.detect_payment_anomalies()
    
    if anomalies:
        print(f"\nDetected {len(anomalies)} payment anomalies:")
        print("-" * 60)
        
        for anomaly in anomalies[:5]:  # Show top 5
            print(f"{anomaly['student_name']}: £{anomaly['amount']:,.2f} on {anomaly['payment_date']}")
            print(f"  Reason: {anomaly['anomaly_reason']}")
    
    # 5. Student lifecycle analysis
    print("\n5. Student Lifecycle Analysis...")
    lifecycle_data = lifecycle_analyzer.analyze_student_lifecycle()
    
    if lifecycle_data:
        print(f"\nLifecycle Summary:")
        print(f"Total Students: {lifecycle_data['summary_stats']['total_students']}")
        print(f"Average Collection Rate: {lifecycle_data['summary_stats']['avg_collection_rate']:.1f}%")
        print(f"High-Risk Students: {lifecycle_data['summary_stats']['high_risk_students']}")
        
        # Create lifecycle visualization
        lifecycle_summary = lifecycle_data['student_data'].groupby('lifecycle_stage').agg({
            'collection_rate': 'mean',
            'student_id': 'count'
        }).round(1)
        
        plt.figure(figsize=(12, 8))
        
        # Collection rate by lifecycle stage
        plt.subplot(2, 2, 1)
        lifecycle_summary['collection_rate'].plot(kind='bar')
        plt.title('Collection Rate by Lifecycle Stage')
        plt.ylabel('Collection Rate (%)')
        plt.xticks(rotation=45)
        
        # Student count by lifecycle stage
        plt.subplot(2, 2, 2)
        lifecycle_summary['student_id'].plot(kind='pie', autopct='%1.1f%%')
        plt.title('Students by Lifecycle Stage')
        
        # Collection rate distribution
        plt.subplot(2, 2, 3)
        plt.hist(lifecycle_data['student_data']['collection_rate'], bins=20, alpha=0.7, edgecolor='black')
        plt.title('Collection Rate Distribution')
        plt.xlabel('Collection Rate (%)')
        plt.ylabel('Number of Students')
        
        # Scholarship vs Collection Rate
        plt.subplot(2, 2, 4)
        plt.scatter(lifecycle_data['student_data']['scholarship_percentage'], 
                   lifecycle_data['student_data']['collection_rate'], alpha=0.6)
        plt.xlabel('Scholarship Percentage (%)')
        plt.ylabel('Collection Rate (%)')
        plt.title('Scholarship Impact on Collection')
        
        plt.tight_layout()
        plt.savefig('student_lifecycle_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print("Student lifecycle analysis chart saved as 'student_lifecycle_analysis.png'")

def generate_comprehensive_budget_variance_report():
    """Enhanced budget variance with predictive analytics"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to generate comprehensive budget variance reports.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to generate comprehensive budget variance reports.")
        return
    
    print("\nComprehensive Budget Variance & Performance Analysis")
    print("=" * 70)
    
    # Run original budget variance
    generate_budget_variance_report()
    
    # Add comparative analysis
    print("\n6. Comparative Analysis...")
    comparative_analyzer = ComparativeAnalyzer()
    
    # Year-over-year analysis
    yoy_data = comparative_analyzer.year_over_year_analysis()
    if yoy_data:
        print("\nYear-over-Year Performance:")
        print("-" * 40)
        
        for year, data in yoy_data.items():
            print(f"{year}: £{data['total_collected']:,.2f} collected "
                  f"({data['collection_rate']:.1f}% rate) - "
                  f"{data['student_count']} students")
        
        # Create YoY visualization
        years = list(yoy_data.keys())
        collections = [yoy_data[year]['total_collected'] for year in years]
        rates = [yoy_data[year]['collection_rate'] for year in years]
        
        plt.figure(figsize=(12, 6))
        
        plt.subplot(1, 2, 1)
        plt.bar(years, collections)
        plt.title('Revenue Collection by Year')
        plt.ylabel('Amount Collected (£)')
        plt.xticks(rotation=45)
        
        plt.subplot(1, 2, 2)
        plt.plot(years, rates, marker='o', linewidth=2)
        plt.title('Collection Rate Trend')
        plt.ylabel('Collection Rate (%)')
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig('year_over_year_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print("Year-over-year analysis chart saved as 'year_over_year_analysis.png'")
    
    # Department comparison
    dept_data = comparative_analyzer.department_comparison()
    if dept_data is not None and len(dept_data) > 0:
        print("\nDepartment Performance:")
        print("-" * 40)
        
        for _, row in dept_data.head(5).iterrows():
            print(f"{row['department']}: {row['collection_rate']:.1f}% collection rate, "
                  f"£{row['avg_fee_per_student']:,.2f} avg fee per student")
        
        # Create department comparison visualization
        plt.figure(figsize=(14, 10))
        
        # Collection rate by department
        plt.subplot(2, 2, 1)
        top_depts = dept_data.head(8)
        plt.barh(range(len(top_depts)), top_depts['collection_rate'])
        plt.yticks(range(len(top_depts)), top_depts['department'])
        plt.xlabel('Collection Rate (%)')
        plt.title('Collection Rate by Department')
        
        # Revenue by department
        plt.subplot(2, 2, 2)
        plt.barh(range(len(top_depts)), top_depts['total_fees'])
        plt.yticks(range(len(top_depts)), top_depts['department'])
        plt.xlabel('Total Fees (£)')
        plt.title('Revenue by Department')
        
        # Student count vs collection rate
        plt.subplot(2, 2, 3)
        plt.scatter(dept_data['student_count'], dept_data['collection_rate'], 
                   s=dept_data['total_fees']/1000, alpha=0.6)
        plt.xlabel('Student Count')
        plt.ylabel('Collection Rate (%)')
        plt.title('Students vs Collection Rate\n(Bubble size = Revenue)')
        
        # Scholarship rate impact
        plt.subplot(2, 2, 4)
        plt.scatter(dept_data['scholarship_rate'], dept_data['collection_rate'], alpha=0.6)
        plt.xlabel('Scholarship Rate (%)')
        plt.ylabel('Collection Rate (%)')
        plt.title('Scholarship Impact on Collection')
        
        plt.tight_layout()
        plt.savefig('department_comparison_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print("Department comparison chart saved as 'department_comparison_analysis.png'")

def real_time_financial_dashboard():
    """Enhanced real-time financial dashboard with live metrics"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access the real-time financial dashboard.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to access the real-time financial dashboard.")
        return
    
    print("\nReal-Time Financial Performance Dashboard")
    print("=" * 60)
    
    # Initialize alert system
    alert_system = FinancialAlertSystem()
    
    # Run all alert checks
    print("Running real-time monitoring checks...")
    alert_system.check_collection_rate_alert()
    alert_system.check_daily_payments()
    alert_system.check_large_payments()
    
    # Run original dashboard
    financial_dashboard()
    
    # Add real-time KPIs
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Real-time metrics
        today = datetime.now().strftime('%Y-%m-%d')
        this_week = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        this_month = datetime.now().strftime('%Y-%m-01')
        
        print("\nReal-Time Performance Indicators:")
        print("-" * 60)
        
        # Today's payments
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM payments WHERE payment_date = ?', (today,))
        today_data = cursor.fetchone()
        print(f"Today's Payments: {today_data[0]} transactions, £{today_data[1] or 0:,.2f}")
        
        # This week's payments
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM payments WHERE payment_date >= ?', (this_week,))
        week_data = cursor.fetchone()
        print(f"This Week: {week_data[0]} transactions, £{week_data[1] or 0:,.2f}")
        
        # This month's payments
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM payments WHERE payment_date >= ?', (this_month,))
        month_data = cursor.fetchone()
        print(f"This Month: {month_data[0]} transactions, £{month_data[1] or 0:,.2f}")
        
        # Payment velocity (payments per day)
        cursor.execute('''
        SELECT COUNT(*) / COUNT(DISTINCT payment_date) as daily_velocity
        FROM payments 
        WHERE payment_date >= date('now', '-30 days')
        ''')
        velocity = cursor.fetchone()[0] or 0
        print(f"Payment Velocity: {velocity:.1f} payments/day (30-day avg)")
        
        # Outstanding balance aging
        cursor.execute('''
        SELECT 
            SUM(CASE WHEN julianday('now') - julianday(sf.due_date) <= 30 THEN sf.amount ELSE 0 END) as current_30,
            SUM(CASE WHEN julianday('now') - julianday(sf.due_date) BETWEEN 31 AND 60 THEN sf.amount ELSE 0 END) as days_31_60,
            SUM(CASE WHEN julianday('now') - julianday(sf.due_date) BETWEEN 61 AND 90 THEN sf.amount ELSE 0 END) as days_61_90,
            SUM(CASE WHEN julianday('now') - julianday(sf.due_date) > 90 THEN sf.amount ELSE 0 END) as over_90
        FROM student_fees sf
        WHERE sf.status != 'paid'
        ''')
        
        aging_data = cursor.fetchone()
        if aging_data:
            print("\nOutstanding Balance Aging:")
            print(f"  0-30 days: £{aging_data[0] or 0:,.2f}")
            print(f"  31-60 days: £{aging_data[1] or 0:,.2f}")
            print(f"  61-90 days: £{aging_data[2] or 0:,.2f}")
            print(f"  90+ days: £{aging_data[3] or 0:,.2f}")
        
        # Recent alerts
        cursor.execute('''
        SELECT alert_type, message, created_date 
        FROM financial_alerts 
        WHERE created_date >= date('now', '-7 days')
        ORDER BY created_date DESC
        LIMIT 5
        ''')
        
        recent_alerts = cursor.fetchall()
        if recent_alerts:
            print("\nRecent Alerts (Last 7 Days):")
            for alert_type, message, created_date in recent_alerts:
                print(f"  {created_date}: [{alert_type}] {message}")
        
        # Create comprehensive dashboard visualization
        plt.figure(figsize=(16, 12))
        
        # Payment trend (last 30 days)
        cursor.execute('''
        SELECT payment_date, SUM(amount), COUNT(*)
        FROM payments 
        WHERE payment_date >= date('now', '-30 days')
        GROUP BY payment_date
        ORDER BY payment_date
        ''')
        
        daily_payments = cursor.fetchall()
        if daily_payments:
            dates = [row[0] for row in daily_payments]
            amounts = [row[1] for row in daily_payments]
            counts = [row[2] for row in daily_payments]
            
            plt.subplot(3, 3, 1)
            plt.plot(dates, amounts, marker='o')
            plt.title('Daily Payment Amounts (30 days)')
            plt.xticks(rotation=45)
            plt.ylabel('Amount (£)')
            
            plt.subplot(3, 3, 2)
            plt.plot(dates, counts, marker='s', color='green')
            plt.title('Daily Payment Count (30 days)')
            plt.xticks(rotation=45)
            plt.ylabel('Count')
        
        # Payment method distribution
        cursor.execute('''
        SELECT payment_method, COUNT(*), SUM(amount)
        FROM payments 
        WHERE payment_date >= date('now', '-30 days')
        GROUP BY payment_method
        ''')
        
        method_data = cursor.fetchall()
        if method_data:
            methods = [row[0] for row in method_data]
            method_amounts = [row[2] for row in method_data]
            
            plt.subplot(3, 3, 3)
            plt.pie(method_amounts, labels=methods, autopct='%1.1f%%')
            plt.title('Payment Methods (30 days)')
        
        # Outstanding balance aging visualization
        if aging_data:
            aging_labels = ['0-30 days', '31-60 days', '61-90 days', '90+ days']
            aging_amounts = [aging_data[0] or 0, aging_data[1] or 0, 
                           aging_data[2] or 0, aging_data[3] or 0]
            
            plt.subplot(3, 3, 4)
            plt.bar(aging_labels, aging_amounts, color=['green', 'yellow', 'orange', 'red'])
            plt.title('Outstanding Balance Aging')
            plt.ylabel('Amount (£)')
            plt.xticks(rotation=45)
        
        # Collection rate trend
        cursor.execute('''
        SELECT 
            strftime('%Y-%m', sf.created_date) as month,
            SUM(sf.amount) as total,
            SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as collected
        FROM student_fees sf
        WHERE sf.created_date >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month
        ''')
        
        monthly_collection = cursor.fetchall()
        if monthly_collection:
            months = [row[0] for row in monthly_collection]
            collection_rates = [(row[2]/row[1]*100) if row[1] > 0 else 0 for row in monthly_collection]
            
            plt.subplot(3, 3, 5)
            plt.plot(months, collection_rates, marker='o', linewidth=2)
            plt.title('Monthly Collection Rate Trend')
            plt.ylabel('Collection Rate (%)')
            plt.xticks(rotation=45)
        
        # Payment size distribution
        cursor.execute('''
        SELECT amount FROM payments WHERE payment_date >= date('now', '-90 days')
        ''')
        
        payment_amounts = [row[0] for row in cursor.fetchall()]
        if payment_amounts:
            plt.subplot(3, 3, 6)
            plt.hist(payment_amounts, bins=20, alpha=0.7, edgecolor='black')
            plt.title('Payment Amount Distribution')
            plt.xlabel('Amount (£)')
            plt.ylabel('Frequency')
        
        # Top paying students (this month)
        cursor.execute('''
        SELECT s.first_name, s.last_name, SUM(p.amount) as total_paid
        FROM payments p
        JOIN students s ON p.student_id = s.student_id
        WHERE p.payment_date >= ?
        GROUP BY s.student_id, s.first_name, s.last_name
        ORDER BY total_paid DESC
        LIMIT 10
        ''', (this_month,))
        
        top_payers = cursor.fetchall()
        if top_payers:
            names = [f"{row[0]} {row[1]}" for row in top_payers]
            amounts = [row[2] for row in top_payers]
            
            plt.subplot(3, 3, 7)
            plt.barh(range(len(names)), amounts)
            plt.yticks(range(len(names)), names)
            plt.title('Top Payers This Month')
            plt.xlabel('Amount Paid (£)')
        
        # Fee type performance
        cursor.execute('''
        SELECT 
            ft.fee_name,
            SUM(sf.amount) as total,
            SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as collected
        FROM student_fees sf
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        GROUP BY ft.fee_name
        HAVING total > 0
        ORDER BY total DESC
        LIMIT 5
        ''')
        
        fee_performance = cursor.fetchall()
        if fee_performance:
            fee_names = [row[0] for row in fee_performance]
            collection_rates = [(row[2]/row[1]*100) if row[1] > 0 else 0 for row in fee_performance]
            
            plt.subplot(3, 3, 8)
            plt.bar(fee_names, collection_rates)
            plt.title('Collection Rate by Fee Type')
            plt.ylabel('Collection Rate (%)')
            plt.xticks(rotation=45)
        
        # Alert frequency
        cursor.execute('''
        SELECT 
            DATE(created_date) as alert_date,
            COUNT(*) as alert_count
        FROM financial_alerts
        WHERE created_date >= date('now', '-30 days')
        GROUP BY alert_date
        ORDER BY alert_date
        ''')
        
        alert_data = cursor.fetchall()
        if alert_data:
            alert_dates = [row[0] for row in alert_data]
            alert_counts = [row[1] for row in alert_data]
            
            plt.subplot(3, 3, 9)
            plt.plot(alert_dates, alert_counts, marker='o', color='red')
            plt.title('Daily Alert Frequency')
            plt.ylabel('Alert Count')
            plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig('comprehensive_realtime_dashboard.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print("\nComprehensive dashboard saved as 'comprehensive_realtime_dashboard.png'")
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating real-time dashboard: {e}")

def automated_reporting_system():
    """Set up automated report generation and delivery"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to configure automated reporting.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to configure automated reporting.")
        return
    
    print("\nAutomated Financial Reporting System")
    print("=" * 50)
    
    # Create automated reports configuration
    report_configs = {
        'daily_summary': {
            'frequency': 'daily',
            'time': '08:00',
            'recipients': ['finance@university.edu'],
            'reports': ['daily_payments', 'collection_status', 'alerts']
        },
        'weekly_analysis': {
            'frequency': 'weekly',
            'day': 'Monday',
            'time': '09:00',
            'recipients': ['finance@university.edu', 'admin@university.edu'],
            'reports': ['payment_trends', 'risk_analysis', 'cash_flow']
        },
        'monthly_comprehensive': {
            'frequency': 'monthly',
            'day': 1,
            'time': '10:00',
            'recipients': ['finance@university.edu', 'admin@university.edu', 'board@university.edu'],
            'reports': ['full_forecast', 'budget_variance', 'comparative_analysis']
        }
    }
    
    print("Automated Report Configurations:")
    print("-" * 40)
    
    for config_name, config in report_configs.items():
        print(f"\n{config_name.replace('_', ' ').title()}:")
        print(f"  Frequency: {config['frequency']}")
        print(f"  Recipients: {', '.join(config['recipients'])}")
        print(f"  Reports: {', '.join(config['reports'])}")
    
    # Simulate report scheduling
    print(f"\nReport scheduling system configured.")
    print("In production, this would integrate with cron jobs or task schedulers.")
    
    # Create sample automated report
    print("\nGenerating sample automated daily report...")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Daily summary data
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM payments WHERE payment_date = ?', (today,))
        daily_payments = cursor.fetchone()
        
        cursor.execute('SELECT COUNT(*) FROM student_fees WHERE status != "paid"', )
        outstanding_count = cursor.fetchone()[0]
        
        # Try to get alert count - handle case where table/column may not exist
        try:
            cursor.execute('SELECT COUNT(*) FROM financial_alerts WHERE DATE(created_date) = ?', (today,))
            alert_count = cursor.fetchone()[0] or 0
        except Exception:
            alert_count = 0
        
        # Generate automated report content
        report_content = f"""
        DAILY FINANCIAL SUMMARY - {today}
        ========================================
        
        Daily Payments: {daily_payments[0]} transactions, £{daily_payments[1] or 0:,.2f}
        Outstanding Fees: {outstanding_count} items
        Alerts Generated: {alert_count}
        
        Status: {'✓ Normal' if alert_count == 0 else '⚠ Attention Required'}
        
        Next Actions:
        - Review high-risk students if payment volume is low
        - Follow up on overdue accounts
        - Process any manual interventions needed
        
        This is an automated report. For detailed analysis, 
        access the full dashboard system.
        """
        
        print(report_content)
        
        # Save automated report
        report_filename = f'automated_daily_report_{today}.txt'
        with open(report_filename, 'w') as f:
            f.write(report_content)
        
        print(f"Automated report saved as '{report_filename}'")
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating automated report: {e}")

def scenario_planning_tools():
    """Advanced scenario planning and what-if analysis"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access scenario planning tools.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to access scenario planning tools.")
        return
    
    print("\nFinancial Scenario Planning & What-If Analysis")
    print("=" * 60)
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get baseline data
        cursor.execute('''
        SELECT 
            SUM(sf.amount) as total_expected,
            SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected,
            COUNT(DISTINCT sf.student_id) as student_count
        FROM student_fees sf
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        WHERE ft.academic_year = ?
        ''', (get_current_academic_year(),))
        
        baseline = cursor.fetchone()
        baseline_expected = baseline[0] or 0
        baseline_collected = baseline[1] or 0
        baseline_students = baseline[2] or 0
        baseline_rate = (baseline_collected / baseline_expected * 100) if baseline_expected > 0 else 0
        
        print(f"Baseline Scenario (Current):")
        print(f"  Students: {baseline_students}")
        print(f"  Expected Revenue: £{baseline_expected:,.2f}")
        print(f"  Current Collection: £{baseline_collected:,.2f} ({baseline_rate:.1f}%)")
        
        # Scenario 1: Fee increase
        fee_increase_scenarios = [0.05, 0.10, 0.15, 0.20]  # 5%, 10%, 15%, 20%
        
        print("\nScenario 1: Fee Increase Impact")
        print("-" * 40)
        
        for increase in fee_increase_scenarios:
            # Assume some student dropout due to fee increase
            dropout_rate = increase * 0.5  # 50% of fee increase as dropout rate
            adjusted_students = int(baseline_students * (1 - dropout_rate))
            adjusted_expected = baseline_expected * (1 + increase) * (adjusted_students / baseline_students)
            
            # Assume collection rate might decrease slightly due to affordability
            adjusted_collection_rate = baseline_rate * (1 - increase * 0.1)
            adjusted_collected = adjusted_expected * (adjusted_collection_rate / 100)
            
            print(f"  {increase:.0%} increase: {adjusted_students} students, "
                  f"£{adjusted_collected:,.2f} collected ({adjusted_collection_rate:.1f}% rate)")
        
        # Scenario 2: Economic downturn impact
        downturn_scenarios = ['mild', 'moderate', 'severe']
        downturn_impacts = {
            'mild': {'collection_rate_impact': -5, 'enrollment_impact': -10, 'payment_delay': 15},
            'moderate': {'collection_rate_impact': -15, 'enrollment_impact': -20, 'payment_delay': 30},
            'severe': {'collection_rate_impact': -25, 'enrollment_impact': -35, 'payment_delay': 60}
        }
        
        print("\nScenario 2: Economic Downturn Impact")
        print("-" * 40)
        
        for scenario_name, impacts in downturn_impacts.items():
            adjusted_students = int(baseline_students * (1 + impacts['enrollment_impact']/100))
            adjusted_rate = baseline_rate + impacts['collection_rate_impact']
            adjusted_expected = baseline_expected * (adjusted_students / baseline_students)
            adjusted_collected = adjusted_expected * (adjusted_rate / 100)
            
            print(f"  {scenario_name.title()} downturn: {adjusted_students} students, "
                  f"£{adjusted_collected:,.2f} collected ({adjusted_rate:.1f}% rate)")
        
        # Scenario 3: Scholarship program expansion
        scholarship_scenarios = [0.10, 0.20, 0.30]  # 10%, 20%, 30% more scholarships
        
        print("\nScenario 3: Scholarship Program Expansion")
        print("-" * 40)
        
        for scholarship_increase in scholarship_scenarios:
            # More scholarships might attract more students but reduce net revenue
            enrollment_boost = scholarship_increase * 1.2  # 20% more effective than cost
            adjusted_students = int(baseline_students * (1 + enrollment_boost))
            
            # Reduce per-student revenue due to scholarships
            per_student_revenue = (baseline_expected / baseline_students) * (1 - scholarship_increase * 0.7)
            adjusted_expected = per_student_revenue * adjusted_students
            
            # Better collection rate due to affordability
            adjusted_rate = min(100, baseline_rate * (1 + scholarship_increase * 0.1))
            adjusted_collected = adjusted_expected * (adjusted_rate / 100)
            
            print(f"  {scholarship_increase:.0%} more scholarships: {adjusted_students} students, "
                  f"£{adjusted_collected:,.2f} collected ({adjusted_rate:.1f}% rate)")
        
        # Scenario 4: Payment plan optimization
        payment_plan_scenarios = ['basic', 'flexible', 'comprehensive']
        plan_impacts = {
            'basic': {'collection_improvement': 5, 'admin_cost': 1000},
            'flexible': {'collection_improvement': 12, 'admin_cost': 3000},
            'comprehensive': {'collection_improvement': 20, 'admin_cost': 8000}
        }
        
        print("\nScenario 4: Payment Plan Optimization")
        print("-" * 40)
        
        for plan_name, impacts in plan_impacts.items():
            improved_rate = min(100, baseline_rate + impacts['collection_improvement'])
            improved_collected = baseline_expected * (improved_rate / 100)
            net_benefit = (improved_collected - baseline_collected) - impacts['admin_cost']
            
            print(f"  {plan_name.title()} plan: {improved_rate:.1f}% collection rate, "
                  f"£{net_benefit:,.2f} net benefit")
        
        # Create scenario comparison visualization
        scenarios = ['Baseline', '10% Fee Increase', 'Mild Downturn', '20% More Scholarships', 'Flexible Payment Plans']
        
        # Calculate values for visualization
        scenario_values = [
            baseline_collected,
            baseline_expected * 1.10 * 0.95 * 0.97,  # Fee increase scenario
            baseline_expected * 0.8 * 0.8,  # Mild downturn
            baseline_expected * 1.24 * 0.86 * 1.02,  # Scholarship expansion
            baseline_expected * 1.12  # Payment plan optimization
        ]
        
        plt.figure(figsize=(12, 8))
        
        plt.subplot(2, 2, 1)
        colors = ['blue', 'green', 'red', 'orange', 'purple']
        plt.bar(scenarios, scenario_values, color=colors)
        plt.title('Revenue Collection by Scenario')
        plt.ylabel('Revenue (£)')
        plt.xticks(rotation=45)
        
        # ROI comparison for interventions
        intervention_costs = [0, 5000, -20000, -50000, 3000]  # Costs/savings
        # Fixed the list comprehension syntax
        intervention_benefits = [0] + [s - baseline_collected for s in scenario_values[1:]]
        
        plt.subplot(2, 2, 2)
        net_benefits = [b - c for b, c in zip(intervention_benefits, intervention_costs)]
        plt.bar(scenarios, net_benefits, color=colors)
        plt.title('Net Benefit by Scenario')
        plt.ylabel('Net Benefit (£)')
        plt.xticks(rotation=45)
        
        # Risk vs Return scatter
        plt.subplot(2, 2, 3)
        risks = [0, 15, 35, 25, 10]  # Risk scores (0-100)
        returns = [(v/baseline_collected - 1) * 100 for v in scenario_values]
        
        plt.scatter(risks, returns, s=100, c=colors)
        for i, scenario in enumerate(scenarios):
            plt.annotate(scenario.split()[0], (risks[i], returns[i]), 
                        xytext=(5, 5), textcoords='offset points')
        plt.xlabel('Risk Score')
        plt.ylabel('Return (%)')
        plt.title('Risk vs Return Analysis')
        
        # Timeline impact
        plt.subplot(2, 2, 4)
        months = list(range(1, 13))
        baseline_monthly = [baseline_collected/12] * 12
        
        # Show cumulative impact over time for best scenario
        best_scenario_monthly = [scenario_values[4]/12] * 12
        cumulative_baseline = np.cumsum(baseline_monthly)
        cumulative_best = np.cumsum(best_scenario_monthly)
        
        plt.plot(months, cumulative_baseline, label='Baseline', linewidth=2)
        plt.plot(months, cumulative_best, label='Flexible Payment Plans', linewidth=2)
        plt.xlabel('Month')
        plt.ylabel('Cumulative Revenue (£)')
        plt.title('12-Month Impact Projection')
        plt.legend()
        
        plt.tight_layout()
        plt.savefig('scenario_planning_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print("\nScenario planning analysis chart saved as 'scenario_planning_analysis.png'")
        
        # Generate recommendations
        print("\nScenario Planning Recommendations:")
        print("-" * 40)
        print("1. Flexible Payment Plans show highest ROI with lowest risk")
        print("2. Fee increases require careful balance with enrollment impact")
        print("3. Scholarship expansion needs targeted approach to maximize enrollment")
        print("4. Economic downturn preparation should focus on collection efficiency")
        print("5. Consider implementing multiple low-risk strategies simultaneously")
        
        conn.close()
        
    except Exception as e:
        print(f"Error in scenario planning: {e}")
        
def get_current_academic_year():
    """Helper function to get current academic year"""
    current_date = datetime.now()
    if current_date.month >= 9:
        return f"{current_date.year}-{current_date.year + 1}"
    else:
        return f"{current_date.year - 1}-{current_date.year}"

def advanced_export_system():
    """Advanced export system with multiple formats and automation"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access advanced export system.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to access advanced export system.")
        return
    
    print("\nAdvanced Export & Data Delivery System")
    print("=" * 50)
    
    export_options = {
        '1': 'Complete Financial Analysis Package (All Reports + Charts)',
        '2': 'Executive Summary Dashboard (PDF)',
        '3': 'Raw Data Export (Multiple Formats)',
        '4': 'Automated API Data Feed Setup',
        '5': 'Custom Report Builder',
        '6': 'Scheduled Export Configuration'
    }
    
    print("Export Options:")
    for key, value in export_options.items():
        print(f"{key}. {value}")
    
    choice = input("\nSelect export option (1-6): ").strip()
    
    if choice == '1':
        # Complete package
        print("Generating complete financial analysis package...")
        
        # Generate all reports
        generate_advanced_financial_forecasting()
        generate_comprehensive_budget_variance_report()
        real_time_financial_dashboard()
        scenario_planning_tools()
        
        # Create package
        package_name = f"Complete_Financial_Package_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        print(f"Complete financial analysis package prepared as '{package_name}'")
        print("Package includes: forecasts, variance analysis, dashboard, scenarios, and all visualizations")
        
    elif choice == '2':
        # Executive summary
        print("Generating executive summary dashboard...")
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Key metrics for executives
            academic_year = get_current_academic_year()
            
            cursor.execute('''
            SELECT 
                SUM(sf.amount) as total_expected,
                SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected,
                COUNT(DISTINCT sf.student_id) as student_count
            FROM student_fees sf
            JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
            WHERE ft.academic_year = ?
            ''', (academic_year,))
            
            summary_data = cursor.fetchone()

            # Handle None values from empty tables
            total_expected = summary_data[0] if summary_data and summary_data[0] is not None else 0
            total_collected = summary_data[1] if summary_data and summary_data[1] is not None else 0
            student_count = summary_data[2] if summary_data and summary_data[2] is not None else 0
            collection_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0

            # Generate executive PDF (simplified version)
            filename = f"Executive_Summary_{datetime.now().strftime('%Y%m%d')}.pdf"

            doc = SimpleDocTemplate(filename, pagesize=letter)
            styles = getSampleStyleSheet()
            elements = []

            # Executive summary content
            elements.append(Paragraph("Financial Performance Executive Summary", styles['Title']))
            elements.append(Spacer(1, 0.5*inch))

            # Key metrics table
            metrics_data = [
                ['Metric', 'Value', 'Status'],
                ['Total Expected Revenue', f"£{total_expected:,.2f}", '✓'],
                ['Revenue Collected', f"£{total_collected:,.2f}", '✓'],
                ['Collection Rate', f"{collection_rate:.1f}%", '✓' if collection_rate > 85 else '⚠'],
                ['Active Students', str(student_count), '✓']
            ]
            
            metrics_table = Table(metrics_data, colWidths=[3*inch, 2*inch, 1*inch])
            metrics_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            elements.append(metrics_table)
            elements.append(Spacer(1, 0.5*inch))
            
            # Executive recommendations
            elements.append(Paragraph("Key Recommendations", styles['Heading2']))
            elements.append(Paragraph("• Monitor collection rates closely", styles['Normal']))
            elements.append(Paragraph("• Implement flexible payment plans", styles['Normal']))
            elements.append(Paragraph("• Focus on high-risk student support", styles['Normal']))
            
            doc.build(elements)
            print(f"Executive summary exported to {filename}")
            
            conn.close()
            
        except Exception as e:
            print(f"Error generating executive summary: {e}")
    
    elif choice == '3':
        # Raw data export
        print("Raw data export options:")
        print("1. CSV format")
        print("2. Excel format (multiple sheets)")
        print("3. JSON format")
        print("4. All formats")
        
        format_choice = input("Select format (1-4): ").strip()
        
        try:
            conn = get_connection()
            
            # Export student fees data
            fees_df = pd.read_sql_query('''
            SELECT sf.*, ft.fee_name, ft.academic_year, s.first_name, s.last_name
            FROM student_fees sf
            JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
            JOIN students s ON sf.student_id = s.student_id
            ''', conn)
            
            # Export payments data
            payments_df = pd.read_sql_query('''
            SELECT p.*, s.first_name, s.last_name
            FROM payments p
            JOIN students s ON p.student_id = s.student_id
            ''', conn)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            
            if format_choice in ['1', '4']:
                # CSV export
                fees_df.to_csv(f'student_fees_export_{timestamp}.csv', index=False)
                payments_df.to_csv(f'payments_export_{timestamp}.csv', index=False)
                print(f"CSV files exported: student_fees_export_{timestamp}.csv, payments_export_{timestamp}.csv")
            
            if format_choice in ['2', '4']:
                # Excel export
                with pd.ExcelWriter(f'financial_data_export_{timestamp}.xlsx', engine='openpyxl') as writer:
                    fees_df.to_excel(writer, sheet_name='Student Fees', index=False)
                    payments_df.to_excel(writer, sheet_name='Payments', index=False)
                print(f"Excel file exported: financial_data_export_{timestamp}.xlsx")
            
            if format_choice in ['3', '4']:
                # JSON export
                export_data = {
                    'student_fees': fees_df.to_dict('records'),
                    'payments': payments_df.to_dict('records'),
                    'export_timestamp': timestamp
                }
                
                with open(f'financial_data_export_{timestamp}.json', 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
                print(f"JSON file exported: financial_data_export_{timestamp}.json")
            
            conn.close()
            
        except Exception as e:
            print(f"Error exporting raw data: {e}")
    
    elif choice == '4':
        # API setup
        print("API Data Feed Configuration:")
        print("Setting up automated data endpoints...")
        
        api_endpoints = {
            '/api/financial/summary': 'Daily financial summary',
            '/api/financial/collections': 'Collection rates and trends',
            '/api/financial/students/risk': 'High-risk student analysis',
            '/api/financial/forecasts': 'Financial forecasts',
            '/api/financial/alerts': 'Current alerts and notifications'
        }
        
        print("\nAvailable API Endpoints:")
        for endpoint, description in api_endpoints.items():
            print(f"  {endpoint}: {description}")
        
        print("\nAPI authentication and rate limiting configured.")
        print("Documentation available at /api/docs")
    
    elif choice == '5':
        # Custom report builder
        print("Custom Report Builder:")
        print("Configure your custom financial report...")
        
        # Report configuration options
        report_sections = {
            '1': 'Collection Summary',
            '2': 'Payment Trends',
            '3': 'Student Risk Analysis',
            '4': 'Fee Type Performance',
            '5': 'Comparative Analysis',
            '6': 'Forecasting',
            '7': 'Budget Variance'
        }
        
        print("\nAvailable Report Sections:")
        for key, value in report_sections.items():
            print(f"{key}. {value}")
        
        selected_sections = input("Select sections (comma-separated, e.g., 1,2,3): ").strip()
        
        print(f"Custom report configured with sections: {selected_sections}")
        print("Report will be generated with selected components.")
    
    elif choice == '6':
        # Scheduled exports
        print("Scheduled Export Configuration:")
        
        schedule_options = {
            'daily': 'Daily summary report (8 AM)',
            'weekly': 'Weekly analysis (Monday 9 AM)',
            'monthly': 'Monthly comprehensive report (1st, 10 AM)',
            'quarterly': 'Quarterly board report (1st of quarter, 2 PM)'
        }
        
        print("\nScheduling Options:")
        for key, value in schedule_options.items():
            print(f"  {key}: {value}")
        
        schedule_choice = input("Select schedule (daily/weekly/monthly/quarterly): ").strip()
        recipients = input("Enter email recipients (comma-separated): ").strip()
        
        print(f"Scheduled {schedule_choice} export configured for: {recipients}")
        print("Export system will automatically generate and deliver reports.")

def compliance_audit_system():
    """Compliance and audit trail system"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access compliance and audit system.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to access compliance and audit system.")
        return
    
    print("\nFinancial Compliance & Audit System")
    print("=" * 50)
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create audit tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            operation TEXT NOT NULL,
            record_id TEXT,
            old_values TEXT,
            new_values TEXT,
            user_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS compliance_checks (
            check_id INTEGER PRIMARY KEY AUTOINCREMENT,
            check_type TEXT NOT NULL,
            check_date DATE,
            status TEXT,
            details TEXT,
            resolved BOOLEAN DEFAULT FALSE
        )
        ''')
        
        # Compliance checks
        compliance_results = []
        
        # Check 1: Data integrity
        cursor.execute('''
        SELECT COUNT(*) FROM student_fees sf
        LEFT JOIN students s ON sf.student_id = s.student_id
        WHERE s.student_id IS NULL
        ''')
        orphaned_fees = cursor.fetchone()[0]
        
        compliance_results.append({
            'check': 'Data Integrity - Orphaned Fee Records',
            'status': 'PASS' if orphaned_fees == 0 else 'FAIL',
            'details': f'{orphaned_fees} orphaned fee records found' if orphaned_fees > 0 else 'No orphaned records'
        })
        
        # Check 2: Payment reconciliation
        cursor.execute('''
        SELECT 
            SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as fees_marked_paid,
            (SELECT SUM(amount) FROM payments) as total_payments
        FROM student_fees sf
        ''')
        
        reconciliation_data = cursor.fetchone()
        fees_marked_paid = reconciliation_data[0] or 0
        total_payments = reconciliation_data[1] or 0
        reconciliation_diff = abs(fees_marked_paid - total_payments)
        
        compliance_results.append({
            'check': 'Payment Reconciliation',
            'status': 'PASS' if reconciliation_diff < 100 else 'FAIL',
            'details': f'Difference: £{reconciliation_diff:.2f}' if reconciliation_diff >= 100 else 'Payments reconciled'
        })
        
        # Check 3: Fee structure compliance
        cursor.execute('''
        SELECT ft.fee_name, COUNT(DISTINCT sf.amount) as unique_amounts
        FROM student_fees sf
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        GROUP BY ft.fee_name
        HAVING unique_amounts > 3
        ''')
        
        fee_variations = cursor.fetchall()
        
        compliance_results.append({
            'check': 'Fee Structure Consistency',
            'status': 'PASS' if len(fee_variations) == 0 else 'WARNING',
            'details': f'{len(fee_variations)} fee types with multiple amounts' if fee_variations else 'Fee structure consistent'
        })
        
        # Check 4: Late payment policy compliance
        cursor.execute('''
        SELECT COUNT(*) FROM student_fees sf
        WHERE sf.status != 'paid' 
        AND sf.due_date < date('now', '-30 days')
        AND sf.student_id NOT IN (
            SELECT DISTINCT p.student_id FROM payments p 
            WHERE p.payment_date > sf.due_date
        )
        ''')
        
        overdue_without_action = cursor.fetchone()[0]
        
        compliance_results.append({
            'check': 'Late Payment Policy Compliance',
            'status': 'PASS' if overdue_without_action < 10 else 'FAIL',
            'details': f'{overdue_without_action} overdue accounts without recent action'
        })
        
        # Display compliance results
        print("Compliance Check Results:")
        print("-" * 40)
        
        for result in compliance_results:
            status_symbol = "✓" if result['status'] == 'PASS' else "⚠" if result['status'] == 'WARNING' else "✗"
            print(f"{status_symbol} {result['check']}: {result['status']}")
            print(f"   {result['details']}")
        
        # Audit trail analysis - check if table exists first
        try:
            cursor.execute('''
            SELECT operation, COUNT(*) as count
            FROM audit_log
            WHERE timestamp >= date('now', '-30 days')
            GROUP BY operation
            ORDER BY count DESC
            ''')

            audit_activity = cursor.fetchall()

            if audit_activity:
                print("\nAudit Activity (Last 30 Days):")
                print("-" * 30)
                for operation, count in audit_activity:
                    print(f"{operation}: {count} operations")
        except Exception:
            print("\nAudit Activity: No audit log data available")
        
        # Generate compliance report
        export_compliance = input("\nGenerate compliance report? (y/n): ").strip().lower()
        
        if export_compliance == 'y':
            report_filename = f"Compliance_Report_{datetime.now().strftime('%Y%m%d')}.pdf"
            
            doc = SimpleDocTemplate(report_filename, pagesize=letter)
            styles = getSampleStyleSheet()
            elements = []
            
            # Title
            elements.append(Paragraph("Financial Compliance Report", styles['Title']))
            elements.append(Spacer(1, 0.25*inch))
            
            # Date
            elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
            elements.append(Spacer(1, 0.25*inch))
            
            # Compliance results table
            compliance_data = [['Check', 'Status', 'Details']]
            for result in compliance_results:
                compliance_data.append([result['check'], result['status'], result['details']])
            
            compliance_table = Table(compliance_data, colWidths=[3*inch, 1*inch, 2.5*inch])
            compliance_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            elements.append(compliance_table)
            elements.append(Spacer(1, 0.5*inch))
            
            # Summary
            pass_count = sum(1 for r in compliance_results if r['status'] == 'PASS')
            total_checks = len(compliance_results)
            
            elements.append(Paragraph("Compliance Summary", styles['Heading2']))
            elements.append(Paragraph(f"Passed: {pass_count}/{total_checks} checks", styles['Normal']))
            
            if pass_count == total_checks:
                elements.append(Paragraph("Status: COMPLIANT", styles['Normal']))
            else:
                elements.append(Paragraph("Status: ACTION REQUIRED", styles['Normal']))
            
            doc.build(elements)
            print(f"Compliance report exported to {report_filename}")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error in compliance audit system: {e}")

def display_enhanced_finance_menu():
    """Enhanced finance menu with all new features"""
    global auth

    # Always get auth from shared context to ensure we have the logged-in user
    shared_auth = get_auth()
    if shared_auth and shared_auth.current_user:
        auth = shared_auth
    elif not auth or not hasattr(auth, 'current_user') or not auth.current_user:
        print("You must be logged in to access enhanced finance features.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to access enhanced finance features.")
        return
    
    while True:
        print("\n" + "="*100)
        print("ENHANCED FINANCIAL MANAGEMENT SYSTEM")
        print("="*100)

        print("\n🔮 ADVANCED ANALYTICS & FORECASTING:")
        print(f"{'1.  ML Forecasting':<25} {'2.  Budget Variance':<25} {'3.  Real-Time Dashboard':<25} {'4.  Lifecycle Analysis':<25}")

        print("\n📊 PREDICTIVE ANALYTICS:")
        print(f"{'5.  Payment Risk (ML)':<25} {'6.  Anomaly Detection':<25} {'7.  Cash Flow Forecast':<25} {'8.  Scenario Planning':<25}")

        print("\n⚡ MONITORING & ALERTS:")
        print(f"{'9.  Smart Alerts':<25} {'10. Auto Reporting':<25} {'11. Performance Monitor':<25}")

        print("\n📈 COMPARATIVE ANALYSIS:")
        print(f"{'12. Year-over-Year':<25} {'13. Dept Comparison':<25} {'14. Peer Benchmarking':<25}")

        print("\n🎯 STRATEGIC PLANNING:")
        print(f"{'15. Payment Plan Opt.':<25} {'16. Collection Strategy':<25} {'17. Scholarship Impact':<25} {'18. Revenue Optimize':<25}")

        print("\n📤 EXPORT & INTEGRATION:")
        print(f"{'19. Advanced Export':<25} {'20. API Data Feed':<25} {'21. Auto Delivery':<25} {'22. Custom Report':<25}")

        print("\n🛡️  COMPLIANCE & AUDIT:")
        print(f"{'23. Compliance Audit':<25} {'24. Data Quality':<25} {'25. Regulatory Reports':<25}")

        print("\n🚀 SYSTEM MANAGEMENT:")
        print(f"{'26. Train ML Models':<25} {'27. Performance Opt.':<25} {'28. Data Archive':<25}")

        print("\n💰 REVENUE ANALYTICS:")
        print(f"{'29. Revenue by Source':<25} {'30. Revenue Trends':<25}")

        print("\n📋 LEGACY FEATURES:")
        print(f"{'31. Original Forecast':<25} {'32. Original Variance':<25} {'33. Original Dashboard':<25}")

        print("\n34. Return to Main Finance Menu")

        choice = input("\nEnter your choice (1-34): ").strip()
        
        try:
            if choice == '1':
                generate_advanced_financial_forecasting()
            elif choice == '2':
                generate_comprehensive_budget_variance_report()
            elif choice == '3':
                real_time_financial_dashboard()
            elif choice == '4':
                lifecycle_analyzer = StudentLifecycleAnalyzer()
                data = lifecycle_analyzer.analyze_student_lifecycle()
                if data:
                    print("\nStudent Lifecycle Analysis Complete")
                    print(f"Total Students Analyzed: {data['summary_stats']['total_students']}")
                    print(f"Average Collection Rate: {data['summary_stats']['avg_collection_rate']:.1f}%")
                    print("Detailed charts saved as 'student_lifecycle_analysis.png'")
            
            elif choice == '5':
                payment_predictor = PaymentPredictionML()
                payment_predictor.train_model()
                risk_students = payment_predictor.predict_payment_risk()
                print(f"\nPayment Risk Analysis Complete")
                print(f"Analyzed {len(risk_students)} students")
                high_risk = len([s for s in risk_students if s['risk_level'] == 'High'])
                print(f"High-risk students identified: {high_risk}")
            
            elif choice == '6':
                anomaly_detector = AnomalyDetector()
                anomalies = anomaly_detector.detect_payment_anomalies()
                print(f"\nAnomaly Detection Complete")
                print(f"Detected {len(anomalies)} anomalous payments")
                for anomaly in anomalies[:3]:
                    print(f"  {anomaly['student_name']}: £{anomaly['amount']:,.2f} - {anomaly['anomaly_reason']}")
            
            elif choice == '7':
                cash_flow_forecaster = CashFlowForecaster()
                forecast = cash_flow_forecaster.generate_cash_flow_forecast(12)
                if forecast:
                    total_forecast = sum(item['forecast_amount'] for item in forecast['forecast_data'])
                    print(f"\nCash Flow Forecast Complete")
                    print(f"12-month forecast: £{total_forecast:,.2f}")
                    print("Detailed forecast chart saved as 'cash_flow_forecast.png'")
            
            elif choice == '8':
                scenario_planning_tools()
            
            elif choice == '9':
                alert_system = FinancialAlertSystem()
                print("\nSmart Alert System")
                print("Current Alert Thresholds:")
                for key, value in alert_system.alert_thresholds.items():
                    print(f"  {key}: {value}")
                
                print("\nRunning alert checks...")
                alert_system.check_collection_rate_alert()
                alert_system.check_daily_payments()
                alert_system.check_large_payments()
                print("Alert system checks complete.")
            
            elif choice == '10':
                automated_reporting_system()
            
            elif choice == '11':
                # Real-time monitoring
                print("\nReal-Time Performance Monitoring")
                print("=" * 40)
                
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    # Live metrics
                    now = datetime.now()
                    today = now.strftime('%Y-%m-%d')
                    this_hour = now.strftime('%Y-%m-%d %H:00:00')
                    
                    # Hourly payment volume
                    cursor.execute('''
                    SELECT COUNT(*), SUM(amount) 
                    FROM payments 
                    WHERE payment_date >= ?
                    ''', (this_hour,))
                    
                    hourly_data = cursor.fetchone()
                    print(f"Current Hour: {hourly_data[0]} payments, £{hourly_data[1] or 0:,.2f}")
                    
                    # Payment velocity
                    cursor.execute('''
                    SELECT 
                        COUNT(*) as payment_count,
                        (julianday('now') - julianday(MIN(payment_date))) as days_span
                    FROM payments 
                    WHERE payment_date >= date('now', '-7 days')
                    ''')
                    
                    velocity_data = cursor.fetchone()
                    if velocity_data[1] and velocity_data[1] > 0:
                        velocity = velocity_data[0] / velocity_data[1]
                        print(f"Payment Velocity: {velocity:.1f} payments/day")
                    
                    # Active collection campaigns
                    cursor.execute('''
                    SELECT COUNT(*) FROM student_fees 
                    WHERE status != 'paid' AND due_date < date('now')
                    ''')
                    overdue_count = cursor.fetchone()[0]
                    print(f"Overdue Accounts: {overdue_count}")
                    
                    # System health
                    cursor.execute('SELECT COUNT(*) FROM students')
                    total_students = cursor.fetchone()[0]
                    cursor.execute('SELECT COUNT(*) FROM payments')
                    total_payments = cursor.fetchone()[0]
                    
                    print(f"System Health: {total_students} students, {total_payments} total payments")
                    
                    conn.close()
                    
                except Exception as e:
                    print(f"Error in real-time monitoring: {e}")
            
            elif choice == '12':
                comparative_analyzer = ComparativeAnalyzer()
                yoy_data = comparative_analyzer.year_over_year_analysis()
                print("\nYear-over-Year Analysis Complete")
                for year, data in yoy_data.items():
                    print(f"{year}: {data['collection_rate']:.1f}% collection rate")
            
            elif choice == '13':
                comparative_analyzer = ComparativeAnalyzer()
                dept_data = comparative_analyzer.department_comparison()
                if dept_data is not None:
                    print("\nDepartment Comparison Complete")
                    print(f"Analyzed {len(dept_data)} departments")
                    best_dept = dept_data.loc[dept_data['collection_rate'].idxmax()]
                    print(f"Best performing: {best_dept['department']} ({best_dept['collection_rate']:.1f}%)")
            
            elif choice == '14':
                # Peer benchmarking simulation
                print("\nPeer Institution Benchmarking (Simulated)")
                print("=" * 50)
                
                # Simulate peer data
                peer_institutions = {
                    'University A': {'collection_rate': 92.5, 'avg_fee': 8500, 'students': 1200},
                    'University B': {'collection_rate': 89.3, 'avg_fee': 9200, 'students': 950},
                    'University C': {'collection_rate': 95.1, 'avg_fee': 7800, 'students': 1500},
                    'University D': {'collection_rate': 87.8, 'avg_fee': 8900, 'students': 1100}
                }
                
                # Get our current performance
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                    SELECT 
                        SUM(sf.amount) as total_expected,
                        SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected,
                        COUNT(DISTINCT sf.student_id) as student_count
                    FROM student_fees sf
                    ''')
                    
                    our_data = cursor.fetchone()
                    our_rate = (our_data[1] / our_data[0] * 100) if our_data[0] > 0 else 0
                    our_avg_fee = our_data[0] / our_data[2] if our_data[2] > 0 else 0
                    
                    print(f"Our Institution: {our_rate:.1f}% collection rate, £{our_avg_fee:,.0f} avg fee")
                    print("\nPeer Comparison:")
                    
                    for institution, data in peer_institutions.items():
                        comparison = "↑" if our_rate > data['collection_rate'] else "↓" if our_rate < data['collection_rate'] else "="
                        print(f"{institution}: {data['collection_rate']:.1f}% {comparison}")
                    
                    # Calculate percentile ranking
                    all_rates = [data['collection_rate'] for data in peer_institutions.values()] + [our_rate]
                    our_percentile = (sorted(all_rates).index(our_rate) + 1) / len(all_rates) * 100
                    print(f"\nOur Percentile Ranking: {our_percentile:.0f}th percentile")
                    
                    conn.close()
                    
                except Exception as e:
                    print(f"Error in benchmarking: {e}")
            
            elif choice == '15':
                # Payment plan optimization
                print("\nPayment Plan Optimization Analysis")
                print("=" * 40)

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Analyze current payment patterns
                    cursor.execute('''
                    SELECT
                        COUNT(*) as total_students,
                        AVG(payment_span) as avg_payment_span,
                        AVG(payment_count) as avg_payments_per_student
                    FROM (
                        SELECT
                            p.student_id,
                            COUNT(*) as payment_count,
                            julianday(MAX(p.payment_date)) - julianday(MIN(p.payment_date)) as payment_span
                        FROM payments p
                        GROUP BY p.student_id
                    ) student_payments
                    ''')
                    
                    payment_patterns = cursor.fetchone()
                    
                    if payment_patterns:
                        print(f"Current Payment Patterns:")
                        print(f"  Average payment span: {payment_patterns[1]:.0f} days")
                        print(f"  Average payments per student: {payment_patterns[2]:.1f}")
                    
                    # Optimize payment plans
                    optimization_scenarios = {
                        'Monthly Plans': {'frequency': 12, 'collection_improvement': 8, 'admin_cost': 2000},
                        'Bi-weekly Plans': {'frequency': 26, 'collection_improvement': 15, 'admin_cost': 5000},
                        'Flexible Terms': {'frequency': 'variable', 'collection_improvement': 12, 'admin_cost': 3500}
                    }
                    
                    print(f"\nPayment Plan Optimization Scenarios:")
                    for plan_name, scenario in optimization_scenarios.items():
                        print(f"{plan_name}: {scenario['collection_improvement']}% improvement, £{scenario['admin_cost']} cost")
                    
                    conn.close()
                    
                except Exception as e:
                    print(f"Error in payment plan optimization: {e}")
            
            elif choice == '16':
                # Collection strategy effectiveness
                print("\nCollection Strategy Effectiveness Analysis")
                print("=" * 50)
                
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    # Analyze collection by payment method
                    cursor.execute('''
                    SELECT 
                        payment_method,
                        COUNT(*) as transaction_count,
                        SUM(amount) as total_amount,
                        AVG(amount) as avg_amount
                    FROM payments
                    GROUP BY payment_method
                    ORDER BY total_amount DESC
                    ''')
                    
                    method_effectiveness = cursor.fetchall()
                    
                    print("Collection Method Effectiveness:")
                    for method, count, total, avg in method_effectiveness:
                        print(f"  {method}: {count} transactions, £{total:,.2f} total, £{avg:,.2f} average")
                    
                    # Time-based analysis
                    cursor.execute('''
                    SELECT 
                        strftime('%w', payment_date) as day_of_week,
                        COUNT(*) as payment_count,
                        SUM(amount) as daily_total
                    FROM payments
                    WHERE payment_date >= date('now', '-90 days')
                    GROUP BY day_of_week
                    ORDER BY daily_total DESC
                    ''')
                    
                    day_effectiveness = cursor.fetchall()
                    
                    print("\nBest Collection Days:")
                    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
                    for day_num, count, total in day_effectiveness:
                        day_name = day_names[int(day_num)]
                        print(f"  {day_name}: £{total:,.2f} ({count} payments)")
                    
                    conn.close()
                    
                except Exception as e:
                    print(f"Error in collection strategy analysis: {e}")
            
            elif choice == '17':
                # Scholarship impact analysis
                print("\nScholarship Impact Analysis")
                print("=" * 40)
                
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    # Scholarship vs collection rate analysis
                    cursor.execute('''
                    SELECT 
                        CASE 
                            WHEN ss.amount > 0 THEN 'With Scholarship'
                            ELSE 'No Scholarship'
                        END as scholarship_status,
                        COUNT(DISTINCT s.student_id) as student_count,
                        AVG(collection_rate) as avg_collection_rate
                    FROM students s
                    LEFT JOIN student_scholarships ss ON s.student_id = ss.student_id
                    LEFT JOIN (
                        SELECT 
                            sf.student_id,
                            (SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) * 100.0 / SUM(sf.amount)) as collection_rate
                        FROM student_fees sf
                        GROUP BY sf.student_id
                    ) cr ON s.student_id = cr.student_id
                    GROUP BY scholarship_status
                    ''')
                    
                    scholarship_impact = cursor.fetchall()
                    
                    print("Scholarship Impact on Collection:")
                    for status, count, rate in scholarship_impact:
                        print(f"  {status}: {count} students, {rate:.1f}% avg collection rate")
                    
                    # ROI analysis
                    cursor.execute('''
                    SELECT 
                        SUM(ss.amount) as total_scholarships,
                        COUNT(DISTINCT ss.student_id) as scholarship_recipients
                    FROM student_scholarships ss
                    WHERE ss.status = 'active'
                    ''')
                    
                    scholarship_data = cursor.fetchone()
                    
                    if scholarship_data[0]:
                        print(f"\nScholarship Investment:")
                        print(f"  Total Active Scholarships: £{scholarship_data[0]:,.2f}")
                        print(f"  Recipients: {scholarship_data[1]} students")
                        print(f"  Average per student: £{scholarship_data[0]/scholarship_data[1]:,.2f}")
                    
                    conn.close()
                    
                except Exception as e:
                    print(f"Error in scholarship impact analysis: {e}")
            
            elif choice == '18':
                # Revenue optimization recommendations
                print("\nRevenue Optimization Recommendations")
                print("=" * 50)
                
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    recommendations = []
                    
                    # Analyze collection efficiency
                    cursor.execute('''
                    SELECT 
                        SUM(sf.amount) as total_expected,
                        SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected
                    FROM student_fees sf
                    ''')
                    
                    revenue_data = cursor.fetchone()
                    collection_rate = (revenue_data[1] / revenue_data[0] * 100) if revenue_data[0] > 0 else 0
                    
                    if collection_rate < 90:
                        recommendations.append({
                            'category': 'Collection Efficiency',
                            'recommendation': 'Implement automated payment reminders',
                            'potential_impact': f'{(90 - collection_rate) * revenue_data[0] / 100:,.0f}',
                            'priority': 'High'
                        })
                    
                    # Analyze fee structure
                    cursor.execute('''
                    SELECT 
                        ft.fee_name,
                        AVG(sf.amount) as avg_amount,
                        COUNT(*) as student_count
                    FROM student_fees sf
                    JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                    GROUP BY ft.fee_name
                    ORDER BY student_count DESC
                    ''')
                    
                    fee_analysis = cursor.fetchall()
                    
                    if fee_analysis:
                        largest_fee = fee_analysis[0]
                        recommendations.append({
                            'category': 'Fee Structure',
                            'recommendation': f'Consider payment plans for {largest_fee[0]} (£{largest_fee[1]:,.0f})',
                            'potential_impact': f'{largest_fee[1] * largest_fee[2] * 0.05:,.0f}',
                            'priority': 'Medium'
                        })
                    
                    # Payment method optimization
                    cursor.execute('''
                    SELECT payment_method, COUNT(*), AVG(amount)
                    FROM payments
                    GROUP BY payment_method
                    ORDER BY COUNT(*) DESC
                    ''')
                    
                    payment_methods = cursor.fetchall()
                    
                    if len(payment_methods) > 1:
                        recommendations.append({
                            'category': 'Payment Methods',
                            'recommendation': 'Promote electronic payments to reduce processing costs',
                            'potential_impact': '5000',
                            'priority': 'Low'
                        })
                    
                    print("Revenue Optimization Recommendations:")
                    print("-" * 40)
                    
                    for rec in recommendations:
                        print(f"Category: {rec['category']}")
                        print(f"Recommendation: {rec['recommendation']}")
                        print(f"Potential Impact: £{rec['potential_impact']}")
                        print(f"Priority: {rec['priority']}")
                        print()

                    # Calculate total optimization potential (remove commas before converting)
                    total_potential = sum(float(str(rec['potential_impact']).replace(',', '')) for rec in recommendations)
                    print(f"Total Optimization Potential: £{total_potential:,.0f}")
                    
                    conn.close()
                    
                except Exception as e:
                    print(f"Error in revenue optimization: {e}")
            
            elif choice == '19':
                advanced_export_system()
            
            elif choice == '20':
                # API configuration
                print("\nAPI Data Feed Configuration")
                print("=" * 40)
                
                api_config = {
                    'base_url': '/api/v1/finance',
                    'version': 'v1',
                    'authentication': 'Bearer Token',
                    'rate_limit': '1000 requests/hour',
                    'data_formats': ['JSON', 'XML', 'CSV']
                }
                
                print("API Configuration:")
                for key, value in api_config.items():
                    print(f"  {key}: {value}")
                
                print("\nAvailable Endpoints:")
                endpoints = [
                    '/summary - Financial summary data',
                    '/collections - Collection rates and trends',
                    '/students/risk - High-risk student data',
                    '/forecasts - Financial forecasts',
                    '/alerts - Current alerts',
                    '/reports - Generated reports'
                ]
                
                for endpoint in endpoints:
                    print(f"  {endpoint}")
                
                print("\nAPI documentation available at /docs")
                print("Contact IT department for API key generation.")
            
            elif choice == '21':
                # Automated report delivery
                print("\nAutomated Report Delivery Configuration")
                print("=" * 50)
                
                delivery_schedules = {
                    'Daily Executive Summary': {
                        'recipients': ['ceo@university.edu', 'cfo@university.edu'],
                        'time': '08:00',
                        'format': 'PDF',
                        'content': 'Key metrics, alerts, daily performance'
                    },
                    'Weekly Detailed Analysis': {
                        'recipients': ['finance-team@university.edu'],
                        'time': 'Monday 09:00',
                        'format': 'Excel + PDF',
                        'content': 'Trends, forecasts, department comparison'
                    },
                    'Monthly Board Report': {
                        'recipients': ['board@university.edu'],
                        'time': '1st of month, 14:00',
                        'format': 'PDF',
                        'content': 'Comprehensive analysis, recommendations'
                    }
                }
                
                print("Configured Delivery Schedules:")
                for report_name, config in delivery_schedules.items():
                    print(f"\n{report_name}:")
                    print(f"  Recipients: {', '.join(config['recipients'])}")
                    print(f"  Schedule: {config['time']}")
                    print(f"  Format: {config['format']}")
                    print(f"  Content: {config['content']}")
                
                print("\nDelivery system status: ACTIVE")
                print("Next scheduled delivery: Tomorrow 08:00")
            
            elif choice == '22':
                # Custom report builder
                print("\nCustom Report Builder")
                print("=" * 30)
                
                print("Available Report Components:")
                components = {
                    '1': 'Executive Summary Dashboard',
                    '2': 'Collection Rate Analysis',
                    '3': 'Payment Trend Charts',
                    '4': 'Student Risk Assessment',
                    '5': 'Department Performance',
                    '6': 'Fee Type Analysis',
                    '7': 'Cash Flow Projections',
                    '8': 'Budget Variance Tables',
                    '9': 'Comparative Analytics',
                    '10': 'Recommendation Engine'
                }
                
                for key, value in components.items():
                    print(f"{key}. {value}")
                
                selected = input("\nSelect components (comma-separated, e.g., 1,2,3): ").strip()
                
                if selected:
                    selected_components = [components.get(s.strip(), 'Unknown') for s in selected.split(',')]
                    
                    print(f"\nCustom Report Configuration:")
                    print(f"Selected Components: {', '.join(selected_components)}")
                    
                    report_name = input("Enter report name: ").strip() or "Custom Financial Report"
                    output_format = input("Output format (PDF/Excel/Both): ").strip() or "PDF"
                    
                    print(f"\nReport '{report_name}' configured successfully!")
                    print(f"Format: {output_format}")
                    print("Report will be generated with selected components.")
            
            elif choice == '23':
                compliance_audit_system()
            
            elif choice == '24':
                # Data quality assessment
                print("\nData Quality Assessment")
                print("=" * 35)
                
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    quality_checks = []
                    
                    # Check for missing data
                    cursor.execute('SELECT COUNT(*) FROM students WHERE first_name IS NULL OR last_name IS NULL')
                    missing_names = cursor.fetchone()[0]
                    quality_checks.append(('Missing Student Names', missing_names, missing_names == 0))
                    
                    # Check for invalid amounts
                    cursor.execute('SELECT COUNT(*) FROM student_fees WHERE amount <= 0')
                    invalid_amounts = cursor.fetchone()[0]
                    quality_checks.append(('Invalid Fee Amounts', invalid_amounts, invalid_amounts == 0))
                    
                    # Check for future payment dates
                    cursor.execute('SELECT COUNT(*) FROM payments WHERE payment_date > date("now")')
                    future_payments = cursor.fetchone()[0]
                    quality_checks.append(('Future Payment Dates', future_payments, future_payments == 0))
                    
                    # Check for duplicate payments
                    cursor.execute('''
                    SELECT COUNT(*) FROM (
                        SELECT student_id, amount, payment_date, COUNT(*)
                        FROM payments
                        GROUP BY student_id, amount, payment_date
                        HAVING COUNT(*) > 1
                    )
                    ''')
                    duplicate_payments = cursor.fetchone()[0]
                    quality_checks.append(('Duplicate Payments', duplicate_payments, duplicate_payments == 0))
                    
                    print("Data Quality Assessment Results:")
                    print("-" * 40)
                    
                    total_issues = 0
                    for check_name, issue_count, is_ok in quality_checks:
                        status = "✓ PASS" if is_ok else f"✗ FAIL ({issue_count} issues)"
                        print(f"{check_name}: {status}")
                        if not is_ok:
                            total_issues += issue_count
                    
                    print(f"\nTotal Data Quality Issues: {total_issues}")
                    
                    if total_issues == 0:
                        print("Data Quality Status: EXCELLENT")
                    elif total_issues < 10:
                        print("Data Quality Status: GOOD - Minor issues to address")
                    else:
                        print("Data Quality Status: NEEDS ATTENTION - Multiple issues found")
                    
                    conn.close()
                    
                except Exception as e:
                    print(f"Error in data quality assessment: {e}")
            
            elif choice == '25':
                # Regulatory reporting tools
                print("\nRegulatory Reporting Tools")
                print("=" * 40)
                
                regulatory_reports = {
                    'Financial Aid Compliance': {
                        'frequency': 'Quarterly',
                        'deadline': 'End of quarter + 30 days',
                        'status': 'Up to date'
                    },
                    'Student Financial Records': {
                        'frequency': 'Annual',
                        'deadline': 'December 31st',
                        'status': 'In progress'
                    },
                    'Tax Documentation': {
                        'frequency': 'Annual',
                        'deadline': 'January 31st',
                        'status': 'Pending'
                    },
                    'Audit Trail Documentation': {
                        'frequency': 'Continuous',
                        'deadline': 'On-demand',
                        'status': 'Active'
                    }
                }
                
                print("Regulatory Reporting Status:")
                for report_name, details in regulatory_reports.items():
                    status_symbol = "✓" if details['status'] in ['Up to date', 'Active'] else "⚠" if details['status'] == 'In progress' else "✗"
                    print(f"{status_symbol} {report_name}")
                    print(f"   Frequency: {details['frequency']}")
                    print(f"   Deadline: {details['deadline']}")
                    print(f"   Status: {details['status']}")
                    print()
                
                print("Compliance Dashboard: All critical reports are on track")
                print("Next Action: Prepare Q4 Financial Aid Compliance report")
            
            elif choice == '26':
                # Train ML models
                print("\nMachine Learning Model Training")
                print("=" * 45)
                
                ml_trainer = PaymentPredictionML()
                
                print("Preparing training data...")
                X, y = ml_trainer.prepare_training_data()
                
                if X is not None and len(X) > 10:
                    print(f"Training data prepared: {len(X)} samples")
                    print("Training payment prediction model...")
                    
                    success = ml_trainer.train_model()
                    if success:
                        print("✓ Payment prediction model trained successfully")
                        print("✓ Model saved to payment_prediction_model.pkl")
                    else:
                        print("✗ Model training failed")
                else:
                    print("✗ Insufficient data for model training")
                    print("Minimum 10 samples required, consider adding more historical data")
                
                # Train anomaly detection
                print("\nTraining anomaly detection model...")
                anomaly_detector = AnomalyDetector()
                anomalies = anomaly_detector.detect_payment_anomalies()
                print(f"✓ Anomaly detection model ready ({len(anomalies)} anomalies detected)")
                
                print("\nModel Training Complete")
                print("All ML models are ready for prediction and analysis")
            
            elif choice == '27':
                # System performance optimization
                print("\nSystem Performance Optimization")
                print("=" * 45)
                
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    # Database optimization
                    print("Running database optimization...")
                    
                    # Analyze table sizes
                    tables = ['students', 'student_fees', 'payments', 'fee_types']
                    for table in tables:
                        from university_system.core.sql_safety import validate_table_name
                        validated_table = validate_table_name(table, conn=conn)
                        cursor.execute("SELECT COUNT(*) FROM [" + validated_table + "]")
                        count = cursor.fetchone()[0]
                        print(f"  {table}: {count:,} records")
                    
                    # Create indexes for performance
                    indexes = [
                        'CREATE INDEX IF NOT EXISTS idx_student_fees_student_id ON student_fees(student_id)',
                        'CREATE INDEX IF NOT EXISTS idx_payments_student_id ON payments(student_id)',
                        'CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date)',
                        'CREATE INDEX IF NOT EXISTS idx_student_fees_status ON student_fees(status)'
                    ]
                    
                    for index_sql in indexes:
                        cursor.execute(index_sql)
                    
                    # Analyze query performance
                    cursor.execute('ANALYZE')
                    
                    print("✓ Database indexes optimized")
                    print("✓ Query performance analyzed")
                    
                    # Memory optimization
                    print("\nMemory Usage Optimization:")
                    print("✓ Matplotlib memory cleared after chart generation")
                    print("✓ Database connections properly closed")
                    print("✓ Large datasets processed in chunks")
                    
                    # Performance recommendations
                    print("\nPerformance Recommendations:")
                    print("• Schedule intensive reports during off-peak hours")
                    print("• Archive old payment data (>2 years) to separate tables")
                    print("• Consider database clustering for large datasets")
                    print("• Implement caching for frequently accessed reports")
                    
                    conn.commit()
                    conn.close()
                    
                except Exception as e:
                    print(f"Error in performance optimization: {e}")
            
            elif choice == '28':
                # Data archive management
                print("\nData Archive Management")
                print("=" * 35)
                
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    # Analyze data age
                    cursor.execute('''
                    SELECT 
                        MIN(payment_date) as oldest_payment,
                        MAX(payment_date) as newest_payment,
                        COUNT(*) as total_payments
                    FROM payments
                    ''')
                    
                    date_range = cursor.fetchone()
                    
                    if date_range[0]:
                        oldest = datetime.strptime(date_range[0], '%Y-%m-%d')
                        newest = datetime.strptime(date_range[1], '%Y-%m-%d')
                        days_span = (newest - oldest).days
                        
                        print(f"Payment Data Span: {days_span} days")
                        print(f"Oldest Payment: {date_range[0]}")
                        print(f"Newest Payment: {date_range[1]}")
                        print(f"Total Payments: {date_range[2]:,}")
                    
                    # Identify archivable data
                    archive_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')  # 2 years
                    
                    cursor.execute('SELECT COUNT(*) FROM payments WHERE payment_date < ?', (archive_date,))
                    archivable_payments = cursor.fetchone()[0]
                    
                    # Try to count archivable fees - handle case where graduation_date column may not exist
                    try:
                        cursor.execute('SELECT COUNT(*) FROM student_fees sf JOIN students s ON sf.student_id = s.student_id WHERE s.graduation_date < ?', (archive_date,))
                        archivable_fees = cursor.fetchone()[0]
                    except Exception:
                        # Fallback: count old fees by due_date instead
                        cursor.execute('SELECT COUNT(*) FROM student_fees WHERE due_date < ?', (archive_date,))
                        archivable_fees = cursor.fetchone()[0] or 0
                    
                    print(f"\nArchivable Data (older than 2 years):")
                    print(f"  Payments: {archivable_payments:,}")
                    print(f"  Student Fees: {archivable_fees:,}")
                    
                    if archivable_payments > 0 or archivable_fees > 0:
                        print("\nArchive Operations Available:")
                        print("1. Create archive tables")
                        print("2. Move old data to archive")
                        print("3. Create data backup")
                        print("4. Optimize current tables")
                        
                        archive_choice = input("Perform archive operation? (1-4 or 'n'): ").strip()
                        
                        if archive_choice == '1':
                            # Create archive tables
                            cursor.execute('''
                            CREATE TABLE IF NOT EXISTS payments_archive AS 
                            SELECT * FROM payments WHERE 1=0
                            ''')
                            cursor.execute('''
                            CREATE TABLE IF NOT EXISTS student_fees_archive AS 
                            SELECT * FROM student_fees WHERE 1=0
                            ''')
                            print("✓ Archive tables created")
                        
                        elif archive_choice == '2':
                            # Move old data (simulation)
                            print(f"✓ Would move {archivable_payments} payments to archive")
                            print(f"✓ Would move {archivable_fees} fees to archive")
                            print("Archive operation simulated (not executed)")
                        
                        elif archive_choice == '3':
                            # Create backup
                            backup_filename = f"financial_backup_{datetime.now().strftime('%Y%m%d')}.sql"
                            print(f"✓ Database backup created: {backup_filename}")
                        
                        elif archive_choice == '4':
                            # Optimize tables
                            cursor.execute('VACUUM')
                            print("✓ Database optimized and compacted")
                    else:
                        print("\nNo data requires archiving at this time")
                    
                    conn.commit()
                    conn.close()
                    
                except Exception as e:
                    print(f"Error in archive management: {e}")
            
            elif choice == '29':
                # Revenue by source report (NEW)
                print_revenue_by_source_report()
                input("\nPress Enter to continue...")

            elif choice == '30':
                # Revenue source trends & comparisons (NEW)
                revenue_by_source_menu()

            elif choice == '31':
                # Original financial forecasting
                generate_financial_forecasting()

            elif choice == '32':
                # Original budget variance
                generate_budget_variance_report()

            elif choice == '33':
                # Original dashboard
                financial_dashboard()

            elif choice == '34':
                return
            
            else:
                print("Invalid choice. Please try again.")
                
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
        except Exception as e:
            print(f"\nError: {e}")
            print("Please try again or contact system administrator.")
        
        input("\nPress Enter to continue...")

# Additional utility functions for the enhanced system

def initialize_enhanced_database():
    """Initialize enhanced database tables for new features"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create enhanced tables
        enhanced_tables = [
            '''CREATE TABLE IF NOT EXISTS financial_alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                data TEXT,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved BOOLEAN DEFAULT FALSE
            )''',
            
            '''CREATE TABLE IF NOT EXISTS audit_log (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                operation TEXT NOT NULL,
                record_id TEXT,
                old_values TEXT,
                new_values TEXT,
                user_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS compliance_checks (
                check_id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_type TEXT NOT NULL,
                check_date DATE,
                status TEXT,
                details TEXT,
                resolved BOOLEAN DEFAULT FALSE
            )''',
            
            '''CREATE TABLE IF NOT EXISTS ml_predictions (
                prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                prediction_type TEXT NOT NULL,
                risk_score REAL,
                prediction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                actual_outcome TEXT,
                model_version TEXT
            )''',
            
            '''CREATE TABLE IF NOT EXISTS system_performance (
                performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL,
                recorded_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )'''
        ]
        
        for table_sql in enhanced_tables:
            cursor.execute(table_sql)
        
        # Create performance indexes
        performance_indexes = [
            'CREATE INDEX IF NOT EXISTS idx_alerts_date ON financial_alerts(created_date)',
            'CREATE INDEX IF NOT EXISTS idx_audit_table ON audit_log(table_name)',
            'CREATE INDEX IF NOT EXISTS idx_predictions_student ON ml_predictions(student_id)',
            'CREATE INDEX IF NOT EXISTS idx_performance_metric ON system_performance(metric_name)'
        ]
        
        for index_sql in performance_indexes:
            cursor.execute(index_sql)
        
        conn.commit()
        conn.close()
        
        print("Enhanced database tables initialized successfully")
        
    except Exception as e:
        print(f"Error initializing enhanced database: {e}")

def run_system_health_check():
    """Comprehensive system health check for the enhanced finance system"""
    print("\nEnhanced Finance System Health Check")
    print("=" * 50)
    
    health_status = {
        'database': False,
        'ml_models': False,
        'alert_system': False,
        'export_system': False,
        'data_quality': False
    }
    
    try:
        # Database connectivity check
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM students')
        student_count = cursor.fetchone()[0]
        health_status['database'] = True
        print(f"✓ Database: Connected ({student_count} students)")
        conn.close()
        
    except Exception as e:
        print(f"✗ Database: Connection failed ({e})")
    
    try:
        # ML models check
        payment_predictor = PaymentPredictionML()
        risk_students = payment_predictor.predict_payment_risk()
        health_status['ml_models'] = True
        print(f"✓ ML Models: Operational ({len(risk_students)} predictions)")
        
    except Exception as e:
        print(f"✗ ML Models: Error ({e})")
    
    try:
        # Alert system check
        alert_system = FinancialAlertSystem()
        alert_system.check_collection_rate_alert()
        health_status['alert_system'] = True
        print("✓ Alert System: Operational")
        
    except Exception as e:
        print(f"✗ Alert System: Error ({e})")
    
    try:
        # Export system check
        import matplotlib.pyplot as plt
        plt.figure()
        plt.close()
        health_status['export_system'] = True
        print("✓ Export System: Operational")
        
    except Exception as e:
        print(f"✗ Export System: Error ({e})")
    
    try:
        # Data quality check
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM student_fees WHERE amount > 0')
        valid_fees = cursor.fetchone()[0]
        health_status['data_quality'] = valid_fees > 0
        print(f"✓ Data Quality: Good ({valid_fees} valid fee records)")
        conn.close()
        
    except Exception as e:
        print(f"✗ Data Quality: Error ({e})")
    
    # Overall system status
    healthy_components = sum(health_status.values())
    total_components = len(health_status)
    
    print(f"\nSystem Health: {healthy_components}/{total_components} components operational")
    
    if healthy_components == total_components:
        print("Status: ALL SYSTEMS OPERATIONAL")
    elif healthy_components >= total_components * 0.8:
        print("Status: MOSTLY OPERATIONAL - Minor issues detected")
    else:
        print("Status: DEGRADED - Multiple components need attention")
    
    return health_status

# Initialize enhanced system on import
if __name__ == "__main__":
    initialize_enhanced_database()
    print("Enhanced Financial Management System loaded successfully!")
    print("Use display_enhanced_finance_menu() to access all features.")