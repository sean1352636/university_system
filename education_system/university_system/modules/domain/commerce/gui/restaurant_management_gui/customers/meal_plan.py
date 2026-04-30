"""Meal-plan and staff-subsidy management dialogs.

Surfaces the four ``restaurant_bus`` entry points that previously had
no UI:

* ``top_up_meal_plan(student_id, amount)``
* ``meal_plan_balance(student_id)``
* ``apply_su_discount(student_id, amount)`` — preview only
* ``apply_staff_subsidy(staff_id, amount)`` — preview only

Attached to ``RestaurantManagementGUI`` from ``core/main_gui.py`` and
launched from buttons added to the customers tab in ``core/tabs.py``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.infrastructure.database.db import (
    get_connection,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_students(limit: int = 500) -> list[tuple[str, str]]:
    """Return ``[(student_id, label)]`` for the combobox. Prefers
    ``students`` (canonical) but falls back to ``restaurant_customers``
    so the dialog works in restaurant-only test installs."""
    out: list[tuple[str, str]] = []
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT student_id, "
                "       TRIM(COALESCE(first_name,'') || ' ' || "
                "            COALESCE(last_name,'')) AS name "
                "FROM students ORDER BY student_id LIMIT ?",
                (limit,),
            ).fetchall()
            out = [(r[0], f"{r[0]} — {r[1] or '(no name)'}")
                   for r in rows if r[0]]
    except Exception:
        pass
    if not out:
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT customer_id, name FROM restaurant_customers "
                    "ORDER BY name LIMIT ?", (limit,),
                ).fetchall()
                out = [(str(r[0]), f"{r[0]} — {r[1] or '(no name)'}")
                       for r in rows if r[0]]
        except Exception:
            pass
    return out


def _load_staff(limit: int = 500) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT u.id, "
                "       TRIM(COALESCE(u.first_name,'') || ' ' || "
                "            COALESCE(u.last_name,'')) AS name, "
                "       COALESCE(u.role, '') "
                "FROM users u "
                "WHERE LOWER(COALESCE(u.role,'')) IN ('staff','admin','instructor') "
                "ORDER BY u.id LIMIT ?",
                (limit,),
            ).fetchall()
            out = [(str(r[0]), f"{r[0]} — {r[1] or '(no name)'} [{r[2]}]")
                   for r in rows if r[0]]
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Meal-plan management
# ---------------------------------------------------------------------------

def manage_meal_plan_dialog(self):
    """Top up / inspect a student's meal-plan balance via
    ``restaurant_bus``. The balance is derived from the finance
    ledger so it always matches the unified student account view.
    """
    try:
        from education_system.university_system.modules.services import (
            restaurant_bus,
        )
    except Exception as exc:
        messagebox.showerror("Meal plan",
                             f"restaurant_bus unavailable: {exc}")
        return

    dialog = tk.Toplevel(self.root)
    dialog.title("Meal plan management")
    dialog.geometry("560x460")
    dialog.transient(self.root)
    dialog.grab_set()

    main = ttk.Frame(dialog, padding=16)
    main.pack(fill="both", expand=True)
    ttk.Label(main, text="Meal plan management",
              font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
    ttk.Label(main, text=(
        "Top-ups credit the student's finance ledger via "
        "restaurant_bus.top_up_meal_plan. Balance is derived from "
        "meal-plan rows in student_finance_transactions."
    ), wraplength=520, foreground="#555").pack(anchor="w", pady=(2, 10))

    pick = ttk.LabelFrame(main, text="Student", padding=10)
    pick.pack(fill="x")
    ttk.Label(pick, text="Select student:").grid(row=0, column=0,
                                                  sticky="w")
    student_var = tk.StringVar()
    students = _load_students()
    student_box = ttk.Combobox(pick, textvariable=student_var,
                               values=[s[1] for s in students],
                               width=44, state="readonly")
    student_box.grid(row=0, column=1, padx=8, pady=4, sticky="ew")
    pick.columnconfigure(1, weight=1)

    info = ttk.LabelFrame(main, text="Current state", padding=10)
    info.pack(fill="x", pady=(10, 0))
    balance_var = tk.StringVar(value="—")
    ttk.Label(info, text="Meal-plan balance:").grid(row=0, column=0,
                                                    sticky="w")
    ttk.Label(info, textvariable=balance_var,
              font=("TkDefaultFont", 11, "bold"),
              foreground="#06c").grid(row=0, column=1, sticky="w",
                                      padx=10)

    def _picked_id() -> str | None:
        sel = student_var.get()
        if not sel:
            return None
        for sid, label in students:
            if label == sel:
                return sid
        return None

    def refresh_balance(*_a):
        sid = _picked_id()
        if not sid:
            balance_var.set("—")
            return
        try:
            bal = restaurant_bus.meal_plan_balance(sid)
            balance_var.set(f"£{bal:,.2f}")
        except Exception as exc:
            balance_var.set(f"(error: {exc})")

    student_box.bind("<<ComboboxSelected>>", refresh_balance)

    topup = ttk.LabelFrame(main, text="Top up", padding=10)
    topup.pack(fill="x", pady=(10, 0))
    ttk.Label(topup, text="Amount (£):").grid(row=0, column=0,
                                              sticky="w")
    amount_var = tk.StringVar()
    ttk.Entry(topup, textvariable=amount_var, width=14
              ).grid(row=0, column=1, sticky="w", padx=8, pady=4)

    def do_topup():
        sid = _picked_id()
        if not sid:
            messagebox.showwarning("Meal plan",
                                   "Pick a student first.")
            return
        try:
            amount = float(amount_var.get())
        except ValueError:
            messagebox.showerror("Meal plan", "Amount must be a number.")
            return
        if amount <= 0:
            messagebox.showerror("Meal plan",
                                 "Amount must be positive.")
            return
        username = None
        if getattr(self, "auth", None) and self.auth.current_user:
            username = self.auth.current_user.get("username")
        tx = restaurant_bus.top_up_meal_plan(
            sid, amount, processed_by=username,
        )
        if tx:
            refresh_balance()
            amount_var.set("")
            messagebox.showinfo(
                "Meal plan",
                f"Top-up of £{amount:,.2f} recorded "
                f"(finance tx {tx})."
            )
        else:
            messagebox.showerror(
                "Meal plan",
                "Top-up failed (check finance ledger / logs).")

    ttk.Button(topup, text="Apply top-up",
               command=do_topup).grid(row=0, column=2, padx=10)

    # SU discount preview
    disc = ttk.LabelFrame(main, text="SU member discount preview",
                          padding=10)
    disc.pack(fill="x", pady=(10, 0))
    ttk.Label(disc, text="Sample order amount (£):"
              ).grid(row=0, column=0, sticky="w")
    sample_var = tk.StringVar(value="20.00")
    ttk.Entry(disc, textvariable=sample_var, width=10
              ).grid(row=0, column=1, sticky="w", padx=8)
    preview_var = tk.StringVar(value="—")
    ttk.Label(disc, textvariable=preview_var, foreground="#070"
              ).grid(row=0, column=2, sticky="w", padx=10)

    def preview_disc():
        sid = _picked_id()
        if not sid:
            preview_var.set("(pick student)")
            return
        try:
            base = float(sample_var.get())
        except ValueError:
            preview_var.set("(amount?)")
            return
        try:
            discounted, applied = restaurant_bus.apply_su_discount(
                sid, base)
            if applied:
                preview_var.set(
                    f"£{base:,.2f} → £{discounted:,.2f} "
                    f"(SU member discount applied)"
                )
            else:
                preview_var.set(f"£{base:,.2f} (no SU membership)")
        except Exception as exc:
            preview_var.set(f"(error: {exc})")

    ttk.Button(disc, text="Preview",
               command=preview_disc).grid(row=0, column=3, padx=4)

    ttk.Button(main, text="Close",
               command=dialog.destroy).pack(pady=12)


# ---------------------------------------------------------------------------
# Staff subsidy preview
# ---------------------------------------------------------------------------

def manage_staff_subsidy_dialog(self):
    """Preview-only dialog for ``apply_staff_subsidy``. Lets the
    operator confirm subsidy amounts before quoting prices to staff."""
    try:
        from education_system.university_system.modules.services import (
            restaurant_bus,
        )
    except Exception as exc:
        messagebox.showerror("Staff subsidy",
                             f"restaurant_bus unavailable: {exc}")
        return

    dialog = tk.Toplevel(self.root)
    dialog.title("Staff subsidy preview")
    dialog.geometry("520x320")
    dialog.transient(self.root)
    dialog.grab_set()

    main = ttk.Frame(dialog, padding=16)
    main.pack(fill="both", expand=True)
    ttk.Label(main, text="Staff subsidy preview",
              font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
    ttk.Label(main, text=(
        "Calculates the subsidised price for active staff via "
        "restaurant_bus.apply_staff_subsidy. Read-only — actual "
        "discount is applied at point of sale."
    ), wraplength=480, foreground="#555").pack(anchor="w", pady=(2, 10))

    pick = ttk.LabelFrame(main, text="Staff member", padding=10)
    pick.pack(fill="x")
    ttk.Label(pick, text="Select staff:").grid(row=0, column=0,
                                               sticky="w")
    staff_var = tk.StringVar()
    staff_rows = _load_staff()
    staff_box = ttk.Combobox(pick, textvariable=staff_var,
                             values=[s[1] for s in staff_rows],
                             width=44, state="readonly")
    staff_box.grid(row=0, column=1, padx=8, pady=4, sticky="ew")
    pick.columnconfigure(1, weight=1)

    calc = ttk.LabelFrame(main, text="Calculate", padding=10)
    calc.pack(fill="x", pady=(10, 0))
    ttk.Label(calc, text="Order amount (£):"
              ).grid(row=0, column=0, sticky="w")
    amount_var = tk.StringVar(value="20.00")
    ttk.Entry(calc, textvariable=amount_var, width=10
              ).grid(row=0, column=1, sticky="w", padx=8)
    out_var = tk.StringVar(value="—")
    ttk.Label(calc, textvariable=out_var, foreground="#06c"
              ).grid(row=0, column=2, sticky="w", padx=10)

    def calc_preview():
        sel = staff_var.get()
        sid = None
        for s, label in staff_rows:
            if label == sel:
                sid = s
                break
        if not sid:
            out_var.set("(pick staff)")
            return
        try:
            base = float(amount_var.get())
        except ValueError:
            out_var.set("(amount?)")
            return
        try:
            discounted, applied = restaurant_bus.apply_staff_subsidy(
                sid, base)
            if applied:
                out_var.set(
                    f"£{base:,.2f} → £{discounted:,.2f} "
                    f"(staff subsidy applied)"
                )
            else:
                out_var.set(f"£{base:,.2f} (no active staff record)")
        except Exception as exc:
            out_var.set(f"(error: {exc})")

    ttk.Button(calc, text="Preview",
               command=calc_preview).grid(row=0, column=3, padx=6)

    ttk.Button(main, text="Close",
               command=dialog.destroy).pack(pady=12)


__all__ = [
    "manage_meal_plan_dialog",
    "manage_staff_subsidy_dialog",
]
