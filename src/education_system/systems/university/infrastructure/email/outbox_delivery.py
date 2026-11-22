"""Delivers the university e-mail outbox (``application/mail/outbox``).

* :func:`delivery_mode` – ``inbox_only`` / ``sandbox`` / ``live``, read from
  the shared e-mail config file each time (``delivery_mode``; when unset,
  ``database_only_mode`` true means ``inbox_only`` and false means ``live``).
* :func:`set_mode` – change it; only an e-mail administrator, and ``live``
  only once an SMTP server, sender and password are configured.
* :func:`deliver_due` – claim due messages, send each, record the result.
* :func:`enqueue` – submit one message on its own connection, commit, and
  start a delivery pass in the background.
* :func:`start_worker` – a daemon thread that delivers every minute and runs
  the retention purge once a day.

The password is never read from the config file here; see
``platform/integrations/email/config.get_smtp_password``.
"""

from __future__ import annotations

import json
import logging
import smtplib
import threading
import time
from email.utils import formatdate, make_msgid
from pathlib import Path

from education_system import paths
from education_system.systems.university.application.mail import (
    admin as email_admin,
    outbox as email_outbox,
)

logger = logging.getLogger(__name__)

SANDBOX_DIR: Path = paths.UNIVERSITY_EMAIL_DATA_DIR / "sandbox"
_WORKER: threading.Thread | None = None
_PASS_LOCK = threading.Lock()


# ── configuration ───────────────────────────────────────────────────────


def _config_path() -> Path:
    return paths.PLATFORM_EMAIL_CONFIG_PATH


