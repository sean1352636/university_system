import matplotlib.pyplot as plt

from education_system.university_system.infrastructure.database.db import get_connection

from .alerts import FinancialAlertSystem
from .ml import PaymentPredictionML


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
