"""Miscellaneous helpers for the enhanced reporting GUI.

This module provides access to any functions or methods from the core
implementation that have not been explicitly wrapped elsewhere.
"""

from __future__ import annotations

# Database functions
from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.core import (
    get_db_connection,
)

# Settings functions
from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.core import (
    show_directory_settings,
    show_theme_settings,
    validate_email_settings,
)

# Data processing functions
from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.core import (
    serialize_dataframe,
    get_template,
)

# Report generation functions
from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.core import (
    generate_enhanced_pdf_report,
    generate_enhanced_section,
    generate_enhanced_excel_report,
    generate_interactive_report,
)

# Visualization functions
from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.core import (
    create_advanced_visualization,
    create_interactive_chart,
    create_standard_chart,
    create_enhanced_pie_chart,
    create_enhanced_bar_chart,
    create_enhanced_line_chart,
    create_enhanced_data_table,
)

# Statistical functions
from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.core import (
    generate_statistical_summary,
    generate_quality_section,
    generate_predictions_section,
)

# Data retrieval functions
from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.core import (
    get_section_dataframe,
    get_correlation_data,
    get_trend_data,
    get_benchmark_data,
    get_original_section_data_complete,
)

# System maintenance functions
from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.core import (
    run_system_maintenance,
    cleanup_old_reports,
    load_scheduled_reports,
    save_scheduled_reports,
    start_scheduler,
)

# Email functions
from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.core import (
    send_report_email,
    get_log_file,
)

# GUI classes and functions
from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.core import (
    ReportingSystemGUI,
    TemplateDialog,
    start_gui,
    start_enhanced_reporting_gui,
)

__all__ = [
    # Database
    'get_db_connection',
    # Settings
    'show_directory_settings',
    'show_theme_settings',
    'validate_email_settings',
    # Data processing
    'serialize_dataframe',
    'get_template',
    # Report generation
    'generate_enhanced_pdf_report',
    'generate_enhanced_section',
    'generate_enhanced_excel_report',
    'generate_interactive_report',
    # Visualization
    'create_advanced_visualization',
    'create_interactive_chart',
    'create_standard_chart',
    'create_enhanced_pie_chart',
    'create_enhanced_bar_chart',
    'create_enhanced_line_chart',
    'create_enhanced_data_table',
    # Statistics
    'generate_statistical_summary',
    'generate_quality_section',
    'generate_predictions_section',
    # Data retrieval
    'get_section_dataframe',
    'get_correlation_data',
    'get_trend_data',
    'get_benchmark_data',
    'get_original_section_data_complete',
    # System maintenance
    'run_system_maintenance',
    'cleanup_old_reports',
    'load_scheduled_reports',
    'save_scheduled_reports',
    'start_scheduler',
    # Email
    'send_report_email',
    'get_log_file',
    # GUI
    'ReportingSystemGUI',
    'TemplateDialog',
    'start_gui',
    'start_enhanced_reporting_gui',
]