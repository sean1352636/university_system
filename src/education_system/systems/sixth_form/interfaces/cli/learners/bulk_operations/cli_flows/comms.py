"""CLI flows for communication bulk operations.

Split out of ``bulk_operations_cli.py``, which re-exports every name here.
"""

from __future__ import annotations

from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_comms as bulk_ops_comms
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import ValidationError

from education_system.systems.sixth_form.interfaces.cli.learners.bulk_operations.cli_flows.prompts import (
    _input,
    _pause,
    _pick_from,
    _pick_students,
    _print_result,
    _UserAbort,
    _yes_no,
)


def bulk_message_flow() -> None:
    print("\n═══ Bulk Message Students ═══")
    try:
        sids = _pick_students()
        subject = _input("Subject", allow_empty=False)
        body = _input("Body", allow_empty=False)
        channel = _pick_from("Channel", ["Email", "SMS", "Letter",
                                            "Phone Call", "In Person",
                                            "System"],
                                default="Email")
        category = _input("Category", default="General")
        priority = _pick_from("Priority", ["Low", "Normal", "High",
                                              "Urgent"],
                                default="Normal")
        status = _pick_from("Status", ["Draft", "Queued", "Sent"],
                              default="Sent")
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_comms.bulk_message(
            sids, subject=subject, body=body, channel=channel,
            category=category, priority=priority, status=status,
            dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_sms_flow() -> None:
    print("\n═══ Bulk SMS ═══")
    try:
        sids = _pick_students()
        body = _input("Body", allow_empty=False)
        subject = _input("Subject (audit)", default="SMS")
        sender = _input("Sender staff id") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_comms.bulk_send_sms(sids, body=body, subject=subject,
                                 sender_staff_id=sender, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_letters_flow() -> None:
    print("\n═══ Bulk Send Templated Letters ═══")
    from education_system.systems.sixth_form.domains.communications.domain.letter_templates import (
        letter_templates as _lt,
    )
    templates = _lt.list_templates()
    if not templates:
        print("  No letter templates available.")
        _pause()
        return
    print("\n  Templates:")
    for i, t in enumerate(templates, 1):
        print(f"    {i:>3}) #{t.template_id}  {t.name}")
    try:
        raw = _input("Pick #", allow_empty=False)
        if not raw.isdigit() or not (1 <= int(raw) <= len(templates)):
            print("  Bad pick.")
            _pause()
            return
        tmpl = templates[int(raw) - 1]
        sids = _pick_students()
        ctx_raw = _input(
            "Extra context (k=v, comma-separated; optional)") or ""
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ctx: dict[str, str] = {}
    for pair in ctx_raw.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            ctx[k.strip()] = v.strip()
    try:
        r = bulk_ops_comms.bulk_send_letters(
            sids, template_id=tmpl.template_id,
            extra_context=ctx, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_meeting_invites_flow() -> None:
    print("\n═══ Bulk Parents-Evening Invites ═══")
    from education_system.systems.sixth_form.domains.communications.domain.parents_evenings import (
        parents_evenings as _pe,
    )
    events = _pe.list_events()
    if not events:
        print("  No parents-evening events.")
        _pause()
        return
    print("\n  Events:")
    for i, e in enumerate(events, 1):
        print(f"    {i:>3}) #{e.event_id}  {e.event_date}  {e.title}")
    try:
        raw = _input("Pick #", allow_empty=False)
        if not raw.isdigit() or not (1 <= int(raw) <= len(events)):
            print("  Bad pick.")
            _pause()
            return
        ev = events[int(raw) - 1]
        sids = _pick_students()
        link = _input("Booking link (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_comms.bulk_meeting_invites(
            sids, event_id=ev.event_id,
            booking_link=link, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_ucas_reminders_flow() -> None:
    print("\n═══ Bulk UCAS Reference Reminders ═══")
    try:
        sids = _pick_students()
        referee = _input("Override referee email (optional)") or None
        deadline = _input("Deadline (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_comms.bulk_ucas_reference_reminders(
            sids, referee_email=referee, deadline=deadline,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_password_reset_flow() -> None:
    print("\n═══ Bulk Password / MFA Emails ═══")
    try:
        sids = _pick_students()
        mfa = _yes_no("MFA enrolment (instead of password reset)?",
                       default=False)
        url = _input("Reset URL (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_comms.bulk_password_reset_emails(
            sids, reset_url=url, mfa_enrolment=mfa, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_schedule_msg_flow() -> None:
    print("\n═══ Bulk Schedule Message ═══")
    try:
        sids = _pick_students()
        subject = _input("Subject", allow_empty=False)
        body = _input("Body", allow_empty=False)
        send_at = _input("Send at (YYYY-MM-DD HH:MM)", allow_empty=False)
        channel = _pick_from("Channel",
                                ["Email", "SMS", "Letter", "Portal"],
                                default="Email")
        category = _input("Category", default="General")
        priority = _pick_from("Priority",
                                ["Low", "Normal", "High", "Urgent"],
                                default="Normal")
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_comms.bulk_schedule_message(
            sids, subject=subject, body=body, send_at=send_at,
            channel=channel, category=category, priority=priority,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)
