"""
Curriculum Design Manager

Provides functionality for:
- Programme management and approval
- Module-programme mapping
- Learning outcomes and alignment
- Syllabus building
- Programme approval workflows
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import json

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608


class CurriculumManager:
    """Manager for curriculum design and programme management."""

    # ==================== PROGRAMME CRUD ====================

    @staticmethod
    def create_programme(code: str, name: str, level: str = 'undergraduate',
                         department: str = None, total_credits: int = 360,
                         duration_years: int = 3, description: str = None,
                         created_by: str = None) -> int:
        """Create a new programme."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO programmes (
                    code, name, level, department, total_credits,
                    duration_years, description, created_by, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft')
            ''', (
                code, name, level, department, total_credits,
                duration_years, description, created_by,
            ))
            programme_id = cursor.lastrowid
            log_activity('create', 'programme', details={
                'programme_id': programme_id, 'code': code, 'name': name
            })
            return programme_id

    @staticmethod
    def get_programmes(status: str = None, department: str = None) -> List[Dict[str, Any]]:
        """Get programmes with optional filters."""
        with get_connection() as conn:
            query = 'SELECT * FROM programmes WHERE 1=1'
            params = []

            if status:
                query += ' AND status = ?'
                params.append(status)

            if department:
                query += ' AND department = ?'
                params.append(department)

            query += ' ORDER BY name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_programme(programme_id: int) -> Optional[Dict[str, Any]]:
        """Get a single programme by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM programmes WHERE programme_id = ?
            ''', (programme_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_programme(programme_id: int, **data) -> None:
        """Update programme fields."""
        if not data:
            return

        allowed_fields = {
            'name', 'level', 'department', 'total_credits',
            'duration_years', 'description', 'status'
        }

        fields = []
        values = []
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        fields.append('updated_at = CURRENT_TIMESTAMP')
        values.append(programme_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE programmes SET ' + ', '.join(fields) + ' WHERE programme_id = ?',
                values)
            log_activity('update', 'programme', details={
                'programme_id': programme_id, 'updated_fields': list(data.keys())
            })

    # ==================== MODULE MAPPING ====================

    @staticmethod
    def add_module_to_programme(programme_id: int, module_code: str,
                                module_name: str = None, year_of_study: int = 1,
                                semester: int = 1, is_core: bool = True,
                                credits: int = 20) -> int:
        """Add a module to a programme."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO programme_modules (
                    programme_id, module_code, module_name,
                    year_of_study, semester, is_core, credits
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                programme_id, module_code, module_name,
                year_of_study, semester, is_core, credits,
            ))
            mapping_id = cursor.lastrowid
            log_activity('create', 'programme_module', details={
                'mapping_id': mapping_id, 'programme_id': programme_id,
                'module_code': module_code
            })
            return mapping_id

    @staticmethod
    def remove_module_from_programme(mapping_id: int) -> None:
        """Remove a module mapping."""
        with transaction() as conn:
            conn.execute('''
                DELETE FROM programme_modules WHERE mapping_id = ?
            ''', (mapping_id,))
            log_activity('delete', 'programme_module', details={
                'mapping_id': mapping_id
            })

    @staticmethod
    def get_programme_structure(programme_id: int) -> Dict[str, Any]:
        """Get programme modules grouped by year and semester."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM programme_modules
                WHERE programme_id = ?
                ORDER BY year_of_study, semester
            ''', (programme_id,)).fetchall()

            years = {}
            total_credits = 0

            for row in rows:
                module = dict(row)
                year = module['year_of_study']
                sem = module['semester']
                total_credits += module.get('credits', 0) or 0

                if year not in years:
                    years[year] = {'semesters': {}}
                if sem not in years[year]['semesters']:
                    years[year]['semesters'][sem] = []

                years[year]['semesters'][sem].append(module)

            return {'years': years, 'total_credits': total_credits}

    @staticmethod
    def get_programme_modules(programme_id: int) -> List[Dict[str, Any]]:
        """Get flat list of modules for a programme."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM programme_modules
                WHERE programme_id = ?
                ORDER BY year_of_study, semester
            ''', (programme_id,)).fetchall()
            return [dict(row) for row in rows]

    # ==================== LEARNING OUTCOMES ====================

    @staticmethod
    def create_outcome(code: str, description: str, programme_id: int = None,
                       module_code: str = None, bloom_level: str = 'understand',
                       outcome_type: str = 'programme') -> int:
        """Create a learning outcome."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO learning_outcomes (
                    code, description, programme_id, module_code,
                    bloom_level, outcome_type
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                code, description, programme_id, module_code,
                bloom_level, outcome_type,
            ))
            outcome_id = cursor.lastrowid
            log_activity('create', 'learning_outcome', details={
                'outcome_id': outcome_id, 'code': code, 'outcome_type': outcome_type
            })
            return outcome_id

    @staticmethod
    def get_programme_outcomes(programme_id: int) -> List[Dict[str, Any]]:
        """Get programme-level learning outcomes."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM learning_outcomes
                WHERE programme_id = ? AND outcome_type = 'programme'
                ORDER BY code
            ''', (programme_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_module_outcomes(module_code: str) -> List[Dict[str, Any]]:
        """Get module-level outcomes."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM learning_outcomes
                WHERE module_code = ? AND outcome_type = 'module'
                ORDER BY code
            ''', (module_code,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_outcome(outcome_id: int, **data) -> None:
        """Update a learning outcome."""
        if not data:
            return

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('outcome_id', 'created_at'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        fields.append('updated_at = CURRENT_TIMESTAMP')
        values.append(outcome_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE learning_outcomes SET ' + ', '.join(fields) + ' WHERE outcome_id = ?',
                values)
            log_activity('update', 'learning_outcome', details={
                'outcome_id': outcome_id, 'updated_fields': list(data.keys())
            })

    @staticmethod
    def delete_outcome(outcome_id: int) -> None:
        """Delete a learning outcome and its alignments."""
        with transaction() as conn:
            conn.execute('''
                DELETE FROM outcome_alignments
                WHERE programme_outcome_id = ? OR module_outcome_id = ?
            ''', (outcome_id, outcome_id))

            conn.execute('''
                DELETE FROM learning_outcomes WHERE outcome_id = ?
            ''', (outcome_id,))

            log_activity('delete', 'learning_outcome', details={
                'outcome_id': outcome_id
            })

    # ==================== OUTCOME ALIGNMENT ====================

    @staticmethod
    def create_alignment(programme_outcome_id: int, module_outcome_id: int,
                         alignment_strength: str = 'moderate',
                         notes: str = None) -> int:
        """Create an outcome alignment."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO outcome_alignments (
                    programme_outcome_id, module_outcome_id,
                    alignment_strength, notes
                ) VALUES (?, ?, ?, ?)
            ''', (
                programme_outcome_id, module_outcome_id,
                alignment_strength, notes,
            ))
            alignment_id = cursor.lastrowid
            log_activity('create', 'outcome_alignment', details={
                'alignment_id': alignment_id,
                'programme_outcome_id': programme_outcome_id,
                'module_outcome_id': module_outcome_id
            })
            return alignment_id

    @staticmethod
    def get_alignment_matrix(programme_id: int) -> Dict[str, Any]:
        """Get the alignment matrix for a programme."""
        with get_connection() as conn:
            # 1. Get all programme outcomes
            po_rows = conn.execute('''
                SELECT * FROM learning_outcomes
                WHERE programme_id = ? AND outcome_type = 'programme'
                ORDER BY code
            ''', (programme_id,)).fetchall()
            programme_outcomes = [dict(row) for row in po_rows]

            # 2. Get all modules with their outcomes
            mod_rows = conn.execute('''
                SELECT DISTINCT module_code, module_name
                FROM programme_modules
                WHERE programme_id = ?
                ORDER BY year_of_study, semester
            ''', (programme_id,)).fetchall()
            modules = [dict(row) for row in mod_rows]

            # Get module outcomes for each module
            module_codes = [m['module_code'] for m in modules]
            module_outcomes = {}
            for mc in module_codes:
                mo_rows = conn.execute('''
                    SELECT * FROM learning_outcomes
                    WHERE module_code = ? AND outcome_type = 'module'
                ''', (mc,)).fetchall()
                module_outcomes[mc] = [dict(row) for row in mo_rows]

            # 3. Build matrix: rows=programme_outcomes, columns=modules
            # 4. For each cell, lookup alignment
            matrix = {}
            for po in programme_outcomes:
                po_id = po['outcome_id']
                matrix[po_id] = {}
                for mc in module_codes:
                    # Check if any module outcome for this module aligns with this programme outcome
                    mo_ids = [mo['outcome_id'] for mo in module_outcomes.get(mc, [])]
                    if mo_ids:
                        placeholders = ', '.join('?' * len(mo_ids))
                        alignment_row = conn.execute(
                            'SELECT alignment_strength FROM outcome_alignments '
                            'WHERE programme_outcome_id = ? '
                            'AND module_outcome_id IN (' + placeholders + ')',
                            [po_id] + mo_ids
                        ).fetchone()
                        matrix[po_id][mc] = alignment_row['alignment_strength'] if alignment_row else None
                    else:
                        matrix[po_id][mc] = None

            return {
                'programme_outcomes': programme_outcomes,
                'modules': modules,
                'matrix': matrix
            }

    @staticmethod
    def delete_alignment(alignment_id: int) -> None:
        """Delete an alignment."""
        with transaction() as conn:
            conn.execute('''
                DELETE FROM outcome_alignments WHERE alignment_id = ?
            ''', (alignment_id,))
            log_activity('delete', 'outcome_alignment', details={
                'alignment_id': alignment_id
            })

    # ==================== SYLLABUS BUILDER ====================

    @staticmethod
    def create_syllabus(module_code: str, academic_year: str,
                        content_json: str, template_id: int = None,
                        created_by: str = None) -> int:
        """Create a syllabus."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO syllabi (
                    module_code, academic_year, content_json,
                    template_id, created_by, status
                ) VALUES (?, ?, ?, ?, ?, 'draft')
            ''', (
                module_code, academic_year, content_json,
                template_id, created_by,
            ))
            syllabus_id = cursor.lastrowid
            log_activity('create', 'syllabus', details={
                'syllabus_id': syllabus_id, 'module_code': module_code,
                'academic_year': academic_year
            })
            return syllabus_id

    @staticmethod
    def get_syllabus(module_code: str,
                     academic_year: str = None) -> Optional[Dict[str, Any]]:
        """Get a syllabus. If academic_year not specified, get the latest."""
        with get_connection() as conn:
            if academic_year:
                row = conn.execute('''
                    SELECT * FROM syllabi
                    WHERE module_code = ? AND academic_year = ?
                ''', (module_code, academic_year)).fetchone()
            else:
                row = conn.execute('''
                    SELECT * FROM syllabi
                    WHERE module_code = ?
                    ORDER BY academic_year DESC
                    LIMIT 1
                ''', (module_code,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_syllabus(syllabus_id: int, content_json: str = None,
                        status: str = None) -> None:
        """Update a syllabus."""
        fields = []
        values = []

        if content_json is not None:
            fields.append('content_json = ?')
            values.append(content_json)

        if status is not None:
            fields.append('status = ?')
            values.append(status)

        if not fields:
            return

        fields.append('updated_at = CURRENT_TIMESTAMP')
        values.append(syllabus_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE syllabi SET ' + ', '.join(fields) + ' WHERE syllabus_id = ?',
                values)
            log_activity('update', 'syllabus', details={
                'syllabus_id': syllabus_id
            })

    @staticmethod
    def get_syllabus_templates(active_only: bool = True) -> List[Dict[str, Any]]:
        """Get syllabus templates."""
        with get_connection() as conn:
            if active_only:
                rows = conn.execute('''
                    SELECT * FROM syllabus_templates
                    WHERE is_active = 1
                    ORDER BY name
                ''').fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM syllabus_templates ORDER BY name
                ''').fetchall()
            return [dict(row) for row in rows]

    # ==================== APPROVAL WORKFLOW ====================

    @staticmethod
    def submit_for_approval(programme_id: int, submitted_by: str = None) -> None:
        """Submit a programme for approval."""
        with transaction() as conn:
            # 1. Update programme status to 'pending_approval'
            conn.execute('''
                UPDATE programmes
                SET status = 'pending_approval', updated_at = CURRENT_TIMESTAMP
                WHERE programme_id = ?
            ''', (programme_id,))

            # 2. Create programme_approvals entries for 3 levels
            for level in ('department', 'faculty', 'senate'):
                conn.execute('''
                    INSERT INTO programme_approvals (
                        programme_id, approval_level, status, submitted_by
                    ) VALUES (?, ?, 'pending', ?)
                ''', (programme_id, level, submitted_by))

            # 3. Log activity
            log_activity('update', 'programme', details={
                'programme_id': programme_id, 'action': 'submitted_for_approval',
                'submitted_by': submitted_by
            })

    @staticmethod
    def review_programme(approval_id: int, reviewer_id: str,
                         status: str, comments: str = None) -> None:
        """Review a programme approval."""
        with transaction() as conn:
            # 1. Update the approval record
            conn.execute('''
                UPDATE programme_approvals
                SET status = ?, reviewer_id = ?, comments = ?,
                    reviewed_date = ?
                WHERE approval_id = ?
            ''', (status, reviewer_id, comments,
                  datetime.now().isoformat(), approval_id))

            # Get the programme_id for this approval
            row = conn.execute('''
                SELECT programme_id FROM programme_approvals
                WHERE approval_id = ?
            ''', (approval_id,)).fetchone()

            if row:
                programme_id = row['programme_id']

                if status == 'approved':
                    # 2. Check if all levels are approved
                    pending = conn.execute('''
                        SELECT COUNT(*) as cnt FROM programme_approvals
                        WHERE programme_id = ? AND status != 'approved'
                    ''', (programme_id,)).fetchone()

                    if pending['cnt'] == 0:
                        conn.execute('''
                            UPDATE programmes
                            SET status = 'approved', updated_at = CURRENT_TIMESTAMP
                            WHERE programme_id = ?
                        ''', (programme_id,))

                elif status == 'rejected':
                    # 3. If rejected, update programme status
                    conn.execute('''
                        UPDATE programmes
                        SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
                        WHERE programme_id = ?
                    ''', (programme_id,))

            # 4. Log activity
            log_activity('update', 'programme_approval', details={
                'approval_id': approval_id, 'reviewer_id': reviewer_id,
                'status': status
            })

    @staticmethod
    def get_pending_approvals(reviewer_id: str = None) -> List[Dict[str, Any]]:
        """Get pending programme approvals."""
        with get_connection() as conn:
            query = '''
                SELECT pa.*, p.code as programme_code, p.name as programme_name,
                       p.department, p.level
                FROM programme_approvals pa
                JOIN programmes p ON pa.programme_id = p.programme_id
                WHERE pa.status = 'pending'
            '''
            params = []

            if reviewer_id:
                query += ' AND (pa.reviewer_id = ? OR pa.reviewer_id IS NULL)'
                params.append(reviewer_id)

            query += ' ORDER BY pa.programme_id, pa.approval_level'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
