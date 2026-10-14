"""Vocabulary and access policy for the apprenticeships system.

Everything here is a closed set the services validate against and the
interfaces render as dropdowns. Keeping them in one module means a CLI
menu, a GUI combobox and a service-layer check can never disagree about
what a valid status is.

The funding numbers follow the ESFA apprenticeship funding rules as they
stood for 2024/25. They are policy, not physics — expect to revise them
each funding year.
"""

from __future__ import annotations

# ═════════════════════════════════════════════════════════════════════
# Roles
# ═════════════════════════════════════════════════════════════════════

ADMIN = "admin"
STAFF = "staff"
APPRENTICE = "apprentice"
EMPLOYER = "employer"
END_POINT_ASSESSOR = "end_point_assessor"

ROLES: tuple[str, ...] = (ADMIN, STAFF, APPRENTICE, EMPLOYER, END_POINT_ASSESSOR)

ROLE_LABELS: dict[str, str] = {
    ADMIN: "Provider Admin",
    STAFF: "Tutor / Assessor",
    APPRENTICE: "Apprentice",
    EMPLOYER: "Employer",
    END_POINT_ASSESSOR: "End-Point Assessor",
}

# Roles that belong to the training provider. Used for read-visibility:
# provider staff see formative assessment and caseload notes; the
# employer and the EPAO do not.
PROVIDER_ROLES: frozenset[str] = frozenset({ADMIN, STAFF})


# ═════════════════════════════════════════════════════════════════════
# Permissions
# ═════════════════════════════════════════════════════════════════════
#
# Verb granularity is deliberately coarse — one permission per screen's
# worth of capability. Finer-grained rules that depend on *which* record
# (an apprentice may only see their own portfolio) are enforced in the
# services by scoping the query, not by another permission.

PERMISSIONS: tuple[str, ...] = (
    # Admissions — deciding on people who have applied, whether they
    # walked in or were handed over by a school, college or university.
    # Separate from apprentice.manage: a tutor should be able to see who
    # is coming onto their caseload without being able to admit them.
    "admission.view",
    "admission.decide",  # accept onto programme / decline
    # Cohort and people
    "apprentice.view",  # see apprentice records
    "apprentice.view_own",  # see only your own record
    "apprentice.manage",  # create / edit / withdraw
    "employer.view",
    "employer.manage",
    "staff.view",
    "staff.manage",
    # Programmes
    "programme.view",
    "programme.manage",
    # Delivery
    "training.view",
    "training.manage",  # schedule and register sessions; build learning plans
    "plan.comment",  # add to the conversation on a learning plan
    "otj.view",
    "otj.log",  # log your own off-the-job hours
    "otj.approve",  # employer / tutor sign-off
    # Portfolio
    "portfolio.view",
    "portfolio.upload",
    "portfolio.assess",  # provider assessor judgement
    "portfolio.verify",  # IQA sampling
    # Reviews
    "review.view",
    "review.conduct",
    "review.sign",
    "review.feedback",  # employer satisfaction feedback
    # Gateway and EPA
    "gateway.view",
    "gateway.request",
    "gateway.approve",
    "epa.view",
    "epa.book",
    "epa.grade",  # EPAO only — record the outcome
    "epa.resit",
    # Correspondence
    "email.view",  # read the message log
    "email.send",  # compose and send
    # Money and compliance
    "funding.view",
    "funding.manage",
    "compliance.view",
    "compliance.manage",
    "report.view",
    # Progress: action plans and assignments
    "action.update",  # move along an action you own
    "assignment.view",
    "assignment.set",  # set and mark assignments
    "assignment.submit",  # hand in your own work
    "assignment.moderate",  # second-mark a sample (IQA)
    # Learner support
    "skills.view",  # functional skills and initial / diagnostic assessments
    "skills.assess",  # record initial / diagnostic assessments (exemptions: compliance.manage)
    "qualification.view",
    "qualification.manage",
    "support.view",  # reasonable adjustments and support arrangements
    "support.manage",
    "welfare.view",  # welfare concerns and case notes — restricted
    "welfare.manage",
    # Records
    "document.view",
    "document.upload",
    "document.approve",
    "signature.sign",  # sign plans, agreements and commitments
    # Employers
    "employer.contact",  # keep contacts and log conversations
    # Quality
    "complaint.raise",
    "complaint.manage",
    "appeal.raise",
    "appeal.decide",  # EPA-result appeals by the EPAO, the rest by the provider
    "survey.respond",
    "survey.view",  # read results
    "survey.manage",
    # Workspace
    "task.view",
    "calendar.view",
    "search.use",
)

