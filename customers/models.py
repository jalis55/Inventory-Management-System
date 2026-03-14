from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, EmailValidator
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

class Customer(models.Model):
    """Customer Information"""
    CUSTOMER_TYPES = (
        ('retail', 'Retail Customer'),
        ('wholesale', 'Wholesale Customer'),
        ('corporate', 'Corporate Customer'),
        ('vip', 'VIP Customer'),
    )
    
    PAYMENT_TERMS = (
        ('immediate', 'Immediate'),
        ('net_15', 'Net 15'),
        ('net_30', 'Net 30'),
        ('net_45', 'Net 45'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer_code = models.CharField(max_length=50, unique=True)
    
    # Basic Information
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPES, default='retail')
    company_name = models.CharField(max_length=200, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(validators=[EmailValidator()], unique=True)
    phone = models.CharField(max_length=20)
    mobile = models.CharField(max_length=20, blank=True)
    
    # Address
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='India')
    
    # Business details (for corporate customers)
    gst_number = models.CharField(max_length=20, blank=True, null=True)
    pan_number = models.CharField(max_length=20, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    
    # Credit Information
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outstanding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERMS, default='immediate')
    
    # Loyalty Information
    loyalty_points = models.IntegerField(default=0)
    loyalty_tier = models.CharField(max_length=20, default='bronze')
    
    # Customer Preferences
    preferred_communication = models.CharField(
        max_length=20, 
        choices=[('email', 'Email'), ('sms', 'SMS'), ('phone', 'Phone')],
        default='email'
    )
    do_not_disturb = models.BooleanField(default=False)
    
    # Metadata
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    profile_image = models.ImageField(upload_to='customers/', null=True, blank=True)
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_customers')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_customers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customers'
        indexes = [
            models.Index(fields=['customer_code']),
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        if self.company_name:
            return f"{self.company_name} ({self.get_full_name})"
        return self.get_full_name
    
    @property
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def is_corporate(self):
        return self.customer_type in ['corporate', 'wholesale']
    
    def save(self, *args, **kwargs):
        if not self.customer_code:
            # Generate customer code
            import random
            prefix = self.customer_type[:3].upper()
            random_num = random.randint(10000, 99999)
            self.customer_code = f"CUST-{prefix}-{random_num}"
        super().save(*args, **kwargs)


class CustomerAddress(models.Model):
    """Additional customer addresses"""
    ADDRESS_TYPES = (
        ('shipping', 'Shipping'),
        ('billing', 'Billing'),
        ('both', 'Both'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPES, default='shipping')
    
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='India')
    
    is_default = models.BooleanField(default=False)
    delivery_instructions = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customer_addresses'
        unique_together = ['customer', 'address_type', 'address_line1']
    
    def __str__(self):
        return f"{self.customer.get_full_name} - {self.address_type}"


class CustomerContact(models.Model):
    """Additional customer contacts"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='contacts')
    
    name = models.CharField(max_length=100)
    designation = models.CharField(max_length=100, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    mobile = models.CharField(max_length=20, blank=True)
    
    is_primary = models.BooleanField(default=False)
    department = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customer_contacts'
    
    def __str__(self):
        return f"{self.name} - {self.customer.get_full_name}"


class CustomerInteraction(models.Model):
    """Track customer interactions"""
    INTERACTION_TYPES = (
        ('call', 'Phone Call'),
        ('email', 'Email'),
        ('meeting', 'Meeting'),
        ('support', 'Support Ticket'),
        ('complaint', 'Complaint'),
        ('feedback', 'Feedback'),
        ('other', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='interactions')
    
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPES)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    
    # Interaction details
    contact_person = models.CharField(max_length=100, blank=True)
    duration_minutes = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Outcome
    outcome = models.TextField(blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    
    # For complaints/support
    priority = models.CharField(
        max_length=20,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')],
        default='medium'
    )
    status = models.CharField(
        max_length=20,
        choices=[('open', 'Open'), ('in_progress', 'In Progress'), ('resolved', 'Resolved'), ('closed', 'Closed')],
        default='open'
    )
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customer_interactions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer.get_full_name} - {self.interaction_type} - {self.created_at.date()}"


class CustomerLoyalty(models.Model):
    """Customer loyalty program tracking"""
    TIERS = (
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
        ('diamond', 'Diamond'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='loyalty')
    
    tier = models.CharField(max_length=20, choices=TIERS, default='bronze')
    points = models.IntegerField(default=0)
    lifetime_points = models.IntegerField(default=0)
    lifetime_purchase = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Tier thresholds
    points_to_next_tier = models.IntegerField(default=1000)
    
    # Join date
    membership_date = models.DateField(auto_now_add=True)
    last_activity_date = models.DateField(auto_now=True)
    
    # Referrals
    referral_code = models.CharField(max_length=50, unique=True, blank=True)
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    total_referrals = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'customer_loyalty'
    
    def __str__(self):
        return f"{self.customer.get_full_name} - {self.tier} - {self.points} points"
    
    def save(self, *args, **kwargs):
        if not self.referral_code:
            import random
            import string
            self.referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        super().save(*args, **kwargs)


class CustomerDocument(models.Model):
    """Customer documents (GST, PAN, etc.)"""
    DOCUMENT_TYPES = (
        ('gst', 'GST Certificate'),
        ('pan', 'PAN Card'),
        ('aadhar', 'Aadhar Card'),
        ('business', 'Business Registration'),
        ('other', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='documents')
    
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    document_number = models.CharField(max_length=100)
    document_file = models.FileField(upload_to='customer_documents/')
    
    expiry_date = models.DateField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'customer_documents'
    
    def __str__(self):
        return f"{self.customer.get_full_name} - {self.document_type}"


class CustomerPayment(models.Model):
    """Customer payment history"""
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
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='payments')
    
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    # Payment details
    reference_number = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=200, blank=True)
    cheque_number = models.CharField(max_length=50, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    
    # For invoice linking
    invoice_id = models.UUIDField(null=True, blank=True)
    invoice_number = models.CharField(max_length=50, blank=True)
    
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='received_payments')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'customer_payments'
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"{self.customer.get_full_name} - {self.amount} - {self.payment_date}"