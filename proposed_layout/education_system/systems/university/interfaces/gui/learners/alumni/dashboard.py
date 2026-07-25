import tkinter as tk
from education_system.systems.university.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system.systems.university.infrastructure import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Matplotlib is optional — the dashboard charts degrade gracefully to a short
# message if it (or the Tk backend) is unavailable.
try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Alumni service functions
from education_system.systems.university.interfaces.gui.learners.alumni._service_imports import (
    init_alumni_db, register_alumni, view_alumni, update_alumni,
    view_events, create_enhanced_event, event_check_in_system,
    record_donation, view_donations, setup_mentorship, view_mentorships,
    search_alumni_directory, view_connection_requests, manage_business_directory,
    create_newsletter, manage_alumni_forum, post_job_opportunity, view_job_board,
    schedule_career_counseling, view_fundraising_campaigns, create_fundraising_campaign,
    view_engagement_leaderboard, view_my_badges, manage_photo_gallery,
    manage_class_reunions, manage_regional_chapters, setup_alumni_directory,
    generate_alumni_report, set_auth, setup_alumni_permissions,
    smart_mentorship_matching, generate_engagement_recommendations,
    create_alumni_story, view_alumni_stories, get_connection,
)


# Palette for stat tiles / section headers.
_CARD_BG = '#f7f9fb'
_ACCENT = '#2c3e50'


