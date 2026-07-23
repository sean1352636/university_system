"""
grade_calculation package - Split from the original grade_calculation.py

Re-exports all public functions for backward compatibility so that
existing imports like:
    from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation import calculate_gpa
continue to work.
"""

import os
try:
    import matplotlib.pyplot as plt
except Exception:  # Optional dependency or backend issues
    plt = None
from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.constants import (
    GRADE_SYSTEMS,
)

from education_system.post_18.university_system.infrastructure.database.db import get_connection


def init_basic_database():
    """Initialize the basic database tables (lazy import for test patching)."""
    from education_system.post_18.university_system.modules.domain.academics.grading.grade_tracking import (
        init_basic_database as _init_basic_database,
    )
    return _init_basic_database()

from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.conversions import (
    percentage_to_letter,
    letter_to_percentage,
    letter_to_gpa,
)

from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.db_init import (
    init_enhanced_grades_db,
)

from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.utils import (
    select_student,
    calculate_trend_slope,
    select_assessment,
    export_batch_predictions,
)

from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.grade_entry import (
    update_module_grade,
    record_assessment_grades,
    update_grades,
)

from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.gpa import (
    calculate_student_gpa,
    calculate_gpa,
)

from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.transcripts import (
    generate_transcript,
    create_transcript_pdf,
)

from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.statistics import (
    calculate_assessment_statistics,
    normalize_assessment_grades,
    validate_grade_data_integrity,
)

from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.visualization import (
    create_trend_visualization,
    view_grade_distribution,
    create_grade_visualizations,
    generate_assessment_stats_report,
)

from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.learning_outcomes import (
    map_assessments_to_outcomes,
    map_assessments_to_competencies,
)

from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.analytics import (
    assessment_performance_summary,
    analyze_specific_assessment,
    grade_distribution_analysis,
    analyze_by_assessment_type,
    analyze_all_assessments,
    analyze_distribution_by_assessment_type,
    compare_by_grade_threshold,
    analyze_overall_grade_trends,
    analyze_assessment_performance_trends,
    analyze_single_assessment_type_trends,
)

from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.risk_assessment import (
    assess_student_risk,
    student_risk_assessment,
    display_risk_assessment_results,
    save_risk_assessments,
)

from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.prediction import (
    extract_student_features,
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
    build_gpa_prediction_model,
    predict_student_gpa,
    predict_next_assessment_grade,
    predict_final_module_grade,
)

from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.views import (
    view_student_grades,
)

from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.menus import (
    display_enhanced_grade_menu,
    grade_curve_analysis_menu,
    competency_assessment_menu,
    grade_prediction,
)
