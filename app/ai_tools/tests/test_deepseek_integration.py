from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from django.conf import settings
from ai_tools.services import _resolve_model, _estimate_cost_usd

User = get_user_model()

class DeepSeekIntegrationTests(TestCase):
    databases = {"default"}

    def test_resolve_model_openai(self):
        provider, model = _resolve_model("openai", "gpt-4o")
        self.assertEqual(provider, "openai")
        self.assertEqual(model, "gpt-4o")

    def test_resolve_model_deepseek(self):
        provider, model = _resolve_model("deepseek", "")
        self.assertEqual(provider, "deepseek")
        self.assertEqual(model, "deepseek-chat")

        provider, model = _resolve_model("deepseek", "deepseek-reasoner")
        self.assertEqual(provider, "deepseek")
        self.assertEqual(model, "deepseek-reasoner")

    @override_settings(AI_TOOLS_PROVIDER="deepseek", AI_TOOLS_DEEPSEEK_MODEL="deepseek-chat")
    def test_resolve_model_uses_configured_default_provider(self):
        provider, model = _resolve_model(None, "")
        self.assertEqual(provider, "deepseek")
        self.assertEqual(model, "deepseek-chat")

    def test_estimate_cost_usd_openai(self):
        # gpt-4o-mini cost
        cost = _estimate_cost_usd("openai", "gpt-4o-mini", 1000000, 1000000)
        self.assertEqual(cost, 0.75)  # 0.150 + 0.600

        # gpt-4o cost
        cost = _estimate_cost_usd("openai", "gpt-4o", 1000000, 1000000)
        self.assertEqual(cost, 12.5)  # 2.500 + 10.000

    def test_estimate_cost_usd_deepseek(self):
        cost = _estimate_cost_usd("deepseek", "deepseek-chat", 1000000, 1000000)
        self.assertEqual(cost, 0.42)  # 0.140 + 0.280


class AiChatAPIVerificationTests(APITestCase):
    databases = {"default"}

    def setUp(self):
        from core.models import UserProfile
        from khovattu.models import Bang_nha_may

        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="ComplexSecurePassword999!"
        )
        self.nha_may = Bang_nha_may.objects.create(
            ma_nha_may="SH",
            ten_nha_may="Song Hinh",
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            nha_may=self.nha_may,
            can_use_ai_tools=True,
        )
        self.client.force_authenticate(user=self.user)

    @patch("ai_tools.views.run_ai_chat")
    def test_api_view_receives_provider_and_model(self, mock_run_ai_chat):
        mock_run_ai_chat.return_value = {
            "session_id": "test-session",
            "response": "Hello from DeepSeek",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "total_tokens": 100,
            "cost_usd": 0.000042,
            "latency_ms": 150,
            "tools_called": 0,
        }

        response = self.client.post(
            "/api/v1/ai/chat/",
            {
                "content": "Test prompt",
                "provider": "deepseek",
                "model": "deepseek-chat"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)
        mock_run_ai_chat.assert_called_once()
        kwargs = mock_run_ai_chat.call_args[1]
        self.assertEqual(kwargs["provider"], "deepseek")
        self.assertEqual(kwargs["model"], "deepseek-chat")

    @patch("ai_tools.views.run_ai_chat")
    def test_api_view_uses_settings_default_when_provider_is_omitted(self, mock_run_ai_chat):
        mock_run_ai_chat.return_value = {
            "session_id": "test-session",
            "response": "Hello from configured default",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "total_tokens": 100,
            "cost_usd": 0.000042,
            "latency_ms": 150,
            "tools_called": 0,
        }

        response = self.client.post(
            "/api/v1/ai/chat/",
            {"content": "Test prompt"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        mock_run_ai_chat.assert_called_once()
        kwargs = mock_run_ai_chat.call_args[1]
        self.assertIsNone(kwargs["provider"])
        self.assertEqual(kwargs["model"], "")
