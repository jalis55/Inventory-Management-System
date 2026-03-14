from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from customers.models import Customer
from suppliers.models import Supplier
from sales.models import SalesOrder, SalesPayment
from purchases.models import PurchaseOrder, PurchasePayment
import uuid
from datetime import timedelta
from django.utils import timezone

User = get_user_model()

class DuesSummary(models.Model):
    """Real-time dues summary for customers and suppliers"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # For Customers (Receivables)
    total_customer_outstanding = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_customer_overdue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    customer_count_with_dues = models.IntegerField(default=0)
    
    # For Suppliers (Payables)
    total_supplier_outstanding = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_supplier_overdue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    supplier_count_with_dues = models.IntegerField(default=0)
    
    # Net position
    net_receivable = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'dues_summary'
        verbose_name_plural = 'Dues Summaries'
    
    def __str__(self):
        return f"Dues Summary - {self.last_updated.date()}"


class CustomerDue(models.Model):
    """Individual customer dues tracking"""
    DUE_STATUS = (
        ('current', 'Current'),
        ('overdue', 'Overdue'),
        ('partially_paid', 'Partially Paid'),
        ('paid', 'Paid'),
        ('written_off', 'Written Off'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='dues')
    sales_order = models.OneToOneField(SalesOrder, on_delete=models.CASCADE, related_name='due')
    
    # Due details
    due_date = models.DateField()
    original_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Status
    status = models.CharField(max_length=20, choices=DUE_STATUS, default='current')
    days_overdue = models.IntegerField(default=0)
    
    # Payment tracking
    last_payment_date = models.DateField(null=True, blank=True)
    last_payment_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Reminders
    reminder_count = models.IntegerField(default=0)
    last_reminder_sent = models.DateField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_customer_dues')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_customer_dues')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customer_dues'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['customer', 'status']),
        ]
        ordering = ['due_date']
    
    def __str__(self):
        return f"{self.customer.get_full_name} - {self.sales_order.order_number} - Due: {self.remaining_amount}"
    
    def save(self, *args, **kwargs):
        self.remaining_amount = self.original_amount - self.paid_amount
        
        # Calculate days overdue
        if self.status == 'written_off':
            self.days_overdue = 0
        elif self.due_date < timezone.now().date() and self.remaining_amount > 0:
            self.days_overdue = (timezone.now().date() - self.due_date).days
            self.status = 'overdue'
        elif self.remaining_amount <= 0:
            self.status = 'paid'
            self.days_overdue = 0
        elif self.paid_amount > 0:
            self.status = 'partially_paid'
        else:
            self.status = 'current'
            self.days_overdue = 0
        
        super().save(*args, **kwargs)


class SupplierDue(models.Model):
    """Individual supplier dues tracking"""
    DUE_STATUS = (
        ('current', 'Current'),
        ('overdue', 'Overdue'),
        ('partially_paid', 'Partially Paid'),
        ('paid', 'Paid'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='dues')
    purchase_order = models.OneToOneField(PurchaseOrder, on_delete=models.CASCADE, related_name='due')
    
    # Due details
    due_date = models.DateField()
    original_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Status
    status = models.CharField(max_length=20, choices=DUE_STATUS, default='current')
    days_overdue = models.IntegerField(default=0)
    
    # Payment tracking
    last_payment_date = models.DateField(null=True, blank=True)
    last_payment_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Reminders
    reminder_count = models.IntegerField(default=0)
    last_reminder_sent = models.DateField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_supplier_dues')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_supplier_dues')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'supplier_dues'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['supplier', 'status']),
        ]
        ordering = ['due_date']
    
    def __str__(self):
        return f"{self.supplier.company_name} - {self.purchase_order.po_number} - Due: {self.remaining_amount}"
    
    def save(self, *args, **kwargs):
        self.remaining_amount = self.original_amount - self.paid_amount
        
        # Calculate days overdue
        if self.due_date < timezone.now().date() and self.remaining_amount > 0:
            self.days_overdue = (timezone.now().date() - self.due_date).days
            self.status = 'overdue'
        elif self.remaining_amount <= 0:
            self.status = 'paid'
            self.days_overdue = 0
        elif self.paid_amount > 0:
            self.status = 'partially_paid'
        else:
            self.status = 'current'
            self.days_overdue = 0
        
        super().save(*args, **kwargs)


class PaymentCollection(models.Model):
    """Record of payment collections from customers"""
    PAYMENT_METHODS = (
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
        ('upi', 'UPI'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collection_number = models.CharField(max_length=50, unique=True)
    customer_due = models.ForeignKey(CustomerDue, on_delete=models.CASCADE, related_name='collections')
    
    collection_date = models.DateField(auto_now_add=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    
    # Payment reference
    reference_number = models.CharField(max_length=100, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    
    # Receipt
    receipt_number = models.CharField(max_length=50, unique=True)
    receipt_generated = models.BooleanField(default=False)
    
    # Notes
    notes = models.TextField(blank=True)
    
    collected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'payment_collections'
        ordering = ['-collection_date']
    
    def __str__(self):
        return f"Collection {self.collection_number} - {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.collection_number:
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(10000, 99999)
            self.collection_number = f"COL-{year}{month}-{random_num}"
        
        if not self.receipt_number:
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(1000, 9999)
            self.receipt_number = f"REC-{year}{month}-{random_num}"
        
        super().save(*args, **kwargs)


class PaymentDisbursement(models.Model):
    """Record of payments made to suppliers"""
    PAYMENT_METHODS = (
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    disbursement_number = models.CharField(max_length=50, unique=True)
    supplier_due = models.ForeignKey(SupplierDue, on_delete=models.CASCADE, related_name='disbursements')
    
    disbursement_date = models.DateField(auto_now_add=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    
    # Payment reference
    reference_number = models.CharField(max_length=100, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    cheque_number = models.CharField(max_length=50, blank=True)
    
    # Voucher
    voucher_number = models.CharField(max_length=50, unique=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    disbursed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'payment_disbursements'
        ordering = ['-disbursement_date']
    
    def __str__(self):
        return f"Disbursement {self.disbursement_number} - {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.disbursement_number:
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(10000, 99999)
            self.disbursement_number = f"DIS-{year}{month}-{random_num}"
        
        if not self.voucher_number:
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(1000, 9999)
            self.voucher_number = f"VCH-{year}{month}-{random_num}"
        
        super().save(*args, **kwargs)


class DueReminder(models.Model):
    """Reminders sent for overdue dues"""
    REMINDER_TYPE = (
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
        ('phone', 'Phone Call'),
    )
    
    REMINDER_STATUS = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # For customer dues
    customer_due = models.ForeignKey(CustomerDue, on_delete=models.CASCADE, null=True, blank=True, related_name='reminders')
    # For supplier dues
    supplier_due = models.ForeignKey(SupplierDue, on_delete=models.CASCADE, null=True, blank=True, related_name='reminders')
    
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPE)
    reminder_date = models.DateField(auto_now_add=True)
    scheduled_date = models.DateField()
    
    # Content
    subject = models.CharField(max_length=200)
    message = models.TextField()
    
    # Status
    status = models.CharField(max_length=20, choices=REMINDER_STATUS, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Response (if any)
    response_received = models.BooleanField(default=False)
    response_notes = models.TextField(blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'due_reminders'
        ordering = ['-scheduled_date']
    
    def __str__(self):
        if self.customer_due:
            return f"Reminder for {self.customer_due.customer.get_full_name} - {self.reminder_type}"
        return f"Reminder for {self.supplier_due.supplier.company_name} - {self.reminder_type}"


class WriteOff(models.Model):
    """Write off bad debts"""
    WRITE_OFF_REASONS = (
        ('bankrupt', 'Customer Bankrupt'),
        ('unreachable', 'Customer Unreachable'),
        ('disputed', 'Disputed Amount'),
        ('time_barred', 'Time Barred'),
        ('other', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    write_off_number = models.CharField(max_length=50, unique=True)
    
    # Which due to write off
    customer_due = models.ForeignKey(CustomerDue, on_delete=models.CASCADE, related_name='write_offs')
    
    write_off_date = models.DateField(auto_now_add=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=20, choices=WRITE_OFF_REASONS)
    
    # Approval
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_write_offs')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Notes
    notes = models.TextField()
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_write_offs')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'write_offs'
    
    def __str__(self):
        return f"Write Off {self.write_off_number} - {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.write_off_number:
            import random
            import datetime
            year = datetime.datetime.now().strftime('%y')
            month = datetime.datetime.now().strftime('%m')
            random_num = random.randint(1000, 9999)
            self.write_off_number = f"WO-{year}{month}-{random_num}"
        super().save(*args, **kwargs)
