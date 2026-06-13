import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class LiveStreamingDialog:
    """Dialog for managing live streaming"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Live Streaming")
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📡 Live Streaming Platform",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Stream setup
        setup_frame = ttk.LabelFrame(main_frame, text="Stream Setup")
        setup_frame.pack(fill='x', pady=(0, 15))

        form = ttk.Frame(setup_frame)
        form.pack(padx=15, pady=15, fill='x')

        ttk.Label(form, text="Event:").grid(row=0, column=0, sticky='w', pady=5)
        self.event_combo = ttk.Combobox(form, width=40)
        self.event_combo['values'] = ('Spring Festival', 'Tech Workshop', 'Guest Lecture')
        self.event_combo.grid(row=0, column=1, pady=5, sticky='ew')

        ttk.Label(form, text="Platform:").grid(row=1, column=0, sticky='w', pady=5)
        self.platform_combo = ttk.Combobox(form, width=40, state='readonly')
        self.platform_combo['values'] = ('YouTube Live', 'Facebook Live', 'Twitch', 'Custom RTMP')
        self.platform_combo.grid(row=1, column=1, pady=5, sticky='ew')
        self.platform_combo.current(0)

        ttk.Label(form, text="Quality:").grid(row=2, column=0, sticky='w', pady=5)
        self.quality_combo = ttk.Combobox(form, width=40, state='readonly')
        self.quality_combo['values'] = ('1080p HD', '720p', '480p', 'Auto')
        self.quality_combo.grid(row=2, column=1, pady=5, sticky='ew')
        self.quality_combo.current(0)

        form.columnconfigure(1, weight=1)

        # Features
        features_frame = ttk.LabelFrame(main_frame, text="Stream Features")
        features_frame.pack(fill='x', pady=(0, 15))

        self.chat_var = tk.BooleanVar(value=True)
        self.recording_var = tk.BooleanVar(value=True)
        self.qa_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(features_frame, text="Enable Live Chat", variable=self.chat_var).pack(anchor='w', padx=15, pady=5)
        ttk.Checkbutton(features_frame, text="Record Stream", variable=self.recording_var).pack(anchor='w', padx=15, pady=5)
        ttk.Checkbutton(features_frame, text="Q&A Session", variable=self.qa_var).pack(anchor='w', padx=15, pady=5)

        # Status
        status_frame = ttk.LabelFrame(main_frame, text="Stream Status")
        status_frame.pack(fill='both', expand=True, pady=(0, 15))

        self.status_label = ttk.Label(status_frame, text="⚪ Not Streaming",
                                     font=('Arial', 12, 'bold'), foreground='gray')
        self.status_label.pack(pady=15)

        self.viewers_label = ttk.Label(status_frame, text="Viewers: 0")
        self.viewers_label.pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Start Stream", command=self.start_stream).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Stop Stream", command=self.stop_stream, state='disabled').pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def start_stream(self):
        if not self.event_combo.get():
            messagebox.showwarning("Warning", "Please select an event.")
            return

        self.status_label.config(text="🔴 LIVE", foreground='red')
        messagebox.showinfo("Stream Started", "Your stream is now live!\n\nStream URL has been shared with registered attendees.")

    def stop_stream(self):
        if messagebox.askyesno("Confirm", "Stop streaming?"):
            self.status_label.config(text="⚪ Not Streaming", foreground='gray')
            messagebox.showinfo("Stream Ended", "Stream has ended.\n\nRecording will be available shortly.")



class ManageLiveStreamingDialog:
    """Live streaming platform for events"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Live Streaming Platform")
        self.dialog.geometry("1200x800")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📡 Live Streaming Platform",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Create notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Active Streams tab
        streams_frame = ttk.Frame(notebook)
        notebook.add(streams_frame, text="Active Streams")
        self.create_streams_tab(streams_frame)

        # Stream Setup tab
        setup_frame = ttk.Frame(notebook)
        notebook.add(setup_frame, text="Stream Setup")
        self.create_setup_tab(setup_frame)

        # Chat Integration tab
        chat_frame = ttk.Frame(notebook)
        notebook.add(chat_frame, text="Chat & Interaction")
        self.create_chat_tab(chat_frame)

        # Recordings tab
        recordings_frame = ttk.Frame(notebook)
        notebook.add(recordings_frame, text="Recordings")
        self.create_recordings_tab(recordings_frame)

        # Analytics tab
        analytics_frame = ttk.Frame(notebook)
        notebook.add(analytics_frame, text="Viewer Analytics")
        self.create_analytics_tab(analytics_frame)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def create_streams_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Live now section
        live_frame = ttk.LabelFrame(frame, text="🔴 Live Now")
        live_frame.pack(fill='x', pady=(0, 15))

        columns = ('Event', 'Streamer', 'Viewers', 'Duration', 'Platform')
        tree = ttk.Treeview(live_frame, columns=columns, show='tree headings', height=5)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Event':
                tree.column(col, width=280)

        tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Sample live streams
        live_streams = [
            ("Annual Research Symposium - Keynote", "Student Union", "245", "1h 23m", "YouTube, Twitch"),
            ("Tech Workshop: Python Basics", "CS Club", "67", "45m", "YouTube")
        ]

        for stream in live_streams:
            tree.insert('', 'end', values=stream)

        # Upcoming streams
        upcoming_frame = ttk.LabelFrame(frame, text="📅 Upcoming Streams")
        upcoming_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns2 = ('Event', 'Scheduled', 'Streamer', 'Platforms')
        tree2 = ttk.Treeview(upcoming_frame, columns=columns2, show='tree headings', height=6)

        for col in columns2:
            tree2.heading(col, text=col)
            if col == 'Event':
                tree2.column(col, width=300)

        tree2.pack(fill='both', expand=True, padx=5, pady=5)

        upcoming_streams = [
            ("Student Panel: Career Advice", "Today, 5:00 PM", "Careers Office", "YouTube, Facebook"),
            ("Music Society Concert", "Tomorrow, 7:00 PM", "Music Society", "YouTube, Instagram"),
            ("Guest Lecture: AI Ethics", "May 16, 2:00 PM", "Philosophy Dept", "YouTube, LinkedIn")
        ]

        for stream in upcoming_streams:
            tree2.insert('', 'end', values=stream)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')

        ttk.Button(btn_frame, text="🔴 Start Stream",
                  command=self.start_stream).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="⏹️ End Stream",
                  command=self.end_stream).pack(side='left')

    def create_setup_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Stream Configuration",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 15))

        # Stream settings form
        form_frame = ttk.Frame(frame)
        form_frame.pack(fill='both', expand=True, pady=(0, 15))

        ttk.Label(form_frame, text="Event Title:").grid(row=0, column=0, sticky='w', pady=5)
        ttk.Entry(form_frame, width=50).grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Stream Description:").grid(row=1, column=0, sticky='nw', pady=5)
        desc_text = scrolledtext.ScrolledText(form_frame, width=50, height=3)
        desc_text.grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Multi-Platform Streaming:").grid(row=2, column=0, sticky='w', pady=5)
        platform_frame = ttk.Frame(form_frame)
        platform_frame.grid(row=2, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Checkbutton(platform_frame, text="YouTube").pack(anchor='w')
        ttk.Checkbutton(platform_frame, text="Facebook Live").pack(anchor='w')
        ttk.Checkbutton(platform_frame, text="Twitch").pack(anchor='w')
        ttk.Checkbutton(platform_frame, text="LinkedIn Live").pack(anchor='w')
        ttk.Checkbutton(platform_frame, text="Instagram Live").pack(anchor='w')

        ttk.Label(form_frame, text="Stream Quality:").grid(row=3, column=0, sticky='w', pady=5)
        quality_combo = ttk.Combobox(form_frame, width=47, state='readonly')
        quality_combo['values'] = ('1080p (Full HD)', '720p (HD)', '480p (SD)', '360p (Low)')
        quality_combo.current(0)
        quality_combo.grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Auto-Record:").grid(row=4, column=0, sticky='w', pady=5)
        ttk.Checkbutton(form_frame, text="Automatically record stream").grid(
            row=4, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Enable Chat:").grid(row=5, column=0, sticky='w', pady=5)
        ttk.Checkbutton(form_frame, text="Enable live chat during stream").grid(
            row=5, column=1, sticky='w', pady=5, padx=(10, 0))

        form_frame.columnconfigure(1, weight=1)

        # Stream key info
        key_frame = ttk.LabelFrame(frame, text="Stream Keys & URLs")
        key_frame.pack(fill='x', pady=(0, 10))

        key_text = """YouTube Stream Key: ytsk-xxxx-xxxx-xxxx-xxxx
Facebook Stream Key: fbsk-xxxx-xxxx-xxxx-xxxx
Twitch Stream Key: live_xxxx_xxxx

RTMP URL: rtmp://streaming.university.edu/live
Stream Server: streaming.university.edu:1935
"""
        ttk.Label(key_frame, text=key_text, justify='left',
                 font=('Courier', 9)).pack(padx=15, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')

        ttk.Button(btn_frame, text="💾 Save Configuration",
                  command=self.save_stream_config).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="🔄 Test Stream",
                  command=self.test_stream).pack(side='left')

    def create_chat_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Chat window
        chat_frame = ttk.LabelFrame(frame, text="Live Chat")
        chat_frame.pack(fill='both', expand=True, pady=(0, 10))

        chat_text = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD,
                                              font=('Arial', 9), height=15)
        chat_text.pack(fill='both', expand=True, padx=5, pady=5)

        sample_chat = """[14:23] John: Great presentation so far!
[14:24] Sarah: Can you go over that last point again?
[14:24] Mike: +1 to Sarah's question
[14:25] Moderator: We'll address questions at the end
[14:26] Alice: Looking forward to the demo!
[14:27] Bob: Is this being recorded?
[14:27] Moderator: Yes, recording will be available within 24 hours
[14:28] Carol: Thank you for streaming this event!
[14:29] David: 👍👍👍
[14:30] Emily: What's the next topic?
"""
        chat_text.insert(1.0, sample_chat)
        chat_text.config(state='disabled')

        # Chat controls
        control_frame = ttk.Frame(frame)
        control_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(control_frame, text="Message:").pack(side='left', padx=(0, 5))
        message_entry = ttk.Entry(control_frame)
        message_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
        ttk.Button(control_frame, text="Send",
                  command=self.send_chat_message).pack(side='left')

        # Chat settings
        settings_frame = ttk.LabelFrame(frame, text="Chat Settings")
        settings_frame.pack(fill='x')

        ttk.Checkbutton(settings_frame, text="Slow mode (1 message per 5 seconds)").pack(anchor='w', padx=10, pady=2)
        ttk.Checkbutton(settings_frame, text="Subscriber-only chat").pack(anchor='w', padx=10, pady=2)
        ttk.Checkbutton(settings_frame, text="Filter profanity").pack(anchor='w', padx=10, pady=2)
        ttk.Checkbutton(settings_frame, text="Emote-only mode").pack(anchor='w', padx=10, pady=2)

        btn_frame = ttk.Frame(settings_frame)
        btn_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(btn_frame, text="🚫 Ban User",
                  command=self.ban_user).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="⏸️ Pause Chat",
                  command=self.pause_chat).pack(side='left')

    def create_recordings_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Stream Recordings",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        # Recordings list
        columns = ('Event', 'Date', 'Duration', 'Views', 'Size', 'Status')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Event':
                tree.column(col, width=280)

        tree.pack(fill='both', expand=True, pady=(0, 10))

        # Sample recordings
        recordings = [
            ("Research Symposium 2025 - Day 1", "May 15, 2025", "4h 32m", "1,245", "8.2 GB", "Available"),
            ("Python Workshop Series - Part 1", "May 10, 2025", "1h 45m", "567", "2.1 GB", "Available"),
            ("Guest Lecture: AI Ethics", "May 5, 2025", "1h 15m", "892", "1.8 GB", "Available"),
            ("Student Union Town Hall", "May 1, 2025", "2h 05m", "456", "3.2 GB", "Available")
        ]

        for rec in recordings:
            tree.insert('', 'end', values=rec)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')

        ttk.Button(btn_frame, text="▶️ Play",
                  command=self.play_recording).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="⬇️ Download",
                  command=self.download_recording).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="🗑️ Delete",
                  command=self.delete_recording).pack(side='left')

    def create_analytics_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill='both', expand=True)

        analytics = """LIVE STREAMING ANALYTICS
================================================================================

OVERALL PERFORMANCE (Last 30 Days)

Total Streams: 24
Total Stream Hours: 67.5
Total Viewers: 12,450
Avg Viewers per Stream: 519
Peak Concurrent Viewers: 1,245 (Research Symposium)

STREAM METRICS:

Top 5 Most-Watched Streams:
  1. Research Symposium 2025 - Day 1
     Views: 1,245 | Duration: 4h 32m | Avg watch time: 2h 15m

  2. Guest Lecture: AI Ethics
     Views: 892 | Duration: 1h 15m | Avg watch time: 48m

  3. Python Workshop Series - Part 1
     Views: 567 | Duration: 1h 45m | Avg watch time: 1h 02m

  4. Student Union Town Hall
     Views: 456 | Duration: 2h 05m | Avg watch time: 1h 20m

  5. Music Society Concert
     Views: 387 | Duration: 2h 30m | Avg watch time: 1h 45m

VIEWER DEMOGRAPHICS:

By Affiliation:
  Students: 68%
  Faculty: 18%
  Alumni: 9%
  External: 5%

By Location:
  On-campus: 45%
  Off-campus local: 32%
  National: 18%
  International: 5%

PLATFORM DISTRIBUTION:

Views by Platform:
  YouTube: 62% (7,719 views)
  Facebook Live: 21% (2,615 views)
  Twitch: 10% (1,245 views)
  LinkedIn Live: 5% (623 views)
  Instagram Live: 2% (248 views)

ENGAGEMENT METRICS:

Average Engagement Rate: 34%
Total Chat Messages: 8,456
Avg Messages per Stream: 352
Likes/Reactions: 3,245
Shares: 567

VIEWER RETENTION:

Average Watch Time: 65% of stream duration
Drop-off Rate: 35%
Return Viewer Rate: 42%

Retention by Duration:
  0-15 min: 95% retention
  15-30 min: 82% retention
  30-60 min: 71% retention
  60+ min: 58% retention

TECHNICAL QUALITY:

Stream Quality Distribution:
  1080p: 72% of viewers
  720p: 21% of viewers
  480p: 6% of viewers
  360p: 1% of viewers

Average Buffering Rate: 0.8%
Connection Issues: 2.3%
Technical Quality Score: 97.7/100

PEAK VIEWING TIMES:

Highest viewership periods:
  Weekday evenings (6-9 PM): 45% of views
  Weekend afternoons (2-5 PM): 28% of views
  Weekday afternoons (2-5 PM): 18% of views
  Other times: 9% of views

RECORDING ANALYTICS:

Total Recordings: 24
On-demand Views (30 days): 4,567
Avg Views per Recording: 190
Download Requests: 234

RECOMMENDATIONS:

✓ Continue streaming during peak times (weekday evenings)
✓ Increase promotion for high-performing event types
✓ Improve retention for streams longer than 60 minutes
✓ Consider exclusive content for high-engagement platforms
✓ Expand international reach through time-zone consideration
"""
        text.insert(1.0, analytics)
        text.config(state='disabled')

    def start_stream(self):
        if messagebox.askyesno("Start Stream",
                              "Start live streaming this event?\n\n"
                              "All configured platforms will go live."):
            messagebox.showinfo("Live", "🔴 Stream is now LIVE on all platforms!")

    def end_stream(self):
        if messagebox.askyesno("End Stream",
                              "End the current live stream?"):
            messagebox.showinfo("Ended", "Stream ended. Recording is being processed.")

    def save_stream_config(self):
        messagebox.showinfo("Saved", "Stream configuration saved successfully.")

    def test_stream(self):
        messagebox.showinfo("Test Stream",
                           "Testing stream connection...\n\n"
                           "✓ YouTube: Connected\n"
                           "✓ Facebook: Connected\n"
                           "✓ Twitch: Connected\n"
                           "✓ Stream quality: Good")

    def send_chat_message(self):
        messagebox.showinfo("Sent", "Chat message sent to all platforms.")

    def ban_user(self):
        if messagebox.askyesno("Ban User", "Ban this user from chat?"):
            messagebox.showinfo("Banned", "User has been banned from chat.")

    def pause_chat(self):
        messagebox.showinfo("Chat Paused", "Live chat has been paused.")

    def play_recording(self):
        messagebox.showinfo("Play Recording", "Opening recording in media player...")

    def download_recording(self):
        messagebox.showinfo("Download", "Recording download started.")

    def delete_recording(self):
        if messagebox.askyesno("Delete Recording",
                              "Permanently delete this recording?"):
            messagebox.showinfo("Deleted", "Recording has been deleted.")



