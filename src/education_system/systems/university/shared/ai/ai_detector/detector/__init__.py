"""AIDetector class split into mixins for maintainability. ``AIDetector`` is
loaded on first use, so ``detector.reading`` can be imported on its own."""


def __getattr__(name):
    if name == "AIDetector":
        from education_system.systems.university.shared.ai.ai_detector.detector.main import (
            AIDetector,
        )
        globals()["AIDetector"] = AIDetector
        return AIDetector
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ['AIDetector']
