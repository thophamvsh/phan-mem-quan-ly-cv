import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import UserProfile
from nhatkyvanhanh.models.command_template import MauNoiDungVanHanh
from nhatkyvanhanh.serializers.command_template import MauNoiDungVanHanhSerializer
from tochuc.models import NhaMay


class MauNoiDungVanHanhModelConstraintTests(TestCase):
    """Kiểm tra tính toàn vẹn dữ liệu và 4 conditional UniqueConstraints của Model."""

    def setUp(self):
        self.sh = NhaMay.objects.create(ma_nha_may="SH_TEST", ten_nha_may="Sông Hinh")
        self.vs = NhaMay.objects.create(ma_nha_may="VS_TEST", ten_nha_may="Vĩnh Sơn")

    def test_seeded_14_default_templates(self):
        """1. Kiểm tra 14 mẫu chuẩn hệ thống đã được seed đầy đủ."""
        global_templates = MauNoiDungVanHanh.objects.filter(
            nha_may__isnull=True, la_mau_he_thong=True, dang_ap_dung=True
        )
        self.assertEqual(global_templates.count(), 14)
        expected_codes = {
            "hoa_luoi", "dung_may", "dung_du_phong", "tach_to_may", "tach_mba",
            "dong_cat_mc", "bao_hoan_thanh_mc", "phieu_thao_tac", "bao_hoan_thanh_ptt",
            "cap_phieu_cong_tac", "cho_phep_vao_lam_viec", "lenh_dieu_do_p",
            "co_lap_ban_giao", "thao_tac_van_tran"
        }
        actual_codes = set(global_templates.values_list("ma_mau", flat=True))
        self.assertEqual(actual_codes, expected_codes)

    def test_unique_constraint_global_active(self):
        """2. Ràng buộc không cho phép 2 mẫu hệ thống cùng ma_mau cùng dang_ap_dung=True."""
        with self.assertRaises(IntegrityError):
            MauNoiDungVanHanh.objects.create(
                nha_may=None,
                ma_mau="hoa_luoi",  # Đã có phiên bản v1 active
                ten_mau="Hòa lưới trùng",
                dinh_dang_tieu_de="Tiêu đề",
                dinh_dang_mau="Nội dung",
                phien_ban=2,
                dang_ap_dung=True,
            )

    def test_unique_constraint_plant_active(self):
        """3. Ràng buộc không cho phép 2 mẫu của cùng một nhà máy cùng ma_mau cùng dang_ap_dung=True."""
        MauNoiDungVanHanh.objects.create(
            nha_may=self.sh,
            ma_mau="lenh_rieng_sh",
            ten_mau="Lệnh riêng 1",
            dinh_dang_tieu_de="Tiêu đề 1",
            dinh_dang_mau="Nội dung 1",
            phien_ban=1,
            dang_ap_dung=True,
        )
        with self.assertRaises(IntegrityError):
            MauNoiDungVanHanh.objects.create(
                nha_may=self.sh,
                ma_mau="lenh_rieng_sh",
                ten_mau="Lệnh riêng 2",
                dinh_dang_tieu_de="Tiêu đề 2",
                dinh_dang_mau="Nội dung 2",
                phien_ban=2,
                dang_ap_dung=True,
            )

    def test_plant_and_global_same_ma_mau_allowed(self):
        """4. Cho phép mẫu của nhà máy tồn tại song song với mẫu hệ thống có cùng ma_mau (để ghi đè)."""
        sh_override = MauNoiDungVanHanh.objects.create(
            nha_may=self.sh,
            ma_mau="hoa_luoi",  # Trùng ma_mau với global
            ten_mau="Hòa lưới đặc thù SH",
            dinh_dang_tieu_de="Chạy máy SH {to_may}",
            dinh_dang_mau="Hòa lưới máy SH {to_may}",
            phien_ban=1,
            dang_ap_dung=True,
        )
        self.assertIsNotNone(sh_override.pk)
        # Global hoa_luoi vẫn active
        global_hl = MauNoiDungVanHanh.objects.get(nha_may__isnull=True, ma_mau="hoa_luoi")
        self.assertTrue(global_hl.dang_ap_dung)


