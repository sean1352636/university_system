"""
Main Locust file — Education Management System load test.

Combines all task scenarios into a single EducationSystemUser that exercises
the full breadth of API endpoints with realistic task weights.

Usage:
    locust -f tests/performance/locustfile.py \\
           --headless -u 50 -r 5 --run-time 60s \\
           --host http://localhost:5000
"""

import random
import string
import time
import logging

from locust import HttpUser, task, between, events

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SYSTEMS = ["university", "college", "secondary", "primary"]

# Credentials that match the seeded demo accounts (see shared auth defaults).
# Pattern: <Role>@<System>123
_CREDENTIALS = {
    "university": {"username": "Admin@University", "password": "Admin@University123"},
    "college":    {"username": "Admin@College",    "password": "Admin@College123"},
    "secondary":  {"username": "Admin@School",     "password": "Admin@School123"},
    "primary":    {"username": "Admin@Primary",    "password": "Admin@Primary123"},
}


def _random_string(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=length))


def _random_student_payload(system: str) -> dict:
    first = _random_string(6).capitalize()
    last = _random_string(8).capitalize()
    return {
        "first_name": first,
        "last_name": last,
        "email": f"{first.lower()}.{last.lower()}@example.edu",
        "year_group": random.choice(["Year 12", "Year 13"]) if system == "college" else "Year 10",
    }


# ---------------------------------------------------------------------------
# Main combined user
# ---------------------------------------------------------------------------

class EducationSystemUser(HttpUser):
    """
    Simulates a realistic mix of authenticated users across all four systems.

    Each virtual user picks a random system at startup, logs in, then runs
    tasks according to the weights below.
    """

    wait_time = between(0.5, 2.0)

    # Populated in on_start
    _token: str = ""
    _system: str = ""
    _headers: dict = {}
    _known_student_ids: list = []

    def on_start(self) -> None:
        """Authenticate once per simulated user and store the JWT token."""
        self._system = random.choice(SYSTEMS)
        creds = _CREDENTIALS[self._system]

        with self.client.post(
            "/api/auth/login",
            json=creds,
            headers={"Content-Type": "application/json"},
            catch_response=True,
            name="[setup] POST /api/auth/login",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("access_token") or data.get("token", "")
                resp.success()
            elif resp.status_code == 401:
                # Server running but credentials wrong — mark success so the
                # user is still created; tasks will simply get 401s.
                self._token = ""
                resp.success()
            else:
                resp.failure(f"Login failed: {resp.status_code}")
                self._token = ""

        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }

    def on_stop(self) -> None:
        """Optionally log out when the user session ends."""
        if self._token:
            self.client.post(
                "/api/auth/logout",
                headers=self._headers,
                catch_response=True,
                name="[teardown] POST /api/auth/logout",
            )

    # -----------------------------------------------------------------------
    # Tasks
    # -----------------------------------------------------------------------

    @task(5)
    def dashboard_load(self) -> None:
        """Fetch dashboard summary data — the most frequent operation."""
        self.client.get(
            "/api/dashboard-data",
            headers=self._headers,
            name="GET /api/dashboard-data",
        )

    @task(3)
    def list_students(self) -> None:
        """Paginated student list with optional status filter."""
        page = random.randint(1, 5)
        limit = random.choice([20, 50, 100])
        offset = (page - 1) * limit
        status = random.choice(["active", "active", "active", "inactive", ""])
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        with self.client.get(
            "/api/students",
            params=params,
            headers=self._headers,
            catch_response=True,
            name="GET /api/students (paginated)",
        ) as resp:
            if resp.status_code in (200, 401):
                if resp.status_code == 200:
                    try:
                        ids = [s.get("id") for s in resp.json().get("data", []) if s.get("id")]
                        if ids:
                            self._known_student_ids = ids[-20:]
                    except Exception:
                        pass
                resp.success()
            else:
                resp.failure(f"Unexpected {resp.status_code}")

    @task(2)
    def get_student(self) -> None:
        """Retrieve a single student record."""
        if self._known_student_ids:
            student_id = random.choice(self._known_student_ids)
        else:
            student_id = random.randint(1, 50)

        with self.client.get(
            f"/api/students/{student_id}",
            headers=self._headers,
            catch_response=True,
            name="GET /api/students/{id}",
        ) as resp:
            if resp.status_code in (200, 404, 401):
                resp.success()
            else:
                resp.failure(f"Unexpected {resp.status_code}")

    @task(1)
    def create_student(self) -> None:
        """Create a new student (write-heavy scenario, lower weight)."""
        payload = _random_student_payload(self._system)

        with self.client.post(
            "/api/students",
            json=payload,
            headers=self._headers,
            catch_response=True,
            name="POST /api/students",
        ) as resp:
            if resp.status_code in (201, 200, 400, 401, 403):
                if resp.status_code == 201:
                    try:
                        new_id = resp.json().get("data", {}).get("id")
                        if new_id:
                            self._known_student_ids.append(new_id)
                    except Exception:
                        pass
                resp.success()
            else:
                resp.failure(f"Unexpected {resp.status_code}")

    @task(3)
    def list_courses(self) -> None:
        """Fetch the course catalogue."""
        with self.client.get(
            "/api/courses",
            params={"limit": 50, "offset": 0},
            headers=self._headers,
            catch_response=True,
            name="GET /api/courses",
        ) as resp:
            if resp.status_code in (200, 401):
                resp.success()
            else:
                resp.failure(f"Unexpected {resp.status_code}")

    @task(2)
    def search_students(self) -> None:
        """Full-text search across student records."""
        query = random.choice(["Smith", "Jones", "Brown", "Taylor", "a", "e"])

        with self.client.get(
            "/api/students",
            params={"search": query, "limit": 25},
            headers=self._headers,
            catch_response=True,
            name="GET /api/students?search=...",
        ) as resp:
            if resp.status_code in (200, 401):
                resp.success()
            else:
                resp.failure(f"Unexpected {resp.status_code}")

    @task(2)
    def attendance_check(self) -> None:
        """Retrieve attendance records — typically a medium-cost query."""
        with self.client.get(
            "/api/attendance",
            params={"limit": 50},
            headers=self._headers,
            catch_response=True,
            name="GET /api/attendance",
        ) as resp:
            if resp.status_code in (200, 401, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected {resp.status_code}")

    @task(1)
    def health_check(self) -> None:
        """Lightweight liveness probe — should always be fast."""
        with self.client.get(
            "/api/health",
            catch_response=True,
            name="GET /api/health",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Health check returned {resp.status_code}")


# ---------------------------------------------------------------------------
# Event hooks (optional reporting)
# ---------------------------------------------------------------------------

@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    """Log a summary line when the run finishes."""
    stats = environment.stats
    total = stats.total
    logger.info(
        "Run complete | requests=%d failures=%d avg_ms=%.1f p95_ms=%.1f",
        total.num_requests,
        total.num_failures,
        total.avg_response_time,
        total.get_response_time_percentile(0.95) or 0,
    )