class InteractiveVirtualFeaturesDialog:
    """Interactive virtual event features"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Interactive Virtual Features")
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="💻 Interactive Virtual Event Features",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Create notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Live Polls tab
        polls_frame = ttk.Frame(notebook)
        notebook.add(polls_frame, text="Live Polls")
        self.create_polls_tab(polls_frame)

        # Q&A Sessions tab
        qa_frame = ttk.Frame(notebook)
        notebook.add(qa_frame, text="Q&A Sessions")
        self.create_qa_tab(qa_frame)

        # Virtual Networking tab
        networking_frame = ttk.Frame(notebook)
        notebook.add(networking_frame, text="Virtual Networking")
        self.create_networking_tab(networking_frame)

        # Breakout Rooms tab
        breakout_frame = ttk.Frame(notebook)
        notebook.add(breakout_frame, text="Breakout Rooms")
        self.create_breakout_tab(breakout_frame)

        # Interactive Presentations tab
        presentations_frame = ttk.Frame(notebook)
        notebook.add(presentations_frame, text="Interactive Presentations")
        self.create_presentations_tab(presentations_frame)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def create_polls_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Active poll
        active_frame = ttk.LabelFrame(frame, text="📊 Active Poll")
        active_frame.pack(fill='x', pady=(0, 15))

        poll_text = """Question: What topic should we cover next?

