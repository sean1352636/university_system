""""SEND Register Check" tab for the Accessibility window.

The SEND register is the single source of truth for SEND status; the
profile's send_status mirrors it. This tab lists profiles that claim a
status without a register entry (or disagree with it) and re-syncs.
"""

from __future__ import annotations

from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any

from education_system.systems.sixth_form.domain.pastoral.accessibility import (
    accessibility as data,
)
from education_system.systems.sixth_form.domain.pastoral.send import send as send_data
from education_system.systems.sixth_form.interfaces.gui.pastoral._records_ui import RecordTab


def _sync(tab: RecordTab, _row: Any) -> None:
    n = send_data.sync_all_accessibility_profiles()
    messagebox.showinfo("SEND Register Check",
                        f"{n} profile(s) updated from the SEND register.",
                        parent=tab.frame)


def add_send_sync_tab(nb: ttk.Notebook) -> None:
    RecordTab(
        nb, "SEND Register Check", None,
        load=lambda _f: data.send_register_mismatches(),
        columns=(("Student", lambda r: r.student_id, 90),
                 ("Name", lambda r: r.student_name, 180),
                 ("Profile says", lambda r: r.profile_status, 110),
                 ("Register says", lambda r: r.register_status, 110),
                 ("Problem", lambda r: r.problem, 420)),
        actions=(("Sync All from SEND Register", _sync, False),),
        row_id=lambda r: r.student_id,
        intro=("SEND status comes from the SEND register. Profiles for "
               "students on the register are kept in step automatically; "
               "the rows here need a register entry adding, or the "
               "profile setting to None."))
