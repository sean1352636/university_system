"""Enhanced detection analysis CLI functions for the AI Detector."""


def _get_ai_detector():
    """Get the global ai_detector instance from the interface module."""
    import education_system.systems.university.interfaces.cli.shell.ai.ai_detector.interface as _iface
    return _iface.ai_detector


def analyze_writing_style_fingerprint_cli():
    """CLI interface for writing style fingerprint analysis"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f52c Writing Style Fingerprint Analysis")
    print("=" * 50)

    student_id = input("Enter student ID: ").strip()
    if not student_id:
        print("\u274c Student ID is required.")
        input("\nPress Enter to continue...")
        return

    print("\nAnalyzing writing style fingerprint...")
    result = ai_detector.analyze_writing_style_fingerprint(student_id)

    if result.get('error'):
        print(f"\u274c Error: {result['error']}")
    else:
        print(f"\n\u2705 Fingerprint Generated for Student: {student_id}")
        print(f"Submissions analyzed: {result.get('submissions_analyzed', 0)}")
        print(f"Total words analyzed: {result.get('total_words_analyzed', 0)}")

        fp = result.get('fingerprint', {})
        if fp:
            vocab = fp.get('vocabulary_metrics', {})
            print("\n\U0001f4ca Vocabulary Metrics:")
            print(f"  Lexical diversity: {vocab.get('lexical_diversity', 'N/A')}")
            print(f"  Avg word length: {vocab.get('avg_word_length', 'N/A')}")
            print(f"  Complex word ratio: {vocab.get('complex_word_ratio', 'N/A')}")

            sent = fp.get('sentence_metrics', {})
            print("\n\U0001f4dd Sentence Patterns:")
            print(f"  Avg sentence length: {sent.get('avg_length', 'N/A')} words")
            print(f"  Total sentences: {sent.get('total_sentences', 'N/A')}")

            print(f"\n\U0001f3af Formality Score: {fp.get('formality_score', 'N/A')}")

    input("\nPress Enter to continue...")


def detect_paraphrasing_tools_cli():
    """CLI interface for paraphrasing tool detection"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f50d Paraphrasing Tool Detection")
    print("=" * 50)
    print("Detects text processed through Quillbot, Spinbot, etc.")

    print("\nEnter the text to analyze (press Enter twice to finish):")
    print("-" * 50)

    lines = []
    empty_lines = 0
    while empty_lines < 2:
        try:
            line = input()
            if line.strip() == "":
                empty_lines += 1
            else:
                empty_lines = 0
            lines.append(line)
        except KeyboardInterrupt:
            print("\nAnalysis cancelled.")
            return

    text = "\n".join(lines).strip()
    if not text:
        print("\u274c No text provided.")
        input("\nPress Enter to continue...")
        return

    print("\nAnalyzing for paraphrasing tool patterns...")
    result = ai_detector.detect_paraphrasing_tools(text)

    print(f"\n{'='*50}")
    print("PARAPHRASING DETECTION RESULTS")
    print(f"{'='*50}")
    paraphrased_str = "\U0001f534 YES" if result.get('is_paraphrased') else "\U0001f7e2 NO"
    print(f"Is Paraphrased: {paraphrased_str}")
    print(f"Paraphrasing Score: {result.get('paraphrasing_score', 0):.3f}")
    print(f"Confidence: {result.get('confidence', 0):.3f}")

    if result.get('likely_tool'):
        print(f"Likely Tool: {result['likely_tool']}")

    indicators = result.get('indicators', [])
    if indicators:
        print(f"\n\U0001f4cc Indicators Found ({len(indicators)}):")
        for ind in indicators:
            print(f"  \u2022 {ind.get('type')}: {ind.get('evidence', '')}")

    input("\nPress Enter to continue...")


