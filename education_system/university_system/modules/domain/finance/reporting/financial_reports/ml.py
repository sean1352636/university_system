import pickle
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score

from education_system.university_system.infrastructure.database.db import get_connection


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
