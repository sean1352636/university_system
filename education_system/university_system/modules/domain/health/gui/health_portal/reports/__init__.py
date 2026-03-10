from .population import PopulationReportsMixin
from .vaccination import VaccinationReportsMixin
from .appointments import AppointmentReportsMixin
from .student_reports import StudentReportsMixin


class ReportsMixin(
    PopulationReportsMixin,
    VaccinationReportsMixin,
    AppointmentReportsMixin,
    StudentReportsMixin,
):
    """Mixin for health reports and analytics."""
