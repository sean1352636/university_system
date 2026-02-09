# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox
import os
import logging
import threading
from university_system.modules.shared.utils.i18n import get_text as _t, get_current_language
from university_system.infrastructure.exceptions import InvalidCredentialsError, AuthenticationError, DatabaseError

# Check for GUI language selector availability
try:
    from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector
    GUI_LANG_SELECTOR_AVAILABLE = True
except ImportError:
    GUI_LANG_SELECTOR_AVAILABLE = False

logger = logging.getLogger(__name__)

def show_login_screen(self):
    """Show login interface when not authenticated"""
    # Check for remember me token first
    if self._check_remember_me_token():
        # Auto-login successful
        self.show_main_interface()
        return

    self.clear_content()

    # Ensure content_frame exists before proceeding
    if not hasattr(self, 'content_frame') or not self.content_frame:
        print(_t("gui.debug.content_frame_not_initialized"))
        return

    login_frame = ttk.LabelFrame(self.content_frame, text=_t("gui.login.please_log_in"), padding="30")
    login_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))

    # Login form
    ttk.Label(login_frame, text=_t("gui.login.username") + ":").grid(row=0, column=0, sticky=tk.W, pady=10)
    self.username_entry = ttk.Entry(login_frame, width=30, font=('Arial', 11))
    self.username_entry.grid(row=0, column=1, pady=10, padx=(15, 0))

    ttk.Label(login_frame, text=_t("gui.login.password") + ":").grid(row=1, column=0, sticky=tk.W, pady=10)
    self.password_entry = ttk.Entry(login_frame, width=30, show="*", font=('Arial', 11))
    self.password_entry.grid(row=1, column=1, pady=10, padx=(15, 0))

    # Show/Hide password toggle
    self.show_password_var = tk.BooleanVar(value=False)

    def toggle_password_visibility():
        if self.show_password_var.get():
            self.password_entry.config(show="")
        else:
            self.password_entry.config(show="*")

    show_password_btn = ttk.Checkbutton(
        login_frame,
        text=_t("gui.show_password"),
        variable=self.show_password_var,
        command=toggle_password_visibility
    )
    show_password_btn.grid(row=1, column=2, pady=10, padx=(10, 0))

    # Remember Me checkbox
    self.remember_me_var = tk.BooleanVar(value=False)
    remember_me_checkbox = ttk.Checkbutton(
        login_frame,
        text=_t("gui.login.remember_me"),
        variable=self.remember_me_var
    )
    remember_me_checkbox.grid(row=2, column=0, columnspan=2, pady=10, sticky=tk.W)

    # Login button (store reference for state management)
    self.login_btn_ref = ttk.Button(login_frame, text=_t("gui.login.login_button"), command=self.perform_login, style="Accent.TButton")
    self.login_btn_ref.grid(row=3, column=0, columnspan=2, pady=25)

    # Bind Enter key
    self.username_entry.bind('<Return>', lambda e: self.perform_login())
    self.password_entry.bind('<Return>', lambda e: self.perform_login())

    # Focus username
    self.username_entry.focus()

    # Show default credentials info
    # WARNING: These are default demo credentials - change them in production!
    # Set DEFAULT_ADMIN_PASSWORD, DEFAULT_STAFF_PASSWORD, DEFAULT_STUDENT_PASSWORD environment variables
    info_frame = ttk.LabelFrame(self.content_frame, text=_t("gui.default_credentials"), padding="20")
    info_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=0, pady=20)

    admin_pwd = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')
    staff_pwd = os.getenv('DEFAULT_STAFF_PASSWORD', 'staff123')
    student_pwd = os.getenv('DEFAULT_STUDENT_PASSWORD', 'student123')
    student_username = os.getenv('DEFAULT_STUDENT_USERNAME', 'S12345')

    creds_text = _t("gui.login.credentials_format").format(
        admin_pwd=admin_pwd,
        staff_pwd=staff_pwd,
        student_username=student_username,
        student_pwd=student_pwd
    )

    ttk.Label(info_frame, text=creds_text, justify=tk.LEFT, font=('Courier', 10)).pack()
def show_login(self):
    """Show login dialog (for re-login)"""
    if hasattr(self.auth, 'current_user') and self.auth.current_user:
        messagebox.showinfo(
            _t("gui.login.already_logged_in"),
            _t("gui.login.already_logged_in_as").format(username=self.auth.current_user['username'])
        )
        return

    self.show_login_screen()
