from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from products.models import Product, ProductVariant
from suppliers.models import Supplier
import uuid

User = get_user_model()

class PurchaseOrder(models.Model):
    """Main Purchase Order Model"""
    ORDER_STATUS = (
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('ordered', 'Ordered'),
        ('partially_received', 'Partially Received'),
        ('received', 'Fully Received'),
        ('cancelled', 'Cancelled'),
    )
    
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    po_number = models.CharField(max_length=50, unique=True, verbose_name="PO Number")
    
    # Relationships
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders')
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='requested_purchase_orders')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_purchase_orders')
    
    # Dates
    order_date = models.DateField(auto_now_add=True)
    expected_delivery_date = models.DateField()
    delivery_date = models.DateField(null=True, blank=True)
    
    # Status
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS, default='draft')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    # Financial
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_type = models.CharField(
        max_length=10,
        choices=[('percentage', 'Percentage'), ('fixed', 'Fixed Amount')],
        null=True, blank=True
    )
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    tax_type = models.CharField(
        max_length=10,
        choices=[('inclusive', 'Inclusive'), ('exclusive', 'Exclusive')],
        default='exclusive'
    )
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Payment
    payment_terms = models.CharField(max_length=100, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    terms_conditions = models.TextField(blank=True)
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_purchase_orders')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_purchase_orders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'purchase_orders'
        indexes = [
            models.Index(fields=['po_number']),
            models.Index(fields=['order_date']),
            models.Index(fields=['order_status']),
            models.Index(fields=['payment_status']),
        ]
        ordering = ['-order_date']
    
    def __str__(self):
        return f"PO {self.po_number} - {self.supplier.company_name}"
    
    def save(self, *args, **kwargs):
        if not self.po_number:
            # Generate PO number
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(10000, 99999)
            self.po_number = f"PO-{year}{month}-{random_num}"
        super().save(*args, **kwargs)
    
    @property
    def is_fully_paid(self):
        return self.paid_amount >= self.total_amount
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.payment_status not in ['paid'] and self.expected_delivery_date:
            return timezone.now().date() > self.expected_delivery_date
        return False


class PurchaseOrderItem(models.Model):
    """Individual items in a purchase order"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='purchase_items')
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, null=True, blank=True, related_name='purchase_items')
    
    # Item details
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Pricing
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)  # Before discount
    total = models.DecimalField(max_digits=12, decimal_places=2)     # After discount and tax
    
    # Receiving
    received_quantity = models.IntegerField(default=0)
    rejected_quantity = models.IntegerField(default=0)
    
    # Notes
    notes = models.CharField(max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'purchase_order_items'
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        # Calculate totals
        self.subtotal = self.quantity * self.unit_price
        self.discount_amount = (self.subtotal * self.discount_percent) / 100
        after_discount = self.subtotal - self.discount_amount
        self.tax_amount = (after_discount * self.tax_rate) / 100
        self.total = after_discount + self.tax_amount
        super().save(*args, **kwargs)


class GoodsReceipt(models.Model):
    """Goods receipt notes for received items"""
    RECEIPT_STATUS = (
        ('pending', 'Pending'),
        ('partial', 'Partially Received'),
        ('completed', 'Completed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grn_number = models.CharField(max_length=50, unique=True, verbose_name="GRN Number")
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='goods_receipts')
    
    receipt_date = models.DateField(auto_now_add=True)
    received_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='goods_receipts')
    
    status = models.CharField(max_length=20, choices=RECEIPT_STATUS, default='pending')
    
    # Invoice details from supplier
    supplier_invoice_number = models.CharField(max_length=100, blank=True)
    supplier_invoice_date = models.DateField(null=True, blank=True)
    
    # Transport details
    transport_mode = models.CharField(max_length=50, blank=True)
    vehicle_number = models.CharField(max_length=50, blank=True)
    driver_name = models.CharField(max_length=100, blank=True)
    driver_phone = models.CharField(max_length=20, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'goods_receipts'
        ordering = ['-receipt_date']
    
    def __str__(self):
        return f"GRN {self.grn_number} - PO {self.purchase_order.po_number}"
    
    def save(self, *args, **kwargs):
        if not self.grn_number:
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(10000, 99999)
            self.grn_number = f"GRN-{year}{month}-{random_num}"
        super().save(*args, **kwargs)


class GoodsReceiptItem(models.Model):
    """Items in a goods receipt"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    goods_receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name='items')
    purchase_order_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.PROTECT, related_name='receipt_items')
    
    ordered_quantity = models.IntegerField()
    received_quantity = models.IntegerField(validators=[MinValueValidator(0)])
    rejected_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    accepted_quantity = models.IntegerField()
    
    # Quality check
    quality_status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('passed', 'Passed'), ('failed', 'Failed')],
        default='pending'
    )
    quality_notes = models.TextField(blank=True)
    
    # Batch/Expiry for perishable items
    batch_number = models.CharField(max_length=100, blank=True)
    manufacturing_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Location
    storage_location = models.CharField(max_length=100, blank=True)
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'goods_receipt_items'
    
    def __str__(self):
        return f"{self.purchase_order_item.product.name} - Received: {self.accepted_quantity}"
    
    def save(self, *args, **kwargs):
        self.accepted_quantity = self.received_quantity - self.rejected_quantity
        super().save(*args, **kwargs)


