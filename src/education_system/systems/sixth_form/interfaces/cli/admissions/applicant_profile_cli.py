"""Admissions CLI: an applicant's profile and eligibility, contacts,
sensitive information, identity / right to study, open-event history,
programme choices and re-applying in a later cycle.

Every flow takes the applicant (from the per-applicant actions menu);
:func:`run` picks one and opens the same set as a menu.
"""

from __future__ import annotations

from typing import Any, Callable

from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
    applicant_details as details,
    cycles,
    open_events,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    identity_checks as idc,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _UserAbort,
    _attempt,
    _can,
    _fresh,
    _input,
    _pause,
    _pick_applicant,
    _pick_from,
    _run_submenu,
    _yes,
)


def _yn(v: Any) -> str:
    return "yes" if v else "no"


# ── Profile & eligibility ──────────────────────────────────────────

def profile_flow(a: Applicant) -> None:
    print(f"\n═══ Profile & Eligibility — {a.applicant_id} {a.full_name} ═══")
    eth = dict(details.ethnicities())
    for key, label in details.PROFILE_FIELDS:
        v = getattr(a, key)
        if key in data.FLAG_COLUMNS:
            v = _yn(v)
        elif key == "ethnicity" and v:
            v = f"{v} — {eth.get(v, '?')}"
        print(f"    {label:<38}: {v if v not in (None, '') else '—'}")
    print(f"    {'16–19 funding residency':<38}: "
          f"{details.funding_eligibility(a)}")
    if not _yes("\n  Edit the profile?"):
        _pause()
        return
    changes: dict[str, Any] = {}
    changes["intake_year"] = _input("Intake year (e.g. 2027/28)",
                                    default=a.intake_year or "") or None
    sex = _pick_from("Sex", ["(not recorded)"] + list(details.GENDER_OPTIONS),
                     default=details.gender_label(a.sex) or "(not recorded)")
    changes["sex"] = None if sex.startswith("(") else sex
    eth_labels = ["(not recorded)"] + [f"{c} — {lbl}" for c, lbl in eth.items()]
    cur = f"{a.ethnicity} — {eth[a.ethnicity]}" if a.ethnicity in eth else \
        "(not recorded)"
    got = _pick_from("Ethnicity", eth_labels, default=cur)
    changes["ethnicity"] = None if got.startswith("(") else got.split(" — ")[0]
    changes["nationality"] = _input("Nationality",
                                    default=a.nationality or "") or None
    changes["first_language"] = _input("First language",
                                       default=a.first_language or "") or None
    res = _pick_from("Residency", ["(not recorded)"]
                     + list(details.RESIDENCY_STATUSES),
                     default=a.residency_status or "(not recorded)")
    changes["residency_status"] = None if res.startswith("(") else res
    for key, label in details.PROFILE_FIELDS:
        if key in data.FLAG_COLUMNS:
            changes[key] = _yes(label, default="y" if getattr(a, key) else "n")
    ok, out = _attempt(details.update_profile, a.applicant_id, **changes)
    if ok:
        print(f"  ✓ Saved — funding: {details.funding_eligibility(out)}")
    _pause()


# ── Contacts ───────────────────────────────────────────────────────

def _contact_form(c: details.Contact | None = None) -> dict[str, Any]:
    rel = _pick_from("Relationship", list(details.CONTACT_RELATIONSHIPS),
                     default=(c.relationship if c and c.relationship
                              else "Parent"))
    return {
        "name": _input("Name", default=c.name if c else "", allow_empty=False),
        "relationship": rel,
        "phone": _input("Phone", default=(c.phone or "") if c else "") or None,
        "email": _input("E-mail", default=(c.email or "") if c else "") or None,
        "address": _input("Address",
                          default=(c.address or "") if c else "") or None,
        "is_emergency": _yes("Emergency contact?",
                             default="y" if c and c.is_emergency else "n"),
        "parental_responsibility": _yes(
            "Parental responsibility?",
            default="y" if (c is None or c.parental_responsibility) else "n"),
        "receives_correspondence": _yes(
            "Receives letters / e-mails?",
            default="y" if (c is None or c.receives_correspondence) else "n"),
    }


