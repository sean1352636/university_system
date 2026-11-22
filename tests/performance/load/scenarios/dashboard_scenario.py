"""
Dashboard load Locust scenario (read-only).

Simulates users repeatedly loading dashboards, KPI panels and activity feeds.
The server needs EDU_DEV_SEED=true for its demo logins.

Usage:
    locust -f tests/performance/load/scenarios/dashboard_scenario.py \\
           --headless -u 30 -r 3 --run-time 60s \\
           --host http://localhost:5000
"""

import random
import sys
from pathlib import Path

from locust import HttpUser, between, task

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import HEALTH, ROUTES, auth_headers, shared_token  # noqa: E402

SYSTEMS = list(ROUTES)


class DashboardUser(HttpUser):
    """Task weights favour read-only aggregation endpoints."""

    wait_time = between(1.0, 4.0)

    def on_start(self) -> None:
        self._system = random.choice(SYSTEMS)
        self._routes = ROUTES[self._system]
        self._headers = auth_headers(shared_token(self, self._system))

    def _get(self, path, label):
        with self.client.get(
            path,
            headers=self._headers,
            catch_response=True,
            name=f"GET {self._system} {label}",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"{path}: {resp.status_code}")

    @task(10)
    def dashboard_refresh(self) -> None:
        """Refresh the main dashboard. Should stay under 500 ms at p95."""
        self._get(self._routes["dashboard"], "dashboard")

    @task(5)
    def full_dashboard_page_load(self) -> None:
        """The calls a dashboard page makes when it first loads."""
        for key in ("dashboard", "learners", "records", "courses"):
            self._get(self._routes[key], f"{key} (page load)")

    @task(3)
    def kpi_panel(self) -> None:
        """KPI panels use multi-table aggregates, so expect them to be slowest."""
        self._get(random.choice(self._routes["kpis"]), "KPI panel")

    @task(2)
    def activity_feed(self) -> None:
        """Reads recently written rows, so it is sensitive to write concurrency."""
        activity = self._routes["activity"]
        if activity:
            self._get(random.choice(activity), "activity")

    @task(1)
    def health_probe(self) -> None:
        with self.client.get(
            HEALTH,
            catch_response=True,
            name="GET health (dashboard probe)",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Health: {resp.status_code}")
