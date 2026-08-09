"""Academic calendar manager coordinator."""

from ._shared import *  # noqa: F401,F403
from .schema import SchemaMixin
from .trips import TripsMixin
from .maintenance import MaintenanceMixin
from .events import EventsMixin
from .periods import PeriodsMixin
from .exports import ExportsMixin
from .backup import BackupMixin


class AcademicCalendarManager(
    SchemaMixin,
    TripsMixin,
    MaintenanceMixin,
    EventsMixin,
    PeriodsMixin,
    ExportsMixin,
    BackupMixin,
):
    """Enhanced Academic Calendar Manager with all features."""

    def __init__(self, config: CalendarConfig = None, auth_manager: AuthenticationManager = None):
        self.config = config or CalendarConfig()
        self.db_manager = DatabaseManager(self.config.db_file)

        # Use the provided auth_manager (which should be the main UserAuth system)
        if auth_manager:
            self.auth_manager = auth_manager
        else:
            # Create a wrapper that uses the main auth system
            self.auth_manager = AuthenticationManager(self.db_manager)
            try:
                self.auth_manager._load_permissions()
            except Exception as e:
                logger.warning(f"Failed to load permissions in fallback auth manager: {e}")
                self.auth_manager.current_user = None
                self.auth_manager.permissions_cache = {}

        self.audit_manager = AuditManager(self.db_manager)

        # Initialize feature managers with error handling
        try:
            self.recurring_events = RecurringEventManager(self.db_manager, self.auth_manager)
            self.categories = EventCategoryManager(self.db_manager, self.auth_manager)
            self.courses = CourseManager(self.db_manager, self.auth_manager)
            self.resources = ResourceManager(self.db_manager, self.auth_manager)
            self.notifications = NotificationManager(self.db_manager, self.auth_manager)
            self.search = AdvancedSearchManager(self.db_manager, self.auth_manager)
            self.holidays = HolidayManager(self.db_manager, self.auth_manager)
            self.visualizations = DataVisualizationManager(self.db_manager, self.auth_manager)
            self.event_dependencies = EventDependencyManager(self.db_manager, self.auth_manager)
            self.advanced_reporting = AdvancedReportingManager(self.db_manager, self.auth_manager)
            self.sms_notifications = SMSNotificationManager(self.db_manager, self.auth_manager)
            self.mobile_api = None
            if FLASK_AVAILABLE:
                try:
                    from education_system.systems.university.domains.academics.domain.services.academic_calendar.mobile_api import MobileAPIManager
                    self.mobile_api = MobileAPIManager(self)
                except Exception:
                    self.mobile_api = None
            self.enhanced_visualizations = EnhancedCalendarVisualizationManager(self.db_manager, self.auth_manager)
            self.academic_deadlines = AcademicDeadlineManager(self.db_manager, self.auth_manager)
            self.batch_operations = BatchOperationsManager(self.db_manager, self.auth_manager)
            self.timezone_manager = EnhancedTimeZoneManager(self.db_manager, self.auth_manager)
        except Exception as e:
            logger.warning(f"Some feature managers failed to initialize: {e}")

        # Initialize database with proper error handling
        try:
            self._initialize_database()
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            # Try to continue with existing schema by creating minimal required tables
            try:
                self._create_minimal_tables()
                logger.info("Created minimal tables as fallback")
            except Exception as verify_error:
                logger.error(f"Minimal table creation failed: {verify_error}")
                # Don't raise here - allow the system to continue with limited functionality
                logger.warning("Calendar system running with limited functionality")

        try:
            self._create_backup_directory()
        except Exception as e:
            logger.warning(f"Could not create backup directory: {e}")
