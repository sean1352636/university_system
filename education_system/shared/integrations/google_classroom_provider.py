"""Google Classroom LMS provider implementation.

Uses the Google Classroom API v1 via ``google-api-python-client``.
OAuth2 credentials are loaded from a service-account JSON file or an
OAuth2 client-secrets file (with token refresh handled automatically).

Google Classroom API reference:
    https://developers.google.com/classroom/reference/rest
"""

from __future__ import annotations

import logging
import os
from typing import Any

from education_system.shared.integrations.lms_base import LMSProvider

logger = logging.getLogger(__name__)

# Google Classroom course state → internal status
_COURSE_STATE_MAP: dict[str, str] = {
    "ACTIVE": "active",
    "ARCHIVED": "archived",
    "PROVISIONED": "unpublished",
    "DECLINED": "archived",
    "SUSPENDED": "inactive",
}

# Google Classroom submission state → rough normalisation
_SUBMISSION_STATE_MAP: dict[str, str] = {
    "NEW": "new",
    "CREATED": "draft",
    "TURNED_IN": "submitted",
    "RETURNED": "graded",
    "RECLAIMED_BY_STUDENT": "resubmit",
}

_SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.students",
    "https://www.googleapis.com/auth/classroom.coursework.me",
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
]


def _build_service(credentials_json: str):
    """Build and return an authenticated Google Classroom API service object.

    Supports both service-account JSON files (``type == service_account``)
    and OAuth2 authorised-user credential files (standard ``credentials.json``
    downloaded from the Google Cloud Console).  For authorised-user files a
    cached token is stored alongside the credentials file as ``token.json``.

    Args:
        credentials_json: Absolute path to the credentials JSON file.

    Returns:
        A ``googleapiclient.discovery.Resource`` for the Classroom API.

    Raises:
        ImportError: If the Google client libraries are not installed.
        FileNotFoundError: If the credentials file does not exist.
        ValueError: If the credentials file format is not recognised.
    """
    try:
        from googleapiclient.discovery import build  # type: ignore
        import google.oauth2.credentials as oauth2_creds
        import google.oauth2.service_account as sa_creds
        from google.auth.transport.requests import Request  # type: ignore
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Google API client libraries are required for Google Classroom "
            "integration.  Install them with:\n"
            "  pip install google-api-python-client google-auth google-auth-oauthlib"
        ) from exc

    import json

    if not os.path.isfile(credentials_json):
        raise FileNotFoundError(
            f"Google credentials file not found: {credentials_json}"
        )

    with open(credentials_json) as fh:
        cred_data = json.load(fh)

    cred_type = cred_data.get("type", "")

    if cred_type == "service_account":
        credentials = sa_creds.Credentials.from_service_account_file(
            credentials_json, scopes=_SCOPES
        )
    elif cred_type in ("authorized_user", ""):
        # Token file lives next to the credentials file
        token_path = os.path.join(
            os.path.dirname(credentials_json), "token.json"
        )
        credentials = None

        if os.path.isfile(token_path):
            credentials = oauth2_creds.Credentials.from_authorized_user_file(
                token_path, _SCOPES
            )

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_json, _SCOPES
                )
                credentials = flow.run_local_server(port=0)

            # Persist refreshed token
            with open(token_path, "w") as fh:
                fh.write(credentials.to_json())
    else:
        raise ValueError(
            f"Unrecognised Google credentials type '{cred_type}' in {credentials_json}"
        )

    return build("classroom", "v1", credentials=credentials, cache_discovery=False)


