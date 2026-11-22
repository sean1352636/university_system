"""Grade CLI: exam marking control, module results and classification.

The same features as Grade Tracking's "Exam Marking & Results" screen; the
rules are in ``university/application``.
"""
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.application.assessment import classification
from education_system.systems.university.application.exams import marking as exam_marking
from education_system.systems.university.application.assessment import module_results
from education_system.systems.university.application.exams.marking import ExamMarkingError


def _pick_assessment(conn):
    rows = conn.execute(
        "SELECT assessment_id, module_code, assessment_name, assessment_type, marks_released_at "
        "FROM assessments WHERE COALESCE(status, 'Active') <> 'Archived' "
        "ORDER BY module_code, due_date").fetchall()
    if not rows:
        print("No exams or tests.")
        return None
    print(f"\n{'ID':<5} {'Module':<12} {'Name':<36} {'Type':<12} Released")
    print("-" * 78)
    for r in rows:
        print(f"{r[0]:<5} {str(r[1])[:11]:<12} {str(r[2])[:35]:<36} {str(r[3])[:11]:<12} "
              f"{'yes' if r[4] else 'no'}")
    choice = input("\nAssessment ID: ").strip()
    if not choice.isdigit() or int(choice) not in {r[0] for r in rows}:
        print("Invalid assessment ID.")
        return None
    return int(choice)


def _attempt(conn, action, done=None):
    try:
        result = action()
        conn.commit()
    except (ExamMarkingError, ValueError) as e:
        conn.rollback()
        print(f"Refused: {e}")
        return None
    if done:
        print(done(result) if callable(done) else done)
    return result if result is not None else True


def exam_settings_menu():
    with get_connection() as conn:
        aid = _pick_assessment(conn)
        if not aid:
            return
        a = exam_marking.get_settings(conn, aid)
        anon = input(f"Anonymous marking (y/n) [{'y' if a.get('anonymous_marking') else 'n'}]: ").strip().lower()
        mod = input(f"Moderation required (y/n) [{'y' if a.get('moderation_required') else 'n'}]: ").strip().lower()
        pct = input(f"Moderation sample % [{a.get('moderation_sample_pct') or 10:g}]: ").strip()
        fields = {}
        if anon in ('y', 'n'):
            fields['anonymous_marking'] = anon == 'y'
        if mod in ('y', 'n'):
            fields['moderation_required'] = mod == 'y'
        if pct:
            fields['moderation_sample_pct'] = pct
        _attempt(conn, lambda: exam_marking.update_settings(conn, aid, **fields), "Settings saved.")


def absences_menu():
    with get_connection() as conn:
        aid = _pick_assessment(conn)
        if not aid:
            return
        missing = exam_marking.unmarked_students(conn, aid)
        if not missing:
            print("Every enrolled student has a mark or an absence code.")
            return
        print("\nNo mark yet:")
        for sid in missing:
            print(f"  {sid}  ({exam_marking.marker_label(conn, aid, sid, sid)})")
        conn.commit()
        sid = input("\nStudent ID to record as absent (Enter to go back): ").strip()
        if not sid:
            return
        code = input("ABS (absent, counts as 0) or ABS-MC (accepted mitigation): ").strip().upper()
        note = input("Note (optional): ").strip() or None
        _attempt(conn, lambda: exam_marking.record_absence(conn, aid, sid, code, reason=note),
                 "Absence recorded.")


def moderation_menu():
    with get_connection() as conn:
        aid = _pick_assessment(conn)
        if not aid:
            return
        while True:
            rows = exam_marking.moderation_rows(conn, aid)
            conn.commit()
            print(f"\n{'#':<5} {'Script':<22} {'First':>7} {'Second':>7} {'Agreed':>7}  Status")
            for r in rows:
                f = lambda v: "—" if v is None else f"{v:.1f}"
                print(f"{r['id']:<5} {str(r['label'])[:21]:<22} {f(r['first_mark']):>7} "
                      f"{f(r['second_mark']):>7} {f(r['agreed_mark']):>7}  {r['status']}")
            print("\n1. Draw sample  2. Second mark  3. Agree mark  4. Complete  0. Back")
            choice = input("Choice: ").strip()
            if choice == '1':
                _attempt(conn, lambda: exam_marking.draw_sample(conn, aid), lambda n: f"{n} script(s) sampled.")
            elif choice in ('2', '3'):
                mid, mark = input("Moderation #: ").strip(), input("Mark (%): ").strip()
                if not mid.isdigit():
                    print("Invalid #.")
                    continue
                if choice == '2':
                    _attempt(conn, lambda: exam_marking.record_second_mark(conn, int(mid), mark))
                else:
                    note = input("How was it resolved? ").strip() or None
                    _attempt(conn, lambda: exam_marking.agree_mark(conn, int(mid), mark, notes=note))
            elif choice == '4':
                _attempt(conn, lambda: exam_marking.complete_moderation(conn, aid), "Moderation complete.")
            else:
                return


