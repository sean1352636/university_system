"""CLI flows for records / lifecycle bulk operations.

Split out of ``bulk_operations_cli.py``, which re-exports every name here.
"""

from __future__ import annotations

from datetime import date as _date

from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_behaviour as bulk_ops_behaviour
from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_records as bulk_ops_records
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import SAFE_STUDENT_FIELDS
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


def bulk_update_field() -> None:
    print("\n═══ Bulk Update Student Field ═══")
    try:
        sids = _pick_students()
        field = _pick_from("Field", list(SAFE_STUDENT_FIELDS))
        value = _input(f"New value for {field}")
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_behaviour.bulk_update_student(
            sids, field=field, value=value or None, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_archive_flow() -> None:
    print("\n═══ Bulk Archive Students → Alumni ═══")
    try:
        sids = _pick_students()
        year = _input("Leaving year (YYYY)",
                       default=str(_date.today().year))
        date_str = _input("Leaving date (YYYY-MM-DD)",
                            default=_date.today().isoformat())
        from education_system.systems.sixth_form.domain.learners.alumni.models import (
            DESTINATION_TYPES,
            LEAVING_REASONS,
            DEFAULT_DESTINATION,
            DEFAULT_LEAVING_REASON,
        )
        reason = _pick_from("Leaving reason", list(LEAVING_REASONS),
                              default=DEFAULT_LEAVING_REASON)
        dest = _pick_from("Destination", list(DESTINATION_TYPES),
                            default=DEFAULT_DESTINATION)
        delete = _yes_no(
            "Also delete the student rows? "
            "(history/links cascade-remove)", default=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not dry and delete and not _yes_no(
            f"This will DELETE {len(sids)} student row(s). Continue?",
            default=False):
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_records.bulk_archive_to_alumni(
            sids, leaving_year=year, leaving_date=date_str,
            leaving_reason=reason, destination_type=dest,
            delete_students=delete, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_promote_flow() -> None:
    print("\n═══ Bulk Promote Year Group ═══")
    try:
        sids = _pick_students()
        year = _input("New academic year (e.g. 2026/27)",
                         allow_empty=False)
        bump = _yes_no("Bump year_group by +1?", default=True)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_records.bulk_promote_year_group(
            sids, new_academic_year=year, bump_year_group=bump,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_leavers_flow() -> None:
    print("\n═══ Bulk Mark Leavers ═══")
    try:
        sids = _pick_students()
        date_str = _input("Leaving date",
                            default=_date.today().isoformat())
        reason = _input("Leaving reason (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_records.bulk_mark_leavers(
            sids, leaving_date=date_str, leaving_reason=reason,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_reinstate_flow() -> None:
    print("\n═══ Bulk Reinstate Alumni ═══")
    try:
        raw = _input("Alumni ids (comma-separated)",
                       allow_empty=False)
        ids = [int(t) for t in raw.replace(" ", ",").split(",") if t]
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = bulk_ops_records.bulk_reinstate_alumni(ids, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_gdpr_flow() -> None:
    print("\n═══ Bulk GDPR Redact ═══")
    try:
        sids = _pick_students()
        raw = _input("Fields to clear (comma; blank = defaults)") or ""
        fields = [f.strip() for f in raw.split(",") if f.strip()] or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_records.bulk_gdpr_redact(sids, fields=fields, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_export_records_flow() -> None:
    print("\n═══ Bulk Export Student Records ═══")
    try:
        sids = _pick_students()
        path = _input("Output CSV path", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_records.bulk_export_student_records(
            sids, output_path=path, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_anonymise_flow() -> None:
    print("\n═══ Bulk Anonymise Alumni ═══")
    try:
        raw = _input("Alumni ids (comma-separated)",
                       allow_empty=False)
        ids = [int(t) for t in raw.replace(" ", ",").split(",") if t]
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = bulk_ops_records.bulk_anonymise_alumni(ids, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_inventory_flow() -> None:
    print("\n═══ Bulk Assign Inventory ═══")
    try:
        sids = _pick_students()
        kind = _pick_from("Kind",
                            list(bulk_ops_records.VALID_INVENTORY_KINDS),
                            default="Locker")
        start = int(_input("Starting number", default="1"))
        prefix = _input("Prefix (optional)") or ""
        pad = int(_input("Zero-pad digits", default="4"))
        by = _input("Assigned by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = bulk_ops_records.bulk_assign_inventory(
            sids, kind=kind, starting_number=start, prefix=prefix,
            pad=pad, assigned_by=by, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_photos_flow() -> None:
    print("\n═══ Bulk Upload Photos ═══")
    try:
        zip_path = _input("ZIP path", allow_empty=False)
        out_dir = _input("Output directory", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_records.bulk_upload_photos(
            zip_path, output_dir=out_dir, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_contacts_csv_flow() -> None:
    print("\n═══ Bulk Import Emergency Contacts CSV ═══")
    print("  Required: student_id")
    print("  Optional: phone, emergency_contact_name,")
    print("            emergency_contact_phone, emergency_contact_relation")
    try:
        path = _input("CSV path", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_records.bulk_import_contacts_csv(path, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_pwreset_flag_flow() -> None:
    print("\n═══ Bulk Force Password Reset ═══")
    try:
        sids = _pick_students()
        clear = _yes_no("Clear the flag (instead of setting it)?",
                          default=False)
        reason = _input("Reason (optional)") or None
        by = _input("Flagged by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_records.bulk_force_password_reset(
            sids, reason=reason, flagged_by=by, clear=clear,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)