# Capabilities the training provider must not hold, however senior the
# account. End-Point Assessment is independent by law and by design: the
# organisation that delivered the training neither decides that its own
# apprentice has passed gateway nor grades the assessment. Granting these
# to an admin would make the independence cosmetic.
EPAO_EXCLUSIVE: frozenset[str] = frozenset({"gateway.approve", "epa.grade"})

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    ADMIN: frozenset(PERMISSIONS) - EPAO_EXCLUSIVE - frozenset({"apprentice.view_own"}),
    STAFF: frozenset(
        {
            # See the queue, but not decide it — a tutor plans a caseload
            # around who is coming; admitting them is an admin act.
            "admission.view",
            "apprentice.view",
            "employer.view",
            "staff.view",
            "programme.view",
            "training.view",
            "training.manage",
            "plan.comment",
            "otj.view",
            "otj.approve",
            "portfolio.view",
            "portfolio.assess",
            "portfolio.verify",
            "review.view",
            "review.conduct",
            "review.sign",
            "gateway.view",
            "gateway.request",
            "epa.view",
            # A tutor writes to their own caseload and the employers who
            # supervise them; that is ordinary delivery work, not admin.
            "email.view",
            "email.send",
            "compliance.view",
            "report.view",
            "action.update",
            "assignment.view",
            "assignment.set",
            "assignment.moderate",
            "skills.view",
            "skills.assess",
            "qualification.view",
            "qualification.manage",
            "support.view",
            "support.manage",
            # Scoped further by the service to the tutor's own caseload.
            "welfare.view",
            "welfare.manage",
            "document.view",
            "document.upload",
            "document.approve",
            "signature.sign",
            "employer.contact",
            "complaint.raise",
            "survey.view",
            "task.view",
            "calendar.view",
            "search.use",
        }
    ),
    APPRENTICE: frozenset(
        {
            "apprentice.view_own",
            # Read what the provider has sent them — not send. Outbound
            # correspondence is the provider's record; the apprentice's slice
            # of it is theirs to read.
            "email.view",
            "programme.view",
            "training.view",
            # Their own plan is theirs to talk about, not to rewrite.
            "plan.comment",
            "otj.view",
            "otj.log",
            "portfolio.view",
            "portfolio.upload",
            "review.view",
            "review.sign",
            "gateway.view",
            "epa.view",
            "action.update",
            "assignment.view",
            "assignment.submit",
            "skills.view",
            "qualification.view",
            "support.view",
            "document.view",
            "document.upload",
            "signature.sign",
            "complaint.raise",
            "appeal.raise",
            "survey.respond",
            "task.view",
            "calendar.view",
            "search.use",
        }
    ),
    EMPLOYER: frozenset(
        {
            "apprentice.view",
            # An employer signs the commitment statement and takes part in
            # every review, so correspondence about their own apprentices is
            # theirs to read. Scoped to those apprentices by the service.
            "email.view",
            "employer.view",
            "programme.view",
            "training.view",
            "plan.comment",
            "otj.view",
            "otj.approve",
            "portfolio.view",
            "review.view",
            "review.sign",
            "review.feedback",
            "gateway.view",
            "epa.view",
            "funding.view",
            "action.update",
            "skills.view",
            "qualification.view",
            # Only arrangements the apprentice has agreed to share with them.
            "support.view",
            "document.view",
            "document.upload",
            "signature.sign",
            "complaint.raise",
            "survey.respond",
            "task.view",
            "calendar.view",
            "search.use",
        }
    ),
    END_POINT_ASSESSOR: frozenset(
        {
            "apprentice.view",
            "programme.view",
            "gateway.view",
            "gateway.approve",
            "epa.view",
            "epa.book",
            "epa.grade",
            "epa.resit",
            "portfolio.view",
            # EPA-category documents only, and appeals against EPA results
            # only — both narrowed by the services.
            "document.view",
            "appeal.decide",
            "complaint.raise",
            "task.view",
            "calendar.view",
            "search.use",
        }
    ),
}


def permissions_for(role: str | None) -> frozenset[str]:
    """Every permission *role* holds. Unknown roles hold none."""
    return ROLE_PERMISSIONS.get((role or "").strip().lower(), frozenset())


def can(role: str | None, permission: str) -> bool:
    """May *role* do *permission*?

    Unknown roles may do nothing. A typo'd role failing closed is a
    nuisance; failing open is an incident.
    """
    return permission in permissions_for(role)


# ═════════════════════════════════════════════════════════════════════
# Apprentice lifecycle
# ═════════════════════════════════════════════════════════════════════

APPRENTICE_STATUSES: tuple[str, ...] = (
    "Applicant",  # applied, not yet started
    "On Programme",  # actively training
    "Break in Learning",  # paused, funding suspended, expected to return
    "Gateway",  # training complete, awaiting EPA
    "EPA",  # booked in with the EPAO
    "Completed",  # EPA passed
    "Withdrawn",  # left without completing
    "Transferred",  # moved to another provider
)

ACTIVE_STATUSES: frozenset[str] = frozenset(
    {
        "On Programme",
        "Gateway",
        "EPA",
    }
)

# Statuses that stop the funding clock. Break in Learning is the only
# pause that preserves the record for a later return.
NON_FUNDED_STATUSES: frozenset[str] = frozenset(
    {
        "Applicant",
        "Break in Learning",
        "Completed",
        "Withdrawn",
        "Transferred",
    }
)

WITHDRAWAL_REASONS: tuple[str, ...] = (
    "Left employment",
    "Redundancy",
    "Personal circumstances",
    "Health",
    "Transferred to another provider",
    "Transferred to another programme",
    "Insufficient progress",
    "Gone into further education",
    "Dismissed",
    "Other",
)

BREAK_REASONS: tuple[str, ...] = (
    "Maternity / paternity",
    "Long-term sickness",
    "Personal circumstances",
    "Employer operational pause",
    "Awaiting functional skills resit",
    "Other",
)

# Youngest an apprentice may be on their first day: an apprenticeship is
# open to anyone who has left compulsory schooling, which in England is 16.
MINIMUM_AGE_AT_START: int = 16

# Someone who leaves within this many days of starting never counted as a
# start for funding, so nothing is claimable for them. Check against the
# current year's funding rules — the figures move.
QUALIFYING_PERIOD_DAYS: int = 42


# ═════════════════════════════════════════════════════════════════════
# Programmes
# ═════════════════════════════════════════════════════════════════════

