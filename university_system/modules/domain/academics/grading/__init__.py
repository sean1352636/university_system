"""
Grading Module - Re-exports for backward compatibility

This module re-exports functions from the refactored grading submodules
to maintain backward compatibility with existing imports.
"""

# Grade calculation functions
from university_system.modules.domain.academics.grading.grade_calculation import (
    select_assessment,
    record_assessment_grades,
    update_module_grade,
    update_grades,
    view_student_grades,
    calculate_gpa,
    calculate_student_gpa,
    generate_transcript,
    create_transcript_pdf,
    letter_to_gpa,
    calculate_assessment_statistics,
    normalize_assessment_grades,
    view_grade_distribution,
    create_grade_visualizations,
    generate_assessment_stats_report,
    map_assessments_to_outcomes,
    map_assessments_to_competencies,
    assessment_performance_summary,
    analyze_specific_assessment,
    grade_distribution_analysis,
    student_risk_assessment,
    display_risk_assessment_results,
    save_risk_assessments,
    analyze_overall_grade_trends,
    analyze_by_assessment_type,
    analyze_all_assessments,
    analyze_distribution_by_assessment_type,
    compare_by_grade_threshold,
    analyze_assessment_performance_trends,
    analyze_single_assessment_type_trends,
    batch_grade_predictions,
    batch_predict_next_assessments,
    predict_student_next_grade,
    batch_predict_module_grades,
    predict_module_final_grade,
    batch_predict_end_term_gpas,
    predict_end_term_gpa,
    forecast_assessment_performance,
    forecast_assessment_type_performance,
    build_assessment_prediction_model,
    validate_grade_data_integrity,
    build_gpa_prediction_model,
    predict_student_gpa,
    grade_prediction,
    predict_next_assessment_grade,
)

# Curve analysis functions
from university_system.modules.domain.academics.grading.curve_analysis import (
    apply_grading_curve,
    comparative_performance_analysis,
    performance_trends_analysis,
    analyze_distribution_by_course,
    analyze_distribution_by_module_type,
    analyze_overall_distribution,
    dropout_risk_analysis,
)

# Learning outcomes functions
from university_system.modules.domain.academics.grading.learning_outcomes import (
    manage_learning_outcomes,
    record_outcome_achievement,
    view_student_outcome_achievement,
    generate_outcome_report,
    generate_student_outcome_report,
    generate_course_outcome_report,
    generate_all_courses_outcome_report,
    generate_module_outcome_report,
)

# Competency assessment functions
from university_system.modules.domain.academics.grading.competency_assessment import (
    add_competency_levels,
    manage_competency_levels,
    view_student_competency_profile,
    generate_competency_report,
    generate_student_competency_report,
    generate_course_competency_report,
    assess_student_risk,
    assess_comprehensive_student_risk,
)

# Predictive analytics functions
from university_system.modules.domain.academics.grading.predictive_analytics import (
    identify_at_risk_students,
    calculate_risk_factors,
    early_warning_system,
    generate_early_warning_alert,
    export_at_risk_students,
    export_early_warning_alerts,
    export_dropout_risk_list,
    build_at_risk_prediction_model,
    analyze_dropout_risk_factors,
    build_dropout_prediction_model,
    generate_dropout_interventions,
    generate_dropout_intervention_plan,
    identify_high_dropout_risk,
    calculate_dropout_risk_score,
    generate_risk_report,
    collect_comprehensive_risk_data,
    generate_comprehensive_risk_report,
)

# Performance analytics functions
from university_system.modules.domain.academics.grading.performance_analytics import (
    module_performance_summary,
    analyze_module_performance,
    display_module_performance_results,
    calculate_course_statistics,
    generate_performance_dashboard,
    display_performance_dashboard,
    export_module_performance,
    analyze_course_performance_trends,
    forecast_course_performance,
    export_performance_summary,
    performance_prediction_models,
    forecast_overall_performance,
)

# Utility functions
from university_system.modules.domain.academics.grading.utils import (
    select_student,
    percentage_to_letter,
    letter_to_percentage,
)

# Report generation functions
from university_system.modules.domain.academics.grading.reports import (
    generate_statistical_report,
    generate_module_stats_report,
    generate_all_modules_stats_report,
    generate_course_stats_report,
    generate_all_courses_stats_report,
    generate_comprehensive_stats_report,
)

# Competency management functions
from university_system.modules.domain.academics.grading.competency import (
    manage_competencies,
    record_student_competencies,
)

