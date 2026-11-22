"""Colours, system registry and table columns for the superadmin dashboard."""

from education_system import paths as _paths

# Which systems exist, in what order, and what they are called are read from
# paths — the one registry that already carries the short display names every
# console uses. This module used to keep its own copies, which is why adding a
# system left the dashboard silently showing a subset of the platform.
SYSTEM_ORDER = list(_paths.SYSTEM_ORDER)

SYSTEM_LABELS = dict(_paths.SYSTEM_LABELS)

# Presentation only, and the one thing genuinely local to this console. A
# system with no colour here still appears — in grey — rather than vanishing
# from the grid or raising a KeyError.
DEFAULT_SYSTEM_COLOR = "#7f8c8d"

SYSTEM_COLORS = {
    "university": "#2980b9",
    "sixth_form": "#27ae60",
    "secondary": "#8e44ad",
    "primary": "#e67e22",
    "nursery": "#16a085",
    "apprenticeships": "#c0392b",
    "fe_college": "#2c3e50",
    "special_education": "#1d4a3f",
    "adult_education": "#7a4b1e",
    "alternative_provision": "#4a3a6b",
    "training_provider": "#2f4f6b",
    "local_authority": "#3d5a3a",
}

# Sub-caption for the Quick Launch cards. Same rule: a system missing from
# here still gets a card, just without the blurb.
SYSTEM_BLURBS = {
    "nursery": "Birth - 5 years\nEYFS / Early Years",
    "primary": "Reception - Year 6\nEYFS / KS1 / KS2",
    "secondary": "Years 7 - 11\nKS3 / KS4 / GCSE",
    "sixth_form": "Years 12 - 13\nA-Levels / BTEC / T-Levels",
    "university": "Undergraduate & Postgraduate\nDegrees / Research",
    "apprenticeships": "Levels 2 - 7\nOn-the-job training / EPA",
    "fe_college": "16+ Further Education\nVocational / Access",
    "special_education": "0 - 25 SEND\nSEN Support / EHCPs",
    "adult_education": "19+ community learning\nAdult Skills Fund / ESOL",
    "alternative_provision": "PRUs & AP placements\nReferrals / Reintegration",
    "training_provider": "Short courses & CPD\nBookings / Certificates",
    "local_authority": "Council education duties\nAdmissions / Welfare / SEND",
}

# Launchable systems that are not cross-system members yet, so are absent from
# paths.SYSTEM_ORDER (the linked-platform list the health/transfer views use).
# Quick Launch shows them after the linked systems. Empty: the five
# placeholder scaffolds that used it were moved to remove/ (2026-11-06).
# Special Education (SEND) is signed-in and launchable but has no learner
# adapter or SYSTEM_DB_PATHS entry yet (2026-11-08). Adult Education and
# Alternative Provision, Training Provider and Local Authority likewise.
LAUNCH_ONLY_SYSTEMS: dict[str, str] = {
    "special_education": "Special Education (SEND) System",
    "adult_education": "Adult Education System",
    "alternative_provision": "Alternative Provision System",
    "training_provider": "Training Provider System",
    "local_authority": "Local Authority Education System",
}

SIDEBAR_BG = "#2c3e50"

SIDEBAR_BTN = "#34495e"

SIDEBAR_BTN_ACTIVE = "#1abc9c"

HEADER_BG = "#2c3e50"

CONTENT_BG = "#ecf0f1"

CARD_BG = "#ffffff"

TEXT_DARK = "#2c3e50"

TEXT_LIGHT = "#ffffff"

TEXT_MUTED = "#7f8c8d"

# Severity styling for the "Needs Attention" panel
ALERT_COLORS = {
    "critical": "#e74c3c",
    "warning": "#f39c12",
    "info": "#3498db",
}

ALERT_OK = "#2ecc71"

def _fmt_backup_age(days):
    """Human label for a last-backup age in whole days (None = never)."""
    if days is None:
        return "never"
    if days == 0:
        return "today"
    return f"{days} day" if days == 1 else f"{days} days"

# Comparison table columns: (id, heading, width, anchor, sort_key, format)
# sort_key maps None backups to a large sentinel so "never" sorts as worst.
COMPARISON_COLUMNS = [
    ("label", "System", 150, "w",
     lambda r: r["label"], lambda r: r["label"]),
    ("status", "Status", 80, "w",
     lambda r: r["status"], lambda r: r["status"].upper()),
    ("students", "Students", 80, "e",
     lambda r: r["student_count"], lambda r: str(r["student_count"])),
    ("staff", "Staff", 70, "e",
     lambda r: r["staff_count"], lambda r: str(r["staff_count"])),
    ("users", "Users", 70, "e",
     lambda r: r["user_count"], lambda r: str(r["user_count"])),
    ("db", "DB (MB)", 80, "e",
     lambda r: r["db_size_mb"], lambda r: f"{r['db_size_mb']:.1f}"),
    ("backup", "Last Backup", 100, "e",
     lambda r: r["last_backup_days"] if r["last_backup_days"] is not None else 10 ** 9,
     lambda r: _fmt_backup_age(r["last_backup_days"])),
    ("issues", "Issues", 60, "e",
     lambda r: r["open_issues"], lambda r: str(r["open_issues"])),
]
