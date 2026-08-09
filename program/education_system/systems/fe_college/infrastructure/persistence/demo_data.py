"""Demo data for the FE College system.

Seeded only on a fresh database when ``EDU_DEV_SEED`` is set (see
``schema.bootstrap``), so a production launch stays empty. The content is
deterministic (a fixed RNG seed), while the dates are anchored to the week it
is seeded in — see :func:`_term_start` for why.

The shape matters more than the volume: a spread of curriculum areas, learners
across the attendance bands (including some genuinely at risk), a marking queue
with work in it, and fees in every state. A demo where everything is green
hides exactly the screens worth looking at.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from education_system.systems.fe_college.config import (
    ACADEMIC_YEAR,
    ATTENDANCE_MARKS,
)
from education_system.systems.fe_college.domain.courses.entry_requirements import (
    EntryRequirement,
)
from education_system.systems.fe_college.domain.courses.models import Course
from education_system.systems.fe_college.domain.courses.modules import Unit
from education_system.systems.fe_college.domain.facilities.rooms import Room
from education_system.systems.fe_college.domain.finance.fees import Fee
from education_system.systems.fe_college.domain.finance.funding import FundingAllocation
from education_system.systems.fe_college.domain.finance.payments import Payment
from education_system.systems.fe_college.domain.pastoral.behaviour import BehaviourRecord
from education_system.systems.fe_college.domain.pastoral.referrals import Referral
from education_system.systems.fe_college.domain.pastoral.tutorials import Tutorial
from education_system.systems.fe_college.domain.pastoral.wellbeing import WellbeingCheckIn
from education_system.systems.fe_college.domain.staff.models import Staff
from education_system.systems.fe_college.domain.students.attendance import AttendanceRecord
from education_system.systems.fe_college.domain.students.enrolment import Enrolment
from education_system.systems.fe_college.domain.students.models import Student
from education_system.systems.fe_college.domain.students.targets import Target
from education_system.systems.fe_college.domain.teaching.assignments import Assignment
from education_system.systems.fe_college.domain.teaching.classes import ClassGroup
from education_system.systems.fe_college.domain.teaching.submissions import Submission
from education_system.systems.fe_college.domain.teaching.timetable import Session
from education_system.systems.fe_college.infrastructure.persistence import session
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    assessment_repository as assessments,
    attendance_repository as attendance,
    course_repository as courses,
    finance_repository as finance,
    pastoral_repository as pastoral,
    staff_repository as staff_repo,
    student_repository as students,
    timetable_repository as timetable,
)

def _term_start(today: date | None = None) -> date:
    """The Monday ten weeks before ``today``.

    Anchoring the demo to a *fixed* date would work for a week and then rot:
    registers, tutorials and hand-in dates would all drift into the distant
    past, so the dashboards would show an empty attendance trend and every
    learner overdue a tutorial. Anchoring to the current week keeps the demo
    college looking live whenever it is seeded, while the fixed RNG seed keeps
    the *content* reproducible.
    """
    ref = today or date.today()
    monday = ref - timedelta(days=ref.weekday())
    return monday - timedelta(weeks=10)


TERM_START = _term_start()

# A 36-week academic year from the term start.
TERM_END = TERM_START + timedelta(weeks=36)


def _past(rng: random.Random, lo_days: int, hi_days: int) -> date:
    """A random date between ``lo_days`` and ``hi_days`` after the term start.

    Clamped so it never lands in the future: the term is only part-way through,
    and the domain rightly refuses a register mark, tutorial or behaviour
    record dated tomorrow.
    """
    elapsed = (date.today() - TERM_START).days
    hi = max(0, min(hi_days, elapsed))
    lo = min(lo_days, hi)
    return TERM_START + timedelta(days=rng.randint(lo, hi))

_FIRST_NAMES = [
    "Aisha", "Liam", "Chloe", "Mohammed", "Ellie", "Jayden", "Sophie", "Ryan",
    "Amelia", "Kofi", "Grace", "Oliver", "Zara", "Callum", "Maya", "Dylan",
    "Priya", "Ethan", "Lucy", "Samuel", "Nadia", "Harry", "Leah", "Tomasz",
    "Isabelle", "Marcus", "Freya", "Idris", "Hannah", "Jack",
]
_LAST_NAMES = [
    "Ahmed", "Bennett", "Clarke", "Dawson", "Evans", "Fletcher", "Gill",
    "Hughes", "Ibrahim", "Jenkins", "Kaur", "Lawson", "Mbeki", "Nowak",
    "O'Brien", "Patel", "Quinn", "Reid", "Sharma", "Thompson", "Unwin",
    "Vaughan", "Walsh", "Yilmaz", "Zhang",
]


def _slug(name: str) -> str:
    """Lower-case, letters only — safe to put either side of an @."""
    return "".join(c for c in name.lower() if c.isalpha())

_STAFF_SEED = [
    ("STF-0001", "Helen", "Marsh", "Head of Department", "Business & Computing", 12.0, True, False),
    ("STF-0002", "Dev", "Chaudhury", "Course Leader", "Business & Computing", 20.0, False, False),
    ("STF-0003", "Rachel", "Okonjo", "Lecturer", "Business & Computing", 24.0, False, False),
    ("STF-0004", "Tom", "Bradley", "Lecturer", "Construction & Engineering", 24.0, False, False),
    ("STF-0005", "Priti", "Nandra", "Course Leader", "Health, Care & Science", 20.0, True, False),
    ("STF-0006", "Gareth", "Lloyd", "Lecturer", "Creative & Service Industries", 18.0, False, False),
    ("STF-0007", "Sandra", "Bell", "Exams Officer", "", 0.0, False, True),
    ("STF-0008", "Michael", "Duffy", "Assessor", "Construction & Engineering", 15.0, False, False),
    ("STF-0009", "Anna", "Kowalska", "Lecturer", "Foundation & Essential Skills", 24.0, False, False),
    ("STF-0010", "Joseph", "Adeyemi", "Learning Support Assistant", "Foundation & Essential Skills", 30.0, False, False),
]

# Records with a fixed email, so the seeded shared-auth demo accounts resolve
# to a college record on first sign-in. The controller joins account to record
# by email; without a predictable one, the demo admin and lecturer would log in
# to empty screens. Keep these addresses in step with ``_DEFAULT_ACCOUNTS`` in
# ``platform/identity/auth/schema.py``.
ADMIN_EMAIL = "admin@riverside.ac.uk"
LECTURER_EMAIL = "dev.chaudhury@riverside.ac.uk"   # STF-0002
LEARNER_EMAIL = "student@riverside.ac.uk"

# (code, title, qualification, level, area, leader, GLH, capacity, fee)
_COURSE_SEED = [
    ("BUS3-EXT", "Business (Extended Diploma)", "BTEC Level 3", "3",
     "Business & Professional", "STF-0002", 1080, 60, 0.0),
    ("BUS2-DIP", "Business (Diploma)", "BTEC Level 2", "2",
     "Business & Professional", "STF-0002", 720, 30, 0.0),
    ("DIG3-TL", "Digital Production, Design and Development", "T-Level", "3",
     "Computing & Digital", "STF-0003", 1200, 24, 0.0),
    ("ENG3-EXT", "Engineering (Extended Diploma)", "BTEC Level 3", "3",
     "Engineering & Motor Vehicle", "STF-0004", 1080, 45, 0.0),
    ("CON1-DIP", "Construction Skills (Diploma)", "BTEC Level 1", "1",
     "Construction & Built Environment", "STF-0004", 600, 20, 0.0),
    ("HSC3-EXT", "Health and Social Care (Extended Diploma)", "BTEC Level 3", "3",
     "Health & Social Care", "STF-0005", 1080, 50, 0.0),
    ("HAI2-NVQ", "Hairdressing", "NVQ", "2",
     "Hair, Beauty & Wellbeing", "STF-0006", 610, 18, 0.0),
    ("ACC-HE", "Access to Higher Education (Health)", "Access to HE Diploma", "3",
     "Health & Social Care", "STF-0005", 720, 25, 3384.0),
    ("FS-ENG", "Functional Skills English Level 2", "Functional Skills", "2",
     "English & Maths", "STF-0009", 90, 80, 0.0),
    ("GCSE-MA", "GCSE Mathematics (Resit)", "GCSE Resit", "2",
     "English & Maths", "STF-0009", 120, 80, 0.0),
]

_ROOM_SEED = [
    ("A101", "Business Suite 1", "Classroom", 28, "Aspen", "1"),
    ("A102", "Business Suite 2", "Classroom", 28, "Aspen", "1"),
    ("A201", "IT Lab 1", "IT Suite", 24, "Aspen", "2"),
    ("A202", "IT Lab 2", "IT Suite", 24, "Aspen", "2"),
    ("B001", "Engineering Workshop", "Workshop", 20, "Beech", "G"),
    ("B002", "Construction Bay", "Workshop", 18, "Beech", "G"),
    ("C101", "Care Skills Suite", "Laboratory", 24, "Cedar", "1"),
    ("C102", "Training Salon", "Salon", 16, "Cedar", "1"),
    ("D101", "Lecture Theatre", "Lecture Theatre", 90, "Dogwood", "1"),
    ("D102", "Study Centre", "Classroom", 40, "Dogwood", "1"),
]

_UNIT_SEED = {
    "BUS3-EXT": [
        ("U1", "Exploring Business", "Mandatory", 10, "Internal — portfolio"),
        ("U2", "Developing a Marketing Campaign", "Mandatory", 10, "External — set task"),
        ("U3", "Personal and Business Finance", "Mandatory", 10, "External — examination"),
        ("U8", "Recruitment and Selection", "Optional", 10, "Internal — assignment"),
    ],
    "DIG3-TL": [
        ("DP1", "Digital Analysis and Problem Solving", "Mandatory", 20, "External — examination"),
        ("DP2", "Digital Environments", "Mandatory", 15, "Internal — assignment"),
        ("DP3", "Occupational Specialism Project", "Synoptic", 25, "External — set task"),
    ],
    "ENG3-EXT": [
        ("E1", "Engineering Principles", "Mandatory", 10, "External — examination"),
        ("E2", "Delivery of Engineering Processes Safely", "Mandatory", 10, "Internal — observation"),
        ("E4", "Applied Commercial and Quality Principles", "Optional", 10, "Internal — assignment"),
    ],
    "HSC3-EXT": [
        ("H1", "Human Lifespan Development", "Mandatory", 10, "External — examination"),
        ("H2", "Working in Health and Social Care", "Mandatory", 10, "External — examination"),
        ("H5", "Meeting Individual Care and Support Needs", "Mandatory", 10, "Internal — portfolio"),
    ],
    # Every course carries units, so any learner the demo picks has work to
    # look at. A learner signing in to empty assignment and results screens
    # would suggest the screens were broken rather than the data thin.
    "BUS2-DIP": [
        ("B21", "The Business Environment", "Mandatory", 10, "Internal — assignment"),
        ("B22", "Working in Business", "Mandatory", 10, "Internal — portfolio"),
    ],
    "CON1-DIP": [
        ("C11", "Health and Safety in Construction", "Mandatory", 10, "Internal — observation"),
        ("C12", "Introduction to Trade Skills", "Mandatory", 15, "Internal — observation"),
    ],
    "HAI2-NVQ": [
        ("N21", "Shampoo and Condition Hair", "Mandatory", 10, "Internal — observation"),
        ("N22", "Cut Hair Using Basic Techniques", "Mandatory", 15, "Internal — observation"),
        ("N23", "Colour and Lighten Hair", "Optional", 10, "Internal — observation"),
    ],
    "ACC-HE": [
        ("A1", "Human Biology", "Mandatory", 15, "Internal — assignment"),
        ("A2", "Study Skills for Higher Education", "Mandatory", 12, "Internal — portfolio"),
        ("A3", "Psychology for Health Professionals", "Optional", 12, "Internal — assignment"),
    ],
    "FS-ENG": [
        ("FE1", "Reading", "Mandatory", 5, "External — examination"),
        ("FE2", "Writing", "Mandatory", 5, "External — examination"),
        ("FE3", "Speaking, Listening and Communicating", "Mandatory", 5, "Internal — observation"),
    ],
    "GCSE-MA": [
        ("MA1", "Number and Algebra", "Mandatory", 10, "External — examination"),
        ("MA2", "Geometry and Statistics", "Mandatory", 10, "External — examination"),
    ],
}


def _birthday(rng: random.Random, on: date, age: int) -> date:
    """A random date of birth that makes someone ``age`` years old on ``on``."""
    born = on.year - age
    # Day 1-28 only, so the date is valid in every month including February.
    candidate = date(born, rng.randint(1, 12), rng.randint(1, 28))
    # Push a birthday that has not happened yet back a year, so the age on
    # ``on`` is exactly what was asked for rather than one less.
    if (candidate.month, candidate.day) > (on.month, on.day):
        candidate = candidate.replace(year=born - 1)
    return candidate


def seed(rng_seed: int = 20250908) -> dict[str, int]:
    """Populate the database with a demo college. Returns per-entity counts.

    Assumes an empty database — ``schema.bootstrap`` checks that before calling.
    """
    rng = random.Random(rng_seed)
    counts: dict[str, int] = {}

    # One connection and one transaction for the whole seed. Without this each
    # of the ~19,000 writes opens its own connection and the seed takes over a
    # minute; with it, a partial failure also rolls back cleanly instead of
    # leaving a half-populated college behind.
    with session():
        counts["staff"] = _seed_staff()
        counts["rooms"] = _seed_rooms()
        counts["courses"], counts["units"] = _seed_courses()
        counts["students"], counts["enrolments"] = _seed_students(rng)
        counts["groups"] = _seed_groups(rng)
        counts["sessions"] = _seed_timetable(rng)
        counts["attendance"] = _seed_attendance(rng)
        counts["assignments"], counts["submissions"] = _seed_assessment(rng)
        counts["fees"], counts["payments"] = _seed_finance(rng)
        counts["pastoral"] = _seed_pastoral(rng)
    return counts


def _seed_staff() -> int:
    for sid, first, last, role, dept, hours, dsl, exams in _STAFF_SEED:
        staff_repo.create(Staff(
            staff_id=sid,
            first_name=first,
            last_name=last,
            email=f"{_slug(first)}.{_slug(last)}@riverside.ac.uk",
            role=role,
            department=dept,
            employment_status="Full-time" if hours >= 18 else "Fractional",
            contracted_hours=hours,
            start_date=TERM_START - timedelta(weeks=52 * 6),
            is_safeguarding_lead=dsl,
            is_exams_officer=exams,
            dbs_checked=True,
        ))

    # The account the seeded `admin6` demo login resolves to.
    staff_repo.create(Staff(
        staff_id="STF-0011",
        first_name="College",
        last_name="Administrator",
        email=ADMIN_EMAIL,
        role="Administrator",
        employment_status="Full-time",
        contracted_hours=0.0,
        start_date=TERM_START - timedelta(weeks=52 * 6),
        dbs_checked=True,
    ))
    return len(_STAFF_SEED) + 1


def _seed_rooms() -> int:
    for rid, name, rtype, cap, building, floor in _ROOM_SEED:
        timetable.save_room(Room(
            room_id=rid, name=name, room_type=rtype, capacity=cap,
            building=building, floor=floor,
        ))
    return len(_ROOM_SEED)


def _seed_courses() -> tuple[int, int]:
    unit_count = 0
    for code, title, qual, level, area, leader, glh, cap, fee in _COURSE_SEED:
        courses.create(Course(
            course_id=code, title=title, qualification_type=qual, level=level,
            curriculum_area=area, academic_year=ACADEMIC_YEAR, course_leader=leader,
            awarding_body="Pearson", guided_learning_hours=glh, duration_weeks=36,
            capacity=cap, status="running", start_date=TERM_START,
            end_date=TERM_END, fee=fee,
            description=f"{qual} in {title}, delivered over one academic year.",
        ))
        courses.save_entry_requirement(EntryRequirement(
            course_id=code,
            min_age=16,
            min_prior_level="2" if level == "3" else "",
            min_gcse_english="4" if level == "3" else "",
            min_gcse_maths="4" if level == "3" else "",
            interview_required=level == "3",
        ))
        for i, (uid, utitle, utype, credits, method) in enumerate(_UNIT_SEED.get(code, [])):
            courses.add_unit(Unit(
                unit_id=uid, course_id=code, title=utitle, unit_type=utype,
                credits=credits, assessment_method=method, sequence=i + 1,
            ))
            unit_count += 1
    return len(_COURSE_SEED), unit_count


def _seed_students(rng: random.Random) -> tuple[int, int]:
    """Create learners and enrol them, weighted towards the larger courses."""
    enrolled_on = {code: 0 for code, *_ in _COURSE_SEED}
    capacities = {code: c[7] for code, *c in ((s[0], *s) for s in _COURSE_SEED)}
    # Fill each course to roughly 60-90% so the viability column shows a range.
    plan: list[tuple[str, int]] = []
    for code, *_rest in _COURSE_SEED:
        cap = capacities[code]
        target = max(4, int(cap * rng.uniform(0.35, 0.9)))
        plan.append((code, min(target, cap)))

    tutor_ids = [s[0] for s in _STAFF_SEED if s[3] in ("Lecturer", "Course Leader")]
    groups = ["BUS3A", "BUS3B", "DIG3A", "ENG3A", "HSC3A", "HAI2A", "ACCA", "FND1"]

    total_students = 0
    total_enrolments = 0
    counter = 0

    # The learner the seeded `learner1` demo login resolves to. Created first
    # and enrolled on a unit-bearing course plus a resit, so that by the time
    # attendance and assessment are seeded below they pick this learner up like
    # any other — the demo account lands on a populated dashboard rather than
    # an empty one.
    demo = students.create(Student(
        student_id="",
        first_name="Demo",
        last_name="Learner",
        date_of_birth=_birthday(rng, TERM_START, 17),
        uln="9990000001",
        email=LEARNER_EMAIL,
        phone="07700900000",
        learner_type="16-18 Study Programme",
        mode_of_study="Full-time",
        status="enrolled",
        tutor_group="BUS3A",
        personal_tutor="STF-0002",
        start_date=TERM_START,
        prior_attainment="Level 2 pass",
        emergency_contact_name="A Guardian",
        emergency_contact_phone="07700900001",
    ))
    total_students += 1
    for course_id, is_main in (("BUS3-EXT", True), ("GCSE-MA", False)):
        students.add_enrolment(Enrolment(
            enrolment_id=None,
            student_id=demo.student_id,
            course_id=course_id,
            academic_year=ACADEMIC_YEAR,
            status="active",
            is_main_aim=is_main,
            start_date=TERM_START,
            expected_end_date=TERM_END,
            funding_source="ESFA 16-18",
        ))
        total_enrolments += 1
        enrolled_on[course_id] += 1

    for code, target in plan:
        for _ in range(target):
            counter += 1
            first = rng.choice(_FIRST_NAMES)
            last = rng.choice(_LAST_NAMES)
            # Age spread: adult learners on Access, 16-18 elsewhere.
            if code == "ACC-HE":
                # Adult learners: 22-40 on entry.
                dob = _birthday(rng, TERM_START, rng.randint(22, 40))
                learner_type = "19+ Adult Learner"
            else:
                # Study-programme learners: 16-18 on entry.
                dob = _birthday(rng, TERM_START, rng.randint(16, 18))
                learner_type = "16-18 Study Programme"

            student = students.create(Student(
                student_id="",              # allocated by the repository
                first_name=first,
                last_name=last,
                date_of_birth=dob,
                uln=f"{9000000000 + counter}",
                email=f"{_slug(first)}.{_slug(last)}{counter}@student.riverside.ac.uk",
                phone=f"07{rng.randint(100000000, 999999999)}",
                postcode=f"RV{rng.randint(1, 9)} {rng.randint(1, 9)}{rng.choice('ABDEFG')}{rng.choice('ABDEFG')}",
                learner_type=learner_type,
                mode_of_study="Part-time" if code in ("FS-ENG", "GCSE-MA") else "Full-time",
                status="enrolled",
                tutor_group=rng.choice(groups),
                personal_tutor=rng.choice(tutor_ids),
                start_date=TERM_START,
                prior_attainment=rng.choice([
                    "Level 2 with merit or above", "Level 2 pass",
                    "Level 1 pass", "No formal qualifications",
                ]),
                has_ehcp=rng.random() < 0.08,
            ))
            total_students += 1

            students.add_enrolment(Enrolment(
                enrolment_id=None,
                student_id=student.student_id,
                course_id=code,
                academic_year=ACADEMIC_YEAR,
                status="active",
                is_main_aim=True,
                start_date=TERM_START,
                expected_end_date=TERM_END,
                funding_source=(
                    "ESFA Adult Skills Fund" if learner_type.startswith("19+")
                    else "ESFA 16-18"
                ),
            ))
            enrolled_on[code] += 1
            total_enrolments += 1

            # 16-18 learners without a grade 4 carry a compulsory resit
            # alongside their main aim — the study-programme rule.
            if learner_type.startswith("16-18") and rng.random() < 0.35:
                resit = rng.choice(["FS-ENG", "GCSE-MA"])
                if resit != code:
                    students.add_enrolment(Enrolment(
                        enrolment_id=None,
                        student_id=student.student_id,
                        course_id=resit,
                        academic_year=ACADEMIC_YEAR,
                        status="active",
                        is_main_aim=False,
                        start_date=TERM_START,
                        funding_source="ESFA 16-18",
                    ))
                    total_enrolments += 1

    # A handful of withdrawals so the retention figures aren't a flat 100%.
    # The demo learner is excluded — the demo account signing in to a
    # withdrawn record would look like a bug rather than a data point.
    active = [
        e for e in students.list_enrolments(status="active")
        if e.student_id != demo.student_id
    ]
    for enrolment in rng.sample(active, k=min(6, len(active))):
        students.withdraw_enrolment(
            enrolment.enrolment_id,
            rng.choice(["Left for employment", "Personal / health reasons", "Non-attendance"]),
            on=_past(rng, 20, 60),
        )
    # A few applicants who have not been enrolled yet, so the admissions and
    # enrolment screens have something to work with rather than opening empty.
    for _ in range(8):
        counter += 1
        first, last = rng.choice(_FIRST_NAMES), rng.choice(_LAST_NAMES)
        students.create(Student(
            student_id="",
            first_name=first,
            last_name=last,
            date_of_birth=_birthday(rng, TERM_START, rng.randint(16, 19)),
            email=f"{_slug(first)}.{_slug(last)}{counter}@applicant.riverside.ac.uk",
            phone=f"07{rng.randint(100000000, 999999999)}",
            learner_type="16-18 Study Programme",
            status="applicant",
            prior_attainment=rng.choice([
                "Level 2 with merit or above", "Level 2 pass",
                "Level 1 pass", "No formal qualifications",
            ]),
        ))
        total_students += 1

    return total_students, total_enrolments


def _seed_groups(rng: random.Random) -> int:
    made = 0
    for code, *_rest in _COURSE_SEED:
        cohort = students.list_students(course_id=code)
        if len(cohort) < 6:
            continue
        # Split larger cohorts into two teaching groups.
        chunks = 2 if len(cohort) > 20 else 1
        size = -(-len(cohort) // chunks)
        for i in range(chunks):
            group_id = f"{code}-{chr(65 + i)}"
            course = courses.get(code)
            courses.create_group(ClassGroup(
                group_id=group_id,
                course_id=code,
                name=f"{code} Group {chr(65 + i)}",
                teacher_id=course.course_leader if course else "",
                academic_year=ACADEMIC_YEAR,
                capacity=size + 4,
            ))
            members = [s.student_id for s in cohort[i * size:(i + 1) * size]]
            courses.set_group_members(group_id, members)
            made += 1
    return made


def _seed_timetable(rng: random.Random) -> int:
    """Place each course's sessions, skipping any slot that would clash."""
    from education_system.systems.fe_college.domain.teaching.timetable import (
        PERIOD_CODES,
        find_clashes,
    )
    from education_system.systems.fe_college.config import WEEKDAYS

    rooms_by_type = {}
    for room in timetable.list_rooms(bookable_only=True):
        rooms_by_type.setdefault(room.room_type, []).append(room.room_id)

    preferred = {
        "Computing & Digital": "IT Suite",
        "Engineering & Motor Vehicle": "Workshop",
        "Construction & Built Environment": "Workshop",
        "Health & Social Care": "Laboratory",
        "Hair, Beauty & Wellbeing": "Salon",
    }

    placed = 0
    existing: list[Session] = []
    for code, *_rest in _COURSE_SEED:
        course = courses.get(code)
        if course is None:
            continue
        groups = courses.list_groups(course_id=code)
        room_pool = rooms_by_type.get(
            preferred.get(course.curriculum_area, "Classroom"), []
        ) or rooms_by_type.get("Classroom", [])
        # Sessions per week scale with the course's guided learning hours.
        per_week = max(1, min(8, course.guided_learning_hours // 150))
        for group in (groups or [None]):
            for _ in range(per_week):
                for _attempt in range(12):
                    session = Session(
                        session_id=None,
                        course_id=code,
                        group_id=group.group_id if group else "",
                        teacher_id=(group.teacher_id if group else course.course_leader) or "",
                        room_id=rng.choice(room_pool) if room_pool else "",
                        day=rng.choice(WEEKDAYS[:5]),
                        period=rng.choice(PERIOD_CODES[:7]),
                        academic_year=ACADEMIC_YEAR,
                    )
                    if not find_clashes(session, existing):
                        timetable.create_session(session)
                        existing.append(session)
                        placed += 1
                        break
    return placed


def _seed_attendance(rng: random.Random) -> int:
    """Mark registers for the first 10 teaching weeks.

    Each learner is given a personal attendance profile so the cohort spreads
    across the bands rather than clustering on the average — the at-risk report
    needs learners who are genuinely at risk.
    """
    marks_written = 0
    sessions_by_course: dict[str, list[Session]] = {}
    for session in timetable.list_sessions():
        sessions_by_course.setdefault(session.course_id, []).append(session)

    for code, sessions in sessions_by_course.items():
        cohort = students.list_students(course_id=code)
        if not cohort:
            continue
        # Personal reliability: most learners are good, a tail are not.
        profile = {
            s.student_id: min(0.99, max(0.45, rng.gauss(0.90, 0.13)))
            for s in cohort
        }
        records: list[AttendanceRecord] = []
        # 11 weeks covers the ten complete weeks plus the days of the current
        # one that have already happened — the future-date guard below drops
        # the rest, so the dashboard's latest week isn't blank.
        for week in range(11):
            for session in sessions:
                day_offset = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"].index(
                    session.day
                )
                session_date = TERM_START + timedelta(weeks=week, days=day_offset)
                if session_date > date.today():
                    continue
                for learner in cohort:
                    roll = rng.random()
                    reliability = profile[learner.student_id]
                    if roll < reliability * 0.93:
                        mark, late = "present", 0
                    elif roll < reliability:
                        mark, late = "late", rng.choice([5, 10, 15, 20])
                    elif roll < reliability + (1 - reliability) * 0.45:
                        mark, late = "authorised", 0
                    elif roll < reliability + (1 - reliability) * 0.9:
                        mark, late = "unauthorised", 0
                    else:
                        mark, late = "excused", 0
                    records.append(AttendanceRecord(
                        record_id=None,
                        student_id=learner.student_id,
                        course_id=code,
                        session_date=session_date,
                        period=session.period,
                        mark=mark,
                        minutes_late=late,
                        recorded_by=session.teacher_id,
                    ))
        # Write in batches so a big cohort doesn't build one enormous statement.
        for i in range(0, len(records), 500):
            marks_written += attendance.save_register(records[i:i + 500])
    return marks_written


def _seed_assessment(rng: random.Random) -> tuple[int, int]:
    """Issue assignments and hand in a realistic mix of work."""
    from education_system.systems.fe_college.domain.students.grades import grades_for

    assignment_count = submission_count = 0
    for code, *_rest in _COURSE_SEED:
        units = courses.list_units(code)
        if not units:
            continue
        course = courses.get(code)
        cohort = students.list_students(course_id=code)
        if not cohort:
            continue
        valid_grades = [g for g in grades_for(course.qualification_type)
                        if g not in ("Referred", "Unclassified", "U", "Fail")]

        for i, unit in enumerate(units):
            due = TERM_START + timedelta(weeks=4 + i * 4)
            assignment = assessments.create_assignment(Assignment(
                assignment_id=None,
                course_id=code,
                title=f"{unit.title} — Assignment {i + 1}",
                unit_id=unit.unit_id,
                status="issued",
                set_by=course.course_leader,
                issue_date=due - timedelta(weeks=3),
                due_date=due,
                criteria=", ".join(rng.sample(["P1", "P2", "P3", "M1", "M2", "D1"], k=3)),
                max_marks=100,
                brief=f"Produce evidence covering the assessment criteria for {unit.title}.",
            ))
            assignment_count += 1

            if due > date.today():
                continue  # Not due yet — nothing handed in.

            for learner in cohort:
                roll = rng.random()
                if roll < 0.06:
                    status, grade, marked_by, submitted = "not_submitted", "", "", None
                elif roll < 0.14:
                    # Handed in, still sitting in the marking queue.
                    status, grade, marked_by = "submitted", "", ""
                    submitted = due - timedelta(days=rng.randint(0, 3))
                elif roll < 0.20:
                    status, grade, marked_by = "referred", "Referred", course.course_leader
                    submitted = due - timedelta(days=rng.randint(0, 2))
                else:
                    status, grade = "marked", rng.choice(valid_grades)
                    marked_by = course.course_leader
                    submitted = due - timedelta(days=rng.randint(0, 5))

                assessments.save_submission(Submission(
                    submission_id=None,
                    assignment_id=assignment.assignment_id,
                    student_id=learner.student_id,
                    status=status,
                    submitted_at=submitted,
                    marked_at=(submitted + timedelta(days=7)) if grade else None,
                    marked_by=marked_by,
                    grade=grade,
                    marks=rng.randint(40, 95) if grade and grade != "Referred" else None,
                    feedback="Good evidence against the criteria." if grade else "",
                ), max_marks=100)
                submission_count += 1
    return assignment_count, submission_count


def _seed_finance(rng: random.Random) -> tuple[int, int]:
    """Raise fees on the chargeable courses and settle some of them."""
    fee_count = payment_count = 0
    for code, *rest in _COURSE_SEED:
        course = courses.get(code)
        if course is None or course.fee <= 0:
            continue
        for learner in students.list_students(course_id=code):
            fee = finance.raise_fee(Fee(
                fee_id=None,
                student_id=learner.student_id,
                fee_type="Tuition",
                amount=course.fee,
                course_id=code,
                academic_year=ACADEMIC_YEAR,
                description=f"{course.title} tuition fee",
                due_date=TERM_START + timedelta(days=30),
                raised_on=TERM_START,
            ))
            fee_count += 1

            roll = rng.random()
            if roll < 0.45:
                amount = course.fee              # settled in full
            elif roll < 0.75:
                amount = round(course.fee / 3, 2)  # first instalment only
            else:
                continue                          # nothing paid yet
            finance.record_payment(Payment(
                payment_id=None,
                fee_id=fee.fee_id,
                student_id=learner.student_id,
                amount=amount,
                method=rng.choice(["Card", "Bank Transfer", "Direct Debit", "Student Loan"]),
                paid_on=_past(rng, 1, 40),
                reference=f"RCPT-{rng.randint(10000, 99999)}",
                received_by="STF-0007",
            ))
            payment_count += 1

    # Exam fees for the resit cohorts — small charges, many learners.
    for code in ("GCSE-MA", "FS-ENG"):
        for learner in students.list_students(course_id=code):
            if rng.random() > 0.4:
                continue
            finance.raise_fee(Fee(
                fee_id=None,
                student_id=learner.student_id,
                fee_type="Exam",
                amount=48.50,
                course_id=code,
                academic_year=ACADEMIC_YEAR,
                description="Awarding body entry fee",
                due_date=TERM_START + timedelta(weeks=25),
                raised_on=TERM_START + timedelta(days=60),
            ))
            fee_count += 1

    for source, allocated in (
        ("ESFA 16-18", 2_450_000.0),
        ("ESFA Adult Skills Fund", 780_000.0),
        ("Advanced Learner Loan", 145_000.0),
    ):
        learners = len(students.list_students(status="enrolled"))
        finance.save_allocation(FundingAllocation(
            allocation_id=None,
            funding_source=source,
            academic_year=ACADEMIC_YEAR,
            allocated=allocated,
            earned=round(allocated * rng.uniform(0.93, 1.04), 2),
            learner_count=learners,
        ))
    return fee_count, payment_count


def _seed_pastoral(rng: random.Random) -> int:
    """Tutorials, behaviour, referrals and wellbeing for a sample of learners."""
    written = 0
    cohort = students.list_students(status="enrolled")
    tutors = [s[0] for s in _STAFF_SEED if s[3] in ("Lecturer", "Course Leader")]

    for learner in cohort:
        tutor = learner.personal_tutor or rng.choice(tutors)

        # Most learners have had a tutorial; some are deliberately overdue.
        if rng.random() < 0.75:
            held = _past(rng, 5, 100)
            if held <= date.today():
                pastoral.add_tutorial(Tutorial(
                    tutorial_id=None,
                    student_id=learner.student_id,
                    tutor_id=tutor,
                    status="held",
                    scheduled_for=held,
                    held_on=held,
                    attendance_discussed=True,
                    progress_discussed=True,
                    targets_set="Complete outstanding unit evidence.",
                    notes="Reviewed attendance and progress against target grade.",
                ))
                written += 1

        if rng.random() < 0.3:
            students.add_target(Target(
                target_id=None,
                student_id=learner.student_id,
                description=rng.choice([
                    "Submit Unit 2 draft before the next tutorial",
                    "Attend all timetabled sessions for four weeks",
                    "Complete the maths diagnostic and book a workshop",
                    "Improve referencing to meet Merit criteria",
                ]),
                status=rng.choice(["set", "in_progress", "achieved"]),
                set_by=tutor,
                set_date=_past(rng, 10, 60),
                # A due date may legitimately still be ahead of us.
                due_date=TERM_START + timedelta(days=rng.randint(70, 140)),
                completed_date=_past(rng, 20, 70),
            ))
            written += 1

        if rng.random() < 0.25:
            btype = rng.choice(["Praise", "Praise", "Concern", "Warning"])
            pastoral.add_behaviour(BehaviourRecord(
                record_id=None,
                student_id=learner.student_id,
                behaviour_type=btype,
                summary=(
                    "Excellent contribution in class" if btype == "Praise"
                    else "Repeated late arrival to first period"
                ),
                logged_by=tutor,
                logged_on=_past(rng, 5, 110),
                action_taken="Discussed at tutorial." if btype != "Praise" else "",
            ))
            written += 1

        if rng.random() < 0.12:
            rtype = rng.choice([
                "Wellbeing / Mental Health", "Learning Support",
                "Financial Support", "Attendance", "Careers",
            ])
            referred = _past(rng, 10, 120)
            closed = rng.random() < 0.5
            pastoral.add_referral(Referral(
                referral_id=None,
                student_id=learner.student_id,
                referral_type=rtype,
                reason=f"Tutor referral — {rtype.lower()}.",
                status="closed" if closed else rng.choice(["open", "in_progress"]),
                urgency=rng.choice(["routine", "routine", "priority"]),
                referred_by=tutor,
                referred_on=referred,
                assigned_to=rng.choice(tutors),
                actioned_on=referred + timedelta(days=2) if closed else None,
                closed_on=(
                    min(referred + timedelta(days=rng.randint(5, 30)), date.today())
                    if closed else None
                ),
                outcome="Support put in place and reviewed." if closed else "",
            ))
            written += 1

        if rng.random() < 0.4:
            for week in range(rng.randint(1, 4)):
                checked = TERM_START + timedelta(weeks=week * 2)
                if checked > date.today():
                    break
                pastoral.add_checkin(WellbeingCheckIn(
                    checkin_id=None,
                    student_id=learner.student_id,
                    mood=rng.choice([2, 3, 3, 4, 4, 5]),
                    checked_on=checked,
                    source="Self",
                ))
                written += 1
    return written


__all__ = ["TERM_START", "seed"]