def release_menu():
    with get_connection() as conn:
        aid = _pick_assessment(conn)
        if not aid:
            return
        blockers = exam_marking.release_blockers(conn, aid)
        force = False
        if blockers:
            print("Not ready:")
            for b in blockers:
                print(f"  - {b}")
            if blockers == ["Marks are already released."]:
                return
            force = input("Release anyway? (y/n): ").strip().lower() == 'y'
            if not force:
                return
        if input("Release every mark on this assessment to students? (y/n): ").strip().lower() == 'y':
            _attempt(conn, lambda: exam_marking.release(conn, aid, force=force),
                     lambda rows: f"Released {len(rows)} mark(s).")


def resits_menu():
    with get_connection() as conn:
        aid = _pick_assessment(conn)
        if not aid:
            return
        for r in exam_marking.resits(conn, aid):
            print(f"  already set: {r['student_id']} {r['attempt_type']} {r['name']} mark {r['mark'] or '—'}")
        try:
            candidates = exam_marking.resit_candidates(conn, aid)
        except ExamMarkingError as e:
            print(e)
            return
        if not candidates:
            print("No fails or absences awaiting a resit.")
            return
        for i, c in enumerate(candidates, 1):
            mark = "—" if c['mark'] is None else f"{c['mark']:.1f}%"
            print(f"{i:>3}. {c['student_id']:<12} {mark:>7}  {c['reason']:<20} suggested: {c['suggested_type']}")
        picks = input("Numbers to resit (comma-separated, 'all'): ").strip().lower()
        chosen = candidates if picks == 'all' else [
            candidates[int(p) - 1] for p in picks.split(',') if p.strip().isdigit()
            and 0 < int(p) <= len(candidates)]
        if not chosen:
            return
        students = []
        for c in chosen:
            kind = input(f"{c['student_id']}: referral or deferral [{c['suggested_type']}]: ").strip().lower()
            students.append({"student_id": c['student_id'], "attempt_type": kind or c['suggested_type'],
                             "mc_claim_id": c.get('mc_claim_id')})
        due = input("Resit date (YYYY-MM-DD HH:MM): ").strip()
        _attempt(conn, lambda: exam_marking.create_resit(conn, aid, students, due),
                 lambda new_id: f"Resit created as assessment {new_id}.")


def module_results_menu():
    with get_connection() as conn:
        code = input("Module code: ").strip()
        if not code:
            return
        if input("Recalculate first? (y/n): ").strip().lower() == 'y':
            _attempt(conn, lambda: module_results.recompute_module(conn, code),
                     lambda n: f"{n} result(s) recalculated (ratified results unchanged).")
        rows = conn.execute(
            "SELECT student_id, final_score, final_grade, outcome, status, locked, credits_awarded, is_complete "
            "FROM module_grades WHERE module_code = ? ORDER BY student_id", (code,)).fetchall()
        print(f"\n{'Student':<12} {'Mark':>6} {'Band':<7} {'Outcome':<12} {'Status':<18} {'Credits':>7} Complete")
        print("-" * 78)
        for r in rows:
            status = (r[4] or 'provisional') + (' (locked)' if r[5] else '')
            print(f"{r[0]:<12} {r[1] or 0:>6.1f} {str(r[2] or '—'):<7} {str(r[3] or '—'):<12} "
                  f"{status:<18} {r[6] or 0:>7g} {'yes' if r[7] else 'no'}")
        for w in module_results.weight_report(conn, code):
            print(f"\nWeightings: assignments {w['assignments_pct']:g}% + exams/tests {w['exams_pct']:g}% "
                  f"= {w['total_pct']:g}% ({w['state']})")
            if w['unweighted'] and w['total_pct']:
                print(f"Not counted (no weighting): {', '.join(w['unweighted'])}")
            if w['mirrors']:
                print(f"Counted once (assignment and assessment share a name): {', '.join(w['mirrors'])}")


def classification_menu():
    sid = input("Student ID: ").strip()
    if not sid:
        return
    with get_connection() as conn:
        result = classification.degree_classification(conn, sid)
        for level, v in sorted(result['levels'].items()):
            print(f"  Level {level}: {v['average']:.1f}% over {v['modules']} module(s), {v['credits']:g} credits")
        if result['classification']:
            print(f"Proposed classification: {result['classification']} ({result['average']:.2f}%)"
                  + ("  — borderline" if result['borderline'] else ""))
        if result['note']:
            print(result['note'])
        comp = classification.compensation_candidates(conn, sid)
        if comp:
            print("Fails a board could compensate: "
                  + ", ".join(f"{c['module_code']} ({c['mark']:.1f}%)" for c in comp))


def change_log_menu():
    sid = input("Student ID (Enter for all): ").strip() or None
    with get_connection() as conn:
        rows = exam_marking.change_log(conn, sid)
    if not rows:
        print("No recorded changes.")
        return
    for r in rows:
        print(f"{str(r['changed_at'])[:16]}  {r['student_id'] or '—':<10} {r['module_code'] or '—':<10} "
              f"{r['old_value'] or '—'} -> {r['new_value'] or '—'}  by {r['changed_by'] or '—'}: {r['reason']}")