def contacts_flow(a: Applicant) -> None:
    while True:
        rows = details.list_contacts(a.applicant_id)
        print(f"\n═══ Contacts — {a.applicant_id} {a.full_name} ═══")
        for i, c in enumerate(rows, 1):
            tags = [t for t, on in (("emergency", c.is_emergency),
                                    ("PR", c.parental_responsibility),
                                    ("letters", c.receives_correspondence))
                    if on]
            print(f"    {i}) {c.name} ({c.relationship or '—'})  "
                  f"{c.phone or ''} {c.email or ''}  [{', '.join(tags)}]")
        if not rows:
            print("    (no contacts)")
        choice = _input("\n  (a)dd, (e)dit <n>, (r)emove <n>, Enter) back",
                        default="")
        if not choice:
            return
        parts = choice.split()
        idx = (int(parts[1]) - 1 if len(parts) > 1 and parts[1].isdigit()
               else None)
        cmd = parts[0].lower()
        try:
            if cmd == "a":
                ok, c = _attempt(details.add_contact, a.applicant_id,
                                 _contact_form())
                if ok:
                    print(f"  ✓ Added {c.name}")
            elif cmd in ("e", "r") and idx is not None and 0 <= idx < len(rows):
                c = rows[idx]
                if cmd == "e":
                    ok, _ = _attempt(details.update_contact, c.contact_id,
                                     _contact_form(c))
                    if ok:
                        print("  ✓ Updated")
                elif _yes(f"Remove {c.name}?"):
                    ok, _ = _attempt(details.remove_contact, c.contact_id)
                    if ok:
                        print("  ✓ Removed")
            else:
                print("  ✗ Unrecognised action.")
        except _UserAbort:
            continue


# ── Sensitive information ──────────────────────────────────────────

def sensitive_flow(a: Applicant) -> None:
    """Admissions staff see only *that* something is held; the text needs
    the area's own permission (SEND / medical / safeguarding)."""
    print(f"\n═══ Sensitive Information — {a.applicant_id} ═══")
    view = details.get_sensitive(a.applicant_id)
    for area, (_col, _cap, label) in details.SENSITIVE_AREAS.items():
        held = "held" if view.held.get(area) else "none"
        if area in view.visible:
            print(f"    {label}: {view.visible[area] or '(none)'}")
            if area == "safeguarding" and view.received_from:
                print(f"      received from: {view.received_from}")
        else:
            print(f"    {label}: [{held}] — needs the {area} permission to "
                  "view")
    editable = [area for area in details.SENSITIVE_AREAS
                if _can(getattr(access, details.SENSITIVE_AREAS[area][1]))]
    if editable and _yes("\n  Record or clear one area?"):
        labels = [details.SENSITIVE_AREAS[x][2] for x in editable]
        area = editable[labels.index(_pick_from("Area", labels))]
        text = _input("Text (blank clears)",
                      default=view.visible.get(area) or "")
        frm = None
        if area == "safeguarding":
            frm = _input("Received from (school / DSL name)",
                         default=view.received_from or "") or None
        ok, _ = _attempt(details.set_sensitive, a.applicant_id, area,
                         text or None, received_from=frm)
        if ok:
            print("  ✓ Saved (the timeline records only that it changed)")
    _pause()


# ── Identity & right to study ──────────────────────────────────────

def identity_flow(a: Applicant) -> None:
    print(f"\n═══ Identity & Right to Study — {a.applicant_id} ═══")
    rec = details.get_identity(a.applicant_id)
    if rec:
        print(f"    Document : {rec.document_type or '—'} (…{rec.id_number_last4 or ''})")
        print(f"    Right to study : {rec.right_to_study}")
        if rec.visa_type or rec.visa_expiry:
            print(f"    Visa : {rec.visa_type or '—'} expires "
                  f"{rec.visa_expiry or '—'}")
        print(f"    Checked {rec.checked_on or '—'} by {rec.checked_by or '—'}"
              + (f" — {rec.notes}" if rec.notes else ""))
    else:
        print("    (no check recorded)")
    ok, why = details.identity_ok(a.applicant_id)
    print(f"    Enrolment gate : {'✓' if ok else '✗'} {why}")
    hist = details.identity_history(a.applicant_id)
    if len(hist) > 1 or (hist and not rec):
        print("\n    History:")
        for h in hist:
            print(f"      {h.get('checked_on') or '—'}  {h.get('document_type')}"
                  f" …{h.get('id_number_last4') or ''}  "
                  f"{h.get('right_to_study')}  by {h.get('checked_by') or '—'}")
    if _yes("\n  Record a check?"):
        doc = _pick_from("Document seen", list(idc.ID_DOCUMENT_TYPES),
                         default=rec.document_type if rec and rec.document_type
                         else None)
        number = _input("Document number (only the last 4 are kept)",
                        allow_empty=False)
        rts = _pick_from("Right to study", list(details.RIGHT_TO_STUDY),
                         default=rec.right_to_study if rec else None)
        visa_type = visa_expiry = None
        if rts.startswith("Yes - visa"):
            visa_type = _input("Visa type", default=(rec.visa_type or "")
                               if rec else "") or None
            visa_expiry = _input("Visa expiry (YYYY-MM-DD)",
                                 allow_empty=False)
        ok, _ = _attempt(details.record_identity_check, a.applicant_id,
                         document_type=doc, document_number=number,
                         right_to_study=rts, visa_type=visa_type,
                         visa_expiry=visa_expiry,
                         checked_on=_input("Checked on (blank = today)") or None,
                         notes=_input("Notes") or None)
        if ok:
            print("  ✓ Recorded (previous check kept in the history)")
    _pause()


