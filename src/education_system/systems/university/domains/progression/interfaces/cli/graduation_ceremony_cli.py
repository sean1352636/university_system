"""Graduation CLI — the console counterpart of the Graduation window.

Who you are decides what you get (``university/application/graduation/access``):

* the graduation office (admins, registrars, ``graduation_office``) — every menu:
  ceremonies and cohorts, graduands / invitations / replies / extra tickets,
  the day itself (check-in, completion, which confers the awards), gowns
  (including cancellation and refund), seating and the stage script,
  conferrals and certificates (in absentia, review after a board reopens,
  revocation, replacements, print jobs, verification), eligibility, holds,
  certificate names, graduation roles and the audit log;
* ceremony staff — check-in only;
* students — My Graduation;
* anyone else, including an account with no role — refused.

The rules live in ``university/application/graduation/``; the menus are in
the sibling ``graduation`` package. Ceremony set-up, gown orders, seating
and the stage script still use the ceremony managers.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from education_system.systems.university.application.graduation import access as ga
from education_system.systems.university.domains.progression.domain.degree_audit.graduation_ceremony import (
    CeremonyManager,
    GownOrderManager,
    SeatPlanManager,
    StageScriptManager,
)
from education_system.systems.university.domains.progression.interfaces.cli.graduation import (
    office,
    records,
    student,
)
from education_system.systems.university.domains.progression.interfaces.cli.graduation._io import (
    menu,
    run as run_rule,
)

try:
    from education_system.systems.university.domains.progression.domain.degree_audit.db_schema import (
        initialize_degree_audit_database,
    )
    _SCHEMA_AVAILABLE = True
except Exception:  # pragma: no cover - schema module optional at import time
    initialize_degree_audit_database = None
    _SCHEMA_AVAILABLE = False




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
            print("\nNo ceremonies exist yet — create one first.")
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
    def require_ceremony(self) -> Optional[int]:
        return self._require_ceremony()

    def run(self):
        """Who you are decides what you get: the graduation office gets every
        menu, ceremony staff get check-in, students get My Graduation, and
        anyone else (including an account with no role) is refused."""
        self.who = run_rule(ga.from_user, self.current_user) if self.current_user else None
        if not self.who or not self.who.has_access:
            print("\nGraduation is run by the graduation office. You don't have access.")
            return
        if self.who.is_student:
            student.main(self)
            return
        if not self.who.is_office:
            menu("🎓 CEREMONY CHECK-IN", [
                ("Choose ceremony", self.list_ceremonies),
                ("Check graduands in", lambda: office.check_in(self)),
                ("Undo a check-in", lambda: office.undo_check_in(self)),
            ])
            return
        menu("🎓 GRADUATION", [
            ("Ceremonies", self._ceremony_menu),
            ("Graduands, invitations and replies", self._graduand_menu),
            ("On the day", self._day_menu),
            ("Gowns", self._gown_menu),
            ("Seating and stage script", self._seat_menu),
            ("Conferrals and certificates", self._records_menu),
            ("Eligibility, holds and certificate names", self._eligibility_menu),
            ("Graduation roles", lambda: records.roles(self)),
            ("Audit log", lambda: records.audit(self)),
        ])

    def _ceremony_menu(self):
        return menu("CEREMONIES", [
            ("List / select ceremony", self.list_ceremonies),
            ("Create ceremony", self.create_ceremony),
            ("Edit ceremony details", self.edit_ceremony),
            ("Who the ceremony is for (cohorts)", lambda: office.cohorts(self)),
            ("Gown order deadline", lambda: office.gown_deadline(self)),
            ("Capacity summary", self.capacity_summary),
            ("Ceremony summary", lambda: office.summary(self)),
            ("Cancel / reopen ceremony", self.set_status),
        ])

    def _graduand_menu(self):
        return menu("GRADUANDS AND REPLIES", [
            ("Graduands for this ceremony", lambda: office.graduands(self)),
            ("Invite graduands", lambda: office.invite(self)),
            ("Send reply and gown reminders", lambda: office.reminders(self)),
            ("Replies and guest tickets", lambda: office.rsvps(self)),
            ("Record a reply", lambda: office.record_rsvp(self)),
            ("Extra ticket requests", lambda: office.extra_tickets(self)),
            ("Move a graduand to a later ceremony", lambda: office.transfer(self)),
        ])

    def _day_menu(self):
        return menu("ON THE DAY", [
            ("Check graduands in", lambda: office.check_in(self)),
            ("Undo a check-in", lambda: office.undo_check_in(self)),
            ("Complete the ceremony (confers awards)", lambda: office.complete(self)),
        ])

    def _gown_menu(self):
        return menu("GOWNS", [
            ("List gown orders", self.list_gowns),
            ("Create / update a gown order", self.create_gown),
            ("Take gown payment", self.take_gown_payment),
            ("Update gown order status", self.update_gown_status),
            ("Cancel a gown order", lambda: office.cancel_gown(self)),
            ("Refund a cancelled order", lambda: office.refund_gown(self)),
        ])

    def _seat_menu(self):
        return menu("SEATING AND STAGE SCRIPT", [
            ("Auto-assign seats", self.auto_assign_seats),
            ("View seat plan", self.view_seat_plan),
            ("Clear seat plan", self.clear_seat_plan),
            ("Export seat plan (CSV)", self.export_seat_plan),
            ("Preview stage script", self.preview_script),
            ("Export stage script", self.export_script),
            ("Export name-pronunciation list (CSV)", self.export_pronunciation),
        ])

    def _records_menu(self):
        return menu("CONFERRALS AND CERTIFICATES", [
            ("Confer in absentia", lambda: records.confer(self)),
            ("List conferrals", lambda: records.conferrals(self)),
            ("View a conferral", lambda: records.view(self)),
            ("Review a suspended conferral", lambda: records.review(self)),
            ("Revoke an award", lambda: records.revoke(self)),
            ("Replacement certificate", lambda: records.replacement(self)),
            ("Certificate print jobs", lambda: records.print_jobs(self)),
            ("Move a print job on", lambda: records.move_job(self)),
            ("Verify a certificate", lambda: records.verify(self)),
        ])

    def _eligibility_menu(self):
        return menu("ELIGIBILITY, HOLDS AND NAMES", [
            ("Can this student graduate?", lambda: records.eligibility(self)),
            ("Open holds", lambda: records.holds(self)),
            ("Place a hold", lambda: records.place_hold(self)),
            ("Release a hold", lambda: records.release_hold(self)),
            ("Set a certificate name (with evidence)", lambda: records.set_name(self)),
        ])

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
        deadline = self._prompt("RSVP deadline (YYYY-MM-DD, optional)")
        guests = self._prompt_int("Guest tickets per graduand", default=2, minimum=0)
        notes = self._prompt("Notes (optional)")

        cid = CeremonyManager.create_ceremony(
            ceremony_name=name, ceremony_date=date, ceremony_time=time,
            venue=venue, capacity=capacity,
            rsvp_deadline=deadline, guest_tickets_per_graduand=guests, notes=notes,
        )
        self.current_ceremony_id = cid
        print(f"\n✓ Created ceremony {cid} and selected it. Set who it is for under "
              "'Who the ceremony is for'.")

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
        print("(Complete a ceremony from 'On the day' — that confers the awards.)")
        status = self._prompt_choice("New status",
                                     ('scheduled', 'cancelled'), default='scheduled')
        if not self._confirm(f"Set ceremony {cid} status to '{status}'?"):
            return
        ok = CeremonyManager.update_ceremony(cid, status=status)
        print(f"\n{'✓ Status updated.' if ok else 'No change made.'}")

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
        gown = self._prompt("Gown size")
        hood = self._prompt("Hood subject (blank = none)")
        print(f"  Hat sizes: {', '.join(GownOrderManager.HAT_SIZES)}")
        hat = self._prompt("Hat size (blank = none)")
        supplier = self._prompt("Supplier (optional)")
        slot = self._prompt("Collection slot (optional)")

        try:
            GownOrderManager.validate(gown, hood, hat)
        except ValueError as e:
            print(f"\n❌ {e}")
            return
        quote = GownOrderManager.quote(gown, hood, hat)
        print(f"\n  Quote for this order: £{quote:.2f}")
        if not self._confirm("Save this order?"):
            return
        try:
            order_id = GownOrderManager.create_order(
                ceremony_id=cid, student_id=sid, gown_size=gown, hood_subject=hood,
                hat_size=hat, supplier=supplier, collection_slot=slot,
            )
        except ValueError as e:
            print(f"\n❌ {e}")
            return
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
