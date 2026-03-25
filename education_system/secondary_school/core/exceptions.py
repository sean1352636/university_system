"""Exception hierarchy for the Secondary School Management System."""

from education_system.shared.auth.exceptions import AuthError as _SharedAuthError
from education_system.shared.auth.exceptions import ValidationError as _SharedValidationError


class SchoolSystemError(Exception):
    """Base exception for all school system errors."""


class DatabaseError(SchoolSystemError):
    """Database operation errors."""


class AuthError(_SharedAuthError, SchoolSystemError):
    """Authentication and authorization errors."""


class ValidationError(_SharedValidationError, SchoolSystemError):
    """Input validation errors."""


class StudentError(SchoolSystemError):
    """Student-related errors."""


class SubjectError(SchoolSystemError):
    """Subject-related errors."""


class EnrollmentError(SchoolSystemError):
    """Enrollment-related errors."""


class GradeError(SchoolSystemError):
    """Grade-related errors."""


class AttendanceError(SchoolSystemError):
    """Attendance-related errors."""


class TimetableError(SchoolSystemError):
    """Timetable-related errors."""


class BehaviourError(SchoolSystemError):
    """Behaviour-related errors."""


class StaffError(SchoolSystemError):
    """Staff-related errors."""


class EmailError(SchoolSystemError):
    """Internal email/messaging errors."""


class ExamError(SchoolSystemError):
    """Exam management errors."""


class HRError(SchoolSystemError):
    """HR / staff management errors."""


class FinanceError(SchoolSystemError):
    """Finance management errors."""


class ReportError(SchoolSystemError):
    """Report generation errors."""


class SENDError(SchoolSystemError):
    """SEND management errors."""


class SafeguardingError(SchoolSystemError):
    """Safeguarding errors."""


class ParentsEveningError(SchoolSystemError):
    """Parents evening errors."""


class CoverError(SchoolSystemError):
    """Cover management errors."""


class HomeworkError(SchoolSystemError):
    """Homework/assignment errors."""


class CalendarError(SchoolSystemError):
    """School calendar errors."""


class AnnouncementError(SchoolSystemError):
    """Announcement errors."""


class UserManagementError(SchoolSystemError):
    """User management errors."""


class PastoralError(SchoolSystemError):
    """Pastoral care errors."""


class LibraryError(SchoolSystemError):
    """Library management errors."""


class MedicalError(SchoolSystemError):
    """Medical/first aid errors."""


class MealsError(SchoolSystemError):
    """School meals errors."""


class TripsError(SchoolSystemError):
    """Trips and visits errors."""


class ClubsError(SchoolSystemError):
    """Clubs/extracurricular errors."""


class DetentionError(SchoolSystemError):
    """Detention errors."""


class DocumentError(SchoolSystemError):
    """Document store errors."""


class VisitorError(SchoolSystemError):
    """Visitor management errors."""


class RoomBookingError(SchoolSystemError):
    """Room booking errors."""


class AssetError(SchoolSystemError):
    """Asset management errors."""


class SettingsError(SchoolSystemError):
    """Settings errors."""


class AdmissionsError(SchoolSystemError):
    """Admissions errors."""


class InterventionError(SchoolSystemError):
    """Intervention group errors."""


class CPDError(SchoolSystemError):
    """CPD / staff training errors."""


class TransportError(SchoolSystemError):
    """School transport errors."""


class RewardsError(SchoolSystemError):
    """Rewards and merits errors."""


class CareersError(SchoolSystemError):
    """Careers and work experience errors."""


class FormGroupError(SchoolSystemError):
    """Form group errors."""


class AuditError(SchoolSystemError):
    """Audit log errors."""


class PolicyError(SchoolSystemError):
    """Policy management errors."""


class CommunicationLogError(SchoolSystemError):
    """Communication log errors."""


class ExclusionError(SchoolSystemError):
    """Exclusion tracking errors."""


class ProgressError(SchoolSystemError):
    """Progress tracking errors."""


class SeatingPlanError(SchoolSystemError):
    """Seating plan errors."""


class ConsentError(SchoolSystemError):
    """Permissions and consent errors."""


class IncidentError(SchoolSystemError):
    """Incident log errors."""


class PayrollError(SchoolSystemError):
    """Payroll management errors."""
