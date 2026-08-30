from datetime import date
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class DonViToChuc(TimeStampedModel):
    class LoaiDonVi(models.TextChoices):
        CONG_TY = "cong_ty", "Công ty"
        CUM_NHA_MAY = "cum_nha_may", "Cụm nhà máy"
        NHA_MAY = "nha_may", "Nhà máy"
        VAN_PHONG = "van_phong", "Văn phòng"
        KHAC = "khac", "Khác"

    ma_don_vi = models.CharField(max_length=50, unique=True)
    ten_don_vi = models.CharField(max_length=200)
    loai_don_vi = models.CharField(max_length=20, choices=LoaiDonVi.choices, default=LoaiDonVi.NHA_MAY)
    don_vi_cha = models.ForeignKey("self", on_delete=models.PROTECT, related_name="don_vi_con", null=True, blank=True)
    nha_may = models.ForeignKey("tochuc.NhaMay", on_delete=models.PROTECT, related_name="don_vi_to_chuc", null=True, blank=True)
    thu_tu = models.PositiveSmallIntegerField(default=1)
    dang_hoat_dong = models.BooleanField(default=True)

    class Meta:
        ordering = ["thu_tu", "ten_don_vi"]
        verbose_name = "Đơn vị tổ chức"
        verbose_name_plural = "Các đơn vị tổ chức"

    def clean(self):
        if self.pk and self.don_vi_cha_id == self.pk:
            raise ValidationError({"don_vi_cha": "Đơn vị không thể là cấp trên của chính nó."})
        ancestor = self.don_vi_cha
        visited = set()
        while ancestor:
            if ancestor.pk == self.pk or ancestor.pk in visited:
                raise ValidationError({"don_vi_cha": "Cấu trúc đơn vị tạo thành vòng lặp."})
            visited.add(ancestor.pk)
            ancestor = ancestor.don_vi_cha

    @property
    def nha_may_pham_vi_id(self):
        current, visited = self, set()
        while current and current.pk not in visited:
            if current.nha_may_id:
                return current.nha_may_id
            visited.add(current.pk)
            current = current.don_vi_cha
        return None

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ma_don_vi} - {self.ten_don_vi}"


class BoPhan(TimeStampedModel):
    class LoaiBoPhan(models.TextChoices):
        VAN_HANH = "van_hanh", "Vận hành"
        KY_THUAT = "ky_thuat", "Kỹ thuật"
        HANH_CHINH = "hanh_chinh", "Hành chính"
        BAO_VE = "bao_ve", "Bảo vệ"
        BAO_TRI = "bao_tri", "Bảo trì"
        AN_TOAN = "an_toan", "An toàn"
        KHAC = "khac", "Khác"

    don_vi = models.ForeignKey(DonViToChuc, on_delete=models.PROTECT, related_name="bo_phan")
    ma_bo_phan = models.CharField(max_length=50)
    ten_bo_phan = models.CharField(max_length=150)
    loai_bo_phan = models.CharField(max_length=20, choices=LoaiBoPhan.choices, default=LoaiBoPhan.KHAC)
    thu_tu = models.PositiveSmallIntegerField(default=1)
    dang_hoat_dong = models.BooleanField(default=True)

    class Meta:
        ordering = ["don_vi", "thu_tu", "ten_bo_phan"]
        constraints = [models.UniqueConstraint(fields=["don_vi", "ma_bo_phan"], name="uq_bophan_donvi_ma")]
        verbose_name = "Bộ phận"
        verbose_name_plural = "Các bộ phận"

    def __str__(self):
        return f"{self.ten_bo_phan} - {self.don_vi.ten_don_vi}"


class NhanSu(TimeStampedModel):
    ma_nhan_vien = models.CharField(max_length=50, unique=True, null=True, blank=True)
    ho_ten = models.CharField(max_length=150)
    don_vi = models.ForeignKey(DonViToChuc, on_delete=models.PROTECT, related_name="nhan_su")
    bo_phan = models.ForeignKey(BoPhan, on_delete=models.PROTECT, related_name="nhan_su")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="nhan_su_ca_truc", null=True, blank=True)
    chuc_danh = models.CharField(max_length=120, blank=True)
    dien_thoai = models.CharField(max_length=30, blank=True)
    tu_ngay = models.DateField(default=date.today)
    den_ngay = models.DateField(null=True, blank=True)
    dang_lam_viec = models.BooleanField(default=True)

    class Meta:
        ordering = ["don_vi", "bo_phan", "ho_ten"]
        indexes = [models.Index(fields=["don_vi", "bo_phan", "dang_lam_viec"])]
        verbose_name = "Nhân sự"
        verbose_name_plural = "Danh mục nhân sự"

    def clean(self):
        errors = {}
        if self.bo_phan_id and self.don_vi_id and self.bo_phan.don_vi_id != self.don_vi_id:
            errors["bo_phan"] = "Bộ phận phải thuộc đơn vị đã chọn."
        if self.den_ngay and self.den_ngay < self.tu_ngay:
            errors["den_ngay"] = "Ngày kết thúc không được trước ngày bắt đầu."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.ma_nhan_vien = self.ma_nhan_vien or None
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.ho_ten


