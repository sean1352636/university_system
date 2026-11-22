"""Save and "Email to admin" for every university report and chart.

One place gives every report and chart window the same two actions:

* **Save…** writes the chart (PNG / PDF / SVG) or the report (text, or
  CSV for its tables) to a file the user picks.
* **Email to admin** sends it to the university's administrators through
  the e-mail system (``email_service.core.send_email`` → the outbox, which
  honours the delivery mode), rendered from the JSON template
  ``auth_security/system/report_to_admin``. The file is attached; a text
  report's first lines are also in the message.

They reach the screens three ways, so no screen has to be edited:

1. Every embedded matplotlib chart (``FigureCanvasTkAgg``) gets a small
   "Save / Email" strip in its top-right corner.
2. Every window whose title says it is a report, chart, dashboard,
   analytics, statistics … gets a button bar along its bottom edge.
3. Screens may also call :func:`add_buttons` on a bar of their own.

A screen that already has its own save or e-mail button keeps it, and only
the action it lacks is added, including when its button appears later (for
instance once a report has been generated).

:func:`install` sets up 1 and 2; the university GUI calls it at start-up.
matplotlib is not imported by this module — the chart hook attaches when
a screen first imports the Tk backend, so start-up stays fast.
"""

from __future__ import annotations

import csv
import importlib.abc
import importlib.machinery
import logging
import re
import sys
import tkinter as tk
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    messagebox,
)

logger = logging.getLogger(__name__)

#: The e-mail template (path-qualified, so the lookup is exact).
TEMPLATE = "auth_security/system/report_to_admin"
SAVE_TEXT = "💾 Save…"
EMAIL_TEXT = "✉ Email to admin"
#: Window titles that get the bar.
_REPORT_TITLE = re.compile(
    r"report|chart|graph|dashboard|analytic|statistic|trend|breakdown|"
    r"insight|summary|overview|kpi|league table", re.I)
#: …unless the window is clearly a form about a report.
_NOT_A_REPORT = re.compile(
    r"setting|schedul|configur|builder|select|choose|filter|edit|new |"
    r"add |delete|confirm|login|password", re.I)
#: A screen's own button that saves this report, by its label. "Save" must be
#: alone or name a report or file: "Save Attendance" is writing a record.
_OWN_SAVE = re.compile(
    r"^\W*(?:(?:export|download)\b"
    r"|save(?:\s+(?:as|to)\b.*|\s+(?:\w+\s+)?(?:report|results|output|stats|analytics|"
    r"data|csv|txt|pdf|json|excel|text|file)\b.*)?\W*$)", re.I)
#: …and an export of this kind is not the report either.
_SAVES_SOMETHING_ELSE = re.compile(
    r"setting|config|template|workflow|schema|database|user|system|backup", re.I)
#: A screen's own button that e-mails this report. Bare "Send" is left out: it
#: is how a message box sends its message.
_OWN_EMAIL = re.compile(
    r"\b(e-?mail|send)\b.*\b(admin|report|chart)\b|^\W*(send\s+)?e-?mail\W*$", re.I)
#: Marks our own widgets (left out of the report text) and done windows.
_MARK = "_report_share"
#: tk widget path -> matplotlib Figure, filled by the chart hook.
_FIGURES: dict[str, Any] = {}
_PREVIEW_LINES = 40


# ── What is on screen ─────────────────────────────────────────────

@dataclass
class Content:
    figures: list[Any] = field(default_factory=list)
    tables: list[tuple[list[str], list[list[str]]]] = field(default_factory=list)
    canvases: list[tk.Canvas] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()

    @property
    def empty(self) -> bool:
        return not (self.figures or self.tables or self.canvases or self.text)


def _children(w: tk.Misc) -> list[tk.Misc]:
    try:
        return w.winfo_children()
    except tk.TclError:
        return []


def _tree_rows(tree: ttk.Treeview) -> tuple[list[str], list[list[str]]]:
    cols = list(tree["columns"])
    show = str(tree.cget("show"))
    headings = []
    if "tree" in show:
        headings.append(tree.heading("#0", "text") or "")
    headings += [tree.heading(c, "text") or str(c) for c in cols]
    rows: list[list[str]] = []

    def walk(parent: str, depth: int) -> None:
        for iid in tree.get_children(parent):
            item = tree.item(iid)
            values = [str(v) for v in (item.get("values") or [])]
            row = (["  " * depth + str(item.get("text", ""))]
                   if "tree" in show else []) + values
            rows.append(row)
            walk(iid, depth + 1)
    walk("", 0)
    return headings, rows


