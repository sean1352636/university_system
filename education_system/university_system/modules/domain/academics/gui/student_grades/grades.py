"""
Grades and Transcript mixins - detailed grade table and printable transcript.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime
import logging

from education_system.university_system.modules.domain.academics.gui.student_grades.common_imports import (
    get_connection,
    format_grade,
    COLORS,
)

# Backend GPA calculation
try:
    from education_system.university_system.modules.domain.academics.grading.grade_calculation import (
        calculate_student_gpa,
        letter_to_gpa,
    )
except ImportError:
    calculate_student_gpa = None
    letter_to_gpa = None

logger = logging.getLogger(__name__)

# Grade-to-letter mapping used when the stored grade is numeric
_LETTER_THRESHOLDS = [
    (97, 'A+'), (93, 'A'), (90, 'A-'),
    (87, 'B+'), (83, 'B'), (80, 'B-'),
    (77, 'C+'), (73, 'C'), (70, 'C-'),
    (67, 'D+'), (63, 'D'), (60, 'D-'),
    (0, 'F'),
]


def _to_letter(grade):
    """Convert a numeric grade to a letter grade; pass-through if already a letter."""
    if grade is None:
        return 'N/A'
    try:
        numeric = float(grade)
        for threshold, letter in _LETTER_THRESHOLDS:
            if numeric >= threshold:
                return letter
        return 'F'
    except (ValueError, TypeError):
        return str(grade)


def _gpa_points(grade):
    """Return GPA point value for a grade."""
    if letter_to_gpa is not None:
        letter = _to_letter(grade)
        return letter_to_gpa(letter)
    return 0.0


class GradesMixin:
    """Displays a detailed grades table with refresh support."""

    def show_grades_table(self, parent):
        """
        Render the grades Treeview inside *parent*.

        Args:
            parent: Parent frame to render into
        """
        # Title
        header = ttk.Frame(parent)
        header.pack(fill='x', padx=10, pady=(10, 0))
        ttk.Label(
            header,
            text='My Grades',
            font=('Arial', 14, 'bold'),
            foreground=COLORS['primary'],
        ).pack(side='left')

        ttk.Button(
            header,
            text='Refresh',
            command=lambda: self._refresh_grades(parent),
        ).pack(side='right')

        # Treeview
        columns = ('Module Code', 'Module Name', 'Grade', 'Letter Grade', 'GPA Points')
        col_widths = {'Module Code': 120, 'Module Name': 250, 'Grade': 80,
                      'Letter Grade': 100, 'GPA Points': 100}

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self._grades_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', height=15,
        )
        for col in columns:
            self._grades_tree.heading(col, text=col)
            self._grades_tree.column(col, width=col_widths.get(col, 100), anchor='w')

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self._grades_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self._grades_tree.xview)
        self._grades_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._grades_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self._populate_grades_tree()

    def _populate_grades_tree(self):
        """Fetch grades from module_grades + assignment_submissions and populate the Treeview."""
        for item in self._grades_tree.get_children():
            self._grades_tree.delete(item)

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Module grades (traditional)
                cursor.execute(
                    '''SELECT mg.module_code, m.module_name, mg.final_grade
                       FROM module_grades mg
                       JOIN modules m ON mg.module_code = m.module_code
                       WHERE mg.student_id = ?''',
                    (self.student_id,),
                )
                module_rows = cursor.fetchall()

                # Assignment submission grades (per-assignment, not averaged)
                cursor.execute(
                    '''SELECT a.module_code, a.title, sub.grade
                       FROM assignment_submissions sub
                       JOIN assignments a ON sub.assignment_id = a.id
                       WHERE sub.student_id = ? AND sub.grade IS NOT NULL
                       ORDER BY sub.graded_date DESC''',
                    (self.student_id,),
                )
                assignment_rows = cursor.fetchall()

            all_rows = list(module_rows) + list(assignment_rows)

            if not all_rows:
                self._grades_tree.insert('', 'end', values=('--', 'No grades found', '--', '--', '--'))
                return

            for code_or_module, name, grade in all_rows:
                letter = _to_letter(grade)
                points = _gpa_points(grade)
                self._grades_tree.insert('', 'end', values=(
                    code_or_module,
                    name,
                    format_grade(grade),
                    letter,
                    f'{points:.2f}',
                ))

        except Exception as e:
            logger.error(f'Error loading grades: {e}')
            messagebox.showerror('Error', f'Failed to load grades: {e}')

    def _refresh_grades(self, parent):
        """Clear and re-populate the grades table."""
        self._populate_grades_tree()


class TranscriptMixin:
    """Displays a formatted academic transcript with export capability."""

    def show_transcript(self, parent):
        """
        Render a read-only transcript view inside *parent*.

        Args:
            parent: Parent frame to render into
        """
        # Title
        header = ttk.Frame(parent)
        header.pack(fill='x', padx=10, pady=(10, 0))
        ttk.Label(
            header,
            text='Academic Transcript',
            font=('Arial', 14, 'bold'),
            foreground=COLORS['primary'],
        ).pack(side='left')

        ttk.Button(
            header,
            text='Export',
            command=lambda: self._export_transcript(),
        ).pack(side='right')

        # Scrolled text area
        self._transcript_text = scrolledtext.ScrolledText(
            parent, wrap='word', font=('Courier', 10), state='disabled',
        )
        self._transcript_text.pack(fill='both', expand=True, padx=10, pady=10)

        self._render_transcript()

    def _render_transcript(self):
        """Build the transcript text and display it."""
        text = self._build_transcript_text()
        self._transcript_text.configure(state='normal')
        self._transcript_text.delete('1.0', 'end')
        self._transcript_text.insert('1.0', text)
        self._transcript_text.configure(state='disabled')

    def _build_transcript_text(self) -> str:
        """
        Query the database and format the transcript as plain text.

        Returns:
            Formatted transcript string
        """
        lines = []
        separator = '=' * 60

        # Header
        student_name = self._get_student_name()
        lines.append(separator)
        lines.append('ACADEMIC TRANSCRIPT')
        lines.append(separator)
        lines.append(f'Student: {student_name}')
        lines.append(f'Student ID: {self.student_id}')
        lines.append(f'Date: {datetime.now().strftime("%Y-%m-%d")}')
        lines.append(separator)
        lines.append('')

        # Grade table header
        lines.append(f'{"Module Code":<14} {"Module Name":<30} {"Grade":<10} {"Letter":<10} {"Points":<8}')
        lines.append('-' * 72)

        gpa = None
        total_modules = 0
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Module grades
                cursor.execute(
                    '''SELECT mg.module_code, m.module_name, mg.final_grade
                       FROM module_grades mg
                       JOIN modules m ON mg.module_code = m.module_code
                       WHERE mg.student_id = ?''',
                    (self.student_id,),
                )
                module_rows = cursor.fetchall()

                # Assignment submission grades
                cursor.execute(
                    '''SELECT a.module_code, a.title, sub.grade
                       FROM assignment_submissions sub
                       JOIN assignments a ON sub.assignment_id = a.id
                       WHERE sub.student_id = ? AND sub.grade IS NOT NULL
                       ORDER BY sub.graded_date DESC''',
                    (self.student_id,),
                )
                assignment_rows = cursor.fetchall()

            rows = list(module_rows) + list(assignment_rows)

            if not rows:
                lines.append('No grade records found.')
            else:
                total_points = 0.0
                for code, name, grade in rows:
                    letter = _to_letter(grade)
                    points = _gpa_points(grade)
                    total_points += points
                    total_modules += 1
                    lines.append(
                        f'{code:<14} {name:<30} {format_grade(grade):<10} {letter:<10} {points:<8.2f}'
                    )

                if total_modules > 0:
                    gpa = total_points / total_modules

        except Exception as e:
            logger.error(f'Error building transcript: {e}')
            lines.append(f'Error retrieving grades: {e}')

        # Summary
        lines.append('')
        lines.append('-' * 72)
        lines.append(f'Total Modules: {total_modules}')
        if gpa is not None:
            lines.append(f'Cumulative GPA: {gpa:.2f}')
        else:
            lines.append('Cumulative GPA: N/A')
        lines.append(separator)

        return '\n'.join(lines)

    def _get_student_name(self) -> str:
        """Retrieve the student's full name from the database."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT first_name, middle_name, last_name
                       FROM students WHERE student_id = ?''',
                    (self.student_id,),
                )
                row = cursor.fetchone()
                if row:
                    first, middle, last = row
                    middle_str = f' {middle} ' if middle else ' '
                    return f'{first}{middle_str}{last}'
        except Exception as e:
            logger.error(f'Error fetching student name: {e}')
        return str(self.student_id)

    def _export_transcript(self):
        """Save the transcript to a text file chosen by the user."""
        filepath = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
            initialfile=f'transcript_{self.student_id}.txt',
        )
        if not filepath:
            return

        try:
            text = self._build_transcript_text()
            with open(filepath, 'w', encoding='utf-8') as fh:
                fh.write(text)
            messagebox.showinfo('Export Successful', f'Transcript saved to:\n{filepath}')
        except Exception as e:
            logger.error(f'Error exporting transcript: {e}')
            messagebox.showerror('Export Error', f'Failed to save transcript: {e}')
