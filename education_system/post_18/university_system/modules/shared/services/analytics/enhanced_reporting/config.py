"""Configuration, constants and shared helpers for enhanced reporting."""

import os
import json
import secrets
import warnings

from education_system.post_18.university_system.infrastructure.database.db import get_db_connection
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core import paths

from education_system.post_18.university_system.modules.shared.services.analytics.enhanced_reporting._compat import configure_logging

warnings.filterwarnings('ignore')

# Configuration
CONFIG = {
    'database': str(paths.DEFAULT_DB_PATH),
    'reports_dir': str(paths.REPORTS_DIR),
    'templates_dir': str(paths.REPORT_TEMPLATES_DIR),
    'cache_dir': str(paths.REPORT_CACHE_DIR),
    'logs_dir': str(paths.LOG_DIR),
    'scheduled_reports_file': str(paths.SCHEDULED_REPORTS_FILE),
    'config_file': str(paths.DATA_DIR / 'system_config.json'),
    'secret_key': os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32)),
    'cache_expiry_hours': 24,
    'max_cache_size_mb': 500
}

# Ensure all directories exist
for dir_path in [CONFIG['reports_dir'], CONFIG['templates_dir'], CONFIG['cache_dir'], CONFIG['logs_dir']]:
    os.makedirs(dir_path, exist_ok=True)

# Setup logging
logger = configure_logging(name=__name__)

# Enhanced available sections with new analytics
AVAILABLE_SECTIONS = [
    "student_overview",
    "student_list",
    "course_distribution",
    "gender_distribution",
    "age_distribution",
    "module_popularity",
    "registration_trends",
    "grade_distribution",
    "attendance_summary",
    "data_quality_report",
    "predictive_analytics",
    "correlation_analysis",
    "anomaly_detection",
    "performance_benchmarks",
    "trend_analysis"
]


class SystemConfig:
    """System configuration management"""

    @staticmethod
    def load_config():
        try:
            with open(CONFIG['config_file'], 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                'security': {
                    'session_timeout': 3600,
                    'max_login_attempts': 5,
                    'require_2fa': False
                },
                'performance': {
                    'enable_caching': True,
                    'max_concurrent_reports': 5,
                    'report_timeout': 1800
                }
            }

    @staticmethod
    def save_config(config):
        with open(CONFIG['config_file'], 'w') as f:
            json.dump(config, f, indent=4)


def get_reporting_db_connection():
    """Create a connection to the database"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    return conn


def serialize_dataframe(df):
    """Convert DataFrame to JSON-serializable format"""
    from education_system.post_18.university_system.modules.shared.services.analytics.enhanced_reporting._compat import pd

    if df is None or df.empty:
        return []

    # Replace NaN values with None for JSON serialization
    df_clean = df.fillna('')
    return df_clean.to_dict('records')
