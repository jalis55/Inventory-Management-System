from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from products.models import Product, ProductVariant
from customers.models import Customer
import uuid

User = get_user_model()

class SalesOrder(models.Model):
    """Main Sales Order Model"""
    ORDER_STATUS = (
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    )
    
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('refunded', 'Refunded'),
    )
    
    PAYMENT_METHODS = (
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
        ('upi', 'UPI'),
        ('credit', 'Credit'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=50, unique=True)
    invoice_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    
    # Relationships
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='sales_orders')
    sales_person = models.ForeignKey(User, on_delete=models.PROTECT, related_name='sales_orders')
    
    # Order Details
    order_date = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateField(null=True, blank=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    
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
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, null=True, blank=True)
    payment_terms = models.CharField(max_length=100, blank=True)
    
    # Shipping
    shipping_address = models.TextField()
    billing_address = models.TextField()
    
    # Notes
    customer_notes = models.TextField(blank=True)
    staff_notes = models.TextField(blank=True)
    terms_conditions = models.TextField(blank=True)
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_sales_orders')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_sales_orders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sales_orders'
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['order_date']),
            models.Index(fields=['order_status']),
            models.Index(fields=['payment_status']),
        ]
        ordering = ['-order_date']
    
    def __str__(self):
        return f"Order {self.order_number} - {self.customer.get_full_name}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate order number
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(10000, 99999)
            self.order_number = f"SO-{year}{month}-{random_num}"
        
        if not self.invoice_number and self.order_status == 'confirmed':
            # Generate invoice number when order is confirmed
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(1000, 9999)
            self.invoice_number = f"INV-{year}{month}-{random_num}"
        
        super().save(*args, **kwargs)
    
    @property
    def is_fully_paid(self):
        return self.paid_amount >= self.total_amount
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.payment_status not in ['paid', 'refunded'] and self.expected_delivery_date:
            return timezone.now().date() > self.expected_delivery_date
        return False


class SalesOrderItem(models.Model):
    """Individual items in a sales order"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='items')
    
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sales_items')
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, null=True, blank=True, related_name='sales_items')
    
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
    
    # Status
    delivered_quantity = models.IntegerField(default=0)
    returned_quantity = models.IntegerField(default=0)
    
    # Notes
    notes = models.CharField(max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sales_order_items'
    
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


class SalesPayment(models.Model):
    """Payments received for sales orders"""
    PAYMENT_METHODS = (
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
        ('upi', 'UPI'),
    )
    
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='payments')
    
    payment_date = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    # Payment details
    reference_number = models.CharField(max_length=100, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=200, blank=True)
    cheque_number = models.CharField(max_length=50, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    
    # For card payments
    card_last_four = models.CharField(max_length=4, blank=True)
    card_type = models.CharField(max_length=50, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Receipt
    receipt_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'sales_payments'
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Payment {self.receipt_number} - {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(10000, 99999)
            self.receipt_number = f"RCP-{year}{month}-{random_num}"
        super().save(*args, **kwargs)


class SalesReturn(models.Model):
    """Sales returns/refunds"""
    RETURN_REASONS = (
        ('damaged', 'Damaged Product'),
        ('defective', 'Defective Product'),
        ('wrong_item', 'Wrong Item Delivered'),
        ('customer_not_satisfied', 'Customer Not Satisfied'),
        ('exchange', 'Exchange'),
        ('other', 'Other'),
    )
    
    RETURN_STATUS = (
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name='returns')
    return_number = models.CharField(max_length=50, unique=True)
    
    # Return details
    return_date = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=50, choices=RETURN_REASONS)
    status = models.CharField(max_length=20, choices=RETURN_STATUS, default='requested')
    
    # Financial
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2)
    refund_method = models.CharField(max_length=20, choices=SalesPayment.PAYMENT_METHODS, null=True, blank=True)
    refund_transaction_id = models.CharField(max_length=100, blank=True)
    
    # Notes
    customer_notes = models.TextField(blank=True)
    staff_notes = models.TextField(blank=True)
    
    # Approval
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_returns')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_returns')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sales_returns'
        ordering = ['-return_date']
    
    def __str__(self):
        return f"Return {self.return_number} - {self.sales_order.order_number}"
    
    def save(self, *args, **kwargs):
        if not self.return_number:
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(1000, 9999)
            self.return_number = f"RET-{year}{month}-{random_num}"
        super().save(*args, **kwargs)


class SalesReturnItem(models.Model):
    """Items in a sales return"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sales_return = models.ForeignKey(SalesReturn, on_delete=models.CASCADE, related_name='items')
    order_item = models.ForeignKey(SalesOrderItem, on_delete=models.PROTECT, related_name='return_items')
    
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    condition = models.CharField(
        max_length=20,
        choices=[('new', 'New'), ('used', 'Used'), ('damaged', 'Damaged')],
        default='new'
    )
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'sales_return_items'
    
    def __str__(self):
        return f"{self.order_item.product.name} x {self.quantity}"


