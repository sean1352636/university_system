"""Manage Collection Agencies dialog, backed by the real agencies API.

``compliance.py`` used to open a dialog that listed three hard-coded sample
agencies, "added" rows only to the Treeview, and "edited" by showing an info
box. The command-line collections menu already uses the non-interactive API
in ``domain/reporting/revenue_analytics/agencies.py``; this dialog is the GUI
face of that same API, so both interfaces read and write ``collection_agencies``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.platform.delivery.gui.form_dialog import Field, ask_form
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.platform.delivery.gui.treeview_helpers import (
    fill_tree,
    make_tree,
    selected_id,
)
from education_system.systems.university.infrastructure.i18n import get_text as _

COLUMNS = ["agency_id", "agency_name", "contact_email", "contact_phone",
           "commission_rate", "minimum_amount", "status"]


def _t(key: str, default: str, **kwargs) -> str:
    """``get_text`` leaves a missing key's default unformatted; do it here."""
    text = _(key, default=default)
    return text.format(**kwargs) if kwargs else text


def _api():
    from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics import (
        agencies,
    )
    return agencies


def _agency_fields(current: dict | None = None) -> list[Field]:
    cur = current or {}
    return [
        Field("agency_name", _t("finance_gui.compliance.agency_name_label", "Agency name"),
              default=str(cur.get("agency_name", ""))),
        Field("contact_email", _t("finance_gui.compliance.email_label", "Contact email"),
              default=str(cur.get("contact_email") or ""), optional=True),
        Field("contact_phone", _t("finance_gui.compliance.phone_label", "Contact phone"),
              default=str(cur.get("contact_phone") or ""), optional=True),
        Field("commission_rate", _t("finance_gui.compliance.commission_label", "Commission %"),
              kind="float", default=str(cur.get("commission_rate", 0) or 0)),
        Field("minimum_amount", _t("finance_gui.compliance.minimum_amount_label", "Minimum amount"),
              kind="float", default=str(cur.get("minimum_amount", 0) or 0)),
    ]