def analyze_prompt_artifacts_cli():
    """CLI interface for AI prompt artifact detection"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f916 AI Prompt Artifact Detection")
    print("=" * 50)
    print("Detects ChatGPT/Claude response patterns and artifacts.")

    print("\nEnter the text to analyze (press Enter twice to finish):")
    print("-" * 50)

    lines = []
    empty_lines = 0
    while empty_lines < 2:
        try:
            line = input()
            if line.strip() == "":
                empty_lines += 1
            else:
                empty_lines = 0
            lines.append(line)
        except KeyboardInterrupt:
            print("\nAnalysis cancelled.")
            return

    text = "\n".join(lines).strip()
    if not text:
        print("\u274c No text provided.")
        input("\nPress Enter to continue...")
        return

    print("\nAnalyzing for AI prompt artifacts...")
    result = ai_detector.analyze_prompt_artifacts(text)

    print(f"\n{'='*50}")
    print("AI ARTIFACT DETECTION RESULTS")
    print(f"{'='*50}")
    artifacts_str = "\U0001f534 YES" if result.get('has_ai_artifacts') else "\U0001f7e2 NO"
    print(f"Has AI Artifacts: {artifacts_str}")
    print(f"Artifact Score: {result.get('artifact_score', 0):.3f}")
    print(f"Most Likely Source: {result.get('most_likely_source', 'Unknown')}")

    artifacts = result.get('artifacts_found', [])
    if artifacts:
        print(f"\n\U0001f4cc Artifacts Found ({len(artifacts)}):")
        for art in artifacts[:10]:
            print(f"  \u2022 {art.get('type')}: {art.get('matches', 0)} match(es) [{art.get('severity', 'low')}]")

    input("\nPress Enter to continue...")


def compare_draft_versions_cli():
    """CLI interface for draft version comparison"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f4dd Draft Version Comparison")
    print("=" * 50)
    print("Compare multiple drafts to detect suspicious quality jumps.")

    num_drafts = input("How many drafts to compare (2-5)? ").strip()
    try:
        num_drafts = int(num_drafts)
        if num_drafts < 2 or num_drafts > 5:
            raise ValueError()
    except ValueError:
        print("\u274c Please enter a number between 2 and 5.")
        input("\nPress Enter to continue...")
        return

    student_id = input("Enter student ID (optional, press Enter to skip): ").strip() or None

    drafts = []
    for i in range(num_drafts):
        print(f"\n--- Draft {i+1} ---")
        print("Enter text (press Enter twice to finish):")

        lines = []
        empty_lines = 0
        while empty_lines < 2:
            try:
                line = input()
                if line.strip() == "":
                    empty_lines += 1
                else:
                    empty_lines = 0
                lines.append(line)
            except KeyboardInterrupt:
                print("\nAnalysis cancelled.")
                return

        draft_text = "\n".join(lines).strip()
        if draft_text:
            drafts.append(draft_text)

    if len(drafts) < 2:
        print("\u274c Need at least 2 drafts to compare.")
        input("\nPress Enter to continue...")
        return

    print("\nComparing drafts...")
    result = ai_detector.compare_draft_versions(drafts, student_id)

    print(f"\n{'='*50}")
    print("DRAFT COMPARISON RESULTS")
    print(f"{'='*50}")
    print(f"Drafts Analyzed: {result.get('drafts_analyzed', 0)}")
    suspicious_str = "\U0001f534 YES" if result.get('is_suspicious') else "\U0001f7e2 NO"
    print(f"Is Suspicious: {suspicious_str}")

    analyses = result.get('analyses', [])
    if analyses:
        print("\n\U0001f4ca Draft Quality Scores:")
        for a in analyses:
            print(f"  Draft {a['draft_number']}: {a['quality_score']:.3f} (Words: {a['word_count']})")

    jumps = result.get('suspicious_jumps', [])
    if jumps:
        print("\n\u26a0\ufe0f Suspicious Jumps Found:")
        for j in jumps:
            print(f"  Draft {j['from_draft']} \u2192 {j['to_draft']}: +{j['improvement']:.3f} [{j['severity']}]")

    reasons = result.get('suspicion_reasons', [])
    if reasons:
        print("\n\U0001f4cc Summary:")
        for r in reasons:
            print(f"  \u2022 {r}")

    input("\nPress Enter to continue...")


