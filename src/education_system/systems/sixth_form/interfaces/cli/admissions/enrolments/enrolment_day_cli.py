"""Enrolment CLI: enrolment day (cohort board, learner status, the
confirmation document, ID card, confirmation wording) and learner /
parent agreements.

Refusals (ValidationError, AccessDenied) are raised to the submenu, which
prints the message."""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domain.admissions.enrolments import agreements
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolment_day
from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments._common import (
    _UserAbort,
    _default_academic_year,
    _input,
    _offer_csv,
    _pause,
    _pick_enrolment_for,
    _pick_from,
    _pick_student,
    _prompt_academic_year,
    _writes_ok,
)

logger = logging.getLogger(__name__)

_MARK = {True: "✓", False: "✗", None: "·"}


def _print_status(st: enrolment_day.LearnerStatus) -> None:
    done, total = st.done_count
    print(f"\n  {st.student_id}  {st.name}  {st.academic_year}"
          + (f"  #{st.enrolment_id} Year {st.year_group} {st.tutor_group or ''}"
             if st.enrolment_id else "")
          + f"  — {st.overall} ({done}/{total})")
    for item in st.items:
        print(f"    {_MARK[item.done]} {item.name:<30} {item.detail}")


# ── Enrolment day ───────────────────────────────────────────────────

def cohort_board() -> None:
    print("\n═══ Enrolment Day — Cohort Board ═══")
    try:
        year = _prompt_academic_year(_default_academic_year())
        yg = _pick_from("Year group", ["All", "12", "13"], default="All")
        detail = _input("Show every item for each learner? (y/n)",
                        default="n").lower().startswith("y")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = enrolment_day.cohort_board(year, None if yg == "All" else int(yg))
    ready = sum(1 for r in rows if r.overall == enrolment_day.READY)
    print(f"\n  {len(rows)} live enrolment(s): {ready} ready, "
          f"{len(rows) - ready} outstanding")
    for st in rows:
        if detail:
            _print_status(st)
            continue
        done, total = st.done_count
        todo = ", ".join(i.name for i in st.outstanding)
        print(f"    {st.student_id:<10} {st.name[:24]:<24} Y{st.year_group or '-'} "
              f"{st.overall:<11} {done}/{total}" + (f"  to do: {todo}" if todo else ""))
    _offer_csv([{"student_id": st.student_id, "name": st.name,
                 "academic_year": st.academic_year, "enrolment_id": st.enrolment_id,
                 "year_group": st.year_group, "tutor_group": st.tutor_group,
                 "overall": st.overall,
                 "outstanding": [i.name for i in st.outstanding]} for st in rows],
               "enrolment_day_board.csv")
    _pause()


def learner_status() -> None:
    print("\n═══ Enrolment Day — One Learner ═══")
    try:
        sid = _pick_student(include_leavers=True)
        year = _prompt_academic_year(_default_academic_year())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_status(enrolment_day.learner_status(sid, year))
    _pause()


def confirmation() -> None:
    """The enrolment confirmation and learner agreement: print it, and
    optionally save it to a text file."""
    print("\n═══ Enrolment Confirmation ═══")
    try:
        e = _pick_enrolment_for()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if e is None:
        return
    text = enrolment_day.confirmation_text(e.enrolment_id)
    print()
    print(text)
    try:
        path = _input("Save to a file? Path (blank = no)")
    except _UserAbort:
        return
    if path:
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
            print(f"  ✓ Saved to {path}")
        except OSError as exc:
            print(f"  ✗ Could not write {path}: {exc}")
    _pause()


def id_card() -> None:
    print("\n═══ Learner ID Card ═══")
    try:
        sid = _pick_student(include_leavers=True)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    c = enrolment_day.id_card_data(sid)
    lines = [
        f"Name        : {c.name}" + (f" ({c.preferred_name})" if c.preferred_name else ""),
        f"Student ID  : {c.student_id}",
        f"Year        : {c.academic_year or '—'}"
        + (f", Year {c.year_group}" if c.year_group else "")
        + (f", tutor group {c.tutor_group}" if c.tutor_group else ""),
        f"Valid until : {c.valid_until or '—'}",
        f"Card number : {c.card_number or '— (no card issued)'}",
        f"Photo       : {c.photo_path or 'MISSING — add one under Photo & ID Checks'}",
    ]
    width = max(len(x) for x in lines) + 4
    print("\n  ┌" + "─" * width + "┐")
    for x in lines:
        print(f"  │  {x:<{width - 2}}│")
    print("  └" + "─" * width + "┘")
    _pause()


