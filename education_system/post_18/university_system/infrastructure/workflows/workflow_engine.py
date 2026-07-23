"""
Core workflow execution engine
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from education_system.post_18.university_system.infrastructure.workflows.models import (
    Workflow,
    WorkflowStep,
    WorkflowInstance,
    WorkflowStatus,
    ApprovalStatus,
    ApprovalRequest,
    StepType,
)
from education_system.post_18.university_system.infrastructure.workflows.database import WorkflowDatabase

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Core workflow execution engine

    Manages workflow lifecycle:
    - Workflow definition and registration
    - Workflow instance creation and execution
    - Step progression and approval routing
    - Context management
    - Error handling and recovery
    """

    def __init__(self, db: Optional[WorkflowDatabase] = None):
        """Initialize workflow engine"""
        self.db = db or WorkflowDatabase()
        self.workflows: Dict[str, Workflow] = {}
        self.instances: Dict[str, WorkflowInstance] = {}
        self._load_workflows()

    def _load_workflows(self) -> None:
        """Load workflows from database"""
        try:
            workflows = self.db.get_all_workflows()
            for workflow in workflows:
                self.workflows[workflow.workflow_id] = workflow
            logger.info(f"Loaded {len(workflows)} workflows")
        except Exception as e:
            logger.error(f"Error loading workflows: {e}")

    def define_workflow(
        self,
        name: str,
        steps: List[WorkflowStep],
        description: str = "",
        category: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Workflow:
        """
        Define a new workflow

        Args:
            name: Workflow name
            steps: List of workflow steps
            description: Workflow description
            category: Workflow category
            created_by: User who created the workflow

        Returns:
            Workflow object
        """
        workflow_id = str(uuid.uuid4())
        workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            description=description,
            steps=steps,
            created_by=created_by,
            created_at=datetime.utcnow(),
            category=category
        )

        # Validate workflow
        self._validate_workflow(workflow)

        # Save to database
        self.db.save_workflow(workflow)
        self.workflows[workflow_id] = workflow

        logger.info(f"Defined workflow: {name} (ID: {workflow_id})")
        return workflow

    def _validate_workflow(self, workflow: Workflow) -> None:
        """Validate workflow definition"""
        if not workflow.steps:
            raise ValueError("Workflow must have at least one step")

        # Check for duplicate step IDs
        step_ids = [s.step_id for s in workflow.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Duplicate step IDs found")

        # Check for duplicate orders
        orders = [s.order for s in workflow.steps]
        if len(orders) != len(set(orders)):
            raise ValueError("Duplicate step orders found")

    def start_workflow(
        self,
        workflow_id: str,
        context: Dict[str, Any],
        initiated_by: Optional[str] = None
    ) -> WorkflowInstance:
        """
        Start a new workflow instance

        Args:
            workflow_id: ID of workflow to start
            context: Initial context data
            initiated_by: User who initiated the workflow

        Returns:
            WorkflowInstance object
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        instance_id = str(uuid.uuid4())
        instance = WorkflowInstance(
            instance_id=instance_id,
            workflow_id=workflow_id,
            workflow_name=workflow.name,
            status=WorkflowStatus.PENDING,
            context=context,
            initiated_by=initiated_by,
            initiated_at=datetime.utcnow()
        )

        # Save to database
        self.db.save_instance(instance)
        self.instances[instance_id] = instance

        logger.info(f"Started workflow instance: {instance_id} for workflow: {workflow.name}")

        # Start execution
        self._execute_next_step(instance, workflow)

        return instance

    def execute_workflow(
        self,
        workflow_id: str,
        context: Dict[str, Any],
        initiated_by: Optional[str] = None
    ) -> WorkflowStatus:
        """
        Execute a workflow (convenience method that starts and executes)

        Args:
            workflow_id: ID of workflow to execute
            context: Initial context data
            initiated_by: User who initiated the workflow

        Returns:
            Final workflow status
        """
        instance = self.start_workflow(workflow_id, context, initiated_by)
        return instance.status

    def _execute_next_step(
        self,
        instance: WorkflowInstance,
        workflow: Workflow
    ) -> None:
        """Execute the next step in the workflow"""
        next_step = workflow.get_next_step(instance.current_step_id)

        if not next_step:
            # Workflow complete
            self._complete_workflow(instance)
            return

        instance.current_step_id = next_step.step_id
        instance.status = WorkflowStatus.IN_PROGRESS

        logger.info(
            f"Executing step: {next_step.name} (ID: {next_step.step_id}) "
            f"for instance: {instance.instance_id}"
        )

        # Execute step based on type
        if next_step.step_type == StepType.APPROVAL:
            self._execute_approval_step(instance, next_step)
        elif next_step.step_type == StepType.AUTOMATED:
            self._execute_automated_step(instance, next_step, workflow)
        elif next_step.step_type == StepType.CONDITIONAL:
            self._execute_conditional_step(instance, next_step, workflow)
        elif next_step.step_type == StepType.NOTIFICATION:
            self._execute_notification_step(instance, next_step, workflow)
        else:
            logger.warning(f"Unsupported step type: {next_step.step_type}")
            # Skip and continue
            instance.add_step_result(next_step.step_id, ApprovalStatus.SKIPPED)
            self._execute_next_step(instance, workflow)

        # Update instance in database
        self.db.update_instance(instance)

    def _execute_approval_step(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep
    ) -> None:
        """Execute an approval step"""
        if not step.approver:
            raise ValueError(f"Approval step {step.step_id} has no approver")

        # Check if criteria are met
        if step.criteria:
            criteria_met = self._evaluate_criteria(instance.context, step.criteria)
            if not criteria_met and not step.required:
                # Skip optional step if criteria not met
                logger.info(f"Skipping optional approval step: {step.step_id}")
                instance.add_step_result(step.step_id, ApprovalStatus.SKIPPED)
                workflow = self.workflows[instance.workflow_id]
                self._execute_next_step(instance, workflow)
                return

        # Create approval request
        request_id = str(uuid.uuid4())
        due_date = None
        if step.timeout_hours:
            due_date = datetime.utcnow() + timedelta(hours=step.timeout_hours)

        approval_request = ApprovalRequest(
            request_id=request_id,
            instance_id=instance.instance_id,
            workflow_name=instance.workflow_name,
            step_id=step.step_id,
            step_name=step.name,
            approver=step.approver,
            context=instance.context,
            created_at=datetime.utcnow(),
            due_date=due_date
        )

        # Save approval request
        self.db.save_approval_request(approval_request)

        # Send notification to approver
        self._notify_approver(approval_request)

        logger.info(
            f"Created approval request: {request_id} for approver: {step.approver}"
        )

    def _execute_automated_step(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        workflow: Workflow
    ) -> None:
        """Execute an automated step"""
        try:
            if step.action:
                # Execute the action with context
                result = step.action(instance.context)
                # Update context with result
                if isinstance(result, dict):
                    instance.context.update(result)

            instance.add_step_result(step.step_id, ApprovalStatus.APPROVED)
            self._execute_next_step(instance, workflow)

        except Exception as e:
            logger.error(f"Error executing automated step {step.step_id}: {e}")
            instance.status = WorkflowStatus.ERROR
            instance.error_message = str(e)
            self.db.update_instance(instance)

    def _execute_conditional_step(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        workflow: Workflow
    ) -> None:
        """Execute a conditional step"""
        if step.condition:
            condition_met = step.condition(instance.context)
            if condition_met:
                instance.add_step_result(step.step_id, ApprovalStatus.APPROVED)
            else:
                instance.add_step_result(step.step_id, ApprovalStatus.SKIPPED)
        else:
            instance.add_step_result(step.step_id, ApprovalStatus.SKIPPED)

        self._execute_next_step(instance, workflow)

    def _execute_notification_step(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        workflow: Workflow
    ) -> None:
        """Execute a notification step"""
        # Send notification (integrate with notification service if available)
        try:
            from education_system.post_18.university_system.infrastructure.communication.realtime_notifications import get_notification_service
            notification_service = get_notification_service()

            if step.approver:  # approver field used as recipient
                # Send notification
                # This is a placeholder - would need async context in real impl
                pass

        except ImportError:
            logger.warning("Notification service not available")

        instance.add_step_result(step.step_id, ApprovalStatus.APPROVED)
        self._execute_next_step(instance, workflow)

    def _evaluate_criteria(
        self,
        context: Dict[str, Any],
        criteria: Dict[str, Any]
    ) -> bool:
        """Evaluate criteria against context"""
        for key, expected_value in criteria.items():
            actual_value = context.get(key)

            # Simple evaluation - can be enhanced with operators
            if isinstance(expected_value, str) and expected_value.startswith(">="):
                threshold = float(expected_value[2:].strip())
                if actual_value is None or float(actual_value) < threshold:
                    return False
            elif isinstance(expected_value, str) and expected_value.startswith("<="):
                threshold = float(expected_value[2:].strip())
                if actual_value is None or float(actual_value) > threshold:
                    return False
            elif actual_value != expected_value:
                return False

        return True

    def approve_step(
        self,
        instance_id: str,
        step_id: str,
        approver: str,
        comments: Optional[str] = None
    ) -> WorkflowInstance:
        """Approve a workflow step"""
        instance = self.instances.get(instance_id)
        if not instance:
            instance = self.db.get_instance(instance_id)
            if not instance:
                raise ValueError(f"Workflow instance not found: {instance_id}")

        if instance.current_step_id != step_id:
            raise ValueError(f"Step {step_id} is not the current step")

        # Record approval
        instance.add_step_result(step_id, ApprovalStatus.APPROVED, approver, comments)

        # Update approval request
        self.db.update_approval_request(instance_id, step_id, ApprovalStatus.APPROVED, approver, comments)

        # Continue to next step
        workflow = self.workflows[instance.workflow_id]
        self._execute_next_step(instance, workflow)

        return instance

    def reject_step(
        self,
        instance_id: str,
        step_id: str,
        approver: str,
        comments: Optional[str] = None
    ) -> WorkflowInstance:
        """Reject a workflow step"""
        instance = self.instances.get(instance_id)
        if not instance:
            instance = self.db.get_instance(instance_id)
            if not instance:
                raise ValueError(f"Workflow instance not found: {instance_id}")

        # Record rejection
        instance.add_step_result(step_id, ApprovalStatus.REJECTED, approver, comments)
        instance.status = WorkflowStatus.REJECTED

        # Update approval request
        self.db.update_approval_request(instance_id, step_id, ApprovalStatus.REJECTED, approver, comments)

        # Update instance
        self.db.update_instance(instance)

        logger.info(f"Workflow instance {instance_id} rejected at step {step_id}")
        return instance

    def _complete_workflow(self, instance: WorkflowInstance) -> None:
        """Complete a workflow instance"""
        instance.status = WorkflowStatus.COMPLETED
        instance.completed_at = datetime.utcnow()
        instance.result = {'status': 'success', 'context': instance.context}

        self.db.update_instance(instance)

        logger.info(
            f"Workflow instance {instance.instance_id} completed in "
            f"{instance.get_elapsed_time():.2f} hours"
        )

    def _notify_approver(self, request: ApprovalRequest) -> None:
        """Send notification to approver"""
        # Integrate with notification service
        try:
            from education_system.post_18.university_system.infrastructure.communication.realtime_notifications import get_notification_service
            # Would send real-time notification here
            logger.info(f"Notification sent to approver: {request.approver}")
        except ImportError:
            logger.warning("Notification service not available")

    def get_pending_approvals(self, approver: str) -> List[ApprovalRequest]:
        """Get pending approvals for an approver"""
        return self.db.get_pending_approvals(approver)

    def get_workflow_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        """Get a workflow instance by ID"""
        instance = self.instances.get(instance_id)
        if not instance:
            instance = self.db.get_instance(instance_id)
        return instance

    def cancel_workflow(self, instance_id: str, reason: Optional[str] = None) -> None:
        """Cancel a running workflow"""
        instance = self.get_workflow_instance(instance_id)
        if not instance:
            raise ValueError(f"Workflow instance not found: {instance_id}")

        instance.status = WorkflowStatus.CANCELLED
        instance.error_message = reason
        instance.completed_at = datetime.utcnow()

        self.db.update_instance(instance)
        logger.info(f"Workflow instance {instance_id} cancelled: {reason}")


# Singleton instance
_workflow_engine: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    """Get the global workflow engine instance"""
    global _workflow_engine
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
    return _workflow_engine
