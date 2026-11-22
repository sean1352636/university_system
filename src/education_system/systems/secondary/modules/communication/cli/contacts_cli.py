"""Parent/carer contacts in the terminal. Rules live in :mod:`modules.pupils.domain.contacts`.
When editing, Enter keeps the current value and ``-`` clears an optional field."""

from __future__ import annotations

from education_system.systems.secondary.modules.pupils.cli.pupils_cli import choose_pupil
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts.prompts import CLEAR
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes


def parent_contacts(principal: Principal) -> None:
    """Parent Contacts menu entry: pick a pupil, then manage their contacts."""
    pupil = choose_pupil("Pupil (admission no., UPN or name)")
    if pupil is not None:
        manage(principal, pupil.pupil_id)


def _print(pupil: P.Pupil, rows: list[C.Contact]) -> None:
    print(f"\n── Contacts for {pupil.display_name} ({pupil.admission_no}) ──")
    if not rows:
        print("  No contacts recorded.")
        return
    for i, c in enumerate(rows, 1):
        flags = []
        if c.parental_responsibility:
            flags.append("parental responsibility")
        flags.append("accepts e-mail" if c.receives_email else "no e-mail")
        print(f"  {i}) [{c.priority}] {c.full_name} ({c.relationship})")
        print(f"       E-mail: {c.email or '—'}   Phone: {c.phone or '—'}   "
              f"{', '.join(flags)}")
        if c.notes:
            print(f"       Notes: {c.notes}")
    if not any(c.can_be_emailed for c in rows):
        print("\n  ⚠ No contact accepts school e-mail.")


def manage(principal: Principal, pupil_id: int) -> None:
    while True:
        pupil = P.get_pupil(pupil_id)
        if pupil is None:
            print("\n  This pupil record no longer exists.")
            return
        rows = C.list_for_pupil(pupil_id)
        activity_log.record("contact.list", target=pupil.admission_no, results=len(rows))
        _print(pupil, rows)
        if principal.can_edit_pupils:
            print("\n  A) Add   E) Edit   D) Delete   0) Back")
        else:
            print("\n  0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in {"0", ""}:
            return
        if not principal.can_edit_pupils or choice not in {"a", "e", "d"}:
            print("  Invalid selection.")
            continue
        if choice == "a":
            _form(principal, pupil, None)
            continue
        if not rows:
            print("  There are no contacts to change.")
            continue
        n = _prompt("  Contact number: ")
        if not (n.isdigit() and 1 <= int(n) <= len(rows)):
            print("  Invalid selection.")
            continue
        contact = rows[int(n) - 1]
        if choice == "e":
            _form(principal, pupil, contact)
        elif _yes(f"  Remove {contact.full_name} as a contact?"):
            try:
                C.delete_contact(contact.contact_id, actor=principal)
                print("  Contact removed.")
                _deliver_parent_mail(principal, pupil.pupil_id)
            except Exception as e:  # noqa: BLE001
                print(f"  Could not delete: {e}")
        else:
            activity_log.record("contact.delete", target=pupil.admission_no,
                                outcome="cancelled", contact=contact.contact_id)


def _yn(label: str, current: bool) -> str | None:
    raw = _prompt(f"  {label} (y/n) [{'y' if current else 'n'}]: ").lower()
    return raw or None


def _form(principal: Principal, pupil: P.Pupil, contact: C.Contact | None) -> None:
    activity_log.record("contact.form.open", target=pupil.admission_no,
                        mode="edit" if contact else "add",
                        contact=contact.contact_id if contact else None)
    print(f"\n  {'Edit' if contact else 'New'} contact (Enter keeps a value, "
          f"'{CLEAR}' clears it). Relationships: {', '.join(C.RELATIONSHIPS)}")

    def cur(name, default=None):
        return getattr(contact, name) if contact else default

    data: dict = {}
    answers = {
        "full_name": _ask("Name", cur("full_name"), required=True),
        "relationship": _ask("Relationship", cur("relationship"), required=True),
        "priority": _ask(f"Priority 1-{C.MAX_PRIORITY}", cur("priority", 1)),
        "email": _ask("E-mail", cur("email")),
        "phone": _ask("Phone", cur("phone")),
        "parental_responsibility": _yn("Parental responsibility",
                                       cur("parental_responsibility", True)),
        "receives_email": _yn("Agrees to school e-mail", cur("receives_email", True)),
        "notes": _ask("Notes", cur("notes")),
    }
    for k, v in answers.items():
        if v is not None:
            data[k] = v
    if answers["relationship"]:
        match = [r for r in C.RELATIONSHIPS if r.lower() == answers["relationship"].lower()]
        if match:
            data["relationship"] = match[0]
    if not _yes("  Save this contact?"):
        activity_log.record("contact.form.cancel", target=pupil.admission_no)
        return
    try:
        if contact:
            C.update_contact(contact.contact_id, data, actor=principal)
        else:
            C.add_contact(pupil.pupil_id, data, actor=principal)
        print("  Saved.")
        _deliver_parent_mail(principal, pupil.pupil_id)
    except C.ValidationError as e:
        print("  Not saved:")
        for problem in e.problems:
            print(f"   - {problem}")
        _pause()
    except Exception as e:  # noqa: BLE001
        print(f"  Could not save: {e}")
        _pause()


def _deliver_parent_mail(principal: Principal, pupil_id: int) -> None:
    """Deliver any parent portal e-mail the change queued (a new login's
    welcome, or 'added to your portal')."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
    for mid in PA.undelivered(pupil_id=pupil_id):
        try:
            report = E.deliver(mid, principal=principal)
            print("  Parent portal e-mail: " + (", ".join(
                f"{n} {E.STATUS_LABELS[s].lower()}" for s, n in report.counts.items())
                or "nothing to deliver"))
        except Exception as e:  # noqa: BLE001 - it stays queued in the outbox
            print(f"  The parent portal e-mail is saved but couldn't be delivered: {e}")