def collect(root: tk.Misc) -> Content:
    """Everything a report/chart window shows, in screen order."""
    out = Content()

    def walk(w: tk.Misc) -> None:
        if getattr(w, _MARK, False):
            return
        path = str(w)
        if path in _FIGURES:
            out.figures.append(_FIGURES[path])
            return
        try:
            if isinstance(w, ttk.Treeview):
                head, rows = _tree_rows(w)
                if rows:
                    out.tables.append((head, rows))
                    out.lines.append("\t".join(head))
                    out.lines += ["\t".join(r) for r in rows]
                return
            if isinstance(w, tk.Text):
                text = w.get("1.0", "end-1c").strip()
                if text:
                    out.lines.append(text)
                return
            if isinstance(w, tk.Listbox):
                out.lines += [str(x) for x in w.get(0, "end")]
                return
            if isinstance(w, tk.Canvas):
                if w.find_all() and not _children(w):
                    out.canvases.append(w)
                    return
            elif isinstance(w, (tk.Label, ttk.Label, tk.Message)):
                text = str(w.cget("text") or "").strip()
                if text:
                    out.lines.append(text)
            elif isinstance(w, (ttk.LabelFrame, tk.LabelFrame)):
                text = str(w.cget("text") or "").strip()
                if text:
                    out.lines.append(f"\n{text}")
        except tk.TclError:
            return
        for child in _children(w):
            walk(child)
    walk(root)
    return out


def _title_of(widget: tk.Misc, fallback: str = "Report") -> str:
    try:
        return widget.winfo_toplevel().title() or fallback
    except tk.TclError:
        return fallback


def _safe_name(title: str) -> str:
    name = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")[:60]
    return name or "report"


# ── Writing files ─────────────────────────────────────────────────

def _write_figure(fig, path: Path) -> None:
    fig.savefig(str(path), dpi=150, bbox_inches="tight", facecolor="white")


def _write_tables(content: Content, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for i, (head, rows) in enumerate(content.tables):
            if i:
                w.writerow([])
            w.writerow(head)
            w.writerows(rows)


def _numbered(path: Path, i: int, n: int) -> Path:
    return path if n == 1 else path.with_name(f"{path.stem}_{i + 1}{path.suffix}")


def write(content: Content, path: Path) -> list[Path]:
    """Write *content* to *path* in the format its extension names.
    Returns the files written (several charts → numbered files)."""
    ext = path.suffix.lower()
    written: list[Path] = []
    if ext in (".png", ".pdf", ".svg", ".jpg", ".jpeg") and content.figures:
        for i, fig in enumerate(content.figures):
            target = _numbered(path, i, len(content.figures))
            _write_figure(fig, target)
            written.append(target)
    elif ext in (".ps", ".eps") and content.canvases:
        for i, cv in enumerate(content.canvases):
            target = _numbered(path, i, len(content.canvases))
            cv.postscript(file=str(target), colormode="color")
            written.append(target)
    elif ext == ".csv" and content.tables:
        _write_tables(content, path)
        written.append(path)
    else:
        path.write_text(content.text + "\n", encoding="utf-8")
        written.append(path)
    return written


def _filetypes(content: Content) -> list[tuple[str, str]]:
    types: list[tuple[str, str]] = []
    if content.figures:
        types += [("PNG image", "*.png"), ("PDF document", "*.pdf"),
                  ("SVG image", "*.svg")]
    if content.canvases:
        types.append(("PostScript (chart)", "*.ps"))
    if content.tables:
        types.append(("CSV (tables)", "*.csv"))
    if content.text:
        types.append(("Text", "*.txt"))
    return types or [("Text", "*.txt")]


def save(source: tk.Misc, title: str | None = None) -> list[Path]:
    """Ask where, then save what *source* (a window or frame) shows."""
    title = title or _title_of(source)
    content = collect(source)
    parent = source.winfo_toplevel()
    if content.empty:
        messagebox.showinfo("Save", "There is nothing on this screen to save yet.",
                            parent=parent)
        return []
    types = _filetypes(content)
    first_ext = types[0][1].lstrip("*")
    name = filedialog.asksaveasfilename(
        parent=parent, title=f"Save — {title}", filetypes=types,
        defaultextension=first_ext,
        initialfile=f"{_safe_name(title)}_{datetime.now():%Y%m%d_%H%M}{first_ext}")
    if not name:
        return []
    try:
        written = write(content, Path(name))
    except Exception as exc:  # noqa: BLE001 — shown to the user
        logger.exception("Saving %s", title)
        messagebox.showerror("Save", f"Could not save:\n{exc}", parent=parent)
        return []
    messagebox.showinfo("Saved", "Saved:\n" + "\n".join(map(str, written)),
                        parent=parent)
    return written


# ── E-mail to the administrators ──────────────────────────────────

def admin_recipients() -> list[str]:
    """E-mail addresses of the university's administrators (``users`` with
    role admin), else the configured system admin address."""
    found: list[str] = []
    try:
        from education_system.systems.university.infrastructure.database.db import (
            get_connection,
        )
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT DISTINCT email FROM users WHERE role = 'admin' "
                "AND email IS NOT NULL AND TRIM(email) != '' ORDER BY email"
            ).fetchall()
        finally:
            conn.close()
        found = [str(r[0]).strip() for r in rows if r and r[0]]
    except Exception:  # noqa: BLE001 — fall back to the configured address
        logger.warning("Admin e-mail lookup failed", exc_info=True)
    if not found:
        from education_system.systems.university.infrastructure.defaults import (
            get_admin_email,
        )
        found = [get_admin_email()]
    return found


