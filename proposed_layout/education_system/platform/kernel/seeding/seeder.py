"""Generate realistic demo data for all education systems.

Improvement #19: Database Seeding CLI
"""

import random
import string
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

FIRST_NAMES_M = [
    "Oliver", "George", "Harry", "Jack", "Noah", "Charlie", "Jacob",
    "Alfie", "Freddie", "Oscar", "Leo", "Archie", "Arthur", "Thomas",
    "James", "Henry", "William", "Ethan", "Lucas", "Muhammad",
]
FIRST_NAMES_F = [
    "Olivia", "Amelia", "Isla", "Ava", "Emily", "Sophia", "Grace",
    "Mia", "Poppy", "Ella", "Lily", "Jessica", "Charlotte", "Daisy",
    "Isabella", "Sophie", "Freya", "Ruby", "Alice", "Evie",
]
LAST_NAMES = [
    "Smith", "Jones", "Williams", "Taylor", "Brown", "Davies", "Evans",
    "Wilson", "Thomas", "Roberts", "Johnson", "Lewis", "Walker", "Robinson",
    "Wood", "Thompson", "White", "Watson", "Jackson", "Wright",
    "Green", "Harris", "Cooper", "King", "Lee", "Martin", "Clarke",
    "James", "Morgan", "Hughes", "Edwards", "Hill", "Moore", "Clark",
]

SUBJECTS_COLLEGE = [
    "Mathematics", "Further Mathematics", "English Literature", "Biology",
    "Chemistry", "Physics", "Computer Science", "Psychology", "Sociology",
    "History", "Geography", "Economics", "Business Studies", "Art & Design",
    "Music", "Drama & Theatre", "Media Studies", "French", "Spanish",
    "Law", "Health & Social Care", "Physical Education",
]
SUBJECTS_SECONDARY = [
    "Mathematics", "English", "Science", "History", "Geography",
    "French", "Spanish", "Art", "Music", "Drama", "PE",
    "Computer Science", "Design & Technology", "Food Technology", "RE",
]
SUBJECTS_PRIMARY = [
    "English", "Mathematics", "Science", "History", "Geography",
    "Art & Design", "Music", "PE", "Computing", "RE", "PSHE", "DT",
]


