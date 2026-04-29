from datetime import datetime, timedelta
import re
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated

from core.factory_scope import filter_queryset_by_factory
from .models import ThietBi, ThongSoVanHanh, ThongSoToMay


def day_slots(ngay, tz=None):
    """
    Trả về list 48 datetime từ 00:00 -> 23:30 theo Vietnam timezone.
    Sử dụng Asia/Ho_Chi_Minh timezone để khớp với dữ liệu Excel import.
    Bắt đầu từ 00:00 và kết thúc lúc 23:30 (48 slots, mỗi slot 30 phút).
    """
    import pytz
    # Sử dụng Vietnam timezone để khớp với Excel import
    vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')

    # Tạo 48 slots từ 00:00 đến 23:30
    slots = []
    for i in range(48):
        hour = (i // 2)  # Mỗi giờ có 2 slot
        minute = 0 if (i % 2 == 0) else 30  # Slot chẵn: XX:00, slot lẻ: XX:30

        slot_time = datetime(ngay.year, ngay.month, ngay.day, hour, minute)
        slot_vietnam = vietnam_tz.localize(slot_time)
        slots.append(slot_vietnam)

    return slots


def day_slots_h1(ngay, tz=None):
    """
    Trả về list 24 datetime từ 00:00 -> 23:00 theo Vietnam timezone.
    Sử dụng Asia/Ho_Chi_Minh timezone để khớp với dữ liệu H1.
    Bắt đầu từ 00:00 và kết thúc lúc 23:00 (24 slots, mỗi slot 1 giờ).
    """
    import pytz
    # Sử dụng Vietnam timezone để khớp với Excel import
    vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')

    # Tạo 24 slots từ 00:00 đến 23:00
    slots = []
    for hour in range(24):
        slot_time = datetime(ngay.year, ngay.month, ngay.day, hour, 0)
        slot_vietnam = vietnam_tz.localize(slot_time)
        slots.append(slot_vietnam)

    return slots


def round30(dt):
    """Làm tròn datetime về mốc gần nhất: XX:00 hoặc XX:30"""
    # Làm tròn về mốc gần nhất: 00:00, 00:30, 01:00, 01:30, ...
    minute = dt.minute
    hour = dt.hour

    if minute <= 15:
        # 00:00-00:15 -> 00:00
        rounded_minute = 0
    elif minute <= 45:
        # 00:16-00:45 -> 00:30
        rounded_minute = 30
    else:
        # 00:46-00:59 -> 01:00 (next hour)
        rounded_minute = 0
        if hour < 23:
            hour = hour + 1
        else:
            # 23:46-23:59 -> 23:30 (giữ nguyên)
            rounded_minute = 30

    return dt.replace(hour=hour, minute=rounded_minute, second=0, microsecond=0)


def round_hour(dt):
    """Làm tròn datetime về mốc giờ gần nhất: XX:00"""
    # Làm tròn về mốc giờ gần nhất: 00:00, 01:00, 02:00, ...
    minute = dt.minute
    hour = dt.hour

    if minute <= 30:
        # 00:00-00:30 -> 00:00
        rounded_minute = 0
    else:
        # 00:31-00:59 -> 01:00 (next hour)
        rounded_minute = 0
        if hour < 23:
            hour = hour + 1
        else:
            # 23:31-23:59 -> 23:00 (giữ nguyên)
            hour = 23

    return dt.replace(hour=hour, minute=rounded_minute, second=0, microsecond=0)


class ThongSo48Serializer(serializers.Serializer):
    ma = serializers.CharField()
    ten = serializers.CharField()
    don_vi = serializers.CharField(allow_blank=True)
    values = serializers.ListField(
        child=serializers.FloatField(allow_null=True),
        max_length=48
    )


class ThongSo24Serializer(serializers.Serializer):
    ma = serializers.CharField()
    ten = serializers.CharField()
    don_vi = serializers.CharField(allow_blank=True)
    values = serializers.ListField(
        child=serializers.FloatField(allow_null=True),
        max_length=24
    )


class ThongSoByDaySerializer(serializers.Serializer):
    ngay = serializers.DateField()
    thiet_bi = serializers.DictField()
    thong_sos = ThongSo48Serializer(many=True)


class ThongSoToMayByDaySerializer(serializers.Serializer):
    ngay = serializers.DateField()
    thiet_bi = serializers.DictField()
    thong_sos = ThongSo24Serializer(many=True)


class ThongSoByDayView(APIView):
    """
    GET /api/quanlyvanhanh/thong-so-van-hanh/by_day/?thiet_bi_id=ID&ngay=YYYY-MM-DD
    hoặc dùng thiet_bi_ma=MA_DAY_DU

    Response tối ưu:
    {
      "ngay": "2025-10-20",
      "thiet_bi": {"id": 5, "ten": "...", "ma_day_du": "..."},
      "thong_sos": [
        {"ma": "dien_ap_kich_tu_h1", "ten": "Điện áp kích từ H1", "don_vi": "V", "values": [48 phần tử]},
        ...
      ]
    }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        tb_id = request.GET.get("thiet_bi_id")
        tb_ma = request.GET.get("thiet_bi_ma")
        ngay_str = request.GET.get("ngay")
        return_all = request.GET.get("return_all") in ("1", "true", "True")
        aggregate = request.GET.get("aggregate") in ("1", "true", "True")
        tz_param = request.GET.get("tz", "Asia/Ho_Chi_Minh")

        if not (tb_id or tb_ma):
            return Response({"detail": "Thiếu thiet_bi_id hoặc thiet_bi_ma"}, status=400)
        if not ngay_str:
            return Response({"detail": "Thiếu tham số ngay (YYYY-MM-DD)"}, status=400)

        try:
            ngay = datetime.fromisoformat(ngay_str).date()
        except Exception:
            return Response({"detail": "Định dạng ngày không hợp lệ, dùng YYYY-MM-DD"}, status=400)

        # Lấy thiết bị trong phạm vi nhà máy được phân quyền cho user.
        thiet_bi_queryset = filter_queryset_by_factory(
            ThietBi.objects.all(),
            request.user,
            "nha_may",
            "string",
        )
        try:
            if tb_id:
                tb = thiet_bi_queryset.get(pk=tb_id)
            else:
                tb = thiet_bi_queryset.get(ma_day_du=tb_ma)
        except ThietBi.DoesNotExist:
            return Response({"detail": "Không tìm thấy thiết bị"}, status=404)

        # Tạo 48 mốc thời gian của ngày
        slots = day_slots(ngay)

        # Query các bản ghi trong ngày (nằm trong [00:00, 24:00))
        start = slots[0]
        end = slots[-1] + timedelta(minutes=30)

        # Lấy tất cả bản ghi thuộc NGÀY chọn, dựa vào cả thoi_diem_nhap__date và ngay_nhap
        qs = (filter_queryset_by_factory(
                ThongSoVanHanh.objects.filter(thiet_bi=tb),
                request.user,
                "nha_may",
                "string",
              )
              .filter(Q(thoi_diem_nhap__date=ngay) | Q(ngay_nhap=ngay))
              .values_list("ma_thong_so", "thoi_diem_nhap", "gia_tri", "ten_thong_so", "don_vi"))

        # Chuẩn bị map {ma_thong_so: [None]*48}
        # Lấy danh sách các thông số có trong dữ liệu
        unique_params = set()
        for ma, td, val, ten, don_vi in qs:
            unique_params.add((ma, ten, don_vi))

        # Khởi tạo values rỗng cho tất cả thông số xuất hiện trong ngày
        ts_values = {ma: [None] * 48 for ma, ten, don_vi in unique_params}
        ts_info = {ma: {"ten": ten, "don_vi": don_vi} for ma, ten, don_vi in unique_params}

        # Build index mốc cho nhanh
        slot_index = {round30(dt): idx for idx, dt in enumerate(slots)}

        # Bổ sung chống "lạc ngày" do 24:00
        # Map 24:00 (00:00 ngày sau) về slot cuối cùng (47)
        import pytz
        vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        twenty_four = vietnam_tz.localize(datetime(ngay.year, ngay.month, ngay.day, 0, 0)) + timedelta(days=1)
        slot_index[twenty_four] = 47  # map 24:00 (00:00 ngày sau) về slot cuối

        # Lưới an toàn: map các giá trị thời gian cũ về slot 47
        # Map 23:59:59 về slot 47 (23:30)
        twenty_three_fifty_nine = vietnam_tz.localize(datetime(ngay.year, ngay.month, ngay.day, 23, 59, 59))
        slot_index[twenty_three_fifty_nine] = 47

        # Helper: parse số kiểu Việt
        NUM_RE = re.compile(r"[-+]?\d+(?:[.,\s]\d+)*([.,]\d+)?")

        def parse_vi_number(s):
            if s is None:
                return None
            if isinstance(s, (int, float, Decimal)):
                try:
                    return Decimal(str(s))
                except InvalidOperation:
                    return None
            s = str(s).strip()
            if not s:
                return None
            m = NUM_RE.search(s)
            if not m:
                return None
            s = m.group(0)
            has_dot = '.' in s
            has_comma = ',' in s
            if has_dot and has_comma:
                last_dot = s.rfind('.')
                last_comma = s.rfind(',')
                dec = '.' if last_dot > last_comma else ','
            elif has_comma:
                dec = ','
            elif has_dot:
                dec = '.'
            else:
                dec = None
            s = s.replace(' ', '')
            if dec:
                other = ',' if dec == '.' else '.'
                s = s.replace(other, '')
                s = s.replace(dec, '.')
            try:
                return Decimal(s)
            except InvalidOperation:
                return None

        # Nạp dữ liệu
        for ma, td, val, ten, don_vi in qs:
            # Bảo đảm có key info
            if ma not in ts_values:
                ts_values[ma] = [None] * 48
                ts_info[ma] = {"ten": (ten or ""), "don_vi": (don_vi or "")}

            # Nếu thiếu thoi_diem_nhap, bỏ qua record (không xác định được slot)
            if not td:
                continue

            try:
                # Đảm bảo td_local là Vietnam timezone để khớp với slot_index
                import pytz
                vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
                if timezone.is_aware(td):
                    # Nếu đã có timezone, chuyển về Vietnam timezone
                    td_local = td.astimezone(vietnam_tz)
                else:
                    # Nếu chưa có timezone, giả sử là Vietnam timezone
                    td_local = vietnam_tz.localize(td)
            except Exception:
                # Fallback: giả sử td đã là Vietnam timezone
                td_local = td

            td_slot = round30(td_local)
            idx = slot_index.get(td_slot)

            if idx is None:
                # Lệch ngày do TZ → bỏ
                continue
            num = parse_vi_number(val)
            ts_values[ma][idx] = float(num) if num is not None else None

        # Trả dữ liệu theo return_all hoặc chỉ những thông số có dữ liệu
        thong_sos = []
        for ma, arr in ts_values.items():
            has_data = any(v is not None for v in arr)
            # Nếu aggregate=true, luôn trả về tất cả thông số (kể cả rỗng)
            if has_data or return_all or aggregate:
                info = ts_info.get(ma, {"ten": "", "don_vi": ""})
                thong_sos.append({
                    "ma": ma,
                    "ten": info.get("ten") or "",
                    "don_vi": info.get("don_vi") or "",
                    "values": arr,
                })

        payload = {
            "ngay": ngay,
            "thiet_bi": {"id": tb.id, "ten": tb.ten, "ma_day_du": tb.ma_day_du},
            "thong_sos": sorted(thong_sos, key=lambda x: x["ma"]),
        }
        return Response(ThongSoByDaySerializer(payload).data, status=status.HTTP_200_OK)


class ThongSoToMayByDayView(APIView):
    """
    GET /api/quanlyvanhanh/thong-so-to-may/by_day/?thiet_bi_id=ID&ngay=YYYY-MM-DD
    hoặc dùng thiet_bi_ma=MA_DAY_DU

    Response tối ưu cho H1 (24 slots):
    {
      "ngay": "2025-10-20",
      "thiet_bi": {"id": 5, "ten": "...", "ma_day_du": "..."},
      "thong_sos": [
        {"ma": "ap_luc_nuoc", "ten": "Áp lực nước", "don_vi": "bar", "values": [24 phần tử]},
        ...
      ]
    }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        tb_id = request.GET.get("thiet_bi_id")
        tb_ma = request.GET.get("thiet_bi_ma")
        ngay_str = request.GET.get("ngay")
        return_all = request.GET.get("return_all") in ("1", "true", "True")
        aggregate = request.GET.get("aggregate") in ("1", "true", "True")
        tz_param = request.GET.get("tz", "Asia/Ho_Chi_Minh")

        if not (tb_id or tb_ma):
            return Response({"detail": "Thiếu thiet_bi_id hoặc thiet_bi_ma"}, status=400)
        if not ngay_str:
            return Response({"detail": "Thiếu tham số ngay (YYYY-MM-DD)"}, status=400)

        try:
            ngay = datetime.fromisoformat(ngay_str).date()
        except Exception:
            return Response({"detail": "Định dạng ngày không hợp lệ, dùng YYYY-MM-DD"}, status=400)

        # Lấy thiết bị trong phạm vi nhà máy được phân quyền cho user.
        thiet_bi_queryset = filter_queryset_by_factory(
            ThietBi.objects.all(),
            request.user,
            "nha_may",
            "string",
        )
        try:
            if tb_id:
                tb = thiet_bi_queryset.get(pk=tb_id)
            else:
                tb = thiet_bi_queryset.get(ma_day_du=tb_ma)
        except ThietBi.DoesNotExist:
            return Response({"detail": "Không tìm thấy thiết bị"}, status=404)

        # Tạo 24 mốc thời gian của ngày (00:00 -> 23:00)
        slots = day_slots_h1(ngay)

        # Query các bản ghi trong ngày
        qs = (filter_queryset_by_factory(
                ThongSoToMay.objects.filter(thiet_bi=tb),
                request.user,
                "nha_may",
                "string",
              )
              .filter(Q(thoi_diem_nhap__date=ngay) | Q(ngay_nhap=ngay))
              .values_list("ma_thong_so", "thoi_diem_nhap", "gia_tri", "ten_thong_so", "don_vi"))

        # Chuẩn bị map {ma_thong_so: [None]*24}
        unique_params = set()
        for ma, td, val, ten, don_vi in qs:
            unique_params.add((ma, ten, don_vi))

        # Khởi tạo values rỗng cho tất cả thông số xuất hiện trong ngày
        ts_values = {ma: [None] * 24 for ma, ten, don_vi in unique_params}
        ts_info = {ma: {"ten": ten, "don_vi": don_vi} for ma, ten, don_vi in unique_params}

        # Build index mốc cho nhanh
        slot_index = {round_hour(dt): idx for idx, dt in enumerate(slots)}

        # Bổ sung chống "lạc ngày" do 24:00
        import pytz
        vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        twenty_four = vietnam_tz.localize(datetime(ngay.year, ngay.month, ngay.day, 0, 0)) + timedelta(days=1)
        slot_index[twenty_four] = 23  # map 24:00 về slot cuối (23)

        # Helper: parse số kiểu Việt
        NUM_RE = re.compile(r"[-+]?\d+(?:[.,\s]\d+)*([.,]\d+)?")

        def parse_vi_number(s):
            if s is None:
                return None
            if isinstance(s, (int, float, Decimal)):
                try:
                    return Decimal(str(s))
                except InvalidOperation:
                    return None
            s = str(s).strip()
            if not s:
                return None
            m = NUM_RE.search(s)
            if not m:
                return None
            s = m.group(0)
            has_dot = '.' in s
            has_comma = ',' in s
            if has_dot and has_comma:
                last_dot = s.rfind('.')
                last_comma = s.rfind(',')
                dec = '.' if last_dot > last_comma else ','
            elif has_comma:
                dec = ','
            elif has_dot:
                dec = '.'
            else:
                dec = None
            s = s.replace(' ', '')
            if dec:
                other = ',' if dec == '.' else '.'
                s = s.replace(other, '')
                s = s.replace(dec, '.')
            try:
                return Decimal(s)
            except InvalidOperation:
                return None

        # Nạp dữ liệu
        for ma, td, val, ten, don_vi in qs:
            # Bảo đảm có key info
            if ma not in ts_values:
                ts_values[ma] = [None] * 24
                ts_info[ma] = {"ten": (ten or ""), "don_vi": (don_vi or "")}

            # Nếu thiếu thoi_diem_nhap, bỏ qua record
            if not td:
                continue

            try:
                # Đảm bảo td_local là Vietnam timezone
                import pytz
                vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
                if timezone.is_aware(td):
                    td_local = td.astimezone(vietnam_tz)
                else:
                    td_local = vietnam_tz.localize(td)
            except Exception:
                td_local = td

            td_slot = round_hour(td_local)
            idx = slot_index.get(td_slot)

            if idx is None:
                # Lệch ngày do TZ → bỏ
                continue
            num = parse_vi_number(val)
            ts_values[ma][idx] = float(num) if num is not None else None

        # Trả dữ liệu theo return_all hoặc chỉ những thông số có dữ liệu
        thong_sos = []
        for ma, arr in ts_values.items():
            has_data = any(v is not None for v in arr)
            # Nếu aggregate=true, luôn trả về tất cả thông số (kể cả rỗng)
            if has_data or return_all or aggregate:
                info = ts_info.get(ma, {"ten": "", "don_vi": ""})
                thong_sos.append({
                    "ma": ma,
                    "ten": info.get("ten") or "",
                    "don_vi": info.get("don_vi") or "",
                    "values": arr,
                })

        payload = {
            "ngay": ngay,
            "thiet_bi": {"id": tb.id, "ten": tb.ten, "ma_day_du": tb.ma_day_du},
            "thong_sos": sorted(thong_sos, key=lambda x: x["ma"]),
        }
        return Response(ThongSoToMayByDaySerializer(payload).data, status=status.HTTP_200_OK)
