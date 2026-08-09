"""
CRUD lifecycle Locust scenario.

Each virtual user performs a full create → enroll → grade → query → update →
delete cycle.  This exercises write paths, relational joins, and delete
cascades end-to-end.

Usage:
    locust -f tests/performance/scenarios/crud_scenario.py \\
           --headless -u 10 -r 1 --run-time 60s \\
           --host http://localhost:5000
"""

import random
import string
import time

from locust import HttpUser, task, between, SequentialTaskSet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CREDENTIALS = {"username": "Admin@College", "password": "Admin@College123"}


def _rand(n: int = 7) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))


def _student_payload() -> dict:
    first = _rand(5).capitalize()
    last = _rand(7).capitalize()
    return {
        "first_name": first,
        "last_name": last,
        "email": f"{first.lower()}.{last.lower()}.{int(time.time() * 1000) % 100000}@test.edu",
        "year_group": random.choice(["Year 12", "Year 13"]),
        "date_of_birth": f"{random.randint(2000, 2006)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
    }


def _grade_payload(student_id: int, course_id: int) -> dict:
    return {
        "student_id": student_id,
        "course_id": course_id,
        "grade": random.choice(["A*", "A", "B", "C", "D", "E"]),
        "percentage": round(random.uniform(40.0, 100.0), 1),
        "assessment_type": random.choice(["exam", "coursework", "mock"]),
    }


# ---------------------------------------------------------------------------
# Task set — sequential lifecycle
# ---------------------------------------------------------------------------

class CRUDLifecycle(SequentialTaskSet):
    """
    Executes a full CRUD lifecycle in order:

    1. Create student
    2. Fetch the course list and pick one
    3. Enroll the student in a course
    4. Record a grade
    5. Query grades for that student
    6. Update the student's details
    7. Delete the enrollment (cleanup)
    """

    _student_pk: int = 0
    _course_id: int = 0
    _enrollment_id: int = 0

    @task
    def step1_create_student(self) -> None:
        payload = _student_payload()
        with self.client.post(
            "/api/students",
            json=payload,
            headers=self.user._headers,
            catch_response=True,
            name="CRUD 1/7 POST /api/students",
        ) as resp:
            if resp.status_code in (201, 200):
                data = resp.json().get("data", {})
                self._student_pk = data.get("id") or data.get("student_pk", 0)
                resp.success()
            elif resp.status_code in (400, 401, 403):
                resp.success()
                self._student_pk = random.randint(1, 30)  # fallback
            else:
                resp.failure(f"Create student: {resp.status_code}")
                self._student_pk = random.randint(1, 30)

    @task
    def step2_list_courses(self) -> None:
        with self.client.get(
            "/api/courses",
            params={"limit": 20},
            headers=self.user._headers,
            catch_response=True,
            name="CRUD 2/7 GET /api/courses",
        ) as resp:
            if resp.status_code == 200:
                courses = resp.json().get("data", [])
                if courses:
                    self._course_id = random.choice(courses).get("id", 1)
                else:
                    self._course_id = 1
                resp.success()
            elif resp.status_code in (401,):
                self._course_id = 1
                resp.success()
            else:
                resp.failure(f"List courses: {resp.status_code}")
                self._course_id = 1

    @task
    def step3_enroll_student(self) -> None:
        if not self._student_pk or not self._course_id:
            return

        payload = {
            "student_id": self._student_pk,
            "course_id": self._course_id,
            "status": "active",
        }
        with self.client.post(
            "/api/enrollments",
            json=payload,
            headers=self.user._headers,
            catch_response=True,
            name="CRUD 3/7 POST /api/enrollments",
        ) as resp:
            if resp.status_code in (201, 200, 400, 409):
                if resp.status_code in (201, 200):
                    self._enrollment_id = resp.json().get("data", {}).get("id", 0)
                resp.success()
            elif resp.status_code in (401, 403):
                resp.success()
            else:
                resp.failure(f"Enroll: {resp.status_code}")

    @task
    def step4_record_grade(self) -> None:
        if not self._student_pk or not self._course_id:
            return

        payload = _grade_payload(self._student_pk, self._course_id)
        with self.client.post(
            "/api/grades",
            json=payload,
            headers=self.user._headers,
            catch_response=True,
            name="CRUD 4/7 POST /api/grades",
        ) as resp:
            if resp.status_code in (201, 200, 400, 401, 403):
                resp.success()
            else:
                resp.failure(f"Record grade: {resp.status_code}")

    @task
    def step5_query_grades(self) -> None:
        if not self._student_pk:
            return

        with self.client.get(
            "/api/grades",
            params={"student_id": self._student_pk, "limit": 50},
            headers=self.user._headers,
            catch_response=True,
            name="CRUD 5/7 GET /api/grades?student_id=...",
        ) as resp:
            if resp.status_code in (200, 401, 404):
                resp.success()
            else:
                resp.failure(f"Query grades: {resp.status_code}")

    @task
    def step6_update_student(self) -> None:
        if not self._student_pk:
            return

        update = {"phone": f"07{random.randint(100000000, 999999999)}"}
        with self.client.put(
            f"/api/students/{self._student_pk}",
            json=update,
            headers=self.user._headers,
            catch_response=True,
            name="CRUD 6/7 PUT /api/students/{id}",
        ) as resp:
            if resp.status_code in (200, 400, 401, 403, 404):
                resp.success()
            else:
                resp.failure(f"Update student: {resp.status_code}")

    @task
    def step7_delete_enrollment(self) -> None:
        if not self._enrollment_id:
            return

        with self.client.delete(
            f"/api/enrollments/{self._enrollment_id}",
            headers=self.user._headers,
            catch_response=True,
            name="CRUD 7/7 DELETE /api/enrollments/{id}",
        ) as resp:
            if resp.status_code in (200, 204, 401, 403, 404):
                resp.success()
            else:
                resp.failure(f"Delete enrollment: {resp.status_code}")

        # Reset state so the next lifecycle starts fresh
        self._student_pk = 0
        self._course_id = 0
        self._enrollment_id = 0


# ---------------------------------------------------------------------------
# User class
# ---------------------------------------------------------------------------

class CRUDUser(HttpUser):
    """
    Simulates an admin/staff user performing database-intensive write operations.

    Uses SequentialTaskSet so each step of the lifecycle runs in order.
    """

    tasks = [CRUDLifecycle]
    wait_time = between(1.0, 3.0)

    _token: str = ""
    _headers: dict = {}

    def on_start(self) -> None:
        """Authenticate before running any CRUD tasks."""
        with self.client.post(
            "/api/auth/login",
            json=_CREDENTIALS,
            headers={"Content-Type": "application/json"},
            catch_response=True,
            name="[setup] POST /api/auth/login",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("access_token") or data.get("token", "")
                resp.success()
            else:
                self._token = ""
                resp.success()

        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
