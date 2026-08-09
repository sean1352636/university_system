"""Single source of truth for the Nursery System menu.

Both ``gui_main.py`` and ``cli_main.py`` import ``NAV_CATEGORIES`` so the
GUI sidebar and the CLI menu always present the same options.

The feature set follows what a UK nursery / Early Years (EYFS) setting
is required to run: EYFS learning & development, the statutory welfare
requirements (ratios, safeguarding, paediatric first aid, accident and
medication logs), funded-hours handling (15/30 hours, 2-year-old
funding) and Ofsted/compliance reporting.

Every entry is a placeholder — domain modules will be wired in later.
"""

from __future__ import annotations

NAV_CATEGORIES: list[tuple[str, list[str]]] = [
    ("Children & Admissions", [
        "Child Directory",
        "Add Child",
        "Search Children",
        "Child Profile",
        "Admissions & Waiting List",
        "Registration & Enrolment",
        "Rooms & Age Groups",
        "Key Person Assignment",
        "Funded Hours (15/30 & 2-Year-Old)",
        "Sessions & Bookings",
        "Settling-In",
        "Transition to School",
        "Move to Primary School",
        "Leavers",
    ]),
    ("EYFS Learning & Development", [
        "EYFS Profile",
        "Development Tracking (Prime & Specific Areas)",
        "Observations",
        "Learning Journeys",
        "Next Steps Planning",
        "2-Year-Old Progress Check",
        "Characteristics of Effective Learning",
        "Activity & Curriculum Planning",
        "Cohort Tracking",
        "Photos & Evidence",
    ]),
    ("Daily Care & Routines", [
        "Daily Register",
        "Sign In / Sign Out",
        "Collections & Late Pickup",
        "Daily Diary",
        "Sleep Log",
        "Nappy / Toileting Log",
        "Meals & Menus",
        "Bottle Feeds",
        "Allergies & Dietary Requirements",
        "Accident & Incident Log",
        "Existing Injuries Log",
        "Medication Log",
    ]),
    ("Safeguarding & Welfare", [
        "Safeguarding / Child Protection",
        "Designated Safeguarding Lead",
        "Welfare Requirements",
        "SEND & Additional Needs",
        "EHC Plans",
        "Looked-After Children",
        "Risk Assessments",
        "Prevent Duty",
        "Concerns & Referrals",
        "Wellbeing",
    ]),
    ("Parents & Communication", [
        "Parent Contacts",
        "Emergency Contacts",
        "Permissions & Consents",
        "Email / Messaging",
        "Parent Messaging",
        "Daily Updates",
        "Newsletters",
        "Parent Meetings",
        "Feedback & Surveys",
        "Complaints",
    ]),
    ("Staff & Ratios", [
        "Staff Directory",
        "Staff : Child Ratios",
        "Live Ratio Alerts",
        "Staff Rota",
        "DBS Checks",
        "Qualifications & Training",
        "Paediatric First Aid",
        "Supervisions & Appraisals",
        "Staff Absence",
        "Recruitment",
        "Visitors",
    ]),
    ("Finance", [
        "Invoices & Fees",
        "Funded Hours Claims",
        "Payments",
        "Tax-Free Childcare / Vouchers",
        "Sibling Discounts",
        "Expense Claims",
        "Occupancy & Income",
    ]),
    ("Compliance & Reports", [
        "Ofsted Readiness",
        "EYFS Compliance",
        "Policies & Procedures",
        "GDPR",
        "Attendance Report",
        "Occupancy Report",
        "Funding Report",
        "Accident / Incident Report",
        "Audit Reports",
        "Data Export",
    ]),
    ("Cross-System", [
        "Student Journey",
    ]),
    ("System", [
        "Change Password",
        "Multi-Factor Authentication",
        "User Accounts",
        "User Management",
        "Settings",
        "Multi-Language",
        "About",
    ]),
]
