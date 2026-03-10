# University GUI – authentication-related helpers (post-login only).
#
# Login is handled exclusively by the universal login in
# education_system/shared/gui/login_gui.py.  This module only contains
# logout, session management, MFA settings, system switching, etc.

import tkinter as tk
from tkinter import ttk, messagebox
import os
import logging
from education_system.university_system.modules.shared.utils.i18n import get_text as _t, get_current_language

# Check for GUI language selector availability
try:
    from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector
    GUI_LANG_SELECTOR_AVAILABLE = True
except ImportError:
    GUI_LANG_SELECTOR_AVAILABLE = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def logout_user(self):
    """Logout current user and return to universal login."""
    if self.auth.current_user:
        username = self.auth.current_user['username']

        # Revoke all sessions if using EnhancedAuth
        try:
            from education_system.university_system.infrastructure.auth.enhanced_auth import EnhancedAuth
            if isinstance(self.auth, EnhancedAuth):
                user_id = self.auth.current_user.get('id')
                if user_id:
                    self.auth.logout_and_revoke_remember_me(user_id)
        except Exception as e:
            logger.debug(f"Could not revoke remember me tokens: {e}")

        self.auth.logout()
        self.update_status()
        messagebox.showinfo(_t("gui.login.logged_out"), _t("gui.login.goodbye").format(username=username))

        # Return to the universal login screen
        from education_system.switch import request_logout
        request_logout()
        self._cancel_timers()
        self.root.destroy()


def toggle_login_logout(self):
    """Logout the current user (login is handled by the universal login)."""
    self.logout_user()


def update_login_logout_button(self):
    """Update the login/logout button text."""
    if hasattr(self, 'login_logout_btn'):
        self.login_logout_btn.config(text=_t("common.logout"))


# ---------------------------------------------------------------------------
# Password
# ---------------------------------------------------------------------------

def show_change_password(self):
    """Show change password dialog"""
    if not self.auth.current_user:
        messagebox.showerror(_t("common.error"), _t("gui.password.must_be_logged_in"))
        return

    password_window = tk.Toplevel(self.root)
    password_window.title(_t("gui.password.change_password"))
    password_window.geometry("400x250")
    password_window.transient(self.root)
    password_window.grab_set()

    main_frame = ttk.Frame(password_window, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text=_t("gui.password.current_password") + ":").grid(row=0, column=0, sticky=tk.W, pady=5)
    current_entry = ttk.Entry(main_frame, show="*", width=30)
    current_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

    ttk.Label(main_frame, text=_t("gui.password.new_password") + ":").grid(row=1, column=0, sticky=tk.W, pady=5)
    new_entry = ttk.Entry(main_frame, show="*", width=30)
    new_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

    ttk.Label(main_frame, text=_t("gui.password.confirm_password") + ":").grid(row=2, column=0, sticky=tk.W, pady=5)
    confirm_entry = ttk.Entry(main_frame, show="*", width=30)
    confirm_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

    status_label = ttk.Label(main_frame, text="", foreground="red")
    status_label.grid(row=3, column=0, columnspan=2, pady=10)

    def change_password():
        current = current_entry.get()
        new = new_entry.get()
        confirm = confirm_entry.get()

        if not all([current, new, confirm]):
            status_label.config(text=_t("gui.password.all_fields_required"))
            return

        if new != confirm:
            status_label.config(text=_t("gui.password.passwords_dont_match"))
            return

        if self.auth.change_password(self.auth.current_user['username'], current, new):
            password_window.destroy()
            messagebox.showinfo(_t("common.success"), _t("gui.password.password_changed"))
        else:
            status_label.config(text=_t("gui.password.current_password_incorrect"))

    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=4, column=0, columnspan=2, pady=10)

    ttk.Button(button_frame, text=_t("gui.password.change_password_button"), command=change_password).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.cancel"), command=password_window.destroy).pack(side=tk.LEFT, padx=5)

    current_entry.focus()


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def check_session_timer(self):
    """Check session validity periodically"""
    try:
        if not self.root.winfo_exists():
            return

        if self.auth.current_user:
            if hasattr(self.auth, 'check_session') and not self.auth.check_session():
                messagebox.showwarning(_t("gui.session.expired"), _t("gui.session.expired_message"))
                self.auth.logout()
                # Return to universal login
                from education_system.switch import request_logout
                request_logout()
                self._cancel_timers()
                self.root.destroy()
    except Exception as e:
        print(f"Session check error: {e}")

    # Schedule next check only if window still exists
    try:
        if self.root.winfo_exists():
            self._session_timer_id = self.root.after(60000, self.check_session_timer)
    except Exception:
        pass  # Window destroyed, don't schedule


