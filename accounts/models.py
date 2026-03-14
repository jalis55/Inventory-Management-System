from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

class User(AbstractUser):
    """Custom User Model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    def __str__(self):
        return self.email

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

class UserProfile(models.Model):
    """Extended user profile"""
    USER_TYPES = (
        ('admin', 'Administrator'),
        ('manager', 'Manager'),
        ('staff', 'Staff'),
        ('accountant', 'Accountant'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='staff')
    department = models.CharField(max_length=100, blank=True)
    employee_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    nid=models.CharField(max_length=10,null=True,blank=True)
    emergency_contact = models.CharField(max_length=15, blank=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.user_type}"

    class Meta:
        db_table = 'user_profiles'

class ActivityLog(models.Model):
    """Track user activities"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'activity_logs'
        ordering = ['-timestamp']