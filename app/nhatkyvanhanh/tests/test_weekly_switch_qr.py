from datetime import datetime, time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from auditlog.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import close_old_connections
from django.db.models.deletion import ProtectedError
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from core.models import UserProfile
from core.throttles import WeeklySwitchQRReadRateThrottle
from nhatkyvanhanh.models import (
    ChiTietChuyenDoiThietBi,
    KhuVucChuyenDoiThietBi,
    LanChuyenDoiThietBi,
    MauChuyenDoiThietBi,
    SoChuyenDoiThietBiTuan,
)
from quanlyvanhanh.models import ThietBi
from tochuc.models import NhaMay


User = get_user_model()


class WeeklySwitchQuickEntryTests(APITestCase):
    def setUp(self):
        self.plant = NhaMay.objects.create(
            ma_nha_may="SH", ten_nha_may="Sông Hinh"
        )
        self.other_plant = NhaMay.objects.create(
            ma_nha_may="VS", ten_nha_may="Vĩnh Sơn"
        )
        self.creator = self._user(
            "weekly_creator",
            self.plant,
            can_view_weekly_equipment_switch_logs=True,
            can_create_weekly_equipment_switch_logs=True,
            can_edit_own_weekly_equipment_switch_logs=True,
            can_view_weekly_equipment_switch_templates=True,
        )
        self.viewer = self._user(
            "weekly_viewer",
            self.plant,
            can_view_weekly_equipment_switch_logs=True,
        )
        self.other_user = self._user(
            "weekly_other",
            self.other_plant,
            can_view_weekly_equipment_switch_logs=True,
            can_edit_own_weekly_equipment_switch_logs=True,
        )
        self.manager = self._user(
            "weekly_manager",
            self.plant,
            can_view_weekly_equipment_switch_logs=True,
            can_manage_all_weekly_equipment_switch_logs=True,
            can_view_weekly_equipment_switch_templates=True,
            can_create_weekly_equipment_switch_templates=True,
            can_edit_weekly_equipment_switch_templates=True,
            can_delete_weekly_equipment_switch_templates=True,
        )
        self.superuser = User.objects.create_superuser(
            username="weekly_superuser",
            email="weekly_superuser@example.com",
            password="testpassword123!",
        )
        UserProfile.objects.create(
            user=self.superuser,
            ho_ten="Weekly Superuser",
            is_all_factories=True,
        )
        self.area = KhuVucChuyenDoiThietBi.objects.create(
            nha_may=self.plant,
            ma_khu_vuc="H1",
            ten_khu_vuc="Tổ máy H1",
        )
        self.other_area = KhuVucChuyenDoiThietBi.objects.create(
            nha_may=self.plant,
            ma_khu_vuc="TD",
            ten_khu_vuc="Tự dùng",
        )
        self.device = ThietBi.objects.create(
            nha_may="Sông Hinh",
            ma="OP1",
            ma_day_du="SH.TB.H1.GOV.OP1",
            ten="Bơm dầu điều tốc số 1",
        )
        self.template = MauChuyenDoiThietBi.objects.create(
            nha_may=self.plant,
            khu_vuc=self.area,
            to_may="H1",
            nhom_thiet_bi="Dầu điều tốc",
            thiet_bi=self.device,
        )
        self.log = self._log(self.plant, 2026, 39, "A", self.creator)
        self.run = self._run(self.log, self.creator)
        self.row = ChiTietChuyenDoiThietBi.objects.create(
            lan_chuyen_doi=self.run,
            thiet_bi=self.device,
            khu_vuc=self.area,
            to_may="H1",
            ten_khu_vuc_snapshot="Tổ máy H1",
            nhom_thiet_bi="Dầu điều tốc",
            trang_thai="lam_viec",
        )
        self.resolve_url = reverse(
            "nhatkyvanhanh:weekly-switch-quick-entry-resolve"
        )
        self.lookup_url = reverse(
            "nhatkyvanhanh:weekly-switch-quick-entry-lookup"
        )
        self.save_url = reverse(
            "nhatkyvanhanh:weekly-switch-quick-entry-save"
        )
        self.create_lan_url = reverse(
            "nhatkyvanhanh:weekly-switch-quick-entry-create-lan"
        )

    @staticmethod
    def _user(username, plant, **permissions):
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

    @staticmethod
    def _log(plant, year, week, shift, creator):
        return SoChuyenDoiThietBiTuan.objects.create(
            nha_may=plant,
            nam=year,
            tuan=week,
            ca_truc=shift,
            nguoi_tao=creator,
        )

    @staticmethod
    def _run(log, user):
        moment = timezone.make_aware(
            datetime.combine(log.tuan_bat_dau, time(hour=8))
        )
        return LanChuyenDoiThietBi.objects.create(
            so=log,
            thoi_gian=moment,
            nguoi_thuc_hien=user,
        )

    def _resolve(self, user=None, **params):
        if user:
            self.client.force_authenticate(user=user)
        return self.client.get(
            self.resolve_url,
            {
                "identity": str(self.template.pk),
                "year": 2026,
                "week": 39,
                **params,
            },
        )

    def _save(self, user=None, **payload):
        if user:
            self.client.force_authenticate(user=user)
        return self.client.post(
            self.save_url,
            {
                "identity": str(self.template.pk),
                "log_id": str(self.log.pk),
                "lan_id": str(self.run.pk),
                "expected_updated_at": self.row.updated_at.isoformat(),
                "trang_thai": "du_phong",
                "confirmed": True,
                "ghi_chu": "Đảo định kỳ",
                **payload,
            },
            format="json",
        )

    def _configure_complementary_pair(self):
        group_name = "Bơm dầu điều tốc"
        self.template.nhom_thiet_bi = group_name
        self.template.save(update_fields=["nhom_thiet_bi", "updated_at"])
        self.row.nhom_thiet_bi = group_name
        self.row.save(update_fields=["nhom_thiet_bi", "updated_at"])

        companion_device = ThietBi.objects.create(
            nha_may="Sông Hinh",
            ma="OP2",
            ma_day_du="SH.TB.H1.GOV.OP2",
            ten="Bơm dầu điều tốc số 2",
        )
        companion_template = MauChuyenDoiThietBi.objects.create(
            nha_may=self.plant,
            khu_vuc=self.area,
            to_may="H1",
            nhom_thiet_bi=group_name,
            thiet_bi=companion_device,
        )
        companion_row = ChiTietChuyenDoiThietBi.objects.create(
            lan_chuyen_doi=self.run,
            thiet_bi=companion_device,
            khu_vuc=self.area,
            to_may="H1",
            ten_khu_vuc_snapshot="Tổ máy H1",
            nhom_thiet_bi=group_name,
            trang_thai="du_phong",
        )
        return companion_template, companion_row

    def _configure_vinh_son_machine_group(self):
        log = self._log(self.other_plant, 2026, 39, "A", self.other_user)
        run = self._run(log, self.other_user)
        templates = []
        rows = []
        for index, area_code in enumerate(
            ["DHKK", "KHI_NEN", "THONG_GIO", "TU_DUNG"], start=1
        ):
            area = KhuVucChuyenDoiThietBi.objects.create(
                nha_may=self.other_plant,
                ma_khu_vuc=area_code,
                ten_khu_vuc=area_code.replace("_", " "),
                thu_tu=index,
            )
            device = ThietBi.objects.create(
                nha_may="Vĩnh Sơn",
                ma=f"VS-{index}",
                ma_day_du=f"VS.TB.{area_code}.{index}",
                ten=f"Thiết bị Tổ máy {area_code}",
            )
            template = MauChuyenDoiThietBi.objects.create(
                nha_may=self.other_plant,
                khu_vuc=area,
                to_may=area_code,
                nhom_thiet_bi="TỔ MÁY",
                thiet_bi=device,
                thu_tu=index,
            )
            row = ChiTietChuyenDoiThietBi.objects.create(
                lan_chuyen_doi=run,
                thiet_bi=device,
                khu_vuc=area,
                to_may=area_code,
                ten_khu_vuc_snapshot=area.ten_khu_vuc,
                nhom_thiet_bi="TỔ MÁY",
                trang_thai="du_phong",
                thu_tu=index,
            )
            templates.append(template)
            rows.append(row)
        return log, run, templates, rows

    def test_resolve_requires_auth(self):
        self.assertEqual(self._resolve().status_code, status.HTTP_401_UNAUTHORIZED)

    def test_vinh_son_machine_group_uses_one_qr_across_areas(self):
        log, run, templates, rows = self._configure_vinh_son_machine_group()
        self.template = templates[0]

        response = self._resolve(self.other_user, shift="A")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["group"]["member_count"], 4)
        self.assertEqual(response.data["group"]["type"], "nhom_dong_bo")
        self.assertEqual(
            response.data["group"]["area"], "Các khu vực thuộc nhóm Tổ máy"
        )
        self.assertCountEqual(
            [item["id"] for item in response.data["rows"]],
            [str(row.pk) for row in rows],
        )

        response_from_other_area = self.client.get(
            self.resolve_url,
            {
                "identity": str(templates[-1].pk),
                "year": 2026,
                "week": 39,
                "shift": "A",
            },
        )
        self.assertEqual(response_from_other_area.status_code, status.HTTP_200_OK)
        self.assertEqual(response_from_other_area.data["group"]["member_count"], 4)

        save_response = self.client.post(
            self.save_url,
            {
                "identity": str(templates[-1].pk),
                "log_id": str(log.pk),
                "lan_id": str(run.pk),
                "items": [
                    {
                        "row_id": str(row.pk),
                        "expected_updated_at": row.updated_at.isoformat(),
                        "trang_thai": "lam_viec",
                        "ghi_chu": f"Đã kiểm tra {row.to_may}",
                    }
                    for row in rows
                ],
                "confirmed": True,
            },
            format="json",
        )
        self.assertEqual(save_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(save_response.data["rows"]), 4)
        self.assertEqual(
            ChiTietChuyenDoiThietBi.objects.filter(
                pk__in=[row.pk for row in rows], trang_thai="lam_viec"
            ).count(),
            4,
        )

    def test_resolve_returns_editable_row(self):
        response = self._resolve(self.creator, shift="A")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "editable")
        self.assertEqual(response.data["row"]["thiet_bi_ma_day_du"], self.device.ma_day_du)
        self.assertEqual(response.data["log_summary"]["ca_truc"], "A")

    def test_resolve_rejects_other_factory(self):
        self.assertEqual(
            self._resolve(self.other_user, shift="A").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_resolve_inactive_template(self):
        self.template.dang_su_dung = False
        self.template.save(update_fields=["dang_su_dung", "updated_at"])
        response = self._resolve(self.creator, shift="A")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "inactive_template")

    def test_resolve_missing_log(self):
        response = self._resolve(self.creator, week=40, shift="A")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "log_not_found")

    def test_resolve_multi_shift_requires_shift(self):
        self._log(self.plant, 2026, 39, "B", self.creator)
        response = self._resolve(self.creator)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "shift_required")
        self.assertEqual(
            [item["shift"] for item in response.data["available_shifts"]],
            ["A", "B"],
        )

    def test_resolve_with_specific_shift(self):
        log_b = self._log(self.plant, 2026, 39, "B", self.creator)
        run_b = self._run(log_b, self.creator)
        ChiTietChuyenDoiThietBi.objects.create(
            lan_chuyen_doi=run_b,
            thiet_bi=self.device,
            khu_vuc=self.area,
            to_may="H1",
        )
        response = self._resolve(self.creator, shift="B")
        self.assertEqual(response.data["log_summary"]["id"], str(log_b.pk))

    def test_resolve_missing_specific_shift_does_not_fallback(self):
        response = self._resolve(self.creator, shift="B")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["create_defaults"]["ca_truc"], "B")

    def test_resolve_missing_lan(self):
        log_b = self._log(self.plant, 2026, 39, "B", self.creator)
        response = self._resolve(self.creator, shift="B")
        self.assertEqual(response.data["status"], "lan_not_found")
        self.assertEqual(response.data["log_summary"]["id"], str(log_b.pk))

    def test_resolve_rejects_multiple_runs(self):
        self._run(self.log, self.creator)
        response = self._resolve(self.creator, shift="A")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "multiple_switch_entries_found")

    def test_resolve_rejects_invalid_iso_week(self):
        response = self._resolve(self.creator, year=2025, week=53)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_qr_payload")

    def test_save_valid_status_and_audit(self):
        response = self._save(self.creator)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.row.refresh_from_db()
        self.assertEqual(self.row.trang_thai, "du_phong")
        entry = LogEntry.objects.get_for_object(self.row).order_by("-id").first()
        self.assertEqual(entry.additional_data["source"], "weekly_switch_qr")
        self.assertTrue(entry.additional_data["confirmed"])
        self.assertTrue(response.data["qr_confirmation"]["confirmed"])

        rescanned = self._resolve(self.creator, shift="A")
        self.assertEqual(rescanned.status_code, status.HTTP_200_OK)
        self.assertTrue(rescanned.data["qr_confirmation"]["confirmed"])
        self.assertEqual(
            rescanned.data["qr_confirmation"]["confirmed_by"],
            self.creator.username,
        )

    def test_resolve_returns_companion_for_complementary_pump_pair(self):
        _, companion = self._configure_complementary_pair()

        response = self._resolve(self.creator, shift="A")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["paired_device"]["id"], str(companion.pk))
        self.assertEqual(
            response.data["paired_device"]["trang_thai"],
            "du_phong",
        )

    def test_any_legacy_device_qr_resolves_the_complete_group(self):
        companion_template, _ = self._configure_complementary_pair()
        self.client.force_authenticate(user=self.creator)

        response = self.client.get(
            self.resolve_url,
            {
                "identity": str(companion_template.pk),
                "year": 2026,
                "week": 39,
                "shift": "A",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["group"]["type"], "cap_du_phong")
        self.assertEqual(response.data["group"]["member_count"], 2)
        self.assertEqual(len(response.data["rows"]), 2)

    def test_group_qr_selects_one_working_device_atomically(self):
        _, companion = self._configure_complementary_pair()
        self.row.refresh_from_db()
        companion.refresh_from_db()
        self.client.force_authenticate(user=self.creator)

        response = self.client.post(
            self.save_url,
            {
                "identity": str(self.template.pk),
                "log_id": str(self.log.pk),
                "lan_id": str(self.run.pk),
                "working_device_id": companion.thiet_bi_id,
                "items": [
                    {
                        "row_id": str(self.row.pk),
                        "expected_updated_at": self.row.updated_at.isoformat(),
                        "trang_thai": self.row.trang_thai,
                    },
                    {
                        "row_id": str(companion.pk),
                        "expected_updated_at": companion.updated_at.isoformat(),
                        "trang_thai": companion.trang_thai,
                    },
                ],
                "confirmed": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.row.refresh_from_db()
        companion.refresh_from_db()
        self.assertEqual(self.row.trang_thai, "du_phong")
        self.assertEqual(companion.trang_thai, "lam_viec")
        self.assertEqual(len(response.data["rows"]), 2)

    def test_group_qr_rejects_incomplete_group_payload(self):
        self._configure_complementary_pair()
        self.row.refresh_from_db()
        self.client.force_authenticate(user=self.creator)

        response = self.client.post(
            self.save_url,
            {
                "identity": str(self.template.pk),
                "log_id": str(self.log.pk),
                "lan_id": str(self.run.pk),
                "working_device_id": self.device.pk,
                "items": [
                    {
                        "row_id": str(self.row.pk),
                        "expected_updated_at": self.row.updated_at.isoformat(),
                        "trang_thai": "lam_viec",
                    }
                ],
                "confirmed": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "incomplete_group_payload")

    def test_synchronized_group_saves_all_device_states_in_one_request(self):
        second_device = ThietBi.objects.create(
            nha_may="Sông Hinh",
            ma="GOV2",
            ma_day_du="SH.TB.H1.GOV.02",
            ten="Van điều tốc số 2",
        )
        MauChuyenDoiThietBi.objects.create(
            nha_may=self.plant,
            khu_vuc=self.area,
            to_may="H1",
            nhom_thiet_bi=self.template.nhom_thiet_bi,
            thiet_bi=second_device,
        )
        second_row = ChiTietChuyenDoiThietBi.objects.create(
            lan_chuyen_doi=self.run,
            thiet_bi=second_device,
            khu_vuc=self.area,
            to_may="H1",
            ten_khu_vuc_snapshot="Tổ máy H1",
            nhom_thiet_bi=self.template.nhom_thiet_bi,
            trang_thai="du_phong",
        )
        self.row.refresh_from_db()
        self.client.force_authenticate(user=self.creator)

        response = self.client.post(
            self.save_url,
            {
                "identity": str(self.template.pk),
                "log_id": str(self.log.pk),
                "lan_id": str(self.run.pk),
                "items": [
                    {
                        "row_id": str(self.row.pk),
                        "expected_updated_at": self.row.updated_at.isoformat(),
                        "trang_thai": "du_phong",
                        "ghi_chu": "Đã chuyển van 1",
                    },
                    {
                        "row_id": str(second_row.pk),
                        "expected_updated_at": second_row.updated_at.isoformat(),
                        "trang_thai": "lam_viec",
                        "ghi_chu": "Đã chuyển van 2",
                    },
                ],
                "confirmed": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.row.refresh_from_db()
        second_row.refresh_from_db()
        self.assertEqual(self.row.trang_thai, "du_phong")
        self.assertEqual(second_row.trang_thai, "lam_viec")
        self.assertEqual(response.data["group"]["type"], "nhom_dong_bo")

    def test_save_atomically_sets_companion_to_opposite_status(self):
        _, companion = self._configure_complementary_pair()

        response = self._save(self.creator, trang_thai="du_phong")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.row.refresh_from_db()
        companion.refresh_from_db()
        self.assertEqual(self.row.trang_thai, "du_phong")
        self.assertEqual(companion.trang_thai, "lam_viec")
        self.assertEqual(
            response.data["paired_update"]["id"],
            str(companion.pk),
        )
        self.assertEqual(
            response.data["paired_update"]["trang_thai"],
            "lam_viec",
        )
        entry = (
            LogEntry.objects.get_for_object(companion).order_by("-id").first()
        )
        self.assertEqual(
            entry.additional_data["source"],
            "weekly_switch_qr_pair_sync",
        )
        self.assertTrue(entry.additional_data["confirmed"])

    def test_resolve_does_not_treat_seeded_status_as_qr_confirmation(self):
        response = self._resolve(self.creator, shift="A")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["qr_confirmation"]["confirmed"])

    def test_manual_update_after_qr_requires_a_new_qr_confirmation(self):
        saved = self._save(self.creator)
        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        self.row.refresh_from_db()
        self.row.ghi_chu = "Điều chỉnh trực tiếp"
        self.row.save(update_fields=["ghi_chu", "updated_at"])

        rescanned = self._resolve(self.creator, shift="A")
        self.assertEqual(rescanned.status_code, status.HTTP_200_OK)
        self.assertFalse(rescanned.data["qr_confirmation"]["confirmed"])

    def test_save_requires_explicit_confirmation(self):
        response = self._save(self.creator, confirmed=False)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirmed", response.data["errors"])

    def test_save_rejects_empty_status(self):
        response = self._save(self.creator, trang_thai="")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_save_rejects_invalid_status(self):
        response = self._save(self.creator, trang_thai="bao_tri")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_save_rejects_stale_occ_version(self):
        response = self._save(
            self.creator,
            expected_updated_at="2099-01-01T00:00:00+07:00",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "concurrent_modification")
        self.assertIn("current_updated_at", response.data)

    def test_save_locked_log_rejected_for_superuser(self):
        self.log.trang_thai = SoChuyenDoiThietBiTuan.TrangThai.DA_DUYET
        self.log.nguoi_duyet = self.superuser
        self.log.duyet_at = timezone.now()
        self.log.save()
        response = self._save(self.superuser)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "log_locked")

    def test_save_rejects_view_only_user(self):
        response = self._save(self.viewer)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_save_rejects_log_from_other_chain(self):
        foreign_log = self._log(self.other_plant, 2026, 39, "A", self.other_user)
        response = self._save(self.creator, log_id=str(foreign_log.pk))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "broken_relation_chain")

    def test_save_rejects_run_from_other_log(self):
        log_b = self._log(self.plant, 2026, 39, "B", self.creator)
        run_b = self._run(log_b, self.creator)
        response = self._save(self.creator, lan_id=str(run_b.pk))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "broken_relation_chain")

    def test_save_rejects_unexpected_field(self):
        response = self._save(self.creator, nha_may=self.other_plant.pk)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_lookup_exact_code(self):
        self.client.force_authenticate(user=self.creator)
        response = self.client.get(self.lookup_url, {"code": self.device.ma_day_du})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "resolved")
        self.assertEqual(response.data["result"]["identity"], str(self.template.pk))

    def test_lookup_ambiguous_short_code(self):
        device = ThietBi.objects.create(
            nha_may="Sông Hinh",
            ma="OP1-ALT",
            ma_day_du="SH.TB.H2.GOV.OP1",
            ten="Bơm dầu điều tốc H2 số 1",
        )
        MauChuyenDoiThietBi.objects.create(
            nha_may=self.plant,
            khu_vuc=self.other_area,
            to_may="TD",
            thiet_bi=device,
        )
        self.client.force_authenticate(user=self.creator)
        response = self.client.get(self.lookup_url, {"code": "OP"})
        self.assertEqual(response.data["status"], "equipment_selection_required")
        self.assertEqual(len(response.data["results"]), 2)

    def test_lookup_missing_code(self):
        self.client.force_authenticate(user=self.creator)
        response = self.client.get(self.lookup_url, {"code": "NOT-FOUND"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "equipment_not_found")

    def test_lookup_all_factory_user_requires_plant(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(self.lookup_url, {"code": "OP1"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "plant_required")

    def test_lookup_rejects_other_factory_parameter(self):
        self.client.force_authenticate(user=self.creator)
        response = self.client.get(
            self.lookup_url, {"code": "OP1", "plant": "VS"}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_read_rate_throttling_returns_429(self):
        cache.clear()
        WeeklySwitchQRReadRateThrottle.rate = "2/minute"
        try:
            self.client.force_authenticate(user=self.creator)
            responses = [
                self.client.get(
                    self.lookup_url,
                    {"code": self.device.ma_day_du},
                )
                for _ in range(3)
            ]
            self.assertEqual(responses[0].status_code, status.HTTP_200_OK)
            self.assertEqual(responses[1].status_code, status.HTTP_200_OK)
            self.assertEqual(
                responses[2].status_code,
                status.HTTP_429_TOO_MANY_REQUESTS,
            )
        finally:
            del WeeklySwitchQRReadRateThrottle.rate
            cache.clear()

    def test_create_lan_missing_log(self):
        self.client.force_authenticate(user=self.creator)
        response = self.client.post(
            self.create_lan_url, {"log_id": str(uuid4())}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_lan_requires_edit_permission(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.post(
            self.create_lan_url, {"log_id": str(self.log.pk)}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_lan_is_idempotent(self):
        self.client.force_authenticate(user=self.creator)
        response = self.client.post(
            self.create_lan_url, {"log_id": str(self.log.pk)}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["created"])
        self.assertEqual(response.data["lan_id"], str(self.run.pk))

    def test_create_lan_rejects_locked_log(self):
        log = self._log(self.plant, 2026, 40, "A", self.creator)
        log.trang_thai = SoChuyenDoiThietBiTuan.TrangThai.DA_DUYET
        log.nguoi_duyet = self.superuser
        log.duyet_at = timezone.now()
        log.save()
        self.client.force_authenticate(user=self.superuser)
        response = self.client.post(
            self.create_lan_url, {"log_id": str(log.pk)}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "log_locked")

    def test_create_lan_seeds_active_templates(self):
        log = self._log(self.plant, 2026, 40, "A", self.creator)
        self.client.force_authenticate(user=self.creator)
        response = self.client.post(
            self.create_lan_url, {"log_id": str(log.pk)}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["created"])
        self.assertEqual(response.data["seeded_row_count"], 1)

    def test_create_lan_uses_previous_log_of_same_shift(self):
        self.row.trang_thai = "lam_viec"
        self.row.save()
        log_b = self._log(self.plant, 2026, 39, "B", self.creator)
        run_b = self._run(log_b, self.creator)
        ChiTietChuyenDoiThietBi.objects.create(
            lan_chuyen_doi=run_b,
            thiet_bi=self.device,
            khu_vuc=self.area,
            to_may="H1",
            trang_thai="du_phong",
        )
        next_a = self._log(self.plant, 2026, 40, "A", self.creator)
        self.client.force_authenticate(user=self.creator)
        response = self.client.post(
            self.create_lan_url, {"log_id": str(next_a.pk)}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_row = next_a.lan_chuyen_dois.get().chi_tiets.get()
        self.assertEqual(created_row.trang_thai, "du_phong")

    def test_template_delete_deactivates_and_preserves_uuid(self):
        self.client.force_authenticate(user=self.manager)
        url = reverse(
            "nhatkyvanhanh:mauchuyendoithietbi-detail",
            args=[self.template.pk],
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.template.refresh_from_db()
        self.assertFalse(self.template.dang_su_dung)

    def test_duplicate_active_template_is_rejected(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            reverse("nhatkyvanhanh:mauchuyendoithietbi-list"),
            {
                "nha_may": self.plant.pk,
                "khu_vuc": self.other_area.pk,
                "thiet_bi": self.device.pk,
                "nhom_thiet_bi": "Trùng",
                "dang_su_dung": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("đã có một mẫu", str(response.data))

    def test_device_with_template_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.device.delete()


class WeeklySwitchCreateRunConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.plant = NhaMay.objects.create(
            ma_nha_may="SH", ten_nha_may="Sông Hinh"
        )
        self.user = User.objects.create_user(
            username="weekly_concurrent_user",
            email="weekly_concurrent_user@example.com",
            password="testpassword123!",
        )
        UserProfile.objects.create(
            user=self.user,
            ho_ten="Weekly Concurrent User",
            nha_may=self.plant,
            can_view_weekly_equipment_switch_logs=True,
            can_create_weekly_equipment_switch_logs=True,
            can_edit_own_weekly_equipment_switch_logs=True,
        )
        area = KhuVucChuyenDoiThietBi.objects.create(
            nha_may=self.plant,
            ma_khu_vuc="H1",
            ten_khu_vuc="Tổ máy H1",
        )
        device = ThietBi.objects.create(
            nha_may="Sông Hinh",
            ma="CONCURRENT-OP1",
            ten="Bơm kiểm thử đồng thời",
        )
        MauChuyenDoiThietBi.objects.create(
            nha_may=self.plant,
            khu_vuc=area,
            to_may="H1",
            thiet_bi=device,
        )
        self.log = SoChuyenDoiThietBiTuan.objects.create(
            nha_may=self.plant,
            nam=2026,
            tuan=40,
            ca_truc="A",
            nguoi_tao=self.user,
        )
        self.url = reverse(
            "nhatkyvanhanh:weekly-switch-quick-entry-create-lan"
        )

    def _request(self):
        close_old_connections()
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post(
            self.url,
            {"log_id": str(self.log.pk)},
            format="json",
        )
        close_old_connections()
        return response.status_code, response.data["lan_id"]

    def test_create_lan_race_condition_creates_only_one_run(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self._request(), range(2)))

        self.assertEqual(
            sorted(code for code, _ in results),
            [status.HTTP_200_OK, status.HTTP_201_CREATED],
        )
        self.assertEqual(len({run_id for _, run_id in results}), 1)
        self.assertEqual(
            LanChuyenDoiThietBi.objects.filter(so=self.log).count(),
            1,
        )
