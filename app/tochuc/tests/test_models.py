from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase

from quanlycatruc.models import NhanSu, NhomLichTruc
from tochuc.models import BoPhan, DonViToChuc, NhaMay


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


class SharedOrganizationModelTests(TestCase):
    def setUp(self):
        self.song_hinh = NhaMay.objects.create(
            ma_nha_may="SH-ORG",
            ten_nha_may="Sông Hinh",
        )
        self.vinh_son = NhaMay.objects.create(
            ma_nha_may="VS-ORG",
            ten_nha_may="Vĩnh Sơn",
        )

    def test_models_belong_to_shared_app_and_keep_legacy_tables(self):
        self.assertEqual(DonViToChuc._meta.app_label, "tochuc")
        self.assertEqual(BoPhan._meta.app_label, "tochuc")
        self.assertEqual(
            DonViToChuc._meta.db_table,
            "quanlycatruc_donvitochuc",
        )
        self.assertEqual(BoPhan._meta.db_table, "quanlycatruc_bophan")

    def test_shift_models_reference_shared_organization_models(self):
        self.assertIs(
            NhanSu._meta.get_field("don_vi").remote_field.model,
            DonViToChuc,
        )
        self.assertIs(
            NhanSu._meta.get_field("bo_phan").remote_field.model,
            BoPhan,
        )
        self.assertIs(
            NhomLichTruc._meta.get_field("don_vi").remote_field.model,
            DonViToChuc,
        )

    def test_parent_unit_must_belong_to_same_factory(self):
        parent = DonViToChuc.objects.create(
            ma_don_vi="SH-PARENT",
            ten_don_vi="Đơn vị Sông Hinh",
            nha_may=self.song_hinh,
        )
        child = DonViToChuc(
            ma_don_vi="VS-CHILD",
            ten_don_vi="Đơn vị Vĩnh Sơn",
            nha_may=self.vinh_son,
            don_vi_cha=parent,
        )

        with self.assertRaises(ValidationError):
            child.full_clean()
