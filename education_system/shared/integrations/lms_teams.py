"""Microsoft Teams for Education LMS integration.

Provides sync capabilities with Microsoft Teams classes, assignments,
and grades via the Microsoft Graph API.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TeamsForEducationProvider:
    """Microsoft Teams for Education integration via Graph API.

    Requires Azure AD app registration with the following permissions:
    - EduAssignments.ReadWrite
    - EduRoster.ReadWrite
    - User.Read.All

    Configuration:
        TEAMS_TENANT_ID, TEAMS_CLIENT_ID, TEAMS_CLIENT_SECRET
    """

    PROVIDER_NAME = "teams"
    DISPLAY_NAME = "Microsoft Teams for Education"

    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 base_url: str = "https://graph.microsoft.com/v1.0"):
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = base_url
        self._access_token = None
        self._token_expires = None

    def test_connection(self) -> dict:
        """Test the connection to Microsoft Graph API."""
        try:
            self._ensure_token()
            return {"status": "connected", "provider": self.PROVIDER_NAME}
        except Exception as e:
            return {"status": "error", "error": str(e), "provider": self.PROVIDER_NAME}

    def _ensure_token(self):
        """Get or refresh OAuth2 access token."""
        import urllib.request
        import urllib.parse
        import json

        if self._access_token and self._token_expires and datetime.utcnow() < self._token_expires:
            return

        token_url = f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token"
        data = urllib.parse.urlencode({
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }).encode()

        req = urllib.request.Request(token_url, data=data, method="POST")
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())

        self._access_token = result["access_token"]
        from datetime import timedelta
        self._token_expires = datetime.utcnow() + timedelta(seconds=result.get("expires_in", 3600) - 60)

    def _api_request(self, endpoint: str, method: str = "GET", data: dict | None = None) -> dict:
        """Make an authenticated request to the Graph API."""
        import urllib.request
        import json

        self._ensure_token()
        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())

    def get_classes(self) -> list[dict]:
        """Fetch all education classes from Teams."""
        result = self._api_request("/education/classes")
        return [
            {
                "id": cls["id"],
                "name": cls.get("displayName", ""),
                "description": cls.get("description", ""),
                "external_id": cls["id"],
                "provider": self.PROVIDER_NAME,
            }
            for cls in result.get("value", [])
        ]

    def get_class_members(self, class_id: str) -> list[dict]:
        """Fetch members of a Teams class."""
        result = self._api_request(f"/education/classes/{class_id}/members")
        return [
            {
                "id": member["id"],
                "name": member.get("displayName", ""),
                "email": member.get("mail", ""),
                "role": "teacher" if member.get("primaryRole") == "teacher" else "student",
            }
            for member in result.get("value", [])
        ]

    def get_assignments(self, class_id: str) -> list[dict]:
        """Fetch assignments for a Teams class."""
        result = self._api_request(f"/education/classes/{class_id}/assignments")
        return [
            {
                "id": a["id"],
                "title": a.get("displayName", ""),
                "due_date": a.get("dueDateTime", ""),
                "status": a.get("status", ""),
                "points": a.get("grading", {}).get("maxPoints"),
            }
            for a in result.get("value", [])
        ]

    def sync_grades(self, class_id: str, assignment_id: str) -> list[dict]:
        """Fetch submission grades for an assignment."""
        result = self._api_request(
            f"/education/classes/{class_id}/assignments/{assignment_id}/submissions"
        )
        grades = []
        for sub in result.get("value", []):
            if sub.get("status") == "returned":
                grades.append({
                    "student_id": sub.get("submittedBy", {}).get("user", {}).get("id"),
                    "grade": sub.get("outcomes", [{}])[0].get("points", {}).get("points") if sub.get("outcomes") else None,
                    "status": sub.get("status"),
                    "submitted_at": sub.get("submittedDateTime"),
                })
        return grades
