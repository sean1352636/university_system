
from education_system.systems.university.infrastructure.i18n import get_text as _t
from . import *  # shared compatibility dependencies

class SessionMixin:
        def __init__(self, root, auth=None):
            """Function 1: Initialize the Dentist GUI."""
            self.root = root
            self._is_embedded = not isinstance(root, (tk.Tk, tk.Toplevel))
            self.auth = auth

            # Try to get auth from shared context if not provided
            if self.auth is None and AUTH_AVAILABLE and get_auth:
                self.auth = get_auth()

            # Check authentication
            if not self._check_authentication():
                return
            # The clinic keys its patient record on the login (username);
            # billing uses the student number that login belongs to
            # (users.student_id), resolved once here.
            self.user_id = self.current_user.get('username', 'unknown')
            from education_system.systems.university.domains.health.domain.health.dentist.services.dentist_core import (
                billing_student_id,
            )
            self._billing_student_id = self.current_user.get('student_id') or billing_student_id(self.user_id)
            self.user_role = self.current_user.get('role', 'student')
            self.user_email = self.current_user.get('email', '')

            # If email not in current_user, fetch from database
            if not self.user_email:
                self.user_email = self._get_user_email()

            self.current_report = None
            self.patient = None
            self._init_database()
            self._load_patient()
            self.create_widgets()

        def _get_user_email(self) -> str:
            """Fetch user email from the users table."""
            try:
                from education_system.systems.university.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT email FROM users WHERE username = ?",
                        (self.user_id,)
                    )
                    row = cursor.fetchone()
                    if row and row[0]:
                        return row[0]
            except Exception as e:
                print(f"Error fetching user email: {e}")
            return ''

        def _check_authentication(self):
            """Check if user is authenticated. Returns True if logged in, False otherwise."""
            if not self.auth:
                self._refuse(_t('gui.pastoral.health.health_portal.dentist.session.dialogs.you_must_be_logged_in_to_access_the_dentist_module_please_log_in', default="You must be logged in to access the Dentist module.\n\n"
                    "Please log in through the main GUI first."))
                return False

            # Check if using dummy auth (fallback when no real auth is configured)
            if _DummyAuth is not None and isinstance(self.auth, _DummyAuth):
                self._refuse(_t('gui.pastoral.health.health_portal.dentist.session.dialogs.you_must_be_logged_in_to_access_the_dentist_module_please_launch', default="You must be logged in to access the Dentist module.\n\n"
                    "Please launch this module from the main GUI after logging in."))
                return False

            if not hasattr(self.auth, 'current_user') or not self.auth.current_user:
                self._refuse(_t('gui.pastoral.health.health_portal.dentist.session.dialogs.you_are_not_currently_logged_in_please_log_in_through_the_main_g', default="You are not currently logged in.\n\n"
                    "Please log in through the main GUI to access this module."))
                return False

            # Store current user info
            self.current_user = self.auth.current_user
            return True

        def _refuse(self, message):
            """Tell the user they can't use the clinic. A window of its own
            is closed; embedded in the Health Portal, the message is shown in
            the portal's content area instead — that frame belongs to the
            portal, and destroying it broke every other portal screen."""
            if self._is_embedded:
                try:
                    ttk.Label(self.root, text=message, justify="left", padding=30,
                              font=("Arial", 11)).grid(row=0, column=0, sticky="nw")
                except tk.TclError:
                    pass
                return
            messagebox.showerror(_t("dentist.window_title"), message)
            try:
                self.root.destroy()
            except tk.TclError:
                pass

        def return_to_homescreen(self):
            """Function 4: Close window."""
            self.root.destroy()