class PurchasePayment(models.Model):
    """Payments made to suppliers for purchase orders"""
    PAYMENT_METHODS = (
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
    )
    
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='payments')
    
    payment_date = models.DateField(auto_now_add=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    # Payment details
    reference_number = models.CharField(max_length=100, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=200, blank=True)
    cheque_number = models.CharField(max_length=50, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Payment voucher
    voucher_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    
    paid_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='purchase_payments_made')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'purchase_payments'
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Payment {self.voucher_number} - {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.voucher_number:
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(10000, 99999)
            self.voucher_number = f"PMT-{year}{month}-{random_num}"
        super().save(*args, **kwargs)


class PurchaseReturn(models.Model):
    """Returns to suppliers"""
    RETURN_REASONS = (
        ('damaged', 'Damaged Goods'),
        ('defective', 'Defective Products'),
        ('wrong_item', 'Wrong Item Delivered'),
        ('expired', 'Expired'),
        ('quality_issues', 'Quality Issues'),
        ('other', 'Other'),
    )
    
    RETURN_STATUS = (
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('shipped', 'Shipped Back'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    return_number = models.CharField(max_length=50, unique=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='returns')
    
    return_date = models.DateField(auto_now_add=True)
    reason = models.CharField(max_length=50, choices=RETURN_REASONS)
    status = models.CharField(max_length=20, choices=RETURN_STATUS, default='requested')
    
    # Financial
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refund_method = models.CharField(max_length=20, choices=PurchasePayment.PAYMENT_METHODS, null=True, blank=True)
    refund_received = models.BooleanField(default=False)
    refund_date = models.DateField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Approval
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_purchase_returns')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_purchase_returns')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'purchase_returns'
        ordering = ['-return_date']
    
    def __str__(self):
        return f"Return {self.return_number} - PO {self.purchase_order.po_number}"
    
    def save(self, *args, **kwargs):
        if not self.return_number:
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(1000, 9999)
            self.return_number = f"PR-{year}{month}-{random_num}"
        super().save(*args, **kwargs)


class PurchaseReturnItem(models.Model):
    """Items in a purchase return"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_return = models.ForeignKey(PurchaseReturn, on_delete=models.CASCADE, related_name='items')
    receipt_item = models.ForeignKey(GoodsReceiptItem, on_delete=models.PROTECT, related_name='return_items')
    
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    condition = models.CharField(
        max_length=20,
        choices=[('new', 'New'), ('used', 'Used'), ('damaged', 'Damaged')],
        default='damaged'
    )
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'purchase_return_items'
    
    def __str__(self):
        return f"{self.receipt_item.purchase_order_item.product.name} x {self.quantity}"


class SupplierInvoice(models.Model):
    """Invoices received from suppliers"""
    INVOICE_STATUS = (
        ('pending', 'Pending'),
        ('matched', 'Matched with PO'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('disputed', 'Disputed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='invoices')
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='supplier_invoices')
    
    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateField()
    due_date = models.DateField()
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # File upload
    invoice_file = models.FileField(upload_to='supplier_invoices/', null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=INVOICE_STATUS, default='pending')
    
    # Matching with GRN
    matched_with_grn = models.ForeignKey(GoodsReceipt, on_delete=models.SET_NULL, null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'supplier_invoices'
        unique_together = ['supplier', 'invoice_number']
        ordering = ['-invoice_date']
    
    def __str__(self):
        return f"{self.supplier.company_name} - Invoice {self.invoice_number}"