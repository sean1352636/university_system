"""Exception hierarchy for the College Management System."""

from education_system.shared.auth.exceptions import AuthError as _SharedAuthError
from education_system.shared.auth.exceptions import ValidationError as _SharedValidationError
from education_system.shared.auth.exceptions import MFAError as _SharedMFAError


class CollegeSystemError(Exception):
    """Base exception for all college system errors."""


class DatabaseError(CollegeSystemError):
    """Database operation errors."""


class AuthError(_SharedAuthError, CollegeSystemError):
    """Authentication and authorization errors."""


class ValidationError(_SharedValidationError, CollegeSystemError):
    """Input validation errors."""


class StudentError(CollegeSystemError):
    """Student-related errors."""


class CourseError(CollegeSystemError):
    """Course-related errors."""


class EnrollmentError(CollegeSystemError):
    """Enrollment-related errors."""


class GradeError(CollegeSystemError):
    """Grade-related errors."""


class AttendanceError(CollegeSystemError):
    """Attendance-related errors."""


class TimetableError(CollegeSystemError):
    """Timetable-related errors."""


class AssignmentError(CollegeSystemError):
    """Assignment-related errors."""


class NotificationError(CollegeSystemError):
    """Notification-related errors."""


class MFAError(_SharedMFAError, CollegeSystemError):
    """MFA-related errors."""


class StaffError(CollegeSystemError):
    """Staff-related errors."""


class MessageError(CollegeSystemError):
    """Messaging-related errors."""


class TodoError(CollegeSystemError):
    """To-do related errors."""


class CalendarError(CollegeSystemError):
    """Calendar related errors."""


class FirstAidError(CollegeSystemError):
    """First aid related errors."""


class HelpdeskError(CollegeSystemError):
    """Helpdesk related errors."""


class ParentPortalError(CollegeSystemError):
    """Parent portal related errors."""


class SettingsError(CollegeSystemError):
    """Settings related errors."""


class AdmissionsError(CollegeSystemError):
    """Admissions related errors."""


class SafeguardingError(CollegeSystemError):
    """Safeguarding related errors."""


class BehaviourError(CollegeSystemError):
    """Behaviour related errors."""


class PastoralError(CollegeSystemError):
    """Pastoral related errors."""


class SENDError(CollegeSystemError):
    """SEND/ALS related errors."""


class ExamsError(CollegeSystemError):
    """Exams related errors."""


class ComplianceError(CollegeSystemError):
    """Compliance/funding related errors."""


class ReportsError(CollegeSystemError):
    """Reports related errors."""


class ParentsEveningError(CollegeSystemError):
    """Parents evening related errors."""


class CareersError(CollegeSystemError):
    """Careers related errors."""


class BursaryError(CollegeSystemError):
    """Bursary related errors."""


class TransportError(CollegeSystemError):
    """Transport related errors."""


class AssetsError(CollegeSystemError):
    """Assets related errors."""


class LibraryError(CollegeSystemError):
    """Library related errors."""


class StaffHRError(CollegeSystemError):
    """Staff HR related errors."""


class CoverError(CollegeSystemError):
    """Cover/substitution related errors."""


class StudentSupportError(CollegeSystemError):
    """Student support related errors."""


class FinanceError(CollegeSystemError):
    """Finance related errors."""


class RoomError(CollegeSystemError):
    """Room management related errors."""


class DepartmentError(CollegeSystemError):
    """Department related errors."""


class GroupError(CollegeSystemError):
    """Group management related errors."""


class FundingError(CollegeSystemError):
    """Funding/ILR related errors."""


class DestinationError(CollegeSystemError):
    """Destination tracking related errors."""


class CPDError(CollegeSystemError):
    """CPD (Continuing Professional Development) related errors."""


class ObservationError(CollegeSystemError):
    """Teaching observation related errors."""


class AppraisalError(CollegeSystemError):
    """Staff appraisal related errors."""


class ResourceBookingError(CollegeSystemError):
    """Resource booking related errors."""


class MarkbookError(CollegeSystemError):
    """Markbook related errors."""


class StaffWellbeingError(CollegeSystemError):
    """Staff wellbeing related errors."""


class LessonPlanError(CollegeSystemError):
    """Lesson plan related errors."""


class DataDashboardError(CollegeSystemError):
    """Data dashboard related errors."""


class AbsenceRequestError(CollegeSystemError):
    """Staff absence request related errors."""


class InterventionError(CollegeSystemError):
    """Academic intervention tracking related errors."""


class VisitorError(CollegeSystemError):
    """Visitor management related errors."""


class PolicyError(CollegeSystemError):
    """Policy management related errors."""


class GDPRError(CollegeSystemError):
    """GDPR/data protection related errors."""


class QualityAssuranceError(CollegeSystemError):
    """Quality assurance related errors."""


class BulkOperationError(CollegeSystemError):
    """Bulk operation related errors."""


class EmergencyError(CollegeSystemError):
    """Emergency management related errors."""


class AcademicYearError(CollegeSystemError):
    """Academic year management related errors."""


class KPIDashboardError(CollegeSystemError):
    """KPI dashboard related errors."""


class AuditReportError(CollegeSystemError):
    """Audit report related errors."""


class UserManagementError(CollegeSystemError):
    """User management related errors."""


