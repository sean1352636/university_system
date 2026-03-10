from ._common import datetime, sqlite3, get_connection, _t


class WorkflowMixin:
    def workflow_management(self):
        """Workflow management system"""
        print("\n⚙️ WORKFLOW MANAGEMENT")
        print("1. View Active Workflows")
        print("2. Process Workflow Step")
        print("3. Create Custom Workflow")
        print("4. Workflow Templates")
        print("5. Workflow Analytics")
        print("6. Return to Main Menu")

        choice = input("\nChoose option (1-6): ").strip()

        if choice == '1':
            self.view_active_workflows()
        elif choice == '2':
            self.process_workflow_step()
        elif choice == '3':
            self.create_custom_workflow()
        elif choice == '4':
            self.workflow_templates()
        elif choice == '5':
            self.workflow_analytics()

    def view_active_workflows(self):
        """View all active workflows"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT dw.workflow_id, dw.document_id, dt.type_name,
                   s.first_name || ' ' || s.last_name as student_name,
                   dw.step_name, dw.assigned_to, dw.status
            FROM document_workflow dw
            JOIN student_documents sd ON dw.document_id = sd.document_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            JOIN students s ON sd.student_id = s.student_id
            WHERE dw.status = 'pending'
            ORDER BY dw.step_order
            ''')

            workflows = cursor.fetchall()

            print(f"\n⚙️ ACTIVE WORKFLOWS ({len(workflows)} pending)")
            print("=" * 100)

            if not workflows:
                print("No active workflows.")
                conn.close()
                return

            print(f"{'WF ID':<8} {'Doc ID':<8} {'Document Type':<20} {'Student':<20} {'Step':<20} {'Assigned To':<15}")
            print("-" * 100)

            for wf in workflows:
                wf_id, doc_id, doc_type, student_name, step_name, assigned_to, status = wf
                print(f"{wf_id:<8} {doc_id:<8} {doc_type:<20} {student_name:<20} {step_name:<20} {assigned_to:<15}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def process_workflow_step(self):
        """Process a workflow step"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            workflow_id = input("Enter workflow ID to process: ").strip()

            cursor.execute('''
            SELECT dw.workflow_id, dw.step_name, dw.assigned_to,
                   sd.document_id, dt.type_name
            FROM document_workflow dw
            JOIN student_documents sd ON dw.document_id = sd.document_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE dw.workflow_id = ? AND dw.status = 'pending'
            ''', (workflow_id,))

            workflow = cursor.fetchone()

            if not workflow:
                print("Workflow step not found or already completed.")
                conn.close()
                return

            wf_id, step_name, assigned_to, doc_id, doc_type = workflow

            print(f"\nWorkflow Step: {step_name}")
            print(f"Document: {doc_type} (ID: {doc_id})")
            print(f"Assigned to: {assigned_to}")

            print("\nActions:")
            print("1. Approve")
            print("2. Reject")
            print("3. Reassign")

            action = input("\nChoose action (1-3): ").strip()

            if action == '1':
                comments = input("Comments (optional): ").strip()
                cursor.execute('''
                UPDATE document_workflow
                SET status = 'completed', comments = ?,
                    completed_date = ?, completed_by = ?
                WHERE workflow_id = ?
                ''', (comments, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                      self.current_user, workflow_id))

                # Check if all steps are complete
                cursor.execute('''
                SELECT COUNT(*)
                FROM document_workflow
                WHERE document_id = ? AND status = 'pending'
                ''', (doc_id,))

                remaining_steps = cursor.fetchone()[0]

                if remaining_steps == 0:
                    cursor.execute('''
                    UPDATE student_documents
                    SET workflow_status = 'completed'
                    WHERE document_id = ?
                    ''', (doc_id,))
                    print("All workflow steps completed!")

                conn.commit()
                print("✅ Step approved.")

            elif action == '2':
                comments = input("Rejection reason: ").strip()
                cursor.execute('''
                UPDATE document_workflow
                SET status = 'rejected', comments = ?,
                    completed_date = ?, completed_by = ?
                WHERE workflow_id = ?
                ''', (comments, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                      self.current_user, workflow_id))

                cursor.execute('''
                UPDATE student_documents
                SET workflow_status = 'rejected'
                WHERE document_id = ?
                ''', (doc_id,))

                conn.commit()
                print("❌ Step rejected.")

            elif action == '3':
                new_assignee = input("Reassign to: ").strip()
                cursor.execute('''
                UPDATE document_workflow
                SET assigned_to = ?
                WHERE workflow_id = ?
                ''', (new_assignee, workflow_id))

                conn.commit()
                print(f"✅ Reassigned to {new_assignee}.")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def create_custom_workflow(self):
        """Create a custom workflow template"""
        try:
            print("\n⚙️  CREATE CUSTOM WORKFLOW")

            workflow_name = input("Workflow name: ").strip()
            if not workflow_name:
                print("Workflow name is required.")
                return

            description = input("Workflow description: ").strip()

            # Get document types this workflow applies to
            conn = get_connection()
            cursor = conn.cursor()

            type_info = self.select_document_type(cursor)
            if not type_info:
                conn.close()
                return

            type_id = type_info[0]

            print("\nDefine workflow steps:")
            steps = []
            step_order = 1

            while True:
                print(f"\nStep {step_order}:")
                step_name = input("  Step name (or 'done' to finish): ").strip()

                if step_name.lower() == 'done':
                    break

                assigned_to = input("  Assigned to (role/username): ").strip()
                required = input("  Required step? (y/n): ").strip().lower() == 'y'

                steps.append({
                    'name': step_name,
                    'order': step_order,
                    'assigned_to': assigned_to,
                    'required': required
                })

                step_order += 1

            if not steps:
                print("No steps defined. Workflow not created.")
                conn.close()
                return

            # Create workflow template table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflow_templates (
                template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT UNIQUE,
                description TEXT,
                type_id INTEGER,
                is_active BOOLEAN DEFAULT 1,
                created_by TEXT,
                created_date TEXT,
                FOREIGN KEY (type_id) REFERENCES document_types (type_id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflow_template_steps (
                step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER,
                step_name TEXT,
                step_order INTEGER,
                assigned_to TEXT,
                is_required BOOLEAN,
                FOREIGN KEY (template_id) REFERENCES workflow_templates (template_id)
            )
            ''')

            # Insert workflow template
            cursor.execute('''
            INSERT INTO workflow_templates (template_name, description, type_id, created_by, created_date)
            VALUES (?, ?, ?, ?, ?)
            ''', (workflow_name, description, type_id, self.current_user,
                  datetime.now().strftime('%Y-%m-%d')))

            template_id = cursor.lastrowid

            # Insert workflow steps
            for step in steps:
                cursor.execute('''
                INSERT INTO workflow_template_steps (template_id, step_name, step_order, assigned_to, is_required)
                VALUES (?, ?, ?, ?, ?)
                ''', (template_id, step['name'], step['order'], step['assigned_to'], step['required']))

            conn.commit()
            conn.close()

            print(f"\n✅ Workflow '{workflow_name}' created successfully with {len(steps)} steps!")

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def workflow_templates(self):
        """Manage workflow templates"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n⚙️  WORKFLOW TEMPLATES")

            # Check if workflow_templates table exists
            cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='workflow_templates'
            ''')

            if not cursor.fetchone():
                print("\nNo workflow templates found.")
                print("Use 'Create Custom Workflow' to create your first template.")
                conn.close()
                return

            cursor.execute('''
            SELECT template_id, template_name, description, is_active
            FROM workflow_templates
            ORDER BY template_name
            ''')

            templates = cursor.fetchall()

            if not templates:
                print("\nNo workflow templates found.")
                conn.close()
                return

            print("\nAvailable Templates:")
            for template_id, name, desc, active in templates:
                status = "Active" if active else "Inactive"
                print(f"\n{template_id}. {name} ({status})")
                if desc:
                    print(f"   {desc}")

                # Show steps
                cursor.execute('''
                SELECT step_name, step_order, assigned_to
                FROM workflow_template_steps
                WHERE template_id = ?
                ORDER BY step_order
                ''', (template_id,))

                steps = cursor.fetchall()
                if steps:
                    print("   Steps:")
                    for step_name, step_order, assigned_to in steps:
                        print(f"     {step_order}. {step_name} (assigned to: {assigned_to})")

            print("\nActions:")
            print("1. Activate/Deactivate template")
            print("2. Delete template")
            print("3. Return to menu")

            action = input("\nChoose action (1-3): ").strip()

            if action == '1':
                template_id = input("Enter template ID: ").strip()
                cursor.execute('''
                UPDATE workflow_templates
                SET is_active = NOT is_active
                WHERE template_id = ?
                ''', (template_id,))
                conn.commit()
                print("✅ Template status updated.")

            elif action == '2':
                template_id = input("Enter template ID to delete: ").strip()
                confirm = input(f"Delete template {template_id}? (y/n): ").strip().lower()
                if confirm == 'y':
                    cursor.execute('DELETE FROM workflow_template_steps WHERE template_id = ?', (template_id,))
                    cursor.execute('DELETE FROM workflow_templates WHERE template_id = ?', (template_id,))
                    conn.commit()
                    print("✅ Template deleted.")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def workflow_analytics(self):
        """View workflow performance analytics"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📊 WORKFLOW ANALYTICS")
            print("=" * 80)

            # Average workflow completion time
            cursor.execute('''
            SELECT AVG(
                julianday(MAX(completed_date)) - julianday(MIN(created_date))
            ) as avg_days
            FROM (
                SELECT dw.document_id,
                       (SELECT upload_date FROM student_documents WHERE document_id = dw.document_id) as created_date,
                       dw.completed_date
                FROM document_workflow dw
                WHERE dw.status = 'completed'
            )
            ''')

            avg_time = cursor.fetchone()[0]

            if avg_time:
                print(f"\nAverage Workflow Completion Time: {avg_time:.1f} days")

            # Workflow completion rate
            cursor.execute('''
            SELECT
                COUNT(DISTINCT CASE WHEN status = 'completed' THEN document_id END) as completed,
                COUNT(DISTINCT document_id) as total
            FROM document_workflow
            ''')

            completed, total = cursor.fetchone()

            if total > 0:
                completion_rate = (completed / total) * 100
                print(f"Workflow Completion Rate: {completion_rate:.1f}% ({completed}/{total})")

            # Bottleneck analysis - steps taking longest
            cursor.execute('''
            SELECT step_name, AVG(
                julianday(completed_date) - julianday(
                    (SELECT MIN(created_date) FROM student_documents WHERE document_id = document_workflow.document_id)
                )
            ) as avg_days
            FROM document_workflow
            WHERE status = 'completed' AND completed_date IS NOT NULL
            GROUP BY step_name
            ORDER BY avg_days DESC
            LIMIT 5
            ''')

            bottlenecks = cursor.fetchall()

            if bottlenecks:
                print("\nSlowest Workflow Steps:")
                for step_name, avg_days in bottlenecks:
                    if avg_days:
                        print(f"  {step_name}: {avg_days:.1f} days average")

            # Workflow status distribution
            cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM document_workflow
            GROUP BY status
            ''')

            status_dist = cursor.fetchall()

            if status_dist:
                print("\nWorkflow Status Distribution:")
                for status, count in status_dist:
                    print(f"  {status}: {count}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")
