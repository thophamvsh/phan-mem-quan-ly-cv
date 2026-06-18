import logging
import mimetypes
import os
import threading

from django.conf import settings
from django.db import close_old_connections
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework import generics, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from documents.models import Document, DocumentFolder
from documents.permissions import CanUseAiDocuments, has_ai_documents_permission
from documents.serializers import (
    DocumentSearchSerializer,
    DocumentSerializer,
    DocumentUploadSerializer,
    DocumentFolderSerializer,
    DocumentUpdateSerializer,
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
