"""Integrity officer tabs: cases (stages, statements, evidence, previous
cases and the recommended outcomes, decisions, appeals), settings (and the
external search key), records (export, erase, retention purge, the daily
jobs), roles and the audit.

The cases tab also serves a member of staff for the cases they raised:
they can read them and add evidence; everything else is the officer's."""

from __future__ import annotations

import json
from tkinter import filedialog, ttk

from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import records
from education_system.systems.university.application.integrity import review
from education_system.systems.university.application.integrity import choices
from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui import (  # noqa: E501
    case_view, pickers,
)
from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.report_view import (
    ReportWindow,
)
from education_system.systems.university.infrastructure.ui.record_screens import (
    Detail, Field, RecordTab, ask, ask_pick, ask_text, call, confirm, fill, info, make_tree,
    nice,
)

OUTCOME_CHOICES = [(k, label) for k, (label, _p) in review.OUTCOMES.items()]


class CasesTab(RecordTab):
    columns = [("id", "Case", 50), ("student", "Student", 90), ("type", "Type", 100),
               ("stage", "Stage", 90), ("source", "Raised from", 90),
               ("outcome", "Outcome", 160), ("opened", "Opened", 90)]
    statuses = review.STAGES

    def new_actions(self):
        return [("Open a case…", self.open_case)] if self.portal.is_officer else []

    def load(self, conn, search, status):
        rows = review.cases(conn, self.who, stage=status)
        if search:
            rows = [r for r in rows if search.lower() in
                    f"{r['student_id']} {r['description'] or ''}".lower()]
        return rows

    def values(self, row):
        return [row["id"], row["student_id"], nice(row["case_type"]), row["stage"],
                nice(row.get("source")), row["penalty"], (row["created_at"] or "")[:10]]

    def fetch(self, conn, record_id):
        return review.case(conn, self.who, int(record_id))

    def render(self, record):
        events = [f"{e['at'][:16]}  {nice(e['stage'])} ({e['actor']}): {e['note'] or ''}"
                  for e in record["events"]]
        appeals = [f"#{a['appeal_id']} {a['lodged_at'][:10]} {nice(a['status'])}: {a['grounds']}"
                   + (f" — {a['decided_by']}: {a['decision_note']}" if a["decided_by"] else "")
                   for a in record["appeals"]]
        sections = [
            ("", [("Student", record["student_id"]), ("Type", record["case_type"]),
                  ("Raised from", record.get("source")), ("Module", record.get("module_code")),
                  ("Severity", record.get("severity")),
                  ("Stage", record["stage"]), ("Status", record["status"]),
                  ("Outcome", record["penalty"]), ("Decided by", record["decided_by"]),
                  ("Offence number", record.get("offence_number")),
                  ("Outside the recommended outcomes", record.get("tariff_departure")),
                  ("Mark before penalty", record["grade_before"]),
                  ("Appeal deadline", record["appeal_deadline"]),
                  ("Similarity result", record["result_id"]),
                  ("Submission", record["submission_id"])]),
            ("Concern", record["description"] or "—")]
        if "recommended" in record:
            rec = record["recommended"]
            sections.append(("Recommended outcomes", [
                f"Offence {rec['offence_number']}: "
                + ", ".join(review.OUTCOMES[o][0] for o in rec["outcomes"])]))
            sections.append(("Previous cases", [
                f"Case {c['id']} ({(c['created_at'] or '')[:10]}) {nice(c['case_type'])}: "
                f"{c['penalty'] or nice(c['stage'])}" + (" — upheld" if c["upheld"] else "")
                for c in record.get("history") or []] or ["None"]))
        sections += case_view.case_sections(record)
        sections += [("History", events), ("Appeals", appeals or ["None"])]
        self.detail.show(f"Case {record['id']}", sections)

    def actions(self, record):
        found = []
        if record["result_id"]:
            found.append(("Similarity report", lambda: ReportWindow(self, self.who,
                                                                     record["result_id"])))
        stage = record["stage"]
        if case_view.file_items(record):
            found.append(("Open evidence file", lambda: case_view.open_evidence(
                self, self.who, record)))
            found.append(("Save evidence file…", lambda: case_view.open_evidence(
                self, self.who, record, save=True)))
        if stage != "closed":
            found.append(("Add evidence…", lambda: case_view.add_evidence(
                self, record, self.portal.is_officer)))
        if not self.portal.is_officer:
            return found
        if record.get("evidence") and any(not e.get("removed_at") for e in record["evidence"]):
            found.append(("Withdraw evidence…", lambda: case_view.withdraw_evidence(self, record)))
        if stage in ("referred", "investigating", "meeting"):
            found.append(("Change statement deadline…",
                          lambda: case_view.change_deadline(self, record)))
        if stage == "referred":
            found.append(("Start investigating…", lambda: self.advance(record, "investigating")))
        if stage in ("referred", "investigating"):
            found.append(("Arrange meeting…", lambda: self.advance(record, "meeting")))
        if stage not in ("decided", "closed"):
            found.append(("Decide outcome…", lambda: self.decide(record)))
        for appeal in record["appeals"]:
            if appeal["status"] == "lodged":
                found.append((f"Decide appeal #{appeal['appeal_id']}…",
                              lambda a=appeal: self.decide_appeal(a)))
        if stage == "decided":
            found.append(("Close case", lambda: self.close(record)))
        return found

    def open_case(self):
        values = ask(self, "Open an integrity case", [
            pickers.module_field(self, self.who, label="Module (narrows the lists)"),
            pickers.student_field(self, self.who, label="Student", required=True,
                                  module_key="module_code"),
            Field("case_type", "Type", "combo", list(review.CASE_TYPES), required=True),
            pickers.assignment_field(self, self.who),
            Field("description", "The concern", "multiline", required=True)],
            {"case_type": "plagiarism"})
        if values:
            assignment = values["assignment_id"] if values["assignment_id"] not in (
                "", None) else None
            self.write(review.open_case, self.who, student_id=values["student_id"],
                       case_type=values["case_type"], description=values["description"],
                       assignment_id=assignment, module_code=values["module_code"] or None,
                       done="Case opened and the student told.")

    def advance(self, record, stage):
        note = ask_text(self, f"Case {record['id']}: {nice(stage)}",
                        "Details (for a meeting: date, time, place)")
        if note:
            self.write(review.advance, self.who, record["id"], stage, note)

    def decide(self, record):
        rec = record.get("recommended") or {"offence_number": "?", "outcomes": []}
        hint = (f"Offence {rec['offence_number']}; recommended: "
                + ", ".join(review.OUTCOMES[o][0] for o in rec["outcomes"]))
        values = ask(self, f"Decide case {record['id']}", [
            Field("outcome", "Outcome", "combo", OUTCOME_CHOICES, required=True, hint=hint),
            Field("note", "Reasons (sent to the student)", "multiline", required=True),
            Field("departure", "Reason for going outside the recommended outcomes (only if you "
                               "do)", "multiline")])
        if values and confirm(self, "Record this outcome? A mark penalty is applied to the "
                                    "submission now."):
            self.write(review.decide, self.who, record["id"], values["outcome"],
                       values["note"], departure_reason=values["departure"] or None,
                       done="Decision recorded and the student told.")

    def decide_appeal(self, appeal):
        values = ask(self, f"Appeal #{appeal['appeal_id']}", [
            Field("result", "Decision", "combo", [("upheld", "Uphold (withdraw the outcome)"),
                                                  ("rejected", "Reject")], required=True),
            Field("note", "Reasons (sent to the student)", "multiline", required=True)])
        if values:
            self.write(review.decide_appeal, self.who, appeal["appeal_id"],
                       values["result"] == "upheld", values["note"], done="Appeal decided.")

    def close(self, record):
        note = ask_text(self, f"Close case {record['id']}", "Closing note", required=False)
        if note is not None:
            self.write(review.close, self.who, record["id"], note)


