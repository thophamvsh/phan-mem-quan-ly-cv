import json
from types import SimpleNamespace

from django.test import SimpleTestCase

from ai_tools.services import (
    _expand_production_clarification_answer,
    _get_time_clarification_message,
    _normalize_missing_data_response,
    _normalize_vinhson_production_tool_call,
    _production_request_needs_plant_clarification,
    _question_seems_context_dependent,
)


class HistoryRelevanceGateTests(SimpleTestCase):
    def test_follow_up_questions_keep_history(self):
        self.assertTrue(_question_seems_context_dependent("so với hôm qua thì sao?"))
        self.assertTrue(_question_seems_context_dependent("còn T1 thì sao?"))
        self.assertTrue(_question_seems_context_dependent("nguyên nhân là gì?"))

    def test_explicit_new_equipment_question_does_not_keep_history(self):
        self.assertFalse(
            _question_seems_context_dependent("Phân tích nhiệt độ MBA T2 Sông Hinh")
        )
        self.assertFalse(
            _question_seems_context_dependent("Phân tích ổ hướng tuabin H1 Vĩnh Sơn")
        )

    def test_standalone_hydrology_or_document_questions_do_not_keep_history(self):
        self.assertFalse(_question_seems_context_dependent("Dự báo mưa Vĩnh Sơn tháng 7"))
        self.assertFalse(_question_seems_context_dependent("Tra cứu quy trình vận hành tràn"))


class MissingDataResponseTests(SimpleTestCase):
    def test_operational_no_data_notice_is_made_user_friendly(self):
        response = _normalize_missing_data_response(
            "Cho tôi xem sản lượng Sông Hinh ngày 01/01/2030",
            "Không có dữ liệu mực nước trong database",
        )

        self.assertIn("Dạ, hiện hệ thống chưa có dữ liệu phù hợp", response)
        self.assertIn("liên hệ kỹ thuật viên", response)
        self.assertNotIn("database", response.lower())

    def test_cause_question_does_not_invent_reason_without_data(self):
        response = _normalize_missing_data_response(
            "Nguyên nhân sản lượng Vĩnh Sơn giảm ngày 01/01/2030 là gì?",
            "Không đủ số liệu lượng mưa đo trạm để tính toán hiệu suất sinh dòng chảy lưu vực.",
        )

        self.assertIn("chưa có đủ dữ liệu", response)
        self.assertIn("chưa có cơ sở tin cậy để phân tích nguyên nhân", response)

    def test_today_production_missing_data_suggests_yesterday(self):
        response = _normalize_missing_data_response(
            "Báo cáo sản lượng Sông Hinh hôm nay",
            "Không tìm thấy dữ liệu cho ngày 10/07/2026.",
        )

        self.assertIn("chỉ có số liệu đã chốt đến D-1", response)
        self.assertIn("ngày hôm qua", response)

    def test_today_operational_report_missing_data_suggests_yesterday_without_production_word(self):
        response = _normalize_missing_data_response(
            "Báo cáo Vĩnh Sơn ngày hôm nay?",
            "Không tìm thấy dữ liệu cho ngày 10/07/2026 và hồ All",
        )

        self.assertIn("dữ liệu vận hành/sản lượng", response)
        self.assertIn("chỉ có số liệu đã chốt đến D-1", response)

    def test_report_with_table_and_missing_data_note_is_preserved(self):
        message = (
            "### Báo cáo\n"
            "| Ngày | Sản lượng |\n"
            "|---|---:|\n"
            "| 01/01/2026 | 12.5 |\n"
            "\n"
            "Ghi chú: một vài thông số không có dữ liệu."
        )

        response = _normalize_missing_data_response(
            "Báo cáo sản lượng Sông Hinh",
            message,
        )

        self.assertEqual(response, message)


class ProductionScopeTests(SimpleTestCase):
    def test_production_question_without_plant_needs_clarification(self):
        self.assertTrue(_production_request_needs_plant_clarification("Báo cáo sản lượng hôm qua?"))
        self.assertFalse(_production_request_needs_plant_clarification("Báo cáo sản lượng Vĩnh Sơn hôm qua?"))
        self.assertFalse(_production_request_needs_plant_clarification("Báo cáo sản lượng 3 nhà máy hôm qua?"))

    def test_vinhson_production_tool_call_uses_all_reservoirs(self):
        tool_call = SimpleNamespace(
            id="call-1",
            function=SimpleNamespace(
                name="get_vinhson_operational_data",
                arguments=json.dumps({"date": "09/07/2026", "reservoir": "Vinh Son -A"}),
            ),
        )

        normalized = _normalize_vinhson_production_tool_call(
            "Báo cáo sản lượng Vĩnh Sơn A hôm qua",
            tool_call,
        )
        args = json.loads(normalized.function.arguments)

        self.assertEqual(args["reservoir"], "All")

    def test_followup_plant_answer_expands_previous_production_question(self):
        history = [
            {"role": "user", "content": "Báo cáo sản lượng hôm nay?"},
            {
                "role": "assistant",
                "content": (
                    "Dạ, anh/chị muốn xem báo cáo sản lượng của nhà máy nào ạ? "
                    "Vui lòng cho em biết Sông Hinh, Vĩnh Sơn, Thượng Kon Tum, hoặc báo cáo tổng hợp 3 nhà máy."
                ),
            },
        ]

        expanded = _expand_production_clarification_answer("Sông Hinh đi", history)

        self.assertIn("Báo cáo sản lượng hôm nay", expanded)
        self.assertIn("Nhà máy: Sông Hinh", expanded)


class TimeClarificationTests(SimpleTestCase):
    def test_report_for_specific_plant_without_time_needs_clarification(self):
        response = _get_time_clarification_message("Báo cáo Vĩnh Sơn")

        self.assertIn("thời gian nào", response)
        self.assertIn("ngày cụ thể", response)
        self.assertIn("tháng/năm", response)

    def test_parameter_for_specific_plant_without_time_needs_clarification(self):
        response = _get_time_clarification_message("Nhiệt độ MBA T1 Vĩnh Sơn")

        self.assertIn("thời gian nào", response)

    def test_specific_plant_report_with_time_does_not_need_clarification(self):
        self.assertEqual(
            _get_time_clarification_message("Báo cáo Vĩnh Sơn ngày hôm nay"),
            "",
        )
        self.assertEqual(
            _get_time_clarification_message("Báo cáo thủy văn Sông Hinh tháng 7/2026"),
            "",
        )
