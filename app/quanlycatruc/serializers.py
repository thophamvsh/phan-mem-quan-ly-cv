from django.db import transaction
from rest_framework import serializers
from tochuc.serializers import (
    BoPhanSerializer,
    DonViToChucSerializer,
    NhanSuSerializer,
)

from .models import ChiTietPhuongAnPhanCongCa, DieuChinhNhanSuCaTruc, KipTruc, LichSuLichTruc, LichTrucCa, MauChuKyCaTruc, NgayTrucCa, NhanSu, NhomLichTruc, PhamViNhanSuCaTruc, PhanCongNhanSuHCNgay, PhuongAnPhanCongCa, ThanhVienKipTruc
from .services import actual_shift_staff


class NhomLichTrucSerializer(serializers.ModelSerializer):
    nha_may_ten = serializers.CharField(source="nha_may.ten_nha_may", read_only=True)
    don_vi_ten = serializers.CharField(source="don_vi.ten_don_vi", read_only=True)
    bo_phan_ten = serializers.CharField(source="bo_phan.ten_bo_phan", read_only=True)

    class Meta:
        model = NhomLichTruc
        fields = ["id", "nha_may", "nha_may_ten", "don_vi", "don_vi_ten", "bo_phan", "bo_phan_ten", "ma_nhom", "ten_nhom", "dia_diem", "thu_tu", "dang_hoat_dong"]

    def validate(self, attrs):
        plant = attrs.get("nha_may", getattr(self.instance, "nha_may", None))
        unit = attrs.get("don_vi", getattr(self.instance, "don_vi", None))
        department = attrs.get("bo_phan", getattr(self.instance, "bo_phan", None))
        if plant and unit and unit.nha_may_pham_vi_id != plant.id:
            raise serializers.ValidationError({"don_vi": "Đơn vị phải thuộc nhà máy đã chọn."})
        if unit and department and department.don_vi_id != unit.id:
            raise serializers.ValidationError({"bo_phan": "Bộ phận phải thuộc đơn vị đã chọn."})
        return attrs


class PhamViNhanSuCaTrucSerializer(serializers.ModelSerializer):
    ho_ten = serializers.CharField(source="nhan_su.ho_ten", read_only=True)
    bo_phan_ten = serializers.CharField(source="nhan_su.bo_phan.ten_bo_phan", read_only=True)

    class Meta:
        model = PhamViNhanSuCaTruc
        fields = ["id", "nhom_lich", "nhan_su", "ho_ten", "bo_phan_ten", "tu_ngay", "den_ngay", "dang_hoat_dong"]
        # POST is an idempotent add/reactivate operation. The database
        # constraint remains the final guard against duplicate rows.
        validators = []

    def validate(self, attrs):
        group = attrs.get("nhom_lich", getattr(self.instance, "nhom_lich", None))
        personnel = attrs.get("nhan_su", getattr(self.instance, "nhan_su", None))
        if group and personnel and personnel.don_vi.nha_may_pham_vi_id != group.nha_may_id:
            raise serializers.ValidationError({"nhan_su": "Nhân sự phải thuộc cùng nhà máy với nhóm lịch."})
        return attrs


class ThanhVienKipTrucSerializer(serializers.ModelSerializer):
    ho_ten = serializers.SerializerMethodField()
    vai_tro_display = serializers.CharField(source="get_vai_tro_display", read_only=True)

    class Meta:
        model = ThanhVienKipTruc
        fields = ["id", "kip_truc", "nhan_su", "user", "ho_ten", "vai_tro", "vai_tro_display", "tu_ngay", "den_ngay", "thu_tu_hien_thi", "dang_hoat_dong"]

    def get_ho_ten(self, obj) -> str:
        if obj.nhan_su_id:
            return obj.nhan_su.ho_ten
        if not obj.user_id:
            return ""
        profile = getattr(obj.user, "profile", None)
        return getattr(profile, "full_name", "") or obj.user.get_full_name() or obj.user.username

    def validate(self, attrs):
        team = attrs.get("kip_truc", getattr(self.instance, "kip_truc", None))
        personnel = attrs.get("nhan_su", getattr(self.instance, "nhan_su", None))
        user = attrs.get("user", getattr(self.instance, "user", None))
        if not personnel and not user:
            raise serializers.ValidationError({"nhan_su": "Phải chọn nhân sự."})
        if team and personnel and personnel.don_vi.nha_may_pham_vi_id != team.nha_may_id:
            raise serializers.ValidationError({"nhan_su": "Nhân sự không thuộc phạm vi nhà máy của kíp."})
        if team and team.nhom_lich_id and personnel and not PhamViNhanSuCaTruc.objects.filter(
            nhom_lich_id=team.nhom_lich_id,
            nhan_su=personnel,
            dang_hoat_dong=True,
        ).exists():
            raise serializers.ValidationError({"nhan_su": "Nhân sự chưa được thêm vào phạm vi của nhóm lịch này."})
        return attrs


