"""
Database schema initialization for Course Evaluation System
"""

import sqlite3

from education_system.post_18.university_system.infrastructure.database.db import transaction


def initialize_evaluation_database():
    """Initialize all database tables for the Course Evaluation System"""

    with transaction() as conn:
        cursor = conn.cursor()

        # Evaluation Templates Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_templates (
                template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT NOT NULL,
                template_type TEXT NOT NULL,
                description TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                is_active INTEGER DEFAULT 1
            )
        ''')

        # Evaluation Questions Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                question_type TEXT NOT NULL,
                question_category TEXT,
                scale_min INTEGER DEFAULT 1,
                scale_max INTEGER DEFAULT 5,
                display_order INTEGER DEFAULT 0,
                is_required INTEGER DEFAULT 1,
                FOREIGN KEY (template_id) REFERENCES evaluation_templates(template_id) ON DELETE CASCADE
            )
        ''')

        # Course Evaluations Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS course_evaluations (
                evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT NOT NULL,
                academic_year TEXT NOT NULL,
                semester TEXT NOT NULL,
                instructor_id TEXT NOT NULL,
                template_id INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                response_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (template_id) REFERENCES evaluation_templates(template_id)
            )
        ''')

        # Evaluation Responses Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_responses (
                response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                student_id TEXT,
                is_complete INTEGER DEFAULT 0,
                is_anonymous INTEGER DEFAULT 1,
                time_taken_minutes INTEGER,
                submitted_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE
            )
        ''')

        # Evaluation Answers Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_answers (
                answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                response_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                answer_value TEXT,
                numeric_value REAL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (response_id) REFERENCES evaluation_responses(response_id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES evaluation_questions(question_id) ON DELETE CASCADE
            )
        ''')

        # Evaluation Results Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                average_score REAL,
                response_count INTEGER,
                calculated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES evaluation_questions(question_id) ON DELETE CASCADE,
                UNIQUE(evaluation_id, question_id)
            )
        ''')

        # --- Authoring extensions (features 1-8) ---

        # Question Bank — reusable questions across templates with tags
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_question_bank (
                bank_id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_text TEXT NOT NULL,
                question_type TEXT NOT NULL DEFAULT 'likert',
                question_category TEXT,
                scale_min INTEGER DEFAULT 1,
                scale_max INTEGER DEFAULT 5,
                options_json TEXT,
                department TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_question_tags (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                UNIQUE(bank_id, tag),
                FOREIGN KEY (bank_id) REFERENCES evaluation_question_bank(bank_id) ON DELETE CASCADE
            )
        ''')

        # Extended fields on evaluation_questions (best-effort ALTER)
        for col, ddl in [
            ('options_json',        "ALTER TABLE evaluation_questions ADD COLUMN options_json TEXT"),
            ('bank_id',             "ALTER TABLE evaluation_questions ADD COLUMN bank_id INTEGER"),
            ('parent_question_id',  "ALTER TABLE evaluation_questions ADD COLUMN parent_question_id INTEGER"),
            ('show_if_value',       "ALTER TABLE evaluation_questions ADD COLUMN show_if_value TEXT"),
            ('show_if_op',          "ALTER TABLE evaluation_questions ADD COLUMN show_if_op TEXT"),
            ('aria_label',          "ALTER TABLE evaluation_questions ADD COLUMN aria_label TEXT"),
        ]:
            try:
                cursor.execute(ddl)
            except sqlite3.OperationalError:
                pass

        # Per-locale translations of question text / aria-label
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_question_locales (
                locale_id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                locale TEXT NOT NULL,
                question_text TEXT NOT NULL,
                aria_label TEXT,
                options_json TEXT,
                UNIQUE(question_id, locale),
                FOREIGN KEY (question_id) REFERENCES evaluation_questions(question_id) ON DELETE CASCADE
            )
        ''')

        # Template version history — full snapshot + diff metadata
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_template_versions (
                version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                version_number INTEGER NOT NULL,
                snapshot_json TEXT NOT NULL,
                change_summary TEXT,
                changed_by TEXT,
                changed_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(template_id, version_number),
                FOREIGN KEY (template_id) REFERENCES evaluation_templates(template_id) ON DELETE CASCADE
            )
        ''')

        # Accessibility audit results per template
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_accessibility_audits (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                rule TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                question_id INTEGER,
                checked_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (template_id) REFERENCES evaluation_templates(template_id) ON DELETE CASCADE
            )
        ''')

        # --- Distribution & analytics extensions (features 9-25) ---

        # Best-effort additions to course_evaluations
        for ddl in [
            "ALTER TABLE course_evaluations ADD COLUMN auto_open INTEGER DEFAULT 0",
            "ALTER TABLE course_evaluations ADD COLUMN calendar_event_id INTEGER",
            "ALTER TABLE course_evaluations ADD COLUMN embargo_until_grades INTEGER DEFAULT 0",
            "ALTER TABLE course_evaluations ADD COLUMN grades_submitted_at TEXT",
            "ALTER TABLE course_evaluations ADD COLUMN estimated_minutes INTEGER",
        ]:
            try:
                cursor.execute(ddl)
            except sqlite3.OperationalError:
                pass

        # Reminder cadence (feature 10)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_reminders (
                reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                offset_days INTEGER NOT NULL,
                channel TEXT NOT NULL DEFAULT 'email',
                message TEXT,
                sent_at TEXT,
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE
            )
        ''')

        # Bulk invitations (feature 11) + tokens (feature 12)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_invitations (
                invite_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                recipient_id TEXT NOT NULL,
                cohort TEXT,
                token TEXT NOT NULL UNIQUE,
                used INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                used_at TEXT,
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE
            )
        ''')

        # Save-and-resume drafts (feature 15, 16)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_drafts (
                draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                respondent_token TEXT NOT NULL,
                answers_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(evaluation_id, respondent_token),
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE
            )
        ''')

        # Redaction rules (feature 18)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_redaction_rules (
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL,
                replacement TEXT NOT NULL DEFAULT '[redacted]',
                kind TEXT NOT NULL DEFAULT 'regex',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

        # Per-response quality flags (feature 25)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_response_flags (
                flag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                response_id INTEGER NOT NULL,
                flag TEXT NOT NULL,
                score REAL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (response_id) REFERENCES evaluation_responses(response_id) ON DELETE CASCADE
            )
        ''')

        # Per-question sentiment scoring cache (feature 24)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_sentiment (
                sentiment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                answer_id INTEGER NOT NULL UNIQUE,
                polarity REAL NOT NULL,
                label TEXT NOT NULL,
                FOREIGN KEY (answer_id) REFERENCES evaluation_answers(answer_id) ON DELETE CASCADE
            )
        ''')

        # Roster snapshot used to compute response rate (feature 20)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_rosters (
                roster_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                UNIQUE(evaluation_id, student_id),
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE
            )
        ''')

        # --- Workflow / integrations / compliance / admin (features 26-50) ---

        # 26: demographic dimensions linked to responses + k-anonymity threshold
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_demographics (
                demo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                response_id INTEGER NOT NULL,
                dimension TEXT NOT NULL,
                value TEXT NOT NULL,
                FOREIGN KEY (response_id) REFERENCES evaluation_responses(response_id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        # 27: custom dashboards (JSON layouts)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_dashboards (
                dashboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT '*',
                name TEXT NOT NULL,
                layout_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

        # 28: significance test cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_significance (
                sig_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                question_id INTEGER,
                comparison TEXT NOT NULL,
                n INTEGER NOT NULL,
                statistic REAL,
                p_value REAL,
                significant INTEGER,
                computed_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE
            )
        ''')

        # 29: You said / we did
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_youssaid_wedid (
                ysw_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER,
                theme TEXT NOT NULL,
                you_said TEXT NOT NULL,
                we_did TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                owner TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                resolved_at TEXT
            )
        ''')

        # 30: instructor reply box
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_instructor_replies (
                reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                theme TEXT,
                reply_text TEXT NOT NULL,
                posted_by TEXT,
                posted_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE
            )
        ''')

        # 31: department-head review queue with sign-off
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_review_queue (
                queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                reviewer TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                comment TEXT,
                signed_off_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE
            )
        ''')

        # 32: red-flag comment routing
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_red_flags (
                flag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                answer_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                pattern TEXT,
                routed_to TEXT,
                acknowledged INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (answer_id) REFERENCES evaluation_answers(answer_id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_red_flag_rules (
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                pattern TEXT NOT NULL,
                route_to TEXT NOT NULL
            )
        ''')

        # 33: improvement plan templates + instances
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_improvement_templates (
                imp_template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                body TEXT NOT NULL,
                trigger_below_score REAL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_improvement_plans (
                plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                template_id INTEGER,
                body TEXT NOT NULL,
                author TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE
            )
        ''')

        # 34-37: integrations (LMS / SIS / HR / calendar)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_lms_links (
                link_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                lms TEXT NOT NULL,
                deep_link_url TEXT NOT NULL,
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_sis_sync_log (
                sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                added INTEGER, removed INTEGER, total INTEGER,
                synced_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_hr_exports (
                export_id INTEGER PRIMARY KEY AUTOINCREMENT,
                instructor_id TEXT NOT NULL,
                academic_year TEXT NOT NULL,
                aggregate_json TEXT NOT NULL,
                exported_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_calendar_holds (
                hold_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                instructor_id TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE
            )
        ''')

        # 38: webhook subscribers + delivery log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_webhooks (
                hook_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT NOT NULL,
                url TEXT NOT NULL,
                secret TEXT,
                active INTEGER DEFAULT 1
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_webhook_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hook_id INTEGER,
                event TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

        # 39: anonymity audit log (id-vs-answer linkage attempts)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_anonymity_audit (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

        # 40: GDPR data-subject requests
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_gdpr_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_token TEXT NOT NULL,
                kind TEXT NOT NULL,
                payload_json TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT
            )
        ''')

        # 41: role-based redaction (which fields hidden per role)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_role_redactions (
                redaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                field TEXT NOT NULL,
                action TEXT NOT NULL DEFAULT 'hide'
            )
        ''')

        # 42: MFA-gated routes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_mfa_gates (
                gate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                route TEXT NOT NULL UNIQUE,
                required INTEGER DEFAULT 1
            )
        ''')

        # 43: retention policies
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_retention_policies (
                policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT NOT NULL,
                keep_days INTEGER NOT NULL,
                keep_aggregates INTEGER DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

        # 44: bulk-import jobs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_imports (
                import_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                rows_seen INTEGER, rows_imported INTEGER, rows_errored INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

        # 45: approval workflow
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_approvals (
                approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                stage TEXT NOT NULL DEFAULT 'draft',
                actor TEXT,
                comment TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (template_id) REFERENCES evaluation_templates(template_id) ON DELETE CASCADE
            )
        ''')

        # 46: A/B tests on question wording
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_ab_tests (
                ab_id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                variant_a TEXT NOT NULL,
                variant_b TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_ab_assignments (
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ab_id INTEGER NOT NULL,
                response_id INTEGER NOT NULL,
                variant CHAR(1) NOT NULL,
                UNIQUE(ab_id, response_id)
            )
        ''')

        # 47: soft-delete with restore
        for ddl in [
            "ALTER TABLE evaluation_templates ADD COLUMN deleted_at TEXT",
            "ALTER TABLE course_evaluations ADD COLUMN deleted_at TEXT",
        ]:
            try:
                cursor.execute(ddl)
            except sqlite3.OperationalError:
                pass

        # 49: bias-language audit findings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_bias_findings (
                finding_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER,
                question_id INTEGER,
                category TEXT NOT NULL,
                snippet TEXT NOT NULL,
                suggestion TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

        # 50: pulse / micro-surveys
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_pulses (
                pulse_id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT NOT NULL,
                question_text TEXT NOT NULL,
                question_type TEXT NOT NULL DEFAULT 'likert',
                cadence_days INTEGER NOT NULL DEFAULT 7,
                next_run TEXT,
                active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_pulse_responses (
                pulse_resp_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pulse_id INTEGER NOT NULL,
                respondent_hash TEXT NOT NULL,
                rating_value INTEGER,
                text_value TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (pulse_id) REFERENCES evaluation_pulses(pulse_id) ON DELETE CASCADE
            )
        ''')

        # Create indexes for better performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_eval_module
            ON course_evaluations(module_code, academic_year, semester)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_eval_instructor
            ON course_evaluations(instructor_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_response_evaluation
            ON evaluation_responses(evaluation_id)
        ''')

        print("✅ Course Evaluation database schema initialized successfully")


__all__ = ['initialize_evaluation_database']
