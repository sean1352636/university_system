"""Parameter forms for communication operations.

Split out of ``bulk_operations_views.py``, which re-exports every name here.
"""

from __future__ import annotations

from tkinter import ttk
import tkinter as tk


class CommsFormsMixin:
    """Parameter forms for communication operations."""

    def _build_message_form(self) -> None:
        f = self.params_frame
        self.p_subject = self._entry(f, 0, "Subject:")
        ttk.Label(f, text="Body:").grid(row=1, column=0,
                                           sticky="ne", pady=3)
        self.p_body = tk.Text(f, width=44, height=8)
        self.p_body.grid(row=1, column=1, sticky="w", padx=6)
        self.p_channel = self._combo(
            f, 2, "Channel:",
            ["Email", "SMS", "Letter", "Phone Call",
             "In Person", "System"], default="Email")
        self.p_msg_cat = self._entry(f, 3, "Category:", "General")
        self.p_pri = self._combo(f, 4, "Priority:",
                                    ["Low", "Normal", "High", "Urgent"],
                                    default="Normal")
        self.p_status = self._combo(f, 5, "Status:",
                                       ["Draft", "Queued", "Sent"],
                                       default="Sent")

    def _build_sms_form(self) -> None:
        f = self.params_frame
        self.p_subject = self._entry(f, 0, "Subject (audit):", "SMS")
        ttk.Label(f, text="Body:").grid(row=1, column=0,
                                            sticky="ne", pady=3)
        self.p_body = tk.Text(f, width=44, height=6)
        self.p_body.grid(row=1, column=1, sticky="w", padx=6)
        self.p_sender = self._entry(f, 2, "Sender staff id:")

    def _build_letters_form(self) -> None:
        from education_system.systems.sixth_form.domains.communications.domain.letter_templates import (
            letter_templates as _lt,
        )
        templates = _lt.list_templates()
        self._template_map: dict[str, int] = {
            f"#{t.template_id}  {t.name}": t.template_id for t in templates
        }
        f = self.params_frame
        self.p_template = self._combo(
            f, 0, "Template:",
            list(self._template_map.keys()) or ["(none)"],
            default=(next(iter(self._template_map), "(none)")), width=40)
        self.p_ctx = self._entry(
            f, 1, "Extra context (k=v,...):", width=40)

    def _build_meeting_form(self) -> None:
        from education_system.systems.sixth_form.domains.communications.domain.parents_evenings import (
            parents_evenings as _pe,
        )
        events = _pe.list_events()
        self._event_map: dict[str, int] = {
            f"#{e.event_id}  {e.event_date}  {e.title}": e.event_id
            for e in events
        }
        f = self.params_frame
        self.p_event = self._combo(
            f, 0, "Event:",
            list(self._event_map.keys()) or ["(none)"],
            default=(next(iter(self._event_map), "(none)")), width=46)
        self.p_link = self._entry(f, 1, "Booking link:", width=40)

    def _build_pwreset_form(self) -> None:
        f = self.params_frame
        self.p_mfa = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            f, text="MFA enrolment (instead of password reset)",
            variable=self.p_mfa).grid(
            row=0, column=1, sticky="w", padx=6, pady=3)
        self.p_url = self._entry(f, 1, "Reset URL:", width=40)

    def _build_schedule_msg_form(self) -> None:
        f = self.params_frame
        self.p_subject = self._entry(f, 0, "Subject:")
        ttk.Label(f, text="Body:").grid(row=1, column=0,
                                            sticky="ne", pady=3)
        self.p_body = tk.Text(f, width=44, height=6)
        self.p_body.grid(row=1, column=1, sticky="w", padx=6)
        self.p_send_at = self._entry(f, 2, "Send at:",
                                       width=20)
        ttk.Label(f, text="  (YYYY-MM-DD HH:MM)",
                   foreground="#555").grid(row=2, column=2, sticky="w")
        self.p_channel = self._combo(f, 3, "Channel:",
                                         ["Email", "SMS", "Letter",
                                          "Portal"], default="Email")
        self.p_msg_cat = self._entry(f, 4, "Category:", "General")
        self.p_pri = self._combo(f, 5, "Priority:",
                                     ["Low", "Normal", "High", "Urgent"],
                                     default="Normal")
