

# Workflow Automation Engine

A comprehensive workflow automation system for managing multi-step approval processes and automated tasks across the university.

## Overview

The Workflow Automation Engine provides a flexible, code-based approach to defining and executing complex approval workflows. It includes built-in templates for common university processes, real-time monitoring, and comprehensive analytics.

### Key Features

- **Dynamic Workflow Definition** - Create workflows programmatically with Python
- **Multi-Step Approval Routing** - Route approvals to different roles/users
- **Conditional Logic** - Skip or execute steps based on context data
- **Automated Steps** - Execute functions automatically during workflow
- **Parallel Execution** - Run multiple approval steps simultaneously
- **Real-time Notifications** - Integrated with notification service
- **Workflow Templates** - Pre-built workflows for common processes
- **Monitoring Dashboard** - Track active workflows, pending approvals, bottlenecks
- **Analytics** - Completion rates, processing times, approval patterns
- **Audit Trail** - Complete history of all workflow actions

## Architecture

```
workflows/
├── __init__.py              # Package exports
├── models.py                # Data models and enums
├── workflow_engine.py       # Core execution engine
├── steps.py                 # Step type implementations
├── templates.py             # Pre-built workflow templates
├── database.py              # Database operations
├── monitoring.py            # Monitoring and analytics
└── README.md                # This file
```

## Quick Start

### 1. Using Templates

```python
from university_system.infrastructure.workflows import (
    get_workflow_engine,
    create_scholarship_workflow
)

# Get the workflow engine
engine = get_workflow_engine()

# Create a scholarship workflow from template
workflow = create_scholarship_workflow()

# Save to database
engine.db.save_workflow(workflow)

# Start a workflow instance
instance = engine.start_workflow(
    workflow_id=workflow.workflow_id,
    context={
        'student_id': 'STU001',
        'gpa': 3.8,
        'financial_need': 60000
    },
    initiated_by='admin'
)

print(f"Workflow started: {instance.instance_id}")
print(f"Status: {instance.status.value}")
```

### 2. Creating Custom Workflows

```python
from university_system.infrastructure.workflows import (
    Workflow,
    ApprovalStep,
    AutomatedStep,
    ConditionalStep,
)

# Define workflow
workflow = Workflow(
    workflow_id="custom_workflow",
    name="My Custom Workflow",
    description="Custom approval process"
)

# Add steps
workflow.add_step(ApprovalStep(
    step_id="step1",
    name="Manager Approval",
    order=1,
    approver="manager",
    timeout_hours=24
))

workflow.add_step(AutomatedStep(
    step_id="step2",
    name="Process Application",
    order=2,
    action=lambda ctx: {'processed': True}
))

# Save and execute
engine.db.save_workflow(workflow)
instance = engine.start_workflow(
    workflow_id=workflow.workflow_id,
    context={'applicant': 'John Doe'}
)
```

### 3. Handling Approvals

```python
# Get pending approvals
pending = engine.get_pending_approvals('department_head')

for approval in pending:
    print(f"Workflow: {approval.workflow_name}")
    print(f"Step: {approval.step_name}")

# Approve a step
engine.approve_step(
    instance_id=instance.instance_id,
    step_id='step1',
    approver='department_head',
    comments='Approved'
)

# Or reject
engine.reject_step(
    instance_id=instance.instance_id,
    step_id='step1',
    approver='department_head',
    comments='Does not meet criteria'
)
```

## Pre-Built Templates

### Scholarship Application

Multi-step approval for scholarship applications with GPA checks and financial aid review.

```python
from university_system.infrastructure.workflows import create_scholarship_workflow

workflow = create_scholarship_workflow()

# Steps:
# 1. Automated GPA eligibility check
# 2. GPA gate (conditional)
# 3. Department head approval
# 4. Financial aid office review
# 5. Calculate award amount (automated)
# 6. Dean's final approval
# 7. Notify student
```

### Leave Request

Employee leave request approval with conditional steps based on duration.

```python
from university_system.infrastructure.workflows import create_leave_request_workflow

workflow = create_leave_request_workflow()

# Steps:
# 1. Supervisor approval
# 2. HR review (if >= 5 days)
# 3. Department head approval (if >= 10 days)
# 4. Update leave balance (automated)
# 5. Notify employee
```

### Grade Appeal

Student grade appeal review process with escalation.

```python
from university_system.infrastructure.workflows import create_grade_appeal_workflow

workflow = create_grade_appeal_workflow()

# Steps:
# 1. Instructor review
# 2. Department chair review
# 3. Academic dean review (escalation)
# 4. Update grade if approved (automated)
# 5. Notify student
```