def perform_login(self):
    """Handle login process with lockout protection"""
    try:
        # Check if entry widgets exist and are still valid
        if not hasattr(self, 'username_entry') or not self.username_entry:
            logger.error("Username entry widget not found")
            messagebox.showerror(_t("common.error"), _t("gui.login.form_not_available"))
            return

        if not hasattr(self, 'password_entry') or not self.password_entry:
            logger.error("Password entry widget not found")
            messagebox.showerror(_t("common.error"), _t("gui.login.form_not_available"))
            return

        # Check if widgets are still valid (not destroyed)
        try:
            if not self.username_entry.winfo_exists() or not self.password_entry.winfo_exists():
                logger.error("Login form widgets have been destroyed")
                messagebox.showerror(_t("common.error"), _t("gui.login.form_not_available"))
                return
        except tk.TclError:
            logger.error("Login form widgets are invalid")
            messagebox.showerror(_t("common.error"), _t("gui.login.form_not_available"))
            return

        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            messagebox.showerror(_t("common.error"), _t("gui.login.enter_both_credentials"))
            return

        # Disable login button to prevent double-clicks
        if hasattr(self, 'login_btn_ref') and self.login_btn_ref:
            try:
                self.login_btn_ref.config(state='disabled', text=_t("gui.login.logging_in", default="Logging in..."))
            except Exception as e:
                logger.warning(f"Could not disable login button: {e}")

        # Run login in background thread to prevent UI freeze
        thread = threading.Thread(target=self._perform_login_thread, args=(username, password), daemon=True)
        thread.start()

    except AttributeError as e:
        logger.error(f"AttributeError in perform_login: {e}", exc_info=True)
        messagebox.showerror(_t("common.error"), _t("gui.login.form_not_initialized"))
        # Try to re-enable the button
        if hasattr(self, 'login_btn_ref') and self.login_btn_ref:
            try:
                self.login_btn_ref.config(state='normal', text=_t("gui.login.login_button"))
            except:
                pass
    except Exception as e:
        logger.error(f"Unexpected error in perform_login: {e}", exc_info=True)
        messagebox.showerror(_t("common.error"), _t("gui.login.login_error").format(error=str(e)))
        # Try to re-enable the button
        if hasattr(self, 'login_btn_ref') and self.login_btn_ref:
            try:
                self.login_btn_ref.config(state='normal', text=_t("gui.login.login_button"))
            except:
                pass
        try:
            self.log_activity(f"Login error: {str(e)}", level="error", action="login")
        except Exception as ex:
            logger.error(f"Failed to log activity for login error: {ex}")

