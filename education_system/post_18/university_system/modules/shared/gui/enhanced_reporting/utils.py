"""Utility functions for the enhanced reporting GUI.

This module re-exports a number of standalone helper functions used
throughout the enhanced reporting GUI.  These helpers handle
database connectivity, dataframe serialization, data retrieval for
various report sections, chart generation and table creation.  By
importing them here the utilities can be consumed without pulling in
the entire GUI framework.
"""

from __future__ import annotations

from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.core import (
    get_db_connection,
    serialize_dataframe,
    get_template,
    get_section_dataframe,
    get_correlation_data,
    get_trend_data,
    get_benchmark_data,
    get_original_section_data_complete,
    create_advanced_visualization,
    create_interactive_chart,
    create_standard_chart,
    create_enhanced_pie_chart,
    create_enhanced_bar_chart,
    create_enhanced_line_chart,
    generate_statistical_summary,
    create_enhanced_data_table,
    generate_quality_section,
    generate_predictions_section,
)

__all__ = [
    "get_db_connection",
    "serialize_dataframe",
    "get_template",
    "get_section_dataframe",
    "get_correlation_data",
    "get_trend_data",
    "get_benchmark_data",
    "get_original_section_data_complete",
    "create_advanced_visualization",
    "create_interactive_chart",
    "create_standard_chart",
    "create_enhanced_pie_chart",
    "create_enhanced_bar_chart",
    "create_enhanced_line_chart",
    "generate_statistical_summary",
    "create_enhanced_data_table",
    "generate_quality_section",
    "generate_predictions_section",
]