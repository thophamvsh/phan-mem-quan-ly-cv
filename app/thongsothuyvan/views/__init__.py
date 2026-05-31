from .views_mnh import (
    SonghinhMnhViewSet,
    ThuongKonTumMnhViewSet,
    Vinhson_HoAViewSet,
    Vinhson_HoBViewSet,
    Vinhson_HocViewSet,
)
from .views_sanxuat import (
    ThongsoSanxuatViewSet,
    ThongsoGioPhatViewSet,
    DashboardSummaryAPIView,
    GioPhatSummaryAPIView,
    GioPhatYearSummaryAPIView,
    DeletePlantDataByDateAPIView,
    ManualHydrologyDataAPIView,
)
from .views_settings import (
    HydrologyPlantsAPIView,
    HydrologySettingsAPIView,
)
from .views_realtime import (
    SongHinhRealtimeAPIView,
    VinhSonRealtimeAPIView,
    RealtimeUpdateStateAPIView,
    RealtimeManualSaveAPIView,
    SongHinhRealtimeSnapshotViewSet,
    VinhSonRealtimeSnapshotViewSet,
)
from .views_quytrinh import (
    MucnuocQuytrinhViewSet,
)
