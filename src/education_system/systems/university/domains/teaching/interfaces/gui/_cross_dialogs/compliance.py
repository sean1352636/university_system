"""Panels for incident evidence and open cases."""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk


class IncidentEvidencePanel(ttk.Frame):
    """Show DM-linked documents for a Health & Safety / First Aid incident.

    Reads through ``document_bus.get_documents_for(domain, incident_id)``
    so both H&S and First Aid views see the same evidence pack.
    Refreshes on ``dm.document.changed``.
    """

    def __init__(self, master: tk.Misc, *,
                 incident_id: int | str | None = None,
                 domain: str = "incident",
                 listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._incident_id: str | None = None
        self._domain = domain

        self._heading_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.incident_evidence', default="Incident evidence"))
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        cols = ("name", "type", "uploaded", "uploaded_by")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=5)
        for c, w in zip(cols, (240, 120, 110, 120)):
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
                    subscribe_tk, EVENT_DOCUMENT_CHANGED,
                )

                def _on_change(**payload):
                    if (str(payload.get("ref_id") or "") in
                            ("", str(self._incident_id or ""))
                            or payload.get("domain") == self._domain):
                        self.refresh()

                subscribe_tk(EVENT_DOCUMENT_CHANGED, self, _on_change)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        if incident_id is not None:
            self.set_incident(incident_id, domain=domain)

    def set_incident(self, incident_id: int | str, *,
                     domain: str | None = None) -> None:
        self._incident_id = str(incident_id)
        if domain:
            self._domain = domain
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._empty_var.set("")
        if not self._incident_id:
            self._heading_var.set("Incident evidence")
            return
        self._heading_var.set(
            f"Incident evidence — {self._domain} #{self._incident_id}"
        )

        try:
            from education_system.systems.university.services.bus.document_bus import (
                get_documents_for,
            )
            docs = get_documents_for(self._domain, self._incident_id)
        except Exception as exc:
            self._empty_var.set(f"(unavailable: {exc})")
            return

        if not docs:
            self._empty_var.set("No evidence linked yet.")
            return
        for d in docs:
            self._tree.insert("", "end", values=(
                d.get("document_name") or "",
                d.get("document_type") or "",
                (d.get("upload_date") or "")[:10],
                d.get("uploaded_by") or "",
            ))


class OpenCasesPanel(ttk.Frame):
    """Inline summary of open academic integrity + disciplinary cases
    against one subject.

    Reads via ``cases_bus.list_open(subject_id)`` so it covers both
    unsettled ``integrity_cases`` and open ``disciplinary_records``. Auto-refreshes on
    ``case.opened`` / ``case.closed`` / ``case.sanction.applied``.

    Embed wherever a person's record is displayed: HR staff profile,
    Grade Tracking student row, advisor view, etc.
    """

    _SEVERITY_FG = {
        "Critical": "#c0392b",
        "Major":    "#d97706",
        "Moderate": "#0066cc",
    }

    def __init__(self, master: tk.Misc,
                 subject_id: str | int | None = None,
                 *, listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._subject_id: str | None = None

        self._heading_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.open_cases', default="Open cases"))
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        cols = ("kind", "case_id", "offense", "severity", "status", "opened_on")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=5)
        for c, w in zip(cols, (130, 80, 160, 90, 100, 100)):
            self._tree.heading(c, text=c.replace("_", " ").capitalize())
            self._tree.column(c, width=w, anchor="w")
        for sev, fg in self._SEVERITY_FG.items():
            self._tree.tag_configure(sev, foreground=fg)
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._empty_var = tk.StringVar(value="")
        ttk.Label(
            self, textvariable=self._empty_var, foreground="#7f8c8d",
        ).pack(anchor="w", padx=10)

        if listen_to_events:
            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    subscribe_tk,
                    EVENT_CASE_OPENED, EVENT_CASE_CLOSED,
                    EVENT_SANCTION_APPLIED,
                )

                def _on_change(**payload):
                    sid = payload.get("subject_id")
                    if (self._subject_id and
                            (sid is None or str(sid) == self._subject_id)):
                        self.refresh()

                for evt in (EVENT_CASE_OPENED, EVENT_CASE_CLOSED,
                            EVENT_SANCTION_APPLIED):
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
        self._empty_var.set("")
        if not self._subject_id:
            self._heading_var.set("Open cases")
            return
        self._heading_var.set(f"Open cases — {self._subject_id}")

        try:
            from education_system.systems.university.services.bus.cases_bus import (
                list_open,
            )
            cases = list_open(self._subject_id)
        except Exception as exc:
            self._empty_var.set(f"(unavailable: {exc})")
            return

        if not cases:
            self._empty_var.set("No open cases.")
            return
        for c in cases:
            sev = c.get("severity") or ""
            tag = (sev,) if sev in self._SEVERITY_FG else ()
            self._tree.insert("", "end", values=(
                c.get("kind") or "",
                c.get("case_id") or "",
                c.get("offense_type") or "",
                sev,
                c.get("status") or "",
                (c.get("opened_on") or "")[:10],
            ), tags=tag)


__all__ = [
    "IncidentEvidencePanel",
    "OpenCasesPanel",
]
