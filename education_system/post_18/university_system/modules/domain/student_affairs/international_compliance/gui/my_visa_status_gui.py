"""Read-only "My visa status" window for the student-facing portal.

Surfaces the bits of the Tier-4 sponsor record the student is allowed to
see — visa expiry, BRP expiry, right-to-study check, ATAS status, current
CAS — so they don't have to email the International Office for routine
status questions.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk

from education_system.post_18.university_system.modules.domain.student_affairs.international_compliance.services import (
    visa_service as vs,
)

logger = logging.getLogger(__name__)


def _days_until(s):
    if not s:
        return None
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    return (d - date.today()).days


def _badge_for_days(days):
    if days is None:
        return "—", "#666666"
    if days < 0:
        return f"EXPIRED ({-days}d ago)", "#b00020"
    if days <= 30:
        return f"{days}d left", "#b00020"
    if days <= 90:
        return f"{days}d left", "#c87a00"
    return f"{days}d left", "#287d3c"


class MyVisaStatusGUI:
    """Read-only Toplevel for the logged-in student's own visa record."""

    def __init__(self, parent=None):
        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("My visa status")
        self.window.geometry("700x620")
        self.window.minsize(600, 520)

        try:
            from education_system.post_18.university_system.infrastructure.shared_context import get_auth
            self.auth = get_auth()
        except Exception:
            self.auth = None

        self.student_id = self._resolve_student_id()
        self._build_ui()
        self._populate()

    def _resolve_student_id(self) -> str:
        if not self.auth or not getattr(self.auth, "current_user", None):
            return ""
        u = self.auth.current_user
        if isinstance(u, dict):
            return str(u.get("student_id") or u.get("username") or "")
        return str(getattr(u, "student_id", "") or getattr(u, "username", "") or "")

    def _build_ui(self):
        outer = ttk.Frame(self.window, padding=14)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text="My visa status",
                  font=("Arial", 16, "bold")).pack(anchor=tk.W)
        self.subtitle = ttk.Label(outer, text="", foreground="#555555")
        self.subtitle.pack(anchor=tk.W, pady=(0, 10))

        self.empty_label = ttk.Label(
            outer,
            text=("No visa record is on file for your account. If you are\n"
                  "an international student and believe this is wrong,\n"
                  "please contact the International Office."),
            foreground="#555555", justify=tk.LEFT,
        )

        self.detail_frame = ttk.Frame(outer)
        self.detail_frame.pack(fill=tk.BOTH, expand=True)

        # Status row at top
        self.status_row = ttk.LabelFrame(self.detail_frame, text="At a glance",
                                          padding=10)
        self.status_row.pack(fill=tk.X)

        self.visa_lbl = ttk.Label(self.status_row, text="Visa: —", font=("Arial", 11))
        self.visa_lbl.grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        self.brp_lbl = ttk.Label(self.status_row, text="BRP: —", font=("Arial", 11))
        self.brp_lbl.grid(row=1, column=0, sticky=tk.W, padx=4, pady=2)
        self.rts_lbl = ttk.Label(self.status_row, text="Right to study: —",
                                  font=("Arial", 11))
        self.rts_lbl.grid(row=2, column=0, sticky=tk.W, padx=4, pady=2)
        self.atas_lbl = ttk.Label(self.status_row, text="ATAS: —", font=("Arial", 11))
        self.atas_lbl.grid(row=3, column=0, sticky=tk.W, padx=4, pady=2)

        # Profile detail
        prof = ttk.LabelFrame(self.detail_frame, text="Profile", padding=10)
        prof.pack(fill=tk.X, pady=(10, 0))
        self.profile_text = tk.Text(prof, height=7, wrap=tk.WORD,
                                     state=tk.DISABLED, bg=self.window.cget("bg"),
                                     relief="flat")
        self.profile_text.pack(fill=tk.X)

        # CAS list
        cas = ttk.LabelFrame(self.detail_frame, text="CAS history", padding=10)
        cas.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.cas_tree = ttk.Treeview(
            cas, columns=("cas", "issued", "programme", "fee_paid", "status"),
            show="headings", height=5,
        )
        for col, txt, w in [("cas", "CAS #", 150), ("issued", "Issued", 110),
                            ("programme", "Programme", 220),
                            ("fee_paid", "Tuition paid £", 110),
                            ("status", "Status", 80)]:
            self.cas_tree.heading(col, text=txt)
            self.cas_tree.column(col, width=w)
        self.cas_tree.pack(fill=tk.BOTH, expand=True)

        # Footer
        footer = ttk.Frame(outer)
        footer.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(
            footer,
            text=("This information is read-only. Need to update it? "
                  "Contact the International Office."),
            foreground="#555555",
        ).pack(side=tk.LEFT)
        ttk.Button(footer, text="Close",
                   command=self.window.destroy).pack(side=tk.RIGHT)

    def _populate(self):
        if not self.student_id:
            self.subtitle.config(text="(not signed in)")
            self.detail_frame.pack_forget()
            self.empty_label.pack(pady=20)
            return

        rec = vs.get_visa_record(self.student_id)
        if not rec:
            self.subtitle.config(text=f"Student ID: {self.student_id}")
            self.detail_frame.pack_forget()
            self.empty_label.pack(pady=20)
            return

        self.subtitle.config(text=f"Student ID: {self.student_id}")

        # Visa expiry chip
        v_days = _days_until(rec.get("visa_expiry_date"))
        v_text, v_color = _badge_for_days(v_days)
        self.visa_lbl.config(
            text=f"Visa: {rec.get('visa_number') or '—'}   "
                 f"expires {rec.get('visa_expiry_date') or '—'}   ({v_text})",
            foreground=v_color,
        )

        # BRP expiry chip
        b_days = _days_until(rec.get("brp_expiry_date"))
        b_text, b_color = _badge_for_days(b_days)
        self.brp_lbl.config(
            text=f"BRP: {rec.get('brp_number') or '—'}   "
                 f"expires {rec.get('brp_expiry_date') or '—'}   ({b_text})",
            foreground=b_color,
        )

        # Right-to-study
        if vs.has_passing_right_to_study(self.student_id):
            self.rts_lbl.config(text="Right to study: ✓ pass on file",
                                 foreground="#287d3c")
        else:
            self.rts_lbl.config(
                text="Right to study: NOT yet on file — please bring your passport "
                     "and visa/BRP to the International Office.",
                foreground="#b00020",
            )

        # ATAS
        atas_modules = vs.atas_required_for_student_modules(self.student_id)
        if not rec.get("atas_required") and not atas_modules:
            self.atas_lbl.config(text="ATAS: not required for your modules",
                                  foreground="#287d3c")
        else:
            ok = all(vs.has_valid_atas(self.student_id, c) for c in atas_modules)
            colour = "#287d3c" if ok else "#b00020"
            txt = "cleared for all restricted modules" if ok else (
                "MISSING for: " + ", ".join(
                    c for c in atas_modules
                    if not vs.has_valid_atas(self.student_id, c)
                )
            )
            self.atas_lbl.config(text=f"ATAS: {txt}", foreground=colour)

        # Profile text
        nat = rec.get("nationality") or "—"
        passport = rec.get("passport_number") or "—"
        passport_exp = rec.get("passport_expiry") or "—"
        sponsor = rec.get("sponsor_licence_ref") or "—"
        status = rec.get("status") or "—"
        body = (
            f"Visa type:           {rec.get('visa_type') or '—'}\n"
            f"Sponsor licence:     {sponsor}\n"
            f"Sponsorship status:  {status}\n"
            f"Nationality:         {nat}\n"
            f"Passport number:     {passport}\n"
            f"Passport expires:    {passport_exp}"
        )
        self.profile_text.config(state=tk.NORMAL)
        self.profile_text.delete("1.0", tk.END)
        self.profile_text.insert("1.0", body)
        self.profile_text.config(state=tk.DISABLED)

        # CAS history
        for c in vs.list_cas_for_student(self.student_id):
            paid = c.get("tuition_fee_paid_gbp") or 0
            fee = c.get("tuition_fee_gbp") or 0
            paid_text = f"{paid:.2f}" + (f" / {fee:.2f}" if fee else "")
            self.cas_tree.insert("", tk.END, values=(
                c.get("cas_number", ""), c.get("issued_at", ""),
                c.get("programme", ""), paid_text, c.get("status", ""),
            ))
