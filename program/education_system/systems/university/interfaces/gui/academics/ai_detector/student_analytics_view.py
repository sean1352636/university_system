"""Compatibility façade for the split implementation."""

from . import student_analytics_view_shared as _shared
from .student_analytics_view_shared import *  # noqa: F401,F403

from .student_analytics_view_parts import create_integrations_view as _part_1
create_integrations_view = _part_1.create_integrations_view
_shared.create_integrations_view = create_integrations_view
_shared.__all__.append("create_integrations_view") if "create_integrations_view" not in _shared.__all__ else None

from .student_analytics_view_parts import save_plagiarism_config as _part_2
_save_plagiarism_config = _part_2._save_plagiarism_config
_shared._save_plagiarism_config = _save_plagiarism_config
_shared.__all__.append("_save_plagiarism_config") if "_save_plagiarism_config" not in _shared.__all__ else None

from .student_analytics_view_parts import test_plagiarism_connection as _part_3
_test_plagiarism_connection = _part_3._test_plagiarism_connection
_shared._test_plagiarism_connection = _test_plagiarism_connection
_shared.__all__.append("_test_plagiarism_connection") if "_test_plagiarism_connection" not in _shared.__all__ else None

from .student_analytics_view_parts import load_integration_status as _part_4
_load_integration_status = _part_4._load_integration_status
_shared._load_integration_status = _load_integration_status
_shared.__all__.append("_load_integration_status") if "_load_integration_status" not in _shared.__all__ else None

from .student_analytics_view_parts import sync_with_plagiarism_checker as _part_5
sync_with_plagiarism_checker = _part_5.sync_with_plagiarism_checker
_shared.sync_with_plagiarism_checker = sync_with_plagiarism_checker
_shared.__all__.append("sync_with_plagiarism_checker") if "sync_with_plagiarism_checker" not in _shared.__all__ else None

from .student_analytics_view_parts import push_to_academic_record as _part_6
push_to_academic_record = _part_6.push_to_academic_record
_shared.push_to_academic_record = push_to_academic_record
_shared.__all__.append("push_to_academic_record") if "push_to_academic_record" not in _shared.__all__ else None

from .student_analytics_view_parts import create_enhanced_detection_view as _part_7
create_enhanced_detection_view = _part_7.create_enhanced_detection_view
_shared.create_enhanced_detection_view = create_enhanced_detection_view
_shared.__all__.append("create_enhanced_detection_view") if "create_enhanced_detection_view" not in _shared.__all__ else None

from .student_analytics_view_parts import load_draft_files as _part_8
_load_draft_files = _part_8._load_draft_files
_shared._load_draft_files = _load_draft_files
_shared.__all__.append("_load_draft_files") if "_load_draft_files" not in _shared.__all__ else None

from .student_analytics_view_parts import analyze_writing_style_fingerprint as _part_9
analyze_writing_style_fingerprint = _part_9.analyze_writing_style_fingerprint
_shared.analyze_writing_style_fingerprint = analyze_writing_style_fingerprint
_shared.__all__.append("analyze_writing_style_fingerprint") if "analyze_writing_style_fingerprint" not in _shared.__all__ else None

from .student_analytics_view_parts import detect_paraphrasing_tools as _part_10
detect_paraphrasing_tools = _part_10.detect_paraphrasing_tools
_shared.detect_paraphrasing_tools = detect_paraphrasing_tools
_shared.__all__.append("detect_paraphrasing_tools") if "detect_paraphrasing_tools" not in _shared.__all__ else None

from .student_analytics_view_parts import analyze_prompt_artifacts as _part_11
analyze_prompt_artifacts = _part_11.analyze_prompt_artifacts
_shared.analyze_prompt_artifacts = analyze_prompt_artifacts
_shared.__all__.append("analyze_prompt_artifacts") if "analyze_prompt_artifacts" not in _shared.__all__ else None

from .student_analytics_view_parts import compare_draft_versions as _part_12
compare_draft_versions = _part_12.compare_draft_versions
_shared.compare_draft_versions = compare_draft_versions
_shared.__all__.append("compare_draft_versions") if "compare_draft_versions" not in _shared.__all__ else None

