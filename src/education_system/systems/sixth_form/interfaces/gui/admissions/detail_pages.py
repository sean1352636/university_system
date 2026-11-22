"""Applicant detail dialog pages: profile & eligibility, contacts,
sensitive information and identity / right to study.

Each page is a small class built into a frame of the detail dialog's
sidebar; ``refresh()`` reloads it from the domain. Every write goes
through ``applicant_actions.attempt`` so a refusal is shown.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)
from education_system.systems.sixth_form.domain.admissions import (
    applicant_details as details,
)

from . import _admissions_ui as ui
from . import applicant_actions as act

logger = logging.getLogger(__name__)

_FLAGS = [k for k, _l in details.PROFILE_FIELDS if k in data.FLAG_COLUMNS]
_TEXT = [k for k, _l in details.PROFILE_FIELDS if k not in data.FLAG_COLUMNS]
_LABELS = dict(details.PROFILE_FIELDS)


def _clear(frame: tk.Misc) -> None:
    for w in frame.winfo_children():
        w.destroy()


def _error(frame: tk.Misc, e: BaseException) -> None:
    ttk.Label(frame, text=act.describe(e), foreground="#b00000",
              wraplength=700, justify="left").pack(anchor="w", padx=10,
                                                   pady=10)


class Page:
    """A detail page: builds into *frame*; ``notify`` refreshes the
    dialog and the list behind it after a change."""

    def __init__(self, frame: tk.Misc, aid: str,
                 notify: Callable[[], None]) -> None:
        self.frame = frame
        self.aid = aid
        self.notify = notify

    def refresh(self) -> None:
        _clear(self.frame)
        try:
            self.build()
        except Exception as e:  # noqa: BLE001 — shown on the page
            logger.debug("page build failed", exc_info=True)
            _clear(self.frame)
            _error(self.frame, e)

    def build(self) -> None:  # pragma: no cover — overridden
        raise NotImplementedError


# ── Profile & eligibility ──────────────────────────────────────────

class ProfilePage(Page):
    def build(self) -> None:
        a = data.get_applicant(self.aid)
        if a is None:
            return
        f = self.frame
        bar = ttk.Frame(f)
        bar.pack(side="bottom", fill="x", padx=10, pady=8)
        save = ttk.Button(bar, text="Save profile", command=self._save)
        save.pack(side="left")
        act.gate(save, act.can_admissions() and not a.is_archived)
        if a.is_archived:
            ttk.Label(bar, foreground="#b00000", text="Archived — restore it "
                      "before changing it.").pack(side="left", padx=8)
        top = ttk.LabelFrame(f, text="Profile")
        top.pack(fill="x", padx=10, pady=(8, 4))
        self._eth = dict(details.ethnicities())
        self.w: dict[str, object] = {}
        options = {
            "sex": ("",) + details.GENDER_OPTIONS,
            "ethnicity": ("",) + tuple(self._eth.values()),
            "residency_status": ("",) + details.RESIDENCY_STATUSES,
        }
        for r, key in enumerate(_TEXT):
            ttk.Label(top, text=_LABELS[key] + ":").grid(
                row=r, column=0, sticky="e", padx=6, pady=2)
            value = getattr(a, key) or ""
            if key == "ethnicity":
                value = self._eth.get(value, value)
            elif key == "sex":
                value = details.gender_label(value)
            if key in options:
                w = ttk.Combobox(top, values=options[key], state="readonly",
                                 width=60)
                w.set(value)
            else:
                w = ttk.Entry(top, width=30)
                w.insert(0, value)
            w.grid(row=r, column=1, sticky="w", padx=6, pady=2)
            self.w[key] = w
        ttk.Label(top, text="16–19 funding residency:").grid(
            row=len(_TEXT), column=0, sticky="e", padx=6, pady=2)
        elig = details.funding_eligibility(a)
        ttk.Label(top, text=elig, foreground=(
            "#2e7d32" if elig == "Eligible" else "#a06000")).grid(
            row=len(_TEXT), column=1, sticky="w", padx=6)
        flags = ttk.LabelFrame(f, text="Flags")
        flags.pack(fill="x", padx=10, pady=4)
        self.v: dict[str, tk.BooleanVar] = {}
        for i, key in enumerate(_FLAGS):
            var = tk.BooleanVar(value=bool(getattr(a, key)))
            self.v[key] = var
            ttk.Checkbutton(flags, text=_LABELS[key], variable=var).grid(
                row=i // 2, column=i % 2, sticky="w", padx=8, pady=1)
        life = ttk.LabelFrame(f, text="Lifecycle")
        life.pack(fill="x", padx=10, pady=4)
        for r, (k, v) in enumerate((
                ("Withdrawal / decline reason", a.withdrawal_reason),
                ("Deferred from", a.deferred_from),
                ("Archived", (f"{a.archived_at} by {a.archived_by or '?'} — "
                              f"{a.archive_reason or ''}")
                 if a.archived_at else None),
                ("Merged into", a.merged_into))):
            ttk.Label(life, text=k + ":").grid(row=r, column=0, sticky="e",
                                               padx=6)
            ttk.Label(life, text=v or "—").grid(row=r, column=1, sticky="w",
                                                padx=6)

    def _save(self) -> None:
        fields: dict[str, object] = {}
        for key, w in self.w.items():
            value = w.get().strip()  # type: ignore[attr-defined]
            if key == "ethnicity" and value:
                value = next((c for c, lbl in self._eth.items()
                              if lbl == value), value)
            fields[key] = value or None
        fields.update({k: v.get() for k, v in self.v.items()})
        ok, _ = act.attempt(self.frame, "Profile", details.update_profile,
                            self.aid, **fields)
        if ok:
            self.notify()


# ── Contacts ───────────────────────────────────────────────────────

_CONTACT_FIELDS: list[ui.Field] = [
    ("name", "Name", "entry", None),
    ("relationship", "Relationship", "readonly",
     ("",) + details.CONTACT_RELATIONSHIPS),
    ("phone", "Phone", "entry", None),
    ("email", "Email", "entry", None),
    ("address", "Address", "entry", None),
    ("is_emergency", "Emergency contact", "check", None),
    ("parental_responsibility", "Parental responsibility", "check", None),
    ("receives_correspondence", "Receives letters / e-mails", "check", None),
]


class ContactsPage(Page):
    COLS = [("name", "Name", 170), ("rel", "Relationship", 110),
            ("phone", "Phone", 120), ("email", "Email", 200),
            ("em", "Emergency", 75), ("pr", "PR", 40),
            ("corr", "Letters", 60)]

    def build(self) -> None:
        f = self.frame
        bar = ttk.Frame(f)
        bar.pack(side="top", fill="x", padx=10, pady=(8, 4))
        for text, cmd in (("Add contact…", self._add),
                          ("Edit…", self._edit), ("Remove", self._remove)):
            act.gate(ttk.Button(bar, text=text, command=cmd),
                     act.can_admissions()).pack(side="left", padx=(0, 4))
        ttk.Label(f, foreground="#555", text=(
            "Parents/carers and emergency contacts. Contacts who receive "
            "letters get admissions e-mails when 'also send to parents' is "
            "ticked, and are carried into the student record at "
            "conversion.")).pack(fill="x", padx=10)
        holder = ttk.Frame(f)
        holder.pack(fill="both", expand=True, padx=10, pady=6)
        self.tree = ui.make_tree(holder, self.COLS, height=10)
        self.tree.bind("<Double-1>", lambda _e: self._edit())
        for c in details.list_contacts(self.aid):
            self.tree.insert("", "end", iid=str(c.contact_id), values=(
                c.name, c.relationship or "", c.phone or "", c.email or "",
                "Yes" if c.is_emergency else "",
                "Yes" if c.parental_responsibility else "",
                "Yes" if c.receives_correspondence else ""))

    def _add(self) -> None:
        if ui.ask_form(self.frame, "Add contact", _CONTACT_FIELDS,
                       {"receives_correspondence": True},
                       on_submit=lambda v: details.add_contact(self.aid, v)):
            self.notify()

    def _edit(self) -> None:
        iid = ui.require_iid(self.tree, "Contacts")
        if iid is None:
            return
        ok, c = act.attempt(self.frame, "Contacts", details.get_contact,
                            int(iid))
        if not ok or c is None:
            return
        if ui.ask_form(self.frame, "Edit contact", _CONTACT_FIELDS, vars(c),
                       on_submit=lambda v: details.update_contact(int(iid),
                                                                  v)):
            self.notify()

    def _remove(self) -> None:
        iid = ui.require_iid(self.tree, "Contacts")
        if iid is None:
            return
        from education_system.platform.delivery.gui.parented_dialogs import (
            messagebox,
        )
        if not messagebox.askyesno("Remove contact", "Remove this contact?",
                                   parent=self.frame.winfo_toplevel()):
            return
        ok, _ = act.attempt(self.frame, "Contacts", details.remove_contact,
                            int(iid))
        if ok:
            self.notify()


# ── Sensitive ──────────────────────────────────────────────────────

class SensitivePage(Page):
    """SEND / medical / safeguarding. Admissions staff see only whether
    something is held; the text and editing need the area's
    capability (each view is logged)."""

    def build(self) -> None:
        f = self.frame
        view = details.get_sensitive(self.aid)
        ttk.Label(f, foreground="#555", wraplength=760, justify="left",
                  text=("Sensitive information is handed to its own register "
                        "at conversion. You see the text only for areas you "
                        "have access to; opening it is logged.")).pack(
            fill="x", padx=10, pady=(8, 4))
        self.texts: dict[str, tk.Text] = {}
        self.received: ttk.Entry | None = None
        for area, (_col, _cap, label) in details.SENSITIVE_AREAS.items():
            lf = ttk.LabelFrame(f, text=label)
            lf.pack(fill="x", padx=10, pady=4)
            held = view.held.get(area)
            if area not in view.visible:
                ttk.Label(lf, text=("Held — you do not have access to view "
                                    "it." if held else "Nothing recorded."),
                          foreground="#a06000" if held else "#555").pack(
                    anchor="w", padx=6, pady=4)
                continue
            t = tk.Text(lf, height=4, wrap="word", width=90)
            t.insert("1.0", view.visible.get(area) or "")
            t.pack(fill="x", padx=6, pady=(4, 2))
            self.texts[area] = t
            row = ttk.Frame(lf)
            row.pack(fill="x", padx=6, pady=(0, 4))
            if area == "safeguarding":
                ttk.Label(row, text="Received from:").pack(side="left")
                self.received = ttk.Entry(row, width=40)
                self.received.insert(0, view.received_from or "")
                self.received.pack(side="left", padx=4)
            ttk.Button(row, text="Save", command=lambda a=area: self._save(
                a)).pack(side="right")

    def _save(self, area: str) -> None:
        text = self.texts[area].get("1.0", "end").strip()
        kw = {}
        if area == "safeguarding" and self.received is not None:
            kw["received_from"] = self.received.get().strip()
        ok, _ = act.attempt(self.frame, "Sensitive information",
                            details.set_sensitive, self.aid, area, text, **kw)
        if ok:
            self.notify()


# ── Identity & right to study ──────────────────────────────────────

def _id_types() -> tuple[str, ...]:
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        identity_checks,
    )
    return identity_checks.ID_DOCUMENT_TYPES


class IdentityPage(Page):
    HIST = [("on", "Checked on", 95), ("doc", "Document", 190),
            ("last4", "Last 4", 60), ("rts", "Right to study", 220),
            ("visa", "Visa", 120), ("exp", "Visa expiry", 95),
            ("by", "Checked by", 110)]

    def build(self) -> None:
        f = self.frame
        bar = ttk.Frame(f)
        bar.pack(side="top", fill="x", padx=10, pady=(8, 4))
        act.gate(ttk.Button(bar, text="Record ID / right-to-study check…",
                            command=self._record),
                 act.can_admissions()).pack(side="left")
        rec = details.get_identity(self.aid)
        ok, why = details.identity_ok(self.aid)
        cur = ttk.LabelFrame(f, text="Current check")
        cur.pack(fill="x", padx=10, pady=4)
        ttk.Label(cur, text=("✓ " if ok else "✗ ") + why,
                  foreground="#2e7d32" if ok else "#b00000").pack(
            anchor="w", padx=6, pady=2)
        if rec is not None:
            for k, v in (("Document", rec.document_type),
                         ("Number (last 4)", rec.id_number_last4),
                         ("Right to study", rec.right_to_study),
                         ("Visa", rec.visa_type),
                         ("Visa expiry", rec.visa_expiry),
                         ("Checked", f"{rec.checked_on or '—'} by "
                                     f"{rec.checked_by or '—'}"),
                         ("Notes", rec.notes)):
                ttk.Label(cur, text=f"{k}: {v or '—'}").pack(anchor="w",
                                                            padx=6)
        ttk.Label(f, text="History", font=("TkDefaultFont", 10, "bold")).pack(
            anchor="w", padx=10, pady=(8, 0))
        holder = ttk.Frame(f)
        holder.pack(fill="both", expand=True, padx=10, pady=(2, 8))
        tree = ui.make_tree(holder, self.HIST, height=8)
        for h in details.identity_history(self.aid):
            tree.insert("", "end", values=(
                h.get("checked_on") or "", h.get("document_type") or "",
                h.get("id_number_last4") or "", h.get("right_to_study") or "",
                h.get("visa_type") or "", h.get("visa_expiry") or "",
                h.get("checked_by") or ""))

    def _record(self) -> None:
        if ui.ask_form(self.frame, "ID / right-to-study check", [
                ("document_type", "Document type", "readonly", _id_types()),
                ("document_number", "Document number (only last 4 kept)",
                 "entry", None),
                ("right_to_study", "Right to study", "readonly",
                 details.RIGHT_TO_STUDY),
                ("visa_type", "Visa type", "entry", None),
                ("visa_expiry", "Visa expiry (YYYY-MM-DD)", "entry", None),
                ("checked_on", "Checked on (blank = today)", "entry", None),
                ("notes", "Notes", "text", None)],
                {"right_to_study": details.RIGHT_TO_STUDY[0]},
                on_submit=lambda v: details.record_identity_check(
                    self.aid, **{k: (val or None) if k not in (
                        "document_type", "document_number", "right_to_study")
                        else val for k, val in v.items()})):
            self.notify()
