from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import UserProfile
from tochuc.models import NhaMay
from quanlycatruc.models import (
    BoPhan,
    DonViToChuc,
    KipTruc,
    LichTrucCa,
    MauChuKyCaTruc,
    NgayTrucCa,
    NhanSu,
    NhomLichTruc,
    PhamViNhanSuCaTruc,
    ThanhVienKipTruc,
)

User = get_user_model()


class BienCheLichTrucHCTests(APITestCase):
    def setUp(self):
        self.plant = NhaMay.objects.create(
            ma_nha_may='SH-HC',
            ten_nha_may='Thủy điện Sông Hinh HC',
        )
        self.user = User.objects.create_user(
            email='hcleader@example.com',
            password='testpassword123!',
            username='hcleader',
        )
        UserProfile.objects.create(
            user=self.user,
            ho_ten='Trưởng ca HC',
            nha_may=self.plant,
            can_view_shift_schedule=True,
            can_view_shift_handover_logs=True,
            can_create_shift_handover_logs=True,
        )
        self.client.force_authenticate(user=self.user)

        self.unit = DonViToChuc.objects.create(
            ma_don_vi="DV-HC",
            ten_don_vi="Phòng Kỹ thuật",
            loai_don_vi="nha_may",
            nha_may=self.plant,
        )
        self.department = BoPhan.objects.create(
            don_vi=self.unit,
            ma_bo_phan="BP-HC",
            ten_bo_phan="Tổ Hành chính",
            loai_bo_phan="hanh_chinh",
        )
        self.nhom_lich = NhomLichTruc.objects.create(
            nha_may=self.plant,
            don_vi=self.unit,
            bo_phan=self.department,
            ma_nhom='HC-SH',
            ten_nhom='Lịch Hành chính SH',
        )
        self.kip_vh_a = KipTruc.objects.create(
            nhom_lich=self.nhom_lich,
            nha_may=self.plant,
            ma_kip='A',
            ten_kip='Kíp A',
            loai_kip=KipTruc.LoaiKip.VAN_HANH,
        )
        self.kip_vh_b = KipTruc.objects.create(
            nhom_lich=self.nhom_lich,
            nha_may=self.plant,
            ma_kip='B',
            ten_kip='Kíp B',
            loai_kip=KipTruc.LoaiKip.VAN_HANH,
        )
        self.kip1 = KipTruc.objects.create(
            nhom_lich=self.nhom_lich,
            nha_may=self.plant,
            ma_kip='1',
            ten_kip='Ca 1',
            loai_kip=KipTruc.LoaiKip.HANH_CHINH,
        )
        self.staff1 = NhanSu.objects.create(
            ho_ten='Nguyễn Văn A',
            don_vi=self.unit,
            bo_phan=self.department,
            dang_lam_viec=True,
        )
        PhamViNhanSuCaTruc.objects.create(
            nhom_lich=self.nhom_lich,
            nhan_su=self.staff1,
            dang_hoat_dong=True,
        )
        ThanhVienKipTruc.objects.create(
            kip_truc=self.kip1,
            nhan_su=self.staff1,
            vai_tro=ThanhVienKipTruc.VaiTro.TRUONG_CA,
            tu_ngay=date(2026, 8, 1),
            dang_hoat_dong=True,
        )

        self.template = MauChuKyCaTruc.objects.create(
            nha_may=self.plant,
            nhom_lich=self.nhom_lich,
            ten_mau="Chu kỳ chuẩn",
            ngay_moc_van_hanh=date(2026, 8, 1),
            vi_tri_moc_van_hanh=0,
            ngay_moc_hanh_chinh=date(2026, 8, 1),
            vi_tri_moc_hanh_chinh=0,
            tu_ngay=date(2026, 1, 1),
        )

        self.schedule = LichTrucCa.objects.create(
            nha_may=self.plant,
            nhom_lich=self.nhom_lich,
            mau_chu_ky=self.template,
            nguoi_tao=self.user,
            thang=8,
            nam=2026,
            phien_ban=1,
            trang_thai=LichTrucCa.TrangThai.DANG_AP_DUNG,
        )

        for day_num in range(1, 15):
            d = date(2026, 8, day_num)
            NgayTrucCa.objects.create(
                lich_truc=self.schedule,
                ngay=d,
                kip_ca_ngay=self.kip_vh_a,
                kip_ca_dem=self.kip_vh_b,
                kip_hanh_chinh=self.kip1,
                ngay_am=day_num,
                thang_am=7,
                nam_am=2026,
            )

    def test_bien_che_defaults_to_six_days_range(self):
        url = reverse('nhatkyvanhanh:sogiaonhancahc-bien-che-lich-truc')
        response = self.client.get(
            url,
            {
                'nha_may': self.plant.pk,
                'ngay_truc': '2026-08-01',
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('lua_chon', data)
        self.assertTrue(len(data['lua_chon']) > 0)
        option = data['lua_chon'][0]
        self.assertEqual(len(option['nhan_su']), 1)
        staff = option['nhan_su'][0]
        self.assertEqual(staff['ho_ten'], 'Nguyễn Văn A')
        start = timezone.datetime.fromisoformat(staff['thoi_gian_bat_dau'])
        end = timezone.datetime.fromisoformat(staff['thoi_gian_ket_thuc'])
        self.assertEqual((end - start).days, 6)