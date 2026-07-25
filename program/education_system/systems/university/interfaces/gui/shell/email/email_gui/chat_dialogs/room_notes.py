from ._common import messagebox, scrolledtext, tk, ttk

class RoomNotesDialog:
    """Shared room notes with idle auto-save + remote-refresh polling.

    - Auto-saves when the user has been idle for AUTOSAVE_IDLE_MS while there
      are unsaved changes.
    - Every POLL_MS, fetches the server-side version; if updated_at advanced
      and the local copy is clean, the new content is loaded.
    - Closing while dirty prompts to save.
    """

    POLL_MS = 5000
    AUTOSAVE_IDLE_MS = 1500

    def __init__(self, parent, dashboard, room_id, room_name):
        self.dashboard = dashboard
        self.room_id = room_id
        self.room_name = room_name
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Notes: {room_name}")
        self.dialog.geometry("700x520")
        self.dialog.transient(parent)
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        self._dirty = False
        self._closed = False
        self._poll_job = None
        self._idle_job = None
        self._last_remote_updated_at = None
        self._last_remote_version = 0
        self._loading = False  # suppress dirty-flag while we're populating

        self._build()
        self._load_initial()
        self._poll_job = self.dialog.after(self.POLL_MS, self._poll)

    def _build(self):
        head = ttk.Frame(self.dialog)
        head.pack(fill=tk.X, padx=10, pady=(10, 0))
        self.meta_label = ttk.Label(head, foreground="#666", text="")
        self.meta_label.pack(side=tk.LEFT)
        self.status_label = ttk.Label(head, foreground="#2a8a2a", text="")
        self.status_label.pack(side=tk.RIGHT)

        # Conflict banner: hidden until a remote save lands while we're dirty.
        self.conflict_frame = ttk.Frame(self.dialog)
        self.conflict_label = ttk.Label(
            self.conflict_frame, anchor=tk.W,
            background="#ffe4e1", foreground="#7a0000",
            font=("TkDefaultFont", 9, "bold"),
            text=" ⚠ Someone else saved while you were editing. "
                 "Choose how to resolve.",
        )
        self.conflict_label.pack(side=tk.LEFT, fill=tk.X, expand=True,
                                 ipady=4)
        ttk.Button(self.conflict_frame, text="Diff & merge…",
                   command=self._resolve_diff_merge
                   ).pack(side=tk.LEFT, padx=4)
        ttk.Button(self.conflict_frame, text="Reload remote (discard mine)",
                   command=self._resolve_reload_remote
                   ).pack(side=tk.LEFT, padx=4)
        ttk.Button(self.conflict_frame, text="Keep mine (overwrite)",
                   command=self._resolve_keep_mine
                   ).pack(side=tk.LEFT, padx=4)

        self.text = scrolledtext.ScrolledText(self.dialog, wrap=tk.WORD)
        self.text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.text.bind('<KeyRelease>', self._on_key_release)

        btns = ttk.Frame(self.dialog)
        btns.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.save_button = ttk.Button(btns, text="Save now",
                                      command=self._save_now)
        self.save_button.pack(side=tk.RIGHT)
        ttk.Button(btns, text="Close",
                   command=self._on_close).pack(side=tk.RIGHT, padx=5)

        self._conflict_active = False
        self._pending_remote_data = None

    def _load_initial(self):
        try:
            data = self.dashboard.get_room_notes(self.room_id) or {}
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)
            data = {}
        self._apply_remote(data, keep_cursor=False)

    def _apply_remote(self, data, keep_cursor=True):
        self._loading = True
        try:
            cursor_idx = self.text.index(tk.INSERT) if keep_cursor else "1.0"
            self.text.delete("1.0", tk.END)
            if data.get('content'):
                self.text.insert("1.0", data['content'])
            try:
                self.text.mark_set(tk.INSERT, cursor_idx)
            except Exception:
                pass
            self._last_remote_updated_at = data.get('updated_at')
            self._last_remote_version = int(data.get('version') or 0)
            self._update_meta(data)
            self._dirty = False
            self._set_status("Up to date", "#666")
        finally:
            self._loading = False

    def _update_meta(self, data):
        ts = (data.get('updated_at') or '')[:16]
        who = data.get('updated_by_username')
        if ts:
            self.meta_label.config(
                text=f"Last updated: {ts}  by @{who or '—'}"
            )
        else:
            self.meta_label.config(text="No saved version yet")

    def _set_status(self, text, colour="#666"):
        self.status_label.config(text=text, foreground=colour)

    def _on_key_release(self, _event=None):
        if self._loading:
            return
        if not self._dirty:
            self._dirty = True
            self._set_status("Editing…", "#888")
        # Reset idle timer
        if self._idle_job is not None:
            try:
                self.dialog.after_cancel(self._idle_job)
            except Exception:
                pass
        self._idle_job = self.dialog.after(self.AUTOSAVE_IDLE_MS, self._idle_save)

    def _idle_save(self):
        self._idle_job = None
        if self._closed or not self._dirty:
            return
        self._save_now()

    def _save_now(self):
        if self._closed:
            return
        content = self.text.get("1.0", tk.END).rstrip()
        try:
            ok = self.dashboard.set_room_notes(
                self.room_id, content,
                expected_version=self._last_remote_version or None,
            )
        except Exception as e:
            self._set_status(f"Save failed: {e}", "#b30000")
            return
        if ok == 'version_conflict':
            # Someone else saved while we were editing — lock the editor
            # and require an explicit resolution choice.
            try:
                data = self.dashboard.get_room_notes(self.room_id) or {}
            except Exception:
                data = {}
            self._enter_conflict(data)
            return
        if not ok:
            self._set_status("Save failed (permission?)", "#b30000")
            return
        self._dirty = False
        self._set_status("Saved", "#2a8a2a")
        # Refresh meta so we know the new updated_at + version server-side.
        try:
            data = self.dashboard.get_room_notes(self.room_id) or {}
            self._last_remote_updated_at = data.get('updated_at')
            self._last_remote_version = int(data.get('version') or 0)
            self._update_meta(data)
        except Exception:
            pass

    def _poll(self):
        if self._closed:
            return
        if self._conflict_active:
            # Don't poll while waiting for the user to resolve a conflict.
            self._poll_job = self.dialog.after(self.POLL_MS, self._poll)
            return
        try:
            data = self.dashboard.get_room_notes(self.room_id) or {}
        except Exception:
            data = {}
        remote_v = int(data.get('version') or 0)
        remote_ts = data.get('updated_at')
        moved = (remote_ts and remote_ts != self._last_remote_updated_at) or (
            remote_v and remote_v != self._last_remote_version
        )
        if moved:
            if self._dirty:
                self._enter_conflict(data)
            else:
                self._apply_remote(data, keep_cursor=True)
                self._set_status("Refreshed", "#1a5fb4")
        self._poll_job = self.dialog.after(self.POLL_MS, self._poll)

    def _enter_conflict(self, remote_data):
        """Lock the editor and demand explicit user resolution."""
        self._conflict_active = True
        self._pending_remote_data = remote_data
        # Lock the editor and disable Save until resolution.
        try:
            self.text.config(state=tk.DISABLED)
        except Exception:
            pass
        try:
            self.save_button.config(state=tk.DISABLED)
        except Exception:
            pass
        # Show the conflict bar above the editor.
        self.conflict_frame.pack(fill=tk.X, padx=10, pady=(0, 4),
                                 before=self.text)
        ts = (remote_data.get('updated_at') or '')[:16]
        who = remote_data.get('updated_by_username') or '—'
        self._set_status(
            f"Conflict — locked. Remote @{who} saved {ts}.", "#b30000",
        )

    def _exit_conflict(self):
        self._conflict_active = False
        self._pending_remote_data = None
        try:
            self.text.config(state=tk.NORMAL)
        except Exception:
            pass
        try:
            self.save_button.config(state=tk.NORMAL)
        except Exception:
            pass
        self.conflict_frame.pack_forget()

    def _resolve_diff_merge(self):
        """Open a side-by-side diff so the user can hand-merge before saving."""
        remote = (self._pending_remote_data or {}).get('content', '') or ''
        mine = self.text.get("1.0", tk.END).rstrip("\n")

        def on_save(merged):
            # Force-save (no expected_version) so we don't bounce back here.
            try:
                ok = self.dashboard.set_room_notes(
                    self.room_id, merged, expected_version=None,
                )
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self.dialog)
                return False
            if not ok or ok == 'version_conflict':
                messagebox.showerror(
                    "Save failed",
                    "The save was rejected. The room may have changed again.",
                    parent=self.dialog,
                )
                return False
            # Reflect the merged content locally and exit the conflict.
            self._loading = True
            try:
                self.text.config(state=tk.NORMAL)
                self.text.delete("1.0", tk.END)
                self.text.insert("1.0", merged)
            finally:
                self._loading = False
            self._exit_conflict()
            self._dirty = False
            self._set_status("Merged and saved.", "#2a8a2a")
            try:
                data = self.dashboard.get_room_notes(self.room_id) or {}
                self._last_remote_updated_at = data.get('updated_at')
                self._last_remote_version = int(data.get('version') or 0)
                self._update_meta(data)
            except Exception:
                pass
            return True

        NotesDiffDialog(self.dialog, mine_content=mine,
                        remote_content=remote, on_save=on_save)

    def _resolve_reload_remote(self):
        """Discard local edits and load the remote version."""
        data = self._pending_remote_data or {}
        self._exit_conflict()
        if data:
            self._apply_remote(data, keep_cursor=False)
        self._set_status("Reloaded remote version.", "#1a5fb4")

    def _resolve_keep_mine(self):
        """Force-save local edits as the next version (no expected_version)."""
        self._exit_conflict()
        if self._closed:
            return
        content = self.text.get("1.0", tk.END).rstrip()
        try:
            ok = self.dashboard.set_room_notes(
                self.room_id, content, expected_version=None,
            )
        except Exception as e:
            self._set_status(f"Save failed: {e}", "#b30000")
            return
        if not ok or ok == 'version_conflict':
            self._set_status("Save still rejected.", "#b30000")
            return
        self._dirty = False
        self._set_status("Saved (overwrote remote).", "#2a8a2a")
        try:
            data = self.dashboard.get_room_notes(self.room_id) or {}
            self._last_remote_updated_at = data.get('updated_at')
            self._last_remote_version = int(data.get('version') or 0)
            self._update_meta(data)
        except Exception:
            pass

    def _on_close(self):
        if self._dirty:
            choice = messagebox.askyesnocancel(
                "Unsaved changes",
                "Save your changes before closing?",
                parent=self.dialog,
            )
            if choice is None:
                return
            if choice:
                self._save_now()
                if self._dirty:  # save failed
                    return
        self._closed = True
        for job in (self._poll_job, self._idle_job):
            if job is not None:
                try:
                    self.dialog.after_cancel(job)
                except Exception:
                    pass
        self._poll_job = None
        self._idle_job = None
        self.dialog.destroy()


