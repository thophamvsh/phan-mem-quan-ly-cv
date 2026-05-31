from django.test import SimpleTestCase
from ..sync_views import safe_int_vinhson, safe_float_vinhson_decimal, safe_float

class ThongSoThuyVanParserTests(SimpleTestCase):
    def test_safe_int_vinhson(self):
        # Kiểm tra chuỗi chứa phân cách dấu chấm
        self.assertEqual(safe_int_vinhson("150.000"), 150000.0)
        self.assertEqual(safe_int_vinhson("1.200.000"), 1200000.0)

        # Kiểm tra chuỗi chứa phân cách dấu phẩy
        self.assertEqual(safe_int_vinhson("150,000"), 150000.0)
        self.assertEqual(safe_int_vinhson("1,200,000"), 1200000.0)

        # Kiểm tra số nguyên dạng chuỗi thông thường
        self.assertEqual(safe_int_vinhson("150"), 150.0)
        self.assertEqual(safe_int_vinhson(" 150 "), 150.0)

        # Kiểm tra kiểu số sẵn có
        self.assertEqual(safe_int_vinhson(150000), 150000.0)
        self.assertEqual(safe_int_vinhson(150000.75), 150000.0)

        # Kiểm tra trường hợp None hoặc rỗng
        self.assertIsNone(safe_int_vinhson(None))
        self.assertIsNone(safe_int_vinhson(""))
        self.assertIsNone(safe_int_vinhson("   "))

        # Kiểm tra chuỗi không hợp lệ
        self.assertIsNone(safe_int_vinhson("abc"))

    def test_safe_float_vinhson_decimal(self):
        # Kiểm tra chuyển đổi số thập phân với dấu phẩy/chấm và làm tròn 2 số sau thập phân
        self.assertEqual(safe_float_vinhson_decimal("150.256"), 150.26)
        self.assertEqual(safe_float_vinhson_decimal("150.254"), 150.25)
        self.assertEqual(safe_float_vinhson_decimal("150,25"), 150.25)
        self.assertEqual(safe_float_vinhson_decimal("150,2"), 150.2)

        # Kiểm tra kiểu số sẵn có
        self.assertEqual(safe_float_vinhson_decimal(150.256), 150.26)
        self.assertEqual(safe_float_vinhson_decimal(150.2), 150.2)

        # Kiểm tra trường hợp None hoặc rỗng
        self.assertIsNone(safe_float_vinhson_decimal(None))
        self.assertIsNone(safe_float_vinhson_decimal(""))

    def test_original_safe_float_retains_behavior(self):
        # Kiểm tra hàm safe_float cũ vẫn hoạt động đúng như trước
        self.assertEqual(safe_float("150.000"), 150.0)
        self.assertEqual(safe_float("150,25"), 150.25)
        self.assertEqual(safe_float("1.234,56"), 1234.56)