# Apprenticeship levels map onto the Regulated Qualifications Framework.
PROGRAMME_LEVELS: tuple[int, ...] = (2, 3, 4, 5, 6, 7)

LEVEL_LABELS: dict[int, str] = {
    2: "Level 2 — Intermediate",
    3: "Level 3 — Advanced",
    4: "Level 4 — Higher",
    5: "Level 5 — Higher",
    6: "Level 6 — Degree",
    7: "Level 7 — Degree (Master's)",
}


# Names the level band a programme belongs to. There are no band-specific
# rules yet; when there are, they belong in domain/programmes/.
def pathway_for_level(level: int) -> str:
    """Which pathway rule-set governs an apprenticeship at *level*."""
    if level <= 2:
        return "intermediate"
    if level == 3:
        return "advanced"
    if level in (4, 5):
        return "higher"
    return "degree"


KSB_TYPES: tuple[str, ...] = ("Knowledge", "Skill", "Behaviour")

# Superseded: replaced by a newer version of the same standard. Closed to
# new enrolments, but still delivered to the apprentices already on it.
PROGRAMME_STATUSES: tuple[str, ...] = ("Draft", "Active", "Withdrawn", "Superseded")


# ═════════════════════════════════════════════════════════════════════
# Off-the-job training
# ═════════════════════════════════════════════════════════════════════
#
# The statutory minimum: 6 hours per week averaged over the practical
# period, for an apprentice working the standard 30+ hour week. The
# services compute the required total from the planned dates rather than
# storing it, so changing a planned end date re-baselines the target.

OTJ_MINIMUM_HOURS_PER_WEEK: float = 6.0
OTJ_STANDARD_WEEKLY_HOURS: float = 30.0

OTJ_ACTIVITY_TYPES: tuple[str, ...] = (
    "Teaching of theory",
    "Practical training",
    "Simulation exercise",
    "Online learning",
    "Learning support",
    "Shadowing",
    "Mentoring",
    "Industry visit",
    "Competition",
    "Assignment / project work",
    "Reflective account",
    "Other",
)

OTJ_STATUSES: tuple[str, ...] = ("Draft", "Submitted", "Approved", "Rejected")


# ═════════════════════════════════════════════════════════════════════
# Attendance
# ═════════════════════════════════════════════════════════════════════
#
# Marks are made on session registers (domain/training/sessions.py).
# Excused is an authorised absence and Absent an unauthorised one; either
# carries a reason from this list.

ABSENCE_REASONS: tuple[str, ...] = (
    "Sickness",
    "Medical appointment",
    # The employer did not release them. Worth chasing: it is the most
    # common reason an apprentice falls behind on off-the-job hours.
    "Work commitments",
    "Annual leave",
    "Family emergency",
    "Bereavement",
    "Transport",
    "No reason given",
    "Other",
)

# The one reason that cannot authorise an absence.
UNEXPLAINED_ABSENCE_REASON: str = "No reason given"

# Attendance rate RAG: at or above the target is Green, below the concern
# line is Red, and anything between is Amber.
ATTENDANCE_TARGET_PERCENT: float = 90.0
ATTENDANCE_CONCERN_PERCENT: float = 80.0

# Too few marked sessions and one absence swings the rate wildly, so a
# rate is only rated once there are this many.
ATTENDANCE_MIN_SESSIONS: int = 4

# This many unauthorised absences in a row is a concern whatever the rate.
ATTENDANCE_CONSECUTIVE_ABSENCE_ALERT: int = 3


# ═════════════════════════════════════════════════════════════════════
# Individual learning plan
# ═════════════════════════════════════════════════════════════════════
#
# Objectives say what the apprentice will achieve and by when; the plan
# items under them (training_plan_items) are the activities that get
# them there.

PLAN_ITEM_STATUSES: tuple[str, ...] = ("Planned", "In Progress", "Complete", "Deferred")

OBJECTIVE_STATUSES: tuple[str, ...] = (
    "Not started", "In progress", "Achieved", "Deferred", "Withdrawn",
)

# An open objective due within this many days shows Amber.
OBJECTIVE_DUE_SOON_DAYS: int = 14

PLAN_COMMENT_MAX_LENGTH: int = 2000


# ═════════════════════════════════════════════════════════════════════
# Portfolio
# ═════════════════════════════════════════════════════════════════════

EVIDENCE_TYPES: tuple[str, ...] = (
    "Witness statement",
    "Work product",
    "Observation record",
    "Professional discussion",
    "Reflective account",
    "Photograph",
    "Video",
    "Certificate",
    "Other",
)

EVIDENCE_STATUSES: tuple[str, ...] = (
    "Draft",
    "Submitted",
    "Accepted",
    "Referred",  # sent back for more work
    "Rejected",
)

# The judgement an assessor records against a KSB mapping.
KSB_COVERAGE_LEVELS: tuple[str, ...] = ("Not started", "Developing", "Competent")


# ═════════════════════════════════════════════════════════════════════
# Progress reviews
# ═════════════════════════════════════════════════════════════════════
#
# Tripartite: provider, apprentice and employer must all sign. The review
# is not complete — and does not count for funding evidence — until all
# three signatures are present.

REVIEW_STATUSES: tuple[str, ...] = (
    "Scheduled",
    "In Progress",
    "Awaiting Signatures",
    "Complete",
    "Missed",
)

REVIEW_SIGNATORIES: tuple[str, ...] = ("provider", "apprentice", "employer")

REVIEW_INTERVAL_WEEKS: int = 12

RAG_RATINGS: tuple[str, ...] = ("Green", "Amber", "Red")

