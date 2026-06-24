from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from ai_tools.leadership_report import (
    build_leadership_actual_water_level_report,
    build_leadership_hydrology_report,
    build_leadership_rainfall_weather_report,
    build_leadership_weekly_limit_report,
)
from thongsothuyvan.hydrology_services import (
    get_capacity_bounds_for_reservoir,
    get_capacity_points_for_reservoir,
    get_settings_week_number,
)
from thongsothuyvan.models import (
    SonghinhMnh,
    ThongSoThuyVanCaiDat,
    ThongSoThuyVanThucTe,
    ThongsoSanxuat,
    ThuongKonTumMnh,
    TramDoMuaVrain,
    Vinhson_HoA,
    Vinhson_HoB,
    Vinhson_Hoc,
)


class LeadershipHydrologyReportTests(TestCase):
    databases = {"default"}

    def setUp(self):
        get_capacity_points_for_reservoir.cache_clear()
        get_capacity_bounds_for_reservoir.cache_clear()

        SonghinhMnh.objects.create(Mucnuoc=Decimal("196.00"), dungtich=Decimal("10.00"))
        SonghinhMnh.objects.create(Mucnuoc=Decimal("209.00"), dungtich=Decimal("110.00"))
        Vinhson_HoA.objects.create(Mucnuoc=Decimal("765.00"), dungtich=Decimal("5.00"))
        Vinhson_HoA.objects.create(Mucnuoc=Decimal("775.00"), dungtich=Decimal("25.00"))
        Vinhson_HoB.objects.create(Mucnuoc=Decimal("813.60"), dungtich=Decimal("2.00"))
        Vinhson_HoB.objects.create(Mucnuoc=Decimal("826.00"), dungtich=Decimal("12.00"))
        Vinhson_Hoc.objects.create(Mucnuoc=Decimal("971.30"), dungtich=Decimal("1.00"))
        Vinhson_Hoc.objects.create(Mucnuoc=Decimal("981.00"), dungtich=Decimal("11.00"))
        ThuongKonTumMnh.objects.create(Mucnuoc=Decimal("1135.00"), dungtich=Decimal("33.34"))
        ThuongKonTumMnh.objects.create(Mucnuoc=Decimal("1144.15"), dungtich=Decimal("64.14"))
        ThuongKonTumMnh.objects.create(Mucnuoc=Decimal("1160.00"), dungtich=Decimal("145.52"))

        self.report_date = date(2026, 6, 12)
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=datetime(2026, 6, 12, 7, 0, tzinfo=timezone.utc),
            cot_g=200.0,
            cot_i=1.0,
            cot_j=2.0,
            cot_k=3.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=datetime(2026, 6, 12, 10, 0, tzinfo=timezone.utc),
            cot_g=202.5,
            cot_i=11.0,
            cot_j=22.0,
            cot_k=33.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="vinhson",
            thoi_gian=datetime(2026, 6, 12, 10, 0, tzinfo=timezone.utc),
            cot_g=770.0,
            cot_i=209.0,  # Total Qve = 44.0 (Lake A) + 77.0 (Lake B) + 88.0 (Lake C)
            cot_j=55.0,
            cot_k=66.0,
            mucnuoc_thuongluu_ho_b=819.8,
            mucnuoc_thuongluu_ho_c=976.15,
            luuluong_ve_ho_b=77.0,
            luuluong_ve_ho_c=88.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="thuongkontum",
            thoi_gian=datetime(2026, 6, 12, 10, 0, tzinfo=timezone.utc),
            cot_g=1144.15,
            cot_i=99.0,
            cot_j=111.0,
            cot_k=0.0,
        )

    def test_hydrology_report_includes_latest_record_and_all_reservoirs(self):
        report = build_leadership_hydrology_report(self.report_date)

        self.assertIn("### Thông số thủy văn", report)
        self.assertIn("| Sông Hinh | 202,50 | 50,000 | 50,000 | 50,0% | 11,00 | 22,00 | 33,00 |", report)
        self.assertIn("| Vĩnh Sơn A | 770,00 | 10,000 | 10,000 | 50,0% | 44,00 | 55,00 | 66,00 |", report)
        self.assertIn("| Vĩnh Sơn B | 819,80 | 5,000 | 5,000 | 50,0% | 77,00 | - | - |", report)
        self.assertIn("| Vĩnh Sơn C | 976,15 | 5,000 | 5,000 | 50,0% | 88,00 | - | - |", report)
        self.assertIn("| Thượng Kon Tum | 1.144,15 | 30,800 | 30,800 | 27,5% | 99,00 | 111,00 | 0,00 |", report)

        self.assertNotIn("| Sông Hinh | 200,00", report)

    def test_hydrology_report_marks_missing_plant_data(self):
        ThongsoSanxuat.objects.filter(nha_may="thuongkontum").delete()

        report = build_leadership_hydrology_report(self.report_date)

        self.assertIn("| Thượng Kon Tum | Không có dữ liệu | - | - | - | - | - | - |", report)