def _perform_login_thread(self, username, password):
    """Background thread for login processing"""
    try:

        # Check if account is locked before attempting login
        lockout_remaining = None
        if hasattr(self.auth, 'get_lockout_time_remaining'):
            lockout_remaining = self.auth.get_lockout_time_remaining(username)
            if lockout_remaining:
                self.root.after(0, lambda: self._handle_login_error(
                    _t("gui.login.account_locked"),
                    _t("gui.login.account_locked_message").format(minutes=lockout_remaining),
                    clear_password=False
                ))
                return

        # Get remember me preference
        remember_me = getattr(self, 'remember_me_var', None)
        remember_me_enabled = remember_me.get() if remember_me else False

        # Try to use EnhancedAuth with remember me if available
        result = None
        try:
            from university_system.infrastructure.auth.enhanced_auth import EnhancedAuth

            # Generate device fingerprint
            import socket
            import hashlib
            machine_id = f"{socket.gethostname()}_{username}"
            device_fingerprint = hashlib.sha256(machine_id.encode()).hexdigest()[:32]

            # Get IP address (use localhost for desktop app)
            ip_address = "127.0.0.1"

            # Use EnhancedAuth if remember me is enabled
            if remember_me_enabled and isinstance(self.auth, EnhancedAuth):
                result = self.auth.login_with_remember_me(
                    username=username,
                    password=password,
                    remember_me=True,
                    device_fingerprint=device_fingerprint,
                    ip_address=ip_address,
                    user_agent="GUI Desktop App"
                )

                # Store remember me token if provided
                if result.get('success') and result.get('remember_token'):
                    self._save_remember_token(username, result['remember_token'], device_fingerprint)
                    result = True  # Convert to standard boolean result
            else:
                # Standard login
                result = self.auth.login(username, password)
        except ImportError:
            # EnhancedAuth not available, use standard login
            result = self.auth.login(username, password)
        except InvalidCredentialsError as e:
            # Handle lockout error specifically
            if hasattr(e, 'details') and e.details and e.details.get('wait_minutes'):
                wait_time = e.details.get('wait_minutes')
                self.root.after(0, lambda: self._handle_login_error(
                    _t("gui.login.account_locked"),
                    _t("gui.login.account_locked_wait").format(minutes=wait_time),
                    clear_password=True
                ))
            else:
                # Show remaining attempts
                remaining = 0
                if hasattr(self.auth, 'get_remaining_login_attempts'):
                    remaining = self.auth.get_remaining_login_attempts(username)

                error_msg = str(e.message) if hasattr(e, 'message') else str(e)
                if remaining > 0:
                    error_msg += "\n\n" + _t("gui.login.attempts_remaining").format(attempts=remaining)
                elif remaining == 0:
                    error_msg += "\n\n" + _t("gui.login.next_attempt_locks")

                self.root.after(0, lambda: self._handle_login_error(
                    _t("gui.login.login_failed"),
                    error_msg,
                    clear_password=True
                ))
            return
        except (AuthenticationError, DatabaseError) as e:
            error_msg = str(e.message) if hasattr(e, 'message') else str(e)
            self.root.after(0, lambda: self._handle_login_error(
                _t("gui.login.login_failed"),
                error_msg,
                clear_password=True
            ))
            return

        if result is True:
            # Check if user has MFA configured with email
            try:
                from university_system.infrastructure.auth.mfa_service import MFAService
                mfa_service = MFAService()

                # Get user ID from auth
                user_id = None
                if hasattr(self.auth, 'current_user') and self.auth.current_user:
                    user_id = self.auth.current_user.get('id')

                # Check if verification is disabled (password-only login)
                if user_id and mfa_service.is_verification_disabled(user_id):
                    # Skip all verification - just login
                    self.root.after(0, lambda: self._complete_login_success(username))
                    return

                # Check for configured email MFA
                email_configured = None
                if user_id:
                    mfa_result = mfa_service.get_user_mfa_methods(user_id)
                    if mfa_result.get('success'):
                        for method in mfa_result.get('methods', []):
                            if method.get('type') == 'email' and method.get('identifier'):
                                email_configured = method.get('identifier')
                                break

                if email_configured:
                    # User has email MFA configured - send OTP to their email
                    otp_result = mfa_service.generate_email_otp(user_id, email_configured)

                    if otp_result.get('success'):
                        # Mask email for display
                        email_parts = email_configured.split('@')
                        masked_email = email_parts[0][:2] + '***@' + email_parts[1] if len(email_parts) == 2 else email_configured

                        if otp_result.get('email_failed'):
                            # Email failed to send - show code on screen as fallback
                            fallback_code = otp_result.get('code', '')
                            self.root.after(0, lambda: self._handle_email_otp_fallback(
                                fallback_code, username, masked_email
                            ))
                        else:
                            # Show success message and verify on main thread
                            self.root.after(0, lambda: self._handle_email_otp_verification(
                                mfa_service, user_id, username, masked_email
                            ))
                        return
                    else:
                        # OTP generation failed - fall back to PIN
                        self.root.after(0, lambda: self._do_pin_verification(username))
                        return
                else:
                    # No email MFA configured - use 4-digit PIN on screen
                    self.root.after(0, lambda: self._do_pin_verification(username))
                    return

            except Exception as e:
                # If MFA check fails, fall back to PIN verification
                logger.warning(f"MFA check error: {e}")
                self.root.after(0, lambda: self._do_pin_verification(username))
                return

        elif isinstance(result, dict) and result.get('requires_2fa'):
            # Handle legacy 2FA - use PIN verification
            mfa_username = result.get('username', username)
            self.root.after(0, lambda: self._do_pin_verification(mfa_username))

        elif result == 'password_reset_required':
            self.root.after(0, lambda: self._handle_password_reset_required())

        elif result == 'mfa_setup_required':
            # MFA setup disabled for simple PIN testing - just proceed to main interface
            self.root.after(0, lambda: self._handle_mfa_setup_skipped())

        else:
            # Show remaining attempts for failed login
            remaining = 0
            if hasattr(self.auth, 'get_remaining_login_attempts'):
                remaining = self.auth.get_remaining_login_attempts(username)

            error_msg = _t("gui.login.invalid_credentials")
            if remaining > 0:
                error_msg += "\n\n" + _t("gui.login.attempts_remaining").format(attempts=remaining)
            elif remaining == 0:
                error_msg += "\n\n" + _t("gui.login.next_attempt_locks")

            self.root.after(0, lambda: self._handle_login_error(
                _t("gui.login.login_failed"),
                error_msg,
                clear_password=True
            ))

    except Exception as e:
        logger.error(f"Login thread error: {e}")
        self.root.after(0, lambda: self._handle_login_error(
            _t("common.error"),
            _t("gui.login.login_error").format(error=str(e)),
            clear_password=True
        ))
        try:
            self.log_activity(f"Login error: {str(e)}", level="error", action="login")
        except Exception as ex:
            logger.error(f"Failed to log activity for login error: {ex}")

def _handle_login_error(self, title, message, clear_password=True):
    """Handle login error on main thread"""
    # Re-enable login button
    if hasattr(self, 'login_btn_ref') and self.login_btn_ref:
        try:
            if self.login_btn_ref.winfo_exists():
                self.login_btn_ref.config(state='normal', text=_t("gui.login.login_button"))
        except (tk.TclError, Exception) as e:
            logger.debug(f"Could not re-enable login button: {e}")

    messagebox.showerror(title, message)

    if clear_password and hasattr(self, 'password_entry') and self.password_entry:
        try:
            if self.password_entry.winfo_exists():
                self.password_entry.delete(0, tk.END)
        except (tk.TclError, Exception) as e:
            logger.debug(f"Could not clear password entry: {e}")

def _complete_login_success(self, username):
    """Complete successful login on main thread"""
    self.show_main_interface()
    messagebox.showinfo(_t("common.success"), _t("gui.login.welcome").format(username=username))
    self.log_activity(f"User {username} logged in successfully", action="login")

def _handle_email_otp_fallback(self, fallback_code, username, masked_email):
    """Handle email OTP fallback on main thread"""
    messagebox.showwarning(
        _t("gui.login.email_delivery_failed"),
        _t("gui.login.email_delivery_failed_message").format(
            email=masked_email,
            code=fallback_code
        )
    )
    # Verify against the fallback code directly
    otp_verified = self._verify_email_otp(fallback_code, username, masked_email)

    if otp_verified:
        self.show_main_interface()
        messagebox.showinfo(_t("common.success"), _t("gui.login.welcome").format(username=username))
        self.log_activity(f"User {username} logged in with email MFA", action="login")
    else:
        if hasattr(self.auth, 'logout'):
            self.auth.logout()
        self.show_login_screen()

