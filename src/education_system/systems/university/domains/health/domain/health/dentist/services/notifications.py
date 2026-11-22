import csv
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog, filedialog
from datetime import datetime
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.domains.health.domain.health.dentist.services.dentist_core import PatientManager, AppointmentManager, TreatmentManager, PrescriptionManager, TransactionManager, ReportManager, init_dentist_db, TREATMENT_TYPES, DENTIST_STAFF, APPOINTMENT_SLOTS
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.dentist import EMAIL_AVAILABLE, send_email, render_template, _send_dentist_email

class NotificationServiceMixin:
        def _notify_finance_for_refund(self, user_id: str, amount: float, method: str, refund_ref: str):
            """Record refund in finance system for integration."""
            refund_row_id = None
            try:
                from education_system.systems.university.infrastructure.database.db import transaction as db_transaction
                from datetime import datetime
                with db_transaction() as conn:
                    # Record refund in unified_refunds table
                    try:
                        cur = conn.execute('''
                            INSERT INTO unified_refunds
                            (source_type, student_id, refund_reference, department,
                             amount, refund_method, refund_date, processed_by, notes, reference_type, status)
                            VALUES ('dentist', ?, ?, 'Dentist', ?, ?, ?, ?, 'Dental Clinic Payment Refund', 'payment', 'processed')
                        ''', (
                            user_id,
                            refund_ref,
                            amount,
                            method.lower().replace(' ', '_'),
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            self.user_id,
                        ))
                        refund_row_id = cur.lastrowid
                        print(f"[Dentist] Refund recorded in finance system: {refund_ref}")
                    except Exception as e:
                        print(f"[Dentist] Error recording refund in finance system: {e}")
                        import traceback
                        traceback.print_exc()
            except Exception as e:
                print(f"Error notifying finance system: {e}")

            # Auto-post to GL (cash has moved). Never raises.
            if refund_row_id is not None:
                try:
                    from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
                    notify_ledger('refund', refund_row_id, posted_by=self.user_id or 'dentist')
                except Exception as _e:
                    import logging
                    logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

