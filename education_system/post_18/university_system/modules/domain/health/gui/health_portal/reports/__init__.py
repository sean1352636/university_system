from education_system.post_18.university_system.modules.domain.health.gui.health_portal.reports.population import PopulationReportsMixin
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.reports.vaccination import VaccinationReportsMixin
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.reports.appointments import AppointmentReportsMixin
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.reports.student_reports import StudentReportsMixin


class ReportsMixin(
    PopulationReportsMixin,
    VaccinationReportsMixin,
    AppointmentReportsMixin,
    StudentReportsMixin,
):
    """Mixin for health reports and analytics."""
