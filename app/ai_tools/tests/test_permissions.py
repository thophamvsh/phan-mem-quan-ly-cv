from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ai_tools.permissions import (
    AI_TOOL_SCOPE_SONGHINH,
    AI_TOOL_SCOPE_VINHSON,
    AI_TOOL_SCOPE_WATER,
    can_user_use_ai_tool,
    filter_ai_tools_for_user,
    get_ai_tool_scope_denial_message,
    get_ai_tool_scopes_for_user,
    get_requested_ai_tool_scope_from_text,
)
from ai_tools.services import _get_tools_and_handlers, run_ai_chat
from core.models import UserProfile
from khovattu.models import Bang_nha_may


def _tool(name):
    return {"type": "function", "function": {"name": name, "parameters": {"type": "object"}}}


class AiToolFactoryScopeTests(TestCase):
    def setUp(self):
        self.songhinh = Bang_nha_may.objects.create(
            ma_nha_may="SH",
            ten_nha_may="Song Hinh",
        )
        self.vinhson = Bang_nha_may.objects.create(
            ma_nha_may="VS",
            ten_nha_may="Vinh Son",
        )
        self.tkt = Bang_nha_may.objects.create(
            ma_nha_may="TKT",
            ten_nha_may="Thuong Kon Tum",
        )

        User = get_user_model()
        self.songhinh_user = User.objects.create_user(
            username="songhinh",
            email="songhinh@example.com",
            password="testpass123",
        )
        UserProfile.objects.create(
            user=self.songhinh_user,
            nha_may=self.songhinh,
            can_use_ai_tools=True,
        )

        self.vinhson_user = User.objects.create_user(
            username="vinhson",
            email="vinhson@example.com",
            password="testpass123",
        )
        UserProfile.objects.create(
            user=self.vinhson_user,
            nha_may=self.vinhson,
            can_use_ai_tools=True,
        )

        self.tkt_user = User.objects.create_user(
            username="tkt",
            email="tkt@example.com",
            password="testpass123",
        )
        UserProfile.objects.create(
            user=self.tkt_user,
            nha_may=self.tkt,
            can_use_ai_tools=True,
        )

        self.all_factories_user = User.objects.create_user(
            username="allfactories",
            email="allfactories@example.com",
            password="testpass123",
        )
        UserProfile.objects.create(
            user=self.all_factories_user,
            is_all_factories=True,
            can_use_ai_tools=True,
        )

        self.tools = [
            _tool("calculate_reservoir_volume"),
            _tool("get_songhinh_rainfall_statistics"),
            _tool("get_vinhson_operational_data"),
        ]

    def test_songhinh_user_only_gets_common_and_songhinh_tools(self):
        scopes = get_ai_tool_scopes_for_user(self.songhinh_user)
        self.assertEqual(scopes, {AI_TOOL_SCOPE_WATER, AI_TOOL_SCOPE_SONGHINH})
        self.assertTrue(can_user_use_ai_tool(self.songhinh_user, "get_songhinh_rainfall_statistics"))
        self.assertFalse(can_user_use_ai_tool(self.songhinh_user, "get_vinhson_operational_data"))

        names = [tool["function"]["name"] for tool in filter_ai_tools_for_user(self.songhinh_user, self.tools)]
        self.assertEqual(names, ["calculate_reservoir_volume", "get_songhinh_rainfall_statistics"])

    def test_vinhson_user_only_gets_common_and_vinhson_tools(self):
        scopes = get_ai_tool_scopes_for_user(self.vinhson_user)
        self.assertEqual(scopes, {AI_TOOL_SCOPE_WATER, AI_TOOL_SCOPE_VINHSON})
        self.assertFalse(can_user_use_ai_tool(self.vinhson_user, "get_songhinh_rainfall_statistics"))
        self.assertTrue(can_user_use_ai_tool(self.vinhson_user, "get_vinhson_operational_data"))

        names = [tool["function"]["name"] for tool in filter_ai_tools_for_user(self.vinhson_user, self.tools)]
        self.assertEqual(names, ["calculate_reservoir_volume", "get_vinhson_operational_data"])

    def test_thuong_kon_tum_user_uses_songhinh_tool_group(self):
        scopes = get_ai_tool_scopes_for_user(self.tkt_user)
        self.assertEqual(scopes, {AI_TOOL_SCOPE_WATER, AI_TOOL_SCOPE_SONGHINH})

    def test_all_factories_user_gets_all_tools(self):
        names = [tool["function"]["name"] for tool in filter_ai_tools_for_user(self.all_factories_user, self.tools)]
        self.assertEqual(
            names,
            [
                "calculate_reservoir_volume",
                "get_songhinh_rainfall_statistics",
                "get_vinhson_operational_data",
            ],
        )

    def test_service_filters_tools_before_provider_receives_them(self):
        fake_import = (
            [_tool("calculate_reservoir_volume")],
            object(),
            object(),
            [_tool("get_songhinh_rainfall_statistics")],
            object(),
            [_tool("get_vinhson_operational_data")],
            object(),
        )
        with patch("ai_tools.services._lazy_import_tools", return_value=fake_import):
            tools, *_ = _get_tools_and_handlers(self.vinhson_user)

        self.assertEqual(
            [tool["function"]["name"] for tool in tools],
            ["calculate_reservoir_volume", "get_vinhson_operational_data"],
        )

    def test_detects_accented_vinhson_request(self):
        self.assertEqual(
            get_requested_ai_tool_scope_from_text("Cho tôi xem dữ liệu nhà máy Vĩnh Sơn"),
            AI_TOOL_SCOPE_VINHSON,
        )

    def test_songhinh_user_gets_vinhson_denial_message(self):
        message = get_ai_tool_scope_denial_message(
            self.songhinh_user,
            "Cho tôi xem dữ liệu nhà máy Vĩnh Sơn",
        )

        self.assertEqual(
            message,
            "Xin lỗi! Bạn không được quyền hỏi thông tin nhà máy Vĩnh Sơn, xin bạn hãy hỏi nhà máy của mình.",
        )

    def test_run_ai_chat_denies_cross_factory_before_provider_call(self):
        with patch("ai_tools.services._run_openai_chat") as run_openai:
            response = run_ai_chat(
                user=self.songhinh_user,
                content="Cho tôi xem dữ liệu nhà máy Vĩnh Sơn",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(
            response["response"],
            "Xin lỗi! Bạn không được quyền hỏi thông tin nhà máy Vĩnh Sơn, xin bạn hãy hỏi nhà máy của mình.",
        )
        self.assertEqual(response["tools_called"], 0)


class AiToolsApiPermissionTests(APITestCase):
    def test_chat_requires_ai_tools_permission(self):
        user = get_user_model().objects.create_user(
            username="noai",
            email="noai@example.com",
            password="testpass123",
        )
        UserProfile.objects.create(user=user, can_use_ai_tools=False)

        self.client.force_authenticate(user=user)
        response = self.client.post(
            reverse("ai-tools-chat"),
            {"content": "Kiem tra muc nuoc Song Hinh"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
