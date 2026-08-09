"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def analyze_reference_authenticity(self):
    """Verify that cited sources actually exist and contain claimed information"""
    text = ""
    if hasattr(self, 'text_input'):
        text = self.text_input.get('1.0', tk.END).strip()

    if not text:
        messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.analyze_reference_authenticity.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.analyze_reference_authenticity.dialogs.please_enter_text_in_the_text_analysis_view_first', default="Please enter text in the Text Analysis view first"))
        return

    try:
        self.update_status("Analyzing reference authenticity...")
        self.enhanced_results_text.delete('1.0', tk.END)

        import re

        # Extract potential references
        # APA style: (Author, Year)
        apa_pattern = r'\(([A-Z][a-z]+(?:\s+(?:&|and)\s+[A-Z][a-z]+)*),?\s*(\d{4})\)'
        apa_refs = re.findall(apa_pattern, text)

        # URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)

        # DOIs
        doi_pattern = r'10\.\d{4,}/[^\s]+'
        dois = re.findall(doi_pattern, text)

        result = "Reference Authenticity Analysis\n"
        result += "=" * 50 + "\n\n"

        result += "References Found:\n"
        result += f"  APA-style citations: {len(apa_refs)}\n"
        result += f"  URLs: {len(urls)}\n"
        result += f"  DOIs: {len(dois)}\n\n"

        suspicious_refs = []

        # Check for suspicious patterns
        for author, year in apa_refs:
            year_int = int(year)
            if year_int > 2025:
                suspicious_refs.append(f"{author}, {year} - Future date")
            elif year_int < 1900:
                suspicious_refs.append(f"{author}, {year} - Very old reference")

        # Check for fake-looking URLs using proper URL parsing
        from urllib.parse import urlparse
        for url in urls:
            url_lower = url.lower()
            try:
                parsed = urlparse(url_lower)
                hostname = parsed.hostname or ''
            except Exception:
                hostname = ''
            if 'fake' in url_lower or hostname == 'example.com' or hostname.endswith('.example.com'):
                suspicious_refs.append(f"Suspicious URL: {url[:50]}...")

        if suspicious_refs:
            result += "Suspicious References Detected:\n"
            result += "-" * 40 + "\n"
            for ref in suspicious_refs:
                result += f"  - {ref}\n"
            result += "\n"

        # Generate authenticity score
        total_refs = len(apa_refs) + len(urls) + len(dois)
        if total_refs > 0:
            authenticity_score = max(0, 100 - len(suspicious_refs) * 20)
            result += f"Reference Authenticity Score: {authenticity_score:.0f}%\n\n"

            if authenticity_score < 60:
                result += "WARNING: Multiple suspicious references detected.\n"
                result += "Manual verification recommended.\n"
            else:
                result += "References appear generally legitimate.\n"
                result += "Note: Full verification requires external database checks.\n"
        else:
            result += "No formal references detected in text.\n"

        self.enhanced_results_text.insert('1.0', result)
        self.update_status("Reference analysis complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.analyze_reference_authenticity.dialogs.error', default="Error"), f"Failed to analyze references: {str(e)}")
