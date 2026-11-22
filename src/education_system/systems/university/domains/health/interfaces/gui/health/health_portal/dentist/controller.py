from .session import SessionMixin
from .widgets.toolbar import ToolbarMixin
from .widgets.patient_summary import PatientSummaryMixin
from .widgets.data_table import DataTableMixin
from .tabs.appointments import AppointmentsTabMixin
from .tabs.treatments import TreatmentsTabMixin
from .tabs.patient_records import PatientRecordsTabMixin
from .tabs.administration import AdministrationTabMixin
from .tabs.payments_refunds import PaymentsRefundsTabMixin
from .dialogs.payment_method import PaymentMethodDialogMixin
from .dialogs.refund_method import RefundMethodDialogMixin
from .exports.treatments_csv import TreatmentExportMixin
from .exports.payments_csv import PaymentExportMixin
from education_system.systems.university.domains.health.domain.health.dentist.services.patients import PatientServiceMixin
from education_system.systems.university.domains.health.domain.health.dentist.services.appointments import AppointmentServiceMixin
from education_system.systems.university.domains.health.domain.health.dentist.services.treatments import TreatmentServiceMixin
from education_system.systems.university.domains.health.domain.health.dentist.services.prescriptions import PrescriptionServiceMixin
from education_system.systems.university.domains.health.domain.health.dentist.services.payments import PaymentServiceMixin
from education_system.systems.university.domains.health.domain.health.dentist.services.refunds import RefundServiceMixin
from education_system.systems.university.domains.health.domain.health.dentist.services.reports import ReportServiceMixin
from education_system.systems.university.domains.health.domain.health.dentist.services.notifications import NotificationServiceMixin

class DentistGUI(SessionMixin, ToolbarMixin, PatientSummaryMixin, DataTableMixin, AppointmentsTabMixin, TreatmentsTabMixin, PatientRecordsTabMixin, AdministrationTabMixin, PaymentsRefundsTabMixin, PaymentMethodDialogMixin, RefundMethodDialogMixin, TreatmentExportMixin, PaymentExportMixin, PatientServiceMixin, AppointmentServiceMixin, TreatmentServiceMixin, PrescriptionServiceMixin, PaymentServiceMixin, RefundServiceMixin, ReportServiceMixin, NotificationServiceMixin):
    """Coordinator retaining the original public GUI class."""
    pass
