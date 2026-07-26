# University GUI – authentication-related helpers (post-login only).
#
# Login is handled exclusively by the universal login in
# education_system/shared/gui/login_gui.py.  This module only contains
# logout, session management, MFA settings, system switching, etc.

import tkinter as tk
from tkinter import ttk, messagebox
import os
import logging
from education_system.systems.university.infrastructure.i18n import get_text as _t, get_current_language
from education_system.systems.university.interfaces.gui.shell.main._tk_callback_filter import install_clean_close as _install_clean_close

# Language selection is now handled at startup via education_system.platform.features.i18n

logger = logging.getLogger(__name__)


def _is_superadmin_user(gui_self):
    """Check if current user has admin access to all 4 systems."""
    user_info = getattr(gui_self, "_shared_user_info", None) or {}
    if not user_info:
        # Try auth current_user
        try:
            user_info = gui_self.auth.current_user or {}
        except Exception:
            return False
    systems = user_info.get("systems", [])
    if not systems:
        return False
    admin_keys = {s["system_key"] for s in systems if s.get("role") == "admin"}
    return "university" in admin_keys


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def logout_user(self):
    """Logout current user and return to universal login.

    Pre-8.117.33 the click went straight through to logout. Now a
    yes/no confirmation runs first — easy to misclick the header
    button or the sidebar entry, and the rebuild + relogin cost is
    real (~seconds). Yes proceeds with the existing flow; No just
    dismisses the confirmation dialog and leaves the user logged in.

    Each step below is wrapped so a failure (e.g. messagebox
    erroring, a Tk callback raising during nav rebuild) can't strand
    the process with ``request_logout`` un-signalled and the root
    undestroyed. We've seen occasional hangs after the "Goodbye, …!"
    print where the GUI appeared frozen — the most reliable
    mitigation is to make the sequence advance to ``root.destroy()``
    no matter what, and to schedule a watchdog that force-exits if
    the dispatch loop's relaunch can't bring up a fresh Tk root
    within a few seconds.
    """
    if not self.auth.current_user:
        return

    # Confirm before logging out. messagebox.askyesno returns True for
    # Yes / False for No (or for the user closing the dialog with the
    # X button). False short-circuits the whole logout flow — the
    # user stays logged in and the dialog is the only thing that
    # gets dismissed.
    try:
        confirmed = messagebox.askyesno(
            _t("common.confirm", default="Confirm"),
            _t(
                "gui.login.confirm_logout",
                default="Are you sure you want to log out?",
            ),
            parent=getattr(self, "root", None),
        )
    except Exception:
        # If the messagebox itself fails (very unusual — broken Tcl
        # state), fall through to the legacy unconfirmed behaviour
        # rather than silently swallowing the user's intent.
        confirmed = True
    if not confirmed:
        return

    username = self.auth.current_user['username']

    # Revoke remember-me tokens (best-effort).
    try:
        from education_system.systems.university.infrastructure.auth.enhanced_auth import EnhancedAuth
        if isinstance(self.auth, EnhancedAuth):
            user_id = self.auth.current_user.get('id')
            if user_id:
                self.auth.logout_and_revoke_remember_me(user_id)
    except Exception as e:
        logger.debug(f"Could not revoke remember me tokens: {e}")

    # Signal "return to universal login" up front so even if a later
    # step throws, the dispatch loop will still relaunch correctly.
    try:
        from education_system.switch import request_logout
        request_logout()
    except Exception:
        logger.exception("request_logout failed")

    try:
        self.auth.logout()
    except Exception:
        logger.exception("auth.logout failed")

    # Show confirmation BEFORE rebuilding the navigation panel — if
    # update_status hangs (it rebuilds the entire sidebar), the user
    # at least got the goodbye dialog.
    try:
        messagebox.showinfo(
            _t("gui.login.logged_out"),
            _t("gui.login.goodbye").format(username=username),
        )
    except Exception:
        logger.exception("logout messagebox failed")

    try:
        self.update_status()
    except Exception:
        logger.exception("update_status after logout failed")

    try:
        self._cancel_timers()
    except Exception:
        pass

    try:
        self.root.destroy()
    except Exception:
        logger.exception("root.destroy failed; forcing exit")
        try:
            import os as _os
            _os._exit(0)
        except Exception:
            pass


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
    _install_clean_close(password_window)
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

        try:
            ok = self.auth.change_password(self.auth.current_user['username'], current, new)
        except Exception as exc:
            status_label.config(text=str(exc))
            return

        if ok:
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
        # winfo_exists raises TclError if the underlying Tcl interp is
        # gone (e.g. root destroyed mid-tick) — treat as "stop".
        if not self.root.winfo_exists():
            return
    except tk.TclError:
        return
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

    # Keep the header notification badge live (best-effort — never let a
    # notification lookup break the session tick).
    try:
        refresh = getattr(self, "_refresh_notification_badge", None)
        if callable(refresh):
            refresh()
    except Exception:
        pass

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
                from education_system.systems.university.infrastructure.database.db import _connection_pool, _pool_lock
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
                from education_system.systems.university.infrastructure.shared_context import set_auth as reset_shared_auth
                from education_system.systems.university.infrastructure.auth import UserAuth
                fresh_auth = UserAuth()
                reset_shared_auth(fresh_auth)
            except Exception:
                pass

            gc.collect()
            time.sleep(0.2)

            from education_system.systems.university.interfaces.cli.shell.cli_main import main as cli_main
            # Pass current user info so CLI skips the login prompt
            user_info = None
            role = None
            shared_auth = None
            if hasattr(self, 'auth') and self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                cu = self.auth.current_user
                user_info = {
                    "user_id": cu.get("user_id") or cu.get("id"),
                    "username": cu.get("username"),
                    "display_name": cu.get("display_name"),
                    "email": cu.get("email", ""),
                    "systems": cu.get("systems", []),
                }
                role = cu.get("role")
                shared_auth = self.auth
            self.root.withdraw()
            self.root.quit()
            cli_main(user_info=user_info, role=role, shared_auth=shared_auth)
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("gui.errors.failed_switch_cli", error=str(e)))
            self.root.deiconify()


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
    """Show language selection dialog using the shared i18n selector."""
    from education_system.platform.features.i18n.selector_gui import show_language_selector as _show

    old_lang = get_current_language()
    new_lang = _show(self.root)

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
        from education_system.systems.university.infrastructure.auth.mfa_service import MFAService
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
        _install_clean_close(dialog)
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
            verification_status = _t("gui.mfa.verification_status_disabled")
            verification_color = "red"
        else:
            verification_status = _t("gui.mfa.verification_status_enabled")
            verification_color = "green"

        status_text = _t("gui.mfa.login_verification_label")
        status_line = tk.Frame(status_frame)
        status_line.pack(pady=2)
        tk.Label(status_line, text=status_text).pack(side=tk.LEFT)
        tk.Label(status_line, text=verification_status, fg=verification_color, font=('Arial', 10, 'bold')).pack(side=tk.LEFT)

        def mask_identifier(identifier):
            if not identifier:
                return _t("gui.mfa.configured")
            if '@' in str(identifier):
                parts = str(identifier).split('@')
                return parts[0][:2] + '***@' + parts[1]
            elif identifier:
                identifier = str(identifier)
                return identifier[:3] + '****' + identifier[-2:] if len(identifier) > 5 else '****'
            return _t("gui.mfa.configured")

        if active_methods and len(active_methods) > 0:
            tk.Label(status_frame, text="", font=('Arial', 2)).pack()
            tk.Label(status_frame, text=_t("gui.mfa.active_methods"), font=('Arial', 10, 'underline')).pack(pady=(5, 2))
            for method in active_methods:
                if method and isinstance(method, dict):
                    method_type = str(method.get('type', 'Unknown')).upper()
                    identifier = method.get('identifier', '')
                    is_primary = f" ({_t('gui.mfa.primary_method')})" if method.get('is_primary') else ""
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
                            _t("common.success"),
                            _t("gui.mfa.turned_off_success")
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
        messagebox.showerror(_t("common.error"), _t("gui.mfa.module_not_available", error=str(e)))
    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("gui.mfa.error_opening_setup", error=str(e)))


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
                from education_system.systems.university.infrastructure.auth.email_otp_service import SMTPEmailProvider

                methods_count = 1
                if result and isinstance(result, dict):
                    methods_count = result.get('methods_count', 1) or 1

                subject = _t("gui.mfa.reenable_email_subject")
                body = _t("gui.mfa.reenable_email_body", username=username or 'User', email=email_to_notify, methods_count=methods_count)

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
                        _t("gui.mfa.reenabled_title"),
                        _t("gui.mfa.reenabled_with_email", email=email_to_notify)
                    )
                else:
                    messagebox.showinfo(
                        _t("gui.mfa.reenabled_title"),
                        _t("gui.mfa.reenabled_no_email")
                    )
            except Exception as email_error:
                messagebox.showinfo(
                    _t("gui.mfa.reenabled_title"),
                    _t("gui.mfa.reenabled_email_error", error=str(email_error))
                )
        else:
            messagebox.showinfo(
                _t("gui.mfa.reenabled_title"),
                _t("gui.mfa.reenabled_simple")
            )

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("gui.mfa.error_reenabling", error=str(e)))


def _open_mfa_wizard(self, user_id, username):
    """Open the MFA setup wizard"""
    try:
        from education_system.systems.university.interfaces.gui.shell.auth.mfa_gui import show_mfa_setup as mfa_setup_wizard

        def on_mfa_complete(success):
            if success:
                messagebox.showinfo(
                    _t("mfa.messages.setup_complete_title", default="MFA Setup Complete"),
                    _t("mfa.messages.setup_complete", default="Two-Factor Authentication has been enabled for your account.")
                )

        mfa_setup_wizard(self.root, user_id, username, on_complete=on_mfa_complete)
    except ImportError as e:
        messagebox.showerror(_t("common.error"), _t("gui.mfa.module_not_available", error=str(e)))
    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("gui.mfa.error_opening_wizard", error=str(e)))


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
        from education_system.systems.university.infrastructure.auth.mfa_service import MFAService
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
