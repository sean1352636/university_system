"""
Main Locust file — Education Management System load test.

Read-only mix of API requests across four systems, with realistic task weights.
crud_scenario.py covers writes. The server needs EDU_DEV_SEED=true for its demo
logins (see common.py).

Usage:
    locust -f tests/performance/load/locustfile.py \\
           --headless -u 50 -r 5 --run-time 60s \\
           --host http://localhost:5000
"""

import logging
import random

from locust import HttpUser, between, events, task

from common import HEALTH, ROUTES, auth_headers, record_id, rows, shared_token

logger = logging.getLogger(__name__)

SYSTEMS = list(ROUTES)


class EducationSystemUser(HttpUser):
    """Each virtual user picks a system at startup and reads from it."""

    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        self._system = random.choice(SYSTEMS)
        self._routes = ROUTES[self._system]
        self._headers = auth_headers(shared_token(self, self._system))
        self._known_ids = []

    def _get(self, path, name, **params):
        with self.client.get(
            path,
            params=params or None,
            headers=self._headers,
            catch_response=True,
            name=f"GET {name}",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"{path}: {resp.status_code}")
            return resp

    @task(5)
    def dashboard_load(self) -> None:
        """The dashboard summary — the most frequent operation."""
        self._get(self._routes["dashboard"], f"{self._system} dashboard")

    @task(3)
    def list_learners(self) -> None:
        resp = self._get(self._routes["learners"], f"{self._system} learners")
        ids = [record_id(row) for row in rows(resp)]
        self._known_ids = [i for i in ids if i is not None][-20:]

    @task(2)
    def get_learner(self) -> None:
        template = self._routes["learner"]
        if not template or not self._known_ids:
            return
        path = template.format(id=random.choice(self._known_ids))
        self._get(path, f"{self._system} learner by id")

    @task(3)
    def list_courses(self) -> None:
        self._get(self._routes["courses"], f"{self._system} courses or subjects")

    @task(2)
    def search_learners(self) -> None:
        search = self._routes["search"]
        if not search:
            return
        path, param = search
        term = random.choice(["sm", "jo", "an", "wi"])
        self._get(path, f"{self._system} learner search", **{param: term})

    @task(2)
    def list_records(self) -> None:
        """A medium-cost read: grades, timetable or attendance."""
        self._get(self._routes["records"], f"{self._system} records")

    @task(1)
    def health_check(self) -> None:
        """Lightweight liveness probe — should always be fast."""
        self._get(HEALTH, "health")


@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    """Log a summary line when the run finishes."""
    total = environment.stats.total
    logger.info(
        "Run complete | requests=%d failures=%d avg_ms=%.1f p95_ms=%.1f",
        total.num_requests,
        total.num_failures,
        total.avg_response_time,
        total.get_response_time_percentile(0.95) or 0,
    )
