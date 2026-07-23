"""CLI interface functions for the AI Detector."""

from education_system.post_18.university_system.infrastructure.ai.ai_detector.cli.interface import (
    integrate_ai_detector_with_main,
    create_minimal_ai_detector,
    display_ai_detector_menu_from_main,
    fix_ai_detector_database_schema,
)
from education_system.post_18.university_system.infrastructure.ai.ai_detector.cli.basic_operations import (
    analyze_text_interface_safe,
    display_analysis_results_safe,
    view_submission_history_safe,
    view_ai_detector_statistics_safe,
    run_ai_detector_demo_safe,
    display_detailed_submission,
)
from education_system.post_18.university_system.infrastructure.ai.ai_detector.cli.enhanced_detection import (
    analyze_writing_style_fingerprint_cli,
    detect_paraphrasing_tools_cli,
    analyze_prompt_artifacts_cli,
    compare_draft_versions_cli,
    detect_translation_artifacts_cli,
    analyze_knowledge_consistency_cli,
    detect_copy_paste_patterns_cli,
    analyze_reference_authenticity_cli,
)
from education_system.post_18.university_system.infrastructure.ai.ai_detector.cli.student_management import (
    view_student_profile_cli,
    compare_students_cli,
    generate_student_report_card_cli,
    flag_student_for_review_cli,
    view_student_progression_cli,
    bulk_student_analysis_cli,
)
from education_system.post_18.university_system.infrastructure.ai.ai_detector.cli.analytics import (
    show_confidence_distribution_cli,
    generate_word_cloud_cli,
    plot_submission_timeline_cli,
    show_correlation_matrix_cli,
    cluster_similar_submissions_cli,
    generate_department_comparison_cli,
    show_weekly_trends_cli,
    export_visualization_pack_cli,
)
from education_system.post_18.university_system.infrastructure.ai.ai_detector.cli.demo import ultimate_demo, main

__all__ = [
    'integrate_ai_detector_with_main', 'create_minimal_ai_detector',
    'display_ai_detector_menu_from_main', 'fix_ai_detector_database_schema',
    'analyze_text_interface_safe', 'display_analysis_results_safe',
    'view_submission_history_safe', 'view_ai_detector_statistics_safe',
    'run_ai_detector_demo_safe', 'display_detailed_submission',
    'analyze_writing_style_fingerprint_cli', 'detect_paraphrasing_tools_cli',
    'analyze_prompt_artifacts_cli', 'compare_draft_versions_cli',
    'detect_translation_artifacts_cli', 'analyze_knowledge_consistency_cli',
    'detect_copy_paste_patterns_cli', 'analyze_reference_authenticity_cli',
    'view_student_profile_cli', 'compare_students_cli',
    'generate_student_report_card_cli', 'flag_student_for_review_cli',
    'view_student_progression_cli', 'bulk_student_analysis_cli',
    'show_confidence_distribution_cli', 'generate_word_cloud_cli',
    'plot_submission_timeline_cli', 'show_correlation_matrix_cli',
    'cluster_similar_submissions_cli', 'generate_department_comparison_cli',
    'show_weekly_trends_cli', 'export_visualization_pack_cli',
    'ultimate_demo', 'main',
]
