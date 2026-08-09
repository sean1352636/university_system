"""Data model classes for enhanced reporting."""

from datetime import datetime


class ReportTemplate:
    """Enhanced report template with new features"""

    def __init__(self, name, description, sections, filters=None,
                 visualization_type='standard', schedule_config=None,
                 security_level='normal', custom_sql=None):
        self.name = name
        self.description = description
        self.sections = sections
        self.filters = filters or {}
        self.visualization_type = visualization_type  # 'standard', 'interactive', 'advanced'
        self.schedule_config = schedule_config or {}
        self.security_level = security_level  # 'normal', 'confidential', 'restricted'
        self.custom_sql = custom_sql or {}
        self.created_at = datetime.now().isoformat()
        self.version = "1.0"

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "sections": self.sections,
            "filters": self.filters,
            "visualization_type": self.visualization_type,
            "schedule_config": self.schedule_config,
            "security_level": self.security_level,
            "custom_sql": self.custom_sql,
            "created_at": self.created_at,
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data):
        template = cls(
            name=data["name"],
            description=data["description"],
            sections=data["sections"],
            filters=data.get("filters", {}),
            visualization_type=data.get("visualization_type", "standard"),
            schedule_config=data.get("schedule_config", {}),
            security_level=data.get("security_level", "normal"),
            custom_sql=data.get("custom_sql", {})
        )
        template.created_at = data.get("created_at", datetime.now().isoformat())
        template.version = data.get("version", "1.0")
        return template


class AdvancedScheduledReport:
    """Enhanced scheduled report with advanced features"""

    def __init__(self, template_name, schedule_config, recipients=None,
                 conditions=None, next_run=None):
        self.template_name = template_name
        self.schedule_config = schedule_config  # Complex scheduling configuration
        self.recipients = recipients or []
        self.conditions = conditions or {}  # Conditional execution rules
        self.next_run = next_run or datetime.now().isoformat()
        self.created_at = datetime.now().isoformat()
        self.last_run = None
        self.run_count = 0
        self.is_active = True

    def to_dict(self):
        return {
            "template_name": self.template_name,
            "schedule_config": self.schedule_config,
            "recipients": self.recipients,
            "conditions": self.conditions,
            "next_run": self.next_run,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "run_count": self.run_count,
            "is_active": self.is_active
        }

    @classmethod
    def from_dict(cls, data):
        report = cls(
            template_name=data["template_name"],
            schedule_config=data["schedule_config"],
            recipients=data.get("recipients", []),
            conditions=data.get("conditions", {}),
            next_run=data.get("next_run")
        )
        report.created_at = data.get("created_at", datetime.now().isoformat())
        report.last_run = data.get("last_run")
        report.run_count = data.get("run_count", 0)
        report.is_active = data.get("is_active", True)
        return report
