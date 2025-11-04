"""Re-exported helpers for student union administration."""

from __future__ import annotations

# Import union_context first to avoid circular imports
from university_system.modules.core.services.student_union_misc import union_context as context  # noqa: F401

from university_system.modules.core.services.student_union_misc.context_setup import set_auth
from university_system.modules.core.services.student_union_misc.union_db_schema import init_student_union_db
from university_system.modules.core.services.student_union_misc.points import (
    auto_award_points,
    award_points_to_student,
    view_all_checkouts,
    view_leaderboard,
    view_point_opportunities,
)
from university_system.modules.core.services.student_union_misc.competitions import (
    create_new_competition,
    update_competition_scores,
    view_active_competitions,
    view_competition_results,
    view_my_competition_history,
)
from university_system.modules.core.services.student_union_misc.facilities import view_facilities
from university_system.modules.core.services.student_union_misc.support import (
    anonymous_peer_matching,
    browse_support_groups,
    create_support_group,
    exam_preparation_groups,
    join_support_group,
    manage_academic_support,
    manage_peer_support_system,
    manage_peer_tutoring,
    manage_shared_resources,
    manage_study_groups,
    view_academic_workshops,
    view_my_support_groups,
    view_wellness_resources,
)
from university_system.modules.core.services.student_union_misc.sustainability import (
    green_certification_system,
    green_transport_tracking,
    manage_green_initiatives,
    track_carbon_footprint,
    view_eco_suppliers,
    waste_reduction_tracking,
)
from university_system.modules.core.services.student_union_misc.volunteering import (
    browse_volunteer_opportunities,
    signup_for_volunteer_opportunity,
    track_community_service_hours,
    view_my_volunteer_activities,
)
from university_system.modules.core.services.student_union_misc.analytics import (
    activity_correlation_analysis,
    generate_advanced_analytics,
    generate_personalized_recommendations,
    learning_analytics_dashboard,
    performance_benchmarking,
)
from university_system.modules.core.services.student_union_misc.events import (
    interactive_virtual_features,
    manage_learning_integration,
    manage_live_streaming,
    organize_academic_conferences,
    recording_and_replay_management,
    research_presentation_platform,
)
from university_system.modules.core.services.student_union_misc.voting import (
    access_control_review,
    approve_reject_materials,
    configure_voting_methods,
    log_configuration_change,
    manage_enhanced_voting,
    manage_union_reps,
    ranked_choice_voting,
    reset_voting_configuration,
    review_pending_materials,
    send_spending_warnings,
    test_email_notifications,
    view_detailed_spending,
)
from university_system.modules.core.services.student_union_misc.communications import send_confirmation_email
from university_system.modules.core.services.student_union_misc.menu import display_student_union_menu

__all__ = [
    "access_control_review",
    "activity_correlation_analysis",
    "anonymous_peer_matching",
    "approve_reject_materials",
    "auto_award_points",
    "award_points_to_student",
    "browse_support_groups",
    "browse_volunteer_opportunities",
    "configure_voting_methods",
    "context",  # Export context for backward compatibility
    "create_new_competition",
    "create_support_group",
    "display_student_union_menu",
    "exam_preparation_groups",
    "generate_advanced_analytics",
    "generate_personalized_recommendations",
    "green_certification_system",
    "green_transport_tracking",
    "init_student_union_db",
    "interactive_virtual_features",
    "join_support_group",
    "learning_analytics_dashboard",
    "log_configuration_change",
    "manage_academic_support",
    "manage_enhanced_voting",
    "manage_green_initiatives",
    "manage_learning_integration",
    "manage_live_streaming",
    "manage_peer_support_system",
    "manage_peer_tutoring",
    "manage_shared_resources",
    "manage_study_groups",
    "manage_union_reps",
    "organize_academic_conferences",
    "performance_benchmarking",
    "ranked_choice_voting",
    "recording_and_replay_management",
    "research_presentation_platform",
    "reset_voting_configuration",
    "review_pending_materials",
    "send_confirmation_email",
    "send_spending_warnings",
    "set_auth",
    "signup_for_volunteer_opportunity",
    "track_carbon_footprint",
    "track_community_service_hours",
    "update_competition_scores",
    "view_academic_workshops",
    "view_active_competitions",
    "view_all_checkouts",
    "view_competition_results",
    "view_detailed_spending",
    "view_eco_suppliers",
    "view_leaderboard",
    "view_my_competition_history",
    "view_my_support_groups",
    "view_my_volunteer_activities",
    "view_point_opportunities",
    "view_wellness_resources",
    "view_facilities",
    "waste_reduction_tracking",
]
