"""Trusted contacts — CLI twin of the Wellbeing Casework tab.

A student manages their own contacts and consent; support staff record and
follow up each use of a contact.
"""

from __future__ import annotations

from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    access,
)
from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    trusted_contacts as tc,
)
from education_system.systems.university.domains.student_support.interfaces.cli.wellbeing.casework.prompts import (
    ask,
    ask_text,
    choose,
    pause,
    run,
    table,
    yes,
)

CONTACTS = (("contact_id", "#", 5), ("priority", "Ord", 4), ("name", "Name", 22),
            ("relationship", "Relationship", 14), ("phone", "Phone", 15), ("email", "E-mail", 26))
USES = (("use_id", "#", 5), ("contact_name", "Contact", 18), ("status", "Status", 10),
        ("basis", "Basis", 15), ("emergency", "Emerg", 5), ("approved_by", "Approved", 10),
        ("student_informed", "Told", 4), ("reason", "Why", 36))


def _show(auth, student_id) -> None:
    state = run(tc.consent, auth, student_id)
    if state is None:
        return
    print(f"\nConsent: {'given ' + str(state.get('given_at') or '')[:10] if state['consent_given'] else 'not given'}")
    print("Contacts:")
    table(run(tc.list_contacts, auth, student_id) or [], CONTACTS)
    print("Uses:")
    table(run(tc.uses, auth, student_id) or [], USES if access.support_scope(auth) is None
          else (("use_id", "#", 5), ("contact_name", "Contact", 18),
                ("contacted_at", "When", 17), ("method", "How", 10), ("reason", "Why", 40)))


def _contact_details():
    return (ask("Name"), ask("Relationship"), ask("Phone"), ask("E-mail"), ask("Address (optional)"))


def _student_menu(auth) -> None:
    sid = access.support_scope(auth)
    while True:
        _show(auth, sid)
        print("\n1. Add a contact  2. Edit a contact  3. Remove a contact")
        print("4. Give consent   5. Withdraw consent  0. Back")
        choice = input("Choice: ").strip()
        if choice == "0":
            return
        if choice == "1":
            name, rel, phone, email, address = _contact_details()
            run(tc.add_contact, auth, name, rel, phone, email, address=address, done="Added.")
        elif choice == "2":
            cid = ask("Contact #")
            name, rel, phone, email, address = _contact_details()
            run(tc.update_contact, auth, int(cid or 0), name, rel, phone, email,
                address=address, done="Updated.")
        elif choice == "3":
            run(tc.remove_contact, auth, int(ask("Contact #") or 0), done="Removed.")
        elif choice == "4":
            print("\n" + tc.CONSENT_STATEMENT)
            if yes("Do you agree"):
                run(tc.set_consent, auth, True, done="Consent recorded.")
        elif choice == "5":
            if yes("Withdraw consent"):
                run(tc.set_consent, auth, False, done="Consent withdrawn.")


def _use_action(auth, sid) -> None:  # noqa: C901 - a flat menu
    choice = choose("Action", [("request", "Request contact"), ("approve", "Approve a use"),
                               ("decline", "Decline a use"), ("record", "Record contact made"),
                               ("inform", "Tell the student"), ("defer", "Defer telling")])
    if choice == "request":
        run(tc.request_use, auth, sid, int(ask("Contact #") or 0),
            ask_text("The serious concern (shared with the student later)"),
            ask_text("Circumstances (staff only)"),
            emergency=yes("Emergency — risk to life"), done="Recorded; it needs approval.")
    elif choice in ("approve", "decline"):
        run(tc.decide_use, auth, int(ask("Use #") or 0), choice == "approve", ask("Note"),
            done="Decision recorded.")
    elif choice == "record":
        method = choose("How", [(m, m) for m in tc.METHODS])
        run(tc.record_contact, auth, int(ask("Use #") or 0), method or "",
            ask_text("What was said and agreed"), done="Contact recorded.")
    elif choice == "inform":
        run(tc.inform_student, auth, int(ask("Use #") or 0), ask("Anything to add"),
            done="The student has been told (their inbox).")
    elif choice == "defer":
        run(tc.defer_informing, auth, int(ask("Use #") or 0),
            ask_text("Why telling them now would increase the risk"),
            ask("Review on (YYYY-MM-DD)"), done="Deferral recorded.")


def _queue(auth) -> None:
    queue = run(tc.work_queue, auth)
    if queue is None:
        return
    for key, label in (("awaiting_approval", "Awaiting approval"),
                       ("approved_not_contacted", "Approved, contact not recorded"),
                       ("student_not_told", "Student not yet told"),
                       ("told_later", "Telling deferred")):
        print(f"\n{label}:")
        table(queue[key], (("use_id", "#", 5), ("student_id", "Student", 10),
                           ("contact_name", "Contact", 18), ("emergency", "Emerg", 5),
                           ("reason", "Why", 40)))


def run_menu(auth) -> None:
    try:
        staff = access.support_scope(auth) is None
    except PermissionError as exc:
        print(f"\n❌ {exc}")
        return
    if not staff:
        _student_menu(auth)
        return
    while True:
        print("\n" + "=" * 50 + "\n  TRUSTED CONTACTS\n" + "=" * 50)
        print("1. A student's contacts and uses\n2. Record / follow up a use\n"
              "3. Follow-up queue\n4. Record a withdrawal of consent\n0. Back")
        choice = input("Choice: ").strip()
        if choice == "0":
            return
        if choice == "1":
            _show(auth, ask("Student number"))
            pause()
        elif choice == "2":
            _use_action(auth, ask("Student number"))
        elif choice == "3":
            _queue(auth)
            pause()
        elif choice == "4":
            run(tc.set_consent, auth, False, student_id=ask("Student number"),
                done="Withdrawal recorded.")
