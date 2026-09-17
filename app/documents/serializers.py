from pathlib import Path

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from documents.models import Document, DocumentChunk, DocumentFolder, ModuleGuide
from documents.services.normalization import canonicalize_doc_type


class DocumentFolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentFolder
        fields = ("id", "name", "slug", "description", "created_at", "updated_at")
        read_only_fields = ("id", "slug", "created_at", "updated_at")


class DocumentSerializer(serializers.ModelSerializer):
    chunk_count = serializers.IntegerField(source="chunks.count", read_only=True)
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)
    folders = DocumentFolderSerializer(many=True, read_only=True)

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
            "folders",
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
    folders = serializers.PrimaryKeyRelatedField(
        queryset=DocumentFolder.objects.all(), many=True, required=False
    )

    class Meta:
        model = Document
        fields = ("title", "file", "factory", "document_type", "visibility", "folders")

    def validate_file(self, value):
        suffix = Path(value.name or "").suffix.lower()
        if suffix == ".doc":
            raise serializers.ValidationError(
                "File .doc cu khong duoc Docling ho tro truc tiep. Hay chuyen file sang .docx hoac .pdf roi upload lai."
            )
        
        # Giới hạn dung lượng file tối đa là 50MB
        max_size = 50 * 1024 * 1024  # 50MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f"Kích thước file quá lớn ({value.size / (1024 * 1024):.1f}MB). Kích thước tối đa được phép là 50MB."
            )
            
        return value

    def validate_document_type(self, value):
        return canonicalize_doc_type(value)

    def create(self, validated_data):
        uploaded_file = validated_data.pop("file")
        folders = validated_data.pop("folders", [])
        if not validated_data.get("title"):
            validated_data["title"] = uploaded_file.name
        document = Document.objects.create(original_file=uploaded_file, **validated_data)
        if folders:
            document.folders.set(folders)
        return document


class DocumentUpdateSerializer(serializers.ModelSerializer):
    folders = serializers.PrimaryKeyRelatedField(
        queryset=DocumentFolder.objects.all(), many=True, required=False
    )

    class Meta:
        model = Document
        fields = ("title", "factory", "document_type", "folders")

    def validate_document_type(self, value):
        return canonicalize_doc_type(value)

    def update(self, instance, validated_data):
        folders = validated_data.pop("folders", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if folders is not None:
            instance.folders.set(folders)
        return instance


class DocumentSearchSerializer(serializers.Serializer):
    query = serializers.CharField()
    factory = serializers.ChoiceField(choices=Document.FACTORY_CHOICES, required=False, allow_blank=True)
    document_type = serializers.CharField(required=False, allow_blank=True)
    folder_id = serializers.IntegerField(required=False, allow_null=True)
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


class ModuleGuideSerializer(serializers.ModelSerializer):
    nha_may_name = serializers.CharField(source="nha_may.ten_nha_may", read_only=True)
    module_name = serializers.CharField(source="get_module_code_display", read_only=True)
    document_kind_name = serializers.CharField(
        source="get_document_kind_display", read_only=True
    )
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True
    )
    approved_by_name = serializers.CharField(
        source="approved_by.get_full_name", read_only=True
    )
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = ModuleGuide
        fields = (
            "id",
            "module_code",
            "module_name",
            "nha_may",
            "nha_may_name",
            "title",
            "document_kind",
            "document_kind_name",
            "is_primary",
            "order",
            "version_label",
            "status",
            "effective_from",
            "effective_to",
            "is_expired",
            "quick_guide",
            "file",
            "original_filename",
            "mime_type",
            "file_size",
            "checksum",
            "created_by",
            "created_by_name",
            "approved_by",
            "approved_by_name",
            "published_at",
            "retired_by",
            "retired_at",
            "retire_reason",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "original_filename",
            "mime_type",
            "file_size",
            "checksum",
            "created_by",
            "approved_by",
            "published_at",
            "retired_by",
            "retired_at",
            "retire_reason",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {"file": {"write_only": True, "required": True}}

    def validate(self, attrs):
        if self.instance and self.instance.status != ModuleGuide.STATUS_DRAFT:
            raise serializers.ValidationError(
                "Chỉ có thể chỉnh sửa tài liệu đang ở trạng thái dự thảo."
            )
        return attrs

    @staticmethod
    def _validation_detail(exc):
        if hasattr(exc, "message_dict"):
            return exc.message_dict
        return {"detail": exc.messages}

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(self._validation_detail(exc)) from exc

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(self._validation_detail(exc)) from exc


class ModuleGuideDetailSerializer(ModuleGuideSerializer):
    pass
