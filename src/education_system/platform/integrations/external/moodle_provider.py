"""Moodle LMS provider implementation (Moodle Web Services REST API).

Moodle Web Services use a single endpoint with a ``wsfunction`` query
parameter that selects the remote function.  All calls are GET or POST to
``<base_url>/webservice/rest/server.php``.

Reference: https://docs.moodle.org/dev/Web_service_API_functions
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.platform.integrations.external.lms_base import LMSProvider

logger = logging.getLogger(__name__)

# Moodle course visible flag → internal status
_COURSE_VISIBLE_MAP: dict[int, str] = {
    1: "active",
    0: "unpublished",
}

# Moodle role shortname → internal role
_ROLE_MAP: dict[str, str] = {
    "student": "student",
    "editingteacher": "teacher",
    "teacher": "teacher",
    "coursecreator": "teacher",
    "manager": "teacher",
    "ta": "ta",
    "noneditingteacher": "ta",
    "guest": "observer",
}


class MoodleProvider(LMSProvider):
    """Integrates with Moodle via its Web Services REST API."""

    provider_name = "Moodle"

    def __init__(self, base_url: str, token: str) -> None:
        """Initialise the Moodle provider.

        Args:
            base_url: Root URL of the Moodle instance, e.g.
                      ``https://moodle.institution.ac.uk``.  Trailing
                      slashes are stripped automatically.
            token: Moodle Web Services token (wstoken).
        """
        super().__init__()
        self._base = base_url.rstrip("/")
        self._endpoint = f"{self._base}/webservice/rest/server.php"
        self._token = token

    # ------------------------------------------------------------------ #
    # Internal helpers                                                      #
    # ------------------------------------------------------------------ #

    def _ws_call(
        self, wsfunction: str, params: dict[str, Any] | None = None
    ) -> Any:
        """Call a Moodle Web Services function.

        Args:
            wsfunction: The Moodle function name, e.g.
                        ``core_course_get_courses``.
            params: Additional POST parameters.

        Returns:
            Parsed JSON response (list or dict).

        Raises:
            RuntimeError: When Moodle returns an exception payload.
            requests.HTTPError: For non-2xx HTTP responses.
        """
        payload: dict[str, Any] = {
            "wstoken": self._token,
            "wsfunction": wsfunction,
            "moodlewsrestformat": "json",
        }
        if params:
            payload.update(params)

        response = self._make_request("POST", self._endpoint, data=payload)
        response.raise_for_status()
        data = response.json()

        # Moodle signals errors inside a 200 JSON payload
        if isinstance(data, dict) and data.get("exception"):
            raise RuntimeError(
                f"Moodle exception [{data.get('errorcode')}]: {data.get('message')}"
            )

        return data

    # ------------------------------------------------------------------ #
    # LMSProvider abstract method implementations                           #
    # ------------------------------------------------------------------ #

    def test_connection(self) -> dict[str, Any]:
        """Verify the token by calling core_webservice_get_site_info."""
        try:
            info = self._ws_call("core_webservice_get_site_info")
            return {
                "ok": True,
                "message": "Connection successful",
                "site": info.get("sitename", ""),
                "username": info.get("username", ""),
                "moodle_version": info.get("release", ""),
            }
        except Exception as exc:
            logger.exception("Moodle connection test failed")
            return {"ok": False, "message": str(exc)}

    def sync_courses(self) -> list[dict[str, Any]]:
        """Fetch all courses via ``core_course_get_courses``."""
        raw_courses: list[dict] = self._ws_call("core_course_get_courses") or []
        results: list[dict[str, Any]] = []
        for course in raw_courses:
            # Skip the site-level course (id == 1)
            if course.get("id") == 1:
                continue
            results.append(
                {
                    "external_id": str(course.get("id", "")),
                    "name": course.get("fullname", ""),
                    "code": course.get("shortname"),
                    "start_date": _epoch_to_iso(course.get("startdate")),
                    "end_date": _epoch_to_iso(course.get("enddate")),
                    "status": _COURSE_VISIBLE_MAP.get(
                        course.get("visible", 1), "unknown"
                    ),
                    "raw": course,
                }
            )
        logger.info("Moodle sync_courses: fetched %d courses", len(results))
        return results

    def sync_students(self) -> list[dict[str, Any]]:
        """Fetch enrolled students for all courses.

        Uses ``core_enrol_get_enrolled_users`` per course.
        """
        courses = self.sync_courses()
        seen_ids: set[str] = set()
        results: list[dict[str, Any]] = []

        for course in courses:
            course_id = course["external_id"]
            try:
                users: list[dict] = self._ws_call(
                    "core_enrol_get_enrolled_users",
                    {"courseid": course_id},
                ) or []
            except Exception as exc:
                logger.warning(
                    "Moodle sync_students: failed for course %s: %s", course_id, exc
                )
                continue

            for user in users:
                uid = str(user.get("id", ""))
                if uid in seen_ids:
                    continue
                # Only include users with a student role
                roles = user.get("roles", [])
                is_student = any(
                    r.get("shortname", "") in ("student", "")
                    for r in roles
                ) or not roles
                if not is_student:
                    continue
                seen_ids.add(uid)
                results.append(
                    {
                        "external_id": uid,
                        "name": user.get("fullname", ""),
                        "email": user.get("email"),
                        "sis_id": user.get("idnumber") or None,
                        "raw": user,
                    }
                )

        logger.info("Moodle sync_students: fetched %d unique students", len(results))
        return results

    def sync_grades(self) -> list[dict[str, Any]]:
        """Fetch assignment grades via ``mod_assign_get_grades``.

        Iterates courses, retrieves their assignment modules, then fetches
        grades for each assignment.
        """
        courses = self.sync_courses()
        results: list[dict[str, Any]] = []

        for course in courses:
            course_id = course["external_id"]
            try:
                assignments_resp = self._ws_call(
                    "mod_assign_get_assignments",
                    {"courseids[0]": course_id},
                )
            except Exception as exc:
                logger.warning(
                    "Moodle sync_grades: failed to get assignments for course %s: %s",
                    course_id, exc,
                )
                continue

            course_data = assignments_resp.get("courses", [])
            for cdata in course_data:
                for assignment in cdata.get("assignments", []):
                    assignment_id = str(assignment.get("id", ""))
                    try:
                        grades_resp = self._ws_call(
                            "mod_assign_get_grades",
                            {"assignmentids[0]": assignment_id},
                        )
                    except Exception as exc:
                        logger.warning(
                            "Moodle sync_grades: failed for assignment %s: %s",
                            assignment_id, exc,
                        )
                        continue

                    for ag in grades_resp.get("assignments", []):
                        for grade in ag.get("grades", []):
                            results.append(
                                {
                                    "external_course_id": str(course_id),
                                    "external_student_id": str(
                                        grade.get("userid", "")
                                    ),
                                    "assignment_id": assignment_id,
                                    "score": _parse_float(grade.get("grade")),
                                    "max_score": _parse_float(
                                        assignment.get("grade")
                                    ),
                                    "submitted_at": _epoch_to_iso(
                                        grade.get("timemodified")
                                    ),
                                    "raw": grade,
                                }
                            )

        logger.info("Moodle sync_grades: fetched %d grade records", len(results))
        return results

    def push_grades(
        self, course_id: str, grades: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Submit grades to Moodle using ``mod_assign_save_grade``.

        Each entry in ``grades`` must have:
            - ``student_id``: Moodle user ID (external)
            - ``assignment_id``: Moodle assignment ID
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
                errors.append(f"Skipped incomplete record: {grade!r}")
                failed += 1
                continue

            try:
                self._ws_call(
                    "mod_assign_save_grade",
                    {
                        "assignmentid": assignment_id,
                        "userid": student_id,
                        "grade": float(score),
                        "attemptnumber": -1,
                        "addattempt": 0,
                        "workflowstate": "released",
                        "applytoall": 0,
                    },
                )
                pushed += 1
            except Exception as exc:
                failed += 1
                errors.append(
                    f"student={student_id} assignment={assignment_id}: {exc}"
                )

        logger.info(
            "Moodle push_grades course=%s: pushed=%d failed=%d",
            course_id, pushed, failed,
        )
        return {"pushed": pushed, "failed": failed, "errors": errors}

    def pull_enrollments(self, course_id: str) -> list[dict[str, Any]]:
        """Fetch enrollment records for a single Moodle course."""
        try:
            users: list[dict] = self._ws_call(
                "core_enrol_get_enrolled_users",
                {"courseid": course_id},
            ) or []
        except Exception:
            logger.exception("Moodle pull_enrollments failed for course %s", course_id)
            raise

        results: list[dict[str, Any]] = []
        for user in users:
            roles = user.get("roles", [])
            primary_role = "student"
            if roles:
                shortname = roles[0].get("shortname", "student")
                primary_role = _ROLE_MAP.get(shortname, "unknown")

            results.append(
                {
                    "external_course_id": str(course_id),
                    "external_student_id": str(user.get("id", "")),
                    "status": "active" if user.get("suspended") == 0 else "inactive",
                    "role": primary_role,
                    "raw": user,
                }
            )

        logger.info(
            "Moodle pull_enrollments course=%s: %d records", course_id, len(results)
        )
        return results


# ------------------------------------------------------------------ #
# Module-level utilities                                               #
# ------------------------------------------------------------------ #

def _epoch_to_iso(epoch: Any) -> str | None:
    """Convert a Unix timestamp to an ISO 8601 string, or return None."""
    if not epoch:
        return None
    try:
        import datetime
        return datetime.datetime.utcfromtimestamp(int(epoch)).isoformat() + "Z"
    except (TypeError, ValueError, OSError):
        return None


def _parse_float(value: Any) -> float | None:
    """Safely parse a float from a value that may be a string or None."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
