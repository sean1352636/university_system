"""Graduation Ceremony Management CLI.

Operational, staff-facing command line for running a graduation ceremony end
to end — the CLI counterpart of ``graduation_ceremony_gui.GraduationCeremonyGUI``.
It drives the same service layer (``CeremonyManager``, ``RsvpManager``,
``GownOrderManager``, ``SeatPlanManager``, ``StageScriptManager`` and the
records managers), so anything achievable through the GUI is achievable here.

Capabilities:

* Ceremonies   — list, create, edit, capacity summary, cancel/reopen, and
                 *complete* (which closes the ceremony AND emails every
                 attending graduand a congratulations / next-steps message).
* RSVPs        — list and record/update graduand attendance + guests.
* Gowns        — list, create/update orders, take payment, advance status.
* Seating      — auto-assign, view, clear and export the seat plan (CSV).
* Stage script — preview, export, and export the name-pronunciation CSV.
* Records      — issue the conferral package (parchment + diploma + transcript
                 freeze + alumni provisioning), manage the print queue, and
                 issue employer transcript-verification tokens.

Staff / admin / instructor / registrar only — students use the GUI's
self-service "My Graduation" tab instead.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from education_system.systems.university.domain.academics.services.degree_audit.graduation_ceremony import (
    CeremonyManager,
    GownOrderManager,
    RsvpManager,
    SeatPlanManager,
    StageScriptManager,
)
from education_system.systems.university.domain.academics.services.degree_audit.graduation_records import (
    PrintQueueManager,
    TranscriptFreezeManager,
    issue_conferral_package,
)

try:
    from education_system.systems.university.domain.academics.services.degree_audit.db_schema import (
        initialize_degree_audit_database,
    )
    _SCHEMA_AVAILABLE = True
except Exception:  # pragma: no cover - schema module optional at import time
    initialize_degree_audit_database = None
    _SCHEMA_AVAILABLE = False


_MANAGER_ROLES = {'admin', 'staff', 'instructor', 'registrar'}
_RSVP_STATUSES = ('going', 'not_going', 'interested', 'pending')


class GraduationCeremonyCLI:
    """Interactive, menu-driven graduation ceremony management."""

    def __init__(self, auth=None):
        self.auth = auth
        self.current_user = getattr(auth, 'current_user', None) if auth else None
        # Selected ceremony carried across menu actions so the operator doesn't
        # re-pick it for every step. ``None`` until the first selection.
        self.current_ceremony_id: Optional[int] = None

        if _SCHEMA_AVAILABLE:
            try:
                initialize_degree_audit_database()
            except Exception as e:  # pragma: no cover - best-effort init
                print(f"Warning: database initialisation failed: {e}")

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _role(user) -> str:
        if not user:
            return ''
        if isinstance(user, dict):
            return str(user.get('role') or '').lower()
        return str(getattr(user, 'role', '') or '').lower()

    def _actor(self) -> str:
        """Username/identifier used for audit fields (processed_by etc.)."""
        u = self.current_user
        if isinstance(u, dict):
            return str(u.get('username') or u.get('email') or 'cli_user')
        return str(getattr(u, 'username', None) or 'cli_user')

    @staticmethod
    def clear_screen():
        print("\033[2J\033[H", end="", flush=True)

    @staticmethod
    def print_header(title):
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)

    @staticmethod
    def print_section(title):
        print(f"\n{'─' * 70}")
        print(f"  {title}")
        print(f"{'─' * 70}")

    @staticmethod
    def pause():
        input("\nPress Enter to continue...")

    # ----- input helpers ------------------------------------------------
    @staticmethod
    def _prompt(text, default: str = "") -> str:
        suffix = f" [{default}]" if default else ""
        val = input(f"{text}{suffix}: ").strip()
        return val or default

    @staticmethod
    def _prompt_int(text, *, default: Optional[int] = None,
                    allow_blank: bool = False, minimum: Optional[int] = None) -> Optional[int]:
        suffix = f" [{default}]" if default is not None else ""
        while True:
            raw = input(f"{text}{suffix}: ").strip()
            if not raw:
                if default is not None:
                    return default
                if allow_blank:
                    return None
                print("  Please enter a number.")
                continue
            try:
                n = int(raw)
            except ValueError:
                print("  Enter a valid whole number.")
                continue
            if minimum is not None and n < minimum:
                print(f"  Must be at least {minimum}.")
                continue
            return n

    @staticmethod
    def _confirm(text) -> bool:
        return input(f"{text} (y/n): ").strip().lower() in ('y', 'yes')

    def _prompt_choice(self, text, choices, *, default: str = "") -> str:
        """Prompt for one of ``choices`` (case-insensitive); reprompt on miss."""
        joined = "/".join(choices)
        while True:
            val = self._prompt(f"{text} ({joined})", default).strip().lower()
            if val in choices:
                return val
            print(f"  Choose one of: {joined}")

    # ----- ceremony selection ------------------------------------------
    def _pick_ceremony(self, *, allow_current: bool = True) -> Optional[int]:
        """List ceremonies and return a chosen id (or the current selection)."""
        ceremonies = CeremonyManager.list_ceremonies()
        if not ceremonies:
            print("\nNo ceremonies exist yet — create one first (option 2).")
            return None

        print("\nCeremonies:")
        for c in ceremonies:
            marker = "→" if (allow_current and c['ceremony_id'] == self.current_ceremony_id) else " "
            print(f"  {marker} [{c['ceremony_id']}] {c['ceremony_name']} — "
                  f"{c['ceremony_date']} {c.get('ceremony_time', '')} "
                  f"@ {c.get('venue', '—')}  ({c.get('status', 'scheduled')})")

        if allow_current and self.current_ceremony_id is not None:
            raw = input("\nCeremony id (blank = keep current selection, 0 = cancel): ").strip()
            if not raw:
                return self.current_ceremony_id
        else:
            raw = input("\nCeremony id (0 = cancel): ").strip()
        if raw == '0' or not raw:
            return None
        try:
            cid = int(raw)
        except ValueError:
            print("  Invalid id.")
            return None
        if not CeremonyManager.get_ceremony(cid):
            print(f"  No ceremony with id {cid}.")
            return None
        self.current_ceremony_id = cid
        return cid

    def _require_ceremony(self) -> Optional[int]:
        if self.current_ceremony_id is not None:
            return self.current_ceremony_id
        return self._pick_ceremony()

    @staticmethod
    def _write_file(path: str, content: str) -> bool:
        try:
            with open(os.path.expanduser(path), 'w', encoding='utf-8') as fh:
                fh.write(content)
            return True
        except OSError as e:
            print(f"  Could not write file: {e}")
            return False

    # ================================================================ menu
    def run(self):
        role = self._role(self.current_user)
        if role and role not in _MANAGER_ROLES:
            print("\nYou don't have permission to manage graduation ceremonies.")
            print("Students can use the GUI's 'My Graduation' self-service tab.")
            return

        while True:
            self.clear_screen()
            self.print_header("🎓 GRADUATION CEREMONY MANAGEMENT")
            sel = CeremonyManager.get_ceremony(self.current_ceremony_id) if self.current_ceremony_id else None
            if sel:
                print(f"\n  Selected: [{sel['ceremony_id']}] {sel['ceremony_name']} "
                      f"({sel.get('status', 'scheduled')})")
            else:
                print("\n  Selected: (none — most actions will prompt you to pick one)")

            print("\n📅 CEREMONIES:")
            print("  1. List / select ceremony")
            print("  2. Create ceremony")
            print("  3. Edit ceremony details")
            print("  4. Capacity summary")
            print("  5. Cancel / reopen ceremony")
            print("  6. ✅ Complete ceremony  (emails attending graduands)")

            print("\n🎟️  RSVPS:")
            print("  7. List RSVPs")
            print("  8. Record / update an RSVP")

            print("\n🥼 GOWNS:")
            print("  9. List gown orders")
            print(" 10. Create / update a gown order")
            print(" 11. Take gown payment")
            print(" 12. Update gown order status")

            print("\n🪑 SEATING & STAGE SCRIPT:")
            print(" 13. Auto-assign seats")
            print(" 14. View seat plan")
            print(" 15. Clear seat plan")
            print(" 16. Export seat plan (CSV)")
            print(" 17. Preview stage script")
            print(" 18. Export stage script (text)")
            print(" 19. Export name-pronunciation list (CSV)")

            print("\n📜 RECORDS & CONFERRAL:")
            print(" 20. Issue conferral package")
            print(" 21. View print queue")
            print(" 22. Update print-queue status")
            print(" 23. Issue employer verification token")

            print("\n  0. Exit")

            choice = input("\n👉 Enter your choice: ").strip()
            actions = {
                '1': self.list_ceremonies,
                '2': self.create_ceremony,
                '3': self.edit_ceremony,
                '4': self.capacity_summary,
                '5': self.set_status,
                '6': self.complete_ceremony,
                '7': self.list_rsvps,
                '8': self.record_rsvp,
                '9': self.list_gowns,
                '10': self.create_gown,
                '11': self.take_gown_payment,
                '12': self.update_gown_status,
                '13': self.auto_assign_seats,
                '14': self.view_seat_plan,
                '15': self.clear_seat_plan,
                '16': self.export_seat_plan,
                '17': self.preview_script,
                '18': self.export_script,
                '19': self.export_pronunciation,
                '20': self.issue_package,
                '21': self.view_print_queue,
                '22': self.update_print_status,
                '23': self.issue_employer_token,
            }
            if choice == '0':
                print("\n👋 Goodbye!")
                return
            handler = actions.get(choice)
            if not handler:
                print("\n❌ Invalid choice.")
                self.pause()
                continue
            try:
                handler()
            except Exception as e:  # pragma: no cover - defensive UX guard
                print(f"\n❌ Error: {e}")
            self.pause()

    # ============================================================ ceremonies
    def list_ceremonies(self):
        self.print_section("Ceremonies")
        cid = self._pick_ceremony()
        if cid:
            print(f"\nSelected ceremony {cid}.")

    def create_ceremony(self):
        self.print_section("Create a ceremony")
        name = self._prompt("Ceremony name")
        if not name:
            print("  Name is required — cancelled.")
            return
        date = self._prompt("Date (YYYY-MM-DD)")
        time = self._prompt("Time (e.g. 14:00)")
        venue = self._prompt("Venue")
        capacity = self._prompt_int("Capacity (total seats)", minimum=1) or 0
        cohort = self._prompt("Cohort filter (optional)")
        deadline = self._prompt("RSVP deadline (YYYY-MM-DD, optional)")
        guests = self._prompt_int("Guest tickets per graduand", default=2, minimum=0)
        notes = self._prompt("Notes (optional)")

        cid = CeremonyManager.create_ceremony(
            ceremony_name=name, ceremony_date=date, ceremony_time=time,
            venue=venue, capacity=capacity, cohort_filter=cohort,
            rsvp_deadline=deadline, guest_tickets_per_graduand=guests, notes=notes,
        )
        self.current_ceremony_id = cid
        print(f"\n✓ Created ceremony {cid} and selected it.")

    def edit_ceremony(self):
        self.print_section("Edit ceremony details")
        cid = self._require_ceremony()
        if not cid:
            return
        c = CeremonyManager.get_ceremony(cid)
        print("\nLeave a field blank to keep its current value.\n")
        fields = {}
        for key, label in (
            ('ceremony_name', 'Name'),
            ('ceremony_date', 'Date (YYYY-MM-DD)'),
            ('ceremony_time', 'Time'),
            ('venue', 'Venue'),
            ('cohort_filter', 'Cohort filter'),
            ('rsvp_deadline', 'RSVP deadline'),
            ('notes', 'Notes'),
        ):
            new = self._prompt(label, str(c.get(key) or ''))
            if new != str(c.get(key) or ''):
                fields[key] = new
        cap = self._prompt_int("Capacity", default=int(c.get('capacity') or 0), minimum=0)
        if cap != int(c.get('capacity') or 0):
            fields['capacity'] = cap
        guests = self._prompt_int("Guest tickets per graduand",
                                  default=int(c.get('guest_tickets_per_graduand') or 0), minimum=0)
        if guests != int(c.get('guest_tickets_per_graduand') or 0):
            fields['guest_tickets_per_graduand'] = guests

        if not fields:
            print("\nNothing changed.")
            return
        ok = CeremonyManager.update_ceremony(cid, **fields)
        print(f"\n{'✓ Updated.' if ok else 'No changes saved.'} ({len(fields)} field(s))")

    def capacity_summary(self):
        self.print_section("Capacity summary")
        cid = self._require_ceremony()
        if not cid:
            return
        cap = CeremonyManager.capacity_summary(cid)
        print(f"\n  Capacity:  {cap['capacity']}")
        print(f"  Graduands: {cap['graduands']}")
        print(f"  Guests:    {cap['guests']}")
        print(f"  Total:     {cap['total']}")
        print(f"  Free:      {cap['free']}")

    def set_status(self):
        self.print_section("Cancel / reopen ceremony")
        cid = self._require_ceremony()
        if not cid:
            return
        c = CeremonyManager.get_ceremony(cid)
        print(f"\nCurrent status: {c.get('status', 'scheduled')}")
        print("(Use option 6 to complete a ceremony — that one also emails graduands.)")
        status = self._prompt_choice("New status",
                                     ('scheduled', 'cancelled'), default='scheduled')
        if not self._confirm(f"Set ceremony {cid} status to '{status}'?"):
            return
        ok = CeremonyManager.update_ceremony(cid, status=status)
        print(f"\n{'✓ Status updated.' if ok else 'No change made.'}")

    def complete_ceremony(self):
        self.print_section("Complete ceremony")
        cid = self._require_ceremony()
        if not cid:
            return
        c = CeremonyManager.get_ceremony(cid)
        if (c.get('status') or '').lower() == 'completed':
            print("\nThis ceremony is already completed — no emails will be re-sent.")
            if not self._confirm("Run completion again anyway (no-op)?"):
                return
        going = RsvpManager.list_rsvps(cid, status='going')
        with_email = [r for r in going if (r.get('email') or '').strip()]
        print(f"\n{len(going)} graduand(s) RSVP'd 'going'; "
              f"{len(with_email)} have an email on file.")
        if not self._confirm(f"Mark ceremony {cid} completed and email those graduands?"):
            return
        sent, total = CeremonyManager.complete_ceremony(cid)
        print("\n✓ Ceremony marked completed.")
        print(f"  Congratulations emails sent to {sent} of {total} graduand(s).")

    # ================================================================ RSVPs
    def list_rsvps(self):
        self.print_section("RSVPs")
        cid = self._require_ceremony()
        if not cid:
            return
        flt = self._prompt("Filter by status (blank = all)")
        rsvps = RsvpManager.list_rsvps(cid, status=flt or None)
        if not rsvps:
            print("\nNo RSVPs match.")
            return
        print(f"\n{'Student ID':<14}{'Name':<26}{'Status':<12}{'Guests':<7}Course")
        print("  " + "-" * 76)
        for r in rsvps:
            print(f"  {str(r['student_id']):<12}{(r.get('student_name') or '')[:24]:<26}"
                  f"{r.get('rsvp_status', ''):<12}{r.get('num_guests', 0):<7}"
                  f"{(r.get('course') or '')[:24]}")
        print(f"\n  {len(rsvps)} RSVP(s).")

    def record_rsvp(self):
        self.print_section("Record / update an RSVP")
        cid = self._require_ceremony()
        if not cid:
            return
        sid = self._prompt("Student ID")
        if not sid:
            print("  Student ID required — cancelled.")
            return
        status = self._prompt_choice("RSVP status", _RSVP_STATUSES, default='going')
        guests = self._prompt_int("Number of guests", default=0, minimum=0)
        access = self._prompt("Accessibility notes (optional)")
        pron = self._prompt("Name pronunciation (optional)")
        try:
            rsvp_id = RsvpManager.record_rsvp(
                ceremony_id=cid, student_id=sid, rsvp_status=status,
                num_guests=guests, accessibility_notes=access,
                name_pronunciation=pron,
            )
        except ValueError as e:
            print(f"\n❌ {e}")
            return
        print(f"\n✓ RSVP saved (id {rsvp_id}). A confirmation email was sent if "
              f"the student has an address on file.")

    # ================================================================ gowns
    def list_gowns(self):
        self.print_section("Gown orders")
        cid = self._require_ceremony()
        if not cid:
            return
        orders = GownOrderManager.list_orders(cid)
        if not orders:
            print("\nNo gown orders for this ceremony.")
            return
        print(f"\n{'Order':<7}{'Student':<22}{'Gown':<6}{'Hat':<6}{'Cost':<9}{'Pay':<9}Status")
        print("  " + "-" * 76)
        for o in orders:
            print(f"  {str(o['order_id']):<5}{(o.get('student_name') or o['student_id'])[:20]:<22}"
                  f"{(o.get('gown_size') or '—'):<6}{(o.get('hat_size') or '—'):<6}"
                  f"£{float(o.get('cost') or 0):<8.2f}"
                  f"{(o.get('payment_status') or 'unpaid'):<9}{o.get('status', 'ordered')}")
        print(f"\n  {len(orders)} order(s).")

    def create_gown(self):
        self.print_section("Create / update a gown order")
        cid = self._require_ceremony()
        if not cid:
            return
        sid = self._prompt("Student ID")
        if not sid:
            print("  Student ID required — cancelled.")
            return
        print(f"\n  Gown sizes: {', '.join(GownOrderManager.GOWN_SIZES)}")
        gown = self._prompt("Gown size (blank = none)")
        hood = self._prompt("Hood subject (blank = none)")
        print(f"  Hat sizes: {', '.join(GownOrderManager.HAT_SIZES)}")
        hat = self._prompt("Hat size (blank = none)")
        supplier = self._prompt("Supplier (optional)")
        slot = self._prompt("Collection slot (optional)")

        quote = GownOrderManager.quote(gown, hood, hat)
        print(f"\n  Quote for this order: £{quote:.2f}")
        if not self._confirm("Save this order?"):
            return
        order_id = GownOrderManager.create_order(
            ceremony_id=cid, student_id=sid, gown_size=gown, hood_subject=hood,
            hat_size=hat, supplier=supplier, collection_slot=slot,
        )
        print(f"\n✓ Gown order saved (id {order_id}, £{quote:.2f}).")

    def take_gown_payment(self):
        self.print_section("Take gown payment")
        cid = self._require_ceremony()
        if not cid:
            return
        unpaid = [o for o in GownOrderManager.list_orders(cid)
                  if (o.get('payment_status') or 'unpaid') != 'paid']
        if not unpaid:
            print("\nNo unpaid gown orders for this ceremony.")
            return
        print("\nUnpaid orders:")
        for o in unpaid:
            print(f"  [{o['order_id']}] {o.get('student_name') or o['student_id']} "
                  f"— £{float(o.get('cost') or 0):.2f}")
        order_id = self._prompt_int("Order id to pay", allow_blank=True)
        if order_id is None:
            return
        print(f"\n  Methods: {', '.join(GownOrderManager.PAYMENT_METHODS)}")
        method = self._prompt_choice("Payment method", GownOrderManager.PAYMENT_METHODS,
                                     default='card')
        try:
            result = GownOrderManager.process_payment(
                order_id, method, processed_by=self._actor())
        except ValueError as e:
            print(f"\n❌ {e}")
            return
        print(f"\n✓ Payment taken: £{result['amount']:.2f} via {result['payment_method']} "
              f"(ref {result['reference']}).")
        if result.get('balance_remaining') is not None:
            print(f"  Finance-account balance remaining: £{result['balance_remaining']:.2f}")
        print("  A receipt has been emailed to the student.")

    def update_gown_status(self):
        self.print_section("Update gown order status")
        cid = self._require_ceremony()
        if not cid:
            return
        orders = GownOrderManager.list_orders(cid)
        if not orders:
            print("\nNo gown orders for this ceremony.")
            return
        for o in orders:
            print(f"  [{o['order_id']}] {o.get('student_name') or o['student_id']} "
                  f"— status {o.get('status', 'ordered')}")
        order_id = self._prompt_int("Order id", allow_blank=True)
        if order_id is None:
            return
        statuses = ('ordered', 'arrived', 'collected', 'returned', 'cancelled')
        status = self._prompt_choice("New status", statuses, default='arrived')
        try:
            ok = GownOrderManager.update_status(order_id, status)
        except ValueError as e:
            print(f"\n❌ {e}")
            return
        print(f"\n{'✓ Status updated.' if ok else 'Order not found.'}")

    # ============================================================== seating
    def auto_assign_seats(self):
        self.print_section("Auto-assign seats")
        cid = self._require_ceremony()
        if not cid:
            return
        per_row = self._prompt_int("Seats per row",
                                   default=SeatPlanManager.DEFAULT_SEATS_PER_ROW, minimum=1)
        acc_rows = self._prompt_int("Accessibility rows", default=1, minimum=0)
        print("\nThis wipes and regenerates the seat plan for 'going' graduands.")
        if not self._confirm("Continue?"):
            return
        n = SeatPlanManager.auto_assign(cid, seats_per_row=per_row,
                                        accessibility_rows=acc_rows)
        print(f"\n✓ Assigned {n} seat(s).")

    def view_seat_plan(self):
        self.print_section("Seat plan")
        cid = self._require_ceremony()
        if not cid:
            return
        plan = SeatPlanManager.list_plan(cid)
        if not plan:
            print("\nNo seats assigned yet — run auto-assign first.")
            return
        last_section = None
        for r in plan:
            if r.get('section') != last_section:
                print(f"\n  — {r.get('section', 'MAIN')} block —")
                last_section = r.get('section')
            acc = "  ♿" if r.get('is_accessibility') else ""
            print(f"    {r.get('row_label')}-{r.get('seat_number'):<3} "
                  f"{(r.get('student_name') or r.get('student_id'))[:30]}{acc}")
        print(f"\n  {len(plan)} seat(s).")

    def clear_seat_plan(self):
        self.print_section("Clear seat plan")
        cid = self._require_ceremony()
        if not cid:
            return
        if not self._confirm(f"Delete ALL seat assignments for ceremony {cid}?"):
            return
        n = SeatPlanManager.clear_assignments(cid)
        print(f"\n✓ Cleared {n} assignment(s).")

    def export_seat_plan(self):
        self.print_section("Export seat plan (CSV)")
        cid = self._require_ceremony()
        if not cid:
            return
        csv_text = SeatPlanManager.export_csv(cid)
        path = self._prompt("Output file", f"seat_plan_{cid}.csv")
        if self._write_file(path, csv_text):
            print(f"\n✓ Wrote seat plan to {path}")

    def preview_script(self):
        self.print_section("Stage script preview")
        cid = self._require_ceremony()
        if not cid:
            return
        incl = self._confirm("Include name pronunciation?")
        try:
            script = StageScriptManager.build_script(cid, include_pronunciation=incl)
        except ValueError as e:
            print(f"\n❌ {e}")
            return
        print("\n" + script)

    def export_script(self):
        self.print_section("Export stage script")
        cid = self._require_ceremony()
        if not cid:
            return
        incl = self._confirm("Include name pronunciation?")
        try:
            script = StageScriptManager.build_script(cid, include_pronunciation=incl)
        except ValueError as e:
            print(f"\n❌ {e}")
            return
        path = self._prompt("Output file", f"stage_script_{cid}.txt")
        if self._write_file(path, script):
            print(f"\n✓ Wrote stage script to {path}")

    def export_pronunciation(self):
        self.print_section("Export name-pronunciation list (CSV)")
        cid = self._require_ceremony()
        if not cid:
            return
        csv_text = StageScriptManager.export_name_pronunciation_csv(cid)
        path = self._prompt("Output file", f"pronunciation_{cid}.csv")
        if self._write_file(path, csv_text):
            print(f"\n✓ Wrote pronunciation list to {path}")

    # ============================================================== records
    def issue_package(self):
        self.print_section("Issue conferral package")
        cid = self._require_ceremony()
        if not cid:
            return
        sid = self._prompt("Student ID")
        if not sid:
            print("  Student ID required — cancelled.")
            return
        course = self._prompt("Course / award name (blank = use student record)")
        grade = self._prompt("Grade (optional)")
        classification = self._prompt("Classification (e.g. First, 2:1) (optional)")
        grad_year = self._prompt_int("Graduation year (optional)", allow_blank=True)
        academic_year = self._prompt("Academic year (e.g. 2025/26) (optional)")
        print("\nThis enqueues the parchment, issues a digital diploma, freezes the")
        print("transcript, and provisions the alumni account.")
        if not self._confirm("Proceed?"):
            return
        summary = issue_conferral_package(
            ceremony_id=cid, student_id=sid, course_name=course, grade=grade,
            classification=classification, graduation_year=grad_year,
            academic_year=academic_year or None, frozen_by=self._actor(),
        )
        print("\n  Conferral summary:")
        pq = summary.get('print_queue') or {}
        print(f"    Print queue:  {pq.get('certificate_number', '—') if pq else '—'}")
        print(f"    Diploma:      {'issued' if summary.get('diploma') else '—'}")
        print(f"    Transcript:   {'frozen' if summary.get('freeze') else '—'}")
        print(f"    Alumni:       {'provisioned' if summary.get('alumni') else '—'}")
        if summary.get('errors'):
            print("\n  ⚠ Some steps failed:")
            for err in summary['errors']:
                print(f"    - {err}")
        else:
            print("\n✓ All conferral steps completed.")

    def view_print_queue(self):
        self.print_section("Print queue")
        cid = self._require_ceremony()
        if not cid:
            return
        flt = self._prompt(f"Filter by status {PrintQueueManager.QUEUE_STATUSES} (blank = all)")
        rows = PrintQueueManager.list_queue(cid, status=flt or None)
        if not rows:
            print("\nPrint queue is empty.")
            return
        print(f"\n{'Queue':<7}{'Student':<22}{'Certificate':<22}Status")
        print("  " + "-" * 70)
        for r in rows:
            print(f"  {str(r['queue_id']):<5}{(r.get('student_name') or r['student_id'])[:20]:<22}"
                  f"{(r.get('certificate_number') or '—'):<22}{r.get('status', '')}")
        print(f"\n  {len(rows)} item(s).")

    def update_print_status(self):
        self.print_section("Update print-queue status")
        cid = self._require_ceremony()
        if not cid:
            return
        rows = PrintQueueManager.list_queue(cid)
        if not rows:
            print("\nPrint queue is empty.")
            return
        for r in rows:
            print(f"  [{r['queue_id']}] {r.get('student_name') or r['student_id']} "
                  f"— {r.get('status', '')}")
        queue_id = self._prompt_int("Queue id", allow_blank=True)
        if queue_id is None:
            return
        status = self._prompt_choice("New status", PrintQueueManager.QUEUE_STATUSES,
                                     default='printed')
        notes = self._prompt("Notes (optional)")
        try:
            ok = PrintQueueManager.set_status(queue_id, status, notes=notes)
        except ValueError as e:
            print(f"\n❌ {e}")
            return
        print(f"\n{'✓ Status updated.' if ok else 'Queue item not found.'}")

    def issue_employer_token(self):
        self.print_section("Issue employer verification token")
        sid = self._prompt("Student ID")
        if not sid:
            print("  Student ID required — cancelled.")
            return
        freeze = TranscriptFreezeManager.get_latest_for_student(sid)
        if not freeze:
            print(f"\nNo frozen transcript for {sid}. Issue the conferral package "
                  f"(option 20) first.")
            return
        emp_email = self._prompt("Employer email")
        if not emp_email:
            print("  Employer email required — cancelled.")
            return
        emp_name = self._prompt("Employer / hiring team name (optional)")
        ttl = self._prompt_int("Token validity (days)", default=30, minimum=1)
        result = TranscriptFreezeManager.issue_employer_token(
            freeze['freeze_id'], employer_email=emp_email, employer_name=emp_name,
            requested_by=self._actor(), ttl_days=ttl,
        )
        print(f"\n✓ Token issued (expires {result['expires_at']}).")
        print(f"  Verification URL: {result['verification_url']}")
        print("  An email has been sent to the employer.")


def launch_graduation_ceremony_cli(auth=None):
    """Entry point: launch the Graduation Ceremony CLI.

    Args:
        auth: Authentication instance carrying the current user.
    """
    try:
        GraduationCeremonyCLI(auth).run()
    except KeyboardInterrupt:
        print("\n\n👋 Exited by user")
    except Exception as e:  # pragma: no cover - top-level safety net
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":  # pragma: no cover - standalone testing
    launch_graduation_ceremony_cli()
