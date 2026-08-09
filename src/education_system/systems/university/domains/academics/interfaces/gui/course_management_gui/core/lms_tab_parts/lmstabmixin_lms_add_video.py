"""Methods _lms_add_video through _lms_load_quizzes."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import lms_tab_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class LMSTabMixin:
    def _lms_add_video(self):
        sel = self.lms_content_tree.selection()
        if not sel:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_content_first")); return
        content_id = self.lms_content_tree.item(sel[0])['values'][0]

        dlg = tk.Toplevel(self.root); dlg.title(_("lms.dialogs.add_video_lecture"))
        dlg.geometry("500x400"); dlg.transient(self.root); dlg.grab_set()
        fields = {}

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.labels.video_url', default="Video URL:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['video_url'] = ttk.Entry(dlg, width=40); fields['video_url'].grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.labels.duration_mins', default="Duration (mins):")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        fields['duration'] = ttk.Entry(dlg, width=40); fields['duration'].insert(0, "0")
        fields['duration'].grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.labels.thumbnail_url', default="Thumbnail URL:")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        fields['thumbnail'] = ttk.Entry(dlg, width=40); fields['thumbnail'].grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.labels.transcript_url', default="Transcript URL:")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        fields['transcript'] = ttk.Entry(dlg, width=40); fields['transcript'].grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.labels.quality', default="Quality:")).grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        fields['quality'] = ttk.Combobox(dlg, values=['360p', '480p', '720p', '1080p', '4K'], width=38, state='readonly')
        fields['quality'].current(2); fields['quality'].grid(row=4, column=1, padx=5, pady=5)

        def save():
            url = fields['video_url'].get().strip()
            if not url:
                messagebox.showerror(_("common.error"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.dialogs.video_url_is_required', default="Video URL is required")); return
            try:
                vid = LMSContentManager.add_video_lecture(
                    content_id=content_id, video_url=url,
                    duration_minutes=int(fields['duration'].get()),
                    thumbnail_url=fields['thumbnail'].get().strip(),
                    transcript_url=fields['transcript'].get().strip(),
                    video_quality=fields['quality'].get())
                log_activity('create', 'lms_video_lecture', str(vid), {'content_id': content_id})
                messagebox.showinfo(_("common.success"), f"Video added (ID: {vid})")
                dlg.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_add_video')}: {e}")

        ttk.Button(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.buttons.add_video', default="Add Video"), command=save).grid(row=5, column=0, columnspan=2, pady=20)

    def _create_lms_discussions_subtab(self):
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_("lms.tabs.discussions"))

        sel = ttk.Frame(tab); sel.pack(fill=tk.X, pady=5)
        ttk.Label(sel, text=_("lms.labels.select_course")).pack(side=tk.LEFT, padx=5)
        self.lms_discussion_course_combo = ttk.Combobox(sel, width=50, state='readonly')
        self.lms_discussion_course_combo.pack(side=tk.LEFT, padx=5)
        self.lms_discussion_course_combo.bind('<<ComboboxSelected>>', self._lms_load_forums)
        ttk.Button(sel, text=_("lms.buttons.load_forums"), command=self._lms_load_forums).pack(side=tk.LEFT, padx=5)

        btn = ttk.Frame(tab); btn.pack(fill=tk.X, pady=5)
        ttk.Button(btn, text=_("lms.buttons.create_forum"), command=self._lms_create_forum).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_("lms.buttons.view_posts"), command=self._lms_view_posts).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_("lms.buttons.add_post"), command=self._lms_add_post).pack(side=tk.LEFT, padx=5)

        lf = ttk.LabelFrame(tab, text=_("lms.frames.discussion_forums"), padding=10)
        lf.pack(fill=tk.BOTH, expand=True, pady=5)
        cols = ("ID", "Topic", "Description", "Created By", "Pinned", "Created")
        self.lms_forums_tree = ttk.Treeview(lf, columns=cols, show='headings', height=15)
        for c in cols:
            self.lms_forums_tree.heading(c, text=c)
            self.lms_forums_tree.column(c, width=250 if c in ("Topic", "Description") else 100)
        sb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.lms_forums_tree.yview)
        self.lms_forums_tree.configure(yscrollcommand=sb.set)
        self.lms_forums_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Double-clicking a forum opens the interactive discussion board.
        self.lms_forums_tree.bind('<Double-1>', lambda e: self._lms_view_posts())

        ttk.Label(
            tab,
            text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.labels.tip_select_a_forum_and_click_view_posts_or_double_click_it_to_re', default="Tip: select a forum and click 'View Posts' (or double-click it) "
                 "to read the thread, reply, and like messages."),
            foreground="#7f8c8d",
        ).pack(anchor=tk.W, padx=5, pady=(2, 0))

    def _lms_load_forums(self, *a):
        cid = self._lms_get_selected_course_id('lms_discussion_course_combo')
        if not cid:
            return
        self.lms_forums_tree.delete(*self.lms_forums_tree.get_children())
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT forum_id, topic, description, created_by, is_pinned, created_at
                    FROM lms_discussion_forums WHERE lms_course_id = ?
                    ORDER BY is_pinned DESC, created_at DESC
                ''', (cid,))
                for row in cursor.fetchall():
                    pinned = "Yes" if row[4] == 1 else "No"
                    self.lms_forums_tree.insert('', tk.END, values=(
                        row[0], row[1], row[2], row[3], pinned, row[5]))
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_load_forums')}: {e}")

    def _lms_create_forum(self):
        cid = self._lms_get_selected_course_id('lms_discussion_course_combo')
        if not cid:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_course_first")); return

        dlg = tk.Toplevel(self.root); dlg.title(_("lms.dialogs.create_discussion_forum"))
        dlg.geometry("500x400"); dlg.transient(self.root); dlg.grab_set()

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.labels.topic', default="Topic:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        topic_entry = ttk.Entry(dlg, width=40); topic_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.labels.description', default="Description:")).grid(row=1, column=0, sticky=tk.NW, padx=5, pady=5)
        desc_text = tk.Text(dlg, width=40, height=8); desc_text.grid(row=1, column=1, padx=5, pady=5)

        pin_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.buttons.pin_forum', default="Pin Forum"), variable=pin_var).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        def save():
            topic = topic_entry.get().strip()
            if not topic:
                messagebox.showerror(_("common.error"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.dialogs.topic_is_required', default="Topic is required")); return
            try:
                fid = LMSDiscussionManager.create_forum(
                    lms_course_id=cid, topic=topic,
                    description=desc_text.get('1.0', tk.END).strip(),
                    created_by=self._lms_user_id, is_pinned=pin_var.get())
                log_activity('create', 'lms_forum', str(fid), {'course_id': cid, 'topic': topic})
                messagebox.showinfo(_("common.success"), f"Forum created (ID: {fid})")
                dlg.destroy(); self._lms_load_forums()
            except Exception as e:
                messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_create_forum')}: {e}")

        ttk.Button(dlg, text=_("lms.buttons.create_forum"), command=save).grid(row=3, column=0, columnspan=2, pady=20)

    def _lms_view_posts(self):
        sel = self.lms_forums_tree.selection()
        if not sel:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_forum_first")); return
        forum_vals = self.lms_forums_tree.item(sel[0])['values']
        forum_id = forum_vals[0]
        forum_topic = forum_vals[1] if len(forum_vals) > 1 else f"Forum {forum_id}"

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Discussion: {forum_topic}")
        dlg.geometry("920x700")
        dlg.minsize(760, 560)
        dlg.transient(self.root)

        header = ttk.Frame(dlg, padding=(10, 8)); header.pack(fill=tk.X)
        ttk.Label(header, text=forum_topic, font=("Arial", 14, "bold")).pack(side=tk.LEFT)

        # Threaded post tree: the tree column shows the message snippet, with
        # replies nested under the post they answer.
        body = ttk.Frame(dlg, padding=(10, 0)); body.pack(fill=tk.BOTH, expand=True)
        cols = ("author", "date", "likes")
        tree = ttk.Treeview(body, columns=cols, show="tree headings", height=13)
        tree.heading("#0", text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.headings.message', default="Message")); tree.column("#0", width=420, stretch=True)
        tree.heading("author", text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.headings.author', default="Author")); tree.column("author", width=150, anchor=tk.W)
        tree.heading("date", text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.headings.date', default="Date")); tree.column("date", width=150, anchor=tk.W)
        tree.heading("likes", text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.headings.likes', default="Likes")); tree.column("likes", width=60, anchor=tk.CENTER)
        vsb = ttk.Scrollbar(body, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Full text of the selected post.
        detail = ttk.LabelFrame(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.labels.selected_message', default="Selected message"), padding=8)
        detail.pack(fill=tk.X, padx=10, pady=5)
        detail_txt = ScrolledText(detail, wrap=tk.WORD, height=6)
        detail_txt.pack(fill=tk.BOTH, expand=True)
        detail_txt.config(state='disabled')

        post_map = {}

        def _set_detail(text):
            detail_txt.config(state='normal')
            detail_txt.delete('1.0', tk.END)
            detail_txt.insert('1.0', text)
            detail_txt.config(state='disabled')

        def load_posts():
            tree.delete(*tree.get_children())
            post_map.clear()
            try:
                posts = LMSDiscussionManager.get_forum_posts(forum_id)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_load_posts')}: {e}")
                return
            by_parent = {}
            for p in posts:
                by_parent.setdefault(p.get('parent_post_id'), []).append(p)
            inserted = set()

            def insert_children(parent_key, tk_parent):
                for p in by_parent.get(parent_key, []):
                    pid = p.get('post_id')
                    snippet = (p.get('content') or '').replace('\n', ' ').strip()
                    if len(snippet) > 70:
                        snippet = snippet[:67] + '...'
                    iid = str(pid)
                    tree.insert(tk_parent, tk.END, iid=iid, text=snippet or "(no text)",
                                values=(p.get('user_id'), p.get('created_at'), p.get('likes_count', 0)))
                    post_map[iid] = p
                    inserted.add(pid)
                    insert_children(pid, iid)

            insert_children(None, "")
            # Surface any posts whose parent is missing so nothing is hidden.
            for p in posts:
                if p.get('post_id') not in inserted:
                    pid = p.get('post_id')
                    snippet = (p.get('content') or '').replace('\n', ' ').strip()
                    if len(snippet) > 70:
                        snippet = snippet[:67] + '...'
                    iid = str(pid)
                    tree.insert("", tk.END, iid=iid, text=snippet or "(no text)",
                                values=(p.get('user_id'), p.get('created_at'), p.get('likes_count', 0)))
                    post_map[iid] = p

            if post_map:
                for iid in tree.get_children(""):
                    tree.item(iid, open=True)
                _set_detail("Select a message to read it in full, then use the buttons below to reply or like.")
            else:
                _set_detail("No messages yet. Write the first message below and click 'Post as New Topic'.")

        def _selected_iid():
            s = tree.selection()
            return s[0] if s else None

        def on_select(_e=None):
            iid = _selected_iid()
            if iid and iid in post_map:
                p = post_map[iid]
                _set_detail(
                    f"{p.get('user_id')}  ·  {p.get('created_at')}  ·  "
                    f"{p.get('likes_count', 0)} likes\n"
                    f"{'-' * 60}\n{p.get('content') or ''}")

        tree.bind('<<TreeviewSelect>>', on_select)

        # Compose area.
        compose = ttk.LabelFrame(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.labels.write_a_message', default="Write a message"), padding=8)
        compose.pack(fill=tk.X, padx=10, pady=(0, 10))
        compose_txt = tk.Text(compose, wrap=tk.WORD, height=4)
        compose_txt.pack(fill=tk.X, pady=(0, 6))

        def _read_compose():
            text = compose_txt.get('1.0', tk.END).strip()
            if not text:
                messagebox.showwarning(_("common.warning"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.dialogs.enter_a_message_first', default="Enter a message first."))
                return None
            return text

        def post_new():
            content = _read_compose()
            if not content:
                return
            try:
                pid = LMSDiscussionManager.add_post(
                    forum_id=forum_id, user_id=self._lms_user_id, content=content)
                log_activity('create', 'lms_post', str(pid), {'forum_id': forum_id})
                compose_txt.delete('1.0', tk.END)
                load_posts()
            except Exception as e:
                messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_add_post')}: {e}")

        def post_reply():
            parent = _selected_iid()
            if not parent:
                messagebox.showwarning(_("common.warning"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.dialogs.select_a_message_to_reply_to', default="Select a message to reply to.")); return
            content = _read_compose()
            if not content:
                return
            try:
                pid = LMSDiscussionManager.add_post(
                    forum_id=forum_id, user_id=self._lms_user_id, content=content,
                    parent_post_id=int(parent))
                log_activity('create', 'lms_post', str(pid), {'forum_id': forum_id, 'parent': parent})
                compose_txt.delete('1.0', tk.END)
                load_posts()
                if parent in tree.get_children("") or parent in post_map:
                    try:
                        tree.see(parent); tree.item(parent, open=True)
                    except Exception:
                        pass
            except Exception as e:
                messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_add_post')}: {e}")

        def like_selected():
            iid = _selected_iid()
            if not iid:
                messagebox.showwarning(_("common.warning"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.dialogs.select_a_message_to_like', default="Select a message to like.")); return
            try:
                LMSDiscussionManager.like_post(int(iid))
                load_posts()
                try:
                    tree.selection_set(iid); tree.see(iid)
                except Exception:
                    pass
            except Exception as e:
                messagebox.showerror(_("common.error"), str(e))

        btns = ttk.Frame(compose); btns.pack(fill=tk.X)
        ttk.Button(btns, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.buttons.post_as_new_topic', default="Post as New Topic"), command=post_new).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.buttons.reply_to_selected', default="Reply to Selected"), command=post_reply).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.buttons.like_selected', default="👍 Like Selected"), command=like_selected).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.buttons.refresh', default="Refresh"), command=load_posts).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.buttons.close', default="Close"), command=dlg.destroy).pack(side=tk.RIGHT, padx=3)

        load_posts()

    def _lms_add_post(self):
        sel = self.lms_forums_tree.selection()
        if not sel:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_forum_first")); return
        forum_id = self.lms_forums_tree.item(sel[0])['values'][0]

        dlg = tk.Toplevel(self.root); dlg.title(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.windows.add_post', default="Add Post")); dlg.geometry("500x400")
        dlg.transient(self.root); dlg.grab_set()

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.labels.post_content', default="Post Content:")).grid(row=0, column=0, sticky=tk.NW, padx=5, pady=5)
        content_text = tk.Text(dlg, width=50, height=15); content_text.grid(row=0, column=1, padx=5, pady=5)

        def save():
            content = content_text.get('1.0', tk.END).strip()
            if not content:
                messagebox.showerror(_("common.error"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.dialogs.post_content_is_required', default="Post content is required")); return
            try:
                pid = LMSDiscussionManager.add_post(forum_id=forum_id, user_id=self._lms_user_id, content=content)
                log_activity('create', 'lms_post', str(pid), {'forum_id': forum_id})
                messagebox.showinfo(_("common.success"), f"Post added (ID: {pid})")
                dlg.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_add_post')}: {e}")

        ttk.Button(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_add_video.buttons.add_post', default="Add Post"), command=save).grid(row=1, column=0, columnspan=2, pady=20)

    def _create_lms_quizzes_subtab(self):
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_("lms.tabs.quizzes"))

        sel = ttk.Frame(tab); sel.pack(fill=tk.X, pady=5)
        ttk.Label(sel, text=_("lms.labels.select_course")).pack(side=tk.LEFT, padx=5)
        self.lms_quiz_course_combo = ttk.Combobox(sel, width=50, state='readonly')
        self.lms_quiz_course_combo.pack(side=tk.LEFT, padx=5)
        self.lms_quiz_course_combo.bind('<<ComboboxSelected>>', self._lms_load_quizzes)
        ttk.Button(sel, text=_("lms.buttons.load_quizzes"), command=self._lms_load_quizzes).pack(side=tk.LEFT, padx=5)

        btn = ttk.Frame(tab); btn.pack(fill=tk.X, pady=5)
        ttk.Button(btn, text=_("lms.buttons.create_quiz"), command=self._lms_create_quiz).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_("lms.buttons.add_questions"), command=self._lms_add_questions).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_("lms.buttons.view_submissions"), command=self._lms_view_submissions).pack(side=tk.LEFT, padx=5)

        lf = ttk.LabelFrame(tab, text=_("lms.frames.quizzes"), padding=10)
        lf.pack(fill=tk.BOTH, expand=True, pady=5)
        cols = ("ID", "Title", "Duration (min)", "Passing Score", "Max Attempts", "From", "Until")
        self.lms_quizzes_tree = ttk.Treeview(lf, columns=cols, show='headings', height=15)
        for c in cols:
            self.lms_quizzes_tree.heading(c, text=c)
            self.lms_quizzes_tree.column(c, width=200 if c == "Title" else 100)
        sb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.lms_quizzes_tree.yview)
        self.lms_quizzes_tree.configure(yscrollcommand=sb.set)
        self.lms_quizzes_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _lms_load_quizzes(self, *a):
        cid = self._lms_get_selected_course_id('lms_quiz_course_combo')
        if not cid:
            return
        self.lms_quizzes_tree.delete(*self.lms_quizzes_tree.get_children())
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT quiz_id, title, duration_minutes, passing_score,
                           max_attempts, available_from, available_until
                    FROM lms_quizzes WHERE lms_course_id = ?
                    ORDER BY created_at DESC
                ''', (cid,))
                for row in cursor.fetchall():
                    self.lms_quizzes_tree.insert('', tk.END, values=tuple(row))
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_load_quizzes')}: {e}")