# ---------------------------------------------------------------------------
# System switching
# ---------------------------------------------------------------------------

def switch_to_cli(self):
    """Switch to CLI mode by launching the CLI main function"""
    if messagebox.askyesno(_t("gui.switch_to_cli"), _t("gui.switch_to_cli_confirm")):
        try:
            import time
            import gc

            # Close database connections before switching
            try:
                from education_system.university_system.infrastructure.database.db import _connection_pool, _pool_lock
                with _pool_lock:
                    if _connection_pool is not None:
                        _connection_pool.close_all()
            except Exception:
                pass

            # Close auth database connections if any
            try:
                if hasattr(self, 'auth') and self.auth:
                    if hasattr(self.auth, 'db_manager') and self.auth.db_manager:
                        if hasattr(self.auth.db_manager, 'conn') and self.auth.db_manager.conn:
                            self.auth.db_manager.conn.close()
            except Exception:
                pass

            # Reset shared_context auth and clear initialization flags
            try:
                from education_system.university_system.infrastructure.shared_context import set_auth as reset_shared_auth
                from education_system.university_system.infrastructure.auth import UserAuth
                fresh_auth = UserAuth()
                reset_shared_auth(fresh_auth)
            except Exception:
                pass

            gc.collect()
            time.sleep(0.2)

            from education_system.university_system.modules.shared.cli.cli_main import main as cli_main
            self.root.withdraw()
            self.root.quit()
            cli_main()
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("gui.errors.failed_switch_cli", error=str(e)))
            self.root.deiconify()


def switch_system(self):
    """Show a dialog to switch to another education system."""
    dlg = tk.Toplevel(self.root)
    dlg.title("Switch System")
    dlg.geometry("400x350")
    dlg.resizable(False, False)
    dlg.transient(self.root)
    dlg.grab_set()

    dlg.update_idletasks()
    x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
    y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
    dlg.geometry(f"+{x}+{y}")

    tk.Label(
        dlg, text="Switch to another system",
        font=("Helvetica", 14, "bold"), pady=16,
    ).pack()

    tk.Label(
        dlg, text="Choose a system to launch:",
        font=("Helvetica", 11), pady=4,
    ).pack()

    btn_style = {"font": ("Helvetica", 12), "width": 28, "height": 2,
                 "cursor": "hand2", "relief": tk.FLAT}

    btn_frame = tk.Frame(dlg)
    btn_frame.pack(expand=True, pady=8)

    def _pick(system_name):
        dlg.destroy()
        try:
            from education_system.switch import request_switch
            request_switch(system_name, "gui")
            try:
                if self.auth and self.auth.current_user:
                    self.auth.logout()
            except Exception:
                pass
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to switch system: {e}")

    tk.Button(
        btn_frame, text="Sixth Form College System",
        bg="#27ae60", fg="white", activebackground="#2ecc71", activeforeground="white",
        command=lambda: _pick("college"), **btn_style,
    ).pack(pady=6)

    tk.Button(
        btn_frame, text="Secondary School System",
        bg="#8e44ad", fg="white", activebackground="#9b59b6", activeforeground="white",
        command=lambda: _pick("school"), **btn_style,
    ).pack(pady=6)

    tk.Button(
        btn_frame, text="Primary School System",
        bg="#e67e22", fg="white", activebackground="#f39c12", activeforeground="white",
        command=lambda: _pick("primary"), **btn_style,
    ).pack(pady=6)

    tk.Button(
        btn_frame, text="Cancel",
        bg="#95a5a6", fg="white", activebackground="#bdc3c7", activeforeground="white",
        command=dlg.destroy, **btn_style,
    ).pack(pady=6)


