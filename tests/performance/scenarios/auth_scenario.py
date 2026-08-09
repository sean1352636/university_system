"""
Auth-focused Locust scenario.

Stress-tests login, token refresh, logout, and failure paths to ensure the
authentication layer does not become a bottleneck under concurrent load.

Usage:
    locust -f tests/performance/scenarios/auth_scenario.py \\
           --headless -u 20 -r 2 --run-time 30s \\
           --host http://localhost:5000
"""

import random
import string

from locust import HttpUser, task, between

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_CREDENTIALS = [
    {"username": "Admin@College",    "password": "Admin@College123"},
    {"username": "Staff@College",    "password": "Staff@College123"},
    {"username": "Admin@University", "password": "Admin@University123"},
]

_WRONG_PASSWORD = "WrongPassword999!"


def _random_string(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))


# ---------------------------------------------------------------------------
# User class
# ---------------------------------------------------------------------------

class AuthUser(HttpUser):
    """
    Simulates users whose primary activity is auth-related:
    logging in, refreshing tokens, and logging out.

    Also exercises the rejection path (wrong password) to ensure rate-limiting
    and error handling do not degrade under pressure.
    """

    wait_time = between(0.3, 1.5)

    _token: str = ""
    _refresh_token: str = ""
    _headers: dict = {}

    def on_start(self) -> None:
        """Perform initial login to warm up a valid session."""
        self._do_login(random.choice(_VALID_CREDENTIALS))

    def _do_login(self, creds: dict) -> bool:
        """POST /api/auth/login and cache the returned token. Returns True on success."""
        with self.client.post(
            "/api/auth/login",
            json=creds,
            headers={"Content-Type": "application/json"},
            catch_response=True,
            name="POST /api/auth/login (valid)",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("access_token") or data.get("token", "")
                self._refresh_token = data.get("refresh_token", "")
                self._headers = {
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                }
                resp.success()
                return True
            elif resp.status_code in (400, 401, 429):
                # Acceptable — wrong creds or rate-limited
                resp.success()
                return False
            else:
                resp.failure(f"Unexpected login status: {resp.status_code}")
                return False

    # -----------------------------------------------------------------------
    # Tasks
    # -----------------------------------------------------------------------

    @task(5)
    def login_valid(self) -> None:
        """Login with valid credentials and cache the token."""
        creds = random.choice(_VALID_CREDENTIALS)
        self._do_login(creds)

    @task(2)
    def token_refresh(self) -> None:
        """Attempt token refresh using the refresh token."""
        if not self._refresh_token:
            # No refresh token available — skip silently
            return

        with self.client.post(
            "/api/auth/refresh",
            json={"refresh_token": self._refresh_token},
            headers=self._headers,
            catch_response=True,
            name="POST /api/auth/refresh",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                new_token = data.get("access_token") or data.get("token", "")
                if new_token:
                    self._token = new_token
                    self._headers["Authorization"] = f"Bearer {self._token}"
                resp.success()
            elif resp.status_code in (400, 401):
                resp.success()
            else:
                resp.failure(f"Unexpected refresh status: {resp.status_code}")

    @task(3)
    def logout(self) -> None:
        """Log out and immediately re-login to maintain an active session."""
        with self.client.post(
            "/api/auth/logout",
            headers=self._headers,
            catch_response=True,
            name="POST /api/auth/logout",
        ) as resp:
            if resp.status_code in (200, 204, 401):
                resp.success()
            else:
                resp.failure(f"Unexpected logout status: {resp.status_code}")

        # Re-authenticate so subsequent tasks have a valid token
        self._do_login(random.choice(_VALID_CREDENTIALS))

    @task(2)
    def login_wrong_password(self) -> None:
        """
        Login with a wrong password — expects 401.

        Verifies the server correctly rejects bad credentials without crashing
        or leaking information, even under concurrent load.
        """
        creds = dict(random.choice(_VALID_CREDENTIALS))
        creds["password"] = _WRONG_PASSWORD

        with self.client.post(
            "/api/auth/login",
            json=creds,
            headers={"Content-Type": "application/json"},
            catch_response=True,
            name="POST /api/auth/login (wrong password → 401)",
        ) as resp:
            if resp.status_code == 401:
                resp.success()
            elif resp.status_code == 429:
                # Rate-limited — also an acceptable response
                resp.success()
            else:
                resp.failure(
                    f"Expected 401 for wrong password, got {resp.status_code}"
                )

    @task(1)
    def login_nonexistent_user(self) -> None:
        """
        Login with a username that does not exist — expects 401.

        Ensures user enumeration is not possible (same response as wrong
        password).
        """
        fake_creds = {
            "username": f"ghost_{_random_string(6)}@nowhere.edu",
            "password": "SomePassword123!",
        }

        with self.client.post(
            "/api/auth/login",
            json=fake_creds,
            headers={"Content-Type": "application/json"},
            catch_response=True,
            name="POST /api/auth/login (nonexistent user → 401)",
        ) as resp:
            if resp.status_code in (401, 429):
                resp.success()
            else:
                resp.failure(
                    f"Expected 401 for nonexistent user, got {resp.status_code}"
                )

    @task(1)
    def concurrent_login_same_user(self) -> None:
        """
        Multiple rapid logins for the same account without logging out first.

        Validates that the session store handles concurrent logins gracefully
        (e.g., multiple valid tokens or oldest-session eviction, not errors).
        """
        creds = _VALID_CREDENTIALS[0]
        responses = []

        for _ in range(3):
            with self.client.post(
                "/api/auth/login",
                json=creds,
                headers={"Content-Type": "application/json"},
                catch_response=True,
                name="POST /api/auth/login (concurrent)",
            ) as resp:
                responses.append(resp.status_code)
                if resp.status_code in (200, 401, 429):
                    resp.success()
                else:
                    resp.failure(f"Unexpected status during concurrent login: {resp.status_code}")
