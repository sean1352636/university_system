"""CLI flows for Sixth Form Integrations & Backups (CTF, LRS, DB backups)."""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domain.operations.integrations import (
    ctf,
)
from education_system.systems.sixth_form.infrastructure.integrations import (
    db_backup,
    lrs,
    store,
)

logger = logging.getLogger(__name__)

MENU_LABEL = "Integrations & Backups"


class _UserAbort(Exception):
    pass


def _input(prompt: str, *, default: str = "", allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)", default="y" if default else "n").lower()
    return raw in ("y", "yes")


# ── CTF ────────────────────────────────────────────────────────────

def _print_preview(pv: ctf.ImportPreview, resolutions: dict[int, str]) -> None:
    h = pv.file.header
    print(f"\n  {pv.file.file_name} — from {h.source_label}, CTF {h.version or '?'}")
    print(f"  {len(pv.rows)} pupil(s): {pv.count(ctf.STATUS_MATCHED)} matched, "
          f"{pv.count(ctf.STATUS_NEW)} new, {pv.count(ctf.STATUS_CONFLICT)} "
          f"conflict, {pv.count(ctf.STATUS_INVALID)} invalid")
    if pv.applied_import_id is not None:
        print(f"  ! Already applied as import #{pv.applied_import_id}")
    print(f"\n  {'#':>3}  {'UPN':<13}  {'Name':<28} {'DOB':<10}  {'Status':<8} "
          f"{'Student':<9} {'Resolve':<9} Notes")
    for r in pv.rows:
        p = r.pupil
        print(f"  {p.index + 1:>3}  {p.upn or '':<13}  {p.full_name[:28]:<28} "
              f"{p.dob or '':<10}  {r.status:<8} {r.student_id or '':<9} "
              f"{resolutions.get(p.index, ''):<9} {'; '.join(r.notes)}")


def ctf_import_flow() -> None:
    path = _input("Path to CTF XML file", allow_empty=False)
    pv = ctf.preview(path)
    resolutions: dict[int, str] = {}
    while True:
        _print_preview(pv, resolutions)
        print("\n  r) Resolve a pupil   d) Pupil detail   a) Apply   0) Back")
        choice = _input("Choice", default="0").lower()
        if choice == "0":
            return
        if choice in ("r", "d"):
            n = _input("Pupil #", allow_empty=False)
            if not n.isdigit() or not 1 <= int(n) <= len(pv.rows):
                print("    Out of range.")
                continue
            row = pv.rows[int(n) - 1]
            if choice == "d":
                _pupil_detail(row.pupil)
                continue
            if row.candidates:
                print(f"    Candidates: {', '.join(row.candidates)}")
            ans = _input("Student ID to merge into, 'new', 'skip' or blank to clear")
            if not ans:
                resolutions.pop(row.pupil.index, None)
            elif ans.lower() in (ctf.RESOLVE_NEW, ctf.RESOLVE_SKIP):
                resolutions[row.pupil.index] = ans.lower()
            else:
                resolutions[row.pupil.index] = ans.upper()
        elif choice == "a":
            if not _yes_no("Apply this file now"):
                continue
            res = ctf.apply(path, resolutions)
            print(f"\n  Import #{res.import_id}: {res.count('created')} created, "
                  f"{res.count('updated')} updated, {res.count('unchanged')} "
                  f"unchanged, {res.count('skipped')} skipped, "
                  f"{res.count('error')} error(s)")
            for o in res.outcomes:
                print(f"    {o.index + 1:>3}. {o.name:<28} {o.action:<9} "
                      f"{o.student_id or '':<9} {'; '.join(o.notes)}")
            _pause()
            return


