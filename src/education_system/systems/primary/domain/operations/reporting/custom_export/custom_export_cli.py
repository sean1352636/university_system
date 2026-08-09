"""CLI flows for Primary School Custom Export."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable
from education_system.systems.primary.domain.operations.reporting.custom_export import custom_export as data
from education_system.systems.primary.domain.operations.reporting.custom_export.custom_export import (
    DatasetSpec,
    FORMATS,
    DEFAULT_FORMAT,
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
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
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


def _pick_dataset() -> DatasetSpec:
    datasets = data.list_datasets()
    print("\n  Datasets:")
    for i, d in enumerate(datasets, 1):
        print(f"    {i:>3}) {d.label:<32}  — {d.description}")
    while True:
        raw = _input(f"Pick #1..{len(datasets)} (or key)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(datasets):
                return datasets[n - 1]
        try:
            return data.get_dataset(raw)
        except ValidationError as e:
            print(f"    ✗ {e}")


def _pick_columns(spec: DatasetSpec) -> list[str] | None:
    print(f"\n  Columns available for {spec.label}:")
    for i, (k, h) in enumerate(spec.columns, 1):
        print(f"    {i:>2}) {h:<22}  ({k})")
    raw = _input(
        "Pick columns (comma-separated #s, or blank for all)")
    if not raw:
        return None
    out: list[str] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok.isdigit():
            n = int(tok)
            if 1 <= n <= len(spec.columns):
                out.append(spec.columns[n - 1][0])
            else:
                print(f"    (skipping out-of-range #{tok})")
        else:
            out.append(tok)
    return out or None


def _collect_filters(spec: DatasetSpec) -> dict[str, Any]:
    if not spec.filter_keys:
        return {}
    print(f"\n  Available filters for {spec.label}:")
    print(f"    {', '.join(spec.filter_keys)}")
    print("  Enter as key=value pairs separated by commas "
          "(blank to skip).")
    raw = _input("Filters")
    if not raw:
        return {}
    out: dict[str, Any] = {}
    for tok in raw.split(","):
        if "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        if k not in spec.filter_keys:
            print(f"    (ignoring unknown filter {k!r})")
            continue
        if v.lower() in ("true", "yes"):
            out[k] = True
        elif v.lower() in ("false", "no"):
            out[k] = False
        else:
            out[k] = v
    return out


# ── Print helpers ──────────────────────────────────────────────────

def _print_preview(headers: list[str],
                     rows: list[list[str]]) -> None:
    if not rows:
        print("\n  (no rows)")
        return
    widths = [
        max([len(h)] + [len(r[i]) for r in rows])
        for i, h in enumerate(headers)
    ]
    widths = [min(w, 32) for w in widths]
    print()
    print("  " + "  ".join(
        h.ljust(widths[i])[:widths[i]] for i, h in enumerate(headers)))
    print("  " + "  ".join("-" * widths[i] for i in range(len(headers))))
    for r in rows:
        print("  " + "  ".join(
            (c or "")[:widths[i]].ljust(widths[i])
            for i, c in enumerate(r)))
    print(f"\n  {len(rows)} row(s) shown.")


# ── Flows ──────────────────────────────────────────────────────────

def list_datasets_flow() -> None:
    print("\n═══ Available Datasets ═══")
    for d in data.list_datasets():
        print(f"\n  {d.label}  ({d.key})")
        print(f"    {d.description}")
        print(f"    Columns ({len(d.columns)}): "
              + ", ".join(k for k, _ in d.columns))
        if d.filter_keys:
            print(f"    Filters: {', '.join(d.filter_keys)}")
    _pause()


def preview_flow() -> None:
    print("\n═══ Preview Dataset ═══")
    try:
        spec = _pick_dataset()
        cols = _pick_columns(spec)
        filters = _collect_filters(spec)
        limit_s = _input("Preview rows", default="10")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        limit = int(limit_s)
    except ValueError:
        print("  ✗ Limit must be a number.")
        _pause()
        return
    try:
        headers, rows = data.preview(spec, columns=cols,
                                        filters=filters,
                                        limit=limit)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_preview(headers, rows)
    _pause()


def export_flow() -> None:
    print("\n═══ Export ═══")
    try:
        spec = _pick_dataset()
        cols = _pick_columns(spec)
        filters = _collect_filters(spec)
        fmt = _pick_from("Format", list(FORMATS),
                            default=DEFAULT_FORMAT)
        limit_s = _input("Row limit (blank=no limit)")
        default_name = f"{spec.key}.{fmt if fmt != 'markdown' else 'md'}"
        path = _input("Output file path", default=default_name,
                          allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    limit: int | None = None
    if limit_s:
        try:
            limit = int(limit_s)
        except ValueError:
            print("  ✗ Limit must be a number.")
            _pause()
            return
    try:
        res = data.export(spec, path,
                             fmt=fmt, columns=cols,
                             filters=filters, limit=limit)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("export crashed")
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Wrote {res.row_count} row(s), "
          f"{res.column_count} column(s) → {res.path}")
    print(f"    {res.bytes_written} byte(s)")
    _pause()


def print_to_console_flow() -> None:
    print("\n═══ Render to Console ═══")
    try:
        spec = _pick_dataset()
        cols = _pick_columns(spec)
        filters = _collect_filters(spec)
        fmt = _pick_from("Format", list(FORMATS),
                            default=DEFAULT_FORMAT)
        limit_s = _input("Row limit", default="50")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        limit = int(limit_s)
    except ValueError:
        print("  ✗ Limit must be a number.")
        _pause()
        return
    try:
        body = data.render(spec, fmt=fmt, columns=cols,
                              filters=filters, limit=limit)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print("\n" + body)
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Datasets",           list_datasets_flow),
    ("Preview",                 preview_flow),
    ("Export to File",          export_flow),
    ("Render to Console",       print_to_console_flow),
]


def run() -> None:
    while True:
        print("\n── Custom Export ──")
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
            logger.exception("Custom-export CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Custom Export":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Custom-export CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
