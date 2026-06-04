from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_tools.permissions import CanUseAiTools, has_ai_tools_permission
from documents.models import Document
from documents.serializers import (
    DocumentSearchSerializer,
    DocumentSerializer,
    DocumentUploadSerializer,
)
import threading
from django.db import close_old_connections
from documents.services.ingest import process_document
from documents.services.retrieval import filter_documents_for_user, search_documents


def _run_process_in_background(document_id):
    def _bg_process():
        close_old_connections()
        try:
            from documents.models import Document
            document = Document.objects.get(pk=document_id)
            process_document(document)
        except Exception:
            pass
        finally:
            close_old_connections()

    threading.Thread(target=_bg_process, daemon=True).start()


class DocumentListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [CanUseAiTools]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        queryset = filter_documents_for_user(self.request.user).prefetch_related("chunks")
        factory = self.request.query_params.get("factory")
        status_value = self.request.query_params.get("status")
        if factory:
            queryset = queryset.filter(factory=factory)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return DocumentUploadSerializer
        return DocumentSerializer

    def perform_create(self, serializer):
        document = serializer.save(created_by=self.request.user)
        _run_process_in_background(document.id)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        serializer.instance.refresh_from_db()
        output = DocumentSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)


class DocumentDetailAPIView(generics.RetrieveDestroyAPIView):
    permission_classes = [CanUseAiTools]
    serializer_class = DocumentSerializer

    def get_queryset(self):
        return filter_documents_for_user(self.request.user).prefetch_related("chunks")


class DocumentReprocessAPIView(APIView):
    permission_classes = [CanUseAiTools]

    def post(self, request, pk):
        document = filter_documents_for_user(request.user).get(pk=pk)
        document.status = Document.STATUS_PROCESSING
        document.error_message = ""
        document.save(update_fields=["status", "error_message", "updated_at"])

        _run_process_in_background(document.id)

        document.refresh_from_db()
        return Response(DocumentSerializer(document).data)


class DocumentSearchAPIView(APIView):
    permission_classes = [CanUseAiTools]

    def post(self, request):
        serializer = DocumentSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        results = search_documents(request.user, **serializer.validated_data)
        return Response({"results": results})


from django.http import FileResponse, Http404
import os
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

@method_decorator(xframe_options_exempt, name='dispatch')
class DocumentViewAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        user = None
        auth_header = request.headers.get("Authorization")
        token = request.query_params.get("token")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if token:
            try:
                jwt_authenticator = JWTAuthentication()
                validated_token = jwt_authenticator.get_validated_token(token)
                user = jwt_authenticator.get_user(validated_token)
            except (InvalidToken, TokenError):
                pass

        if not user or not user.is_authenticated:
            if request.user and request.user.is_authenticated:
                user = request.user

        if not user or not has_ai_tools_permission(user):
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

        response = FileResponse(open(file_path, "rb"), content_type="application/pdf")
        return response
