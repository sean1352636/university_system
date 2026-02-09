"""Cloud storage dialogs for uploading and downloading backups.

Provides UploadDialog for uploading local backups to AWS S3 cloud storage
and DownloadDialog for downloading cloud-stored backups back to the local
file system, both with progress tracking and threaded operations.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import time
import datetime
import threading

from university_system.modules.shared.gui.database.config import config
from university_system.modules.shared.gui.database.metadata import metadata_manager
from university_system.modules.shared.gui.database.operations.backup_ops import list_available_backups, upload_to_aws_s3, download_from_aws_s3


class UploadDialog:
    """Dialog for uploading backups to cloud"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Upload to Cloud")
        self.dialog.geometry("500x300")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_backups()

    def create_widgets(self):
        """Create dialog widgets"""
        # Backup selection
        select_frame = ttk.LabelFrame(self.dialog, text="Select Backup to Upload", padding=10)
        select_frame.pack(fill="x", padx=10, pady=5)

        self.backup_var = tk.StringVar()
        self.backup_combo = ttk.Combobox(select_frame, textvariable=self.backup_var,
                                        state="readonly", width=50)
        self.backup_combo.pack(fill="x", pady=5)

        # Upload options
        options_frame = ttk.LabelFrame(self.dialog, text="Upload Options", padding=10)
        options_frame.pack(fill="x", padx=10, pady=5)

        self.overwrite_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Overwrite if exists", variable=self.overwrite_var).pack(anchor="w")

        self.delete_local_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Delete local file after upload",
                       variable=self.delete_local_var).pack(anchor="w")

        # Progress
        progress_frame = ttk.LabelFrame(self.dialog, text="Upload Progress", padding=10)
        progress_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var,
                                          mode="determinate", length=400)
        self.progress_bar.pack(pady=5)

        self.status_label = ttk.Label(progress_frame, text="Ready to upload")
        self.status_label.pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        self.upload_button = ttk.Button(button_frame, text="Upload", command=self.upload)
        self.upload_button.pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side="right")

    def load_backups(self):
        """Load available backups"""
        try:
            backups = list_available_backups()
            self.backups = backups

            # Filter out already uploaded backups
            local_backups = [backup for backup in backups if not backup.get('cloud_uploaded', False)]

            backup_names = [f"{backup['date_formatted']} - {backup['filename']}"
                           for backup in local_backups]
            self.backup_combo['values'] = backup_names

            if backup_names:
                self.backup_combo.current(0)
            else:
                self.status_label.config(text="No local backups available for upload")

        except Exception as e:
            self.status_label.config(text=f"Error loading backups: {e}")

    def upload(self):
        """Upload selected backup"""
        if not self.backup_combo.get():
            messagebox.showwarning("No Selection", "Please select a backup to upload")
            return

        try:
            # Get selected backup
            index = self.backup_combo.current()
            local_backups = [b for b in self.backups if not b.get('cloud_uploaded', False)]
            backup = local_backups[index]

            # Start upload in separate thread
            self.upload_button.config(state="disabled")
            self.status_label.config(text="Starting upload...")
            self.progress_var.set(0)

            def upload_worker():
                try:
                    # Simulate upload progress
                    for i in range(101):
                        time.sleep(0.02)  # Simulate upload time
                        self.progress_var.set(i)
                        self.status_label.config(text=f"Uploading... {i}%")
                        self.dialog.update()

                    # Perform actual upload
                    success = upload_to_aws_s3(
                        backup['path'],
                        config["aws_bucket"],
                        f"backups/{backup['filename']}"
                    )

                    if success:
                        # Update metadata
                        for b in metadata_manager.metadata["backups"]:
                            if b['path'] == backup['path']:
                                b['cloud_uploaded'] = True
                                break
                        metadata_manager.save_metadata()

                        self.status_label.config(text="Upload completed successfully!")

                        if self.delete_local_var.get():
                            os.remove(backup['path'])
                            self.status_label.config(text="Upload completed, local file deleted")

                        messagebox.showinfo("Success", "Backup uploaded successfully!")
                        self.dialog.destroy()
                    else:
                        self.status_label.config(text="Upload failed")
                        messagebox.showerror("Error", "Upload failed")

                except Exception as e:
                    self.status_label.config(text=f"Upload error: {e}")
                    messagebox.showerror("Error", f"Upload failed: {e}")
                finally:
                    self.upload_button.config(state="normal")
                    self.progress_var.set(0)

            # Start upload thread
            upload_thread = threading.Thread(target=upload_worker)
            upload_thread.daemon = True
            upload_thread.start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start upload: {e}")
            self.upload_button.config(state="normal")

