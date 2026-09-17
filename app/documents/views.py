import logging
import mimetypes
import os
import threading
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, close_old_connections, models, transaction
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404, HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework import generics, permissions, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from core.factory_scope import has_all_factory_access
from core.models import UserActivityLog
from core.signals import get_client_ip
from core.account_auth import AccountJWTAuthentication as JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from documents.models import Document, DocumentFolder, ModuleGuide
from documents.permissions import (
    CanAccessModuleGuideContent,
    CanManageModuleGuides,
    CanPublishModuleGuides,
    CanUseAiDocuments,
    CanViewModuleGuideHistory,
    CanViewModuleGuides,
    can_download_module_guides,
    can_review_module_guides,
    can_view_module_guide_history,
    has_ai_documents_permission,
)
from documents.serializers import (
    DocumentSearchSerializer,
    DocumentSerializer,
    DocumentUploadSerializer,
    DocumentFolderSerializer,
    DocumentUpdateSerializer,
    ModuleGuideDetailSerializer,
    ModuleGuideSerializer,
)
from documents.services.module_guide_service import (
    ModuleGuideConflict,
    create_next_version,
    publish_module_guide,
    retire_module_guide,
)
from documents.services.ingest import process_document
from documents.services.retrieval import (
    filter_documents_for_user,
    get_allowed_factories_for_user,
    search_documents,
)


logger = logging.getLogger(__name__)

DOCUMENT_CONTENT_TYPES = {
    ".csv": "text/csv",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}


def _run_process_in_background(document_id):
    def _bg_process():
        close_old_connections()
        try:
            document = Document.objects.get(pk=document_id)
            process_document(document)
        except Document.DoesNotExist:
            logger.warning("Document %s no longer exists before background processing started.", document_id)
        except Exception:
            logger.exception("Background processing failed for document %s.", document_id)
        finally:
            close_old_connections()

    threading.Thread(target=_bg_process, daemon=True).start()


def _enqueue_process_document(document_id):
    if getattr(settings, "DOCUMENTS_USE_CELERY", False):
        try:
            from documents.tasks import process_document_task

            process_document_task.delay(document_id)
            return
        except Exception:
            logger.exception("Could not enqueue document %s with Celery. Falling back to local thread.", document_id)

    _run_process_in_background(document_id)


class DocumentListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [CanUseAiDocuments]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        queryset = filter_documents_for_user(self.request.user).prefetch_related("chunks")
        factory = self.request.query_params.get("factory")
        status_value = self.request.query_params.get("status")
        folder_id = self.request.query_params.get("folder_id")
        if factory:
            queryset = queryset.filter(factory=factory)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if folder_id:
            queryset = queryset.filter(folders__id=folder_id)
        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return DocumentUploadSerializer
        return DocumentSerializer

    def perform_create(self, serializer):
        factory = serializer.validated_data.get("factory") or Document.FACTORY_GENERAL
        if factory not in get_allowed_factories_for_user(self.request.user):
            raise PermissionDenied("Ban khong co quyen tai tai lieu len pham vi nha may nay.")

        document = serializer.save(created_by=self.request.user)
        _enqueue_process_document(document.id)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        serializer.instance.refresh_from_db()
        output = DocumentSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)


class DocumentDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [CanUseAiDocuments]
    serializer_class = DocumentSerializer

    def get_queryset(self):
        return filter_documents_for_user(self.request.user).prefetch_related("chunks")

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return DocumentUpdateSerializer
        return DocumentSerializer


class DocumentReprocessAPIView(APIView):
    permission_classes = [CanUseAiDocuments]

    def post(self, request, pk):
        document = get_object_or_404(filter_documents_for_user(request.user), pk=pk)
        document.status = Document.STATUS_PROCESSING
        document.error_message = ""
        document.save(update_fields=["status", "error_message", "updated_at"])

        _enqueue_process_document(document.id)

        document.refresh_from_db()
        return Response(DocumentSerializer(document).data)


