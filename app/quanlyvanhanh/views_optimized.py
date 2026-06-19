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

from core.factory_scope import filter_queryset_by_factory, has_profile_permission, get_user_factory_code
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
        child=serializers.JSONField(allow_null=True),
        max_length=48
    )
    alarm = serializers.FloatField(allow_null=True, required=False)
    trip = serializers.FloatField(allow_null=True, required=False)
    rated = serializers.FloatField(allow_null=True, required=False)
    min_value = serializers.FloatField(allow_null=True, required=False)
    max_value = serializers.FloatField(allow_null=True, required=False)


class ThongSo24Serializer(serializers.Serializer):
    ma = serializers.CharField()
    ten = serializers.CharField()
    don_vi = serializers.CharField(allow_blank=True)
    values = serializers.ListField(
        child=serializers.JSONField(allow_null=True),
        max_length=24
    )
    alarm = serializers.FloatField(allow_null=True, required=False)
    trip = serializers.FloatField(allow_null=True, required=False)
    rated = serializers.FloatField(allow_null=True, required=False)
    min_value = serializers.FloatField(allow_null=True, required=False)
    max_value = serializers.FloatField(allow_null=True, required=False)


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
        if not has_profile_permission(request.user, "can_view_operation_parameters"):
            return Response(
                {"detail": "Tài khoản của bạn chưa được cấp quyền xem thông số vận hành. Vui lòng liên hệ quản trị viên."},
                status=status.HTTP_403_FORBIDDEN
            )
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

        # Luôn sử dụng 48 chu kỳ (30 phút) cho thông số vận hành điện để khớp với database lưu chu kỳ 30 phút
        num_cycles = 48
        slots = day_slots(ngay)

        # Lấy tất cả bản ghi thuộc NGÀY chọn, dựa vào cả thoi_diem_nhap__date và ngay_nhap
        qs = (filter_queryset_by_factory(
                ThongSoVanHanh.objects.filter(thiet_bi__ma_day_du__startswith=tb.ma_day_du),
                request.user,
                "nha_may",
                "string",
              )
              .filter(Q(thoi_diem_nhap__date=ngay) | Q(ngay_nhap=ngay))
              .values_list("ma_thong_so", "thoi_diem_nhap", "gia_tri", "ten_thong_so", "don_vi"))

        # Chuẩn bị map {ma_thong_so: [None]*num_cycles}
        # Lấy danh sách các thông số có trong dữ liệu
        unique_params = set()
        for ma, td, val, ten, don_vi in qs:
            unique_params.add((ma, ten, don_vi))

        # Khởi tạo values rỗng cho tất cả thông số xuất hiện trong ngày
        ts_values = {ma: [None] * num_cycles for ma, ten, don_vi in unique_params}
        ts_info = {ma: {"ten": ten, "don_vi": don_vi} for ma, ten, don_vi in unique_params}

        # Build index mốc cho nhanh
        slot_index = {round30(dt): idx for idx, dt in enumerate(slots)}

        # Bổ sung chống "lạc ngày" do 24:00
        # Map 24:00 (00:00 ngày sau) về slot cuối cùng
        import pytz
        vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        twenty_four = vietnam_tz.localize(datetime(ngay.year, ngay.month, ngay.day, 0, 0)) + timedelta(days=1)
        slot_index[twenty_four] = num_cycles - 1  # map 24:00 (00:00 ngày sau) về slot cuối

        # Lưới an toàn: map các giá trị thời gian cũ về slot cuối
        twenty_three_fifty_nine = vietnam_tz.localize(datetime(ngay.year, ngay.month, ngay.day, 23, 59, 59))
        slot_index[twenty_three_fifty_nine] = num_cycles - 1

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
                ts_values[ma] = [None] * num_cycles
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
        from quanlyvanhanh.services.thongso_history_service import get_metric_thresholds

        thong_sos = []
        for ma, arr in ts_values.items():
            has_data = any(v is not None for v in arr)
            # Nếu aggregate=true, luôn trả về tất cả thông số (kể cả rỗng)
            if has_data or return_all or aggregate:
                info = ts_info.get(ma, {"ten": "", "don_vi": ""})
                thresh = get_metric_thresholds(request.user, "dien", ma, tb)
                thong_sos.append({
                    "ma": ma,
                    "ten": info.get("ten") or "",
                    "don_vi": info.get("don_vi") or "",
                    "values": arr,
                    "alarm": thresh.get("alarm"),
                    "trip": thresh.get("trip"),
                    "rated": thresh.get("rated"),
                    "min_value": thresh.get("min_value"),
                    "max_value": thresh.get("max_value"),
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
        if not has_profile_permission(request.user, "can_view_operation_parameters"):
            return Response(
                {"detail": "Tài khoản của bạn chưa được cấp quyền xem thông số vận hành. Vui lòng liên hệ quản trị viên."},
                status=status.HTTP_403_FORBIDDEN
            )
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

        # Query các bản ghi trong ngày (bao gồm các thiết bị con của tổ máy)
        prefix = ".".join(tb.ma_day_du.split(".")[:3])  # E.g., "SH.TB.H1" hoặc "SH.TB.H2"
        qs = (filter_queryset_by_factory(
                ThongSoToMay.objects.filter(thiet_bi__ma_day_du__startswith=prefix),
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
            if val is not None:
                val_clean = str(val).strip()
                stripped = val_clean.replace(".", "").replace(",", "").replace("+", "").replace("-", "").replace(" ", "")
                if stripped.isdigit():
                    num = parse_vi_number(val_clean)
                    ts_values[ma][idx] = float(num) if num is not None else None
                else:
                    ts_values[ma][idx] = val_clean
            else:
                ts_values[ma][idx] = None

        # Trả dữ liệu theo return_all hoặc chỉ những thông số có dữ liệu
        from quanlyvanhanh.services.thongso_history_service import get_metric_thresholds

        thong_sos = []
        for ma, arr in ts_values.items():
            has_data = any(v is not None for v in arr)
            # Nếu aggregate=true, luôn trả về tất cả thông số (kể cả rỗng)
            if has_data or return_all or aggregate:
                info = ts_info.get(ma, {"ten": "", "don_vi": ""})
                thresh = get_metric_thresholds(request.user, "tomay", ma, tb)
                thong_sos.append({
                    "ma": ma,
                    "ten": info.get("ten") or "",
                    "don_vi": info.get("don_vi") or "",
                    "values": arr,
                    "alarm": thresh.get("alarm"),
                    "trip": thresh.get("trip"),
                    "rated": thresh.get("rated"),
                    "min_value": thresh.get("min_value"),
                    "max_value": thresh.get("max_value"),
                })

        payload = {
            "ngay": ngay,
            "thiet_bi": {"id": tb.id, "ten": tb.ten, "ma_day_du": tb.ma_day_du},
            "thong_sos": sorted(thong_sos, key=lambda x: x["ma"]),
        }
        return Response(ThongSoToMayByDaySerializer(payload).data, status=status.HTTP_200_OK)


class ThongSoActiveAlertsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not has_profile_permission(request.user, "can_receive_alert_notifications"):
            return Response([], status=status.HTTP_200_OK)

        if not has_profile_permission(request.user, "can_view_operation_parameters"):
            return Response(
                {"detail": "Tài khoản của bạn chưa được cấp quyền xem thông số vận hành. Vui lòng liên hệ quản trị viên."},
                status=status.HTTP_403_FORBIDDEN
            )
        from quanlyvanhanh.services.thongso_history_service import get_metric_thresholds
        from quanlyvanhanh.models import ThongSoTram110KV
        from django.utils.dateparse import parse_datetime
        import pytz

        target_date_str = request.GET.get("date")
        if target_date_str:
            try:
                target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            except ValueError:
                target_date = timezone.localtime(timezone.now()).date()
            target_dates = [target_date]
        else:
            today = timezone.localtime(timezone.now()).date()
            has_today = (
                filter_queryset_by_factory(ThongSoVanHanh.objects.all(), request.user, "nha_may", "string").filter(ngay_nhap=today).exists() or
                filter_queryset_by_factory(ThongSoToMay.objects.all(), request.user, "nha_may", "string").filter(ngay_nhap=today).exists() or
                filter_queryset_by_factory(ThongSoTram110KV.objects.all(), request.user, "nha_may", "string").filter(ngay_nhap=today).exists()
            )
            if has_today:
                target_date = today
                target_dates = [today, today - timedelta(days=1)]
            else:
                from django.db.models import Max
                latest_vh = filter_queryset_by_factory(ThongSoVanHanh.objects.all(), request.user, "nha_may", "string").aggregate(Max('ngay_nhap'))['ngay_nhap__max']
                latest_tm = filter_queryset_by_factory(ThongSoToMay.objects.all(), request.user, "nha_may", "string").aggregate(Max('ngay_nhap'))['ngay_nhap__max']
                latest_tr = filter_queryset_by_factory(ThongSoTram110KV.objects.all(), request.user, "nha_may", "string").aggregate(Max('ngay_nhap'))['ngay_nhap__max']
                dates = [d for d in [latest_vh, latest_tm, latest_tr] if d is not None]
                target_date = max(dates) if dates else today
                target_dates = [target_date]

        # 1. Query parameter records from all 3 models for the selected dates.
        qs_vh = filter_queryset_by_factory(ThongSoVanHanh.objects.all(), request.user, "nha_may", "string").filter(ngay_nhap__in=target_dates)
        qs_tm = filter_queryset_by_factory(ThongSoToMay.objects.all(), request.user, "nha_may", "string").filter(ngay_nhap__in=target_dates)
        qs_tr = filter_queryset_by_factory(ThongSoTram110KV.objects.all(), request.user, "nha_may", "string").filter(ngay_nhap__in=target_dates)

        records = []
        for r in qs_vh.select_related("thiet_bi"):
            records.append({
                "source": "dien",
                "thiet_bi": r.thiet_bi,
                "ma_thong_so": r.ma_thong_so,
                "ten_thong_so": r.ten_thong_so,
                "gia_tri": r.gia_tri,
                "don_vi": r.don_vi,
                "thoi_diem_nhap": r.thoi_diem_nhap,
            })
        for r in qs_tm.select_related("thiet_bi"):
            records.append({
                "source": "tomay",
                "thiet_bi": r.thiet_bi,
                "ma_thong_so": r.ma_thong_so,
                "ten_thong_so": r.ten_thong_so,
                "gia_tri": r.gia_tri,
                "don_vi": r.don_vi,
                "thoi_diem_nhap": r.thoi_diem_nhap,
            })
        for r in qs_tr.select_related("thiet_bi"):
            records.append({
                "source": "tram",
                "thiet_bi": r.thiet_bi,
                "ma_thong_so": r.ma_thong_so,
                "ten_thong_so": r.ten_thong_so,
                "gia_tri": r.gia_tri,
                "don_vi": r.don_vi,
                "thoi_diem_nhap": r.thoi_diem_nhap,
            })

        # Helper: parse number
        NUM_RE = re.compile(r"[-+]?\d+(?:[.,\s]\d+)*([.,]\d+)?")

        def parse_number_local(s):
            if s is None:
                return None
            if isinstance(s, (int, float, Decimal)):
                return float(s)
            s = str(s).strip()
            if not s:
                return None
            m = NUM_RE.search(s)
            if not m:
                return None
            s = m.group(0).replace(' ', '')
            has_dot = '.' in s
            has_comma = ',' in s
            if has_dot and has_comma:
                dec = '.' if s.rfind('.') > s.rfind(',') else ','
            elif has_comma:
                dec = ','
            elif has_dot:
                dec = '.'
            else:
                dec = None
            if dec:
                other = ',' if dec == '.' else '.'
                s = s.replace(other, '').replace(dec, '.')
            try:
                return float(s)
            except Exception:
                return None

        # Resolve alerts
        alerts_map = {}
        thresholds_cache = {}

        for r in records:
            val = parse_number_local(r["gia_tri"])
            if val is None:
                continue

            # Check cache for thresholds
            cache_key = (r["source"], r["ma_thong_so"], r["thiet_bi"].id)
            if cache_key not in thresholds_cache:
                thresh = get_metric_thresholds(request.user, r["source"], r["ma_thong_so"], r["thiet_bi"])
                thresholds_cache[cache_key] = thresh
            else:
                thresh = thresholds_cache[cache_key]

            alarm = thresh.get("alarm")
            trip = thresh.get("trip")
            rated = thresh.get("rated")
            min_val = thresh.get("min_value")
            max_val = thresh.get("max_value")

            if alarm is None and trip is None and min_val is None and max_val is None:
                continue

            # Determine limit direction
            is_low_limit = False
            ma = r["ma_thong_so"]
            don_vi = r["don_vi"] or ""
            is_flow = "luu_luong" in ma or don_vi.lower() == "l/p"
            is_pressure = "ap_luc" in ma or "ap_suat" in ma or don_vi.lower() in ("bar", "mpa")
            if is_flow or is_pressure:
                is_low_limit = True

            if alarm is not None and trip is not None:
                is_low_limit = trip < alarm
            elif rated is not None:
                if alarm is not None:
                    is_low_limit = alarm < rated
                elif trip is not None:
                    is_low_limit = trip < rated

            is_alert = False
            alert_type = None

            if trip is not None:
                if is_low_limit and val <= trip:
                    is_alert = True
                    alert_type = "trip"
                elif not is_low_limit and val >= trip:
                    is_alert = True
                    alert_type = "trip"

            if not is_alert and alarm is not None:
                # Tính biên cảnh báo (Warning Margin) tiệm cận alarm
                margin = abs(alarm - rated) * 0.2 if rated is not None else alarm * 0.02
                if is_low_limit:
                    if val <= alarm:
                        is_alert = True
                        alert_type = "alarm"
                    elif val <= alarm + margin:
                        is_alert = True
                        alert_type = "near_alarm"
                else:
                    if val >= alarm:
                        is_alert = True
                        alert_type = "alarm"
                    elif val >= alarm - margin:
                        is_alert = True
                        alert_type = "near_alarm"



            if is_alert:
                # Group by device code + parameter code to keep only the latest alert
                group_key = (r["thiet_bi"].ma_day_du, r["ma_thong_so"])
                local_time = timezone.localtime(r["thoi_diem_nhap"])
                
                alert_item = {
                    "id": f"{r['source']}-{r['thiet_bi'].ma_day_du}-{r['ma_thong_so']}-{r['thoi_diem_nhap'].timestamp()}",
                    "thiet_bi_ten": r["thiet_bi"].ten,
                    "thiet_bi_ma": r["thiet_bi"].ma_day_du,
                    "ma_thong_so": r["ma_thong_so"],
                    "ten_thong_so": r["ten_thong_so"],
                    "gia_tri": val,
                    "don_vi": r["don_vi"],
                    "alarm": alarm,
                    "trip": trip,
                    "min_value": min_val,
                    "max_value": max_val,
                    "thoi_diem_nhap": local_time.isoformat(),
                    "alert_type": alert_type,
                    "source": r["source"],
                    "direction": "low" if is_low_limit else "high",
                    "nha_may": r["thiet_bi"].nha_may or ("Sông Hinh" if r["thiet_bi"].ma_day_du.startswith("SH") else ("Vĩnh Sơn" if r["thiet_bi"].ma_day_du.startswith("VS") else "")),
                }

                existing = alerts_map.get(group_key)
                if not existing or r["thoi_diem_nhap"] > parse_datetime(existing["thoi_diem_nhap"]):
                    alerts_map[group_key] = alert_item

        return Response(list(alerts_map.values()), status=status.HTTP_200_OK)
