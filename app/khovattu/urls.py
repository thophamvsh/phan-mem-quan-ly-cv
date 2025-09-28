# apps/kho/urls.py
from django.urls import path
from .auth_views import (
    CustomTokenObtainPairView,
    get_user_profile,
    update_user_profile,
    change_password,
    get_nha_may_list,
    logout_user,
    upload_avatar,
)
from .views_upload import UploadMaterialImageView
from .views import (
    # ===== Import Excel
    ImportVatTuAPIView, ImportKiemKeAPIView, ImportDeNghiNhapAPIView, ImportDeNghiXuatAPIView, ImportViTriAPIView,

    # ===== Templates
    DownloadVatTuTemplateAPIView,

    # ===== Kiểm kê
    KiemKeListAPIView, DownloadKiemKeTemplateAPIView, ExportKiemKeAPIView, KiemKeStatsAPIView, UpdateSoLuongThucTeAPIView,

    # ===== Vị trí
    ViTriListAPIView, ViTriDetailAPIView, HeThongListAPIView,

    # ===== Xuất xứ
    XuatXuListAPIView,

    # ===== Bravo Parser
    BravoPositionAnalyzeAPIView,

    # ===== Vật tư
    VatTuListAPIView,            # GET (list), POST (tạo/cập nhật theo (ma_nha_may, ma_bravo))
    VatTuDetailByIdAPIView,      # GET theo id
    VatTuDetailByBravoAPIView,   # GET/PATCH/DELETE theo (ma_nha_may, ma_bravo)
    VatTuByQRAPIView,            # GET theo ma_bravo từ QR code
    VatTuOverviewAPIView,        # GET tổng hợp lịch sử
    # VatTuImageAPIView removed - using UploadMaterialImageView instead

    # ===== Đề nghị nhập
    DeNghiNhapListAPIView,           # GET list toàn bộ đề nghị nhập với filter
    DeNghiNhapByBravoPlantAPIView,   # GET (list theo vật tư), POST (tạo) theo (ma_nha_may, ma_bravo)
    DeNghiNhapDetailAPIView,         # PATCH/DELETE theo id (nếu muốn, bạn có thể thêm GET trong view)

    # ===== Đề nghị xuất
    DeNghiXuatListAPIView,           # GET list toàn bộ đề nghị xuất với filter
    DeNghiXuatByBravoPlantAPIView,   # GET (list theo vật tư), POST (tạo) theo (ma_nha_may, ma_bravo)
    DeNghiXuatDetailAPIView,         # PATCH/DELETE theo id (nếu muốn, bạn có thể thêm GET trong view)

    # ===== Action nhanh (tuỳ chọn, có thể bỏ vì đã có POST ở các endpoint theo vật tư)
    TaoDeNghiNhapAPIView, TaoDeNghiXuatAPIView,

    # ===== Cập nhật hình ảnh vật tư (removed - using UploadMaterialImageView instead)

    # ===== Kiểm kê theo vật tư
    KiemKeByMaterialAPIView,

    # ===== Hệ thống
    SystemCategoriesAPIView,
)

