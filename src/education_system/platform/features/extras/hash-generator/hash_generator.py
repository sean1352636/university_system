"""
Hash Generator Utility
=====================
Generate and verify cryptographic hashes for text and files.
Supports MD5, SHA1, SHA256, SHA512 with batch processing and history.
"""

import hashlib
import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime


class HashGeneratorApp(tk.Tk):
    """Main application for generating and verifying cryptographic hashes."""

    ALGORITHMS = ["MD5", "SHA1", "SHA256", "SHA512"]
    CHUNK_SIZE = 8192

    def __init__(self):
        super().__init__()
        self.title("Hash Generator")
        self.geometry("900x700")
        self.minsize(800, 600)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Hash.TEntry", font=("Consolas", 10))
        style.configure("Green.TLabel", foreground="green", font=("Segoe UI", 10, "bold"))
        style.configure("Red.TLabel", foreground="red", font=("Segoe UI", 10, "bold"))

        self.history = []
        self.batch_files = []

        self._build_ui()

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.text_tab = ttk.Frame(notebook, padding=10)
        self.file_tab = ttk.Frame(notebook, padding=10)
        self.verify_tab = ttk.Frame(notebook, padding=10)
        self.batch_tab = ttk.Frame(notebook, padding=10)
        self.history_tab = ttk.Frame(notebook, padding=10)

        notebook.add(self.text_tab, text="  Text Hash  ")
        notebook.add(self.file_tab, text="  File Hash  ")
        notebook.add(self.verify_tab, text="  Verify  ")
        notebook.add(self.batch_tab, text="  Batch  ")
        notebook.add(self.history_tab, text="  History  ")

        self._build_text_tab()
        self._build_file_tab()
        self._build_verify_tab()
        self._build_batch_tab()
        self._build_history_tab()

    # ── Text Hash Tab ──────────────────────────────────────────────
    def _build_text_tab(self):
        f = self.text_tab
        ttk.Label(f, text="Hash Text Input", style="Title.TLabel").pack(anchor="w")
        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=(4, 10))

        ttk.Label(f, text="Enter text to hash:", style="Section.TLabel").pack(anchor="w")
        self.text_input = tk.Text(f, height=6, wrap="word", font=("Consolas", 10))
        self.text_input.pack(fill="x", pady=(4, 8))

        algo_frame = ttk.Frame(f)
        algo_frame.pack(fill="x", pady=4)
        ttk.Label(algo_frame, text="Algorithm:").pack(side="left")
        self.text_algo = ttk.Combobox(algo_frame, values=self.ALGORITHMS, state="readonly", width=12)
        self.text_algo.set("SHA256")
        self.text_algo.pack(side="left", padx=8)

        ttk.Label(algo_frame, text="Encoding:").pack(side="left", padx=(16, 0))
        self.text_encoding = ttk.Combobox(algo_frame, values=["utf-8", "ascii", "latin-1"], state="readonly", width=10)
        self.text_encoding.set("utf-8")
        self.text_encoding.pack(side="left", padx=8)

        btn_frame = ttk.Frame(f)
        btn_frame.pack(fill="x", pady=4)
        ttk.Button(btn_frame, text="Generate Hash", command=self._hash_text).pack(side="left")
        ttk.Button(btn_frame, text="Generate All", command=self._hash_text_all).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="Clear", command=self._clear_text).pack(side="left")

        ttk.Label(f, text="Result:", style="Section.TLabel").pack(anchor="w", pady=(10, 4))
        self.text_result = tk.Text(f, height=8, wrap="word", font=("Consolas", 10), state="disabled",
                                   bg="#f5f5f5")
        self.text_result.pack(fill="both", expand=True, pady=(0, 4))

        ttk.Button(f, text="Copy to Clipboard", command=lambda: self._copy(self.text_result)).pack(anchor="e")

    def _hash_text(self):
        text = self.text_input.get("1.0", "end-1c")
        if not text:
            messagebox.showwarning("Warning", "Please enter text to hash.")
            return
        algo = self.text_algo.get()
        encoding = self.text_encoding.get()
        try:
            data = text.encode(encoding)
        except UnicodeEncodeError as e:
            messagebox.showerror("Encoding Error", str(e))
            return
        h = hashlib.new(algo.lower().replace("sha", "sha"))
        # Fix algorithm name mapping
        algo_map = {"MD5": "md5", "SHA1": "sha1", "SHA256": "sha256", "SHA512": "sha512"}
        h = hashlib.new(algo_map[algo])
        h.update(data)
        digest = h.hexdigest()
        self._show_result(self.text_result, f"{algo}: {digest}")
        self._add_history("Text", algo, digest, text[:60])

    def _hash_text_all(self):
        text = self.text_input.get("1.0", "end-1c")
        if not text:
            messagebox.showwarning("Warning", "Please enter text to hash.")
            return
        encoding = self.text_encoding.get()
        try:
            data = text.encode(encoding)
        except UnicodeEncodeError as e:
            messagebox.showerror("Encoding Error", str(e))
            return
        lines = []
        algo_map = {"MD5": "md5", "SHA1": "sha1", "SHA256": "sha256", "SHA512": "sha512"}
        for algo in self.ALGORITHMS:
            h = hashlib.new(algo_map[algo])
            h.update(data)
            digest = h.hexdigest()
            lines.append(f"{algo:>6}: {digest}")
            self._add_history("Text", algo, digest, text[:60])
        self._show_result(self.text_result, "\n".join(lines))

    def _clear_text(self):
        self.text_input.delete("1.0", "end")
        self._show_result(self.text_result, "")

    # ── File Hash Tab ──────────────────────────────────────────────
    def _build_file_tab(self):
        f = self.file_tab
        ttk.Label(f, text="Hash File", style="Title.TLabel").pack(anchor="w")
        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=(4, 10))

        sel_frame = ttk.Frame(f)
        sel_frame.pack(fill="x", pady=4)
        ttk.Label(sel_frame, text="File:").pack(side="left")
        self.file_path_var = tk.StringVar()
        ttk.Entry(sel_frame, textvariable=self.file_path_var, state="readonly").pack(side="left", fill="x",
                                                                                      expand=True, padx=8)
        ttk.Button(sel_frame, text="Browse...", command=self._browse_file).pack(side="left")

        algo_frame = ttk.Frame(f)
        algo_frame.pack(fill="x", pady=4)
        ttk.Label(algo_frame, text="Algorithm:").pack(side="left")
        self.file_algo = ttk.Combobox(algo_frame, values=self.ALGORITHMS, state="readonly", width=12)
        self.file_algo.set("SHA256")
        self.file_algo.pack(side="left", padx=8)

        btn_frame = ttk.Frame(f)
        btn_frame.pack(fill="x", pady=4)
        ttk.Button(btn_frame, text="Generate Hash", command=self._hash_file).pack(side="left")
        ttk.Button(btn_frame, text="Generate All", command=self._hash_file_all).pack(side="left", padx=8)

        ttk.Label(f, text="Result:", style="Section.TLabel").pack(anchor="w", pady=(10, 4))
        self.file_result = tk.Text(f, height=10, wrap="word", font=("Consolas", 10), state="disabled",
                                   bg="#f5f5f5")
        self.file_result.pack(fill="both", expand=True, pady=(0, 4))

        ttk.Button(f, text="Copy to Clipboard", command=lambda: self._copy(self.file_result)).pack(anchor="e")

    def _browse_file(self):
        path = filedialog.askopenfilename(title="Select File")
        if path:
            self.file_path_var.set(path)

    def _hash_file(self):
        path = self.file_path_var.get()
        if not path or not os.path.isfile(path):
            messagebox.showwarning("Warning", "Please select a valid file.")
            return
        algo = self.file_algo.get()
        digest = self._compute_file_hash(path, algo)
        if digest:
            size = os.path.getsize(path)
            name = os.path.basename(path)
            self._show_result(self.file_result,
                              f"File: {name}\nSize: {size:,} bytes\n\n{algo}: {digest}")
            self._add_history("File", algo, digest, name)

    def _hash_file_all(self):
        path = self.file_path_var.get()
        if not path or not os.path.isfile(path):
            messagebox.showwarning("Warning", "Please select a valid file.")
            return
        size = os.path.getsize(path)
        name = os.path.basename(path)
        lines = [f"File: {name}", f"Size: {size:,} bytes", ""]
        for algo in self.ALGORITHMS:
            digest = self._compute_file_hash(path, algo)
            if digest:
                lines.append(f"{algo:>6}: {digest}")
                self._add_history("File", algo, digest, name)
        self._show_result(self.file_result, "\n".join(lines))

    def _compute_file_hash(self, path, algo):
        algo_map = {"MD5": "md5", "SHA1": "sha1", "SHA256": "sha256", "SHA512": "sha512"}
        try:
            h = hashlib.new(algo_map[algo])
            with open(path, "rb") as fh:
                while True:
                    chunk = fh.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except OSError as e:
            messagebox.showerror("File Error", str(e))
            return None

    # ── Verify Tab ─────────────────────────────────────────────────
    def _build_verify_tab(self):
        f = self.verify_tab
        ttk.Label(f, text="Verify File Integrity", style="Title.TLabel").pack(anchor="w")
        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=(4, 10))

        sel_frame = ttk.Frame(f)
        sel_frame.pack(fill="x", pady=4)
        ttk.Label(sel_frame, text="File:").pack(side="left")
        self.verify_path_var = tk.StringVar()
        ttk.Entry(sel_frame, textvariable=self.verify_path_var, state="readonly").pack(side="left", fill="x",
                                                                                        expand=True, padx=8)
        ttk.Button(sel_frame, text="Browse...", command=self._browse_verify).pack(side="left")

        algo_frame = ttk.Frame(f)
        algo_frame.pack(fill="x", pady=4)
        ttk.Label(algo_frame, text="Algorithm:").pack(side="left")
        self.verify_algo = ttk.Combobox(algo_frame, values=self.ALGORITHMS, state="readonly", width=12)
        self.verify_algo.set("SHA256")
        self.verify_algo.pack(side="left", padx=8)

        hash_frame = ttk.Frame(f)
        hash_frame.pack(fill="x", pady=4)
        ttk.Label(hash_frame, text="Expected Hash:").pack(side="left")
        self.verify_hash_var = tk.StringVar()
        ttk.Entry(hash_frame, textvariable=self.verify_hash_var, font=("Consolas", 10)).pack(
            side="left", fill="x", expand=True, padx=8)

        ttk.Button(f, text="Verify", command=self._verify_hash).pack(anchor="w", pady=8)

        self.verify_status = ttk.Label(f, text="", font=("Segoe UI", 12, "bold"))
        self.verify_status.pack(anchor="w", pady=4)

        ttk.Label(f, text="Computed Hash:", style="Section.TLabel").pack(anchor="w", pady=(10, 4))
        self.verify_result = tk.Text(f, height=4, wrap="word", font=("Consolas", 10), state="disabled",
                                     bg="#f5f5f5")
        self.verify_result.pack(fill="x")

    def _browse_verify(self):
        path = filedialog.askopenfilename(title="Select File to Verify")
        if path:
            self.verify_path_var.set(path)

    def _verify_hash(self):
        path = self.verify_path_var.get()
        expected = self.verify_hash_var.get().strip().lower()
        algo = self.verify_algo.get()
        if not path or not os.path.isfile(path):
            messagebox.showwarning("Warning", "Please select a valid file.")
            return
        if not expected:
            messagebox.showwarning("Warning", "Please enter the expected hash.")
            return
        computed = self._compute_file_hash(path, algo)
        if computed:
            self._show_result(self.verify_result, computed)
            if computed == expected:
                self.verify_status.config(text="MATCH — File integrity verified", style="Green.TLabel")
            else:
                self.verify_status.config(text="MISMATCH — File may be altered", style="Red.TLabel")

    # ── Batch Tab ──────────────────────────────────────────────────
    def _build_batch_tab(self):
        f = self.batch_tab
        ttk.Label(f, text="Batch Hash Files", style="Title.TLabel").pack(anchor="w")
        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=(4, 10))

        btn_frame = ttk.Frame(f)
        btn_frame.pack(fill="x", pady=4)
        ttk.Button(btn_frame, text="Add Files...", command=self._batch_add).pack(side="left")
        ttk.Button(btn_frame, text="Clear List", command=self._batch_clear).pack(side="left", padx=8)

        algo_frame = ttk.Frame(f)
        algo_frame.pack(fill="x", pady=4)
        ttk.Label(algo_frame, text="Algorithm:").pack(side="left")
        self.batch_algo = ttk.Combobox(algo_frame, values=self.ALGORITHMS, state="readonly", width=12)
        self.batch_algo.set("SHA256")
        self.batch_algo.pack(side="left", padx=8)
        ttk.Button(algo_frame, text="Hash All", command=self._batch_hash).pack(side="left", padx=8)
        ttk.Button(algo_frame, text="Export Results", command=self._batch_export).pack(side="left")

        cols = ("file", "size", "hash")
        self.batch_tree = ttk.Treeview(f, columns=cols, show="headings", height=15)
        self.batch_tree.heading("file", text="File Name")
        self.batch_tree.heading("size", text="Size")
        self.batch_tree.heading("hash", text="Hash")
        self.batch_tree.column("file", width=250)
        self.batch_tree.column("size", width=100)
        self.batch_tree.column("hash", width=450)

        sb = ttk.Scrollbar(f, orient="vertical", command=self.batch_tree.yview)
        self.batch_tree.configure(yscrollcommand=sb.set)
        self.batch_tree.pack(side="left", fill="both", expand=True, pady=4)
        sb.pack(side="right", fill="y", pady=4)

    def _batch_add(self):
        paths = filedialog.askopenfilenames(title="Select Files")
        for p in paths:
            if p not in self.batch_files:
                self.batch_files.append(p)
                size = os.path.getsize(p)
                self.batch_tree.insert("", "end", iid=p, values=(os.path.basename(p), f"{size:,}", ""))

    def _batch_clear(self):
        self.batch_files.clear()
        for item in self.batch_tree.get_children():
            self.batch_tree.delete(item)

    def _batch_hash(self):
        if not self.batch_files:
            messagebox.showinfo("Info", "No files added.")
            return
        algo = self.batch_algo.get()
        for p in self.batch_files:
            digest = self._compute_file_hash(p, algo)
            if digest:
                self.batch_tree.set(p, "hash", digest)
                self._add_history("Batch", algo, digest, os.path.basename(p))

    def _batch_export(self):
        children = self.batch_tree.get_children()
        if not children:
            messagebox.showinfo("Info", "Nothing to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            filetypes=[("Text files", "*.txt"), ("All", "*.*")],
                                            title="Export Batch Results")
        if path:
            algo = self.batch_algo.get()
            with open(path, "w") as fh:
                fh.write(f"Batch Hash Results — {algo}\n")
                fh.write(f"Generated: {datetime.now().isoformat()}\n")
                fh.write("=" * 80 + "\n\n")
                for item in children:
                    vals = self.batch_tree.item(item, "values")
                    fh.write(f"{vals[2]}  {vals[0]}\n")
            messagebox.showinfo("Exported", f"Results saved to {path}")

    # ── History Tab ────────────────────────────────────────────────
    def _build_history_tab(self):
        f = self.history_tab
        ttk.Label(f, text="Hash History", style="Title.TLabel").pack(anchor="w")
        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=(4, 10))

        btn_frame = ttk.Frame(f)
        btn_frame.pack(fill="x", pady=(0, 4))
        ttk.Button(btn_frame, text="Clear History", command=self._clear_history).pack(side="left")
        ttk.Button(btn_frame, text="Export History", command=self._export_history).pack(side="left", padx=8)

        cols = ("time", "type", "algo", "source", "hash")
        self.history_tree = ttk.Treeview(f, columns=cols, show="headings", height=18)
        self.history_tree.heading("time", text="Time")
        self.history_tree.heading("type", text="Type")
        self.history_tree.heading("algo", text="Algorithm")
        self.history_tree.heading("source", text="Source")
        self.history_tree.heading("hash", text="Hash")
        self.history_tree.column("time", width=140)
        self.history_tree.column("type", width=60)
        self.history_tree.column("algo", width=70)
        self.history_tree.column("source", width=180)
        self.history_tree.column("hash", width=400)

        sb = ttk.Scrollbar(f, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=sb.set)
        self.history_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _add_history(self, htype, algo, digest, source):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.history.append({"time": now, "type": htype, "algo": algo, "source": source, "hash": digest})
        self.history_tree.insert("", 0, values=(now, htype, algo, source, digest))

    def _clear_history(self):
        self.history.clear()
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

    def _export_history(self):
        if not self.history:
            messagebox.showinfo("Info", "No history to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON", "*.json"), ("All", "*.*")],
                                            title="Export History")
        if path:
            with open(path, "w") as fh:
                json.dump(self.history, fh, indent=2)
            messagebox.showinfo("Exported", f"History saved to {path}")

    # ── Helpers ────────────────────────────────────────────────────
    def _show_result(self, widget, text):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.config(state="disabled")

    def _copy(self, widget):
        text = widget.get("1.0", "end-1c").strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Copied", "Hash copied to clipboard.")


if __name__ == "__main__":
    app = HashGeneratorApp()
    app.mainloop()
