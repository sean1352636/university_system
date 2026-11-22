"""Search tab — results grid / preview / rendering methods (mixin).

Moved verbatim from ``advanced_search_views.SearchTab``.
"""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog
from education_system.systems.sixth_form.domain.learners.advanced_search import (
    actions as search_actions,
    exports as search_exports,
    matching as search_matching,
    query as search_query,
    sources as search_sources,
)
from education_system.systems.sixth_form.domain.learners.advanced_search.models import (
    Hit,
    QUERY_SYNTAX_HELP,
    SCOPE_LABELS,
    SearchResults,
)
from ._widgets import (
    _ROW_TAG_COLOURS,
    _DENSITY_ROWHEIGHT,
    _load_ui_store,
    _save_ui_store,
    _load_ann_store,
    _ann_key,
    _get_annotation,
    _phonetic_match,
    _sparkline,
    _SHORTCUT_HELP,
)


class _ResultsMixin:

    def _rerender(self) -> None:
        """(Re)draw the tree honouring flat/grouped (11), pagination (15),
        conditional colour (14) and column layout (12/17)."""
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._hit_by_item: dict[str, Hit] = {}
        results = self._last_results
        if results is None:
            self.page_var.set("")
            return
        mode = self.group_by.get()
        if "Year" in mode or "Tutor" in mode:
            try:
                self._group_index = search_sources.student_group_index()
            except Exception:
                self._group_index = {}
        colour = bool(self.colour_var.get())
        heatmap = bool(getattr(self, "heatmap_var", None)
                       and self.heatmap_var.get())
        diff_on = bool(getattr(self, "diff_var", None)
                       and self.diff_var.get())
        new_keys = getattr(self, "_new_keys", set()) if diff_on else set()
        self._ann_cache = _load_ann_store() if colour else {}
        # Heatmap (feature 13) needs the score range across the result set.
        self._heat_lo = self._heat_hi = 0.0
        if heatmap and results.total:
            scores = [h.score for h in results.all_hits()]
            self._heat_lo, self._heat_hi = min(scores), max(scores)

        # Flatten in scope order, then paginate the flat list (15) so the
        # page window is stable across flat/grouped modes.
        ordered = [(s, h) for s in results.scopes
                   for h in results.hits_by_scope.get(s, [])]
        total = len(ordered)
        page_size = self._page_size()
        if page_size:
            pages = max(1, (total + page_size - 1) // page_size)
            self._page = max(0, min(self._page, pages - 1))
            start = self._page * page_size
            page_slice = ordered[start:start + page_size]
            self.page_var.set(f"Page {self._page + 1}/{pages}")
        else:
            page_slice = ordered
            self.page_var.set(f"All {total}")

        def _child_tags(scope: str, h: Hit) -> tuple[str, ...]:
            tags: list[str] = []
            # Diff-since-last-run (feature 4) wins the row highlight.
            if diff_on and f"{scope}#{h.entity_id}" in new_keys:
                tags.append("row-new")
            elif heatmap:
                span = (self._heat_hi - self._heat_lo) or 1.0
                bucket = int((h.score - self._heat_lo) / span * 4)
                tags.append(f"heat{max(0, min(4, bucket))}")
            elif colour:
                tag = self._row_colour_tag(scope, h)
                if tag:
                    tags.append(tag)
            return tuple(tags)

        if self.flat_var.get():
            self.tree.configure(show="headings")
            for scope, h in page_slice:
                item_id = self.tree.insert(
                    "", "end",
                    values=(h.entity_id, h.label, h.sublabel, h.matched_field),
                    tags=_child_tags(scope, h))
                self._hit_by_item[item_id] = h
        else:
            self.tree.configure(show="tree headings")
            groups: dict[str, list[tuple[str, Hit]]] = {}
            order: list[str] = []
            for scope, h in page_slice:
                key = self._group_key(scope, h)
                if key not in groups:
                    groups[key] = []
                    order.append(key)
                groups[key].append((scope, h))
            for key in order:
                pairs = groups[key]
                node = self.tree.insert(
                    "", "end", text=f"{key}  ({len(pairs)})",
                    values=("", "", "", ""), open=True, tags=("scope",))
                for scope, h in pairs:
                    item_id = self.tree.insert(
                        node, "end", text="",
                        values=(h.entity_id, h.label, h.sublabel,
                                h.matched_field),
                        tags=_child_tags(scope, h))
                    self._hit_by_item[item_id] = h
        self._apply_columns()
        per = {s: len(results.hits_by_scope.get(s, [])) for s in results.scopes}
        chips = [f"{SCOPE_LABELS.get(s, s)} {n}" for s, n in per.items() if n]
        self.stats_var.set("   ·   ".join(chips[:8])
                           + (f"      Σ {results.total}" if results.total
                              else ""))
        layout = ("flat" if self.flat_var.get()
                  else f"grouped by {mode.lower()}")
        more = ""
        if getattr(results, "truncated", False):
            more = (f" (of {results.matched_total} matching — raise the "
                    f"per-area limit to see the rest)")
        self.status_var.set(
            f"{results.total} hit(s){more} for "
            f"{(results.query or '(empty)')!r}  ·  {layout}")

    def _page_size(self) -> int | None:
        v = self.page_size_var.get()
        if v == "All":
            return None
        try:
            return max(1, int(v))
        except ValueError:
            return None

    def _row_colour_tag(self, scope: str, h: Hit) -> str:
        """Pick a row-colour tag from the hit's status/risk level, or an
        'at-risk'/'flag'/'safeguarding' annotation tag."""
        ann = self._ann_cache.get(_ann_key(scope, h.entity_id), {})
        flags = {t.lower() for t in ann.get("tags", [])}
        if flags & {"at-risk", "flag", "flagged", "safeguarding"}:
            return "row-flagged"
        doc = (h.extra or {}).get("_doc") or {}
        status = str(doc.get("status") or "").strip().lower()
        level = str(doc.get("level") or "").strip().lower()
        if status == "active":
            return "row-active"
        if status == "inactive":
            return "row-inactive"
        if status == "suspended":
            return "row-suspended"
        if status in ("left", "withdrawn"):
            return "row-left"
        if level in ("high", "critical", "red"):
            return "row-flagged"
        if level in ("medium", "amber"):
            return "row-suspended"
        if level in ("low", "green"):
            return "row-active"
        return ""

    # ── Pagination / density / expand controls (15, 13, 16) ───────────

    def _on_page_size(self) -> None:
        self._page = 0
        self._rerender()

    def _prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._rerender()

    def _next_page(self) -> None:
        self._page += 1        # _rerender clamps to the last page
        self._rerender()

    def _apply_density(self) -> None:
        h = _DENSITY_ROWHEIGHT.get(self.density_var.get(), 22)
        self._tree_style.configure("AdvSearch.Treeview", rowheight=h)

    def _expand_all(self) -> None:
        for n in self.tree.get_children():
            self.tree.item(n, open=True)

    def _collapse_all(self) -> None:
        for n in self.tree.get_children():
            self.tree.item(n, open=False)

    def _hit_student_id(self, scope: str, h: Hit) -> str:
        if scope == "students":
            return h.entity_id
        if scope in search_matching._STUDENT_KEYED_SCOPES:
            doc = (h.extra or {}).get("_doc") or {}
            return search_query._doc_student_id(scope, doc)
        return ""

    def _group_key(self, scope: str, h: Hit) -> str:
        mode = self.group_by.get()
        # Composite group-by (feature 8): primary + risk band.
        if "+" in mode:
            primary, _plus, secondary = mode.partition("+")
            outer = self._group_key_single(primary, scope, h)
            inner = self._group_key_single(secondary, scope, h)
            return f"{outer}  ·  {inner}"
        return self._group_key_single(mode, scope, h)

    def _group_key_single(self, mode: str, scope: str, h: Hit) -> str:
        if mode == "Scope":
            return SCOPE_LABELS.get(scope, scope)
        if mode == "Risk":
            doc = (h.extra or {}).get("_doc") or {}
            return f"Risk: {doc.get('level') or '—'}"
        sid = self._hit_student_id(scope, h)
        if not sid:
            return "(non-student)"
        yr, tg = self._group_index.get(sid, (None, None))
        if mode == "Year":
            return f"Year {yr}" if yr is not None else "Year —"
        return f"Tutor {tg}" if tg else "Tutor —"

    # ── Column chooser + sortable columns (item 18) ───────────────

    def _apply_columns(self) -> None:
        # Pinned columns (17) are forced to the front and always shown;
        # remaining visible columns follow the chosen order (12).
        pinned = [c for c in self._col_order if c in self._pinned_cols]
        rest = [c for c in self._col_order
                if c not in self._pinned_cols and self._col_vars[c].get()]
        self._display_cols = (pinned + rest) or list(self._cols)
        self.tree.configure(displaycolumns=self._display_cols)

    def _sort_by(self, col: str) -> None:
        asc = True
        if self._sort_state and self._sort_state[0] == col:
            asc = not self._sort_state[1]
        self._sort_state = (col, asc)
        for node in self.tree.get_children():
            kids = list(self.tree.get_children(node))
            kids.sort(key=lambda k: (self.tree.set(k, col) or "").lower(),
                      reverse=not asc)
            for pos, k in enumerate(kids):
                self.tree.move(k, node, pos)
        for c in self._cols:
            arrow = (" ▲" if asc else " ▼") if c == col else ""
            self.tree.heading(c, text=self._col_titles[c] + arrow)

    # ── Preview pane (item 19) ────────────────────────────────────

    def _on_select(self, _event=None) -> None:
        hits = self._selected_hits()
        if not hits:
            return
        h = hits[0]
        safe = bool(getattr(self, "safe_var", None) and self.safe_var.get())
        doc = (h.extra or {}).get("_doc") or {}
        lines = [f"[{h.scope}]  {h.entity_id}", h.label, ""]
        if h.sublabel:
            lines += [self._mask(h.sublabel) if safe else h.sublabel, ""]
        for k, v in doc.items():
            if k.startswith("_") or v in (None, ""):
                continue
            # Numeric series → inline trend sparkline (feature 10).
            if isinstance(v, (list, tuple)) and any(
                    isinstance(x, (int, float)) for x in v):
                spark = _sparkline(list(v))
                if spark:
                    lines.append(f"{k:>14}: {spark}  "
                                 f"({v[0]}→{v[-1]})")
                    continue
            if safe and self._is_sensitive_field(k):
                lines.append(f"{k:>14}: {self._mask(str(v))}")
            else:
                lines.append(f"{k:>14}: {v}")
        if h.matched_fields:
            lines += ["", "matched: " + ", ".join(h.matched_fields)]
        lines += self._annotation_lines(h.scope, h.entity_id)
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", "\n".join(str(x) for x in lines))
        self.preview.configure(state="disabled")

    def _annotation_lines(self, scope: str, entity_id: str) -> list[str]:
        """Render tag/owner/note/merge annotations (21, 22, 24, 25) for
        the preview pane. Empty list when the record has none."""
        ann = _get_annotation(scope, entity_id)
        if not ann:
            return []
        out = ["", "── annotations ──"]
        if ann.get("tags"):
            out.append("tags: " + ", ".join(ann["tags"]))
        for flag in ann.get("flags", []):                 # feature 14
            out.append(f"⚑ flag [{flag.get('code', '?')}]: "
                       f"{flag.get('reason', '')}")
        if ann.get("owner"):
            out.append(f"owner: {ann['owner']}")
        wf = ann.get("workflow")                          # feature 18
        if wf:
            out.append(f"→ workflow: {wf.get('owner', '?')} "
                       f"(due {wf.get('due', '—')}) [{wf.get('state', 'open')}]")
        if ann.get("merged_into"):
            out.append(f"⚠ merged into: {ann['merged_into']}")
        for note in ann.get("notes", []):
            out.append(f"note ({note.get('ts', '')}): {note.get('text', '')}")
        return out

    # ══ Column reorder / pin (features 12, 17) ════════════════════════

    def _show_column_menu(self, event) -> None:
        region = self.tree.identify_region(event.x, event.y)
        if region not in ("heading", "separator"):
            return
        colid = self.tree.identify_column(event.x)      # '#0' or '#n'
        if not colid or colid == "#0":
            return
        try:
            disp_idx = int(colid[1:]) - 1
        except ValueError:
            return
        display = self._display_cols
        if not (0 <= disp_idx < len(display)):
            return
        col = display[disp_idx]
        menu = tk.Menu(self.tree, tearoff=False)
        menu.add_command(label=f"Column: {self._col_titles.get(col, col)}",
                         state="disabled")
        menu.add_separator()
        menu.add_command(label="Move ◀ left",
                         command=lambda c=col: self._move_column(c, -1))
        menu.add_command(label="Move ▶ right",
                         command=lambda c=col: self._move_column(c, +1))
        if col in self._pinned_cols:
            menu.add_command(label="Unpin",
                             command=lambda c=col: self._toggle_pin(c))
        else:
            menu.add_command(label="Pin to front",
                             command=lambda c=col: self._toggle_pin(c))
        menu.add_command(label="Hide",
                         command=lambda c=col: self._hide_column(c))
        menu.tk_popup(event.x_root, event.y_root)

    def _move_column(self, col: str, delta: int) -> None:
        order = self._col_order
        if col not in order:
            return
        i = order.index(col)
        j = i + delta
        if 0 <= j < len(order):
            order[i], order[j] = order[j], order[i]
            self._apply_columns()

    def _toggle_pin(self, col: str) -> None:
        if col in self._pinned_cols:
            self._pinned_cols.discard(col)
        else:
            self._pinned_cols.add(col)
            self._col_vars[col].set(True)       # pinned ⇒ visible
        self._apply_columns()

    def _hide_column(self, col: str) -> None:
        if col in self._pinned_cols:
            self.status_var.set("Unpin the column before hiding it.")
            return
        visible = [c for c in self._cols if self._col_vars[c].get()]
        if len(visible) <= 1:
            self.status_var.set("At least one column must stay visible.")
            return
        self._col_vars[col].set(False)
        self._apply_columns()

    # ══ Inline edit (feature 18) ══════════════════════════════════════

    @staticmethod
    def _students_api():
        from education_system.systems.sixth_form.domain.learners.\
            students.students import get_student
        return get_student, search_actions.statuses()

    @staticmethod
    def _may_manage_students() -> bool:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().can(access.STUDENTS_MANAGE)

    def _inline_edit(self, _event=None) -> None:
        students = [h for h in self._selected_hits() if h.scope == "students"]
        if not students:
            self.status_var.set("Inline edit (F2): select a student row.")
            return
        if not self._may_manage_students():
            messagebox.showinfo("Inline edit",
                                "Editing students needs the manage-students "
                                "permission.")
            return
        get_student, statuses = self._students_api()
        h = students[0]
        try:
            stu = get_student(h.entity_id)
        except Exception:  # noqa: BLE001
            stu = None
        if stu is None:
            self.status_var.set(f"No student record for {h.entity_id}.")
            return
        top = tk.Toplevel(self.frame.winfo_toplevel())
        top.transient(self.frame.winfo_toplevel())
        top.title(f"Edit {stu.student_id}")
        try:
            top.wm_geometry(
                f"+{self.tree.winfo_pointerx()}+{self.tree.winfo_pointery()}")
        except tk.TclError:
            pass
        entries: dict[str, ttk.Entry] = {}
        row = 0
        for attr, label in search_actions.INLINE_FIELDS:
            ttk.Label(top, text=label + ":").grid(row=row, column=0,
                                                  sticky="e", padx=4, pady=2)
            e = ttk.Entry(top, width=26)
            e.insert(0, getattr(stu, attr) or "")
            e.grid(row=row, column=1, padx=4, pady=2)
            entries[attr] = e
            row += 1
        ttk.Label(top, text="Status:").grid(row=row, column=0, sticky="e",
                                            padx=4, pady=2)
        status_var = tk.StringVar(value=stu.status)
        ttk.Combobox(top, textvariable=status_var, values=list(statuses),
                     state="readonly", width=24).grid(row=row, column=1,
                                                       padx=4, pady=2)
        row += 1
        ttk.Label(top, text="Reason (status change):").grid(
            row=row, column=0, sticky="e", padx=4, pady=2)
        reason_e = ttk.Entry(top, width=26)
        reason_e.grid(row=row, column=1, padx=4, pady=2)
        row += 1

        def _save() -> None:
            changes = {attr: e.get().strip() for attr, e in entries.items()}
            try:
                search_actions.inline_update(
                    stu.student_id, changes, status=status_var.get(),
                    reason=reason_e.get().strip() or None)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Update failed", str(exc))
                return
            top.destroy()
            self.run()
            self.status_var.set(f"Updated {stu.student_id}.")

        btns = ttk.Frame(top)
        btns.grid(row=row, column=0, columnspan=2, pady=6)
        ttk.Button(btns, text="Save", command=_save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel",
                   command=top.destroy).pack(side="left", padx=4)
        top.grab_set()

    # ══ Quick-look hover popover (feature 19) ═════════════════════════

    def _on_tree_motion(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if row == self._ql_row:
            return
        self._ql_row = row
        self._hide_quicklook()
        if row and row in self._hit_by_item:
            self._ql_after = self.tree.after(
                500, lambda: self._show_quicklook(row))

    def _show_quicklook(self, row: str) -> None:
        h = self._hit_by_item.get(row)
        if h is None:
            return
        try:
            x = self.tree.winfo_pointerx() + 16
            y = self.tree.winfo_pointery() + 12
        except tk.TclError:
            return
        self._hide_quicklook()
        win = tk.Toplevel(self.tree)
        win.wm_overrideredirect(True)
        win.wm_geometry(f"+{x}+{y}")
        lines = [h.label]
        if h.sublabel:
            lines.append(h.sublabel)
        ann = _get_annotation(h.scope, h.entity_id)
        if ann.get("tags"):
            lines.append("tags: " + ", ".join(ann["tags"]))
        if ann.get("owner"):
            lines.append("owner: " + str(ann["owner"]))
        tk.Label(win, text="\n".join(lines), justify="left",
                 background="#ffffe0", relief="solid", borderwidth=1,
                 font=("", 9), padx=6, pady=4, wraplength=320).pack()
        self._ql_win = win

    def _hide_quicklook(self) -> None:
        if self._ql_after is not None:
            try:
                self.tree.after_cancel(self._ql_after)
            except Exception:  # noqa: BLE001
                pass
            self._ql_after = None
        if self._ql_win is not None:
            try:
                self._ql_win.destroy()
            except Exception:  # noqa: BLE001
                pass
            self._ql_win = None

    # ══ Jump to scope (feature 20) ════════════════════════════════════

    def _ordered_hit_items(self) -> list[str]:
        out: list[str] = []
        for node in self.tree.get_children():
            if node in self._hit_by_item:
                out.append(node)                 # flat-mode row
            for child in self.tree.get_children(node):
                out.append(child)                # grouped child row
        return out

    def _jump_next_scope(self, _event=None):
        self._jump_scope(+1)
        return "break"

    def _jump_prev_scope(self, _event=None):
        self._jump_scope(-1)
        return "break"

    def _jump_scope(self, direction: int) -> None:
        first_of: dict[str, str] = {}
        scope_order: list[str] = []
        for iid in self._ordered_hit_items():
            h = self._hit_by_item.get(iid)
            if h is None or h.scope in first_of:
                continue
            first_of[h.scope] = iid
            scope_order.append(h.scope)
        if not scope_order:
            return
        sel = self.tree.selection()
        cur = (self._hit_by_item[sel[0]].scope
               if sel and sel[0] in self._hit_by_item else None)
        if cur in scope_order:
            idx = (scope_order.index(cur) + direction) % len(scope_order)
        else:
            idx = 0 if direction > 0 else len(scope_order) - 1
        target = first_of[scope_order[idx]]
        self.tree.see(target)
        self.tree.selection_set(target)
        self.tree.focus(target)
        self.status_var.set(
            f"Jumped to scope: "
            f"{SCOPE_LABELS.get(scope_order[idx], scope_order[idx])}")

    # ── Keyboard type-ahead jump (item 24) ────────────────────────

    def _type_ahead(self, event) -> None:
        ch = event.char
        if not ch or len(ch) != 1 or not ch.isprintable():
            return
        self._typeahead_buf = (self._typeahead_buf + ch).lower()
        after = getattr(self, "_ta_after", None)
        if after is not None:
            try:
                self.frame.after_cancel(after)
            except Exception:
                pass
        self._ta_after = self.frame.after(800, self._reset_typeahead)
        for node in self.tree.get_children():
            for k in self.tree.get_children(node):
                lbl = (self.tree.set(k, "label") or "").lower()
                if lbl.startswith(self._typeahead_buf):
                    self.tree.see(k)
                    self.tree.selection_set(k)
                    self.tree.focus(k)
                    return

    def _reset_typeahead(self) -> None:
        self._typeahead_buf = ""

    def _show_suggestion(self, suggestion: str) -> None:
        for w in self.sugg_frame.winfo_children():
            w.destroy()
        if not suggestion:
            return
        ttk.Label(self.sugg_frame,
                   text="Did you mean:").pack(side="left")

        def _apply() -> None:
            self.query_e.delete(0, "end")
            self.query_e.insert(0, suggestion)
            self.run()

        ttk.Button(self.sugg_frame, text=suggestion,
                    command=_apply).pack(side="left", padx=(4, 0))

    def _show_syntax(self) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.transient(self.frame.winfo_toplevel())
        win.title("Advanced Search — query syntax")
        win.geometry("760x520")
        txt = tk.Text(win, wrap="none", font=("TkFixedFont", 10))
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", QUERY_SYNTAX_HELP)
        txt.configure(state="disabled")
        ttk.Button(win, text="Close",
                    command=win.destroy).pack(pady=(0, 8))

    # ── Bulk-action handlers (item 45) ────────────────────────────

    def _selected_hits(self) -> list[Hit]:
        return [self._hit_by_item[i]
                for i in self.tree.selection()
                if i in getattr(self, "_hit_by_item", {})]

    def _open_selected(self) -> None:
        hits = self._selected_hits()
        if not hits:
            self.status_var.set("Nothing selected.")
            return
        opened = 0
        for h in hits:
            self._push_recent(h)
            if search_exports.open_hit(h) is not None:
                opened += 1
        self.status_var.set(f"Opened {opened} of {len(hits)} record(s).")

    # ── Keyboard helpers (item 44) ────────────────────────────────

    def _focus_query(self, _event=None) -> str | None:
        # "/" typed into another box (a date, a tutor group) is just text.
        widget = getattr(_event, "widget", None)
        if (getattr(_event, "keysym", "") == "slash"
                and isinstance(widget, (tk.Entry, ttk.Entry, tk.Text))
                and widget is not self.query_e):
            return None
        if getattr(_event, "keysym", "") != "Escape":
            show = getattr(self, "_show_search", None)
            if show is not None:
                show()
        try:
            self.query_e.focus_set()
            self.query_e.select_range(0, "end")
        except Exception:
            pass
        return "break"

    def _focus_first_hit(self) -> None:
        for parent in self.tree.get_children():
            kids = self.tree.get_children(parent)
            if kids:
                self.tree.selection_set(kids[0])
                self.tree.focus(kids[0])
                return

    # ══════════════════════════════════════════════════════════════════
    # New feature batch (features 1–25 of this request)
    # ══════════════════════════════════════════════════════════════════

    # ── Safe-mode masking helpers (feature 24) ────────────────────────

    _SENSITIVE_HINTS: tuple[str, ...] = (
        "dob", "birth", "email", "phone", "mobile", "address",
        "postcode", "nhs", "medical", "ni_number", "guardian",
    )

    def _is_sensitive_field(self, key: str) -> bool:
        k = key.lower()
        return any(h in k for h in self._SENSITIVE_HINTS)

    @staticmethod
    def _mask(text: str) -> str:
        """Redact all but the first character of each word so a value is
        recognisable-as-present without disclosing it."""
        return re.sub(r"(?<=\w)\w", "•", text or "")

    def _toggle_safe(self) -> None:
        state = "ON" if self.safe_var.get() else "OFF"
        self.status_var.set(f"Safe mode {state} — sensitive preview fields "
                            f"are {'masked' if self.safe_var.get() else 'shown'}.")
        self._on_select()

    # ── Feature 2: phonetic / fuzzy filter ────────────────────────────

    def _filter_results_phonetic(self, results: SearchResults,
                                 q: str) -> SearchResults:
        keep = [h for h in results.all_hits()
                if _phonetic_match(q, f"{h.label} {h.sublabel}")]
        out = self._results_from_hits(keep, results.query)
        out.suggestions = results.suggestions
        self.status_var.set(
            f"Phonetic filter: {len(keep)}/{results.total} kept for {q!r}.")
        return out

    def _toggle_phonetic(self) -> None:
        if self.phonetic_var.get() and self.query_e.get().strip():
            self.run()

    # ── Feature 4: diff-since-last-run toggle ─────────────────────────

    def _toggle_diff(self) -> None:
        on = self.diff_var.get()
        self.status_var.set(
            "Diff highlight ON — new rows vs the previous run of this query "
            "are highlighted." if on else "Diff highlight OFF.")
        self._rerender()

    # ── Feature 9: pivot / crosstab ───────────────────────────────────

    def _pivot_view(self) -> None:
        if self._last_results is None or self._last_results.total == 0:
            self.status_var.set("Run a search first.")
            return
        statuses: list[str] = []
        matrix: dict[str, dict[str, int]] = {}
        for h in self._last_results.all_hits():
            doc = (h.extra or {}).get("_doc") or {}
            st = str(doc.get("status") or doc.get("level") or "—").strip() or "—"
            if st not in statuses:
                statuses.append(st)
            row = matrix.setdefault(SCOPE_LABELS.get(h.scope, h.scope), {})
            row[st] = row.get(st, 0) + 1
        statuses = statuses[:8]
        header = f"{'scope':<22}" + "".join(f"{s[:10]:>11}" for s in statuses)
        header += f"{'Σ':>8}"
        lines = [header, "─" * len(header)]
        for scope, row in matrix.items():
            cells = "".join(f"{row.get(s, 0):>11}" for s in statuses)
            lines.append(f"{scope:<22}{cells}{sum(row.values()):>8}")
        self._show_text_popup("Pivot — scope × status", "\n".join(lines))

    # ── Feature 11: saved column layouts ──────────────────────────────

    def _rebuild_layout_menu(self) -> None:
        m = self._layout_menu
        m.delete(0, "end")
        m.add_command(label="Save current layout…",
                      command=self._save_layout)
        store = _load_ui_store()
        names = sorted(store.get("layouts", {}))
        if names:
            m.add_separator()
            for name in names:
                sub = tk.Menu(m, tearoff=False)
                sub.add_command(label="Apply",
                                command=lambda n=name: self._apply_layout(n))
                sub.add_command(label="Delete",
                                command=lambda n=name: self._delete_layout(n))
                m.add_cascade(label=name, menu=sub)

    def _save_layout(self) -> None:
        name = simpledialog.askstring("Save layout", "Layout name:",
                                      parent=self.frame)
        if not name or not name.strip():
            return
        store = _load_ui_store()
        store.setdefault("layouts", {})[name.strip()] = {
            "order": list(self._col_order),
            "pinned": sorted(self._pinned_cols),
            "hidden": [c for c in self._cols if not self._col_vars[c].get()],
        }
        _save_ui_store(store)
        self.status_var.set(f"Saved layout {name.strip()!r}.")

    def _apply_layout(self, name: str) -> None:
        layout = _load_ui_store().get("layouts", {}).get(name)
        if not layout:
            return
        self._col_order = [c for c in layout.get("order", self._cols)
                           if c in self._cols]
        for c in self._cols:
            if c not in self._col_order:
                self._col_order.append(c)
        self._pinned_cols = {c for c in layout.get("pinned", [])
                             if c in self._cols}
        hidden = set(layout.get("hidden", []))
        for c in self._cols:
            self._col_vars[c].set(c not in hidden)
        self._apply_columns()
        self.status_var.set(f"Applied layout {name!r}.")

    def _delete_layout(self, name: str) -> None:
        store = _load_ui_store()
        if store.get("layouts", {}).pop(name, None) is not None:
            _save_ui_store(store)
            self.status_var.set(f"Deleted layout {name!r}.")

    # ── Feature 12: compare result sets A / B ─────────────────────────

    def _snapshot_slot(self, slot: str) -> None:
        if self._last_results is None:
            self.status_var.set("Run a search first.")
            return
        self._cmp_slots[slot] = {
            "query": self._last_results.query,
            "keys": {f"{h.scope}#{h.entity_id}": h.label
                     for h in self._last_results.all_hits()},
        }
        self.status_var.set(
            f"Captured slot {slot} ({len(self._cmp_slots[slot]['keys'])} hits) "
            f"for {self._last_results.query!r}.")

    def _compare_slots(self) -> None:
        if "A" not in self._cmp_slots or "B" not in self._cmp_slots:
            messagebox.showinfo(
                "Compare",
                "Capture slot A and slot B first (from the Compare menu).")
            return
        a, b = self._cmp_slots["A"], self._cmp_slots["B"]
        ka, kb = set(a["keys"]), set(b["keys"])
        only_a = sorted(ka - kb)
        only_b = sorted(kb - ka)
        both = ka & kb
        lines = [f"A: {a['query']!r}  ({len(ka)} hits)",
                 f"B: {b['query']!r}  ({len(kb)} hits)",
                 f"In both: {len(both)}", "",
                 f"── Only in A ({len(only_a)}) ──"]
        lines += [f"  {a['keys'][k]}  [{k}]" for k in only_a[:60]]
        lines += ["", f"── Only in B ({len(only_b)}) ──"]
        lines += [f"  {b['keys'][k]}  [{k}]" for k in only_b[:60]]
        self._show_text_popup("Compare A vs B", "\n".join(lines))

    # ── Feature 13: heatmap toggle ────────────────────────────────────

    def _toggle_heatmap(self) -> None:
        if self.heatmap_var.get():
            self.colour_var.set(False)
        self._rerender()

    # ── Feature 20: keyboard shortcut cheatsheet ──────────────────────

    def _show_shortcuts(self, _event=None) -> str:
        lines = [f"{keys:<22} {desc}" for keys, desc in _SHORTCUT_HELP]
        self._show_text_popup("Keyboard shortcuts", "\n".join(lines))
        return "break"

    # ── Feature 21: dark / high-contrast theme ────────────────────────

    def _toggle_theme(self) -> None:
        self._apply_theme(self.dark_var.get())

    def _apply_theme(self, dark: bool) -> None:
        if dark:
            bg, fg, sel = "#1e1e1e", "#e6e6e6", "#375a7f"
            self._tree_style.configure(
                "AdvSearch.Treeview", background=bg, fieldbackground=bg,
                foreground=fg)
            self._tree_style.map("AdvSearch.Treeview",
                                 background=[("selected", sel)])
            self.tree.tag_configure("scope", background="#2d3a4a",
                                    foreground="#cfe4ff")
            for tag in _ROW_TAG_COLOURS:
                self.tree.tag_configure(tag, background="#332b1a")
            try:
                self.preview.configure(bg=bg, fg=fg, insertbackground=fg)
            except tk.TclError:
                pass
            self.status_var.set("High-contrast dark theme ON.")
        else:
            self._tree_style.configure(
                "AdvSearch.Treeview", background="white",
                fieldbackground="white", foreground="black")
            self.tree.tag_configure("scope", background="#eef7ff",
                                    foreground="black")
            for tag, colour in _ROW_TAG_COLOURS.items():
                self.tree.tag_configure(tag, background=colour)
            try:
                self.preview.configure(bg="white", fg="black",
                                       insertbackground="black")
            except tk.TclError:
                pass
            self.status_var.set("Light theme.")
        self._rerender()
