"""Staff tabs of the Academic Integrity window: the review queue, the
documents on modules they review (run checks, add references and
templates; officers also import external texts), automatic checks that
failed, module settings and statistics. The AI-writing tab is in
``ai_writing``."""

from __future__ import annotations

from tkinter import filedialog, ttk

from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import ai as integrity_ai
from education_system.systems.university.application.integrity import review
from education_system.systems.university.application.integrity import choices
from education_system.systems.university.application.integrity import plagiarism_checks as checks
from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui import (  # noqa: E501
    pickers,
)
from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.report_view import (
    ReportWindow,
)
from education_system.systems.university.infrastructure.ui.record_screens import (
    Detail, Field, RecordTab, ask, ask_text, call, confirm, info, nice,
)

REVIEW_STATES = ("pending", "not_needed", "no_concern", "false_positive", "referred")


class ReviewQueueTab(RecordTab):
    """Results on modules the person reviews; waiting ones first."""

    columns = [("id", "Result", 60), ("title", "Work", 210), ("student", "Student", 90),
               ("module", "Module", 80), ("score", "Score", 60), ("reworded", "Reworded", 70),
               ("disguised", "Disguised", 70), ("band", "Band", 80), ("review", "Review", 90)]
    statuses = REVIEW_STATES

    def load(self, conn, search, status):
        rows = review.results(conn, self.who, review_status=status)
        if search:
            needle = search.lower()
            rows = [r for r in rows if needle in " ".join(
                str(r.get(k) or "") for k in ("title", "student_id", "module_code")).lower()]
        return sorted(rows, key=lambda r: (r["review_status"] != "pending", -r["id"]))

    def values(self, row):
        return [row["id"], row["title"], row["student_id"], row["module_code"],
                f"{float(row['similarity_score']):.0%}",
                f"{float(row.get('paraphrase_score') or 0):.0%}",
                row.get("obfuscated_chars") or 0, row["status"], row["review_status"]]

    def fetch(self, conn, record_id):
        return self._rows.get(str(record_id))

    def render(self, record):
        self.detail.show(f"Result {record['id']}", [("", [
            ("Work", record["title"]), ("Student", record["student_id"]),
            ("Module", record["module_code"]), ("Assignment", record["assignment_id"]),
            ("Checked", record["check_date"]),
            ("Similarity", f"{float(record['similarity_score']):.0%}"),
            ("Reworded", f"{float(record.get('paraphrase_score') or 0):.0%}"),
            ("Disguised characters", record.get("obfuscated_chars") or 0),
            ("Band", record["status"]), ("Review", record["review_status"]),
            ("Case", record["case_id"]),
            ("Released to student", "yes" if record["released_to_student"] else "no")])])

    def actions(self, record):
        return [("Open report / review", lambda: ReportWindow(self, self.who, record["id"],
                                                               on_change=self.reload))]


