from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.core.files.storage import default_storage
import uuid

from .models import UserProfile

class UploadAvatarAPIView(APIView):
    """API upload avatar của user"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            if 'avatar' not in request.FILES:
                return Response({
                    'success': False,
                    'message': 'Không có file hình ảnh được gửi'
                }, status=status.HTTP_400_BAD_REQUEST)

            avatar_file = request.FILES['avatar']

            # Validate file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
            if avatar_file.content_type not in allowed_types:
                return Response({
                    'success': False,
                    'message': 'Chỉ chấp nhận file JPG, JPEG, PNG'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate file size (max 5MB)
            if avatar_file.size > 5 * 1024 * 1024:
                return Response({
                    'success': False,
                    'message': 'Kích thước file không được vượt quá 5MB'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Generate unique filename
            file_extension = avatar_file.name.split('.')[-1]
            unique_filename = f"avatar_{request.user.id}_{uuid.uuid4().hex[:8]}.{file_extension}"

            # Save file
            file_path = default_storage.save(f"avatars/{unique_filename}", avatar_file)

            # Get or create user profile
            user_profile, created = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={'is_mobile_user': True}
            )

            # Update avatar
            user_profile.avatar = file_path
            user_profile.save()

            # Get full URL
            avatar_url = request.build_absolute_uri(default_storage.url(file_path))

            return Response({
                'success': True,
                'message': 'Cập nhật hình ảnh thành công',
                'avatar_url': avatar_url
            })

        except Exception as e:
            return Response({
                'success': False,
                'message': 'Có lỗi xảy ra khi cập nhật hình ảnh',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UploadSignatureAPIView(APIView):
    """API upload chữ ký điện tử"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            if 'chu_ky' not in request.FILES:
                return Response({
                    'success': False,
                    'message': 'Không có file chữ ký được gửi'
                }, status=status.HTTP_400_BAD_REQUEST)

            signature_file = request.FILES['chu_ky']

            allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
            if signature_file.content_type not in allowed_types:
                return Response({
                    'success': False,
                    'message': 'Chỉ chấp nhận file JPG, JPEG, PNG'
                }, status=status.HTTP_400_BAD_REQUEST)

            if signature_file.size > 5 * 1024 * 1024:
                return Response({
                    'success': False,
                    'message': 'Kích thước file không được vượt quá 5MB'
                }, status=status.HTTP_400_BAD_REQUEST)

            file_extension = signature_file.name.split('.')[-1]
            unique_filename = f"signature_{request.user.id}_{uuid.uuid4().hex[:8]}.{file_extension}"
            file_path = default_storage.save(f"signatures/{unique_filename}", signature_file)

            user_profile, created = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={'is_mobile_user': True}
            )

            user_profile.chu_ky = file_path
            user_profile.save()

            signature_url = request.build_absolute_uri(default_storage.url(file_path))

            return Response({
                'success': True,
                'message': 'Cập nhật chữ ký thành công',
                'chu_ky_url': signature_url
            })

        except Exception as e:
            return Response({
                'success': False,
                'message': 'Có lỗi xảy ra khi cập nhật chữ ký',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
