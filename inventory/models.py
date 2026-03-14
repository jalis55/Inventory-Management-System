from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from products.models import Product, ProductVariant
import uuid
from datetime import timedelta
from django.utils import timezone

User = get_user_model()

class Warehouse(models.Model):
    """Warehouse/Location where inventory is stored"""
    WAREHOUSE_TYPES = (
        ('main', 'Main Warehouse'),
        ('branch', 'Branch Warehouse'),
        ('store', 'Retail Store'),
        ('damaged', 'Damaged Goods'),
        ('returns', 'Returns Processing'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=WAREHOUSE_TYPES, default='main')
    
    # Location
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='India')
    
    # Contact
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    # Capacity
    total_capacity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="in sq ft")
    used_capacity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_refrigerated = models.BooleanField(default=False)
    
    # Metadata
    notes = models.TextField(blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_warehouses')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_warehouses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'warehouses'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def save(self, *args, **kwargs):
        if not self.code:
            # Generate warehouse code
            import random
            prefix = self.name[:3].upper()
            random_num = random.randint(100, 999)
            self.code = f"WH-{prefix}-{random_num}"
        super().save(*args, **kwargs)


class Stock(models.Model):
    """Current stock levels by warehouse"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='stock_items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='stock_items')
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, null=True, blank=True, related_name='stock_items')
    
    # Stock levels
    quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    reserved_quantity = models.IntegerField(default=0)  # Items in pending orders
    available_quantity = models.IntegerField(default=0)  # quantity - reserved
    reorder_point = models.IntegerField(default=10)
    
    # Location within warehouse
    bin_location = models.CharField(max_length=100, blank=True)
    shelf = models.CharField(max_length=50, blank=True)
    rack = models.CharField(max_length=50, blank=True)
    
    # Batch/Serial tracking
    track_batch = models.BooleanField(default=False)
    track_serial = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Dates
    last_received = models.DateTimeField(null=True, blank=True)
    last_shipped = models.DateTimeField(null=True, blank=True)
    last_counted = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'stock'
        unique_together = ['warehouse', 'product', 'variant']
        indexes = [
            models.Index(fields=['warehouse', 'product']),
            models.Index(fields=['quantity']),
        ]
    
    def __str__(self):
        return f"{self.product.name} @ {self.warehouse.code}: {self.quantity}"
    
    def save(self, *args, **kwargs):
        self.available_quantity = self.quantity - self.reserved_quantity
        super().save(*args, **kwargs)
    
    @property
    def is_low_stock(self):
        return self.available_quantity <= self.reorder_point
    
    @property
    def is_out_of_stock(self):
        return self.available_quantity <= 0


class Batch(models.Model):
    """Batch tracking for perishable/serialized items"""
    BATCH_STATUS = (
        ('active', 'Active'),
        ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('blocked', 'Blocked'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch_number = models.CharField(max_length=100, unique=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='batches')
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, null=True, blank=True)
    
    # Batch details
    manufacturing_date = models.DateField()
    expiry_date = models.DateField()
    manufacturing_lot = models.CharField(max_length=100, blank=True)
    
    # Quantity
    initial_quantity = models.IntegerField(validators=[MinValueValidator(0)])
    current_quantity = models.IntegerField(validators=[MinValueValidator(0)])
    
    # Location
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='batches')
    bin_location = models.CharField(max_length=100, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=BATCH_STATUS, default='active')
    quality_check_passed = models.BooleanField(default=True)
    quality_notes = models.TextField(blank=True)
    
    # Pricing
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Dates
    received_date = models.DateField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'batches'
        indexes = [
            models.Index(fields=['batch_number']),
            models.Index(fields=['expiry_date']),
            models.Index(fields=['product', 'expiry_date']),
        ]
    
    def __str__(self):
        return f"{self.batch_number} - {self.product.name}"
    
    @property
    def days_until_expiry(self):
        if self.expiry_date:
            return (self.expiry_date - timezone.now().date()).days
        return None
    
    @property
    def is_expiring_soon(self):
        days = self.days_until_expiry
        return days is not None and days <= 30 and days > 0
    
    def save(self, *args, **kwargs):
        # Update status based on expiry
        if self.expiry_date < timezone.now().date():
            self.status = 'expired'
        elif self.days_until_expiry and self.days_until_expiry <= 30:
            self.status = 'expiring_soon'
        super().save(*args, **kwargs)


class SerialNumber(models.Model):
    """Serial number tracking for individual items"""
    SERIAL_STATUS = (
        ('available', 'Available'),
        ('sold', 'Sold'),
        ('returned', 'Returned'),
        ('damaged', 'Damaged'),
        ('warranty', 'Under Warranty'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    serial_number = models.CharField(max_length=100, unique=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='serials')
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, null=True, blank=True)
    
    # Current location
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='serials', null=True, blank=True)
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name='serials')
    
    # Status
    status = models.CharField(max_length=20, choices=SERIAL_STATUS, default='available')
    
    # Warranty
    warranty_start = models.DateField(null=True, blank=True)
    warranty_end = models.DateField(null=True, blank=True)
    
    # Sales info
    sold_to = models.ForeignKey('customers.Customer', on_delete=models.SET_NULL, null=True, blank=True)
    sold_date = models.DateField(null=True, blank=True)
    sales_order = models.ForeignKey('sales.SalesOrder', on_delete=models.SET_NULL, null=True, blank=True)
    
    # History
    manufactured_date = models.DateField(null=True, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'serial_numbers'
        indexes = [
            models.Index(fields=['serial_number']),
            models.Index(fields=['status']),
            models.Index(fields=['product', 'status']),
        ]
    
    def __str__(self):
        return f"{self.serial_number} - {self.product.name}"


class StockTransfer(models.Model):
    """Transfer stock between warehouses"""
    TRANSFER_STATUS = (
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('in_transit', 'In Transit'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer_number = models.CharField(max_length=50, unique=True)
    
    # Locations
    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='transfers_out')
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='transfers_in')
    
    # Dates
    transfer_date = models.DateField(auto_now_add=True)
    expected_delivery = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=TRANSFER_STATUS, default='draft')
    
    # Tracking
    reference_number = models.CharField(max_length=100, blank=True)
    vehicle_number = models.CharField(max_length=50, blank=True)
    driver_name = models.CharField(max_length=100, blank=True)
    driver_phone = models.CharField(max_length=20, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Approval
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='requested_transfers')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_transfers')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_transfers')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_transfers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'stock_transfers'
        ordering = ['-transfer_date']
    
    def __str__(self):
        return f"Transfer {self.transfer_number}: {self.from_warehouse.code} -> {self.to_warehouse.code}"
    
    def save(self, *args, **kwargs):
        if not self.transfer_number:
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(10000, 99999)
            self.transfer_number = f"TRF-{year}{month}-{random_num}"
        super().save(*args, **kwargs)


class StockTransferItem(models.Model):
    """Items in a stock transfer"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name='items')
    
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, null=True, blank=True)
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True)
    
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    received_quantity = models.IntegerField(default=0)
    
    # For serialized items
    serial_numbers = models.JSONField(default=list, blank=True)
    
    notes = models.CharField(max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'stock_transfer_items'
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class StockAdjustment(models.Model):
    """Stock adjustments (cycle count, damage, loss, etc.)"""
    ADJUSTMENT_TYPES = (
        ('cycle_count', 'Cycle Count'),
        ('damage', 'Damaged Goods'),
        ('loss', 'Lost/Stolen'),
        ('found', 'Found Surplus'),
        ('quality', 'Quality Control'),
        ('sample', 'Sample/Testing'),
        ('donation', 'Donation'),
        ('other', 'Other'),
    )
    
    ADJUSTMENT_STATUS = (
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    adjustment_number = models.CharField(max_length=50, unique=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='adjustments')
    
    adjustment_type = models.CharField(max_length=20, choices=ADJUSTMENT_TYPES)
    status = models.CharField(max_length=20, choices=ADJUSTMENT_STATUS, default='draft')
    
    adjustment_date = models.DateField(auto_now_add=True)
    
    # Reason
    reason = models.TextField()
    
    # Financial impact
    total_cost_impact = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Approval
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_adjustments')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_adjustments')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_adjustments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'stock_adjustments'
        ordering = ['-adjustment_date']
    
    def __str__(self):
        return f"Adjustment {self.adjustment_number}: {self.adjustment_type}"
    
    def save(self, *args, **kwargs):
        if not self.adjustment_number:
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(10000, 99999)
            self.adjustment_number = f"ADJ-{year}{month}-{random_num}"
        super().save(*args, **kwargs)


class StockAdjustmentItem(models.Model):
    """Items in a stock adjustment"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    adjustment = models.ForeignKey(StockAdjustment, on_delete=models.CASCADE, related_name='items')
    
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, null=True, blank=True)
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Quantities
    expected_quantity = models.IntegerField()
    counted_quantity = models.IntegerField()
    difference = models.IntegerField()
    
    # Cost impact
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    cost_impact = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Reason
    reason = models.CharField(max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'stock_adjustment_items'
    
    def save(self, *args, **kwargs):
        self.difference = self.counted_quantity - self.expected_quantity
        self.cost_impact = self.difference * self.unit_cost
        super().save(*args, **kwargs)


class CycleCount(models.Model):
    """Cycle counting schedule and execution"""
    COUNT_STATUS = (
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('verified', 'Verified'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    count_number = models.CharField(max_length=50, unique=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='cycle_counts')
    
    # Schedule
    scheduled_date = models.DateField()
    counted_date = models.DateField(null=True, blank=True)
    verified_date = models.DateField(null=True, blank=True)
    
    # Area/Category
    zone = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=100, blank=True)
    
    status = models.CharField(max_length=20, choices=COUNT_STATUS, default='scheduled')
    
    # Counters
    counted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='cycle_counts_done')
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='cycle_counts_verified')
    
    # Results
    total_items = models.IntegerField(default=0)
    items_counted = models.IntegerField(default=0)
    items_matched = models.IntegerField(default=0)
    items_discrepancy = models.IntegerField(default=0)
    discrepancy_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    notes = models.TextField(blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cycle_counts'
        ordering = ['-scheduled_date']
    
    def __str__(self):
        return f"Cycle Count {self.count_number} - {self.warehouse.code}"
    
    def save(self, *args, **kwargs):
        if not self.count_number:
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(1000, 9999)
            self.count_number = f"CC-{year}{month}-{random_num}"
        super().save(*args, **kwargs)


class CycleCountItem(models.Model):
    """Items in a cycle count"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cycle_count = models.ForeignKey(CycleCount, on_delete=models.CASCADE, related_name='items')
    
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, null=True, blank=True)
    
    # Quantities
    system_quantity = models.IntegerField()
    counted_quantity = models.IntegerField(null=True, blank=True)
    difference = models.IntegerField(default=0)
    
    # Location
    bin_location = models.CharField(max_length=100, blank=True)
    
    # Status
    is_counted = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    has_discrepancy = models.BooleanField(default=False)
    
    notes = models.CharField(max_length=255, blank=True)
    
    counted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cycle_count_items'
    
    def __str__(self):
        return f"{self.product.name} - System: {self.system_quantity}, Counted: {self.counted_quantity}"
    
    def save(self, *args, **kwargs):
        if self.counted_quantity is not None:
            self.difference = self.counted_quantity - self.system_quantity
            self.has_discrepancy = self.difference != 0
        super().save(*args, **kwargs)


