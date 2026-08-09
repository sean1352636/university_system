"""
Workflow data models and enums
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime


class WorkflowStatus(Enum):
    """Status of a workflow instance"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"
    ERROR = "error"


class StepType(Enum):
    """Type of workflow step"""
    APPROVAL = "approval"
    AUTOMATED = "automated"
    CONDITIONAL = "conditional"
    PARALLEL = "parallel"
    NOTIFICATION = "notification"
    MANUAL = "manual"
    INTEGRATION = "integration"


class ApprovalStatus(Enum):
    """Status of an approval step"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DELEGATED = "delegated"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    """Represents a single step in a workflow"""
    step_id: str
    name: str
    step_type: StepType
    order: int
    description: str = ""
    approver: Optional[str] = None  # Role or user ID
    criteria: Optional[Dict[str, Any]] = None
    timeout_hours: Optional[int] = None
    escalation_target: Optional[str] = None
    parallel_steps: List[str] = field(default_factory=list)
    condition: Optional[Callable] = None
    action: Optional[Callable] = None
    required: bool = True

    def __post_init__(self):
        if self.criteria is None:
            self.criteria = {}


@dataclass
class Workflow:
    """Represents a workflow definition"""
    workflow_id: str
    name: str
    description: str
    version: str = "1.0"
    steps: List[WorkflowStep] = field(default_factory=list)
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_template: bool = False
    category: Optional[str] = None

    def add_step(self, step: WorkflowStep) -> None:
        """Add a step to the workflow"""
        self.steps.append(step)
        # Sort by order
        self.steps.sort(key=lambda s: s.order)

    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        """Get a step by ID"""
        return next((s for s in self.steps if s.step_id == step_id), None)

    def get_next_step(self, current_step_id: Optional[str] = None) -> Optional[WorkflowStep]:
        """Get the next step in the workflow"""
        if current_step_id is None:
            return self.steps[0] if self.steps else None

        current_step = self.get_step(current_step_id)
        if not current_step:
            return None

        # Find next step by order
        next_steps = [s for s in self.steps if s.order > current_step.order]
        return min(next_steps, key=lambda s: s.order) if next_steps else None


@dataclass
class WorkflowInstance:
    """Represents an execution instance of a workflow"""
    instance_id: str
    workflow_id: str
    workflow_name: str
    status: WorkflowStatus
    current_step_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    initiated_by: Optional[str] = None
    initiated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    step_history: List[Dict[str, Any]] = field(default_factory=list)

    def add_step_result(
        self,
        step_id: str,
        status: ApprovalStatus,
        approver: Optional[str] = None,
        comments: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Add a step result to the history"""
        if timestamp is None:
            timestamp = datetime.utcnow()

        self.step_history.append({
            'step_id': step_id,
            'status': status.value,
            'approver': approver,
            'comments': comments,
            'timestamp': timestamp.isoformat()
        })

    def get_elapsed_time(self) -> Optional[float]:
        """Get elapsed time in hours"""
        if not self.initiated_at:
            return None

        end_time = self.completed_at or datetime.utcnow()
        delta = end_time - self.initiated_at
        return delta.total_seconds() / 3600

    def is_terminal_status(self) -> bool:
        """Check if workflow is in a terminal status"""
        return self.status in [
            WorkflowStatus.COMPLETED,
            WorkflowStatus.REJECTED,
            WorkflowStatus.CANCELLED,
            WorkflowStatus.ERROR
        ]


@dataclass
class ApprovalRequest:
    """Represents an approval request for a workflow step"""
    request_id: str
    instance_id: str
    workflow_name: str
    step_id: str
    step_name: str
    approver: str
    context: Dict[str, Any]
    created_at: datetime
    due_date: Optional[datetime] = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    comments: Optional[str] = None
    decision_at: Optional[datetime] = None
    decision_by: Optional[str] = None
