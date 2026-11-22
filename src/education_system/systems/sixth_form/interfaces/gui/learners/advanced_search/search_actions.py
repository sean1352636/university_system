"""Search tab — export, bulk actions, pins, saving and misc actions (mixin).

Moved verbatim from ``advanced_search_views.SearchTab``.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog
from typing import Callable
from education_system.systems.sixth_form.domain.learners.advanced_search import (
    actions as search_actions,
    engine as search_engine,
    exports as search_exports,
    history as search_history,
)
from education_system.systems.sixth_form.domain.learners.advanced_search.models import (
    Hit,
    SCOPE_LABELS,
    ValidationError,
)
from ._widgets import (
    _load_ui_store,
    _save_ui_store,
    _load_ann_store,
    _save_ann_store,
    _ann_key,
    _append_action_log,
    _read_action_log,
    _choose_from,
)


class _ActionsMixin:

    # ── Export / message / contact sheet (items 36, 37, 39) ───────

    def _export_results_dialog(self) -> None:
        if self._last_results is None or self._last_results.total == 0:
            self.status_var.set("Run a search first.")
            return
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Excel", "*.xlsx"),
                       ("PDF", "*.pdf"), ("HTML", "*.html"),
                       ("JSON", "*.json"), ("Markdown", "*.md"),
                       ("TSV", "*.tsv")],
            initialfile="advanced_search_results.csv")
        if not path:
            return
        columns = list(search_exports.EXPORT_COLUMNS)
        if messagebox.askyesno(
                "Export", "Include student details (name, status, year, "
                          "tutor group, UPN, DOB, postcode…) for each row?"):
            columns += list(search_exports.STUDENT_EXPORT_COLUMNS)
        try:
            # export_results_file records the export in the audit and
            # the operator action log.
            search_exports.export_results_file(self._last_results, path,
                                               columns=columns)
            self.status_var.set(f"Exported to {path}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def _mailmerge_dialog(self) -> None:
        if self._last_results is None:
            self.status_var.set("Run a search first.")
            return
        from education_system.platform.delivery.gui.parented_dialogs import simpledialog
        subject = simpledialog.askstring("Message students", "Subject:")
        if not subject:
            return
        body = simpledialog.askstring("Message students", "Body:") or ""
        # Feature 15: offer to actually dispatch, not just draft.
        send = messagebox.askyesno(
            "Send now?",
            "Send these messages now?\n\n"
            "Yes = dispatch via the email service.\n"
            "No  = save as drafts only.")
        try:
            res = search_exports.mailmerge_results(
                self._last_results, subject=subject, body=body, send=send)
        except Exception as e:
            messagebox.showerror("Message failed", str(e))
            return
        verb = "Sent" if send else "Drafted"
        messagebox.showinfo(
            "Message",
            f"{verb} {res['created']} message(s) to "
            f"{res['recipients']} student(s) (thread {res['thread_id']}).")

    def _contact_sheet(self) -> None:
        if self._last_results is None or self._last_results.total == 0:
            self.status_var.set("Run a search first.")
            return
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".html", filetypes=[("HTML", "*.html")],
            initialfile="contact_sheet.html")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(search_exports.contact_sheet(self._last_results))
            self.status_var.set(f"Contact sheet → {path}")
        except Exception as e:
            messagebox.showerror("Contact sheet failed", str(e))

    # ══ Bulk actions (features 21–25) ═════════════════════════════════

    def _bulk_tag(self) -> None:
        hits = self._selected_hits()
        if not hits:
            self.status_var.set("Select rows to tag.")
            return
        raw = simpledialog.askstring(
            "Bulk tag",
            "Tags to add (comma-separated; prefix with '-' to remove):",
            parent=self.frame)
        if not raw:
            return
        parts = [t.strip() for t in raw.split(",") if t.strip()]
        add = [t for t in parts if not t.startswith("-")]
        remove = {t[1:] for t in parts if t.startswith("-")}
        keys = {(h.scope, h.entity_id) for h in hits}
        self._snapshot_ann("bulk tag")
        store = _load_ann_store()
        for h in hits:
            ann = store.setdefault(_ann_key(h.scope, h.entity_id), {})
            tags = ann.get("tags", [])
            for t in add:
                if t not in tags:
                    tags.append(t)
            ann["tags"] = [t for t in tags if t not in remove]
        _save_ann_store(store)
        self._rerender()             # repaint colours (14) for new tags
        self._reselect(keys)         # rerender regenerates item ids
        self._on_select()
        self.status_var.set(f"Updated tags on {len(hits)} record(s).")

    def _reselect(self, keys: set) -> None:
        """Re-select the rows for the given (scope, entity_id) keys after a
        rerender has regenerated the tree item ids."""
        want = [iid for iid, h in self._hit_by_item.items()
                if (h.scope, h.entity_id) in keys]
        if want:
            self.tree.selection_set(want)
            self.tree.see(want[0])

    def _bulk_assign_staff(self) -> None:
        hits = self._selected_hits()
        if not hits:
            self.status_var.set("Select rows to assign an owner.")
            return
        owner = simpledialog.askstring(
            "Assign owner",
            "Owning staff (name or id; leave blank to clear):",
            parent=self.frame)
        if owner is None:
            return
        owner = owner.strip()
        self._snapshot_ann("bulk assign owner")
        store = _load_ann_store()
        for h in hits:
            ann = store.setdefault(_ann_key(h.scope, h.entity_id), {})
            if owner:
                ann["owner"] = owner
            else:
                ann.pop("owner", None)
        _save_ann_store(store)
        self._on_select()
        verb = "Assigned" if owner else "Cleared"
        self.status_var.set(f"{verb} owner on {len(hits)} record(s).")

    def _bulk_add_note(self) -> None:
        hits = self._selected_hits()
        if not hits:
            self.status_var.set("Select rows to note.")
            return
        text = simpledialog.askstring("Add note", "Note text:",
                                      parent=self.frame)
        if not text or not text.strip():
            return
        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        self._snapshot_ann("bulk add note")
        store = _load_ann_store()
        for h in hits:
            ann = store.setdefault(_ann_key(h.scope, h.entity_id), {})
            ann.setdefault("notes", []).append(
                {"ts": ts, "text": text.strip()})
        _save_ann_store(store)
        self._on_select()
        self.status_var.set(f"Added note to {len(hits)} record(s).")

    def _bulk_status_change(self) -> None:
        hits = [h for h in self._selected_hits() if h.scope == "students"]
        if not hits:
            self.status_var.set("Select student rows to change status.")
            return
        if not self._may_manage_students():
            messagebox.showinfo("Change status",
                                "Changing student status needs the "
                                "manage-students permission.")
            return
        new = _choose_from("Set status",
                           f"New status for {len(hits)} student(s):",
                           list(search_actions.statuses()), self.frame)
        if not new:
            return
        reason = simpledialog.askstring(
            "Set status",
            "Reason (required for Left — they are withdrawn: enrolments "
            "closed, tutor group left, login revoked):",
            parent=self.frame)
        if reason is None:
            return
        leaving = None
        if new == "Left":
            if not reason.strip():
                messagebox.showerror("Set status",
                                     "A reason is needed to mark students "
                                     "as Left.")
                return
            leaving = simpledialog.askstring(
                "Set status", "Leaving date (YYYY-MM-DD, blank = today):",
                parent=self.frame)
            if leaving is None:
                return
        if not messagebox.askyesno(
                "Confirm bulk status change",
                f"Set status to {new!r} for {len(hits)} student(s)?"):
            return
        try:
            res = search_actions.bulk_set_status(
                [h.entity_id for h in hits], new, reason=reason.strip(),
                leaving_date=(leaving or "").strip() or None)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Change status", str(exc))
            return
        self.run()
        msg = f"Status → {new!r}: {len(res.changed)} changed"
        if res.unchanged:
            msg += f", {len(res.unchanged)} already {new}"
        if res.failed:
            msg += f", {len(res.failed)} failed"
            messagebox.showwarning(
                "Some changes failed",
                "\n".join(f"{sid}: {why}" for sid, why in res.failed.items()))
        self.status_var.set(msg + ".")

    def _merge_duplicates(self) -> None:
        hits = [h for h in self._selected_hits() if h.scope == "students"]
        if len(hits) != 2:
            self.status_var.set(
                "Select exactly 2 student rows to merge.")
            return
        if not self._may_manage_students():
            messagebox.showinfo("Merge duplicates",
                                "Linking duplicates needs the "
                                "manage-students permission.")
            return
        get_student, _statuses = self._students_api()
        a = get_student(hits[0].entity_id)
        b = get_student(hits[1].entity_id)
        if a is None or b is None:
            self.status_var.set("Could not load both student records.")
            return
        self._merge_dialog(a, b)

    def _merge_dialog(self, a, b) -> None:
        top = tk.Toplevel(self.frame.winfo_toplevel())
        top.title("Merge duplicate students")
        top.transient(self.frame.winfo_toplevel())
        ttk.Label(top, text="Choose the record to KEEP (the primary). "
                            "Empty fields on it are filled from the other, "
                            "and both records' history notes the link. The "
                            "other record's attendance, marks and other "
                            "records stay on it — withdraw it from the "
                            "Student Directory once they are dealt with.",
                  wraplength=460, justify="left").grid(
            row=0, column=0, columnspan=3, padx=8, pady=(8, 6), sticky="w")
        primary_var = tk.StringVar(value=a.student_id)
        ttk.Radiobutton(top, text=f"Keep {a.student_id} — {a.full_name}",
                        variable=primary_var, value=a.student_id).grid(
            row=1, column=1, sticky="w", padx=4)
        ttk.Radiobutton(top, text=f"Keep {b.student_id} — {b.full_name}",
                        variable=primary_var, value=b.student_id).grid(
            row=1, column=2, sticky="w", padx=4)
        ttk.Label(top, text="Field", font=("", 9, "bold")).grid(
            row=2, column=0, sticky="w", padx=6)
        ttk.Label(top, text=a.student_id, font=("", 9, "bold")).grid(
            row=2, column=1, sticky="w", padx=4)
        ttk.Label(top, text=b.student_id, font=("", 9, "bold")).grid(
            row=2, column=2, sticky="w", padx=4)
        r = 3
        for attr, label in search_actions.MERGE_FIELDS:
            va, vb = getattr(a, attr, None), getattr(b, attr, None)
            if not (va or vb):
                continue
            ttk.Label(top, text=label).grid(row=r, column=0, sticky="w",
                                            padx=6)
            ttk.Label(top, text=str(va or "—")).grid(
                row=r, column=1, sticky="w", padx=4)
            ttk.Label(top, text=str(vb or "—")).grid(
                row=r, column=2, sticky="w", padx=4)
            r += 1

        def _do_merge() -> None:
            keep = primary_var.get()
            dup = b.student_id if keep == a.student_id else a.student_id
            try:
                link = search_actions.link_duplicate(keep, dup)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Merge failed", str(exc))
                return
            top.destroy()
            self.run()
            left = ", ".join(f"{t} {n}" for t, n in
                             sorted(link.linked_records.items())[:8])
            messagebox.showinfo(
                "Duplicate linked",
                f"{dup} is now marked as a duplicate of {keep}.\n"
                f"Filled on {keep}: {', '.join(link.filled) or 'nothing'}.\n"
                + (f"Still on {dup}: {left}." if left else
                   f"{dup} has no other records."))
            self.status_var.set(f"Linked {dup} → {keep}.")

        btns = ttk.Frame(top)
        btns.grid(row=r, column=0, columnspan=3, pady=10)
        ttk.Button(btns, text="Merge", command=_do_merge).pack(
            side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=top.destroy).pack(
            side="left", padx=4)
        top.grab_set()

    # ── Recent-result breadcrumb (item 25) ────────────────────────

    def _push_recent(self, h: Hit) -> None:
        key = (h.scope, h.entity_id)
        self._recent = [x for x in self._recent
                        if (x.scope, x.entity_id) != key]
        self._recent.insert(0, h)
        self._recent = self._recent[:10]
        self.recent_combo.configure(
            values=[f"[{x.scope}] {x.label[:34]}" for x in self._recent])

    def _reopen_recent(self, _event=None) -> None:
        i = self.recent_combo.current()
        if 0 <= i < len(self._recent):
            search_exports.open_hit(self._recent[i])

    # ── Copy emails + shortlist + cohort (items 20, 23) ───────────

    def _copy_emails(self) -> None:
        emails: list[str] = []
        for h in self._selected_hits():
            doc = (h.extra or {}).get("_doc") or {}
            e = str(doc.get("email") or "").strip()
            if e and e not in emails:
                emails.append(e)
        if not emails:
            self.status_var.set("No emails in selection.")
            return
        self.frame.clipboard_clear()
        self.frame.clipboard_append("; ".join(emails))
        self.status_var.set(f"Copied {len(emails)} email(s).")

    def _add_to_shortlist(self) -> None:
        existing = {(h.scope, h.entity_id) for h in self._shortlist}
        added = 0
        for h in self._selected_hits():
            if (h.scope, h.entity_id) not in existing:
                self._shortlist.append(h)
                existing.add((h.scope, h.entity_id))
                added += 1
        self._refresh_shortlist()
        self.status_var.set(
            f"Added {added} to shortlist ({len(self._shortlist)} total).")

    def _refresh_shortlist(self) -> None:
        self.shortlist_box.delete(0, "end")
        for h in self._shortlist:
            self.shortlist_box.insert("end", f"[{h.scope}] {h.label[:40]}")

    def _open_shortlisted(self) -> None:
        sel = self.shortlist_box.curselection()
        targets = ([self._shortlist[i] for i in sel] if sel
                   else list(self._shortlist))
        for h in targets:
            self._push_recent(h)
            search_exports.open_hit(h)

    def _remove_shortlisted(self) -> None:
        for i in sorted(self.shortlist_box.curselection(), reverse=True):
            del self._shortlist[i]
        self._refresh_shortlist()

    def _clear_shortlist(self) -> None:
        self._shortlist = []
        self._refresh_shortlist()

    def _shortlist_to_cohort(self) -> None:
        if not self._shortlist:
            messagebox.showinfo("Cohort", "Shortlist is empty.")
            return
        self._cohort_from_hits(self._shortlist, "shortlist")

    def _save_cohort(self) -> None:
        if self._last_results is None or self._last_results.total == 0:
            messagebox.showinfo("Cohort", "Run a search with results first.")
            return
        from education_system.platform.delivery.gui.parented_dialogs import simpledialog
        name = simpledialog.askstring("Save cohort", "Cohort name:")
        if not name:
            return
        try:
            c = search_history.create_cohort_from_results(name.strip(),
                                                 self._last_results)
        except Exception as e:
            messagebox.showerror("Cohort failed", str(e))
            return
        messagebox.showinfo(
            "Cohort",
            f"Cohort '{c.name}' saved with {c.member_count} student(s).")

    def _cohort_from_hits(self, hits: list[Hit], default_name: str) -> None:
        from education_system.platform.delivery.gui.parented_dialogs import simpledialog
        name = simpledialog.askstring("Save cohort", "Cohort name:",
                                       initialvalue=default_name)
        if not name:
            return
        ids: list[str] = []
        for h in hits:
            sid = self._hit_student_id(h.scope, h)
            if sid and sid not in ids:
                ids.append(sid)
        if not ids:
            messagebox.showinfo("Cohort", "No students in selection.")
            return
        try:
            c = search_history.create_cohort(name.strip(), ids)
        except Exception as e:
            messagebox.showerror("Cohort failed", str(e))
            return
        messagebox.showinfo(
            "Cohort",
            f"Cohort '{c.name}' saved with {c.member_count} student(s).")

    def _copy_ids(self) -> None:
        hits = self._selected_hits()
        if not hits:
            return
        text = "\n".join(h.entity_id for h in hits)
        self.frame.clipboard_clear()
        self.frame.clipboard_append(text)
        self.status_var.set(f"Copied {len(hits)} id(s).")

    def _export_csv(self) -> None:
        if self._last_results is None:
            self.status_var.set("Run a search first.")
            return
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
            initialfile="advanced_search_results.csv")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(search_exports.export_results_csv(self._last_results))
            self.status_var.set(f"Exported to {path}")
        except OSError as e:
            messagebox.showerror("Export failed", str(e))

    def _pin_selected(self) -> None:
        hits = self._selected_hits()
        if not hits:
            return
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        actor = access.current().username or "default"
        n = 0
        for h in hits:
            try:
                search_history.pin_result(actor, h.scope, h.entity_id,
                                 label=h.label)
                n += 1
            except ValidationError:
                pass
        self.status_var.set(f"Pinned {n} hit(s) for actor={actor!r}")

    # ── Feature 1: boolean query builder ──────────────────────────────

    def _boolean_builder(self) -> None:
        top = tk.Toplevel(self.frame.winfo_toplevel())
        top.title("Boolean query builder")
        top.transient(self.frame.winfo_toplevel())
        ttk.Label(top, text="Build a query from field/value clauses:").pack(
            padx=10, pady=(10, 4), anchor="w")
        rows_frame = ttk.Frame(top)
        rows_frame.pack(padx=10, pady=4, fill="x")
        # Only fields the parser knows; anything else would be searched as
        # plain text and silently match nothing.
        fields = ["name", "status", "subject", "tutor_group", "year",
                  "email", "upn", "uln", "postcode", "dob", "gender",
                  "preferred", "previous_school", "category", "type",
                  "description", "notes", "(keyword)"]
        rows: list[tuple] = []

        def _add_row() -> None:
            r = ttk.Frame(rows_frame)
            r.pack(fill="x", pady=1)
            join = tk.StringVar(value="AND" if rows else "")
            if rows:
                ttk.Combobox(r, textvariable=join, width=5, state="readonly",
                             values=["AND", "OR"]).pack(side="left")
            else:
                ttk.Label(r, width=5).pack(side="left")
            neg = tk.BooleanVar(value=False)
            ttk.Checkbutton(r, text="NOT", variable=neg).pack(side="left")
            fld = tk.StringVar(value="name")
            ttk.Combobox(r, textvariable=fld, width=12, state="readonly",
                         values=fields).pack(side="left", padx=2)
            val = ttk.Entry(r, width=22)
            val.pack(side="left", padx=2)
            rows.append((join, neg, fld, val))

        _add_row()
        _add_row()
        ttk.Button(top, text="+ clause", command=_add_row).pack(
            padx=10, anchor="w")

        def _compile() -> None:
            parts: list[str] = []
            for i, (join, neg, fld, val) in enumerate(rows):
                v = val.get().strip()
                if not v:
                    continue
                field = fld.get()
                term = (v if " " not in v else f'"{v}"')
                clause = (term if field == "(keyword)"
                          else f"{field}:{term}")
                if neg.get():
                    clause = f"-{clause}"
                if parts and join.get() == "OR":
                    clause = f"OR {clause}"
                parts.append(clause)
            query = " ".join(parts)
            self.query_e.delete(0, "end")
            self.query_e.insert(0, query)
            top.destroy()
            self._update_lint()
            if query:
                self.run()

        btns = ttk.Frame(top)
        btns.pack(pady=8)
        ttk.Button(btns, text="Apply & search",
                   command=_compile).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel",
                   command=top.destroy).pack(side="left", padx=4)
        top.grab_set()

    # ── Feature 5: cross-scope overlap ────────────────────────────────

    def _cross_scope_overlap(self) -> None:
        if self._last_results is None or self._last_results.total == 0:
            self.status_var.set("Run a search first.")
            return
        by_student: dict[str, dict[str, Hit]] = {}
        for h in self._last_results.all_hits():
            sid = self._hit_student_id(h.scope, h)
            if sid:
                by_student.setdefault(sid, {})[h.scope] = h
        overlaps = {sid: sc for sid, sc in by_student.items() if len(sc) >= 2}
        if not overlaps:
            messagebox.showinfo(
                "Cross-scope overlap",
                "No student appears in two or more scopes in these results.")
            return
        lines = []
        for sid, sc in sorted(overlaps.items(),
                              key=lambda kv: -len(kv[1])):
            label = next(iter(sc.values())).label
            lines.append(f"{sid}  {label[:32]:<32}  "
                         f"in {len(sc)}: {', '.join(sorted(sc))}")
        self._show_text_popup(
            f"Cross-scope overlap — {len(overlaps)} student(s)",
            "\n".join(lines))

    # ── Feature 6: query cost / row estimate ──────────────────────────

    def _estimate_query(self) -> None:
        q = self.query_e.get().strip()
        scopes = self._selected_scopes()
        if not scopes:
            self.status_var.set("Pick at least one scope to estimate.")
            return
        try:
            preview = search_engine.run_search(q, scopes=scopes, limit_per_scope=5,
                                      record_history=False)
        except ValidationError as e:
            messagebox.showerror("Estimate", str(e))
            return
        lines = [f"Estimated hits for {q or '(empty)'!r}:", ""]
        for s in preview.scopes:
            n = len(preview.hits_by_scope.get(s, []))
            cap = "≥5 (capped)" if n >= 5 else str(n)
            lines.append(f"  {SCOPE_LABELS.get(s, s):<24} {cap}")
        lines.append("")
        lines.append(f"Sampled total (cap 5/scope): {preview.total}")
        messagebox.showinfo("Query estimate", "\n".join(lines))

    # ── Feature 7: regex tester ───────────────────────────────────────

    def _regex_tester(self) -> None:
        top = tk.Toplevel(self.frame.winfo_toplevel())
        top.title("Regex tester")
        top.transient(self.frame.winfo_toplevel())
        ttk.Label(top, text="Pattern:").pack(anchor="w", padx=10, pady=(10, 0))
        pat_e = ttk.Entry(top, width=50)
        pat_e.pack(fill="x", padx=10)
        pat_e.insert(0, self.query_e.get().strip())
        ttk.Label(top, text="Sample text (one candidate per line):").pack(
            anchor="w", padx=10, pady=(8, 0))
        sample = tk.Text(top, width=60, height=8, wrap="none")
        sample.pack(fill="both", expand=True, padx=10)
        # Seed with labels from current results so it's useful immediately.
        if self._last_results:
            sample.insert("1.0", "\n".join(
                h.label for h in self._last_results.all_hits()[:20]))
        out_var = tk.StringVar()
        ttk.Label(top, textvariable=out_var, foreground="#0a6").pack(
            anchor="w", padx=10, pady=4)

        def _test() -> None:
            try:
                rx = re.compile(pat_e.get())
            except re.error as e:
                out_var.set(f"✗ invalid regex: {e}")
                return
            lines = sample.get("1.0", "end").splitlines()
            hits = [ln for ln in lines if ln and rx.search(ln)]
            out_var.set(f"✓ matches {len(hits)}/"
                        f"{len([x for x in lines if x])} line(s)")

        pat_e.bind("<KeyRelease>", lambda _e: _test())
        sample.bind("<KeyRelease>", lambda _e: _test())
        btns = ttk.Frame(top)
        btns.pack(pady=8)
        ttk.Button(btns, text="Use as query",
                   command=lambda: (self.query_e.delete(0, "end"),
                                    self.query_e.insert(0, pat_e.get()),
                                    self.regex_var.set(True),
                                    top.destroy(), self.run())).pack(
            side="left", padx=4)
        ttk.Button(btns, text="Close",
                   command=top.destroy).pack(side="left", padx=4)
        _test()

    # ── Feature 14: flag with reason code ─────────────────────────────

    _FLAG_CODES: tuple[str, ...] = (
        "safeguarding", "attendance", "behaviour", "academic",
        "pastoral", "sen", "medical", "other",
    )

    def _bulk_flag(self) -> None:
        hits = self._selected_hits()
        if not hits:
            self.status_var.set("Select rows to flag.")
            return
        code = _choose_from("Flag records", "Reason code:",
                            list(self._FLAG_CODES), self.frame)
        if not code:
            return
        reason = simpledialog.askstring(
            "Flag records", "Reason detail (optional):",
            parent=self.frame) or ""
        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        keys = {(h.scope, h.entity_id) for h in hits}
        self._snapshot_ann("bulk flag")
        store = _load_ann_store()
        for h in hits:
            ann = store.setdefault(_ann_key(h.scope, h.entity_id), {})
            ann.setdefault("flags", []).append(
                {"code": code, "reason": reason.strip(), "ts": ts})
            tags = ann.setdefault("tags", [])
            if "flag" not in tags:
                tags.append("flag")
        _save_ann_store(store)
        _append_action_log("flag", f"{code}: {reason.strip()}", len(hits))
        self._rerender()
        self._reselect(keys)
        self._on_select()
        self.status_var.set(f"Flagged {len(hits)} record(s) as {code!r}.")

    # ── Feature 16: bulk PDF one-pagers ───────────────────────────────

    def _export_pdf_reports(self) -> None:
        hits = self._selected_hits() or (
            self._last_results.all_hits() if self._last_results else [])
        if not hits:
            self.status_var.set("Select rows (or run a search) first.")
            return
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf"), ("HTML", "*.html")],
            initialfile="student_reports.pdf")
        if not path:
            return
        subset = self._results_from_hits(hits, self._last_results.query
                                         if self._last_results else "")
        try:
            search_exports.export_results_file(subset, path)
            self.status_var.set(f"Report for {len(hits)} record(s) → {path}")
        except Exception as e:                       # noqa: BLE001
            messagebox.showerror("Report failed", str(e))

    # ── Feature 17: undo last bulk annotation ─────────────────────────

    def _snapshot_ann(self, label: str) -> None:
        snap = json.dumps(_load_ann_store())
        self._ann_undo.append((label, snap))
        del self._ann_undo[:-20]                     # keep last 20

    def _undo_bulk(self) -> None:
        if not self._ann_undo:
            self.status_var.set("Nothing to undo.")
            return
        label, snap = self._ann_undo.pop()
        try:
            _save_ann_store(json.loads(snap))
        except ValueError:
            self.status_var.set("Undo failed (corrupt snapshot).")
            return
        self._rerender()
        self._on_select()
        self.status_var.set(f"Undid: {label}.")

    # ── Feature 18: assign selection to a workflow / case queue ───────

    def _bulk_assign_workflow(self) -> None:
        hits = self._selected_hits()
        if not hits:
            self.status_var.set("Select rows to assign to a workflow.")
            return
        owner = simpledialog.askstring(
            "Assign to workflow", "Owning staff (name or id):",
            parent=self.frame)
        if not owner or not owner.strip():
            return
        due = simpledialog.askstring(
            "Assign to workflow", "Due date (YYYY-MM-DD, optional):",
            parent=self.frame) or ""
        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        keys = {(h.scope, h.entity_id) for h in hits}
        self._snapshot_ann("assign workflow")
        store = _load_ann_store()
        for h in hits:
            ann = store.setdefault(_ann_key(h.scope, h.entity_id), {})
            ann["workflow"] = {"owner": owner.strip(), "due": due.strip(),
                               "state": "open", "ts": ts}
        _save_ann_store(store)
        _append_action_log("assign workflow", owner.strip(), len(hits))
        self._reselect(keys)
        self._on_select()
        self.status_var.set(
            f"Assigned {len(hits)} record(s) to {owner.strip()!r}.")

    # ── Feature 19: watchlists ────────────────────────────────────────

    def _rebuild_watchlist_menu(self) -> None:
        m = self._watch_menu
        m.delete(0, "end")
        m.add_command(label="Add selection to watchlist…",
                      command=self._add_to_watchlist)
        store = _load_ui_store()
        names = sorted(store.get("watchlists", {}))
        if names:
            m.add_separator()
            for name in names:
                sub = tk.Menu(m, tearoff=False)
                count = len(store["watchlists"][name])
                sub.add_command(
                    label=f"Load as results ({count})",
                    command=lambda n=name: self._open_watchlist(n))
                sub.add_command(label="Delete",
                                command=lambda n=name: self._delete_watchlist(n))
                m.add_cascade(label=name, menu=sub)

    def _add_to_watchlist(self) -> None:
        hits = self._selected_hits()
        if not hits:
            self.status_var.set("Select rows to add to a watchlist.")
            return
        name = simpledialog.askstring("Watchlist", "Watchlist name:",
                                      parent=self.frame)
        if not name or not name.strip():
            return
        store = _load_ui_store()
        wl = store.setdefault("watchlists", {}).setdefault(name.strip(), [])
        have = {(m["scope"], m["entity_id"]) for m in wl}
        added = 0
        for h in hits:
            if (h.scope, h.entity_id) not in have:
                wl.append({"scope": h.scope, "entity_id": h.entity_id,
                           "label": h.label})
                added += 1
        _save_ui_store(store)
        self.status_var.set(
            f"Added {added} to watchlist {name.strip()!r} ({len(wl)} total).")

    def _open_watchlist(self, name: str) -> None:
        members = _load_ui_store().get("watchlists", {}).get(name, [])
        if not members:
            self.status_var.set(f"Watchlist {name!r} is empty.")
            return
        hits = [Hit(scope=m["scope"], entity_id=m["entity_id"],
                    label=m.get("label", m["entity_id"]))
                for m in members]
        self._render(self._results_from_hits(hits, f"watchlist:{name}"))
        self.status_var.set(f"Loaded watchlist {name!r} ({len(hits)} member(s)).")

    def _delete_watchlist(self, name: str) -> None:
        store = _load_ui_store()
        if store.get("watchlists", {}).pop(name, None) is not None:
            _save_ui_store(store)
            self.status_var.set(f"Deleted watchlist {name!r}.")

    # ── Feature 22: command palette ───────────────────────────────────

    def _build_command_registry(self) -> None:
        self._commands: dict[str, Callable[[], object]] = {
            "Search: run": self.run,
            "Search: clear": self._clear,
            "Query: boolean builder": self._boolean_builder,
            "Query: regex tester": self._regex_tester,
            "Query: estimate hits": self._estimate_query,
            "Query: natural language": self._natural_language_query,
            "Query: pin current as chip": self._pin_current_query,
            "View: pivot (scope × status)": self._pivot_view,
            "View: cross-scope overlap": self._cross_scope_overlap,
            "View: save column layout": self._save_layout,
            "View: expand all": self._expand_all,
            "View: collapse all": self._collapse_all,
            "Compare: capture slot A": lambda: self._snapshot_slot("A"),
            "Compare: capture slot B": lambda: self._snapshot_slot("B"),
            "Compare: show A vs B": self._compare_slots,
            "Selection: open": self._open_selected,
            "Selection: copy IDs": self._copy_ids,
            "Selection: copy emails": self._copy_emails,
            "Selection: export…": self._export_results_dialog,
            "Selection: PDF report": self._export_pdf_reports,
            "Selection: message students": self._mailmerge_dialog,
            "Selection: flag with reason": self._bulk_flag,
            "Selection: assign to workflow": self._bulk_assign_workflow,
            "Selection: add to watchlist": self._add_to_watchlist,
            "Bulk: tag": self._bulk_tag,
            "Bulk: add note": self._bulk_add_note,
            "Bulk: undo last": self._undo_bulk,
            "Cohort: save from results": self._save_cohort,
            "Help: keyboard shortcuts": self._show_shortcuts,
            "Log: show action log": self._show_action_log,
        }

    def _command_palette(self, _event=None) -> str:
        if not hasattr(self, "_commands"):
            self._build_command_registry()
        top = tk.Toplevel(self.frame.winfo_toplevel())
        top.title("Command palette")
        top.transient(self.frame.winfo_toplevel())
        top.geometry("460x360")
        entry = ttk.Entry(top)
        entry.pack(fill="x", padx=8, pady=8)
        lb = tk.Listbox(top)
        lb.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        names = sorted(self._commands)

        def _refresh(_e=None) -> None:
            term = entry.get().strip().lower()
            lb.delete(0, "end")
            for n in names:
                if all(w in n.lower() for w in term.split()):
                    lb.insert("end", n)
            if lb.size():
                lb.selection_set(0)

        def _run_sel(_e=None) -> None:
            sel = lb.curselection()
            if not sel:
                return
            name = lb.get(sel[0])
            top.destroy()
            try:
                self._commands[name]()
            except Exception as exc:                 # noqa: BLE001
                self.status_var.set(f"{name}: {exc}")

        entry.bind("<KeyRelease>", _refresh)
        entry.bind("<Return>", _run_sel)
        entry.bind("<Down>", lambda _e: (lb.focus_set(),
                                         lb.selection_set(0)))
        lb.bind("<Return>", _run_sel)
        lb.bind("<Double-1>", _run_sel)
        top.bind("<Escape>", lambda _e: top.destroy())
        _refresh()
        entry.focus_set()
        top.grab_set()
        return "break"

    # ── Feature 23: pinned-query chips ────────────────────────────────

    def _pin_current_query(self) -> None:
        q = self.query_e.get().strip()
        if not q:
            self.status_var.set("Type a query to pin it.")
            return
        store = _load_ui_store()
        chips = store.setdefault("pinned_queries", [])
        if q not in chips:
            chips.insert(0, q)
            del chips[8:]                            # cap at 8 chips
            _save_ui_store(store)
        self._rebuild_qchips()
        self.status_var.set(f"Pinned query {q!r}.")

    def _rebuild_qchips(self) -> None:
        for w in self.qchip_frame.winfo_children():
            w.destroy()
        chips = _load_ui_store().get("pinned_queries", [])
        if not chips:
            return
        ttk.Label(self.qchip_frame, text="Pinned:").pack(side="left")
        for q in chips:
            cf = ttk.Frame(self.qchip_frame)
            cf.pack(side="left", padx=2)
            ttk.Button(cf, text=q[:24], width=min(24, len(q) + 2),
                       command=lambda qq=q: self._use_pinned_query(qq)).pack(
                side="left")
            ttk.Button(cf, text="✕", width=2,
                       command=lambda qq=q: self._unpin_query(qq)).pack(
                side="left")

    def _use_pinned_query(self, q: str) -> None:
        self.query_e.delete(0, "end")
        self.query_e.insert(0, q)
        self.run()

    def _unpin_query(self, q: str) -> None:
        store = _load_ui_store()
        chips = store.get("pinned_queries", [])
        if q in chips:
            chips.remove(q)
            _save_ui_store(store)
            self._rebuild_qchips()

    # ── Feature 25: operator action log viewer ────────────────────────

    def _show_action_log(self) -> None:
        rows = _read_action_log()
        if not rows:
            self._show_text_popup("Action log", "(no actions recorded yet)")
            return
        lines = [f"{r.get('ts', ''):<20} {r.get('actor') or '—':<14} "
                 f"{r.get('action', ''):<14} "
                 f"×{r.get('count', 0):<4} {r.get('detail', '')}"
                 for r in reversed(rows[-200:])]
        self._show_text_popup("Operator action log", "\n".join(lines))

    # ── Shared popup helper for the features above ────────────────────

    def _show_text_popup(self, title: str, text: str) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.transient(self.frame.winfo_toplevel())
        win.title(title)
        win.geometry("760x480")
        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        t = tk.Text(frame, wrap="none", font=("TkFixedFont", 9))
        vs = ttk.Scrollbar(frame, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=vs.set)
        t.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        t.insert("1.0", text or "(nothing)")
        t.configure(state="disabled")
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 8))
