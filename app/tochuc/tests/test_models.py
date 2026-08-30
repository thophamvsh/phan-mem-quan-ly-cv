from django.contrib.auth.models import Permission
from django.test import TestCase

from tochuc.models import NhaMay


class NhaMayModelTests(TestCase):
    def test_uses_existing_factory_table(self):
        self.assertEqual(NhaMay._meta.db_table, "khovattu_bang_nha_may")

    def test_factory_identity_and_display_are_stable(self):
        factory = NhaMay.objects.create(
            ma_nha_may="TEST",
            ten_nha_may="Nhà máy kiểm thử",
        )

        self.assertEqual(str(factory), "TEST - Nhà máy kiểm thử")
        self.assertEqual(
            NhaMay.objects.get(pk=factory.pk).ma_nha_may,
            "TEST",
        )

    def test_default_permissions_belong_to_shared_organization_app(self):
        codenames = set(
            Permission.objects.filter(
                content_type__app_label="tochuc",
                content_type__model="nhamay",
            ).values_list("codename", flat=True)
        )

        self.assertTrue(
            {"add_nhamay", "change_nhamay", "delete_nhamay", "view_nhamay"}
            <= codenames
        )
