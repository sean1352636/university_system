"""Static configuration for the FE College system.

Everything here is a domain vocabulary constant — the option lists the GUI
combo-boxes and CLI prompts are built from, and the thresholds the reporting
service compares against. They live in one module so a college can retune its
policy (attendance thresholds, fee bands, grade scales) without hunting through
the interface layer.

Nothing here touches the filesystem or the database; paths belong to
:mod:`education_system.paths`.
"""

from __future__ import annotations

# ── Identity ────────────────────────────────────────────────────────────────

COLLEGE_NAME = "Riverside FE College"
COLLEGE_UKPRN = "10000000"  # Placeholder UK Provider Reference Number.
ACADEMIC_YEAR = "2025/26"

# The academic year runs Sept–Aug; terms drive timetable and reporting filters.
TERMS = ("Autumn", "Spring", "Summer")

# ── Learners ────────────────────────────────────────────────────────────────

# ESFA funding streams split 16-18 study programmes from adult provision, and
# the distinction changes both the funding rate and the reporting return.
LEARNER_TYPES = (
    "16-18 Study Programme",
    "19+ Adult Learner",
    "Apprentice",
    "Higher Education",
    "Part-time / Evening",
)

STUDENT_STATUSES = (
    "applicant",
    "enrolled",
    "withdrawn",
    "completed",
    "transferred",
)

# Learners on roll for day-to-day operations — registers, marking, timetables.
ACTIVE_STUDENT_STATUSES = ("enrolled",)

MODES_OF_STUDY = ("Full-time", "Part-time", "Evening", "Distance", "Blended")

# ── Curriculum ──────────────────────────────────────────────────────────────

# The qualification families an FE college actually delivers. Each maps to a
# regulated qualification type with its own grading scale (see GRADE_SCALES).
QUALIFICATION_TYPES = (
    "BTEC Level 1",
    "BTEC Level 2",
    "BTEC Level 3",
    "T-Level",
    "NVQ",
    "Access to HE Diploma",
    "Functional Skills",
    "GCSE Resit",
    "A-Level",
    "HNC/HND",
    "Short Course",
)

# Regulated Qualifications Framework levels an FE college delivers at.
QUALIFICATION_LEVELS = ("Entry", "1", "2", "3", "4", "5")

CURRICULUM_AREAS = (
    "Business & Professional",
    "Computing & Digital",
    "Construction & Built Environment",
    "Creative Arts & Media",
    "Engineering & Motor Vehicle",
    "Hair, Beauty & Wellbeing",
    "Health & Social Care",
    "Hospitality & Catering",
    "Public Services & Sport",
    "Science",
    "English & Maths",
    "Foundation Learning",
)

# Grade scales keyed by qualification family. The assessment service validates
# a submitted grade against the scale for the course's qualification type, so a
# BTEC unit can't accidentally be awarded a GCSE grade.
GRADE_SCALES: dict[str, tuple[str, ...]] = {
    "BTEC": ("Distinction*", "Distinction", "Merit", "Pass", "Referred", "Unclassified"),
    "T-Level": ("Distinction*", "Distinction", "Merit", "Pass", "Unclassified"),
    "NVQ": ("Competent", "Not Yet Competent"),
    "Access to HE Diploma": ("Distinction", "Merit", "Pass", "Unclassified"),
    "Functional Skills": ("Pass", "Fail"),
    "GCSE": ("9", "8", "7", "6", "5", "4", "3", "2", "1", "U"),
    "A-Level": ("A*", "A", "B", "C", "D", "E", "U"),
    "HNC/HND": ("Distinction", "Merit", "Pass", "Referred", "Unclassified"),
    "Short Course": ("Pass", "Fail"),
}

# Qualification type -> the GRADE_SCALES key that governs it.
QUALIFICATION_GRADE_SCALE: dict[str, str] = {
    "BTEC Level 1": "BTEC",
    "BTEC Level 2": "BTEC",
    "BTEC Level 3": "BTEC",
    "T-Level": "T-Level",
    "NVQ": "NVQ",
    "Access to HE Diploma": "Access to HE Diploma",
    "Functional Skills": "Functional Skills",
    "GCSE Resit": "GCSE",
    "A-Level": "A-Level",
    "HNC/HND": "HNC/HND",
    "Short Course": "Short Course",
}

# Grades that count as an achievement for the reporting service's pass rate.
PASSING_GRADES = frozenset(
    {
        "Distinction*",
        "Distinction",
        "Merit",
        "Pass",
        "Competent",
        "9",
        "8",
        "7",
        "6",
        "5",
        "4",
        "A*",
        "A",
        "B",
        "C",
        "D",
        "E",
    }
)

