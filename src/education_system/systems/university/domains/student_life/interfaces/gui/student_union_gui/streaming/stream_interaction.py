"""Interactive features for SU live streams: polls/quizzes, Q&A, networking and breakout rooms."""

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


class _StreamPicker:
    """'Stream:' combobox over scheduled/live/ended streams, live first."""

    def __init__(self, parent, on_change):
        self.frame = ttk.Frame(parent)
        ttk.Label(self.frame, text="Stream:").pack(side='left')
        self.combo = ttk.Combobox(self.frame, width=70, state='readonly')
        self.combo.pack(side='left', padx=5)
        self.combo.bind('<<ComboboxSelected>>', lambda e: on_change())
        ttk.Button(self.frame, text="Refresh", command=lambda: (self.load(), on_change())).pack(side='left')
        self._map = {}
        self.load()

    def load(self):
        try:
            with su_records.db() as conn:
                rows = ls.list_streams(conn, status=('live', 'scheduled', 'ended'))
        except Exception:
            rows = []
        rows.sort(key=lambda r: ({'live': 0, 'scheduled': 1}.get(r['status'], 2), r['scheduled_start']))
        keep = self.combo.get()
        self._map = {f"[{r['status']}] " + _stream_label(r): r['stream_id'] for r in rows}
        self.combo['values'] = tuple(self._map)
        if keep not in self._map:
            self.combo.set(next(iter(self._map), ''))

    def get(self):
        return self._map.get(self.combo.get())


def _ask_choice(parent, title, prompt, options):
    """Modal list picker; returns the chosen index or None."""
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.grab_set()
    ttk.Label(win, text=prompt, wraplength=420).pack(padx=15, pady=(15, 5), anchor='w')
    var = tk.IntVar(value=-1)
    for i, opt in enumerate(options):
        ttk.Radiobutton(win, text=opt, variable=var, value=i).pack(anchor='w', padx=25, pady=2)
    result = {'i': None}

    def ok():
        if var.get() >= 0:
            result['i'] = var.get()
        win.destroy()
    btns = ttk.Frame(win)
    btns.pack(fill='x', padx=15, pady=15)
    ttk.Button(btns, text="OK", command=ok).pack(side='left', padx=(0, 10))
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side='left')
    parent.wait_window(win)
    return result['i']


class _PollEditor:
    """Create a poll, or a quiz when ask_correct=True"""

    def __init__(self, parent, title, ask_correct=False):
        self.result = None
        self.ask_correct = ask_correct
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.transient(parent)
        self.win.grab_set()
        f = ttk.Frame(self.win)
        f.pack(fill='both', expand=True, padx=15, pady=15)
        ttk.Label(f, text="Question:").grid(row=0, column=0, sticky='w', pady=4)
        self.q = ttk.Entry(f, width=50)
        self.q.grid(row=0, column=1, sticky='ew', pady=4)
        self.opts = []
        for i in range(6):
            ttk.Label(f, text=f"Option {chr(65 + i)}{' *' if i < 2 else ''}:").grid(row=i + 1, column=0, sticky='w', pady=2)
            e = ttk.Entry(f, width=50)
            e.grid(row=i + 1, column=1, sticky='ew', pady=2)
            self.opts.append(e)
        if ask_correct:
            ttk.Label(f, text="Correct option:").grid(row=7, column=0, sticky='w', pady=4)
            self.correct = ttk.Combobox(f, width=5, state='readonly', values=[chr(65 + i) for i in range(6)])
            self.correct.grid(row=7, column=1, sticky='w', pady=4)
        f.columnconfigure(1, weight=1)
        b = ttk.Frame(self.win)
        b.pack(fill='x', padx=15, pady=(0, 15))
        ttk.Button(b, text="Create", command=self.ok).pack(side='left', padx=(0, 10))
        ttk.Button(b, text="Cancel", command=self.win.destroy).pack(side='left')
        parent.wait_window(self.win)

    def ok(self):
        raw = [e.get().strip() for e in self.opts]
        correct = None
        if self.ask_correct:
            letter = self.correct.get()
            if not letter:
                messagebox.showwarning("Quiz", "Choose the correct option.", parent=self.win)
                return
            idx = ord(letter) - 65
            if idx >= len(raw) or not raw[idx]:
                messagebox.showwarning("Quiz", "The correct option is empty.", parent=self.win)
                return
            correct = sum(1 for o in raw[:idx] if o)  # index among non-empty options
        self.result = (self.q.get(), [o for o in raw if o], correct)
        self.win.destroy()


