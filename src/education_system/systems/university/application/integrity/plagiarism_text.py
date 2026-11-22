"""Text comparison for similarity checks. Pure functions, no database.

A document is prepared once: quotations ("…", “…”, lines starting with
``>``) and the reference list (everything after a References /
Bibliography / Works Cited heading) are left out, and for code, comments
are left out. What remains is split into words, each remembering where it
sits in the original text.

Before splitting, letters are folded so disguises do not hide a match:
look-alike letters from other alphabets (Cyrillic "а" for Latin "a") become
the Latin letter, accents are dropped, and invisible characters inside a
word (zero-width spaces, soft hyphens) are ignored. Each disguised character
found inside a word is counted (``Prepared.obfuscated``): a handful in an
English essay is a strong sign someone tried to beat the check.

Two documents are compared by overlapping runs of ``n`` consecutive words
(shingles). The score is the share of the submission's checked words that
sit inside a shared run — "how much of this work also appears there" — and
each run becomes a matched passage with its place in both texts. Runs that
also appear in the assignment's template (set text, starter code) are not
counted.

**Code** is compared on its shape, not its names: every identifier that is
not a keyword becomes the same token, and every number another, so renaming
variables does not hide copied code. Runs are three times as long as for
prose, because code tokens include punctuation.

**Paraphrase** (prose only, :func:`paraphrase`): sentence by sentence, the
content words (no common words, crude stems, a small table of academic
synonyms folded together) are compared. A sentence whose content words
mostly appear in one sentence of the source is a paraphrased passage, even
when the wording, order and inflection were changed.
"""

from __future__ import annotations

import bisect
import re
import unicodedata
from dataclasses import dataclass, field

CODE_TYPES = {"py", "java", "c", "cpp", "h", "js", "ts", "cs", "rb", "go", "php", "sql", "r",
              "m", "swift", "kt", "scala", "rs", "html", "css"}
CODE_RUN_FACTOR = 3

_HIDDEN = "\x00"   # stands in for an invisible character, so offsets keep their place
_WORD = re.compile(r"[A-Za-z0-9\x00]+(?:'[A-Za-z]+)?")
_CODE_TOKEN = re.compile(r"[A-Za-z_\x00][A-Za-z0-9_\x00]*|\d+|[^\sA-Za-z0-9_\x00]")
_QUOTES = (re.compile(r'"[^"\n]{1,600}"'), re.compile(r"“[^”]{1,600}”"))
_BLOCK_QUOTE = re.compile(r"^[ \t]*>.*$", re.MULTILINE)
_REFERENCES = re.compile(r"^[ \t]*(references|reference list|bibliography|works cited|"
                         r"sources)[ \t]*:?[ \t]*$", re.IGNORECASE | re.MULTILINE)
_COMMENTS = (re.compile(r"/\*.*?\*/", re.DOTALL), re.compile(r"//[^\n]*"),
             re.compile(r"#[^\n]*"), re.compile(r"<!--.*?-->", re.DOTALL))
_SENTENCE_END = re.compile(r"[.!?]+(?=[\s\"”')\]]|$)|\n[ \t]*\n")

_INVISIBLE = {"​", "‌", "‍", "⁠", "﻿", "­", "᠎"}
_LOOKALIKES = {
    # Cyrillic
    "а": "a", "в": "b", "е": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p", "с": "c",
    "т": "t", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s", "ԁ": "d", "һ": "h", "ӏ": "l",
    "ԛ": "q", "ԝ": "w", "ɡ": "g",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C",
    "Т": "T", "У": "Y", "Х": "X", "І": "I", "Ј": "J", "Ѕ": "S",
    # Greek
    "α": "a", "ο": "o", "ρ": "p", "ν": "v", "ι": "i", "κ": "k", "τ": "t", "υ": "u", "χ": "x",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N",
    "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
}

