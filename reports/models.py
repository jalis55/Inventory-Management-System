from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

class SavedReport(models.Model):
    """Saved report configurations"""
    REPORT_TYPES = (
        ('sales', 'Sales Report'),
        ('purchase', 'Purchase Report'),
        ('inventory', 'Inventory Report'),
        ('customer', 'Customer Report'),
        ('supplier', 'Supplier Report'),
        ('financial', 'Financial Report'),
        ('dues', 'Dues Report'),
        ('product', 'Product Report'),
        ('profit_loss', 'Profit & Loss'),
        ('cash_flow', 'Cash Flow'),
    )
    
    FORMATS = (
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('html', 'HTML'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    description = models.TextField(blank=True)
    
    # Report configuration (JSON)
    config = models.JSONField(default=dict)
    
    # Default format
    default_format = models.CharField(max_length=10, choices=FORMATS, default='pdf')
    
    # Sharing
    is_public = models.BooleanField(default=False)
    shared_with = models.ManyToManyField(User, related_name='shared_reports', blank=True)
    
    # Schedule
    is_scheduled = models.BooleanField(default=False)
    schedule_cron = models.CharField(max_length=100, blank=True)  # Cron expression
    schedule_recipients = models.JSONField(default=list)  # Email recipients
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_generated = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'saved_reports'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.report_type}"


class ReportGeneration(models.Model):
    """History of report generations"""
    STATUS = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    saved_report = models.ForeignKey(SavedReport, on_delete=models.CASCADE, related_name='generations', null=True, blank=True)
    
    report_type = models.CharField(max_length=50)
    parameters = models.JSONField(default=dict)
    format = models.CharField(max_length=10)
    
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    
    # File
    file = models.FileField(upload_to='reports/', null=True, blank=True)
    file_size = models.IntegerField(default=0)
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    execution_time = models.FloatField(default=0)  # in seconds
    
    # Error
    error_message = models.TextField(blank=True)
    
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'report_generations'
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.report_type} - {self.started_at}"


class DashboardWidget(models.Model):
    """Custom dashboard widgets"""
    WIDGET_TYPES = (
        ('chart', 'Chart'),
        ('metric', 'Metric'),
        ('table', 'Table'),
        ('list', 'List'),
    )
    
    CHART_TYPES = (
        ('line', 'Line Chart'),
        ('bar', 'Bar Chart'),
        ('pie', 'Pie Chart'),
        ('doughnut', 'Doughnut Chart'),
        ('area', 'Area Chart'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboard_widgets')
    
    name = models.CharField(max_length=100)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPES)
    chart_type = models.CharField(max_length=20, choices=CHART_TYPES, null=True, blank=True)
    
    # Data source
    data_source = models.CharField(max_length=100)  # e.g., 'sales.daily', 'inventory.low_stock'
    query_params = models.JSONField(default=dict)
    
    # Appearance
    color = models.CharField(max_length=20, default='#3B82F6')
    size = models.CharField(max_length=10, choices=[('small', 'Small'), ('medium', 'Medium'), ('large', 'Large')], default='medium')
    position_x = models.IntegerField(default=0)
    position_y = models.IntegerField(default=0)
    
    # Refresh
    refresh_interval = models.IntegerField(default=300)  # in seconds
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'dashboard_widgets'
        ordering = ['position_y', 'position_x']
    
    def __str__(self):
        return f"{self.user.username} - {self.name}"