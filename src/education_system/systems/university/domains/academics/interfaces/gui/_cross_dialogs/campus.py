"""Campus service panels: resources, trips and parking, restaurant."""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk


class ResourceAvailabilityPanel(ttk.Frame):
    """Shows library availability for a textbook ISBN or a module's reading list.

    Pass ``isbn=`` for a single title, or ``module_code=`` to walk the
    module's textbook list. Auto-refreshes on ``library.loan.changed``
    and ``library.reading_list.changed``.
    """

    def __init__(self, master: tk.Misc, *,
                 isbn: str | None = None,
                 module_code: str | None = None,
                 listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._isbn: str | None = None
        self._module_code: str | None = None

        self._heading_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.library_availability', default="Library availability"))
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        cols = ("title", "author", "on_loan", "available")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=6)
        for c, w in zip(cols, (260, 160, 80, 80)):
            self._tree.heading(c, text=c.replace("_", " ").capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._empty_var = tk.StringVar(value="")
        ttk.Label(
            self, textvariable=self._empty_var, foreground="#7f8c8d",
        ).pack(anchor="w", padx=10)

        if listen_to_events:
            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    subscribe_tk, EVENT_LOAN_CHANGED, EVENT_READING_LIST_CHANGED,
                )

                def _on_change(**_payload):
                    if self._isbn or self._module_code:
                        self.refresh()

                for evt in (EVENT_LOAN_CHANGED, EVENT_READING_LIST_CHANGED):
                    subscribe_tk(evt, self, _on_change)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        if isbn or module_code:
            self.set_target(isbn=isbn, module_code=module_code)

    def set_target(self, *, isbn: str | None = None,
                   module_code: str | None = None) -> None:
        self._isbn = isbn or None
        self._module_code = module_code or None
        if self._isbn:
            self._heading_var.set(f"Library availability — ISBN {self._isbn}")
        elif self._module_code:
            self._heading_var.set(
                f"Library availability — reading list for {self._module_code}"
            )
        else:
            self._heading_var.set("Library availability")
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._empty_var.set("")

        rows: list[tuple[str, str, int, int]] = []
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                if self._module_code:
                    books = conn.execute(
                        "SELECT isbn, title, author FROM textbooks "
                        "WHERE module_code = ? ORDER BY required DESC, title",
                        (self._module_code,),
                    ).fetchall()
                elif self._isbn:
                    books = conn.execute(
                        "SELECT isbn, title, author FROM textbooks "
                        "WHERE isbn = ? LIMIT 1",
                        (self._isbn,),
                    ).fetchall()
                else:
                    books = []

                for b in books:
                    isbn = b["isbn"]
                    on_loan_row = conn.execute(
                        "SELECT COUNT(*) FROM book_loans bl "
                        "JOIN books bk ON bl.book_id = bk.book_id "
                        "WHERE bk.isbn = ? AND bl.return_date IS NULL",
                        (isbn,),
                    ).fetchone() if isbn else None
                    on_loan = int(on_loan_row[0] or 0) if on_loan_row else 0
                    total_row = conn.execute(
                        "SELECT COUNT(*) FROM books WHERE isbn = ?",
                        (isbn,),
                    ).fetchone() if isbn else None
                    total = int(total_row[0] or 0) if total_row else 0
                    rows.append((
                        b["title"] or "—",
                        b["author"] or "—",
                        on_loan,
                        max(0, total - on_loan),
                    ))
        except Exception as exc:
            self._empty_var.set(f"(unavailable: {exc})")
            return

        if not rows:
            self._empty_var.set("No reading-list titles found.")
            return
        for title, author, on_loan, available in rows:
            self._tree.insert("", "end", values=(title, author, on_loan, available))


