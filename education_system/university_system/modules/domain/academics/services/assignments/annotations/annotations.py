from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
import json
import os


ANNOTATION_CATEGORIES = ['praise', 'suggestion', 'correction', 'question']

CATEGORY_SYMBOLS = {
    'praise': '[+]',
    'suggestion': '[~]',
    'correction': '[!]',
    'question': '[?]',
}


class AnnotationMixin:
    """Mixin providing CLI-based annotation of student submissions."""

    def _get_submission_text(self, submission_id):
        """Retrieve submission content as text, from DB or file."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT content, file_path FROM assignment_submissions
            WHERE id = ?
        ''', (submission_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None
        content, file_path = row
        if content:
            return content
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    return f.read()
            except (OSError, IOError):
                return None
        return None

    def _display_submission_with_line_numbers(self, text):
        """Print submission text with line numbers."""
        lines = text.split('\n')
        for i, line in enumerate(lines, 1):
            print(f"  {i:4d} | {line}")
        return lines

    def _select_submission(self, cursor, permission='manage_assignments'):
        """Common helper: list submissions and let user pick one. Returns submission_id or None."""
        cursor.execute('''
            SELECT s.id, s.assignment_id, a.title, s.student_id, s.status, s.submitted_at
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            WHERE s.status IN ('submitted', 'graded', 'reviewed')
            ORDER BY s.submitted_at DESC
            LIMIT 50
        ''')
        submissions = cursor.fetchall()

        if not submissions:
            print("No submissions found.")
            return None

        print("\nSubmissions:")
        for i, (sid, aid, title, student, status, submitted) in enumerate(submissions, 1):
            date_str = submitted[:10] if submitted else 'N/A'
            print(f"  {i}. [ID {sid}] {title} - Student {student} ({status}) - {date_str}")

        choice = input("\nSelect submission number: ").strip()
        try:
            index = int(choice) - 1
            if 0 <= index < len(submissions):
                return submissions[index][0]
            else:
                print("Invalid selection.")
                return None
        except ValueError:
            print("Please enter a number.")
            return None

    # ------------------------------------------------------------------
    # 1. annotate_submission
    # ------------------------------------------------------------------

    def annotate_submission(self):
        """Instructor annotates a submission with inline comments."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            submission_id = self._select_submission(cursor)
            if not submission_id:
                conn.close()
                return

            text = self._get_submission_text(submission_id)
            if not text:
                print("Could not retrieve submission content.")
                conn.close()
                return

            print("\n" + "=" * 60)
            print("Submission Content:")
            print("=" * 60)
            lines = self._display_submission_with_line_numbers(text)
            print("=" * 60)

            reviewer_id = self.auth.current_user['id']

            while True:
                print("\nAdd annotation (or type 'done' to finish):")
                line_input = input("Line number: ").strip()
                if line_input.lower() == 'done':
                    break

                try:
                    line_number = int(line_input)
                except ValueError:
                    print("Please enter a valid line number.")
                    continue

                if line_number < 1 or line_number > len(lines):
                    print(f"Line number must be between 1 and {len(lines)}.")
                    continue

                print(f"\n  Line {line_number}: {lines[line_number - 1]}")

                print("\nCategory:")
                for i, cat in enumerate(ANNOTATION_CATEGORIES, 1):
                    print(f"  {i}. {cat}")
                cat_choice = input("Select category (1-4) [2]: ").strip()
                if cat_choice in ('1', '2', '3', '4'):
                    category = ANNOTATION_CATEGORIES[int(cat_choice) - 1]
                else:
                    category = 'suggestion'

                # Offer templates
                use_template = input("Use a template? (y/n) [n]: ").strip().lower()
                comment = ''
                if use_template == 'y':
                    cursor.execute('''
                        SELECT id, name, text, category
                        FROM annotation_templates
                        ORDER BY usage_count DESC
                        LIMIT 20
                    ''')
                    templates = cursor.fetchall()
                    if templates:
                        print("\nAvailable Templates:")
                        for i, (tid, name, ttext, tcat) in enumerate(templates, 1):
                            display = ttext[:60] + '...' if len(ttext) > 60 else ttext
                            print(f"  {i}. [{tcat}] {name}: {display}")
                        t_choice = input("Select template number (or Enter to skip): ").strip()
                        try:
                            t_index = int(t_choice) - 1
                            if 0 <= t_index < len(templates):
                                comment = templates[t_index][2]
                                cursor.execute(
                                    'UPDATE annotation_templates SET usage_count = usage_count + 1 WHERE id = ?',
                                    (templates[t_index][0],)
                                )
                                print(f"Template applied: {comment}")
                        except (ValueError, IndexError):
                            pass
                    else:
                        print("No templates available.")

                if not comment:
                    comment = input("Comment: ").strip()
                else:
                    extra = input("Additional comment (or Enter to keep template text): ").strip()
                    if extra:
                        comment = comment + ' ' + extra

                if not comment:
                    print("Comment cannot be empty.")
                    continue

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO submission_annotations
                        (submission_id, reviewer_id, line_number, position_start, position_end,
                         comment, category, created_at, updated_at)
                    VALUES (?, ?, ?, 0, 0, ?, ?, ?, ?)
                ''', (submission_id, reviewer_id, line_number, comment, category, now, now))
                conn.commit()
                print(f"Annotation added at line {line_number} [{category}].")

            conn.close()
            print("\nAnnotation session complete.")

        except Exception as e:
            print(f"Error annotating submission: {e}")

    # ------------------------------------------------------------------
    # 2. view_annotations
    # ------------------------------------------------------------------

    def view_annotations(self):
        """View all annotations on a submission with inline markers."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            submission_id = self._select_submission(cursor)
            if not submission_id:
                conn.close()
                return

            text = self._get_submission_text(submission_id)
            if not text:
                print("Could not retrieve submission content.")
                conn.close()
                return

            cursor.execute('''
                SELECT line_number, category, comment, reviewer_id, created_at, student_response
                FROM submission_annotations
                WHERE submission_id = ?
                ORDER BY line_number, created_at
            ''', (submission_id,))
            annotations = cursor.fetchall()
            conn.close()

            if not annotations:
                print("\nNo annotations found for this submission.")
                return

            # Group annotations by line number
            annot_by_line = {}
            for line_num, category, comment, reviewer, created_at, response in annotations:
                annot_by_line.setdefault(line_num, []).append(
                    (category, comment, reviewer, created_at, response)
                )

            print(f"\nAnnotated Submission (ID: {submission_id})")
            print("=" * 70)

            lines = text.split('\n')
            for i, line in enumerate(lines, 1):
                print(f"  {i:4d} | {line}")
                if i in annot_by_line:
                    for category, comment, reviewer, created_at, response in annot_by_line[i]:
                        symbol = CATEGORY_SYMBOLS.get(category, '[*]')
                        date_str = created_at[:10] if created_at else 'N/A'
                        print(f"       {symbol} {category.upper()} (by {reviewer}, {date_str}): {comment}")
                        if response:
                            print(f"           >> Student reply: {response}")

            print("=" * 70)
            print(f"Total annotations: {len(annotations)}")

        except Exception as e:
            print(f"Error viewing annotations: {e}")

    # ------------------------------------------------------------------
    # 3. manage_annotation_templates
    # ------------------------------------------------------------------

    def manage_annotation_templates(self):
        """CRUD menu for reusable annotation comment templates."""
        if not self._check_permission('manage_assignments'):
            return

        while True:
            print("\nAnnotation Templates")
            print("=" * 40)
            print("1. View templates")
            print("2. Create template")
            print("3. Edit template")
            print("4. Delete template")
            print("5. Back")

            choice = input("\nSelect option: ").strip()

            if choice == '1':
                self._list_annotation_templates()
            elif choice == '2':
                self.create_annotation_template()
            elif choice == '3':
                self._edit_annotation_template()
            elif choice == '4':
                self._delete_annotation_template()
            elif choice == '5':
                break
            else:
                print("Invalid option.")

    def _list_annotation_templates(self):
        """Display all annotation templates."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, text, category, usage_count, created_at
                FROM annotation_templates
                ORDER BY usage_count DESC, name
            ''')
            templates = cursor.fetchall()
            conn.close()

            if not templates:
                print("\nNo annotation templates found.")
                return

            print(f"\n{'ID':<5} {'Name':<25} {'Category':<12} {'Uses':<6} {'Text'}")
            print("-" * 80)
            for tid, name, text, category, uses, created_at in templates:
                display_text = text[:40] + '...' if len(text) > 40 else text
                print(f"{tid:<5} {name:<25} {category:<12} {uses:<6} {display_text}")

        except Exception as e:
            print(f"Error listing templates: {e}")

    # ------------------------------------------------------------------
    # 4. create_annotation_template
    # ------------------------------------------------------------------

    def create_annotation_template(self):
        """Create a new reusable annotation comment template."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            print("\nCreate Annotation Template")
            print("=" * 40)

            name = input("Template name: ").strip()
            if not name:
                print("Name cannot be empty.")
                return

            text = input("Template text: ").strip()
            if not text:
                print("Text cannot be empty.")
                return

            print("Category:")
            for i, cat in enumerate(ANNOTATION_CATEGORIES, 1):
                print(f"  {i}. {cat}")
            cat_choice = input("Select category (1-4) [2]: ").strip()
            if cat_choice in ('1', '2', '3', '4'):
                category = ANNOTATION_CATEGORIES[int(cat_choice) - 1]
            else:
                category = 'suggestion'

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO annotation_templates (name, text, category, created_by, usage_count, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
            ''', (name, text, category, self.auth.current_user['id'], now))
            conn.commit()
            conn.close()

            print(f"Template '{name}' created successfully!")

        except Exception as e:
            print(f"Error creating template: {e}")

    def _edit_annotation_template(self):
        """Edit an existing annotation template."""
        try:
            self._list_annotation_templates()

            template_id = input("\nEnter template ID to edit: ").strip()
            if not template_id.isdigit():
                print("Invalid ID.")
                return

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, name, text, category FROM annotation_templates WHERE id = ?',
                (int(template_id),)
            )
            template = cursor.fetchone()
            if not template:
                print("Template not found.")
                conn.close()
                return

            tid, old_name, old_text, old_category = template
            print(f"\nEditing template: {old_name}")

            name = input(f"Name [{old_name}]: ").strip() or old_name
            text = input(f"Text [{old_text}]: ").strip() or old_text

            print("Category:")
            for i, cat in enumerate(ANNOTATION_CATEGORIES, 1):
                marker = " (current)" if cat == old_category else ""
                print(f"  {i}. {cat}{marker}")
            cat_choice = input(f"Select category (1-4) [{old_category}]: ").strip()
            if cat_choice in ('1', '2', '3', '4'):
                category = ANNOTATION_CATEGORIES[int(cat_choice) - 1]
            else:
                category = old_category

            cursor.execute('''
                UPDATE annotation_templates SET name = ?, text = ?, category = ? WHERE id = ?
            ''', (name, text, category, tid))
            conn.commit()
            conn.close()

            print(f"Template '{name}' updated successfully!")

        except Exception as e:
            print(f"Error editing template: {e}")

    def _delete_annotation_template(self):
        """Delete an annotation template."""
        try:
            self._list_annotation_templates()

            template_id = input("\nEnter template ID to delete: ").strip()
            if not template_id.isdigit():
                print("Invalid ID.")
                return

            confirm = input(f"Are you sure you want to delete template {template_id}? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Cancelled.")
                return

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM annotation_templates WHERE id = ?', (int(template_id),))
            if cursor.rowcount == 0:
                print("Template not found.")
            else:
                print("Template deleted successfully!")
            conn.commit()
            conn.close()

        except Exception as e:
            print(f"Error deleting template: {e}")

    # ------------------------------------------------------------------
    # 5. view_student_annotations
    # ------------------------------------------------------------------

    def view_student_annotations(self):
        """Student views annotations on their submission and can respond."""
        if not self._check_permission('submit_assignment'):
            return

        try:
            student_id = self._get_student_id()
            if not student_id:
                print("No student ID associated with your account.")
                return

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Show student's submissions that have annotations
            cursor.execute('''
                SELECT DISTINCT s.id, a.title, s.submitted_at
                FROM assignment_submissions s
                JOIN assignments a ON s.assignment_id = a.id
                JOIN submission_annotations sa ON sa.submission_id = s.id
                WHERE s.student_id = ?
                ORDER BY s.submitted_at DESC
            ''', (student_id,))
            submissions = cursor.fetchall()

            if not submissions:
                print("\nNo annotated submissions found.")
                conn.close()
                return

            print("\nYour Annotated Submissions:")
            for i, (sid, title, submitted) in enumerate(submissions, 1):
                date_str = submitted[:10] if submitted else 'N/A'
                print(f"  {i}. [ID {sid}] {title} - Submitted: {date_str}")

            choice = input("\nSelect submission number: ").strip()
            try:
                index = int(choice) - 1
                if not (0 <= index < len(submissions)):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            submission_id = submissions[index][0]

            # Display submission with annotations
            text = self._get_submission_text(submission_id)
            if text:
                cursor.execute('''
                    SELECT id, line_number, category, comment, student_response, reviewer_id, created_at
                    FROM submission_annotations
                    WHERE submission_id = ?
                    ORDER BY line_number, created_at
                ''', (submission_id,))
                annotations = cursor.fetchall()

                # Group by line
                annot_by_line = {}
                annot_list = []
                for annot in annotations:
                    aid, line_num, category, comment, response, reviewer, created_at = annot
                    annot_by_line.setdefault(line_num, []).append(annot)
                    annot_list.append(annot)

                print(f"\nSubmission with Feedback (ID: {submission_id})")
                print("=" * 70)

                lines = text.split('\n')
                for i, line in enumerate(lines, 1):
                    print(f"  {i:4d} | {line}")
                    if i in annot_by_line:
                        for annot in annot_by_line[i]:
                            aid, _, category, comment, response, reviewer, created_at = annot
                            symbol = CATEGORY_SYMBOLS.get(category, '[*]')
                            date_str = created_at[:10] if created_at else 'N/A'
                            print(f"       {symbol} {category.upper()} (by {reviewer}, {date_str}): {comment}")
                            if response:
                                print(f"           >> Your reply: {response}")
                            else:
                                print(f"           (No reply yet - annotation #{aid})")

                print("=" * 70)

                # Let student respond to annotations
                while True:
                    print("\nRespond to an annotation (or type 'done' to finish):")
                    aid_input = input("Annotation ID: ").strip()
                    if aid_input.lower() == 'done':
                        break

                    try:
                        aid = int(aid_input)
                    except ValueError:
                        print("Please enter a valid annotation ID.")
                        continue

                    # Verify the annotation belongs to this submission
                    matching = [a for a in annot_list if a[0] == aid]
                    if not matching:
                        print("Annotation not found for this submission.")
                        continue

                    annot = matching[0]
                    if annot[4]:
                        print(f"You already replied: {annot[4]}")
                        overwrite = input("Overwrite? (y/n): ").strip().lower()
                        if overwrite != 'y':
                            continue

                    response_text = input("Your response: ").strip()
                    if not response_text:
                        print("Response cannot be empty.")
                        continue

                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('''
                        UPDATE submission_annotations
                        SET student_response = ?, updated_at = ?
                        WHERE id = ?
                    ''', (response_text, now, aid))
                    conn.commit()
                    print("Response saved!")

            else:
                print("Could not retrieve submission content.")

            conn.close()

        except Exception as e:
            print(f"Error viewing student annotations: {e}")

    # ------------------------------------------------------------------
    # 6. annotation_summary
    # ------------------------------------------------------------------

    def annotation_summary(self):
        """Display summary statistics of annotations."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Total annotations
            cursor.execute('SELECT COUNT(*) FROM submission_annotations')
            total = cursor.fetchone()[0]

            if total == 0:
                print("\nNo annotations found.")
                conn.close()
                return

            # By category
            cursor.execute('''
                SELECT category, COUNT(*) FROM submission_annotations
                GROUP BY category ORDER BY COUNT(*) DESC
            ''')
            by_category = cursor.fetchall()

            # By reviewer
            cursor.execute('''
                SELECT reviewer_id, COUNT(*) FROM submission_annotations
                GROUP BY reviewer_id ORDER BY COUNT(*) DESC
            ''')
            by_reviewer = cursor.fetchall()

            # With student responses
            cursor.execute('SELECT COUNT(*) FROM submission_annotations WHERE student_response IS NOT NULL')
            with_responses = cursor.fetchone()[0]

            # Distinct annotated submissions
            cursor.execute('SELECT COUNT(DISTINCT submission_id) FROM submission_annotations')
            annotated_submissions = cursor.fetchone()[0]

            conn.close()

            # Display
            print("\nAnnotation Summary")
            print("=" * 50)
            print(f"  Total annotations:      {total}")
            print(f"  Annotated submissions:  {annotated_submissions}")
            print(f"  Student responses:      {with_responses}")
            response_rate = (with_responses / total * 100) if total > 0 else 0
            print(f"  Response rate:          {response_rate:.1f}%")

            print("\nBy Category:")
            print("-" * 30)
            for category, count in by_category:
                bar = '#' * min(count, 40)
                print(f"  {category:<12} {count:>5}  {bar}")

            print("\nBy Reviewer:")
            print("-" * 30)
            for reviewer_id, count in by_reviewer:
                print(f"  {reviewer_id:<20} {count:>5}")

        except Exception as e:
            print(f"Error generating annotation summary: {e}")

    # ------------------------------------------------------------------
    # 7. export_annotations
    # ------------------------------------------------------------------

    def export_annotations(self):
        """Export annotations for a submission to a text file."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            submission_id = self._select_submission(cursor)
            if not submission_id:
                conn.close()
                return

            cursor.execute('''
                SELECT id, line_number, category, comment, student_response, reviewer_id, created_at
                FROM submission_annotations
                WHERE submission_id = ?
                ORDER BY line_number, created_at
            ''', (submission_id,))
            annotations = cursor.fetchall()
            conn.close()

            if not annotations:
                print("\nNo annotations found for this submission.")
                return

            # Determine output path
            default_filename = f"annotations_submission_{submission_id}.txt"
            default_path = os.path.join(self.submission_dir, default_filename)
            export_path = input(f"Export path [{default_path}]: ").strip() or default_path

            # Build export content
            output_lines = []
            output_lines.append(f"Annotation Export - Submission {submission_id}")
            output_lines.append(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            output_lines.append("=" * 60)
            output_lines.append("")

            # Include submission text if available
            text = self._get_submission_text(submission_id)
            if text:
                output_lines.append("SUBMISSION CONTENT:")
                output_lines.append("-" * 60)
                for i, line in enumerate(text.split('\n'), 1):
                    output_lines.append(f"  {i:4d} | {line}")
                output_lines.append("")
                output_lines.append("ANNOTATIONS:")
                output_lines.append("-" * 60)

            for annot in annotations:
                annot_id, line_num, category, comment, student_response, reviewer_id, created_at = annot
                date_str = created_at[:10] if created_at else 'N/A'
                output_lines.append(
                    f"Line {line_num} [{category.upper()}] (by {reviewer_id}, {date_str})"
                )
                output_lines.append(f"  {comment}")
                if student_response:
                    output_lines.append(f"  Student reply: {student_response}")
                output_lines.append("")

            output_lines.append("=" * 60)

            # Category summary
            cat_counts = {}
            for annot in annotations:
                cat = annot[2]
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
            summary_parts = [f"{cat}: {cnt}" for cat, cnt in sorted(cat_counts.items())]
            output_lines.append(f"Total annotations: {len(annotations)}")
            output_lines.append(f"Breakdown: {', '.join(summary_parts)}")

            # Ensure output directory exists
            os.makedirs(os.path.dirname(export_path) if os.path.dirname(export_path) else '.', exist_ok=True)

            with open(export_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(output_lines))

            print(f"\nAnnotations exported to: {export_path}")

        except Exception as e:
            print(f"Error exporting annotations: {e}")
