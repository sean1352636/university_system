"""
Student Union Services Module

This module contains service layer implementations for student union operations.
"""

# Make union_context available as 'context' to avoid circular imports
from education_system.systems.university.domain.pastoral.student_life.student_union.services import union_context as context

# Export context_setup for auth initialization
from education_system.systems.university.domain.pastoral.student_life.student_union.services.context_setup import set_auth

# Lazy imports to avoid circular dependencies
# Functions are imported when accessed, not at module load time

def __getattr__(name):
    """Lazy import functions to avoid circular dependencies"""

    # Points management
    if name in ('view_all_checkouts', 'view_leaderboard', 'view_point_opportunities',
                'award_points_to_student', 'auto_award_points'):
        from education_system.systems.university.domain.pastoral.student_life.student_union.services import points
        return getattr(points, name)

    # Competitions
    if name in ('view_active_competitions', 'view_competition_results', 'view_my_competition_history',
                'create_new_competition', 'update_competition_scores'):
        from education_system.systems.university.domain.pastoral.student_life.student_union.services import competitions
        return getattr(competitions, name)

    # Facilities
    if name == 'view_facilities':
        from education_system.systems.university.domain.pastoral.student_life.student_union.services import facilities
        return getattr(facilities, name)

    # Support services
    if name in ('manage_peer_support_system', 'browse_support_groups', 'join_support_group',
                'view_my_support_groups', 'create_support_group', 'anonymous_peer_matching',
                'view_wellness_resources', 'manage_academic_support', 'manage_study_groups',
                'manage_peer_tutoring', 'manage_shared_resources', 'exam_preparation_groups',
                'view_academic_workshops'):
        from education_system.systems.university.domain.pastoral.student_life.student_union.services import support
        return getattr(support, name)

    # Sustainability
    if name in ('manage_green_initiatives', 'track_carbon_footprint', 'waste_reduction_tracking',
                'green_transport_tracking', 'view_eco_suppliers', 'green_certification_system'):
        from education_system.systems.university.domain.pastoral.student_life.student_union.services import sustainability
        return getattr(sustainability, name)

    # Volunteering
    if name in ('browse_volunteer_opportunities', 'signup_for_volunteer_opportunity',
                'view_my_volunteer_activities', 'track_community_service_hours'):
        from education_system.systems.university.domain.pastoral.student_life.student_union.services import volunteering
        return getattr(volunteering, name)

    # Analytics
    if name in ('generate_advanced_analytics', 'activity_correlation_analysis',
                'generate_personalized_recommendations', 'performance_benchmarking',
                'learning_analytics_dashboard'):
        from education_system.systems.university.domain.pastoral.student_life.student_union.services import analytics
        return getattr(analytics, name)

    # Events
    if name in ('manage_live_streaming', 'interactive_virtual_features',
                'recording_and_replay_management', 'manage_learning_integration',
                'organize_academic_conferences', 'research_presentation_platform'):
        from education_system.systems.university.domain.pastoral.student_life.student_union.services import events
        return getattr(events, name)

    # Voting
    if name in ('manage_enhanced_voting', 'ranked_choice_voting', 'configure_voting_methods',
                'review_pending_materials', 'send_spending_warnings', 'view_detailed_spending',
                'approve_reject_materials', 'access_control_review', 'log_configuration_change',
                'test_email_notifications', 'reset_voting_configuration', 'manage_union_reps'):
        from education_system.systems.university.domain.pastoral.student_life.student_union.services import voting
        return getattr(voting, name)

    # Communications
    if name == 'send_confirmation_email':
        from education_system.systems.university.domain.pastoral.student_life.student_union.services import communications
        return getattr(communications, name)

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    'context',
    'set_auth',
    # Points
    'view_all_checkouts',
    'view_leaderboard',
    'view_point_opportunities',
    'award_points_to_student',
    'auto_award_points',
    # Competitions
    'view_active_competitions',
    'view_competition_results',
    'view_my_competition_history',
    'create_new_competition',
    'update_competition_scores',
    # Facilities
    'view_facilities',
    # Support
    'manage_peer_support_system',
    'browse_support_groups',
    'join_support_group',
    'view_my_support_groups',
    'create_support_group',
    'anonymous_peer_matching',
    'view_wellness_resources',
    'manage_academic_support',
    'manage_study_groups',
    'manage_peer_tutoring',
    'manage_shared_resources',
    'exam_preparation_groups',
    'view_academic_workshops',
    # Sustainability
    'manage_green_initiatives',
    'track_carbon_footprint',
    'waste_reduction_tracking',
    'green_transport_tracking',
    'view_eco_suppliers',
    'green_certification_system',
    # Volunteering
    'browse_volunteer_opportunities',
    'signup_for_volunteer_opportunity',
    'view_my_volunteer_activities',
    'track_community_service_hours',
    # Analytics
    'generate_advanced_analytics',
    'activity_correlation_analysis',
    'generate_personalized_recommendations',
    'performance_benchmarking',
    'learning_analytics_dashboard',
    # Events
    'manage_live_streaming',
    'interactive_virtual_features',
    'recording_and_replay_management',
    'manage_learning_integration',
    'organize_academic_conferences',
    'research_presentation_platform',
    # Voting
    'manage_enhanced_voting',
    'ranked_choice_voting',
    'configure_voting_methods',
    'review_pending_materials',
    'send_spending_warnings',
    'view_detailed_spending',
    'approve_reject_materials',
    'access_control_review',
    'log_configuration_change',
    'test_email_notifications',
    'reset_voting_configuration',
    'manage_union_reps',
    # Communications
    'send_confirmation_email',
]
