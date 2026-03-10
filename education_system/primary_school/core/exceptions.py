"""Exception hierarchy for the Primary School Management System."""


class SchoolSystemError(Exception):
    """Base exception for the primary school system."""


# ── Academics ─────────────────────────────────────────────────────────────
class PupilError(SchoolSystemError):
    """Error related to pupil operations."""

class SubjectError(SchoolSystemError):
    """Error related to subject operations."""

class ClassError(SchoolSystemError):
    """Error related to class/form operations."""

class AssessmentError(SchoolSystemError):
    """Error related to assessment operations."""

class AttendanceError(SchoolSystemError):
    """Error related to attendance operations."""

class TimetableError(SchoolSystemError):
    """Error related to timetable operations."""

class HomeworkError(SchoolSystemError):
    """Error related to homework operations."""

class SATsError(SchoolSystemError):
    """Error related to SATs operations."""

class PhonicsError(SchoolSystemError):
    """Error related to phonics screening operations."""

class ReadingRecordError(SchoolSystemError):
    """Error related to reading record operations."""

class ProgressError(SchoolSystemError):
    """Error related to progress tracking operations."""


# ── Pastoral care ─────────────────────────────────────────────────────────
class BehaviourError(SchoolSystemError):
    """Error related to behaviour operations."""

class RewardsError(SchoolSystemError):
    """Error related to rewards operations."""

class SafeguardingError(SchoolSystemError):
    """Error related to safeguarding operations."""

class SENDError(SchoolSystemError):
    """Error related to SEND operations."""

class PastoralError(SchoolSystemError):
    """Error related to pastoral operations."""


# ── Staff ─────────────────────────────────────────────────────────────────
class StaffError(SchoolSystemError):
    """Error related to staff operations."""

class HRError(SchoolSystemError):
    """Error related to HR operations."""

class CPDError(SchoolSystemError):
    """Error related to CPD operations."""

class CoverError(SchoolSystemError):
    """Error related to cover operations."""


# ── Admin ─────────────────────────────────────────────────────────────────
class UserManagementError(SchoolSystemError):
    """Error related to user management operations."""

class SettingsError(SchoolSystemError):
    """Error related to settings operations."""

class AdmissionsError(SchoolSystemError):
    """Error related to admissions operations."""

class FinanceError(SchoolSystemError):
    """Error related to finance operations."""

class AuditError(SchoolSystemError):
    """Error related to audit log operations."""

class PolicyError(SchoolSystemError):
    """Error related to policy operations."""

class DocumentError(SchoolSystemError):
    """Error related to document operations."""


# ── Pupil life ────────────────────────────────────────────────────────────
class ClubsError(SchoolSystemError):
    """Error related to clubs operations."""

class MealsError(SchoolSystemError):
    """Error related to meals operations."""

class TransportError(SchoolSystemError):
    """Error related to transport operations."""

class TripsError(SchoolSystemError):
    """Error related to trips operations."""

class LibraryError(SchoolSystemError):
    """Error related to library operations."""

class MedicalError(SchoolSystemError):
    """Error related to medical operations."""

class ClassGroupError(SchoolSystemError):
    """Error related to class group operations."""

class ConsentError(SchoolSystemError):
    """Error related to consent operations."""


# ── Communication ─────────────────────────────────────────────────────────
class EmailError(SchoolSystemError):
    """Error related to email operations."""

class NotificationError(SchoolSystemError):
    """Error related to notification operations."""

class AnnouncementError(SchoolSystemError):
    """Error related to announcement operations."""

class CalendarError(SchoolSystemError):
    """Error related to calendar operations."""

class ParentsEveningError(SchoolSystemError):
    """Error related to parents evening operations."""

class CommunicationLogError(SchoolSystemError):
    """Error related to communication log operations."""


# ── Facilities ────────────────────────────────────────────────────────────
class RoomBookingError(SchoolSystemError):
    """Error related to room booking operations."""

class AssetError(SchoolSystemError):
    """Error related to asset operations."""

class VisitorError(SchoolSystemError):
    """Error related to visitor operations."""

class IncidentError(SchoolSystemError):
    """Error related to incident operations."""


# ── Validation ────────────────────────────────────────────────────────────
class ValidationError(SchoolSystemError):
    """Error related to input validation."""
