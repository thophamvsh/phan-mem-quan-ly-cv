from datetime import timedelta
from django.conf import settings
from django.db.models import Max
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .views.views_sanxuat import user_can_access_plant, user_can_view_realtime_hydrology
from .vrain_history_models import VrainStation, VrainRainfallInterval, VrainSourceSample
from .vrain_history_services import aligned, contract_verified
from .vrain_history_provider import rainfall


def read_window(params):
    try:
        start, end = parse_datetime(params.get("start", "")), parse_datetime(params.get("end", ""))
        if start is None or end is None or not aligned(start) or not aligned(end) or not start < end or end - start > timedelta(days=7) or end > timezone.now():
            raise ValueError()
        return start, end
    except (ValueError, TypeError):
        return None


class VrainHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]
    mode = "intervals"

    def finalize_response(self, *args, **kwargs):
        response = super().finalize_response(*args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response

    def get(self, request):
        plant = request.query_params.get("plant")
        if plant not in {"songhinh", "vinhson"}:
            return Response({"detail": "Invalid plant"}, status=400)
        if not user_can_view_realtime_hydrology(request.user) or not user_can_access_plant(request.user, plant):
            return Response({"detail": "Permission denied"}, status=403)
        stations = VrainStation.objects.filter(plant=plant, enabled=True).order_by("source_station_code")
        if self.mode == "status":
            items = []
            now = timezone.now()
            for station in stations:
                latest = station.samples.aggregate(source=Max("source_timestamp"), received=Max("last_received_at"))
                source, received = latest["source"], latest["received"]
                fresh = source is not None and received is not None and now-source <= timedelta(minutes=40) and now-received <= timedelta(minutes=40)
                items.append({"code": station.source_station_code, "name": station.name, "latest_source_timestamp": source, "last_received_at": received, "status": "fresh" if fresh else "stale" if source else "unavailable"})
            return Response({"collection_enabled": getattr(settings, "VRAIN_HISTORY_ENABLED", False), "contract_verified": contract_verified(), "stations": items})
        if not contract_verified():
            return Response({"detail": "VRAIN interval semantics have not been verified; source evidence only.", "code": "contract_unverified"}, status=409)
        window = read_window(request.query_params)
        if window is None:
            return Response({"detail": "Supply aware start/end on 10-minute boundaries, at most 7 days, in the past."}, status=400)
        start, end = window
        station_code = request.query_params.get("station")
        if station_code:
            stations = stations.filter(source_station_code=station_code)
            if not stations.exists():
                return Response({"detail": "Station unavailable in this plant"}, status=404)
        rows = VrainRainfallInterval.objects.filter(station__in=stations, interval_start__gte=start, interval_end__lte=end)
        if self.mode == "summary":
            expected = int((end - start).total_seconds() // 600)
            summaries = []
            for station in stations:
                values = list(rows.filter(station=station))
                valid = [row for row in values if row.status == "valid" and row.rainfall_mm is not None]
                complete = len(valid) == expected
                partial = sum((row.rainfall_mm for row in valid), start=0) if valid else None
                latest = max((row.interval_end for row in valid), default=None)
                summaries.append({"station": station.source_station_code, "expected_intervals": expected, "valid_intervals": len(valid), "coverage_ratio": len(valid)/expected, "complete": complete, "rainfall_mm": partial if complete else None, "partial_rainfall_mm": partial, "data_end": latest, "status": "complete" if complete else "partial" if valid else "unavailable"})
            return Response({"start": start, "end": end, "stations": summaries})
        try:
            page = int(request.query_params.get("page", "1"))
            if not 1 <= page <= 10000:
                raise ValueError()
        except ValueError:
            return Response({"detail": "Invalid page"}, status=400)
        ordered = rows.select_related("station", "revision__sample").order_by("interval_end", "station_id")
        chunk = list(ordered[(page-1)*500:page*500+1])
        return Response({"page": page, "has_more": len(chunk)>500, "results": [{"station": r.station.source_station_code, "interval_start": r.interval_start, "interval_end": r.interval_end, "rainfall_mm": r.rainfall_mm, "status": r.status, "quality_flags": r.quality_flags, "source_timestamp": r.revision.sample.source_timestamp if r.revision_id else None, "received_at": r.revision.received_at if r.revision_id else None, "revision_id": r.revision_id} for r in chunk[:500]]})


class VrainSummaryAPIView(VrainHistoryAPIView):
    mode = "summary"


class VrainSyncStatusAPIView(VrainHistoryAPIView):
    mode = "status"


class VrainSourceSamplesAPIView(VrainHistoryAPIView):
    """Read-only source matrix; one page contains whole timestamps across stations."""
    def get(self, request):
        plant = request.query_params.get("plant")
        if plant not in {"songhinh", "vinhson"}:
            return Response({"detail": "Invalid plant"}, status=400)
        if not user_can_view_realtime_hydrology(request.user) or not user_can_access_plant(request.user, plant):
            return Response({"detail": "Permission denied"}, status=403)
        try:
            start = parse_datetime(request.query_params.get("start", ""))
            end = parse_datetime(request.query_params.get("end", ""))
            page = int(request.query_params.get("page", "1"))
            if start is None or end is None or timezone.is_naive(start) or timezone.is_naive(end) or not start < end or end-start > timedelta(days=1) or end > timezone.now() or not 1 <= page <= 10000:
                raise ValueError()
        except (ValueError, TypeError):
            return Response({"detail": "Supply aware start/end in the past, at most 24 hours, and a positive page."}, status=400)
        stations = VrainStation.objects.filter(plant=plant, enabled=True).order_by("source_station_code")
        code = request.query_params.get("station")
        if code:
            stations = stations.filter(source_station_code=code)
            if not stations.exists():
                return Response({"detail": "Station unavailable in this plant"}, status=404)
        station_list = list(stations)
        rows = VrainSourceSample.objects.filter(station__in=station_list, source_timestamp__gte=start, source_timestamp__lt=end)
        timestamps = rows.order_by("-source_timestamp").values_list("source_timestamp", flat=True).distinct()
        total = timestamps.count()
        chunk = list(timestamps[(page-1)*50:page*50+1])
        selected = chunk[:50]
        matrix = {stamp: {} for stamp in selected}
        for row in rows.filter(source_timestamp__in=selected).select_related("station"):
            depth = rainfall(row.data.get("depth"))
            matrix[row.source_timestamp][row.station.source_station_code] = {"depth_mm": depth, "status": "source_unverified" if depth is not None else "invalid", "first_received_at": row.first_received_at, "last_received_at": row.last_received_at}
        latest = rows.aggregate(source=Max("source_timestamp"), received=Max("last_received_at"))
        latest_by_station = {r["station_id"]: r for r in VrainSourceSample.objects.filter(station__in=station_list).values("station_id").annotate(source=Max("source_timestamp"), received=Max("last_received_at"))}
        now = timezone.now()
        station_meta = []
        for station in station_list:
            meta = latest_by_station.get(station.pk, {})
            source, received = meta.get("source"), meta.get("received")
            fresh = source is not None and received is not None and timedelta(0) <= now-source <= timedelta(minutes=40) and timedelta(0) <= now-received <= timedelta(minutes=40)
            station_meta.append({"code": station.source_station_code, "name": station.name, "status": "fresh" if fresh else "stale" if source else "unavailable", "latest_source_timestamp": source, "last_received_at": received})
        return Response({"plant": plant, "data_kind": "source_samples", "interval_verified": False, "collection_enabled": getattr(settings, "VRAIN_HISTORY_ENABLED", False), "timezone": "Asia/Ho_Chi_Minh", "start": start, "end": end, "page": page, "page_size": 50, "total_timestamps": total, "has_more": len(chunk)>50, "latest_source_timestamp": latest["source"], "last_received_at": latest["received"], "stations": station_meta, "results": [{"time_point": stamp, "samples": matrix[stamp]} for stamp in selected]})
