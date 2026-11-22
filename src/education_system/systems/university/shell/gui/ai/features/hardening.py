"""Production hardening controls for the chatbot GUI."""
import tkinter as tk
from tkinter import messagebox, ttk

class HardeningMixin:
    SENSITIVE_TERMS = ('grade', 'fee', 'payment', 'health', 'visa', 'attendance', 'address')

    def initialize_hardening(self):
        self.response_detail = 'balanced'
        self.response_language = 'Current interface language'
        self.reading_level = 'University'

    def confirm_sensitive_access(self, message):
        fields = [term for term in self.SENSITIVE_TERMS if term in message.casefold()]
        if not fields:
            return True
        return messagebox.askyesno('Data access preview',
            'This answer may access: ' + ', '.join(fields) + '.\nContinue?', parent=self.root)

    def show_memory_controls(self):
        win = tk.Toplevel(self.root); win.title('Assistant memory')
        ttk.Label(win, text='Information remembered for personalisation').pack(padx=12,pady=10)
        user = self.current_user.get('username','unknown')
        for item in self.conversation_store.memories(user):
            row=ttk.Frame(win); row.pack(fill=tk.X,padx=10,pady=3)
            ttk.Label(row,text=f"{item['memory_key']}: {item['memory_value']}").pack(side=tk.LEFT)
            ttk.Button(row,text='Remove',command=lambda k=item['memory_key'],r=row:(self.conversation_store.delete_memory(user,k),r.destroy())).pack(side=tk.RIGHT)

    def create_support_handoff(self):
        """'Contact support' opens a real case with the chatbot agents."""
        self.speak_to_person()

    def show_chat_notifications(self):
        notes=self.conversation_store.notifications(self.current_user.get('username','unknown'))
        messagebox.showinfo('Chatbot notifications','\n'.join(n['message'] for n in notes) or 'No new notifications.',parent=self.root)

    def show_quality_dashboard(self):
        rows=self.conversation_store.metrics_summary(self.current_user.get('username','unknown'))
        text='\n'.join(f"{r['event']}: {r['count']} events, average {r['average_ms'] or 0} ms" for r in rows)
        messagebox.showinfo('Assistant quality dashboard',text or 'No usage metrics yet.',parent=self.root)

    def response_instruction(self):
        return f"\n\nResponse preferences: {self.response_detail} detail; {self.reading_level} reading level; language: {self.response_language}."

    @staticmethod
    def render_rich_text(text):
        """Make common Markdown readable in Tk labels without hiding content."""
        return str(text).replace('**','').replace('### ','').replace('## ','').replace('# ','')
