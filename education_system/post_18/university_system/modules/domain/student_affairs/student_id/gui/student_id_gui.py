import tkinter as tk
from tkinter import ttk, messagebox
import logging
import hashlib
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class StudentIDGUI:
    """Digital Student ID Card viewer with QR code display."""

    def __init__(self, parent=None):
        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("Digital Student ID")
        self.window.geometry("500x700")
        self.window.resizable(False, False)

        try:
            from education_system.post_18.university_system.infrastructure.shared_context import get_auth
            self.auth = get_auth()
        except Exception:
            self.auth = None

        try:
            from education_system.post_18.university_system.core.i18n import get_text as _t
            self._t = _t
        except ImportError:
            self._t = lambda key, **kw: key

        self._init_db()
        self._build_ui()
        self._load_student_info()

    def _init_db(self):
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS student_id_cards (
                    card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL UNIQUE,
                    card_number TEXT NOT NULL,
                    issue_date TEXT DEFAULT (date('now')),
                    expiry_date TEXT,
                    status TEXT DEFAULT 'active',
                    photo_path TEXT DEFAULT '',
                    qr_data TEXT DEFAULT ''
                )""")
        except Exception as e:
            logger.error(f"DB init error: {e}")

    def _get_student_info(self):
        info = {
            'student_id': 'N/A', 'name': 'N/A', 'email': 'N/A',
            'course': 'N/A', 'department': 'N/A', 'year': 'N/A',
            'card_number': '', 'issue_date': '', 'expiry_date': '', 'status': 'active'
        }
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            user = self.auth.current_user
            if isinstance(user, dict):
                info['student_id'] = user.get('student_id', user.get('username', 'N/A'))
                info['name'] = user.get('name', user.get('full_name', user.get('username', 'N/A')))
                info['email'] = user.get('email', 'N/A')
            else:
                info['student_id'] = getattr(user, 'student_id', getattr(user, 'username', 'N/A'))
                info['name'] = getattr(user, 'name', getattr(user, 'full_name', 'N/A'))
                info['email'] = getattr(user, 'email', 'N/A')

        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            sid = info['student_id']
            with get_connection() as conn:
                # Get student details
                row = conn.execute(
                    "SELECT * FROM students WHERE student_id = ? OR username = ?",
                    (sid, sid)
                ).fetchone()
                if row:
                    keys = row.keys() if hasattr(row, 'keys') else []
                    if 'full_name' in keys:
                        info['name'] = row['full_name']
                    elif 'name' in keys:
                        info['name'] = row['name']
                    if 'email' in keys:
                        info['email'] = row['email']
                    if 'course' in keys:
                        info['course'] = row['course']
                    if 'department' in keys:
                        info['department'] = row['department']
                    if 'year_of_study' in keys:
                        info['year'] = str(row['year_of_study'])
                    elif 'year' in keys:
                        info['year'] = str(row['year'])

                # Get or create card
                card = conn.execute(
                    "SELECT * FROM student_id_cards WHERE student_id = ?", (sid,)
                ).fetchone()
                if card:
                    info['card_number'] = card['card_number']
                    info['issue_date'] = card['issue_date']
                    info['expiry_date'] = card['expiry_date'] or ''
                    info['status'] = card['status']
                else:
                    # Auto-generate card
                    card_num = "UNI-" + hashlib.sha256(sid.encode()).hexdigest()[:8].upper()
                    qr_data = json.dumps({'student_id': sid, 'card': card_num, 'type': 'student_id'})
                    conn.execute(
                        "INSERT OR IGNORE INTO student_id_cards (student_id, card_number, expiry_date, qr_data) VALUES (?, ?, date('now', '+4 years'), ?)",
                        (sid, card_num, qr_data)
                    )
                    conn.commit()
                    info['card_number'] = card_num
                    info['issue_date'] = datetime.now().strftime('%Y-%m-%d')
                    info['expiry_date'] = str(datetime.now().year + 4) + datetime.now().strftime('-%m-%d')
        except Exception as e:
            logger.debug(f"Load student info: {e}")

        return info

    def _build_ui(self):
        # Card background
        self.card_frame = tk.Frame(self.window, bg="#1a237e", padx=3, pady=3)
        self.card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        inner = tk.Frame(self.card_frame, bg="white")
        inner.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(inner, bg="#1a237e", height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="UNIVERSITY", font=("Helvetica", 18, "bold"),
                 fg="white", bg="#1a237e").pack(pady=(15, 0))
        tk.Label(header, text="STUDENT IDENTIFICATION CARD", font=("Helvetica", 9),
                 fg="#90caf9", bg="#1a237e").pack()

        # Photo placeholder
        photo_frame = tk.Frame(inner, bg="white")
        photo_frame.pack(pady=15)

        self.photo_canvas = tk.Canvas(photo_frame, width=120, height=150, bg="#e0e0e0",
                                       highlightthickness=1, highlightbackground="#bdbdbd")
        self.photo_canvas.pack()
        self.photo_canvas.create_text(60, 75, text="Photo", font=("Helvetica", 12), fill="#757575")

        # Info fields
        info_frame = tk.Frame(inner, bg="white", padx=30)
        info_frame.pack(fill=tk.X)

        self.info_labels = {}
        fields = [
            ("Name", "name"), ("Student ID", "student_id"), ("Email", "email"),
            ("Course", "course"), ("Department", "department"), ("Year", "year"),
            ("Card Number", "card_number"), ("Status", "status"),
            ("Issued", "issue_date"), ("Expires", "expiry_date")
        ]
        for label_text, key in fields:
            row_frame = tk.Frame(info_frame, bg="white")
            row_frame.pack(fill=tk.X, pady=2)
            tk.Label(row_frame, text=f"{label_text}:", font=("Helvetica", 9, "bold"),
                     bg="white", fg="#424242", width=12, anchor=tk.W).pack(side=tk.LEFT)
            val_label = tk.Label(row_frame, text="", font=("Helvetica", 9),
                                 bg="white", fg="#616161", anchor=tk.W)
            val_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.info_labels[key] = val_label

        # QR Code placeholder
        qr_frame = tk.Frame(inner, bg="white")
        qr_frame.pack(pady=15)
        tk.Label(qr_frame, text="QR Code", font=("Helvetica", 8), bg="white", fg="#9e9e9e").pack()

        self.qr_canvas = tk.Canvas(qr_frame, width=120, height=120, bg="white",
                                    highlightthickness=1, highlightbackground="#e0e0e0")
        self.qr_canvas.pack()
        self._draw_qr_placeholder()

        # Footer
        footer = tk.Frame(inner, bg="#e8eaf6")
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(footer, text="Present this card for campus access and services",
                 font=("Helvetica", 8), bg="#e8eaf6", fg="#5c6bc0").pack(pady=5)

        # Buttons below card
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        ttk.Button(btn_frame, text="Refresh", command=self._load_student_info).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Report Lost Card", command=self._report_lost).pack(side=tk.LEFT, padx=5)

    def _draw_qr_placeholder(self):
        """Draw a simple QR-like pattern as placeholder."""
        import random
        size = 10
        offset = 10
        for row in range(size):
            for col in range(size):
                x1 = offset + col * 10
                y1 = offset + row * 10
                # Create corner patterns (like real QR codes)
                is_corner = (row < 3 and col < 3) or (row < 3 and col >= size-3) or (row >= size-3 and col < 3)
                if is_corner or random.random() > 0.5:
                    self.qr_canvas.create_rectangle(x1, y1, x1+10, y1+10, fill="black", outline="")

    def _load_student_info(self):
        info = self._get_student_info()
        for key, label in self.info_labels.items():
            value = info.get(key, 'N/A')
            label.configure(text=str(value))
            if key == 'status':
                color = "#4caf50" if value == 'active' else "#f44336"
                label.configure(fg=color, font=("Helvetica", 9, "bold"))

    def _report_lost(self):
        if messagebox.askyesno("Report Lost Card",
                "Report your student ID card as lost?\nA new card number will be generated."):
            try:
                from education_system.post_18.university_system.infrastructure.database.db import get_connection
                sid = self._get_student_info()['student_id']
                with get_connection() as conn:
                    conn.execute("UPDATE student_id_cards SET status='lost' WHERE student_id=?", (sid,))
                    # Generate new card
                    new_num = "UNI-" + hashlib.sha256((sid + str(datetime.now())).encode()).hexdigest()[:8].upper()
                    qr_data = json.dumps({'student_id': sid, 'card': new_num, 'type': 'student_id'})
                    conn.execute("DELETE FROM student_id_cards WHERE student_id=?", (sid,))
                    conn.execute(
                        "INSERT INTO student_id_cards (student_id, card_number, expiry_date, qr_data) VALUES (?, ?, date('now', '+4 years'), ?)",
                        (sid, new_num, qr_data)
                    )
                    conn.commit()
                messagebox.showinfo("Success", f"New card issued: {new_num}")
                self._load_student_info()
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {e}")


def launch_student_id_gui(parent=None):
    return StudentIDGUI(parent=parent)