class KipTrucSerializer(serializers.ModelSerializer):
    thanh_vien = ThanhVienKipTrucSerializer(many=True, read_only=True)
    nha_may_ten = serializers.CharField(source="nha_may.ten_nha_may", read_only=True)

    class Meta:
        model = KipTruc
        fields = ["id", "nha_may", "nha_may_ten", "nhom_lich", "loai_kip", "ma_kip", "ten_kip", "mau_nhan_dien", "thu_tu", "dang_hoat_dong", "thanh_vien"]


class ChiTietPhuongAnPhanCongCaSerializer(serializers.ModelSerializer):
    ho_ten = serializers.CharField(source="nhan_su.ho_ten", read_only=True)
    bo_phan_ten = serializers.CharField(source="nhan_su.bo_phan.ten_bo_phan", read_only=True)
    kip_truc_ma = serializers.CharField(source="kip_truc.ma_kip", read_only=True)
    vai_tro_display = serializers.CharField(source="get_vai_tro_display", read_only=True)

    class Meta:
        model = ChiTietPhuongAnPhanCongCa
        fields = ["id", "phuong_an", "nhan_su", "ho_ten", "bo_phan_ten", "kip_truc", "kip_truc_ma", "vai_tro", "vai_tro_display", "thu_tu_hien_thi"]
        read_only_fields = ["phuong_an", "nhan_su"]

    def validate(self, attrs):
        if self.instance and self.instance.phuong_an.trang_thai not in {
            PhuongAnPhanCongCa.TrangThai.DU_THAO,
            PhuongAnPhanCongCa.TrangThai.DA_AP_DUNG,
        }:
            raise serializers.ValidationError("Chỉ được sửa phương án đang ở trạng thái dự thảo.")
        team = attrs.get("kip_truc", getattr(self.instance, "kip_truc", None))
        plan = getattr(self.instance, "phuong_an", None)
        if team and plan and team.nhom_lich_id != plan.nhom_lich_id:
            raise serializers.ValidationError({"kip_truc": "Kíp trực phải thuộc nhóm lịch của phương án."})
        return attrs


class PhuongAnPhanCongCaSerializer(serializers.ModelSerializer):
    chi_tiet = ChiTietPhuongAnPhanCongCaSerializer(many=True, read_only=True)
    trang_thai_display = serializers.CharField(source="get_trang_thai_display", read_only=True)

    class Meta:
        model = PhuongAnPhanCongCa
        fields = ["id", "nha_may", "nhom_lich", "lich_truc", "thang", "nam", "phien_ban", "ngay_hieu_luc", "trang_thai", "trang_thai_display", "ghi_chu", "nguoi_tao", "nguoi_ap_dung", "ngay_ap_dung", "chi_tiet", "created_at", "updated_at"]
        read_only_fields = ["phien_ban", "trang_thai", "nguoi_tao", "nguoi_ap_dung", "ngay_ap_dung"]
        # Phiên bản được cấp tuần tự trong perform_create. Nếu để DRF tự sinh
        # UniqueTogetherValidator, mọi request thiếu phien_ban đều bị kiểm tra
        # nhầm với giá trị mặc định 1 trước khi view kịp cấp phiên bản tiếp theo.
        validators = []

    def validate(self, attrs):
        if self.instance and self.instance.trang_thai not in {
            PhuongAnPhanCongCa.TrangThai.DU_THAO,
            PhuongAnPhanCongCa.TrangThai.DA_AP_DUNG,
        }:
            raise serializers.ValidationError("Chỉ được sửa phương án đang ở trạng thái dự thảo.")
        return attrs


class MauChuKyCaTrucSerializer(serializers.ModelSerializer):
    class Meta:
        model = MauChuKyCaTruc
        fields = "__all__"


