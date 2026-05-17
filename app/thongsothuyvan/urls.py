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
    DeletePlantDataByDateAPIView,
    DashboardSummaryAPIView,
    HydrologyPlantsAPIView,
    ManualHydrologyDataAPIView,
    RealtimeManualSaveAPIView,
    RealtimeUpdateStateAPIView,
    SongHinhRealtimeAPIView,
    SongHinhRealtimeSnapshotViewSet,
    VinhSonRealtimeAPIView,
    VinhSonRealtimeSnapshotViewSet,
)
from .sync_views import PreviewGoogleSheetAPIView, SaveGoogleSheetDataAPIView, PreviewGioPhatAPIView, SaveGioPhatAPIView
from .vrain_views import SyncVrainRainfallAPIView, VrainRealtimeAPIView

app_name = "thongsothuyvan"

router = DefaultRouter()
router.register(r"song-hinh-mnh", SonghinhMnhViewSet, basename="songhinh-mnh")
router.register(r"thuong-kon-tum-mnh", ThuongKonTumMnhViewSet, basename="thuongkontum-mnh")
router.register(r"vinhson-ho-a", Vinhson_HoAViewSet, basename="vinhson-hoa")
router.register(r"vinhson-ho-b", Vinhson_HoBViewSet, basename="vinhson-hob")
router.register(r"vinhson-ho-c", Vinhson_HocViewSet, basename="vinhson-hoc")
router.register(r"thongsosanxuat", ThongsoSanxuatViewSet, basename="thongsosanxuat")
router.register(r"mucnuoc-quytrinh", MucnuocQuytrinhViewSet, basename="mucnuoc-quytrinh")
router.register(r"thongsogiophat", ThongsoGioPhatViewSet, basename="thongsogiophat")
router.register(r"realtime-songhinh-snapshots", SongHinhRealtimeSnapshotViewSet, basename="realtime-songhinh-snapshots")
router.register(r"realtime-vinhson-snapshots", VinhSonRealtimeSnapshotViewSet, basename="realtime-vinhson-snapshots")

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard-summary/", DashboardSummaryAPIView.as_view(), name="dashboard-summary"),
    path("plants/", HydrologyPlantsAPIView.as_view(), name="plants"),
    path("realtime/songhinh/", SongHinhRealtimeAPIView.as_view(), name="realtime-songhinh"),
    path("realtime/vinhson/", VinhSonRealtimeAPIView.as_view(), name="realtime-vinhson"),
    path("realtime/state/", RealtimeUpdateStateAPIView.as_view(), name="realtime-state"),
    path("realtime/manual-save/", RealtimeManualSaveAPIView.as_view(), name="realtime-manual-save"),
    path("sync/preview/", PreviewGoogleSheetAPIView.as_view(), name="sync-preview"),
    path("sync/save/", SaveGoogleSheetDataAPIView.as_view(), name="sync-save"),
    path("sync/delete-date/", DeletePlantDataByDateAPIView.as_view(), name="sync-delete-date"),
    path("manual-entry/", ManualHydrologyDataAPIView.as_view(), name="manual-entry"),
    path("sync-giophat/preview/", PreviewGioPhatAPIView.as_view(), name="sync-giophat-preview"),
    path("sync-giophat/save/", SaveGioPhatAPIView.as_view(), name="sync-giophat-save"),
    path("sync-vrain/", SyncVrainRainfallAPIView.as_view(), name="sync-vrain"),
    path("vrain-realtime/", VrainRealtimeAPIView.as_view(), name="vrain-realtime"),
]
