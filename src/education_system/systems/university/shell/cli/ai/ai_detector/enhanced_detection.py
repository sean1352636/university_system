"""Enhanced detection in the CLI (informational; none of these changes a
reading's strength)."""

from education_system.systems.university.shell.cli.ai.ai_detector import _cli


def _get_ai_detector():
    return _cli.detector()


def _text():
    text, _kind = _cli.read_text()
    if not text:
        print("  No text given.")
    return text


def analyze_writing_style_fingerprint_cli():
    module = _cli.pick_module()
    student = _cli.pick_student(module) if module else None
    if student:
        text = _cli.read_text("Paste the new text to compare (or leave empty)")[0] or None
        _cli.run(_get_ai_detector().analyze_writing_style_fingerprint, student, text,
                 title="Writing style against earlier work")
        _cli.pause()


def detect_paraphrasing_tools_cli():
    text = _text()
    if text:
        _cli.run(_get_ai_detector().detect_paraphrasing_tools, text,
                 title="Paraphrasing-tool patterns")
        _cli.pause()


def analyze_prompt_artifacts_cli():
    text = _text()
    if text:
        _cli.run(_get_ai_detector().analyze_prompt_artifacts, text, title="Leftover prompt text")
        _cli.pause()


def compare_draft_versions_cli():
    paths = []
    while True:
        path = _cli.ask(f"Draft {len(paths) + 1} file path (Enter when done)")
        if not path:
            break
        paths.append(path)
    if len(paths) < 2:
        print("  Give at least two drafts.")
        return
    from education_system.systems.university.infrastructure.integrity import text_extract
    try:
        drafts = [text_extract.extract(p) for p in paths]
    except ValueError as exc:
        print(f"  {exc}")
        return
    _cli.run(_get_ai_detector().compare_draft_versions, drafts, title="Drafts compared")
    _cli.pause()


def detect_translation_artifacts_cli():
    text = _text()
    if text:
        _cli.run(_get_ai_detector().detect_translation_artifacts, text,
                 title="Other-language paragraphs")
        _cli.pause()


def analyze_knowledge_consistency_cli():
    module = _cli.pick_module()
    student = _cli.pick_student(module) if module else None
    text = _text() if student else None
    if text:
        _cli.run(_get_ai_detector().analyze_knowledge_consistency, text, student, module,
                 title="Against the module level")
        _cli.pause()


def detect_copy_paste_patterns_cli():
    text = _text()
    if text:
        _cli.run(_get_ai_detector().detect_copy_paste_patterns, text,
                 title="Pasted / formatting traces")
        _cli.pause()


def analyze_reference_authenticity_cli():
    text = _text()
    if text:
        _cli.run(_get_ai_detector().analyze_reference_authenticity, text, title="References")
        _cli.pause()
