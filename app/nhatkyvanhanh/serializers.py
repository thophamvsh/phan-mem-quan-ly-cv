from django.utils import timezone
import unicodedata
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from core.factory_scope import filter_queryset_by_factory
from quanlyvanhanh.models import ThietBi
from .models import (
    ChiTietSoGiaoNhanCaHC,
    ChiTietSoGiaoNhanCaVH,
    DienBienSuKien,
    KhacPhucSuKien,
    ChiTietChuyenDoiThietBi,
    LanChuyenDoiThietBi,
    MauChuyenDoiThietBi,
    NguoiTrucSoGiaoNhanCaHC,
    SoBCHCSongHinh,
    SoChuyenDoiThietBiTuan,
    Sonhatkyvanhanh,
    SonhatkyvanhanhDiesel,
    SuKien,
    SogiaonhancaHC,
    SogiaonhancaVH,
    SoAnToanDauGio
)

LEADERSHIP_TITLES = {
    "giam doc",
    "pho tong giam doc",
    "tong giam doc",
    "tgd",
}


def _normalize_title(value):
    normalized = unicodedata.normalize("NFD", str(value or "").replace("đ", "d").replace("Đ", "D"))
    without_marks = "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    )
    return " ".join(without_marks.casefold().split())


def user_can_edit_chi_dao(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return _normalize_title(getattr(profile, "chuc_danh", "")) in LEADERSHIP_TITLES


class UserSummaryMixin:
    def _build_file_url(self, file_field):
        if not file_field:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(file_field.url)
        return file_field.url

    def _get_user_display(self, user):
        if not user:
            return None
        full_name = f"{user.first_name} {user.last_name}".strip()
        return full_name or user.username or user.email


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
        profile = getattr(obj.nguoi_tao, "profile", None)
        return self._build_file_url(getattr(profile, "chu_ky", None))

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


class ChiTietSoGiaoNhanCaVHSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()

    class Meta:
        model = ChiTietSoGiaoNhanCaVH
        fields = [
            "id",
            "so_giao_nhan_ca",
            "thoi_gian",
            "tieu_de",
            "noi_dung",
            "thu_tu",
            "nguoi_tao",
            "nguoi_tao_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "so_giao_nhan_ca",
            "nguoi_tao",
            "nguoi_tao_display",
            "created_at",
            "updated_at",
        ]

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)


class SogiaonhancaVHSerializer(serializers.ModelSerializer, UserSummaryMixin):
    user_giao_ca_display = serializers.SerializerMethodField()
    user_nhan_ca_display = serializers.SerializerMethodField()
    nguoi_tao_display = serializers.SerializerMethodField()
    hinh_anh_url = serializers.SerializerMethodField()
    chu_ky_user_giao_ca_url = serializers.SerializerMethodField()
    chu_ky_user_nhan_ca_url = serializers.SerializerMethodField()
    da_hoan_thanh = serializers.BooleanField(read_only=True)
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    noi_dung_chi_tiets = ChiTietSoGiaoNhanCaVHSerializer(many=True, read_only=True)

    class Meta:
        model = SogiaonhancaVH
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "ngay_truc",
            "ca_truc",
            "dia_diem",
            "truc_chinh",
            "truc_phu",
            "truc_ktvh",
            "dieu_do_a0",
            "dieu_do_a3",
            "dieu_do_b3",
            "thoi_gian_bat_dau_ca",
            "thoi_gian_giao_ca",
            "noi_dung_chi_tiets",
            "tinh_trang_van_hanh_trong_ca",
            "cac_phuong_tien_trang_bi_ca",
            "luu_y",
            "tong_muc_luc",
            "hinh_anh",
            "hinh_anh_url",
            "chu_ky_user_giao_ca",
            "chu_ky_user_giao_ca_url",
            "chu_ky_user_nhan_ca",
            "chu_ky_user_nhan_ca_url",
            "user_giao_ca",
            "user_giao_ca_display",
            "user_nhan_ca",
            "user_nhan_ca_display",
            "nguoi_tao",
            "nguoi_tao_display",
            "giao_ca_ky_at",
            "nhan_ca_ky_at",
            "trang_thai",
            "da_hoan_thanh",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may_code",
            "nha_may_name",
            "noi_dung_chi_tiets",
            "chu_ky_user_giao_ca",
            "chu_ky_user_giao_ca_url",
            "chu_ky_user_nhan_ca",
            "chu_ky_user_nhan_ca_url",
            "user_giao_ca",
            "user_giao_ca_display",
            "user_nhan_ca",
            "user_nhan_ca_display",
            "nguoi_tao",
            "nguoi_tao_display",
            "trang_thai",
            "da_hoan_thanh",
            "created_at",
            "updated_at",
        ]

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_user_giao_ca_display(self, obj):
        return self._get_user_display(obj.user_giao_ca)

    def get_user_nhan_ca_display(self, obj):
        return self._get_user_display(obj.user_nhan_ca)

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)

    def get_hinh_anh_url(self, obj):
        return self._build_file_url(obj.hinh_anh)

    def get_chu_ky_user_giao_ca_url(self, obj):
        return self._build_file_url(obj.chu_ky_user_giao_ca)

    def get_chu_ky_user_nhan_ca_url(self, obj):
        return self._build_file_url(obj.chu_ky_user_nhan_ca)


class ChiTietSoGiaoNhanCaHCSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()

    class Meta:
        model = ChiTietSoGiaoNhanCaHC
        fields = [
            "id",
            "so_giao_nhan_ca",
            "thoi_gian",
            "tieu_de",
            "noi_dung",
            "thu_tu",
            "nguoi_tao",
            "nguoi_tao_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "so_giao_nhan_ca",
            "nguoi_tao",
            "nguoi_tao_display",
            "created_at",
            "updated_at",
        ]

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)


class NguoiTrucSoGiaoNhanCaHCSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()

    class Meta:
        model = NguoiTrucSoGiaoNhanCaHC
        fields = [
            "id",
            "so_giao_nhan_ca",
            "thoi_gian",
            "ten_nguoi_truc",
            "thu_tu",
            "nguoi_tao",
            "nguoi_tao_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "so_giao_nhan_ca",
            "nguoi_tao",
            "nguoi_tao_display",
            "created_at",
            "updated_at",
        ]

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)


class SogiaonhancaHCSerializer(serializers.ModelSerializer, UserSummaryMixin):
    user_giao_ca_display = serializers.SerializerMethodField()
    user_nhan_ca_display = serializers.SerializerMethodField()
    nguoi_tao_display = serializers.SerializerMethodField()
    chu_ky_user_giao_ca_url = serializers.SerializerMethodField()
    chu_ky_user_nhan_ca_url = serializers.SerializerMethodField()
    da_hoan_thanh = serializers.BooleanField(read_only=True)
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    nguoi_truc_chi_tiets = NguoiTrucSoGiaoNhanCaHCSerializer(many=True, read_only=True)
    noi_dung_chi_tiets = ChiTietSoGiaoNhanCaHCSerializer(many=True, read_only=True)

    class Meta:
        model = SogiaonhancaHC
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "ngay_truc",
            "dia_diem",
            "nguoi_truc",
            "nguoi_truc_2",
            "nguoi_truc_3",
            "nguoi_truc_chi_tiets",
            "thoi_gian_bat_dau_ca",
            "thoi_gian_giao_ca",
            "noi_dung_chi_tiets",
            "luu_y",
            "chu_ky_user_giao_ca",
            "chu_ky_user_giao_ca_url",
            "chu_ky_user_nhan_ca",
            "chu_ky_user_nhan_ca_url",
            "user_giao_ca",
            "user_giao_ca_display",
            "user_nhan_ca",
            "user_nhan_ca_display",
            "nguoi_tao",
            "nguoi_tao_display",
            "giao_ca_ky_at",
            "nhan_ca_ky_at",
            "trang_thai",
            "da_hoan_thanh",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may_code",
            "nha_may_name",
            "nguoi_truc_chi_tiets",
            "noi_dung_chi_tiets",
            "chu_ky_user_giao_ca",
            "chu_ky_user_giao_ca_url",
            "chu_ky_user_nhan_ca",
            "chu_ky_user_nhan_ca_url",
            "user_giao_ca",
            "user_giao_ca_display",
            "user_nhan_ca",
            "user_nhan_ca_display",
            "nguoi_tao",
            "nguoi_tao_display",
            "trang_thai",
            "da_hoan_thanh",
            "created_at",
            "updated_at",
        ]

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_user_giao_ca_display(self, obj):
        return self._get_user_display(obj.user_giao_ca)

    def get_user_nhan_ca_display(self, obj):
        return self._get_user_display(obj.user_nhan_ca)

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)

    def get_chu_ky_user_giao_ca_url(self, obj):
        return self._build_file_url(obj.chu_ky_user_giao_ca)

    def get_chu_ky_user_nhan_ca_url(self, obj):
        return self._build_file_url(obj.chu_ky_user_nhan_ca)


class SonhatkyvanhanhSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()
    nguoi_xac_nhan_display = serializers.SerializerMethodField()
    chu_ky_nguoi_tao_url = serializers.SerializerMethodField()
    chu_ky_nguoi_xac_nhan_url = serializers.SerializerMethodField()
    da_hoan_thanh = serializers.BooleanField(read_only=True)
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()

    class Meta:
        model = Sonhatkyvanhanh
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "thoi_gian_tao",
            "noi_dung_tao",
            "nguoi_tao",
            "nguoi_tao_display",
            "nguoi_xac_nhan",
            "nguoi_xac_nhan_display",
            "chu_ky_nguoi_tao",
            "chu_ky_nguoi_tao_url",
            "chu_ky_nguoi_xac_nhan",
            "chu_ky_nguoi_xac_nhan_url",
            "xac_nhan_at",
            "trang_thai",
            "da_hoan_thanh",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may_code",
            "nha_may_name",
            "nguoi_tao",
            "nguoi_tao_display",
            "nguoi_xac_nhan",
            "nguoi_xac_nhan_display",
            "chu_ky_nguoi_tao",
            "chu_ky_nguoi_tao_url",
            "chu_ky_nguoi_xac_nhan",
            "chu_ky_nguoi_xac_nhan_url",
            "xac_nhan_at",
            "trang_thai",
            "da_hoan_thanh",
            "created_at",
            "updated_at",
        ]

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)

    def get_nguoi_xac_nhan_display(self, obj):
        return self._get_user_display(obj.nguoi_xac_nhan)

    def get_chu_ky_nguoi_tao_url(self, obj):
        return self._build_file_url(obj.chu_ky_nguoi_tao)

    def get_chu_ky_nguoi_xac_nhan_url(self, obj):
        return self._build_file_url(obj.chu_ky_nguoi_xac_nhan)


class SonhatkyvanhanhDieselSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()
    chu_ky_nguoi_tao_url = serializers.SerializerMethodField()
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()

    class Meta:
        model = SonhatkyvanhanhDiesel
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "thoi_gian",
            "noi_dung",
            "i",
            "u",
            "f",
            "i_sac",
            "u_sac",
            "p",
            "q",
            "chi_so_gio_vh",
            "t_may",
            "muc_dau",
            "ap_luc_dau",
            "ca_truc",
            "nguoi_tao",
            "nguoi_tao_display",
            "chu_ky_nguoi_tao",
            "chu_ky_nguoi_tao_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may_code",
            "nha_may_name",
            "nguoi_tao",
            "nguoi_tao_display",
            "chu_ky_nguoi_tao",
            "chu_ky_nguoi_tao_url",
            "created_at",
            "updated_at",
        ]

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)

    def get_chu_ky_nguoi_tao_url(self, obj):
        return self._build_file_url(obj.chu_ky_nguoi_tao)


class SoBCHCSongHinhSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_dong_bo_display = serializers.SerializerMethodField()
    chu_ky_nguoi_dong_bo_url = serializers.SerializerMethodField()
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()

    class Meta:
        model = SoBCHCSongHinh
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "ngay_dong_bo",
            "muc_nuoc_quy_trinh",
            "muc_nuoc_quy_trinh_tu",
            "muc_nuoc_quy_trinh_den",
            "muc_nuoc_ho",
            "luu_luong_ve_ho",
            "luu_luong_xa_tran",
            "luu_luong_chay_may",
            "luu_luong_chay_may_qt",
            "nguyen_nhan_khong_dap_ung",
            "nguoi_dong_bo",
            "nguoi_dong_bo_display",
            "chu_ky_nguoi_dong_bo",
            "chu_ky_nguoi_dong_bo_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "nguoi_dong_bo",
            "nguoi_dong_bo_display",
            "chu_ky_nguoi_dong_bo",
            "chu_ky_nguoi_dong_bo_url",
            "created_at",
            "updated_at",
        ]

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_nguoi_dong_bo_display(self, obj):
        return self._get_user_display(obj.nguoi_dong_bo)

    def get_chu_ky_nguoi_dong_bo_url(self, obj):
        return self._build_file_url(obj.chu_ky_nguoi_dong_bo)

class SoAnToanSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_dong_bo_display = serializers.SerializerMethodField()
    chu_ky_nguoi_dong_bo_url = serializers.SerializerMethodField()
    ca_truc_display = serializers.SerializerMethodField()
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()

    class Meta:
        model = SoAnToanDauGio
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "ngay_dong_bo",
            "ca_truc",
            "ca_truc_display",
            "tinh_trang_an_toan",
            "nguoi_dong_bo",
            "nguoi_dong_bo_display",
            "chu_ky_nguoi_dong_bo",
            "chu_ky_nguoi_dong_bo_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "nguoi_dong_bo",
            "nguoi_dong_bo_display",
            "chu_ky_nguoi_dong_bo",
            "chu_ky_nguoi_dong_bo_url",
            "created_at",
            "updated_at",
        ]

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_ca_truc_display(self, obj):
        return obj.get_ca_truc_display()

    def get_nguoi_dong_bo_display(self, obj):
        return self._get_user_display(obj.nguoi_dong_bo)

    def get_chu_ky_nguoi_dong_bo_url(self, obj):
        return self._build_file_url(obj.chu_ky_nguoi_dong_bo)


class MauChuyenDoiThietBiSerializer(serializers.ModelSerializer):
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    thiet_bi_ten = serializers.CharField(source="thiet_bi.ten", read_only=True)
    thiet_bi_ma_day_du = serializers.CharField(source="thiet_bi.ma_day_du", read_only=True)
    to_may_display = serializers.SerializerMethodField()

    class Meta:
        model = MauChuyenDoiThietBi
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "to_may",
            "to_may_display",
            "nhom_thiet_bi",
            "thiet_bi",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "thu_tu",
            "dang_su_dung",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["nha_may_code", "nha_may_name", "thiet_bi_ten", "thiet_bi_ma_day_du", "to_may_display", "created_at", "updated_at"]

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_to_may_display(self, obj):
        return obj.get_to_may_display()


class ChiTietChuyenDoiThietBiSerializer(serializers.ModelSerializer):
    thiet_bi_ten = serializers.CharField(source="thiet_bi.ten", read_only=True)
    thiet_bi_ma_day_du = serializers.CharField(source="thiet_bi.ma_day_du", read_only=True)
    to_may_display = serializers.SerializerMethodField()
    trang_thai_display = serializers.SerializerMethodField()

    class Meta:
        model = ChiTietChuyenDoiThietBi
        fields = [
            "id",
            "lan_chuyen_doi",
            "thiet_bi",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "to_may",
            "to_may_display",
            "nhom_thiet_bi",
            "trang_thai",
            "trang_thai_display",
            "ghi_chu",
            "thu_tu",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "lan_chuyen_doi",
            "thiet_bi",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "to_may",
            "to_may_display",
            "nhom_thiet_bi",
            "thu_tu",
            "trang_thai_display",
            "created_at",
            "updated_at",
        ]

    def get_to_may_display(self, obj):
        return obj.get_to_may_display()

    def get_trang_thai_display(self, obj):
        return obj.get_trang_thai_display() if obj.trang_thai else ""


class LanChuyenDoiThietBiSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_thuc_hien_display = serializers.SerializerMethodField()
    chi_tiets = ChiTietChuyenDoiThietBiSerializer(many=True, read_only=True)

    class Meta:
        model = LanChuyenDoiThietBi
        fields = [
            "id",
            "so",
            "thoi_gian",
            "nguoi_thuc_hien",
            "nguoi_thuc_hien_display",
            "ghi_chu_chung",
            "chi_tiets",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["so", "nguoi_thuc_hien", "nguoi_thuc_hien_display", "chi_tiets", "created_at", "updated_at"]

    def get_nguoi_thuc_hien_display(self, obj):
        return self._get_user_display(obj.nguoi_thuc_hien)


class SoChuyenDoiThietBiTuanSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    ca_truc_display = serializers.SerializerMethodField()
    lan_chuyen_dois = LanChuyenDoiThietBiSerializer(many=True, read_only=True)

    class Meta:
        model = SoChuyenDoiThietBiTuan
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "nam",
            "tuan",
            "ca_truc",
            "ca_truc_display",
            "tuan_bat_dau",
            "tuan_ket_thuc",
            "nguoi_tao",
            "nguoi_tao_display",
            "lan_chuyen_dois",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may_code",
            "nha_may_name",
            "ca_truc_display",
            "tuan_bat_dau",
            "tuan_ket_thuc",
            "nguoi_tao",
            "nguoi_tao_display",
            "lan_chuyen_dois",
            "created_at",
            "updated_at",
        ]

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_ca_truc_display(self, obj):
        return obj.get_ca_truc_display()

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)
