from rest_framework import serializers
from datetime import time, datetime
from .models import ThietBi, VatTu, ThietBiVatTu, ThongSoVanHanh, AnToanThietBi, DinhKem, ThongSoToMay, ThongSoTram110KV, NguongThongSo


def get_thiet_bi_qr_payload(obj):
    return obj.ma_day_du or str(obj.pk)


def get_thiet_bi_qr_url(obj, request=None):
    path = f"/api/quanlyvanhanh/thiet-bi/{obj.pk}/qr/"
    if request:
        return request.build_absolute_uri(path)
    return path


class ThietBiSerializer(serializers.ModelSerializer):
    """Serializer cho model ThietBi"""
    cha_ten = serializers.CharField(source='cha.ten', read_only=True)
    con_count = serializers.SerializerMethodField()
    hinh_anh_url = serializers.SerializerMethodField()
    ma_qr = serializers.SerializerMethodField()
    qr_url = serializers.SerializerMethodField()

    class Meta:
        model = ThietBi
        fields = [
            'id', 'ten', 'ma', 'ma_day_du', 'cha', 'cha_ten',
            'loai', 'trang_thai', 'nha_che_tao', 'nha_cung_cap',
            'nuoc_san_xuat', 'nha_may', 'do_uu_tien', 'so_serial',
            'ma_van_hanh', 'bo_phan_quan_ly', 'bang_ve',
            'mo_ta_ky_thuat', 'cap', 'thu_tu', 'slug', 'con_count',
            'ngay_lap_dat', 'ngay_dua_vao_van_hanh', 'hinh_anh', 'hinh_anh_url',
            'ma_qr', 'qr_url'
        ]
        read_only_fields = ['ma_day_du', 'cap', 'slug']

    def get_con_count(self, obj):
        return obj.con.count()

    def get_hinh_anh_url(self, obj):
        if obj.hinh_anh:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.hinh_anh.url)
            return obj.hinh_anh.url
        return None

    def get_ma_qr(self, obj):
        return get_thiet_bi_qr_payload(obj)

    def get_qr_url(self, obj):
        return get_thiet_bi_qr_url(obj, self.context.get('request'))


class ThietBiListSerializer(serializers.ModelSerializer):
    """Serializer đơn giản cho danh sách thiết bị"""
    cha_ten = serializers.CharField(source='cha.ten', read_only=True)
    hinh_anh_url = serializers.SerializerMethodField()
    ma_qr = serializers.SerializerMethodField()
    qr_url = serializers.SerializerMethodField()

    class Meta:
        model = ThietBi
        fields = ['id', 'ten', 'ma', 'ma_day_du', 'cha_ten', 'loai', 'trang_thai', 'cap', 'hinh_anh_url', 'nha_may', 'ma_qr', 'qr_url']

    def get_hinh_anh_url(self, obj):
        if obj.hinh_anh:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.hinh_anh.url)
            return obj.hinh_anh.url
        return None

    def get_ma_qr(self, obj):
        return get_thiet_bi_qr_payload(obj)

    def get_qr_url(self, obj):
        return get_thiet_bi_qr_url(obj, self.context.get('request'))


class VatTuSerializer(serializers.ModelSerializer):
    """Serializer cho model VatTu"""

    class Meta:
        model = VatTu
        fields = [
            'id', 'ma_vat_tu', 'ten_vat_tu', 'don_vi_tinh',
            'quy_cach', 'nha_che_tao', 'nha_cung_cap'
        ]


class ThietBiVatTuSerializer(serializers.ModelSerializer):
    """Serializer cho model ThietBiVatTu"""
    thiet_bi_ten = serializers.CharField(source='thiet_bi.ten', read_only=True)
    vat_tu_ten = serializers.CharField(source='vat_tu.ten_vat_tu', read_only=True)
    vat_tu_ma = serializers.CharField(source='vat_tu.ma_vat_tu', read_only=True)

    class Meta:
        model = ThietBiVatTu
        fields = [
            'id', 'thiet_bi', 'thiet_bi_ten', 'vat_tu', 'vat_tu_ten', 'vat_tu_ma',
            'so_luong', 'ghi_chu'
        ]


