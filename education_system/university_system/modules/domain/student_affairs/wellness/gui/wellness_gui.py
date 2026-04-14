"""
Mental Health & Wellness GUI Interface

Provides graphical interface for wellness tracking and mental health support.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Optional
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from education_system.university_system.modules.domain.student_affairs.wellness.services.wellness_service import WellnessService
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.infrastructure.localization import get_translation

_t = get_translation


class WellnessGUI:
    """Graphical interface for Mental Health & Wellness Hub."""

    def __init__(self, parent=None, auth=None):
        """Initialize the Wellness GUI."""
        self.service = WellnessService()
        self.auth = auth or get_auth()

        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title(_t("wellness.title", default="Mental Health & Wellness Hub"))
        self.root.geometry("1200x800")

        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        # Main container with crisis resources always visible
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Crisis resources panel (always visible at top)
        self.create_crisis_resources_panel(main_frame)

        # Check if user is logged in
        if not self.auth.current_user:
            ttk.Label(main_frame, text=_t("wellness.login_required", default="Please log in to access wellness features."),
                     font=('Arial', 14)).grid(row=1, column=0, pady=20)
            return

        # Wellness points display
        self.create_wellness_points_display(main_frame)

        # Create notebook for different sections
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        # Create tabs
        self.create_dashboard_tab()
        self.create_mood_tracking_tab()
        self.create_sleep_tracking_tab()
        self.create_activities_tab()
        self.create_goals_tab()
        self.create_counseling_tab()
        self.create_resources_tab()

        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

    def create_crisis_resources_panel(self, parent):
        """Create crisis resources panel (always visible)."""
        crisis_frame = ttk.LabelFrame(parent, text=_t("wellness.crisis_resources.title", default="🚨 CRISIS RESOURCES - AVAILABLE 24/7"),
                                     padding="10")
        crisis_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        resources = self.service.get_crisis_resources()

        # Display top crisis resources in a compact grid
        for i, resource in enumerate(resources[:4]):
            row = i // 2
            col = (i % 2) * 2

            ttk.Label(crisis_frame, text=f"{resource['resource_name']}:",
                     font=('Arial', 9, 'bold')).grid(row=row, column=col, sticky=tk.W, padx=5)
            ttk.Label(crisis_frame, text=resource['contact_info'],
                     font=('Arial', 9)).grid(row=row, column=col+1, sticky=tk.W, padx=5)

        crisis_frame.columnconfigure(0, weight=1)
        crisis_frame.columnconfigure(1, weight=1)
        crisis_frame.columnconfigure(2, weight=1)
        crisis_frame.columnconfigure(3, weight=1)

    def create_wellness_points_display(self, parent):
        """Create wellness points display."""
        points_frame = ttk.Frame(parent)
        points_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        student_id = self.auth.get_current_user()['username']
        total_points = self.service.get_total_wellness_points(student_id)

        # Determine level
        if total_points >= 1000:
            level = _t("wellness.wellness_points.levels.champion", default="Wellness Champion 🏆")
            color = "gold"
        elif total_points >= 500:
            level = _t("wellness.wellness_points.levels.master", default="Wellness Master ⭐")
            color = "blue"
        elif total_points >= 250:
            level = _t("wellness.wellness_points.levels.expert", default="Wellness Expert 💎")
            color = "purple"
        elif total_points >= 100:
            level = _t("wellness.wellness_points.levels.warrior", default="Wellness Warrior 🎖️")
            color = "green"
        elif total_points >= 50:
            level = _t("wellness.wellness_points.levels.enthusiast", default="Wellness Enthusiast ✨")
            color = "orange"
        else:
            level = _t("wellness.wellness_points.levels.beginner", default="Wellness Beginner 🌱")
            color = "gray"

        ttk.Label(points_frame, text=_t("wellness.wellness_points.title", default="Wellness Points: {points}").format(points=total_points),
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT, padx=10)
        ttk.Label(points_frame, text=_t("wellness.wellness_points.level", default="Level: {level}").format(level=level),
                 font=('Arial', 12)).pack(side=tk.LEFT, padx=10)

    def create_dashboard_tab(self):
        """Create dashboard tab with overview."""
        dashboard = ttk.Frame(self.notebook)
        self.notebook.add(dashboard, text=_t("wellness.tabs.dashboard", default="📊 Dashboard"))

        # Create two columns
        left_frame = ttk.Frame(dashboard)
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        right_frame = ttk.Frame(dashboard)
        right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # Wellness score card
        self.create_wellness_score_card(left_frame)

        # Mood chart
        self.create_mood_chart(left_frame)

        # Recent activities
        self.create_recent_activities(right_frame)

        # Quick actions
        self.create_quick_actions(right_frame)

        dashboard.columnconfigure(0, weight=1)
        dashboard.columnconfigure(1, weight=1)
        dashboard.rowconfigure(0, weight=1)

    def create_wellness_score_card(self, parent):
        """Create wellness score card."""
        score_frame = ttk.LabelFrame(parent, text=_t("wellness.dashboard.wellness_summary", default="Wellness Summary (Past 30 Days)"), padding="10")
        score_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        student_id = self.auth.get_current_user()['username']
        patterns = self.service.analyze_wellness_patterns(student_id, 30)

        if 'message' in patterns:
            ttk.Label(score_frame, text=patterns['message']).pack()
            return

        # Display averages
        avgs = patterns['averages']
        metrics = [
            (_t("wellness.dashboard.metrics.overall_mood", default="Overall Mood"), avgs['mood'], self.get_mood_emoji(avgs['mood'])),
            (_t("wellness.dashboard.metrics.stress_level", default="Stress Level"), avgs['stress'], self.get_stress_emoji(avgs['stress'])),
            (_t("wellness.dashboard.metrics.sleep_quality", default="Sleep Quality"), avgs['sleep_quality'], self.get_quality_emoji(avgs['sleep_quality'])),
            (_t("wellness.dashboard.metrics.energy_level", default="Energy Level"), avgs['energy'], self.get_quality_emoji(avgs['energy'])),
            (_t("wellness.dashboard.metrics.anxiety_level", default="Anxiety Level"), avgs['anxiety'], self.get_stress_emoji(avgs['anxiety']))
        ]

        for metric, value, emoji in metrics:
            metric_frame = ttk.Frame(score_frame)
            metric_frame.pack(fill=tk.X, pady=2)

            ttk.Label(metric_frame, text=f"{metric}:", width=15).pack(side=tk.LEFT)
            ttk.Label(metric_frame, text=f"{value:.1f}/10").pack(side=tk.LEFT, padx=5)
            ttk.Label(metric_frame, text=emoji, font=('Arial', 14)).pack(side=tk.LEFT)

        # Show concerns
        if patterns['concerns']:
            concerns_frame = ttk.LabelFrame(score_frame, text=_t("wellness.dashboard.concerns.title", default="⚠ Areas of Concern"), padding="5")
            concerns_frame.pack(fill=tk.X, pady=(10, 0))

            for concern in patterns['concerns']:
                ttk.Label(concerns_frame, text=f"• {concern}").pack(anchor=tk.W)

        # Recommendation
        rec_frame = ttk.Frame(score_frame)
        rec_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(rec_frame, text=_t("wellness.dashboard.recommendation_label", default="Recommendation:"), font=('Arial', 9, 'bold')).pack(anchor=tk.W)
        ttk.Label(rec_frame, text=patterns['recommendation'], wraplength=400).pack(anchor=tk.W)

    def create_mood_chart(self, parent):
        """Create mood trend chart."""
        chart_frame = ttk.LabelFrame(parent, text=_t("wellness.dashboard.mood_trends", default="Mood Trends (Past 30 Days)"), padding="10")
        chart_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        student_id = self.auth.get_current_user()['username']
        checkins = self.service.get_recent_checkins(student_id, 30)

        if not checkins:
            ttk.Label(chart_frame, text=_t("wellness.dashboard.no_data", default="No mood data available yet.")).pack()
            return

        # Create matplotlib figure
        fig = Figure(figsize=(6, 4), dpi=80)
        ax = fig.add_subplot(111)

        dates = [datetime.strptime(c['checkin_date'], '%Y-%m-%d') for c in reversed(checkins)]
        moods = [c['overall_mood'] for c in reversed(checkins)]
        stress = [c['stress_level'] for c in reversed(checkins)]

        ax.plot(dates, moods, marker='o', label=_t("wellness.dashboard.chart.mood_legend", default='Mood'), linewidth=2)
        ax.plot(dates, stress, marker='s', label=_t("wellness.dashboard.chart.stress_legend", default='Stress'), linewidth=2)

        ax.set_xlabel(_t("wellness.dashboard.chart.date_label", default='Date'))
        ax.set_ylabel(_t("wellness.dashboard.chart.level_label", default='Level (1-10)'))
        ax.set_title(_t("wellness.dashboard.chart.title", default='Mood & Stress Trends'))
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()

        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def create_recent_activities(self, parent):
        """Create recent activities display."""
        activities_frame = ttk.LabelFrame(parent, text=_t("wellness.dashboard.recent_activities", default="Recent Activities"), padding="10")
        activities_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), pady=(0, 10))

        # Create text widget with scrollbar
        text_widget = scrolledtext.ScrolledText(activities_frame, height=15, width=50,
                                                wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True)

        student_id = self.auth.get_current_user()['username']

        # Get recent mood entries
        moods = self.service.get_mood_history(student_id, 7)
        if moods:
            text_widget.insert(tk.END, _t("wellness.dashboard.recent_mood_entries", default="Recent Mood Entries:") + "\n", 'header')
            for mood in moods[:3]:
                entry_text = _t("wellness.dashboard.mood_entry", default="{date}: {mood} (Intensity: {intensity}/5)").format(
                    date=mood['mood_date'],
                    mood=mood['mood_type'],
                    intensity=mood['intensity']
                )
                text_widget.insert(tk.END, f"\n{entry_text}\n")
                if mood['notes']:
                    notes_text = _t("wellness.dashboard.notes_label", default="Notes: {notes}").format(notes=mood['notes'])
                    text_widget.insert(tk.END, f"  {notes_text}\n")

        # Get active goals
        goals = self.service.get_active_goals(student_id)
        if goals:
            text_widget.insert(tk.END, "\n\n" + _t("wellness.dashboard.active_goals", default="Active Goals:") + "\n", 'header')
            for goal in goals[:3]:
                percentage = (goal['current_value'] / goal['target_value']) * 100 if goal['target_value'] > 0 else 0
                goal_text = _t("wellness.dashboard.goal_progress", default="{type}: {percentage}% complete").format(
                    type=goal['goal_type'],
                    percentage=percentage
                )
                text_widget.insert(tk.END, f"\n{goal_text}\n")

        text_widget.tag_config('header', font=('Arial', 10, 'bold'))
        text_widget.config(state=tk.DISABLED)

    def create_quick_actions(self, parent):
        """Create quick actions panel."""
        actions_frame = ttk.LabelFrame(parent, text=_t("wellness.dashboard.quick_actions", default="Quick Actions"), padding="10")
        actions_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        actions = [
            (_t("wellness.dashboard.actions.log_mood", default="Log Mood"), lambda: self.notebook.select(1)),
            (_t("wellness.dashboard.actions.track_sleep", default="Track Sleep"), lambda: self.notebook.select(2)),
            (_t("wellness.dashboard.actions.log_exercise", default="Log Exercise"), lambda: self.notebook.select(3)),
            (_t("wellness.dashboard.actions.book_counseling", default="Book Counseling"), lambda: self.notebook.select(5)),
            (_t("wellness.dashboard.actions.view_resources", default="View Resources"), lambda: self.notebook.select(6))
        ]

        for i, (text, command) in enumerate(actions):
            ttk.Button(actions_frame, text=text, command=command,
                      width=20).grid(row=i, column=0, pady=5, sticky=(tk.W, tk.E))

        actions_frame.columnconfigure(0, weight=1)

    def create_mood_tracking_tab(self):
        """Create mood tracking tab."""
        mood_tab = ttk.Frame(self.notebook)
        self.notebook.add(mood_tab, text=_t("wellness.tabs.mood_tracking", default="😊 Mood Tracking"))

        # Create two panels
        left_panel = ttk.Frame(mood_tab)
        left_panel.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        right_panel = ttk.Frame(mood_tab)
        right_panel.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # Log mood form
        self.create_mood_log_form(left_panel)

        # Mood history
        self.create_mood_history(right_panel)

        mood_tab.columnconfigure(0, weight=1)
        mood_tab.columnconfigure(1, weight=1)
        mood_tab.rowconfigure(0, weight=1)

    def create_mood_log_form(self, parent):
        """Create mood logging form."""
        form_frame = ttk.LabelFrame(parent, text=_t("wellness.mood_tracking.log_form.title", default="Log Your Mood"), padding="10")
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Mood type with emoji buttons
        ttk.Label(form_frame, text=_t("wellness.mood_tracking.log_form.question", default="How are you feeling?"), font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        mood_types = [
            (_t("wellness.mood_tracking.moods.happy", default='😊 Happy'), 'Happy'),
            (_t("wellness.mood_tracking.moods.sad", default='😢 Sad'), 'Sad'),
            (_t("wellness.mood_tracking.moods.anxious", default='😰 Anxious'), 'Anxious'),
            (_t("wellness.mood_tracking.moods.stressed", default='😤 Stressed'), 'Stressed'),
            (_t("wellness.mood_tracking.moods.calm", default='😌 Calm'), 'Calm'),
            (_t("wellness.mood_tracking.moods.excited", default='😃 Excited'), 'Excited'),
            (_t("wellness.mood_tracking.moods.angry", default='😠 Angry'), 'Angry'),
            (_t("wellness.mood_tracking.moods.content", default='😊 Content'), 'Content'),
            (_t("wellness.mood_tracking.moods.overwhelmed", default='😵 Overwhelmed'), 'Overwhelmed'),
            (_t("wellness.mood_tracking.moods.peaceful", default='☮ Peaceful'), 'Peaceful')
        ]

        self.mood_var = tk.StringVar()
        mood_button_frame = ttk.Frame(form_frame)
        mood_button_frame.pack(fill=tk.X, pady=(0, 10))

        for i, (label, value) in enumerate(mood_types):
            row = i // 2
            col = i % 2
            ttk.Radiobutton(mood_button_frame, text=label, variable=self.mood_var,
                          value=value).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)

        # Intensity
        ttk.Label(form_frame, text=_t("wellness.mood_tracking.log_form.intensity_label", default="Intensity (1=Mild, 5=Intense):")).pack(anchor=tk.W, pady=(10, 0))
        self.intensity_var = tk.IntVar(value=3)
        intensity_scale = ttk.Scale(form_frame, from_=1, to=5, variable=self.intensity_var,
                                   orient=tk.HORIZONTAL)
        intensity_scale.pack(fill=tk.X, pady=(0, 10))

        # Triggers
        ttk.Label(form_frame, text=_t("wellness.mood_tracking.log_form.triggers_label", default="What triggered this mood?")).pack(anchor=tk.W)
        self.triggers_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.triggers_var, width=40).pack(fill=tk.X, pady=(0, 10))

        # Activities
        ttk.Label(form_frame, text=_t("wellness.mood_tracking.log_form.activities_label", default="Activities that helped/hurt:")).pack(anchor=tk.W)
        self.activities_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.activities_var, width=40).pack(fill=tk.X, pady=(0, 10))

        # Notes
        ttk.Label(form_frame, text=_t("wellness.mood_tracking.log_form.notes_label", default="Additional notes:")).pack(anchor=tk.W)
        self.mood_notes = scrolledtext.ScrolledText(form_frame, height=4, width=40)
        self.mood_notes.pack(fill=tk.X, pady=(0, 10))

        # Submit button
        ttk.Button(form_frame, text=_t("wellness.mood_tracking.log_form.submit", default="Log Mood"), command=self.submit_mood).pack(pady=10)

    def submit_mood(self):
        """Submit mood entry."""
        mood_type = self.mood_var.get()
        if not mood_type:
            messagebox.showwarning(
                _t("wellness.mood_tracking.messages.title_missing", default="Missing Information"),
                _t("wellness.mood_tracking.messages.missing_mood", default="Please select a mood type.")
            )
            return

        intensity = int(self.intensity_var.get())
        triggers = self.triggers_var.get() or None
        activities = self.activities_var.get() or None
        notes = self.mood_notes.get("1.0", tk.END).strip() or None

        student_id = self.auth.get_current_user()['username']
        mood_id = self.service.log_mood(student_id, mood_type, intensity,
                                       triggers, activities, notes)

        messagebox.showinfo(
            _t("wellness.mood_tracking.messages.title_success", default="Success"),
            _t("wellness.mood_tracking.messages.success", default="Mood logged successfully!\n+5 Wellness Points earned!")
        )

        # Clear form
        self.mood_var.set('')
        self.intensity_var.set(3)
        self.triggers_var.set('')
        self.activities_var.set('')
        self.mood_notes.delete("1.0", tk.END)

        # Refresh history
        self.refresh_mood_history()

    def create_mood_history(self, parent):
        """Create mood history display."""
        history_frame = ttk.LabelFrame(parent, text=_t("wellness.mood_tracking.history.title", default="Mood History (Past 30 Days)"), padding="10")
        history_frame.pack(fill=tk.BOTH, expand=True)

        # Create text widget
        self.mood_history_text = scrolledtext.ScrolledText(history_frame, height=20, width=50,
                                                           wrap=tk.WORD)
        self.mood_history_text.pack(fill=tk.BOTH, expand=True)

        # Refresh button
        ttk.Button(history_frame, text=_t("wellness.buttons.refresh", default="Refresh"), command=self.refresh_mood_history).pack(pady=5)

        self.refresh_mood_history()

    def refresh_mood_history(self):
        """Refresh mood history display."""
        self.mood_history_text.config(state=tk.NORMAL)
        self.mood_history_text.delete("1.0", tk.END)

        student_id = self.auth.get_current_user()['username']
        moods = self.service.get_mood_history(student_id, 30)

        if not moods:
            self.mood_history_text.insert(tk.END, _t("wellness.mood_tracking.history.no_entries", default="No mood entries yet."))
        else:
            for mood in moods:
                self.mood_history_text.insert(tk.END, f"\n{'=' * 50}\n")
                self.mood_history_text.insert(tk.END, f"{mood['mood_date']}: {mood['mood_type']}\n", 'header')
                intensity_text = _t("wellness.mood_tracking.history.intensity", default="Intensity: {intensity}/5").format(intensity=mood['intensity'])
                self.mood_history_text.insert(tk.END, f"{intensity_text}\n")
                if mood['triggers']:
                    triggers_text = _t("wellness.mood_tracking.history.triggers", default="Triggers: {triggers}").format(triggers=mood['triggers'])
                    self.mood_history_text.insert(tk.END, f"{triggers_text}\n")
                if mood['activities']:
                    activities_text = _t("wellness.mood_tracking.history.activities", default="Activities: {activities}").format(activities=mood['activities'])
                    self.mood_history_text.insert(tk.END, f"{activities_text}\n")
                if mood['notes']:
                    notes_text = _t("wellness.mood_tracking.history.notes", default="Notes: {notes}").format(notes=mood['notes'])
                    self.mood_history_text.insert(tk.END, f"{notes_text}\n")

        self.mood_history_text.tag_config('header', font=('Arial', 10, 'bold'))
        self.mood_history_text.config(state=tk.DISABLED)

    def create_sleep_tracking_tab(self):
        """Create sleep tracking tab."""
        sleep_tab = ttk.Frame(self.notebook)
        self.notebook.add(sleep_tab, text=_t("wellness.tabs.sleep_tracking", default="😴 Sleep Tracking"))

        # Create two panels
        left_panel = ttk.Frame(sleep_tab)
        left_panel.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        right_panel = ttk.Frame(sleep_tab)
        right_panel.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # Sleep log form
        self.create_sleep_log_form(left_panel)

        # Sleep analytics
        self.create_sleep_analytics_display(right_panel)

        sleep_tab.columnconfigure(0, weight=1)
        sleep_tab.columnconfigure(1, weight=1)
        sleep_tab.rowconfigure(0, weight=1)

    def create_sleep_log_form(self, parent):
        """Create sleep logging form."""
        form_frame = ttk.LabelFrame(parent, text=_t("wellness.sleep_tracking.form.title", default="Track Your Sleep"), padding="10")
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Date
        ttk.Label(form_frame, text=_t("wellness.sleep_tracking.form.date_label", default="Sleep Date:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.sleep_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(form_frame, textvariable=self.sleep_date_var, width=20).grid(row=0, column=1, pady=5)

        # Bedtime
        ttk.Label(form_frame, text=_t("wellness.sleep_tracking.form.bedtime_label", default="Bedtime (HH:MM):")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.bedtime_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.bedtime_var, width=20).grid(row=1, column=1, pady=5)

        # Wake time
        ttk.Label(form_frame, text=_t("wellness.sleep_tracking.form.wake_time_label", default="Wake Time (HH:MM):")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.wake_time_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.wake_time_var, width=20).grid(row=2, column=1, pady=5)

        # Hours slept
        ttk.Label(form_frame, text=_t("wellness.sleep_tracking.form.hours_label", default="Hours Slept:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.hours_slept_var = tk.DoubleVar()
        ttk.Entry(form_frame, textvariable=self.hours_slept_var, width=20).grid(row=3, column=1, pady=5)

        # Sleep quality
        ttk.Label(form_frame, text=_t("wellness.sleep_tracking.form.quality_label", default="Sleep Quality (1-5):")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.sleep_quality_var = tk.IntVar(value=3)
        ttk.Scale(form_frame, from_=1, to=5, variable=self.sleep_quality_var,
                 orient=tk.HORIZONTAL).grid(row=4, column=1, pady=5, sticky=(tk.W, tk.E))

        # Interruptions
        ttk.Label(form_frame, text=_t("wellness.sleep_tracking.form.interruptions_label", default="Interruptions:")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.interruptions_var = tk.IntVar(value=0)
        ttk.Spinbox(form_frame, from_=0, to=20, textvariable=self.interruptions_var,
                   width=18).grid(row=5, column=1, pady=5)

        # Notes
        ttk.Label(form_frame, text=_t("wellness.sleep_tracking.form.notes_label", default="Notes:")).grid(row=6, column=0, sticky=tk.W, pady=5)
        self.sleep_notes = scrolledtext.ScrolledText(form_frame, height=4, width=30)
        self.sleep_notes.grid(row=6, column=1, pady=5)

        # Submit button
        ttk.Button(form_frame, text=_t("wellness.sleep_tracking.form.submit", default="Log Sleep"), command=self.submit_sleep).grid(row=7, column=0,
                                                                                 columnspan=2, pady=10)

        form_frame.columnconfigure(1, weight=1)

    def submit_sleep(self):
        """Submit sleep entry."""
        try:
            sleep_date = self.sleep_date_var.get()
            bedtime = self.bedtime_var.get()
            wake_time = self.wake_time_var.get()
            hours_slept = self.hours_slept_var.get()
            sleep_quality = int(self.sleep_quality_var.get())
            interruptions = self.interruptions_var.get()
            notes = self.sleep_notes.get("1.0", tk.END).strip() or None

            if not all([bedtime, wake_time, hours_slept]):
                messagebox.showwarning(
                    _t("wellness.sleep_tracking.messages.title_missing", default="Missing Information"),
                    _t("wellness.sleep_tracking.messages.missing_fields", default="Please fill in bedtime, wake time, and hours slept.")
                )
                return

            student_id = self.auth.get_current_user()['username']
            sleep_id = self.service.log_sleep(student_id, sleep_date, bedtime, wake_time,
                                             hours_slept, sleep_quality, interruptions, notes)

            points = 5
            if hours_slept >= 7 and sleep_quality >= 4:
                points = 15
                messagebox.showinfo(
                    _t("wellness.sleep_tracking.messages.title_success", default="Success"),
                    _t("wellness.sleep_tracking.messages.success_quality", default="Sleep logged successfully!\n+15 Wellness Points (5 + 10 bonus for quality sleep)!")
                )
            else:
                messagebox.showinfo(
                    _t("wellness.sleep_tracking.messages.title_success", default="Success"),
                    _t("wellness.sleep_tracking.messages.success_basic", default="Sleep logged successfully!\n+5 Wellness Points!")
                )

            # Clear form
            self.bedtime_var.set('')
            self.wake_time_var.set('')
            self.hours_slept_var.set(0)
            self.sleep_quality_var.set(3)
            self.interruptions_var.set(0)
            self.sleep_notes.delete("1.0", tk.END)

            # Refresh analytics
            self.refresh_sleep_analytics()

        except Exception as e:
            messagebox.showerror(
                _t("wellness.sleep_tracking.messages.title_error", default="Error"),
                _t("wellness.sleep_tracking.messages.error", default="Failed to log sleep: {error}").format(error=str(e))
            )

    def create_sleep_analytics_display(self, parent):
        """Create sleep analytics display."""
        analytics_frame = ttk.LabelFrame(parent, text=_t("wellness.sleep_tracking.analytics.title", default="Sleep Analytics (Past 30 Days)"), padding="10")
        analytics_frame.pack(fill=tk.BOTH, expand=True)

        self.sleep_analytics_text = scrolledtext.ScrolledText(analytics_frame, height=20, width=50,
                                                              wrap=tk.WORD)
        self.sleep_analytics_text.pack(fill=tk.BOTH, expand=True)

        ttk.Button(analytics_frame, text=_t("wellness.buttons.refresh", default="Refresh"), command=self.refresh_sleep_analytics).pack(pady=5)

        self.refresh_sleep_analytics()

    def refresh_sleep_analytics(self):
        """Refresh sleep analytics display."""
        self.sleep_analytics_text.config(state=tk.NORMAL)
        self.sleep_analytics_text.delete("1.0", tk.END)

        student_id = self.auth.get_current_user()['username']
        analytics = self.service.get_sleep_analytics(student_id, 30)

        if 'message' in analytics:
            self.sleep_analytics_text.insert(tk.END, analytics['message'])
        else:
            self.sleep_analytics_text.insert(tk.END, _t("wellness.sleep_tracking.analytics.header", default="SLEEP ANALYSIS - PAST 30 DAYS") + "\n", 'header')
            self.sleep_analytics_text.insert(tk.END, "=" * 50 + "\n\n")
            self.sleep_analytics_text.insert(tk.END, _t("wellness.sleep_tracking.analytics.nights_tracked", default="Nights Tracked: {count}").format(count=analytics['nights_tracked']) + "\n")
            self.sleep_analytics_text.insert(tk.END, _t("wellness.sleep_tracking.analytics.average_hours", default="Average Hours: {hours} hours/night").format(hours=f"{analytics['average_hours']:.1f}") + "\n")
            self.sleep_analytics_text.insert(tk.END, _t("wellness.sleep_tracking.analytics.average_quality", default="Average Quality: {quality}/5").format(quality=f"{analytics['average_quality']:.1f}") + "\n")
            self.sleep_analytics_text.insert(tk.END, _t("wellness.sleep_tracking.analytics.total_interruptions", default="Total Interruptions: {count}").format(count=analytics['total_interruptions']) + "\n\n")
            self.sleep_analytics_text.insert(tk.END, _t("wellness.sleep_tracking.analytics.recommendation_header", default="RECOMMENDATION:") + f"\n{analytics['recommendation']}\n")

        self.sleep_analytics_text.tag_config('header', font=('Arial', 11, 'bold'))
        self.sleep_analytics_text.config(state=tk.DISABLED)

    def create_activities_tab(self):
        """Create activities tracking tab."""
        activities_tab = ttk.Frame(self.notebook)
        self.notebook.add(activities_tab, text=_t("wellness.tabs.activities", default="🏃 Activities"))

        # Create notebook for different activities
        activities_notebook = ttk.Notebook(activities_tab)
        activities_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Exercise tab
        exercise_frame = ttk.Frame(activities_notebook)
        activities_notebook.add(exercise_frame, text=_t("wellness.tabs.exercise", default="Exercise"))
        self.create_exercise_form(exercise_frame)

        # Hydration tab
        hydration_frame = ttk.Frame(activities_notebook)
        activities_notebook.add(hydration_frame, text=_t("wellness.tabs.hydration", default="Hydration"))
        self.create_hydration_form(hydration_frame)

    def create_exercise_form(self, parent):
        """Create exercise logging form."""
        form_frame = ttk.LabelFrame(parent, text=_t("wellness.activities.exercise.form_title", default="Log Exercise Activity"), padding="10")
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Exercise type
        ttk.Label(form_frame, text=_t("wellness.activities.exercise.type_label", default="Exercise Type:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.exercise_type_var = tk.StringVar()
        exercise_types = [
            _t("wellness.activities.exercise.types.running", default='Running'),
            _t("wellness.activities.exercise.types.walking", default='Walking'),
            _t("wellness.activities.exercise.types.cycling", default='Cycling'),
            _t("wellness.activities.exercise.types.swimming", default='Swimming'),
            _t("wellness.activities.exercise.types.gym", default='Gym Workout'),
            _t("wellness.activities.exercise.types.yoga", default='Yoga'),
            _t("wellness.activities.exercise.types.sports", default='Sports'),
            _t("wellness.activities.exercise.types.dancing", default='Dancing'),
            _t("wellness.activities.exercise.types.hiking", default='Hiking'),
            _t("wellness.activities.exercise.types.other", default='Other')
        ]
        ttk.Combobox(form_frame, textvariable=self.exercise_type_var,
                    values=exercise_types, width=25).grid(row=0, column=1, pady=5)

        # Duration
        ttk.Label(form_frame, text=_t("wellness.activities.exercise.duration_label", default="Duration (minutes):")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.exercise_duration_var = tk.IntVar()
        ttk.Entry(form_frame, textvariable=self.exercise_duration_var, width=27).grid(row=1, column=1, pady=5)

        # Intensity
        ttk.Label(form_frame, text=_t("wellness.activities.exercise.intensity_label", default="Intensity:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.exercise_intensity_var = tk.StringVar()
        intensity_values = [
            _t("wellness.activities.exercise.intensities.light", default='Light'),
            _t("wellness.activities.exercise.intensities.moderate", default='Moderate'),
            _t("wellness.activities.exercise.intensities.vigorous", default='Vigorous')
        ]
        ttk.Combobox(form_frame, textvariable=self.exercise_intensity_var,
                    values=intensity_values, width=25).grid(row=2, column=1, pady=5)

        # Calories
        ttk.Label(form_frame, text=_t("wellness.activities.exercise.calories_label", default="Calories Burned (optional):")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.exercise_calories_var = tk.IntVar()
        ttk.Entry(form_frame, textvariable=self.exercise_calories_var, width=27).grid(row=3, column=1, pady=5)

        # Notes
        ttk.Label(form_frame, text=_t("wellness.activities.exercise.notes_label", default="Notes:")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.exercise_notes = scrolledtext.ScrolledText(form_frame, height=4, width=30)
        self.exercise_notes.grid(row=4, column=1, pady=5)

        # Submit button
        ttk.Button(form_frame, text=_t("wellness.activities.exercise.submit", default="Log Exercise"), command=self.submit_exercise).grid(row=5, column=0,
                                                                                       columnspan=2, pady=10)

    def submit_exercise(self):
        """Submit exercise entry."""
        try:
            exercise_type = self.exercise_type_var.get()
            duration = self.exercise_duration_var.get()
            intensity = self.exercise_intensity_var.get()
            calories = self.exercise_calories_var.get() or None
            notes = self.exercise_notes.get("1.0", tk.END).strip() or None

            if not all([exercise_type, duration, intensity]):
                messagebox.showwarning(
                    _t("wellness.activities.exercise.messages.title_missing", default="Missing Information"),
                    _t("wellness.activities.exercise.messages.missing_fields", default="Please fill in exercise type, duration, and intensity.")
                )
                return

            student_id = self.auth.get_current_user()['username']
            exercise_id = self.service.log_exercise(student_id, exercise_type, duration,
                                                   intensity, calories, notes)

            points = min(duration // 10, 30)
            messagebox.showinfo(
                _t("wellness.activities.exercise.messages.title_success", default="Success"),
                _t("wellness.activities.exercise.messages.success", default="Exercise logged successfully!\n+{points} Wellness Points!").format(points=points)
            )

            # Clear form
            self.exercise_type_var.set('')
            self.exercise_duration_var.set(0)
            self.exercise_intensity_var.set('')
            self.exercise_calories_var.set(0)
            self.exercise_notes.delete("1.0", tk.END)

        except Exception as e:
            messagebox.showerror(
                _t("wellness.activities.exercise.messages.title_error", default="Error"),
                _t("wellness.activities.exercise.messages.error", default="Failed to log exercise: {error}").format(error=str(e))
            )

    def create_hydration_form(self, parent):
        """Create hydration tracking form."""
        form_frame = ttk.LabelFrame(parent, text=_t("wellness.activities.hydration.form_title", default="Track Hydration"), padding="10")
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Show current status
        student_id = self.auth.get_current_user()['username']
        status = self.service.get_hydration_status(student_id)

        status_frame = ttk.Frame(form_frame)
        status_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(status_frame, text=_t("wellness.activities.hydration.progress_label", default="Today's Progress:"), font=('Arial', 11, 'bold')).pack()
        self.hydration_status_label = ttk.Label(status_frame,
                                               text=_t("wellness.activities.hydration.status", default="{consumed}/{goal} glasses ({percentage}%)").format(
                                                   consumed=status['glasses_consumed'],
                                                   goal=status['daily_goal'],
                                                   percentage=f"{status['percentage']:.1f}"
                                               ),
                                               font=('Arial', 14))
        self.hydration_status_label.pack(pady=5)

        # Progress bar
        self.hydration_progress = ttk.Progressbar(status_frame, length=300, mode='determinate')
        self.hydration_progress.pack(pady=5)
        self.hydration_progress['value'] = min(status['percentage'], 100)

        # Add glasses
        add_frame = ttk.Frame(form_frame)
        add_frame.pack(pady=20)

        ttk.Label(add_frame, text=_t("wellness.activities.hydration.add_label", default="Add glasses:")).pack()
        self.hydration_glasses_var = tk.IntVar(value=1)
        ttk.Spinbox(add_frame, from_=1, to=10, textvariable=self.hydration_glasses_var,
                   width=10).pack(pady=5)

        ttk.Button(add_frame, text=_t("wellness.activities.hydration.submit", default="Log Hydration"), command=self.submit_hydration).pack(pady=10)

    def submit_hydration(self):
        """Submit hydration entry."""
        try:
            glasses = self.hydration_glasses_var.get()

            student_id = self.auth.get_current_user()['username']
            self.service.log_hydration(student_id, glasses)

            # Update display
            new_status = self.service.get_hydration_status(student_id)
            self.hydration_status_label.config(
                text=_t("wellness.activities.hydration.status", default="{consumed}/{goal} glasses ({percentage}%)").format(
                    consumed=new_status['glasses_consumed'],
                    goal=new_status['daily_goal'],
                    percentage=f"{new_status['percentage']:.1f}"
                )
            )
            self.hydration_progress['value'] = min(new_status['percentage'], 100)

            points = min(glasses, 10)
            msg = _t("wellness.activities.hydration.messages.success", default="Hydration logged! New total: {consumed}/{goal} glasses\n+{points} Wellness Points!").format(
                consumed=new_status['glasses_consumed'],
                goal=new_status['daily_goal'],
                points=points
            )

            if new_status['goal_met']:
                msg += _t("wellness.activities.hydration.messages.goal_achieved", default="\n\n🎉 Daily hydration goal achieved! Great job!")

            messagebox.showinfo(
                _t("wellness.activities.hydration.messages.title_success", default="Success"),
                msg
            )

        except Exception as e:
            messagebox.showerror(
                _t("wellness.activities.hydration.messages.title_error", default="Error"),
                _t("wellness.activities.hydration.messages.error", default="Failed to log hydration: {error}").format(error=str(e))
            )

    def create_goals_tab(self):
        """Create goals tracking tab."""
        goals_tab = ttk.Frame(self.notebook)
        self.notebook.add(goals_tab, text=_t("wellness.tabs.goals", default="🎯 Goals"))

        # Create two panels
        left_panel = ttk.Frame(goals_tab)
        left_panel.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        right_panel = ttk.Frame(goals_tab)
        right_panel.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # Create goal form
        self.create_goal_form(left_panel)

        # Active goals display
        self.create_active_goals_display(right_panel)

        goals_tab.columnconfigure(0, weight=1)
        goals_tab.columnconfigure(1, weight=1)
        goals_tab.rowconfigure(0, weight=1)

    def create_goal_form(self, parent):
        """Create goal creation form."""
        form_frame = ttk.LabelFrame(parent, text=_t("wellness.goals.form.title", default="Set a New Goal"), padding="10")
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Goal type
        ttk.Label(form_frame, text=_t("wellness.goals.form.type_label", default="Goal Type:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.goal_type_var = tk.StringVar()
        goal_types = [
            _t("wellness.goals.form.types.sleep_hours", default='Sleep Hours'),
            _t("wellness.goals.form.types.exercise_minutes", default='Exercise Minutes'),
            _t("wellness.goals.form.types.hydration", default='Hydration'),
            _t("wellness.goals.form.types.meditation_minutes", default='Meditation Minutes'),
            _t("wellness.goals.form.types.stress_reduction", default='Stress Reduction'),
            _t("wellness.goals.form.types.weight", default='Weight'),
            _t("wellness.goals.form.types.steps", default='Steps'),
            _t("wellness.goals.form.types.custom", default='Custom')
        ]
        ttk.Combobox(form_frame, textvariable=self.goal_type_var,
                    values=goal_types, width=25).grid(row=0, column=1, pady=5)

        # Description
        ttk.Label(form_frame, text=_t("wellness.goals.form.description_label", default="Description:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.goal_description_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.goal_description_var, width=27).grid(row=1, column=1, pady=5)

        # Target value
        ttk.Label(form_frame, text=_t("wellness.goals.form.target_label", default="Target Value:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.goal_target_var = tk.DoubleVar()
        ttk.Entry(form_frame, textvariable=self.goal_target_var, width=27).grid(row=2, column=1, pady=5)

        # End date
        ttk.Label(form_frame, text=_t("wellness.goals.form.end_date_label", default="End Date (optional):")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.goal_end_date_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.goal_end_date_var, width=27).grid(row=3, column=1, pady=5)

        # Submit button
        ttk.Button(form_frame, text=_t("wellness.goals.form.submit", default="Create Goal"), command=self.submit_goal).grid(row=4, column=0,
                                                                                  columnspan=2, pady=10)

    def submit_goal(self):
        """Submit new goal."""
        try:
            goal_type = self.goal_type_var.get()
            description = self.goal_description_var.get()
            target = self.goal_target_var.get()
            end_date = self.goal_end_date_var.get() or None

            if not all([goal_type, description, target]):
                messagebox.showwarning(
                    _t("wellness.goals.messages.title_missing", default="Missing Information"),
                    _t("wellness.goals.messages.missing_fields", default="Please fill in goal type, description, and target value.")
                )
                return

            student_id = self.auth.get_current_user()['username']
            goal_id = self.service.create_wellness_goal(student_id, goal_type, description,
                                                       target, end_date)

            messagebox.showinfo(
                _t("wellness.goals.messages.title_success", default="Success"),
                _t("wellness.goals.messages.success", default="Wellness goal created!\nKeep tracking your progress to earn bonus points!")
            )

            # Clear form
            self.goal_type_var.set('')
            self.goal_description_var.set('')
            self.goal_target_var.set(0)
            self.goal_end_date_var.set('')

            # Refresh goals display
            self.refresh_active_goals()

        except Exception as e:
            messagebox.showerror(
                _t("wellness.goals.messages.title_error", default="Error"),
                _t("wellness.goals.messages.error", default="Failed to create goal: {error}").format(error=str(e))
            )

    def create_active_goals_display(self, parent):
        """Create active goals display."""
        goals_frame = ttk.LabelFrame(parent, text=_t("wellness.goals.display.title", default="Active Goals"), padding="10")
        goals_frame.pack(fill=tk.BOTH, expand=True)

        self.goals_text = scrolledtext.ScrolledText(goals_frame, height=20, width=50, wrap=tk.WORD)
        self.goals_text.pack(fill=tk.BOTH, expand=True)

        ttk.Button(goals_frame, text=_t("wellness.buttons.refresh", default="Refresh"), command=self.refresh_active_goals).pack(pady=5)

        self.refresh_active_goals()

    def refresh_active_goals(self):
        """Refresh active goals display."""
        self.goals_text.config(state=tk.NORMAL)
        self.goals_text.delete("1.0", tk.END)

        student_id = self.auth.get_current_user()['username']
        goals = self.service.get_active_goals(student_id)

        if not goals:
            self.goals_text.insert(tk.END, _t("wellness.goals.display.no_goals", default="No active goals. Set a goal to start tracking your progress!"))
        else:
            for goal in goals:
                self.goals_text.insert(tk.END, "=" * 50 + "\n")
                self.goals_text.insert(tk.END, f"{goal['goal_type']}\n", 'header')
                self.goals_text.insert(tk.END, f"{goal['goal_description']}\n\n")

                percentage = (goal['current_value'] / goal['target_value']) * 100 if goal['target_value'] > 0 else 0
                progress_text = _t("wellness.goals.display.progress", default="Progress: {current} / {target}").format(
                    current=f"{goal['current_value']:.1f}",
                    target=f"{goal['target_value']:.1f}"
                )
                completion_text = _t("wellness.goals.display.completion", default="Completion: {percentage}%").format(
                    percentage=f"{percentage:.1f}"
                )
                self.goals_text.insert(tk.END, f"{progress_text}\n")
                self.goals_text.insert(tk.END, f"{completion_text}\n")

                if goal['end_date']:
                    target_date_text = _t("wellness.goals.display.target_date", default="Target Date: {date}").format(date=goal['end_date'])
                    self.goals_text.insert(tk.END, f"{target_date_text}\n")
                started_text = _t("wellness.goals.display.started", default="Started: {date}").format(date=goal['start_date'])
                self.goals_text.insert(tk.END, f"{started_text}\n\n")

        self.goals_text.tag_config('header', font=('Arial', 10, 'bold'))
        self.goals_text.config(state=tk.DISABLED)

    def create_counseling_tab(self):
        """Create counseling appointments tab."""
        counseling_tab = ttk.Frame(self.notebook)
        self.notebook.add(counseling_tab, text=_t("wellness.tabs.counseling", default="💬 Counseling"))

        # Privacy notice
        privacy_frame = ttk.Frame(counseling_tab)
        privacy_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(privacy_frame, text=_t("wellness.counseling.privacy_notice", default="🔒 All counseling appointments are confidential and private."),
                 font=('Arial', 10, 'italic')).pack()

        # Create two panels
        left_panel = ttk.Frame(counseling_tab)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        right_panel = ttk.Frame(counseling_tab)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Booking form
        self.create_counseling_form(left_panel)

        # Appointments display
        self.create_appointments_display(right_panel)

    def create_counseling_form(self, parent):
        """Create counseling appointment booking form."""
        form_frame = ttk.LabelFrame(parent, text=_t("wellness.counseling.form.title", default="Book Counseling Appointment"), padding="10")
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Date
        ttk.Label(form_frame, text=_t("wellness.counseling.form.date_label", default="Appointment Date:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.counseling_date_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.counseling_date_var, width=27).grid(row=0, column=1, pady=5)
        ttk.Label(form_frame, text=_t("wellness.counseling.form.date_format", default="(YYYY-MM-DD)"), font=('Arial', 8)).grid(row=0, column=2, sticky=tk.W)

        # Time
        ttk.Label(form_frame, text=_t("wellness.counseling.form.time_label", default="Preferred Time:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.counseling_time_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.counseling_time_var, width=27).grid(row=1, column=1, pady=5)
        ttk.Label(form_frame, text=_t("wellness.counseling.form.time_format", default="(HH:MM)"), font=('Arial', 8)).grid(row=1, column=2, sticky=tk.W)

        # Appointment type
        ttk.Label(form_frame, text=_t("wellness.counseling.form.type_label", default="Appointment Type:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.counseling_type_var = tk.StringVar()
        appt_types = [
            _t("wellness.counseling.form.types.individual", default='Individual Counseling'),
            _t("wellness.counseling.form.types.group", default='Group Therapy'),
            _t("wellness.counseling.form.types.crisis", default='Crisis Intervention'),
            _t("wellness.counseling.form.types.academic", default='Academic Stress'),
            _t("wellness.counseling.form.types.relationship", default='Relationship Issues'),
            _t("wellness.counseling.form.types.anxiety", default='Anxiety/Depression'),
            _t("wellness.counseling.form.types.consultation", default='General Consultation')
        ]
        ttk.Combobox(form_frame, textvariable=self.counseling_type_var,
                    values=appt_types, width=25).grid(row=2, column=1, pady=5)

        # Notes
        ttk.Label(form_frame, text=_t("wellness.counseling.form.notes_label", default="Concerns (confidential):")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.counseling_notes = scrolledtext.ScrolledText(form_frame, height=6, width=30)
        self.counseling_notes.grid(row=3, column=1, pady=5)

        # Submit button
        ttk.Button(form_frame, text=_t("wellness.counseling.form.submit", default="Book Appointment"), command=self.submit_counseling).grid(row=4, column=0,
                                                                                             columnspan=2, pady=10)

    def submit_counseling(self):
        """Submit counseling appointment."""
        try:
            appt_date = self.counseling_date_var.get()
            appt_time = self.counseling_time_var.get()
            appt_type = self.counseling_type_var.get()
            notes = self.counseling_notes.get("1.0", tk.END).strip() or None

            if not all([appt_date, appt_time, appt_type]):
                messagebox.showwarning(
                    _t("wellness.counseling.messages.title_missing", default="Missing Information"),
                    _t("wellness.counseling.messages.missing_fields", default="Please fill in date, time, and appointment type.")
                )
                return

            student_id = self.auth.get_current_user()['username']
            appointment_id = self.service.schedule_counseling(student_id, appt_date, appt_time,
                                                             appt_type, notes)

            messagebox.showinfo(
                _t("wellness.counseling.messages.title_success", default="Success"),
                _t("wellness.counseling.messages.success", default="Counseling appointment booked!\n\nDate: {date} at {time}\nType: {type}\n\nYou will receive a confirmation.\nAll information is confidential.").format(
                    date=appt_date,
                    time=appt_time,
                    type=appt_type
                )
            )

            # Clear form
            self.counseling_date_var.set('')
            self.counseling_time_var.set('')
            self.counseling_type_var.set('')
            self.counseling_notes.delete("1.0", tk.END)

            # Refresh appointments
            self.refresh_appointments()

        except Exception as e:
            messagebox.showerror(
                _t("wellness.counseling.messages.title_error", default="Error"),
                _t("wellness.counseling.messages.error", default="Failed to book appointment: {error}").format(error=str(e))
            )

    def create_appointments_display(self, parent):
        """Create appointments display."""
        appts_frame = ttk.LabelFrame(parent, text=_t("wellness.counseling.appointments.title", default="My Appointments"), padding="10")
        appts_frame.pack(fill=tk.BOTH, expand=True)

        self.appointments_text = scrolledtext.ScrolledText(appts_frame, height=20, width=50, wrap=tk.WORD)
        self.appointments_text.pack(fill=tk.BOTH, expand=True)

        ttk.Button(appts_frame, text=_t("wellness.buttons.refresh", default="Refresh"), command=self.refresh_appointments).pack(pady=5)

        self.refresh_appointments()

    def refresh_appointments(self):
        """Refresh appointments display."""
        self.appointments_text.config(state=tk.NORMAL)
        self.appointments_text.delete("1.0", tk.END)

        student_id = self.auth.get_current_user()['username']
        appointments = self.service.get_counseling_appointments(student_id)

        if not appointments:
            self.appointments_text.insert(tk.END, _t("wellness.counseling.appointments.no_appointments", default="No appointments scheduled."))
        else:
            for appt in appointments:
                self.appointments_text.insert(tk.END, "=" * 50 + "\n")
                appt_id_text = _t("wellness.counseling.appointments.appointment_id", default="Appointment ID: {id}").format(id=appt['appointment_id'])
                self.appointments_text.insert(tk.END, f"{appt_id_text}\n", 'header')
                date_time_text = _t("wellness.counseling.appointments.date_time", default="Date: {date} at {time}").format(
                    date=appt['appointment_date'],
                    time=appt['appointment_time']
                )
                self.appointments_text.insert(tk.END, f"{date_time_text}\n")
                type_text = _t("wellness.counseling.appointments.type", default="Type: {type}").format(type=appt['appointment_type'])
                self.appointments_text.insert(tk.END, f"{type_text}\n")
                status_text = _t("wellness.counseling.appointments.status", default="Status: {status}").format(status=appt['status'])
                self.appointments_text.insert(tk.END, f"{status_text}\n")
                if appt['counselor_name']:
                    counselor_text = _t("wellness.counseling.appointments.counselor", default="Counselor: {name}").format(name=appt['counselor_name'])
                    self.appointments_text.insert(tk.END, f"{counselor_text}\n")
                self.appointments_text.insert(tk.END, "\n")

        self.appointments_text.tag_config('header', font=('Arial', 10, 'bold'))
        self.appointments_text.config(state=tk.DISABLED)

    def create_resources_tab(self):
        """Create resources tab."""
        resources_tab = ttk.Frame(self.notebook)
        self.notebook.add(resources_tab, text=_t("wellness.tabs.resources", default="📚 Resources"))

        # Crisis resources
        crisis_frame = ttk.LabelFrame(resources_tab, text=_t("wellness.resources.crisis_title", default="🚨 Crisis Resources - Available 24/7"), padding="10")
        crisis_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        resources = self.service.get_crisis_resources()

        for resource in resources:
            resource_frame = ttk.Frame(crisis_frame)
            resource_frame.pack(fill=tk.X, pady=5)

            ttk.Label(resource_frame, text=resource['resource_name'],
                     font=('Arial', 11, 'bold')).pack(anchor=tk.W)
            type_text = _t("wellness.resources.resource_type", default="Type: {type}").format(type=resource['resource_type'])
            ttk.Label(resource_frame, text=type_text).pack(anchor=tk.W)
            contact_text = _t("wellness.resources.resource_contact", default="Contact: {contact}").format(contact=resource['contact_info'])
            ttk.Label(resource_frame, text=contact_text,
                     font=('Arial', 10, 'bold')).pack(anchor=tk.W)
            if resource['description']:
                ttk.Label(resource_frame, text=resource['description'],
                         wraplength=600).pack(anchor=tk.W)
            availability_text = _t("wellness.resources.resource_availability", default="Availability: {availability}").format(availability=resource['availability'])
            ttk.Label(resource_frame, text=availability_text).pack(anchor=tk.W)
            ttk.Separator(crisis_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        # Emergency notice
        emergency_frame = ttk.Frame(crisis_frame)
        emergency_frame.pack(pady=10)

        ttk.Label(emergency_frame,
                 text=_t("wellness.crisis_resources.emergency_notice", default="⚠ If you are in immediate danger, please call 911 or go to your nearest emergency room."),
                 font=('Arial', 10, 'bold'),
                 foreground='red',
                 wraplength=600).pack()

    def get_mood_emoji(self, score: float) -> str:
        """Get emoji for mood score."""
        if score >= 8:
            return "😊"
        elif score >= 6:
            return "🙂"
        elif score >= 4:
            return "😐"
        else:
            return "☹️"

    def get_stress_emoji(self, score: float) -> str:
        """Get emoji for stress/anxiety score."""
        if score >= 8:
            return "😰"
        elif score >= 6:
            return "😟"
        elif score >= 4:
            return "😐"
        else:
            return "😌"

    def get_quality_emoji(self, score: float) -> str:
        """Get emoji for quality score."""
        if score >= 8:
            return "⭐"
        elif score >= 6:
            return "✓"
        elif score >= 4:
            return "~"
        else:
            return "✗"

    def run(self):
        """Run the GUI."""
        self.root.mainloop()


def main():
    """Main entry point for wellness GUI."""
    app = WellnessGUI()
    app.run()


if __name__ == '__main__':
    main()
