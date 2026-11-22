"""Builds a study plan's tasks from what the student actually has on.

The old generator picked one task a day with ``random.choice`` from a list
of ten ("Watch tutorial videos", …), knew nothing about the module, and gave
two exams in the same week two plans that both claimed every evening.

A plan now runs from today to the day before the exam:

* **Phases** — the first 40% of the days learn the material, the next 40%
  practise it, the rest review it; the last day is a light final review
  with the sitting's time and room.
* **Modules** — the plan's module, or (a general plan) every enrolled
  module with an exam before the date, else every enrolled module. Time is
  shared by smooth weighted round-robin; a module weighs more when its
  released marks, flashcard recall or session ratings are weak
  (``study_context.weak_modules``).
* **Topics** — each task names a topic from the module's specification,
  learning outcomes or description, rotating through them.
* **The rest of the diary** — no study is planned on the day of another
  exam; the day before and the day of an assignment deadline get a
  deadline task and half the study time; minutes already planned by the
  student's other active plans come off each day's budget.
* **Flashcards** — when the student has cards, every other practice or
  review day starts with a short review of what is due.

Deterministic: the same records always give the same plan.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.university.domains.student_life.domain.study_hub.services import (
    study_context as ctx,
)

MIN_TASK_MINUTES = 30
SPLIT_AT_MINUTES = 120
CARD_REVIEW_MINUTES = 20
DEADLINE_MINUTES = 30
PRIORITIES = ("Low", "Medium", "High")

_GENERAL = {
    "learn": ("Read and summarise this week's lecture notes",
              "Go through your notes and reading for the week and write a one-page summary "
              "in your own words."),
    "practice": ("Practice questions",
                 "Work through seminar or tutorial questions without your notes; make a "
                 "flashcard for anything you get wrong."),
    "review": ("Self-test and fill gaps",
               "Test yourself on the main topics, then go back to the ones you could not "
               "answer."),
}


def _phase(index, days) -> str:
    if days and index == days - 1:
        return "final"
    fraction = index / days if days else 1
    if fraction < 0.4:
        return "learn"
    if fraction < 0.8:
        return "practice"
    return "review"


def _bump(priority, weak) -> str:
    if not weak:
        return priority
    return PRIORITIES[min(PRIORITIES.index(priority) + 1, len(PRIORITIES) - 1)]


class _Rotation:
    """Smooth weighted round-robin over modules (nginx's algorithm)."""

    def __init__(self, weights):
        self.weights = dict(weights)
        self.current = {m: 0.0 for m in self.weights}
        self.total = sum(self.weights.values()) or 1.0

    def next(self, exclude=()):
        for m, w in self.weights.items():
            self.current[m] += w
        choices = [m for m in self.weights if m not in exclude] or list(self.weights)
        pick = max(choices, key=lambda m: (self.current[m], str(m)))
        self.current[pick] -= self.total
        return pick


def _study_task(conn, module, phase, topic, minutes, weak, names, past_paper=False):
    name = names.get(module) or module
    label = f"{module} {name}".strip() if module and name != module else (module or "")
    if module is None:
        title, desc = _GENERAL[phase]
    elif past_paper:
        title = f"Past paper: {module}"
        desc = (f"Sit a past or specimen paper for {label} under timed conditions, then mark it "
                "against the model answers or your notes.")
    elif phase == "learn":
        title = f"Learn: {topic}" if topic else f"Work through lecture notes — {module}"
        desc = (f"Read your lecture notes and the reading list on {topic or 'this week'} for "
                f"{label}; write a one-page summary in your own words.")
    elif phase == "practice":
        title = f"Practise: {topic}" if topic else f"Practice questions — {module}"
        desc = (f"Do practice or seminar questions on {topic or 'the module'} for {label}; make a "
                "flashcard for each one you get wrong.")
    else:
        title = f"Review: {topic}" if topic else f"Self-test — {module}"
        desc = (f"Test yourself on {topic or 'the main topics'} ({label}) without notes, then "
                "check and fill the gaps.")
    priority = {"learn": "Low", "practice": "Medium", "review": "High"}[phase]
    return {"title": title, "description": desc, "duration": int(minutes),
            "priority": _bump(priority, weak), "module_code": module, "topic": topic,
            "kind": phase}


def build(conn, student_id, course_id, today: date, exam_day: date, hours_per_day) -> dict:
    """``{tasks, warnings, exam, modules}`` for a plan from ``today`` to the
    day before ``exam_day``."""
    days = (exam_day - today).days
    budget_full = int(round(float(hours_per_day) * 60))
    sid = str(student_id)
    warnings: list[str] = []

    enrolled = ctx.enrolled_modules(conn, sid)
    names = {m["module_code"]: m["module_name"] for m in enrolled}
    exams = ctx.upcoming_exams(conn, sid, today, exam_day)
    if course_id:
        modules = [course_id]
        names.setdefault(course_id, ctx.module_name(conn, course_id))
    else:
        with_exams = [e["module_code"] for e in exams]
        modules = list(dict.fromkeys(with_exams)) or [m["module_code"] for m in enrolled] or [None]

    weak = {w["module_code"]: w for w in ctx.weak_modules(conn, sid)}
    weights = {m: 1.0 + (weak[m]["weight"] if m in weak else 0.0) for m in modules}
    rotation = _Rotation(weights)
    topics = {m: ctx.module_topics(conn, m) for m in modules if m}
    topic_turn = {m: 0 for m in modules}

    the_exam = None
    if course_id:
        the_exam = next((e for e in ctx.upcoming_exams(conn, sid, exam_day, exam_day)
                         if e["module_code"] == course_id), None)
    other_exam_days: dict[str, list[dict]] = {}
    for e in exams:
        if e["date"] < exam_day.isoformat() and e is not the_exam:
            other_exam_days.setdefault(e["date"], []).append(e)
    deadline_days: dict[str, list[dict]] = {}
    for d in ctx.upcoming_deadlines(conn, sid, today, exam_day):
        due = str(d["due_date"])[:10]
        deadline_days.setdefault(due, []).append(d)
        before = (date.fromisoformat(due) - timedelta(days=1)).isoformat()
        deadline_days.setdefault(before, [])
    already = ctx.planned_minutes(conn, sid, today, exam_day)
    has_cards = conn.execute("SELECT 1 FROM flashcards WHERE student_id = ? LIMIT 1",
                             (sid,)).fetchone() is not None

    tasks: list[dict] = []
    card_turn = 0
    review_day = 0
    for i in range(days):
        day = today + timedelta(days=i)
        iso = day.isoformat()
        phase = _phase(i, days)

        if iso in other_exam_days:
            for e in other_exam_days[iso]:
                warnings.append(f"No study planned on {iso}: you have the {e['module_code']} "
                                "exam that day.")
            continue

        budget = budget_full
        if iso in deadline_days:
            budget //= 2
            for d in deadline_days[iso]:
                tasks.append({"date": iso, "title": f"Submit: {d['title']} ({d['module_code']})",
                              "description": f"Final checks and submission — due "
                                             f"{str(d['due_date'])[:16]}.",
                              "duration": DEADLINE_MINUTES, "priority": "High",
                              "module_code": d["module_code"], "topic": None,
                              "kind": "deadline"})
        if already.get(iso):
            budget -= already[iso]
            if budget < MIN_TASK_MINUTES:
                warnings.append(f"{iso} already has {already[iso]} min from your other study "
                                f"plans; this plan adds a short {MIN_TASK_MINUTES}-min session.")
        budget = max(budget, MIN_TASK_MINUTES)

        if phase == "final":
            module = course_id or (modules[0] if modules else None)
            where = ""
            if the_exam:
                where = (f" Your exam is {the_exam['date']} at {the_exam['start_time'] or '?'}"
                         + (f" in {the_exam['room']}" if the_exam.get("room") else "") + ".")
            tasks.append({"date": iso, "title": f"Final review{' — ' + module if module else ''}",
                          "description": "Light review of your summaries and flashcards; check "
                                         "what to bring, then rest." + where,
                          "duration": min(budget, 90), "priority": "High",
                          "module_code": module, "topic": None, "kind": "final"})
            continue

        if has_cards and phase in ("practice", "review"):
            card_turn += 1
            if card_turn % 2 == 1 and budget - CARD_REVIEW_MINUTES >= MIN_TASK_MINUTES:
                tasks.append({"date": iso, "title": "Review due flashcards",
                              "description": "Work through today's due cards in the Flashcards "
                                             "tab before anything else.",
                              "duration": CARD_REVIEW_MINUTES, "priority": "Medium",
                              "module_code": course_id, "topic": None, "kind": "flashcards"})
                budget -= CARD_REVIEW_MINUTES

        sessions = 2 if budget >= SPLIT_AT_MINUTES and len(modules) > 1 else 1
        chosen: list = []
        for s in range(sessions):
            module = rotation.next(exclude=chosen)
            chosen.append(module)
            minutes = budget // sessions + (budget % sessions if s == 0 else 0)
            past_paper = False
            if phase == "review" and module is not None:
                review_day += 1
                past_paper = review_day % 3 == 0
            topic = None
            if module and topics.get(module):
                topic = topics[module][topic_turn[module] % len(topics[module])]
                topic_turn[module] += 1
            tasks.append(dict(_study_task(conn, module, phase, topic, minutes, module in weak,
                                          names, past_paper), date=iso))

    for m in modules:
        if m in weak:
            warnings.append(f"More time given to {m}: " + "; ".join(weak[m]["reasons"]) + ".")
    return {"tasks": tasks, "warnings": warnings, "exam": the_exam, "modules": modules}
