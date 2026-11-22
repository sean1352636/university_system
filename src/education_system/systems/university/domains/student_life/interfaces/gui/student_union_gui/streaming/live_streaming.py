
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.systems.university.infrastructure.email.template_utils import render_template
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
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
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import (
    live_streams as ls,
)
from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.core import (
    su_records,
)

_L = 'gui.pastoral.student_union_gui.streaming.live_streaming'


def _stream_label(r):
    return f"{r['title']} — {r['scheduled_start']} (#{r['stream_id']})"


def _streamer(r):
    return r.get('club_name') or r.get('event_title') or r.get('created_by') or 'Student Union'


def _viewers(r):
    return str(r['peak_viewers']) if r.get('peak_viewers') is not None else '—'


def _load_choices():
    """(clubs, events) for the stream form: {label: id}."""
    clubs, events = {}, {}
    with su_records.db() as conn:
        try:
            for row in conn.execute("SELECT club_id, club_name FROM student_clubs "
                                    "WHERE LOWER(COALESCE(status, 'active')) = 'active' ORDER BY club_name"):
                clubs[f"{row[1]} (#{row[0]})"] = row[0]
        except Exception:
            pass
        try:
            for row in conn.execute(
                    "SELECT event_id, title, COALESCE(event_date, substr(start_datetime, 1, 10)) "
                    "FROM unified_events WHERE source_type IN ('union', 'student_union') "
                    "ORDER BY 3 DESC LIMIT 300"):
                events[f"{row[1]} ({row[2] or 'no date'}) #{row[0]}"] = row[0]
        except Exception:
            pass
    return clubs, events


def _ask_peak_viewers(parent):
    """Optional peak viewer count, only if the streamer actually has one."""
    if not messagebox.askyesno("Viewer count", "Do you have the peak viewer count from the "
                               "streaming platform?\n\n(Choose No to leave it unrecorded.)", parent=parent):
        return None
    return simpledialog.askinteger("Viewer count", "Peak concurrent viewers:", minvalue=0, parent=parent)


