"""Shared helper for previewing an uploaded submission file.

Plain-text-ish formats (.txt / .md / .csv / source) are rendered
inline in a scrollable Toplevel. Other formats (.pdf, .docx, …) are
first tried via the plagiarism module's extractor (which uses textract
when available) and otherwise fall back to opening the file with the
OS default application.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

logger = logging.getLogger(__name__)

_TEXT_EXTENSIONS = {
    '.txt', '.md', '.rst', '.log', '.csv', '.tsv',
    '.json', '.xml', '.html', '.htm', '.yml', '.yaml',
    '.py', '.js', '.ts', '.java', '.c', '.h', '.cpp', '.hpp',
    '.cs', '.go', '.rb', '.rs', '.sh', '.sql', '.ini', '.cfg',
}


def open_externally(file_path: str, parent=None) -> None:
    """Launch the OS default application for file_path."""
    try:
        if sys.platform == 'darwin':
            subprocess.Popen(['open', file_path])
        elif sys.platform.startswith('win'):
            os.startfile(file_path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(['xdg-open', file_path])
    except Exception as e:
        messagebox.showerror("Open Failed",
                             f"Could not open file externally:\n{e}",
                             parent=parent)


def preview_file(parent, file_path: str, title: str = "Submitted File") -> None:
    """Show file contents in a Toplevel preview, or offer to open externally."""
    if not file_path or not os.path.exists(file_path):
        messagebox.showerror(
            "File Not Found",
            f"The submitted file is no longer on disk:\n{file_path}",
            parent=parent,
        )
        return

    text, err = _extract_text(file_path)
    if text is None:
        if messagebox.askyesno(
                "Preview Unavailable",
                f"'{os.path.basename(file_path)}' cannot be previewed in-app"
                + (f"\n({err})" if err else '')
                + "\n\nOpen it with your system's default application?",
                parent=parent):
            open_externally(file_path, parent=parent)
        return

    _show_text_window(parent, title, file_path, text)


def _extract_text(file_path: str):
    """Return (text, error_message_or_None). text is None when extraction fails."""
    ext = Path(file_path).suffix.lower()
    if ext in _TEXT_EXTENSIONS or ext == '':
        for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'cp1252'):
            try:
                with open(file_path, 'r', encoding=enc) as fh:
                    return fh.read(), None
            except UnicodeDecodeError:
                continue
            except OSError as e:
                return None, str(e)
        return None, 'could not decode as text'

    try:
        from education_system.university_system.modules.domain.academics.services.plagiarism.checker import (
            PlagiarismChecker,
        )
        text, _ = PlagiarismChecker().extract_text_from_file(file_path)
        return text, None
    except Exception as e:
        logger.debug("Text extraction via plagiarism checker failed: %s", e)
        return None, str(e)


def _show_text_window(parent, title: str, file_path: str, text: str) -> None:
    win = tk.Toplevel(parent)
    win.title(f"{title} — {os.path.basename(file_path)}")
    win.geometry('900x700')
    win.minsize(520, 360)
    try:
        win.transient(parent)
    except Exception:
        pass

    header = ttk.Frame(win, padding=(10, 8))
    header.pack(fill='x')
    ttk.Label(header, text=os.path.basename(file_path),
              font=('Arial', 11, 'bold')).pack(side='left')
    try:
        size = os.path.getsize(file_path)
        ttk.Label(header, text=f"({size:,} bytes)",
                  foreground='#666').pack(side='left', padx=(8, 0))
    except OSError:
        pass
    ttk.Button(header, text='Open Externally',
               command=lambda: open_externally(file_path, parent=win)
               ).pack(side='right')

    body = ttk.Frame(win, padding=(10, 0, 10, 10))
    body.pack(fill='both', expand=True)

    txt = tk.Text(body, wrap='word', font=('Courier', 10), padx=6, pady=6)
    vsb = ttk.Scrollbar(body, orient='vertical', command=txt.yview)
    txt.configure(yscrollcommand=vsb.set)
    txt.pack(side='left', fill='both', expand=True)
    vsb.pack(side='right', fill='y')

    txt.insert('1.0', text)
    txt.configure(state='disabled')

    footer = ttk.Frame(win, padding=(10, 0, 10, 10))
    footer.pack(fill='x')
    ttk.Button(footer, text='Close', command=win.destroy).pack(side='right')
