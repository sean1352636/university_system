"""General feedback tab — migrated from the retired HelpCenterGUI."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import logging
import tkinter as tk
from tkinter import ttk, scrolledtext

from ._dialogs import make_toplevel, messagebox

from education_system.systems.university.infrastructure.database.db import transaction
from education_system.systems.university.infrastructure.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)


class FeedbackMixin:
    """Provides a 'rate your experience' feedback form backed by user_feedback."""

    def _ensure_user_feedback_table(self):
        try:
            with transaction() as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS user_feedback ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "student_id TEXT, "
                    "rating INTEGER, "
                    "comment TEXT, "
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                )
        except Exception as exc:
            logger.warning("Could not ensure user_feedback table: %s", exc)

    def show_general_feedback(self):
        """Show the general feedback submission form."""
        self.clear_content()
        self._ensure_user_feedback_table()

        frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(frame, text=_t('gui.pastoral.student_support.feedback.tabs.feedback', default="💬 Feedback"))

        container = ttk.Frame(frame)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(
            container,
            text=_t('gui.pastoral.student_support.feedback.labels.how_would_you_rate_your_experience', default="How would you rate your experience?"),
            font=("Segoe UI", 14),
        ).pack(anchor="w", pady=(0, 10))

        self.general_feedback_rating = tk.IntVar(value=0)
        rating_frame = ttk.Frame(container)
        rating_frame.pack(anchor="w", pady=(0, 15))

        for i in range(1, 6):
            ttk.Radiobutton(
                rating_frame,
                text=f"{i} Star{'s' if i > 1 else ''}",
                variable=self.general_feedback_rating,
                value=i,
            ).pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(container, text=_t('gui.pastoral.student_support.feedback.labels.comments', default="Comments:")).pack(anchor="w", pady=(0, 5))
        self.general_feedback_text = scrolledtext.ScrolledText(container, height=10, width=70)
        self.general_feedback_text.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        ttk.Button(
            container,
            text=_t('gui.pastoral.student_support.feedback.buttons.submit_feedback', default="Submit Feedback"),
            command=self._submit_general_feedback,
        ).pack(anchor="e")

    def _submit_general_feedback(self):
        rating = self.general_feedback_rating.get()
        comment = self.general_feedback_text.get("1.0", tk.END).strip()

        if rating == 0:
            messagebox.showwarning(_t('gui.pastoral.student_support.feedback.dialogs.validation', default="Validation"), _t('gui.pastoral.student_support.feedback.dialogs.please_select_a_rating', default="Please select a rating."))
            return

        student_id = ""
        uid = ""
        if self.auth and getattr(self.auth, "current_user", None):
            user = self.auth.current_user
            student_id = user.get("username", "") if isinstance(user, dict) else getattr(user, "username", "")
            uid = user.get("id", "") if isinstance(user, dict) else getattr(user, "id", "")

        try:
            with transaction() as conn:
                conn.execute(
                    "INSERT INTO user_feedback (student_id, rating, comment, created_at) "
                    "VALUES (?, ?, ?, datetime('now'))",
                    (student_id, rating, comment),
                )
            log_activity(
                uid,
                student_id,
                "student",
                "submit_feedback",
                "student_support",
                details=f"Submitted feedback with rating {rating}",
            )
            messagebox.showinfo(_t('gui.pastoral.student_support.feedback.dialogs.thank_you', default="Thank You"), _t('gui.pastoral.student_support.feedback.dialogs.your_feedback_has_been_submitted', default="Your feedback has been submitted."))
            self.general_feedback_rating.set(0)
            self.general_feedback_text.delete("1.0", tk.END)
        except Exception as exc:
            logger.error("Failed to submit feedback: %s", exc)
            messagebox.showerror(_t('gui.pastoral.student_support.feedback.dialogs.error', default="Error"), f"Could not submit feedback: {exc}")
