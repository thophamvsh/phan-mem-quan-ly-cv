from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from core.factory_scope import filter_queryset_by_factory
from quanlyvanhanh.models import ThietBi
from nhatkyvanhanh.models import SuKien, ChiDaoSuKien, DienBienSuKien, KhacPhucSuKien
from .mixins import UserSummaryMixin, user_can_edit_chi_dao

class DienBienSuKienSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()
    chu_ky_nguoi_tao_url = serializers.SerializerMethodField()

    class Meta:
        model = DienBienSuKien
        fields = [
            "id",
            "su_kien",
            "thoi_gian_dien_bien",
            "noi_dung",
            "nguoi_tao",
            "nguoi_tao_display",
            "chu_ky_nguoi_tao_url",
            "chuc_danh_nguoi_tao",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nguoi_tao",
            "nguoi_tao_display",
            "chu_ky_nguoi_tao_url",
            "chuc_danh_nguoi_tao",
            "created_at",
            "updated_at",
        ]

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)

    def get_chu_ky_nguoi_tao_url(self, obj):
        try:
            chu_ky = obj.nguoi_tao.profile.chu_ky
        except Exception:
            return None
        return self._build_file_url(chu_ky)


class KhacPhucSuKienSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()
    ben_xu_ly_su_kien_thiet_bi_display = serializers.SerializerMethodField()
    nguoi_xac_nhan_xu_ly_display = serializers.SerializerMethodField()
    hinh_anh_sau_xu_ly_url = serializers.SerializerMethodField()
    chu_ky_ben_xu_ly_su_kien_thiet_bi_url = serializers.SerializerMethodField()
    chu_ky_nguoi_xac_nhan_xu_ly_url = serializers.SerializerMethodField()

    class Meta:
        model = KhacPhucSuKien
        fields = [
            "id",
            "su_kien",
            "nguoi_tao",
            "nguoi_tao_display",
            "qua_trinh_xu_ly",
            "thoi_gian_xu_ly",
            "ket_qua_kiem_tra_nguyen_nhan",
            "noi_dung_xu_ly_khac_phuc",
            "de_xuat_lien_quan",
            "ket_qua_sau_xu_ly",
            "hinh_anh_sau_xu_ly",
            "hinh_anh_sau_xu_ly_url",
            "chu_ky_ben_xu_ly_su_kien_thiet_bi",
            "chu_ky_ben_xu_ly_su_kien_thiet_bi_url",
            "chu_ky_nguoi_xac_nhan_xu_ly",
            "chu_ky_nguoi_xac_nhan_xu_ly_url",
            "ben_xu_ly_su_kien_thiet_bi",
            "ben_xu_ly_su_kien_thiet_bi_display",
            "nguoi_xac_nhan_xu_ly",
            "nguoi_xac_nhan_xu_ly_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nguoi_tao",
            "nguoi_tao_display",
            "chu_ky_ben_xu_ly_su_kien_thiet_bi",
            "chu_ky_ben_xu_ly_su_kien_thiet_bi_url",
            "chu_ky_nguoi_xac_nhan_xu_ly",
            "chu_ky_nguoi_xac_nhan_xu_ly_url",
            "created_at",
            "updated_at",
        ]

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)

    def get_ben_xu_ly_su_kien_thiet_bi_display(self, obj):
        return self._get_user_display(obj.ben_xu_ly_su_kien_thiet_bi)

    def get_nguoi_xac_nhan_xu_ly_display(self, obj):
        return self._get_user_display(obj.nguoi_xac_nhan_xu_ly)

    def get_hinh_anh_sau_xu_ly_url(self, obj):
        return self._build_file_url(obj.hinh_anh_sau_xu_ly)

    def get_chu_ky_ben_xu_ly_su_kien_thiet_bi_url(self, obj):
        return self._build_file_url(obj.chu_ky_ben_xu_ly_su_kien_thiet_bi)

    def get_chu_ky_nguoi_xac_nhan_xu_ly_url(self, obj):
        return self._build_file_url(obj.chu_ky_nguoi_xac_nhan_xu_ly)


class ChiDaoSuKienSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_chi_dao_display = serializers.SerializerMethodField()
    chu_ky_nguoi_chi_dao_url = serializers.SerializerMethodField()

    class Meta:
        model = ChiDaoSuKien
        fields = [
            "id",
            "su_kien",
            "noi_dung",
            "nguoi_chi_dao",
            "nguoi_chi_dao_display",
            "chuc_danh_nguoi_chi_dao",
            "chu_ky_nguoi_chi_dao",
            "chu_ky_nguoi_chi_dao_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "su_kien",
            "nguoi_chi_dao",
            "nguoi_chi_dao_display",
            "chuc_danh_nguoi_chi_dao",
            "chu_ky_nguoi_chi_dao",
            "chu_ky_nguoi_chi_dao_url",
            "created_at",
            "updated_at",
        ]

    def validate_noi_dung(self, value):
        if not str(value or "").strip():
            raise serializers.ValidationError("Can nhap noi dung chi dao.")
        return value

    def get_nguoi_chi_dao_display(self, obj):
        return self._get_user_display(obj.nguoi_chi_dao)

    def get_chu_ky_nguoi_chi_dao_url(self, obj):
        return self._build_file_url(obj.chu_ky_nguoi_chi_dao)