class DieuChinhNhanSuCaTrucSerializer(serializers.ModelSerializer):
    nhan_su_vang_ten = serializers.CharField(source="nhan_su_vang.ho_ten", read_only=True)
    nhan_su_thay_ten = serializers.CharField(source="nhan_su_thay.ho_ten", read_only=True)
    loai_ca_display = serializers.CharField(source="get_loai_ca_display", read_only=True)
    loai_dieu_chinh_display = serializers.CharField(source="get_loai_dieu_chinh_display", read_only=True)
    trang_thai_display = serializers.CharField(source="get_trang_thai_display", read_only=True)
    vai_tro_thay_display = serializers.CharField(source="get_vai_tro_thay_display", read_only=True)

    class Meta:
        model = DieuChinhNhanSuCaTruc
        fields = ["id", "ma_phieu", "ngay_truc", "loai_ca", "loai_ca_display", "ngay_truc_doi", "loai_ca_doi", "loai_dieu_chinh", "loai_dieu_chinh_display", "nhan_su_vang", "nhan_su_vang_ten", "nhan_su_thay", "nhan_su_thay_ten", "vai_tro_thay", "vai_tro_thay_display", "vai_tro_doi", "ly_do", "trang_thai", "trang_thai_display", "nguoi_tao", "nguoi_duyet", "ngay_duyet", "ly_do_tu_choi", "created_at", "updated_at"]
        read_only_fields = ["ma_phieu", "trang_thai", "nguoi_tao", "nguoi_duyet", "ngay_duyet", "ly_do_tu_choi"]

    def validate(self, attrs):
        day = attrs.get("ngay_truc", getattr(self.instance, "ngay_truc", None))
        if self.instance and self.instance.trang_thai != DieuChinhNhanSuCaTruc.TrangThai.DU_THAO:
            raise serializers.ValidationError("Chỉ được sửa điều chỉnh đang ở trạng thái dự thảo.")
        return attrs


class PhanCongNhanSuHCNgaySerializer(serializers.ModelSerializer):
    ho_ten = serializers.CharField(source="nhan_su.ho_ten", read_only=True)
    vai_tro_display = serializers.CharField(source="get_vai_tro_display", read_only=True)

    class Meta:
        model = PhanCongNhanSuHCNgay
        fields = ["id", "nhan_su", "ho_ten", "vai_tro", "vai_tro_display", "thu_tu"]


