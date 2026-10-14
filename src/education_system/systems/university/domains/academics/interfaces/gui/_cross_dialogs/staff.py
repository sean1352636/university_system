"""Staff-facing panels: research output, workload, certifications."""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk


class ResearchOutputPanel(ttk.Frame):
    """Recent publications for an instructor or for a module's PI.

    Embed in the Course/Module detail page so a student sees the
    research-led context, or in the Library to inform journal
    subscription decisions.
    """

    def __init__(self, master: tk.Misc, *,
                 instructor_id: int | str | None = None,
                 module_code: str | None = None,
                 limit: int = 10) -> None:
        super().__init__(master)
        self._instructor_id = instructor_id
        self._module_code = module_code
        self._limit = limit

        self._heading_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.recent_research_outputs', default="Recent research outputs"))
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        cols = ("year", "title", "venue")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=6)
        for c, w in zip(cols, (60, 360, 200)):
            self._tree.heading(c, text=c.capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._empty_var = tk.StringVar(value="")
        ttk.Label(
            self, textvariable=self._empty_var, foreground="#7f8c8d",
        ).pack(anchor="w", padx=10)

        if instructor_id or module_code:
            self.refresh()

    def set_target(self, *, instructor_id: int | str | None = None,
                   module_code: str | None = None) -> None:
        self._instructor_id = instructor_id
        self._module_code = module_code
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._empty_var.set("")

        instr = self._instructor_id
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                # Resolve instructor from module if needed.
                if instr is None and self._module_code:
                    row = conn.execute(
                        "SELECT instructor_id FROM module_schedule "
                        "WHERE module_code = ? "
                        "  AND instructor_id IS NOT NULL "
                        "ORDER BY rowid DESC LIMIT 1",
                        (self._module_code,),
                    ).fetchone()
                    if row:
                        instr = row[0]

                if instr is None:
                    self._empty_var.set("No instructor / module supplied.")
                    return

                self._heading_var.set(f"Recent research — instructor {instr}")
                rows = conn.execute(
                    "SELECT publication_date, title, "
                    "       COALESCE(journal_name, conference_name, '') AS venue "
                    "FROM research_publications rp "
                    "JOIN research_projects pr ON rp.project_id = pr.project_id "
                    "WHERE pr.principal_investigator_id = ? "
                    "ORDER BY publication_date DESC LIMIT ?",
                    (instr, self._limit),
                ).fetchall()
        except Exception as exc:
            self._empty_var.set(f"(unavailable: {exc})")
            return

        if not rows:
            self._empty_var.set("No publications recorded.")
            return
        for r in rows:
            year = (r["publication_date"] or "")[:4]
            self._tree.insert("", "end", values=(
                year, r["title"] or "—", r["venue"] or "",
            ))


class StaffWorkloadPanel(ttk.Frame):
    """Inline summary of one staff member's teaching load.

    Wraps the existing ``instructor_workload`` cross-service so HR
    can drop it into the staff detail page, and Module Scheduling
    can drop it into the instructor-edit dialog. Auto-refreshes on
    ``hr.staff_availability.changed`` / ``module.schedule.changed``.
    """

    def __init__(self, master: tk.Misc,
                 instructor_id: int | str | None = None,
                 *, listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._instructor_id: int | str | None = None

        self._heading_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.staff_workload', default="Staff workload"))
        self._totals_var = tk.StringVar(value="—")
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))
        ttk.Label(self, textvariable=self._totals_var).pack(
            anchor="w", padx=10, pady=(0, 4),
        )

        cols = ("module", "day", "time", "room")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=5)
        for c, w in zip(cols, (90, 90, 110, 130)):
            self._tree.heading(c, text=c.capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        if listen_to_events:
            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    subscribe_tk,
                    EVENT_STAFF_AVAILABILITY_CHANGED,
                    EVENT_MODULE_SCHEDULE_CHANGED,
                )

                def _on_change(**_payload):
                    if self._instructor_id is not None:
                        self.refresh()

                for evt in (EVENT_STAFF_AVAILABILITY_CHANGED,
                            EVENT_MODULE_SCHEDULE_CHANGED):
                    subscribe_tk(evt, self, _on_change)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        if instructor_id is not None:
            self.set_instructor(instructor_id)

    def set_instructor(self, instructor_id: int | str) -> None:
        self._instructor_id = instructor_id
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        if self._instructor_id is None:
            self._heading_var.set("Staff workload")
            self._totals_var.set("—")
            return
        try:
            from education_system.systems.university.domains.academics.interfaces.gui._cross_services import (
                instructor_workload,
            )
            data = instructor_workload(instructor_id=int(self._instructor_id))
        except Exception:
            data = None
        if not data:
            self._totals_var.set("(unavailable)")
            return
        info = data.get("instructor", {})
        totals = data.get("totals", {})
        self._heading_var.set(
            f"Staff workload — {info.get('name') or self._instructor_id}"
        )
        self._totals_var.set(
            f"{totals.get('teaching_hours_per_week', 0):.1f} h/wk · "
            f"{totals.get('slot_count', 0)} slots · "
            f"{totals.get('modules', 0)} modules · "
            f"{totals.get('exam_panels', 0)} exam panels"
        )
        for s in data.get("teaching_slots", []):
            self._tree.insert("", "end", values=(
                s.get("module_code") or "",
                s.get("day_of_week") or "",
                f"{s.get('start_time') or ''}–{s.get('end_time') or ''}",
                s.get("room") or "",
            ))