# Progress tracking functions
from university_system.modules.domain.academics.grading.progress import (
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

# Intervention functions
from university_system.modules.domain.academics.grading.interventions import (
    intervention_recommendations,
    generate_intervention_plan,
    display_intervention_recommendations,
    generate_system_recommendations,
)

# Comparison functions
from university_system.modules.domain.academics.grading.comparisons import (
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
)

# Forecasting functions
from university_system.modules.domain.academics.grading.forecasting import (
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

# Trend analysis functions
from university_system.modules.domain.academics.grading.trends import (
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

# Additional utility functions
from university_system.modules.domain.academics.grading.utils import (
    calculate_trend_slope,
)

__all__ = [
    # Grade calculation
    'select_assessment',
    'record_assessment_grades',
    'update_module_grade',
    'update_grades',
    'view_student_grades',
    'calculate_gpa',
    'calculate_student_gpa',
    'generate_transcript',
    'create_transcript_pdf',
    'letter_to_gpa',
    'calculate_assessment_statistics',
    'normalize_assessment_grades',
    'view_grade_distribution',
    'create_grade_visualizations',
    'generate_assessment_stats_report',
    'map_assessments_to_outcomes',
    'map_assessments_to_competencies',
    'assessment_performance_summary',
    'analyze_specific_assessment',
    'grade_distribution_analysis',
    'student_risk_assessment',
    'display_risk_assessment_results',
    'save_risk_assessments',
    'analyze_overall_grade_trends',
    'analyze_by_assessment_type',
    'analyze_all_assessments',
    'analyze_distribution_by_assessment_type',
    'compare_by_grade_threshold',
    'analyze_assessment_performance_trends',
    'analyze_single_assessment_type_trends',
    'batch_grade_predictions',
    'batch_predict_next_assessments',
    'predict_student_next_grade',
    'batch_predict_module_grades',
    'predict_module_final_grade',
    'batch_predict_end_term_gpas',
    'predict_end_term_gpa',
    'forecast_assessment_performance',
    'forecast_assessment_type_performance',
    'build_assessment_prediction_model',
    'validate_grade_data_integrity',
    'build_gpa_prediction_model',
    'predict_student_gpa',
    'grade_prediction',
    'predict_next_assessment_grade',

    # Curve analysis
    'apply_grading_curve',
    'comparative_performance_analysis',
    'performance_trends_analysis',
    'analyze_distribution_by_course',
    'analyze_distribution_by_module_type',
    'analyze_overall_distribution',
    'dropout_risk_analysis',

    # Learning outcomes
    'manage_learning_outcomes',
    'record_outcome_achievement',
    'view_student_outcome_achievement',
    'generate_outcome_report',
    'generate_student_outcome_report',
    'generate_course_outcome_report',
    'generate_all_courses_outcome_report',
    'generate_module_outcome_report',

    # Competency assessment
    'add_competency_levels',
    'manage_competency_levels',
    'view_student_competency_profile',
    'generate_competency_report',
    'generate_student_competency_report',
    'generate_course_competency_report',
    'assess_student_risk',
    'assess_comprehensive_student_risk',

    # Predictive analytics
    'identify_at_risk_students',
    'calculate_risk_factors',
    'early_warning_system',
    'generate_early_warning_alert',
    'export_at_risk_students',
    'export_early_warning_alerts',
    'export_dropout_risk_list',
    'build_at_risk_prediction_model',
    'analyze_dropout_risk_factors',
    'build_dropout_prediction_model',
    'generate_dropout_interventions',
    'generate_dropout_intervention_plan',
    'identify_high_dropout_risk',
    'calculate_dropout_risk_score',
    'generate_risk_report',
    'collect_comprehensive_risk_data',
    'generate_comprehensive_risk_report',

    # Performance analytics
    'module_performance_summary',
    'analyze_module_performance',
    'display_module_performance_results',
    'calculate_course_statistics',
    'generate_performance_dashboard',
    'display_performance_dashboard',
    'export_module_performance',
    'analyze_course_performance_trends',
    'forecast_course_performance',
    'export_performance_summary',
    'performance_prediction_models',
    'forecast_overall_performance',

    # Miscellaneous
    'select_student',
    'percentage_to_letter',
    'letter_to_percentage',
    'generate_statistical_report',
    'generate_module_stats_report',
    'generate_all_modules_stats_report',
    'generate_course_stats_report',
    'generate_all_courses_stats_report',
    'generate_comprehensive_stats_report',
    'manage_competencies',
    'record_student_competencies',
    'student_progress_tracking',
    'analyze_student_progress',
    'intervention_recommendations',
    'generate_intervention_plan',
    'display_intervention_recommendations',
    'success_probability_calculator',
    'calculate_individual_success_probability',
    'save_intervention_recommendations',
    'calculate_all_students_success_probability',
    'calculate_student_success_probability',
    'generate_system_recommendations',

    # Comparisons
    'compare_by_course',
    'display_course_comparison',
    'compare_by_gender',
    'compare_by_module_type',
    'perform_statistical_test',
    'compare_by_time_period',
    'custom_group_comparison',
    'compare_by_module_codes',
    'compare_by_enrollment_date',
    'compare_by_specific_courses',

    # Forecasting
    'export_batch_predictions',
    'forecast_single_course',
    'forecast_module_difficulty',
    'forecast_module_difficulty_single',
    'forecast_success_rates',
    'forecast_course_success_rate',
    'extract_comprehensive_student_features',
    'build_module_success_model',
    'create_dashboard_visualizations',
    'generate_dashboard_report',
    'generate_dashboard_recommendations',
    'generate_dashboard_alerts',
    'extract_student_features',

    # Trends
    'analyze_individual_student_trends',
    'collect_dashboard_data',
    'create_progress_visualization',
    'analyze_single_course_trends',
    'analyze_seasonal_trends',
    'analyze_monthly_patterns',
    'analyze_day_of_week_patterns',
    'analyze_academic_term_patterns',
    'trend_forecasting',
    'calculate_trend_slope',
    'create_trend_visualization',
    'create_individual_trend_visualization',
    'create_course_comparison_charts',
    'export_comparison_data',
]
