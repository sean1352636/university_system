"""Student tabs of the Academic Integrity window: the notice, their own
work and released reports, a draft check, and their cases (their
statement, the evidence they may see) and appeals."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk

from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import review
from education_system.systems.university.application.integrity import plagiarism_checks as checks
from education_system.systems.university.application.integrity import choices
from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui import (  # noqa: E501
    case_view, pickers,
)
from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.report_view import (
    ReportWindow, _scrolled_text, highlight,
)
from education_system.systems.university.infrastructure.ui.record_screens import (
    RecordTab, ask_text, call, info, nice,
)


class NoticeTab(ttk.Frame):
    """How work is checked, and the student's acknowledgement."""

    def __init__(self, parent, portal):
        super().__init__(parent, padding=12)
        self.portal = portal
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", pady=(6, 0))
        self.ack_button = ttk.Button(bar, text="I have read this", command=self.acknowledge)
        self.ack_button.pack(side="left")
        self.state_label = ttk.Label(bar, text="")
        self.state_label.pack(side="left", padx=8)
        ttk.Label(self, text="How your work is checked", font=("Segoe UI", 13, "bold")).pack(
            anchor="w")
        frame, self.text = _scrolled_text(self, height=10)
        frame.pack(fill="both", expand=True, pady=6)
        self.refresh()

    def refresh(self):
        notice = call(self, access.notice) or {"text": "", "version": ""}
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", notice["text"])
        self.text.configure(state="disabled")
        done = call(self, access.has_acknowledged, self.portal.who, quiet=True)
        self.state_label.configure(text=f"Acknowledged (notice {notice['version']})" if done
                                   else "Not yet acknowledged")
        self.ack_button.configure(state="disabled" if done else "normal")

    def acknowledge(self):
        if call(self, access.acknowledge, self.portal.who, write=True) is not None:
            self.refresh()


class MyWorkTab(RecordTab):
    """The student's own submissions with their released reports."""

    columns = [("title", "Work", 260), ("module", "Module", 90), ("year", "Year", 70),
               ("score", "Similarity", 80), ("review", "Review", 100)]

    def load(self, conn, search, status):
        docs = checks.documents(conn, self.who)
        latest = {}
        for r in review.results(conn, self.who):
            latest.setdefault(r["document_id"], r)
        rows = []
        for d in docs:
            res = latest.get(d["id"])
            if search and search.lower() not in (d["title"] or "").lower():
                continue
            rows.append({**d, "result": res})
        return rows

    def values(self, row):
        res = row["result"]
        return [row["title"], row["module_code"], row["academic_year"],
                f"{float(res['similarity_score']):.0%}" if res else "—",
                nice(res["review_status"]) if res else "not checked / not released"]

    def fetch(self, conn, record_id):
        return self._rows.get(str(record_id))

    def render(self, record):
        res = record["result"]
        pairs = [("Module", record["module_code"]), ("Year", record["academic_year"]),
                 ("Submitted", record["submission_date"]), ("Words", record["word_count"])]
        if res:
            pairs += [("Similarity", f"{float(res['similarity_score']):.0%}"),
                      ("Band", res["status"]), ("Review", res["review_status"]),
                      ("Case", res["case_id"])]
        note = ("Reports are shown once released. A high match is reviewed by a member of staff "
                "first; nothing happens without that review.")
        self.detail.show(record["title"], [("", pairs), ("", note)])

    def actions(self, record):
        res = record["result"]
        if not res:
            return []
        return [("Open report", lambda: ReportWindow(self, self.who, res["id"]))]


