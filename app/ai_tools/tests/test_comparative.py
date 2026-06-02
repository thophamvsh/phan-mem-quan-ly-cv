from unittest.mock import patch, MagicMock
from django.test import TestCase
from ai_tools.songhinh_tools.services.comparative_service import ComparativeAnalysisService as ComparativeAnalysisServiceSH
from ai_tools.vinhson_tools.services.comparative_service import ComparativeAnalysisService as ComparativeAnalysisServiceVS

class ComparativeServicesTests(TestCase):
    databases = {"default"}

    def setUp(self):
        # Fake operational data for Sông Hinh (cols: date=1, reservoir=2, water_level=6, volume=7, inflow=8, turbine=9, spillway=10)
        self.songhinh_fake_data = [
            # Headers
            ["STT", "Ngày", "Hồ chứa", "MNH KH", "Qve KH", "MNH chết", "MNH", "Dung tích", "Qve", "Qcm", "Qxl"],
            ["", "", "", "", "", "", "", "", "", "", ""],
            # 2026 (Current year)
            ["1", "01/04/2026", "Song Hinh", "", "", "", "205.0", "", "50.0", "40.0", "0.0"],
            ["2", "02/04/2026", "Song Hinh", "", "", "", "205.2", "", "55.0", "42.0", "0.0"],
            # 2025 (Last year)
            ["3", "01/04/2025", "Song Hinh", "", "", "", "204.0", "", "40.0", "35.0", "0.0"],
            ["4", "02/04/2025", "Song Hinh", "", "", "", "204.2", "", "45.0", "38.0", "0.0"],
        ]

        # Fake operational data for Vĩnh Sơn (cols: date=1, reservoir=2, water_level=6, volume=7, inflow=8, turbine=9, spillway=10)
        self.vinhson_fake_data = [
            # Headers
            ["STT", "Ngày", "Hồ chứa", "MNH KH", "Qve KH", "MNH chết", "MNH", "Dung tích", "Qve", "Qcm", "Qxl"],
            ["", "", "", "", "", "", "", "", "", "", ""],
            # 2026 (Current year)
            ["1", "01/04/2026", "Vinh Son -A", "", "", "", "769.35", "", "10.0", "5.0", "0.0"],
            ["2", "02/04/2026", "Vinh Son -A", "", "", "", "769.40", "", "12.0", "6.0", "0.0"],
            ["3", "01/04/2026", "Vinh Son -B", "", "", "", "90.0", "", "15.0", "7.0", "0.0"],
            ["4", "01/04/2026", "Vinh Son -C", "", "", "", "80.0", "", "12.0", "4.0", "0.0"],
            # 2025 (Last year)
            ["5", "01/04/2025", "Vinh Son -A", "", "", "", "768.10", "", "8.0", "4.0", "0.0"],
            ["6", "02/04/2025", "Vinh Son -A", "", "", "", "768.15", "", "9.0", "4.5", "0.0"],
            ["7", "01/04/2025", "Vinh Son -B", "", "", "", "89.0", "", "13.0", "6.0", "0.0"],
            ["8", "01/04/2025", "Vinh Son -C", "", "", "", "79.0", "", "10.0", "3.0", "0.0"],
        ]

    @patch("ai_tools.songhinh_tools.core.sheets_client.GoogleSheetsClientManager")
    def test_songhinh_comparative_analysis(self, mock_manager_cls):
        mock_manager = MagicMock()
        mock_manager.get_read_worksheets.return_value = (MagicMock(), MagicMock())
        mock_manager.get_all_values_cached.return_value = self.songhinh_fake_data

        service = ComparativeAnalysisServiceSH(manager=mock_manager)
        report = service.get_comparative_analysis(
            start_date="01/04/2026",
            end_date="02/04/2026",
            parameters=["water_level", "inflow", "turbine", "spillway"]
        )

        self.assertIn("Sông Hinh", report)
        self.assertIn("Mực nước thượng lưu", report)
        self.assertIn("Lưu lượng về - Qve", report)
        self.assertIn("Lưu lượng chạy máy - Qcm", report)
        self.assertIn("Lưu lượng xả lũ - Qxl", report)
        self.assertIn("```chart", report)
        self.assertIn("NamNay", report)
        self.assertIn("NamNgoai", report)
        self.assertIn("```excel", report)
        self.assertIn("So sanh Song Hinh", report)
        self.assertIn("BÁO CÁO PHÂN TÍCH SO SÁNH - THỦY ĐIỆN SÔNG HINH", report)
        self.assertIn("Kết luận Phân tích So sánh", report)

    @patch("ai_tools.vinhson_tools.services.comparative_service.SheetsClient")
    def test_vinhson_comparative_analysis_single(self, mock_sheets_client_cls):
        mock_client = MagicMock()
        mock_worksheet = MagicMock()
        mock_worksheet.get_all_values.return_value = self.vinhson_fake_data
        
        mock_sheets_client = MagicMock()
        mock_sheets_client.get_client.return_value = (mock_client, mock_worksheet, MagicMock())
        mock_sheets_client_cls.return_value = mock_sheets_client

        service = ComparativeAnalysisServiceVS()
        # Test for Vinh Son -A
        report = service.get_comparative_analysis(
            start_date="01/04/2026",
            end_date="02/04/2026",
            reservoir="Vinh Son -A",
            parameters=["water_level", "inflow"]
        )

        self.assertIn("Vĩnh Sơn (Vinh Son -A)", report)
        self.assertIn("769.35 m", report)  # Checks that decimal float parsing is correct
        self.assertIn("768.10 m", report)
        self.assertIn("Lưu lượng về - Qve", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)
        self.assertIn("Ho A", report)
        self.assertIn("Kết luận Phân tích So sánh", report)

    @patch("ai_tools.vinhson_tools.services.comparative_service.SheetsClient")
    def test_vinhson_comparative_analysis_all(self, mock_sheets_client_cls):
        mock_client = MagicMock()
        mock_worksheet = MagicMock()
        mock_worksheet.get_all_values.return_value = self.vinhson_fake_data
        
        mock_sheets_client = MagicMock()
        mock_sheets_client.get_client.return_value = (mock_client, mock_worksheet, MagicMock())
        mock_sheets_client_cls.return_value = mock_sheets_client

        service = ComparativeAnalysisServiceVS()
        # Test for "All" reservoirs
        report = service.get_comparative_analysis(
            start_date="01/04/2026",
            end_date="02/04/2026",
            reservoir="All",
            parameters=["water_level", "inflow"]
        )

        self.assertIn("Vĩnh Sơn (cả 3 hồ A, B, C)", report)
        self.assertIn("Bảng 1: Vinh Son -A", report)
        self.assertIn("Bảng 2: Vinh Son -B", report)
        self.assertIn("Bảng 3: Vinh Son -C", report)
        
        # Verify no duplicate headers are printed (ensuring loop fix is correct)
        self.assertEqual(report.count("Bảng 1: Vinh Son -A"), 1)
        self.assertEqual(report.count("Bảng 2: Vinh Son -B"), 1)
        self.assertEqual(report.count("Bảng 3: Vinh Son -C"), 1)
        
        self.assertIn("```excel", report)
        self.assertIn("Ho A", report)
        self.assertIn("Ho B", report)
        self.assertIn("Ho C", report)
        self.assertIn("Kết luận Phân tích So sánh", report)

    @patch("ai_tools.vinhson_tools.services.comparative_service.SheetsClient")
    def test_vinhson_comparative_analysis_invalid_reservoir(self, mock_sheets_client_cls):
        service = ComparativeAnalysisServiceVS()
        report = service.get_comparative_analysis(
            start_date="01/04/2026",
            end_date="02/04/2026",
            reservoir="invalid_res"
        )
        self.assertIn("Hồ không hợp lệ", report)
