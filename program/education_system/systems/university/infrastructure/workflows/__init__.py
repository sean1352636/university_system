"""
Workflow Automation Engine

This module provides a comprehensive workflow automation system for managing
multi-step approval processes and automated tasks across the university.

Features:
- Dynamic workflow definition with visual DSL
- Multi-step approval routing with role-based assignments
- Conditional logic and branching
- Automated task execution
- Real-time workflow monitoring and notifications
- Workflow templates for common processes
- Analytics and performance tracking
- Audit trail for compliance

Common Use Cases:
- Scholarship applications
- Leave requests
- Grade appeals
- Budget approvals
- Course creation requests
- Facility booking approvals
- Research grant applications
"""

from education_system.systems.university.infrastructure.workflows.workflow_engine import (
    WorkflowEngine,
    get_workflow_engine,
)

from education_system.systems.university.infrastructure.workflows.models import (
    Workflow,
    WorkflowStep,
    WorkflowInstance,
    WorkflowStatus,
    StepType,
    ApprovalStatus,
)

from education_system.systems.university.infrastructure.workflows.steps import (
    ApprovalStep,
    AutomatedStep,
    ConditionalStep,
    ParallelStep,
    NotificationStep,
)

from education_system.systems.university.infrastructure.workflows.templates import (
    WorkflowTemplates,
    create_scholarship_workflow,
    create_leave_request_workflow,
    create_grade_appeal_workflow,
    create_course_approval_workflow,
    create_budget_approval_workflow,
    get_workflow_template,
)

from education_system.systems.university.infrastructure.workflows.monitoring import (
    WorkflowMonitor,
    WorkflowAnalytics,
    get_workflow_monitor,
    get_workflow_analytics,
)

__all__ = [
    # Core engine
    'WorkflowEngine',
    'get_workflow_engine',

    # Models
    'Workflow',
    'WorkflowStep',
    'WorkflowInstance',
    'WorkflowStatus',
    'StepType',
    'ApprovalStatus',

    # Step types
    'ApprovalStep',
    'AutomatedStep',
    'ConditionalStep',
    'ParallelStep',
    'NotificationStep',

    # Templates
    'WorkflowTemplates',
    'create_scholarship_workflow',
    'create_leave_request_workflow',
    'create_grade_appeal_workflow',
    'create_course_approval_workflow',
    'create_budget_approval_workflow',
    'get_workflow_template',

    # Monitoring
    'WorkflowMonitor',
    'WorkflowAnalytics',
    'get_workflow_monitor',
    'get_workflow_analytics',
]