class InteractiveVirtualFeaturesDialog:
    """Interactive features for a stream: polls, Q&A, networking and breakout rooms"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.staff = su_records.is_staff(auth_manager)
        self.me = su_records.username(auth_manager)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t(f'{_L}.windows.interactive_virtual_features', default="Interactive Virtual Features"))
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.refresh()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t(f'{_L}.labels.interactive_virtual_event_features', default="💻 Interactive Virtual Event Features"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        self.picker = _StreamPicker(main_frame, self.refresh)
        self.picker.frame.pack(fill='x', pady=(0, 10))

        ttk.Button(main_frame, text=_t(f'{_L}.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='bottom')

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        for key, default, builder in (
                ('live_polls', "Live Polls", self.create_polls_tab),
                ('q_a_sessions', "Q&A Sessions", self.create_qa_tab),
                ('virtual_networking', "Virtual Networking", self.create_networking_tab),
                ('breakout_rooms', "Breakout Rooms", self.create_breakout_tab),
                ('interactive_presentations', "Interactive Presentations", self.create_presentations_tab)):
            tab = ttk.Frame(notebook)
            notebook.add(tab, text=_t(f'{_L}.tabs.{key}', default=default))
            builder(tab)

    def _sid(self, warn=True):
        sid = self.picker.get()
        if sid is None and warn:
            messagebox.showwarning("Warning", "Schedule a stream first (Live Streaming → Schedule Stream…).", parent=self.dialog)
        return sid

    def _staff_only(self):
        if self.staff:
            return True
        messagebox.showwarning("Staff only", "Only Student Union staff can do this.", parent=self.dialog)
        return False

    def _run(self, fn, *args, done=None, **kw):
        """Call a store function with a fresh connection; show ValueErrors as warnings."""
        try:
            with su_records.db() as conn:
                out = fn(conn, *args, **kw)
        except ValueError as e:
            messagebox.showwarning("Warning", str(e), parent=self.dialog)
            return None
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)
            return None
        if done:
            messagebox.showinfo("Done", done, parent=self.dialog)
        self.refresh()
        return out if out is not None else True

    def refresh(self):
        self.load_polls()
        self.load_questions()
        self.load_networking()
        self.load_breakouts()
        self.load_presentations()

    # ------------------------------------------------------------ polls
    def create_polls_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Button(frame, text=_t(f'{_L}.buttons.create_new_poll', default="➕ Create New Poll"),
                  command=self.create_poll).pack(side='bottom', pady=(10, 0))

        active_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.active_poll', default="📊 Active Poll"))
        active_frame.pack(fill='x', pady=(0, 15))
        self.poll_label = ttk.Label(active_frame, text="", justify='left', font=('Courier', 9))
        self.poll_label.pack(padx=15, pady=10, anchor='w')

        btn_frame = ttk.Frame(active_frame)
        btn_frame.pack(fill='x', padx=15, pady=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.vote', default="✓ Vote"),
                  command=self.vote_poll).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.end_poll', default="⏹️ End Poll"),
                  command=self.end_poll).pack(side='left')

        history_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.recent_polls', default="Recent Polls"))
        history_frame.pack(fill='both', expand=True)
        columns = ('Question', 'Winner', 'Votes', 'Date')
        self.poll_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=8)
        for col in columns:
            self.poll_tree.heading(col, text=col)
            if col == 'Question':
                self.poll_tree.column(col, width=350)
        self.poll_tree.pack(fill='both', expand=True, padx=5, pady=5)

    def load_polls(self):
        for i in self.poll_tree.get_children():
            self.poll_tree.delete(i)
        self.active_poll = None
        sid = self._sid(warn=False)
        if sid is None:
            self.poll_label.config(text="No streams yet.")
            return
        with su_records.db() as conn:
            rows = lsi.polls(conn, sid)
        self.active_poll = next((p for p in rows if p['status'] == 'open'), None)
        p = self.active_poll
        if p:
            lines = [("Quiz: " if p['is_quiz'] else "Question: ") + p['question'], "", "Options:"]
            for i, (opt, n) in enumerate(zip(p['options'], p['counts'])):
                pct = n * 100 / p['total'] if p['total'] else 0
                bar = '█' * round(pct / 10) + '░' * (10 - round(pct / 10))
                lines.append(f"  {chr(65 + i)}) {opt[:38]:<38} {n:>4} ({pct:.0f}%) [{bar}]")
            lines += ["", f"Total Votes: {p['total']}"]
            self.poll_label.config(text="\n".join(lines))
        else:
            self.poll_label.config(text="No poll is open for this stream.")
        for q in rows:
            if q['status'] != 'closed':
                continue
            winner = lsi.poll_summary(q)
            if q['is_quiz'] and q['correct_option'] is not None:
                right = q['counts'][q['correct_option']]
                winner = f"Answer: {q['options'][q['correct_option']]} — {right}/{q['total']} correct"
            self.poll_tree.insert('', 'end', values=(q['question'], winner, q['total'], (q['closed_at'] or '')[:16]))
        if not self.poll_tree.get_children():
            self.poll_tree.insert('', 'end', values=("No closed polls yet", '', '', ''))

    def vote_poll(self):
        p = self.active_poll
        if not p:
            messagebox.showinfo("Vote", "There is no open poll for this stream.", parent=self.dialog)
            return
        idx = _ask_choice(self.dialog, "Vote", p['question'], p['options'])
        if idx is not None:
            self._run(lsi.vote, p['poll_id'], self.me, idx,
                      done=_t(f'{_L}.dialogs.your_vote_has_been_recorded_thank_you', default="Your vote has been recorded. Thank you!"))

    def end_poll(self):
        p = self.active_poll
        if not p or not self._staff_only():
            return
        if messagebox.askyesno(_t(f'{_L}.dialogs.end_poll', default="End Poll"), _t(f'{_L}.dialogs.end_this_poll_and_display_results', default="End this poll and display results?"), parent=self.dialog):
            if self._run(lsi.close_poll, p['poll_id']):
                with su_records.db() as conn:
                    final = next(x for x in lsi.polls(conn, p['stream_id']) if x['poll_id'] == p['poll_id'])
                messagebox.showinfo(_t(f'{_L}.dialogs.results', default="Results"),
                                    f"Poll ended.\n\n{final['question']}\nLeading: {lsi.poll_summary(final)}\n"
                                    f"Total votes: {final['total']}", parent=self.dialog)

    def _new_poll(self, quiz):
        sid = self._sid()
        if sid is None or not self._staff_only():
            return
        ed = _PollEditor(self.dialog, "Create Quiz" if quiz else "Create Poll", ask_correct=quiz)
        if ed.result:
            q, opts, correct = ed.result
            self._run(lsi.create_poll, sid, q, opts, actor=self.me, correct_option=correct,
                      done="Quiz is open for answers." if quiz else "Poll is open for votes.")

    def create_poll(self):
        self._new_poll(quiz=False)

    # ------------------------------------------------------------ Q&A
    def create_qa_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x')
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.ask_question', default="❓ Ask Question"),
                  command=self.ask_question).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.upvote', default="👍 Upvote"),
                  command=self.upvote_question).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.mark_answered', default="✓ Mark Answered"),
                  command=self.mark_answered).pack(side='left')

        columns = ('Question', 'Asker', 'Votes', 'Status')
        self.qa_tree = ttk.Treeview(frame, columns=columns, show='headings', height=12)
        for col in columns:
            self.qa_tree.heading(col, text=col)
            if col == 'Question':
                self.qa_tree.column(col, width=450)
        self.qa_tree.pack(fill='both', expand=True, pady=(0, 10))

    def load_questions(self):
        for i in self.qa_tree.get_children():
            self.qa_tree.delete(i)
        sid = self._sid(warn=False)
        rows = []
        if sid is not None:
            with su_records.db() as conn:
                rows = lsi.questions(conn, sid)
        for q in rows:
            self.qa_tree.insert('', 'end', iid=str(q['question_id']),
                                values=(q['question'], q['author'], q['votes'], q['status'].title()))
        if not rows:
            self.qa_tree.insert('', 'end', iid='empty', values=("No questions yet", '', '', ''))

    def _selected_question(self):
        sel = self.qa_tree.selection()
        if not sel or sel[0] == 'empty':
            messagebox.showwarning("Warning", "Select a question first.", parent=self.dialog)
            return None
        return int(sel[0])

    def ask_question(self):
        sid = self._sid()
        if sid is None:
            return
        text = simpledialog.askstring(_t(f'{_L}.dialogs.ask_question', default="Ask Question"), "Your question:", parent=self.dialog)
        if text:
            self._run(lsi.ask, sid, self.me, text, done="Your question has been submitted. Questions are listed by votes.")

    def upvote_question(self):
        qid = self._selected_question()
        if qid is not None:
            self._run(lsi.upvote, qid, self.me)

    def mark_answered(self):
        qid = self._selected_question()
        if qid is not None and self._staff_only():
            self._run(lsi.mark_answered, qid)

    # ------------------------------------------------------------ networking
    def create_networking_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.join_room', default="🚪 Join Room"),
                  command=self.join_networking_room).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.create_room', default="➕ Create Room"),
                  command=self.create_networking_room).pack(side='left')

        lobby_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.virtual_networking_lobby', default="🤝 Virtual Networking Lobby"))
        lobby_frame.pack(fill='x', pady=(0, 15))
        self.lobby_label = ttk.Label(lobby_frame, text="", justify='left', wraplength=950)
        self.lobby_label.pack(padx=15, pady=10, anchor='w')

        rooms_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.discussion_rooms', default="Discussion Rooms"))
        rooms_frame.pack(fill='both', expand=True)
        columns = ('Room', 'Topic', 'Participants', 'Status')
        self.net_tree = ttk.Treeview(rooms_frame, columns=columns, show='headings', height=8)
        for col in columns:
            self.net_tree.heading(col, text=col)
        self.net_tree.pack(fill='both', expand=True, padx=5, pady=5)

    def load_networking(self):
        for i in self.net_tree.get_children():
            self.net_tree.delete(i)
        sid = self._sid(warn=False)
        if sid is None:
            self.lobby_label.config(text="No streams yet.")
            return
        with su_records.db() as conn:
            people = lsi.participants(conn, sid)
            rows = lsi.rooms(conn, sid, 'networking')
        shown = ", ".join(people[:15]) + (f" and {len(people) - 15} more" if len(people) > 15 else "")
        self.lobby_label.config(text=(f"Known participants: {len(people)}"
                                      + (f"\n{shown}" if people else "")
                                      + "\n\nParticipants are event registrants and anyone who has posted in chat or Q&A."))
        for r in rows:
            cap = f"{r['members']}/{r['capacity']}" if r['capacity'] else str(r['members'])
            full = r['capacity'] and r['members'] >= r['capacity']
            status = "Full" if full else ("Private" if r['is_private'] else "Open")
            self.net_tree.insert('', 'end', iid=str(r['room_id']), values=(r['name'], r['topic'] or '', cap, status))
        if not rows:
            self.net_tree.insert('', 'end', iid='empty', values=("No rooms yet", '', '', ''))

    def join_networking_room(self):
        sel = self.net_tree.selection()
        if not sel or sel[0] == 'empty':
            messagebox.showwarning("Warning", "Select a room first.", parent=self.dialog)
            return
        room = self._run(lsi.join_room, int(sel[0]), self.me)
        if room and room is not True:
            if room.get('meeting_link'):
                su_records.open_target(room['meeting_link'])
                messagebox.showinfo(_t(f'{_L}.dialogs.joining', default="Joining"), f"You're in {room['name']}. Opening its link…", parent=self.dialog)
            else:
                messagebox.showinfo(_t(f'{_L}.dialogs.joining', default="Joining"), f"You're listed in {room['name']}. The host hasn't added a meeting link for it.", parent=self.dialog)

    def create_networking_room(self):
        sid = self._sid()
        if sid is None:
            return
        win = tk.Toplevel(self.dialog)
        win.title(_t(f'{_L}.dialogs.create_room', default="Create Room"))
        win.transient(self.dialog)
        win.grab_set()
        f = ttk.Frame(win)
        f.pack(padx=15, pady=15)
        entries = {}
        for row, (key, label) in enumerate((('name', "Room name *"), ('topic', "Topic"),
                                            ('capacity', "Capacity (max 15)"), ('link', "Meeting link"))):
            ttk.Label(f, text=label).grid(row=row, column=0, sticky='w', pady=3)
            e = ttk.Entry(f, width=40)
            e.grid(row=row, column=1, pady=3)
            entries[key] = e
        entries['capacity'].insert(0, "15")
        private = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Private", variable=private).grid(row=4, column=1, sticky='w')

        def save():
            cap = entries['capacity'].get().strip()
            if cap.isdigit() and int(cap) > 15:
                messagebox.showwarning("Create Room", "Capacity is at most 15.", parent=win)
                return
            try:
                with su_records.db() as conn:
                    lsi.create_room(conn, sid, 'networking', entries['name'].get(), topic=entries['topic'].get(),
                                    capacity=cap, meeting_link=entries['link'].get(),
                                    is_private=private.get(), actor=self.me)
            except ValueError as e:
                messagebox.showwarning("Create Room", str(e), parent=win)
                return
            win.destroy()
            self.refresh()
        b = ttk.Frame(win)
        b.pack(fill='x', padx=15, pady=(0, 15))
        ttk.Button(b, text="Create", command=save).pack(side='left', padx=(0, 10))
        ttk.Button(b, text="Cancel", command=win.destroy).pack(side='left')

    # ------------------------------------------------------------ breakouts
    def create_breakout_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        control_frame = ttk.LabelFrame(frame, text=_t(f'{_L}.labels.breakout_room_controls', default="Breakout Room Controls"))
        control_frame.pack(side='bottom', fill='x')
        ttk.Label(control_frame, text=_t(f'{_L}.labels.auto_assign_participants_to_breakout_rooms', default="Auto-assign participants to breakout rooms:"),
                 font=('Arial', 10)).pack(anchor='w', padx=10, pady=5)
        assign_frame = ttk.Frame(control_frame)
        assign_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(assign_frame, text=_t(f'{_L}.labels.number_of_rooms', default="Number of rooms:")).pack(side='left', padx=(0, 5))
        self.rooms_spin = ttk.Spinbox(assign_frame, from_=2, to=20, width=5)
        self.rooms_spin.set(4)
        self.rooms_spin.pack(side='left', padx=(0, 10))
        ttk.Label(assign_frame, text="Minutes:").pack(side='left', padx=(0, 5))
        self.minutes_spin = ttk.Spinbox(assign_frame, from_=5, to=120, width=5)
        self.minutes_spin.set(15)
        self.minutes_spin.pack(side='left', padx=(0, 10))
        ttk.Button(assign_frame, text=_t(f'{_L}.buttons.create_assign', default="Create & Assign"),
                  command=self.create_breakout_rooms).pack(side='left')
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.broadcast_message', default="📢 Broadcast Message"),
                  command=self.broadcast_to_breakout).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.extend_time', default="⏰ Extend Time"),
                  command=self.extend_breakout_time).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.return_all_to_main', default="🔙 Return All to Main"),
                  command=self.return_from_breakout).pack(side='left')

        columns = ('Room', 'Participants', 'Members', 'Time Remaining')
        self.bo_tree = ttk.Treeview(frame, columns=columns, show='headings', height=10)
        for col in columns:
            self.bo_tree.heading(col, text=col)
        self.bo_tree.column('Members', width=450)
        self.bo_tree.pack(fill='both', expand=True, pady=(0, 15))

    def load_breakouts(self):
        for i in self.bo_tree.get_children():
            self.bo_tree.delete(i)
        sid = self._sid(warn=False)
        rows = []
        if sid is not None:
            with su_records.db() as conn:
                rows = lsi.rooms(conn, sid, 'breakout')
                members = {r['room_id']: lsi.room_members(conn, r['room_id']) for r in rows}
        for r in rows:
            self.bo_tree.insert('', 'end', values=(r['name'], r['members'], ", ".join(members[r['room_id']]),
                                                   lsi.time_left(r.get('ends_at'))))
        if not rows:
            self.bo_tree.insert('', 'end', values=("No breakout rooms open", '', '', ''))

    def create_breakout_rooms(self):
        sid = self._sid()
        if sid is None or not self._staff_only():
            return
        try:
            n, m = int(self.rooms_spin.get()), int(self.minutes_spin.get())
        except ValueError:
            messagebox.showwarning("Warning", "Rooms and minutes must be numbers.", parent=self.dialog)
            return
        out = self._run(lsi.create_breakouts, sid, n, minutes=m, actor=self.me)
        if out and out is not True:
            messagebox.showinfo(_t(f'{_L}.dialogs.creating', default="Creating"),
                                f"{out[0]} breakout rooms opened; {out[1]} known participant(s) assigned.", parent=self.dialog)

    def broadcast_to_breakout(self):
        sid = self._sid()
        if sid is None or not self._staff_only():
            return
        text = simpledialog.askstring(_t(f'{_L}.dialogs.broadcast', default="Broadcast"), "Message to all breakout rooms:", parent=self.dialog)
        if text:
            self._run(ls.post_chat, sid, self.me, f"[To all breakout rooms] {text}",
                      done="Posted to the stream chat for every breakout room.")

    def extend_breakout_time(self):
        sid = self._sid()
        if sid is None or not self._staff_only():
            return
        n = self._run(lsi.extend_breakouts, sid, 10)
        if n is not None:
            messagebox.showinfo(_t(f'{_L}.dialogs.extended', default="Extended"),
                                f"{n if n is not True else 0} breakout room(s) extended by 10 minutes.", parent=self.dialog)

    def return_from_breakout(self):
        sid = self._sid()
        if sid is None or not self._staff_only():
            return
        if messagebox.askyesno(_t(f'{_L}.dialogs.return_all', default="Return All"),
                               _t(f'{_L}.dialogs.return_all_participants_to_the_main_session', default="Return all participants to the main session?"), parent=self.dialog):
            self._run(lsi.close_breakouts, sid, done="Breakout rooms closed; everyone is back in the main session.")

    # ------------------------------------------------------------ presentations
    def create_presentations_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x')
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.launch_whiteboard', default="🎨 Launch Whiteboard"),
                  command=self.launch_whiteboard).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(f'{_L}.buttons.create_quiz', default="📊 Create Quiz"),
                  command=self.create_quiz).pack(side='left')

        self.pres_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        self.pres_text.pack(fill='both', expand=True, pady=(0, 10))

    def load_presentations(self):
        sid = self._sid(warn=False)
        lines = ["INTERACTIVE PRESENTATION TOOLS", "=" * 60, "",
                 "• Polls and quizzes — Live Polls tab / Create Quiz (votes are stored per stream)",
                 "• Audience questions — Q&A Sessions tab",
                 "• Group work — Breakout Rooms tab",
                 "• Whiteboard — opens a shared Excalidraw board in your browser",
                 "• Screen sharing and annotation — done in the meeting platform itself", ""]
        if sid is not None:
            with su_records.db() as conn:
                ps = lsi.polls(conn, sid)
                qs = lsi.questions(conn, sid)
                rooms = lsi.rooms(conn, sid, 'breakout', include_closed=True)
            lines += ["THIS STREAM", "-" * 60,
                      f"Polls/quizzes run: {len(ps)} ({sum(p['total'] for p in ps)} votes)",
                      f"Questions asked: {len(qs)} ({sum(1 for q in qs if q['status'] == 'answered')} answered)",
                      f"Breakout rooms used: {len(rooms)}", ""]
        with su_records.db() as conn:
            upcoming = ls.list_streams(conn, status='scheduled')
        lines.append("UPCOMING STREAMS")
        lines += [f"  {r['scheduled_start']}: {r['title']}" for r in upcoming[:10]] or ["  None scheduled."]
        self.pres_text.config(state='normal')
        self.pres_text.delete(1.0, tk.END)
        self.pres_text.insert(1.0, "\n".join(lines))
        self.pres_text.config(state='disabled')

    def launch_whiteboard(self):
        if messagebox.askyesno(_t(f'{_L}.dialogs.whiteboard', default="Whiteboard"),
                               "Open a shared whiteboard (excalidraw.com) in your browser?\n\n"
                               "Use its 'Live collaboration' button to share the board link in chat.",
                               parent=self.dialog):
            su_records.open_target("https://excalidraw.com/")

    def create_quiz(self):
        self._new_poll(quiz=True)
