"""API error handlers for the Primary School system."""

import logging

from education_system.shared.api.errors import register_common_error_handlers, domain_error_handler
from education_system.primary_school.core.exceptions import (
    SchoolSystemError, ValidationError,
    PupilError, SubjectError, ClassError, AssessmentError, AttendanceError,
    TimetableError, HomeworkError, SATsError, PhonicsError, ReadingRecordError,
    ProgressError, BehaviourError, RewardsError, SafeguardingError, SENDError,
    PastoralError, StaffError, HRError, CPDError, CoverError,
    UserManagementError, AdmissionsError, FinanceError,
    AuditError, PolicyError, DocumentError,
    ClubsError, MealsError, TransportError, TripsError, LibraryError,
    MedicalError, ClassGroupError, ConsentError,
    NotificationError, AnnouncementError, CalendarError,
    ParentsEveningError, CommunicationLogError,
    RoomBookingError, AssetError, VisitorError, IncidentError,
)
from education_system.shared.auth.exceptions import AuthError

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Register error handlers on the Flask app."""
    register_common_error_handlers(app)

    app.register_error_handler(ValidationError, domain_error_handler(ValidationError, "Validation Error"))
    app.register_error_handler(AuthError, domain_error_handler(AuthError, "Authentication Error", 401))
    app.register_error_handler(PupilError, domain_error_handler(PupilError, "Pupil Error"))
    app.register_error_handler(SubjectError, domain_error_handler(SubjectError, "Subject Error"))
    app.register_error_handler(ClassError, domain_error_handler(ClassError, "Class Error"))
    app.register_error_handler(AssessmentError, domain_error_handler(AssessmentError, "Assessment Error"))
    app.register_error_handler(AttendanceError, domain_error_handler(AttendanceError, "Attendance Error"))
    app.register_error_handler(TimetableError, domain_error_handler(TimetableError, "Timetable Error"))
    app.register_error_handler(HomeworkError, domain_error_handler(HomeworkError, "Homework Error"))
    app.register_error_handler(SATsError, domain_error_handler(SATsError, "SATs Error"))
    app.register_error_handler(PhonicsError, domain_error_handler(PhonicsError, "Phonics Error"))
    app.register_error_handler(ReadingRecordError, domain_error_handler(ReadingRecordError, "Reading Record Error"))
    app.register_error_handler(ProgressError, domain_error_handler(ProgressError, "Progress Error"))
    app.register_error_handler(BehaviourError, domain_error_handler(BehaviourError, "Behaviour Error"))
    app.register_error_handler(RewardsError, domain_error_handler(RewardsError, "Rewards Error"))
    app.register_error_handler(SafeguardingError, domain_error_handler(SafeguardingError, "Safeguarding Error"))
    app.register_error_handler(SENDError, domain_error_handler(SENDError, "SEND Error"))
    app.register_error_handler(PastoralError, domain_error_handler(PastoralError, "Pastoral Error"))
    app.register_error_handler(StaffError, domain_error_handler(StaffError, "Staff Error"))
    app.register_error_handler(HRError, domain_error_handler(HRError, "HR Error"))
    app.register_error_handler(CPDError, domain_error_handler(CPDError, "CPD Error"))
    app.register_error_handler(CoverError, domain_error_handler(CoverError, "Cover Error"))
    app.register_error_handler(FinanceError, domain_error_handler(FinanceError, "Finance Error"))
    app.register_error_handler(AdmissionsError, domain_error_handler(AdmissionsError, "Admissions Error"))
    app.register_error_handler(PolicyError, domain_error_handler(PolicyError, "Policy Error"))
    app.register_error_handler(DocumentError, domain_error_handler(DocumentError, "Document Error"))
    app.register_error_handler(ClubsError, domain_error_handler(ClubsError, "Clubs Error"))
    app.register_error_handler(MealsError, domain_error_handler(MealsError, "Meals Error"))
    app.register_error_handler(TransportError, domain_error_handler(TransportError, "Transport Error"))
    app.register_error_handler(TripsError, domain_error_handler(TripsError, "Trips Error"))
    app.register_error_handler(LibraryError, domain_error_handler(LibraryError, "Library Error"))
    app.register_error_handler(MedicalError, domain_error_handler(MedicalError, "Medical Error"))
    app.register_error_handler(NotificationError, domain_error_handler(NotificationError, "Notification Error"))
    app.register_error_handler(AnnouncementError, domain_error_handler(AnnouncementError, "Announcement Error"))
    app.register_error_handler(CalendarError, domain_error_handler(CalendarError, "Calendar Error"))
    app.register_error_handler(ParentsEveningError, domain_error_handler(ParentsEveningError, "Parents Evening Error"))
    app.register_error_handler(RoomBookingError, domain_error_handler(RoomBookingError, "Room Booking Error"))
    app.register_error_handler(AssetError, domain_error_handler(AssetError, "Asset Error"))
    app.register_error_handler(VisitorError, domain_error_handler(VisitorError, "Visitor Error"))
    app.register_error_handler(IncidentError, domain_error_handler(IncidentError, "Incident Error"))
    app.register_error_handler(SchoolSystemError, domain_error_handler(SchoolSystemError, "System Error", 500))