class SettingsTab(ttk.Frame):
    LABELS = {
        "auto_check": "Check submissions automatically (1/0)",
        "review_threshold": "Default review threshold (0–1)",
        "high_threshold": "High band from (0–1)",
        "shingle_words": "Words in a matching run (3–15)",
        "release_after_review": "Hold high matches until reviewed (1/0)",
        "appeal_days": "Days allowed to appeal",
        "retention_years": "Years submitted text is kept",
        "statement_days": "Days a student has to give their account",
        "review_reminder_days": "Remind module staff of unreviewed reports after (days)",
        "stage_reminder_days": "Remind officers of cases with no progress after (days)",
        "auto_close": "Close decided cases when the appeal period ends (1/0)",
        "paraphrase_threshold": "Review when this share is reworded (0–1)",
        "obfuscation_chars": "Review when this many disguised characters are found",
        "ai_auto_check": "Take AI-writing readings of submissions (1/0)",
        "ai_min_words": "Fewest words for an AI-writing reading",
        "ai_review_threshold": "Strength at which a reading waits for review (0–1)",
        "external_checks": "Allow searching published sources (1/0; update the notice first)",
        "external_max_queries": "Phrases searched per document (1–20)",
        "notice_version": "Student notice version",
        "notice_text": "Student notice text",
    }

    def __init__(self, parent, portal):
        super().__init__(parent, padding=10)
        self.portal = portal
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(bar, text="Change a setting…", command=self.edit).pack(side="left")
        if portal.who.is_admin:
            ttk.Button(bar, text="Set CORE API key…", command=self.set_key).pack(
                side="left", padx=4)
        self.detail = Detail(self)
        self.detail.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self):
        from education_system.systems.university.infrastructure.integrity import external_sources
        values = {k: call(self, access.setting, k, quiet=True) for k in access.SETTINGS}
        self.detail.show("Integrity settings", [
            ("", [(self.LABELS.get(k, k), v) for k, v in values.items()]),
            ("Published-source search", [("CORE API key", "set" if external_sources.configured()
                                          else "not set")])])

    def set_key(self):
        from education_system.systems.university.infrastructure.integrity import external_sources
        key = ask_text(self, "CORE API key", "API key from core.ac.uk (kept in the owner-only "
                                             "secrets file)", multiline=False)
        if key:
            path = external_sources.save_core_key(key)
            call(self, access.audit, self.portal.who.username, "setting", "core_api_key",
                 "changed", write=True)
            info(self, f"Saved to {path}.")
            self.refresh()

    def edit(self):
        values = ask(self, "Change a setting", [
            Field("key", "Setting", "combo", list(self.LABELS.items()), required=True),
            Field("value", "New value", "multiline", required=True)])
        if values and call(self, access.set_setting, self.portal.who, values["key"],
                           values["value"], write=True) is not None:
            self.refresh()


