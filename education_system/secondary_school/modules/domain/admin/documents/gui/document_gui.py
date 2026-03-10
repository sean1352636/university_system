"""Document Store GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.admin.documents.services.document_service import (
    DocumentService, DOC_CATEGORIES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class DocumentFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = DocumentService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Document Store", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Add Document", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Acknowledge", command=self._on_acknowledge).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)
        tk.Label(toolbar, text="Category:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._cat_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._cat_var,
                     values=["All"] + list(DOC_CATEGORIES), state="readonly", width=14).pack(side="left")
        self._cat_var.trace_add("write", lambda *_: self._load())

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("title", "category", "filename", "version", "uploaded_by", "ack_req", "ack_count", "date")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("title", "Title", 160), ("category", "Category", 90),
                           ("filename", "Filename", 120), ("version", "Ver", 35),
                           ("uploaded_by", "By", 80), ("ack_req", "Ack Req", 50),
                           ("ack_count", "Acks", 40), ("date", "Date", 110)]:
            self._tree.heading(col, text=h)
            self._tree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load()

    def _load(self):
        self._tree.delete(*self._tree.get_children())
        cat = self._cat_var.get()
        try:
            docs = self._svc.list_documents(category=cat if cat != "All" else None)
            for d in docs:
                ack_cnt = self._svc.acknowledgement_count(d["id"])
                self._tree.insert("", "end", iid=d["id"], values=(
                    d["title"], d["category"], d["filename"], d.get("version") or "",
                    d.get("uploaded_by") or "", "Yes" if d["requires_acknowledgement"] else "No",
                    ack_cnt, d["created_at"][:16] if d.get("created_at") else ""))
            self._status_var.set(f"{len(docs)} document(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add Document")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        fields = [("Title", "title", "", None), ("Category", "category", "policy", list(DOC_CATEGORIES)),
                  ("Filename", "filename", "", None), ("File Path", "file_path", "", None),
                  ("Description", "description", "", None), ("Version", "version", "1.0", None)]
        for row, (l, k, d, vals) in enumerate(fields):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=22).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=25).grid(row=row, column=1, **pad)
        row = len(fields)
        vars_["ack"] = tk.BooleanVar()
        ttk.Checkbutton(c, text="Requires Acknowledgement", variable=vars_["ack"]).grid(row=row, column=1, sticky="w", **pad)
        result = [None]
        def save():
            t = vars_["title"].get().strip()
            fn = vars_["filename"].get().strip()
            fp = vars_["file_path"].get().strip()
            if not t or not fn or not fp:
                messagebox.showwarning("Validation", "Title, filename and file path required.")
                return
            result[0] = {k: v.get().strip() if isinstance(v, tk.StringVar) else v.get() for k, v in vars_.items()}
            dlg.destroy()
        ttk.Button(c, text="Save", command=save).grid(row=row + 1, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        uploaded_by = self._auth.get("username") if self._auth else None
        try:
            self._svc.add_document(d["title"], d["filename"], d["file_path"],
                                   d.get("category") or "policy", d.get("description") or None,
                                   uploaded_by, d.get("version") or "1.0", d.get("ack", False))
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_acknowledge(self):
        sel = self._tree.selection()
        if not sel:
            return
        user_id = self._auth.get("user_id") if self._auth else None
        if not user_id:
            messagebox.showwarning("Error", "User ID not available.")
            return
        try:
            self._svc.acknowledge(int(sel[0]), user_id)
            messagebox.showinfo("Done", "Document acknowledged.")
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this document?"):
            self._svc.delete_document(int(sel[0]))
            self._load()
