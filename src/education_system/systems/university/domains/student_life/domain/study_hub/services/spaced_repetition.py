"""SM-2 spaced repetition for the study companion's flashcards.

The old scheduler only knew right or wrong and picked the next interval from
the card's *total* review count, so a card failed five times came back in 30
days after a single correct answer. SM-2 keeps the run of consecutive correct
recalls (``repetitions``) and a per-card ease factor instead:

* a grade below 3 is a lapse — the run resets and the card is due tomorrow;
* the first correct recall waits 1 day, the second 6, then each interval is
  the last one times the card's ease;
* every grade moves the ease (never below 1.3), so a card that is always
  "hard" comes back more often than one that is always "easy".

Pure functions; the service stores the result.
"""

from __future__ import annotations

from datetime import date, timedelta

MIN_EASE = 1.3
DEFAULT_EASE = 2.5
MAX_INTERVAL_DAYS = 365

#: Grades offered on the review screen (SM-2 quality, 0–5).
AGAIN, HARD, GOOD, EASY = 1, 3, 4, 5
GRADES = {"again": AGAIN, "hard": HARD, "good": GOOD, "easy": EASY}


def quality_for(correct=None, quality=None) -> int:
    """The SM-2 grade for a review: an explicit ``quality`` (0–5 or a name
    from :data:`GRADES`), else ``correct`` mapped to Good / Again."""
    if quality is not None:
        if isinstance(quality, str):
            key = quality.strip().lower()
            if key in GRADES:
                return GRADES[key]
            if not key.isdigit():
                raise ValueError("Grade is again, hard, good, easy or 0-5")
            quality = int(key)
        q = int(quality)
        if not 0 <= q <= 5:
            raise ValueError("Grade is again, hard, good, easy or 0-5")
        return q
    if correct is None:
        raise ValueError("Say whether the answer was right, or give a grade")
    return GOOD if correct else AGAIN


def schedule(*, ease=None, interval=None, repetitions=None, quality: int,
             today: date | None = None) -> dict:
    """Next SM-2 state for a card reviewed ``today`` with grade ``quality``."""
    today = today or date.today()
    ease = float(ease) if ease else DEFAULT_EASE
    interval = int(interval or 0)
    repetitions = int(repetitions or 0)
    lapsed = quality < 3

    if lapsed:
        repetitions = 0
        interval = 1
    else:
        repetitions += 1
        if repetitions == 1:
            interval = 1
        elif repetitions == 2:
            interval = 6
        else:
            interval = max(1, round(interval * ease))
    interval = min(interval, MAX_INTERVAL_DAYS)

    miss = 5 - quality
    ease = max(MIN_EASE, round(ease + (0.1 - miss * (0.08 + miss * 0.02)), 3))

    return {
        "ease_factor": ease,
        "interval_days": interval,
        "repetitions": repetitions,
        "lapsed": lapsed,
        "correct": not lapsed,
        "next_review": (today + timedelta(days=interval)).isoformat(),
    }


def retention(reviews) -> float | None:
    """Share of reviews (as rows with a ``quality``) that were recalled, as a
    percentage; ``None`` when there are none."""
    grades = [int(r["quality"]) for r in reviews if r.get("quality") is not None]
    if not grades:
        return None
    return round(100.0 * sum(1 for g in grades if g >= 3) / len(grades), 1)