class DownloadDialog:
    """Dialog for downloading backups from cloud"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Download from Cloud")
        self.dialog.geometry("620x420")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.download_dir = tk.StringVar(value=config.get("backup_directory", "backups"))
        self.progress_var = tk.DoubleVar()
        self.status_text = tk.StringVar(value="Select a backup to download")
        self.cloud_backups = []

        self.create_widgets()
        self.load_backups()

    def create_widgets(self):
        """Create dialog widgets"""
        list_frame = ttk.LabelFrame(self.dialog, text="Available Cloud Backups", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("date", "type", "size", "file")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        self.tree.heading("date", text="Date")
        self.tree.heading("type", text="Type")
        self.tree.heading("size", text="Size")
        self.tree.heading("file", text="File")

        self.tree.column("date", width=150)
        self.tree.column("type", width=100)
        self.tree.column("size", width=100)
        self.tree.column("file", width=220)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        controls_frame = ttk.Frame(self.dialog)
        controls_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(controls_frame, text="Refresh", command=self.load_backups).pack(side="left")

        ttk.Label(controls_frame, text="Download to:").pack(side="left", padx=(20, 5))
        destination_entry = ttk.Entry(controls_frame, textvariable=self.download_dir, width=40)
        destination_entry.pack(side="left", padx=5)
        ttk.Button(controls_frame, text="Browse", command=self.select_destination).pack(side="left")

        progress_frame = ttk.LabelFrame(self.dialog, text="Download Status", padding=10)
        progress_frame.pack(fill="x", padx=10, pady=5)
        ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, mode="determinate").pack(fill="x", pady=5)
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_text)
        self.status_label.pack(anchor="w")

        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        self.download_button = ttk.Button(button_frame, text="Download", command=self.download)
        self.download_button.pack(side="right", padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side="right")

    def load_backups(self):
        """Load list of backups marked as uploaded to the cloud"""
        try:
            backups = list_available_backups()
            self.cloud_backups = [b for b in backups if b.get("cloud_uploaded", False)]

            for item in self.tree.get_children():
                self.tree.delete(item)

            for backup in self.cloud_backups:
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        backup.get("date_formatted", "Unknown"),
                        backup.get("backup_type", "full"),
                        backup.get("size_formatted", "0 B"),
                        backup.get("filename", "")
                    )
                )

            if not self.cloud_backups:
                self.status_text.set("No cloud backups found. Upload backups before downloading.")
            else:
                self.status_text.set("Select a backup and click Download.")
        except Exception as exc:
            self.status_text.set(f"Error loading backups: {exc}")

    def select_destination(self):
        """Choose destination directory for downloads"""
        directory = filedialog.askdirectory(initialdir=self.download_dir.get() or ".")
        if directory:
            self.download_dir.set(directory)

    def download(self):
        """Download the selected backup from cloud storage"""
        if not config.get("cloud_enabled", False):
            messagebox.showwarning("Cloud Storage", "Cloud storage is not enabled.")
            return

        if config.get("cloud_provider") != "aws":
            messagebox.showwarning("Cloud Storage", "Only AWS S3 provider is supported for downloads in this demo.")
            return

        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a cloud backup to download.")
            return

        index = self.tree.index(selection[0])
        backup = self.cloud_backups[index]

        destination_dir = self.download_dir.get().strip()
        if not destination_dir:
            messagebox.showwarning("Destination", "Please choose a destination directory.")
            return

        os.makedirs(destination_dir, exist_ok=True)
        destination_path = os.path.join(destination_dir, backup["filename"])

        if os.path.exists(destination_path):
            if not messagebox.askyesno(
                "Overwrite File",
                f"'{backup['filename']}' already exists in the destination.\nOverwrite?",
                parent=self.dialog
            ):
                return

        bucket = config.get("aws_bucket", "").strip()
        if not bucket:
            messagebox.showwarning("Cloud Storage", "AWS bucket is not configured.")
            return

        key = backup.get("cloud_key") or f"backups/{backup['filename']}"
        self.download_button.config(state="disabled")
        self.status_text.set(f"Starting download for {backup['filename']}...")
        self.progress_var.set(0)

        def update_ui(progress, text=None):
            self.progress_var.set(progress)
            if text:
                self.status_text.set(text)

        def finish(success, message):
            self.download_button.config(state="normal")
            if success:
                messagebox.showinfo("Download Complete", message, parent=self.dialog)
            else:
                messagebox.showerror("Download Failed", message, parent=self.dialog)
            self.progress_var.set(0)

        def worker():
            try:
                self.dialog.after(0, update_ui, 10, f"Downloading {backup['filename']}...")
                success = download_from_aws_s3(bucket, key, destination_path)
                if success:
                    self.dialog.after(0, update_ui, 100, "Download complete.")

                    for record in metadata_manager.metadata["backups"]:
                        if record["path"] == backup["path"]:
                            record["last_downloaded"] = datetime.datetime.now().isoformat()
                            break
                    metadata_manager.save_metadata()

                    self.dialog.after(0, finish, True, f"Backup downloaded to {destination_path}")
                else:
                    self.dialog.after(0, finish, False, "Cloud service reported a failure.")
            except Exception as exc:
                self.dialog.after(0, finish, False, f"Download failed: {exc}")

        threading.Thread(target=worker, daemon=True).start()
