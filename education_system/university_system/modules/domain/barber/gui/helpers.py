"""Barber Shop GUI - Helper methods mixin.

Provides authentication checks, database init, data-loading utilities,
and form-clearing helpers used across all tabs.
"""

from education_system.university_system.modules.domain.barber.gui.common import (
    tk, ttk, messagebox, logging, datetime,
    _t, log_activity,
    AUTH_AVAILABLE, get_auth, _DummyAuth,
)

logger = logging.getLogger(__name__)


class HelpersMixin:
    """Mixin providing shared helper methods for BarberGUI."""

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _check_authentication(self):
        """Check if user is authenticated. Returns True if logged in, False otherwise."""
        if not self.auth:
            messagebox.showerror(
                _t("barber.window_title"),
                "You must be logged in to access the Barber Shop module.\n\n"
                "Please log in through the main GUI first."
            )
            if self.parent:
                self.parent.destroy()
            return False

        # Check if using dummy auth (fallback when no real auth is configured)
        if _DummyAuth is not None and isinstance(self.auth, _DummyAuth):
            messagebox.showerror(
                _t("barber.window_title"),
                "You must be logged in to access the Barber Shop module.\n\n"
                "Please launch this module from the main GUI after logging in."
            )
            if self.parent:
                self.parent.destroy()
            return False

        if not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror(
                _t("barber.window_title"),
                "You are not currently logged in.\n\n"
                "Please log in through the main GUI to access this module."
            )
            if self.parent:
                self.parent.destroy()
            return False

        # Store current user info
        self.current_user = self.auth.current_user
        return True

    # ------------------------------------------------------------------
    # Database initialisation
    # ------------------------------------------------------------------

    def _init_database(self):
        """Initialize database tables."""
        from education_system.university_system.modules.domain.barber.services.barber_core import (
            init_barber_db, init_extended_barber_db
        )
        try:
            init_barber_db()
            init_extended_barber_db()
        except Exception as e:
            logger.error(f"Failed to initialize barber database: {e}")

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _get_time_slots(self) -> list:
        """Get available time slots."""
        from education_system.university_system.modules.domain.barber.services.barber_core import TIME_SLOTS
        return TIME_SLOTS

    def _get_service_types(self) -> dict:
        """Get service types."""
        from education_system.university_system.modules.domain.barber.services.barber_core import SERVICE_TYPES
        return SERVICE_TYPES

    def _load_appointments(self):
        """Load appointments into the treeview."""
        for item in self.appointments_tree.get_children():
            self.appointments_tree.delete(item)

        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import AppointmentManager
            appointments = AppointmentManager.get_todays_appointments()

            for appt in appointments:
                self.appointments_tree.insert('', tk.END, values=(
                    appt['appointment_number'],
                    appt['appointment_time'],
                    appt['customer_name'],
                    appt['service_name'],
                    appt.get('staff_name', 'Any'),
                    appt['status'],
                    appt['payment_status']
                ))
        except Exception as e:
            logger.error(f"Error loading appointments: {e}")

    def _load_services(self):
        """Load services into the treeview."""
        for item in self.services_tree.get_children():
            self.services_tree.delete(item)

        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import ServiceManager
            services = ServiceManager.get_all_services()

            service_types = self._get_service_types()
            service_list = []
            for svc in services:
                type_name = service_types.get(svc['service_type'], svc['service_type'])
                self.services_tree.insert('', tk.END, values=(
                    svc['service_id'],
                    svc['name'],
                    type_name,
                    f"{svc['duration_minutes']} min",
                    f"£{svc['price']:.2f}"
                ))
                service_list.append(f"{svc['service_id']}: {svc['name']} (£{svc['price']:.2f})")

            self.appt_service_combo['values'] = service_list

        except Exception as e:
            logger.error(f"Error loading services: {e}")

    def _load_staff(self):
        """Load staff into the treeview."""
        for item in self.staff_tree.get_children():
            self.staff_tree.delete(item)

        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import StaffManager
            staff = StaffManager.get_all_staff()

            staff_list = ['Any']
            for s in staff:
                status = 'Active' if s.get('is_active', 1) else 'Inactive'
                self.staff_tree.insert('', tk.END, values=(
                    s['staff_id'],
                    s['name'],
                    s.get('employee_id', ''),
                    s.get('specialties', ''),
                    status
                ))
                staff_list.append(f"{s['staff_id']}: {s['name']}")

            self.appt_staff_combo['values'] = staff_list
            self.appt_staff_combo.set('Any')

        except Exception as e:
            logger.error(f"Error loading staff: {e}")

    def _load_customers(self):
        """Load customers into the customers tree."""
        for item in self.customers_tree.get_children():
            self.customers_tree.delete(item)
        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import CustomerManager
            customers = CustomerManager.get_all_customers()
            for cust in customers:
                self.customers_tree.insert('', tk.END, values=(
                    cust['customer_id'], cust['name'], cust.get('email', ''),
                    cust.get('phone', ''), cust.get('visit_count', 0),
                    cust.get('last_visit', 'N/A'),
                    'Yes' if cust.get('is_favorite') else 'No'
                ))
        except Exception as e:
            logger.error(f"Error loading customers: {e}")

    # ------------------------------------------------------------------
    # Form-clearing helpers
    # ------------------------------------------------------------------

    def _clear_appointment_form(self):
        """Clear appointment form."""
        self.appt_service_combo.set("")
        self.appt_staff_combo.set("Any")
        self.appt_time_combo.set("")

    def _clear_service_form(self):
        """Clear service form."""
        self.service_name_var.set("")
        self.service_type_combo.set("")
        self.service_duration_var.set("30")
        self.service_price_var.set("")
        self.service_desc_text.delete("1.0", tk.END)

    def _clear_staff_form(self):
        """Clear staff form."""
        self.staff_name_var.set("")
        self.staff_emp_id_var.set("")
        self.staff_specialties_var.set("")
        self.staff_phone_var.set("")
        self.staff_email_var.set("")