### Course Approval

New course creation approval through curriculum committee.

```python
from university_system.infrastructure.workflows import create_course_approval_workflow

workflow = create_course_approval_workflow()

# Steps:
# 1. Department review
# 2. Curriculum committee review
# 3. Academic dean approval
# 4. Provost approval (if cross-departmental)
# 5. Create course in system (automated)
```

### Budget Approval

Budget request approval with thresholds.

```python
from university_system.infrastructure.workflows import create_budget_approval_workflow

workflow = create_budget_approval_workflow()

# Steps:
# 1. Department review
# 2. Finance office review
# 3. Budget committee approval
# 4. CFO approval (if >= $50k)
# 5. Process budget allocation (automated)
```

## Step Types

### ApprovalStep

Requires human approval decision.

```python
ApprovalStep(
    step_id="dept_approval",
    name="Department Head Approval",
    order=1,
    approver="department_head",
    criteria={"gpa": ">= 3.5"},
    timeout_hours=48,
    escalation_target="dean"
)
```

### AutomatedStep

Executes a function automatically.

```python
def calculate_discount(context):
    amount = context['amount']
    return {'discount': amount * 0.1}

AutomatedStep(
    step_id="calc_discount",
    name="Calculate Discount",
    order=2,
    action=calculate_discount
)
```

### ConditionalStep

Evaluates a condition to determine if workflow should continue.

```python
def check_eligibility(context):
    return context.get('score', 0) >= 70

ConditionalStep(
    step_id="eligibility_check",
    name="Check Eligibility",
    order=1,
    condition=check_eligibility
)
```

### NotificationStep

Sends a notification to a user.

```python
NotificationStep(
    step_id="notify",
    name="Notify Student",
    order=10,
    approver="student_id",  # recipient
    message_template="Your application status: {status}"
)
```

## Monitoring

### System Health

```python
from university_system.infrastructure.workflows import get_workflow_monitor

monitor = get_workflow_monitor()
health = monitor.get_workflow_health()

print(f"Active workflows: {health['active_workflows']}")
print(f"Completed today: {health['completed_today']}")
print(f"Error count: {health['error_count']}")
print(f"Health score: {health['health_score']}")
```

### Active Workflows

```python
active = monitor.get_active_workflows()

for workflow in active:
    print(f"{workflow['workflow_name']}: {workflow['status']}")
```

### Overdue Approvals

```python
overdue = monitor.get_overdue_approvals()

for approval in overdue:
    print(f"Workflow: {approval['workflow_name']}")
    print(f"Approver: {approval['approver']}")
    print(f"Days overdue: {approval['days_overdue']}")
```

### Bottleneck Detection

```python
bottlenecks = monitor.identify_bottlenecks(threshold_hours=48)

for bottleneck in bottlenecks:
    print(f"Step: {bottleneck['step_name']}")
    print(f"Stuck for: {bottleneck['hours_stuck']:.1f} hours")
```

## Analytics

### Completion Rate

```python
from university_system.infrastructure.workflows import get_workflow_analytics

analytics = get_workflow_analytics()

# Overall completion rate
rate = analytics.get_completion_rate(days=30)
print(f"Completion rate: {rate:.1f}%")

# Specific workflow
rate = analytics.get_completion_rate(
    workflow_id="template_scholarship",
    days=30
)
```

### Processing Time

```python
avg_time = analytics.get_average_completion_time(days=30)
print(f"Average time: {avg_time:.1f} hours")
```

### Approver Patterns

```python
patterns = analytics.get_approval_patterns("department_head", days=30)

print(f"Total requests: {patterns['total_requests']}")
print(f"Approval rate: {patterns['approval_rate']:.1f}%")
print(f"Avg decision time: {patterns['average_decision_time_hours']:.1f} hours")
```

### Comprehensive Statistics

```python
stats = analytics.get_workflow_statistics(days=30)

print(f"Total instances: {stats['total_instances']}")
print(f"Completion rate: {stats['completion_rate']:.1f}%")
print(f"Trend: {stats['trend']}")  # improving/declining/stable
```

## API Endpoints

### Start Workflow

```http
POST /api/v1/workflows/start
Content-Type: application/json

{
    "workflow_id": "template_scholarship",
    "context": {
        "student_id": "STU001",
        "gpa": 3.8
    },
    "initiated_by": "admin"
}
```

### Approve Step

```http
POST /api/v1/workflows/{instance_id}/approve
Content-Type: application/json

{
    "instance_id": "abc-123",
    "step_id": "dept_head_approval",
    "approver": "john.smith",
    "comments": "Approved"
}
```

