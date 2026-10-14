"""Tkinter views for Live Ratio Alerts (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). A live compliance board: the room-by-room picture on top (children
counted, adults available, absences, headroom) and the ranked alert list below,
breaches in red — the GUI counterpart of ``ratio_alerts_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.nursery.domain.operations.ratio_alerts import (
    ratio_alerts as data,
)
from education_system.systems.nursery.domain.operations.ratio_alerts.ratio_alerts import (
    CATEGORIES,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        parent = getattr(host, "root", None)
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror(func.__name__, str(e), parent=parent)
            except Exception:
                logger.debug("Could not show validation dialog", exc_info=True)
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=parent)
            except Exception:
                logger.debug("Could not show error dialog", exc_info=True)
    return wrapper


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _header(parent: ttk.Frame, title: str) -> None:
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _tree(parent: ttk.Frame, spec: list[tuple[str, str, int]],
          height: int) -> ttk.Treeview:
    cols = tuple(c for c, _l, _w in spec)
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=height)
    for c, label, w in spec:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.tag_configure("breach", foreground="#c0392b")
    tree.tag_configure("warning", foreground="#b9770e")
    tree.tag_configure("info", foreground="#5d6d7e")
    tree.tag_configure("ok", foreground="#1e7e34")
    tree.pack(fill="both", expand=True)
    return tree


@_safe_view
def open_manager(host, day: str | None = None) -> None:
    logger.debug("GUI: ratio_alerts open_manager")
    root = _clear(host)
    _header(root, "Live Ratio Alerts")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Date:").pack(side="left")
    date_var = tk.StringVar(value=day or data._today())
    ttk.Entry(bar, textvariable=date_var, width=13).pack(side="left", padx=6)
    ttk.Label(bar, text="Category:").pack(side="left", padx=(8, 0))
    cat_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=cat_var, values=["", *CATEGORIES],
                 state="readonly", width=16).pack(side="left", padx=6)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(date_var.get(), cat_var.get(), banner,
                                        detail, rooms, alerts)).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Breaches only",
               command=lambda: (cat_var.set(""),
                                _refresh(date_var.get(), "", banner, detail,
                                         rooms, alerts,
                                         severity="breach"))).pack(
        side="left", padx=2)

    banner = ttk.Label(root, font=("", 12, "bold"))
    banner.pack(anchor="w", pady=(0, 2))
    detail = ttk.Label(root, foreground="#555")
    detail.pack(anchor="w", pady=(0, 8))

    ttk.Label(root, text="Rooms", font=("", 11, "bold")).pack(anchor="w")
    rooms = _tree(root, [
        ("room", "Room", 160), ("ratio", "Ratio", 70),
        ("children", "Children", 80), ("staff", "Adults", 75),
        ("absent", "Absent", 70), ("required", "Required", 80),
        ("headroom", "Headroom", 85), ("source", "Counted from", 110),
        ("status", "Status", 130),
    ], height=6)

    ttk.Label(root, text="Alerts", font=("", 11, "bold")).pack(
        anchor="w", pady=(10, 0))
    alerts = _tree(root, [
        ("severity", "Severity", 90), ("category", "Cause", 130),
        ("room", "Room", 140), ("message", "What is happening", 430),
    ], height=10)
    alerts.bind("<Double-1>", lambda _e: _show_detail(host, alerts))

    _refresh(date_var.get(), cat_var.get(), banner, detail, rooms, alerts)
    host.status_var.set("Ratio alerts loaded")


# Alert details are keyed by tree row id so the double-click handler can show
# the full explanation without re-running every rule.
_DETAILS: dict[str, tuple[str, str]] = {}


def _refresh(day: str, category: str, banner: ttk.Label, detail: ttk.Label,
             rooms: ttk.Treeview, alerts: ttk.Treeview,
             severity: str | None = None) -> None:
    for t in (rooms, alerts):
        for i in t.get_children():
            t.delete(i)
    _DETAILS.clear()
    try:
        s = data.summary(day)
        states = data.room_states(s["date"])
        rows = data.list_alerts(s["date"], severity=severity,
                                category=category or None)
    except ValidationError as e:
        banner.config(text=str(e), foreground="#a00")
        detail.config(text="")
        return
    except Exception:
        logger.exception("Could not refresh ratio alerts")
        banner.config(text="Could not load — see logs.", foreground="#a00")
        detail.config(text="")
        return

    if s["breaches"]:
        banner.config(text=f"⚠ {s['breaches']} live breach(es) across "
                           f"{s['rooms_in_breach']} room(s) on {s['date']}",
                      foreground="#c0392b")
    elif s["warnings"]:
        banner.config(text=f"{s['warnings']} warning(s) on {s['date']} — no "
                           "room is under ratio yet", foreground="#b9770e")
    else:
        banner.config(text=f"All rooms meet their ratio on {s['date']}",
                      foreground="#1e7e34")
    detail.config(
        text=f"Children: {s['children']} (from the {s['counted_from']})   "
             f"Adults available: {s['staff_available']} (from the "
             f"{s['staff_from']})   Staff absent: {s['staff_absent']}   "
             f"Rooms on the edge: {s['rooms_on_edge']}")

    for st in states:
        if st.compliant is None:
            tag, state = "warning", "no ratio set"
        elif st.compliant:
            tag, state = "ok", "OK"
        else:
            tag, state = "breach", f"UNDER by {st.shortfall}"
        rooms.insert("", "end", iid=st.room, tags=(tag,), values=(
            st.room, st.staff_ratio or "-", st.children_counted,
            st.staff_available, st.staff_absent,
            "-" if st.required_staff is None else st.required_staff,
            "-" if st.spare_places is None else st.spare_places,
            st.counted_from, state))

    for i, a in enumerate(rows):
        iid = f"alert-{i}"
        _DETAILS[iid] = (a.message, a.detail)
        alerts.insert("", "end", iid=iid, tags=(a.severity,), values=(
            a.severity.upper(), a.category, a.room or "-", a.message))


def _show_detail(host, alerts: ttk.Treeview) -> None:
    sel = alerts.focus()
    entry = _DETAILS.get(sel)
    if entry is None:
        return
    message, detail = entry
    messagebox.showinfo(message, detail or "No further detail recorded.",
                        parent=host.root)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Live Ratio Alerts", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Live Ratio Alerts from the navigation menu."
              ).pack(anchor="w")
    return frame
