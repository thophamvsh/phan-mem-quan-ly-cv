import json
import re

from rest_framework import serializers

from nhatkyvanhanh.models.command_template import MauNoiDungVanHanh, NHOM_MAU_CHOICES


ALLOWED_PARAM_TYPES = {"text", "select", "number", "time", "checkbox", "device"}
ALLOWED_OPTIONS_SOURCES = {
    "plants",
    "units",
    "transformers",
    "breakers",
    "dispatchers",
    "frequencies",
    "purposes",
    "plantUnits",
    "spillwayGates",
}
MAX_PARAMS_COUNT = 20
MAX_JSON_PAYLOAD_SIZE = 50 * 1024  # 50 KB


class MauNoiDungVanHanhSerializer(serializers.ModelSerializer):
    nha_may_code = serializers.CharField(source="nha_may.ma_nha_may", read_only=True)
    nha_may_name = serializers.CharField(source="nha_may.ten_nha_may", read_only=True)
    nguoi_tao_name = serializers.SerializerMethodField()
    nguoi_cap_nhat_name = serializers.SerializerMethodField()
    # Field hỗ trợ kiểm soát cập nhật đồng thời (Optimistic Concurrency Control)
    updated_at_client = serializers.CharField(required=False, write_only=True, allow_blank=True)

    class Meta:
        model = MauNoiDungVanHanh
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "ma_mau",
            "ten_mau",
            "nhom_mau",
            "dinh_dang_tieu_de",
            "dinh_dang_mau",
            "danh_sach_tham_so",
            "thu_tu",
            "phien_ban",
            "dang_ap_dung",
            "la_mau_he_thong",
            "ghi_chu",
            "nguoi_tao",
            "nguoi_tao_name",
            "nguoi_cap_nhat",
            "nguoi_cap_nhat_name",
            "created_at",
            "updated_at",
            "updated_at_client",
        ]
        read_only_fields = [
            "id",
            "phien_ban",
            "la_mau_he_thong",
            "nguoi_tao",
            "nguoi_cap_nhat",
            "created_at",
            "updated_at",
        ]

    def get_nguoi_tao_name(self, obj):
        if not obj.nguoi_tao:
            return None
        profile = getattr(obj.nguoi_tao, "profile", None)
        if profile and getattr(profile, "ho_ten", None):
            return profile.ho_ten
        full = f"{getattr(obj.nguoi_tao, 'first_name', '')} {getattr(obj.nguoi_tao, 'last_name', '')}".strip()
        return full or getattr(obj.nguoi_tao, "username", "") or getattr(obj.nguoi_tao, "email", "")

    def get_nguoi_cap_nhat_name(self, obj):
        if not obj.nguoi_cap_nhat:
            return None
        profile = getattr(obj.nguoi_cap_nhat, "profile", None)
        if profile and getattr(profile, "ho_ten", None):
            return profile.ho_ten
        full = f"{getattr(obj.nguoi_cap_nhat, 'first_name', '')} {getattr(obj.nguoi_cap_nhat, 'last_name', '')}".strip()
        return full or getattr(obj.nguoi_cap_nhat, "username", "") or getattr(obj.nguoi_cap_nhat, "email", "")

    def validate_ma_mau(self, value):
        val = str(value or "").strip()
        if not val:
            raise serializers.ValidationError("Mã mẫu không được để trống.")
        if not re.match(r"^[a-zA-Z0-9_-]+$", val):
            raise serializers.ValidationError("Mã mẫu chỉ được chứa chữ cái, số, dấu gạch ngang và gạch dưới.")
        return val

    def validate_dinh_dang_tieu_de(self, value):
        val = str(value or "").strip()
        if not val:
            raise serializers.ValidationError("Định dạng tiêu đề không được để trống.")
        # Kiểm tra ký tự điều khiển ASCII
        if re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", val):
            raise serializers.ValidationError("Định dạng tiêu đề chứa ký tự điều khiển không hợp lệ.")
        # Kiểm tra cân bằng ngoặc nhọn
        if val.count("{") != val.count("}"):
            raise serializers.ValidationError("Định dạng tiêu đề có ngoặc nhọn '{' và '}' không cân bằng.")
        return val

    def validate_dinh_dang_mau(self, value):
        val = str(value or "").strip()
        if not val:
            raise serializers.ValidationError("Định dạng nội dung mẫu không được để trống.")
        # Kiểm tra ký tự điều khiển ASCII
        if re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", val):
            raise serializers.ValidationError("Định dạng nội dung mẫu chứa ký tự điều khiển không hợp lệ.")
        # Kiểm tra cân bằng ngoặc nhọn
        if val.count("{") != val.count("}"):
            raise serializers.ValidationError("Định dạng nội dung mẫu có ngoặc nhọn '{' và '}' không cân bằng.")
        return val

    def validate_danh_sach_tham_so(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Danh sách tham số phải là một mảng (list).")

        # DoS guard: Giới hạn số lượng tham số
        if len(value) > MAX_PARAMS_COUNT:
            raise serializers.ValidationError(
                f"Số lượng tham số tối đa là {MAX_PARAMS_COUNT}, hiện có {len(value)}."
            )

        # DoS guard: Giới hạn kích thước payload JSON
        raw_json_size = len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
        if raw_json_size > MAX_JSON_PAYLOAD_SIZE:
            raise serializers.ValidationError("Kích thước danh sách tham số vượt quá giới hạn 50 KB.")

        param_keys = []
        for idx, param in enumerate(value):
            if not isinstance(param, dict):
                raise serializers.ValidationError(f"Tham số thứ {idx + 1} phải là một đối tượng (dict).")

            key = str(param.get("key") or "").strip()
            if not key:
                raise serializers.ValidationError(f"Tham số thứ {idx + 1} thiếu trường 'key'.")
            if not re.match(r"^[a-zA-Z0-9_]+$", key):
                raise serializers.ValidationError(f"Mã tham số '{key}' không hợp lệ (chỉ chấp nhận a-z, 0-9, _).")

            if key in param_keys:
                raise serializers.ValidationError(f"Mã tham số '{key}' bị lặp lại trong danh sách.")
            param_keys.append(key)

            label = str(param.get("label") or "").strip()
            if not label:
                raise serializers.ValidationError(f"Tham số '{key}' thiếu trường nhãn hiển thị 'label'.")

            param_type = str(param.get("type") or "").strip()
            if param_type not in ALLOWED_PARAM_TYPES:
                raise serializers.ValidationError(
                    f"Kiểu tham số '{param_type}' của '{key}' không được hỗ trợ. "
                    f"Các kiểu cho phép: {', '.join(sorted(ALLOWED_PARAM_TYPES))}."
                )

            # Kiểm tra riêng cho kiểu select
            if param_type == "select":
                options = param.get("options")
                options_source = param.get("optionsSource")
                default_val = param.get("default")

                if not options and not options_source:
                    raise serializers.ValidationError(
                        f"Tham số kiểu select '{key}' phải có trường 'options' hoặc 'optionsSource'."
                    )

                if options_source and options_source not in ALLOWED_OPTIONS_SOURCES:
                    raise serializers.ValidationError(
                        f"Nguồn danh mục '{options_source}' của tham số '{key}' không hợp lệ. "
                        f"Cho phép: {', '.join(sorted(ALLOWED_OPTIONS_SOURCES))}."
                    )

                if options is not None:
                    if not isinstance(options, list) or len(options) == 0:
                        raise serializers.ValidationError(
                            f"Trường 'options' của tham số '{key}' phải là danh sách không rỗng."
                        )
                    if default_val is not None and default_val not in options:
                        raise serializers.ValidationError(
                            f"Giá trị mặc định '{default_val}' của tham số '{key}' không nằm trong danh mục options."
                        )

        return value

    def validate(self, attrs):
        title = attrs.get("dinh_dang_tieu_de") or (self.instance and self.instance.dinh_dang_tieu_de) or ""
        content = attrs.get("dinh_dang_mau") or (self.instance and self.instance.dinh_dang_mau) or ""
        params = attrs.get("danh_sach_tham_so")
        if params is None and self.instance:
            params = self.instance.danh_sach_tham_so
        params = params or []

        # Trích xuất tất cả placeholder từ tiêu đề và nội dung
        title_placeholders = set(re.findall(r"\{([a-zA-Z0-9_]+)\}", title))
        content_placeholders = set(re.findall(r"\{([a-zA-Z0-9_]+)\}", content))
        all_placeholders = title_placeholders | content_placeholders

        # Đối chiếu với danh sách tham số
        param_keys = {p.get("key") for p in params if isinstance(p, dict)}
        missing_params = all_placeholders - param_keys
        if missing_params:
            raise serializers.ValidationError({
                "danh_sach_tham_so": (
                    f"Thiếu định nghĩa tham số cho các placeholder sau: {', '.join(sorted(missing_params))}."
                )
            })

        return attrs
