"""
Pre-built workflow templates for common university processes
"""

from typing import Dict, Any
from education_system.university_system.infrastructure.workflows.models import Workflow
from education_system.university_system.infrastructure.workflows.steps import (
    ApprovalStep,
    AutomatedStep,
    ConditionalStep,
    NotificationStep,
)


class WorkflowTemplates:
    """Collection of pre-built workflow templates"""

    @staticmethod
    def scholarship_application() -> Workflow:
        """
        Scholarship application workflow

        Steps:
        1. Automated GPA check
        2. Department head approval
        3. Financial aid office review
        4. Dean's final approval
        5. Notify student of decision
        """
        def check_gpa_eligibility(context: Dict[str, Any]) -> Dict[str, Any]:
            """Check if student meets minimum GPA requirement"""
            gpa = context.get('gpa', 0.0)
            eligible = gpa >= 3.0
            return {'gpa_eligible': eligible, 'checked_gpa': gpa}

        def calculate_award_amount(context: Dict[str, Any]) -> Dict[str, Any]:
            """Calculate scholarship amount based on GPA and need"""
            gpa = context.get('gpa', 0.0)
            financial_need = context.get('financial_need', 0)

            if gpa >= 4.0:
                base_amount = 10000
            elif gpa >= 3.5:
                base_amount = 5000
            else:
                base_amount = 2500

            # Adjust for financial need
            if financial_need > 50000:
                base_amount = int(base_amount * 1.5)

            return {'award_amount': base_amount}

        workflow = Workflow(
            workflow_id="template_scholarship",
            name="Scholarship Application",
            description="Multi-step approval workflow for scholarship applications",
            category="financial_aid",
            is_template=True
        )

        # Step 1: Automated GPA eligibility check
        workflow.add_step(AutomatedStep(
            step_id="check_gpa",
            name="Check GPA Eligibility",
            order=1,
            action=check_gpa_eligibility,
            description="Verify student meets minimum 3.0 GPA requirement"
        ))

        # Step 2: Conditional check - only continue if GPA eligible
        workflow.add_step(ConditionalStep(
            step_id="gpa_gate",
            name="GPA Gate",
            order=2,
            condition=lambda ctx: ctx.get('gpa_eligible', False),
            description="Gate to ensure GPA requirement is met"
        ))

        # Step 3: Department head approval
        workflow.add_step(ApprovalStep(
            step_id="dept_head_approval",
            name="Department Head Approval",
            order=3,
            approver="department_head",
            criteria={"gpa": ">= 3.5"},
            timeout_hours=48,
            description="Department head reviews academic merit"
        ))

        # Step 4: Financial aid office review
        workflow.add_step(ApprovalStep(
            step_id="financial_aid_review",
            name="Financial Aid Office Review",
            order=4,
            approver="financial_aid_office",
            criteria={"financial_need": True},
            timeout_hours=72,
            description="Financial aid office reviews need-based criteria"
        ))

        # Step 5: Calculate award amount
        workflow.add_step(AutomatedStep(
            step_id="calculate_amount",
            name="Calculate Award Amount",
            order=5,
            action=calculate_award_amount,
            description="Automatically calculate scholarship amount"
        ))

        # Step 6: Dean's final approval
        workflow.add_step(ApprovalStep(
            step_id="dean_approval",
            name="Dean's Final Approval",
            order=6,
            approver="dean",
            timeout_hours=96,
            escalation_target="provost",
            description="Dean provides final approval"
        ))

        # Step 7: Notify student
        workflow.add_step(NotificationStep(
            step_id="notify_student",
            name="Notify Student",
            order=7,
            approver="student_id",  # Will be substituted from context
            description="Send notification to student about decision"
        ))

        return workflow

    @staticmethod
    def leave_request() -> Workflow:
        """
        Staff/Faculty leave request workflow

        Steps:
        1. Supervisor approval
        2. HR review (if > 5 days)
        3. Department head approval (if > 10 days)
        4. Update leave balance
        5. Notify employee
        """
        def update_leave_balance(context: Dict[str, Any]) -> Dict[str, Any]:
            """Update employee leave balance"""
            days_requested = context.get('days_requested', 0)
            current_balance = context.get('current_balance', 0)
            new_balance = current_balance - days_requested
            return {'new_balance': new_balance, 'balance_updated': True}

        workflow = Workflow(
            workflow_id="template_leave_request",
            name="Leave Request",
            description="Employee leave request approval workflow",
            category="hr",
            is_template=True
        )

        # Step 1: Supervisor approval
        workflow.add_step(ApprovalStep(
            step_id="supervisor_approval",
            name="Supervisor Approval",
            order=1,
            approver="supervisor",
            timeout_hours=24,
            description="Direct supervisor approves leave request"
        ))

        # Step 2: HR review (conditional - only if > 5 days)
        workflow.add_step(ApprovalStep(
            step_id="hr_review",
            name="HR Review",
            order=2,
            approver="hr_manager",
            criteria={"days_requested": ">= 5"},
            timeout_hours=48,
            description="HR reviews extended leave requests",
            required=False
        ))

        # Step 3: Department head approval (conditional - only if > 10 days)
        workflow.add_step(ApprovalStep(
            step_id="dept_head_approval",
            name="Department Head Approval",
            order=3,
            approver="department_head",
            criteria={"days_requested": ">= 10"},
            timeout_hours=48,
            description="Department head approves long leave requests",
            required=False
        ))

        # Step 4: Update leave balance
        workflow.add_step(AutomatedStep(
            step_id="update_balance",
            name="Update Leave Balance",
            order=4,
            action=update_leave_balance,
            description="Automatically update employee leave balance"
        ))

        # Step 5: Notify employee
        workflow.add_step(NotificationStep(
            step_id="notify_employee",
            name="Notify Employee",
            order=5,
            approver="employee_id",
            description="Notify employee of approval"
        ))

        return workflow

    @staticmethod
    def grade_appeal() -> Workflow:
        """
        Student grade appeal workflow

        Steps:
        1. Instructor review
        2. Department chair review
        3. Academic dean review (if unresolved)
        4. Update grade if approved
        5. Notify student
        """
        def update_grade(context: Dict[str, Any]) -> Dict[str, Any]:
            """Update student grade"""
            new_grade = context.get('revised_grade')
            student_id = context.get('student_id')
            course_id = context.get('course_id')

            # This would integrate with grading system
            return {
                'grade_updated': True,
                'old_grade': context.get('original_grade'),
                'new_grade': new_grade
            }

        workflow = Workflow(
            workflow_id="template_grade_appeal",
            name="Grade Appeal",
            description="Student grade appeal review process",
            category="academics",
            is_template=True
        )

        # Step 1: Instructor review
        workflow.add_step(ApprovalStep(
            step_id="instructor_review",
            name="Instructor Review",
            order=1,
            approver="course_instructor",
            timeout_hours=72,
            description="Original instructor reviews appeal"
        ))

        # Step 2: Department chair review
        workflow.add_step(ApprovalStep(
            step_id="chair_review",
            name="Department Chair Review",
            order=2,
            approver="department_chair",
            timeout_hours=96,
            description="Department chair reviews if instructor denies"
        ))

        # Step 3: Academic dean review (escalation)
        workflow.add_step(ApprovalStep(
            step_id="dean_review",
            name="Academic Dean Review",
            order=3,
            approver="academic_dean",
            timeout_hours=120,
            description="Dean provides final decision",
            required=False
        ))

        # Step 4: Update grade if approved
        workflow.add_step(AutomatedStep(
            step_id="update_grade",
            name="Update Grade",
            order=4,
            action=update_grade,
            description="Update grade in system if appeal approved"
        ))

        # Step 5: Notify student
        workflow.add_step(NotificationStep(
            step_id="notify_student",
            name="Notify Student",
            order=5,
            approver="student_id",
            description="Notify student of appeal decision"
        ))

        return workflow

    @staticmethod
    def course_approval() -> Workflow:
        """
        New course creation approval workflow

        Steps:
        1. Department review
        2. Curriculum committee review
        3. Academic dean approval
        4. Provost approval (if cross-departmental)
        5. Create course in system
        """
        def create_course(context: Dict[str, Any]) -> Dict[str, Any]:
            """Create course in system"""
            course_code = context.get('course_code')
            course_name = context.get('course_name')

            # This would integrate with course management system
            return {
                'course_created': True,
                'course_id': f"CRS-{course_code}"
            }

        workflow = Workflow(
            workflow_id="template_course_approval",
            name="New Course Approval",
            description="Approval workflow for creating new courses",
            category="academics",
            is_template=True
        )

        # Step 1: Department review
        workflow.add_step(ApprovalStep(
            step_id="dept_review",
            name="Department Review",
            order=1,
            approver="department_chair",
            timeout_hours=168,  # 1 week
            description="Department reviews course proposal"
        ))

        # Step 2: Curriculum committee
        workflow.add_step(ApprovalStep(
            step_id="curriculum_committee",
            name="Curriculum Committee Review",
            order=2,
            approver="curriculum_committee",
            timeout_hours=240,  # 10 days
            description="Curriculum committee evaluates course"
        ))

        # Step 3: Academic dean approval
        workflow.add_step(ApprovalStep(
            step_id="dean_approval",
            name="Academic Dean Approval",
            order=3,
            approver="academic_dean",
            timeout_hours=120,  # 5 days
            description="Dean approves new course"
        ))

        # Step 4: Provost approval (conditional)
        workflow.add_step(ApprovalStep(
            step_id="provost_approval",
            name="Provost Approval",
            order=4,
            approver="provost",
            criteria={"cross_departmental": True},
            timeout_hours=168,
            description="Provost approves cross-departmental courses",
            required=False
        ))

        # Step 5: Create course
        workflow.add_step(AutomatedStep(
            step_id="create_course",
            name="Create Course in System",
            order=5,
            action=create_course,
            description="Automatically create course in system"
        ))

        return workflow

    @staticmethod
    def budget_approval() -> Workflow:
        """
        Budget approval workflow

        Steps:
        1. Department review
        2. Finance office review
        3. Budget committee approval
        4. CFO approval (if > $50k)
        5. Process budget allocation
        """
        def process_budget(context: Dict[str, Any]) -> Dict[str, Any]:
            """Process budget allocation"""
            amount = context.get('amount', 0)
            department = context.get('department')

            return {
                'budget_allocated': True,
                'allocation_id': f"BUDGET-{department}-{amount}",
                'fiscal_year': context.get('fiscal_year', '2025')
            }

        workflow = Workflow(
            workflow_id="template_budget_approval",
            name="Budget Approval",
            description="Budget request approval workflow",
            category="finance",
            is_template=True
        )

        # Step 1: Department review
        workflow.add_step(ApprovalStep(
            step_id="dept_review",
            name="Department Review",
            order=1,
            approver="department_head",
            timeout_hours=48,
            description="Department head reviews budget request"
        ))

        # Step 2: Finance office review
        workflow.add_step(ApprovalStep(
            step_id="finance_review",
            name="Finance Office Review",
            order=2,
            approver="finance_office",
            timeout_hours=72,
            description="Finance office validates budget request"
        ))

        # Step 3: Budget committee
        workflow.add_step(ApprovalStep(
            step_id="budget_committee",
            name="Budget Committee Approval",
            order=3,
            approver="budget_committee",
            timeout_hours=120,
            description="Budget committee reviews allocation"
        ))

        # Step 4: CFO approval (conditional)
        workflow.add_step(ApprovalStep(
            step_id="cfo_approval",
            name="CFO Approval",
            order=4,
            approver="cfo",
            criteria={"amount": ">= 50000"},
            timeout_hours=96,
            description="CFO approves large budget requests",
            required=False
        ))

        # Step 5: Process budget
        workflow.add_step(AutomatedStep(
            step_id="process_budget",
            name="Process Budget Allocation",
            order=5,
            action=process_budget,
            description="Process approved budget allocation"
        ))

        return workflow


