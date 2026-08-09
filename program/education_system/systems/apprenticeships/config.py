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
    "admission.decide",          # accept onto programme / decline
    # Cohort and people
    "apprentice.view",           # see apprentice records
    "apprentice.view_own",       # see only your own record
    "apprentice.manage",         # create / edit / withdraw
    "employer.view",
    "employer.manage",
    "staff.view",
    "staff.manage",
    # Programmes
    "programme.view",
    "programme.manage",
    # Delivery
    "training.view",
    "training.manage",           # schedule and register sessions
    "otj.view",
    "otj.log",                   # log your own off-the-job hours
    "otj.approve",               # employer / tutor sign-off
    # Portfolio
    "portfolio.view",
    "portfolio.upload",
    "portfolio.assess",          # provider assessor judgement
    "portfolio.verify",          # IQA sampling
    # Reviews
    "review.view",
    "review.conduct",
    "review.sign",
    "review.feedback",           # employer satisfaction feedback
    # Gateway and EPA
    "gateway.view",
    "gateway.request",
    "gateway.approve",
    "epa.view",
    "epa.book",
    "epa.grade",                 # EPAO only — record the outcome
    "epa.resit",
    # Correspondence
    "email.view",                # read the message log
    "email.send",                # compose and send
    # Money and compliance
    "funding.view",
    "funding.manage",
    "compliance.view",
    "compliance.manage",
    "report.view",
)

# Capabilities the training provider must not hold, however senior the
# account. End-Point Assessment is independent by law and by design: the
# organisation that delivered the training neither decides that its own
# apprentice has passed gateway nor grades the assessment. Granting these
# to an admin would make the independence cosmetic.
EPAO_EXCLUSIVE: frozenset[str] = frozenset({"gateway.approve", "epa.grade"})

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    ADMIN: frozenset(PERMISSIONS) - EPAO_EXCLUSIVE - frozenset({"apprentice.view_own"}),
    STAFF: frozenset({
        # See the queue, but not decide it — a tutor plans a caseload
        # around who is coming; admitting them is an admin act.
        "admission.view",
        "apprentice.view",
        "employer.view",
        "staff.view",
        "programme.view",
        "training.view", "training.manage",
        "otj.view", "otj.approve",
        "portfolio.view", "portfolio.assess", "portfolio.verify",
        "review.view", "review.conduct", "review.sign",
        "gateway.view", "gateway.request",
        "epa.view",
        # A tutor writes to their own caseload and the employers who
        # supervise them; that is ordinary delivery work, not admin.
        "email.view", "email.send",
        "compliance.view",
        "report.view",
    }),
    APPRENTICE: frozenset({
        "apprentice.view_own",
        # Read what the provider has sent them — not send. Outbound
        # correspondence is the provider's record; the apprentice's slice
        # of it is theirs to read.
        "email.view",
        "programme.view",
        "training.view",
        "otj.view", "otj.log",
        "portfolio.view", "portfolio.upload",
        "review.view", "review.sign",
        "gateway.view",
        "epa.view",
    }),
    EMPLOYER: frozenset({
        "apprentice.view",
        # An employer signs the commitment statement and takes part in
        # every review, so correspondence about their own apprentices is
        # theirs to read. Scoped to those apprentices by the service.
        "email.view",
        "employer.view",
        "programme.view",
        "training.view",
        "otj.view", "otj.approve",
        "portfolio.view",
        "review.view", "review.sign", "review.feedback",
        "gateway.view",
        "epa.view",
        "funding.view",
    }),
    END_POINT_ASSESSOR: frozenset({
        "apprentice.view",
        "programme.view",
        "gateway.view", "gateway.approve",
        "epa.view", "epa.book", "epa.grade", "epa.resit",
        "portfolio.view",
    }),
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
    "Applicant",          # applied, not yet started
    "On Programme",       # actively training
    "Break in Learning",  # paused, funding suspended, expected to return
    "Gateway",            # training complete, awaiting EPA
    "EPA",                # booked in with the EPAO
    "Completed",          # EPA passed
    "Withdrawn",          # left without completing
    "Transferred",        # moved to another provider
)

