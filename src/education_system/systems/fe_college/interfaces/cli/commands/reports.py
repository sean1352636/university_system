"""Report commands — run any of the reports, and export them as CSV.

Column headings and formatting are derived from the rows, the same way the GUI
reports screen does it, so a new report needs no change here.
"""

from __future__ import annotations

from education_system.systems.fe_college.interfaces.cli import shell as sh

# Keys rendered as a percentage / as money, matching the GUI's report screen.
_PCT_KEYS = ("attendance_pct", "punctuality_pct", "retention_pct",
             "achievement_pct", "fill_pct", "utilisation_pct")
_MONEY_KEYS = ("estimated_income", "lost_to_withdrawal", "outstanding", "overdue")


def run(ctl) -> None:
    """Pick a report and print it."""
    names = list(ctl.reports.REPORTS)
    labels = [ctl.reports.REPORTS[n][0] for n in names]
    chosen = sh.choose("Report", labels)
    if chosen is sh.CANCEL:
        return
    name = names[labels.index(chosen)]
    _show(ctl, name)


def _show(ctl, name: str) -> None:
    label = ctl.reports.REPORTS[name][0]
    sh.header(label, ctl.reports.header())
    try:
        rows = ctl.reports.run(name)
    except Exception as exc:  # noqa: BLE001 - report failures are reported, not fatal
        sh.error(f"That report could not be run: {exc}")
        return

    if not rows:
        sh.note("That report has no data yet — nothing matches.")
        return

    keys = [k for k in rows[0] if not k.startswith("_")]
    columns = [(k, k.replace("_pct", " %").replace("_", " ").title()) for k in keys]
    sh.table(columns, [_format(row) for row in rows], limit=50)

    if sh.confirm("Export it as CSV?"):
        path = ctl.reports.export(name)
        sh.success(f"Written to {path}")


def _format(row: dict) -> dict:
    out = {}
    for key, value in row.items():
        if key in _PCT_KEYS:
            out[key] = sh.pct(value)
        elif key in _MONEY_KEYS:
            out[key] = sh.money(value)
        else:
            out[key] = value
    return out


def attendance(ctl) -> None:
    _show(ctl, "attendance")


def achievement(ctl) -> None:
    _show(ctl, "achievement")


def viability(ctl) -> None:
    _show(ctl, "viability")


def funding(ctl) -> None:
    _show(ctl, "funding")


def at_risk(ctl) -> None:
    _show(ctl, "at_risk")


def workload(ctl) -> None:
    _show(ctl, "workload")


def finance(ctl) -> None:
    _show(ctl, "finance")


def export_all(ctl) -> None:
    """Write every report to the exports directory."""
    sh.header("Export all reports")
    written = []
    for name in ctl.reports.REPORTS:
        try:
            written.append(ctl.reports.export(name))
        except Exception as exc:  # noqa: BLE001
            sh.error(f"{name}: {exc}")
    if written:
        sh.success(f"Wrote {len(written)} report(s):")
        sh.bullet_list([str(p) for p in written])


__all__ = [
    "achievement", "at_risk", "attendance", "export_all", "finance",
    "funding", "run", "viability", "workload",
]
