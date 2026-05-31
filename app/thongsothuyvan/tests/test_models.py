from django.test import TestCase
from decimal import Decimal
from ..models import (
    SonghinhMnh,
    Vinhson_HoA,
    Vinhson_HoB,
)
from ..hydrology_services import (
    get_capacity_by_level,
    get_operating_capacity_by_level,
    get_operating_capacity_by_reservoir_level,
    get_operating_capacity_range,
    get_capacity_points_for_reservoir,
    get_capacity_bounds_for_reservoir,
)


class HydrologyCalculationTests(TestCase):
    def setUp(self):
        # Clear cache để tránh kết quả rác từ các test trước đó
        get_capacity_points_for_reservoir.cache_clear()
        get_capacity_bounds_for_reservoir.cache_clear()

        # Thiết lập dữ liệu bậc mực nước - dung tích cho hồ Sông Hinh (Operating range: 196m - 209m)
        SonghinhMnh.objects.create(Mucnuoc=Decimal("196.00"), dungtich=Decimal("10.00"))
        SonghinhMnh.objects.create(Mucnuoc=Decimal("200.00"), dungtich=Decimal("30.00"))
        SonghinhMnh.objects.create(Mucnuoc=Decimal("209.00"), dungtich=Decimal("110.00"))

        # Thiết lập dữ liệu cho hồ Vĩnh Sơn A (Operating range: 765m - 775m)
        Vinhson_HoA.objects.create(Mucnuoc=Decimal("765.00"), dungtich=Decimal("5.00"))
        Vinhson_HoA.objects.create(Mucnuoc=Decimal("775.00"), dungtich=Decimal("25.00"))

        # Thiết lập dữ liệu cho hồ Vĩnh Sơn B (Operating range: 813.6m - 826m)
        Vinhson_HoB.objects.create(Mucnuoc=Decimal("813.60"), dungtich=Decimal("2.00"))
        Vinhson_HoB.objects.create(Mucnuoc=Decimal("826.00"), dungtich=Decimal("12.00"))

    def test_get_capacity_by_level(self):
        # Test chính xác tại điểm bậc có sẵn
        capacity = get_capacity_by_level("songhinh", 196.00)
        self.assertEqual(capacity, 10.00)

        # Test nội suy tuyến tính ở giữa hai điểm bậc
        # Mực nước 198m ở giữa 196m (10) và 200m (30) => Dung tích phải là 20
        capacity = get_capacity_by_level("songhinh", 198.00)
        self.assertEqual(capacity, 20.00)

        # Mực nước nằm ngoài khoảng dưới (nhỏ hơn min) => Trả về min
        capacity = get_capacity_by_level("songhinh", 190.00)
        self.assertEqual(capacity, 10.00)

        # Mực nước nằm ngoài khoảng trên (lớn hơn max) => Trả về max
        capacity = get_capacity_by_level("songhinh", 215.00)
        self.assertEqual(capacity, 110.00)

    def test_get_operating_capacity_by_level(self):
        # Dung tích hữu ích hoạt động = dung tích tại mức nước hiện tại - dung tích tại mức nước chết (196m cho Sông Hinh)
        # Tại 196m => 10.00 - 10.00 = 0
        self.assertEqual(get_operating_capacity_by_level("songhinh", 196.00), 0.0)

        # Tại 200m => 30.00 - 10.00 = 20.0
        self.assertEqual(get_operating_capacity_by_level("songhinh", 200.00), 20.0)

        # Tại 209m => 110.00 - 10.00 = 100.0
        self.assertEqual(get_operating_capacity_by_level("songhinh", 209.00), 100.0)

    def test_get_operating_capacity_by_reservoir_level(self):
        # Test cho hồ Vĩnh Sơn B
        # Tại 813.6m => 2.00 - 2.00 = 0
        self.assertEqual(get_operating_capacity_by_reservoir_level("vinhson_b", 813.60), 0.0)

        # Tại 819.8m (trung điểm) => 7.00 - 2.00 = 5.0
        self.assertEqual(get_operating_capacity_by_reservoir_level("vinhson_b", 819.80), 5.0)

    def test_get_operating_capacity_range(self):
        # Trả về khoảng dung tích hoạt động (min_operating=0, max_operating = max_cap - min_cap)
        # Sông Hinh: max_cap (110) - min_cap (10) = 100
        capacity_range = get_operating_capacity_range("songhinh")
        self.assertEqual(capacity_range["min"], 0.0)
        self.assertEqual(capacity_range["max"], 100.0)