class DocumentSearchAPIView(APIView):
    permission_classes = [CanUseAiDocuments]

    def post(self, request):
        serializer = DocumentSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        results = search_documents(request.user, **serializer.validated_data)
        return Response({"results": results})


@method_decorator(xframe_options_exempt, name="dispatch")
class DocumentViewAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        user = None
        auth_header = request.headers.get("Authorization")
        token = request.query_params.get("token")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

        if token:
            try:
                jwt_authenticator = JWTAuthentication()
                validated_token = jwt_authenticator.get_validated_token(token)
                user = jwt_authenticator.get_user(validated_token)
            except (InvalidToken, TokenError):
                logger.warning("Invalid token used for document view %s.", pk)

        if not user or not user.is_authenticated:
            if request.user and request.user.is_authenticated:
                user = request.user

        if not user or not has_ai_documents_permission(user):
            raise Http404("Tài liệu không tồn tại hoặc bạn không có quyền xem.")

        try:
            document = filter_documents_for_user(user).get(pk=pk)
        except Document.DoesNotExist:
            raise Http404("Tài liệu không tồn tại hoặc bạn không có quyền xem.")

        if not document.original_file:
            raise Http404("Tài liệu này không có file đính kèm.")

        file_path = document.original_file.path
        if not os.path.exists(file_path):
            raise Http404("File tài liệu vật lý không tìm thấy trên server.")

        extension = os.path.splitext(file_path)[1].lower()
        content_type = DOCUMENT_CONTENT_TYPES.get(extension) or mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        return FileResponse(
            open(file_path, "rb"),
            content_type=content_type,
            filename=os.path.basename(file_path),
        )


class DocumentFolderViewSet(viewsets.ModelViewSet):
    permission_classes = [CanUseAiDocuments]
    serializer_class = DocumentFolderSerializer
    queryset = DocumentFolder.objects.all().order_by("name")


def _scoped_guide_or_404(user, pk):
    guide = get_object_or_404(ModuleGuide.objects.select_related("nha_may"), pk=pk)
    if guide.nha_may_id and not has_all_factory_access(user):
        user_plant_id = getattr(getattr(user, "profile", None), "nha_may_id", None)
        if user_plant_id != guide.nha_may_id:
            raise PermissionDenied("Bạn không có quyền truy cập tài liệu của nhà máy khác.")
    return guide


def _enforce_guide_mutation_scope(user, guide):
    if has_all_factory_access(user):
        return
    user_plant_id = getattr(getattr(user, "profile", None), "nha_may_id", None)
    if guide.nha_may_id is None or guide.nha_may_id != user_plant_id:
        raise PermissionDenied(
            "Bạn không có quyền thay đổi tài liệu chung hoặc tài liệu của nhà máy khác."
        )


def _raise_drf_validation(exc):
    detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
    raise DRFValidationError(detail) from exc


def _log_guide_action(request, guide, action, extra=None):
    details = {
        "guide_id": guide.id,
        "module_code": guide.module_code,
        "version_label": guide.version_label,
        "checksum": guide.checksum,
    }
    if extra:
        details.update(extra)
    UserActivityLog.objects.create(
        user=request.user,
        action_type=f"GUIDE_{action.upper()}",
        description=" | ".join(f"{key}={value}" for key, value in details.items()),
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
        nha_may=guide.nha_may,
    )


class ModuleGuideListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ModuleGuideSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_permissions(self):
        permission_classes = (
            (permissions.IsAuthenticated, CanManageModuleGuides)
            if self.request.method == "POST"
            else (permissions.IsAuthenticated, CanViewModuleGuides)
        )
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user
        can_review = can_review_module_guides(user)
        queryset = ModuleGuide.objects.select_related(
            "nha_may", "created_by", "approved_by"
        )
        requested_status = self.request.query_params.get("status")
        if not can_review:
            queryset = queryset.filter(status=ModuleGuide.STATUS_PUBLISHED)
        elif requested_status:
            valid_statuses = {choice[0] for choice in ModuleGuide.STATUS_CHOICES}
            if requested_status not in valid_statuses:
                raise DRFValidationError({"status": "Trạng thái tài liệu không hợp lệ."})
            queryset = queryset.filter(status=requested_status)

        module_code = self.request.query_params.get("module_code")
        if module_code:
            queryset = queryset.filter(module_code=module_code)

        if has_all_factory_access(user):
            requested_plant = self.request.query_params.get("nha_may")
            management_mode = self.request.query_params.get("is_management") == "1"
            if not requested_plant and not (can_review and management_mode):
                raise DRFValidationError(
                    {"nha_may": "Vui lòng chọn nhà máy cần tra cứu."}
                )
            if requested_plant:
                queryset = queryset.filter(
                    models.Q(nha_may_id=requested_plant)
                    | models.Q(nha_may__isnull=True)
                )
        else:
            user_plant_id = getattr(getattr(user, "profile", None), "nha_may_id", None)
            if user_plant_id:
                queryset = queryset.filter(
                    models.Q(nha_may_id=user_plant_id)
                    | models.Q(nha_may__isnull=True)
                )
            else:
                queryset = queryset.filter(nha_may__isnull=True)

        return queryset.annotate(
            is_plant_specific=models.Case(
                models.When(nha_may__isnull=False, then=models.Value(1)),
                default=models.Value(0),
                output_field=models.IntegerField(),
            )
        ).order_by("-is_primary", "-is_plant_specific", "order", "-published_at")

    def perform_create(self, serializer):
        user = self.request.user
        requested_plant = serializer.validated_data.get("nha_may")
        if has_all_factory_access(user):
            serializer.save(created_by=user, status=ModuleGuide.STATUS_DRAFT)
            return
        profile = getattr(user, "profile", None)
        user_plant = getattr(profile, "nha_may", None)
        if not user_plant or not requested_plant or requested_plant.pk != user_plant.pk:
            raise PermissionDenied("Bạn chỉ được tạo tài liệu cho nhà máy được phân công.")
        serializer.save(
            created_by=user,
            nha_may=user_plant,
            status=ModuleGuide.STATUS_DRAFT,
        )


class ModuleGuideDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ModuleGuideDetailSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_permissions(self):
        permission_classes = (
            (permissions.IsAuthenticated, CanManageModuleGuides)
            if self.request.method in ("PUT", "PATCH", "DELETE")
            else (permissions.IsAuthenticated, CanAccessModuleGuideContent)
        )
        return [permission() for permission in permission_classes]

    def get_object(self):
        guide = _scoped_guide_or_404(self.request.user, self.kwargs["pk"])
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            _enforce_guide_mutation_scope(self.request.user, guide)
            if guide.status != ModuleGuide.STATUS_DRAFT:
                raise ModuleGuideConflict("Chỉ được thay đổi tài liệu dự thảo.")
        elif guide.status == ModuleGuide.STATUS_DRAFT:
            if not can_review_module_guides(self.request.user):
                raise PermissionDenied("Bạn không có quyền xem tài liệu dự thảo.")
        elif guide.status == ModuleGuide.STATUS_RETIRED:
            if not can_view_module_guide_history(self.request.user):
                raise PermissionDenied("Bạn không có quyền xem tài liệu đã thu hồi.")
        self.check_object_permissions(self.request, guide)
        return guide

    def perform_update(self, serializer):
        requested_plant = serializer.validated_data.get(
            "nha_may", serializer.instance.nha_may
        )
        if not has_all_factory_access(self.request.user):
            user_plant_id = getattr(
                getattr(self.request.user, "profile", None), "nha_may_id", None
            )
            if not requested_plant or requested_plant.pk != user_plant_id:
                raise PermissionDenied("Bạn không được chuyển tài liệu sang phạm vi khác.")
        serializer.save()


class ModuleGuideContentAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, CanAccessModuleGuideContent)

    def get(self, request, pk):
        guide = _scoped_guide_or_404(request.user, pk)
        if guide.status == ModuleGuide.STATUS_DRAFT and not can_review_module_guides(request.user):
            raise PermissionDenied("Bạn không có quyền mở tài liệu dự thảo.")
        if guide.status == ModuleGuide.STATUS_RETIRED and not can_view_module_guide_history(
            request.user
        ):
            raise PermissionDenied("Bạn không có quyền mở tài liệu đã thu hồi.")

        is_download = request.query_params.get("download") == "1"
        if is_download and not can_download_module_guides(request.user):
            raise PermissionDenied("Bạn không có quyền tải tài liệu.")
        if not guide.file:
            raise Http404("Tài liệu không có file đính kèm.")

        _log_guide_action(
            request,
            guide,
            "download" if is_download else "view",
            {"status": guide.status},
        )
        disposition = "attachment" if is_download else "inline"
        encoded_filename = quote(guide.original_filename or "document", safe="")
        content_disposition = f"{disposition}; filename*=UTF-8''{encoded_filename}"

        if getattr(settings, "USE_X_ACCEL_REDIRECT", False) and not settings.DEBUG:
            response = HttpResponse()
            response["Content-Type"] = guide.mime_type
            response["Content-Disposition"] = content_disposition
            response["X-Accel-Redirect"] = f"/protected_media/{quote(guide.file.name, safe='/')}"
        else:
            response = FileResponse(
                guide.file.open("rb"),
                content_type=guide.mime_type,
                as_attachment=is_download,
                filename=guide.original_filename,
            )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-cache, no-store, must-revalidate"
        return response


class ModuleGuidePublishAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, CanPublishModuleGuides)

    def post(self, request, pk):
        target = _scoped_guide_or_404(request.user, pk)
        _enforce_guide_mutation_scope(request.user, target)
        try:
            with transaction.atomic():
                guide = publish_module_guide(target.id, request.user)
        except IntegrityError as exc:
            raise ModuleGuideConflict() from exc
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        _log_guide_action(request, guide, "publish")
        return Response(ModuleGuideDetailSerializer(guide).data)


class ModuleGuideRetireAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, CanPublishModuleGuides)

    def post(self, request, pk):
        target = _scoped_guide_or_404(request.user, pk)
        _enforce_guide_mutation_scope(request.user, target)
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            raise DRFValidationError({"reason": "Vui lòng nhập lý do thu hồi."})
        try:
            guide = retire_module_guide(target.id, request.user, reason)
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        _log_guide_action(request, guide, "retire", {"reason": reason})
        return Response(ModuleGuideDetailSerializer(guide).data)


class ModuleGuideCreateNextVersionAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, CanManageModuleGuides)

    def post(self, request, pk):
        target = _scoped_guide_or_404(request.user, pk)
        _enforce_guide_mutation_scope(request.user, target)
        version_label = str(request.data.get("version_label", "")).strip()
        try:
            guide = create_next_version(target.id, version_label, request.user)
        except IntegrityError as exc:
            raise ModuleGuideConflict("Phiên bản này vừa được tạo.") from exc
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        _log_guide_action(request, guide, "create_version")
        return Response(ModuleGuideDetailSerializer(guide).data, status=status.HTTP_201_CREATED)


class ModuleGuideHistoryAPIView(generics.ListAPIView):
    serializer_class = ModuleGuideSerializer
    permission_classes = (permissions.IsAuthenticated, CanViewModuleGuideHistory)

    def get_queryset(self):
        user = self.request.user
        queryset = ModuleGuide.objects.select_related("nha_may", "created_by").filter(
            status=ModuleGuide.STATUS_RETIRED
        )
        module_code = self.request.query_params.get("module_code")
        if module_code:
            queryset = queryset.filter(module_code=module_code)
        if has_all_factory_access(user):
            plant = self.request.query_params.get("nha_may")
            if plant:
                queryset = queryset.filter(
                    models.Q(nha_may_id=plant) | models.Q(nha_may__isnull=True)
                )
        else:
            plant_id = getattr(getattr(user, "profile", None), "nha_may_id", None)
            queryset = (
                queryset.filter(
                    models.Q(nha_may_id=plant_id) | models.Q(nha_may__isnull=True)
                )
                if plant_id
                else queryset.filter(nha_may__isnull=True)
            )
        return queryset.order_by("-published_at", "-created_at")
