"""The AI Content Detector's CLI menu (staff).

The detector runs as the signed-in member of staff; with nobody signed in,
or a student, the menu refuses. If the detector cannot load, no reading is
ever made up: the menu says so."""

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger

from education_system.systems.university.shell.cli.ai.ai_detector.basic_operations import (
    analyze_text_interface_safe, view_submission_history_safe,
    view_ai_detector_statistics_safe, run_ai_detector_demo_safe,
)
from education_system.systems.university.shell.cli.ai.ai_detector.enhanced_detection import (
    analyze_writing_style_fingerprint_cli, detect_paraphrasing_tools_cli,
    analyze_prompt_artifacts_cli, compare_draft_versions_cli,
    detect_translation_artifacts_cli, analyze_knowledge_consistency_cli,
    detect_copy_paste_patterns_cli, analyze_reference_authenticity_cli,
)
from education_system.systems.university.shell.cli.ai.ai_detector.student_management import (
    view_student_profile_cli, compare_students_cli,
    generate_student_report_card_cli, flag_student_for_review_cli,
    view_student_progression_cli, bulk_student_analysis_cli,
)
from education_system.systems.university.shell.cli.ai.ai_detector.analytics import (
    show_confidence_distribution_cli, generate_word_cloud_cli,
    plot_submission_timeline_cli, show_correlation_matrix_cli,
    cluster_similar_submissions_cli, generate_department_comparison_cli,
    show_weekly_trends_cli, export_visualization_pack_cli,
)
from education_system.systems.university.shell.cli.ai.ai_detector import review_operations as ops

STAFF_ROLES = ("staff", "instructor", "lecturer", "teacher", "faculty", "admin",
               "administrator", "superadmin")


class ConfigurationError(Exception):
    """The detector could not load."""


# The detector for this CLI session (built on first use).
ai_detector = None


def integrate_ai_detector_with_main(auth=None):
    """Build the detector once for this session. ``False`` if it cannot load."""
    global ai_detector
    try:
        from education_system.systems.university.shared.ai.ai_detector.detector.main import (
            AIDetector,
        )
        ai_detector = AIDetector(auth=auth)
        return True
    except Exception as exc:
        logger.error(f"Failed to initialize AI detector: {exc}")
        ai_detector = create_minimal_ai_detector(exc)
        return False


def create_minimal_ai_detector(error=None):
    """A stand-in that refuses everything plainly: no reading, no data."""
    reason = f"The AI detector could not load ({error}). " if error else \
        "The AI detector could not load. "

    class MinimalAIDetector:
        current_user = None
        component_errors = {"detector": str(error or "not loaded")}

        def set_auth(self, auth_obj):
            user = getattr(auth_obj, "current_user", None)
            self.current_user = user if isinstance(user, dict) else None

        def __getattr__(self, name):
            def refuse(*_args, **_kwargs):
                raise ConfigurationError(reason + "Ask an administrator to check it.")
            return refuse

    return MinimalAIDetector()


def _role(auth_obj):
    user = getattr(auth_obj, "current_user", None) or {}
    return str(user.get("role") or "").lower() if isinstance(user, dict) else ""


