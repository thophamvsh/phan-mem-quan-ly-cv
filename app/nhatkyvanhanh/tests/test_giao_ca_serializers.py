import datetime
from datetime import timedelta, date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient
from core.models import UserActivityLog, UserProfile
from tochuc.models import NhaMay, DonViToChuc, BoPhan, NhanSu
from nhatkyvanhanh.models import (
    NhanSuSoGiaoNhanCaVH,
    SogiaonhancaHC,
    SogiaonhancaVH,
)
from nhatkyvanhanh.serializers import (
    ChiTietSoGiaoNhanCaHCSerializer,
    NguoiTrucSoGiaoNhanCaHCSerializer,
    SogiaonhancaHCSerializer,
    SogiaonhancaVHSerializer,
    NhanSuSoGiaoNhanCaVHSerializer,
)
from nhatkyvanhanh.views.giao_ca_vh import SogiaonhancaVHFilterSet


class ShiftHandoverSerializerTimeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="hc_shift_creator",
            email="hc-shift-creator@example.com",
            password="VshSecure@2026Test#!",
        )
        self.plant = NhaMay.objects.create(
            ma_nha_may="TEST-SHIFT",
            ten_nha_may="Nhà máy kiểm thử giao nhận ca",
        )

    def _assert_rejects_invalid_range(self, serializer_class, extra_data=None):
        start = timezone.now()
        serializer = serializer_class(
            data={
                "ngay_truc": start.date().isoformat(),
                "nha_may": self.plant.pk,
                "thoi_gian_bat_dau_ca": start.isoformat(),
                "thoi_gian_giao_ca": (start - timedelta(minutes=1)).isoformat(),
                **(extra_data or {}),
            },
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("thoi_gian_giao_ca", serializer.errors)

    def test_vh_rejects_handover_before_shift_start(self):
        self._assert_rejects_invalid_range(
            SogiaonhancaVHSerializer,
            {"ca_truc": "A"},
        )

    def test_hc_rejects_handover_before_shift_start(self):
        self._assert_rejects_invalid_range(SogiaonhancaHCSerializer)

    def test_hc_detail_rejects_end_before_start(self):
        start = timezone.now()
        serializer = ChiTietSoGiaoNhanCaHCSerializer(
            data={
                "thoi_gian": start.isoformat(),
                "thoi_gian_bat_dau": start.isoformat(),
                "thoi_gian_ket_thuc": (start - timedelta(minutes=1)).isoformat(),
                "noi_dung": "Kiểm tra công việc hành chính",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("thoi_gian_ket_thuc", serializer.errors)

    def test_hc_duty_person_rejects_end_before_start(self):
        start = timezone.now()
        serializer = NguoiTrucSoGiaoNhanCaHCSerializer(
            data={
                "thoi_gian": start.isoformat(),
                "thoi_gian_bat_dau": start.isoformat(),
                "thoi_gian_ket_thuc": (start - timedelta(minutes=1)).isoformat(),
                "ten_nguoi_truc": "Nguyễn Văn A",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("thoi_gian_ket_thuc", serializer.errors)

    def _create_hc_shift(self):
        start = timezone.now()
        return SogiaonhancaHC.objects.create(
            ngay_truc=start.date(),
            nha_may=self.plant,
            thoi_gian_bat_dau_ca=start,
            thoi_gian_giao_ca=start + timedelta(days=6),
            user_giao_ca=self.user,
            nguoi_tao=self.user,
        )

    def test_hc_duty_person_allows_omitted_time_range(self):
        shift = self._create_hc_shift()
        serializer = NguoiTrucSoGiaoNhanCaHCSerializer(
            data={"ten_nguoi_truc": "Nhân viên hỗ trợ"},
            context={"shift_log": shift},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_hc_duty_person_range_is_not_limited_by_shift_range(self):
        shift = self._create_hc_shift()
        serializer = NguoiTrucSoGiaoNhanCaHCSerializer(
            data={
                "ten_nguoi_truc": "Nhân viên hỗ trợ",
                "thoi_gian_bat_dau": (
                    shift.thoi_gian_bat_dau_ca - timedelta(hours=1)
                ).isoformat(),
                "thoi_gian_ket_thuc": (
                    shift.thoi_gian_giao_ca + timedelta(hours=1)
                ).isoformat(),
            },
            context={"shift_log": shift},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)


class NhanSuSoGiaoNhanCaVHPhase2Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="test_user",
            email="test@vsh.vn",
            password="VshSecure@2026Test#!",
        )
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save()

        self.plant = NhaMay.objects.create(
            ma_nha_may="SH_TEST",
            ten_nha_may="Thủy điện Sông Hinh Test",
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            ho_ten="Test Admin",
            nha_may=self.plant,
            is_all_factories=True,
            can_view_shift_handover_logs=True,
        )

        self.don_vi = DonViToChuc.objects.create(
            ma_don_vi="DV_TEST",
            ten_don_vi="Phân xưởng Vận hành",
            nha_may=self.plant,
        )
        self.bo_phan = BoPhan.objects.create(
            don_vi=self.don_vi,
            ma_bo_phan="BP_TEST",
            ten_bo_phan="Kíp trực",
        )
        self.nhan_su_1 = NhanSu.objects.create(
            ma_nhan_vien="NV001",
            ho_ten="Nguyễn Văn A",
            don_vi=self.don_vi,
            bo_phan=self.bo_phan,
            chuc_danh="Trưởng ca",
        )
        self.nhan_su_2 = NhanSu.objects.create(
            ma_nhan_vien="NV002",
            ho_ten="Nguyễn Văn A",
            don_vi=self.don_vi,
            bo_phan=self.bo_phan,
            chuc_danh="Trực phụ",
        )
        self.nhan_su_3 = NhanSu.objects.create(
            ma_nhan_vien="NV003",
            ho_ten="Trần Văn C",
            don_vi=self.don_vi,
            bo_phan=self.bo_phan,
            chuc_danh="Kỹ thuật viên",
        )

        # Separate factory and staff to test factory boundary enforcement
        self.plant_vs = NhaMay.objects.create(
            ma_nha_may="VS_TEST",
            ten_nha_may="Thủy điện Vĩnh Sơn Test",
        )
        self.don_vi_vs = DonViToChuc.objects.create(
            ma_don_vi="DV_VS_TEST",
            ten_don_vi="Phân xưởng Vận hành VS",
            nha_may=self.plant_vs,
        )
        self.bo_phan_vs = BoPhan.objects.create(
            don_vi=self.don_vi_vs,
            ma_bo_phan="BP_VS_TEST",
            ten_bo_phan="Kíp trực VS",
        )
        self.nhan_su_vs = NhanSu.objects.create(
            ma_nhan_vien="NV_VS_001",
            ho_ten="Hoàng Vĩnh Sơn",
            don_vi=self.don_vi_vs,
            bo_phan=self.bo_phan_vs,
            chuc_danh="Trực chính",
        )

        start = timezone.now()
        self.shift_log_dem = SogiaonhancaVH.objects.create(
            ngay_truc=start.date(),
            nha_may=self.plant,
            ca_truc="A",
            loai_thoi_gian_truc=SogiaonhancaVH.LoaiThoiGianTruc.DEM,
            thoi_gian_bat_dau_ca=start,
            thoi_gian_giao_ca=start + timedelta(hours=12),
            user_giao_ca=self.user,
            nguoi_tao=self.user,
        )
        self.shift_log_ngay = SogiaonhancaVH.objects.create(
            ngay_truc=start.date(),
            nha_may=self.plant,
            ca_truc="B",
            loai_thoi_gian_truc=SogiaonhancaVH.LoaiThoiGianTruc.NGAY,
            thoi_gian_bat_dau_ca=start,
            thoi_gian_giao_ca=start + timedelta(hours=12),
            user_giao_ca=self.user,
            nguoi_tao=self.user,
        )

    def test_filter_by_loai_thoi_gian_truc(self):
        qs = SogiaonhancaVH.objects.filter(nha_may=self.plant)
        filter_dem = SogiaonhancaVHFilterSet(data={"loai_thoi_gian_truc": "dem"}, queryset=qs)
        self.assertEqual(filter_dem.qs.count(), 1)
        self.assertEqual(filter_dem.qs.first(), self.shift_log_dem)

        filter_ngay = SogiaonhancaVHFilterSet(data={"loai_thoi_gian_truc": "ngay"}, queryset=qs)
        self.assertEqual(filter_ngay.qs.count(), 1)
        self.assertEqual(filter_ngay.qs.first(), self.shift_log_ngay)

    def test_model_auto_snapshot_from_nhan_su(self):
        staff = NhanSuSoGiaoNhanCaVH.objects.create(
            so_giao_nhan_ca=self.shift_log_dem,
            vai_tro=NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_CHINH,
            nhan_su=self.nhan_su_1,
            nguoi_tao=self.user,
        )
        self.assertEqual(staff.ten_nhan_su, "Nguyễn Văn A")
        self.assertEqual(staff.ma_nhan_vien, "NV001")

    def test_serializer_nhan_su_and_detail(self):
        serializer = NhanSuSoGiaoNhanCaVHSerializer(
            data={
                "vai_tro": "truc_phu",
                "nhan_su": self.nhan_su_2.pk,
            },
            context={"shift_log": self.shift_log_dem},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        instance = serializer.save(so_giao_nhan_ca=self.shift_log_dem, nguoi_tao=self.user)
        self.assertEqual(instance.ten_nhan_su, "Nguyễn Văn A")
        self.assertEqual(instance.ma_nhan_vien, "NV002")

        data = NhanSuSoGiaoNhanCaVHSerializer(instance).data
        self.assertEqual(data["ma_nhan_vien"], "NV002")
        self.assertIsNotNone(data["nhan_su_detail"])
        self.assertEqual(data["nhan_su_detail"]["ma_nhan_vien"], "NV002")

    def test_allow_two_staff_with_same_name_different_id_in_same_shift(self):
        # Nhân sự 1: Nguyễn Văn A (NV001)
        NhanSuSoGiaoNhanCaVH.objects.create(
            so_giao_nhan_ca=self.shift_log_dem,
            vai_tro=NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_CHINH,
            nhan_su=self.nhan_su_1,
            nguoi_tao=self.user,
        )
        # Nhân sự 2: cũng tên Nguyễn Văn A nhưng khác ID (NV002)
        serializer = NhanSuSoGiaoNhanCaVHSerializer(
            data={
                "vai_tro": "truc_phu",
                "nhan_su": self.nhan_su_2.pk,
            },
            context={"shift_log": self.shift_log_dem},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save(so_giao_nhan_ca=self.shift_log_dem, nguoi_tao=self.user)
        self.assertEqual(self.shift_log_dem.nhan_su_ca.count(), 2)

    def test_reject_duplicate_nhan_su_id_in_same_shift(self):
        NhanSuSoGiaoNhanCaVH.objects.create(
            so_giao_nhan_ca=self.shift_log_dem,
            vai_tro=NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_PHU,
            nhan_su=self.nhan_su_1,
            nguoi_tao=self.user,
        )
        serializer = NhanSuSoGiaoNhanCaVHSerializer(
            data={
                "vai_tro": "truc_phu",
                "nhan_su": self.nhan_su_1.pk,
            },
            context={"shift_log": self.shift_log_dem},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("nhan_su", serializer.errors)

    def test_reject_nhan_su_from_different_factory(self):
        serializer = NhanSuSoGiaoNhanCaVHSerializer(
            data={
                "vai_tro": "truc_phu",
                "nhan_su": self.nhan_su_vs.pk,
            },
            context={"shift_log": self.shift_log_dem},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("nhan_su", serializer.errors)
        self.assertIn("không thuộc nhà máy", str(serializer.errors["nhan_su"]))

    def test_update_staff_switching_from_a_to_b_refreshes_snapshot(self):
        staff = NhanSuSoGiaoNhanCaVH.objects.create(
            so_giao_nhan_ca=self.shift_log_dem,
            vai_tro=NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_PHU,
            nhan_su=self.nhan_su_1,
            nguoi_tao=self.user,
        )
        self.assertEqual(staff.ten_nhan_su, "Nguyễn Văn A")
        self.assertEqual(staff.ma_nhan_vien, "NV001")

        # Serializer cập nhật nhan_su sang nhan_su_3 ("Trần Văn C" - "NV003")
        serializer = NhanSuSoGiaoNhanCaVHSerializer(
            staff,
            data={"nhan_su": self.nhan_su_3.pk},
            partial=True,
            context={"shift_log": self.shift_log_dem},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        self.assertEqual(updated.ten_nhan_su, "Trần Văn C")
        self.assertEqual(updated.ma_nhan_vien, "NV003")

        # Cập nhật trực tiếp qua model save() cũng tự động cập nhật snapshot
        updated.nhan_su = self.nhan_su_1
        updated.save()
        self.assertEqual(updated.ten_nhan_su, "Nguyễn Văn A")
        self.assertEqual(updated.ma_nhan_vien, "NV001")

    def test_delete_nhan_su_preserves_snapshot_with_set_null(self):
        temp_ns = NhanSu.objects.create(
            ma_nhan_vien="NV_TEMP",
            ho_ten="Lê Văn Tạm",
            don_vi=self.don_vi,
            bo_phan=self.bo_phan,
            chuc_danh="Nhân viên tạm",
        )
        staff = NhanSuSoGiaoNhanCaVH.objects.create(
            so_giao_nhan_ca=self.shift_log_dem,
            vai_tro=NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_PHU,
            nhan_su=temp_ns,
            nguoi_tao=self.user,
        )
        self.assertEqual(staff.ten_nhan_su, "Lê Văn Tạm")
        self.assertEqual(staff.ma_nhan_vien, "NV_TEMP")

        # Xóa NhanSu gốc
        temp_ns.delete()

        # Reload bản ghi từ cơ sở dữ liệu
        staff.refresh_from_db()
        self.assertIsNone(staff.nhan_su)
        self.assertEqual(staff.ten_nhan_su, "Lê Văn Tạm")
        self.assertEqual(staff.ma_nhan_vien, "NV_TEMP")

    def test_api_endpoint_filter_loai_thoi_gian_truc(self):
        client = APIClient()
        client.force_authenticate(user=self.user)

        # 1. Gọi API với ?loai_thoi_gian_truc=dem
        response_dem = client.get("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/?loai_thoi_gian_truc=dem")
        self.assertEqual(response_dem.status_code, 200)
        results_dem = response_dem.data.get("results", response_dem.data)
        self.assertGreaterEqual(len(results_dem), 1)
        self.assertTrue(all(item["loai_thoi_gian_truc"] == "dem" for item in results_dem))

        # 2. Gọi API với ?loai_thoi_gian_truc=ngay
        response_ngay = client.get("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/?loai_thoi_gian_truc=ngay")
        self.assertEqual(response_ngay.status_code, 200)
        results_ngay = response_ngay.data.get("results", response_ngay.data)
        self.assertGreaterEqual(len(results_ngay), 1)
        self.assertTrue(all(item["loai_thoi_gian_truc"] == "ngay" for item in results_ngay))


class NightShiftReportAuditPhase3Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.plant_sh = NhaMay.objects.create(
            ma_nha_may="SH_AUDIT",
            ten_nha_may="Thủy điện Sông Hinh Audit",
        )
        self.plant_vs = NhaMay.objects.create(
            ma_nha_may="VS_AUDIT",
            ten_nha_may="Thủy điện Vĩnh Sơn Audit",
        )

        # 1. User có quyền can_export_night_shift_report cho riêng SH
        self.user_exporter = User.objects.create_user(
            email="exporter@example.com",
            password="testpassword",
            username="exporter",
        )
        UserProfile.objects.create(
            user=self.user_exporter,
            nha_may=self.plant_sh,
            is_all_factories=False,
            can_export_night_shift_report=True,
            can_view_shift_handover_logs=True,
        )

        # 2. User có quyền can_manage_all_shift_handover_logs (quản lý)
        self.user_manager = User.objects.create_user(
            email="manager@example.com",
            password="testpassword",
            username="manager",
        )
        UserProfile.objects.create(
            user=self.user_manager,
            nha_may=self.plant_sh,
            is_all_factories=False,
            can_manage_all_shift_handover_logs=True,
            can_view_shift_handover_logs=True,
        )

        # 3. User thông thường không có quyền xuất ca đêm
        self.user_regular = User.objects.create_user(
            email="regular@example.com",
            password="testpassword",
            username="regular",
        )
        UserProfile.objects.create(
            user=self.user_regular,
            nha_may=self.plant_sh,
            is_all_factories=False,
            can_view_shift_handover_logs=True,
        )

        # 4. Superuser
        self.user_super = User.objects.create_superuser(
            email="super@example.com",
            password="testpassword",
            username="superuser",
        )

        # Tạo sẵn dữ liệu ca đêm thực tế trong DB: Tháng 03/2026
        from datetime import date
        d1 = date(2026, 3, 5)
        d2 = date(2026, 3, 10)

        # Sổ ca 1: hoàn thành (giao_ca_ky_at và nhan_ca_ky_at), 2 nhân sự
        self.log1 = SogiaonhancaVH.objects.create(
            ngay_truc=d1,
            nha_may=self.plant_sh,
            ca_truc="A",
            loai_thoi_gian_truc=SogiaonhancaVH.LoaiThoiGianTruc.DEM,
            thoi_gian_bat_dau_ca=timezone.now(),
            thoi_gian_giao_ca=timezone.now() + timedelta(hours=12),
            user_giao_ca=self.user_exporter,
            user_nhan_ca=self.user_regular,
            giao_ca_ky_at=timezone.now(),
            nhan_ca_ky_at=timezone.now(),
            nguoi_tao=self.user_exporter,
        )
        NhanSuSoGiaoNhanCaVH.objects.create(
            so_giao_nhan_ca=self.log1,
            vai_tro=NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_CHINH,
            ten_nhan_su="Nguyễn Văn A",
            nguoi_tao=self.user_exporter,
        )
        NhanSuSoGiaoNhanCaVH.objects.create(
            so_giao_nhan_ca=self.log1,
            vai_tro=NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_PHU,
            ten_nhan_su="Trần Văn B",
            nguoi_tao=self.user_exporter,
        )

        # Sổ ca 2: chưa hoàn thành (cho_xac_nhan), 1 nhân sự trực chính + 1 KTVH
        self.log2 = SogiaonhancaVH.objects.create(
            ngay_truc=d2,
            nha_may=self.plant_sh,
            ca_truc="B",
            loai_thoi_gian_truc=SogiaonhancaVH.LoaiThoiGianTruc.DEM,
            thoi_gian_bat_dau_ca=timezone.now(),
            thoi_gian_giao_ca=timezone.now() + timedelta(hours=12),
            user_giao_ca=self.user_exporter,
            nguoi_tao=self.user_exporter,
            truc_ktvh="Lê Văn C",
        )
        NhanSuSoGiaoNhanCaVH.objects.create(
            so_giao_nhan_ca=self.log2,
            vai_tro=NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_CHINH,
            ten_nhan_su="Phạm Văn D",
            nguoi_tao=self.user_exporter,
        )

    def test_xuat_ca_dem_creates_user_activity_log_with_server_calculated_metrics(self):
        client = APIClient()
        client.force_authenticate(user=self.user_exporter)

        # 1. Xuất tất cả ca đêm (tat_ca): 2 ca, tổng 5 lượt nhân sự (log1 có 3: Trưởng ca, TC, TP; log2 có 2: Trưởng ca, TC; KTVH bị loại khỏi ca đêm)
        payload = {
            "nha_may_id": self.plant_sh.pk,
            "thang": 3,
            "nam": 2026,
            "trang_thai": "tat_ca",
            "file_name": "SoGiaoNhanCa_DEM_SH_Thang_03_2026.xlsx",
        }
        response = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data=payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("success"))
        self.assertEqual(response.data.get("so_ca"), 2)
        self.assertEqual(response.data.get("tong_luot"), 5)

        log_id = response.data.get("log_id")
        self.assertIsNotNone(log_id)

        log = UserActivityLog.objects.get(pk=log_id)
        self.assertEqual(log.user, self.user_exporter)
        self.assertEqual(log.action_type, "EXPORT_EXCEL")
        self.assertEqual(log.nha_may, self.plant_sh)
        self.assertIn("Tháng 03/2026", log.description)
        self.assertIn("2 ca đêm", log.description)
        self.assertIn("5 lượt nhân sự", log.description)
        self.assertIn("Tất cả ca đêm", log.description)
        self.assertIn("SoGiaoNhanCa_DEM_SH_Thang_03_2026.xlsx", log.description)

        # 2. Xuất chỉ ca hoàn thành (hoan_thanh): chỉ có log1 -> 1 ca, 3 lượt nhân sự (Trưởng ca, TC, TP)
        payload_ht = {
            "nha_may_id": self.plant_sh.pk,
            "thang": 3,
            "nam": 2026,
            "trang_thai": "hoan_thanh",
            "file_name": "SoGiaoNhanCa_DEM_SH_Thang_03_2026.xlsx",
        }
        res_ht = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data=payload_ht, format="json")
        self.assertEqual(res_ht.status_code, 200)
        self.assertEqual(res_ht.data.get("so_ca"), 1)
        self.assertEqual(res_ht.data.get("tong_luot"), 3)

    def test_xuat_ca_dem_ignores_client_metric_tampering(self):
        """Nếu client cố tình truyền số ca/số lượt giả mạo, server vẫn tính toán và ghi số liệu CSDL chuẩn xác."""
        client = APIClient()
        client.force_authenticate(user=self.user_exporter)

        payload = {
            "nha_may_id": self.plant_sh.pk,
            "thang": 3,
            "nam": 2026,
            "trang_thai": "tat_ca",
            "so_ca": 999,
            "tong_luot": 9999,
            "file_name": "SoGiaoNhanCa_DEM_SH_Thang_03_2026.xlsx",
        }
        response = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data=payload, format="json")
        self.assertEqual(response.status_code, 200)
        # Server trả về số liệu xác thực từ database
        self.assertEqual(response.data.get("so_ca"), 2)
        self.assertEqual(response.data.get("tong_luot"), 5)

        log = UserActivityLog.objects.get(pk=response.data.get("log_id"))
        self.assertIn("2 ca đêm", log.description)
        self.assertIn("5 lượt nhân sự", log.description)
        self.assertNotIn("999 ca", log.description)

    def test_xuat_ca_dem_rejects_unauthenticated_user_401(self):
        client = APIClient()
        # Không authenticate
        response = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data={"nha_may_id": self.plant_sh.pk, "thang": 3, "nam": 2026}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_xuat_ca_dem_rejects_unauthorized_user_403(self):
        client = APIClient()
        client.force_authenticate(user=self.user_regular)

        payload = {
            "nha_may_id": self.plant_sh.pk,
            "thang": 3,
            "nam": 2026,
        }
        response = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data=payload, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(UserActivityLog.objects.filter(user=self.user_regular).exists())

    def test_xuat_ca_dem_rejects_unauthorized_factory_scope_403(self):
        client = APIClient()
        client.force_authenticate(user=self.user_exporter)

        # user_exporter chỉ có quyền trên plant_sh, gọi xuất plant_vs
        payload = {
            "nha_may_id": self.plant_vs.pk,
            "thang": 3,
            "nam": 2026,
        }
        response = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data=payload, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertIn("không có quyền", str(response.data))

    def test_xuat_ca_dem_validates_required_and_invalid_fields(self):
        client = APIClient()
        client.force_authenticate(user=self.user_exporter)

        # 1. Thiếu nha_may_id
        res_no_plant = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data={"thang": 3, "nam": 2026}, format="json")
        self.assertEqual(res_no_plant.status_code, 400)

        # 2. Nhà máy không tồn tại
        res_plant_404 = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data={"nha_may_id": 999999, "thang": 3, "nam": 2026}, format="json")
        self.assertEqual(res_plant_404.status_code, 404)

        # 3. Tháng không hợp lệ (13 hoặc 'abc')
        res_inv_month = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data={"nha_may_id": self.plant_sh.pk, "thang": 13, "nam": 2026}, format="json")
        self.assertEqual(res_inv_month.status_code, 400)
        res_str_month = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data={"nha_may_id": self.plant_sh.pk, "thang": "abc", "nam": 2026}, format="json")
        self.assertEqual(res_str_month.status_code, 400)

        # 4. Năm không hợp lệ (< 2000 hoặc > 2100)
        res_inv_year_low = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data={"nha_may_id": self.plant_sh.pk, "thang": 3, "nam": 1999}, format="json")
        self.assertEqual(res_inv_year_low.status_code, 400)
        res_inv_year_high = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data={"nha_may_id": self.plant_sh.pk, "thang": 3, "nam": 2105}, format="json")
        self.assertEqual(res_inv_year_high.status_code, 400)

        # 5. Trạng thái không thuộc danh sách cho phép
        res_inv_status = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data={"nha_may_id": self.plant_sh.pk, "thang": 3, "nam": 2026, "trang_thai": "invalid_status"}, format="json")
        self.assertEqual(res_inv_status.status_code, 400)

        # 6. Số ca hoặc tổng lượt là số âm
        res_neg_so_ca = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data={"nha_may_id": self.plant_sh.pk, "thang": 3, "nam": 2026, "so_ca": -1}, format="json")
        self.assertEqual(res_neg_so_ca.status_code, 400)
        res_neg_tong_luot = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data={"nha_may_id": self.plant_sh.pk, "thang": 3, "nam": 2026, "tong_luot": -10}, format="json")
        self.assertEqual(res_neg_tong_luot.status_code, 400)

        # 7. Tên tệp chứa ký tự không an toàn (path traversal / control chars)
        res_unsafe_file = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data={"nha_may_id": self.plant_sh.pk, "thang": 3, "nam": 2026, "file_name": "../../bad.xlsx"}, format="json")
        self.assertEqual(res_unsafe_file.status_code, 400)

    def test_user_with_manage_all_permission_can_export(self):
        client = APIClient()
        client.force_authenticate(user=self.user_manager)

        payload = {
            "nha_may_id": self.plant_sh.pk,
            "thang": 3,
            "nam": 2026,
            "trang_thai": "tat_ca",
        }
        response = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data=payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("success"))

    def test_superuser_can_export_any_factory(self):
        client = APIClient()
        client.force_authenticate(user=self.user_super)

        payload = {
            "nha_may_id": self.plant_vs.pk,
            "thang": 3,
            "nam": 2026,
        }
        response = client.post("/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/", data=payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("success"))

    def test_user_giao_ca_nhan_su_fields_serialized(self):
        from nhatkyvanhanh.serializers.giao_ca_vh import SogiaonhancaVHSerializer
        from tochuc.models import NhanSu, DonViToChuc, BoPhan
        dv = DonViToChuc.objects.create(ma_don_vi="DV_TEST", ten_don_vi="Đơn vị Test", nha_may=self.plant_sh)
        bp = BoPhan.objects.create(ma_bo_phan="BP_TEST", ten_bo_phan="Bộ phận Test", don_vi=dv)
        ns = NhanSu.objects.create(
            user=self.user_exporter,
            ho_ten="Nguyễn Trưởng Ca",
            ma_nhan_vien="NV_TC_01",
            don_vi=dv,
            bo_phan=bp,
        )
        data = SogiaonhancaVHSerializer(self.log1).data
        self.assertEqual(data.get("user_giao_ca_nhan_su_id"), ns.pk)
        self.assertEqual(data.get("user_giao_ca_ma_nhan_vien"), "NV_TC_01")

    def test_validate_clears_ktvh_and_hc_nguon_for_night_shift(self):
        from nhatkyvanhanh.serializers.giao_ca_vh import SogiaonhancaVHSerializer
        serializer = SogiaonhancaVHSerializer()
        validated = serializer.validate({
            "loai_thoi_gian_truc": SogiaonhancaVH.LoaiThoiGianTruc.DEM,
            "truc_ktvh": "Kỹ thuật viên A",
            "so_giao_nhan_ca_hc_nguon": self.log1,
        })
        self.assertEqual(validated.get("truc_ktvh"), "")
        self.assertIsNone(validated.get("so_giao_nhan_ca_hc_nguon"))

    def test_xuat_ca_dem_accepts_all_and_tat_ca(self):
        """API hợp đồng chấp nhận cả 'tat_ca' và 'all' (ánh xạ phòng vệ sang 'tat_ca')."""
        client = APIClient()
        client.force_authenticate(user=self.user_exporter)

        # 1. Gọi với 'all'
        res_all = client.post(
            "/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/",
            data={"nha_may_id": self.plant_sh.pk, "thang": 3, "nam": 2026, "trang_thai": "all"},
            format="json",
        )
        self.assertEqual(res_all.status_code, 200)
        self.assertEqual(res_all.data.get("so_ca"), 2)

        # 2. Gọi với 'tat_ca'
        res_tat_ca = client.post(
            "/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/",
            data={"nha_may_id": self.plant_sh.pk, "thang": 3, "nam": 2026, "trang_thai": "tat_ca"},
            format="json",
        )
        self.assertEqual(res_tat_ca.status_code, 200)
        self.assertEqual(res_tat_ca.data.get("so_ca"), 2)

    def test_block_new_staff_overlapping_shift_leader(self):
        """Chặn tạo mới nhân sự Trực chính/Trực phụ trùng với Trưởng ca (user_giao_ca)."""
        from nhatkyvanhanh.serializers.giao_ca_vh import NhanSuSoGiaoNhanCaVHSerializer
        from django.core.exceptions import ValidationError as DjangoValidationError
        from rest_framework.exceptions import ValidationError as DRFValidationError

        leader_user = self.log1.user_giao_ca
        leader_name = f"{leader_user.first_name} {leader_user.last_name}".strip() or leader_user.username

        # 1. Serializer validation
        serializer = NhanSuSoGiaoNhanCaVHSerializer(
            data={"ten_nhan_su": leader_name, "vai_tro": NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_PHU},
            context={"shift_log": self.log1},
        )
        with self.assertRaises(DRFValidationError) as ctx:
            serializer.is_valid(raise_exception=True)
        self.assertIn("nhan_su", ctx.exception.detail)
        self.assertIn("Người tạo sổ (Trưởng ca) không được trùng", str(ctx.exception.detail["nhan_su"]))

        # 2. Model clean() validation
        staff = NhanSuSoGiaoNhanCaVH(
            so_giao_nhan_ca=self.log1,
            ten_nhan_su=leader_name,
            vai_tro=NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_PHU,
        )
        with self.assertRaises(DjangoValidationError):
            staff.clean()

    def test_shift_leader_identity_prefers_personnel_directory_name(self):
        """Tên danh mục nhân sự vẫn chặn trùng khi khác họ tên trên tài khoản."""
        from django.core.exceptions import ValidationError as DjangoValidationError
        from rest_framework.exceptions import ValidationError as DRFValidationError
        from nhatkyvanhanh.serializers.giao_ca_vh import (
            NhanSuSoGiaoNhanCaVHSerializer,
            SogiaonhancaVHSerializer,
        )
        from tochuc.models import BoPhan, DonViToChuc, NhanSu

        don_vi = DonViToChuc.objects.create(
            ma_don_vi="DV_LEADER_NAME",
            ten_don_vi="Đơn vị tên Trưởng ca",
            nha_may=self.plant_sh,
        )
        bo_phan = BoPhan.objects.create(
            ma_bo_phan="BP_LEADER_NAME",
            ten_bo_phan="Bộ phận tên Trưởng ca",
            don_vi=don_vi,
        )
        leader = self.log1.user_giao_ca
        leader.first_name = "Tên"
        leader.last_name = "Tài Khoản"
        leader.save(update_fields=["first_name", "last_name"])
        NhanSu.objects.create(
            user=leader,
            ho_ten="Nguyễn Văn Danh Mục",
            ma_nhan_vien="NV_LEADER_NAME",
            don_vi=don_vi,
            bo_phan=bo_phan,
        )

        serializer = NhanSuSoGiaoNhanCaVHSerializer(
            data={
                "ten_nhan_su": "  Nguyễn   Văn Danh Mục ",
                "vai_tro": NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_PHU,
            },
            context={"shift_log": self.log1},
        )
        with self.assertRaises(DRFValidationError):
            serializer.is_valid(raise_exception=True)

        staff = NhanSuSoGiaoNhanCaVH(
            so_giao_nhan_ca=self.log1,
            ten_nhan_su="Nguyễn Văn Danh Mục",
            vai_tro=NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_PHU,
        )
        with self.assertRaises(DjangoValidationError):
            staff.clean()

        data = SogiaonhancaVHSerializer(self.log1).data
        self.assertEqual(data["user_giao_ca_display"], "Nguyễn Văn Danh Mục")

    def test_xuat_ca_dem_cross_reference_identity_deduplication(self):
        """Khử trùng chéo ID - Tên giữa Trưởng ca có ID và Trực chính cũ chỉ có tên."""
        from tochuc.models import NhanSu, DonViToChuc, BoPhan

        # Tạo sổ ca đêm mới với leader có NhanSu ID
        dv = DonViToChuc.objects.create(ma_don_vi="DV_CROSS", ten_don_vi="ĐV Cross", nha_may=self.plant_sh)
        bp = BoPhan.objects.create(ma_bo_phan="BP_CROSS", ten_bo_phan="BP Cross", don_vi=dv)
        ns_leader = NhanSu.objects.create(
            user=self.user_exporter,
            ho_ten="Lê Thị Trưởng Ca",
            ma_nhan_vien="NV_LE_01",
            don_vi=dv,
            bo_phan=bp,
        )
        # Họ tên tài khoản cố ý khác tên trong danh mục nhân sự. Endpoint phải
        # ưu tiên NhanSu.ho_ten để nhận diện bản ghi legacy chỉ có tên.
        self.user_exporter.first_name = "Tên"
        self.user_exporter.last_name = "Tài Khoản"
        self.user_exporter.save()

        shift_cross = SogiaonhancaVH.objects.create(
            nha_may=self.plant_sh,
            ca_truc="A",
            ngay_truc=datetime.date(2026, 4, 1),
            loai_thoi_gian_truc=SogiaonhancaVH.LoaiThoiGianTruc.DEM,
            thoi_gian_bat_dau_ca=timezone.now(),
            thoi_gian_giao_ca=timezone.now() + timedelta(hours=12),
            user_giao_ca=self.user_exporter,
            nguoi_tao=self.user_exporter,
            dia_diem="Đang trực",
            truc_chinh="Lê Thị Trưởng Ca", # Bản ghi cũ trùng tên với Trưởng ca nhưng không có ID
            trang_thai=SogiaonhancaVH.TrangThai.HOAN_THANH,
            nhan_ca_ky_at=timezone.now(),
            giao_ca_ky_at=timezone.now(),
        )

        client = APIClient()
        client.force_authenticate(user=self.user_exporter)
        res = client.post(
            "/api/nhatkyvanhanh/so-giao-nhan-ca-vh/xuat-ca-dem/",
            data={"nha_may_id": self.plant_sh.pk, "thang": 4, "nam": 2026, "trang_thai": "tat_ca"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data.get("so_ca"), 1)
        # Vì Trưởng ca và Trực chính cùng tên, backend khử trùng chéo thành 1 lượt (không phải 2)
        self.assertEqual(res.data.get("tong_luot"), 1)

    def test_model_clean_clears_ktvh_and_hc_nguon_for_night_shift(self):
        """Model SogiaonhancaVH.clean() tự bảo vệ quy tắc xóa KTVH đối với ca đêm."""
        from nhatkyvanhanh.models import SogiaonhancaHC
        hc_log = SogiaonhancaHC.objects.create(
            ngay_truc=datetime.date(2026, 4, 2),
            nha_may=self.plant_sh,
            thoi_gian_bat_dau_ca=timezone.now(),
            thoi_gian_giao_ca=timezone.now() + timedelta(hours=8),
            nguoi_tao=self.user_exporter,
            user_giao_ca=self.user_exporter,
            user_nhan_ca=self.user_regular,
        )
        shift = SogiaonhancaVH(
            nha_may=self.plant_sh,
            ca_truc="B",
            ngay_truc=datetime.date(2026, 4, 2),
            loai_thoi_gian_truc=SogiaonhancaVH.LoaiThoiGianTruc.DEM,
            thoi_gian_bat_dau_ca=timezone.now(),
            thoi_gian_giao_ca=timezone.now() + timedelta(hours=12),
            user_giao_ca=self.user_exporter,
            nguoi_tao=self.user_exporter,
            truc_ktvh="Nguyễn KTVH",
            so_giao_nhan_ca_hc_nguon=hc_log,
        )
        shift.clean()
        self.assertEqual(shift.truc_ktvh, "")
        self.assertIsNone(shift.so_giao_nhan_ca_hc_nguon)