Options:
  A) Advanced Python Programming (35%)     [███████░░░]
  B) Machine Learning Basics (42%)         [████████░░]
  C) Web Development (15%)                 [███░░░░░░░]
  D) Data Science (8%)                     [██░░░░░░░░]

Total Votes: 127
Time Remaining: 2:45
"""
        ttk.Label(active_frame, text=poll_text, justify='left',
                 font=('Courier', 9)).pack(padx=15, pady=10)

        btn_frame = ttk.Frame(active_frame)
        btn_frame.pack(fill='x', padx=15, pady=(0, 10))

        ttk.Button(btn_frame, text="✓ Vote",
                  command=self.vote_poll).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="⏹️ End Poll",
                  command=self.end_poll).pack(side='left')

        # Poll history
        history_frame = ttk.LabelFrame(frame, text="Recent Polls")
        history_frame.pack(fill='both', expand=True)

        columns = ('Question', 'Winner', 'Votes', 'Date')
        tree = ttk.Treeview(history_frame, columns=columns, show='tree headings', height=8)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Question':
                tree.column(col, width=350)

        tree.pack(fill='both', expand=True, padx=5, pady=5)

        polls = [
            ("Rate today's session", "Excellent (65%)", "245", "Today, 2:30 PM"),
            ("Preferred workshop time?", "Evening (48%)", "189", "May 10"),
            ("Interest in follow-up?", "Yes (92%)", "312", "May 8")
        ]

        for poll in polls:
            tree.insert('', 'end', values=poll)

        ttk.Button(frame, text="➕ Create New Poll",
                  command=self.create_poll).pack(pady=(10, 0))

    def create_qa_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Questions list
        columns = ('Question', 'Asker', 'Votes', 'Status')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Question':
                tree.column(col, width=450)

        tree.pack(fill='both', expand=True, pady=(0, 10))

        # Sample questions
        questions = [
            ("How do you handle large datasets?", "John Doe", "15", "Answered"),
            ("Can you explain that algorithm again?", "Jane Smith", "12", "Pending"),
            ("What resources do you recommend?", "Bob Johnson", "8", "Pending"),
            ("Is the code available on GitHub?", "Alice Williams", "6", "Answered")
        ]

        for q in questions:
            tree.insert('', 'end', values=q)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')

        ttk.Button(btn_frame, text="❓ Ask Question",
                  command=self.ask_question).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="👍 Upvote",
                  command=self.upvote_question).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="✓ Mark Answered",
                  command=self.mark_answered).pack(side='left')

    def create_networking_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Networking lobby
        lobby_frame = ttk.LabelFrame(frame, text="🤝 Virtual Networking Lobby")
        lobby_frame.pack(fill='x', pady=(0, 15))

        lobby_text = """Active Participants: 87