class NgayTrucCaSerializer(serializers.ModelSerializer):
    hien_thi_ca_ngay = serializers.CharField(read_only=True)
    hien_thi_ca_hanh_chinh = serializers.CharField(read_only=True)
    kip_ca_ngay_ma = serializers.CharField(source="kip_ca_ngay.ma_kip", read_only=True)
    kip_ca_dem_ma = serializers.CharField(source="kip_ca_dem.ma_kip", read_only=True)
    kip_hanh_chinh_ma = serializers.CharField(source="kip_hanh_chinh.ma_kip", read_only=True)
    dieu_chinh_nhan_su = DieuChinhNhanSuCaTrucSerializer(many=True, read_only=True)
    nhan_su_thuc_te = serializers.SerializerMethodField()
    canh_bao_nhan_su = serializers.SerializerMethodField()
    phan_cong_hc = PhanCongNhanSuHCNgaySerializer(many=True, read_only=True)
    nhan_su_hc = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)

    class Meta:
        model = NgayTrucCa
        fields = ["id", "lich_truc", "ngay", "ngay_am", "thang_am", "nam_am", "la_thang_nhuan", "kip_ca_ngay", "kip_ca_ngay_ma", "kip_ca_dem", "kip_ca_dem_ma", "kip_hanh_chinh", "kip_hanh_chinh_ma", "kip_hanh_chinh_truoc", "la_ngay_chuyen_kip", "la_ngay_chuyen_ca_hc", "hien_thi_ca_ngay", "hien_thi_ca_hanh_chinh", "da_dieu_chinh", "ly_do_dieu_chinh", "ghi_chu", "che_do_phan_cong_hc", "phan_cong_hc", "nhan_su_hc", "dieu_chinh_nhan_su", "nhan_su_thuc_te", "canh_bao_nhan_su"]
        read_only_fields = ["lich_truc"]

    def get_nhan_su_thuc_te(self, obj):
        return {period: actual_shift_staff(obj, period) for period in ("ca_ngay", "ca_dem", "hanh_chinh")}

    def get_canh_bao_nhan_su(self, obj):
        required = {"truong_ca", "truc_chinh", "truc_phu"}
        result = {}
        for period in ("ca_ngay", "ca_dem"):
            staff = actual_shift_staff(obj, period)
            roles = {member["vai_tro"] for member in staff}
            result[period] = len(staff) < 3 or not required.issubset(roles)
        return result

    def validate(self, attrs):
        instance = self.instance
        if instance and not instance.lich_truc.co_the_chinh_sua:
            raise serializers.ValidationError("Chỉ được sửa ngày thuộc lịch dự thảo hoặc bị từ chối.")
        attrs["da_dieu_chinh"] = True
        if not attrs.get("ly_do_dieu_chinh", getattr(instance, "ly_do_dieu_chinh", "")).strip():
            raise serializers.ValidationError({"ly_do_dieu_chinh": "Phải nhập lý do điều chỉnh."})
        schedule = instance.lich_truc
        mode = attrs.get("che_do_phan_cong_hc", instance.che_do_phan_cong_hc)
        assignments = attrs.get("nhan_su_hc")
        if mode != NgayTrucCa.CheDoPhanCongHC.THEO_PHUONG_AN and schedule.loai_lich != LichTrucCa.LoaiLich.CHUYEN_DE:
            raise serializers.ValidationError({"che_do_phan_cong_hc": "Chỉ lịch chuyên đề mới được phân công KT-HC riêng theo ngày."})
        if mode == NgayTrucCa.CheDoPhanCongHC.TUY_CHINH and assignments is not None:
            ids = [item.get("nhan_su") for item in assignments]
            if not ids or any(not value for value in ids):
                raise serializers.ValidationError({"nhan_su_hc": "Phải chọn ít nhất một nhân sự khi dùng chế độ tùy chỉnh."})
            if len(ids) != len(set(ids)):
                raise serializers.ValidationError({"nhan_su_hc": "Danh sách nhân sự không được trùng."})
            candidates = NhanSu.objects.filter(id__in=ids, dang_lam_viec=True).select_related("don_vi", "don_vi__don_vi_cha", "don_vi__don_vi_cha__don_vi_cha")
            valid_ids = {person.id for person in candidates if person.don_vi.nha_may_pham_vi_id == schedule.nha_may_id}
            if valid_ids != set(ids):
                raise serializers.ValidationError({"nhan_su_hc": "Có nhân sự không thuộc nhà máy hoặc đã ngừng làm việc."})
        expected_types = {
            "kip_ca_ngay": KipTruc.LoaiKip.VAN_HANH,
            "kip_ca_dem": KipTruc.LoaiKip.VAN_HANH,
            "kip_hanh_chinh": KipTruc.LoaiKip.HANH_CHINH,
            "kip_hanh_chinh_truoc": KipTruc.LoaiKip.HANH_CHINH,
        }
        for field, expected_type in expected_types.items():
            team = attrs.get(field, getattr(instance, field, None))
            if team and (team.nha_may_id != schedule.nha_may_id or team.loai_kip != expected_type):
                raise serializers.ValidationError({field: "Kíp trực không đúng loại hoặc không thuộc nhà máy của lịch."})
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        assignments = validated_data.pop("nhan_su_hc", None)
        instance = super().update(instance, validated_data)
        if assignments is not None:
            instance.phan_cong_hc.all().delete()
            if instance.che_do_phan_cong_hc == NgayTrucCa.CheDoPhanCongHC.TUY_CHINH:
                PhanCongNhanSuHCNgay.objects.bulk_create([
                    PhanCongNhanSuHCNgay(
                        ngay_truc=instance,
                        nhan_su_id=item["nhan_su"],
                        vai_tro=item.get("vai_tro") or ThanhVienKipTruc.VaiTro.NHAN_VIEN,
                        thu_tu=index,
                    ) for index, item in enumerate(assignments, start=1)
                ])
        elif instance.che_do_phan_cong_hc != NgayTrucCa.CheDoPhanCongHC.TUY_CHINH:
            instance.phan_cong_hc.all().delete()
        return instance


class LichSuLichTrucSerializer(serializers.ModelSerializer):
    nguoi_thuc_hien_ten = serializers.CharField(source="nguoi_thuc_hien.username", read_only=True)

    class Meta:
        model = LichSuLichTruc
        fields = ["id", "hanh_dong", "du_lieu_truoc", "du_lieu_sau", "ly_do", "nguoi_thuc_hien_ten", "created_at"]


