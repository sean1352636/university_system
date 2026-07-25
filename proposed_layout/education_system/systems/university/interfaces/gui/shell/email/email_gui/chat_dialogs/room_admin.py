from ._common import askinteger, askstring, datetime, messagebox, tk, ttk

class EditRoomDialog:
    """Edit room metadata: name, description, type, category, icon, colour, max_members."""

    ROOM_TYPES = ("public", "private", "course", "department")
    PRESET_COLOURS = ("", "#ffe4e1", "#e1f0ff", "#e1ffe4", "#fff7d6", "#f0e1ff", "#e6e6e6")

    def __init__(self, parent, dashboard, room, refresh_callback=None):
        self.dashboard = dashboard
        self.room = room
        self.refresh_callback = refresh_callback
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Edit Room: {room.get('name', '')}")
        self.dialog.geometry("460x440")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        self._build()

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.name_var = tk.StringVar(value=self.room.get('name', ''))
        ttk.Entry(frame, textvariable=self.name_var).grid(row=0, column=1, sticky=tk.EW, pady=4)

        ttk.Label(frame, text="Description:").grid(row=1, column=0, sticky=tk.NW, pady=4)
        self.desc_text = tk.Text(frame, height=4, wrap=tk.WORD)
        self.desc_text.grid(row=1, column=1, sticky=tk.EW, pady=4)
        if self.room.get('description'):
            self.desc_text.insert("1.0", self.room['description'])

        ttk.Label(frame, text="Type:").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.type_var = tk.StringVar(value=self.room.get('room_type') or 'public')
        ttk.Combobox(frame, textvariable=self.type_var, values=self.ROOM_TYPES,
                     state="readonly").grid(row=2, column=1, sticky=tk.EW, pady=4)

        ttk.Label(frame, text="Category:").grid(row=3, column=0, sticky=tk.W, pady=4)
        try:
            existing = self.dashboard.list_chat_categories() or []
        except Exception:
            existing = []
        self.category_var = tk.StringVar(value=self.room.get('category') or '')
        ttk.Combobox(frame, textvariable=self.category_var, values=existing).grid(
            row=3, column=1, sticky=tk.EW, pady=4)

        ttk.Label(frame, text="Icon (emoji):").grid(row=4, column=0, sticky=tk.W, pady=4)
        self.icon_var = tk.StringVar(value=self.room.get('icon') or '')
        ttk.Entry(frame, textvariable=self.icon_var, width=6).grid(
            row=4, column=1, sticky=tk.W, pady=4)

        ttk.Label(frame, text="Colour:").grid(row=5, column=0, sticky=tk.W, pady=4)
        self.colour_var = tk.StringVar(value=self.room.get('colour') or '')
        ttk.Combobox(frame, textvariable=self.colour_var, values=self.PRESET_COLOURS).grid(
            row=5, column=1, sticky=tk.EW, pady=4)

        ttk.Label(frame, text="Max members:").grid(row=6, column=0, sticky=tk.W, pady=4)
        self.max_var = tk.StringVar(value=str(self.room.get('max_members') or ''))
        ttk.Entry(frame, textvariable=self.max_var, width=8).grid(
            row=6, column=1, sticky=tk.W, pady=4)

        ttk.Label(frame, text="Linked module:").grid(row=7, column=0, sticky=tk.W, pady=4)
        self.course_var = tk.StringVar(value=self.room.get('linked_course_code') or '')
        ttk.Entry(frame, textvariable=self.course_var).grid(
            row=7, column=1, sticky=tk.EW, pady=4)

        self.ann_var = tk.BooleanVar(value=bool(self.room.get('announcement_mode')))
        ttk.Checkbutton(frame, text="Announcement-only (only admins can post)",
                        variable=self.ann_var).grid(row=8, column=0, columnspan=2,
                                                    sticky=tk.W, pady=4)

        ttk.Label(frame, text="Office hours start:").grid(row=9, column=0, sticky=tk.W, pady=4)
        self.oh_start_var = tk.StringVar(value=self.room.get('oh_starts_at') or '')
        ttk.Entry(frame, textvariable=self.oh_start_var).grid(
            row=9, column=1, sticky=tk.EW, pady=4)
        ttk.Label(frame, text="Office hours end:").grid(row=10, column=0, sticky=tk.W, pady=4)
        self.oh_end_var = tk.StringVar(value=self.room.get('oh_ends_at') or '')
        ttk.Entry(frame, textvariable=self.oh_end_var).grid(
            row=10, column=1, sticky=tk.EW, pady=4)
        ttk.Label(frame, text="(format: YYYY-MM-DD HH:MM:SS)",
                  foreground="#666").grid(row=11, column=1, sticky=tk.W)

        ttk.Label(frame, text="Retention (days):").grid(row=12, column=0, sticky=tk.W, pady=4)
        self.retention_var = tk.StringVar(value=str(self.room.get('retention_days') or ''))
        ttk.Entry(frame, textvariable=self.retention_var, width=8).grid(
            row=12, column=1, sticky=tk.W, pady=4)

        ttk.Label(frame, text="Slow-mode (seconds):").grid(row=13, column=0, sticky=tk.W, pady=4)
        self.slow_var = tk.StringVar(value=str(self.room.get('slow_mode_seconds') or 0))
        ttk.Entry(frame, textvariable=self.slow_var, width=8).grid(
            row=13, column=1, sticky=tk.W, pady=4)

        self.enc_var = tk.BooleanVar(value=bool(self.room.get('is_encrypted')))
        ttk.Checkbutton(frame, text="Encrypt new messages at rest (deterrent only)",
                        variable=self.enc_var).grid(row=14, column=0, columnspan=2,
                                                    sticky=tk.W, pady=4)

        btns = ttk.Frame(frame)
        btns.grid(row=15, column=0, columnspan=2, pady=12)
        ttk.Button(btns, text="Save", command=self._save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Name is required.")
            return
        for var, label_for_msg in ((self.oh_start_var, "Office-hours start"),
                                    (self.oh_end_var, "Office-hours end")):
            v = var.get().strip()
            if v:
                try:
                    datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    messagebox.showwarning("Bad date",
                                           f"{label_for_msg} must be YYYY-MM-DD HH:MM:SS.")
                    return
        kwargs = {
            'name': name,
            'description': self.desc_text.get("1.0", tk.END).strip(),
            'room_type': self.type_var.get(),
            'category': self.category_var.get().strip(),
            'icon': self.icon_var.get().strip(),
            'colour': self.colour_var.get().strip(),
            'linked_course_code': self.course_var.get().strip(),
            'announcement_mode': bool(self.ann_var.get()),
            'oh_starts_at': self.oh_start_var.get().strip(),
            'oh_ends_at': self.oh_end_var.get().strip(),
            'is_encrypted': bool(self.enc_var.get()),
        }
        max_str = self.max_var.get().strip()
        if max_str:
            try:
                kwargs['max_members'] = int(max_str)
            except ValueError:
                messagebox.showwarning("Invalid", "Max members must be a number.")
                return
        ret_str = self.retention_var.get().strip()
        if ret_str:
            try:
                kwargs['retention_days'] = int(ret_str)
            except ValueError:
                messagebox.showwarning("Invalid", "Retention days must be a number.")
                return
        else:
            kwargs['retention_days'] = ''
        slow_str = self.slow_var.get().strip()
        try:
            kwargs['slow_mode_seconds'] = int(slow_str) if slow_str else 0
        except ValueError:
            messagebox.showwarning("Invalid", "Slow-mode seconds must be a number.")
            return
        try:
            ok = self.dashboard.update_chat_room(self.room['id'], **kwargs)
            if ok:
                self.dialog.destroy()
                if self.refresh_callback:
                    self.refresh_callback()
            else:
                messagebox.showerror("Error", "Could not update room (admin only).")
        except Exception as e:
            messagebox.showerror("Error", str(e))


class ManageMembersDialog:
    """Admin tool: promote/demote, kick, ban/unban, mute, transfer ownership."""

    def __init__(self, parent, dashboard, room, refresh_callback=None):
        self.dashboard = dashboard
        self.room = room
        self.room_id = room['id']
        self.refresh_callback = refresh_callback
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Members of {room.get('name', '')}")
        self.dialog.geometry("680x420")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        self._build()
        self._load()

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        cols = ("Username", "Name", "Role", "State", "Muted until")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.column("Username", width=110)
        self.tree.column("Name", width=160)
        self.tree.column("Role", width=80)
        self.tree.column("State", width=100)
        self.tree.column("Muted until", width=140)
        self.tree.tag_configure("banned", foreground="#888")
        self.tree.tag_configure("creator", font=("TkDefaultFont", 10, "bold"))
        self.tree.pack(fill=tk.BOTH, expand=True)

        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="Promote",
                   command=lambda: self._set_admin(True)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Demote",
                   command=lambda: self._set_admin(False)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Kick", command=self._kick).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Ban", command=self._ban_with_reason).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Bans…",
                   command=self._show_bans).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Mute…", command=self._mute).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Unmute", command=self._unmute).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Transfer Ownership",
                   command=self._transfer).pack(side=tk.LEFT, padx=10)
        ttk.Button(btns, text="Close",
                   command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load(self):
        for it in self.tree.get_children():
            self.tree.delete(it)
        try:
            members = self.dashboard.get_room_members(self.room_id) or []
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        for m in members:
            role = ("Creator" if m.get('is_creator')
                    else "Admin" if m.get('is_admin') else "Member")
            state = "banned" if m.get('is_banned') else "active"
            tag = "creator" if m.get('is_creator') else ("banned" if m.get('is_banned') else "")
            self.tree.insert(
                '', tk.END,
                values=(f"@{m['username']}", m['full_name'], role, state,
                        m.get('muted_until') or ''),
                tags=(str(m['user_id']),) + ((tag,) if tag else ()),
            )

    def _selected_user_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        tags = self.tree.item(sel[0]).get('tags') or ()
        for t in tags:
            if str(t).isdigit():
                return int(t)
        return None

    def _act(self, fn, *args, success_msg=None):
        uid = self._selected_user_id()
        if not uid:
            messagebox.showwarning("Select", "Select a member first.")
            return
        try:
            ok = fn(self.room_id, uid, *args)
            if ok:
                if success_msg:
                    self.dialog.title(success_msg)
                self._load()
                if self.refresh_callback:
                    self.refresh_callback()
            else:
                messagebox.showerror("Error",
                                     "Action denied (creator can't be demoted/kicked, "
                                     "or you lack permission).")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _set_admin(self, promote):
        self._act(self.dashboard.set_room_admin, promote)

    def _kick(self):
        if not messagebox.askyesno("Kick", "Remove the selected member from this room?"):
            return
        reason = askstring(
            "Kick reason",
            "Reason (optional, included in the email notice):",
            parent=self.dialog,
        ) or ''
        self._act(self.dashboard.kick_room_member, reason)

    def _ban(self, banned, reason=None):
        # Underlying API now takes a reason kwarg.
        uid = self._selected_user_id()
        if not uid:
            messagebox.showwarning("Select", "Select a member first.",
                                   parent=self.dialog)
            return
        try:
            ok = self.dashboard.ban_room_member(self.room_id, uid,
                                                banned=banned, reason=reason)
            if ok:
                self._load()
                if self.refresh_callback:
                    self.refresh_callback()
            else:
                messagebox.showerror("Error",
                                     "Action denied (creator can't be banned, "
                                     "or you lack permission).",
                                     parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)

    def _ban_with_reason(self):
        uid = self._selected_user_id()
        if not uid:
            messagebox.showwarning("Select", "Select a member first.",
                                   parent=self.dialog)
            return
        if not messagebox.askyesno(
            "Ban member",
            "Ban this user from the room? They will be removed and unable "
            "to rejoin until you unban them.",
            parent=self.dialog,
        ):
            return
        reason = askstring("Ban reason",
                           "Reason (optional, shown in audit log):",
                           parent=self.dialog) or ''
        self._ban(True, reason=reason)

    def _show_bans(self):
        try:
            bans = self.dashboard.list_room_bans(self.room_id) or []
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)
            return
        dlg = tk.Toplevel(self.dialog)
        dlg.title(f"Bans — {self.room.get('name', '')}")
        dlg.geometry("520x340")
        dlg.transient(self.dialog)
        frame = ttk.Frame(dlg, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        if not bans:
            ttk.Label(frame, text="No active bans.",
                      foreground="#666").pack(padx=10, pady=20)
        else:
            cols = ("User", "Banned at", "By", "Reason")
            tree = ttk.Treeview(frame, columns=cols, show="headings")
            for c in cols:
                tree.heading(c, text=c)
            tree.column("User", width=150)
            tree.column("Banned at", width=130)
            tree.column("By", width=90)
            tree.column("Reason", width=140)
            for b in bans:
                tree.insert(
                    '', tk.END,
                    values=(
                        f"{b['full_name']} (@{b['username']})",
                        (b.get('banned_at') or '')[:16],
                        f"@{b.get('banned_by') or ''}" if b.get('banned_by') else '',
                        b.get('reason') or '',
                    ),
                    tags=(str(b['user_id']),),
                )
            tree.pack(fill=tk.BOTH, expand=True)

            def unban_selected():
                sel = tree.selection()
                if not sel:
                    return
                uid = int(tree.item(sel[0])['tags'][0])
                try:
                    ok = self.dashboard.ban_room_member(
                        self.room_id, uid, banned=False,
                    )
                    if ok:
                        dlg.destroy()
                        self._show_bans()  # refresh
                        if self.refresh_callback:
                            self.refresh_callback()
                    else:
                        messagebox.showerror("Error", "Could not unban.",
                                             parent=dlg)
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=dlg)

            ttk.Button(frame, text="Unban selected",
                       command=unban_selected).pack(pady=(8, 0))
        ttk.Button(frame, text="Close",
                   command=dlg.destroy).pack(pady=(8, 0))

    def _mute(self):
        minutes = askinteger("Mute", "Mute for how many minutes?",
                             parent=self.dialog, minvalue=1, maxvalue=10080)
        if not minutes:
            return
        reason = askstring(
            "Mute reason",
            "Reason (optional, included in the email notice):",
            parent=self.dialog,
        ) or ''
        self._act(self.dashboard.mute_room_member, minutes, reason)

    def _unmute(self):
        self._act(self.dashboard.mute_room_member, None)

    def _transfer(self):
        uid = self._selected_user_id()
        if not uid:
            messagebox.showwarning("Select", "Select the new owner first.")
            return
        if not messagebox.askyesno("Transfer Ownership",
                                   "Transfer ownership to this member? "
                                   "You will remain an admin."):
            return
        try:
            ok = self.dashboard.transfer_room_ownership(self.room_id, uid)
            if ok:
                self._load()
                if self.refresh_callback:
                    self.refresh_callback()
                messagebox.showinfo("Transferred", "Ownership transferred.")
            else:
                messagebox.showerror("Error",
                                     "Only the current owner can transfer ownership.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