class MauNoiDungVanHanhSerializerValidationTests(TestCase):
    """Kiểm tra Deep Validation của Serializer."""

    def test_serializer_valid_template(self):
        data = {
            "ma_mau": "lenh_moi",
            "ten_mau": "Lệnh kiểm tra",
            "nhom_mau": "khoi_dong_hoa_luoi",
            "dinh_dang_tieu_de": "Khởi động {to_may}",
            "dinh_dang_mau": "Khởi động tổ máy {to_may} công suất {p} MW",
            "danh_sach_tham_so": [
                {"key": "to_may", "label": "Tổ máy", "type": "select", "options": ["H1", "H2"], "default": "H1"},
                {"key": "p", "label": "Công suất", "type": "number", "min": 0},
            ],
            "thu_tu": 1,
        }
        serializer = MauNoiDungVanHanhSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_serializer_detects_unclosed_braces(self):
        data = {
            "ma_mau": "lenh_loi_ngoac",
            "ten_mau": "Lỗi ngoặc",
            "nhom_mau": "khac",
            "dinh_dang_tieu_de": "Tiêu đề {to_may",
            "dinh_dang_mau": "Nội dung chuẩn",
            "danh_sach_tham_so": [{"key": "to_may", "label": "Tổ máy", "type": "text"}],
        }
        serializer = MauNoiDungVanHanhSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("dinh_dang_tieu_de", serializer.errors)

    def test_serializer_detects_control_characters(self):
        data = {
            "ma_mau": "lenh_loi_ctrl",
            "ten_mau": "Lỗi ký tự điều khiển",
            "nhom_mau": "khac",
            "dinh_dang_tieu_de": "Tiêu đề",
            "dinh_dang_mau": "Nội dung có ký tự null \x00 nguy hiểm",
            "danh_sach_tham_so": [],
        }
        serializer = MauNoiDungVanHanhSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("dinh_dang_mau", serializer.errors)

    def test_serializer_detects_missing_placeholder_param(self):
        data = {
            "ma_mau": "lenh_thieu_param",
            "ten_mau": "Thiếu tham số",
            "nhom_mau": "khac",
            "dinh_dang_tieu_de": "Tiêu đề {thiet_bi}",
            "dinh_dang_mau": "Thao tác {thiet_bi} bởi {nguoi_thuc_hien}",
            "danh_sach_tham_so": [
                {"key": "thiet_bi", "label": "Thiết bị", "type": "text"}
                # Thiếu 'nguoi_thuc_hien'
            ],
        }
        serializer = MauNoiDungVanHanhSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("danh_sach_tham_so", serializer.errors)

    def test_serializer_detects_duplicate_param_keys(self):
        data = {
            "ma_mau": "lenh_trung_key",
            "ten_mau": "Trùng key",
            "nhom_mau": "khac",
            "dinh_dang_tieu_de": "Tiêu đề",
            "dinh_dang_mau": "Nội dung",
            "danh_sach_tham_so": [
                {"key": "to_may", "label": "Tổ máy", "type": "text"},
                {"key": "to_may", "label": "Tổ máy lặp", "type": "text"},
            ],
        }
        serializer = MauNoiDungVanHanhSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("danh_sach_tham_so", serializer.errors)

    def test_serializer_invalid_param_type(self):
        data = {
            "ma_mau": "lenh_loi_type",
            "ten_mau": "Lỗi type",
            "nhom_mau": "khac",
            "dinh_dang_tieu_de": "Tiêu đề",
            "dinh_dang_mau": "Nội dung",
            "danh_sach_tham_so": [
                {"key": "x", "label": "X", "type": "unsupported_data_type"},
            ],
        }
        serializer = MauNoiDungVanHanhSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("danh_sach_tham_so", serializer.errors)

    def test_serializer_select_default_not_in_options(self):
        data = {
            "ma_mau": "lenh_select_loi",
            "ten_mau": "Lỗi select",
            "nhom_mau": "khac",
            "dinh_dang_tieu_de": "Tiêu đề",
            "dinh_dang_mau": "Nội dung",
            "danh_sach_tham_so": [
                {"key": "opt", "label": "Lựa chọn", "type": "select", "options": ["A", "B"], "default": "C"},
            ],
        }
        serializer = MauNoiDungVanHanhSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("danh_sach_tham_so", serializer.errors)


