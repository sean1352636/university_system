"""CLI flows for Sixth Form Data Export."""

from __future__ import annotations

import logging
from datetime import datetime as _dt
from pathlib import Path
from typing import Any, Callable
from education_system.systems.sixth_form.domain.operations.reporting.data_export import (
    data_export as data,
)
from education_system.systems.sixth_form.domain.operations.reporting.data_export.data_export import (
    DEFAULT_FORMAT,
    FORMATS,
    JOB_STATUSES,
    Preset,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
           allow_empty: bool = True) -> str:
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


def _pick_from(label: str, options: list[str],
               default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                     default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel').")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _yes_no(prompt: str, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)", default="y" if default else "n")
    return raw.lower() in ("y", "yes")


def _pick_preset() -> Preset:
    presets = data.list_presets()
    if not presets:
        raise _UserAbort
    print("\n  Presets:")
    for i, p in enumerate(presets, 1):
        kind = "built-in" if p.is_builtin else "user"
        print(f"    {i:>3}) {p.name:<28} [{kind}]  "
              f"— {p.description[:50]}")
        print(f"          datasets: {len(p.datasets)} "
              f"({', '.join(p.datasets[:4])}"
              f"{'…' if len(p.datasets) > 4 else ''})")
    while True:
        raw = _input(f"Pick #1..{len(presets)} or key",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(presets):
                return presets[n - 1]
        p = data.get_preset(raw)
        if p is not None:
            return p
        print("    No matching preset.")


def _pick_datasets(default: list[str] | None = None) -> list[str]:
    all_ds = data.available_datasets()
    print(f"\n  Datasets ({len(all_ds)}):")
    for i, (k, label) in enumerate(all_ds, 1):
        marker = " *" if default and k in default else "  "
        print(f"    {marker}{i:>3}) {label:<32}  ({k})")
    raw = _input(
        "Comma-separated #s/keys (blank=keep current, '*' = all)",
        default="")
    if not raw:
        return list(default or [])
    if raw.strip() == "*":
        return [k for k, _ in all_ds]
    out: list[str] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok.isdigit():
            n = int(tok)
            if 1 <= n <= len(all_ds):
                out.append(all_ds[n - 1][0])
            else:
                print(f"    (skipping out-of-range #{tok})")
        else:
            out.append(tok)
    return out


# ── Print helpers ──────────────────────────────────────────────────

def _print_presets(rows: list[Preset]) -> None:
    if not rows:
        print("\n  (no presets)")
        return
    print()
    print(f"  {'#':>4}  {'Key':<22}  {'Name':<28}  "
          f"{'Kind':<8}  {'Sets':>5}  Description")
    print("  " + "-" * 110)
    for p in rows:
        print(f"  {(p.preset_id or 0):>4}  {p.key[:22]:<22}  "
              f"{p.name[:28]:<28}  "
              f"{'builtin' if p.is_builtin else 'user':<8}  "
              f"{len(p.datasets):>5}  {p.description[:36]}")
    print(f"\n  {len(rows)} preset(s).")


def _print_jobs(rows: list[data.ExportJob]) -> None:
    if not rows:
        print("\n  (no jobs)")
        return
    print()
    print(f"  {'#':>4}  {'Started':<19}  {'Preset':<22}  "
          f"{'Status':<10}  {'Files':>5}  {'Rows':>8}  "
          f"{'Bytes':>10}  Output")
    print("  " + "-" * 130)
    for j in rows:
        print(f"  {j.job_id:>4}  {j.started_at:<19}  "
              f"{j.preset_name[:22]:<22}  {j.status:<10}  "
              f"{j.files_total:>5}  {j.rows_total:>8}  "
              f"{j.bytes_total:>10}  {j.output_dir[:32]}")
    print(f"\n  {len(rows)} job(s).")


def _print_job(j: data.ExportJob) -> None:
    print()
    print(f"    Job #{j.job_id}")
    print(f"    Preset       : {j.preset_name} ({j.preset_key})")
    print(f"    Output dir   : {j.output_dir}")
    print(f"    Format       : {j.fmt}")
    print(f"    Status       : {j.status}")
    print(f"    Started      : {j.started_at}")
    print(f"    Finished     : {j.finished_at or '—'}")
    print(f"    Files written: {j.files_total}")
    print(f"    Rows written : {j.rows_total}")
    print(f"    Bytes written: {j.bytes_total}")
    if j.zipped:
        print(f"    Archive      : {j.archive_path or '(not produced)'}")
    if j.run_by:
        print(f"    Run by       : {j.run_by}")
    if j.notes:
        print(f"    Notes        : {j.notes}")
    if j.files:
        print()
        print(f"    {'Dataset':<24}  {'Rows':>6}  {'Cols':>4}  "
              f"{'Bytes':>10}  Path / Error")
        print("    " + "-" * 96)
        for r in j.files:
            err = r.error or ""
            tail = r.file_path or err
            print(f"    {r.dataset_key[:24]:<24}  {r.row_count:>6}  "
                  f"{r.column_count:>4}  {r.bytes_written:>10}  "
                  f"{tail[:48]}")


# ── Flows ──────────────────────────────────────────────────────────

def list_presets_flow() -> None:
    print("\n═══ Presets ═══")
    _print_presets(data.list_presets())
    _pause()


def view_preset_flow() -> None:
    print("\n═══ View Preset ═══")
    try:
        p = _pick_preset()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print()
    print(f"    Key         : {p.key}")
    print(f"    Name        : {p.name}")
    print(f"    Kind        : "
          f"{'built-in' if p.is_builtin else 'user'}")
    if p.preset_id:
        print(f"    ID          : {p.preset_id}")
    print(f"    Description : {p.description}")
    print(f"    Datasets    : {len(p.datasets)}")
    for d in p.datasets:
        print(f"      - {d}")
    _pause()


def new_preset_flow() -> None:
    print("\n═══ New Preset ═══")
    try:
        key = _input("Key (alphanumeric / _-)", allow_empty=False)
        name = _input("Name", allow_empty=False)
        desc = _input("Description (optional)")
        ds = _pick_datasets()
        by = _input("Created by (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        p = data.create_preset({
            "key": key, "name": name,
            "description": desc, "datasets": ds,
            "created_by": by or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created preset #{p.preset_id} ({p.key})")
    _pause()


def edit_preset_flow() -> None:
    print("\n═══ Edit Preset ═══")
    try:
        pid = int(_input("Preset ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_preset(pid)
    if existing is None or existing.is_builtin:
        print(f"  ✗ No editable preset #{pid}")
        _pause()
        return
    try:
        key = _input("Key", default=existing.key, allow_empty=False)
        name = _input("Name", default=existing.name, allow_empty=False)
        desc = _input("Description",
                       default=existing.description or "")
        ds = _pick_datasets(default=existing.datasets)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_preset(pid, {
            "key": key, "name": name,
            "description": desc, "datasets": ds,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{pid}")
    _pause()


def delete_preset_flow() -> None:
    print("\n═══ Delete Preset ═══")
    try:
        pid = int(_input("Preset ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_preset(pid)
    if existing is None or existing.is_builtin:
        print(f"  ✗ No editable preset #{pid}")
        _pause()
        return
    if _input(f"Delete preset #{pid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_preset(pid):
        print(f"\n  ✓ Deleted #{pid}")
    _pause()


def run_export_flow() -> None:
    print("\n═══ Run Export ═══")
    try:
        preset = _pick_preset()
        default_dir = (Path.cwd() / "exports" /
                        f"{preset.key}_"
                        f"{_dt.now().strftime('%Y%m%d_%H%M%S')}")
        path = _input("Output folder", default=str(default_dir),
                       allow_empty=False)
        fmt = _pick_from("Format", list(FORMATS),
                          default=DEFAULT_FORMAT)
        zip_q = _yes_no("Zip the folder when done?", default=False)
        by = _input("Run by (optional)")
        notes = _input("Notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  Running export for {preset.key} → {path} …")
    try:
        job = data.run_export(
            preset.key, path,
            fmt=fmt, zip_output=zip_q,
            run_by=by or None, notes=notes or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Job #{job.job_id} finished with status: {job.status}")
    _print_job(job)
    _pause()


def list_jobs_flow() -> None:
    print("\n═══ Past Jobs ═══")
    try:
        preset_q = _input("Filter by preset key (optional)")
        status_q = _input(
            f"Filter by status ({'/'.join(JOB_STATUSES)}, optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_jobs(
            preset_key=preset_q or None,
            status=status_q or None,
            limit=200)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_jobs(rows)
    _pause()


def view_job_flow() -> None:
    print("\n═══ View Job ═══")
    try:
        jid = int(_input("Job ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    j = data.get_job(jid)
    if j is None:
        print(f"  ✗ No job #{jid}")
        _pause()
        return
    _print_job(j)
    _pause()


def delete_job_flow() -> None:
    print("\n═══ Delete Job ═══")
    try:
        jid = int(_input("Job ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_job(jid) is None:
        print(f"  ✗ No job #{jid}")
        _pause()
        return
    remove = _yes_no(
        "Also delete the on-disk output folder & archive?",
        default=False)
    if _input(f"Delete job #{jid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_job(jid, remove_files=remove):
        print(f"\n  ✓ Deleted #{jid}")
    _pause()


def overview_flow() -> None:
    print("\n═══ Data Export Overview ═══")
    o = data.overview()
    print(f"\n  Total jobs           : {o.total_jobs}")
    print(f"  Succeeded            : {o.succeeded}")
    print(f"  Partial              : {o.partial}")
    print(f"  Failed               : {o.failed}")
    print(f"  Files written        : {o.total_files_written}")
    print(f"  Rows written         : {o.total_rows_written}")
    print(f"  Bytes written        : {o.total_bytes_written}")
    print(f"  Built-in presets     : {o.builtin_preset_count}")
    print(f"  User-defined presets : {o.user_preset_count}")
    if o.last_job:
        print("\n  Last job:")
        _print_job(o.last_job)
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Overview",          overview_flow),
    ("List Presets",      list_presets_flow),
    ("View Preset",       view_preset_flow),
    ("New Preset",        new_preset_flow),
    ("Edit Preset",       edit_preset_flow),
    ("Delete Preset",     delete_preset_flow),
    ("Run Export",        run_export_flow),
    ("List Past Jobs",    list_jobs_flow),
    ("View Job",          view_job_flow),
    ("Delete Job",        delete_job_flow),
]


def run() -> None:
    while True:
        print("\n── Data Export ──")
        for i, (label, _) in enumerate(_MENU, 1):
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
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Data-export CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Data Export":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Data-export CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
