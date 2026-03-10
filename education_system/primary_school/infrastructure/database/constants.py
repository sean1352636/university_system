"""Database constants for the Primary School Management System."""

# ── Connection settings ───────────────────────────────────────────────────
CONNECTION_TIMEOUT = 30
BUSY_TIMEOUT = 5000

# ── Key stages ────────────────────────────────────────────────────────────
KEY_STAGES = {
    "EYFS": ["Reception"],
    "KS1": ["Year 1", "Year 2"],
    "KS2": ["Year 3", "Year 4", "Year 5", "Year 6"],
}

YEAR_GROUPS = ["Reception", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5", "Year 6"]

# ── Assessment levels ─────────────────────────────────────────────────────
ASSESSMENT_LEVELS = ["Emerging", "Developing", "Expected", "Greater Depth"]

EYFS_PROFILE_LEVELS = ["Emerging", "Expected", "Exceeding"]

# ── Attendance statuses ───────────────────────────────────────────────────
ATTENDANCE_STATUSES = {
    "/": "Present (AM)",
    "\\": "Present (PM)",
    "B": "Off-site educational activity",
    "C": "Authorised absence (other)",
    "D": "Dual registered",
    "E": "Excluded",
    "G": "Unauthorised holiday",
    "H": "Authorised holiday",
    "I": "Illness",
    "J": "Interview",
    "L": "Late (before register closes)",
    "M": "Medical/dental appointment",
    "N": "No reason provided",
    "O": "Unauthorised absence",
    "P": "Approved sporting activity",
    "R": "Religious observance",
    "S": "Study leave",
    "T": "Traveller absence",
    "U": "Late (after register closes)",
    "V": "Educational visit or trip",
    "W": "Work experience",
    "#": "School closed",
    "X": "Non-compulsory school age absence",
    "Y": "Unable to attend (exceptional)",
    "Z": "Pupil not on roll",
}

# ── Behaviour categories ─────────────────────────────────────────────────
BEHAVIOUR_TYPES = ["positive", "negative"]

BEHAVIOUR_CATEGORIES = [
    "Kindness",
    "Helpfulness",
    "Good Manners",
    "Excellent Work",
    "Trying Hard",
    "Disruption",
    "Not Listening",
    "Unkindness",
    "Not Following Instructions",
    "Unsafe Behaviour",
]

# ── Reward types ──────────────────────────────────────────────────────────
REWARD_TYPES = [
    "House Point",
    "Star of the Week",
    "Sticker",
    "Golden Time",
    "Headteacher Award",
    "Certificate",
    "Reading Award",
    "Attendance Award",
]

# ── SEND categories ──────────────────────────────────────────────────────
SEND_CATEGORIES = [
    "Communication and Interaction",
    "Cognition and Learning",
    "Social, Emotional and Mental Health",
    "Sensory and/or Physical Needs",
]

SEND_STATUSES = ["SEN Support", "EHCP", "Monitoring", "No SEN"]

# ── Meal types ────────────────────────────────────────────────────────────
MEAL_TYPES = ["School Dinner", "Packed Lunch", "Home"]
MEAL_ENTITLEMENTS = ["Universal Free (EYFS/KS1)", "Free School Meals", "Paid"]

# ── Phonics screening ────────────────────────────────────────────────────
PHONICS_THRESHOLD = 32  # Pass mark for the phonics screening check

# ── SATs key stage levels ─────────────────────────────────────────────────
SATS_KS1_SUBJECTS = ["Reading", "Maths", "GPS"]
SATS_KS2_SUBJECTS = ["Reading", "Maths", "GPS", "Science (TA)"]
SATS_OUTCOMES = [
    "Has not met the expected standard",
    "Working towards the expected standard",
    "Working at the expected standard",
    "Working at greater depth within the expected standard",
]