TARGET_STATUSES: tuple[str, ...] = ("Open", "Met", "Not Met", "Carried Forward")

SATISFACTION_SCALE: tuple[str, ...] = (
    "Very dissatisfied",
    "Dissatisfied",
    "Neutral",
    "Satisfied",
    "Very satisfied",
)


# ═════════════════════════════════════════════════════════════════════
# Gateway and End-Point Assessment
# ═════════════════════════════════════════════════════════════════════
#
# Gateway is the checkpoint between training and assessment. Every
# requirement must be met before the EPAO will accept a booking.

GATEWAY_REQUIREMENTS: tuple[tuple[str, str], ...] = (
    ("otj_hours", "Off-the-job hours target met"),
    ("english", "English functional skills achieved or exempt"),
    ("maths", "Maths functional skills achieved or exempt"),
    ("portfolio", "Portfolio complete and all KSBs competent"),
    ("reviews", "Progress reviews up to date and signed"),
    ("employer_sign_off", "Employer confirms readiness"),
    ("minimum_duration", "Minimum 12-month practical period served"),
)

GATEWAY_STATUSES: tuple[str, ...] = (
    "Not Ready",
    "Requested",
    "Approved",
    "Rejected",
)

MINIMUM_PRACTICAL_PERIOD_DAYS: int = 365

EPA_METHODS: tuple[str, ...] = (
    "Professional discussion",
    "Portfolio interview",
    "Practical observation",
    "Knowledge test",
    "Project with report",
    "Presentation",
    "Multiple choice test",
    "Work-based project",
)

EPA_BOOKING_STATUSES: tuple[str, ...] = (
    "Requested",
    "Scheduled",
    "In Progress",
    "Assessed",
    "Cancelled",
)

EPA_GRADES: tuple[str, ...] = ("Fail", "Pass", "Merit", "Distinction")

PASSING_GRADES: frozenset[str] = frozenset({"Pass", "Merit", "Distinction"})

# An apprentice may normally sit each method twice more after a fail.
MAX_RESITS: int = 2

RESIT_TYPES: tuple[str, ...] = (
    "Resit",  # re-sit a failed method
    "Retake",  # further training first, then re-sit
)


# ═════════════════════════════════════════════════════════════════════
# Functional skills
# ═════════════════════════════════════════════════════════════════════

FUNCTIONAL_SKILLS: tuple[str, ...] = ("English", "Maths")

FUNCTIONAL_SKILL_LEVELS: tuple[str, ...] = (
    "Entry 3",
    "Level 1",
    "Level 2",
    "GCSE 4/C",
    "GCSE 5+",
)

FUNCTIONAL_SKILL_STATUSES: tuple[str, ...] = (
    "Not started",
    "In progress",
    "Achieved",
    "Exempt",
)

EXEMPTION_REASONS: tuple[str, ...] = (
    "Prior GCSE grade 4/C or above",
    "Prior Level 2 functional skill",
    "Equivalent overseas qualification",
    "Education, health and care plan",
    "Learning difficulty assessment",
)


# ═════════════════════════════════════════════════════════════════════
# Funding
# ═════════════════════════════════════════════════════════════════════

# Employers with a pay bill above the threshold pay the levy and draw
# down from their digital account. Everyone else co-invests.
LEVY_THRESHOLD_PAYBILL: float = 3_000_000.0
LEVY_RATE: float = 0.005
LEVY_ALLOWANCE: float = 15_000.0

# Non-levy co-investment: the government pays this share, the employer
# the rest. Small employers taking a young apprentice pay nothing.
CO_INVESTMENT_GOVERNMENT_SHARE: float = 0.95
SMALL_EMPLOYER_HEADCOUNT: int = 50
SMALL_EMPLOYER_FULL_FUNDING_MAX_AGE: int = 21

# ═════════════════════════════════════════════════════════════════════
# Correspondence
# ═════════════════════════════════════════════════════════════════════

MESSAGE_DIRECTIONS: tuple[str, ...] = ("Outgoing", "Incoming")

MESSAGE_CHANNELS: tuple[str, ...] = ("Email", "SMS", "Letter")

# Shaped by who an apprenticeship involves rather than by school
# vocabulary: most provider correspondence is with an employer or an
# EPAO, not with the learner.
MESSAGE_CATEGORIES: tuple[str, ...] = (
    "General",
    "Recruitment",
    "Employer",
    "Training",
    "Review",
    "Off-the-Job",
    "Gateway / EPA",
    "Funding",
    "Compliance",
    "Safeguarding",
)

MESSAGE_PRIORITIES: tuple[str, ...] = ("Low", "Normal", "High")

MESSAGE_STATUSES: tuple[str, ...] = ("Draft", "Sent", "Received", "Failed")


FUNDING_MODELS: tuple[str, ...] = ("Levy", "Co-investment", "Fully funded")

FUNDING_BANDS: dict[int, float] = {
    1: 1_500.0,
    2: 2_000.0,
    3: 2_500.0,
    4: 3_000.0,
    5: 3_500.0,
    6: 4_000.0,
    7: 5_000.0,
    8: 6_000.0,
    9: 7_000.0,
    10: 9_000.0,
    11: 12_000.0,
    12: 15_000.0,
    13: 18_000.0,
    14: 21_000.0,
    15: 27_000.0,
}

# The provider is paid monthly across the practical period, with the
# balance held back until the EPA completes.
COMPLETION_PAYMENT_SHARE: float = 0.20

PAYMENT_STATUSES: tuple[str, ...] = (
    "Scheduled",
    "Claimed",
    "Paid",
    "Withheld",
    "Clawed Back",
)

