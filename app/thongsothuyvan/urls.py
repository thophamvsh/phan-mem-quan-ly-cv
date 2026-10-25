from .vrain_history_views import VrainSourceSamplesAPIView
from .vrain_history_views import VrainHistoryAPIView, VrainSummaryAPIView, VrainSyncStatusAPIView
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    SonghinhMnhViewSet,
    ThuongKonTumMnhViewSet,
    Vinhson_HoAViewSet,
    Vinhson_HoBViewSet,
    Vinhson_HocViewSet,
    MucnuocQuytrinhViewSet,
    ThongsoSanxuatViewSet,
    ThongsoGioPhatViewSet,
    ThongSoThuyVanThucTeViewSet,
    DeletePlantDataByDateAPIView,
    DashboardSummaryAPIView,
    GioPhatSummaryAPIView,
    GioPhatYearSummaryAPIView,
    HydrologyPlantsAPIView,
    HydrologySettingsAPIView,
    ManualHydrologyDataAPIView,
    RealtimeManualSaveAPIView,
    RealtimeUpdateStateAPIView,
    SongHinhRealtimeAPIView,
    SongHinhRealtimeSnapshotViewSet,
    VinhSonRealtimeAPIView,
    ThuongKonTumLatestDailyHydrologyAPIView,
    VinhSonRealtimeSnapshotViewSet,
)
from .sync_views import (
    PreviewGioPhatAPIView,
    PreviewGoogleSheetAPIView,
    PreviewThuyVanThucTeAPIView,
    SaveGioPhatAPIView,
    SaveGoogleSheetDataAPIView,
    SaveThuyVanThucTeAPIView,
)
from .vrain_views import (
    SyncVrainRainfallAPIView,
    VrainRealtimeAPIView,
    VrainSince19APIView,
)

app_name = "thongsothuyvan"
from .rain_forecast_views import RainForecastAPIView

router = DefaultRouter()
router.register(r"song-hinh-mnh", SonghinhMnhViewSet, basename="songhinh-mnh")
router.register(r"thuong-kon-tum-mnh", ThuongKonTumMnhViewSet, basename="thuongkontum-mnh")
router.register(r"vinhson-ho-a", Vinhson_HoAViewSet, basename="vinhson-hoa")
router.register(r"vinhson-ho-b", Vinhson_HoBViewSet, basename="vinhson-hob")
router.register(r"vinhson-ho-c", Vinhson_HocViewSet, basename="vinhson-hoc")
router.register(r"thongsosanxuat", ThongsoSanxuatViewSet, basename="thongsosanxuat")
router.register(r"mucnuoc-quytrinh", MucnuocQuytrinhViewSet, basename="mucnuoc-quytrinh")
router.register(r"thongsogiophat", ThongsoGioPhatViewSet, basename="thongsogiophat")
router.register(r"thongso-thucte", ThongSoThuyVanThucTeViewSet, basename="thongso-thucte")
router.register(r"realtime-songhinh-snapshots", SongHinhRealtimeSnapshotViewSet, basename="realtime-songhinh-snapshots")
router.register(r"realtime-vinhson-snapshots", VinhSonRealtimeSnapshotViewSet, basename="realtime-vinhson-snapshots")

urlpatterns = [
    path("vrain-source-samples/", VrainSourceSamplesAPIView.as_view(), name="vrain-source-samples"),
    path("vrain-intervals/", VrainHistoryAPIView.as_view(), name="vrain-intervals"),
    path("vrain-summary/", VrainSummaryAPIView.as_view(), name="vrain-summary"),
    path("vrain-sync-status/", VrainSyncStatusAPIView.as_view(), name="vrain-sync-status"),
    path("rain-forecast/", RainForecastAPIView.as_view(), name="rain-forecast"),
    path("", include(router.urls)),
    path("dashboard-summary/", DashboardSummaryAPIView.as_view(), name="dashboard-summary"),
    path("gio-phat-summary/", GioPhatSummaryAPIView.as_view(), name="gio-phat-summary"),
    path("gio-phat-year-summary/", GioPhatYearSummaryAPIView.as_view(), name="gio-phat-year-summary"),
    path("plants/", HydrologyPlantsAPIView.as_view(), name="plants"),
    path("settings/", HydrologySettingsAPIView.as_view(), name="settings"),
    path("realtime/songhinh/", SongHinhRealtimeAPIView.as_view(), name="realtime-songhinh"),
    path("realtime/vinhson/", VinhSonRealtimeAPIView.as_view(), name="realtime-vinhson"),
    path("latest-daily-hydrology/thuongkontum/", ThuongKonTumLatestDailyHydrologyAPIView.as_view(), name="latest-daily-hydrology-thuongkontum"),
    path("realtime/state/", RealtimeUpdateStateAPIView.as_view(), name="realtime-state"),
    path("realtime/manual-save/", RealtimeManualSaveAPIView.as_view(), name="realtime-manual-save"),
    path("sync/preview/", PreviewGoogleSheetAPIView.as_view(), name="sync-preview"),
    path("sync/save/", SaveGoogleSheetDataAPIView.as_view(), name="sync-save"),
    path("sync/delete-date/", DeletePlantDataByDateAPIView.as_view(), name="sync-delete-date"),
    path("manual-entry/", ManualHydrologyDataAPIView.as_view(), name="manual-entry"),
    path("sync-giophat/preview/", PreviewGioPhatAPIView.as_view(), name="sync-giophat-preview"),
    path("sync-giophat/save/", SaveGioPhatAPIView.as_view(), name="sync-giophat-save"),
    path("sync-thucte/preview/", PreviewThuyVanThucTeAPIView.as_view(), name="sync-thucte-preview"),
    path("sync-thucte/save/", SaveThuyVanThucTeAPIView.as_view(), name="sync-thucte-save"),
    path("sync-vrain/", SyncVrainRainfallAPIView.as_view(), name="sync-vrain"),
    path("vrain-realtime/", VrainRealtimeAPIView.as_view(), name="vrain-realtime"),
    path("vrain-since-19/", VrainSince19APIView.as_view(), name="vrain-since-19"),
]
