from django.contrib import admin
from .models import (
    Customer, CustomerAddress, CustomerContact, 
    CustomerInteraction, CustomerLoyalty, CustomerDocument,
    CustomerPayment
)

class CustomerAddressInline(admin.TabularInline):
    model = CustomerAddress
    extra = 1

class CustomerContactInline(admin.TabularInline):
    model = CustomerContact
    extra = 1

class CustomerInteractionInline(admin.TabularInline):
    model = CustomerInteraction
    extra = 0
    readonly_fields = ['created_at']

class CustomerDocumentInline(admin.TabularInline):
    model = CustomerDocument
    extra = 0

class CustomerPaymentInline(admin.TabularInline):
    model = CustomerPayment
    extra = 0
    readonly_fields = ['created_at']

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = [
        'customer_code', 'get_full_name', 'company_name', 
        'customer_type', 'email', 'phone', 'city',
        'outstanding_amount', 'loyalty_tier', 'is_active'
    ]
    list_filter = [
        'customer_type', 'loyalty_tier', 'is_active',
        'payment_terms', 'preferred_communication', 'state'
    ]
    search_fields = [
        'customer_code', 'first_name', 'last_name', 
        'company_name', 'email', 'phone', 'gst_number'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'customer_code', 'customer_type', 'company_name',
                'first_name', 'last_name', 'email', 'phone', 'mobile'
            )
        }),
        ('Address', {
            'fields': (
                'address_line1', 'address_line2', 'city',
                'state', 'postal_code', 'country'
            )
        }),
        ('Business Details', {
            'fields': ('gst_number', 'pan_number', 'tax_id')
        }),
        ('Credit Information', {
            'fields': ('credit_limit', 'outstanding_amount', 'payment_terms')
        }),
        ('Preferences', {
            'fields': ('preferred_communication', 'do_not_disturb', 'notes')
        }),
        ('Loyalty', {
            'fields': ('loyalty_points', 'loyalty_tier')
        }),
        ('Status', {
            'fields': ('is_active', 'profile_image')
        }),
        ('Tracking', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at')
        }),
    )
    
    inlines = [
        CustomerAddressInline, CustomerContactInline,
        CustomerInteractionInline, CustomerDocumentInline,
        CustomerPaymentInline
    ]
    
    def get_full_name(self, obj):
        return obj.get_full_name
    get_full_name.short_description = 'Full Name'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        else:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(CustomerLoyalty)
class CustomerLoyaltyAdmin(admin.ModelAdmin):
    list_display = ['customer', 'tier', 'points', 'lifetime_points', 'lifetime_purchase', 'membership_date']
    list_filter = ['tier']
    search_fields = ['customer__first_name', 'customer__last_name', 'customer__email']
    readonly_fields = ['membership_date', 'last_activity_date']

@admin.register(CustomerPayment)
class CustomerPaymentAdmin(admin.ModelAdmin):
    list_display = ['customer', 'payment_date', 'amount', 'payment_method', 'status', 'reference_number']
    list_filter = ['payment_method', 'status', 'payment_date']
    search_fields = ['customer__first_name', 'customer__last_name', 'reference_number']
    readonly_fields = ['created_at']