class DocumentsTab(RecordTab):
    """Documents on the person's modules, without their text. "Filter…"
    narrows the list (file type, word count, dates, module, student,
    author); "Export…" saves the filtered list as CSV (no document text)."""

    columns = [("id", "Doc", 50), ("title", "Title", 240), ("kind", "Kind", 80),
               ("student", "Student", 90), ("module", "Module", 80), ("year", "Year", 70),
               ("words", "Words", 60), ("type", "Type", 50)]
    statuses = checks.KINDS
    FILTER_FIELDS = (("module_code", "Module code", "text", ""),
                     ("file_type", "File type", "text", "e.g. pdf, docx, py"),
                     ("min_words", "Minimum words", "number", ""),
                     ("max_words", "Maximum words", "number", ""),
                     ("date_from", "Submitted from", "date", ""),
                     ("date_to", "Submitted to", "date", ""),
                     ("student", "Student / candidate", "text", "as shown in the list"),
                     ("author", "Added by (username)", "text", "references and templates"))

    def __init__(self, parent, portal):
        self.filters = {}
        super().__init__(parent, portal)

    def extra_toolbar(self, bar):
        ttk.Button(bar, text="Filter…", command=self.edit_filters).pack(side="left", padx=4)
        ttk.Button(bar, text="Clear filters", command=self.clear_filters).pack(side="left",
                                                                              padx=2)
        ttk.Button(bar, text="Export…", command=self.export).pack(side="left", padx=4)
        self.filter_label = ttk.Label(bar, text="", foreground="#555555")
        self.filter_label.pack(side="left", padx=6)

    def _active(self):
        return {k: v for k, v in self.filters.items() if v not in (None, "")}

    def _show_filters(self):
        active = self._active()
        self.filter_label.configure(text=("Filtered: " + ", ".join(
            f"{k.replace('_', ' ')} {v}" for k, v in active.items())) if active else "")

    def _filter_fields(self):
        """The filter form: dropdowns of what this person can see, numbers
        for the word counts, date pickers for the dates."""
        who = self.who
        source = {
            "module_code": lambda: pickers.pairs(self, choices.modules, who),
            "file_type": lambda: pickers.pairs(self, choices.file_types, who),
            "student": lambda: pickers.pairs(self, choices.document_students, who),
            "author": lambda: pickers.pairs(self, choices.document_authors, who),
        }
        fields = []
        for key, label, kind, hint in self.FILTER_FIELDS:
            if key in source:
                fields.append(Field(key, label, "pick", source[key], filter=True,
                                    hint="" if key != "student" else "as shown in the list"))
            elif kind == "date":
                fields.append(Field(key, label, "datepick"))
            else:
                fields.append(Field(key, label, kind, hint=hint))
        return fields

    def edit_filters(self):
        values = ask(self, "Filter documents", self._filter_fields(), self.filters, columns=2)
        if values is None:
            return
        for key in ("min_words", "max_words"):
            if values.get(key) not in (None, ""):
                values[key] = int(values[key])
        self.filters = values
        self._show_filters()
        self.refresh()

    def clear_filters(self):
        self.filters = {}
        self._show_filters()
        self.refresh()

    def export(self):
        filters = dict(self._active())
        if self.status.get():
            filters["kind"] = self.status.get()
        if self.search.get().strip():
            filters["search"] = self.search.get().strip()
        text = call(self, checks.export_documents, self.who, write=True, **filters)
        if text is None:
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".csv",
                                            initialfile="integrity_documents.csv",
                                            filetypes=[("CSV", "*.csv")])
        if path:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
            info(self, f"Saved {max(0, text.count(chr(10)) - 1)} document(s) to {path}.")

    def new_actions(self):
        found = [("Add reference…", lambda: self.add("reference")),
                 ("Add template…", lambda: self.add("template"))]
        if self.portal.is_officer:
            found.append(("Import external texts…", self.import_external))
        return found

    def load(self, conn, search, status):
        return checks.documents(conn, self.who, search=search, kind=status or None,
                                **self._active())

    def values(self, row):
        return [row["id"], row["title"], row["kind"], row["student_id"], row["module_code"],
                row["academic_year"], row["word_count"], row["file_type"]]

    def fetch(self, conn, record_id):
        return self._rows.get(str(record_id))

    def render(self, record):
        self.detail.show(record["title"], [("", [
            ("Kind", record["kind"]), ("Student", record["student_id"]),
            ("Module", record["module_code"]), ("Assignment", record["assignment_id"]),
            ("Submission", record["submission_id"]), ("Year", record["academic_year"]),
            ("File type", record["file_type"]), ("Words", record["word_count"]),
            ("Added by", record.get("author")), ("Submitted", record.get("submission_date")),
            ("Source", record.get("source_url")),
            ("Text", "removed under the retention policy" if record["purged"] else "held")])])

    def actions(self, record):
        found = []
        if record["kind"] == "submission" and not record["purged"]:
            found.append(("Run check", lambda: self.run_check(record)))
        if self.portal.is_officer:
            found.append(("Delete", lambda: self.delete(record)))
        return found

    def import_external(self):
        """Known external texts (essay-mill samples, widely copied articles)
        that every later check compares against."""
        from education_system.systems.university.application.integrity import (
            external as integrity_external,
        )
        from education_system.systems.university.infrastructure.integrity import text_extract
        paths = filedialog.askopenfilenames(parent=self, title="Choose external texts",
                                            filetypes=[("Documents", "*.pdf *.docx *.txt *.md"),
                                                       ("All files", "*.*")])
        if not paths:
            return
        url = ask_text(self, "External texts", "Where they come from (web address, optional)",
                       required=False, multiline=False)
        if url is None:
            return
        added, skipped = 0, []
        for path in paths:
            try:
                text = text_extract.extract(path)
            except ValueError as exc:
                skipped.append(str(exc))
                continue
            title = path.replace("\\", "/").rsplit("/", 1)[-1]
            if call(self, integrity_external.import_text, self.who, title=title, content=text,
                    file_type=text_extract.file_type(path), source_url=url.strip() or None,
                    write=True) is not None:
                added += 1
        self.reload()
        info(self, f"Added {added} external text(s)." + (
            "\nSkipped: " + "; ".join(skipped[:5]) if skipped else ""))

    def run_check(self, record):
        result_id = call(self, checks.run_check, record["id"], who=self.who, write=True)
        if result_id:
            self.portal.changed()
            ReportWindow(self, self.who, result_id, on_change=self.portal.changed)

    def delete(self, record):
        if confirm(self, f"Delete '{record['title']}' and its results? This cannot be undone."):
            self.write(checks.delete_document, self.who, record["id"], done="Deleted.")

    def add(self, kind):
        from education_system.systems.university.infrastructure.integrity import text_extract
        path = filedialog.askopenfilename(parent=self, title=f"Choose the {kind} document",
                                          filetypes=[("Documents", "*.pdf *.docx *.txt *.md *.py "
                                                      "*.java *.c *.cpp *.js"),
                                                     ("All files", "*.*")])
        if not path:
            return
        try:
            text = text_extract.extract(path)
        except ValueError as exc:
            info(self, str(exc))
            return
        values = ask(self, f"Add {kind}", [
            Field("title", "Title", required=True),
            pickers.module_field(self, self.who, hint="blank = any module (references only)"),
            pickers.assignment_field(self, self.who, label="Assignment (optional)")],
            {"title": path.rsplit("/", 1)[-1]})
        if not values:
            return
        assignment = values["assignment_id"] if values["assignment_id"] not in ("", None) \
            else None
        self.write(checks.add_document, self.who, title=values["title"], content=text,
                   file_type=text_extract.file_type(path),
                   module_code=values["module_code"] or None, kind=kind,
                   assignment_id=assignment, done=f"The {kind} was added.")


