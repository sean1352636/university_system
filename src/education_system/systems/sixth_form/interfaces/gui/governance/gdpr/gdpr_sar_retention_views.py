"""GDPR window tabs: Subject Access (deadlines, extension, preview and
bundle compilation — safeguarding records are never exported) and
Retention (schedule, DRY-RUN report, and an admin-only purge that ships
switched off, must be opted in per category and confirmed twice)."""

from __future__ import annotations

import json
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog

from education_system.systems.sixth_form.domain.governance.gdpr import (
    retention as ret,
    sar,
)
from education_system.systems.sixth_form.domains.finance.interfaces.gui import (
    _widgets as w,
)


def add_gdpr_tabs(nb: ttk.Notebook) -> None:
    SarTab(nb)
    RetentionTab(nb)


class SarTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Subject Access")
        w.button_bar(self.frame, [
            ("Refresh", self.refresh),
            ("Extend Deadline…", self.extend),
            ("Preview Learner's Data…", self.preview),
            ("Compile SAR Bundle…", self.compile),
        ])
        ttk.Label(self.frame, text=(
            "Deadline: one calendar month from receipt, extendable once by "
            "up to two months (tell the requester before the original due "
            "date). Safeguarding records are never put in a bundle; they "
            "are listed for the DSL. Third-party data is flagged for "
            "redaction review."), wraplength=1300,
            justify="left").pack(fill="x", padx=10)
        pane = ttk.PanedWindow(self.frame, orient="vertical")
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        top = ttk.LabelFrame(pane, text="Open requests by deadline")
        pane.add(top, weight=2)
        self.table = w.Table(top, [
            ("#", 40), ("Subject", 180), ("Ref", 80), ("Type", 180),
            ("Received", 90), ("Due", 90), ("Extended to", 90),
            ("Days left", 70), ("RAG", 80), ("Compiled", 130)], height=8)
        self.table.pack(fill="both", expand=True, padx=4, pady=4)
        low = ttk.LabelFrame(pane, text="Result")
        pane.add(low, weight=3)
        self.out = w.TextPanel(low)
        self.out.pack(fill="both", expand=True, padx=4, pady=4)
        self.refresh()

    def refresh(self) -> None:
        self.table.set_rows(
            [(d.request_id, d.subject_name, d.subject_ref or "",
              d.request_type, d.received_date, d.due_date,
              d.extended_due_date or "", d.days_remaining, d.rag,
              (d.compiled_at or "")[:16]) for d in sar.deadlines()],
            alert=lambda r: r[8] in ("Overdue", "Due soon"))

    def extend(self) -> None:
        rid = w.need_selection(self.frame, self.table)
        if rid is None:
            return
        f = w.ask_form(self.frame, f"Extend request #{rid}", [
            ("months", f"Months (1-{sar.EXTENSION_MONTHS})", "entry",
             sar.EXTENSION_MONTHS, None),
            ("reason", "Reason (complex / several requests)", "text", "",
             None)])
        if f and w.call(self.frame, lambda: sar.extend_deadline(
                rid, reason=f["reason"] or "", by=w.actor() or "",
                months=w.whole(f["months"]) or sar.EXTENSION_MONTHS),
                done="Deadline extended.") is not None:
            self.refresh()

    def _student(self, title: str) -> str | None:
        f = w.ask_form(self.frame, title, [
            ("student", "Learner", "combo", "", w.student_choices())])
        return w.student_id(f["student"]) if f else None

    def preview(self) -> None:
        sid = self._student("Preview learner's data")
        if not sid:
            return
        res = w.call(self.frame, lambda: sar.scan(sid))
        if res is None:
            return
        included, safeguarding = res
        lines = [f"Records held for {sid} (preview — nothing written)", ""]
        for t in included:
            flag = t.review_reason or (
                "columns: " + ", ".join(t.flagged_columns)
                if t.flagged_columns else "")
            lines.append(f"  {t.table:<36} {len(t.rows):>5} row(s)"
                         + (f"  via {t.via}" if t.via else "")
                         + (f"  [REVIEW: {flag}]" if flag else ""))
        if safeguarding:
            lines += ["", "Safeguarding records (NOT exported — for the DSL):"]
            lines += [f"  {k}: {len(v)} record(s)"
                      for k, v in safeguarding.items()]
        self.out.set("\n".join(lines))

    def compile(self) -> None:
        sid = self._student("Compile SAR bundle")
        if not sid:
            return
        rid = self.table.selected_id()
        if rid is not None and not messagebox.askyesno(
                "Link request", f"Link the bundle to request #{rid}?",
                parent=self.frame):
            rid = None
        b = w.call(self.frame, lambda: sar.compile_sar(
            sid, request_id=rid, compiled_by=w.actor() or None))
        if b is None:
            return
        lines = [f"Bundle written to {b.folder}",
                 f"{b.total_rows} row(s) from {len(b.included)} table(s)", ""]
        if b.review_tables:
            lines.append("Review for third-party data before release "
                         "(REDACTION_REVIEW.txt):")
            lines += [f"  {t.table}" for t in b.review_tables]
        if b.safeguarding:
            lines.append("")
            lines.append("Safeguarding records exist — see DSL_REVIEW.txt "
                         "(not in the bundle):")
            lines += [f"  {k}: {len(v)}" for k, v in b.safeguarding.items()]
        self.out.set("\n".join(lines))
        self.refresh()


class RetentionTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Retention")
        w.button_bar(self.frame, [
            ("Refresh", self.refresh),
            ("Dry Run", self.dry_run),
            ("Load Suggested Schedule…", self.load_suggested),
            ("Add / Edit Category…", self.edit),
            ("Delete Category", self.delete),
            ("Opt In / Out (admin)", self.toggle),
            ("Purge Switch (admin)…", self.switch),
            ("Run Purge (admin)…", self.apply),
            ("Run Log", self.show_log),
        ])
        self.status = ttk.Label(self.frame, text="")
        self.status.pack(fill="x", padx=10)
        pane = ttk.PanedWindow(self.frame, orient="vertical")
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        top = ttk.LabelFrame(pane, text="Retention schedule")
        pane.add(top, weight=2)
        self.table = w.Table(top, [
            ("Category", 200), ("Months", 60), ("Trigger", 100),
            ("Date column", 100), ("Action", 80), ("Opted in", 70),
            ("Tables", 500)], height=7)
        self.table.pack(fill="both", expand=True, padx=4, pady=4)
        low = ttk.LabelFrame(pane, text="Dry run / log")
        pane.add(low, weight=3)
        self.out = w.TextPanel(low)
        self.out.pack(fill="both", expand=True, padx=4, pady=4)
        self.refresh()

    def _selected_name(self) -> str | None:
        row = self.table.selected()
        if not row:
            messagebox.showinfo("Select", "Select a category first.",
                                parent=self.frame)
            return None
        return str(row[0])

    def refresh(self) -> None:
        on = ret.purge_enabled()
        self.status.configure(
            text=f"Purge switch: {'ON' if on else 'OFF'} — purges also need "
                 "the category opted in, an admin, and two confirmations. "
                 "The database is backed up first. Safeguarding records are "
                 "never touched.")
        self.table.set_rows(
            [(c.category, c.retention_months, c.trigger,
              c.date_column or "", c.action, "YES" if c.enabled else "no",
              ", ".join(c.tables)) for c in ret.list_categories()],
            alert=lambda r: r[5] == "YES")

    def dry_run(self) -> None:
        res = w.call(self.frame, ret.dry_run)
        if res is not None:
            self.out.set(ret.dry_run_text(res))

    def load_suggested(self) -> None:
        if messagebox.askyesno(
                "Suggested schedule", "Load the suggested categories? They "
                "arrive disabled; review the periods against your own "
                "retention policy.", parent=self.frame):
            made = w.call(self.frame, lambda: ret.load_suggested_schedule(
                by=w.actor() or "unknown"))
            if made is not None:
                self.refresh()

    def edit(self) -> None:
        row = self.table.selected()
        cur = ret.get_category(str(row[0])) if row else None
        f = w.ask_form(self.frame, "Retention category", [
            ("category", "Name", "entry", cur.category if cur else "", None),
            ("description", "Description", "entry",
             (cur.description or "") if cur else "", None),
            ("tables", "Tables (comma separated)", "entry",
             ", ".join(cur.tables) if cur else "", None),
            ("retention_months", "Keep for (months)", "entry",
             cur.retention_months if cur else "", None),
            ("trigger", "Trigger", "combo",
             cur.trigger if cur else ret.TRIGGER_LEAVING, ret.TRIGGERS),
            ("date_column", "Date column (record-date trigger)", "entry",
             (cur.date_column or "") if cur else "", None),
            ("action", "Action", "combo",
             cur.action if cur else ret.ACTION_ANONYMISE, ret.ACTIONS),
            ("notes", "Notes", "text", (cur.notes or "") if cur else "",
             None)],
            note="Saving never opts a category in. Safeguarding tables are "
                 "refused.")
        if f and w.call(self.frame, lambda: ret.save_category(
                f, by=w.actor() or "unknown"), done="Saved.") is not None:
            self.refresh()

    def delete(self) -> None:
        name = self._selected_name()
        if name and messagebox.askyesno("Delete", f"Delete category "
                                        f"{name!r}?", parent=self.frame):
            w.call(self.frame, lambda: ret.delete_category(name))
            self.refresh()

    def toggle(self) -> None:
        name = self._selected_name()
        cat = ret.get_category(name) if name else None
        if cat is None:
            return
        on = not cat.enabled
        if messagebox.askyesno(
                "Opt in" if on else "Opt out",
                f"{'Opt in' if on else 'Disable'} {name!r}?",
                parent=self.frame):
            w.call(self.frame, lambda: ret.set_category_enabled(name, on))
            self.refresh()

    def switch(self) -> None:
        on = ret.purge_enabled()
        if messagebox.askyesno(
                "Purge switch", f"Turn retention purges "
                f"{'OFF' if on else 'ON'} for this college?",
                parent=self.frame):
            w.call(self.frame, lambda: ret.set_purge_enabled(not on))
            self.refresh()

    def apply(self) -> None:
        name = self._selected_name()
        if not name:
            return
        res = w.call(self.frame, lambda: ret.dry_run([name]))
        if not res:
            return
        self.out.set(ret.dry_run_text(res))
        f = res[0]
        if f.rows == 0:
            messagebox.showinfo("Nothing to do", "The dry run found nothing.",
                                parent=self.frame)
            return
        if not messagebox.askyesno(
                "First confirmation",
                f"{f.category.action.upper()} {f.rows} row(s) for "
                f"{len(f.learners)} learner(s) in {name!r}?\n\nThe database "
                "is backed up first.", icon="warning", parent=self.frame):
            return
        typed = simpledialog.askstring(
            "Second confirmation", "Type the category name exactly:",
            parent=self.frame)
        if typed is None:
            return
        out = w.call(self.frame, lambda: ret.apply_category(
            name, confirm=typed, actor=w.actor() or None))
        if out is not None:
            messagebox.showinfo(
                "Purge done", f"{out['rows']} row(s) for {out['learners']} "
                f"learner(s).\nBackup: {out['backup']}", parent=self.frame)
            self.refresh()

    def show_log(self) -> None:
        rows = w.call(self.frame, ret.run_log) or []
        if not rows:
            self.out.set("No retention purges have been run.")
            return
        lines = ["Retention run log", ""]
        for r in rows:
            detail = json.loads(r.get("detail") or "{}")
            lines.append(f"{r['run_at']}  {r['category']}  {r['action']}  "
                         f"{r['learners']} learner(s), {r['rows_affected']} "
                         f"row(s)  by {r['run_by']}")
            lines.append(f"    backup: {r['backup_path']}")
            if detail:
                lines.append("    " + ", ".join(f"{k}: {v}"
                                                for k, v in detail.items()))
        self.out.set("\n".join(lines))