class Invoice(models.Model):
    """Invoice for sales orders"""
    INVOICE_STATUS = (
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sales_order = models.OneToOneField(SalesOrder, on_delete=models.PROTECT, related_name='invoice')
    
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    
    # Invoice details
    status = models.CharField(max_length=20, choices=INVOICE_STATUS, default='draft')
    
    # GST details (for India)
    gst_type = models.CharField(
        max_length=10,
        choices=[('cgst_sgst', 'CGST+SGST'), ('igst', 'IGST')],
        default='cgst_sgst'
    )
    
    # Company details (from settings)
    company_name = models.CharField(max_length=200)
    company_address = models.TextField()
    company_gst = models.CharField(max_length=20)
    company_pan = models.CharField(max_length=20)
    company_email = models.EmailField()
    company_phone = models.CharField(max_length=20)
    
    # Customer details (snapshot at invoice time)
    customer_name = models.CharField(max_length=200)
    customer_address = models.TextField()
    customer_gst = models.CharField(max_length=20, blank=True)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)
    
    # Financial summary
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_total = models.DecimalField(max_digits=10, decimal_places=2)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Amount in words
    amount_in_words = models.CharField(max_length=500)
    
    # QR Code for UPI payments
    qr_code = models.ImageField(upload_to='invoices/qr/', null=True, blank=True)
    
    # PDF
    pdf_file = models.FileField(upload_to='invoices/pdf/', null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'invoices'
        ordering = ['-invoice_date']
    
    def __str__(self):
        return f"Invoice {self.invoice_number}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(1000, 9999)
            self.invoice_number = f"INV-{year}{month}-{random_num}"
        super().save(*args, **kwargs)


class Quotation(models.Model):
    """Quotations/Estimates for customers"""
    QUOTATION_STATUS = (
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
        ('converted', 'Converted to Order'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quotation_number = models.CharField(max_length=50, unique=True)
    
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='quotations')
    sales_person = models.ForeignKey(User, on_delete=models.PROTECT, related_name='quotations')
    
    quotation_date = models.DateField(auto_now_add=True)
    valid_until = models.DateField()
    
    status = models.CharField(max_length=20, choices=QUOTATION_STATUS, default='draft')
    
    # Financial
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Terms
    terms_conditions = models.TextField(blank=True)
    customer_notes = models.TextField(blank=True)
    staff_notes = models.TextField(blank=True)
    
    # Converted to order
    converted_to_order = models.ForeignKey(SalesOrder, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_quotations')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_quotations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'quotations'
        ordering = ['-quotation_date']
    
    def __str__(self):
        return f"Quotation {self.quotation_number} - {self.customer.get_full_name}"
    
    def save(self, *args, **kwargs):
        if not self.quotation_number:
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(1000, 9999)
            self.quotation_number = f"QTN-{year}{month}-{random_num}"
        super().save(*args, **kwargs)


class QuotationItem(models.Model):
    """Items in a quotation"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='items')
    
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, null=True, blank=True)
    
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    
    notes = models.CharField(max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'quotation_items'
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        # Calculate totals
        self.subtotal = self.quantity * self.unit_price
        discount = (self.subtotal * self.discount_percent) / 100
        after_discount = self.subtotal - discount
        tax = (after_discount * self.tax_rate) / 100
        self.total = after_discount + tax
        super().save(*args, **kwargs)
