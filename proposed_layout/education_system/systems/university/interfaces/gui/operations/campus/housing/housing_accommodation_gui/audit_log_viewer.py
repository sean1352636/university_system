"""Activity / audit-log viewer.

The university system writes every ``log_activity`` call to a daily-
rotated file under ``LOG_DIR/app.log`` (plus dated suffixes). This
screen reads the current ``app.log`` and any rotated siblings, parses
the standard ``%Y-%m-%d %H:%M:%S,fff - LEVEL - logger - message`` line
format, and offers free-text + level filters. Default filter narrows
to housing-relevant lines (containers ``housing`` or ``assignment``)
so the table isn't dominated by ambient framework chatter.
"""

from __future__ import annotations

import logging
import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

logger = logging.getLogger(__name__)

LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})"
    r"\s-\s(?P<level>\w+)\s-\s(?P<logger>[\w\.\-]+)\s-\s(?P<msg>.*)$"
)


def show_audit_log(gui_instance) -> None:
    gui_instance.clear_content()
    parent = gui_instance.content_frame

    ttk.Label(parent, text="Activity / Audit Log",
              font=("Arial", 14, "bold")).pack(anchor="w", padx=8,
                                                pady=(8, 4))

    # ── Filter bar ──
    bar = ttk.Frame(parent)
    bar.pack(fill="x", padx=8, pady=4)

    ttk.Label(bar, text="Contains:").pack(side="left", padx=(0, 4))
    q_var = tk.StringVar(value="housing")
    qentry = ttk.Entry(bar, textvariable=q_var, width=30)
    qentry.pack(side="left")

    ttk.Label(bar, text="Level:").pack(side="left", padx=(12, 4))
    level_var = tk.StringVar(value="(any)")
    ttk.Combobox(bar, textvariable=level_var, state="readonly", width=10,
                 values=["(any)", "DEBUG", "INFO", "WARNING", "ERROR",
                         "CRITICAL"]).pack(side="left")

    ttk.Label(bar, text="Max rows:").pack(side="left", padx=(12, 4))
    max_var = tk.StringVar(value="500")
    ttk.Entry(bar, textvariable=max_var, width=8).pack(side="left")

    ttk.Button(bar, text="Apply", command=lambda: reload()).pack(side="left",
                                                                   padx=8)
    ttk.Button(bar, text="Refresh", command=lambda: reload()).pack(side="right")

    cols = ("ts", "level", "logger", "msg")
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=20)
    for k, lbl, w in [
        ("ts", "When", 180),
        ("level", "Level", 80),
        ("logger", "Source", 320),
        ("msg", "Message", 720),
    ]:
        tree.heading(k, text=lbl)
        tree.column(k, width=w, anchor="w")
    tree.pack(fill="both", expand=True, padx=8, pady=4)

    summary_var = tk.StringVar()
    ttk.Label(parent, textvariable=summary_var,
              foreground="#666").pack(anchor="w", padx=8)

    def reload() -> None:
        for it in tree.get_children():
            tree.delete(it)
        q = q_var.get().strip().lower()
        lv = level_var.get()
        try:
            cap = max(50, int(max_var.get().strip()))
        except ValueError:
            cap = 500

        try:
            lines = _read_log_lines()
        except Exception as e:
            logger.exception("Audit log read failed")
            messagebox.showerror("Audit log",
                                  f"Could not read log:\n\n{e}",
                                  parent=gui_instance.root)
            return

        # Iterate from newest first.
        kept = 0
        for raw in reversed(lines):
            m = LINE_RE.match(raw)
            if not m:
                continue
            level = m.group('level')
            if lv != "(any)" and level != lv:
                continue
            msg = m.group('msg')
            src = m.group('logger')
            if q and q not in msg.lower() and q not in src.lower():
                continue
            tree.insert("", "end", values=(
                m.group('ts'), level, src, msg))
            kept += 1
            if kept >= cap:
                break
        summary_var.set(
            f"Showing {kept} row(s) "
            f"(filter={q!r}, level={lv}, cap={cap})")

    qentry.bind("<Return>", lambda _e: reload())
    reload()


def _read_log_lines() -> list[str]:
    """Concatenate the current app.log and any rotated siblings."""
    log_dir = _resolve_log_dir()
    if log_dir is None or not log_dir.is_dir():
        return []
    lines: list[str] = []
    paths: list[Path] = []
    # Rotated files first (oldest-looking by suffix), then current.
    for p in sorted(log_dir.glob("app.*.log")):
        paths.append(p)
    cur = log_dir / "app.log"
    if cur.exists():
        paths.append(cur)
    for p in paths:
        try:
            with p.open("r", encoding="utf-8", errors="replace") as f:
                lines.extend(line.rstrip("\n") for line in f)
        except OSError:
            logger.exception("Could not read log file %s", p)
    return lines


def _resolve_log_dir() -> Path | None:
    try:
        from education_system.systems.university.infrastructure import paths
        ld = getattr(paths, 'LOG_DIR', None)
        if ld:
            return Path(ld)
    except Exception:
        logger.debug("paths module unavailable", exc_info=True)
    # Fallback to the conventional repo path.
    return Path("education_system/post_18/university_system/logs")
