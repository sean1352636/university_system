from ._common import askstring, datetime, messagebox, scrolledtext, tk, ttk

class PollComposerDialog:
    """Compose a chat poll: question, multiple options, optional close-time."""

    def __init__(self, parent, dashboard, room_id, on_created=None):
        self.dashboard = dashboard
        self.room_id = room_id
        self.on_created = on_created
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("New Poll")
        self.dialog.geometry("420x420")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        self._option_vars = []
        self._build()

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Question:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.question_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.question_var).grid(
            row=0, column=1, sticky=tk.EW, pady=4)

        ttk.Label(frame, text="Options:").grid(row=1, column=0, sticky=tk.NW, pady=4)
        self.options_frame = ttk.Frame(frame)
        self.options_frame.grid(row=1, column=1, sticky=tk.EW, pady=4)
        for _ in range(2):
            self._add_option_row()
        ttk.Button(frame, text="+ Add option",
                   command=self._add_option_row).grid(row=2, column=1, sticky=tk.W)

        self.multi_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Allow multiple choices",
                        variable=self.multi_var).grid(row=3, column=1,
                                                      sticky=tk.W, pady=8)

        ttk.Label(frame, text="Closes at (YYYY-MM-DD HH:MM:SS, optional):").grid(
            row=4, column=0, columnspan=2, sticky=tk.W, pady=(8, 2))
        self.closes_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.closes_var).grid(
            row=5, column=0, columnspan=2, sticky=tk.EW, pady=2)

        btns = ttk.Frame(frame)
        btns.grid(row=6, column=0, columnspan=2, pady=12)
        ttk.Button(btns, text="Create", command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _add_option_row(self):
        var = tk.StringVar()
        self._option_vars.append(var)
        ttk.Entry(self.options_frame, textvariable=var).pack(fill=tk.X, pady=2)

    def _create(self):
        question = self.question_var.get().strip()
        options = [v.get().strip() for v in self._option_vars if v.get().strip()]
        if not question or len(options) < 2:
            messagebox.showwarning("Missing", "Need a question and at least two options.")
            return
        closes_at = self.closes_var.get().strip() or None
        if closes_at:
            try:
                datetime.strptime(closes_at, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                messagebox.showwarning("Bad date", "Use format YYYY-MM-DD HH:MM:SS.")
                return
        try:
            ok = self.dashboard.create_chat_poll(
                self.room_id, question, options,
                multi_choice=self.multi_var.get(), closes_at=closes_at,
            )
            if ok:
                self.dialog.destroy()
                if self.on_created:
                    self.on_created()
            else:
                messagebox.showerror("Error", "Could not create poll.")
        except Exception as e:
            messagebox.showerror("Error", str(e))


class QueueDialog:
    """Office-hours queue. Members see their position; admins see Call Next."""

    POLL_MS = 3000

    def __init__(self, parent, dashboard, room_id, is_admin=False):
        self.dashboard = dashboard
        self.room_id = room_id
        self.is_admin = is_admin
        self._closed = False
        self._job = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Queue")
        self.dialog.geometry("400x340")
        self.dialog.transient(parent)
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()
        self._refresh()
        self._job = self.dialog.after(self.POLL_MS, self._tick)

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        cols = ("#", "Member", "Joined")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.column("#", width=40, anchor=tk.CENTER)
        self.tree.tag_configure("mine", font=("TkDefaultFont", 10, "bold"),
                                foreground="#1a5fb4")
        self.tree.pack(fill=tk.BOTH, expand=True)

        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=(8, 0))
        if self.is_admin:
            ttk.Button(btns, text="Call Next",
                       command=self._call_next).pack(side=tk.LEFT)
        ttk.Button(btns, text="Refresh", command=self._refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Close", command=self._on_close).pack(side=tk.RIGHT)

    def _refresh(self):
        for it in self.tree.get_children():
            self.tree.delete(it)
        try:
            queue = self.dashboard.get_room_queue(self.room_id) or []
        except Exception:
            queue = []
        for i, q in enumerate(queue, start=1):
            tags = ("mine",) if q.get('mine') else ()
            self.tree.insert(
                '', tk.END,
                values=(i, f"{q['full_name']} (@{q['username']})", q['joined_at'][:16]),
                tags=tags,
            )

    def _call_next(self):
        try:
            called = self.dashboard.call_next_in_queue(self.room_id)
            if called:
                messagebox.showinfo(
                    "Called",
                    f"Calling {called['full_name']} (@{called['username']}).",
                    parent=self.dialog,
                )
                self._refresh()
            else:
                messagebox.showinfo("Empty", "Queue is empty.", parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)

    def _tick(self):
        if self._closed:
            return
        self._refresh()
        self._job = self.dialog.after(self.POLL_MS, self._tick)

    def _on_close(self):
        self._closed = True
        if self._job is not None:
            try:
                self.dialog.after_cancel(self._job)
            except Exception:
                pass
        self.dialog.destroy()


class ReportsDialog:
    """Moderator panel for reviewing reported messages/users."""

    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Chat Reports")
        self.dialog.geometry("820x440")
        self.dialog.transient(parent)
        self._build()
        self._refresh()

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        head = ttk.Frame(frame)
        head.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(head, text="Status:").pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="open")
        ttk.Combobox(head, textvariable=self.status_var,
                     values=("open", "resolved", "all"),
                     state="readonly", width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(head, text="Refresh", command=self._refresh).pack(side=tk.LEFT)
        ttk.Button(head, text="Resolve…", command=self._resolve).pack(side=tk.LEFT, padx=5)
        ttk.Button(head, text="Open case file…",
                   command=self._open_case_file).pack(side=tk.LEFT, padx=5)
        cols = ("Created", "Status", "Reporter", "Target", "Room", "Case", "Reason", "Excerpt")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.column("Created", width=130)
        self.tree.column("Status", width=70, anchor=tk.CENTER)
        self.tree.column("Reporter", width=110)
        self.tree.column("Target", width=110)
        self.tree.column("Room", width=110)
        self.tree.column("Case", width=70, anchor=tk.CENTER)
        self.tree.column("Reason", width=140)
        self.tree.column("Excerpt", width=200)
        self.tree.pack(fill=tk.BOTH, expand=True)
        ttk.Button(frame, text="Close", command=self.dialog.destroy).pack(pady=(8, 0))

    def _refresh(self):
        for it in self.tree.get_children():
            self.tree.delete(it)
        try:
            reports = self.dashboard.list_chat_reports(status=self.status_var.get()) or []
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)
            return
        for r in reports:
            target = (f"@{r.get('target_user')}" if r.get('target_user')
                      else f"msg #{r.get('target_message_id')}" if r.get('target_message_id')
                      else "")
            sg = r.get('safeguarding_submission_id')
            tags = [str(r['id'])]
            if sg:
                tags.append(f"sg_{sg}")
            self.tree.insert(
                '', tk.END,
                values=(
                    (r.get('created_at') or '')[:16], r.get('status'),
                    f"@{r.get('reporter') or ''}", target,
                    r.get('room_name') or '',
                    f"#{sg}" if sg else "",
                    (r.get('reason') or '')[:60],
                    r.get('message_excerpt') or '',
                ),
                tags=tuple(tags),
            )

    def _selected_case_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        for tag in self.tree.item(sel[0]).get('tags') or ():
            if str(tag).startswith('sg_'):
                try:
                    return int(str(tag)[3:])
                except ValueError:
                    return None
        return None

    def _open_case_file(self):
        case_id = self._selected_case_id()
        if not case_id:
            messagebox.showinfo("Case file",
                                "Selected report has no linked safeguarding case.",
                                parent=self.dialog)
            return
        try:
            case = self.dashboard.get_safeguarding_submission(case_id)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)
            return
        if not case:
            messagebox.showerror("Case file",
                                 "Case not found, or you lack permission.",
                                 parent=self.dialog)
            return
        dlg = tk.Toplevel(self.dialog)
        dlg.title(f"Safeguarding case #{case['id']}")
        dlg.geometry("520x420")
        dlg.transient(self.dialog)
        f = ttk.Frame(dlg, padding=10)
        f.pack(fill=tk.BOTH, expand=True)
        meta = (
            f"Submitted: {case.get('submitted_at')}\n"
            f"Reporter: {case.get('full_name') or case.get('username')} "
            f"(@{case.get('username')})  ·  role: {case.get('role') or '—'}\n"
            f"Severity: {case.get('severity')}  ·  Status: {case.get('status')}\n"
            f"Categories: {case.get('categories')}\n"
        )
        ttk.Label(f, text=meta, justify=tk.LEFT).pack(anchor=tk.W)
        body = scrolledtext.ScrolledText(f, wrap=tk.WORD)
        body.pack(fill=tk.BOTH, expand=True, pady=(8, 8))
        body.insert("1.0", case.get('content') or '')
        if case.get('reviewer'):
            ttk.Label(f, foreground="#666",
                      text=f"Reviewed by @{case['reviewer']} at "
                           f"{case.get('reviewed_at') or ''}: "
                           f"{case.get('review_note') or ''}").pack(anchor=tk.W)
        body.config(state=tk.DISABLED)
        ttk.Button(f, text="Close", command=dlg.destroy).pack(pady=(8, 0))

    def _resolve(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a report first.", parent=self.dialog)
            return
        report_id = int(self.tree.item(sel[0])['tags'][0])
        note = askstring("Resolve report",
                         "Resolution notes (optional):",
                         parent=self.dialog) or ''
        try:
            ok = self.dashboard.resolve_chat_report(report_id, note)
            if ok:
                self._refresh()
            else:
                messagebox.showerror("Error", "Could not resolve (permission?).",
                                     parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)


class AuditLogDialog:
    """Read-only audit log viewer."""

    def __init__(self, parent, dashboard, room_id=None, room_name=None):
        self.dashboard = dashboard
        self.room_id = room_id
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Audit Log{' — ' + room_name if room_name else ''}")
        self.dialog.geometry("780x420")
        self.dialog.transient(parent)
        self._build()
        self._refresh()

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        head = ttk.Frame(frame)
        head.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(head, text="Action filter:").pack(side=tk.LEFT)
        self.action_var = tk.StringVar()
        ttk.Entry(head, textvariable=self.action_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(head, text="Apply", command=self._refresh).pack(side=tk.LEFT)
        cols = ("When", "User", "Action", "Details")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.column("When", width=140)
        self.tree.column("User", width=110)
        self.tree.column("Action", width=160)
        self.tree.column("Details", width=340)
        self.tree.pack(fill=tk.BOTH, expand=True)
        ttk.Button(frame, text="Close", command=self.dialog.destroy).pack(pady=(8, 0))

    def _refresh(self):
        for it in self.tree.get_children():
            self.tree.delete(it)
        try:
            entries = self.dashboard.get_communication_audit_log(
                room_id=self.room_id,
                action_type=(self.action_var.get().strip() or None),
            ) or []
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)
            return
        for e in entries:
            self.tree.insert('', tk.END, values=(
                (e.get('performed_at') or '')[:19],
                f"@{e.get('username') or ''}",
                e.get('action_type') or '',
                e.get('details') or '',
            ))


class BlocksDialog:
    """Manage the current user's DM block list."""

    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Blocked users")
        self.dialog.geometry("440x320")
        self.dialog.transient(parent)
        self._build()
        self._refresh()

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        cols = ("Username", "Name", "Blocked since")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.pack(fill=tk.BOTH, expand=True)
        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="Block by username…",
                   command=self._block).pack(side=tk.LEFT)
        ttk.Button(btns, text="Unblock", command=self._unblock).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _refresh(self):
        for it in self.tree.get_children():
            self.tree.delete(it)
        try:
            rows = self.dashboard.list_blocked_users() or []
        except Exception:
            rows = []
        for r in rows:
            self.tree.insert(
                '', tk.END,
                values=(f"@{r['username']}", r['full_name'],
                        (r.get('created_at') or '')[:16]),
                tags=(str(r['user_id']),),
            )

    def _block(self):
        username = askstring("Block user", "Username to block:",
                             parent=self.dialog)
        if not username:
            return
        try:
            from education_system.post_18.university_system.infrastructure.email.admin import search_users as _su
            users = _su(self.dashboard.auth, username)
        except Exception:
            users = []
        if not users:
            messagebox.showerror("Error", f"No user found for '{username}'.",
                                 parent=self.dialog)
            return
        try:
            ok = self.dashboard.block_user(users[0]['id'])
            if ok:
                self._refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)

    def _unblock(self):
        sel = self.tree.selection()
        if not sel:
            return
        uid = int(self.tree.item(sel[0])['tags'][0])
        try:
            ok = self.dashboard.unblock_user(uid)
            if ok:
                self._refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)

