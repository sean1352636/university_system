"""Student Handbook — CLI reader.

The terminal counterpart of the book-style GUI reader: a contents page,
chapters, sections read one at a time with next/previous, the handbook's
cross-references as numbered links, keyword search and a bookmark. Reached
from the admin, staff, instructor and student CLI portals.
"""

from __future__ import annotations

import shutil
import textwrap

from education_system.systems.university.domains.student_life.domain.student_handbook.content import (
    handbook,
    MOTTO,
    SUBTITLE,
    institution_name,
    YEAR,
    links_in,
    search,
    sections,
    strip_links,
)

_MAX_WIDTH = 88


def _width() -> int:
    return max(40, min(_MAX_WIDTH, shutil.get_terminal_size((80, 24)).columns - 2))


def _rule(char: str = "=") -> str:
    return char * _width()


def _wrap(text: str, indent: str = "  ") -> str:
    if text.startswith("•"):
        # Bullets keep their dotted leaders on one line where they fit.
        return textwrap.fill(text, _width(), initial_indent=indent,
                             subsequent_indent=indent + "  ")
    return textwrap.fill(text, _width(), initial_indent=indent, subsequent_indent=indent)


class HandbookCLI:
    """Interactive reader over the handbook content."""

    def __init__(self):
        self.institution = institution_name()
        self.chapters = handbook()
        self.entries = sections(self.chapters)
        self.index_of = {e["section"]["id"]: i for i, e in enumerate(self.entries)}
        self.chapter_ids = {ch["id"]: n for n, ch in enumerate(self.chapters, start=1)}
        self.bookmark: int | None = None

    # ----- pages ---------------------------------------------------------
    def _header(self, title: str) -> None:
        print("\n" + _rule())
        print(f"  {self.institution} — {SUBTITLE} {YEAR}")
        print(f"  {title}")
        print(_rule())

    def contents(self) -> None:
        while True:
            self._header("CONTENTS")
            print(f"  {MOTTO}\n")
            for n, ch in enumerate(self.chapters, start=1):
                print(f"    {n}.  {ch['title']}")
            print("\n    S.  Search the handbook")
            if self.bookmark is not None:
                e = self.entries[self.bookmark]
                print(f"    K.  Go to bookmark ({e['num']} {e['section']['title']})")
            print("    0.  Close the handbook")
            print(_rule())

            choice = input("\n  Choose a chapter (or 2.3 for a section): ").strip().lower()
            if choice in ("0", "q", ""):
                return
            if choice == "s":
                if self.search_prompt() == "close":
                    return
            elif choice == "k" and self.bookmark is not None:
                if self.read(self.bookmark) == "close":
                    return
            elif "." in choice:
                idx = self._index_for_number(choice)
                if idx is None:
                    print("\n  No such section.")
                    input("Press Enter to continue...")
                elif self.read(idx) == "close":
                    return
            elif choice.isdigit() and 1 <= int(choice) <= len(self.chapters):
                if self.chapter(int(choice)) == "close":
                    return
            else:
                print("\n  Invalid choice. Please try again.")
                input("Press Enter to continue...")

    def chapter(self, number: int) -> str | None:
        ch = self.chapters[number - 1]
        while True:
            self._header(f"CHAPTER {number}: {ch['title'].upper()}")
            for s_num, sec in enumerate(ch["sections"], start=1):
                print(f"    {s_num}.  {sec['title']}")
            print("\n    0.  Back to contents")
            print(_rule())
            choice = input("\n  Choose a section: ").strip().lower()
            if choice in ("0", "b", "c", ""):
                return None
            if choice == "q":
                return "close"
            if choice.isdigit() and 1 <= int(choice) <= len(ch["sections"]):
                idx = self.index_of[ch["sections"][int(choice) - 1]["id"]]
                if self.read(idx) == "close":
                    return "close"
            else:
                print("\n  Invalid choice. Please try again.")
                input("Press Enter to continue...")

    def read(self, idx: int) -> str | None:
        """Read sections from ``idx``; returns "close" to leave the handbook."""
        history: list[int] = []
        while True:
            entry = self.entries[idx]
            sec = entry["section"]
            self._header(f"{entry['num']}  {sec['title']}   (Chapter: {entry['chapter']['title']})")
            print()
            for para in sec["body"]:
                print(_wrap(strip_links(para)))
                if not para.startswith("•"):
                    print()

            links = []
            for para in sec["body"]:
                for label, target in links_in(para):
                    if (label, target) not in links:
                        links.append((label, target))
            if links:
                print(_rule("-"))
                print("  See also:")
                for n, (label, target) in enumerate(links, start=1):
                    print(f"    L{n}. {label}{self._describe(target)}")

            print(_rule("-"))
            nav = []
            if idx + 1 < len(self.entries):
                nav.append("N next")
            if idx > 0:
                nav.append("P previous")
            if history:
                nav.append("B back")
            nav.append("M remove bookmark" if self.bookmark == idx else "M bookmark")
            nav += ["C contents", "Q close"]
            print("  " + "  ·  ".join(nav))
            choice = input("\n  > ").strip().lower()

            if choice in ("n", "") and idx + 1 < len(self.entries):
                history.append(idx)
                idx += 1
            elif choice == "p" and idx > 0:
                history.append(idx)
                idx -= 1
            elif choice == "b" and history:
                idx = history.pop()
            elif choice == "m":
                self.bookmark = None if self.bookmark == idx else idx
                print("\n  Bookmark removed." if self.bookmark is None else "\n  Bookmarked.")
            elif choice in ("c", "0"):
                return None
            elif choice == "q":
                return "close"
            elif choice.startswith("l") and choice[1:].isdigit() and 1 <= int(choice[1:]) <= len(links):
                target = links[int(choice[1:]) - 1][1]
                if target in self.index_of:
                    history.append(idx)
                    idx = self.index_of[target]
                elif target in self.chapter_ids:
                    if self.chapter(self.chapter_ids[target]) == "close":
                        return "close"
                else:            # "toc" and anything unknown
                    return None
            elif choice in ("n", ""):
                print("\n  This is the last section.")
            else:
                print("\n  Invalid choice. Please try again.")
                input("Press Enter to continue...")

    def search_prompt(self) -> str | None:
        query = input("\n  Search for: ").strip()
        if not query:
            return
        hits = search(query, self.chapters)
        while True:
            self._header(f"SEARCH: {query}")
            if not hits:
                print("  Nothing in the handbook matches that.")
                input("\nPress Enter to continue...")
                return
            for n, e in enumerate(hits, start=1):
                print(f"    {n}.  {e['num']}  {e['section']['title']}   ({e['chapter']['title']})")
            print("\n    0.  Back to contents")
            print(_rule())
            choice = input("\n  Open result: ").strip()
            if choice in ("0", ""):
                return
            if choice.isdigit() and 1 <= int(choice) <= len(hits):
                if self.read(self.index_of[hits[int(choice) - 1]["section"]["id"]]) == "close":
                    return "close"
            else:
                print("\n  Invalid choice. Please try again.")
                input("Press Enter to continue...")

    # ----- helpers -------------------------------------------------------
    def _index_for_number(self, number: str) -> int | None:
        for i, e in enumerate(self.entries):
            if e["num"] == number:
                return i
        return None

    def _describe(self, target: str) -> str:
        if target in self.index_of:
            e = self.entries[self.index_of[target]]
            return f"  → {e['num']} {e['section']['title']}"
        if target in self.chapter_ids:
            return f"  → Chapter {self.chapter_ids[target]}"
        return "  → Contents"


def run_student_handbook_cli(auth=None) -> None:
    """Open the handbook reader. ``auth`` is accepted for menu-dispatch
    symmetry; the handbook is the same for every signed-in role."""
    HandbookCLI().contents()
