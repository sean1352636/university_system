"""
Slack Integration Service

Sends notifications and alerts to Slack channels.
Requires slack-sdk library and Slack Bot Token.
"""

import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Optional dependency - graceful degradation if not available
try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False
    logger.warning("slack-sdk not available - Slack integration disabled")


class SlackNotifier:
    """Service for sending notifications to Slack"""

    def __init__(self):
        """Initialize Slack notifier"""
        self.bot_token = os.getenv('SLACK_BOT_TOKEN', '')
        self.client = None

        if SLACK_AVAILABLE and self.bot_token:
            try:
                self.client = WebClient(token=self.bot_token)
                # Test the connection
                self.client.auth_test()
                logger.info("Slack integration initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Slack client: {e}")
                self.client = None
        else:
            if not SLACK_AVAILABLE:
                logger.warning("slack-sdk not installed")
            else:
                logger.warning("SLACK_BOT_TOKEN not configured")

    def is_available(self) -> bool:
        """Check if Slack integration is available"""
        return self.client is not None

    def send_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        thread_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send message to Slack channel

        Args:
            channel: Channel ID or name (e.g., '#general', 'C1234567890')
            text: Message text (fallback for notifications)
            blocks: Rich message blocks (Block Kit)
            thread_ts: Thread timestamp for replying to thread

        Returns:
            Result dictionary with success status
        """
        if not self.client:
            return {
                'success': False,
                'error': 'Slack client not initialized'
            }

        try:
            response = self.client.chat_postMessage(
                channel=channel,
                text=text,
                blocks=blocks,
                thread_ts=thread_ts
            )

            logger.info(f"Sent Slack message to {channel}")
            return {
                'success': True,
                'ts': response['ts'],
                'channel': response['channel']
            }

        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            return {
                'success': False,
                'error': e.response['error']
            }

        except Exception as e:
            logger.error(f"Error sending Slack message: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def send_alert(
        self,
        channel: str,
        title: str,
        message: str,
        severity: str = "info",
        fields: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Send alert message with formatting

        Args:
            channel: Channel ID or name
            title: Alert title
            message: Alert message
            severity: Alert severity (info, warning, error, critical)
            fields: Additional fields to display

        Returns:
            Result dictionary
        """
        # Color coding based on severity
        colors = {
            'info': '#36a64f',      # Green
            'warning': '#ff9900',   # Orange
            'error': '#ff0000',     # Red
            'critical': '#8b0000'   # Dark Red
        }

        color = colors.get(severity, '#808080')

        # Build blocks for rich formatting
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 {title}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            }
        ]

        # Add fields if provided
        if fields:
            field_items = []
            for field in fields:
                field_items.append({
                    "type": "mrkdwn",
                    "text": f"*{field.get('title', '')}*\n{field.get('value', '')}"
                })

            blocks.append({
                "type": "section",
                "fields": field_items
            })

        # Add timestamp
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"<!date^{int(datetime.utcnow().timestamp())}^{{date_num}} {{time_secs}}|{datetime.utcnow().isoformat()}>"
                }
            ]
        })

        return self.send_message(
            channel=channel,
            text=f"{title}: {message}",  # Fallback text
            blocks=blocks
        )

    def send_student_alert(
        self,
        channel: str,
        student_id: str,
        student_name: str,
        alert_type: str,
        details: str
    ) -> Dict[str, Any]:
        """Send student-specific alert"""
        return self.send_alert(
            channel=channel,
            title=f"Student Alert: {alert_type}",
            message=details,
            severity="warning",
            fields=[
                {"title": "Student ID", "value": student_id},
                {"title": "Student Name", "value": student_name}
            ]
        )

    def send_system_alert(
        self,
        channel: str,
        alert_type: str,
        message: str,
        severity: str = "error"
    ) -> Dict[str, Any]:
        """Send system alert"""
        return self.send_alert(
            channel=channel,
            title=f"System Alert: {alert_type}",
            message=message,
            severity=severity
        )

    def send_enrollment_notification(
        self,
        channel: str,
        student_name: str,
        course_code: str,
        course_name: str
    ) -> Dict[str, Any]:
        """Send course enrollment notification"""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✅ *New Enrollment*\n{student_name} enrolled in {course_code} - {course_name}"
                }
            }
        ]

        return self.send_message(
            channel=channel,
            text=f"{student_name} enrolled in {course_code}",
            blocks=blocks
        )

    def send_grade_posted_notification(
        self,
        channel: str,
        course_code: str,
        assignment_name: str,
        student_count: int
    ) -> Dict[str, Any]:
        """Send grade posted notification"""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📝 *Grades Posted*\n{assignment_name} for {course_code} ({student_count} students)"
                }
            }
        ]

        return self.send_message(
            channel=channel,
            text=f"Grades posted for {course_code} - {assignment_name}",
            blocks=blocks
        )

    def upload_file(
        self,
        channel: str,
        file_path: str,
        title: Optional[str] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload file to Slack channel

        Args:
            channel: Channel ID or name
            file_path: Path to file
            title: File title
            comment: File comment

        Returns:
            Result dictionary
        """
        if not self.client:
            return {
                'success': False,
                'error': 'Slack client not initialized'
            }

        try:
            response = self.client.files_upload_v2(
                channel=channel,
                file=file_path,
                title=title,
                initial_comment=comment
            )

            logger.info(f"Uploaded file to Slack channel {channel}")
            return {
                'success': True,
                'file_id': response['file']['id']
            }

        except SlackApiError as e:
            logger.error(f"Slack API error uploading file: {e.response['error']}")
            return {
                'success': False,
                'error': e.response['error']
            }

        except Exception as e:
            logger.error(f"Error uploading file to Slack: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Singleton instance
_slack_notifier: Optional[SlackNotifier] = None


def get_slack_notifier() -> SlackNotifier:
    """Get or create Slack notifier singleton"""
    global _slack_notifier
    if _slack_notifier is None:
        _slack_notifier = SlackNotifier()
    return _slack_notifier