class DemoSeeder:
    """Generate realistic demo data for education system databases.

    Usage:
        seeder = DemoSeeder(system_key="sixth_form")
        students = seeder.generate_students(count=50)
        courses = seeder.generate_courses()
    """

    def __init__(self, system_key: str = "sixth_form"):
        self.system_key = system_key

    def _random_name(self) -> tuple[str, str, str]:
        gender = random.choice(["M", "F"])
        first = random.choice(FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F)
        last = random.choice(LAST_NAMES)
        return first, last, gender

    def _random_dob(self, min_age: int = 16, max_age: int = 19) -> str:
        today = datetime.now()
        age = random.randint(min_age, max_age)
        dob = today.replace(year=today.year - age) - timedelta(days=random.randint(0, 365))
        return dob.strftime("%Y-%m-%d")

    def _random_email(self, first: str, last: str, domain: str = "example.ac.uk") -> str:
        num = random.randint(1, 99)
        return f"{first.lower()}.{last.lower()}{num}@{domain}"

    def _random_phone(self) -> str:
        return f"07{''.join(random.choices(string.digits, k=9))}"

    def _random_address(self) -> str:
        num = random.randint(1, 200)
        streets = ["High Street", "Church Road", "Station Road", "Park Avenue",
                    "Victoria Road", "Manor Drive", "Oak Lane", "Mill Lane"]
        towns = ["Oxford", "Cambridge", "Bristol", "Leeds", "Manchester",
                 "Birmingham", "Sheffield", "York", "Bath", "Chester"]
        return f"{num} {random.choice(streets)}, {random.choice(towns)}"

    def generate_students(self, count: int = 50) -> list[dict]:
        """Generate realistic student records."""
        prefix_map = {"sixth_form": "SFC", "university": "UNI", "secondary": "SEC", "primary": "PRI"}
        prefix = prefix_map.get(self.system_key, "STU")

        domain_map = {"sixth_form": "sixthform.ac.uk", "university": "university.ac.uk",
                      "secondary": "secondary.sch.uk", "primary": "primary.sch.uk"}
        domain = domain_map.get(self.system_key, "school.ac.uk")

        age_map = {"sixth_form": (16, 19), "university": (18, 25), "secondary": (11, 16), "primary": (4, 11)}
        min_age, max_age = age_map.get(self.system_key, (11, 18))

        year_groups_map = {"sixth_form": ["12", "13"], "university": ["1", "2", "3", "4"],
                           "secondary": ["7", "8", "9", "10", "11"],
                           "primary": ["Reception", "1", "2", "3", "4", "5", "6"]}
        year_groups = year_groups_map.get(self.system_key, ["12", "13"])

        students = []
        for i in range(1, count + 1):
            first, last, gender = self._random_name()
            yg = random.choice(year_groups)
            students.append({
                "student_id": f"{prefix}{i:04d}",
                "first_name": first, "last_name": last, "gender": gender,
                "date_of_birth": self._random_dob(min_age, max_age),
                "email": self._random_email(first, last, domain),
                "phone": self._random_phone(),
                "address": self._random_address(),
                "year_group": yg, "form_group": f"{yg}{random.choice('ABCDEF')}",
                "status": random.choices(["active", "inactive"], weights=[95, 5])[0],
                "enrolment_date": (datetime.now() - timedelta(days=random.randint(30, 400))).strftime("%Y-%m-%d"),
                "emergency_contact_name": f"{random.choice(FIRST_NAMES_M + FIRST_NAMES_F)} {last}",
                "emergency_contact_phone": self._random_phone(),
            })
        logger.info("Generated %d demo students for %s", count, self.system_key)
        return students

    def generate_courses(self) -> list[dict]:
        """Generate courses appropriate to the system type."""
        subjects_map = {"sixth_form": SUBJECTS_COLLEGE, "secondary": SUBJECTS_SECONDARY,
                        "primary": SUBJECTS_PRIMARY, "university": SUBJECTS_COLLEGE}
        subjects = subjects_map.get(self.system_key, SUBJECTS_COLLEGE)

        courses = []
        for i, subject in enumerate(subjects, 1):
            courses.append({
                "course_code": f"{''.join(w[0] for w in subject.split()[:2]).upper()}{i:02d}",
                "title": subject,
                "capacity": random.choice([20, 25, 30, 35]),
                "guided_learning_hours": random.choice([2, 3, 4, 5]),
                "subject_area": subject,
            })
        logger.info("Generated %d demo courses for %s", len(courses), self.system_key)
        return courses

    def generate_enrollments(self, students: list[dict], courses: list[dict], avg_per_student: int = 4) -> list[dict]:
        """Generate enrollment records."""
        enrollments = []
        for student in students:
            n = random.randint(max(1, avg_per_student - 1), avg_per_student + 1)
            for course in random.sample(courses, min(n, len(courses))):
                enrollments.append({
                    "student_id": student["student_id"],
                    "course_code": course["course_code"],
                    "status": "enrolled",
                    "enrolled_date": student.get("enrolment_date", datetime.now().strftime("%Y-%m-%d")),
                })
        logger.info("Generated %d demo enrollments", len(enrollments))
        return enrollments

    def generate_attendance(self, students: list[dict], days: int = 30) -> list[dict]:
        """Generate attendance records for the last N days."""
        records = []
        base = datetime.now()
        for student in students:
            for d in range(days):
                dt = base - timedelta(days=d)
                if dt.weekday() >= 5:
                    continue
                mark = random.choices(
                    ["present", "present", "late", "absent_authorised", "absent_unauthorised"],
                    weights=[70, 70, 10, 5, 2],
                )[0]
                records.append({
                    "student_id": student["student_id"],
                    "date": dt.strftime("%Y-%m-%d"),
                    "status": mark,
                    "period": random.choice(["AM", "PM", "1", "2", "3", "4", "5"]),
                })
        logger.info("Generated %d demo attendance records", len(records))
        return records

    def generate_grades(self, students: list[dict], courses: list[dict]) -> list[dict]:
        """Generate grade records."""
        grade_scales = {
            "sixth_form": ["A*", "A", "B", "C", "D", "E", "U"],
            "secondary": ["9", "8", "7", "6", "5", "4", "3", "2", "1"],
            "primary": ["Greater Depth", "Expected", "Developing", "Emerging"],
            "university": ["1st", "2:1", "2:2", "3rd", "Fail"],
        }
        scale = grade_scales.get(self.system_key, ["A", "B", "C", "D", "F"])
        weights = list(range(len(scale), 0, -1))

        grades = []
        for student in students:
            for course in random.sample(courses, min(4, len(courses))):
                grades.append({
                    "student_id": student["student_id"],
                    "course_code": course["course_code"],
                    "grade": random.choices(scale, weights=weights)[0],
                    "assessment_type": random.choice(["exam", "coursework", "mock"]),
                    "date": (datetime.now() - timedelta(days=random.randint(1, 90))).strftime("%Y-%m-%d"),
                })
        logger.info("Generated %d demo grades", len(grades))
        return grades