_KEYWORDS = frozenset("""
and as assert async await auto bool boolean break byte case catch char class const continue
def default del delete do double elif else enum except export extends extern false final
finally float fn for foreach from func function global go if impl implements import in
include instanceof int interface is lambda let long match mod module mut namespace new nil
none not null or package pass private protected pub public raise readonly ref return select
self short signed sizeof static string struct super switch template this throw throws trait
true try type typedef typeof union unsigned use using val var void volatile when where while
with yield print println printf len range list dict set str tuple map append push pop
insert update join group order by having limit values into
""".split())

_STOPWORDS = frozenset("""
a about above after again against all also am an and any are as at be because been before
being below between both but by can could did do does doing down during each few for from
further had has have having he her here hers herself him himself his how i if in into is it
its itself just me more most my myself no nor not now of off on once only or other our ours
ourselves out over own same she should so some such than that the their theirs them
themselves then there these they this those through to too under until up very was we were
what when where which while who whom why will with would you your yours yourself yourselves
however therefore thus hence moreover furthermore whereas whilst within without upon may
might must shall one two many much several often
""".split())

# Words a student might swap for each other. The first word of each group
# stands for the group.
_SYNONYM_GROUPS = (
    "show demonstrate indicate illustrate reveal display",
    "use utilise utilize employ apply",
    "important significant crucial essential vital key critical",
    "big large substantial considerable major",
    "small minor slight modest little",
    "help assist aid support facilitate",
    "begin start commence initiate",
    "end finish conclude terminate complete",
    "increase rise grow expand escalate",
    "decrease reduce decline diminish lessen fall",
    "get obtain acquire gain receive",
    "make create produce generate construct",
    "need require necessitate",
    "suggest propose imply recommend",
    "examine analyse analyze investigate study explore assess evaluate",
    "result outcome consequence effect",
    "cause lead trigger produce",
    "method approach technique way means procedure",
    "problem issue difficulty challenge",
    "change alter modify transform adjust",
    "main primary principal chief",
    "clear evident obvious apparent",
    "many numerous multiple various",
    "enough sufficient adequate",
    "try attempt endeavour endeavor",
    "think believe consider argue contend",
    "say state claim assert maintain",
    "often frequently commonly regularly",
    "quick rapid fast swift",
    "find discover identify detect",
    "aim goal objective purpose",
    "part component element portion",
    "affect influence impact",
    "allow enable permit",
    "keep retain maintain preserve",
    "choose select pick",
    "buy purchase",
    "people individuals persons",
    "therefore consequently accordingly",
)
_SYNONYMS = {}
for _group in _SYNONYM_GROUPS:
    _words = _group.split()
    for _w in _words:
        _SYNONYMS.setdefault(_w, _words[0])

_SUFFIXES = ("isations", "izations", "isation", "ization", "ational", "fulness", "iveness",
             "ements", "ement", "ments", "ment", "ness", "ities", "ity", "ings", "ing", "edly",
             "ied", "ies", "ed", "es", "ly", "s")

PARAPHRASE_MIN_CONCEPTS = 5
PARAPHRASE_CONTAINMENT = 0.7
PARAPHRASE_SOURCE_SHARE = 0.5


@dataclass
class Prepared:
    tokens: list[str]
    spans: list[tuple[int, int]]
    excluded_words: int = 0
    total_words: int = 0
    shingles: dict[int, list[int]] = field(default_factory=dict)
    n: int = 6
    code: bool = False
    obfuscated: int = 0
    sentences: list[tuple[int, int]] = field(default_factory=list)
    _concepts: list[frozenset] | None = None

    def concepts(self) -> list[frozenset]:
        """Content-word stems of each sentence (prose only)."""
        if self._concepts is None:
            self._concepts = [frozenset(c for c in (concept(t) for t in self.tokens[a:b + 1])
                                        if c) for a, b in self.sentences]
        return self._concepts


def is_code(file_type) -> bool:
    return str(file_type or "").lower().lstrip(".") in CODE_TYPES


