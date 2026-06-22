from datetime import date
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import UserProfile
from khovattu.models import Bang_nha_may
from ..models import ThongSoThuyVanCaiDat, ThongsoSanxuat, ThongsoGioPhat
from ..hydrology_services import (
    get_capacity_points_for_reservoir,
    get_capacity_bounds_for_reservoir,
)

User = get_user_model()


class ThongSoThuyVanAPITests(APITestCase):
    def setUp(self):
        # Clear cache để tránh kết quả rác từ các test trước đó
        get_capacity_points_for_reservoir.cache_clear()
        get_capacity_bounds_for_reservoir.cache_clear()
        # 1. Khởi tạo các nhà máy
        self.nha_may_sh = Bang_nha_may.objects.create(
            ma_nha_may="SH",
            ten_nha_may="Sông Hinh",
        )
        self.nha_may_vs = Bang_nha_may.objects.create(
            ma_nha_may="VS",
            ten_nha_may="Vĩnh Sơn",
        )

        # 2. Tạo users
        self.sh_user = User.objects.create_user(
            email="sh_user@example.com",
            password="testpassword123!",
            username="sh_user",
        )
        self.vs_user = User.objects.create_user(
            email="vs_user@example.com",
            password="testpassword123!",
            username="vs_user",
        )
        self.unprivileged_user = User.objects.create_user(
            email="unprivileged@example.com",
            password="testpassword123!",
            username="unprivileged",
        )

        # 3. Tạo UserProfiles với phân quyền nhà máy tương ứng
        self.sh_profile = UserProfile.objects.create(
            user=self.sh_user,
            ho_ten="Nhân viên Sông Hinh",
            nha_may=self.nha_may_sh,
            can_view_hydrology_data=True,
            can_create_hydrology_data=True,
            can_edit_hydrology_data=True,
            can_delete_hydrology_data=True,
            can_view_realtime_hydrology=True,
            can_update_realtime_hydrology=True,
            can_view_hydrology_settings=True,
            can_edit_hydrology_settings=True,
        )

        self.vs_profile = UserProfile.objects.create(
            user=self.vs_user,
            ho_ten="Nhân viên Vĩnh Sơn",
            nha_may=self.nha_may_vs,
            can_view_hydrology_data=True,
            can_create_hydrology_data=True,
            can_edit_hydrology_data=True,
            can_delete_hydrology_data=True,
            can_view_realtime_hydrology=True,
            can_update_realtime_hydrology=True,
            can_view_hydrology_settings=True,
            can_edit_hydrology_settings=True,
        )

        self.unprivileged_profile = UserProfile.objects.create(
            user=self.unprivileged_user,
            ho_ten="Nhân viên không có quyền",
            nha_may=self.nha_may_sh,
            can_view_hydrology_data=False,
            can_create_hydrology_data=False,
        )

    def test_factory_scoping_thongsosanxuat_list(self):
        url = reverse("thongsothuyvan:thongsosanxuat-list")

        # 1. Chưa đăng nhập => 401 Unauthorized
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Đăng nhập bằng sh_user và lấy dữ liệu Sông Hinh => 200 OK
        self.client.force_authenticate(user=self.sh_user)
        response = self.client.get(url, {"nhamay": "songhinh"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 3. Đăng nhập bằng sh_user cố truy cập Vĩnh Sơn => 403 Forbidden
        response = self.client.get(url, {"nhamay": "vinhson"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_factory_scoping_thongsosanxuat_create(self):
        url = reverse("thongsothuyvan:thongsosanxuat-list")

        # Đăng nhập bằng sh_user (nhà máy Sông Hinh)
        self.client.force_authenticate(user=self.sh_user)

        # 1. Tạo thông số cho Sông Hinh => Thành công (201 Created)
        data_sh = {
            "nha_may": "songhinh",
            "thoi_gian": timezone.now().isoformat(),
            "cot_g": 200.5,
        }
        response = self.client.post(url, data_sh)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 2. Cố tình tạo thông số cho Vĩnh Sơn => Thất bại (403 Forbidden)
        data_vs = {
            "nha_may": "vinhson",
            "thoi_gian": timezone.now().isoformat(),
            "cot_g": 768.2,
        }
        response = self.client.post(url, data_vs)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_thongsosanxuat_requires_hydrology_view_permission(self):
        url = reverse("thongsothuyvan:thongsosanxuat-list")
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=timezone.now(),
            cot_g=200.5,
            created_by=self.sh_user,
            updated_by=self.sh_user,
        )

        self.client.force_authenticate(user=self.unprivileged_user)
        response = self.client.get(url, {"nhamay": "songhinh"})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_thongsosanxuat_requires_hydrology_create_permission(self):
        url = reverse("thongsothuyvan:thongsosanxuat-list")
        self.client.force_authenticate(user=self.unprivileged_user)

        response = self.client.post(
            url,
            {
                "nha_may": "songhinh",
                "thoi_gian": timezone.now().isoformat(),
                "cot_g": 200.5,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_thongsogiophat_requires_hydrology_permissions(self):
        url = reverse("thongsothuyvan:thongsogiophat-list")
        ThongsoGioPhat.objects.create(
            nha_may="songhinh",
            ngay=date(2026, 5, 30),
            to_may=1,
            gio_phat_dien=12.5,
            created_by=self.sh_user,
            updated_by=self.sh_user,
        )

        self.client.force_authenticate(user=self.unprivileged_user)
        list_response = self.client.get(url, {"nhamay": "songhinh"})
        create_response = self.client.post(
            url,
            {
                "nha_may": "songhinh",
                "ngay": "2026-05-30",
                "to_may": 2,
                "gio_phat_dien": 8,
            },
        )

        self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hydrology_settings_requires_view_permission(self):
        url = reverse("thongsothuyvan:settings")

        self.client.force_authenticate(user=self.unprivileged_user)
        response = self.client.get(url, {"year": 2026})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hydrology_settings_requires_edit_permission(self):
        url = reverse("thongsothuyvan:settings")

        self.client.force_authenticate(user=self.unprivileged_user)
        response = self.client.post(
            url,
            {
                "year": 2026,
                "annual": {"songhinh": 1200},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hydrology_settings_create_sets_created_and_updated_user(self):
        url = reverse("thongsothuyvan:settings")

        self.client.force_authenticate(user=self.sh_user)
        response = self.client.post(
            url,
            {
                "year": 2026,
                "annual": {"songhinh": 1200},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        setting = ThongSoThuyVanCaiDat.objects.get(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_NAM,
        )
        self.assertEqual(setting.created_by, self.sh_user)
        self.assertEqual(setting.updated_by, self.sh_user)

    def test_hydrology_settings_creator_can_update_record(self):
        url = reverse("thongsothuyvan:settings")
        setting = ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_NAM,
            sanluong_kehoach_nam=1200,
            created_by=self.sh_user,
            updated_by=self.sh_user,
        )

        self.client.force_authenticate(user=self.sh_user)
        response = self.client.post(
            url,
            {
                "year": 2026,
                "annual": {"songhinh": 1300},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        setting.refresh_from_db()
        self.assertEqual(setting.sanluong_kehoach_nam, 1300)
        self.assertEqual(setting.created_by, self.sh_user)
        self.assertEqual(setting.updated_by, self.sh_user)

    def test_hydrology_settings_other_user_with_permission_can_update_existing_record(self):
        url = reverse("thongsothuyvan:settings")
        other_user = User.objects.create_user(
            email="sh_other@example.com",
            password="testpassword123!",
            username="sh_other",
        )
        UserProfile.objects.create(
            user=other_user,
            ho_ten="Nhan vien Song Hinh khac",
            nha_may=self.nha_may_sh,
            can_view_hydrology_settings=True,
            can_edit_hydrology_settings=True,
        )
        setting = ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_NAM,
            sanluong_kehoach_nam=1200,
            created_by=self.sh_user,
            updated_by=self.sh_user,
        )

        self.client.force_authenticate(user=other_user)
        response = self.client.post(
            url,
            {
                "year": 2026,
                "annual": {"songhinh": 1300},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        setting.refresh_from_db()
        self.assertEqual(setting.sanluong_kehoach_nam, 1300)
        self.assertEqual(setting.updated_by, other_user)

        # Kiểm tra user khác KHÔNG có quyền can_edit_hydrology_settings
        no_perm_user = User.objects.create_user(
            email="sh_no_perm@example.com",
            password="testpassword123!",
            username="sh_no_perm",
        )
        UserProfile.objects.create(
            user=no_perm_user,
            ho_ten="Nhan vien khong co quyen",
            nha_may=self.nha_may_sh,
            can_view_hydrology_settings=True,
            can_edit_hydrology_settings=False,
        )
        self.client.force_authenticate(user=no_perm_user)
        response = self.client.post(
            url,
            {
                "year": 2026,
                "annual": {"songhinh": 1400},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        setting.refresh_from_db()
        self.assertEqual(setting.sanluong_kehoach_nam, 1300)

    def test_google_sheet_preview_factory_scoping(self):
        url = reverse("thongsothuyvan:sync-preview")

        # 1. Đăng nhập bằng sh_user (Sông Hinh)
        self.client.force_authenticate(user=self.sh_user)

        # 2. Cố tình preview Google Sheet của Vĩnh Sơn => Thất bại (403 Forbidden)
        response = self.client.get(url, {"nhamay": "vinhson", "date": "2026-05-30"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_vrain_sync_anonymous_denied(self):
        # 1. Gọi API Sync Vrain không có xác thực
        url = reverse("thongsothuyvan:sync-vrain")
        response = self.client.post(url, {"date": "2026-05-30"})
        
        # Mặc định trước kia là AllowAny (200/500/v.v.). Bây giờ phải bị chặn (401 Unauthorized)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