class NhomLichTruc(TimeStampedModel):
    nha_may = models.ForeignKey("tochuc.NhaMay", on_delete=models.PROTECT, related_name="nhom_lich_truc")
    don_vi = models.ForeignKey(DonViToChuc, on_delete=models.PROTECT, related_name="nhom_lich_truc")
    bo_phan = models.ForeignKey(BoPhan, on_delete=models.PROTECT, related_name="nhom_lich_truc")
    ma_nhom = models.CharField(max_length=50)
    ten_nhom = models.CharField(max_length=150)
    dia_diem = models.CharField(max_length=200, blank=True)
    thu_tu = models.PositiveSmallIntegerField(default=1)
    dang_hoat_dong = models.BooleanField(default=True)

    class Meta:
        ordering = ["nha_may", "thu_tu", "ten_nhom"]
        constraints = [models.UniqueConstraint(fields=["nha_may", "ma_nhom"], name="uq_nhomlich_nhamay_ma")]
        verbose_name = "Nhóm lịch trực"
        verbose_name_plural = "Các nhóm lịch trực"

    def clean(self):
        errors = {}
        if self.don_vi_id and self.don_vi.nha_may_pham_vi_id != self.nha_may_id:
            errors["don_vi"] = "Đơn vị phải thuộc nhà máy của nhóm lịch."
        if self.bo_phan_id and self.bo_phan.don_vi_id != self.don_vi_id:
            errors["bo_phan"] = "Bộ phận phải thuộc đơn vị đã chọn."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ten_nhom} - {self.nha_may.ma_nha_may}"