def shutdown_system(self):
    """Shutdown the entire system"""
    if messagebox.askyesno(_t("gui.shutdown"), _t("gui.shutdown_confirm")):
        try:
            if self.auth and self.auth.current_user:
                username = self.auth.current_user['username']
                print(_t("gui.debug.system_shutdown_by_user", username=username))
            else:
                print(_t("gui.debug.system_shutdown"))

            def do_shutdown():
                try:
                    self.root.quit()
                    self.root.destroy()
                except Exception:
                    pass
                finally:
                    import os
                    os._exit(0)

            self.root.after(100, do_shutdown)
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("gui.errors.error_during_shutdown", error=str(e)))


# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------

def show_language_selector(self):
    """Show language selection dialog using centralized selector"""
    old_lang = get_current_language()

    if GUI_LANG_SELECTOR_AVAILABLE:
        new_lang = show_gui_language_selector(self.root)
    else:
        messagebox.showwarning(
            _t("common.warning"),
            _t("gui.language_selector_unavailable")
        )
        return

    if new_lang != old_lang:
        messagebox.showinfo(
            _t("gui.language_changed"),
            _t("gui.restart_required")
        )
        self.restart_gui()


# ---------------------------------------------------------------------------
# MFA settings (post-login management, NOT login verification)
# ---------------------------------------------------------------------------

