from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from quanlyvanhanh.admin import ThietBiAdmin, ThietBiResource
from quanlyvanhanh.models import ThietBi


class ThietBiAdminExportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="device-export-admin",
            email="device-export-admin@example.com",
            password="test-pass-123",
        )
        self.song_hinh = ThietBi.objects.create(
            ten="Máy cắt Sông Hinh",
            ma="SH-EXPORT",
            ma_day_du="SH-EXPORT",
            nha_may="Sông Hinh",
        )
        ThietBi.objects.create(
            ten="Máy cắt Vĩnh Sơn",
            ma="VS-EXPORT",
            ma_day_du="VS-EXPORT",
            nha_may="Vĩnh Sơn",
        )
        self.client.force_login(self.user)

    def test_export_page_supports_django_52_changelist_signature(self):
        response = self.client.get(
            reverse("admin:quanlyvanhanh_thietbi_export"),
            {"nha_may": "Sông Hinh"},
        )

        self.assertEqual(response.status_code, 200)

    def test_export_queryset_keeps_admin_factory_filter(self):
        request = RequestFactory().get(
            reverse("admin:quanlyvanhanh_thietbi_export"),
            {"nha_may": "Sông Hinh"},
        )
        request.user = self.user
        model_admin = admin.site._registry[ThietBi]

        queryset = model_admin.get_export_queryset(request)

        self.assertIsInstance(model_admin, ThietBiAdmin)
        self.assertEqual(list(queryset), [self.song_hinh])

    def test_resource_export_supports_export_fields_keyword(self):
        dataset = ThietBiResource().export(
            ThietBi.objects.filter(pk=self.song_hinh.pk)
        )

        self.assertEqual(dataset.height, 1)