CURRENCY_SYMBOL: str = "£"


# ═════════════════════════════════════════════════════════════════════
# Compliance
# ═════════════════════════════════════════════════════════════════════

COMPLIANCE_DOCUMENTS: tuple[tuple[str, str], ...] = (
    ("training_plan", "Individual training plan"),
    ("commitment_statement", "Commitment statement"),
    ("training_agreement", "Apprenticeship agreement"),
    ("employer_contract", "Employer contract for services"),
    ("eligibility_evidence", "Eligibility evidence"),
    ("initial_assessment", "Initial needs assessment"),
    ("prior_learning", "Recognition of prior learning"),
)

DOCUMENT_STATUSES: tuple[str, ...] = (
    "Missing",
    "Draft",
    "Awaiting Signature",
    "Signed",
    "Expired",
)

ELIGIBILITY_CHECKS: tuple[tuple[str, str], ...] = (
    ("right_to_work", "Right to work in the UK"),
    ("residency", "Residency requirement met"),
    ("age", "Aged 16 or over at start"),
    ("contract_hours", "Contracted 30+ hours, or duration extended"),
    ("duration", "Programme runs at least 12 months"),
    ("prior_qualification", "Not a duplicate of prior learning"),
)

# How long a completed apprentice's record must be kept for audit.
RETENTION_YEARS: int = 7

AUDIT_ACTIONS: tuple[str, ...] = (
    "create",
    "update",
    "delete",
    "sign",
    "approve",
    "reject",
    "withdraw",
    "reinstate",
    "export",
    "grade",
    "admit",  # admissions: an applicant accepted onto programme
)


# ═════════════════════════════════════════════════════════════════════
# Staff
# ═════════════════════════════════════════════════════════════════════

STAFF_ROLES: tuple[str, ...] = (
    "Tutor",
    "Trainer",
    "Assessor",
    "IQA",
    "Skills Coach",
    "Programme Manager",
)

# Above this, a caseload is flagged red on the admin dashboard.
CASELOAD_WARNING_THRESHOLD: int = 40
CASELOAD_MAXIMUM: int = 55

EMPLOYER_STATUSES: tuple[str, ...] = ("Prospect", "Active", "On Hold", "Ended")

EMPLOYER_SIZES: tuple[str, ...] = ("Micro", "Small", "Medium", "Large")


# ═════════════════════════════════════════════════════════════════════
# Progress: action plans, assignments, skills matrix
# ═════════════════════════════════════════════════════════════════════
#
# Action plans are the targets agreed at progress reviews, given an owner
# and a priority so the people who have to do them can see and move them.
# Their statuses are TARGET_STATUSES above; "Carried Forward" is reserved
# for the carry-forward mechanism, which moves an outstanding action onto
# the apprentice's next review rather than letting it quietly lapse.

# Who has to do it. The apprentice and the employer may move the status
# of actions they own; provider staff may move anything in scope.
ACTION_OWNERS: tuple[str, ...] = ("Apprentice", "Employer", "Tutor")
ACTION_DEFAULT_OWNER: str = "Apprentice"

ACTION_PRIORITIES: tuple[str, ...] = ("Low", "Normal", "High")
ACTION_DEFAULT_PRIORITY: str = "Normal"

# An open action due within this many days shows Amber; past due, Red.
ACTION_DUE_SOON_DAYS: int = 7

ACTION_NOTE_MAX_LENGTH: int = 2000

# Assignments: work set, submitted, marked and moderated by the provider.
# Distinct from End-Point Assessment, which is the EPAO's and graded on
# config.EPA_GRADES; these are the provider's formative and summative
# assessments on the way there.
ASSIGNMENT_TYPES: tuple[str, ...] = (
    "Written assignment",
    "Practical observation",
    "Professional discussion",
    "Project",
    "Test",
    "Presentation",
)

ASSIGNMENT_STATUSES: tuple[str, ...] = (
    "Set",        # waiting on the apprentice
    "Submitted",  # waiting on a marker
    "Marked",     # graded; open to moderation
    "Referred",   # graded Refer with attempts left: back to the apprentice
    "Moderated",  # second-marked by someone other than the marker
    "Withdrawn",  # set in error or no longer needed
)

# Best first. Refer is the one grade that is not a pass.
ASSIGNMENT_GRADES: tuple[str, ...] = ("Distinction", "Merit", "Pass", "Refer")
ASSIGNMENT_REFER_GRADE: str = "Refer"

# The most attempts an assignment may allow, first submission included.
# Each assignment stores its own figure when set (never above this), so
# lowering the cap later does not strand work already under way.
ASSIGNMENT_MAX_ATTEMPTS: int = 3

ASSIGNMENT_MODERATION_OUTCOMES: tuple[str, ...] = ("Agreed", "Adjusted")

# An assignment still with the apprentice and due within this many days
# shows Amber.
ASSIGNMENT_DUE_SOON_DAYS: int = 7

ASSIGNMENT_SUBMISSION_MAX_LENGTH: int = 20000
ASSIGNMENT_BRIEF_MAX_LENGTH: int = 5000

# Skills matrix: how wide the text bar for one KSB's coverage level is.
SKILLS_MATRIX_BAR_WIDTH: int = 12


# ═════════════════════════════════════════════════════════════════════
# Learner support: functional skills, qualifications, adjustments, welfare
# ═════════════════════════════════════════════════════════════════════

