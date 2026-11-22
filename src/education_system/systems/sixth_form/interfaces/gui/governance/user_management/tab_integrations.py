"""Integrations tab (SSO, sync, webhooks, saved filters, notes) of User Management.

Split out of ``user_management_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.governance.user_management import integrations as integ
from education_system.systems.sixth_form.domain.governance.user_management.user_accounts import (
    UserAccountError,
)


# ── Integrations tab (44-47) + saved filters + notes ───────────────

def _build_integrations_tab(gui, parent: ttk.Frame, refresh_all) -> None:
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)

    sso_p = ttk.Frame(nb, padding=8)
    sync_p = ttk.Frame(nb, padding=8)
    hooks_p = ttk.Frame(nb, padding=8)
    filt_p = ttk.Frame(nb, padding=8)
    notes_p = ttk.Frame(nb, padding=8)

    nb.add(sso_p,  text="SSO mappings")
    nb.add(sync_p, text="HRIS / MIS sync")
    nb.add(hooks_p, text="Webhooks")
    nb.add(filt_p, text="Saved filters")
    nb.add(notes_p, text="Admin notes")

    _build_sso_pane(gui, sso_p)
    _build_sync_pane(gui, sync_p, refresh_all)
    _build_webhooks_pane(gui, hooks_p)
    _build_filters_pane(gui, filt_p)
    _build_notes_pane(gui, notes_p)


def _build_sso_pane(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 4))
    ttk.Label(bar, text="User id:").pack(side="left", padx=(0, 4))
    uid = tk.StringVar()
    ttk.Entry(bar, textvariable=uid, width=8).pack(side="left",
                                                       padx=(0, 8))
    ttk.Label(bar, text="Provider:").pack(side="left", padx=(0, 4))
    prov = tk.StringVar()
    ttk.Combobox(bar, textvariable=prov, state="readonly", width=14,
                  values=["microsoft", "google", "other"]
                  ).pack(side="left", padx=(0, 8))
    ttk.Label(bar, text="Subject:").pack(side="left", padx=(0, 4))
    sub = tk.StringVar()
    ttk.Entry(bar, textvariable=sub, width=28).pack(side="left",
                                                        padx=(0, 8))
    ttk.Label(bar, text="Email:").pack(side="left", padx=(0, 4))
    em = tk.StringVar()
    ttk.Entry(bar, textvariable=em, width=22).pack(side="left",
                                                       padx=(0, 8))

    cols = ("id", "uid", "provider", "subject", "email", "created")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=14)
    for c, lbl, w in [("id", "ID", 60),
                       ("uid", "User #", 60),
                       ("provider", "Provider", 100),
                       ("subject", "External subject", 220),
                       ("email", "Email", 200),
                       ("created", "Created", 160)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(4, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for r in integ.list_sso_mappings(gui.auth):
            tree.insert("", "end", iid=str(r["id"]), values=(
                r["id"], r["user_id"], r["provider"],
                r["external_subject"], r["email"] or "",
                r["created_at"]))

    def _add():
        if not uid.get().strip().isdigit():
            return
        try:
            integ.add_sso_mapping(
                gui.auth, user_id=int(uid.get()),
                provider=prov.get() or "other",
                external_subject=sub.get().strip(),
                email=em.get().strip() or None)
        except UserAccountError as e:
            messagebox.showerror("SSO", str(e), parent=gui.root)
            return
        _refresh()

    def _remove():
        sel = tree.focus()
        if not sel:
            return
        integ.remove_sso_mapping(gui.auth, int(sel))
        _refresh()

    ttk.Button(bar, text="Add",
               command=_add).pack(side="left", padx=(0, 4))
    ttk.Button(bar, text="Remove selected",
               command=_remove).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Refresh",
               command=_refresh).pack(side="left")
    _refresh()


def _build_sync_pane(gui, parent: ttk.Frame, refresh_all) -> None:
    ttk.Label(parent,
              text=("Compare a CSV feed (HRIS / MIS) against the local "
                    "users. Columns expected: external_id, username, "
                    "display_name, email, department, job_title. "
                    "Reconcile, then create only the rows you want."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 4))
    path = tk.StringVar()
    ttk.Entry(bar, textvariable=path, width=60).pack(side="left",
                                                          padx=(0, 4))

    def _browse():
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
        p = filedialog.askopenfilename(
            parent=gui.root, title="Pick feed",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if p:
            path.set(p)

    ttk.Button(bar, text="Browse…",
               command=_browse).pack(side="left", padx=(0, 8))

    out = tk.Text(parent, height=20, wrap="word")
    out.pack(fill="both", expand=True, pady=(6, 6))
    out.configure(state="disabled")
    state = {"report": None}

    def _preview():
        if not path.get().strip():
            return
        try:
            r = integ.reconcile_sync(gui.auth, path.get().strip())
        except UserAccountError as e:
            messagebox.showerror("Sync", str(e), parent=gui.root)
            return
        state["report"] = r
        lines = [
            f"New (in feed, not local): {len(r.new)}",
            f"Matched: {len(r.matched)}",
            f"Missing externally (in local, not feed): "
            f"{len(r.missing_externally)}",
            "",
        ]
        for row in r.new:
            lines.append(f"  + {row.username} · {row.display_name or ''} "
                          f"· {row.email or ''} · {row.department or ''}")
        out.configure(state="normal")
        out.delete("1.0", "end")
        out.insert("1.0", "\n".join(lines))
        out.configure(state="disabled")

    def _apply_create():
        r = state.get("report")
        if r is None or not r.new:
            messagebox.showinfo("Sync",
                                 "Run a preview with 'new' rows first.",
                                 parent=gui.root)
            return
        if not messagebox.askyesno(
                "Sync",
                f"Create {len(r.new)} user(s) with role 'student' on "
                f"sixth-form? Random initial passwords will be set.",
                parent=gui.root):
            return
        ids = integ.apply_sync_create(
            gui.auth, r.new, role="student",
            system_key="sixth_form")
        messagebox.showinfo("Sync",
                              f"Created {len(ids)} user(s).",
                              parent=gui.root)
        refresh_all()

    bar2 = ttk.Frame(parent)
    bar2.pack(fill="x")
    ttk.Button(bar2, text="Preview reconcile",
               command=_preview).pack(side="left")
    ttk.Button(bar2, text="Create new (role=student)",
               command=_apply_create).pack(side="left", padx=(6, 0))


def _build_webhooks_pane(gui, parent: ttk.Frame) -> None:
    ttk.Label(parent,
              text=("Register external URLs to receive user events. "
                    "Subscribed events go to the outbox; a delivery "
                    "worker (not shipped here) would POST them."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))
    bar = ttk.Frame(parent)
    bar.pack(anchor="w")
    url = tk.StringVar()
    ttk.Entry(bar, textvariable=url, width=46).pack(side="left",
                                                        padx=(0, 4))
    events = tk.StringVar(value="user_create,user_archive,user_purge")
    ttk.Entry(bar, textvariable=events, width=40).pack(side="left",
                                                            padx=(0, 4))
    secret = tk.StringVar()
    ttk.Entry(bar, textvariable=secret, width=20).pack(side="left",
                                                            padx=(0, 4))

    cols = ("id", "url", "events", "active")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=12)
    for c, lbl, w in [("id", "ID", 50),
                       ("url", "URL", 360),
                       ("events", "Events", 320),
                       ("active", "Active", 70)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(6, 4))

    out = tk.Text(parent, height=10, wrap="none")
    out.pack(fill="both", expand=True)
    out.configure(state="disabled")

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for w in integ.list_webhooks(gui.auth):
            tree.insert("", "end", iid=str(w["id"]), values=(
                w["id"], w["url"], w["events"],
                "yes" if w["is_active"] else "no"))
        out.configure(state="normal")
        out.delete("1.0", "end")
        for r in integ.list_outbox(gui.auth, limit=30):
            out.insert("end",
                         f"#{r['id']:>4}  ep={r['endpoint_id']}  "
                         f"event={r['event']:<20}  "
                         f"status={r['status']:<10}  "
                         f"enqueued={r['enqueued_at']}\n")
        out.configure(state="disabled")

    def _add():
        if not url.get().strip():
            return
        evs = [e.strip() for e in events.get().split(",") if e.strip()]
        try:
            integ.add_webhook(gui.auth, url=url.get().strip(),
                                events=evs,
                                secret=secret.get().strip() or None)
        except UserAccountError as e:
            messagebox.showerror("Webhooks", str(e), parent=gui.root)
            return
        _refresh()

    def _remove():
        sel = tree.focus()
        if not sel:
            return
        integ.remove_webhook(gui.auth, int(sel))
        _refresh()

    btns = ttk.Frame(parent)
    btns.pack(fill="x")
    ttk.Button(btns, text="Add",
               command=_add).pack(side="left", padx=(0, 4))
    ttk.Button(btns, text="Disable selected",
               command=_remove).pack(side="left", padx=(0, 8))
    ttk.Button(btns, text="Refresh",
               command=_refresh).pack(side="left")
    _refresh()


def _build_filters_pane(gui, parent: ttk.Frame) -> None:
    ttk.Label(parent,
              text=("Save a filter payload (any JSON-able dict). The "
                    "Users tab could load these as quick filters."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))

    bar = ttk.Frame(parent)
    bar.pack(anchor="w")
    name = tk.StringVar()
    ttk.Entry(bar, textvariable=name, width=22).pack(side="left",
                                                          padx=(0, 4))
    payload = tk.StringVar(
        value='{"scope": "Locked", "query": ""}')
    ttk.Entry(bar, textvariable=payload, width=50).pack(side="left",
                                                            padx=(0, 4))

    cols = ("id", "name", "payload", "created_at")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=14)
    for c, lbl, w in [("id", "ID", 50),
                       ("name", "Name", 200),
                       ("payload", "Payload", 460),
                       ("created_at", "Created", 160)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(6, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        import json
        for f in integ.list_filters(gui.auth):
            tree.insert("", "end", iid=str(f["id"]), values=(
                f["id"], f["name"],
                json.dumps(f["payload"], default=str),
                f["created_at"]))

    def _save():
        if not name.get().strip():
            return
        import json
        try:
            pl = json.loads(payload.get() or "{}")
        except Exception:
            messagebox.showerror("Filter", "Payload must be JSON.",
                                  parent=gui.root)
            return
        try:
            integ.save_filter(gui.auth, name=name.get().strip(),
                                 payload=pl)
        except UserAccountError as e:
            messagebox.showerror("Filter", str(e), parent=gui.root)
            return
        _refresh()

    def _delete():
        sel = tree.focus()
        if not sel:
            return
        row = next((f for f in integ.list_filters(gui.auth)
                     if str(f["id"]) == sel), None)
        if row is None:
            return
        integ.delete_filter(gui.auth, name=row["name"])
        _refresh()

    btns = ttk.Frame(parent)
    btns.pack(fill="x")
    ttk.Button(btns, text="Save",
               command=_save).pack(side="left", padx=(0, 4))
    ttk.Button(btns, text="Delete selected",
               command=_delete).pack(side="left")
    _refresh()


def _build_notes_pane(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 6))
    ttk.Label(bar, text="User id:").pack(side="left", padx=(0, 4))
    uid = tk.StringVar()
    ttk.Entry(bar, textvariable=uid, width=8).pack(side="left",
                                                       padx=(0, 8))
    body = tk.StringVar()
    ttk.Entry(bar, textvariable=body, width=60).pack(side="left",
                                                          padx=(0, 4))
    visible = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="Visible to user",
                    variable=visible).pack(side="left", padx=(0, 4))

    cols = ("id", "ts", "author", "body", "vis")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=14)
    for c, lbl, w in [("id", "ID", 60),
                       ("ts", "When", 160),
                       ("author", "Author", 120),
                       ("body", "Note", 460),
                       ("vis", "User-visible", 110)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(4, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        if not uid.get().strip().isdigit():
            return
        for n in integ.list_notes(gui.auth, int(uid.get())):
            tree.insert("", "end", iid=str(n["id"]), values=(
                n["id"], n["created_at"], n["author"] or "",
                n["body"],
                "yes" if n["visible_to_user"] else "no"))

    def _add():
        if not uid.get().strip().isdigit() or not body.get().strip():
            return
        try:
            integ.add_note(gui.auth, user_id=int(uid.get()),
                              body=body.get().strip(),
                              visible_to_user=visible.get())
        except UserAccountError as e:
            messagebox.showerror("Note", str(e), parent=gui.root)
            return
        body.set("")
        _refresh()

    def _delete():
        sel = tree.focus()
        if not sel:
            return
        integ.delete_note(gui.auth, int(sel))
        _refresh()

    btns = ttk.Frame(parent)
    btns.pack(fill="x")
    ttk.Button(btns, text="Add",
               command=_add).pack(side="left", padx=(0, 4))
    ttk.Button(btns, text="Delete selected",
               command=_delete).pack(side="left", padx=(0, 8))
    ttk.Button(btns, text="Load / refresh",
               command=_refresh).pack(side="left")
    _refresh()