class StreamEditorDialog:
    """Create or edit a scheduled stream (SU staff)"""

    def __init__(self, parent, auth_manager, stream_id=None):
        self.auth = auth_manager
        self.stream_id = stream_id
        self.saved_id = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Stream" if stream_id else "Schedule Stream")
        self.dialog.geometry("640x560")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.form = StreamForm(self.dialog, auth_manager)
        self.form.frame.pack(fill='both', expand=True, padx=15, pady=15)
        if stream_id:
            self.form.load(stream_id)

        btns = ttk.Frame(self.dialog)
        btns.pack(fill='x', padx=15, pady=(0, 15))
        ttk.Button(btns, text="Save", command=self.save).pack(side='left', padx=(0, 10))
        ttk.Button(btns, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def save(self):
        sid = self.form.save()
        if sid:
            self.saved_id = sid
            self.dialog.destroy()


class StreamForm:
    """The stream fields, used by the editor dialog and the Stream Setup tab"""

    def __init__(self, parent, auth_manager, *, platforms_as_checks=False):
        self.auth = auth_manager
        self.stream_id = None
        self.frame = ttk.Frame(parent)
        try:
            self.clubs, self.events = _load_choices()
        except Exception:
            self.clubs, self.events = {}, {}

        f = self.frame
        r = 0
        ttk.Label(f, text=_t(f'{_L}.labels.event_title', default="Event Title:")).grid(row=r, column=0, sticky='w', pady=4)
        self.title_entry = ttk.Entry(f, width=50)
        self.title_entry.grid(row=r, column=1, sticky='ew', pady=4, padx=(10, 0)); r += 1

        ttk.Label(f, text=_t(f'{_L}.labels.stream_description', default="Stream Description:")).grid(row=r, column=0, sticky='nw', pady=4)
        self.desc_text = scrolledtext.ScrolledText(f, width=50, height=3)
        self.desc_text.grid(row=r, column=1, sticky='ew', pady=4, padx=(10, 0)); r += 1

        ttk.Label(f, text="Club:").grid(row=r, column=0, sticky='w', pady=4)
        self.club_combo = ttk.Combobox(f, width=47, state='readonly', values=('(none)',) + tuple(self.clubs))
        self.club_combo.set('(none)')
        self.club_combo.grid(row=r, column=1, sticky='w', pady=4, padx=(10, 0)); r += 1

        ttk.Label(f, text="SU event:").grid(row=r, column=0, sticky='w', pady=4)
        self.event_combo = ttk.Combobox(f, width=47, state='readonly', values=('(none)',) + tuple(self.events))
        self.event_combo.set('(none)')
        self.event_combo.grid(row=r, column=1, sticky='w', pady=4, padx=(10, 0)); r += 1

        ttk.Label(f, text="Stream / watch URL:").grid(row=r, column=0, sticky='w', pady=4)
        self.url_entry = ttk.Entry(f, width=50)
        self.url_entry.grid(row=r, column=1, sticky='ew', pady=4, padx=(10, 0)); r += 1

        ttk.Label(f, text="Start (YYYY-MM-DD HH:MM):").grid(row=r, column=0, sticky='w', pady=4)
        self.start_entry = ttk.Entry(f, width=50)
        self.start_entry.grid(row=r, column=1, sticky='ew', pady=4, padx=(10, 0)); r += 1

        ttk.Label(f, text="End (YYYY-MM-DD HH:MM):").grid(row=r, column=0, sticky='w', pady=4)
        self.end_entry = ttk.Entry(f, width=50)
        self.end_entry.grid(row=r, column=1, sticky='ew', pady=4, padx=(10, 0)); r += 1

        self.platform_vars = {}
        if platforms_as_checks:
            ttk.Label(f, text=_t(f'{_L}.labels.multi_platform_streaming', default="Multi-Platform Streaming:")).grid(row=r, column=0, sticky='nw', pady=4)
            pf = ttk.Frame(f)
            pf.grid(row=r, column=1, sticky='w', pady=4, padx=(10, 0))
            for name in ("YouTube", "Facebook Live", "Twitch", "LinkedIn Live", "Instagram Live"):
                var = tk.BooleanVar(value=False)
                ttk.Checkbutton(pf, text=name, variable=var).pack(anchor='w')
                self.platform_vars[name] = var
            self.platform_combo = None
        else:
            ttk.Label(f, text=_t(f'{_L}.labels.platform', default="Platform:")).grid(row=r, column=0, sticky='w', pady=4)
            self.platform_combo = ttk.Combobox(f, width=47, values=ls.PLATFORMS)
            self.platform_combo.grid(row=r, column=1, sticky='w', pady=4, padx=(10, 0))
        r += 1

        ttk.Label(f, text=_t(f'{_L}.labels.stream_quality', default="Stream Quality:")).grid(row=r, column=0, sticky='w', pady=4)
        self.quality_combo = ttk.Combobox(f, width=47, state='readonly', values=ls.QUALITIES)
        self.quality_combo.current(0)
        self.quality_combo.grid(row=r, column=1, sticky='w', pady=4, padx=(10, 0)); r += 1

        self.record_var = tk.BooleanVar(value=self._auto_record_default())
        self.chat_var = tk.BooleanVar(value=True)
        ttk.Label(f, text=_t(f'{_L}.labels.auto_record', default="Auto-Record:")).grid(row=r, column=0, sticky='w', pady=4)
        ttk.Checkbutton(f, text=_t(f'{_L}.buttons.automatically_record_stream', default="Automatically record stream"),
                        variable=self.record_var).grid(row=r, column=1, sticky='w', pady=4, padx=(10, 0)); r += 1
        ttk.Label(f, text=_t(f'{_L}.labels.enable_chat', default="Enable Chat:")).grid(row=r, column=0, sticky='w', pady=4)
        ttk.Checkbutton(f, text=_t(f'{_L}.buttons.enable_live_chat_during_stream', default="Enable live chat during stream"),
                        variable=self.chat_var).grid(row=r, column=1, sticky='w', pady=4, padx=(10, 0)); r += 1
        f.columnconfigure(1, weight=1)

    @staticmethod
    def _auto_record_default():
        """New streams follow the 'record all live streams' setting (Recordings & Replay)."""
        try:
            from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import (
                live_stream_interaction,
            )
            with su_records.db() as conn:
                return live_stream_interaction.get_settings(conn).get('auto_record_streams', '1') == '1'
        except Exception:
            return True

    def clear(self):
        self.stream_id = None
        for e in (self.title_entry, self.url_entry, self.start_entry, self.end_entry):
            e.delete(0, tk.END)
        self.desc_text.delete(1.0, tk.END)
        self.club_combo.set('(none)')
        self.event_combo.set('(none)')
        if self.platform_combo is not None:
            self.platform_combo.set('')
        for v in self.platform_vars.values():
            v.set(False)
        self.quality_combo.current(0)
        self.record_var.set(self._auto_record_default())
        self.chat_var.set(True)

    def load(self, stream_id):
        with su_records.db() as conn:
            r = ls.get_stream(conn, stream_id)
        self.clear()
        if not r:
            return
        self.stream_id = stream_id
        self.title_entry.insert(0, r['title'] or '')
        self.desc_text.insert(1.0, r.get('description') or '')
        self.url_entry.insert(0, r.get('stream_url') or '')
        self.start_entry.insert(0, r.get('scheduled_start') or '')
        self.end_entry.insert(0, r.get('scheduled_end') or '')
        for label, cid in self.clubs.items():
            if cid == r.get('club_id'):
                self.club_combo.set(label)
        for label, eid in self.events.items():
            if eid == r.get('event_id'):
                self.event_combo.set(label)
        platforms = [p.strip() for p in (r.get('platform') or '').split(',') if p.strip()]
        if self.platform_combo is not None:
            self.platform_combo.set(', '.join(platforms))
        for name, var in self.platform_vars.items():
            var.set(name in platforms)
        if r.get('quality') in ls.QUALITIES:
            self.quality_combo.set(r['quality'])
        self.record_var.set(bool(r.get('record_stream')))
        self.chat_var.set(bool(r.get('chat_enabled')))

    def save(self):
        if not su_records.is_staff(self.auth):
            messagebox.showwarning("Staff only", "Only Student Union staff can schedule streams.", parent=self.frame)
            return None
        if self.platform_combo is not None:
            platform = self.platform_combo.get().strip()
        else:
            platform = ', '.join(n for n, v in self.platform_vars.items() if v.get())
        data = {
            'title': self.title_entry.get(), 'description': self.desc_text.get(1.0, tk.END),
            'club_id': self.clubs.get(self.club_combo.get()),
            'event_id': self.events.get(self.event_combo.get()),
            'stream_url': self.url_entry.get(), 'scheduled_start': self.start_entry.get(),
            'scheduled_end': self.end_entry.get(), 'platform': platform,
            'quality': self.quality_combo.get(), 'record_stream': self.record_var.get(),
            'chat_enabled': self.chat_var.get(),
        }
        try:
            with su_records.db() as conn:
                sid = ls.save_stream(conn, data, actor=su_records.username(self.auth),
                                     stream_id=self.stream_id)
        except ValueError as e:
            messagebox.showwarning("Check the form", str(e), parent=self.frame)
            return None
        except Exception as e:
            messagebox.showerror("Error", f"Could not save the stream:\n{e}", parent=self.frame)
            return None
        self.stream_id = sid
        return sid


class LiveStreamingDialog:
    """Dialog for running a scheduled live stream"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self._streams = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t(f'{_L}.windows.live_streaming', default="Live Streaming"))
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_streams()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t(f'{_L}.labels.live_streaming_platform', default="📡 Live Streaming Platform"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Buttons (packed first so they stay visible on a short screen)
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side='bottom', fill='x')

        self.start_btn = ttk.Button(button_frame, text=_t(f'{_L}.buttons.start_stream', default="Start Stream"), command=self.start_stream)
        self.start_btn.pack(side='left', padx=(0, 10))
        self.stop_btn = ttk.Button(button_frame, text=_t(f'{_L}.buttons.stop_stream', default="Stop Stream"), command=self.stop_stream, state='disabled')
        self.stop_btn.pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Schedule Stream…", command=self.schedule_stream).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Manage Streams…", command=self.manage_streams).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Interactive Features…", command=self.open_interactive).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Recordings & Replay…", command=self.open_recordings).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t(f'{_L}.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

        # Stream setup
        setup_frame = ttk.LabelFrame(main_frame, text=_t(f'{_L}.labels.stream_setup', default="Stream Setup"))
        setup_frame.pack(fill='x', pady=(0, 15))

        form = ttk.Frame(setup_frame)
        form.pack(padx=15, pady=15, fill='x')

        ttk.Label(form, text=_t(f'{_L}.labels.event', default="Event:")).grid(row=0, column=0, sticky='w', pady=5)
        self.event_combo = ttk.Combobox(form, width=40, state='readonly')
        self.event_combo.grid(row=0, column=1, pady=5, sticky='ew')
        self.event_combo.bind('<<ComboboxSelected>>', lambda e: self.show_selected())

        ttk.Label(form, text=_t(f'{_L}.labels.platform', default="Platform:")).grid(row=1, column=0, sticky='w', pady=5)
        self.platform_combo = ttk.Combobox(form, width=40)
        self.platform_combo['values'] = ls.PLATFORMS
        self.platform_combo.grid(row=1, column=1, pady=5, sticky='ew')

        ttk.Label(form, text=_t(f'{_L}.labels.quality', default="Quality:")).grid(row=2, column=0, sticky='w', pady=5)
        self.quality_combo = ttk.Combobox(form, width=40, state='readonly')
        self.quality_combo['values'] = ls.QUALITIES
        self.quality_combo.grid(row=2, column=1, pady=5, sticky='ew')
        self.quality_combo.current(0)

        form.columnconfigure(1, weight=1)

        # Features
        features_frame = ttk.LabelFrame(main_frame, text=_t(f'{_L}.labels.stream_features', default="Stream Features"))
        features_frame.pack(fill='x', pady=(0, 15))

        self.chat_var = tk.BooleanVar(value=True)
        self.recording_var = tk.BooleanVar(value=True)
        self.qa_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(features_frame, text=_t(f'{_L}.buttons.enable_live_chat', default="Enable Live Chat"), variable=self.chat_var).pack(anchor='w', padx=15, pady=5)
        ttk.Checkbutton(features_frame, text=_t(f'{_L}.buttons.record_stream', default="Record Stream"), variable=self.recording_var).pack(anchor='w', padx=15, pady=5)
        ttk.Checkbutton(features_frame, text=_t(f'{_L}.buttons.q_a_session', default="Q&A Session") + " (run on the streaming platform)",
                        variable=self.qa_var, state='disabled').pack(anchor='w', padx=15, pady=5)

        # Status
        status_frame = ttk.LabelFrame(main_frame, text=_t(f'{_L}.labels.stream_status', default="Stream Status"))
        status_frame.pack(fill='both', expand=True, pady=(0, 15))

        self.status_label = ttk.Label(status_frame, text=_t(f'{_L}.labels.not_streaming', default="⚪ Not Streaming"),
                                     font=('Arial', 12, 'bold'), foreground='gray')
        self.status_label.pack(pady=15)

        self.viewers_label = ttk.Label(status_frame, text="")
        self.viewers_label.pack(pady=5)

        self.url_label = ttk.Label(status_frame, text="", foreground='blue', cursor='hand2')
        self.url_label.pack(pady=5)
        self.url_label.bind('<Button-1>', lambda e: self._open_url())

    def load_streams(self, keep=None):
        try:
            with su_records.db() as conn:
                rows = ls.list_streams(conn, status=('scheduled', 'live'))
        except Exception as e:
            messagebox.showerror("Error", f"Could not load streams:\n{e}", parent=self.dialog)
            rows = []
        self._streams = {_stream_label(r): r for r in rows}
        self.event_combo['values'] = list(self._streams)
        if not rows:
            self.event_combo.set('')
            self.status_label.config(text="No streams are scheduled. Use 'Schedule Stream…' to add one.",
                                     foreground='gray')
            self.viewers_label.config(text="")
            self.url_label.config(text="")
            self.start_btn.config(state='disabled')
            self.stop_btn.config(state='disabled')
            return
        pick = next((k for k, r in self._streams.items() if keep and r['stream_id'] == keep), None)
        pick = pick or next((k for k, r in self._streams.items() if r['status'] == 'live'), None)
        self.event_combo.set(pick or list(self._streams)[0])
        self.show_selected()

    def _current(self):
        return self._streams.get(self.event_combo.get())

    def show_selected(self):
        r = self._current()
        if not r:
            return
        self.platform_combo.set(r.get('platform') or '')
        if r.get('quality') in ls.QUALITIES:
            self.quality_combo.set(r['quality'])
        self.chat_var.set(bool(r.get('chat_enabled')))
        self.recording_var.set(bool(r.get('record_stream')))
        live = r['status'] == 'live'
        if live:
            self.status_label.config(text=f"🔴 LIVE since {r.get('actual_start')} "
                                     f"({ls.duration_text(r.get('actual_start'), None)})", foreground='red')
        else:
            self.status_label.config(text=f"⚪ Scheduled for {r['scheduled_start']}", foreground='gray')
        self.viewers_label.config(text=f"Viewers: {r['peak_viewers']} (recorded)" if r.get('peak_viewers') is not None
                                  else "Viewers: not recorded (check the streaming platform)")
        self.url_label.config(text=r.get('stream_url') or "No stream URL set")
        self.start_btn.config(state='disabled' if live else 'normal')
        self.stop_btn.config(state='normal' if live else 'disabled')

    def _open_url(self):
        r = self._current()
        if r and r.get('stream_url'):
            su_records.open_target(r['stream_url'])

    def _staff(self):
        if su_records.is_staff(self.auth):
            return True
        messagebox.showwarning("Staff only", "Only Student Union staff can run streams.", parent=self.dialog)
        return False

    def start_stream(self):
        r = self._current()
        if not r:
            messagebox.showwarning(_t(f'{_L}.dialogs.warning', default="Warning"), _t(f'{_L}.dialogs.please_select_an_event', default="Please select an event."), parent=self.dialog)
            return
        if not self._staff():
            return
        try:
            with su_records.db() as conn:
                # Keep any platform/quality/feature changes made on this screen.
                ls.save_stream(conn, {**r, 'platform': self.platform_combo.get(),
                                      'quality': self.quality_combo.get(),
                                      'chat_enabled': self.chat_var.get(),
                                      'record_stream': self.recording_var.get()},
                               actor=r.get('created_by'), stream_id=r['stream_id'])
                ls.set_status(conn, r['stream_id'], 'live')
        except ValueError as e:
            messagebox.showwarning("Warning", str(e), parent=self.dialog)
            return
        except Exception as e:
            messagebox.showerror("Error", f"Could not start the stream:\n{e}", parent=self.dialog)
            return
        msg = "The stream is marked live."
        msg += (f"\n\nWatch link: {r['stream_url']}" if r.get('stream_url')
                else "\n\nNo watch link is set — add one under Manage Streams so viewers can find it.")
        messagebox.showinfo(_t(f'{_L}.dialogs.stream_started', default="Stream Started"), msg, parent=self.dialog)
        self.load_streams(keep=r['stream_id'])

    def stop_stream(self):
        r = self._current()
        if not r or not self._staff():
            return
        if not messagebox.askyesno(_t(f'{_L}.dialogs.confirm', default="Confirm"), _t(f'{_L}.dialogs.stop_streaming', default="Stop streaming?"), parent=self.dialog):
            return
        peak = _ask_peak_viewers(self.dialog)
        try:
            with su_records.db() as conn:
                ls.set_status(conn, r['stream_id'], 'ended', peak_viewers=peak)
        except Exception as e:
            messagebox.showerror("Error", f"Could not end the stream:\n{e}", parent=self.dialog)
            return
        messagebox.showinfo(_t(f'{_L}.dialogs.stream_ended', default="Stream Ended"),
                            "Stream ended." + ("\n\nLink the recording under Manage Streams → Recordings "
                                               "once the platform has it." if r.get('record_stream') else ""),
                            parent=self.dialog)
        self.load_streams()

    def schedule_stream(self):
        if not self._staff():
            return
        dialog = StreamEditorDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
        self.load_streams(keep=dialog.saved_id)

    def manage_streams(self):
        dialog = ManageLiveStreamingDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
        self.load_streams()

    def open_interactive(self):
        from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.streaming.stream_interaction import (
            InteractiveVirtualFeaturesDialog,
        )
        dialog = InteractiveVirtualFeaturesDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def open_recordings(self):
        from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.streaming.stream_recordings import (
            RecordingManagementDialog,
        )
        dialog = RecordingManagementDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
        self.load_streams()



class ManageLiveStreamingDialog:
    """Live streaming platform for events"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.staff = su_records.is_staff(auth_manager)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t(f'{_L}.windows.live_streaming_platform', default="Live Streaming Platform"))
        self.dialog.geometry("1200x800")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.refresh_all()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t(f'{_L}.labels.live_streaming_platform', default="📡 Live Streaming Platform"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        ttk.Button(main_frame, text=_t(f'{_L}.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='bottom')

        # Create notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))
        self.notebook = notebook

        streams_frame = ttk.Frame(notebook)
        notebook.add(streams_frame, text=_t(f'{_L}.tabs.active_streams', default="Active Streams"))
        self.create_streams_tab(streams_frame)

        setup_frame = ttk.Frame(notebook)
        notebook.add(setup_frame, text=_t(f'{_L}.tabs.stream_setup', default="Stream Setup"))
        self.create_setup_tab(setup_frame)

        chat_frame = ttk.Frame(notebook)
        notebook.add(chat_frame, text=_t(f'{_L}.tabs.chat_interaction', default="Chat & Interaction"))
        self.create_chat_tab(chat_frame)

        recordings_frame = ttk.Frame(notebook)
        notebook.add(recordings_frame, text=_t(f'{_L}.tabs.recordings', default="Recordings"))
        self.create_recordings_tab(recordings_frame)

        analytics_frame = ttk.Frame(notebook)
        notebook.add(analytics_frame, text=_t(f'{_L}.tabs.viewer_analytics', default="Viewer Analytics"))
        self.create_analytics_tab(analytics_frame)

    def refresh_all(self):
        self.load_streams_tab()
        self.load_setup_choices()
        self.load_chat_streams()
        self.load_recordings()
        self.load_analytics()

    def _staff_only(self):
        if self.staff:
            return True
        messagebox.showwarning("Staff only", "Only Student Union staff can do this.", parent=self.dialog)
        return False

    # ------------------------------------------------------------ streams tab
    def create_streams_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x')

        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.start_stream_variant_2', default="🔴 Start Stream"),
                  command=self.start_stream).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.end_stream', default="⏹️ End Stream"),
                  command=self.end_stream).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="✏️ Edit", command=self.edit_stream).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="✖ Cancel Stream", command=self.cancel_stream).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="🔗 Open Link", command=self.open_stream_link).pack(side='left')

        live_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.live_now', default="🔴 Live Now"))
        live_frame.pack(fill='x', pady=(0, 15))

        columns = ('Event', 'Streamer', 'Viewers', 'Duration', 'Platform')
        self.live_tree = ttk.Treeview(live_frame, columns=columns, show='headings', height=5)
        for col in columns:
            self.live_tree.heading(col, text=col)
            if col == 'Event':
                self.live_tree.column(col, width=280)
        self.live_tree.pack(fill='both', expand=True, padx=5, pady=5)

        upcoming_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.upcoming_streams', default="📅 Upcoming Streams"))
        upcoming_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns2 = ('Event', 'Scheduled', 'Streamer', 'Platforms')
        self.upcoming_tree = ttk.Treeview(upcoming_frame, columns=columns2, show='headings', height=6)
        for col in columns2:
            self.upcoming_tree.heading(col, text=col)
            if col == 'Event':
                self.upcoming_tree.column(col, width=300)
        self.upcoming_tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Selecting in one list clears the other so a button acts on one stream.
        self.live_tree.bind('<<TreeviewSelect>>', lambda e: self._exclusive(self.live_tree, self.upcoming_tree))
        self.upcoming_tree.bind('<<TreeviewSelect>>', lambda e: self._exclusive(self.upcoming_tree, self.live_tree))

    def _exclusive(self, chosen, other):
        if chosen.selection() and other.selection():
            other.selection_remove(other.selection())

    def load_streams_tab(self):
        for tree in (self.live_tree, self.upcoming_tree):
            for i in tree.get_children():
                tree.delete(i)
        try:
            with su_records.db() as conn:
                live = ls.list_streams(conn, status='live')
                upcoming = ls.list_streams(conn, status='scheduled')
        except Exception as e:
            messagebox.showerror("Error", f"Could not load streams:\n{e}", parent=self.dialog)
            return
        for r in live:
            self.live_tree.insert('', 'end', iid=str(r['stream_id']), values=(
                r['title'], _streamer(r), _viewers(r), ls.duration_text(r.get('actual_start'), None),
                r.get('platform') or ''))
        if not live:
            self.live_tree.insert('', 'end', iid='empty-live', values=("Nothing is live right now", '', '', '', ''))
        for r in upcoming:
            self.upcoming_tree.insert('', 'end', iid=str(r['stream_id']), values=(
                r['title'], r['scheduled_start'], _streamer(r), r.get('platform') or ''))
        if not upcoming:
            self.upcoming_tree.insert('', 'end', iid='empty-up', values=("No streams scheduled", '', '', ''))

    def _selected_stream_id(self):
        for tree in (self.live_tree, self.upcoming_tree):
            sel = tree.selection()
            if sel and not sel[0].startswith('empty'):
                return int(sel[0])
        messagebox.showwarning("Warning", "Select a stream first.", parent=self.dialog)
        return None

    def _transition(self, status, done_msg, **kw):
        sid = self._selected_stream_id()
        if sid is None or not self._staff_only():
            return
        try:
            with su_records.db() as conn:
                ls.set_status(conn, sid, status, **kw)
        except ValueError as e:
            messagebox.showwarning("Warning", str(e), parent=self.dialog)
            return
        except Exception as e:
            messagebox.showerror("Error", f"Could not update the stream:\n{e}", parent=self.dialog)
            return
        messagebox.showinfo("Done", done_msg, parent=self.dialog)
        self.refresh_all()

    def start_stream(self):
        if messagebox.askyesno(_t(f'{_L}.dialogs.start_stream', default="Start Stream"),
                               "Mark the selected stream as live now?", parent=self.dialog):
            self._transition('live', "🔴 The stream is marked live.")

    def end_stream(self):
        if messagebox.askyesno(_t(f'{_L}.dialogs.end_stream', default="End Stream"),
                               _t(f'{_L}.dialogs.end_the_current_live_stream', default="End the current live stream?"), parent=self.dialog):
            peak = _ask_peak_viewers(self.dialog)
            self._transition('ended', "Stream ended. Link its recording on the Recordings tab once available.",
                             peak_viewers=peak)

    def cancel_stream(self):
        if messagebox.askyesno("Cancel Stream", "Cancel the selected scheduled stream?", parent=self.dialog):
            self._transition('cancelled', "Stream cancelled.")

    def edit_stream(self):
        sid = self._selected_stream_id()
        if sid is None or not self._staff_only():
            return
        dialog = StreamEditorDialog(self.dialog, self.auth, sid)
        self.dialog.wait_window(dialog.dialog)
        self.refresh_all()

    def open_stream_link(self):
        sid = self._selected_stream_id()
        if sid is None:
            return
        with su_records.db() as conn:
            r = ls.get_stream(conn, sid)
        if r and r.get('stream_url'):
            su_records.open_target(r['stream_url'])
        else:
            messagebox.showinfo("No link", "This stream has no URL set yet.", parent=self.dialog)

    # ------------------------------------------------------------ setup tab
    def create_setup_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text=_t(f'{_L}.labels.stream_configuration', default="Stream Configuration"),
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        pick = ttk.Frame(frame)
        pick.pack(fill='x', pady=(0, 10))
        ttk.Label(pick, text="Stream:").pack(side='left')
        self.setup_combo = ttk.Combobox(pick, width=60, state='readonly')
        self.setup_combo.pack(side='left', padx=5)
        self.setup_combo.bind('<<ComboboxSelected>>', self._load_setup)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x')
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.save_configuration', default="💾 Save Configuration"),
                  command=self.save_stream_config).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.test_stream', default="🔄 Test Stream"),
                  command=self.test_stream).pack(side='left')

        key_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.stream_keys_urls', default="Stream Keys & URLs"))
        key_frame.pack(side='bottom', fill='x', pady=(0, 10))
        ttk.Label(key_frame, justify='left', wraplength=900, text=(
            "Stream keys stay with each platform (YouTube Studio, Facebook Live Producer, Twitch "
            "dashboard…) and are entered in your encoder, not stored here. Put the public watch "
            "URL in 'Stream / watch URL' so attendees can find the stream.")).pack(padx=15, pady=10, anchor='w')

        self.setup_form = StreamForm(frame, self.auth, platforms_as_checks=True)
        self.setup_form.frame.pack(fill='both', expand=True, pady=(0, 10))

    def load_setup_choices(self):
        try:
            with su_records.db() as conn:
                rows = ls.list_streams(conn, status=('scheduled', 'live'))
        except Exception:
            rows = []
        self._setup_streams = {_stream_label(r): r['stream_id'] for r in rows}
        self.setup_combo['values'] = ('(new stream)',) + tuple(self._setup_streams)
        current = self.setup_form.stream_id
        label = next((k for k, v in self._setup_streams.items() if v == current), '(new stream)')
        self.setup_combo.set(label)

    def _load_setup(self, event=None):
        sid = self._setup_streams.get(self.setup_combo.get())
        if sid:
            self.setup_form.load(sid)
        else:
            self.setup_form.clear()

    def save_stream_config(self):
        sid = self.setup_form.save()
        if sid:
            messagebox.showinfo(_t(f'{_L}.dialogs.saved', default="Saved"), _t(f'{_L}.dialogs.stream_configuration_saved_successfully', default="Stream configuration saved successfully."), parent=self.dialog)
            self.refresh_all()

    def test_stream(self):
        url = self.setup_form.url_entry.get().strip()
        if not url:
            messagebox.showinfo(_t(f'{_L}.dialogs.test_stream', default="Test Stream"),
                                "Enter the stream / watch URL first.", parent=self.dialog)
            return
        if not su_records.open_target(url):
            messagebox.showwarning(_t(f'{_L}.dialogs.test_stream', default="Test Stream"),
                                   f"Could not open {url} on this computer.", parent=self.dialog)

    # ------------------------------------------------------------ chat tab
    def create_chat_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        pick = ttk.Frame(frame)
        pick.pack(fill='x', pady=(0, 5))
        ttk.Label(pick, text="Stream:").pack(side='left')
        self.chat_combo = ttk.Combobox(pick, width=60, state='readonly')
        self.chat_combo.pack(side='left', padx=5)
        self.chat_combo.bind('<<ComboboxSelected>>', lambda e: self.load_chat())
        ttk.Button(pick, text="Refresh", command=self.load_chat).pack(side='left')

        settings_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.chat_settings', default="Chat Settings"))
        settings_frame.pack(side='bottom', fill='x')
        for key, default in (('slow_mode_1_message_per_5_seconds', "Slow mode (1 message per 5 seconds)"),
                             ('subscriber_only_chat', "Subscriber-only chat"),
                             ('filter_profanity', "Filter profanity"),
                             ('emote_only_mode', "Emote-only mode")):
            ttk.Checkbutton(settings_frame, text=_t(f'{_L}.buttons.{key}', default=default) + " — set on the streaming platform",
                            state='disabled').pack(anchor='w', padx=10, pady=2)
        btn_frame = ttk.Frame(settings_frame)
        btn_frame.pack(fill='x', padx=10, pady=5)
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.ban_user', default="🚫 Ban User"),
                  command=self.ban_user).pack(side='left', padx=(0, 10))
        self.pause_btn = ttk.Button(btn_frame, text=_t(f'{_L}.buttons.pause_chat', default="⏸️ Pause Chat"),
                                    command=self.pause_chat)
        self.pause_btn.pack(side='left')

        control_frame = ttk.Frame(frame)
        control_frame.pack(side='bottom', fill='x', pady=(0, 10))
        ttk.Label(control_frame, text=_t(f'{_L}.labels.message', default="Message:")).pack(side='left', padx=(0, 5))
        self.message_entry = ttk.Entry(control_frame)
        self.message_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
        self.message_entry.bind('<Return>', lambda e: self.send_chat_message())
        ttk.Button(control_frame, text=_t(f'{_L}.buttons.send', default="Send"),
                  command=self.send_chat_message).pack(side='left')

        chat_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.live_chat', default="Live Chat"))
        chat_frame.pack(fill='both', expand=True, pady=(0, 10))
        self.chat_text = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, font=('Arial', 9), height=15)
        self.chat_text.pack(fill='both', expand=True, padx=5, pady=5)
        self.chat_text.config(state='disabled')

    def load_chat_streams(self):
        try:
            with su_records.db() as conn:
                rows = ls.list_streams(conn, status=('live', 'scheduled', 'ended'))
        except Exception:
            rows = []
        rows.sort(key=lambda r: ({'live': 0, 'scheduled': 1}.get(r['status'], 2), r['scheduled_start']))
        self._chat_streams = {_stream_label(r): r['stream_id'] for r in rows}
        keep = self.chat_combo.get()
        self.chat_combo['values'] = tuple(self._chat_streams)
        if keep not in self._chat_streams:
            self.chat_combo.set(next(iter(self._chat_streams), ''))
        self.load_chat()

    def _chat_stream(self):
        return self._chat_streams.get(self.chat_combo.get())

    def load_chat(self):
        sid = self._chat_stream()
        self.chat_text.config(state='normal')
        self.chat_text.delete(1.0, tk.END)
        if sid is None:
            self.chat_text.insert(1.0, "No streams yet.")
        else:
            try:
                with su_records.db() as conn:
                    msgs = ls.chat_messages(conn, sid)
                    r = ls.get_stream(conn, sid)
            except Exception as e:
                msgs, r = [], None
                self.chat_text.insert(1.0, f"Could not load chat: {e}")
            for m in msgs:
                self.chat_text.insert(tk.END, f"[{m['posted_at'][11:16]}] {m['author']}: {m['message']}\n")
            if r is not None and not msgs:
                self.chat_text.insert(1.0, "No messages yet.")
            if r is not None:
                self.pause_btn.config(text="▶️ Resume Chat" if not r['chat_enabled'] else
                                      _t(f'{_L}.buttons.pause_chat', default="⏸️ Pause Chat"))
        self.chat_text.config(state='disabled')

    def send_chat_message(self):
        sid = self._chat_stream()
        if sid is None:
            return
        author = su_records.username(self.auth)
        if not author:
            messagebox.showwarning("Warning", "Sign in to post.", parent=self.dialog)
            return
        try:
            with su_records.db() as conn:
                ls.post_chat(conn, sid, author, self.message_entry.get())
        except ValueError as e:
            messagebox.showwarning("Warning", str(e), parent=self.dialog)
            return
        except Exception as e:
            messagebox.showerror("Error", f"Could not post the message:\n{e}", parent=self.dialog)
            return
        self.message_entry.delete(0, tk.END)
        self.load_chat()

    def ban_user(self):
        sid = self._chat_stream()
        if sid is None or not self._staff_only():
            return
        with su_records.db() as conn:
            authors = sorted({m['author'] for m in ls.chat_messages(conn, sid)})
        who = simpledialog.askstring(_t(f'{_L}.dialogs.ban_user', default="Ban User"),
                                     "Username to remove from this stream's chat:"
                                     + (f"\n(posted so far: {', '.join(authors)})" if authors else ""),
                                     parent=self.dialog)
        if not who or not who.strip():
            return
        try:
            with su_records.db() as conn:
                hidden = ls.ban_author(conn, sid, who.strip())
        except Exception as e:
            messagebox.showerror("Error", f"Could not ban the user:\n{e}", parent=self.dialog)
            return
        messagebox.showinfo(_t(f'{_L}.dialogs.banned', default="Banned"),
                            f"{who.strip()} can no longer post here; {hidden} message(s) hidden.", parent=self.dialog)
        self.load_chat()

    def pause_chat(self):
        sid = self._chat_stream()
        if sid is None or not self._staff_only():
            return
        try:
            with su_records.db() as conn:
                enabled = ls.toggle_chat(conn, sid)
        except Exception as e:
            messagebox.showerror("Error", f"Could not change chat:\n{e}", parent=self.dialog)
            return
        messagebox.showinfo(_t(f'{_L}.dialogs.chat_paused', default="Chat Paused") if not enabled else "Chat Resumed",
                            "Live chat has been paused." if not enabled else "Live chat has been resumed.",
                            parent=self.dialog)
        self.load_chat()

    # ------------------------------------------------------------ recordings tab
    def create_recordings_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text=_t(f'{_L}.labels.stream_recordings', default="Stream Recordings"),
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x')
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.play', default="▶️ Play"),
                  command=self.play_recording).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.download', default="⬇️ Download"),
                  command=self.download_recording).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="🔗 Link Recording…", command=self.link_recording).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.delete', default="🗑️ Delete"),
                  command=self.delete_recording).pack(side='left')

        columns = ('Event', 'Date', 'Duration', 'Views', 'Link', 'Status')
        self.rec_tree = ttk.Treeview(frame, columns=columns, show='headings', height=12)
        for col in columns:
            self.rec_tree.heading(col, text=col)
            if col in ('Event', 'Link'):
                self.rec_tree.column(col, width=280)
        self.rec_tree.pack(fill='both', expand=True, pady=(0, 10))

    def load_recordings(self):
        for i in self.rec_tree.get_children():
            self.rec_tree.delete(i)
        try:
            with su_records.db() as conn:
                rows = ls.list_streams(conn, status='ended')
        except Exception as e:
            messagebox.showerror("Error", f"Could not load recordings:\n{e}", parent=self.dialog)
            return
        self._recordings = {str(r['stream_id']): r for r in rows}
        for r in reversed(rows):
            views = str(r['recording_views']) if r.get('recording_views') is not None else '—'
            self.rec_tree.insert('', 'end', iid=str(r['stream_id']), values=(
                r['title'], (r.get('actual_start') or r['scheduled_start'])[:10],
                ls.duration_text(r.get('actual_start'), r.get('actual_end')) if r.get('actual_end') else '—',
                views, r.get('recording_url') or '', 'Available' if r.get('recording_url') else 'No recording linked'))
        if not rows:
            self.rec_tree.insert('', 'end', iid='empty', values=("No streams have ended yet", '', '', '', '', ''))

    def _selected_recording(self, need_link=True):
        sel = self.rec_tree.selection()
        r = self._recordings.get(sel[0]) if sel else None
        if not r:
            messagebox.showwarning("Warning", "Select an ended stream first.", parent=self.dialog)
            return None
        if need_link and not r.get('recording_url'):
            messagebox.showinfo("No recording", "No recording is linked to this stream yet.", parent=self.dialog)
            return None
        return r

    def play_recording(self):
        r = self._selected_recording()
        if r and not su_records.open_target(r['recording_url']):
            messagebox.showwarning("Play", f"Could not open {r['recording_url']}.", parent=self.dialog)

    def download_recording(self):
        r = self._selected_recording()
        if r:
            su_records.open_target(r['recording_url'])
            messagebox.showinfo(_t(f'{_L}.dialogs.download', default="Download"),
                                "The recording link has been opened; use the platform's download option "
                                "if it offers one.", parent=self.dialog)

    def link_recording(self):
        r = self._selected_recording(need_link=False)
        if not r or not self._staff_only():
            return
        url = simpledialog.askstring("Link Recording", "Recording URL:", initialvalue=r.get('recording_url') or '',
                                     parent=self.dialog)
        if url is None:
            return
        views = None
        if url.strip() and messagebox.askyesno("Views", "Do you have a view count from the platform?", parent=self.dialog):
            views = simpledialog.askinteger("Views", "Recording views:", minvalue=0, parent=self.dialog)
        try:
            with su_records.db() as conn:
                ls.set_recording(conn, r['stream_id'], url, views)
        except ValueError as e:
            messagebox.showwarning("Warning", str(e), parent=self.dialog)
            return
        self.load_recordings()
        self.load_analytics()

    def delete_recording(self):
        r = self._selected_recording()
        if not r or not self._staff_only():
            return
        if messagebox.askyesno(_t(f'{_L}.dialogs.delete_recording', default="Delete Recording"),
                               "Remove this recording link? (The file on the streaming platform is not touched.)",
                               parent=self.dialog):
            with su_records.db() as conn:
                ls.set_recording(conn, r['stream_id'], None)
            self.load_recordings()
            self.load_analytics()

    # ------------------------------------------------------------ analytics tab
    def create_analytics_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        self.analytics_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        self.analytics_text.pack(fill='both', expand=True)

    def load_analytics(self):
        try:
            with su_records.db() as conn:
                report = ls.analytics_report(conn)
        except Exception as e:
            report = f"Could not build the report: {e}"
        self.analytics_text.config(state='normal')
        self.analytics_text.delete(1.0, tk.END)
        self.analytics_text.insert(1.0, report)
        self.analytics_text.config(state='disabled')



# Main application launcher - FIXED: Added proper parameter handling

def open_live_streaming_dialog(self):
    """Open live streaming platform"""
    dialog = LiveStreamingDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