# Initial and diagnostic assessments cover digital skills as well as
# English and Maths. Digital is deliberately kept out of
# FUNCTIONAL_SKILLS: gateway and compliance read that list as "the
# subjects an apprentice must achieve or be exempt from", and digital is
# assessed at the start without being a gateway requirement.
SKILLS_ASSESSMENT_SUBJECTS: tuple[str, ...] = (*FUNCTIONAL_SKILLS, "Digital")

SKILLS_ASSESSMENT_KINDS: tuple[str, ...] = ("Initial", "Diagnostic")

# The levels an initial or diagnostic tool places someone at, lowest
# first — the order is what "below target" is judged against.
SKILLS_ASSESSMENT_LEVELS: tuple[str, ...] = (
    "Pre-entry",
    "Entry 1",
    "Entry 2",
    "Entry 3",
    "Level 1",
    "Level 2",
    "Level 3",
)

# The level English and Maths have to reach for gateway. An assessment
# placing someone below it means functional-skills study goes in the plan.
SKILLS_TARGET_LEVEL: str = "Level 2"

QUALIFICATION_STATUSES: tuple[str, ...] = ("Held (prior)", "In progress", "Achieved")

# Regulated Qualifications Framework levels, as a qualification states them.
QUALIFICATION_LEVELS: tuple[str, ...] = (
    "Entry level",
    "Level 1",
    "Level 2",
    "Level 3",
    "Level 4",
    "Level 5",
    "Level 6",
    "Level 7",
    "Level 8",
)

SUPPORT_NEED_CATEGORIES: tuple[str, ...] = (
    "Learning difficulty",
    "Disability",
    "Mental health",
    "Medical condition",
    "Caring responsibilities",
    "English language",
    "Other",
)

SUPPORT_STATUSES: tuple[str, ...] = ("Active", "Under review", "Ended")

# An arrangement still in force whose review date falls within this many
# days shows Amber; one whose date has passed shows Red.
SUPPORT_REVIEW_DUE_SOON_DAYS: int = 14

WELFARE_CATEGORIES: tuple[str, ...] = (
    "Wellbeing",
    "Safeguarding",
    "Prevent",
    "Attendance",
    "Financial hardship",
    "Housing",
    "Other",
)

WELFARE_SEVERITIES: tuple[str, ...] = ("Low", "Medium", "High", "Critical")

WELFARE_STATUSES: tuple[str, ...] = ("Open", "Monitoring", "Escalated", "Closed")

# Everything except Closed is a live concern somebody is holding.
WELFARE_OPEN_STATUSES: frozenset[str] = frozenset({"Open", "Monitoring", "Escalated"})

# Shared by case notes, support notes and the free-text descriptions.
LEARNER_SUPPORT_NOTE_MAX_LENGTH: int = 4000

# ── Risk profile ─────────────────────────────────────────────────────
# Each warning sign adds points; the total decides the level. The weights
# say how much a tutor should worry about each sign on its own: an
# attendance concern is worth chasing by itself, whereas lagging a little
# on off-the-job hours is common and only matters alongside something else.
RISK_LEVELS: tuple[str, ...] = ("Low", "Medium", "High")

RISK_POINTS_ATTENDANCE: int = 2
RISK_POINTS_OTJ_BEHIND: int = 1
RISK_POINTS_OVERDUE_REVIEW: int = 1
RISK_POINTS_OVERDUE_OBJECTIVES: int = 1

# An open welfare concern adds points by its severity (the worst open one
# counts, not the sum, so logging a concern twice cannot double it).
RISK_POINTS_WELFARE: dict[str, int] = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}

# Overdue learning-plan objectives only count from this many upwards:
# one slipped target is ordinary, a pattern of them is not.
RISK_OVERDUE_OBJECTIVES_MIN: int = 2

RISK_MEDIUM_SCORE: int = 2
RISK_HIGH_SCORE: int = 4


# ═════════════════════════════════════════════════════════════════════
# Records: documents, signatures, audit
# ═════════════════════════════════════════════════════════════════════

# Uploaded files are filed under one of these. "EPA" is special: it is
# the only category the end-point assessor may see, because the EPAO is
# independent of the provider and has no business reading the formative
# record (see EPA_DOCUMENT_CATEGORY).
DOCUMENT_CATEGORIES: tuple[str, ...] = (
    "Identity",
    "Learning Agreement",
    "Commitment Statement",
    "Initial Assessment",
    "Reviews",
    "Training Evidence",
    "Certificates",
    "EPA",
    "Other",
)

EPA_DOCUMENT_CATEGORY: str = "EPA"

# An upload from an apprentice or employer waits for provider approval;
# one from provider staff is approved as it lands (they are the approver).
DOCUMENT_APPROVAL_STATUSES: tuple[str, ...] = ("Pending", "Approved", "Rejected")

# Big enough for a scanned multi-page agreement, small enough that one
# careless upload of a video cannot fill the disk.
DOCUMENT_MAX_BYTES: int = 20 * 1024 * 1024

# Documents, spreadsheets and images only. Nothing executable, and no
# HTML or SVG: files are opened in the user's browser, where either
# could run script.
DOCUMENT_EXTENSIONS: tuple[str, ...] = (
    ".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt",
    ".xls", ".xlsx", ".ods", ".csv",
    ".ppt", ".pptx", ".odp",
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
)

# A document expiring within this many days is flagged Amber; past its
# expiry date it is Red. Right-to-work evidence is the usual culprit.
DOCUMENT_EXPIRY_WARNING_DAYS: int = 30

# Who signs. Each role signs as exactly one of these, and only for the
# records inside its own scope; the end-point assessor never signs.
SIGNATORY_ROLES: tuple[str, ...] = ("Apprentice", "Employer", "Provider")

