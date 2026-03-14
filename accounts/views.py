from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import login
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from knox.models import AuthToken
from knox.views import (
    LoginView as KnoxLoginView,
    LogoutAllView as KnoxLogoutAllView,
    LogoutView as KnoxLogoutView,
)
from .models import User, UserProfile, ActivityLog
from .serializers import (
    UserSerializer, UserProfileSerializer, RegisterSerializer,
    LoginSerializer, ChangePasswordSerializer, ActivityLogSerializer,
    RegisterResponseSerializer, LoginResponseSerializer, MessageResponseSerializer
)
import ipaddress

@extend_schema(
    tags=['Authentication'],
    request=RegisterSerializer,
    responses={201: RegisterResponseSerializer},
)
class RegisterAPIView(generics.CreateAPIView):
    """Register new user"""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Create token
        _, token = AuthToken.objects.create(user)
        
        # Log activity
        ActivityLog.objects.create(
            user=user,
            action='USER_REGISTERED',
            ip_address=self.get_client_ip(request),
            details={'email': user.email}
        )
        
        return Response({
            "user": UserSerializer(user).data,
            "token": token
        }, status=status.HTTP_201_CREATED)
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

@extend_schema(
    tags=['Authentication'],
    request=LoginSerializer,
    responses={200: LoginResponseSerializer},
)
class LoginAPIView(KnoxLoginView):
    """User login"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, format=None):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login(request, user)
        
        # Log activity
        ActivityLog.objects.create(
            user=user,
            action='USER_LOGIN',
            ip_address=self.get_client_ip(request),
            details={'email': user.email}
        )
        
        return super().post(request, format=None)
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


@extend_schema(tags=['Authentication'], request=None, responses={204: None})
class LogoutAPIView(KnoxLogoutView):
    pass


@extend_schema(tags=['Authentication'], request=None, responses={204: None})
class LogoutAllAPIView(KnoxLogoutAllView):
    pass

@extend_schema_view(
    get=extend_schema(tags=['Authentication'], responses={200: UserProfileSerializer}),
    put=extend_schema(tags=['Authentication'], request=UserProfileSerializer, responses={200: UserProfileSerializer}),
    patch=extend_schema(tags=['Authentication'], request=UserProfileSerializer, responses={200: UserProfileSerializer}),
)
class UserProfileAPIView(generics.RetrieveUpdateAPIView):
    """Get and update user profile"""
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

@extend_schema(
    tags=['Authentication'],
    request=ChangePasswordSerializer,
    responses={200: MessageResponseSerializer},
)
class ChangePasswordAPIView(APIView):
    """Change user password"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if user.check_password(serializer.data.get('old_password')):
                user.set_password(serializer.data.get('new_password'))
                user.save()
                
                # Log activity
                ActivityLog.objects.create(
                    user=user,
                    action='PASSWORD_CHANGED',
                    ip_address=self.get_client_ip(request)
                )
                
                return Response({'message': 'Password changed successfully.'})
            return Response({'old_password': ['Wrong password.']}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

@extend_schema(tags=['Users'])
class UserListAPIView(generics.ListAPIView):
    """List all users (Admin only)"""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = User.objects.order_by('date_joined')

@extend_schema(tags=['Users'])
class UserDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Manage user (Admin only)"""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = User.objects.all()
    lookup_field = 'id'

@extend_schema(
    tags=['Users'],
    parameters=[
        OpenApiParameter(name='user_id', type=str, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name='action', type=str, location=OpenApiParameter.QUERY, required=False),
    ],
)
class ActivityLogAPIView(generics.ListAPIView):
    """View activity logs (Admin only)"""
    serializer_class = ActivityLogSerializer
    permission_classes = [permissions.IsAdminUser]
    
    def get_queryset(self):
        queryset = ActivityLog.objects.all()
        user_id = self.request.query_params.get('user_id', None)
        action = self.request.query_params.get('action', None)
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if action:
            queryset = queryset.filter(action=action)
            
        return queryset
