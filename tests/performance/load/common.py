"""Shared paths and logins for the Locust load tests.

The logins are the demo accounts in docs/reference/DEFAULT_ACCOUNTS.md, so the
server under test needs EDU_DEV_SEED=true. Every path was checked against
docs/api/openapi.json; regenerate that file and re-check if routes move.
"""

import sys

from gevent.lock import Semaphore
from locust.exception import StopUser

API = "/api/v1"
LOGIN = f"{API}/auth/login"
LOGOUT = f"{API}/auth/logout"
REFRESH = f"{API}/auth/refresh"
HEALTH = f"{API}/health"

JSON_HEADERS = {"Content-Type": "application/json"}

ACCOUNTS = {
    "university": {"username": "admin", "password": "admin123"},
    "sixth_form": {"username": "admin1", "password": "admin1234"},
    "secondary": {"username": "admin2", "password": "admin1234"},
    "primary": {"username": "admin3", "password": "admin1234"},
}

# The same reads exist under different paths in each system. A path of None
# means that system has no such route, and the task skips it.
ROUTES = {
    "university": {
        "dashboard": f"{API}/university/dashboard",
        "learners": f"{API}/university/students",
        "learner": f"{API}/university/students/{{id}}",
        "search": (f"{API}/university/students", "search"),
        "courses": f"{API}/university/courses",
        "records": f"{API}/university/grades",
        "kpis": [f"{API}/university/analytics/enrollment"],
        "activity": [
            f"{API}/university/notifications",
            f"{API}/university/announcements",
        ],
    },
    "sixth_form": {
        "dashboard": f"{API}/sixthform/reports/kpi/snapshot",
        "learners": f"{API}/sixthform/student-services/enrolments",
        "learner": None,
        "search": None,
        "courses": f"{API}/sixthform/academics/courses",
        "records": f"{API}/sixthform/academics/subjects",
        "kpis": [f"{API}/sixthform/reports/kpi/snapshot"],
        "activity": [],
    },
    "secondary": {
        "dashboard": f"{API}/school/reports/kpi/snapshot",
        "learners": f"{API}/school/pupils/pupils",
        "learner": f"{API}/school/pupils/pupils/{{id}}",
        "search": None,
        "courses": f"{API}/school/academics/subjects",
        "records": f"{API}/school/academics/timetable",
        "kpis": [f"{API}/school/reports/kpi/snapshot"],
        "activity": [],
    },
    "primary": {
        "dashboard": f"{API}/primary/kpi-dashboard",
        "learners": f"{API}/primary/pupils",
        "learner": f"{API}/primary/pupils/{{id}}",
        "search": (f"{API}/primary/pupils/search", "q"),
        "courses": f"{API}/primary/subjects",
        "records": f"{API}/primary/attendance",
        "kpis": [
            f"{API}/primary/kpi-dashboard",
            f"{API}/primary/data-dashboard",
            f"{API}/primary/mobile-dashboard",
        ],
        "activity": [f"{API}/primary/attendance-report/summary"],
    },
}

_tokens = {}
_login_lock = Semaphore()


def auth_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    }


def shared_token(user, system):
    """One login per account for the whole run.

    Login allows 10 requests a minute per IP, so a login per virtual user would
    get 429s and leave most users with no token. auth_scenario.py measures login.
    """
    with _login_lock:
        if system in _tokens:
            return _tokens[system]
        token = ""
        with user.client.post(
            LOGIN,
            json=ACCOUNTS[system],
            headers=JSON_HEADERS,
            catch_response=True,
            name=f"[setup] POST {LOGIN}",
        ) as resp:
            if resp.status_code == 200:
                body = resp.json()
                token = body.get("access_token") or body.get("token", "")
                resp.success()
            else:
                resp.failure(f"Login as {ACCOUNTS[system]['username']}: {resp.status_code}")
                print(
                    f"Login failed for {system}: {resp.status_code}. "
                    "Is the server running with EDU_DEV_SEED=true?",
                    file=sys.stderr,
                )
        if not token:
            raise StopUser()
        _tokens[system] = token
        return token


def rows(resp):
    """The list in a response, whichever shape this route uses."""
    try:
        body = resp.json()
    except ValueError:
        return []
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for key in ("items", "data", "results", "rows"):
            if isinstance(body.get(key), list):
                return body[key]
    return []


def record_id(row):
    if not isinstance(row, dict):
        return None
    for key in ("id", "student_id", "pupil_id"):
        if row.get(key) not in (None, ""):
            return row[key]
    return None