class DashboardMixin:
        def show_dashboard(self):
            """Show the main dashboard — a scrollable, data-driven overview."""
            self.clear_content()
            self.update_status(_t("alumni.dashboard_loaded", default="Dashboard loaded"))

            # ── Scrollable container so the richer dashboard never clips ──
            outer = ttk.Frame(self.content_frame)
            outer.pack(fill=tk.BOTH, expand=True)
            canvas = tk.Canvas(outer, highlightthickness=0)
            vscroll = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
            body = ttk.Frame(canvas)
            body.bind("<Configure>",
                      lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            window_id = canvas.create_window((0, 0), window=body, anchor="nw")
            canvas.bind("<Configure>",
                        lambda e: canvas.itemconfigure(window_id, width=e.width))
            canvas.configure(yscrollcommand=vscroll.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            vscroll.pack(side=tk.RIGHT, fill=tk.Y)

            def _on_wheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            canvas.bind("<MouseWheel>", _on_wheel)
            body.bind("<MouseWheel>", _on_wheel)

            # Resolve the signed-in alumnus once and reuse across the sections.
            alumni = self._resolve_current_alumni()

            # ── Build the sections ──
            self._build_welcome(body, alumni)
            self._build_stat_tiles(body)
            self._build_personal_cards(body, alumni)
            self._build_directory_search(body)
            self._build_charts(body)
            self._build_gamification(body, alumni)
            self._build_activity_feed(body)

        # ------------------------------------------------------------------
        # Helpers
        # ------------------------------------------------------------------
        def _resolve_current_alumni(self):
            """Return the alumni row dict for the signed-in user, or None.

            Matches the account against ``alumni`` by alumni_id, student_id or
            email — covering the different ways an alumnus account is keyed."""
            uid = self._current_user_id()
            email = ''
            if isinstance(self.current_user, dict):
                email = (self.current_user.get('email') or '').strip()
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    "SELECT * FROM alumni "
                    "WHERE alumni_id = ? OR student_id = ? OR email_address = ? "
                    "LIMIT 1",
                    (uid, uid, email),
                )
                row = cur.fetchone()
                conn.close()
                return dict(row) if row else None
            except sqlite3.Error:
                return None

        def _alumni_display_name(self, alumni):
            """Best-effort display name for the welcome banner."""
            if alumni:
                name = " ".join(filter(None, [alumni.get('first_name'),
                                              alumni.get('last_name')])).strip()
                if name:
                    return name
            user = self.current_user if isinstance(self.current_user, dict) else {}
            return user.get('display_name') or user.get('username') or _t(
                "alumni.fallback_name", default="Alumnus")

        def _section_header(self, parent, text, icon=""):
            label = f"{icon}  {text}" if icon else text
            ttk.Label(parent, text=label, font=('Arial', 13, 'bold')).pack(
                anchor='w', pady=(16, 6))

        def _scalar(self, cursor, sql, params=(), default=0):
            """Run a single-value query, returning ``default`` on any error."""
            try:
                cursor.execute(sql, params)
                row = cursor.fetchone()
                if not row:
                    return default
                val = row[0]
                return default if val is None else val
            except sqlite3.Error:
                return default

        # ------------------------------------------------------------------
        # 1) Personalised welcome banner
        # ------------------------------------------------------------------
        def _build_welcome(self, parent, alumni):
            banner = tk.Frame(parent, bg=_ACCENT)
            banner.pack(fill=tk.X)
            name = self._alumni_display_name(alumni)
            tk.Label(banner, text=_t("alumni.welcome_back",
                                     default="Welcome back, {name}!").format(name=name),
                     font=('Arial', 20, 'bold'), bg=_ACCENT, fg='white'
                     ).pack(anchor='w', padx=16, pady=(12, 2))

            subtitle_bits = []
            if alumni:
                if alumni.get('degree_earned'):
                    subtitle_bits.append(str(alumni['degree_earned']))
                if alumni.get('graduation_year'):
                    subtitle_bits.append(_t("alumni.class_of",
                                            default="Class of {year}").format(
                                                year=alumni['graduation_year']))
                if alumni.get('current_employer'):
                    subtitle_bits.append(str(alumni['current_employer']))
            subtitle = "  ·  ".join(subtitle_bits) or _t(
                "alumni.welcome_tagline",
                default="Your alumni community at a glance")
            tk.Label(banner, text=subtitle, font=('Arial', 11),
                     bg=_ACCENT, fg='#bdc3c7').pack(anchor='w', padx=16, pady=(0, 12))

        # ------------------------------------------------------------------
        # 2) Quick-statistics tiles
        # ------------------------------------------------------------------
        def _build_stat_tiles(self, parent):
            self._section_header(parent, _t("alumni.quick_statistics",
                                            default="Quick Statistics"), "📊")
            grid = ttk.Frame(parent)
            grid.pack(fill=tk.X)

            uid = self._current_user_id()
            this_year = datetime.now().strftime('%Y')
            stats = []
            try:
                conn = get_connection()
                cur = conn.cursor()

                total_alumni = self._scalar(cur, "SELECT COUNT(*) FROM alumni")
                upcoming_events = self._scalar(
                    cur, "SELECT COUNT(*) FROM unified_events "
                         "WHERE source_type = 'alumni' AND start_datetime > datetime('now')")
                total_donors = self._scalar(
                    cur, "SELECT COUNT(*) FROM alumni WHERE is_donor = 1")
                total_donated = self._scalar(
                    cur, "SELECT COALESCE(SUM(amount), 0) FROM donations")
                raised_this_year = self._scalar(
                    cur, "SELECT COALESCE(SUM(amount), 0) FROM donations "
                         "WHERE strftime('%Y', donation_date) = ?", (this_year,))
                active_mentors = self._scalar(
                    cur, "SELECT COUNT(*) FROM mentorships WHERE status = 'active'")
                gift_aid_total = self._scalar(
                    cur, "SELECT COALESCE(SUM(amount), 0) FROM donations "
                         "WHERE is_gift_aided = 1")
                open_jobs = self._scalar(
                    cur, "SELECT COUNT(*) FROM job_postings WHERE is_active = 1 "
                         "AND (expiry_date IS NULL OR expiry_date >= date('now'))")
                upcoming_reunions = self._scalar(
                    cur, "SELECT COUNT(*) FROM class_reunions "
                         "WHERE reunion_date >= date('now')")
                unread_notifications = self._scalar(
                    cur, "SELECT COUNT(*) FROM notifications "
                         "WHERE user_id = ? AND is_read = 0", (uid,))

                conn.close()

                stats = [
                    (_t("alumni.stats.total_alumni", default="Total Alumni"), total_alumni, "👥"),
                    (_t("alumni.stats.upcoming_events", default="Upcoming Events"), upcoming_events, "📅"),
                    (_t("alumni.stats.active_donors", default="Active Donors"), total_donors, "💝"),
                    (_t("alumni.stats.total_donated", default="Total Donated"), f"£{total_donated:,.2f}", "💰"),
                    (_t("alumni.stats.raised_this_year", default="Raised This Year"), f"£{raised_this_year:,.2f}", "📈"),
                    (_t("alumni.stats.active_mentors", default="Active Mentors"), active_mentors, "🤝"),
                    (_t("alumni.stats.gift_aid", default="Gift Aid Eligible"), f"£{gift_aid_total:,.2f}", "🎁"),
                    (_t("alumni.stats.open_jobs", default="Open Jobs"), open_jobs, "💼"),
                    (_t("alumni.stats.upcoming_reunions", default="Upcoming Reunions"), upcoming_reunions, "🎉"),
                    (_t("alumni.stats.unread_notifications", default="Unread Alerts"), unread_notifications, "🔔"),
                ]
            except sqlite3.Error:
                stats = [
                    (_t("alumni.stats.total_alumni", default="Total Alumni"), _t("common.na", default="N/A"), "👥"),
                    (_t("alumni.stats.upcoming_events", default="Upcoming Events"), _t("common.na", default="N/A"), "📅"),
                    (_t("alumni.stats.active_donors", default="Active Donors"), _t("common.na", default="N/A"), "💝"),
                    (_t("alumni.stats.system_status", default="System Status"), _t("common.error", default="Error"), "❌"),
                ]

            cols = 5
            for i, (label, value, icon) in enumerate(stats):
                col = i % cols
                row = i // cols
                tile = tk.Frame(grid, bg=_CARD_BG, relief=tk.RIDGE, bd=1,
                                padx=10, pady=8)
                tile.grid(row=row, column=col, padx=5, pady=5, sticky='ew')
                tk.Label(tile, text=icon, font=('Arial', 16), bg=_CARD_BG).pack()
                tk.Label(tile, text=str(value), font=('Arial', 14, 'bold'),
                         bg=_CARD_BG).pack()
                tk.Label(tile, text=label, font=('Arial', 9), bg=_CARD_BG,
                         fg='#555').pack()
                grid.columnconfigure(col, weight=1)

        # ------------------------------------------------------------------
        # 3) Personal cards: next event · giving · mentorship · notifications
        # ------------------------------------------------------------------
        def _build_personal_cards(self, parent, alumni):
            self._section_header(parent, _t("alumni.for_you", default="For You"), "⭐")
            row = ttk.Frame(parent)
            row.pack(fill=tk.X)
            for c in range(4):
                row.columnconfigure(c, weight=1)

            self._build_next_event_card(row, alumni, col=0)
            self._build_giving_card(row, alumni, col=1)
            self._build_mentorship_card(row, alumni, col=2)
            self._build_notifications_card(row, alumni, col=3)

        def _card(self, parent, col, title):
            frame = ttk.LabelFrame(parent, text=title, padding=10)
            frame.grid(row=0, column=col, padx=5, pady=5, sticky='nsew')
            return frame

        def _build_next_event_card(self, parent, alumni, col):
            card = self._card(parent, col, _t("alumni.cards.next_event",
                                              default="📅 My Next Event"))
            uid = self._current_user_id()
            event = None
            try:
                conn = get_connection()
                cur = conn.cursor()
                # The alumnus's own next registered event takes priority …
                cur.execute(
                    """SELECT e.title, e.start_datetime, e.location
                         FROM unified_event_registrations r
                         JOIN unified_events e ON r.event_id = e.event_id
                        WHERE r.user_id = ? AND e.start_datetime > datetime('now')
                        ORDER BY e.start_datetime ASC LIMIT 1""", (uid,))
                event = cur.fetchone()
                registered = event is not None
                if not event:
                    # … otherwise surface the next public alumni event to RSVP to.
                    cur.execute(
                        """SELECT title, start_datetime, location
                             FROM unified_events
                            WHERE source_type = 'alumni'
                              AND start_datetime > datetime('now')
                            ORDER BY start_datetime ASC LIMIT 1""")
                    event = cur.fetchone()
                conn.close()
            except sqlite3.Error:
                registered = False

            if event:
                title = event[0] or _t("alumni.cards.untitled_event", default="Event")
                when = (event[1] or '')[:16].replace('T', ' ')
                where = event[2] or ''
                ttk.Label(card, text=title, font=('Arial', 11, 'bold'),
                          wraplength=180).pack(anchor='w')
                ttk.Label(card, text=when, foreground='#555').pack(anchor='w')
                if where:
                    ttk.Label(card, text=where, foreground='#555',
                              wraplength=180).pack(anchor='w')
                tag = (_t("alumni.cards.youre_going", default="You're going ✓")
                       if registered
                       else _t("alumni.cards.rsvp_now", default="RSVP / View"))
                ttk.Button(card, text=tag,
                           command=self.show_view_events).pack(anchor='w', pady=(8, 0))
            else:
                ttk.Label(card, text=_t("alumni.cards.no_events",
                                        default="No upcoming events yet."),
                          foreground='#777').pack(anchor='w')
                ttk.Button(card, text=_t("alumni.cards.browse_events",
                                         default="Browse events"),
                           command=self.show_view_events).pack(anchor='w', pady=(8, 0))

        def _build_giving_card(self, parent, alumni, col):
            card = self._card(parent, col, _t("alumni.cards.giving",
                                              default="💰 My Giving"))
            total = 0
            count = 0
            last_date = None
            if alumni:
                try:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT COUNT(*), COALESCE(SUM(amount), 0), MAX(donation_date) "
                        "FROM donations WHERE alumni_id = ?", (alumni.get('alumni_id'),))
                    r = cur.fetchone()
                    conn.close()
                    if r:
                        count, total, last_date = r[0], r[1], r[2]
                except sqlite3.Error:
                    pass

            ttk.Label(card, text=f"£{(total or 0):,.2f}",
                      font=('Arial', 18, 'bold')).pack(anchor='w')
            ttk.Label(card, text=_t("alumni.cards.lifetime_giving",
                                    default="across {n} gift(s)").format(n=count),
                      foreground='#555').pack(anchor='w')
            if last_date:
                ttk.Label(card, text=_t("alumni.cards.last_gift",
                                        default="Last gift: {d}").format(d=str(last_date)[:10]),
                          foreground='#555').pack(anchor='w')
            ttk.Button(card, text=_t("alumni.cards.donate", default="Donate"),
                       command=self.show_record_donation).pack(anchor='w', pady=(8, 0))

        def _build_mentorship_card(self, parent, alumni, col):
            card = self._card(parent, col, _t("alumni.cards.mentorship",
                                              default="🤝 Mentorship"))
            as_mentor = as_mentee = 0
            is_mentor = bool(alumni and alumni.get('is_mentor'))
            if alumni:
                aid = alumni.get('alumni_id')
                try:
                    conn = get_connection()
                    cur = conn.cursor()
                    as_mentor = self._scalar(
                        cur, "SELECT COUNT(*) FROM mentorships "
                             "WHERE mentor_id = ? AND status = 'active'", (aid,))
                    as_mentee = self._scalar(
                        cur, "SELECT COUNT(*) FROM mentorships "
                             "WHERE mentee_id = ? AND status = 'active'", (aid,))
                    conn.close()
                except sqlite3.Error:
                    pass

            if as_mentor or as_mentee:
                if as_mentor:
                    ttk.Label(card, text=_t("alumni.cards.mentoring_n",
                                            default="Mentoring {n} alum(s)").format(n=as_mentor),
                              font=('Arial', 11, 'bold')).pack(anchor='w')
                if as_mentee:
                    ttk.Label(card, text=_t("alumni.cards.mentored_by_n",
                                            default="In {n} mentorship(s)").format(n=as_mentee),
                              foreground='#555').pack(anchor='w')
                ttk.Button(card, text=_t("alumni.cards.view_mentorships",
                                         default="View mentorships"),
                           command=self.show_view_mentorships).pack(anchor='w', pady=(8, 0))
            else:
                msg = (_t("alumni.cards.share_expertise",
                          default="Share your expertise with recent graduates.")
                       if not is_mentor else
                       _t("alumni.cards.no_active_mentorships",
                          default="No active mentorships yet."))
                ttk.Label(card, text=msg, foreground='#777',
                          wraplength=180).pack(anchor='w')
                ttk.Button(card, text=_t("alumni.cards.become_mentor",
                                         default="Become a mentor"),
                           command=self.show_setup_mentorship).pack(anchor='w', pady=(8, 0))

        def _build_notifications_card(self, parent, alumni, col):
            card = self._card(parent, col, _t("alumni.cards.notifications",
                                              default="🔔 Notifications"))
            uid = self._current_user_id()
            rows = []
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    "SELECT title, message, created_datetime, is_read "
                    "FROM notifications WHERE user_id = ? "
                    "ORDER BY created_datetime DESC LIMIT 4", (uid,))
                rows = cur.fetchall()
                conn.close()
            except sqlite3.Error:
                rows = []

            if not rows:
                ttk.Label(card, text=_t("alumni.cards.no_notifications",
                                        default="You're all caught up."),
                          foreground='#777').pack(anchor='w')
                return
            for r in rows:
                title = r[0] or r[1] or ''
                unread = not r[3]
                dot = "🔵 " if unread else "○ "
                ttk.Label(card, text=f"{dot}{str(title)[:34]}",
                          font=('Arial', 9, 'bold' if unread else 'normal'),
                          wraplength=190).pack(anchor='w')

        # ------------------------------------------------------------------
        # 4) Directory quick-search
        # ------------------------------------------------------------------
        def _build_directory_search(self, parent):
            self._section_header(parent, _t("alumni.directory_search",
                                            default="Find an Alum"), "🔍")
            box = ttk.Frame(parent)
            box.pack(fill=tk.X)

            self._dash_search_var = tk.StringVar()
            entry = ttk.Entry(box, textvariable=self._dash_search_var, width=40)
            entry.pack(side=tk.LEFT, padx=(0, 6))
            entry.bind("<Return>", lambda e: self._run_directory_search())
            ttk.Button(box, text=_t("common.search", default="Search"),
                       command=self._run_directory_search).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Button(box, text=_t("alumni.open_full_directory",
                                    default="Open full directory"),
                       command=self.show_alumni_directory).pack(side=tk.LEFT)

            cols = ("name", "year", "employer", "role")
            tree = ttk.Treeview(parent, columns=cols, show="headings", height=5)
            for c, txt, w in (("name", _t("alumni.col.name", default="Name"), 200),
                              ("year", _t("alumni.col.year", default="Year"), 70),
                              ("employer", _t("alumni.col.employer", default="Employer"), 200),
                              ("role", _t("alumni.col.role", default="Role"), 180)):
                tree.heading(c, text=txt)
                tree.column(c, width=w, anchor='w')
            tree.pack(fill=tk.X, pady=(6, 0))
            self._dash_search_tree = tree

        def _run_directory_search(self):
            tree = getattr(self, '_dash_search_tree', None)
            if tree is None:
                return
            for item in tree.get_children():
                tree.delete(item)
            term = (self._dash_search_var.get() or '').strip()
            if not term:
                return
            like = f"%{term}%"
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    """SELECT first_name, last_name, graduation_year,
                              current_employer, job_title
                         FROM alumni
                        WHERE first_name LIKE ? OR last_name LIKE ?
                           OR current_employer LIKE ? OR degree_earned LIKE ?
                        ORDER BY last_name, first_name LIMIT 25""",
                    (like, like, like, like))
                rows = cur.fetchall()
                conn.close()
            except sqlite3.Error:
                rows = []

            if not rows:
                tree.insert('', tk.END, values=(
                    _t("alumni.no_matches", default="No matches found."), "", "", ""))
                return
            for r in rows:
                name = " ".join(filter(None, [r[0], r[1]])).strip() or '—'
                tree.insert('', tk.END, values=(name, r[2] or '', r[3] or '', r[4] or ''))

        # ------------------------------------------------------------------
        # 5) Charts: donations over time + event registrations over time
        # ------------------------------------------------------------------
        def _build_charts(self, parent):
            self._section_header(parent, _t("alumni.trends", default="Trends"), "📈")
            holder = ttk.Frame(parent)
            holder.pack(fill=tk.X)

            if not MATPLOTLIB_AVAILABLE:
                ttk.Label(holder, text=_t("alumni.charts_unavailable",
                                          default="Charts require matplotlib "
                                                  "(pip install matplotlib)."),
                          foreground='#777').pack(anchor='w')
                return

            months, donation_series, reg_series = self._last_12_months_series()
            if not any(donation_series) and not any(reg_series):
                ttk.Label(holder, text=_t("alumni.no_trend_data",
                                          default="Not enough data to chart yet."),
                          foreground='#777').pack(anchor='w')
                return

            try:
                fig = Figure(figsize=(10, 3.2), dpi=100)
                fig.subplots_adjust(wspace=0.3, bottom=0.2)
                labels = [m[5:] for m in months]  # MM portion for compact axis

                ax1 = fig.add_subplot(121)
                ax1.bar(labels, donation_series, color='#27ae60')
                ax1.set_title(_t("alumni.chart.donations",
                                 default="Donations (£) — last 12 months"),
                              fontsize=9)
                ax1.tick_params(labelsize=7)

                ax2 = fig.add_subplot(122)
                ax2.plot(labels, reg_series, marker='o', color='#2980b9')
                ax2.set_title(_t("alumni.chart.event_regs",
                                 default="Event registrations — last 12 months"),
                              fontsize=9)
                ax2.tick_params(labelsize=7)

                canvas = FigureCanvasTkAgg(fig, master=holder)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.X, expand=True)
            except Exception:
                ttk.Label(holder, text=_t("alumni.chart_render_failed",
                                          default="Charts could not be rendered."),
                          foreground='#777').pack(anchor='w')

        def _last_12_months_series(self):
            """Return (month_labels, donation_totals, registration_counts) for
            the trailing 12 calendar months, zero-filled."""
            now = datetime.now()
            months = []
            y, m = now.year, now.month
            for _ in range(12):
                months.append(f"{y:04d}-{m:02d}")
                m -= 1
                if m == 0:
                    m = 12
                    y -= 1
            months.reverse()
            donation_map = {k: 0.0 for k in months}
            reg_map = {k: 0 for k in months}
            try:
                conn = get_connection()
                cur = conn.cursor()
                try:
                    cur.execute(
                        "SELECT strftime('%Y-%m', donation_date) ym, "
                        "COALESCE(SUM(amount), 0) FROM donations "
                        "WHERE donation_date >= date('now','-11 months','start of month') "
                        "GROUP BY ym")
                    for ym, total in cur.fetchall():
                        if ym in donation_map:
                            donation_map[ym] = float(total or 0)
                except sqlite3.Error:
                    pass
                try:
                    cur.execute(
                        "SELECT strftime('%Y-%m', registration_date) ym, COUNT(*) "
                        "FROM unified_event_registrations "
                        "WHERE registration_date >= date('now','-11 months','start of month') "
                        "GROUP BY ym")
                    for ym, n in cur.fetchall():
                        if ym in reg_map:
                            reg_map[ym] = int(n or 0)
                except sqlite3.Error:
                    pass
                conn.close()
            except sqlite3.Error:
                pass
            return (months,
                    [donation_map[k] for k in months],
                    [reg_map[k] for k in months])

        # ------------------------------------------------------------------
        # 6) Gamification: my points · badges · leaderboard
        # ------------------------------------------------------------------
        def _build_gamification(self, parent, alumni):
            self._section_header(parent, _t("alumni.engagement",
                                            default="Engagement"), "🏆")
            row = ttk.Frame(parent)
            row.pack(fill=tk.X)
            row.columnconfigure(0, weight=1)
            row.columnconfigure(1, weight=2)

            # My points + badges (left)
            mine = ttk.LabelFrame(row, text=_t("alumni.my_engagement",
                                               default="My Engagement"), padding=10)
            mine.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
            points = 0
            badges = 0
            if alumni:
                aid = alumni.get('alumni_id')
                points = alumni.get('engagement_score') or 0
                try:
                    conn = get_connection()
                    cur = conn.cursor()
                    earned = self._scalar(
                        cur, "SELECT COALESCE(SUM(points_earned),0) "
                             "FROM engagement_points WHERE alumni_id = ?", (aid,))
                    if earned:
                        points = earned
                    badges = self._scalar(
                        cur, "SELECT COUNT(*) FROM alumni_badges WHERE alumni_id = ?", (aid,))
                    conn.close()
                except sqlite3.Error:
                    pass
            ttk.Label(mine, text=_t("alumni.points_value",
                                    default="{n} pts").format(n=points),
                      font=('Arial', 18, 'bold')).pack(anchor='w')
            ttk.Label(mine, text=_t("alumni.badges_earned",
                                    default="{n} badge(s) earned").format(n=badges),
                      foreground='#555').pack(anchor='w')
            btns = ttk.Frame(mine)
            btns.pack(anchor='w', pady=(8, 0))
            ttk.Button(btns, text=_t("alumni.my_badges", default="My badges"),
                       command=self.show_my_badges).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Button(btns, text=_t("alumni.full_leaderboard",
                                     default="Full leaderboard"),
                       command=self.show_leaderboard).pack(side=tk.LEFT)

            # Top leaderboard (right)
            board = ttk.LabelFrame(row, text=_t("alumni.top_engaged",
                                                default="Top Engaged Alumni"), padding=10)
            board.grid(row=0, column=1, padx=5, pady=5, sticky='nsew')
            leaders = []
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    "SELECT first_name, last_name, graduation_year, engagement_score "
                    "FROM alumni WHERE COALESCE(engagement_score,0) > 0 "
                    "ORDER BY engagement_score DESC LIMIT 5")
                leaders = cur.fetchall()
                conn.close()
            except sqlite3.Error:
                leaders = []

            if not leaders:
                ttk.Label(board, text=_t("alumni.no_leaderboard",
                                         default="No engagement recorded yet."),
                          foreground='#777').pack(anchor='w')
            else:
                medals = ["🥇", "🥈", "🥉", "4.", "5."]
                for i, r in enumerate(leaders):
                    name = " ".join(filter(None, [r[0], r[1]])).strip() or '—'
                    yr = f" ('{str(r[2])[2:]})" if r[2] else ""
                    ttk.Label(board, text=f"{medals[i]}  {name}{yr} — {r[3] or 0} pts",
                              font=('Arial', 10)).pack(anchor='w')

        # ------------------------------------------------------------------
        # 7) Real recent-activity feed
        # ------------------------------------------------------------------
        def _build_activity_feed(self, parent):
            self._section_header(parent, _t("alumni.recent_activity",
                                            default="Recent Activity"), "🕑")
            frame = ttk.Frame(parent)
            frame.pack(fill=tk.BOTH, expand=True)
            activity_text = ScrolledText(frame, height=10, wrap=tk.WORD)
            activity_text.pack(fill=tk.BOTH, expand=True)

            events = self._collect_recent_activity()
            if not events:
                activity_text.insert(tk.END, _t("alumni.no_activity",
                                                 default="No recent activity to show."))
            else:
                for when, icon, text in events:
                    stamp = str(when)[:16].replace('T', ' ') if when else ''
                    activity_text.insert(tk.END, f"{icon}  {stamp}  —  {text}\n")
            activity_text.config(state=tk.DISABLED)

        def _collect_recent_activity(self, limit=15):
            """Merge recent rows across modules into one reverse-chronological feed.

            Each query is independent and best-effort: a missing table simply
            contributes nothing rather than breaking the feed."""
            items = []

            def _gather(sql, icon, fmt):
                try:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute(sql)
                    rows = cur.fetchall()
                    conn.close()
                except sqlite3.Error:
                    return
                for r in rows:
                    try:
                        items.append((r[0], icon, fmt(r)))
                    except Exception:
                        continue

            _gather(
                "SELECT date_registered, first_name, last_name FROM alumni "
                "WHERE date_registered IS NOT NULL ORDER BY date_registered DESC LIMIT 8",
                "👤",
                lambda r: _t("alumni.activity.registered",
                             default="{name} joined the alumni network").format(
                                 name=" ".join(filter(None, [r[1], r[2]])).strip() or "An alum"))
            _gather(
                "SELECT d.donation_date, a.first_name, a.last_name, d.amount "
                "FROM donations d LEFT JOIN alumni a ON a.alumni_id = d.alumni_id "
                "ORDER BY d.donation_date DESC LIMIT 8",
                "💰",
                lambda r: _t("alumni.activity.donated",
                             default="{name} donated £{amt:,.2f}").format(
                                 name=" ".join(filter(None, [r[1], r[2]])).strip() or "An alum",
                                 amt=float(r[3] or 0)))
            _gather(
                "SELECT r.registration_date, e.title "
                "FROM unified_event_registrations r "
                "JOIN unified_events e ON e.event_id = r.event_id "
                "ORDER BY r.registration_date DESC LIMIT 8",
                "📅",
                lambda r: _t("alumni.activity.rsvp",
                             default="New registration for {title}").format(
                                 title=r[1] or "an event"))
            _gather(
                "SELECT post_date, title FROM alumni_forum "
                "ORDER BY post_date DESC LIMIT 8",
                "💬",
                lambda r: _t("alumni.activity.forum",
                             default="New forum post: {title}").format(
                                 title=r[1] or "(untitled)"))
            _gather(
                "SELECT publish_date, title FROM alumni_stories "
                "ORDER BY publish_date DESC LIMIT 8",
                "📖",
                lambda r: _t("alumni.activity.story",
                             default="New story published: {title}").format(
                                 title=r[1] or "(untitled)"))

            # Sort by timestamp string (ISO-ish) descending; None sinks to bottom.
            items.sort(key=lambda x: (x[0] or ''), reverse=True)
            return items[:limit]
