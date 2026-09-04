from datetime import date

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from core.models import UserProfile
from nhatkyvanhanh.models import MauTomLuocGiaoCaVH, SogiaonhancaVH
from tochuc.models import NhaMay


class SummaryTemplateApiTests(APITestCase):
    url = "/api/nhatkyvanhanh/mau-tom-luoc-giao-ca-vh/"

    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="summary-admin", email="summary@example.com", password="Safe-2026!"
        )
        self.plant = NhaMay.objects.create(ma_nha_may="SUM", ten_nha_may="Nhà máy mẫu")
        self.other_plant = NhaMay.objects.create(ma_nha_may="SUM2", ten_nha_may="Nhà máy khác")
        self.client.force_authenticate(self.admin)
        self.payload = {
            "nha_may": self.plant.id,
            "ten_mau": "Mẫu tóm lược chuẩn",
            "ghi_chu": "Dùng cho giao ca",
            "hang_muc": [
                {"ten_hang_muc": "Công việc trong ca", "noi_dung_mac_dinh": "", "thu_tu": 1},
                {"ten_hang_muc": "Lưu ý bàn giao", "ghi_chu_mac_dinh": "Kiểm tra ca sau", "thu_tu": 2},
            ],
        }

    def test_create_activate_version_and_get_active(self):
        created = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["phien_ban"], 1)
        self.assertEqual(len(created.data["hang_muc"]), 2)

        activated = self.client.post(f"{self.url}{created.data['id']}/kich-hoat/", {}, format="json")
        self.assertEqual(activated.status_code, 200, activated.data)
        self.assertTrue(activated.data["dang_ap_dung"])

        structural_update = self.client.patch(
            f"{self.url}{created.data['id']}/",
            {"hang_muc": self.payload["hang_muc"]},
            format="json",
        )
        self.assertEqual(structural_update.status_code, 400)

        version = self.client.post(
            f"{self.url}{created.data['id']}/tao-phien-ban/",
            {"ten_mau": "Mẫu tóm lược v2"},
            format="json",
        )
        self.assertEqual(version.status_code, 201, version.data)
        self.assertEqual(version.data["phien_ban"], 2)
        self.assertFalse(version.data["dang_ap_dung"])

        self.client.post(f"{self.url}{version.data['id']}/kich-hoat/", {}, format="json")
        active = self.client.get(f"{self.url}dang-ap-dung/?nha_may={self.plant.id}")
        self.assertEqual(active.status_code, 200, active.data)
        self.assertEqual(active.data["id"], version.data["id"])
        self.assertFalse(MauTomLuocGiaoCaVH.objects.get(pk=created.data["id"]).dang_ap_dung)

    def test_rejects_empty_and_duplicate_items(self):
        empty = self.client.post(self.url, {**self.payload, "hang_muc": []}, format="json")
        self.assertEqual(empty.status_code, 400)
        duplicate = {**self.payload, "hang_muc": [
            {"ten_hang_muc": "Lưu ý", "thu_tu": 1},
            {"ten_hang_muc": " lưu Ý ", "thu_tu": 2},
        ]}
        response = self.client.post(self.url, duplicate, format="json")
        self.assertEqual(response.status_code, 400)

    def test_used_template_is_a_snapshot_reference_and_cannot_be_deleted(self):
        template = self.client.post(self.url, self.payload, format="json").data
        shift = SogiaonhancaVH.objects.create(
            nha_may=self.plant,
            ngay_truc=date(2026, 9, 4),
            ca_truc="A",
            loai_thoi_gian_truc="ngay",
            thoi_gian_giao_ca=timezone.now(),
            user_giao_ca=self.admin,
            nguoi_tao=self.admin,
            mau_tom_luoc_nguon_id=template["id"],
            tong_muc_luc="Công việc trong ca | Nội dung đã sửa |",
        )
        self.assertEqual(self.client.delete(f"{self.url}{template['id']}/").status_code, 400)
        MauTomLuocGiaoCaVH.objects.filter(pk=template["id"]).update(ten_mau="Tên mới")
        shift.refresh_from_db()
        self.assertEqual(shift.tong_muc_luc, "Công việc trong ca | Nội dung đã sửa |")

    def test_profile_permissions_and_factory_scope(self):
        user = get_user_model().objects.create_user(
            username="summary-viewer", email="viewer@example.com", password="Safe-2026!"
        )
        profile = UserProfile.objects.create(
            user=user,
            nha_may=self.plant,
            can_view_shift_summary_templates=True,
        )
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url, self.payload, format="json").status_code, 403)

        profile.can_create_shift_summary_templates = True
        profile.save()
        wrong_plant_payload = {**self.payload, "nha_may": self.other_plant.id}
        created = self.client.post(self.url, wrong_plant_payload, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["nha_may"], self.plant.id)
        self.assertEqual(
            self.client.delete(f"{self.url}{created.data['id']}/").status_code,
            403,
        )
        profile.can_delete_shift_summary_templates = True
        profile.save(update_fields=["can_delete_shift_summary_templates"])
        user.refresh_from_db()
        self.client.force_authenticate(user)
        self.assertEqual(
            self.client.delete(f"{self.url}{created.data['id']}/").status_code,
            204,
        )

    def test_delete_active_unused_template_activates_previous_version(self):
        # Version 1
        t1 = self.client.post(self.url, self.payload, format="json").data
        self.client.post(f"{self.url}{t1['id']}/kich-hoat/", {}, format="json")

        # Version 2
        t2 = self.client.post(f"{self.url}{t1['id']}/tao-phien-ban/", {"ten_mau": "v2"}, format="json").data
        self.client.post(f"{self.url}{t2['id']}/kich-hoat/", {}, format="json")

        # Verify v2 is currently active
        self.assertTrue(MauTomLuocGiaoCaVH.objects.get(pk=t2["id"]).dang_ap_dung)
        self.assertFalse(MauTomLuocGiaoCaVH.objects.get(pk=t1["id"]).dang_ap_dung)

        # Delete active v2 (unused) -> Should succeed and reactivate v1
        response = self.client.delete(f"{self.url}{t2['id']}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(MauTomLuocGiaoCaVH.objects.filter(pk=t2["id"]).exists())
        self.assertTrue(MauTomLuocGiaoCaVH.objects.get(pk=t1["id"]).dang_ap_dung)
