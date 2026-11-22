"""Small Tk helpers shared by the newer pastoral windows (looked-after
register, young carers, tutorial programme, contact log, exit
interviews). The tables and forms themselves are
:mod:`_records_ui`'s ``RecordTab`` / ``ask_form``."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable

from education_system.platform import branding
from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.domain.pastoral import _people
from education_system.systems.sixth_form.domain.pastoral._records import Col

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def make_window(parent: Any, title: str) -> tuple[tk.Misc, ttk.Notebook]:
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"{title} — {branding.SYSTEM_NAME}")
    window_sizing.fit(win, WIN_GEOMETRY, WIN_MINSIZE)
    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    return win, nb


def user_error(parent: tk.Misc, title: str, exc: BaseException) -> None:
    """Warning for things the user can fix, error (and log) otherwise."""
    if isinstance(exc, (ValueError, PermissionError)):
        messagebox.showwarning(title, str(exc), parent=parent)
    else:
        logger.exception("%s failed", title, exc_info=exc)
        messagebox.showerror(title, f"Unexpected error: {exc}", parent=parent)


def staff_col(name: str, label: str, *, required: bool = False) -> Col:
    """A choice column of ``"<id> — <name>"`` staff labels; the domain
    accepts the label or a bare id."""
    try:
        choices = _people.staff_choices()
    except Exception:
        logger.exception("Could not list staff")
        choices = ()
    return Col(name, label, "choice", required=required, choices=choices)


def swap_cols(cols: Any, replacements: dict[str, Col]) -> list[Col]:
    """*cols* with the named columns replaced (e.g. staff ids → staff
    choice lists)."""
    return [replacements.get(c.name, c) for c in cols]


class ReportTab:
    """Read-only text page rebuilt from ``render(filters)`` → lines, with
    optional free-text filters on the action bar."""

    def __init__(self, nb: ttk.Notebook, title: str,
                 render: Callable[[dict[str, str]], list[str]], *,
                 filters: tuple[tuple[str, str, str], ...] = ()) -> None:
        self.render = render
        self.title = title
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=title)
        bar = ttk.Frame(self.frame)
        bar.pack(side="top", fill="x", padx=8, pady=(8, 4))
        self._vars: dict[str, tk.StringVar] = {}
        for key, label, default in filters:
            ttk.Label(bar, text=f"{label}:").pack(side="left")
            var = tk.StringVar(value=default)
            ttk.Entry(bar, textvariable=var, width=12).pack(
                side="left", padx=(2, 10))
            self._vars[key] = var
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(
            side="left")
        holder = ttk.Frame(self.frame)
        holder.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text = tk.Text(holder, wrap="none", font=("TkFixedFont", 10))
        sb = ttk.Scrollbar(holder, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.refresh()

    def refresh(self) -> None:
        try:
            lines = self.render({k: v.get().strip()
                                 for k, v in self._vars.items()})
        except Exception as exc:
            lines = [f"Could not build the report: {exc}"]
            if not isinstance(exc, (ValueError, PermissionError)):
                logger.exception("%s report failed", self.title)
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


def counts_block(title: str, d: dict[str, int]) -> list[str]:
    out = [f"  {title}:"]
    if not d:
        out.append("    (none)")
    for k, n in sorted(d.items(), key=lambda kv: (-kv[1], kv[0])):
        out.append(f"    {k:<40} {n:>4}")
    return out + [""]