ACTIVE_STATUSES: frozenset[str] = frozenset({
    "On Programme", "Gateway", "EPA",
})

# Statuses that stop the funding clock. Break in Learning is the only
# pause that preserves the record for a later return.
NON_FUNDED_STATUSES: frozenset[str] = frozenset({
    "Applicant", "Break in Learning", "Completed", "Withdrawn", "Transferred",
})

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

# The pathway packages under ``pathways/`` key off this.
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

PROGRAMME_STATUSES: tuple[str, ...] = ("Draft", "Active", "Withdrawn")


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
    "Referred",      # sent back for more work
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
    "Scheduled", "In Progress", "Awaiting Signatures", "Complete", "Missed",
)

REVIEW_SIGNATORIES: tuple[str, ...] = ("provider", "apprentice", "employer")

REVIEW_INTERVAL_WEEKS: int = 12

RAG_RATINGS: tuple[str, ...] = ("Green", "Amber", "Red")

TARGET_STATUSES: tuple[str, ...] = ("Open", "Met", "Not Met", "Carried Forward")

SATISFACTION_SCALE: tuple[str, ...] = (
    "Very dissatisfied", "Dissatisfied", "Neutral", "Satisfied", "Very satisfied",
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
    "Not Ready", "Requested", "Approved", "Rejected",
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
    "Requested", "Scheduled", "In Progress", "Assessed", "Cancelled",
)

EPA_GRADES: tuple[str, ...] = ("Fail", "Pass", "Merit", "Distinction")

PASSING_GRADES: frozenset[str] = frozenset({"Pass", "Merit", "Distinction"})

# An apprentice may normally sit each method twice more after a fail.
MAX_RESITS: int = 2

RESIT_TYPES: tuple[str, ...] = (
    "Resit",    # re-sit a failed method
    "Retake",   # further training first, then re-sit
)


# ═════════════════════════════════════════════════════════════════════
# Functional skills
# ═════════════════════════════════════════════════════════════════════

FUNCTIONAL_SKILLS: tuple[str, ...] = ("English", "Maths")

FUNCTIONAL_SKILL_LEVELS: tuple[str, ...] = (
    "Entry 3", "Level 1", "Level 2", "GCSE 4/C", "GCSE 5+",
)

FUNCTIONAL_SKILL_STATUSES: tuple[str, ...] = (
    "Not started", "In progress", "Achieved", "Exempt",
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
    1: 1_500.0, 2: 2_000.0, 3: 2_500.0, 4: 3_000.0, 5: 3_500.0,
    6: 4_000.0, 7: 5_000.0, 8: 6_000.0, 9: 7_000.0, 10: 9_000.0,
    11: 12_000.0, 12: 15_000.0, 13: 18_000.0, 14: 21_000.0, 15: 27_000.0,
}

# The provider is paid monthly across the practical period, with the
# balance held back until the EPA completes.
COMPLETION_PAYMENT_SHARE: float = 0.20

PAYMENT_STATUSES: tuple[str, ...] = (
    "Scheduled", "Claimed", "Paid", "Withheld", "Clawed Back",
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
    "Missing", "Draft", "Awaiting Signature", "Signed", "Expired",
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
    "create", "update", "delete", "sign", "approve", "reject",
    "withdraw", "reinstate", "export", "grade",
)


# ═════════════════════════════════════════════════════════════════════
# Staff
# ═════════════════════════════════════════════════════════════════════

STAFF_ROLES: tuple[str, ...] = (
    "Tutor", "Trainer", "Assessor", "IQA", "Skills Coach", "Programme Manager",
)

# Above this, a caseload is flagged red on the admin dashboard.
CASELOAD_WARNING_THRESHOLD: int = 40
CASELOAD_MAXIMUM: int = 55

EMPLOYER_STATUSES: tuple[str, ...] = ("Prospect", "Active", "On Hold", "Ended")

EMPLOYER_SIZES: tuple[str, ...] = ("Micro", "Small", "Medium", "Large")


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
