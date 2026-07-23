"""Predictive analytics for attendance risk assessment."""

import datetime
import json
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.modules.domain.academics.services.attendance.settings import get_setting


class AttendancePredictiveAnalytics:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = [
            'current_attendance_rate', 'consecutive_absences', 'days_since_last_attendance',
            'total_sessions', 'week_of_term', 'day_of_week', 'previous_module_performance'
        ]

    def prepare_training_data(self):
        """Prepare training data for the predictive model"""
        import pandas as pd
        try:
            conn = get_connection()

            # Get historical attendance data
            query = '''
            SELECT
                ar.student_id,
                ar.module_code,
                ar.date,
                ar.status,
                COUNT(*) OVER (PARTITION BY ar.student_id, ar.module_code) as total_sessions,
                AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END)
                    OVER (PARTITION BY ar.student_id, ar.module_code
                          ORDER BY ar.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as running_attendance_rate
            FROM attendance_records ar
            ORDER BY ar.student_id, ar.module_code, ar.date
            '''

            df = pd.read_sql_query(query, conn)
            conn.close()

            if df.empty:
                return None, None

            # Feature engineering
            df['date'] = pd.to_datetime(df['date'])
            df['day_of_week'] = df['date'].dt.dayofweek
            df['week_of_term'] = df['date'].dt.isocalendar().week % 52
            df['is_present'] = df['status'].isin(['Present', 'Late']).astype(int)

            # Calculate features for each student-module combination
            features = []
            targets = []

            for (student_id, module_code), group in df.groupby(['student_id', 'module_code']):
                group = group.sort_values('date')

                for i in range(5, len(group)):  # Need at least 5 sessions for prediction
                    current_data = group.iloc[:i]
                    future_window = group.iloc[i:i+5]  # Predict next 5 sessions

                    # Current features
                    current_attendance_rate = current_data['is_present'].mean()
                    consecutive_absences = self._calculate_consecutive_absences(current_data['is_present'].values)
                    days_since_last = (current_data['date'].iloc[-1] - current_data[current_data['is_present'] == 1]['date'].iloc[-1] if (current_data['is_present'] == 1).any() else pd.Timedelta(days=999)).days

                    feature_row = [
                        current_attendance_rate,
                        consecutive_absences,
                        min(days_since_last, 30),  # Cap at 30 days
                        len(current_data),
                        current_data['week_of_term'].iloc[-1],
                        current_data['day_of_week'].iloc[-1],
                        current_attendance_rate  # Simplified previous performance
                    ]

                    # Target: attendance rate in next 5 sessions
                    future_attendance_rate = future_window['is_present'].mean()

                    features.append(feature_row)
                    targets.append(future_attendance_rate)

            return np.array(features), np.array(targets)

        except Exception as e:
            print(f"Error preparing training data: {e}")
            return None, None

    def _calculate_consecutive_absences(self, attendance_array):
        """Calculate consecutive absences from the end"""
        consecutive = 0
        for status in reversed(attendance_array):
            if status == 0:  # Absent
                consecutive += 1
            else:
                break
        return consecutive

    def train_model(self):
        """Train the predictive model"""
        try:
            if get_setting('enable_predictive_analytics') != 'True':
                return False

            X, y = self.prepare_training_data()

            if X is None or len(X) < 50:  # Need minimum data
                print("Insufficient data for training predictive model")
                return False

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)

            # Train model
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)

            # Convert regression to classification (risk levels)
            y_train_class = np.where(y_train < 0.7, 2, np.where(y_train < 0.8, 1, 0))  # 2=high risk, 1=medium, 0=low
            y_test_class = np.where(y_test < 0.7, 2, np.where(y_test < 0.8, 1, 0))

            self.model.fit(X_train_scaled, y_train_class)

            # Evaluate model
            accuracy = self.model.score(X_test_scaled, y_test_class)
            print(f"Model accuracy: {accuracy:.3f}")

            accuracy_threshold = float(get_setting('prediction_model_accuracy_threshold') or 0.75)

            if accuracy >= accuracy_threshold:
                print("Model training successful!")
                return True
            else:
                print(f"Model accuracy ({accuracy:.3f}) below threshold ({accuracy_threshold})")
                return False

        except Exception as e:
            print(f"Error training model: {e}")
            return False

    def predict_student_risk(self, student_id, module_code):
        """Predict attendance risk for a student"""
        try:
            if self.model is None:
                return None

            conn = get_connection()
            cursor = conn.cursor()

            # Get recent attendance data
            cursor.execute('''
            SELECT date, status FROM attendance_records
            WHERE student_id = ? AND module_code = ?
            ORDER BY date DESC
            LIMIT 20
            ''', (student_id, module_code))

            records = cursor.fetchall()
            conn.close()

            if len(records) < 5:
                return None

            # Prepare features
            dates = [datetime.datetime.strptime(r[0], '%Y-%m-%d') for r in records]
            statuses = [1 if r[1] in ['Present', 'Late'] else 0 for r in records]

            current_attendance_rate = sum(statuses) / len(statuses)
            consecutive_absences = self._calculate_consecutive_absences(statuses[::-1])

            last_present_dates = [d for d, s in zip(dates, statuses) if s == 1]
            days_since_last = (datetime.datetime.now() - last_present_dates[0]).days if last_present_dates else 999

            current_date = datetime.datetime.now()

            features = np.array([[
                current_attendance_rate,
                consecutive_absences,
                min(days_since_last, 30),
                len(records),
                current_date.isocalendar().week % 52,
                current_date.weekday(),
                current_attendance_rate
            ]])

            # Scale and predict
            features_scaled = self.scaler.transform(features)
            risk_level = self.model.predict(features_scaled)[0]
            confidence = max(self.model.predict_proba(features_scaled)[0])

            risk_labels = ['Low Risk', 'Medium Risk', 'High Risk']

            # Store prediction
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO attendance_predictions
            (student_id, module_code, prediction_date, predicted_attendance_rate,
             risk_level, confidence_score, factors, model_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, module_code, datetime.date.today().isoformat(),
                  current_attendance_rate, risk_labels[risk_level], confidence,
                  json.dumps({'consecutive_absences': consecutive_absences, 'days_since_last': days_since_last}),
                  '1.0'))

            conn.commit()
            conn.close()

            # Cross-domain: a 'High Risk' classification feeds the
            # student_affairs case spine via attendance_bus, which is
            # idempotent per ISO week so repeated predictions don't
            # create duplicate cases.
            if risk_labels[risk_level] == 'High Risk':
                try:
                    from education_system.post_18.university_system.modules.services import (
                        attendance_bus,
                    )
                    attendance_bus.flag_student_concern(
                        student_id,
                        threshold_pct=current_attendance_rate * 100,
                        description=(
                            f"Predictive model classifies student as "
                            f"High Risk (confidence {confidence:.2f}, "
                            f"rate {current_attendance_rate:.0%}, "
                            f"module {module_code})."
                        ),
                        opened_by="predictive_analytics",
                    )
                except Exception:
                    pass

            return {
                'risk_level': risk_labels[risk_level],
                'confidence': confidence,
                'current_attendance_rate': current_attendance_rate,
                'factors': {
                    'consecutive_absences': consecutive_absences,
                    'days_since_last_attendance': days_since_last
                }
            }

        except Exception as e:
            print(f"Error predicting student risk: {e}")
            return None
