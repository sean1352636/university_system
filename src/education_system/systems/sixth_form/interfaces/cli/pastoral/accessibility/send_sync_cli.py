"""CLI: profiles that disagree with the SEND register (the source of
truth for SEND status) and a re-sync."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.pastoral.accessibility import (
    accessibility as data,
)
from education_system.systems.sixth_form.domain.pastoral.send import send as send_data
from education_system.systems.sixth_form.interfaces.cli.pastoral import _records_cli as ui


def run() -> None:
    rows = data.send_register_mismatches()
    ui.print_rows(rows, (
        ("Student", lambda r: r.student_id, 9),
        ("Name", lambda r: r.student_name, 20),
        ("Profile", lambda r: r.profile_status, 11),
        ("Register", lambda r: r.register_status, 11),
        ("Problem", lambda r: r.problem, 50)),
        empty="(every profile matches the SEND register)")
    if rows and ui.yes_no("Sync all profiles from the SEND register now?"):
        n = send_data.sync_all_accessibility_profiles()
        print(f"\n  ✓ {n} profile(s) updated.")
    ui.pause()
