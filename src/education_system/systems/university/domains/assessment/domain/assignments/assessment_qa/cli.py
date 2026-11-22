"""CLI for assessment QA — the same features as the GUI's Assessment QA screen."""
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa.service import (
    CLASH_THRESHOLD,
    CLASH_WINDOW_DAYS,
    FEEDBACK_TURNAROUND_WORKING_DAYS,
    PASS_MARK,
    AssessmentQAError,
    AssessmentQAService,
)


class AssessmentQAMixin:
    """Mixin providing anonymity, moderation, release, NS and reassessment menus."""

    def _qa_service(self):
        return AssessmentQAService(self.db_path)

    def _qa_user(self):
        user = getattr(self.auth, 'current_user', None) or {}
        return user.get('username') or str(user.get('id') or '')

    def _qa_pick_assignment(self):
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT id, module_code, title, due_date FROM assignments "
                "WHERE COALESCE(is_active, 1) = 1 ORDER BY due_date DESC").fetchall()
        finally:
            conn.close()
        if not rows:
            print("No assignments.")
            return None
        print(f"\n{'ID':<5} {'Module':<12} {'Title':<40} {'Due':<16}")
        print("-" * 75)
        for aid, module, title, due in rows:
            print(f"{aid:<5} {str(module)[:11]:<12} {str(title)[:39]:<40} {str(due)[:16]:<16}")
        choice = input("\nAssignment ID: ").strip()
        if not choice.isdigit() or int(choice) not in {r[0] for r in rows}:
            print("Invalid assignment ID.")
            return None
        return int(choice)

    def _qa_try(self, action):
        try:
            return action()
        except AssessmentQAError as e:
            print(f"Refused: {e}")
        except Exception as e:
            print(f"Error: {e}")
        return None

    def release_due_grades(self):
        """Release assignments whose release date has passed (run at menu start)."""
        try:
            outcome = self._qa_service().release_due(released_by=self._qa_user() or "scheduled release")
        except Exception:
            return
        for aid, r in outcome.items():
            if "released" in r:
                print(f"Released grades for assignment {aid} (release date reached).")

    # ── settings ────────────────────────────────────────────────────────

    def qa_assignment_settings(self):
        aid = self._qa_pick_assignment()
        if not aid:
            return
        qa = self._qa_service()
        a = qa.get_settings(aid)
        print("\nPress Enter to keep the current value.")
        prompts = [
            ("assessment_kind", "Assessment type (summative/formative)"),
            ("module_weight_pct", "Module weighting % (blank on all = equal weights)"),
            ("anonymous_marking", "Anonymous marking (y/n)"),
            ("word_limit", "Word limit (0 = none)"),
            ("word_limit_tolerance_pct", "Tolerance over limit %"),
            ("word_limit_penalty_pct", "Penalty if exceeded (percentage points)"),
            ("feedback_due_date", f"Feedback due YYYY-MM-DD (default {FEEDBACK_TURNAROUND_WORKING_DAYS} working days)"),
            ("grade_release_date", "Grade release date YYYY-MM-DD (blank = by hand)"),
            ("moderation_required", "Moderation required (y/n)"),
            ("moderation_sample_pct", "Moderation sample %"),
        ]
        changes = {}
        for key, label in prompts:
            current = a.get(key)
            shown = ("y" if current else "n") if key in ("anonymous_marking", "moderation_required") else current
            answer = input(f"{label} [{'' if shown is None else shown}]: ").strip()
            if not answer:
                continue
            if key in ("anonymous_marking", "moderation_required"):
                changes[key] = answer.lower().startswith('y')
            elif answer == "-":
                changes[key] = None
            else:
                changes[key] = answer
        if changes and self._qa_try(lambda: qa.update_settings(aid, **changes)):
            print("Settings saved.")
        a = qa.get_settings(aid)
        total = qa.module_weight_total(a["module_code"])
        print(f"Feedback due: {a.get('effective_feedback_due') or '—'}; "
              f"module {a['module_code']} weightings total {total:g}%"
              + (" (should be 100%)" if total and abs(total - 100) > 0.01 else ""))

    # ── moderation ──────────────────────────────────────────────────────

    def qa_moderation(self):
        aid = self._qa_pick_assignment()
        if not aid:
            return
        qa = self._qa_service()
        while True:
            rows = qa.moderation_rows(aid)
            print(f"\n{'#':<5} {'Student':<20} {'First':>7} {'Second':>7} {'Diff':>6} {'Agreed':>7}  Status")
            print("-" * 70)
            for r in rows:
                f = lambda v: "—" if v is None else f"{v:.1f}"
                print(f"{r['id']:<5} {str(r['label'])[:19]:<20} {f(r['first_mark']):>7} {f(r['second_mark']):>7} "
                      f"{f(r['difference']):>6} {f(r['agreed_mark']):>7}  {r['status']}")
            print("\n1. Draw sample  2. Second mark  3. Agree mark  4. Complete moderation  0. Back")
            choice = input("Choice: ").strip()
            if choice == '1':
                if self._qa_try(lambda: qa.draw_moderation_sample(aid, drawn_by=self._qa_user())):
                    print("Sample drawn.")
            elif choice in ('2', '3'):
                mid = input("Moderation #: ").strip()
                mark = input("Mark (%): ").strip()
                if not mid.isdigit():
                    print("Invalid #.")
                    continue
                notes = input("Comments (optional): ").strip() or None
                if choice == '2':
                    self._qa_try(lambda: qa.record_second_mark(int(mid), mark, self._qa_user(), notes))
                else:
                    self._qa_try(lambda: qa.agree_mark(int(mid), mark, self._qa_user(), notes))
            elif choice == '4':
                if self._qa_try(lambda: qa.complete_moderation(aid, self._qa_user())) is not None:
                    print("Moderation complete.")
            elif choice == '0':
                return

    # ── release ─────────────────────────────────────────────────────────

    def qa_release_grades(self):
        aid = self._qa_pick_assignment()
        if not aid:
            return
        qa = self._qa_service()
        blockers = qa.release_blockers(aid)
        date_only = blockers and all(b.startswith("Release date") for b in blockers)
        if blockers and not date_only:
            print("Not ready to release:")
            for b in blockers:
                print(f"  - {b}")
            return
        ignore = False
        if date_only:
            print(blockers[0])
            ignore = input("Release now anyway? (y/n): ").strip().lower() == 'y'
            if not ignore:
                return
        if input("Release every mark on this assignment to students? (y/n): ").strip().lower() != 'y':
            return
        r = self._qa_try(lambda: qa.release_grades(aid, self._qa_user(), ignore_release_date=ignore))
        if r:
            print(f"Released {r['released']} mark(s); {r['non_submissions']} non-submission(s) counted as 0.")

    # ── non-submissions ─────────────────────────────────────────────────

    def qa_non_submissions(self):
        aid = self._qa_pick_assignment()
        if not aid:
            return
        qa = self._qa_service()
        missing = qa.find_non_submissions(aid)
        recorded = qa.non_submissions(aid)
        print(f"\nRecorded non-submissions: {len(recorded)}")
        for r in recorded:
            print(f"  {r['student_id']}  {r.get('first_name') or ''} {r.get('last_name') or ''}  ({r['code']})")
        new = [m for m in missing if m["student_id"] not in {r["student_id"] for r in recorded}]
        print(f"Not yet recorded (deadline passed, nothing submitted): {len(new)}")
        for m in new:
            print(f"  {m['student_id']}  deadline {m['deadline']}")
        print("\n1. Record all  2. Remove one  0. Back")
        choice = input("Choice: ").strip()
        if choice == '1':
            n = self._qa_try(lambda: qa.record_non_submissions(aid, self._qa_user()))
            if n is not None:
                print(f"{n} non-submission(s) recorded.")
        elif choice == '2':
            sid = input("Student ID: ").strip()
            if sid:
                self._qa_try(lambda: qa.void_non_submission(aid, sid))
                print("Removed.")

    # ── reassessment ────────────────────────────────────────────────────

    def qa_reassessment(self):
        aid = self._qa_pick_assignment()
        if not aid:
            return
        qa = self._qa_service()
        candidates = self._qa_try(lambda: qa.reassessment_candidates(aid))
        if candidates is None:
            return
        for r in qa.reassessments(aid):
            mark = "—" if r["mark"] is None else f"{r['mark']:.1f}%"
            print(f"  already set: {r['student_id']} {r['attempt_type']} due {str(r['due_date'])[:16]} mark {mark}")
        if not candidates:
            print("No fails or non-submissions awaiting reassessment.")
            return
        print(f"\nFails (under {PASS_MARK:g}%) and non-submissions. Referral is capped at "
              f"{PASS_MARK:g}%; deferral (MC-granted) is uncapped.")
        for i, c in enumerate(candidates, 1):
            print(f"{i:>3}. {c['student_id']:<12} {float(c['mark']):>5.1f}%  {c['reason']:<15} suggested: {c['suggested_type']}")
        picks = input("\nNumbers to reassess (comma-separated, 'all'): ").strip().lower()
        if not picks:
            return
        chosen = candidates if picks == 'all' else [
            candidates[int(p) - 1] for p in picks.split(',') if p.strip().isdigit()
            and 0 < int(p) <= len(candidates)]
        students = []
        for c in chosen:
            kind = input(f"{c['student_id']}: referral or deferral [{c['suggested_type']}]: ").strip().lower()
            students.append({"student_id": c["student_id"],
                             "attempt_type": kind or c["suggested_type"],
                             "mc_claim_id": c.get("mc_claim_id")})
        due = input("Reassessment due date (YYYY-MM-DD HH:MM): ").strip()
        user = getattr(self.auth, 'current_user', None) or {}
        new_id = self._qa_try(lambda: qa.create_reassessment(aid, students, due, created_by=user.get('id')))
        if new_id:
            print(f"Reassessment created as assignment {new_id}; only those students can see it.")

    # ── reports ─────────────────────────────────────────────────────────

    def qa_feedback_turnaround(self):
        rows = self._qa_service().feedback_turnaround_report()
        if not rows:
            print("No unreleased assignments.")
            return
        print(f"\n{'ID':<5} {'Module':<12} {'Title':<34} {'Feedback due':<13} {'Marked':<8} State")
        print("-" * 90)
        for r in rows:
            state = "OVERDUE" if r["overdue"] else (
                f"{r['days_left']} day(s) left" if r["days_left"] is not None else "—")
            print(f"{r['id']:<5} {str(r['module_code'])[:11]:<12} {str(r['title'])[:33]:<34} "
                  f"{r['feedback_due'] or '—':<13} {r['marked']}/{r['submissions']:<6} {state}")

    def qa_deadline_clashes(self):
        rows = self._qa_service().clash_report()
        if not rows:
            print(f"No cohort has {CLASH_THRESHOLD}+ summative deadlines within {CLASH_WINDOW_DAYS} days.")
            return
        print(f"\n{'ID':<5} {'Module':<12} {'Title':<34} {'Due':<17} {'Students':>8} {'Most':>5}")
        print("-" * 85)
        for r in rows:
            print(f"{r['id']:<5} {str(r['module_code'])[:11]:<12} {str(r['title'])[:33]:<34} "
                  f"{str(r['due_date'])[:16]:<17} {r['students_affected']:>8} {r['worst']:>5}")
