"""Bulk & onboarding tab (import / export / onboard panes) of Sixth Form User Management.

Split out of ``user_management_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.platform.identity.auth.role_manager import ROLE_HIERARCHY
from education_system.systems.sixth_form.domain.governance.user_management import bulk_io
from education_system.systems.sixth_form.domain.governance.user_management import onboarding
from education_system.systems.sixth_form.domain.governance.user_management.user_accounts import (
    UserAccountError,
)
from ._common import logger


# ── Bulk & onboarding tab ──────────────────────────────────────────

def _build_bulk_tab(gui, parent: ttk.Frame, refresh_all) -> None:
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)

    imp = ttk.Frame(nb, padding=8)
    exp = ttk.Frame(nb, padding=8)
    onb = ttk.Frame(nb, padding=8)
    nb.add(imp, text="Import")
    nb.add(exp, text="Export")
    nb.add(onb, text="Onboard")

    _build_import_pane(gui, imp, refresh_all)
    _build_export_pane(gui, exp)
    _build_onboard_pane(gui, onb, refresh_all)


def _build_import_pane(gui, parent: ttk.Frame, refresh_all) -> None:
    ttk.Label(parent,
              text=("Bulk-create users from a CSV/XLSX file. Required "
                    "columns: username, password. Optional: "
                    "display_name, email, role, phone, department, "
                    "job_title, line_manager_id, notes. The wizard "
                    "validates every row, lets you preview the result, "
                    "and only commits when you say so."),
              wraplength=820, foreground="#555", justify="left").pack(
        anchor="w", pady=(0, 8))

    path_var = tk.StringVar()
    pick = ttk.Frame(parent)
    pick.pack(fill="x")
    ttk.Label(pick, text="File:").pack(side="left", padx=(0, 4))
    ttk.Entry(pick, textvariable=path_var, width=60).pack(side="left",
                                                            padx=(0, 4))

    def _browse():
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
        p = filedialog.askopenfilename(
            parent=gui.root,
            title="Pick CSV / XLSX",
            filetypes=[("CSV", "*.csv"), ("Excel", "*.xlsx *.xlsm"),
                       ("All", "*.*")])
        if p:
            path_var.set(p)

    ttk.Button(pick, text="Browse…", command=_browse).pack(side="left")

    def _template():
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
        p = filedialog.asksaveasfilename(
            parent=gui.root, defaultextension=".csv",
            initialfile="users_template.csv",
            filetypes=[("CSV", "*.csv")])
        if not p:
            return
        try:
            bulk_io.write_template_csv(p)
        except Exception as e:
            logger.exception("Template write failed")
            messagebox.showerror("Template", str(e), parent=gui.root)
            return
        messagebox.showinfo("Template",
                             f"Template written to:\n{p}",
                             parent=gui.root)

    ttk.Button(pick, text="Download template…",
               command=_template).pack(side="left", padx=(8, 0))

    report = tk.Text(parent, height=22, wrap="none")
    yscroll = ttk.Scrollbar(parent, orient="vertical",
                              command=report.yview)
    report.configure(yscrollcommand=yscroll.set)
    yscroll.pack(side="right", fill="y")
    report.pack(fill="both", expand=True, pady=(6, 6))
    report.insert("1.0", "Pick a file then click 'Validate / Preview'.")
    report.configure(state="disabled")

    preview_holder = {"preview": None}

    def _set_report(text: str) -> None:
        report.configure(state="normal")
        report.delete("1.0", "end")
        report.insert("1.0", text)
        report.configure(state="disabled")

    def _validate():
        path = path_var.get().strip()
        if not path:
            messagebox.showinfo("Import", "Pick a file first.",
                                 parent=gui.root)
            return
        try:
            records = bulk_io.parse_file(path)
            preview = bulk_io.dry_run(gui.auth, records)
        except UserAccountError as e:
            messagebox.showerror("Import", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("Import preview crashed")
            messagebox.showerror("Import", f"Unexpected: {e}",
                                  parent=gui.root)
            return
        preview_holder["preview"] = preview
        lines = [f"Parsed {len(preview.rows)} row(s).",
                  f"  valid:   {len(preview.valid)}",
                  f"  invalid: {len(preview.invalid)}",
                  ""]
        for r in preview.invalid:
            lines.append(f"  line {r.line_no}: "
                          f"{', '.join(r.errors)}")
        _set_report("\n".join(lines))

    def _commit():
        preview = preview_holder.get("preview")
        if preview is None:
            messagebox.showinfo("Import",
                                 "Validate first to preview the rows.",
                                 parent=gui.root)
            return
        valid = preview.valid
        if not valid:
            messagebox.showwarning("Import",
                                    "No valid rows to import.",
                                    parent=gui.root)
            return
        if not messagebox.askyesno(
                "Import",
                f"Create {len(valid)} user(s)? Invalid rows will "
                f"be skipped ({len(preview.invalid)}).",
                parent=gui.root):
            return
        try:
            result = bulk_io.commit_import(gui.auth, preview)
        except Exception as e:
            logger.exception("Import commit crashed")
            messagebox.showerror("Import", f"Unexpected: {e}",
                                  parent=gui.root)
            return
        lines = ["Imported.",
                  f"  created: {len(result.created_user_ids)}",
                  f"  failed:  {len(result.failed)}",
                  ""]
        for ln, err in result.failed[:50]:
            lines.append(f"  line {ln}: {err}")
        _set_report("\n".join(lines))
        refresh_all()

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 0))
    ttk.Button(bar, text="Validate / Preview",
               command=_validate).pack(side="left")
    ttk.Button(bar, text="Commit import",
               command=_commit).pack(side="left", padx=(6, 0))


def _build_export_pane(gui, parent: ttk.Frame) -> None:
    ttk.Label(parent,
              text=("Export every user (or just one sixth-form role) "
                    "to CSV / JSON / XLSX. XLSX needs the openpyxl "
                    "package; CSV always works."),
              wraplength=820, foreground="#555", justify="left").pack(
        anchor="w", pady=(0, 8))

    row1 = ttk.Frame(parent)
    row1.pack(anchor="w", pady=4)
    ttk.Label(row1, text="Filter role:").pack(side="left", padx=(0, 4))
    role_var = tk.StringVar(value="(all)")
    ttk.Combobox(row1, textvariable=role_var, state="readonly",
                  width=22,
                  values=["(all)"] + list(ROLE_HIERARCHY.keys())
                  ).pack(side="left")

    ttk.Label(row1, text="Format:").pack(side="left", padx=(12, 4))
    fmt_var = tk.StringVar(value="csv")
    ttk.Combobox(row1, textvariable=fmt_var, state="readonly",
                  width=8,
                  values=["csv", "json"]
                       + (["xlsx"] if bulk_io.XLSX_AVAILABLE else [])
                  ).pack(side="left")

    def _go():
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
        fmt = fmt_var.get()
        p = filedialog.asksaveasfilename(
            parent=gui.root,
            defaultextension=f".{fmt}",
            initialfile=f"users_export.{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}")])
        if not p:
            return
        role = role_var.get()
        try:
            n = bulk_io.export(
                gui.auth, p, fmt=fmt,
                sixthform_role=None if role == "(all)" else role)
        except UserAccountError as e:
            messagebox.showerror("Export", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("Export crashed")
            messagebox.showerror("Export", f"Unexpected: {e}",
                                  parent=gui.root)
            return
        messagebox.showinfo("Export",
                             f"Wrote {n} user(s) to:\n{p}",
                             parent=gui.root)

    ttk.Button(parent, text="Export…", command=_go).pack(anchor="w",
                                                            pady=(8, 0))


def _build_onboard_pane(gui, parent: ttk.Frame, refresh_all) -> None:
    ttk.Label(parent,
              text=("Run the onboarding wizard: pick a role template, "
                    "review the permissions preview, fill in profile "
                    "details, and the system creates the user, issues "
                    "a one-time setup token, and emails it to them."),
              wraplength=820, foreground="#555", justify="left").pack(
        anchor="w", pady=(0, 8))

    row1 = ttk.Frame(parent)
    row1.pack(anchor="w", pady=4)
    ttk.Label(row1, text="Template:").pack(side="left", padx=(0, 4))
    tpl_var = tk.StringVar()
    tpl_combo = ttk.Combobox(row1, textvariable=tpl_var,
                               state="readonly", width=32)
    templates = onboarding.list_templates()
    tpl_combo['values'] = [f"{t.label}  ({t.role})" for t in templates]
    tpl_combo.current(0)
    tpl_combo.pack(side="left")

    preview = tk.Text(parent, height=10, wrap="word")
    preview.pack(fill="x", pady=(6, 6))
    preview.configure(state="disabled")

    def _refresh_preview(_e=None):
        i = tpl_combo.current()
        if i < 0 or i >= len(templates):
            return
        t = templates[i]
        text = (f"{t.label}\n"
                f"Role mapped: {t.role}\n\n"
                f"{t.description}\n\n"
                f"Permissions preview:\n"
                + "\n".join(f"  • {p}" for p in t.permissions_preview))
        preview.configure(state="normal")
        preview.delete("1.0", "end")
        preview.insert("1.0", text)
        preview.configure(state="disabled")

    tpl_combo.bind("<<ComboboxSelected>>", _refresh_preview)
    _refresh_preview()

    ttk.Button(parent, text="Start wizard…",
               command=lambda: _open_onboard_wizard(
                   gui, refresh_all,
                   template=templates[tpl_combo.current()])
               ).pack(anchor="w", pady=(0, 0))


def _open_onboard_wizard(gui, refresh_all, *, template) -> None:
    dlg = tk.Toplevel(gui.root)
    dlg.title(f"Onboard — {template.label}")
    dlg.geometry("520x440")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    row_idx = 0

    def _row(label: str, widget: tk.Widget) -> None:
        nonlocal row_idx
        ttk.Label(body, text=label).grid(row=row_idx, column=0,
                                            sticky="e", padx=(0, 8),
                                            pady=3)
        widget.grid(row=row_idx, column=1, sticky="ew", pady=3)
        row_idx += 1

    username_var = tk.StringVar()
    _row("Username *", ttk.Entry(body, textvariable=username_var,
                                    width=40))

    display_var = tk.StringVar()
    _row("Display name", ttk.Entry(body, textvariable=display_var,
                                      width=40))

    email_var = tk.StringVar()
    _row("Email (for welcome link)",
         ttk.Entry(body, textvariable=email_var, width=40))

    phone_var = tk.StringVar()
    _row("Phone", ttk.Entry(body, textvariable=phone_var, width=40))

    dept_var = tk.StringVar(value=template.default_department or "")
    _row("Department", ttk.Entry(body, textvariable=dept_var, width=40))

    title_var = tk.StringVar(value=template.default_job_title or "")
    _row("Job title", ttk.Entry(body, textvariable=title_var, width=40))

    mgr_var = tk.StringVar()
    _row("Line manager user-id (optional)",
         ttk.Entry(body, textvariable=mgr_var, width=40))

    ttk.Label(body,
              text=("A secure random initial password is set; the user "
                    "logs in with the emailed one-time token and "
                    "chooses their own password."),
              foreground="#666", wraplength=480).grid(
        row=row_idx, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _go():
        try:
            mgr_id = int(mgr_var.get().strip()) if mgr_var.get().strip() \
                else None
        except ValueError:
            messagebox.showerror("Onboard",
                                  "Line manager id must be a number.",
                                  parent=dlg)
            return
        try:
            result = onboarding.onboard(
                gui.auth, template_key=template.key,
                username=username_var.get().strip(),
                display_name=display_var.get().strip() or None,
                email=email_var.get().strip() or None,
                phone=phone_var.get(),
                department=dept_var.get(),
                job_title=title_var.get(),
                line_manager_id=mgr_id)
        except UserAccountError as e:
            messagebox.showerror("Onboard", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("onboard crashed")
            messagebox.showerror("Onboard", f"Unexpected: {e}",
                                  parent=dlg)
            return
        dlg.destroy()
        refresh_all()
        messagebox.showinfo(
            "Onboard",
            (f"Created user #{result.user.id} ({result.user.username}).\n"
             f"Template: {result.template.label}\n"
             f"Email sent: {'yes' if result.email_sent else 'no'}\n\n"
             f"One-time setup token (share if email failed):\n"
             f"  {result.token}"),
            parent=gui.root)

    bar = ttk.Frame(body)
    bar.grid(row=row_idx + 1, column=0, columnspan=2, sticky="e",
              pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Onboard",
               command=_go).pack(side="right")
