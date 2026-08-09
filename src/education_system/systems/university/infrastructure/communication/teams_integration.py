"""
Microsoft Teams Integration Service

Sends notifications and alerts to Microsoft Teams channels using webhooks.
No additional libraries required - uses standard requests.
"""

import logging
import os
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TeamsNotifier:
    """Service for sending notifications to Microsoft Teams"""

    def __init__(self):
        """Initialize Teams notifier"""
        # Teams uses incoming webhooks - no authentication needed
        # Webhooks are configured per-channel in Teams
        self.webhook_url = os.getenv('TEAMS_WEBHOOK_URL', '')

        if self.webhook_url:
            logger.info("Microsoft Teams integration initialized")
        else:
            logger.warning("TEAMS_WEBHOOK_URL not configured")

    def is_available(self) -> bool:
        """Check if Teams integration is available"""
        return bool(self.webhook_url)

    def send_message(
        self,
        text: str,
        title: Optional[str] = None,
        sections: Optional[List[Dict[str, Any]]] = None,
        webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send message to Teams channel

        Args:
            text: Message text
            title: Message title
            sections: Message sections for rich formatting
            webhook_url: Optional webhook URL (overrides default)

        Returns:
            Result dictionary with success status
        """
        url = webhook_url or self.webhook_url

        if not url:
            return {
                'success': False,
                'error': 'Teams webhook URL not configured'
            }

        # Build message card (MessageCard format)
        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": title or text[:50],
            "themeColor": "0078D7",  # Microsoft blue
            "title": title,
            "text": text
        }

        if sections:
            payload["sections"] = sections

        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )

            if response.status_code == 200:
                logger.info("Sent Teams message successfully")
                return {
                    'success': True,
                    'status_code': response.status_code
                }
            else:
                logger.error(f"Teams API error: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}"
                }

        except requests.exceptions.Timeout:
            logger.error("Teams webhook timeout")
            return {
                'success': False,
                'error': 'Request timeout'
            }

        except Exception as e:
            logger.error(f"Error sending Teams message: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def send_alert(
        self,
        title: str,
        message: str,
        severity: str = "info",
        facts: Optional[List[Dict[str, str]]] = None,
        webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send alert message with formatting

        Args:
            title: Alert title
            message: Alert message
            severity: Alert severity (info, warning, error, critical)
            facts: Additional facts to display
            webhook_url: Optional webhook URL

        Returns:
            Result dictionary
        """
        # Color coding based on severity
        colors = {
            'info': '0078D7',       # Blue
            'warning': 'FFA500',    # Orange
            'error': 'DC143C',      # Crimson
            'critical': '8B0000'    # Dark Red
        }

        color = colors.get(severity, '808080')

        # Build sections
        sections = [
            {
                "activityTitle": f"🚨 {title}",
                "activitySubtitle": message,
                "facts": facts or []
            }
        ]

        # Add timestamp
        sections.append({
            "text": f"*Timestamp:* {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        })

        # Build payload
        url = webhook_url or self.webhook_url

        if not url:
            return {
                'success': False,
                'error': 'Teams webhook URL not configured'
            }

        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": title,
            "themeColor": color,
            "sections": sections
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )

            if response.status_code == 200:
                logger.info(f"Sent Teams alert: {title}")
                return {
                    'success': True,
                    'status_code': response.status_code
                }
            else:
                logger.error(f"Teams API error: {response.status_code}")
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}"
                }

        except Exception as e:
            logger.error(f"Error sending Teams alert: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def send_student_alert(
        self,
        student_id: str,
        student_name: str,
        alert_type: str,
        details: str,
        webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send student-specific alert"""
        return self.send_alert(
            title=f"Student Alert: {alert_type}",
            message=details,
            severity="warning",
            facts=[
                {"name": "Student ID", "value": student_id},
                {"name": "Student Name", "value": student_name}
            ],
            webhook_url=webhook_url
        )

    def send_system_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "error",
        webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send system alert"""
        return self.send_alert(
            title=f"System Alert: {alert_type}",
            message=message,
            severity=severity,
            webhook_url=webhook_url
        )

    def send_enrollment_notification(
        self,
        student_name: str,
        course_code: str,
        course_name: str,
        webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send course enrollment notification"""
        return self.send_alert(
            title="New Enrollment",
            message=f"{student_name} enrolled in {course_code} - {course_name}",
            severity="info",
            facts=[
                {"name": "Student", "value": student_name},
                {"name": "Course", "value": f"{course_code} - {course_name}"}
            ],
            webhook_url=webhook_url
        )

    def send_grade_posted_notification(
        self,
        course_code: str,
        assignment_name: str,
        student_count: int,
        webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send grade posted notification"""
        return self.send_alert(
            title="Grades Posted",
            message=f"{assignment_name} for {course_code}",
            severity="info",
            facts=[
                {"name": "Course", "value": course_code},
                {"name": "Assignment", "value": assignment_name},
                {"name": "Students", "value": str(student_count)}
            ],
            webhook_url=webhook_url
        )

    def send_actionable_message(
        self,
        title: str,
        message: str,
        actions: List[Dict[str, str]],
        webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send message with action buttons

        Args:
            title: Message title
            message: Message text
            actions: List of actions [{'name': 'View', 'url': 'https://...'}]
            webhook_url: Optional webhook URL

        Returns:
            Result dictionary
        """
        url = webhook_url or self.webhook_url

        if not url:
            return {
                'success': False,
                'error': 'Teams webhook URL not configured'
            }

        # Build potential actions
        potential_actions = []
        for action in actions:
            potential_actions.append({
                "@type": "OpenUri",
                "name": action.get('name', 'View'),
                "targets": [{
                    "os": "default",
                    "uri": action.get('url', '#')
                }]
            })

        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": title,
            "themeColor": "0078D7",
            "title": title,
            "text": message,
            "potentialAction": potential_actions
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )

            if response.status_code == 200:
                logger.info(f"Sent Teams actionable message: {title}")
                return {
                    'success': True,
                    'status_code': response.status_code
                }
            else:
                logger.error(f"Teams API error: {response.status_code}")
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}"
                }

        except Exception as e:
            logger.error(f"Error sending Teams message: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Singleton instance
_teams_notifier: Optional[TeamsNotifier] = None


def get_teams_notifier() -> TeamsNotifier:
    """Get or create Teams notifier singleton"""
    global _teams_notifier
    if _teams_notifier is None:
        _teams_notifier = TeamsNotifier()
    return _teams_notifier
