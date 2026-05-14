from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
import time

from .models import User, UserProfile
from .serializers import UserSerializer, UserProfileSerializer

class UserProfileAPIView(APIView):
    """API để lấy và cập nhật thông tin profile của user hiện tại"""
    permission_classes = [IsAuthenticated]

    def _get_response_with_cache_headers(self, data):
        response = Response(data)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    def get(self, request):
        """Lấy thông tin profile của user hiện tại"""
        try:
            profile, created = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={'is_mobile_user': True}
            )
            serializer = UserProfileSerializer(profile, context={'request': request})
            
            return self._get_response_with_cache_headers({
                'success': True,
                'user': serializer.data,
                'timestamp': profile.updated_at.isoformat() if profile.updated_at else None,
                'cache_bust': int(time.time() * 1000)
            })
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Lỗi lấy thông tin profile: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request):
        return self.patch(request)

    def patch(self, request):
        """Cập nhật thông tin profile của user hiện tại"""
        try:
            profile, created = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={'is_mobile_user': True}
            )
            serializer = UserProfileSerializer(profile, data=request.data, partial=True, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return self._get_response_with_cache_headers({
                    'success': True,
                    'message': 'Cập nhật thông tin thành công',
                    'user': serializer.data,
                    'timestamp': profile.updated_at.isoformat() if profile.updated_at else None,
                    'cache_bust': int(time.time() * 1000)
                })
            else:
                return Response({
                    'success': False,
                    'message': 'Cập nhật thất bại',
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Lỗi cập nhật profile: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from rest_framework import generics

class UserListAPIView(generics.ListAPIView):
    """API lấy danh sách user (chỉ admin)"""
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_queryset(self):
        # Chỉ admin mới có thể xem danh sách user
        if not self.request.user.is_staff:
            return User.objects.none()
        return User.objects.all().select_related('profile__nha_may')

    def list(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({
                'success': False,
                'message': 'Không có quyền truy cập'
            }, status=status.HTTP_403_FORBIDDEN)
            
        response = super().list(request, *args, **kwargs)
        
        # Override to maintain 'success' structure if desired, or just use DRF's default
        return Response({
            'success': True,
            'data': response.data['results'] if 'results' in response.data else response.data,
            'count': response.data['count'] if 'count' in response.data else len(response.data),
            'next': response.data.get('next'),
            'previous': response.data.get('previous')
        }, status=status.HTTP_200_OK)
