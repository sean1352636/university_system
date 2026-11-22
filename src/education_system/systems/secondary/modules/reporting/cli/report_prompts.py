"""Terminal helpers shared by the report menus."""

from __future__ import annotations

from typing import Any, Callable

from education_system.systems.secondary.modules.reporting.domain import report_common as RC
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt

ERRORS = (RC.ValidationError, RC.PermissionDenied, RC.NotFound)


def table(head: list[str], rows: list[list[Any]], *, limit: int | None = 60,
          width: int = 22) -> None:
    """Print rows as fixed-width columns (first *limit* rows)."""
    if not rows:
        print("  (nothing to show)")
        return
    widths = [min(width, max(len(str(h)), *(len(RC.show(r[i])) for r in rows)))
              for i, h in enumerate(head)]
    print("  " + " ".join(f"{str(h)[:w]:<{w}}" for h, w in zip(head, widths)))
    print("  " + " ".join("-" * w for w in widths))
    for r in rows[:limit] if limit else rows:
        print("  " + " ".join(f"{RC.show(v)[:w]:<{w}}" for v, w in zip(r, widths)))
    if limit and len(rows) > limit:
        print(f"  ... and {len(rows) - limit} more (export to CSV for all)")


def filters(state: dict[str, Any], *, dates: bool = True, year: bool = True,
            form: bool = True) -> dict[str, Any]:
    """Ask for the filters; Enter keeps the last answer, '-' clears it."""
    out = dict(state)
    asks = []
    if dates:
        asks += [("from", "From date (YYYY-MM-DD, blank = 1 Sep)"),
                 ("to", "To date (blank = today)")]
    if year:
        asks.append(("year", "Year group (7-11, blank = all)"))
    if form:
        asks.append(("form", "Form (blank = all)"))
    for key, label in asks:
        v = prompts.ask(label, out.get(key) or None)
        if v is not None:
            out[key] = v
    state.update(out)
    return out


def pupil_id(label: str = "Pupil (admission no / UPN / id)") -> int | None:
    ref = _prompt(f"  {label}: ")
    if not ref:
        return None
    p = P.find_by_reference(ref)
    if p is None:
        print("  No such pupil.")
        return None
    return p.pupil_id


def csv_path(default: str) -> str | None:
    path = _prompt(f"  Save CSV to [{default}]: ") or default
    return path or None


def run(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except ERRORS as e:
        prompts.problem(e)
        return None
