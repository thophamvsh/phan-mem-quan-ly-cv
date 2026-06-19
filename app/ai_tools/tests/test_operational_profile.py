from django.test import TestCase
from django.utils import timezone
import datetime
import pytz
import json
import re
from types import SimpleNamespace

from quanlyvanhanh.models import ThietBi, ThongSoToMay, ThongSoTram110KV, ThongSoVanHanh, NguongThongSo
from ai_tools.analysis_tools.services import get_unit_state_profile
from ai_tools.services import _normalize_analysis_tool_call, _strip_large_markdown_blocks
from ai_tools.tool_format import make_tool_response, render_markdown


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

    def test_transformer_question_overrides_wrong_h1_tool_arguments(self):
        tool_call = SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(
                name="get_unit_state_profile",
                arguments=json.dumps(
                    {
                        "device_code": "SH.TB.H1",
                        "parameter_code": "nhiet_do_o_huong_tuabin",
                    }
                ),
            ),
        )

        fixed_call = _normalize_analysis_tool_call("Phân tích nhiệt độ Máy biến áp T1 của Sông Hinh", tool_call)
        fixed_args = json.loads(fixed_call.function.arguments)

        self.assertEqual(fixed_args["device_code"], "SH.TB.TPP.110.T1")
        self.assertEqual(fixed_args["parameter_code"], "nhiet_do_mba_t1")

    def test_get_unit_state_profile_supports_song_hinh_transformer_t1(self):
        transformer = ThietBi.objects.create(
            ten="MBA T1",
            ma="SH.TB.TPP.110.T1",
            ma_day_du="SH.TB.TPP.110.T1",
            nha_may="Sông Hinh",
        )

        NguongThongSo.objects.create(
            nha_may="Sông Hinh",
            thiet_bi=transformer,
            ma_thong_so="nhiet_do_mba_t1",
            ten_thong_so="Nhiệt độ MBA T1",
            don_vi="°C",
            alarm=80.0,
            trip=90.0,
        )
        ThongSoVanHanh.objects.create(
            thiet_bi=transformer,
            ma_thong_so="nhiet_do_mba_t1",
            ten_thong_so="Nhiệt độ MBA T1",
            don_vi="°C",
            gia_tri="62.5",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh",
        )

        report = get_unit_state_profile(
            "SH.TB.TPP.110.T1",
            date="2026-06-10",
            time="08:00",
            parameter_code="nhiet_do_mba_t1",
        )

        self.assertIn("Hồ sơ trạng thái vận hành Thiết bị: MBA T1 (SH.TB.TPP.110.T1)", report)
        self.assertIn("Nhiệt độ MBA T1", report)
        self.assertIn("nhiet_do_mba_t1", report)
        self.assertIn("**62.50 °C**", report)
        self.assertIn("SH.TB.H1", report)
        self.assertNotIn("nhiet_do_o_huong_tuabin", report)

    def test_get_unit_state_profile_reads_song_hinh_transformer_t2_tram_data(self):
        transformer = ThietBi.objects.create(
            ten="MBA T2",
            ma="SH.TB.TPP.110.T2",
            ma_day_du="SH.TB.TPP.110.T2",
            nha_may="Sông Hinh",
        )

        NguongThongSo.objects.create(
            nha_may="Sông Hinh",
            thiet_bi=transformer,
            ma_thong_so="nhiet_do_mba_t2",
            ten_thong_so="Nhiệt độ MBA T2",
            don_vi="°C",
            alarm=80.0,
            trip=90.0,
        )
        ThongSoTram110KV.objects.create(
            thiet_bi=transformer,
            ma_thong_so="nhiet_do_mba_t2",
            ten_thong_so="Nhiệt độ MBA T2",
            don_vi="°C",
            gia_tri="60",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh",
        )
        ThongSoTram110KV.objects.create(
            thiet_bi=transformer,
            ma_thong_so="nac_phan_ap_mba_t2",
            ten_thong_so="Nấc phân áp MBA T2",
            don_vi="",
            gia_tri="9",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh",
        )

        report = get_unit_state_profile(
            "SH.TB.TPP.110.T2",
            date="2026-06-10",
            time="08:00",
            parameter_code="nhiet_do_mba_t2",
        )

        self.assertIn("Hồ sơ trạng thái vận hành Thiết bị: MBA T2 (SH.TB.TPP.110.T2)", report)
        self.assertIn("Nhiệt độ MBA T2", report)
        self.assertIn("nhiet_do_mba_t2", report)
        self.assertIn("**60.00 °C**", report)
        self.assertIn('"source": "tram"', report)
        self.assertNotIn("Không tìm thấy dữ liệu vận hành", report)

    def test_get_unit_state_profile_reads_vinh_son_transformer_t2_when_names_change(self):
        transformer = ThietBi.objects.create(
            ten="Máy biến áp T2",
            ma="VS.TB.TPP.T2",
            ma_day_du="VS.TB.TPP.T2",
            nha_may="Vĩnh Sơn",
        )
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        older_date = datetime.date(2026, 6, 8)
        newer_date = datetime.date(2026, 6, 9)
        older_dt = vn_tz.localize(datetime.datetime(2026, 6, 8, 8, 0))
        newer_dt = vn_tz.localize(datetime.datetime(2026, 6, 9, 8, 0))

        NguongThongSo.objects.create(
            nha_may="Vĩnh Sơn",
            thiet_bi=transformer,
            ma_thong_so="nhiet_do_cuon_day_t2",
            ten_thong_so="Nhiệt độ cuộn dây T2",
            don_vi="°C",
            alarm=80.0,
            trip=90.0,
        )
        ThongSoVanHanh.objects.create(
            thiet_bi=transformer,
            ma_thong_so="nhiet_do_cuon_day_t2",
            ten_thong_so="Nđ\nổ T2",
            don_vi="°C",
            gia_tri="62",
            thoi_diem_nhap=older_dt,
            ngay_nhap=older_date,
            nha_may="Vĩnh Sơn",
        )
        ThongSoVanHanh.objects.create(
            thiet_bi=transformer,
            ma_thong_so="nhiet_do_cuon_day_t2",
            ten_thong_so="Nđ\nø T2",
            don_vi="°C",
            gia_tri="68",
            thoi_diem_nhap=newer_dt,
            ngay_nhap=newer_date,
            nha_may="Vĩnh Sơn",
        )

        report = get_unit_state_profile("VS.TB.TPP.T2", parameter_code="nhiet_do_cuon_day_t2")

        self.assertIn("09/06/2026", report)
        self.assertIn("nhiet_do_cuon_day_t2", report)
        self.assertIn("**68.00 °C**", report)
        self.assertIn('"source": "dien"', report)
        self.assertNotIn("Không tìm thấy dữ liệu vận hành", report)

    def test_rendered_operational_profile_does_not_leak_hidden_json_payload(self):
        transformer = ThietBi.objects.create(
            ten="MBA T2",
            ma="SH.TB.TPP.110.T2",
            ma_day_du="SH.TB.TPP.110.T2",
            nha_may="Sông Hinh",
        )
        ThongSoTram110KV.objects.create(
            thiet_bi=transformer,
            ma_thong_so="nhiet_do_mba_t2",
            ten_thong_so="Nhiệt độ MBA T2",
            don_vi="°C",
            gia_tri="60",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh",
        )

        raw_report = get_unit_state_profile(
            "SH.TB.TPP.110.T2",
            date="2026-06-10",
            time="08:00",
            parameter_code="nhiet_do_mba_t2",
        )
        rendered = render_markdown(make_tool_response("get_unit_state_profile", raw_report, None))

        self.assertIn("Bảng diễn biến thông số trong các ngày so sánh", rendered)
        self.assertIn("Nhiệt độ MBA T2", rendered)
        self.assertNotIn("NAMI_THERMO_DATA_START", rendered)
        self.assertNotIn("NAMI_THERMO_DATA_END", rendered)
        self.assertNotIn('"SH.TB.TPP.110.T2|nhiet_do_mba_t2"', rendered)
        self.assertNotIn('"signals"', rendered)

    def test_history_compaction_removes_long_operational_trend_table(self):
        transformer = ThietBi.objects.create(
            ten="MBA T2",
            ma="SH.TB.TPP.110.T2",
            ma_day_du="SH.TB.TPP.110.T2",
            nha_may="Sông Hinh",
        )
        ThongSoTram110KV.objects.create(
            thiet_bi=transformer,
            ma_thong_so="nhiet_do_mba_t2",
            ten_thong_so="Nhiệt độ MBA T2",
            don_vi="°C",
            gia_tri="60",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Sông Hinh",
        )

        raw_report = get_unit_state_profile(
            "SH.TB.TPP.110.T2",
            date="2026-06-10",
            time="08:00",
            parameter_code="nhiet_do_mba_t2",
        )
        compacted = _strip_large_markdown_blocks(raw_report)

        self.assertIn("Hồ sơ trạng thái vận hành Thiết bị: MBA T2", compacted)
        self.assertIn("Nhiệt độ MBA T2", compacted)
        self.assertIn("Dữ liệu vận hành & Chẩn đoán chuyên sâu", compacted)
        self.assertIn("Đã lược bỏ bảng diễn biến 15 ngày", compacted)
        self.assertNotIn("Bảng diễn biến thông số trong các ngày so sánh", compacted)
        self.assertNotIn("```chart", compacted)
        self.assertNotIn("NAMI_THERMO_DATA_START", compacted)
        self.assertNotIn('"signals"', compacted)

    def test_offline_expected_temperature(self):
        ThongSoVanHanh.objects.filter(
            thiet_bi=self.device,
            ma_thong_so="cong_suat_tac_dung_h1",
            thoi_diem_nhap=self.dt_0800,
        ).update(gia_tri="0.0")
        ThongSoToMay.objects.filter(
            thiet_bi=self.device,
            ma_thong_so="nhiet_do_o_do",
            thoi_diem_nhap=self.dt_0800,
        ).update(gia_tri="28.0")
        
        report = get_unit_state_profile("SH.TB.H1", date="2026-06-10", time="08:00", parameter_code="nhiet_do_o_do")
        self.assertIn("25.00 °C", report)
        self.assertIn("+3.00 °C", report)

    def test_rated_power_map_lookup_and_online_calculation(self):
        tkt_device = ThietBi.objects.create(
            ten="TỔ MÁY H1 TKT",
            ma="TKT.TB.H1",
            ma_day_du="TKT.TB.H1",
            nha_may="Thượng Kon Tum"
        )
        NguongThongSo.objects.create(
            nha_may="Thượng Kon Tum",
            thiet_bi=tkt_device,
            ma_thong_so="cong_suat_tac_dung_h1",
            ten_thong_so="Công suất tác dụng",
            don_vi="MW",
            rated=110.0
        )
        NguongThongSo.objects.create(
            nha_may="Thượng Kon Tum",
            thiet_bi=tkt_device,
            ma_thong_so="nhiet_do_o_do",
            ten_thong_so="Nhiệt độ ổ đỡ",
            don_vi="°C",
            alarm=80.0,
            trip=85.0,
            rated=65.0
        )
        
        ThongSoVanHanh.objects.create(
            thiet_bi=tkt_device,
            ma_thong_so="cong_suat_tac_dung_h1",
            ten_thong_so="Công suất tác dụng",
            don_vi="MW",
            gia_tri="55.0",
            thoi_diem_nhap=self.dt_0700,
            ngay_nhap=self.target_date,
            nha_may="Thượng Kon Tum"
        )
        ThongSoToMay.objects.create(
            thiet_bi=tkt_device,
            ma_thong_so="nhiet_do_o_do",
            ten_thong_so="Nhiệt độ ổ đỡ",
            don_vi="°C",
            gia_tri="50.0",
            thoi_diem_nhap=self.dt_0700,
            ngay_nhap=self.target_date,
            nha_may="Thượng Kon Tum"
        )
        
        report = get_unit_state_profile("TKT.TB.H1", date="2026-06-10", time="07:00", parameter_code="nhiet_do_o_do")
        self.assertIn("47.00 °C", report)
        self.assertIn("+3.00 °C", report)

    def test_compare_hydro_periods_missing_data(self):
        from ai_tools.analysis_tools.services import compare_hydro_periods
        from thongsothuyvan.models import TramDoMuaVrain
        
        dt_current = self.dt_0700
        TramDoMuaVrain.objects.create(
            Thoi_gian=dt_current,
            Xa_Ea_M_doan=10.0,
            Thon_10_Xa_Ea_M_Doal=5.0,
            UBND_xa_Song_Hinh=3.0,
            Cu_Kroa=2.0,
            Xa_Ea_Trang=1.0,
            Dap_Tran=4.0
        )

        report = compare_hydro_periods(
            data_type="rainfall",
            current_start="2026-06-10",
            current_end="2026-06-10",
            compare_start="2026-06-09",
            compare_end="2026-06-09",
            reservoir="Song Hinh"
        )

        # TB Kỳ hiện tại (10.00 mm) có mặt, TB Kỳ so sánh và Chênh lệch/Thay đổi là "-"
        self.assertIn("10.00 mm", report)
        self.assertIn("-", report)

    def test_vinhson_stator_parameter_resolution(self):
        # 1. Create Vinh Son H2 and Stator devices
        vs_h2 = ThietBi.objects.create(
            ten="TỔ MÁY H2 VĨNH SƠN",
            ma="VS.TB.H2",
            ma_day_du="VS.TB.H2",
            nha_may="Vĩnh Sơn"
        )
        vs_stator = ThietBi.objects.create(
            ten="Stator máy phát H2",
            ma="GE.STA",
            ma_day_du="VS.TB.H2.GE.STA",
            cha=vs_h2,
            nha_may="Vĩnh Sơn"
        )

        # 2. Thresholds
        NguongThongSo.objects.create(
            nha_may="Vĩnh Sơn",
            thiet_bi=vs_h2,
            ma_thong_so="cong_suat_tac_dung_h2",
            ten_thong_so="Công suất tác dụng",
            don_vi="MW",
            rated=33.0
        )
        NguongThongSo.objects.create(
            nha_may="Vĩnh Sơn",
            thiet_bi=vs_stator,
            ma_thong_so="nhiet_do_cuon_day_stato_1",
            ten_thong_so="Cuộn dây 1",
            don_vi="°C",
            alarm=85.0,
            trip=90.0
        )
        NguongThongSo.objects.create(
            nha_may="Vĩnh Sơn",
            thiet_bi=vs_stator,
            ma_thong_so="nhiet_do_cuon_day_stato_2",
            ten_thong_so="Cuộn dây 2",
            don_vi="°C",
            alarm=85.0,
            trip=90.0
        )
        NguongThongSo.objects.create(
            nha_may="Vĩnh Sơn",
            thiet_bi=vs_stator,
            ma_thong_so="nhiet_do_loi_sat_stato_1",
            ten_thong_so="Lõi sắt 1",
            don_vi="°C",
            alarm=85.0,
            trip=90.0
        )

        # 3. Operational data at 08:00
        ThongSoVanHanh.objects.create(
            thiet_bi=vs_h2,
            ma_thong_so="cong_suat_tac_dung_h2",
            ten_thong_so="Công suất tác dụng",
            don_vi="MW",
            gia_tri="30.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Vĩnh Sơn"
        )
        ThongSoToMay.objects.create(
            thiet_bi=vs_stator,
            ma_thong_so="nhiet_do_cuon_day_stato_1",
            ten_thong_so="Cuộn dây 1",
            don_vi="°C",
            gia_tri="75.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Vĩnh Sơn"
        )
        ThongSoToMay.objects.create(
            thiet_bi=vs_stator,
            ma_thong_so="nhiet_do_cuon_day_stato_2",
            ten_thong_so="Cuộn dây 2",
            don_vi="°C",
            gia_tri="88.0",  # Trạng thái ALARM
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Vĩnh Sơn"
        )
        ThongSoToMay.objects.create(
            thiet_bi=vs_stator,
            ma_thong_so="nhiet_do_loi_sat_stato_1",
            ten_thong_so="Lõi sắt 1",
            don_vi="°C",
            gia_tri="80.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Vĩnh Sơn"
        )

        # 4. Resolve "nhiệt độ cuộn dây số 1"
        report1 = get_unit_state_profile("VS.TB.H2", date="2026-06-10", time="08:00", parameter_code="nhiệt độ cuộn dây số 1")
        self.assertIn("Cuộn dây 1", report1)
        self.assertIn("75.00 °C", report1)
        self.assertNotIn("Cuộn dây 2", report1)

        # 5. Resolve "nhiệt độ cuộn dây số 2"
        report2 = get_unit_state_profile("VS.TB.H2", date="2026-06-10", time="08:00", parameter_code="nhiệt độ cuộn dây số 2")
        self.assertIn("Cuộn dây 2", report2)
        self.assertIn("88.00 °C", report2)
        self.assertIn("🚨 CẢNH BÁO", report2)
        self.assertNotIn("Cuộn dây 1", report2)

        # 6. Resolve "nhiệt độ lõi sắt 1"
        report3 = get_unit_state_profile("VS.TB.H2", date="2026-06-10", time="08:00", parameter_code="nhiệt độ lõi sắt 1")
        self.assertIn("Lõi sắt 1", report3)
        self.assertIn("80.00 °C", report3)
        self.assertNotIn("Cuộn dây 1", report3)

    def test_vinhson_td_transformer_parameter_resolution(self):
        # 1. Create Vinh Son TD1 device
        vs_td1 = ThietBi.objects.create(
            ten="Máy biến áp tự dùng TD1",
            ma="VS.TB.TD.LV.TD1",
            ma_day_du="VS.TB.TD.LV.TD1",
            nha_may="Vĩnh Sơn"
        )

        # 2. Thresholds
        NguongThongSo.objects.create(
            nha_may="Vĩnh Sơn",
            thiet_bi=vs_td1,
            ma_thong_so="dien_ap_td91",
            ten_thong_so="U",
            don_vi="V",
            rated=380.0,
            alarm=360.0,
            trip=350.0
        )
        NguongThongSo.objects.create(
            nha_may="Vĩnh Sơn",
            thiet_bi=vs_td1,
            ma_thong_so="cong_suat_td91",
            ten_thong_so="P",
            don_vi="kW",
            rated=50.0
        )

        # 3. Operational data at 08:00
        ThongSoVanHanh.objects.create(
            thiet_bi=vs_td1,
            ma_thong_so="dien_ap_td91",
            ten_thong_so="U",
            don_vi="V",
            gia_tri="376.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Vĩnh Sơn"
        )
        ThongSoVanHanh.objects.create(
            thiet_bi=vs_td1,
            ma_thong_so="cong_suat_td91",
            ten_thong_so="P",
            don_vi="kW",
            gia_tri="35.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Vĩnh Sơn"
        )

        # 4. Query for voltage
        report = get_unit_state_profile("VS.TB.TD.LV.TD1", date="2026-06-10", time="08:00", parameter_code="dien_ap_td91")
        self.assertIn("Máy biến áp tự dùng TD1", report)
        self.assertIn("376.00 V", report)
        self.assertIn("dien_ap_td91", report)
        
        # Test resolution with general queries
        report2 = get_unit_state_profile("VS.TB.TD.LV.TD1", date="2026-06-10", time="08:00", parameter_code="điện áp")
        self.assertIn("376.00 V", report2)

    def test_parameter_with_newlines_resolution(self):
        # 1. Create a device with newlines in its name
        vs_t1 = ThietBi.objects.create(
            ten="Máy biến áp\nT1",
            ma="VS.TB.TPP.T1",
            ma_day_du="VS.TB.TPP.T1",
            nha_may="Vĩnh Sơn"
        )

        # 2. Threshold with newlines in name
        NguongThongSo.objects.create(
            nha_may="Vĩnh Sơn",
            thiet_bi=vs_t1,
            ma_thong_so="nhiet_do_cuon_day_t1",
            ten_thong_so="Nđ\nổ T1",
            don_vi="°C",
            rated=65.0
        )

        # 3. Operational data with newlines in name
        ThongSoVanHanh.objects.create(
            thiet_bi=vs_t1,
            ma_thong_so="nhiet_do_cuon_day_t1",
            ten_thong_so="Nđ\nổ T1",
            don_vi="°C",
            gia_tri="62.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Vĩnh Sơn"
        )

        # 4. Call get_unit_state_profile
        report = get_unit_state_profile("VS.TB.TPP.T1", date="2026-06-10", time="08:00", parameter_code="nhiet_do_cuon_day_t1")
        
        # Verify the report contains the cleaned name without newline
        self.assertIn("Nđ ổ T1", report)
        self.assertIn("Máy biến áp T1", report)
        # Verify that the raw uncleaned names with newlines are NOT in the report
        self.assertNotIn("Nđ\nổ T1", report)
        self.assertNotIn("Máy biến áp\nT1", report)
        self.assertIn("62.00 °C", report)

    def test_mba_analysis_includes_generator_power(self):
        # 1. Create MBA T1 device and H1 device
        vs_t1 = ThietBi.objects.create(
            ten="Máy biến áp T1",
            ma="VS.TB.TPP.T1",
            ma_day_du="VS.TB.TPP.T1",
            nha_may="Vĩnh Sơn"
        )
        vs_h1 = ThietBi.objects.create(
            ten="TỔ MÁY H1",
            ma="VS.TB.H1",
            ma_day_du="VS.TB.H1",
            nha_may="Vĩnh Sơn"
        )

        # 2. Thresholds
        NguongThongSo.objects.create(
            nha_may="Vĩnh Sơn",
            thiet_bi=vs_t1,
            ma_thong_so="nhiet_do_cuon_day_t1",
            ten_thong_so="Nhiệt độ cuộn dây T1",
            don_vi="°C",
            rated=65.0
        )
        NguongThongSo.objects.create(
            nha_may="Vĩnh Sơn",
            thiet_bi=vs_h1,
            ma_thong_so="cong_suat_tac_dung_h1",
            ten_thong_so="Công suất tác dụng",
            don_vi="MW",
            rated=33.0
        )
        # Add another parameter on H1 to verify it is filtered out
        NguongThongSo.objects.create(
            nha_may="Vĩnh Sơn",
            thiet_bi=vs_h1,
            ma_thong_so="nhiet_do_o_do",
            ten_thong_so="Nhiệt độ ổ đỡ",
            don_vi="°C",
            alarm=80.0
        )

        # 3. Operational data at 08:00
        ThongSoVanHanh.objects.create(
            thiet_bi=vs_t1,
            ma_thong_so="nhiet_do_cuon_day_t1",
            ten_thong_so="Nhiệt độ cuộn dây T1",
            don_vi="°C",
            gia_tri="62.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Vĩnh Sơn"
        )
        ThongSoVanHanh.objects.create(
            thiet_bi=vs_h1,
            ma_thong_so="cong_suat_tac_dung_h1",
            ten_thong_so="Công suất tác dụng",
            don_vi="MW",
            gia_tri="30.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Vĩnh Sơn"
        )
        ThongSoToMay.objects.create(
            thiet_bi=vs_h1,
            ma_thong_so="nhiet_do_o_do",
            ten_thong_so="Nhiệt độ ổ đỡ",
            don_vi="°C",
            gia_tri="70.0",
            thoi_diem_nhap=self.dt_0800,
            ngay_nhap=self.target_date,
            nha_may="Vĩnh Sơn"
        )

        # 4. Call get_unit_state_profile for MBA T1
        report = get_unit_state_profile("VS.TB.TPP.T1", date="2026-06-10", time="08:00", parameter_code="nhiet_do_cuon_day_t1")
        
        # Verify generator power is fetched and displayed
        self.assertIn("Công suất tác dụng", report)
        self.assertIn("30.00 MW", report)
        # Verify the expectation formula for T1 temperature uses the H1 load!
        # Expected temp for winding: t_inlet (25) + (t_rated (65) - t_inlet) * (0.4 + 0.6 * (P/P_rated)^2)
        # P/P_rated = 30 / 33 = 0.909
        # Expected = 25 + 40 * (0.4 + 0.6 * 0.826) = 25 + 40 * 0.895 = 60.826 => rounds to 60.83 °C
        self.assertIn("60.83 °C", report)  # expected value
        self.assertIn("+1.17 °C", report)  # residual value (62.00 - 60.83)
        
        # Verify other H1 parameters (like bearing temp) are filtered out and NOT in the report
        self.assertNotIn("Nhiệt độ ổ đỡ", report)
