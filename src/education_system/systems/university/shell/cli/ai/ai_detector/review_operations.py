"""Alerts, batches, the model, federation, the audit chain, the processing
queue, bias, forecasts, privacy and settings in the CLI. Officer-only
actions are checked here and again by the backend."""

from education_system.systems.university.shell.cli.ai.ai_detector import _cli


def _d():
    return _cli.detector()


# ── alerts ──────────────────────────────────────────────────────────────


def alerts_cli():
    """Alerts on your modules: open, no concern, refer, escalate."""
    try:
        out = _d().view_alert_queue(None, _cli.ask("Include reviewed? (y/n)", "n") == "y")
    except (PermissionError, ValueError) as exc:
        print(f"  {exc}")
        return
    alerts = out.get("alerts", [])
    if not alerts:
        print("  No alerts.")
        return
    for a in alerts:
        print(f"  {a['alert_id']:>4}  reading {a.get('ai_result_id')}  {a.get('student_id')}  "
              f"{a.get('module_code')}  {a.get('risk_level')}  {a.get('status')}  "
              f"{a.get('submission_title')}")
    alert_id = _cli.ask("Alert number (Enter to go back)")
    alert = next((a for a in alerts if str(a["alert_id"]) == alert_id), None)
    if not alert:
        return
    choice = _cli.ask("1 open  2 no concern  3 refer as a case  4 escalate")
    if choice == "1" and alert.get("submission_id"):
        from education_system.systems.university.shell.cli.ai.ai_detector.basic_operations import (
            display_detailed_submission,
        )
        display_detailed_submission(_d().get_submission_details(int(alert["submission_id"])))
    elif choice == "2":
        reason = _cli.ask("Why is there no concern? (shown to the student)")
        if reason:
            _cli.run(_d().dismiss_alert, alert["alert_id"], "other", reason, title="Recorded")
    elif choice == "3":
        note = _cli.ask("Why refer it? (what else does the concern rest on?)")
        if note:
            _cli.run(_d().refer_alert, alert["alert_id"], note, title="Referred")
    elif choice == "4":
        summary = _cli.ask("Summary")
        if summary:
            _cli.run(_d().escalate_to_dean, alert["submission_id"], alert.get("student_id"),
                     _cli.ask("Concern", "Unauthorised AI use"), summary,
                     _cli.ask("Suggested outcome (optional)") or None, title="Escalated")
    _cli.pause()


# ── batches ─────────────────────────────────────────────────────────────


def batch_cli():
    choice = _cli.ask("1 read a folder  2 read an LMS export  3 schedule  4 jobs  "
                      "5 run due jobs now  6 retry failed")
    if choice in ("1", "2", "3"):
        module = _cli.pick_module()
        if not module:
            return
        assignment = _cli.pick_assignment(module)
        path = _cli.ask("Folder or export path")
        if not path:
            return
        if choice == "1":
            _cli.run(_d().batch_analyze_folder, path, course_code=module,
                     assignment_id=assignment, title="Folder read")
        elif choice == "2":
            _cli.run(_d().batch_analyze_lms_export, path, _cli.ask("LMS (auto/canvas/blackboard/"
                                                                   "moodle)", "auto"),
                     course_code=module, assignment_name=assignment, title="Export read")
        else:
            _cli.run(_d().schedule_batch_job, _cli.ask("Type (folder / lms)", "folder"), path,
                     _cli.ask("Time (HH:MM)", "02:00"), course_code=module,
                     assignment_id=assignment, title="Scheduled")
    elif choice == "4":
        _cli.run(_d().view_batch_job_status, title="Jobs")
    elif choice == "5":
        _cli.run(_d().run_due_batch_jobs, title="Ran")
    elif choice == "6":
        _cli.run(_d().retry_failed_analyses, title="Queued again")
    _cli.pause()


# ── model management ────────────────────────────────────────────────────