class ThongSoVanHanhSerializer(serializers.ModelSerializer):
    """Serializer cho model ThongSoVanHanh"""
    thiet_bi_ten = serializers.CharField(source='thiet_bi.ten', read_only=True)
    thiet_bi_ma_day_du = serializers.CharField(source='thiet_bi.ma_day_du', read_only=True)

    class Meta:
        model = ThongSoVanHanh
        fields = [
            'id', 'thiet_bi', 'thiet_bi_ten', 'thiet_bi_ma_day_du', 'ma_thong_so', 'ten_thong_so', 'gia_tri',
            'don_vi', 'gia_tri_toi_thieu', 'gia_tri_toi_da', 'gia_tri_thiet_ke',
            'ky_hieu_van_hanh', 'nha_may', 'ghi_chu', 'thoi_diem_nhap', 'ngay_nhap', 'nguoi_nhap'
        ]
        # Set read_only cho các field khóa duy nhất khi update
        read_only_fields = ['thiet_bi', 'ten_thong_so', 'thoi_diem_nhap', 'ngay_nhap', 'nguoi_nhap']


class ThongSoVanHanhCreateSerializer(serializers.ModelSerializer):
    """Serializer đơn giản cho việc tạo thông số vận hành"""

    class Meta:
        model = ThongSoVanHanh
        fields = [
            'thiet_bi', 'ma_thong_so', 'ten_thong_so', 'gia_tri',
            'don_vi', 'gia_tri_toi_thieu', 'gia_tri_toi_da', 'gia_tri_thiet_ke',
            'ky_hieu_van_hanh', 'nha_may', 'ghi_chu', 'thoi_diem_nhap', 'ngay_nhap'
        ]

    def validate_thoi_diem_nhap(self, value):
        """Chuẩn hóa format thoi_diem_nhap cho DateTimeField"""
        if isinstance(value, str):
            try:
                if 'T' in value:
                    # ISO format: YYYY-MM-DDTHH:MM:SS+07:00
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return dt
                elif ' ' in value:
                    # Format: YYYY-MM-DD HH:MM:SS
                    return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                else:
                    # Format: HH:MM hoặc HH:MM:SS
                    parts = value.split(':')
                    hh, mm = int(parts[0]), int(parts[1])
                    ss = int(parts[2]) if len(parts) > 2 else 0
                    # Tạo datetime với ngày hiện tại
                    today = datetime.now().date()
                    return datetime.combine(today, time(hh, mm, ss))
            except Exception as e:
                raise serializers.ValidationError(f'Định dạng thoi_diem_nhap không hợp lệ: {str(e)}')
        return value

    def validate(self, data):
        """Validation tùy chỉnh"""
        # Kiểm tra giá trị nằm trong khoảng cho phép
        gia_tri = data.get('gia_tri')
        gia_tri_toi_thieu = data.get('gia_tri_toi_thieu')
        gia_tri_toi_da = data.get('gia_tri_toi_da')

        if gia_tri and gia_tri_toi_thieu and gia_tri_toi_da:
            try:
                gia_tri_float = float(gia_tri)
                min_float = float(gia_tri_toi_thieu)
                max_float = float(gia_tri_toi_da)

                if gia_tri_float < min_float or gia_tri_float > max_float:
                    raise serializers.ValidationError(
                        f"Giá trị {gia_tri} nằm ngoài khoảng cho phép [{gia_tri_toi_thieu}, {gia_tri_toi_da}]"
                    )
            except (ValueError, TypeError):
                pass  # Bỏ qua nếu không thể convert sang số

        return data


class AnToanThietBiSerializer(serializers.ModelSerializer):
    """Serializer cho model AnToanThietBi"""
    thiet_bi_ten = serializers.CharField(source='thiet_bi.ten', read_only=True)

    class Meta:
        model = AnToanThietBi
        fields = [
            'id', 'thiet_bi', 'thiet_bi_ten', 'moi_nguy', 'bien_phap',
            'bao_ho_lao_dong', 'ghi_chu'
        ]


