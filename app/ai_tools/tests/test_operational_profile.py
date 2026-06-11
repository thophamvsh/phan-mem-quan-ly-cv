from django.test import TestCase
from django.utils import timezone
import datetime
import pytz
import json
import re

from quanlyvanhanh.models import ThietBi, ThongSoToMay, ThongSoVanHanh, NguongThongSo
from ai_tools.analysis_tools.services import get_unit_state_profile


class OperationalProfileTests(TestCase):
    databases = {"default"}

    def setUp(self):
        # 1. Create a test device (set ma="SH.TB.H1" so save() sets ma_day_du correctly)
        self.device = ThietBi.objects.create(
            ten="TỔ MÁY H1",
            ma="SH.TB.H1",
            ma_day_du="SH.TB.H1",
            nha_may="Sông Hinh"
        )
        self.subdevice = ThietBi.objects.create(
            ten="Hệ thống làm mát chèn trục H1",
            ma="NLM",
            ma_day_du="SH.TB.H1.NLM",
            cha=self.device,
            nha_may="Sông Hinh"
        )

        # 2. Create target date and localized times
        self.target_date = datetime.date(2026, 6, 10)
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        
        # 07:00 local time
        self.dt_0700 = vn_tz.localize(datetime.datetime(2026, 6, 10, 7, 0))
        # 08:00 local time
        self.dt_0800 = vn_tz.localize(datetime.datetime(2026, 6, 10, 8, 0))

        # 3. Create parameter thresholds (NguongThongSo)
        NguongThongSo.objects.create(
            nha_may="Sông Hinh",
            thiet_bi=self.device,
            ma_thong_so="cong_suat_tac_dung_h1",
            ten_thong_so="Công suất tác dụng",
            don_vi="MW",
            rated=37.0
        )
        NguongThongSo.objects.create(
            nha_may="Sông Hinh",
            thiet_bi=self.subdevice,
            ma_thong_so="luu_luong_chen_truc",
            ten_thong_so="Lưu lượng chèn trục",
            don_vi="l/p",
            alarm=8.0,
            trip=4.4,
            rated=10.0
        )
        NguongThongSo.objects.create(
            nha_may="Sông Hinh",
            thiet_bi=self.device,
            ma_thong_so="nhiet_do_o_do",
            ten_thong_so="Nhiệt độ ổ đỡ",
            don_vi="°C",
            alarm=80.0,
            trip=85.0
        )

        # 4. Create operational values in database
        # At 07:00
        ThongSoVanHanh.objects.create(
            thiet_bi=self.device,
            ma_thong_so="cong_suat_tac_dung_h1",
            ten_thong_so="Công suất tác dụng",
            don_vi="MW",
            gia_tri="35.0",
            thoi_diem_nhap=self.dt_0700,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh"
        )
        ThongSoToMay.objects.create(
            thiet_bi=self.subdevice,
            ma_thong_so="luu_luong_chen_truc",
            ten_thong_so="Lưu lượng chèn trục",
            don_vi="l/p",
            gia_tri="10.0",
            thoi_diem_nhap=self.dt_0700,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh"
        )
        ThongSoToMay.objects.create(
            thiet_bi=self.device,
            ma_thong_so="nhiet_do_o_do",
            ten_thong_so="Nhiệt độ ổ đỡ",
            don_vi="°C",
            gia_tri="76.0",
            thoi_diem_nhap=self.dt_0700,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh"
        )

        # At 08:00
        ThongSoVanHanh.objects.create(
            thiet_bi=self.device,
            ma_thong_so="cong_suat_tac_dung_h1",
            ten_thong_so="Công suất tác dụng",
            don_vi="MW",
            gia_tri="35.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh"
        )
        ThongSoToMay.objects.create(
            thiet_bi=self.subdevice,
            ma_thong_so="luu_luong_chen_truc",
            ten_thong_so="Lưu lượng chèn trục",
            don_vi="l/p",
            gia_tri="5.0",  # Sụt giảm lưu lượng chèn trục
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh"
        )
        ThongSoToMay.objects.create(
            thiet_bi=self.device,
            ma_thong_so="nhiet_do_o_do",
            ten_thong_so="Nhiệt độ ổ đỡ",
            don_vi="°C",
            gia_tri="79.0",  # Tăng nhiệt độ
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh"
        )

    def test_get_unit_state_profile_full_day(self):
        report = get_unit_state_profile("SH.TB.H1", date="2026-06-10")
        self.assertIn("Hồ sơ trạng thái vận hành Tổ máy: TỔ MÁY H1", report)
        self.assertIn("**Ngày báo cáo**: 10/06/2026", report)
        self.assertIn("Lưu lượng chèn trục", report)
        self.assertIn("07:00", report)
        self.assertIn("08:00", report)
        self.assertIn("35.00", report)  # Aligned power
        self.assertIn("10.00", report)  # Aligned flow at 07:00
        self.assertIn("5.00", report)   # Aligned flow at 08:00
        self.assertIn("Bảng diễn biến thông số trong các ngày so sánh", report)
        self.assertIn("Khoảng so sánh", report)
        self.assertIn("```chart", report)
        self.assertNotIn("Hướng dẫn phân tích chẩn đoán cho AI Agent Nami", report)

    def test_get_unit_state_profile_includes_15_day_comparison_rows(self):
        previous_date = datetime.date(2026, 6, 9)
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        dt_previous = vn_tz.localize(datetime.datetime(2026, 6, 9, 8, 0))

        ThongSoVanHanh.objects.create(
            thiet_bi=self.device,
            ma_thong_so="cong_suat_tac_dung_h1",
            ten_thong_so="Công suất tác dụng",
            don_vi="MW",
            gia_tri="30.0",
            thoi_diem_nhap=dt_previous,
            ngay_nhap=previous_date,
            nha_may="Sông Hinh"
        )
        ThongSoToMay.objects.create(
            thiet_bi=self.subdevice,
            ma_thong_so="luu_luong_chen_truc",
            ten_thong_so="Lưu lượng chèn trục",
            don_vi="l/p",
            gia_tri="9.0",
            thoi_diem_nhap=dt_previous,
            ngay_nhap=previous_date,
            nha_may="Sông Hinh"
        )
        ThongSoToMay.objects.create(
            thiet_bi=self.device,
            ma_thong_so="nhiet_do_o_do",
            ten_thong_so="Nhiệt độ ổ đỡ",
            don_vi="°C",
            gia_tri="70.0",
            thoi_diem_nhap=dt_previous,
            ngay_nhap=previous_date,
            nha_may="Sông Hinh"
        )

        report = get_unit_state_profile("SH.TB.H1", date="2026-06-10", time="08:00")

        self.assertIn("| **09/06** | 08:00 | 30.00 | 70.00 | 9.00 |", report)
        self.assertIn("| **10/06** | 07:00 | 35.00 | 76.00 | 10.00 |", report)
        self.assertIn("| **10/06** | 08:00 | 35.00 | 79.00 | 5.00 |", report)
        self.assertIn('"Thời điểm": "09/06 08:00"', report)
        self.assertIn('"Thời điểm": "10/06 07:00"', report)
        self.assertIn('"Nhiệt độ ổ đỡ (°C)": 70.0', report)

    def test_get_unit_state_profile_specific_time(self):
        report = get_unit_state_profile("SH.TB.H1", date="2026-06-10", time="08:00", window="60m")
        self.assertIn("**Mốc thời gian chẩn đoán**: 08:00", report)
        self.assertIn("Lưu lượng chèn trục", report)
        self.assertIn("5.00 l/p", report)
        self.assertIn("Cảnh báo (Alarm)", report)  # 5.0 is <= 8.0 Alarm
        
        # Verify new diagnostic columns are present in Markdown
        self.assertIn("Kỳ vọng (Expected)", report)
        self.assertIn("Sai lệch (Residual)", report)
        self.assertIn("Xu hướng", report)
        self.assertIn("Tốc độ thay đổi", report)
        self.assertIn("Chất lượng", report)
        self.assertIn("Chế độ vận hành hiện tại", report)
        self.assertIn("high_load_stable", report)

        # Verify rate of change calculation: 79.0 - 76.0 = +3.0 over 60m => +0.050 °C/minute
        self.assertIn("+0.050", report)
        # Verify flow rate of change: 5.0 - 10.0 = -5.0 over 60m => -0.083 l/p/minute
        self.assertIn("-0.083", report)
        
        # Verify presence and validity of hidden JSON payload for Nami
        match = re.search(r"<!-- NAMI_THERMO_DATA_START\n(.*?)\nNAMI_THERMO_DATA_END -->", report, re.DOTALL)
        self.assertTrue(match is not None)
        
        json_data = json.loads(match.group(1))
        self.assertEqual(json_data["device_code"], "SH.TB.H1")
        self.assertEqual(json_data["operating_mode"], "high_load_stable")
        self.assertEqual(json_data["analysis_window"], "60m")
        
        signals = json_data["signals"]
        signals_by_metric = {sig["metric_code"]: sig for sig in signals.values()}
        self.assertIn("nhiet_do_o_do", signals_by_metric)
        self.assertIn("luu_luong_chen_truc", signals_by_metric)
        
        # Check specific computed properties in JSON
        bearing_sig = signals_by_metric["nhiet_do_o_do"]
        self.assertEqual(bearing_sig["device_code"], "SH.TB.H1")
        self.assertEqual(bearing_sig["val"], 79.0)
        self.assertEqual(bearing_sig["trend"], "increasing")
        self.assertEqual(bearing_sig["rate_of_change"], 0.05)
        self.assertIsNotNone(bearing_sig["expected"])
        self.assertIsNotNone(bearing_sig["residual"])
        self.assertEqual(bearing_sig["quality"], "good")
        self.assertEqual(bearing_sig["status"], "⚠️ TIỆM CẬN ALARM (NEAR ALARM)") # 79.0 is within tolerance of 80.0 Alarm
        
        flow_sig = signals_by_metric["luu_luong_chen_truc"]
        self.assertEqual(flow_sig["device_code"], "SH.TB.H1.NLM")
        self.assertEqual(flow_sig["val"], 5.0)
        self.assertEqual(flow_sig["trend"], "decreasing")
        self.assertEqual(flow_sig["rate_of_change"], -0.083)
        self.assertEqual(flow_sig["quality"], "good")
        self.assertIn("CẢNH BÁO", flow_sig["status"])

    def test_get_unit_state_profile_prefers_latest_diagnostic_time(self):
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        dt_0900 = vn_tz.localize(datetime.datetime(2026, 6, 10, 9, 0))
        ThongSoToMay.objects.create(
            thiet_bi=self.device,
            ma_thong_so="luu_luong_o_do_may_phat",
            ten_thong_so="Lưu lượng ổ đỡ máy phát",
            don_vi="l/p",
            gia_tri="55.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh"
        )
        ThongSoVanHanh.objects.create(
            thiet_bi=self.device,
            ma_thong_so="cong_suat_tac_dung_h1",
            ten_thong_so="Công suất tác dụng",
            don_vi="MW",
            gia_tri="35.0",
            thoi_diem_nhap=dt_0900,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh"
        )

        report = get_unit_state_profile("SH.TB.H1", date="2026-06-10", parameter_code="nhiet_do_o_do")

        self.assertIn("**Mốc thời gian chẩn đoán**: 08:00", report)
        self.assertIn("**79.00 °C**", report)
        self.assertIn("**55.00 l/p**", report)
        self.assertNotIn("Nhiệt độ ổ đỡ (TỔ MÁY H1) | N/A", report)
        self.assertNotIn("Lưu lượng ổ đỡ máy phát (TỔ MÁY H1) | N/A", report)

    def test_get_unit_state_profile_with_parameter_code_resolves_correct_date(self):
        # Create data for another date, but ONLY for cong_suat_tac_dung_h1 (no bearing data)
        later_date = datetime.date(2026, 6, 11)
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        dt_later = vn_tz.localize(datetime.datetime(2026, 6, 11, 8, 0))
        
        ThongSoVanHanh.objects.create(
            thiet_bi=self.device,
            ma_thong_so="cong_suat_tac_dung_h1",
            ten_thong_so="Công suất tác dụng",
            don_vi="MW",
            gia_tri="36.0",
            thoi_diem_nhap=dt_later,
            ngay_nhap=later_date,
            nha_may="Sông Hinh"
        )
        
        # When querying without parameter_code, it should resolve to 2026-06-11 (latest date with any data)
        report_any = get_unit_state_profile("SH.TB.H1")
        self.assertIn("11/06/2026", report_any)
        
        # When querying for 'nhiet_do_o_do', it should resolve to 2026-06-10 (latest date with bearing data)
        report_param = get_unit_state_profile("SH.TB.H1", parameter_code="nhiet_do_o_do")
        self.assertIn("10/06/2026", report_param)
        self.assertIn("Nhiệt độ ổ đỡ", report_param)

    def test_get_unit_state_profile_parameter_not_found(self):
        # Querying for a parameter that has no data on the resolved date
        report = get_unit_state_profile("SH.TB.H1", date="2026-06-10", parameter_code="khong_ton_tai")
        self.assertIn("Không tìm thấy dữ liệu vận hành cho thông số 'khong_ton_tai'", report)

    def test_get_related_flow_code_mapping(self):
        # Create flow and temp parameters in the db
        ThongSoToMay.objects.create(
            thiet_bi=self.device,
            ma_thong_so="luu_luong_o_do_may_phat",
            ten_thong_so="Lưu lượng ổ đỡ máy phát",
            don_vi="l/p",
            gia_tri="55.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh"
        )
        ThongSoToMay.objects.create(
            thiet_bi=self.device,
            ma_thong_so="luu_luong_o_huong_may_phat",
            ten_thong_so="Lưu lượng ổ hướng máy phát",
            don_vi="l/p",
            gia_tri="45.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh"
        )
        ThongSoToMay.objects.create(
            thiet_bi=self.device,
            ma_thong_so="nhiet_do_o_huong_may_phat",
            ten_thong_so="Nhiệt độ ổ hướng máy phát",
            don_vi="°C",
            gia_tri="60.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh"
        )
        
        # Query with parameter_code="nhiet_do_o_do"
        report_odo = get_unit_state_profile("SH.TB.H1", date="2026-06-10", time="08:00", parameter_code="nhiet_do_o_do")
        
        # Verify it has luu_luong_o_do_may_phat but NOT luu_luong_o_huong_may_phat
        self.assertIn("Lưu lượng ổ đỡ máy phát", report_odo)
        self.assertNotIn("Lưu lượng ổ hướng máy phát", report_odo)
        
        # Query with parameter_code="nhiet_do_o_huong_may_phat"
        report_ohuong = get_unit_state_profile("SH.TB.H1", date="2026-06-10", time="08:00", parameter_code="nhiet_do_o_huong_may_phat")
        
        # Verify it has luu_luong_o_huong_may_phat but NOT luu_luong_o_do_may_phat
        self.assertIn("Lưu lượng ổ hướng máy phát", report_ohuong)
        self.assertNotIn("Lưu lượng ổ đỡ máy phát", report_ohuong)

    def test_turbine_guide_bearing_alias_does_not_resolve_to_thrust_bearing(self):
        h2 = ThietBi.objects.create(
            ten="TỔ MÁY H2",
            ma="SH.TB.H2",
            ma_day_du="SH.TB.H2",
            nha_may="Sông Hinh"
        )
        h2_turbine_guide = ThietBi.objects.create(
            ten="Ổ hướng tuabin",
            ma="TuB.OH",
            ma_day_du="SH.TB.H2.TuB.OH",
            cha=h2,
            nha_may="Sông Hinh"
        )

        NguongThongSo.objects.create(
            nha_may="Sông Hinh",
            thiet_bi=h2,
            ma_thong_so="cong_suat_tac_dung_h2",
            ten_thong_so="Công suất tác dụng",
            don_vi="MW",
            rated=37.0
        )
        NguongThongSo.objects.create(
            nha_may="Sông Hinh",
            thiet_bi=h2_turbine_guide,
            ma_thong_so="nhiet_do_o_huong_tuabin",
            ten_thong_so="Nhiệt độ ổ hướng tuabin",
            don_vi="°C",
            alarm=75.0,
            trip=80.0
        )
        NguongThongSo.objects.create(
            nha_may="Sông Hinh",
            thiet_bi=h2_turbine_guide,
            ma_thong_so="luu_luong_o_huong_tuabin",
            ten_thong_so="Lưu lượng ổ hướng tuabin",
            don_vi="l/p",
            alarm=25.0,
            trip=20.0
        )

        ThongSoVanHanh.objects.create(
            thiet_bi=h2,
            ma_thong_so="cong_suat_tac_dung_h2",
            ten_thong_so="Công suất tác dụng",
            don_vi="MW",
            gia_tri="32.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh"
        )
        ThongSoToMay.objects.create(
            thiet_bi=h2_turbine_guide,
            ma_thong_so="luu_luong_o_huong_tuabin",
            ten_thong_so="Lưu lượng ổ hướng tuabin",
            don_vi="l/p",
            gia_tri="51.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh"
        )
        ThongSoToMay.objects.create(
            thiet_bi=h2_turbine_guide,
            ma_thong_so="nhiet_do_o_huong_tuabin",
            ten_thong_so="Nhiệt độ ổ hướng tuabin",
            don_vi="°C",
            gia_tri="62.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh"
        )

        report = get_unit_state_profile(
            "SH.TB.H2",
            date="2026-06-10",
            time="08:00",
            parameter_code="nhiệt độ ổ hướng tuabine",
        )

        self.assertIn("SH.TB.H2", report)
        self.assertIn("Nhiệt độ ổ hướng tuabin", report)
        self.assertIn("Lưu lượng ổ hướng tuabin", report)
        self.assertIn("nhiet_do_o_huong_tuabin", report)
        self.assertNotIn("nhiet_do_o_do", report)