def _pupil_detail(p: ctf.CTFPupil) -> None:
    print(f"\n  {p.full_name}  UPN {p.upn or '-'}  ULN {p.uln or '-'}  "
          f"DOB {p.dob or '-'}  Gender {p.gender_code or '-'}")
    if p.address:
        print("  Address: " + ", ".join(p.address.splitlines()))
    for c in p.contacts:
        print(f"  Contact {c.order or '-'}: {c.forename} {c.surname} "
              f"({c.relationship}) {', '.join(n for _t, n in c.phones)} {c.email or ''}")
    for a in p.attendance:
        print(f"  Attendance {a.year}: possible {a.possible}, authorised "
              f"{a.authorised}, unauthorised {a.unauthorised} "
              f"({a.percentage if a.percentage is not None else '-'}%)")
    for r in p.results:
        print(f"  {r.stage or '?'} {r.year or ''} {r.subject or '?'} "
              f"{r.component or r.method or ''}: {r.result or '-'}")
    print(f"  SEN records: {len(p.sen)}   FSM records: {len(p.fsm)}")
    _pause()


def ctf_history_flow() -> None:
    rows = ctf.list_imports()
    if not rows:
        print("\n  No CTF imports yet.")
        _pause()
        return
    print(f"\n  {'#':>4}  {'File':<36} {'Source':<24} {'Pupils':>6} {'New':>4} "
          f"{'Upd':>4} {'Skip':>4}  Applied")
    for r in rows:
        src = f"{r['source_la'] or '?'}/{r['source_estab'] or '?'}"
        print(f"  {r['import_id']:>4}  {r['file_name'][:36]:<36} {src:<24} "
              f"{r['pupil_count']:>6} {r['created_count']:>4} {r['updated_count']:>4} "
              f"{r['skipped_count']:>4}  {r['applied_at']} by {r['applied_by'] or '?'}")
    n = _input("Import # to list pupils (blank to go back)")
    if n.isdigit():
        for p in ctf.import_pupils(int(n)):
            print(f"    {p['upn'] or '':<13} {(p['forename'] or '') + ' ' + (p['surname'] or ''):<28} "
                  f"{p['action']:<9} {p['student_id'] or '':<9} {p['notes'] or ''}")
        _pause()


def ctf_pending_flow() -> None:
    rows = ctf.pending_results()
    print(f"\n  {len(rows)} KS4 result(s) not yet passed to a prior-attainment store")
    for r in rows:
        print(f"    {r['student_id']:<9} {r['student_name'][:26]:<26} {r['year'] or '':<5} "
              f"{r['subject'] or '':<10} {r['component'] or r['method'] or '':<8} "
              f"{r['result'] or ''}")
    if rows and ctf.prior_attainment_sink() is not None and _yes_no("Forward them now"):
        done, left = ctf.forward_pending_results()
        print(f"  Forwarded {done}; {left} still pending.")
    elif rows:
        print("  (No prior-attainment store is available yet.)")
    _pause()


def ctf_export_flow() -> None:
    leavers = ctf.list_leavers()
    if not leavers:
        print("\n  No leavers (students with status 'Left').")
        _pause()
        return
    for i, s in enumerate(leavers, 1):
        print(f"  {i:>3}) {s.student_id:<9} {s.full_name:<30} {s.date_of_birth or ''}")
    n = _input(f"Pick #1..{len(leavers)}", allow_empty=False)
    if not n.isdigit() or not 1 <= int(n) <= len(leavers):
        print("    Out of range.")
        return
    print("  Destination: LA + establishment number; XXX/XXXX if unknown, "
          "MMM/MMMM if leaving England/Wales.")
    la = _input("Destination LA", default=ctf.UNKNOWN_DEST_LA)
    estab = _input("Destination establishment", default=ctf.UNKNOWN_DEST_ESTAB)
    res = ctf.export_leaver(leavers[int(n) - 1].student_id, dest_la=la,
                            dest_estab=estab)
    print(f"\n  ✓ CTF written to {res.path}")
    _pause()


# ── LRS ────────────────────────────────────────────────────────────

def lrs_status_flow() -> None:
    _ok, text = lrs.config_status()
    print(f"\n  {text}")
    _pause()