def _sender() -> str:
    try:
        from education_system.systems.university.infrastructure.shared_context import (
            get_auth,
        )
        user = getattr(get_auth(), "current_user", None) or {}
        return (user.get("username") or user.get("name") or "A staff member"
                if isinstance(user, dict) else "A staff member")
    except Exception:  # noqa: BLE001
        return "A staff member"


def _outbox_dir() -> Path:
    """Attachments must outlive the screen: the outbox sends later."""
    from education_system import paths
    folder = paths.UNIVERSITY_EXPORTS_REPORTS_DIR / "emailed"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


@dataclass
class EmailResult:
    recipients: list[str]
    sent: list[str]
    failed: list[str]
    attachments: list[Path]


def email_content(content: Content, title: str, *,
                  recipients: list[str] | None = None) -> EmailResult:
    """Render the template and send *content* to the administrators."""
    from education_system.systems.university.infrastructure.email.email_service import (
        core,
    )
    from education_system.systems.university.infrastructure.email.template_utils import (
        render_template,
    )
    recipients = recipients or admin_recipients()
    stamp = datetime.now()
    base = _outbox_dir() / f"{_safe_name(title)}_{stamp:%Y%m%d_%H%M%S}"
    attachments: list[Path] = []
    if content.figures:
        attachments += write(content, base.with_suffix(".png"))
    elif content.canvases:
        attachments += write(content, base.with_suffix(".ps"))
    if content.tables:
        attachments += write(content, base.with_suffix(".csv"))
    if content.text and not content.tables and not content.figures:
        attachments += write(content, base.with_suffix(".txt"))
    kind = "chart" if (content.figures or content.canvases) else "report"
    lines = content.text.splitlines()
    preview = "\n".join(lines[:_PREVIEW_LINES])
    if len(lines) > _PREVIEW_LINES:
        preview += f"\n… ({len(lines) - _PREVIEW_LINES} more lines in the attachment)"
    subject, body = render_template(TEMPLATE, {
        "report_title": title,
        "report_kind": kind,
        "sent_by": _sender(),
        "source_window": title,
        "generated_at": stamp.strftime("%d %B %Y %H:%M"),
        "attachment_name": ", ".join(p.name for p in attachments) or "none",
        "preview": preview,
    })
    if not subject:
        raise RuntimeError(f"E-mail template {TEMPLATE!r} could not be loaded")
    sent, failed = [], []
    for to in recipients:
        try:
            ok = core.send_email(to, subject, body,
                                 attachments=[str(p) for p in attachments],
                                 kind="transactional", category="reports")
        except Exception:  # noqa: BLE001 — reported per recipient
            logger.exception("Report e-mail to %s", to)
            ok = False
        (sent if ok else failed).append(to)
    return EmailResult(recipients, sent, failed, attachments)


def email_to_admin(source: tk.Misc, title: str | None = None) -> EmailResult | None:
    """Confirm, then e-mail what *source* shows to the administrators."""
    title = title or _title_of(source)
    parent = source.winfo_toplevel()
    content = collect(source)
    if content.empty:
        messagebox.showinfo("Email to admin",
                            "There is nothing on this screen to send yet.",
                            parent=parent)
        return None
    recipients = admin_recipients()
    if not messagebox.askyesno(
            "Email to admin",
            f"Send “{title}” to the administrator"
            f"{'s' if len(recipients) != 1 else ''}?\n\n"
            + "\n".join(recipients), parent=parent):
        return None
    try:
        result = email_content(content, title, recipients=recipients)
    except Exception as exc:  # noqa: BLE001 — shown to the user
        logger.exception("Emailing %s", title)
        messagebox.showerror("Email to admin", f"Could not send:\n{exc}",
                             parent=parent)
        return None
    if result.failed:
        messagebox.showwarning(
            "Email to admin",
            f"Sent to: {', '.join(result.sent) or 'nobody'}\n"
            f"Not sent to: {', '.join(result.failed)}", parent=parent)
    else:
        messagebox.showinfo(
            "Email to admin",
            f"“{title}” was sent to {', '.join(result.sent)}.\n\n"
            "It goes out according to the e-mail delivery mode "
            "(Email Hub → Delivery).", parent=parent)
    return result


