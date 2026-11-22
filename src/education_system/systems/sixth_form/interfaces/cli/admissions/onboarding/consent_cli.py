"""CLI: onboarding consent items backed by the GDPR consents register."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.onboarding.onboarding_cli import (
    READ_ONLY_MESSAGE,
    _input,
    _pause,
    _pick_checklist,
    _pick_from,
    _UserAbort,
    _yes_no,
)


def _user() -> str | None:
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or None
    except Exception:
        return None


def _show(checklist_id: int) -> list[data.ConsentLink]:
    links = data.consent_links(checklist_id)
    if not links:
        print("    This checklist has no consent items.")
    for i, link in enumerate(links, 1):
        print(f"    {i}) {link.item.task_name:<34} {link.purpose:<20} "
              f"{link.state:<9} item {link.item.status:<10} {link.detail}")
    return links


def consents_flow() -> None:
    """Show a checklist's consent tasks against the GDPR register.

    Viewing never writes (``consent_links`` is read-only); bringing the
    tasks in line with the register is the separate "Sync Consents with
    GDPR Records" menu option."""
    print("\n═══ Onboarding consents (GDPR register) ═══")
    c = _pick_checklist()
    links = _show(c.checklist_id)
    if not links:
        return _pause()
    if not data.can_write():
        print(f"\n  {READ_ONLY_MESSAGE}")
        return _pause()
    action = _pick_from("Action", ["Record granted", "Record refused",
                                   "Done"], default="Done")
    if action == "Done":
        return
    labels = [link.item.task_name for link in links]
    item = links[labels.index(_pick_from("Item", labels))].item
    granted = action == "Record granted"
    if not _yes_no(f"Record consent {'GRANTED' if granted else 'REFUSED'} "
                   f"for '{item.task_name}'?", default=True):
        raise _UserAbort
    given_by = _input("Given by (e.g. parent's name)") or None
    expires = _input("Expires (YYYY-MM-DD, optional)") or None
    notes = _input("Notes") or None
    try:
        link = data.record_consent(
            item.item_id, granted=granted, given_by=given_by,
            expires_date=expires, recorded_by=_user(), notes=notes)
        print("  ✓ Recorded in the GDPR register and the item updated")
    except (ValueError, PermissionError) as e:
        print(f"  ✗ {e}")
        return _pause()
    _report_followup(link)
    _pause()


def _report_followup(link: data.ConsentLink) -> None:
    """Open (or close) the follow-up task for a refused consent and say
    what happened."""
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        consent_followups,
    )
    try:
        follow = consent_followups.after_consent(link)
    except (ValueError, PermissionError) as e:
        print(f"  ✗ Follow-up task not checked: {e}")
        return
    if follow is None:
        print("  No follow-up task needed.")
    elif link.state == "Refused":
        print(f"  ! Follow-up task #{follow.item_id} '{follow.task_name}' "
              f"is open ({follow.status}) — tell the staff who need to know.")
    elif follow.is_done:
        print(f"  ✓ Follow-up task #{follow.item_id} '{follow.task_name}' "
              "ticked now consent is granted.")
    else:
        print(f"  Follow-up task #{follow.item_id} '{follow.task_name}' is "
              f"still {follow.status}.")
