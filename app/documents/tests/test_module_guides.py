import hashlib
import io
import shutil
import tempfile
import threading
import zipfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from core.models import UserActivityLog, UserProfile
from documents.models import ModuleGuide, inspect_module_guide_file
from documents.services import module_guide_service
from documents.services.module_guide_service import (
    ModuleGuideConflict,
    publish_module_guide,
)
from tochuc.models import NhaMay


def pdf_upload(name="quy-trinh.pdf", marker=b"v1"):
    return SimpleUploadedFile(
        name,
        b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n" + marker + b"\n%%EOF\n",
        content_type="application/pdf",
    )


def docx_upload(name="huong-dan.docx", valid=True):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("readme.txt", "not an OOXML document")
        if valid:
            archive.writestr("[Content_Types].xml", "<Types />")
            archive.writestr("word/document.xml", "<document />")
    return SimpleUploadedFile(
        name,
        stream.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )


class ModuleGuideApiTests(APITestCase):
    endpoint = "/api/v1/module-guides/"

    def setUp(self):
        self.media_dir = tempfile.mkdtemp(prefix="module-guides-test-")
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_dir,
            USE_X_ACCEL_REDIRECT=False,
        )
        self.settings_override.enable()
        self.sh = NhaMay.objects.create(ma_nha_may="SH-GUIDE", ten_nha_may="Sông Hinh")
        self.vs = NhaMay.objects.create(ma_nha_may="VS-GUIDE", ten_nha_may="Vĩnh Sơn")
        self.viewer = self.make_user(
            "guide-viewer",
            self.sh,
            can_view_module_guides=True,
            can_download_module_guides=True,
        )
        self.manager = self.make_user(
            "guide-manager",
            self.sh,
            can_view_module_guides=True,
            can_manage_module_guides=True,
            can_download_module_guides=True,
        )
        self.publisher = self.make_user(
            "guide-publisher",
            self.sh,
            can_view_module_guides=True,
            can_publish_module_guides=True,
            can_view_module_guide_history=True,
        )
        self.all_factory_manager = self.make_user(
            "guide-global-manager",
            None,
            is_all_factories=True,
            can_view_module_guides=True,
            can_manage_module_guides=True,
            can_publish_module_guides=True,
        )

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_dir, ignore_errors=True)

    @staticmethod
    def make_user(username, plant, **profile_values):
        user = get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="Guide-Safe-2026!",
        )
        UserProfile.objects.create(user=user, nha_may=plant, **profile_values)
        return user

    def create_guide(
        self,
        *,
        module_code="so_giao_nhan_ca_vh",
        plant=None,
        creator=None,
        version="v1.0",
        status=ModuleGuide.STATUS_DRAFT,
        title="Quy trình vận hành",
        marker=b"v1",
        is_primary=True,
        kind="procedure",
        order=0,
    ):
        return ModuleGuide.objects.create(
            module_code=module_code,
            nha_may=plant,
            title=title,
            document_kind=kind,
            is_primary=is_primary,
            order=order,
            version_label=version,
            status=status,
            quick_guide="1. Kiểm tra thiết bị\n2. Bàn giao ca",
            file=pdf_upload(f"guide-{version}.pdf", marker),
            created_by=creator or self.manager,
        )

    def test_module_options_require_authentication_and_return_scoped_catalog(self):
        options_endpoint = f"{self.endpoint}module-options/"
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(options_endpoint).status_code, 401)

        self.client.force_authenticate(self.viewer)
        response = self.client.get(options_endpoint)
        self.assertEqual(response.status_code, 200, response.data)
        options = response.data
        values = [item["value"] for item in options]
        self.assertEqual(len(values), len(set(values)))
        self.assertEqual(set(values), {value for value, _ in ModuleGuide.MODULE_CHOICES})
        scopes = {item["value"]: item["scope"] for item in options}
        self.assertEqual(scopes["dashboard_nha_may"], ModuleGuide.SCOPE_PLANT)
        self.assertEqual(scopes["cai_dat_he_thong"], ModuleGuide.SCOPE_PLANT_OPTIONAL)
        self.assertEqual(scopes["quan_ly_tai_khoan"], ModuleGuide.SCOPE_GLOBAL)

    def test_new_module_choices_validate_and_global_module_rejects_plant(self):
        required_codes = {
            "dashboard_nha_may",
            "cai_dat_he_thong",
            "quan_ly_tai_khoan",
            "quan_ly_ca_truc",
            "nhat_ky_kiem_toan",
            "quan_ly_tai_lieu",
        }
        self.assertTrue(required_codes.issubset(dict(ModuleGuide.MODULE_CHOICES)))

        self.client.force_authenticate(self.all_factory_manager)
        base_payload = {
            "title": "Hướng dẫn kiểm thử",
            "document_kind": "procedure",
            "is_primary": True,
            "order": 0,
            "version_label": "scope-v1",
        }
        invalid_code = self.client.post(
            self.endpoint,
            {
                **base_payload,
                "module_code": "module_khong_ton_tai",
                "file": pdf_upload("invalid-code.pdf"),
            },
            format="multipart",
        )
        self.assertEqual(invalid_code.status_code, 400, invalid_code.data)

        invalid_scope = self.client.post(
            self.endpoint,
            {
                **base_payload,
                "module_code": "quan_ly_tai_khoan",
                "nha_may": self.sh.id,
                "file": pdf_upload("invalid-scope.pdf"),
            },
            format="multipart",
        )
        self.assertEqual(invalid_scope.status_code, 400, invalid_scope.data)
        self.assertIn("nha_may", invalid_scope.data)

        valid_global = self.client.post(
            self.endpoint,
            {
                **base_payload,
                "module_code": "quan_ly_tai_khoan",
                "file": pdf_upload("valid-global.pdf"),
            },
            format="multipart",
        )
        self.assertEqual(valid_global.status_code, 201, valid_global.data)
        self.assertIsNone(valid_global.data["nha_may"])

    def test_all_factory_scope_rules_allow_global_and_optional_without_plant(self):
        viewer = self.make_user(
            "all-factory-scope-viewer",
            None,
            is_all_factories=True,
            can_view_module_guides=True,
        )
        global_guide = self.create_guide(
            module_code="quan_ly_tai_khoan",
            plant=None,
            creator=self.all_factory_manager,
            status=ModuleGuide.STATUS_PUBLISHED,
            version="accounts-global",
        )
        optional_global = self.create_guide(
            module_code="cai_dat_he_thong",
            plant=None,
            creator=self.all_factory_manager,
            status=ModuleGuide.STATUS_PUBLISHED,
            version="settings-global",
        )
        self.create_guide(
            module_code="cai_dat_he_thong",
            plant=self.sh,
            creator=self.all_factory_manager,
            status=ModuleGuide.STATUS_PUBLISHED,
            version="settings-sh",
        )

        self.client.force_authenticate(viewer)
        global_response = self.client.get(
            f"{self.endpoint}?module_code=quan_ly_tai_khoan"
        )
        self.assertEqual(global_response.status_code, 200, global_response.data)
        global_items = global_response.data.get("results", global_response.data)
        self.assertEqual([item["id"] for item in global_items], [global_guide.id])

        optional_response = self.client.get(
            f"{self.endpoint}?module_code=cai_dat_he_thong"
        )
        self.assertEqual(optional_response.status_code, 200, optional_response.data)
        optional_items = optional_response.data.get("results", optional_response.data)
        self.assertEqual([item["id"] for item in optional_items], [optional_global.id])

        plant_response = self.client.get(
            f"{self.endpoint}?module_code=nhat_ky_su_kien"
        )
        self.assertEqual(plant_response.status_code, 400, plant_response.data)

    def test_file_validation_is_fail_closed_for_fake_pdf_and_broken_docx(self):
        with self.assertRaises(ValidationError):
            inspect_module_guide_file(
                SimpleUploadedFile("malware.pdf", b"MZ executable payload")
            )
        with self.assertRaises(ValidationError):
            inspect_module_guide_file(docx_upload(valid=False))
        mime, checksum, size = inspect_module_guide_file(docx_upload(valid=True))
        self.assertIn(mime, {"application/zip", "application/octet-stream"})
        self.assertEqual(len(checksum), 64)
        self.assertGreater(size, 0)

    def test_create_enforces_plant_scope_and_server_fields(self):
        self.client.force_authenticate(self.manager)
        payload = {
            "module_code": "so_giao_nhan_ca_vh",
            "nha_may": self.sh.id,
            "title": "Quy trình SH",
            "document_kind": "procedure",
            "is_primary": True,
            "order": 0,
            "version_label": "v2.0",
            "status": "published",
            "file": pdf_upload(),
        }
        created = self.client.post(self.endpoint, payload, format="multipart")
        self.assertEqual(created.status_code, 201, created.data)
        guide = ModuleGuide.objects.get(pk=created.data["id"])
        self.assertEqual(guide.status, ModuleGuide.STATUS_DRAFT)
        self.assertEqual(guide.created_by, self.manager)
        self.assertEqual(guide.nha_may, self.sh)

        payload["nha_may"] = self.vs.id
        payload["version_label"] = "v3.0"
        payload["file"] = pdf_upload("vs.pdf")
        denied = self.client.post(self.endpoint, payload, format="multipart")
        self.assertEqual(denied.status_code, 403, denied.data)

    def test_all_factory_viewer_must_choose_plant_but_manager_can_use_management_mode(self):
        viewer = self.make_user(
            "all-factory-viewer",
            None,
            is_all_factories=True,
            can_view_module_guides=True,
        )
        self.client.force_authenticate(viewer)
        self.assertEqual(self.client.get(self.endpoint).status_code, 400)
        self.assertEqual(
            self.client.get(f"{self.endpoint}?is_management=1").status_code,
            400,
        )
        self.client.force_authenticate(self.all_factory_manager)
        self.assertEqual(
            self.client.get(f"{self.endpoint}?is_management=1").status_code,
            200,
        )

    def test_published_list_is_plant_scoped_and_orders_plant_before_global(self):
        global_guide = self.create_guide(
            plant=None, creator=self.all_factory_manager, status="published", version="global"
        )
        plant_guide = self.create_guide(
            plant=self.sh, status="published", version="plant"
        )
        self.create_guide(plant=self.vs, status="published", version="foreign")
        self.client.force_authenticate(self.viewer)
        response = self.client.get(
            f"{self.endpoint}?module_code=so_giao_nhan_ca_vh"
        )
        self.assertEqual(response.status_code, 200, response.data)
        items = response.data.get("results", response.data)
        ids = [item["id"] for item in items]
        self.assertEqual(ids, [plant_guide.id, global_guide.id])

    def test_cross_plant_and_non_history_content_access_are_denied(self):
        foreign = self.create_guide(
            plant=self.vs, status="published", version="foreign-content"
        )
        retired = self.create_guide(
            plant=self.sh, status="retired", version="retired-content"
        )
        self.client.force_authenticate(self.viewer)
        self.assertEqual(
            self.client.get(f"{self.endpoint}{foreign.id}/content/").status_code,
            403,
        )
        self.assertEqual(
            self.client.get(f"{self.endpoint}{retired.id}/content/").status_code,
            403,
        )
        self.client.force_authenticate(self.publisher)
        self.assertEqual(
            self.client.get(f"{self.endpoint}{retired.id}/content/").status_code,
            200,
        )

    def test_publisher_can_review_draft_but_cannot_edit_it(self):
        draft = self.create_guide(plant=self.sh, version="review")
        self.client.force_authenticate(self.publisher)
        self.assertEqual(
            self.client.get(f"{self.endpoint}?status=draft").status_code,
            200,
        )
        self.assertEqual(
            self.client.get(f"{self.endpoint}{draft.id}/").status_code,
            200,
        )
        denied = self.client.patch(
            f"{self.endpoint}{draft.id}/", {"title": "Không được sửa"}, format="json"
        )
        self.assertEqual(denied.status_code, 403, denied.data)

    def test_published_document_is_immutable_through_api(self):
        published = self.create_guide(
            plant=self.sh, status="published", version="immutable"
        )
        self.client.force_authenticate(self.manager)
        response = self.client.patch(
            f"{self.endpoint}{published.id}/",
            {"quick_guide": "Nội dung bị thay đổi"},
            format="json",
        )
        self.assertEqual(response.status_code, 409, response.data)

    def test_publish_retire_and_create_next_version_lifecycle(self):
        old = self.create_guide(
            plant=self.sh, status="published", version="old", marker=b"old"
        )
        draft = self.create_guide(
            plant=self.sh, version="new", marker=b"new"
        )
        self.client.force_authenticate(self.publisher)
        published = self.client.post(f"{self.endpoint}{draft.id}/publish/", {})
        self.assertEqual(published.status_code, 200, published.data)
        old.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(old.status, ModuleGuide.STATUS_RETIRED)
        self.assertEqual(draft.status, ModuleGuide.STATUS_PUBLISHED)
        self.assertEqual(draft.approved_by, self.publisher)

        retired = self.client.post(
            f"{self.endpoint}{draft.id}/retire/", {"reason": "Thay quy trình"}
        )
        self.assertEqual(retired.status_code, 200, retired.data)
        self.client.force_authenticate(self.manager)
        copied = self.client.post(
            f"{self.endpoint}{draft.id}/create-next-version/",
            {"version_label": "next"},
            format="json",
        )
        self.assertEqual(copied.status_code, 201, copied.data)
        copied_guide = ModuleGuide.objects.get(pk=copied.data["id"])
        self.assertEqual(copied_guide.status, ModuleGuide.STATUS_DRAFT)
        self.assertEqual(copied_guide.checksum, draft.checksum)

    def test_duplicate_version_and_expired_publish_return_business_errors(self):
        source = self.create_guide(plant=self.sh, version="duplicate")
        self.client.force_authenticate(self.manager)
        duplicate = self.client.post(
            f"{self.endpoint}{source.id}/create-next-version/",
            {"version_label": "duplicate"},
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400, duplicate.data)

        source.effective_to = timezone.localdate() - timedelta(days=1)
        ModuleGuide.objects.filter(pk=source.pk).update(effective_to=source.effective_to)
        self.client.force_authenticate(self.publisher)
        expired = self.client.post(f"{self.endpoint}{source.id}/publish/", {})
        self.assertEqual(expired.status_code, 400, expired.data)

    def test_content_streaming_headers_metadata_and_audit(self):
        guide = self.create_guide(
            plant=self.sh, status="published", version="stream", marker=b"stream"
        )
        expected_checksum = hashlib.sha256(
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nstream\n%%EOF\n"
        ).hexdigest()
        self.assertEqual(guide.checksum, expected_checksum)
        self.client.force_authenticate(self.viewer)
        response = self.client.get(f"{self.endpoint}{guide.id}/content/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("no-store", response["Cache-Control"])
        log = UserActivityLog.objects.get(action_type="GUIDE_VIEW")
        self.assertEqual(log.user, self.viewer)
        self.assertEqual(log.nha_may, self.sh)
        self.assertIn(f"guide_id={guide.id}", log.description)
        self.assertIn(guide.checksum, log.description)
        self.assertIsNotNone(log.ip_address)

        with override_settings(USE_X_ACCEL_REDIRECT=True, DEBUG=False):
            accelerated = self.client.get(f"{self.endpoint}{guide.id}/content/")
        self.assertEqual(accelerated.status_code, 200)
        self.assertTrue(accelerated["X-Accel-Redirect"].startswith("/protected_media/"))

    def test_download_requires_permission_and_records_a_separate_audit_action(self):
        guide = self.create_guide(
            plant=self.sh, status="published", version="download-policy"
        )
        self.client.force_authenticate(self.publisher)
        denied = self.client.get(f"{self.endpoint}{guide.id}/content/?download=1")
        self.assertEqual(denied.status_code, 403, denied.data)

        self.client.force_authenticate(self.viewer)
        allowed = self.client.get(f"{self.endpoint}{guide.id}/content/?download=1")
        self.assertEqual(allowed.status_code, 200)
        audit = UserActivityLog.objects.get(action_type="GUIDE_DOWNLOAD")
        self.assertEqual(audit.user, self.viewer)
        self.assertEqual(audit.nha_may, self.sh)
        self.assertIn(f"guide_id={guide.id}", audit.description)
        self.assertIn(guide.checksum, audit.description)

    def test_replacing_draft_file_recalculates_all_metadata(self):
        draft = self.create_guide(
            plant=self.sh, version="metadata", marker=b"original"
        )
        old_checksum = draft.checksum
        self.client.force_authenticate(self.manager)
        response = self.client.patch(
            f"{self.endpoint}{draft.id}/",
            {"file": pdf_upload("replacement.pdf", b"replacement")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.data)
        draft.refresh_from_db()
        self.assertEqual(draft.original_filename, "replacement.pdf")
        self.assertEqual(draft.mime_type, "application/pdf")
        self.assertNotEqual(draft.checksum, old_checksum)
        self.assertEqual(draft.file_size, len(pdf_upload(marker=b"replacement").read()))

    def test_cross_plant_idor_blocks_read_and_every_mutating_action(self):
        operator = self.make_user(
            "guide-sh-operator",
            self.sh,
            can_view_module_guides=True,
            can_view_module_guide_history=True,
            can_manage_module_guides=True,
            can_publish_module_guides=True,
            can_download_module_guides=True,
        )
        foreign_draft = self.create_guide(
            plant=self.vs, creator=self.all_factory_manager, version="foreign-draft"
        )
        foreign_published = self.create_guide(
            plant=self.vs,
            creator=self.all_factory_manager,
            version="foreign-published",
            status="published",
        )
        global_draft = self.create_guide(
            plant=None, creator=self.all_factory_manager, version="global-draft"
        )
        local_draft = self.create_guide(plant=self.sh, version="local-scope")
        self.client.force_authenticate(operator)

        requests = (
            self.client.get(f"{self.endpoint}{foreign_draft.id}/"),
            self.client.get(f"{self.endpoint}{foreign_published.id}/content/"),
            self.client.patch(
                f"{self.endpoint}{foreign_draft.id}/", {"title": "IDOR"}, format="json"
            ),
            self.client.delete(f"{self.endpoint}{foreign_draft.id}/"),
            self.client.post(f"{self.endpoint}{foreign_draft.id}/publish/", {}),
            self.client.post(
                f"{self.endpoint}{foreign_published.id}/retire/",
                {"reason": "IDOR"},
                format="json",
            ),
            self.client.post(
                f"{self.endpoint}{foreign_published.id}/create-next-version/",
                {"version_label": "idor-next"},
                format="json",
            ),
            self.client.patch(
                f"{self.endpoint}{global_draft.id}/", {"title": "Global IDOR"}, format="json"
            ),
            self.client.patch(
                f"{self.endpoint}{local_draft.id}/",
                {"nha_may": self.vs.id},
                format="multipart",
            ),
        )
        self.assertEqual(
            [response.status_code for response in requests],
            [403] * len(requests),
            [getattr(response, "data", None) for response in requests],
        )

    def test_publish_and_retire_audits_contain_required_trace_fields(self):
        draft = self.create_guide(plant=self.sh, version="audit-lifecycle")
        self.client.force_authenticate(self.publisher)
        self.assertEqual(
            self.client.post(f"{self.endpoint}{draft.id}/publish/", {}).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                f"{self.endpoint}{draft.id}/retire/",
                {"reason": "Nghiệm thu audit"},
                format="json",
            ).status_code,
            200,
        )
        for action in ("GUIDE_PUBLISH", "GUIDE_RETIRE"):
            audit = UserActivityLog.objects.get(action_type=action)
            self.assertEqual(audit.user, self.publisher)
            self.assertEqual(audit.nha_may, self.sh)
            self.assertIsNotNone(audit.timestamp)
            self.assertIsNotNone(audit.ip_address)
            self.assertIn(f"guide_id={draft.id}", audit.description)
            self.assertIn(draft.checksum, audit.description)


class ModuleGuidePublishConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.media_dir = tempfile.mkdtemp(prefix="module-guide-race-")
        self.settings_override = override_settings(MEDIA_ROOT=self.media_dir)
        self.settings_override.enable()
        self.plant = NhaMay.objects.create(
            ma_nha_may="RACE", ten_nha_may="Nhà máy kiểm thử đồng thời"
        )
        self.user = get_user_model().objects.create_user(
            username="race-publisher",
            email="race-publisher@example.com",
            password="Guide-Safe-2026!",
        )
        self.first = self._guide("race-v1", b"race-one")
        self.second = self._guide("race-v2", b"race-two")

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_dir, ignore_errors=True)

    def _guide(self, version, marker):
        return ModuleGuide.objects.create(
            module_code="so_giao_nhan_ca_vh",
            nha_may=self.plant,
            title=f"Quy trình {version}",
            document_kind="procedure",
            is_primary=True,
            order=0,
            version_label=version,
            file=pdf_upload(f"{version}.pdf", marker),
            created_by=self.user,
        )

    def test_concurrent_publish_race_condition(self):
        first_has_lock = threading.Event()
        release_first = threading.Event()
        results = []
        original_lock = module_guide_service._acquire_publish_slot_lock

        def controlled_lock(guide):
            original_lock(guide)
            if threading.current_thread().name == "publisher-one":
                first_has_lock.set()
                self.assertTrue(release_first.wait(timeout=10))

        def publish(target_id, label):
            close_old_connections()
            try:
                publish_module_guide(target_id, self.user)
                results.append((label, "published"))
            except ModuleGuideConflict:
                results.append((label, "conflict"))
            finally:
                close_old_connections()

        from unittest.mock import patch

        with patch.object(
            module_guide_service,
            "_acquire_publish_slot_lock",
            side_effect=controlled_lock,
        ):
            first_thread = threading.Thread(
                target=publish,
                args=(self.first.id, "first"),
                name="publisher-one",
            )
            first_thread.start()
            self.assertTrue(first_has_lock.wait(timeout=10))
            second_thread = threading.Thread(
                target=publish,
                args=(self.second.id, "second"),
                name="publisher-two",
            )
            second_thread.start()
            second_thread.join(timeout=10)
            release_first.set()
            first_thread.join(timeout=10)

        self.assertFalse(first_thread.is_alive())
        self.assertFalse(second_thread.is_alive())
        self.assertCountEqual(results, [("first", "published"), ("second", "conflict")])
        self.assertEqual(
            ModuleGuide.objects.filter(status=ModuleGuide.STATUS_PUBLISHED).count(),
            1,
        )
