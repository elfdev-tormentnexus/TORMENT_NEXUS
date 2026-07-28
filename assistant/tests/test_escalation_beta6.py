import os
import unittest
from unittest import mock

from core import escalation


class EscalationBeta6Tests(unittest.TestCase):
    def _response(self, body):
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = body
        return response

    def test_official_openai_default_uses_responses_api_without_storage(self):
        response = self._response({
            "model": "gpt-5.6-sol",
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": "Answer."}],
            }],
        })
        with mock.patch.dict(
            os.environ,
            {
                "TORMENT_NEXUS_ESCALATION": "1",
                "TORMENT_NEXUS_OPENAI_KEY": "explicit-test-key",
            },
            clear=False,
        ), mock.patch.object(
            escalation.requests, "post", return_value=response
        ) as post:
            os.environ.pop("TORMENT_NEXUS_ESCALATION_OPENAI_URL", None)
            provider, model, answer = escalation.escalate("question", "openai")

        self.assertEqual((provider, model, answer), (
            "openai", "gpt-5.6-sol", "Answer.",
        ))
        self.assertEqual(post.call_args.args[0], escalation.DEFAULT_OPENAI_URL)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["input"], "question")
        self.assertIs(payload["store"], False)
        self.assertNotIn("messages", payload)

    def test_plain_http_is_allowed_only_for_loopback(self):
        valid, _ = escalation._validate_openai_url(
            "http://127.0.0.1:11434/v1/chat/completions"
        )
        invalid, reason = escalation._validate_openai_url(
            "http://models.example.test/v1/chat/completions"
        )
        self.assertTrue(valid)
        self.assertFalse(invalid)
        self.assertIn("HTTPS", reason)

    def test_ambient_openai_key_is_not_forwarded_to_custom_host(self):
        with mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "broad-ambient-key",
                "TORMENT_NEXUS_ESCALATION_OPENAI_URL":
                    "https://compatible.example.test/v1/chat/completions",
            },
            clear=False,
        ):
            os.environ.pop("TORMENT_NEXUS_OPENAI_KEY", None)
            with mock.patch.object(
                escalation, "_read_key_file", return_value=""
            ):
                self.assertEqual(escalation._key_for("openai"), "")

    def test_custom_chat_endpoint_keeps_compatible_request_shape(self):
        response = self._response({
            "model": "local-model",
            "choices": [{"message": {"content": "Local answer"}}],
        })
        environment = {
            "TORMENT_NEXUS_ESCALATION": "1",
            "TORMENT_NEXUS_OPENAI_KEY": "explicit-custom-key",
            "TORMENT_NEXUS_ESCALATION_OPENAI_URL":
                "http://localhost:11434/v1/chat/completions",
            "TORMENT_NEXUS_ESCALATION_OPENAI_MODEL": "local-model",
        }
        with mock.patch.dict(
            os.environ, environment, clear=False
        ), mock.patch.object(
            escalation.requests, "post", return_value=response
        ) as post:
            _provider, _model, answer = escalation.escalate(
                "local question", "openai"
            )

        self.assertEqual(answer, "Local answer")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(
            payload["messages"],
            [{"role": "user", "content": "local question"}],
        )

    def test_external_control_sequences_are_removed(self):
        dirty = "\x1b[31mred\x1b[0m\nokay\x00\x07"
        self.assertEqual(escalation.sanitize_external_text(dirty), "red\nokay")


if __name__ == "__main__":
    unittest.main()

