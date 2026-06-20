from unittest.mock import patch, MagicMock
from types import SimpleNamespace
from datetime import datetime, timezone
from django.test import TestCase

from thongsothuyvan.models import ThongsoSanxuat
from ai_tools.vinhson_tools.services.qve_analysis_service import QveAnalysisService as QveAnalysisServiceVS
from ai_tools.songhinh_tools.services.qve_analysis_service import QveAnalysisService as QveAnalysisServiceSH

def _fake_query_rainfall_data(*args, **kwargs):
    # Trả về dữ liệu mưa giả lập cho các trạm tương ứng
    return [
        {
            "Thoi_gian": "2026-04-01T00:00:00",
            "UBND_xa_Song_Hinh": 10.0,
            "Xa_Ea_M_doan": 5.0,
            "Thon_10_Xa_Ea_M_Doal": 0.0,
            "Cu_Kroa": 0.0,
            "Dap_Tran": 5.0,
            "Xa_Ea_Trang": 0.0,
            "Ho_A_TD_Vinh_Son": 20.0,
            "Ho_B_TD_Vinh_Son": 15.0,
            "Ho_C_TD_Vinh_Son": 10.0,
        },
        {
            "Thoi_gian": "2026-04-02T00:00:00",
            "UBND_xa_Song_Hinh": 12.0,
            "Xa_Ea_M_doan": 6.0,
            "Thon_10_Xa_Ea_M_Doal": 0.0,
            "Cu_Kroa": 0.0,
            "Dap_Tran": 6.0,
            "Xa_Ea_Trang": 0.0,
            "Ho_A_TD_Vinh_Son": 22.0,
            "Ho_B_TD_Vinh_Son": 16.0,
            "Ho_C_TD_Vinh_Son": 11.0,
        },
        {
            "Thoi_gian": "2025-04-01T00:00:00",
            "UBND_xa_Song_Hinh": 8.0,
            "Xa_Ea_M_doan": 4.0,
            "Thon_10_Xa_Ea_M_Doal": 0.0,
            "Cu_Kroa": 0.0,
            "Dap_Tran": 4.0,
            "Xa_Ea_Trang": 0.0,
            "Ho_A_TD_Vinh_Son": 18.0,
            "Ho_B_TD_Vinh_Son": 14.0,
            "Ho_C_TD_Vinh_Son": 9.0,
        },
        {
            "Thoi_gian": "2025-04-02T00:00:00",
            "UBND_xa_Song_Hinh": 9.0,
            "Xa_Ea_M_doan": 4.5,
            "Thon_10_Xa_Ea_M_Doal": 0.0,
            "Cu_Kroa": 0.0,
            "Dap_Tran": 4.5,
            "Xa_Ea_Trang": 0.0,
            "Ho_A_TD_Vinh_Son": 19.0,
            "Ho_B_TD_Vinh_Son": 15.0,
            "Ho_C_TD_Vinh_Son": 10.0,
        },
    ]

