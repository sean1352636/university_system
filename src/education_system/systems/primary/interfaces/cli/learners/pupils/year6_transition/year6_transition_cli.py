"""Terminal menu for Year 6 Transition (Pupil Management → Year 6 Transition).

The same functions as the GUI page: cohort and checklist, destinations and
the admissions round, transition reports, consent and handover, visits, and
(designated safeguarding leads only) safeguarding-file transfers. Pupils and
fixed lists are chosen by number; dates are YYYY-MM-DD.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Sequence

from education_system.systems.primary.domain import access
from education_system.systems.primary.domain.learners.pupils import year6_transition as y6
from education_system.systems.primary.domain.learners.pupils.pupils import ValidationError

logger = logging.getLogger(__name__)

LABEL = "Year 6 Transition"


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _choose(title: str, options: Sequence[tuple[str, str]], *,
            allow_blank: bool = False) -> str | None:
    """Pick one of ``(value, label)`` by number. ``None`` when cancelled."""
    if not options:
        print("  (nothing to choose from)")
        return None
    print(f"  {title}:")
    for i, (_v, label) in enumerate(options, start=1):
        print(f"   {i:>2}) {label}")
    hint = " (blank for none)" if allow_blank else " (blank to cancel)"
    raw = _prompt(f"  Choose{hint}: ")
    if not raw:
        return "" if allow_blank else None
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1][0]
    print("  Invalid choice.")
    return None


def _choose_many(title: str, options: Sequence[tuple[str, str]],
                 selected: Sequence[str] = ()) -> list[str]:
    print(f"  {title} (numbers separated by commas; blank keeps current):")
    for i, (v, label) in enumerate(options, start=1):
        mark = "*" if v in selected else " "
        print(f"   {i:>2}){mark}{label}")
    raw = _prompt("  Choose: ")
    if not raw:
        return list(selected)
    if raw == "-":
        return []
    out = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= len(options):
            out.append(options[int(part) - 1][0])
    return out


def _yes_no(msg: str, default: bool = False) -> bool:
    raw = _prompt(f"  {msg} [{'Y/n' if default else 'y/N'}]: ").lower()
    if not raw:
        return default
    return raw.startswith("y")


def _text(msg: str, current: str = "") -> str:
    shown = f" [{current}]" if current else ""
    return _prompt(f"  {msg}{shown}: ") or current


class _Session:
    def __init__(self) -> None:
        self.principal = access.current()
        self.actor = self.principal.username or None
        self.year = y6.current_academic_year()

    # ── shared ──────────────────────────────────────────────────────

    def pupils(self, exclude: str | None = None) -> list[tuple[str, str]]:
        return [(p.pupil_id, f"{p.last_name}, {p.first_name} ({p.pupil_id})"
                 + (f" · {p.class_name}" if p.class_name else ""))
                for p in y6.year6_pupils(self.year) if p.pupil_id != exclude]

    def pick_pupil(self) -> str | None:
        return _choose("Year 6 pupils", self.pupils())

    def set_year(self) -> None:
        raw = _prompt(f"  Academic year (e.g. 2026-27) [{self.year}]: ")
        if raw:
            self.year = y6.normalise_year(raw)

    # ── Cohort ──────────────────────────────────────────────────────

    def show_cohort(self) -> None:
        rows = y6.cohort(self.year)
        tt = y6.national_timetable(self.year)
        print(f"\n  Year 6 cohort {self.year}: applications close {tt.application_deadline}, "
              f"offer day {tt.offer_day}, reply by about {tt.reply_by}")
        if not rows:
            print("  (no Year 6 pupils)")
            return
        print(f"  {'Pupil':<26} {'Destination':<26} {'Admissions':<16} {'Rep':<4} "
              f"{'Chk':<6} Secondary")
        for r in rows:
            rec = r.record
            print(f"  {(r.pupil.last_name + ', ' + r.pupil.first_name)[:26]:<26} "
                  f"{(rec.destination_label or '-')[:26]:<26} "
                  f"{y6.APPLICATION_STATUSES.get(rec.application_status, '')[:16]:<16} "
                  f"{'yes' if r.report_written else '-':<4} "
                  f"{r.checklist_done}/{r.checklist_total:<4} "
                  f"{y6.SECONDARY_STATUS_LABELS.get(rec.secondary_status or '', '')}")

    def show_checklist(self) -> None:
        pid = self.pick_pupil()
        if not pid:
            return
        for item in y6.checklist(pid, self.year):
            detail = f" ({item.detail})" if item.detail else ""
            print(f"  [{'x' if item.done else ' '}] {item.label}{detail}")
        status = y6.platform_status(pid, self.year)
        if status is None:
            print("  No platform transition.")
            return
        print(f"\n  Secondary: {status['label']}")
        if status.get("reason"):
            print(f"  Reason: {status['reason']}")
        print("  Platform checklist:")
        for item in status["checklist"]:
            print(f"   [{'x' if item.get('done') else ' '}] {item.get('label')} "
                  f"({item.get('owner')})")
        print("  History:")
        for e in status["events"]:
            print(f"   {e['at'] or '':<20} {e['step'] or '':<18} {e['actor'] or '':<12} "
                  f"{e['note'] or ''}")
        ours = [(i["key"], i["label"]) for i in status["checklist"]
                if i.get("owner") in y6.PRIMARY_CHECKLIST_OWNERS]
        if ours and _yes_no("Tick or untick one of the primary school's items?"):
            key = _choose("Items", ours)
            if key:
                done = _yes_no("Mark as done?", True)
                y6.tick_platform_item(pid, self.year, key, done=done, actor=self.actor)
                print("  Updated.")

    def refresh_secondary(self) -> None:
        n = y6.refresh_secondary_status(self.year)
        print(f"  Secondary status refreshed ({n} changed).")

    def edit_notes(self) -> None:
        pid = self.pick_pupil()
        if not pid:
            return
        rec = y6.get_record(pid, self.year)
        y6.update_notes(pid, self.year, _text("Notes", (rec.notes or "") if rec else ""))
        print("  Saved.")

    # ── Destinations & Offers ───────────────────────────────────────

    def set_destination(self) -> None:
        pid = self.pick_pupil()
        if not pid:
            return
        kind = _choose("Going to", list(y6.DESTINATION_TYPES.items()))
        if not kind:
            return
        school = ""
        if kind == y6.DESTINATION_EXTERNAL:
            school = _text("School name")
        rec = y6.set_destination(pid, self.year, kind, school, actor=self.actor)
        print(f"  Destination: {rec.destination_label}.")

    def record_application(self) -> None:
        pid = self.pick_pupil()
        if pid:
            rec = y6.record_application(pid, self.year, _text("Applied on (YYYY-MM-DD)"),
                                        actor=self.actor)
            print("  Application recorded" + (" (late)." if y6.is_late_application(rec)
                                               else "."))

    def record_offer(self) -> None:
        pid = self.pick_pupil()
        if pid:
            tt = y6.national_timetable(self.year)
            on = _text("Offered on (YYYY-MM-DD)", tt.offer_day)
            school = _text("Offered school (blank = destination)")
            y6.record_offer(pid, self.year, on, school, actor=self.actor)
            print("  Offer recorded.")

    def record_acceptance(self) -> None:
        pid = self.pick_pupil()
        if pid:
            y6.record_acceptance(pid, self.year, _text("Accepted on (YYYY-MM-DD)"),
                                 actor=self.actor)
            print("  Acceptance recorded.")

    def record_decline(self) -> None:
        pid = self.pick_pupil()
        if pid:
            y6.record_decline(pid, self.year, _text("Declined on (YYYY-MM-DD)"),
                              _text("Reason"), actor=self.actor)
            print("  Decline recorded.")

    def external_move(self) -> None:
        pid = self.pick_pupil()
        if pid and _yes_no("Write the leaver record and take the pupil off roll?"):
            lid = y6.complete_external_move(pid, self.year, _text("Leaving date (YYYY-MM-DD)"),
                                            _text("Notes"))
            print(f"  Done. Leaver record {lid or '-'}.")

    # ── Transition reports ──────────────────────────────────────────

    def edit_report(self) -> None:
        pid = self.pick_pupil()
        if not pid:
            return
        rep = y6.get_report(pid, self.year) or y6.TransitionReport(pid, self.year)
        others = self.pupils(exclude=pid)
        data: dict[str, Any] = {
            "strengths": _text("Strengths", rep.strengths),
            "interests": _text("Interests", rep.interests),
            "learning_style": _text("How they learn best", rep.learning_style),
            "worries": _text("Worries about secondary", rep.worries),
            "friendships": _choose_many("Friendships ('-' clears)", others, rep.friendships),
            "keep_apart": _choose_many("Keep apart from ('-' clears)", others, rep.keep_apart),
            "all_about_me": _text("All about me", rep.all_about_me),
            "teacher_comments": _text("Teacher comments", rep.teacher_comments),
        }
        data["enhanced_transition"] = _yes_no("Enhanced transition needed?",
                                              rep.enhanced_transition)
        data["enhanced_reason"] = (_text("Why enhanced", rep.enhanced_reason)
                                   if data["enhanced_transition"] else "")
        staff = _staff_names()
        written_by = _choose("Written by", staff) if staff else _text("Written by")
        data["written_by"] = written_by or rep.written_by
        data["written_on"] = _text("Written on (YYYY-MM-DD, blank = today)",
                                   rep.written_on or "")
        y6.save_report(pid, self.year, data)
        print("  Report saved.")

    def view_report(self) -> None:
        pid = self.pick_pupil()
        if not pid:
            return
        payload = y6.report_payload(pid, self.year)
        if payload is None:
            print("  No report yet.")
            return
        for key, value in payload.items():
            if isinstance(value, list):
                value = ", ".join(value) or "-"
            print(f"  {key.replace('_', ' ').capitalize():<22} {value if value != '' else '-'}")

    # ── Consent & Handover ──────────────────────────────────────────

    def record_consent(self) -> None:
        pid = self.pick_pupil()
        if not pid:
            return
        rec = y6.get_record(pid, self.year) or y6.Year6Record(pid, self.year)
        consents = {k: _yes_no(f"May share {y6.CONSENT_LABELS[k]}?", rec.consent.get(k, False))
                    for k in y6.CONSENT_FIELDS}
        given_by = _text("Parent / carer giving the decision", rec.consent_given_by or "")
        given_on = _text("Date (YYYY-MM-DD)", rec.consent_on or "")
        method = _choose("How", [(m, m) for m in y6.CONSENT_METHODS])
        if not method:
            return
        y6.set_consent(pid, self.year, consents, given_by=given_by, given_on=given_on,
                       method=method)
        print("  Consent recorded.")

    def preview(self) -> None:
        pid = self.pick_pupil()
        if pid:
            out = y6.preview_handover(pid, self.year)
            print("  Would be shared: " + (", ".join(out["included"]) or "nothing"))
            print("  Withheld (no consent): " + (", ".join(out["withheld_no_consent"]) or "none"))
            if out["missing"]:
                print("  Missing required: " + ", ".join(out["missing"]))

    def approve(self) -> None:
        if not access.can_approve_year6_handover(self.principal):
            print("  Only an administrator or a designated safeguarding lead can approve "
                  "the handover.")
            return
        pid = self.pick_pupil()
        if pid and _yes_no("Release the handover now? It can only be approved once."):
            y6.approve_handover(pid, self.year, actor=self.actor)
            print("  Handover approved.")

    # ── Visits ──────────────────────────────────────────────────────

    def _visit_data(self, current: y6.Visit | None = None) -> dict[str, Any] | None:
        vtype = _choose("Visit type", [(t, t) for t in y6.VISIT_TYPES])
        if not vtype:
            return None
        return {
            "visit_date": _text("Date (YYYY-MM-DD)", current.visit_date if current else ""),
            "visit_type": vtype,
            "school_name": _text("School (blank = destination)",
                                 (current.school_name or "") if current else ""),
            "attended": _yes_no("Attended?", current.attended if current else True),
            "notes": _text("Notes", (current.notes or "") if current else ""),
        }

    def list_visits(self) -> list[y6.Visit]:
        visits = y6.list_visits(self.year)
        if not visits:
            print("  (no visits)")
        for v in visits:
            print(f"  #{v.visit_id:<5} {v.pupil_id:<10} {v.visit_date} {v.visit_type:<28} "
                  f"{(v.school_name or '')[:24]:<24} {'attended' if v.attended else 'absent'}")
        return visits

    def add_visit(self) -> None:
        ids = _choose_many("Pupils", self.pupils())
        if not ids:
            return
        data = self._visit_data()
        if data:
            y6.add_group_visit(ids, self.year, data)
            print(f"  Visit recorded for {len(ids)} pupil(s).")

    def edit_visit(self) -> None:
        visits = self.list_visits()
        vid = _choose("Visit", [(str(v.visit_id), f"#{v.visit_id} {v.pupil_id} {v.visit_date}")
                                for v in visits])
        if not vid:
            return
        visit = y6.get_visit(int(vid))
        if _yes_no("Delete this visit instead of editing?"):
            y6.delete_visit(int(vid))
            print("  Deleted.")
            return
        data = self._visit_data(visit)
        if data:
            y6.update_visit(int(vid), data)
            print("  Saved.")

    # ── Safeguarding files ──────────────────────────────────────────

    def safeguarding(self) -> None:
        if not access.can_manage_year6_safeguarding_files(self.principal):
            print("  Safeguarding file transfers are recorded by the designated "
                  "safeguarding lead.")
            return
        for sg in y6.list_safeguarding_transfers(self.year):
            print(f"  {sg.pupil_id:<10} {'file' if sg.has_file else 'no file':<8} "
                  f"sent {sg.sent_on or '-':<11} to {sg.sent_to_name or '-'} "
                  f"({sg.sent_to_school or '-'}) receipt {sg.receipt_confirmed_on or '-'}")
        pid = self.pick_pupil()
        if not pid:
            return
        sg = y6.get_safeguarding_transfer(pid, self.year)
        has_file = _yes_no("Is there a safeguarding file to transfer?",
                           sg.has_file if sg else True)
        data: dict[str, Any] = {"has_file": has_file}
        if has_file:
            data["sent_on"] = _text("Date sent (YYYY-MM-DD)", (sg.sent_on or "") if sg else "")
            data["sent_to_name"] = _text("Sent to (name)", (sg.sent_to_name or "") if sg else "")
            data["sent_to_role"] = _text("Their role", (sg.sent_to_role or "") if sg
                                         else "Designated Safeguarding Lead")
            data["sent_to_school"] = _text("School", (sg.sent_to_school or "") if sg else "")
            method = _choose("Method", [(m, m) for m in y6.SAFEGUARDING_METHODS],
                             allow_blank=True)
            data["method"] = method or ((sg.method or "") if sg else "")
            data["receipt_confirmed_on"] = _text(
                "Receipt confirmed on (YYYY-MM-DD)",
                (sg.receipt_confirmed_on or "") if sg else "")
        data["recorded_by"] = self.principal.username or _text("Recorded by")
        data["notes"] = _text("Notes (no case detail)", (sg.notes or "") if sg else "")
        y6.save_safeguarding_transfer(pid, self.year, data)
        print("  Saved.")


def _staff_names() -> list[tuple[str, str]]:
    try:
        from education_system.systems.primary.domain.staff import staff
        return [(s.full_name, f"{s.full_name} ({s.staff_id})")
                for s in staff.list_staff(active_only=True)]
    except Exception:  # noqa: BLE001
        logger.debug("staff list failed", exc_info=True)
        return []


@_safe
def open_year6_transition() -> None:
    logger.debug("CLI: open_year6_transition")
    s = _Session()
    actions: dict[str, tuple[str, Callable[[], None]]] = {
        "1": ("Cohort overview", s.show_cohort),
        "2": ("Checklist & secondary status", s.show_checklist),
        "3": ("Refresh status from secondary", s.refresh_secondary),
        "4": ("Set destination", s.set_destination),
        "5": ("Record application", s.record_application),
        "6": ("Record offer", s.record_offer),
        "7": ("Record acceptance", s.record_acceptance),
        "8": ("Record decline", s.record_decline),
        "9": ("Complete move to another school", s.external_move),
        "10": ("Write / edit transition report", s.edit_report),
        "11": ("View transition report", s.view_report),
        "12": ("Record consent", s.record_consent),
        "13": ("Preview handover", s.preview),
        "14": ("Approve handover", s.approve),
        "15": ("List visits", s.list_visits),
        "16": ("Add visit", s.add_visit),
        "17": ("Edit / delete visit", s.edit_visit),
        "18": ("Safeguarding files (DSL)", s.safeguarding),
        "19": ("Pupil notes", s.edit_notes),
        "20": ("Change academic year", s.set_year),
    }
    while True:
        print(f"\n  -- {LABEL} ({s.year}) --")
        for key, (label, _fn) in actions.items():
            print(f"  {key:>3}) {label}")
        print("    0) Back")
        choice = _prompt("  Select: ")
        if choice in ("", "0"):
            return
        entry = actions.get(choice)
        if entry is None:
            print("  Invalid selection.")
            continue
        _safe(entry[1])()


_DISPATCH = {LABEL: open_year6_transition}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching Year 6 transition CLI label: %s", label)
    handler()
    return True


__all__ = ["dispatch", "open_year6_transition"]