class PortfolioError(CollegeSystemError):
    """Student portfolio related errors."""


class StudyPlannerError(CollegeSystemError):
    """Study planner related errors."""


class EnrichmentError(CollegeSystemError):
    """Enrichment activities related errors."""


class PeerMentoringError(CollegeSystemError):
    """Peer mentoring related errors."""


class SurveyError(CollegeSystemError):
    """Survey related errors."""


class SkillsPassportError(CollegeSystemError):
    """Skills passport related errors."""


class ProgressDashboardError(CollegeSystemError):
    """Student progress dashboard related errors."""


class MealOrderingError(CollegeSystemError):
    """Meal ordering related errors."""


class PrintCreditError(CollegeSystemError):
    """Print credit related errors."""


class WorkJournalError(CollegeSystemError):
    """Work experience journal related errors."""


class AnnouncementError(CollegeSystemError):
    """Announcement related errors."""


class DocumentHubError(CollegeSystemError):
    """Document hub related errors."""


class AdvancedSearchError(CollegeSystemError):
    """Advanced search related errors."""


class FeedbackError(CollegeSystemError):
    """Feedback related errors."""


class AccessibilityError(CollegeSystemError):
    """Accessibility preference related errors."""


class MobileDashboardError(CollegeSystemError):
    """Mobile dashboard related errors."""


class AttachmentError(CollegeSystemError):
    """File attachment related errors."""


class ActivityFeedError(CollegeSystemError):
    """Activity feed related errors."""


class SmsEmailError(CollegeSystemError):
    """SMS/Email notification related errors."""


class MultiLanguageError(CollegeSystemError):
    """Multi-language/i18n related errors."""


class ILPError(CollegeSystemError):
    """Individual Learning Plan related errors."""


class UCASError(CollegeSystemError):
    """UCAS application related errors."""


class TLevelError(CollegeSystemError):
    """T-Level pathway related errors."""


class ApprenticeshipError(CollegeSystemError):
    """Apprenticeship related errors."""


class ValueAddedError(CollegeSystemError):
    """Value-added analysis related errors."""


class GovernanceError(CollegeSystemError):
    """Governance and board related errors."""


class DBSCheckError(CollegeSystemError):
    """DBS check related errors."""


class RiskManagementError(CollegeSystemError):
    """Risk management related errors."""


class PreventDutyError(CollegeSystemError):
    """Prevent duty related errors."""


class ComplaintError(CollegeSystemError):
    """Complaints handling related errors."""


class EqualityDiversityError(CollegeSystemError):
    """Equality and diversity related errors."""


class StaffAbsenceError(CollegeSystemError):
    """Staff absence related errors."""


class RecruitmentError(CollegeSystemError):
    """Staff recruitment related errors."""


class MarketingError(CollegeSystemError):
    """Marketing and open day related errors."""


class EarlyWarningError(CollegeSystemError):
    """Early warning system related errors."""


class SelfAssessmentError(CollegeSystemError):
    """Self-assessment and Ofsted related errors."""


class AlumniError(CollegeSystemError):
    """Alumni network related errors."""


class StudentPortalError(CollegeSystemError):
    """Student portal related errors."""


class ForumError(CollegeSystemError):
    """Discussion forum related errors."""


class InternalVerificationError(CollegeSystemError):
    """Internal verification related errors."""


class FunctionalSkillsError(CollegeSystemError):
    """Functional skills related errors."""


class StudyProgrammeError(CollegeSystemError):
    """Study programme related errors."""


class TutorialError(CollegeSystemError):
    """Tutorial system related errors."""


class StudentWellbeingError(CollegeSystemError):
    """Student wellbeing related errors."""


class StudentCouncilError(CollegeSystemError):
    """Student council related errors."""


class LettingsError(CollegeSystemError):
    """Facility lettings related errors."""


class HealthSafetyError(CollegeSystemError):
    """Health and safety related errors."""


class LetterTemplateError(CollegeSystemError):
    """Letter template related errors."""


class DisciplinaryError(CollegeSystemError):
    """Disciplinary related errors."""


class OnboardingError(CollegeSystemError):
    """Staff onboarding related errors."""


class ExpenseClaimError(CollegeSystemError):
    """Expense claim related errors."""


class BaselineAssessmentError(CollegeSystemError):
    """Baseline assessment related errors."""


class DataExportError(CollegeSystemError):
    """Data export related errors."""


class CensusILRError(CollegeSystemError):
    """Census/ILR data extraction related errors."""


class UCASExportError(CollegeSystemError):
    """UCAS data export related errors."""


class DestinationOutcomeError(CollegeSystemError):
    """Destination outcome tracking related errors."""


class IQRManagerError(CollegeSystemError):
    """Internal quality review related errors."""


class SEFBuilderError(CollegeSystemError):
    """SEF builder related errors."""


class QuestionAnalysisError(CollegeSystemError):
    """Question-level analysis related errors."""


class TargetSettingError(CollegeSystemError):
    """Target setting engine related errors."""


class CoverAgencyError(CollegeSystemError):
    """Cover agency integration related errors."""


class LettingsPortalError(CollegeSystemError):
    """Lettings portal related errors."""


class EmployerPortalError(CollegeSystemError):
    """Employer portal related errors."""
