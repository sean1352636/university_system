"""Exception hierarchy for the Primary School Management System.

The hierarchy mirrors the domain structure so that callers can catch at
whatever granularity makes sense — a single exception, a whole category
(e.g. ``except AcademicError``), or everything (``except SchoolSystemError``).
"""

from __future__ import annotations

from typing import Any


# ── Base ─────────────────────────────────────────────────────────────────


class SchoolSystemError(Exception):
    """Base exception for the primary school system.

    All domain exceptions inherit from this so a single ``except
    SchoolSystemError`` clause catches every school-related error.

    Parameters
    ----------
    message:
        Human-readable description.
    detail:
        Optional structured context (IDs, field names, etc.) that
        error handlers and loggers can inspect without parsing the
        message string.
    """

    def __init__(self, message: str = "", *, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.detail: dict[str, Any] = detail or {}


class DatabaseError(SchoolSystemError):
    """Error originating from the database layer (connection, constraint, etc.)."""


class SchoolValidationError(SchoolSystemError):
    """Error related to input validation.

    Named ``SchoolValidationError`` to avoid conflicts with similarly
    named exceptions in Pydantic, Marshmallow, Django, etc.
    """


# Backward-compatible alias — prefer ``SchoolValidationError`` in new code.
ValidationError = SchoolValidationError


# ── Academics ────────────────────────────────────────────────────────────


class AcademicError(SchoolSystemError):
    """Base for all academics-related errors."""


class PupilError(AcademicError):
    """Error related to pupil operations."""


class SubjectError(AcademicError):
    """Error related to subject operations."""


class FormError(AcademicError):
    """Error related to class/form operations.

    Named ``FormError`` rather than ``ClassError`` to avoid confusion
    with the Python keyword and to match UK primary school terminology.
    """


# Backward-compatible alias — prefer ``FormError`` in new code.
ClassError = FormError


class AssessmentError(AcademicError):
    """Error related to assessment operations."""


class AttendanceError(AcademicError):
    """Error related to attendance operations."""


class TimetableError(AcademicError):
    """Error related to timetable operations."""


class HomeworkError(AcademicError):
    """Error related to homework operations."""


class SATsError(AcademicError):
    """Error related to SATs operations."""


class PhonicsError(AcademicError):
    """Error related to phonics screening operations."""


class ReadingRecordError(AcademicError):
    """Error related to reading record operations."""


class ProgressError(AcademicError):
    """Error related to progress tracking operations."""


# ── Pastoral care ────────────────────────────────────────────────────────


class PastoralCareError(SchoolSystemError):
    """Base for all pastoral-care-related errors."""


class BehaviourError(PastoralCareError):
    """Error related to behaviour operations."""


class RewardsError(PastoralCareError):
    """Error related to rewards operations."""


class SafeguardingError(PastoralCareError):
    """Error related to safeguarding operations."""


class SENDError(PastoralCareError):
    """Error related to SEND operations."""


class PastoralError(PastoralCareError):
    """Error related to general pastoral operations."""


# ── Staff ────────────────────────────────────────────────────────────────


class StaffManagementError(SchoolSystemError):
    """Base for all staff-related errors."""


class StaffError(StaffManagementError):
    """Error related to staff directory operations."""


class HRError(StaffManagementError):
    """Error related to HR operations."""


class CPDError(StaffManagementError):
    """Error related to CPD operations."""


class CoverError(StaffManagementError):
    """Error related to cover operations."""


class PayrollError(StaffManagementError):
    """Error related to payroll operations."""


# ── Admin ────────────────────────────────────────────────────────────────


class AdminError(SchoolSystemError):
    """Base for all admin-related errors."""


class UserManagementError(AdminError):
    """Error related to user management operations."""


class SettingsError(AdminError):
    """Error related to settings operations."""


class AdmissionsError(AdminError):
    """Error related to admissions operations."""


class FinanceError(AdminError):
    """Error related to finance operations."""


class AuditError(AdminError):
    """Error related to audit log operations."""


class PolicyError(AdminError):
    """Error related to policy operations."""


class DocumentError(AdminError):
    """Error related to document operations."""


# ── Pupil life ───────────────────────────────────────────────────────────


class PupilLifeError(SchoolSystemError):
    """Base for all pupil-life-related errors."""


class ClubsError(PupilLifeError):
    """Error related to clubs operations."""


class MealsError(PupilLifeError):
    """Error related to meals operations."""


class TransportError(PupilLifeError):
    """Error related to transport operations."""


class TripsError(PupilLifeError):
    """Error related to trips operations."""


class LibraryError(PupilLifeError):
    """Error related to library operations."""


class MedicalError(PupilLifeError):
    """Error related to medical operations."""


class ClassGroupError(PupilLifeError):
    """Error related to class group operations."""


class ConsentError(PupilLifeError):
    """Error related to consent operations."""


# ── Communication ────────────────────────────────────────────────────────


class CommunicationError(SchoolSystemError):
    """Base for all communication-related errors."""


class EmailError(CommunicationError):
    """Error related to email operations."""


class NotificationError(CommunicationError):
    """Error related to notification operations."""


class AnnouncementError(CommunicationError):
    """Error related to announcement operations."""


class CalendarError(CommunicationError):
    """Error related to calendar operations."""


class ParentsEveningError(CommunicationError):
    """Error related to parents evening operations."""


class CommunicationLogError(CommunicationError):
    """Error related to communication log operations."""


# ── Facilities ───────────────────────────────────────────────────────────


class FacilitiesError(SchoolSystemError):
    """Base for all facilities-related errors."""


class RoomBookingError(FacilitiesError):
    """Error related to room booking operations."""


class AssetError(FacilitiesError):
    """Error related to asset operations."""


class VisitorError(FacilitiesError):
    """Error related to visitor operations."""


class IncidentError(FacilitiesError):
    """Error related to incident operations."""


# ── Public API ───────────────────────────────────────────────────────────

__all__ = [
    # Base
    "SchoolSystemError",
    "DatabaseError",
    "SchoolValidationError",
    "ValidationError",
    # Category bases
    "AcademicError",
    "PastoralCareError",
    "StaffManagementError",
    "AdminError",
    "PupilLifeError",
    "CommunicationError",
    "FacilitiesError",
    # Academics
    "PupilError",
    "SubjectError",
    "FormError",
    "ClassError",
    "AssessmentError",
    "AttendanceError",
    "TimetableError",
    "HomeworkError",
    "SATsError",
    "PhonicsError",
    "ReadingRecordError",
    "ProgressError",
    # Pastoral care
    "BehaviourError",
    "RewardsError",
    "SafeguardingError",
    "SENDError",
    "PastoralError",
    # Staff
    "StaffError",
    "HRError",
    "CPDError",
    "CoverError",
    "PayrollError",
    # Admin
    "UserManagementError",
    "SettingsError",
    "AdmissionsError",
    "FinanceError",
    "AuditError",
    "PolicyError",
    "DocumentError",
    # Pupil life
    "ClubsError",
    "MealsError",
    "TransportError",
    "TripsError",
    "LibraryError",
    "MedicalError",
    "ClassGroupError",
    "ConsentError",
    # Communication
    "EmailError",
    "NotificationError",
    "AnnouncementError",
    "CalendarError",
    "ParentsEveningError",
    "CommunicationLogError",
    # Facilities
    "RoomBookingError",
    "AssetError",
    "VisitorError",
    "IncidentError",
]
