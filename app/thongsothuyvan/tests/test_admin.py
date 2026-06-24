from datetime import date

import tablib
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from thongsothuyvan.admin import ThongSoThuyVanThucTeResource
from thongsothuyvan.models import ThongSoThuyVanThucTe


class ThongSoThuyVanThucTeAdminTests(TestCase):
    def test_resource_import_updates_by_plant_and_day(self):
        ThongSoThuyVanThucTe.objects.create(
            nha_may="songhinh",
            ngay=date(2026, 6, 23),
            muc_nuoc_ho=200.0,
            qve=1.0,
        )

        dataset = tablib.Dataset(
            headers=[
                "nha_may",
                "ngay",
                "muc_nuoc_ho",
                "qve",
                "muc_nuoc_ho_a",
                "muc_nuoc_ho_b",
                "muc_nuoc_ho_c",
                "qve_ho_a",
                "qve_ho_b",
                "qve_ho_c",
                "qve_tong",
            ]
        )
        dataset.append(["songhinh", "23/06/2026", "203,174", "9,446", "", "", "", "", "", "", ""])
        dataset.append(["vinhson", "23/06/2026", "", "", "770,48", "818,69", "972,72", "0,5", "0,4", "0,3", "1,2"])

        result = ThongSoThuyVanThucTeResource().import_data(dataset, dry_run=False, raise_errors=True)

        self.assertFalse(result.has_errors())
        self.assertEqual(ThongSoThuyVanThucTe.objects.count(), 2)
        songhinh = ThongSoThuyVanThucTe.objects.get(nha_may="songhinh", ngay=date(2026, 6, 23))
        self.assertEqual(songhinh.muc_nuoc_ho, 203.174)
        self.assertEqual(songhinh.qve, 9.446)
        vinhson = ThongSoThuyVanThucTe.objects.get(nha_may="vinhson", ngay=date(2026, 6, 23))
        self.assertEqual(vinhson.muc_nuoc_ho_a, 770.48)
        self.assertEqual(vinhson.qve_tong, 1.2)

    def test_admin_exposes_import_export_urls_with_custom_changelist(self):
        User = get_user_model()
        admin_user = User.objects.create_superuser(
            email="admin-thucte@example.com",
            password="testpassword123!",
            username="admin-thucte",
        )
        self.client.force_login(admin_user)

        changelist_url = reverse("admin:thongsothuyvan_thongsothuyvanthucte_changelist")
        import_url = reverse("admin:thongsothuyvan_thongsothuyvanthucte_import")
        export_url = reverse("admin:thongsothuyvan_thongsothuyvanthucte_export")
        response = self.client.get(changelist_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, import_url)
        self.assertContains(response, export_url)