class ReorderRequest(models.Model):
    """Automatic reorder suggestions based on stock levels"""
    PRIORITY = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )
    
    STATUS = (
        ('pending', 'Pending'),
        ('ordered', 'Ordered'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='reorder_requests')
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, null=True, blank=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='reorder_requests')
    
    # Current status
    current_stock = models.IntegerField()
    reorder_point = models.IntegerField()
    suggested_quantity = models.IntegerField()
    
    # Based on
    average_daily_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    lead_time_days = models.IntegerField(default=7)
    
    priority = models.CharField(max_length=20, choices=PRIORITY)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    
    # Supplier (from product's preferred supplier)
    suggested_supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.SET_NULL, null=True)
    
    generated_date = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    # If converted to purchase order
    purchase_order = models.ForeignKey('purchases.PurchaseOrder', on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'reorder_requests'
        ordering = ['-priority', 'generated_date']
    
    def __str__(self):
        return f"Reorder: {self.product.name} - {self.suggested_quantity} units"


class InventoryForecast(models.Model):
    """Inventory demand forecasting"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='forecasts')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True)
    
    forecast_date = models.DateField()
    forecast_quantity = models.IntegerField()
    confidence_level = models.DecimalField(max_digits=5, decimal_places=2, default=80)
    
    # Based on historical data
    historical_avg = models.IntegerField()
    trend_factor = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    seasonal_factor = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    
    # For ML model tracking
    model_version = models.CharField(max_length=50, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'inventory_forecasts'
        unique_together = ['product', 'variant', 'forecast_date']
        ordering = ['forecast_date']
    
    def __str__(self):
        return f"{self.product.name} - {self.forecast_date}: {self.forecast_quantity}"