"""API error handlers for the Primary School system."""

from flask import jsonify
import logging

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

    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        logger.warning("Validation error: %s", e)
        return jsonify({"error": "Validation Error", "message": str(e)}), 400

    @app.errorhandler(AuthError)
    def handle_auth_error(e):
        logger.warning("Auth error: %s", e)
        return jsonify({"error": "Authentication Error", "message": str(e)}), 401

    @app.errorhandler(PupilError)
    def handle_pupil_error(e):
        return jsonify({"error": "Pupil Error", "message": str(e)}), 400

    @app.errorhandler(SubjectError)
    def handle_subject_error(e):
        return jsonify({"error": "Subject Error", "message": str(e)}), 400

    @app.errorhandler(ClassError)
    def handle_class_error(e):
        return jsonify({"error": "Class Error", "message": str(e)}), 400

    @app.errorhandler(AssessmentError)
    def handle_assessment_error(e):
        return jsonify({"error": "Assessment Error", "message": str(e)}), 400

    @app.errorhandler(AttendanceError)
    def handle_attendance_error(e):
        return jsonify({"error": "Attendance Error", "message": str(e)}), 400

    @app.errorhandler(TimetableError)
    def handle_timetable_error(e):
        return jsonify({"error": "Timetable Error", "message": str(e)}), 400

    @app.errorhandler(HomeworkError)
    def handle_homework_error(e):
        return jsonify({"error": "Homework Error", "message": str(e)}), 400

    @app.errorhandler(SATsError)
    def handle_sats_error(e):
        return jsonify({"error": "SATs Error", "message": str(e)}), 400

    @app.errorhandler(PhonicsError)
    def handle_phonics_error(e):
        return jsonify({"error": "Phonics Error", "message": str(e)}), 400

    @app.errorhandler(ReadingRecordError)
    def handle_reading_record_error(e):
        return jsonify({"error": "Reading Record Error", "message": str(e)}), 400

    @app.errorhandler(ProgressError)
    def handle_progress_error(e):
        return jsonify({"error": "Progress Error", "message": str(e)}), 400

    @app.errorhandler(BehaviourError)
    def handle_behaviour_error(e):
        return jsonify({"error": "Behaviour Error", "message": str(e)}), 400

    @app.errorhandler(RewardsError)
    def handle_rewards_error(e):
        return jsonify({"error": "Rewards Error", "message": str(e)}), 400

    @app.errorhandler(SafeguardingError)
    def handle_safeguarding_error(e):
        return jsonify({"error": "Safeguarding Error", "message": str(e)}), 400

    @app.errorhandler(SENDError)
    def handle_send_error(e):
        return jsonify({"error": "SEND Error", "message": str(e)}), 400

    @app.errorhandler(PastoralError)
    def handle_pastoral_error(e):
        return jsonify({"error": "Pastoral Error", "message": str(e)}), 400

    @app.errorhandler(StaffError)
    def handle_staff_error(e):
        return jsonify({"error": "Staff Error", "message": str(e)}), 400

    @app.errorhandler(HRError)
    def handle_hr_error(e):
        return jsonify({"error": "HR Error", "message": str(e)}), 400

    @app.errorhandler(CPDError)
    def handle_cpd_error(e):
        return jsonify({"error": "CPD Error", "message": str(e)}), 400

    @app.errorhandler(CoverError)
    def handle_cover_error(e):
        return jsonify({"error": "Cover Error", "message": str(e)}), 400

    @app.errorhandler(FinanceError)
    def handle_finance_error(e):
        return jsonify({"error": "Finance Error", "message": str(e)}), 400

    @app.errorhandler(AdmissionsError)
    def handle_admissions_error(e):
        return jsonify({"error": "Admissions Error", "message": str(e)}), 400

    @app.errorhandler(PolicyError)
    def handle_policy_error(e):
        return jsonify({"error": "Policy Error", "message": str(e)}), 400

    @app.errorhandler(DocumentError)
    def handle_document_error(e):
        return jsonify({"error": "Document Error", "message": str(e)}), 400

    @app.errorhandler(ClubsError)
    def handle_clubs_error(e):
        return jsonify({"error": "Clubs Error", "message": str(e)}), 400

    @app.errorhandler(MealsError)
    def handle_meals_error(e):
        return jsonify({"error": "Meals Error", "message": str(e)}), 400

    @app.errorhandler(TransportError)
    def handle_transport_error(e):
        return jsonify({"error": "Transport Error", "message": str(e)}), 400

    @app.errorhandler(TripsError)
    def handle_trips_error(e):
        return jsonify({"error": "Trips Error", "message": str(e)}), 400

    @app.errorhandler(LibraryError)
    def handle_library_error(e):
        return jsonify({"error": "Library Error", "message": str(e)}), 400

    @app.errorhandler(MedicalError)
    def handle_medical_error(e):
        return jsonify({"error": "Medical Error", "message": str(e)}), 400

    @app.errorhandler(NotificationError)
    def handle_notification_error(e):
        return jsonify({"error": "Notification Error", "message": str(e)}), 400

    @app.errorhandler(AnnouncementError)
    def handle_announcement_error(e):
        return jsonify({"error": "Announcement Error", "message": str(e)}), 400

    @app.errorhandler(CalendarError)
    def handle_calendar_error(e):
        return jsonify({"error": "Calendar Error", "message": str(e)}), 400

    @app.errorhandler(ParentsEveningError)
    def handle_parents_evening_error(e):
        return jsonify({"error": "Parents Evening Error", "message": str(e)}), 400

    @app.errorhandler(RoomBookingError)
    def handle_room_booking_error(e):
        return jsonify({"error": "Room Booking Error", "message": str(e)}), 400

    @app.errorhandler(AssetError)
    def handle_asset_error(e):
        return jsonify({"error": "Asset Error", "message": str(e)}), 400

    @app.errorhandler(VisitorError)
    def handle_visitor_error(e):
        return jsonify({"error": "Visitor Error", "message": str(e)}), 400

    @app.errorhandler(IncidentError)
    def handle_incident_error(e):
        return jsonify({"error": "Incident Error", "message": str(e)}), 400

    @app.errorhandler(SchoolSystemError)
    def handle_system_error(e):
        logger.error("System error: %s", e)
        return jsonify({"error": "System Error", "message": str(e)}), 500

    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({"error": "Not Found", "message": "Resource not found."}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        return jsonify({"error": "Method Not Allowed", "message": str(e)}), 405

    @app.errorhandler(500)
    def handle_internal_error(e):
        logger.error("Internal server error: %s", e)
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500
