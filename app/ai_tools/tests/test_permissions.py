from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ai_tools.models import AiConversationMessage
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
from ai_tools.services import _get_tools_and_handlers, _time_of_day_greeting, run_ai_chat
from core.models import UserProfile
from khovattu.models import Bang_nha_may
from thongsothuyvan.models import ThongSoThuyVanCaiDat, ThongsoSanxuat, TramDoMuaVrain


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
            [],
            object(),
            [],
            object(),
        )
        with patch("ai_tools.services._lazy_import_tools", return_value=fake_import):
            tools, *_ = _get_tools_and_handlers(self.vinhson_user)

        self.assertEqual(
            [tool["function"]["name"] for tool in tools],
            ["calculate_reservoir_volume", "get_vinhson_operational_data"],
        )

    def test_service_hides_document_tool_without_document_permission(self):
        fake_import = (
            [_tool("calculate_reservoir_volume")],
            object(),
            object(),
            [],
            object(),
            [],
            object(),
            [],
            object(),
            [_tool("search_internal_documents")],
            object(),
        )
        with patch("ai_tools.services._lazy_import_tools", return_value=fake_import):
            tools, *_ = _get_tools_and_handlers(self.all_factories_user)

        self.assertEqual(
            [tool["function"]["name"] for tool in tools],
            ["calculate_reservoir_volume"],
        )

    def test_service_includes_document_tool_with_document_permission(self):
        self.all_factories_user.profile.can_use_ai_documents = True
        self.all_factories_user.profile.save()
        fake_import = (
            [_tool("calculate_reservoir_volume")],
            object(),
            object(),
            [],
            object(),
            [],
            object(),
            [],
            object(),
            [_tool("search_internal_documents")],
            object(),
        )
        with patch("ai_tools.services._lazy_import_tools", return_value=fake_import):
            tools, *_ = _get_tools_and_handlers(self.all_factories_user)

        self.assertEqual(
            [tool["function"]["name"] for tool in tools],
            ["calculate_reservoir_volume", "search_internal_documents"],
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

    def test_run_ai_chat_greets_with_user_title_and_name_without_provider_call(self):
        self.songhinh_user.profile.chuc_danh = "Phó Tổng Giám Đốc"
        self.songhinh_user.profile.ho_ten = "Nguyễn Văn An"
        self.songhinh_user.profile.save()

        with patch("ai_tools.services._run_openai_chat") as run_openai:
            response = run_ai_chat(
                user=self.songhinh_user,
                content="Hi Nami",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertRegex(
            response["response"],
            (
                r"^Chào buổi (sáng|chiều|tối) Phó Tổng Giám Đốc Nguyễn Văn An! "
                r"Hôm nay ngài có khỏe không\? Ngài muốn được báo cáo thông tin gì trước\?\n"
                r"1\. Báo cáo tình hình sản xuất của 3 nhà máy ngày hôm qua\.\n"
                r"2\. Tổng hợp lượng mưa các trạm 7 ngày gần nhất và dự báo thời tiết cho 7 ngày sắp tới\.\n"
                r"3\. Mực nước giới hạn tuần và phân tích\.\n"
                r"4\. Tình hình thiết bị sự kiện của 3 nhà máy\.$"
            ),
        )
        self.assertEqual(response["tools_called"], 0)
        assistant_message = AiConversationMessage.objects.filter(
            user=self.songhinh_user,
            role=AiConversationMessage.ROLE_ASSISTANT,
        ).latest("id")
        self.assertTrue(assistant_message.meta["greeting"])
        self.assertEqual(assistant_message.content, response["response"])

    def test_run_ai_chat_non_leadership_greeting_keeps_standard_response(self):
        self.songhinh_user.profile.chuc_danh = "Trưởng ca"
        self.songhinh_user.profile.ho_ten = "Nguyễn Văn An"
        self.songhinh_user.profile.save()

        with patch("ai_tools.services._run_openai_chat") as run_openai:
            response = run_ai_chat(
                user=self.songhinh_user,
                content="Hi Nami",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertRegex(
            response["response"],
            r"^Chào buổi (sáng|chiều|tối) Trưởng ca Nguyễn Văn An, tôi có thể giúp gì cho ngài\?$",
        )
        self.assertEqual(response["tools_called"], 0)

    def test_run_ai_chat_short_hi_greets_with_user_profile_without_provider_call(self):
        self.songhinh_user.profile.chuc_danh = "Trưởng ca"
        self.songhinh_user.profile.ho_ten = "Nguyễn Văn An"
        self.songhinh_user.profile.save()

        with patch("ai_tools.services._run_openai_chat") as run_openai:
            response = run_ai_chat(
                user=self.songhinh_user,
                content="Hi!",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertRegex(
            response["response"],
            r"^Chào buổi (sáng|chiều|tối) Trưởng ca Nguyễn Văn An, tôi có thể giúp gì cho ngài\?$",
        )
        self.assertEqual(response["tools_called"], 0)

    def test_run_ai_chat_typo_hi_with_digit_greets_with_user_profile_without_provider_call(self):
        self.songhinh_user.profile.chuc_danh = "Trưởng ca"
        self.songhinh_user.profile.ho_ten = "Nguyễn Văn An"
        self.songhinh_user.profile.save()

        with patch("ai_tools.services._run_openai_chat") as run_openai:
            response = run_ai_chat(
                user=self.songhinh_user,
                content="Hi1",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertRegex(
            response["response"],
            r"^Chào buổi (sáng|chiều|tối) Trưởng ca Nguyễn Văn An, tôi có thể giúp gì cho ngài\?$",
        )
        self.assertEqual(response["tools_called"], 0)

    def test_time_of_day_greeting_uses_local_hour(self):
        cases = (
            (datetime(2026, 6, 12, 8, 0), "Chào buổi sáng"),
            (datetime(2026, 6, 12, 14, 0), "Chào buổi chiều"),
            (datetime(2026, 6, 12, 20, 0), "Chào buổi tối"),
        )
        for current_time, expected in cases:
            with self.subTest(expected=expected), patch("ai_tools.services.timezone.localtime", return_value=current_time):
                self.assertEqual(_time_of_day_greeting(), expected)

    def test_leadership_menu_choice_one_returns_three_plant_production_report(self):
        self.all_factories_user.profile.chuc_danh = "Phó Tổng Giám Đốc"
        self.all_factories_user.profile.ho_ten = "Dương Tấn Tưởng"
        self.all_factories_user.profile.save()
        report_date = timezone.localdate() - timedelta(days=1)
        report_time = timezone.make_aware(datetime.combine(report_date, time(hour=7)))

        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=report_time,
            cot_l=100,
            cot_n=90,
            cot_p=1000,
            cot_r=900,
            cot_w=12000,
            cot_v=9000,
        )
        ThongsoSanxuat.objects.create(
            nha_may="vinhson",
            thoi_gian=report_time,
            cot_c="Vinh Son -A",
            cot_l=50,
            cot_n=45,
            cot_p=500,
            cot_r=450,
            cot_w=6000,
            cot_v=4500,
        )
        ThongsoSanxuat.objects.create(
            nha_may="vinhson",
            thoi_gian=report_time + timedelta(minutes=1),
            cot_c="Vinh Son -B",
            cot_l=50,
            cot_n=45,
            cot_p=500,
            cot_r=450,
            cot_w=6000,
            cot_v=4500,
        )
        ThongsoSanxuat.objects.create(
            nha_may="thuongkontum",
            thoi_gian=report_time,
            cot_l=200,
            cot_n=160,
            cot_p=2000,
            cot_r=1500,
            cot_w=20000,
            cot_v=10000,
        )
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=report_date.year,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_THANG,
            thang=report_date.month,
            sanluong_kehoach_thang=1200,
        )

        greeting = run_ai_chat(
            user=self.all_factories_user,
            content="Hi Nami",
            provider="openai",
            model="",
        )

        with patch("ai_tools.services._run_openai_chat") as run_openai:
            response = run_ai_chat(
                user=self.all_factories_user,
                content="1",
                session_id=greeting["session_id"],
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn(f"**Ngày báo cáo:** {report_date.strftime('%d/%m/%Y')}", response["response"])
        self.assertIn("| Sông Hinh | 90 | 100 | 90.00% | 900 | 1.200 | 75.00% | 9.000 | 12.000 | 75.00% |", response["response"])
        self.assertIn("| Vĩnh Sơn | 90 | 100 | 90.00% | 900 | 1.000 | 90.00% | 9.000 | 12.000 | 75.00% |", response["response"])
        self.assertIn("| Thượng Kon Tum | 160 | 200 | 80.00% | 1.500 | 2.000 | 75.00% | 10.000 | 20.000 | 50.00% |", response["response"])
        self.assertIn("| Tổng cộng | 340 | 400 | 85.00% | 3.300 | 4.200 | 78.57% | 28.000 | 44.000 | 63.64% |", response["response"])

    def test_leadership_menu_choice_two_returns_rainfall_weather_report(self):
        self.all_factories_user.profile.chuc_danh = "Phó Tổng Giám Đốc"
        self.all_factories_user.profile.ho_ten = "Dương Tấn Tưởng"
        self.all_factories_user.profile.save()
        reference_date = date(2026, 6, 13)
        start_date = reference_date - timedelta(days=6)

        for index in range(7):
            record_date = start_date + timedelta(days=index)
            TramDoMuaVrain.objects.create(
                Thoi_gian=timezone.make_aware(datetime.combine(record_date, time.min)),
                Xa_Ea_M_doan=index + 1,
                Ho_A_TD_Vinh_Son=2,
            )

        def fake_forecast(_location):
            return [
                {
                    "date": "2026-06-14",
                    "weather_code": 61,
                    "temperature_min": 24.5,
                    "temperature_max": 31.2,
                    "precipitation": 12.3,
                    "precipitation_probability": 80,
                }
            ]

        greeting = run_ai_chat(
            user=self.all_factories_user,
            content="Hi Nami",
            provider="openai",
            model="",
        )

        with (
            patch("ai_tools.leadership_report.services.report_service.timezone.localdate", return_value=reference_date),
            patch("ai_tools.leadership_report.services.report_service._fetch_weather_forecast", side_effect=fake_forecast),
            patch("ai_tools.services._run_openai_chat") as run_openai,
        ):
            response = run_ai_chat(
                user=self.all_factories_user,
                content="2",
                session_id=greeting["session_id"],
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn("### Tổng hợp lượng mưa và dự báo thời tiết", response["response"])
        self.assertIn("**Mưa đo:** 07/06/2026 - 13/06/2026", response["response"])
        self.assertIn("| Ngày | Xã Ea M'đoan | Thôn 10 - Xã Ea M'Doal | UBND xã Sông Hinh |", response["response"])
        self.assertIn("| 07/06/2026 | 1,0 | - | - | - | - | - | 2,0 | - | - | 3,0 |", response["response"])
        self.assertIn("| 13/06/2026 | 7,0 | - | - | - | - | - | 2,0 | - | - | 9,0 |", response["response"])
        self.assertIn("| Sông Hinh | 2026-06-14 | Mưa nhỏ | 24,5-31,2°C | 12,3 | 80,0% |", response["response"])

    def test_leadership_menu_choice_three_returns_weekly_limit_report(self):
        self.all_factories_user.profile.chuc_danh = "Phó Tổng Giám Đốc"
        self.all_factories_user.profile.ho_ten = "Dương Tấn Tưởng"
        self.all_factories_user.profile.save()

        greeting = run_ai_chat(
            user=self.all_factories_user,
            content="Hi Nami",
            provider="openai",
            model="",
        )

        with (
            patch("ai_tools.leadership_report.services.report_service.timezone.localdate", return_value=date(2026, 6, 13)),
            patch("ai_tools.services._run_openai_chat") as run_openai,
        ):
            response = run_ai_chat(
                user=self.all_factories_user,
                content="3",
                session_id=greeting["session_id"],
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn("### Mực nước giới hạn tuần và phân tích", response["response"])
        self.assertIn("Vĩnh Sơn B hiện chưa có Qcm riêng", response["response"])
        self.assertNotIn("| Vĩnh Sơn C |", response["response"])

    def test_direct_weekly_limit_report_request_does_not_call_model(self):
        self.all_factories_user.profile.chuc_danh = "Phó Tổng Giám Đốc"
        self.all_factories_user.profile.save()

        with (
            patch("ai_tools.leadership_report.services.report_service.timezone.localdate", return_value=date(2026, 6, 13)),
            patch("ai_tools.services._run_openai_chat") as run_openai,
        ):
            response = run_ai_chat(
                user=self.all_factories_user,
                content="Báo cáo mực nước giới hạn tuần và phân tích",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn("### Mực nước giới hạn tuần và phân tích", response["response"])

    def test_monthly_production_plan_request_reads_settings_and_production_data(self):
        report_time = timezone.make_aware(datetime(2026, 7, 9, 7, 0))
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_THANG,
            thang=7,
            sanluong_kehoach_thang=1000,
        )
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="vinhson",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_THANG,
            thang=7,
            sanluong_kehoach_thang=2000,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=report_time,
            cot_o=950,
            cot_r=850,
            sanluong_kh_thang=900,
        )
        ThongsoSanxuat.objects.create(
            nha_may="vinhson",
            thoi_gian=report_time,
            cot_o=1800,
            cot_r=1650,
            sanluong_kh_thang=1700,
        )

        with (
            patch("ai_tools.leadership_report.services.intent_service.timezone.localdate", return_value=date(2026, 7, 10)),
            patch("ai_tools.services._run_openai_chat") as run_openai,
        ):
            response = run_ai_chat(
                user=self.all_factories_user,
                content="Sản lượng kế hoạch Qkh và Qc tháng này bao nhiêu?",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn("### Sản lượng kế hoạch tháng 07/2026", response["response"])
        self.assertIn("| Sông Hinh | 1.000 | 950 | 850 |", response["response"])
        self.assertIn("| Vĩnh Sơn | 2.000 | 1.800 | 1.650 |", response["response"])
        self.assertIn("| Tổng cộng | 3.000 | 2.750 | 2.500 |", response["response"])
        self.assertNotIn("ThongSoThuyVanCaiDat", response["response"])
        self.assertNotIn("ThongsoSanxuat", response["response"])
        self.assertNotIn("cot_o", response["response"])

    def test_monthly_production_plan_request_for_single_factory_user_uses_own_factory(self):
        report_time = timezone.make_aware(datetime(2026, 7, 9, 7, 0))
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_THANG,
            thang=7,
            sanluong_kehoach_thang=1000,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=report_time,
            cot_o=950,
        )

        with (
            patch("ai_tools.leadership_report.services.intent_service.timezone.localdate", return_value=date(2026, 7, 10)),
            patch("ai_tools.services._run_openai_chat") as run_openai,
        ):
            response = run_ai_chat(
                user=self.songhinh_user,
                content="Sản lượng kế hoạch Qkh và Qc tháng này bao nhiêu?",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertIn("| Sông Hinh | 1.000 | 950 |", response["response"])
        self.assertNotIn("Vĩnh Sơn", response["response"])

    def test_monthly_production_plan_without_production_word_does_not_use_model_or_rag(self):
        report_time = timezone.make_aware(datetime(2026, 7, 9, 7, 0))
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_THANG,
            thang=7,
            sanluong_kehoach_thang=1000,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=report_time,
            cot_o=950,
        )

        with (
            patch("ai_tools.leadership_report.services.intent_service.timezone.localdate", return_value=date(2026, 7, 10)),
            patch("ai_tools.services._run_openai_chat") as run_openai,
        ):
            response = run_ai_chat(
                user=self.all_factories_user,
                content="Qkh và Qc tháng này của Sông Hinh?",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn("### Sản lượng kế hoạch tháng 07/2026", response["response"])
        self.assertIn("| Sông Hinh | 1.000 | 950 |", response["response"])
        self.assertNotIn("Dựa theo tài liệu", response["response"])

    def test_year_to_date_production_plan_request_sums_months_until_current_month(self):
        january_time = timezone.make_aware(datetime(2026, 1, 31, 7, 0))
        july_time = timezone.make_aware(datetime(2026, 7, 9, 7, 0))
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_THANG,
            thang=1,
            sanluong_kehoach_thang=1000,
        )
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_THANG,
            thang=7,
            sanluong_kehoach_thang=7000,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=january_time,
            cot_o=900,
            cot_r=800,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=july_time,
            cot_o=6500,
            cot_r=6000,
        )

        with (
            patch("ai_tools.leadership_report.services.intent_service.timezone.localdate", return_value=date(2026, 7, 10)),
            patch("ai_tools.services._run_openai_chat") as run_openai,
        ):
            response = run_ai_chat(
                user=self.all_factories_user,
                content="Qc và Qkh năm 2026 của Sông Hinh?",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn("### Qkh và Qc theo tháng năm 2026", response["response"])
        self.assertIn("**Phạm vi:** Tháng 01/2026 - tháng 07/2026", response["response"])
        self.assertIn("| Sông Hinh | 01/2026 | 1.000 | 900 | 800 |", response["response"])
        self.assertIn("| Sông Hinh | 07/2026 | 7.000 | 6.500 | 6.000 |", response["response"])
        self.assertIn("| Tổng cộng | 01-07/2026 | 8.000 | 7.400 | 6.800 |", response["response"])
        self.assertIn("```chart", response["response"])
        self.assertIn('"yKeys": [', response["response"])
        self.assertIn('"Qkh"', response["response"])
        self.assertIn('"Qc"', response["response"])
        self.assertIn('"Thực hiện"', response["response"])
        self.assertNotIn("Dựa theo tài liệu", response["response"])

    def test_year_to_date_production_plan_uses_current_year_when_asked_from_year_start(self):
        july_time = timezone.make_aware(datetime(2026, 7, 9, 7, 0))
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_THANG,
            thang=7,
            sanluong_kehoach_thang=7000,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=july_time,
            cot_o=6500,
        )

        with (
            patch("ai_tools.leadership_report.services.intent_service.timezone.localdate", return_value=date(2026, 7, 10)),
            patch("ai_tools.services._run_openai_chat") as run_openai,
        ):
            response = run_ai_chat(
                user=self.songhinh_user,
                content="Qc, Qkh từ đầu năm đến giờ",
                provider="openai",
                model="",
        )

        run_openai.assert_not_called()
        self.assertIn("### Qkh và Qc theo tháng năm 2026", response["response"])
        self.assertIn("| Sông Hinh | 07/2026 | 7.000 | 6.500 |", response["response"])
        self.assertIn("| Tổng cộng | 01-07/2026 | 7.000 | 6.500 |", response["response"])
        self.assertIn("```chart", response["response"])
        self.assertNotIn("Vĩnh Sơn", response["response"])

    def test_direct_three_plant_yesterday_production_request_uses_current_date(self):
        self.all_factories_user.profile.chuc_danh = "Phó Tổng Giám Đốc"
        self.all_factories_user.profile.save()
        report_date = timezone.localdate() - timedelta(days=1)
        report_time = timezone.make_aware(datetime.combine(report_date, time(hour=7)))
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=report_time,
            cot_l=100,
            cot_n=90,
            cot_p=1000,
            cot_r=900,
            cot_w=12000,
            cot_v=9000,
        )

        with patch("ai_tools.services._run_openai_chat") as run_openai:
            response = run_ai_chat(
                user=self.all_factories_user,
                content="Báo cáo tình hình sản xuất của 3 nhà máy ngày hôm qua",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn(f"**Ngày báo cáo:** {report_date.strftime('%d/%m/%Y')}", response["response"])
        self.assertNotIn("04/10/2023", response["response"])

    def test_ambiguous_production_report_asks_for_plant_before_model(self):
        with patch("ai_tools.services._run_openai_chat") as run_openai:
            response = run_ai_chat(
                user=self.all_factories_user,
                content="Báo cáo sản lượng hôm qua?",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn("muốn xem báo cáo sản lượng của nhà máy nào", response["response"])
        self.assertIn("Sông Hinh", response["response"])
        self.assertIn("Vĩnh Sơn", response["response"])
        self.assertIn("3 nhà máy", response["response"])

    def test_specific_plant_report_without_time_asks_for_time_before_model(self):
        with patch("ai_tools.services._run_openai_chat") as run_openai:
            response = run_ai_chat(
                user=self.all_factories_user,
                content="Báo cáo Vĩnh Sơn",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn("thời gian nào", response["response"])
        self.assertIn("ngày cụ thể", response["response"])
        self.assertIn("tháng/năm", response["response"])

    def test_specific_plant_parameter_without_time_asks_for_time_before_model(self):
        with patch("ai_tools.services._run_openai_chat") as run_openai:
            response = run_ai_chat(
                user=self.all_factories_user,
                content="Nhiệt độ MBA T1 Vĩnh Sơn",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn("thời gian nào", response["response"])

    def test_production_clarification_followup_keeps_today_context(self):
        first_response = run_ai_chat(
            user=self.all_factories_user,
            content="Báo cáo sản lượng hôm nay?",
            provider="openai",
            model="",
        )

        with patch("ai_tools.services._run_openai_chat") as run_openai:
            run_openai.return_value = ("Không tìm thấy dữ liệu cho ngày 10/07/2026.", 1, 0, 0, 0)
            response = run_ai_chat(
                user=self.all_factories_user,
                session_id=first_response["session_id"],
                content="Sông Hinh đi",
                provider="openai",
                model="",
            )

        run_openai.assert_called_once()
        model_content = run_openai.call_args.kwargs["content"]
        self.assertIn("Báo cáo sản lượng hôm nay", model_content["text"])
        self.assertIn("Nhà máy: Sông Hinh", model_content["text"])
        self.assertIn("chỉ có số liệu đã chốt đến D-1", response["response"])

    def test_direct_three_plant_production_request_accepts_explicit_date(self):
        self.all_factories_user.profile.chuc_danh = "Phó Tổng Giám Đốc"
        self.all_factories_user.profile.save()
        report_date = datetime(2026, 6, 11).date()
        report_time = timezone.make_aware(datetime.combine(report_date, time(hour=7)))
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=report_time,
            cot_l=100,
            cot_n=91,
            cot_p=1000,
            cot_r=910,
            cot_w=12000,
            cot_v=9100,
        )

        with patch("ai_tools.services._run_openai_chat") as run_openai:
            response = run_ai_chat(
                user=self.all_factories_user,
                content="Báo cáo tình hình sản xuất của 3 nhà máy ngày 11/6/2026.",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn("**Ngày báo cáo:** 11/06/2026", response["response"])
        self.assertIn("| Sông Hinh | 91 | 100 | 91.00% | 910 | 1.000 | 91.00% | 9.100 | 12.000 | 75.83% |", response["response"])

    def test_direct_three_plant_production_request_accepts_date_without_year(self):
        self.all_factories_user.profile.chuc_danh = "Phó Tổng Giám Đốc"
        self.all_factories_user.profile.save()
        report_date = date(2026, 6, 11)
        report_time = timezone.make_aware(datetime.combine(report_date, time(hour=7)))
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=report_time,
            cot_l=100,
            cot_n=91,
            cot_p=1000,
            cot_r=910,
            cot_w=12000,
            cot_v=9100,
        )

        with (
            patch("ai_tools.leadership_report.services.intent_service.timezone.localdate", return_value=date(2026, 6, 13)),
            patch("ai_tools.services._run_openai_chat") as run_openai,
        ):
            response = run_ai_chat(
                user=self.all_factories_user,
                content=(
                    "B\u00e1o c\u00e1o t\u00ecnh h\u00ecnh s\u1ea3n xu\u1ea5t "
                    "c\u1ee7a 3 nh\u00e0 m\u00e1y ng\u00e0y 11/6"
                ),
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn("**Ngày báo cáo:** 11/06/2026", response["response"])
        self.assertNotIn("**Ngày báo cáo:** 12/06/2026", response["response"])

    def test_run_ai_chat_does_not_treat_greeting_with_request_as_simple_greeting(self):
        with patch("ai_tools.services._run_openai_chat") as run_openai:
            run_openai.return_value = ("Đang xử lý yêu cầu.", 0, 0, 0, 0)
            response = run_ai_chat(
                user=self.songhinh_user,
                content="Hi Nami phân tích nhiệt độ ổ hướng tuabin H1 Sông Hinh hôm qua",
                provider="openai",
                model="",
            )

        run_openai.assert_called_once()
        self.assertEqual(response["response"], "Đang xử lý yêu cầu.")

    def test_direct_three_plant_production_request_denied_for_non_ptgd(self):
        self.all_factories_user.profile.chuc_danh = "Giám đốc"
        self.all_factories_user.profile.save()

        with patch("ai_tools.services._run_openai_chat") as run_openai:
            run_openai.return_value = ("Chuyển cho LLM xử lý.", 0, 0, 0, 0)
            response = run_ai_chat(
                user=self.all_factories_user,
                content="Báo cáo tình hình sản xuất của 3 nhà máy ngày hôm qua",
                provider="openai",
                model="",
            )

        run_openai.assert_called_once()
        self.assertEqual(response["response"], "Chuyển cho LLM xử lý.")


    def test_actual_water_level_request_denied_for_non_leader(self):
        self.all_factories_user.profile.chuc_danh = "Giám đốc"
        self.all_factories_user.profile.save()

        with patch("ai_tools.services._run_openai_chat") as run_openai:
            response = run_ai_chat(
                user=self.all_factories_user,
                content="bao cao muc nuoc ho thuc te ngay 23/6/2026",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn("chỉ dành cho Tổng Giám Đốc/Phó Tổng Giám Đốc", response["response"])

    def test_actual_water_level_ambiguous_request_asks_leader_for_time(self):
        self.all_factories_user.profile.chuc_danh = "Phó Tổng Giám Đốc"
        self.all_factories_user.profile.save()

        with patch("ai_tools.services._run_openai_chat") as run_openai:
            response = run_ai_chat(
                user=self.all_factories_user,
                content="bao cao muc nuoc ho thuc te",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn("ngày nào", response["response"])
        self.assertIn("khoảng thời gian nào", response["response"])

    def test_actual_water_level_direct_songhinh_range_does_not_call_openai_tools(self):
        self.all_factories_user.profile.chuc_danh = "Phó Tổng Giám Đốc"
        self.all_factories_user.profile.save()

        with patch("ai_tools.services._run_openai_chat") as run_openai:
            response = run_ai_chat(
                user=self.all_factories_user,
                content="Muc nuoc va Qve thuc te cua Song Hinh tu ngay 1/6 den 23/6/2026",
                provider="openai",
                model="",
            )

        run_openai.assert_not_called()
        self.assertEqual(response["tools_called"], 0)
        self.assertIn("01/06/2026 - 23/06/2026", response["response"])
        self.assertIn("Sông Hinh", response["response"])
        self.assertNotIn("Vĩnh Sơn", response["response"])


    def test_actual_water_level_without_actual_keyword_uses_normal_ai_flow(self):
        self.all_factories_user.profile.chuc_danh = "Phó Tổng Giám Đốc"
        self.all_factories_user.profile.save()

        with patch("ai_tools.services._run_openai_chat") as run_openai:
            run_openai.return_value = ("NORMAL FLOW", 0, 0, 0, 0)
            response = run_ai_chat(
                user=self.all_factories_user,
                content="Muc nuoc va Qve cua Song Hinh tu ngay 1/6 den 23/6/2026",
                provider="openai",
                model="",
            )

        run_openai.assert_called_once()
        self.assertEqual(response["response"], "NORMAL FLOW")


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

    def test_chat_stream_returns_sse_events(self):
        user = get_user_model().objects.create_user(
            username="streamuser",
            email="stream@example.com",
            password="testpass123",
        )
        UserProfile.objects.create(
            user=user,
            can_use_ai_tools=True,
            chuc_danh="Trưởng ca",
            ho_ten="Nguyễn Văn An",
        )

        self.client.force_authenticate(user=user)
        response = self.client.post(
            reverse("ai-tools-chat-stream"),
            {"content": "Hi!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("event: status", body)
        self.assertIn("event: delta", body)
        self.assertRegex(body, r"Chào buổi (sáng|chiều|tối) Trưởng ca Nguyễn Văn An")
        self.assertIn("event: done", body)

    def test_chat_endpoint_supports_stream_flag(self):
        user = get_user_model().objects.create_user(
            username="streamflag",
            email="streamflag@example.com",
            password="testpass123",
        )
        UserProfile.objects.create(user=user, can_use_ai_tools=True)

        self.client.force_authenticate(user=user)
        response = self.client.post(
            reverse("ai-tools-chat"),
            {"content": "Hi!", "stream": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/event-stream")
