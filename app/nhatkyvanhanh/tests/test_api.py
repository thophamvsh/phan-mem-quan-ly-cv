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
from khovattu.models import Bang_nha_may
from nhatkyvanhanh.models import (
    SoAnToanDauGio,
    SoChuyenDoiTBThang,
    SoChuyenDoiThietBiTuan,
    LanChuyenDoiThietBi,
    KhacPhucSuKien,
    SonhatkyvanhanhDiesel,
    SogiaonhancaHC,
    SogiaonhancaVH,
    SuKien,
)

User = get_user_model()


class NhatKyVanHanhAPITests(APITestCase):
    def setUp(self):
        # Create factory/nha_may first
        self.nha_may = Bang_nha_may.objects.create(
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