class LeadershipActualWaterLevelReportTests(TestCase):
    databases = {"default"}

    def test_actual_water_level_report_compares_actual_and_reported_levels(self):
        report_date = date(2026, 6, 23)
        ThongSoThuyVanThucTe.objects.create(
            nha_may="songhinh",
            ngay=report_date,
            muc_nuoc_ho=202.4,
            qve=11.0,
        )
        ThongSoThuyVanThucTe.objects.create(
            nha_may="vinhson",
            ngay=report_date,
            muc_nuoc_ho_a=770.5,
            muc_nuoc_ho_b=819.9,
            muc_nuoc_ho_c=976.2,
            qve_ho_a=44.0,
            qve_ho_b=77.0,
            qve_ho_c=88.0,
        )
        ThongSoThuyVanThucTe.objects.create(
            nha_may="thuongkontum",
            ngay=report_date,
            muc_nuoc_ho=1144.3,
            qve=99.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=datetime(2026, 6, 23, 7, 0, tzinfo=timezone.utc),
            cot_g=202.0,
            cot_i=10.5,
        )
        ThongsoSanxuat.objects.create(
            nha_may="vinhson",
            thoi_gian=datetime(2026, 6, 23, 7, 0, tzinfo=timezone.utc),
            cot_g=770.0,
            cot_i=210.0,
            mucnuoc_thuongluu_ho_b=820.0,
            mucnuoc_thuongluu_ho_c=976.0,
            luuluong_ve_ho_b=77.0,
            luuluong_ve_ho_c=88.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="thuongkontum",
            thoi_gian=datetime(2026, 6, 23, 7, 0, tzinfo=timezone.utc),
            cot_g=1144.0,
            cot_i=98.5,
        )

        report = build_leadership_actual_water_level_report(
            report_date,
            report_date,
            compare_reported=True,
        )

        self.assertIn("### Báo cáo mực nước hồ thực tế", report)
        self.assertIn("| 23/06/2026 | Sông Hinh | 202,40 | 202,00 | 0,40 | 11,00 |", report)
        self.assertIn("| 23/06/2026 | Vĩnh Sơn A | 770,50 | 770,00 | 0,50 | 44,00 |", report)
        self.assertIn("| 23/06/2026 | Vĩnh Sơn B | 819,90 | 820,00 | -0,10 | 77,00 |", report)
        self.assertIn("| 23/06/2026 | Vĩnh Sơn C | 976,20 | 976,00 | 0,20 | 88,00 |", report)
        self.assertIn("| 23/06/2026 | Thượng Kon Tum | 1.144,30 | 1.144,00 | 0,30 | 99,00 |", report)
        self.assertIn("Qve báo cáo", report)
        self.assertIn("11,00 | 10,50", report)
        self.assertIn("44,00 | 45,00", report)
        self.assertIn("99,00 | 98,50", report)
        self.assertIn("```chart", report)
        self.assertIn("So sánh MNH và Qve thực tế/báo cáo - Sông Hinh", report)
        self.assertIn('"yKeys": [', report)
        self.assertIn('"MNH thực tế"', report)
        self.assertIn('"MNH báo cáo"', report)
        self.assertIn('"Qve thực tế"', report)
        self.assertIn('"Qve báo cáo"', report)
        self.assertIn('"yTicks": [', report)
        self.assertIn("55", report)
        self.assertIn("110", report)
        self.assertIn("165", report)
        self.assertIn("220", report)
        self.assertIn("ThongSoThuyVanThucTe", report)
        self.assertIn("ThongsoSanxuat", report)

    def test_actual_water_level_report_can_filter_to_songhinh(self):
        report_date = date(2026, 6, 23)
        ThongSoThuyVanThucTe.objects.create(
            nha_may="songhinh",
            ngay=report_date,
            muc_nuoc_ho=202.4,
            qve=11.0,
        )
        ThongSoThuyVanThucTe.objects.create(
            nha_may="vinhson",
            ngay=report_date,
            muc_nuoc_ho_a=770.5,
            qve_ho_a=44.0,
        )

        report = build_leadership_actual_water_level_report(
            report_date,
            report_date,
            plant_codes=("songhinh",),
        )

        self.assertIn("| 23/06/2026 | Sông Hinh | 202,40 |", report)
        self.assertNotIn("Vĩnh Sơn", report)
        self.assertNotIn("Thượng Kon Tum", report)


    def test_actual_water_level_report_defaults_to_actual_only(self):
        report_date = date(2026, 6, 23)
        ThongSoThuyVanThucTe.objects.create(
            nha_may="songhinh",
            ngay=report_date,
            muc_nuoc_ho=202.4,
            qve=11.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=datetime(2026, 6, 23, 7, 0, tzinfo=timezone.utc),
            cot_g=202.0,
            cot_i=10.5,
        )

        report = build_leadership_actual_water_level_report(
            report_date,
            report_date,
            plant_codes=("songhinh",),
        )

        self.assertIn("Thống kê mực nước và Qve thực tế", report)
        self.assertIn("| Ngày | Hồ | MNH thực tế (m) | Qve thực tế (m³/s) |", report)
        self.assertIn("| 23/06/2026 | Sông Hinh | 202,40 | 11,00 |", report)
        self.assertIn("```chart", report)
        self.assertIn("Diễn biến MNH và Qve thực tế - Sông Hinh", report)
        self.assertIn('"MNH thực tế"', report)
        self.assertIn('"Qve thực tế"', report)
        self.assertIn('"yDomain": [', report)
        self.assertIn('"yTicks": [', report)
        self.assertNotIn("Qve báo cáo", report)
        self.assertNotIn("Thá»", report)
        self.assertNotIn("mÃ", report)
        self.assertNotIn("202,00", report)