class QveAnalysisServicesTests(TestCase):
    databases = {"default"}

    def setUp(self):
        # 1) Tạo dữ liệu vận hành & thống kê cho Vĩnh Sơn
        # Năm 2026 (năm hiện tại)
        ThongsoSanxuat.objects.create(
            nha_may="vinhson",
            thoi_gian=datetime(2026, 4, 1, tzinfo=timezone.utc),
            cot_c="vinhson",
            cot_g=100.0,  # MNH A
            cot_i=37.0,   # Total Qve = 10.0 (Lake A) + 15.0 (Lake B) + 12.0 (Lake C)
            cot_j=5.0,    # Qcm A
            cot_k=0.0,    # Qxl A
            cot_m=50.0,   # Output day
            cot_n=48.0,   # Commercial day
            mucnuoc_thuongluu_ho_b=90.0,
            mucnuoc_thuongluu_ho_c=80.0,
            luuluong_ve_ho_b=15.0,
            luuluong_ve_ho_c=12.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="vinhson",
            thoi_gian=datetime(2026, 4, 2, tzinfo=timezone.utc),
            cot_c="vinhson",
            cot_g=100.5,
            cot_i=41.0,   # Total Qve = 12.0 (Lake A) + 16.0 (Lake B) + 13.0 (Lake C)
            cot_j=6.0,    # Qcm A
            cot_k=0.0,
            cot_m=55.0,
            cot_n=52.0,
            mucnuoc_thuongluu_ho_b=90.2,
            mucnuoc_thuongluu_ho_c=80.1,
            luuluong_ve_ho_b=16.0,
            luuluong_ve_ho_c=13.0,
        )

        # Năm 2025 (cùng kỳ năm trước)
        ThongsoSanxuat.objects.create(
            nha_may="vinhson",
            thoi_gian=datetime(2025, 4, 1, tzinfo=timezone.utc),
            cot_c="vinhson",
            cot_g=99.0,
            cot_i=31.0,   # Total Qve = 8.0 (Lake A) + 13.0 (Lake B) + 10.0 (Lake C)
            cot_j=4.0,
            cot_k=0.0,
            cot_m=40.0,
            cot_n=38.0,
            mucnuoc_thuongluu_ho_b=89.0,
            mucnuoc_thuongluu_ho_c=79.0,
            luuluong_ve_ho_b=13.0,
            luuluong_ve_ho_c=10.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="vinhson",
            thoi_gian=datetime(2025, 4, 2, tzinfo=timezone.utc),
            cot_c="vinhson",
            cot_g=99.2,
            cot_i=34.0,   # Total Qve = 9.0 (Lake A) + 14.0 (Lake B) + 11.0 (Lake C)
            cot_j=4.5,
            cot_k=0.0,
            cot_m=42.0,
            cot_n=40.0,
            mucnuoc_thuongluu_ho_b=89.1,
            mucnuoc_thuongluu_ho_c=79.2,
            luuluong_ve_ho_b=14.0,
            luuluong_ve_ho_c=11.0,
        )

        # 2) Tạo dữ liệu vận hành & thống kê cho Sông Hinh
        # Năm 2026 (năm hiện tại)
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=datetime(2026, 4, 1, tzinfo=timezone.utc),
            cot_g=205.0,  # MNH Sông Hinh (Thống kê: cột 1)
            cot_i=50.0,   # Qve Sông Hinh (Thống kê: cột 5)
            cot_j=40.0,   # Qcm Sông Hinh (COL_TURBINE)
            cot_k=0.0,    # Qxl Sông Hinh (COL_SPILLWAY)
            cot_m=100.0,  # Output day
            cot_n=95.0,   # Commercial day
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=datetime(2026, 4, 2, tzinfo=timezone.utc),
            cot_g=205.2,
            cot_i=55.0,
            cot_j=42.0,
            cot_k=0.0,
            cot_m=105.0,
            cot_n=100.0,
        )

        # Năm 2025 (cùng kỳ năm trước)
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=datetime(2025, 4, 1, tzinfo=timezone.utc),
            cot_g=204.0,
            cot_i=40.0,
            cot_j=35.0,
            cot_k=0.0,
            cot_m=80.0,
            cot_n=76.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=datetime(2025, 4, 2, tzinfo=timezone.utc),
            cot_g=204.2,
            cot_i=45.0,
            cot_j=38.0,
            cot_k=0.0,
            cot_m=85.0,
            cot_n=80.0,
        )

    @patch("thuyvan_data_client.query_rainfall_data", side_effect=_fake_query_rainfall_data)
    def test_vinhson_qve_analysis_all_reservoirs(self, _mock_rain):
        service = QveAnalysisServiceVS()
        report = service.get_qve_analysis(
            start_date="01/04/2026",
            end_date="02/04/2026",
            reservoir="All",
            parameters=["qve", "water_level", "rainfall", "commercial_output"],
        )

        # Kiểm tra nội dung báo cáo có chứa các chỉ số sinh dòng chảy và cân bằng nước vật lý
        self.assertIn("Vinh Son", report)
        self.assertIn("Rainfall-Runoff Relation", report)
        self.assertIn("H\u1ed3 A", report)
        self.assertIn("H\u1ed3 B", report)
        self.assertIn("H\u1ed3 C", report)
        self.assertIn("Physical Water Balance", report)

    @patch("thuyvan_data_client.query_rainfall_data", side_effect=_fake_query_rainfall_data)
    def test_vinhson_qve_analysis_single_reservoir(self, _mock_rain):
        service = QveAnalysisServiceVS()
        report = service.get_qve_analysis(
            start_date="01/04/2026",
            end_date="02/04/2026",
            reservoir="Vinh Son -A",
            parameters=["qve", "water_level", "rainfall", "commercial_output"],
        )

        # Đảm bảo Qcm được tính toán đúng (không bị coi là thiếu dữ liệu Qcm, tức không chứa thông báo thiếu Qcm)
        self.assertIn("Vinh Son -A", report)
        self.assertNotIn("Thi\u1ebfu d\u1eef li\u1ec7u l\u01b0u l\u01b0\u1ee3ng x\u1ea3", report)
        self.assertIn("Qcm", report)
        self.assertIn("5.50", report)  # average of 5.0 and 6.0 in 2026
        self.assertIn("4.25", report)  # average of 4.0 and 4.5 in 2025

    @patch("thuyvan_data_client.query_rainfall_data", side_effect=_fake_query_rainfall_data)
    def test_vinhson_qve_analysis_single_reservoir_ho_a(self, _mock_rain):
        service = QveAnalysisServiceVS()
        report = service.get_qve_analysis(
            start_date="01/04/2026",
            end_date="02/04/2026",
            reservoir="H\u1ed3 A",
            parameters=["qve", "water_level", "rainfall", "commercial_output"],
        )

        # Đảm bảo Qcm được tính toán đúng khi truy vấn theo tên "Hồ A"
        self.assertIn("Vinh Son -A", report)
        self.assertNotIn("Thi\u1ebfu d\u1eef li\u1ec7u l\u01b0u l\u01b0\u1ee3ng x\u1ea3", report)
        self.assertIn("Qcm", report)
        self.assertIn("5.50", report)
        self.assertIn("4.25", report)

    @patch("ai_tools.songhinh_tools.services.qve_analysis_service.GoogleSheetsClientManager")
    @patch("thuyvan_data_client.query_rainfall_data", side_effect=_fake_query_rainfall_data)
    def test_songhinh_qve_analysis(self, _mock_rain, mock_manager_cls):
        # Mock GoogleSheetsClientManager cho Sông Hinh
        def _get_all_values_cached(ws, cache_key=None):
            row_cur1 = [""] * 24
            row_cur1[1] = "01/04/2026"
            row_cur1[9] = "40.0"   # COL_TURBINE
            row_cur1[10] = "0.0"   # COL_SPILLWAY
            row_cur1[16] = "100.0" # COL_OUTPUT_MONTH
            row_cur1[17] = "95.0"  # COL_COMMERCIAL_MONTH
            row_cur1[20] = "100.0" # COL_OUTPUT_YEAR
            row_cur1[21] = "95.0"  # COL_COMMERCIAL_YEAR

            row_cur2 = [""] * 24
            row_cur2[1] = "02/04/2026"
            row_cur2[9] = "42.0"
            row_cur2[10] = "0.0"
            row_cur2[16] = "105.0"
            row_cur2[17] = "100.0"
            row_cur2[20] = "105.0"
            row_cur2[21] = "100.0"

            row_ly1 = [""] * 24
            row_ly1[1] = "01/04/2025"
            row_ly1[9] = "35.0"
            row_ly1[10] = "0.0"
            row_ly1[16] = "80.0"
            row_ly1[17] = "76.0"
            row_ly1[20] = "80.0"
            row_ly1[21] = "76.0"

            row_ly2 = [""] * 24
            row_ly2[1] = "02/04/2025"
            row_ly2[9] = "38.0"
            row_ly2[10] = "0.0"
            row_ly2[16] = "85.0"
            row_ly2[17] = "80.0"
            row_ly2[20] = "85.0"
            row_ly2[21] = "80.0"

            return [
                [],
                [],
                row_cur1,
                row_cur2,
                row_ly1,
                row_ly2,
            ]

        mock_manager = MagicMock()
        mock_manager.get_all_values_cached.side_effect = _get_all_values_cached
        mock_manager.get_read_worksheets.return_value = (MagicMock(), MagicMock())
        mock_manager_cls.return_value = mock_manager

        service = QveAnalysisServiceSH(manager=mock_manager)
        report = service.get_qve_analysis(
            start_date="01/04/2026",
            end_date="02/04/2026",
            parameters=["qve", "water_level", "rainfall", "commercial_output"],
        )

        # Kiểm tra nội dung báo cáo Sông Hinh
        self.assertIn("Song Hinh", report)
        self.assertIn("Rainfall-Runoff Relation", report)
        self.assertIn("Physical Water Balance", report)
        self.assertIn("Qcm", report)

    def test_vinhson_qve_a_calculation(self):
        from ai_tools.vinhson_tools.services.qve_analysis_service import load_vinhson_stats_rows_from_db
        from datetime import date
        rows = load_vinhson_stats_rows_from_db(date(2026, 4, 1), date(2026, 4, 2))
        
        # We expect:
        # Day 1: cot_i = 37.0, luuluong_ve_ho_b = 15.0, luuluong_ve_ho_c = 12.0
        # Qve A = 37.0 - 15.0 - 12.0 = 10.0
        # Day 2: cot_i = 41.0, luuluong_ve_ho_b = 16.0, luuluong_ve_ho_c = 13.0
        # Qve A = 41.0 - 16.0 - 13.0 = 12.0
        
        self.assertEqual(len(rows), 2)
        
        # Row 1 (2026-04-01)
        row1 = rows[0]
        self.assertEqual(row1[0], "01/04/2026")
        self.assertEqual(row1[4], 10.0) # qve_a
        self.assertEqual(row1[5], 15.0) # qve_b
        self.assertEqual(row1[6], 12.0) # qve_c
        
        # Row 2 (2026-04-02)
        row2 = rows[1]
        self.assertEqual(row2[0], "02/04/2026")
        self.assertEqual(row2[4], 12.0) # qve_a
        self.assertEqual(row2[5], 16.0) # qve_b
        self.assertEqual(row2[6], 13.0) # qve_c
