from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

class Category(models.Model):
    """Product Categories"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    image = models.ImageField(upload_to='categories/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Brand(models.Model):
    """Product Brands"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='brands/', null=True, blank=True)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'brands'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Unit(models.Model):
    """Measurement Units (pcs, kg, box, etc.)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    abbreviation = models.CharField(max_length=10, unique=True)
    description = models.CharField(max_length=255, blank=True)
    
    class Meta:
        db_table = 'units'
    
    def __str__(self):
        return f"{self.name} ({self.abbreviation})"

class Product(models.Model):
    """Main Product Model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU")
    barcode = models.CharField(max_length=100, unique=True, null=True, blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Relationships
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, null=True, blank=True, related_name='products')
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='products')
    
    # Pricing
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Tax
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Inventory
    current_stock = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    minimum_stock = models.IntegerField(default=5, validators=[MinValueValidator(0)])
    maximum_stock = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    reorder_point = models.IntegerField(default=10, validators=[MinValueValidator(0)])
    
    # Media
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    gallery = models.JSONField(default=list, blank=True)  # Store multiple image URLs
    
    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_discounted = models.BooleanField(default=False)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Metadata
    tags = models.JSONField(default=list, blank=True)
    attributes = models.JSONField(default=dict, blank=True)  # Store product attributes like size, color, etc.
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_products')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_products')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'products'
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['barcode']),
            models.Index(fields=['name']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.sku})"
    
    def save(self, *args, **kwargs):
        if not self.sku:
            # Generate SKU if not provided
            prefix = self.category.name[:3].upper() if self.category else "PRD"
            import random
            self.sku = f"{prefix}{random.randint(1000, 9999)}"
        super().save(*args, **kwargs)
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.cost_price > 0:
            return ((self.selling_price - self.cost_price) / self.cost_price) * 100
        return 0
    
    @property
    def is_low_stock(self):
        """Check if stock is below reorder point"""
        return self.current_stock <= self.reorder_point
    
    @property
    def is_out_of_stock(self):
        """Check if product is out of stock"""
        return self.current_stock <= 0

class ProductVariant(models.Model):
    """Product Variants (size, color, etc.)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)  # e.g., "Red - Large"
    
    # Variant attributes
    attributes = models.JSONField(default=dict)  # {"color": "Red", "size": "Large"}
    
    # Pricing
    price_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cost_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Stock
    stock = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Image
    image = models.ImageField(upload_to='product_variants/', null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_variants'
        unique_together = ['product', 'sku']
    
    def __str__(self):
        return f"{self.product.name} - {self.name}"
    
    @property
    def selling_price(self):
        return self.product.selling_price + self.price_adjustment
    
    @property
    def cost_price(self):
        return self.product.cost_price + self.cost_adjustment

class StockMovement(models.Model):
    """Track all stock movements"""
    MOVEMENT_TYPES = (
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('return', 'Return'),
        ('adjustment', 'Adjustment'),
        ('transfer', 'Transfer'),
        ('damage', 'Damage'),
        ('expiry', 'Expiry'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True, related_name='stock_movements')
    
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()  # Positive for incoming, negative for outgoing
    previous_quantity = models.IntegerField()
    new_quantity = models.IntegerField()
    
    reference_id = models.UUIDField(null=True, blank=True)  # Reference to sale/purchase order
    reference_type = models.CharField(max_length=50, null=True, blank=True)
    
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'stock_movements'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.movement_type} - {self.product.name} - {self.quantity}"