THRESHOLD_CHOICES = [(round(n / 100, 2), f"{n}%") for n in range(5, 100, 5)]


class ModuleSettingsTab(ttk.Frame):
    """Per-module checking switch and review threshold."""

    def __init__(self, parent, portal):
        super().__init__(parent, padding=10)
        self.portal = portal
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(bar, text="Change a module's settings…", command=self.edit).pack(side="left")
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left", padx=4)
        self.detail = Detail(self)
        self.detail.pack(fill="both", expand=True)
        self.refresh()

    def _rows(self, conn):
        access.ensure(conn)
        modules = access.taught_modules(conn, self.portal.who)
        rows = access.dicts(conn.execute("SELECT * FROM course_integrity_settings "
                                         "ORDER BY module_code"))
        return [r for r in rows if modules is None or r["module_code"] in modules], modules

    def refresh(self):
        found = call(self, self._rows) or ([], [])
        rows, modules = found
        default = call(self, access.number, "review_threshold", quiet=True)
        lines = [f"{r['module_code']}: checks {'on' if r['plagiarism_enabled'] else 'off'}, "
                 f"review at {float(r['similarity_threshold'] or 0):.0%}, collaboration "
                 f"{'allowed' if r.get('allow_collaboration') else 'not allowed'}, AI-writing "
                 f"indicators {'off' if r.get('ai_detection_enabled') == 0 else 'on'}"
                 + (f" — {r['notes']}" if r["notes"] else "") for r in rows]
        self.detail.show("Module settings", [
            ("", [("Default review threshold", f"{float(default or 0):.0%}"),
                  ("Your modules", "all modules" if modules is None else ", ".join(modules)
                   or "none")]),
            ("Modules with their own settings", lines or ["None — every module uses the "
                                                          "default."])])

    def edit(self):
        values = ask(self, "Module integrity settings", [
            pickers.module_field(self, self.portal.who, required=True),
            Field("enabled", "Check submissions automatically", "check"),
            Field("threshold", "Review threshold", "pick", THRESHOLD_CHOICES, required=True),
            Field("allow_collaboration", "Collaboration allowed", "check"),
            Field("ai_enabled", "AI-writing indicators", "check"),
            Field("notes", "Notes", "multiline")],
            {"enabled": True, "threshold": 0.25, "ai_enabled": True})
        if values and call(self, access.set_module_settings, self.portal.who,
                           values["module_code"], enabled=values["enabled"],
                           threshold=values["threshold"],
                           allow_collaboration=values["allow_collaboration"],
                           notes=values["notes"], ai_enabled=values["ai_enabled"],
                           write=True) is not None:
            self.refresh()