def detect_translation_artifacts_cli():
    """CLI interface for translation artifact detection"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f30d Translation Artifact Detection")
    print("=" * 50)
    print("Identifies text written in another language and translated.")

    print("\nEnter the text to analyze (press Enter twice to finish):")
    print("-" * 50)

    lines = []
    empty_lines = 0
    while empty_lines < 2:
        try:
            line = input()
            if line.strip() == "":
                empty_lines += 1
            else:
                empty_lines = 0
            lines.append(line)
        except KeyboardInterrupt:
            print("\nAnalysis cancelled.")
            return

    text = "\n".join(lines).strip()
    if not text:
        print("\u274c No text provided.")
        input("\nPress Enter to continue...")
        return

    print("\nAnalyzing for translation artifacts...")
    result = ai_detector.detect_translation_artifacts(text)

    print(f"\n{'='*50}")
    print("TRANSLATION DETECTION RESULTS")
    print(f"{'='*50}")
    translated_str = "\U0001f534 YES" if result.get('is_likely_translated') else "\U0001f7e2 NO"
    print(f"Is Likely Translated: {translated_str}")
    print(f"Translation Score: {result.get('translation_score', 0):.3f}")
    print(f"Confidence: {result.get('confidence', 0):.3f}")

    if result.get('detected_language'):
        print(f"Detected Language: {result['detected_language']} ({result.get('language_confidence', 0):.2f})")

    indicators = result.get('indicators', [])
    if indicators:
        print(f"\n\U0001f4cc Indicators Found ({len(indicators)}):")
        for ind in indicators:
            print(f"  \u2022 {ind.get('type')}: {ind.get('evidence', '')}")

    input("\nPress Enter to continue...")


def analyze_knowledge_consistency_cli():
    """CLI interface for knowledge consistency analysis"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f4da Knowledge Consistency Analysis")
    print("=" * 50)
    print("Check if demonstrated knowledge matches student's course level.")

    student_id = input("Enter student ID: ").strip()
    if not student_id:
        print("\u274c Student ID is required.")
        input("\nPress Enter to continue...")
        return

    course_code = input("Enter course code (optional): ").strip() or None

    print("\nEnter the text to analyze (press Enter twice to finish):")
    print("-" * 50)

    lines = []
    empty_lines = 0
    while empty_lines < 2:
        try:
            line = input()
            if line.strip() == "":
                empty_lines += 1
            else:
                empty_lines = 0
            lines.append(line)
        except KeyboardInterrupt:
            print("\nAnalysis cancelled.")
            return

    text = "\n".join(lines).strip()
    if not text:
        print("\u274c No text provided.")
        input("\nPress Enter to continue...")
        return

    print("\nAnalyzing knowledge consistency...")
    result = ai_detector.analyze_knowledge_consistency(text, student_id, course_code)

    print(f"\n{'='*50}")
    print("KNOWLEDGE CONSISTENCY RESULTS")
    print(f"{'='*50}")
    consistent_str = "\U0001f7e2 YES" if result.get('is_consistent') else "\U0001f534 NO"
    print(f"Is Consistent: {consistent_str}")
    print(f"Previous Submissions: {result.get('previous_submissions_count', 0)}")

    current = result.get('current_analysis', {})
    if current:
        print("\n\U0001f4ca Current Submission Analysis:")
        print(f"  Vocabulary Level: {current.get('vocabulary_level', 0):.3f}")
        print(f"  Concept Complexity: {current.get('concept_complexity', 0):.3f}")
        print(f"  Argument Sophistication: {current.get('argument_sophistication', 0):.3f}")

    inconsistencies = result.get('inconsistencies', [])
    if inconsistencies:
        print("\n\u26a0\ufe0f Inconsistencies Found:")
        for inc in inconsistencies:
            print(f"  \u2022 {inc.get('type')}: {inc.get('severity', 'medium')} severity")

    print(f"\n\U0001f4cc Recommendation: {result.get('recommendation', 'N/A')}")

    input("\nPress Enter to continue...")