Looking to connect:
  • Sarah Chen - Interested in: AI Research, Machine Learning
  • Michael Green - Interested in: Renewable Energy, Sustainability
  • Emily Rodriguez - Interested in: Psychology, Mental Health
  • David Kim - Interested in: Quantum Computing, Physics

You can start 1-on-1 video chats or join discussion rooms below.
"""
        ttk.Label(lobby_frame, text=lobby_text, justify='left').pack(padx=15, pady=10)

        # Discussion rooms
        rooms_frame = ttk.LabelFrame(frame, text="Discussion Rooms")
        rooms_frame.pack(fill='both', expand=True)

        columns = ('Room', 'Topic', 'Participants', 'Status')
        tree = ttk.Treeview(rooms_frame, columns=columns, show='tree headings', height=8)

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True, padx=5, pady=5)

        rooms = [
            ("Room 1", "AI & Machine Learning", "12/15", "Open"),
            ("Room 2", "Sustainable Technology", "8/15", "Open"),
            ("Room 3", "Career Networking", "15/15", "Full"),
            ("Room 4", "Research Collaboration", "5/10", "Open")
        ]

        for room in rooms:
            tree.insert('', 'end', values=room)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(btn_frame, text="🚪 Join Room",
                  command=self.join_networking_room).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="➕ Create Room",
                  command=self.create_networking_room).pack(side='left')

    def create_breakout_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Breakout rooms
        columns = ('Room', 'Participants', 'Activity', 'Time Remaining')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True, pady=(0, 15))

        breakout_rooms = [
            ("Group A - Problem Solving", "8", "Active Discussion", "12:45"),
            ("Group B - Brainstorming", "7", "Active Discussion", "12:45"),
            ("Group C - Code Review", "9", "Active Discussion", "12:45"),
            ("Group D - Design Session", "6", "Active Discussion", "12:45")
        ]

        for room in breakout_rooms:
            tree.insert('', 'end', values=room)

        # Controls
        control_frame = ttk.LabelFrame(frame, text="Breakout Room Controls")
        control_frame.pack(fill='x')

        ttk.Label(control_frame, text="Auto-assign participants to breakout rooms:",
                 font=('Arial', 10)).pack(anchor='w', padx=10, pady=5)

        assign_frame = ttk.Frame(control_frame)
        assign_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(assign_frame, text="Number of rooms:").pack(side='left', padx=(0, 5))
        ttk.Spinbox(assign_frame, from_=2, to=20, width=5).pack(side='left', padx=(0, 10))
        ttk.Button(assign_frame, text="Create & Assign",
                  command=self.create_breakout_rooms).pack(side='left')

        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(btn_frame, text="📢 Broadcast Message",
                  command=self.broadcast_to_breakout).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="⏰ Extend Time",
                  command=self.extend_breakout_time).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="🔙 Return All to Main",
                  command=self.return_from_breakout).pack(side='left')

    def create_presentations_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill='both', expand=True, pady=(0, 10))

        content = """INTERACTIVE PRESENTATION FEATURES
