"""Enhanced reporting package.

This package was split from a single ``enhanced_reporting.py`` module.
All public names are re-exported here so that existing imports like::

    from education_system.systems.university.services.analytics.enhanced_reporting import (
        CONFIG, SystemConfig, CacheManager, ...
    )

continue to work without changes.
"""

# ── config & helpers ────────────────────────────────────────────────────────
from education_system.systems.university.services.analytics.enhanced_reporting.config import (
    CONFIG,
    AVAILABLE_SECTIONS,
    SystemConfig,
    get_reporting_db_connection,
    serialize_dataframe,
    logger,
)

# ── data models ─────────────────────────────────────────────────────────────
from education_system.systems.university.services.analytics.enhanced_reporting.models import ReportTemplate, AdvancedScheduledReport

# ── cache ───────────────────────────────────────────────────────────────────
from education_system.systems.university.services.analytics.enhanced_reporting.cache import CacheManager

# ── data quality ────────────────────────────────────────────────────────────
from education_system.systems.university.services.analytics.enhanced_reporting.data_quality import DataQualityMonitor

# ── predictive analytics ────────────────────────────────────────────────────
from education_system.systems.university.services.analytics.enhanced_reporting.predictive import PredictiveAnalytics

# ── visualization ───────────────────────────────────────────────────────────
from education_system.systems.university.services.analytics.enhanced_reporting.visualization import (
    AdvancedVisualization,
    create_advanced_visualization,
    create_interactive_chart,
    create_standard_chart,
    create_enhanced_pie_chart,
    create_enhanced_bar_chart,
    create_enhanced_line_chart,
    generate_statistical_summary,
    create_enhanced_data_table,
)

# ── template CRUD ───────────────────────────────────────────────────────────
from education_system.systems.university.services.analytics.enhanced_reporting.templates_db import (
    save_template,
    load_templates,
    save_template_dict,
    delete_template_from_db,
    get_template,
)

# ── data retrieval ──────────────────────────────────────────────────────────
from education_system.systems.university.services.analytics.enhanced_reporting.data_retrieval import (
    get_section_dataframe,
    get_correlation_data,
    get_trend_data,
    get_benchmark_data,
    get_original_section_data_complete,
)

# ── report generation ───────────────────────────────────────────────────────
from education_system.systems.university.services.analytics.enhanced_reporting.report_generation import (
    generate_report,
    generate_enhanced_pdf_report,
    generate_enhanced_section,
    generate_quality_section,
    generate_predictions_section,
    generate_enhanced_excel_report,
    generate_interactive_report,
)

# ── Flask API ───────────────────────────────────────────────────────────────
from education_system.systems.university.services.analytics.enhanced_reporting.api import app

# ── scheduling & maintenance ────────────────────────────────────────────────
from education_system.systems.university.services.analytics.enhanced_reporting.scheduler import (
    run_system_maintenance,
    cleanup_old_reports,
    load_scheduled_reports,
    save_scheduled_reports,
    start_scheduler,
)

# ── CLI menus ───────────────────────────────────────────────────────────────
from education_system.systems.university.services.analytics.enhanced_reporting.menu import (
    display_enhanced_reporting_menu,
    show_performance_monitor,
)


def main():
    """Main function to start the advanced reporting system"""
    print("🔬 Advanced Student Reporting System v2.0")
    print("Initializing enhanced features...")

    # Run system checks
    try:
        # Check database connection
        conn = get_reporting_db_connection()
        conn.close()
        print("✅ Database connection verified")

        # Initialize system config
        SystemConfig.load_config()
        print("✅ System configuration loaded")

        # Start background scheduler
        start_scheduler()
        print("✅ Background scheduler started")

        print("\n🎉 All systems ready!")

        # Show the main menu
        display_enhanced_reporting_menu()

    except Exception as e:
        print(f"❌ System initialization failed: {str(e)}")
        logger.error(f"System initialization error: {str(e)}")


if __name__ == "__main__":
    main()
