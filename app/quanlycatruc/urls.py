from rest_framework.routers import DefaultRouter

from .views import BoPhanViewSet, ChiTietPhuongAnPhanCongCaViewSet, DieuChinhNhanSuCaTrucViewSet, DonViToChucViewSet, KipTrucViewSet, LichTrucCaViewSet, MauChuKyCaTrucViewSet, NgayTrucCaViewSet, NhanSuViewSet, NhomLichTrucViewSet, PhamViNhanSuCaTrucViewSet, PhuongAnPhanCongCaViewSet, ThanhVienKipTrucViewSet

router = DefaultRouter()
router.register("don-vi", DonViToChucViewSet, basename="don-vi")
router.register("bo-phan", BoPhanViewSet, basename="bo-phan")
router.register("nhan-su", NhanSuViewSet, basename="nhan-su")
router.register("nhom-lich", NhomLichTrucViewSet, basename="nhom-lich")
router.register("pham-vi-nhan-su", PhamViNhanSuCaTrucViewSet, basename="pham-vi-nhan-su")
router.register("kip-truc", KipTrucViewSet, basename="kip-truc")
router.register("thanh-vien-kip", ThanhVienKipTrucViewSet, basename="thanh-vien-kip")
router.register("phuong-an-phan-cong", PhuongAnPhanCongCaViewSet, basename="phuong-an-phan-cong")
router.register("chi-tiet-phan-cong", ChiTietPhuongAnPhanCongCaViewSet, basename="chi-tiet-phan-cong")
router.register("mau-chu-ky", MauChuKyCaTrucViewSet, basename="mau-chu-ky")
router.register("lich-truc", LichTrucCaViewSet, basename="lich-truc")
router.register("ngay-truc", NgayTrucCaViewSet, basename="ngay-truc")
router.register("dieu-chinh-nhan-su", DieuChinhNhanSuCaTrucViewSet, basename="dieu-chinh-nhan-su")

urlpatterns = router.urls
