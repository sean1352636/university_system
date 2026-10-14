"""Running untrusted, student-submitted code.

The auto-grader used to write a student's Python to a temp file and hand it to
the host interpreter with nothing but a timeout::

    subprocess.run(['python3', tmp_path], input=..., timeout=10)

A timeout bounds how *long* the code runs, not what it may do. The submission
inherited the grader's identity: its filesystem, its ``student_records.db``,
its environment (API keys, DB paths, JWT secrets), its network position inside
the institution, and its ability to spawn further processes. A submission is
attacker-controlled input by definition — a coursework question is an open
invitation to send code — so this is remote code execution with the grader's
privileges, triggered by anyone who can submit an assignment.

This module makes that a deliberate, configured decision instead of a default.

Backends
--------
Chosen with ``EDU_CODE_SANDBOX``:

``disabled`` (default, and the value assumed when unset)
    Refuse to execute. Coding questions come back ungraded and flagged for a
    human, which is the safe failure: an ungraded submission is a nuisance, a
    compromised grader is an incident.

``docker`` / ``podman``
    The recommended setting. Runs in a throwaway container: no network, a
    read-only root filesystem, dropped capabilities, an unprivileged user, and
    memory/PID caps. Nothing of the host is mounted.

``unshare``
    A middle option for hosts without a container runtime. Uses a user + net +
    PID namespace, so the code has **no network** and cannot see host
    processes. It does *not* get a private filesystem: the code can still read
    what the grader's account can read. Better than nothing, weaker than a
    container — the log says so on every run.

``host``
    No isolation at all — the original behaviour. Requires a second, explicit
    acknowledgement in ``EDU_CODE_SANDBOX_ACCEPT_HOST_RISK`` so it cannot be
    switched on by someone skim-reading a config file.

Every backend additionally gets, from the parent side: a scrubbed environment
(no inherited secrets), a fresh empty working directory, CPU/memory/file-size/
process rlimits, no bytecode writes, ``-I`` isolated mode, and truncated
output.
"""

from __future__ import annotations

import logging
import os
import resource
import shutil
import subprocess  # nosec B404 - running code is this module's purpose
import sys
import tempfile
from dataclasses import dataclass
from typing import Optional, Sequence

logger = logging.getLogger(__name__)

__all__ = [
    "SandboxResult",
    "SandboxUnavailable",
    "active_backend",
    "run_untrusted_python",
]

#: Backends in descending order of the isolation they provide.
_BACKENDS = ("docker", "podman", "unshare", "host", "disabled")

#: The literal a deployer must set to accept running submissions unisolated.
_HOST_RISK_ACK = "i-accept-arbitrary-code-execution"

#: Container image for the container backends. Deliberately a plain upstream
#: Python image: it must contain nothing of this institution.
_IMAGE = os.getenv("EDU_CODE_SANDBOX_IMAGE", "python:3.11-alpine")

#: Environment handed to the submission. Everything else is dropped, so a
#: submission cannot read a database path, a JWT secret or an API key out of
#: its own environment.
_CLEAN_ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "HOME": "/tmp",  # nosec B108 - inside the sandbox, not a host path
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONUNBUFFERED": "1",
    "PYTHONNOUSERSITE": "1",
}


class SandboxUnavailable(RuntimeError):
    """Raised when the configured backend cannot be used."""


@dataclass(frozen=True)
class SandboxResult:
    """Outcome of one attempt to run a submission."""

    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    timed_out: bool = False
    #: Set when the code was never run. ``executed`` is then False and the
    #: caller must not treat the empty stdout as a wrong answer.
    refused_reason: Optional[str] = None

    @property
    def executed(self) -> bool:
        return self.refused_reason is None

    @property
    def ok(self) -> bool:
        return self.executed and not self.timed_out and self.exit_code == 0


def active_backend() -> str:
    """The backend name in force, normalised.

    An unset or unrecognised value reads as ``disabled`` — a typo in the
    deployment config must not silently fall through to running code.
    """
    raw = (os.getenv("EDU_CODE_SANDBOX") or "disabled").strip().lower()
    if raw not in _BACKENDS:
        logger.error(
            "EDU_CODE_SANDBOX=%r is not one of %s; refusing to run untrusted code",
            raw, ", ".join(_BACKENDS),
        )
        return "disabled"
    return raw


def _host_execution_acknowledged() -> bool:
    return (os.getenv("EDU_CODE_SANDBOX_ACCEPT_HOST_RISK") or "").strip() == _HOST_RISK_ACK


