"""
Graduation window.

Who sees what (the rules in ``university/application/graduation/`` check
again, so hiding a tab is a convenience, not the guard):

* the graduation office (admins, registrars, ``graduation_office``) — every
  tab: eligibility, ceremonies, graduands & invitations, RSVPs & guests,
  on the day, gown orders, seat plan, stage script, conferrals & records,
  holds & names;
* ceremony staff (``ceremony_staff``) — On the day only (check-in);
* students — My Graduation only;
* any other member of staff — a message, no tabs.

Window matches the project convention: 1400x900, minsize 1200x800.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

import importlib
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

from education_system.systems.university.domains.progression.domain.degree_audit.graduation_ceremony import (
    CeremonyManager, GownOrderManager, SeatPlanManager, StageScriptManager,
)
from education_system.systems.university.domains.progression.domain.degree_audit.db_schema import (
    initialize_degree_audit_database,
)
from education_system.systems.university.infrastructure.ui.field_pickers import attach_picker
from education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui.graduation_gui_ops import (
    GraduationOpsMixin,
)
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (
    common,
)

_PKG = "education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui"


class _Context:
    """What the separately-built tabs get: who, the window, auth, refresh."""

    def __init__(self, gui):
        self.who = gui.who
        self.root = gui.window
        self.auth = gui.auth
        self.refresh_all = gui._reload_ceremonies


class GraduationCeremonyGUI(GraduationOpsMixin):
    """Graduation: ceremonies, graduands, the day itself and the records."""

    # Display label -> service key for the payment-method selector.
    _PAY_METHOD_KEYS = {
        "Cash": "cash",
        "Card": "card",
        "Student Finance Account": "student_finance_account",
    }

    def __init__(self, parent, auth=None):
        self.auth = auth
        try:
            initialize_degree_audit_database()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        # Allow embedding in workspace Frame.
        if parent is not None and not hasattr(parent, "wm_title"):
            self.window = parent
            self._owned_window = False
        else:
            self.window = tk.Toplevel(parent) if parent is not None else tk.Tk()
            self.window.title(_t('gui.academics.course_management_gui.graduation_ceremony.windows.graduation_ceremony_management', default="Graduation Ceremony Management"))
            self.window.geometry("1400x900")
            self.window.minsize(1200, 800)
            self._owned_window = True

        self.current_ceremony_id: Optional[int] = None
        self._ceremonies: list = []
        self.who = self._resolve_who()
        self._ctx = _Context(self)
        self._build_ui()
        if self.who is not None and not self.who.is_student and self.who.has_access:
            self._reload_ceremonies()

    def _resolve_who(self):
        from education_system.systems.university.application.graduation import (
            access as graduation_access,
        )
        user = getattr(self.auth, "current_user", None) if self.auth else None
        if not user:
            try:
                from education_system.systems.university.infrastructure.shared_context import get_auth
                shared = get_auth()
                user = getattr(shared, "current_user", None) if shared else None
            except Exception:
                user = None
        if not user:
            return None
        return common.call(self.window, graduation_access.from_user, dict(user), write=True,
                           quiet=True)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        outer = ttk.Frame(self.window, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        top_bar = ttk.Frame(outer)
        top_bar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(top_bar, text=_t('gui.academics.course_management_gui.graduation_ceremony.buttons.close', default="✖ Close"), command=self._close).pack(
            side=tk.RIGHT, anchor="ne")
        ttk.Label(
            top_bar, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.graduation_ceremony_management', default="🎓 Graduation Ceremony Management"),
            font=("Arial", 16, "bold"),
        ).pack(side=tk.LEFT, anchor="w")

        who = self.who
        if who is None or not who.has_access:
            message = ("Sign in to use Graduation." if who is None else
                       "Graduation is run by the graduation office. Ask them (or an "
                       "administrator) for the graduation_office or ceremony_staff role "
                       "if you need it.")
            ttk.Label(outer, text=message, padding=40, font=("Arial", 12),
                      wraplength=700, justify="center").pack(expand=True)
            return

        self.notebook = ttk.Notebook(outer)
        if who.is_student:
            self.notebook.pack(fill=tk.BOTH, expand=True)
            self._add_external_tab("graduation_student_tab", "build_student_tab", "My Graduation")
            return

        # Ceremony picker (shared across all staff tabs).
        picker = ttk.LabelFrame(outer, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.active_ceremony', default="Active ceremony"), padding=8)
        picker.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(picker, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.ceremony', default="Ceremony:")).pack(side=tk.LEFT)
        self.ceremony_combo = ttk.Combobox(picker, width=70, state="readonly")
        self.ceremony_combo.pack(side=tk.LEFT, padx=8)
        self.ceremony_combo.bind("<<ComboboxSelected>>", self._on_ceremony_selected)
        self.capacity_label = ttk.Label(picker, text="", foreground="#444")
        self.capacity_label.pack(side=tk.LEFT, padx=20)
        ttk.Button(picker, text=_t('gui.academics.course_management_gui.graduation_ceremony.buttons.refresh', default="🔄 Refresh"), command=self._reload_ceremonies).pack(side=tk.RIGHT)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        if not who.is_office:          # ceremony staff: check-in only
            self._build_day_tab()
            return
        self._build_ceremonies_tab()
        self._build_graduands_tab()
        self._build_rsvp_tab()
        self._build_day_tab()
        self._build_gown_tab()
        self._build_seat_tab()
        self._build_script_tab()
        self._add_external_tab("graduation_records_tabs", "build_conferrals_tab",
                               "Conferrals & records")
        self._add_external_tab("graduation_records_tabs", "build_holds_tab",
                               "Holds & eligibility")

    def _add_external_tab(self, module, builder, label):
        """Tabs built in their own modules; a missing one shows a note."""
        try:
            build = getattr(importlib.import_module(f"{_PKG}.{module}"), builder)
            build(self.notebook, self._ctx)
        except Exception as exc:
            logger.exception("graduation tab %s.%s unavailable", module, builder)
            tab = ttk.Frame(self.notebook, padding=20)
            self.notebook.add(tab, text=label)
            ttk.Label(tab, text=f"This tab is unavailable: {exc}").pack(anchor="nw")

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
        if hasattr(self, 'cer_tree'):
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
        """Refresh whichever tabs this person has."""
        self._reload_graduands()
        self._reload_rsvp_table()
        self._reload_day()
        if hasattr(self, 'gown_tree'):
            self._reload_gown_table()
        if hasattr(self, 'seat_tree'):
            self._reload_seat_table()
        if hasattr(self, 'script_text'):
            self._refresh_script_preview()

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
            logger.debug("Suppressed exception", exc_info=True)

    def _update_capacity_label(self):
        if not hasattr(self, 'capacity_label'):
            return
        if self.current_ceremony_id is None:
            self.capacity_label.config(text="")
            return
        cap = CeremonyManager.capacity_summary(self.current_ceremony_id)
        self.capacity_label.config(
            text=(f"Capacity: {cap['total']}/{cap['capacity']} "
                  f"(graduands: {cap['graduands']}, guests: {cap['guests']}, "
                  f"free: {cap['free']})")
        )

    def _build_ceremonies_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text=_t('gui.academics.course_management_gui.graduation_ceremony.tabs.ceremonies', default="Ceremonies"))

        # Form
        form = ttk.LabelFrame(tab, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.schedule_edit_a_ceremony', default="Schedule / edit a ceremony"), padding=10)
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

        ttk.Label(form, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.venue', default="Venue:")).grid(row=0, column=2, sticky="e", padx=6, pady=4)
        venue_box = ttk.Frame(form)
        venue_box.grid(row=0, column=3, sticky="w", padx=6, pady=4)
        self._cer_venue = ttk.Combobox(venue_box, width=26, state="readonly")
        self._cer_venue.pack(side=tk.LEFT)
        ttk.Button(venue_box, text="🔄", width=3,
                   command=self._reload_venues).pack(side=tk.LEFT, padx=(4, 0))

        # Row 1: Date picker | Time steppers
        ttk.Label(form, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.date', default="Date:")).grid(row=1, column=0, sticky="e", padx=6, pady=4)
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

        ttk.Label(form, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.time', default="Time:")).grid(row=1, column=2, sticky="e", padx=6, pady=4)
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

        # Row 3: gown-order deadline (cohorts are set on the Graduands tab)
        _text_field("Gown order deadline (YYYY-MM-DD)", 3, 0, "", width=14)

        # Row 4: RSVP deadline picker (optional)
        ttk.Label(form, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.rsvp_deadline', default="RSVP deadline:")).grid(row=4, column=0, sticky="e", padx=6, pady=4)
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
        ttk.Button(deadline_box, text=_t('gui.academics.course_management_gui.graduation_ceremony.buttons.clear', default="✖ Clear"), command=self._clear_deadline).pack(
            side=tk.LEFT, padx=(4, 0))
        ttk.Label(deadline_box, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.leave_blank_for_none', default="(leave blank for none)"),
                  foreground="#888").pack(side=tk.LEFT, padx=(6, 0))

        self._reload_venues()

        btn_row = ttk.Frame(form)
        btn_row.grid(row=5, column=0, columnspan=4, pady=(8, 0), sticky="w")
        ttk.Button(btn_row, text=_t('gui.academics.course_management_gui.graduation_ceremony.buttons.create', default="➕ Create"),  command=self._on_create_ceremony).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text=_t('gui.academics.course_management_gui.graduation_ceremony.buttons.update_selected', default="💾 Update selected"), command=self._on_update_ceremony).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text=_t('gui.academics.course_management_gui.graduation_ceremony.buttons.cancel_selected', default="🗑️ Cancel selected"),
                   command=lambda: self._set_ceremony_status('cancelled')).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="✅ Complete ceremony…",
                   command=self._on_complete).pack(side=tk.LEFT, padx=4)

        # Table
        table_frame = ttk.LabelFrame(tab, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.all_ceremonies', default="All ceremonies"), padding=6)
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
            logger.debug("Suppressed exception", exc_info=True)

    def _set_date_widget(self, widget, value):
        """Set a date widget (tkcalendar DateEntry or plain Entry) from a string."""
        try:
            widget.delete(0, tk.END)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        if not value:
            return
        if _HAS_TKCALENDAR and isinstance(widget, DateEntry):
            try:
                widget.set_date(value)
                return
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
        try:
            widget.insert(0, value)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

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
                self._cer_entries["Gown order deadline (YYYY-MM-DD)"].delete(0, tk.END); self._cer_entries["Gown order deadline (YYYY-MM-DD)"].insert(0, c.get('gown_order_deadline') or '')
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
            'rsvp_deadline': self._cer_deadline.get().strip(),
            'guest_tickets_per_graduand': guests,
        }

    def _on_create_ceremony(self):
        try:
            p = self._form_ceremony_payload()
        except ValueError as ve:
            messagebox.showwarning(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.check_the_form', default="Check the form"), str(ve))
            return
        missing = [name for name, key in (
            ("Name", "ceremony_name"),
            ("Date", "ceremony_date"),
            ("Time", "ceremony_time"),
            ("Venue", "venue"),
        ) if not p.get(key)]
        if missing:
            messagebox.showwarning(
                _t('gui.academics.course_management_gui.graduation_ceremony.dialogs.check_the_form', default="Check the form"),
                "These fields are required:\n  • " + "\n  • ".join(missing),
            )
            return
        try:
            new_id = CeremonyManager.create_ceremony(**p)
            self.current_ceremony_id = new_id
            self._save_gown_deadline(new_id)
            self._reload_ceremonies()
            messagebox.showinfo(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.created', default="Created"), _t('gui.academics.course_management_gui.graduation_ceremony.dialogs.ceremony_scheduled', default="Ceremony scheduled."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.error', default="Error"), str(e))

    def _on_update_ceremony(self):
        if self.current_ceremony_id is None:
            messagebox.showwarning(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.select', default="Select"), _t('gui.academics.course_management_gui.graduation_ceremony.dialogs.select_a_ceremony_first', default="Select a ceremony first."))
            return
        try:
            p = self._form_ceremony_payload()
            CeremonyManager.update_ceremony(self.current_ceremony_id, **p)
            self._save_gown_deadline(self.current_ceremony_id)
            self._reload_ceremonies()
            messagebox.showinfo(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.updated', default="Updated"), _t('gui.academics.course_management_gui.graduation_ceremony.dialogs.ceremony_updated', default="Ceremony updated."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.error', default="Error"), str(e))

    def _save_gown_deadline(self, ceremony_id):
        from education_system.systems.university.application.graduation import (
            ceremonies as graduation_ceremonies,
        )
        value = self._cer_entries["Gown order deadline (YYYY-MM-DD)"].get().strip()
        common.call(self.window, graduation_ceremonies.set_gown_deadline, self.who, ceremony_id,
                    value or None, write=True)

    def _set_ceremony_status(self, status: str):
        if self.current_ceremony_id is None:
            return
        if not messagebox.askyesno(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.confirm', default="Confirm"), f"Set ceremony status to '{status}'?"):
            return

        CeremonyManager.update_ceremony(self.current_ceremony_id, status=status)
        self._reload_ceremonies()

    # =============================================================== Tab 3
    def _build_gown_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text=_t('gui.academics.course_management_gui.graduation_ceremony.tabs.gown_orders', default="Gown orders"))

        form = ttk.LabelFrame(tab, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.place_update_a_gown_order', default="Place / update a gown order"), padding=10)
        form.pack(fill=tk.X)

        ttk.Label(form, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.student_id', default="Student ID:")).grid(row=0, column=0, sticky="e", padx=6, pady=4)
        self.gown_sid = attach_picker(form, 'student', width=32)
        self.gown_sid.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.gown_size', default="Gown size:")).grid(row=0, column=2, sticky="e", padx=6)
        self.gown_size = ttk.Combobox(form, width=8, state="readonly",
                                      values=GownOrderManager.GOWN_SIZES)
        self.gown_size.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(form, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.hat_size', default="Hat size:")).grid(row=0, column=4, sticky="e", padx=6)
        self.hat_size = ttk.Combobox(form, width=6, state="readonly",
                                     values=GownOrderManager.HAT_SIZES)
        self.hat_size.grid(row=0, column=5, sticky="w", padx=6)

        ttk.Label(form, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.hood_subject', default="Hood subject:")).grid(row=1, column=0, sticky="e", padx=6)
        self.hood_subject = ttk.Entry(form, width=24)
        self.hood_subject.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.supplier', default="Supplier:")).grid(row=1, column=2, sticky="e", padx=6)
        self.gown_supplier = ttk.Entry(form, width=22)
        self.gown_supplier.grid(row=1, column=3, sticky="w", padx=6)

        ttk.Label(form, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.collection_slot', default="Collection slot:")).grid(row=1, column=4, sticky="e", padx=6)
        self.gown_slot = ttk.Entry(form, width=22)
        self.gown_slot.grid(row=1, column=5, sticky="w", padx=6)

        actions = ttk.Frame(form)
        actions.grid(row=2, column=0, columnspan=6, sticky="w", padx=6, pady=(8, 0))
        ttk.Button(actions, text=_t('gui.academics.course_management_gui.graduation_ceremony.buttons.save_order', default="💾 Save order"), command=self._on_save_gown).pack(side=tk.LEFT, padx=4)
        for st in ('arrived', 'collected', 'returned'):
            ttk.Button(actions, text=f"Mark {st}",
                       command=lambda s=st: self._on_set_gown_status(s)).pack(side=tk.LEFT, padx=4)

        pay = ttk.Frame(form)
        pay.grid(row=3, column=0, columnspan=6, sticky="w", padx=6, pady=(6, 0))
        ttk.Label(pay, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.take_payment_by', default="Take payment by:")).pack(side=tk.LEFT, padx=(0, 4))
        self.gown_pay_method = ttk.Combobox(
            pay, width=22, state="readonly",
            values=["Cash", "Card", "Student Finance Account"])
        self.gown_pay_method.set("Card")
        self.gown_pay_method.pack(side=tk.LEFT, padx=4)
        ttk.Button(pay, text=_t('gui.academics.course_management_gui.graduation_ceremony.buttons.take_payment_for_selected_order', default="💳 Take payment for selected order"),
                   command=self._on_take_gown_payment).pack(side=tk.LEFT, padx=8)
        ttk.Button(pay, text="✖ Cancel order…", command=self._on_cancel_gown).pack(
            side=tk.LEFT, padx=4)
        ttk.Button(pay, text="↩ Process refund", command=self._on_refund_gown).pack(
            side=tk.LEFT, padx=4)

        table = ttk.LabelFrame(tab, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.gown_orders_for_this_ceremony', default="Gown orders for this ceremony"), padding=6)
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
            messagebox.showwarning(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.ceremony', default="Ceremony"), _t('gui.academics.course_management_gui.graduation_ceremony.dialogs.select_a_ceremony_first', default="Select a ceremony first."))
            return
        sid = self.gown_sid.get().strip()
        if not sid:
            messagebox.showwarning(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.student', default="Student"), _t('gui.academics.course_management_gui.graduation_ceremony.dialogs.enter_a_student_id', default="Enter a student ID."))
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
            messagebox.showinfo(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.saved', default="Saved"), _t('gui.academics.course_management_gui.graduation_ceremony.dialogs.gown_order_saved', default="Gown order saved."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.error', default="Error"), str(e))

    def _on_set_gown_status(self, status: str):
        oid = getattr(self, '_selected_gown_order_id', None)
        if not oid:
            messagebox.showwarning(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.select', default="Select"), _t('gui.academics.course_management_gui.graduation_ceremony.dialogs.select_an_order_in_the_table_first', default="Select an order in the table first."))
            return
        try:
            GownOrderManager.update_status(oid, status)
            self._reload_gown_table()
        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.error', default="Error"), str(e))

    def _on_take_gown_payment(self):
        oid = getattr(self, '_selected_gown_order_id', None)
        if not oid:
            messagebox.showwarning(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.select', default="Select"), _t('gui.academics.course_management_gui.graduation_ceremony.dialogs.select_an_order_in_the_table_first', default="Select an order in the table first."))
            return
        method = self._PAY_METHOD_KEYS.get(self.gown_pay_method.get())
        if not method:
            messagebox.showwarning(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.payment', default="Payment"), _t('gui.academics.course_management_gui.graduation_ceremony.dialogs.choose_a_payment_method', default="Choose a payment method."))
            return
        processed_by = (self.auth.current_user.get('username')
                        if self.auth and getattr(self.auth, 'current_user', None)
                        else 'staff')
        try:
            result = GownOrderManager.process_payment(
                order_id=oid, payment_method=method, processed_by=processed_by)
        except ValueError as ve:
            messagebox.showwarning(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.payment', default="Payment"), str(ve))
            return
        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.error', default="Error"), str(e))
            return
        self._reload_gown_table()
        msg = (f"Payment of £{result['amount']:.2f} recorded "
               f"({self.gown_pay_method.get()}).\nReference: {result['reference']}\n"
               "A receipt has been emailed to the student.")
        if result.get('balance_remaining') is not None:
            msg += (f"\nFinance account balance remaining: "
                    f"£{result['balance_remaining']:.2f}")
        messagebox.showinfo(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.payment_recorded', default="Payment recorded"), msg)

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
        self.notebook.add(tab, text=_t('gui.academics.course_management_gui.graduation_ceremony.tabs.seat_plan', default="Seat plan"))

        controls = ttk.LabelFrame(tab, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.generator', default="Generator"), padding=10)
        controls.pack(fill=tk.X)

        ttk.Label(controls, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.seats_per_row', default="Seats per row:")).pack(side=tk.LEFT, padx=4)
        self.seats_per_row = ttk.Spinbox(controls, from_=4, to=30, width=5)
        self.seats_per_row.set(12)
        self.seats_per_row.pack(side=tk.LEFT, padx=4)

        ttk.Label(controls, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.accessibility_rows', default="Accessibility rows:")).pack(side=tk.LEFT, padx=8)
        self.access_rows = ttk.Spinbox(controls, from_=0, to=10, width=5)
        self.access_rows.set(1)
        self.access_rows.pack(side=tk.LEFT, padx=4)

        ttk.Button(controls, text=_t('gui.academics.course_management_gui.graduation_ceremony.buttons.auto_assign_seats', default="⚙️ Auto-assign seats"),
                   command=self._on_auto_assign).pack(side=tk.LEFT, padx=12)
        ttk.Button(controls, text=_t('gui.academics.course_management_gui.graduation_ceremony.buttons.clear_seat_plan', default="🧹 Clear seat plan"),
                   command=self._on_clear_seats).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text=_t('gui.academics.course_management_gui.graduation_ceremony.buttons.export_csv', default="⬇️ Export CSV"),
                   command=self._on_export_seats).pack(side=tk.LEFT, padx=4)

        table = ttk.LabelFrame(tab, text=_t('gui.academics.course_management_gui.graduation_ceremony.labels.seat_plan', default="Seat plan"), padding=6)
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
            messagebox.showwarning(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.ceremony', default="Ceremony"), _t('gui.academics.course_management_gui.graduation_ceremony.dialogs.select_a_ceremony_first', default="Select a ceremony first."))
            return
        try:
            spr = int(self.seats_per_row.get() or 12)
            acc = int(self.access_rows.get() or 1)
            count = SeatPlanManager.auto_assign(
                self.current_ceremony_id, seats_per_row=spr, accessibility_rows=acc,
            )
            self._reload_seat_table()
            self._refresh_script_preview()
            messagebox.showinfo(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.seat_plan', default="Seat plan"), f"Assigned {count} seat(s).")
        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.error', default="Error"), str(e))

    def _on_clear_seats(self):
        if self.current_ceremony_id is None:
            return
        if not messagebox.askyesno(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.confirm', default="Confirm"), _t('gui.academics.course_management_gui.graduation_ceremony.dialogs.wipe_the_seat_plan_for_this_ceremony', default="Wipe the seat plan for this ceremony?")):
            return
        SeatPlanManager.clear_assignments(self.current_ceremony_id)
        self._reload_seat_table()
        self._refresh_script_preview()

    def _on_export_seats(self):
        if self.current_ceremony_id is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.window,
            title=_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.save_seat_plan_csv', default="Save seat plan CSV"),
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
            initialfile=f"seat_plan_ceremony_{self.current_ceremony_id}.csv",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(SeatPlanManager.export_csv(self.current_ceremony_id))
            messagebox.showinfo(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.saved', default="Saved"), f"Seat plan exported:\n{path}")
        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.error', default="Error"), str(e))

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
        self.notebook.add(tab, text=_t('gui.academics.course_management_gui.graduation_ceremony.tabs.stage_script', default="Stage script"))

        controls = ttk.Frame(tab)
        controls.pack(fill=tk.X)
        self.include_pron = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text=_t('gui.academics.course_management_gui.graduation_ceremony.buttons.include_pronunciation_lines', default="Include pronunciation lines"),
                        variable=self.include_pron,
                        command=self._refresh_script_preview).pack(side=tk.LEFT)
        ttk.Button(controls, text=_t('gui.academics.course_management_gui.graduation_ceremony.buttons.refresh_preview', default="🔄 Refresh preview"),
                   command=self._refresh_script_preview).pack(side=tk.LEFT, padx=12)
        ttk.Button(controls, text=_t('gui.academics.course_management_gui.graduation_ceremony.buttons.export_script_txt', default="⬇️ Export script (.txt)"),
                   command=self._on_export_script).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text=_t('gui.academics.course_management_gui.graduation_ceremony.buttons.export_pronunciation_list_csv', default="⬇️ Export pronunciation list (CSV)"),
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
            messagebox.showinfo(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.saved', default="Saved"), f"Script exported:\n{path}")
        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.error', default="Error"), str(e))

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
            messagebox.showinfo(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.saved', default="Saved"), f"Pronunciation list exported:\n{path}")
        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.graduation_ceremony.dialogs.error', default="Error"), str(e))


def launch_graduation_ceremony_gui(root, auth):
    """Module-level launcher used by main_gui wiring."""
    return GraduationCeremonyGUI(root, auth=auth)


__all__ = ['GraduationCeremonyGUI', 'launch_graduation_ceremony_gui']