class LeadershipRainfallWeatherReportTests(TestCase):
    databases = {"default"}

    def test_rainfall_weather_report_uses_database_rainfall_and_weather_api(self):
        reference_date = date(2026, 6, 13)
        start_date = reference_date - timedelta(days=6)
        for index in range(7):
            record_date = start_date + timedelta(days=index)
            TramDoMuaVrain.objects.create(
                Thoi_gian=datetime(record_date.year, record_date.month, record_date.day, tzinfo=timezone.utc),
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

        with patch("ai_tools.leadership_report.services.report_service._fetch_weather_forecast", side_effect=fake_forecast):
            report = build_leadership_rainfall_weather_report(reference_date)

        self.assertIn("### Tổng hợp lượng mưa và dự báo thời tiết", report)
        self.assertIn("**Mưa đo:** 07/06/2026 - 13/06/2026", report)
        self.assertIn("| Ngày | Xã Ea M'đoan | Thôn 10 - Xã Ea M'Doal | UBND xã Sông Hinh |", report)
        self.assertIn("|------|--------|--------|--------|--------|--------|--------|--------|--------|--------|----------------|", report)
        self.assertNotIn("||----------------|", report)
        self.assertIn("| 07/06/2026 | 1,0 | - | - | - | - | - | 2,0 | - | - | 3,0 |", report)
        self.assertIn("| 13/06/2026 | 7,0 | - | - | - | - | - | 2,0 | - | - | 9,0 |", report)
        self.assertIn("| Sông Hinh | 2026-06-14 | Mưa nhỏ | 24,5-31,2°C | 12,3 | 80,0% |", report)


class LeadershipWeeklyLimitReportTests(TestCase):
    databases = {"default"}

    def setUp(self):
        get_capacity_points_for_reservoir.cache_clear()
        get_capacity_bounds_for_reservoir.cache_clear()

        SonghinhMnh.objects.create(Mucnuoc=Decimal("196.00"), dungtich=Decimal("10.00"))
        SonghinhMnh.objects.create(Mucnuoc=Decimal("209.00"), dungtich=Decimal("110.00"))
        Vinhson_HoA.objects.create(Mucnuoc=Decimal("765.00"), dungtich=Decimal("5.00"))
        Vinhson_HoA.objects.create(Mucnuoc=Decimal("775.00"), dungtich=Decimal("25.00"))
        Vinhson_HoB.objects.create(Mucnuoc=Decimal("813.60"), dungtich=Decimal("2.00"))
        Vinhson_HoB.objects.create(Mucnuoc=Decimal("826.00"), dungtich=Decimal("12.00"))
        Vinhson_Hoc.objects.create(Mucnuoc=Decimal("971.30"), dungtich=Decimal("1.00"))
        Vinhson_Hoc.objects.create(Mucnuoc=Decimal("981.00"), dungtich=Decimal("11.00"))
        ThuongKonTumMnh.objects.create(Mucnuoc=Decimal("1135.00"), dungtich=Decimal("33.34"))
        ThuongKonTumMnh.objects.create(Mucnuoc=Decimal("1160.00"), dungtich=Decimal("145.52"))

    def test_weekly_limit_report_compares_current_level_and_forecasts_week_end(self):
        reference_date = date(2026, 6, 13)
        week_number = get_settings_week_number(reference_date)
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
            tuan=week_number,
            tuan_bat_dau=date(2026, 6, 7),
            tuan_ket_thuc=date(2026, 6, 13),
            mucnuoc_gioihan_tuan=205.0,
        )
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="vinhson",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
            tuan=week_number,
            tuan_bat_dau=date(2026, 6, 7),
            tuan_ket_thuc=date(2026, 6, 13),
            mucnuoc_gioihan_tuan_ho_a=772.0,
            mucnuoc_gioihan_tuan_ho_b=822.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=datetime(2026, 6, 10, 0, 0, tzinfo=timezone.utc),
            cot_g=202.5,
            cot_i=20.0,
            cot_j=20.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=datetime(2026, 6, 13, 0, 0, tzinfo=timezone.utc),
            cot_g=202.5,
            cot_i=40.0,
            cot_j=40.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="vinhson",
            thoi_gian=datetime(2026, 6, 13, 0, 0, tzinfo=timezone.utc),
            cot_g=770.0,
            cot_i=15.0,
            cot_j=15.0,
            mucnuoc_thuongluu_ho_b=819.8,
            mucnuoc_thuongluu_ho_c=976.15,
            luuluong_ve_ho_b=5.0,
            luuluong_ve_ho_c=3.0,
        )

        report = build_leadership_weekly_limit_report(reference_date)

        self.assertIn("### Mực nước giới hạn tuần và phân tích", report)
        self.assertIn(f"**Tuần:** {week_number} (07/06/2026 - 13/06/2026)", report)
        self.assertIn("| Sông Hinh |", report)
        self.assertIn("| Vĩnh Sơn A |", report)
        self.assertIn("| Vĩnh Sơn B |", report)
        self.assertNotIn("| Vĩnh Sơn C |", report)
        self.assertIn("202,50 | 205,00 | -2,50 | 50,000 | 19,231", report)
        self.assertIn("30,00 | 30,00", report)  # Kiểm tra Qve và Qcm trung bình ((20+40)/2 = 30)
        self.assertIn("202,50 | 50,000 | Hiện tại thấp hơn MNGH 2,50 m; Dự báo cuối tuần thấp hơn MNGH 2,50 m |", report)
        self.assertIn("Hiện tại thấp hơn MNGH 2,20 m; Chưa đủ dữ liệu Qcm/điều tiết để dự báo", report)
        self.assertIn("Vĩnh Sơn B hiện chưa có Qcm riêng", report)
        self.assertIn("### Phân tích điều tiết bậc thang Vĩnh Sơn", report)
        self.assertIn("| Qve A/B/C trung bình 7 ngày (m³/s) | 7,00 / 5,00 / 3,00 |", report)
        self.assertIn("| Qcm A trung bình 7 ngày (m³/s) | 15,00 |", report)
        self.assertIn("| DT hữu ích hiện tại hồ C (tr.m³) | 5,000 |", report)
        self.assertIn("| B -> A tối thiểu để B không vượt MNGH (m³/s) | 0,00 |", report)
        self.assertIn("| C -> B tối đa theo A/B không vượt MNGH (m³/s) |", report)
        self.assertIn("| C -> B tối đa theo DT hữu ích hiện tại hồ C (m³/s) |", report)
        self.assertIn("| C -> B tối đa theo DT hữu ích C + Qve C đến cuối tuần (m³/s) |", report)
        self.assertIn("| C -> B tối đa khuyến nghị (m³/s) |", report)
        self.assertIn("dung tích hữu ích khả dụng của hồ C quyết định", report)
        self.assertIn("Hồ C chưa có MNGH tuần", report)
        self.assertIn("dung tích hữu ích hiện tại", report)

    def test_weekly_limit_report_uses_latest_seven_days_for_qve_qcm_averages(self):
        reference_date = date(2026, 6, 15)
        week_number = get_settings_week_number(reference_date)
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
            tuan=week_number,
            tuan_bat_dau=date(2026, 6, 15),
            tuan_ket_thuc=date(2026, 6, 21),
            mucnuoc_gioihan_tuan=205.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=datetime(2026, 6, 8, 0, 0, tzinfo=timezone.utc),
            cot_g=202.0,
            cot_i=1000.0,
            cot_j=1000.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=datetime(2026, 6, 9, 0, 0, tzinfo=timezone.utc),
            cot_g=202.0,
            cot_i=20.0,
            cot_j=10.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=datetime(2026, 6, 14, 0, 0, tzinfo=timezone.utc),
            cot_g=202.5,
            cot_i=40.0,
            cot_j=30.0,
        )

        report = build_leadership_weekly_limit_report(reference_date)

        self.assertIn(f"**Tuần:** {week_number} (15/06/2026 - 21/06/2026)", report)
        self.assertIn("| Sông Hinh | 14/06/2026 07:00 | 202,50 | 205,00 | -2,50 |", report)
        self.assertIn("30,00 | 20,00", report)
        self.assertIn("Qve và Qcm trong bảng là trung bình 7 ngày gần nhất", report)

    def test_weekly_limit_report_describes_current_above_limit_but_forecast_below_limit(self):
        reference_date = date(2026, 6, 13)
        week_number = get_settings_week_number(reference_date)
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="vinhson",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
            tuan=week_number,
            tuan_bat_dau=date(2026, 6, 7),
            tuan_ket_thuc=date(2026, 6, 14),
            mucnuoc_gioihan_tuan_ho_a=768.6,
        )
        ThongsoSanxuat.objects.create(
            nha_may="vinhson",
            thoi_gian=datetime(2026, 6, 13, 0, 0, tzinfo=timezone.utc),
            cot_g=768.73,
            cot_i=0.57,
            cot_j=7.89,
        )

        report = build_leadership_weekly_limit_report(reference_date)

        self.assertIn("| Vĩnh Sơn A | 13/06/2026 07:00 | 768,73 | 768,60 | 0,13 |", report)
        self.assertIn("Hiện tại cao hơn MNGH 0,13 m; Dự báo cuối tuần thấp hơn MNGH", report)
        self.assertNotIn("Đang vượt giới hạn; Dự báo không vi phạm", report)

    def test_weekly_limit_report_warns_current_violation_even_without_forecast_data(self):
        reference_date = date(2026, 6, 13)
        week_number = get_settings_week_number(reference_date)
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="vinhson",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
            tuan=week_number,
            tuan_bat_dau=date(2026, 6, 7),
            tuan_ket_thuc=date(2026, 6, 13),
            mucnuoc_gioihan_tuan_ho_b=822.0,
        )
        ThongsoSanxuat.objects.create(
            nha_may="vinhson",
            thoi_gian=datetime(2026, 6, 13, 0, 0, tzinfo=timezone.utc),
            mucnuoc_thuongluu_ho_b=823.5,
            luuluong_ve_ho_b=5.0,
        )

        report = build_leadership_weekly_limit_report(reference_date)

        self.assertIn(
            "| Vĩnh Sơn B | 13/06/2026 07:00 | 823,50 | 822,00 | 1,50 |",
            report,
        )
        self.assertIn(
            "Hiện tại cao hơn MNGH 1,50 m; Chưa đủ dữ liệu Qcm/điều tiết để dự báo",
            report,
        )

    def test_get_settings_week_number_calculates_correct_week_2026(self):
        # 13/06/2026 nằm trong tuần 24 (08/06/2026 - 14/06/2026) theo lịch ISO
        target_date = date(2026, 6, 13)
        week_number = get_settings_week_number(target_date)
        self.assertEqual(week_number, 24)