class PhamViNhanSuCaTruc(TimeStampedModel):
    nhom_lich = models.ForeignKey(NhomLichTruc, on_delete=models.CASCADE, related_name="pham_vi_nhan_su")
    nhan_su = models.ForeignKey(NhanSu, on_delete=models.CASCADE, related_name="pham_vi_ca_truc")
    tu_ngay = models.DateField(default=date.today)
    den_ngay = models.DateField(null=True, blank=True)
    dang_hoat_dong = models.BooleanField(default=True)

    class Meta:
        ordering = ["nhom_lich", "nhan_su__ho_ten"]
        constraints = [models.UniqueConstraint(fields=["nhom_lich", "nhan_su"], name="uq_phamvi_nhom_nhansu")]
        verbose_name = "Phạm vi nhân sự ca trực"
        verbose_name_plural = "Phạm vi nhân sự ca trực"

    def clean(self):
        if self.nhan_su_id and self.nhom_lich_id and self.nhan_su.don_vi.nha_may_pham_vi_id != self.nhom_lich.nha_may_id:
            raise ValidationError({"nhan_su": "Nhân sự phải thuộc cùng nhà máy với nhóm lịch."})
        if self.den_ngay and self.den_ngay < self.tu_ngay:
            raise ValidationError({"den_ngay": "Ngày kết thúc không hợp lệ."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class KipTruc(TimeStampedModel):
    class LoaiKip(models.TextChoices):
        VAN_HANH = "van_hanh", "Vận hành"
        HANH_CHINH = "hanh_chinh", "Kỹ thuật - hành chính"

    class MaKip(models.TextChoices):
        A = "A", "Kíp A"
        B = "B", "Kíp B"
        C = "C", "Kíp C"
        D = "D", "Kíp D"
        HC1 = "HC1", "Ca 1"
        HC2 = "HC2", "Ca 2"

    nha_may = models.ForeignKey("tochuc.NhaMay", on_delete=models.PROTECT, related_name="cac_kip_truc")
    nhom_lich = models.ForeignKey(NhomLichTruc, on_delete=models.PROTECT, related_name="kip_truc", null=True, blank=True)
    loai_kip = models.CharField(max_length=20, choices=LoaiKip.choices)
    ma_kip = models.CharField(max_length=20)
    ten_kip = models.CharField(max_length=80)
    mau_nhan_dien = models.CharField(max_length=20, default="#4f46e5")
    thu_tu = models.PositiveSmallIntegerField(default=1)
    dang_hoat_dong = models.BooleanField(default=True)

    class Meta:
        ordering = ["nha_may", "loai_kip", "thu_tu", "ma_kip"]
        constraints = [
            models.UniqueConstraint(fields=["nhom_lich", "ma_kip"], name="uq_catruc_nhomlich_makip"),
        ]
        verbose_name = "Kíp trực"
        verbose_name_plural = "Các kíp trực"

    def clean(self):
        if self.nhom_lich_id and self.nhom_lich.nha_may_id != self.nha_may_id:
            raise ValidationError({"nhom_lich": "Nhóm lịch phải thuộc cùng nhà máy với kíp."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ten_kip} - {self.nha_may.ma_nha_may}"


class ThanhVienKipTruc(TimeStampedModel):
    class VaiTro(models.TextChoices):
        TRUONG_CA = "truong_ca", "Trưởng ca"
        TRUC_CHINH = "truc_chinh", "Trực chính"
        TRUC_PHU = "truc_phu", "Trực phụ"
        KY_THUAT_VIEN = "ky_thuat_vien", "Kỹ thuật viên"
        NHAN_VIEN = "nhan_vien", "Nhân viên"

    kip_truc = models.ForeignKey(KipTruc, on_delete=models.CASCADE, related_name="thanh_vien")
    nhan_su = models.ForeignKey(NhanSu, on_delete=models.PROTECT, related_name="phan_cong_kip_truc", null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="phan_cong_kip_truc", null=True, blank=True)
    vai_tro = models.CharField(max_length=20, choices=VaiTro.choices, default=VaiTro.NHAN_VIEN)
    tu_ngay = models.DateField()
    den_ngay = models.DateField(null=True, blank=True)
    thu_tu_hien_thi = models.PositiveSmallIntegerField(default=1)
    dang_hoat_dong = models.BooleanField(default=True)

    class Meta:
        ordering = ["kip_truc", "thu_tu_hien_thi", "tu_ngay"]
        indexes = [
            models.Index(fields=["user", "tu_ngay", "den_ngay"]),
            models.Index(fields=["nhan_su", "tu_ngay", "den_ngay"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(nhan_su__isnull=False) | Q(user__isnull=False),
                name="ck_thanhvien_co_nhansu_hoac_user",
            )
        ]
        verbose_name = "Thành viên kíp trực"
        verbose_name_plural = "Thành viên kíp trực"

    def clean(self):
        if not self.nhan_su_id and not self.user_id:
            raise ValidationError({"nhan_su": "Phải chọn nhân sự."})
        if self.nhan_su_id:
            if self.user_id and self.nhan_su.user_id and self.user_id != self.nhan_su.user_id:
                raise ValidationError({"user": "Tài khoản không khớp với nhân sự đã chọn."})
            if self.kip_truc_id and self.nhan_su.don_vi.nha_may_pham_vi_id != self.kip_truc.nha_may_id:
                raise ValidationError({"nhan_su": "Nhân sự không thuộc phạm vi nhà máy của kíp."})
            if self.kip_truc_id and self.kip_truc.nhom_lich_id and not PhamViNhanSuCaTruc.objects.filter(
                nhom_lich_id=self.kip_truc.nhom_lich_id,
                nhan_su_id=self.nhan_su_id,
                dang_hoat_dong=True,
            ).exists():
                raise ValidationError({"nhan_su": "Nhân sự chưa thuộc phạm vi của nhóm lịch này."})
        if self.den_ngay and self.den_ngay < self.tu_ngay:
            raise ValidationError({"den_ngay": "Ngày kết thúc không được trước ngày bắt đầu."})
        identity = Q(nhan_su_id=self.nhan_su_id) if self.nhan_su_id else Q(user_id=self.user_id)
        overlaps = type(self).objects.filter(identity, tu_ngay__lte=self.den_ngay or date.max).filter(
            Q(den_ngay__isnull=True) | Q(den_ngay__gte=self.tu_ngay)
        )
        if self.kip_truc_id and self.kip_truc.nhom_lich_id:
            overlaps = overlaps.filter(kip_truc__nhom_lich=self.kip_truc.nhom_lich)
        if self.pk:
            overlaps = overlaps.exclude(pk=self.pk)
        if overlaps.exists():
            raise ValidationError("Nhân sự đã thuộc một kíp khác trong khoảng thời gian này.")

    def save(self, *args, **kwargs):
        if self.nhan_su_id and not self.user_id:
            self.user_id = self.nhan_su.user_id
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nhan_su or self.user} - {self.kip_truc.ten_kip}"


class PhuongAnPhanCongCa(TimeStampedModel):
    class TrangThai(models.TextChoices):
        DU_THAO = "du_thao", "Dự thảo"
        DA_AP_DUNG = "da_ap_dung", "Đã áp dụng"
        DA_KHOA = "da_khoa", "Đã khóa"

    nha_may = models.ForeignKey("tochuc.NhaMay", on_delete=models.PROTECT, related_name="phuong_an_phan_cong_ca")
    nhom_lich = models.ForeignKey(NhomLichTruc, on_delete=models.PROTECT, related_name="phuong_an_phan_cong", null=True, blank=True)
    lich_truc = models.ForeignKey("LichTrucCa", on_delete=models.SET_NULL, related_name="phuong_an_phan_cong", null=True, blank=True)
    thang = models.PositiveSmallIntegerField()
    nam = models.PositiveIntegerField()
    phien_ban = models.PositiveIntegerField(default=1)
    ngay_hieu_luc = models.DateField()
    trang_thai = models.CharField(max_length=20, choices=TrangThai.choices, default=TrangThai.DU_THAO)
    ghi_chu = models.TextField(blank=True)
    nguoi_tao = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="phuong_an_phan_cong_da_tao")
    nguoi_ap_dung = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="phuong_an_phan_cong_da_ap_dung", null=True, blank=True)
    ngay_ap_dung = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-nam", "-thang", "-phien_ban"]
        constraints = [
            models.UniqueConstraint(fields=["nhom_lich", "nam", "thang", "phien_ban"], name="uq_phuongan_nhom_ky_phienban"),
            models.CheckConstraint(condition=Q(thang__gte=1, thang__lte=12), name="ck_phuongan_thang"),
        ]
        verbose_name = "Phương án phân công ca"
        verbose_name_plural = "Phương án phân công ca"

    def __str__(self):
        return f"Phân công {self.thang:02d}/{self.nam} v{self.phien_ban}"


class ChiTietPhuongAnPhanCongCa(TimeStampedModel):
    phuong_an = models.ForeignKey(PhuongAnPhanCongCa, on_delete=models.CASCADE, related_name="chi_tiet")
    nhan_su = models.ForeignKey(NhanSu, on_delete=models.PROTECT, related_name="cac_phuong_an_phan_cong")
    kip_truc = models.ForeignKey(KipTruc, on_delete=models.PROTECT, related_name="cac_phuong_an_phan_cong", null=True, blank=True)
    vai_tro = models.CharField(max_length=20, choices=ThanhVienKipTruc.VaiTro.choices, blank=True)
    thu_tu_hien_thi = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["kip_truc__thu_tu", "thu_tu_hien_thi", "nhan_su__ho_ten"]
        constraints = [models.UniqueConstraint(fields=["phuong_an", "nhan_su"], name="uq_phuongan_nhansu")]
        verbose_name = "Chi tiết phương án phân công"
        verbose_name_plural = "Chi tiết phương án phân công"

    def clean(self):
        if self.kip_truc_id and self.kip_truc.nha_may_id != self.phuong_an.nha_may_id:
            raise ValidationError({"kip_truc": "Kíp trực phải thuộc nhà máy của phương án."})
        if self.kip_truc_id and self.kip_truc.nhom_lich_id != self.phuong_an.nhom_lich_id:
            raise ValidationError({"kip_truc": "Kíp trực phải thuộc nhóm lịch của phương án."})
        if self.nhan_su_id and self.nhan_su.don_vi.nha_may_pham_vi_id != self.phuong_an.nha_may_id:
            raise ValidationError({"nhan_su": "Nhân sự phải thuộc nhà máy của phương án."})
        if self.kip_truc_id and not self.vai_tro:
            raise ValidationError({"vai_tro": "Phải chọn chức danh khi phân công vào kíp."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


DEFAULT_OPERATION_CYCLE = [
    {"day": "D", "night": "A", "transition": True},
    {"day": "D", "night": "A"}, {"day": "D", "night": "A"},
    {"day": "B", "night": "D", "transition": True},
    {"day": "B", "night": "D"}, {"day": "B", "night": "D"},
    {"day": "C", "night": "B", "transition": True},
    {"day": "C", "night": "B"}, {"day": "C", "night": "B"},
    {"day": "A", "night": "C", "transition": True},
    {"day": "A", "night": "C"}, {"day": "A", "night": "C"},
]
DEFAULT_ADMIN_CYCLE = [
    {"team": "HC2"}, {"team": "HC2"}, {"team": "HC2"},
    {"team": "HC1", "from": "HC2", "transition": True},
    {"team": "HC1"}, {"team": "HC1"}, {"team": "HC1"}, {"team": "HC1"}, {"team": "HC1"},
    {"team": "HC2", "from": "HC1", "transition": True},
    {"team": "HC2"}, {"team": "HC2"},
]


def default_operation_cycle():
    return [dict(item) for item in DEFAULT_OPERATION_CYCLE]


def default_admin_cycle():
    return [dict(item) for item in DEFAULT_ADMIN_CYCLE]


class MauChuKyCaTruc(TimeStampedModel):
    nha_may = models.ForeignKey("tochuc.NhaMay", on_delete=models.PROTECT, related_name="mau_chu_ky_ca_truc")
    nhom_lich = models.ForeignKey(NhomLichTruc, on_delete=models.PROTECT, related_name="mau_chu_ky", null=True, blank=True)
    ten_mau = models.CharField(max_length=150)
    ngay_moc_van_hanh = models.DateField()
    vi_tri_moc_van_hanh = models.PositiveSmallIntegerField(default=0)
    ngay_moc_hanh_chinh = models.DateField()
    vi_tri_moc_hanh_chinh = models.PositiveSmallIntegerField(default=0)
    chu_ky_van_hanh = models.JSONField(default=default_operation_cycle)
    chu_ky_hanh_chinh = models.JSONField(default=default_admin_cycle)
    tu_ngay = models.DateField()
    den_ngay = models.DateField(null=True, blank=True)
    phien_ban = models.PositiveIntegerField(default=1)
    dang_hoat_dong = models.BooleanField(default=True)

    class Meta:
        ordering = ["-tu_ngay", "-phien_ban"]
        constraints = [models.UniqueConstraint(fields=["nhom_lich", "phien_ban"], name="uq_mauchuky_nhom_phienban")]
        verbose_name = "Mẫu chu kỳ ca trực"
        verbose_name_plural = "Mẫu chu kỳ ca trực"

    def clean(self):
        errors = {}
        if not 0 <= self.vi_tri_moc_van_hanh < len(self.chu_ky_van_hanh or []):
            errors["vi_tri_moc_van_hanh"] = "Vị trí mốc vận hành không hợp lệ."
        if not 0 <= self.vi_tri_moc_hanh_chinh < len(self.chu_ky_hanh_chinh or []):
            errors["vi_tri_moc_hanh_chinh"] = "Vị trí mốc hành chính không hợp lệ."
        if len(self.chu_ky_van_hanh or []) != 12 or len(self.chu_ky_hanh_chinh or []) != 12:
            errors["chu_ky_van_hanh"] = "Mỗi chu kỳ phải có đúng 12 vị trí."
        if self.den_ngay and self.den_ngay < self.tu_ngay:
            errors["den_ngay"] = "Ngày kết thúc không hợp lệ."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ten_mau} v{self.phien_ban}"


class LichTrucCa(TimeStampedModel):
    class CheDoSinhChuKy(models.TextChoices):
        TIEP_NOI = "tiep_noi", "Nối tiếp lịch tháng trước"
        MOC_TUY_CHON = "moc_tuy_chon", "Chọn mốc chu kỳ"

    class LoaiLich(models.TextChoices):
        THANG = "thang", "Lịch tháng"
        CHUYEN_DE = "chuyen_de", "Lịch chuyên đề"

    class TrangThai(models.TextChoices):
        DU_THAO = "du_thao", "Dự thảo"
        CHO_DUYET = "cho_duyet", "Chờ duyệt"
        DA_DUYET = "da_duyet", "Đã duyệt"
        DANG_AP_DUNG = "dang_ap_dung", "Đang áp dụng"
        DA_KHOA = "da_khoa", "Đã khóa"
        TU_CHOI = "tu_choi", "Từ chối"

    nha_may = models.ForeignKey("tochuc.NhaMay", on_delete=models.PROTECT, related_name="lich_truc_ca")
    nhom_lich = models.ForeignKey(NhomLichTruc, on_delete=models.PROTECT, related_name="lich_truc", null=True, blank=True)
    loai_lich = models.CharField(max_length=20, choices=LoaiLich.choices, default=LoaiLich.THANG)
    ten_lich = models.CharField(max_length=200, blank=True)
    tu_ngay = models.DateField(null=True, blank=True)
    den_ngay = models.DateField(null=True, blank=True)
    lich_thang_goc = models.ForeignKey("self", on_delete=models.SET_NULL, related_name="lich_chuyen_de", null=True, blank=True)
    thang = models.PositiveSmallIntegerField()
    nam = models.PositiveIntegerField()
    mau_chu_ky = models.ForeignKey(MauChuKyCaTruc, on_delete=models.PROTECT, related_name="lich_da_sinh")
    che_do_sinh_chu_ky = models.CharField(
        max_length=20, choices=CheDoSinhChuKy.choices, default=CheDoSinhChuKy.TIEP_NOI
    )
    ngay_moc_chu_ky = models.DateField(null=True, blank=True)
    vi_tri_moc_van_hanh = models.PositiveSmallIntegerField(null=True, blank=True)
    vi_tri_moc_hanh_chinh = models.PositiveSmallIntegerField(null=True, blank=True)
    chu_ky_van_hanh_tuy_chon = models.JSONField(null=True, blank=True)
    chu_ky_hanh_chinh_tuy_chon = models.JSONField(null=True, blank=True)
    phien_ban = models.PositiveIntegerField(default=1)
    trang_thai = models.CharField(max_length=20, choices=TrangThai.choices, default=TrangThai.DU_THAO)
    nguoi_tao = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lich_truc_ca_da_tao")
    nguoi_duyet = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lich_truc_ca_da_duyet", null=True, blank=True)
    ngay_gui_duyet = models.DateTimeField(null=True, blank=True)
    ngay_duyet = models.DateTimeField(null=True, blank=True)
    ly_do_tu_choi = models.TextField(blank=True)
    ghi_chu = models.TextField(blank=True)
    snapshot_nhan_su = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-nam", "-thang", "nha_may", "-phien_ban"]
        constraints = [
            models.UniqueConstraint(fields=["nhom_lich", "nam", "thang", "phien_ban"], name="uq_lichtruc_nhom_thang_phienban"),
            models.CheckConstraint(condition=Q(thang__gte=1, thang__lte=12), name="ck_lichtruc_thang"),
        ]
        verbose_name = "Lịch trực ca tháng"
        verbose_name_plural = "Lịch trực ca tháng"

    @property
    def co_the_chinh_sua(self):
        return self.trang_thai in {self.TrangThai.DU_THAO, self.TrangThai.TU_CHOI}

    def clean(self):
        errors = {}
        if self.che_do_sinh_chu_ky == self.CheDoSinhChuKy.MOC_TUY_CHON:
            if not self.ngay_moc_chu_ky:
                errors["ngay_moc_chu_ky"] = "Phải chọn ngày mốc chu kỳ."
            if self.vi_tri_moc_van_hanh is None or not 0 <= self.vi_tri_moc_van_hanh < 12:
                errors["vi_tri_moc_van_hanh"] = "Vị trí chu kỳ vận hành phải từ 1 đến 12."
            if self.vi_tri_moc_hanh_chinh is None or not 0 <= self.vi_tri_moc_hanh_chinh < 12:
                errors["vi_tri_moc_hanh_chinh"] = "Vị trí chu kỳ KT-HC phải từ 1 đến 12."
        if self.loai_lich == self.LoaiLich.CHUYEN_DE:
            if not self.ten_lich.strip():
                errors["ten_lich"] = "Phải nhập tên lịch chuyên đề."
            if not self.tu_ngay:
                errors["tu_ngay"] = "Phải chọn ngày bắt đầu."
            if not self.den_ngay:
                errors["den_ngay"] = "Phải chọn ngày kết thúc."
            if self.tu_ngay and self.den_ngay and self.den_ngay < self.tu_ngay:
                errors["den_ngay"] = "Ngày kết thúc phải từ ngày bắt đầu trở đi."
            if self.tu_ngay and self.den_ngay and (self.den_ngay - self.tu_ngay).days > 62:
                errors["den_ngay"] = "Lịch chuyên đề không được dài quá 63 ngày."
            if self.lich_thang_goc_id and self.lich_thang_goc.nha_may_id != self.nha_may_id:
                errors["lich_thang_goc"] = "Lịch nguồn phải thuộc cùng nhà máy."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"Lịch trực {self.thang:02d}/{self.nam} - {self.nha_may.ma_nha_may}"


class NgayTrucCa(TimeStampedModel):
    class CheDoPhanCongHC(models.TextChoices):
        THEO_PHUONG_AN = "theo_phuong_an", "Theo phương án chung"
        TUY_CHINH = "tuy_chinh", "Tùy chỉnh theo ngày"
        KHONG_BO_TRI = "khong_bo_tri", "Không bố trí nhân sự"

    lich_truc = models.ForeignKey(LichTrucCa, on_delete=models.CASCADE, related_name="danh_sach_ngay")
    ngay = models.DateField()
    ngay_am = models.PositiveSmallIntegerField(null=True, blank=True)
    thang_am = models.PositiveSmallIntegerField(null=True, blank=True)
    nam_am = models.PositiveIntegerField(null=True, blank=True)
    la_thang_nhuan = models.BooleanField(default=False)
    kip_ca_ngay = models.ForeignKey(KipTruc, on_delete=models.PROTECT, related_name="cac_ca_ngay")
    kip_ca_dem = models.ForeignKey(KipTruc, on_delete=models.PROTECT, related_name="cac_ca_dem")
    kip_hanh_chinh = models.ForeignKey(KipTruc, on_delete=models.PROTECT, related_name="cac_ca_hanh_chinh")
    kip_hanh_chinh_truoc = models.ForeignKey(KipTruc, on_delete=models.PROTECT, related_name="cac_lan_giao_ca_hanh_chinh", null=True, blank=True)
    la_ngay_chuyen_kip = models.BooleanField(default=False)
    la_ngay_chuyen_ca_hc = models.BooleanField(default=False)
    da_dieu_chinh = models.BooleanField(default=False)
    ly_do_dieu_chinh = models.TextField(blank=True)
    ghi_chu = models.TextField(blank=True)
    che_do_phan_cong_hc = models.CharField(
        max_length=20, choices=CheDoPhanCongHC.choices,
        default=CheDoPhanCongHC.THEO_PHUONG_AN,
    )

    class Meta:
        ordering = ["ngay"]
        constraints = [models.UniqueConstraint(fields=["lich_truc", "ngay"], name="uq_ngaytruc_lich_ngay")]
        verbose_name = "Ngày trực ca"
        verbose_name_plural = "Các ngày trực ca"

    def clean(self):
        errors = {}
        if self.lich_truc_id:
            for field in ("kip_ca_ngay", "kip_ca_dem"):
                team = getattr(self, field, None)
                if team and (team.nha_may_id != self.lich_truc.nha_may_id or team.loai_kip != KipTruc.LoaiKip.VAN_HANH):
                    errors[field] = "Phải chọn kíp vận hành A–D thuộc đúng nhà máy."
            if self.kip_hanh_chinh_id and (self.kip_hanh_chinh.nha_may_id != self.lich_truc.nha_may_id or self.kip_hanh_chinh.loai_kip != KipTruc.LoaiKip.HANH_CHINH):
                errors["kip_hanh_chinh"] = "Phải chọn Ca 1–2 thuộc đúng nhà máy."
            if self.kip_hanh_chinh_truoc_id and (self.kip_hanh_chinh_truoc.nha_may_id != self.lich_truc.nha_may_id or self.kip_hanh_chinh_truoc.loai_kip != KipTruc.LoaiKip.HANH_CHINH):
                errors["kip_hanh_chinh_truoc"] = "Ca hành chính bàn giao phải thuộc đúng nhà máy."
        if self.da_dieu_chinh and not self.ly_do_dieu_chinh.strip():
            errors["ly_do_dieu_chinh"] = "Phải nhập lý do điều chỉnh."
        if errors:
            raise ValidationError(errors)

    @property
    def hien_thi_ca_ngay(self):
        return f"{self.kip_ca_dem.ma_kip}/{self.kip_ca_ngay.ma_kip}" if self.la_ngay_chuyen_kip else self.kip_ca_ngay.ma_kip

    @property
    def hien_thi_ca_hanh_chinh(self):
        def label(team):
            return team.ma_kip.replace("HC", "")
        if self.la_ngay_chuyen_ca_hc and self.kip_hanh_chinh_truoc_id:
            return f"{label(self.kip_hanh_chinh_truoc)}/{label(self.kip_hanh_chinh)}"
        return label(self.kip_hanh_chinh)

    def __str__(self):
        return f"{self.ngay:%d/%m/%Y}: {self.hien_thi_ca_ngay}"


class PhanCongNhanSuHCNgay(TimeStampedModel):
    ngay_truc = models.ForeignKey(NgayTrucCa, on_delete=models.CASCADE, related_name="phan_cong_hc")
    nhan_su = models.ForeignKey(NhanSu, on_delete=models.PROTECT, related_name="phan_cong_hc_theo_ngay")
    vai_tro = models.CharField(max_length=20, choices=ThanhVienKipTruc.VaiTro.choices, default=ThanhVienKipTruc.VaiTro.NHAN_VIEN)
    thu_tu = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["thu_tu", "nhan_su__ho_ten"]
        constraints = [models.UniqueConstraint(fields=["ngay_truc", "nhan_su"], name="uq_phanconghc_ngay_nhansu")]
        verbose_name = "Phân công KT-HC theo ngày"
        verbose_name_plural = "Phân công KT-HC theo ngày"

    def clean(self):
        if self.nhan_su_id and self.ngay_truc_id and self.nhan_su.don_vi.nha_may_pham_vi_id != self.ngay_truc.lich_truc.nha_may_id:
            raise ValidationError({"nhan_su": "Nhân sự phải thuộc nhà máy của lịch."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class DieuChinhNhanSuCaTruc(TimeStampedModel):
    class LoaiCa(models.TextChoices):
        CA_NGAY = "ca_ngay", "Ca ngày (08:00–20:00)"
        CA_DEM = "ca_dem", "Ca đêm (20:00–08:00)"
        HANH_CHINH = "hanh_chinh", "Ca kỹ thuật - hành chính"

    class LoaiDieuChinh(models.TextChoices):
        DOI_CA = "doi_ca", "Đổi ca"
        TRUC_THAY = "truc_thay", "Trực thay"
        NGHI_PHEP = "nghi_phep", "Nghỉ phép"
        NGHI_BU = "nghi_bu", "Nghỉ bù"
        DIEU_DONG = "dieu_dong", "Điều động"

    class TrangThai(models.TextChoices):
        DU_THAO = "du_thao", "Dự thảo"
        DA_DUYET = "da_duyet", "Đã duyệt"
        TU_CHOI = "tu_choi", "Từ chối"
        DA_HUY = "da_huy", "Đã hủy"

    ngay_truc = models.ForeignKey(NgayTrucCa, on_delete=models.CASCADE, related_name="dieu_chinh_nhan_su")
    ma_phieu = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    loai_ca = models.CharField(max_length=20, choices=LoaiCa.choices)
    ngay_truc_doi = models.ForeignKey(NgayTrucCa, on_delete=models.CASCADE, related_name="dieu_chinh_doi_den", null=True, blank=True)
    loai_ca_doi = models.CharField(max_length=20, choices=LoaiCa.choices, blank=True)
    loai_dieu_chinh = models.CharField(max_length=20, choices=LoaiDieuChinh.choices)
    nhan_su_vang = models.ForeignKey(NhanSu, on_delete=models.PROTECT, related_name="cac_ca_vang", null=True, blank=True)
    nhan_su_thay = models.ForeignKey(NhanSu, on_delete=models.PROTECT, related_name="cac_ca_truc_thay", null=True, blank=True)
    vai_tro_thay = models.CharField(max_length=20, choices=ThanhVienKipTruc.VaiTro.choices, blank=True)
    vai_tro_doi = models.CharField(max_length=20, choices=ThanhVienKipTruc.VaiTro.choices, blank=True)
    ly_do = models.TextField()
    trang_thai = models.CharField(max_length=20, choices=TrangThai.choices, default=TrangThai.DU_THAO)
    nguoi_tao = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dieu_chinh_ca_da_tao")
    nguoi_duyet = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dieu_chinh_ca_da_duyet", null=True, blank=True)
    ngay_duyet = models.DateTimeField(null=True, blank=True)
    ly_do_tu_choi = models.TextField(blank=True)

    class Meta:
        ordering = ["ngay_truc__ngay", "loai_ca", "created_at"]
        verbose_name = "Điều chỉnh nhân sự ca trực"
        verbose_name_plural = "Điều chỉnh nhân sự ca trực"
        indexes = [
            models.Index(fields=["ngay_truc", "loai_ca", "trang_thai"]),
            models.Index(fields=["nhan_su_thay", "trang_thai"]),
        ]

    def clean(self):
        errors = {}
        if not str(self.ly_do or "").strip():
            errors["ly_do"] = "Phải nhập lý do điều chỉnh."
        if self.loai_dieu_chinh in {self.LoaiDieuChinh.NGHI_PHEP, self.LoaiDieuChinh.NGHI_BU} and not self.nhan_su_vang_id:
            errors["nhan_su_vang"] = "Phải chọn nhân sự vắng hoặc không tham gia."
        if self.loai_dieu_chinh in {self.LoaiDieuChinh.DOI_CA, self.LoaiDieuChinh.TRUC_THAY, self.LoaiDieuChinh.DIEU_DONG} and not self.nhan_su_thay_id:
            errors["nhan_su_thay"] = "Phải chọn nhân sự trực thay."
        if self.nhan_su_vang_id and self.nhan_su_vang_id == self.nhan_su_thay_id:
            errors["nhan_su_thay"] = "Người trực thay phải khác người vắng mặt."
        if self.loai_dieu_chinh == self.LoaiDieuChinh.DOI_CA:
            if not self.ngay_truc_doi_id:
                errors["ngay_truc_doi"] = "Phải chọn ngày trực đối ứng."
            if not self.loai_ca_doi:
                errors["loai_ca_doi"] = "Phải chọn ca trực đối ứng."
            if self.ngay_truc_doi_id == self.ngay_truc_id and self.loai_ca_doi == self.loai_ca:
                errors["ngay_truc_doi"] = "Ca đối ứng phải khác ca nguồn."
        plant_id = self.ngay_truc.lich_truc.nha_may_id if self.ngay_truc_id else None
        for field in ("nhan_su_vang", "nhan_su_thay"):
            person = getattr(self, field, None)
            if person and person.don_vi.nha_may_pham_vi_id != plant_id:
                errors[field] = "Nhân sự phải thuộc phạm vi nhà máy của lịch."
        if self.ngay_truc_doi_id and self.ngay_truc_doi.lich_truc.nha_may_id != plant_id:
            errors["ngay_truc_doi"] = "Ngày đối ứng phải thuộc cùng nhà máy."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class LichSuLichTruc(models.Model):
    lich_truc = models.ForeignKey(LichTrucCa, on_delete=models.CASCADE, related_name="lich_su")
    hanh_dong = models.CharField(max_length=40)
    du_lieu_truoc = models.JSONField(default=dict, blank=True)
    du_lieu_sau = models.JSONField(default=dict, blank=True)
    ly_do = models.TextField(blank=True)
    nguoi_thuc_hien = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Lịch sử lịch trực"
        verbose_name_plural = "Lịch sử lịch trực"