def show_mfa_setup(self):
    """Show MFA setup dialog with current status and options"""
    if not self.auth or not self.auth.current_user:
        messagebox.showerror(_t("common.error"), _t("mfa.messages.login_required", default="You must be logged in to set up MFA"))
        return

    user_id = self.auth.current_user.get('id')
    username = self.auth.current_user.get('username')
    user_email = self.auth.current_user.get('email', '')

    if not user_id or not username:
        messagebox.showerror(_t("common.error"), _t("mfa.messages.user_info_missing", default="Unable to get user information"))
        return

    try:
        from education_system.university_system.infrastructure.auth.mfa_service import MFAService
        mfa_service = MFAService()

        methods_result = None
        is_verification_disabled = False
        saved_methods_result = None

        try:
            methods_result = mfa_service.get_user_mfa_methods(user_id)
        except Exception as e:
            print(f"Error getting MFA methods: {e}")
            methods_result = {'success': False, 'methods': []}

        try:
            is_verification_disabled = mfa_service.is_verification_disabled(user_id)
        except Exception as e:
            print(f"Error checking verification status: {e}")
            is_verification_disabled = False

        try:
            saved_methods_result = mfa_service.get_saved_mfa_methods(user_id)
        except Exception as e:
            print(f"Error getting saved MFA methods: {e}")
            saved_methods_result = {'success': False, 'methods': []}

        saved_methods = []
        if saved_methods_result and isinstance(saved_methods_result, dict) and saved_methods_result.get('success'):
            methods_data = saved_methods_result.get('methods')
            if methods_data and isinstance(methods_data, list):
                saved_methods = methods_data

        active_methods = []
        if methods_result and isinstance(methods_result, dict) and methods_result.get('success'):
            methods_data = methods_result.get('methods')
            if methods_data and isinstance(methods_data, list):
                active_methods = methods_data

        has_saved_disabled_methods = False
        if saved_methods and isinstance(saved_methods, list) and len(saved_methods) > 0:
            try:
                has_saved_disabled_methods = any(
                    not m.get('is_enabled', True)
                    for m in saved_methods
                    if m and isinstance(m, dict)
                )
            except Exception as e:
                print(f"Error checking saved disabled methods: {e}")
                has_saved_disabled_methods = False

        dialog = tk.Toplevel(self.root)
        dialog.title(_t("gui.mfa.settings_title"))
        dialog.geometry("500x450")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 500) // 2
        y = (dialog.winfo_screenheight() - 450) // 2
        dialog.geometry(f"+{x}+{y}")

        title_label = tk.Label(dialog, text=_t("gui.mfa.settings_title"), font=('Arial', 16, 'bold'))
        title_label.pack(pady=(20, 15))

        status_frame = tk.Frame(dialog, relief=tk.GROOVE, bd=2)
        status_frame.pack(padx=20, pady=10, fill=tk.X)

        tk.Label(status_frame, text=_t("gui.mfa.current_setup_details"), font=('Arial', 11, 'bold')).pack(pady=(10, 5))

        if is_verification_disabled:
            verification_status = "Disabled (Password Only)"
            verification_color = "red"
        else:
            verification_status = "Enabled"
            verification_color = "green"

        status_text = f"Login Verification: "
        status_line = tk.Frame(status_frame)
        status_line.pack(pady=2)
        tk.Label(status_line, text=status_text).pack(side=tk.LEFT)
        tk.Label(status_line, text=verification_status, fg=verification_color, font=('Arial', 10, 'bold')).pack(side=tk.LEFT)

        def mask_identifier(identifier):
            if not identifier:
                return 'Configured'
            if '@' in str(identifier):
                parts = str(identifier).split('@')
                return parts[0][:2] + '***@' + parts[1]
            elif identifier:
                identifier = str(identifier)
                return identifier[:3] + '****' + identifier[-2:] if len(identifier) > 5 else '****'
            return 'Configured'

        if active_methods and len(active_methods) > 0:
            tk.Label(status_frame, text="", font=('Arial', 2)).pack()
            tk.Label(status_frame, text=_t("gui.mfa.active_methods"), font=('Arial', 10, 'underline')).pack(pady=(5, 2))
            for method in active_methods:
                if method and isinstance(method, dict):
                    method_type = str(method.get('type', 'Unknown')).upper()
                    identifier = method.get('identifier', '')
                    is_primary = " (Primary)" if method.get('is_primary') else ""
                    masked = mask_identifier(identifier)
                    method_text = f"  • {method_type}: {masked}{is_primary}"
                    tk.Label(status_frame, text=method_text, fg="dark green").pack(pady=1)
        elif has_saved_disabled_methods and saved_methods:
            tk.Label(status_frame, text="", font=('Arial', 2)).pack()
            tk.Label(status_frame, text=_t("gui.mfa.saved_methods_disabled"), font=('Arial', 10, 'underline')).pack(pady=(5, 2))
            for method in saved_methods:
                if method and isinstance(method, dict) and not method.get('is_enabled'):
                    method_type = str(method.get('type', 'Unknown')).upper()
                    identifier = method.get('identifier', '')
                    masked = mask_identifier(identifier)
                    method_text = f"  • {method_type}: {masked}"
                    tk.Label(status_frame, text=method_text, fg="gray").pack(pady=1)
        else:
            tk.Label(status_frame, text=_t("gui.mfa.no_methods_configured"), fg="gray").pack(pady=5)

        tk.Label(status_frame, text="").pack(pady=5)

        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=20)

        def change_authentication():
            if has_saved_disabled_methods and not active_methods:
                choice = messagebox.askyesnocancel(
                    _t("gui.mfa.reuse_settings_title"),
                    _t("gui.mfa.reuse_settings_message")
                )
                if choice is None:
                    return
                elif choice:
                    dialog.destroy()
                    self._reenable_mfa_with_confirmation(user_id, username, user_email, mfa_service, saved_methods)
                else:
                    dialog.destroy()
                    self._open_mfa_wizard(user_id, username)
            else:
                dialog.destroy()
                self._open_mfa_wizard(user_id, username)

        def turn_on_mfa():
            if has_saved_disabled_methods:
                choice = messagebox.askyesnocancel(
                    _t("gui.mfa.turn_on_mfa_title"),
                    _t("gui.mfa.reuse_settings_message")
                )
                if choice is None:
                    return
                elif choice:
                    dialog.destroy()
                    self._reenable_mfa_with_confirmation(user_id, username, user_email, mfa_service, saved_methods)
                else:
                    dialog.destroy()
                    self._open_mfa_wizard(user_id, username)
            else:
                dialog.destroy()
                self._open_mfa_wizard(user_id, username)

        def turn_off_mfa():
            if not active_methods and is_verification_disabled:
                messagebox.showinfo(_t("common.info"), _t("gui.mfa.already_disabled"))
                return

            confirm = messagebox.askyesno(
                _t("gui.mfa.turn_off_mfa_title"),
                _t("gui.mfa.turn_off_mfa_message"),
                icon='warning'
            )

            if confirm:
                try:
                    if active_methods:
                        result = mfa_service.disable_mfa(user_id)
                        if not result.get('success'):
                            messagebox.showerror(_t("common.error"), _t("gui.mfa.failed_disable_mfa", error=result.get('error')))
                            return

                    result = mfa_service.set_verification_disabled(user_id, True)
                    if result.get('success'):
                        messagebox.showinfo(
                            "Success",
                            "MFA has been turned off.\n\n"
                            "Your settings have been saved.\n"
                            "You can restore them later from this menu."
                        )
                        dialog.destroy()
                    else:
                        messagebox.showerror(_t("common.error"), _t("gui.mfa.failed_disable_verification", error=result.get('error')))
                except Exception as e:
                    messagebox.showerror(_t("common.error"), _t("gui.mfa.error_disabling", error=str(e)))

        button_width = 22
        button_pady = 5

        if active_methods or not is_verification_disabled:
            change_btn = tk.Button(
                button_frame, text=_t("gui.mfa.change_authentication"),
                command=change_authentication, width=button_width,
                bg="#2196F3", fg="white", font=('Arial', 10)
            )
            change_btn.pack(pady=button_pady)

            turnoff_btn = tk.Button(
                button_frame, text=_t("gui.mfa.turn_off_mfa_button"),
                command=turn_off_mfa, width=button_width,
                bg="#f44336", fg="white", font=('Arial', 10)
            )
            turnoff_btn.pack(pady=button_pady)
        else:
            turnon_btn = tk.Button(
                button_frame, text=_t("gui.mfa.turn_on_mfa_button"),
                command=turn_on_mfa, width=button_width,
                bg="#4CAF50", fg="white", font=('Arial', 10, 'bold')
            )
            turnon_btn.pack(pady=button_pady)

        close_btn = tk.Button(
            button_frame, text=_t("common.close"),
            command=dialog.destroy, width=button_width, font=('Arial', 10)
        )
        close_btn.pack(pady=button_pady)

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

    except ImportError as e:
        messagebox.showerror(_t("common.error"), f"MFA module not available: {e}")
    except Exception as e:
        messagebox.showerror(_t("common.error"), f"Error opening MFA setup: {e}")