def confirmation_template() -> None:
    """View, edit (new version) and list versions of the expectations
    wording printed on the confirmation."""
    while True:
        print("\n═══ Confirmation Wording ═══")
        print(enrolment_day.get_template())
        print("\n  E) Edit (new version)   V) Versions   (Enter to go back)")
        try:
            choice = _input("Action").lower()
        except _UserAbort:
            return
        if not choice:
            return
        if choice == "v":
            for v in enrolment_day.template_versions():
                first = (v["body"].strip().splitlines() or [""])[0]
                print(f"    v#{v['template_id']:<4} {v['saved_at'][:16]} by "
                      f"{v.get('saved_by') or '—':<10} {first[:50]}")
            if not enrolment_day.template_versions():
                print("    (only the built-in wording — never edited)")
            continue
        if choice != "e":
            print("  ✗ Pick E or V.")
            continue
        if not _writes_ok():
            continue
        try:
            src = _input("Read the new wording from a file path (blank = type it)")
            if src:
                with open(src, encoding="utf-8") as fh:
                    body = fh.read()
            else:
                print("  Type the wording; a line with just '.' ends it.")
                lines: list[str] = []
                while True:
                    line = input("  > ")
                    if line.strip() == ".":
                        break
                    lines.append(line)
                body = "\n".join(lines)
            if not _input("Save as the new version? (y/n)", default="n"
                          ).lower().startswith("y"):
                print("  Not saved.")
                continue
        except (_UserAbort, EOFError, KeyboardInterrupt):
            print("  Cancelled.")
            continue
        except OSError as exc:
            print(f"  ✗ Could not read the file: {exc}")
            continue
        try:
            enrolment_day.save_template(body)
            print("  ✓ Saved")
        except (ValueError, PermissionError) as exc:
            print(f"  ✗ {exc}")


# ── Agreements ──────────────────────────────────────────────────────

def _print_agreements(enrolment_id: int) -> None:
    st = agreements.state(enrolment_id)
    print(f"\n  Agreements — enrolment #{enrolment_id}: "
          + ("complete" if st.complete else "to do — " + "; ".join(st.missing))
          + ("  (parent/guardian needed: under 18 at start)" if st.parent_needed else ""))
    for a in agreements.for_enrolment(enrolment_id):
        print(f"    #{a.agreement_id:<5} {a.kind:<16} {a.status:<10} "
              f"{a.signed_name}" + (f" ({a.relationship})" if a.relationship else "")
              + f", {a.method}, signed {a.signed_on}"
              + (f" — {a.ended_reason}" if a.ended_reason else ""))


def record_agreement() -> None:
    print("\n═══ Record Agreement ═══")
    if not _writes_ok():
        return
    try:
        e = _pick_enrolment_for()
        if e is None:
            return
        _print_agreements(e.enrolment_id)
        kind = _pick_from("Who signed", list(agreements.KINDS))
        method = _pick_from("Method", list(agreements.METHODS), default="Paper")
        contact_id = relationship = name = None
        if kind == agreements.PARENT:
            contacts = agreements.parent_contacts(e.student_id)
            labels = [f"#{c.contact_id} {c.full_name} ({c.relationship})"
                      + (" [PR]" if c.has_parental_responsibility else "")
                      for c in contacts] + ["Someone not on file"]
            pick = _pick_from("Parent / guardian", labels, default=labels[0])
            if pick.startswith("#"):
                contact_id = int(pick.split()[0].lstrip("#"))
            else:
                name = _input("Name as signed", allow_empty=False)
                relationship = _input("Relationship to the learner", allow_empty=False)
        else:
            name = _input("Name as signed (blank = the learner's name)") or None
        signed_on = _input("Signed on (YYYY-MM-DD; blank = today)") or None
        notes = _input("Notes (optional)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    a = agreements.record(e.enrolment_id, kind, method=method, signed_name=name,
                          signed_on=signed_on, relationship=relationship,
                          contact_id=contact_id, notes=notes)
    print(f"  ✓ Recorded agreement #{a.agreement_id}: {a.kind} — {a.signed_name}")
    _print_agreements(e.enrolment_id)
    _pause()


