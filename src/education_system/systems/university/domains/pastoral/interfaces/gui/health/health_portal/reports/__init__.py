from education_system.systems.university.domains.pastoral.interfaces.gui.health.health_portal.reports.population import PopulationReportsMixin
from education_system.systems.university.domains.pastoral.interfaces.gui.health.health_portal.reports.vaccination import VaccinationReportsMixin
from education_system.systems.university.domains.pastoral.interfaces.gui.health.health_portal.reports.appointments import AppointmentReportsMixin
from education_system.systems.university.domains.pastoral.interfaces.gui.health.health_portal.reports.student_reports import StudentReportsMixin


class ReportsMixin(
    PopulationReportsMixin,
    VaccinationReportsMixin,
    AppointmentReportsMixin,
    StudentReportsMixin,
):
    """Mixin for health reports and analytics."""
