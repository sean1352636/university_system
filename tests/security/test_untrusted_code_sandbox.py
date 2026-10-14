"""Student-submitted code does not run on the host by default.

The auto-grader used to hand submissions to ``python3`` with only a timeout,
so a coding question was remote code execution with the grader's filesystem,
database, environment and network.
"""

from __future__ import annotations

import pytest

from education_system.platform.kernel import untrusted_code as sandbox

pytestmark = pytest.mark.security


@pytest.mark.parametrize("app_env", ["production", "development", "testing", ""])
def test_refuses_by_default_in_every_environment(monkeypatch, app_env):
    """The gate is the sandbox setting, not the environment."""
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.delenv("EDU_CODE_SANDBOX", raising=False)

    result = sandbox.run_untrusted_python("print('hello')")

    assert result.executed is False
    assert result.refused_reason
    assert result.stdout == ""


def test_unset_backend_reads_as_disabled(monkeypatch):
    monkeypatch.delenv("EDU_CODE_SANDBOX", raising=False)
    assert sandbox.active_backend() == "disabled"


@pytest.mark.parametrize("value", ["", "none", "sandbox", "Docker!", "off"])
def test_an_unrecognised_backend_is_not_a_licence_to_run(monkeypatch, value):
    monkeypatch.setenv("EDU_CODE_SANDBOX", value)
    assert sandbox.active_backend() == "disabled"


def test_host_backend_needs_an_explicit_acknowledgement(monkeypatch):
    monkeypatch.setenv("EDU_CODE_SANDBOX", "host")
    monkeypatch.delenv("EDU_CODE_SANDBOX_ACCEPT_HOST_RISK", raising=False)

    result = sandbox.run_untrusted_python("print('hello')")

    assert result.executed is False
    assert "ACCEPT_HOST_RISK" in result.refused_reason

    # A near-miss value is not an acknowledgement either.
    monkeypatch.setenv("EDU_CODE_SANDBOX_ACCEPT_HOST_RISK", "yes")
    assert sandbox.run_untrusted_python("print('hello')").executed is False


def test_a_refusal_is_not_a_wrong_answer():
    """``executed`` must distinguish "did not run" from "ran and failed"."""
    refused = sandbox.SandboxResult(refused_reason="disabled")
    ran_and_failed = sandbox.SandboxResult(stdout="", exit_code=1)

    assert refused.executed is False and refused.ok is False
    assert ran_and_failed.executed is True and ran_and_failed.ok is False


@pytest.mark.slow
class TestNamespaceBackend:
    """Behaviour of the unshare backend, where the host supports it."""

    @pytest.fixture(autouse=True)
    def _backend(self, monkeypatch):
        import shutil

        if shutil.which("unshare") is None:  # pragma: no cover - host dependent
            pytest.skip("unshare(1) is not available")
        monkeypatch.setenv("EDU_CODE_SANDBOX", "unshare")

    def test_a_correct_submission_still_grades(self):
        result = sandbox.run_untrusted_python("print(int(input()) * 2)", stdin="21\n")
        assert result.ok is True
        assert result.stdout.strip() == "42"

    def test_secrets_are_not_inherited(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "hunter2")
        code = "import os; print([k for k in os.environ if 'SECRET' in k])"

        result = sandbox.run_untrusted_python(code)

        assert result.ok is True
        assert "JWT_SECRET" not in result.stdout

    def test_the_grader_cwd_is_not_visible(self):
        result = sandbox.run_untrusted_python("import os; print(sorted(os.listdir('.')))")
        assert result.stdout.strip() == "['submission.py']"

    def test_network_is_unavailable(self):
        code = (
            "import socket\n"
            "try:\n"
            "    socket.create_connection(('1.1.1.1', 53), timeout=2)\n"
            "    print('REACHED')\n"
            "except OSError:\n"
            "    print('BLOCKED')\n"
        )
        assert sandbox.run_untrusted_python(code).stdout.strip() == "BLOCKED"

    def test_an_infinite_loop_is_stopped(self):
        result = sandbox.run_untrusted_python("while True: pass", timeout=2)
        assert result.timed_out is True
        assert result.ok is False

    def test_a_memory_bomb_is_capped(self):
        result = sandbox.run_untrusted_python("x = bytearray(10 ** 9)", timeout=5, memory_mb=64)
        assert result.ok is False

    def test_output_is_truncated(self):
        result = sandbox.run_untrusted_python("print('A' * 100000)", output_limit=1000)
        assert len(result.stdout) <= 1000
