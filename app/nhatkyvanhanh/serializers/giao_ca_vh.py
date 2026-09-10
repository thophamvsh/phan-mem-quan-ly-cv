from rest_framework import serializers
from nhatkyvanhanh.models import (
    SogiaonhancaVH,
    ChiTietSoGiaoNhanCaVH,
    NhanSuSoGiaoNhanCaVH,
    LuuYChiDaoSoGiaoNhanCaVH,
    AnhSoGiaoNhanCaVH,
)
from .mixins import UserSummaryMixin
from nhatkyvanhanh.device_status import summarize_device_status, validate_device_status_snapshot
from nhatkyvanhanh.models import MauTomLuocGiaoCaVH, MauTrangThaiThietBiCa
from quanlyvanhanh.models import ThietBi

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


class AnhSoGiaoNhanCaVHSerializer(serializers.ModelSerializer):
    hinh_anh_url = serializers.SerializerMethodField()

    class Meta:
        model = AnhSoGiaoNhanCaVH
        fields = ["id", "hinh_anh", "hinh_anh_url", "chu_thich", "thu_tu", "created_at"]
        read_only_fields = ["id", "hinh_anh_url", "created_at"]

    def get_hinh_anh_url(self, obj):
        request = self.context.get("request")
        if not obj.hinh_anh:
            return None
        return request.build_absolute_uri(obj.hinh_anh.url) if request else obj.hinh_anh.url


class LuuYChiDaoSoGiaoNhanCaVHSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()

    class Meta:
        model = LuuYChiDaoSoGiaoNhanCaVH
        fields = [
            "id",
            "so_giao_nhan_ca",
            "thoi_gian",
            "noi_dung",
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


class NhanSuSoGiaoNhanCaVHSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()
    vai_tro_display = serializers.CharField(source="get_vai_tro_display", read_only=True)
    nhan_su_detail = serializers.SerializerMethodField()

    class Meta:
        model = NhanSuSoGiaoNhanCaVH
        fields = [
            "id",
            "so_giao_nhan_ca",
            "nhan_su",
            "ma_nhan_vien",
            "nhan_su_detail",
            "vai_tro",
            "vai_tro_display",
            "ten_nhan_su",
            "thu_tu",
            "nguoi_tao",
            "nguoi_tao_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "so_giao_nhan_ca",
            "vai_tro_display",
            "nhan_su_detail",
            "nguoi_tao",
            "nguoi_tao_display",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "ten_nhan_su": {"required": False, "allow_blank": True},
            "ma_nhan_vien": {"required": False, "allow_blank": True},
            "nhan_su": {"required": False, "allow_null": True},
        }

    def get_nhan_su_detail(self, obj):
        if not obj.nhan_su_id or not obj.nhan_su:
            return None
        return {
            "id": obj.nhan_su_id,
            "ho_ten": obj.nhan_su.ho_ten,
            "ma_nhan_vien": obj.nhan_su.ma_nhan_vien or "",
            "chuc_danh": obj.nhan_su.chuc_danh or "",
        }

    def validate(self, attrs):
        shift_log = self.context.get("shift_log")
        nhan_su = attrs.get("nhan_su", getattr(self.instance, "nhan_su", None))

        # 1. Kiểm tra nhà máy: nhân sự phải thuộc nhà máy của sổ trực ca
        if nhan_su and shift_log:
            if nhan_su.nha_may_id != shift_log.nha_may_id:
                raise serializers.ValidationError(
                    {"nhan_su": f"Nhân sự '{nhan_su.ho_ten}' không thuộc nhà máy của sổ trực ca."}
                )

        # 2. Xử lý đổi liên kết nhân sự từ A sang B
        is_changing_nhan_su = (
            self.instance
            and "nhan_su" in attrs
            and attrs["nhan_su"] != self.instance.nhan_su
        )

        # Có liên kết danh mục thì snapshot chỉ được lấy từ bản ghi NhanSu.
        # Client không được gửi tên/mã khác với khóa ngoại đã chọn.
        if nhan_su and (self.instance is None or is_changing_nhan_su):
            name = nhan_su.ho_ten
            attrs["ma_nhan_vien"] = nhan_su.ma_nhan_vien or ""
        elif nhan_su and self.instance:
            name = self.instance.ten_nhan_su
            attrs["ma_nhan_vien"] = self.instance.ma_nhan_vien
        else:
            name = attrs.get(
                "ten_nhan_su",
                getattr(self.instance, "ten_nhan_su", ""),
            )

        name = " ".join((name or "").split())
        if not name and nhan_su:
            name = nhan_su.ho_ten
        if not name:
            raise serializers.ValidationError({"ten_nhan_su": "Yêu cầu nhập tên nhân sự."})
        attrs["ten_nhan_su"] = name

        if is_changing_nhan_su and nhan_su is None:
            attrs["ma_nhan_vien"] = getattr(
                self.instance,
                "ma_nhan_vien",
                "",
            )

        if not shift_log:
            return attrs

        role = attrs.get("vai_tro", getattr(self.instance, "vai_tro", None))
        queryset = shift_log.nhan_su_ca.all()
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if role == NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_CHINH and queryset.filter(
            vai_tro=NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_CHINH
        ).exists():
            raise serializers.ValidationError(
                {"vai_tro": "Mỗi ca chỉ được có tối đa một trực chính."}
            )

        # 3. Kiểm tra trùng lặp:
        # - Có nhan_su: kiểm tra trùng theo nhan_su_id
        # - Không có nhan_su (nhập tay/legacy): fallback kiểm tra trùng theo tên chuẩn hóa
        if nhan_su:
            if any(person.nhan_su_id == nhan_su.pk for person in queryset):
                raise serializers.ValidationError(
                    {"nhan_su": "Nhân sự đã được phân công trong ca trực này."}
                )
        else:
            if any(person.ten_nhan_su.casefold() == name.casefold() for person in queryset):
                raise serializers.ValidationError(
                    {"ten_nhan_su": "Nhân sự không được trùng tên trong cùng một ca."}
                )

        # 4. Kiểm tra trùng Trưởng ca (user_giao_ca):
        # Người tạo sổ (Trưởng ca) không được trùng với nhân sự Trực chính hoặc Trực phụ.
        if shift_log.user_giao_ca_id and role in (
            NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_CHINH,
            NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_PHU,
        ):
            leader = shift_log.user_giao_ca
            leader_nhansu = getattr(leader, "nhan_su_ca_truc", None)
            leader_id = leader_nhansu.id if leader_nhansu else None
            leader_code = (leader_nhansu.ma_nhan_vien or "").strip() if leader_nhansu else ""
            leader_name = (
                ((leader_nhansu.ho_ten or "").strip() if leader_nhansu else "")
                or f"{leader.first_name} {leader.last_name}".strip()
                or leader.username
            ).strip()

            code = (attrs.get("ma_nhan_vien") or getattr(self.instance, "ma_nhan_vien", "") or "").strip()
            is_overlap = False
            if nhan_su and leader_id and nhan_su.pk == leader_id:
                is_overlap = True
            elif code and leader_code and code.casefold() == leader_code.casefold():
                is_overlap = True
            elif name and leader_name and " ".join(name.split()).casefold() == " ".join(leader_name.split()).casefold():
                is_overlap = True

            if is_overlap:
                raise serializers.ValidationError(
                    {"nhan_su": "Người tạo sổ (Trưởng ca) không được trùng với nhân sự Trực chính hoặc Trực phụ trong cùng một ca trực."}
                )

        return attrs

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)


