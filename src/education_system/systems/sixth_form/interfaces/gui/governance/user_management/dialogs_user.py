"""User create/edit, archive, delete, suspend, offboard, rename and merge dialogs.

Split out of ``user_management_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.platform.identity.auth.role_manager import ROLE_HIERARCHY
from education_system.systems.sixth_form.domain.governance.user_management import lifecycle
from education_system.systems.sixth_form.domain.governance.user_management import identity
from education_system.systems.sixth_form.domain.governance.user_management import user_accounts as ua_data
from education_system.systems.sixth_form.domain.governance.user_management.user_accounts import (
    DEFAULT_ROLE,
    SYSTEM_KEY,
    UserAccountError,
)
from ._common import logger


# ── Create / Edit user dialog ──────────────────────────────────────

def _open_user_form(gui, *, auth, user_id: int | None) -> bool:
    """Modal dialog. Returns True on save, False on cancel/error."""
    is_edit = user_id is not None
    title = "Edit user" if is_edit else "Create user"

    # Load existing values for edit mode.
    initial = {}
    if is_edit:
        u = ua_data.get_user(auth, user_id)
        if u is None:
            messagebox.showerror(title, f"No user #{user_id}",
                                  parent=gui.root)
            return False
        extras = lifecycle.get_extras(auth, user_id)
        initial = {
            "username": u.username,
            "display_name": u.display_name or "",
            "email": u.email or "",
            "role": u.role_for(SYSTEM_KEY) or DEFAULT_ROLE,
            "phone": extras.phone or "",
            "department": extras.department or "",
            "job_title": extras.job_title or "",
            "line_manager_id": (str(extras.line_manager_id)
                                 if extras.line_manager_id else ""),
            "notes": extras.notes or "",
        }

    dlg = tk.Toplevel(gui.root)
    dlg.title(title)
    dlg.geometry("520x520")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    row_idx = 0

    def _row(label: str, widget: tk.Widget) -> None:
        nonlocal row_idx
        ttk.Label(body, text=label).grid(row=row_idx, column=0, sticky="e",
                                            padx=(0, 8), pady=3)
        widget.grid(row=row_idx, column=1, sticky="ew", pady=3)
        row_idx += 1

    username_var = tk.StringVar(value=initial.get("username", ""))
    username_entry = ttk.Entry(body, textvariable=username_var, width=40)
    if is_edit:
        username_entry.configure(state="readonly")
    _row("Username *", username_entry)

    password_var = tk.StringVar()
    if not is_edit:
        _row("Password *",
             ttk.Entry(body, textvariable=password_var, show="*", width=40))

    display_var = tk.StringVar(value=initial.get("display_name", ""))
    _row("Display name", ttk.Entry(body, textvariable=display_var,
                                      width=40))

    email_var = tk.StringVar(value=initial.get("email", ""))
    _row("Email", ttk.Entry(body, textvariable=email_var, width=40))

    role_var = tk.StringVar(value=initial.get("role", DEFAULT_ROLE))
    if not is_edit:
        _row("Sixth-form role",
             ttk.Combobox(body, textvariable=role_var, state="readonly",
                          values=list(ROLE_HIERARCHY.keys()), width=38))

    phone_var = tk.StringVar(value=initial.get("phone", ""))
    _row("Phone", ttk.Entry(body, textvariable=phone_var, width=40))

    dept_var = tk.StringVar(value=initial.get("department", ""))
    _row("Department", ttk.Entry(body, textvariable=dept_var, width=40))

    title_var = tk.StringVar(value=initial.get("job_title", ""))
    _row("Job title", ttk.Entry(body, textvariable=title_var, width=40))

    mgr_var = tk.StringVar(value=initial.get("line_manager_id", ""))
    _row("Line manager user-id (optional)",
         ttk.Entry(body, textvariable=mgr_var, width=40))

    ttk.Label(body, text="Notes").grid(row=row_idx, column=0,
                                          sticky="ne", padx=(0, 8), pady=3)
    notes_text = tk.Text(body, height=4, width=40)
    if initial.get("notes"):
        notes_text.insert("1.0", initial["notes"])
    notes_text.grid(row=row_idx, column=1, sticky="ew", pady=3)
    row_idx += 1

    saved = {"ok": False}

    def _gather():
        try:
            mgr = int(mgr_var.get().strip()) if mgr_var.get().strip() else None
        except ValueError:
            raise UserAccountError("Line manager id must be a number.")
        return {
            "username": username_var.get().strip(),
            "password": password_var.get(),
            "display_name": display_var.get().strip() or None,
            "email": email_var.get().strip() or None,
            "role": role_var.get() or DEFAULT_ROLE,
            "phone": phone_var.get(),
            "department": dept_var.get(),
            "job_title": title_var.get(),
            "line_manager_id": mgr,
            "notes": notes_text.get("1.0", "end").strip() or None,
        }

    def _save():
        try:
            fields = _gather()
        except UserAccountError as e:
            messagebox.showerror(title, str(e), parent=dlg)
            return
        try:
            if is_edit:
                lifecycle.update_user_full(
                    auth, user_id,
                    display_name=fields["display_name"],
                    email=fields["email"],
                    phone=fields["phone"],
                    department=fields["department"],
                    job_title=fields["job_title"],
                    line_manager_id=fields["line_manager_id"],
                    notes=fields["notes"])
            else:
                if not fields["username"] or not fields["password"]:
                    raise UserAccountError(
                        "Username and password are required.")
                lifecycle.create_user_full(
                    auth, username=fields["username"],
                    password=fields["password"],
                    display_name=fields["display_name"],
                    email=fields["email"], role=fields["role"],
                    phone=fields["phone"],
                    department=fields["department"],
                    job_title=fields["job_title"],
                    line_manager_id=fields["line_manager_id"],
                    notes=fields["notes"])
        except UserAccountError as e:
            messagebox.showerror(title, str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("%s crashed", title)
            messagebox.showerror(title, f"Unexpected: {e}", parent=dlg)
            return
        saved["ok"] = True
        dlg.destroy()

    bar = ttk.Frame(body)
    bar.grid(row=row_idx, column=0, columnspan=2, sticky="e",
              pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return saved["ok"]


# ── Archive dialog ─────────────────────────────────────────────────

def _open_archive_form(gui, *, auth, user_id: int) -> bool:
    u = ua_data.get_user(auth, user_id)
    if u is None:
        messagebox.showerror("Archive", f"No user #{user_id}",
                              parent=gui.root)
        return False

    dlg = tk.Toplevel(gui.root)
    dlg.title("Archive user")
    dlg.geometry("440x240")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    ttk.Label(body, text=f"User: {u.username} (#{u.id})").grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

    ttk.Label(body, text="Reason:").grid(row=1, column=0, sticky="e",
                                            padx=(0, 8))
    reason_var = tk.StringVar()
    ttk.Entry(body, textvariable=reason_var, width=40).grid(
        row=1, column=1, sticky="ew")

    ttk.Label(body, text="Retention (days):").grid(row=2, column=0,
                                                      sticky="e", padx=(0, 8))
    retention_var = tk.IntVar(value=lifecycle.DEFAULT_RETENTION_DAYS)
    ttk.Spinbox(body, from_=1, to=3650, textvariable=retention_var,
                width=10).grid(row=2, column=1, sticky="w")

    ttk.Label(body, text="Archiving disables login. Restore is possible "
                          "until retention expires.",
              foreground="#666", wraplength=380).grid(
        row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

    ok = {"ok": False}

    def _go():
        try:
            lifecycle.archive_user(auth, user_id,
                                     reason=reason_var.get(),
                                     retention_days=retention_var.get())
        except UserAccountError as e:
            messagebox.showerror("Archive", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("archive_user crashed")
            messagebox.showerror("Archive", f"Unexpected: {e}",
                                  parent=dlg)
            return
        ok["ok"] = True
        dlg.destroy()

    bar = ttk.Frame(body)
    bar.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Archive",
               command=_go).pack(side="right")

    dlg.wait_window()
    return ok["ok"]


# ── Permanent-delete dialog (two-step) ─────────────────────────────

def _open_purge_dialog(gui, *, auth, archive, on_done) -> None:
    username = archive.snapshot.get("username", "")
    if not messagebox.askyesno(
            "Permanent delete",
            f"This permanently deletes user '{username}' "
            f"(#{archive.user_id}) and cannot be undone.\n\n"
            "Proceed to the confirmation step?",
            parent=gui.root):
        return

    dlg = tk.Toplevel(gui.root)
    dlg.title("Permanent delete — confirmation")
    dlg.geometry("420x220")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)

    ttk.Label(body, text=f"Type the username '{username}' to confirm.",
              wraplength=380).pack(anchor="w", pady=(0, 6))
    confirm_var = tk.StringVar()
    ttk.Entry(body, textvariable=confirm_var, width=40
              ).pack(anchor="w", pady=(0, 6))
    ttk.Label(body, text="Reason (optional):").pack(anchor="w")
    reason_var = tk.StringVar()
    ttk.Entry(body, textvariable=reason_var, width=40
              ).pack(anchor="w")

    def _go():
        try:
            ok = lifecycle.purge_user(
                auth, archive.user_id,
                reason=reason_var.get().strip() or None,
                confirmation_token=confirm_var.get())
        except UserAccountError as e:
            messagebox.showerror("Permanent delete", str(e),
                                  parent=dlg)
            return
        except Exception as e:
            logger.exception("purge_user crashed")
            messagebox.showerror("Permanent delete",
                                  f"Unexpected: {e}", parent=dlg)
            return
        if not ok:
            messagebox.showerror("Permanent delete",
                                  "Delete returned without success.",
                                  parent=dlg)
            return
        messagebox.showinfo("Permanent delete",
                              f"User '{username}' permanently deleted.",
                              parent=gui.root)
        dlg.destroy()
        on_done()

    bar = ttk.Frame(body)
    bar.pack(fill="x", pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Permanently delete",
               command=_go).pack(side="right")


# ── Suspend dialog ─────────────────────────────────────────────────

def _open_suspend_form(gui, *, auth, user_id: int) -> bool:
    u = ua_data.get_user(auth, user_id)
    if u is None:
        messagebox.showerror("Suspend", f"No user #{user_id}",
                              parent=gui.root)
        return False

    dlg = tk.Toplevel(gui.root)
    dlg.title("Suspend user")
    dlg.geometry("440x240")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    ttk.Label(body, text=f"User: {u.username} (#{u.id})").grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

    ttk.Label(body, text="Reason:").grid(row=1, column=0, sticky="e",
                                            padx=(0, 8))
    reason_var = tk.StringVar()
    ttk.Entry(body, textvariable=reason_var, width=40
              ).grid(row=1, column=1, sticky="ew")

    ttk.Label(body, text="Auto-resume on (YYYY-MM-DD, optional):").grid(
        row=2, column=0, sticky="e", padx=(0, 8))
    resume_var = tk.StringVar()
    ttk.Entry(body, textvariable=resume_var, width=20).grid(
        row=2, column=1, sticky="w")

    ttk.Label(body,
              text=("Suspension disables the login. Auto-resume is "
                    "informational only — Unsuspend manually when "
                    "ready."),
              foreground="#666", wraplength=380).grid(
        row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

    ok = {"ok": False}

    def _go():
        try:
            lifecycle.suspend_user(
                auth, user_id,
                reason=reason_var.get(),
                resume_at=resume_var.get().strip() or None)
        except UserAccountError as e:
            messagebox.showerror("Suspend", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("suspend crashed")
            messagebox.showerror("Suspend", f"Unexpected: {e}",
                                  parent=dlg)
            return
        ok["ok"] = True
        dlg.destroy()

    bar = ttk.Frame(body)
    bar.grid(row=4, column=0, columnspan=2, sticky="e",
              pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Suspend",
               command=_go).pack(side="right")
    dlg.wait_window()
    return ok["ok"]


# ── Offboard dialog ────────────────────────────────────────────────

def _open_offboard_form(gui, *, auth, user_id: int) -> bool:
    u = ua_data.get_user(auth, user_id)
    if u is None:
        messagebox.showerror("Offboard", f"No user #{user_id}",
                              parent=gui.root)
        return False

    dlg = tk.Toplevel(gui.root)
    dlg.title("Offboard user")
    dlg.geometry("520x320")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    ttk.Label(body, text=f"Offboarding user: {u.username} (#{u.id})",
              font=("", 11, "bold")).grid(row=0, column=0, columnspan=2,
                                            sticky="w", pady=(0, 8))
    ttk.Label(body, text=("This is a single-action workflow: rotate "
                            "password (invalidates sessions), record a "
                            "reassignment plan, then archive."),
              foreground="#666", wraplength=480).grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))

    ttk.Label(body, text="Reason:").grid(row=2, column=0, sticky="e",
                                            padx=(0, 8))
    reason_var = tk.StringVar(value="Offboarding")
    ttk.Entry(body, textvariable=reason_var, width=46).grid(
        row=2, column=1, sticky="ew")

    ttk.Label(body, text="Retention (days):").grid(row=3, column=0,
                                                      sticky="e", padx=(0, 8))
    ret_var = tk.IntVar(value=lifecycle.DEFAULT_RETENTION_DAYS)
    ttk.Spinbox(body, from_=1, to=3650, textvariable=ret_var,
                width=10).grid(row=3, column=1, sticky="w")

    ttk.Label(body, text="Reassign owned records to user-id "
                          "(optional):").grid(
        row=4, column=0, sticky="e", padx=(0, 8))
    reassign_var = tk.StringVar()
    ttk.Entry(body, textvariable=reassign_var, width=14).grid(
        row=4, column=1, sticky="w")

    ok = {"ok": False}

    def _go():
        try:
            r_id = (int(reassign_var.get().strip())
                    if reassign_var.get().strip() else None)
        except ValueError:
            messagebox.showerror("Offboard",
                                  "Reassign id must be a number.",
                                  parent=dlg)
            return
        try:
            result = lifecycle.offboard_user(
                auth, user_id,
                reason=reason_var.get(),
                retention_days=ret_var.get(),
                reassign_to_user_id=r_id)
        except UserAccountError as e:
            messagebox.showerror("Offboard", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("offboard crashed")
            messagebox.showerror("Offboard", f"Unexpected: {e}",
                                  parent=dlg)
            return
        ok["ok"] = True
        dlg.destroy()
        messagebox.showinfo(
            "Offboard",
            (f"Offboarded user #{user_id}.\n"
             f"  Archive #{result.archive_id}\n"
             f"  Sessions invalidated: "
             f"{'yes' if result.sessions_invalidated else 'no'}\n\n"
             "Reassignment plan logged. Per-domain re-owners "
             "still need to be run for any records owned by this "
             "user."),
            parent=gui.root)

    bar = ttk.Frame(body)
    bar.grid(row=5, column=0, columnspan=2, sticky="e",
              pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Offboard",
               command=_go).pack(side="right")
    dlg.wait_window()
    return ok["ok"]


# ── Rename dialog (feature 11) ─────────────────────────────────────

def _open_rename_form(gui, *, auth, user_id: int) -> bool:
    u = ua_data.get_user(auth, user_id)
    if u is None:
        messagebox.showerror("Rename", f"No user #{user_id}",
                              parent=gui.root)
        return False
    dlg = tk.Toplevel(gui.root)
    dlg.title("Rename user")
    dlg.geometry("480x260")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    ttk.Label(body, text=f"User #{u.id} — current username "
                          f"'{u.username}'.").grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

    ttk.Label(body, text="New username:").grid(row=1, column=0,
                                                  sticky="e", padx=(0, 6))
    uname_var = tk.StringVar(value=u.username)
    ttk.Entry(body, textvariable=uname_var, width=40).grid(
        row=1, column=1, sticky="ew")

    ttk.Label(body, text="New display name:").grid(row=2, column=0,
                                                      sticky="e",
                                                      padx=(0, 6))
    disp_var = tk.StringVar(value=u.display_name or "")
    ttk.Entry(body, textvariable=disp_var, width=40).grid(
        row=2, column=1, sticky="ew")

    ttk.Label(body, text="Reason:").grid(row=3, column=0, sticky="e",
                                            padx=(0, 6))
    reason_var = tk.StringVar()
    ttk.Entry(body, textvariable=reason_var, width=40).grid(
        row=3, column=1, sticky="ew")

    ttk.Label(body, text=("Prior values are kept in "
                          "user_name_history."),
              foreground="#666").grid(row=4, column=0, columnspan=2,
                                        sticky="w", pady=(8, 0))

    ok = {"ok": False}

    def _go():
        try:
            identity.force_rename(
                auth, user_id,
                new_username=uname_var.get().strip(),
                new_display_name=disp_var.get().strip() or None,
                reason=reason_var.get().strip() or None)
        except UserAccountError as e:
            messagebox.showerror("Rename", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("rename crashed")
            messagebox.showerror("Rename", f"Unexpected: {e}",
                                  parent=dlg)
            return
        ok["ok"] = True
        dlg.destroy()

    bar = ttk.Frame(body)
    bar.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Rename",
               command=_go).pack(side="right")
    dlg.wait_window()
    return ok["ok"]


# ── Merge dialog (feature 12) ──────────────────────────────────────

def _open_merge_form(gui, *, auth, ids: list[int]) -> bool:
    u1 = ua_data.get_user(auth, ids[0])
    u2 = ua_data.get_user(auth, ids[1])
    if u1 is None or u2 is None:
        messagebox.showerror("Merge",
                              "One or both users missing.",
                              parent=gui.root)
        return False
    dlg = tk.Toplevel(gui.root)
    dlg.title("Merge users")
    dlg.geometry("520x300")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    ttk.Label(body, text="Pick the canonical user (the loser is "
                          "archived).",
              wraplength=480).grid(row=0, column=0, columnspan=2,
                                     sticky="w", pady=(0, 8))

    canonical_var = tk.IntVar(value=u1.id)
    ttk.Radiobutton(body,
                    text=f"#{u1.id} {u1.username} ({u1.display_name or ''})",
                    variable=canonical_var,
                    value=u1.id).grid(row=1, column=0, columnspan=2,
                                        sticky="w")
    ttk.Radiobutton(body,
                    text=f"#{u2.id} {u2.username} ({u2.display_name or ''})",
                    variable=canonical_var,
                    value=u2.id).grid(row=2, column=0, columnspan=2,
                                        sticky="w")

    ttk.Label(body, text="Reason:").grid(row=3, column=0, sticky="e",
                                            padx=(0, 6), pady=(8, 0))
    reason_var = tk.StringVar()
    ttk.Entry(body, textvariable=reason_var, width=46).grid(
        row=3, column=1, sticky="ew", pady=(8, 0))

    ttk.Label(body, text=("Cross-domain records (gradebook, finance, "
                          "housing) are NOT moved by this action — run "
                          "each domain's reassign tool separately."),
              foreground="#666",
              wraplength=480).grid(row=4, column=0, columnspan=2,
                                     sticky="w", pady=(8, 0))

    ok = {"ok": False}

    def _go():
        canonical = canonical_var.get()
        loser = u2.id if canonical == u1.id else u1.id
        if not messagebox.askyesno(
                "Merge",
                f"Merge #{loser} into #{canonical}? The loser will be "
                f"archived and its sessions invalidated.",
                parent=dlg):
            return
        try:
            r = identity.merge_accounts(
                auth, canonical_user_id=canonical,
                loser_user_id=loser,
                reason=reason_var.get().strip() or None)
        except UserAccountError as e:
            messagebox.showerror("Merge", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("merge crashed")
            messagebox.showerror("Merge", f"Unexpected: {e}",
                                  parent=dlg)
            return
        ok["ok"] = True
        dlg.destroy()
        summary = "\n".join(f"  {t}: {n}"
                              for t, n in sorted(r.moved.items()))
        messagebox.showinfo("Merge",
                              (f"Merged #{loser} -> #{canonical}.\n\n"
                               f"Rows moved:\n{summary}\n\n"
                               f"{r.cross_domain_note}"),
                              parent=gui.root)

    bar = ttk.Frame(body)
    bar.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Merge",
               command=_go).pack(side="right")
    dlg.wait_window()
    return ok["ok"]
