"""Onboarding templates tab and editor.

Templates are stored and versioned in the onboarding database
(:mod:`onboarding.templates`). The tab lists every template — base and
add-on, retired ones on request — with its tasks, shows the saved
versions of the selected one, and (for onboarding writers) edits a
template, retires / reactivates it with a reason, and applies it to an
open checklist.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
    simpledialog,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    templates as tpl,
)
from education_system.systems.sixth_form.interfaces.gui._ui import (
    grab_when_viewable,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)
from education_system.systems.sixth_form.interfaces.gui.admissions.onboarding import (
    onboarding_actions as actions,
)

logger = logging.getLogger(__name__)


def _describe(t: tpl.Template) -> str:
    req = sum(1 for i in t.items if i.required)
    bits = [t.kind, f"v{t.version}", f"{len(t.items)} tasks, {req} required"]
    if t.learner_type:
        bits.insert(1, t.learner_type)
    return (f"{t.name}  ({', '.join(bits)})"
            + ("" if t.active else "  [RETIRED]"))


def apply_template_dialog(parent: tk.Misc, checklist_id: int,
                          initial: str | None = None) -> list[str] | None:
    """Pick an active template and add its tasks to the checklist.
    Returns the tasks added, or None when cancelled."""
    names = tpl.template_names(kind=None)
    if not names:
        messagebox.showinfo("Apply template", "There are no active "
                            "templates.", parent=parent)
        return None
    holder: dict[str, list[str]] = {}

    def run(v: dict[str, Any]) -> None:
        if not v["template"]:
            raise data.ValidationError("Pick a template")
        holder["added"] = tpl.apply_template(checklist_id, v["template"])

    v = ui.ask_form(parent, f"Apply template — checklist #{checklist_id}", [
        ("template", "Template", "readonly", names)],
        {"template": initial or ""}, on_submit=run)
    if v is None:
        return None
    added = holder.get("added", [])
    messagebox.showinfo(
        "Apply template",
        (f"{len(added)} task(s) added:\n" + "\n".join(f"• {t}" for t in added))
        if added else "The checklist already had every task in that "
        "template (required flags were brought in line).", parent=parent)
    return added


# ══ Templates tab ═════════════════════════════════════════════════

class TemplatesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Templates")
        self._writable = actions.can_write()
        self._write_buttons: list[ttk.Button] = []
        self._templates: dict[str, tpl.Template] = {}
        self._build()
        self.refresh()

    def _wbtn(self, parent: tk.Misc, text: str,
              command: Callable[[], None]) -> ttk.Button:
        b = ttk.Button(parent, text=text, command=command)
        self._write_buttons.append(b)
        return b

    def _build(self) -> None:
        ttk.Label(
            self.frame,
            text="Templates are stored in the onboarding database. Every "
                 "save is a new version (checklists keep the version they "
                 "were made from). Base templates open a checklist; add-ons "
                 "are added on top for the learners they apply to. Retired "
                 "templates are kept but not offered.",
            foreground="#555", wraplength=1000, anchor="w",
            justify="left",
        ).pack(fill="x", padx=12, pady=(12, 6))

        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=12, pady=(0, 6))
        self._wbtn(bar, "New template…", self._new).pack(side="left")
        self._wbtn(bar, "Edit…", self._edit).pack(side="left", padx=4)
        self._wbtn(bar, "Retire…",
                   lambda: self._set_active(False)).pack(side="left", padx=4)
        self._wbtn(bar, "Reactivate…",
                   lambda: self._set_active(True)).pack(side="left", padx=4)
        self._wbtn(bar, "Apply to checklist…",
                   self._apply).pack(side="left", padx=(12, 4))
        self.inactive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Show retired",
                        variable=self.inactive_var,
                        command=self.refresh).pack(side="left", padx=(12, 4))
        ttk.Button(bar, text="Refresh",
                   command=self.refresh).pack(side="right")
        if not self._writable:
            ttk.Label(bar, foreground="#a33",
                      text="Read-only").pack(side="right", padx=8)

        # Versions of the selected template — packed before the tree.
        vbox = ttk.LabelFrame(self.frame, text="Versions of the selected "
                              "template (double-click to see its tasks)")
        vbox.pack(side="bottom", fill="x", padx=12, pady=(6, 12))
        self.ver_tree = ttk.Treeview(
            vbox, columns=("version", "saved", "by", "tasks", "note",
                           "changes"), show="headings", height=6)
        for key, text, width in (("version", "Ver.", 50),
                                 ("saved", "Saved", 140), ("by", "By", 110),
                                 ("tasks", "Tasks", 55),
                                 ("note", "Note", 330),
                                 ("changes", "What changed", 520)):
            self.ver_tree.heading(key, text=text)
            self.ver_tree.column(key, width=width, anchor="w")
        self.ver_tree.pack(fill="x", padx=4, pady=4)
        self.ver_tree.bind("<Double-1>", lambda _e: self._show_version())

        cols = ("template", "category", "required", "task", "owner", "due",
                "sensitive")
        holder = ttk.Frame(self.frame)
        holder.pack(fill="both", expand=True, padx=12)
        self.tree = ttk.Treeview(holder, columns=cols, show="tree headings")
        self.tree.heading("#0", text="")
        for key, text, width in (("template", "Template", 200),
                                 ("category", "Category", 160),
                                 ("required", "Req.", 50),
                                 ("task", "Task", 430),
                                 ("owner", "Owner", 100),
                                 ("due", "Due (days)", 80),
                                 ("sensitive", "Sensitive", 70)):
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor="w")
        self.tree.column("#0", width=380)
        self.tree.column("required", anchor="center")
        vs = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("retired", foreground="#999")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._versions())
        self.tree.bind("<Double-1>", lambda _e: self._edit())
        actions.set_write_state(self._write_buttons, self._writable)

    def refresh(self) -> None:
        keep = self._selected_name()
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = tpl.list_templates(include_inactive=self.inactive_var.get())
        except Exception as e:  # noqa: BLE001 — shown
            logger.exception("Onboarding templates failed to load")
            messagebox.showerror("Templates", str(e),
                                 parent=self.frame.winfo_toplevel())
            return
        self._templates = {t.name: t for t in rows}
        rows.sort(key=lambda t: (not t.active, t.kind != "base", t.name))
        for t in rows:
            tags = () if t.active else ("retired",)
            parent = self.tree.insert(
                "", "end", iid=f"t:{t.name}", text=_describe(t),
                values=(t.name, "", "", t.description or "", "", "", ""),
                open=False, tags=tags)
            for i in t.items:
                self.tree.insert(parent, "end", tags=tags, values=(
                    "", i.category, "✓" if i.required else "", i.task,
                    i.owner_role or "", i.due_offset_days,
                    "yes" if i.sensitive else ""))
        if keep and self.tree.exists(f"t:{keep}"):
            self.tree.selection_set(f"t:{keep}")
        self._versions()

    def _selected_name(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            return None
        iid = sel[0]
        if not iid.startswith("t:"):
            iid = self.tree.parent(iid)
        return iid[2:] if iid.startswith("t:") else None

    def _require_name(self, title: str) -> str | None:
        name = self._selected_name()
        if name is None:
            messagebox.showinfo(title, "Select a template first.",
                                parent=self.frame.winfo_toplevel())
        return name

    def _versions(self) -> None:
        for i in self.ver_tree.get_children():
            self.ver_tree.delete(i)
        name = self._selected_name()
        if not name:
            return
        try:
            rows = tpl.versions(name)
        except Exception:  # noqa: BLE001
            logger.exception("Template versions failed to load")
            return
        for r in rows:
            self.ver_tree.insert("", "end", iid=str(r["version"]), values=(
                r["version"], r["saved_at"] or "", r["saved_by"] or "—",
                r["tasks"], r["note"] or "", r["changes"] or ""))

    def _show_version(self) -> None:
        name = self._selected_name()
        sel = self.ver_tree.selection()
        if not name or not sel:
            return
        t = tpl.get_template(name, version=int(sel[0]))
        if t is None:
            return
        lines = [f"{t.name} — version {t.version}",
                 f"Saved {t.updated_at or '—'} by {t.updated_by or '—'}",
                 f"Kind: {t.kind}   Learner type: {t.learner_type or '—'}",
                 f"{t.description or ''}", ""]
        for i in t.items:
            lines.append(
                f"{'*' if i.required else ' '} {i.task}  [{i.category}; "
                f"owner {i.owner_role or '—'}; +{i.due_offset_days}d"
                + ("; sensitive" if i.sensitive else "") + "]"
                + (f"  (rule key: {i.key})" if i.key != i.task else ""))
        ui.show_text(self.frame.winfo_toplevel(),
                     f"{t.name} v{t.version}", "\n".join(lines))

    # ── actions ────────────────────────────────────────────────────
    def _new(self) -> None:
        TemplateEditor(self.frame.winfo_toplevel(), None,
                       on_save=self.refresh)

    def _edit(self) -> None:
        if not self._writable:
            return
        name = self._require_name("Edit template")
        if name is None:
            return
        t = tpl.get_template(name)
        if t is not None:
            TemplateEditor(self.frame.winfo_toplevel(), t,
                           on_save=self.refresh)

    def _set_active(self, active: bool) -> None:
        name = self._require_name("Template")
        if name is None:
            return
        t = self._templates.get(name)
        if t is not None and t.active == active:
            messagebox.showinfo("Template", f"{name!r} is already "
                                f"{'active' if active else 'retired'}.",
                                parent=self.frame.winfo_toplevel())
            return
        verb = "Reactivate" if active else "Retire"
        if actions.prompt_text(
                self.frame.winfo_toplevel(), f"{verb} template",
                f"{verb} {name!r}?\n\n" + (
                    "It will be offered again for new checklists."
                    if active else "It stops being offered for new "
                    "checklists; checklists already made from it keep it."),
                label="Reason:", min_chars=5,
                on_submit=lambda r: tpl.set_active(name, active,
                                                   reason=r)) is None:
            return
        self.refresh()

    def _apply(self) -> None:
        name = self._selected_name()
        cid = simpledialog.askinteger(
            "Apply template", "Checklist # to add the template's tasks to:",
            parent=self.frame.winfo_toplevel(), minvalue=1)
        if cid is None:
            return
        apply_template_dialog(self.frame.winfo_toplevel(), cid, name)


# ══ Template editor ═══════════════════════════════════════════════

class TemplateEditor:
    """Edit a template's details and task list; Save writes a new
    version with a note."""

    COLS = (("task", "Task", 330), ("key", "Rule key", 200),
            ("category", "Category", 150), ("req", "Req.", 45),
            ("due", "Due +days", 75), ("owner", "Owner", 100),
            ("sens", "Sensitive", 70))

    def __init__(self, parent: tk.Misc, existing: tpl.Template | None, *,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.items: list[dict[str, Any]] = [
            dict(i.__dict__) for i in (existing.items if existing else [])]
        self.win = make_toplevel(parent)
        self.win.title(f"Edit template — {existing.name}" if existing
                       else "New onboarding template")
        self.win.geometry("1100x640")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()
        self._render()

    def _build(self) -> None:
        top = ttk.Frame(self.win, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Name:").grid(row=0, column=0, sticky="e")
        self.name_e = ttk.Entry(top, width=40)
        self.name_e.grid(row=0, column=1, sticky="w", padx=4, pady=2)
        if self.existing:
            self.name_e.insert(0, self.existing.name)
            self.name_e.configure(state="readonly")
        ttk.Label(top, text="Kind:").grid(row=0, column=2, sticky="e")
        self.kind_cb = ttk.Combobox(top, values=tpl.KINDS, state="readonly",
                                    width=8)
        self.kind_cb.set(self.existing.kind if self.existing else "base")
        self.kind_cb.grid(row=0, column=3, sticky="w", padx=4)
        ttk.Label(top, text="Learner type:").grid(row=1, column=0,
                                                  sticky="e")
        self.type_cb = ttk.Combobox(top, values=("",) + tpl.LEARNER_TYPES,
                                    state="readonly", width=30)
        self.type_cb.set((self.existing.learner_type or "")
                         if self.existing else "")
        self.type_cb.grid(row=1, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(top, text="Description:").grid(row=1, column=2,
                                                 sticky="e")
        self.desc_e = ttk.Entry(top, width=60)
        if self.existing and self.existing.description:
            self.desc_e.insert(0, self.existing.description)
        self.desc_e.grid(row=1, column=3, sticky="w", padx=4)

        # Save bar and task buttons first (bottom), then the table.
        save = ttk.Frame(self.win, padding=(10, 4, 10, 10))
        save.pack(side="bottom", fill="x")
        ttk.Label(save, text="Note for this version:").pack(side="left")
        self.note_e = ttk.Entry(save, width=60)
        self.note_e.pack(side="left", padx=4)
        ttk.Button(save, text="Save new version",
                   command=self._save).pack(side="left", padx=(8, 4))
        ttk.Button(save, text="Cancel",
                   command=self.win.destroy).pack(side="left")
        tbar = ttk.Frame(self.win, padding=(10, 0))
        tbar.pack(side="bottom", fill="x")
        for text, cmd in (("Add task…", self._add), ("Edit task…", self._edit),
                          ("Remove task", self._remove),
                          ("Move up", lambda: self._move(-1)),
                          ("Move down", lambda: self._move(1))):
            ttk.Button(tbar, text=text, command=cmd).pack(side="left",
                                                           padx=(0, 4))
        holder = ttk.Frame(self.win, padding=(10, 4))
        holder.pack(fill="both", expand=True)
        self.tree = ui.make_tree(holder, list(self.COLS), height=16)
        self.tree.bind("<Double-1>", lambda _e: self._edit())

    def _render(self, select: int | None = None) -> None:
        ui.clear(self.tree)
        for n, i in enumerate(self.items):
            self.tree.insert("", "end", iid=str(n), values=(
                i.get("task", ""), i.get("key", ""), i.get("category", ""),
                "✓" if i.get("required", True) else "",
                i.get("due_offset_days", ""), i.get("owner_role") or "",
                "yes" if i.get("sensitive") else ""))
        if select is not None and self.tree.exists(str(select)):
            self.tree.selection_set(str(select))

    def _selected(self) -> int | None:
        iid = ui.require_iid(self.tree, "Template task")
        return int(iid) if iid is not None else None

    def _task_form(self, title: str, initial: dict[str, Any]
                   ) -> dict[str, Any] | None:
        fields = [("task", "Task", "entry", None),
                  ("category", "Category", "readonly", data.CATEGORIES),
                  ("required", "Required", "check", None),
                  ("due_offset_days", "Due (days after start)", "entry",
                   None),
                  ("owner_role", "Owner", "readonly",
                   ("",) + tpl.OWNER_ROLES),
                  ("sensitive", "Sensitive", "check", None)]

        def check(v: dict[str, Any]) -> None:
            if not v["task"]:
                raise data.ValidationError("A task name is required")
            if v["category"] not in data.CATEGORIES:
                raise data.ValidationError("Pick a category")
            try:
                off = int(v["due_offset_days"] or 14)
            except ValueError:
                raise data.ValidationError("Due offset must be a whole "
                                           "number of days") from None
            if not tpl.MIN_OFFSET <= off <= tpl.MAX_OFFSET:
                raise data.ValidationError(
                    f"Due offset must be {tpl.MIN_OFFSET}..{tpl.MAX_OFFSET}")

        return ui.ask_form(self.win, title, fields, initial, on_submit=check)

    def _add(self) -> None:
        v = self._task_form("Add task", {"category": data.DEFAULT_CATEGORY,
                                         "required": True,
                                         "due_offset_days": 14})
        if v is None:
            return
        v["due_offset_days"] = int(v["due_offset_days"] or 14)
        v["key"] = v["task"]
        v["owner_role"] = v["owner_role"] or None
        self.items.append(v)
        self._render(len(self.items) - 1)

    def _edit(self) -> None:
        n = self._selected()
        if n is None:
            return
        cur = self.items[n]
        v = self._task_form(f"Edit task (rule key: {cur.get('key')})", cur)
        if v is None:
            return
        v["due_offset_days"] = int(v["due_offset_days"] or 14)
        v["owner_role"] = v["owner_role"] or None
        cur.update(v)       # the rule key is kept when the task is renamed
        self._render(n)

    def _remove(self) -> None:
        n = self._selected()
        if n is None:
            return
        if messagebox.askyesno("Remove task", f"Remove "
                               f"'{self.items[n].get('task')}' from the "
                               "template? Checklists already made keep it.",
                               parent=self.win):
            del self.items[n]
            self._render()

    def _move(self, step: int) -> None:
        n = self._selected()
        if n is None:
            return
        m = n + step
        if 0 <= m < len(self.items):
            self.items[n], self.items[m] = self.items[m], self.items[n]
            self._render(m)

    def _save(self) -> None:
        note = self.note_e.get().strip()
        if self.existing and len(note) < 3:
            messagebox.showwarning("Save template", "Say what changed in "
                                   "the note (at least 3 characters).",
                                   parent=self.win)
            return
        try:
            t = tpl.save_template(
                self.name_e.get().strip(), items=self.items,
                learner_type=self.type_cb.get() or None,
                kind=self.kind_cb.get() or "base",
                description=self.desc_e.get().strip() or None,
                note=note or None)
        except Exception as e:  # noqa: BLE001 — ValidationError / AccessDenied
            messagebox.showerror("Save template", str(e), parent=self.win)
            return
        messagebox.showinfo("Save template", f"{t.name} saved as version "
                            f"{t.version}.", parent=self.win)
        self.win.destroy()
        self.on_save()
