"""Tkinter views for Payroll & Staffing Costs (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Three tabs — a costed period (default: this week) broken down per
staff member, the week-by-week forecast, and the pay-rate list — the GUI
counterpart of ``payroll_cli.py``.
"""

from __future__ import annotations

import datetime as _dt
import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.staff.payroll import (
    payroll as data,
)
from education_system.systems.nursery.domain.staff.payroll.payroll import (
    PAY_STATUSES,
    PAY_TYPES,
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


def _tree(parent: ttk.Frame, spec: list[tuple[str, str, int]],
          height: int = 13) -> ttk.Treeview:
    cols = tuple(c for c, _l, _w in spec)
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=height)
    for c, label, w in spec:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.tag_configure("alert", foreground="#c0392b")
    tree.tag_configure("warn", foreground="#b9770e")
    tree.tag_configure("muted", foreground="#7f8c8d")
    tree.pack(fill="both", expand=True)
    return tree


def _this_monday() -> str:
    today = _dt.date.today()
    return (today - _dt.timedelta(days=today.weekday())).isoformat()


def _form_dialog(host, title: str, fields: list[tuple[str, str, str, Any]], *,
                 initial: dict[str, Any] | None = None,
                 geometry: str = "480x560") -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry(geometry)
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}
    row = 0
    for key, label, kind, choices in fields:
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw",
                                              pady=2)
        cur = initial.get(key)
        if kind == "choice":
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Combobox(frm, textvariable=v, values=list(choices or []),
                         width=34).grid(row=row, column=1, sticky="ew", pady=2)
        elif kind == "bool":
            v = tk.BooleanVar(value=bool(cur))
            ttk.Checkbutton(frm, variable=v).grid(row=row, column=1, sticky="w",
                                                  pady=2)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=36).grid(
                row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {}
        for key, v in vars_.items():
            out[key] = (bool(v.get()) if isinstance(v, tk.BooleanVar)
                        else (str(v.get()) or "").strip())
        result = out
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                              padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


# ── Manager ──────────────────────────────────────────────────────────────────

@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: payroll open_manager")
    root = _clear(host)
    ttk.Label(root, text="Payroll & Staffing Costs",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 2))
    warn = ttk.Label(root, foreground="#a00", wraplength=900)
    warn.pack(anchor="w", pady=(0, 6))
    _refresh_summary(summary, warn)

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)
    period_tab = ttk.Frame(nb, padding=8)
    forecast_tab = ttk.Frame(nb, padding=8)
    rate_tab = ttk.Frame(nb, padding=8)
    nb.add(period_tab, text="Costed Period")
    nb.add(forecast_tab, text="Forecast")
    nb.add(rate_tab, text="Pay Rates")

    _build_period_tab(host, period_tab)
    _build_forecast_tab(host, forecast_tab)
    _build_rate_tab(host, rate_tab)

    host.status_var.set("Payroll loaded")


def _refresh_summary(summary: ttk.Label, warn: ttk.Label) -> None:
    try:
        s = data.summary()
    except Exception:
        logger.exception("Could not load payroll summary")
        summary.config(text="Could not load — see logs.", foreground="#a00")
        return
    summary.config(
        text=f"On payroll: {s['staff_on_payroll']} ({s['agency_staff']} "
             f"agency)   Week of {s['week_start']}: {s['week_hours']}h, "
             f"£{s['week_total']:.2f} all in   Next 4 weeks: "
             f"£{s['forecast_4_weeks']:.2f} "
             f"(avg £{s['forecast_weekly_average']:.2f}/week)")
    warn.config(text=(
        f"⚠ {s['missing_pay_records']} employed staff have no pay record — "
        "every cost below understates the real bill."
        if s["missing_pay_records"] else ""))


# ── Costed period tab ────────────────────────────────────────────────────────

def _build_period_tab(host, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="From:").pack(side="left")
    from_var = tk.StringVar(value=_this_monday())
    ttk.Entry(bar, textvariable=from_var, width=13).pack(side="left", padx=4)
    ttk.Label(bar, text="To:").pack(side="left")
    to_var = tk.StringVar(value=(
        _dt.date.fromisoformat(_this_monday())
        + _dt.timedelta(days=6)).isoformat())
    ttk.Entry(bar, textvariable=to_var, width=13).pack(side="left", padx=4)
    ttk.Button(bar, text="Show",
               command=lambda: _refresh_period(from_var.get(), to_var.get(),
                                               totals, tree)).pack(side="left",
                                                                   padx=2)
    ttk.Button(bar, text="This Week",
               command=lambda: (
                   from_var.set(_this_monday()),
                   to_var.set((_dt.date.fromisoformat(_this_monday())
                               + _dt.timedelta(days=6)).isoformat()),
                   _refresh_period(from_var.get(), to_var.get(), totals,
                                   tree))).pack(side="left", padx=2)
    ttk.Button(bar, text="This Month",
               command=lambda: (
                   from_var.set(_dt.date.today().replace(day=1).isoformat()),
                   to_var.set(_dt.date.today().isoformat()),
                   _refresh_period(from_var.get(), to_var.get(), totals,
                                   tree))).pack(side="left", padx=2)

    totals = ttk.Label(parent, foreground="#2c3e50", font=("", 11, "bold"))
    totals.pack(anchor="w", pady=(0, 6))

    tree = _tree(parent, [
        ("staff", "Staff", 190), ("role", "Role", 160),
        ("shifts", "Shifts", 70), ("hours", "Hours", 80),
        ("ot", "Overtime", 80), ("absent", "Absent", 80),
        ("gross", "Gross", 100), ("oncosts", "On-costs", 100),
        ("total", "Total cost", 110),
    ])
    _refresh_period(from_var.get(), to_var.get(), totals, tree)


