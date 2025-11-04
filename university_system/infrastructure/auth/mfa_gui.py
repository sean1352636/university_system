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
from university_system.infrastructure.auth.mfa_service import MFAService


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

        self.title("Multi-Factor Authentication Setup")
        self.geometry("600x700")
        self.resizable(False, False)

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
            text="🔐 Multi-Factor Authentication Setup",
            font=("Arial", 16, "bold"),
            bg="#0066cc",
            fg="white"
        ).pack(pady=20)

        # Content area
        self.content_frame = tk.Frame(self, bg="white")
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Button frame
        self.button_frame = tk.Frame(self, bg="white")
        self.button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        self.back_btn = ttk.Button(
            self.button_frame,
            text="← Back",
            command=self._go_back
        )
        self.back_btn.pack(side=tk.LEFT, padx=5)

        self.next_btn = ttk.Button(
            self.button_frame,
            text="Next →",
            command=self._go_next
        )
        self.next_btn.pack(side=tk.RIGHT, padx=5)

        self.cancel_btn = ttk.Button(
            self.button_frame,
            text="Cancel",
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
        self.next_btn.config(text="Get Started →", command=self._show_method_selection)

        tk.Label(
            self.content_frame,
            text="Welcome to MFA Setup!",
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=(20, 10))

        info_text = """
Multi-Factor Authentication (MFA) adds an extra layer of
security to your account by requiring a second verification
step when you log in.

Why MFA is important:
• Protects your account even if your password is compromised
• Prevents unauthorized access to sensitive academic data
• Required for compliance with security policies

This wizard will guide you through setting up MFA methods:
• Authenticator App (TOTP) - Most secure, works offline
• SMS Text Messages - Convenient, requires phone
• Email Verification - Easy to use, universal access

You can set up multiple methods for backup access.
"""

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
        self.next_btn.config(text="Continue →", command=self._validate_methods)

        tk.Label(
            self.content_frame,
            text="Choose Your MFA Methods",
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=(10, 20))

        tk.Label(
            self.content_frame,
            text="Select at least one method (recommended: choose two for backup)",
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
            text="📱 Authenticator App (TOTP)",
            font=("Arial", 11, "bold"),
            bg="white",
            padx=15,
            pady=15
        )
        totp_frame.pack(fill=tk.X, pady=10)

        tk.Checkbutton(
            totp_frame,
            text="Use Authenticator App",
            variable=self.totp_var,
            font=("Arial", 10),
            bg="white"
        ).pack(anchor=tk.W)

        tk.Label(
            totp_frame,
            text="Works with: Google Authenticator, Authy, Microsoft Authenticator\n"
                 "✓ Most secure  ✓ Works offline  ✓ No phone number needed",
            font=("Arial", 9),
            bg="white",
            fg="gray",
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(5, 0))

        # SMS
        sms_frame = tk.LabelFrame(
            methods_frame,
            text="📲 SMS Text Message",
            font=("Arial", 11, "bold"),
            bg="white",
            padx=15,
            pady=15
        )
        sms_frame.pack(fill=tk.X, pady=10)

        tk.Checkbutton(
            sms_frame,
            text="Use SMS Verification",
            variable=self.sms_var,
            font=("Arial", 10),
            bg="white"
        ).pack(anchor=tk.W)

        tk.Label(
            sms_frame,
            text="Receive codes via text message to your mobile phone\n"
                 "✓ Convenient  ⚠ Requires cell signal  ⚠ Carrier charges may apply",
            font=("Arial", 9),
            bg="white",
            fg="gray",
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(5, 0))

        self.sms_phone_var = tk.StringVar()
        phone_frame = tk.Frame(sms_frame, bg="white")
        phone_frame.pack(anchor=tk.W, pady=(5, 0))
        tk.Label(phone_frame, text="Phone:", bg="white").pack(side=tk.LEFT)
        self.phone_entry = tk.Entry(phone_frame, textvariable=self.sms_phone_var, width=20)
        self.phone_entry.pack(side=tk.LEFT, padx=5)
        tk.Label(phone_frame, text="(e.g., +1-555-123-4567)", bg="white", fg="gray", font=("Arial", 8)).pack(side=tk.LEFT)

        # Email
        email_frame = tk.LabelFrame(
            methods_frame,
            text="📧 Email Verification",
            font=("Arial", 11, "bold"),
            bg="white",
            padx=15,
            pady=15
        )
        email_frame.pack(fill=tk.X, pady=10)

        tk.Checkbutton(
            email_frame,
            text="Use Email Verification",
            variable=self.email_var,
            font=("Arial", 10),
            bg="white"
        ).pack(anchor=tk.W)

        tk.Label(
            email_frame,
            text="Receive codes via email\n"
                 "✓ Universal access  ✓ No phone needed  ⚠ Less secure than TOTP",
            font=("Arial", 9),
            bg="white",
            fg="gray",
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(5, 0))

        self.email_var_input = tk.StringVar()
        email_input_frame = tk.Frame(email_frame, bg="white")
        email_input_frame.pack(anchor=tk.W, pady=(5, 0))
        tk.Label(email_input_frame, text="Email:", bg="white").pack(side=tk.LEFT)
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
                messagebox.showerror("Error", "Please enter a phone number for SMS verification")
                return
            selected_methods.append('sms')
            self.setup_data['phone'] = phone

        if self.email_var.get():
            email = self.email_var_input.get().strip()
            if not email or '@' not in email:
                messagebox.showerror("Error", "Please enter a valid email address")
                return
            selected_methods.append('email')
            self.setup_data['email'] = email

        if not selected_methods:
            messagebox.showerror("Error", "Please select at least one MFA method")
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
        self.next_btn.config(text="Verify & Continue →", command=self._verify_totp)

        tk.Label(
            self.content_frame,
            text="Setup Authenticator App",
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=(10, 20))

        # Generate TOTP secret and QR code
        result = self.mfa_service.setup_totp(self.user_id, self.username)

        if not result['success']:
            messagebox.showerror("Error", f"Failed to setup TOTP: {result.get('error', 'Unknown error')}")
            self.destroy()
            return

        self.setup_data['totp_secret'] = result['secret']
        self.setup_data['recovery_codes'] = result['recovery_codes']

        # Instructions
        instructions = """
1. Install an authenticator app on your phone:
   • Google Authenticator
   • Microsoft Authenticator
   • Authy

2. Open the app and scan the QR code below:
"""
        tk.Label(
            self.content_frame,
            text=instructions,
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
            text="Can't scan? Enter this code manually:",
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
            text="3. Enter the 6-digit code from your app to verify:",
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
            messagebox.showerror("Error", "Please enter a 6-digit code")
            return

        result = self.mfa_service.verify_totp(self.user_id, code)

        if not result['success']:
            messagebox.showerror("Error", "Invalid code. Please try again.")
            return

        messagebox.showinfo("Success", "Authenticator app setup successfully!")

        # Continue to next method or finish
        self._continue_setup()

    def _show_sms_setup(self):
        """Step 3b: SMS setup"""
        self._clear_content()
        self.current_step = 2

        tk.Label(
            self.content_frame,
            text="Verify SMS",
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=(10, 20))

        phone = self.setup_data.get('phone', '')

        tk.Label(
            self.content_frame,
            text=f"A verification code has been sent to:\n{phone}",
            font=("Arial", 11),
            bg="white"
        ).pack(pady=10)

        # Send SMS
        result = self.mfa_service.generate_sms_otp(self.user_id, phone)

        if not result['success']:
            messagebox.showerror("Error", f"Failed to send SMS: {result.get('error', 'Unknown error')}")
            self.destroy()
            return

        # For testing - show code
        if 'code' in result:
            tk.Label(
                self.content_frame,
                text=f"[DEV MODE] Code: {result['code']}",
                font=("Arial", 9),
                bg="white",
                fg="red"
            ).pack()

        tk.Label(
            self.content_frame,
            text="Enter the 6-digit code:",
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

        self.next_btn.config(text="Verify & Continue →", command=self._verify_sms)

    def _verify_sms(self):
        """Verify SMS code"""
        code = self.sms_code_var.get().strip()

        if not code or len(code) != 6:
            messagebox.showerror("Error", "Please enter a 6-digit code")
            return

        result = self.mfa_service.verify_sms_otp(self.user_id, code)

        if not result['success']:
            messagebox.showerror("Error", "Invalid code. Please try again.")
            return

        messagebox.showinfo("Success", "SMS verification setup successfully!")
        self._continue_setup()

    def _show_email_setup(self):
        """Step 3c: Email setup"""
        self._clear_content()
        self.current_step = 2

        tk.Label(
            self.content_frame,
            text="Verify Email",
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=(10, 20))

        email = self.setup_data.get('email', '')

        tk.Label(
            self.content_frame,
            text=f"A verification code has been sent to:\n{email}",
            font=("Arial", 11),
            bg="white"
        ).pack(pady=10)

        # Send email
        result = self.mfa_service.generate_email_otp(self.user_id, email)

        if not result['success']:
            messagebox.showerror("Error", f"Failed to send email: {result.get('error', 'Unknown error')}")
            self.destroy()
            return

        # For testing - show code
        if 'code' in result:
            tk.Label(
                self.content_frame,
                text=f"[DEV MODE] Code: {result['code']}",
                font=("Arial", 9),
                bg="white",
                fg="red"
            ).pack()

        tk.Label(
            self.content_frame,
            text="Enter the 6-digit code from your email:",
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

        self.next_btn.config(text="Verify & Continue →", command=self._verify_email)

    def _verify_email(self):
        """Verify email code"""
        code = self.email_code_var.get().strip()

        if not code or len(code) != 6:
            messagebox.showerror("Error", "Please enter a 6-digit code")
            return

        result = self.mfa_service.verify_email_otp(self.user_id, code)

        if not result['success']:
            messagebox.showerror("Error", "Invalid code. Please try again.")
            return

        messagebox.showinfo("Success", "Email verification setup successfully!")
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
        self.next_btn.config(text="Complete Setup ✓", command=self._complete_setup)

        tk.Label(
            self.content_frame,
            text="Save Your Recovery Codes",
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=(10, 10))

        tk.Label(
            self.content_frame,
            text="⚠️ IMPORTANT: Save these codes in a safe place!\n"
                 "Use them to access your account if you lose your MFA device.",
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
        codes_text.insert(tk.END, "Recovery Codes:\n")
        codes_text.insert(tk.END, "=" * 40 + "\n\n")
        for i, code in enumerate(recovery_codes, 1):
            codes_text.insert(tk.END, f"{i:2d}. {code}\n")
        codes_text.insert(tk.END, "\n" + "=" * 40 + "\n")
        codes_text.insert(tk.END, "\nEach code can only be used once.\n")
        codes_text.insert(tk.END, "Generate new codes after using several.")
        codes_text.config(state=tk.DISABLED)

        # Save button
        ttk.Button(
            self.content_frame,
            text="📥 Save to File",
            command=lambda: self._save_recovery_codes(recovery_codes)
        ).pack(pady=10)

        # Confirmation checkbox
        self.confirm_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.content_frame,
            text="I have saved these recovery codes in a safe place",
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
                    f.write("University System - MFA Recovery Codes\n")
                    f.write(f"Username: {self.username}\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 60 + "\n\n")
                    for i, code in enumerate(codes, 1):
                        f.write(f"{i:2d}. {code}\n")
                    f.write("\n" + "=" * 60 + "\n")
                    f.write("\nIMPORTANT SECURITY NOTES:\n")
                    f.write("• Each code can only be used once\n")
                    f.write("• Store this file in a secure location\n")
                    f.write("• Do not share these codes with anyone\n")
                    f.write("• Generate new codes if this file is compromised\n")

                messagebox.showinfo("Success", f"Recovery codes saved to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {e}")

    def _complete_setup(self):
        """Complete MFA setup"""
        if not self.confirm_var.get():
            messagebox.showwarning(
                "Confirmation Required",
                "Please confirm that you have saved your recovery codes before continuing."
            )
            return

        # Enable MFA for user
        result = self.mfa_service.enable_mfa(self.user_id)

        if result['success']:
            messagebox.showinfo(
                "Setup Complete!",
                "Multi-Factor Authentication has been successfully enabled for your account.\n\n"
                "You will be prompted for verification on your next login."
            )

            if self.on_complete:
                self.on_complete()

            self.destroy()
        else:
            messagebox.showerror("Error", f"Failed to enable MFA: {result.get('error', 'Unknown error')}")

    def _go_back(self):
        """Go to previous step"""
        if self.current_step > 0:
            self.current_step -= 1
            # Implement step navigation as needed

    def _go_next(self):
        """Go to next step"""
        # Default action, overridden by specific steps
        pass


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

        self.title("Verification Required")
        self.geometry("450x550")
        self.resizable(False, False)

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Get available methods
        methods_result = self.mfa_service.get_user_mfa_methods(user_id)
        self.available_methods = methods_result.get('methods', []) if methods_result['success'] else []

        if not self.available_methods:
            messagebox.showerror("Error", "No MFA methods configured")
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
            text="🔒 Verification Required",
            font=("Arial", 14, "bold"),
            bg="#0066cc",
            fg="white"
        ).pack(pady=20)

        # Content
        content_frame = tk.Frame(self, bg="white")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(
            content_frame,
            text=f"Welcome back, {self.username}!",
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=(0, 5))

        tk.Label(
            content_frame,
            text="Please verify your identity to continue",
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
            text="Trust this device for 30 days",
            variable=self.trust_device_var,
            font=("Arial", 9),
            bg="white"
        ).pack(pady=10)

        # Cancel button
        ttk.Button(
            content_frame,
            text="Cancel",
            command=self.destroy
        ).pack(pady=(10, 0))

    def _create_totp_tab(self):
        """Create TOTP verification tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="📱 Authenticator App")

        tk.Label(
            tab,
            text="Enter the 6-digit code from your\nauthenticator app:",
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
            text="Verify",
            command=self._verify_totp
        ).pack(pady=20)

    def _create_sms_tab(self, phone_number):
        """Create SMS verification tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="📲 SMS")

        tk.Label(
            tab,
            text=f"We'll send a code to:\n{phone_number or 'your phone'}",
            font=("Arial", 10),
            bg="white"
        ).pack(pady=20)

        ttk.Button(
            tab,
            text="Send Code",
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
            text="Verify",
            command=self._verify_sms
        ).pack(pady=20)

    def _create_email_tab(self, email):
        """Create Email verification tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="📧 Email")

        tk.Label(
            tab,
            text=f"We'll send a code to:\n{email or 'your email'}",
            font=("Arial", 10),
            bg="white"
        ).pack(pady=20)

        ttk.Button(
            tab,
            text="Send Code",
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
            text="Verify",
            command=self._verify_email
        ).pack(pady=20)

    def _create_recovery_tab(self):
        """Create recovery code tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="🔑 Recovery Code")

        tk.Label(
            tab,
            text="Lost access to your MFA device?\nUse a recovery code:",
            font=("Arial", 10),
            bg="white"
        ).pack(pady=20)

        tk.Label(
            tab,
            text="Format: XXXX-XXXX",
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
            text="Verify",
            command=self._verify_recovery
        ).pack(pady=20)

        tk.Label(
            tab,
            text="⚠️ Each recovery code can only be used once",
            font=("Arial", 8),
            bg="white",
            fg="red"
        ).pack(pady=10)

    def _verify_totp(self):
        """Verify TOTP code"""
        code = self.totp_code_var.get().strip()

        if not code or len(code) != 6:
            messagebox.showerror("Error", "Please enter a 6-digit code")
            return

        device_id = self._get_device_id() if self.trust_device_var.get() else None
        result = self.mfa_service.verify_totp(self.user_id, code, device_id)

        if result['success']:
            self._on_verification_success(result)
        else:
            messagebox.showerror("Error", "Invalid code. Please try again.")

    def _send_sms(self, phone_number):
        """Send SMS code"""
        result = self.mfa_service.generate_sms_otp(self.user_id, phone_number)

        if result['success']:
            messagebox.showinfo("Sent", "Verification code sent to your phone")
            # For dev - show code
            if 'code' in result:
                print(f"[DEV] SMS Code: {result['code']}")
        else:
            messagebox.showerror("Error", f"Failed to send SMS: {result.get('error', 'Unknown error')}")

    def _verify_sms(self):
        """Verify SMS code"""
        code = self.sms_code_var.get().strip()

        if not code or len(code) != 6:
            messagebox.showerror("Error", "Please enter a 6-digit code")
            return

        device_id = self._get_device_id() if self.trust_device_var.get() else None
        result = self.mfa_service.verify_sms_otp(self.user_id, code, device_id)

        if result['success']:
            self._on_verification_success(result)
        else:
            messagebox.showerror("Error", "Invalid code. Please try again.")

    def _send_email(self, email):
        """Send email code"""
        result = self.mfa_service.generate_email_otp(self.user_id, email)

        if result['success']:
            messagebox.showinfo("Sent", "Verification code sent to your email")
            # For dev - show code
            if 'code' in result:
                print(f"[DEV] Email Code: {result['code']}")
        else:
            messagebox.showerror("Error", f"Failed to send email: {result.get('error', 'Unknown error')}")

    def _verify_email(self):
        """Verify email code"""
        code = self.email_code_var.get().strip()

        if not code or len(code) != 6:
            messagebox.showerror("Error", "Please enter a 6-digit code")
            return

        device_id = self._get_device_id() if self.trust_device_var.get() else None
        result = self.mfa_service.verify_email_otp(self.user_id, code, device_id)

        if result['success']:
            self._on_verification_success(result)
        else:
            messagebox.showerror("Error", "Invalid code. Please try again.")

    def _verify_recovery(self):
        """Verify recovery code"""
        code = self.recovery_code_var.get().strip()

        if not code:
            messagebox.showerror("Error", "Please enter a recovery code")
            return

        device_id = self._get_device_id() if self.trust_device_var.get() else None
        result = self.mfa_service.verify_recovery_code(self.user_id, code, device_id)

        if result['success']:
            if result.get('remaining_codes', 0) <= 2:
                messagebox.showwarning(
                    "Warning",
                    f"Only {result['remaining_codes']} recovery codes remaining!\n"
                    "Please generate new codes from your account settings."
                )
            self._on_verification_success(result)
        else:
            messagebox.showerror("Error", "Invalid or already used recovery code")

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
        return hashlib.md5(device_info.encode()).hexdigest()


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