def _masked(text, code) -> list[tuple[int, int]]:
    ranges = []
    if code:
        for rx in _COMMENTS:
            ranges += [m.span() for m in rx.finditer(text)]
        return ranges
    for rx in _QUOTES:
        ranges += [m.span() for m in rx.finditer(text)]
    ranges += [m.span() for m in _BLOCK_QUOTE.finditer(text)]
    heading = None
    for heading in _REFERENCES.finditer(text):
        pass
    if heading and heading.start() > len(text) * 0.3:
        ranges.append((heading.start(), len(text)))
    return ranges


def _inside(pos, ranges) -> bool:
    return any(a <= pos < b for a, b in ranges)


def fold(text) -> tuple[str, int]:
    """``text`` with look-alike letters made Latin, accents dropped and
    invisible characters replaced by a placeholder — the same length, so
    offsets still point into the original. Also how many disguised
    characters sat inside a word."""
    out = []
    disguised = 0
    for i, ch in enumerate(text):
        if ch.isascii():
            out.append(ch)
            continue
        prev_letter = i > 0 and text[i - 1].isalpha()
        next_letter = i + 1 < len(text) and text[i + 1].isalpha()
        if ch in _INVISIBLE:
            out.append(_HIDDEN)
            if prev_letter and next_letter:
                disguised += 1
            continue
        if ch in _LOOKALIKES:
            out.append(_LOOKALIKES[ch])
            # A look-alike beside a Latin letter is a disguise; a whole
            # Cyrillic or Greek word is just another language.
            if (prev_letter and text[i - 1].isascii()) or (next_letter and text[i + 1].isascii()):
                disguised += 1
            continue
        base = unicodedata.normalize("NFKD", ch)[:1]
        out.append(base if base.isascii() and base.isalpha() else ch)
    return "".join(out), disguised


def _code_token(tok) -> str:
    if tok[0].isdigit():
        return "§n"
    if tok[0].isalpha() or tok[0] == "_":
        return tok if tok in _KEYWORDS else "§i"
    return tok


def _sentences(text, spans) -> list[tuple[int, int]]:
    """Token ranges ``(first, last)`` of each sentence."""
    if not spans:
        return []
    ends = [m.start() for m in _SENTENCE_END.finditer(text)]
    found, start = [], 0
    starts = [s for s, _e in spans]
    for end in ends:
        last = bisect.bisect_right(starts, end) - 1
        if last >= start:
            found.append((start, last))
            start = last + 1
    if start < len(spans):
        found.append((start, len(spans) - 1))
    return found


def prepare(text, file_type="txt", n=6) -> Prepared:
    text = str(text or "")
    code = is_code(file_type)
    folded, disguised = fold(text)
    ranges = sorted(_masked(folded, code))
    tokens, spans, excluded = [], [], 0
    for match in (_CODE_TOKEN if code else _WORD).finditer(folded):
        if _inside(match.start(), ranges):
            excluded += 1
            continue
        tok = match.group(0).replace(_HIDDEN, "")
        if not tok:
            continue
        tokens.append(_code_token(tok) if code else tok.lower())
        spans.append(match.span())
    run = n * CODE_RUN_FACTOR if code else n
    prepared = Prepared(tokens, spans, excluded, len(tokens) + excluded, n=run, code=code,
                        obfuscated=disguised)
    prepared.shingles = shingles(tokens, run)
    if not code:
        prepared.sentences = _sentences(folded, spans)
    return prepared


def shingles(tokens, n) -> dict[int, list[int]]:
    found: dict[int, list[int]] = {}
    for i in range(len(tokens) - n + 1):
        found.setdefault(hash(tuple(tokens[i:i + n])), []).append(i)
    return found


def _runs(positions) -> list[tuple[int, int]]:
    runs, start, last = [], None, None
    for pos in sorted(positions):
        if start is None:
            start = last = pos
        elif pos == last + 1:
            last = pos
        else:
            runs.append((start, last))
            start = last = pos
    if start is not None:
        runs.append((start, last))
    return runs


