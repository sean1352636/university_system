"""Data Export in the terminal.

The old Data Export menu keeps its numbers: 1 Overview, 2 List presets
(packs and your saved exports), 3 View preset, 4 New preset (a saved
export), 5 Edit preset, 6 Delete preset, 7 Run export (a pack to a folder),
8 List past jobs, 9 View job, 10 Delete job. The old Custom Export options
follow, after "More": 11 List datasets, 12 Preview, 13 Export to file,
14 Render to console; then 15 Run a saved export. Rules:
:mod:`modules.reporting.domain.data_export`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.reporting.cli import report_prompts as RP
from education_system.systems.secondary.modules.reporting.domain import data_export as DX
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt

_state: dict[str, Any] = {}


def _overview(principal: Principal) -> None:
    o = DX.overview(principal)
    for k, label in (("exports", "Total exports"), ("succeeded", "Succeeded"),
                     ("failed", "Failed"), ("rows", "Rows written"),
                     ("datasets", "Datasets exported"), ("packs", "Built-in packs"),
                     ("saved", "Your saved exports"), ("last", "Last export")):
        print(f"  {label:<20} {RP.RC.show(o[k]) or '-'}")


def _list_presets(principal: Principal) -> None:
    print("  Built-in packs:")
    for key, (label, ds) in DX.PACKS.items():
        print(f"    {key:<12} {label:<16} {', '.join(ds)}")
    print("  Your saved exports:")
    RP.table(["#", "Name", "Dataset", "Columns", "Format", "Limit"],
             [[d.definition_id, d.name, d.dataset, len(d.columns), d.fmt, d.row_limit]
              for d in DX.list_definitions(principal)], limit=None, width=30)


def _view_preset(principal: Principal) -> None:
    ref = _prompt("  Pack key or saved export #: ")
    if ref in DX.PACKS:
        label, ds = DX.PACKS[ref]
        print(f"  {label}: " + ", ".join(DX.DATASETS[k].label for k in ds))
        return
    if not ref.isdigit():
        print("  Not found.")
        return
    d = DX.get_definition(principal, int(ref))
    print(f"  {d.name} - {DX.DATASETS[d.dataset].label}, {d.fmt}"
          + (f", first {d.row_limit} rows" if d.row_limit is not None else ""))
    print("  Columns: " + ", ".join(d.columns))
    print("  Filters: " + (", ".join(f"{k}={v}" for k, v in d.filters.items()) or "none"))
    if d.description:
        print(f"  {d.description}")


def _pick_dataset(principal: Principal) -> str | None:
    ds = DX.datasets_for(principal)
    for i, d in enumerate(ds, 1):
        print(f"   {i:>2}) {d.key:<14} {d.label}")
    n = prompts.ask_int("  Dataset (number): ")
    if n is None or not 1 <= n <= len(ds):
        print("  Nothing chosen.")
        return None
    return ds[n - 1].key


def _pick_columns(principal: Principal, key: str, current: list[str] | None = None
                  ) -> list[str]:
    cols = DX.columns_for(principal, key)
    for i, c in enumerate(cols, 1):
        mark = "*" if current is None or c.key in current else " "
        print(f"   {mark}{i:>2}) {c.heading}")
    raw = _prompt("  Columns (numbers separated by commas, blank = all shown with *): ")
    if not raw:
        return [c.key for c in cols if current is None or c.key in current]
    out = []
    for part in raw.replace(" ", "").split(","):
        if part.isdigit() and 1 <= int(part) <= len(cols):
            out.append(cols[int(part) - 1].key)
    return out


def _filters() -> dict[str, Any]:
    f = _state.setdefault("filters", {})
    out = RP.filters(f)
    return {"year_group": out.get("year"), "form": out.get("form"),
            "date_from": out.get("from"), "date_to": out.get("to")}


def _choices(principal: Principal) -> tuple[str, list[str], dict[str, Any]] | None:
    key = _pick_dataset(principal)
    if not key:
        return None
    return key, _pick_columns(principal, key), _filters()


def _new_preset(principal: Principal, definition_id: int | None = None) -> None:
    cur = DX.get_definition(principal, definition_id) if definition_id else None
    key = _pick_dataset(principal)
    if not key:
        return
    cols = _pick_columns(principal, key, cur.columns if cur and cur.dataset == key else None)
    f = _filters()
    name = prompts.ask("Name", cur.name if cur else None, required=True) or \
        (cur.name if cur else "")
    fmt = prompts.pick("Format", list(DX.FORMATS), cur.fmt if cur else DX.DEFAULT_FORMAT)
    limit = _prompt("  Row limit (blank = all): ")
    desc = prompts.ask("Description", cur.description if cur else None)
    d = DX.save_definition(principal, {"name": name, "dataset": key, "columns": cols,
                                       "filters": f, "fmt": fmt, "row_limit": limit,
                                       "description": desc if desc is not None else
                                       (cur.description if cur else None)}, definition_id)
    print(f"  Saved #{d.definition_id} '{d.name}'.")


def _edit_preset(principal: Principal) -> None:
    n = prompts.ask_int("  Saved export #: ")
    if n is not None:
        _new_preset(principal, n)


def _delete_preset(principal: Principal) -> None:
    n = prompts.ask_int("  Saved export #: ")
    if n is not None and prompts.yes("  Delete it?"):
        DX.delete_definition(principal, n)
        print("  Deleted.")


def _run_pack(principal: Principal) -> None:
    pack = prompts.pick("Pack", list(DX.PACKS), "pupils_core") or "pupils_core"
    fmt = prompts.pick("Format", list(DX.FORMATS), DX.DEFAULT_FORMAT) or DX.DEFAULT_FORMAT
    folder = _prompt("  Output folder: ")
    if not folder:
        return
    zip_ = prompts.yes("  Zip when done?")
    out = DX.run_pack(principal, pack, folder, fmt=fmt, zip_output=zip_)
    for f in out["files"]:
        print(f"  {f['file']:<24} {f['rows']:>6} rows")
    for r in out["refused"]:
        print(f"  refused: {r['dataset']} - {r['why']}")
    if out["archive"]:
        print(f"  Zipped to {out['archive']}")


def _jobs(principal: Principal) -> None:
    everyone = DX.can_export_all(principal) and prompts.yes("  Everyone's exports?")
    RP.table(["#", "When", "Who", "Dataset", "Format", "Rows", "Scope", "File", "Status"],
             [[r["log_id"], r["at"], r["actor"], r["dataset"], r["fmt"], r["row_count"],
               r["scope"], r["file_name"], r["status"]]
              for r in DX.history(principal, everyone=everyone)], limit=100)


def _view_job(principal: Principal) -> None:
    n = prompts.ask_int("  Export #: ")
    for r in DX.history(principal, everyone=True, limit=100000):
        if r["log_id"] == n:
            for k, v in r.items():
                print(f"  {k:<10} {RP.RC.show(v)}")
            return
    print("  Not found.")


def _delete_job(principal: Principal) -> None:
    n = prompts.ask_int("  Export #: ")
    if n is not None and prompts.yes("  Delete this record?"):
        DX.delete_log_entry(principal, n)
        print("  Deleted.")


def _datasets(principal: Principal) -> None:
    for d in DX.datasets_for(principal):
        cols = DX.columns_for(principal, d.key)
        print(f"  {d.key:<14} {d.label:<32} {len(cols)} column(s)"
              + ("  [dates]" if d.dated else ""))


def _preview(principal: Principal) -> None:
    ch = _choices(principal)
    if ch:
        pv = DX.preview(principal, *ch)
        print(f"\n  {pv['total']} row(s) ({pv['scope']}); first {len(pv['rows'])}:")
        RP.table([c.heading for c in pv["columns"]], pv["rows"], limit=None, width=18)


def _export(principal: Principal) -> None:
    ch = _choices(principal)
    if not ch:
        return
    path = _prompt(f"  Save to [{ch[0]}.csv] (.csv .tsv .json .jsonl .md): ") or f"{ch[0]}.csv"
    limit = prompts.to_int(_prompt("  Row limit (blank = all): "))
    n = DX.export(principal, ch[0], path, columns=ch[1], filters=ch[2], limit=limit)
    print(f"  Exported {n} row(s) to {path}.")


def _render(principal: Principal) -> None:
    ch = _choices(principal)
    if not ch:
        return
    fmt = prompts.pick("Format", list(DX.FORMATS), "markdown") or "markdown"
    limit = prompts.to_int(_prompt("  Row limit (blank = all): "))
    cols, rows, _scope = DX.rows(principal, ch[0], ch[1], ch[2], limit)
    print(DX.render(cols, rows, fmt))


def _run_saved(principal: Principal) -> None:
    n = prompts.ask_int("  Saved export #: ")
    if n is None:
        return
    d = DX.get_definition(principal, n)
    path = _prompt(f"  Save to [{DX.safe_file_name(d.name)}{DX.FORMATS[d.fmt]}]: ") or \
        DX.safe_file_name(d.name) + DX.FORMATS[d.fmt]
    print(f"  Exported {DX.run_definition(principal, n, path)} row(s).")


_OPTIONS = {"1": _overview, "2": _list_presets, "3": _view_preset, "4": _new_preset,
            "5": _edit_preset, "6": _delete_preset, "7": _run_pack, "8": _jobs,
            "9": _view_job, "10": _delete_job, "11": _datasets, "12": _preview,
            "13": _export, "14": _render, "15": _run_saved}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("data_export.view")
        print("\n  ── Data Export ──")
        print("    1) Overview\n    2) List presets\n    3) View preset\n    4) New preset"
              "\n    5) Edit preset\n    6) Delete preset\n    7) Run export"
              "\n    8) List past jobs\n    9) View job\n   10) Delete job")
        print("  More")
        print("   11) List datasets\n   12) Preview\n   13) Export to file"
              "\n   14) Render to console\n   15) Run a saved export")
        print("    0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except (*RP.ERRORS, OSError) as e:
            prompts.problem(e)
        _pause()
