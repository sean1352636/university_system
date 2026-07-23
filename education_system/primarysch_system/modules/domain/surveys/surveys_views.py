"""Tkinter views for Primary School Surveys."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any
from education_system.shared import branding
from education_system.primarysch_system.modules.domain.surveys import (
    surveys as data,
)
from education_system.primarysch_system.modules.domain.surveys.surveys import (
    AUDIENCES,
    DEFAULT_AUDIENCE,
    DEFAULT_STATUS,
    QUESTION_TYPES,
    Question,
    Response,
    STATUSES,
    Survey,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Draft":    ("#fff7e6", "#7a5800"),
    "Open":     ("#e6f7e6", "#0d6b2a"),
    "Closed":   ("#e6e6ff", "#3a3a8c"),
    "Archived": ("#eeeeee", "#444444"),
}


def open_surveys_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Surveys — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    SurveysTab(nb, scope="open", label="Open")
    SurveysTab(nb, scope="all",  label="All")
    SummaryTab(nb)


class SurveysTab:
    def __init__(self, nb: ttk.Notebook, *,
                 scope: str, label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        # paned: surveys top, responses + stats bottom
        paned = ttk.PanedWindow(self.frame, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=8)
        self.top = ttk.Frame(paned)
        self.bottom = ttk.Frame(paned)
        paned.add(self.top, weight=3)
        paned.add(self.bottom, weight=2)
        self._build_top()
        self._build_bottom()
        self.refresh()

    def _build_top(self) -> None:
        bar = ttk.Frame(self.top)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Audience:").pack(side="left")
        self.f_aud = ttk.Combobox(bar, values=("",) + AUDIENCES,
                                    state="readonly", width=18)
        self.f_aud.current(0)
        self.f_aud.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly", width=12)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Name:").pack(side="left")
        self.f_name = ttk.Entry(bar, width=20)
        self.f_name.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Created by:").pack(side="left")
        self.f_creator = ttk.Entry(bar, width=14)
        self.f_creator.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                  padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New survey",
                    command=self._new).pack(side="left",
                                                padx=(16, 0))

        table_frame = ttk.Frame(self.top)
        table_frame.pack(fill="both", expand=True)
        cols = ("id", "name", "audience", "status",
                "open_on", "close_on", "questions",
                "responses", "created_by")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "name": 280, "audience": 140,
                   "status": 100, "open_on": 100,
                   "close_on": 100, "questions": 80,
                   "responses": 90, "created_by": 130}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "questions",
                                                  "responses")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.bind("<<TreeviewSelect>>",
                         lambda _e: self._refresh_bottom())
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.top)
        actions.pack(fill="x", pady=(4, 0))
        for label, cmd in (
                ("View / Edit",     self._edit),
                ("Publish",         self._publish),
                ("Close",           self._close),
                ("Archive",         self._archive),
                ("Submit response", self._submit),
                ("Change status",   self._set_status),
                ("Delete",          self._delete),
                ("Refresh",         self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _build_bottom(self) -> None:
        nb = ttk.Notebook(self.bottom)
        nb.pack(fill="both", expand=True)

        self.responses_frame = ttk.Frame(nb)
        nb.add(self.responses_frame, text="Responses")
        bar = ttk.Frame(self.responses_frame)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Button(bar, text="View",
                    command=self._view_response).pack(side="right",
                                                          padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_response).pack(side="right",
                                                            padx=4)
        rcols = ("id", "submitted_on", "respondent", "role")
        self.resp_tree = ttk.Treeview(self.responses_frame,
                                          columns=rcols,
                                          show="headings",
                                          selectmode="browse")
        rwidths = {"id": 60, "submitted_on": 110,
                     "respondent": 200, "role": 160}
        for c in rcols:
            self.resp_tree.heading(c,
                                       text=c.replace("_", " ").title())
            self.resp_tree.column(c, width=rwidths[c],
                                      anchor=("center"
                                               if c == "id" else "w"))
        rvsb = ttk.Scrollbar(self.responses_frame,
                                orient="vertical",
                                command=self.resp_tree.yview)
        self.resp_tree.configure(yscrollcommand=rvsb.set)
        self.resp_tree.pack(side="left", fill="both", expand=True)
        rvsb.pack(side="right", fill="y")
        self.resp_tree.bind("<Double-Button-1>",
                                lambda _e: self._view_response())

        self.stats_frame = ttk.Frame(nb)
        nb.add(self.stats_frame, text="Question Stats")
        self.stats_text = tk.Text(self.stats_frame, wrap="word",
                                       font=("TkFixedFont", 10))
        self.stats_text.pack(fill="both", expand=True)
        self.stats_text.config(state="disabled")

    def _clear(self) -> None:
        self.f_aud.current(0)
        self.f_name.delete(0, "end")
        self.f_creator.delete(0, "end")
        if self.f_status is not None:
            self.f_status.current(0)
        self.refresh()

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_aud.get():
            f["audience"] = self.f_aud.get()
        if self.f_name.get().strip():
            f["name_like"] = self.f_name.get().strip()
        if self.f_creator.get().strip():
            f["created_by_like"] = self.f_creator.get().strip()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "open":
            f["open_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_surveys(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Surveys", str(e),
                                    parent=self.frame)
            return
        for s in rows:
            rc = data.response_count(s.survey_id)
            self.tree.insert(
                "", "end", iid=str(s.survey_id),
                values=(s.survey_id, s.name, s.audience,
                         s.status, s.open_on or "—",
                         s.close_on or "—",
                         len(s.questions), rc,
                         s.created_by or "—"),
                tags=(s.status,))
        self.count.config(text=f"{len(rows)} survey(s)")
        self._refresh_bottom()

    def _selected(self) -> Survey | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Surveys",
                                  "Select a survey first.",
                                  parent=self.frame)
            return None
        return data.get_survey(int(sel[0]))

    def _refresh_bottom(self) -> None:
        for iid in self.resp_tree.get_children():
            self.resp_tree.delete(iid)
        self.stats_text.config(state="normal")
        self.stats_text.delete("1.0", "end")
        sel = self.tree.selection()
        if not sel:
            self.stats_text.config(state="disabled")
            return
        sid = int(sel[0])
        s = data.get_survey(sid)
        if s is None:
            self.stats_text.config(state="disabled")
            return
        for r in data.list_responses(sid):
            name = (r.respondent_name
                      or ("anonymous" if r.anonymous else "—"))
            self.resp_tree.insert(
                "", "end", iid=str(r.response_id),
                values=(r.response_id, r.submitted_on,
                         name, r.respondent_role or "—"))
        # Stats
        stats = data.question_stats(sid)
        self.stats_text.insert("end",
                                  f"Stats for {s.name!r}  "
                                  f"({data.response_count(sid)} "
                                  f"responses)\n")
        self.stats_text.insert("end", "-" * 60 + "\n\n")
        for st in stats:
            self.stats_text.insert("end",
                                      f"Q{st.index+1}. [{st.type}] "
                                      f"{st.prompt}\n"
                                      f"   answered: {st.answered}  "
                                      f"skipped: {st.skipped}\n")
            if st.mean is not None:
                self.stats_text.insert("end",
                                          f"   mean: {st.mean}\n")
            if st.counts:
                for k, v in sorted(st.counts.items(),
                                      key=lambda kv: -kv[1]):
                    self.stats_text.insert("end",
                                              f"     {k:<24}: {v}\n")
            if st.text_samples:
                for sample in st.text_samples:
                    self.stats_text.insert("end",
                                              f"     - {sample[:60]}\n")
            self.stats_text.insert("end", "\n")
        self.stats_text.config(state="disabled")

    def _new(self) -> None:
        if SurveyEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        s = self._selected()
        if s and SurveyEditor(self.frame,
                                    survey=s).result is not None:
            self.refresh()

    def _publish(self) -> None:
        s = self._selected()
        if not s:
            return
        try:
            data.publish(s.survey_id)
        except ValidationError as exc:
            messagebox.showerror("Surveys", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _close(self) -> None:
        s = self._selected()
        if not s:
            return
        try:
            data.close_survey(s.survey_id)
        except ValidationError as exc:
            messagebox.showerror("Surveys", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _archive(self) -> None:
        s = self._selected()
        if not s:
            return
        try:
            data.archive(s.survey_id)
        except ValidationError as exc:
            messagebox.showerror("Surveys", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _submit(self) -> None:
        s = self._selected()
        if not s:
            return
        if s.status != "Open":
            messagebox.showinfo("Surveys",
                                  f"Survey is {s.status}, not Open.",
                                  parent=self.frame)
            return
        if ResponseDialog(self.frame,
                              survey=s).result is not None:
            self.refresh()

    def _set_status(self) -> None:
        s = self._selected()
        if not s:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES), default=s.status)
        if not new:
            return
        try:
            data.set_status(s.survey_id, new)
        except ValidationError as exc:
            messagebox.showerror("Surveys", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        s = self._selected()
        if not s:
            return
        if not messagebox.askyesno(
                "Surveys",
                f"Delete survey #{s.survey_id} and all responses?",
                parent=self.frame):
            return
        data.delete_survey(s.survey_id)
        self.refresh()

    def _view_response(self) -> None:
        sel_s = self.tree.selection()
        sel_r = self.resp_tree.selection()
        if not sel_s or not sel_r:
            return
        s = data.get_survey(int(sel_s[0]))
        r = data.get_response(int(sel_r[0]))
        if not s or not r:
            return
        ResponseViewer(self.frame, survey=s, response=r)

    def _delete_response(self) -> None:
        sel_r = self.resp_tree.selection()
        if not sel_r:
            return
        rid = int(sel_r[0])
        if not messagebox.askyesno("Surveys",
                                       f"Delete response #{rid}?",
                                       parent=self.frame):
            return
        data.delete_response(rid)
        self._refresh_bottom()
        self.refresh()


class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Surveys Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total surveys      : {s.total}\n"
                            f"Drafts             : {s.drafts}\n"
                            f"Open               : {s.open_count}\n"
                            f"Closed             : {s.closed}\n"
                            f"Archived           : {s.archived}\n"
                            f"Total responses    : {s.total_responses}\n\n")
        self.text.insert("end", "By audience:\n")
        for k in AUDIENCES:
            n = s.by_audience.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.config(state="disabled")


# ── Survey Editor ────────────────────────────────────────────

class SurveyEditor:
    def __init__(self, parent, *,
                 survey: Survey | None = None) -> None:
        self.survey = survey
        self.result: Survey | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit survey #{survey.survey_id}"
                          if survey else "New survey")
        self.win.geometry("900x780")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if survey:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.bools: dict[str, tk.BooleanVar] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        entry(0, 0, "Name*", "name", width=48)
        combo(1, 0, "Audience*", "audience", AUDIENCES)
        combo(1, 2, "Status*", "status", STATUSES)
        entry(2, 0, "Open on", "open_on")
        entry(2, 2, "Close on", "close_on")
        entry(3, 0, "Created by", "created_by")
        self.bools["anonymous"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(body, text="Anonymous responses",
                         variable=self.bools["anonymous"]).grid(
            row=3, column=2, columnspan=2, sticky="w",
            padx=4, pady=2)

        ttk.Label(body, text="Description").grid(
            row=4, column=0, sticky="nw", padx=4, pady=(6, 2))
        self.texts["description"] = tk.Text(body, height=3,
                                                width=74,
                                                wrap="word")
        self.texts["description"].grid(row=4, column=1,
                                            columnspan=3,
                                            sticky="ew", padx=4,
                                            pady=(6, 2))
        ttk.Label(body, text="Notes").grid(
            row=5, column=0, sticky="nw", padx=4, pady=(6, 2))
        self.texts["notes"] = tk.Text(body, height=2, width=74,
                                          wrap="word")
        self.texts["notes"].grid(row=5, column=1, columnspan=3,
                                      sticky="ew", padx=4,
                                      pady=(6, 2))

        # Questions area
        qframe = ttk.LabelFrame(body, text="Questions")
        qframe.grid(row=6, column=0, columnspan=4,
                       sticky="nsew", padx=4, pady=(8, 4))
        body.grid_rowconfigure(6, weight=1)
        qframe.grid_columnconfigure(0, weight=1)
        qframe.grid_rowconfigure(0, weight=1)
        qcols = ("idx", "type", "prompt", "required",
                   "choices")
        self.qtree = ttk.Treeview(qframe, columns=qcols,
                                       show="headings",
                                       selectmode="browse",
                                       height=8)
        qwidths = {"idx": 40, "type": 110, "prompt": 360,
                     "required": 80, "choices": 240}
        for c in qcols:
            self.qtree.heading(c,
                                   text=c.replace("_", " ").title())
            self.qtree.column(c, width=qwidths[c],
                                  anchor=("center"
                                           if c in ("idx",
                                                      "required")
                                           else "w"))
        qvsb = ttk.Scrollbar(qframe, orient="vertical",
                                command=self.qtree.yview)
        self.qtree.configure(yscrollcommand=qvsb.set)
        self.qtree.grid(row=0, column=0, sticky="nsew")
        qvsb.grid(row=0, column=1, sticky="ns")

        qbar = ttk.Frame(qframe)
        qbar.grid(row=1, column=0, columnspan=2, sticky="ew",
                     pady=(4, 0))
        ttk.Button(qbar, text="Add",
                    command=self._add_q).pack(side="left", padx=2)
        ttk.Button(qbar, text="Edit",
                    command=self._edit_q).pack(side="left", padx=2)
        ttk.Button(qbar, text="Delete",
                    command=self._delete_q).pack(side="left", padx=2)
        ttk.Button(qbar, text="Move up",
                    command=lambda: self._move_q(-1)).pack(
            side="left", padx=2)
        ttk.Button(qbar, text="Move down",
                    command=lambda: self._move_q(1)).pack(
            side="left", padx=2)
        self.locked_lbl = ttk.Label(qbar, text="",
                                          foreground="#7a5800")
        self.locked_lbl.pack(side="right", padx=8)

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.questions: list[Question] = []
        self.vars["audience"].set(DEFAULT_AUDIENCE)
        self.vars["status"].set(DEFAULT_STATUS)
        self._refresh_q()

    def _load(self) -> None:
        s = self.survey
        assert s is not None
        for key in ("name", "audience", "status",
                     "open_on", "close_on", "created_by"):
            self.vars[key].set(getattr(s, key) or "")
        self.bools["anonymous"].set(s.anonymous)
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(s, k) or "")
        self.questions = [Question.from_dict(q.to_dict())
                              for q in s.questions]
        if not s.is_editable:
            self.locked_lbl.config(
                text="Questions locked (past Draft)")
        self._refresh_q()

    @property
    def _locked(self) -> bool:
        return bool(self.survey and not self.survey.is_editable)

    def _refresh_q(self) -> None:
        for iid in self.qtree.get_children():
            self.qtree.delete(iid)
        for i, q in enumerate(self.questions, 1):
            self.qtree.insert(
                "", "end", iid=str(i),
                values=(i, q.type, q.prompt,
                         "yes" if q.required else "no",
                         ", ".join(q.choices)
                         if q.choices else "—"))

    def _selected_q_idx(self) -> int | None:
        sel = self.qtree.selection()
        if not sel:
            messagebox.showinfo("Surveys",
                                  "Select a question first.",
                                  parent=self.win)
            return None
        return int(sel[0]) - 1

    def _add_q(self) -> None:
        if self._locked:
            messagebox.showinfo("Surveys",
                                  "Questions are locked.",
                                  parent=self.win)
            return
        q = QuestionEditor(self.win).result
        if q is not None:
            self.questions.append(q)
            self._refresh_q()

    def _edit_q(self) -> None:
        if self._locked:
            messagebox.showinfo("Surveys",
                                  "Questions are locked.",
                                  parent=self.win)
            return
        idx = self._selected_q_idx()
        if idx is None:
            return
        q = QuestionEditor(self.win,
                              existing=self.questions[idx]).result
        if q is not None:
            self.questions[idx] = q
            self._refresh_q()

    def _delete_q(self) -> None:
        if self._locked:
            messagebox.showinfo("Surveys",
                                  "Questions are locked.",
                                  parent=self.win)
            return
        idx = self._selected_q_idx()
        if idx is None:
            return
        del self.questions[idx]
        self._refresh_q()

    def _move_q(self, direction: int) -> None:
        if self._locked:
            return
        idx = self._selected_q_idx()
        if idx is None:
            return
        new_idx = idx + direction
        if not (0 <= new_idx < len(self.questions)):
            return
        self.questions[idx], self.questions[new_idx] = (
            self.questions[new_idx], self.questions[idx])
        self._refresh_q()
        self.qtree.selection_set(str(new_idx + 1))

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        payload["anonymous"] = self.bools["anonymous"].get()
        payload["questions"] = self.questions
        try:
            if self.survey:
                self.result = data.update_survey(
                    self.survey.survey_id, payload)
            else:
                self.result = data.create_survey(payload)
        except ValidationError as exc:
            messagebox.showerror("Surveys", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class QuestionEditor:
    def __init__(self, parent, *,
                 existing: Question | None = None) -> None:
        self.existing = existing
        self.result: Question | None = None
        self.win = tk.Toplevel(parent)
        self.win.title("Edit question" if existing
                          else "New question")
        self.win.geometry("560x440")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Prompt*").grid(
            row=0, column=0, sticky="nw", padx=4, pady=4)
        self.prompt = tk.Text(body, height=3, width=50,
                                  wrap="word")
        if existing:
            self.prompt.insert("1.0", existing.prompt)
        self.prompt.grid(row=0, column=1, sticky="ew",
                            padx=4, pady=4)
        ttk.Label(body, text="Type*").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.qtype = tk.StringVar(
            value=existing.type if existing else "Text")
        self.qtype_combo = ttk.Combobox(body,
                                              textvariable=self.qtype,
                                              values=QUESTION_TYPES,
                                              state="readonly")
        self.qtype_combo.grid(row=1, column=1, sticky="w",
                                  padx=4, pady=4)
        self.qtype_combo.bind("<<ComboboxSelected>>",
                                  lambda _e: self._toggle_choices())
        ttk.Label(body, text="Choices").grid(
            row=2, column=0, sticky="nw", padx=4, pady=4)
        self.choices = tk.Text(body, height=6, width=50,
                                   wrap="word")
        if existing and existing.choices:
            self.choices.insert("1.0", "\n".join(existing.choices))
        self.choices.grid(row=2, column=1, sticky="ew",
                             padx=4, pady=4)
        ttk.Label(body, text="(one per line, only used "
                              "for Single/Multi Choice)").grid(
            row=3, column=1, sticky="w", padx=4)
        self.required = tk.BooleanVar(
            value=existing.required if existing else False)
        ttk.Checkbutton(body, text="Required",
                         variable=self.required).grid(
            row=4, column=1, sticky="w", padx=4, pady=8)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self._toggle_choices()
        self.win.wait_window()

    def _toggle_choices(self) -> None:
        active = self.qtype.get() in ("Single Choice",
                                           "Multi Choice")
        state = "normal" if active else "disabled"
        self.choices.config(state=state)

    def _save(self) -> None:
        prompt = self.prompt.get("1.0", "end").strip()
        if not prompt:
            messagebox.showerror("Surveys",
                                    "Prompt required.",
                                    parent=self.win)
            return
        qtype = self.qtype.get()
        choices: list[str] = []
        if qtype in ("Single Choice", "Multi Choice"):
            raw = self.choices.get("1.0", "end")
            choices = [line.strip()
                          for line in raw.splitlines()
                          if line.strip()]
            if not choices:
                messagebox.showerror(
                    "Surveys",
                    f"{qtype} requires at least one choice.",
                    parent=self.win)
                return
        self.result = Question(
            prompt=prompt, type=qtype,
            choices=choices, required=self.required.get())
        self.win.destroy()


# ── Response dialog & viewer ──────────────────────────────────

class ResponseDialog:
    def __init__(self, parent, *, survey: Survey) -> None:
        self.survey = survey
        self.result: Response | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Respond — {survey.name}")
        self.win.geometry("700x720")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)

        self.anon = tk.BooleanVar(value=survey.anonymous)
        ttk.Checkbutton(body, text="Anonymous",
                         variable=self.anon).grid(
            row=0, column=0, columnspan=2, sticky="w",
            padx=4, pady=4)
        ttk.Label(body, text="Respondent name").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.name = tk.StringVar()
        ttk.Entry(body, textvariable=self.name).grid(
            row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Respondent role").grid(
            row=2, column=0, sticky="w", padx=4, pady=4)
        self.role = tk.StringVar()
        ttk.Entry(body, textvariable=self.role).grid(
            row=2, column=1, sticky="ew", padx=4, pady=4)

        # Scrollable question area
        canvas = tk.Canvas(body, borderwidth=0,
                              highlightthickness=0)
        canvas.grid(row=3, column=0, columnspan=2,
                      sticky="nsew", padx=4, pady=(8, 4))
        body.grid_rowconfigure(3, weight=1)
        cvsb = ttk.Scrollbar(body, orient="vertical",
                                command=canvas.yview)
        cvsb.grid(row=3, column=2, sticky="ns")
        canvas.configure(yscrollcommand=cvsb.set)
        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                      lambda _e: canvas.configure(
                          scrollregion=canvas.bbox("all")))

        self.q_widgets: list[tuple[Question, Any]] = []
        for idx, q in enumerate(survey.questions):
            f = ttk.Frame(inner)
            f.pack(fill="x", padx=4, pady=4)
            marker = " *" if q.required else ""
            ttk.Label(f, text=f"Q{idx+1}{marker} "
                            f"[{q.type}] {q.prompt}",
                       wraplength=600,
                       font=("TkDefaultFont", 10, "bold")).pack(
                anchor="w")
            widget: Any
            if q.type == "Likert":
                widget = tk.StringVar()
                ttk.Combobox(f, textvariable=widget,
                              values=("", "1", "2", "3", "4", "5"),
                              state="readonly", width=6).pack(
                    anchor="w", pady=2)
            elif q.type == "Yes/No":
                widget = tk.StringVar()
                ttk.Combobox(f, textvariable=widget,
                              values=("", "Yes", "No"),
                              state="readonly", width=8).pack(
                    anchor="w", pady=2)
            elif q.type == "Single Choice":
                widget = tk.StringVar()
                ttk.Combobox(f, textvariable=widget,
                              values=("",) + tuple(q.choices),
                              state="readonly", width=40).pack(
                    anchor="w", pady=2)
            elif q.type == "Multi Choice":
                widget = {c: tk.BooleanVar() for c in q.choices}
                for c in q.choices:
                    ttk.Checkbutton(f, text=c,
                                     variable=widget[c]).pack(
                        anchor="w")
            elif q.type == "Number":
                widget = tk.StringVar()
                ttk.Entry(f, textvariable=widget,
                            width=20).pack(anchor="w", pady=2)
            else:  # Text
                widget = tk.Text(f, height=3, width=60,
                                   wrap="word")
                widget.pack(anchor="w", pady=2)
            self.q_widgets.append((q, widget))

        ttk.Label(body, text="Notes").grid(
            row=4, column=0, sticky="nw", padx=4, pady=4)
        self.notes = tk.Text(body, height=3, width=60,
                                wrap="word")
        self.notes.grid(row=4, column=1, sticky="ew",
                          padx=4, pady=4)

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Submit",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        answers: dict[int, Any] = {}
        for idx, (q, w) in enumerate(self.q_widgets):
            if q.type == "Multi Choice":
                picks = [c for c, v in w.items() if v.get()]
                if picks:
                    answers[idx] = picks
            elif q.type == "Text":
                val = w.get("1.0", "end").rstrip()
                if val:
                    answers[idx] = val
            else:
                val = w.get().strip()
                if val:
                    answers[idx] = val
        try:
            self.result = data.submit_response(
                self.survey.survey_id, answers=answers,
                respondent_name=self.name.get().strip() or None,
                respondent_role=self.role.get().strip() or None,
                anonymous=self.anon.get(),
                notes=self.notes.get("1.0", "end").rstrip()
                or None)
        except ValidationError as exc:
            messagebox.showerror("Surveys", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class ResponseViewer:
    def __init__(self, parent, *,
                 survey: Survey, response: Response) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title(f"Response #{response.response_id}")
        self.win.geometry("640x600")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        text = tk.Text(self.win, wrap="word",
                         font=("TkFixedFont", 10))
        text.pack(fill="both", expand=True, padx=8, pady=8)
        name = (response.respondent_name
                  or ("anonymous" if response.anonymous
                       else "—"))
        text.insert("end",
                       f"Response #{response.response_id}\n"
                       f"Survey: {survey.name}\n"
                       f"Submitted: {response.submitted_on}\n"
                       f"By: {name}"
                       + (f"  ({response.respondent_role})"
                            if response.respondent_role else "")
                       + "\n" + "=" * 60 + "\n\n")
        for idx, q in enumerate(survey.questions):
            v = response.answers.get(idx)
            if v is None:
                display = "(skipped)"
            elif isinstance(v, list):
                display = ", ".join(str(x) for x in v)
            else:
                display = str(v)
            text.insert("end", f"Q{idx+1}. [{q.type}] {q.prompt}\n")
            text.insert("end", f"   → {display}\n\n")
        if response.notes:
            text.insert("end", f"Notes: {response.notes}\n")
        text.config(state="disabled")
        ttk.Button(self.win, text="Close",
                    command=self.win.destroy).pack(pady=(0, 8))


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("320x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_surveys_window"]
