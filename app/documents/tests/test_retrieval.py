from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import UserProfile
from documents.models import Document
from documents.services.retrieval import filter_documents_for_user, get_allowed_factories_for_user
from khovattu.models import Bang_nha_may


class DocumentRetrievalPermissionTests(TestCase):
    def setUp(self):
        self.songhinh = Bang_nha_may.objects.create(ma_nha_may="SH", ten_nha_may="Song Hinh")
        self.vinhson = Bang_nha_may.objects.create(ma_nha_may="VS", ten_nha_may="Vinh Son")

        User = get_user_model()
        self.songhinh_user = User.objects.create_user(
            email="songhinh-docs@example.com",
            username="songhinh_docs",
            password="testpass123",
        )
        UserProfile.objects.create(
            user=self.songhinh_user,
            nha_may=self.songhinh,
            can_use_ai_tools=True,
            can_use_ai_documents=True,
        )

        self.vinhson_user = User.objects.create_user(
            email="vinhson-docs@example.com",
            username="vinhson_docs",
            password="testpass123",
        )
        UserProfile.objects.create(
            user=self.vinhson_user,
            nha_may=self.vinhson,
            can_use_ai_tools=True,
            can_use_ai_documents=True,
        )

        self.general_doc = Document.objects.create(
            title="Tài liệu chung",
            original_file="ai_documents/general.pdf",
            factory=Document.FACTORY_GENERAL,
            status=Document.STATUS_READY,
        )
        self.songhinh_doc = Document.objects.create(
            title="Tài liệu Sông Hinh",
            original_file="ai_documents/songhinh.pdf",
            factory=Document.FACTORY_SONGHINH,
            status=Document.STATUS_READY,
        )
        self.tkt_doc = Document.objects.create(
            title="Tài liệu Thượng Kon Tum",
            original_file="ai_documents/tkt.pdf",
            factory=Document.FACTORY_THUONGKONTUM,
            status=Document.STATUS_READY,
        )
        self.vinhson_doc = Document.objects.create(
            title="Tài liệu Vĩnh Sơn",
            original_file="ai_documents/vinhson.pdf",
            factory=Document.FACTORY_VINHSON,
            status=Document.STATUS_READY,
        )

    def test_songhinh_user_can_access_general_songhinh_and_tkt_documents(self):
        allowed_factories = get_allowed_factories_for_user(self.songhinh_user)
        self.assertEqual(
            allowed_factories,
            {
                Document.FACTORY_GENERAL,
                Document.FACTORY_SONGHINH,
                Document.FACTORY_THUONGKONTUM,
                Document.FACTORY_VINHSON,
                Document.FACTORY_TCKT,
                Document.FACTORY_KHDT,
                Document.FACTORY_TH,
                Document.FACTORY_KT,
            },
        )

        ids = set(filter_documents_for_user(self.songhinh_user).values_list("id", flat=True))
        self.assertEqual(
            ids,
            {
                self.general_doc.id,
                self.songhinh_doc.id,
                self.tkt_doc.id,
                self.vinhson_doc.id,
            },
        )

    def test_vinhson_user_can_access_general_and_vinhson_documents(self):
        ids = set(filter_documents_for_user(self.vinhson_user).values_list("id", flat=True))
        self.assertEqual(
            ids,
            {
                self.general_doc.id,
                self.songhinh_doc.id,
                self.tkt_doc.id,
                self.vinhson_doc.id,
            },
        )
