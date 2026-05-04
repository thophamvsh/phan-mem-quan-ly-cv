from rest_framework import viewsets
from .models import SonghinhMnh, ThuongKonTumMnh, Vinhson_HoA, Vinhson_HoB, Vinhson_Hoc
from .serializers import (
    SonghinhMnhSerializer,
    ThuongKonTumMnhSerializer,
    Vinhson_HoASerializer,
    Vinhson_HoBSerializer,
    Vinhson_HocSerializer,
)


class SonghinhMnhViewSet(viewsets.ModelViewSet):
    queryset = SonghinhMnh.objects.all()
    serializer_class = SonghinhMnhSerializer


class ThuongKonTumMnhViewSet(viewsets.ModelViewSet):
    queryset = ThuongKonTumMnh.objects.all()
    serializer_class = ThuongKonTumMnhSerializer


class Vinhson_HoAViewSet(viewsets.ModelViewSet):
    queryset = Vinhson_HoA.objects.all()
    serializer_class = Vinhson_HoASerializer


class Vinhson_HoBViewSet(viewsets.ModelViewSet):
    queryset = Vinhson_HoB.objects.all()
    serializer_class = Vinhson_HoBSerializer


class Vinhson_HocViewSet(viewsets.ModelViewSet):
    queryset = Vinhson_Hoc.objects.all()
    serializer_class = Vinhson_HocSerializer