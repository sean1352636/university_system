"""Cloud storage dialogs for uploading and downloading backups.

Provides UploadDialog for uploading local backups to AWS S3 cloud storage
and DownloadDialog for downloading cloud-stored backups back to the local
file system, both with progress tracking and threaded operations.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import time
import datetime
import threading

from education_system.platform.delivery.gui.tk_threads import start_thread, ui

from education_system.systems.university.shell.gui.database.config import config
from education_system.systems.university.shell.gui.database.metadata import metadata_manager
from education_system.systems.university.shell.gui.database.operations.backup_ops import list_available_backups, upload_to_aws_s3, download_from_aws_s3


class UploadDialog:
    """Dialog for uploading backups to cloud"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.database.dialogs.cloud.windows.upload_to_cloud', default="Upload to Cloud"))
        self.dialog.geometry("500x300")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_backups()

    def _post(self, callback):
        """Run *callback* on the Tk main loop, from any thread.

        The upload runs on a worker thread so the dialog stays responsive,
        but Tk is single-threaded: setting a progress variable, configuring
        a label, opening a messagebox or destroying this dialog from that
        thread is undefined behaviour. Widget work is queued for the main
        thread via ui(); dropped if the dialog has already closed.
        """
        def _run():
            if self.dialog.winfo_exists():
                callback()

        ui(self.dialog, _run)

    def create_widgets(self):
        """Create dialog widgets"""
        # Backup selection
        select_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.cloud.labels.select_backup_to_upload', default="Select Backup to Upload"), padding=10)
        select_frame.pack(fill="x", padx=10, pady=5)

        self.backup_var = tk.StringVar()
        self.backup_combo = ttk.Combobox(select_frame, textvariable=self.backup_var,
                                        state="readonly", width=50)
        self.backup_combo.pack(fill="x", pady=5)

        # Upload options
        options_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.cloud.labels.upload_options', default="Upload Options"), padding=10)
        options_frame.pack(fill="x", padx=10, pady=5)

        self.overwrite_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text=_t('gui.shell.database.dialogs.cloud.buttons.overwrite_if_exists', default="Overwrite if exists"), variable=self.overwrite_var).pack(anchor="w")

        self.delete_local_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text=_t('gui.shell.database.dialogs.cloud.buttons.delete_local_file_after_upload', default="Delete local file after upload"),
                       variable=self.delete_local_var).pack(anchor="w")

        # Progress
        progress_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.cloud.labels.upload_progress', default="Upload Progress"), padding=10)
        progress_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var,
                                          mode="determinate", length=400)
        self.progress_bar.pack(pady=5)

        self.status_label = ttk.Label(progress_frame, text=_t('gui.shell.database.dialogs.cloud.labels.ready_to_upload', default="Ready to upload"))
        self.status_label.pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        self.upload_button = ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.cloud.buttons.upload', default="Upload"), command=self.upload)
        self.upload_button.pack(side="right", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.cloud.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side="right")

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
                self.status_label.config(text=_t('gui.shell.database.dialogs.cloud.text.no_local_backups_available_for_upload', default="No local backups available for upload"))

        except Exception as e:
            self.status_label.config(text=f"Error loading backups: {e}")

    def upload(self):
        """Upload selected backup"""
        if not self.backup_combo.get():
            messagebox.showwarning(_t('gui.shell.database.dialogs.cloud.dialogs.no_selection', default="No Selection"), _t('gui.shell.database.dialogs.cloud.dialogs.please_select_a_backup_to_upload', default="Please select a backup to upload"))
            return

        try:
            # Get selected backup
            index = self.backup_combo.current()
            local_backups = [b for b in self.backups if not b.get('cloud_uploaded', False)]
            backup = local_backups[index]

            # Start upload in separate thread
            self.upload_button.config(state="disabled")
            self.status_label.config(text=_t('gui.shell.database.dialogs.cloud.text.starting_upload', default="Starting upload..."))
            self.progress_var.set(0)

            # Read Tk variables here, on the main loop, not from the worker.
            delete_local = self.delete_local_var.get()

            def progress(i):
                """Main loop only."""
                self.progress_var.set(i)
                self.status_label.config(text=f"Uploading... {i}%")

            def finish(status_text, error=False, close=False):
                """Report the outcome and reset the form. Main loop only."""
                self.status_label.config(text=status_text)
                self.upload_button.config(state="normal")
                self.progress_var.set(0)

                if error:
                    messagebox.showerror(_t('gui.shell.database.dialogs.cloud.dialogs.error', default="Error"), status_text, parent=self.dialog)
                else:
                    messagebox.showinfo(_t('gui.shell.database.dialogs.cloud.dialogs.success', default="Success"), _t('gui.shell.database.dialogs.cloud.dialogs.backup_uploaded_successfully', default="Backup uploaded successfully!"), parent=self.dialog)

                if close:
                    try:
                        self.dialog.destroy()
                    except tk.TclError:
                        pass

            def upload_worker():
                # Worker thread: the upload and the metadata write only.
                # Every widget touch is posted back to the main loop.
                try:
                    # Simulate upload progress
                    for i in range(101):
                        time.sleep(0.02)  # Simulate upload time
                        self._post(lambda pct=i: progress(pct))

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

                        done = _t('gui.shell.database.dialogs.cloud.text.upload_completed_successfully', default="Upload completed successfully!")
                        if delete_local:
                            os.remove(backup['path'])
                            done = _t('gui.shell.database.dialogs.cloud.text.upload_completed_local_file_deleted', default="Upload completed, local file deleted")

                        self._post(lambda text=done: finish(text, close=True))
                    else:
                        failed = _t('gui.shell.database.dialogs.cloud.text.upload_failed', default="Upload failed")
                        self._post(lambda text=failed: finish(text, error=True))

                except Exception as e:
                    self._post(lambda err=e: finish(f"Upload failed: {err}", error=True))

            # Start upload thread
            start_thread(self.dialog, upload_worker)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.dialogs.cloud.dialogs.error', default="Error"), f"Failed to start upload: {e}")
            self.upload_button.config(state="normal")