class RecordsTab(ttk.Frame):
    """Subject access export, erasure and the retention purge."""

    def __init__(self, parent, portal):
        super().__init__(parent, padding=10)
        self.portal = portal
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(bar, text="Export a student's records…", command=self.export).pack(
            side="left", padx=3)
        if portal.who.is_admin:
            ttk.Button(bar, text="Erase a student's records…", command=self.erase).pack(
                side="left", padx=3)
        ttk.Button(bar, text="Run retention purge now", command=self.purge).pack(
            side="left", padx=3)
        ttk.Button(bar, text="Run daily jobs now", command=self.daily).pack(side="left", padx=3)
        self.detail = Detail(self)
        self.detail.pack(fill="both", expand=True)
        self.detail.show("Records", [("", (
            "Export gives everything held about a student's work as a JSON file (a subject "
            "access request). Erasure removes their documents and results; work that is "
            "evidence in a case is kept. The retention purge removes the text of submissions "
            "older than the retention period, except evidence in a case that is not closed."))])

    def _student(self, title):
        picked = ask_pick(self, title, "Student",
                          lambda: pickers.pairs(self, choices.students, self.portal.who))
        return None if picked in (None, "") else str(picked)

    def export(self):
        student = self._student("Export a student's records")
        if not student:
            return
        data = call(self, records.export, self.portal.who, student.strip(), write=True)
        if data is None:
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json",
                                            initialfile=f"integrity_{student.strip()}.json")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, default=str)
            info(self, f"Saved {len(data['documents'])} document(s) and "
                       f"{len(data['cases'])} case(s).")

    def erase(self):
        student = self._student("Erase a student's records")
        if not student or not confirm(self, f"Erase the integrity records of {student}? "
                                            "This cannot be undone."):
            return
        done = call(self, records.erase, self.portal.who, student.strip(), write=True)
        if done is not None:
            info(self, f"Removed {done['removed']} document(s); kept "
                       f"{len(done['kept_as_evidence'])} as case evidence.")

    def purge(self):
        if not confirm(self, "Remove the text of every submission past the retention period?"):
            return
        count = call(self, records.purge, write=True)
        if count is not None:
            info(self, f"Removed the text of {count if count is not True else 0} submission(s).")

    def daily(self):
        """Purge, reminders, automatic closing and check retries, each on its
        own connection (as the daily worker runs them)."""
        if not confirm(self, "Run the daily integrity jobs now? Reminder e-mails may be sent."):
            return
        from education_system.systems.university.infrastructure.integrity import retention_worker
        report = retention_worker.run_once()
        jobs = report.get("jobs") or {}
        retries = report.get("retries") or {}
        info(self, f"Text removed from {report.get('purged') or 0} submission(s); "
                   f"{jobs.get('reminders', 0)} reminder(s) sent; {jobs.get('closed', 0)} case(s) "
                   f"closed; {retries.get('retried', 0)} failed check(s) retried.")