def lrs_missing_flow() -> None:
    missing = lrs.students_missing_uln()
    bad = lrs.students_with_invalid_uln()
    print(f"\n  {len(missing)} student(s) with no ULN:")
    for s in missing:
        print(f"    {s.student_id:<9} {s.full_name:<30} {s.date_of_birth or '':<10} {s.status}")
    print(f"\n  {len(bad)} student(s) whose ULN fails the check digit:")
    for s in bad:
        print(f"    {s.student_id:<9} {s.full_name:<30} {s.uln:<11} {lrs.explain_uln(s.uln)}")
    _pause()


def lrs_find_flow() -> None:
    sid = _input("Student ID", allow_empty=False).upper()
    try:
        resp = lrs.find_uln_for_student(sid)
    except lrs.LRSNotConfigured as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  LRS: {resp.description} ({resp.code})")
    for i, l in enumerate(resp.learners, 1):
        print(f"    {i}) ULN {l.uln}  {l.given_name or ''} {l.family_name or ''}  "
              f"DOB {l.date_of_birth or '?'}  {l.postcode or ''}")
    if resp.learners:
        n = _input("Record which ULN # (blank for none)")
        if n.isdigit() and 1 <= int(n) <= len(resp.learners):
            lrs.apply_uln(sid, resp.learners[int(n) - 1].uln)
            print("  ✓ ULN recorded")
    _pause()


def lrs_verify_flow() -> None:
    sid = _input("Student ID", allow_empty=False).upper()
    try:
        resp = lrs.verify_student_uln(sid)
    except lrs.LRSNotConfigured as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  LRS: {resp.description} ({resp.code})")
    _pause()


def uln_enter_flow() -> None:
    sid = _input("Student ID", allow_empty=False).upper()
    uln = _input("ULN (10 digits)", allow_empty=False)
    print(f"  {lrs.explain_uln(uln)}")
    if lrs.is_valid_uln(uln):
        lrs.apply_uln(sid, uln)
        print("  ✓ ULN recorded")
    _pause()


def uln_check_flow() -> None:
    uln = _input("ULN to check", allow_empty=False)
    print(f"  {lrs.explain_uln(uln)}")
    _pause()


def lrs_log_flow() -> None:
    rows = lrs.list_requests(50)
    if not rows:
        print("\n  No LRS requests logged.")
    for r in rows:
        print(f"  {r['requested_at']}  {r['operation']:<22} {r['student_id'] or '':<9} "
              f"{r['response_code'] or '':<9} {r['response_text'] or r['error'] or ''}")
    _pause()


# ── Backups ────────────────────────────────────────────────────────

def backup_now_flow() -> None:
    print(f"\n  Backing up to {db_backup.backup_dir()}")
    for r in db_backup.backup_all():
        print(f"  ✓ {r.source.name} -> {r.backup.name} ({r.backup.size_label}), "
              f"integrity {r.integrity}, rotated out {len(r.removed)}")
    _pause()


def _list_backups() -> list[db_backup.BackupInfo]:
    rows = db_backup.list_backups()
    print(f"\n  Databases: " + ", ".join(
        f"{p} ({len(n)} constant(s))" for p, n in db_backup.database_constants().items()))
    print(f"  Backups in {db_backup.backup_dir()} (keep {db_backup.keep_count()}):")
    for i, b in enumerate(rows, 1):
        print(f"  {i:>3}) {b.name:<50} {b.created:%Y-%m-%d %H:%M:%S}  "
              f"{b.label or '':<12} {b.size_label}")
    if not rows:
        print("    (none)")
    return rows


def backup_list_flow() -> None:
    _list_backups()
    _pause()


def _pick_backup() -> db_backup.BackupInfo | None:
    rows = _list_backups()
    if not rows:
        return None
    n = _input(f"Pick #1..{len(rows)}", allow_empty=False)
    if not n.isdigit() or not 1 <= int(n) <= len(rows):
        print("    Out of range.")
        return None
    return rows[int(n) - 1]


