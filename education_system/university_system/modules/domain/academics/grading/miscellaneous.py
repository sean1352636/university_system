"""Backwards-compatible shim forwarding grading utility functions."""

from __future__ import annotations

# Import from individual submodules rather than the package __init__
# to avoid circular import issues and missing-export errors.

from education_system.university_system.modules.domain.academics.grading.utils import (
    select_student,
    percentage_to_letter,
    letter_to_percentage,
    calculate_trend_slope,
)

from education_system.university_system.modules.domain.academics.grading.reports import (
    generate_statistical_report,
    generate_module_stats_report,
    generate_all_modules_stats_report,
    generate_course_stats_report,
    generate_all_courses_stats_report,
    generate_comprehensive_stats_report,
)

from education_system.university_system.modules.domain.academics.grading.competency import (
    manage_competencies,
    record_student_competencies,
)

from education_system.university_system.modules.domain.academics.grading.progress import (
    student_progress_tracking,
    analyze_student_progress,
    save_intervention_recommendations,
    success_probability_calculator,
    calculate_individual_success_probability,
    calculate_all_students_success_probability,
    calculate_student_success_probability,
    collect_dashboard_data,
    create_progress_visualization,
)

from education_system.university_system.modules.domain.academics.grading.interventions import (
    intervention_recommendations,
    generate_intervention_plan,
    display_intervention_recommendations,
    generate_system_recommendations,
)

from education_system.university_system.modules.domain.academics.grading.comparisons import (
    compare_by_course,
    display_course_comparison,
    compare_by_gender,
    compare_by_module_type,
    perform_statistical_test,
    compare_by_time_period,
    custom_group_comparison,
    compare_by_module_codes,
    compare_by_enrollment_date,
    compare_by_specific_courses,
    compare_by_assessment_type,
)

from education_system.university_system.modules.domain.academics.grading.forecasting import (
    export_batch_predictions,
    forecast_single_course,
    forecast_module_difficulty,
    forecast_module_difficulty_single,
    forecast_success_rates,
    forecast_course_success_rate,
    extract_comprehensive_student_features,
    build_module_success_model,
    create_dashboard_visualizations,
    generate_dashboard_report,
    generate_dashboard_recommendations,
    generate_dashboard_alerts,
    extract_student_features,
    export_comparison_data,
)

from education_system.university_system.modules.domain.academics.grading.trends import (
    analyze_individual_student_trends,
    analyze_single_course_trends,
    analyze_seasonal_trends,
    analyze_monthly_patterns,
    analyze_day_of_week_patterns,
    analyze_academic_term_patterns,
    trend_forecasting,
    create_trend_visualization,
    create_individual_trend_visualization,
    create_course_comparison_charts,
)

__all__ = [
    "analyze_academic_term_patterns",
    "analyze_day_of_week_patterns",
    "analyze_individual_student_trends",
    "analyze_monthly_patterns",
    "analyze_seasonal_trends",
    "analyze_single_course_trends",
    "analyze_student_progress",
    "build_module_success_model",
    "calculate_all_students_success_probability",
    "calculate_individual_success_probability",
    "calculate_student_success_probability",
    "calculate_trend_slope",
    "collect_dashboard_data",
    "compare_by_assessment_type",
    "compare_by_course",
    "compare_by_enrollment_date",
    "compare_by_gender",
    "compare_by_module_codes",
    "compare_by_module_type",
    "compare_by_specific_courses",
    "compare_by_time_period",
    "create_course_comparison_charts",
    "create_dashboard_visualizations",
    "create_individual_trend_visualization",
    "create_progress_visualization",
    "create_trend_visualization",
    "custom_group_comparison",
    "display_course_comparison",
    "display_intervention_recommendations",
    "export_batch_predictions",
    "export_comparison_data",
    "extract_comprehensive_student_features",
    "extract_student_features",
    "forecast_course_success_rate",
    "forecast_module_difficulty",
    "forecast_module_difficulty_single",
    "forecast_single_course",
    "forecast_success_rates",
    "generate_all_courses_stats_report",
    "generate_all_modules_stats_report",
    "generate_comprehensive_stats_report",
    "generate_course_stats_report",
    "generate_dashboard_alerts",
    "generate_dashboard_recommendations",
    "generate_dashboard_report",
    "generate_intervention_plan",
    "generate_module_stats_report",
    "generate_statistical_report",
    "generate_system_recommendations",
    "intervention_recommendations",
    "letter_to_percentage",
    "manage_competencies",
    "percentage_to_letter",
    "perform_statistical_test",
    "record_student_competencies",
    "save_intervention_recommendations",
    "select_student",
    "student_progress_tracking",
    "success_probability_calculator",
    "trend_forecasting",
]
