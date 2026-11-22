"""Graduation window: graduands and invitations, RSVPs with named guests,
the day itself (check-in and completing the ceremony) and gown
cancellations / refunds.

Mixed into :class:`GraduationCeremonyGUI`. Every action goes through
``university/application/graduation/ceremonies`` (or ``_conferral``) via
``research_portal.common.call``, which runs it in one transaction, turns a
refusal into a dialog and sends the e-mails it returns. The rules check
permissions themselves; the tabs only decide what to show.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
    common,
)


def _rules():
    from education_system.systems.university.application.graduation import (
        ceremonies as graduation_ceremonies,
    )
    return graduation_ceremonies


def _conferral():
    from education_system.systems.university.application.graduation import (
        conferral as graduation_conferral,
    )
    return graduation_conferral


def _bar(parent):
    """A button bar packed at the bottom, before the list that expands."""
    bar = ttk.Frame(parent, padding=(0, 4))
    bar.pack(side="bottom", fill="x")
    return bar


def _btn(bar, text, command):
    ttk.Button(bar, text=text, command=command).pack(side="left", padx=3)


class GraduationOpsMixin:
    """Needs ``self.window``, ``self.notebook``, ``self.who`` and
    ``self.current_ceremony_id`` from the host."""

    def _cid(self):
        if self.current_ceremony_id is None:
            common.info(self.window, "Select a ceremony first.")
        return self.current_ceremony_id

    def _write(self, fn, *args, done=None, **kwargs):
        result = common.call(self.window, fn, *args, write=True, **kwargs)
        if result is not None:
            self._reload_active_tabs()
            self._update_capacity_label()
            if done:
                common.info(self.window, done(result) if callable(done) else done)
        return result

    # ── graduands, cohorts, invitations ──────────────────────────────────
    def _build_graduands_tab(self):
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="Graduands & invitations")
        bar = _bar(tab)
        _btn(bar, "Invite selected", self._on_invite_selected)
        _btn(bar, "Invite all eligible", lambda: self._on_invite(None))
        _btn(bar, "Send reminders", self._on_send_reminders)
        _btn(bar, "Allocate extra tickets", self._on_allocate_tickets)
        _btn(bar, "Set cohorts", self._on_set_cohorts)
        self.grad_summary = ttk.Label(tab, text="", justify="left", foreground="#333")
        self.grad_summary.pack(side="top", anchor="w", pady=(0, 4))
        self.grad_tree = common.make_tree(tab, [
            ("sid", "Student", 90), ("name", "Name", 180), ("award", "Award", 200),
            ("eligible", "Eligible", 70), ("name_ok", "Name confirmed", 110),
            ("invited", "Invited", 70), ("rsvp", "Reply", 90), ("blockers", "Blockers", 360)])
        self.grad_tree.configure(selectmode="extended")

    def _reload_graduands(self):
        if not hasattr(self, "grad_tree"):
            return
        self.grad_tree.delete(*self.grad_tree.get_children())
        cid = self.current_ceremony_id
        if cid is None:
            self.grad_summary.configure(text="")
            return
        rows = common.call(self.window, _rules().graduands, self.who, cid, quiet=True) or []
        common.fill(self.grad_tree, rows, lambda r: r["student_id"], lambda r: (
            r["student_id"], r["name"], r["award"], "yes" if r["eligible"] else "no",
            "yes" if r["name_confirmed"] else "no", "yes" if r["invited"] else "",
            r["rsvp"] or "", "; ".join(r["blockers"])))
        s = common.call(self.window, _rules().summary, cid, quiet=True)
        if s:
            cohorts = ", ".join(f"{c['kind']}={c['value']}" for c in s["cohorts"]) or "everyone"
            self.grad_summary.configure(text=(
                f"Cohorts: {cohorts}   ·   invited {s['invited']}, going {s['going']}, "
                f"seats {s['seats_taken']}/{s['capacity']}, guests {s['guests']}, "
                f"attended {s['attended']}, no-shows {s['no_shows']}, conferred "
                f"{s['conferred']}, extra tickets waiting {s['waiting_tickets']}"))

    def _on_invite_selected(self):
        ids = list(self.grad_tree.selection())
        if not ids:
            common.info(self.window, "Select graduands in the list first.")
            return
        self._on_invite(ids)

    def _on_invite(self, ids):
        cid = self._cid()
        if cid is None:
            return
        self._write(_rules().invite, self.who, cid, ids, done=lambda r: (
            f"Invited {len(r['invited'])}." + ("\nNot invited:\n" + "\n".join(
                f"  {s}: {why}" for s, why in r["skipped"]) if r["skipped"] else "")))

    def _on_send_reminders(self):
        self._write(_rules().send_reminders, done=lambda r: f"Reminders sent: {r['reminded']}")

    def _on_allocate_tickets(self):
        cid = self._cid()
        if cid is not None:
            self._write(_rules().allocate_extra_tickets, self.who, cid, done=lambda r: (
                f"Granted {r['granted']} extra ticket(s); {r['spare_left']} seat(s) left."))

    def _on_set_cohorts(self):
        cid = self._cid()
        if cid is None:
            return
        current = common.call(self.window, _rules().cohorts, cid, quiet=True) or []
        text = "\n".join(f"{c['kind']}: {c['value']}" for c in current)
        answer = common.ask(self.window, "Ceremony cohorts", [common.Field(
            "lines", "One per line — programme: CS / department: Computing / "
                     "award_year: 2025/26 (blank = everyone)", "multiline")], {"lines": text})
        if answer is None:
            return
        items = []
        for line in answer["lines"].splitlines():
            if ":" in line:
                kind, value = line.split(":", 1)
                items.append((kind.strip().lower(), value.strip()))
        self._write(_rules().set_cohorts, self.who, cid, items, done="Cohorts saved.")

    # ── RSVPs ────────────────────────────────────────────────────────────
    def _build_rsvp_tab(self):
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="RSVPs & guests")
        bar = _bar(tab)
        _btn(bar, "Record reply…", self._on_record_rsvp)
        _btn(bar, "Transfer to another ceremony…", self._on_transfer)
        panes = ttk.PanedWindow(tab, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=3)
        panes.add(right, weight=2)
        self.rsvp_tree = common.make_tree(left, [
            ("sid", "Student", 90), ("name", "Name", 170), ("status", "Reply", 80),
            ("guests", "Guests", 55), ("needs", "Access needs", 170),
            ("pron", "Pronunciation", 120), ("by", "Recorded by", 90)])
        ttk.Label(right, text="Guest tickets").pack(anchor="w")
        self.guest_tree = common.make_tree(right, [
            ("sid", "Graduand", 80), ("guest", "Guest", 140), ("ticket", "Ticket", 110),
            ("needs", "Needs", 90)], height=8)
        ttk.Label(right, text="Extra-ticket requests").pack(anchor="w", pady=(6, 0))
        self.req_tree = common.make_tree(right, [
            ("sid", "Graduand", 80), ("asked", "Asked", 50), ("granted", "Granted", 60),
            ("status", "Status", 100)], height=5)

    def _reload_rsvp_table(self):
        if not hasattr(self, "rsvp_tree"):
            return
        for tree in (self.rsvp_tree, self.guest_tree, self.req_tree):
            tree.delete(*tree.get_children())
        cid = self.current_ceremony_id
        if cid is None:
            return
        from education_system.systems.university.domains.progression.domain.degree_audit.graduation_ceremony import (  # noqa: E501
            RsvpManager,
        )
        rows = RsvpManager.list_rsvps(cid)
        common.fill(self.rsvp_tree, rows, lambda r: r["student_id"], lambda r: (
            r["student_id"], r.get("student_name", ""), r["rsvp_status"], r["num_guests"],
            r.get("accessibility_notes") or "", r.get("name_pronunciation") or "",
            r.get("recorded_by") or ""))
        guests = common.call(self.window, _rules().guests, cid, quiet=True) or []
        common.fill(self.guest_tree, guests, lambda g: g["guest_id"], lambda g: (
            g["student_id"], g["guest_name"], g["ticket_ref"], g.get("access_needs") or ""))
        reqs = common.call(self.window, _rules().ticket_requests, cid, quiet=True) or []
        common.fill(self.req_tree, reqs, lambda r: r["request_id"], lambda r: (
            r["student_id"], r["requested"], r["granted"], r["status"]))

    def _rsvp_fields(self):
        rules = _rules()
        fields = [
            common.Field("student_id", "Student", required=True),
            common.Field("status", "Reply", "combo", list(rules.RSVP_STATUSES), required=True),
            common.Field("guests", "Guests — one per line: Name, or Name | needs", "multiline"),
        ]
        fields += [common.Field(f"need_{n}", n.replace("_", " ").capitalize(), "check")
                   for n in rules.ACCESS_NEEDS]
        fields += [common.Field("notes", "Access notes"),
                   common.Field("pron", "Name pronunciation"),
                   common.Field("extra", "Extra tickets requested", "number")]
        if self.who.is_office:
            fields.append(common.Field("override", "Override deadline / cohort", "check"))
        return fields

    def _on_record_rsvp(self):
        cid = self._cid()
        if cid is None:
            return
        values = {"status": "going"}
        sel = common.selected(self.rsvp_tree)
        if sel:
            values["student_id"] = sel
        answer = common.ask(self.window, "Record a reply", self._rsvp_fields(), values,
                            columns=2)
        if answer is None:
            return
        guests = []
        for line in (answer["guests"] or "").splitlines():
            name, _sep, needs = line.partition("|")
            if name.strip():
                guests.append((name.strip(), needs.strip()))
        needs = [n for n in _rules().ACCESS_NEEDS if answer.get(f"need_{n}")]
        self._write(_rules().record_rsvp, self.who, cid, answer["student_id"].strip(),
                    answer["status"], guests=guests, access_needs=needs,
                    notes=answer["notes"], name_pronunciation=answer["pron"],
                    extra_tickets=int(answer["extra"] or 0),
                    override=bool(answer.get("override")),
                    done=lambda r: "Reply recorded." + ("\nTickets: " + ", ".join(
                        f"{n} {t}" for n, t in r["tickets"]) if r["tickets"] else ""))

    def _on_transfer(self):
        cid = self._cid()
        sid = common.selected(self.rsvp_tree)
        if cid is None or not sid:
            common.info(self.window, "Select a graduand's reply first.")
            return
        others = [(c["ceremony_id"], self._ceremony_label(c)) for c in self._ceremonies
                  if c["ceremony_id"] != cid and (c.get("status") or "scheduled") == "scheduled"]
        answer = common.ask(self.window, f"Transfer {sid}", [
            common.Field("to", "To ceremony", "combo", others, required=True),
            common.Field("reason", "Reason")])
        if answer:
            self._write(_rules().transfer, self.who, cid, sid, int(answer["to"]),
                        answer["reason"], done=f"{sid} moved.")

    # ── on the day ───────────────────────────────────────────────────────
    def _build_day_tab(self):
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="On the day")
        bar = _bar(tab)
        _btn(bar, "Check in", self._on_check_in)
        _btn(bar, "Undo check-in", self._on_undo_check_in)
        if self.who.is_office:
            _btn(bar, "Complete ceremony…", self._on_complete)
        top = ttk.Frame(tab)
        top.pack(side="top", fill="x", pady=(0, 4))
        ttk.Label(top, text="Find").pack(side="left")
        self.day_search = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.day_search, width=28)
        entry.pack(side="left", padx=4)
        entry.bind("<KeyRelease>", lambda _e: self._reload_day())
        entry.bind("<Return>", lambda _e: self._on_check_in())
        self.day_count = ttk.Label(top, text="")
        self.day_count.pack(side="left", padx=12)
        self.day_tree = common.make_tree(tab, [
            ("sid", "Student", 100), ("name", "Name", 220), ("guests", "Guests", 60),
            ("needs", "Access", 200), ("pron", "Pronunciation", 160),
            ("in", "Checked in", 150), ("by", "By", 100)])
        self.day_tree.bind("<Double-1>", lambda _e: self._on_check_in())

    def _reload_day(self):
        if not hasattr(self, "day_tree"):
            return
        self.day_tree.delete(*self.day_tree.get_children())
        cid = self.current_ceremony_id
        if cid is None:
            return
        from education_system.systems.university.domains.progression.domain.degree_audit.graduation_ceremony import (  # noqa: E501
            RsvpManager,
        )
        needle = self.day_search.get().strip().lower()
        rows = [r for r in RsvpManager.list_rsvps(cid, status="going")
                if not needle or needle in f"{r['student_id']} {r.get('student_name', '')}".lower()]
        common.fill(self.day_tree, rows, lambda r: r["student_id"], lambda r: (
            r["student_id"], r.get("student_name", ""), r["num_guests"],
            r.get("accessibility_notes") or "", r.get("name_pronunciation") or "",
            r.get("attended_at") or "", r.get("checked_in_by") or ""))
        done = sum(1 for r in rows if r.get("attended_at"))
        self.day_count.configure(text=f"{done} of {len(rows)} checked in")

    def _day_sid(self):
        sid = common.selected(self.day_tree)
        if not sid:
            kids = self.day_tree.get_children()
            sid = kids[0] if len(kids) == 1 else None
        if not sid:
            common.info(self.window, "Select a graduand (or search until one is left).")
        return sid

    def _on_check_in(self):
        cid, sid = self.current_ceremony_id, self._day_sid()
        if cid is not None and sid:
            self._write(_rules().check_in, self.who, cid, sid)

    def _on_undo_check_in(self):
        cid, sid = self.current_ceremony_id, self._day_sid()
        if cid is not None and sid and common.confirm(self.window, f"Undo {sid}'s check-in?"):
            self._write(_rules().undo_check_in, self.who, cid, sid)

    def _on_complete(self):
        cid = self._cid()
        if cid is None or not common.confirm(
                self.window, "Complete this ceremony? Everyone checked in has their award "
                             "conferred; everyone else is marked as a no-show."):
            return
        result = self._write(_rules().complete, self.who, cid)
        if result is None:
            return
        for item in result["conferred"]:
            _conferral().after_commit(item)
        lines = [f"Conferred: {len(result['conferred'])}"]
        lines += [f"  {c['student_id']}: certificate {c['certificate_number']}"
                  for c in result["conferred"]]
        if result["failed"]:
            lines.append(f"Not conferred: {len(result['failed'])}")
            lines += [f"  {sid}: {why}" for sid, why in result["failed"]]
        if result["no_shows"]:
            lines.append("No-shows (confer in absentia or transfer): " +
                         ", ".join(result["no_shows"]))
        common.info(self.window, "\n".join(lines))
        if hasattr(self, "_ctx"):
            self._ctx.refresh_all()

    # ── gown cancellations and refunds ───────────────────────────────────
    def _on_cancel_gown(self):
        oid = getattr(self, "_selected_gown_order_id", None)
        if not oid:
            common.info(self.window, "Select an order in the table first.")
            return
        reason = common.ask_text(self.window, "Cancel gown order", "Reason", multiline=False)
        if reason:
            self._write(_rules().cancel_gown_order, self.who, oid, reason,
                        done="Order cancelled. A paid order is now due a refund.")

    def _on_refund_gown(self):
        oid = getattr(self, "_selected_gown_order_id", None)
        if not oid:
            common.info(self.window, "Select a cancelled, paid order first.")
            return
        result = self._write(_rules().refund_gown_order, self.who, oid,
                             done=lambda r: f"Refunded £{r['amount']:.2f}.")
        if result is not None:
            _rules().post_refund(result, self.who.username)
