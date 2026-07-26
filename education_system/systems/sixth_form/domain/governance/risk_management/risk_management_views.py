"""Tkinter views for Sixth Form Risk Management."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any

from education_system.platform import branding
from education_system.systems.sixth_form.domain.governance.risk_management import (
    risk_management as data,
)
from education_system.systems.sixth_form.domain.governance.risk_management.risk_management import (
    ACTION_STATUSES,
    CATEGORIES,
    DEFAULT_ACTION_STATUS,
    DEFAULT_CATEGORY,
    DEFAULT_STATUS,
    DEFAULT_TREATMENT,
    IMPACT_LABELS,
    LIKELIHOOD_LABELS,
    STATUSES,
    TREATMENTS,
    ValidationError,
    score_band,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

BAND_COLOURS = {
    "Low":      "#d8f5d8",
    "Medium":   "#fff3c2",
    "High":     "#ffd9b3",
    "Critical": "#ffb3b3",
    "—":        "#f5f5f5",
}


def open_risk_management_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Risk Management — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    RisksTab(nb)
    ActionsTab(nb)
    ReviewsTab(nb)
    HeatmapTab(nb)
    OverviewTab(nb)


def _set_text(text: tk.Text, body: str) -> None:
    text.configure(state="normal")
    text.delete("1.0", "end")
    text.insert("1.0", body)
    text.configure(state="disabled")


# ══ Risks tab ══════════════════════════════════════════════════════

class RisksTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Risk Register")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Show:").pack(side="left")
        self.filter_var = tk.StringVar(value="open")
        for lbl, val in (("Open", "open"),
                          ("High / Critical", "hi"),
                          ("Review due", "due"),
                          ("All", "all")):
            ttk.Radiobutton(bar, text=lbl, value=val,
                             variable=self.filter_var,
                             command=self.refresh).pack(side="left")
        ttk.Label(bar, text="   Category:").pack(side="left")
        self.cat_cb = ttk.Combobox(
            bar, values=("",) + CATEGORIES,
            state="readonly", width=14)
        self.cat_cb.current(0)
        self.cat_cb.pack(side="left", padx=4)
        self.cat_cb.bind("<<ComboboxSelected>>",
                          lambda _e: self.refresh())
        ttk.Label(bar, text="Search:").pack(side="left")
        self.search_e = ttk.Entry(bar, width=22)
        self.search_e.pack(side="left", padx=4)
        self.search_e.bind("<Return>", lambda _e: self.refresh())
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="New…",
                    command=self._new).pack(side="right")
        ttk.Button(bar, text="Edit…",
                    command=self._edit).pack(side="right", padx=4)
        ttk.Button(bar, text="Add action…",
                    command=self._add_action).pack(side="right", padx=4)
        ttk.Button(bar, text="Add review…",
                    command=self._add_review).pack(side="right", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="right", padx=4)

        cols = ("risk_id", "title", "category", "owner",
                "likelihood", "impact", "score", "band",
                "status", "next_review")
        widths = {"risk_id": 50, "title": 280, "category": 110,
                   "owner": 100, "likelihood": 30, "impact": 30,
                   "score": 55, "band": 80, "status": 100,
                   "next_review": 100}
        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(wrap, columns=cols,
                                    show="headings", height=22)
        for c, h in zip(cols, ("#", "Title", "Category", "Owner",
                                  "L", "I", "Score", "Band",
                                  "Status", "Next review")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c], anchor="w")
        for band, colour in BAND_COLOURS.items():
            self.tree.tag_configure(f"band_{band}", background=colour)
        vs = ttk.Scrollbar(wrap, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._edit())

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        filt = self.filter_var.get()
        cat = self.cat_cb.get() or None
        search = self.search_e.get().strip() or None
        kwargs: dict[str, Any] = {"category": cat, "search": search}
        if filt == "open":
            kwargs["open_only"] = True
        elif filt == "hi":
            kwargs["open_only"] = True
            kwargs["min_score"] = 10
        elif filt == "due":
            kwargs["open_only"] = True
            kwargs["review_due_only"] = True
        for r in data.list_risks(**kwargs):
            self.tree.insert("", "end", iid=str(r.risk_id),
                              values=(r.risk_id, r.title, r.category,
                                       r.owner or "",
                                       r.likelihood, r.impact,
                                       r.inherent_score,
                                       r.inherent_band, r.status,
                                       r.next_review or ""),
                              tags=(f"band_{r.inherent_band}",))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _new(self) -> None:
        RiskDialog(self.frame, on_save=self._save_new)

    def _save_new(self, payload: dict[str, Any]) -> None:
        try:
            data.create_risk(payload)
        except ValidationError as e:
            messagebox.showerror("Save", str(e))
            return
        self.refresh()

    def _edit(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        existing = data.get_risk(rid)
        if existing is None:
            return
        RiskDialog(self.frame, existing=existing,
                    on_save=lambda p: self._save_edit(rid, p))

    def _save_edit(self, rid: int, payload: dict[str, Any]) -> None:
        try:
            data.update_risk(rid, payload)
        except ValidationError as e:
            messagebox.showerror("Save", str(e))
            return
        self.refresh()

    def _delete(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete risk #{rid}?\n"
                "(also deletes its actions and reviews)"):
            return
        data.delete_risk(rid)
        self.refresh()

    def _add_action(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Add action", "Pick a risk first.")
            return
        ActionDialog(self.frame, risk_id=rid,
                      on_save=lambda p: self._save_new_action(rid, p))

    def _save_new_action(self, rid: int,
                           payload: dict[str, Any]) -> None:
        try:
            data.add_action(rid, payload)
        except ValidationError as e:
            messagebox.showerror("Add action", str(e))
            return

    def _add_review(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Add review", "Pick a risk first.")
            return
        ReviewDialog(self.frame, risk_id=rid,
                      on_save=lambda p: self._save_review(rid, p))

    def _save_review(self, rid: int,
                       payload: dict[str, Any]) -> None:
        try:
            data.add_review(rid, payload)
        except ValidationError as e:
            messagebox.showerror("Add review", str(e))
            return
        self.refresh()


class RiskDialog(tk.Toplevel):
    def __init__(self, master, existing: data.Risk | None = None, *,
                 on_save) -> None:
        super().__init__(master)
        self.title("Risk")
        self.geometry("720x780")
        self.transient(master.winfo_toplevel())
        self.after_idle(self.grab_set)
        self._existing = existing
        self._on_save = on_save
        self._build()

    def _build(self) -> None:
        wrap = ttk.Frame(self, padding=10)
        wrap.pack(fill="both", expand=True)
        wrap.columnconfigure(1, weight=1)

        self.title_e = ttk.Entry(wrap)
        self.cat_cb = ttk.Combobox(wrap, values=CATEGORIES,
                                      state="readonly")
        self.desc_t = tk.Text(wrap, height=3, width=40)
        self.owner_e = ttk.Entry(wrap)
        self.ident_e = ttk.Entry(wrap)
        self.status_cb = ttk.Combobox(wrap, values=STATUSES,
                                          state="readonly")
        self.like_cb = ttk.Combobox(
            wrap, values=[f"{n} ({LIKELIHOOD_LABELS[n]})"
                          for n in range(1, 6)],
            state="readonly", width=20)
        self.imp_cb = ttk.Combobox(
            wrap, values=[f"{n} ({IMPACT_LABELS[n]})"
                          for n in range(1, 6)],
            state="readonly", width=20)
        self.controls_t = tk.Text(wrap, height=3, width=40)
        self.res_like_cb = ttk.Combobox(
            wrap, values=("",) + tuple(
                f"{n} ({LIKELIHOOD_LABELS[n]})" for n in range(1, 6)),
            state="readonly", width=20)
        self.res_imp_cb = ttk.Combobox(
            wrap, values=("",) + tuple(
                f"{n} ({IMPACT_LABELS[n]})" for n in range(1, 6)),
            state="readonly", width=20)
        self.treat_cb = ttk.Combobox(wrap, values=TREATMENTS,
                                          state="readonly")
        self.freq_e = ttk.Entry(wrap, width=10)
        self.last_e = ttk.Entry(wrap)
        self.next_e = ttk.Entry(wrap)
        self.notes_t = tk.Text(wrap, height=3, width=40)

        fields = [
            ("Title:",          self.title_e),
            ("Category:",       self.cat_cb),
            ("Description:",    self.desc_t),
            ("Owner:",          self.owner_e),
            ("Identified date:", self.ident_e),
            ("Status:",         self.status_cb),
            ("Likelihood:",     self.like_cb),
            ("Impact:",         self.imp_cb),
            ("Controls:",       self.controls_t),
            ("Residual likelihood:", self.res_like_cb),
            ("Residual impact:", self.res_imp_cb),
            ("Treatment:",      self.treat_cb),
            ("Review every (days):", self.freq_e),
            ("Last reviewed:",  self.last_e),
            ("Next review:",    self.next_e),
            ("Notes:",          self.notes_t),
        ]
        for i, (lbl, w) in enumerate(fields):
            ttk.Label(wrap, text=lbl).grid(row=i, column=0,
                                              sticky="ne",
                                              padx=6, pady=2)
            w.grid(row=i, column=1, sticky="ew",
                   padx=6, pady=2)

        btns = ttk.Frame(wrap)
        btns.grid(row=len(fields), column=0, columnspan=2,
                   sticky="e", pady=10)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="left", padx=4)

        today = _date.today().isoformat()
        if self._existing is None:
            self.cat_cb.set(DEFAULT_CATEGORY)
            self.ident_e.insert(0, today)
            self.status_cb.set(DEFAULT_STATUS)
            self.like_cb.current(2)
            self.imp_cb.current(2)
            self.res_like_cb.set("")
            self.res_imp_cb.set("")
            self.treat_cb.set(DEFAULT_TREATMENT)
            self.freq_e.insert(0, "90")
        else:
            e = self._existing
            self.title_e.insert(0, e.title)
            self.cat_cb.set(e.category)
            self.desc_t.insert("1.0", e.description or "")
            self.owner_e.insert(0, e.owner or "")
            self.ident_e.insert(0, e.identified_date)
            self.status_cb.set(e.status)
            self.like_cb.current(int(e.likelihood) - 1)
            self.imp_cb.current(int(e.impact) - 1)
            self.controls_t.insert("1.0", e.controls or "")
            self.res_like_cb.set(
                "" if e.residual_likelihood is None
                else f"{e.residual_likelihood} "
                     f"({LIKELIHOOD_LABELS[e.residual_likelihood]})")
            self.res_imp_cb.set(
                "" if e.residual_impact is None
                else f"{e.residual_impact} "
                     f"({IMPACT_LABELS[e.residual_impact]})")
            self.treat_cb.set(e.treatment)
            self.freq_e.insert(0, str(e.review_frequency_days))
            self.last_e.insert(0, e.last_reviewed or "")
            self.next_e.insert(0, e.next_review or "")
            self.notes_t.insert("1.0", e.notes or "")

    @staticmethod
    def _parse_score(v: str) -> int | None:
        v = (v or "").strip()
        if not v:
            return None
        return int(v.split(" ", 1)[0])

    def _save(self) -> None:
        payload = {
            "title":           self.title_e.get().strip(),
            "category":        self.cat_cb.get(),
            "description":     self.desc_t.get("1.0", "end").strip(),
            "owner":           self.owner_e.get().strip(),
            "identified_date": self.ident_e.get().strip(),
            "status":          self.status_cb.get(),
            "likelihood":      self._parse_score(self.like_cb.get()),
            "impact":          self._parse_score(self.imp_cb.get()),
            "controls":        self.controls_t.get(
                "1.0", "end").strip(),
            "residual_likelihood":
                self._parse_score(self.res_like_cb.get()),
            "residual_impact":
                self._parse_score(self.res_imp_cb.get()),
            "treatment":       self.treat_cb.get(),
            "review_frequency_days": self.freq_e.get().strip() or 90,
            "last_reviewed":   self.last_e.get().strip(),
            "next_review":     self.next_e.get().strip(),
            "notes":           self.notes_t.get("1.0", "end").strip(),
        }
        if not payload["title"]:
            messagebox.showerror("Save", "Title is required.")
            return
        self._on_save(payload)
        self.destroy()


# ══ Actions tab ════════════════════════════════════════════════════

class ActionsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Actions")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        self.filter_var = tk.StringVar(value="open")
        for lbl, val in (("Open", "open"),
                          ("Overdue", "overdue"),
                          ("All", "all")):
            ttk.Radiobutton(bar, text=lbl, value=val,
                             variable=self.filter_var,
                             command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Edit…",
                    command=self._edit).pack(side="right")
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="right", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right", padx=4)

        cols = ("action_id", "risk_id", "description", "owner",
                "due_date", "status", "completed")
        widths = {"action_id": 60, "risk_id": 60,
                   "description": 360, "owner": 120,
                   "due_date": 100, "status": 100, "completed": 100}
        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(wrap, columns=cols,
                                    show="headings", height=22)
        for c, h in zip(cols, ("#", "Risk", "Description", "Owner",
                                  "Due", "Status", "Completed")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.tag_configure("overdue", background="#ffe2e2")
        self.tree.tag_configure("done", foreground="#888")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._edit())

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        filt = self.filter_var.get()
        if filt == "open":
            rows = data.list_actions(open_only=True)
        elif filt == "overdue":
            rows = data.list_actions(overdue_only=True)
        else:
            rows = data.list_actions()
        for a in rows:
            tags = []
            if a.is_overdue:
                tags.append("overdue")
            if a.is_done:
                tags.append("done")
            self.tree.insert("", "end", iid=str(a.action_id),
                              values=(a.action_id, a.risk_id,
                                       a.description,
                                       a.owner or "",
                                       a.due_date or "", a.status,
                                       a.completed_date or ""),
                              tags=tuple(tags))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _edit(self) -> None:
        aid = self._selected_id()
        if aid is None:
            return
        existing = data.get_action(aid)
        if existing is None:
            return
        ActionDialog(self.frame, risk_id=existing.risk_id,
                      existing=existing,
                      on_save=lambda p: self._save(aid, p))

    def _save(self, aid: int, payload: dict[str, Any]) -> None:
        try:
            data.update_action(aid, payload)
        except ValidationError as e:
            messagebox.showerror("Edit", str(e))
            return
        self.refresh()

    def _delete(self) -> None:
        aid = self._selected_id()
        if aid is None:
            return
        if not messagebox.askyesno("Delete",
                                      f"Delete action #{aid}?"):
            return
        data.delete_action(aid)
        self.refresh()


class ActionDialog(tk.Toplevel):
    def __init__(self, master, *, risk_id: int,
                 existing: data.Action | None = None,
                 on_save) -> None:
        super().__init__(master)
        self.title(f"Action on risk #{risk_id}")
        self.geometry("620x480")
        self.transient(master.winfo_toplevel())
        self.after_idle(self.grab_set)
        self._risk_id = risk_id
        self._existing = existing
        self._on_save = on_save
        self._build()

    def _build(self) -> None:
        wrap = ttk.Frame(self, padding=10)
        wrap.pack(fill="both", expand=True)
        wrap.columnconfigure(1, weight=1)
        self.desc_t = tk.Text(wrap, height=3, width=40)
        self.owner_e = ttk.Entry(wrap)
        self.due_e = ttk.Entry(wrap)
        self.status_cb = ttk.Combobox(wrap, values=ACTION_STATUSES,
                                          state="readonly")
        self.completed_e = ttk.Entry(wrap)
        self.evidence_e = ttk.Entry(wrap)
        self.notes_t = tk.Text(wrap, height=3, width=40)

        fields = [
            ("Description:",    self.desc_t),
            ("Owner:",          self.owner_e),
            ("Due date:",       self.due_e),
            ("Status:",         self.status_cb),
            ("Completed date:", self.completed_e),
            ("Evidence:",       self.evidence_e),
            ("Notes:",          self.notes_t),
        ]
        for i, (lbl, w) in enumerate(fields):
            ttk.Label(wrap, text=lbl).grid(row=i, column=0,
                                              sticky="ne",
                                              padx=6, pady=2)
            w.grid(row=i, column=1, sticky="ew",
                   padx=6, pady=2)
        btns = ttk.Frame(wrap)
        btns.grid(row=len(fields), column=0, columnspan=2,
                   sticky="e", pady=10)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="left", padx=4)

        if self._existing is None:
            self.status_cb.set(DEFAULT_ACTION_STATUS)
        else:
            e = self._existing
            self.desc_t.insert("1.0", e.description)
            self.owner_e.insert(0, e.owner or "")
            self.due_e.insert(0, e.due_date or "")
            self.status_cb.set(e.status)
            self.completed_e.insert(0, e.completed_date or "")
            self.evidence_e.insert(0, e.evidence or "")
            self.notes_t.insert("1.0", e.notes or "")

    def _save(self) -> None:
        payload = {
            "description":    self.desc_t.get("1.0", "end").strip(),
            "owner":          self.owner_e.get().strip(),
            "due_date":       self.due_e.get().strip(),
            "status":         self.status_cb.get(),
            "completed_date": self.completed_e.get().strip(),
            "evidence":       self.evidence_e.get().strip(),
            "notes":          self.notes_t.get("1.0", "end").strip(),
        }
        if not payload["description"]:
            messagebox.showerror("Save", "Description is required.")
            return
        self._on_save(payload)
        self.destroy()


class ReviewDialog(tk.Toplevel):
    def __init__(self, master, *, risk_id: int, on_save) -> None:
        super().__init__(master)
        self.title(f"Review on risk #{risk_id}")
        self.geometry("620x520")
        self.transient(master.winfo_toplevel())
        self.after_idle(self.grab_set)
        self._risk_id = risk_id
        self._on_save = on_save
        self._build()

    def _build(self) -> None:
        wrap = ttk.Frame(self, padding=10)
        wrap.pack(fill="both", expand=True)
        wrap.columnconfigure(1, weight=1)
        self.date_e = ttk.Entry(wrap)
        self.reviewer_e = ttk.Entry(wrap)
        self.summary_t = tk.Text(wrap, height=3, width=40)
        self.like_cb = ttk.Combobox(
            wrap, values=("",) + tuple(
                f"{n} ({LIKELIHOOD_LABELS[n]})"
                for n in range(1, 6)),
            state="readonly")
        self.imp_cb = ttk.Combobox(
            wrap, values=("",) + tuple(
                f"{n} ({IMPACT_LABELS[n]})"
                for n in range(1, 6)),
            state="readonly")
        self.status_cb = ttk.Combobox(
            wrap, values=("",) + STATUSES, state="readonly")
        self.notes_t = tk.Text(wrap, height=3, width=40)

        self.date_e.insert(0, _date.today().isoformat())
        fields = [
            ("Review date:",     self.date_e),
            ("Reviewer:",        self.reviewer_e),
            ("Summary:",         self.summary_t),
            ("New likelihood:",  self.like_cb),
            ("New impact:",      self.imp_cb),
            ("New status:",      self.status_cb),
            ("Notes:",           self.notes_t),
        ]
        for i, (lbl, w) in enumerate(fields):
            ttk.Label(wrap, text=lbl).grid(row=i, column=0,
                                              sticky="ne",
                                              padx=6, pady=2)
            w.grid(row=i, column=1, sticky="ew",
                   padx=6, pady=2)
        btns = ttk.Frame(wrap)
        btns.grid(row=len(fields), column=0, columnspan=2,
                   sticky="e", pady=10)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="left", padx=4)

    @staticmethod
    def _parse_score(v: str) -> int | None:
        v = (v or "").strip()
        if not v:
            return None
        return int(v.split(" ", 1)[0])

    def _save(self) -> None:
        payload = {
            "review_date":    self.date_e.get().strip(),
            "reviewer":       self.reviewer_e.get().strip(),
            "summary":        self.summary_t.get(
                "1.0", "end").strip(),
            "new_likelihood": self._parse_score(self.like_cb.get()),
            "new_impact":     self._parse_score(self.imp_cb.get()),
            "new_status":     self.status_cb.get() or None,
            "notes":          self.notes_t.get(
                "1.0", "end").strip(),
        }
        self._on_save(payload)
        self.destroy()


# ══ Reviews tab ════════════════════════════════════════════════════

class ReviewsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Reviews")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="right")

        cols = ("review_id", "risk_id", "date", "reviewer",
                "new_l", "new_i", "new_status", "summary")
        widths = {"review_id": 60, "risk_id": 60, "date": 100,
                   "reviewer": 130, "new_l": 50, "new_i": 50,
                   "new_status": 110, "summary": 400}
        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(wrap, columns=cols,
                                    show="headings", height=22)
        for c, h in zip(cols, ("#", "Risk", "Date", "Reviewer",
                                  "L", "I", "Status", "Summary")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for r in data.list_reviews(limit=500):
            self.tree.insert("", "end", iid=str(r.review_id),
                              values=(r.review_id, r.risk_id,
                                       r.review_date,
                                       r.reviewer or "",
                                       r.new_likelihood or "",
                                       r.new_impact or "",
                                       r.new_status or "",
                                       (r.summary or "")[:80]))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _delete(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        if not messagebox.askyesno("Delete",
                                      f"Delete review #{rid}?"):
            return
        data.delete_review(rid)
        self.refresh()


# ══ Heatmap tab ════════════════════════════════════════════════════

class HeatmapTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Heatmap")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.grid_frame = ttk.Frame(self.frame, padding=10)
        self.grid_frame.pack(fill="both", expand=True)

    def refresh(self) -> None:
        for w in self.grid_frame.winfo_children():
            w.destroy()
        grid = data.heatmap()
        # Header row: impact
        ttk.Label(self.grid_frame, text="L \\ I",
                   font=("", 10, "bold")).grid(row=0, column=0,
                                                  padx=4, pady=4)
        for i in range(1, 6):
            ttk.Label(self.grid_frame,
                       text=f"{i}\n{IMPACT_LABELS[i]}",
                       font=("", 10, "bold")).grid(
                row=0, column=i, padx=4, pady=4)
        for l in range(5, 0, -1):
            ttk.Label(self.grid_frame,
                       text=f"{l} {LIKELIHOOD_LABELS[l]}",
                       font=("", 10, "bold")).grid(
                row=6 - l, column=0, padx=4, pady=4, sticky="e")
            for i in range(1, 6):
                n = grid.get((l, i), 0)
                band = score_band(l * i)
                cell = tk.Label(
                    self.grid_frame,
                    text=f"{n}\n({l*i})",
                    bg=BAND_COLOURS.get(band, "#f5f5f5"),
                    width=12, height=3,
                    relief="solid", borderwidth=1)
                cell.grid(row=6 - l, column=i,
                           padx=2, pady=2, sticky="nsew")
        for c in range(6):
            self.grid_frame.columnconfigure(c, weight=1)


# ══ Overview tab ═══════════════════════════════════════════════════

class OverviewTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Overview")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                             font=("TkFixedFont", 10),
                             state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=8)

    def refresh(self) -> None:
        try:
            o = data.overview()
        except Exception as e:
            _set_text(self.text, f"Error: {e}")
            return
        lines = [
            "═══ Risk Overview ═══",
            "",
            f"  Total risks         : {o.total}",
            f"  Open                : {o.open}",
            f"  Closed              : {o.closed}",
            f"  Reviews due (open)  : {o.reviews_due}",
            f"  High or Critical    : {o.high_or_critical}",
            "",
            f"  Actions             : {o.actions_total} "
            f"({o.actions_open} open, {o.actions_overdue} overdue)",
        ]
        if o.by_band:
            lines.append("\n  By inherent band:")
            for b in ("Low", "Medium", "High", "Critical"):
                n = o.by_band.get(b, 0)
                if n:
                    lines.append(f"    {b:<10} : {n}")
        if o.by_status:
            lines.append("\n  By status:")
            for s in STATUSES:
                n = o.by_status.get(s, 0)
                if n:
                    lines.append(f"    {s:<14} : {n}")
        if any(o.by_category.values()):
            lines.append("\n  By category:")
            for c in CATEGORIES:
                n = o.by_category.get(c, 0)
                if n:
                    lines.append(f"    {c:<20} : {n}")
        if o.top_risks:
            lines.append("\n  Top risks:")
            for rid, title, score, status in o.top_risks:
                lines.append(
                    f"    #{rid:<4}  {title[:34]:<34}  "
                    f"score {score:>3} "
                    f"({score_band(score):<8})  {status}")
        _set_text(self.text, "\n".join(lines))