def compare(sub: Prepared, src: Prepared, n=None, ignore: set[int] = frozenset()) -> dict:
    """What of ``sub`` also appears in ``src``, word for word (or, for
    code, token shape for token shape).

    Returns ``{"covered": set of word positions in sub, "passages": [...]}``,
    each passage giving character offsets in both texts."""
    n = sub.n if n is None or sub.code else n
    covered: set[int] = set()
    source_of: dict[int, int] = {}
    for key, positions in sub.shingles.items():
        if key in ignore or key not in src.shingles:
            continue
        first_source = src.shingles[key][0]
        for i in positions:
            for k in range(n):
                covered.add(i + k)
                source_of.setdefault(i + k, first_source + k)
    passages = []
    for start, end in _runs(covered):
        s_start, s_end = source_of[start], source_of[end]
        passages.append({
            "start": sub.spans[start][0], "end": sub.spans[end][1], "words": end - start + 1,
            "source_start": src.spans[s_start][0] if s_start < len(src.spans) else None,
            "source_end": src.spans[min(s_end, len(src.spans) - 1)][1] if src.spans else None,
            "kind": "exact",
        })
    return {"covered": covered, "passages": passages}


def concept(token) -> str | None:
    """A word's stem with synonyms folded together; ``None`` for a common word."""
    word = token.lower().strip("'")
    if len(word) < 3 or word in _STOPWORDS or word.isdigit():
        return None
    if word in _SYNONYMS:
        return _SYNONYMS[word]
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            stem = word[: -len(suffix)]
            if suffix in ("ies", "ied"):
                stem += "y"
            return _SYNONYMS.get(stem, stem)
    return word


def paraphrase(sub: Prepared, src: Prepared, already: set[int] = frozenset()) -> dict:
    """Sentences of ``sub`` that say what a sentence of ``src`` says in
    other words. Sentences mostly covered by an exact match (``already``)
    are skipped. Same shape as :func:`compare`, passages of kind
    ``paraphrase``."""
    if sub.code or src.code or not sub.sentences or not src.sentences:
        return {"covered": set(), "passages": []}
    index: dict[str, list[int]] = {}
    src_concepts = src.concepts()
    for sid, words in enumerate(src_concepts):
        for word in words:
            index.setdefault(word, []).append(sid)
    covered: set[int] = set()
    passages = []
    for (first, last), words in zip(sub.sentences, sub.concepts()):
        if len(words) < PARAPHRASE_MIN_CONCEPTS:
            continue
        positions = range(first, last + 1)
        if sum(1 for p in positions if p in already) * 2 >= len(positions):
            continue
        counts: dict[int, int] = {}
        for word in words:
            for sid in index.get(word, ()):
                counts[sid] = counts.get(sid, 0) + 1
        if not counts:
            continue
        best = max(counts, key=counts.get)
        shared = counts[best]
        if shared / len(words) < PARAPHRASE_CONTAINMENT:
            continue
        if shared / max(1, len(src_concepts[best])) < PARAPHRASE_SOURCE_SHARE:
            continue
        s_first, s_last = src.sentences[best]
        covered.update(positions)
        passages.append({"start": sub.spans[first][0], "end": sub.spans[last][1],
                         "words": last - first + 1, "source_start": src.spans[s_first][0],
                         "source_end": src.spans[s_last][1], "kind": "paraphrase"})
    return {"covered": covered, "passages": passages}


def score(covered_words, prepared: Prepared) -> float:
    if not prepared.tokens:
        return 0.0
    return round(min(1.0, covered_words / len(prepared.tokens)), 4)


def band(value, review_threshold, high_threshold) -> str:
    if value >= high_threshold:
        return "HIGH"
    if value >= review_threshold:
        return "MODERATE"
    return "LOW" if value > 0 else "NO_MATCH"
