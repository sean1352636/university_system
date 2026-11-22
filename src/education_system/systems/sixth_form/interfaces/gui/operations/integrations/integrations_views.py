"""Tkinter window: Integrations & Backups (CTF, LRS, database backups)."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox, simpledialog

from education_system.platform import branding
from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.domain.operations.integrations import (
    ctf,
)
from education_system.systems.sixth_form.infrastructure.integrations import (
    db_backup,
    lrs,
    store,
)
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)
TITLE = "Integrations & Backups"

_STATUS_COLOURS = {
    ctf.STATUS_MATCHED:  ("#e6f7e6", "#0d6b2a"),
    ctf.STATUS_NEW:      ("#e6f0ff", "#1a3f8c"),
    ctf.STATUS_CONFLICT: ("#fff0d6", "#7a5800"),
    ctf.STATUS_INVALID:  ("#ffd1d1", "#8c0d0d"),
}


def _error(win: tk.Misc, e: Exception) -> None:
    messagebox.showerror(TITLE, str(e), parent=win)


def _tree(parent: tk.Misc, cols: tuple[str, ...], widths: dict[str, int],
          *, height: int | None = None) -> ttk.Treeview:
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, padx=8, pady=4)
    kw = {"height": height} if height else {}
    tree = ttk.Treeview(frame, columns=cols, show="headings",
                        selectmode="browse", **kw)
    for c in cols:
        tree.heading(c, text=c.replace("_", " ").title())
        tree.column(c, width=widths.get(c, 100), anchor="w")
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    return tree


def _fill(tree: ttk.Treeview, rows: list[tuple], tags: list[str] | None = None
          ) -> None:
    tree.delete(*tree.get_children())
    for i, r in enumerate(rows):
        tree.insert("", "end", iid=str(i),
                    values=tuple("" if v is None else v for v in r),
                    tags=((tags[i],) if tags else ()))


def open_integrations_window(parent=None) -> None:
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"{TITLE} — {branding.SYSTEM_NAME}")
    window_sizing.fit(win, WIN_GEOMETRY, WIN_MINSIZE)
    try:
        store.init_db()
    except Exception as e:
        logger.exception("Integrations schema could not be prepared")
        _error(win, e)
        return
    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    CTFImportTab(nb, win)
    CTFHistoryTab(nb, win)
    CTFExportTab(nb, win)
    LRSTab(nb, win)
    BackupsTab(nb, win)
    SettingsTab(nb, win)


# ── CTF import ─────────────────────────────────────────────────────

class CTFImportTab:
    def __init__(self, nb: ttk.Notebook, win: tk.Misc) -> None:
        self.win = win
        self.path: str | None = None
        self.preview: ctf.ImportPreview | None = None
        self.resolutions: dict[int, str] = {}
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="CTF Import")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Open CTF file…", command=self._open).pack(side="left")
        ttk.Button(bar, text="Re-check", command=self._refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Resolve selected…",
                   command=self._resolve).pack(side="left", padx=(16, 4))
        ttk.Button(bar, text="Pupil detail", command=self._detail).pack(side="left", padx=4)
        ttk.Button(bar, text="Apply import", command=self._apply).pack(side="left", padx=(16, 0))
        self.info = ttk.Label(self.frame, text="No file loaded. A CTF is the DfE "
                              "XML file a Year 11 school sends with each pupil.",
                              anchor="w", justify="left")
        self.info.pack(fill="x", padx=8, pady=4)
        cols = ("no", "upn", "name", "dob", "status", "student", "basis",
                "resolution", "results", "contacts", "notes")
        self.tree = _tree(self.frame, cols, {
            "no": 40, "upn": 120, "name": 180, "dob": 90, "status": 80,
            "student": 90, "basis": 90, "resolution": 90, "results": 60,
            "contacts": 60, "notes": 420})
        for status, (bg, fg) in _STATUS_COLOURS.items():
            self.tree.tag_configure(status, background=bg, foreground=fg)

    def _open(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.win, title="Open Common Transfer File",
            filetypes=[("CTF XML", "*.xml *.XML"), ("All files", "*.*")])
        if not path:
            return
        self.path = path
        self.resolutions = {}
        self._refresh()

    def _refresh(self) -> None:
        if not self.path:
            return
        try:
            self.preview = ctf.preview(self.path)
        except Exception as e:
            self.preview = None
            _error(self.win, e)
            return
        pv = self.preview
        h = pv.file.header
        text = (f"{pv.file.file_name} — from {h.source_label}, CTF "
                f"{h.version or '?'}, generated {h.generated_at or '?'}; "
                f"{len(pv.rows)} pupil(s): {pv.count(ctf.STATUS_MATCHED)} matched, "
                f"{pv.count(ctf.STATUS_NEW)} new, {pv.count(ctf.STATUS_CONFLICT)} "
                f"conflict, {pv.count(ctf.STATUS_INVALID)} invalid.")
        if pv.applied_import_id is not None:
            text += f"\nThis exact file was already applied (import #{pv.applied_import_id})."
        self.info.configure(text=text)
        rows, tags = [], []
        for r in pv.rows:
            p = r.pupil
            rows.append((p.index + 1, p.upn, p.full_name, p.dob, r.status,
                         r.student_id, r.match_basis,
                         self.resolutions.get(p.index, ""), len(p.results),
                         len(p.contacts), "; ".join(r.notes)))
            tags.append(r.status)
        _fill(self.tree, rows, tags)

    def _selected(self) -> ctf.PreviewRow | None:
        sel = self.tree.selection()
        if not sel or self.preview is None:
            messagebox.showinfo(TITLE, "Select a pupil first.", parent=self.win)
            return None
        return self.preview.rows[int(sel[0])]

    def _resolve(self) -> None:
        row = self._selected()
        if row is None:
            return
        hint = (f"Candidates: {', '.join(row.candidates)}\n" if row.candidates else "")
        ans = simpledialog.askstring(
            TITLE,
            f"{row.pupil.full_name} ({row.status}).\n{hint}"
            "Enter a student ID to merge into, 'new' to create a new "
            "student, 'skip' to leave out, or blank to clear:",
            parent=self.win)
        if ans is None:
            return
        ans = ans.strip()
        if not ans:
            self.resolutions.pop(row.pupil.index, None)
        elif ans.lower() in (ctf.RESOLVE_NEW, ctf.RESOLVE_SKIP):
            self.resolutions[row.pupil.index] = ans.lower()
        else:
            from education_system.systems.sixth_form.domain.learners.students import (
                students,
            )
            if students.get_student(ans.upper()) is None:
                messagebox.showerror(TITLE, f"No student with id {ans}", parent=self.win)
                return
            self.resolutions[row.pupil.index] = ans.upper()
        self._refresh()

    def _detail(self) -> None:
        row = self._selected()
        if row is None:
            return
        p = row.pupil
        lines = [f"{p.full_name}  UPN {p.upn or '-'}  ULN {p.uln or '-'}  "
                 f"UCI {p.uci or '-'}", f"DOB {p.dob or '-'}  Gender "
                 f"{p.gender_code or '-'}", "", "Address:", p.address or "  (none)",
                 "", "Contacts:"]
        for c in p.contacts:
            lines.append(f"  {c.order or '-'}. {c.forename} {c.surname} "
                         f"({c.relationship}) {', '.join(n for _t, n in c.phones)} "
                         f"{c.email or ''}")
        lines += ["", "Attendance:"]
        for a in p.attendance:
            pct = f"{a.percentage}%" if a.percentage is not None else "-"
            lines.append(f"  {a.year}: possible {a.possible}, auth {a.authorised}, "
                         f"unauth {a.unauthorised} ({pct})")
        lines += ["", "Assessment results:"]
        for r in p.results:
            lines.append(f"  {r.stage or '?'} {r.year or ''} {r.subject or '?'} "
                         f"{r.component or r.method or ''}: {r.result or '-'}")
        lines += ["", f"SEN records: {len(p.sen)}   FSM records: {len(p.fsm)} "
                  "(stored on apply; viewable with SEND/funding access)"]
        top = make_toplevel(self.win)
        top.title(f"CTF pupil — {p.full_name}")
        window_sizing.fit(top, "800x600", (600, 400))
        txt = tk.Text(top, wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", "\n".join(lines))
        txt.configure(state="disabled")

    def _apply(self) -> None:
        if not self.path or self.preview is None:
            messagebox.showinfo(TITLE, "Open a CTF file first.", parent=self.win)
            return
        pv = self.preview
        unresolved = sum(1 for r in pv.rows if r.status == ctf.STATUS_CONFLICT
                         and r.pupil.index not in self.resolutions)
        msg = (f"Apply {pv.file.file_name}?\n\n"
               f"New students will be created and matched students updated "
               f"(blank fields only).")
        if unresolved:
            msg += f"\n\n{unresolved} unresolved conflict(s) will be skipped."
        if not messagebox.askyesno(TITLE, msg, parent=self.win):
            return
        try:
            res = ctf.apply(self.path, self.resolutions)
        except Exception as e:
            _error(self.win, e)
            return
        rows = [(o.index + 1, "", o.name, "", o.action, o.student_id, "", "", "",
                 "", "; ".join(o.notes)) for o in res.outcomes]
        _fill(self.tree, rows)
        self.info.configure(text=(
            f"Applied as import #{res.import_id}: {res.count('created')} created, "
            f"{res.count('updated')} updated, {res.count('unchanged')} unchanged, "
            f"{res.count('skipped')} skipped, {res.count('error')} error(s)."))
        self.preview = None


# ── CTF history ────────────────────────────────────────────────────

class CTFHistoryTab:
    def __init__(self, nb: ttk.Notebook, win: tk.Misc) -> None:
        self.win = win
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="CTF History")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Forward pending results",
                   command=self._forward).pack(side="left", padx=(16, 0))
        ttk.Label(self.frame, text="Applied imports").pack(anchor="w", padx=8)
        self.imports = _tree(self.frame, (
            "import_id", "file", "source", "pupils", "created", "updated",
            "skipped", "applied_by", "applied_at"), {
            "import_id": 60, "file": 260, "source": 220, "applied_at": 140},
            height=6)
        self.imports.bind("<<TreeviewSelect>>", lambda _e: self._pupils())
        ttk.Label(self.frame, text="Pupils in selected import").pack(anchor="w", padx=8)
        self.pupils = _tree(self.frame, (
            "upn", "name", "dob", "student", "action", "notes"),
            {"upn": 120, "name": 180, "notes": 600}, height=8)
        ttk.Label(self.frame, text="KS4 results not yet passed to a prior-"
                  "attainment store").pack(anchor="w", padx=8)
        self.pending = _tree(self.frame, (
            "student", "name", "year", "subject", "component", "result",
            "import_id"), {"name": 180, "subject": 160}, height=8)
        self._import_rows: list[dict] = []
        self.refresh()

    def refresh(self) -> None:
        try:
            self._import_rows = ctf.list_imports()
            pending = ctf.pending_results()
        except Exception as e:
            _error(self.win, e)
            return
        _fill(self.imports, [(
            r["import_id"], r["file_name"],
            f"{r['source_name'] or ''} {r['source_la'] or '?'}/{r['source_estab'] or '?'}",
            r["pupil_count"], r["created_count"], r["updated_count"],
            r["skipped_count"], r["applied_by"], r["applied_at"])
            for r in self._import_rows])
        _fill(self.pending, [(
            r["student_id"], r["student_name"], r["year"], r["subject"],
            r["component"] or r["method"], r["result"], r["import_id"])
            for r in pending])
        self.pupils.delete(*self.pupils.get_children())

    def _pupils(self) -> None:
        sel = self.imports.selection()
        if not sel:
            return
        imp = self._import_rows[int(sel[0])]
        rows = ctf.import_pupils(imp["import_id"])
        _fill(self.pupils, [(
            r["upn"], f"{r['forename'] or ''} {r['surname'] or ''}", r["dob"],
            r["student_id"], r["action"], r["notes"]) for r in rows])

    def _forward(self) -> None:
        try:
            done, left = ctf.forward_pending_results()
        except Exception as e:
            _error(self.win, e)
            return
        messagebox.showinfo(TITLE, f"Forwarded {done} result(s); {left} still pending.",
                            parent=self.win)
        self.refresh()


# ── CTF export ─────────────────────────────────────────────────────

class CTFExportTab:
    def __init__(self, nb: ttk.Notebook, win: tk.Misc) -> None:
        self.win = win
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="CTF Export")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Label(bar, text="Destination LA:").pack(side="left", padx=(16, 2))
        self.dest_la = ttk.Entry(bar, width=6)
        self.dest_la.insert(0, ctf.UNKNOWN_DEST_LA)
        self.dest_la.pack(side="left")
        ttk.Label(bar, text="Estab:").pack(side="left", padx=(8, 2))
        self.dest_estab = ttk.Entry(bar, width=6)
        self.dest_estab.insert(0, ctf.UNKNOWN_DEST_ESTAB)
        self.dest_estab.pack(side="left")
        ttk.Button(bar, text="Export selected leaver",
                   command=self._export).pack(side="left", padx=(16, 0))
        ttk.Label(self.frame, text="Leavers (status 'Left'). XXX/XXXX = "
                  "destination unknown; MMM/MMMM = leaving England/Wales.").pack(
            anchor="w", padx=8)
        self.leavers = _tree(self.frame, ("student", "name", "dob", "uln", "email"),
                             {"name": 220, "email": 240}, height=12)
        ttk.Label(self.frame, text="Exports written").pack(anchor="w", padx=8)
        self.exports = _tree(self.frame, (
            "export_id", "student", "file", "dest", "by", "at"),
            {"file": 560, "at": 140}, height=8)
        self._leavers: list = []
        self.refresh()

    def refresh(self) -> None:
        try:
            self._leavers = ctf.list_leavers()
            exports = ctf.list_exports()
        except Exception as e:
            _error(self.win, e)
            return
        _fill(self.leavers, [(s.student_id, s.full_name, s.date_of_birth, s.uln,
                              s.email) for s in self._leavers])
        _fill(self.exports, [(r["export_id"], r["student_id"], r["file_path"],
                              f"{r['dest_la']}/{r['dest_estab']}",
                              r["exported_by"], r["exported_at"]) for r in exports])

    def _export(self) -> None:
        sel = self.leavers.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a leaver first.", parent=self.win)
            return
        s = self._leavers[int(sel[0])]
        try:
            res = ctf.export_leaver(s.student_id, dest_la=self.dest_la.get(),
                                    dest_estab=self.dest_estab.get())
        except Exception as e:
            _error(self.win, e)
            return
        messagebox.showinfo(TITLE, f"CTF written to\n{res.path}", parent=self.win)
        self.refresh()


# ── LRS ────────────────────────────────────────────────────────────

class LRSTab:
    def __init__(self, nb: ttk.Notebook, win: tk.Misc) -> None:
        self.win = win
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="LRS / ULN")
        self.status = ttk.Label(self.frame, anchor="w", justify="left",
                                wraplength=1200)
        self.status.pack(fill="x", padx=8, pady=(8, 4))
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=4)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Find ULN on LRS",
                   command=self._find).pack(side="left", padx=(16, 4))
        ttk.Button(bar, text="Verify ULN on LRS",
                   command=self._verify).pack(side="left", padx=4)
        ttk.Button(bar, text="Enter ULN…", command=self._enter).pack(side="left", padx=4)
        ttk.Label(bar, text="Check a ULN:").pack(side="left", padx=(24, 2))
        self.check = ttk.Entry(bar, width=14)
        self.check.pack(side="left")
        ttk.Button(bar, text="Check", command=self._check).pack(side="left", padx=4)
        ttk.Label(self.frame, text="Students missing a ULN, or with a ULN that "
                  "fails the check digit").pack(anchor="w", padx=8)
        self.tree = _tree(self.frame, ("student", "name", "dob", "status", "uln",
                                       "issue"),
                          {"name": 220, "issue": 360}, height=14)
        ttk.Label(self.frame, text="LRS request log").pack(anchor="w", padx=8)
        self.log = _tree(self.frame, ("at", "operation", "student", "code",
                                      "response", "ulns", "error", "by"),
                         {"at": 140, "response": 240, "error": 300}, height=7)
        self._rows: list = []
        self.refresh()

    def refresh(self) -> None:
        ok, text = lrs.config_status()
        self.status.configure(text=text, foreground=("#0d6b2a" if ok else "#8c0d0d"))
        try:
            missing = lrs.students_missing_uln()
            bad = lrs.students_with_invalid_uln()
            log = lrs.list_requests()
        except Exception as e:
            _error(self.win, e)
            return
        self._rows = [(s, "No ULN") for s in missing] + [
            (s, lrs.explain_uln(s.uln)) for s in bad]
        _fill(self.tree, [(s.student_id, s.full_name, s.date_of_birth, s.status,
                           s.uln, issue) for s, issue in self._rows])
        _fill(self.log, [(r["requested_at"], r["operation"], r["student_id"],
                          r["response_code"], r["response_text"],
                          r["ulns_returned"], r["error"], r["requested_by"])
                         for r in log])

    def _student(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a student first.", parent=self.win)
            return None
        return self._rows[int(sel[0])][0]

    def _find(self) -> None:
        s = self._student()
        if s is None:
            return
        try:
            resp = lrs.find_uln_for_student(s.student_id)
        except Exception as e:
            _error(self.win, e)
            self.refresh()
            return
        self.refresh()
        if not resp.learners:
            messagebox.showinfo(TITLE, f"LRS: {resp.description} ({resp.code}).",
                                parent=self.win)
            return
        lines = [f"{i}. ULN {l.uln} — {l.given_name or ''} {l.family_name or ''}, "
                 f"DOB {l.date_of_birth or '?'}, postcode {l.postcode or '?'}"
                 for i, l in enumerate(resp.learners, 1)]
        ans = simpledialog.askstring(
            TITLE, f"LRS: {resp.description} ({resp.code}).\n\n" + "\n".join(lines)
            + "\n\nEnter the number of the learner to record that ULN (blank to "
              "record nothing):", parent=self.win)
        if not ans or not ans.strip().isdigit():
            return
        n = int(ans.strip())
        if not 1 <= n <= len(resp.learners):
            return
        try:
            lrs.apply_uln(s.student_id, resp.learners[n - 1].uln)
        except Exception as e:
            _error(self.win, e)
        self.refresh()

    def _verify(self) -> None:
        sel = self.tree.selection()
        s = self._rows[int(sel[0])][0] if sel else None
        sid = s.student_id if s and s.uln else simpledialog.askstring(
            TITLE, "Student ID to verify:", parent=self.win)
        if not sid:
            return
        try:
            resp = lrs.verify_student_uln(sid.strip().upper())
        except Exception as e:
            _error(self.win, e)
            self.refresh()
            return
        messagebox.showinfo(TITLE, f"LRS: {resp.description} ({resp.code}).",
                            parent=self.win)
        self.refresh()

    def _enter(self) -> None:
        s = self._student()
        if s is None:
            return
        uln = simpledialog.askstring(TITLE, f"ULN for {s.full_name}:", parent=self.win)
        if not uln:
            return
        try:
            lrs.apply_uln(s.student_id, uln.strip())
        except Exception as e:
            _error(self.win, e)
            return
        self.refresh()

    def _check(self) -> None:
        messagebox.showinfo(TITLE, lrs.explain_uln(self.check.get()), parent=self.win)


# ── Backups ────────────────────────────────────────────────────────

class BackupsTab:
    def __init__(self, nb: ttk.Notebook, win: tk.Misc) -> None:
        self.win = win
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Database Backups")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Back up now", command=self._backup).pack(side="left", padx=(16, 4))
        ttk.Label(bar, text="Keep newest:").pack(side="left", padx=(16, 2))
        self.keep = ttk.Spinbox(bar, from_=db_backup.MIN_KEEP, to=365, width=5)
        self.keep.pack(side="left")
        ttk.Button(bar, text="Save", command=self._save_keep).pack(side="left", padx=4)
        ttk.Button(bar, text="Preview restore", command=self._preview).pack(side="left", padx=(24, 4))
        ttk.Button(bar, text="Restore…", command=self._restore).pack(side="left", padx=4)
        self.dir_label = ttk.Label(self.frame, anchor="w")
        self.dir_label.pack(fill="x", padx=8)
        ttk.Label(self.frame, text="Databases").pack(anchor="w", padx=8)
        self.dbs = _tree(self.frame, ("path", "size", "constants"),
                         {"path": 520, "size": 90, "constants": 700}, height=3)
        ttk.Label(self.frame, text="Backups (newest first)").pack(anchor="w", padx=8)
        self.backups = _tree(self.frame, ("name", "database", "created", "label", "size"),
                             {"name": 420, "created": 160}, height=10)
        self.detail = tk.Text(self.frame, height=12, wrap="none")
        self.detail.pack(fill="both", expand=False, padx=8, pady=(4, 8))
        self._backups: list[db_backup.BackupInfo] = []
        self.refresh()

    def refresh(self) -> None:
        self.dir_label.configure(text=f"Backup folder: {db_backup.backup_dir()}")
        try:
            self.keep.delete(0, "end")
            self.keep.insert(0, str(db_backup.keep_count()))
            consts = db_backup.database_constants()
            self._backups = db_backup.list_backups()
        except Exception as e:
            _error(self.win, e)
            return
        _fill(self.dbs, [(str(p), f"{p.stat().st_size / 1048576:.1f} MB"
                          if p.is_file() else "missing",
                          f"{len(names)}: " + ", ".join(names))
                         for p, names in consts.items()])
        _fill(self.backups, [(b.name, b.stem, b.created.strftime("%Y-%m-%d %H:%M:%S"),
                              b.label or "", b.size_label) for b in self._backups])

    def _show(self, text: str) -> None:
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def _backup(self) -> None:
        try:
            results = db_backup.backup_all()
        except Exception as e:
            _error(self.win, e)
            return
        self._show("\n".join(
            f"{r.source} -> {r.backup.path} ({r.backup.size_label}), integrity "
            f"{r.integrity}; rotated out {len(r.removed)}" for r in results)
            or "No database files exist yet.")
        self.refresh()

    def _save_keep(self) -> None:
        try:
            db_backup.set_keep_count(int(self.keep.get()))
        except Exception as e:
            _error(self.win, e)
            return
        messagebox.showinfo(TITLE, "Retention saved. It applies from the next backup.",
                            parent=self.win)

    def _selected(self) -> db_backup.BackupInfo | None:
        sel = self.backups.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a backup first.", parent=self.win)
            return None
        return self._backups[int(sel[0])]

    def _preview(self) -> db_backup.RestorePreview | None:
        b = self._selected()
        if b is None:
            return None
        try:
            pv = db_backup.restore_preview(b)
        except Exception as e:
            _error(self.win, e)
            return None
        lines = [f"Backup:    {b.path} ({b.size_label}, {b.created})",
                 f"Target:    {pv.target}",
                 f"Integrity: {pv.integrity}",
                 f"Tables:    {len(pv.backup_counts)} in backup, "
                 f"{len(pv.current_counts)} now", ""]
        diffs = pv.differences()
        if diffs:
            lines.append(f"{'Table':<40} {'Now':>10} {'Backup':>10}")
            for name, now, then in diffs:
                lines.append(f"{name:<40} {now if now is not None else '-':>10} "
                             f"{then if then is not None else '-':>10}")
        else:
            lines.append("Row counts are identical in every table.")
        self._show("\n".join(lines))
        return pv

    def _restore(self) -> None:
        pv = self._preview()
        if pv is None:
            return
        if pv.integrity != "ok":
            messagebox.showerror(TITLE, "This backup failed its integrity check "
                                 "and cannot be restored.", parent=self.win)
            return
        phrase = db_backup.confirmation_phrase(pv.backup)
        typed = simpledialog.askstring(
            TITLE, f"Restoring replaces ALL data in\n{pv.target}\nwith this "
            "backup. A safety copy of the current database is taken first.\n\n"
            f"Type exactly:\n{phrase}", parent=self.win)
        if typed is None:
            return
        try:
            res = db_backup.restore(pv.backup, typed)
        except Exception as e:
            _error(self.win, e)
            return
        messagebox.showinfo(
            TITLE, f"Restored {res.target}\nfrom {res.restored_from}.\n"
            f"Safety copy: {res.safety_backup}\nIntegrity: {res.integrity}\n\n"
            "Restart the application now so every screen reloads.",
            parent=self.win)
        self.refresh()


# ── Settings ───────────────────────────────────────────────────────

_SETTING_LABELS = (
    ("school_la", "College LA number (3 digits)"),
    ("school_estab", "College establishment number (4 digits)"),
    ("school_name", "College name (CTF header)"),
    ("lrs_endpoint", "LRS endpoint URL"),
    ("lrs_ukprn", "LRS UKPRN"),
    ("lrs_username", "LRS username"),
    ("lrs_vendor_id", "LRS vendor id (optional)"),
)


class SettingsTab:
    def __init__(self, nb: ttk.Notebook, win: tk.Misc) -> None:
        self.win = win
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Settings")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Reload", command=self.refresh).pack(side="left", padx=4)
        form = ttk.Frame(self.frame)
        form.pack(fill="x", padx=16, pady=8)
        self.entries: dict[str, ttk.Entry] = {}
        for i, (key, label) in enumerate(_SETTING_LABELS):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", pady=3)
            e = ttk.Entry(form, width=60)
            e.grid(row=i, column=1, sticky="w", padx=8, pady=3)
            self.entries[key] = e
        ttk.Label(self.frame, justify="left", text=(
            "The LRS password is read only from the LRS_PASSWORD environment "
            "variable (and a client certificate from LRS_CERT_FILE / LRS_KEY_FILE); "
            "it is never stored in the database.\nEnvironment variables "
            "LRS_ENDPOINT, LRS_UKPRN and LRS_USERNAME override the values above.")
        ).pack(anchor="w", padx=16, pady=8)
        self.refresh()

    def refresh(self) -> None:
        try:
            for key, e in self.entries.items():
                e.delete(0, "end")
                e.insert(0, store.get_setting(key))
        except Exception as e:
            _error(self.win, e)

    def _save(self) -> None:
        try:
            who = store.require("ADMIN", "integration settings")
            for key, e in self.entries.items():
                store.set_setting(key, e.get(), by=who)
        except Exception as e:
            _error(self.win, e)
            return
        messagebox.showinfo(TITLE, "Settings saved.", parent=self.win)