class RolesTab(ttk.Frame):
    def __init__(self, parent, portal):
        super().__init__(parent, padding=10)
        self.portal = portal
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(bar, text="Grant…", command=self.grant).pack(side="left", padx=3)
        ttk.Button(bar, text="Revoke selected", command=self.revoke).pack(side="left", padx=3)
        self.tree = make_tree(self, [("username", "Username", 160), ("role", "Role", 100),
                                     ("by", "Granted by", 120), ("at", "Granted", 140)])
        self.refresh()

    def refresh(self):
        rows = call(self, access.roles) or []
        fill(self.tree, rows, lambda r: f"{r['username']}|{r['role']}",
             lambda r: [r["username"], r["role"], r["granted_by"], r["granted_at"]])

    def grant(self):
        values = ask(self, "Grant an integrity role", [
            Field("username", "Member of staff", "pick",
                  lambda: pickers.pairs(self, choices.staff, self.portal.who), required=True,
                  filter=True),
            Field("role", "Role", "combo", [("reviewer", "Reviewer (any module)"),
                                            ("officer", "Integrity officer")], required=True)])
        if values and call(self, access.grant, self.portal.who, values["username"],
                           values["role"], write=True) is not None:
            self.refresh()

    def revoke(self):
        sel = self.tree.selection()
        if not sel:
            return
        username, role = sel[0].split("|")
        if confirm(self, f"Revoke {role} from {username}?") and call(
                self, access.revoke, self.portal.who, username, role, write=True) is not None:
            self.refresh()


class AuditTab(ttk.Frame):
    def __init__(self, parent, portal):
        super().__init__(parent, padding=10)
        self.portal = portal
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left")
        self.tree = make_tree(self, [("at", "When", 140), ("actor", "Who", 110),
                                     ("entity", "What", 90), ("id", "Id", 70),
                                     ("action", "Action", 120), ("detail", "Detail", 380)])
        self.refresh()

    def refresh(self):
        rows = call(self, access.recent_audit, self.portal.who) or []
        fill(self.tree, rows, lambda r: r["audit_id"],
             lambda r: [r["at"], r["actor"], r["entity"], r["entity_id"], r["action"],
                        r["detail"]])
