"""Board data files: entries export and results import (EDI fixed-width or CSV)."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox

from education_system.systems.sixth_form.domain.assessment.exam_entries.exam_entries import (
    EXAM_BOARDS,
)
from education_system.systems.sixth_form.domain.assessment.exams_office import edi
from education_system.systems.sixth_form.interfaces.gui.assessment.exams_office.exams_widgets import (
    guarded,
    SeriesBar,
    text_window,
)

logger = logging.getLogger(__name__)

_FIELD_MAP_NOTE = ("The fixed-width (EDI) layout is a configurable field map in "
                   "exams_office/edi.py and must be checked against the current JCQ "
                   "Formats specification before live use. CSV does not depend on it.")


def build_import_panel(gui, parent: tk.Misc, *, on_done=None) -> None:
    """Pick a board results file, dry-run it, then import under embargo."""
    box = ttk.LabelFrame(parent, text="Import board results", padding=8)
    box.pack(fill="x", pady=(0, 8))
    row = ttk.Frame(box)
    row.pack(fill="x")
    series = SeriesBar(row)
    board_var = tk.StringVar()
    fmt_var = tk.StringVar(value="auto")
    ttk.Label(row, text="Board (EDI files):").pack(side="left")
    ttk.Combobox(row, textvariable=board_var, values=["", *EXAM_BOARDS], state="readonly",
                 width=18).pack(side="left", padx=(4, 10))
    ttk.Label(row, text="Format:").pack(side="left")
    ttk.Combobox(row, textvariable=fmt_var, values=["auto", "csv", "edi"],
                 state="readonly", width=6).pack(side="left", padx=(4, 10))
    ttk.Label(box, text="CSV columns: board, candidate number, entry code, "
                        "[component code], grade, marks, [ums], [uci]. Results stay "
                        "hidden from students until the series is released.",
              foreground="#555", wraplength=900, justify="left").pack(anchor="w", pady=(6, 0))

    def run(dry: bool) -> None:
        path = filedialog.askopenfilename(
            parent=gui.root, title="Board results file",
            filetypes=[("Results files", "*.csv *.txt *.dat *.edi"), ("All files", "*")])
        if not path:
            return
        try:
            season, year = series.get()
            with open(path, encoding="utf-8-sig", errors="replace") as fh:
                content = fh.read()
            report = edi.import_results_file(content, season=season, year=year,
                                             fmt=fmt_var.get(),
                                             exam_board=board_var.get() or None,
                                             dry_run=dry)
        except (ValueError, OSError) as e:
            messagebox.showerror("Cannot import", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("Results import failed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
            return
        lines = [("DRY RUN — nothing written" if dry else "RESULTS IMPORTED"),
                 f"Rows: {report.rows}", f"Component results: {report.components}",
                 f"Qualification results: {report.qualifications}",
                 f"Problems: {len(report.problems)}", ""] + report.problems
        text_window(gui.root, "Results import", "\n".join(lines) + "\n",
                    filename="results_import_report.txt")
        if not dry and on_done:
            on_done()

    bar = ttk.Frame(box)
    bar.pack(fill="x", pady=(6, 0))
    ttk.Button(bar, text="Check file (dry run)…", command=lambda: run(True)).pack(side="left")
    ttk.Button(bar, text="Import file…", command=lambda: run(False)).pack(side="left", padx=6)


def build_tab(gui, parent: ttk.Frame) -> None:
    box = ttk.LabelFrame(parent, text="Export entries for a board", padding=8)
    box.pack(fill="x", pady=(0, 8))
    row = ttk.Frame(box)
    row.pack(fill="x")
    series = SeriesBar(row)
    board_var = tk.StringVar(value=EXAM_BOARDS[0])
    fmt_var = tk.StringVar(value="edi")
    centre_var = tk.StringVar(value=edi.CENTRE_NUMBER)
    withdrawn_var = tk.BooleanVar(value=True)
    ttk.Label(row, text="Board:").pack(side="left")
    ttk.Combobox(row, textvariable=board_var, values=list(EXAM_BOARDS), state="readonly",
                 width=18).pack(side="left", padx=(4, 10))
    ttk.Label(row, text="Format:").pack(side="left")
    ttk.Combobox(row, textvariable=fmt_var, values=["edi", "csv"], state="readonly",
                 width=6).pack(side="left", padx=(4, 10))
    ttk.Label(row, text="Centre no.:").pack(side="left")
    ttk.Entry(row, textvariable=centre_var, width=8).pack(side="left", padx=(4, 10))
    ttk.Checkbutton(row, text="Include withdrawals", variable=withdrawn_var).pack(side="left")

    @guarded(gui.root)
    def export() -> None:
        try:
            season, year = series.get()
            f = edi.export_entries(board_var.get(), season, year, fmt=fmt_var.get(),
                                   centre_number=centre_var.get() or None,
                                   include_withdrawn=withdrawn_var.get())
        except ValueError as e:
            messagebox.showerror("Cannot export", str(e), parent=gui.root)
            return
        if f.problems:
            messagebox.showwarning("Check before sending",
                                   "\n".join(f.problems[:15])
                                   + (f"\n… {len(f.problems) - 15} more"
                                      if len(f.problems) > 15 else ""), parent=gui.root)
        text_window(gui.root, f"Entries file — {f.exam_board} {season} {year} "
                              f"({f.detail_count} record(s))", f.content,
                    filename=f.suggested_name)

    ttk.Button(box, text="Build entries file…", command=export).pack(anchor="w", pady=(6, 0))
    ttk.Label(box, text=_FIELD_MAP_NOTE, foreground="#a60", wraplength=900,
              justify="left").pack(anchor="w", pady=(6, 0))
    build_import_panel(gui, parent)
