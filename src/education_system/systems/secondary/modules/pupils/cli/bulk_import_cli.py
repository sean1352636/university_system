"""Bulk Import in the terminal. Rules live in :mod:`modules.pupils.domain.bulk_import`."""

from __future__ import annotations

from pathlib import Path

from education_system.systems.secondary.modules.communication.domain import email_outbox as E
from education_system.systems.secondary.modules.pupils.domain import bulk_import as B
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (B.ValidationError, B.PermissionDenied, B.NotFound)


def _problem(e: Exception) -> None:
    prompts.problem(e, "Please fix:")


def _progress(i: int, n: int) -> None:
    print(f"\r  {i} of {n}…", end="" if i < n else "\n", flush=True)


def _path(prompt: str) -> Path | None:
    raw = _prompt(prompt).strip().strip("'\"")
    return Path(raw).expanduser() if raw else None


def menu(principal: Principal) -> None:
    if not (principal.can_open(B.MENU_LABEL) and principal.can_edit_pupils):
        print("\n  " + principal.denied_message(B.MENU_LABEL).replace("\n\n", "\n  "))
        _pause()
        return
    activity_log.record("bulk.open")
    while True:
        print("\n── Bulk Import ──")
        print("  1) Import pupils from CSV / Excel")
        print("  2) Export pupils to CSV")
        print("  3) Bulk update field")
        print("  4) Bulk delete pupils")
        print("  5) CSV format help")
        print("  6) Save a blank template")
        print("  7) Import history / undo")
        print("  0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", "", "q"}:
            return
        {"1": import_file, "2": export, "3": update, "4": delete, "5": lambda _p: _help(),
         "6": template, "7": history}.get(choice, lambda _p: None)(principal)


def _help() -> None:
    print("\n" + "\n".join("  " + line for line in B.FORMAT_HELP.splitlines()))
    _pause()


def template(principal: Principal) -> None:
    path = _path("  Save template as (e.g. ~/pupil_import.csv): ")
    if path:
        B.write_template(path)
        activity_log.record("bulk.template")
        print(f"  ✓ Saved {path}")


def import_file(principal: Principal) -> None:
    path = _path("  File to import (.csv or .xlsx): ")
    if not path:
        return
    try:
        pv = B.preview(B.read_file(path))
    except _ERRORS as e:
        _problem(e)
        _pause()
        return
    activity_log.record("bulk.preview", rows=len(pv.rows), ready=pv.count(B.READY, B.WARNING),
                        duplicates=pv.count(B.DUPLICATE), errors=pv.count(B.ERROR))
    print(f"\n── Preview: {pv.file_name} ── (nothing saved yet)")
    print(f"  {len(pv.rows)} rows: {pv.count(B.READY)} ready, {pv.count(B.WARNING)} ready but "
          f"worth checking, {pv.count(B.DUPLICATE)} possible duplicates, "
          f"{pv.count(B.ERROR)} with errors (skipped)")
    if pv.ignored_columns:
        print("  Columns ignored: " + ", ".join(pv.ignored_columns))
    for r in pv.rows:
        if r.status == B.READY:
            continue
        notes = ([f"same name and DOB as {r.existing}"] if r.existing else []) \
            + r.problems + r.warnings
        print(f"  line {r.line:>4}  {r.name[:26]:<26} {B.STATUS_LABELS[r.status]}: "
              + "; ".join(notes))
    dups = bool(pv.count(B.DUPLICATE)) and _yes(
        f"\n  Also add the {pv.count(B.DUPLICATE)} possible duplicates?")
    n = pv.count(B.READY, B.WARNING) + (pv.count(B.DUPLICATE) if dups else 0)
    if not n:
        print("  Nothing to import.")
        _pause()
        return
    logins = _yes("  Create logins and send welcome e-mails (as Add Pupil does)?")
    if not _yes(f"  Add {n} pupil{'s' if n != 1 else ''}?"):
        return
    try:
        result = B.run_import(pv, actor=principal, include_duplicates=dups,
                              create_logins=logins, progress=_progress)
    except _ERRORS as e:
        _problem(e)
        _pause()
        return
    print(f"\n  ✓ {len(result.created)} added (job #{result.job_id}).")
    for line, why in result.failed:
        print(f"  ✗ line {line}: {why}")
    for adm, why in result.login_errors:
        print(f"  ! {adm} login: {why} (use Create login on their profile)")
    if result.welcome_message_ids:
        try:
            for mid in result.welcome_message_ids:
                E.deliver(mid, principal=principal)
            print(f"  {len(result.welcome_message_ids)} welcome e-mail(s) handled "
                  f"({E.delivery_mode()} mode).")
        except Exception as e:  # noqa: BLE001 - saved; retry from Email
            print(f"  Welcome e-mails saved, but delivery failed: {e}. Retry from Email.")
    _pause()


def export(principal: Principal) -> None:
    raw = _prompt("  Pupils: 1) on roll  2) left  3) all  [1]: ") or "1"
    status = {"1": "on_roll", "2": "left", "3": None}.get(raw, "on_roll")
    yr = _prompt("  Year group (Enter for all): ")
    form = _prompt("  Form (Enter for all): ").upper() or None
    contacts = _yes("  Include parent contacts?")
    sensitive = _yes("  Include SEN, FSM, EAL and notes (sensitive)?")
    path = _path("  Save as (e.g. ~/pupils.csv): ")
    if not path:
        return
    try:
        n = B.export_csv(path, actor=principal, roll_status=status,
                         year_group=int(yr) if yr.isdigit() else None, form_group=form,
                         include_sensitive=sensitive, include_contacts=contacts)
    except _ERRORS as e:
        _problem(e)
        _pause()
        return
    except OSError as e:
        print(f"  Couldn't write the file: {e}")
        return
    print(f"  ✓ {n} pupil{'s' if n != 1 else ''} written to {path}. Keep it safe.")
    _pause()