class LichTrucCaSerializer(serializers.ModelSerializer):
    nha_may_ten = serializers.CharField(source="nha_may.ten_nha_may", read_only=True)
    trang_thai_display = serializers.CharField(source="get_trang_thai_display", read_only=True)
    danh_sach_ngay = NgayTrucCaSerializer(many=True, read_only=True)
    lich_su = LichSuLichTrucSerializer(many=True, read_only=True)

    class Meta:
        model = LichTrucCa
        fields = ["id", "nha_may", "nha_may_ten", "nhom_lich", "loai_lich", "ten_lich", "tu_ngay", "den_ngay", "lich_thang_goc", "thang", "nam", "mau_chu_ky", "che_do_sinh_chu_ky", "ngay_moc_chu_ky", "vi_tri_moc_van_hanh", "vi_tri_moc_hanh_chinh", "chu_ky_van_hanh_tuy_chon", "chu_ky_hanh_chinh_tuy_chon", "phien_ban", "trang_thai", "trang_thai_display", "nguoi_tao", "nguoi_duyet", "ngay_gui_duyet", "ngay_duyet", "ly_do_tu_choi", "ghi_chu", "snapshot_nhan_su", "danh_sach_ngay", "lich_su", "created_at", "updated_at"]
        read_only_fields = ["phien_ban", "trang_thai", "nguoi_tao", "nguoi_duyet", "ngay_gui_duyet", "ngay_duyet", "ly_do_tu_choi", "snapshot_nhan_su"]
        # The server allocates the next version in perform_create(). DRF's
        # generated validator would otherwise check the read-only default 1.
        validators = []

    def validate(self, attrs):
        template = attrs.get("mau_chu_ky")
        plant = attrs.get("nha_may")
        if template and plant and template.nha_may_id != plant.id:
            raise serializers.ValidationError({"mau_chu_ky": "Mẫu chu kỳ phải thuộc đúng nhà máy."})
        schedule_type = attrs.get("loai_lich", LichTrucCa.LoaiLich.THANG)
        generation_mode = attrs.get("che_do_sinh_chu_ky", LichTrucCa.CheDoSinhChuKy.TIEP_NOI)
        if generation_mode == LichTrucCa.CheDoSinhChuKy.MOC_TUY_CHON:
            anchor_errors = {}
            if not attrs.get("ngay_moc_chu_ky"):
                anchor_errors["ngay_moc_chu_ky"] = "Phải chọn ngày mốc chu kỳ."
            for field, label in (
                ("vi_tri_moc_van_hanh", "vận hành"),
                ("vi_tri_moc_hanh_chinh", "KT-HC"),
            ):
                value = attrs.get(field)
                if value is None or not 0 <= value < 12:
                    anchor_errors[field] = f"Vị trí chu kỳ {label} phải từ 1 đến 12."
            if anchor_errors:
                raise serializers.ValidationError(anchor_errors)
            operation_cycle = attrs.get("chu_ky_van_hanh_tuy_chon")
            admin_cycle = attrs.get("chu_ky_hanh_chinh_tuy_chon")
            if operation_cycle is not None:
                if not isinstance(operation_cycle, list) or len(operation_cycle) != 12:
                    raise serializers.ValidationError({"chu_ky_van_hanh_tuy_chon": "Chu kỳ vận hành phải có đúng 12 ngày."})
                for index, item in enumerate(operation_cycle, start=1):
                    if not isinstance(item, dict) or not item.get("day") or not item.get("night") or item.get("day") == item.get("night"):
                        raise serializers.ValidationError({"chu_ky_van_hanh_tuy_chon": f"Ngày {index} phải có hai ca ngày/đêm khác nhau."})
            if admin_cycle is not None:
                if not isinstance(admin_cycle, list) or len(admin_cycle) != 12 or any(not isinstance(item, dict) or not item.get("team") for item in admin_cycle):
                    raise serializers.ValidationError({"chu_ky_hanh_chinh_tuy_chon": "Chu kỳ KT-HC phải có đúng 12 ngày và đủ kíp trực."})
        start = attrs.get("tu_ngay")
        end = attrs.get("den_ngay")
        source = attrs.get("lich_thang_goc")
        if schedule_type == LichTrucCa.LoaiLich.CHUYEN_DE:
            errors = {}
            group = attrs.get("nhom_lich")
            if source and not group:
                attrs["nhom_lich"] = source.nhom_lich
                group = source.nhom_lich
            if not attrs.get("ten_lich", "").strip():
                errors["ten_lich"] = "Phải nhập tên lịch chuyên đề."
            if not start:
                errors["tu_ngay"] = "Phải chọn ngày bắt đầu."
            if not end:
                errors["den_ngay"] = "Phải chọn ngày kết thúc."
            if start and end and end < start:
                errors["den_ngay"] = "Ngày kết thúc phải từ ngày bắt đầu trở đi."
            if start and end and (end - start).days > 62:
                errors["den_ngay"] = "Lịch chuyên đề không được dài quá 63 ngày."
            if source and plant and source.nha_may_id != plant.id:
                errors["lich_thang_goc"] = "Lịch nguồn phải thuộc cùng nhà máy."
            if source and source.nhom_lich_id != getattr(group, "id", None):
                errors["nhom_lich"] = "Lịch chuyên đề phải thuộc cùng nhóm với lịch nguồn."
            if errors:
                raise serializers.ValidationError(errors)
        return attrs


class TransitionSerializer(serializers.Serializer):
    ly_do = serializers.CharField(required=False, allow_blank=True, default="")
