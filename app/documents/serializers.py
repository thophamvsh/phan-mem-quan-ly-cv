from pathlib import Path

from rest_framework import serializers

from documents.models import Document, DocumentChunk
from documents.services.normalization import canonicalize_doc_type


class DocumentSerializer(serializers.ModelSerializer):
    chunk_count = serializers.IntegerField(source="chunks.count", read_only=True)
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)

    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "original_file",
            "status",
            "factory",
            "document_type",
            "visibility",
            "version",
            "chunk_count",
            "created_by_name",
            "processed_at",
            "error_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "original_file",
            "status",
            "chunk_count",
            "created_by_name",
            "processed_at",
            "error_message",
            "created_at",
            "updated_at",
        )


class DocumentUploadSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)

    class Meta:
        model = Document
        fields = ("title", "file", "factory", "document_type", "visibility")

    def validate_file(self, value):
        suffix = Path(value.name or "").suffix.lower()
        if suffix == ".doc":
            raise serializers.ValidationError(
                "File .doc cu khong duoc Docling ho tro truc tiep. Hay chuyen file sang .docx hoac .pdf roi upload lai."
            )
        return value

    def validate_document_type(self, value):
        return canonicalize_doc_type(value)

    def create(self, validated_data):
        uploaded_file = validated_data.pop("file")
        if not validated_data.get("title"):
            validated_data["title"] = uploaded_file.name
        return Document.objects.create(original_file=uploaded_file, **validated_data)


class DocumentSearchSerializer(serializers.Serializer):
    query = serializers.CharField()
    factory = serializers.ChoiceField(choices=Document.FACTORY_CHOICES, required=False, allow_blank=True)
    document_type = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=12, default=5)

    def validate_document_type(self, value):
        return canonicalize_doc_type(value)


class DocumentChunkResultSerializer(serializers.Serializer):
    score = serializers.FloatField()
    document_id = serializers.IntegerField()
    document_title = serializers.CharField()
    factory = serializers.CharField()
    document_type = serializers.CharField(allow_blank=True)
    heading_path = serializers.CharField(allow_blank=True)
    chunk_index = serializers.IntegerField()
    content = serializers.CharField()
