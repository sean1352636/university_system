"""Who may open what in the Secondary School System.

One rule table, read by both the GUI sidebar and the CLI menu, so the two can
never disagree. The role comes from the signed-in account's ``secondary``
entry in the shared ``auth.db`` (``user_systems``), never from anything the
user types.

Roles:

* ``admin``   - every area.
* ``teacher`` / ``staff`` - every area except the restricted ones below.
* ``student`` / ``parent`` - no staff window: they get the pupil or parent
  portal, which shows only the pupils their login is linked to
  (:mod:`modules.portals.domain.portal_accounts`).

Staff land on the staff portal ("My Day", :mod:`modules.portals.domain.my_day`).

Restricted areas are named by menu label in :data:`RESTRICTED`. A label not
listed there is open to all staff.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.manifest import MANIFEST

SYSTEM_KEY = MANIFEST.key

#: Older tokens and seeds still carry the pre-rename key.
_LEGACY_KEYS = {"school"}

ADMIN = "admin"
STAFF_ROLES = frozenset({"admin", "superadmin", "teacher", "staff"})
LEARNER_ROLES = frozenset({"student"})
PARENT_ROLES = frozenset({"parent"})

#: label -> roles allowed to open it. Anything not listed: all staff roles.
#: Roles that may create, change or delete pupil records. Other staff can
#: look pupils up but not change them.
PUPIL_EDITORS = frozenset({"admin", "superadmin"})

#: Roles that may e-mail a whole form, year group or the school. Other staff
#: can e-mail the contacts of pupils they choose.
BULK_EMAIL_SENDERS = frozenset({"admin", "superadmin"})

#: Roles that can see every message in the school outbox (others see the
#: messages they sent).
EMAIL_ADMINS = frozenset({"admin", "superadmin"})

#: Roles that may change the school year, terms and holidays, and edit or
#: delete any calendar event. Other staff read the calendar and manage the
#: events they created.
CALENDAR_EDITORS = frozenset({"admin", "superadmin"})

#: Roles that may change year-group settings (head of year, capacity) and
#: move pupils between year groups. All staff can view year groups.
YEAR_GROUP_EDITORS = frozenset({"admin", "superadmin"})

#: Roles that may set up, change and archive form groups and put pupils in
#: them. All staff can view forms and their pupils.
FORM_GROUP_EDITORS = frozenset({"admin", "superadmin"})

#: Roles that may change the subject catalogue and the curriculum plan
#: (lessons per week). All staff can view them.
SUBJECT_EDITORS = frozenset({"admin", "superadmin"})

#: Roles that may set up teaching groups and put pupils in them. All staff can
#: view groups; a teacher can filter to the groups they teach.
TEACHING_GROUP_EDITORS = frozenset({"admin", "superadmin"})

#: Roles that may build the timetable (lessons, periods, the week cycle). All
#: staff can view it; a teacher can view their own.
TIMETABLE_EDITORS = frozenset({"admin", "superadmin"})

#: The attendance office: may enter reason codes, mark or change past
#: registers, record absence over several days and remove marks. Other staff
#: take today's registers (present / late / absent) and lesson registers.
ATTENDANCE_EDITORS = frozenset({"admin", "superadmin"})

#: Roles that may manage schemes of work (units) and change or remove anyone's
#: lesson plan. All staff view every plan and write their own.
LESSON_PLAN_EDITORS = frozenset({"admin", "superadmin"})

#: The cover manager: assigns cover, records anyone's absence, manages supply
#: staff. Other staff view cover, report their own absence, set work for their
#: own lessons and confirm cover they've been given.
COVER_EDITORS = frozenset({"admin", "superadmin"})

#: Roles that may change or remove anyone's homework and set the daily homework
#: limit. All staff view all homework, set their own and mark their own.
HOMEWORK_EDITORS = frozenset({"admin", "superadmin"})

#: The options lead: runs options rounds (subjects, rules, blocks, allocation,
#: Year 10 groups) and can enter or change choices at any time. Other staff
#: view rounds and enter pupils' choices while a round is open (tutors).
OPTIONS_EDITORS = frozenset({"admin", "superadmin"})

#: The enrichment lead: sets up and closes any club and manages any club's
#: members and registers. A club's own leader manages that club's members and
#: registers; other staff view clubs.
ENRICHMENT_EDITORS = frozenset({"admin", "superadmin"})

#: The librarian: changes the catalogue and copies, writes off lost books,
#: deletes loans and sets the loan rules. All staff search the catalogue and
#: issue, return, renew and reserve books for pupils.
LIBRARY_EDITORS = frozenset({"admin", "superadmin"})

#: Heads of department / data managers: change or delete any assessment and
#: its marks, unlock locked assessments and set subjects' grade boundaries.
#: Other staff view all marks, and set and mark assessments for the groups they
#: teach.
GRADEBOOK_EDITORS = frozenset({"admin", "superadmin"})

#: The data manager: sets up assessment points (data drops), opens, closes and
#: publishes them, and enters or corrects any class's grades. Teachers enter
#: grades for the groups they teach while a point is open; all staff view.
ASSESSMENT_POINT_EDITORS = frozenset({"admin", "superadmin"})

#: The data manager: sets, lowers and deletes any pupil's targets and imports
#: them in bulk. Teachers set and raise targets for pupils in the groups they
#: teach (never lower them); all staff view targets and progress against them.
TARGET_GRADE_EDITORS = frozenset({"admin", "superadmin"})

#: The SENCO: records and changes pupils' SEN details (area of need, EHC plan,
#: provision, strategies, exam access). All staff can read them.
SEN_EDITORS = frozenset({"admin", "superadmin"})

#: The exams officer: enters, imports and corrects GCSE results. All staff
#: can read them.
EXAM_RESULT_EDITORS = frozenset({"admin", "superadmin"})

#: Who may send Year 11 pupils on to the Sixth Form system (with consent).
SIXTH_FORM_SENDERS = frozenset({"admin", "superadmin"})
MOCK_EXAM_EDITORS = frozenset({"admin", "superadmin"})  # exams officer
#: Make and change real exam entries, specifications, candidate numbers and
#: board files (the exams officer). Teachers may set tiers for the pupils they
#: teach while an entry is provisional; all staff can read entries.
EXAM_ENTRY_EDITORS = frozenset({"admin", "superadmin"})
#: Enter KS2 prior attainment and P8 estimates, calculate / edit Attainment 8
#: and Progress 8 (the data manager).
HEADLINE_MEASURE_EDITORS = frozenset({"admin", "superadmin"})
#: The school's intervention lead: any intervention, reopen closed ones, delete.
INTERVENTION_EDITORS = frozenset({"admin", "superadmin"})
#: Reports to parents: set up cycles, write any comment, check, issue, withdraw.
REPORT_EDITORS = frozenset({"admin", "superadmin"})
#: Form tutors: assign tutors to forms, see and change every meeting record.
FORM_TUTOR_EDITORS = frozenset({"admin", "superadmin"})
#: Behaviour lead: behaviour types, houses, edit any entry, delete entries.
BEHAVIOUR_EDITORS = frozenset({"admin", "superadmin"})
#: Detentions lead: sessions, SLT / Saturday detentions, change or delete any.
DETENTION_EDITORS = frozenset({"admin", "superadmin"})
#: The headteacher's office: suspends and excludes, records governors' and
#: review decisions, tells families and the local authority, takes a permanently
#: excluded pupil off roll. All staff can see cases; heads of year add events.
EXCLUSION_EDITORS = frozenset({"admin", "superadmin"})

#: Designated safeguarding lead and deputies: read and manage every
#: safeguarding record. All staff can report a concern; they see only their own.
SAFEGUARDING_LEADS = frozenset({"admin", "superadmin"})
#: SENCO: the SEND register, plans, provision maps, reviews.
SEND_EDITORS = frozenset({"admin", "superadmin"})
#: School office / first aid lead: medical conditions, care plans, medicines.
MEDICAL_EDITORS = frozenset({"admin", "superadmin"})
#: Pupil premium lead: eligibility, spending, strategy.
PUPIL_PREMIUM_EDITORS = frozenset({"admin", "superadmin"})
#: Attendance lead: attendance concern cases, letters, meetings, LA referrals.
ATTENDANCE_CONCERN_EDITORS = frozenset({"admin", "superadmin"})
#: Wellbeing / pastoral lead: any wellbeing record and referral.
WELLBEING_EDITORS = frozenset({"admin", "superadmin"})
#: Complaints lead (headteacher's office / clerk to governors).
COMPLAINT_EDITORS = frozenset({"admin", "superadmin"})
#: HR / office: staff records and departments.
STAFF_EDITORS = frozenset({"admin", "superadmin"})
#: Who approves and records staff absence (the cover manager reads it).
STAFF_ABSENCE_EDITORS = frozenset({"admin", "superadmin"})
#: Single central record (pre-employment checks).
SCR_EDITORS = frozenset({"admin", "superadmin"})
#: Appraisal and CPD leads: any appraisal, CPD approval and budgets.
APPRAISAL_EDITORS = frozenset({"admin", "superadmin"})
#: Parents' evenings, announcements and letters to families.
PARENTS_EVENING_EDITORS = frozenset({"admin", "superadmin"})
ANNOUNCEMENT_EDITORS = frozenset({"admin", "superadmin"})
LETTER_EDITORS = frozenset({"admin", "superadmin"})
#: Finance office: trips, dinner money, expense approval, budgets.
TRIP_EDITORS = frozenset({"admin", "superadmin"})
DINNER_MONEY_EDITORS = frozenset({"admin", "superadmin"})
EXPENSE_APPROVERS = frozenset({"admin", "superadmin"})
BUDGET_EDITORS = frozenset({"admin", "superadmin"})
#: Data manager: census returns and whole-school data exports.
DATA_MANAGERS = frozenset({"admin", "superadmin"})
#: School settings.
SETTINGS_EDITORS = frozenset({"admin", "superadmin"})

RESTRICTED: dict[str, frozenset[str]] = {
    "Add Pupil": PUPIL_EDITORS,
    # Adds, changes and deletes pupil records in bulk.
    "Bulk Import": PUPIL_EDITORS,
    # Applications hold looked-after and SEN details, and decide places.
    "Admissions": frozenset({"admin", "superadmin"}),
    # Referrals carry exclusion, SEN and medical details and move pupils off roll.
    "Referrals to Alternative Provision": frozenset({"admin", "superadmin"}),
    # Requests to the SEND service carry SEN, medical and support details.
    "SEND Service Requests": SEND_EDITORS,
    # Notifications to the local authority: exclusions, children missing
    # education, attendance, SEN.
    "Local Authority": frozenset({"admin", "superadmin"}),
    # Leaving details include exclusions and children missing education.
    "Enrolment & Leavers": frozenset({"admin", "superadmin"}),
    # Former pupils' personal contact details and consent.
    "Alumni": frozenset({"admin", "superadmin"}),
    # Child protection records: admin only until DSL roles are built.
    # Every member of staff can still *report* a concern.
    "Safeguarding": frozenset({"admin", "superadmin"}),
    # Confidential staff records.
    "Single Central Record": frozenset({"admin", "superadmin"}),
    "Staff Absence": frozenset({"admin", "superadmin"}),
    # Money.
    "Trips & Payments": frozenset({"admin", "superadmin"}),
    "Dinner Money": frozenset({"admin", "superadmin"}),
    "Expense Claims": frozenset({"admin", "superadmin"}),
    "Budgets": frozenset({"admin", "superadmin"}),
    # Statutory returns and system administration.
    "School Census": frozenset({"admin", "superadmin"}),
    "User Accounts": frozenset({"admin", "superadmin"}),
    "Settings": frozenset({"admin", "superadmin"}),
    "Audit Log": frozenset({"admin", "superadmin"}),
}


@dataclass(frozen=True)
class Principal:
    """The signed-in person, as this system sees them."""

    username: str
    role: str | None
    user_id: Any = None

    @property
    def is_staff(self) -> bool:
        return self.role in STAFF_ROLES

    @property
    def is_admin(self) -> bool:
        return self.role in {"admin", "superadmin"}

    @property
    def is_student(self) -> bool:
        return self.role in LEARNER_ROLES

    @property
    def is_parent(self) -> bool:
        return self.role in PARENT_ROLES

    @property
    def can_edit_pupils(self) -> bool:
        return self.role in PUPIL_EDITORS

    @property
    def can_email_bulk(self) -> bool:
        return self.role in BULK_EMAIL_SENDERS

    def can_open(self, label: str) -> bool:
        """True if this person may open the menu entry *label*."""
        if not self.is_staff:
            return False
        allowed = RESTRICTED.get(label)
        return allowed is None or self.role in allowed

    def denied_message(self, label: str) -> str:
        return (f"Your account doesn't have access to {label}.\n\n"
                "If you need it for your job, ask a system administrator "
                "to update your permissions.")


ANONYMOUS = Principal(username="", role=None)


def _role_from_systems(systems: Any) -> str | None:
    for s in systems or []:
        if not isinstance(s, dict):
            continue
        if s.get("system_key") == SYSTEM_KEY or s.get("system_key") in _LEGACY_KEYS:
            return s.get("role")
    return None


def from_auth(auth: Any, role: str | None = None) -> Principal:
    """Principal for the shared ``UserAuth`` session the launcher hands over.

    The ``secondary`` entry in the account's systems list wins over the
    launcher-supplied *role*, which wins over the account's general role.
    Missing identity fails closed (no role, so nothing opens).
    """
    cu = getattr(auth, "current_user", None) or {}
    if not isinstance(cu, dict):
        return ANONYMOUS
    resolved = _role_from_systems(cu.get("systems")) or role or cu.get("role")
    resolved = str(resolved).lower() if resolved else None
    return Principal(
        username=cu.get("username", "") or "",
        role=resolved,
        user_id=cu.get("id") or cu.get("user_id"),
    )


def visible_categories(principal: Principal, categories):
    """Filter a ``[(category, [(label, ...), ...])]`` catalogue to what
    *principal* may open, dropping categories left empty."""
    out = []
    for name, items in categories:
        allowed = [item for item in items if principal.can_open(item[0])]
        if allowed:
            out.append((name, allowed))
    return out
