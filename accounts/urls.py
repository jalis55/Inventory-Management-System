from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterAPIView.as_view(), name='register'),
    path('login/', views.LoginAPIView.as_view(), name='login'),
    path('logout/', views.LogoutAPIView.as_view(), name='logout'),
    path('logoutall/', views.LogoutAllAPIView.as_view(), name='logoutall'),
    path('profile/', views.UserProfileAPIView.as_view(), name='profile'),
    path('change-password/', views.ChangePasswordAPIView.as_view(), name='change-password'),
    path('users/', views.UserListAPIView.as_view(), name='user-list'),
    path('users/<uuid:id>/', views.UserDetailAPIView.as_view(), name='user-detail'),
    path('activity-logs/', views.ActivityLogAPIView.as_view(), name='activity-logs'),
]