def _handle_email_otp_verification(self, mfa_service, user_id, username, masked_email):
    """Handle email OTP verification on main thread"""
    messagebox.showinfo(
        _t("gui.login.verification_code_sent"),
        _t("gui.login.verification_code_sent_message").format(email=masked_email)
    )
    # Verify using MFA service (code stored in database)
    otp_verified = self._verify_email_otp_via_service(
        mfa_service, user_id, username, masked_email
    )

    if otp_verified:
        self.show_main_interface()
        messagebox.showinfo(_t("common.success"), _t("gui.login.welcome").format(username=username))
        self.log_activity(f"User {username} logged in with email MFA", action="login")
    else:
        if hasattr(self.auth, 'logout'):
            self.auth.logout()
        self.show_login_screen()

def _handle_password_reset_required(self):
    """Handle password reset required on main thread"""
    # Re-enable login button
    if hasattr(self, 'login_btn_ref') and self.login_btn_ref:
        try:
            if self.login_btn_ref.winfo_exists():
                self.login_btn_ref.config(state='normal', text=_t("gui.login.login_button"))
        except (tk.TclError, Exception) as e:
            logger.debug(f"Could not re-enable login button: {e}")

    messagebox.showwarning(_t("gui.login.password_reset_required"), _t("gui.login.must_change_password"))
    self.show_change_password()

def _handle_mfa_setup_skipped(self):
    """Handle MFA setup skipped on main thread"""
    messagebox.showinfo(_t("common.info"), _t("gui.login.mfa_setup_skipped"))
    self.show_main_interface()

def _do_pin_verification(self, username):
    """Generate and display 4-digit PIN for first-time login verification"""
    import random
    pin = f"{random.randint(0, 9999):04d}"

    # Show PIN to user
    messagebox.showinfo(
        _t("gui.login.verification_required"),
        _t("gui.login.pin_verification_message").format(pin=pin)
    )

    # Verify the PIN
    if self._verify_login_pin(pin, username):
        self.show_main_interface()
        messagebox.showinfo(_t("common.success"), _t("gui.login.welcome").format(username=username))
        self.log_activity(f"User {username} logged in successfully", action="login")
    else:
        if hasattr(self.auth, 'logout'):
            self.auth.logout()
        self.show_login_screen()

