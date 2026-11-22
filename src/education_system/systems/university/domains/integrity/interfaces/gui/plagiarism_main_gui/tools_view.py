"""The "Tools" tab of the Academic Integrity window: the old plagiarism
checker's tools on the current rules (``application/integrity/tools``) —
compare two documents, import files or a folder, check / export / delete
several documents, document and student history, statistics with a chart,
reports (CSV, HTML, PDF) and, for integrity officers, repository health.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, ttk

from education_system.systems.university.application.integrity import choices
from education_system.systems.university.application.integrity import tools
from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui import (  # noqa: E501
    pickers,
)
from education_system.systems.university.application.integrity import plagiarism_checks as checks
from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.report_view import (  # noqa: E501
    ReportWindow, _scrolled_text,
)
from education_system.systems.university.infrastructure.ui.record_screens import (
    Detail, Field, ask, ask_pick, ask_text, call, confirm, fill, info, make_tree, nice,
)

EXACT, REWORDED = "#ffe08a", "#ffd59a"


def _pct(value) -> str:
    return f"{float(value or 0):.0%}"


def _window(parent, title, width=1100, height=720):
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent.winfo_toplevel())
    win.geometry(f"{min(width, win.winfo_screenwidth() - 60)}x"
                 f"{min(height, win.winfo_screenheight() - 100)}")
    win.minsize(700, 450)
    return win


def _save(parent, data, default_ext, kinds, initial):
    path = filedialog.asksaveasfilename(parent=parent, defaultextension=default_ext,
                                        filetypes=kinds, initialfile=initial)
    if not path:
        return None
    mode = "wb" if isinstance(data, (bytes, bytearray)) else "w"
    with open(path, mode, **({} if mode == "wb" else {"encoding": "utf-8"})) as fh:
        fh.write(data)
    info(parent, f"Saved {os.path.basename(path)}.")
    return path


# ── choosing documents ──────────────────────────────────────────────────


class DocumentPicker(tk.Toplevel):
    """Pick one or more documents from those the person may see."""

    def __init__(self, parent, who, title, many=True, need=None):
        super().__init__(parent)
        self.who, self.many, self.need, self.result = who, many, need, None
        self.title(title)
        self.transient(parent.winfo_toplevel())
        self.geometry("900x560")
        bar = ttk.Frame(self, padding=6)
        bar.pack(side="bottom", fill="x")
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right", padx=3)
        ttk.Button(bar, text="Choose", command=self.choose).pack(side="right", padx=3)
        self.count = ttk.Label(bar, text="")
        self.count.pack(side="left")
        top = ttk.Frame(self, padding=6)
        top.pack(side="top", fill="x")
        ttk.Label(top, text="Search").pack(side="left")
        self.search = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.search, width=26)
        entry.pack(side="left", padx=4)
        entry.bind("<Return>", lambda _e: self.load())
        ttk.Label(top, text="Module").pack(side="left", padx=(8, 0))
        self.module = pickers.Picker(top, lambda: pickers.pairs(self, choices.modules, who),
                                     width=28, blank="(any module)")
        self.module.pack(side="left", padx=4)
        self.module.bind("<<ComboboxSelected>>", lambda _e: self.load(), add="+")
        ttk.Label(top, text="Kind").pack(side="left", padx=(8, 0))
        self.kind = tk.StringVar()
        ttk.Combobox(top, textvariable=self.kind, values=("",) + checks.KINDS, width=11,
                     state="readonly").pack(side="left", padx=4)
        ttk.Button(top, text="Find", command=self.load).pack(side="left", padx=4)
        if many:
            ttk.Label(top, text="Ctrl/Shift-click to choose several",
                      foreground="#666666").pack(side="left", padx=8)
        self.tree = make_tree(self, [("id", "Doc", 60), ("title", "Title", 280),
                                     ("kind", "Kind", 80), ("student", "Student", 100),
                                     ("module", "Module", 80), ("words", "Words", 60),
                                     ("date", "Submitted", 120)], height=16)
        self.tree.configure(selectmode="extended" if many else "browse")
        self.load()
        self.grab_set()
        parent.wait_window(self)

    def load(self):
        rows = call(self, checks.documents, self.who, search=self.search.get().strip() or None,
                    module_code=self.module.value() or None,
                    kind=self.kind.get() or None, limit=1000) or []
        fill(self.tree, rows, lambda r: r["id"],
             lambda r: [r["id"], r["title"], r["kind"], r["student_id"], r["module_code"],
                        r["word_count"], (r["submission_date"] or "")[:16]])
        self.count.configure(text=f"{len(rows)} document(s)")

    def choose(self):
        picked = [int(i) for i in self.tree.selection()]
        if not picked:
            info(self, "Choose a document first.")
            return
        if self.need and len(picked) != self.need:
            info(self, f"Choose exactly {self.need} documents.")
            return
        self.result = picked
        self.destroy()


# ── compare ─────────────────────────────────────────────────────────────


class CompareWindow(tk.Toplevel):
    def __init__(self, parent, who, doc_a, doc_b):
        super().__init__(parent)
        self.result = call(self, tools.compare, who, doc_a, doc_b, write=True)
        if self.result is None:
            self.after(10, self.destroy)
            return
        self.title(f"Compare documents {doc_a} and {doc_b}")
        self.transient(parent.winfo_toplevel())
        self.geometry(f"{min(1400, self.winfo_screenwidth() - 40)}x"
                      f"{min(860, self.winfo_screenheight() - 80)}")
        bar = ttk.Frame(self, padding=6)
        bar.pack(side="bottom", fill="x")
        ttk.Button(bar, text="Close", command=self.destroy).pack(side="right", padx=3)
        ttk.Button(bar, text="Save as HTML…", command=lambda: _save(
            self, tools.comparison_html(self.result), ".html", [("HTML", "*.html")],
            f"comparison_{doc_a}_{doc_b}.html")).pack(side="right", padx=3)
        ttk.Button(bar, text="Save as text…", command=lambda: _save(
            self, tools.comparison_text(self.result), ".txt", [("Text", "*.txt")],
            f"comparison_{doc_a}_{doc_b}.txt")).pack(side="right", padx=3)
        ttk.Label(bar, text="Yellow: same words · orange: same sentence reworded").pack(
            side="left")
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=6, pady=6)
        for side in ("a", "b"):
            d = self.result[side]
            other = self.result["b" if side == "a" else "a"]
            frame = ttk.Frame(panes)
            panes.add(frame, weight=1)
            ttk.Label(frame, text=f"{d['id']}: {d['title']}", font=("Segoe UI", 11, "bold")).pack(
                anchor="w")
            ttk.Label(frame, text=f"{nice(d['kind'])} · {d['module_code'] or 'no module'} · "
                                  f"{d['student'] or ''} · {d['words']} words").pack(anchor="w")
            ttk.Label(frame, text=f"{_pct(d['score'])} also in document {other['id']}; a further "
                                  f"{_pct(d['paraphrase_score'])} reworded",
                      foreground="#b0620a").pack(anchor="w")
            box, text = _scrolled_text(frame, height=20)
            box.pack(fill="both", expand=True)
            text.insert("1.0", d["text"])
            text.tag_configure("exact", background=EXACT)
            text.tag_configure("paraphrase", background=REWORDED)
            for p in d["passages"]:
                text.tag_add(p.get("kind", "exact"), f"1.0+{int(p['start'])}c",
                             f"1.0+{int(p['end'])}c")
            text.configure(state="disabled")


# ── import ──────────────────────────────────────────────────────────────


class ImportWindow(tk.Toplevel):
    """Bring several files, or a folder, into the repository."""

    def __init__(self, parent, who, folder=False):
        super().__init__(parent)
        self.who = who
        self.title("Import files")
        self.transient(parent.winfo_toplevel())
        self.geometry("980x620")
        from education_system.systems.university.infrastructure.integrity import text_extract
        if folder:
            root = filedialog.askdirectory(parent=self, title="Folder of work to import")
            paths = []
            if root:
                for base, _dirs, names in os.walk(root):
                    paths += [os.path.join(base, n) for n in sorted(names)
                              if text_extract.file_type(n) in text_extract.SUPPORTED]
        else:
            paths = list(filedialog.askopenfilenames(parent=self, title="Files to import",
                                                     filetypes=text_extract.FILETYPES))
        if not paths:
            self.after(10, self.destroy)
            return
        self.paths, self.students = paths, {}
        bar = ttk.Frame(self, padding=6)
        bar.pack(side="bottom", fill="x")
        ttk.Button(bar, text="Close", command=self.destroy).pack(side="right", padx=3)
        ttk.Button(bar, text="Import", command=self.run).pack(side="right", padx=3)
        ttk.Button(bar, text="Set student for selected…", command=self.set_student).pack(
            side="left", padx=3)
        form = ttk.Frame(self, padding=6)
        form.pack(side="top", fill="x")
        self.kind = tk.StringVar(value="submission")
        self.check = tk.BooleanVar(value=True)
        ttk.Label(form, text="Kind").pack(side="left")
        ttk.Combobox(form, textvariable=self.kind, values=tools.IMPORT_KINDS, width=11,
                     state="readonly").pack(side="left", padx=4)
        ttk.Label(form, text="Module").pack(side="left", padx=(8, 0))
        self.module = pickers.Picker(form, lambda: pickers.pairs(self, choices.modules, who),
                                     width=26, blank="(none)")
        self.module.pack(side="left", padx=4)
        ttk.Label(form, text="Assignment").pack(side="left", padx=(8, 0))
        self.assignment = pickers.Picker(form, lambda: pickers.pairs(
            self, choices.assignments, who, self.module.value() or None), width=26,
            blank="(none)")
        self.assignment.pack(side="left", padx=4)
        self.module.bind("<<ComboboxSelected>>", lambda _e: self.assignment.reload(), add="+")
        ttk.Checkbutton(form, text="Check submissions as they are added",
                        variable=self.check).pack(side="left", padx=8)
        ttk.Label(self, text="Student work: the student number is read from each file name "
                             "(e.g. 5853694_essay.pdf) unless you set it.",
                  foreground="#666666", padding=(8, 0)).pack(anchor="w")
        self.tree = make_tree(self, [("file", "File", 360), ("student", "Student", 110),
                                     ("status", "Status", 140), ("detail", "Detail", 320)])
        self.tree.configure(selectmode="extended")
        guesses = call(self, lambda conn: {p: tools.student_from_name(conn, p) for p in paths},
                       quiet=True) or {}
        for p in paths:
            self.tree.insert("", "end", iid=p, values=[os.path.basename(p), guesses.get(p) or "",
                                                       "to import", ""])

    def set_student(self):
        picked = self.tree.selection()
        if not picked:
            info(self, "Select the files first.")
            return
        number = ask_pick(self, "Student", "Student for the selected files",
                          lambda: pickers.pairs(self, choices.students, self.who,
                                                self.module.value() or None))
        if number not in (None, ""):
            number = str(number)
            for iid in picked:
                self.students[iid] = number
                self.tree.set(iid, "student", number)

    def run(self):
        assignment = self.assignment.value()
        out = call(self, tools.import_files, self.who, self.paths, kind=self.kind.get(),
                   module_code=self.module.value() or None,
                   assignment_id=int(assignment) if assignment not in ("", None) else None,
                   students=self.students, check=self.check.get(), write=True)
        if out is None:
            return
        by_name = {}
        for o in out:
            by_name.setdefault(o["file"], []).append(o)
        for p in self.paths:
            o = (by_name.get(os.path.basename(p)) or [None]).pop(0)
            if o:
                detail = o["error"] or (f"document {o['document_id']}"
                                        + (f", report {o['result_id']}" if o["result_id"] else ""))
                self.tree.item(p, values=[os.path.basename(p), o["student"] or "",
                                          o["status"], detail])
        added = sum(1 for o in out if o["document_id"])
        info(self, f"{added} of {len(out)} file(s) added.")


# ── outcomes of a bulk action ───────────────────────────────────────────


def _outcomes(parent, title, rows, columns, values, open_result=None, who=None):
    win = _window(parent, title, 860, 480)
    bar = ttk.Frame(win, padding=6)
    bar.pack(side="bottom", fill="x")
    ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
    tree = make_tree(win, columns)
    fill(tree, rows, lambda r: r["document_id"], values)
    if open_result:
        def opened(_e=None):
            row = next((r for r in rows if str(r["document_id"]) == (tree.selection() or [""])[0]),
                       None)
            if row and row.get("result_id"):
                ReportWindow(win, who, row["result_id"])
        tree.bind("<Double-1>", opened)
        ttk.Label(bar, text="Double-click a row to open its report").pack(side="left")


# ── history ─────────────────────────────────────────────────────────────


class DocumentHistoryWindow:
    def __init__(self, parent, who, doc_id):
        data = call(parent, tools.document_history, who, doc_id, write=True)
        if data is None:
            return
        win = _window(parent, f"Checks on document {doc_id}", 980, 520)
        ttk.Label(win, text=f"{data['title']} — {nice(data['kind'])}, "
                            f"{data['module_code'] or 'no module'}, {data['student'] or ''}, "
                            f"{data['words']} words", padding=8).pack(anchor="w")
        bar = ttk.Frame(win, padding=6)
        bar.pack(side="bottom", fill="x")
        ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
        ttk.Label(bar, text="Double-click a check to open its report").pack(side="left")
        tree = make_tree(win, [("id", "Report", 60), ("date", "Checked", 130),
                               ("by", "By", 90), ("score", "Similarity", 80),
                               ("reworded", "Reworded", 80), ("band", "Band", 80),
                               ("review", "Review", 100), ("sources", "Sources", 60),
                               ("case", "Case", 50)])
        fill(tree, data["results"], lambda r: r["id"],
             lambda r: [r["id"], (r["check_date"] or "")[:16], r["checked_by"],
                        _pct(r["similarity_score"]), _pct(r["paraphrase_score"]), r["status"],
                        r["review_status"], r["sources"], r["case_id"] or ""])
        tree.bind("<Double-1>", lambda _e: tree.selection() and ReportWindow(
            win, who, int(tree.selection()[0])))


class StudentHistoryWindow:
    def __init__(self, parent, who, student_id):
        data = call(parent, tools.student_history, who, student_id, write=True)
        if data is None:
            return
        win = _window(parent, f"Integrity history: {student_id}", 1000, 600)
        bar = ttk.Frame(win, padding=6)
        bar.pack(side="bottom", fill="x")
        ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
        ttk.Label(bar, text="Double-click a document for its checks").pack(side="left")
        ttk.Label(win, text="Documents", padding=(8, 4)).pack(anchor="w")
        tree = make_tree(win, [("id", "Doc", 60), ("title", "Title", 260),
                               ("module", "Module", 80), ("date", "Submitted", 120),
                               ("checks", "Checks", 60), ("score", "Latest", 70),
                               ("review", "Review", 100), ("case", "Case", 50)], height=10)
        fill(tree, data["documents"], lambda r: r["id"],
             lambda r: [r["id"], r["title"], r["module_code"], (r["submitted"] or "")[:16],
                        r["checks"], _pct((r["latest"] or {}).get("similarity_score")),
                        (r["latest"] or {}).get("review_status") or "",
                        (r["latest"] or {}).get("case_id") or ""])
        tree.bind("<Double-1>", lambda _e: tree.selection() and DocumentHistoryWindow(
            win, who, int(tree.selection()[0])))
        if data["cases"]:
            ttk.Label(win, text="Integrity cases", padding=(8, 4)).pack(anchor="w")
            cases = make_tree(win, [("id", "Case", 60), ("type", "Type", 110),
                                    ("stage", "Stage", 90), ("outcome", "Outcome", 200),
                                    ("module", "Module", 80), ("opened", "Opened", 100)],
                              height=6)
            fill(cases, data["cases"], lambda r: r["id"],
                 lambda r: [r["id"], r["case_type"], r["stage"], r["penalty"] or r["outcome"],
                            r["module_code"], (r["created_at"] or "")[:10]])


# ── statistics ──────────────────────────────────────────────────────────


class StatisticsWindow:
    def __init__(self, parent, who):
        self.who = who
        self.win = _window(parent, "Integrity statistics", 1200, 780)
        top = ttk.Frame(self.win, padding=6)
        top.pack(side="top", fill="x")
        from education_system.platform.delivery.gui.date_picker import DatePicker
        ttk.Label(top, text="From").pack(side="left")
        self.date_from = DatePicker(top)
        self.date_from.pack(side="left", padx=3)
        ttk.Label(top, text="To").pack(side="left", padx=(8, 0))
        self.date_to = DatePicker(top)
        self.date_to.pack(side="left", padx=3)
        ttk.Button(top, text="Refresh", command=self.load).pack(side="left", padx=6)
        bar = ttk.Frame(self.win, padding=6)
        bar.pack(side="bottom", fill="x")
        ttk.Button(bar, text="Close", command=self.win.destroy).pack(side="right")
        body = ttk.PanedWindow(self.win, orient="horizontal")
        body.pack(fill="both", expand=True, padx=6)
        left, right = ttk.Frame(body), ttk.Frame(body)
        body.add(left, weight=2)
        body.add(right, weight=3)
        self.detail = Detail(left)
        self.detail.pack(fill="both", expand=True)
        ttk.Label(right, text="Checks by month (bar) and needing review (orange)").pack(
            anchor="w")
        self.canvas = tk.Canvas(right, height=220, background="white", highlightthickness=0)
        self.canvas.pack(fill="x")
        self.canvas.bind("<Configure>", lambda _e: self.draw())
        ttk.Label(right, text="By module").pack(anchor="w", pady=(6, 0))
        self.modules = make_tree(right, [("module", "Module", 90), ("checks", "Checks", 60),
                                         ("docs", "Docs", 50), ("avg", "Average", 70),
                                         ("high", "High", 50), ("waiting", "Waiting", 60),
                                         ("referred", "Referred", 60)], height=7)
        ttk.Label(right, text="Recent checks (double-click to open)").pack(anchor="w")
        self.recent = make_tree(right, [("id", "Report", 60), ("title", "Work", 220),
                                        ("student", "Student", 90), ("score", "Score", 60),
                                        ("review", "Review", 90), ("date", "Checked", 120)],
                                height=6)
        self.recent.bind("<Double-1>", lambda _e: self.recent.selection() and ReportWindow(
            self.win, who, int(self.recent.selection()[0])))
        self.stats = None
        self.load()

    def load(self):
        stats = call(self.win, tools.statistics_detail, self.who,
                     self.date_from.get() or None, self.date_to.get() or None)
        if stats is None:
            return
        self.stats = stats
        o = stats["overview"]
        self.detail.show("Checks", [
            ("", [("Checks", o["checks"] or 0), ("Documents checked", o["documents"] or 0),
                  ("Average similarity", _pct(o["average"])),
                  ("Waiting for review", o["waiting"] or 0), ("Referred", o["referred"] or 0),
                  ("Cleared on review", o["cleared"] or 0)]),
            ("By band", [(nice(b["band"]), b["checks"]) for b in stats["by_band"]] or ["None"]),
            ("By file type", [(f".{f['file_type']}", f"{f['checks']} checks, average "
                                                     f"{_pct(f['average'])}")
                              for f in stats["by_file_type"]] or ["None"]),
            ("Repository", [(nice(k), v) for k, v in sorted(o["repository"].items())] or
             ["Empty"])])
        fill(self.modules, stats["by_module"], lambda r: r["module"] or "-",
             lambda r: [r["module"] or "—", r["checks"], r["documents"], _pct(r["average"]),
                        r["high"] or 0, r["waiting"] or 0, r["referred"] or 0])
        fill(self.recent, stats["recent"], lambda r: r["id"],
             lambda r: [r["id"], r["title"], r["student_id"], _pct(r["similarity_score"]),
                        r["review_status"], (r["check_date"] or "")[:16]])
        self.draw()

    def draw(self):
        c = self.canvas
        c.delete("all")
        months = (self.stats or {}).get("by_month") or []
        if not months:
            c.create_text(20, 20, anchor="nw", text="No checks in this period.")
            return
        width, height = max(c.winfo_width(), 300), int(c.cget("height"))
        top = max(m["checks"] for m in months) or 1
        slot = (width - 40) / len(months)
        for i, m in enumerate(months):
            x = 30 + i * slot
            h = (height - 50) * m["checks"] / top
            r = (height - 50) * (m["needing_review"] or 0) / top
            c.create_rectangle(x, height - 30 - h, x + slot * 0.6, height - 30, fill="#7aa6d6",
                               outline="")
            c.create_rectangle(x, height - 30 - r, x + slot * 0.6, height - 30, fill="#f0a24a",
                               outline="")
            c.create_text(x + slot * 0.3, height - 30 - h - 8, text=str(m["checks"]))
            c.create_text(x + slot * 0.3, height - 15, text=m["month"][2:], font=("Segoe UI", 8))


# ── reports ─────────────────────────────────────────────────────────────


def make_report(parent, who, officer):
    kinds = [(k, label) for k, label in tools.REPORTS.items()
             if officer or k not in ("users", "health")]
    values = ask(parent, "Integrity report", [
        Field("kind", "Report", "combo", kinds, required=True),
        Field("date_from", "From", "datepick"), Field("date_to", "To", "datepick"),
        Field("fmt", "Format", "combo", [("pdf", "PDF"), ("html", "HTML"), ("csv", "CSV")],
              required=True)], {"kind": "summary", "fmt": "pdf"})
    if not values:
        return

    def build(conn):
        rep = tools.report(conn, who, values["kind"], values["date_from"] or None,
                           values["date_to"] or None)
        return tools.render(rep, values["fmt"])
    data = call(parent, build, write=True)
    if data is not None:
        _save(parent, data, f".{values['fmt']}", [(values["fmt"].upper(), f"*.{values['fmt']}")],
              f"integrity_{values['kind']}_{tools.today()}.{values['fmt']}")


# ── repository health (officers) ────────────────────────────────────────


class HealthWindow:
    def __init__(self, parent, who):
        self.who = who
        self.win = _window(parent, "Repository health", 760, 480)
        bar = ttk.Frame(self.win, padding=6)
        bar.pack(side="bottom", fill="x")
        ttk.Button(bar, text="Close", command=self.win.destroy).pack(side="right", padx=3)
        ttk.Button(bar, text="Fix what can be fixed", command=self.fix).pack(side="right",
                                                                            padx=3)
        ttk.Button(bar, text="Check again", command=self.load).pack(side="left")
        self.detail = Detail(self.win)
        self.detail.pack(fill="both", expand=True)
        self.load()

    def load(self):
        found = call(self.win, tools.repository_health, self.who)
        if found is None:
            return
        lines = []
        for key, items in found.items():
            if key == "checked_at":
                continue
            shown = ", ".join(str(i["documents"] if isinstance(i, dict) else i)
                              for i in items[:15])
            lines.append((nice(key), f"{len(items)}" + (f" — {shown}" if items else "")))
        self.detail.show(f"Checked {found['checked_at']}", [
            ("", lines),
            ("", "Fixing removes orphaned results and matches, clears links to deleted sources "
                 "and deletes empty documents nothing refers to. Unknown authors and duplicate "
                 "texts are listed for you to look at.")])

    def fix(self):
        if not confirm(self.win, "Repair the repository now?"):
            return
        done = call(self.win, tools.fix_repository, self.who, write=True)
        if done is not None:
            info(self.win, "Removed {orphaned_results} orphaned result(s), {orphaned_matches} "
                           "orphaned match(es); cleared {dangling_sources} dangling source(s); "
                           "deleted {empty_documents} empty document(s).".format(**done))
            self.load()


# ── the tab ─────────────────────────────────────────────────────────────


class ToolsTab(ttk.Frame):
    def __init__(self, parent, portal):
        super().__init__(parent, padding=14)
        self.portal = portal
        self.who = portal.who
        officer = portal.is_officer
        groups = [
            ("Documents", [
                ("Compare two documents…", self.compare,
                 "Side by side, with what each shares with the other highlighted."),
                ("Import files…", lambda: ImportWindow(self, self.who),
                 "Student work, references or templates; checked as they go in."),
                ("Import a folder…", lambda: ImportWindow(self, self.who, folder=True),
                 "Every supported file in a folder and its subfolders."),
                ("Check several documents…", self.bulk_check,
                 "Run a similarity check on each chosen document."),
                ("Export documents…", self.export,
                 "The chosen documents' text as a ZIP (text, Markdown or HTML)."),
            ]),
            ("History and figures", [
                ("Document history…", self.document_history,
                 "Every check on one document."),
                ("Student history…", self.student_history,
                 "A student's documents and checks on your modules."),
                ("Statistics and chart…", lambda: StatisticsWindow(self, self.who),
                 "By module, band, file type and month."),
                ("Reports…", lambda: make_report(self, self.who, officer),
                 "Summary, trends, modules" + (", staff activity, repository health"
                                               if officer else "") + " as PDF, HTML or CSV."),
            ]),
        ]
        if officer:
            groups.append(("Repository (integrity officers)", [
                ("Repository health…", lambda: HealthWindow(self, self.who),
                 "Orphaned results, empty documents, unknown authors, duplicates."),
                ("Delete several documents…", self.bulk_delete,
                 "With a reason; documents that are case evidence stay."),
            ]))
        for title, items in groups:
            box = ttk.LabelFrame(self, text=title, padding=10)
            box.pack(fill="x", pady=6)
            for label, command, hint in items:
                row = ttk.Frame(box)
                row.pack(fill="x", pady=2)
                ttk.Button(row, text=label, command=command, width=28).pack(side="left")
                ttk.Label(row, text=hint, foreground="#555555").pack(side="left", padx=10)

    def _pick(self, title, many=True, need=None):
        return DocumentPicker(self, self.who, title, many=many, need=need).result

    def compare(self):
        picked = self._pick("Choose two documents to compare", need=2)
        if picked:
            CompareWindow(self, self.who, picked[0], picked[1])

    def bulk_check(self):
        picked = self._pick("Choose documents to check")
        if not picked:
            return
        out = call(self, tools.bulk_check, self.who, picked, write=True)
        if out is not None:
            self.portal.changed()
            _outcomes(self, "Checks run", out,
                      [("doc", "Doc", 60), ("report", "Report", 70), ("score", "Similarity", 80),
                       ("band", "Band", 90), ("error", "Not checked because", 380)],
                      lambda r: [r["document_id"], r["result_id"] or "",
                                 _pct(r["score"]) if r["score"] is not None else "",
                                 r["band"] or "", r["error"] or ""],
                      open_result=True, who=self.who)

    def bulk_delete(self):
        picked = self._pick("Choose documents to delete")
        if not picked:
            return
        reason = ask_text(self, "Delete documents", f"Why are these {len(picked)} document(s) "
                                                    "being deleted?")
        if not reason or not confirm(self, f"Delete {len(picked)} document(s) and their "
                                           "results? This cannot be undone."):
            return
        out = call(self, tools.bulk_delete, self.who, picked, reason, write=True)
        if out is not None:
            self.portal.changed()
            _outcomes(self, "Documents deleted", out,
                      [("doc", "Doc", 60), ("deleted", "Deleted", 80),
                       ("error", "Kept because", 400)],
                      lambda r: [r["document_id"], "yes" if r["deleted"] else "no",
                                 r["error"] or ""])

    def export(self):
        picked = self._pick("Choose documents to export")
        if not picked:
            return
        values = ask(self, "Export documents", [
            Field("fmt", "Format", "combo", [("txt", "Plain text"), ("md", "Markdown"),
                                             ("html", "HTML")], required=True)], {"fmt": "txt"})
        if not values:
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".zip",
                                            filetypes=[("ZIP", "*.zip")],
                                            initialfile=f"documents_{tools.today()}.zip")
        if path:
            done = call(self, tools.export_texts, self.who, picked, path, values["fmt"],
                        write=True)
            if done is not None:
                info(self, f"Exported {done['written']} of {done['documents']} document(s).")

    def document_history(self):
        picked = self._pick("Choose a document", many=False)
        if picked:
            DocumentHistoryWindow(self, self.who, picked[0])

    def student_history(self):
        number = ask_pick(self, "Student history", "Student",
                          lambda: pickers.pairs(self, choices.students, self.who))
        if number not in (None, ""):
            StudentHistoryWindow(self, self.who, str(number))