def _limits(timeout: int, memory_mb: int):
    """Return a ``preexec_fn`` applying rlimits in the child before exec.

    A memory bomb is capped by RLIMIT_AS, a disk-filling loop by RLIMIT_FSIZE
    and a spin loop by RLIMIT_CPU.

    ``RLIMIT_NPROC`` is deliberately **not** set here. It counts every process
    belonging to the real uid, not just this process's descendants, so outside
    a container — where the grader shares its uid with the rest of the host
    session — any cap tight enough to stop a fork bomb is already exceeded
    before the submission starts, and every single run dies with "fork
    failed". Process-count containment is a property of the container
    backends (``--pids-limit``); under ``unshare`` a fork bomb is at least
    confined to the PID namespace and reaped when the namespace leader is
    killed at the timeout. It is one more reason to prefer a container.
    """

    def _apply() -> None:  # pragma: no cover - runs in the forked child
        # CPU seconds: a hard backstop under the wall-clock timeout, so a
        # process that ignores SIGTERM still dies.
        resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout + 1))
        as_bytes = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (as_bytes, as_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))  # no file writes
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # The session is detached by ``start_new_session=True`` on the Popen
        # call — calling setsid() here as well fails with EPERM, because the
        # child is already a session leader by then.

    return _apply


def _container_command(runtime: str, workdir: str, timeout: int, memory_mb: int) -> Sequence[str]:
    """Argv for docker/podman. Nothing of the host is mounted."""
    return [
        runtime, "run", "--rm", "--interactive",
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "65534:65534",          # nobody
        "--memory", f"{memory_mb}m",
        "--pids-limit", "64",
        "--cpus", "1",
        # The submission is mounted read-only; /tmp is a small tmpfs so the
        # interpreter has somewhere to work but nothing persists.
        "--mount", f"type=bind,source={workdir}/submission.py,target=/submission.py,readonly",
        "--tmpfs", "/tmp:rw,size=16m,noexec",
        "--workdir", "/tmp",
        _IMAGE,
        "python3", "-I", "-B", "/submission.py",
    ]


def _unshare_command(script: str) -> Sequence[str]:
    """Argv for the namespace backend: no network, no host process table."""
    return [
        "unshare", "--user", "--map-root-user", "--net", "--pid", "--fork",
        # --mount-proc gives the namespace its own /proc, so the submission
        # sees exactly one process (itself) instead of the host process table.
        "--mount-proc",
        "--", sys.executable or "python3", "-I", "-B", script,
    ]


def run_untrusted_python(
    code: str,
    stdin: str = "",
    *,
    timeout: int = 10,
    memory_mb: int = 256,
    output_limit: int = 64 * 1024,
) -> SandboxResult:
    """Run *code* against *stdin* under the configured isolation.

    Never raises for anything the submission does — a refusal, a crash, a
    timeout and a memory bomb all come back as a :class:`SandboxResult`. The
    caller distinguishes "ran and failed" (``executed`` true) from "was not
    run" (``refused_reason`` set), because scoring a refusal as a wrong answer
    would quietly zero every student the day the sandbox breaks.
    """
    backend = active_backend()

    if backend == "disabled":
        return SandboxResult(refused_reason=(
            "Code execution is disabled. Set EDU_CODE_SANDBOX to a sandbox "
            "backend (docker, podman or unshare) to grade coding questions."
        ))

    if backend == "host":
        if not _host_execution_acknowledged():
            return SandboxResult(refused_reason=(
                "EDU_CODE_SANDBOX=host runs submissions with no isolation and "
                "requires EDU_CODE_SANDBOX_ACCEPT_HOST_RISK to be set to the "
                "documented acknowledgement string."
            ))
        logger.warning(
            "Running a student submission with NO isolation (EDU_CODE_SANDBOX=host). "
            "It has this process's filesystem and network access."
        )

    if backend in ("docker", "podman") and shutil.which(backend) is None:
        return SandboxResult(refused_reason=f"EDU_CODE_SANDBOX={backend} but {backend} is not installed.")
    if backend == "unshare" and shutil.which("unshare") is None:
        return SandboxResult(refused_reason="EDU_CODE_SANDBOX=unshare but unshare(1) is not available.")

    # A fresh directory that contains only the submission: whatever the code
    # does with relative paths, it is not doing it in the grader's cwd.
    workdir = tempfile.mkdtemp(prefix="edu-submission-")
    script = os.path.join(workdir, "submission.py")
    try:
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(code or "")
        os.chmod(script, 0o444)

        if backend in ("docker", "podman"):
            argv = _container_command(backend, workdir, timeout, memory_mb)
            preexec = None  # the runtime applies its own limits
        elif backend == "unshare":
            argv = _unshare_command(script)
            preexec = _limits(timeout, memory_mb)
            logger.info(
                "Grading a submission under namespace isolation: no network, but "
                "the host filesystem is still readable. Prefer a container runtime."
            )
        else:
            argv = [sys.executable or "python3", "-I", "-B", script]
            preexec = _limits(timeout, memory_mb)

        try:
            completed = subprocess.run(  # nosec B603 - argv is built here, never shell
                argv,
                input=stdin or "",
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=workdir,
                env=dict(_CLEAN_ENV),
                preexec_fn=preexec,
                start_new_session=True,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(timed_out=True, stderr=f"Execution timed out ({timeout}s limit).")
        except OSError as exc:
            return SandboxResult(refused_reason=f"Sandbox could not start: {exc}")

        return SandboxResult(
            stdout=(completed.stdout or "")[:output_limit],
            stderr=(completed.stderr or "")[:output_limit],
            exit_code=completed.returncode,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