class GoogleClassroomProvider(LMSProvider):
    """Integrates with Google Classroom via the Google API v1."""

    provider_name = "Google Classroom"

    def __init__(self, credentials_json: str) -> None:
        """Initialise the Google Classroom provider.

        Args:
            credentials_json: Path to a service-account or OAuth2 client
                              credentials JSON file.
        """
        super().__init__()
        self._credentials_json = credentials_json
        self._service = None  # Lazily initialised on first use

    # ------------------------------------------------------------------ #
    # Internal helpers                                                      #
    # ------------------------------------------------------------------ #

    @property
    def service(self):
        """Return the authenticated Google Classroom API service, building it lazily."""
        if self._service is None:
            self._service = _build_service(self._credentials_json)
        return self._service

    def _list_pages(self, request_fn, *, items_key: str = "courses") -> list[dict]:
        """Iterate through all pages of a Google API list response.

        Args:
            request_fn: A callable that accepts an optional ``pageToken``
                        keyword argument and returns a Google API Request object.
            items_key: The key in the response dict that holds the item list.

        Returns:
            Flat list of all items across all pages.
        """
        items: list[dict] = []
        page_token: str | None = None

        while True:
            request = request_fn(pageToken=page_token)
            response = request.execute()
            items.extend(response.get(items_key, []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return items

    # ------------------------------------------------------------------ #
    # LMSProvider abstract method implementations                           #
    # ------------------------------------------------------------------ #

    def test_connection(self) -> dict[str, Any]:
        """Verify credentials by listing courses (page size 1)."""
        try:
            response = (
                self.service.courses()
                .list(pageSize=1)
                .execute()
            )
            return {
                "ok": True,
                "message": "Connection successful",
                "courses_found": bool(response.get("courses")),
            }
        except Exception as exc:
            logger.exception("Google Classroom connection test failed")
            return {"ok": False, "message": str(exc)}

    def sync_courses(self) -> list[dict[str, Any]]:
        """Fetch all courses via ``courses.list``."""
        raw_courses = self._list_pages(
            lambda pageToken: self.service.courses().list(
                pageSize=100,
                pageToken=pageToken,
            ),
            items_key="courses",
        )
        results: list[dict[str, Any]] = []
        for course in raw_courses:
            results.append(
                {
                    "external_id": course.get("id", ""),
                    "name": course.get("name", ""),
                    "code": course.get("section") or course.get("courseCode"),
                    "start_date": None,  # Google Classroom does not expose a start date
                    "end_date": None,
                    "status": _COURSE_STATE_MAP.get(
                        course.get("courseState", ""), "unknown"
                    ),
                    "raw": course,
                }
            )
        logger.info(
            "Google Classroom sync_courses: fetched %d courses", len(results)
        )
        return results

    def sync_students(self) -> list[dict[str, Any]]:
        """Fetch all students enrolled across every course via ``courses.students.list``."""
        courses = self.sync_courses()
        seen_ids: set[str] = set()
        results: list[dict[str, Any]] = []

        for course in courses:
            course_id = course["external_id"]
            try:
                students = self._list_pages(
                    lambda pageToken, _cid=course_id: (
                        self.service.courses()
                        .students()
                        .list(courseId=_cid, pageSize=100, pageToken=pageToken)
                    ),
                    items_key="students",
                )
            except Exception as exc:
                logger.warning(
                    "Google Classroom sync_students: failed for course %s: %s",
                    course_id, exc,
                )
                continue

            for student in students:
                profile = student.get("profile", {})
                uid = profile.get("id", "")
                if uid in seen_ids:
                    continue
                seen_ids.add(uid)
                name_obj = profile.get("name", {})
                results.append(
                    {
                        "external_id": uid,
                        "name": name_obj.get("fullName", ""),
                        "email": profile.get("emailAddress"),
                        "sis_id": None,  # Google Classroom has no built-in SIS ID
                        "raw": student,
                    }
                )

        logger.info(
            "Google Classroom sync_students: fetched %d unique students", len(results)
        )
        return results

    def sync_grades(self) -> list[dict[str, Any]]:
        """Fetch student submission grades via ``courses.courseWork.studentSubmissions.list``."""
        courses = self.sync_courses()
        results: list[dict[str, Any]] = []

        for course in courses:
            course_id = course["external_id"]

            # List all coursework items
            try:
                coursework_items = self._list_pages(
                    lambda pageToken, _cid=course_id: (
                        self.service.courses()
                        .courseWork()
                        .list(courseId=_cid, pageSize=100, pageToken=pageToken)
                    ),
                    items_key="courseWork",
                )
            except Exception as exc:
                logger.warning(
                    "Google Classroom sync_grades: failed to list coursework for "
                    "course %s: %s",
                    course_id, exc,
                )
                continue

            for cw in coursework_items:
                cw_id = cw.get("id", "")
                max_score = cw.get("maxPoints")

                try:
                    submissions = self._list_pages(
                        lambda pageToken, _cid=course_id, _cwid=cw_id: (
                            self.service.courses()
                            .courseWork()
                            .studentSubmissions()
                            .list(
                                courseId=_cid,
                                courseWorkId=_cwid,
                                pageSize=100,
                                pageToken=pageToken,
                            )
                        ),
                        items_key="studentSubmissions",
                    )
                except Exception as exc:
                    logger.warning(
                        "Google Classroom sync_grades: submissions failed for "
                        "coursework %s: %s",
                        cw_id, exc,
                    )
                    continue

                for sub in submissions:
                    results.append(
                        {
                            "external_course_id": course_id,
                            "external_student_id": sub.get("userId", ""),
                            "assignment_id": cw_id,
                            "score": sub.get("assignedGrade"),
                            "max_score": max_score,
                            "submitted_at": sub.get("updateTime"),
                            "raw": sub,
                        }
                    )

        logger.info(
            "Google Classroom sync_grades: fetched %d submission records",
            len(results),
        )
        return results

    def push_grades(
        self, course_id: str, grades: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Patch student submission grades using ``courses.courseWork.studentSubmissions.patch``.

        Each entry in ``grades`` must have:
            - ``student_id``: Google user ID (external)
            - ``assignment_id``: Google courseWork ID
            - ``score``: Numeric grade value
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
                # First, find the submission ID for this student + coursework
                list_resp = (
                    self.service.courses()
                    .courseWork()
                    .studentSubmissions()
                    .list(
                        courseId=course_id,
                        courseWorkId=assignment_id,
                        userId=student_id,
                    )
                    .execute()
                )
                submissions = list_resp.get("studentSubmissions", [])
                if not submissions:
                    errors.append(
                        f"No submission found for student={student_id} "
                        f"assignment={assignment_id}"
                    )
                    failed += 1
                    continue

                submission_id = submissions[0]["id"]
                (
                    self.service.courses()
                    .courseWork()
                    .studentSubmissions()
                    .patch(
                        courseId=course_id,
                        courseWorkId=assignment_id,
                        id=submission_id,
                        updateMask="assignedGrade,draftGrade",
                        body={
                            "assignedGrade": float(score),
                            "draftGrade": float(score),
                        },
                    )
                    .execute()
                )
                pushed += 1
            except Exception as exc:
                failed += 1
                errors.append(
                    f"student={student_id} assignment={assignment_id}: {exc}"
                )

        logger.info(
            "Google Classroom push_grades course=%s: pushed=%d failed=%d",
            course_id, pushed, failed,
        )
        return {"pushed": pushed, "failed": failed, "errors": errors}

    def pull_enrollments(self, course_id: str) -> list[dict[str, Any]]:
        """Fetch all student enrollments for a single Google Classroom course."""
        try:
            students = self._list_pages(
                lambda pageToken: (
                    self.service.courses()
                    .students()
                    .list(courseId=course_id, pageSize=100, pageToken=pageToken)
                ),
                items_key="students",
            )
        except Exception:
            logger.exception(
                "Google Classroom pull_enrollments failed for course %s", course_id
            )
            raise

        results: list[dict[str, Any]] = []
        for student in students:
            profile = student.get("profile", {})
            results.append(
                {
                    "external_course_id": course_id,
                    "external_student_id": profile.get("id", ""),
                    "status": "active",  # Google Classroom only returns active members
                    "role": "student",
                    "raw": student,
                }
            )

        logger.info(
            "Google Classroom pull_enrollments course=%s: %d records",
            course_id, len(results),
        )
        return results