# ── Buttons ───────────────────────────────────────────────────────

def _action_of(button: tk.Misc) -> str | None:
    """"save" or "email" if this is a screen's own button for that action."""
    if getattr(button, _MARK, False):
        return None
    try:
        text = str(button.cget("text") or "")
    except tk.TclError:
        return None
    if _OWN_EMAIL.search(text):
        return "email"
    if _OWN_SAVE.search(text) and not _SAVES_SOMETHING_ELSE.search(text):
        return "save"
    return None


def _own_actions(root: tk.Misc) -> set[str]:
    """The actions *root* already offers, not counting dialogs it has opened."""
    found: set[str] = set()

    def walk(w: tk.Misc) -> None:
        for child in _children(w):
            if isinstance(child, tk.Toplevel):
                continue
            if isinstance(child, (tk.Button, ttk.Button)):
                action = _action_of(child)
                if action:
                    found.add(action)
            walk(child)
    walk(root)
    return found


def _drop_when_screen_adds_its_own(bar: tk.Misc, buttons: dict[str, tk.Misc]) -> None:
    """Withdraw ours if the screen later shows a button for the same action.

    A window's bindings also receive its descendants' events, so this sees every
    button as it appears, whenever the screen builds it.
    """
    def on_map(event: tk.Event) -> None:
        widget = event.widget
        if not isinstance(widget, (tk.Button, ttk.Button)):
            return
        action = _action_of(widget)
        ours = buttons.pop(action, None) if action else None
        if ours is None:
            return
        try:
            ours.destroy()
            if not _children(bar):
                bar.destroy()
        except tk.TclError:
            pass
    bar.winfo_toplevel().bind("<Map>", on_map, add="+")


def add_buttons(bar: tk.Misc, source: tk.Misc | None = None, *,
                title: str | None = None, side: str = "right") -> None:
    """Pack Save… and Email to admin on *bar*, leaving out any the screen already
    has; they act on *source* (default: the bar's window)."""
    target = source if source is not None else bar.winfo_toplevel()
    own = _own_actions(target)
    buttons: dict[str, tk.Misc] = {}
    for action, text, fn in (("email", EMAIL_TEXT, email_to_admin),
                             ("save", SAVE_TEXT, save)):
        if action in own:
            continue
        b = ttk.Button(bar, text=text,
                       command=lambda f=fn: f(target, title))
        setattr(b, _MARK, True)
        b.pack(side=side, padx=(4, 0))
        buttons[action] = b
    setattr(target, _MARK + "_done", True)
    if buttons:
        _drop_when_screen_adds_its_own(bar, buttons)


def add_bar(window: tk.Misc, *, title: str | None = None) -> bool:
    """Add a bottom bar with whichever of the two buttons *window* lacks, whatever
    its layout (pack or grid). Returns False if there is nothing in it yet."""
    if getattr(window, _MARK + "_done", False):
        return True
    try:
        packed = window.pack_slaves()
        gridded = window.grid_slaves()
    except tk.TclError:
        return True
    if not packed and not gridded:
        return False
    if _own_actions(window) >= {"save", "email"}:
        setattr(window, _MARK + "_done", True)
        return True
    bar = ttk.Frame(window, padding=(8, 4))
    setattr(bar, _MARK, True)
    add_buttons(bar, window, title=title)
    if packed:
        # Packed first so it keeps its space however the rest expands.
        bar.pack(side="bottom", fill="x", before=packed[-1])
    else:
        cols, rows = window.grid_size()
        bar.grid(row=rows, column=0, columnspan=max(cols, 1), sticky="ew")
    setattr(window, _MARK + "_done", True)
    return True