def _choose_pupils(allow_groups: bool = True) -> list[P.Pupil]:
    if allow_groups:
        how = _prompt("  Pupils by 1) year group  2) form  3) admission numbers/UPNs: ")
        if how == "1":
            yr = _prompt("  Year group: ")
            return P.list_pupils(year_group=int(yr)) if yr.isdigit() else []
        if how == "2":
            form = _prompt("  Form: ").upper()
            return P.list_pupils(form_group=form) if form else []
        if how != "3":
            return []
    refs = _prompt("  Admission numbers / UPNs (comma or space separated): ")
    found, missing = B.resolve_refs(refs)
    for ref in missing:
        print(f"  Not found: {ref}")
    return found


def update(principal: Principal) -> None:
    keys = list(B.UPDATE_FIELDS)
    for i, k in enumerate(keys, 1):
        print(f"    {i}) {B.UPDATE_FIELDS[k]}")
    raw = _prompt("  Field: ")
    if not (raw.isdigit() and 1 <= int(raw) <= len(keys)):
        return
    key = keys[int(raw) - 1]
    hint = {"sen_status": "N/K/E", "fsm_eligible": "yes/no", "eal": "yes/no",
            "year_group": "7-11", "form_group": "blank clears"}[key]
    value = _prompt(f"  New value ({hint}): ")
    pupils = _choose_pupils()
    if not pupils:
        print("  No pupils chosen.")
        return
    try:
        checks = B.preview_update(key, value, pupils)
    except _ERRORS as e:
        _problem(e)
        return
    todo = [c for c in checks if c.changes]
    for c in checks:
        note = c.problem or ("" if c.changes else "already set")
        print(f"  {c.pupil.admission_no:<10} {c.pupil.display_name[:24]:<24} "
              f"{B._show(c.before):>8} → {B._show(c.after) if c.after is not None else '':<8} "
              f"{note}")
    print(f"\n  {len(todo)} will change. No 'record updated' e-mails are sent.")
    if not todo or not _yes("  Apply?"):
        return
    try:
        job_id, failed = B.run_update(key, value, [c.pupil.pupil_id for c in todo],
                                      actor=principal, progress=_progress)
    except _ERRORS as e:
        _problem(e)
        _pause()
        return
    print(f"  ✓ Done (job #{job_id}).")
    for adm, why in failed:
        print(f"  ✗ {adm}: {why}")
    _pause()


def delete(principal: Principal) -> None:
    print("\n  Only for records created in error - Undo in Import history is usually "
          "better, and leavers belong in Enrolment & Leavers. Each record is kept in the "
          "audit trail and loses its login.")
    pupils = _choose_pupils(allow_groups=False)
    if not pupils:
        return
    for p in pupils:
        print(f"  {p.admission_no:<10} {p.display_name[:26]:<26} Y{p.year_group} "
              f"{p.roll_status_label}")
    reason = _prompt("  Reason *: ")
    if _prompt(f"  Type DELETE to delete these {len(pupils)}: ").strip() != "DELETE":
        print("  Cancelled.")
        return
    try:
        job_id, failed = B.run_delete([p.pupil_id for p in pupils], actor=principal,
                                      reason=reason, progress=_progress)
    except _ERRORS as e:
        _problem(e)
        _pause()
        return
    print(f"  ✓ {len(pupils) - len(failed)} deleted (job #{job_id}).")
    for ref, why in failed:
        print(f"  ✗ {ref}: {why}")
    _pause()


def history(principal: Principal) -> None:
    jobs = B.list_jobs(50)
    if not jobs:
        print("\n  No jobs yet.")
        _pause()
        return
    print(f"\n  {'#':>4}  {'When':<19} {'By':<10} {'Type':<7} {'Done':>4} {'Fail':>4}  "
          f"{'Status':<14} What")
    for j in jobs:
        print(f"  {j.job_id:>4}  {j.created_at:<19} {j.created_by[:10]:<10} {j.kind:<7} "
              f"{j.done:>4} {j.failed:>4}  {j.status.replace('_', ' '):<14} {j.description}")
    raw = _prompt("\n  Job number to open (Enter to go back): ")
    job = B.get_job(int(raw)) if raw.isdigit() else None
    if job is None:
        return
    for it in B.job_items(job.job_id):
        d = it["detail"]
        detail = it["message"] or (f"{d['field']}: {d['from']} → {d['to']}"
                                   if "field" in d else "")
        print(f"  line {it['line'] or '-':>4}  {it['admission_no'] or '':<10} "
              f"{it['outcome']:<7} {detail}")
    if job.can_undo and _yes(f"\n  Undo job #{job.job_id}? (pupils changed since are left "
                             "alone)"):
        try:
            undone, kept = B.undo_job(job.job_id, actor=principal)
        except _ERRORS as e:
            _problem(e)
            _pause()
            return
        print(f"  ✓ {undone} undone.")
        for adm, why in kept:
            print(f"  - {adm}: {why}")
    _pause()