def detect_copy_paste_patterns_cli():
    """CLI interface for copy-paste pattern detection"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f4cb Copy-Paste Pattern Detection")
    print("=" * 50)
    print("Identifies copy-paste behavior from formatting anomalies.")

    print("\nEnter the text to analyze (press Enter twice to finish):")
    print("-" * 50)

    lines = []
    empty_lines = 0
    while empty_lines < 2:
        try:
            line = input()
            if line.strip() == "":
                empty_lines += 1
            else:
                empty_lines = 0
            lines.append(line)
        except KeyboardInterrupt:
            print("\nAnalysis cancelled.")
            return

    text = "\n".join(lines).strip()
    if not text:
        print("\u274c No text provided.")
        input("\nPress Enter to continue...")
        return

    print("\nAnalyzing for copy-paste patterns...")
    result = ai_detector.detect_copy_paste_patterns(text)

    print(f"\n{'='*50}")
    print("COPY-PASTE DETECTION RESULTS")
    print(f"{'='*50}")
    copy_paste_str = "\U0001f534 YES" if result.get('has_copy_paste_indicators') else "\U0001f7e2 NO"
    print(f"Has Copy-Paste Indicators: {copy_paste_str}")
    print(f"Copy-Paste Score: {result.get('copy_paste_score', 0):.3f}")
    print(f"Confidence: {result.get('confidence', 0):.3f}")

    indicators = result.get('indicators', [])
    if indicators:
        print(f"\n\U0001f4cc Indicators Found ({len(indicators)}):")
        for ind in indicators:
            print(f"  \u2022 {ind.get('type')}: {ind.get('evidence', '')}")

    input("\nPress Enter to continue...")


def analyze_reference_authenticity_cli():
    """CLI interface for reference authenticity analysis"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f4d6 Reference Authenticity Analysis")
    print("=" * 50)
    print("Verify that cited sources are properly formatted.")

    print("\nEnter the text with citations (press Enter twice to finish):")
    print("-" * 50)

    lines = []
    empty_lines = 0
    while empty_lines < 2:
        try:
            line = input()
            if line.strip() == "":
                empty_lines += 1
            else:
                empty_lines = 0
            lines.append(line)
        except KeyboardInterrupt:
            print("\nAnalysis cancelled.")
            return

    text = "\n".join(lines).strip()
    if not text:
        print("\u274c No text provided.")
        input("\nPress Enter to continue...")
        return

    print("\nAnalyzing references...")
    result = ai_detector.analyze_reference_authenticity(text)

    print(f"\n{'='*50}")
    print("REFERENCE AUTHENTICITY RESULTS")
    print(f"{'='*50}")
    authentic_str = "\U0001f7e2 YES" if result.get('is_authentic') else "\U0001f534 NO"
    print(f"Is Authentic: {authentic_str}")
    print(f"Authenticity Score: {result.get('authenticity_score', 0):.3f}")
    print(f"Citations Found: {result.get('citations_found', 0)}")
    print(f"References Found: {result.get('references_found', 0)}")

    fabrication = result.get('fabrication_indicators', [])
    if fabrication:
        print("\n\u26a0\ufe0f Fabrication Indicators:")
        for f in fabrication:
            print(f"  \u2022 {f.get('type')}: {f.get('evidence', '')}")

    suspicious = result.get('suspicious_references', [])
    if suspicious:
        print(f"\n\U0001f4cc Suspicious References ({len(suspicious)}):")
        for s in suspicious[:5]:
            print(f"  \u2022 {s.get('reference', 'N/A')[:60]}...")

    print(f"\nNote: {result.get('verification_note', '')}")

    input("\nPress Enter to continue...")