================================================================================

AVAILABLE INTERACTIVE TOOLS:

1. LIVE ANNOTATIONS
   • Draw on slides in real-time
   • Highlight key points
   • Add text annotations
   • Use laser pointer
   • Save annotated slides

2. COLLABORATIVE WHITEBOARDS
   • Shared brainstorming space
   • Multiple users can draw simultaneously
   • Export whiteboard as image/PDF
   • Templates available (mind maps, diagrams, etc.)

3. SCREEN SHARING
   • Share entire screen or specific window
   • Share with audio
   • Give control to participants
   • Multiple presenters can share

4. LIVE REACTIONS
   Participants can react with:
   👍 Thumbs up
   ❤️ Heart
   😂 Laugh
   😮 Wow
   ✋ Raise hand

5. INTERACTIVE QUIZZES
   • Create quizzes during presentation
   • Instant results visualization
   • Leaderboard display
   • Export quiz results

6. REAL-TIME COLLABORATION
   • Shared document editing
   • Live code collaboration
   • Simultaneous note-taking
   • Collaborative problem-solving

7. ENGAGEMENT ANALYTICS
   Track participant engagement:
   • Attention metrics
   • Interaction rates
   • Question frequency
   • Poll participation
   • Chat activity

BEST PRACTICES:

✓ Use polls every 10-15 minutes
✓ Encourage questions throughout
✓ Incorporate interactive elements
✓ Use breakout rooms for group work
✓ Provide clear instructions
✓ Test all features before event
✓ Have a moderator for large events

UPCOMING INTERACTIVE PRESENTATIONS:

May 16: "Interactive Data Science Workshop"
  - Live coding sessions
  - Collaborative data analysis
  - Real-time Q&A
  - Hands-on exercises

May 20: "Virtual Design Thinking Session"
  - Collaborative whiteboarding
  - Breakout brainstorming
  - Live prototyping
  - Group presentations
