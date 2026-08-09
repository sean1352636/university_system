from datetime import datetime


class SessionMixin:
    """Mixin for session tracking and statistics."""

    def create_session_management(self):
        """Create session management functionality"""
        self.session_start_time = datetime.now()
        self.message_count = 0
        self.session_data = {
            'start_time': self.session_start_time,
            'messages_sent': 0,
            'voice_interactions': 0,
            'errors_encountered': 0
        }

        def update_session_stats(message_type="text"):
            """Update session statistics"""
            self.session_data['messages_sent'] += 1
            self.message_count += 1

            if message_type == "voice":
                self.session_data['voice_interactions'] += 1

            # Update status bar with session info
            duration = datetime.now() - self.session_start_time
            duration_str = str(duration).split('.')[0]  # Remove microseconds

            status_text = f"Session: {duration_str} | Messages: {self.message_count}"
            if hasattr(self, 'status_label'):
                self.status_label.config(text=status_text)

        def get_session_summary():
            """Get session summary for logout"""
            duration = datetime.now() - self.session_start_time

            summary = f"""Session Summary:
Duration: {str(duration).split('.')[0]}
Messages Sent: {self.session_data['messages_sent']}
Voice Interactions: {self.session_data['voice_interactions']}
Errors: {self.session_data['errors_encountered']}
Start Time: {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S')}
End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            return summary

        return update_session_stats, get_session_summary
