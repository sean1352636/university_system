"""Shared GUI frame for managing security questions.

Provides ``SecurityQuestionsFrame`` — a tk.Frame that can be embedded
in any education subsystem's main window or settings area.  Follows the
same pattern as ``MFASettingsFrame``.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.shared.auth.forgot_password import ForgotPasswordService
from education_system.shared.auth.schema import SECURITY_QUESTIONS

logger = logging.getLogger(__name__)

_BG = "#ecf0f1"
_HEADER_BG = "#2c3e50"
_CARD_BG = "white"


class SecurityQuestionsFrame(tk.Frame):
    """Security questions management frame.

    Parameters
    ----------
    parent : tk widget
    db_path : str or None
        Path to the shared auth database.
    auth : UserAuth or dict
        Either a ``UserAuth`` instance (with ``current_user``) or a
        user-info dict containing ``user_id`` and ``username`` keys.
    """

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ForgotPasswordService(db_path)
        self._user_id = self._resolve_user_id()
        self._username = self._resolve_username()
        self._build_ui()
        self._refresh_status()

    def _resolve_user_id(self) -> int | None:
        # `security_questions` is keyed on auth.db `users.id`.  In multi-system
        # launchers (e.g. the university launcher) `current_user["user_id"]`
        # is rewritten to a *system-local* legacy id and the real auth-db id
        # is stashed under `shared_auth_id` — prefer that key when present.
        def _from(d):
            return d.get("shared_auth_id") or d.get("user_id") or d.get("id")
        if isinstance(self._auth, dict):
            return _from(self._auth)
        cu = getattr(self._auth, "current_user", None)
        if isinstance(cu, dict):
            return _from(cu)
        return None

    def _resolve_username(self) -> str | None:
        if isinstance(self._auth, dict):
            return self._auth.get("username")
        cu = getattr(self._auth, "current_user", None)
        if isinstance(cu, dict):
            return cu.get("username")
        return None

    # ------------------------------------------------------------------
    #  UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg=_BG)

        # Header — include username so the user can never be unsure
        # which account these questions are being saved against.
        header = tk.Frame(self, bg=_HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        title = "Security Questions"
        if self._username:
            title = f"Security Questions — {self._username} (id={self._user_id})"
        tk.Label(
            header, text=title,
            font=("Helvetica", 15, "bold"), bg=_HEADER_BG, fg="white",
        ).pack(side="left", padx=20, pady=10)

        # Info
        info_frame = tk.Frame(self, bg=_BG, padx=20, pady=10)
        info_frame.pack(fill="x")
        tk.Label(
            info_frame,
            text="Security questions are used to verify your identity when\n"
                 "you reset your password via the Forgot Password feature.",
            font=("Helvetica", 10), bg=_BG, fg="#34495e", justify="left",
        ).pack(anchor="w")

        # Status section
        status_frame = tk.LabelFrame(self, text="Current Status", bg=_BG, padx=15, pady=10)
        status_frame.pack(fill="x", padx=20, pady=10)

        self._status_var = tk.StringVar(value="Checking...")
        tk.Label(
            status_frame, textvariable=self._status_var,
            font=("Helvetica", 12, "bold"), bg=_BG,
        ).pack(anchor="w")

        # Current questions display
        self._questions_frame = tk.Frame(status_frame, bg=_BG)
        self._questions_frame.pack(fill="x", pady=(5, 0))

        # Action buttons
        btn_frame = tk.Frame(self, bg=_BG, padx=20)
        btn_frame.pack(fill="x", pady=10)

        self._setup_btn = ttk.Button(
            btn_frame, text="Set Up Security Questions",
            command=self._show_setup_dialog,
        )
        self._setup_btn.pack(side="left", padx=(0, 10))

        self._update_btn = ttk.Button(
            btn_frame, text="Update Questions",
            command=self._show_setup_dialog,
        )
        self._update_btn.pack(side="left")

        # Setup form area (hidden until needed)
        self._form_frame = tk.LabelFrame(
            self, text="Set Security Questions", bg=_BG, padx=15, pady=15,
        )

    # ------------------------------------------------------------------
    #  Status refresh
    # ------------------------------------------------------------------

    def _refresh_status(self):
        """Refresh the current security question status display."""
        # Clear existing question labels
        for w in self._questions_frame.winfo_children():
            w.destroy()

        if not self._username:
            self._status_var.set("Unable to determine user")
            self._setup_btn.pack_forget()
            self._update_btn.pack_forget()
            return

        try:
            has_qs = self._svc.has_security_questions(self._username)
        except Exception:
            has_qs = False

        if has_qs:
            self._status_var.set("Configured")
            try:
                questions = self._svc.get_questions_for_user(self._username)
                for i, q in enumerate(questions, 1):
                    tk.Label(
                        self._questions_frame,
                        text=f"  {i}. {q['question']}",
                        font=("Helvetica", 10), bg=_BG, fg="#555", anchor="w",
                    ).pack(fill="x")
            except Exception:
                pass
            self._setup_btn.pack_forget()
            self._update_btn.pack(side="left")
        else:
            self._status_var.set("Not configured")
            self._update_btn.pack_forget()
            self._setup_btn.pack(side="left")

        # Force visual refresh
        self.update_idletasks()

    # ------------------------------------------------------------------
    #  Setup dialog
    # ------------------------------------------------------------------

    def _show_setup_dialog(self):
        """Open a dialog to set or update security questions."""
        dialog = _SecurityQuestionsDialog(self, self._svc, self._user_id)
        self.wait_window(dialog)
        # Always refresh after dialog closes — saved or not
        try:
            self._refresh_status()
            if dialog.saved:
                self._status_var.set("Configured  (saved successfully)")
        except Exception:
            pass


class _SecurityQuestionsDialog(tk.Toplevel):
    """Modal dialog for setting security questions."""

    def __init__(self, parent, svc: ForgotPasswordService, user_id: int):
        super().__init__(parent)
        self._svc = svc
        self._user_id = user_id
        self.saved = False

        self.title("Set Security Questions")
        # Track username for header / save-time logging
        self._username = getattr(parent, "_username", None)
        self.geometry("550x700")
        self.minsize(500, 600)
        self.transient(parent)
        self.grab_set()

        self._build_ui()

        # Centre on parent
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - 550) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - 700) // 2
        self.geometry(f"+{max(px, 0)}+{max(py, 0)}")

    def _build_ui(self):
        main = tk.Frame(self, bg=_BG, padx=20, pady=15)
        main.pack(fill="both", expand=True)

        heading = "Choose 3 questions and provide answers"
        if self._username:
            heading = f"Choose 3 questions for: {self._username}"
        tk.Label(
            main, text=heading,
            font=("Helvetica", 12, "bold"), bg=_BG,
        ).pack(pady=(0, 5))
        tk.Label(
            main, text="Answers are case-insensitive",
            font=("Helvetica", 9), bg=_BG, fg="#7f8c8d",
        ).pack(pady=(0, 15))

        self._combos = []
        self._answer_vars = []

        for i in range(3):
            frame = tk.Frame(main, bg=_CARD_BG, bd=1, relief="solid", padx=12, pady=10)
            frame.pack(fill="x", pady=5)

            tk.Label(
                frame, text=f"Question {i + 1}",
                font=("Helvetica", 10, "bold"), bg=_CARD_BG,
            ).pack(anchor="w")

            combo = ttk.Combobox(
                frame, values=SECURITY_QUESTIONS, state="readonly",
                font=("Helvetica", 10), width=45,
            )
            combo.pack(fill="x", pady=(4, 8))
            # Pre-select a different default for each
            if i < len(SECURITY_QUESTIONS):
                combo.current(i)
            self._combos.append(combo)

            tk.Label(
                frame, text="Your Answer:",
                font=("Helvetica", 9), bg=_CARD_BG, fg="#555",
            ).pack(anchor="w")
            var = tk.StringVar()
            ttk.Entry(frame, textvariable=var, font=("Helvetica", 10)).pack(fill="x", ipady=3)
            self._answer_vars.append(var)

        # Error label
        self._error_var = tk.StringVar()
        tk.Label(
            main, textvariable=self._error_var,
            font=("Helvetica", 9), fg="red", bg=_BG, wraplength=440,
        ).pack(fill="x", pady=(8, 0))

        # Buttons
        btn_frame = tk.Frame(main, bg=_BG)
        btn_frame.pack(fill="x", pady=(15, 5))
        ttk.Button(btn_frame, text="Save Questions", command=self._save).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="right")

    def _save(self):
        """Validate and save the security questions."""
        questions: list[tuple[str, str]] = []
        chosen_qs: set[str] = set()

        for i in range(3):
            q = self._combos[i].get()
            a = self._answer_vars[i].get().strip()

            if not q:
                self._error_var.set(f"Please select question {i + 1}.")
                return
            if not a:
                self._error_var.set(f"Please provide an answer for question {i + 1}.")
                return
            if q in chosen_qs:
                self._error_var.set("Each question must be different.")
                return

            chosen_qs.add(q)
            questions.append((q, a))

        if not self._user_id:
            self._error_var.set(
                "Cannot save: no user is logged in. "
                "Please re-login and try again.",
            )
            logger.error("SQ save aborted: _user_id is None (username=%s)",
                         self._username)
            return

        try:
            self._svc.set_security_questions(self._user_id, questions)
            self.saved = True
            messagebox.showinfo(
                "Success", "Security questions updated successfully.",
                parent=self,
            )
            self.destroy()
        except Exception as e:
            logger.exception("SQ save failed for user_id=%s", self._user_id)
            self._error_var.set(str(e))
