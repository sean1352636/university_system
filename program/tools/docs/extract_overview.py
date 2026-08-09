"""Extract PROGRAM_OVERVIEW.docx into structured blocks for the combined guide.

The overview's original generator is no longer in the repository, so its prose
exists only inside the .docx. This pulls it out as JSON so the combined document
can replay Part I verbatim instead of it being retyped and quietly reworded.

    python extract_overview.py program/docs/PROGRAM_OVERVIEW.docx overview.json
"""
from __future__ import annotations

import json
import sys

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph


def classify(p: Paragraph) -> str:
    style = p.style.name
    if style.startswith("Heading"):
        return "h" + style[-1]
    if style == "List Bullet":
        return "bullet"
    runs = [r for r in p.runs if r.text.strip()]
    if runs and all((r.font.name or "").startswith("Consolas") for r in runs):
        return "code"
    if runs and all(r.italic for r in runs):
        return "note"
    return "para"


def main(src, dest):
    doc = docx.Document(src)
    blocks = []
    for el in doc.element.body.iterchildren():
        if el.tag == qn("w:p"):
            p = Paragraph(el, doc)
            text = p.text.strip()
            if not text:
                continue
            kind = classify(p)
            # the bold-lead runs ("What this shows: …") are worth keeping apart
            lead = None
            if p.runs and p.runs[0].bold and len(p.runs) > 1:
                lead = p.runs[0].text
                text = "".join(r.text for r in p.runs[1:]).strip()
            blocks.append({"kind": kind, "text": text, "lead": lead})
        elif el.tag == qn("w:tbl"):
            t = Table(el, doc)
            first = t.rows[0].cells[0].text.strip()
            if first.startswith("[") and "SCREENSHOT" in first:
                blocks.append({"kind": "placeholder",
                               "text": t.rows[0].cells[0].text.strip()})
                continue
            rows = [[c.text.strip() for c in r.cells] for r in t.rows]
            blocks.append({"kind": "table", "rows": rows})

    with open(dest, "w") as fh:
        json.dump(blocks, fh, indent=1)
    print(f"{len(blocks)} blocks -> {dest}")
    kinds: dict[str, int] = {}
    for b in blocks:
        kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
    print(kinds)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
