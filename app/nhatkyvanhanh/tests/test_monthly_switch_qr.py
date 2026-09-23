from decimal import Decimal

from auditlog.models import LogEntry
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import UserProfile
from nhatkyvanhanh.models import (
    ChiTietChuyenDoiTBThang,
    MauChuyenDoiTBThang,
    SoChuyenDoiTBThang,
)
from tochuc.models import NhaMay


User = get_user_model()


class MonthlySwitchQuickEntryTests(APITestCase):
    def setUp(self):
        self.plant = NhaMay.objects.create(
            ma_nha_may="SH",
            ten_nha_may="Sông Hinh",
        )
        self.other_plant = NhaMay.objects.create(
            ma_nha_may="VS",
            ten_nha_may="Vĩnh Sơn",
        )
        self.creator = self._create_user(
            "qr_creator",
            self.plant,
            can_view_monthly_equipment_switch_logs=True,
            can_create_monthly_equipment_switch_logs=True,
            can_edit_own_monthly_equipment_switch_logs=True,
        )
        self.viewer = self._create_user(
            "qr_viewer",
            self.plant,
            can_view_monthly_equipment_switch_logs=True,
        )
        self.other_user = self._create_user(
            "qr_other",
            self.other_plant,
            can_view_monthly_equipment_switch_logs=True,
            can_edit_own_monthly_equipment_switch_logs=True,
        )
        self.manager = self._create_user(
            "qr_manager",
            self.plant,
            can_view_monthly_equipment_switch_logs=True,
            can_manage_all_monthly_equipment_switch_logs=True,
        )
        self.superuser = User.objects.create_superuser(
            username="qr_superuser",
            email="qr_superuser@example.com",
            password="testpassword123!",
        )
        UserProfile.objects.create(
            user=self.superuser,
            ho_ten="QR Superuser",
            is_all_factories=True,
        )

        self.template = MauChuyenDoiTBThang.objects.create(
            nha_may=self.plant,
            ma_nhom="I",
            ten_nhom="Máy nén khí",
            ma_hien_thi="SH.MN1",
            ten_hien_thi="MN1",
            don_vi="Giờ",
            loai_tinh_toan="counter",
        )
        self.log = SoChuyenDoiTBThang.objects.create(
            nha_may=self.plant,
            nam=2026,
            thang=9,
            ca_truc="A",
            nguoi_tao=self.creator,
        )
        self.row = ChiTietChuyenDoiTBThang.objects.create(
            so=self.log,
            ma_dinh_danh=self.template.ma_dinh_danh,
            ma_nhom=self.template.ma_nhom,
            ten_nhom=self.template.ten_nhom,
            ma_hien_thi=self.template.ma_hien_thi,
            ten_hien_thi=self.template.ten_hien_thi,
            don_vi=self.template.don_vi,
            loai_tinh_toan="counter",
            dau_nam=Decimal("100.000"),
            dau_thang=Decimal("110.000"),
            cuoi_thang=Decimal("115.000"),
        )
        self.resolve_url = reverse(
            "nhatkyvanhanh:monthly-switch-quick-entry-resolve"
        )
        self.save_url = reverse(
            "nhatkyvanhanh:monthly-switch-quick-entry-save"
        )

    @staticmethod
    def _create_user(username, plant, **permissions):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="testpassword123!",
        )
        UserProfile.objects.create(
            user=user,
            ho_ten=username,
            nha_may=plant,
            **permissions,
        )
        return user

    def _resolve(self, user=None, **params):
        if user:
            self.client.force_authenticate(user=user)
        return self.client.get(
            self.resolve_url,
            {
                "identity": str(self.template.ma_dinh_danh),
                "year": 2026,
                "month": 9,
                **params,
            },
        )

    def _save(self, user=None, **payload):
        if user:
            self.client.force_authenticate(user=user)
        return self.client.post(
            self.save_url,
            {
                "identity": str(self.template.ma_dinh_danh),
                "log_id": str(self.log.pk),
                "expected_updated_at": self.row.updated_at.isoformat(),
                "cuoi_thang": "120.000",
                **payload,
            },
            format="json",
        )

    def test_resolve_requires_authentication(self):
        response = self._resolve()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_resolve_returns_editable_row_and_decimal_strings(self):
        response = self._resolve(self.creator)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "editable")
        self.assertTrue(response.data["can_edit"])
        self.assertEqual(response.data["plant"]["code"], "SH")
        self.assertEqual(response.data["row"]["cuoi_thang"], "115.000")
        self.assertEqual(response.data["version"], self.row.updated_at.isoformat())

    def test_resolve_rejects_user_from_another_factory(self):
        response = self._resolve(self.other_user)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_resolve_rejects_inactive_template(self):
        self.template.dang_su_dung = False
        self.template.save(update_fields=["dang_su_dung", "updated_at"])
        response = self._resolve(self.creator)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "inactive_template")

    def test_resolve_missing_log_returns_create_defaults(self):
        response = self._resolve(self.creator, month=10)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "log_not_found")
        self.assertTrue(response.data["can_create"])
        self.assertEqual(response.data["create_defaults"]["thang"], 10)

    def test_save_updates_calculations_and_audit_metadata(self):
        response = self._save(
            self.creator,
            cuoi_thang="123.000",
            ghi_chu="Đọc tại hiện trường",
            client_time="2026-09-30T17:00:00+07:00",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.row.refresh_from_db()
        self.assertEqual(self.row.cuoi_thang, Decimal("123.000"))
        self.assertEqual(self.row.thuc_hien, Decimal("13.000"))
        self.assertEqual(response.data["row"]["luy_ke_nam"], "23.000")
        self.assertNotEqual(response.data["version"], "")

        entry = (
            LogEntry.objects.get_for_object(self.row)
            .filter(action=LogEntry.Action.UPDATE)
            .order_by("-timestamp", "-id")
            .first()
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.additional_data["source"], "monthly_switch_qr")
        self.assertEqual(
            entry.additional_data["identity"], str(self.template.ma_dinh_danh)
        )
        self.assertEqual(entry.additional_data["new_values"]["cuoi_thang"], "123.000")

    def test_save_rejects_fractional_counter_value(self):
        response = self._save(self.creator, cuoi_thang="123.500")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertIn("cuoi_thang", response.data["errors"])

    def test_save_rejects_stale_or_future_version(self):
        response = self._save(
            self.creator,
            expected_updated_at="2099-01-01T00:00:00+07:00",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "concurrent_modification")

    def test_save_rejects_locked_log_even_for_superuser(self):
        self.log.trang_thai = SoChuyenDoiTBThang.TrangThai.DA_DUYET
        self.log.nguoi_duyet = self.superuser
        self.log.duyet_at = self.log.updated_at
        self.log.save()
        response = self._save(self.superuser)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "log_locked")

    def test_save_rejects_view_only_user(self):
        response = self._save(self.viewer)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_save_rejects_fields_outside_allowlist(self):
        response = self._save(self.creator, nha_may=self.other_plant.pk)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "unexpected_fields")

    def test_save_uses_fuel_validation_from_shared_service(self):
        self.row.loai_tinh_toan = "fuel"
        self.row.dau_thang = Decimal("100.000")
        self.row.nhap_trong_thang = Decimal("0.000")
        self.row.cuoi_thang = Decimal("90.000")
        self.row.save()
        response = self._save(
            self.creator,
            expected_updated_at=self.row.updated_at.isoformat(),
            cuoi_thang="101.000",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertIn("cuoi_thang", response.data["errors"])
