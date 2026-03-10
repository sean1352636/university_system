"""
Alumni Management Package

Split from the monolithic alumni_management.py into focused submodules.
All public functions are re-exported here for backward compatibility.
"""

# Core infrastructure
from .core import (
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
from education_system.university_system.infrastructure.database.db import get_connection

# Data model
from .models import Alumni

# Database initialization
from .database import init_alumni_db, init_default_enhanced_data

# Profile management
from .profiles import (
    setup_alumni_directory,
    register_alumni,
    view_alumni,
    view_alumni_details,
    update_alumni,
)

# Events
from .events import (
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

# Donations & Fundraising
from .donations import (
    record_donation,
    view_donations,
    create_fundraising_campaign,
    view_fundraising_campaigns,
    view_campaign_performance,
    manage_donor_recognition,
    update_donor_recognition_levels,
    generate_recognition_report,
    manage_campaigns,
)

# Mentorship
from .mentorship import (
    setup_mentorship,
    view_mentorships,
    smart_mentorship_matching,
    create_recommended_mentorships,
)

# Stories
from .stories import (
    create_alumni_story,
    view_alumni_stories,
    read_full_story,
)

# Reunions
from .reunions import (
    manage_existing_reunion,
    view_class_reunions,
    manage_class_reunions,
    create_class_reunion,
    send_reunion_invitations,
    _send_simple_reunion_email,
)

# Regional Chapters
from .chapters import (
    view_my_chapters,
    admin_manage_chapters,
    manage_regional_chapters,
    view_regional_chapters,
    create_regional_chapter,
    join_regional_chapter,
)

# Directory & Networking
from .directory import (
    search_alumni_directory,
    send_connection_request,
    view_connection_requests,
    update_business_listing,
    manage_business_directory,
    view_business_directory,
    add_business_listing,
    search_business_directory,
)

# Communications
from .communications import (
    create_newsletter,
    send_newsletter_now,
)

# Forum
from .forum import (
    manage_alumni_forum,
    view_forum_posts,
    create_forum_post,
    view_forum_post_details,
    add_forum_reply,
)

# Jobs & Career Services
from .jobs import (
    post_job_opportunity,
    view_job_board,
    view_job_details,
    record_job_interest,
    schedule_career_counseling,
)

# Gamification & Engagement
from .gamification import (
    award_engagement_points,
    get_activity_description,
    check_badge_achievements,
    view_engagement_leaderboard,
    view_my_badges,
    generate_engagement_recommendations,
)

# Photos
from .photos import (
    manage_photo_gallery,
    view_photo_gallery,
    view_event_photos,
    upload_photos,
    view_my_photos,
    moderate_photos,
)

# Reports
from .reports import generate_alumni_report

# Menu & GUI
from .menu import (
    display_alumni_menu,
    display_alumni_relations_menu,
    launch_alumni_relations_gui,
)

__all__ = [
    'display_alumni_menu',
    'display_alumni_relations_menu',
    'launch_alumni_relations_gui',
    'setup_alumni_permissions',
]
