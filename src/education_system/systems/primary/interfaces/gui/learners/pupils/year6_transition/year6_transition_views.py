"""Year 6 Transition screen (Pupil Management → Year 6 Transition).

One page with six tabs over ``domain/learners/pupils/year6_transition``:
Cohort, Destinations & Offers, Transition Reports, Consent & Handover,
Visits and Safeguarding Files. Every date, pupil, staff member and fixed
list is a kit picker. The Safeguarding Files tab is for designated
safeguarding leads only; approving the handover is for an administrator or
a DSL (``domain/access.py``).
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.primary.domain import access
from education_system.systems.primary.domain.learners.pupils import year6_transition as y6
from education_system.systems.primary.domain.learners.pupils.pupils import ValidationError
from education_system.systems.primary.interfaces.gui import kit

logger = logging.getLogger(__name__)

TITLE = "Year 6 Transition"


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            messagebox.showerror(TITLE, str(e), parent=getattr(host, "root", None))
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            messagebox.showerror(TITLE, f"An unexpected error occurred:\n\n{e}\n\n"
                                        "See logs for details.",
                                 parent=getattr(host, "root", None))
    return wrapper


@_safe_view
def open_year6_transition(host) -> None:
    logger.debug("GUI: open_year6_transition")
    kit.show_page(host, TITLE, lambda parent: _Year6Page(parent, host))


def _principal(host) -> access.Principal:
    return getattr(host, "principal", None) or access.current()


def _yes(flag: bool) -> str:
    return "Yes" if flag else "—"


class _Year6Page:
    """The page: year picker + summary, then the six tabs."""

    def __init__(self, page: ttk.Frame, host: Any) -> None:
        self.page, self.host = page, host
        self.principal = _principal(host)
        self.actor = self.principal.username or None
        kit.page_heading(
            page, TITLE,
            "Destinations, offers, consent, transition reports, visits and the "
            "handover to secondary for the Year 6 cohort. The platform's Secondary "
            "School System sees each pupil in its queue as the stages are recorded.")
        top = ttk.Frame(page)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="Academic year:").pack(side="left")
        self.year = tk.StringVar(value=y6.current_academic_year())
        kit.AcademicYearPicker(top, self.year, on_change=lambda _v: self.refresh()
                               ).pack(side="left", padx=(4, 12))
        ttk.Button(top, text="Refresh from secondary",
                   command=self._refresh_secondary).pack(side="left")
        self.summary = tk.StringVar()
        ttk.Label(page, textvariable=self.summary, foreground="#444").pack(anchor="w")
        self.timetable = tk.StringVar()
        ttk.Label(page, textvariable=self.timetable, foreground="#666").pack(anchor="w",
                                                                             pady=(0, 6))
        nb = ttk.Notebook(page)
        nb.pack(fill="both", expand=True)
        self.trees: dict[str, ttk.Treeview] = {}
        self._cohort_tab(self._tab(nb, "Cohort"))
        self._destinations_tab(self._tab(nb, "Destinations & Offers"))
        self._reports_tab(self._tab(nb, "Transition Reports"))
        self._consent_tab(self._tab(nb, "Consent & Handover"))
        self._visits_tab(self._tab(nb, "Visits"))
        self._safeguarding_tab(self._tab(nb, "Safeguarding Files"))
        self.refresh()

    # ── helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _tab(nb: ttk.Notebook, title: str) -> ttk.Frame:
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text=title)
        return frame

    @staticmethod
    def _bar(parent: ttk.Frame, buttons: list[tuple[str, Callable[[], None]]]) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 6))
        for text, cmd in buttons:
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 6))

    def _y(self) -> str:
        return y6.normalise_year(self.year.get())

    def _act(self, fn: Callable[[], Any], done: str | None = None) -> bool:
        try:
            fn()
        except ValidationError as e:
            messagebox.showerror(TITLE, str(e), parent=self.page.winfo_toplevel())
            return False
        except Exception as e:  # noqa: BLE001
            logger.exception("Year 6 transition action failed")
            messagebox.showerror(TITLE, f"Could not complete that:\n\n{e}",
                                 parent=self.page.winfo_toplevel())
            return False
        self.refresh()
        if done:
            self._status(done)
        return True

    def _status(self, text: str) -> None:
        var = getattr(self.host, "status_var", None)
        if var is not None:
            try:
                var.set(text)
            except tk.TclError:
                pass

    def _selected(self, key: str) -> str | None:
        tree = self.trees[key]
        sel = tree.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a row first.", parent=self.page.winfo_toplevel())
            return None
        return sel[0]

    def _cohort_choices(self, exclude: str | None = None) -> list[tuple[str, str]]:
        return [(p.pupil_id, f"{p.last_name}, {p.first_name} ({p.pupil_id})"
                 + (f" · {p.class_name}" if p.class_name else ""))
                for p in y6.year6_pupils(self._y()) if p.pupil_id != exclude]

    def _form(self, title: str, fields: list, on_save: Callable[[dict], Any],
              note: str | None = None) -> None:
        def save(values: dict) -> None:
            on_save(values)
            self.refresh()
        kit.form_dialog(self.page, title, fields, save, note, errors=(ValidationError,))

    # ── refresh ─────────────────────────────────────────────────────

    def refresh(self) -> None:
        try:
            year = self._y()
        except ValidationError:
            return
        tt = y6.national_timetable(year)
        self.timetable.set(
            f"National timetable {year}: applications {tt.applications_open} – "
            f"{tt.application_deadline} · offer day {tt.offer_day} · reply by about "
            f"{tt.reply_by} · induction days from {tt.induction_from}")
        rows = y6.cohort(year)
        s = y6.cohort_summary(year)
        self.summary.set(
            f"{s['pupils']} pupils · platform secondary {s['platform']} · other schools "
            f"{s['external']} · no destination {s['no_destination']} · reports "
            f"{s['reports_written']} · consent recorded {s['consent_recorded']} · "
            f"enhanced transition {s['enhanced']}")
        for t in self.trees.values():
            t.delete(*t.get_children())
        sg_ok = access.can_manage_year6_safeguarding_files(self.principal)
        sg_rows = {r.pupil_id: r for r in y6.list_safeguarding_transfers(year)} if sg_ok else {}
        for row in rows:
            p, r = row.pupil, row.record
            pid = p.pupil_id
            name = f"{p.last_name}, {p.first_name}"
            status = y6.APPLICATION_STATUSES.get(r.application_status, r.application_status)
            sec = y6.SECONDARY_STATUS_LABELS.get(r.secondary_status or "", "")
            tag = ("bad" if r.secondary_status == "rejected" else
                   "good" if row.checklist_done == row.checklist_total else
                   "warn" if not r.destination_type else "")
            self.trees["cohort"].insert("", "end", iid=pid, tags=(tag,) if tag else (), values=(
                name, p.class_name or "", r.destination_label or "—", status,
                _yes(row.report_written), row.visits_attended,
                f"{row.checklist_done}/{row.checklist_total}", sec))
            late = " (late)" if y6.is_late_application(r) else ""
            outcome = (f"accepted {r.accepted_on}" if r.accepted_on else
                       f"declined {r.declined_on}" if r.declined_on else "")
            self.trees["dest"].insert("", "end", iid=pid, values=(
                name, y6.DESTINATION_TYPES.get(r.destination_type, "—"),
                r.destination_school or "", status, (r.applied_on or "") + late,
                r.offered_on or "", outcome, sec))
            rep = y6.get_report(pid, year)
            self.trees["reports"].insert("", "end", iid=pid, values=(
                name, _yes(rep is not None), rep.written_by if rep else "",
                (rep.written_on or "") if rep else "",
                _yes(bool(rep and rep.enhanced_transition))))
            shared = ", ".join(sorted(r.consented_fields)) or "none"
            self.trees["consent"].insert("", "end", iid=pid, values=(
                name, _yes(r.consent_recorded),
                shared if r.consent_recorded else "", r.consent_given_by or "",
                r.handover_approved_on or ("n/a" if r.destination_type == "external" else ""),
                sec))
            if sg_ok:
                sg = sg_rows.get(pid)
                self.trees["sg"].insert("", "end", iid=pid, values=(
                    name, ("No file" if sg and not sg.has_file else "File" if sg else
                           "Not recorded"),
                    (sg.sent_on or "") if sg else "", (sg.sent_to_name or "") if sg else "",
                    (sg.sent_to_school or "") if sg else "", (sg.method or "") if sg else "",
                    (sg.receipt_confirmed_on or "") if sg else ""))
        names = {row.pupil.pupil_id: f"{row.pupil.last_name}, {row.pupil.first_name}"
                 for row in rows}
        for v in y6.list_visits(year):
            self.trees["visits"].insert("", "end", iid=str(v.visit_id), values=(
                names.get(v.pupil_id, v.pupil_id), v.visit_date, v.visit_type,
                v.school_name or "", _yes(v.attended), v.notes or ""))

    def _refresh_secondary(self) -> None:
        holder: dict[str, int] = {}
        if self._act(lambda: holder.update(n=y6.refresh_secondary_status(self._y()))):
            self._status(f"Secondary status refreshed ({holder.get('n', 0)} changed)")

    # ── Cohort ──────────────────────────────────────────────────────

    def _cohort_tab(self, tab: ttk.Frame) -> None:
        self._bar(tab, [("Checklist & secondary status…", self._show_checklist),
                        ("Notes…", self._edit_notes)])
        self.trees["cohort"] = kit.tree(tab, (
            ("name", "Pupil", 180), ("class", "Class", 60), ("dest", "Destination", 200),
            ("status", "Admissions", 120), ("report", "Report", 60),
            ("visits", "Visits", 50), ("check", "Checklist", 70),
            ("sec", "Secondary", 220)), stretch=("dest", "sec"))

    def _show_checklist(self) -> None:
        pid = self._selected("cohort")
        if not pid:
            return
        year = self._y()
        win, frm = kit.dialog(self.page, f"Checklist — {pid}", size="640x560")
        ttk.Label(frm, text="Transition checklist", font=("", 11, "bold")).pack(anchor="w")
        for item in y6.checklist(pid, year):
            mark = "✔" if item.done else "○"
            detail = f"  ({item.detail})" if item.detail else ""
            ttk.Label(frm, text=f"{mark} {item.label}{detail}",
                      foreground="#1a7f37" if item.done else "#444").pack(anchor="w")
        status = None
        try:
            status = y6.platform_status(pid, year)
        except Exception:  # noqa: BLE001
            logger.exception("platform status failed for %s", pid)
        if status is None:
            ttk.Label(frm, text="\nNo platform transition (external destination, or not "
                                "started).", foreground="#666").pack(anchor="w")
        else:
            ttk.Label(frm, text=f"\nSecondary: {status['label']}",
                      font=("", 11, "bold")).pack(anchor="w")
            if status.get("reason"):
                ttk.Label(frm, text=f"Reason: {status['reason']}", foreground="#a33",
                          wraplength=580).pack(anchor="w")
            ttk.Label(frm, text="Platform checklist (tick the primary school's items):"
                      ).pack(anchor="w", pady=(6, 0))
            for item in status["checklist"]:
                var = tk.BooleanVar(value=bool(item.get("done")))
                ours = item.get("owner") in y6.PRIMARY_CHECKLIST_OWNERS
                cb = ttk.Checkbutton(frm, text=f"{item.get('label')} ({item.get('owner')})",
                                     variable=var)
                cb.pack(anchor="w")
                if not ours:
                    cb.state(["disabled"])
                else:
                    cb.configure(command=lambda k=item.get("key"), v=var: self._act(
                        lambda: y6.tick_platform_item(pid, year, k, done=v.get(),
                                                      actor=self.actor)))
            ttk.Label(frm, text="History:").pack(anchor="w", pady=(6, 0))
            t = kit.tree(frm, (("at", "When", 140), ("step", "Step", 130),
                               ("actor", "By", 90), ("note", "Note", 220)),
                         height=6, stretch=("note",))
            for e in status["events"]:
                t.insert("", "end", values=(e["at"] or "", e["step"] or "", e["actor"] or "",
                                            e["note"] or ""))
        ttk.Button(frm, text="Close", command=win.destroy).pack(anchor="e", pady=(8, 0))

    def _edit_notes(self) -> None:
        pid = self._selected("cohort")
        if not pid:
            return
        rec = y6.get_record(pid, self._y())
        self._form(f"Notes — {pid}", [("notes", "Notes", rec.notes if rec else "", "text")],
                   lambda v: y6.update_notes(pid, self._y(), v["notes"]))

    # ── Destinations & Offers ───────────────────────────────────────

    def _destinations_tab(self, tab: ttk.Frame) -> None:
        self._bar(tab, [("Set destination…", self._set_destination),
                        ("Record application…", self._record_application),
                        ("Record offer…", self._record_offer),
                        ("Record acceptance…", self._record_acceptance),
                        ("Record decline…", self._record_decline),
                        ("Complete move to other school…", self._external_move)])
        self.trees["dest"] = kit.tree(tab, (
            ("name", "Pupil", 180), ("type", "Destination type", 190),
            ("school", "School", 180), ("status", "Admissions", 110),
            ("applied", "Applied", 110), ("offered", "Offered", 90),
            ("outcome", "Outcome", 130), ("sec", "Secondary", 200)),
            stretch=("school", "sec"))

    def _known_schools(self) -> list[str]:
        names = {r.record.destination_school for r in y6.cohort(self._y())
                 if r.record.destination_type == y6.DESTINATION_EXTERNAL}
        return sorted(n for n in names if n)

    def _set_destination(self) -> None:
        pid = self._selected("dest")
        if not pid:
            return
        rec = y6.get_record(pid, self._y())
        self._form(
            f"Destination — {pid}",
            [("type", "Going to", rec.destination_type if rec else y6.DESTINATION_PLATFORM,
              list(y6.DESTINATION_TYPES.items())),
             ("school", "School name (other school)",
              rec.destination_school if rec and rec.destination_type == "external" else "",
              ("edit", self._known_schools()))],
            lambda v: y6.set_destination(pid, self._y(), v["type"], v["school"],
                                         actor=self.actor),
            note="Choosing the platform's Secondary School System puts the pupil in its "
                 "queue now. Changing away from it cancels that transition.")

    def _record_application(self) -> None:
        pid = self._selected("dest")
        if not pid:
            return
        tt = y6.national_timetable(self._y())
        self._form(f"Application — {pid}", [("on", "Applied on", "", "date")],
                   lambda v: y6.record_application(pid, self._y(), v["on"], actor=self.actor),
                   note=f"The national closing date is {tt.application_deadline}; a later "
                        f"date is recorded as a late application.")

    def _record_offer(self) -> None:
        pid = self._selected("dest")
        if not pid:
            return
        tt = y6.national_timetable(self._y())
        rec = y6.get_record(pid, self._y())
        self._form(f"Offer — {pid}",
                   [("on", "Offered on", tt.offer_day, "date"),
                    ("school", "Offered school", rec.destination_school if rec else "",
                     ("edit", self._known_schools()))],
                   lambda v: y6.record_offer(pid, self._y(), v["on"], v["school"],
                                             actor=self.actor),
                   note="For the platform secondary, this creates the pupil's Year 7 "
                        "applicant there with the information the parent consented to.")

    def _record_acceptance(self) -> None:
        pid = self._selected("dest")
        if not pid:
            return
        self._form(f"Acceptance — {pid}", [("on", "Accepted on", "", "date")],
                   lambda v: y6.record_acceptance(pid, self._y(), v["on"], actor=self.actor))

    def _record_decline(self) -> None:
        pid = self._selected("dest")
        if not pid:
            return
        self._form(f"Decline — {pid}", [("on", "Declined on", "", "date"),
                                        ("reason", "Reason", "", "text")],
                   lambda v: y6.record_decline(pid, self._y(), v["on"], v["reason"],
                                               actor=self.actor))

    def _external_move(self) -> None:
        pid = self._selected("dest")
        if not pid:
            return
        self._form(f"Move to other school — {pid}",
                   [("on", "Leaving date", "", "date"), ("notes", "Notes", "", "text")],
                   lambda v: y6.complete_external_move(pid, self._y(), v["on"], v["notes"]),
                   note="Writes the leaver record with the destination school and takes "
                        "the pupil off roll. For the platform secondary use Pupil "
                        "Directory → Move to Secondary instead.")

    # ── Transition Reports ──────────────────────────────────────────

    def _reports_tab(self, tab: ttk.Frame) -> None:
        self._bar(tab, [("Write / edit report…", self._edit_report),
                        ("View report", self._view_report)])
        self.trees["reports"] = kit.tree(tab, (
            ("name", "Pupil", 200), ("written", "Written", 70), ("by", "By", 160),
            ("on", "On", 100), ("enh", "Enhanced transition", 130)), stretch=("by",))

    def _edit_report(self) -> None:
        pid = self._selected("reports")
        if not pid:
            return
        rep = y6.get_report(pid, self._y()) or y6.TransitionReport(pid, self._y())
        others = self._cohort_choices(exclude=pid)
        self._form(
            f"Transition report — {pid}",
            [("strengths", "Strengths", rep.strengths, "text"),
             ("interests", "Interests", rep.interests, "text"),
             ("learning_style", "How they learn best", rep.learning_style, "text"),
             ("worries", "Worries about secondary", rep.worries, "text"),
             ("friendships", "Friendships", rep.friendships, ("multi", others)),
             ("keep_apart", "Keep apart from", rep.keep_apart, ("multi", others)),
             ("all_about_me", "All about me (pupil's words)", rep.all_about_me, "text"),
             ("teacher_comments", "Teacher comments", rep.teacher_comments, "text"),
             ("enhanced_transition", "Enhanced transition needed", rep.enhanced_transition,
              "check"),
             ("enhanced_reason", "Why enhanced", rep.enhanced_reason, "text"),
             ("written_by", "Written by", rep.written_by or "", "staff_name"),
             ("written_on", "Written on", rep.written_on or "", "date")],
            lambda v: y6.save_report(pid, self._y(), v),
            note="Shared with the secondary school as routine information. Put SEND, "
                 "medical or safeguarding detail in their own records, not here.")

    def _view_report(self) -> None:
        pid = self._selected("reports")
        if not pid:
            return
        payload = y6.report_payload(pid, self._y())
        if payload is None:
            messagebox.showinfo(TITLE, "No report written yet.",
                                parent=self.page.winfo_toplevel())
            return
        win, frm = kit.dialog(self.page, f"Transition report — {pid}", size="620x520")
        text = tk.Text(frm, wrap="word")
        text.pack(fill="both", expand=True)
        for key, value in payload.items():
            if isinstance(value, list):
                value = ", ".join(value) or "—"
            elif isinstance(value, bool):
                value = "Yes" if value else "No"
            text.insert("end", f"{key.replace('_', ' ').capitalize()}: {value or '—'}\n\n")
        text.configure(state="disabled")
        ttk.Button(frm, text="Close", command=win.destroy).pack(anchor="e", pady=(6, 0))

    # ── Consent & Handover ──────────────────────────────────────────

    def _consent_tab(self, tab: ttk.Frame) -> None:
        self._bar(tab, [("Record consent…", self._record_consent),
                        ("Preview handover", self._preview),
                        ("Approve handover…", self._approve)])
        ttk.Label(tab, foreground="#666", wraplength=900, justify="left", text=(
            "The handover can be approved once, after the place is accepted: the "
            "platform workflow only moves forward, so later edits are not re-sent — "
            "pass them to the secondary school directly.")).pack(anchor="w", pady=(0, 6))
        self.trees["consent"] = kit.tree(tab, (
            ("name", "Pupil", 180), ("rec", "Consent recorded", 110),
            ("shared", "May share", 280), ("by", "Given by", 140),
            ("approved", "Handover approved", 120), ("sec", "Secondary", 200)),
            stretch=("shared", "sec"))

    def _guardian_names(self, pid: str) -> list[str]:
        try:
            from education_system.systems.primary.domain.learners.pupils import (
                cross_system_adapter,
            )
            from education_system.systems.primary.domain.learners.pupils import pupils
            pupil = pupils.get_pupil(pid)
            return [g["name"] for g in (cross_system_adapter._guardians(pupil) or [])
                    if g.get("name")] if pupil else []
        except Exception:  # noqa: BLE001
            logger.debug("guardian names failed", exc_info=True)
            return []

    def _record_consent(self) -> None:
        pid = self._selected("consent")
        if not pid:
            return
        rec = y6.get_record(pid, self._y()) or y6.Year6Record(pid, self._y())
        fields: list = [(k, y6.CONSENT_LABELS[k], rec.consent.get(k, False), "check")
                        for k in y6.CONSENT_FIELDS]
        fields += [("given_by", "Parent / carer", rec.consent_given_by or "",
                    ("edit", self._guardian_names(pid))),
                   ("given_on", "Date", rec.consent_on or "", "date"),
                   ("method", "How", rec.consent_method or y6.CONSENT_METHODS[0],
                    list(y6.CONSENT_METHODS))]
        self._form(
            f"Consent — {pid}", fields,
            lambda v: y6.set_consent(pid, self._y(), {k: bool(v[k]) for k in y6.CONSENT_FIELDS},
                                     given_by=v["given_by"], given_on=v["given_on"],
                                     method=v["method"]),
            note="Tick what the parent agrees may be shared. Unticked items are recorded "
                 "as refused and are withheld from the handover.")

    def _preview(self) -> None:
        pid = self._selected("consent")
        if not pid:
            return
        try:
            out = y6.preview_handover(pid, self._y())
        except ValidationError as e:
            messagebox.showerror(TITLE, str(e), parent=self.page.winfo_toplevel())
            return
        messagebox.showinfo(
            TITLE,
            "Would be shared: " + (", ".join(out["included"]) or "nothing") +
            "\n\nWithheld (no consent): " + (", ".join(out["withheld_no_consent"]) or "none") +
            ("\n\nMissing required: " + ", ".join(out["missing"]) if out["missing"] else ""),
            parent=self.page.winfo_toplevel())

    def _approve(self) -> None:
        pid = self._selected("consent")
        if not pid:
            return
        if not access.can_approve_year6_handover(self.principal):
            messagebox.showerror(TITLE, "Only an administrator or a designated "
                                        "safeguarding lead can approve the handover.",
                                 parent=self.page.winfo_toplevel())
            return
        if not messagebox.askyesno(
                TITLE, "Release this pupil's handover to the Secondary School System now? "
                       "It can only be approved once.", parent=self.page.winfo_toplevel()):
            return
        self._act(lambda: y6.approve_handover(pid, self._y(), actor=self.actor),
                  f"Handover approved for {pid}")

    # ── Visits ──────────────────────────────────────────────────────

    def _visits_tab(self, tab: ttk.Frame) -> None:
        self._bar(tab, [("Add visit…", self._add_visit),
                        ("Add visit for several pupils…", self._add_group_visit),
                        ("Edit…", self._edit_visit), ("Delete", self._delete_visit)])
        self.trees["visits"] = kit.tree(tab, (
            ("name", "Pupil", 180), ("date", "Date", 100), ("type", "Type", 190),
            ("school", "School", 180), ("att", "Attended", 70), ("notes", "Notes", 200)),
            stretch=("notes",))

    def _visit_fields(self, v: y6.Visit | None = None) -> list:
        return [("visit_date", "Date", v.visit_date if v else "", "date"),
                ("visit_type", "Type", v.visit_type if v else y6.VISIT_TYPES[1],
                 list(y6.VISIT_TYPES)),
                ("school_name", "School (blank = destination)", (v.school_name or "") if v
                 else "", ("edit", self._known_schools() + [y6.PLATFORM_DESTINATION_NAME])),
                ("attended", "Attended", v.attended if v else True, "check"),
                ("notes", "Notes", (v.notes or "") if v else "", "text")]

    def _add_visit(self) -> None:
        choices = self._cohort_choices()
        self._form("Add visit", [("pupil", "Pupil", "", choices)] + self._visit_fields(),
                   lambda v: y6.add_visit(v["pupil"], self._y(), v))

    def _add_group_visit(self) -> None:
        self._form("Add visit for several pupils",
                   [("pupils", "Pupils", [], ("multi", self._cohort_choices()))]
                   + self._visit_fields(),
                   lambda v: y6.add_group_visit(v["pupils"], self._y(), v))

    def _edit_visit(self) -> None:
        vid = self._selected("visits")
        if not vid:
            return
        visit = y6.get_visit(int(vid))
        if visit is None:
            return
        self._form("Edit visit", self._visit_fields(visit),
                   lambda v: y6.update_visit(int(vid), v))

    def _delete_visit(self) -> None:
        vid = self._selected("visits")
        if vid and messagebox.askyesno(TITLE, "Delete this visit?",
                                       parent=self.page.winfo_toplevel()):
            self._act(lambda: y6.delete_visit(int(vid)))

    # ── Safeguarding Files (DSL only) ───────────────────────────────

    def _safeguarding_tab(self, tab: ttk.Frame) -> None:
        if not access.can_manage_year6_safeguarding_files(self.principal):
            ttk.Label(tab, wraplength=800, justify="left", text=(
                "Safeguarding file transfers are recorded by the designated "
                "safeguarding lead. The Cohort checklist shows whether this step is "
                "done.")).pack(anchor="w")
            self.trees["sg"] = ttk.Treeview(tab)  # placeholder, never shown
            return
        ttk.Label(tab, foreground="#666", wraplength=900, justify="left", text=(
            "Record where each child-protection file went — DSL to DSL, by a secure "
            "route, within five school days of the pupil starting, with receipt "
            "confirmed. Only a reference crosses the platform; never the file.")
                  ).pack(anchor="w", pady=(0, 6))
        self._bar(tab, [("Record / edit transfer…", self._edit_sg)])
        self.trees["sg"] = kit.tree(tab, (
            ("name", "Pupil", 180), ("file", "File", 90), ("sent", "Sent on", 100),
            ("to", "To (DSL)", 150), ("school", "School", 170), ("method", "Method", 200),
            ("receipt", "Receipt confirmed", 120)), stretch=("method",))

    def _edit_sg(self) -> None:
        pid = self._selected("sg")
        if not pid:
            return
        sg = y6.get_safeguarding_transfer(pid, self._y())
        rec = y6.get_record(pid, self._y())
        self._form(
            f"Safeguarding file — {pid}",
            [("has_file", "There is a safeguarding file to transfer",
              sg.has_file if sg else True, "check"),
             ("sent_on", "Date sent", (sg.sent_on or "") if sg else "", "date"),
             ("sent_to_name", "Sent to (name)", (sg.sent_to_name or "") if sg else "", None),
             ("sent_to_role", "Their role", (sg.sent_to_role or "Designated Safeguarding Lead")
              if sg else "Designated Safeguarding Lead",
              ("edit", ["Designated Safeguarding Lead", "Deputy DSL", "Headteacher"])),
             ("sent_to_school", "School", (sg.sent_to_school or "") if sg else
              (rec.destination_school if rec else ""), ("edit", self._known_schools()
                                                        + [y6.PLATFORM_DESTINATION_NAME])),
             ("method", "Method", (sg.method or "") if sg else "",
              list(y6.SAFEGUARDING_METHODS)),
             ("receipt_confirmed_on", "Receipt confirmed on",
              (sg.receipt_confirmed_on or "") if sg else "", "date"),
             ("recorded_by", "Recorded by", (sg.recorded_by or "") if sg else
              (self.principal.username or ""), "staff_name"),
             ("notes", "Notes (no case detail)", (sg.notes or "") if sg else "", "text")],
            lambda v: y6.save_safeguarding_transfer(pid, self._y(), v))


__all__ = ["open_year6_transition"]
