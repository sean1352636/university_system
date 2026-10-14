"""Domain package: class_groups."""
from education_system.systems.sixth_form.domain.academics.class_groups.class_groups import *  # noqa: F401,F403

# Sibling modules, in the attendance-package style: the core file keeps
# single-record CRUD, and each sibling owns one job. Imported by name so
# `from ...class_groups import class_group_membership` works without the
# caller reaching through to the full dotted path.
from education_system.systems.sixth_form.domain.academics.class_groups import (  # noqa: F401,E402
    class_group_allocation,
    class_group_capacity,
    class_group_conflicts,
    class_group_history,
    class_group_intake,
    class_group_logging,
    class_group_membership,
    class_group_schedule,
    class_group_structure,
    class_group_validation,
    class_group_waitlist,
)

# The bulk/cross-group operations, re-exported so callers that already do
# `from ...class_groups import add_member` can reach the batch forms the
# same way.
from education_system.systems.sixth_form.domain.academics.class_groups.class_group_membership import (  # noqa: F401,E402
    BulkResult,
    MemberDetail,
    Skip,
    add_members_bulk,
    clear_members,
    is_member,
    list_member_details,
    move_student,
    remove_members_bulk,
    swap_students,
    transfer_all_members,
)
from education_system.systems.sixth_form.domain.academics.class_groups.class_group_history import (  # noqa: F401,E402
    MembershipEvent,
    membership_history,
)
from education_system.systems.sixth_form.domain.academics.class_groups.class_group_intake import (  # noqa: F401,E402
    Candidate,
    bulk_enrol_from_course,
    preview_intake,
)

# Capacity, waitlist, allocation and structure operations.
from education_system.systems.sixth_form.domain.academics.class_groups.class_group_capacity import (  # noqa: F401,E402
    GroupCapacity,
    capacity_of,
    capacity_report,
    course_capacity_summary,
    is_full,
    is_over_capacity,
    list_full_groups,
    list_over_capacity,
    list_undersubscribed,
    remaining_capacity,
    set_capacity,
)
from education_system.systems.sixth_form.domain.academics.class_groups.class_group_waitlist import (  # noqa: F401,E402
    WaitlistEntry,
    add_to_waitlist,
    list_waitlist,
    promote_from_waitlist,
    promote_where_possible,
    remove_from_waitlist,
    waitlist_position,
)
from education_system.systems.sixth_form.domain.academics.class_groups.class_group_allocation import (  # noqa: F401,E402
    AllocationPlan,
    Placement,
    apply_plan,
    auto_allocate,
    balance_groups,
    baseline_scores,
    duplicate_placements,
    rebalance_by_attainment,
    suggest_group_for_student,
    unassigned_students,
)
from education_system.systems.sixth_form.domain.academics.class_groups.class_group_structure import (  # noqa: F401,E402
    SplitPlan,
    merge_groups,
    split_group,
)

# Schedule parsing, clash detection and integrity auditing.
from education_system.systems.sixth_form.domain.academics.class_groups.class_group_schedule import (  # noqa: F401,E402
    ParseReport,
    ScheduleWindow,
    format_schedule,
    parse_report,
    parse_schedule,
    reconcile,
    slot_windows,
)
from education_system.systems.sixth_form.domain.academics.class_groups.class_group_conflicts import (  # noqa: F401,E402
    Clash,
    SlotView,
    all_slots,
    clash_check,
    course_clash_summary,
    room_conflicts,
    student_timetable_clashes,
    teacher_conflicts,
)
from education_system.systems.sixth_form.domain.academics.class_groups.class_group_validation import (  # noqa: F401,E402
    AuditResult,
    audit_all_groups,
    duplicate_memberships,
    validate_group_integrity,
)