from .student_analytics_view_parts import detect_translation_artifacts as _part_13
detect_translation_artifacts = _part_13.detect_translation_artifacts
_shared.detect_translation_artifacts = detect_translation_artifacts
_shared.__all__.append("detect_translation_artifacts") if "detect_translation_artifacts" not in _shared.__all__ else None

from .student_analytics_view_parts import analyze_knowledge_consistency as _part_14
analyze_knowledge_consistency = _part_14.analyze_knowledge_consistency
_shared.analyze_knowledge_consistency = analyze_knowledge_consistency
_shared.__all__.append("analyze_knowledge_consistency") if "analyze_knowledge_consistency" not in _shared.__all__ else None

from .student_analytics_view_parts import detect_copy_paste_patterns as _part_15
detect_copy_paste_patterns = _part_15.detect_copy_paste_patterns
_shared.detect_copy_paste_patterns = detect_copy_paste_patterns
_shared.__all__.append("detect_copy_paste_patterns") if "detect_copy_paste_patterns" not in _shared.__all__ else None

from .student_analytics_view_parts import analyze_reference_authenticity as _part_16
analyze_reference_authenticity = _part_16.analyze_reference_authenticity
_shared.analyze_reference_authenticity = analyze_reference_authenticity
_shared.__all__.append("analyze_reference_authenticity") if "analyze_reference_authenticity" not in _shared.__all__ else None

from .student_analytics_view_parts import create_student_management_view as _part_17
create_student_management_view = _part_17.create_student_management_view
_shared.create_student_management_view = create_student_management_view
_shared.__all__.append("create_student_management_view") if "create_student_management_view" not in _shared.__all__ else None

from .student_analytics_view_parts import view_student_profile as _part_18
view_student_profile = _part_18.view_student_profile
_shared.view_student_profile = view_student_profile
_shared.__all__.append("view_student_profile") if "view_student_profile" not in _shared.__all__ else None

from .student_analytics_view_parts import compare_students as _part_19
compare_students = _part_19.compare_students
_shared.compare_students = compare_students
_shared.__all__.append("compare_students") if "compare_students" not in _shared.__all__ else None

from .student_analytics_view_parts import generate_student_report_card as _part_20
generate_student_report_card = _part_20.generate_student_report_card
_shared.generate_student_report_card = generate_student_report_card
_shared.__all__.append("generate_student_report_card") if "generate_student_report_card" not in _shared.__all__ else None

from .student_analytics_view_parts import flag_student_for_review as _part_21
flag_student_for_review = _part_21.flag_student_for_review
_shared.flag_student_for_review = flag_student_for_review
_shared.__all__.append("flag_student_for_review") if "flag_student_for_review" not in _shared.__all__ else None

from .student_analytics_view_parts import view_student_progression as _part_22
view_student_progression = _part_22.view_student_progression
_shared.view_student_progression = view_student_progression
_shared.__all__.append("view_student_progression") if "view_student_progression" not in _shared.__all__ else None

from .student_analytics_view_parts import bulk_student_analysis as _part_23
bulk_student_analysis = _part_23.bulk_student_analysis
_shared.bulk_student_analysis = bulk_student_analysis
_shared.__all__.append("bulk_student_analysis") if "bulk_student_analysis" not in _shared.__all__ else None

from .student_analytics_view_parts import create_advanced_analytics_view as _part_24
create_advanced_analytics_view = _part_24.create_advanced_analytics_view
_shared.create_advanced_analytics_view = create_advanced_analytics_view
_shared.__all__.append("create_advanced_analytics_view") if "create_advanced_analytics_view" not in _shared.__all__ else None

from .student_analytics_view_parts import show_detection_confidence_distribution as _part_25
show_detection_confidence_distribution = _part_25.show_detection_confidence_distribution
_shared.show_detection_confidence_distribution = show_detection_confidence_distribution
_shared.__all__.append("show_detection_confidence_distribution") if "show_detection_confidence_distribution" not in _shared.__all__ else None

from .student_analytics_view_parts import generate_word_cloud as _part_26
generate_word_cloud = _part_26.generate_word_cloud
_shared.generate_word_cloud = generate_word_cloud
_shared.__all__.append("generate_word_cloud") if "generate_word_cloud" not in _shared.__all__ else None

