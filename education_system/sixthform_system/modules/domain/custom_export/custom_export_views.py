"""Tkinter views for Sixth Form Custom Export."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable
from education_system.sixthform_system.modules.domain.custom_export import custom_export as data
from education_system.sixthform_system.modules.domain.custom_export.custom_export import (
    DEFAULT_FORMAT,
    DatasetSpec,
    FORMATS,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_custom_export_window(parent=None) -> None:
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title("Custom Export — Sixth Form System")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    ExportBuilder(win)


class ExportBuilder:
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self._datasets = data.list_datasets()
        self._current_spec: DatasetSpec | None = (
            self._datasets[0] if self._datasets else None)
        self._build()
        if self._current_spec:
            self._load_dataset(self._current_spec.key)

    def _build(self) -> None:
        paned = ttk.Panedwindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        # ── Left pane: dataset list ──
        left = ttk.LabelFrame(paned, text="Datasets")
        cols = ("key", "label")
        widths = {"key": 130, "label": 200}
        self.ds_tree = ttk.Treeview(left, columns=cols,
                                       show="headings", height=20)
        self.ds_tree.heading("key", text="Key")
        self.ds_tree.heading("label", text="Label")
        self.ds_tree.column("key", width=widths["key"], anchor="w")
        self.ds_tree.column("label", width=widths["label"], anchor="w")
        vs = ttk.Scrollbar(left, orient="vertical",
                            command=self.ds_tree.yview)
        self.ds_tree.configure(yscrollcommand=vs.set)
        self.ds_tree.pack(side="left", fill="both", expand=True,
                              padx=6, pady=6)
        vs.pack(side="right", fill="y")
        for d in self._datasets:
            self.ds_tree.insert("", "end", iid=d.key,
                                    values=(d.key, d.label))
        if self._datasets:
            self.ds_tree.selection_set(self._datasets[0].key)
        self.ds_tree.bind("<<TreeviewSelect>>",
                              lambda _e: self._on_ds_selected())
        paned.add(left, weight=1)

        # ── Right pane: builder ──
        right = ttk.Frame(paned)
        paned.add(right, weight=3)

        # Header
        self.head_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.head_var,
                   font=("", 12, "bold"),
                   anchor="w").pack(fill="x", padx=4, pady=(0, 2))
        self.desc_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.desc_var,
                   foreground="#444", anchor="w",
                   wraplength=900).pack(fill="x", padx=4)

        # Two side-by-side panes: columns + filters
        sel = ttk.Frame(right)
        sel.pack(fill="x", padx=4, pady=8)

        cols_frame = ttk.LabelFrame(sel, text="Columns")
        cols_frame.pack(side="left", fill="both", expand=True,
                            padx=(0, 4))
        self.cols_list = tk.Listbox(cols_frame,
                                         selectmode="extended",
                                         exportselection=False,
                                         height=10)
        self.cols_list.pack(side="left", fill="both", expand=True,
                                 padx=6, pady=6)
        cvs = ttk.Scrollbar(cols_frame, orient="vertical",
                              command=self.cols_list.yview)
        self.cols_list.configure(yscrollcommand=cvs.set)
        cvs.pack(side="right", fill="y")
        col_bar = ttk.Frame(cols_frame)
        col_bar.pack(side="bottom", fill="x", padx=6, pady=(0, 6))
        ttk.Button(col_bar, text="Select all",
                    command=self._select_all_cols).pack(side="left")
        ttk.Button(col_bar, text="Clear",
                    command=self._clear_cols).pack(side="left", padx=4)

        filt_frame = ttk.LabelFrame(sel, text="Filters")
        filt_frame.pack(side="left", fill="both", expand=True,
                            padx=(4, 0))
        self.filt_holder = ttk.Frame(filt_frame)
        self.filt_holder.pack(fill="both", expand=True,
                                 padx=6, pady=6)
        self._filter_entries: dict[str, tk.Variable] = {}

        # Format / limit / output
        opts = ttk.Frame(right)
        opts.pack(fill="x", padx=4, pady=4)
        ttk.Label(opts, text="Format:").pack(side="left")
        self.fmt_cb = ttk.Combobox(opts, values=FORMATS,
                                       state="readonly", width=12)
        self.fmt_cb.set(DEFAULT_FORMAT)
        self.fmt_cb.pack(side="left", padx=(2, 10))
        ttk.Label(opts, text="Row limit (blank=all):").pack(side="left")
        self.limit_e = ttk.Entry(opts, width=8)
        self.limit_e.pack(side="left", padx=(2, 10))
        ttk.Label(opts, text="Output file:").pack(side="left")
        self.path_e = ttk.Entry(opts, width=40)
        self.path_e.pack(side="left", padx=(2, 4))
        ttk.Button(opts, text="Browse…",
                    command=self._browse).pack(side="left")

        # Actions
        actions = ttk.Frame(right)
        actions.pack(fill="x", padx=4, pady=4)
        ttk.Button(actions, text="Preview",
                    command=self._preview).pack(side="left")
        ttk.Button(actions, text="Render to console pane",
                    command=self._render).pack(side="left", padx=4)
        ttk.Button(actions, text="Export to file",
                    command=self._export).pack(side="left", padx=4)

        # Preview pane
        preview_frame = ttk.LabelFrame(right, text="Preview / output")
        preview_frame.pack(fill="both", expand=True, padx=4, pady=4)
        self.preview = tk.Text(preview_frame, wrap="none",
                                  font=("TkFixedFont", 10),
                                  state="disabled")
        pvs = ttk.Scrollbar(preview_frame, orient="vertical",
                              command=self.preview.yview)
        phs = ttk.Scrollbar(preview_frame, orient="horizontal",
                              command=self.preview.xview)
        self.preview.configure(yscrollcommand=pvs.set,
                                  xscrollcommand=phs.set)
        self.preview.grid(row=0, column=0, sticky="nsew")
        pvs.grid(row=0, column=1, sticky="ns")
        phs.grid(row=1, column=0, sticky="ew")
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.status_var,
                   anchor="w",
                   foreground="#444").pack(fill="x", padx=4,
                                              pady=(2, 0))

    def _on_ds_selected(self) -> None:
        sel = self.ds_tree.selection()
        if not sel:
            return
        self._load_dataset(sel[0])

    def _load_dataset(self, key: str) -> None:
        try:
            spec = data.get_dataset(key)
        except ValidationError as e:
            messagebox.showerror("Dataset", str(e))
            return
        self._current_spec = spec
        self.head_var.set(f"{spec.label}  ({spec.key})")
        self.desc_var.set(spec.description)
        # Columns
        self.cols_list.delete(0, "end")
        for k, h in spec.columns:
            self.cols_list.insert("end", f"{h}  ({k})")
        # Select all by default
        self.cols_list.select_set(0, "end")
        # Filters
        for w in self.filt_holder.winfo_children():
            w.destroy()
        self._filter_entries = {}
        if not spec.filter_keys:
            ttk.Label(self.filt_holder,
                       text="(this dataset takes no filters)",
                       foreground="#888").pack(anchor="w")
        else:
            for i, k in enumerate(spec.filter_keys):
                row = ttk.Frame(self.filt_holder)
                row.pack(fill="x", pady=2)
                ttk.Label(row, text=f"{k}:", width=18,
                            anchor="e").pack(side="left")
                v = tk.StringVar()
                ttk.Entry(row, textvariable=v,
                            width=28).pack(side="left", padx=4,
                                              fill="x", expand=True)
                self._filter_entries[k] = v
                ttk.Label(row,
                            text="(blank = no filter; "
                                 "use true/false for booleans)",
                            foreground="#888",
                            font=("", 8)).pack(side="left", padx=4)
        # Default output filename.
        self.path_e.delete(0, "end")
        ext = (self.fmt_cb.get() if self.fmt_cb.get() != "markdown"
               else "md")
        self.path_e.insert(0, f"{spec.key}.{ext}")

    def _selected_columns(self) -> list[str] | None:
        if not self._current_spec:
            return None
        idx = self.cols_list.curselection()
        if not idx:
            return []
        spec = self._current_spec
        return [spec.columns[i][0] for i in idx]

    def _select_all_cols(self) -> None:
        self.cols_list.select_set(0, "end")

    def _clear_cols(self) -> None:
        self.cols_list.select_clear(0, "end")

    def _collect_filters(self) -> dict:
        out: dict = {}
        for k, var in self._filter_entries.items():
            v = var.get().strip()
            if not v:
                continue
            if v.lower() in ("true", "yes"):
                out[k] = True
            elif v.lower() in ("false", "no"):
                out[k] = False
            else:
                out[k] = v
        return out

    def _resolve_limit(self) -> int | None:
        s = self.limit_e.get().strip()
        if not s:
            return None
        try:
            return int(s)
        except ValueError:
            raise ValidationError("Row limit must be a number")

    def _browse(self) -> None:
        cur = self.path_e.get().strip()
        path = filedialog.asksaveasfilename(
            initialfile=cur,
            defaultextension="." + (self.fmt_cb.get() or "csv"),
            filetypes=[
                ("CSV", "*.csv"),
                ("TSV", "*.tsv"),
                ("JSON", "*.json"),
                ("JSONL", "*.jsonl"),
                ("Markdown", "*.md"),
                ("All files", "*.*"),
            ])
        if path:
            self.path_e.delete(0, "end")
            self.path_e.insert(0, path)

    def _set_preview(self, text: str) -> None:
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _preview(self) -> None:
        if not self._current_spec:
            return
        cols = self._selected_columns()
        if cols == []:
            messagebox.showerror(
                "Preview", "Select at least one column.")
            return
        try:
            limit = self._resolve_limit() or 20
            headers, rows = data.preview(
                self._current_spec, columns=cols,
                filters=self._collect_filters(),
                limit=limit)
        except ValidationError as e:
            messagebox.showerror("Preview", str(e))
            return
        except Exception as e:
            logger.exception("preview crashed")
            messagebox.showerror("Preview", str(e))
            return
        widths = [
            max([len(h)] + [len(r[i]) for r in rows])
            for i, h in enumerate(headers)
        ]
        widths = [min(w, 32) for w in widths] or [4]
        lines = [
            "  ".join(h.ljust(widths[i])
                       for i, h in enumerate(headers)),
            "  ".join("-" * w for w in widths),
        ]
        for r in rows:
            lines.append("  ".join(
                (c or "")[:widths[i]].ljust(widths[i])
                for i, c in enumerate(r)))
        body = "\n".join(lines) + f"\n\n[{len(rows)} row(s) preview]"
        self._set_preview(body)
        self.status_var.set(f"Preview: {len(rows)} row(s).")

    def _render(self) -> None:
        if not self._current_spec:
            return
        cols = self._selected_columns()
        if cols == []:
            messagebox.showerror(
                "Render", "Select at least one column.")
            return
        try:
            limit = self._resolve_limit()
            body = data.render(
                self._current_spec,
                fmt=self.fmt_cb.get(),
                columns=cols,
                filters=self._collect_filters(),
                limit=limit)
        except ValidationError as e:
            messagebox.showerror("Render", str(e))
            return
        except Exception as e:
            logger.exception("render crashed")
            messagebox.showerror("Render", str(e))
            return
        self._set_preview(body)
        self.status_var.set(
            f"Rendered {self.fmt_cb.get()} "
            f"({len(body)} char(s)).")

    def _export(self) -> None:
        if not self._current_spec:
            return
        path = self.path_e.get().strip()
        if not path:
            messagebox.showerror(
                "Export", "Pick an output file path.")
            return
        cols = self._selected_columns()
        if cols == []:
            messagebox.showerror(
                "Export", "Select at least one column.")
            return
        try:
            limit = self._resolve_limit()
            res = data.export(
                self._current_spec, path,
                fmt=self.fmt_cb.get(),
                columns=cols,
                filters=self._collect_filters(),
                limit=limit)
        except ValidationError as e:
            messagebox.showerror("Export", str(e))
            return
        except Exception as e:
            logger.exception("export crashed")
            messagebox.showerror("Export", str(e))
            return
        self.status_var.set(
            f"Wrote {res.row_count} row(s), "
            f"{res.column_count} col(s) "
            f"({res.bytes_written} bytes) → {res.path}")
        messagebox.showinfo(
            "Export complete",
            f"{res.row_count} row(s) written\n{res.path}")
