"""The applicant's Firm / Insurance / Declined reply, recorded uni-side.

The reply used to be typed into the sixth form's own choice dialog. It
now lives with the university that made the offer, so these cover the
move: the guards on what can be replied to, the one-Firm rule the sixth
form still enforces underneath, and the rule about when the student is
emailed — which is on a *change*, not on every save.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def sent(monkeypatch, ucas_env):
    """Capture final-decision emails instead of writing to the mail log."""
    calls: list[tuple] = []
    monkeypatch.setattr(
        ucas_env.uni_ucas, "_send_final_decision_email",
        lambda choice, final: calls.append((choice.choice_id, final)))
    return calls


class TestGuards:
    def test_unknown_reply_is_refused(self, ucas_env):
        with pytest.raises(ucas_env.uni_ucas.UcasError) as e:
            ucas_env.uni_ucas.record_final_decision(
                ucas_env.our_choice_id, "Maybe")
        assert "Firm" in str(e.value)

    def test_unknown_choice_is_refused(self, ucas_env):
        with pytest.raises(ucas_env.uni_ucas.UcasError):
            ucas_env.uni_ucas.record_final_decision(999_999, "Firm")

    def test_reply_needs_an_offer_to_reply_to(self, ucas_env, sent):
        # The seeded choice at our university is still 'Awaiting'.
        with pytest.raises(ucas_env.uni_ucas.UcasError) as e:
            ucas_env.uni_ucas.record_final_decision(
                ucas_env.our_choice_id, "Firm")
        assert "only be recorded against an offer" in str(e.value)
        assert sent == []

    def test_rejection_cannot_be_firmed(self, ucas_env, sent):
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Rejected")
        with pytest.raises(ucas_env.uni_ucas.UcasError):
            ucas_env.uni_ucas.record_final_decision(
                ucas_env.our_choice_id, "Firm")

    def test_clearing_a_reply_needs_no_offer(self, ucas_env, sent):
        # Nothing to clear, but clearing must never be the thing that
        # fails — it is the escape hatch from a reply typed in error.
        out = ucas_env.uni_ucas.record_final_decision(
            ucas_env.our_choice_id, None)
        assert out.final_decision is None
        assert sent == []


class TestRecording:
    def _offer(self, ucas_env):
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Conditional Offer",
            offer_terms="ABB including B in Mathematics")

    def test_reply_is_written_to_the_sixth_form_row(self, ucas_env, sent):
        self._offer(ucas_env)
        out = ucas_env.uni_ucas.record_final_decision(
            ucas_env.our_choice_id, "Firm", issued_by="admissions1")
        assert out.final_decision == "Firm"
        stored = ucas_env.sf_ucas.get_choice(ucas_env.our_choice_id)
        assert stored.final_decision == "Firm"

    def test_the_offer_itself_is_left_alone(self, ucas_env, sent):
        self._offer(ucas_env)
        ucas_env.uni_ucas.record_final_decision(
            ucas_env.our_choice_id, "Firm")
        stored = ucas_env.sf_ucas.get_choice(ucas_env.our_choice_id)
        assert stored.decision_status == "Conditional Offer"
        assert stored.offer_terms == "ABB including B in Mathematics"

    def test_student_is_emailed_once_per_change(self, ucas_env, sent):
        self._offer(ucas_env)
        ucas_env.uni_ucas.record_final_decision(
            ucas_env.our_choice_id, "Firm")
        assert sent == [(ucas_env.our_choice_id, "Firm")]

        # Re-saving the same reply is not a new decision and must not
        # re-confirm one the student already has in writing.
        ucas_env.uni_ucas.record_final_decision(
            ucas_env.our_choice_id, "Firm")
        assert len(sent) == 1

        # Changing it is.
        ucas_env.uni_ucas.record_final_decision(
            ucas_env.our_choice_id, "Insurance")
        assert sent[-1] == (ucas_env.our_choice_id, "Insurance")

    def test_clearing_a_reply_emails_nobody(self, ucas_env, sent):
        self._offer(ucas_env)
        ucas_env.uni_ucas.record_final_decision(
            ucas_env.our_choice_id, "Firm")
        sent.clear()
        out = ucas_env.uni_ucas.record_final_decision(
            ucas_env.our_choice_id, "")
        assert out.final_decision is None
        assert sent == []

    def test_a_failing_email_does_not_lose_the_reply(
            self, ucas_env, monkeypatch):
        self._offer(ucas_env)

        def _boom(*_a, **_k):
            raise RuntimeError("mail server down")

        monkeypatch.setattr(ucas_env.uni_ucas,
                            "_send_final_decision_email", _boom)
        out = ucas_env.uni_ucas.record_final_decision(
            ucas_env.our_choice_id, "Firm")
        assert out.final_decision == "Firm"

    def test_one_firm_per_application(self, ucas_env, sent):
        """The sixth form's uniqueness rule still bites from up here."""
        self._offer(ucas_env)
        ucas_env.uni_ucas.record_final_decision(
            ucas_env.our_choice_id, "Firm")
        # The second choice is at another university and already holds a
        # conditional offer, so it is repliable — but Firm is taken.
        with pytest.raises(ucas_env.uni_ucas.UcasError) as e:
            ucas_env.uni_ucas.record_final_decision(
                ucas_env.their_choice_id, "Firm")
        assert "Firm" in str(e.value)

    def test_insurance_alongside_firm_is_allowed(self, ucas_env, sent):
        self._offer(ucas_env)
        ucas_env.uni_ucas.record_final_decision(
            ucas_env.our_choice_id, "Firm")
        out = ucas_env.uni_ucas.record_final_decision(
            ucas_env.their_choice_id, "Insurance")
        assert out.final_decision == "Insurance"


class TestEmailBody:
    """The email is the student's written record of what they accepted,
    so the three outcomes have to say three different things."""

    @pytest.mark.parametrize("reply, expected", [
        ("Firm",      "FIRM choice"),
        ("Insurance", "INSURANCE choice"),
        ("Declined",  "DECLINED this offer"),
    ])
    def test_each_outcome_has_its_own_explanation(
            self, ucas_env, monkeypatch, reply, expected):
        rendered: list[dict] = []

        def _capture(name, context, **kwargs):
            rendered.append({"name": name, **context})
            return type("M", (), {"message_id": 1})()

        import education_system.systems.sixth_form.domain.operations.communications.messages.email_templates as tpl
        monkeypatch.setattr(tpl, "send_from_template", _capture)

        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Unconditional Offer")
        ucas_env.uni_ucas.record_final_decision(
            ucas_env.our_choice_id, reply)

        assert len(rendered) == 1
        ctx = rendered[0]
        assert ctx["name"] == "ucas_final_decision"
        assert ctx["final_decision"] == reply
        assert ctx["final_decision_upper"] == reply.upper()
        assert expected in ctx["outcome_block"]
        assert ctx["university"] == ucas_env.home