class StaffCertificationsPanel(ttk.Frame):
    """Inline view of one staff member's certifications + expiry warnings.

    Pulls from ``cert_bus.list_certifications_for`` and tints rows
    that have expired or expire within 30 days. Auto-refreshes on
    ``hr.certification.changed``.
    """

    _EXPIRED_FG = "#c0392b"
    _SOON_FG = "#d97706"

    def __init__(self, master: tk.Misc,
                 staff_id: str | int | None = None,
                 *, listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._staff_id: str | None = None

        self._heading_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.certifications', default="Certifications"))
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        cols = ("kind", "issued", "expires", "issuer")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=5)
        for c, w in zip(cols, (160, 110, 110, 160)):
            self._tree.heading(c, text=c.capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.tag_configure("expired", foreground=self._EXPIRED_FG)
        self._tree.tag_configure("soon", foreground=self._SOON_FG)
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        if listen_to_events:
            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    subscribe_tk, EVENT_CERT_CHANGED,
                )
                subscribe_tk(EVENT_CERT_CHANGED, self,
                             lambda **_: self.refresh())
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        if staff_id is not None:
            self.set_staff(staff_id)

    def set_staff(self, staff_id: str | int) -> None:
        self._staff_id = str(staff_id)
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        if not self._staff_id:
            self._heading_var.set("Certifications")
            return
        self._heading_var.set(f"Certifications — staff {self._staff_id}")

        try:
            from datetime import date as _date, timedelta as _td
            from education_system.systems.university.services.bus.cert_bus import (
                list_certifications_for,
            )
            today = _date.today()
            soon = today + _td(days=30)
            for c in list_certifications_for(self._staff_id):
                expires = c.get("expires_on") or ""
                tag = ()
                if expires:
                    try:
                        d = _date.fromisoformat(expires[:10])
                        if d < today:
                            tag = ("expired",)
                        elif d <= soon:
                            tag = ("soon",)
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)
                self._tree.insert("", "end", values=(
                    c.get("kind") or "",
                    c.get("issued_on") or "",
                    expires,
                    c.get("issuer") or "",
                ), tags=tag)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)


__all__ = [
    "ResearchOutputPanel",
    "StaffWorkloadPanel",
    "StaffCertificationsPanel",
]
