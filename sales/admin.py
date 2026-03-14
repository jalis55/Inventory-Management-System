from django.contrib import admin
from .models import (
    SalesOrder, SalesOrderItem, SalesPayment, 
    SalesReturn, SalesReturnItem, Invoice,
    Quotation, QuotationItem
)

class SalesOrderItemInline(admin.TabularInline):
    model = SalesOrderItem
    extra = 1
    raw_id_fields = ['product', 'variant']
    readonly_fields = ['subtotal', 'discount_amount', 'tax_amount', 'total']

class SalesPaymentInline(admin.TabularInline):
    model = SalesPayment
    extra = 0
    readonly_fields = ['receipt_number', 'created_at']

class SalesReturnInline(admin.TabularInline):
    model = SalesReturn
    extra = 0
    readonly_fields = ['return_number', 'return_date']

@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'invoice_number', 'customer', 'order_date',
        'order_status', 'payment_status', 'total_amount', 'due_amount'
    ]
    list_filter = ['order_status', 'payment_status', 'order_date', 'payment_method']
    search_fields = ['order_number', 'invoice_number', 'customer__first_name', 'customer__last_name']
    readonly_fields = ['order_number', 'invoice_number', 'subtotal', 'discount_amount', 
                      'tax_amount', 'total_amount', 'paid_amount', 'due_amount', 
                      'created_at', 'updated_at']
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'invoice_number', 'customer', 'sales_person', 'order_date')
        }),
        ('Status', {
            'fields': ('order_status', 'payment_status', 'delivery_date', 'expected_delivery_date')
        }),
        ('Financial', {
            'fields': ('subtotal', 'discount_type', 'discount_value', 'discount_amount',
                      'tax_type', 'tax_amount', 'shipping_charge', 'other_charges',
                      'total_amount', 'paid_amount', 'due_amount')
        }),
        ('Payment', {
            'fields': ('payment_method', 'payment_terms')
        }),
        ('Addresses', {
            'fields': ('shipping_address', 'billing_address')
        }),
        ('Notes', {
            'fields': ('customer_notes', 'staff_notes', 'terms_conditions')
        }),
        ('Tracking', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at')
        }),
    )
    
    inlines = [SalesOrderItemInline, SalesPaymentInline, SalesReturnInline]
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        else:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ['quotation_number', 'customer', 'quotation_date', 'valid_until', 'status', 'total_amount']
    list_filter = ['status', 'quotation_date']
    search_fields = ['quotation_number', 'customer__first_name', 'customer__last_name']
    readonly_fields = ['quotation_number', 'subtotal', 'discount_amount', 'tax_amount', 'total_amount', 'created_at']

class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1
    raw_id_fields = ['product', 'variant']

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'sales_order', 'invoice_date', 'due_date', 'status', 'grand_total']
    list_filter = ['status', 'invoice_date']
    search_fields = ['invoice_number', 'sales_order__order_number']
    readonly_fields = ['invoice_number', 'invoice_date']