class DinhKemSerializer(serializers.ModelSerializer):
    """Serializer cho model DinhKem"""
    thiet_bi_ten = serializers.CharField(source='thiet_bi.ten', read_only=True)
    tep_url = serializers.SerializerMethodField()

    class Meta:
        model = DinhKem
        fields = [
            'id', 'thiet_bi', 'thiet_bi_ten', 'tieu_de', 'tep', 'tep_url',
            'duong_dan', 'dinh_dang', 'ngay_tai_len'
        ]
        read_only_fields = ['ngay_tai_len']

    def get_tep_url(self, obj):
        if obj.tep:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.tep.url)
            return obj.tep.url
        return None


class ThietBiDetailSerializer(serializers.ModelSerializer):
    """Serializer chi tiết cho thiết bị bao gồm các thông tin liên quan"""
    cha_ten = serializers.CharField(source='cha.ten', read_only=True)
    con = ThietBiListSerializer(many=True, read_only=True)
    vat_tu = ThietBiVatTuSerializer(source='thietbivattu_set', many=True, read_only=True)
    thong_so = ThongSoVanHanhSerializer(source='thongsovanhanh_set', many=True, read_only=True)
    an_toan = AnToanThietBiSerializer(source='antoanthietbi_set', many=True, read_only=True)
    dinh_kem = DinhKemSerializer(source='dinhkem_set', many=True, read_only=True)
    hinh_anh_url = serializers.SerializerMethodField()
    ma_qr = serializers.SerializerMethodField()
    qr_url = serializers.SerializerMethodField()
    so_lan_lam_viec_thang = serializers.SerializerMethodField()
    so_lan_lam_viec_thang_label = serializers.SerializerMethodField()
    so_lan_lam_viec_theo_thang = serializers.SerializerMethodField()

    class Meta:
        model = ThietBi
        fields = [
            'id', 'ten', 'ma', 'ma_day_du', 'cha', 'cha_ten',
            'loai', 'trang_thai', 'nha_che_tao', 'nha_cung_cap',
            'nuoc_san_xuat', 'nha_may', 'do_uu_tien', 'so_serial',
            'ma_van_hanh', 'bo_phan_quan_ly', 'bang_ve',
            'mo_ta_ky_thuat', 'cap', 'thu_tu', 'slug',
            'ngay_lap_dat', 'ngay_dua_vao_van_hanh', 'hinh_anh', 'hinh_anh_url',
            'ma_qr', 'qr_url', 'so_lan_lam_viec_thang',
            'so_lan_lam_viec_thang_label', 'so_lan_lam_viec_theo_thang',
            'con', 'vat_tu', 'thong_so', 'an_toan', 'dinh_kem'
        ]
        read_only_fields = ['ma_day_du', 'cap', 'slug']

    def get_hinh_anh_url(self, obj):
        if obj.hinh_anh:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.hinh_anh.url)
            return obj.hinh_anh.url
        return None

    def get_ma_qr(self, obj):
        return get_thiet_bi_qr_payload(obj)

    def get_qr_url(self, obj):
        return get_thiet_bi_qr_url(obj, self.context.get('request'))

    def _get_monthly_switch_detail_queryset(self, obj):
        try:
            from django.db.models import Q
            from nhatkyvanhanh.models import ChiTietChuyenDoiTBThang
        except Exception:
            return None

        device_query = Q(thiet_bi=obj)
        if obj.ma_day_du:
            device_query |= Q(thiet_bi__ma_day_du__startswith=f"{obj.ma_day_du}.")

        return ChiTietChuyenDoiTBThang.objects.select_related("so").filter(device_query)

    def _get_latest_monthly_switch_detail(self, obj):
        cached = getattr(obj, '_latest_monthly_switch_detail_cache', None)
        if cached is not None:
            return None if cached is False else cached

        queryset = self._get_monthly_switch_detail_queryset(obj)
        if queryset is None:
            obj._latest_monthly_switch_detail_cache = False
            return None

        detail = (
            queryset
            .order_by('-so__nam', '-so__thang', '-so__created_at', '-created_at')
            .first()
        )
        obj._latest_monthly_switch_detail_cache = detail or False
        return detail

    def get_so_lan_lam_viec_thang(self, obj):
        detail = self._get_latest_monthly_switch_detail(obj)
        return None if not detail else detail.thuc_hien

    def get_so_lan_lam_viec_thang_label(self, obj):
        detail = self._get_latest_monthly_switch_detail(obj)
        if not detail or not detail.so_id:
            return None
        return f"Tháng {detail.so.thang}/{detail.so.nam}"

    def get_so_lan_lam_viec_theo_thang(self, obj):
        try:
            from django.db.models import Sum
            from django.utils import timezone
        except Exception:
            return []

        queryset = self._get_monthly_switch_detail_queryset(obj)
        if queryset is None:
            return []

        latest_year = (
            queryset
            .exclude(so__nam__isnull=True)
            .order_by('-so__nam')
            .values_list('so__nam', flat=True)
            .first()
        )
        year = latest_year or timezone.localdate().year
        rows = (
            queryset
            .filter(so__nam=year)
            .values('so__thang')
            .annotate(so_lan=Sum('thuc_hien'))
            .order_by('so__thang')
        )
        values_by_month = {
            row['so__thang']: row['so_lan'] or 0
            for row in rows
        }
        return [
            {
                'nam': year,
                'thang': month,
                'so_lan': values_by_month.get(month),
            }
            for month in range(1, 13)
        ]