from .student_analytics_view_parts import plot_submission_timeline as _part_27
plot_submission_timeline = _part_27.plot_submission_timeline
_shared.plot_submission_timeline = plot_submission_timeline
_shared.__all__.append("plot_submission_timeline") if "plot_submission_timeline" not in _shared.__all__ else None

from .student_analytics_view_parts import show_correlation_matrix as _part_28
show_correlation_matrix = _part_28.show_correlation_matrix
_shared.show_correlation_matrix = show_correlation_matrix
_shared.__all__.append("show_correlation_matrix") if "show_correlation_matrix" not in _shared.__all__ else None

from .student_analytics_view_parts import cluster_similar_submissions as _part_29
cluster_similar_submissions = _part_29.cluster_similar_submissions
_shared.cluster_similar_submissions = cluster_similar_submissions
_shared.__all__.append("cluster_similar_submissions") if "cluster_similar_submissions" not in _shared.__all__ else None

from .student_analytics_view_parts import generate_department_comparison as _part_30
generate_department_comparison = _part_30.generate_department_comparison
_shared.generate_department_comparison = generate_department_comparison
_shared.__all__.append("generate_department_comparison") if "generate_department_comparison" not in _shared.__all__ else None

from .student_analytics_view_parts import show_weekly_trends as _part_31
show_weekly_trends = _part_31.show_weekly_trends
_shared.show_weekly_trends = show_weekly_trends
_shared.__all__.append("show_weekly_trends") if "show_weekly_trends" not in _shared.__all__ else None

from .student_analytics_view_parts import export_visualization_pack as _part_32
export_visualization_pack = _part_32.export_visualization_pack
_shared.export_visualization_pack = export_visualization_pack
_shared.__all__.append("export_visualization_pack") if "export_visualization_pack" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['_load_draft_files', '_load_integration_status', '_save_plagiarism_config', '_test_plagiarism_connection', 'analyze_knowledge_consistency', 'analyze_prompt_artifacts', 'analyze_reference_authenticity', 'analyze_writing_style_fingerprint', 'bulk_student_analysis', 'cluster_similar_submissions', 'compare_draft_versions', 'compare_students', 'create_advanced_analytics_view', 'create_enhanced_detection_view', 'create_integrations_view', 'create_student_management_view', 'detect_copy_paste_patterns', 'detect_paraphrasing_tools', 'detect_translation_artifacts', 'export_visualization_pack', 'flag_student_for_review', 'generate_department_comparison', 'generate_student_report_card', 'generate_word_cloud', 'plot_submission_timeline', 'push_to_academic_record', 'show_correlation_matrix', 'show_detection_confidence_distribution', 'show_weekly_trends', 'sync_with_plagiarism_checker', 'view_student_profile', 'view_student_progression']}
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14, _part_15, _part_16, _part_17, _part_18, _part_19, _part_20, _part_21, _part_22, _part_23, _part_24, _part_25, _part_26, _part_27, _part_28, _part_29, _part_30, _part_31, _part_32]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14, _part_15, _part_16, _part_17, _part_18, _part_19, _part_20, _part_21, _part_22, _part_23, _part_24, _part_25, _part_26, _part_27, _part_28, _part_29, _part_30, _part_31, _part_32]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['_load_draft_files', '_load_integration_status', '_save_plagiarism_config', '_test_plagiarism_connection', 'analyze_knowledge_consistency', 'analyze_prompt_artifacts', 'analyze_reference_authenticity', 'analyze_writing_style_fingerprint', 'bulk_student_analysis', 'cluster_similar_submissions', 'compare_draft_versions', 'compare_students', 'create_advanced_analytics_view', 'create_enhanced_detection_view', 'create_integrations_view', 'create_student_management_view', 'detect_copy_paste_patterns', 'detect_paraphrasing_tools', 'detect_translation_artifacts', 'export_visualization_pack', 'flag_student_for_review', 'generate_department_comparison', 'generate_student_report_card', 'generate_word_cloud', 'plot_submission_timeline', 'push_to_academic_record', 'show_correlation_matrix', 'show_detection_confidence_distribution', 'show_weekly_trends', 'sync_with_plagiarism_checker', 'view_student_profile', 'view_student_progression']
