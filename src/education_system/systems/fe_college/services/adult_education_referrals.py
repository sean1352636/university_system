"""The college's learners for the platform's outgoing boards: referrals to
Adult Education (``adult_education_applications``) and requests to the
Training Provider (``training_provider_requests``)."""

from __future__ import annotations

from education_system.systems.fe_college.services import student_service

SOURCE_SYSTEM = "fe_college"


def referable_learners() -> list[tuple[str, str]]:
    """``[(student_id, label), ...]`` - every learner not withdrawn (a
    completed learner may still be referred on to a community course)."""
    return [(s.student_id, f"{s.full_name} ({s.student_id}, {s.status})")
            for s in student_service.search("")
            if (s.status or "") != "withdrawn"]


__all__ = ["SOURCE_SYSTEM", "referable_learners"]