# -------------------------
# THÔNG SỐ TỔ MÁY SERIALIZERS
# -------------------------
class ThongSoToMaySerializer(serializers.ModelSerializer):
    """Serializer cho model ThongSoToMay"""
    thiet_bi_ten = serializers.CharField(source='thiet_bi.ten', read_only=True)
    thiet_bi_ma_day_du = serializers.CharField(source='thiet_bi.ma_day_du', read_only=True)

    class Meta:
        model = ThongSoToMay
        fields = [
            'id', 'thiet_bi', 'thiet_bi_ten', 'thiet_bi_ma_day_du', 'ten_thong_so', 'ma_thong_so',
            'don_vi', 'gia_tri', 'ghi_chu', 'nha_may', 'ky_hieu_van_hanh',
            'thoi_diem_nhap', 'ngay_nhap', 'created_at', 'updated_at', 'nguoi_nhap'
        ]
        # Set read_only cho các field khóa duy nhất khi update
        read_only_fields = ['thiet_bi', 'ten_thong_so', 'thoi_diem_nhap', 'ngay_nhap', 'created_at', 'updated_at', 'nguoi_nhap']


class ThongSoToMayCreateSerializer(serializers.ModelSerializer):
    """Serializer đơn giản cho việc tạo thông số tổ máy"""

    class Meta:
        model = ThongSoToMay
        fields = [
            'thiet_bi', 'ten_thong_so', 'ma_thong_so', 'don_vi', 'gia_tri',
            'ghi_chu', 'nha_may', 'ky_hieu_van_hanh', 'thoi_diem_nhap', 'ngay_nhap'
        ]
        # TẮT UniqueTogetherValidator để cho phép upsert ở bulk_create
        validators = []

    def validate_thoi_diem_nhap(self, value):
        """Chuẩn hóa format thoi_diem_nhap cho DateTimeField"""
        if isinstance(value, str):
            try:
                if 'T' in value:
                    # ISO format: YYYY-MM-DDTHH:MM:SS+07:00
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return dt
                elif ' ' in value:
                    # Format: YYYY-MM-DD HH:MM:SS
                    return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                else:
                    # Format: HH:MM hoặc HH:MM:SS
                    parts = value.split(':')
                    hh, mm = int(parts[0]), int(parts[1])
                    ss = int(parts[2]) if len(parts) > 2 else 0
                    # Tạo datetime với ngày hiện tại
                    today = datetime.now().date()
                    return datetime.combine(today, time(hh, mm, ss))
            except Exception as e:
                raise serializers.ValidationError(f'Định dạng thoi_diem_nhap không hợp lệ: {str(e)}')
        return value

    def validate(self, data):
        """Validation tùy chỉnh"""
        # Kiểm tra giá trị không âm nếu là số
        gia_tri = data.get('gia_tri')
        if gia_tri is not None:
            try:
                val_float = float(str(gia_tri).replace(",", "."))
                if val_float < 0:
                    raise serializers.ValidationError("Giá trị không được âm")
            except (ValueError, TypeError):
                pass

        return data


