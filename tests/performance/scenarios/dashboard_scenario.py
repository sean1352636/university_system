"""
Dashboard-heavy Locust scenario.

Simulates the realistic pattern where many staff members keep a dashboard tab
open and refresh it every few seconds.  Dashboard endpoints typically trigger
expensive aggregation queries (count totals, attendance rates, recent activity)
so they are the most latency-sensitive pages in the system.

Usage:
    locust -f tests/performance/scenarios/dashboard_scenario.py \\
           --headless -u 30 -r 5 --run-time 60s \\
           --host http://localhost:5000
"""

import random

from locust import HttpUser, task, between, constant_pacing

# ---------------------------------------------------------------------------
# Credentials — staff role is the most common dashboard consumer
# ---------------------------------------------------------------------------

_CREDENTIALS_POOL = [
    {"username": "Staff@College",    "password": "Staff@College123"},
    {"username": "Admin@College",    "password": "Admin@College123"},
    {"username": "Staff@University", "password": "Staff@University123"},
]

# Endpoints that contribute to a full dashboard render
_DASHBOARD_ENDPOINTS = [
    "/api/dashboard-data",
    "/api/students?limit=10&status=active",
    "/api/attendance?limit=10",
    "/api/courses?limit=10",
]

_KPI_ENDPOINTS = [
    "/api/kpi-dashboard",
    "/api/data-dashboard",
    "/api/progress-dashboard",
]

_ACTIVITY_ENDPOINTS = [
    "/api/activity-feed?limit=20",
    "/api/notifications?limit=10",
    "/api/announcements?limit=5",
]


# ---------------------------------------------------------------------------
# User class
# ---------------------------------------------------------------------------

class DashboardUser(HttpUser):
    """
    Simulates users who repeatedly load and refresh dashboard views.

    Task weights heavily favour read-only aggregation endpoints.  A small
    weight is given to navigation between different dashboard pages to reflect
    realistic browsing patterns.
    """

    # constant_pacing ensures exactly one task-iteration per N seconds,
    # regardless of response time, modelling auto-refresh behaviour.
    wait_time = between(1.0, 4.0)

    _token: str = ""
    _headers: dict = {}

    def on_start(self) -> None:
        """Authenticate and build the auth header."""
        creds = random.choice(_CREDENTIALS_POOL)
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
            else:
                self._token = ""
                resp.success()

        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }

    # -----------------------------------------------------------------------
    # Tasks
    # -----------------------------------------------------------------------

    @task(10)
    def main_dashboard_refresh(self) -> None:
        """
        The primary use case: refresh the main dashboard data endpoint.

        This aggregates student counts, recent attendance, upcoming events and
        other KPIs into a single response.  It is the most common request and
        should complete in under 500 ms at p95.
        """
        with self.client.get(
            "/api/dashboard-data",
            headers=self._headers,
            catch_response=True,
            name="GET /api/dashboard-data",
        ) as resp:
            if resp.status_code in (200, 401, 404):
                resp.success()
            else:
                resp.failure(f"Dashboard data: {resp.status_code}")

    @task(5)
    def full_dashboard_page_load(self) -> None:
        """
        Simulate all XHR calls fired when the dashboard page first loads.

        A real browser issues several parallel requests; Locust fires them
        sequentially — the combined time still reflects page-load pressure.
        """
        for endpoint in _DASHBOARD_ENDPOINTS:
            with self.client.get(
                endpoint,
                headers=self._headers,
                catch_response=True,
                name=f"GET {endpoint.split('?')[0]} (page-load)",
            ) as resp:
                if resp.status_code in (200, 401, 404):
                    resp.success()
                else:
                    resp.failure(f"{endpoint}: {resp.status_code}")

    @task(3)
    def kpi_dashboard(self) -> None:
        """
        Fetch KPI / progress dashboard panels — often involve multi-table
        aggregations and are expected to be the slowest endpoints (<1 s p95).
        """
        endpoint = random.choice(_KPI_ENDPOINTS)
        with self.client.get(
            endpoint,
            headers=self._headers,
            catch_response=True,
            name=f"GET {endpoint} (KPI)",
        ) as resp:
            if resp.status_code in (200, 401, 404):
                resp.success()
            else:
                resp.failure(f"KPI endpoint {endpoint}: {resp.status_code}")

    @task(2)
    def activity_feed(self) -> None:
        """
        Load the live activity feed and notifications panel.

        These endpoints read from recently-written rows and are sensitive to
        write concurrency.
        """
        endpoint = random.choice(_ACTIVITY_ENDPOINTS)
        with self.client.get(
            endpoint,
            headers=self._headers,
            catch_response=True,
            name=f"GET {endpoint.split('?')[0]} (activity)",
        ) as resp:
            if resp.status_code in (200, 401, 404):
                resp.success()
            else:
                resp.failure(f"Activity endpoint {endpoint}: {resp.status_code}")

    @task(1)
    def report_summary(self) -> None:
        """
        Trigger a lightweight report summary — the most expensive operation.

        Reports aggregate across many tables with GROUP BY clauses and are
        expected to stay below 1 s p95.
        """
        report_type = random.choice(["attendance", "grades", "behaviour"])
        with self.client.get(
            f"/api/reports?type={report_type}&format=summary",
            headers=self._headers,
            catch_response=True,
            name="GET /api/reports (summary)",
        ) as resp:
            if resp.status_code in (200, 400, 401, 404):
                resp.success()
            else:
                resp.failure(f"Report summary: {resp.status_code}")

    @task(1)
    def health_probe(self) -> None:
        """Include health checks in the dashboard scenario to verify uptime."""
        with self.client.get(
            "/api/health",
            catch_response=True,
            name="GET /api/health (dashboard probe)",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Health: {resp.status_code}")
