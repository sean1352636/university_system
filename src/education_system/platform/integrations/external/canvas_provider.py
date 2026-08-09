"""Canvas LMS provider implementation (REST API v1).

Canvas API reference: https://canvas.instructure.com/doc/api/

Authentication uses a Bearer token supplied at construction time.  All requests
go through ``LMSProvider._make_request()`` so rate-limit back-off and retries
are handled automatically.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.platform.integrations.external.lms_base import LMSProvider

logger = logging.getLogger(__name__)

# Canvas enrollment state → internal enrollment status
_ENROLLMENT_STATE_MAP: dict[str, str] = {
    "active": "active",
    "invited": "invited",
    "inactive": "inactive",
    "rejected": "rejected",
    "completed": "inactive",
    "deleted": "inactive",
}

# Canvas enrollment type → internal role
_ENROLLMENT_TYPE_MAP: dict[str, str] = {
    "StudentEnrollment": "student",
    "TeacherEnrollment": "teacher",
    "TaEnrollment": "ta",
    "ObserverEnrollment": "observer",
    "DesignerEnrollment": "designer",
}

# Canvas course workflow state → internal status
_COURSE_STATE_MAP: dict[str, str] = {
    "available": "active",
    "unpublished": "unpublished",
    "completed": "archived",
    "deleted": "archived",
}


class CanvasProvider(LMSProvider):
    """Integrates with the Canvas LMS REST API (v1)."""

    provider_name = "Canvas"

    def __init__(self, base_url: str, access_token: str) -> None:
        """Initialise the Canvas provider.

        Args:
            base_url: Root URL of the Canvas instance, e.g.
                      ``https://institution.instructure.com``.  Trailing
                      slashes are stripped automatically.
            access_token: Canvas API access token (Bearer auth).
        """
        super().__init__()
        self._base = base_url.rstrip("/")
        self._session.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                      #
    # ------------------------------------------------------------------ #

    def _url(self, path: str) -> str:
        """Build an absolute Canvas API URL from a relative path."""
        return f"{self._base}/api/v1{path}"

    def _get_paginated(self, path: str, params: dict | None = None) -> list[dict]:
        """Follow Canvas Link-header pagination and collect all pages.

        Args:
            path: API path relative to ``/api/v1``.
            params: Optional query parameters for the first request.

        Returns:
            Flattened list of all items across all pages.
        """
        params = dict(params or {})
        params.setdefault("per_page", 100)
        url: str | None = self._url(path)
        items: list[dict] = []

        while url:
            response = self._make_request("GET", url, params=params)
            response.raise_for_status()
            page = response.json()
            if isinstance(page, list):
                items.extend(page)
            else:
                items.append(page)

            # Parse the RFC 5988 Link header for the next page
            url = None
            link_header = response.headers.get("Link", "")
            for part in link_header.split(","):
                part = part.strip()
                if 'rel="next"' in part:
                    url = part.split(";")[0].strip().strip("<>")
                    params = {}  # URL already contains query params
                    break

        return items

    # ------------------------------------------------------------------ #
    # LMSProvider abstract method implementations                           #
    # ------------------------------------------------------------------ #

    def test_connection(self) -> dict[str, Any]:
        """Verify credentials by fetching the authenticated user's profile."""
        try:
            response = self._make_request("GET", self._url("/users/self"))
            if response.ok:
                data = response.json()
                return {
                    "ok": True,
                    "message": "Connection successful",
                    "user": data.get("name", "unknown"),
                    "canvas_id": data.get("id"),
                }
            return {
                "ok": False,
                "message": f"Canvas returned HTTP {response.status_code}",
            }
        except Exception as exc:
            logger.exception("Canvas connection test failed")
            return {"ok": False, "message": str(exc)}

    def sync_courses(self) -> list[dict[str, Any]]:
        """Fetch all courses the token user can access."""
        raw_courses = self._get_paginated(
            "/courses",
            {"include[]": ["term", "course_code"], "state[]": ["available", "unpublished", "completed"]},
        )
        results: list[dict[str, Any]] = []
        for course in raw_courses:
            results.append(
                {
                    "external_id": str(course.get("id", "")),
                    "name": course.get("name", ""),
                    "code": course.get("course_code"),
                    "start_date": course.get("start_at"),
                    "end_date": course.get("end_at"),
                    "status": _COURSE_STATE_MAP.get(
                        course.get("workflow_state", ""), "unknown"
                    ),
                    "raw": course,
                }
            )
        logger.info("Canvas sync_courses: fetched %d courses", len(results))
        return results

    def sync_students(self) -> list[dict[str, Any]]:
        """Fetch all student enrollments across every accessible course."""
        courses = self._get_paginated(
            "/courses",
            {"enrollment_type[]": ["student"], "state[]": ["available"]},
        )
        seen_ids: set[str] = set()
        results: list[dict[str, Any]] = []

        for course in courses:
            course_id = course.get("id")
            if not course_id:
                continue
            enrollments = self._get_paginated(
                f"/courses/{course_id}/enrollments",
                {"type[]": ["StudentEnrollment"], "state[]": ["active"]},
            )
            for enr in enrollments:
                user = enr.get("user", {})
                uid = str(user.get("id", ""))
                if uid in seen_ids:
                    continue
                seen_ids.add(uid)
                results.append(
                    {
                        "external_id": uid,
                        "name": user.get("name", ""),
                        "email": user.get("login_id"),
                        "sis_id": user.get("sis_user_id"),
                        "raw": user,
                    }
                )

        logger.info("Canvas sync_students: fetched %d unique students", len(results))
        return results

    def sync_grades(self) -> list[dict[str, Any]]:
        """Fetch submission data for all courses and assignments."""
        courses = self._get_paginated(
            "/courses",
            {"state[]": ["available"]},
        )
        results: list[dict[str, Any]] = []

        for course in courses:
            course_id = course.get("id")
            if not course_id:
                continue
            assignments = self._get_paginated(f"/courses/{course_id}/assignments")
            for assignment in assignments:
                assignment_id = assignment.get("id")
                if not assignment_id:
                    continue
                submissions = self._get_paginated(
                    f"/courses/{course_id}/assignments/{assignment_id}/submissions",
                    {"include[]": ["user"]},
                )
                for sub in submissions:
                    results.append(
                        {
                            "external_course_id": str(course_id),
                            "external_student_id": str(sub.get("user_id", "")),
                            "assignment_id": str(assignment_id),
                            "score": sub.get("score"),
                            "max_score": assignment.get("points_possible"),
                            "submitted_at": sub.get("submitted_at"),
                            "raw": sub,
                        }
                    )

        logger.info("Canvas sync_grades: fetched %d submission records", len(results))
        return results

    def push_grades(
        self, course_id: str, grades: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Submit grade overrides to Canvas for a given course.

        Each entry in ``grades`` must have:
            - ``student_id``: Canvas user ID (external)
            - ``assignment_id``: Canvas assignment ID
            - ``score``: Numeric score
        """
        pushed = 0
        failed = 0
        errors: list[str] = []

        for grade in grades:
            student_id = grade.get("student_id")
            assignment_id = grade.get("assignment_id")
            score = grade.get("score")

            if not all([student_id, assignment_id, score is not None]):
                errors.append(
                    f"Skipped incomplete grade record: {grade!r}"
                )
                failed += 1
                continue

            url = self._url(
                f"/courses/{course_id}/assignments/{assignment_id}"
                f"/submissions/{student_id}"
            )
            payload = {"submission": {"posted_grade": score}}
            try:
                response = self._make_request("PUT", url, json=payload)
                if response.ok:
                    pushed += 1
                else:
                    failed += 1
                    errors.append(
                        f"student={student_id} assignment={assignment_id}: "
                        f"HTTP {response.status_code}"
                    )
            except Exception as exc:
                failed += 1
                errors.append(
                    f"student={student_id} assignment={assignment_id}: {exc}"
                )

        logger.info(
            "Canvas push_grades course=%s: pushed=%d failed=%d",
            course_id, pushed, failed,
        )
        return {"pushed": pushed, "failed": failed, "errors": errors}

    def pull_enrollments(self, course_id: str) -> list[dict[str, Any]]:
        """Fetch all enrollment records for a single Canvas course."""
        raw = self._get_paginated(
            f"/courses/{course_id}/enrollments",
            {"state[]": ["active", "invited", "inactive", "completed"]},
        )
        results: list[dict[str, Any]] = []
        for enr in raw:
            results.append(
                {
                    "external_course_id": str(course_id),
                    "external_student_id": str(enr.get("user_id", "")),
                    "status": _ENROLLMENT_STATE_MAP.get(
                        enr.get("enrollment_state", ""), "unknown"
                    ),
                    "role": _ENROLLMENT_TYPE_MAP.get(enr.get("type", ""), "unknown"),
                    "raw": enr,
                }
            )
        logger.info(
            "Canvas pull_enrollments course=%s: %d records", course_id, len(results)
        )
        return results
