from django.contrib import admin
from .models import (
    PurchaseOrder, PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem,
    PurchasePayment, PurchaseReturn, PurchaseReturnItem, SupplierInvoice
)

class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1
    raw_id_fields = ['product', 'variant']
    readonly_fields = ['subtotal', 'discount_amount', 'tax_amount', 'total']

class PurchasePaymentInline(admin.TabularInline):
    model = PurchasePayment
    extra = 0
    readonly_fields = ['voucher_number', 'created_at']

class PurchaseReturnInline(admin.TabularInline):
    model = PurchaseReturn
    extra = 0
    readonly_fields = ['return_number', 'return_date']

class GoodsReceiptInline(admin.TabularInline):
    model = GoodsReceipt
    extra = 0
    readonly_fields = ['grn_number', 'receipt_date']

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = [
        'po_number', 'supplier', 'order_date', 'expected_delivery_date',
        'order_status', 'payment_status', 'total_amount', 'due_amount'
    ]
    list_filter = ['order_status', 'payment_status', 'order_date']
    search_fields = ['po_number', 'supplier__company_name']
    readonly_fields = [
        'po_number', 'subtotal', 'discount_amount', 'tax_amount',
        'total_amount', 'paid_amount', 'due_amount', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('po_number', 'supplier', 'requested_by', 'approved_by')
        }),
        ('Dates', {
            'fields': ('order_date', 'expected_delivery_date', 'delivery_date')
        }),
        ('Status', {
            'fields': ('order_status', 'payment_status')
        }),
        ('Financial', {
            'fields': ('subtotal', 'discount_type', 'discount_value', 'discount_amount',
                      'tax_type', 'tax_amount', 'shipping_charge', 'other_charges',
                      'total_amount', 'paid_amount', 'due_amount')
        }),
        ('Payment', {
            'fields': ('payment_terms',)
        }),
        ('Notes', {
            'fields': ('notes', 'terms_conditions')
        }),
        ('Tracking', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at')
        }),
    )
    
    inlines = [PurchaseOrderItemInline, PurchasePaymentInline, PurchaseReturnInline, GoodsReceiptInline]
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        else:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)

class GoodsReceiptItemInline(admin.TabularInline):
    model = GoodsReceiptItem
    extra = 1
    readonly_fields = ['accepted_quantity']

@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = ['grn_number', 'purchase_order', 'receipt_date', 'received_by', 'status']
    list_filter = ['status', 'receipt_date']
    search_fields = ['grn_number', 'purchase_order__po_number']
    readonly_fields = ['grn_number', 'receipt_date']
    
    inlines = [GoodsReceiptItemInline]

@admin.register(PurchasePayment)
class PurchasePaymentAdmin(admin.ModelAdmin):
    list_display = ['voucher_number', 'purchase_order', 'payment_date', 'amount', 'payment_method', 'status']
    list_filter = ['payment_method', 'status', 'payment_date']
    search_fields = ['voucher_number', 'purchase_order__po_number', 'reference_number']
    readonly_fields = ['voucher_number', 'created_at']

@admin.register(PurchaseReturn)
class PurchaseReturnAdmin(admin.ModelAdmin):
    list_display = ['return_number', 'purchase_order', 'return_date', 'reason', 'status', 'refund_amount']
    list_filter = ['status', 'reason', 'return_date']
    search_fields = ['return_number', 'purchase_order__po_number']
    readonly_fields = ['return_number', 'return_date']

class PurchaseReturnItemInline(admin.TabularInline):
    model = PurchaseReturnItem
    extra = 1

@admin.register(SupplierInvoice)
class SupplierInvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'supplier', 'invoice_date', 'due_date', 'total_amount', 'status']
    list_filter = ['status', 'invoice_date']
    search_fields = ['invoice_number', 'supplier__company_name', 'purchase_order__po_number']
    readonly_fields = ['created_at']