class ManageAgenciesDialog:
    """List + add/edit/activate/remove over ``collection_agencies``."""

    def __init__(self, parent, on_change=None):
        self.on_change = on_change
        self.top = tk.Toplevel(parent)
        self.top.title(_t("finance_gui.compliance.manage_agencies_title", "Manage Collection Agencies"))
        self.top.geometry("960x600")
        self.top.transient(parent)

        ttk.Label(self.top,
                  text=_t("finance_gui.compliance.agencies_management_header", "Collection Agencies"),
                  font=("TkDefaultFont", 14, "bold")).pack(pady=10)

        # Action bar first, so it keeps its height when the table expands.
        bar = ttk.Frame(self.top)
        bar.pack(fill="x", padx=10, pady=5)
        for label, cmd in (
            (_t("finance_gui.compliance.btn_add_agency", "Add"), self.add),
            (_t("finance_gui.compliance.btn_edit_agency", "Edit"), self.edit),
            (_t("finance_gui.compliance.btn_toggle_agency", "Activate / Deactivate"), self.toggle_active),
            (_t("finance_gui.compliance.btn_remove_agency", "Remove"), self.remove),
            (_t("finance_gui.compliance.btn_refresh", "Refresh"), self.refresh),
        ):
            ttk.Button(bar, text=label, command=cmd).pack(side="left", padx=4)
        self.show_inactive = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text=_t("finance_gui.compliance.show_inactive", "Show inactive"),
                        variable=self.show_inactive, command=self.refresh).pack(side="right", padx=4)

        body = ttk.Frame(self.top)
        body.pack(fill="both", expand=True, padx=10, pady=5)
        self.tree = make_tree(body, COLUMNS)
        self.tree.column("agency_id", width=70, stretch=False)
        self.tree.bind("<Double-1>", lambda _e: self.edit())

        ttk.Button(self.top, text=_("finance_gui.buttons.close", default="Close"),
                   command=self.top.destroy).pack(pady=8)
        self.refresh()

    # -- data -----------------------------------------------------------
    def refresh(self):
        try:
            rows = _api().list_agencies(include_inactive=self.show_inactive.get())
        except Exception as exc:
            messagebox.showerror(_("finance_gui.messages.error", default="Error"),
                                 _t("finance_gui.compliance.failed_manage_agencies",
                                    "Could not load agencies: {error}", error=exc),
                                 parent=self.top)
            rows = []
        for row in rows:
            row["status"] = (_t("finance_gui.compliance.status_active", "Active")
                             if row.get("is_active") else
                             _t("finance_gui.compliance.status_inactive", "Inactive"))
            row["commission_rate"] = f"{float(row.get('commission_rate') or 0):.2f}%"
            row["minimum_amount"] = f"{float(row.get('minimum_amount') or 0):.2f}"
        fill_tree(self.tree, rows, COLUMNS)

    def _changed(self):
        self.refresh()
        if callable(self.on_change):
            try:
                self.on_change()
            except Exception:  # the caller's refresh must not break the dialog
                pass

    def _selected(self) -> dict | None:
        agency_id = selected_id(self.tree)
        if agency_id is None:
            messagebox.showwarning(_("finance_gui.messages.no_selection", default="No selection"),
                                   _t("finance_gui.compliance.no_selection_edit",
                                      "Select an agency first."), parent=self.top)
            return None
        agency = _api().get_agency(agency_id)
        if agency is None:
            messagebox.showerror(_("finance_gui.messages.error", default="Error"),
                                 _t("finance_gui.compliance.agency_missing",
                                    "Agency {id} no longer exists.", id=agency_id), parent=self.top)
            self.refresh()
        return agency

    def _report(self, exc: Exception):
        messagebox.showerror(_("finance_gui.messages.error", default="Error"), str(exc), parent=self.top)

    # -- actions --------------------------------------------------------
    def add(self):
        values = ask_form(self.top, _t("finance_gui.compliance.add_agency_title", "Add Agency"),
                          _agency_fields())
        if not values:
            return
        try:
            _api().create_agency(**values)
        except Exception as exc:
            return self._report(exc)
        messagebox.showinfo(_("finance_gui.messages.success", default="Success"),
                            _t("finance_gui.compliance.agency_added", "Agency '{name}' added.",
                               name=values["agency_name"]), parent=self.top)
        self._changed()

    def edit(self):
        agency = self._selected()
        if agency is None:
            return
        values = ask_form(self.top, _t("finance_gui.compliance.edit_agency_title", "Edit Agency"),
                          _agency_fields(agency))
        if not values:
            return
        try:
            _api().update_agency(agency["agency_id"], **values)
        except Exception as exc:
            return self._report(exc)
        self._changed()

    def toggle_active(self):
        agency = self._selected()
        if agency is None:
            return
        activate = not agency.get("is_active")
        try:
            result = _api().set_agency_active(agency["agency_id"], activate)
        except Exception as exc:
            return self._report(exc)
        if not activate and result.get("open_cases"):
            messagebox.showwarning(
                _("finance_gui.messages.warning", default="Warning"),
                _t("finance_gui.compliance.deactivated_with_open_cases",
                   "'{name}' deactivated. It still has {count} open case(s); reassign them.",
                   name=agency["agency_name"], count=result["open_cases"]), parent=self.top)
        self._changed()

    def remove(self):
        agency = self._selected()
        if agency is None:
            return
        if not messagebox.askyesno(
                _t("finance_gui.compliance.confirm_remove_title", "Remove agency"),
                _t("finance_gui.compliance.confirm_remove_message",
                   "Remove '{name}' permanently?", name=agency["agency_name"]), parent=self.top):
            return
        try:
            _api().delete_agency(agency["agency_id"])
        except ValueError as exc:
            # Referenced by cases: the API refuses; offer the safe alternative.
            if agency.get("is_active") and messagebox.askyesno(
                    _t("finance_gui.compliance.cannot_remove_title", "Cannot remove"),
                    _t("finance_gui.compliance.cannot_remove_offer_deactivate",
                       "{error}\n\nDeactivate it instead?", error=exc), parent=self.top):
                return self.toggle_active()
            return self._report(exc)
        except Exception as exc:
            return self._report(exc)
        messagebox.showinfo(_("finance_gui.messages.success", default="Success"),
                            _t("finance_gui.compliance.agency_removed", "Agency removed."),
                            parent=self.top)
        self._changed()


def open_manage_agencies(parent, on_change=None) -> ManageAgenciesDialog:
    return ManageAgenciesDialog(parent, on_change=on_change)


__all__ = ["ManageAgenciesDialog", "open_manage_agencies"]
