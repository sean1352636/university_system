"""
Business Intelligence Reports Core Service

Report definitions, data exports, scheduled reports,
visualizations, custom metrics, and data quality checks.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.feature_gui_factory import create_gui_launcher
from education_system.university_system.core.i18n import get_text, _


class ReportDefinitionManager:
    """Manages report definitions"""

    @staticmethod
    def create_report(report_name: str, report_category: str,
                     description: str = "", sql_query: str = "",
                     data_source: str = "", created_by: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO bi_report_definitions (
                        report_name, report_category, description,
                        sql_query, data_source, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (report_name, report_category, description,
                      sql_query, data_source, created_by))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error creating report: {e}")


class ReportExportManager:
    """Manages report exports"""

    @staticmethod
    def export_report(report_id: int, export_format: str, file_path: str,
                     generated_by: str, row_count: int = 0) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO bi_report_exports (
                        report_id, export_format, file_path,
                        generated_by, row_count
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (report_id, export_format, file_path, generated_by, row_count))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error exporting report: {e}")


class ReportScheduleManager:
    """Manages scheduled reports"""

    @staticmethod
    def create_schedule(report_id: int, schedule_name: str, frequency: str,
                       delivery_method: str, recipients: str,
                       export_format: str) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO bi_report_schedules (
                        report_id, schedule_name, frequency, delivery_method,
                        recipients, export_format
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (report_id, schedule_name, frequency, delivery_method,
                      recipients, export_format))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error creating schedule: {e}")


class VisualizationManager:
    """Manages data visualizations"""

    @staticmethod
    def create_visualization(visualization_name: str, chart_type: str,
                            data_source: str, x_axis: str = "",
                            y_axis: str = "", created_by: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO bi_visualizations (
                        visualization_name, chart_type, data_source,
                        x_axis, y_axis, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (visualization_name, chart_type, data_source,
                      x_axis, y_axis, created_by))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error creating visualization: {e}")


class CustomMetricManager:
    """Manages custom metrics"""

    @staticmethod
    def define_metric(metric_name: str, metric_category: str,
                     calculation_formula: str, description: str = "",
                     target_value: float = 0, created_by: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO bi_custom_metrics (
                        metric_name, metric_category, calculation_formula,
                        description, target_value, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (metric_name, metric_category, calculation_formula,
                      description, target_value, created_by))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error defining metric: {e}")


def display_business_intelligence_menu(auth):
    """Display the Business Intelligence Reports CLI menu"""
    print("\n" + "="*50)
    print("    BUSINESS INTELLIGENCE REPORTS")
    print("="*50)
    print("1. Create Report Definition")
    print("2. Export Reports")
    print("3. Schedule Reports")
    print("4. Data Visualizations")
    print("5. Custom Metrics")
    print("6. Data Quality Checks")
    print("7. Report Library")
    print("8. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-8): ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n📊 Feature available via BI managers")
                print("Use: from education_system.university_system.modules.shared.services.business_intelligence import ReportDefinitionManager")
            elif choice == '8':
                break
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")


# Use factory to create GUI launcher
launch_business_intelligence_gui = create_gui_launcher(
    title="Business Intelligence Reports",
    description="""Custom reports, dashboards, and data visualizations.

Features:
• Custom report definitions
• Data exports
• Scheduled reports
• Data visualizations
• Custom metrics
• Data quality checks""",
    cli_instruction="Use CLI: Business Intelligence Reports"
)



__all__ = [
    'ReportDefinitionManager', 'ReportExportManager', 'ReportScheduleManager',
    'VisualizationManager', 'CustomMetricManager',
    'display_business_intelligence_menu',
    'launch_business_intelligence_gui',
]
