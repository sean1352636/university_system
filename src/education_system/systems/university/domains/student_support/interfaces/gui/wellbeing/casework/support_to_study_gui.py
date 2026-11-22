"""Support to Study — staged cases (informal → formal → Fitness to Study
panel) with meetings, action plans, outcomes, letters and links.

Everything goes through ``domain/wellbeing/casework/support_to_study``,
which checks the signed-in user; support staff work every case, a student
sees their own (read-only).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk

from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    access,
)
from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    support_to_study as sts,
)
from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.casework.widgets import (
    Table,
    ask,
    form_dialog,
    info,
    open_file,
    show_error,
)

TITLE = "Support to Study"


class SupportToStudyPanel(ttk.Frame):
    COLUMNS = (("case_id", "#", 50), ("student_id", "Student", 90),
               ("student_name", "Name", 170), ("stage", "Stage", 60),
               ("status", "Status", 70), ("case_manager", "Case manager", 120),
               ("next_meeting", "Next meeting", 110), ("open_actions", "Open actions", 90),
               ("opened_at", "Opened", 140))

    def __init__(self, master, auth):
        super().__init__(master, padding=8)
        self.auth = auth
        self.case = None
        try:
            self.staff = access.support_scope(auth) is None
        except PermissionError as exc:
            ttk.Label(self, text=str(exc), wraplength=900).pack(padx=20, pady=20)
            return
        self._build()
        self.refresh()

    # ------------------------------------------------------------- layout
    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X)
        ttk.Label(top, text=TITLE, font=("Arial", 13, "bold")).pack(side=tk.LEFT)
        ttk.Label(top, text=("Stage 1 informal · Stage 2 formal · Stage 3 Fitness to Study "
                             "panel"), foreground="#555555").pack(side=tk.LEFT, padx=10)
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=4)
        self.show_closed = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Show closed", variable=self.show_closed,
                        command=self.refresh).pack(side=tk.LEFT)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side=tk.LEFT, padx=4)
        if self.staff:
            ttk.Button(bar, text="Open case…", command=self._open_case).pack(side=tk.LEFT, padx=4)
            ttk.Button(bar, text="Overdue actions", command=self._overdue).pack(side=tk.LEFT)
        pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        pane.pack(fill=tk.BOTH, expand=True)
        self.table = Table(pane, self.COLUMNS, height=8)
        self.table.bind_open(self._load_selected)
        self.table.tree.bind("<<TreeviewSelect>>", lambda _e: self._load_selected())
        pane.add(self.table, weight=1)
        detail = ttk.Frame(pane)
        pane.add(detail, weight=2)
        self.header = tk.StringVar(value="Select a case.")
        ttk.Label(detail, textvariable=self.header, font=("Arial", 11, "bold")).pack(
            anchor="w", pady=(6, 2))
        if self.staff:
            actions = ttk.Frame(detail)
            actions.pack(fill=tk.X)
            for label, cmd in (("Schedule meeting…", self._schedule), ("Record meeting…",
                               self._record_meeting), ("Add action…", self._add_action),
                               ("Update action…", self._update_action),
                               ("Record outcome…", self._outcome), ("Escalate…", self._escalate),
                               ("Letter…", self._letter), ("Link record…", self._link),
                               ("Case manager…", self._manager), ("Close case…", self._close)):
                ttk.Button(actions, text=label, command=cmd).pack(side=tk.LEFT, padx=2, pady=2)
        book = ttk.Notebook(detail)
        book.pack(fill=tk.BOTH, expand=True, pady=4)
        self.summary = self._text_tab(book, "Summary")
        self.meetings = Table(book, (("meeting_id", "#", 50), ("stage", "Stage", 50),
                                     ("meeting_date", "Date", 100), ("meeting_time", "Time", 60),
                                     ("location", "Where", 140), ("status", "Status", 90),
                                     ("panel_members", "Panel", 180), ("summary", "Summary", 400)))
        book.add(self.meetings, text="Meetings")
        self.actions = Table(book, (("action_id", "#", 50), ("stage", "Stage", 50),
                                    ("action_text", "Action", 420), ("owner", "Owner", 110),
                                    ("due_date", "Due", 100), ("status", "Status", 80)))
        book.add(self.actions, text="Action plan")
        self.outcomes = Table(book, (("outcome_id", "#", 50), ("stage", "Stage", 50),
                                     ("outcome_type", "Outcome", 190), ("decision", "Decision", 420),
                                     ("review_date", "Review", 100),
                                     ("lifecycle_history_id", "Lifecycle #", 90)))
        book.add(self.outcomes, text="Outcomes")
        self.letters = Table(book, (("letter_id", "#", 50), ("kind", "Letter", 120),
                                    ("created_at", "Written", 150), ("path", "File", 520)))
        self.letters.bind_open(self._open_letter)
        book.add(self.letters, text="Letters")
        self.links = Table(book, (("link_id", "#", 50), ("kind", "Record", 180),
                                  ("ref_id", "Number", 90), ("note", "Note", 400)))
        book.add(self.links, text="Linked records")

    @staticmethod
    def _text_tab(book, label):
        frame = ttk.Frame(book)
        book.add(frame, text=label)
        box = scrolledtext.ScrolledText(frame, height=10, wrap="word", state="disabled")
        box.pack(fill=tk.BOTH, expand=True)
        return box

    # ------------------------------------------------------------- data
    def refresh(self):
        try:
            rows = sts.list_cases(self.auth, include_closed=self.show_closed.get())
        except Exception as exc:
            show_error(self, exc, TITLE)
            return
        self.table.load(rows, empty_text=None if rows else "No cases")
        if self.case:
            self._load(self.case["case_id"])

    def _load_selected(self):
        row = self.table.selected()
        if row and row.get("case_id") not in (None, "No cases"):
            self._load(row["case_id"])

    def _load(self, case_id):
        try:
            self.case = sts.case_detail(self.auth, case_id)
        except Exception as exc:
            self.case = None
            show_error(self, exc, TITLE)
            return
        c = self.case
        self.header.set(f"Case #{c['case_id']} — {c['student_name']} ({c['student_id']}) — "
                        f"{c['stage_label']} — {c['status']}")
        lines = [f"Opened {c['opened_at']} by {c['opened_by']}; case manager "
                 f"{c.get('case_manager') or '—'}", "", "Concern:", c.get("reason") or "", "",
                 "Stage history:"]
        lines += [f"  {h['changed_at']}: stage {h['from_stage'] or '—'} → {h['to_stage']} "
                  f"({h['changed_by']}) {h.get('reason') or ''}" for h in c["history"]]
        if c.get("closed_at"):
            lines += ["", f"Closed {c['closed_at']} by {c['closed_by']}: {c['closed_reason']}"]
        self.summary.config(state="normal")
        self.summary.delete("1.0", tk.END)
        self.summary.insert("1.0", "\n".join(lines))
        self.summary.config(state="disabled")
        self.meetings.load(c["meetings"])
        self.actions.load(c["actions"])
        self.outcomes.load([dict(o, outcome_type=sts.OUTCOME_LABELS.get(o["outcome_type"],
                                                                         o["outcome_type"]))
                            for o in c["outcomes"]])
        self.letters.load(c["letters"])
        self.links.load([dict(link, kind=sts.LINK_KINDS.get(link["kind"], ("", "", link["kind"]))[2])
                         for link in c["links"]])

    def _need_case(self):
        if not self.case:
            info(self, "Select a case first.", TITLE)
            return None
        return self.case["case_id"]

    def _run(self, fn, *args, done=None, **kwargs):
        try:
            result = fn(self.auth, *args, **kwargs)
        except Exception as exc:
            show_error(self, exc, TITLE)
            return None
        if done:
            info(self, done, TITLE)
        self.refresh()
        return result

    # ------------------------------------------------------------- actions
    def _open_case(self):
        def save(v):
            case_id = sts.open_case(self.auth, v["student_id"], v["reason"],
                                    stage=int(v["stage"]), case_manager=v["manager"] or None)
            self.after(10, lambda: self._load(case_id))
            self.after(20, self.refresh)
        form_dialog(self, "Open a Support to Study case", [
            ("student_id", "Student number", "entry", ""),
            ("stage", "Start at stage", ("1", "2", "3"), "1"),
            ("manager", "Case manager (username; blank = you)", "entry", ""),
            ("reason", "The concern", "text", "")], save)

    def _overdue(self):
        try:
            rows = sts.overdue_actions(self.auth)
        except Exception as exc:
            show_error(self, exc, TITLE)
            return
        info(self, "\n".join(f"Case #{r['case_id']} ({r['student_id']}): {r['action_text']} — "
                             f"due {r['due_date']}" for r in rows) or "No overdue actions.", TITLE)

    def _schedule(self):
        case_id = self._need_case()
        if case_id is None:
            return
        form_dialog(self, "Schedule a meeting", [
            ("date", "Date (YYYY-MM-DD)", "entry", ""), ("time", "Time (HH:MM)", "entry", ""),
            ("location", "Where", "entry", ""), ("attendees", "Attendees", "entry", ""),
            ("panel", "Panel members (stage 3, comma-separated)", "entry", "")],
            lambda v: self._run(sts.schedule_meeting, case_id, v["date"], meeting_time=v["time"],
                                location=v["location"], attendees=v["attendees"],
                                panel_members=v["panel"]))

    def _record_meeting(self):
        row = self.meetings.selected()
        if not row:
            info(self, "Select a meeting on the Meetings tab.", TITLE)
            return
        form_dialog(self, f"Meeting #{row['meeting_id']}", [
            ("status", "Status", sts.MEETING_STATUSES, "held"),
            ("attended", "Student attended", "check", True),
            ("supporter", "Supporter who came with them", "entry", row.get("supporter") or ""),
            ("summary", "What was discussed and agreed", "text", row.get("summary") or "")],
            lambda v: self._run(sts.record_meeting, row["meeting_id"], status=v["status"],
                                student_attended=v["attended"], summary=v["summary"],
                                supporter=v["supporter"]))

    def _add_action(self):
        case_id = self._need_case()
        if case_id is None:
            return
        form_dialog(self, "Add an action", [
            ("text", "Action", "text", ""), ("owner", "Who (student / tutor / a name)", "entry",
                                               "student"),
            ("due", "Due (YYYY-MM-DD)", "entry", "")],
            lambda v: self._run(sts.add_action, case_id, v["text"], owner=v["owner"],
                                due_date=v["due"]))

    def _update_action(self):
        row = self.actions.selected()
        if not row:
            info(self, "Select an action on the Action plan tab.", TITLE)
            return
        form_dialog(self, f"Action #{row['action_id']}", [
            ("status", "Status", sts.ACTION_STATUSES, row.get("status")),
            ("notes", "Notes", "text", row.get("notes") or "")],
            lambda v: self._run(sts.update_action, row["action_id"], v["status"], v["notes"]))

    def _outcome(self):
        case_id = self._need_case()
        if case_id is None:
            return
        choices = tuple(sts.OUTCOME_LABELS[o] for o in sts.OUTCOMES[self.case["stage"]])
        by_label = {sts.OUTCOME_LABELS[o]: o for o in sts.OUTCOMES[self.case["stage"]]}

        def save(v):
            kind = by_label[v["outcome"]]
            if kind in sts.INTERRUPTING and not ask(
                    self, "This interrupts the student's studies through the student "
                    "lifecycle (finance, visa, library and modules are told). Continue?", TITLE):
                raise ValueError("Not recorded.")
            sts.record_outcome(self.auth, case_id, kind, v["decision"],
                               review_date=v["review"], effective_date=v["effective"] or None,
                               expected_return_date=v["return"] or None)
            self.after(10, self.refresh)
        form_dialog(self, f"Outcome of {self.case['stage_label']}", [
            ("outcome", "Outcome", choices, choices[0]),
            ("decision", "Decision and reasons", "text", ""),
            ("review", "Review date (YYYY-MM-DD)", "entry", ""),
            ("effective", "Interruption from (YYYY-MM-DD; blank = today)", "entry", ""),
            ("return", "Expected return (YYYY-MM-DD)", "entry", "")], save, size="620x520")

    def _escalate(self):
        case_id = self._need_case()
        if case_id is None:
            return
        form_dialog(self, "Move to the next stage", [("reason", "Why", "text", "")],
                    lambda v: self._run(sts.escalate, case_id, v["reason"]))

    def _letter(self):
        case_id = self._need_case()
        if case_id is None:
            return
        kinds = {"Meeting invitation (selected or latest meeting)": "invitation",
                 "Action plan": "action_plan", "Outcome (latest)": "outcome"}

        def save(v):
            kind = kinds[v["kind"]]
            ref = None
            if kind == "invitation" and self.meetings.selected():
                ref = self.meetings.selected()["meeting_id"]
            path = sts.generate_letter(self.auth, case_id, kind, ref)
            self.after(10, self.refresh)
            if ask(self, f"Letter written to\n{path}\n\nOpen it now?", TITLE):
                open_file(path)
        form_dialog(self, "Write a letter", [("kind", "Letter", tuple(kinds), None)], save,
                    size="520x180")

    def _open_letter(self):
        row = self.letters.selected()
        if row and row.get("path"):
            try:
                open_file(row["path"])
            except Exception as exc:
                show_error(self, exc, TITLE)

    def _link(self):
        case_id = self._need_case()
        if case_id is None:
            return
        labels = {v[2]: k for k, v in sts.LINK_KINDS.items()}
        form_dialog(self, "Link a record", [
            ("kind", "Record", tuple(labels), None), ("ref", "Its number", "entry", ""),
            ("note", "Note", "entry", "")],
            lambda v: self._run(sts.link, case_id, labels[v["kind"]], v["ref"], v["note"]))

    def _manager(self):
        case_id = self._need_case()
        if case_id is None:
            return
        form_dialog(self, "Case manager", [("user", "Username", "entry",
                                            self.case.get("case_manager") or "")],
                    lambda v: self._run(sts.set_case_manager, case_id, v["user"]),
                    size="420x160")

    def _close(self):
        case_id = self._need_case()
        if case_id is None:
            return
        form_dialog(self, "Close the case", [("reason", "Reason", "text", "")],
                    lambda v: self._run(sts.close_case, case_id, v["reason"]))