def file_config() -> dict:
    """The shared config file's settings, without any password."""
    try:
        data = json.loads(_config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data.pop("smtp_password", None)
    data.pop("password", None)
    return data


def delivery_mode(cfg: dict | None = None) -> str:
    cfg = file_config() if cfg is None else cfg
    mode = str(cfg.get("delivery_mode") or "").strip().lower()
    if mode in email_outbox.MODES:
        return mode
    return "inbox_only" if cfg.get("database_only_mode", True) else "live"


def _username(cfg) -> str:
    return str(cfg.get("smtp_username") or cfg.get("username") or "")


def _password(cfg) -> str:
    from education_system.platform.integrations.email.config import get_smtp_password
    return get_smtp_password(_username(cfg))


def live_problems(cfg: dict | None = None) -> list[str]:
    """What is missing before live sending can work."""
    cfg = file_config() if cfg is None else cfg
    problems = []
    if not cfg.get("smtp_server"):
        problems.append("no SMTP server")
    if not cfg.get("sender_email"):
        problems.append("no sender address")
    if cfg.get("use_authentication", True) and not (_username(cfg) and _password(cfg)):
        problems.append("no SMTP login (set SMTP_PASSWORD, or move the password out of the "
                        "config file)")
    return problems


def status() -> dict:
    """What the status screens show."""
    from education_system.platform.integrations.email.config import password_in_config_file
    cfg = file_config()
    return {
        "mode": delivery_mode(cfg),
        "sender": cfg.get("sender_email") or "",
        "smtp_server": f"{cfg.get('smtp_server') or '-'}:{cfg.get('smtp_port') or 587}",
        "password_in_config_file": password_in_config_file(_config_path()),
        "live_ready": not live_problems(cfg),
        "live_problems": live_problems(cfg),
        "sandbox_dir": str(SANDBOX_DIR),
        "worker_running": bool(_WORKER and _WORKER.is_alive()),
    }


def set_mode(conn, actor, actor_role, mode) -> None:
    """Change the delivery mode in the config file, keeping every other key.
    Audited on ``conn``; the caller commits."""
    email_outbox.ensure(conn)
    email_outbox.require(email_outbox.is_admin(actor_role)
                         or email_outbox.holds(conn, actor, "email_admin"),
                         "Only an e-mail administrator can change how e-mail is delivered")
    if mode not in email_outbox.MODES:
        raise ValueError(f"mode must be one of {', '.join(email_outbox.MODES)}")
    if mode == "live" and live_problems():
        raise ValueError("Live sending is not set up: " + "; ".join(live_problems()))
    path = _config_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    before = delivery_mode(raw)
    raw["delivery_mode"] = mode
    raw["database_only_mode"] = mode == "inbox_only"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    tmp.replace(path)
    email_outbox.audit(conn, actor, "mode", None, "changed", {"from": before, "to": mode})


# ── transport ───────────────────────────────────────────────────────────


def _write_sandbox(msg_row, cfg) -> str:
    from education_system.systems.university.infrastructure.email.smtp import build_message
    message = build_message(subject=msg_row["subject"], body=msg_row["body"],
                            from_header=f"{cfg.get('sender_name') or 'University'} "
                                        f"<{cfg.get('sender_email') or 'noreply@localhost'}>",
                            to_header=msg_row["to_address"], cc=msg_row.get("cc"),
                            reply_to=msg_row.get("reply_to"))
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid()
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    target = SANDBOX_DIR / f"{msg_row['message_id']:08d}.eml"
    target.write_text(message.as_string(), encoding="utf-8")
    return str(target)


def _smtp_client(cfg):
    from education_system.systems.university.infrastructure.email.smtp import (
        SMTPClient, SMTPConfig,
    )
    return SMTPClient(SMTPConfig(
        smtp_server=cfg.get("smtp_server", ""), smtp_port=int(cfg.get("smtp_port") or 587),
        sender_email=cfg.get("sender_email", ""), sender_name=cfg.get("sender_name", ""),
        username=_username(cfg) or None, password=_password(cfg) or None,
        use_tls=bool(cfg.get("use_tls", True)),
        use_authentication=bool(cfg.get("use_authentication", True))))


def classify(exc) -> str:
    """``permanent`` / ``rejected`` / ``temporary`` for a send error."""
    from education_system.systems.university.infrastructure.exceptions import AttachmentError
    if isinstance(exc, (AttachmentError, ValueError)):
        return "rejected"
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        codes = [code for code, _msg in exc.recipients.values()]
        return "permanent" if codes and all(int(c) >= 500 for c in codes) else "temporary"
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "temporary"
    if isinstance(exc, smtplib.SMTPResponseException) and exc.smtp_code in (550, 551, 553):
        return "permanent"
    return "temporary"


def _transmit(msg_row, mode, cfg) -> tuple[str, str | None]:
    try:
        if mode == "sandbox":
            return "sent", f"written to {_write_sandbox(msg_row, cfg)}"
        _smtp_client(cfg).send_or_raise(msg_row["to_address"], msg_row["subject"],
                                        msg_row["body"], msg_row.get("cc"), msg_row.get("bcc"),
                                        msg_row.get("attachments"),
                                        reply_to=msg_row.get("reply_to"))
        return "sent", None
    except Exception as exc:  # every failure is recorded against the message
        logger.warning("E-mail %s not delivered: %s", msg_row["message_id"], exc)
        return classify(exc), f"{type(exc).__name__}: {exc}"[:500]


# ── delivery passes ─────────────────────────────────────────────────────


def _connect(db_path=None):
    from education_system.systems.university.infrastructure.database.db import get_connection
    return get_connection(db_path, row_factory=False)


def deliver_due(db_path=None, limit=20) -> dict:
    """One delivery pass. Messages queued while the mode is ``inbox_only``
    wait until the mode changes."""
    cfg = file_config()
    mode = delivery_mode(cfg)
    done = {"sent": 0, "retrying": 0, "failed": 0, "bounced": 0, "mode": mode}
    if mode == "inbox_only" or not _PASS_LOCK.acquire(blocking=False):
        return done
    try:
        if mode == "live" and live_problems(cfg):
            return done
        conn = _connect(db_path)
        try:
            due = email_outbox.claim_due(conn, limit)
            conn.commit()
            for row in due:
                outcome, detail = _transmit(row, mode, cfg)
                new = email_outbox.record_result(conn, row["message_id"], mode, outcome, detail)
                conn.commit()
                key = "retrying" if new == "queued" else new
                done[key] = done.get(key, 0) + 1
        finally:
            conn.close()
    finally:
        _PASS_LOCK.release()
    return done


def kick(db_path=None) -> None:
    """Start a delivery pass in the background (no-op in inbox_only mode)."""
    if delivery_mode() == "inbox_only":
        return
    threading.Thread(target=_safe_pass, args=(db_path,), daemon=True,
                     name="email-outbox-kick").start()


def _safe_pass(db_path=None) -> None:
    try:
        deliver_due(db_path)
    except Exception:
        logger.exception("E-mail delivery pass failed")


def purge(db_path=None) -> dict:
    conn = _connect(db_path)
    try:
        done = email_admin.purge(conn)
        conn.commit()
        return done
    finally:
        conn.close()


def _loop(interval, db_path) -> None:
    last_purge = 0.0
    while True:
        _safe_pass(db_path)
        if time.time() - last_purge > 86400:
            try:
                purge(db_path)
            except Exception:
                logger.exception("E-mail retention purge failed")
            last_purge = time.time()
        time.sleep(interval)


def start_worker(interval=60, db_path=None) -> bool:
    """Start the background delivery worker once per process."""
    global _WORKER
    if _WORKER and _WORKER.is_alive():
        return False
    _WORKER = threading.Thread(target=_loop, args=(interval, db_path), daemon=True,
                               name="email-outbox-worker")
    _WORKER.start()
    return True


def enqueue(to_address, subject, body, *, kind="transactional", category="general",
            to_ref=None, cc=None, bcc=None, attachments=None, created_by=None,
            stored_email_id=None, db_path=None, reply_to=None) -> dict:
    """Submit one message on its own connection, commit, then deliver."""
    conn = _connect(db_path)
    try:
        result = email_outbox.submit(conn, to_address, subject, body, mode=delivery_mode(),
                                     kind=kind, category=category, to_ref=to_ref, cc=cc,
                                     bcc=bcc, attachments=attachments, created_by=created_by,
                                     stored_email_id=stored_email_id, reply_to=reply_to)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if result["status"] == "queued":
        kick(db_path)
    return result