class NotesDiffDialog:
    """Side-by-side merge view for resolving a notes conflict.

    Left pane is editable ("Mine"); right pane is read-only ("Remote").
    Lines are tagged using difflib so additions/removals/changes stand out.
    The user edits the left pane to produce the merged version, then Save."""

    def __init__(self, parent, mine_content, remote_content, on_save):
        self.on_save = on_save
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Merge notes — diff")
        self.dialog.geometry("1100x620")
        self.dialog.transient(parent)
        self.dialog.after(100,
                          lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        self._build()
        self._populate(mine_content or '', remote_content or '')

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=8)
        frame.pack(fill=tk.BOTH, expand=True)
        head = ttk.Frame(frame)
        head.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(head, text=" Edit the left pane to produce the merged version. "
                              "Click a remote line to copy it across.",
                  foreground="#444").pack(side=tk.LEFT)

        paned = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=1)

        ttk.Label(left, text="Mine (editable)",
                  font=("TkDefaultFont", 10, "bold"),
                  foreground="#1a5fb4").pack(anchor=tk.W)
        self.mine = scrolledtext.ScrolledText(left, wrap=tk.WORD)
        self.mine.pack(fill=tk.BOTH, expand=True)

        ttk.Label(right, text="Remote (read-only)",
                  font=("TkDefaultFont", 10, "bold"),
                  foreground="#7a4f00").pack(anchor=tk.W)
        self.remote = scrolledtext.ScrolledText(right, wrap=tk.WORD,
                                                 state=tk.DISABLED)
        self.remote.pack(fill=tk.BOTH, expand=True)

        # Diff colours
        for w in (self.mine, self.remote):
            w.tag_configure("diff_add",   background="#e0f5e0")
            w.tag_configure("diff_remove", background="#fbe0e0")
            w.tag_configure("diff_change", background="#fff4d6")

        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="Save merged",
                   command=self._on_save).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy
                   ).pack(side=tk.RIGHT, padx=5)

    def _populate(self, mine_text, remote_text):
        import difflib
        mine_lines = mine_text.splitlines() or ['']
        remote_lines = remote_text.splitlines() or ['']
        self.mine.delete("1.0", tk.END)
        # Populate left first; remote populated under DISABLED state.
        self.remote.config(state=tk.NORMAL)
        self.remote.delete("1.0", tk.END)

        sm = difflib.SequenceMatcher(a=mine_lines, b=remote_lines, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                for line in mine_lines[i1:i2]:
                    self.mine.insert(tk.END, line + "\n")
                for line in remote_lines[j1:j2]:
                    self.remote.insert(tk.END, line + "\n")
            elif tag == 'replace':
                for line in mine_lines[i1:i2]:
                    self.mine.insert(tk.END, line + "\n", ("diff_change",))
                for line in remote_lines[j1:j2]:
                    self._insert_remote_line(line, "diff_change")
            elif tag == 'delete':
                # Lines only in mine: highlight on left, blank on right.
                for line in mine_lines[i1:i2]:
                    self.mine.insert(tk.END, line + "\n", ("diff_remove",))
                for _ in range(i2 - i1):
                    self._insert_remote_line("", "diff_remove")
            elif tag == 'insert':
                # Lines only in remote: highlight on right, blank on left.
                for _ in range(j2 - j1):
                    self.mine.insert(tk.END, "\n", ("diff_add",))
                for line in remote_lines[j1:j2]:
                    self._insert_remote_line(line, "diff_add")

        self.remote.config(state=tk.DISABLED)
        self.remote.bind("<Button-1>", self._copy_remote_line)

    def _insert_remote_line(self, line, tag):
        # Tag each line so click-handlers can grab the exact range.
        start = self.remote.index("end-1c")
        self.remote.insert(tk.END, line + "\n", (tag,))
        end = self.remote.index("end-1c")
        # Per-line tag for click resolution
        line_tag = f"r_line_{start.split('.')[0]}"
        self.remote.tag_add(line_tag, start, end)

    def _copy_remote_line(self, event):
        """Click a remote line to insert it at the cursor in the left pane."""
        idx = self.remote.index(f"@{event.x},{event.y}")
        line_no = idx.split('.')[0]
        line_start = f"{line_no}.0"
        line_end = f"{int(line_no) + 1}.0"
        try:
            line = self.remote.get(line_start, line_end)
        except Exception:
            return
        if not line.strip():
            return
        # Insert at the current insertion point in the left pane.
        self.mine.focus_set()
        self.mine.insert(tk.INSERT, line)

    def _on_save(self):
        merged = self.mine.get("1.0", tk.END).rstrip()
        if self.on_save and self.on_save(merged):
            self.dialog.destroy()
