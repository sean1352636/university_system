"""HTML/PDF report generation for the education system."""

import os
from string import Template
from datetime import datetime

_REPORT_TEMPLATE = Template("""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>$title</title>
<style>
body { font-family: Arial, sans-serif; margin: 40px; color: #333; }
h1 { color: #1a5276; border-bottom: 2px solid #1a5276; padding-bottom: 10px; }
h2 { color: #2c3e50; margin-top: 30px; }
table { width: 100%; border-collapse: collapse; margin: 15px 0; }
th { background: #1a5276; color: white; padding: 10px; text-align: left; }
td { padding: 8px 10px; border-bottom: 1px solid #ddd; }
tr:nth-child(even) { background: #f8f9fa; }
.footer { margin-top: 40px; font-size: 0.8em; color: #7f8c8d; border-top: 1px solid #ddd; padding-top: 10px; }
.summary-box { background: #eaf2f8; padding: 15px; border-radius: 5px; margin: 15px 0; }
</style></head><body>
<h1>$title</h1>
<p>Generated: $generated_at</p>
$content
<div class="footer">$institution - Confidential Report</div>
</body></html>""")


def generate_report_html(title, sections, institution="Education System"):
    """Generate an HTML report from sections.

    Args:
        title: Report title
        sections: List of dicts with keys: heading, type ('table'|'text'|'summary'),
                  and data (list of dicts for tables, string for text)
        institution: Institution name for footer
    """
    content_parts = []
    for section in sections:
        heading = section.get("heading", "")
        sec_type = section.get("type", "text")
        data = section.get("data", "")

        if heading:
            content_parts.append(f"<h2>{heading}</h2>")

        if sec_type == "table" and isinstance(data, list) and data:
            headers = list(data[0].keys())
            rows_html = ""
            for row in data:
                cells = "".join(f"<td>{row.get(h, '')}</td>" for h in headers)
                rows_html += f"<tr>{cells}</tr>\n"
            header_html = "".join(f"<th>{h.replace('_', ' ').title()}</th>" for h in headers)
            content_parts.append(
                f"<table><thead><tr>{header_html}</tr></thead>"
                f"<tbody>{rows_html}</tbody></table>"
            )
        elif sec_type == "summary":
            content_parts.append(f'<div class="summary-box">{data}</div>')
        else:
            content_parts.append(f"<p>{data}</p>")

    return _REPORT_TEMPLATE.substitute(
        title=title,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        content="\n".join(content_parts),
        institution=institution,
    )


def save_report_html(title, sections, filepath, institution="Education System"):
    """Generate and save an HTML report to a file."""
    html = generate_report_html(title, sections, institution)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    return filepath
