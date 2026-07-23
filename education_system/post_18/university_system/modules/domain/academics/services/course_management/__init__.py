from education_system.post_18.university_system.modules.domain.academics.services.course_management.database import initialize_enhanced_database
from education_system.post_18.university_system.modules.domain.academics.services.course_management.validation import (
    validate_course_code,
    validate_email,
    validate_time_format,
    validate_days_of_week,
    check_circular_prerequisite,
)
from education_system.post_18.university_system.modules.domain.academics.services.course_management.courses import (
    create_enhanced_course,
    create_course,
    view_all_courses,
    update_course,
    delete_course,
    view_course_details,
)
from education_system.post_18.university_system.modules.domain.academics.services.course_management.prerequisites import (
    add_prerequisite,
    view_prerequisites,
    remove_prerequisite,
)
from education_system.post_18.university_system.modules.domain.academics.services.course_management.instructors import (
    create_instructor,
    view_instructors,
    assign_instructor_to_course,
)
from education_system.post_18.university_system.modules.domain.academics.services.course_management.scheduling import (
    create_course_schedule,
    view_course_schedules,
    update_schedule,
)
from education_system.post_18.university_system.modules.domain.academics.services.course_management.search import search_courses
from education_system.post_18.university_system.modules.domain.academics.services.course_management.import_export import (
    import_courses_from_csv,
    export_courses_to_csv,
    bulk_update_courses,
)
from education_system.post_18.university_system.modules.domain.academics.services.course_management.analytics import (
    generate_course_analytics,
    generate_enrollment_report,
    department_statistics,
)
from education_system.post_18.university_system.modules.domain.academics.services.course_management.waitlist import (
    add_to_waitlist,
    view_waitlists,
    process_waitlist,
)
from education_system.post_18.university_system.modules.domain.academics.services.course_management.recommendations import (
    recommend_courses,
    find_alternative_courses,
)
from education_system.post_18.university_system.modules.domain.academics.services.course_management.status import manage_course_status
from education_system.post_18.university_system.modules.domain.academics.services.course_management.history import view_course_history
from education_system.post_18.university_system.modules.domain.academics.services.course_management.maintenance import system_maintenance
from education_system.post_18.university_system.modules.domain.academics.services.course_management.menu import (
    display_enhanced_course_menu,
    display_course_management_menu,
)
