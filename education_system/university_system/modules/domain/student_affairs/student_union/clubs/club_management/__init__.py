from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports import set_auth, get_connection
from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management.clubs import (
    create_club,
    view_clubs,
    manage_club,
)
from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management.membership import (
    join_club,
    view_my_clubs,
    club_member_directory,
)
from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management.finance import (
    view_club_financial_reports,
    manage_club_budgets,
)
from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management.discussions import (
    manage_club_discussions,
    view_discussion_details,
    manage_discussions_admin,
)
from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management.media import (
    manage_club_media,
)
from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management.mentorship import (
    manage_mentorship_system,
    find_mentor,
    become_mentor,
    view_my_mentorship_relationships,
    schedule_mentorship_session,
    view_mentorship_sessions,
    rate_mentorship_experience,
    search_mentors_by_skill,
)
from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management.rewards import (
    manage_engagement_rewards,
    view_my_points_and_badges,
    check_and_award_badges,
    view_available_badges,
    create_new_badge,
    manage_reward_system_admin,
)
from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management.competitions import (
    manage_interclub_competitions,
    register_club_for_competition,
)
from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management.community import (
    manage_community_engagement,
    engagement_trend_analysis,
    member_retention_insights,
    manage_book_clubs,
)
from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management.menu import (
    display_club_menu,
)