class SogiaonhancaVHSerializer(serializers.ModelSerializer, UserSummaryMixin):
    user_giao_ca_display = serializers.SerializerMethodField()
    user_giao_ca_nhan_su_id = serializers.SerializerMethodField()
    user_giao_ca_ma_nhan_vien = serializers.SerializerMethodField()
    user_nhan_ca_display = serializers.SerializerMethodField()
    nguoi_tao_display = serializers.SerializerMethodField()
    hinh_anh_url = serializers.SerializerMethodField()
    chu_ky_user_giao_ca_url = serializers.SerializerMethodField()
    chu_ky_user_nhan_ca_url = serializers.SerializerMethodField()
    da_hoan_thanh = serializers.BooleanField(read_only=True)
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    noi_dung_chi_tiets = ChiTietSoGiaoNhanCaVHSerializer(many=True, read_only=True)
    nhan_su_ca = NhanSuSoGiaoNhanCaVHSerializer(many=True, read_only=True)
    luu_y_chi_daos = serializers.SerializerMethodField()
    hinh_anh_bo_sung = AnhSoGiaoNhanCaVHSerializer(many=True, read_only=True)
    trang_thai_quy_trinh = serializers.CharField(read_only=True)

    class Meta:
        model = SogiaonhancaVH
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "lich_truc_nguon",
            "ngay_truc_ca_nguon",
            "phien_ban_lich_nguon",
            "dong_bo_bien_che_at",
            "so_giao_nhan_ca_hc_nguon",
            "dong_bo_truc_ktvh_at",
            "ngay_truc",
            "ca_truc",
            "loai_thoi_gian_truc",
            "dia_diem",
            "truc_chinh",
            "truc_phu",
            "truc_ktvh",
            "nhan_su_ca",
            "dieu_do_a0",
            "dieu_do_a3",
            "dieu_do_b3",
            "thoi_gian_bat_dau_ca",
            "thoi_gian_giao_ca",
            "noi_dung_chi_tiets",
            "luu_y_chi_daos",
            "tinh_trang_van_hanh_trong_ca",
            "ghi_chu_van_hanh_bo_sung",
            "trang_thai_thiet_bi",
            "cac_phuong_tien_trang_bi_ca",
            "luu_y",
            "tong_muc_luc",
            "mau_tom_luoc_nguon",
            "hinh_anh",
            "hinh_anh_url",
            "hinh_anh_bo_sung",
            "chu_ky_user_giao_ca",
            "chu_ky_user_giao_ca_url",
            "chu_ky_user_nhan_ca",
            "chu_ky_user_nhan_ca_url",
            "user_giao_ca",
            "user_giao_ca_display",
            "user_giao_ca_nhan_su_id",
            "user_giao_ca_ma_nhan_vien",
            "user_nhan_ca",
            "user_nhan_ca_display",
            "nguoi_tao",
            "nguoi_tao_display",
            "giao_ca_ky_at",
            "nhan_ca_ky_at",
            "trang_thai",
            "da_hoan_thanh",
            "trang_thai_quy_trinh",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may_code",
            "nha_may_name",
            "dong_bo_bien_che_at",
            "dong_bo_truc_ktvh_at",
            "noi_dung_chi_tiets",
            "nhan_su_ca",
            "luu_y_chi_daos",
            "chu_ky_user_giao_ca",
            "chu_ky_user_giao_ca_url",
            "chu_ky_user_nhan_ca",
            "chu_ky_user_nhan_ca_url",
            "user_giao_ca",
            "user_giao_ca_display",
            "user_giao_ca_nhan_su_id",
            "user_giao_ca_ma_nhan_vien",
            "user_nhan_ca",
            "user_nhan_ca_display",
            "nguoi_tao",
            "nguoi_tao_display",
            "trang_thai",
            "da_hoan_thanh",
            "trang_thai_quy_trinh",
            "created_at",
            "updated_at",
        ]
        validators = []

    def validate(self, attrs):
        shift_period = attrs.get(
            "loai_thoi_gian_truc",
            getattr(self.instance, "loai_thoi_gian_truc", "ngay"),
        )
        if shift_period == SogiaonhancaVH.LoaiThoiGianTruc.DEM:
            attrs["truc_ktvh"] = ""
            attrs["so_giao_nhan_ca_hc_nguon"] = None

        start = attrs.get(
            "thoi_gian_bat_dau_ca",
            getattr(self.instance, "thoi_gian_bat_dau_ca", None),
        )
        end = attrs.get(
            "thoi_gian_giao_ca",
            getattr(self.instance, "thoi_gian_giao_ca", None),
        )
        if start and end and end <= start:
            raise serializers.ValidationError(
                {
                    "thoi_gian_giao_ca": (
                        "Thời gian giao ca phải sau thời gian bắt đầu ca."
                    )
                }
            )
        source_schedule = attrs.get(
            "lich_truc_nguon", getattr(self.instance, "lich_truc_nguon", None)
        )
        source_day = attrs.get(
            "ngay_truc_ca_nguon", getattr(self.instance, "ngay_truc_ca_nguon", None)
        )
        plant = attrs.get("nha_may", getattr(self.instance, "nha_may", None))
        shift_date = attrs.get("ngay_truc", getattr(self.instance, "ngay_truc", None))
        if bool(source_schedule) != bool(source_day):
            raise serializers.ValidationError(
                {"lich_truc_nguon": "Lịch trực nguồn và ngày trực nguồn phải được chọn cùng nhau."}
            )
        if source_schedule and source_day:
            if source_day.lich_truc_id != source_schedule.id:
                raise serializers.ValidationError(
                    {"ngay_truc_ca_nguon": "Ngày trực nguồn không thuộc lịch trực đã chọn."}
                )
            if plant and source_schedule.nha_may_id != plant.id:
                raise serializers.ValidationError(
                    {"lich_truc_nguon": "Lịch trực nguồn không thuộc nhà máy của sổ."}
                )
            if shift_date and source_day.ngay != shift_date:
                raise serializers.ValidationError(
                    {"ngay_truc_ca_nguon": "Ngày trực nguồn không trùng ngày trực của sổ."}
                )
        admin_source = attrs.get(
            "so_giao_nhan_ca_hc_nguon",
            getattr(self.instance, "so_giao_nhan_ca_hc_nguon", None),
        )
        if admin_source:
            if plant and admin_source.nha_may_id != plant.id:
                raise serializers.ValidationError(
                    {"so_giao_nhan_ca_hc_nguon": "Sổ hành chính nguồn không thuộc nhà máy của sổ vận hành."}
                )
            if start and end and not (
                admin_source.thoi_gian_bat_dau_ca
                and admin_source.thoi_gian_bat_dau_ca <= end
                and admin_source.thoi_gian_giao_ca >= start
            ):
                raise serializers.ValidationError(
                    {"so_giao_nhan_ca_hc_nguon": "Thời gian sổ hành chính nguồn không giao với ca vận hành."}
                )
        device_states = attrs.get(
            "trang_thai_thiet_bi",
            getattr(self.instance, "trang_thai_thiet_bi", []),
        )
        try:
            validate_device_status_snapshot(device_states, plant=plant)
        except ValueError as exc:
            raise serializers.ValidationError({"trang_thai_thiet_bi": str(exc)})
        if isinstance(device_states, dict):
            try:
                template = MauTrangThaiThietBiCa.objects.get(pk=device_states["template_id"])
            except (MauTrangThaiThietBiCa.DoesNotExist, ValueError, TypeError, KeyError):
                raise serializers.ValidationError({"trang_thai_thiet_bi": "Mẫu thiết bị không tồn tại."})
            if plant and template.nha_may_id != plant.id:
                raise serializers.ValidationError({"trang_thai_thiet_bi": "Mẫu thiết bị không thuộc nhà máy của sổ."})
            if template.phien_ban != device_states.get("template_version"):
                raise serializers.ValidationError({"trang_thai_thiet_bi": "Phiên bản mẫu thiết bị không hợp lệ."})
            linked_ids = {
                str(row.get("thiet_bi_id"))
                for group in device_states.get("groups", [])
                for row in group.get("thiet_bi", [])
                if row.get("thiet_bi_id")
            }
            linked_devices = {str(device.pk): device for device in ThietBi.objects.filter(pk__in=linked_ids)}
            if set(linked_devices) != linked_ids:
                raise serializers.ValidationError({"trang_thai_thiet_bi": "Có thiết bị liên kết không tồn tại."})
            plant_code = (plant.ma_nha_may or "").casefold() if plant else ""
            plant_name = (plant.ten_nha_may or "").casefold() if plant else ""
            for device in linked_devices.values():
                if (device.nha_may or "").casefold() not in {plant_code, plant_name} and not (device.ma_day_du or "").casefold().startswith(f"{plant_code}."):
                    raise serializers.ValidationError({"trang_thai_thiet_bi": f"Thiết bị {device.ma_day_du} không thuộc nhà máy của sổ."})
            summary = summarize_device_status(device_states)
            extra = attrs.get(
                "ghi_chu_van_hanh_bo_sung",
                getattr(self.instance, "ghi_chu_van_hanh_bo_sung", ""),
            )
            attrs["tinh_trang_van_hanh_trong_ca"] = "\n\n".join(
                part for part in (summary, extra.strip()) if part
            )
        summary_template = attrs.get(
            "mau_tom_luoc_nguon",
            getattr(self.instance, "mau_tom_luoc_nguon", None),
        )
        if summary_template and plant and summary_template.nha_may_id != plant.id:
            raise serializers.ValidationError(
                {"mau_tom_luoc_nguon": "Mẫu tóm lược không thuộc nhà máy của sổ."}
            )
        return attrs

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_luu_y_chi_daos(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return []
        if not user.is_superuser:
            try:
                profile = user.profile
                if not (profile.can_view_shift_handover_directives or profile.can_view_shift_handover_logs):
                    return []
            except Exception:
                return []
        return LuuYChiDaoSoGiaoNhanCaVHSerializer(
            obj.luu_y_chi_daos.all(),
            many=True,
            context=self.context,
        ).data

    def get_user_giao_ca_display(self, obj):
        if obj.user_giao_ca_id:
            nhan_su = getattr(obj.user_giao_ca, "nhan_su_ca_truc", None)
            if nhan_su and nhan_su.ho_ten:
                return nhan_su.ho_ten.strip()
        return self._get_user_display(obj.user_giao_ca)

    def get_user_giao_ca_nhan_su_id(self, obj):
        if not obj.user_giao_ca_id:
            return None
        nhan_su = getattr(obj.user_giao_ca, "nhan_su_ca_truc", None)
        return nhan_su.id if nhan_su else None

    def get_user_giao_ca_ma_nhan_vien(self, obj):
        if not obj.user_giao_ca_id:
            return ""
        nhan_su = getattr(obj.user_giao_ca, "nhan_su_ca_truc", None)
        return nhan_su.ma_nhan_vien if nhan_su and nhan_su.ma_nhan_vien else ""

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
