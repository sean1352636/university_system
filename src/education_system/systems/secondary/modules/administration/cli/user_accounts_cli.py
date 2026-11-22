"""User Accounts (admin) in the terminal: pupil logins, parent logins made
from contacts, and logins linked by hand. Rules live in
:mod:`modules.portals.domain.portal_accounts`."""

from __future__ import annotations

from education_system.systems.secondary.modules.communication.domain import email_outbox as E
from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
from education_system.systems.secondary.modules.pupils.domain import pupil_accounts
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (PA.ValidationError, PA.PermissionDenied, PA.NotFound)


_problem = prompts.problem


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("user_accounts.view")
        print("\n── User Accounts ──")
        waiting = len(PA.undelivered())
        print("   1) Pupil logins\n   2) Parent logins\n   3) Linked logins"
              "\n   4) Create parent logins from contacts"
              f"\n   5) Send waiting parent e-mails ({waiting})"
              "\n   6) Link a login to a pupil\n   7) Remove a link\n   0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", ""}:
            return
        try:
            {"1": _pupils, "2": _parents, "3": _links, "4": lambda: _sync(principal),
             "5": lambda: _send(principal), "6": lambda: _link(principal),
             "7": lambda: _unlink(principal)}.get(choice, lambda: print("  Invalid selection."))()
        except _ERRORS as e:
            _problem(e)


def _pupils() -> None:
    accts = {a.pupil_id: a for a in pupil_accounts.list_accounts()}
    rows = P.list_pupils()
    print(f"\n  {'Adm no':<10} {'Pupil':<24} {'Yr':<3} {'Username':<16} {'Status':<9} E-mail")
    for p in rows:
        a = accts.get(p.pupil_id)
        print(f"  {p.admission_no:<10} {p.display_name[:24]:<24} {p.year_group:<3} "
              f"{(a.username if a else ''):<16} {(a.status if a else 'no login'):<9} "
              f"{a.school_email if a else ''}")
    print(f"\n  {sum(1 for p in rows if p.pupil_id not in accts)} pupil(s) without a login")
    _pause()


def _parents() -> None:
    rows = PA.parent_logins()
    if not rows:
        print("  No parent logins yet - option 4 creates them from contacts.")
    for r in rows:
        kids = ", ".join(f"{k.pupil_name} ({k.admission_no})" for k in r["children"])
        print(f"  {r['username']:<34} {(r['display_name'] or '')[:22]:<22} {kids or 'none now'}")
    _pause()


def _links() -> None:
    rows = PA.list_links(include_removed=_yes("  Include removed links?"))
    print(f"\n  {'ID':<5} {'Username':<30} {'As':<7} {'Pupil':<24} {'From':<8} Status")
    for x in rows:
        print(f"  {x.link_id:<5} {x.username[:30]:<30} {x.kind:<7} {x.pupil_name[:24]:<24} "
              f"{('contact' if x.source == 'contact' else 'by hand'):<8} {x.status}")
    _pause()


def _sync(principal: Principal) -> None:
    if not _yes("  Create a parent login for every contact with parental responsibility "
                "and an e-mail, and e-mail them?"):
        return
    counts = PA.sync_all(actor=principal)
    print("  " + ", ".join(f"{k}: {n}" for k, n in counts.items() if n) or "  Nothing to do.")
    _send(principal)


def _send(principal: Principal) -> None:
    ids = PA.undelivered()
    if not ids:
        print("  No parent portal e-mails are waiting.")
        return
    for mid in ids:
        try:
            report = E.deliver(mid, principal=principal)
            print(f"  Message {mid}: " + (", ".join(
                f"{n} {E.STATUS_LABELS[s].lower()}" for s, n in report.counts.items())
                or "nothing to deliver"))
        except Exception as e:  # noqa: BLE001 - stays queued
            print(f"  Message {mid} couldn't be delivered: {e}")


def _link(principal: Principal) -> None:
    username = _prompt("  Username: ")
    ref = _prompt("  Pupil (admission number or UPN): ")
    pupil = P.find_by_reference(ref) if ref else None
    if not username or pupil is None:
        print("  Give a username and a pupil's admission number.")
        return
    kind = "pupil" if _prompt("  Link as (P)arent or the pu(Y)il? [P]: ").lower() in {
        "y", "pupil"} else "parent"
    link = PA.link_login(username, pupil.pupil_id, kind, actor=principal)
    print(f"  ✓ {link.username} can now see {link.pupil_name} in the {link.kind} portal")


def _unlink(principal: Principal) -> None:
    n = _prompt("  Link ID (see option 3): ")
    if not n.isdigit():
        return
    x = PA.get_link(int(n))
    if _yes(f"  Stop {x.username} seeing {x.pupil_name}?"):
        PA.unlink(x.link_id, actor=principal)
        print("  ✓ Removed")
