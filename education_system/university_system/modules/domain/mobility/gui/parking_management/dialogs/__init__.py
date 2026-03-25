"""Dialog classes for parking management GUI."""
from education_system.university_system.modules.domain.mobility.gui.parking_management.dialogs.permit_dialog import PermitDialog
from education_system.university_system.modules.domain.mobility.gui.parking_management.dialogs.vehicle_dialog import VehicleDialog
from education_system.university_system.modules.domain.mobility.gui.parking_management.dialogs.violation_dialog import ViolationDialog
from education_system.university_system.modules.domain.mobility.gui.parking_management.dialogs.lot_dialog import LotDialog
from education_system.university_system.modules.domain.mobility.gui.parking_management.dialogs.export_dialog import ExportDialog
from education_system.university_system.modules.domain.mobility.gui.parking_management.dialogs.payment_dialog import PaymentDialog
from education_system.university_system.modules.domain.mobility.gui.parking_management.dialogs.refund_dialog import RefundDialog

__all__ = [
    'PermitDialog', 'VehicleDialog', 'ViolationDialog', 'LotDialog',
    'ExportDialog', 'PaymentDialog', 'RefundDialog',
]
