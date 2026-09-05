from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.utils import timezone
from rest_framework.test import APITestCase

from nhatkyvanhanh.device_status import summarize_device_status, validate_device_status_snapshot
from nhatkyvanhanh.models import MauTrangThaiThietBiCa
from nhatkyvanhanh.serializers import SogiaonhancaVHSerializer
from tochuc.models import NhaMay
from quanlyvanhanh.models import ThietBi
from core.models import UserProfile


class DeviceStatusTemplateApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="template-admin", email="template@example.com", password="Template-Safe-2026!"
        )
        self.plant = NhaMay.objects.create(ma_nha_may="TEST", ten_nha_may="Nhà máy Test")
        self.other_plant = NhaMay.objects.create(ma_nha_may="OTHER", ten_nha_may="Nhà máy Khác")
        self.client.force_authenticate(self.user)
        self.payload = {
            "nha_may": self.plant.id,
            "ten_mau": "Mẫu chuẩn",
            "groups": [{
                "ma_nhom": "cap-110kv",
                "tieu_de": "Máy cắt 110 kV",
                "thu_tu": 1,
                "thiet_bi": [
                    {"ma_hien_thi": "MC 171", "trang_thai_mac_dinh": "dong", "thu_tu": 1},
                    {"ma_hien_thi": "MC 172", "trang_thai_mac_dinh": "cat", "thu_tu": 2},
                ],
            }],
        }

    def test_create_version_activate_and_get_active_template(self):
        created = self.client.post("/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/", self.payload, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        template_id = created.data["id"]
        activated = self.client.post(f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{template_id}/kich-hoat/", {}, format="json")
        self.assertEqual(activated.status_code, 200)
        renamed = self.client.patch(
            f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{template_id}/",
            {"ten_mau": "Mẫu chuẩn đã đổi tên"},
            format="json",
        )
        self.assertEqual(renamed.status_code, 200, renamed.data)
        self.assertEqual(renamed.data["ten_mau"], "Mẫu chuẩn đã đổi tên")
        self.assertEqual(
            self.client.patch(
                f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{template_id}/",
                {"groups": self.payload["groups"]},
                format="json",
            ).status_code,
            400,
        )
        version = self.client.post(f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{template_id}/tao-phien-ban/", {"ten_mau": "Mẫu v2"}, format="json")
        self.assertEqual(version.status_code, 201, version.data)
        self.assertEqual(version.data["phien_ban"], 2)
        self.client.post(f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{version.data['id']}/kich-hoat/", {}, format="json")
        self.assertFalse(MauTrangThaiThietBiCa.objects.get(pk=template_id).dang_ap_dung)
        active = self.client.get(f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/dang-ap-dung/?nha_may={self.plant.id}")
        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.data["id"], version.data["id"])

    def test_deletes_an_unused_template_but_protects_a_used_template(self):
        created = self.client.post(
            "/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/", self.payload, format="json"
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(
            self.client.delete(
                f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{created.data['id']}/"
            ).status_code,
            204,
        )

    def test_rejects_duplicate_devices_and_protects_active_template(self):
        self.payload["groups"][0]["thiet_bi"].append(
            {"ma_hien_thi": "mc 171", "trang_thai_mac_dinh": "dong"}
        )
        duplicate = self.client.post("/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/", self.payload, format="json")
        self.assertEqual(duplicate.status_code, 400)

        foreign_device = ThietBi.objects.create(
            ten="Máy cắt khác", ma="OTHER.MC999", ma_day_du="OTHER.MC999", nha_may="OTHER"
        )
        self.payload["groups"][0]["thiet_bi"] = [{
            "thiet_bi": foreign_device.id,
            "ma_hien_thi": "MC 999",
            "trang_thai_mac_dinh": "dong",
        }]
        wrong_plant = self.client.post("/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/", self.payload, format="json")
        self.assertEqual(wrong_plant.status_code, 400)

    def test_snapshot_validation_and_backend_summary(self):
        template = self.client.post("/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/", self.payload, format="json").data
        snapshot = {
            "schema_version": 2,
            "template_id": template["id"],
            "template_version": 1,
            "nha_may": "TEST",
            "groups": [{
                "id": "cap-110kv",
                "tieu_de": "Máy cắt 110 kV",
                "thu_tu": 1,
                "thiet_bi": [
                    {"ma_thiet_bi": "MC 171", "trang_thai": "dong", "ghi_chu": ""},
                    {"ma_thiet_bi": "MC 172", "trang_thai": "cat", "ghi_chu": "sửa chữa"},
                ],
            }],
        }
        self.assertEqual(validate_device_status_snapshot(snapshot, plant=self.plant), snapshot)
        self.assertEqual(
            summarize_device_status(snapshot),
            "Máy cắt 110 kV: MC 171 đóng; MC 172 (sửa chữa) cắt.",
        )
        invalid = {**snapshot, "nha_may": "OTHER"}
        with self.assertRaisesMessage(ValueError, "không thuộc nhà máy"):
            validate_device_status_snapshot(invalid, plant=self.plant)

    def test_shift_serializer_persists_schema_2_and_preserves_manual_note(self):
        template_data = self.client.post("/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/", self.payload, format="json").data
        snapshot = {
            "schema_version": 2,
            "template_id": template_data["id"],
            "template_version": 1,
            "nha_may": "TEST",
            "groups": [{"id": "cap-110kv", "tieu_de": "Máy cắt 110 kV", "thiet_bi": [{"ma_thiet_bi": "MC 171", "trang_thai": "dong", "ghi_chu": ""}]}],
        }
        start = timezone.make_aware(datetime(2026, 9, 3, 8, 0))
        serializer = SogiaonhancaVHSerializer(data={
            "nha_may": self.plant.id,
            "ngay_truc": date(2026, 9, 3),
            "ca_truc": "A",
            "loai_thoi_gian_truc": "ngay",
            "thoi_gian_bat_dau_ca": start,
            "thoi_gian_giao_ca": start + timedelta(hours=12),
            "trang_thai_thiet_bi": snapshot,
            "ghi_chu_van_hanh_bo_sung": "Theo dõi nhiệt độ.",
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        shift = serializer.save(user_giao_ca=self.user, nguoi_tao=self.user)
        self.assertEqual(shift.trang_thai_thiet_bi["template_id"], template_data["id"])
        self.assertIn("MC 171 đóng", shift.tinh_trang_van_hanh_trong_ca)
        self.assertIn("Theo dõi nhiệt độ.", shift.tinh_trang_van_hanh_trong_ca)
        protected = self.client.delete(
            f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{template_data['id']}/"
        )
        self.assertEqual(protected.status_code, 400)

    def test_regular_user_is_scoped_to_assigned_plant_and_cannot_manage(self):
        created = self.client.post("/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/", self.payload, format="json").data
        self.client.post(f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{created['id']}/kich-hoat/", {}, format="json")
        regular = get_user_model().objects.create_user(
            username="operator", email="operator@example.com", password="Operator-Safe-2026!"
        )
        UserProfile.objects.create(
            user=regular,
            nha_may=self.plant,
            can_view_shift_handover_logs=True,
            can_manage_all_shift_handover_logs=False,
        )
        self.client.force_authenticate(regular)
        own = self.client.get(f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/dang-ap-dung/?nha_may={self.plant.id}")
        self.assertEqual(own.status_code, 200)
        other = self.client.get(f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/dang-ap-dung/?nha_may={self.other_plant.id}")
        self.assertEqual(other.status_code, 404)
        denied = self.client.post("/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/", self.payload, format="json")
        self.assertEqual(denied.status_code, 403)

    def _profile_user(self, username, **permissions):
        user = get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="Operator-Safe-2026!",
        )
        UserProfile.objects.create(user=user, nha_may=self.plant, **permissions)
        return user

    def test_profile_permissions_are_separated_by_action(self):
        viewer = self._profile_user("template-viewer")
        self.client.force_authenticate(viewer)
        self.assertEqual(
            self.client.get("/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/").status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                "/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/",
                self.payload,
                format="json",
            ).status_code,
            403,
        )

        creator = self._profile_user(
            "template-creator", can_create_shift_device_templates=True
        )
        self.client.force_authenticate(creator)
        created = self.client.post(
            "/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/",
            self.payload,
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(
            self.client.patch(
                f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{created.data['id']}/",
                {"ten_mau": "Không được sửa"},
                format="json",
            ).status_code,
            403,
        )

        editor = self._profile_user(
            "template-editor", can_edit_shift_device_templates=True
        )
        self.client.force_authenticate(editor)
        renamed = self.client.patch(
            f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{created.data['id']}/",
            {"ten_mau": "Tên đã được sửa"},
            format="json",
        )
        self.assertEqual(renamed.status_code, 200, renamed.data)

        activator = self._profile_user(
            "template-activator", can_activate_shift_device_templates=True
        )
        self.client.force_authenticate(activator)
        activated = self.client.post(
            f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{created.data['id']}/kich-hoat/",
            {},
            format="json",
        )
        self.assertEqual(activated.status_code, 200, activated.data)

        deleter = self._profile_user(
            "template-deleter", can_delete_shift_device_templates=True
        )
        self.client.force_authenticate(deleter)
        protected = self.client.delete(
            f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{created.data['id']}/"
        )
        self.assertEqual(protected.status_code, 204)

    def test_delete_active_unused_template_activates_previous_version(self):
        # Version 1
        t1 = self.client.post("/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/", self.payload, format="json").data
        self.client.post(f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{t1['id']}/kich-hoat/", {}, format="json")

        # Version 2
        t2 = self.client.post(
            f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{t1['id']}/tao-phien-ban/",
            {"ten_mau": "v2", "groups": self.payload["groups"]},
            format="json",
        ).data
        self.client.post(f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{t2['id']}/kich-hoat/", {}, format="json")

        # Verify v2 is currently active
        self.assertTrue(MauTrangThaiThietBiCa.objects.get(pk=t2["id"]).dang_ap_dung)
        self.assertFalse(MauTrangThaiThietBiCa.objects.get(pk=t1["id"]).dang_ap_dung)

        # Delete active v2 (unused) -> Should succeed and reactivate v1
        response = self.client.delete(f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{t2['id']}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(MauTrangThaiThietBiCa.objects.filter(pk=t2["id"]).exists())
        self.assertTrue(MauTrangThaiThietBiCa.objects.get(pk=t1["id"]).dang_ap_dung)

    def test_django_model_permissions_and_factory_scope_are_enforced(self):
        django_user = self._profile_user(
            "django-template-user", can_view_shift_device_templates=False
        )
        django_user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="nhatkyvanhanh",
                codename="add_mautrangthaithietbica",
            )
        )
        self.client.force_authenticate(django_user)
        created = self.client.post(
            "/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/",
            self.payload,
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["nha_may"], self.plant.id)

        scoped_manager = self._profile_user(
            "scoped-template-manager",
            can_view_shift_device_templates=True,
            can_create_shift_device_templates=True,
            can_edit_shift_device_templates=True,
            can_delete_shift_device_templates=True,
            can_activate_shift_device_templates=True,
        )
        self.client.force_authenticate(self.user)
        other_payload = {**self.payload, "nha_may": self.other_plant.id}
        other_template = self.client.post(
            "/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/",
            other_payload,
            format="json",
        ).data
        self.client.force_authenticate(scoped_manager)
        self.assertEqual(
            self.client.get(
                f"/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/{other_template['id']}/"
            ).status_code,
            404,
        )
        forced_own = self.client.post(
            "/api/nhatkyvanhanh/mau-trang-thai-thiet-bi/",
            other_payload,
            format="json",
        )
        self.assertEqual(forced_own.status_code, 201, forced_own.data)
        self.assertEqual(forced_own.data["nha_may"], self.plant.id)
