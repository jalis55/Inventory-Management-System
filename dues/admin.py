from django.contrib import admin
from .models import (
    DuesSummary, CustomerDue, SupplierDue,
    PaymentCollection, PaymentDisbursement,
    DueReminder, WriteOff
)

@admin.register(CustomerDue)
class CustomerDueAdmin(admin.ModelAdmin):
    list_display = ['customer', 'sales_order', 'due_date', 'original_amount', 
                   'paid_amount', 'remaining_amount', 'status', 'days_overdue']
    list_filter = ['status', 'due_date']
    search_fields = ['customer__first_name', 'customer__last_name', 'sales_order__order_number']
    readonly_fields = ['days_overdue', 'created_at', 'updated_at']

@admin.register(SupplierDue)
class SupplierDueAdmin(admin.ModelAdmin):
    list_display = ['supplier', 'purchase_order', 'due_date', 'original_amount', 
                   'paid_amount', 'remaining_amount', 'status', 'days_overdue']
    list_filter = ['status', 'due_date']
    search_fields = ['supplier__company_name', 'purchase_order__po_number']
    readonly_fields = ['days_overdue', 'created_at', 'updated_at']

@admin.register(PaymentCollection)
class PaymentCollectionAdmin(admin.ModelAdmin):
    list_display = ['collection_number', 'customer_due', 'collection_date', 
                   'amount', 'payment_method', 'receipt_number']
    list_filter = ['payment_method', 'collection_date']
    search_fields = ['collection_number', 'receipt_number', 'customer_due__customer__first_name']
    readonly_fields = ['collection_number', 'receipt_number', 'created_at']

@admin.register(PaymentDisbursement)
class PaymentDisbursementAdmin(admin.ModelAdmin):
    list_display = ['disbursement_number', 'supplier_due', 'disbursement_date', 
                   'amount', 'payment_method', 'voucher_number']
    list_filter = ['payment_method', 'disbursement_date']
    search_fields = ['disbursement_number', 'voucher_number', 'supplier_due__supplier__company_name']
    readonly_fields = ['disbursement_number', 'voucher_number', 'created_at']

@admin.register(DueReminder)
class DueReminderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer_due', 'supplier_due', 'reminder_type', 
                   'scheduled_date', 'status', 'response_received']
    list_filter = ['reminder_type', 'status', 'scheduled_date']
    readonly_fields = ['created_at']

@admin.register(WriteOff)
class WriteOffAdmin(admin.ModelAdmin):
    list_display = ['write_off_number', 'customer_due', 'write_off_date', 
                   'amount', 'reason', 'approved_by']
    list_filter = ['reason', 'write_off_date']
    search_fields = ['write_off_number', 'customer_due__customer__first_name']
    readonly_fields = ['write_off_number', 'write_off_date', 'created_at']

@admin.register(DuesSummary)
class DuesSummaryAdmin(admin.ModelAdmin):
    list_display = ['id', 'total_customer_outstanding', 'total_supplier_outstanding', 
                   'net_receivable', 'last_updated']
    readonly_fields = ['last_updated']