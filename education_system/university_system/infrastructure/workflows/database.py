"""
Database operations for workflow management
"""

import json
import logging
from typing import List, Optional
from datetime import datetime

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.workflows.models import (
    Workflow,
    WorkflowInstance,
    WorkflowStep,
    WorkflowStatus,
    StepType,
    ApprovalStatus,
    ApprovalRequest,
)

logger = logging.getLogger(__name__)


class WorkflowDatabase:
    """Database operations for workflows"""

    def __init__(self):
        """Initialize database and create tables"""
        self._create_tables()

    def _create_tables(self) -> None:
        """Create workflow tables if they don't exist"""
        with transaction() as conn:
            # Drop old workflow tables if they exist with incompatible schema
            try:
                cursor = conn.execute("PRAGMA table_info(workflows)")
                columns = [row[1] for row in cursor.fetchall()]
                # Check if old schema (missing required columns)
                if columns and ('steps_json' not in columns or 'name' not in columns):
                    conn.execute("DROP TABLE IF EXISTS workflows")
                    conn.execute("DROP TABLE IF EXISTS workflow_instances")
                    conn.execute("DROP TABLE IF EXISTS approval_requests")
                    conn.execute("DROP TABLE IF EXISTS step_history")
            except Exception:
                pass

            # Workflows table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS workflows (
                    workflow_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    version TEXT DEFAULT '1.0',
                    category TEXT,
                    steps_json TEXT NOT NULL,
                    metadata_json TEXT,
                    is_template INTEGER DEFAULT 0,
                    created_by TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            ''')

            # Workflow instances table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS workflow_instances (
                    instance_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    workflow_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_step_id TEXT,
                    context_json TEXT,
                    initiated_by TEXT,
                    initiated_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    result_json TEXT,
                    error_message TEXT,
                    step_history_json TEXT,
                    FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id)
                )
            ''')

            # Approval requests table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS approval_requests (
                    request_id TEXT PRIMARY KEY,
                    instance_id TEXT NOT NULL,
                    workflow_name TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    step_name TEXT NOT NULL,
                    approver TEXT NOT NULL,
                    context_json TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP,
                    due_date TIMESTAMP,
                    decision_at TIMESTAMP,
                    decision_by TEXT,
                    comments TEXT,
                    FOREIGN KEY (instance_id) REFERENCES workflow_instances(instance_id)
                )
            ''')

            # Workflow audit log
            conn.execute('''
                CREATE TABLE IF NOT EXISTS workflow_audit_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instance_id TEXT NOT NULL,
                    step_id TEXT,
                    action TEXT NOT NULL,
                    actor TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    details_json TEXT,
                    FOREIGN KEY (instance_id) REFERENCES workflow_instances(instance_id)
                )
            ''')

            # Migrate existing workflows table if needed
            try:
                cursor = conn.execute("PRAGMA table_info(workflows)")
                columns = [row[1] for row in cursor.fetchall()]

                # Add missing columns if table exists
                if columns:  # Table exists
                    if 'name' not in columns:
                        conn.execute('ALTER TABLE workflows ADD COLUMN name TEXT')
                    if 'description' not in columns:
                        conn.execute('ALTER TABLE workflows ADD COLUMN description TEXT')
                    if 'category' not in columns:
                        conn.execute('ALTER TABLE workflows ADD COLUMN category TEXT')
                    if 'version' not in columns:
                        conn.execute('ALTER TABLE workflows ADD COLUMN version TEXT DEFAULT "1.0"')
            except Exception:
                pass  # Table doesn't exist yet or migration failed

            # Create indexes
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_workflow_instances_status
                ON workflow_instances(status)
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_approval_requests_approver
                ON approval_requests(approver, status)
            ''')

            try:
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_workflows_category
                    ON workflows(category, is_template)
                ''')
            except Exception:
                pass  # Index creation failed, likely because column doesn't exist

    def save_workflow(self, workflow: Workflow) -> None:
        """Save a workflow definition"""
        steps_json = json.dumps([self._step_to_dict(s) for s in workflow.steps])
        metadata_json = json.dumps(workflow.metadata)

        with transaction() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO workflows (
                    workflow_id, name, description, version, category,
                    steps_json, metadata_json, is_template, created_by,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                workflow.workflow_id,
                workflow.name,
                workflow.description,
                workflow.version,
                workflow.category,
                steps_json,
                metadata_json,
                1 if workflow.is_template else 0,
                workflow.created_by,
                workflow.created_at,
                datetime.utcnow()
            ))

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get a workflow by ID"""
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM workflows WHERE workflow_id = ?
            ''', (workflow_id,))
            row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_workflow(row)

    def get_all_workflows(self) -> List[Workflow]:
        """Get all workflows"""
        with get_connection() as conn:
            cursor = conn.execute('SELECT * FROM workflows ORDER BY created_at DESC')
            rows = cursor.fetchall()

        return [self._row_to_workflow(row) for row in rows]

    def save_instance(self, instance: WorkflowInstance) -> None:
        """Save a workflow instance"""
        with transaction() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO workflow_instances (
                    instance_id, workflow_id, workflow_name, status,
                    current_step_id, context_json, initiated_by,
                    initiated_at, completed_at, result_json,
                    error_message, step_history_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                instance.instance_id,
                instance.workflow_id,
                instance.workflow_name,
                instance.status.value,
                instance.current_step_id,
                json.dumps(instance.context),
                instance.initiated_by,
                instance.initiated_at,
                instance.completed_at,
                json.dumps(instance.result) if instance.result else None,
                instance.error_message,
                json.dumps(instance.step_history)
            ))

    def update_instance(self, instance: WorkflowInstance) -> None:
        """Update a workflow instance"""
        self.save_instance(instance)

    def get_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        """Get a workflow instance by ID"""
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM workflow_instances WHERE instance_id = ?
            ''', (instance_id,))
            row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_instance(row)

    def save_approval_request(self, request: ApprovalRequest) -> None:
        """Save an approval request"""
        with transaction() as conn:
            conn.execute('''
                INSERT INTO approval_requests (
                    request_id, instance_id, workflow_name, step_id,
                    step_name, approver, context_json, status,
                    created_at, due_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                request.request_id,
                request.instance_id,
                request.workflow_name,
                request.step_id,
                request.step_name,
                request.approver,
                json.dumps(request.context),
                request.status.value,
                request.created_at,
                request.due_date
            ))

    def update_approval_request(
        self,
        instance_id: str,
        step_id: str,
        status: ApprovalStatus,
        decision_by: str,
        comments: Optional[str] = None
    ) -> None:
        """Update an approval request"""
        with transaction() as conn:
            conn.execute('''
                UPDATE approval_requests
                SET status = ?, decision_at = ?, decision_by = ?, comments = ?
                WHERE instance_id = ? AND step_id = ? AND status = 'pending'
            ''', (
                status.value,
                datetime.utcnow(),
                decision_by,
                comments,
                instance_id,
                step_id
            ))

    def get_pending_approvals(self, approver: str) -> List[ApprovalRequest]:
        """Get pending approval requests for an approver"""
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM approval_requests
                WHERE approver = ? AND status = 'pending'
                ORDER BY created_at DESC
            ''', (approver,))
            rows = cursor.fetchall()

        return [self._row_to_approval_request(row) for row in rows]

    def _step_to_dict(self, step: WorkflowStep) -> dict:
        """Convert step to dictionary"""
        return {
            'step_id': step.step_id,
            'name': step.name,
            'step_type': step.step_type.value,
            'order': step.order,
            'description': step.description,
            'approver': step.approver,
            'criteria': step.criteria,
            'timeout_hours': step.timeout_hours,
            'escalation_target': step.escalation_target,
            'parallel_steps': step.parallel_steps,
            'required': step.required
        }

    def _dict_to_step(self, data: dict) -> WorkflowStep:
        """Convert dictionary to step"""
        return WorkflowStep(
            step_id=data['step_id'],
            name=data['name'],
            step_type=StepType(data['step_type']),
            order=data['order'],
            description=data.get('description', ''),
            approver=data.get('approver'),
            criteria=data.get('criteria'),
            timeout_hours=data.get('timeout_hours'),
            escalation_target=data.get('escalation_target'),
            parallel_steps=data.get('parallel_steps', []),
            required=data.get('required', True)
        )

    def _row_to_workflow(self, row) -> Workflow:
        """Convert database row to Workflow"""
        steps_data = json.loads(row[5])  # steps_json
        steps = [self._dict_to_step(s) for s in steps_data]

        return Workflow(
            workflow_id=row[0],
            name=row[1],
            description=row[2],
            version=row[3],
            category=row[4],
            steps=steps,
            metadata=json.loads(row[6]) if row[6] else {},  # metadata_json
            is_template=bool(row[7]),
            created_by=row[8],
            created_at=datetime.fromisoformat(row[9]) if row[9] else None
        )

    def _row_to_instance(self, row) -> WorkflowInstance:
        """Convert database row to WorkflowInstance"""
        return WorkflowInstance(
            instance_id=row[0],
            workflow_id=row[1],
            workflow_name=row[2],
            status=WorkflowStatus(row[3]),
            current_step_id=row[4],
            context=json.loads(row[5]) if row[5] else {},
            initiated_by=row[6],
            initiated_at=datetime.fromisoformat(row[7]) if row[7] else None,
            completed_at=datetime.fromisoformat(row[8]) if row[8] else None,
            result=json.loads(row[9]) if row[9] else None,
            error_message=row[10],
            step_history=json.loads(row[11]) if row[11] else []
        )

    def _row_to_approval_request(self, row) -> ApprovalRequest:
        """Convert database row to ApprovalRequest"""
        return ApprovalRequest(
            request_id=row[0],
            instance_id=row[1],
            workflow_name=row[2],
            step_id=row[3],
            step_name=row[4],
            approver=row[5],
            context=json.loads(row[6]) if row[6] else {},
            status=ApprovalStatus(row[7]),
            created_at=datetime.fromisoformat(row[8]) if row[8] else datetime.utcnow(),
            due_date=datetime.fromisoformat(row[9]) if row[9] else None,
            decision_at=datetime.fromisoformat(row[10]) if row[10] else None,
            decision_by=row[11],
            comments=row[12]
        )
