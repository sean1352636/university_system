"""A learner's own details.

Editable in part: a learner may correct their own contact details and
emergency contact, because those go stale and nobody else notices. Everything
that affects funding or assessment — name, date of birth, ULN, status, course
— is shown read-only and changed by college administration, so a learner
cannot edit themselves onto a different funding band.
"""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "My details"

# The only fields a learner may change themselves.
EDITABLE = ("email", "phone", "address", "postcode",
            "emergency_contact_name", "emergency_contact_phone")


def open_window(host) -> None:
    Screen(host)


class Screen:
    def __init__(self, host):
        self.host = host
        self.ctl = host.ctl
        host.clear_content()
        parent = host.content_frame

        w.page_header(
            parent, TITLE,
            "Keep your contact details up to date. Anything else is changed by "
            "college administration.",
            actions=[
                ("Update my contact details", self.edit),
                ("↻ Refresh", self.refresh),
            ],
        )

        if not self.ctl.student_id:
            w.empty_state(parent, "Your account is not linked to a learner record.")
            return

        self.holder = ttk.Frame(parent)
        self.holder.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self) -> None:
        w.clear(self.holder)
        try:
            profile = self.ctl.students.profile(self.ctl.student_id)
        except Exception as exc:
            logger.exception("Could not load the FE College learner profile")
            w.error(self.host, TITLE, f"Could not load your details: {exc}")
            return
        if profile is None:
            w.empty_state(self.holder, "Your learner record could not be found.")
            return

        self.student = profile.student
        s = self.student

        columns = ttk.Frame(self.holder)
        columns.pack(fill="both", expand=True)
        columns.columnconfigure(0, weight=1, uniform="p")
        columns.columnconfigure(1, weight=1, uniform="p")

        left = ttk.Frame(columns)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        tutor = self.ctl.staff.get(s.personal_tutor) if s.personal_tutor else None
        w.kv_panel(left, "About me", [
            ("Name", s.full_name),
            ("Student ID", s.student_id),
            ("Date of birth", w.when(s.date_of_birth)),
            ("Age", str(s.age) if s.age is not None else "—"),
            ("ULN", s.uln or "—"),
            ("Learner type", s.learner_type),
            ("Mode of study", s.mode_of_study),
            ("Status", s.status),
            ("Started", w.when(s.start_date)),
        ]).pack(fill="x", pady=(0, 10))

        w.kv_panel(left, "My college contacts", [
            ("Tutor group", s.tutor_group or "—"),
            ("Personal tutor", tutor.full_name if tutor else "not assigned"),
            ("Tutor email", tutor.email if tutor else "—"),
        ]).pack(fill="x")

        right = ttk.Frame(columns)
        right.grid(row=0, column=1, sticky="nsew")

        w.kv_panel(right, "Contact details (you can change these)", [
            ("Email", s.email or "— not set"),
            ("Phone", s.phone or "— not set"),
            ("Address", s.address or "— not set"),
            ("Postcode", s.postcode or "— not set"),
        ]).pack(fill="x", pady=(0, 10))

        w.kv_panel(right, "Emergency contact", [
            ("Name", s.emergency_contact_name or "— not set",
             "warn" if not s.emergency_contact_name else "plain"),
            ("Phone", s.emergency_contact_phone or "— not set",
             "warn" if not s.emergency_contact_phone else "plain"),
        ]).pack(fill="x", pady=(0, 10))

        if profile.support:
            panel = ttk.LabelFrame(right, text="My learning support", padding=8)
            panel.pack(fill="x", pady=(0, 10))
            table = w.DataTable(panel, [
                ("type", "Support", 190),
                ("status", "Status", 105),
                ("hours", "Hours/week", 90, "e"),
                ("review", "Next review", 105),
            ], height=min(5, len(profile.support)))
            table.set_rows([
                {
                    "type": p.support_type,
                    "status": p.status.replace("_", " "),
                    "hours": f"{p.hours_per_week:g}" if p.hours_per_week else "—",
                    "review": w.when(p.review_date),
                    "_tone": "good" if p.is_active else "muted",
                }
                for p in profile.support
            ])

        w.kv_panel(right, "Finance", [
            ("Balance", w.money(profile.balance),
             "warn" if profile.balance > 0 else "good"),
        ]).pack(fill="x")

        if not s.emergency_contact_name or not s.emergency_contact_phone:
            ttk.Label(
                self.holder,
                text=("We do not have an emergency contact for you. Please add "
                      "one — the college needs it if you are taken ill on site."),
                foreground=w.TONE["warn"], wraplength=1000, justify="left",
            ).pack(anchor="w", pady=(10, 0))

        self.host.set_status(f"{s.display_name} · {s.status}")

    def edit(self) -> None:
        s = self.student
        result = w.ask(self.host, "Update my contact details", [
            ("email", "Email", "text"),
            ("phone", "Phone", "text"),
            ("address", "Address", "multiline"),
            ("postcode", "Postcode", "text"),
            ("emergency_contact_name", "Emergency contact name", "text"),
            ("emergency_contact_phone", "Emergency contact phone", "text"),
        ], initial={key: getattr(s, key) for key in EDITABLE},
            submit_label="Save")
        if result is None:
            return

        # Copy only the whitelisted fields onto the record, so nothing else can
        # be changed from this screen even if the form grows.
        for key in EDITABLE:
            setattr(s, key, result[key])
        try:
            self.ctl.students.update(s)
        except ValidationError as exc:
            w.error(self.host, "Update details", str(exc))
            return
        self.refresh()
        self.host.set_status("Your contact details have been updated")


__all__ = ["EDITABLE", "TITLE", "Screen", "open_window"]
