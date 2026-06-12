from django.test import SimpleTestCase

from ai_tools.services import _question_seems_context_dependent


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
