from datetime import date
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import UserProfile
from tochuc.models import NhaMay
from quanlyvanhanh.models import ThietBi
from nhatkyvanhanh.models import (
    MauChuyenDoiTBThang,
    SoChuyenDoiTBThang,
    ChiTietChuyenDoiTBThang,
)

User = get_user_model()


class ChuyenDoiTBThangTests(APITestCase):
    def setUp(self):
        # 1. Tao Nha may
        self.nha_may = NhaMay.objects.create(
            ma_nha_may="SH",
            ten_nha_may="Song Hinh",
        )

        # 2. Tao Thiet bi
        self.tb1 = ThietBi.objects.create(
            nha_may="Sông Hinh",
            ma="SH.TB.THANG.01",
            ma_day_du="SH.TB.THANG.01",
            ten="Bom dau boi tron 1",
        )
        self.tb2 = ThietBi.objects.create(
            nha_may="Sông Hinh",
            ma="SH.TB.THANG.02",
            ma_day_du="SH.TB.THANG.02",
            ten="Bom dau boi tron 2",
        )

        # 3. Tao Users va Profiles
        self.creator = User.objects.create_user(
            email="creator_month@example.com",
            password="testpassword123!",
            username="creator_month",
        )
        self.creator_profile = UserProfile.objects.create(
            user=self.creator,
            ho_ten="Tran Van Tao Thang",
            nha_may=self.nha_may,
            chu_ky="signatures/creator_month.png",
            can_view_monthly_equipment_switch_logs=True,
            can_create_monthly_equipment_switch_logs=True,
            can_edit_own_monthly_equipment_switch_logs=True,
            can_delete_own_monthly_equipment_switch_logs=True,
        )

        self.shift_leader = User.objects.create_user(
            email="shift_leader_month@example.com",
            password="testpassword123!",
            username="shift_leader_month",
        )
        self.shift_leader_profile = UserProfile.objects.create(
            user=self.shift_leader,
            ho_ten="Pham Truong Ca Thang",
            nha_may=self.nha_may,
            chu_ky="signatures/shift_leader_month.png",
            chuc_danh="Truong ca van hanh",
            can_view_monthly_equipment_switch_logs=True,
            can_confirm_monthly_equipment_switch_logs=True,
        )

        self.manager = User.objects.create_user(
            email="manager_month@example.com",
            password="testpassword123!",
            username="manager_month",
        )
        self.manager_profile = UserProfile.objects.create(
            user=self.manager,
            ho_ten="Vu Quan Ly Thang",
            nha_may=self.nha_may,
            chu_ky="signatures/manager_month.png",
            can_manage_all_monthly_equipment_switch_logs=True,
            can_view_monthly_equipment_switch_templates=True,
            can_create_monthly_equipment_switch_templates=True,
            can_edit_monthly_equipment_switch_templates=True,
            can_delete_monthly_equipment_switch_templates=True,
        )

        self.unprivileged = User.objects.create_user(
            email="unprivileged_month@example.com",
            password="testpassword123!",
            username="unprivileged_month",
        )
        self.unprivileged_profile = UserProfile.objects.create(
            user=self.unprivileged,
            ho_ten="Nguoi khong co quyen thang",
            nha_may=self.nha_may,
            can_view_monthly_equipment_switch_templates=False,
            can_view_monthly_equipment_switch_logs=False,
        )

        # 4. Tao Mau thiet bi thang
        self.mau1 = MauChuyenDoiTBThang.objects.create(
            nha_may=self.nha_may,
            thiet_bi=self.tb1,
            ma_nhom="I",
            ten_nhom="Bom dau boi tron",
            don_vi="Lan",
            thu_tu_nhom=1,
            thu_tu=1,
            dang_su_dung=True,
        )
        self.mau2 = MauChuyenDoiTBThang.objects.create(
            nha_may=self.nha_may,
            thiet_bi=self.tb2,
            ma_nhom="I",
            ten_nhom="Bom dau boi tron",
            don_vi="Lan",
            thu_tu_nhom=1,
            thu_tu=2,
            dang_su_dung=True,
        )

    def test_mau_chuyen_doi_tb_thang_permissions(self):
        url = reverse("nhatkyvanhanh:mauchuyendoitbthang-list")

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
            ma="SH.TB.THANG.03",
            ma_day_du="SH.TB.THANG.03",
            ten="Bom cuu hoa 1",
        )
        create_res = self.client.post(
            url,
            {
                "nha_may": self.nha_may.id,
                "thiet_bi": tb3.id,
                "ma_nhom": "II",
                "ten_nhom": "Bom cuu hoa",
                "don_vi": "Lan",
                "thu_tu_nhom": 2,
                "thu_tu": 1,
                "dang_su_dung": True,
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)

    def test_create_so_with_string_factory_code(self):
        self.client.force_authenticate(user=self.creator)
        url_so = reverse("nhatkyvanhanh:sochuyendoitbthang-list")
        res = self.client.post(
            url_so,
            {
                "nam": 2026,
                "thang": 9,
                "ca_truc": "B",
                "nha_may": "song_hinh",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["nha_may"], self.nha_may.id)

    def test_monthly_switch_log_workflow_and_locking(self):
        # 1. Creator creates monthly switch log
        self.client.force_authenticate(user=self.creator)
        url_so = reverse("nhatkyvanhanh:sochuyendoitbthang-list")
        create_so_res = self.client.post(
            url_so,
            {
                "nam": 2026,
                "thang": 8,
                "ca_truc": "A",
                "nha_may": self.nha_may.id,
            },
            format="json",
        )
        self.assertEqual(create_so_res.status_code, status.HTTP_201_CREATED)
        so_id = create_so_res.data["id"]
        so = SoChuyenDoiTBThang.objects.get(id=so_id)

        # Verify initial state: CHO_DUYET and not locked
        self.assertEqual(so.trang_thai, SoChuyenDoiTBThang.TrangThai.CHO_DUYET)
        self.assertFalse(so.da_khoa)
        self.assertEqual(so.chu_ky_nguoi_tao, "signatures/creator_month.png")
        self.assertEqual(so.chi_tiets.count(), 2)

        # 2. Creator updates switch detail (cuoi_thang)
        ct1 = so.chi_tiets.first()
        url_update_ct = reverse(
            "nhatkyvanhanh:sochuyendoitbthang-cap-nhat-chi-tiet",
            kwargs={"pk": so_id, "chi_tiet_id": ct1.id},
        )
        update_ct_res = self.client.patch(
            url_update_ct,
            {
                "cuoi_thang": 15,
                "ghi_chu": "Chay tot trong thang 8",
            },
            format="json",
        )
        self.assertEqual(update_ct_res.status_code, status.HTTP_200_OK)
        ct1.refresh_from_db()
        self.assertEqual(ct1.cuoi_thang, 15)
        self.assertEqual(ct1.thuc_hien, 15)

        # 3. Creator cannot self-approve their own log
        url_xac_nhan = reverse("nhatkyvanhanh:sochuyendoitbthang-xac-nhan", kwargs={"pk": so_id})
        self_approve_res = self.client.post(url_xac_nhan, {}, format="json")
        self.assertEqual(self_approve_res.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Shift leader confirms / approves and locks the monthly logbook
        self.client.force_authenticate(user=self.shift_leader)
        approve_res = self.client.post(
            url_xac_nhan,
            {"ghi_chu_duyet": "Da kiem tra chi so thang 8 va dong y"},
            format="json",
        )
        self.assertEqual(approve_res.status_code, status.HTTP_200_OK)
        so.refresh_from_db()
        self.assertEqual(so.trang_thai, SoChuyenDoiTBThang.TrangThai.DA_DUYET)
        self.assertTrue(so.da_khoa)
        self.assertEqual(so.nguoi_duyet, self.shift_leader)
        self.assertEqual(so.chu_ky_nguoi_duyet, "signatures/shift_leader_month.png")
        self.assertIsNotNone(so.duyet_at)

        # 5. Once locked, Creator CANNOT edit or delete the logbook
        self.client.force_authenticate(user=self.creator)
        url_detail_so = reverse("nhatkyvanhanh:sochuyendoitbthang-detail", kwargs={"pk": so_id})
        edit_so_res = self.client.patch(
            url_detail_so,
            {"ca_truc": "B"},
            format="json",
        )
        self.assertEqual(edit_so_res.status_code, status.HTTP_403_FORBIDDEN)

        delete_so_res = self.client.delete(url_detail_so)
        self.assertEqual(delete_so_res.status_code, status.HTTP_403_FORBIDDEN)

        # 6. Once locked, Creator CANNOT edit or delete details
        edit_ct_locked_res = self.client.patch(
            url_update_ct,
            {"cuoi_thang": 20},
            format="json",
        )
        self.assertEqual(edit_ct_locked_res.status_code, status.HTTP_403_FORBIDDEN)

        # 7. Manager / Superuser unlocks the logbook
        self.client.force_authenticate(user=self.manager)
        url_huy_xac_nhan = reverse("nhatkyvanhanh:sochuyendoitbthang-huy-xac-nhan", kwargs={"pk": so_id})
        unlock_res = self.client.post(url_huy_xac_nhan, {}, format="json")
        self.assertEqual(unlock_res.status_code, status.HTTP_200_OK)
        so.refresh_from_db()
        self.assertEqual(so.trang_thai, SoChuyenDoiTBThang.TrangThai.CHO_DUYET)
        self.assertFalse(so.da_khoa)
        self.assertIsNone(so.nguoi_duyet)

        # 8. Now Creator can edit again
        self.client.force_authenticate(user=self.creator)
        edit_again_res = self.client.patch(
            url_detail_so,
            {"ca_truc": "B"},
            format="json",
        )
        self.assertEqual(edit_again_res.status_code, status.HTTP_200_OK)
        so.refresh_from_db()
        self.assertEqual(so.ca_truc, "B")

    def test_inheritance_of_previous_month_values_and_sync(self):
        # 1. Tao so thang 7 voi ca truc 'A'
        self.client.force_authenticate(user=self.creator)
        url_so = reverse("nhatkyvanhanh:sochuyendoitbthang-list")
        res_m7 = self.client.post(
            url_so,
            {
                "nam": 2026,
                "thang": 7,
                "ca_truc": "A",
                "nha_may": self.nha_may.id,
            },
            format="json",
        )
        self.assertEqual(res_m7.status_code, status.HTTP_201_CREATED)
        so_m7 = SoChuyenDoiTBThang.objects.get(id=res_m7.data["id"])

        # Cap nhat chi so cuoi thang 7: tb1 = 100, tb2 = 250
        ct1_m7 = so_m7.chi_tiets.get(thiet_bi=self.tb1)
        ct1_m7.cuoi_thang = 100
        ct1_m7.save()

        ct2_m7 = so_m7.chi_tiets.get(thiet_bi=self.tb2)
        ct2_m7.cuoi_thang = 250
        ct2_m7.save()

        # 2. Tao so thang 8 voi ca truc KHAC ('B')
        res_m8 = self.client.post(
            url_so,
            {
                "nam": 2026,
                "thang": 8,
                "ca_truc": "B",
                "nha_may": self.nha_may.id,
            },
            format="json",
        )
        self.assertEqual(res_m8.status_code, status.HTTP_201_CREATED)
        so_m8 = SoChuyenDoiTBThang.objects.get(id=res_m8.data["id"])

        # Kiem tra chi so dau thang 8 tu dong ke thua tu cuoi thang 7
        ct1_m8 = so_m8.chi_tiets.get(thiet_bi=self.tb1)
        ct2_m8 = so_m8.chi_tiets.get(thiet_bi=self.tb2)

        self.assertEqual(ct1_m8.dau_thang, 100)
        self.assertEqual(ct1_m8.cuoi_thang, 100)
        self.assertEqual(ct1_m8.thuc_hien, 0)

        self.assertEqual(ct2_m8.dau_thang, 250)
        self.assertEqual(ct2_m8.cuoi_thang, 250)
        self.assertEqual(ct2_m8.thuc_hien, 0)

        # Cap nhat cuoi thang 8 cua tb1 = 120 -> thuc_hien = 20
        url_update_ct1_m8 = reverse(
            "nhatkyvanhanh:sochuyendoitbthang-cap-nhat-chi-tiet",
            kwargs={"pk": so_m8.id, "chi_tiet_id": ct1_m8.id},
        )
        res_update = self.client.patch(
            url_update_ct1_m8,
            {"cuoi_thang": 120},
            format="json",
        )
        self.assertEqual(res_update.status_code, status.HTTP_200_OK)
        ct1_m8.refresh_from_db()
        self.assertEqual(ct1_m8.thuc_hien, 20)

        # 3. Kiem tra dong bo dau thang khi thang 7 duoc dieu chinh
        ct1_m7.cuoi_thang = 105
        ct1_m7.save()

        url_sync = reverse(
            "nhatkyvanhanh:sochuyendoitbthang-dong-bo-dau-thang",
            kwargs={"pk": so_m8.id},
        )
        res_sync = self.client.post(url_sync, {}, format="json")
        self.assertEqual(res_sync.status_code, status.HTTP_200_OK)

        ct1_m8.refresh_from_db()
        self.assertEqual(ct1_m8.dau_thang, 105)
        self.assertEqual(ct1_m8.cuoi_thang, 120)
        self.assertEqual(ct1_m8.thuc_hien, 15)