urlpatterns = [
    # ---------- Import Excel ----------
    path("import/vat-tu/", ImportVatTuAPIView.as_view()),
    path("import/kiem-ke/", ImportKiemKeAPIView.as_view()),
    path("import/de-nghi-nhap/", ImportDeNghiNhapAPIView.as_view()),
    path("import/de-nghi-xuat/", ImportDeNghiXuatAPIView.as_view()),
    path("import/vi-tri/", ImportViTriAPIView.as_view()),

    # ---------- Templates ----------
    path("template/vat-tu/", DownloadVatTuTemplateAPIView.as_view()),

    # ---------- Kiểm kê ----------
    path("kiem-ke/", KiemKeListAPIView.as_view()),
    path("kiem-ke/template/", DownloadKiemKeTemplateAPIView.as_view()),
    path("kiem-ke/export/", ExportKiemKeAPIView.as_view()),
    path("kiem-ke/stats/", KiemKeStatsAPIView.as_view()),
    path("kiem-ke/<int:id>/update-so-luong-thuc-te/", UpdateSoLuongThucTeAPIView.as_view()),
    path("kiem-ke/material/<str:ma_nha_may>/<str:ma_bravo>/", KiemKeByMaterialAPIView.as_view()),

    # ---------- Vị trí ----------
    path("vi-tri/", ViTriListAPIView.as_view()),
    path("vi-tri/<str:ma_vi_tri>/", ViTriDetailAPIView.as_view()),
    path("he-thong/", HeThongListAPIView.as_view()),

    # ---------- Xuất xứ ----------
    path("xuat-xu/", XuatXuListAPIView.as_view()),
    path("system-categories/", SystemCategoriesAPIView.as_view()),

    # ---------- Bravo Parser ----------
    path("bravo/analyze/", BravoPositionAnalyzeAPIView.as_view()),

    # ---------- Vật tư ----------
    # List + tạo/cập nhật (POST body chứa ma_nha_may, ma_bravo, ...)
    path("vat-tu/", VatTuListAPIView.as_view()),
    # Xem chi tiết theo id
    path("vat-tu/id/<int:pk>/", VatTuDetailByIdAPIView.as_view()),
    # Xem chi tiết từ QR code (cần cả ma_nha_may và ma_bravo để tránh nhầm lẫn)
    path("vat-tu/qr/<str:ma_nha_may>/<str:ma_bravo>/", VatTuByQRAPIView.as_view()),
    # Xem/sửa/xoá theo (nhà máy + mã bravo)
    path("vat-tu/<str:ma_nha_may>/<str:ma_bravo>/", VatTuDetailByBravoAPIView.as_view()),
    path("vat-tu/<str:ma_nha_may>/<str:ma_bravo>/overview/", VatTuOverviewAPIView.as_view()),

    # ---------- Đề nghị NHẬP ----------
    # GET list toàn bộ đề nghị nhập với filter
    path("de-nghi-nhap/", DeNghiNhapListAPIView.as_view()),
    # GET list theo vật tư (cùng nhà máy) + POST tạo phiếu nhập cho vật tư đó
    path("de-nghi-nhap/<str:ma_nha_may>/<str:ma_bravo>/", DeNghiNhapByBravoPlantAPIView.as_view()),
    # PATCH/DELETE phiếu nhập theo id
    path("de-nghi-nhap/<int:pk>/", DeNghiNhapDetailAPIView.as_view()),

    # ---------- Đề nghị XUẤT ----------
    # GET list toàn bộ đề nghị xuất với filter
    path("de-nghi-xuat/", DeNghiXuatListAPIView.as_view()),
    # GET list theo vật tư (cùng nhà máy) + POST tạo phiếu xuất cho vật tư đó
    path("de-nghi-xuat/<str:ma_nha_may>/<str:ma_bravo>/", DeNghiXuatByBravoPlantAPIView.as_view()),
    # PATCH/DELETE phiếu xuất theo id
    path("de-nghi-xuat/<int:pk>/", DeNghiXuatDetailAPIView.as_view()),

    # ---------- Action nhanh (tuỳ chọn) ----------
    path("de-nghi-nhap/create/", TaoDeNghiNhapAPIView.as_view()),
    path("de-nghi-xuat/create/", TaoDeNghiXuatAPIView.as_view()),

    # ---------- Cập nhật hình ảnh vật tư (removed - using UploadMaterialImageView instead) ----------

    # ---------- Authentication ----------
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    # path("auth/register/", register_user, name="register_user"),  # Removed - registration only through Django admin
    path("auth/profile/", get_user_profile, name="get_user_profile"),
    path("auth/profile/update/", update_user_profile, name="update_user_profile"),
    path("auth/change-password/", change_password, name="change_password"),
    path("auth/upload-avatar/", upload_avatar, name="upload_avatar"),
    path("auth/nha-may/", get_nha_may_list, name="get_nha_may_list"),
    path("auth/logout/", logout_user, name="logout_user"),

    # ===== Upload Material Image =====
    path("vat-tu/<str:ma_nha_may>/<str:ma_bravo>/update-image/", UploadMaterialImageView.as_view(), name="upload_material_image"),

    # ===== Multiple Images Management =====
    # Removed - using UploadMaterialImageView instead for consistency with VshMobile

]