def _reenable_mfa_with_confirmation(self, user_id, username, user_email, mfa_service, saved_methods):
    """Re-enable MFA with saved settings and send confirmation email"""
    try:
        result = mfa_service.reenable_mfa(user_id)

        if not result or not result.get('success'):
            error_msg = result.get('error') if result else 'Unknown error'
            messagebox.showerror(_t("common.error"), _t("gui.mfa.failed_reenable", error=error_msg))
            return

        email_to_notify = user_email
        if saved_methods and isinstance(saved_methods, list):
            for method in saved_methods:
                if method and isinstance(method, dict):
                    if method.get('type') == 'email' and method.get('identifier'):
                        email_to_notify = method.get('identifier')
                        break

        if email_to_notify:
            try:
                from education_system.university_system.infrastructure.auth.email_otp_service import SMTPEmailProvider

                methods_count = 1
                if result and isinstance(result, dict):
                    methods_count = result.get('methods_count', 1) or 1

                subject = "MFA Re-enabled for Your Account"
                body = f"""Hello {username or 'User'},

Multi-Factor Authentication (MFA) has been re-enabled for your account using your previously saved settings.

Details:
- Account: {username}
- Email: {email_to_notify}
- Methods restored: {methods_count}

If you did not make this change, please contact support immediately and change your password.

Thank you,
University System Security Team"""

                email_sent = False
                try:
                    smtp_provider = SMTPEmailProvider()
                    import smtplib
                    from email.mime.text import MIMEText
                    from email.mime.multipart import MIMEMultipart

                    msg = MIMEMultipart()
                    msg['Subject'] = subject
                    msg['From'] = f"{smtp_provider.from_name} <{smtp_provider.from_email}>"
                    msg['To'] = email_to_notify
                    msg.attach(MIMEText(body, 'plain'))

                    with smtplib.SMTP(smtp_provider.smtp_server, smtp_provider.smtp_port) as server:
                        server.starttls()
                        server.login(smtp_provider.username, smtp_provider.password)
                        server.send_message(msg)

                    email_sent = True
                except Exception as smtp_error:
                    print(f"SMTP send failed: {smtp_error}")

                if email_sent:
                    messagebox.showinfo(
                        "MFA Re-enabled",
                        f"MFA has been successfully re-enabled using your saved settings.\n\n"
                        f"A confirmation email has been sent to:\n{email_to_notify}"
                    )
                else:
                    messagebox.showinfo(
                        "MFA Re-enabled",
                        f"MFA has been successfully re-enabled using your saved settings.\n\n"
                        f"(Email notification could not be sent externally)"
                    )
            except Exception as email_error:
                messagebox.showinfo(
                    "MFA Re-enabled",
                    f"MFA has been successfully re-enabled using your saved settings.\n\n"
                    f"(Confirmation email could not be sent: {email_error})"
                )
        else:
            messagebox.showinfo(
                "MFA Re-enabled",
                "MFA has been successfully re-enabled using your saved settings."
            )

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("gui.mfa.error_reenabling", error=str(e)))


