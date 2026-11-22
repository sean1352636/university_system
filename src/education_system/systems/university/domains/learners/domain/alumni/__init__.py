"""
Alumni Management Package

Split from the monolithic alumni_management.py into focused submodules.
All public functions are re-exported here for backward compatibility.
"""

# Core infrastructure
from education_system.systems.university.domains.learners.domain.alumni.core import (
    get_db_connection,
    safe_execute,
    get_auth,
    set_auth,
    auth,
    setup_alumni_permissions,
    DB_PATH,
    _AuthProxy,
    HAS_AUTH,
)

# Re-export get_connection for backward compatibility (used by GUI layer)
from education_system.systems.university.infrastructure.database.db import get_connection

# Data model
from education_system.systems.university.domains.learners.domain.alumni.models import Alumni

# Database initialization
from education_system.systems.university.domains.learners.domain.alumni.database import init_alumni_db, init_default_enhanced_data


# Events
from education_system.systems.university.domains.learners.domain.alumni.events import (
    view_events,
    search_events,
    view_event_details,
    view_my_event_registrations,
    register_for_event,
    create_enhanced_event,
    generate_event_qr_code,
    send_enhanced_event_notifications,
    send_enhanced_event_invitation,
    _send_simple_event_email,
    event_check_in_system,
    process_event_checkin,
)




# Reunions
from education_system.systems.university.domains.learners.domain.alumni.reunions import (
    manage_existing_reunion,
    view_class_reunions,
    manage_class_reunions,
    create_class_reunion,
    send_reunion_invitations,
    _send_simple_reunion_email,
)


# Directory & Networking
from education_system.systems.university.domains.learners.domain.alumni.directory import (
    send_connection_request,
    view_connection_requests,
    update_business_listing,
    manage_business_directory,
    view_business_directory,
    add_business_listing,
    search_business_directory,
)


# Forum
from education_system.systems.university.domains.learners.domain.alumni.forum import (
    manage_alumni_forum,
    view_forum_posts,
    create_forum_post,
    view_forum_post_details,
    add_forum_reply,
)

# Jobs & Career Services
from education_system.systems.university.domains.learners.domain.alumni.jobs import (
    post_job_opportunity,
    view_job_board,
    view_job_details,
    record_job_interest,
    schedule_career_counseling,
)

# Gamification & Engagement
from education_system.systems.university.domains.learners.domain.alumni.gamification import (
    award_engagement_points,
    get_activity_description,
    check_badge_achievements,
    view_engagement_leaderboard,
    view_my_badges,
    generate_engagement_recommendations,
)

# Photos
from education_system.systems.university.domains.learners.domain.alumni.photos import (
    manage_photo_gallery,
    view_photo_gallery,
    view_event_photos,
    upload_photos,
    view_my_photos,
    moderate_photos,
)

# Reports
from education_system.systems.university.domains.learners.domain.alumni.reports import generate_alumni_report, get_engagement_dashboard


__all__ = [
    'init_alumni_db',
    'set_auth',
    'setup_alumni_permissions',
]