### Get Pending Approvals

```http
GET /api/v1/workflows/approvals/pending?approver=department_head
```

### Get Workflow Health

```http
GET /api/v1/workflows/monitoring/health
```

### Get Analytics

```http
GET /api/v1/workflows/analytics/completion-rate?days=30
GET /api/v1/workflows/analytics/avg-time?days=30
GET /api/v1/workflows/analytics/approver/department_head?days=30
```

See full API documentation at `/docs` when server is running.

## Database Schema

The workflow engine uses SQLite with the following tables:

- **workflows** - Workflow definitions
- **workflow_instances** - Workflow execution instances
- **approval_requests** - Pending and completed approval requests
- **workflow_audit_log** - Complete audit trail

Tables are automatically created on first use.

## Best Practices

### 1. Use Templates

Start with built-in templates and customize as needed:

```python
workflow = create_scholarship_workflow()
# Modify steps if needed
workflow.steps[0].timeout_hours = 72
```

### 2. Meaningful Step IDs

Use descriptive step IDs for debugging:

```python
# Good
ApprovalStep(step_id="dept_head_approval", ...)

# Bad
ApprovalStep(step_id="step1", ...)
```

### 3. Set Timeouts

Always set timeout_hours for approval steps:

```python
ApprovalStep(
    step_id="approval",
    timeout_hours=48,  # Alert if not approved within 48 hours
    escalation_target="manager"
)
```

### 4. Add Descriptions

Document what each step does:

```python
ApprovalStep(
    step_id="review",
    name="Technical Review",
    description="Engineering team reviews technical feasibility and resource requirements"
)
```

### 5. Handle Errors

Wrap workflow operations in try/except:

```python
try:
    instance = engine.start_workflow(workflow_id, context)
except ValueError as e:
    logger.error(f"Failed to start workflow: {e}")
```

### 6. Monitor Regularly

Set up monitoring dashboards:

```python
# Check health every hour
health = monitor.get_workflow_health()
if health['health_score'] < 70:
    alert_admin()
```

### 7. Use Context Wisely

Pass all necessary data in context:

```python
context = {
    'student_id': 'STU001',
    'student_name': 'Alice',  # For display
    'gpa': 3.8,
    'financial_need': 60000,
    'email': 'alice@university.edu'  # For notifications
}
```

## Examples

See `examples/workflow_demo.py` for comprehensive examples of:

- Creating and using workflow templates
- Handling approvals
- Monitoring active workflows
- Analyzing workflow performance
- Detecting bottlenecks

## Troubleshooting

### Workflow Not Progressing

Check pending approvals:

```python
pending = engine.get_pending_approvals(approver)
print(f"Pending: {len(pending)}")
```

### Approval Timeout

Check overdue approvals:

```python
overdue = monitor.get_overdue_approvals()
for approval in overdue:
    # Send reminder or escalate
    pass
```

### High Error Count

Check workflow instances with errors:

```python
with get_connection() as conn:
    cursor = conn.execute('''
        SELECT instance_id, workflow_name, error_message
        FROM workflow_instances
        WHERE status = 'error'
    ''')
    errors = cursor.fetchall()
```

## Integration

### With Real-time Notifications

Workflow engine automatically integrates with the notification service:

```python
# Notifications sent automatically for:
# - Pending approvals
# - Workflow completion
# - Approval rejections
# - Timeout warnings
```

### With Email Service

Integrate email notifications:

```python
from university_system.infrastructure.email import get_email_service

def notify_approver(approval_request):
    email_service = get_email_service()
    email_service.send_email(
        to=approval_request.approver_email,
        subject=f"Approval Required: {approval_request.workflow_name}",
        body=render_approval_template(approval_request)
    )
```

## Performance

- **Database**: SQLite with WAL mode for concurrent access
- **Indexes**: Optimized for common queries (status, approver, dates)
- **Caching**: Workflow definitions cached in memory
- **Scalability**: Handles 1000s of concurrent workflows

## Security

- **Permission Checks**: Verify approver identity before accepting decisions
- **Audit Trail**: Complete history of all actions
- **Data Encryption**: Context data can be encrypted at rest
- **Access Control**: Role-based workflow visibility

## License

MIT License - See project root for details.

## Support

For issues or questions:
1. Check this documentation
2. See `examples/workflow_demo.py`
3. Review API docs at `/docs`
4. Check GitHub issues

---

**Version**: 1.0.0
**Last Updated**: 2025-02-01
