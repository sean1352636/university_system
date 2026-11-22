"""The academic-year screen and the personal / admin calendar tools.

Everything goes through ``university/application/academic_calendar/`` (one
transaction per action via ``record_screens.call``); the rules re-check who
may do what, so a hidden button is a convenience, not the guard.

* **Academic year** (calendar administrators): years (new, edit, reopen,
  roll over), and for the selected year its terms, key dates, teaching
  weeks, vacations / term time, checks, imports from other systems, publish
  (with a preview of errors, warnings, changes and the old terms it will
  supersede) and the change log.
* **My calendar feed** / **My reminders** for everyone signed in.
* **Events without a date**, **Calendar administrators**, **Calendar audit
  log** for administrators.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import ttk

from education_system.systems.university.infrastructure.ui import record_screens as rs


def _rules():
    from education_system.systems.university.application.academic_calendar import (
        access as calendar_access,
        dates as calendar_dates,
        events as calendar_events,
        year as calendar_year,
    )
    return calendar_access, calendar_year, calendar_dates, calendar_events


def _bar(parent):
    """A button row packed at the bottom (before the list fills the rest)."""
    bar = ttk.Frame(parent)
    bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(4, 0))
    return bar


def _btn(bar, text, command):
    ttk.Button(bar, text=text, command=command).pack(side=tk.LEFT, padx=2, pady=2)


class AcademicYearScreenMixin:
    """Mixed into ``CalendarGUI``; expects ``self.who``, ``self.root``,
    ``self.content_area`` and ``self._clear_content_area()``."""

    # The old Academic Years / Semesters screens wrote tables nothing else
    # reads; the audit screen read a log nothing wrote. They open these now.
    def _show_academic_years(self):
        self._show_year_screen()

    def _show_semesters(self):
        self._show_year_screen()

    def _show_audit_logs(self):
        self._show_calendar_audit()

    # ── helpers ─────────────────────────────────────────────────────────

    def _cal_call(self, fn, *args, write=False, **kwargs):
        return rs.call(self.root, fn, *args, write=write, **kwargs)

    def _screen(self, title, subtitle=""):
        self._clear_content_area()
        head = ttk.Frame(self.content_area, padding=(10, 8))
        head.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(head, text=title, font=("Arial", 16, "bold")).pack(side=tk.LEFT)
        if subtitle:
            ttk.Label(head, text=subtitle, foreground="#555").pack(side=tk.LEFT, padx=12)
        body = ttk.Frame(self.content_area, padding=(10, 0, 10, 10))
        body.pack(fill=tk.BOTH, expand=True)
        return body

    # ── academic year ───────────────────────────────────────────────────

    def _show_year_screen(self):
        if not (self.who and self.who.is_admin):
            rs.info(self.root, "The academic year is managed by calendar administrators. The "
                               "published dates appear in the calendar.")
            return
        body = self._screen("Academic year", "Draft → publish. Publishing updates terms, "
                                             "closures and teaching weeks everywhere.")
        panes = ttk.PanedWindow(body, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(panes, width=360)
        right = ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=3)
        bar = _bar(left)
        for text, cmd in (("New year…", self._year_new), ("Edit dates…", self._year_edit),
                          ("Reopen", self._year_reopen), ("Roll over…", self._year_rollover)):
            _btn(bar, text, cmd)
        self._years_tree = rs.make_tree(left, [("year", "Year", 90), ("status", "Status", 80),
                                               ("version", "Ver.", 40),
                                               ("dates", "Dates", 170)], height=10)
        self._years_tree.bind("<<TreeviewSelect>>", lambda _e: self._year_selected())
        self._year_tabs = ttk.Notebook(right)
        self._year_tabs.pack(fill=tk.BOTH, expand=True)
        self._year_pages = {}
        for key, label in (("terms", "Terms"), ("dates", "Key dates"), ("weeks", "Weeks"),
                           ("vacations", "Vacations & term time"), ("checks", "Checks & publish"),
                           ("log", "Change log")):
            page = ttk.Frame(self._year_tabs, padding=6)
            self._year_tabs.add(page, text=f"  {label}  ")
            self._year_pages[key] = page
        self._build_terms_page()
        self._build_dates_page()
        self._build_weeks_page()
        self._build_vacations_page()
        self._build_checks_page()
        self._build_log_page()
        self._year_code = None
        self._load_years()

    def _load_years(self, select=None):
        _a, cy, _d, _e = _rules()
        rows = self._cal_call(cy.years) or []
        rs.fill(self._years_tree, rows, lambda r: r["year_code"],
                lambda r: (r["year_code"], r["status"], r["version"],
                           f"{r['start_date']} – {r['end_date']}"))
        target = select or self._year_code or (rows[0]["year_code"] if rows else None)
        if target and self._years_tree.exists(target):
            self._years_tree.selection_set(target)
        else:
            self._year_code = None
            self._refresh_year_pages()

    def _year_selected(self):
        sel = rs.selected(self._years_tree)
        if sel:
            self._year_code = sel
            self._refresh_year_pages()

    def _need_year(self):
        if not self._year_code:
            rs.info(self.root, "Select a year first.")
            return False
        return True

    def _year_write(self, fn, *args, done=None, **kwargs):
        result = self._cal_call(fn, *args, write=True, **kwargs)
        if result is not None:
            self._load_years()
            if done:
                rs.info(self.root, done)
        return result

    def _year_new(self):
        _a, cy, cd, _e = _rules()
        start_year = date.today().year if date.today().month < 9 else date.today().year + 1
        start, end = cy.default_year_dates(start_year)
        ans = rs.ask(self.root, "New academic year", [
            rs.Field("code", "Year", required=True, hint="e.g. 2026/2027"),
            rs.Field("start", "Starts", "date", required=True),
            rs.Field("end", "Ends", "date", required=True),
            rs.Field("region", "Bank holidays for", "combo", list(cd.REGIONS), required=True)],
            {"code": f"{start_year}/{start_year + 1}", "start": start, "end": end,
             "region": cd.REGIONS[0]})
        if ans:
            code = self._cal_call(cy.create_year, self.who, ans["code"], ans["start"],
                                  ans["end"], ans["region"], write=True)
            if code:
                self._year_code = code
                self._load_years(code)

    def _year_edit(self):
        if not self._need_year():
            return
        _a, cy, _d, _e = _rules()
        row = self._cal_call(cy.year, self._year_code)
        if not row:
            return
        ans = rs.ask(self.root, f"Edit {self._year_code}", [
            rs.Field("start", "Starts", "date", required=True),
            rs.Field("end", "Ends", "date", required=True),
            rs.Field("notes", "Notes", "multiline")],
            {"start": row["start_date"], "end": row["end_date"], "notes": row.get("notes")})
        if ans:
            self._year_write(cy.update_year, self.who, self._year_code, ans["start"], ans["end"],
                             ans["notes"] or None)

    def _year_reopen(self):
        if self._need_year() and rs.confirm(self.root, f"Reopen {self._year_code} as a draft? "
                                                       "Nothing changes for anyone until you "
                                                       "publish again."):
            _a, cy, _d, _e = _rules()
            self._year_write(cy.reopen, self.who, self._year_code)

    def _year_rollover(self):
        if not self._need_year():
            return
        _a, _y, cd, _e = _rules()
        first = int(self._year_code[:4]) + 1
        ans = rs.ask(self.root, f"Roll {self._year_code} forward", [
            rs.Field("code", "New year", required=True)], {"code": f"{first}/{first + 1}"})
        if ans:
            code = self._year_write(cd.rollover, self.who, self._year_code, ans["code"],
                                    done="Created as a draft. Terms and key dates moved by whole "
                                         "weeks; bank holidays recomputed. Check them before "
                                         "publishing.")
            if code:
                self._year_code = code
                self._load_years(code)

    def _refresh_year_pages(self):
        for fn in (self._load_terms, self._load_dates, self._load_weeks, self._load_vacations,
                   self._load_log):
            fn()
        self._checks_detail.clear("Run the checks to see what would block publishing.")

    # terms

    def _build_terms_page(self):
        page = self._year_pages["terms"]
        bar = _bar(page)
        for text, cmd in (("Add term…", lambda: self._term_edit(None)),
                          ("Edit term…", self._term_edit_selected),
                          ("Delete term", self._term_delete)):
            _btn(bar, text, cmd)
        self._terms_tree = rs.make_tree(page, [("name", "Term", 140), ("start", "Starts", 100),
                                               ("end", "Ends", 100),
                                               ("weeks", "Teaching weeks", 110)])

    def _load_terms(self):
        tree = self._terms_tree
        tree.delete(*tree.get_children())
        if not self._year_code:
            return
        _a, cy, cd, _e = _rules()
        rows = self._cal_call(cy.terms, self._year_code) or []
        check = self._cal_call(cd.check_year, self._year_code, quiet=True) or {}
        weeks = check.get("teaching_weeks", {})
        rs.fill(tree, rows, lambda r: r["term_id"],
                lambda r: (r["name"], r["start_date"], r["end_date"], weeks.get(r["name"], "—")))

    def _term_edit_selected(self):
        tid = rs.selected(self._terms_tree)
        if not tid:
            rs.info(self.root, "Select a term.")
            return
        values = self._terms_tree.item(tid, "values")
        self._term_edit(int(tid), {"name": values[0], "start": values[1], "end": values[2]})

    def _term_edit(self, term_id, values=None):
        if not self._need_year():
            return
        _a, cy, _d, _e = _rules()
        ans = rs.ask(self.root, "Term", [rs.Field("name", "Name", required=True,
                                                  hint="Autumn, Spring, Summer…"),
                                         rs.Field("start", "Starts", "date", required=True),
                                         rs.Field("end", "Ends", "date", required=True)], values)
        if ans:
            if self._cal_call(cy.save_term, self.who, self._year_code, ans["name"], ans["start"],
                              ans["end"], term_id, write=True) is not None:
                self._refresh_year_pages()

    def _term_delete(self):
        tid = rs.selected(self._terms_tree)
        if tid and rs.confirm(self.root, "Delete this term from the draft?"):
            _a, cy, _d, _e = _rules()
            if self._cal_call(cy.delete_term, self.who, self._year_code, int(tid),
                              write=True) is not None:
                self._refresh_year_pages()

    # key dates

    def _build_dates_page(self):
        page = self._year_pages["dates"]
        bar = _bar(page)
        for text, cmd in (("Add key date…", lambda: self._date_edit(None)),
                          ("Edit…", self._date_edit_selected), ("Delete", self._date_delete),
                          ("Import from other systems", self._date_import)):
            _btn(bar, text, cmd)
        ttk.Label(bar, text="Imported and computed dates change at their source.",
                  foreground="#666").pack(side=tk.LEFT, padx=8)
        self._dates_tree = rs.make_tree(page, [("kind", "Kind", 160), ("title", "Title", 220),
                                               ("start", "From", 90), ("end", "To", 90),
                                               ("aud", "For", 70), ("src", "Source", 120)])
        self._dates_rows = {}

    def _load_dates(self):
        tree = self._dates_tree
        tree.delete(*tree.get_children())
        if not self._year_code:
            return
        _a, cy, _d, _e = _rules()
        rows = self._cal_call(cy.key_dates, self._year_code) or []
        self._dates_rows = {str(r["key_date_id"]): r for r in rows}
        rs.fill(tree, rows, lambda r: r["key_date_id"],
                lambda r: (cy.KINDS.get(r["kind"], r["kind"]), r["title"], r["start_date"],
                           r["end_date"] or "", r["audience"], r["source"]))

    def _date_edit_selected(self):
        did = rs.selected(self._dates_tree)
        row = self._dates_rows.get(str(did)) if did else None
        if not row:
            rs.info(self.root, "Select a key date.")
            return
        if row["source"] != "manual":
            rs.info(self.root, "That date comes from another system (or is a computed bank "
                               "holiday); change it there.")
            return
        self._date_edit(int(did), row)

    def _date_edit(self, key_date_id, row=None):
        if not self._need_year():
            return
        _a, cy, _d, _e = _rules()
        kinds = [(k, v) for k, v in cy.KINDS.items()]
        values = None
        if row:
            values = {"kind": row["kind"], "title": row["title"], "start": row["start_date"],
                      "end": row["end_date"], "audience": row["audience"], "notes": row["notes"]}
        ans = rs.ask(self.root, "Key date", [
            rs.Field("kind", "Kind", "combo", kinds, required=True),
            rs.Field("title", "Title", required=True),
            rs.Field("start", "From", "date", required=True),
            rs.Field("end", "To (optional)", "date"),
            rs.Field("audience", "For", "combo", ["all", "students", "staff"], required=True),
            rs.Field("notes", "Notes", "multiline")], values or {"audience": "all"})
        if ans and self._cal_call(cy.save_key_date, self.who, self._year_code, ans["kind"],
                                  ans["title"], ans["start"], ans["end"] or None,
                                  ans["audience"], ans["notes"], key_date_id,
                                  write=True) is not None:
            self._refresh_year_pages()

    def _date_delete(self):
        did = rs.selected(self._dates_tree)
        row = self._dates_rows.get(str(did)) if did else None
        if row and row["source"] != "manual" and row["source"] != "computed":
            rs.info(self.root, "Imported dates are replaced on the next import.")
            return
        if did and rs.confirm(self.root, "Delete this key date from the draft?"):
            _a, cy, _d, _e = _rules()
            if self._cal_call(cy.delete_key_date, self.who, self._year_code, int(did),
                              write=True) is not None:
                self._refresh_year_pages()

    def _date_import(self):
        if not self._need_year():
            return
        _a, _y, cd, _e = _rules()
        counts = self._cal_call(cd.import_dates, self.who, self._year_code, write=True)
        if counts is not None:
            self._refresh_year_pages()
            rs.info(self.root, "Imported: " + (", ".join(f"{k} {v}" for k, v in counts.items())
                                               or "nothing found for this year"))

    # weeks

    def _build_weeks_page(self):
        page = self._year_pages["weeks"]
        ttk.Label(page, text="Term weeks count from the Monday of each term's first week, as the "
                             "timetable does. Reading weeks and fully closed weeks are not "
                             "teaching weeks.", foreground="#555", wraplength=760).pack(
            side=tk.TOP, anchor="w", pady=(0, 4))
        self._weeks_tree = rs.make_tree(page, [("term", "Term", 110), ("week", "Week", 60),
                                               ("tw", "Teaching week", 100),
                                               ("start", "Monday", 100), ("why", "Not teaching",
                                                                          140)])

    def _load_weeks(self):
        tree = self._weeks_tree
        tree.delete(*tree.get_children())
        if not self._year_code:
            return
        _a, _y, cd, _e = _rules()
        rows = self._cal_call(cd.weeks, self._year_code) or []
        for n, w in enumerate(rows):
            tree.insert("", "end", iid=str(n), values=(w["term"], w["week"],
                                                       w["teaching_week"] or "—", w["start"],
                                                       w["why_not"] or ""))

    # vacations / term time

    def _build_vacations_page(self):
        page = self._year_pages["vacations"]
        box = ttk.LabelFrame(page, text="Is this date term time?", padding=6)
        box.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        self._tt_date = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(box, textvariable=self._tt_date, width=12).pack(side=tk.LEFT)
        _btn(box, "Check", self._term_time_check)
        self._tt_answer = ttk.Label(box, text="")
        self._tt_answer.pack(side=tk.LEFT, padx=10)
        ttk.Label(page, text="Vacations (UKVI work limits relax; sponsor monitoring treats these "
                             "as vacation):", foreground="#555").pack(side=tk.TOP, anchor="w")
        self._vac_tree = rs.make_tree(page, [("start", "From", 110), ("end", "To", 110),
                                             ("before", "Before term", 140)])

    def _load_vacations(self):
        tree = self._vac_tree
        tree.delete(*tree.get_children())
        if not self._year_code:
            return
        _a, _y, cd, _e = _rules()
        rows = self._cal_call(cd.vacation_periods, self._year_code) or []
        for n, v in enumerate(rows):
            tree.insert("", "end", iid=str(n), values=(v["start"], v["end"],
                                                       v["before"] or "(end of year)"))

    def _term_time_check(self):
        _a, _y, cd, _e = _rules()
        day = self._tt_date.get().strip()
        answer = self._cal_call(cd.is_term_time, day)
        term = self._cal_call(cd.term_for, day, quiet=True)
        if answer is None:
            text = "No published year covers that date."
        elif answer is True:
            text = f"Term time ({term['name']} {term['year_code']})" if term else "Term time"
        elif answer is False and term:
            text = f"Not term time: a closure, bank holiday or reading week in {term['name']}"
        else:
            text = "Vacation"
        self._tt_answer.configure(text=text)

    # checks and publish

    def _build_checks_page(self):
        page = self._year_pages["checks"]
        bar = _bar(page)
        _btn(bar, "Run checks", self._run_checks)
        _btn(bar, "Publish…", self._publish)
        self._checks_detail = rs.Detail(page)
        self._checks_detail.pack(fill=tk.BOTH, expand=True)

    def _run_checks(self):
        if not self._need_year():
            return
        _a, cy, _d, _e = _rules()
        p = self._cal_call(cy.preview_publish, self.who, self._year_code)
        if p is not None:
            self._show_preview(p)
        return p

    def _show_preview(self, p):
        sections = [
            ("Blocking problems", [("✗", e, "bad") for e in p["errors"]] or ["None"]),
            ("Warnings", [("!", w, "warn") for w in p["warnings"]] or ["None"]),
            ("Clashes", [("!", c, "warn") for c in p["clashes"]] or ["None"]),
            ("Teaching weeks", [(k, v) for k, v in p["teaching_weeks"].items()]),
            (f"Changes in version {p['version']}", p["changes"] or ["No changes"]),
            ("Older terms that will be marked Superseded",
             [f"{t['name']} ({t['academic_year']}, {t['start_date']} – {t['end_date']})"
              for t in p["supersedes"]] or ["None"]),
        ]
        self._checks_detail.show(f"{self._year_code} — before publishing", sections)

    def _publish(self):
        p = self._run_checks()
        if not p:
            return
        if p["errors"]:
            rs.info(self.root, "Fix the blocking problems first.")
            return
        text = (f"Publish {self._year_code} (version {p['version']})?\n\n"
                f"{len(p['changes'])} change(s); {len(p['supersedes'])} older term(s) will be "
                f"marked Superseded; {len(p['warnings'])} warning(s).\n\nStaff and students are "
                "told what changed.")
        if not rs.confirm(self.root, text):
            return
        note = rs.ask_text(self.root, "Publish", "Note for the announcement (optional)",
                           required=False)
        if note is None:
            return
        _a, cy, _d, _e = _rules()
        result = self._year_write(cy.publish, self.who, self._year_code, note)
        if result:
            rs.info(self.root, f"Published version {result['version']}. "
                               f"{len(result.get('emails') or [])} people e-mailed.")
            self._refresh_year_pages()

    # change log

    def _build_log_page(self):
        self._log_detail = rs.Detail(self._year_pages["log"])
        self._log_detail.pack(fill=tk.BOTH, expand=True)

    def _load_log(self):
        if not self._year_code:
            self._log_detail.clear("Select a year.")
            return
        _a, cy, _d, _e = _rules()
        rows = self._cal_call(cy.change_log, self._year_code) or []
        self._log_detail.show(f"{self._year_code} publications", [
            (f"Version {r['version']} — {r['published_at']} by {r['published_by']}",
             r["changes"] or ["(first publication)" if r["version"] == 1 else "No changes"])
            for r in rows] or [("", "Not published yet.")])

    # ── personal tools ──────────────────────────────────────────────────

    def _show_my_feed(self):
        if not self.who:
            return
        body = self._screen("My calendar feed", "Subscribe from Outlook, Google or Apple "
                                                "Calendar.")
        ttk.Label(body, text="The feed holds the published key dates, the events you can see "
                             "and your own timetable. The link is private: anyone who has it can "
                             "read your calendar, so make a new one if it leaks (the old one "
                             "stops working).", wraplength=760, justify="left").pack(
            anchor="w", pady=6)
        self._feed_var = tk.StringVar(value="(no link shown — links are only shown once)")
        row = ttk.Frame(body)
        row.pack(fill=tk.X, pady=6)
        ttk.Entry(row, textvariable=self._feed_var, width=90, state="readonly").pack(
            side=tk.LEFT)
        _btn(row, "Copy", lambda: self._copy_to_clipboard(self._feed_var.get()))
        bar = ttk.Frame(body)
        bar.pack(fill=tk.X, pady=6)
        _btn(bar, "Make a new feed link", self._feed_new)
        _btn(bar, "Stop my feed", self._feed_stop)

    def _feed_new(self):
        _a, _y, _d, ce = _rules()
        result = self._cal_call(ce.create_feed, self.who, write=True)
        if result:
            self._feed_var.set(result["url"])

    def _feed_stop(self):
        _a, _y, _d, ce = _rules()
        n = self._cal_call(ce.revoke_feed, self.who, write=True)
        if n is not None:
            self._feed_var.set("(feed stopped)")
            rs.info(self.root, "Your feed link no longer works." if n else "You had no feed.")

    def _show_my_reminders(self):
        if not self.who:
            return
        body = self._screen("My reminders")
        bar = _bar(body)
        _btn(bar, "Add a reminder…", self._reminder_add)
        _btn(bar, "Cancel reminder", self._reminder_cancel)
        self._rem_tree = rs.make_tree(body, [("event", "Event", 260), ("at", "Remind at", 150)])
        self._load_reminders()

    def _load_reminders(self):
        _a, _y, _d, ce = _rules()
        rows = self._cal_call(ce.my_reminders, self.who) or []
        rs.fill(self._rem_tree, rows, lambda r: r["reminder_id"],
                lambda r: (r["event_id"], r["remind_at"]))

    def _reminder_add(self, event_id=None):
        _a, _y, _d, ce = _rules()
        today = date.today()
        events = self._cal_call(ce.visible_events, self.who, today.isoformat(),
                                today.replace(year=today.year + 1).isoformat()) or []
        choices = [(e["id"], f"{(e['start'] or '')[:16]}  {e['title']}") for e in events
                   if e["source"] == "event" and e["start"]]
        if not choices:
            rs.info(self.root, "There are no upcoming events to be reminded about.")
            return
        ans = rs.ask(self.root, "Reminder", [
            rs.Field("event", "Event", "combo", choices, required=True),
            rs.Field("minutes", "Minutes before", "combo",
                     ["15", "30", "60", "120", "1440"], required=True)],
            {"event": event_id, "minutes": "60"})
        if ans and self._cal_call(ce.add_reminder, self.who, ans["event"], int(ans["minutes"]),
                                  write=True) is not None:
            if hasattr(self, "_rem_tree") and self._rem_tree.winfo_exists():
                self._load_reminders()
            else:
                rs.info(self.root, "Reminder set.")

    def _reminder_cancel(self):
        rid = rs.selected(self._rem_tree)
        if rid:
            _a, _y, _d, ce = _rules()
            if self._cal_call(ce.cancel_reminder, self.who, int(rid), write=True) is not None:
                self._load_reminders()

    # ── admin tools ─────────────────────────────────────────────────────

    def _show_undated_events(self):
        body = self._screen("Events without a date", "These cannot appear on any day.")
        bar = _bar(body)
        _btn(bar, "Repair…", self._undated_repair)
        self._undated_tree = rs.make_tree(body, [("title", "Title", 280),
                                                 ("date", "event_date", 100),
                                                 ("by", "Created by", 100),
                                                 ("at", "Created", 160)])
        self._load_undated()

    def _load_undated(self):
        _a, _y, _d, ce = _rules()
        rows = self._cal_call(ce.undated_events) or []
        rs.fill(self._undated_tree, rows, lambda r: r["event_id"],
                lambda r: (r["title"], r["event_date"] or "(none)", r["created_by"],
                           r["created_at"]))

    def _undated_repair(self):
        n = len(self._undated_tree.get_children())
        if not n or not rs.confirm(self.root, f"Give the {n} event(s) that have a date their "
                                              "start? Events with no date at all are only "
                                              "deleted if you say so next."):
            return
        delete = rs.confirm(self.root, "Also delete the events that have no date at all?")
        _a, _y, _d, ce = _rules()
        result = self._cal_call(ce.repair_undated, self.who, delete, write=True)
        if result is not None:
            rs.info(self.root, f"Fixed {result['fixed']}, deleted {result['removed']}.")
            self._load_undated()

    def _show_calendar_admins(self):
        body = self._screen("Calendar administrators", "Admins and registrars always are.")
        bar = _bar(body)
        _btn(bar, "Add…", self._admin_add)
        _btn(bar, "Remove", self._admin_remove)
        self._admins_tree = rs.make_tree(body, [("user", "Username", 160),
                                                ("by", "Added by", 120),
                                                ("at", "Added", 160)])
        self._load_admins()

    def _load_admins(self):
        ca, _y, _d, _e = _rules()
        rows = self._cal_call(ca.admins) or []
        rs.fill(self._admins_tree, rows, lambda r: r["username"],
                lambda r: (r["username"], r["granted_by"], r["granted_at"]))

    def _admin_add(self):
        ca, _y, _d, _e = _rules()
        ans = rs.ask(self.root, "Add calendar administrator",
                     [rs.Field("user", "Member of staff", "staff", rs.staff_choices(self.root),
                               required=True)])
        if ans and self._cal_call(ca.grant, self.who, ans["user"], write=True) is not None:
            self._load_admins()

    def _admin_remove(self):
        user = rs.selected(self._admins_tree)
        if user and rs.confirm(self.root, f"Remove {user} as a calendar administrator?"):
            ca, _y, _d, _e = _rules()
            if self._cal_call(ca.revoke, self.who, user, write=True) is not None:
                self._load_admins()

    def _show_calendar_audit(self):
        body = self._screen("Calendar audit log")
        tree = rs.make_tree(body, [("at", "When", 150), ("actor", "Who", 100),
                                   ("entity", "What", 90), ("id", "Which", 120),
                                   ("action", "Action", 110), ("detail", "Detail", 360)])
        ca, _y, _d, _e = _rules()
        rows = self._cal_call(ca.history, limit=500) or []
        rs.fill(tree, rows, lambda r: r["audit_id"],
                lambda r: (r["at"], r["actor"], r["entity"], r["entity_id"], r["action"],
                           (r["detail"] or "")[:200]))