class DraftCheckTab(ttk.Frame):
    """Check a draft before submitting. Nothing is stored."""

    def __init__(self, parent, portal):
        super().__init__(parent, padding=8)
        self.portal = portal
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(bar, text="Load file…", command=self.load_file).pack(side="left", padx=3)
        ttk.Button(bar, text="Check draft", command=self.check).pack(side="left", padx=3)
        ttk.Button(bar, text="Clear", command=self.clear).pack(side="left", padx=3)
        self.result_label = ttk.Label(bar, text="")
        self.result_label.pack(side="left", padx=10)
        top = ttk.Frame(self)
        top.pack(side="top", fill="x")
        ttk.Label(top, text="Module").pack(side="left")
        self.module = pickers.Picker(
            top, lambda: pickers.pairs(self, choices.modules, portal.who), width=34)
        self.module.pack(side="left", padx=4)
        ttk.Label(top, text=f"Paste your draft or load a file. You can check "
                            f"{checks.SELF_CHECKS_PER_DAY} drafts a day; drafts are not kept.",
                  foreground="#555555").pack(side="left", padx=8)
        frame, self.text = _scrolled_text(self, height=16)
        frame.pack(fill="both", expand=True, pady=4)
        self.file_type = "txt"

    def load_file(self):
        from education_system.systems.university.infrastructure.integrity import text_extract
        path = filedialog.askopenfilename(parent=self, title="Choose your draft",
                                          filetypes=[("Documents", "*.pdf *.docx *.txt *.md"),
                                                     ("All files", "*.*")])
        if not path:
            return
        try:
            text = text_extract.extract(path)
        except ValueError as exc:
            info(self, str(exc))
            return
        self.file_type = text_extract.file_type(path)
        self.clear()
        self.text.insert("1.0", text)

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.result_label.configure(text="")

    def check(self):
        draft = self.text.get("1.0", "end-1c")
        if not draft.strip():
            info(self, "Paste or load your draft first.")
            return
        if not self.module.value():
            info(self, "Choose the module so your draft is compared with work on that "
                       "module.")
            return
        found = call(self, checks.self_check, self.portal.who, text=draft,
                     file_type=self.file_type, module_code=self.module.value() or None,
                     write=True)
        if found is None:
            return
        highlight(self.text, draft, found["passages"])
        self.text.configure(state="normal")
        extra = ""
        if found.get("paraphrase_score"):
            extra += f" {found['paraphrase_score']:.0%} reworded from a source (orange)."
        if found.get("obfuscated"):
            extra += (f" {found['obfuscated']} disguised character(s) found — retype any text "
                      "pasted from elsewhere.")
        self.result_label.configure(
            text=f"{found['score']:.0%} of {found['words_checked']} words match existing work "
                 f"(yellow); {found['words_excluded']} quoted/reference words left out.{extra}")


class MyCasesTab(RecordTab):
    """The student's integrity cases, with appeals."""

    columns = [("id", "Case", 60), ("type", "Type", 100), ("stage", "Stage", 100),
               ("respond", "Respond by", 90), ("outcome", "Outcome", 160),
               ("deadline", "Appeal by", 90)]

    def load(self, conn, search, status):
        return review.cases(conn, self.who)

    def values(self, row):
        return [row["id"], nice(row["case_type"]), row["stage"],
                row.get("response_due") if row["stage"] in case_view.evidence.OPEN_STAGES
                else "", row["penalty"], row["appeal_deadline"]]

    def fetch(self, conn, record_id):
        return review.case(conn, self.who, int(record_id))

    def render(self, record):
        events = [f"{e['at'][:16]}  {nice(e['stage'])}: {e['note'] or ''}"
                  for e in record["events"]]
        appeals = [f"{a['lodged_at'][:10]} {nice(a['status'])}: {a['grounds']}"
                   + (f" — {a['decision_note']}" if a["decision_note"] else "")
                   for a in record["appeals"]]
        self.detail.show(f"Case {record['id']}", [
            ("", [("Type", record["case_type"]), ("Stage", record["stage"]),
                  ("Outcome", record["penalty"]), ("Appeal deadline", record["appeal_deadline"])]),
            ("Concern", record["description"] or "—"),
            *case_view.case_sections(record),
            ("History", events), ("Appeals", appeals)])

    def actions(self, record):
        found = []
        if record["stage"] in case_view.evidence.OPEN_STAGES:
            found.append(("Send my statement…", lambda: case_view.send_statement(self, record)))
        if case_view.file_items(record):
            found.append(("Open evidence file", lambda: case_view.open_evidence(
                self, self.who, record)))
            found.append(("Save evidence file…", lambda: case_view.open_evidence(
                self, self.who, record, save=True)))
        if record["stage"] == "decided":
            found.append(("Appeal…", lambda: self.appeal(record)))
        return found

    def appeal(self, record):
        grounds = ask_text(self, f"Appeal case {record['id']}",
                           "Your grounds for appeal (at least a sentence)")
        if grounds:
            self.write(review.lodge_appeal, self.who, record["id"], grounds,
                       done="Your appeal has been lodged.")