_MENU = (
    ("Readings", (
        ("1", "Take a reading of a text", analyze_text_interface_safe),
        ("2", "History", view_submission_history_safe),
        ("3", "Statistics", view_ai_detector_statistics_safe),
        ("4", "What a reading looks like (fixed example, not stored)", run_ai_detector_demo_safe),
    )),
    ("Enhanced detection (informational)", (
        ("5", "Writing style against a student's earlier work",
         analyze_writing_style_fingerprint_cli),
        ("6", "Paraphrasing-tool patterns", detect_paraphrasing_tools_cli),
        ("7", "Leftover prompt text", analyze_prompt_artifacts_cli),
        ("8", "Compare drafts", compare_draft_versions_cli),
        ("9", "Other-language paragraphs", detect_translation_artifacts_cli),
        ("10", "Against the module level", analyze_knowledge_consistency_cli),
        ("11", "Pasted / formatting traces", detect_copy_paste_patterns_cli),
        ("12", "References", analyze_reference_authenticity_cli),
    )),
    ("Students", (
        ("13", "A student's profile", view_student_profile_cli),
        ("14", "Compare two students", compare_students_cli),
        ("15", "Integrity summary", generate_student_report_card_cli),
        ("16", "Flag a student for review", flag_student_for_review_cli),
        ("17", "Readings over time", view_student_progression_cli),
        ("18", "A whole module", bulk_student_analysis_cli),
    )),
    ("Analytics", (
        ("19", "Spread of strengths", show_confidence_distribution_cli),
        ("20", "Frequent words", generate_word_cloud_cli),
        ("21", "Readings over time", plot_submission_timeline_cli),
        ("22", "How the indicators relate", show_correlation_matrix_cli),
        ("23", "Very similar texts", cluster_similar_submissions_cli),
        ("24", "By module", generate_department_comparison_cli),
        ("25", "Week by week", show_weekly_trends_cli),
        ("26", "Export a data pack", export_visualization_pack_cli),
    )),
    ("Review and administration", (
        ("27", "Alerts (no concern / refer / escalate)", ops.alerts_cli),
        ("28", "Batch readings and scheduled jobs", ops.batch_cli),
        ("29", "Review-outcome model", ops.model_cli),
        ("30", "Federated learning (officers)", ops.federated_cli),
        ("31", "Audit chain", ops.audit_chain_cli),
        ("32", "Processing queue", ops.realtime_cli),
        ("33", "Bias report (officers)", ops.bias_cli),
        ("34", "Review workload forecast", ops.predictive_cli),
        ("35", "Privacy and retention", ops.privacy_cli),
        ("36", "Settings", ops.settings_cli),
        ("37", "Student self-check preview", ops.self_check_preview_cli),
    )),
)


def display_ai_detector_menu_from_main(auth_obj):
    """The menu, for a signed-in member of staff."""
    global ai_detector
    if not auth_obj or not getattr(auth_obj, "current_user", None):
        print("Sign in to use the AI Content Detector.")
        return
    if _role(auth_obj) not in STAFF_ROLES:
        print("The AI Content Detector is for staff. Your own readings are in Academic "
              "Integrity.")
        return
    if ai_detector is None:
        print("Loading the AI detector...")
        if not integrate_ai_detector_with_main(auth_obj):
            print("The AI detector could not load; no readings can be taken.")
    ai_detector.set_auth(auth_obj)
    actions = {key: fn for _title, items in _MENU for key, _label, fn in items}
    while True:
        print("\nAI Content Detector — indicators for review, never a verdict")
        print("=" * 62)
        for title, items in _MENU:
            print(f"\n{title}:")
            for key, label, _fn in items:
                print(f" {key:>3}. {label}")
        print("\n   0. Back")
        choice = input("\nChoose: ").strip()
        if choice in ("0", ""):
            return
        action = actions.get(choice)
        if action is None:
            print("Not a choice.")
            continue
        try:
            action()
        except (PermissionError, ValueError, ConfigurationError) as exc:
            print(f"  {exc}")
        except Exception as exc:
            logger.exception("AI detector menu action failed")
            print(f"  That did not work: {exc}")


def fix_ai_detector_database_schema():
    """Bring the AI detector tables up to date (the integrity and detector
    schemas, migrations e2a4c6e8f0b3 / f3b5d7f9a1c4)."""
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        from education_system.systems.university.infrastructure.database.schemas import (
            ai_detector_schema,
        )
        conn = get_connection(row_factory=False)
        try:
            ai_detector_schema.apply_to_connection(conn)
            conn.commit()
        finally:
            conn.close()
        return True
    except Exception as e:
        print(f"Error applying the AI detector schema: {e}")
        return False
