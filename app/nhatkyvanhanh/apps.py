from django.apps import AppConfig


class NhatkyvanhanhConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "nhatkyvanhanh"
    verbose_name = "Nhật ký vận hành"

    def ready(self):
        import nhatkyvanhanh.signals

        from auditlog.registry import auditlog
        from .models import (
            SuKien, ChiDaoSuKien, DienBienSuKien, KhacPhucSuKien,
            SogiaonhancaVH, ChiTietSoGiaoNhanCaVH, LuuYChiDaoSoGiaoNhanCaVH,
            SogiaonhancaHC, NguoiTrucSoGiaoNhanCaHC, ChiTietSoGiaoNhanCaHC,
            Sonhatkyvanhanh, SonhatkyvanhanhDiesel,
            SoBCHCSongHinh, SoAnToanDauGio,
            MauChuyenDoiThietBi, SoChuyenDoiThietBiTuan, LanChuyenDoiThietBi, ChiTietChuyenDoiThietBi,
            MauChuyenDoiTBThang, SoChuyenDoiTBThang, ChiTietChuyenDoiTBThang
        )

        auditlog.register(SuKien)
        auditlog.register(ChiDaoSuKien)
        auditlog.register(DienBienSuKien)
        auditlog.register(KhacPhucSuKien)
        auditlog.register(SogiaonhancaVH)
        auditlog.register(ChiTietSoGiaoNhanCaVH)
        auditlog.register(LuuYChiDaoSoGiaoNhanCaVH)
        auditlog.register(SogiaonhancaHC)
        auditlog.register(NguoiTrucSoGiaoNhanCaHC)
        auditlog.register(ChiTietSoGiaoNhanCaHC)
        auditlog.register(Sonhatkyvanhanh)
        auditlog.register(SonhatkyvanhanhDiesel)
        auditlog.register(SoBCHCSongHinh)
        auditlog.register(SoAnToanDauGio)
        auditlog.register(MauChuyenDoiThietBi)
        auditlog.register(SoChuyenDoiThietBiTuan)
        auditlog.register(LanChuyenDoiThietBi)
        auditlog.register(ChiTietChuyenDoiThietBi)
        auditlog.register(MauChuyenDoiTBThang)
        auditlog.register(SoChuyenDoiTBThang)
        auditlog.register(ChiTietChuyenDoiTBThang)