# ── Attendance ──────────────────────────────────────────────────────────────

# Register marks. ``present`` and ``late`` both count as attended for the
# headline attendance rate; only ``authorised``/``unauthorised`` are absences.
ATTENDANCE_MARKS = ("present", "late", "authorised", "unauthorised", "excused")
ATTENDING_MARKS = ("present", "late")

# ESFA-aligned thresholds the dashboards and reports colour against.
ATTENDANCE_TARGET_PCT = 90.0
ATTENDANCE_CONCERN_PCT = 85.0
ATTENDANCE_AT_RISK_PCT = 75.0

# ── Staff ───────────────────────────────────────────────────────────────────

STAFF_ROLES = (
    "Lecturer",
    "Assessor",
    "Course Leader",
    "Curriculum Manager",
    "Head of Department",
    "Learning Support Assistant",
    "Technician",
    "Student Services",
    "Exams Officer",
    "Administrator",
)

EMPLOYMENT_STATUSES = ("Full-time", "Part-time", "Fractional", "Sessional", "Agency", "Left")

# Teaching hours per week beyond which the workload report flags a lecturer.
FULL_TIME_TEACHING_HOURS = 24.0

# ── Finance ─────────────────────────────────────────────────────────────────

FEE_TYPES = ("Tuition", "Exam", "Registration", "Materials", "Trip", "Resit")
PAYMENT_METHODS = (
    "Card",
    "Bank Transfer",
    "Cash",
    "Cheque",
    "Direct Debit",
    "Employer",
    "Student Loan",
)
FUNDING_SOURCES = (
    "ESFA 16-18",
    "ESFA Adult Skills Fund",
    "Advanced Learner Loan",
    "Employer Funded",
    "Self Funded",
    "Bursary",
    "Higher Education (OfS)",
)
BURSARY_TYPES = (
    "Vulnerable Student",
    "Discretionary",
    "Free Meals",
    "Travel",
    "Childcare",
    "Equipment",
)

# ── Pastoral ────────────────────────────────────────────────────────────────

BEHAVIOUR_TYPES = ("Praise", "Concern", "Warning", "Formal Warning", "Suspension")
REFERRAL_TYPES = (
    "Safeguarding",
    "Wellbeing / Mental Health",
    "Learning Support",
    "Careers",
    "Financial Support",
    "Attendance",
)
REFERRAL_STATUSES = ("open", "in_progress", "closed")

# ── Communications ──────────────────────────────────────────────────────────

MESSAGE_DIRECTIONS = ("Outgoing", "Incoming")

# SMS and Letter are logged the same way as email: the college has to be able
# to show what it sent a learner, whatever it went out on.
MESSAGE_CHANNELS = ("Email", "SMS", "Letter")

MESSAGE_CATEGORIES = (
    "General",
    "Admissions",
    "Attendance",
    "Assessment",
    "Safeguarding",
    "Finance",
    "Employer",
    "Newsletter",
    "Reminder",
)

MESSAGE_PRIORITIES = ("Low", "Normal", "High")

# Draft -> Sent is the normal path. Failed exists so a delivery problem is
# visible in the log rather than silently looking like it was never written.
MESSAGE_STATUSES = ("Draft", "Sent", "Received", "Failed")

# ── Timetable ───────────────────────────────────────────────────────────────

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")

# One-hour teaching slots; FE timetables commonly run 09:00–21:00 to cover
# evening provision for adult learners.
PERIODS = (
    ("P1", "09:00", "10:00"),
    ("P2", "10:00", "11:00"),
    ("P3", "11:15", "12:15"),
    ("P4", "12:15", "13:15"),
    ("P5", "14:00", "15:00"),
    ("P6", "15:00", "16:00"),
    ("P7", "16:00", "17:00"),
    ("E1", "18:00", "19:00"),
    ("E2", "19:00", "20:00"),
    ("E3", "20:00", "21:00"),
)

ROOM_TYPES = (
    "Classroom",
    "IT Suite",
    "Workshop",
    "Laboratory",
    "Salon",
    "Kitchen",
    "Gym",
    "Studio",
    "Lecture Theatre",
)

# ── Interface ───────────────────────────────────────────────────────────────

# Matches the sizing convention used by the Finance and Library windows in the
# other systems: a fixed launch size with a floor, never maximised.
WINDOW_GEOMETRY = "1400x900"
WINDOW_MINSIZE = (1200, 800)

VERSION = "1.0.0"

__all__ = [n for n in dir() if n.isupper()]