# -------------------------
# THÔNG SỐ TRẠM 110KV SERIALIZERS
# -------------------------
class ThongSoTram110KVSerializer(serializers.ModelSerializer):
    """Serializer cho model ThongSoTram110KV"""
    thiet_bi_ten = serializers.CharField(source='thiet_bi.ten', read_only=True)
    thiet_bi_ma_day_du = serializers.CharField(source='thiet_bi.ma_day_du', read_only=True)
    don_vi = serializers.CharField(allow_blank=True, required=False, allow_null=True)

    class Meta:
        model = ThongSoTram110KV
        fields = [
            'id', 'thiet_bi', 'thiet_bi_ten', 'thiet_bi_ma_day_du', 'ten_thong_so', 'ma_thong_so',
            'don_vi', 'gia_tri', 'ghi_chu', 'nha_may', 'ky_hieu_van_hanh',
            'thoi_diem_nhap', 'ngay_nhap', 'created_at', 'updated_at', 'nguoi_nhap'
        ]
        read_only_fields = ['thiet_bi', 'ten_thong_so', 'thoi_diem_nhap', 'ngay_nhap', 'created_at', 'updated_at', 'nguoi_nhap']


class ThongSoTram110KVCreateSerializer(serializers.ModelSerializer):
    """Serializer đơn giản cho việc tạo thông số trạm 110kV"""
    don_vi = serializers.CharField(allow_blank=True, required=False, allow_null=True)

    class Meta:
        model = ThongSoTram110KV
        fields = [
            'thiet_bi', 'ten_thong_so', 'ma_thong_so', 'don_vi', 'gia_tri',
            'ghi_chu', 'nha_may', 'ky_hieu_van_hanh', 'thoi_diem_nhap', 'ngay_nhap'
        ]
        validators = []

    def validate_thoi_diem_nhap(self, value):
        """Chuẩn hóa format thoi_diem_nhap cho DateTimeField"""
        if isinstance(value, str):
            try:
                if 'T' in value:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return dt
                elif ' ' in value:
                    return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                else:
                    parts = value.split(':')
                    hh, mm = int(parts[0]), int(parts[1])
                    ss = int(parts[2]) if len(parts) > 2 else 0
                    today = datetime.now().date()
                    return datetime.combine(today, time(hh, mm, ss))
            except Exception as e:
                raise serializers.ValidationError(f'Định dạng thoi_diem_nhap không hợp lệ: {str(e)}')
        return value


class NguongThongSoSerializer(serializers.ModelSerializer):
    """Serializer cho model NguongThongSo"""
    thiet_bi = serializers.PrimaryKeyRelatedField(
        queryset=ThietBi.objects.all(),
        required=False,
        allow_null=True,
    )
    thiet_bi_ten = serializers.CharField(source='thiet_bi.ten', read_only=True)
    thiet_bi_ma = serializers.CharField(source='thiet_bi.ma_day_du', read_only=True)

    class Meta:
        model = NguongThongSo
        fields = [
            'id', 'nha_may', 'thiet_bi', 'thiet_bi_ten', 'thiet_bi_ma',
            'ma_thong_so', 'ten_thong_so', 'don_vi', 'alarm', 'trip', 'rated',
            'min_value', 'max_value', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'thiet_bi': {'required': False, 'allow_null': True},
        }
        validators = []