SIGNATORY_BY_ROLE: dict[str, str] = {
    ADMIN: "Provider",
    STAFF: "Provider",
    APPRENTICE: "Apprentice",
    EMPLOYER: "Employer",
}

# Required signatories per signable thing. A plain entity type is keyed
# by itself; a document is keyed "document:<category>", because only
# some categories are agreements that need signing. Anything absent
# needs no signatures.
SIGNATURE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "learning_plan": SIGNATORY_ROLES,
    "document:Learning Agreement": SIGNATORY_ROLES,
    "document:Commitment Statement": SIGNATORY_ROLES,
}

SIGNATURE_DEFAULT_STATEMENT: str = (
    "I have read this and I agree to it as it stands today."
)
SIGNATURE_STATEMENT_MAX_LENGTH: int = 500

# A value longer than this is cut short in an audit diff. The log is for
# seeing what changed, not for keeping a second copy of every notes field.
AUDIT_CHANGE_VALUE_MAX_LENGTH: int = 200


# ═════════════════════════════════════════════════════════════════════
# Employers and programmes: contacts, commitments, risk, curriculum
# ═════════════════════════════════════════════════════════════════════

# What a contact at an employer does for the apprenticeship. Stored on the
# employer_managers row; the signatory is still the is_primary flag.
EMPLOYER_CONTACT_ROLES: tuple[str, ...] = (
    "Primary contact",
    "HR",
    "Training manager",
    "Line manager / Supervisor",
    "Finance",
    "Levy account holder",
)

CONTACT_CHANNELS: tuple[str, ...] = ("Phone", "Email", "Visit", "Video call", "Meeting")

CONTACT_SUMMARY_MAX_LENGTH: int = 2000

# A follow-up due within this many days shows Amber.
CONTACT_FOLLOW_UP_SOON_DAYS: int = 7

COMMITMENT_CATEGORIES: tuple[str, ...] = (
    "Release for off-the-job training",
    "Mentoring",
    "Review attendance",
    "Health & safety",
    "Funding contribution",
    "Other",
)

COMMITMENT_STATUSES: tuple[str, ...] = ("Open", "Met", "Escalated", "Withdrawn")

# Still owed by the employer. Escalated is open with more people chasing it.
OUTSTANDING_COMMITMENT_STATUSES: frozenset[str] = frozenset({"Open", "Escalated"})

COMMITMENT_MAX_ESCALATION: int = 3

COMMITMENT_ESCALATION_LEVELS: dict[int, str] = {
    0: "Not escalated",
    1: "Tutor / skills coach",
    2: "Programme manager",
    3: "Senior leadership",
}

# Employer risk rating. Each indicator adds points; the total decides the
# level. Attendance uses ATTENDANCE_TARGET_PERCENT / ATTENDANCE_CONCERN_PERCENT.
EMPLOYER_RISK_LEVELS: tuple[str, ...] = ("Low", "Medium", "High")
EMPLOYER_RISK_RAG: dict[str, str] = {"Low": "Green", "Medium": "Amber", "High": "Red"}
EMPLOYER_RISK_MEDIUM_POINTS: int = 2
EMPLOYER_RISK_HIGH_POINTS: int = 4
# Share of active apprentices on track with off-the-job hours.
EMPLOYER_RISK_OTJ_TARGET_PERCENT: float = 80.0
EMPLOYER_RISK_OTJ_CONCERN_PERCENT: float = 60.0
# Overdue progress reviews: one is a point, this many is two.
EMPLOYER_RISK_OVERDUE_REVIEWS_CONCERN: int = 3
# A commitment escalated this far is a concern on its own.
EMPLOYER_RISK_ESCALATION_CONCERN_LEVEL: int = 2
# Mean employer satisfaction, 1-5 on config.SATISFACTION_SCALE.
EMPLOYER_RISK_SATISFACTION_TARGET: float = 3.5
EMPLOYER_RISK_SATISFACTION_CONCERN: float = 2.5

# A standard's first version. A new version is a new programme row sharing
# the reference, so apprentices on the old one keep it.
PROGRAMME_DEFAULT_VERSION: str = "1.0"

# Stages inside admissions. The apprentice stays 'Applicant' throughout;
# accepting takes them on programme and settles the stage at Enrolment.
ADMISSION_STAGES: tuple[str, ...] = ("Application", "Offer", "Enrolment")

OFFER_CONDITIONS_MAX_LENGTH: int = 2000


# ═════════════════════════════════════════════════════════════════════
# Quality: complaints, appeals, surveys
# ═════════════════════════════════════════════════════════════════════
#
# Complaints are open to everyone with a stake in an apprenticeship.
# Appeals are the apprentice's route to challenge a decision about them,
# and are routed by type: an appeal against an EPA result goes to the
# End-Point Assessment Organisation, never to the provider (see
# EPAO_EXCLUSIVE). Surveys are how the provider hears from apprentices
# and employers in aggregate, anonymously.

COMPLAINT_CATEGORIES: tuple[str, ...] = (
    "Teaching and training",
    "Assessment",
    "Employer",
    "Staff conduct",
    "Communication",
    "Facilities",
    "Other",
)

COMPLAINT_STATUSES: tuple[str, ...] = (
    "Received",
    "Acknowledged",
    "Investigating",
    "Resolved",
    "Escalated",  # referred to an external body after the provider's own process
    "Closed",
)

# Calendar days from receipt. The acknowledgement says "we have it and
# who is looking at it"; the response is the provider's answer.
COMPLAINT_ACK_DAYS: int = 5
COMPLAINT_RESPONSE_DAYS: int = 20