class TripsAndParkingPanel(ttk.Frame):
    """Inline view of upcoming trips + active parking permits + fines.

    Refreshes on ``trip.created``, ``trip.registration.changed``,
    ``parking.violation``, and ``finance.charge.raised`` (fee paid).
    Embed alongside ``EngagementsPanel`` / ``OpenCasesPanel`` on
    student or staff profile pages.
    """

    def __init__(self, master: tk.Misc,
                 subject_id: str | int | None = None,
                 *, listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._subject_id: str | None = None

        self._heading_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.trips_parking', default="Trips & parking"))
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        self._summary_var = tk.StringVar(value="—")
        ttk.Label(self, textvariable=self._summary_var).pack(
            anchor="w", padx=10, pady=(0, 4),
        )

        cols = ("kind", "ref", "info", "when")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=5)
        for c, w in zip(cols, (90, 110, 280, 110)):
            self._tree.heading(c, text=c.capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.tag_configure("violation", foreground="#c0392b")
        self._tree.tag_configure("upcoming", foreground="#0066cc")
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        if listen_to_events:
            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    subscribe_tk,
                    EVENT_TRIP_CREATED, EVENT_TRIP_REGISTRATION_CHANGED,
                    EVENT_PARKING_VIOLATION, EVENT_CHARGE_RAISED,
                )

                def _on_change(**payload):
                    sid = (payload.get("student_id")
                           or payload.get("holder_id"))
                    if (self._subject_id and
                            (sid is None or str(sid) == self._subject_id)):
                        self.refresh()

                for evt in (EVENT_TRIP_CREATED,
                            EVENT_TRIP_REGISTRATION_CHANGED,
                            EVENT_PARKING_VIOLATION,
                            EVENT_CHARGE_RAISED):
                    subscribe_tk(evt, self, _on_change)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        if subject_id is not None:
            self.set_subject(subject_id)

    def set_subject(self, subject_id: str | int) -> None:
        self._subject_id = str(subject_id) if subject_id is not None else None
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        if not self._subject_id:
            self._heading_var.set("Trips & parking")
            self._summary_var.set("—")
            return
        self._heading_var.set(f"Trips & parking — {self._subject_id}")

        try:
            from education_system.systems.university.services.bus.trip_bus import (
                list_registrations_for,
            )
            from education_system.systems.university.services.bus.parking_bus import (
                list_permits_for, outstanding_parking_charges,
            )
            regs = list_registrations_for(self._subject_id)
            permits = list_permits_for(self._subject_id)
            fines = outstanding_parking_charges(self._subject_id)
        except Exception:
            regs, permits, fines = [], [], []

        active_regs = [r for r in regs if r.get("status") == "registered"]
        active_permits = [p for p in permits
                          if p.get("status") == "active"
                          or p.get("active_status") == 1]
        fine_total = sum(float(f.get("amount") or 0) for f in fines)
        self._summary_var.set(
            f"{len(active_regs)} active trip(s) · "
            f"{len(active_permits)} permit(s) · "
            f"{len(fines)} fine(s) £{fine_total:,.2f}"
        )

        for r in regs:
            tag = ("upcoming",) if r.get("status") == "registered" else ()
            self._tree.insert("", "end", values=(
                "trip",
                f"#{r.get('trip_id')}",
                f"{r.get('trip_name') or '?'} → {r.get('destination') or '?'}",
                (r.get("start_date") or "")[:10],
            ), tags=tag)
        for p in permits:
            self._tree.insert("", "end", values=(
                "permit",
                f"#{p.get('permit_id')}",
                f"{p.get('plate') or '?'} ({p.get('zone') or ''}, "
                f"{p.get('permit_type') or ''}) — {p.get('status') or ''}",
                (p.get("end_date") or "")[:10],
            ))
        for f in fines:
            self._tree.insert("", "end", values=(
                "fine",
                f.get("reference_id") or "",
                f"£{float(f.get('amount') or 0):,.2f} — "
                f"{f.get('description') or ''}",
                (f.get("created_at") or "")[:10],
            ), tags=("violation",))


class RestaurantPanel(ttk.Frame):
    """Inline view of meal-plan balance + recent POS + today's menu.

    Auto-refreshes on ``restaurant.meal_plan.changed``,
    ``finance.charge.raised`` (filtered to restaurant sources), and
    ``calendar.changed`` (menu publish).
    """

    def __init__(self, master: tk.Misc,
                 student_id: str | int | None = None,
                 *, listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._student_id: str | None = None

        self._heading_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.restaurant', default="Restaurant"))
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        self._summary_var = tk.StringVar(value="—")
        ttk.Label(self, textvariable=self._summary_var).pack(
            anchor="w", padx=10, pady=(0, 4),
        )

        cols = ("kind", "info", "when")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=5)
        for c, w in zip(cols, (90, 380, 110)):
            self._tree.heading(c, text=c.capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        if listen_to_events:
            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    subscribe_tk,
                    EVENT_MEAL_PLAN_CHANGED, EVENT_CHARGE_RAISED,
                    EVENT_CALENDAR_CHANGED,
                )

                def _on_change(**payload):
                    sid = payload.get("student_id")
                    if (self._student_id and
                            (sid is None or str(sid) == self._student_id)):
                        self.refresh()

                for evt in (EVENT_MEAL_PLAN_CHANGED, EVENT_CHARGE_RAISED,
                            EVENT_CALENDAR_CHANGED):
                    subscribe_tk(evt, self, _on_change)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        if student_id is not None:
            self.set_student(student_id)

    def set_student(self, student_id: str | int) -> None:
        self._student_id = str(student_id) if student_id is not None else None
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        if not self._student_id:
            self._heading_var.set("Restaurant")
            self._summary_var.set("—")
            return
        self._heading_var.set(f"Restaurant — {self._student_id}")

        balance = 0.0
        menu_rows: list[dict] = []
        recent_pos: list[dict] = []
        try:
            from education_system.systems.university.plugins.campus_commerce.services.restaurant_bus import (
                meal_plan_balance, menu_for,
            )
            balance = meal_plan_balance(self._student_id)
            menu_rows = menu_for() or []
            from education_system.systems.university.infrastructure.database.db import (
                get_connection,
            )
            with get_connection() as conn:
                for r in conn.execute(
                    "SELECT amount, description, created_at "
                    "FROM student_finance_transactions "
                    "WHERE student_id = ? "
                    "  AND ( description LIKE 'Restaurant POS%' "
                    "    OR description LIKE 'Meal-plan top-up%' ) "
                    "ORDER BY created_at DESC LIMIT 5",
                    (self._student_id,),
                ).fetchall():
                    recent_pos.append(dict(r))
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        items_today = (
            menu_rows[0]["body"].get("items", []) if menu_rows else []
        )
        self._summary_var.set(
            f"Meal plan: £{balance:,.2f} · "
            f"Recent activity: {len(recent_pos)} · "
            f"Today's menu: {len(items_today)} item(s)"
        )

        for r in recent_pos:
            self._tree.insert("", "end", values=(
                "tx",
                f"£{float(r.get('amount') or 0):,.2f} — "
                f"{r.get('description') or ''}",
                (r.get("created_at") or "")[:10],
            ))
        for item in items_today[:6]:
            self._tree.insert("", "end", values=(
                "menu",
                str(item),
                (menu_rows[0].get("date") or "")[:10] if menu_rows else "",
            ))


__all__ = [
    "ResourceAvailabilityPanel",
    "TripsAndParkingPanel",
    "RestaurantPanel",
]