def _refresh_period(date_from: str, date_to: str, totals: ttk.Label,
                    tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        period = data.period_cost(date_from, date_to)
    except ValidationError as e:
        totals.config(text=str(e), foreground="#a00")
        return
    except Exception:
        logger.exception("Could not cost the period")
        totals.config(text="Could not load — see logs.", foreground="#a00")
        return

    for s in period.staff:
        if not (s.worked_hours or s.absent_hours):
            continue
        if not s.has_pay_record:
            tag = "alert"
        elif s.is_agency:
            tag = "warn"
        elif s.overtime_hours:
            tag = "warn"
        else:
            tag = ""
        tree.insert("", "end", iid=s.staff_id, tags=(tag,) if tag else (),
                    values=(s.staff_name or s.staff_id, s.role or "-",
                            s.shifts, f"{s.worked_hours:g}",
                            f"{s.overtime_hours:g}", f"{s.absent_hours:g}",
                            f"£{s.gross_pay:.2f}",
                            f"£{s.ni_cost + s.pension_cost:.2f}",
                            f"£{s.total_cost:.2f}"))
    extra = []
    if period.agency_cost:
        extra.append(f"agency £{period.agency_cost:.2f}")
    if period.overtime_cost:
        extra.append(f"overtime £{period.overtime_cost:.2f}")
    totals.config(
        text=f"{period.date_from} to {period.date_to}:  "
             f"{period.worked_hours}h worked, {period.absent_hours}h lost to "
             f"absence  —  gross £{period.gross_pay:.2f} + on-costs "
             f"£{period.on_costs:.2f} = £{period.total_cost:.2f}"
             + (f"  ({', '.join(extra)})" if extra else ""),
        foreground="#2c3e50")


# ── Forecast tab ─────────────────────────────────────────────────────────────

def _build_forecast_tab(host, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Weeks ahead:").pack(side="left")
    weeks_var = tk.StringVar(value="8")
    ttk.Spinbox(bar, from_=1, to=52, textvariable=weeks_var, width=6).pack(
        side="left", padx=6)
    ttk.Button(bar, text="Project",
               command=lambda: _refresh_forecast(weeks_var.get(), totals,
                                                 tree)).pack(side="left",
                                                             padx=2)

    ttk.Label(parent, foreground="#555",
              text="Weeks the rota already covers are priced from it; beyond "
                   "that, staff are priced at their contracted hours.").pack(
        anchor="w", pady=(0, 4))

    totals = ttk.Label(parent, foreground="#2c3e50", font=("", 11, "bold"))
    totals.pack(anchor="w", pady=(0, 6))

    tree = _tree(parent, [
        ("from", "Week beginning", 150), ("to", "Week ending", 150),
        ("hours", "Hours", 110), ("cost", "Projected cost", 150),
    ], height=14)
    _refresh_forecast(weeks_var.get(), totals, tree)


def _refresh_forecast(weeks: str, totals: ttk.Label,
                      tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        result = data.forecast_total(int(weeks))
    except (ValueError, ValidationError) as e:
        totals.config(text=str(e) or "Weeks must be a number.",
                      foreground="#a00")
        return
    except Exception:
        logger.exception("Could not build the staffing forecast")
        totals.config(text="Could not load — see logs.", foreground="#a00")
        return
    for i, w in enumerate(result["weekly"]):
        tree.insert("", "end", iid=f"week-{i}", values=(
            w["from"], w["to"], f"{w['hours']:g}", f"£{w['cost']:.2f}"))
    totals.config(
        text=f"{result['from']} to {result['to']}:  £{result['total_cost']:.2f} "
             f"over {result['weeks']} week(s), averaging "
             f"£{result['average_weekly_cost']:.2f}/week  —  gross "
             f"£{result['gross_pay']:.2f} + on-costs £{result['on_costs']:.2f}, "
             f"overtime £{result['overtime_cost']:.2f}, agency "
             f"£{result['agency_cost']:.2f}",
        foreground="#2c3e50")


# ── Pay rates tab ────────────────────────────────────────────────────────────

_PAY_FIELDS: list[tuple[str, str, str, Any]] = [
    ("pay_type",            "Pay type",              "choice", PAY_TYPES),
    ("hourly_rate",         "Hourly rate (£)",       "entry",  None),
    ("annual_salary",       "Annual salary (£)",     "entry",  None),
    ("contracted_hours",    "Contracted hours/week", "entry",  None),
    ("overtime_multiplier", "Overtime multiplier",   "entry",  None),
    ("is_agency",           "Agency staff",          "bool",   None),
    ("agency_name",         "Agency name",           "entry",  None),
    ("ni_percent",          "Employer NI %",         "entry",  None),
    ("pension_percent",     "Employer pension %",    "entry",  None),
    ("effective_from",      "Effective from",        "entry",  None),
    ("status",              "Status",                "choice", PAY_STATUSES),
    ("notes",               "Notes",                 "entry",  None),
]


def _build_rate_tab(host, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Set a Rate",
               command=lambda: _set_rate(host, None)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_rate(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_rate(host, tree)).pack(side="left",
                                                              padx=2)
    ttk.Button(bar, text="Staff With No Rate",
               command=lambda: _gaps(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh_rates(tree)).pack(side="left", padx=2)

    tree = _tree(parent, [
        ("staff", "Staff", 200), ("role", "Role", 180),
        ("type", "Type", 90), ("rate", "Basic/hour", 100),
        ("ot", "Overtime/hour", 110), ("hours", "Contracted", 100),
        ("oncost", "On-costs", 90), ("agency", "Agency", 150),
        ("status", "Status", 80),
    ])
    tree.bind("<Double-1>", lambda _e: _edit_rate(host, tree))
    _refresh_rates(tree)


def _refresh_rates(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_pay_records()
    except Exception:
        logger.exception("Could not refresh pay records")
        return
    for p in rows:
        if p.status != "active":
            tag = "muted"
        elif p.is_agency:
            tag = "warn"
        else:
            tag = ""
        tree.insert("", "end", iid=p.staff_id, tags=(tag,) if tag else (),
                    values=(p.staff_name or p.staff_id, p.role or "-",
                            p.pay_type, f"£{p.effective_hourly_rate:.2f}",
                            f"£{p.overtime_rate:.2f}",
                            f"{p.contracted_hours:g}h",
                            f"{p.on_cost_percent:g}%", p.agency_name or "-",
                            p.status))


@_safe_view
def _set_rate(host, staff_id: str | None) -> None:
    initial: dict[str, Any] = {"pay_type": "hourly", "overtime_multiplier": "1.5",
                               "ni_percent": "13.8", "pension_percent": "3.0",
                               "status": "active"}
    fields_spec = list(_PAY_FIELDS)
    if staff_id is None:
        staff = data.list_staff_choices()
        if not staff:
            messagebox.showinfo("Pay rate", "No employed staff to pay.",
                                parent=host.root)
            return
        fields_spec.insert(0, ("staff_id", "Staff", "choice",
                               [sid for sid, _label in staff]))
    else:
        existing = data.get_pay_record(staff_id)
        if existing is not None:
            initial = {k: getattr(existing, k)
                       for k, _l, _kd, _ch in _PAY_FIELDS}

    fields = _form_dialog(host,
                          f"Pay rate — {staff_id}" if staff_id else "Set a Rate",
                          fields_spec, initial=initial)
    if not fields:
        return
    target = staff_id or fields.pop("staff_id", "")
    if not target:
        messagebox.showerror("Pay rate", "Please choose a staff member.",
                             parent=host.root)
        return
    try:
        p = data.set_pay(target, fields)
    except ValidationError as e:
        messagebox.showerror("Pay rate", str(e), parent=host.root)
        return
    host.status_var.set(
        f"{p.staff_name or target}: £{p.effective_hourly_rate:.2f}/hour")
    open_manager(host)


@_safe_view
def _edit_rate(host, tree: ttk.Treeview) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Pay rate", "Select a staff member to edit.",
                            parent=host.root)
        return
    _set_rate(host, sel)


@_safe_view
def _delete_rate(host, tree: ttk.Treeview) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Pay rate", "Select a staff member.",
                            parent=host.root)
        return
    if not messagebox.askyesno(
            "Delete pay record",
            f"Delete the pay record for {sel}? Their hours will still be "
            "counted but will cost nothing.", parent=host.root):
        return
    data.delete_pay_record(sel)
    host.status_var.set(f"Deleted the pay record for {sel}")
    open_manager(host)


@_safe_view
def _gaps(host) -> None:
    rows = data.staff_without_pay()
    if not rows:
        messagebox.showinfo("Pay records",
                            "Every employed staff member has a pay arrangement.",
                            parent=host.root)
        return
    messagebox.showwarning(
        "Staff with no pay record",
        "\n".join(f"{name} ({sid})" for sid, name in rows)
        + "\n\nTheir hours are counted but cost nothing until a rate is set.",
        parent=host.root)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Payroll & Staffing Costs",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Payroll & Staffing Costs from the navigation "
              "menu.").pack(anchor="w")
    return frame
