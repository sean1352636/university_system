#!/usr/bin/env python3
"""
Multi-Factor Authentication (MFA) GUI Components
Provides user interfaces for MFA setup, verification, and management
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from PIL import Image, ImageTk
import io
from typing import Optional, Dict, Callable
from education_system.university_system.infrastructure.auth.mfa_service import MFAService
from education_system.university_system.core.institution_settings import get_mfa_recovery_format_hint
from education_system.university_system.core.i18n import get_text as _t, init_i18n
init_i18n()


class MFASetupWizard(tk.Toplevel):
    """
    Wizard for setting up MFA for the first time
    Guides user through choosing methods and completing setup
    """

    def __init__(self, parent, user_id: int, username: str, on_complete: Callable = None):
        super().__init__(parent)

        self.user_id = user_id
        self.username = username
        self.on_complete = on_complete
        self.mfa_service = MFAService()

        self.title(_t("mfa.setup.title"))
        self.geometry("700x850")
        self.resizable(True, True)
        self.minsize(600, 700)

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Current step
        self.current_step = 0
        self.setup_data = {}

        # Create UI
        self._create_widgets()
        self._show_welcome_step()

        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create main UI structure"""
        # Header
        header_frame = tk.Frame(self, bg="#0066cc", height=80)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        tk.Label(
            header_frame,
            text=_t("mfa.setup.header"),
            font=("Arial", 16, "bold"),
            bg="#0066cc",
            fg="white"
        ).pack(pady=20)

        # Scrollable content area
        content_container = tk.Frame(self, bg="white")
        content_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Canvas and scrollbar for scrolling
        self.content_canvas = tk.Canvas(content_container, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(content_container, orient="vertical", command=self.content_canvas.yview)

        self.content_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.content_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Inner frame for content
        self.content_frame = tk.Frame(self.content_canvas, bg="white")
        self.content_window = self.content_canvas.create_window((0, 0), window=self.content_frame, anchor="nw")

        # Configure scroll region when content changes
        def configure_scroll_region(event):
            self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))

        self.content_frame.bind("<Configure>", configure_scroll_region)

        # Make content frame width match canvas
        def configure_content_width(event):
            self.content_canvas.itemconfig(self.content_window, width=event.width)

        self.content_canvas.bind("<Configure>", configure_content_width)

        # Mousewheel scrolling
        def on_mousewheel(event):
            self.content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.content_canvas.bind("<Enter>", lambda e: self.content_canvas.bind_all("<MouseWheel>", on_mousewheel))
        self.content_canvas.bind("<Leave>", lambda e: self.content_canvas.unbind_all("<MouseWheel>"))

        # Button frame
        self.button_frame = tk.Frame(self, bg="white")
        self.button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        self.back_btn = ttk.Button(
            self.button_frame,
            text=_t("mfa.buttons.back"),
            command=self._go_back
        )
        self.back_btn.pack(side=tk.LEFT, padx=5)

        self.next_btn = ttk.Button(
            self.button_frame,
            text=_t("mfa.buttons.next"),
            command=self._go_next
        )
        self.next_btn.pack(side=tk.RIGHT, padx=5)

        self.cancel_btn = ttk.Button(
            self.button_frame,
            text=_t("common.cancel"),
            command=self.destroy
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=5)

    def _clear_content(self):
        """Clear content frame"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _show_welcome_step(self):
        """Step 1: Welcome and explanation"""
        self._clear_content()
        self.current_step = 0
        self.back_btn.config(state=tk.DISABLED)
        self.next_btn.config(text=_t("mfa.buttons.get_started"), command=self._show_method_selection)

        tk.Label(
            self.content_frame,
            text=_t("mfa.welcome.title"),
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=(20, 10))

        info_text = _t("mfa.welcome.info_text")

        tk.Label(
            self.content_frame,
            text=info_text,
            font=("Arial", 10),
            bg="white",
            justify=tk.LEFT
        ).pack(pady=10, padx=20)

    def _show_method_selection(self):
        """Step 2: Choose MFA methods"""
        self._clear_content()
        self.current_step = 1
        self.back_btn.config(state=tk.NORMAL)
        self.next_btn.config(text=_t("mfa.buttons.continue"), command=self._validate_methods)

        tk.Label(
            self.content_frame,
            text=_t("mfa.method_selection.title"),
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=(10, 20))

        tk.Label(
            self.content_frame,
            text=_t("mfa.method_selection.subtitle"),
            font=("Arial", 9),
            bg="white",
            fg="gray"
        ).pack()

        # Method checkboxes
        self.totp_var = tk.BooleanVar(value=True)
        self.sms_var = tk.BooleanVar(value=False)
        self.email_var = tk.BooleanVar(value=False)

        methods_frame = tk.Frame(self.content_frame, bg="white")
        methods_frame.pack(pady=20, fill=tk.BOTH, expand=True)

        # TOTP
        totp_frame = tk.LabelFrame(
            methods_frame,
            text=_t("mfa.methods.totp.label"),
            font=("Arial", 11, "bold"),
            bg="white",
            padx=15,
            pady=15
        )
        totp_frame.pack(fill=tk.X, pady=10)

        tk.Checkbutton(
            totp_frame,
            text=_t("mfa.methods.totp.use"),
            variable=self.totp_var,
            font=("Arial", 10),
            bg="white"
        ).pack(anchor=tk.W)

        tk.Label(
            totp_frame,
            text=_t("mfa.methods.totp.description"),
            font=("Arial", 9),
            bg="white",
            fg="gray",
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(5, 0))

        # SMS
        sms_frame = tk.LabelFrame(
            methods_frame,
            text=_t("mfa.methods.sms.label"),
            font=("Arial", 11, "bold"),
            bg="white",
            padx=15,
            pady=15
        )
        sms_frame.pack(fill=tk.X, pady=10)

        tk.Checkbutton(
            sms_frame,
            text=_t("mfa.methods.sms.use"),
            variable=self.sms_var,
            font=("Arial", 10),
            bg="white"
        ).pack(anchor=tk.W)

        tk.Label(
            sms_frame,
            text=_t("mfa.methods.sms.description"),
            font=("Arial", 9),
            bg="white",
            fg="gray",
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(5, 0))

        self.sms_phone_var = tk.StringVar()
        phone_frame = tk.Frame(sms_frame, bg="white")
        phone_frame.pack(anchor=tk.W, pady=(5, 0))
        tk.Label(phone_frame, text=_t("mfa.labels.phone"), bg="white").pack(side=tk.LEFT)
        self.phone_entry = tk.Entry(phone_frame, textvariable=self.sms_phone_var, width=20)
        self.phone_entry.pack(side=tk.LEFT, padx=5)
        tk.Label(phone_frame, text=_t("mfa.labels.phone_example"), bg="white", fg="gray", font=("Arial", 8)).pack(side=tk.LEFT)

        # Email
        email_frame = tk.LabelFrame(
            methods_frame,
            text=_t("mfa.methods.email.label"),
            font=("Arial", 11, "bold"),
            bg="white",
            padx=15,
            pady=15
        )
        email_frame.pack(fill=tk.X, pady=10)

        tk.Checkbutton(
            email_frame,
            text=_t("mfa.methods.email.use"),
            variable=self.email_var,
            font=("Arial", 10),
            bg="white"
        ).pack(anchor=tk.W)

        tk.Label(
            email_frame,
            text=_t("mfa.methods.email.description"),
            font=("Arial", 9),
            bg="white",
            fg="gray",
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(5, 0))

        self.email_var_input = tk.StringVar()
        email_input_frame = tk.Frame(email_frame, bg="white")
        email_input_frame.pack(anchor=tk.W, pady=(5, 0))
        tk.Label(email_input_frame, text=_t("mfa.labels.email"), bg="white").pack(side=tk.LEFT)
        self.email_entry = tk.Entry(email_input_frame, textvariable=self.email_var_input, width=30)
        self.email_entry.pack(side=tk.LEFT, padx=5)

    def _validate_methods(self):
        """Validate method selection and proceed"""
        selected_methods = []

        if self.totp_var.get():
            selected_methods.append('totp')

        if self.sms_var.get():
            phone = self.sms_phone_var.get().strip()
            if not phone:
                messagebox.showerror(_t("common.error"), _t("mfa.messages.enter_phone"))
                return
            selected_methods.append('sms')
            self.setup_data['phone'] = phone

        if self.email_var.get():
            email = self.email_var_input.get().strip()
            if not email or '@' not in email:
                messagebox.showerror(_t("common.error"), _t("mfa.messages.enter_valid_email"))
                return
            selected_methods.append('email')
            self.setup_data['email'] = email

        if not selected_methods:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.select_method"))
            return

        self.setup_data['methods'] = selected_methods

        # Show setup for first method
        if 'totp' in selected_methods:
            self._show_totp_setup()
        elif 'sms' in selected_methods:
            self._show_sms_setup()
        elif 'email' in selected_methods:
            self._show_email_setup()

    def _show_totp_setup(self):
        """Step 3a: TOTP setup"""
        self._clear_content()
        self.current_step = 2
        self.next_btn.config(text=_t("mfa.buttons.verify_continue"), command=self._verify_totp)

        tk.Label(
            self.content_frame,
            text=_t("mfa.totp_setup.title"),
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=(10, 20))

        # Generate TOTP secret and QR code
        result = self.mfa_service.setup_totp(self.user_id, self.username)

        if not result['success']:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.totp_setup_failed", error=result.get('error', _t("common.unknown_error"))))
            self.destroy()
            return

        self.setup_data['totp_secret'] = result['secret']
        self.setup_data['recovery_codes'] = result['recovery_codes']

        # Show the secret code prominently in a message box for easy copying
        messagebox.showinfo(
            _t("mfa.totp_setup.secret_code_title", default="Your MFA Setup Code"),
            f"{_t('mfa.totp_setup.secret_code_message', default='Enter this code in your authenticator app:')}\n\n"
            f"{result['secret']}\n\n"
            f"{_t('mfa.totp_setup.secret_code_note', default='You can also scan the QR code shown on screen.')}"
        )

        # Instructions
        tk.Label(
            self.content_frame,
            text=_t("mfa.totp_setup.instructions"),
            font=("Arial", 10),
            bg="white",
            justify=tk.LEFT
        ).pack(anchor=tk.W, padx=20)

        # Display QR code
        qr_image = Image.open(io.BytesIO(result['qr_code']))
        qr_image = qr_image.resize((200, 200), Image.Resampling.LANCZOS)
        qr_photo = ImageTk.PhotoImage(qr_image)

        qr_label = tk.Label(self.content_frame, image=qr_photo, bg="white")
        qr_label.image = qr_photo  # Keep reference
        qr_label.pack(pady=10)

        # Manual entry option
        tk.Label(
            self.content_frame,
            text=_t("mfa.totp_setup.manual_entry"),
            font=("Arial", 9),
            bg="white",
            fg="gray"
        ).pack()

        secret_frame = tk.Frame(self.content_frame, bg="#f0f0f0", relief=tk.RIDGE, borderwidth=2)
        secret_frame.pack(pady=5)
        tk.Label(
            secret_frame,
            text=result['secret'],
            font=("Courier", 12, "bold"),
            bg="#f0f0f0",
            fg="#0066cc"
        ).pack(padx=20, pady=10)

        # Verification
        tk.Label(
            self.content_frame,
            text=_t("mfa.totp_setup.enter_code"),
            font=("Arial", 10),
            bg="white"
        ).pack(pady=(20, 5), anchor=tk.W, padx=20)

        self.totp_code_var = tk.StringVar()
        code_entry = tk.Entry(
            self.content_frame,
            textvariable=self.totp_code_var,
            font=("Courier", 16),
            width=10,
            justify=tk.CENTER
        )
        code_entry.pack()
        code_entry.focus()

    def _verify_totp(self):
        """Verify TOTP code"""
        code = self.totp_code_var.get().strip()

        if not code or len(code) != 6:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.enter_6_digit"))
            return

        result = self.mfa_service.verify_totp(self.user_id, code)

        if not result['success']:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.invalid_code"))
            return

        messagebox.showinfo(_t("common.success"), _t("mfa.messages.totp_success"))

        # Continue to next method or finish
        self._continue_setup()

    def _show_sms_setup(self):
        """Step 3b: SMS setup"""
        self._clear_content()
        self.current_step = 2

        tk.Label(
            self.content_frame,
            text=_t("mfa.sms_setup.title"),
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=(10, 20))

        phone = self.setup_data.get('phone', '')

        tk.Label(
            self.content_frame,
            text=_t("mfa.sms_setup.code_sent", phone=phone),
            font=("Arial", 11),
            bg="white"
        ).pack(pady=10)

        # Send SMS
        result = self.mfa_service.generate_sms_otp(self.user_id, phone)

        if not result['success']:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.failed_send_sms", error=result.get('error', _t("common.unknown_error"))))
            self.destroy()
            return

        # For testing - show code
        if 'code' in result:
            tk.Label(
                self.content_frame,
                text=_t("mfa.dev_mode_code", code=result['code']),
                font=("Arial", 9),
                bg="white",
                fg="red"
            ).pack()

        tk.Label(
            self.content_frame,
            text=_t("mfa.labels.enter_6_digit_code"),
            font=("Arial", 10),
            bg="white"
        ).pack(pady=(20, 5))

        self.sms_code_var = tk.StringVar()
        code_entry = tk.Entry(
            self.content_frame,
            textvariable=self.sms_code_var,
            font=("Courier", 16),
            width=10,
            justify=tk.CENTER
        )
        code_entry.pack()
        code_entry.focus()

        self.next_btn.config(text=_t("mfa.buttons.verify_continue"), command=self._verify_sms)

    def _verify_sms(self):
        """Verify SMS code"""
        code = self.sms_code_var.get().strip()

        if not code or len(code) != 6:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.enter_6_digit"))
            return

        result = self.mfa_service.verify_sms_otp(self.user_id, code)

        if not result['success']:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.invalid_code"))
            return

        messagebox.showinfo(_t("common.success"), _t("mfa.messages.sms_success"))
        self._continue_setup()

    def _show_email_setup(self):
        """Step 3c: Email setup"""
        self._clear_content()
        self.current_step = 2

        tk.Label(
            self.content_frame,
            text=_t("mfa.email_setup.title"),
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=(10, 20))

        email = self.setup_data.get('email', '')

        tk.Label(
            self.content_frame,
            text=_t("mfa.email_setup.code_sent", email=email),
            font=("Arial", 11),
            bg="white"
        ).pack(pady=10)

        # Send email
        result = self.mfa_service.generate_email_otp(self.user_id, email)

        if not result['success']:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.failed_send_email", error=result.get('error', _t("common.unknown_error"))))
            self.destroy()
            return

        # For testing - show code
        if 'code' in result:
            tk.Label(
                self.content_frame,
                text=_t("mfa.dev_mode_code", code=result['code']),
                font=("Arial", 9),
                bg="white",
                fg="red"
            ).pack()

        tk.Label(
            self.content_frame,
            text=_t("mfa.email_setup.enter_code"),
            font=("Arial", 10),
            bg="white"
        ).pack(pady=(20, 5))

        self.email_code_var = tk.StringVar()
        code_entry = tk.Entry(
            self.content_frame,
            textvariable=self.email_code_var,
            font=("Courier", 16),
            width=10,
            justify=tk.CENTER
        )
        code_entry.pack()
        code_entry.focus()

        self.next_btn.config(text=_t("mfa.buttons.verify_continue"), command=self._verify_email)

    def _verify_email(self):
        """Verify email code"""
        code = self.email_code_var.get().strip()

        if not code or len(code) != 6:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.enter_6_digit"))
            return

        result = self.mfa_service.verify_email_otp(self.user_id, code)

        if not result['success']:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.invalid_code"))
            return

        messagebox.showinfo(_t("common.success"), _t("mfa.messages.email_success"))
        self._continue_setup()

    def _continue_setup(self):
        """Continue to next method or show recovery codes"""
        # Check if there are more methods to setup
        methods = self.setup_data.get('methods', [])
        completed_methods = self.setup_data.get('completed_methods', [])

        for method in methods:
            if method not in completed_methods:
                completed_methods.append(method)
                self.setup_data['completed_methods'] = completed_methods

                # Setup next method
                if method == 'totp' and 'sms' in methods and 'sms' not in completed_methods:
                    self._show_sms_setup()
                    return
                elif method == 'totp' and 'email' in methods and 'email' not in completed_methods:
                    self._show_email_setup()
                    return
                elif method == 'sms' and 'email' in methods and 'email' not in completed_methods:
                    self._show_email_setup()
                    return

        # All methods completed - show recovery codes
        self._show_recovery_codes()

    def _show_recovery_codes(self):
        """Step 4: Show recovery codes"""
        self._clear_content()
        self.current_step = 3
        self.back_btn.config(state=tk.DISABLED)
        self.next_btn.config(text=_t("mfa.buttons.complete_setup"), command=self._complete_setup)

        tk.Label(
            self.content_frame,
            text=_t("mfa.recovery.title"),
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=(10, 10))

        tk.Label(
            self.content_frame,
            text=_t("mfa.recovery.warning"),
            font=("Arial", 10),
            bg="#fff3cd",
            fg="#856404",
            justify=tk.LEFT,
            relief=tk.RIDGE,
            borderwidth=2,
            padx=10,
            pady=10
        ).pack(fill=tk.X, padx=20, pady=10)

        # Display recovery codes
        codes_text = scrolledtext.ScrolledText(
            self.content_frame,
            height=12,
            font=("Courier", 10),
            bg="#f8f9fa",
            relief=tk.RIDGE,
            borderwidth=2
        )
        codes_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        recovery_codes = self.setup_data.get('recovery_codes', [])
        # Generate recovery codes if not already created (e.g. email/SMS-only setup)
        if not recovery_codes:
            result = self.mfa_service.generate_recovery_codes(self.user_id)
            if result.get('success'):
                recovery_codes = result.get('codes', [])
                self.setup_data['recovery_codes'] = recovery_codes
        codes_text.insert(tk.END, _t("mfa.recovery.codes_header") + "\n")
        codes_text.insert(tk.END, "=" * 40 + "\n\n")
        for i, code in enumerate(recovery_codes, 1):
            codes_text.insert(tk.END, f"{i:2d}. {code}\n")
        codes_text.insert(tk.END, "\n" + "=" * 40 + "\n")
        codes_text.insert(tk.END, "\n" + _t("mfa.recovery.codes_note") + "\n")
        codes_text.insert(tk.END, _t("mfa.recovery.generate_new"))
        codes_text.config(state=tk.DISABLED)

        # Save button
        ttk.Button(
            self.content_frame,
            text=_t("mfa.buttons.save_to_file"),
            command=lambda: self._save_recovery_codes(recovery_codes)
        ).pack(pady=10)

        # Confirmation checkbox
        self.confirm_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.content_frame,
            text=_t("mfa.recovery.confirm_saved"),
            variable=self.confirm_var,
            font=("Arial", 10, "bold"),
            bg="white"
        ).pack(pady=10)

    def _save_recovery_codes(self, codes):
        """Save recovery codes to file"""
        from tkinter import filedialog
        from datetime import datetime

        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"recovery_codes_{datetime.now().strftime('%Y%m%d')}.txt"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(_t("mfa.recovery.file_header") + "\n")
                    f.write(f"{_t('mfa.recovery.file_username')}: {self.username}\n")
                    f.write(f"{_t('mfa.recovery.file_generated')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 60 + "\n\n")
                    for i, code in enumerate(codes, 1):
                        f.write(f"{i:2d}. {code}\n")
                    f.write("\n" + "=" * 60 + "\n")
                    f.write("\n" + _t("mfa.recovery.security_notes_header") + "\n")
                    f.write(_t("mfa.recovery.security_note_1") + "\n")
                    f.write(_t("mfa.recovery.security_note_2") + "\n")
                    f.write(_t("mfa.recovery.security_note_3") + "\n")
                    f.write(_t("mfa.recovery.security_note_4") + "\n")

                messagebox.showinfo(_t("common.success"), _t("mfa.recovery.saved_success", filename=filename))
            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("mfa.recovery.save_failed", error=str(e)))

    def _complete_setup(self):
        """Complete MFA setup"""
        if not self.confirm_var.get():
            messagebox.showwarning(
                _t("mfa.messages.confirmation_required"),
                _t("mfa.messages.confirm_codes_saved")
            )
            return

        # Enable MFA for user
        result = self.mfa_service.enable_mfa(self.user_id)

        if result['success']:
            messagebox.showinfo(
                _t("mfa.messages.setup_complete"),
                _t("mfa.messages.mfa_enabled")
            )

            if self.on_complete:
                try:
                    self.on_complete(True)
                except TypeError:
                    # Callback doesn't accept arguments
                    self.on_complete()

            self.destroy()
        else:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.enable_failed", error=result.get('error', _t("common.unknown_error"))))
            if self.on_complete:
                try:
                    self.on_complete(False)
                except TypeError:
                    pass

    def _go_back(self):
        """Go to previous step"""
        if self.current_step > 0:
            self.current_step -= 1
            # Implement step navigation as needed

    def _go_next(self):
        """
        Go to next step

        Default navigation method - overridden by specific wizard steps.
        Each step in the setup wizard configures this button's command
        to perform the appropriate action (e.g., _validate_methods,
        _verify_totp, _complete_setup).

        This method serves as a fallback if no specific action is set,
        though in practice it should always be overridden by the current step.
        """
        # If somehow called without being overridden, show error
        messagebox.showwarning(
            _t("mfa.messages.nav_error_title"),
            _t("mfa.messages.nav_error")
        )


class MFAVerificationDialog(tk.Toplevel):
    """
    Dialog for verifying MFA during login or sensitive operations
    """

    def __init__(self, parent, user_id: int, username: str, on_success: Callable = None):
        super().__init__(parent)

        self.user_id = user_id
        self.username = username
        self.on_success = on_success
        self.mfa_service = MFAService()
        self.verified = False

        self.title(_t("mfa.verification.title"))
        self.geometry("450x550")
        self.resizable(False, False)

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Get available methods
        methods_result = self.mfa_service.get_user_mfa_methods(user_id)
        self.available_methods = methods_result.get('methods', []) if methods_result['success'] else []

        if not self.available_methods:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.no_mfa_methods"))
            self.destroy()
            return

        # Create UI
        self._create_widgets()

        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create verification UI"""
        # Header
        header_frame = tk.Frame(self, bg="#0066cc", height=70)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        tk.Label(
            header_frame,
            text=_t("mfa.verification.header"),
            font=("Arial", 14, "bold"),
            bg="#0066cc",
            fg="white"
        ).pack(pady=20)

        # Content
        content_frame = tk.Frame(self, bg="white")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(
            content_frame,
            text=_t("mfa.verification.welcome", username=self.username),
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=(0, 5))

        tk.Label(
            content_frame,
            text=_t("mfa.verification.verify_identity"),
            font=("Arial", 10),
            bg="white",
            fg="gray"
        ).pack(pady=(0, 20))

        # Method tabs
        self.notebook = ttk.Notebook(content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Add tabs for each available method
        for method in self.available_methods:
            if method['type'] == 'totp':
                self._create_totp_tab()
            elif method['type'] == 'sms':
                self._create_sms_tab(method.get('identifier'))
            elif method['type'] == 'email':
                self._create_email_tab(method.get('identifier'))

        # Recovery code tab
        self._create_recovery_tab()

        # Device trust option
        self.trust_device_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            content_frame,
            text=_t("mfa.verification.trust_device"),
            variable=self.trust_device_var,
            font=("Arial", 9),
            bg="white"
        ).pack(pady=10)

        # Cancel button
        ttk.Button(
            content_frame,
            text=_t("common.cancel"),
            command=self.destroy
        ).pack(pady=(10, 0))

    def _create_totp_tab(self):
        """Create TOTP verification tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text=_t("mfa.tabs.authenticator"))

        tk.Label(
            tab,
            text=_t("mfa.verification.enter_totp_code"),
            font=("Arial", 10),
            bg="white"
        ).pack(pady=20)

        self.totp_code_var = tk.StringVar()
        code_entry = tk.Entry(
            tab,
            textvariable=self.totp_code_var,
            font=("Courier", 18),
            width=8,
            justify=tk.CENTER
        )
        code_entry.pack(pady=10)
        code_entry.focus()

        ttk.Button(
            tab,
            text=_t("mfa.buttons.verify"),
            command=self._verify_totp
        ).pack(pady=20)

    def _create_sms_tab(self, phone_number):
        """Create SMS verification tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text=_t("mfa.tabs.sms"))

        tk.Label(
            tab,
            text=_t("mfa.verification.send_code_to", destination=phone_number or _t("mfa.verification.your_phone")),
            font=("Arial", 10),
            bg="white"
        ).pack(pady=20)

        ttk.Button(
            tab,
            text=_t("mfa.buttons.send_code"),
            command=lambda: self._send_sms(phone_number)
        ).pack(pady=10)

        self.sms_code_var = tk.StringVar()
        code_entry = tk.Entry(
            tab,
            textvariable=self.sms_code_var,
            font=("Courier", 18),
            width=8,
            justify=tk.CENTER
        )
        code_entry.pack(pady=10)

        ttk.Button(
            tab,
            text=_t("mfa.buttons.verify"),
            command=self._verify_sms
        ).pack(pady=20)

    def _create_email_tab(self, email):
        """Create Email verification tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text=_t("mfa.tabs.email"))

        tk.Label(
            tab,
            text=_t("mfa.verification.send_code_to", destination=email or _t("mfa.verification.your_email")),
            font=("Arial", 10),
            bg="white"
        ).pack(pady=20)

        ttk.Button(
            tab,
            text=_t("mfa.buttons.send_code"),
            command=lambda: self._send_email(email)
        ).pack(pady=10)

        self.email_code_var = tk.StringVar()
        code_entry = tk.Entry(
            tab,
            textvariable=self.email_code_var,
            font=("Courier", 18),
            width=8,
            justify=tk.CENTER
        )
        code_entry.pack(pady=10)

        ttk.Button(
            tab,
            text=_t("mfa.buttons.verify"),
            command=self._verify_email
        ).pack(pady=20)

    def _create_recovery_tab(self):
        """Create recovery code tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text=_t("mfa.tabs.recovery"))

        tk.Label(
            tab,
            text=_t("mfa.verification.lost_access"),
            font=("Arial", 10),
            bg="white"
        ).pack(pady=20)

        tk.Label(
            tab,
            text=_t("mfa.verification.format_hint", format=get_mfa_recovery_format_hint()),
            font=("Arial", 9),
            bg="white",
            fg="gray"
        ).pack()

        self.recovery_code_var = tk.StringVar()
        code_entry = tk.Entry(
            tab,
            textvariable=self.recovery_code_var,
            font=("Courier", 14),
            width=12,
            justify=tk.CENTER
        )
        code_entry.pack(pady=10)

        ttk.Button(
            tab,
            text=_t("mfa.buttons.verify"),
            command=self._verify_recovery
        ).pack(pady=20)

        tk.Label(
            tab,
            text=_t("mfa.verification.recovery_warning"),
            font=("Arial", 8),
            bg="white",
            fg="red"
        ).pack(pady=10)

    def _verify_totp(self):
        """Verify TOTP code"""
        code = self.totp_code_var.get().strip()

        if not code or len(code) != 6:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.enter_6_digit"))
            return

        device_id = self._get_device_id() if self.trust_device_var.get() else None
        result = self.mfa_service.verify_totp(self.user_id, code, device_id)

        if result['success']:
            self._on_verification_success(result)
        else:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.invalid_code"))

    def _send_sms(self, phone_number):
        """Send SMS code"""
        result = self.mfa_service.generate_sms_otp(self.user_id, phone_number)

        if result['success']:
            messagebox.showinfo(_t("mfa.messages.sent"), _t("mfa.messages.code_sent_phone"))
            # For dev - show code
            if 'code' in result:
                print(f"[DEV] SMS Code: {result['code']}")
        else:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.failed_send_sms", error=result.get('error', _t("common.unknown_error"))))

    def _verify_sms(self):
        """Verify SMS code"""
        code = self.sms_code_var.get().strip()

        if not code or len(code) != 6:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.enter_6_digit"))
            return

        device_id = self._get_device_id() if self.trust_device_var.get() else None
        result = self.mfa_service.verify_sms_otp(self.user_id, code, device_id)

        if result['success']:
            self._on_verification_success(result)
        else:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.invalid_code"))

    def _send_email(self, email):
        """Send email code"""
        result = self.mfa_service.generate_email_otp(self.user_id, email)

        if result['success']:
            messagebox.showinfo(_t("mfa.messages.sent"), _t("mfa.messages.code_sent_email"))
            # For dev - show code
            if 'code' in result:
                print(f"[DEV] Email Code: {result['code']}")
        else:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.failed_send_email", error=result.get('error', _t("common.unknown_error"))))

    def _verify_email(self):
        """Verify email code"""
        code = self.email_code_var.get().strip()

        if not code or len(code) != 6:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.enter_6_digit"))
            return

        device_id = self._get_device_id() if self.trust_device_var.get() else None
        result = self.mfa_service.verify_email_otp(self.user_id, code, device_id)

        if result['success']:
            self._on_verification_success(result)
        else:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.invalid_code"))

    def _verify_recovery(self):
        """Verify recovery code"""
        code = self.recovery_code_var.get().strip()

        if not code:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.enter_recovery_code"))
            return

        device_id = self._get_device_id() if self.trust_device_var.get() else None
        result = self.mfa_service.verify_recovery_code(self.user_id, code, device_id)

        if result['success']:
            if result.get('remaining_codes', 0) <= 2:
                messagebox.showwarning(
                    _t("common.warning"),
                    _t("mfa.messages.recovery_codes_warning", count=result['remaining_codes'])
                )
            self._on_verification_success(result)
        else:
            messagebox.showerror(_t("common.error"), _t("mfa.messages.invalid_recovery_code"))

    def _on_verification_success(self, result):
        """Handle successful verification"""
        self.verified = True

        if self.on_success:
            self.on_success(result)

        self.destroy()

    def _get_device_id(self):
        """Generate device identifier"""
        import platform
        import hashlib

        # Create simple device fingerprint
        device_info = f"{platform.node()}_{platform.system()}_{platform.machine()}"
        return hashlib.sha256(device_info.encode()).hexdigest()


# Convenience functions
def show_mfa_setup(parent, user_id: int, username: str, on_complete: Callable = None):
    """Show MFA setup wizard"""
    wizard = MFASetupWizard(parent, user_id, username, on_complete)
    parent.wait_window(wizard)


def show_mfa_verification(parent, user_id: int, username: str, on_success: Callable = None) -> bool:
    """Show MFA verification dialog and return verification status"""
    dialog = MFAVerificationDialog(parent, user_id, username, on_success)
    parent.wait_window(dialog)
    return dialog.verified


if __name__ == '__main__':
    # Test MFA GUI
    root = tk.Tk()
    root.withdraw()

    # Test setup wizard
    show_mfa_setup(root, user_id=1, username="test_user")

    # Test verification dialog
    # verified = show_mfa_verification(root, user_id=1, username="test_user")
    # print(f"Verification result: {verified}")

    root.mainloop()