def _verify_login_pin(self, correct_pin, username):
    """Show PIN verification dialog and verify the entered PIN"""
    max_attempts = 3
    attempts = 0

    while attempts < max_attempts:
        # Create PIN entry dialog
        pin_dialog = tk.Toplevel(self.root)
        pin_dialog.title(_t("gui.login.enter_verification_code"))
        pin_dialog.geometry("350x200")
        pin_dialog.transient(self.root)
        pin_dialog.grab_set()

        # Center the dialog
        pin_dialog.update_idletasks()
        x = (pin_dialog.winfo_screenwidth() // 2) - (pin_dialog.winfo_width() // 2)
        y = (pin_dialog.winfo_screenheight() // 2) - (pin_dialog.winfo_height() // 2)
        pin_dialog.geometry(f"+{x}+{y}")

        main_frame = ttk.Frame(pin_dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame,
            text=_t("gui.login.enter_4digit_code").format(username=username),
            font=('Arial', 11),
            justify=tk.CENTER
        ).pack(pady=(0, 15))

        if attempts > 0:
            ttk.Label(
                main_frame,
                text=_t("gui.login.incorrect_code_remaining").format(attempts=max_attempts - attempts),
                foreground="red"
            ).pack(pady=(0, 10))

        pin_var = tk.StringVar()
        pin_entry = ttk.Entry(
            main_frame,
            textvariable=pin_var,
            font=('Courier', 20, 'bold'),
            width=6,
            justify=tk.CENTER
        )
        pin_entry.pack(pady=10)
        pin_entry.focus()

        result = {'verified': False, 'cancelled': False}

        def verify():
            entered = pin_var.get().strip()
            if entered == correct_pin:
                result['verified'] = True
            pin_dialog.destroy()

        def cancel():
            result['cancelled'] = True
            pin_dialog.destroy()

        pin_entry.bind('<Return>', lambda e: verify())

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)

        ttk.Button(btn_frame, text=_t("common.verify"), command=verify, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=cancel).pack(side=tk.LEFT, padx=5)

        pin_dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.root.wait_window(pin_dialog)

        if result['cancelled']:
            messagebox.showwarning(_t("gui.login.login_cancelled"), _t("gui.login.verification_cancelled"))
            return False

        if result['verified']:
            return True

        attempts += 1

    messagebox.showerror(_t("gui.login.verification_failed"), _t("gui.login.too_many_attempts"))
    return False

def _verify_email_otp(self, correct_otp, username, masked_email):
    """Show OTP verification dialog for email-based verification"""
    max_attempts = 3
    attempts = 0

    while attempts < max_attempts:
        # Create OTP entry dialog
        otp_dialog = tk.Toplevel(self.root)
        otp_dialog.title(_t("gui.login.email_verification"))
        otp_dialog.geometry("400x220")
        otp_dialog.transient(self.root)
        otp_dialog.grab_set()

        # Center the dialog
        otp_dialog.update_idletasks()
        x = (otp_dialog.winfo_screenwidth() // 2) - (otp_dialog.winfo_width() // 2)
        y = (otp_dialog.winfo_screenheight() // 2) - (otp_dialog.winfo_height() // 2)
        otp_dialog.geometry(f"+{x}+{y}")

        main_frame = ttk.Frame(otp_dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame,
            text=_t("gui.login.enter_6digit_code").format(email=masked_email),
            font=('Arial', 11),
            justify=tk.CENTER
        ).pack(pady=(0, 15))

        if attempts > 0:
            ttk.Label(
                main_frame,
                text=_t("gui.login.incorrect_code_remaining").format(attempts=max_attempts - attempts),
                foreground="red"
            ).pack(pady=(0, 10))

        otp_var = tk.StringVar()
        otp_entry = ttk.Entry(
            main_frame,
            textvariable=otp_var,
            font=('Courier', 20, 'bold'),
            width=8,
            justify=tk.CENTER
        )
        otp_entry.pack(pady=10)
        otp_entry.focus()

        result = {'verified': False, 'cancelled': False}

        def verify():
            entered = otp_var.get().strip()
            if entered == correct_otp:
                result['verified'] = True
            otp_dialog.destroy()

        def cancel():
            result['cancelled'] = True
            otp_dialog.destroy()

        otp_entry.bind('<Return>', lambda e: verify())

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)

        ttk.Button(btn_frame, text=_t("common.verify"), command=verify, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=cancel).pack(side=tk.LEFT, padx=5)

        otp_dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.root.wait_window(otp_dialog)

        if result['cancelled']:
            messagebox.showwarning(_t("gui.login.login_cancelled"), _t("gui.login.verification_cancelled"))
            return False

        if result['verified']:
            return True

        attempts += 1

    messagebox.showerror(_t("gui.login.verification_failed"), _t("gui.login.too_many_attempts"))
    return False

def _verify_email_otp_via_service(self, mfa_service, user_id, username, masked_email):
    """Verify OTP using MFA service (for codes sent via email)"""
    max_attempts = 3
    attempts = 0

    while attempts < max_attempts:
        # Create OTP entry dialog
        otp_dialog = tk.Toplevel(self.root)
        otp_dialog.title(_t("gui.login.email_verification"))
        otp_dialog.geometry("400x220")
        otp_dialog.transient(self.root)
        otp_dialog.grab_set()

        # Center the dialog
        otp_dialog.update_idletasks()
        x = (otp_dialog.winfo_screenwidth() // 2) - (otp_dialog.winfo_width() // 2)
        y = (otp_dialog.winfo_screenheight() // 2) - (otp_dialog.winfo_height() // 2)
        otp_dialog.geometry(f"+{x}+{y}")

        main_frame = ttk.Frame(otp_dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame,
            text=_t("gui.login.enter_6digit_code").format(email=masked_email),
            font=('Arial', 11),
            justify=tk.CENTER
        ).pack(pady=(0, 15))

        if attempts > 0:
            ttk.Label(
                main_frame,
                text=_t("gui.login.incorrect_code_remaining").format(attempts=max_attempts - attempts),
                foreground="red"
            ).pack(pady=(0, 10))

        otp_var = tk.StringVar()
        otp_entry = ttk.Entry(
            main_frame,
            textvariable=otp_var,
            font=('Courier', 20, 'bold'),
            width=8,
            justify=tk.CENTER
        )
        otp_entry.pack(pady=10)
        otp_entry.focus()

        result = {'verified': False, 'cancelled': False, 'code': ''}

        def verify():
            result['code'] = otp_var.get().strip()
            otp_dialog.destroy()

        def cancel():
            result['cancelled'] = True
            otp_dialog.destroy()

        otp_entry.bind('<Return>', lambda e: verify())

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)

        ttk.Button(btn_frame, text=_t("common.verify"), command=verify, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=cancel).pack(side=tk.LEFT, padx=5)

        otp_dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.root.wait_window(otp_dialog)

        if result['cancelled']:
            messagebox.showwarning(_t("gui.login.login_cancelled"), _t("gui.login.verification_cancelled"))
            return False

        # Verify using MFA service
        if result['code']:
            verify_result = mfa_service.verify_email_otp(user_id, result['code'])
            if verify_result.get('success'):
                return True

        attempts += 1

    messagebox.showerror(_t("gui.login.verification_failed"), _t("gui.login.too_many_attempts"))
    return False

def logout_user(self):
    """Logout current user"""
    if self.auth.current_user:
        username = self.auth.current_user['username']

        # Clear remember me token
        self._clear_remember_token()

        # Revoke all sessions if using EnhancedAuth
        try:
            from university_system.infrastructure.auth.enhanced_auth import EnhancedAuth
            if isinstance(self.auth, EnhancedAuth):
                user_id = self.auth.current_user.get('id')
                if user_id:
                    self.auth.logout_and_revoke_remember_me(user_id)
        except Exception as e:
            logger.debug(f"Could not revoke remember me tokens: {e}")

        self.auth.logout()
        self.update_status()
        messagebox.showinfo(_t("gui.login.logged_out"), _t("gui.login.goodbye").format(username=username))
        self.show_login_screen()
def toggle_login_logout(self):
    """Toggle between login and logout based on current authentication status"""
    if self.auth.current_user:
        self.logout_user()
    else:
        self.show_login_screen()
def update_login_logout_button(self):
    """Update the login/logout button text based on authentication status"""
    if hasattr(self, 'login_logout_btn'):
        if self.auth.current_user:
            self.login_logout_btn.config(text=_t("common.logout"))
        else:
            self.login_logout_btn.config(text=_t("common.login"))
def show_change_password(self):
    """Show change password dialog"""
    if not self.auth.current_user:
        messagebox.showerror(_t("common.error"), _t("gui.password.must_be_logged_in"))
        return

    # Implementation similar to AuthenticationGUI version
    password_window = tk.Toplevel(self.root)
    password_window.title(_t("gui.password.change_password"))
    password_window.geometry("400x250")
    password_window.transient(self.root)
    password_window.grab_set()

    main_frame = ttk.Frame(password_window, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Password change form
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
def check_session_timer(self):
    """Check session validity periodically"""
    try:
        # Check if window still exists
        if not self.root.winfo_exists():
            return

        if self.auth.current_user:
            if hasattr(self.auth, 'check_session') and not self.auth.check_session():
                messagebox.showwarning(_t("gui.session.expired"), _t("gui.session.expired_message"))
                self.update_status()
                self.show_login_screen()
    except Exception as e:
        print(f"Session check error: {e}")

    # Schedule next check only if window still exists
    try:
        if self.root.winfo_exists():
            self._session_timer_id = self.root.after(60000, self.check_session_timer)
    except Exception:
        pass  # Window destroyed, don't schedule
def switch_to_cli(self):
    """Switch to CLI mode by launching the CLI main function"""
    if messagebox.askyesno(_t("gui.switch_to_cli"), _t("gui.switch_to_cli_confirm")):
        try:
            import time
            import gc

            # Close database connections before switching
            try:
                from university_system.infrastructure.database.db import _connection_pool, _pool_lock
                with _pool_lock:
                    if _connection_pool is not None:
                        _connection_pool.close_all()
            except Exception:
                pass  # Ignore errors closing pool

            # Close auth database connections if any
            try:
                if hasattr(self, 'auth') and self.auth:
                    if hasattr(self.auth, 'db_manager') and self.auth.db_manager:
                        if hasattr(self.auth.db_manager, 'conn') and self.auth.db_manager.conn:
                            self.auth.db_manager.conn.close()
            except Exception:
                pass

            # Reset shared_context auth and clear initialization flags
            # This forces CLI to create a fresh UserAuth with proper initialization
            try:
                from university_system.infrastructure.shared_context import set_auth as reset_shared_auth
                from university_system.infrastructure.auth import UserAuth
                # Create a fresh UserAuth for CLI instead of reusing GUI's
                fresh_auth = UserAuth()
                reset_shared_auth(fresh_auth)
            except Exception:
                pass

            # Force garbage collection to release any lingering connections
            gc.collect()

            # Brief pause to allow WAL checkpoint and connection cleanup
            time.sleep(0.2)

            # Import and launch CLI main function
            from university_system.modules.shared.cli.cli_main import main as cli_main
            self.root.withdraw()  # Hide the GUI window
            self.root.quit()      # Exit the GUI event loop
            # Launch CLI in the same process
            cli_main()
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("gui.errors.failed_switch_cli", error=str(e)))
            self.root.deiconify()  # Show the GUI window again if CLI fails
def shutdown_system(self):
    """Shutdown the entire system"""
    if messagebox.askyesno(_t("gui.shutdown"), _t("gui.shutdown_confirm")):
        try:
            # Log the shutdown
            if self.auth and self.auth.current_user:
                username = self.auth.current_user['username']
                print(_t("gui.debug.system_shutdown_by_user", username=username))
            else:
                print(_t("gui.debug.system_shutdown"))

            # Schedule exit after callback completes to avoid Tkinter errors
            def do_shutdown():
                try:
                    self.root.quit()
                    self.root.destroy()
                except Exception:
                    pass
                finally:
                    import os
                    os._exit(0)

            # Use after() to schedule shutdown outside of button callback
            self.root.after(100, do_shutdown)
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("gui.errors.error_during_shutdown", error=str(e)))
def show_language_selector(self):
    """Show language selection dialog using centralized selector"""
    old_lang = get_current_language()

    # Use the centralized GUI language selector
    if GUI_LANG_SELECTOR_AVAILABLE:
        new_lang = show_gui_language_selector(self.root)
    else:
        messagebox.showwarning(
            _t("common.warning"),
            _t("gui.language_selector_unavailable")
        )
        return

    # If language changed, restart GUI
    if new_lang != old_lang:
        messagebox.showinfo(
            _t("gui.language_changed"),
            _t("gui.restart_required")
        )
        self.restart_gui()

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
        from university_system.infrastructure.auth.mfa_service import MFAService
        mfa_service = MFAService()

        # Get current MFA status (enabled methods) with error handling
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

        # Get all saved methods (including disabled ones)
        try:
            saved_methods_result = mfa_service.get_saved_mfa_methods(user_id)
        except Exception as e:
            print(f"Error getting saved MFA methods: {e}")
            saved_methods_result = {'success': False, 'methods': []}

        # Safely extract methods with null checking
        saved_methods = []
        if saved_methods_result and isinstance(saved_methods_result, dict) and saved_methods_result.get('success'):
            methods_data = saved_methods_result.get('methods')
            if methods_data and isinstance(methods_data, list):
                saved_methods = methods_data

        # Active methods vs saved (disabled) methods
        active_methods = []
        if methods_result and isinstance(methods_result, dict) and methods_result.get('success'):
            methods_data = methods_result.get('methods')
            if methods_data and isinstance(methods_data, list):
                active_methods = methods_data

        # Check if there are saved but disabled methods
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

        # Create the MFA settings dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("gui.mfa.settings_title"))
        dialog.geometry("500x450")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 500) // 2
        y = (dialog.winfo_screenheight() - 450) // 2
        dialog.geometry(f"+{x}+{y}")

        # Title
        title_label = tk.Label(dialog, text=_t("gui.mfa.settings_title"), font=('Arial', 16, 'bold'))
        title_label.pack(pady=(20, 15))

        # Status frame
        status_frame = tk.Frame(dialog, relief=tk.GROOVE, bd=2)
        status_frame.pack(padx=20, pady=10, fill=tk.X)

        # Current Setup Details
        tk.Label(status_frame, text=_t("gui.mfa.current_setup_details"), font=('Arial', 11, 'bold')).pack(pady=(10, 5))

        # Verification status
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

        # Helper function to mask identifiers
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

        # Show active methods
        if active_methods and len(active_methods) > 0:
            tk.Label(status_frame, text="", font=('Arial', 2)).pack()  # Spacer
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
            tk.Label(status_frame, text="", font=('Arial', 2)).pack()  # Spacer
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

        tk.Label(status_frame, text="").pack(pady=5)  # Bottom spacer

        # Buttons frame
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=20)

        def change_authentication():
            """Handle change/setup authentication"""
            # If there are saved disabled methods, ask if user wants to reuse
            if has_saved_disabled_methods and not active_methods:
                # Show choice dialog
                choice = messagebox.askyesnocancel(
                    _t("gui.mfa.reuse_settings_title"),
                    _t("gui.mfa.reuse_settings_message")
                )

                if choice is None:  # Cancel
                    return
                elif choice:  # Yes - reuse
                    dialog.destroy()
                    self._reenable_mfa_with_confirmation(user_id, username, user_email, mfa_service, saved_methods)
                else:  # No - new setup
                    dialog.destroy()
                    self._open_mfa_wizard(user_id, username)
            else:
                dialog.destroy()
                self._open_mfa_wizard(user_id, username)

        def turn_on_mfa():
            """Turn on MFA - reuse saved details or set up new"""
            if has_saved_disabled_methods:
                choice = messagebox.askyesnocancel(
                    _t("gui.mfa.turn_on_mfa_title"),
                    _t("gui.mfa.reuse_settings_message")
                )

                if choice is None:  # Cancel
                    return
                elif choice:  # Yes - reuse
                    dialog.destroy()
                    self._reenable_mfa_with_confirmation(user_id, username, user_email, mfa_service, saved_methods)
                else:  # No - new setup
                    dialog.destroy()
                    self._open_mfa_wizard(user_id, username)
            else:
                # No saved methods, go to wizard
                dialog.destroy()
                self._open_mfa_wizard(user_id, username)

        def turn_off_mfa():
            """Turn off MFA but preserve settings"""
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
                    # Disable MFA methods (but preserve them)
                    if active_methods:
                        result = mfa_service.disable_mfa(user_id)
                        if not result.get('success'):
                            messagebox.showerror(_t("common.error"), _t("gui.mfa.failed_disable_mfa", error=result.get('error')))
                            return

                    # Disable verification
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

        # Style buttons
        button_width = 22
        button_pady = 5

        # Show different buttons based on MFA status
        if active_methods or not is_verification_disabled:
            # MFA is on - show Change and Turn Off
            change_btn = tk.Button(
                button_frame,
                text=_t("gui.mfa.change_authentication"),
                command=change_authentication,
                width=button_width,
                bg="#2196F3",
                fg="white",
                font=('Arial', 10)
            )
            change_btn.pack(pady=button_pady)

            turnoff_btn = tk.Button(
                button_frame,
                text=_t("gui.mfa.turn_off_mfa_button"),
                command=turn_off_mfa,
                width=button_width,
                bg="#f44336",
                fg="white",
                font=('Arial', 10)
            )
            turnoff_btn.pack(pady=button_pady)
        else:
            # MFA is off - show Turn On
            turnon_btn = tk.Button(
                button_frame,
                text=_t("gui.mfa.turn_on_mfa_button"),
                command=turn_on_mfa,
                width=button_width,
                bg="#4CAF50",
                fg="white",
                font=('Arial', 10, 'bold')
            )
            turnon_btn.pack(pady=button_pady)

        close_btn = tk.Button(
            button_frame,
            text=_t("common.close"),
            command=dialog.destroy,
            width=button_width,
            font=('Arial', 10)
        )
        close_btn.pack(pady=button_pady)

        # Handle window close
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

    except ImportError as e:
        messagebox.showerror(_t("common.error"), f"MFA module not available: {e}")
    except Exception as e:
        messagebox.showerror(_t("common.error"), f"Error opening MFA setup: {e}")


