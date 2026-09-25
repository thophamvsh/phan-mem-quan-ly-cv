from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    NhatKySuKienViewSet,
    KhuVucChuyenDoiThietBiViewSet,
    MauChuyenDoiThietBiViewSet,
    MauChuyenDoiTBThangViewSet,
    SoBCHCSongHinhViewSet,
    SoChuyenDoiTBThangViewSet,
    SoChuyenDoiThietBiTuanViewSet,
    SonhatkyvanhanhDieselViewSet,
    SonhatkyvanhanhViewSet,
    SogiaonhancaHCViewSet,
    SogiaonhancaVHViewSet,
    SoAnToanViewSet,
    BangPhanCongNhiemVuHCViewSet,
    MauTrangThaiThietBiCaViewSet,
    MauTomLuocGiaoCaVHViewSet,
    MauNoiDungVanHanhViewSet,
    MonthlySwitchQuickEntryViewSet,
    WeeklySwitchQuickEntryViewSet,
)

app_name = "nhatkyvanhanh"

router = DefaultRouter()
router.register(r"nhat-ky-su-kien", NhatKySuKienViewSet, basename="nhatkysukien")
router.register(r"so-nhat-ky-van-hanh", SonhatkyvanhanhViewSet, basename="sonhatkyvanhanh")
router.register(r"so-nhat-ky-van-hanh-diesel", SonhatkyvanhanhDieselViewSet, basename="sonhatkyvanhanhdiesel")
router.register(r"so-bchc-song-hinh", SoBCHCSongHinhViewSet, basename="sobchcsonghinh")
router.register(r"so-giao-nhan-ca-vh", SogiaonhancaVHViewSet, basename="sogiaonhancavh")
router.register(r"so-giao-nhan-ca-hc", SogiaonhancaHCViewSet, basename="sogiaonhancahc")
router.register(r"phan-cong-nhiem-vu-hc", BangPhanCongNhiemVuHCViewSet, basename="phancongnhiemvuhc")
router.register(r"so-an-toan-dau-gio", SoAnToanViewSet, basename="soantoadaugio")
router.register(r"mau-chuyen-doi-thiet-bi", MauChuyenDoiThietBiViewSet, basename="mauchuyendoithietbi")
router.register(r"khu-vuc-chuyen-doi-thiet-bi", KhuVucChuyenDoiThietBiViewSet, basename="khuvucchuyendoithietbi")
router.register(r"so-chuyen-doi-thiet-bi-tuan", SoChuyenDoiThietBiTuanViewSet, basename="sochuyendoithietbituan")
router.register(r"mau-chuyen-doi-tb-thang", MauChuyenDoiTBThangViewSet, basename="mauchuyendoitbthang")
router.register(r"so-chuyen-doi-tb-thang", SoChuyenDoiTBThangViewSet, basename="sochuyendoitbthang")
router.register(r"mau-trang-thai-thiet-bi", MauTrangThaiThietBiCaViewSet, basename="mautrangthaithietbi")
router.register(r"mau-tom-luoc-giao-ca-vh", MauTomLuocGiaoCaVHViewSet, basename="mautomluocgiaocavh")
router.register(r"mau-noi-dung-vh", MauNoiDungVanHanhViewSet, basename="maunoidungvh")
router.register(
    r"monthly-switch-quick-entry",
    MonthlySwitchQuickEntryViewSet,
    basename="monthly-switch-quick-entry",
)
router.register(
    r"weekly-switch-quick-entry",
    WeeklySwitchQuickEntryViewSet,
    basename="weekly-switch-quick-entry",
)

urlpatterns = [
    path("", include(router.urls)),
]
