from .sukien import (
    DienBienSuKienSerializer,
    KhacPhucSuKienSerializer,
    ChiDaoSuKienSerializer,
    NhatKySuKienSerializer,
)
from .mixins import (
    user_can_edit_chi_dao,
)
from .giao_ca_vh import (
    ChiTietSoGiaoNhanCaVHSerializer,
    NhanSuSoGiaoNhanCaVHSerializer,
    LuuYChiDaoSoGiaoNhanCaVHSerializer,
    AnhSoGiaoNhanCaVHSerializer,
    SogiaonhancaVHSerializer,
)
from .giao_ca_hc import (
    ChiTietSoGiaoNhanCaHCSerializer,
    NguoiTrucSoGiaoNhanCaHCSerializer,
    SogiaonhancaHCSerializer,
)
from .nhat_ky_vh import (
    SonhatkyvanhanhSerializer,
    SonhatkyvanhanhDieselSerializer,
)
from .bchc_sh import (
    SoBCHCSongHinhSerializer,
)
from .an_toan_dg import (
    SoAnToanSerializer,
)
from .chuyen_doi_tuan import (
    KhuVucChuyenDoiThietBiSerializer,
    MauChuyenDoiThietBiSerializer,
    ChiTietChuyenDoiThietBiSerializer,
    LanChuyenDoiThietBiSerializer,
    SoChuyenDoiThietBiTuanSerializer,
)
from .chuyen_doi_thang import (
    MauChuyenDoiTBThangSerializer,
    ChiTietChuyenDoiTBThangSerializer,
    SoChuyenDoiTBThangSerializer,
)
from .phan_cong_nhiem_vu_hc import (
    BangPhanCongNhiemVuHCSerializer,
    ChiTietNhiemVuThuTrongTuanSerializer,
)
from .device_template import MauTrangThaiThietBiCaSerializer
from .summary_template import MauTomLuocGiaoCaVHSerializer
from .command_template import MauNoiDungVanHanhSerializer

__all__ = [
    "user_can_edit_chi_dao",
    "DienBienSuKienSerializer",
    "KhacPhucSuKienSerializer",
    "ChiDaoSuKienSerializer",
    "NhatKySuKienSerializer",
    "ChiTietSoGiaoNhanCaVHSerializer",
    "NhanSuSoGiaoNhanCaVHSerializer",
    "LuuYChiDaoSoGiaoNhanCaVHSerializer",
    "AnhSoGiaoNhanCaVHSerializer",
    "SogiaonhancaVHSerializer",
    "ChiTietSoGiaoNhanCaHCSerializer",
    "NguoiTrucSoGiaoNhanCaHCSerializer",
    "SogiaonhancaHCSerializer",
    "SonhatkyvanhanhSerializer",
    "SonhatkyvanhanhDieselSerializer",
    "SoBCHCSongHinhSerializer",
    "SoAnToanSerializer",
    "MauChuyenDoiThietBiSerializer",
    "KhuVucChuyenDoiThietBiSerializer",
    "ChiTietChuyenDoiThietBiSerializer",
    "LanChuyenDoiThietBiSerializer",
    "SoChuyenDoiThietBiTuanSerializer",
    "MauChuyenDoiTBThangSerializer",
    "ChiTietChuyenDoiTBThangSerializer",
    "SoChuyenDoiTBThangSerializer",
    "BangPhanCongNhiemVuHCSerializer",
    "ChiTietNhiemVuThuTrongTuanSerializer",
    "MauTrangThaiThietBiCaSerializer",
    "MauTomLuocGiaoCaVHSerializer",
    "MauNoiDungVanHanhSerializer",
]