# ── Open events, programme choices, re-applying ────────────────────

def open_event_history_flow(a: Applicant) -> None:
    print(f"\n═══ Open Events — {a.applicant_id} {a.full_name} ═══")
    rows = open_events.bookings_for_applicant(a.applicant_id)
    for b in rows:
        ev = open_events.get_event(b.event_id)
        att = ("unmarked" if b.attended is None
               else "attended" if b.attended else "no-show")
        print(f"    {ev.label if ev else f'event #{b.event_id}'}  "
              f"party {b.party_size}  {att}  follow-up {b.follow_up_status}")
    if not rows:
        print("    (no open-event bookings linked)")
    _pause()


def programme_choices_flow(a: Applicant) -> None:
    while True:
        rows = data.list_programme_choices(a.applicant_id)
        print(f"\n═══ Programme Choices — {a.applicant_id} ═══")
        for i, c in enumerate(rows, 1):
            print(f"    {i}) {c.qualification_type:<22} {c.subject}")
        if not rows:
            print("    (none)")
        cmd = _input("  (a)dd, (r)emove <n>, Enter) back", default="")
        if not cmd:
            return
        try:
            if cmd.lower() == "a":
                q = _pick_from("Qualification", list(data.programme_types()),
                               default="A Level")
                subj = _input("Subject / course", allow_empty=False)
                if _attempt(data.add_programme_choice, a.applicant_id, q,
                            subj)[0]:
                    print("  ✓ Added")
            elif cmd.lower().startswith("r"):
                n = cmd.split()[-1]
                if n.isdigit() and 1 <= int(n) <= len(rows):
                    c = rows[int(n) - 1]
                    if _attempt(data.remove_programme_choice, a.applicant_id,
                                c.qualification_type, c.subject)[0]:
                        print("  ✓ Removed")
        except _UserAbort:
            continue


def reapply_flow(a: Applicant) -> None:
    print(f"\n═══ Re-apply in a Later Cycle — {a.applicant_id} ═══")
    earlier = cycles.reapplied_from(a.applicant_id)
    later = cycles.reapplications_of(a.applicant_id)
    if earlier:
        print(f"    Re-applies from {earlier}")
    if later:
        print(f"    Re-applied as {', '.join(later)}")
    if a.status not in cycles.REAPPLY_FROM:
        print(f"    Re-applying starts from {', '.join(cycles.REAPPLY_FROM)} "
              f"(this one is {a.status}).")
        _pause()
        return
    names = [c.cycle for c in cycles.list_cycles(include_archived=False)
             if c.cycle != a.intake_year]
    default = cycles.next_cycle_name(a.intake_year or data.default_intake_year())
    to = (_pick_from("Cycle", names, default=default if default in names
                     else None) if names
          else _input("Cycle (e.g. 2027/28)", default=default))
    note = _input("Note")
    ok, new = _attempt(cycles.reapply, a.applicant_id, to, note=note or None)
    if ok:
        print(f"  ✓ New application {new.applicant_id} in {new.intake_year} "
              f"[{new.status}]")
    _pause()


def booking_history_flow(a: Applicant) -> None:
    from education_system.systems.sixth_form.domain.admissions import (
        interviews,
    )
    print(f"\n═══ Interview Bookings — {a.applicant_id} ═══")
    rows = interviews.booking_history(a.applicant_id)
    for b in rows:
        print(f"    #{b.booking_id} {b.slot.label if b.slot else b.slot_id}"
              f"  [{b.status}]" + (f" — {b.reason}" if b.reason else ""))
    if not rows:
        print("    (no slot bookings)")
    _pause()


ACTIONS: list[tuple[str, Callable[[Applicant], None]]] = [
    ("Profile & eligibility", profile_flow),
    ("Contacts (parents/carers)", contacts_flow),
    ("Sensitive information", sensitive_flow),
    ("Identity & right to study", identity_flow),
    ("Open-event history", open_event_history_flow),
    ("Programme choices", programme_choices_flow),
    ("Interview booking history", booking_history_flow),
    ("Re-apply in a later cycle", reapply_flow),
]


def run() -> None:
    a = _pick_applicant()
    _run_submenu(f"Profile — {a.applicant_id} {a.full_name}",
                 [(label, (lambda f=fn: f(_fresh(a)))) for label, fn in ACTIONS])
