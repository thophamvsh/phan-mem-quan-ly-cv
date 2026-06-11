from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import (
    views_excel,
    views_export,
    views_history,
    views_thietbi,
    views_thietbi_meta,
    views_thongso_dien,
    views_optimized,
    views_thongso_tomay,
    views_tomay_excel,
    views_tram,
    views_vattu,
    views_nguongthongso,
)

app_name = 'quanlyvanhanh'

# Tạo router cho REST API
router = DefaultRouter()
router.register(r'thiet-bi', views_thietbi.ThietBiViewSet, basename='thietbi')
router.register(r'vat-tu', views_vattu.VatTuViewSet, basename='vattu')
router.register(r'thiet-bi-vat-tu', views_vattu.ThietBiVatTuViewSet, basename='thietbivattu')
router.register(r'thong-so-van-hanh', views_thongso_dien.ThongSoVanHanhViewSet, basename='thongsovanhanh')
router.register(r'thong-so-to-may', views_thongso_tomay.ThongSoToMayViewSet, basename='thongsotomay')
router.register(r'thong-so-tram-110kv', views_tram.ThongSoTram110KVViewSet, basename='thongsotram110kv')
router.register(r'an-toan-thiet-bi', views_thietbi_meta.AnToanThietBiViewSet, basename='antoanthietbi')
router.register(r'dinh-kem', views_thietbi_meta.DinhKemViewSet, basename='dinhkem')
router.register(r'nguong-thong-so', views_nguongthongso.NguongThongSoViewSet, basename='nguongthongso')

urlpatterns = [
    # Excel import endpoints (phải đặt trước router để tránh conflict)
    path('thong-so-van-hanh/excel_template/', views_excel.excel_template, name='excel_template'),
    path('thong-so-van-hanh/excel_import/', views_excel.excel_import, name='excel_import'),
    # Thông số tổ máy H1 endpoints
    path('thong-so-to-may/excel_template/', views_tomay_excel.excel_template_h1, name='excel_template_tomay'),
    path('thong-so-to-may/excel_import/', views_tomay_excel.import_excel_h1, name='excel_import_tomay'),
    # Thông số tổ máy H2 endpoints
    path('thong-so-to-may-h2/excel_template/', views_tomay_excel.excel_template_h2, name='excel_template_tomay_h2'),
    path('thong-so-to-may-h2/excel_import/', views_tomay_excel.import_excel_h2, name='excel_import_tomay_h2'),
    # Thông số trạm 110kV endpoints
    path('thong-so-tram-110kv/excel_template/', views_tram.excel_template_tram, name='excel_template_tram'),
    path('thong-so-tram-110kv/excel_import/', views_tram.excel_import_tram, name='excel_import_tram'),
    path('thong-so-tram-110kv/export/', views_tram.export_thong_so_tram_110kv, name='export_thong_so_tram_110kv'),
    # Export endpoints
    path('export-thong-so/', views_export.export_thong_so, name='export_thong_so'),
    path('thong-so-to-may-h1/export/', views_export.export_thong_so_to_may_h1, name='export_thong_so_to_may_h1'),
    path('thong-so-to-may-h2/export/', views_export.export_thong_so_to_may_h2, name='export_thong_so_to_may_h2'),
    # Optimized API endpoints
    path('thong-so-van-hanh/by_day/', views_optimized.ThongSoByDayView.as_view(), name='thong-so-by-day'),
    path('thong-so-to-may/by_day/', views_optimized.ThongSoToMayByDayView.as_view(), name='thong-so-to-may-by-day'),
    path('thong-so-lich-su/', views_history.ThongSoLichSuView.as_view(), name='thong-so-lich-su'),
    path('thong-so/active-alerts/', views_optimized.ThongSoActiveAlertsView.as_view(), name='thong-so-active-alerts'),
    # Router URLs (đặt cuối cùng)
    path('', include(router.urls)),
]
