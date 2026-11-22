"""Panels for module timelines and the academic period."""

from __future__ import annotations

import logging

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)

from education_system.systems.university.domains.teaching.interfaces.gui._cross_services import (
    module_timeline,
)


class ModuleTimelinePanel(ttk.Frame):
    """Embeddable inline panel showing the timeline for one module.

    Use as a child widget anywhere a host GUI wants to show "what's
    happening for this module" without popping a dialog. Call
    :meth:`set_module` to retarget; refreshes auto-subscribe to the
    relevant bus events when the host root is provided.
    """

    def __init__(self, master: tk.Misc, module_code: str | None = None,
                 *, listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._module_code: str | None = None

        self._heading_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.module_timeline', default="Module timeline"))
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        cols = ("kind", "date", "label", "detail")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (80, 100, 240, 280)):
            self._tree.heading(c, text=c.capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._empty_var = tk.StringVar(value="")
        self._empty_label = ttk.Label(
            self, textvariable=self._empty_var, foreground="#7f8c8d",
        )
        self._empty_label.pack(anchor="w", padx=10)

        if listen_to_events:
            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    subscribe_tk,
                    EVENT_MODULE_SCHEDULE_CHANGED,
                    EVENT_EXAM_CHANGED,
                    EVENT_ASSESSMENT_CHANGED,
                    EVENT_ASSIGNMENT_CHANGED,
                )

                def _on_change(**_payload):
                    if self._module_code:
                        self.refresh()

                for evt in (EVENT_MODULE_SCHEDULE_CHANGED, EVENT_EXAM_CHANGED,
                            EVENT_ASSESSMENT_CHANGED, EVENT_ASSIGNMENT_CHANGED):
                    subscribe_tk(evt, self, _on_change)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        if module_code:
            self.set_module(module_code)

    def set_module(self, module_code: str) -> None:
        self._module_code = module_code or None
        self._heading_var.set(
            f"Module timeline — {module_code}" if module_code
            else "Module timeline"
        )
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        if not self._module_code:
            self._empty_var.set("No module selected.")
            return
        rows = module_timeline(self._module_code)
        if not rows:
            self._empty_var.set("No events recorded for this module.")
            return
        self._empty_var.set("")
        cols = ("kind", "date", "label", "detail")
        for r in rows:
            self._tree.insert("", "end", values=tuple(r.get(c, "") for c in cols))


class AcademicPeriodPanel(ttk.Frame):
    """Compact strip showing the current term + calendar context.

    Embed at the top of every scheduling GUI so the operator sees
    "Term: Spring 2026 · Week 7 · Exam window opens 12 May" without
    scrolling to find it. Refreshes on ``calendar.changed`` and
    ``term.changed``.
    """

    def __init__(self, master: tk.Misc, *,
                 listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._line_var = tk.StringVar(value="—")
        self._lbl = ttk.Label(
            self, textvariable=self._line_var,
            font=("Helvetica", 10, "bold"),
            foreground="#2c3e50",
        )
        self._lbl.pack(anchor="w", padx=8, pady=4)
        # When no term is set the strip is a dead end, so it doubles as a way
        # into the Calendar's Terms screen, which is where terms are defined.
        self._lbl.bind("<Button-1>", self._on_click)

        if listen_to_events:
            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    subscribe_tk, EVENT_CALENDAR_CHANGED, EVENT_TERM_CHANGED,
                )
                subscribe_tk(EVENT_CALENDAR_CHANGED, self, lambda **_: self.refresh())
                subscribe_tk(EVENT_TERM_CHANGED, self, lambda **_: self.refresh())
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        # refresh() performs up to ~62 calendar lookups (current term, week
        # offset, holiday, today's exam window, then a 60-day look-ahead for
        # the next exam window). Defer to after_idle so embedding GUIs can
        # paint before this runs.
        try:
            self.after_idle(self.refresh)
        except tk.TclError:
            self.refresh()

    def refresh(self) -> None:
        bits: list[str] = []
        try:
            from education_system.systems.university.services.bus.academic_state import (
                get_current_term,
            )
            term = get_current_term()
            if term is not None:
                bits.append(f"Term: {term.label()}")
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        try:
            from education_system.systems.university.domains.teaching.interfaces.gui._cross_services import (
                current_period, is_holiday,
            )
            from datetime import date as _date
            today = _date.today().isoformat()
            term_p = current_period("term", on_date=today)
            if term_p:
                # Name the term here too when the state bus had no answer:
                # the Calendar's own academic_terms table is the other place
                # a term can be defined, and the operator should see it named
                # rather than just getting a bare week number.
                if not any(b.startswith("Term: ") for b in bits):
                    label = term_p.get("name") or ""
                    year = term_p.get("academic_year") or ""
                    if label:
                        bits.append(
                            f"Term: {label}" + (f" ({year})" if year else ""))
                # Compute a rough week-of-term number for the operator.
                start = (term_p.get("date_start") or "")[:10]
                if start:
                    try:
                        delta = (_date.fromisoformat(today)
                                 - _date.fromisoformat(start)).days
                        bits.append(f"Week {max(1, delta // 7 + 1)}")
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)
            if is_holiday(today):
                bits.append("⚠ holiday today")
            exam_p = current_period("exam_window", on_date=today)
            if exam_p:
                bits.append(f"exam window open (until {exam_p.get('date_end','')})")
            else:
                # Look ahead 60 days for the next exam window.
                try:
                    from datetime import timedelta as _td
                    for ahead in range(1, 61):
                        d = (_date.fromisoformat(today)
                             + _td(days=ahead)).isoformat()
                        nxt = current_period("exam_window", on_date=d)
                        if nxt:
                            bits.append(f"exam window opens {nxt.get('date_start','')}")
                            break
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        self._has_period = bool(bits)
        self._line_var.set(
            " · ".join(bits) if bits
            else "No active term set — click to open the Calendar and add one")
        try:
            self._lbl.configure(
                foreground="#2c3e50" if bits else "#1a5fb4",
                cursor="" if bits else "hand2")
        except tk.TclError:
            pass


    def _on_click(self, _event=None):
        """Open the Academic Calendar so a term can be defined."""
        if getattr(self, "_has_period", False):
            return
        parent = self.winfo_toplevel()
        try:
            from education_system.systems.university.domains.teaching.interfaces.gui.academic_calendar.main_gui import (
                CalendarGUI,
            )
            window = tk.Toplevel(parent)
            window.title("Academic Calendar")
            # House style for a full portal window (see window_sizing).
            window.geometry("1400x900")
            window.minsize(1200, 800)
            window.transient(parent)
            # Same launch shape as sections_tab / timetables_tab: the GUI is
            # handed the window it should build into.
            CalendarGUI(auth_manager=getattr(self, "auth", None),
                        parent_window=window)
            # Pick up a term defined in there as soon as the window closes.
            window.bind(
                "<Destroy>",
                lambda e, w=window: self.refresh() if e.widget is w else None,
                add="+")
        except Exception:
            logger.warning("could not open the Academic Calendar", exc_info=True)
            from education_system.platform.delivery.gui.parented_dialogs import messagebox
            messagebox.showinfo(
                "Set a term",
                "Terms are defined in the Academic Calendar, under Terms.")


__all__ = [
    "ModuleTimelinePanel",
    "AcademicPeriodPanel",
]