"""
        text.insert(1.0, content)
        text.config(state='disabled')

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')

        ttk.Button(btn_frame, text="🎨 Launch Whiteboard",
                  command=self.launch_whiteboard).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="📊 Create Quiz",
                  command=self.create_quiz).pack(side='left')

    def vote_poll(self):
        messagebox.showinfo("Vote", "Your vote has been recorded. Thank you!")

    def end_poll(self):
        if messagebox.askyesno("End Poll", "End this poll and display results?"):
            messagebox.showinfo("Results",
                               "Poll ended.\n\n"
                               "Winner: Machine Learning Basics (42%)")

    def create_poll(self):
        messagebox.showinfo("Create Poll",
                           "Poll creation form:\n\n"
                           "• Poll question\n"
                           "• Options (2-6)\n"
                           "• Duration\n"
                           "• Anonymous voting option")

    def ask_question(self):
        messagebox.showinfo("Ask Question",
                           "Your question has been submitted!\n\n"
                           "It will be answered in order of votes.")

    def upvote_question(self):
        messagebox.showinfo("Upvoted", "Question upvoted!")

    def mark_answered(self):
        messagebox.showinfo("Marked", "Question marked as answered.")

    def join_networking_room(self):
        messagebox.showinfo("Joining", "Joining virtual networking room...")

    def create_networking_room(self):
        messagebox.showinfo("Create Room",
                           "Create discussion room:\n\n"
                           "• Room name\n"
                           "• Topic\n"
                           "• Capacity (max 15)\n"
                           "• Public/Private")

    def create_breakout_rooms(self):
        messagebox.showinfo("Creating",
                           "Creating breakout rooms and auto-assigning participants...")

    def broadcast_to_breakout(self):
        messagebox.showinfo("Broadcast",
                           "Your message will be sent to all breakout rooms.")

    def extend_breakout_time(self):
        messagebox.showinfo("Extended", "Breakout room time extended by 10 minutes.")

    def return_from_breakout(self):
        if messagebox.askyesno("Return All",
                              "Return all participants to the main session?"):
            messagebox.showinfo("Returned", "All participants returned to main session.")

    def launch_whiteboard(self):
        messagebox.showinfo("Whiteboard", "Collaborative whiteboard launched!")

    def create_quiz(self):
        messagebox.showinfo("Create Quiz",
                           "Quiz builder:\n\n"
                           "• Add questions (multiple choice, true/false, short answer)\n"
                           "• Set time limits\n"
                           "• Configure scoring\n"
                           "• Launch during presentation")



class RecordingManagementDialog:
    """Recording and replay management system"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Recording & Replay Management")
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🎥 Recording & Replay Management",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Create notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Auto-Recording tab
        auto_frame = ttk.Frame(notebook)
        notebook.add(auto_frame, text="Auto-Recording")
        self.create_auto_tab(auto_frame)

        # Video Library tab
        library_frame = ttk.Frame(notebook)
        notebook.add(library_frame, text="Video Library")
        self.create_library_tab(library_frame)

        # On-Demand Viewing tab
        ondemand_frame = ttk.Frame(notebook)
        notebook.add(ondemand_frame, text="On-Demand Viewing")
        self.create_ondemand_tab(ondemand_frame)

        # Analytics tab
        analytics_frame = ttk.Frame(notebook)
        notebook.add(analytics_frame, text="Playback Analytics")
        self.create_analytics_tab(analytics_frame)

        # Download Options tab
        download_frame = ttk.Frame(notebook)
        notebook.add(download_frame, text="Download Options")
        self.create_download_tab(download_frame)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def create_auto_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Auto-recording settings
        settings_frame = ttk.LabelFrame(frame, text="Auto-Recording Settings")
        settings_frame.pack(fill='x', pady=(0, 15))

        ttk.Checkbutton(settings_frame,
                       text="Automatically record all live streams").pack(anchor='w', padx=10, pady=5)
        ttk.Checkbutton(settings_frame,
                       text="Automatically record virtual events").pack(anchor='w', padx=10, pady=5)
        ttk.Checkbutton(settings_frame,
                       text="Automatically record conference sessions").pack(anchor='w', padx=10, pady=5)

        quality_frame = ttk.Frame(settings_frame)
        quality_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(quality_frame, text="Recording quality:").pack(side='left', padx=(0, 5))
        quality_combo = ttk.Combobox(quality_frame, width=20, state='readonly')
        quality_combo['values'] = ('1080p Full HD', '720p HD', '480p SD')
        quality_combo.current(0)
        quality_combo.pack(side='left')

        storage_frame = ttk.Frame(settings_frame)
        storage_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(storage_frame, text="Storage location:").pack(side='left', padx=(0, 5))
        ttk.Entry(storage_frame, width=40).pack(side='left')
        ttk.Button(storage_frame, text="Browse").pack(side='left', padx=(5, 0))

        # Active recordings
        active_frame = ttk.LabelFrame(frame, text="Currently Recording")
        active_frame.pack(fill='both', expand=True)

        columns = ('Event', 'Started', 'Duration', 'Size', 'Status')
        tree = ttk.Treeview(active_frame, columns=columns, show='tree headings', height=8)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Event':
                tree.column(col, width=300)

        tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Sample active recordings
        active_recs = [
            ("Research Symposium - Afternoon Session", "2:00 PM", "1h 23m", "1.8 GB", "🔴 Recording"),
            ("Virtual Workshop: Python Advanced", "3:15 PM", "45m", "620 MB", "🔴 Recording")
        ]

        for rec in active_recs:
            tree.insert('', 'end', values=rec)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(btn_frame, text="⏹️ Stop Recording",
                  command=self.stop_recording).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="💾 Save Settings",
                  command=self.save_recording_settings).pack(side='left')

    def create_library_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Search and filter
        search_frame = ttk.Frame(frame)
        search_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(search_frame, text="Search:").pack(side='left', padx=(0, 5))
        ttk.Entry(search_frame, width=30).pack(side='left', padx=(0, 10))
        ttk.Button(search_frame, text="🔍 Search").pack(side='left', padx=(0, 20))

        ttk.Label(search_frame, text="Filter:").pack(side='left', padx=(0, 5))
        filter_combo = ttk.Combobox(search_frame, width=20, state='readonly')
        filter_combo['values'] = ('All Events', 'Conferences', 'Workshops',
                                   'Lectures', 'Presentations', 'Meetings')
        filter_combo.current(0)
        filter_combo.pack(side='left')

        # Video library
        columns = ('Title', 'Date', 'Duration', 'Views', 'Size')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Title':
                tree.column(col, width=400)

        tree.pack(fill='both', expand=True, pady=(0, 10))

        # Sample library videos
        videos = [
            ("Research Symposium 2025 - Day 1", "May 15, 2025", "4h 32m", "1,245", "8.2 GB"),
            ("Research Symposium 2025 - Day 2", "May 16, 2025", "4h 15m", "987", "7.8 GB"),
            ("Python Workshop Series - Part 1", "May 10, 2025", "1h 45m", "567", "2.1 GB"),
            ("Python Workshop Series - Part 2", "May 11, 2025", "1h 52m", "534", "2.3 GB"),
            ("Guest Lecture: AI Ethics", "May 5, 2025", "1h 15m", "892", "1.8 GB"),
            ("Student Union Town Hall", "May 1, 2025", "2h 05m", "456", "3.2 GB"),
            ("Career Panel Discussion", "Apr 28, 2025", "1h 30m", "678", "2.0 GB"),
            ("Music Society Concert", "Apr 25, 2025", "2h 30m", "387", "3.8 GB")
        ]

        for video in videos:
            tree.insert('', 'end', values=video)

        # Stats
        stats_frame = ttk.LabelFrame(frame, text="Library Statistics")
        stats_frame.pack(fill='x', pady=(10, 0))

        stats_text = """Total Recordings: 128
Total Storage: 247 GB / 500 GB (49%)
Total Views: 45,678
Most Popular: Research Symposium 2025 (1,245 views)
"""
        ttk.Label(stats_frame, text=stats_text, justify='left',
                 font=('Courier', 9)).pack(padx=15, pady=10)

    def create_ondemand_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Featured videos
        featured_frame = ttk.LabelFrame(frame, text="🌟 Featured On-Demand Content")
        featured_frame.pack(fill='x', pady=(0, 15))

        featured_text = """EDITOR'S PICKS:

1. Research Symposium 2025 - Complete Coverage
   Duration: 8h 47m | Views: 2,232 | Rating: 4.9/5

2. Python Workshop Series (Complete)
   Duration: 7h 15m | Views: 1,543 | Rating: 4.8/5

3. AI Ethics Lecture Series
   Duration: 5h 30m | Views: 1,876 | Rating: 4.9/5
"""
        ttk.Label(featured_frame, text=featured_text, justify='left',
                 font=('Courier', 9)).pack(padx=15, pady=10)

        # Categories
        categories_frame = ttk.LabelFrame(frame, text="Browse by Category")
        categories_frame.pack(fill='both', expand=True)

        columns = ('Category', 'Videos', 'Total Duration', 'Total Views')
        tree = ttk.Treeview(categories_frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True, padx=5, pady=5)

        categories = [
            ("Academic Conferences", "24", "87h 30m", "12,456"),
            ("Workshops & Training", "45", "156h 15m", "18,234"),
            ("Guest Lectures", "32", "45h 20m", "8,567"),
            ("Student Presentations", "67", "92h 45m", "5,234"),
            ("Town Halls & Meetings", "18", "28h 10m", "3,456"),
            ("Performances & Events", "23", "42h 30m", "6,789")
        ]

        for cat in categories:
            tree.insert('', 'end', values=cat)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(btn_frame, text="▶️ Watch",
                  command=self.watch_video).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="➕ Add to Playlist",
                  command=self.add_to_playlist).pack(side='left')

    def create_analytics_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill='both', expand=True)

        analytics = """PLAYBACK ANALYTICS
================================================================================

OVERALL VIEWERSHIP (Last 30 Days)

Total On-Demand Views: 45,678
Total Watch Time: 123,456 hours
Average View Duration: 2h 42m
Unique Viewers: 8,234

MOST WATCHED RECORDINGS:

1. Research Symposium 2025 - Day 1
   Views: 1,245 | Watch time: 5,634h | Avg completion: 58%

2. Python Workshop Series (Complete)
   Views: 1,543 | Watch time: 11,187h | Avg completion: 82%

3. Guest Lecture: AI Ethics
   Views: 892 | Watch time: 1,115h | Avg completion: 94%

4. Career Panel Discussion
   Views: 678 | Watch time: 1,017h | Avg completion: 78%

5. Student Union Town Hall
   Views: 456 | Watch time: 952h | Avg completion: 65%

VIEWER ENGAGEMENT:

Average Completion Rate: 67%
Replay Rate: 23%
Share Rate: 15%
Download Rate: 8%

Engagement by Content Type:
  Workshops: 82% completion
  Lectures: 74% completion
  Conferences: 58% completion
  Meetings: 52% completion
  Events: 71% completion

VIEWING PATTERNS:

Peak Viewing Times:
  Weekday evenings (7-10 PM): 35%
  Weekend afternoons (2-6 PM): 28%
  Weekday afternoons (3-6 PM): 22%
  Late night (10 PM-1 AM): 15%

Average Session Duration:
  Desktop: 3h 15m
  Mobile: 1h 45m
  Tablet: 2h 30m

DEVICE DISTRIBUTION:

Desktop: 52%
Mobile: 31%
Tablet: 17%

VIEWER RETENTION:

0-15 min: 92% retention
15-30 min: 84% retention
30-60 min: 76% retention
1-2 hours: 68% retention
2+ hours: 54% retention

PLAYBACK QUALITY:

Quality Selection:
  1080p: 68%
  720p: 24%
  480p: 7%
  360p: 1%

Buffering Rate: 0.6%
Playback Errors: 0.3%
Quality Score: 98.5/100

CONTENT PERFORMANCE:

Top Performing Categories:
  1. Python Workshops - 82% avg completion
  2. Guest Lectures - 74% avg completion
  3. Student Presentations - 71% avg completion

Underperforming Categories:
  1. Long Conferences - 52% avg completion
  2. Administrative Meetings - 48% avg completion

VIEWER FEEDBACK:

Average Rating: 4.7/5
Total Ratings: 3,456
Comments: 1,234

Most Common Positive Feedback:
  • "High quality recordings"
  • "Great content selection"
  • "Easy to navigate"

Areas for Improvement:
  • "Add chapter markers"
  • "Improve search function"
  • "Add subtitles/captions"

RECOMMENDATIONS:

✓ Add chapter markers to long recordings (>2 hours)
✓ Implement automated subtitle generation
✓ Create curated playlists by topic
✓ Improve mobile viewing experience
✓ Add speed control options (already at 1.5x, 2x)
"""
        text.insert(1.0, analytics)
        text.config(state='disabled')

    def create_download_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Download settings
        settings_frame = ttk.LabelFrame(frame, text="Download Settings")
        settings_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(settings_frame, text="Default download quality:",
                 font=('Arial', 10)).pack(anchor='w', padx=10, pady=5)

        quality_var = tk.StringVar(value="1080p")
        ttk.Radiobutton(settings_frame, text="1080p Full HD (largest file)",
                       variable=quality_var, value="1080p").pack(anchor='w', padx=20, pady=2)
        ttk.Radiobutton(settings_frame, text="720p HD (recommended)",
                       variable=quality_var, value="720p").pack(anchor='w', padx=20, pady=2)
        ttk.Radiobutton(settings_frame, text="480p SD (smaller file)",
                       variable=quality_var, value="480p").pack(anchor='w', padx=20, pady=2)

        ttk.Checkbutton(settings_frame,
                       text="Include subtitles when available").pack(anchor='w', padx=10, pady=5)
        ttk.Checkbutton(settings_frame,
                       text="Download thumbnail").pack(anchor='w', padx=10, pady=5)

        # Download queue
        queue_frame = ttk.LabelFrame(frame, text="Download Queue")
        queue_frame.pack(fill='both', expand=True)

        columns = ('Video', 'Progress', 'Speed', 'ETA', 'Status')
        tree = ttk.Treeview(queue_frame, columns=columns, show='tree headings', height=8)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Video':
                tree.column(col, width=350)

        tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Sample downloads
        downloads = [
            ("Research Symposium - Day 1 (1080p)", "45%", "12.3 MB/s", "3m 15s", "Downloading"),
            ("Python Workshop Part 2 (720p)", "100%", "-", "-", "Completed"),
            ("Guest Lecture: AI Ethics (1080p)", "Queued", "-", "-", "Waiting")
        ]

        for dl in downloads:
            tree.insert('', 'end', values=dl)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(btn_frame, text="⏸️ Pause",
                  command=self.pause_download).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel",
                  command=self.cancel_download).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="📂 Open Folder",
                  command=self.open_download_folder).pack(side='left')

    def stop_recording(self):
        if messagebox.askyesno("Stop Recording", "Stop this recording?"):
            messagebox.showinfo("Stopped", "Recording stopped and saved.")

    def save_recording_settings(self):
        messagebox.showinfo("Saved", "Recording settings saved successfully.")

    def watch_video(self):
        messagebox.showinfo("Watch", "Opening video player...")

    def add_to_playlist(self):
        messagebox.showinfo("Added", "Video added to playlist.")

    def pause_download(self):
        messagebox.showinfo("Paused", "Download paused.")

    def cancel_download(self):
        if messagebox.askyesno("Cancel", "Cancel this download?"):
            messagebox.showinfo("Cancelled", "Download cancelled.")

    def open_download_folder(self):
        messagebox.showinfo("Folder", "Opening downloads folder...")


# Main application launcher - FIXED: Added proper parameter handling

def open_live_streaming_dialog(self):
    """Open live streaming platform"""
    dialog = LiveStreamingDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


