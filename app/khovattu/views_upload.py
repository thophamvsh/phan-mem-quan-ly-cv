# Upload Material Image View
from django.db import models
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Bang_vat_tu, Bang_hinh_anh_vat_tu
from .permissions import HasFactoryAccess


class UploadMaterialImageView(APIView):
    """
    API để upload hình ảnh cho vật tư (hỗ trợ nhiều hình ảnh)
    """
    permission_classes = [HasFactoryAccess]

    def post(self, request, ma_nha_may, ma_bravo):
        try:
            # Tìm vật tư theo ma_nha_may và ma_bravo
            vat_tu = Bang_vat_tu.objects.select_related('bang_nha_may').filter(
                bang_nha_may__ma_nha_may=ma_nha_may,
                ma_bravo=ma_bravo
            ).first()

            if not vat_tu:
                return Response({
                    "ok": False,
                    "error": f"Không tìm thấy vật tư {ma_bravo} tại nhà máy {ma_nha_may}"
                }, status=status.HTTP_404_NOT_FOUND)

            # Kiểm tra có file image trong request không
            if 'image' not in request.FILES:
                return Response({
                    "ok": False,
                    "error": "Không tìm thấy file hình ảnh"
                }, status=status.HTTP_400_BAD_REQUEST)

            image_file = request.FILES['image']
            mo_ta = request.data.get('mo_ta', '')  # Mô tả hình ảnh (tùy chọn)

            # Validate file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
            if image_file.content_type not in allowed_types:
                return Response({
                    "ok": False,
                    "error": "Định dạng file không được hỗ trợ. Chỉ chấp nhận JPG, PNG, GIF"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate file size (max 5MB)
            max_size = 5 * 1024 * 1024  # 5MB
            if image_file.size > max_size:
                return Response({
                    "ok": False,
                    "error": "Kích thước file quá lớn. Tối đa 5MB"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Tạo tên file unique
            import os
            from django.utils import timezone

            file_extension = os.path.splitext(image_file.name)[1]
            if not file_extension:
                file_extension = '.jpg'

            timestamp = int(timezone.now().timestamp())
            unique_filename = f"vat_tu_{vat_tu.id}_{timestamp}{file_extension}"

            # Tạo record mới trong Bang_hinh_anh_vat_tu
            hinh_anh_vat_tu = Bang_hinh_anh_vat_tu.objects.create(
                vat_tu=vat_tu,
                mo_ta=mo_ta,
                thu_tu=0,  # Sẽ được cập nhật sau
                is_active=True
            )

            # Lưu file
            hinh_anh_vat_tu.hinh_anh.save(unique_filename, image_file, save=True)

            # Cập nhật thứ tự (số thứ tự tiếp theo)
            max_thu_tu = Bang_hinh_anh_vat_tu.objects.filter(
                vat_tu=vat_tu,
                is_active=True
            ).aggregate(max_thu_tu=models.Max('thu_tu'))['max_thu_tu'] or 0

            hinh_anh_vat_tu.thu_tu = max_thu_tu + 1
            hinh_anh_vat_tu.save()

            return Response({
                "ok": True,
                "message": "Hình ảnh vật tư đã được thêm thành công",
                "data": {
                    "id": hinh_anh_vat_tu.id,
                    "image_url": hinh_anh_vat_tu.hinh_anh.url,
                    "filename": unique_filename,
                    "size": image_file.size,
                    "content_type": image_file.content_type,
                    "mo_ta": mo_ta,
                    "thu_tu": hinh_anh_vat_tu.thu_tu
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "ok": False,
                "error": f"Lỗi upload hình ảnh: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request, ma_nha_may, ma_bravo):
        """
        Lấy danh sách hình ảnh của vật tư
        """
        try:
            # Tìm vật tư theo ma_nha_may và ma_bravo
            vat_tu = Bang_vat_tu.objects.select_related('bang_nha_may').filter(
                bang_nha_may__ma_nha_may=ma_nha_may,
                ma_bravo=ma_bravo
            ).first()

            if not vat_tu:
                return Response({
                    "ok": False,
                    "error": f"Không tìm thấy vật tư {ma_bravo} tại nhà máy {ma_nha_may}"
                }, status=status.HTTP_404_NOT_FOUND)

            # Lấy danh sách hình ảnh
            hinh_anh_list = Bang_hinh_anh_vat_tu.objects.filter(
                vat_tu=vat_tu,
                is_active=True
            ).order_by('thu_tu', 'created_at')

            images_data = []
            for hinh_anh in hinh_anh_list:
                # Tạo absolute URL cho hình ảnh
                image_url = hinh_anh.hinh_anh.url
                if not image_url.startswith('http'):
                    from django.conf import settings
                    request_scheme = request.scheme if hasattr(request, 'scheme') else 'http'
                    request_host = request.get_host() if hasattr(request, 'get_host') else '192.168.1.173:8000'
                    image_url = f"{request_scheme}://{request_host}{image_url}"

                images_data.append({
                    "id": hinh_anh.id,
                    "image_url": image_url,
                    "mo_ta": hinh_anh.mo_ta,
                    "thu_tu": hinh_anh.thu_tu,
                    "created_at": hinh_anh.created_at.isoformat()
                })

            return Response({
                "ok": True,
                "data": {
                    "vat_tu": {
                        "ma_bravo": vat_tu.ma_bravo,
                        "ten_vat_tu": vat_tu.ten_vat_tu
                    },
                    "images": images_data,
                    "total": len(images_data)
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "ok": False,
                "error": f"Lỗi lấy danh sách hình ảnh: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, ma_nha_may, ma_bravo):
        """
        Xóa hình ảnh của vật tư
        """
        try:
            image_id = request.data.get('image_id')
            if not image_id:
                return Response({
                    "ok": False,
                    "error": "Thiếu image_id để xóa"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Tìm vật tư theo ma_nha_may và ma_bravo
            vat_tu = Bang_vat_tu.objects.select_related('bang_nha_may').filter(
                bang_nha_may__ma_nha_may=ma_nha_may,
                ma_bravo=ma_bravo
            ).first()

            if not vat_tu:
                return Response({
                    "ok": False,
                    "error": f"Không tìm thấy vật tư {ma_bravo} tại nhà máy {ma_nha_may}"
                }, status=status.HTTP_404_NOT_FOUND)

            # Tìm và xóa hình ảnh
            try:
                hinh_anh = Bang_hinh_anh_vat_tu.objects.get(
                    id=image_id,
                    vat_tu=vat_tu,
                    is_active=True
                )

                # Xóa file vật lý
                if hinh_anh.hinh_anh:
                    hinh_anh.hinh_anh.delete(save=False)

                # Xóa record
                hinh_anh.delete()

                return Response({
                    "ok": True,
                    "message": "Hình ảnh đã được xóa thành công"
                }, status=status.HTTP_200_OK)

            except Bang_hinh_anh_vat_tu.DoesNotExist:
                return Response({
                    "ok": False,
                    "error": "Không tìm thấy hình ảnh để xóa"
                }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({
                "ok": False,
                "error": f"Lỗi xóa hình ảnh: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