def _print_restore_preview(pv: db_backup.RestorePreview) -> None:
    print(f"\n  Backup:    {pv.backup.path} ({pv.backup.size_label})")
    print(f"  Target:    {pv.target}")
    print(f"  Integrity: {pv.integrity}")
    print(f"  Tables:    {len(pv.backup_counts)} in backup, {len(pv.current_counts)} now")
    diffs = pv.differences()
    if not diffs:
        print("  Row counts identical in every table.")
    for name, now, then in diffs:
        print(f"    {name:<40} now {now if now is not None else '-':>8}  "
              f"backup {then if then is not None else '-':>8}")


def restore_preview_flow() -> None:
    b = _pick_backup()
    if b is None:
        _pause()
        return
    _print_restore_preview(db_backup.restore_preview(b))
    _pause()


def restore_flow() -> None:
    b = _pick_backup()
    if b is None:
        _pause()
        return
    pv = db_backup.restore_preview(b)
    _print_restore_preview(pv)
    if pv.integrity != "ok":
        print("\n  ✗ This backup failed its integrity check and cannot be restored.")
        _pause()
        return
    phrase = db_backup.confirmation_phrase(b)
    print(f"\n  Restoring replaces ALL data in {pv.target}.")
    print("  A safety copy of the current database is taken first.")
    typed = _input(f"Type exactly '{phrase}' to continue")
    res = db_backup.restore(b, typed)
    print(f"\n  ✓ Restored from {res.restored_from.name}; safety copy "
          f"{res.safety_backup}; integrity {res.integrity}")
    print("  Restart the application now.")
    _pause()


def retention_flow() -> None:
    n = _input("Keep how many backups per database", default=str(db_backup.keep_count()))
    if not n.isdigit():
        print("    Enter a number.")
        return
    db_backup.set_keep_count(int(n))
    print("  ✓ Saved")
    _pause()


# ── Settings ───────────────────────────────────────────────────────

_SETTINGS = (
    ("school_la", "College LA number (3 digits)"),
    ("school_estab", "College establishment number (4 digits)"),
    ("school_name", "College name"),
    ("lrs_endpoint", "LRS endpoint URL"),
    ("lrs_ukprn", "LRS UKPRN"),
    ("lrs_username", "LRS username"),
    ("lrs_vendor_id", "LRS vendor id"),
)


def settings_flow() -> None:
    who = store.require("ADMIN", "integration settings")
    print("\n  (The LRS password is read from LRS_PASSWORD in the environment only.)")
    for key, label in _SETTINGS:
        value = _input(label, default=store.get_setting(key))
        store.set_setting(key, value, by=who)
    print("  ✓ Saved")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("CTF: import (preview + apply)", ctf_import_flow),
    ("CTF: import history",           ctf_history_flow),
    ("CTF: pending KS4 results",      ctf_pending_flow),
    ("CTF: export a leaver",          ctf_export_flow),
    ("─" * 6,                         lambda: None),
    ("LRS: configuration status",     lrs_status_flow),
    ("LRS: students missing / invalid ULN", lrs_missing_flow),
    ("LRS: find ULN for a student",   lrs_find_flow),
    ("LRS: verify a student's ULN",   lrs_verify_flow),
    ("ULN: enter manually",           uln_enter_flow),
    ("ULN: check digit calculator",   uln_check_flow),
    ("LRS: request log",              lrs_log_flow),
    ("─" * 6,                         lambda: None),
    ("Backups: back up now",          backup_now_flow),
    ("Backups: list",                 backup_list_flow),
    ("Backups: restore preview",      restore_preview_flow),
    ("Backups: restore",              restore_flow),
    ("Backups: retention",            retention_flow),
    ("─" * 6,                         lambda: None),
    ("Settings",                      settings_flow),
]


def run() -> None:
    while True:
        print(f"\n── {MENU_LABEL} ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
                print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except (ValueError, PermissionError, RuntimeError) as e:
            # ValidationError / AccessDenied / LRSNotConfigured / LRSError.
            print(f"\n  ✗ {e}")
            _pause()
        except Exception as e:
            logger.exception("Integrations CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != MENU_LABEL:
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Integrations CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
