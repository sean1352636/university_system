"""
Graduation Ceremony GUI

Five-tab Toplevel for the operational side of graduation:

  1. Ceremonies         — schedule date/time/venue per cohort, capacity.
  2. RSVPs              — record graduand RSVPs + allocate guest tickets.
  3. Gown Orders        — robing/gown size, supplier, collection slot.
  4. Seat Plan          — auto-generate, view, and export as CSV.
  5. Stage Script       — announcer script + name-pronunciation CSV.

Window matches the project convention: 1400x900, minsize 1200x800.
"""

from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import Optional

try:
    from tkcalendar import DateEntry  # nicer pop-up calendar for date fields
    _HAS_TKCALENDAR = True
except Exception:  # pragma: no cover - fallback when tkcalendar is absent
    DateEntry = None
    _HAS_TKCALENDAR = False

from education_system.post_18.university_system.modules.domain.academics.services.degree_audit.graduation_ceremony import (
    CeremonyManager, GownOrderManager, RsvpManager, SeatPlanManager,
    StageScriptManager,
)
from education_system.post_18.university_system.modules.domain.academics.services.degree_audit.graduation_records import (
    AlumniProvisioner, DigitalDiplomaManager, PrintQueueManager,
    TranscriptFreezeManager, issue_conferral_package,
)
from education_system.post_18.university_system.modules.domain.academics.services.degree_audit.db_schema import (
    initialize_degree_audit_database,
)
from education_system.post_18.university_system.modules.domain.academics.services.degree_audit.graduation_eligibility import (
    check_eligibility,
)