def _open_mfa_wizard(self, user_id, username):
    """Open the MFA setup wizard"""
    try:
        from education_system.university_system.modules.shared.gui.auth.mfa_gui import show_mfa_setup as mfa_setup_wizard

        def on_mfa_complete(success):
            if success:
                messagebox.showinfo(
                    _t("mfa.messages.setup_complete_title", default="MFA Setup Complete"),
                    _t("mfa.messages.setup_complete", default="Two-Factor Authentication has been enabled for your account.")
                )

        mfa_setup_wizard(self.root, user_id, username, on_complete=on_mfa_complete)
    except ImportError as e:
        messagebox.showerror(_t("common.error"), f"MFA module not available: {e}")
    except Exception as e:
        messagebox.showerror(_t("common.error"), f"Error opening MFA wizard: {e}")


def toggle_login_verification(self):
    """Toggle login verification on/off (disable MFA and PIN for password-only login)"""
    if not self.auth or not self.auth.current_user:
        messagebox.showerror(_t("common.error"), _t("gui.mfa.must_be_logged_in"))
        return

    user_id = self.auth.current_user.get('id')

    if not user_id:
        messagebox.showerror(_t("common.error"), _t("gui.mfa.unable_get_user_info"))
        return

    try:
        from education_system.university_system.infrastructure.auth.mfa_service import MFAService
        mfa_service = MFAService()

        is_disabled = mfa_service.is_verification_disabled(user_id)

        if is_disabled:
            if messagebox.askyesno(
                _t("gui.mfa.enable_verification_title"),
                _t("gui.mfa.enable_verification_message")
            ):
                result = mfa_service.set_verification_disabled(user_id, False)
                if result.get('success'):
                    messagebox.showinfo(_t("common.success"), _t("gui.mfa.verification_enabled"))
                else:
                    messagebox.showerror(_t("common.error"), _t("gui.mfa.failed_enable_verification", error=result.get('error')))
        else:
            if messagebox.askyesno(
                _t("gui.mfa.disable_verification_title"),
                _t("gui.mfa.disable_verification_message"),
                icon='warning'
            ):
                result = mfa_service.set_verification_disabled(user_id, True)
                if result.get('success'):
                    messagebox.showinfo(_t("common.success"), _t("gui.mfa.verification_disabled"))
                else:
                    messagebox.showerror(_t("common.error"), _t("gui.mfa.failed_disable_verification_second", error=result.get('error')))

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("gui.mfa.error_changing_verification", error=str(e)))
