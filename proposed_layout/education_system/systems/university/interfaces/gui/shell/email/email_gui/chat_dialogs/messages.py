from ._common import RecipientSelectorDialog, messagebox, scrolledtext, tk, ttk
from education_system.systems.university.infrastructure.email.email_db_utilities import (
    execute_db_operation,
)

class ComposeMessageDialog:
    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Compose Message")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Recipient
        ttk.Label(main_frame, text="To:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.recipient_entry = ttk.Entry(main_frame, width=40)
        self.recipient_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Button(main_frame, text="Select", command=self.select_recipient).grid(row=0, column=2, padx=5)

        # Subject
        ttk.Label(main_frame, text="Subject:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.subject_entry = ttk.Entry(main_frame, width=40)
        self.subject_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW, pady=5)

        # Message
        ttk.Label(main_frame, text="Message:").grid(row=2, column=0, sticky=tk.NW, pady=5)
        self.message_text = scrolledtext.ScrolledText(main_frame, width=50, height=15)
        self.message_text.grid(row=2, column=1, columnspan=2, sticky=tk.NSEW, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=10)

        ttk.Button(button_frame, text="Send", command=self.send_message).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

    def select_recipient(self):
        """Select message recipient"""
        RecipientSelectorDialog(self.dialog, self.recipient_entry)

    def send_message(self):
        """Send the message"""
        try:
            recipient_email = self.recipient_entry.get().strip()
            subject = self.subject_entry.get().strip()
            content = self.message_text.get(1.0, tk.END).strip()

            if not recipient_email or not subject or not content:
                messagebox.showerror("Error", "Please fill in all fields")
                return

            # Find recipient user ID
            def _find_recipient(cursor):
                cursor.execute("SELECT id FROM users WHERE email = ?", (recipient_email,))
                result = cursor.fetchone()
                return result[0] if result else None

            if execute_db_operation is not None:
                recipient_id = execute_db_operation(_find_recipient)

                if recipient_id and self.dashboard:
                    if self.dashboard.send_message(recipient_id, subject, content):
                        messagebox.showinfo("Success", "Message sent successfully")
                        self.dialog.destroy()
                    else:
                        messagebox.showerror("Error", "Failed to send message")
                else:
                    messagebox.showerror("Error", "Recipient not found")
            else:
                messagebox.showerror("Error", "Messaging system not available")

        except Exception as e:
            messagebox.showerror("Error", f"Error sending message: {e}")


class ReplyMessageDialog:
    def __init__(self, parent, dashboard, message_id):
        self.dashboard = dashboard
        self.message_id = message_id
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Reply to Message")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
        self.load_original_message()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Original message (read-only)
        ttk.Label(main_frame, text="Original Message:").pack(anchor=tk.W)
        self.original_text = scrolledtext.ScrolledText(main_frame, height=8, state=tk.DISABLED)
        self.original_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Reply
        ttk.Label(main_frame, text="Your Reply:").pack(anchor=tk.W, pady=(10, 0))
        self.reply_text = scrolledtext.ScrolledText(main_frame, height=8)
        self.reply_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Send Reply", command=self.send_reply).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def load_original_message(self):
        """Load the original message"""
        try:
            if self.dashboard:
                message = self.dashboard.read_message(self.message_id)
                if message:
                    original_content = f"From: {message['sender']}\n"
                    original_content += f"Subject: {message['subject']}\n"
                    original_content += f"Date: {message['sent_at']}\n"
                    original_content += "-" * 40 + "\n"
                    original_content += message['content']

                    self.original_text.config(state=tk.NORMAL)
                    self.original_text.insert(1.0, original_content)
                    self.original_text.config(state=tk.DISABLED)

                    # Store message info for reply
                    self.original_sender_id = message['sender_id']
                    self.original_subject = message['subject']
        except Exception as e:
            messagebox.showerror("Error", f"Error loading original message: {e}")

    def send_reply(self):
        """Send the reply"""
        try:
            reply_content = self.reply_text.get(1.0, tk.END).strip()

            if not reply_content:
                messagebox.showerror("Error", "Please enter a reply")
                return

            # Create reply subject
            reply_subject = self.original_subject
            if not reply_subject.startswith("Re: "):
                reply_subject = f"Re: {reply_subject}"

            if self.dashboard:
                if self.dashboard.send_message(self.original_sender_id, reply_subject, reply_content):
                    messagebox.showinfo("Success", "Reply sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send reply")

        except Exception as e:
            messagebox.showerror("Error", f"Error sending reply: {e}")

