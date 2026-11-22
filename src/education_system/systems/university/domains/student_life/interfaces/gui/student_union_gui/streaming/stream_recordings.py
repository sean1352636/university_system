"""Recording & replay for SU live streams: auto-record defaults, library, on-demand, playback report, downloads."""

import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog

from education_system import paths
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import (
    live_streams as ls,
)
from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.core import (
    su_records,
)
from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.streaming.live_streaming import (
    _L,
    _stream_label,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import (
    live_stream_interaction as lsi,
)


class RecordingManagementDialog:
    """Recording and replay management over linked stream recordings"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.staff = su_records.is_staff(auth_manager)
        self.me = su_records.username(auth_manager)
        self._downloads = []  # dicts: title, url, path, progress, status, pause, cancel

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t(f'{_L}.windows.recording_replay_management', default="Recording & Replay Management"))
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.refresh()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t(f'{_L}.labels.recording_replay_management', default="🎥 Recording & Replay Management"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        ttk.Button(main_frame, text=_t(f'{_L}.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='bottom')

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))
        for key, default, builder in (
                ('auto_recording', "Auto-Recording", self.create_auto_tab),
                ('video_library', "Video Library", self.create_library_tab),
                ('on_demand_viewing', "On-Demand Viewing", self.create_ondemand_tab),
                ('playback_analytics', "Playback Analytics", self.create_analytics_tab),
                ('download_options', "Download Options", self.create_download_tab)):
            tab = ttk.Frame(notebook)
            notebook.add(tab, text=_t(f'{_L}.tabs.{key}', default=default))
            builder(tab)

    def refresh(self):
        self.load_settings()
        self.load_active()
        self.load_library()
        self.load_ondemand()
        self.load_analytics()

    def _staff_only(self):
        if self.staff:
            return True
        messagebox.showwarning("Staff only", "Only Student Union staff can do this.", parent=self.dialog)
        return False

    # ------------------------------------------------------------ auto-recording
    def create_auto_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.stop_recording', default="⏹️ Stop Recording"),
                  command=self.stop_recording).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.save_settings', default="💾 Save Settings"),
                  command=self.save_recording_settings).pack(side='left')

        settings_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.auto_recording_settings', default="Auto-Recording Settings"))
        settings_frame.pack(fill='x', pady=(0, 15))
        self.set_vars = {k: tk.BooleanVar() for k in ('auto_record_streams', 'auto_record_virtual_events', 'auto_record_conferences')}
        for key, tkey, default in (
                ('auto_record_streams', 'automatically_record_all_live_streams', "Automatically record all live streams"),
                ('auto_record_virtual_events', 'automatically_record_virtual_events', "Automatically record virtual events"),
                ('auto_record_conferences', 'automatically_record_conference_sessions', "Automatically record conference sessions")):
            ttk.Checkbutton(settings_frame, text=_t(f'{_L}.buttons.{tkey}', default=default),
                            variable=self.set_vars[key]).pack(anchor='w', padx=10, pady=5)
        ttk.Label(settings_frame, foreground='gray', wraplength=900, text=(
            "These are the defaults for new streams' 'Record' setting (the recording itself is "
            "made by the streaming platform; link it afterwards on Live Streaming → Recordings).")).pack(anchor='w', padx=10)

        quality_frame = ttk.Frame(settings_frame)
        quality_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(quality_frame, text=_t(f'{_L}.labels.recording_quality', default="Recording quality:")).pack(side='left', padx=(0, 5))
        self.quality_combo = ttk.Combobox(quality_frame, width=20, state='readonly', values=ls.QUALITIES)
        self.quality_combo.pack(side='left')

        storage_frame = ttk.Frame(settings_frame)
        storage_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(storage_frame, text=_t(f'{_L}.labels.storage_location', default="Storage location:")).pack(side='left', padx=(0, 5))
        self.storage_entry = ttk.Entry(storage_frame, width=60)
        self.storage_entry.pack(side='left')
        ttk.Button(storage_frame, text=_t(f'{_L}.buttons.browse', default="Browse"), command=self.browse_storage).pack(side='left', padx=(5, 0))

        active_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.currently_recording', default="Currently Recording"))
        active_frame.pack(fill='both', expand=True)
        columns = ('Event', 'Started', 'Duration', 'Platform', 'Status')
        self.active_tree = ttk.Treeview(active_frame, columns=columns, show='headings', height=8)
        for col in columns:
            self.active_tree.heading(col, text=col)
            if col == 'Event':
                self.active_tree.column(col, width=300)
        self.active_tree.pack(fill='both', expand=True, padx=5, pady=5)

    def _default_storage(self):
        return str(paths.UNIVERSITY_EXPORTS_DIR / "stream_recordings")

    def load_settings(self):
        with su_records.db() as conn:
            self.settings = lsi.get_settings(conn)
        for k, v in self.set_vars.items():
            v.set(self.settings.get(k) == '1')
        q = self.settings.get('recording_quality')
        self.quality_combo.set(q if q in ls.QUALITIES else ls.QUALITIES[0])
        self.storage_entry.delete(0, tk.END)
        self.storage_entry.insert(0, self.settings.get('storage_location') or self._default_storage())
        if hasattr(self, 'dl_quality'):
            self.dl_subs.set(self.settings.get('download_subtitles') == '1')
            self.dl_thumb.set(self.settings.get('download_thumbnail') == '1')

    def browse_storage(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(parent=self.dialog, initialdir=self.storage_entry.get() or None)
        if path:
            self.storage_entry.delete(0, tk.END)
            self.storage_entry.insert(0, path)

    def load_active(self):
        for i in self.active_tree.get_children():
            self.active_tree.delete(i)
        with su_records.db() as conn:
            live = ls.list_streams(conn, status='live')
        for r in live:
            self.active_tree.insert('', 'end', iid=str(r['stream_id']), values=(
                r['title'], r.get('actual_start') or '', ls.duration_text(r.get('actual_start'), None),
                r.get('platform') or '', "🔴 Recording" if r.get('record_stream') else "Live, not recording"))
        if not live:
            self.active_tree.insert('', 'end', iid='empty', values=("Nothing is live right now", '', '', '', ''))

    def stop_recording(self):
        sel = self.active_tree.selection()
        if not sel or sel[0] == 'empty':
            messagebox.showwarning("Warning", "Select a live stream first.", parent=self.dialog)
            return
        if not self._staff_only():
            return
        if messagebox.askyesno(_t(f'{_L}.dialogs.stop_recording', default="Stop Recording"),
                               "Mark this stream as not being recorded?\n\n(Stop the recording on the "
                               "streaming platform too.)", parent=self.dialog):
            with su_records.db() as conn:
                ls.set_record_flag(conn, int(sel[0]), False)
            self.load_active()

    def save_recording_settings(self):
        if not self._staff_only():
            return
        values = {k: '1' if v.get() else '0' for k, v in self.set_vars.items()}
        values['recording_quality'] = self.quality_combo.get()
        store = self.storage_entry.get().strip()
        values['storage_location'] = '' if store == self._default_storage() else store
        values['download_subtitles'] = '1' if self.dl_subs.get() else '0'
        values['download_thumbnail'] = '1' if self.dl_thumb.get() else '0'
        with su_records.db() as conn:
            lsi.save_settings(conn, values, actor=self.me)
        messagebox.showinfo(_t(f'{_L}.dialogs.saved', default="Saved"), _t(f'{_L}.dialogs.recording_settings_saved_successfully', default="Recording settings saved successfully."), parent=self.dialog)
        self.load_settings()

    # ------------------------------------------------------------ library
    def create_library_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        search_frame = ttk.Frame(frame)
        search_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(search_frame, text=_t(f'{_L}.labels.search', default="Search:")).pack(side='left', padx=(0, 5))
        self.search_entry = ttk.Entry(search_frame, width=30)
        self.search_entry.pack(side='left', padx=(0, 10))
        self.search_entry.bind('<Return>', lambda e: self.load_library())
        ttk.Button(search_frame, text=_t(f'{_L}.buttons.search', default="🔍 Search"), command=self.load_library).pack(side='left', padx=(0, 20))
        ttk.Label(search_frame, text=_t(f'{_L}.labels.filter', default="Filter:")).pack(side='left', padx=(0, 5))
        self.filter_combo = ttk.Combobox(search_frame, width=25, state='readonly')
        self.filter_combo.pack(side='left')
        self.filter_combo.bind('<<ComboboxSelected>>', lambda e: self.load_library())

        stats_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.library_statistics', default="Library Statistics"))
        stats_frame.pack(side='bottom', fill='x', pady=(10, 0))
        self.lib_stats = ttk.Label(stats_frame, text="", justify='left', font=('Courier', 9))
        self.lib_stats.pack(padx=15, pady=10, anchor='w')

        lib_btns = ttk.Frame(frame)
        lib_btns.pack(side='bottom', fill='x')
        ttk.Button(lib_btns, text="▶️ Watch", command=lambda: self.watch_video(self.lib_tree)).pack(side='left', padx=(0, 10))
        ttk.Button(lib_btns, text="⬇️ Download", command=self.queue_download).pack(side='left', padx=(0, 10))
        ttk.Button(lib_btns, text="➕ Add to Playlist", command=lambda: self.add_to_playlist(self.lib_tree)).pack(side='left')

        columns = ('Title', 'Date', 'Duration', 'Views', 'Club')
        self.lib_tree = ttk.Treeview(frame, columns=columns, show='headings', height=12)
        for col in columns:
            self.lib_tree.heading(col, text=col)
            if col == 'Title':
                self.lib_tree.column(col, width=400)
        self.lib_tree.pack(fill='both', expand=True, pady=(0, 10))

    def load_library(self):
        for i in self.lib_tree.get_children():
            self.lib_tree.delete(i)
        with su_records.db() as conn:
            everything = lsi.library(conn)
            rows = lsi.library(conn, search=self.search_entry.get().strip(), club=self.filter_combo.get() or None)
        clubs = sorted({r.get('club_name') or 'Student Union' for r in everything})
        keep = self.filter_combo.get()
        self.filter_combo['values'] = ('All Events',) + tuple(clubs)
        self.filter_combo.set(keep if keep in self.filter_combo['values'] else 'All Events')
        self._lib = {str(r['stream_id']): r for r in everything}
        for r in rows:
            m = lsi.recording_minutes(r)
            self.lib_tree.insert('', 'end', iid=str(r['stream_id']), values=(
                r['title'], (r.get('actual_start') or r['scheduled_start'])[:10],
                ls.duration_text(r.get('actual_start'), r.get('actual_end')) if m is not None else '—',
                r['recording_views'] if r.get('recording_views') is not None else '—',
                r.get('club_name') or 'Student Union'))
        if not rows:
            self.lib_tree.insert('', 'end', iid='empty', values=("No recordings linked yet" if not everything else "No matches", '', '', '', ''))
        views = [r['recording_views'] for r in everything if r.get('recording_views') is not None]
        top = max((r for r in everything if r.get('recording_views') is not None),
                  key=lambda r: r['recording_views'], default=None)
        mins = sum(m for m in (lsi.recording_minutes(r) for r in everything) if m is not None)
        popular = f"{top['title']} ({top['recording_views']} views)" if top else '—'
        self.lib_stats.config(text=(
            f"Total Recordings: {len(everything)}\n"
            f"Total Recorded Length: {mins / 60:.1f} hours\n"
            f"Total Views (entered): {sum(views) if views else '—'}\n"
            f"Most Popular: {popular}\n"
            "Storage: recordings stay on their platforms; only links are kept here."))

    def _selected_recording(self, tree):
        sel = tree.selection()
        r = self._lib.get(sel[0]) if sel else None
        if not r:
            messagebox.showwarning("Warning", "Select a recording first.", parent=self.dialog)
        return r

    def watch_video(self, tree=None):
        r = self._selected_recording(tree or self.od_tree)
        if r and not su_records.open_target(r['recording_url']):
            messagebox.showwarning(_t(f'{_L}.dialogs.watch', default="Watch"), f"Could not open {r['recording_url']}.", parent=self.dialog)

    def add_to_playlist(self, tree=None):
        r = self._selected_recording(tree or self.od_tree)
        if not r:
            return
        try:
            with su_records.db() as conn:
                added = lsi.add_to_playlist(conn, self.me, r['stream_id'])
        except ValueError as e:
            messagebox.showwarning("Warning", str(e), parent=self.dialog)
            return
        messagebox.showinfo(_t(f'{_L}.dialogs.added', default="Added"),
                            "Added to your playlist." if added else "It's already in your playlist.", parent=self.dialog)
        self.load_ondemand()
        self.load_analytics()

    # ------------------------------------------------------------ on demand
    def create_ondemand_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.watch', default="▶️ Watch"),
                  command=self.watch_video).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.add_to_playlist', default="➕ Add to Playlist"),
                  command=self.add_to_playlist).pack(side='left')

        featured_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.featured_on_demand_content', default="🌟 Featured On-Demand Content"))
        featured_frame.pack(fill='x', pady=(0, 15))
        self.featured_label = ttk.Label(featured_frame, text="", justify='left', font=('Courier', 9))
        self.featured_label.pack(padx=15, pady=10, anchor='w')

        categories_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.browse_by_category', default="Browse by Category"))
        categories_frame.pack(fill='both', expand=True)
        columns = ('Videos', 'Total Duration', 'Total Views')
        self.od_tree = ttk.Treeview(categories_frame, columns=columns, show='tree headings', height=10)
        self.od_tree.heading('#0', text='Category / Recording')
        self.od_tree.column('#0', width=400)
        for col in columns:
            self.od_tree.heading(col, text=col)
        self.od_tree.pack(fill='both', expand=True, padx=5, pady=5)

    def load_ondemand(self):
        for i in self.od_tree.get_children():
            self.od_tree.delete(i)
        with su_records.db() as conn:
            rows = lsi.library(conn)
            mine = lsi.playlist(conn, self.me) if self.me else []
        self._lib.update({str(r['stream_id']): r for r in rows})
        ranked = sorted((r for r in rows if r.get('recording_views') is not None),
                        key=lambda r: -r['recording_views'])[:3]
        lines = ["MOST VIEWED (views entered from the platform):"]
        lines += [f"  {i}. {r['title']} — {r['recording_views']} views" for i, r in enumerate(ranked, 1)] or ["  No view counts entered yet."]
        lines += ["", f"MY PLAYLIST ({len(mine)}):"]
        lines += [f"  • {r['title']}" for r in mine[:5]] or ["  Empty — use 'Add to Playlist'."]
        self.featured_label.config(text="\n".join(lines))
        groups = {}
        for r in rows:
            groups.setdefault(r.get('club_name') or 'Student Union', []).append(r)
        for name, items in sorted(groups.items()):
            mins = sum(m for m in (lsi.recording_minutes(r) for r in items) if m is not None)
            views = [r['recording_views'] for r in items if r.get('recording_views') is not None]
            parent_id = self.od_tree.insert('', 'end', text=name, open=True, values=(
                len(items), f"{mins // 60}h {mins % 60:02d}m", sum(views) if views else '—'))
            for r in items:
                m = lsi.recording_minutes(r)
                self.od_tree.insert(parent_id, 'end', iid=str(r['stream_id']), text=r['title'], values=(
                    '', f"{m // 60}h {m % 60:02d}m" if m is not None else '—',
                    r['recording_views'] if r.get('recording_views') is not None else '—'))
        if not rows:
            self.od_tree.insert('', 'end', text="No recordings linked yet", values=('', '', ''))

    # ------------------------------------------------------------ analytics
    def create_analytics_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        self.pb_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        self.pb_text.pack(fill='both', expand=True)

    def load_analytics(self):
        with su_records.db() as conn:
            report = lsi.playback_report(conn)
        done = [d for d in self._downloads if d['status'] == 'Completed']
        report += f"\n\nDownloads completed this session: {len(done)}"
        self.pb_text.config(state='normal')
        self.pb_text.delete(1.0, tk.END)
        self.pb_text.insert(1.0, report)
        self.pb_text.config(state='disabled')

    # ------------------------------------------------------------ downloads
    def create_download_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.pause', default="⏸️ Pause"),
                  command=self.pause_download).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.cancel', default="❌ Cancel"),
                  command=self.cancel_download).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.open_folder', default="📂 Open Folder"),
                  command=self.open_download_folder).pack(side='left')

        settings_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.download_settings', default="Download Settings"))
        settings_frame.pack(fill='x', pady=(0, 15))
        ttk.Label(settings_frame, text=_t(f'{_L}.labels.default_download_quality', default="Default download quality:"),
                 font=('Arial', 10)).pack(anchor='w', padx=10, pady=5)
        self.dl_quality = tk.StringVar(value="1080p")
        for value, key, default in (("1080p", 'value_1080p_full_hd_largest_file', "1080p Full HD (largest file)"),
                                    ("720p", 'value_720p_hd_recommended', "720p HD (recommended)"),
                                    ("480p", 'value_480p_sd_smaller_file', "480p SD (smaller file)")):
            ttk.Radiobutton(settings_frame, text=_t(f'{_L}.buttons.{key}', default=default) + " — only if the platform offers it",
                            variable=self.dl_quality, value=value, state='disabled').pack(anchor='w', padx=20, pady=2)
        self.dl_subs = tk.BooleanVar(value=False)
        self.dl_thumb = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text=_t(f'{_L}.buttons.include_subtitles_when_available', default="Include subtitles when available"),
                        variable=self.dl_subs).pack(anchor='w', padx=10, pady=5)
        ttk.Checkbutton(settings_frame, text=_t(f'{_L}.buttons.download_thumbnail', default="Download thumbnail"),
                        variable=self.dl_thumb).pack(anchor='w', padx=10, pady=5)
        ttk.Label(settings_frame, foreground='gray', wraplength=900, text=(
            "Downloads fetch the linked recording file into the storage folder (Auto-Recording tab). "
            "Links to a web page rather than a video file (e.g. a YouTube page) can only be watched. "
            "Subtitle/thumbnail options are saved with Save Settings; neither is fetched unless the "
            "platform exposes a separate file for it.")).pack(anchor='w', padx=10, pady=(0, 5))

        queue_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.download_queue', default="Download Queue"))
        queue_frame.pack(fill='both', expand=True)
        columns = ('Video', 'Progress', 'Speed', 'ETA', 'Status')
        self.dl_tree = ttk.Treeview(queue_frame, columns=columns, show='headings', height=8)
        for col in columns:
            self.dl_tree.heading(col, text=col)
            if col == 'Video':
                self.dl_tree.column(col, width=350)
        self.dl_tree.pack(fill='both', expand=True, padx=5, pady=5)
        self._render_downloads()

    def _storage_dir(self):
        from pathlib import Path
        return Path(self.storage_entry.get().strip() or self._default_storage())

    def queue_download(self):
        r = self._selected_recording(self.lib_tree)
        if not r:
            return
        url = r['recording_url']
        if not url.lower().startswith(("http://", "https://")):
            messagebox.showwarning("Download", "Only http(s) links can be downloaded.", parent=self.dialog)
            return
        safe = "".join(c if c.isalnum() else "_" for c in r['title']).strip("_")[:60] or f"stream_{r['stream_id']}"
        job = {'title': r['title'], 'url': url, 'dir': self._storage_dir(), 'name': safe,
               'done': 0, 'total': None, 'speed': 0.0, 'status': 'Queued',
               'pause': threading.Event(), 'cancel': threading.Event(), 'path': None}
        self._downloads.append(job)
        threading.Thread(target=self._download, args=(job,), daemon=True).start()
        self._render_downloads()

    def _download(self, job):
        import time
        import urllib.request
        try:
            job['status'] = 'Connecting'
            req = urllib.request.Request(job['url'], headers={'User-Agent': 'EducationSystem/1.0'})
            with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 - http(s) checked above
                ctype = (resp.headers.get('Content-Type') or '').split(';')[0].strip().lower()
                if not (ctype.startswith(('video/', 'audio/')) or ctype in ('application/octet-stream', 'application/mp4')):
                    job['status'] = f"Not a video file ({ctype or 'unknown'}) — use Watch"
                    return
                ext = {'video/mp4': '.mp4', 'video/webm': '.webm', 'audio/mpeg': '.mp3'}.get(ctype, '.mp4')
                job['dir'].mkdir(parents=True, exist_ok=True)
                path = job['dir'] / (job['name'] + ext)
                job['path'] = path
                job['total'] = int(resp.headers.get('Content-Length') or 0) or None
                job['status'] = 'Downloading'
                start = time.monotonic()
                with open(path, 'wb') as fh:
                    while True:
                        if job['cancel'].is_set():
                            break
                        while job['pause'].is_set() and not job['cancel'].is_set():
                            job['status'] = 'Paused'
                            time.sleep(0.3)
                        if job['cancel'].is_set():
                            break
                        job['status'] = 'Downloading'
                        chunk = resp.read(256 * 1024)
                        if not chunk:
                            break
                        fh.write(chunk)
                        job['done'] += len(chunk)
                        job['speed'] = job['done'] / max(0.001, time.monotonic() - start)
                if job['cancel'].is_set():
                    path.unlink(missing_ok=True)
                    job['status'] = 'Cancelled'
                else:
                    job['status'] = 'Completed'
        except Exception as exc:
            job['status'] = f"Failed: {exc.__class__.__name__}"

    def _render_downloads(self):
        try:
            if not self.dl_tree.winfo_exists():
                return
        except tk.TclError:
            return
        sel = self.dl_tree.selection()
        for i in self.dl_tree.get_children():
            self.dl_tree.delete(i)
        for n, j in enumerate(self._downloads):
            if j['total']:
                prog = f"{j['done'] * 100 / j['total']:.0f}%"
                eta = (f"{int((j['total'] - j['done']) / j['speed'])}s" if j['speed'] and j['status'] == 'Downloading' else '-')
            else:
                prog = f"{j['done'] / 1048576:.1f} MB" if j['done'] else '-'
                eta = '-'
            speed = f"{j['speed'] / 1048576:.1f} MB/s" if j['status'] == 'Downloading' else '-'
            self.dl_tree.insert('', 'end', iid=str(n), values=(j['title'], prog, speed, eta, j['status']))
        if not self._downloads:
            self.dl_tree.insert('', 'end', iid='empty', values=("No downloads yet — use Video Library → Download", '', '', '', ''))
        for s in sel:
            if self.dl_tree.exists(s):
                self.dl_tree.selection_add(s)
        if any(j['status'] in ('Queued', 'Connecting', 'Downloading', 'Paused') for j in self._downloads):
            self.dialog.after(700, self._render_downloads)

    def _selected_job(self):
        sel = self.dl_tree.selection()
        if not sel or sel[0] == 'empty':
            messagebox.showwarning("Warning", "Select a download first.", parent=self.dialog)
            return None
        return self._downloads[int(sel[0])]

    def pause_download(self):
        j = self._selected_job()
        if not j:
            return
        if j['pause'].is_set():
            j['pause'].clear()
        elif j['status'] in ('Downloading', 'Connecting', 'Queued'):
            j['pause'].set()
        self._render_downloads()

    def cancel_download(self):
        j = self._selected_job()
        if j and j['status'] in ('Queued', 'Connecting', 'Downloading', 'Paused'):
            if messagebox.askyesno(_t(f'{_L}.dialogs.cancel', default="Cancel"), _t(f'{_L}.dialogs.cancel_this_download', default="Cancel this download?"), parent=self.dialog):
                j['cancel'].set()
                self._render_downloads()

    def open_download_folder(self):
        folder = self._storage_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            messagebox.showerror(_t(f'{_L}.dialogs.folder', default="Folder"), str(e), parent=self.dialog)
            return
        if not su_records.open_target(folder):
            messagebox.showinfo(_t(f'{_L}.dialogs.folder', default="Folder"), f"Downloads folder:\n{folder}", parent=self.dialog)