def model_cli():
    choice = _cli.ask("1 training data  2 train  3 versions  4 activate  5 roll back  "
                      "6 use no model  7 evaluate  8 compare  9 export  10 import  11 cache  "
                      "12 try a text on versions")
    d = _d()
    if choice == "1":
        _cli.run(d.training_data_summary, title="Training data")
    elif choice == "2" and _cli.require_officer():
        _cli.run(d.retrain_detection_model,
                 activate=_cli.ask("Activate it? (y/n)", "n") == "y", title="Trained")
    elif choice == "3":
        _cli.run(d.list_model_versions, title="Versions")
    elif choice in ("4", "5") and _cli.require_officer():
        version = _cli.ask("Version")
        reason = _cli.ask("Reason")
        if version and reason:
            method = d.activate_model_version if choice == "4" else d.rollback_model_version
            _cli.run(method, version, reason, title="Done")
    elif choice == "6" and _cli.require_officer():
        reason = _cli.ask("Reason")
        if reason:
            _cli.run(d.deactivate_model, reason, title="Done")
    elif choice == "7" and _cli.require_officer():
        _cli.run(d.evaluate_model_version, _cli.ask("Version"), title="Evaluation")
    elif choice == "8":
        _cli.run(d.compare_model_versions, _cli.ask("First version"), _cli.ask("Second version"),
                 title="Compared")
    elif choice == "9":
        _cli.run(d.export_weights, _cli.ask("Save to (path ending .json)"),
                 _cli.ask("Version (Enter for the active one)") or None, title="Exported")
    elif choice == "10" and _cli.require_officer():
        _cli.run(d.import_weights, _cli.ask("Weights file"), title="Imported (inactive)")
    elif choice == "11":
        _cli.run(d.get_cache_statistics, title="Cache")
        if _cli.ask("Clear it? (y/n)", "n") == "y":
            _cli.run(d.clear_cache, title="Cleared")
    elif choice == "12":
        versions = [v.strip() for v in _cli.ask("Versions (comma-separated)").split(",")
                    if v.strip()]
        text = _cli.read_text("Text to try (read, not stored)")[0] if versions else ""
        if text:
            _cli.run(d.estimate_text_with_versions, text, versions,
                     title="Estimate under each version (context, not a judgement)")
    _cli.pause()


# ── federated learning ──────────────────────────────────────────────────


def federated_cli():
    fl = getattr(_d(), "federated_learning", None)
    if fl is None or not _cli.require_officer():
        return
    choice = _cli.ask("1 set institution id  2 export update  3 import update  4 aggregate  "
                      "5 list updates  6 import a shared global model")
    if choice == "1":
        value = _cli.ask("Institution id", fl.institution_id or "")
        if value:
            _cli.run(lambda: fl.initialize_federation(value) or {"institution_id": value},
                     title="Saved")
    elif choice == "2":
        _cli.run(fl.contribute_model_update, privacy_budget=float(_cli.ask("Epsilon", "1.0")),
                 path=_cli.ask("Save to (folder or .json path)") or None, title="Exported")
    elif choice == "3":
        _cli.run(fl.import_model_update, _cli.ask("Update file"), title="Imported")
    elif choice == "4":
        ids = [int(x) for x in _cli.ask("Update ids (comma-separated; Enter for every unused "
                                        "one)").split(",") if x.strip().isdigit()]
        _cli.run(fl.aggregate_model_updates, ids or None, title="Aggregated (inactive)")
    elif choice == "5":
        _cli.run(lambda: fl.model_updates, title="Updates")
    elif choice == "6":
        path = _cli.ask("Global model weights file (.json)")
        if path:
            _cli.run(_d().import_weights, path, False,
                     title="Imported (inactive — evaluate it before activating)")
    _cli.pause()


# ── audit chain, queue, bias, forecasts ─────────────────────────────────


def audit_chain_cli():
    chain = getattr(_d(), "blockchain_audit", None)
    if chain is None:
        print("  The audit chain is not available.")
        return
    _cli.run(chain.verify_chain, title="Chain check")
    for b in chain.get_blocks(int(_cli.ask("How many recent blocks", "20") or 20)):
        print(f"  {b['index']:>5} {b['timestamp']}  {b['event']:<28} {b['actor']}")
    _cli.pause()


def realtime_cli():
    processor = getattr(_d(), "realtime_processor", None)
    if processor is None:
        print("  The processing queue is not available.")
        return
    _cli.run(processor.get_status, title="Queue")
    choice = _cli.ask("1 start workers  2 stop workers  3 queue submissions without a reading")
    if choice == "1":
        processor.start_real_time_processing(int(_cli.ask("Workers", "2") or 2))
        print("  Running while this program is open.")
    elif choice == "2":
        processor.stop_real_time_processing()
        print("  Stopped.")
    elif choice == "3":
        print(f"  {processor.sweep_now()} submission(s) queued.")
    _cli.pause()


