from ._common import messagebox, tk, ttk

class CreateChatRoomDialog:
    def __init__(self, parent, dashboard, refresh_callback=None):
        self.dashboard = dashboard
        self.refresh_callback = refresh_callback
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Chat Room")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Room name
        ttk.Label(main_frame, text="Room Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(main_frame, width=40)
        self.name_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        # Description
        ttk.Label(main_frame, text="Description:").grid(row=1, column=0, sticky=tk.NW, pady=5)
        self.description_text = tk.Text(main_frame, width=40, height=5)
        self.description_text.grid(row=1, column=1, sticky=tk.NSEW, pady=5)

        # Room type
        ttk.Label(main_frame, text="Room Type:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.type_var = tk.StringVar(value="public")
        type_frame = ttk.Frame(main_frame)
        type_frame.grid(row=2, column=1, sticky=tk.W, pady=5)

        ttk.Radiobutton(type_frame, text="Public", variable=self.type_var, value="public").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="Private", variable=self.type_var, value="private").pack(anchor=tk.W)

        # Max members
        ttk.Label(main_frame, text="Max Members:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.max_members_var = tk.StringVar(value="50")
        ttk.Spinbox(main_frame, from_=2, to=1000, textvariable=self.max_members_var, width=10).grid(row=3, column=1, sticky=tk.W, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Create", command=self.create_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

    def create_room(self):
        name = self.name_entry.get().strip()
        description = self.description_text.get(1.0, tk.END).strip()
        room_type = self.type_var.get()
        max_members = int(self.max_members_var.get())

        if not name:
            messagebox.showwarning("Missing Information", "Please provide a room name")
            return

        if not self.dashboard:
            messagebox.showerror("Error", "Dashboard not initialized")
            return

        try:
            result = self.dashboard.create_chat_room(
                name,
                description=description or None,
                room_type=room_type,
                max_members=max_members,
            )
            if result:
                messagebox.showinfo("Success", f"Chat room '{name}' created successfully!")
                self.dialog.destroy()
                if self.refresh_callback:
                    self.refresh_callback()
            else:
                messagebox.showerror(
                    "Error",
                    "Failed to create chat room (name may already exist or you lack permission)",
                )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create chat room: {e}")


class ChatInvitationsDialog:
    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Chat Room Invitations")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
        self.load_invitations()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text="Pending Chat Room Invitations", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Invitations list
        columns = ("Room", "Invited By", "Date")
        self.invitations_tree = ttk.Treeview(main_frame, columns=columns, show="headings")

        for col in columns:
            self.invitations_tree.heading(col, text=col)

        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.invitations_tree.yview)
        self.invitations_tree.configure(yscrollcommand=scrollbar.set)

        self.invitations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Accept", command=self.accept_invitation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Decline", command=self.decline_invitation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def load_invitations(self):
        # Clear existing items
        for item in self.invitations_tree.get_children():
            self.invitations_tree.delete(item)

        try:
            invitations = self.dashboard.get_pending_invitations()

            for invitation in invitations:
                self.invitations_tree.insert('', tk.END, values=(
                    invitation['room_name'],
                    invitation['invited_by'],
                    invitation['invited_at']
                ), tags=(invitation['id'],))
        except Exception as e:
            messagebox.showerror("Error", f"Error loading invitations: {e}")

    def accept_invitation(self):
        selection = self.invitations_tree.selection()
        if selection:
            item = self.invitations_tree.item(selection[0])
            invitation_id = item['tags'][0]

            try:
                if self.dashboard.respond_to_invitation(invitation_id, accept=True):
                    messagebox.showinfo("Success", "Invitation accepted!")
                    self.load_invitations()
                else:
                    messagebox.showerror("Error", "Failed to accept invitation")
            except Exception as e:
                messagebox.showerror("Error", f"Error accepting invitation: {e}")

    def decline_invitation(self):
        selection = self.invitations_tree.selection()
        if selection:
            item = self.invitations_tree.item(selection[0])
            invitation_id = item['tags'][0]

            try:
                if self.dashboard.respond_to_invitation(invitation_id, accept=False):
                    messagebox.showinfo("Success", "Invitation declined")
                    self.load_invitations()
                else:
                    messagebox.showerror("Error", "Failed to decline invitation")
            except Exception as e:
                messagebox.showerror("Error", f"Error declining invitation: {e}")


class RoomSwitcherDialog:
    """Quick-find palette over the joined rooms. Type to filter, Enter to open."""

    def __init__(self, parent, dashboard, current_room_id=None):
        self.dashboard = dashboard
        self.parent = parent
        self.current_room_id = current_room_id
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Switch room")
        self.dialog.geometry("420x360")
        self.dialog.transient(parent)
        self.dialog.bind('<Escape>', lambda e: self.dialog.destroy())
        self._rooms = []
        self._build()
        self._reload()
        self.dialog.after(50, self.entry.focus_set)

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        self.query_var = tk.StringVar()
        self.entry = ttk.Entry(frame, textvariable=self.query_var)
        self.entry.pack(fill=tk.X)
        self.entry.bind('<Return>', lambda e: self._open_selected())
        self.entry.bind('<Down>', self._focus_list)
        self.query_var.trace_add('write', lambda *_: self._render())

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.listbox = tk.Listbox(list_frame, activestyle='dotbox')
        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                           command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.bind('<Return>', lambda e: self._open_selected())
        self.listbox.bind('<Double-1>', lambda e: self._open_selected())

    def _reload(self):
        try:
            data = self.dashboard.get_chat_rooms('joined') or {}
            self._rooms = data.get('rooms', []) or []
        except Exception:
            self._rooms = []
        self._render()

    def _render(self):
        needle = (self.query_var.get() or '').strip().lower()
        self.listbox.delete(0, tk.END)
        self._filtered = []
        for r in self._rooms:
            label_parts = []
            if r.get('icon'):
                label_parts.append(r['icon'])
            if r.get('is_favourite'):
                label_parts.append("★")
            label_parts.append(r['name'])
            if r.get('category'):
                label_parts.append(f"  · {r['category']}")
            label = " ".join(label_parts)
            if needle and needle not in label.lower() \
                    and needle not in (r.get('description') or '').lower():
                continue
            self._filtered.append(r)
            self.listbox.insert(tk.END, label)
        if self.listbox.size():
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(0)

    def _focus_list(self, _event=None):
        if self.listbox.size():
            self.listbox.focus_set()
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(0)
        return "break"

    def _open_selected(self):
        sel = self.listbox.curselection()
        idx = sel[0] if sel else 0
        if not getattr(self, '_filtered', None):
            return
        if idx >= len(self._filtered):
            return
        room = self._filtered[idx]
        if room['id'] == self.current_room_id:
            self.dialog.destroy()
            return
        self.dialog.destroy()
        from .chat_room_window import ChatRoomWindow
        ChatRoomWindow(self.parent, self.dashboard, room['id'], room['name'])

