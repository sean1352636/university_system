"""Shared Tk helpers for the exams-office screens.

Tables, a field-list form dialog, a printable text window, a series
picker and the capability check used by the sensitive tabs.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from dataclasses import dataclass
from datetime import date as _date
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from typing import Any, Callable, Iterable, Sequence

from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable
from education_system.systems.sixth_form.domain.assessment.exam_entries.exam_entries import (
    DEFAULT_SEASON,
    SEASONS,
)
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel

logger = logging.getLogger(__name__)

ERROR_FG = "#a33"
MUTED_FG = "#555"


def default_year() -> int:
    today = _date.today()
    return today.year if today.month < 9 else today.year + 1


def clear(frame: tk.Misc) -> None:
    for w in frame.winfo_children():
        w.destroy()


# ── Tables ──────────────────────────────────────────────────────────

def table(parent: tk.Misc, columns: Sequence[tuple[str, int]],
          rows: Iterable[Sequence[Any]], *, height: int = 14,
          iids: Sequence[Any] | None = None) -> ttk.Treeview:
    """A scrolled Treeview. ``columns`` is ``[(heading, width), ...]``."""
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    keys = [f"c{i}" for i in range(len(columns))]
    tree = ttk.Treeview(holder, columns=keys, show="headings", height=height)
    for key, (heading, width) in zip(keys, columns):
        tree.heading(key, text=heading)
        tree.column(key, width=width, anchor="w")
    vs = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    tree.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")
    for i, row in enumerate(rows):
        values = ["—" if v in (None, "") else v for v in row]
        if iids is not None:
            tree.insert("", "end", iid=str(iids[i]), values=values)
        else:
            tree.insert("", "end", values=values)
    return tree


def selected_id(tree: ttk.Treeview, root: tk.Misc, what: str = "a row") -> int | None:
    sel = tree.selection()
    if not sel:
        messagebox.showinfo("No selection", f"Pick {what} first.", parent=root)
        return None
    try:
        return int(sel[0])
    except ValueError:
        return None


def yn(flag: Any) -> str:
    return "Yes" if flag else ""


def money(v: float | None) -> str:
    return f"£{v:.2f}" if v is not None else ""


# ── Form dialog ─────────────────────────────────────────────────────

@dataclass
class FormField:
    key: str
    label: str
    kind: str = "entry"            # entry / combo / readonly / check / text
    options: Sequence[str] = ()
    width: int = 32


def form_dialog(root: tk.Misc, title: str, fields: Sequence[FormField],
                on_submit: Callable[[dict[str, Any]], Any], *,
                initial: dict[str, Any] | None = None,
                on_done: Callable[[], None] | None = None,
                note: str | None = None) -> None:
    """Modal form. ``on_submit(values)`` may raise ValueError to keep it open."""
    initial = initial or {}
    win = tk.Toplevel(root)
    win.title(title)
    win.transient(root)
    grab_when_viewable(win)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    getters: dict[str, Callable[[], Any]] = {}
    row = 0
    if note:
        ttk.Label(frm, text=note, foreground=MUTED_FG, wraplength=520,
                  justify="left").grid(row=0, column=0, columnspan=2, sticky="w",
                                       pady=(0, 8))
        row = 1
    for f in fields:
        ttk.Label(frm, text=f.label + ":").grid(row=row, column=0, sticky="ne",
                                                padx=(0, 6), pady=2)
        init = initial.get(f.key)
        if f.kind == "check":
            var = tk.BooleanVar(value=bool(init))
            ttk.Checkbutton(frm, variable=var).grid(row=row, column=1, sticky="w", pady=2)
            getters[f.key] = var.get
        elif f.kind == "text":
            txt = tk.Text(frm, width=f.width + 10, height=5, wrap="word")
            txt.insert("1.0", "" if init is None else str(init))
            txt.grid(row=row, column=1, sticky="w", pady=2)
            getters[f.key] = (lambda t=txt: t.get("1.0", "end").strip())
        else:
            var = tk.StringVar(value="" if init is None else str(init))
            if f.kind in ("combo", "readonly"):
                w = ttk.Combobox(frm, textvariable=var, values=list(f.options),
                                 width=f.width,
                                 state="readonly" if f.kind == "readonly" else "normal")
            else:
                w = ttk.Entry(frm, textvariable=var, width=f.width)
            w.grid(row=row, column=1, sticky="w", pady=2)
            getters[f.key] = var.get
        row += 1

    def save() -> None:
        values = {k: g() for k, g in getters.items()}
        try:
            on_submit(values)
        except (ValueError, PermissionError) as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("%s failed", title)
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        if on_done:
            on_done()

    bar = ttk.Frame(frm)
    bar.grid(row=row, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


def run_action(root: tk.Misc, action: Callable[[], Any], *, done: str | None = None,
               then: Callable[[], None] | None = None) -> Any:
    """Run a domain call, showing a validation error instead of raising."""
    try:
        out = action()
    except (ValueError, PermissionError) as e:
        messagebox.showerror("Cannot do that", str(e), parent=root)
        return None
    except Exception as e:
        logger.exception("Exams-office action failed")
        messagebox.showerror("Error", f"Unexpected: {e}", parent=root)
        return None
    if done:
        messagebox.showinfo("Done", done if "{" not in done else done.format(out=out),
                            parent=root)
    if then:
        then()
    return out


def guarded(root: tk.Misc, what: str = "That action"
            ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a button callback so errors never escape into Tk.

    A validation problem (e.g. a year that isn't a number) is shown as
    an error; anything unexpected (an adapter or database failure) is
    logged with its traceback and shown as a warning.
    """
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def run(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except (ValueError, PermissionError) as e:
                messagebox.showerror("Cannot do that", str(e), parent=root)
            except Exception as e:
                logger.exception("Exams-office callback %s failed", fn.__name__)
                messagebox.showwarning(
                    "Exams Office",
                    f"{what} failed: {e}\n\nThe error has been logged.",
                    parent=root)
            return None
        return run
    return deco


# ── Printable text ──────────────────────────────────────────────────

def text_window(root: tk.Misc, title: str, content: str, *,
                filename: str = "report.txt") -> None:
    """Show text in a window with Save (for printing) and Copy."""
    from education_system.platform.delivery.gui import window_sizing
    win = make_toplevel(root)
    win.title(title)
    window_sizing.fit(win, "1000x700", (700, 500))
    bar = ttk.Frame(win, padding=(8, 8, 8, 0))
    bar.pack(fill="x")

    def save() -> None:
        path = filedialog.asksaveasfilename(parent=win, initialfile=filename,
                                            defaultextension=filename.rsplit(".", 1)[-1]
                                            if "." in filename else ".txt")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(content)
        except OSError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        messagebox.showinfo("Saved", f"Saved to {path}", parent=win)

    def copy() -> None:
        win.clipboard_clear()
        win.clipboard_append(content)

    ttk.Button(bar, text="Save to file (for printing)…", command=save).pack(side="left")
    ttk.Button(bar, text="Copy", command=copy).pack(side="left", padx=6)
    txt = tk.Text(win, wrap="none", font=("Courier", 10))
    txt.insert("1.0", content)
    txt.configure(state="disabled")
    txt.pack(fill="both", expand=True, padx=8, pady=8)


# ── Series picker ───────────────────────────────────────────────────

class SeriesBar:
    """Season + year pickers packed into *parent*."""

    def __init__(self, parent: tk.Misc, *, on_change: Callable[[], None] | None = None):
        self.season = tk.StringVar(value=DEFAULT_SEASON)
        self.year = tk.StringVar(value=str(default_year()))
        ttk.Label(parent, text="Season:").pack(side="left")
        ttk.Combobox(parent, textvariable=self.season, values=list(SEASONS),
                     state="readonly", width=10).pack(side="left", padx=(4, 10))
        ttk.Label(parent, text="Year:").pack(side="left")
        ttk.Entry(parent, textvariable=self.year, width=6).pack(side="left", padx=(4, 10))
        if on_change:
            ttk.Button(parent, text="Show", command=on_change).pack(side="left", padx=(0, 10))

    def get(self) -> tuple[str, int]:
        try:
            return self.season.get(), int(self.year.get())
        except ValueError:
            raise ValueError("Year must be a number") from None


# ── Access ──────────────────────────────────────────────────────────

def sensitive_gate(parent: tk.Misc, area: str, capabilities: Sequence[str],
                   message: str) -> bool:
    """True when the signed-in principal holds one of *capabilities*.

    Logs the view (or the refusal) to the sensitive-access log and, when
    refused, puts *message* in *parent*.
    """
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        p = access.current()
        caps = [getattr(access, c) for c in capabilities]
        allowed = any(p.can(c) for c in caps)
        access.log_sensitive_access(p, area, "view", allowed=allowed)
    except (ImportError, AttributeError):
        allowed = True
    if not allowed:
        ttk.Label(parent, text=message, foreground=ERROR_FG, wraplength=780,
                  justify="left").pack(anchor="w")
    return allowed


def log_change(area: str, action: str, *, student_id: str | None = None,
               record_ref: str | None = None) -> None:
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        access.log_sensitive_access(access.current(), area, action,
                                    student_id=student_id, record_ref=record_ref)
    except (ImportError, AttributeError):
        pass


def student_choices() -> tuple[list[str], dict[str, str]]:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    rows = _students.list_students()
    labels = [f"{s.student_id} — {s.full_name}" for s in rows]
    return labels, {lbl: s.student_id for lbl, s in zip(labels, rows)}


def student_from_label(value: str, mapping: dict[str, str]) -> str:
    return mapping.get(value) or value.split(" — ", 1)[0].strip()
