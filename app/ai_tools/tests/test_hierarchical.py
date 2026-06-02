from unittest.mock import patch, MagicMock
from django.test import TestCase

from ai_tools.songhinh_tools.services.hierarchical_service import HierarchicalStatisticsService as HierarchicalServiceSH
from ai_tools.vinhson_tools.services.hierarchical_service import HierarchicalStatisticsService as HierarchicalServiceVS

class HierarchicalServicesTests(TestCase):
    databases = {"default"}

    def setUp(self):
        # Fake operational data for Sông Hinh (cols: date=0, water=1, qve=5)
        self.songhinh_fake_data = [
            # Headers (must be at least 8 rows total, data starting at index 7)
            ["Ngày", "Htl (m)", "", "", "", "Qv (m3/s)"],
            ["", "", "", "", "", ""],
            ["", "", "", "", "", ""],
            ["", "", "", "", "", ""],
            ["", "", "", "", "", ""],
            ["", "", "", "", "", ""],
            ["", "", "", "", "", ""],
            # 2026 data
            ["01/05/2026", "204.50", "", "", "", "43.50"],
            ["02/05/2026", "204.60", "", "", "", "44.00"],
            # 2025 data
            ["01/05/2025", "203.50", "", "", "", "35.50"],
            ["02/05/2025", "203.60", "", "", "", "36.00"],
        ]

        # Fake operational data for Vĩnh Sơn:
        # col_date = 0, water levels (A=1, B=2, C=3), Qve (A=4, B=5, C=6)
        self.vinhson_fake_data = [
            # Headers
            ["Ngày", "Hồ A - Htl", "Hồ B - Htl", "Hồ C - Htl", "Hồ A - Qve", "Hồ B - Qve", "Hồ C - Qve"],
            ["", "", "", "", "", "", ""],
            ["", "", "", "", "", "", ""],
            ["", "", "", "", "", "", ""],
            ["", "", "", "", "", "", ""],
            ["", "", "", "", "", "", ""],
            ["", "", "", "", "", "", ""],
            # 2026 data
            ["01/05/2026", "769.35", "90.00", "80.00", "10.00", "15.00", "12.00"],
            ["02/05/2026", "769.40", "90.10", "80.10", "12.00", "16.00", "13.00"],
            # 2025 data
            ["01/05/2025", "768.10", "89.00", "79.00", "8.00", "13.00", "10.00"],
            ["02/05/2025", "768.15", "89.10", "79.10", "9.00", "14.00", "11.00"],
        ]

    @patch("ai_tools.songhinh_tools.services.hierarchical_service.get_sheets_client_manager")
    def test_songhinh_hierarchical_year_compare(self, mock_manager_cls):
        mock_manager = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_worksheet.get_all_values.return_value = self.songhinh_fake_data
        mock_spreadsheet.worksheets.return_value = [mock_worksheet]
        mock_manager.get_write_spreadsheet.return_value = mock_spreadsheet
        mock_manager.get_all_values_cached.return_value = self.songhinh_fake_data
        mock_manager_cls.return_value = mock_manager

        service = HierarchicalServiceSH()
        report = service.get_hierarchical_statistics(
            period_type="year",
            period_value="2026",
            parameters=["qve", "water_level"],
            compare=True,
            compare_years=1
        )

        self.assertIn("Sông Hinh", report)
        self.assertIn("Lưu lượng về Qve (m³/s)", report)
        self.assertIn("Mực nước hồ (m)", report)
        self.assertIn("Kết luận Phân tích So sánh", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)
        self.assertIn("bao-cao-thong-ke-nam-song-hinh-2026.xlsx", report)

    @patch("ai_tools.songhinh_tools.services.hierarchical_service.get_sheets_client_manager")
    def test_songhinh_hierarchical_month_no_compare(self, mock_manager_cls):
        mock_manager = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_spreadsheet.worksheets.return_value = [mock_worksheet]
        mock_manager.get_write_spreadsheet.return_value = mock_spreadsheet
        mock_manager.get_all_values_cached.return_value = self.songhinh_fake_data
        mock_manager_cls.return_value = mock_manager

        service = HierarchicalServiceSH()
        report = service.get_hierarchical_statistics(
            period_type="month",
            period_value="05/2026",
            parameters=["qve"],
            compare=False
        )

        self.assertIn("tháng 5/2026", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)
        self.assertIn("bao-cao-thong-ke-thang-song-hinh-05-2026.xlsx", report)

    @patch("ai_tools.vinhson_tools.services.hierarchical_service.get_stats_export_client")
    def test_vinhson_hierarchical_year_all_compare(self, mock_get_client):
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_worksheet.get_all_values.return_value = self.vinhson_fake_data
        mock_spreadsheet.worksheets.return_value = [mock_worksheet]
        mock_get_client.return_value = (MagicMock(), mock_spreadsheet)

        service = HierarchicalServiceVS()
        report = service.get_hierarchical_statistics(
            period_type="year",
            period_value="2026",
            reservoir="All",
            parameters=["qve"],
            compare=True,
            compare_years=1
        )

        # Check all reservoirs are listed
        self.assertIn("Vinh Son -A", report)
        self.assertIn("Vinh Son -B", report)
        self.assertIn("Vinh Son -C", report)

        # Verify only a single unified chart and excel block are returned
        self.assertEqual(report.count("```chart"), 3) # 3 reservoirs, 1 chart each
        self.assertEqual(report.count("```excel"), 1) # Only 1 merged excel block
        self.assertIn("Ho A", report)
        self.assertIn("Ho B", report)
        self.assertIn("Ho C", report)
        self.assertIn("Kết luận Phân tích So sánh", report)
        self.assertIn("bao-cao-thong-ke-nam-vinh-son-2026.xlsx", report)

    @patch("ai_tools.vinhson_tools.services.hierarchical_service.get_stats_export_client")
    def test_vinhson_hierarchical_month_single_compare(self, mock_get_client):
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_worksheet.get_all_values.return_value = self.vinhson_fake_data
        mock_spreadsheet.worksheets.return_value = [mock_worksheet]
        mock_get_client.return_value = (MagicMock(), mock_spreadsheet)

        service = HierarchicalServiceVS()
        report = service.get_hierarchical_statistics(
            period_type="month",
            period_value="05/2026",
            reservoir="Vinh Son -A",
            parameters=["qve"],
            compare=True,
            compare_years=3
        )

        self.assertIn("tháng 5/2026", report)
        self.assertIn("Vinh Son -A", report)
        self.assertIn("Kết luận Phân tích So sánh", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)
        self.assertIn("bao-cao-thong-ke-thang-vinh-son-05-2026.xlsx", report)

    @patch("ai_tools.vinhson_tools.services.hierarchical_service.get_stats_export_client")
    def test_vinhson_hierarchical_date_range_all(self, mock_get_client):
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_worksheet.get_all_values.return_value = self.vinhson_fake_data
        mock_spreadsheet.worksheets.return_value = [mock_worksheet]
        mock_get_client.return_value = (MagicMock(), mock_spreadsheet)

        service = HierarchicalServiceVS()
        report = service.get_hierarchical_statistics(
            period_type="range",
            start_date="01/05/2026",
            end_date="02/05/2026",
            reservoir="All",
            parameters=["water_level"]
        )

        self.assertIn("Từ 01/05/2026 đến 02/05/2026", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)
        self.assertIn("bao-cao-thong-ke-ngay-vinh-son-01-05-2026-den-02-05-2026.xlsx", report)

    @patch("ai_tools.vinhson_tools.services.hierarchical_service.get_stats_export_client")
    def test_vinhson_hierarchical_month_all_compare_years_1(self, mock_get_client):
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_worksheet.get_all_values.return_value = self.vinhson_fake_data
        mock_spreadsheet.worksheets.return_value = [mock_worksheet]
        mock_get_client.return_value = (MagicMock(), mock_spreadsheet)

        service = HierarchicalServiceVS()
        report = service.get_hierarchical_statistics(
            period_type="month",
            period_value="05/2026",
            reservoir="All",
            parameters=["qve"],
            compare=True,
            compare_years=1
        )

        # Check all reservoirs are listed
        self.assertIn("Vinh Son -A", report)
        self.assertIn("Vinh Son -B", report)
        self.assertIn("Vinh Son -C", report)

        # Verify only a single unified chart and excel block are returned
        self.assertEqual(report.count("```chart"), 3) # 3 reservoirs, 1 chart each
        self.assertEqual(report.count("```excel"), 1) # Only 1 merged excel block
        self.assertIn("Ho A", report)
        self.assertIn("Ho B", report)
        self.assertIn("Ho C", report)
        self.assertIn("Kết luận Phân tích So sánh", report)
        self.assertIn("bao-cao-thong-ke-thang-vinh-son-05-2026.xlsx", report)