# Where a complaint goes when the provider's own process is exhausted.
# Offered as suggestions; the field also takes free text.
COMPLAINT_ESCALATION_BODIES: tuple[str, ...] = (
    "ESFA / DfE Apprenticeship Service",
    "Ofsted",
    "End-Point Assessment Organisation",
    "Awarding organisation",
    "Other",
)

COMPLAINT_MAX_LENGTH: int = 4000

APPEAL_TYPES: tuple[str, ...] = (
    "Assessment decision",
    "EPA result",
    "Gateway decision",
    "Withdrawal",
    "Other",
)

# The one type the provider neither sees nor decides.
EPA_RESULT_APPEAL: str = "EPA result"

APPEAL_STATUSES: tuple[str, ...] = (
    "Lodged",
    "Under review",
    "Upheld",
    "Partially upheld",
    "Rejected",
    "Withdrawn",
)

# Calendar days after the decision within which an appeal may be lodged,
# and after lodging within which it should be decided.
APPEAL_WINDOW_DAYS: int = 15
APPEAL_DECISION_DAYS: int = 20

SURVEY_AUDIENCES: tuple[str, ...] = ("Apprentice", "Employer")

SURVEY_KINDS: tuple[str, ...] = (
    "Satisfaction",
    "Training feedback",
    "End of programme",
    "Employer satisfaction",
)

# Which audiences each kind of survey may be sent to.
SURVEY_KIND_AUDIENCES: dict[str, tuple[str, ...]] = {
    "Satisfaction": ("Apprentice", "Employer"),
    "Training feedback": ("Apprentice",),
    "End of programme": ("Apprentice",),
    "Employer satisfaction": ("Employer",),
}

SURVEY_STATUSES: tuple[str, ...] = ("Draft", "Open", "Closed")

# Every question is answered on SATISFACTION_SCALE, scored 1 (Very
# dissatisfied) to 5 (Very satisfied), so each is phrased as "how
# satisfied are you with…".
SURVEY_QUESTIONS: dict[str, tuple[str, ...]] = {
    "Satisfaction": (
        "How satisfied are you with your apprenticeship overall?",
        "How satisfied are you with the support from your training provider?",
        "How satisfied are you with communication from your training provider?",
    ),
    "Training feedback": (
        "How satisfied are you with the quality of the teaching and training?",
        "How satisfied are you that training sessions are relevant to your job?",
        "How satisfied are you with the feedback you get on your work?",
        "How satisfied are you with the learning resources available to you?",
    ),
    "End of programme": (
        "How satisfied are you with your apprenticeship as a whole?",
        "How satisfied are you with how well you were prepared for end-point assessment?",
        "How satisfied are you with the skills you have gained for your career?",
        "How satisfied would you be recommending this provider to a friend?",
    ),
    "Employer satisfaction": (
        "How satisfied are you with the training your apprentices receive?",
        "How satisfied are you with communication from the training provider?",
        "How satisfied are you that the programme meets your business needs?",
        "How satisfied are you with the progress reviews?",
    ),
}

# Only apprentices this far through are asked about the programme as a
# whole; asking someone in month three is noise.
SURVEY_END_OF_PROGRAMME_STATUSES: frozenset[str] = frozenset({"EPA", "Completed"})

# Below this many responses the results are withheld: with one or two
# answers an average *is* somebody's answer, and anonymity is fiction.
SURVEY_ANONYMITY_THRESHOLD: int = 3

SURVEY_COMMENT_MAX_LENGTH: int = 2000


# ═════════════════════════════════════════════════════════════════════
# Workspace: tasks, calendar, workload, search
# ═════════════════════════════════════════════════════════════════════

# A dated task within this many days is "due soon"; the task list looks
# this far ahead at all. Two weeks is the horizon a tutor plans to.
TASK_DUE_SOON_DAYS: int = 7
TASK_HORIZON_DAYS: int = 14

# The calendar's default window, and the longest one it will build.
CALENDAR_DEFAULT_DAYS: int = 28
CALENDAR_MAX_DAYS: int = 366

# Open items on one person's plate before their workload shows Amber /
# Red — alongside the caseload-size thresholds above.
WORKLOAD_ITEMS_WARNING: int = 25
WORKLOAD_ITEMS_MAXIMUM: int = 40

SEARCH_MIN_LENGTH: int = 2
SEARCH_LIMIT_PER_KIND: int = 25


# ═════════════════════════════════════════════════════════════════════
# UI
# ═════════════════════════════════════════════════════════════════════

# Matches the house convention across the other five systems.
WIN_GEOMETRY: str = "1400x900"
WIN_MINSIZE: tuple[int, int] = (1200, 800)

# Semantic colours for RAG ratings and status tags, shared by every
# window so a red row means the same thing everywhere.
RAG_COLOURS: dict[str, str] = {
    "Green": "#d8f3dc",
    "Amber": "#ffe8c2",
    "Red": "#ffd0d0",
}

STATUS_COLOURS: dict[str, str] = {
    "On Programme": "#d8f3dc",
    "Gateway": "#cfe8ff",
    "EPA": "#e5d4ff",
    "Completed": "#d8f3dc",
    "Break in Learning": "#ffe8c2",
    "Withdrawn": "#ffd0d0",
    "Transferred": "#eeeeee",
    "Applicant": "#f5f5f5",
}

MUTED_FG: str = "#666666"
ERROR_FG: str = "#a00000"
EMPTY_CELL: str = "—"
