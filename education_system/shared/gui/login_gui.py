"""Universal login window for the Education System.

Authenticates users against the shared auth database, then presents
the list of systems they have access to. The chosen system and the
user's role in that system are returned to the caller.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.shared.auth.core import UserAuth
from education_system.shared.auth.db import connect
from education_system.shared.auth.exceptions import AuthError, MFAError
from education_system.shared.auth.defaults import SYSTEMS

logger = logging.getLogger(__name__)

# Colour constants
_HEADER_BG = "#2c3e50"
_CARD_BG = "white"
_BG = "#f0f0f0"

# System button colours
_SYSTEM_COLOURS = {
    "university": ("#2980b9", "#3498db"),
    "college":    ("#27ae60", "#2ecc71"),
    "school":     ("#8e44ad", "#9b59b6"),
    "primary":    ("#e67e22", "#f39c12"),
}


class UniversalLoginWindow(tk.Tk):
    """Full-screen login window that authenticates and selects a system.

    After a successful login and system selection, the following attributes
    are populated:
        ``user_info``   – dict returned by ``UserAuth.login()``
        ``system_key``  – e.g. ``"college"``, ``"school"``, ``"primary"``
        ``system_role`` – the user's role in the chosen system
        ``auth``        – the ``UserAuth`` instance (session active)
    """

    def __init__(self, auth_db_path: str | None = None):
        super().__init__()
        self.title("Education System - Login")
        self.geometry("500x580")
        self.resizable(False, False)
        self.configure(bg=_BG)

        self._auth = UserAuth(auth_db_path)
        self._auth_db_path = auth_db_path

        # Results (populated on success)
        self.user_info: dict | None = None
        self.system_key: str | None = None
        self.system_role: str | None = None
        self.auth: UserAuth | None = None

        # Centre on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 500) // 2
        y = (self.winfo_screenheight() - 580) // 2
        self.geometry(f"+{x}+{y}")

        self._build_login_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    #  Login screen
    # ------------------------------------------------------------------

    def _build_login_ui(self):
        """Build the login form."""
        # Clear any existing widgets
        for w in self.winfo_children():
            w.destroy()

        self.geometry("500x440")

        # Header
        header = tk.Frame(self, bg=_HEADER_BG, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Education System",
            font=("Helvetica", 22, "bold"), fg="white", bg=_HEADER_BG,
        ).pack(expand=True)

        # Subtitle
        tk.Label(
            self, text="Sign in to continue",
            font=("Helvetica", 11), fg="#7f8c8d", bg=_BG,
        ).pack(pady=(20, 15))

        # Card
        card = tk.Frame(self, bg=_CARD_BG, bd=1, relief="solid", padx=40, pady=30)
        card.pack(padx=50)

        # Username
        tk.Label(
            card, text="Username", font=("Helvetica", 10, "bold"),
            bg=_CARD_BG, anchor="w",
        ).pack(fill="x", pady=(0, 4))
        self._username_var = tk.StringVar()
        username_entry = ttk.Entry(card, textvariable=self._username_var, width=30,
                                   font=("Helvetica", 11))
        username_entry.pack(fill="x", ipady=4, pady=(0, 14))
        username_entry.focus_set()

        # Password
        tk.Label(
            card, text="Password", font=("Helvetica", 10, "bold"),
            bg=_CARD_BG, anchor="w",
        ).pack(fill="x", pady=(0, 4))
        self._password_var = tk.StringVar()
        password_entry = ttk.Entry(card, textvariable=self._password_var, width=30,
                                   show="*", font=("Helvetica", 11))
        password_entry.pack(fill="x", ipady=4, pady=(0, 4))

        # Show password toggle
        self._show_pw_var = tk.BooleanVar()
        def _toggle_pw():
            password_entry.configure(show="" if self._show_pw_var.get() else "*")
        tk.Checkbutton(
            card, text="Show password", variable=self._show_pw_var,
            command=_toggle_pw, bg=_CARD_BG, font=("Helvetica", 9),
            activebackground=_CARD_BG,
        ).pack(anchor="w", pady=(0, 12))

        # Bind Enter
        username_entry.bind("<Return>", lambda _: self._do_login())
        password_entry.bind("<Return>", lambda _: self._do_login())

        # Login button
        ttk.Button(card, text="Login", command=self._do_login).pack(fill="x", ipady=6)

        # Error label
        self._error_var = tk.StringVar()
        self._error_lbl = tk.Label(
            card, textvariable=self._error_var,
            font=("Helvetica", 9), fg="red", bg=_CARD_BG, wraplength=280,
        )
        self._error_lbl.pack(fill="x", pady=(12, 0))

        # Forgot password link
        forgot_link = tk.Label(
            card, text="Forgot Password?",
            font=("Helvetica", 9, "underline"), fg="#2980b9",
            bg=_CARD_BG, cursor="hand2",
        )
        forgot_link.pack(anchor="e", pady=(8, 0))
        forgot_link.bind("<Button-1>", lambda _: self._show_forgot_username())

        # Hint
        tk.Label(
            self, text="Default: superadmin / SuperAdmin@123",
            font=("Helvetica", 9), fg="#95a5a6", bg=_BG,
        ).pack(pady=(10, 0))

    # ------------------------------------------------------------------
    #  Login action
    # ------------------------------------------------------------------

    def _do_login(self):
        """Validate credentials and dispatch to MFA or system picker."""
        username = self._username_var.get().strip()
        password = self._password_var.get()

        if not username or not password:
            self._error_var.set("Please enter both username and password.")
            return

        try:
            user_info = self._auth.login(username, password)
        except AuthError as exc:
            self._error_var.set(str(exc))
            return
        except Exception as exc:
            logger.error("Login error: %s", exc, exc_info=True)
            self._error_var.set("An unexpected error occurred. Please try again.")
            return

        # Stash the just-used password so the forced-change screen can
        # prefill the "Current Password" field (typically a temp password).
        self._last_login_password = password

        # Handle MFA challenge
        if user_info.get("mfa_required"):
            logger.info("MFA required for user_id=%s, showing MFA screen", user_info["user_id"])
            self._show_mfa(user_info["user_id"])
            return

        self._on_login_success(user_info)

    def _show_mfa(self, user_id: int):
        """Show inline MFA verification.

        Sends a 6-digit email OTP using the shared email sender.
        If email delivery fails, the code is shown on screen as a fallback.
        TOTP codes from an authenticator app are always accepted too.
        """
        import hashlib
        import secrets
        from datetime import datetime, timedelta

        # Try to send an email OTP before building the UI
        email_sent = False
        email_fallback_code = None
        masked_email = None
        self._pending_email_otp = None  # (hash, expiry)

        try:
            # Look up the user's email — prefer the MFA-registered email
            # from the university mfa_methods table, fall back to shared auth
            conn = connect(self._auth_db_path)
            try:
                row = conn.execute(
                    "SELECT username, email FROM users WHERE id = ?", (user_id,)
                ).fetchone()
                username = row["username"] if row else None
                user_email = row["email"] if row else None
            finally:
                conn.close()

            # Check university mfa_methods for a real email
            if username:
                try:
                    from education_system.university_system.infrastructure.database.db import get_connection
                    uconn = get_connection()
                    try:
                        # Try by shared auth user_id first, then by username
                        for uid_val in (user_id, None):
                            if uid_val is not None:
                                mrow = uconn.execute(
                                    "SELECT method_identifier FROM mfa_methods "
                                    "WHERE user_id = ? AND method_type = 'email' "
                                    "AND is_enabled = 1 AND method_identifier IS NOT NULL "
                                    "ORDER BY id DESC LIMIT 1",
                                    (uid_val,),
                                ).fetchone()
                            else:
                                # Look up university user_id by username
                                urow = uconn.execute(
                                    "SELECT id FROM user_accounts WHERE username = ?",
                                    (username,),
                                ).fetchone()
                                if not urow:
                                    break
                                ua_id = urow[0] if isinstance(urow, tuple) else urow["id"]
                                mrow = uconn.execute(
                                    "SELECT method_identifier FROM mfa_methods "
                                    "WHERE user_id = ? AND method_type = 'email' "
                                    "AND is_enabled = 1 AND method_identifier IS NOT NULL "
                                    "ORDER BY id DESC LIMIT 1",
                                    (ua_id,),
                                ).fetchone()
                            if mrow:
                                mfa_email = mrow[0] if isinstance(mrow, tuple) else mrow["method_identifier"]
                                if mfa_email:
                                    user_email = mfa_email
                                    break
                    finally:
                        uconn.close()
                except ImportError:
                    pass
                except Exception:
                    pass

            if user_email and username:
                # Mask email for display
                parts = user_email.split("@")
                masked_email = (
                    parts[0][:2] + "***@" + parts[1]
                    if len(parts) == 2
                    else user_email
                )

                # Generate a 6-digit code and hash it with PBKDF2-HMAC-SHA256
                # so the in-memory pending-OTP tuple never holds a bare digest
                # of user-supplied data (py/weak-sensitive-data-hashing).
                code = "".join(str(secrets.randbelow(10)) for _ in range(6))
                code_hash = hashlib.pbkdf2_hmac(
                    "sha256",
                    code.encode("utf-8"),
                    b"otp-verify",
                    10_000,
                ).hex()
                expiry = datetime.now() + timedelta(minutes=10)
                self._pending_email_otp = (code_hash, expiry)

                logger.info("Sending MFA OTP to %s for user '%s'", user_email, username)

                # Send via shared email sender (no university imports)
                try:
                    from education_system.shared.email.otp_sender import send_otp
                    result = send_otp(user_email, code, username=username)
                    logger.info("OTP send result: %s", result)
                    if result.get("success"):
                        email_sent = True
                    else:
                        logger.warning("Email send failed, showing code on screen")
                        email_fallback_code = code
                except ImportError as exc:
                    logger.warning("shared.email.otp_sender not available: %s", exc)
                    email_fallback_code = code
                except Exception as exc:
                    logger.warning("OTP send error: %s", exc)
                    email_fallback_code = code
            else:
                logger.info("No email found for MFA (email=%s, username=%s)", user_email, username)
        except Exception as exc:
            logger.warning("MFA email lookup failed: %s", exc, exc_info=True)

        for w in self.winfo_children():
            w.destroy()

        self.geometry("500x380")

        header = tk.Frame(self, bg=_HEADER_BG, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Two-Factor Authentication",
            font=("Helvetica", 18, "bold"), fg="white", bg=_HEADER_BG,
        ).pack(expand=True)

        card = tk.Frame(self, bg=_CARD_BG, bd=1, relief="solid", padx=40, pady=30)
        card.pack(padx=50, pady=30)

        if email_sent and masked_email:
            tk.Label(
                card,
                text=f"A verification code has been sent to\n{masked_email}",
                font=("Helvetica", 11), bg=_CARD_BG, justify="center",
            ).pack(pady=(0, 10))
        elif email_fallback_code and masked_email:
            tk.Label(
                card,
                text=f"Email delivery to {masked_email} failed.\nYour code is shown below:",
                font=("Helvetica", 10), bg=_CARD_BG, fg="#e67e22", justify="center",
            ).pack(pady=(0, 5))
            tk.Label(
                card,
                text=email_fallback_code,
                font=("Courier", 22, "bold"), bg=_CARD_BG, fg="#2c3e50",
            ).pack(pady=(0, 10))
        else:
            tk.Label(
                card, text="Enter your authentication code:",
                font=("Helvetica", 11), bg=_CARD_BG,
            ).pack(pady=(0, 10))

        self._mfa_var = tk.StringVar()
        mfa_entry = ttk.Entry(card, textvariable=self._mfa_var, width=20,
                              font=("Helvetica", 14), justify="center")
        mfa_entry.pack(ipady=4, pady=(0, 15))
        mfa_entry.focus_set()
        mfa_entry.bind("<Return>", lambda _: self._verify_mfa(user_id))

        ttk.Button(card, text="Verify", command=lambda: self._verify_mfa(user_id)).pack(fill="x", ipady=4)

        self._mfa_error_var = tk.StringVar()
        tk.Label(card, textvariable=self._mfa_error_var, fg="red", bg=_CARD_BG,
                 font=("Helvetica", 9)).pack(pady=(10, 0))

        ttk.Button(card, text="Back to Login", command=self._build_login_ui).pack(fill="x", pady=(10, 0))

    def _verify_mfa(self, user_id: int):
        """Check the entered MFA code (TOTP or recovery) and proceed on success."""
        import hashlib
        import hmac
        from datetime import datetime

        code = self._mfa_var.get().strip()
        if not code:
            self._mfa_error_var.set("Please enter a code.")
            return

        # Try in-memory email OTP verification first. The OTP is hashed with
        # PBKDF2-HMAC-SHA256 (rather than a bare HMAC) so CodeQL's
        # py/weak-sensitive-data-hashing query treats it as a password-safe
        # KDF. Iteration count is modest because the OTP is short-lived and
        # lives only in-process memory.
        pending = getattr(self, "_pending_email_otp", None)
        if pending:
            code_hash, expiry = pending
            if datetime.now() < expiry:
                candidate_hash = hashlib.pbkdf2_hmac(
                    "sha256",
                    code.encode("utf-8"),
                    b"otp-verify",
                    10_000,
                ).hex()
                if hmac.compare_digest(candidate_hash, code_hash):
                    self._pending_email_otp = None  # consume
                    user_info = self._auth.complete_mfa_login(user_id)
                    self._on_login_success(user_info)
                    return

        # Fall back to shared auth TOTP / recovery code verification.
        # MFAError is a sibling of AuthError (not a subclass) and bubbled
        # up uncaught when the user only had email-MFA enrolled (no TOTP
        # secret on file) — verify_totp would raise "MFA is not set up"
        # and crash the dialog. core.verify_mfa now swallows MFAError
        # internally, but we keep both in the except for defence in
        # depth in case any other auth backend re-raises.
        try:
            user_info = self._auth.verify_mfa(user_id, code)
        except (AuthError, MFAError) as exc:
            self._mfa_error_var.set(str(exc) or "Invalid MFA code.")
            return

        self._on_login_success(user_info)

    # ------------------------------------------------------------------
    #  Forgot password flow
    # ------------------------------------------------------------------

    def _show_forgot_username(self):
        """Step 1: Ask for username to look up security questions."""
        for w in self.winfo_children():
            w.destroy()

        self.geometry("500x380")

        header = tk.Frame(self, bg=_HEADER_BG, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Forgot Password",
            font=("Helvetica", 18, "bold"), fg="white", bg=_HEADER_BG,
        ).pack(expand=True)

        tk.Label(
            self, text="Enter your username to verify your identity",
            font=("Helvetica", 11), fg="#7f8c8d", bg=_BG,
        ).pack(pady=(20, 15))

        card = tk.Frame(self, bg=_CARD_BG, bd=1, relief="solid", padx=40, pady=30)
        card.pack(padx=50)

        tk.Label(
            card, text="Username", font=("Helvetica", 10, "bold"),
            bg=_CARD_BG, anchor="w",
        ).pack(fill="x", pady=(0, 4))
        self._forgot_username_var = tk.StringVar()
        username_entry = ttk.Entry(
            card, textvariable=self._forgot_username_var, width=30,
            font=("Helvetica", 11),
        )
        username_entry.pack(fill="x", ipady=4, pady=(0, 14))
        username_entry.focus_set()
        username_entry.bind("<Return>", lambda _: self._forgot_lookup_questions())

        ttk.Button(
            card, text="Continue", command=self._forgot_lookup_questions,
        ).pack(fill="x", ipady=6)

        self._forgot_error_var = tk.StringVar()
        tk.Label(
            card, textvariable=self._forgot_error_var,
            font=("Helvetica", 9), fg="red", bg=_CARD_BG, wraplength=280,
        ).pack(fill="x", pady=(12, 0))

        ttk.Button(
            card, text="Back to Login", command=self._build_login_ui,
        ).pack(fill="x", pady=(10, 0))

    def _forgot_lookup_questions(self):
        """Look up security questions for the entered username."""
        username = self._forgot_username_var.get().strip()
        if not username:
            self._forgot_error_var.set("Please enter your username.")
            return

        try:
            from education_system.shared.auth.forgot_password import ForgotPasswordService
            svc = ForgotPasswordService(self._auth_db_path)
            questions = svc.get_questions_for_user(username)
        except Exception:
            # Generic message — specific reason is logged server-side
            self._forgot_error_var.set(
                "Unable to verify your identity. Please try again "
                "or contact an administrator."
            )
            return

        self._show_forgot_questions(username, questions)

    def _show_forgot_questions(self, username: str, questions: list[dict]):
        """Step 2: Show security questions for the user to answer."""
        for w in self.winfo_children():
            w.destroy()

        height = 320 + (len(questions) * 80)
        self.geometry(f"500x{height}")

        header = tk.Frame(self, bg=_HEADER_BG, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Security Questions",
            font=("Helvetica", 18, "bold"), fg="white", bg=_HEADER_BG,
        ).pack(expand=True)

        tk.Label(
            self, text=f"Answer all questions for: {username}",
            font=("Helvetica", 11), fg="#7f8c8d", bg=_BG,
        ).pack(pady=(15, 10))

        card = tk.Frame(self, bg=_CARD_BG, bd=1, relief="solid", padx=40, pady=25)
        card.pack(padx=50)

        self._forgot_answer_vars = {}
        for i, q in enumerate(questions):
            tk.Label(
                card, text=q["question"],
                font=("Helvetica", 10, "bold"), bg=_CARD_BG, anchor="w",
            ).pack(fill="x", pady=(10 if i > 0 else 0, 4))
            var = tk.StringVar()
            entry = ttk.Entry(card, textvariable=var, width=30, font=("Helvetica", 11))
            entry.pack(fill="x", ipady=4)
            if i == 0:
                entry.focus_set()
            self._forgot_answer_vars[q["id"]] = var

        ttk.Button(
            card, text="Verify & Reset Password",
            command=lambda: self._forgot_verify(username),
        ).pack(fill="x", ipady=6, pady=(15, 0))

        self._forgot_q_error_var = tk.StringVar()
        tk.Label(
            card, textvariable=self._forgot_q_error_var,
            font=("Helvetica", 9), fg="red", bg=_CARD_BG, wraplength=280,
        ).pack(fill="x", pady=(10, 0))

        ttk.Button(
            card, text="Back to Login", command=self._build_login_ui,
        ).pack(fill="x", pady=(10, 0))

    @staticmethod
    def _get_client_ip() -> str | None:
        """Best-effort local IP for audit trails in desktop GUI."""
        try:
            import socket
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

    def _forgot_verify(self, username: str):
        """Verify answers and show temp password on success."""
        answers = {qid: var.get() for qid, var in self._forgot_answer_vars.items()}

        if any(not a.strip() for a in answers.values()):
            self._forgot_q_error_var.set("Please answer all questions.")
            return

        try:
            from education_system.shared.auth.forgot_password import ForgotPasswordService
            svc = ForgotPasswordService(self._auth_db_path)
            result = svc.verify_answers_and_reset(
                username, answers, ip_address=self._get_client_ip(),
            )
        except Exception as exc:
            self._forgot_q_error_var.set(str(exc))
            return

        if result.get("delivered_via_email"):
            self._show_temp_password_emailed(result)
        else:
            self._show_temp_password(result)

    def _show_temp_password_emailed(self, reset_info: dict):
        """MFA flow: confirm temp password was sent to the user's email."""
        for w in self.winfo_children():
            w.destroy()
        self.geometry("500x420")

        header = tk.Frame(self, bg="#27ae60", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Check Your Email",
            font=("Helvetica", 18, "bold"), fg="white", bg="#27ae60",
        ).pack(expand=True)

        card = tk.Frame(self, bg=_CARD_BG, bd=1, relief="solid", padx=40, pady=30)
        card.pack(padx=50, pady=30, fill="x")

        email = reset_info.get("email") or ""
        masked = email
        if "@" in email:
            local, _, domain = email.partition("@")
            if len(local) > 2:
                masked = local[0] + "*" * (len(local) - 2) + local[-1] + "@" + domain

        tk.Label(
            card,
            text="Because MFA is enabled on this account, your temporary "
                 "password has been sent to your registered email address:",
            font=("Helvetica", 11), bg=_CARD_BG, wraplength=380, justify="left",
        ).pack(pady=(0, 10))

        tk.Label(
            card, text=masked, font=("Helvetica", 12, "bold"),
            bg=_CARD_BG, fg="#2c3e50",
        ).pack(pady=(0, 15))

        tk.Label(
            card,
            text="Use that password to log in. You'll be asked to set a "
                 "new password on first login.",
            font=("Helvetica", 10), bg=_CARD_BG, fg="#555",
            wraplength=380, justify="left",
        ).pack(pady=(0, 20))

        ttk.Button(
            card, text="Back to Login", command=self._build_login_ui,
        ).pack(fill="x", ipady=6)

    def _show_temp_password(self, reset_info: dict):
        """Step 3: Show the temporary password to the user (masked by default)."""
        for w in self.winfo_children():
            w.destroy()

        self.geometry("500x500")

        header = tk.Frame(self, bg="#27ae60", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Password Reset Successful",
            font=("Helvetica", 18, "bold"), fg="white", bg="#27ae60",
        ).pack(expand=True)

        card = tk.Frame(self, bg=_CARD_BG, bd=1, relief="solid", padx=40, pady=30)
        card.pack(padx=50, pady=30)

        tk.Label(
            card, text="Your password has been reset.",
            font=("Helvetica", 12), bg=_CARD_BG,
        ).pack(pady=(0, 10))

        tk.Label(
            card, text="Your temporary password is:",
            font=("Helvetica", 10), bg=_CARD_BG, fg="#555",
        ).pack()

        # Temp password display — masked by default
        temp_pw = reset_info["temp_password"]
        masked = "\u2022" * len(temp_pw)

        pw_frame = tk.Frame(card, bg="#ecf0f1", bd=1, relief="solid", padx=15, pady=10)
        pw_frame.pack(fill="x", pady=(8, 8))
        pw_var = tk.StringVar(value=masked)
        pw_label = tk.Label(
            pw_frame, textvariable=pw_var,
            font=("Courier", 14, "bold"), bg="#ecf0f1", fg="#2c3e50",
        )
        pw_label.pack()

        # Reveal / Copy buttons
        btn_row = tk.Frame(card, bg=_CARD_BG)
        btn_row.pack(fill="x", pady=(0, 12))

        _revealed = {"state": False, "timer": None}

        def _toggle_reveal():
            if _revealed["state"]:
                pw_var.set(masked)
                reveal_btn.configure(text="Show Password")
                _revealed["state"] = False
                if _revealed["timer"]:
                    self.after_cancel(_revealed["timer"])
                    _revealed["timer"] = None
            else:
                pw_var.set(temp_pw)
                reveal_btn.configure(text="Hide Password")
                _revealed["state"] = True

                def _auto_hide():
                    try:
                        if reveal_btn.winfo_exists():
                            pw_var.set(masked)
                            reveal_btn.configure(text="Show Password")
                            _revealed.update(state=False, timer=None)
                    except tk.TclError:
                        pass

                # Auto-hide after 30 seconds
                _revealed["timer"] = self.after(30_000, _auto_hide)

        def _copy_to_clipboard():
            self.clipboard_clear()
            self.clipboard_append(temp_pw)
            copy_btn.configure(text="Copied!")

            def _restore_copy_label():
                try:
                    if copy_btn.winfo_exists():
                        copy_btn.configure(text="Copy")
                except tk.TclError:
                    pass

            self.after(2000, _restore_copy_label)
            # Auto-clear clipboard after 60 seconds for security
            def _clear_clipboard():
                try:
                    self.clipboard_clear()
                    self.clipboard_append("")
                except tk.TclError:
                    pass
            self.after(60_000, _clear_clipboard)

        reveal_btn = ttk.Button(btn_row, text="Show Password", command=_toggle_reveal)
        reveal_btn.pack(side="left", padx=(0, 8))

        copy_btn = ttk.Button(btn_row, text="Copy", command=_copy_to_clipboard)
        copy_btn.pack(side="left")

        tk.Label(
            card,
            text="You will be asked to change your password\n"
                 "when you log in. The password auto-hides after 30s.",
            font=("Helvetica", 10), bg=_CARD_BG, fg="#e67e22",
            justify="center",
        ).pack(pady=(0, 5))

        if reset_info.get("email"):
            tk.Label(
                card,
                text=f"A confirmation email has been sent to\n{reset_info['email']}",
                font=("Helvetica", 9), bg=_CARD_BG, fg="#7f8c8d",
                justify="center",
            ).pack(pady=(5, 0))

        ttk.Button(
            card, text="Back to Login", command=self._build_login_ui,
        ).pack(fill="x", ipady=6, pady=(15, 0))

    # ------------------------------------------------------------------
    #  System selection screen
    # ------------------------------------------------------------------

    def _is_superadmin(self, user_info: dict) -> bool:
        """Check if the user has admin access to all 4 systems."""
        systems = user_info.get("systems", [])
        admin_keys = {s["system_key"] for s in systems if s.get("role") == "admin"}
        return admin_keys >= {"university", "college", "school", "primary"}

    def _on_login_success(self, user_info: dict):
        """After login, show password change if expired, then system picker."""
        # Force password change if expired (includes temp passwords)
        if user_info.get("password_expired"):
            self._show_change_password(user_info)
            return

        self._proceed_after_login(user_info)

    def _show_change_password(self, user_info: dict):
        """Show a mandatory password change screen."""
        for w in self.winfo_children():
            w.destroy()

        self.geometry("500x500")

        header = tk.Frame(self, bg="#e67e22", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Password Change Required",
            font=("Helvetica", 18, "bold"), fg="white", bg="#e67e22",
        ).pack(expand=True)

        tk.Label(
            self, text="Your password has expired or was reset.\nPlease set a new password.",
            font=("Helvetica", 11), fg="#7f8c8d", bg=_BG, justify="center",
        ).pack(pady=(15, 10))

        card = tk.Frame(self, bg=_CARD_BG, bd=1, relief="solid", padx=40, pady=25)
        card.pack(padx=50)

        tk.Label(
            card, text="Current Password", font=("Helvetica", 10, "bold"),
            bg=_CARD_BG, anchor="w",
        ).pack(fill="x", pady=(0, 4))
        # Prefill with the password the user just logged in with (e.g. the
        # temp password from a forgot-password reset) so they don't have to
        # retype it. Consume the cached value so it's only used once.
        prefilled_old = getattr(self, "_last_login_password", "") or ""
        self._last_login_password = ""
        self._cp_old_var = tk.StringVar(value=prefilled_old)
        old_entry = ttk.Entry(card, textvariable=self._cp_old_var, width=30,
                              show="*", font=("Helvetica", 11))
        old_entry.pack(fill="x", ipady=4, pady=(0, 10))
        # Focus the new-password field if old is already filled in
        if prefilled_old:
            pass  # focus moves below after new_entry exists
        else:
            old_entry.focus_set()

        tk.Label(
            card, text="New Password", font=("Helvetica", 10, "bold"),
            bg=_CARD_BG, anchor="w",
        ).pack(fill="x", pady=(0, 4))
        self._cp_new_var = tk.StringVar()
        new_entry = ttk.Entry(card, textvariable=self._cp_new_var, width=30,
                              show="*", font=("Helvetica", 11))
        new_entry.pack(fill="x", ipady=4, pady=(0, 10))
        if prefilled_old:
            new_entry.focus_set()

        tk.Label(
            card, text="Confirm New Password", font=("Helvetica", 10, "bold"),
            bg=_CARD_BG, anchor="w",
        ).pack(fill="x", pady=(0, 4))
        self._cp_confirm_var = tk.StringVar()
        confirm_entry = ttk.Entry(card, textvariable=self._cp_confirm_var, width=30,
                                  show="*", font=("Helvetica", 11))
        confirm_entry.pack(fill="x", ipady=4, pady=(0, 4))

        # Show password toggle
        self._cp_show_pw_var = tk.BooleanVar()
        def _toggle_cp_pw():
            char = "" if self._cp_show_pw_var.get() else "*"
            old_entry.configure(show=char)
            new_entry.configure(show=char)
            confirm_entry.configure(show=char)
        tk.Checkbutton(
            card, text="Show passwords", variable=self._cp_show_pw_var,
            command=_toggle_cp_pw, bg=_CARD_BG, font=("Helvetica", 9),
            activebackground=_CARD_BG,
        ).pack(anchor="w", pady=(0, 10))

        ttk.Button(
            card, text="Change Password",
            command=lambda: self._do_change_password(user_info),
        ).pack(fill="x", ipady=6)

        self._cp_error_var = tk.StringVar()
        tk.Label(
            card, textvariable=self._cp_error_var,
            font=("Helvetica", 9), fg="red", bg=_CARD_BG, wraplength=280,
        ).pack(fill="x", pady=(10, 0))

        tk.Label(
            card,
            text="Min 12 chars, uppercase, lowercase, digit, special char",
            font=("Helvetica", 8), fg="#95a5a6", bg=_CARD_BG,
        ).pack(fill="x", pady=(5, 0))

    def _do_change_password(self, user_info: dict):
        """Process the password change form."""
        old_pw = self._cp_old_var.get()
        new_pw = self._cp_new_var.get()
        confirm_pw = self._cp_confirm_var.get()

        if not old_pw or not new_pw or not confirm_pw:
            self._cp_error_var.set("Please fill in all fields.")
            return

        if new_pw != confirm_pw:
            self._cp_error_var.set("New passwords do not match.")
            return

        try:
            self._auth.change_password(user_info["id"], old_pw, new_pw)
        except AuthError as exc:
            self._cp_error_var.set(str(exc))
            return
        except Exception as exc:
            logger.error("Auth change error: %s", exc, exc_info=True)
            self._cp_error_var.set("An unexpected error occurred.")
            return

        # Password changed — re-login with new credentials to get a fresh session
        try:
            new_user_info = self._auth.login(user_info["username"], new_pw)
        except AuthError:
            # MFA may kick in; just go back to login
            messagebox.showinfo(
                "Password Changed",
                "Your password has been changed successfully.\nPlease log in again.",
                parent=self,
            )
            self._build_login_ui()
            return

        if new_user_info.get("mfa_required"):
            messagebox.showinfo(
                "Password Changed",
                "Your password has been changed successfully.\nPlease log in again.",
                parent=self,
            )
            self._build_login_ui()
            return

        # Send a confirmation email and flag the session so the system GUI
        # opens the email manager once it loads.
        self._send_change_confirmation_email(new_user_info)
        new_user_info["_open_email_after_login"] = True

        messagebox.showinfo(
            "Password Changed",
            "Your password has been changed successfully.\n"
            "A confirmation email has been sent to your inbox.",
            parent=self,
        )
        self._proceed_after_login(new_user_info)

    def _send_change_confirmation_email(self, user_info: dict):
        """Send a 'password changed' confirmation to the user's email."""
        email = user_info.get("email")
        if not email:
            return
        try:
            from education_system.shared.email.email_service import EmailService
            svc = EmailService()
            if not svc.is_configured:
                return
            display = user_info.get("display_name") or user_info.get("username", "")
            subject = "Your password was changed"
            body = (
                f"Hello {display},\n\n"
                "This is confirmation that your Education System password "
                "was just changed.\n\n"
                "If you did not make this change, contact an administrator "
                "immediately.\n\n"
                "— Education System"
            )
            svc.send_email(email, subject, body)
        except Exception as exc:
            logger.debug("Confirmation email failed: %s", exc)

    def _proceed_after_login(self, user_info: dict):
        """Continue login flow after password is confirmed OK."""
        systems = user_info.get("systems", [])

        if not systems:
            messagebox.showerror(
                "No Access",
                "Your account does not have access to any systems.\n"
                "Please contact an administrator.",
                parent=self,
            )
            self._build_login_ui()
            return

        # Superadmin gets the full dashboard
        if self._is_superadmin(user_info):
            self.user_info = user_info
            self.system_key = "__superadmin__"
            self.system_role = "admin"
            self.auth = self._auth
            self.destroy()
            return

        # If user only has one system, go straight there
        if len(systems) == 1:
            self.user_info = user_info
            self.system_key = systems[0]["system_key"]
            self.system_role = systems[0]["role"]
            self.auth = self._auth
            self.destroy()
            return

        # Show system picker
        self._show_system_picker(user_info, systems)

    def _show_system_picker(self, user_info: dict, systems: list[dict]):
        """Display buttons for each system the user can access."""
        for w in self.winfo_children():
            w.destroy()

        height = 200 + (len(systems) * 70)
        self.geometry(f"500x{height}")

        # Header
        header = tk.Frame(self, bg=_HEADER_BG, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Education System",
            font=("Helvetica", 22, "bold"), fg="white", bg=_HEADER_BG,
        ).pack(expand=True)

        # Welcome
        display = user_info.get("display_name", user_info.get("username", "User"))
        tk.Label(
            self, text=f"Welcome, {display}",
            font=("Helvetica", 14), bg=_BG,
        ).pack(pady=(20, 5))
        tk.Label(
            self, text="Choose a system to launch:",
            font=("Helvetica", 11), fg="#7f8c8d", bg=_BG,
        ).pack(pady=(0, 15))

        # System buttons
        btn_frame = tk.Frame(self, bg=_BG)
        btn_frame.pack(expand=True)

        for sys_info in systems:
            key = sys_info["system_key"]
            role = sys_info["role"]
            label = SYSTEMS.get(key, key.title())
            colours = _SYSTEM_COLOURS.get(key, ("#2980b9", "#3498db"))

            btn = tk.Button(
                btn_frame,
                text=f"{label}\n({role})",
                font=("Helvetica", 13), width=30, height=2,
                bg=colours[0], fg="white",
                activebackground=colours[1], activeforeground="white",
                cursor="hand2", relief=tk.FLAT,
                command=lambda k=key, r=role: self._pick_system(user_info, k, r),
            )
            btn.pack(pady=6)

        # Logout / back button
        ttk.Button(
            btn_frame, text="Logout",
            command=self._do_logout_and_restart,
        ).pack(pady=(15, 0))

    def _pick_system(self, user_info: dict, system_key: str, role: str):
        """User selected a system."""
        self.user_info = user_info
        self.system_key = system_key
        self.system_role = role
        self.auth = self._auth
        self.destroy()

    def _do_logout_and_restart(self):
        """Log out and return to login screen."""
        try:
            self._auth.logout()
        except Exception:
            pass
        self._auth = UserAuth(self._auth_db_path)
        self._build_login_ui()

    # ------------------------------------------------------------------
    #  Window close
    # ------------------------------------------------------------------

    def _on_close(self):
        """Handle window close - treat as cancel."""
        try:
            self._auth.logout()
        except Exception:
            pass
        self.user_info = None
        self.system_key = None
        self.destroy()
