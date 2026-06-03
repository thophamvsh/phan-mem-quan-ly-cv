from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_tools.permissions import CanUseAiTools
from documents.models import Document
from documents.serializers import (
    DocumentSearchSerializer,
    DocumentSerializer,
    DocumentUploadSerializer,
)
from documents.services.ingest import process_document
from documents.services.retrieval import filter_documents_for_user, search_documents


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
        try:
            process_document(document)
        except Exception:
            document.refresh_from_db()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
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
        try:
            process_document(document)
        except Exception:
            document.refresh_from_db()
            return Response(DocumentSerializer(document).data, status=status.HTTP_200_OK)
        return Response(DocumentSerializer(document).data)


class DocumentSearchAPIView(APIView):
    permission_classes = [CanUseAiTools]

    def post(self, request):
        serializer = DocumentSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        results = search_documents(request.user, **serializer.validated_data)
        return Response({"results": results})