class StatisticsTab(ttk.Frame):
    def __init__(self, parent, portal):
        super().__init__(parent, padding=10)
        self.portal = portal
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left")
        self.detail = Detail(self)
        self.detail.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self):
        stats = call(self, review.statistics, self.portal.who)
        if stats is None:
            return
        ai = call(self, integrity_ai.statistics, self.portal.who, quiet=True) or {}
        self.detail.show("Checks on your modules", [
            ("", [("Checks", stats["checks"]), ("Waiting for review", stats["waiting_review"]),
                  ("Referred", stats["referred"]), ("Open cases", stats["open_cases"]),
                  ("Largely reworded", stats.get("reworded", 0)),
                  ("With disguised characters", stats.get("disguised", 0)),
                  ("Failed automatic checks", stats.get("failed_checks", 0))]),
            ("By band", [(nice(k), v) for k, v in stats["by_status"].items()]),
            ("AI-writing readings (indicators, not evidence)", [
                ("Readings", ai.get("readings", 0)), ("At or above the review strength",
                                                      ai.get("flagged", 0)),
                ("Waiting for review", ai.get("waiting_review", 0)),
                ("Referred", ai.get("referred", 0)),
                ("Too short / code (no reading)", ai.get("not_enough_text", 0))])])


class FailedChecksTab(RecordTab):
    """Automatic checks that failed (no readable text, no student account),
    to retry, check by hand or close with a reason."""

    columns = [("id", "Submission", 80), ("work", "Assignment", 200), ("student", "Student", 90),
               ("module", "Module", 80), ("tries", "Tries", 50), ("error", "Problem", 260)]
    statuses = ("waiting", "all")

    def load(self, conn, search, status):
        rows = checks.failures(conn, self.who, include_resolved=status == "all")
        if search:
            needle = search.lower()
            rows = [r for r in rows if needle in " ".join(str(r.get(k) or "") for k in (
                "assignment_title", "student_id", "module_code", "file_name")).lower()]
        return rows

    def row_id(self, row):
        return row["submission_id"]

    def values(self, row):
        return [row["submission_id"], row["assignment_title"], row["student_id"],
                row["module_code"], row["attempts"], row["last_error"]]

    def fetch(self, conn, record_id):
        return self._rows.get(str(record_id))

    def render(self, record):
        self.detail.show(f"Submission {record['submission_id']}", [("", [
            ("Assignment", record["assignment_title"]), ("Module", record["module_code"]),
            ("Student", record["student_id"]), ("File", record["file_name"]),
            ("Tries", record["attempts"]), ("First failed", record["first_failed_at"]),
            ("Last tried", record["last_attempt_at"]), ("Problem", record["last_error"]),
            ("Settled", record["resolved_at"]), ("How", record["resolution"])])])

    def actions(self, record):
        if record["resolved_at"]:
            return []
        return [("Try again now", lambda: self.retry(record)),
                ("Check text by hand…", lambda: self.by_hand(record)),
                ("Won't be checked…", lambda: self.dismiss(record))]

    def retry(self, record):
        from education_system.systems.university.infrastructure.integrity import submission_hook
        try:        # on its own connection, as the automatic check runs
            result_id = submission_hook.check_now(record["submission_id"])
        except Exception as exc:
            call(self, checks.record_failure, record["submission_id"], exc, write=True)
            self.reload()
            info(self, f"It failed again: {exc}")
            return
        if not result_id:
            call(self, checks.resolve_failure, record["submission_id"], "no check needed",
                 self.who.username, write=True)
        self.reload()
        if result_id:
            ReportWindow(self, self.who, result_id, on_change=self.portal.changed)
        else:
            info(self, "Checks are turned off for this module now; nothing to check.")

    def by_hand(self, record):
        from education_system.systems.university.infrastructure.integrity import text_extract
        path = filedialog.askopenfilename(parent=self, title="Choose a readable copy of the work "
                                                             "(typed up or run through OCR)",
                                          filetypes=[("Documents", "*.pdf *.docx *.txt *.md"),
                                                     ("All files", "*.*")])
        if not path:
            return
        try:
            text = text_extract.extract(path)
        except ValueError as exc:
            info(self, str(exc))
            return
        result_id = self.write(checks.check_by_hand, self.who, record["submission_id"], text,
                               text_extract.file_type(path))
        if result_id:
            ReportWindow(self, self.who, result_id, on_change=self.portal.changed)

    def dismiss(self, record):
        note = ask_text(self, "Won't be checked", "Why this submission will not be checked "
                                                  "(e.g. an image-only portfolio)")
        if note:
            self.write(checks.dismiss_failure, self.who, record["submission_id"], note,
                       done="Recorded.")


# The AI-writing tab lives in ai_writing; the old name still works.
from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.ai_writing import (  # noqa: E402,E501
    AiWritingTab,
)

AIFlagsTab = AiWritingTab
