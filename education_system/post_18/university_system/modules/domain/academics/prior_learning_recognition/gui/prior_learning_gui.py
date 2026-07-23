"""Accreditation of Prior Learning (APL/RPL) GUI."""

import logging
import tkinter as tk
from tkinter import messagebox, ttk

logger = logging.getLogger(__name__)


class PriorLearningGUI:
    def __init__(self, parent=None, *, student_id: str | None = None):
        if parent is not None and not hasattr(parent, "wm_title"):
            self.root = parent
            self._owns_window = False
        else:
            self.root = tk.Toplevel(parent) if parent else tk.Tk()
            title = "Accreditation of Prior Learning (APL/RPL)"
            if student_id:
                title = f"{title} — student {student_id}"
            self.root.title(title)
            self.root.geometry("1400x900")
            try:
                self.root.minsize(1200, 800)
            except Exception:
                pass
            self._owns_window = True

        try:
            from education_system.post_18.university_system.modules.domain.academics.prior_learning_recognition.services.prior_learning_service import (
                PriorLearningService,
            )
            self.service = PriorLearningService()
        except Exception as e:
            logger.error(f"Service init error: {e}")
            self.service = None

        try:
            from education_system.post_18.university_system.infrastructure.shared_context import (
                get_auth,
            )
            self.auth = get_auth()
        except Exception:
            self.auth = None

        self._context_student_id: str | None = (
            str(student_id) if student_id else None
        )

        self._setup_ui()

    # ------------------------------------------------------------------ helpers
    def _current_user(self) -> str:
        try:
            return self.auth.current_user.get("username", "system")
        except Exception:
            return "system"

    # ------------------------------------------------------------------ layout
    def _setup_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._build_claims_tab(notebook)
        self._build_evidence_tab(notebook)
        self._build_awards_tab(notebook)
        self._build_stats_tab(notebook)

    # ------------------------------------------------------------------ claims
    def _build_claims_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Claims")

        cols = ("id", "claimant", "type", "target", "requested", "awarded", "status")
        self.claims_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        widths = {"id": 50, "claimant": 130, "type": 170, "target": 220,
                  "requested": 90, "awarded": 90, "status": 110}
        for c in cols:
            self.claims_tree.heading(c, text=c.replace("_", " ").title())
            self.claims_tree.column(c, width=widths.get(c, 130))
        self.claims_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btns = ttk.Frame(tab)
        btns.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btns, text="New Claim", command=self._new_claim).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Submit", command=self._submit_claim).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Review", command=self._review_claim).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Withdraw", command=self._withdraw_claim).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Refresh", command=self._refresh_claims).pack(side=tk.RIGHT, padx=2)

        self._refresh_claims()

    def _refresh_claims(self):
        for row in self.claims_tree.get_children():
            self.claims_tree.delete(row)
        if not self.service:
            return
        try:
            claims = (
                self.service.list_claims(claimant_id=self._context_student_id)
                if self._context_student_id
                else self.service.list_claims()
            )
            for c in claims:
                self.claims_tree.insert("", tk.END, values=(
                    c["id"],
                    c.get("claimant_id", ""),
                    c.get("claim_type", ""),
                    c.get("target_course") or c.get("target_qualification") or "",
                    c.get("credits_requested", 0),
                    c.get("credits_awarded", 0),
                    c.get("status", ""),
                ))
        except Exception as e:
            logger.error(f"Error loading claims: {e}")

    def _selected_claim_id(self):
        sel = self.claims_tree.selection()
        if not sel:
            return None
        return int(self.claims_tree.item(sel[0], "values")[0])

    def _new_claim(self):
        from education_system.post_18.university_system.modules.domain.academics.prior_learning_recognition.services.prior_learning_service import (
            CLAIM_TYPES,
        )
        if not self.service:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("New APL/RPL Claim")
        dlg.geometry("520x460")
        dlg.transient(self.root)
        dlg.grab_set()

        rows = [
            ("Claimant ID:", "claimant_id", "entry", None),
            ("Claimant name:", "claimant_name", "entry", None),
            ("Claim type:", "claim_type", "combo", list(CLAIM_TYPES)),
            ("Target course:", "target_course", "entry", None),
            ("Target qualification:", "target_qualification", "entry", None),
            ("Credits requested:", "credits_requested", "entry", None),
            ("Summary:", "summary", "text", None),
        ]
        widgets = {}
        for i, (label, key, kind, opts) in enumerate(rows):
            ttk.Label(dlg, text=label).grid(row=i, column=0, sticky=tk.W, padx=10, pady=4)
            if kind == "entry":
                w = ttk.Entry(dlg, width=42)
            elif kind == "combo":
                w = ttk.Combobox(dlg, values=opts, width=39, state="readonly")
            else:
                w = tk.Text(dlg, width=42, height=4)
            w.grid(row=i, column=1, padx=10, pady=4, sticky=tk.W)
            widgets[key] = w

        def save():
            try:
                vals = {}
                for key, w in widgets.items():
                    if isinstance(w, tk.Text):
                        vals[key] = w.get("1.0", tk.END).strip() or None
                    else:
                        vals[key] = w.get().strip() or None
                if not vals.get("claimant_id") or not vals.get("claim_type"):
                    messagebox.showerror("Error", "Claimant ID and claim type required.")
                    return
                try:
                    credits = int(vals.get("credits_requested") or 0)
                except ValueError:
                    credits = 0
                self.service.create_claim(
                    vals["claimant_id"],
                    vals["claim_type"],
                    target_course=vals.get("target_course"),
                    target_qualification=vals.get("target_qualification"),
                    claimant_name=vals.get("claimant_name"),
                    summary=vals.get("summary"),
                    credits_requested=credits,
                )
                dlg.destroy()
                self._refresh_claims()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        btn_row = ttk.Frame(dlg)
        btn_row.grid(row=len(rows), column=0, columnspan=2, pady=10)
        ttk.Button(btn_row, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT, padx=5)

    def _submit_claim(self):
        cid = self._selected_claim_id()
        if not cid or not self.service:
            return
        self.service.submit_claim(cid)
        self._refresh_claims()

    def _withdraw_claim(self):
        cid = self._selected_claim_id()
        if not cid or not self.service:
            return
        if messagebox.askyesno("Confirm", f"Withdraw claim {cid}?"):
            self.service.withdraw_claim(cid)
            self._refresh_claims()

    def _review_claim(self):
        cid = self._selected_claim_id()
        if not cid or not self.service:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Review Claim {cid}")
        dlg.geometry("440x260")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Decision:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=6)
        decision = ttk.Combobox(
            dlg,
            values=["approved", "partial", "rejected", "under_review"],
            state="readonly",
            width=30,
        )
        decision.grid(row=0, column=1, padx=10, pady=6)

        ttk.Label(dlg, text="Notes:").grid(row=1, column=0, sticky=tk.NW, padx=10, pady=6)
        notes = tk.Text(dlg, width=34, height=6)
        notes.grid(row=1, column=1, padx=10, pady=6)

        def save():
            d = decision.get().strip()
            if not d:
                messagebox.showerror("Error", "Pick a decision.")
                return
            try:
                self.service.review_claim(
                    cid, d, reviewed_by=self._current_user(),
                    notes=notes.get("1.0", tk.END).strip() or None,
                )
                dlg.destroy()
                self._refresh_claims()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        btn_row = ttk.Frame(dlg)
        btn_row.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(btn_row, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT, padx=5)

    # ------------------------------------------------------------- evidence
    def _build_evidence_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Evidence")

        top = ttk.Frame(tab)
        top.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(top, text="Claim ID:").pack(side=tk.LEFT, padx=4)
        self.evidence_claim_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.evidence_claim_var, width=10).pack(side=tk.LEFT)
        ttk.Button(top, text="Load", command=self._refresh_evidence).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Add Evidence", command=self._add_evidence).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Verify Selected", command=self._verify_evidence).pack(side=tk.LEFT, padx=4)

        cols = ("id", "type", "title", "issuer", "issued", "verified")
        self.evidence_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        for c in cols:
            self.evidence_tree.heading(c, text=c.title())
            self.evidence_tree.column(c, width=160)
        self.evidence_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _refresh_evidence(self):
        for row in self.evidence_tree.get_children():
            self.evidence_tree.delete(row)
        if not self.service:
            return
        try:
            cid = int(self.evidence_claim_var.get().strip())
        except ValueError:
            return
        for ev in self.service.list_evidence(cid):
            self.evidence_tree.insert("", tk.END, values=(
                ev["id"], ev.get("evidence_type", ""), ev.get("title", ""),
                ev.get("issuing_body", ""), ev.get("issue_date", ""),
                "yes" if ev.get("verified") else "no",
            ))

    def _add_evidence(self):
        try:
            cid = int(self.evidence_claim_var.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Enter a claim ID first.")
            return
        if not self.service:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Add Evidence")
        dlg.geometry("500x420")
        dlg.transient(self.root)
        dlg.grab_set()

        rows = [
            ("Title:", "title", "entry"),
            ("Type:", "evidence_type", "entry"),
            ("Issuing body:", "issuing_body", "entry"),
            ("Issue date (YYYY-MM-DD):", "issue_date", "entry"),
            ("File path:", "file_path", "entry"),
            ("Description:", "description", "text"),
        ]
        widgets = {}
        for i, (label, key, kind) in enumerate(rows):
            ttk.Label(dlg, text=label).grid(row=i, column=0, sticky=tk.W, padx=10, pady=4)
            w = tk.Text(dlg, width=38, height=4) if kind == "text" else ttk.Entry(dlg, width=40)
            w.grid(row=i, column=1, padx=10, pady=4)
            widgets[key] = w

        def save():
            vals = {}
            for k, w in widgets.items():
                if isinstance(w, tk.Text):
                    vals[k] = w.get("1.0", tk.END).strip() or None
                else:
                    vals[k] = w.get().strip() or None
            if not vals.get("title"):
                messagebox.showerror("Error", "Title required.")
                return
            self.service.add_evidence(
                cid,
                title=vals["title"],
                evidence_type=vals.get("evidence_type"),
                description=vals.get("description"),
                file_path=vals.get("file_path"),
                issuing_body=vals.get("issuing_body"),
                issue_date=vals.get("issue_date"),
            )
            dlg.destroy()
            self._refresh_evidence()

        btn_row = ttk.Frame(dlg)
        btn_row.grid(row=len(rows), column=0, columnspan=2, pady=10)
        ttk.Button(btn_row, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT, padx=5)

    def _verify_evidence(self):
        sel = self.evidence_tree.selection()
        if not sel or not self.service:
            return
        eid = int(self.evidence_tree.item(sel[0], "values")[0])
        self.service.verify_evidence(eid, verified_by=self._current_user())
        self._refresh_evidence()

    # --------------------------------------------------------------- awards
    def _build_awards_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Credit Awards")

        top = ttk.Frame(tab)
        top.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(top, text="Claim ID:").pack(side=tk.LEFT, padx=4)
        self.awards_claim_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.awards_claim_var, width=10).pack(side=tk.LEFT)
        ttk.Button(top, text="Load", command=self._refresh_awards).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Award Credits", command=self._award_credits).pack(side=tk.LEFT, padx=4)

        cols = ("id", "module_code", "module_name", "level", "credits", "grade", "awarded_by")
        self.awards_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        for c in cols:
            self.awards_tree.heading(c, text=c.replace("_", " ").title())
            self.awards_tree.column(c, width=140)
        self.awards_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _refresh_awards(self):
        for row in self.awards_tree.get_children():
            self.awards_tree.delete(row)
        if not self.service:
            return
        try:
            cid = int(self.awards_claim_var.get().strip())
        except ValueError:
            return
        for aw in self.service.list_awards(cid):
            self.awards_tree.insert("", tk.END, values=(
                aw["id"], aw.get("module_code", ""), aw.get("module_name", ""),
                aw.get("level", ""), aw.get("credits_awarded", 0),
                aw.get("grade", ""), aw.get("awarded_by", ""),
            ))

    def _award_credits(self):
        try:
            cid = int(self.awards_claim_var.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Enter a claim ID first.")
            return
        if not self.service:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Award Credits")
        dlg.geometry("460x380")
        dlg.transient(self.root)
        dlg.grab_set()

        rows = [
            ("Module code:", "module_code"),
            ("Module name:", "module_name"),
            ("Level (4/5/6/7):", "level"),
            ("Credits awarded:", "credits_awarded"),
            ("Grade:", "grade"),
            ("Notes:", "notes"),
        ]
        widgets = {}
        for i, (label, key) in enumerate(rows):
            ttk.Label(dlg, text=label).grid(row=i, column=0, sticky=tk.W, padx=10, pady=6)
            e = ttk.Entry(dlg, width=36)
            e.grid(row=i, column=1, padx=10, pady=6)
            widgets[key] = e

        def save():
            try:
                credits = int(widgets["credits_awarded"].get().strip())
            except ValueError:
                messagebox.showerror("Error", "Credits must be an integer.")
                return
            try:
                level = int(widgets["level"].get().strip()) if widgets["level"].get().strip() else None
            except ValueError:
                level = None
            self.service.award_credits(
                cid,
                credits_awarded=credits,
                module_code=widgets["module_code"].get().strip() or None,
                module_name=widgets["module_name"].get().strip() or None,
                level=level,
                grade=widgets["grade"].get().strip() or None,
                awarded_by=self._current_user(),
                notes=widgets["notes"].get().strip() or None,
            )
            dlg.destroy()
            self._refresh_awards()
            self._refresh_claims()

        btn_row = ttk.Frame(dlg)
        btn_row.grid(row=len(rows), column=0, columnspan=2, pady=10)
        ttk.Button(btn_row, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT, padx=5)

    # ---------------------------------------------------------------- stats
    def _build_stats_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Statistics")

        self.stats_text = tk.Text(tab, wrap=tk.WORD, height=30)
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Button(tab, text="Refresh", command=self._refresh_stats).pack(pady=5)
        self._refresh_stats()

    def _refresh_stats(self):
        self.stats_text.delete("1.0", tk.END)
        if not self.service:
            self.stats_text.insert(tk.END, "Service unavailable.\n")
            return
        s = self.service.get_statistics()
        lines = [
            f"Total claims:        {s['total_claims']}",
            f"Credits requested:   {s['credits_requested']}",
            f"Credits awarded:     {s['credits_awarded']}",
            f"Approval rate:       {s['approval_rate_pct']}%",
            "",
            "By status:",
        ]
        for k, v in s.get("by_status", {}).items():
            lines.append(f"  {k}: {v}")
        lines.append("")
        lines.append("By type:")
        for k, v in s.get("by_type", {}).items():
            lines.append(f"  {k}: {v}")
        self.stats_text.insert(tk.END, "\n".join(lines))


def launch(parent=None):
    return PriorLearningGUI(parent=parent)


if __name__ == "__main__":
    app = PriorLearningGUI()
    if hasattr(app.root, "mainloop"):
        app.root.mainloop()
