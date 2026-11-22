"""The portal sections fed by the linked areas, mixed into
:class:`portal_views.PortalFrame`:

* **Messages** - school announcements (read / "I have read this"), letters
  home with the reply slip, and parents' evening booking / cancelling;
* **Money** - trips (consent, cost, paid, balance, next payment) and the
  dinner money account;
* **Wellbeing** - the pupil's own check-in (pupils only).

Everything goes through :mod:`modules.portals.domain.portal`, which checks
the login is linked to the child on every call.
"""

from __future__ import annotations

from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.secondary.modules.portals.domain import portal as PT
from education_system.systems.secondary.ui.gui.components import widgets as W

_ERRORS = (PT.ValidationError, PT.PermissionDenied, PT.NotFound)


def _v():
    from education_system.systems.secondary.modules.portals.gui import portal_views
    return portal_views


class PortalLinkedMixin:
    principal: Any
    pupil_id: int | None
    is_pupil: bool

    # ── Home additions ──────────────────────────────────────────────
    def _draw_home_linked(self, f, h: dict[str, Any]) -> None:
        v = _v()
        an = h.get("announcements") or {}
        unread = {a.announcement_id for a in an.get("unread") or []}
        ack = {a.announcement_id for a in an.get("to_acknowledge") or []}
        if an.get("active"):
            box = v._box(f, "Notices from school")
            for a in an["active"][:5]:
                self._announcement_row(box, a, a.announcement_id in unread,
                                       a.announcement_id in ack)
        dinner = h.get("dinner") or {}
        trips = h.get("trips") or []
        owing = [t for t in trips if t["balance_pence"]]
        no_consent = [t for t in trips if t["consent"] == "Not given"]
        if dinner.get("overdrawn") or dinner.get("low") or owing or no_consent:
            box = v._box(f, "Money and consent")
            if dinner.get("overdrawn"):
                ttk.Label(box, text=f"Dinner money is overdrawn: {dinner['balance']}",
                          foreground="#a00").pack(anchor="w")
            elif dinner.get("low"):
                ttk.Label(box, text=f"Dinner money is running low: {dinner['balance']}",
                          foreground="#a60").pack(anchor="w")
            for t in owing:
                ttk.Label(box, text=f"{t['trip']}: {t['balance']} to pay"
                          + (f" ({t['next_due']})" if t["next_due"] else ""),
                          foreground="#a60").pack(anchor="w")
            for t in no_consent:
                ttk.Label(box, text=f"{t['trip']}: consent not given yet"
                          + (f" (by {v._date(t['consent_due'])})" if t["consent_due"] else ""),
                          foreground="#a60").pack(anchor="w")
            ttk.Button(box, text="Open Money", command=lambda: self.show("Money")).pack(
                anchor="w", pady=(4, 0))

    def _announcement_row(self, box, a, unread: bool, needs_ack: bool) -> None:
        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Label(row, text=("● " if unread else "") + a.title
                  + (f" - {a.summary}" if a.summary else ""),
                  foreground="#a00" if needs_ack else "", wraplength=560,
                  justify="left").pack(side="left")
        ttk.Button(row, text="I have read this" if needs_ack else "Read",
                   command=lambda: self._read_announcement(a, needs_ack)).pack(side="right")

    def _read_announcement(self, a, needs_ack: bool) -> None:
        top = self._top()
        try:
            if needs_ack:
                ok = messagebox.askyesno(a.title, a.body + "\n\nI have read and understood "
                                         "this.", parent=top)
                PT.read_announcement(self.principal, a.announcement_id, acknowledge=ok)
            else:
                PT.read_announcement(self.principal, a.announcement_id)
                messagebox.showinfo(a.title, a.body, parent=top)
        except _ERRORS as e:
            messagebox.showerror(a.title, W.problems(e), parent=top)
        self.show(self.section)

    # ── Messages ────────────────────────────────────────────────────
    def _draw_messages(self, f) -> None:
        v = _v()
        m = PT.messages(self.principal, self.pupil_id)
        an = m["announcements"]
        unread = {a.announcement_id for a in an["unread"]}
        ack = {a.announcement_id for a in an["to_acknowledge"]}
        box = v._box(f, "Announcements")
        if not an["active"]:
            v._empty(box, "No announcements at the moment.")
        for a in an["active"]:
            self._announcement_row(box, a, a.announcement_id in unread,
                                   a.announcement_id in ack)
        if self.is_pupil:
            return
        self._draw_parents_evenings(f, m["parents_evenings"])
        box = v._box(f, "Letters home")
        if not m["letters"]:
            v._empty(box, "No letters yet.")
        for r in m["letters"]:
            row = ttk.Frame(box)
            row.pack(fill="x", pady=1)
            state = ""
            if r.reply_question:
                state = f" - replied {r.reply}" if r.reply else (
                    f" - reply needed by {v._date(r.reply_by)}" if r.reply_by
                    else " - reply needed")
            ttk.Label(row, text=f"{v._date(r.sent_at)}  {r.subject}{state}",
                      foreground="#a60" if r.reply_question and not r.reply else "").pack(
                side="left")
            ttk.Button(row, text="Read", command=lambda r=r: self._letter(r)).pack(
                side="right")

    def _letter(self, r) -> None:
        top = self._top()
        if not r.reply_question or r.reply:
            messagebox.showinfo(r.subject, r.body, parent=top)
            return

        def save(val: dict[str, Any]) -> None:
            PT.reply_to_letter(self.principal, r.recipient_id, val["reply"],
                               val["note"] or None)
            self.show(self.section)
        W.form_dialog(top, r.subject, [("reply", r.reply_question, "Yes", ["Yes", "No"]),
                                       ("note", "Note (optional)", "", "text")], save,
                      r.body[:1200])

    def _draw_parents_evenings(self, f, rows: list[dict[str, Any]]) -> None:
        v = _v()
        box = v._box(f, "Parents' evenings")
        if not rows:
            v._empty(box, "No parents' evenings coming up for this year group.")
        for x in rows:
            e = x["event"]
            ttk.Label(box, text=f"{e.name} - {v._date(e.event_date)} {e.start_time}-"
                      f"{e.end_time}" + (f", {e.location}" if e.location else "")
                      + ("" if x["can_book"] else f" ({e.status.lower()})"),
                      font=("", 10, "bold")).pack(anchor="w", pady=(4, 0))
            for t in x["teachers"]:
                row = ttk.Frame(box)
                row.pack(fill="x")
                b = t["booking"]
                text = f"  {t['teacher']} ({', '.join(t['subjects'])})"
                if b is not None:
                    text += f": booked {b.slot_time}" + (f", room {t['room']}" if t["room"]
                                                          else "")
                elif t["free"]:
                    text += f": {len(t['free'])} free slot(s)"
                ttk.Label(row, text=text).pack(side="left")
                if b is not None and x["can_book"]:
                    ttk.Button(row, text="Cancel", command=lambda b=b: self._cancel_pe(b)
                               ).pack(side="right")
                elif t["free"]:
                    ttk.Button(row, text="Book", command=lambda e=e, t=t: self._book_pe(e, t)
                               ).pack(side="right")

    def _book_pe(self, e, t: dict[str, Any]) -> None:
        def save(val: dict[str, Any]) -> None:
            PT.book_parents_evening(self.principal, e.event_id, self.pupil_id,
                                    t["teacher_key"], val["slot"])
            self.show(self.section)
        W.form_dialog(self._top(), f"Book {t['teacher']}",
                      [("slot", "Time", t["free"][0], list(t["free"]))], save,
                      f"{e.name}, {e.event_date}")

    def _cancel_pe(self, b) -> None:
        top = self._top()
        if not messagebox.askyesno("Cancel appointment", f"Cancel {b.slot_time} with "
                                   f"{b.teacher_name}?", parent=top):
            return
        try:
            PT.cancel_parents_evening(self.principal, b.booking_id)
        except _ERRORS as ex:
            messagebox.showerror("Cancel appointment", W.problems(ex), parent=top)
        self.show(self.section)

    # ── Money ───────────────────────────────────────────────────────
    def _draw_money(self, f) -> None:
        v = _v()
        d = PT.dinner_money(self.principal, self.pupil_id)
        box = v._box(f, "Dinner money")
        colour = "#a00" if d["overdrawn"] else "#a60" if d["low"] else ""
        ttk.Label(box, text=f"Balance: {d['balance']}" + (" · free school meals"
                                                         if d["fsm"] else ""),
                  font=("", 12, "bold"), foreground=colour).pack(anchor="w")
        if d["overdrawn"]:
            v._empty(box, "The account is overdrawn - please top it up.")
        elif d["low"]:
            v._empty(box, "The balance is running low.")
        if d["recent"]:
            tree = v._tree(box, [("date", "Date", 90), ("detail", "What", 260),
                                 ("amt", "Amount", 90)], height=min(8, len(d["recent"])))
            for x in d["recent"]:
                tree.insert("", "end", values=(v._date(x["date"]), x["what"], x["amount"]))
        rows = PT.trips(self.principal, self.pupil_id)
        box = v._box(f, "Trips")
        if not rows:
            v._empty(box, "No trips coming up.")
            return
        tree = v._tree(box, [("title", "Trip", 200), ("dates", "Dates", 150),
                             ("consent", "Consent", 90), ("cost", "Cost", 70),
                             ("paid", "Paid", 70), ("bal", "To pay", 70),
                             ("detail", "Next", 160)], height=min(8, len(rows)))
        for t in rows:
            tags = ("warn",) if t["balance_pence"] or t["consent"] == "Not given" else ()
            tree.insert("", "end", tags=tags, values=(
                t["trip"], t["dates"], t["consent"], t["cost"] if t["charging"] else "-",
                t["paid"], t["balance"], t["next_due"] or ""))
        v._empty(box, "Consent and payments are handled by the school office.")

    # ── Wellbeing ───────────────────────────────────────────────────
    def _draw_wellbeing(self, f) -> None:
        v = _v()
        w = PT.wellbeing(self.principal, self.pupil_id)
        box = v._box(f, "How are you doing?")
        for s in w["surveys"]:
            ttk.Label(box, text=f"{s.title}" + (f" - {s.question}" if s.question else ""),
                      foreground="#06a").pack(anchor="w")
        lo, hi = w["scale"]
        v._empty(box, f"Score each from {lo} (not good) to {hi} (great). A member of staff "
                      "reads these - if you need help now, talk to your tutor or any adult "
                      "you trust.")
        if not w["can_check_in"]:
            return
        scale = [str(i) for i in range(lo, hi + 1)]

        def save(val: dict[str, Any]) -> None:
            PT.check_in(self.principal, self.pupil_id, val)
            messagebox.showinfo("Check in", "Thank you - your check-in has been saved.",
                                parent=self._top())
        ttk.Button(box, text="Check in now", command=lambda: W.form_dialog(
            self._top(), "Wellbeing check-in",
            [("mood_rating", "My mood", "", scale),
             ("confidence_rating", "How confident I feel", "", scale),
             ("connection_rating", "How connected I feel to others", "", scale),
             ("notes", "Anything you want to tell us (optional)", "", "text")], save)
        ).pack(anchor="w", pady=(6, 0))


__all__ = ["PortalLinkedMixin"]
