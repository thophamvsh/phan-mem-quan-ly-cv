from datetime import date, datetime
from io import BytesIO
import tempfile
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from PIL import Image
from core.models import UserProfile
from tochuc.models import NhaMay
from nhatkyvanhanh.models import (
    SoAnToanDauGio,
    SoChuyenDoiTBThang,
    SoChuyenDoiThietBiTuan,
    LanChuyenDoiThietBi,
    KhacPhucSuKien,
    SonhatkyvanhanhDiesel,
    SogiaonhancaHC,
    SogiaonhancaVH,
    ChiTietSoGiaoNhanCaHC,
    ChiTietSoGiaoNhanCaVH,
    LuuYChiDaoSoGiaoNhanCaVH,
    AnhTruocSuCo,
    SuKien,
)

User = get_user_model()


class NhatKyVanHanhAPITests(APITestCase):
    def setUp(self):
        # Create factory/nha_may first
        self.nha_may = NhaMay.objects.create(
            ma_nha_may="SH",
            ten_nha_may="Sông Hinh",
        )

        # Create users
        self.creator = User.objects.create_user(
            email="creator@example.com",
            password="testpassword123!",
            username="creator",
        )
        self.receiver = User.objects.create_user(
            email="receiver@example.com",
            password="testpassword123!",
            username="receiver",
        )
        self.unprivileged_user = User.objects.create_user(
            email="unprivileged@example.com",
            password="testpassword123!",
            username="unprivileged",
        )
        self.viewer = User.objects.create_user(
            email="viewer@example.com",
            password="testpassword123!",
            username="viewer",
        )
        self.manager = User.objects.create_user(
            email="manager@example.com",
            password="testpassword123!",
            username="manager",
        )

        # Create profiles with permissions and assigned factory
        self.creator_profile = UserProfile.objects.create(
            user=self.creator,
            ho_ten="Creator User",
            chu_ky="signatures/creator.png",
            nha_may=self.nha_may,
            can_view_shift_handover_logs=True,
            can_create_shift_handover_logs=True,
            can_edit_own_shift_handover_logs=True,
            can_delete_own_shift_handover_logs=True,
            can_view_operation_events=True,
            can_create_operation_events=True,
            can_edit_own_operation_events=True,
        )
        self.receiver_profile = UserProfile.objects.create(
            user=self.receiver,
            ho_ten="Receiver User",
            chu_ky="signatures/receiver.png",
            nha_may=self.nha_may,
            can_view_shift_handover_logs=True,
            can_receive_shift_handover_logs=True,
        )
        self.unprivileged_profile = UserProfile.objects.create(
            user=self.unprivileged_user,
            ho_ten="Unprivileged User",
            nha_may=self.nha_may,
            can_view_shift_handover_logs=False,
            can_create_shift_handover_logs=False,
            can_view_operation_events=False,
        )
        self.viewer_profile = UserProfile.objects.create(
            user=self.viewer,
            ho_ten="View Only User",
            nha_may=self.nha_may,
            can_view_shift_handover_logs=True,
            can_create_shift_handover_logs=False,
            can_edit_shift_handover_logs=False,
            can_delete_shift_handover_logs=False,
            can_view_operation_events=True,
            can_edit_own_operation_events=False,
            can_edit_all_operation_events=False,
            can_delete_own_operation_events=False,
            can_delete_all_operation_events=False,
        )
        self.manager_profile = UserProfile.objects.create(
            user=self.manager,
            ho_ten="Manager User",
            nha_may=self.nha_may,
            can_view_operation_events=True,
            can_edit_all_operation_events=True,
            can_delete_all_operation_events=True,
            can_view_shift_handover_logs=True,
            can_manage_all_shift_handover_logs=True,
        )

    def test_nhatkysukien_list_permissions(self):
        url = reverse("nhatkyvanhanh:nhatkysukien-list")

        # 1. Anonymous user should be unauthorized
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Unprivileged user should be forbidden
        self.client.force_authenticate(user=self.unprivileged_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Privileged user should succeed
        self.client.force_authenticate(user=self.creator)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_so_an_toan_create_requires_dedicated_create_permission(self):
        url = reverse("nhatkyvanhanh:soantoadaugio-list")
        payload = {
            "ngay_dong_bo": "2026-08-23",
            "ca_truc": "ca_ngay",
            "tinh_trang_an_toan": "An toan",
        }

        self.viewer_profile.can_view_so_an_toan_dau_gio = True
        self.viewer_profile.can_create_so_an_toan_dau_gio = False
        self.viewer_profile.save()
        self.client.force_authenticate(user=self.viewer)

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.viewer_profile.can_create_so_an_toan_dau_gio = True
        self.viewer_profile.save()
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["nguoi_dong_bo"], self.viewer.id)
        self.assertEqual(response.data["nha_may"], self.nha_may.id)

    def test_so_an_toan_edit_requires_owner_permission_or_manage_all(self):
        item = SoAnToanDauGio.objects.create(
            nha_may=self.nha_may,
            ngay_dong_bo=date(2026, 8, 23),
            ca_truc="ca_ngay",
            tinh_trang_an_toan="Ban dau",
            nguoi_dong_bo=self.creator,
        )
        url = reverse("nhatkyvanhanh:soantoadaugio-detail", args=[item.id])

        self.client.force_authenticate(user=self.creator)
        response = self.client.patch(url, {"tinh_trang_an_toan": "Lan 1"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.creator_profile.can_edit_own_so_an_toan_dau_gio = True
        self.creator_profile.save()
        response = self.client.patch(url, {"tinh_trang_an_toan": "Chu so sua"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.viewer_profile.can_edit_own_so_an_toan_dau_gio = True
        self.viewer_profile.save()
        self.client.force_authenticate(user=self.viewer)
        response = self.client.patch(url, {"tinh_trang_an_toan": "Nguoi khac sua"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.manager_profile.can_manage_all_so_an_toan_dau_gio = True
        self.manager_profile.save()
        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(url, {"tinh_trang_an_toan": "Quan ly sua"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_so_an_toan_delete_requires_owner_permission_or_manage_all(self):
        owner_item = SoAnToanDauGio.objects.create(
            nha_may=self.nha_may,
            ngay_dong_bo=date(2026, 8, 23),
            ca_truc="ca_dem",
            nguoi_dong_bo=self.creator,
        )
        owner_url = reverse(
            "nhatkyvanhanh:soantoadaugio-detail",
            args=[owner_item.id],
        )

        self.viewer_profile.can_delete_own_so_an_toan_dau_gio = True
        self.viewer_profile.save()
        self.client.force_authenticate(user=self.viewer)
        response = self.client.delete(owner_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.creator_profile.can_delete_own_so_an_toan_dau_gio = True
        self.creator_profile.save()
        self.client.force_authenticate(user=self.creator)
        response = self.client.delete(owner_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        managed_item = SoAnToanDauGio.objects.create(
            nha_may=self.nha_may,
            ngay_dong_bo=date(2026, 8, 24),
            ca_truc="ca_ngay",
            nguoi_dong_bo=self.creator,
        )
        managed_url = reverse(
            "nhatkyvanhanh:soantoadaugio-detail",
            args=[managed_item.id],
        )
        self.manager_profile.can_manage_all_so_an_toan_dau_gio = True
        self.manager_profile.save()
        self.client.force_authenticate(user=self.manager)
        response = self.client.delete(managed_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_diesel_edit_requires_owner_permission_or_manage_all(self):
        item = SonhatkyvanhanhDiesel.objects.create(
            nha_may=self.nha_may,
            thoi_gian=timezone.now(),
            noi_dung="Ban dau",
            nguoi_tao=self.creator,
        )
        url = reverse(
            "nhatkyvanhanh:sonhatkyvanhanhdiesel-detail",
            args=[item.id],
        )

        self.creator_profile.can_edit_own_diesel_operation_logbooks = True
        self.creator_profile.save()
        self.client.force_authenticate(user=self.creator)
        response = self.client.patch(url, {"noi_dung": "Chu so sua"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.viewer_profile.can_edit_own_diesel_operation_logbooks = True
        self.viewer_profile.save()
        self.client.force_authenticate(user=self.viewer)
        response = self.client.patch(url, {"noi_dung": "Nguoi khac sua"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.manager_profile.can_manage_all_diesel_operation_logbooks = True
        self.manager_profile.save()
        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(url, {"noi_dung": "Quan ly sua"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_diesel_delete_requires_owner_permission_or_manage_all(self):
        owner_item = SonhatkyvanhanhDiesel.objects.create(
            nha_may=self.nha_may,
            thoi_gian=timezone.now(),
            nguoi_tao=self.creator,
        )
        owner_url = reverse(
            "nhatkyvanhanh:sonhatkyvanhanhdiesel-detail",
            args=[owner_item.id],
        )

        self.viewer_profile.can_delete_own_diesel_operation_logbooks = True
        self.viewer_profile.save()
        self.client.force_authenticate(user=self.viewer)
        response = self.client.delete(owner_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.creator_profile.can_delete_own_diesel_operation_logbooks = True
        self.creator_profile.save()
        self.client.force_authenticate(user=self.creator)
        response = self.client.delete(owner_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        managed_item = SonhatkyvanhanhDiesel.objects.create(
            nha_may=self.nha_may,
            thoi_gian=timezone.now(),
            nguoi_tao=self.creator,
        )
        managed_url = reverse(
            "nhatkyvanhanh:sonhatkyvanhanhdiesel-detail",
            args=[managed_item.id],
        )
        self.manager_profile.can_manage_all_diesel_operation_logbooks = True
        self.manager_profile.save()
        self.client.force_authenticate(user=self.manager)
        response = self.client.delete(managed_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        superuser = User.objects.create_superuser(
            email="super@example.com",
            password="testpassword123!",
            username="superuser",
        )
        super_item = SonhatkyvanhanhDiesel.objects.create(
            nha_may=self.nha_may,
            thoi_gian=timezone.now(),
            nguoi_tao=self.creator,
        )
        super_url = reverse(
            "nhatkyvanhanh:sonhatkyvanhanhdiesel-detail",
            args=[super_item.id],
        )
        self.client.force_authenticate(user=superuser)
        response = self.client.delete(super_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_weekly_switch_edit_requires_owner_permission_or_manage_all(self):
        item = SoChuyenDoiThietBiTuan.objects.create(
            nha_may=self.nha_may,
            nam=2026,
            tuan=35,
            ca_truc="A",
            nguoi_tao=self.creator,
        )
        url = reverse(
            "nhatkyvanhanh:sochuyendoithietbituan-detail",
            args=[item.id],
        )

        self.client.force_authenticate(user=self.creator)
        response = self.client.patch(url, {"ca_truc": "B"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.creator_profile.can_edit_own_weekly_equipment_switch_logs = True
        self.creator_profile.save()
        response = self.client.patch(url, {"ca_truc": "B"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.viewer_profile.can_edit_own_weekly_equipment_switch_logs = True
        self.viewer_profile.save()
        self.client.force_authenticate(user=self.viewer)
        response = self.client.patch(url, {"ca_truc": "C"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.manager_profile.can_manage_all_weekly_equipment_switch_logs = True
        self.manager_profile.save()
        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(url, {"ca_truc": "C"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_weekly_switch_delete_requires_owner_permission_or_manage_all(self):
        owner_item = SoChuyenDoiThietBiTuan.objects.create(
            nha_may=self.nha_may,
            nam=2026,
            tuan=36,
            ca_truc="A",
            nguoi_tao=self.creator,
        )
        owner_url = reverse(
            "nhatkyvanhanh:sochuyendoithietbituan-detail",
            args=[owner_item.id],
        )

        self.client.force_authenticate(user=self.creator)
        response = self.client.delete(owner_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.viewer_profile.can_delete_own_weekly_equipment_switch_logs = True
        self.viewer_profile.save()
        self.client.force_authenticate(user=self.viewer)
        response = self.client.delete(owner_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.creator_profile.can_delete_own_weekly_equipment_switch_logs = True
        self.creator_profile.save()
        self.client.force_authenticate(user=self.creator)
        response = self.client.delete(owner_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        managed_item = SoChuyenDoiThietBiTuan.objects.create(
            nha_may=self.nha_may,
            nam=2026,
            tuan=37,
            ca_truc="A",
            nguoi_tao=self.creator,
        )
        managed_url = reverse(
            "nhatkyvanhanh:sochuyendoithietbituan-detail",
            args=[managed_item.id],
        )
        self.manager_profile.can_manage_all_weekly_equipment_switch_logs = True
        self.manager_profile.save()
        self.client.force_authenticate(user=self.manager)
        response = self.client.delete(managed_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_weekly_switch_entry_requires_executor_permission_or_manage_all(self):
        item = SoChuyenDoiThietBiTuan.objects.create(
            nha_may=self.nha_may,
            nam=2026,
            tuan=35,
            ca_truc="D",
            nguoi_tao=self.creator,
        )
        entry = LanChuyenDoiThietBi.objects.create(
            so=item,
            thoi_gian=timezone.make_aware(datetime(2026, 8, 24, 8, 0)),
            nguoi_thuc_hien=self.creator,
        )
        url = reverse(
            "nhatkyvanhanh:sochuyendoithietbituan-cap-nhat-lan-chuyen-doi",
            args=[item.id, entry.id],
        )

        self.creator_profile.can_edit_own_weekly_equipment_switch_logs = True
        self.creator_profile.save()
        self.client.force_authenticate(user=self.creator)
        response = self.client.patch(
            url,
            {"ghi_chu_chung": "Nguoi thuc hien sua"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.viewer_profile.can_edit_own_weekly_equipment_switch_logs = True
        self.viewer_profile.save()
        self.client.force_authenticate(user=self.viewer)
        response = self.client.patch(
            url,
            {"ghi_chu_chung": "Nguoi khac sua"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.manager_profile.can_manage_all_weekly_equipment_switch_logs = True
        self.manager_profile.save()
        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            url,
            {"ghi_chu_chung": "Quan ly sua"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.viewer_profile.can_delete_own_weekly_equipment_switch_logs = True
        self.viewer_profile.save()
        self.client.force_authenticate(user=self.viewer)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.creator_profile.can_delete_own_weekly_equipment_switch_logs = True
        self.creator_profile.save()
        self.client.force_authenticate(user=self.creator)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_monthly_switch_edit_requires_owner_permission_or_manage_all(self):
        item = SoChuyenDoiTBThang.objects.create(
            nha_may=self.nha_may,
            nam=2026,
            thang=9,
            ca_truc="A",
            nguoi_tao=self.creator,
        )
        url = reverse(
            "nhatkyvanhanh:sochuyendoitbthang-detail",
            args=[item.id],
        )

        self.client.force_authenticate(user=self.creator)
        response = self.client.patch(url, {"ca_truc": "B"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.creator_profile.can_edit_own_monthly_equipment_switch_logs = True
        self.creator_profile.save()
        response = self.client.patch(url, {"ca_truc": "B"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.viewer_profile.can_edit_own_monthly_equipment_switch_logs = True
        self.viewer_profile.save()
        self.client.force_authenticate(user=self.viewer)
        response = self.client.patch(url, {"ca_truc": "C"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.manager_profile.can_manage_all_monthly_equipment_switch_logs = True
        self.manager_profile.save()
        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(url, {"ca_truc": "C"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_monthly_switch_delete_requires_owner_permission_or_manage_all(self):
        item = SoChuyenDoiTBThang.objects.create(
            nha_may=self.nha_may,
            nam=2026,
            thang=10,
            ca_truc="A",
            nguoi_tao=self.creator,
        )
        url = reverse(
            "nhatkyvanhanh:sochuyendoitbthang-detail",
            args=[item.id],
        )

        self.viewer_profile.can_delete_own_monthly_equipment_switch_logs = True
        self.viewer_profile.save()
        self.client.force_authenticate(user=self.viewer)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.creator_profile.can_delete_own_monthly_equipment_switch_logs = True
        self.creator_profile.save()
        self.client.force_authenticate(user=self.creator)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_nhatkysukien_rejects_unsupported_image_format(self):
        self.client.force_authenticate(user=self.creator)
        response = self.client.post(
            reverse("nhatkyvanhanh:nhatkysukien-list"),
            {
                "thoi_gian_xay_ra": timezone.now().isoformat(),
                "ten_he_thong_thiet_bi": "H1",
                "hien_tuong_dien_bien": "Test event",
                "hinh_anh_truoc_su_co": SimpleUploadedFile(
                    "fake.gif", b"GIF89a-not-an-image", content_type="image/gif"
                ),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("hinh_anh_truoc_su_co", response.data)

    def test_nhatkysukien_accepts_valid_jpeg(self):
        image_buffer = BytesIO()
        Image.new("RGB", (20, 20), "white").save(image_buffer, format="JPEG")
        self.client.force_authenticate(user=self.creator)
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse("nhatkyvanhanh:nhatkysukien-list"),
                {
                    "thoi_gian_xay_ra": timezone.now().isoformat(),
                    "ten_he_thong_thiet_bi": "H1",
                    "hien_tuong_dien_bien": "Test event",
                    "hinh_anh_truoc_su_co": SimpleUploadedFile(
                        "event.jpg", image_buffer.getvalue(), content_type="image/jpeg"
                    ),
                },
                format="multipart",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_nhatkysukien_accepts_multiple_before_images(self):
        uploads = []
        for index in range(2):
            image_buffer = BytesIO()
            Image.new("RGB", (20, 20), "white").save(image_buffer, format="JPEG")
            uploads.append(
                SimpleUploadedFile(
                    f"event-{index}.jpg",
                    image_buffer.getvalue(),
                    content_type="image/jpeg",
                )
            )
        self.client.force_authenticate(user=self.creator)
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse("nhatkyvanhanh:nhatkysukien-list"),
                {
                    "thoi_gian_xay_ra": timezone.now().isoformat(),
                    "ten_he_thong_thiet_bi": "H1",
                    "hien_tuong_dien_bien": "Multiple images",
                    "hinh_anh_truoc_su_co_moi": uploads,
                },
                format="multipart",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["hinh_anh_truoc_su_co_urls"]), 2)
        self.assertEqual(len(response.data["hinh_anh_truoc_su_co_items"]), 2)
        self.assertTrue(all(item["id"] for item in response.data["hinh_anh_truoc_su_co_items"]))

    def test_nhatkysukien_creator_can_delete_before_image(self):
        event = SuKien.objects.create(
            nha_may=self.nha_may,
            thoi_gian_xay_ra=timezone.now(),
            ten_he_thong_thiet_bi="H1",
            hien_tuong_dien_bien="Test event",
            nguoi_tao=self.creator,
        )
        image_buffer = BytesIO()
        Image.new("RGB", (20, 20), "white").save(image_buffer, format="JPEG")
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            image = AnhTruocSuCo.objects.create(
                su_kien=event,
                hinh_anh=SimpleUploadedFile(
                    "event.jpg", image_buffer.getvalue(), content_type="image/jpeg"
                ),
            )
            url = reverse(
                "nhatkyvanhanh:nhatkysukien-xoa-anh-truoc-su-co",
                kwargs={"pk": event.id, "image_id": image.id},
            )
            self.client.force_authenticate(user=self.creator)
            response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(AnhTruocSuCo.objects.filter(pk=image.id).exists())
        self.assertEqual(response.data["hinh_anh_truoc_su_co_items"], [])

    def test_nhatkysukien_other_user_cannot_delete_before_image(self):
        event = SuKien.objects.create(
            nha_may=self.nha_may,
            thoi_gian_xay_ra=timezone.now(),
            ten_he_thong_thiet_bi="H1",
            hien_tuong_dien_bien="Test event",
            nguoi_tao=self.creator,
        )
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            image = AnhTruocSuCo.objects.create(
                su_kien=event,
                hinh_anh=SimpleUploadedFile(
                    "event.jpg", b"test", content_type="image/jpeg"
                ),
            )
            url = reverse(
                "nhatkyvanhanh:nhatkysukien-xoa-anh-truoc-su-co",
                kwargs={"pk": event.id, "image_id": image.id},
            )
            self.client.force_authenticate(user=self.viewer)
            response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(AnhTruocSuCo.objects.filter(pk=image.id).exists())

    def test_nhatkysukien_viewer_cannot_update_or_delete(self):
        event = SuKien.objects.create(
            nha_may=self.nha_may,
            thoi_gian_xay_ra=timezone.now(),
            ten_he_thong_thiet_bi="H1",
            hien_tuong_dien_bien="Test event",
            nguoi_tao=self.creator,
        )
        detail_url = reverse("nhatkyvanhanh:nhatkysukien-detail", kwargs={"pk": event.id})

        self.client.force_authenticate(user=self.viewer)
        patch_response = self.client.patch(
            detail_url,
            {"hien_tuong_dien_bien": "Updated by viewer"},
            format="json",
        )
        delete_response = self.client.delete(detail_url)

        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_nhatkysukien_creator_can_update_before_acknowledged(self):
        event = SuKien.objects.create(
            nha_may=self.nha_may,
            thoi_gian_xay_ra=timezone.now(),
            ten_he_thong_thiet_bi="H1",
            hien_tuong_dien_bien="Test event",
            nguoi_tao=self.creator,
        )
        detail_url = reverse("nhatkyvanhanh:nhatkysukien-detail", kwargs={"pk": event.id})

        self.client.force_authenticate(user=self.creator)
        response = self.client.patch(
            detail_url,
            {"hien_tuong_dien_bien": "Updated by creator"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["hien_tuong_dien_bien"], "Updated by creator")

    def test_nhatkysukien_creator_cannot_update_after_acknowledged(self):
        event = SuKien.objects.create(
            nha_may=self.nha_may,
            thoi_gian_xay_ra=timezone.now(),
            ten_he_thong_thiet_bi="H1",
            hien_tuong_dien_bien="Test event",
            nguoi_tao=self.creator,
            ben_ghi_nhan_su_kien=self.receiver,
        )
        detail_url = reverse("nhatkyvanhanh:nhatkysukien-detail", kwargs={"pk": event.id})

        self.client.force_authenticate(user=self.creator)
        response = self.client.patch(
            detail_url,
            {"hien_tuong_dien_bien": "Updated after acknowledged"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_nhatkysukien_creator_cannot_update_after_completed(self):
        event = SuKien.objects.create(
            nha_may=self.nha_may,
            thoi_gian_xay_ra=timezone.now(),
            ten_he_thong_thiet_bi="H1",
            hien_tuong_dien_bien="Test event",
            nguoi_tao=self.creator,
            ben_ghi_nhan_su_kien=self.receiver,
            trang_thai=SuKien.TrangThaiXuLy.XU_LY_XONG,
        )
        detail_url = reverse("nhatkyvanhanh:nhatkysukien-detail", kwargs={"pk": event.id})

        self.client.force_authenticate(user=self.creator)
        response = self.client.patch(
            detail_url,
            {"hien_tuong_dien_bien": "Updated after completed"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_nhatkysukien_other_user_with_edit_all_can_update_open_event(self):
        event = SuKien.objects.create(
            nha_may=self.nha_may,
            thoi_gian_xay_ra=timezone.now(),
            ten_he_thong_thiet_bi="H1",
            hien_tuong_dien_bien="Test event",
            nguoi_tao=self.creator,
        )
        detail_url = reverse("nhatkyvanhanh:nhatkysukien-detail", kwargs={"pk": event.id})

        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            detail_url,
            {"hien_tuong_dien_bien": "Updated by manager"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["hien_tuong_dien_bien"], "Updated by manager")

    def test_nhatkysukien_edit_all_cannot_update_acknowledged_event(self):
        event = SuKien.objects.create(
            nha_may=self.nha_may,
            thoi_gian_xay_ra=timezone.now(),
            ten_he_thong_thiet_bi="H1",
            hien_tuong_dien_bien="Test event",
            nguoi_tao=self.creator,
            ben_ghi_nhan_su_kien=self.receiver,
        )
        detail_url = reverse(
            "nhatkyvanhanh:nhatkysukien-detail",
            kwargs={"pk": event.id},
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            detail_url,
            {"hien_tuong_dien_bien": "Must remain locked"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_nhatkysukien_delete_all_cannot_delete_fully_signed_event(self):
        event = SuKien.objects.create(
            nha_may=self.nha_may,
            thoi_gian_xay_ra=timezone.now(),
            ten_he_thong_thiet_bi="H1",
            hien_tuong_dien_bien="Signed event",
            nguoi_tao=self.creator,
            ben_ghi_nhan_su_kien=self.receiver,
            chu_ky_ben_ghi_nhan_su_kien="signatures/receiver.png",
            trang_thai=SuKien.TrangThaiXuLy.XU_LY_XONG,
        )
        KhacPhucSuKien.objects.create(
            su_kien=event,
            nguoi_tao=self.manager,
            ben_xu_ly_su_kien_thiet_bi=self.manager,
            chu_ky_ben_xu_ly_su_kien_thiet_bi="signatures/manager.png",
        )
        detail_url = reverse(
            "nhatkyvanhanh:nhatkysukien-detail",
            kwargs={"pk": event.id},
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.delete(detail_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(SuKien.objects.filter(pk=event.pk).exists())

    def test_sogiaonhancavh_shift_handover_flow(self):
        # 1. Create a shift handover log as self.creator
        self.client.force_authenticate(user=self.creator)
        create_url = reverse("nhatkyvanhanh:sogiaonhancavh-list")
        data = {
            "ngay_truc": str(date.today()),
            "ca_truc": "A",
            "dia_diem": "Phòng điều khiển trung tâm",
            "thoi_gian_giao_ca": timezone.now().isoformat(),
            "nha_may": self.nha_may.id,
        }
        response = self.client.post(create_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        so_id = response.data["id"]

        # 2. Try to sign shift log as self.receiver (should succeed to receive the shift)
        self.client.force_authenticate(user=self.receiver)
        ky_nhan_url = reverse("nhatkyvanhanh:sogiaonhancavh-ky-nhan-ca", kwargs={"pk": so_id})
        response = self.client.post(ky_nhan_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["nhan_ca_ky_at"])
        self.assertEqual(response.data["user_nhan_ca"], self.receiver.id)

        # 3. Try to finalize the handover (ky_giao_ca) as self.creator
        self.client.force_authenticate(user=self.creator)
        ky_giao_url = reverse("nhatkyvanhanh:sogiaonhancavh-ky-giao-ca", kwargs={"pk": so_id})
        response = self.client.post(ky_giao_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["giao_ca_ky_at"])
        self.assertEqual(response.data["trang_thai"], SogiaonhancaVH.TrangThai.HOAN_THANH)

    def test_sogiaonhancahc_duplicate_factory_date_returns_400(self):
        self.creator_profile.can_create_admin_shift_handover_logs = True
        self.creator_profile.save(update_fields=["can_create_admin_shift_handover_logs"])
        SogiaonhancaHC.objects.create(
            nha_may=self.nha_may,
            ngay_truc=date.today(),
            thoi_gian_giao_ca=timezone.now(),
            user_giao_ca=self.creator,
            nguoi_tao=self.creator,
        )
        self.client.force_authenticate(user=self.creator)

        response = self.client.post(
            reverse("nhatkyvanhanh:sogiaonhancahc-list"),
            {
                "ngay_truc": str(date.today()),
                "thoi_gian_giao_ca": timezone.now().isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ngay_truc", response.data)

    def test_sogiaonhancahc_overlap_filter_finds_both_logs_on_handover_day(self):
        self.creator_profile.can_view_admin_shift_handover_logs = True
        self.creator_profile.save(update_fields=["can_view_admin_shift_handover_logs"])
        admin_start = timezone.make_aware(datetime(2026, 8, 28, 11, 30))
        admin_end = timezone.make_aware(datetime(2026, 8, 31, 11, 30))
        admin_log = SogiaonhancaHC.objects.create(
            nha_may=self.nha_may,
            ngay_truc=admin_start.date(),
            nguoi_truc="Nhân sự hành chính",
            thoi_gian_bat_dau_ca=admin_start,
            thoi_gian_giao_ca=admin_end,
            user_giao_ca=self.creator,
            nguoi_tao=self.creator,
        )
        next_admin_log = SogiaonhancaHC.objects.create(
            nha_may=self.nha_may,
            ngay_truc=date(2026, 8, 31),
            nguoi_truc="Nhân sự hành chính ca sau",
            thoi_gian_bat_dau_ca=admin_end,
            thoi_gian_giao_ca=timezone.make_aware(datetime(2026, 9, 3, 11, 30)),
            user_giao_ca=self.creator,
            nguoi_tao=self.creator,
        )
        self.client.force_authenticate(user=self.creator)

        response = self.client.get(
            reverse("nhatkyvanhanh:sogiaonhancahc-list"),
            {
                "nha_may": self.nha_may.id,
                "thoi_gian_chong_lan_tu": timezone.make_aware(
                    datetime(2026, 8, 31, 8, 0)
                ).isoformat(),
                "thoi_gian_chong_lan_den": timezone.make_aware(
                    datetime(2026, 8, 31, 20, 0)
                ).isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(
            {item["id"] for item in response.data["results"]},
            {str(admin_log.id), str(next_admin_log.id)},
        )

    def test_sogiaonhancavh_uses_admin_shift_staff_only_when_explicitly_selected(self):
        shift_start = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
        shift_end = shift_start.replace(hour=17)
        admin_log = SogiaonhancaHC.objects.create(
            nha_may=self.nha_may,
            ngay_truc=shift_start.date(),
            nguoi_truc="Nhân sự hành chính",
            thoi_gian_bat_dau_ca=shift_start,
            thoi_gian_giao_ca=shift_end,
            user_giao_ca=self.creator,
            nguoi_tao=self.creator,
        )
        self.client.force_authenticate(user=self.creator)
        url = reverse("nhatkyvanhanh:sogiaonhancavh-list")

        response = self.client.post(
            url,
            {
                "nha_may": self.nha_may.id,
                "ngay_truc": str(shift_start.date()),
                "ca_truc": "A",
                "loai_thoi_gian_truc": "ngay",
                "thoi_gian_bat_dau_ca": shift_start.isoformat(),
                "thoi_gian_giao_ca": shift_end.isoformat(),
                "truc_ktvh": "Nhân sự hành chính",
                "so_giao_nhan_ca_hc_nguon": admin_log.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        shift_log = SogiaonhancaVH.objects.get(pk=response.data["id"])
        self.assertEqual(shift_log.so_giao_nhan_ca_hc_nguon, admin_log)
        self.assertEqual(shift_log.truc_ktvh, "Nhân sự hành chính")
        self.assertIsNotNone(shift_log.dong_bo_truc_ktvh_at)

        without_selection = self.client.post(
            url,
            {
                "nha_may": self.nha_may.id,
                "ngay_truc": str(shift_start.date()),
                "ca_truc": "B",
                "loai_thoi_gian_truc": "ngay",
                "thoi_gian_bat_dau_ca": shift_start.isoformat(),
                "thoi_gian_giao_ca": shift_end.isoformat(),
            },
            format="json",
        )
        self.assertEqual(without_selection.status_code, status.HTTP_201_CREATED)
        untouched_log = SogiaonhancaVH.objects.get(pk=without_selection.data["id"])
        self.assertEqual(untouched_log.truc_ktvh, "")
        self.assertIsNone(untouched_log.so_giao_nhan_ca_hc_nguon)
        self.assertIsNone(untouched_log.dong_bo_truc_ktvh_at)

    def test_sogiaonhancavh_viewer_cannot_update_or_delete(self):
        so = SogiaonhancaVH.objects.create(
            nha_may=self.nha_may,
            ngay_truc=date.today(),
            ca_truc=SogiaonhancaVH.CaTruc.A,
            thoi_gian_giao_ca=timezone.now(),
            user_giao_ca=self.creator,
            nguoi_tao=self.creator,
        )
        detail_url = reverse("nhatkyvanhanh:sogiaonhancavh-detail", kwargs={"pk": so.id})

        self.client.force_authenticate(user=self.viewer)
        patch_response = self.client.patch(
            detail_url,
            {"dia_diem": "Updated by viewer"},
            format="json",
        )
        delete_response = self.client.delete(detail_url)

        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sogiaonhancavh_owner_and_manager_permissions_before_receive(self):
        so = SogiaonhancaVH.objects.create(
            nha_may=self.nha_may,
            ngay_truc=date.today(),
            ca_truc=SogiaonhancaVH.CaTruc.A,
            thoi_gian_giao_ca=timezone.now(),
            user_giao_ca=self.creator,
            nguoi_tao=self.creator,
        )
        detail_url = reverse("nhatkyvanhanh:sogiaonhancavh-detail", kwargs={"pk": so.id})

        self.client.force_authenticate(user=self.creator)
        owner_response = self.client.patch(
            detail_url, {"dia_diem": "Phòng điều khiển"}, format="json"
        )
        self.assertEqual(owner_response.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.manager)
        manager_response = self.client.patch(
            detail_url, {"dia_diem": "Trung tâm vận hành"}, format="json"
        )
        self.assertEqual(manager_response.status_code, status.HTTP_200_OK)

    def test_shift_log_owner_can_delete_detail_created_by_manager(self):
        now = timezone.now()
        vh_log = SogiaonhancaVH.objects.create(
            nha_may=self.nha_may,
            ngay_truc=now.date(),
            ca_truc=SogiaonhancaVH.CaTruc.A,
            thoi_gian_giao_ca=now,
            user_giao_ca=self.creator,
            nguoi_tao=self.creator,
        )
        vh_detail = ChiTietSoGiaoNhanCaVH.objects.create(
            so_giao_nhan_ca=vh_log,
            noi_dung="Nội dung do quản lý bổ sung",
            nguoi_tao=self.manager,
        )
        vh_url = reverse(
            "nhatkyvanhanh:sogiaonhancavh-cap-nhat-noi-dung-chi-tiet",
            kwargs={"pk": vh_log.pk, "chi_tiet_id": vh_detail.pk},
        )

        hc_log = SogiaonhancaHC.objects.create(
            nha_may=self.nha_may,
            ngay_truc=now.date(),
            thoi_gian_giao_ca=now,
            user_giao_ca=self.creator,
            nguoi_tao=self.creator,
        )
        hc_detail = ChiTietSoGiaoNhanCaHC.objects.create(
            so_giao_nhan_ca=hc_log,
            noi_dung="Nội dung HC do quản lý bổ sung",
            nguoi_tao=self.manager,
        )
        hc_url = reverse(
            "nhatkyvanhanh:sogiaonhancahc-cap-nhat-noi-dung-chi-tiet",
            kwargs={"pk": hc_log.pk, "chi_tiet_id": hc_detail.pk},
        )

        self.client.force_authenticate(user=self.creator)
        self.assertEqual(self.client.delete(vh_url).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.delete(hc_url).status_code, status.HTTP_200_OK)
        self.assertFalse(ChiTietSoGiaoNhanCaVH.objects.filter(pk=vh_detail.pk).exists())
        self.assertFalse(ChiTietSoGiaoNhanCaHC.objects.filter(pk=hc_detail.pk).exists())

    def test_shift_log_manager_can_delete_other_users_details(self):
        now = timezone.now()
        vh_log = SogiaonhancaVH.objects.create(
            nha_may=self.nha_may,
            ngay_truc=now.date(),
            ca_truc=SogiaonhancaVH.CaTruc.A,
            thoi_gian_giao_ca=now,
            user_giao_ca=self.creator,
            nguoi_tao=self.creator,
        )
        detail = ChiTietSoGiaoNhanCaVH.objects.create(
            so_giao_nhan_ca=vh_log,
            noi_dung="Nội dung của trưởng ca",
            nguoi_tao=self.creator,
        )
        url = reverse(
            "nhatkyvanhanh:sogiaonhancavh-cap-nhat-noi-dung-chi-tiet",
            kwargs={"pk": vh_log.pk, "chi_tiet_id": detail.pk},
        )

        self.client.force_authenticate(user=self.manager)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_200_OK)
        self.assertFalse(ChiTietSoGiaoNhanCaVH.objects.filter(pk=detail.pk).exists())

        protected_detail = ChiTietSoGiaoNhanCaVH.objects.create(
            so_giao_nhan_ca=vh_log,
            noi_dung="Nội dung cần bảo vệ",
            nguoi_tao=self.creator,
        )
        protected_url = reverse(
            "nhatkyvanhanh:sogiaonhancavh-cap-nhat-noi-dung-chi-tiet",
            kwargs={"pk": vh_log.pk, "chi_tiet_id": protected_detail.pk},
        )

        self.client.force_authenticate(user=self.viewer)
        self.assertEqual(
            self.client.delete(protected_url).status_code,
            status.HTTP_403_FORBIDDEN,
        )

        vh_log.user_nhan_ca = self.receiver
        vh_log.nhan_ca_ky_at = timezone.now()
        vh_log.save()
        self.client.force_authenticate(user=self.manager)
        self.assertEqual(
            self.client.delete(protected_url).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertTrue(
            ChiTietSoGiaoNhanCaVH.objects.filter(pk=protected_detail.pk).exists()
        )

    def test_sogiaonhancavh_is_locked_immediately_after_receive(self):
        so = SogiaonhancaVH.objects.create(
            nha_may=self.nha_may,
            ngay_truc=date.today(),
            ca_truc=SogiaonhancaVH.CaTruc.A,
            thoi_gian_giao_ca=timezone.now(),
            user_giao_ca=self.creator,
            user_nhan_ca=self.receiver,
            nguoi_tao=self.creator,
            nhan_ca_ky_at=timezone.now(),
        )
        detail_url = reverse("nhatkyvanhanh:sogiaonhancavh-detail", kwargs={"pk": so.id})
        directive_url = reverse(
            "nhatkyvanhanh:sogiaonhancavh-tao-luu-y-chi-dao",
            kwargs={"pk": so.id},
        )

        self.client.force_authenticate(user=self.manager)
        patch_response = self.client.patch(
            detail_url, {"dia_diem": "Không được thay đổi"}, format="json"
        )
        delete_response = self.client.delete(detail_url)
        directive_response = self.client.post(
            directive_url,
            {"thoi_gian": timezone.now().isoformat(), "noi_dung": "Chỉ đạo mới"},
            format="json",
        )

        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(directive_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(SogiaonhancaVH.objects.filter(pk=so.pk).exists())

    def test_shift_directive_create_allows_log_owner_or_dedicated_permission(self):
        so = SogiaonhancaVH.objects.create(
            nha_may=self.nha_may,
            ngay_truc=date.today(),
            ca_truc=SogiaonhancaVH.CaTruc.A,
            thoi_gian_giao_ca=timezone.now(),
            user_giao_ca=self.creator,
            nguoi_tao=self.creator,
        )
        url = reverse(
            "nhatkyvanhanh:sogiaonhancavh-tao-luu-y-chi-dao",
            kwargs={"pk": so.id},
        )
        payload = {
            "thoi_gian": timezone.now().isoformat(),
            "noi_dung": "Chỉ đạo vận hành an toàn.",
        }

        self.client.force_authenticate(user=self.creator)
        owner_response = self.client.post(url, payload, format="json")
        self.assertEqual(owner_response.status_code, status.HTTP_201_CREATED)
        owner_directive = LuuYChiDaoSoGiaoNhanCaVH.objects.get(
            so_giao_nhan_ca=so,
            nguoi_tao=self.creator,
        )
        self.assertEqual(owner_directive.nguoi_tao_id, self.creator.id)

        self.client.force_authenticate(user=self.receiver)
        other_user_response = self.client.post(url, payload, format="json")
        self.assertEqual(other_user_response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.manager)
        manager_response = self.client.post(url, payload, format="json")
        self.assertEqual(manager_response.status_code, status.HTTP_403_FORBIDDEN)

        self.viewer_profile.can_create_shift_handover_directives = True
        self.viewer_profile.save(update_fields=["can_create_shift_handover_directives"])
        self.client.force_authenticate(user=self.viewer)
        allowed_response = self.client.post(url, payload, format="json")

        self.assertEqual(allowed_response.status_code, status.HTTP_201_CREATED)
        directive = LuuYChiDaoSoGiaoNhanCaVH.objects.get(
            so_giao_nhan_ca=so,
            nguoi_tao=self.viewer,
        )
        self.assertEqual(directive.nguoi_tao_id, self.viewer.id)

    def test_shift_directive_update_and_delete_are_owner_only(self):
        so = SogiaonhancaVH.objects.create(
            nha_may=self.nha_may,
            ngay_truc=date.today(),
            ca_truc=SogiaonhancaVH.CaTruc.A,
            thoi_gian_giao_ca=timezone.now(),
            user_giao_ca=self.creator,
            nguoi_tao=self.creator,
        )
        directive = LuuYChiDaoSoGiaoNhanCaVH.objects.create(
            so_giao_nhan_ca=so,
            thoi_gian=timezone.now(),
            noi_dung="Nội dung ban đầu",
            nguoi_tao=self.creator,
        )
        url = reverse(
            "nhatkyvanhanh:sogiaonhancavh-cap-nhat-luu-y-chi-dao",
            kwargs={"pk": so.id, "directive_id": directive.id},
        )

        self.client.force_authenticate(user=self.manager)
        manager_patch = self.client.patch(url, {"noi_dung": "Quản lý sửa"}, format="json")
        manager_delete = self.client.delete(url)
        self.assertEqual(manager_patch.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(manager_delete.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.creator)
        owner_patch = self.client.patch(url, {"noi_dung": "Chủ sở hữu sửa"}, format="json")
        self.assertEqual(owner_patch.status_code, status.HTTP_200_OK)
        directive.refresh_from_db()
        self.assertEqual(directive.noi_dung, "Chủ sở hữu sửa")

        owner_delete = self.client.delete(url)
        self.assertEqual(owner_delete.status_code, status.HTTP_200_OK)
        self.assertFalse(LuuYChiDaoSoGiaoNhanCaVH.objects.filter(pk=directive.pk).exists())

    def test_superuser_can_create_and_update_shift_directive_before_lock(self):
        superuser = User.objects.create_superuser(
            email="super-directive@example.com",
            password="testpassword123!",
            username="super-directive",
        )
        so = SogiaonhancaVH.objects.create(
            nha_may=self.nha_may,
            ngay_truc=date.today(),
            ca_truc=SogiaonhancaVH.CaTruc.A,
            thoi_gian_giao_ca=timezone.now(),
            user_giao_ca=self.creator,
            nguoi_tao=self.creator,
        )
        create_url = reverse(
            "nhatkyvanhanh:sogiaonhancavh-tao-luu-y-chi-dao",
            kwargs={"pk": so.id},
        )
        self.client.force_authenticate(user=superuser)
        created = self.client.post(
            create_url,
            {"thoi_gian": timezone.now().isoformat(), "noi_dung": "Chỉ đạo quản trị"},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        directive = LuuYChiDaoSoGiaoNhanCaVH.objects.get(so_giao_nhan_ca=so)
        self.assertEqual(directive.nguoi_tao_id, superuser.id)

        other_directive = LuuYChiDaoSoGiaoNhanCaVH.objects.create(
            so_giao_nhan_ca=so,
            thoi_gian=timezone.now(),
            noi_dung="Lưu ý của người khác",
            nguoi_tao=self.creator,
        )
        update_url = reverse(
            "nhatkyvanhanh:sogiaonhancavh-cap-nhat-luu-y-chi-dao",
            kwargs={"pk": so.id, "directive_id": other_directive.id},
        )
        updated = self.client.patch(update_url, {"noi_dung": "Superuser hiệu chỉnh"}, format="json")
        self.assertEqual(updated.status_code, status.HTTP_200_OK)

    def test_shift_directive_is_immutable_after_shift_is_received(self):
        so = SogiaonhancaVH.objects.create(
            nha_may=self.nha_may,
            ngay_truc=date.today(),
            ca_truc=SogiaonhancaVH.CaTruc.A,
            thoi_gian_giao_ca=timezone.now(),
            user_giao_ca=self.creator,
            user_nhan_ca=self.receiver,
            nguoi_tao=self.creator,
            nhan_ca_ky_at=timezone.now(),
        )
        directive = LuuYChiDaoSoGiaoNhanCaVH.objects.create(
            so_giao_nhan_ca=so,
            thoi_gian=timezone.now(),
            noi_dung="Nội dung đã khóa",
            nguoi_tao=self.creator,
        )
        url = reverse(
            "nhatkyvanhanh:sogiaonhancavh-cap-nhat-luu-y-chi-dao",
            kwargs={"pk": so.id, "directive_id": directive.id},
        )
        self.client.force_authenticate(user=self.creator)

        patch_response = self.client.patch(url, {"noi_dung": "Không được sửa"}, format="json")
        delete_response = self.client.delete(url)

        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)
        directive.refresh_from_db()
        self.assertEqual(directive.noi_dung, "Nội dung đã khóa")

    def test_sogiaonhancavh_allows_two_assistants_without_primary(self):
        shift_log = SogiaonhancaVH.objects.create(
            nha_may=self.nha_may,
            ngay_truc=date.today(),
            ca_truc=SogiaonhancaVH.CaTruc.A,
            thoi_gian_giao_ca=timezone.now(),
            user_giao_ca=self.creator,
            nguoi_tao=self.creator,
        )
        create_staff_url = reverse(
            "nhatkyvanhanh:sogiaonhancavh-tao-nhan-su-ca",
            kwargs={"pk": shift_log.id},
        )
        self.client.force_authenticate(user=self.creator)

        first_response = self.client.post(
            create_staff_url,
            {"vai_tro": "truc_phu", "ten_nhan_su": "Nguyễn Văn A", "thu_tu": 1},
            format="json",
        )
        second_response = self.client.post(
            create_staff_url,
            {"vai_tro": "truc_phu", "ten_nhan_su": "Trần Văn B", "thu_tu": 2},
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(second_response.data["nhan_su_ca"]), 2)
        shift_log.refresh_from_db()
        self.assertEqual(shift_log.truc_chinh, "")
        self.assertEqual(shift_log.truc_phu, "Nguyễn Văn A, Trần Văn B")

    def test_sogiaonhancavh_rejects_duplicate_staff_name(self):
        shift_log = SogiaonhancaVH.objects.create(
            nha_may=self.nha_may,
            ngay_truc=date.today(),
            ca_truc=SogiaonhancaVH.CaTruc.A,
            thoi_gian_giao_ca=timezone.now(),
            user_giao_ca=self.creator,
            nguoi_tao=self.creator,
        )
        create_staff_url = reverse(
            "nhatkyvanhanh:sogiaonhancavh-tao-nhan-su-ca",
            kwargs={"pk": shift_log.id},
        )
        self.client.force_authenticate(user=self.creator)
        self.client.post(
            create_staff_url,
            {"vai_tro": "truc_phu", "ten_nhan_su": "Nguyễn Văn A"},
            format="json",
        )
        duplicate_response = self.client.post(
            create_staff_url,
            {"vai_tro": "truc_phu", "ten_nhan_su": "nguyễn văn a"},
            format="json",
        )

        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ten_nhan_su", duplicate_response.data)
