"""Save a Course Management report as PDF, CSV or TXT.

The report windows used to offer a single "Export as TXT" button. This
replaces that with one "Save Report" action that asks for the format first,
so a report can leave the app as something other than a wall of text.

A report is described as *sections* — ``(heading, columns, rows)`` triples —
alongside the plain-text rendering that already existed. The structured form
is what makes a genuinely useful CSV (one row per record, not one row per line
of prose) and a tabular PDF; the text form remains the fallback and is what
the TXT export and the email body use.
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

#: (label, extension, filedialog type entry)
FORMATS = (
    ("PDF document", ".pdf", ("PDF files", "*.pdf")),
    ("CSV spreadsheet", ".csv", ("CSV files", "*.csv")),
    ("Plain text", ".txt", ("Text files", "*.txt")),
)


def ask_format(parent):
    """Small modal asking which format to save as. Returns '.pdf'/'.csv'/'.txt' or None."""
    import tkinter as tk
    from tkinter import ttk

    dialog = tk.Toplevel(parent)
    dialog.title("Save Report")
    dialog.resizable(False, False)
    dialog.transient(parent)

    choice = {"ext": None}
    chosen = tk.StringVar(value=".pdf")

    ttk.Label(dialog, text="Save this report as:").pack(anchor="w", padx=16, pady=(16, 8))
    for label, ext, _types in FORMATS:
        ttk.Radiobutton(dialog, text=label, value=ext, variable=chosen).pack(
            anchor="w", padx=28, pady=2)

    buttons = ttk.Frame(dialog)
    buttons.pack(fill=tk.X, padx=16, pady=(14, 14))

    def _ok():
        choice["ext"] = chosen.get()
        dialog.destroy()

    ttk.Button(buttons, text="Save…", command=_ok).pack(side=tk.RIGHT)
    ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=(0, 8))

    dialog.bind("<Return>", lambda _e: _ok())
    dialog.bind("<Escape>", lambda _e: dialog.destroy())

    # Centre on the report window rather than the screen.
    dialog.update_idletasks()
    try:
        x = parent.winfo_rootx() + (parent.winfo_width() - dialog.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - dialog.winfo_height()) // 3
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
    except Exception:
        logger.debug("could not centre the save dialog", exc_info=True)

    try:
        dialog.grab_set()
    except tk.TclError:
        logger.debug("could not make the save dialog modal", exc_info=True)
    dialog.wait_window()
    return choice["ext"]


def _write_txt(path, title, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.write(f"\n\nGenerated: {datetime.now():%Y-%m-%d %H:%M:%S}\n")


def _write_csv(path, title, text, sections):
    """One block per section, each with its own header row.

    Falls back to the text rendering when a caller has no structured data —
    still better than nothing, but the sections are what make this readable
    in a spreadsheet.
    """
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([title])
        writer.writerow([f"Generated {datetime.now():%Y-%m-%d %H:%M:%S}"])
        writer.writerow([])

        if not sections:
            for line in text.splitlines():
                writer.writerow([line])
            return

        for heading, columns, rows in sections:
            writer.writerow([heading])
            if columns:
                writer.writerow(list(columns))
            for row in rows:
                writer.writerow(["" if v is None else v for v in row])
            writer.writerow([])


def _write_pdf(path, title, text, sections):
    """Tabular PDF via the shared PDFGenerator service."""
    from education_system.systems.university.services.pdf_export.pdf_generator import (
        PDFGenerator,
    )

    pdf = PDFGenerator(path)
    pdf.add_title_page(title, subtitle=f"Generated {datetime.now():%Y-%m-%d %H:%M}")

    if sections:
        for heading, columns, rows in sections:
            if columns and rows:
                pdf.add_data_table(list(columns), [tuple(r) for r in rows],
                                   table_name=heading)
            else:
                pdf.add_section_header(heading)
                for row in rows:
                    pdf.add_text(" — ".join(str(v) for v in row))
            pdf.add_spacer(0.2)
    else:
        pdf.add_section_header(title)
        for line in text.splitlines():
            pdf.add_text(line if line.strip() else "&nbsp;")

    if not pdf.save():
        raise OSError("PDF writer reported a failure")


def save_report(parent, base_name, title, text, sections=None):
    """Ask for a format, ask for a path, write the file.

    ``sections`` is an optional list of ``(heading, columns, rows)``. Returns
    the path written, or None when the user cancelled either dialog.
    """
    from tkinter import filedialog, messagebox

    ext = ask_format(parent)
    if not ext:
        return None

    types = next((t for _l, e, t in FORMATS if e == ext), ("All files", "*.*"))
    path = filedialog.asksaveasfilename(
        parent=parent,
        defaultextension=ext,
        filetypes=[types, ("All files", "*.*")],
        initialfile=f"{base_name}_{datetime.now():%Y%m%d_%H%M%S}{ext}",
    )
    if not path:
        return None

    try:
        if ext == ".pdf":
            _write_pdf(path, title, text, sections)
        elif ext == ".csv":
            _write_csv(path, title, text, sections)
        else:
            _write_txt(path, title, text)
    except ImportError:
        # reportlab is an optional dependency; say so plainly rather than
        # failing with a traceback about a missing module.
        messagebox.showerror(
            "Save Report",
            "Saving as PDF needs the 'reportlab' package, which is not "
            "installed. Save as CSV or TXT instead.",
            parent=parent,
        )
        return None
    except Exception as exc:
        logger.exception("failed to save report to %s", path)
        messagebox.showerror("Save Report", f"Failed to save the report:\n{exc}",
                             parent=parent)
        return None

    messagebox.showinfo("Save Report", f"Report saved to:\n{path}", parent=parent)
    return path


__all__ = ["save_report", "ask_format", "FORMATS"]
