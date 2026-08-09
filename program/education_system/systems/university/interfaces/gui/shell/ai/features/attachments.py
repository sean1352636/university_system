"""Validated chatbot file attachments with optional antivirus scanning."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from tkinter import filedialog, messagebox

from education_system.paths import UNIVERSITY_CHATBOT_UPLOAD_DIR


class AttachmentsMixin:
    MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
    ALLOWED_ATTACHMENT_SUFFIXES = {
        ".pdf",
        ".txt",
        ".md",
        ".csv",
        ".docx",
        ".xlsx",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
    }
    BLOCKED_ATTACHMENT_SUFFIXES = {
        ".exe",
        ".dll",
        ".bat",
        ".cmd",
        ".com",
        ".msi",
        ".ps1",
        ".sh",
        ".js",
        ".jar",
        ".scr",
        ".vbs",
    }

    def initialize_attachments(self):
        self.pending_attachments = []

    def choose_attachment(self):
        paths = filedialog.askopenfilenames(
            parent=self.root,
            title="Attach files",
            filetypes=[
                (
                    "Supported documents",
                    "*.pdf *.txt *.md *.csv *.docx *.xlsx *.png *.jpg *.jpeg *.gif",
                )
            ],
        )
        for value in paths:
            try:
                attachment = self._validate_and_store_attachment(Path(value))
            except (ValueError, OSError) as error:
                messagebox.showerror("Attachment rejected", str(error), parent=self.root)
                continue
            if any(
                existing.get("sha256") == attachment["sha256"]
                for existing in self.pending_attachments
            ):
                messagebox.showwarning(
                    "Duplicate attachment",
                    f"{attachment['filename']} is already attached.",
                    parent=self.root,
                )
                Path(attachment["path"]).unlink(missing_ok=True)
                continue
            self.pending_attachments.append(attachment)
            self.add_chat_message(
                "System",
                f"Attached {attachment['filename']} ({attachment['scan_status']}).",
                "system",
            )
        self._update_attachment_button()

    def _validate_and_store_attachment(self, source: Path) -> dict:
        if not source.is_file():
            raise ValueError("The selected attachment is not a file.")
        suffix = source.suffix.casefold()
        if (
            suffix in self.BLOCKED_ATTACHMENT_SUFFIXES
            or suffix not in self.ALLOWED_ATTACHMENT_SUFFIXES
        ):
            raise ValueError(f'Files of type {suffix or "unknown"} are not permitted.')
        size = source.stat().st_size
        if size > self.MAX_ATTACHMENT_BYTES:
            raise ValueError("Attachments must be 10 MB or smaller.")
        if suffix in {".txt", ".md", ".csv"}:
            sample = source.read_text(encoding="utf-8", errors="ignore")[:100000].casefold()
            hostile = (
                "ignore previous instructions",
                "reveal the system prompt",
                "override your rules",
                "exfiltrate",
            )
            if any(marker in sample for marker in hostile):
                raise ValueError("The attachment contains prompt-injection-like instructions.")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        scan_status = self._scan_attachment(source)
        if scan_status == "infected":
            raise ValueError("The attachment failed the malware scan.")

        username = (
            "".join(
                c
                for c in self.current_user.get("username", "user")
                if c.isalnum() or c in ("-", "_")
            )
            or "user"
        )
        destination_dir = UNIVERSITY_CHATBOT_UPLOAD_DIR / username / self.conversation_id
        destination_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{digest[:12]}_{source.name.replace('..', '_')}"
        destination = destination_dir / safe_name
        shutil.copy2(source, destination)
        if getattr(self, "history_enabled", True):
            self.conversation_store.add_attachment(
                self.conversation_id,
                source.name,
                str(destination),
                size,
                digest,
                scan_status,
            )
        return {
            "filename": source.name,
            "path": str(destination),
            "size": size,
            "sha256": digest,
            "scan_status": scan_status,
        }

    def show_attachment_manager(self):
        import tkinter as tk
        from tkinter import ttk

        win = tk.Toplevel(self.root)
        win.title("Attachments")

        def refresh():
            # The file picker runs its own Tk event loop. The user can close the
            # attachment manager while it is open, so its widgets may no longer
            # exist when the picker returns.
            if not win.winfo_exists() or not body.winfo_exists():
                return

            for child in body.winfo_children():
                child.destroy()

            for item in self.pending_attachments:
                row = ttk.Frame(body)
                row.pack(fill=tk.X, padx=8, pady=3)
                ttk.Label(
                    row,
                    text=f"{item['filename']} — {item['scan_status']}",
                ).pack(side=tk.LEFT)
                ttk.Button(
                    row,
                    text="Remove",
                    command=lambda selected=item: remove_attachment(selected),
                ).pack(side=tk.RIGHT)
                ttk.Button(
                    row,
                    text="Preview",
                    command=lambda selected=item: self.preview_attachment(selected),
                ).pack(side=tk.RIGHT, padx=3)

        def add_files():
            self.choose_attachment()
            refresh()

        def remove_attachment(item):
            if item in self.pending_attachments:
                self.pending_attachments.remove(item)
                self._update_attachment_button()
            refresh()

        ttk.Button(win, text="Add files", command=add_files).pack(pady=8)
        body = ttk.Frame(win)
        body.pack(fill=tk.BOTH, expand=True)
        refresh()

    def preview_attachment(self, item):
        import tkinter as tk
        from tkinter import ttk

        path = Path(item["path"])
        win = tk.Toplevel(self.root)
        win.title(item["filename"])
        if path.suffix.casefold() in {".txt", ".md", ".csv"}:
            text = tk.Text(win, wrap=tk.WORD)
            text.pack(fill=tk.BOTH, expand=True)
            text.insert("1.0", path.read_text(encoding="utf-8", errors="replace")[:200000])
            text.configure(state=tk.DISABLED)
        else:
            ttk.Label(
                win,
                text=f"Preview metadata\nName: {item['filename']}\nSize: {item['size']} bytes\nSHA-256: {item['sha256']}\n{item['scan_status']}",
            ).pack(padx=20, pady=20)

    @staticmethod
    def _scan_attachment(path: Path) -> str:
        scanner = shutil.which("clamscan")
        if scanner is None:
            return "validated; antivirus unavailable"
        try:
            result = subprocess.run(
                [scanner, "--no-summary", str(path)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise ValueError("The malware scan timed out; the file was not attached.") from error
        except OSError as error:
            raise ValueError("The malware scanner could not be started.") from error
        if result.returncode == 0:
            return "malware scan passed"
        if result.returncode == 1:
            return "infected"
        raise ValueError("The malware scanner could not verify this file.")

    def _update_attachment_button(self):
        if hasattr(self, "attach_button"):
            count = len(getattr(self, "pending_attachments", []))
            self.attach_button.configure(
                text=f"Attach files ({count})" if count else "Attach files"
            )

    def consume_attachment_context(self) -> str:
        attachments = list(getattr(self, "pending_attachments", []))
        self.pending_attachments = []
        self._update_attachment_button()
        if not attachments:
            return ""
        names = ", ".join(item["filename"] for item in attachments)
        return f"\n\nAttached files available for reference: {names}"
