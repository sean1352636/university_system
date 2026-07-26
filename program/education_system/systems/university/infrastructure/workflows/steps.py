"""
Workflow step implementations
"""

from typing import Dict, Any, Callable, Optional, List
from education_system.systems.university.infrastructure.workflows.models import WorkflowStep, StepType


class ApprovalStep(WorkflowStep):
    """
    Approval step requiring human decision

    Example:
        step = ApprovalStep(
            step_id="dept_head_approval",
            name="Department Head Approval",
            order=1,
            approver="department_head",
            criteria={"gpa": ">= 3.5"},
            timeout_hours=48
        )
    """

    def __init__(
        self,
        step_id: str,
        name: str,
        order: int,
        approver: str,
        description: str = "",
        criteria: Optional[Dict[str, Any]] = None,
        timeout_hours: Optional[int] = None,
        escalation_target: Optional[str] = None,
        required: bool = True
    ):
        super().__init__(
            step_id=step_id,
            name=name,
            step_type=StepType.APPROVAL,
            order=order,
            description=description,
            approver=approver,
            criteria=criteria,
            timeout_hours=timeout_hours,
            escalation_target=escalation_target,
            required=required
        )


class AutomatedStep(WorkflowStep):
    """
    Automated step that executes a function

    Example:
        def calculate_scholarship_amount(context):
            gpa = context['gpa']
            if gpa >= 4.0:
                return {'amount': 10000}
            elif gpa >= 3.5:
                return {'amount': 5000}
            return {'amount': 2500}

        step = AutomatedStep(
            step_id="calculate_amount",
            name="Calculate Scholarship Amount",
            order=2,
            action=calculate_scholarship_amount
        )
    """

    def __init__(
        self,
        step_id: str,
        name: str,
        order: int,
        action: Callable[[Dict[str, Any]], Dict[str, Any]],
        description: str = "",
        required: bool = True
    ):
        super().__init__(
            step_id=step_id,
            name=name,
            step_type=StepType.AUTOMATED,
            order=order,
            description=description,
            action=action,
            required=required
        )


class ConditionalStep(WorkflowStep):
    """
    Conditional step that evaluates a condition

    Example:
        def check_financial_need(context):
            return context.get('income', 0) < 50000

        step = ConditionalStep(
            step_id="check_need",
            name="Check Financial Need",
            order=1,
            condition=check_financial_need
        )
    """

    def __init__(
        self,
        step_id: str,
        name: str,
        order: int,
        condition: Callable[[Dict[str, Any]], bool],
        description: str = "",
        required: bool = True
    ):
        super().__init__(
            step_id=step_id,
            name=name,
            step_type=StepType.CONDITIONAL,
            order=order,
            description=description,
            condition=condition,
            required=required
        )


class ParallelStep(WorkflowStep):
    """
    Step that executes multiple substeps in parallel

    Example:
        step = ParallelStep(
            step_id="parallel_approvals",
            name="Parallel Department Approvals",
            order=2,
            parallel_steps=["cs_dept_approval", "math_dept_approval"]
        )
    """

    def __init__(
        self,
        step_id: str,
        name: str,
        order: int,
        parallel_steps: List[str],
        description: str = "",
        required: bool = True
    ):
        super().__init__(
            step_id=step_id,
            name=name,
            step_type=StepType.PARALLEL,
            order=order,
            description=description,
            parallel_steps=parallel_steps,
            required=required
        )


class NotificationStep(WorkflowStep):
    """
    Step that sends a notification

    Example:
        step = NotificationStep(
            step_id="notify_student",
            name="Notify Student of Decision",
            order=10,
            approver="student_id_from_context",  # recipient
            message_template="Your application has been {status}"
        )
    """

    def __init__(
        self,
        step_id: str,
        name: str,
        order: int,
        approver: str,  # Used as recipient
        message_template: str = "",
        description: str = "",
        required: bool = False
    ):
        super().__init__(
            step_id=step_id,
            name=name,
            step_type=StepType.NOTIFICATION,
            order=order,
            description=description,
            approver=approver,
            criteria={'message_template': message_template},
            required=required
        )


class ManualStep(WorkflowStep):
    """
    Manual step requiring human intervention without approval

    Example:
        step = ManualStep(
            step_id="document_review",
            name="Review Documents",
            order=1,
            assignee="admin",
            checklist=["Verify ID", "Check transcripts"]
        )
    """

    def __init__(
        self,
        step_id: str,
        name: str,
        order: int,
        assignee: str,
        checklist: Optional[List[str]] = None,
        description: str = "",
        timeout_hours: Optional[int] = None,
        required: bool = True
    ):
        super().__init__(
            step_id=step_id,
            name=name,
            step_type=StepType.MANUAL,
            order=order,
            description=description,
            approver=assignee,
            criteria={'checklist': checklist or []},
            timeout_hours=timeout_hours,
            required=required
        )


class IntegrationStep(WorkflowStep):
    """
    Integration step that calls external service

    Example:
        def call_payment_gateway(context):
            amount = context['amount']
            # Call external payment service
            return {'payment_id': 'PAY-123', 'status': 'completed'}

        step = IntegrationStep(
            step_id="process_payment",
            name="Process Payment",
            order=5,
            integration_function=call_payment_gateway,
            retry_count=3
        )
    """

    def __init__(
        self,
        step_id: str,
        name: str,
        order: int,
        integration_function: Callable[[Dict[str, Any]], Dict[str, Any]],
        description: str = "",
        retry_count: int = 1,
        timeout_hours: Optional[int] = None,
        required: bool = True
    ):
        super().__init__(
            step_id=step_id,
            name=name,
            step_type=StepType.INTEGRATION,
            order=order,
            description=description,
            action=integration_function,
            criteria={'retry_count': retry_count},
            timeout_hours=timeout_hours,
            required=required
        )