# Convenience functions
def create_scholarship_workflow() -> Workflow:
    """Create scholarship application workflow"""
    return WorkflowTemplates.scholarship_application()


def create_leave_request_workflow() -> Workflow:
    """Create leave request workflow"""
    return WorkflowTemplates.leave_request()


def create_grade_appeal_workflow() -> Workflow:
    """Create grade appeal workflow"""
    return WorkflowTemplates.grade_appeal()


def create_course_approval_workflow() -> Workflow:
    """Create new course approval workflow"""
    return WorkflowTemplates.course_approval()


def create_budget_approval_workflow() -> Workflow:
    """Create budget approval workflow"""
    return WorkflowTemplates.budget_approval()


def get_workflow_template(template_name: str) -> Workflow:
    """
    Get a workflow template by name

    Args:
        template_name: Name of template (scholarship, leave_request, grade_appeal,
                      course_approval, budget_approval)

    Returns:
        Workflow template
    """
    templates = {
        'scholarship': create_scholarship_workflow,
        'leave_request': create_leave_request_workflow,
        'grade_appeal': create_grade_appeal_workflow,
        'course_approval': create_course_approval_workflow,
        'budget_approval': create_budget_approval_workflow,
    }

    factory = templates.get(template_name)
    if not factory:
        raise ValueError(f"Unknown template: {template_name}")

    return factory()
