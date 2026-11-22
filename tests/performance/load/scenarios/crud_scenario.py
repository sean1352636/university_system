"""
CRUD lifecycle Locust scenario, run against the Primary School API.

Each virtual user creates a pupil, records attendance, reads, updates and then
deletes what it made.

This writes to the database of the server under test, so it refuses to start
unless LOAD_TEST_ALLOW_WRITES=1. Never run it against a server holding real data.
The server needs EDU_DEV_SEED=true for its demo logins.

Usage:
    LOAD_TEST_ALLOW_WRITES=1 locust -f tests/performance/load/scenarios/crud_scenario.py \\
           --headless -u 10 -r 1 --run-time 60s \\
           --host http://localhost:5000
"""

import os
import random
import string
import sys
from pathlib import Path

from locust import HttpUser, SequentialTaskSet, between, task
from locust.exception import StopUser

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import API, auth_headers, record_id, shared_token  # noqa: E402

PUPILS = f"{API}/primary/pupils"
SUBJECTS = f"{API}/primary/subjects"
ATTENDANCE = f"{API}/primary/attendance"


def _rand(n: int = 7) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))


def _pupil_payload() -> dict:
    return {
        "first_name": f"Load{_rand(5)}",
        "last_name": f"Test{_rand(7)}",
        "date_of_birth": f"{random.randint(2015, 2019)}-0{random.randint(1, 9)}-15",
        "year_group": random.choice(["Year 1", "Year 2", "Year 3"]),
    }


class CRUDLifecycle(SequentialTaskSet):
    """Runs in order, then starts again with a new pupil."""

    _pupil_id = None
    _attendance_id = None

    def _call(self, method, path, label, ok=(200,), **kwargs):
        with self.client.request(
            method,
            path,
            headers=self.user._headers,
            catch_response=True,
            name=f"CRUD {label}",
            **kwargs,
        ) as resp:
            if resp.status_code in ok:
                resp.success()
                return resp
            resp.failure(f"{method} {path}: {resp.status_code} {resp.text[:120]}")
            return None

    @task
    def step1_create_pupil(self) -> None:
        self._pupil_id = self._attendance_id = None
        resp = self._call("POST", PUPILS, "1/7 POST pupil", ok=(201,), json=_pupil_payload())
        if resp is None:
            self.interrupt(reschedule=True)
        self._pupil_id = record_id(resp.json())

    @task
    def step2_list_subjects(self) -> None:
        self._call("GET", SUBJECTS, "2/7 GET subjects")

    @task
    def step3_record_attendance(self) -> None:
        resp = self._call(
            "POST",
            ATTENDANCE,
            "3/7 POST attendance",
            ok=(201,),
            json={
                "pupil_id": self._pupil_id,
                "date": "2026-01-15",
                "session": "AM",
                "mark": "/",
            },
        )
        if resp is not None:
            self._attendance_id = resp.json().get("id")

    @task
    def step4_read_pupil_attendance(self) -> None:
        self._call(
            "GET",
            f"{ATTENDANCE}/summary/pupil/{self._pupil_id}",
            "4/7 GET pupil attendance summary",
        )

    @task
    def step5_update_pupil(self) -> None:
        self._call(
            "PUT",
            f"{PUPILS}/{self._pupil_id}",
            "5/7 PUT pupil",
            json={"first_name": f"Load{_rand(5)}"},
        )

    @task
    def step6_delete_attendance(self) -> None:
        if self._attendance_id is not None:
            self._call("DELETE", f"{ATTENDANCE}/{self._attendance_id}", "6/7 DELETE attendance")

    @task
    def step7_delete_pupil(self) -> None:
        self._call("DELETE", f"{PUPILS}/{self._pupil_id}", "7/7 DELETE pupil")


class CRUDUser(HttpUser):
    """An admin performing database-intensive writes."""

    tasks = [CRUDLifecycle]
    wait_time = between(1.0, 3.0)

    def on_start(self) -> None:
        if os.environ.get("LOAD_TEST_ALLOW_WRITES") != "1":
            print(
                "crud_scenario writes to the server's database. Set "
                "LOAD_TEST_ALLOW_WRITES=1 if it holds no real data.",
                file=sys.stderr,
            )
            raise StopUser()
        self._headers = auth_headers(shared_token(self, "primary"))
