"""GUI for self-serve enrolment verification / status letters."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from education_system.systems.university.domain.pastoral.student_app.documentation.services.documentation_service import (
    DocumentationService,
    LETTER_TYPES,
)

logger = logging.getLogger(__name__)


class DocumentationGUI:
    """Tk window for requesting, viewing, and verifying enrolment letters.

    Layout follows the repo convention used by Finance / Library /
    Student App: 1400x900 with a 1200x800 minsize and a top-level
    notebook with one tab per workflow."""

    def __init__(self, parent=None, auth=None, prefill_student_id=None,
                 prefill_letter_type=None, prefill_purpose=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("Enrolment Verification & Status Letters")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        self.auth = auth
        self._prefill_student_id = prefill_student_id
        self._prefill_letter_type = prefill_letter_type
        self._prefill_purpose = prefill_purpose
        if not self.auth:
            try:
                from education_system.systems.university.infrastructure.shared_context import (
                    get_auth,
                )

                self.auth = get_auth()
            except Exception:
                pass

        self.student_id = self._resolve_student_id()
        self.is_staff = self._is_staff()
        try:
            self.service = DocumentationService()
        except Exception as exc:
            logger.error("DocumentationService init failed: %s", exc)
            messagebox.showerror("Error", f"Failed to load documentation service: {exc}")
            self.service = None
            return

        self._build_ui()

    # ---------------------------------------------------------------- helpers
    def _resolve_student_id(self) -> str:
        if self._prefill_student_id:
            return self._prefill_student_id
        if (
            self.auth
            and getattr(self.auth, "current_user", None)
            and isinstance(self.auth.current_user, dict)
        ):
            user = self.auth.current_user
            return user.get("student_id") or user.get("username") or "unknown"
        return "unknown"

    def _is_staff(self) -> bool:
        if (
            self.auth
            and getattr(self.auth, "current_user", None)
            and isinstance(self.auth.current_user, dict)
        ):
            role = (self.auth.current_user.get("role") or "").lower()
            return role in {"admin", "staff", "registrar", "manager"}
        return False

    def _approver_username(self) -> str:
        if (
            self.auth
            and getattr(self.auth, "current_user", None)
            and isinstance(self.auth.current_user, dict)
        ):
            return self.auth.current_user.get("username") or "unknown"
        return "unknown"

    # ---------------------------------------------------------------------- UI
    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._build_request_tab(notebook)
        self._build_my_requests_tab(notebook)
        self._build_my_letters_tab(notebook)
        self._build_verify_tab(notebook)
        if self.is_staff:
            self._build_review_tab(notebook)

    # ----- request tab
    def _build_request_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=20)
        notebook.add(frame, text="Request Letter")

        ttk.Label(
            frame,
            text="Request a self-serve enrolment / proof-of-study letter",
            font=("", 14, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))

        ttk.Label(frame, text="Letter type:").grid(row=1, column=0, sticky="w", pady=4)
        self.letter_type_var = tk.StringVar()
        self.letter_type_combo = ttk.Combobox(
            frame,
            textvariable=self.letter_type_var,
            state="readonly",
            width=50,
            values=[f"{key} — {label}" for key, label in LETTER_TYPES.items()],
        )
        self.letter_type_combo.grid(row=1, column=1, sticky="we", pady=4)
        self.letter_type_combo.current(0)

        ttk.Label(frame, text="Purpose:").grid(row=2, column=0, sticky="nw", pady=4)
        self.purpose_text = tk.Text(frame, height=3, width=50)
        self.purpose_text.grid(row=2, column=1, sticky="we", pady=4)

        ttk.Label(frame, text="Recipient name:").grid(row=3, column=0, sticky="w", pady=4)
        self.recipient_name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.recipient_name_var, width=52).grid(
            row=3, column=1, sticky="we", pady=4
        )

        ttk.Label(frame, text="Recipient address:").grid(row=4, column=0, sticky="nw", pady=4)
        self.recipient_addr_text = tk.Text(frame, height=4, width=50)
        self.recipient_addr_text.grid(row=4, column=1, sticky="we", pady=4)

        ttk.Button(frame, text="Submit request", command=self._submit_request).grid(
            row=5, column=1, sticky="e", pady=15
        )
        frame.columnconfigure(1, weight=1)

        if self._prefill_letter_type and self._prefill_letter_type in LETTER_TYPES:
            keys = list(LETTER_TYPES.keys())
            self.letter_type_combo.current(keys.index(self._prefill_letter_type))
        if self._prefill_purpose:
            self.purpose_text.insert("1.0", self._prefill_purpose)

    def _submit_request(self):
        try:
            sel = self.letter_type_var.get()
            letter_type = sel.split(" — ", 1)[0] if sel else "general"
            purpose = self.purpose_text.get("1.0", "end").strip() or None
            name = self.recipient_name_var.get().strip() or None
            addr = self.recipient_addr_text.get("1.0", "end").strip() or None
            request_id = self.service.submit_request(
                student_id=self.student_id,
                letter_type=letter_type,
                purpose=purpose,
                recipient_name=name,
                recipient_address=addr,
            )
            messagebox.showinfo(
                "Submitted",
                f"Request #{request_id} submitted. The registry will review and issue.",
            )
            self.purpose_text.delete("1.0", "end")
            self.recipient_name_var.set("")
            self.recipient_addr_text.delete("1.0", "end")
            self._refresh_my_requests()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to submit request: {exc}")

    # ----- my requests tab
    def _build_my_requests_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="My Requests")

        cols = ("id", "type", "status", "requested", "decided_by", "letter_id")
        self.req_tree = ttk.Treeview(frame, columns=cols, show="headings", height=20)
        for col, width in zip(cols, (60, 140, 100, 160, 120, 90)):
            self.req_tree.heading(col, text=col.replace("_", " ").title())
            self.req_tree.column(col, width=width, anchor="w")
        self.req_tree.pack(fill=tk.BOTH, expand=True)
        ttk.Button(frame, text="Refresh", command=self._refresh_my_requests).pack(
            anchor="e", pady=8
        )
        self._refresh_my_requests()

    def _refresh_my_requests(self):
        if not hasattr(self, "req_tree"):
            return
        for item in self.req_tree.get_children():
            self.req_tree.delete(item)
        for r in self.service.list_requests(student_id=self.student_id):
            self.req_tree.insert(
                "",
                "end",
                values=(
                    r["id"],
                    r["letter_type"],
                    r["status"],
                    (r.get("requested_at") or "")[:19],
                    r.get("decided_by") or "",
                    r.get("letter_id") or "",
                ),
            )

    # ----- my letters tab
    def _build_my_letters_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="My Letters")

        top = ttk.Frame(frame)
        top.pack(fill=tk.X)
        cols = ("id", "reference", "type", "issued", "valid_until", "revoked")
        self.letter_tree = ttk.Treeview(top, columns=cols, show="headings", height=10)
        for col, width in zip(cols, (60, 180, 140, 140, 120, 80)):
            self.letter_tree.heading(col, text=col.replace("_", " ").title())
            self.letter_tree.column(col, width=width, anchor="w")
        self.letter_tree.pack(fill=tk.X)
        self.letter_tree.bind("<<TreeviewSelect>>", self._on_letter_select)

        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=6)
        ttk.Button(btns, text="Refresh", command=self._refresh_my_letters).pack(
            side=tk.RIGHT
        )
        ttk.Button(btns, text="Save as .txt", command=self._save_letter).pack(
            side=tk.RIGHT, padx=6
        )
        if self.is_staff:
            ttk.Button(btns, text="Revoke Letter", command=self._revoke_letter).pack(
                side=tk.LEFT
            )

        ttk.Label(frame, text="Letter content:").pack(anchor="w")
        self.letter_view = tk.Text(frame, wrap="word")
        self.letter_view.pack(fill=tk.BOTH, expand=True)

        self._refresh_my_letters()

    def _refresh_my_letters(self):
        if not hasattr(self, "letter_tree"):
            return
        for item in self.letter_tree.get_children():
            self.letter_tree.delete(item)
        for r in self.service.list_letters(self.student_id):
            self.letter_tree.insert(
                "",
                "end",
                values=(
                    r["id"],
                    r["reference_code"],
                    r["letter_type"],
                    (r.get("issued_at") or "")[:19],
                    r.get("valid_until") or "",
                    "yes" if r["revoked"] else "no",
                ),
            )
        self.letter_view.delete("1.0", "end")

    def _on_letter_select(self, _event):
        sel = self.letter_tree.selection()
        if not sel:
            return
        letter_id = int(self.letter_tree.item(sel[0])["values"][0])
        letter = self.service.get_letter(letter_id)
        self.letter_view.delete("1.0", "end")
        if letter:
            self.letter_view.insert(
                "1.0",
                letter["content"]
                + f"\n\nVerification token: {letter['verification_token']}\n",
            )

    def _save_letter(self):
        content = self.letter_view.get("1.0", "end").strip()
        if not content:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt")],
            title="Save letter as",
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(content)
                messagebox.showinfo("Saved", f"Saved to {path}")
            except OSError as exc:
                messagebox.showerror("Error", f"Could not save: {exc}")

    def _revoke_letter(self):
        sel = self.letter_tree.selection()
        if not sel:
            messagebox.showwarning("Select letter", "Pick an issued letter first.")
            return
        letter_id = int(self.letter_tree.item(sel[0])["values"][0])
        reason = self._prompt("Revoke letter", "Reason for revoking this letter:")
        if reason is None:
            return
        if self.service.revoke_letter(letter_id, reason):
            messagebox.showinfo("Revoked", f"Letter #{letter_id} revoked.")
            self._refresh_my_letters()
        else:
            messagebox.showerror("Error", "Letter not found.")

    # ----- verify tab
    def _build_verify_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=20)
        notebook.add(frame, text="Verify a Letter")

        ttk.Label(
            frame,
            text="Third-party verification — confirm a letter is genuine",
            font=("", 13, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text="Reference code or token:").pack(side=tk.LEFT)
        self.verify_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.verify_var, width=50).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(row, text="Verify", command=self._verify_letter).pack(side=tk.LEFT)

        self.verify_result = tk.Text(frame, height=12, wrap="word")
        self.verify_result.pack(fill=tk.BOTH, expand=True, pady=10)

    def _verify_letter(self):
        token = self.verify_var.get().strip()
        self.verify_result.delete("1.0", "end")
        if not token:
            return
        result = self.service.verify_letter(token)
        if not result:
            self.verify_result.insert(
                "1.0", "Not recognised. This letter cannot be verified.\n"
            )
            return
        for key, value in result.items():
            if value in (None, ""):
                continue
            self.verify_result.insert("end", f"{key}: {value}\n")

    # ----- staff review tab
    def _build_review_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Registry Review")

        cols = ("id", "student", "type", "purpose", "requested")
        self.pending_tree = ttk.Treeview(frame, columns=cols, show="headings", height=18)
        for col, width in zip(cols, (60, 120, 140, 360, 160)):
            self.pending_tree.heading(col, text=col.title())
            self.pending_tree.column(col, width=width, anchor="w")
        self.pending_tree.pack(fill=tk.BOTH, expand=True)

        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=8)
        ttk.Button(btns, text="Approve & Issue", command=self._staff_approve).pack(
            side=tk.LEFT
        )
        ttk.Button(btns, text="Reject", command=self._staff_reject).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(btns, text="Refresh", command=self._refresh_pending).pack(
            side=tk.RIGHT
        )
        self._refresh_pending()

    def _refresh_pending(self):
        for item in self.pending_tree.get_children():
            self.pending_tree.delete(item)
        for r in self.service.list_requests(status="pending"):
            self.pending_tree.insert(
                "",
                "end",
                values=(
                    r["id"],
                    r["student_id"],
                    r["letter_type"],
                    (r.get("purpose") or "")[:80],
                    (r.get("requested_at") or "")[:19],
                ),
            )

    def _selected_pending_id(self):
        sel = self.pending_tree.selection()
        if not sel:
            messagebox.showwarning("Select request", "Pick a pending request first.")
            return None
        return int(self.pending_tree.item(sel[0])["values"][0])

    def _staff_approve(self):
        request_id = self._selected_pending_id()
        if request_id is None:
            return
        try:
            letter = self.service.approve_request(request_id, self._approver_username())
            messagebox.showinfo(
                "Issued", f"Issued letter {letter['reference_code']} (#{letter['id']})."
            )
            self._refresh_pending()
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))

    def _staff_reject(self):
        request_id = self._selected_pending_id()
        if request_id is None:
            return
        reason = self._prompt("Rejection reason", "Reason for rejecting this request:")
        if reason is None:
            return
        if self.service.reject_request(request_id, self._approver_username(), reason):
            messagebox.showinfo("Rejected", "Request rejected.")
            self._refresh_pending()
        else:
            messagebox.showerror("Error", "Could not reject (no longer pending?).")

    def _prompt(self, title: str, message: str):
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.transient(self.root)
        dlg.grab_set()
        ttk.Label(dlg, text=message).pack(padx=15, pady=10)
        var = tk.StringVar()
        ttk.Entry(dlg, textvariable=var, width=50).pack(padx=15, pady=5)
        out = {"value": None}

        def ok():
            out["value"] = var.get().strip() or "Not specified"
            dlg.destroy()

        def cancel():
            dlg.destroy()

        row = ttk.Frame(dlg)
        row.pack(pady=10)
        ttk.Button(row, text="OK", command=ok).pack(side=tk.LEFT, padx=6)
        ttk.Button(row, text="Cancel", command=cancel).pack(side=tk.LEFT, padx=6)
        self.root.wait_window(dlg)
        return out["value"]
