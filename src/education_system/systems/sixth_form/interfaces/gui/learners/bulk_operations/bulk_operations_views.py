"""Tkinter views for Sixth Form Bulk Operations.

Notebook tabs:
* Run         — pick operation, pick students, configure parameters,
                preview (dry run) and execute.
* Job log     — recent runs with view-details / delete.
* Schedules   — manage recurring bulk-job definitions.
* Logs        — structured log entries persisted to the bulk DB.
* Summary     — totals + by-operation counts.
"""

from __future__ import annotations

import json
import logging
import tkinter as tk
from datetime import date as _date
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog
from typing import Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.learners.bulk_operations import (
    base as bulk_base,
    ops_academic as bulk_ops_academic,
    ops_attendance as bulk_ops_attendance,
    ops_behaviour as bulk_ops_behaviour,
    ops_comms as bulk_ops_comms,
    ops_finance as bulk_ops_finance,
    ops_records as bulk_ops_records,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import (
    BulkResult,
    Job,
    OPERATIONS,
    SAFE_STUDENT_FIELDS,
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.view_common import (
    _NO_STUDENTS_OPS,
    OPERATION_LABELS,
    _today,
    WIN_GEOMETRY,
    WIN_MINSIZE,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.dialogs import (
    JobDetailDialog,
    _ResultDialog,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.other_tabs import (
    JobsTab,
    LogsTab,
    SchedulesTab,
    SummaryTab,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.run_tab.forms_records import (
    RecordsFormsMixin,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.run_tab.forms_attendance import (
    AttendanceFormsMixin,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.run_tab.forms_academic import (
    AcademicFormsMixin,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.run_tab.forms_pastoral import (
    PastoralFormsMixin,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.run_tab.forms_comms import (
    CommsFormsMixin,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.run_tab.forms_finance import (
    FinanceFormsMixin,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.run_tab.runner import (
    RunnerMixin,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.run_tab.tab import (
    RunTab,
)

logger = logging.getLogger(__name__)


def open_bulk_operations_window(parent=None) -> None:
    bulk_base.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Bulk Operations — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    RunTab(nb)
    JobsTab(nb)
    SchedulesTab(nb)
    LogsTab(nb)
    SummaryTab(nb)
