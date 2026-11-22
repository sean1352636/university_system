"""One Claude request for university features that draft text.

:func:`complete` sends one prompt to Claude (``claude-opus-5-5``) and returns
the text, or ``None`` when Claude cannot answer: the ``anthropic`` SDK is not
installed, no credentials resolve (``ANTHROPIC_API_KEY``,
``ANTHROPIC_AUTH_TOKEN`` or an ``ant auth login`` profile), the request fails,
or the reply is refused or cut off. Callers treat ``None`` as "no draft" and
carry on without one.

Server-side refusal fallback is on (``fallbacks: "default"``), so a request
declined by one model's safeguards is retried on another inside the same call.

``UNIVERSITY_AI=off`` disables every call; ``UNIVERSITY_AI_MODEL`` overrides
the model. The study companion has its own client and switches
(``study_hub/services/companion_ai.py``).
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


def enabled() -> bool:
    return os.environ.get("UNIVERSITY_AI", "on").strip().lower() not in (
        "off", "0", "false", "no")


def model() -> str:
    return os.environ.get("UNIVERSITY_AI_MODEL", "").strip() or MODEL


def _client():
    if not enabled():
        return None
    try:
        import anthropic
    except ImportError:
        logger.info("University AI unavailable: the anthropic package is not installed")
        return None
    try:
        return anthropic.Anthropic()
    except Exception:
        logger.info("University AI unavailable: no Anthropic credentials", exc_info=True)
        return None


def complete(prompt: str, *, system: str | None = None, max_tokens: int = 16000,
             effort: str = "medium") -> str | None:
    """Claude's reply to *prompt*, or ``None`` if there is no usable reply."""
    client = _client()
    if client is None:
        return None
    import anthropic

    params = {
        "model": model(),
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": {"effort": effort},
    }
    if system:
        params["system"] = system
    try:
        try:
            response = client.beta.messages.create(
                betas=[_FALLBACK_BETA], fallbacks="default", **params)
        except (TypeError, anthropic.BadRequestError):
            # An SDK that does not know the fallback parameter, or a platform
            # that rejects it: the same request without it.
            response = client.messages.create(**params)
    except anthropic.AuthenticationError:
        logger.warning("University AI request rejected: invalid Anthropic credentials")
        return None
    except anthropic.RateLimitError:
        logger.warning("University AI request rate-limited; try again later")
        return None
    except anthropic.APIStatusError as exc:
        logger.warning("University AI request failed (%s): %s", exc.status_code, exc.message)
        return None
    except anthropic.APIConnectionError:
        logger.warning("University AI request failed: could not reach the Anthropic API")
        return None
    if response.stop_reason == "refusal":
        category = getattr(response.stop_details, "category", None)
        logger.info("University AI request declined (category: %s)", category)
        return None
    if response.stop_reason == "max_tokens":
        logger.info("University AI reply cut off at max_tokens=%s", max_tokens)
        return None
    text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
    return text.strip() or None
