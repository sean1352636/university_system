"""Tkinter views for Sixth Form Data Export."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import datetime as _dt
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from education_system.shared import branding
from education_system.sixthform_system.modules.domain.reports.data_export import (
    data_export as data,
)
from education_system.sixthform_system.modules.domain.reports.data_export.data_export import (
    DEFAULT_FORMAT,
    FORMATS,
    Preset,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_data_export_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Data Export — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    RunTab(nb)
    PresetsTab(nb)
    JobsTab(nb)
    OverviewTab(nb)


def _set_text(text: tk.Text, body: str) -> None:
    text.configure(state="normal")
    text.delete("1.0", "end")
    text.insert("1.0", body)
    text.configure(state="disabled")


# ══ Run tab ════════════════════════════════════════════════════════

class RunTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Run Export")
        self._build()
        self.refresh_presets()

    def _build(self) -> None:
        top = ttk.Frame(self.frame)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Preset:").pack(side="left")
        self.preset_cb = ttk.Combobox(top, state="readonly", width=40)
        self.preset_cb.pack(side="left", padx=(2, 10))
        self.preset_cb.bind("<<ComboboxSelected>>",
                            lambda _e: self._on_preset_change())

        ttk.Label(top, text="Format:").pack(side="left")
        self.fmt_cb = ttk.Combobox(top, values=FORMATS,
                                    state="readonly", width=10)
        self.fmt_cb.set(DEFAULT_FORMAT)
        self.fmt_cb.pack(side="left", padx=(2, 10))

        self.zip_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Zip when done",
                         variable=self.zip_var).pack(side="left", padx=4)

        mid = ttk.Frame(self.frame)
        mid.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(mid, text="Output folder:").pack(side="left")
        self.dir_e = ttk.Entry(mid)
        self.dir_e.pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(mid, text="Browse…",
                    command=self._browse).pack(side="left")
        ttk.Button(mid, text="Run export",
                    command=self._run).pack(side="left", padx=8)

        info = ttk.LabelFrame(self.frame, text="Preset detail")
        info.pack(fill="x", padx=8, pady=6)
        self.info_var = tk.StringVar()
        ttk.Label(info, textvariable=self.info_var,
                   wraplength=1100, anchor="w",
                   justify="left").pack(fill="x", padx=8, pady=6)

        out = ttk.LabelFrame(self.frame, text="Output")
        out.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text = tk.Text(out, wrap="word",
                            font=("TkFixedFont", 10),
                            state="disabled")
        vs = ttk.Scrollbar(out, orient="vertical",
                            command=self.text.yview)
        self.text.configure(yscrollcommand=vs.set)
        self.text.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        self.status = tk.StringVar(value="Ready.")
        ttk.Label(self.frame, textvariable=self.status,
                   foreground="#444", anchor="w").pack(
            fill="x", padx=8)

    def _presets(self) -> list[Preset]:
        return data.list_presets()

    def refresh_presets(self) -> None:
        presets = self._presets()
        self._preset_list = presets
        self.preset_cb["values"] = [
            f"{p.name} ({p.key})"
            + (" — built-in" if p.is_builtin else "")
            for p in presets
        ]
        if presets:
            self.preset_cb.current(0)
            self._on_preset_change()

    def _selected(self) -> Preset | None:
        i = self.preset_cb.current()
        if i < 0 or i >= len(self._preset_list):
            return None
        return self._preset_list[i]

    def _on_preset_change(self) -> None:
        p = self._selected()
        if p is None:
            self.info_var.set("")
            return
        self.info_var.set(
            f"{p.name} ({p.key})  "
            f"[{'built-in' if p.is_builtin else 'user'}]\n"
            f"{p.description}\n\n"
            f"Datasets ({len(p.datasets)}): "
            + ", ".join(p.datasets))
        if not self.dir_e.get().strip():
            default = (Path.cwd() / "exports" /
                       f"{p.key}_"
                       f"{_dt.now().strftime('%Y%m%d_%H%M%S')}")
            self.dir_e.insert(0, str(default))

    def _browse(self) -> None:
        d = filedialog.askdirectory(
            title="Pick output folder",
            mustexist=False)
        if d:
            self.dir_e.delete(0, "end")
            self.dir_e.insert(0, d)

    def _run(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showerror("Run", "Pick a preset first.")
            return
        out_dir = self.dir_e.get().strip()
        if not out_dir:
            messagebox.showerror(
                "Run", "Pick an output folder.")
            return
        self.status.set("Running…")
        self.frame.update_idletasks()
        try:
            job = data.run_export(
                p.key, out_dir,
                fmt=self.fmt_cb.get(),
                zip_output=self.zip_var.get())
        except ValidationError as e:
            messagebox.showerror("Run", str(e))
            self.status.set("Ready.")
            return
        except Exception as e:
            logger.exception("run_export crashed")
            messagebox.showerror("Run", str(e))
            self.status.set("Ready.")
            return
        self.status.set(
            f"Job #{job.job_id}: {job.status}  "
            f"files={job.files_total} rows={job.rows_total}")
        _set_text(self.text, _render_job(job))


def _render_job(j: data.ExportJob) -> str:
    lines = [
        f"Job #{j.job_id}    status: {j.status}",
        f"Preset       : {j.preset_name} ({j.preset_key})",
        f"Output dir   : {j.output_dir}",
        f"Format       : {j.fmt}",
        f"Started      : {j.started_at}",
        f"Finished     : {j.finished_at or '—'}",
        f"Files written: {j.files_total}",
        f"Rows written : {j.rows_total}",
        f"Bytes written: {j.bytes_total}",
    ]
    if j.zipped:
        lines.append(f"Archive      : {j.archive_path or '(not produced)'}")
    if j.run_by:
        lines.append(f"Run by       : {j.run_by}")
    if j.notes:
        lines.append(f"Notes        : {j.notes}")
    if j.files:
        lines.append("")
        lines.append(f"  {'Dataset':<28}  {'Rows':>6}  {'Cols':>5}  "
                     f"{'Bytes':>10}  Path / Error")
        lines.append("  " + "-" * 100)
        for r in j.files:
            tail = r.file_path or (r.error or "")
            lines.append(
                f"  {r.dataset_key[:28]:<28}  {r.row_count:>6}  "
                f"{r.column_count:>5}  {r.bytes_written:>10}  "
                f"{tail[:60]}")
    return "\n".join(lines)


# ══ Presets tab ════════════════════════════════════════════════════

class PresetsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Presets")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="New…",
                    command=self._new).pack(side="left")
        ttk.Button(bar, text="Edit…",
                    command=self._edit).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left", padx=4)

        cols = ("preset_id", "key", "name", "kind", "datasets",
                 "description")
        widths = {"preset_id": 60, "key": 140, "name": 200,
                   "kind": 70, "datasets": 60, "description": 420}
        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(wrap, columns=cols,
                                    show="headings", height=20)
        for c, h in zip(cols, ("#", "Key", "Name", "Kind",
                                  "Sets", "Description")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._edit())

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for p in data.list_presets():
            iid = (f"u{p.preset_id}" if p.preset_id is not None
                   else f"b:{p.key}")
            self.tree.insert("", "end", iid=iid, values=(
                p.preset_id if p.preset_id is not None else "—",
                p.key, p.name,
                "built-in" if p.is_builtin else "user",
                len(p.datasets), p.description))

    def _selected(self) -> Preset | None:
        sel = self.tree.selection()
        if not sel:
            return None
        iid = sel[0]
        if iid.startswith("u"):
            try:
                return data.get_preset(int(iid[1:]))
            except ValueError:
                return None
        if iid.startswith("b:"):
            return data.get_preset(iid[2:])
        return None

    def _new(self) -> None:
        PresetDialog(self.frame, on_save=self._save_new)

    def _save_new(self, payload: dict[str, Any]) -> None:
        try:
            data.create_preset(payload)
        except ValidationError as e:
            messagebox.showerror("Save", str(e))
            return
        self.refresh()

    def _edit(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showinfo("Edit", "Pick a preset first.")
            return
        if p.is_builtin:
            messagebox.showinfo(
                "Edit", "Built-in presets can be viewed but not edited.")
            PresetDialog(self.frame, existing=p, read_only=True,
                         on_save=lambda _p: None)
            return
        PresetDialog(self.frame, existing=p,
                     on_save=lambda payload: self._save_edit(
                         p.preset_id, payload))

    def _save_edit(self, pid: int, payload: dict[str, Any]) -> None:
        try:
            data.update_preset(pid, payload)
        except ValidationError as e:
            messagebox.showerror("Edit", str(e))
            return
        self.refresh()

    def _delete(self) -> None:
        p = self._selected()
        if p is None or p.is_builtin or p.preset_id is None:
            messagebox.showinfo(
                "Delete",
                "Pick a user-defined preset to delete "
                "(built-ins can't be removed).")
            return
        if not messagebox.askyesno(
                "Delete", f"Delete preset #{p.preset_id} ({p.key})?"):
            return
        data.delete_preset(p.preset_id)
        self.refresh()


class PresetDialog(tk.Toplevel):
    def __init__(self, master, existing: Preset | None = None, *,
                 read_only: bool = False, on_save) -> None:
        super().__init__(master)
        self.title("Preset")
        self.geometry("700x600")
        self.transient(master.winfo_toplevel())
        self.after_idle(self.grab_set)
        self._existing = existing
        self._read_only = read_only
        self._on_save = on_save
        self._build()

    def _build(self) -> None:
        pad = {"padx": 8, "pady": 4}
        wrap = ttk.Frame(self, padding=10)
        wrap.pack(fill="both", expand=True)

        ttk.Label(wrap, text="Key:").grid(row=0, column=0,
                                              sticky="e", **pad)
        self.key_e = ttk.Entry(wrap, width=32)
        self.key_e.grid(row=0, column=1, sticky="ew", **pad)

        ttk.Label(wrap, text="Name:").grid(row=1, column=0,
                                              sticky="e", **pad)
        self.name_e = ttk.Entry(wrap, width=32)
        self.name_e.grid(row=1, column=1, sticky="ew", **pad)

        ttk.Label(wrap, text="Description:").grid(row=2, column=0,
                                                      sticky="e", **pad)
        self.desc_e = ttk.Entry(wrap, width=42)
        self.desc_e.grid(row=2, column=1, sticky="ew", **pad)

        ttk.Label(wrap, text="Datasets:").grid(row=3, column=0,
                                                   sticky="ne", **pad)
        list_wrap = ttk.Frame(wrap)
        list_wrap.grid(row=3, column=1, sticky="nsew", **pad)
        self.lb = tk.Listbox(list_wrap, selectmode="extended",
                              exportselection=False, height=18)
        self.lb.pack(side="left", fill="both", expand=True)
        vs = ttk.Scrollbar(list_wrap, orient="vertical",
                            command=self.lb.yview)
        self.lb.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self._all_keys: list[str] = []
        for k, label in data.available_datasets():
            self._all_keys.append(k)
            self.lb.insert("end", f"{label}  ({k})")

        wrap.rowconfigure(3, weight=1)
        wrap.columnconfigure(1, weight=1)

        btns = ttk.Frame(wrap)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=8)
        if not self._read_only:
            ttk.Button(btns, text="Save",
                        command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Close",
                    command=self.destroy).pack(side="left", padx=4)

        if self._existing is not None:
            e = self._existing
            self.key_e.insert(0, e.key)
            self.name_e.insert(0, e.name)
            self.desc_e.insert(0, e.description)
            chosen = set(e.datasets)
            for i, k in enumerate(self._all_keys):
                if k in chosen:
                    self.lb.select_set(i)
        if self._read_only:
            for w in (self.key_e, self.name_e, self.desc_e):
                w.configure(state="disabled")
            self.lb.configure(state="disabled")

    def _save(self) -> None:
        if self._read_only:
            return
        sel = [self._all_keys[i] for i in self.lb.curselection()]
        payload = {
            "key": self.key_e.get().strip(),
            "name": self.name_e.get().strip(),
            "description": self.desc_e.get().strip(),
            "datasets": sel,
        }
        if not payload["key"]:
            messagebox.showerror("Save", "Key is required.")
            return
        if not payload["name"]:
            messagebox.showerror("Save", "Name is required.")
            return
        if not payload["datasets"]:
            messagebox.showerror(
                "Save", "Pick at least one dataset.")
            return
        self._on_save(payload)
        self.destroy()


# ══ Jobs tab ═══════════════════════════════════════════════════════

class JobsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Past Jobs")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="View",
                    command=self._view).pack(side="left")
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left", padx=4)

        cols = ("job_id", "started", "preset", "status",
                "files", "rows", "bytes", "output")
        widths = {"job_id": 60, "started": 150, "preset": 180,
                   "status": 80, "files": 60, "rows": 80,
                   "bytes": 100, "output": 380}
        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(wrap, columns=cols,
                                    show="headings", height=20)
        for c, h in zip(cols, ("#", "Started", "Preset", "Status",
                                  "Files", "Rows", "Bytes", "Output")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._view())

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for j in data.list_jobs(limit=500):
            self.tree.insert("", "end", iid=str(j.job_id),
                              values=(j.job_id, j.started_at,
                                       j.preset_name, j.status,
                                       j.files_total, j.rows_total,
                                       j.bytes_total, j.output_dir))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _view(self) -> None:
        jid = self._selected_id()
        if jid is None:
            messagebox.showinfo("View", "Pick a job first.")
            return
        j = data.get_job(jid)
        if j is None:
            messagebox.showerror("View", f"No job #{jid}")
            return
        JobViewer(self.frame, j)

    def _delete(self) -> None:
        jid = self._selected_id()
        if jid is None:
            messagebox.showinfo("Delete", "Pick a job first.")
            return
        remove = messagebox.askyesno(
            "Delete files too?",
            "Also delete the on-disk output folder and archive?",
            default="no")
        if not messagebox.askyesno(
                "Delete", f"Delete job #{jid}?"):
            return
        data.delete_job(jid, remove_files=bool(remove))
        self.refresh()


class JobViewer(tk.Toplevel):
    def __init__(self, master, job: data.ExportJob) -> None:
        super().__init__(master)
        self.title(f"Job #{job.job_id} — {job.preset_name}")
        self.geometry("1100x680")
        self.transient(master.winfo_toplevel())
        text = tk.Text(self, wrap="word",
                        font=("TkFixedFont", 10))
        vs = ttk.Scrollbar(self, orient="vertical",
                            command=text.yview)
        text.configure(yscrollcommand=vs.set)
        text.pack(side="left", fill="both", expand=True,
                   padx=(10, 0), pady=10)
        vs.pack(side="right", fill="y", pady=10)
        text.insert("1.0", _render_job(job))
        text.configure(state="disabled")


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
            "═══ Data Export Overview ═══",
            "",
            f"  Total jobs           : {o.total_jobs}",
            f"  Succeeded            : {o.succeeded}",
            f"  Partial              : {o.partial}",
            f"  Failed               : {o.failed}",
            f"  Files written        : {o.total_files_written}",
            f"  Rows written         : {o.total_rows_written}",
            f"  Bytes written        : {o.total_bytes_written}",
            f"  Built-in presets     : {o.builtin_preset_count}",
            f"  User-defined presets : {o.user_preset_count}",
        ]
        if o.last_job:
            lines.append("")
            lines.append("  Last job:")
            lines.append("")
            lines.append(_render_job(o.last_job))
        _set_text(self.text, "\n".join(lines))
