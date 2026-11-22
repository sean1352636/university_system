"""Applicant detail and add/edit dialogs for the Sixth Form Admissions window.

Split out of ``admissions_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable
import datetime as _dt
import logging
import os
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from typing import Callable
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)
from education_system.systems.sixth_form.domain.admissions import (
    applicant_reports as reports,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
    DEFAULT_OFFER_TYPE,
    DEFAULT_SOURCE,
    DEFAULT_STATUS,
    DOCUMENT_TYPES,
    REFERENCE_STATUSES,
    SOURCES,
    ValidationError,
)
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.systems.sixth_form.domain.admissions.admissions import (
    INITIAL_STATUSES,
)
from . import _admissions_ui as ui
from . import applicant_actions as act
from . import applicant_email
from ._common import _compute_age, _days_in_stage, _gcse_concerns, _open_path, _parse_date, _prompt, _subject_options, _today
from ._sidecar import REQUIRED_DOCS

logger = logging.getLogger(__name__)


# ══ Dialogs ═══════════════════════════════════════════════════════

class DetailDialog:
    """Applicant record: sections down a sidebar (profile, eligibility,
    contacts, sensitive information, identity, documents & references,
    interview booking, open events, notes, timeline, re-applications,
    communications), with the record actions along the bottom."""

    _GROUPS = {
        "Profile": "Applicant", "Profile & eligibility": "Applicant",
        "Contacts": "Applicant", "Sensitive": "Applicant",
        "Identity & right to study": "Applicant",
        "Documents & References": "Application",
        "Interview booking": "Application", "Open events": "Application",
        "Re-applications": "Application",
        "Notes": "Record", "Timeline": "Record", "Communications": "Record",
    }

    def __init__(self, parent: tk.Misc, applicant: Applicant,
                 on_change: Callable[[], None]) -> None:
        self.aid = applicant.applicant_id
        self.on_change = on_change
        self._photo_img: tk.PhotoImage | None = None  # keep a reference
        self.win = ui.new_window(
            parent, f"Applicant {applicant.applicant_id} — "
                    f"{applicant.full_name}")
        # Action rows first (bottom up) so the sidebar never clips them.
        from education_system.systems.sixth_form.interfaces.gui.admissions import (
            applicant_extras_views,
        )
        applicant_extras_views.add_workflow_footer(  # choices/GCSEs/refs
            self.win, self.aid, self._notify)
        self._build_lifecycle_bar()
        footer = ttk.Frame(self.win)
        footer.pack(side="bottom", fill="x", padx=8, pady=(0, 6))
        adm_ok = act.can_admissions()
        act.gate(ttk.Button(footer, text="Email applicant…",
                            command=self._email), adm_ok).pack(side="left")
        act.gate(ttk.Button(footer, text="Offer letter…",
                            command=self._letter), adm_ok).pack(
            side="left", padx=4)
        ttk.Button(footer, text="Open student record",
                   command=self._open_student).pack(side="left", padx=4)

        # Extra single-applicant actions (items 36–45).
        more_mb = ttk.Menubutton(footer, text="More ▾")
        mmenu = tk.Menu(more_mb, tearoff=0)
        mmenu.add_command(label="Custom email…",
                          command=self._send_custom_email)
        mmenu.add_command(label="Quick standard offer",
                          command=self._quick_offer)
        mmenu.add_command(label="Print offer letter",
                          command=self._print_offer_letter)
        mmenu.add_command(label="Offer status / expiry…",
                          command=self._offer_expiry_reminder)
        mmenu.add_separator()
        mmenu.add_command(label="Communications log…",
                          command=self._communication_log)
        mmenu.add_command(label="Score vs cohort…",
                          command=self._score_comparison)
        mmenu.add_command(label="Chase all outstanding references…",
                          command=self._reference_chase_all)
        for label in ("Custom email…", "Quick standard offer",
                      "Chase all outstanding references…"):
            act.gate_menu(mmenu, label, adm_ok)
        more_mb["menu"] = mmenu
        more_mb.pack(side="left", padx=4)

        ttk.Button(footer, text="GDPR export…",
                   command=self._gdpr_export).pack(side="right")
        act.gate(ttk.Button(footer, text="Request erasure…",
                            command=self._gdpr_erase), adm_ok).pack(
            side="right", padx=4)

        self.banner = ttk.Label(self.win, text="", foreground="#b00000",
                                anchor="w")
        self.banner.pack(side="top", fill="x", padx=10, pady=(6, 0))
        nb = SidebarBook(self.win, groups=self._GROUPS, title="Applicant")
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.nb = nb
        self.profile = ttk.Frame(nb)
        self.docs_tab = ttk.Frame(nb)
        self.notes_tab = ttk.Frame(nb)
        self.timeline_tab = ttk.Frame(nb)
        self._pages: dict[str, object] = {}
        self._built: set[str] = set()
        from . import detail_pages as dp
        from . import detail_workflow_pages as dw
        page_classes = {
            "Profile & eligibility": lambda f: dp.ProfilePage(
                f, self.aid, self._notify),
            "Contacts": lambda f: dp.ContactsPage(f, self.aid, self._notify),
            "Sensitive": lambda f: dp.SensitivePage(f, self.aid,
                                                    self._notify),
            "Identity & right to study": lambda f: dp.IdentityPage(
                f, self.aid, self._notify),
            "Interview booking": lambda f: dw.InterviewPage(
                f, self.aid, self._notify),
            "Open events": lambda f: dw.OpenEventsPage(f, self.aid,
                                                       self._notify),
            "Re-applications": lambda f: dw.ReapplicationsPage(
                f, self.aid, self._notify, self._open_other),
            "Communications": lambda f: dw.CommunicationsPage(
                f, self.aid, self._notify, self._send_custom_email),
        }
        order = ["Profile", "Profile & eligibility", "Contacts", "Sensitive",
                 "Identity & right to study", "Documents & References",
                 "Interview booking", "Open events", "Re-applications",
                 "Notes", "Timeline", "Communications"]
        fixed = {"Profile": self.profile, "Documents & References":
                 self.docs_tab, "Notes": self.notes_tab,
                 "Timeline": self.timeline_tab}
        self._frames: dict[str, ttk.Frame] = {}
        for name in order:
            if name in fixed:
                nb.add(fixed[name], text=name)
                continue
            frame = ttk.Frame(nb)
            self._frames[name] = frame
            self._pages[name] = page_classes[name](frame)
            nb.add(frame, text=name,
                   on_show=lambda n=name: self._show_page(n))
        self.refresh()

    def _build_lifecycle_bar(self) -> None:
        """Record lifecycle actions (status, reopen, withdraw, decline,
        defer, archive, restore, convert), always visible."""
        bar = ttk.Frame(self.win)
        bar.pack(side="bottom", fill="x", padx=8, pady=(0, 4))
        ok = act.can_admissions()
        self._life_buttons: dict[str, ttk.Button] = {}
        for text, cmd in (
                ("Change status…", self._status),
                ("Reopen…", self._reopen),
                ("Withdraw…", lambda: self._withdraw(False)),
                ("Decline offer…", lambda: self._withdraw(True)),
                ("Defer…", self._defer),
                ("Archive…", self._archive),
                ("Restore", self._restore),
                ("Convert to student…", self._convert)):
            b = ttk.Button(bar, text=text, command=cmd)
            b.pack(side="left", padx=(0, 4))
            self._life_buttons[text] = b
            act.gate(b, ok)
        act.gate(self._life_buttons["Convert to student…"], act.can_convert())

    def _sync_lifecycle(self, a: Applicant) -> None:
        from education_system.systems.sixth_form.domain.admissions import (
            status_rules,
        )
        ok = act.can_admissions()
        live = not a.is_archived
        rules = {
            "Change status…": live and bool(data.allowed_statuses(a.applicant_id)),
            "Reopen…": live and a.status in status_rules.REOPENABLE,
            "Withdraw…": live and "Withdrawn" in data.allowed_statuses(
                a.applicant_id),
            "Decline offer…": live and a.status in ("Offer Made",
                                                     "Offer Accepted"),
            "Defer…": live and "Deferred" in data.allowed_statuses(
                a.applicant_id),
            "Archive…": live,
            "Restore": a.is_archived and not a.merged_into,
        }
        for text, allowed in rules.items():
            act.gate(self._life_buttons[text], ok and allowed)
        act.gate(self._life_buttons["Convert to student…"],
                 act.can_convert() and live and not a.converted_student_id
                 and a.status == "Offer Accepted")

    def _show_page(self, name: str) -> None:
        if name not in self._built:
            self._built.add(name)
            self._pages[name].refresh()  # type: ignore[attr-defined]

    def _open_other(self, applicant_id: str) -> None:
        other = data.get_applicant(applicant_id)
        if other is not None:
            DetailDialog(self.win, other, on_change=self.on_change)

    def _email(self) -> None:
        applicant_email.email_applicant(self.win, self.aid,
                                        on_sent=self._notify)

    def _letter(self) -> None:
        applicant_email.offer_letter(self.win, self.aid,
                                     on_sent=self._notify)

    def _open_student(self) -> None:
        a = self._applicant()
        if a is None or not a.converted_student_id:
            messagebox.showinfo("Student record",
                                "This applicant has not been enrolled.",
                                parent=self.win)
            return
        from . import detail_student_link
        detail_student_link.open_student(self.win, a.converted_student_id)

    def _gdpr_export(self) -> None:
        import json
        ok, payload = act.attempt(self.win, "GDPR export",
                                  reports.gdpr_export, self.aid)
        if not ok:
            return
        TextViewerDialog(self.win, f"GDPR export — {self.aid}",
                         json.dumps(payload, indent=2, default=str),
                         save_name=f"gdpr_{self.aid}.json")

    def _gdpr_erase(self) -> None:
        def erased() -> None:
            self.on_change()
            self.win.destroy()
        act.erasure(self.win, self.aid, self._notify, erased)

    # ── lifecycle actions ───────────────────────────────────────
    def _status(self) -> None:
        a = self._applicant()
        if a is not None:
            StatusDialog(self.win, a, on_save=self._notify)

    def _reopen(self) -> None:
        act.reopen(self.win, self.aid, self._notify)

    def _withdraw(self, decline: bool) -> None:
        act.withdraw_or_decline(self.win, [self.aid], decline=decline,
                                on_done=self._notify)

    def _defer(self) -> None:
        act.defer(self.win, self.aid, self._notify)

    def _archive(self) -> None:
        act.archive(self.win, [self.aid], self._notify)

    def _restore(self) -> None:
        act.restore(self.win, [self.aid], self._notify)

    def _convert(self) -> None:
        from . import applicant_convert
        applicant_convert.convert_many(self.win, [self.aid], self._notify)

    # ── data ────────────────────────────────────────────────────
    def _applicant(self) -> Applicant | None:
        return data.get_applicant(self.aid)

    def refresh(self) -> None:
        a = self._applicant()
        if a is None:
            self.win.destroy()
            return
        banner = []
        if a.merged_into:
            banner.append(f"Merged into {a.merged_into} — its records are "
                          "there now.")
        elif a.is_archived:
            banner.append(f"Archived {a.archived_at} by {a.archived_by or '?'}"
                          f": {a.archive_reason or ''} — restore it before "
                          "changing it.")
        if a.converted_student_id:
            banner.append(f"Enrolled as student {a.converted_student_id}.")
        self.banner.configure(text="  ".join(banner))
        self._sync_lifecycle(a)
        self._build_profile(a)
        self._build_docs(a)
        self._build_notes(a)
        self._build_timeline(a)
        for name in self._built:
            self._pages[name].refresh()  # type: ignore[attr-defined]

    @staticmethod
    def _clear(frame: ttk.Frame) -> None:
        for w in frame.winfo_children():
            w.destroy()

    # ── Profile tab (11, 14, 20, 25) ────────────────────────────
    def _build_profile(self, a: Applicant) -> None:
        self._clear(self.profile)
        top = ttk.Frame(self.profile)
        top.pack(fill="x", padx=10, pady=8)

        # Photo / avatar (item 20).
        photo = data.get_photo(self.aid)
        ph_frame = ttk.LabelFrame(top, text="Photo")
        ph_frame.pack(side="right", padx=(10, 0))
        img = None
        if photo:
            try:
                img = tk.PhotoImage(file=photo.path)
                # Downscale very large images crudely to fit.
                if img.width() > 160:
                    img = img.subsample(max(1, img.width() // 160))
            except Exception:
                img = None
        if img is not None:
            self._photo_img = img
            ttk.Label(ph_frame, image=img).pack(padx=4, pady=4)
        else:
            ttk.Label(ph_frame, text="(no photo)\nPNG/GIF",
                       width=14, anchor="center",
                       justify="center").pack(padx=12, pady=20)

        grid = ttk.Frame(top)
        grid.pack(side="left", fill="both", expand=True)

        def section(title: str, rows: list[tuple[str, str]]) -> None:
            lf = ttk.LabelFrame(grid, text=title)
            lf.pack(fill="x", pady=4)
            for i, (k, v) in enumerate(rows):
                ttk.Label(lf, text=f"{k}:", width=16, anchor="e").grid(
                    row=i, column=0, sticky="e", padx=4, pady=1)
                ttk.Label(lf, text=v or "—", anchor="w",
                           wraplength=460, justify="left").grid(
                    row=i, column=1, sticky="w", padx=4, pady=1)

        age = _compute_age(a.dob)
        section("Personal", [
            ("Applicant ID", a.applicant_id),
            ("Name", a.full_name),
            ("DOB", f"{a.dob or '—'}"
                    + (f"  (age {age})" if age is not None else "")),
            ("Email", a.email or "—"),
            ("Phone", a.phone or "—"),
            ("Address", a.address or "—"),
        ])
        section("Academic", [
            ("Previous school", a.previous_school or "—"),
            ("Predicted GCSEs", a.predicted_gcses or "—"),
            ("Subjects", ", ".join(a.subjects) if a.subjects else "—"),
        ])
        section("Application", [
            ("Source", a.application_source),
            ("Submitted", a.submitted_at),
            ("Status", a.status),
            ("Days in stage", str(_days_in_stage(a) or 0)),
        ])
        if a.offer_type or a.decision_by or a.decision_reason:
            section("Offer & Decision", [
                ("Offer", a.offer_type or "—"),
                ("Conditions", a.offer_conditions or "—"),
                ("Offer expiry", a.offer_expiry or "—"),
                ("Decided by", a.decision_by or "—"),
                ("Decision date", a.decision_date or "—"),
                ("Reason code", a.decision_reason or "—"),
                ("Decision notes", a.decision_notes or "—"),
                ("Follow-up flag", "Yes" if a.follow_up else "No"),
                ("Enrolled as", a.converted_student_id or "—"),
            ])

        # GCSE-vs-conditions heuristic (item 14).
        concern = _gcse_concerns(a.predicted_gcses, a.offer_conditions)
        if concern:
            warn = ttk.Label(self.profile, text="⚠ " + concern,
                              foreground="#b00000", wraplength=760,
                              justify="left")
            warn.pack(fill="x", padx=12, pady=(0, 4))

        # Interview scorecard summary (item 25).
        score = data.get_interview_score(self.aid)
        sf = ttk.LabelFrame(self.profile, text="Interview scorecard")
        sf.pack(fill="x", padx=10, pady=6)
        if score is None:
            ttk.Label(sf, text="No scorecard recorded.").pack(
                side="left", padx=6, pady=4)
        else:
            txt = (f"Motivation {score.motivation or '—'} · "
                   f"Subject fit {score.subject_fit or '—'} · "
                   f"Attainment {score.attainment or '—'}  "
                   f"→ avg {score.average if score.average is not None else '—'}"
                   f"   |   Recommendation: {score.recommendation or '—'}")
            ttk.Label(sf, text=txt).pack(side="left", padx=6, pady=4)
            if score.comments:
                ttk.Label(sf, text=score.comments, wraplength=740,
                           foreground="#444").pack(
                    fill="x", padx=6, pady=(0, 4))
        ttk.Button(sf, text="Edit scorecard…",
                    command=self._edit_score).pack(side="right", padx=6)

    # ── Documents & References tab (16, 17, 20) ─────────────────
    def _build_docs(self, a: Applicant) -> None:
        self._clear(self.docs_tab)

        # References (item 17) — one system: the reference tracker.
        ref = ttk.LabelFrame(self.docs_tab, text="Reference")
        ref.pack(fill="x", padx=10, pady=8)
        ttk.Label(ref, text=f"Referee: {a.reference_name or '—'}  "
                            f"({a.reference_contact or '—'})").grid(
            row=0, column=0, columnspan=4, sticky="w", padx=6, pady=2)
        tracked = None
        tracked_refs = []
        try:
            from education_system.systems.sixth_form.domain.admissions import (
                references as _refs,
            )
            tracked = _refs.tracker_status(self.aid)
            tracked_refs = _refs.list_references(applicant_id=self.aid)
        except Exception:  # noqa: BLE001 — falls back to the stored status
            logger.debug("reference tracker unreadable", exc_info=True)
        ttk.Label(ref, text="Status:").grid(row=1, column=0,
                                            sticky="e", padx=6)
        self.ref_cb = ttk.Combobox(ref, values=REFERENCE_STATUSES,
                                   state="readonly", width=16)
        self.ref_cb.set(tracked or a.reference_status)
        self.ref_cb.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        set_btn = ttk.Button(ref, text="Set", command=self._set_ref_status)
        set_btn.grid(row=1, column=2, padx=4)
        chase_btn = ttk.Button(ref, text="Chase referee",
                               command=lambda: self._chase(a))
        chase_btn.grid(row=1, column=3, padx=4)
        act.gate(chase_btn, act.can_admissions())
        if tracked is not None:
            self.ref_cb.configure(state="disabled")
            act.gate(set_btn, False)
            ttk.Label(ref, foreground="#555", text=(
                "Follows the reference tracker: " + "; ".join(
                    f"#{r.reference_id} {r.referee_name} — {r.status}"
                    + (" (overdue)" if r.is_overdue else "")
                    for r in tracked_refs))).grid(
                row=2, column=0, columnspan=4, sticky="w", padx=6, pady=2)
        else:
            act.gate(set_btn, act.can_admissions())

        # Documents (item 16) + Photo (item 20).
        dl = ttk.LabelFrame(self.docs_tab, text="Documents")
        dl.pack(fill="both", expand=True, padx=10, pady=8)
        cols = ("type", "label", "added")
        self.doc_tree = ttk.Treeview(dl, columns=cols, show="headings",
                                      height=10)
        for c, w in (("type", 150), ("label", 380), ("added", 160)):
            self.doc_tree.heading(c, text=c.capitalize())
            self.doc_tree.column(c, width=w, anchor="w")
        self.doc_tree.pack(fill="both", expand=True, side="left",
                            padx=(4, 0), pady=4)
        self._docs = {d.id: d for d in data.list_documents(self.aid)}
        for d in self._docs.values():
            self.doc_tree.insert("", "end", iid=str(d.id), values=(
                d.doc_type, d.label or "—", d.added_at))
        self.doc_tree.bind("<Double-1>", lambda _e: self._open_doc())
        self.doc_tree.bind("<<TreeviewSelect>>",
                            lambda _e: self._document_preview())

        bar = ttk.Frame(dl)
        bar.pack(side="right", fill="y", padx=4, pady=4)
        ttk.Button(bar, text="Add…", command=self._add_doc).pack(
            fill="x", pady=2)
        ttk.Button(bar, text="Add several…",
                    command=self._bulk_upload_docs).pack(fill="x", pady=2)
        ttk.Button(bar, text="Set photo…",
                    command=lambda: self._add_doc(force_type="Photo")).pack(
            fill="x", pady=2)
        ttk.Button(bar, text="Open", command=self._open_doc).pack(
            fill="x", pady=2)
        ttk.Button(bar, text="Remove", command=self._remove_doc).pack(
            fill="x", pady=2)
        # Inline preview pane (item 40).
        self._preview_img: tk.PhotoImage | None = None
        self.doc_preview = ttk.Label(bar, text="(preview)", anchor="center",
                                      relief="solid", borderwidth=1,
                                      width=18)
        self.doc_preview.pack(fill="x", pady=(8, 2))

        # Required-document checklist (item 42).
        present = {d.doc_type for d in self._docs.values()}
        check = ttk.LabelFrame(self.docs_tab, text="Required documents")
        check.pack(fill="x", padx=10, pady=(0, 8))
        for req in REQUIRED_DOCS:
            ok = req in present
            ttk.Label(check, text=f"{'✓' if ok else '✗'}  {req}",
                       foreground="#2e7d32" if ok else "#b00000").pack(
                anchor="w", padx=8, pady=1)

    # ── Notes tab (18) ──────────────────────────────────────────
    def _build_notes(self, a: Applicant) -> None:
        self._clear(self.notes_tab)
        entry = ttk.Frame(self.notes_tab)
        entry.pack(fill="x", padx=10, pady=8)
        ttk.Label(entry, text="Author:").pack(side="left")
        self.note_author = ttk.Entry(entry, width=16)
        self.note_author.pack(side="left", padx=(2, 8))
        ttk.Label(entry, text="Note:").pack(side="left")
        self.note_body = ttk.Entry(entry, width=46)
        self.note_body.pack(side="left", padx=2, fill="x", expand=True)
        self.note_body.bind("<Return>", lambda _e: self._add_note())
        ttk.Button(entry, text="Add note",
                    command=self._add_note).pack(side="left", padx=6)

        thread = tk.Text(self.notes_tab, wrap="word", state="disabled",
                          font=("TkDefaultFont", 10))
        thread.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        notes = data.list_notes(self.aid)
        thread.configure(state="normal")
        if not notes:
            thread.insert("end", "No notes yet.")
        for n in notes:
            thread.insert("end", f"{n.at}  —  {n.author or 'unknown'}\n",
                           ("hdr",))
            thread.insert("end", f"{n.body}\n\n")
        thread.tag_configure("hdr", foreground="#205080",
                              font=("TkDefaultFont", 9, "bold"))
        thread.configure(state="disabled")

    # ── Timeline tab (12) ───────────────────────────────────────
    def _build_timeline(self, a: Applicant) -> None:
        self._clear(self.timeline_tab)
        holder = ttk.Frame(self.timeline_tab)
        holder.pack(fill="both", expand=True, padx=10, pady=10)
        tree = ui.make_tree(holder, [("at", "At", 150), ("kind", "Kind", 90),
                                     ("actor", "By", 110),
                                     ("detail", "Detail", 560)], height=20)
        for e in data.list_events(self.aid):
            tree.insert("", "end", values=(e.at, e.kind, e.actor or "—",
                                           e.detail))

    # ── actions ─────────────────────────────────────────────────
    def _notify(self) -> None:
        self.refresh()
        self.on_change()

    def _set_ref_status(self) -> None:
        ok, _ = act.attempt(self.win, "Reference", data.set_reference_status,
                            self.aid, self.ref_cb.get())
        if ok:
            self._notify()

    def _chase(self, a: Applicant) -> None:
        applicant_email.chase_referee(self.win, a.applicant_id,
                                      on_done=self._notify)

    def _selected_doc(self) -> data.Document | None:
        sel = self.doc_tree.selection()
        if not sel:
            return None
        return self._docs.get(int(sel[0]))

    def _add_doc(self, force_type: str | None = None) -> None:
        path = filedialog.askopenfilename(parent=self.win,
                                           title="Choose a document")
        if not path:
            return
        if force_type:
            doc_type, label = force_type, None
        else:
            doc_type = AskChoiceDialog(
                self.win, "Document type", "Type:",
                list(DOCUMENT_TYPES)).result
            if doc_type is None:
                return
            label = None
        ok, _ = act.attempt(self.win, "Add document", data.add_document,
                            self.aid, path, doc_type=doc_type, label=label)
        if ok:
            self._notify()

    def _open_doc(self) -> None:
        d = self._selected_doc()
        if d is None:
            messagebox.showinfo("Open", "Select a document first.")
            return
        _open_path(d.path)

    def _remove_doc(self) -> None:
        d = self._selected_doc()
        if d is None:
            messagebox.showinfo("Remove", "Select a document first.")
            return
        if not messagebox.askyesno("Remove document",
                                     f"Remove '{d.label or d.doc_type}'?"):
            return
        ok, _ = act.attempt(self.win, "Remove document",
                            data.remove_document, d.id)
        if ok:
            self._notify()

    def _add_note(self) -> None:
        body = self.note_body.get().strip()
        if not body:
            return
        ok, _ = act.attempt(self.win, "Add note", data.add_note, self.aid,
                            body,
                            author=self.note_author.get().strip() or None)
        if not ok:
            return
        self.note_body.delete(0, "end")
        self._notify()

    def _edit_score(self) -> None:
        ScorecardDialog(self.win, self.aid, on_save=self._notify)

    # ── documents: preview + bulk upload (items 40, 41) ─────────

    def _document_preview(self) -> None:
        d = self._selected_doc()
        if d is None:
            return
        ext = os.path.splitext(d.path)[1].lower()
        if ext in (".png", ".gif", ".pgm", ".ppm"):
            try:
                img = tk.PhotoImage(file=d.path)
                if img.width() > 160:
                    img = img.subsample(max(1, img.width() // 160))
                self._preview_img = img
                self.doc_preview.configure(image=img, text="")
                return
            except Exception:  # noqa: BLE001 — fall back to a text label
                pass
        self._preview_img = None
        self.doc_preview.configure(
            image="", text=f"{d.doc_type}\n{ext or 'file'}\n(no preview)")

    def _bulk_upload_docs(self) -> None:
        paths = filedialog.askopenfilenames(
            parent=self.win, title="Choose one or more documents")
        if not paths:
            return
        doc_type = AskChoiceDialog(self.win, "Document type",
                                    "Type for all:",
                                    list(DOCUMENT_TYPES)).result
        if doc_type is None:
            return
        added, failures = 0, []
        for p in paths:
            try:
                data.add_document(self.aid, p, doc_type=doc_type)
                added += 1
            except Exception as e:  # noqa: BLE001
                failures.append(f"{os.path.basename(p)}: {e}")
        self._notify()
        msg = f"Added {added} document(s)."
        if failures:
            msg += "\n\nFailed:\n" + "\n".join(failures)
        messagebox.showinfo("Add several", msg)

    # ── email / offer actions (items 36, 37, 39, 45) ────────────

    def _send_custom_email(self) -> None:
        applicant_email.custom_email(self.win, self.aid, on_sent=self._notify)

    def _offer_expiry_reminder(self) -> None:
        a = self._applicant()
        if a is None:
            return
        if not a.offer_type or a.offer_type == "Not Offered":
            messagebox.showinfo("Offer status", "No offer has been made.")
            return
        if not a.offer_expiry:
            if messagebox.askyesno(
                    "Offer status",
                    "This offer has no expiry date. Set one now?"):
                new = _prompt(self.win, "Offer expiry",
                              "Expiry date (YYYY-MM-DD):",
                              (_dt.date.today()
                               + _dt.timedelta(days=14)).isoformat())
                if new:
                    ok, _ = act.attempt(self.win, "Offer expiry",
                                        data.set_offer_expiry, self.aid, new)
                    if ok:
                        self._notify()
            return
        exp = _parse_date(a.offer_expiry)
        days = (exp - _dt.date.today()).days if exp else None
        state = ("EXPIRED" if days is not None and days < 0
                 else f"{days} day(s) remaining" if days is not None
                 else "unknown")
        if messagebox.askyesno(
                "Offer status",
                f"Offer ({a.offer_type}) expires {a.offer_expiry} — {state}."
                f"\n\nE-mail a reminder to {a.email or 'the applicant'} now?"):
            if a.status == "Offer Made":
                applicant_email.expiry_warning(self.win, self.aid,
                                               on_sent=self._notify)
            else:
                self._send_custom_email()

    def _print_offer_letter(self) -> None:
        a = self._applicant()
        if a is None or not a.offer_type:
            messagebox.showinfo("Print offer letter",
                                  "No offer has been made yet.")
            return
        try:
            ApplicantsTab._send_to_printer(reports.render_offer_letter(self.aid))
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Print offer letter",
                                  f"Could not print:\n{e}")
            return
        messagebox.showinfo("Print offer letter",
                              "Offer letter sent to the default printer.")

    def _quick_offer(self) -> None:
        a = self._applicant()
        if a is None:
            return
        conditions = "Achieve at least grade 6 in your chosen subjects."
        if not messagebox.askyesno(
                "Quick standard offer",
                f"Make a standard {DEFAULT_OFFER_TYPE} offer to "
                f"{a.full_name}?\n\nConditions: {conditions}"):
            return
        if act.make_offer(self.win, self.aid, offer_type=DEFAULT_OFFER_TYPE,
                          conditions=conditions,
                          decided_by=act.username()) is not None:
            self._notify()

    # ── logs / comparisons / references (items 38, 43, 44) ──────

    def _communication_log(self) -> None:
        """Show the Communications page (outbox delivery of every
        admissions e-mail), alongside notes and events in the timeline."""
        self.nb.select(self._frames["Communications"])

    def _score_comparison(self) -> None:
        mine = data.get_interview_score(self.aid)
        if mine is None or mine.average is None:
            messagebox.showinfo("Score vs cohort",
                                  "This applicant has no interview score yet.")
            return
        averages = []
        for a in data.list_applicants():
            s = data.get_interview_score(a.applicant_id)
            if s is not None and s.average is not None:
                averages.append(s.average)
        cohort = round(sum(averages) / len(averages), 1) if averages else 0
        rank = sum(1 for v in averages if v > mine.average) + 1
        delta = round(mine.average - cohort, 1)
        messagebox.showinfo(
            "Score vs cohort",
            f"Applicant average : {mine.average}\n"
            f"Cohort average    : {cohort}  (n={len(averages)})\n"
            f"Difference        : {delta:+}\n"
            f"Rank              : {rank} of {len(averages)}")

    def _reference_chase_all(self) -> None:
        applicant_email.chase_all(self.win, on_done=self._notify)


class ApplicantDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Applicant | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = make_toplevel(parent)
        self.win.title("Edit Applicant" if existing else "New Applicant")
        grab_when_viewable(self.win)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        ttk.Label(form, text="First name:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.first_e = ttk.Entry(form, width=22)
        if self.existing:
            self.first_e.insert(0, self.existing.first_name)
        self.first_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Last name:").grid(row=r, column=2,
                                                   sticky="e", pady=4)
        self.last_e = ttk.Entry(form, width=22)
        if self.existing:
            self.last_e.insert(0, self.existing.last_name)
        self.last_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="DOB:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.dob_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.dob:
            self.dob_e.insert(0, self.existing.dob)
        self.dob_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Email:").grid(row=r, column=2,
                                               sticky="e", pady=4)
        self.email_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.email:
            self.email_e.insert(0, self.existing.email)
        self.email_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Phone:").grid(row=r, column=0,
                                               sticky="e", pady=4)
        self.phone_e = ttk.Entry(form, width=18)
        if self.existing and self.existing.phone:
            self.phone_e.insert(0, self.existing.phone)
        self.phone_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Address:").grid(row=r, column=2,
                                                 sticky="e", pady=4)
        self.addr_e = ttk.Entry(form, width=40)
        if self.existing and self.existing.address:
            self.addr_e.insert(0, self.existing.address)
        self.addr_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Previous school:").grid(row=r, column=0,
                                                          sticky="e", pady=4)
        self.prev_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.previous_school:
            self.prev_e.insert(0, self.existing.previous_school)
        self.prev_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Predicted GCSEs:").grid(row=r, column=2,
                                                          sticky="e", pady=4)
        self.gcse_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.predicted_gcses:
            self.gcse_e.insert(0, self.existing.predicted_gcses)
        self.gcse_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        opts = _subject_options()
        # Chip-style subject editor (item 13): add/remove, capped at 3.
        ttk.Label(form, text="Subjects (max 3):").grid(
            row=r, column=0, sticky="ne", pady=4)
        self.subj_list = tk.Listbox(form, height=3, width=30,
                                     exportselection=False)
        self.subj_list.grid(row=r, column=1, sticky="w", padx=6)
        self._subjects: list[str] = (list(self.existing.subjects)
                                     if self.existing else [])
        for s in self._subjects:
            self.subj_list.insert("end", s)
        picker = ttk.Frame(form)
        picker.grid(row=r, column=2, columnspan=2, sticky="w", padx=6)
        self.subj_pick = ttk.Combobox(picker, values=tuple(opts), width=26)
        self.subj_pick.grid(row=0, column=0, columnspan=2, pady=2)
        self.subj_pick.bind("<Return>", lambda _e: self._add_subject())
        ttk.Button(picker, text="Add", width=9,
                    command=self._add_subject).grid(row=1, column=0, pady=2)
        ttk.Button(picker, text="Remove", width=9,
                    command=self._remove_subject).grid(row=1, column=1,
                                                        pady=2)

        r += 1
        ttk.Label(form, text="Reference name:").grid(row=r, column=0,
                                                        sticky="e", pady=4)
        self.refname_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.reference_name:
            self.refname_e.insert(0, self.existing.reference_name)
        self.refname_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Reference contact:").grid(row=r, column=2,
                                                            sticky="e", pady=4)
        self.refcontact_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.reference_contact:
            self.refcontact_e.insert(0, self.existing.reference_contact)
        self.refcontact_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Source:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.source_cb = ttk.Combobox(form, values=SOURCES,
                                         state="readonly", width=18)
        self.source_cb.set(self.existing.application_source
                              if self.existing else DEFAULT_SOURCE)
        self.source_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Submitted:").grid(row=r, column=2,
                                                   sticky="e", pady=4)
        self.sub_e = ttk.Entry(form, width=14)
        self.sub_e.insert(0, (self.existing.submitted_at
                                if self.existing else _today()))
        self.sub_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        # New applications start in an initial status; an edit may move
        # only to the statuses the workflow allows next.
        if self.existing:
            statuses = (self.existing.status,) + tuple(
                st for st in data.allowed_statuses(self.existing.applicant_id)
                if st != self.existing.status)
        else:
            statuses = INITIAL_STATUSES
        self.status_cb = ttk.Combobox(form, values=statuses,
                                      state="readonly", width=22)
        self.status_cb.set(self.existing.status
                           if self.existing else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Intake year:").grid(row=r, column=2,
                                                  sticky="e", pady=4)
        self.intake_e = ttk.Entry(form, width=10)
        self.intake_e.insert(0, (self.existing.intake_year or "")
                             if self.existing else data.default_intake_year())
        self.intake_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=70, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        # Inline contact-field validation feedback (item 19).
        r += 1
        self.fb_lbl = ttk.Label(form, text="", foreground="#b00000")
        self.fb_lbl.grid(row=r, column=0, columnspan=4, sticky="w", padx=6)
        for w in (self.email_e, self.phone_e, self.dob_e):
            w.bind("<KeyRelease>", lambda _e: self._revalidate())
            w.bind("<FocusOut>", lambda _e: self._revalidate())

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=4, pady=(12, 0))
        save = ttk.Button(bar, text="Save", command=self._save)
        save.pack(side="left")
        archived = bool(self.existing and self.existing.is_archived)
        act.gate(save, act.can_admissions() and not archived)
        ttk.Button(bar, text="Cancel",
                   command=self.win.destroy).pack(side="left", padx=8)
        if archived:
            ttk.Label(bar, foreground="#b00000", text=(
                "Archived — restore it before changing it.")).pack(
                side="left", padx=8)
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

    def _add_subject(self) -> None:
        s = self.subj_pick.get().strip()
        if not s or s in self._subjects:
            return
        if len(self._subjects) >= 3:
            messagebox.showinfo("Subjects", "Maximum of 3 subjects.")
            return
        self._subjects.append(s)
        self.subj_list.insert("end", s)
        self.subj_pick.set("")

    def _remove_subject(self) -> None:
        sel = self.subj_list.curselection()
        if not sel:
            return
        idx = sel[0]
        self.subj_list.delete(idx)
        del self._subjects[idx]

    def _revalidate(self) -> None:
        problems: list[str] = []
        for getter, validator, args in (
                (self.email_e, data._validate_email, ()),
                (self.phone_e, data._validate_phone, ()),
                (self.dob_e, data._validate_date, ("Date of birth",))):
            try:
                validator(getter.get().strip(), *args)
            except ValidationError as e:
                problems.append(str(e))
        if problems:
            self.fb_lbl.configure(text="⚠ " + " · ".join(problems),
                                   foreground="#b00000")
        else:
            self.fb_lbl.configure(text="✓ contact fields look valid",
                                   foreground="#207020")

    def _collect(self) -> dict:
        return {
            "first_name":         self.first_e.get().strip(),
            "last_name":          self.last_e.get().strip(),
            "dob":                self.dob_e.get().strip(),
            "email":              self.email_e.get().strip(),
            "phone":              self.phone_e.get().strip(),
            "address":            self.addr_e.get().strip(),
            "previous_school":    self.prev_e.get().strip(),
            "predicted_gcses":    self.gcse_e.get().strip(),
            "subject_1":          (self._subjects[0]
                                   if len(self._subjects) > 0 else None),
            "subject_2":          (self._subjects[1]
                                   if len(self._subjects) > 1 else None),
            "subject_3":          (self._subjects[2]
                                   if len(self._subjects) > 2 else None),
            "reference_name":     self.refname_e.get().strip(),
            "reference_contact":  self.refcontact_e.get().strip(),
            "application_source": self.source_cb.get().strip(),
            "submitted_at":       self.sub_e.get().strip(),
            "status":             self.status_cb.get().strip(),
            "notes":              self.notes_t.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        payload = self._collect()
        # Required-field check: list EVERY missing field at once.
        missing = data.missing_required(payload)
        if missing:
            messagebox.showerror(
                "Missing required fields",
                "Please complete the following before saving:\n\n  • "
                + "\n  • ".join(missing), parent=self.win)
            return
        intake = self.intake_e.get().strip()
        if self.existing:
            # Duplicate warning on edit (the domain checks new ones).
            dups = [d for d in data.find_duplicates(
                email=payload["email"] or None,
                first_name=payload["first_name"],
                last_name=payload["last_name"],
                dob=payload["dob"] or None,
                exclude_id=self.existing.applicant_id) if not d.is_archived]
            if dups and not self._confirm_duplicates(dups):
                return
            ok, _ = act.attempt(self.win, "Save failed",
                                data.update_applicant,
                                self.existing.applicant_id, payload)
            if not ok:
                return
            if intake != (self.existing.intake_year or ""):
                from education_system.systems.sixth_form.domain.admissions import (
                    applicant_details,
                )
                ok, _ = act.attempt(self.win, "Intake year",
                                    applicant_details.update_profile,
                                    self.existing.applicant_id,
                                    intake_year=intake or None)
                if not ok:
                    self.on_save()
                    return
        else:
            payload["intake_year"] = intake or None
            try:
                data.create_applicant(payload)
            except data.PossibleDuplicate as e:
                if not self._confirm_duplicates(e.matches):
                    return
                ok, _ = act.attempt(self.win, "Save failed",
                                    data.create_applicant, payload,
                                    allow_duplicate=True)
                if not ok:
                    return
            except Exception as e:  # noqa: BLE001 — every refusal is shown
                act.show_error(self.win, "Save failed", e)
                return
        self.win.destroy()
        self.on_save()

    def _confirm_duplicates(self, matches: list[Applicant]) -> bool:
        lines = "\n".join(
            f"  {d.applicant_id} — {d.full_name}, DOB {d.dob or '—'} "
            f"({d.email or 'no email'}) — {d.status}" for d in matches[:10])
        return messagebox.askyesno(
            "Possible duplicate",
            f"{len(matches)} existing applicant(s) look like the same "
            f"person:\n\n{lines}\n\nOpen the existing record instead, or "
            "save this as a separate application anyway?\n\n"
            "Yes = save anyway · No = go back", parent=self.win)


# Sibling names used only at call time; imported last so any import order works.
from .dialogs_actions import (  # noqa: E402
    AskChoiceDialog,
    ScorecardDialog,
    StatusDialog,
    TextViewerDialog,
)
from .tab_applicants import ApplicantsTab  # noqa: E402
