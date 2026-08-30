from django.contrib import admin
from django.test import SimpleTestCase

from nhatkyvanhanh.models import SogiaonhancaHC, SogiaonhancaVH


class ShiftHandoverAdminConfigurationTests(SimpleTestCase):
    def test_vh_admin_exposes_factory_filter_and_column(self):
        model_admin = admin.site._registry[SogiaonhancaVH]

        self.assertIn("nha_may", model_admin.list_filter)
        self.assertIn("nha_may", model_admin.list_display)
        self.assertIn("nha_may", model_admin.list_select_related)

    def test_hc_admin_exposes_factory_filter_and_column(self):
        model_admin = admin.site._registry[SogiaonhancaHC]

        self.assertIn("nha_may", model_admin.list_filter)
        self.assertIn("nha_may", model_admin.list_display)
        self.assertIn("nha_may", model_admin.list_select_related)
