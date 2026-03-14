from django.contrib import admin
from .models import Supplier, SupplierProduct

class SupplierProductInline(admin.TabularInline):
    model = SupplierProduct
    extra = 1
    raw_id_fields = ['product']

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'contact_person', 'email', 'phone', 
                   'city', 'state', 'gst_number', 'outstanding_amount', 
                   'rating', 'is_active']
    list_filter = ['is_active', 'rating', 'payment_terms', 'state', 'country']
    search_fields = ['company_name', 'contact_person', 'email', 'gst_number', 'pan_number']
    inlines = [SupplierProductInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('company_name', 'contact_person', 'email', 'phone', 'mobile', 'website')
        }),
        ('Address', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country')
        }),
        ('Business Details', {
            'fields': ('gst_number', 'pan_number', 'tax_id')
        }),
        ('Payment Information', {
            'fields': ('payment_terms', 'credit_limit', 'outstanding_amount')
        }),
        ('Bank Details', {
            'fields': ('bank_name', 'bank_account', 'bank_ifsc')
        }),
        ('Additional Information', {
            'fields': ('notes', 'rating', 'is_active', 'created_by', 'updated_by')
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        else:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(SupplierProduct)
class SupplierProductAdmin(admin.ModelAdmin):
    list_display = ['supplier', 'product', 'price', 'lead_time_days', 
                   'minimum_order_quantity', 'is_preferred']
    list_filter = ['is_preferred', 'supplier']
    search_fields = ['supplier__company_name', 'product__name', 'supplier_sku']
    raw_id_fields = ['product']