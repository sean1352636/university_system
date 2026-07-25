"""Abstract base class and common helpers for LMS provider integrations.

All provider implementations (Canvas, Moodle, Google Classroom) must subclass
LMSProvider and implement every abstract method.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Grade scale identifiers used by _map_grade()
SCALE_PERCENTAGE = "percentage"   # 0–100
SCALE_LETTER = "letter"           # A*, A, B, C, D, E/U
SCALE_GPA = "gpa"                 # 0.0–4.0
SCALE_GCSE = "gcse"               # 9–1
SCALE_DEGREE = "degree"           # First, 2:1, 2:2, Third, Pass, Fail

# Mapping tables used by _map_grade()
_PERCENTAGE_TO_LETTER = [
    (90, "A*"),
    (80, "A"),
    (70, "B"),
    (60, "C"),
    (50, "D"),
    (0,  "U"),
]

_PERCENTAGE_TO_GCSE = [
    (90, 9),
    (80, 8),
    (70, 7),
    (60, 6),
    (50, 5),
    (40, 4),
    (30, 3),
    (20, 2),
    (0,  1),
]

_PERCENTAGE_TO_GPA = [
    (90, 4.0),
    (80, 3.7),
    (70, 3.3),
    (60, 3.0),
    (50, 2.7),
    (40, 2.3),
    (30, 2.0),
    (20, 1.0),
    (0,  0.0),
]

_PERCENTAGE_TO_DEGREE = [
    (70, "First"),
    (60, "2:1"),
    (50, "2:2"),
    (40, "Third"),
    (35, "Pass"),
    (0,  "Fail"),
]


class LMSProvider(ABC):
    """Abstract base class for all LMS provider integrations."""

    # Subclasses should set a human-readable name.
    provider_name: str = "Unknown LMS"

    def __init__(self) -> None:
        self._session = self._build_session()

    # ------------------------------------------------------------------ #
    # Abstract interface – every provider must implement these             #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def test_connection(self) -> dict[str, Any]:
        """Verify that the provider credentials are valid and the remote is reachable.

        Returns a dict with at minimum:
            {"ok": bool, "message": str}
        """

    @abstractmethod
    def sync_courses(self) -> list[dict[str, Any]]:
        """Fetch all courses from the remote LMS.

        Returns a list of normalised course dicts:
            {
                "external_id": str,
                "name": str,
                "code": str | None,
                "start_date": str | None,   # ISO 8601
                "end_date": str | None,
                "status": str,              # "active" | "archived" | "unpublished"
                "raw": dict,                # original provider payload
            }
        """

    @abstractmethod
    def sync_students(self) -> list[dict[str, Any]]:
        """Fetch all students known to the remote LMS.

        Returns a list of normalised student dicts:
            {
                "external_id": str,
                "name": str,
                "email": str | None,
                "sis_id": str | None,       # student information system ID
                "raw": dict,
            }
        """

    @abstractmethod
    def sync_grades(self) -> list[dict[str, Any]]:
        """Fetch grade/submission data for all available courses.

        Returns a list of normalised grade dicts:
            {
                "external_course_id": str,
                "external_student_id": str,
                "assignment_id": str | None,
                "score": float | None,
                "max_score": float | None,
                "submitted_at": str | None,
                "raw": dict,
            }
        """

    @abstractmethod
    def push_grades(
        self, course_id: str, grades: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Push grade updates for one course to the remote LMS.

        Args:
            course_id: External course identifier.
            grades: List of grade dicts.  Each must contain at minimum
                    ``student_id`` (external), ``assignment_id``, and ``score``.

        Returns:
            {"pushed": int, "failed": int, "errors": list[str]}
        """

    @abstractmethod
    def pull_enrollments(self, course_id: str) -> list[dict[str, Any]]:
        """Fetch enrollment records for a single course.

        Returns a list of normalised enrollment dicts:
            {
                "external_course_id": str,
                "external_student_id": str,
                "status": str,   # "active" | "inactive" | "invited" | "rejected"
                "role": str,     # "student" | "teacher" | "ta" | "observer"
                "raw": dict,
            }
        """

    # ------------------------------------------------------------------ #
    # Shared helpers                                                        #
    # ------------------------------------------------------------------ #

    def _build_session(self) -> requests.Session:
        """Return a requests.Session pre-configured with retry logic."""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST", "PUT", "PATCH", "DELETE"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _make_request(
        self,
        method: str,
        url: str,
        *,
        retry_on_rate_limit: bool = True,
        **kwargs: Any,
    ) -> requests.Response:
        """Make an HTTP request with retry and rate-limit back-off.

        Args:
            method: HTTP verb (GET, POST, etc.).
            url: Full URL to request.
            retry_on_rate_limit: When True, automatically sleep and retry once
                on HTTP 429 responses (in addition to the session-level retries).
            **kwargs: Forwarded verbatim to ``requests.Session.request``.

        Returns:
            The ``requests.Response`` object.

        Raises:
            requests.HTTPError: For non-2xx responses after retries are
                exhausted (only when the caller explicitly calls
                ``response.raise_for_status()``).
        """
        kwargs.setdefault("timeout", 30)
        response = self._session.request(method, url, **kwargs)

        if retry_on_rate_limit and response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 10))
            logger.warning(
                "%s rate-limited by %s; sleeping %ds before retry",
                self.provider_name,
                url,
                retry_after,
            )
            time.sleep(retry_after)
            response = self._session.request(method, url, **kwargs)

        if not response.ok:
            logger.warning(
                "%s request %s %s → HTTP %d",
                self.provider_name,
                method.upper(),
                url,
                response.status_code,
            )

        return response

    @staticmethod
    def _map_grade(
        internal_grade: float | int | str | None,
        scale: str = SCALE_PERCENTAGE,
    ) -> Any:
        """Convert an internal percentage grade to another grading scale.

        Args:
            internal_grade: Percentage value (0–100) or a string grade.
                            When ``None`` an empty string is returned.
            scale: One of the ``SCALE_*`` constants defined in this module.

        Returns:
            The converted grade value, whose type depends on the target scale.
        """
        if internal_grade is None:
            return None

        # Normalise to a float percentage if possible
        try:
            pct = float(internal_grade)
        except (TypeError, ValueError):
            # Already a string grade – return as-is for non-percentage scales
            return internal_grade

        if scale == SCALE_PERCENTAGE:
            return round(pct, 2)

        if scale == SCALE_LETTER:
            for threshold, letter in _PERCENTAGE_TO_LETTER:
                if pct >= threshold:
                    return letter
            return "U"

        if scale == SCALE_GCSE:
            for threshold, band in _PERCENTAGE_TO_GCSE:
                if pct >= threshold:
                    return band
            return 1

        if scale == SCALE_GPA:
            for threshold, gpa in _PERCENTAGE_TO_GPA:
                if pct >= threshold:
                    return gpa
            return 0.0

        if scale == SCALE_DEGREE:
            for threshold, classification in _PERCENTAGE_TO_DEGREE:
                if pct >= threshold:
                    return classification
            return "Fail"

        logger.warning("Unknown grade scale '%s'; returning raw percentage", scale)
        return pct
