"""Constants extracted from gui.py."""
from __future__ import annotations

PERSON_TYPES = ["Student", "Staff"]
DEPARTMENTS = [
    "Computing", "Engineering", "Business", "Law", "Medicine",
    "Arts & Humanities", "Social Sciences", "Natural Sciences",
    "Education", "Administration", "Other",
]
AGE_GROUPS = ["Under 18", "18-24", "25-34", "35-44", "45-54", "55-64", "65+", "Prefer not to say"]
GENDERS = ["Female", "Male", "Non-binary", "Other", "Prefer not to say"]
ETHNICITIES = [
    "White - British", "White - Other", "Asian - Indian", "Asian - Pakistani",
    "Asian - Chinese", "Asian - Other", "Black - African", "Black - Caribbean",
    "Mixed", "Arab", "Other", "Prefer not to say",
]
DISABILITY_STATUS = [
    "No known disability", "Physical", "Sensory", "Mental health",
    "Learning difficulty", "Long-term health condition", "Multiple", "Prefer not to say",
]
RELIGIONS = ["Christian", "Muslim", "Hindu", "Sikh", "Jewish", "Buddhist",
             "No religion", "Other", "Prefer not to say"]
SEXUAL_ORIENTATIONS = ["Heterosexual", "Gay/Lesbian", "Bisexual", "Other", "Prefer not to say"]
INCIDENT_CATEGORIES = [
    "Racial discrimination", "Gender discrimination", "Disability discrimination",
    "Religious discrimination", "Sexual orientation discrimination",
    "Age discrimination", "Harassment", "Bullying", "Other",
]
INCIDENT_STATUS = ["Open", "Under investigation", "Resolved", "Closed"]
SEVERITIES = ["Low", "Medium", "High", "Critical"]
SLA_DAYS = {"Low": 30, "Medium": 14, "High": 5, "Critical": 1}

FIELD_OPTIONS = {
    "person_type": PERSON_TYPES,
    "department": DEPARTMENTS,
    "age_group": AGE_GROUPS,
    "gender": GENDERS,
    "ethnicity": ETHNICITIES,
    "disability": DISABILITY_STATUS,
    "religion": RELIGIONS,
    "sexual_orientation": SEXUAL_ORIENTATIONS,
}

# feature 48 — themes
THEMES = {
    "light": {"bg": "#f4f6f9", "panel": "#ffffff", "accent": "#1e3a5f",
              "text": "#1a1a1a", "muted": "#666666", "header_fg": "#ffffff"},
    "dark":  {"bg": "#1c1f24", "panel": "#262b33", "accent": "#4aa3ff",
              "text": "#eaeaea", "muted": "#aaaaaa", "header_fg": "#ffffff"},
    "high":  {"bg": "#000000", "panel": "#000000", "accent": "#ffff00",
              "text": "#ffffff", "muted": "#ffff00", "header_fg": "#000000"},
}

PAGE_SIZE = 50
