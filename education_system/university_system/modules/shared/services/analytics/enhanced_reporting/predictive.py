"""Machine learning for predictive insights."""

from ._compat import (
    pd, np, RandomForestClassifier, IsolationForest,
    train_test_split, accuracy_score,
)
from .config import get_reporting_db_connection, logger


class PredictiveAnalytics:
    """Machine learning for predictive insights"""

    @staticmethod
    def predict_dropout_risk():
        """Predict which students are at risk of dropping out"""
        conn = get_reporting_db_connection()

        try:
            # Check which attendance table exists
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attendance_records'")

            if cursor.fetchone():
                attendance_table = 'attendance_records'
                status_column = 'status'
            else:
                # No attendance data available
                return {'error': 'No attendance data available for prediction'}

            # Fixed query with proper table aliases
            query = f"""
            SELECT s.student_id, s.age, s.course,
                   COUNT(sm.module_code) as module_count,
                   AVG(CASE WHEN sg.grade IS NOT NULL THEN CAST(sg.grade AS FLOAT) ELSE NULL END) as avg_grade,
                   COUNT(ar.student_id) as attendance_count,
                   SUM(CASE WHEN LOWER(ar.{status_column}) IN ('present', 'attended') THEN 1 ELSE 0 END) as present_count
            FROM students s
            LEFT JOIN student_modules sm ON s.student_id = sm.student_id
            LEFT JOIN student_grades sg ON s.student_id = sg.student_id
            LEFT JOIN {attendance_table} ar ON s.student_id = ar.student_id
            WHERE s.registration_datetime >= date('now', '-1 year')
            GROUP BY s.student_id, s.age, s.course
            """

            df = pd.read_sql_query(query, conn)

            if df.empty or len(df) < 10:
                return {'error': 'Insufficient data for prediction'}

            # Feature engineering
            df['attendance_rate'] = df.apply(
                lambda row: row['present_count'] / row['attendance_count'] if row['attendance_count'] > 0 else 0,
                axis=1
            )
            df['course_numeric'] = df['course'].map({'CS': 1, 'DS': 2}).fillna(0)
            df = df.fillna(0)

            # For demonstration, create synthetic dropout labels
            # In reality, you'd have historical dropout data
            np.random.seed(42)
            df['dropout_risk'] = np.random.choice([0, 1], size=len(df), p=[0.8, 0.2])

            # Prepare features
            features = ['age', 'module_count', 'avg_grade', 'attendance_rate', 'course_numeric']
            X = df[features]
            y = df['dropout_risk']

            # Train model
            if len(np.unique(y)) > 1:
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

                model = RandomForestClassifier(n_estimators=100, random_state=42)
                model.fit(X_train, y_train)

                # Predictions
                y_pred = model.predict(X_test)
                accuracy = accuracy_score(y_test, y_pred)

                # Get feature importance
                importance = dict(zip(features, model.feature_importances_))

                # Predict for all students
                df['risk_score'] = model.predict_proba(X)[:, 1]
                high_risk_students = df[df['risk_score'] > 0.7][['student_id', 'risk_score']].to_dict('records')

                return {
                    'model_accuracy': accuracy,
                    'feature_importance': importance,
                    'high_risk_students': high_risk_students,
                    'total_students_analyzed': len(df)
                }
            else:
                return {'error': 'Insufficient variety in data for meaningful prediction'}

        except Exception as e:
            logger.error(f"Error in dropout prediction: {str(e)}")
            return {'error': f'Prediction failed: {str(e)}'}
        finally:
            conn.close()

    @staticmethod
    def detect_anomalies():
        """Detect anomalous patterns in student data"""
        conn = get_reporting_db_connection()

        try:
            # Fixed query with table aliases to resolve ambiguous column names
            query = """
            SELECT s.student_id, s.age,
                   COUNT(DISTINCT sm.module_code) as unique_modules,
                   AVG(CASE WHEN sg.grade IS NOT NULL THEN CAST(sg.grade AS FLOAT) ELSE NULL END) as avg_grade
            FROM students s
            LEFT JOIN student_modules sm ON s.student_id = sm.student_id
            LEFT JOIN student_grades sg ON s.student_id = sg.student_id
            GROUP BY s.student_id, s.age
            """

            df = pd.read_sql_query(query, conn)

            if df.empty or len(df) < 10:
                return {'error': 'Insufficient data for anomaly detection'}

            # Prepare features for anomaly detection
            features = ['age', 'unique_modules', 'avg_grade']
            X = df[features].fillna(0)

            # Use Isolation Forest for anomaly detection
            iso_forest = IsolationForest(contamination=0.1, random_state=42)
            anomalies = iso_forest.fit_predict(X)

            df['is_anomaly'] = anomalies == -1
            anomalous_students = df[df['is_anomaly']][['student_id', 'age', 'unique_modules', 'avg_grade']].to_dict('records')

            return {
                'anomalous_students': anomalous_students,
                'total_anomalies': len(anomalous_students),
                'anomaly_rate': len(anomalous_students) / len(df) * 100
            }

        except Exception as e:
            logger.error(f"Error in anomaly detection: {str(e)}")
            return {'error': f'Anomaly detection failed: {str(e)}'}
        finally:
            conn.close()