class LeadershipEventReportTests(TestCase):
    databases = {"default"}

    def setUp(self):
        from khovattu.models import Bang_nha_may
        from django.contrib.auth import get_user_model
        # Tạo mock user
        User = get_user_model()
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="SecurePassword123!")
        # Tạo mock các nhà máy
        self.sh = Bang_nha_may.objects.create(id=1, ma_nha_may="SH", ten_nha_may="Sông Hinh")
        self.vs = Bang_nha_may.objects.create(id=2, ma_nha_may="VS", ten_nha_may="Vĩnh Sơn")
        self.tkt = Bang_nha_may.objects.create(id=3, ma_nha_may="TKT", ten_nha_may="Thượng Kon Tum")

    def test_build_leadership_event_report_statistics_and_pending_list(self):
        from nhatkyvanhanh.models import SuKien
        from ai_tools.leadership_report import build_leadership_event_report

        reference_date = date(2026, 6, 13)

        # Tạo sự kiện trong 7 ngày qua (từ 07/06 đến 13/06)
        # Sông Hinh: 1 sự cố đang xử lý
        SuKien.objects.create(
            nha_may=self.sh,
            thoi_gian_xay_ra=datetime(2026, 6, 10, 10, 0, tzinfo=timezone.utc),
            ten_he_thong_thiet_bi="Hệ thống điều tốc H1",
            hien_tuong_dien_bien="Relay trung gian hỏng",
            loai=SuKien.LoaiSuKien.SU_CO,
            trang_thai=SuKien.TrangThaiXuLy.DANG_XU_LY,
            ben_ghi_nhan_su_kien=self.user,
        )

        # Vĩnh Sơn: 1 khiếm khuyết chưa xử lý xong
        SuKien.objects.create(
            nha_may=self.vs,
            thoi_gian_xay_ra=datetime(2026, 6, 12, 14, 0, tzinfo=timezone.utc),
            ten_he_thong_thiet_bi="Hệ thống chiếu sáng VS",
            hien_tuong_dien_bien="Hỏng bóng đèn hành lang",
            loai=SuKien.LoaiSuKien.KHIEM_KHUYET,
            trang_thai=SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG,
        )

        # Thượng Kon Tum: 1 sự kiện xử lý xong
        SuKien.objects.create(
            nha_may=self.tkt,
            thoi_gian_xay_ra=datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc),
            ten_he_thong_thiet_bi="Hệ thống nước làm mát TKT",
            hien_tuong_dien_bien="Rò rỉ đường ống",
            loai=SuKien.LoaiSuKien.SU_CO,
            trang_thai=SuKien.TrangThaiXuLy.XU_LY_XONG,
            ben_ghi_nhan_su_kien=self.user,
        )

        # 1 sự kiện cũ tồn đọng của Sông Hinh (xảy ra trước 7 ngày)
        old_event = SuKien.objects.create(
            nha_may=self.sh,
            thoi_gian_xay_ra=datetime(2026, 5, 20, 8, 0, tzinfo=timezone.utc),
            ten_he_thong_thiet_bi="Ổ hướng H2 Sông Hinh",
            hien_tuong_dien_bien="Nhiệt độ tăng cao",
            loai=SuKien.LoaiSuKien.SU_CO,
            trang_thai=SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG,
            chi_dao="Cần theo dõi sát nhiệt độ",
        )

        report = build_leadership_event_report(reference_date)

        self.assertIn("### Tình hình thiết bị sự kiện của 3 nhà máy", report)
        self.assertIn("* **Sông Hinh:** 2 sự kiện (Chưa xử lý: 1, Đang xử lý: 1, Đã xử lý: 0)", report)
        self.assertIn("* **Vĩnh Sơn:** 1 sự kiện (Chưa xử lý: 1, Đang xử lý: 0, Đã xử lý: 0)", report)
        self.assertIn("* **Thượng Kon Tum:** 1 sự kiện (Chưa xử lý: 0, Đang xử lý: 0, Đã xử lý: 1)", report)

        # Kiểm tra bảng danh sách sự kiện tồn đọng (chưa xử lý xong và đang xử lý)
        # Gồm: Hệ thống điều tốc H1, Hệ thống chiếu sáng VS, và Ổ hướng H2 Sông Hinh
        self.assertIn("Hệ thống điều tốc H1", report)
        self.assertIn("Hệ thống chiếu sáng VS", report)
        self.assertIn("Ổ hướng H2 Sông Hinh", report)

        # Sự kiện xử lý xong (Hệ thống nước làm mát TKT) không được đưa vào bảng tồn đọng
        self.assertNotIn("Hệ thống nước làm mát TKT", report)

        # Kiểm tra chỉ đạo và link hành động
        self.assertIn("Cần theo dõi sát nhiệt độ", report)
        self.assertIn(f"[Chỉ đạo](/quanlyvanhanh/nhatkysukien?event={old_event.id})", report)

    def test_build_event_statistics_report_is_compact_and_counts_statuses(self):
        from nhatkyvanhanh.models import SuKien
        from ai_tools.leadership_report import build_leadership_event_statistics_report

        shown_event = SuKien.objects.create(
            nha_may=self.sh,
            thoi_gian_xay_ra=datetime(2026, 6, 10, 10, 0, tzinfo=timezone.utc),
            ten_he_thong_thiet_bi="Governor H1",
            hien_tuong_dien_bien="Noi dung dien bien rat dai khong nen dua vao bao cao thong ke gon.",
            loai=SuKien.LoaiSuKien.SU_CO,
            trang_thai=SuKien.TrangThaiXuLy.DANG_XU_LY,
            ben_ghi_nhan_su_kien=self.user,
        )
        SuKien.objects.create(
            nha_may=self.sh,
            thoi_gian_xay_ra=datetime(2026, 6, 11, 8, 0, tzinfo=timezone.utc),
            ten_he_thong_thiet_bi="Lighting SH",
            hien_tuong_dien_bien="Short note",
            loai=SuKien.LoaiSuKien.KHIEM_KHUYET,
            trang_thai=SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG,
        )
        SuKien.objects.create(
            nha_may=self.sh,
            thoi_gian_xay_ra=datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc),
            ten_he_thong_thiet_bi="Cooling SH",
            hien_tuong_dien_bien="Done note",
            loai=SuKien.LoaiSuKien.SU_CO,
            trang_thai=SuKien.TrangThaiXuLy.XU_LY_XONG,
            ben_ghi_nhan_su_kien=self.user,
        )
        SuKien.objects.create(
            nha_may=self.vs,
            thoi_gian_xay_ra=datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc),
            ten_he_thong_thiet_bi="Excluded VS",
            hien_tuong_dien_bien="Other plant",
            loai=SuKien.LoaiSuKien.SU_CO,
            trang_thai=SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG,
        )

        report = build_leadership_event_statistics_report(
            plant_code="SH",
            plant_name="Sông Hinh",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )

        self.assertIn("**Tổng số:** 3 sự kiện", report)
        self.assertIn("* **Chưa xử lý:** 1", report)
        self.assertIn("* **Đang xử lý:** 1", report)
        self.assertIn("* **Đã xử lý:** 1", report)
        self.assertIn("Governor H1", report)
        self.assertIn("Lighting SH", report)
        self.assertIn("Cooling SH", report)
        self.assertNotIn("Noi dung dien bien rat dai", report)
        self.assertNotIn("Excluded VS", report)
        self.assertIn("| STT | Thời gian | Tên sự kiện | Loại | Trạng thái | Chi tiết |", report)
        self.assertIn(f"[Xem chi tiết](/quanlyvanhanh/nhatkysukien?event={shown_event.id})", report)