def bias_cli():
    detector = getattr(_d(), "bias_detector", None)
    if detector is not None and _cli.require_officer():
        _cli.run(detector.analyze_detection_bias, title="Bias report")
        _cli.pause()


def predictive_cli():
    pa = getattr(_d(), "predictive_analytics", None)
    if pa is None:
        return
    choice = _cli.ask("1 review workload forecast  2 how often similar readings were confirmed")
    if choice == "1":
        module = _cli.pick_module()
        _cli.run(pa.forecast_review_workload, int(_cli.ask("Weeks ahead", "4") or 4), module,
                 title="Forecast")
    elif choice == "2":
        value = _cli.ask("Reading id")
        if value.isdigit():
            _cli.run(pa.reviewer_agreement, int(value), title="Similar readings")
    _cli.pause()


# ── privacy, settings, self-check ───────────────────────────────────────


def privacy_cli():
    pm = getattr(_d(), "privacy_manager", None)
    if pm is None:
        return
    choice = _cli.ask("1 retention policy and runs  2 apply retention now  3 a student's "
                      "consents  4 record a consent")
    if choice == "1":
        _cli.run(pm.get_retention_policy, title="Policy")
        _cli.run(pm.get_retention_runs, title="Recent runs")
    elif choice == "2" and _cli.require_officer():
        _cli.run(pm.apply_retention, title="Applied")
    elif choice == "3":
        _cli.run(pm.get_consents, _cli.ask("Student number"), title="Consents")
    elif choice == "4" and _cli.require_officer():
        _cli.run(lambda: pm.record_consent(
            _cli.ask("Student number"),
            _cli.ask("Type (research_use / federated_training / self_check_history)",
                     "research_use"), _cli.ask("Given? (y/n)", "y") == "y") or {"recorded": True},
            title="Recorded")
    _cli.pause()


def settings_cli():
    """The integrity settings the detector uses (officers change them) and
    a module's on/off switch (its staff)."""
    from education_system.systems.university.application.integrity import (
        access as integrity_access,
    )
    conn = _cli._connect()
    try:
        for key in ("ai_review_threshold", "ai_min_words", "ai_auto_check"):
            print(f"  {key:<22} {integrity_access.setting(conn, key)}")
    finally:
        conn.close()
    choice = _cli.ask("1 change a setting  2 turn readings on/off for a module  "
                      "3 informational checks for this session")
    if choice == "1" and _cli.require_officer():
        key = _cli.ask("Setting")
        value = _cli.ask("New value")
        conn = _cli._connect()
        try:
            integrity_access.set_setting(conn, _cli.who(), key, value)
            conn.commit()
            print("  Saved.")
        except (PermissionError, ValueError) as exc:
            conn.rollback()
            print(f"  {exc}")
        finally:
            conn.close()
    elif choice == "2":
        module = _cli.pick_module()
        if module:
            _cli.run(_d().set_course_ai_detection, module,
                     _cli.ask("Readings on? (y/n)", "y") == "y", title="Saved")
    elif choice == "3":
        methods = _d().detection_methods
        names = list(methods)
        for i, key in enumerate(names, 1):
            print(f"  {i}. {key.replace('_', ' '):<26} {'on' if methods[key] else 'off'}")
        pick = _cli.ask("Number to switch on/off (Enter to leave)")
        if pick.isdigit() and 1 <= int(pick) <= len(names):
            key = names[int(pick) - 1]
            methods[key] = not methods[key]
            print(f"  {key.replace('_', ' ')} is now {'on' if methods[key] else 'off'} "
                  "(informational only; the indicators always run).")
    _cli.pause()


def self_check_preview_cli():
    tool = getattr(_d(), "student_self_check", None)
    text = _cli.read_text()[0] if tool is not None else ""
    if text:
        result = tool.preview_analysis(text)
        if result.get("error"):
            print(f"  {result['error']}")
        else:
            _cli.print_reading({**result, "result_id": "preview", "submission_id": "—",
                                "student_id": "—", "course_code": "—"})
            for advice in result.get("suggestions", []):
                print(f"  • {advice}")
        _cli.pause()