class DownloadDialog:
    """Dialog for downloading backups from cloud"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.database.dialogs.cloud.windows.download_from_cloud', default="Download from Cloud"))
        self.dialog.geometry("620x420")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.download_dir = tk.StringVar(value=config.get("backup_directory", "backups"))
        self.progress_var = tk.DoubleVar()
        self.status_text = tk.StringVar(value=_t('gui.shell.database.dialogs.cloud.values.select_a_backup_to_download', default="Select a backup to download"))
        self.cloud_backups = []

        self.create_widgets()
        self.load_backups()

    def create_widgets(self):
        """Create dialog widgets"""
        list_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.cloud.labels.available_cloud_backups', default="Available Cloud Backups"), padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("date", "type", "size", "file")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        self.tree.heading("date", text=_t('gui.shell.database.dialogs.cloud.headings.date', default="Date"))
        self.tree.heading("type", text=_t('gui.shell.database.dialogs.cloud.headings.type', default="Type"))
        self.tree.heading("size", text=_t('gui.shell.database.dialogs.cloud.headings.size', default="Size"))
        self.tree.heading("file", text=_t('gui.shell.database.dialogs.cloud.headings.file', default="File"))

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

        ttk.Button(controls_frame, text=_t('gui.shell.database.dialogs.cloud.buttons.refresh', default="Refresh"), command=self.load_backups).pack(side="left")

        ttk.Label(controls_frame, text=_t('gui.shell.database.dialogs.cloud.labels.download_to', default="Download to:")).pack(side="left", padx=(20, 5))
        destination_entry = ttk.Entry(controls_frame, textvariable=self.download_dir, width=40)
        destination_entry.pack(side="left", padx=5)
        ttk.Button(controls_frame, text=_t('gui.shell.database.dialogs.cloud.buttons.browse', default="Browse"), command=self.select_destination).pack(side="left")

        progress_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.cloud.labels.download_status', default="Download Status"), padding=10)
        progress_frame.pack(fill="x", padx=10, pady=5)
        ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, mode="determinate").pack(fill="x", pady=5)
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_text)
        self.status_label.pack(anchor="w")

        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        self.download_button = ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.cloud.buttons.download', default="Download"), command=self.download)
        self.download_button.pack(side="right", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.cloud.buttons.close', default="Close"), command=self.dialog.destroy).pack(side="right")

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
            messagebox.showwarning(_t('gui.shell.database.dialogs.cloud.dialogs.cloud_storage', default="Cloud Storage"), _t('gui.shell.database.dialogs.cloud.dialogs.cloud_storage_is_not_enabled', default="Cloud storage is not enabled."))
            return

        if config.get("cloud_provider") != "aws":
            messagebox.showwarning(_t('gui.shell.database.dialogs.cloud.dialogs.cloud_storage', default="Cloud Storage"), _t('gui.shell.database.dialogs.cloud.dialogs.only_aws_s3_provider_is_supported_for_downloads_in_this_demo', default="Only AWS S3 provider is supported for downloads in this demo."))
            return

        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.shell.database.dialogs.cloud.dialogs.no_selection', default="No Selection"), _t('gui.shell.database.dialogs.cloud.dialogs.please_select_a_cloud_backup_to_download', default="Please select a cloud backup to download."))
            return

        index = self.tree.index(selection[0])
        backup = self.cloud_backups[index]

        destination_dir = self.download_dir.get().strip()
        if not destination_dir:
            messagebox.showwarning(_t('gui.shell.database.dialogs.cloud.dialogs.destination', default="Destination"), _t('gui.shell.database.dialogs.cloud.dialogs.please_choose_a_destination_directory', default="Please choose a destination directory."))
            return

        os.makedirs(destination_dir, exist_ok=True)
        destination_path = os.path.join(destination_dir, backup["filename"])

        if os.path.exists(destination_path):
            if not messagebox.askyesno(
                _t('gui.shell.database.dialogs.cloud.dialogs.overwrite_file', default="Overwrite File"),
                f"'{backup['filename']}' already exists in the destination.\nOverwrite?",
                parent=self.dialog
            ):
                return

        bucket = config.get("aws_bucket", "").strip()
        if not bucket:
            messagebox.showwarning(_t('gui.shell.database.dialogs.cloud.dialogs.cloud_storage', default="Cloud Storage"), _t('gui.shell.database.dialogs.cloud.dialogs.aws_bucket_is_not_configured', default="AWS bucket is not configured."))
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
                messagebox.showinfo(_t('gui.shell.database.dialogs.cloud.dialogs.download_complete', default="Download Complete"), message, parent=self.dialog)
            else:
                messagebox.showerror(_t('gui.shell.database.dialogs.cloud.dialogs.download_failed', default="Download Failed"), message, parent=self.dialog)
            self.progress_var.set(0)

        def worker():
            try:
                ui(self.dialog, update_ui, 10, f"Downloading {backup['filename']}...")
                success = download_from_aws_s3(bucket, key, destination_path)
                if success:
                    ui(self.dialog, update_ui, 100, "Download complete.")

                    for record in metadata_manager.metadata["backups"]:
                        if record["path"] == backup["path"]:
                            record["last_downloaded"] = datetime.datetime.now().isoformat()
                            break
                    metadata_manager.save_metadata()

                    ui(self.dialog, finish, True, f"Backup downloaded to {destination_path}")
                else:
                    ui(self.dialog, finish, False, "Cloud service reported a failure.")
            except Exception as exc:
                ui(self.dialog, finish, False, f"Download failed: {exc}")

        start_thread(self.dialog, worker)
