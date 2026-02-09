from __future__ import annotations
from datetime import datetime
from university_system.infrastructure.database.db import get_connection, sqlite3
from university_system.modules.shared.utils.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_analytics_dashboard_system_db():
    """Initialize the Predictive Analytics Dashboard database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Predictive Analytics Dashboard"))

        # Analytics models registry
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics_models (
            model_id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            model_type TEXT NOT NULL,
            description TEXT,
            model_version TEXT,
            accuracy_score REAL,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP,
            last_trained_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            parameters TEXT
        )
        ''')

        # Student retention predictions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS retention_predictions (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            model_id INTEGER NOT NULL,
            retention_probability REAL NOT NULL,
            risk_level TEXT NOT NULL,
            prediction_date TEXT DEFAULT CURRENT_TIMESTAMP,
            prediction_year INTEGER,
            factors TEXT,
            recommendations TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (model_id) REFERENCES analytics_models (model_id)
        )
        ''')

        # Graduation rate forecasts
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS graduation_forecasts (
            forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
            cohort_year INTEGER NOT NULL,
            program_id INTEGER,
            predicted_graduation_rate REAL,
            predicted_4year_rate REAL,
            predicted_5year_rate REAL,
            predicted_6year_rate REAL,
            forecast_date TEXT DEFAULT CURRENT_TIMESTAMP,
            model_id INTEGER,
            confidence_interval TEXT,
            FOREIGN KEY (model_id) REFERENCES analytics_models (model_id)
        )
        ''')

        # Course demand predictions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_demand_predictions (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            semester TEXT NOT NULL,
            predicted_enrollment INTEGER,
            actual_enrollment INTEGER,
            prediction_date TEXT DEFAULT CURRENT_TIMESTAMP,
            model_id INTEGER,
            factors TEXT,
            FOREIGN KEY (module_code) REFERENCES modules (module_code),
            FOREIGN KEY (model_id) REFERENCES analytics_models (model_id)
        )
        ''')

        # Enrollment projections
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS enrollment_projections (
            projection_id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT NOT NULL,
            program_id INTEGER,
            projected_new_students INTEGER,
            projected_continuing_students INTEGER,
            projected_total_enrollment INTEGER,
            projection_date TEXT DEFAULT CURRENT_TIMESTAMP,
            model_id INTEGER,
            scenario TEXT,
            FOREIGN KEY (model_id) REFERENCES analytics_models (model_id)
        )
        ''')

        # KPI tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS kpi_metrics (
            kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
            kpi_name TEXT NOT NULL,
            kpi_category TEXT NOT NULL,
            current_value REAL NOT NULL,
            target_value REAL,
            measurement_date TEXT DEFAULT CURRENT_DATE,
            period TEXT,
            trend TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Custom dashboards
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics_dashboards (
            dashboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dashboard_name TEXT NOT NULL,
            dashboard_type TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            is_public BOOLEAN DEFAULT 0,
            layout_config TEXT,
            widget_config TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Dashboard widgets
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS dashboard_widgets (
            widget_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dashboard_id INTEGER NOT NULL,
            widget_type TEXT NOT NULL,
            widget_title TEXT NOT NULL,
            data_source TEXT,
            chart_type TEXT,
            position_x INTEGER,
            position_y INTEGER,
            width INTEGER DEFAULT 4,
            height INTEGER DEFAULT 3,
            config TEXT,
            FOREIGN KEY (dashboard_id) REFERENCES analytics_dashboards (dashboard_id)
        )
        ''')

        # Scheduled reports
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_name TEXT NOT NULL,
            report_type TEXT NOT NULL,
            schedule_frequency TEXT NOT NULL,
            recipients TEXT NOT NULL,
            last_run_date TEXT,
            next_run_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            report_config TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Data snapshots for trend analysis
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_type TEXT NOT NULL,
            snapshot_date TEXT DEFAULT CURRENT_DATE,
            data_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Performance trends
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS performance_trends (
            trend_id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            metric_category TEXT NOT NULL,
            time_period TEXT NOT NULL,
            value REAL NOT NULL,
            change_from_previous REAL,
            trend_direction TEXT,
            recorded_date TEXT DEFAULT CURRENT_DATE
        )
        ''')

        # Insert default analytics model if it doesn't exist
        cursor.execute('SELECT COUNT(*) FROM analytics_models WHERE model_id = 1')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO analytics_models (
                    model_id, model_name, model_type, description,
                    model_version, accuracy_score, is_active, parameters
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                1,
                'Default Prediction Model',
                'baseline',
                'Default model for initial predictions and testing',
                '1.0',
                0.75,
                1,
                '{}'
            ))
            print(_t("schemas.created_default_model", id=1))

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Predictive Analytics Dashboard"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Analytics Dashboard", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# SMART TIMETABLE OPTIMIZER SCHEMAS
# ============================================================================


def init_business_intelligence_system_db():
    """Initialize the Business Intelligence Reports database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Business Intelligence Reports"))

        # Report definitions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bi_report_definitions (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_name TEXT NOT NULL,
            report_category TEXT NOT NULL,
            description TEXT,
            sql_query TEXT,
            data_source TEXT,
            parameters TEXT,
            visualization_type TEXT,
            created_by TEXT,
            is_public BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        )
        ''')

        # Saved reports/exports
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bi_report_exports (
            export_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            export_format TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            generated_by TEXT NOT NULL,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            parameters_used TEXT,
            row_count INTEGER,
            FOREIGN KEY (report_id) REFERENCES bi_report_definitions (report_id)
        )
        ''')

        # Report schedules
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bi_report_schedules (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            schedule_name TEXT NOT NULL,
            frequency TEXT NOT NULL,
            delivery_method TEXT NOT NULL,
            recipients TEXT NOT NULL,
            export_format TEXT NOT NULL,
            last_run_date TEXT,
            next_run_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_id) REFERENCES bi_report_definitions (report_id)
        )
        ''')

        # Data visualizations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bi_visualizations (
            visualization_id INTEGER PRIMARY KEY AUTOINCREMENT,
            visualization_name TEXT NOT NULL,
            chart_type TEXT NOT NULL,
            data_source TEXT NOT NULL,
            x_axis TEXT,
            y_axis TEXT,
            filters TEXT,
            color_scheme TEXT,
            configuration TEXT,
            created_by TEXT,
            is_public BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Custom metrics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bi_custom_metrics (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            metric_category TEXT NOT NULL,
            description TEXT,
            calculation_formula TEXT NOT NULL,
            data_sources TEXT,
            unit_of_measure TEXT,
            target_value REAL,
            created_by TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Data quality checks
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bi_data_quality_checks (
            check_id INTEGER PRIMARY KEY AUTOINCREMENT,
            check_name TEXT NOT NULL,
            data_source TEXT NOT NULL,
            check_type TEXT NOT NULL,
            check_rule TEXT NOT NULL,
            last_run_date TEXT,
            passed BOOLEAN,
            issues_found INTEGER,
            details TEXT,
            is_active BOOLEAN DEFAULT 1
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Business Intelligence Reports"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Business Intelligence", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# AI-POWERED FEATURES SCHEMAS
# ============================================================================


def init_analytics_tables():
    """Initialize analytics system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="analytics"))

        # Create analytics_cache table
        cursor.execute('''
        CREATE TABLE analytics_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE NOT NULL,
                    cache_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
        ''')

        # Create analytics_data table
        cursor.execute('''
        CREATE TABLE analytics_data (
                    analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    metric_value REAL,
                    metric_date TEXT,
                    category TEXT,
                    additional_data TEXT
                )
        ''')

        # Create quality_metrics table
        cursor.execute('''
        CREATE TABLE quality_metrics (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            metric_name TEXT,
                            metric_category TEXT,
                            target_value REAL,
                            actual_value REAL,
                            measurement_period TEXT,
                            measured_date TEXT,
                            status TEXT,
                            improvement_needed INTEGER DEFAULT 0,
                            created_at TEXT
                        )
        ''')

        # Create search_analytics table
        cursor.execute('''
        CREATE TABLE search_analytics (
                    search_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    search_query TEXT NOT NULL,
                    search_type TEXT NOT NULL,  -- faq, resource, ticket, global
                    results_count INTEGER NOT NULL,
                    clicked_result_id TEXT,
                    search_datetime TEXT NOT NULL,
                    session_id TEXT
                , search_criteria TEXT, execution_time REAL)
        ''')

        # Create system_metrics table
        cursor.execute('''
        CREATE TABLE system_metrics (
                    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    category TEXT NOT NULL,
                    recorded_datetime TEXT NOT NULL,
                    metadata TEXT  -- JSON data
                )
        ''')

        # Create teacher_reports table
        cursor.execute('''
        CREATE TABLE teacher_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    teacher_id INTEGER,
                    module_code TEXT,
                    report_type TEXT,
                    report_content TEXT,
                    created_date TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (module_code) REFERENCES modules (module_code)
                )
        ''')

        # Create usage_analytics table
        cursor.execute('''
        CREATE TABLE usage_analytics (
                    analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    category TEXT,
                    additional_data TEXT
                )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="analytics"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="analytics", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# AUDIT TABLES (5 tables)
# ============================================================================