def _pick_current(enrolment_id: int) -> agreements.Agreement | None:
    rows = agreements.for_enrolment(enrolment_id, current_only=True)
    if not rows:
        print("  (no current agreement on this enrolment)")
        _pause()
        return None
    pick = _pick_from("Agreement", [f"#{a.agreement_id} {a.kind} — {a.signed_name}, "
                                    f"{a.signed_on}" for a in rows])
    return agreements.get(int(pick.split()[0].lstrip("#")))


def withdraw_agreement() -> None:
    print("\n═══ Withdraw Agreement ═══")
    if not _writes_ok():
        return
    try:
        e = _pick_enrolment_for()
        if e is None:
            return
        a = _pick_current(e.enrolment_id)
        if a is None:
            return
        reason = _input("Reason (required)", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    agreements.withdraw(a.agreement_id, reason=reason)
    print(f"  ✓ Agreement #{a.agreement_id} withdrawn")
    _print_agreements(e.enrolment_id)
    _pause()


def correct_agreement() -> None:
    """Replace a signature's details; blank keeps the old value."""
    print("\n═══ Correct Agreement ═══")
    if not _writes_ok():
        return
    try:
        e = _pick_enrolment_for()
        if e is None:
            return
        a = _pick_current(e.enrolment_id)
        if a is None:
            return
        name = _input("Name as signed", default=a.signed_name) or None
        signed_on = _input("Signed on (YYYY-MM-DD)", default=a.signed_on) or None
        method = _pick_from("Method", list(agreements.METHODS), default=a.method)
        relationship = (_input("Relationship", default=a.relationship or "") or None
                        if a.kind == agreements.PARENT else None)
        reason = _input("Reason for the correction (required)", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    new = agreements.correct(a.agreement_id, reason=reason, method=method,
                             signed_name=name, signed_on=signed_on,
                             relationship=relationship)
    print(f"  ✓ #{a.agreement_id} corrected — now #{new.agreement_id}")
    _print_agreements(e.enrolment_id)
    _pause()


def agreement_history() -> None:
    print("\n═══ Agreement History ═══")
    try:
        e = _pick_enrolment_for()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if e is None:
        return
    _print_agreements(e.enrolment_id)
    rows = agreements.history(e.enrolment_id)
    print("\n    History (newest first):")
    for h in rows:
        print(f"      {h['changed_at'][:16]}  #{h['agreement_id']:<5} {h['action']:<10} "
              f"{h.get('changed_by') or '—':<10} {h.get('detail') or ''}")
    if not rows:
        print("      (none)")
    _pause()


def outstanding_agreements() -> None:
    print("\n═══ Outstanding Agreements ═══")
    try:
        year = _prompt_academic_year(_default_academic_year())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = agreements.outstanding(year)
    print(f"\n  {len(rows)} enrolment(s) in {year} missing a signature:")
    for r in rows:
        print(f"    #{r.enrolment_id:<5} {r.student_id:<10} Y{r.year_group}  "
              f"missing: {', '.join(r.missing)}")
    _offer_csv(rows, "outstanding_agreements.csv")
    _pause()


MENU = [
    ("Cohort board", cohort_board),
    ("One learner's enrolment-day status", learner_status),
    ("Enrolment confirmation (print / save)", confirmation),
    ("ID card", id_card),
    ("Confirmation wording (view / edit / versions)", confirmation_template),
    ("Record agreement (learner / parent)", record_agreement),
    ("Withdraw agreement", withdraw_agreement),
    ("Correct agreement", correct_agreement),
    ("Agreement history", agreement_history),
    ("Outstanding agreements (year)", outstanding_agreements),
]
