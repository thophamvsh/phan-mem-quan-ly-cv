from django.test import TestCase
from datetime import date
from thongsothuyvan.models import (
    SonghinhMnh,
    ThongSoThuyVanCaiDat,
)
from thongsothuyvan.hydrology_services import (
    get_capacity_by_reservoir_level,
    get_settings_week_number,
    get_all_weekly_settings_cached,
)

class HydrologyOptimizationTestCase(TestCase):
    def setUp(self):
        # Clear any cached data to ensure a clean state
        get_all_weekly_settings_cached.cache_clear()
        get_settings_week_number.cache_clear()
        
        # Populate capacity points for testing
        SonghinhMnh.objects.create(Mucnuoc=196.0, dungtich=0.0)
        SonghinhMnh.objects.create(Mucnuoc=200.0, dungtich=10.0)
        SonghinhMnh.objects.create(Mucnuoc=209.0, dungtich=100.0)
        
        # Setup a weekly setting
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
            tuan=12,
            tuan_bat_dau=date(2026, 3, 16),
            tuan_ket_thuc=date(2026, 3, 22),
            mucnuoc_gioihan_tuan=201.5
        )

    def test_float_interpolation_correctness(self):
        # Test exact match
        cap_exact = get_capacity_by_reservoir_level("songhinh", 200.0)
        self.assertEqual(cap_exact, 10.0)
        
        # Test interpolation: midpoint between 196 and 200 (198.0)
        # Expected capacity is 5.0
        cap_interp = get_capacity_by_reservoir_level("songhinh", 198.0)
        self.assertAlmostEqual(cap_interp, 5.0)

        # Test out of bounds (returns min/max boundary values)
        self.assertEqual(get_capacity_by_reservoir_level("songhinh", 190.0), 0.0)
        self.assertEqual(get_capacity_by_reservoir_level("songhinh", 220.0), 100.0)

    def test_week_number_memory_lookup(self):
        # Inside defined week 12 range (2026-03-18)
        week = get_settings_week_number(date(2026, 3, 18))
        self.assertEqual(week, 12)
        
        # Outside defined ranges (should fallback to ISO week)
        # June 28, 2026 is ISO week 26
        week_iso = get_settings_week_number(date(2026, 6, 28))
        self.assertEqual(week_iso, 26)

    def test_cache_invalidation_via_signals(self):
        # Prime the cache
        get_settings_week_number(date(2026, 3, 18))
        
        # Modify the week number to 15
        setting = ThongSoThuyVanCaiDat.objects.get(nha_may="songhinh", tuan=12)
        setting.tuan = 15
        setting.save()
        
        # Verify the change is reflected (which means cache was cleared and re-evaluated)
        week = get_settings_week_number(date(2026, 3, 18))
        self.assertEqual(week, 15)
