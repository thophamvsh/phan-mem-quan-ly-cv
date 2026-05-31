from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from ..models import (
    SonghinhMnh,
    ThuongKonTumMnh,
    Vinhson_HoA,
    Vinhson_HoB,
    Vinhson_Hoc,
)
from ..serializers import (
    SonghinhMnhSerializer,
    ThuongKonTumMnhSerializer,
    Vinhson_HoASerializer,
    Vinhson_HoBSerializer,
    Vinhson_HocSerializer,
)
from .views_sanxuat import user_can_access_plant


class BaseMnhViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    plant_code = ""

    def get_queryset(self):
        if not user_can_access_plant(self.request.user, self.plant_code):
            raise PermissionDenied(f"Bạn không có quyền truy cập dữ liệu của nhà máy {self.plant_code.upper()}.")
        return self.queryset.all()

    def perform_create(self, serializer):
        if not user_can_access_plant(self.request.user, self.plant_code):
            raise PermissionDenied(f"Bạn không có quyền tạo dữ liệu của nhà máy {self.plant_code.upper()}.")
        serializer.save()

    def perform_update(self, serializer):
        if not user_can_access_plant(self.request.user, self.plant_code):
            raise PermissionDenied(f"Bạn không có quyền cập nhật dữ liệu của nhà máy {self.plant_code.upper()}.")
        serializer.save()

    def perform_destroy(self, instance):
        if not user_can_access_plant(self.request.user, self.plant_code):
            raise PermissionDenied(f"Bạn không có quyền xóa dữ liệu của nhà máy {self.plant_code.upper()}.")
        instance.delete()


class SonghinhMnhViewSet(BaseMnhViewSet):
    queryset = SonghinhMnh.objects.all()
    serializer_class = SonghinhMnhSerializer
    plant_code = "songhinh"


class ThuongKonTumMnhViewSet(BaseMnhViewSet):
    queryset = ThuongKonTumMnh.objects.all()
    serializer_class = ThuongKonTumMnhSerializer
    plant_code = "thuongkontum"


class Vinhson_HoAViewSet(BaseMnhViewSet):
    queryset = Vinhson_HoA.objects.all()
    serializer_class = Vinhson_HoASerializer
    plant_code = "vinhson"


class Vinhson_HoBViewSet(BaseMnhViewSet):
    queryset = Vinhson_HoB.objects.all()
    serializer_class = Vinhson_HoBSerializer
    plant_code = "vinhson"


class Vinhson_HocViewSet(BaseMnhViewSet):
    queryset = Vinhson_Hoc.objects.all()
    serializer_class = Vinhson_HocSerializer
    plant_code = "vinhson"
