from django.db import models
from django.core.validators import MinValueValidator, EmailValidator
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

class Supplier(models.Model):
    """Supplier Information"""
    PAYMENT_TERMS = (
        ('immediate', 'Immediate'),
        ('net_15', 'Net 15'),
        ('net_30', 'Net 30'),
        ('net_45', 'Net 45'),
        ('net_60', 'Net 60'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_name = models.CharField(max_length=200, unique=True)
    contact_person = models.CharField(max_length=100)
    email = models.EmailField(validators=[EmailValidator()])
    phone = models.CharField(max_length=20)
    mobile = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    
    # Address
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='India')
    
    # Business details
    gst_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    pan_number = models.CharField(max_length=20, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    
    # Payment
    payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERMS, default='net_30')
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outstanding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Bank details
    bank_name = models.CharField(max_length=200, blank=True)
    bank_account = models.CharField(max_length=50, blank=True)
    bank_ifsc = models.CharField(max_length=20, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    rating = models.IntegerField(default=3, choices=[(i, i) for i in range(1, 6)])
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_suppliers')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_suppliers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'suppliers'
        ordering = ['company_name']
    
    def __str__(self):
        return self.company_name

class SupplierProduct(models.Model):
    """Products supplied by supplier"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='supplier_products')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='supplier_products')
    supplier_sku = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    lead_time_days = models.IntegerField(default=7, validators=[MinValueValidator(1)])
    minimum_order_quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    
    is_preferred = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'supplier_products'
        unique_together = ['supplier', 'product']
    
    def __str__(self):
        return f"{self.supplier.company_name} - {self.product.name}"