class GraduationCeremonyGUI:
    """Operational graduation ceremony management."""

    def __init__(self, parent, auth=None):
        self.auth = auth
        try:
            initialize_degree_audit_database()
        except Exception:
            pass

        # Allow embedding in workspace Frame.
        if parent is not None and not hasattr(parent, "wm_title"):
            self.window = parent
            self._owned_window = False
        else:
            self.window = tk.Toplevel(parent) if parent is not None else tk.Tk()
            self.window.title("Graduation Ceremony Management")
            self.window.geometry("1400x900")
            self.window.minsize(1200, 800)
            self._owned_window = True

        self.current_ceremony_id: Optional[int] = None
        self._build_ui()
        self._reload_ceremonies()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        outer = ttk.Frame(self.window, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        # Top bar: title on the left, a Close button pinned to the top corner.
        top_bar = ttk.Frame(outer)
        top_bar.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(top_bar, text="✖ Close", command=self._close).pack(
            side=tk.RIGHT, anchor="ne")

        ttk.Label(
            top_bar, text="🎓 Graduation Ceremony Management",
            font=("Arial", 16, "bold"),
        ).pack(side=tk.LEFT, anchor="w")

        # Ceremony picker (shared across all tabs).
        picker = ttk.LabelFrame(outer, text="Active ceremony", padding=8)
        picker.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(picker, text="Ceremony:").pack(side=tk.LEFT)
        self.ceremony_combo = ttk.Combobox(picker, width=70, state="readonly")
        self.ceremony_combo.pack(side=tk.LEFT, padx=8)
        self.ceremony_combo.bind("<<ComboboxSelected>>", self._on_ceremony_selected)

        self.capacity_label = ttk.Label(picker, text="", foreground="#444")
        self.capacity_label.pack(side=tk.LEFT, padx=20)

        ttk.Button(picker, text="🔄 Refresh", command=self._reload_ceremonies).pack(side=tk.RIGHT)

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # The self-service "My Graduation" tab is only for logged-in students.
        if self._is_student():
            self._build_student_tab()
        self._build_ceremonies_tab()
        self._build_rsvp_tab()
        self._build_gown_tab()
        self._build_seat_tab()
        self._build_script_tab()
        self._build_records_tab()

    # ----- helpers
    def _ceremony_label(self, c: dict) -> str:
        return (f"#{c['ceremony_id']} — {c['ceremony_name']} "
                f"({c['ceremony_date']} {c['ceremony_time']}) @ {c['venue']}")

    def _reload_ceremonies(self):
        rows = CeremonyManager.list_ceremonies()
        self._ceremonies = rows
        self.ceremony_combo['values'] = [self._ceremony_label(c) for c in rows]
        if rows:
            # preserve selection where possible
            idx = 0
            if self.current_ceremony_id is not None:
                for i, c in enumerate(rows):
                    if c['ceremony_id'] == self.current_ceremony_id:
                        idx = i
                        break
            self.ceremony_combo.current(idx)
            self.current_ceremony_id = rows[idx]['ceremony_id']
        else:
            self.ceremony_combo.set('')
            self.current_ceremony_id = None
        self._reload_ceremonies_table()
        self._reload_active_tabs()
        self._update_capacity_label()

    def _on_ceremony_selected(self, _evt=None):
        sel = self.ceremony_combo.current()
        if 0 <= sel < len(self._ceremonies):
            self.current_ceremony_id = self._ceremonies[sel]['ceremony_id']
            self._reload_active_tabs()
            self._update_capacity_label()

    def _reload_active_tabs(self):
        self._reload_rsvp_table()
        self._reload_gown_table()
        self._reload_seat_table()
        self._refresh_script_preview()
        if hasattr(self, 'print_tree'):
            self._reload_print_queue()
        if hasattr(self, '_stu_status'):
            self._reload_student_tab()

    # ----- window / identity helpers
    def _close(self):
        """Close only the graduation window, leaving the rest of the app open.

        When standalone we own a Toplevel/Tk and destroy it. When embedded in a
        workspace frame we only clear our own widgets so the host survives."""
        try:
            if getattr(self, '_owned_window', False):
                self.window.destroy()
            else:
                for child in self.window.winfo_children():
                    child.destroy()
        except Exception:
            pass

    def _is_student(self) -> bool:
        """True only when the signed-in user's role is 'student'.

        Mirrors ``CourseManagementGUI.get_user_role`` so the self-service tab is
        offered to exactly the same accounts the host app treats as students."""
        user = getattr(self.auth, 'current_user', None) if self.auth else None
        if not user:
            return False
        role = None
        if isinstance(user, dict):
            role = user.get('role')
        elif hasattr(user, 'role'):
            role = user.role
        return bool(role) and str(role).lower() == 'student'

    def _current_student_id(self) -> Optional[str]:
        """Best-effort student ID for the signed-in user (self-service tab)."""
        user = getattr(self.auth, 'current_user', None) if self.auth else None
        if not user:
            return None
        sid = user.get('student_id') or user.get('university_student_id')
        if sid:
            return sid
        username = user.get('username', '') or ''
        if username.startswith('S') or username.isdigit():
            return username
        return None

    def _update_capacity_label(self):
        if self.current_ceremony_id is None:
            self.capacity_label.config(text="")
            return
        cap = CeremonyManager.capacity_summary(self.current_ceremony_id)
        self.capacity_label.config(
            text=(f"Capacity: {cap['total']}/{cap['capacity']} "
                  f"(graduands: {cap['graduands']}, guests: {cap['guests']}, "
                  f"free: {cap['free']})")
        )

    # =========================================================== Student tab
    def _build_student_tab(self):
        """Self-service tab for the signed-in student: confirm their own RSVP,
        order their gown, and look up their assigned seat. All actions are
        scoped to the student's own ID — no access to other graduands."""
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="⭐ My Graduation")

        sid = self._current_student_id()
        header = ttk.Frame(tab)
        header.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(
            header,
            text=(f"Signed in as student: {sid}" if sid
                  else "No student record is linked to your account."),
            font=("Arial", 11, "bold"),
            foreground=("#004b8d" if sid else "#8d0000"),
        ).pack(side=tk.LEFT)

        self._stu_sid = sid

        # --- My RSVP -------------------------------------------------------
        rsvp = ttk.LabelFrame(tab, text="My RSVP", padding=10)
        rsvp.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(rsvp, text="Attending?").grid(row=0, column=0, sticky="e", padx=6, pady=4)
        self._stu_status = ttk.Combobox(
            rsvp, width=14, state="readonly",
            values=["going", "not_going", "interested", "pending"])
        self._stu_status.set("going")
        self._stu_status.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(rsvp, text="Guests:").grid(row=0, column=2, sticky="e", padx=6)
        self._stu_guests = ttk.Spinbox(rsvp, from_=0, to=10, width=5)
        self._stu_guests.set(0)
        self._stu_guests.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(rsvp, text="Accessibility needs:").grid(row=1, column=0, sticky="e", padx=6, pady=4)
        self._stu_access = ttk.Entry(rsvp, width=44)
        self._stu_access.grid(row=1, column=1, columnspan=3, sticky="we", padx=6)

        ttk.Label(rsvp, text="Name pronunciation:").grid(row=2, column=0, sticky="e", padx=6, pady=4)
        self._stu_pron = ttk.Entry(rsvp, width=44)
        self._stu_pron.grid(row=2, column=1, columnspan=3, sticky="we", padx=6)

        ttk.Button(rsvp, text="💾 Save my RSVP",
                   command=self._on_student_save_rsvp).grid(
                       row=3, column=0, columnspan=2, sticky="w", padx=6, pady=(8, 0))

        # --- My gown order -------------------------------------------------
        gown = ttk.LabelFrame(tab, text="My Gown Order", padding=10)
        gown.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(gown, text="Gown size:").grid(row=0, column=0, sticky="e", padx=6, pady=4)
        self._stu_gown_size = ttk.Combobox(gown, width=8, state="readonly",
                                            values=GownOrderManager.GOWN_SIZES)
        self._stu_gown_size.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(gown, text="Hat size:").grid(row=0, column=2, sticky="e", padx=6)
        self._stu_hat_size = ttk.Combobox(gown, width=6, state="readonly",
                                          values=GownOrderManager.HAT_SIZES)
        self._stu_hat_size.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(gown, text="Hood subject:").grid(row=1, column=0, sticky="e", padx=6, pady=4)
        self._stu_hood = ttk.Entry(gown, width=28)
        self._stu_hood.grid(row=1, column=1, columnspan=3, sticky="we", padx=6)

        ttk.Label(gown, text="Pay by:").grid(row=2, column=0, sticky="e", padx=6, pady=4)
        self._stu_pay_method = ttk.Combobox(
            gown, width=22, state="readonly",
            values=["Cash", "Card", "Student Finance Account"])
        self._stu_pay_method.set("Card")
        self._stu_pay_method.grid(row=2, column=1, sticky="w", padx=6)

        self._stu_gown_cost = ttk.Label(gown, text="", foreground="#005c1f")
        self._stu_gown_cost.grid(row=2, column=2, columnspan=2, sticky="w", padx=6)
        # Live-quote the cost as the student changes their selection.
        for w in (self._stu_gown_size, self._stu_hat_size):
            w.bind("<<ComboboxSelected>>", lambda _e: self._update_student_gown_cost())
        self._stu_hood.bind("<KeyRelease>", lambda _e: self._update_student_gown_cost())

        ttk.Button(gown, text="💾 Save order (no payment)",
                   command=self._on_student_save_gown).grid(
                       row=3, column=0, columnspan=2, sticky="w", padx=6, pady=(8, 0))
        ttk.Button(gown, text="💳 Pay & confirm order",
                   command=self._on_student_pay_gown).grid(
                       row=3, column=2, columnspan=2, sticky="w", padx=6, pady=(8, 0))

        # --- My seat -------------------------------------------------------
        seat = ttk.LabelFrame(tab, text="My Seat", padding=10)
        seat.pack(fill=tk.X)
        self._stu_seat_label = ttk.Label(seat, text="—", font=("Arial", 11))
        self._stu_seat_label.pack(side=tk.LEFT, padx=6)
        ttk.Button(seat, text="🔄 Refresh",
                   command=self._reload_student_tab).pack(side=tk.RIGHT)

        # Disable the action widgets when there is no linked student.
        if not sid:
            for w in (self._stu_status, self._stu_guests, self._stu_access,
                      self._stu_pron, self._stu_gown_size, self._stu_hat_size,
                      self._stu_hood, self._stu_pay_method):
                try:
                    w.config(state="disabled")
                except Exception:
                    pass

    def _reload_student_tab(self):
        """Populate the self-service tab from the student's own records."""
        if not hasattr(self, '_stu_status'):
            return
        sid = self._stu_sid
        if not sid or self.current_ceremony_id is None:
            self._stu_seat_label.config(text="—")
            return

        # Prefill RSVP from any existing record.
        try:
            mine = next((r for r in RsvpManager.list_rsvps(self.current_ceremony_id)
                         if str(r['student_id']) == str(sid)), None)
        except Exception:
            mine = None
        if mine:
            self._stu_status.set(mine.get('rsvp_status', 'going'))
            self._stu_guests.delete(0, tk.END)
            self._stu_guests.insert(0, str(mine.get('num_guests', 0)))
            self._stu_access.delete(0, tk.END)
            self._stu_access.insert(0, mine.get('accessibility_notes', '') or '')
            self._stu_pron.delete(0, tk.END)
            self._stu_pron.insert(0, mine.get('name_pronunciation', '') or '')

        # Prefill gown order from any existing record.
        try:
            order = next((o for o in GownOrderManager.list_orders(self.current_ceremony_id)
                          if str(o['student_id']) == str(sid)), None)
        except Exception:
            order = None
        if order:
            self._stu_gown_size.set(order.get('gown_size', '') or '')
            self._stu_hat_size.set(order.get('hat_size', '') or '')
            self._stu_hood.delete(0, tk.END)
            self._stu_hood.insert(0, order.get('hood_subject', '') or '')
        self._update_student_gown_cost(order)

        # Show the assigned seat, if any.
        try:
            seat = next((s for s in SeatPlanManager.list_plan(self.current_ceremony_id)
                         if str(s['student_id']) == str(sid)), None)
        except Exception:
            seat = None
        if seat:
            self._stu_seat_label.config(
                text=(f"Section {seat['section']} · Row {seat['row_label']} · "
                      f"Seat {seat['seat_number']}"
                      + ("  (accessibility)" if seat.get('is_accessibility') else "")))
        else:
            self._stu_seat_label.config(text="Not assigned yet.")

    def _on_student_save_rsvp(self):
        sid = self._stu_sid
        if not sid:
            messagebox.showwarning("Not available", "No student record is linked to your account.")
            return
        if self.current_ceremony_id is None:
            messagebox.showwarning("Ceremony", "Select a ceremony at the top first.")
            return
        if not self._eligibility_ok(sid, self._stu_status.get()):
            return
        try:
            RsvpManager.record_rsvp(
                ceremony_id=self.current_ceremony_id,
                student_id=sid,
                rsvp_status=self._stu_status.get(),
                num_guests=int(self._stu_guests.get() or 0),
                accessibility_notes=self._stu_access.get().strip(),
                name_pronunciation=self._stu_pron.get().strip(),
            )
            self._reload_rsvp_table()
            self._update_capacity_label()
            messagebox.showinfo("RSVP", "Your RSVP has been saved.")
        except ValueError as ve:
            messagebox.showwarning("RSVP", str(ve))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_student_save_gown(self):
        sid = self._stu_sid
        if not sid:
            messagebox.showwarning("Not available", "No student record is linked to your account.")
            return
        if self.current_ceremony_id is None:
            messagebox.showwarning("Ceremony", "Select a ceremony at the top first.")
            return
        if not self._stu_gown_size.get():
            messagebox.showwarning("Gown", "Choose a gown size.")
            return
        try:
            GownOrderManager.create_order(
                ceremony_id=self.current_ceremony_id,
                student_id=sid,
                gown_size=self._stu_gown_size.get(),
                hood_subject=self._stu_hood.get().strip(),
                hat_size=self._stu_hat_size.get(),
            )
            self._reload_gown_table()
            self._update_student_gown_cost()
            messagebox.showinfo("Gown order", "Your gown order has been saved.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # Display label -> service key for the payment-method selector.
    _PAY_METHOD_KEYS = {
        "Cash": "cash",
        "Card": "card",
        "Student Finance Account": "student_finance_account",
    }

    def _update_student_gown_cost(self, order=None):
        """Refresh the live cost label from the current gown selection."""
        if not hasattr(self, '_stu_gown_cost'):
            return
        cost = GownOrderManager.quote(
            self._stu_gown_size.get(), self._stu_hood.get().strip(),
            self._stu_hat_size.get())
        paid = bool(order and (order.get('payment_status') == 'paid'))
        if paid:
            self._stu_gown_cost.config(
                text=f"PAID · £{float(order.get('cost') or cost):.2f}",
                foreground="#005c1f")
        else:
            self._stu_gown_cost.config(text=f"Total: £{cost:.2f}",
                                       foreground="#444")

    def _on_student_pay_gown(self):
        sid = self._stu_sid
        if not sid:
            messagebox.showwarning("Not available", "No student record is linked to your account.")
            return
        if self.current_ceremony_id is None:
            messagebox.showwarning("Ceremony", "Select a ceremony at the top first.")
            return
        if not self._stu_gown_size.get():
            messagebox.showwarning("Gown", "Choose a gown size.")
            return
        method = self._PAY_METHOD_KEYS.get(self._stu_pay_method.get())
        if not method:
            messagebox.showwarning("Payment", "Choose a payment method.")
            return
        try:
            order_id = GownOrderManager.create_order(
                ceremony_id=self.current_ceremony_id,
                student_id=sid,
                gown_size=self._stu_gown_size.get(),
                hood_subject=self._stu_hood.get().strip(),
                hat_size=self._stu_hat_size.get(),
            )
            result = GownOrderManager.process_payment(
                order_id=order_id,
                payment_method=method,
                processed_by=sid,
            )
        except ValueError as ve:
            messagebox.showwarning("Payment", str(ve))
            return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self._reload_gown_table()
        self._reload_student_tab()
        msg = (f"Payment of £{result['amount']:.2f} recorded "
               f"({self._stu_pay_method.get()}).\nReference: {result['reference']}\n"
               "A receipt has been emailed to you.")
        if result.get('balance_remaining') is not None:
            msg += (f"\nFinance account balance remaining: "
                    f"£{result['balance_remaining']:.2f}")
        messagebox.showinfo("Gown order paid", msg)

    # =============================================================== Tab 1
    def _build_ceremonies_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="1. Ceremonies")

        # Form
        form = ttk.LabelFrame(tab, text="Schedule / edit a ceremony", padding=10)
        form.pack(fill=tk.X)

        # Plain text fields keep the generic entry dict.
        self._cer_entries = {}

        def _text_field(label, row, col, default="", width=28):
            ttk.Label(form, text=label + ":").grid(
                row=row, column=col, sticky="e", padx=6, pady=4)
            e = ttk.Entry(form, width=width)
            e.insert(0, default)
            e.grid(row=row, column=col + 1, sticky="w", padx=6, pady=4)
            self._cer_entries[label] = e
            return e

        # Row 0: Name | Venue (linked to the buildings table)
        _text_field("Name", 0, 0, "Summer Graduation")

        ttk.Label(form, text="Venue:").grid(row=0, column=2, sticky="e", padx=6, pady=4)
        venue_box = ttk.Frame(form)
        venue_box.grid(row=0, column=3, sticky="w", padx=6, pady=4)
        self._cer_venue = ttk.Combobox(venue_box, width=26, state="readonly")
        self._cer_venue.pack(side=tk.LEFT)
        ttk.Button(venue_box, text="🔄", width=3,
                   command=self._reload_venues).pack(side=tk.LEFT, padx=(4, 0))

        # Row 1: Date picker | Time steppers
        ttk.Label(form, text="Date:").grid(row=1, column=0, sticky="e", padx=6, pady=4)
        today = datetime.now()
        if _HAS_TKCALENDAR:
            self._cer_date = DateEntry(
                form, width=18, date_pattern="yyyy-mm-dd",
                showweeknumbers=False)
            self._cer_date.set_date(today)
        else:
            self._cer_date = ttk.Entry(form, width=20)
            self._cer_date.insert(0, today.strftime("%Y-%m-%d"))
        self._cer_date.grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(form, text="Time:").grid(row=1, column=2, sticky="e", padx=6, pady=4)
        time_box = ttk.Frame(form)
        time_box.grid(row=1, column=3, sticky="w", padx=6, pady=4)
        self._cer_hour = ttk.Spinbox(time_box, from_=0, to=23, width=4,
                                     format="%02.0f", wrap=True)
        self._cer_hour.set("14")
        self._cer_hour.pack(side=tk.LEFT)
        ttk.Label(time_box, text=":").pack(side=tk.LEFT, padx=2)
        self._cer_minute = ttk.Spinbox(time_box, from_=0, to=55, increment=5,
                                       width=4, format="%02.0f", wrap=True)
        self._cer_minute.set("00")
        self._cer_minute.pack(side=tk.LEFT)

        # Row 2: Capacity | Guests per graduand
        _text_field("Capacity", 2, 0, "300", width=10)
        _text_field("Guests per graduand", 2, 2, "2", width=10)

        # Row 3: Cohort filter (full width)
        _text_field("Cohort filter (e.g. BSc CS 2025/26)", 3, 0, "", width=60)

        # Row 4: RSVP deadline picker (optional)
        ttk.Label(form, text="RSVP deadline:").grid(row=4, column=0, sticky="e", padx=6, pady=4)
        deadline_box = ttk.Frame(form)
        deadline_box.grid(row=4, column=1, sticky="w", padx=6, pady=4)
        if _HAS_TKCALENDAR:
            self._cer_deadline = DateEntry(
                deadline_box, width=18, date_pattern="yyyy-mm-dd",
                showweeknumbers=False)
            self._cer_deadline.delete(0, tk.END)  # optional → start empty
        else:
            self._cer_deadline = ttk.Entry(deadline_box, width=20)
        self._cer_deadline.pack(side=tk.LEFT)
        ttk.Button(deadline_box, text="✖ Clear", command=self._clear_deadline).pack(
            side=tk.LEFT, padx=(4, 0))
        ttk.Label(deadline_box, text="(leave blank for none)",
                  foreground="#888").pack(side=tk.LEFT, padx=(6, 0))

        self._reload_venues()

        btn_row = ttk.Frame(form)
        btn_row.grid(row=5, column=0, columnspan=4, pady=(8, 0), sticky="w")
        ttk.Button(btn_row, text="➕ Create",  command=self._on_create_ceremony).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="💾 Update selected", command=self._on_update_ceremony).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="🗑️ Cancel selected",
                   command=lambda: self._set_ceremony_status('cancelled')).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="✅ Mark completed",
                   command=lambda: self._set_ceremony_status('completed')).pack(side=tk.LEFT, padx=4)

        # Table
        table_frame = ttk.LabelFrame(tab, text="All ceremonies", padding=6)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        cols = ("id", "name", "date", "time", "venue", "capacity", "cohort", "status")
        self.cer_tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (40, 200, 100, 70, 180, 80, 200, 100)):
            self.cer_tree.heading(c, text=c.title())
            self.cer_tree.column(c, width=w, anchor="w")
        self.cer_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scr = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.cer_tree.yview)
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        self.cer_tree.configure(yscrollcommand=scr.set)
        self.cer_tree.bind("<<TreeviewSelect>>", self._on_cer_tree_select)

    # ----- venue / date / time field helpers
    def _reload_venues(self):
        """Populate the venue dropdown from the buildings table.

        Keeps it strictly a picker (read-only) when buildings exist so a venue
        can't be mistyped; falls back to free text only if the table is empty
        or unavailable, preserving whatever value is already selected."""
        try:
            self._venues = CeremonyManager.list_venues()
        except Exception:
            self._venues = []
        current = self._cer_venue.get()
        labels = [v['building_name'] for v in self._venues]
        self._cer_venue['values'] = labels
        if labels:
            self._cer_venue.config(state="readonly")
            if current in labels:
                self._cer_venue.set(current)
        else:
            # No buildings on file — let the user type a venue manually.
            self._cer_venue.config(state="normal")
            if current:
                self._cer_venue.set(current)

    def _clear_deadline(self):
        try:
            self._cer_deadline.delete(0, tk.END)
        except Exception:
            pass

    def _set_date_widget(self, widget, value):
        """Set a date widget (tkcalendar DateEntry or plain Entry) from a string."""
        try:
            widget.delete(0, tk.END)
        except Exception:
            pass
        if not value:
            return
        if _HAS_TKCALENDAR and isinstance(widget, DateEntry):
            try:
                widget.set_date(value)
                return
            except Exception:
                pass
        try:
            widget.insert(0, value)
        except Exception:
            pass

    def _set_venue(self, value):
        value = (value or '').strip()
        labels = [v['building_name'] for v in getattr(self, '_venues', [])]
        if value and value not in labels:
            # Venue from an older record / external building — show it without
            # losing the value, even though it's not in the current picker list.
            self._cer_venue.config(state="normal")
        self._cer_venue.set(value)

    def _set_time(self, value):
        hh, mm = "14", "00"
        if value and ":" in value:
            parts = value.split(":")
            hh, mm = parts[0].strip(), parts[1].strip()
        self._cer_hour.set(f"{int(hh or 0):02d}" if (hh or '').isdigit() else hh)
        self._cer_minute.set(f"{int(mm or 0):02d}" if (mm or '').isdigit() else mm)

    def _on_cer_tree_select(self, _evt=None):
        sel = self.cer_tree.selection()
        if not sel:
            return
        vals = self.cer_tree.item(sel[0])['values']
        if not vals:
            return
        cid = int(vals[0])
        # Find the row and populate the form.
        for c in self._ceremonies:
            if c['ceremony_id'] == cid:
                self._cer_entries["Name"].delete(0, tk.END); self._cer_entries["Name"].insert(0, c['ceremony_name'])
                self._set_date_widget(self._cer_date, c['ceremony_date'])
                self._set_time(c['ceremony_time'])
                self._set_venue(c['venue'])
                self._cer_entries["Capacity"].delete(0, tk.END); self._cer_entries["Capacity"].insert(0, str(c['capacity']))
                self._cer_entries["Cohort filter (e.g. BSc CS 2025/26)"].delete(0, tk.END); self._cer_entries["Cohort filter (e.g. BSc CS 2025/26)"].insert(0, c.get('cohort_filter') or '')
                self._set_date_widget(self._cer_deadline, c.get('rsvp_deadline') or '')
                self._cer_entries["Guests per graduand"].delete(0, tk.END); self._cer_entries["Guests per graduand"].insert(0, str(c.get('guest_tickets_per_graduand', 2)))
                self.current_ceremony_id = cid
                for i, cer in enumerate(self._ceremonies):
                    if cer['ceremony_id'] == cid:
                        self.ceremony_combo.current(i)
                        break
                self._reload_active_tabs()
                self._update_capacity_label()
                return

    def _reload_ceremonies_table(self):
        for iid in self.cer_tree.get_children():
            self.cer_tree.delete(iid)
        for c in self._ceremonies:
            self.cer_tree.insert("", tk.END, values=(
                c['ceremony_id'], c['ceremony_name'], c['ceremony_date'],
                c['ceremony_time'], c['venue'], c['capacity'],
                c.get('cohort_filter', '') or '—',
                c.get('status', 'scheduled'),
            ))

    def _form_ceremony_payload(self) -> dict:
        try:
            capacity = int(self._cer_entries["Capacity"].get().strip() or 0)
        except ValueError:
            raise ValueError("Capacity must be a number")
        try:
            guests = int(self._cer_entries["Guests per graduand"].get().strip() or 0)
        except ValueError:
            raise ValueError("Guests per graduand must be a number")
        hh = (self._cer_hour.get() or "").strip()
        mm = (self._cer_minute.get() or "").strip()
        try:
            ceremony_time = f"{int(hh):02d}:{int(mm):02d}"
        except ValueError:
            raise ValueError("Time must be a valid hour and minute")
        return {
            'ceremony_name': self._cer_entries["Name"].get().strip(),
            'ceremony_date': self._cer_date.get().strip(),
            'ceremony_time': ceremony_time,
            'venue':         self._cer_venue.get().strip(),
            'capacity':      capacity,
            'cohort_filter': self._cer_entries["Cohort filter (e.g. BSc CS 2025/26)"].get().strip(),
            'rsvp_deadline': self._cer_deadline.get().strip(),
            'guest_tickets_per_graduand': guests,
        }

    def _on_create_ceremony(self):
        try:
            p = self._form_ceremony_payload()
        except ValueError as ve:
            messagebox.showwarning("Check the form", str(ve))
            return
        missing = [name for name, key in (
            ("Name", "ceremony_name"),
            ("Date", "ceremony_date"),
            ("Time", "ceremony_time"),
            ("Venue", "venue"),
        ) if not p.get(key)]
        if missing:
            messagebox.showwarning(
                "Check the form",
                "These fields are required:\n  • " + "\n  • ".join(missing),
            )
            return
        try:
            CeremonyManager.create_ceremony(**p)
            self._reload_ceremonies()
            messagebox.showinfo("Created", "Ceremony scheduled.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_update_ceremony(self):
        if self.current_ceremony_id is None:
            messagebox.showwarning("Select", "Select a ceremony first.")
            return
        try:
            p = self._form_ceremony_payload()
            CeremonyManager.update_ceremony(self.current_ceremony_id, **p)
            self._reload_ceremonies()
            messagebox.showinfo("Updated", "Ceremony updated.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _set_ceremony_status(self, status: str):
        if self.current_ceremony_id is None:
            return
        if not messagebox.askyesno("Confirm", f"Set ceremony status to '{status}'?"):
            return

        if status == 'completed':
            # Completing a ceremony closes it AND emails every graduand who
            # attended (RSVP'd 'going') a congratulations / next-steps message.
            # complete_ceremony is idempotent — re-marking an already-completed
            # ceremony won't re-send.
            try:
                sent, total = CeremonyManager.complete_ceremony(self.current_ceremony_id)
                messagebox.showinfo(
                    "Ceremony completed",
                    f"Ceremony marked completed.\n\n"
                    f"Congratulations emails sent to {sent} of {total} graduand(s).")
            except Exception:
                messagebox.showwarning(
                    "Ceremony completed",
                    "Ceremony marked completed, but graduand emails could not be sent.")
        else:
            CeremonyManager.update_ceremony(self.current_ceremony_id, status=status)

        self._reload_ceremonies()

    # =============================================================== Tab 2
    def _build_rsvp_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="2. RSVPs")

        form = ttk.LabelFrame(tab, text="Record / update an RSVP", padding=10)
        form.pack(fill=tk.X)

        ttk.Label(form, text="Student ID:").grid(row=0, column=0, sticky="e", padx=6, pady=4)
        self.rsvp_sid = ttk.Entry(form, width=18)
        self.rsvp_sid.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Status:").grid(row=0, column=2, sticky="e", padx=6)
        self.rsvp_status = ttk.Combobox(form, width=14, state="readonly",
                                        values=["going", "not_going", "interested", "pending"])
        self.rsvp_status.set("going")
        self.rsvp_status.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(form, text="Guests:").grid(row=0, column=4, sticky="e", padx=6)
        self.rsvp_guests = ttk.Spinbox(form, from_=0, to=10, width=5)
        self.rsvp_guests.set(0)
        self.rsvp_guests.grid(row=0, column=5, sticky="w", padx=6)

        ttk.Label(form, text="Accessibility notes:").grid(row=1, column=0, sticky="e", padx=6, pady=4)
        self.rsvp_access = ttk.Entry(form, width=50)
        self.rsvp_access.grid(row=1, column=1, columnspan=3, sticky="we", padx=6)

        ttk.Label(form, text="Name pronunciation:").grid(row=1, column=4, sticky="e", padx=6)
        self.rsvp_pron = ttk.Entry(form, width=22)
        self.rsvp_pron.grid(row=1, column=5, sticky="we", padx=6)

        ttk.Button(form, text="💾 Record RSVP",
                   command=self._on_record_rsvp).grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=(8, 0))

        # Table
        table = ttk.LabelFrame(tab, text="RSVPs", padding=6)
        table.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        cols = ("sid", "name", "course", "status", "guests", "access", "pron", "recorded")
        self.rsvp_tree = ttk.Treeview(table, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (90, 200, 140, 90, 60, 200, 180, 140)):
            self.rsvp_tree.heading(c, text=c.title())
            self.rsvp_tree.column(c, width=w, anchor="w")
        self.rsvp_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scr = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.rsvp_tree.yview)
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        self.rsvp_tree.configure(yscrollcommand=scr.set)
        self.rsvp_tree.bind("<<TreeviewSelect>>", self._on_rsvp_tree_select)

    def _on_rsvp_tree_select(self, _evt=None):
        sel = self.rsvp_tree.selection()
        if not sel:
            return
        vals = self.rsvp_tree.item(sel[0])['values']
        if not vals:
            return
        self.rsvp_sid.delete(0, tk.END); self.rsvp_sid.insert(0, str(vals[0]))
        self.rsvp_status.set(vals[3])
        self.rsvp_guests.delete(0, tk.END); self.rsvp_guests.insert(0, str(vals[4]))
        self.rsvp_access.delete(0, tk.END); self.rsvp_access.insert(0, str(vals[5] or ''))
        self.rsvp_pron.delete(0, tk.END); self.rsvp_pron.insert(0, str(vals[6] or ''))

    def _eligibility_ok(self, student_id, rsvp_status):
        """Gate graduand RSVPs on graduation eligibility.

        Declining ('not_going') is always allowed. For any status that makes the
        student a graduand, refuse when they're not eligible to graduate; if
        eligibility can't be computed, warn and let the operator decide."""
        if (rsvp_status or "").strip().lower() == "not_going":
            return True
        report = check_eligibility(student_id)
        if report.get("eligible"):
            return True
        if report.get("error"):
            return messagebox.askyesno(
                "Eligibility unverified",
                f"Could not verify graduation eligibility for {student_id}.\n\n"
                f"{' '.join(report.get('reasons', []))}\n\nAdd them anyway?")
        reasons = "\n".join(f"  • {r}" for r in report.get("reasons", []))
        messagebox.showwarning(
            "Not eligible for graduation",
            f"{report.get('student_name', student_id)} cannot be added as a "
            f"graduand — they are not eligible to graduate:\n\n{reasons}\n\n"
            "Run a graduation audit in Degree Audit first.")
        return False

    def _on_record_rsvp(self):
        if self.current_ceremony_id is None:
            messagebox.showwarning("Ceremony", "Select a ceremony first.")
            return
        sid = self.rsvp_sid.get().strip()
        if not sid:
            messagebox.showwarning("Student", "Enter a student ID.")
            return
        if not self._eligibility_ok(sid, self.rsvp_status.get()):
            return
        try:
            RsvpManager.record_rsvp(
                ceremony_id=self.current_ceremony_id,
                student_id=sid,
                rsvp_status=self.rsvp_status.get(),
                num_guests=int(self.rsvp_guests.get() or 0),
                accessibility_notes=self.rsvp_access.get().strip(),
                name_pronunciation=self.rsvp_pron.get().strip(),
            )
            self._reload_rsvp_table()
            self._update_capacity_label()
            messagebox.showinfo("RSVP", "RSVP recorded.")
        except ValueError as ve:
            messagebox.showwarning("RSVP", str(ve))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _reload_rsvp_table(self):
        for iid in self.rsvp_tree.get_children():
            self.rsvp_tree.delete(iid)
        if self.current_ceremony_id is None:
            return
        for r in RsvpManager.list_rsvps(self.current_ceremony_id):
            self.rsvp_tree.insert("", tk.END, values=(
                r['student_id'], r.get('student_name', ''),
                r.get('course', ''), r['rsvp_status'], r['num_guests'],
                r.get('accessibility_notes', ''),
                r.get('name_pronunciation', ''),
                r.get('recorded_at', ''),
            ))

    # =============================================================== Tab 3
    def _build_gown_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="3. Gown Orders")

        form = ttk.LabelFrame(tab, text="Place / update a gown order", padding=10)
        form.pack(fill=tk.X)

        ttk.Label(form, text="Student ID:").grid(row=0, column=0, sticky="e", padx=6, pady=4)
        self.gown_sid = ttk.Entry(form, width=18)
        self.gown_sid.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Gown size:").grid(row=0, column=2, sticky="e", padx=6)
        self.gown_size = ttk.Combobox(form, width=8, state="readonly",
                                      values=GownOrderManager.GOWN_SIZES)
        self.gown_size.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(form, text="Hat size:").grid(row=0, column=4, sticky="e", padx=6)
        self.hat_size = ttk.Combobox(form, width=6, state="readonly",
                                     values=GownOrderManager.HAT_SIZES)
        self.hat_size.grid(row=0, column=5, sticky="w", padx=6)

        ttk.Label(form, text="Hood subject:").grid(row=1, column=0, sticky="e", padx=6)
        self.hood_subject = ttk.Entry(form, width=24)
        self.hood_subject.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Supplier:").grid(row=1, column=2, sticky="e", padx=6)
        self.gown_supplier = ttk.Entry(form, width=22)
        self.gown_supplier.grid(row=1, column=3, sticky="w", padx=6)

        ttk.Label(form, text="Collection slot:").grid(row=1, column=4, sticky="e", padx=6)
        self.gown_slot = ttk.Entry(form, width=22)
        self.gown_slot.grid(row=1, column=5, sticky="w", padx=6)

        actions = ttk.Frame(form)
        actions.grid(row=2, column=0, columnspan=6, sticky="w", padx=6, pady=(8, 0))
        ttk.Button(actions, text="💾 Save order", command=self._on_save_gown).pack(side=tk.LEFT, padx=4)
        for st in ('arrived', 'collected', 'returned', 'cancelled'):
            ttk.Button(actions, text=f"Mark {st}",
                       command=lambda s=st: self._on_set_gown_status(s)).pack(side=tk.LEFT, padx=4)

        pay = ttk.Frame(form)
        pay.grid(row=3, column=0, columnspan=6, sticky="w", padx=6, pady=(6, 0))
        ttk.Label(pay, text="Take payment by:").pack(side=tk.LEFT, padx=(0, 4))
        self.gown_pay_method = ttk.Combobox(
            pay, width=22, state="readonly",
            values=["Cash", "Card", "Student Finance Account"])
        self.gown_pay_method.set("Card")
        self.gown_pay_method.pack(side=tk.LEFT, padx=4)
        ttk.Button(pay, text="💳 Take payment for selected order",
                   command=self._on_take_gown_payment).pack(side=tk.LEFT, padx=8)

        table = ttk.LabelFrame(tab, text="Gown orders for this ceremony", padding=6)
        table.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        cols = ("oid", "sid", "name", "gown", "hat", "hood", "supplier", "slot",
                "status", "cost", "payment")
        self.gown_tree = ttk.Treeview(table, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (50, 90, 180, 50, 50, 140, 140, 140, 80, 70, 150)):
            self.gown_tree.heading(c, text=c.title())
            self.gown_tree.column(c, width=w, anchor="w")
        self.gown_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scr = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.gown_tree.yview)
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        self.gown_tree.configure(yscrollcommand=scr.set)
        self.gown_tree.bind("<<TreeviewSelect>>", self._on_gown_tree_select)

    def _on_gown_tree_select(self, _evt=None):
        sel = self.gown_tree.selection()
        if not sel:
            return
        vals = self.gown_tree.item(sel[0])['values']
        if not vals:
            return
        self._selected_gown_order_id = int(vals[0])
        self.gown_sid.delete(0, tk.END); self.gown_sid.insert(0, str(vals[1]))
        self.gown_size.set(vals[3] or '')
        self.hat_size.set(vals[4] or '')
        self.hood_subject.delete(0, tk.END); self.hood_subject.insert(0, str(vals[5] or ''))
        self.gown_supplier.delete(0, tk.END); self.gown_supplier.insert(0, str(vals[6] or ''))
        self.gown_slot.delete(0, tk.END); self.gown_slot.insert(0, str(vals[7] or ''))

    def _on_save_gown(self):
        if self.current_ceremony_id is None:
            messagebox.showwarning("Ceremony", "Select a ceremony first.")
            return
        sid = self.gown_sid.get().strip()
        if not sid:
            messagebox.showwarning("Student", "Enter a student ID.")
            return
        try:
            GownOrderManager.create_order(
                ceremony_id=self.current_ceremony_id,
                student_id=sid,
                gown_size=self.gown_size.get(),
                hood_subject=self.hood_subject.get().strip(),
                hat_size=self.hat_size.get(),
                supplier=self.gown_supplier.get().strip(),
                collection_slot=self.gown_slot.get().strip(),
            )
            self._reload_gown_table()
            messagebox.showinfo("Saved", "Gown order saved.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_set_gown_status(self, status: str):
        oid = getattr(self, '_selected_gown_order_id', None)
        if not oid:
            messagebox.showwarning("Select", "Select an order in the table first.")
            return
        try:
            GownOrderManager.update_status(oid, status)
            self._reload_gown_table()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_take_gown_payment(self):
        oid = getattr(self, '_selected_gown_order_id', None)
        if not oid:
            messagebox.showwarning("Select", "Select an order in the table first.")
            return
        method = self._PAY_METHOD_KEYS.get(self.gown_pay_method.get())
        if not method:
            messagebox.showwarning("Payment", "Choose a payment method.")
            return
        processed_by = (self.auth.current_user.get('username')
                        if self.auth and getattr(self.auth, 'current_user', None)
                        else 'staff')
        try:
            result = GownOrderManager.process_payment(
                order_id=oid, payment_method=method, processed_by=processed_by)
        except ValueError as ve:
            messagebox.showwarning("Payment", str(ve))
            return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self._reload_gown_table()
        msg = (f"Payment of £{result['amount']:.2f} recorded "
               f"({self.gown_pay_method.get()}).\nReference: {result['reference']}\n"
               "A receipt has been emailed to the student.")
        if result.get('balance_remaining') is not None:
            msg += (f"\nFinance account balance remaining: "
                    f"£{result['balance_remaining']:.2f}")
        messagebox.showinfo("Payment recorded", msg)

    def _reload_gown_table(self):
        for iid in self.gown_tree.get_children():
            self.gown_tree.delete(iid)
        if self.current_ceremony_id is None:
            return
        for r in GownOrderManager.list_orders(self.current_ceremony_id):
            pay_status = r.get('payment_status', 'unpaid') or 'unpaid'
            method = r.get('payment_method', '') or ''
            method_disp = GownOrderManager.PAYMENT_METHOD_DISPLAY.get(method, method)
            payment_cell = (f"{pay_status}" + (f" · {method_disp}" if method_disp else ''))
            self.gown_tree.insert("", tk.END, values=(
                r['order_id'], r['student_id'], r.get('student_name', ''),
                r.get('gown_size', ''), r.get('hat_size', ''),
                r.get('hood_subject', ''), r.get('supplier', ''),
                r.get('collection_slot', ''), r.get('status', ''),
                f"£{float(r.get('cost') or 0):.2f}", payment_cell,
            ))

    # =============================================================== Tab 4
    def _build_seat_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="4. Seat Plan")

        controls = ttk.LabelFrame(tab, text="Generator", padding=10)
        controls.pack(fill=tk.X)

        ttk.Label(controls, text="Seats per row:").pack(side=tk.LEFT, padx=4)
        self.seats_per_row = ttk.Spinbox(controls, from_=4, to=30, width=5)
        self.seats_per_row.set(12)
        self.seats_per_row.pack(side=tk.LEFT, padx=4)

        ttk.Label(controls, text="Accessibility rows:").pack(side=tk.LEFT, padx=8)
        self.access_rows = ttk.Spinbox(controls, from_=0, to=10, width=5)
        self.access_rows.set(1)
        self.access_rows.pack(side=tk.LEFT, padx=4)

        ttk.Button(controls, text="⚙️ Auto-assign seats",
                   command=self._on_auto_assign).pack(side=tk.LEFT, padx=12)
        ttk.Button(controls, text="🧹 Clear seat plan",
                   command=self._on_clear_seats).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="⬇️ Export CSV",
                   command=self._on_export_seats).pack(side=tk.LEFT, padx=4)

        table = ttk.LabelFrame(tab, text="Seat plan", padding=6)
        table.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        cols = ("section", "row", "seat", "sid", "name", "course", "access", "notes")
        self.seat_tree = ttk.Treeview(table, columns=cols, show="headings", height=22)
        for c, w in zip(cols, (80, 80, 60, 90, 200, 140, 100, 220)):
            self.seat_tree.heading(c, text=c.title())
            self.seat_tree.column(c, width=w, anchor="w")
        self.seat_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scr = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.seat_tree.yview)
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        self.seat_tree.configure(yscrollcommand=scr.set)

    def _on_auto_assign(self):
        if self.current_ceremony_id is None:
            messagebox.showwarning("Ceremony", "Select a ceremony first.")
            return
        try:
            spr = int(self.seats_per_row.get() or 12)
            acc = int(self.access_rows.get() or 1)
            count = SeatPlanManager.auto_assign(
                self.current_ceremony_id, seats_per_row=spr, accessibility_rows=acc,
            )
            self._reload_seat_table()
            self._refresh_script_preview()
            messagebox.showinfo("Seat plan", f"Assigned {count} seat(s).")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_clear_seats(self):
        if self.current_ceremony_id is None:
            return
        if not messagebox.askyesno("Confirm", "Wipe the seat plan for this ceremony?"):
            return
        SeatPlanManager.clear_assignments(self.current_ceremony_id)
        self._reload_seat_table()
        self._refresh_script_preview()

    def _on_export_seats(self):
        if self.current_ceremony_id is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.window,
            title="Save seat plan CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
            initialfile=f"seat_plan_ceremony_{self.current_ceremony_id}.csv",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(SeatPlanManager.export_csv(self.current_ceremony_id))
            messagebox.showinfo("Saved", f"Seat plan exported:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _reload_seat_table(self):
        for iid in self.seat_tree.get_children():
            self.seat_tree.delete(iid)
        if self.current_ceremony_id is None:
            return
        for r in SeatPlanManager.list_plan(self.current_ceremony_id):
            self.seat_tree.insert("", tk.END, values=(
                r['section'], r['row_label'], r['seat_number'],
                r['student_id'], r.get('student_name', ''),
                r.get('course', ''),
                'YES' if r.get('is_accessibility') else '',
                r.get('notes', ''),
            ))

    # =============================================================== Tab 5
    def _build_script_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="5. Stage Script")

        controls = ttk.Frame(tab)
        controls.pack(fill=tk.X)
        self.include_pron = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Include pronunciation lines",
                        variable=self.include_pron,
                        command=self._refresh_script_preview).pack(side=tk.LEFT)
        ttk.Button(controls, text="🔄 Refresh preview",
                   command=self._refresh_script_preview).pack(side=tk.LEFT, padx=12)
        ttk.Button(controls, text="⬇️ Export script (.txt)",
                   command=self._on_export_script).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="⬇️ Export pronunciation list (CSV)",
                   command=self._on_export_pron).pack(side=tk.LEFT, padx=4)

        self.script_text = tk.Text(tab, wrap="none", height=30,
                                   font=("Courier New", 10))
        self.script_text.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        scr = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.script_text.yview)
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        self.script_text.configure(yscrollcommand=scr.set)

    def _refresh_script_preview(self):
        self.script_text.delete("1.0", tk.END)
        if self.current_ceremony_id is None:
            return
        try:
            text = StageScriptManager.build_script(
                self.current_ceremony_id,
                include_pronunciation=bool(self.include_pron.get()),
            )
            self.script_text.insert("1.0", text)
        except Exception as e:
            self.script_text.insert("1.0", f"Script error: {e}")

    def _on_export_script(self):
        if self.current_ceremony_id is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.window, defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All", "*.*")],
            initialfile=f"stage_script_ceremony_{self.current_ceremony_id}.txt",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(StageScriptManager.build_script(
                    self.current_ceremony_id,
                    include_pronunciation=bool(self.include_pron.get()),
                ))
            messagebox.showinfo("Saved", f"Script exported:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_export_pron(self):
        if self.current_ceremony_id is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.window, defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
            initialfile=f"pronunciation_ceremony_{self.current_ceremony_id}.csv",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(StageScriptManager.export_name_pronunciation_csv(
                    self.current_ceremony_id,
                ))
            messagebox.showinfo("Saved", f"Pronunciation list exported:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))


    # =============================================================== Tab 6
    def _build_records_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="6. Records & Artefacts")

        # Quick jump to the full Alumni Management system — graduands moved
        # across by the conferral package show up there.
        topbar = ttk.Frame(tab)
        topbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(topbar, text="🎓 Open Alumni System",
                   command=self._open_alumni_system).pack(side=tk.RIGHT)

        # Conferral package — one-click for the four steps.
        package = ttk.LabelFrame(
            tab, text="Conferral package (parchment + diploma + freeze + alumni)",
            padding=10,
        )
        package.pack(fill=tk.X)

        ttk.Label(package, text="Student ID:").grid(row=0, column=0, sticky="e", padx=6, pady=4)
        self.rec_sid = ttk.Entry(package, width=14)
        self.rec_sid.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(package, text="Course / award:").grid(row=0, column=2, sticky="e", padx=6)
        self.rec_course = ttk.Entry(package, width=28)
        self.rec_course.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(package, text="Classification:").grid(row=0, column=4, sticky="e", padx=6)
        self.rec_class = ttk.Combobox(package, width=18, state="readonly", values=[
            'First Class Honours', 'Upper Second Class (2:1)',
            'Lower Second Class (2:2)', 'Third Class', 'Pass',
            'Distinction', 'Merit', '(no classification)',
        ])
        self.rec_class.set('Upper Second Class (2:1)')
        self.rec_class.grid(row=0, column=5, sticky="w", padx=6)

        ttk.Label(package, text="Academic year:").grid(row=1, column=0, sticky="e", padx=6)
        self.rec_year = ttk.Entry(package, width=14)
        self.rec_year.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(package, text="Grad. year:").grid(row=1, column=2, sticky="e", padx=6)
        self.rec_grad_year = ttk.Entry(package, width=8)
        self.rec_grad_year.insert(0, str(datetime.now().year))
        self.rec_grad_year.grid(row=1, column=3, sticky="w", padx=6)

        ttk.Button(package, text="🎁 Issue full conferral package",
                   command=self._on_issue_package).grid(
                       row=1, column=4, columnspan=2, sticky="w", padx=6, pady=(4, 0))

        # Print queue table.
        pq = ttk.LabelFrame(tab, text="Parchment print queue", padding=6)
        pq.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        controls = ttk.Frame(pq)
        controls.pack(fill=tk.X, pady=(0, 6))
        for label, status in [('Mark printing', 'printing'),
                              ('Mark printed', 'printed'),
                              ('Mark dispatched', 'dispatched'),
                              ('Mark failed', 'failed')]:
            ttk.Button(controls, text=label,
                       command=lambda s=status: self._on_set_print_status(s)).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="↻ Reload",
                   command=self._reload_print_queue).pack(side=tk.RIGHT)

        cols = ("qid", "sid", "name", "cert_no", "status",
                "printed_at", "dispatched_at", "notes")
        self.print_tree = ttk.Treeview(pq, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (50, 80, 180, 180, 90, 130, 130, 240)):
            self.print_tree.heading(c, text=c.title())
            self.print_tree.column(c, width=w, anchor="w")
        self.print_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scr = ttk.Scrollbar(pq, orient=tk.VERTICAL, command=self.print_tree.yview)
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        self.print_tree.configure(yscrollcommand=scr.set)

        # Employer transcript token issuer.
        token = ttk.LabelFrame(tab, text="Issue employer transcript link", padding=10)
        token.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(token, text="Student ID:").grid(row=0, column=0, sticky="e", padx=6, pady=4)
        self.tok_sid = ttk.Entry(token, width=14)
        self.tok_sid.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(token, text="Employer name:").grid(row=0, column=2, sticky="e", padx=6)
        self.tok_emp_name = ttk.Entry(token, width=24)
        self.tok_emp_name.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(token, text="Employer email:").grid(row=0, column=4, sticky="e", padx=6)
        self.tok_emp_email = ttk.Entry(token, width=28)
        self.tok_emp_email.grid(row=0, column=5, sticky="w", padx=6)

        ttk.Label(token, text="Purpose:").grid(row=1, column=0, sticky="e", padx=6)
        self.tok_purpose = ttk.Entry(token, width=40)
        self.tok_purpose.insert(0, "Employment verification")
        self.tok_purpose.grid(row=1, column=1, columnspan=3, sticky="we", padx=6)

        ttk.Label(token, text="TTL (days):").grid(row=1, column=4, sticky="e", padx=6)
        self.tok_ttl = ttk.Spinbox(token, from_=1, to=365, width=6)
        self.tok_ttl.set(30)
        self.tok_ttl.grid(row=1, column=5, sticky="w", padx=6)

        ttk.Button(token, text="🔗 Issue transcript token",
                   command=self._on_issue_token).grid(
                       row=2, column=0, columnspan=3, sticky="w", padx=6, pady=(6, 0))

        self.tok_result = ttk.Label(token, text="", foreground="#005c1f")
        self.tok_result.grid(row=2, column=3, columnspan=3, sticky="w", padx=6, pady=(6, 0))

    def _reload_print_queue(self):
        for iid in self.print_tree.get_children():
            self.print_tree.delete(iid)
        if self.current_ceremony_id is None:
            return
        for r in PrintQueueManager.list_queue(self.current_ceremony_id):
            self.print_tree.insert("", tk.END, values=(
                r['queue_id'], r['student_id'], r.get('student_name', ''),
                r.get('certificate_number', ''), r['status'],
                r.get('printed_at') or '', r.get('dispatched_at') or '',
                r.get('notes', '') or '',
            ))

    def _on_set_print_status(self, status: str):
        sel = self.print_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a print-queue row first.")
            return
        qid = int(self.print_tree.item(sel[0])['values'][0])
        try:
            PrintQueueManager.set_status(qid, status)
            self._reload_print_queue()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _open_alumni_system(self):
        """Launch the Alumni Management GUI in a new window."""
        try:
            from education_system.post_18.university_system.modules.domain.student_affairs.gui.alumni.main_gui import (
                AlumniGUIApp,
            )
            AlumniGUIApp(tk.Toplevel(self.window), auth=self.auth)
        except Exception as e:
            messagebox.showerror(
                "Alumni System",
                f"Could not open the Alumni Management system:\n{e}")

    def _on_issue_package(self):
        if self.current_ceremony_id is None:
            messagebox.showwarning("Ceremony", "Select a ceremony first.")
            return
        sid = self.rec_sid.get().strip()
        if not sid:
            messagebox.showwarning("Student", "Enter a student ID.")
            return
        course = self.rec_course.get().strip()
        classification = self.rec_class.get().strip()
        try:
            grad_year = int(self.rec_grad_year.get().strip() or datetime.now().year)
        except ValueError:
            messagebox.showwarning("Year", "Graduation year must be a number.")
            return
        try:
            result = issue_conferral_package(
                ceremony_id=self.current_ceremony_id,
                student_id=sid,
                course_name=course,
                classification=classification if classification != '(no classification)' else '',
                graduation_year=grad_year,
                academic_year=self.rec_year.get().strip() or None,
                frozen_by=(self.auth.current_user.get('username')
                           if self.auth and getattr(self.auth, 'current_user', None) else 'system'),
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self._reload_print_queue()
        lines = []
        if result.get('print_queue'):
            lines.append(f"Parchment queued: cert {result['print_queue'].get('certificate_number')}")
        if result.get('diploma'):
            lines.append(f"Digital diploma: hash {result['diploma']['blockchain_hash'][:16]}…")
        if result.get('freeze'):
            lines.append(f"Transcript frozen: ref FRZ-{result['freeze'].get('freeze_id')}")
        if result.get('alumni'):
            alum = result['alumni']
            lines.append(f"Alumni record: provisioned (alumni_id={alum.get('alumni_id')})")
            if alum.get('student_moved'):
                lines.append("  → student record moved to alumni (status: Graduated)")
        if result.get('errors'):
            lines.append("")
            lines.append("Errors:")
            lines.extend(f"  • {e}" for e in result['errors'])
        messagebox.showinfo("Conferral package", "\n".join(lines) or "Done.")

    def _on_issue_token(self):
        sid = self.tok_sid.get().strip()
        emp_email = self.tok_emp_email.get().strip()
        if not sid or not emp_email:
            messagebox.showwarning("Token", "Student ID and employer email are required.")
            return
        freeze = TranscriptFreezeManager.get_latest_for_student(sid)
        if not freeze:
            messagebox.showwarning(
                "No frozen transcript",
                f"No transcript freeze on file for {sid}. "
                "Issue the conferral package first."
            )
            return
        try:
            ttl = int(self.tok_ttl.get())
        except ValueError:
            ttl = 30
        try:
            res = TranscriptFreezeManager.issue_employer_token(
                freeze_id=freeze['freeze_id'],
                employer_email=emp_email,
                employer_name=self.tok_emp_name.get().strip(),
                requested_by=(self.auth.current_user.get('username')
                              if self.auth and getattr(self.auth, 'current_user', None) else ''),
                purpose=self.tok_purpose.get().strip() or 'Employment verification',
                ttl_days=ttl,
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self.tok_result.config(
            text=f"Token issued — expires {res['expires_at']}. URL: {res['verification_url']}"
        )


def launch_graduation_ceremony_gui(root, auth):
    """Module-level launcher used by main_gui wiring."""
    return GraduationCeremonyGUI(root, auth=auth)


__all__ = ['GraduationCeremonyGUI', 'launch_graduation_ceremony_gui']
