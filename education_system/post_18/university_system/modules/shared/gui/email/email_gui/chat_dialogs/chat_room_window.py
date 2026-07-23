from ._common import (
    askinteger,
    askstring,
    datetime,
    filedialog,
    logger,
    messagebox,
    os,
    scrolledtext,
    tk,
    ttk,
    webbrowser,
)
from .room_admin import ManageMembersDialog
from .room_tools import PollComposerDialog, QueueDialog
from .room_notes import RoomNotesDialog
from .misc_dialogs import UserProfileDialog

class ChatRoomWindow:
    """Enhanced chat room interface"""
    PAGE_SIZE = 50
    POLL_MS = 2000          # poll interval for new messages / typing / presence
    TYPING_TTL_SEC = 5      # how long a typing indicator stays alive
    TYPING_PING_MS = 2000   # min interval between outbound typing pings
    PRESENCE_PING_MS = 10000  # heartbeat interval
    REACTION_PALETTE = ["👍", "❤️", "🎉", "😂", "✅", "❓"]
    ROLE_BADGES = {
        'admin':      ('ADMIN',      '#ffffff', '#b30000'),
        'staff':      ('STAFF',      '#ffffff', '#1a5fb4'),
        'instructor': ('INSTRUCTOR', '#ffffff', '#2a8a2a'),
        'ta':         ('TA',         '#000000', '#f7c948'),
        'student':    ('STUDENT',    '#000000', '#dddddd'),
    }

    def __init__(self, parent, dashboard, room_id, room_name):
        self.dashboard = dashboard
        self.room_id = room_id
        self.room_name = room_name
        self.current_page = 1
        self.total_pages = 1
        self.last_message_id = 0          # highest id currently displayed
        self.oldest_message_id = None
        self._messages_by_id = {}         # cache of message dicts currently rendered
        self._poll_job = None
        self._presence_job = None
        self._last_typing_ping = 0.0
        self._closed = False
        self._pending_reply = None        # {'id': int, 'snippet': str, 'sender': str}
        self._pending_attachment = None   # {'path', 'name', 'mime', 'size'}
        self._context_message_id = None
        self._current_user_id = None
        self._current_username = None
        if dashboard and getattr(dashboard, 'auth', None) and dashboard.auth.current_user:
            self._current_user_id = dashboard.auth.current_user.get('id')
            self._current_username = dashboard.auth.current_user.get('username')

        # Fetch room metadata (announcement-mode, office hours, etc.)
        self.room_info = {}
        try:
            self.room_info = self.dashboard.get_room_info(room_id) or {}
        except Exception:
            self.room_info = {}

        self.window = tk.Toplevel(parent)
        self.window.title(f"Chat Room: {room_name}")
        self.window.geometry("1400x900")
        self.window.minsize(1200, 800)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        # Keyboard shortcuts (window-level)
        self.window.bind('<Escape>', lambda e: self._on_close())
        self.window.bind('<Control-Return>', lambda e: (self.send_message(), "break")[1])
        self.window.bind('<Control-k>', self._open_room_switcher)
        self.window.bind('<Control-K>', self._open_room_switcher)

        self.create_widgets()
        self._update_mode_banner()
        self.load_messages()
        self._refresh_members_panel()
        # Kick off background loops
        self._poll_job = self.window.after(self.POLL_MS, self._poll)
        self._presence_job = self.window.after(0, self._presence_heartbeat)

    def create_widgets(self):
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Mode banner (announcement / office-hours). Hidden by default.
        self.mode_banner = ttk.Label(main_frame, text="", anchor=tk.W,
                                     background="#fff7d6", foreground="#664d00",
                                     font=("TkDefaultFont", 9))

        # Top toolbar: history + presence + search
        history_frame = ttk.Frame(main_frame)
        history_frame.pack(fill=tk.X)
        self.load_older_button = ttk.Button(history_frame, text="Load Older", command=self.load_older)
        self.load_older_button.pack(side=tk.LEFT)
        self.history_status = ttk.Label(history_frame, text="")
        self.history_status.pack(side=tk.LEFT, padx=10)
        self.presence_label = ttk.Label(history_frame, text="● 0 online", foreground="#888")
        self.presence_label.pack(side=tk.RIGHT)
        ttk.Button(history_frame, text="Pinned", command=self.show_pinned).pack(side=tk.RIGHT, padx=5)

        # Search bar (in-room)
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(4, 4))
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        search_entry.bind('<Return>', lambda e: self.do_search())
        ttk.Button(search_frame, text="Find", command=self.do_search).pack(side=tk.LEFT)

        # Resizable two-pane layout: chat on the left, members sidebar on the right.
        self.paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)
        chat_pane = ttk.Frame(self.paned)
        self.members_pane = ttk.Frame(self.paned)
        self.paned.add(chat_pane, weight=4)
        self.paned.add(self.members_pane, weight=1)

        # Members sidebar contents
        ttk.Label(self.members_pane, text="Members",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, padx=4, pady=(2, 2))
        cols = ("Status", "Member", "Role")
        self.members_tree = ttk.Treeview(self.members_pane, columns=cols, show="headings")
        self.members_tree.bind("<Button-3>", self._on_member_right_click)
        for c in cols:
            self.members_tree.heading(c, text=c)
        self.members_tree.column("Status", width=70, anchor=tk.CENTER)
        self.members_tree.column("Member", width=160)
        self.members_tree.column("Role", width=80, anchor=tk.CENTER)
        self.members_tree.tag_configure("online", foreground="#2a8a2a")
        self.members_tree.tag_configure("offline", foreground="#888")
        members_sb = ttk.Scrollbar(self.members_pane, orient=tk.VERTICAL,
                                   command=self.members_tree.yview)
        self.members_tree.configure(yscrollcommand=members_sb.set)
        self.members_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0))
        members_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._members_visible = True
        self._cached_members = []

        # Chat display area
        self.chat_text = scrolledtext.ScrolledText(chat_pane, state=tk.DISABLED, wrap=tk.WORD, height=20)
        self.chat_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        # Tags for rendering
        self.chat_text.tag_configure("header", font=("TkDefaultFont", 10, "bold"))
        self.chat_text.tag_configure("timestamp", foreground="#888")
        self.chat_text.tag_configure("mention", foreground="#b30000", font=("TkDefaultFont", 10, "bold"))
        self.chat_text.tag_configure("self_mention", background="#fff4b8", foreground="#b30000",
                                     font=("TkDefaultFont", 10, "bold"))
        self.chat_text.tag_configure("bold", font=("TkDefaultFont", 10, "bold"))
        self.chat_text.tag_configure("italic", font=("TkDefaultFont", 10, "italic"))
        self.chat_text.tag_configure("inline_code", font=("TkFixedFont", 10),
                                     background="#f0f0f0")
        self.chat_text.tag_configure("code_block", font=("TkFixedFont", 10),
                                     background="#f5f5f5", lmargin1=20, lmargin2=20,
                                     spacing1=4, spacing3=4)
        self.chat_text.tag_configure("url", foreground="#1a5fb4", underline=True)
        self.chat_text.tag_configure("reply_quote", foreground="#666", lmargin1=20, lmargin2=20,
                                     font=("TkDefaultFont", 9, "italic"))
        self.chat_text.tag_configure("deleted", foreground="#888",
                                     font=("TkDefaultFont", 10, "italic"))
        self.chat_text.tag_configure("edited", foreground="#888",
                                     font=("TkDefaultFont", 9, "italic"))
        self.chat_text.tag_configure("pinned", foreground="#b8860b",
                                     font=("TkDefaultFont", 10, "bold"))
        self.chat_text.tag_configure("attachment", foreground="#1a5fb4", underline=True,
                                     lmargin1=20, lmargin2=20)
        self.chat_text.tag_configure("reaction", background="#eaeaea", lmargin1=20, lmargin2=20)
        self.chat_text.tag_configure("reaction_mine", background="#cde4ff",
                                     lmargin1=20, lmargin2=20)
        self.chat_text.tag_configure("search_hit", background="#ffe680")
        self.chat_text.tag_configure("due_date", foreground="#7a4f00",
                                     background="#fff4d6",
                                     font=("TkDefaultFont", 10, "bold"))
        self.chat_text.tag_configure("team_mention", foreground="#ffffff",
                                     background="#1a5fb4",
                                     font=("TkDefaultFont", 9, "bold"))
        # Role badge tags (one per known role + a fallback).
        for role, (label, fg, bg) in self.ROLE_BADGES.items():
            self.chat_text.tag_configure(
                f"role_{role}", foreground=fg, background=bg,
                font=("TkDefaultFont", 8, "bold"),
            )
        self.chat_text.tag_configure("poll_box", background="#f5f5f5",
                                     lmargin1=20, lmargin2=20,
                                     spacing1=4, spacing3=4)
        self.chat_text.tag_configure("poll_question",
                                     font=("TkDefaultFont", 10, "bold"),
                                     lmargin1=20, lmargin2=20)
        self.chat_text.tag_configure("poll_meta", foreground="#666",
                                     lmargin1=20, lmargin2=20,
                                     font=("TkDefaultFont", 9, "italic"))
        self.chat_text.tag_configure("poll_option", lmargin1=30, lmargin2=30)
        self.chat_text.tag_configure("poll_chosen", lmargin1=30, lmargin2=30,
                                     foreground="#1a5fb4",
                                     font=("TkDefaultFont", 10, "bold"))
        self.chat_text.bind("<Button-3>", self._on_right_click)

        # Typing indicator (within the chat pane)
        self.typing_label = ttk.Label(chat_pane, text="", foreground="#666")
        self.typing_label.pack(fill=tk.X, pady=(0, 2))

        # Reply / attachment indicator strip (within the chat pane)
        self.indicator_frame = ttk.Frame(chat_pane)
        self.indicator_frame.pack(fill=tk.X, pady=(0, 2))
        self.reply_label = ttk.Label(self.indicator_frame, text="", foreground="#1a5fb4")
        self.reply_cancel = ttk.Button(self.indicator_frame, text="✕", width=2,
                                       command=self.clear_reply)
        self.attach_label = ttk.Label(self.indicator_frame, text="", foreground="#1a5fb4")
        self.attach_cancel = ttk.Button(self.indicator_frame, text="✕", width=2,
                                        command=self.clear_attachment)

        # Message input (multi-line). Enter sends, Shift+Enter inserts newline.
        input_frame = ttk.Frame(chat_pane)
        input_frame.pack(fill=tk.X, pady=(0, 10))

        self.message_entry = tk.Text(input_frame, height=3, wrap=tk.WORD)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.message_entry.bind('<Return>', self._on_return)
        self.message_entry.bind('<Shift-Return>', lambda e: None)
        self.message_entry.bind('<KeyRelease>', self._on_key_release)

        button_col = ttk.Frame(input_frame)
        button_col.pack(side=tk.RIGHT)
        ttk.Button(button_col, text="📎 Attach", command=self.attach_file).pack(fill=tk.X)
        ttk.Button(button_col, text="Send", command=self.send_message).pack(fill=tk.X, pady=(2, 0))

        # Controls frame
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X)

        ttk.Button(controls_frame, text="Members", command=self.show_members).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Invite", command=self.invite_user).pack(side=tk.LEFT, padx=5)
        # Admins/creator: full member-management dialog (kick / ban / mute /
        # promote / transfer ownership). Hidden for ordinary members.
        if (self.room_info or {}).get('is_admin'):
            ttk.Button(controls_frame, text="Manage…",
                       command=self.open_manage_members
                       ).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Seen By", command=self.show_seen_by).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Notes", command=self.open_notes).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Poll…", command=self.create_poll).pack(side=tk.LEFT, padx=5)
        # Course-linked controls (only meaningful when the room maps to a module)
        if (self.room_info or {}).get('linked_course_code'):
            ttk.Button(controls_frame, text="📚 Module",
                       command=self.show_module_info).pack(side=tk.LEFT, padx=5)
            ttk.Button(controls_frame, text="Post Due Dates",
                       command=self.post_due_dates).pack(side=tk.LEFT, padx=5)
        self.hand_button = ttk.Button(controls_frame, text="🙋 Raise Hand",
                                      command=self.toggle_hand)
        self.hand_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Queue", command=self.show_queue).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Leave Room", command=self.leave_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Close", command=self._on_close).pack(side=tk.RIGHT, padx=5)

    # ---- rendering helpers ----------------------------------------------

    def _is_at_bottom(self):
        """True if the chat text view is scrolled to (or near) the bottom."""
        try:
            yview = self.chat_text.yview()
            return yview[1] >= 0.999
        except Exception:
            return True

    def _format_size(self, n):
        if not n:
            return ""
        try:
            n = int(n)
        except (TypeError, ValueError):
            return ""
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
            n /= 1024.0
        return f"{n:.1f} TB"

    def _insert_message(self, msg, position="end"):
        """Render a single message at the end (only — used for initial load
        and live polling). Records the message in the cache by id."""
        if position != "end":
            # Older-page prepends rebuild from cache via _redraw_all.
            self._messages_by_id[msg.get('id')] = msg
            return
        msg_id = msg.get('id')
        if msg_id is None:
            return
        self._messages_by_id[msg_id] = msg
        self._render_one_at_end(msg)

    def _render_one_at_end(self, msg):
        msg_id = msg['id']
        msg_tag = f"m{msg_id}"
        start_index = self.chat_text.index("end-1c")

        # Header line: [time] [BADGE] sender ★ pinned
        timestamp = (msg.get('sent_at') or '')[:16]
        sender = msg.get('sender', 'Unknown')
        self.chat_text.insert(tk.END, f"[{timestamp}] ", ("timestamp",))
        role = (msg.get('sender_role') or '').lower()
        if role in self.ROLE_BADGES:
            label, _, _ = self.ROLE_BADGES[role]
            self.chat_text.insert(tk.END, f" {label} ", (f"role_{role}",))
            self.chat_text.insert(tk.END, " ")
        sender_tag = f"sender_{msg_id}"
        self.chat_text.insert(tk.END, sender, ("header", sender_tag))
        sender_uid = msg.get('sender_id')
        if sender_uid:
            self.chat_text.tag_bind(
                sender_tag, "<Button-1>",
                lambda e, uid=sender_uid: UserProfileDialog(self.window, self.dashboard, uid),
            )
        if msg.get('pinned_at'):
            self.chat_text.insert(tk.END, "  ★ pinned", ("pinned",))
        self.chat_text.insert(tk.END, "\n")

        # Reply quote
        reply = msg.get('reply_preview')
        if reply:
            snippet = (reply.get('content') or '').replace('\n', ' ')
            if len(snippet) > 80:
                snippet = snippet[:77] + '…'
            if reply.get('is_deleted'):
                snippet = "(deleted message)"
            self.chat_text.insert(tk.END, f"  ↪ {reply.get('sender')}: {snippet}\n",
                                  ("reply_quote",))

        # Body
        if msg.get('is_deleted'):
            self.chat_text.insert(tk.END, "  [deleted message]\n", ("deleted",))
        elif msg.get('poll'):
            self._render_poll(msg.get('poll'))
        else:
            content = msg.get('content') or ''
            if content.startswith('[due]'):
                self.chat_text.insert(tk.END, f"  📅 {content[len('[due]'):].strip()}\n",
                                      ("due_date",))
            else:
                if content:
                    self._render_inline(content, leading="  ", track_self_mention=True)
                if msg.get('edited_at'):
                    self.chat_text.insert(tk.END, "  (edited)\n", ("edited",))

        # Attachment
        att_path = msg.get('attachment_path')
        if att_path:
            att_name = msg.get('attachment_name') or att_path.rsplit('/', 1)[-1]
            size_str = self._format_size(msg.get('attachment_size'))
            label = f"  📎 {att_name}" + (f" ({size_str})" if size_str else "")
            att_tag = f"att_{msg_id}"
            self.chat_text.insert(tk.END, label + "\n", ("attachment", att_tag))
            self.chat_text.tag_bind(att_tag, "<Button-1>",
                                    lambda e, p=att_path: self._open_attachment(p))

        # Reactions bar
        reactions = msg.get('reactions') or []
        if reactions:
            self.chat_text.insert(tk.END, "  ")
            for rxn in reactions:
                emoji = rxn['emoji']
                count = rxn['count']
                tag = "reaction_mine" if rxn.get('mine') else "reaction"
                rxn_tag = f"rxn_{msg_id}_{emoji}"
                chip = f" {emoji} {count} "
                self.chat_text.insert(tk.END, chip, (tag, rxn_tag))
                self.chat_text.tag_bind(
                    rxn_tag, "<Button-1>",
                    lambda e, mid=msg_id, em=emoji, mine=rxn.get('mine'):
                        self._toggle_reaction(mid, em, mine),
                )
                self.chat_text.insert(tk.END, " ")
            self.chat_text.insert(tk.END, "\n")

        self.chat_text.insert(tk.END, "\n")  # blank separator
        end_index = self.chat_text.index("end-1c")
        # Tag entire range so right-click can find the message id.
        self.chat_text.tag_add(msg_tag, start_index, end_index)

    def _render_inline(self, content, leading="", track_self_mention=False):
        """Render `content` with markdown (bold/italic/inline-code/code-block),
        @mentions, and URL auto-linking. Inserts at end."""
        # Code block first (multi-line), then inline parsing on the rest.
        import re
        cb_re = re.compile(r"```(.*?)```", re.DOTALL)
        pos = 0
        for m in cb_re.finditer(content):
            if m.start() > pos:
                self._render_inline_simple(
                    leading + content[pos:m.start()],
                    track_self_mention=track_self_mention,
                )
            block = m.group(1).strip("\n")
            for line in block.split("\n"):
                self.chat_text.insert(tk.END, line + "\n", ("code_block",))
            pos = m.end()
        if pos < len(content):
            self._render_inline_simple(
                leading + content[pos:],
                track_self_mention=track_self_mention,
            )

    def _render_inline_simple(self, text, track_self_mention=False):
        """Render text with inline markdown + mentions + URLs (no code blocks).
        Each input line ends with a newline."""
        import re
        # Split into lines so leading spacing is preserved per line.
        lines = text.split("\n")
        for i, line in enumerate(lines):
            self._tokenize_inline_line(line, track_self_mention)
            # Re-add the newline (split removed it). The last fragment may
            # already have ended at an internal newline, so we add one too.
            if i < len(lines) - 1:
                self.chat_text.insert(tk.END, "\n")
        # Ensure final newline so the next render starts on its own line.
        if not text.endswith("\n"):
            self.chat_text.insert(tk.END, "\n")

    def _tokenize_inline_line(self, line, track_self_mention):
        """Walk a single line, emitting (text, tags) for bold/italic/inline-
        code/mention/url tokens; everything else is plain."""
        import re
        # Master pattern: order matters; bold before italic, code before others.
        pattern = re.compile(
            r"(?P<code>`[^`\n]+`)"
            r"|(?P<bold>\*\*[^*\n]+\*\*)"
            r"|(?P<italic>\*[^*\n]+\*)"
            r"|(?P<url>https?://[^\s)>\]]+)"
            r"|(?P<team>@team:[\w\-]+)"
            r"|(?P<mention>@\w+)"
        )
        pos = 0
        for m in pattern.finditer(line):
            if m.start() > pos:
                self.chat_text.insert(tk.END, line[pos:m.start()])
            kind = m.lastgroup
            text = m.group(0)
            if kind == "code":
                self.chat_text.insert(tk.END, text[1:-1], ("inline_code",))
            elif kind == "bold":
                self.chat_text.insert(tk.END, text[2:-2], ("bold",))
            elif kind == "italic":
                self.chat_text.insert(tk.END, text[1:-1], ("italic",))
            elif kind == "url":
                url_tag = f"url_{abs(hash(text)) & 0xffffffff}"
                self.chat_text.insert(tk.END, text, ("url", url_tag))
                # Inline domain badge as a minimal "preview"
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(text).netloc
                    if domain:
                        self.chat_text.insert(tk.END, f" [{domain}]", ("timestamp",))
                except Exception:
                    pass
                self.chat_text.tag_bind(
                    url_tag, "<Button-1>",
                    lambda e, u=text: webbrowser.open(u),
                )
            elif kind == "team":
                team_name = text.split(":", 1)[1]
                team_tag = f"team_{abs(hash(team_name)) & 0xffffffff}"
                self.chat_text.insert(tk.END, f" @{team_name} ",
                                      ("team_mention", team_tag))
                self.chat_text.tag_bind(
                    team_tag, "<Button-1>",
                    lambda e, name=team_name: self._show_team_members(name),
                )
            elif kind == "mention":
                handle = text[1:]
                tag = "self_mention" if (
                    self._current_username and handle.lower() == self._current_username.lower()
                ) else "mention"
                if tag == "self_mention" and track_self_mention:
                    try:
                        self.window.bell()
                    except Exception:
                        pass
                mention_tag = f"mention_{abs(hash(handle)) & 0xffffffff}"
                self.chat_text.insert(tk.END, text, (tag, mention_tag))
                self.chat_text.tag_bind(
                    mention_tag, "<Button-1>",
                    lambda e, h=handle: self._open_profile_for_handle(h),
                )
            pos = m.end()
        if pos < len(line):
            self.chat_text.insert(tk.END, line[pos:])

    def _redraw_all(self):
        """Re-render every cached message (used after edits/deletes/reactions
        and after Load Older). Preserves scroll-bottom anchoring."""
        was_at_bottom = self._is_at_bottom()
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.delete("1.0", tk.END)
        ordered = sorted(self._messages_by_id.values(), key=lambda m: m['id'])
        for msg in ordered:
            self._render_one_at_end(msg)
        self.chat_text.config(state=tk.DISABLED)
        if was_at_bottom:
            self.chat_text.see(tk.END)

    def _update_history_controls(self):
        if self.current_page >= self.total_pages:
            self.load_older_button.config(state=tk.DISABLED)
        else:
            self.load_older_button.config(state=tk.NORMAL)
        self.history_status.config(
            text=f"Page {self.current_page} of {self.total_pages}"
        )

    def _hydrate_reactions(self, messages):
        """Attach reactions to each message dict in-place."""
        if not messages:
            return
        try:
            ids = [m['id'] for m in messages if m.get('id')]
            rmap = self.dashboard.get_chat_reactions_for_messages(ids) or {}
        except Exception:
            rmap = {}
        for m in messages:
            m['reactions'] = rmap.get(m['id'], [])

    def _hydrate_polls(self, messages):
        """For any '[poll]' message, attach the poll details inline."""
        if not messages:
            return
        for m in messages:
            content = m.get('content') or ''
            if content.startswith('[poll]'):
                try:
                    poll = self.dashboard.get_chat_poll(m['id'])
                except Exception:
                    poll = None
                if poll:
                    m['poll'] = poll

    def _render_poll(self, poll):
        """Render a poll: question, options as clickable lines, totals."""
        msg_id = poll.get('message_id')
        self.chat_text.insert(tk.END, f"  📊 {poll.get('question', '')}\n",
                              ("poll_question",))
        meta_bits = []
        if poll.get('multi_choice'):
            meta_bits.append("multi-choice")
        if poll.get('closes_at'):
            meta_bits.append(f"closes at {poll['closes_at']}")
        meta_bits.append(f"{poll.get('total_voters', 0)} voted")
        self.chat_text.insert(tk.END, "  " + " · ".join(meta_bits) + "\n",
                              ("poll_meta",))
        for opt in poll.get('options', []):
            tag_name = f"polloption_{msg_id}_{opt['id']}"
            line_tag = "poll_chosen" if opt.get('mine') else "poll_option"
            mark = "● " if opt.get('mine') else "○ "
            line = f"  {mark}{opt['label']}  ({opt['count']})\n"
            self.chat_text.insert(tk.END, line, (line_tag, tag_name))
            self.chat_text.tag_bind(
                tag_name, "<Button-1>",
                lambda e, mid=msg_id, oid=opt['id']: self._cast_vote(mid, oid),
            )

    def _cast_vote(self, message_id, option_id):
        if not self.dashboard:
            return
        try:
            poll = self._messages_by_id.get(message_id, {}).get('poll') or {}
            multi = bool(poll.get('multi_choice'))
            chosen = []
            if multi:
                # Toggle: include or exclude this option from the existing vote.
                current = {o['id'] for o in poll.get('options', []) if o.get('mine')}
                if option_id in current:
                    current.discard(option_id)
                else:
                    current.add(option_id)
                chosen = list(current)
            else:
                chosen = [option_id]
            ok = self.dashboard.vote_chat_poll(message_id, chosen)
            if ok:
                self.load_messages()
        except Exception as e:
            messagebox.showerror("Error", f"Vote failed: {e}")

    def _update_mode_banner(self):
        """Show announcement-only / office-hours banner when relevant."""
        bits = []
        info = self.room_info or {}
        if info.get('announcement_mode'):
            bits.append("📢 Announcement-only — only admins can post here.")
        oh_start = info.get('oh_starts_at')
        oh_end = info.get('oh_ends_at')
        if oh_start or oh_end:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if oh_end and now > oh_end:
                bits.append(f"🕒 Office hours closed (ended {oh_end}).")
            elif oh_start and now < oh_start:
                bits.append(f"🕒 Office hours not yet open (start {oh_start}).")
            else:
                bits.append(f"🕒 Office hours open until {oh_end or 'no end set'}.")
        if bits:
            self.mode_banner.config(text="  " + "  ".join(bits))
            # Sit at the top, above all other rows already packed.
            siblings = self.mode_banner.master.pack_slaves()
            if siblings and siblings[0] is not self.mode_banner:
                self.mode_banner.pack(fill=tk.X, before=siblings[0])
            elif not self.mode_banner.winfo_ismapped():
                self.mode_banner.pack(fill=tk.X)
        else:
            self.mode_banner.pack_forget()

    def load_messages(self):
        """Load the most recent page of messages."""
        try:
            if not self.dashboard:
                self.chat_text.config(state=tk.NORMAL)
                self.chat_text.delete(1.0, tk.END)
                self.chat_text.insert(1.0, "Error: Dashboard not initialized. Please restart the application.\n")
                self.chat_text.config(state=tk.DISABLED)
                return

            self.current_page = 1
            self._messages_by_id.clear()
            self.last_message_id = 0
            self.oldest_message_id = None

            messages_data = self.dashboard.get_chat_messages(
                self.room_id, page=1, limit=self.PAGE_SIZE
            )

            self.chat_text.config(state=tk.NORMAL)
            self.chat_text.delete(1.0, tk.END)

            if not messages_data or not isinstance(messages_data, dict):
                self.chat_text.insert(1.0, "No messages to display.\n")
                self.total_pages = 1
            else:
                self.total_pages = max(1, messages_data.get('total_pages', 1))
                messages = messages_data.get('messages', [])
                self._hydrate_reactions(messages)
                self._hydrate_polls(messages)
                if not messages:
                    self.chat_text.insert(1.0, "No messages yet. Start the conversation!\n")
                else:
                    for msg in messages:
                        self._render_one_at_end(msg)
                        self._messages_by_id[msg['id']] = msg
                        mid = msg.get('id') or 0
                        if mid > self.last_message_id:
                            self.last_message_id = mid
                        if self.oldest_message_id is None or mid < self.oldest_message_id:
                            self.oldest_message_id = mid

            self.chat_text.config(state=tk.DISABLED)
            self.chat_text.see(tk.END)
            self._update_history_controls()
            self._mark_read_up_to(self.last_message_id)
        except Exception as e:
            self.chat_text.config(state=tk.NORMAL)
            self.chat_text.delete(1.0, tk.END)
            self.chat_text.insert(1.0, f"Error loading messages: {e}\n")
            self.chat_text.config(state=tk.DISABLED)
            logger.exception("Error loading chat messages")

    def load_older(self):
        """Fetch the next older page and merge it into the cache, then redraw."""
        if not self.dashboard:
            return
        if self.current_page >= self.total_pages:
            return
        try:
            next_page = self.current_page + 1
            messages_data = self.dashboard.get_chat_messages(
                self.room_id, page=next_page, limit=self.PAGE_SIZE
            )
            if not messages_data or not isinstance(messages_data, dict):
                return
            messages = messages_data.get('messages', [])
            self._hydrate_reactions(messages)
            self.total_pages = max(1, messages_data.get('total_pages', self.total_pages))
            self.current_page = next_page
            for msg in messages:
                self._messages_by_id[msg['id']] = msg
                mid = msg['id']
                if self.oldest_message_id is None or mid < self.oldest_message_id:
                    self.oldest_message_id = mid
            self._redraw_all()
            self._update_history_controls()
        except Exception as e:
            logger.exception("Error loading older chat messages")
            messagebox.showerror("Error", f"Error loading older messages: {e}")

    def _on_return(self, event):
        """Enter sends; Shift+Enter falls through to insert newline."""
        if event.state & 0x0001:  # Shift held
            return None
        self.send_message()
        return "break"

    def send_message(self, event=None):
        """Send a message to the chat room"""
        if not self.dashboard:
            messagebox.showerror("Error", "Dashboard not initialized. Cannot send message.")
            return
        text = self.message_entry.get("1.0", tk.END).strip()
        att = self._pending_attachment
        if not text and not att:
            return
        try:
            kwargs = {}
            if self._pending_reply:
                kwargs['reply_to_id'] = self._pending_reply['id']
            if att:
                kwargs.update({
                    'attachment_path': att['path'],
                    'attachment_name': att['name'],
                    'attachment_mime': att.get('mime'),
                    'attachment_size': att.get('size'),
                })
            result = self.dashboard.send_chat_message(self.room_id, text, **kwargs)
            if result:
                self.message_entry.delete("1.0", tk.END)
                self.clear_reply()
                self.clear_attachment()
                try:
                    self.dashboard.clear_chat_typing(self.room_id)
                except Exception:
                    pass
                self._last_typing_ping = 0.0
                self._poll_once()
            else:
                messagebox.showerror("Error", "Failed to send message")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending message: {e}")
            logger.exception("Error sending chat message")

    # ---- live updates: polling, typing, presence -----------------------

    def _on_key_release(self, _event=None):
        """Throttled outbound typing ping while the user is composing."""
        if not self.dashboard:
            return
        # Skip pings on Return / when entry is empty
        if not self.message_entry.get("1.0", tk.END).strip():
            return
        import time
        now = time.monotonic()
        if (now - self._last_typing_ping) * 1000 < self.TYPING_PING_MS:
            return
        self._last_typing_ping = now
        try:
            self.dashboard.set_chat_typing(self.room_id)
        except Exception:
            logger.debug("set_chat_typing failed", exc_info=True)

    def _poll(self):
        if self._closed:
            return
        try:
            self._poll_once()
        finally:
            if not self._closed:
                self._poll_job = self.window.after(self.POLL_MS, self._poll)

    def _poll_once(self):
        """One batched fetch per tick — replaces the previous 5–7 separate
        dashboard calls. The realtime helper opens a single connection and
        returns messages, typing, presence, members (optional), and the
        per-room unread count in one shot."""
        if not self.dashboard:
            return
        try:
            state = self.dashboard.get_room_realtime_state(
                self.room_id,
                since_message_id=self.last_message_id,
                include_members=bool(getattr(self, '_members_visible', False)),
                typing_ttl_seconds=self.TYPING_TTL_SEC,
            ) or {}
        except Exception:
            state = {}
            logger.debug("get_room_realtime_state failed", exc_info=True)

        new_msgs = state.get('messages') or []
        if new_msgs:
            self._hydrate_reactions(new_msgs)
            try:
                ids = [m['id'] for m in new_msgs if m.get('content', '').startswith('[poll]')]
                if ids:
                    polls = self.dashboard.get_chat_polls_for_messages(ids) or {}
                    for m in new_msgs:
                        if m['id'] in polls:
                            m['poll'] = polls[m['id']]
            except Exception:
                pass
            was_at_bottom = self._is_at_bottom()
            self.chat_text.config(state=tk.NORMAL)
            for msg in new_msgs:
                self._render_one_at_end(msg)
                self._messages_by_id[msg['id']] = msg
                mid = msg.get('id') or 0
                if mid > self.last_message_id:
                    self.last_message_id = mid
            self.chat_text.config(state=tk.DISABLED)
            if was_at_bottom:
                self.chat_text.see(tk.END)
                self._mark_read_up_to(self.last_message_id)
        elif state.get('last_message_id'):
            # Keep our pointer in sync even when the probe found nothing new.
            self.last_message_id = max(
                self.last_message_id or 0,
                int(state.get('last_message_id') or 0),
            )

        self._render_typing(state.get('typing_users') or [])

        presence = state.get('presence') or {}
        online = int(presence.get('online') or 0)
        total = int(presence.get('total') or 0)
        colour = "#2a8a2a" if online else "#888"
        try:
            self.presence_label.config(
                text=f"● {online}/{total} online", foreground=colour,
            )
        except Exception:
            pass

        # Members sidebar (already fetched in the same round trip)
        if getattr(self, '_members_visible', False):
            members = state.get('members')
            if members is not None:
                self._render_members_panel(members)

    def _render_members_panel(self, members):
        """Render the cached member list directly (no extra DB calls)."""
        if not getattr(self, 'members_tree', None):
            return
        self._cached_members = members
        for it in self.members_tree.get_children():
            self.members_tree.delete(it)
        for m in members:
            online = m.get('is_online', False)
            role = ("Creator" if m.get('is_creator')
                    else "Admin" if m.get('is_admin') else "Member")
            self.members_tree.insert(
                '', tk.END,
                values=(
                    "● online" if online else "○ offline",
                    f"{m['full_name']} (@{m['username']})",
                    role,
                ),
                tags=(str(m['user_id']),
                      "online" if online else "offline"),
            )

    def _render_typing(self, names):
        if not names:
            self.typing_label.config(text="")
            return
        if len(names) == 1:
            text = f"{names[0]} is typing…"
        elif len(names) == 2:
            text = f"{names[0]} and {names[1]} are typing…"
        else:
            text = f"{names[0]}, {names[1]} and {len(names) - 2} others are typing…"
        self.typing_label.config(text=text)

    def _presence_heartbeat(self):
        if self._closed:
            return
        try:
            if self.dashboard:
                self.dashboard.update_chat_presence(self.room_id)
        except Exception:
            logger.debug("update_chat_presence failed", exc_info=True)
        self._presence_job = self.window.after(self.PRESENCE_PING_MS, self._presence_heartbeat)

    def _mark_read_up_to(self, message_id):
        if not self.dashboard or not message_id:
            return
        try:
            self.dashboard.mark_chat_messages_read(self.room_id, up_to_message_id=message_id)
        except Exception:
            logger.debug("mark_chat_messages_read failed", exc_info=True)

    def _on_close(self):
        self._closed = True
        for job in (self._poll_job, self._presence_job):
            if job is not None:
                try:
                    self.window.after_cancel(job)
                except Exception:
                    pass
        self._poll_job = None
        self._presence_job = None
        # Clear typing flag so other members don't see a stale "typing…".
        try:
            if self.dashboard:
                self.dashboard.clear_chat_typing(self.room_id)
        except Exception:
            pass
        # Mark the latest message read on exit.
        self._mark_read_up_to(self.last_message_id)
        self.window.destroy()

    def show_members(self):
        try:
            # Toggle the embedded sidebar instead of popping a dialog.
            if self._members_visible:
                self.paned.forget(self.members_pane)
                self._members_visible = False
            else:
                self.paned.add(self.members_pane, weight=1)
                self._members_visible = True
                self._refresh_members_panel()
        except Exception as e:
            messagebox.showerror("Error", f"Error toggling members: {e}")

    def _refresh_members_panel(self):
        """Re-populate the members sidebar from get_room_members + presence.
        Cheap enough to call on each poll tick."""
        if not getattr(self, 'members_tree', None) or not self._members_visible:
            return
        try:
            members = self.dashboard.get_room_members(self.room_id) or []
            presence = {p['user_id']: p
                        for p in (self.dashboard.get_chat_presence(self.room_id) or [])}
        except Exception:
            return
        self._cached_members = members
        for it in self.members_tree.get_children():
            self.members_tree.delete(it)
        for m in members:
            p = presence.get(m['user_id'], {})
            online = p.get('is_online', False)
            role = ("Creator" if m.get('is_creator')
                    else "Admin" if m.get('is_admin') else "Member")
            self.members_tree.insert(
                '', tk.END,
                values=(
                    "● online" if online else "○ offline",
                    f"{m['full_name']} (@{m['username']})",
                    role,
                ),
                tags=(str(m['user_id']),
                      "online" if online else "offline"),
            )

    def open_manage_members(self):
        """Admin shortcut: open the full member-management dialog (kick / ban /
        mute / promote / transfer ownership / Bans viewer)."""
        if not (self.room_info or {}).get('is_admin'):
            messagebox.showinfo("Manage members",
                                "You need to be a room admin to manage members.")
            return
        ManageMembersDialog(self.window, self.dashboard, self.room_info,
                            refresh_callback=self._refresh_members_panel)

    def _on_member_right_click(self, event):
        """Admin: right-click a sidebar row for quick kick / ban / promote /
        demote without leaving the chat window."""
        if not (self.room_info or {}).get('is_admin'):
            return
        iid = self.members_tree.identify_row(event.y)
        if not iid:
            return
        self.members_tree.selection_set(iid)
        tags = self.members_tree.item(iid).get('tags') or ()
        target_uid = None
        for t in tags:
            if str(t).isdigit():
                target_uid = int(t)
                break
        if not target_uid:
            return
        # Find the cached member dict so we know creator/admin status.
        member = next(
            (m for m in (self._cached_members or [])
             if m.get('user_id') == target_uid),
            {},
        )
        if member.get('is_creator'):
            return  # no actions on the creator

        menu = tk.Menu(self.window, tearoff=0)
        if member.get('is_admin'):
            menu.add_command(
                label="Demote to member",
                command=lambda: self._do_member_action(
                    self.dashboard.set_room_admin, target_uid, False,
                ),
            )
        else:
            menu.add_command(
                label="Promote to admin",
                command=lambda: self._do_member_action(
                    self.dashboard.set_room_admin, target_uid, True,
                ),
            )
        menu.add_separator()
        menu.add_command(
            label="Kick from room",
            command=lambda: self._confirm_and(
                "Kick", "Remove this member from the room?",
                self.dashboard.kick_room_member, target_uid,
            ),
        )
        menu.add_command(
            label="Ban from room…",
            command=lambda: self._ban_from_sidebar(target_uid),
        )
        menu.add_command(
            label="Mute…",
            command=lambda: self._mute_from_sidebar(target_uid),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _do_member_action(self, fn, target_uid, *args):
        try:
            ok = fn(self.room_id, target_uid, *args)
            if ok:
                self._refresh_members_panel()
            else:
                messagebox.showerror("Error",
                                     "Action denied (creator can't be acted on, "
                                     "or you lack permission).")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _confirm_and(self, title, prompt, fn, target_uid, *args):
        if not messagebox.askyesno(title, prompt, parent=self.window):
            return
        # Kick path takes a reason kwarg for the email notice; ask for it.
        if fn is getattr(self.dashboard, 'kick_room_member', None):
            reason = askstring(
                "Kick reason",
                "Reason (optional, included in the email notice):",
                parent=self.window,
            ) or ''
            try:
                ok = self.dashboard.kick_room_member(
                    self.room_id, target_uid, reason=reason,
                )
                if ok:
                    self._refresh_members_panel()
                else:
                    messagebox.showerror("Error",
                                         "Action denied (creator can't be acted on, "
                                         "or you lack permission).")
            except Exception as e:
                messagebox.showerror("Error", str(e))
            return
        self._do_member_action(fn, target_uid, *args)

    def _ban_from_sidebar(self, target_uid):
        if not messagebox.askyesno(
            "Ban member",
            "Ban this user from the room? They will be removed and unable "
            "to rejoin until you unban them.",
            parent=self.window,
        ):
            return
        reason = askstring("Ban reason",
                           "Reason (optional, shown in audit log):",
                           parent=self.window) or ''
        try:
            ok = self.dashboard.ban_room_member(
                self.room_id, target_uid, banned=True, reason=reason,
            )
            if ok:
                self._refresh_members_panel()
            else:
                messagebox.showerror("Error", "Could not ban (creator?).")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _mute_from_sidebar(self, target_uid):
        minutes = askinteger("Mute", "Mute for how many minutes?",
                             parent=self.window, minvalue=1, maxvalue=10080)
        if not minutes:
            return
        reason = askstring(
            "Mute reason",
            "Reason (optional, included in the email notice):",
            parent=self.window,
        ) or ''
        try:
            ok = self.dashboard.mute_room_member(
                self.room_id, target_uid, minutes, reason=reason,
            )
            if ok:
                self._refresh_members_panel()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def show_seen_by(self):
        """Show who has read up to the latest message."""
        if not self.dashboard or not self.last_message_id:
            messagebox.showinfo("Seen By", "No messages yet.")
            return
        try:
            readers = self.dashboard.get_chat_message_readers(
                self.room_id, self.last_message_id
            )
            if not readers:
                messagebox.showinfo("Seen By", "Nobody else has read the latest message yet.")
                return
            lines = [f"• {r['full_name']} (@{r['username']})  — {r['read_at']}" for r in readers]
            messagebox.showinfo(
                f"Seen by {len(readers)}",
                "Latest message has been read by:\n\n" + "\n".join(lines),
            )
        except Exception as e:
            messagebox.showerror("Error", f"Error fetching read receipts: {e}")

    # ---- per-message context menu and actions --------------------------

    def _message_id_at_index(self, index):
        for tag in self.chat_text.tag_names(index):
            if tag.startswith("m") and tag[1:].isdigit():
                return int(tag[1:])
        return None

    def _on_right_click(self, event):
        index = self.chat_text.index(f"@{event.x},{event.y}")
        msg_id = self._message_id_at_index(index)
        if msg_id is None:
            return
        msg = self._messages_by_id.get(msg_id)
        if not msg:
            return
        self._context_message_id = msg_id
        is_own = msg.get('sender_id') == self._current_user_id
        is_deleted = msg.get('is_deleted')

        menu = tk.Menu(self.window, tearoff=0)
        if not is_deleted:
            if msg.get('poll'):
                menu.add_command(
                    label="Propose dates to calendar",
                    command=lambda: self._propose_poll_to_calendar(msg_id),
                )
                menu.add_separator()
            menu.add_command(label="Reply", command=lambda: self._reply_to(msg_id))
            react_menu = tk.Menu(menu, tearoff=0)
            for emoji in self.REACTION_PALETTE:
                react_menu.add_command(
                    label=emoji,
                    command=lambda em=emoji: self._toggle_reaction(msg_id, em, mine=False),
                )
            menu.add_cascade(label="React", menu=react_menu)
            pin_label = "Unpin" if msg.get('pinned_at') else "Pin"
            menu.add_command(label=pin_label,
                             command=lambda: self._toggle_pin(msg_id, not msg.get('pinned_at')))
            menu.add_separator()
            menu.add_command(label="Copy text", command=lambda: self._copy_message(msg_id))
            menu.add_command(label="Copy link", command=lambda: self._copy_message_link(msg_id))
            menu.add_separator()
            menu.add_command(label="Report message…",
                             command=lambda: self._report_message(msg_id))
            if is_own:
                menu.add_separator()
                menu.add_command(label="Edit…", command=lambda: self._edit_message(msg_id))
                menu.add_command(label="Delete", command=lambda: self._delete_message(msg_id))
        else:
            menu.add_command(label="Copy link", command=lambda: self._copy_message_link(msg_id))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _reply_to(self, msg_id):
        msg = self._messages_by_id.get(msg_id)
        if not msg:
            return
        snippet = (msg.get('content') or '').replace('\n', ' ')
        if len(snippet) > 60:
            snippet = snippet[:57] + '…'
        self._pending_reply = {
            'id': msg_id, 'snippet': snippet, 'sender': msg.get('sender'),
        }
        self.reply_label.config(text=f"↪ Replying to {msg.get('sender')}: {snippet}")
        self.reply_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.reply_cancel.pack(side=tk.LEFT)
        self.message_entry.focus_set()

    def clear_reply(self):
        self._pending_reply = None
        self.reply_label.pack_forget()
        self.reply_cancel.pack_forget()

    def attach_file(self):
        path = filedialog.askopenfilename(parent=self.window, title="Attach file")
        if not path:
            return
        try:
            size = os.path.getsize(path)
        except OSError:
            size = None
        name = os.path.basename(path)
        import mimetypes
        mime, _ = mimetypes.guess_type(path)
        self._pending_attachment = {
            'path': path, 'name': name, 'mime': mime, 'size': size,
        }
        size_str = self._format_size(size)
        self.attach_label.config(
            text=f"📎 {name}" + (f" ({size_str})" if size_str else "")
        )
        self.attach_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.attach_cancel.pack(side=tk.LEFT)

    def clear_attachment(self):
        self._pending_attachment = None
        self.attach_label.pack_forget()
        self.attach_cancel.pack_forget()

    def _open_attachment(self, path):
        if not path:
            return
        try:
            webbrowser.open(path if path.startswith(("http://", "https://")) else f"file://{os.path.abspath(path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open attachment: {e}")

    def _toggle_reaction(self, msg_id, emoji, mine):
        if not self.dashboard:
            return
        try:
            if mine:
                ok = self.dashboard.remove_chat_reaction(msg_id, emoji)
            else:
                ok = self.dashboard.add_chat_reaction(msg_id, emoji)
            if ok:
                self._refresh_message(msg_id)
        except Exception as e:
            messagebox.showerror("Error", f"Reaction failed: {e}")

    def _toggle_pin(self, msg_id, pin):
        try:
            ok = self.dashboard.pin_chat_message(msg_id, pin=pin)
            if ok:
                self._refresh_message(msg_id)
            else:
                messagebox.showerror("Error", "Could not change pin (need admin or own message).")
        except Exception as e:
            messagebox.showerror("Error", f"Pin failed: {e}")

    def _edit_message(self, msg_id):
        msg = self._messages_by_id.get(msg_id)
        if not msg:
            return
        new_text = askstring("Edit message", "New message text:",
                             initialvalue=msg.get('content', ''),
                             parent=self.window)
        if new_text is None:
            return
        new_text = new_text.strip()
        if not new_text:
            return
        try:
            ok = self.dashboard.edit_chat_message(msg_id, new_text)
            if ok:
                self._refresh_message(msg_id)
            else:
                messagebox.showerror("Error", "Edit failed (own messages only).")
        except Exception as e:
            messagebox.showerror("Error", f"Edit failed: {e}")

    def _delete_message(self, msg_id):
        if not messagebox.askyesno("Delete", "Delete this message?"):
            return
        try:
            ok = self.dashboard.delete_chat_message(msg_id)
            if ok:
                self._refresh_message(msg_id)
            else:
                messagebox.showerror("Error", "Delete failed (own messages or admin only).")
        except Exception as e:
            messagebox.showerror("Error", f"Delete failed: {e}")

    def _copy_message(self, msg_id):
        msg = self._messages_by_id.get(msg_id) or {}
        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(msg.get('content') or '')
        except Exception:
            pass

    def _report_message(self, msg_id):
        dlg = tk.Toplevel(self.window)
        dlg.title("Report message")
        dlg.geometry("420x260")
        dlg.transient(self.window)
        dlg.after(100, lambda: dlg.grab_set() if dlg.winfo_exists() else None)
        frame = ttk.Frame(dlg, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Why are you reporting this message?").pack(anchor=tk.W)
        text = scrolledtext.ScrolledText(frame, height=6, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, pady=(4, 8))
        escalate_var = tk.BooleanVar()
        ttk.Checkbutton(
            frame,
            text="Escalate as a safeguarding concern (creates a case file)",
            variable=escalate_var,
        ).pack(anchor=tk.W)

        def submit():
            reason = text.get("1.0", tk.END).strip()
            try:
                ok = self.dashboard.report_chat_message(
                    msg_id, reason,
                    escalate_safeguarding=bool(escalate_var.get()),
                )
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)
                return
            if ok:
                messagebox.showinfo(
                    "Reported",
                    "Thank you. A moderator will review the report.",
                    parent=dlg,
                )
                dlg.destroy()
            else:
                messagebox.showerror("Error", "Could not submit report.",
                                     parent=dlg)

        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="Submit", command=submit).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Cancel",
                   command=dlg.destroy).pack(side=tk.RIGHT, padx=5)

    def _copy_message_link(self, msg_id):
        link = f"chat://room/{self.room_id}/message/{msg_id}"
        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(link)
            self.window.update()
            messagebox.showinfo("Copied", f"Link copied:\n{link}")
        except Exception:
            pass

    def _refresh_message(self, msg_id):
        """Re-fetch the room (cheap path: reload current page) so the cache
        and the rendering reflect the latest server state."""
        # Simple, robust approach: reload page 1.
        self.load_messages()

    # ---- search and pinned panel ---------------------------------------

    def do_search(self):
        query = (self.search_var.get() or '').strip()
        if not query:
            # Clear highlights
            self.chat_text.tag_remove("search_hit", "1.0", tk.END)
            return
        if not self.dashboard:
            return
        try:
            hits = self.dashboard.search_chat_messages(query, room_id=self.room_id)
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {e}")
            return
        if not hits:
            messagebox.showinfo("Search", f"No matches for '{query}' in this room.")
            return
        # Highlight matches in the currently rendered window.
        self.chat_text.tag_remove("search_hit", "1.0", tk.END)
        idx = "1.0"
        first_hit = None
        while True:
            idx = self.chat_text.search(query, idx, nocase=True, stopindex=tk.END)
            if not idx:
                break
            end = f"{idx}+{len(query)}c"
            self.chat_text.tag_add("search_hit", idx, end)
            if first_hit is None:
                first_hit = idx
            idx = end
        if first_hit:
            self.chat_text.see(first_hit)
        messagebox.showinfo("Search", f"{len(hits)} match(es) in this room "
                                       "(highlighted in view; older matches may be off-screen).")

    def show_pinned(self):
        if not self.dashboard:
            return
        try:
            pinned = self.dashboard.get_pinned_messages(self.room_id) or []
        except Exception as e:
            messagebox.showerror("Error", f"Could not load pinned messages: {e}")
            return
        dlg = tk.Toplevel(self.window)
        dlg.title(f"Pinned in {self.room_name}")
        dlg.geometry("520x400")
        dlg.transient(self.window)
        if not pinned:
            ttk.Label(dlg, text="No pinned messages.").pack(padx=20, pady=20)
        else:
            txt = scrolledtext.ScrolledText(dlg, wrap=tk.WORD, state=tk.NORMAL)
            txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            for p in pinned:
                txt.insert(tk.END, f"★ [{p['sent_at'][:16]}] {p['sender']}\n",
                           ("header",))
                txt.insert(tk.END, f"  {p.get('content', '')}\n\n")
            txt.tag_configure("header", font=("TkDefaultFont", 10, "bold"),
                              foreground="#b8860b")
            txt.config(state=tk.DISABLED)
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=(0, 10))

    # ---- academics + staff_hr integration ------------------------------

    def show_module_info(self):
        code = (self.room_info or {}).get('linked_course_code')
        if not code:
            messagebox.showinfo("Module", "This room isn't linked to a module.")
            return
        try:
            info = self.dashboard.get_module_info(code)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if not info:
            messagebox.showinfo("Module",
                                f"No module record found for '{code}'.")
            return

        dlg = tk.Toplevel(self.window)
        dlg.title(f"Module: {info.get('name') or code}")
        dlg.geometry("560x420")
        dlg.transient(self.window)
        frame = ttk.Frame(dlg, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=info.get('name') or code,
                  font=("TkDefaultFont", 13, "bold")).pack(anchor=tk.W)
        ttk.Label(frame, foreground="#666",
                  text=f"{info.get('code')} · instructor: {info.get('instructor') or '—'}"
                  ).pack(anchor=tk.W, pady=(0, 8))
        if info.get('description'):
            desc = scrolledtext.ScrolledText(frame, height=5, wrap=tk.WORD)
            desc.insert("1.0", info['description'])
            desc.config(state=tk.DISABLED)
            desc.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(frame, text="Upcoming assignments",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=(4, 2))
        cols = ("Title", "Due", "Type", "Marks")
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=10)
        for c in cols:
            tree.heading(c, text=c)
        tree.column("Title", width=240)
        tree.column("Due", width=130)
        tree.column("Type", width=80, anchor=tk.CENTER)
        tree.column("Marks", width=60, anchor=tk.CENTER)
        for a in info.get('assignments', []):
            tree.insert('', tk.END, values=(
                a['title'], (a.get('due_date') or '')[:16],
                a.get('type') or '', a.get('max_marks') or '',
            ))
        tree.pack(fill=tk.BOTH, expand=True)

        ttk.Button(frame, text="Close", command=dlg.destroy).pack(pady=(8, 0))

    def post_due_dates(self):
        code = (self.room_info or {}).get('linked_course_code')
        if not code:
            messagebox.showinfo("Due dates", "This room isn't linked to a module.")
            return
        try:
            n = self.dashboard.post_assignment_due_dates(self.room_id)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if n:
            self.load_messages()
            messagebox.showinfo("Due dates",
                                f"Posted {n} new due-date notice(s).")
        else:
            messagebox.showinfo("Due dates",
                                "No new upcoming assignments to post.")

    def _propose_poll_to_calendar(self, msg_id):
        try:
            proposed = self.dashboard.propose_poll_dates_to_calendar(msg_id)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if not proposed:
            messagebox.showinfo(
                "Calendar",
                "No date-formatted options found in this poll, or the calendar "
                "table isn't available.\n\n"
                "Tip: write options like '2026-05-14' or '2026-05-14 14:00'.",
            )
            return
        lines = [f"• {p['date']}  ({p['option']})" for p in proposed]
        messagebox.showinfo(
            "Calendar",
            f"Added {len(proposed)} tentative event(s):\n\n" + "\n".join(lines),
        )

    def _open_profile_for_handle(self, handle):
        if not handle or not self.dashboard:
            return
        try:
            uid = self.dashboard.resolve_username_to_id(handle)
        except Exception:
            uid = None
        if not uid:
            messagebox.showinfo("Profile",
                                f"No profile found for @{handle}.")
            return
        UserProfileDialog(self.window, self.dashboard, uid)

    def _show_team_members(self, team_name):
        try:
            members = self.dashboard.get_team_members(team_name) or []
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        dlg = tk.Toplevel(self.window)
        dlg.title(f"Team: {team_name}")
        dlg.geometry("440x340")
        dlg.transient(self.window)
        frame = ttk.Frame(dlg, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        if not members:
            ttk.Label(frame, text=f"No staff found in department '{team_name}'.",
                      foreground="#666").pack(padx=10, pady=20)
        else:
            cols = ("Name", "Username", "Job title")
            tree = ttk.Treeview(frame, columns=cols, show="headings")
            for c in cols:
                tree.heading(c, text=c)
            tree.column("Name", width=160)
            tree.column("Username", width=110)
            tree.column("Job title", width=140)
            for m in members:
                tree.insert('', tk.END, values=(
                    m['full_name'],
                    f"@{m['username']}" if m['username'] else '',
                    m['job_title'],
                ))
            tree.pack(fill=tk.BOTH, expand=True)
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=(8, 0))

    def _open_room_switcher(self, _event=None):
        """Ctrl+K: jump to another room via a quick-find dialog."""
        from .rooms_create import RoomSwitcherDialog
        RoomSwitcherDialog(self.window, self.dashboard,
                           current_room_id=self.room_id)
        return "break"

    # ---- notes / polls / raise-hand / queue ----------------------------

    def open_notes(self):
        if not self.dashboard:
            return
        RoomNotesDialog(self.window, self.dashboard, self.room_id, self.room_name)

    def create_poll(self):
        PollComposerDialog(self.window, self.dashboard, self.room_id,
                           on_created=self.load_messages)

    def toggle_hand(self):
        if not self.dashboard:
            return
        try:
            queue = self.dashboard.get_room_queue(self.room_id) or []
            mine = any(q.get('mine') for q in queue)
            if mine:
                ok = self.dashboard.lower_hand(self.room_id)
            else:
                ok = self.dashboard.raise_hand(self.room_id)
            if ok:
                self.hand_button.config(
                    text="✋ Lower Hand" if not mine else "🙋 Raise Hand"
                )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def show_queue(self):
        if not self.dashboard:
            return
        QueueDialog(self.window, self.dashboard, self.room_id,
                    is_admin=bool((self.room_info or {}).get('is_admin')))

    def invite_user(self):
        username = askstring("Invite User", "Enter username to invite:")
        if username:
            try:
                # Find user and invite
                from education_system.post_18.university_system.infrastructure.email.admin import search_users as _su
                users = _su(self.dashboard.auth, username)
                if users:
                    user = users[0]
                    result = self.dashboard.invite_user_to_room(self.room_id, user['id'])
                    if result == True:
                        messagebox.showinfo("Success", f"Invitation sent to {username}")
                    elif result == "already_member":
                        messagebox.showinfo("Info", f"{username} is already a member")
                    else:
                        messagebox.showerror("Error", "Failed to send invitation")
                else:
                    messagebox.showerror("Error", f"User '{username}' not found")
            except Exception as e:
                messagebox.showerror("Error", f"Error inviting user: {e}")

    def leave_room(self):
        if messagebox.askyesno("Confirm", f"Leave room '{self.room_name}'?"):
            try:
                if self.dashboard.leave_chat_room(self.room_id):
                    messagebox.showinfo("Success", f"Left room '{self.room_name}'")
                    self._on_close()
                else:
                    messagebox.showerror("Error", "Failed to leave room")
            except Exception as e:
                messagebox.showerror("Error", f"Error leaving room: {e}")

