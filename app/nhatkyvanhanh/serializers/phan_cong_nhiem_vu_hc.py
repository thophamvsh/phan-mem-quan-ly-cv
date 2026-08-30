from rest_framework import serializers
from ..models.phan_cong_nhiem_vu_hc import BangPhanCongNhiemVuHC, ChiTietNhiemVuThuTrongTuan
from .mixins import UserSummaryMixin


DEFAULT_DUTY_ROSTER_ITEMS = [
    {
        "stt": 1,
        "thu": "Thứ 2",
        "noi_dung_nhiem_vu": "Xung quanh nhà máy (từ cổng trước ra nhà bảo vệ).\nLau dầu thủy lực/làm mát (các điểm rò rỉ dầu trong nhà máy: các ổ, điều tốc)",
    },
    {
        "stt": 2,
        "thu": "Thứ 3",
        "noi_dung_nhiem_vu": "Tầng 69 và cầu thang lên tầng 69, sắp xếp kho lưu trữ; đổ thùng rác lớn.",
    },
    {
        "stt": 3,
        "thu": "Thứ 4",
        "noi_dung_nhiem_vu": "Phòng ĐKTT + phòng tài liệu. (các tủ+hộc bàn điều khiển+trần + cửa kính xung quanh).\nCa trực VH phối hợp vệ sinh các bộ máy tính trên bàn ĐK",
    },
    {
        "stt": 4,
        "thu": "Thứ 5",
        "noi_dung_nhiem_vu": "Phòng nước (sắp xếp/vệ sinh DCAT + biển báo), kiểm tra/vệ sinh dụng cụ đồ nghề, 2 WC",
    },
    {
        "stt": 5,
        "thu": "Thứ 6",
        "noi_dung_nhiem_vu": "Gian sửa chữa, phòng tự dùng 400vAC + diesel, cửa kính NM phía hạ lưu; cửa lấy gió AH1+AH2",
    },
    {
        "stt": 6,
        "thu": "Thứ 7",
        "noi_dung_nhiem_vu": "Các phòng + tủ, tầng 60 + 55; đổ thùng rác lớn.",
    },
    {
        "stt": 7,
        "thu": "CN",
        "noi_dung_nhiem_vu": "Tầng 50 (vệ sinh 2 hố tua bin và 2 MIV), trạm 110/22kV, MBA T7 + T8.",
    },
]

DEFAULT_GHI_CHU = (
    "- Bảng trên là làm vệ sinh hằng ngày, khi có công việc khác thì trưởng ca trực VH/lãnh đạo NM yêu cầu ca KT-VH thực hiện. "
    "Riêng ngày 01 hàng tháng thực hiện công việc định kỳ theo thứ + thống kê thiết bị làm việc, kiểm tra + vệ sinh thiết bị/dụng cụ/ hệ thống PCCC.\n"
    "- Khu vực làm vệ sinh: bao gồm nền nhà/sân, trần, tường, tủ bảng, bình chữa cháy, rãnh thoát nước, bẫy chuột các phòng bên trong tương ứng trong phạm vi này."
)


class ChiTietNhiemVuThuTrongTuanSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False)

    class Meta:
        model = ChiTietNhiemVuThuTrongTuan
        fields = [
            "id",
            "stt",
            "thu",
            "noi_dung_nhiem_vu",
        ]


class BangPhanCongNhiemVuHCSerializer(serializers.ModelSerializer, UserSummaryMixin):
    chi_tiets = ChiTietNhiemVuThuTrongTuanSerializer(many=True, required=False)
    nha_may_ten = serializers.CharField(source="nha_may.ten_nha_may", read_only=True)
    nguoi_tao_display = serializers.SerializerMethodField()

    class Meta:
        model = BangPhanCongNhiemVuHC
        fields = [
            "id",
            "nha_may",
            "nha_may_ten",
            "thang",
            "nam",
            "tieu_de",
            "ngay_lap",
            "dia_diem_lap",
            "ghi_chu",
            "nguoi_tao",
            "nguoi_tao_display",
            "chi_tiets",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "nguoi_tao"]

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao) or ""

    def create(self, validated_data):
        chi_tiets_data = validated_data.pop("chi_tiets", [])
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["nguoi_tao"] = request.user

        if not validated_data.get("tieu_de"):
            thang = validated_data.get("thang")
            nam = validated_data.get("nam")
            validated_data["tieu_de"] = f"BẢNG PHÂN LÀM VỆ SINH CA KT-VH THÁNG {thang:02d}/{nam}"

        if not validated_data.get("ghi_chu"):
            validated_data["ghi_chu"] = DEFAULT_GHI_CHU

        instance = BangPhanCongNhiemVuHC.objects.create(**validated_data)

        if chi_tiets_data:
            for item in chi_tiets_data:
                item.pop("id", None)
                ChiTietNhiemVuThuTrongTuan.objects.create(bang_phan_cong=instance, **item)
        else:
            for item in DEFAULT_DUTY_ROSTER_ITEMS:
                ChiTietNhiemVuThuTrongTuan.objects.create(bang_phan_cong=instance, **item)

        return instance

    def update(self, instance, validated_data):
        chi_tiets_data = validated_data.pop("chi_tiets", None)

        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()

        if chi_tiets_data is not None:
            existing_items = {str(item.id): item for item in instance.chi_tiets.all()}
            keep_ids = set()

            for item_data in chi_tiets_data:
                item_id = str(item_data.get("id", "")) if item_data.get("id") else None
                if item_id and item_id in existing_items:
                    detail_obj = existing_items[item_id]
                    for attr, val in item_data.items():
                        if attr != "id":
                            setattr(detail_obj, attr, val)
                    detail_obj.save()
                    keep_ids.add(item_id)
                else:
                    item_data.pop("id", None)
                    new_obj = ChiTietNhiemVuThuTrongTuan.objects.create(
                        bang_phan_cong=instance, **item_data
                    )
                    keep_ids.add(str(new_obj.id))

            for old_id, old_obj in existing_items.items():
                if old_id not in keep_ids:
                    old_obj.delete()

        return instance