def _reenable_mfa_with_confirmation(self, user_id, username, user_email, mfa_service, saved_methods):
    """Re-enable MFA with saved settings and send confirmation email"""
    try:
        # Re-enable MFA
        result = mfa_service.reenable_mfa(user_id)

        if not result or not result.get('success'):
            error_msg = result.get('error') if result else 'Unknown error'
            messagebox.showerror(_t("common.error"), _t("gui.mfa.failed_reenable", error=error_msg))
            return

        # Get the email from saved methods if available
        email_to_notify = user_email
        if saved_methods and isinstance(saved_methods, list):
            for method in saved_methods:
                if method and isinstance(method, dict):
                    if method.get('type') == 'email' and method.get('identifier'):
                        email_to_notify = method.get('identifier')
                        break

        # Send confirmation email externally via SMTP (security notification)
        if email_to_notify:
            try:
                # Use SMTP provider directly for external delivery
                from university_system.infrastructure.auth.email_otp_service import SMTPEmailProvider, MockEmailProvider

                # Try to use template with dictionary of variables
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

                # Try SMTP first, fall back to mock if not configured
                email_sent = False
                try:
                    smtp_provider = SMTPEmailProvider()
                    # Send using SMTP directly
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
                    # Fall back to mock provider (logs to file)
                    try:
                        mock_provider = MockEmailProvider()
                        mock_provider.send_otp(email_to_notify, f"MFA Re-enabled - {username}", username)
                    except Exception:
                        pass

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
                # MFA was re-enabled but email setup failed
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
        from university_system.modules.shared.gui.auth.mfa_gui import show_mfa_setup as mfa_setup_wizard

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
    username = self.auth.current_user.get('username')

    if not user_id:
        messagebox.showerror(_t("common.error"), _t("gui.mfa.unable_get_user_info"))
        return

    try:
        from university_system.infrastructure.auth.mfa_service import MFAService
        mfa_service = MFAService()

        # Check current status
        is_disabled = mfa_service.is_verification_disabled(user_id)

        if is_disabled:
            # Currently disabled - ask to enable
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
            # Currently enabled - ask to disable
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

