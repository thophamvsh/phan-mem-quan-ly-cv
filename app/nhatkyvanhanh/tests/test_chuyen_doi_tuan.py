from datetime import date, datetime, time
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import UserProfile
from tochuc.models import NhaMay
from quanlyvanhanh.models import ThietBi
from nhatkyvanhanh.models import (
    KhuVucChuyenDoiThietBi,
    MauChuyenDoiThietBi,
    SoChuyenDoiThietBiTuan,
    LanChuyenDoiThietBi,
    ChiTietChuyenDoiThietBi,
)

User = get_user_model()


class ChuyenDoiThietBiTuanTests(APITestCase):
    def setUp(self):
        # 1. Tao Nha may
        self.nha_may = NhaMay.objects.create(
            ma_nha_may="SH",
            ten_nha_may="Song Hinh",
        )

        # 2. Tao Thiet bi
        self.tb1 = ThietBi.objects.create(
            nha_may="Sông Hinh",
            ma="SH.TB.H1.BOM.01",
            ma_day_du="SH.TB.H1.BOM.01",
            ten="Bom nuoc ky thuat 1",
        )
        self.tb2 = ThietBi.objects.create(
            nha_may="Sông Hinh",
            ma="SH.TB.H1.BOM.02",
            ma_day_du="SH.TB.H1.BOM.02",
            ten="Bom nuoc ky thuat 2",
        )

        # 3. Tao Users va Profiles
        self.creator = User.objects.create_user(
            email="creator_cd@example.com",
            password="testpassword123!",
            username="creator_cd",
        )
        self.creator_profile = UserProfile.objects.create(
            user=self.creator,
            ho_ten="Nguyen Van Tao",
            nha_may=self.nha_may,
            chu_ky="signatures/creator_cd.png",
            can_view_weekly_equipment_switch_logs=True,
            can_create_weekly_equipment_switch_logs=True,
            can_edit_own_weekly_equipment_switch_logs=True,
            can_delete_own_weekly_equipment_switch_logs=True,
        )

        self.shift_leader = User.objects.create_user(
            email="shift_leader@example.com",
            password="testpassword123!",
            username="shift_leader",
        )
        self.shift_leader_profile = UserProfile.objects.create(
            user=self.shift_leader,
            ho_ten="Tran Truong Ca",
            nha_may=self.nha_may,
            chu_ky="signatures/shift_leader.png",
            chuc_danh="Truong ca van hanh",
            can_view_weekly_equipment_switch_logs=True,
            can_confirm_weekly_equipment_switch_logs=True,
        )

        self.manager = User.objects.create_user(
            email="manager_cd@example.com",
            password="testpassword123!",
            username="manager_cd",
        )
        self.manager_profile = UserProfile.objects.create(
            user=self.manager,
            ho_ten="Le Quan Ly",
            nha_may=self.nha_may,
            chu_ky="signatures/manager_cd.png",
            can_manage_all_weekly_equipment_switch_logs=True,
            can_view_weekly_equipment_switch_templates=True,
            can_create_weekly_equipment_switch_templates=True,
            can_edit_weekly_equipment_switch_templates=True,
            can_delete_weekly_equipment_switch_templates=True,
        )

        self.unprivileged = User.objects.create_user(
            email="unprivileged_cd@example.com",
            password="testpassword123!",
            username="unprivileged_cd",
        )
        self.unprivileged_profile = UserProfile.objects.create(
            user=self.unprivileged,
            ho_ten="Nguoi khong co quyen",
            nha_may=self.nha_may,
            can_view_weekly_equipment_switch_templates=False,
            can_view_weekly_equipment_switch_logs=False,
        )

        self.khu_vuc_h1 = KhuVucChuyenDoiThietBi.objects.create(
            nha_may=self.nha_may,
            ma_khu_vuc="H1",
            ten_khu_vuc="Tổ máy H1",
            thu_tu=1,
        )

        # 4. Tao Mau thiet bi tuan
        self.mau1 = MauChuyenDoiThietBi.objects.create(
            nha_may=self.nha_may,
            khu_vuc=self.khu_vuc_h1,
            thiet_bi=self.tb1,
            to_may="H1",
            nhom_thiet_bi="Bom nuoc ky thuat",
            thu_tu=1,
            dang_su_dung=True,
        )
        self.mau2 = MauChuyenDoiThietBi.objects.create(
            nha_may=self.nha_may,
            khu_vuc=self.khu_vuc_h1,
            thiet_bi=self.tb2,
            to_may="H1",
            nhom_thiet_bi="Bom nuoc ky thuat",
            thu_tu=2,
            dang_su_dung=True,
        )

    def test_mau_chuyen_doi_thiet_bi_permissions(self):
        url = reverse("nhatkyvanhanh:mauchuyendoithietbi-list")

        # Unprivileged user cannot view template list
        self.client.force_authenticate(user=self.unprivileged)
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Manager with template permissions can view and create
        self.client.force_authenticate(user=self.manager)
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Create new template item
        tb3 = ThietBi.objects.create(
            nha_may="Sông Hinh",
            ma="SH.TB.H1.BOM.03",
            ma_day_du="SH.TB.H1.BOM.03",
            ten="Bom nuoc ky thuat 3",
        )
        create_res = self.client.post(
            url,
            {
                "nha_may": self.nha_may.id,
                "thiet_bi": tb3.id,
                "to_may": "H1",
                "nhom_thiet_bi": "Bom nuoc ky thuat",
                "thu_tu": 3,
                "dang_su_dung": True,
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)

    def test_dynamic_area_crud_and_factory_validation(self):
        url = reverse("nhatkyvanhanh:khuvucchuyendoithietbi-list")
        self.client.force_authenticate(user=self.manager)

        options_response = self.client.options(url)
        self.assertEqual(options_response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            url,
            {
                "nha_may": self.nha_may.id,
                "ma_khu_vuc": "  tram-110kv ",
                "ten_khu_vuc": "Trạm 110 kV",
                "thu_tu": 4,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["ma_khu_vuc"], "TRAM-110KV")

        area_id = response.data["id"]
        response = self.client.patch(
            reverse("nhatkyvanhanh:khuvucchuyendoithietbi-detail", args=[area_id]),
            {"ten_khu_vuc": "Trạm phân phối 110 kV"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ten_khu_vuc"], "Trạm phân phối 110 kV")

        other_factory = NhaMay.objects.create(ma_nha_may="VS", ten_nha_may="Vĩnh Sơn")
        foreign_area = KhuVucChuyenDoiThietBi.objects.create(
            nha_may=other_factory, ma_khu_vuc="H3", ten_khu_vuc="Tổ máy H3"
        )
        response = self.client.post(
            reverse("nhatkyvanhanh:mauchuyendoithietbi-list"),
            {
                "nha_may": self.nha_may.id,
                "khu_vuc": foreign_area.id,
                "thiet_bi": self.tb1.id,
                "nhom_thiet_bi": "Kiểm tra",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Khu vực không thuộc nhà máy", str(response.data))

    def test_used_area_cannot_be_deleted(self):
        self.client.force_authenticate(user=self.manager)
        url = reverse(
            "nhatkyvanhanh:khuvucchuyendoithietbi-detail",
            args=[self.khu_vuc_h1.id],
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(KhuVucChuyenDoiThietBi.objects.filter(id=self.khu_vuc_h1.id).exists())

    def test_create_duplicate_weekly_log_returns_clear_validation_error(self):
        self.client.force_authenticate(user=self.creator)
        url = reverse("nhatkyvanhanh:sochuyendoithietbituan-list")
        other_factory = NhaMay.objects.create(
            ma_nha_may="VS",
            ten_nha_may="Vinh Son",
        )
        payload = {
            "nam": 2026,
            "tuan": 35,
            "ca_truc": "A",
            "nha_may": self.nha_may.id,
        }

        first_response = self.client.post(url, payload, format="json")
        duplicate_payload = {**payload, "nha_may": other_factory.id}
        duplicate_response = self.client.post(url, duplicate_payload, format="json")

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("đã tồn tại", str(duplicate_response.data))

    def test_weekly_switch_log_workflow_and_locking(self):
        # 1. Creator creates weekly switch log
        self.client.force_authenticate(user=self.creator)
        url_so = reverse("nhatkyvanhanh:sochuyendoithietbituan-list")
        create_so_res = self.client.post(
            url_so,
            {
                "nam": 2026,
                "tuan": 35,
                "ca_truc": "A",
                "nha_may": self.nha_may.id,
            },
            format="json",
        )
        self.assertEqual(create_so_res.status_code, status.HTTP_201_CREATED)
        so_id = create_so_res.data["id"]
        so = SoChuyenDoiThietBiTuan.objects.get(id=so_id)

        # Verify initial state: CHO_DUYET and not locked
        self.assertEqual(so.trang_thai, SoChuyenDoiThietBiTuan.TrangThai.CHO_DUYET)
        self.assertFalse(so.da_khoa)
        self.assertEqual(so.chu_ky_nguoi_tao, "signatures/creator_cd.png")

        # 2. Creator creates switch run (LanChuyenDoiThietBi)
        url_tao_lan = reverse("nhatkyvanhanh:sochuyendoithietbituan-tao-lan-chuyen-doi", kwargs={"pk": so_id})
        thoi_gian_trong_tuan = timezone.make_aware(
            datetime.combine(so.tuan_bat_dau, time(hour=8))
        )
        lan_res = self.client.post(
            url_tao_lan,
            {
                "thoi_gian": thoi_gian_trong_tuan.isoformat(),
                "ghi_chu_chung": "Chuyen doi thiet bi dinh ky dau tuan",
            },
            format="json",
        )
        self.assertEqual(lan_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(so.lan_chuyen_dois.count(), 1)
        lan = so.lan_chuyen_dois.first()
        self.assertEqual(lan.chi_tiets.count(), 2)

        # 3. Creator updates switch details
        url_update_lan = reverse(
            "nhatkyvanhanh:sochuyendoithietbituan-cap-nhat-lan-chuyen-doi",
            kwargs={"pk": so_id, "lan_id": lan.id},
        )
        ct1 = lan.chi_tiets.first()
        update_lan_res = self.client.patch(
            url_update_lan,
            {
                "chi_tiets": [
                    {
                        "id": str(ct1.id),
                        "trang_thai": "lam_viec",
                        "ghi_chu": "Bom 1 dang van hanh tot",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(update_lan_res.status_code, status.HTTP_200_OK)
        ct1.refresh_from_db()
        self.assertEqual(ct1.trang_thai, "lam_viec")

        # 4. Creator cannot self-approve their own log
        url_xac_nhan = reverse("nhatkyvanhanh:sochuyendoithietbituan-xac-nhan", kwargs={"pk": so_id})
        self_approve_res = self.client.post(url_xac_nhan, {}, format="json")
        self.assertEqual(self_approve_res.status_code, status.HTTP_403_FORBIDDEN)

        # 5. Shift leader confirms / approves and locks the logbook
        self.client.force_authenticate(user=self.shift_leader)
        approve_res = self.client.post(
            url_xac_nhan,
            {"ghi_chu_duyet": "Da kiem tra va dong y"},
            format="json",
        )
        self.assertEqual(approve_res.status_code, status.HTTP_200_OK)
        so.refresh_from_db()
        self.assertEqual(so.trang_thai, SoChuyenDoiThietBiTuan.TrangThai.DA_DUYET)
        self.assertTrue(so.da_khoa)
        self.assertEqual(so.nguoi_duyet, self.shift_leader)
        self.assertEqual(so.chu_ky_nguoi_duyet, "signatures/shift_leader.png")
        self.assertIsNotNone(so.duyet_at)

        # 6. Once locked, Creator CANNOT edit or delete the logbook
        self.client.force_authenticate(user=self.creator)
        url_detail_so = reverse("nhatkyvanhanh:sochuyendoithietbituan-detail", kwargs={"pk": so_id})
        edit_so_res = self.client.patch(
            url_detail_so,
            {"ca_truc": "B"},
            format="json",
        )
        self.assertEqual(edit_so_res.status_code, status.HTTP_403_FORBIDDEN)

        delete_so_res = self.client.delete(url_detail_so)
        self.assertEqual(delete_so_res.status_code, status.HTTP_403_FORBIDDEN)

        # 7. Once locked, Creator CANNOT edit or delete the switch runs
        edit_lan_locked_res = self.client.patch(
            url_update_lan,
            {
                "chi_tiets": [
                    {
                        "id": str(ct1.id),
                        "trang_thai": "du_phong",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(edit_lan_locked_res.status_code, status.HTTP_403_FORBIDDEN)

        delete_lan_locked_res = self.client.delete(url_update_lan)
        self.assertEqual(delete_lan_locked_res.status_code, status.HTTP_403_FORBIDDEN)

        # 8. Manager / Superuser unlocks the logbook
        self.client.force_authenticate(user=self.manager)
        url_huy_xac_nhan = reverse("nhatkyvanhanh:sochuyendoithietbituan-huy-xac-nhan", kwargs={"pk": so_id})
        unlock_res = self.client.post(url_huy_xac_nhan, {}, format="json")
        self.assertEqual(unlock_res.status_code, status.HTTP_200_OK)
        so.refresh_from_db()
        self.assertEqual(so.trang_thai, SoChuyenDoiThietBiTuan.TrangThai.CHO_DUYET)
        self.assertFalse(so.da_khoa)
        self.assertIsNone(so.nguoi_duyet)

        # 9. Now Creator can edit again
        self.client.force_authenticate(user=self.creator)
        edit_again_res = self.client.patch(
            url_detail_so,
            {"ca_truc": "B"},
            format="json",
        )
        self.assertEqual(edit_again_res.status_code, status.HTTP_200_OK)
        so.refresh_from_db()
        self.assertEqual(so.ca_truc, "B")

    def test_complementary_pump_pair_rejects_duplicate_statuses(self):
        so = SoChuyenDoiThietBiTuan.objects.create(
            nha_may=self.nha_may,
            nam=2026,
            tuan=36,
            ca_truc="A",
            nguoi_tao=self.creator,
        )
        lan = LanChuyenDoiThietBi.objects.create(
            so=so,
            thoi_gian=timezone.make_aware(
                datetime.combine(so.tuan_bat_dau, time(hour=8))
            ),
            nguoi_thuc_hien=self.creator,
        )
        rows = [
            ChiTietChuyenDoiThietBi.objects.create(
                lan_chuyen_doi=lan,
                thiet_bi=device,
                khu_vuc=self.khu_vuc_h1,
                to_may="H1",
                ten_khu_vuc_snapshot="Tổ máy H1",
                nhom_thiet_bi="Bơm nước làm mát",
            )
            for device in (self.tb1, self.tb2)
        ]
        url = reverse(
            "nhatkyvanhanh:sochuyendoithietbituan-cap-nhat-lan-chuyen-doi",
            kwargs={"pk": so.pk, "lan_id": lan.pk},
        )
        self.client.force_authenticate(user=self.creator)

        invalid_response = self.client.patch(
            url,
            {
                "chi_tiets": [
                    {"id": str(row.pk), "trang_thai": "lam_viec"}
                    for row in rows
                ]
            },
            format="json",
        )

        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            invalid_response.data["code"],
            "invalid_complementary_pair",
        )
        self.assertIn("một thiết bị Làm việc", invalid_response.data["detail"])

        self.client.force_authenticate(user=self.shift_leader)
        approve_response = self.client.post(
            reverse(
                "nhatkyvanhanh:sochuyendoithietbituan-xac-nhan",
                kwargs={"pk": so.pk},
            ),
            {},
            format="json",
        )
        self.assertEqual(approve_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            approve_response.data["code"],
            "invalid_complementary_pair",
        )

        self.client.force_authenticate(user=self.creator)
        valid_response = self.client.patch(
            url,
            {
                "chi_tiets": [
                    {"id": str(rows[0].pk), "trang_thai": "lam_viec"},
                    {"id": str(rows[1].pk), "trang_thai": "du_phong"},
                ]
            },
            format="json",
        )

        self.assertEqual(valid_response.status_code, status.HTTP_200_OK)
        rows[0].refresh_from_db()
        rows[1].refresh_from_db()
        self.assertEqual(
            {rows[0].trang_thai, rows[1].trang_thai},
            {"lam_viec", "du_phong"},
        )
