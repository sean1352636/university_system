"""Learner support — asking for help, and seeing what happened to the ask.

Two things a learner can do here: raise a request (which becomes a referral to
the right team) and record how they are doing. Both are visible to staff, and
the screen says so — a wellbeing tool that quietly shares what you write is
worse than none.

Safeguarding is deliberately not one of the options a learner picks from a
dropdown: a disclosure needs a person, not a form, and the screen says who to
go to instead.
"""

from __future__ import annotations

import logging
from datetime import date
from tkinter import ttk

from education_system.systems.fe_college.domain.pastoral.referrals import Referral
from education_system.systems.fe_college.domain.pastoral.wellbeing import (
    MOOD_LABELS,
    MOOD_SCALE,
    WellbeingCheckIn,
    trend,
)
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    pastoral_repository as pastoral_repo,
)
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "Support"

# What a learner may request for themselves. Safeguarding is handled by a
# person, not a self-service form — see the module docstring.
REQUESTABLE = (
    "Wellbeing / Mental Health",
    "Learning Support",
    "Financial Support",
    "Careers",
    "Attendance",
)


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
            "Ask for help, and see what has happened to anything you have "
            "already asked about.",
            actions=[
                ("Ask for support", self.request),
                ("How am I doing?", self.check_in),
                ("↻ Refresh", self.refresh),
            ],
        )

        if not self.ctl.student_id:
            w.empty_state(parent, "Your account is not linked to a learner record.")
            return

        self._safeguarding_notice(parent)

        self.holder = ttk.Frame(parent)
        self.holder.pack(fill="both", expand=True)
        self.refresh()

    def _safeguarding_notice(self, parent) -> None:
        panel = ttk.LabelFrame(parent, text="If you are worried about your safety",
                               padding=10)
        panel.pack(fill="x", pady=(0, 10))
        leads = [
            s for s in self.ctl.staff.search(active_only=True)
            if s.is_safeguarding_lead
        ]
        contact = (
            "Speak to a Designated Safeguarding Lead: "
            + ", ".join(f"{s.full_name} ({s.email})" for s in leads)
            if leads else
            "Speak to any member of staff, or to Student Services."
        )
        ttk.Label(
            panel,
            text=(
                "If you or someone else is at risk, do not use this form — it "
                "is not monitored outside office hours.\n" + contact
            ),
            wraplength=1000, justify="left",
        ).pack(anchor="w")

    # ── Data ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        w.clear(self.holder)
        try:
            referrals = pastoral_repo.list_referrals(student_id=self.ctl.student_id)
            checkins = pastoral_repo.list_checkins(student_id=self.ctl.student_id)
            profile = self.ctl.students.profile(self.ctl.student_id)
        except Exception as exc:
            logger.exception("Could not load FE College learner support data")
            w.error(self.host, TITLE, f"Could not load your support records: {exc}")
            return

        columns = ttk.Frame(self.holder)
        columns.pack(fill="both", expand=True)
        columns.columnconfigure(0, weight=3, uniform="s")
        columns.columnconfigure(1, weight=2, uniform="s")
        columns.rowconfigure(0, weight=1)

        left = ttk.Frame(columns)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._requests_panel(left, referrals)
        self._support_panel(left, profile)

        right = ttk.Frame(columns)
        right.grid(row=0, column=1, sticky="nsew")
        self._wellbeing_panel(right, checkins)

        open_count = sum(1 for r in referrals if r.is_open)
        self.host.set_status(
            f"{open_count} open request(s) · {len(checkins)} check-in(s)"
        )

    def _requests_panel(self, parent, referrals) -> None:
        panel = ttk.LabelFrame(parent, text="My support requests", padding=8)
        panel.pack(fill="both", expand=True, pady=(0, 10))
        if not referrals:
            w.empty_state(panel, "You have not asked for any support yet.")
            return

        table = w.DataTable(panel, [
            ("type", "About", 190),
            ("raised", "Raised", 100),
            ("status", "Status", 110),
            ("response", "Response due", 110),
            ("outcome", "Outcome", 250),
        ], height=8)
        table.set_rows([
            {
                "type": r.referral_type,
                "raised": w.when(r.referred_on),
                "status": r.status.replace("_", " "),
                "response": w.when(r.response_due),
                "outcome": r.outcome or ("being looked at" if r.is_open else "—"),
                "_tone": (
                    "good" if r.status == "closed"
                    else "bad" if r.is_breaching()
                    else "warn"
                ),
            }
            for r in referrals
        ])

    def _support_panel(self, parent, profile) -> None:
        plans = profile.support if profile else []
        panel = ttk.LabelFrame(parent, text="Support already in place", padding=8)
        panel.pack(fill="x")
        if not plans:
            w.empty_state(panel, "No learning support is set up for you.")
            return
        table = w.DataTable(panel, [
            ("type", "Support", 210),
            ("status", "Status", 115),
            ("hours", "Hours/week", 95, "e"),
            ("detail", "Detail", 300),
        ], height=min(5, len(plans)))
        table.set_rows([
            {
                "type": p.support_type,
                "status": p.status.replace("_", " "),
                "hours": f"{p.hours_per_week:g}" if p.hours_per_week else "—",
                "detail": p.detail or "—",
                "_tone": "good" if p.is_active else "muted",
            }
            for p in plans
        ])

    def _wellbeing_panel(self, parent, checkins) -> None:
        panel = ttk.LabelFrame(parent, text="How I have been", padding=8)
        panel.pack(fill="both", expand=True)

        summary = trend(checkins)
        if summary.checkins == 0:
            w.empty_state(
                panel,
                "You have not recorded a check-in. It takes a moment, and it "
                "helps your tutor know how things are going.",
            )
            return

        w.kv_panel(panel, "Recent", [
            ("Latest", MOOD_LABELS.get(summary.latest, str(summary.latest))),
            ("Average of last few", str(summary.average)),
            ("Direction", summary.direction,
             "bad" if summary.direction == "declining"
             else "good" if summary.direction == "improving" else "plain"),
        ]).pack(fill="x", pady=(0, 8))

        table = w.DataTable(panel, [
            ("date", "Date", 100),
            ("mood", "How I felt", 130),
            ("note", "Note", 220),
        ], height=10)
        table.set_rows([
            {
                "date": w.when(c.checked_on),
                "mood": c.label,
                "note": c.note or "—",
                "_tone": "bad" if c.is_concern else "plain",
            }
            for c in checkins[:20]
        ])

        if summary.needs_follow_up:
            ttk.Label(
                panel,
                text=("Your tutor will see this and may get in touch. If you "
                      "would rather talk to someone now, Student Services is "
                      "open during college hours."),
                foreground=w.TONE["warn"], wraplength=380, justify="left",
            ).pack(anchor="w", pady=(8, 0))

    # ── Actions ────────────────────────────────────────────────────────────

    def request(self) -> None:
        result = w.ask(self.host, "Ask for support", [
            ("referral_type", "What is it about?", "choice", list(REQUESTABLE)),
            ("reason", "Tell us a bit more", "multiline"),
            ("urgent", "I need help soon", "bool"),
        ], initial={"referral_type": REQUESTABLE[0]}, submit_label="Send request")
        if result is None:
            return
        if not result["reason"].strip():
            w.error(self.host, "Ask for support",
                    "Please say a little about what you need — it goes to the "
                    "right team based on what you write.")
            return

        try:
            referral = pastoral_repo.add_referral(Referral(
                referral_id=None,
                student_id=self.ctl.student_id,
                referral_type=result["referral_type"],
                reason=result["reason"],
                status="open",
                urgency="priority" if result["urgent"] else "routine",
                # Self-referrals are attributed to the learner's own record, so
                # the support team can see it came from them rather than a tutor.
                referred_by=self.ctl.student_id,
                referred_on=date.today(),
            ))
        except ValidationError as exc:
            w.error(self.host, "Ask for support", str(exc))
            return

        w.info(
            self.host, "Request sent",
            f"Your {result['referral_type'].lower()} request has been sent.\n\n"
            f"Someone should be in touch by {w.when(referral.response_due)}.",
        )
        self.refresh()

    def check_in(self) -> None:
        result = w.ask(self.host, "How are you doing?", [
            ("mood", "How have you been?", "choice",
             [f"{n} — {MOOD_LABELS[n]}" for n in MOOD_SCALE]),
            ("note", "Anything you want to add (optional)", "multiline"),
            ("follow_up", "I would like someone to get in touch", "bool"),
        ], initial={"mood": f"3 — {MOOD_LABELS[3]}"}, submit_label="Record")
        if result is None:
            return
        try:
            pastoral_repo.add_checkin(WellbeingCheckIn(
                checkin_id=None,
                student_id=self.ctl.student_id,
                mood=int(result["mood"].split(" — ")[0]),
                checked_on=date.today(),
                source="Self",
                note=result["note"],
                recorded_by=self.ctl.student_id,
                follow_up_needed=result["follow_up"],
            ))
        except ValidationError as exc:
            w.error(self.host, "Check in", str(exc))
            return

        if result["follow_up"]:
            w.info(self.host, "Recorded",
                   "Thanks — your tutor will see this and get in touch.")
        self.refresh()


__all__ = ["REQUESTABLE", "TITLE", "Screen", "open_window"]
