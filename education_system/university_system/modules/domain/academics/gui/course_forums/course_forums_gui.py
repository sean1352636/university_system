"""Course Discussion Forums GUI (Feature 39).

Provides a forum interface for course discussions, including threaded posts,
topic creation, replies, and likes. Organized by enrolled courses.
"""

import logging
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, simpledialog, ttk

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity

logger = logging.getLogger(__name__)


class CourseForumsGUI:
    """Toplevel window for course discussion forums."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.student_id = (
            auth.current_user.get('username', '') if auth and auth.current_user else ''
        )
        self.selected_course_id = None
        self.selected_forum_id = None
        self.selected_post_id = None

        self.window = tk.Toplevel(parent)
        self.window.title("Course Discussion Forums")
        self.window.geometry("1000x700")
        self.window.transient(parent)

        self._ensure_tables()
        self._setup_ui()
        self._load_courses()

    # ------------------------------------------------------------------
    # Database setup
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        """Create forum tables if they do not exist."""
        try:
            with transaction() as conn:
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS lms_discussion_forums (
                        forum_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        lms_course_id TEXT,
                        topic TEXT NOT NULL,
                        description TEXT,
                        created_by TEXT,
                        is_pinned INTEGER DEFAULT 0,
                        is_locked INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )"""
                )
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS lms_discussion_posts (
                        post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        forum_id INTEGER,
                        user_id TEXT,
                        content TEXT,
                        parent_post_id INTEGER,
                        attachments TEXT,
                        likes_count INTEGER DEFAULT 0,
                        is_instructor_post INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )"""
                )
        except Exception as exc:
            logger.error("Failed to create forum tables: %s", exc)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the forum interface."""
        ttk.Label(
            self.window,
            text="Course Discussion Forums",
            font=('Arial', 16, 'bold'),
        ).pack(pady=(10, 5))

        # ---- Top: Course selector ----
        top_frame = ttk.Frame(self.window)
        top_frame.pack(fill=tk.X, padx=15, pady=5)

        ttk.Label(top_frame, text="Course:").pack(side=tk.LEFT, padx=(0, 5))
        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(
            top_frame, textvariable=self.course_var, state='readonly', width=50
        )
        self.course_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.course_combo.bind('<<ComboboxSelected>>', lambda e: self._on_course_selected())

        # Internal mapping: combo index -> course_id
        self._course_ids = []

        # ---- Middle section: forums list (left) + posts view (right) ----
        middle_paned = ttk.PanedWindow(self.window, orient=tk.HORIZONTAL)
        middle_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # -- Left: forum list --
        forum_frame = ttk.LabelFrame(middle_paned, text="Forums")
        middle_paned.add(forum_frame, weight=1)

        forum_tree_frame = ttk.Frame(forum_frame)
        forum_tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        cols = ('title', 'posts_count', 'last_activity')
        self.forum_tree = ttk.Treeview(
            forum_tree_frame, columns=cols, show='headings', selectmode='browse'
        )
        self.forum_tree.heading('title', text='Title')
        self.forum_tree.heading('posts_count', text='Posts')
        self.forum_tree.heading('last_activity', text='Last Activity')
        self.forum_tree.column('title', width=200)
        self.forum_tree.column('posts_count', width=60, anchor=tk.CENTER)
        self.forum_tree.column('last_activity', width=140)

        forum_scroll = ttk.Scrollbar(
            forum_tree_frame, orient=tk.VERTICAL, command=self.forum_tree.yview
        )
        self.forum_tree.configure(yscrollcommand=forum_scroll.set)
        self.forum_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        forum_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.forum_tree.bind('<<TreeviewSelect>>', self._on_forum_selected)

        # Internal mapping: tree item iid -> forum_id
        self._forum_map = {}

        # -- Right: posts view --
        posts_frame = ttk.LabelFrame(middle_paned, text="Posts")
        middle_paned.add(posts_frame, weight=2)

        posts_container = ttk.Frame(posts_frame)
        posts_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Scrollable canvas for threaded posts
        self.posts_canvas = tk.Canvas(posts_container)
        posts_vscroll = ttk.Scrollbar(
            posts_container, orient=tk.VERTICAL, command=self.posts_canvas.yview
        )
        self.posts_canvas.configure(yscrollcommand=posts_vscroll.set)
        posts_vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.posts_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.posts_inner_frame = ttk.Frame(self.posts_canvas)
        self.posts_canvas_window = self.posts_canvas.create_window(
            (0, 0), window=self.posts_inner_frame, anchor=tk.NW
        )
        self.posts_inner_frame.bind(
            '<Configure>',
            lambda e: self.posts_canvas.configure(
                scrollregion=self.posts_canvas.bbox('all')
            ),
        )
        self.posts_canvas.bind(
            '<Configure>',
            lambda e: self.posts_canvas.itemconfig(
                self.posts_canvas_window, width=e.width
            ),
        )

        # ---- Bottom: action buttons ----
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=15, pady=(5, 10))

        ttk.Button(
            btn_frame, text="New Topic", command=self._new_topic
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            btn_frame, text="Reply", command=self._reply_to_post
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            btn_frame, text="Like", command=self._like_post
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            btn_frame, text="Refresh", command=self._refresh_current
        ).pack(side=tk.RIGHT, padx=5)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_courses(self):
        """Load enrolled courses into the combo box."""
        self.course_combo.set('')
        self._course_ids.clear()
        values = []

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """SELECT m.module_code, m.module_name
                       FROM student_modules sm
                       JOIN modules m ON sm.module_code = m.module_code
                       WHERE sm.student_id = ?
                       ORDER BY m.module_name""",
                    (self.student_id,),
                ).fetchall()

            for module_code, module_name in rows:
                self._course_ids.append(module_code)
                values.append(f"{module_code} - {module_name}")
        except Exception as exc:
            logger.error("Failed to load courses: %s", exc)

        self.course_combo['values'] = values

    def _on_course_selected(self):
        """Handle course selection from the combo box."""
        idx = self.course_combo.current()
        if idx < 0 or idx >= len(self._course_ids):
            return
        self.selected_course_id = self._course_ids[idx]
        self.selected_forum_id = None
        self.selected_post_id = None
        self._load_forums()
        self._clear_posts()

    def _load_forums(self):
        """Load forums for the selected course."""
        self.forum_tree.delete(*self.forum_tree.get_children())
        self._forum_map.clear()

        if not self.selected_course_id:
            return

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """SELECT f.forum_id, f.topic,
                              COUNT(p.post_id) AS posts,
                              MAX(p.created_at) AS last_activity
                       FROM lms_discussion_forums f
                       LEFT JOIN lms_discussion_posts p ON f.forum_id = p.forum_id
                       WHERE f.lms_course_id = ? AND f.is_locked = 0
                       GROUP BY f.forum_id""",
                    (self.selected_course_id,),
                ).fetchall()

            for forum_id, title, posts_count, last_activity in rows:
                activity_str = last_activity[:19] if last_activity else 'No posts'
                iid = self.forum_tree.insert(
                    '', tk.END,
                    values=(title, posts_count, activity_str),
                )
                self._forum_map[iid] = forum_id
        except Exception as exc:
            logger.error("Failed to load forums: %s", exc)

    def _on_forum_selected(self, event):
        """Handle forum selection from the treeview."""
        selection = self.forum_tree.selection()
        if not selection:
            return
        iid = selection[0]
        self.selected_forum_id = self._forum_map.get(iid)
        self.selected_post_id = None
        self._load_posts()

    def _clear_posts(self):
        """Clear the posts view."""
        for widget in self.posts_inner_frame.winfo_children():
            widget.destroy()
        self.selected_post_id = None

    def _load_posts(self):
        """Load and display threaded posts for the selected forum."""
        self._clear_posts()

        if self.selected_forum_id is None:
            return

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """SELECT post_id, parent_post_id, user_id, content,
                              created_at, likes_count
                       FROM lms_discussion_posts
                       WHERE forum_id = ?
                       ORDER BY created_at ASC""",
                    (self.selected_forum_id,),
                ).fetchall()
        except Exception as exc:
            logger.error("Failed to load posts: %s", exc)
            return

        # Build a tree structure for threading
        posts_by_id = {}
        root_posts = []
        for post_id, parent_id, author_id, content, created_at, likes in rows:
            post = {
                'id': post_id,
                'parent_id': parent_id,
                'author_id': author_id,
                'content': content,
                'created_at': created_at,
                'likes': likes,
                'children': [],
            }
            posts_by_id[post_id] = post
            if parent_id is None or parent_id not in posts_by_id:
                root_posts.append(post)
            else:
                posts_by_id[parent_id]['children'].append(post)

        # Render posts recursively
        for post in root_posts:
            self._render_post(self.posts_inner_frame, post, indent=0)

    def _render_post(self, parent_widget, post, indent=0):
        """Render a single post with indentation for threading."""
        frame = ttk.Frame(parent_widget)
        frame.pack(fill=tk.X, padx=(indent * 20 + 5, 5), pady=3)

        # Post header
        timestamp = post['created_at'][:19] if post['created_at'] else ''
        header_text = f"{post['author_id']}  |  {timestamp}  |  Likes: {post['likes']}"
        header_label = ttk.Label(
            frame, text=header_text, font=('Arial', 9, 'bold'), foreground='gray'
        )
        header_label.pack(anchor=tk.W)

        # Post content
        content_label = ttk.Label(
            frame, text=post['content'], wraplength=500, justify=tk.LEFT
        )
        content_label.pack(anchor=tk.W, padx=(10, 0))

        # Make the frame clickable to select the post
        for widget in (frame, header_label, content_label):
            widget.bind('<Button-1>', lambda e, pid=post['id']: self._select_post(pid))

        # Separator
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(3, 0))

        # Render child posts
        for child in post['children']:
            self._render_post(parent_widget, child, indent=indent + 1)

    def _select_post(self, post_id):
        """Mark a post as selected."""
        self.selected_post_id = post_id
        logger.debug("Selected post ID: %s", post_id)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _new_topic(self):
        """Create a new forum topic for the selected course."""
        if not self.selected_course_id:
            messagebox.showwarning(
                "No Course", "Please select a course first.", parent=self.window
            )
            return

        dialog = tk.Toplevel(self.window)
        dialog.title("New Forum Topic")
        dialog.geometry("400x250")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text="Title:").pack(anchor=tk.W, padx=10, pady=(10, 2))
        title_entry = ttk.Entry(dialog, width=50)
        title_entry.pack(padx=10, pady=(0, 5))

        ttk.Label(dialog, text="Description:").pack(anchor=tk.W, padx=10, pady=(5, 2))
        desc_text = tk.Text(dialog, height=5, width=50)
        desc_text.pack(padx=10, pady=(0, 10))

        def _create():
            title = title_entry.get().strip()
            description = desc_text.get('1.0', tk.END).strip()
            if not title:
                messagebox.showwarning(
                    "Missing Title", "Please enter a topic title.", parent=dialog
                )
                return
            try:
                with transaction() as conn:
                    conn.execute(
                        """INSERT INTO lms_discussion_forums
                              (lms_course_id, topic, description, created_by)
                           VALUES (?, ?, ?, ?)""",
                        (self.selected_course_id, title, description, self.student_id),
                    )
                log_activity(
                    self.student_id, self.student_id, 'student',
                    'create_forum_topic', 'course_forums',
                    details=f"Created topic '{title}' in {self.selected_course_id}",
                )
                logger.info(
                    "Forum topic '%s' created by %s in %s",
                    title, self.student_id, self.selected_course_id,
                )
                dialog.destroy()
                self._load_forums()
            except Exception as exc:
                logger.error("Failed to create topic: %s", exc)
                messagebox.showerror(
                    "Error", f"Failed to create topic: {exc}", parent=dialog
                )

        ttk.Button(dialog, text="Create Topic", command=_create).pack(pady=10)

    def _reply_to_post(self):
        """Reply to the selected post or create a root post in the selected forum."""
        if self.selected_forum_id is None:
            messagebox.showwarning(
                "No Forum", "Please select a forum first.", parent=self.window
            )
            return

        parent_post_id = self.selected_post_id  # May be None for root-level reply

        dialog = tk.Toplevel(self.window)
        dialog.title("Reply" if parent_post_id else "New Post")
        dialog.geometry("400x200")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text="Your reply:").pack(anchor=tk.W, padx=10, pady=(10, 2))
        reply_text = tk.Text(dialog, height=5, width=50)
        reply_text.pack(padx=10, pady=(0, 10))

        def _submit():
            content = reply_text.get('1.0', tk.END).strip()
            if not content:
                messagebox.showwarning(
                    "Empty Reply", "Please enter your reply.", parent=dialog
                )
                return
            try:
                with transaction() as conn:
                    conn.execute(
                        """INSERT INTO lms_discussion_posts
                              (forum_id, parent_post_id, user_id, content)
                           VALUES (?, ?, ?, ?)""",
                        (self.selected_forum_id, parent_post_id, self.student_id, content),
                    )
                log_activity(
                    self.student_id, self.student_id, 'student',
                    'reply_forum_post', 'course_forums',
                    details=f"Replied in forum {self.selected_forum_id}",
                )
                logger.info(
                    "Post created by %s in forum %s",
                    self.student_id, self.selected_forum_id,
                )
                dialog.destroy()
                self._load_posts()
                self._load_forums()
            except Exception as exc:
                logger.error("Failed to create reply: %s", exc)
                messagebox.showerror(
                    "Error", f"Failed to create reply: {exc}", parent=dialog
                )

        ttk.Button(dialog, text="Submit", command=_submit).pack(pady=5)

    def _like_post(self):
        """Increment like count on the selected post."""
        if self.selected_post_id is None:
            messagebox.showwarning(
                "No Post Selected",
                "Please click on a post to select it before liking.",
                parent=self.window,
            )
            return

        try:
            with transaction() as conn:
                conn.execute(
                    """UPDATE lms_discussion_posts
                       SET likes_count = likes_count + 1
                       WHERE post_id = ?""",
                    (self.selected_post_id,),
                )
            logger.info("Post %s liked by %s", self.selected_post_id, self.student_id)
            self._load_posts()
        except Exception as exc:
            logger.error("Failed to like post: %s", exc)
            messagebox.showerror(
                "Error", f"Failed to like post: {exc}", parent=self.window
            )

    def _refresh_current(self):
        """Refresh the current forum and posts view."""
        if self.selected_course_id:
            self._load_forums()
        if self.selected_forum_id:
            self._load_posts()
