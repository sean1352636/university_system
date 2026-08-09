"""Tkinter GUI for Curriculum Specification (programme specs, module
descriptors, learning outcomes, assessment strategy, change control)."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import logging
import tkinter as tk
from tkinter import ttk, messagebox

logger = logging.getLogger(__name__)


class CurriculumSpecificationGUI:
    def __init__(self, parent=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title(_t('gui.academics.curriculum_specification.curriculum_specification.windows.curriculum_specification_programme_specs_module_descriptors', default="Curriculum Specification — Programme Specs & Module Descriptors"))
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        try:
            from education_system.systems.university.domains.academics.domain.curriculum_specification.services.curriculum_specification_service import (
                CurriculumSpecificationService,
            )
            self.service = CurriculumSpecificationService()
        except Exception as e:
            logger.error(f"Service init error: {e}")
            self.service = None

        try:
            from education_system.systems.university.infrastructure.shared_context import get_auth
            self.auth = get_auth()
        except Exception:
            self.auth = None

        self._setup_ui()

    def _user(self):
        if self.auth and getattr(self.auth, "current_user", None):
            return self.auth.current_user.get("username", "system")
        return "system"

    def _setup_ui(self):
        try:
            from education_system.systems.university.domains.academics.interfaces.gui.research.external_quality_assurance.qa_widgets import EQAStatusStrip
            EQAStatusStrip(self.root).pack(fill=tk.X)
        except Exception:
            pass
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._build_programmes_tab(notebook)
        self._build_modules_tab(notebook)
        self._build_outcomes_tab(notebook)
        self._build_assessment_tab(notebook)
        self._build_changes_tab(notebook)
        self._build_handbook_tab(notebook)

    # ----------------------------------------------------------- Programmes
    def _build_programmes_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text=_t('gui.academics.curriculum_specification.curriculum_specification.tabs.programmes', default="Programmes"))

        cols = ("id", "code", "version", "title", "award", "level", "credits", "status")
        self.prog_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        widths = {"id": 50, "code": 90, "version": 60, "title": 320,
                  "award": 110, "level": 60, "credits": 70, "status": 100}
        for c in cols:
            self.prog_tree.heading(c, text=c.title())
            self.prog_tree.column(c, width=widths[c], anchor=tk.W)
        self.prog_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn = ttk.Frame(tab)
        btn.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.add', default="Add"), command=self._add_programme).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.edit_aims', default="Edit Aims"), command=self._edit_programme_aims).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.summary', default="Summary"), command=self._programme_summary).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.approve', default="Approve"), command=self._approve_programme).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.new_version', default="New Version"), command=self._new_programme_version).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.refresh', default="Refresh"), command=self._refresh_programmes).pack(side=tk.RIGHT, padx=2)
        self._refresh_programmes()

    def _refresh_programmes(self):
        for r in self.prog_tree.get_children():
            self.prog_tree.delete(r)
        if not self.service:
            return
        try:
            for p in self.service.list_programmes():
                self.prog_tree.insert("", tk.END, values=(
                    p["id"], p["code"], p["version"], p["title"],
                    p.get("award") or "", p.get("level") or "",
                    p.get("credits") or "", p["status"],
                ))
        except Exception as e:
            logger.error(f"Error loading programmes: {e}")

    def _selected_prog_id(self):
        sel = self.prog_tree.selection()
        if not sel:
            messagebox.showwarning(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.selection', default="Selection"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.select_a_programme_first', default="Select a programme first."), parent=self.root)
            return None
        return int(self.prog_tree.item(sel[0], "values")[0])

    def _add_programme(self):
        dlg = tk.Toplevel(self.root)
        dlg.title(_t('gui.academics.curriculum_specification.curriculum_specification.windows.add_programme', default="Add Programme"))
        dlg.geometry("520x520")
        dlg.transient(self.root)
        dlg.grab_set()

        fields = [
            ("Code:", "code"), ("Title:", "title"), ("Award:", "award"),
            ("Level:", "level"), ("Credits:", "credits"),
            ("Department:", "department"), ("QAA Benchmark:", "qaa_benchmark"),
        ]
        vars_ = {}
        for label, key in fields:
            ttk.Label(dlg, text=label).pack(padx=10, pady=(8, 0), anchor=tk.W)
            v = tk.StringVar()
            ttk.Entry(dlg, textvariable=v).pack(fill=tk.X, padx=10)
            vars_[key] = v

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.educational_aims', default="Educational Aims:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        aims_text = tk.Text(dlg, height=6)
        aims_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        def save():
            data = {k: v.get().strip() or None for k, v in vars_.items()}
            if not data["code"] or not data["title"]:
                messagebox.showwarning(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.validation', default="Validation"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.code_and_title_required', default="Code and title required."), parent=dlg)
                return
            try:
                if data.get("credits"):
                    data["credits"] = int(data["credits"])
                data["educational_aims"] = aims_text.get("1.0", tk.END).strip() or None
                data["created_by"] = self._user()
                self.service.create_programme(**data)
                dlg.destroy()
                self._refresh_programmes()
                messagebox.showinfo(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.success', default="Success"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.programme_created', default="Programme created."), parent=self.root)
            except Exception as e:
                messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=dlg)

        ttk.Button(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.save', default="Save"), command=save).pack(pady=10)

    def _edit_programme_aims(self):
        pid = self._selected_prog_id()
        if not pid:
            return
        prog = self.service.get_programme(pid)

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Edit Programme — {prog['code']} v{prog['version']}")
        dlg.geometry("600x520")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.educational_aims', default="Educational Aims:")).pack(padx=10, pady=(10, 0), anchor=tk.W)
        aims = tk.Text(dlg, height=6)
        aims.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        aims.insert("1.0", prog.get("educational_aims") or "")

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.pedagogic_approach', default="Pedagogic Approach:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        ped = tk.Text(dlg, height=4)
        ped.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        ped.insert("1.0", prog.get("pedagogic_approach") or "")

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.entry_requirements', default="Entry Requirements:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        ent = tk.Text(dlg, height=4)
        ent.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        ent.insert("1.0", prog.get("entry_requirements") or "")

        def save():
            try:
                self.service.update_programme(
                    pid,
                    educational_aims=aims.get("1.0", tk.END).strip() or None,
                    pedagogic_approach=ped.get("1.0", tk.END).strip() or None,
                    entry_requirements=ent.get("1.0", tk.END).strip() or None,
                )
                dlg.destroy()
                messagebox.showinfo(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.success', default="Success"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.programme_updated', default="Programme updated."), parent=self.root)
            except Exception as e:
                messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=dlg)

        ttk.Button(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.save', default="Save"), command=save).pack(pady=10)

    def _programme_summary(self):
        pid = self._selected_prog_id()
        if not pid:
            return
        try:
            s = self.service.programme_summary(pid)
        except Exception as e:
            messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=self.root)
            return
        if not s:
            messagebox.showinfo(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.programme_summary', default="Programme Summary"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.not_found', default="Not found."), parent=self.root)
            return
        p = s["programme"]
        msg = (f"{p['code']} v{p['version']} — {p['title']}\n"
               f"Status: {p['status']}    Department: {p.get('department') or 'n/a'}\n\n"
               f"Modules: {s['module_count']} "
               f"({s['core_modules']} core, {s['optional_modules']} optional)\n"
               f"Total credits: {s['total_credits']}\n"
               f"Programme LOs: {s['programme_los']}\n"
               f"Pending changes: {s['pending_changes']}")
        messagebox.showinfo(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.programme_summary', default="Programme Summary"), msg, parent=self.root)

    def _approve_programme(self):
        pid = self._selected_prog_id()
        if not pid:
            return
        try:
            self.service.approve_programme(pid, self._user())
            self._refresh_programmes()
            messagebox.showinfo(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.success', default="Success"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.programme_approved', default="Programme approved."), parent=self.root)
        except Exception as e:
            messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=self.root)

    def _new_programme_version(self):
        pid = self._selected_prog_id()
        if not pid:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title(_t('gui.academics.curriculum_specification.curriculum_specification.windows.new_programme_version', default="New Programme Version"))
        dlg.geometry("320x140")
        dlg.transient(self.root)
        dlg.grab_set()
        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.new_version_e_g_2_0', default="New version (e.g. 2.0):")).pack(padx=10, pady=10, anchor=tk.W)
        ver = tk.StringVar()
        ttk.Entry(dlg, textvariable=ver).pack(fill=tk.X, padx=10)

        def save():
            if not ver.get().strip():
                return
            try:
                self.service.new_programme_version(pid, ver.get().strip(), self._user())
                dlg.destroy()
                self._refresh_programmes()
            except Exception as e:
                messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=dlg)

        ttk.Button(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.create', default="Create"), command=save).pack(pady=10)

    # ------------------------------------------------------- Module Descriptors
    def _build_modules_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text=_t('gui.academics.curriculum_specification.curriculum_specification.tabs.module_descriptors', default="Module Descriptors"))

        filt = ttk.Frame(tab)
        filt.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(filt, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.programme_id', default="Programme ID:")).pack(side=tk.LEFT)
        self.mod_filter_pid = tk.StringVar()
        ttk.Entry(filt, textvariable=self.mod_filter_pid, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(filt, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.apply', default="Apply"), command=self._refresh_modules).pack(side=tk.LEFT)

        cols = ("id", "code", "version", "title", "credits", "level", "core", "leader")
        self.mod_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        widths = {"id": 50, "code": 90, "version": 60, "title": 300,
                  "credits": 70, "level": 60, "core": 60, "leader": 150}
        for c in cols:
            self.mod_tree.heading(c, text=c.title())
            self.mod_tree.column(c, width=widths[c], anchor=tk.W)
        self.mod_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn = ttk.Frame(tab)
        btn.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.add', default="Add"), command=self._add_module).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.edit', default="Edit"), command=self._edit_module).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.validate_assessment', default="Validate Assessment"), command=self._validate_module).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.examiner_findings', default="Examiner Findings"), command=self._show_examiner_findings).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.refresh', default="Refresh"), command=self._refresh_modules).pack(side=tk.RIGHT, padx=2)
        self._refresh_modules()

    def _refresh_modules(self):
        for r in self.mod_tree.get_children():
            self.mod_tree.delete(r)
        if not self.service:
            return
        pid = self.mod_filter_pid.get().strip()
        try:
            rows = self.service.list_module_descriptors(int(pid)) if pid else self.service.list_module_descriptors()
            for m in rows:
                self.mod_tree.insert("", tk.END, values=(
                    m["id"], m["module_code"], m["version"], m["title"],
                    m.get("credits") or "", m.get("level") or "",
                    "Y" if m.get("is_core") else "N", m.get("module_leader") or "",
                ))
        except Exception as e:
            logger.error(f"Error loading modules: {e}")

    def _add_module(self):
        dlg = tk.Toplevel(self.root)
        dlg.title(_t('gui.academics.curriculum_specification.curriculum_specification.windows.add_module_descriptor', default="Add Module Descriptor"))
        dlg.geometry("520x560")
        dlg.transient(self.root)
        dlg.grab_set()

        fields = [
            ("Programme ID:", "programme_id"),
            ("Module code:", "module_code"),
            ("Title:", "title"),
            ("Credits:", "credits"),
            ("Level:", "level"),
            ("Semester:", "semester"),
            ("Module leader:", "module_leader"),
        ]
        vars_ = {}
        for label, key in fields:
            ttk.Label(dlg, text=label).pack(padx=10, pady=(6, 0), anchor=tk.W)
            v = tk.StringVar()
            ttk.Entry(dlg, textvariable=v).pack(fill=tk.X, padx=10)
            vars_[key] = v

        is_core = tk.BooleanVar(value=True)
        ttk.Checkbutton(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.core_module', default="Core module"), variable=is_core).pack(padx=10, pady=4, anchor=tk.W)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.aims', default="Aims:")).pack(padx=10, pady=(6, 0), anchor=tk.W)
        aims_text = tk.Text(dlg, height=5)
        aims_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.indicative_content', default="Indicative content:")).pack(padx=10, pady=(6, 0), anchor=tk.W)
        content_text = tk.Text(dlg, height=4)
        content_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        def save():
            data = {k: v.get().strip() or None for k, v in vars_.items()}
            if not data["module_code"] or not data["title"]:
                messagebox.showwarning(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.validation', default="Validation"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.code_and_title_required', default="Code and title required."), parent=dlg)
                return
            try:
                if data.get("programme_id"):
                    data["programme_id"] = int(data["programme_id"])
                if data.get("credits"):
                    data["credits"] = int(data["credits"])
                data["is_core"] = 1 if is_core.get() else 0
                data["aims"] = aims_text.get("1.0", tk.END).strip() or None
                data["indicative_content"] = content_text.get("1.0", tk.END).strip() or None
                data["created_by"] = self._user()
                self.service.create_module_descriptor(**data)
                dlg.destroy()
                self._refresh_modules()
            except Exception as e:
                messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=dlg)

        ttk.Button(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.save', default="Save"), command=save).pack(pady=10)

    def _edit_module(self):
        mid = self._selected_module_id()
        if not mid:
            return
        md = self.service.get_module_descriptor(mid)
        if not md:
            messagebox.showinfo(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.edit', default="Edit"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.descriptor_not_found', default="Descriptor not found."), parent=self.root)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Edit Module Descriptor — {md['module_code']}")
        dlg.geometry("480x420")
        dlg.transient(self.root)
        dlg.grab_set()

        fields = [("Title:", "title"), ("Credits:", "credits"),
                  ("Level:", "level"), ("Module leader:", "module_leader")]
        vars_ = {}
        for label, key in fields:
            ttk.Label(dlg, text=label).pack(padx=10, pady=(8, 0), anchor=tk.W)
            v = tk.StringVar(value=str(md.get(key) or ""))
            ttk.Entry(dlg, textvariable=v).pack(fill=tk.X, padx=10)
            vars_[key] = v

        is_core = tk.BooleanVar(value=bool(md.get("is_core")))
        ttk.Checkbutton(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.core_module', default="Core module"), variable=is_core).pack(padx=10, pady=6, anchor=tk.W)

        def save():
            try:
                updates = {
                    "title": vars_["title"].get().strip() or None,
                    "level": vars_["level"].get().strip() or None,
                    "module_leader": vars_["module_leader"].get().strip() or None,
                    "is_core": 1 if is_core.get() else 0,
                }
                credits = vars_["credits"].get().strip()
                updates["credits"] = int(credits) if credits else None
                self.service.update_module_descriptor(mid, **updates)
                dlg.destroy()
                self._refresh_modules()
            except Exception as e:
                messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=dlg)

        ttk.Button(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.save', default="Save"), command=save).pack(pady=10)

    def _selected_module_id(self):
        sel = self.mod_tree.selection()
        if not sel:
            messagebox.showwarning(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.selection', default="Selection"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.select_a_module_descriptor_first', default="Select a module descriptor first."), parent=self.root)
            return None
        return int(self.mod_tree.item(sel[0], "values")[0])

    def _validate_module(self):
        mid = self._selected_module_id()
        if not mid:
            return
        v = self.service.validate_assessment_strategy(mid)
        msg = f"Total weighting: {v['total']:.2f}%\nValid: {v['valid']}\n\n"
        msg += "\n".join(f"• {i}" for i in v["issues"]) or "No issues found."
        messagebox.showinfo(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.assessment_strategy', default="Assessment Strategy"), msg, parent=self.root)

    def _show_examiner_findings(self):
        mid = self._selected_module_id()
        if not mid:
            return
        rows = self.service.examiner_findings_for_module(mid)
        dlg = tk.Toplevel(self.root)
        md = self.service.get_module_descriptor(mid)
        dlg.title(f"Examiner Findings — {md['module_code']}")
        dlg.geometry("900x500")
        dlg.transient(self.root)

        if not rows:
            ttk.Label(dlg, text=f"No external-examiner findings reference {md['module_code']}.",
                      padding=20).pack()
            return

        cols = ("date", "examiner", "department", "rating", "findings")
        tree = ttk.Treeview(dlg, columns=cols, show="headings", height=18)
        widths = {"date": 100, "examiner": 160, "department": 140, "rating": 110, "findings": 380}
        for c in cols:
            tree.heading(c, text=c.title())
            tree.column(c, width=widths[c], anchor=tk.W)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        for r in rows:
            tree.insert("", tk.END, values=(
                r.get("visit_date") or "", r.get("examiner") or "",
                r.get("department") or "", r.get("overall_rating") or "",
                (r.get("findings") or "")[:90],
            ))

    # ----------------------------------------------------- Learning Outcomes
    def _build_outcomes_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text=_t('gui.academics.curriculum_specification.curriculum_specification.tabs.learning_outcomes', default="Learning Outcomes"))

        top = ttk.Frame(tab)
        top.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.parent_type', default="Parent type:")).pack(side=tk.LEFT)
        self.lo_parent_type = tk.StringVar(value=_t('gui.academics.curriculum_specification.curriculum_specification.values.programme', default="programme"))
        ttk.Combobox(top, textvariable=self.lo_parent_type,
                     values=["programme", "module"], state="readonly",
                     width=12).pack(side=tk.LEFT, padx=5)
        ttk.Label(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.parent_id', default="Parent ID:")).pack(side=tk.LEFT)
        self.lo_parent_id = tk.StringVar()
        ttk.Entry(top, textvariable=self.lo_parent_id, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.load', default="Load"), command=self._refresh_outcomes).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.add', default="Add"), command=self._add_outcome).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.delete', default="Delete"), command=self._delete_outcome).pack(side=tk.LEFT, padx=5)

        cols = ("id", "code", "domain", "bloom", "description")
        self.lo_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        widths = {"id": 50, "code": 70, "domain": 130, "bloom": 110, "description": 700}
        for c in cols:
            self.lo_tree.heading(c, text=c.title())
            self.lo_tree.column(c, width=widths[c], anchor=tk.W)
        self.lo_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _refresh_outcomes(self):
        for r in self.lo_tree.get_children():
            self.lo_tree.delete(r)
        if not self.service or not self.lo_parent_id.get().strip():
            return
        try:
            pid = int(self.lo_parent_id.get().strip())
            for lo in self.service.list_learning_outcomes(self.lo_parent_type.get(), pid):
                self.lo_tree.insert("", tk.END, values=(
                    lo["id"], lo.get("code") or "", lo.get("domain") or "",
                    lo.get("bloom_level") or "", lo["description"],
                ))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=self.root)

    def _add_outcome(self):
        if not self.lo_parent_id.get().strip():
            messagebox.showwarning(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.validation', default="Validation"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.set_parent_id_first', default="Set parent ID first."), parent=self.root)
            return
        dlg = tk.Toplevel(self.root)
        dlg.title(_t('gui.academics.curriculum_specification.curriculum_specification.windows.add_learning_outcome', default="Add Learning Outcome"))
        dlg.geometry("480x400")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.code_e_g_lo1', default="Code (e.g. LO1):")).pack(padx=10, pady=(10, 0), anchor=tk.W)
        code = tk.StringVar()
        ttk.Entry(dlg, textvariable=code).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.domain', default="Domain:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        domain = tk.StringVar(value=_t('gui.academics.curriculum_specification.curriculum_specification.values.knowledge', default="knowledge"))
        ttk.Combobox(dlg, textvariable=domain,
                     values=["knowledge", "skills", "professional", "transferable"],
                     state="readonly").pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.bloom_level', default="Bloom level:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        bloom = tk.StringVar()
        ttk.Combobox(dlg, textvariable=bloom,
                     values=["remember", "understand", "apply", "analyze", "evaluate", "create"],
                     state="readonly").pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.description', default="Description:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        desc = tk.Text(dlg, height=8)
        desc.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        def save():
            d = desc.get("1.0", tk.END).strip()
            if not d:
                messagebox.showwarning(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.validation', default="Validation"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.description_required', default="Description required."), parent=dlg)
                return
            try:
                self.service.add_learning_outcome(
                    self.lo_parent_type.get(),
                    int(self.lo_parent_id.get().strip()),
                    d, code.get().strip() or None,
                    domain.get() or None, bloom.get() or None,
                )
                dlg.destroy()
                self._refresh_outcomes()
            except Exception as e:
                messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=dlg)

        ttk.Button(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.save', default="Save"), command=save).pack(pady=10)

    def _delete_outcome(self):
        sel = self.lo_tree.selection()
        if not sel:
            return
        lo_id = int(self.lo_tree.item(sel[0], "values")[0])
        if messagebox.askyesno(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.confirm', default="Confirm"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.delete_this_learning_outcome', default="Delete this learning outcome?"), parent=self.root):
            self.service.delete_learning_outcome(lo_id)
            self._refresh_outcomes()

    # --------------------------------------------------------- Assessment
    def _build_assessment_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text=_t('gui.academics.curriculum_specification.curriculum_specification.tabs.assessment_strategy', default="Assessment Strategy"))

        top = ttk.Frame(tab)
        top.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.module_descriptor_id', default="Module Descriptor ID:")).pack(side=tk.LEFT)
        self.asm_module_id = tk.StringVar()
        ttk.Entry(top, textvariable=self.asm_module_id, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.load', default="Load"), command=self._refresh_assessment).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.add_component', default="Add Component"), command=self._add_assessment).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.delete', default="Delete"), command=self._delete_assessment).pack(side=tk.LEFT, padx=5)

        cols = ("id", "name", "type", "weighting", "los", "feedback")
        self.asm_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        widths = {"id": 50, "name": 220, "type": 130, "weighting": 100,
                  "los": 200, "feedback": 250}
        for c in cols:
            self.asm_tree.heading(c, text=c.title())
            self.asm_tree.column(c, width=widths[c], anchor=tk.W)
        self.asm_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.asm_status = ttk.Label(tab, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.total_weighting_0', default="Total weighting: 0%"))
        self.asm_status.pack(padx=5, pady=5, anchor=tk.W)

    def _refresh_assessment(self):
        for r in self.asm_tree.get_children():
            self.asm_tree.delete(r)
        if not self.service or not self.asm_module_id.get().strip():
            return
        try:
            mid = int(self.asm_module_id.get().strip())
            for c in self.service.list_assessment_components(mid):
                self.asm_tree.insert("", tk.END, values=(
                    c["id"], c.get("name") or "", c.get("assessment_type") or "",
                    f"{c.get('weighting_pct') or 0:.1f}%",
                    c.get("learning_outcomes_assessed") or "",
                    c.get("feedback_method") or "",
                ))
            v = self.service.validate_assessment_strategy(mid)
            colour = "green" if v["valid"] else "red"
            self.asm_status.configure(
                text=f"Total weighting: {v['total']:.2f}%   Valid: {v['valid']}",
                foreground=colour,
            )
        except Exception as e:
            messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=self.root)

    def _add_assessment(self):
        if not self.asm_module_id.get().strip():
            messagebox.showwarning(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.validation', default="Validation"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.set_module_id_first', default="Set module ID first."), parent=self.root)
            return
        dlg = tk.Toplevel(self.root)
        dlg.title(_t('gui.academics.curriculum_specification.curriculum_specification.windows.add_assessment_component', default="Add Assessment Component"))
        dlg.geometry("460x440")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.name', default="Name:")).pack(padx=10, pady=(10, 0), anchor=tk.W)
        name = tk.StringVar()
        ttk.Entry(dlg, textvariable=name).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.type', default="Type:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        a_type = tk.StringVar(value=_t('gui.academics.curriculum_specification.curriculum_specification.values.coursework', default="coursework"))
        ttk.Combobox(dlg, textvariable=a_type,
                     values=["exam", "coursework", "presentation", "practical",
                             "dissertation", "portfolio", "lab_report", "other"],
                     state="readonly").pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.weighting', default="Weighting (%):")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        weight = tk.StringVar()
        ttk.Entry(dlg, textvariable=weight).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.los_assessed_e_g_lo1_lo2', default="LOs assessed (e.g. LO1,LO2):")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        los = tk.StringVar()
        ttk.Entry(dlg, textvariable=los).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.feedback_method', default="Feedback method:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        fb = tk.StringVar()
        ttk.Entry(dlg, textvariable=fb).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.notes', default="Notes:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        notes = tk.Text(dlg, height=4)
        notes.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        def save():
            if not name.get().strip():
                messagebox.showwarning(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.validation', default="Validation"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.name_required', default="Name required."), parent=dlg)
                return
            try:
                mid = int(self.asm_module_id.get().strip())
                self.service.add_assessment_component(
                    mid, name.get().strip(),
                    assessment_type=a_type.get() or None,
                    weighting_pct=float(weight.get()) if weight.get().strip() else None,
                    learning_outcomes_assessed=los.get().strip() or None,
                    feedback_method=fb.get().strip() or None,
                    notes=notes.get("1.0", tk.END).strip() or None,
                )
                dlg.destroy()
                self._refresh_assessment()
            except Exception as e:
                messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=dlg)

        ttk.Button(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.save', default="Save"), command=save).pack(pady=10)

    def _delete_assessment(self):
        sel = self.asm_tree.selection()
        if not sel:
            return
        cid = int(self.asm_tree.item(sel[0], "values")[0])
        if messagebox.askyesno(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.confirm', default="Confirm"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.delete_this_component', default="Delete this component?"), parent=self.root):
            self.service.delete_assessment_component(cid)
            self._refresh_assessment()

    # ------------------------------------------------------ Change Control
    def _build_changes_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text=_t('gui.academics.curriculum_specification.curriculum_specification.tabs.change_control', default="Change Control"))

        top = ttk.Frame(tab)
        top.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.status_filter', default="Status filter:")).pack(side=tk.LEFT)
        self.chg_status = tk.StringVar(value="")
        ttk.Combobox(top, textvariable=self.chg_status,
                     values=["", "proposed", "approved", "rejected"],
                     state="readonly", width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.refresh', default="Refresh"), command=self._refresh_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.propose_change', default="Propose Change"), command=self._propose_change).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.approve', default="Approve"), command=self._approve_change).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.reject', default="Reject"), command=self._reject_change).pack(side=tk.LEFT, padx=5)

        cols = ("id", "parent", "type", "from_v", "to_v", "status", "summary", "proposed_at")
        self.chg_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        widths = {"id": 50, "parent": 120, "type": 90, "from_v": 70, "to_v": 70,
                  "status": 90, "summary": 350, "proposed_at": 150}
        for c in cols:
            self.chg_tree.heading(c, text=c.replace("_", " ").title())
            self.chg_tree.column(c, width=widths[c], anchor=tk.W)
        self.chg_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self._refresh_changes()

    def _refresh_changes(self):
        for r in self.chg_tree.get_children():
            self.chg_tree.delete(r)
        if not self.service:
            return
        try:
            status = self.chg_status.get().strip() or None
            for c in self.service.list_changes(status=status):
                self.chg_tree.insert("", tk.END, values=(
                    c["id"], f"{c['parent_type']}#{c['parent_id']}",
                    c.get("change_type") or "", c.get("from_version") or "",
                    c.get("to_version") or "", c["status"],
                    (c["summary"] or "")[:80], c.get("proposed_at") or "",
                ))
        except Exception as e:
            logger.error(f"Error loading changes: {e}")

    def _propose_change(self):
        dlg = tk.Toplevel(self.root)
        dlg.title(_t('gui.academics.curriculum_specification.curriculum_specification.windows.propose_change', default="Propose Change"))
        dlg.geometry("520x580")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.parent_type', default="Parent type:")).pack(padx=10, pady=(10, 0), anchor=tk.W)
        ptype = tk.StringVar(value=_t('gui.academics.curriculum_specification.curriculum_specification.values.programme', default="programme"))
        ttk.Combobox(dlg, textvariable=ptype, values=["programme", "module"],
                     state="readonly").pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.parent_id', default="Parent ID:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        pid = tk.StringVar()
        ttk.Entry(dlg, textvariable=pid).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.change_type', default="Change type:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        ctype = tk.StringVar(value=_t('gui.academics.curriculum_specification.curriculum_specification.values.minor', default="minor"))
        ttk.Combobox(dlg, textvariable=ctype, values=["minor", "major", "cosmetic"],
                     state="readonly").pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.from_version', default="From version:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        from_v = tk.StringVar()
        ttk.Entry(dlg, textvariable=from_v).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.to_version', default="To version:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        to_v = tk.StringVar()
        ttk.Entry(dlg, textvariable=to_v).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.summary', default="Summary:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        summary = tk.StringVar()
        ttk.Entry(dlg, textvariable=summary).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.rationale', default="Rationale:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        rationale = tk.Text(dlg, height=4)
        rationale.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.impact', default="Impact:")).pack(padx=10, pady=(8, 0), anchor=tk.W)
        impact = tk.Text(dlg, height=4)
        impact.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        def save():
            if not pid.get().strip() or not summary.get().strip():
                messagebox.showwarning(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.validation', default="Validation"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.parent_id_and_summary_required', default="Parent ID and summary required."), parent=dlg)
                return
            try:
                self.service.propose_change(
                    ptype.get(), int(pid.get().strip()), summary.get().strip(),
                    from_version=from_v.get().strip() or None,
                    to_version=to_v.get().strip() or None,
                    change_type=ctype.get() or None,
                    rationale=rationale.get("1.0", tk.END).strip() or None,
                    impact=impact.get("1.0", tk.END).strip() or None,
                    proposed_by=self._user(),
                )
                dlg.destroy()
                self._refresh_changes()
            except Exception as e:
                messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=dlg)

        ttk.Button(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.submit', default="Submit"), command=save).pack(pady=10)

    def _selected_change_id(self):
        sel = self.chg_tree.selection()
        if not sel:
            messagebox.showwarning(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.selection', default="Selection"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.select_a_change_first', default="Select a change first."), parent=self.root)
            return None
        return int(self.chg_tree.item(sel[0], "values")[0])

    def _approve_change(self):
        cid = self._selected_change_id()
        if not cid:
            return
        try:
            self.service.approve_change(cid, self._user())
            self._refresh_changes()
        except Exception as e:
            messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=self.root)

    def _reject_change(self):
        cid = self._selected_change_id()
        if not cid:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title(_t('gui.academics.curriculum_specification.curriculum_specification.windows.reject_change', default="Reject Change"))
        dlg.geometry("400x180")
        dlg.transient(self.root)
        dlg.grab_set()
        ttk.Label(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.reason', default="Reason:")).pack(padx=10, pady=(10, 0), anchor=tk.W)
        reason = tk.StringVar()
        ttk.Entry(dlg, textvariable=reason).pack(fill=tk.X, padx=10)

        def save():
            try:
                self.service.reject_change(cid, self._user(), reason.get().strip() or None)
                dlg.destroy()
                self._refresh_changes()
            except Exception as e:
                messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=dlg)

        ttk.Button(dlg, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.reject', default="Reject"), command=save).pack(pady=10)

    # -------------------------------------------------------- Handbook
    def _build_handbook_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text=_t('gui.academics.curriculum_specification.curriculum_specification.tabs.course_handbook', default="Course Handbook"))

        top = ttk.Frame(tab)
        top.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.labels.programme_id', default="Programme ID:")).pack(side=tk.LEFT)
        self.hb_pid = tk.StringVar()
        ttk.Entry(top, textvariable=self.hb_pid, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.generate', default="Generate"), command=self._generate_handbook).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.curriculum_specification.curriculum_specification.buttons.export_to_file', default="Export to file…"), command=self._export_handbook).pack(side=tk.LEFT, padx=5)

        self.hb_text = tk.Text(tab, wrap=tk.WORD)
        self.hb_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _generate_handbook(self):
        if not self.hb_pid.get().strip():
            return
        try:
            text = self.service.generate_handbook(int(self.hb_pid.get().strip()))
            self.hb_text.delete("1.0", tk.END)
            self.hb_text.insert("1.0", text)
        except Exception as e:
            messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=self.root)

    def _export_handbook(self):
        from tkinter import filedialog
        text = self.hb_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.empty', default="Empty"), _t('gui.academics.curriculum_specification.curriculum_specification.dialogs.generate_a_handbook_first', default="Generate a handbook first."), parent=self.root)
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("Markdown", "*.md")],
            parent=self.root,
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            messagebox.showinfo(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.success', default="Success"), f"Handbook saved to {path}", parent=self.root)
        except Exception as e:
            messagebox.showerror(_t('gui.academics.curriculum_specification.curriculum_specification.dialogs.error', default="Error"), str(e), parent=self.root)


def main():
    app = CurriculumSpecificationGUI()
    app.root.mainloop()


if __name__ == "__main__":
    main()