def _chart_strip(widget: tk.Misc) -> None:
    """Small Save / Email strip in a chart's top-right corner."""
    try:
        if not widget.winfo_exists() or getattr(widget, _MARK + "_strip", False):
            return
        strip = tk.Frame(widget, bg="white")
        setattr(strip, _MARK, True)
        for text, fn in (("💾", save), ("✉", email_to_admin)):
            b = tk.Button(strip, text=text, relief="flat", bg="white",
                          cursor="hand2", padx=4, pady=0,
                          command=lambda f=fn: f(widget, _chart_title(widget)))
            setattr(b, _MARK, True)
            b.pack(side="left")
            _tooltip(b, "Save chart…" if fn is save else "Email chart to admin")
        strip.place(relx=1.0, rely=0.0, anchor="ne", x=-2, y=2)
        setattr(widget, _MARK + "_strip", True)
    except tk.TclError:
        pass


def _chart_title(widget: tk.Misc) -> str:
    fig = _FIGURES.get(str(widget))
    try:
        for ax in (fig.axes if fig is not None else []):
            if ax.get_title():
                return f"{_title_of(widget, 'Chart')} — {ax.get_title()}"
        if fig is not None and fig._suptitle is not None:
            return f"{_title_of(widget, 'Chart')} — {fig._suptitle.get_text()}"
    except Exception:  # noqa: BLE001
        pass
    return _title_of(widget, "Chart")


def _tooltip(widget: tk.Misc, text: str) -> None:
    tip: dict[str, tk.Toplevel | None] = {"w": None}

    def show(_e) -> None:
        if tip["w"] is not None:
            return
        w = tk.Toplevel(widget)
        w.wm_overrideredirect(True)
        w.wm_geometry(f"+{widget.winfo_rootx() + 10}+{widget.winfo_rooty() + 24}")
        tk.Label(w, text=text, bg="#ffffe0", relief="solid", bd=1,
                 padx=4).pack()
        tip["w"] = w

    def hide(_e) -> None:
        if tip["w"] is not None:
            tip["w"].destroy()
            tip["w"] = None
    widget.bind("<Enter>", show, add="+")
    widget.bind("<Leave>", hide, add="+")


# ── Hooks ─────────────────────────────────────────────────────────

_INSTALLED = False
_BACKEND = "matplotlib.backends.backend_tkagg"


def _patch_backend(module) -> None:
    cls = getattr(module, "FigureCanvasTkAgg", None)
    if cls is None or getattr(cls, _MARK, False):
        return
    original = cls.__init__

    def __init__(self, figure=None, master=None, *args, **kwargs):
        original(self, figure, master, *args, **kwargs)
        try:
            widget = self.get_tk_widget()
            path = str(widget)
            _FIGURES[path] = self.figure
            widget.bind("<Destroy>",
                        lambda e, p=path: _FIGURES.pop(p, None)
                        if str(e.widget) == p else None, add="+")
            widget.after_idle(lambda: _chart_strip(widget))
        except Exception:  # noqa: BLE001 — a chart must still draw
            logger.debug("chart buttons not added", exc_info=True)

    cls.__init__ = __init__
    setattr(cls, _MARK, True)


class _BackendFinder(importlib.abc.MetaPathFinder):
    """Patches the Tk chart backend the moment a screen imports it."""

    def find_spec(self, fullname, path, target=None):
        if fullname != _BACKEND:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return None
        loader = spec.loader
        exec_module = loader.exec_module

        def exec_and_patch(module):
            exec_module(module)
            _patch_backend(module)
        loader.exec_module = exec_and_patch
        return spec


def _schedule_bar(window: tk.Misc, title: str, tries: int = 6) -> None:
    def attempt(left: int) -> None:
        try:
            if not window.winfo_exists():
                return
        except tk.TclError:
            return
        if not add_bar(window, title=None) and left > 0:
            window.after(400, lambda: attempt(left - 1))
    window.after_idle(lambda: attempt(tries))


def _patch_titles() -> None:
    original = tk.Wm.wm_title

    def wm_title(self, string=None):
        result = original(self, string)
        if (string and isinstance(self, tk.Toplevel)
                and _REPORT_TITLE.search(str(string))
                and not _NOT_A_REPORT.search(str(string))
                and not getattr(self, _MARK + "_done", False)):
            try:
                _schedule_bar(self, str(string))
            except Exception:  # noqa: BLE001 — a window must still open
                logger.debug("report bar not scheduled", exc_info=True)
        return result

    tk.Wm.wm_title = wm_title
    tk.Wm.title = wm_title


def install() -> None:
    """Give every report/chart window Save and Email to admin.
    Idempotent."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    _patch_titles()
    if _BACKEND in sys.modules:
        _patch_backend(sys.modules[_BACKEND])
    else:
        sys.meta_path.insert(0, _BackendFinder())


__all__ = ["install", "add_buttons", "add_bar", "save", "email_to_admin",
           "email_content", "admin_recipients", "collect", "write", "Content",
           "EmailResult", "TEMPLATE"]
