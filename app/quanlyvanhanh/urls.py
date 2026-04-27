from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, views_excel, views_test, views_optimized, views_export, views_h1, views_h2

app_name = 'quanlyvanhanh'

# Tạo router cho REST API
router = DefaultRouter()
router.register(r'thiet-bi', views.ThietBiViewSet, basename='thietbi')
router.register(r'vat-tu', views.VatTuViewSet, basename='vattu')
router.register(r'thiet-bi-vat-tu', views.ThietBiVatTuViewSet, basename='thietbivattu')
router.register(r'thong-so-van-hanh', views.ThongSoVanHanhViewSet, basename='thongsovanhanh')
router.register(r'thong-so-to-may', views.ThongSoToMayViewSet, basename='thongsotomay')
router.register(r'an-toan-thiet-bi', views.AnToanThietBiViewSet, basename='antoanthietbi')
router.register(r'dinh-kem', views.DinhKemViewSet, basename='dinhkem')

urlpatterns = [
    # Excel import endpoints (phải đặt trước router để tránh conflict)
    path('thong-so-van-hanh/excel_template/', views_excel.excel_template, name='excel_template'),
    path('thong-so-van-hanh/excel_import/', views_excel.excel_import, name='excel_import'),
    # Thông số tổ máy H1 endpoints
    path('thong-so-to-may/excel_template/', views_h1.excel_template_h1, name='excel_template_tomay'),
    path('thong-so-to-may/excel_import/', views_h1.import_excel_h1, name='excel_import_tomay'),
    # Thông số tổ máy H2 endpoints
    path('thong-so-to-may-h2/excel_template/', views_h2.excel_template_h2, name='excel_template_tomay_h2'),
    path('thong-so-to-may-h2/excel_import/', views_h2.import_excel_h2, name='excel_import_tomay_h2'),
    # Test endpoint
    path('test-export/', views_export.test_export, name='test_export'),
    # Export endpoints
    path('export-thong-so/', views_export.export_thong_so, name='export_thong_so'),
    path('thong-so-to-may-h1/export/', views_export.export_thong_so_to_may_h1, name='export_thong_so_to_may_h1'),
    path('thong-so-to-may-h2/export/', views_export.export_thong_so_to_may_h2, name='export_thong_so_to_may_h2'),
    # Optimized API endpoints
    path('thong-so-van-hanh/by_day/', views_optimized.ThongSoByDayView.as_view(), name='thong-so-by-day'),
    path('thong-so-to-may/by_day/', views_optimized.ThongSoToMayByDayView.as_view(), name='thong-so-to-may-by-day'),
    # Test endpoints
    path('test/', views_test.test_endpoint, name='test'),
    path('test-excel/', views_test.test_excel, name='test_excel'),
    # Router URLs (đặt cuối cùng)
    path('', include(router.urls)),
]