class MauNoiDungVanHanhAPITests(APITestCase):
    """Kiểm tra toàn bộ ViewSet API, phân quyền, merging và concurrency."""

    def setUp(self):
        User = get_user_model()
        self.sh = NhaMay.objects.create(ma_nha_may="SH_API", ten_nha_may="Sông Hinh")
        self.vs = NhaMay.objects.create(ma_nha_may="VS_API", ten_nha_may="Vĩnh Sơn")

        # 1. Superuser
        self.admin = User.objects.create_superuser(
            email="admin_api@vsh.vn", username="admin_api", password="VshSecurePass@2026"
        )
        UserProfile.objects.get_or_create(user=self.admin)

        # 2. Operator SH có đủ quyền quản lý mẫu
        self.sh_user = User.objects.create_user(
            email="sh_user@vsh.vn", username="sh_user", password="VshSecurePass@2026"
        )
        sh_profile, _ = UserProfile.objects.get_or_create(user=self.sh_user)
        sh_profile.nha_may = self.sh
        sh_profile.can_view_shift_command_templates = True
        sh_profile.can_create_shift_command_templates = True
        sh_profile.can_edit_shift_command_templates = True
        sh_profile.can_delete_shift_command_templates = True
        sh_profile.can_activate_shift_command_templates = True
        sh_profile.save()

        # 3. Operator VS có quyền
        self.vs_user = User.objects.create_user(
            email="vs_user@vsh.vn", username="vs_user", password="VshSecurePass@2026"
        )
        vs_profile, _ = UserProfile.objects.get_or_create(user=self.vs_user)
        vs_profile.nha_may = self.vs
        vs_profile.can_view_shift_command_templates = True
        vs_profile.can_create_shift_command_templates = True
        vs_profile.can_edit_shift_command_templates = True
        vs_profile.can_delete_shift_command_templates = True
        vs_profile.can_activate_shift_command_templates = True
        vs_profile.save()

        # 4. User không có quyền
        self.no_perm_user = User.objects.create_user(
            email="no_perm@vsh.vn", username="no_perm", password="VshSecurePass@2026"
        )
        no_perm_profile, _ = UserProfile.objects.get_or_create(user=self.no_perm_user)
        no_perm_profile.nha_may = self.sh
        no_perm_profile.save()

        self.list_url = reverse("nhatkyvanhanh:maunoidungvh-list")
        self.active_url = reverse("nhatkyvanhanh:maunoidungvh-dang-ap-dung")

    def test_permission_guard(self):
        """User không có quyền xem bị 403."""
        self.client.force_authenticate(user=self.no_perm_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dang_ap_dung_merging_plant_precedence(self):
        """Kiểm tra merging: Mẫu nhà máy ghi đè mẫu hệ thống có cùng ma_mau."""
        self.client.force_authenticate(user=self.sh_user)

        # Ban đầu: cả 14 mẫu đều là global
        res1 = self.client.get(f"{self.active_url}?nha_may={self.sh.pk}")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res1.data), 14)
        hl_template = next(t for t in res1.data if t["ma_mau"] == "hoa_luoi")
        self.assertTrue(hl_template["la_mau_he_thong"])
        self.assertIsNone(hl_template["nha_may"])

        # Tạo mẫu ghi đè của SH
        sh_override = MauNoiDungVanHanh.objects.create(
            nha_may=self.sh,
            ma_mau="hoa_luoi",
            ten_mau="Hòa lưới riêng Thủy điện Sông Hinh",
            nhom_mau="khoi_dong_hoa_luoi",
            dinh_dang_tieu_de="Chạy máy SH {to_may}",
            dinh_dang_mau="Hòa lưới máy SH {to_may}, phát {cong_suat} MW / lệnh {nguoi_ra_lenh}.",
            danh_sach_tham_so=[
                {"key": "to_may", "label": "Tổ máy", "type": "select", "options": ["H1", "H2"]},
                {"key": "cong_suat", "label": "P (MW)", "type": "number"},
                {"key": "nguoi_ra_lenh", "label": "Lệnh", "type": "text"},
            ],
            thu_tu=1,
            phien_ban=1,
            dang_ap_dung=True,
            la_mau_he_thong=False,
        )

        # Gọi lại API cho SH: hoa_luoi phải là mẫu riêng của SH
        res2 = self.client.get(f"{self.active_url}?nha_may={self.sh.pk}")
        self.assertEqual(len(res2.data), 14)
        sh_hl = next(t for t in res2.data if t["ma_mau"] == "hoa_luoi")
        self.assertEqual(sh_hl["ten_mau"], "Hòa lưới riêng Thủy điện Sông Hinh")
        self.assertEqual(sh_hl["nha_may"], self.sh.pk)
        self.assertFalse(sh_hl["la_mau_he_thong"])

        # Nhưng khi gọi cho VS: hoa_luoi vẫn là mẫu hệ thống ban đầu
        res3 = self.client.get(f"{self.active_url}?nha_may={self.vs.pk}")
        vs_hl = next(t for t in res3.data if t["ma_mau"] == "hoa_luoi")
        self.assertTrue(vs_hl["la_mau_he_thong"])
        self.assertIsNone(vs_hl["nha_may"])

    def test_tao_phien_ban_and_kich_hoat(self):
        """Kiểm tra tạo phiên bản mới (phien_ban = max + 1) và kích hoạt chuyển đổi."""
        self.client.force_authenticate(user=self.sh_user)

        # Tạo bản ghi v1 cho SH
        v1 = MauNoiDungVanHanh.objects.create(
            nha_may=self.sh,
            ma_mau="mau_test_vb",
            ten_mau="Mẫu v1",
            nhom_mau="khac",
            dinh_dang_tieu_de="Tiêu đề v1",
            dinh_dang_mau="Nội dung v1",
            danh_sach_tham_so=[],
            phien_ban=1,
            dang_ap_dung=True,
        )

        # Gọi action tao-phien-ban
        clone_url = reverse("nhatkyvanhanh:maunoidungvh-tao-phien-ban", args=[v1.pk])
        res_clone = self.client.post(clone_url, {"ten_mau": "Mẫu v2 đã sửa"})
        self.assertEqual(res_clone.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_clone.data["phien_ban"], 2)
        self.assertFalse(res_clone.data["dang_ap_dung"])
        v2_id = res_clone.data["id"]

        # V1 vẫn đang áp dụng
        v1.refresh_from_db()
        self.assertTrue(v1.dang_ap_dung)

        # Kích hoạt v2
        activate_url = reverse("nhatkyvanhanh:maunoidungvh-kich-hoat", args=[v2_id])
        res_act = self.client.post(activate_url)
        self.assertEqual(res_act.status_code, status.HTTP_200_OK)
        self.assertTrue(res_act.data["dang_ap_dung"])

        # V1 tự động chuyển dang_ap_dung=False
        v1.refresh_from_db()
        self.assertFalse(v1.dang_ap_dung)

    def test_optimistic_concurrency_control(self):
        """Kiểm tra chống ghi đè đồng thời (HTTP 409 Conflict khi updated_at bị cũ)."""
        self.client.force_authenticate(user=self.sh_user)

        target = MauNoiDungVanHanh.objects.create(
            nha_may=self.sh,
            ma_mau="mau_concurrency",
            ten_mau="Mẫu ban đầu",
            nhom_mau="khac",
            dinh_dang_tieu_de="Tiêu đề",
            dinh_dang_mau="Nội dung",
            danh_sach_tham_so=[],
            phien_ban=1,
            dang_ap_dung=False,
        )

        detail_url = reverse("nhatkyvanhanh:maunoidungvh-detail", args=[target.pk])

        # Gửi payload với updated_at cũ hơn 10 phút -> Bị 409 Conflict
        stale_time = (timezone.now() - timedelta(minutes=10)).isoformat()
        res_conflict = self.client.patch(detail_url, {
            "ten_mau": "Ghi đè xung đột",
            "updated_at_client": stale_time,
        })
        self.assertEqual(res_conflict.status_code, status.HTTP_409_CONFLICT)

        # Gửi payload với updated_at khớp -> Thành công 200 OK
        current_time = target.updated_at.isoformat()
        res_ok = self.client.patch(detail_url, {
            "ten_mau": "Cập nhật hợp lệ",
            "updated_at_client": current_time,
        })
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        self.assertEqual(res_ok.data["ten_mau"], "Cập nhật hợp lệ")

    def test_delete_protection_for_system_and_active_templates(self):
        """Kiểm tra bảo vệ cấm xóa mẫu hệ thống và cấm xóa phiên bản đang kích hoạt."""
        self.client.force_authenticate(user=self.admin)

        # 1. Mẫu hệ thống -> Cấm xóa
        global_hl = MauNoiDungVanHanh.objects.get(nha_may__isnull=True, ma_mau="hoa_luoi")
        del_global_url = reverse("nhatkyvanhanh:maunoidungvh-detail", args=[global_hl.pk])
        res_del_sys = self.client.delete(del_global_url)
        self.assertEqual(res_del_sys.status_code, status.HTTP_400_BAD_REQUEST)

        # 2. Mẫu nhà máy đang áp dụng -> Cấm xóa
        active_plant = MauNoiDungVanHanh.objects.create(
            nha_may=self.sh,
            ma_mau="mau_active_plant",
            ten_mau="Mẫu active",
            nhom_mau="khac",
            dinh_dang_tieu_de="Tiêu đề",
            dinh_dang_mau="Nội dung",
            danh_sach_tham_so=[],
            phien_ban=1,
            dang_ap_dung=True,
        )
        del_active_url = reverse("nhatkyvanhanh:maunoidungvh-detail", args=[active_plant.pk])
        res_del_act = self.client.delete(del_active_url)
        self.assertEqual(res_del_act.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. Mẫu nhà máy KHÔNG áp dụng (nháp/lịch sử) -> Được phép xóa
        active_plant.dang_ap_dung = False
        active_plant.save()
        res_del_ok = self.client.delete(del_active_url)
        self.assertEqual(res_del_ok.status_code, status.HTTP_204_NO_CONTENT)

    def test_khoi_phuc_mac_dinh_action(self):
        """Kiểm tra khôi phục mặc định: Xóa toàn bộ ghi đè nhà máy, quay về mẫu hệ thống."""
        self.client.force_authenticate(user=self.sh_user)

        # Tạo 2 mẫu riêng cho SH
        MauNoiDungVanHanh.objects.create(
            nha_may=self.sh, ma_mau="hoa_luoi", ten_mau="HL SH", nhom_mau="khac",
            dinh_dang_tieu_de="T", dinh_dang_mau="N", phien_ban=1, dang_ap_dung=True
        )
        MauNoiDungVanHanh.objects.create(
            nha_may=self.sh, ma_mau="dung_may", ten_mau="DM SH", nhom_mau="khac",
            dinh_dang_tieu_de="T", dinh_dang_mau="N", phien_ban=1, dang_ap_dung=True
        )

        self.assertEqual(MauNoiDungVanHanh.objects.filter(nha_may=self.sh).count(), 2)

        reset_url = reverse("nhatkyvanhanh:maunoidungvh-khoi-phuc-mac-dinh")
        res_reset = self.client.post(f"{reset_url}?nha_may={self.sh.pk}")
        self.assertEqual(res_reset.status_code, status.HTTP_200_OK)
        self.assertEqual(res_reset.data["deleted_count"], 2)

        # Tất cả mẫu riêng của SH bị xóa
        self.assertEqual(MauNoiDungVanHanh.objects.filter(nha_may=self.sh).count(), 0)

        # 14 mẫu hệ thống vẫn nguyên vẹn
        self.assertEqual(MauNoiDungVanHanh.objects.filter(nha_may__isnull=True).count(), 14)

    def test_cross_plant_isolation(self):
        """User của VS không thể sửa mẫu của SH."""
        sh_template = MauNoiDungVanHanh.objects.create(
            nha_may=self.sh,
            ma_mau="mau_sh",
            ten_mau="Mẫu của SH",
            nhom_mau="khac",
            dinh_dang_tieu_de="Tiêu đề",
            dinh_dang_mau="Nội dung",
            phien_ban=1,
            dang_ap_dung=False,
        )

        self.client.force_authenticate(user=self.vs_user)
        detail_url = reverse("nhatkyvanhanh:maunoidungvh-detail", args=[sh_template.pk])
        res = self.client.patch(detail_url, {"ten_mau": "VS cố sửa"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