def _save_remember_token(self, username, token, device_fingerprint):
    """Save remember me token to file"""
    try:
        import json
        from pathlib import Path

        token_file = Path.home() / '.university_system' / 'remember_me.json'
        token_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'username': username,
            'token': token,
            'device_fingerprint': device_fingerprint
        }

        with open(token_file, 'w') as f:
            json.dump(data, f)

    except Exception as e:
        logger.warning(f"Failed to save remember me token: {e}")

def _load_remember_token(self):
    """Load remember me token from file"""
    try:
        import json
        from pathlib import Path

        token_file = Path.home() / '.university_system' / 'remember_me.json'

        if not token_file.exists():
            return None

        with open(token_file, 'r') as f:
            data = json.load(f)

        return data

    except Exception as e:
        logger.warning(f"Failed to load remember me token: {e}")
        return None

def _clear_remember_token(self):
    """Clear remember me token from file"""
    try:
        from pathlib import Path

        token_file = Path.home() / '.university_system' / 'remember_me.json'

        if token_file.exists():
            token_file.unlink()

    except Exception as e:
        logger.warning(f"Failed to clear remember me token: {e}")

def _check_remember_me_token(self):
    """Check for remember me token and auto-login if valid"""
    try:
        # Make sure auth is available
        if not hasattr(self, 'auth') or not self.auth:
            return False

        from university_system.infrastructure.auth.enhanced_auth import EnhancedAuth

        # Load saved token
        token_data = self._load_remember_token()
        if not token_data:
            return False

        username = token_data.get('username')
        token = token_data.get('token')
        device_fingerprint = token_data.get('device_fingerprint')

        if not all([username, token, device_fingerprint]):
            return False

        # Try to use EnhancedAuth
        if not isinstance(self.auth, EnhancedAuth):
            from university_system.infrastructure.auth.enhanced_auth import create_enhanced_auth
            self.auth = create_enhanced_auth()

        # Verify token
        ip_address = "127.0.0.1"
        result = self.auth.verify_remember_me_token(
            token=token,
            device_fingerprint=device_fingerprint,
            ip_address=ip_address
        )

        if result.get('success'):
            # Update saved token if rotated
            if result.get('new_token'):
                self._save_remember_token(username, result['new_token'], device_fingerprint)

            logger.info(f"Auto-login successful for {username}")
            return True
        else:
            # Token invalid or expired - clear it
            self._clear_remember_token()
            return False

    except ImportError:
        # EnhancedAuth not available
        logger.debug("EnhancedAuth not available for remember me")
        return False
    except Exception as e:
        logger.warning(f"Remember me auto-login failed: {e}")
        return False