class NhatKySuKienSerializer(serializers.ModelSerializer, UserSummaryMixin):
    ten_he_thong_thiet_bi = serializers.CharField(required=False, allow_blank=True)
    thiet_bi = serializers.PrimaryKeyRelatedField(
        required=False,
        allow_null=True,
        queryset=ThietBi.objects.all(),
    )
    thiet_bi_ten = serializers.CharField(source="thiet_bi.ten", read_only=True)
    thiet_bi_ma_day_du = serializers.CharField(source="thiet_bi.ma_day_du", read_only=True)
    qua_trinh_xu_ly = serializers.CharField(required=False, allow_blank=True)
    thoi_gian_xu_ly = serializers.DateTimeField(required=False, allow_null=True)
    ket_qua_kiem_tra_nguyen_nhan = serializers.CharField(required=False, allow_blank=True)
    noi_dung_xu_ly_khac_phuc = serializers.CharField(required=False, allow_blank=True)
    de_xuat_lien_quan = serializers.CharField(required=False, allow_blank=True)
    ket_qua_sau_xu_ly = serializers.CharField(required=False, allow_blank=True)
    hinh_anh_sau_xu_ly = serializers.ImageField(required=False, allow_null=True)
    ben_xu_ly_su_kien_thiet_bi = serializers.PrimaryKeyRelatedField(
        required=False,
        allow_null=True,
        queryset=KhacPhucSuKien._meta.get_field("ben_xu_ly_su_kien_thiet_bi").remote_field.model.objects.all(),
    )
    nguoi_xac_nhan_xu_ly = serializers.PrimaryKeyRelatedField(
        required=False,
        allow_null=True,
        queryset=KhacPhucSuKien._meta.get_field("nguoi_xac_nhan_xu_ly").remote_field.model.objects.all(),
    )

    nguoi_tao_display = serializers.SerializerMethodField()
    chu_ky_nguoi_tao_url = serializers.SerializerMethodField()
    nguoi_chi_dao_display = serializers.SerializerMethodField()
    chu_ky_nguoi_chi_dao_url = serializers.SerializerMethodField()
    ben_ghi_nhan_su_kien_display = serializers.SerializerMethodField()
    ben_xu_ly_su_kien_thiet_bi_display = serializers.SerializerMethodField()
    nguoi_xac_nhan_xu_ly_display = serializers.SerializerMethodField()
    hinh_anh_truoc_su_co_url = serializers.SerializerMethodField()
    hinh_anh_sau_xu_ly_url = serializers.SerializerMethodField()
    chu_ky_ben_ghi_nhan_su_kien_url = serializers.SerializerMethodField()
    chu_ky_ben_xu_ly_su_kien_thiet_bi_url = serializers.SerializerMethodField()
    chu_ky_nguoi_xac_nhan_xu_ly_url = serializers.SerializerMethodField()
    khac_phuc_su_kiens = KhacPhucSuKienSerializer(many=True, read_only=True)
    dien_bien_su_kiens = DienBienSuKienSerializer(many=True, read_only=True)
    chi_dao_su_kiens = ChiDaoSuKienSerializer(many=True, read_only=True)
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    can_edit_chi_dao = serializers.SerializerMethodField()

    class Meta:
        model = SuKien
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "thoi_gian_xay_ra",
            "thiet_bi",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "ten_he_thong_thiet_bi",
            "loai",
            "hien_tuong_dien_bien",
            "phan_tich_nguyen_nhan",
            "qua_trinh_kiem_tra",
            "qua_trinh_xu_ly",
            "chi_dao",
            "nguoi_chi_dao",
            "nguoi_chi_dao_display",
            "chu_ky_nguoi_chi_dao",
            "chu_ky_nguoi_chi_dao_url",
            "de_xuat_khac_phuc",
            "bao_cho",
            "thoi_gian_xu_ly",
            "ket_qua_kiem_tra_nguyen_nhan",
            "noi_dung_xu_ly_khac_phuc",
            "de_xuat_lien_quan",
            "ket_qua_sau_xu_ly",
            "hinh_anh_truoc_su_co",
            "hinh_anh_truoc_su_co_url",
            "hinh_anh_sau_xu_ly",
            "hinh_anh_sau_xu_ly_url",
            "chu_ky_ben_ghi_nhan_su_kien",
            "chu_ky_ben_ghi_nhan_su_kien_url",
            "chu_ky_ben_xu_ly_su_kien_thiet_bi_url",
            "chu_ky_nguoi_xac_nhan_xu_ly_url",
            "trang_thai",
            "nguoi_tao",
            "nguoi_tao_display",
            "chu_ky_nguoi_tao_url",
            "ben_ghi_nhan_su_kien",
            "ben_ghi_nhan_su_kien_display",
            "ben_xu_ly_su_kien_thiet_bi",
            "ben_xu_ly_su_kien_thiet_bi_display",
            "nguoi_xac_nhan_xu_ly",
            "nguoi_xac_nhan_xu_ly_display",
            "dien_bien_su_kiens",
            "khac_phuc_su_kiens",
            "chi_dao_su_kiens",
            "can_edit_chi_dao",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may_code",
            "nha_may_name",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "can_edit_chi_dao",
            "nguoi_tao",
            "nguoi_tao_display",
            "chu_ky_nguoi_tao_url",
            "nguoi_chi_dao",
            "nguoi_chi_dao_display",
            "chu_ky_nguoi_chi_dao",
            "chu_ky_nguoi_chi_dao_url",
            "chu_ky_ben_ghi_nhan_su_kien",
            "chu_ky_ben_ghi_nhan_su_kien_url",
            "chu_ky_ben_xu_ly_su_kien_thiet_bi_url",
            "chu_ky_nguoi_xac_nhan_xu_ly_url",
            "created_at",
            "updated_at",
        ]

    remediation_fields = {
        "thoi_gian_xu_ly",
        "ket_qua_kiem_tra_nguyen_nhan",
        "noi_dung_xu_ly_khac_phuc",
        "de_xuat_lien_quan",
        "ket_qua_sau_xu_ly",
        "hinh_anh_sau_xu_ly",
        "ben_xu_ly_su_kien_thiet_bi",
        "nguoi_xac_nhan_xu_ly",
    }

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        request = self.context.get("request")
        current_user = getattr(request, "user", None)
        thiet_bi = attrs.get("thiet_bi", getattr(instance, "thiet_bi", None))
        ten_he_thong_thiet_bi = attrs.get(
            "ten_he_thong_thiet_bi",
            getattr(instance, "ten_he_thong_thiet_bi", ""),
        )

        if thiet_bi and current_user:
            allowed = filter_queryset_by_factory(
                ThietBi.objects.filter(pk=thiet_bi.pk),
                current_user,
                "nha_may",
                "string",
            ).exists()
            if not allowed:
                raise serializers.ValidationError(
                    {"thiet_bi": "Ban khong co quyen chon thiet bi cua nha may nay."}
                )

        if thiet_bi:
            attrs["ten_he_thong_thiet_bi"] = self._get_thiet_bi_snapshot(thiet_bi)
        elif not str(ten_he_thong_thiet_bi or "").strip():
            raise serializers.ValidationError(
                {"ten_he_thong_thiet_bi": "Can chon thiet bi hoac nhap ten he thong thiet bi."}
            )

        trang_thai = attrs.get("trang_thai", getattr(instance, "trang_thai", None))
        ben_ghi_nhan_su_kien = attrs.get(
            "ben_ghi_nhan_su_kien",
            getattr(instance, "ben_ghi_nhan_su_kien", None),
        )
        remediation_payload = {
            key: attrs.get(key)
            for key in self.remediation_fields
            if key in attrs
        }
        thoi_gian_xu_ly = remediation_payload.get(
            "thoi_gian_xu_ly",
            getattr(instance, "thoi_gian_xu_ly", None),
        )

        if trang_thai == SuKien.TrangThaiXuLy.XU_LY_XONG and not thoi_gian_xu_ly:
            attrs["thoi_gian_xu_ly"] = timezone.now()
        if trang_thai in [
            SuKien.TrangThaiXuLy.DANG_XU_LY,
            SuKien.TrangThaiXuLy.XU_LY_XONG,
        ] and not ben_ghi_nhan_su_kien:
            raise serializers.ValidationError(
                {"ben_ghi_nhan_su_kien": "Can ghi nhan su kien truoc khi xu ly."}
            )
        if "chi_dao" in attrs:
            request = self.context.get("request")
            current_user = getattr(request, "user", None)
            current_value = getattr(instance, "chi_dao", "") if instance else ""
            if attrs.get("chi_dao", "") != current_value and not user_can_edit_chi_dao(current_user):
                raise serializers.ValidationError(
                    {"chi_dao": "Chi lanh dao moi duoc cap nhat noi dung chi dao."}
                )
        return attrs

    def _get_thiet_bi_snapshot(self, thiet_bi):
        return f"{thiet_bi.ma_day_du} - {thiet_bi.ten}".strip()

    def create(self, validated_data):
        self._apply_chi_dao_signature(validated_data)
        remediation_data = self._pop_remediation_data(validated_data)
        su_kien = super().create(validated_data)
        self._save_remediation(su_kien, remediation_data)
        return su_kien

    def update(self, instance, validated_data):
        if "chi_dao" in validated_data and validated_data.get("chi_dao", "") != instance.chi_dao:
            self._apply_chi_dao_signature(validated_data)

        remediation_data = self._pop_remediation_data(validated_data)
        su_kien = super().update(instance, validated_data)
        self._save_remediation(su_kien, remediation_data)
        return su_kien

    def _apply_chi_dao_signature(self, validated_data):
        if "chi_dao" not in validated_data:
            return

        request = self.context.get("request")
        current_user = getattr(request, "user", None)
        if current_user and current_user.is_authenticated and validated_data.get("chi_dao", ""):
            validated_data["nguoi_chi_dao"] = current_user
            try:
                validated_data["chu_ky_nguoi_chi_dao"] = current_user.profile.chu_ky
            except Exception:
                validated_data["chu_ky_nguoi_chi_dao"] = None
        else:
            validated_data["nguoi_chi_dao"] = None
            validated_data["chu_ky_nguoi_chi_dao"] = None

    def _pop_remediation_data(self, validated_data):
        return {
          key: validated_data.pop(key)
          for key in list(validated_data.keys())
          if key in self.remediation_fields
        }

    def _save_remediation(self, su_kien, remediation_data):
        if not remediation_data:
            return None

        has_meaningful_value = any(
            value not in (None, "", [])
            for value in remediation_data.values()
        )
        if not has_meaningful_value:
            return None

        request = self.context.get("request")
        current_user = getattr(request, "user", None)
        has_user = bool(current_user and current_user.is_authenticated)

        khac_phuc = su_kien.latest_khac_phuc
        if khac_phuc is None:
            khac_phuc = KhacPhucSuKien(
                su_kien=su_kien,
                nguoi_tao=current_user if has_user else None,
            )
        else:
            if khac_phuc.nguoi_xac_nhan_xu_ly_id:
                raise serializers.ValidationError(
                    {"detail": "Ban ghi khac phuc da duoc xac nhan, khong the chinh sua."}
                )
            if khac_phuc.nguoi_tao_id and (
                not has_user or khac_phuc.nguoi_tao_id != current_user.id
            ):
                raise PermissionDenied(
                    "Chi nguoi tao noi dung khac phuc moi duoc chinh sua khi chua xac nhan."
                )
            if not khac_phuc.nguoi_tao_id and has_user:
                khac_phuc.nguoi_tao = current_user

        for key, value in remediation_data.items():
            setattr(khac_phuc, key, value)

        khac_phuc.save()
        return khac_phuc

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_can_edit_chi_dao(self, obj):
        request = self.context.get("request")
        return user_can_edit_chi_dao(getattr(request, "user", None))

    def get_chu_ky_nguoi_tao_url(self, obj):
        if not obj.nguoi_tao:
            return None
        try:
            chu_ky = obj.nguoi_tao.profile.chu_ky
        except Exception:
            return None
        return self._build_file_url(chu_ky)

    def get_nguoi_chi_dao_display(self, obj):
        return self._get_user_display(obj.nguoi_chi_dao)

    def get_chu_ky_nguoi_chi_dao_url(self, obj):
        return self._build_file_url(obj.chu_ky_nguoi_chi_dao)

    def get_ben_ghi_nhan_su_kien_display(self, obj):
        return self._get_user_display(obj.ben_ghi_nhan_su_kien)

    def get_ben_xu_ly_su_kien_thiet_bi_display(self, obj):
        return self._get_user_display(obj.ben_xu_ly_su_kien_thiet_bi)

    def get_nguoi_xac_nhan_xu_ly_display(self, obj):
        return self._get_user_display(obj.nguoi_xac_nhan_xu_ly)

    def get_hinh_anh_truoc_su_co_url(self, obj):
        return self._build_file_url(obj.hinh_anh_truoc_su_co)

    def get_hinh_anh_sau_xu_ly_url(self, obj):
        return self._build_file_url(obj.hinh_anh_sau_xu_ly)

    def get_chu_ky_ben_ghi_nhan_su_kien_url(self, obj):
        return self._build_file_url(obj.chu_ky_ben_ghi_nhan_su_kien)

    def get_chu_ky_ben_xu_ly_su_kien_thiet_bi_url(self, obj):
        return self._build_file_url(obj.chu_ky_ben_xu_ly_su_kien_thiet_bi)

    def get_chu_ky_nguoi_xac_nhan_xu_ly_url(self, obj):
        return self._build_file_url(obj.chu_ky_nguoi_xac_nhan_xu_ly)
