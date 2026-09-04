from .base import TimestampedUUIDModel, _current_year
from .sukien import (
    SuKien,
    ChiDaoSuKien,
    DienBienSuKien,
    KhacPhucSuKien,
    AnhTruocSuCo,
    AnhSauXuLy,
)
from .giao_ca_vh import (
    SogiaonhancaVH,
    ChiTietSoGiaoNhanCaVH,
    NhanSuSoGiaoNhanCaVH,
    LuuYChiDaoSoGiaoNhanCaVH,
    AnhSoGiaoNhanCaVH,
)
from .giao_ca_hc import SogiaonhancaHC, NguoiTrucSoGiaoNhanCaHC, ChiTietSoGiaoNhanCaHC
from .nhat_ky_vh import Sonhatkyvanhanh, SonhatkyvanhanhDiesel
from .bchc_sh import SoBCHCSongHinh
from .an_toan_dg import SoAnToanDauGio
from .chuyen_doi_tuan import MauChuyenDoiThietBi, SoChuyenDoiThietBiTuan, LanChuyenDoiThietBi, ChiTietChuyenDoiThietBi
from .chuyen_doi_thang import MauChuyenDoiTBThang, SoChuyenDoiTBThang, ChiTietChuyenDoiTBThang
from .phan_cong_nhiem_vu_hc import BangPhanCongNhiemVuHC, ChiTietNhiemVuThuTrongTuan
from .device_template import (
    MauTrangThaiThietBiCa,
    NhomMauTrangThaiThietBiCa,
    ChiTietMauTrangThaiThietBiCa,
)
from .summary_template import MauTomLuocGiaoCaVH, HangMucMauTomLuocGiaoCaVH
