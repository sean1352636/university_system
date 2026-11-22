"""E-mail in the terminal: outbox, message details, retry and compose.
Rules and delivery live in :mod:`modules.communication.domain.email_outbox`."""

from __future__ import annotations

from education_system.systems.secondary.modules.communication.domain import email_outbox as E
from education_system.systems.secondary.modules.pupils.cli.pupils_cli import choose_pupil
from education_system.systems.secondary.core.permissions import access
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes


def _report_text(report: E.DeliveryReport) -> str:
    return ", ".join(f"{n} {E.STATUS_LABELS[s].lower()}" for s, n in report.counts.items()) \
        or "nothing to deliver"


def menu(principal: Principal) -> None:
    while True:
        print("\n── Email ──")
        print("  Delivery: " + E.MODE_DESCRIPTIONS.get(E.delivery_mode(), E.delivery_mode()))
        print("  1) New email")
        print("  2) Sent messages")
        print("  0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", "", "q"}:
            return
        if choice == "1":
            compose(principal)
        elif choice == "2":
            outbox(principal)
        else:
            print("Invalid selection.")


def outbox(principal: Principal) -> None:
    while True:
        msgs = E.list_messages(actor=principal)
        activity_log.record("email.list", results=len(msgs))
        scope = "all school messages" if principal.role in access.EMAIL_ADMINS else "your messages"
        print(f"\n── Sent messages ({scope}) ──")
        if not msgs:
            print("  No messages yet.")
            _pause()
            return
        for m in msgs[:50]:
            print(f"  {m.message_id:>4}  {m.created_at}  {m.sender_username:<12} "
                  f"{m.subject[:40]:<40}  {m.status_text}")
        if len(msgs) > 50:
            print(f"  … {len(msgs) - 50} older not shown (open by number)")
        ref = _prompt("\n  Message number to open (Enter to go back): ")
        if not ref:
            return
        if not ref.isdigit():
            print("  Invalid number.")
            continue
        show(principal, int(ref))


def show(principal: Principal, message_id: int) -> None:
    while True:
        try:
            msg, recipients = E.get_message(message_id, actor=principal)
        except (E.PermissionDenied, E.NotFound) as e:
            print(f"\n  {e}")
            _pause()
            return
        print(f"\n═══ Email {msg.message_id}: {msg.subject} ═══")
        print(f"  From:   {msg.sender_username}\n  Sent:   {msg.created_at}")
        print(f"  To:     {msg.audience_label}\n  Status: {msg.status_text or '—'}")
        print("\n" + "\n".join("  " + line for line in msg.body.splitlines()))
        print(f"\n  Recipients ({len(recipients)}):")
        for r in recipients:
            line = (f"   {r['address']:<34} {(r['admission_no'] or ''):<10} "
                    f"{E.STATUS_LABELS.get(r['status'], r['status'])}")
            if r["last_error"]:
                line += f"  ({r['last_error']})"
            print(line)
        retryable = [r for r in recipients
                     if r["status"] == "failed" and r["attempts"] < E.MAX_ATTEMPTS]
        if not retryable:
            _pause()
            return
        if not _yes(f"\n  Retry {len(retryable)} failed recipient(s)?"):
            return
        if E.retry_failed(message_id, actor=principal):
            report = E.deliver(message_id, principal=principal)
            print("  Retry finished: " + _report_text(report))


def _choose_audience(principal: Principal) -> E.Audience | None:
    print("\n  Who is this for?")
    options = [("pupils", "Contacts of pupils I choose")]
    if principal.can_email_bulk:
        options += [("form", "A form group"), ("year", "A year group"),
                    ("school", "Whole school")]
    options.append(("none", "Only addresses I type"))
    for i, (_k, text) in enumerate(options, 1):
        print(f"  {i}) {text}")
    choice = _prompt("  Select: ")
    if not (choice.isdigit() and 1 <= int(choice) <= len(options)):
        return None
    kind = options[int(choice) - 1][0]
    aud = E.Audience(kind=kind)
    if kind == "pupils":
        while True:
            pupil = choose_pupil("Add a pupil (Enter when done)")
            if pupil is None:
                break
            if pupil.pupil_id not in aud.pupil_ids:
                aud.pupil_ids.append(pupil.pupil_id)
                print(f"  Added {pupil.display_name}. {len(aud.pupil_ids)} chosen.")
        if not aud.pupil_ids:
            print("  No pupils chosen.")
    elif kind == "form":
        forms = P.form_groups_in_use()
        print("  Forms: " + (", ".join(forms) or "none recorded"))
        aud.form_group = _prompt("  Form group: ") or None
    elif kind == "year":
        year = _prompt("  Year group (7-11): ")
        aud.year_group = int(year) if year.isdigit() else None
    aud.extra_addresses = E.parse_addresses(
        _prompt("  Other addresses (commas; Enter for none): "))
    return aud


def compose(principal: Principal) -> None:
    activity_log.record("email.compose.open")
    aud = _choose_audience(principal)
    if aud is None:
        activity_log.record("email.compose.cancel")
        return
    try:
        resolved = E.resolve(aud)
    except E.ValidationError as e:
        print(f"  {e}")
        return
    print(f"\n  Will go to {len(resolved.recipients)} address(es)"
          f"{f' for {resolved.pupils} pupil(s)' if resolved.pupils else ''}.")
    if resolved.pupils_without_email:
        print(f"  {len(resolved.pupils_without_email)} pupil(s) have no contact who accepts "
              "e-mail:")
        for p in resolved.pupils_without_email[:10]:
            print(f"   - {p.display_name} ({p.admission_no})")
    if resolved.invalid_addresses:
        print("  Not valid: " + ", ".join(resolved.invalid_addresses))
    subject = _prompt("\n  Subject: ")
    print("  Message - finish with a line containing only a full stop (.)")
    print("  Placeholders: " + ", ".join("{" + k + "}" for k in E.PLACEHOLDERS))
    lines: list[str] = []
    while True:
        try:
            line = input("  ")
        except EOFError:
            break
        if line.strip() == ".":
            break
        lines.append(line)
    body = "\n".join(lines)
    mode = E.delivery_mode()
    if mode != "live":
        print(f"\n  Note: {E.MODE_DESCRIPTIONS[mode]}")
    if not _yes(f"  Send to {len(resolved.recipients)} address(es)?"):
        activity_log.record("email.send", outcome="cancelled", audience=aud.kind,
                            recipients=len(resolved.recipients))
        return
    try:
        result = E.send_message(subject, body, aud, actor=principal)
    except E.PermissionDenied as e:
        print(f"  {e}")
        _pause()
        return
    except E.ValidationError as e:
        print("  Not sent:")
        for problem in e.problems:
            print(f"   - {problem}")
        _pause()
        return
    print(f"  Saved as email {result.message_id}. Delivering…")
    try:
        report = E.deliver(result.message_id, principal=principal)
        print("  " + _report_text(report))
    except Exception as e:  # noqa: BLE001
        print(f"  Delivery failed: {e}. Open it from Sent messages to retry.")
    _pause()
