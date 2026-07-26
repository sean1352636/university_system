"""Tkinter views for Secondary School Assets."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from education_system.platform import branding
from education_system.systems.secondary.domain.governance.assets import (
    assets as data,
)
from education_system.systems.secondary.domain.governance.assets.assets import (
    Asset,
    CATEGORIES,
    CONDITIONS,
    CURRENCY_SYMBOL,
    DEFAULT_CATEGORY,
    DEFAULT_CONDITION,
    DEFAULT_DEPRECIATION_METHOD,
    DEFAULT_MAINTENANCE_OUTCOME,
    DEFAULT_SERVICE_TYPE,
    DEFAULT_STATUS,
    DEPRECIATION_METHODS,
    DISPOSAL_METHODS,
    DISPOSED_STATUSES,
    MAINTENANCE_OUTCOMES,
    MaintenanceEntry,
    SERVICE_TYPES,
    STATUSES,
    ValidationError,
)
from education_system.systems.secondary.domain.staff import (
    staff as _staff_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "In Use":          ("#e6f0ff", "#1a3f8c"),
    "In Storage":      ("#eef0f4", "#444444"),
    "On Loan":         ("#fff7e6", "#7a5800"),
    "Awaiting Repair": ("#fff0d6", "#7a5800"),
    "In Repair":       ("#ffe0b3", "#7a3f00"),
    "Retired":         ("#eeeeee", "#555555"),
    "Disposed":        ("#dddddd", "#222222"),
    "Lost/Stolen":     ("#ffd1d1", "#8c0d0d"),
}


def _money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{CURRENCY_SYMBOL}{v:.2f}"


def _staff_options() -> list[tuple[str, str]]:
    try:
        rows = sorted(_staff_data.list_staff(),
                        key=lambda s: s.staff_id)
    except Exception:
        return []
    return [(s.staff_id, f"{s.staff_id} — {s.full_name}")
            for s in rows]


def open_assets_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Assets — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    AssetsTab(win)


# ── Main tab ──────────────────────────────────────────────────────

class AssetsTab:
    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="both", expand=True,
                          padx=10, pady=10)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=4, pady=(4, 6))

        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_category = ttk.Combobox(
            bar, values=("",) + CATEGORIES,
            state="readonly", width=18)
        self.f_category.current(0)
        self.f_category.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(
            bar, values=("",) + STATUSES,
            state="readonly", width=16)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Condition:").pack(side="left")
        self.f_condition = ttk.Combobox(
            bar, values=("",) + CONDITIONS,
            state="readonly", width=12)
        self.f_condition.current(0)
        self.f_condition.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Location:").pack(side="left")
        self.f_location = ttk.Entry(bar, width=14)
        self.f_location.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Search:").pack(side="left")
        self.f_search = ttk.Entry(bar, width=18)
        self.f_search.pack(side="left", padx=(2, 8))

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(
            side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True,
                            padx=4, pady=4)
        cols = ("id", "tag", "name", "category", "location",
                  "custodian", "condition", "status", "book_value")
        self.tree = ttk.Treeview(
            table_frame, columns=cols, show="headings",
            selectmode="browse")
        widths = {
            "id": 50, "tag": 110, "name": 240,
            "category": 140, "location": 150,
            "custodian": 160, "condition": 90,
            "status": 120, "book_value": 110,
        }
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(
                c, width=widths[c],
                anchor=("center" if c in ("id",)
                          else "e" if c == "book_value"
                          else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(
                status, background=bg, foreground=fg)
        self.tree.tag_configure(
            "audit_overdue", background="#ffd1d1",
            foreground="#8c0d0d")
        self.tree.bind("<Double-Button-1>",
                          lambda _e: self._view_detail())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=4, pady=(4, 4))
        for label, cmd in (
                ("Refresh",          self.refresh),
                ("New Asset",        self._new),
                ("Edit",             self._edit),
                ("View Detail",      self._view_detail),
                ("Set Status",       self._set_status),
                ("Delete",           self._delete),
                ("Maintenance Log",  self._maintenance_log),
                ("Summary",          self._summary),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_category.current(0)
        self.f_status.current(0)
        self.f_condition.current(0)
        self.f_location.delete(0, "end")
        self.f_search.delete(0, "end")
        self.refresh()

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_category.get():
            f["category"] = self.f_category.get()
        if self.f_status.get():
            f["status"] = self.f_status.get()
        if self.f_condition.get():
            f["condition"] = self.f_condition.get()
        if self.f_location.get().strip():
            f["location"] = self.f_location.get().strip()
        if self.f_search.get().strip():
            f["search"] = self.f_search.get().strip()
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            views = data.list_views(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Assets", str(e),
                                    parent=self.frame)
            return
        for v in views:
            a = v.asset
            tag = "audit_overdue" if a.audit_overdue else a.status
            self.tree.insert(
                "", "end", iid=str(a.asset_id),
                values=(a.asset_id, a.asset_tag, a.name,
                         a.category, a.location,
                         v.custodian_name or "—",
                         a.condition, a.status,
                         _money(v.current_book_value)),
                tags=(tag,))
        self.count.config(text=f"{len(views)} asset(s)")

    def _selected(self) -> Asset | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Assets",
                                  "Select an asset first.",
                                  parent=self.frame)
            return None
        return data.get_asset(int(sel[0]))

    def _new(self) -> None:
        if AssetEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        a = self._selected()
        if a and AssetEditor(self.frame,
                                asset=a).result is not None:
            self.refresh()

    def _view_detail(self) -> None:
        a = self._selected()
        if not a:
            return
        AssetDetail(self.frame, asset_id=a.asset_id)
        self.refresh()

    def _set_status(self) -> None:
        a = self._selected()
        if not a:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES), default=a.status)
        if not new:
            return
        try:
            data.set_status(a.asset_id, new)
        except ValidationError as exc:
            messagebox.showerror("Assets", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        a = self._selected()
        if not a:
            return
        if not messagebox.askyesno(
                "Assets",
                f"Delete asset #{a.asset_id} ({a.asset_tag})?\n"
                "This also deletes all its maintenance entries.",
                parent=self.frame):
            return
        data.delete_asset(a.asset_id)
        self.refresh()

    def _maintenance_log(self) -> None:
        a = self._selected()
        if not a:
            return
        AssetDetail(self.frame, asset_id=a.asset_id,
                       focus_maintenance=True)
        self.refresh()

    def _summary(self) -> None:
        SummaryDialog(self.frame)


# ── Asset editor ──────────────────────────────────────────────────

class AssetEditor:
    def __init__(self, parent, *, asset: Asset | None = None) -> None:
        self.asset = asset
        self.result: Asset | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit asset #{asset.asset_id}"
                          if asset else "New asset")
        self.win.geometry("860x820")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._staff_opts = _staff_options()
        self._build()
        if asset:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.StringVar] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        entry(0, 0, "Asset tag*", "asset_tag")
        entry(0, 2, "Name*", "name")
        combo(1, 0, "Category*", "category", CATEGORIES)
        entry(1, 2, "Location*", "location")
        entry(2, 0, "Manufacturer", "manufacturer")
        entry(2, 2, "Model", "model")
        entry(3, 0, "Serial number", "serial_number")
        entry(3, 2, "Room", "room")

        ttk.Label(body, text="Custodian").grid(
            row=4, column=0, sticky="w", padx=4, pady=2)
        self.custodian_combo = ttk.Combobox(
            body, state="readonly", width=42)
        self.custodian_combo["values"] = ["(none)"] + [
            lbl for _, lbl in self._staff_opts]
        self.custodian_combo.current(0)
        self.custodian_combo.grid(
            row=4, column=1, columnspan=3,
            sticky="ew", padx=4, pady=2)

        entry(5, 0, "Purchase date", "purchase_date")
        entry(5, 2, "Purchase cost", "purchase_cost")
        entry(6, 0, "Supplier", "supplier")
        entry(6, 2, "Warranty expiry", "warranty_expiry")
        entry(7, 0, "Useful life (yrs)", "useful_life_years")
        combo(7, 2, "Depreciation method",
                 "depreciation_method", DEPRECIATION_METHODS)
        entry(8, 0, "Residual value", "residual_value")
        combo(8, 2, "Condition*", "condition", CONDITIONS)
        combo(9, 0, "Status*", "status", STATUSES)
        entry(9, 2, "Next audit due", "next_audit_due")
        entry(10, 0, "Last audit date", "last_audit_date")

        disp = ttk.LabelFrame(
            body, text="Disposal (only if status = Disposed / Lost/Stolen)")
        disp.grid(row=11, column=0, columnspan=4,
                     sticky="ew", padx=4, pady=(8, 4))
        for c in range(4):
            disp.grid_columnconfigure(c, weight=1)
        ttk.Label(disp, text="Disposal date").grid(
            row=0, column=0, sticky="w", padx=4, pady=2)
        self.vars["disposal_date"] = tk.StringVar()
        ttk.Entry(disp, textvariable=self.vars["disposal_date"],
                    width=22).grid(row=0, column=1,
                                      sticky="ew", padx=4, pady=2)
        ttk.Label(disp, text="Method").grid(
            row=0, column=2, sticky="w", padx=4, pady=2)
        self.vars["disposal_method"] = tk.StringVar()
        ttk.Combobox(
            disp, textvariable=self.vars["disposal_method"],
            values=("",) + DISPOSAL_METHODS,
            state="readonly", width=20).grid(
            row=0, column=3, sticky="ew", padx=4, pady=2)
        ttk.Label(disp, text="Proceeds").grid(
            row=1, column=0, sticky="w", padx=4, pady=2)
        self.vars["disposal_proceeds"] = tk.StringVar()
        ttk.Entry(disp,
                    textvariable=self.vars["disposal_proceeds"],
                    width=22).grid(row=1, column=1,
                                      sticky="ew", padx=4, pady=2)

        ttk.Label(body, text="Notes").grid(
            row=12, column=0, sticky="nw", padx=4, pady=(6, 2))
        self.notes = tk.Text(body, height=4, width=70, wrap="word")
        self.notes.grid(row=12, column=1, columnspan=3,
                          sticky="ew", padx=4, pady=(6, 2))

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        # Defaults for new asset.
        self.vars["category"].set(DEFAULT_CATEGORY)
        self.vars["condition"].set(DEFAULT_CONDITION)
        self.vars["status"].set(DEFAULT_STATUS)
        self.vars["depreciation_method"].set(
            DEFAULT_DEPRECIATION_METHOD)
        self.vars["residual_value"].set("0")

    def _load(self) -> None:
        a = self.asset
        assert a is not None
        for k in ("asset_tag", "name", "category", "manufacturer",
                    "model", "serial_number", "location", "room",
                    "purchase_date", "supplier", "warranty_expiry",
                    "depreciation_method", "condition", "status",
                    "last_audit_date", "next_audit_due",
                    "disposal_date", "disposal_method"):
            self.vars[k].set(getattr(a, k) or "")
        for k in ("purchase_cost", "residual_value",
                    "useful_life_years", "disposal_proceeds"):
            val = getattr(a, k)
            self.vars[k].set("" if val is None else str(val))
        # Custodian.
        if a.custodian_id:
            for idx, (sid, _) in enumerate(self._staff_opts):
                if sid == a.custodian_id:
                    self.custodian_combo.current(idx + 1)
                    break
        self.notes.delete("1.0", "end")
        if a.notes:
            self.notes.insert("1.0", a.notes)

    def _save(self) -> None:
        payload: dict = {k: v.get().strip()
                         for k, v in self.vars.items()}
        # Custodian: combobox index 0 == "(none)".
        idx = self.custodian_combo.current()
        if idx <= 0:
            payload["custodian_id"] = None
        else:
            payload["custodian_id"] = (
                self._staff_opts[idx - 1][0])
        # Replace blank strings with None for nullable numerics.
        for k in ("purchase_cost", "useful_life_years",
                    "disposal_proceeds"):
            if payload.get(k) == "":
                payload[k] = None
        if payload.get("residual_value") == "":
            payload["residual_value"] = 0
        payload["notes"] = self.notes.get("1.0", "end").rstrip()
        try:
            if self.asset:
                self.result = data.update_asset(
                    self.asset.asset_id, payload)
            else:
                self.result = data.create_asset(payload)
        except ValidationError as exc:
            messagebox.showerror("Assets", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


# ── Asset detail dialog ──────────────────────────────────────────

class AssetDetail:
    def __init__(self, parent, *, asset_id: int,
                 focus_maintenance: bool = False) -> None:
        self.asset_id = asset_id
        self.win = tk.Toplevel(parent)
        self.win.title(f"Asset detail #{asset_id}")
        self.win.geometry("1000x720")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        self.refresh()
        if focus_maintenance:
            self.maint_tree.focus_set()
        self.win.wait_window()

    def _build(self) -> None:
        top = ttk.Frame(self.win)
        top.pack(fill="x", padx=10, pady=(10, 4))
        self.summary = tk.Text(top, height=14, wrap="word",
                                  font=("TkFixedFont", 10))
        self.summary.pack(fill="both", expand=True)
        self.summary.config(state="disabled")

        ttk.Label(self.win, text="Maintenance Log",
                    font=("TkDefaultFont", 11, "bold")).pack(
            anchor="w", padx=10, pady=(8, 0))

        mid = ttk.Frame(self.win)
        mid.pack(fill="both", expand=True, padx=10, pady=4)
        cols = ("id", "date", "type", "performed_by",
                  "cost", "outcome", "next_due")
        self.maint_tree = ttk.Treeview(
            mid, columns=cols, show="headings", height=10,
            selectmode="browse")
        widths = {"id": 50, "date": 90, "type": 140,
                   "performed_by": 200, "cost": 90,
                   "outcome": 100, "next_due": 100}
        for c in cols:
            self.maint_tree.heading(
                c, text=c.replace("_", " ").title())
            self.maint_tree.column(
                c, width=widths[c],
                anchor=("e" if c == "cost"
                          else "center" if c == "id" else "w"))
        vsb = ttk.Scrollbar(mid, orient="vertical",
                              command=self.maint_tree.yview)
        self.maint_tree.configure(yscrollcommand=vsb.set)
        self.maint_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.maint_tree.bind(
            "<Double-Button-1>", lambda _e: self._edit_maint())

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=10, pady=(4, 10))
        for label, cmd in (
                ("Add Maintenance",    self._add_maint),
                ("Edit Maintenance",   self._edit_maint),
                ("Delete Maintenance", self._delete_maint),
                ("Refresh",            self.refresh),
                ("Close",              self.win.destroy),
        ):
            ttk.Button(bar, text=label,
                        command=cmd).pack(side="left", padx=4)

    def refresh(self) -> None:
        v = data.view_asset(self.asset_id)
        self.summary.config(state="normal")
        self.summary.delete("1.0", "end")
        if v is None:
            self.summary.insert("end", "Asset not found.")
            self.summary.config(state="disabled")
            return
        a = v.asset
        lines = [
            f"#{a.asset_id}   Tag: {a.asset_tag}   "
            f"Name: {a.name}",
            f"Category: {a.category}    "
            f"Status: {a.status}    Condition: {a.condition}",
            f"Manufacturer / Model: "
            f"{a.manufacturer or '—'} / {a.model or '—'}",
            f"Serial: {a.serial_number or '—'}    "
            f"Location: {a.location}    Room: {a.room or '—'}",
            f"Custodian: {a.custodian_id or '—'}"
            + (f"  ({v.custodian_name})" if v.custodian_name else ""),
            f"Purchase: {a.purchase_date or '—'}  "
            f"{_money(a.purchase_cost)}    "
            f"Supplier: {a.supplier or '—'}",
            f"Warranty expiry: {a.warranty_expiry or '—'}"
            + ("  (EXPIRED)" if a.warranty_expired else ""),
            f"Useful life: {a.useful_life_years or '—'} year(s)"
            f"    Depreciation: {a.depreciation_method}"
            f"    Residual: {_money(a.residual_value)}",
            f"Book value: {_money(v.current_book_value)}"
            f"    Age: {v.age_days} day(s)",
            f"Last audit: {a.last_audit_date or '—'}"
            f"    Next due: {a.next_audit_due or '—'}"
            + ("  (OVERDUE)" if a.audit_overdue else ""),
        ]
        if a.is_disposed:
            lines.append(
                f"Disposal: {a.disposal_date or '—'}  "
                f"{a.disposal_method or '—'}  "
                f"{_money(a.disposal_proceeds)}")
        if a.notes:
            lines.append("")
            lines.append(f"Notes: {a.notes}")
        self.summary.insert("end", "\n".join(lines))
        self.summary.config(state="disabled")

        for iid in self.maint_tree.get_children():
            self.maint_tree.delete(iid)
        for m in data.list_maintenance(asset_id=self.asset_id):
            self.maint_tree.insert(
                "", "end", iid=str(m.maintenance_id),
                values=(m.maintenance_id, m.service_date,
                         m.service_type, m.performed_by or "—",
                         _money(m.cost), m.outcome,
                         m.next_service_due or "—"))

    def _selected_maint(self) -> MaintenanceEntry | None:
        sel = self.maint_tree.selection()
        if not sel:
            messagebox.showinfo("Assets",
                                  "Select a maintenance entry.",
                                  parent=self.win)
            return None
        return data.get_maintenance(int(sel[0]))

    def _add_maint(self) -> None:
        MaintenanceEditor(self.win, asset_id=self.asset_id)
        self.refresh()

    def _edit_maint(self) -> None:
        m = self._selected_maint()
        if m:
            MaintenanceEditor(self.win, asset_id=self.asset_id,
                                  entry=m)
            self.refresh()

    def _delete_maint(self) -> None:
        m = self._selected_maint()
        if not m:
            return
        if not messagebox.askyesno(
                "Assets",
                f"Delete maintenance entry #{m.maintenance_id}?",
                parent=self.win):
            return
        data.delete_maintenance(m.maintenance_id)
        self.refresh()


# ── Maintenance editor ────────────────────────────────────────────

class MaintenanceEditor:
    def __init__(self, parent, *, asset_id: int,
                 entry: MaintenanceEntry | None = None) -> None:
        self.asset_id = asset_id
        self.entry = entry
        self.result: MaintenanceEntry | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit maintenance #{entry.maintenance_id}"
            if entry else "Add maintenance")
        self.win.geometry("600x440")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._staff_opts = _staff_options()
        self._build()
        if entry:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        self.vars: dict[str, tk.StringVar] = {}

        def row(idx, label, key, widget):
            ttk.Label(body, text=label).grid(
                row=idx, column=0, sticky="w", padx=4, pady=4)
            widget.grid(row=idx, column=1, sticky="ew",
                          padx=4, pady=4)

        v = tk.StringVar(value=_date.today().isoformat())
        self.vars["service_date"] = v
        row(0, "Service date*", "service_date",
              ttk.Entry(body, textvariable=v))

        v = tk.StringVar(value=DEFAULT_SERVICE_TYPE)
        self.vars["service_type"] = v
        row(1, "Service type*", "service_type",
              ttk.Combobox(body, textvariable=v,
                             values=SERVICE_TYPES,
                             state="readonly"))

        v = tk.StringVar()
        self.vars["performed_by"] = v
        row(2, "Performed by", "performed_by",
              ttk.Entry(body, textvariable=v))

        ttk.Label(body, text="Staff").grid(
            row=3, column=0, sticky="w", padx=4, pady=4)
        self.staff_combo = ttk.Combobox(body, state="readonly")
        self.staff_combo["values"] = ["(none)"] + [
            lbl for _, lbl in self._staff_opts]
        self.staff_combo.current(0)
        self.staff_combo.grid(row=3, column=1, sticky="ew",
                                 padx=4, pady=4)

        v = tk.StringVar()
        self.vars["cost"] = v
        row(4, "Cost", "cost",
              ttk.Entry(body, textvariable=v))

        v = tk.StringVar(value=DEFAULT_MAINTENANCE_OUTCOME)
        self.vars["outcome"] = v
        row(5, "Outcome*", "outcome",
              ttk.Combobox(body, textvariable=v,
                             values=MAINTENANCE_OUTCOMES,
                             state="readonly"))

        v = tk.StringVar()
        self.vars["next_service_due"] = v
        row(6, "Next service due", "next_service_due",
              ttk.Entry(body, textvariable=v))

        ttk.Label(body, text="Notes").grid(
            row=7, column=0, sticky="nw", padx=4, pady=4)
        self.notes = tk.Text(body, height=4, width=46, wrap="word")
        self.notes.grid(row=7, column=1, sticky="ew",
                         padx=4, pady=4)

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

    def _load(self) -> None:
        m = self.entry
        assert m is not None
        self.vars["service_date"].set(m.service_date)
        self.vars["service_type"].set(m.service_type)
        self.vars["performed_by"].set(m.performed_by or "")
        self.vars["cost"].set(
            "" if m.cost is None else str(m.cost))
        self.vars["outcome"].set(m.outcome)
        self.vars["next_service_due"].set(
            m.next_service_due or "")
        if m.staff_id:
            for idx, (sid, _) in enumerate(self._staff_opts):
                if sid == m.staff_id:
                    self.staff_combo.current(idx + 1)
                    break
        self.notes.delete("1.0", "end")
        if m.notes:
            self.notes.insert("1.0", m.notes)

    def _save(self) -> None:
        payload: dict = {k: v.get().strip()
                         for k, v in self.vars.items()}
        idx = self.staff_combo.current()
        if idx <= 0:
            payload["staff_id"] = None
        else:
            payload["staff_id"] = self._staff_opts[idx - 1][0]
        if payload.get("cost") == "":
            payload["cost"] = None
        payload["notes"] = self.notes.get("1.0", "end").rstrip()
        try:
            if self.entry:
                self.result = data.update_maintenance(
                    self.entry.maintenance_id, payload)
            else:
                self.result = data.add_maintenance(
                    self.asset_id, payload)
        except ValidationError as exc:
            messagebox.showerror("Assets", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


# ── Summary dialog ────────────────────────────────────────────────

class SummaryDialog:
    def __init__(self, parent) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title("Assets summary")
        self.win.geometry("640x600")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")
        self.text = tk.Text(self.win, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True,
                          padx=10, pady=(4, 10))
        self.refresh()
        self.win.wait_window()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Assets Summary\n")
        self.text.insert("end", "=" * 50 + "\n\n")
        self.text.insert(
            "end",
            f"Total assets        : {s.total_assets}\n"
            f"Total purchase cost : {_money(s.total_purchase_cost)}\n"
            f"Total book value    : {_money(s.total_book_value)}\n"
            f"Overdue service     : {s.count_overdue_service}\n"
            f"Warranty expired    : {s.count_warranty_expired}\n"
            f"Due for audit       : {s.count_due_for_audit}\n\n")
        self.text.insert("end", "By category:\n")
        for k in CATEGORIES:
            n = s.by_category.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<18}: {n}\n")
        self.text.insert("end", "\nBy condition:\n")
        for k in CONDITIONS:
            n = s.by_condition.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nTop locations:\n")
        for loc, n in s.by_location:
            self.text.insert("end", f"  {loc[:30]:<30}: {n}\n")
        self.text.config(state="disabled")


# ── Choice prompt ────────────────────────────────────────────────

def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("320x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(
        value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK",
                command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_assets_window"]
