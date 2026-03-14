from django.contrib import admin
from .models import (
    Warehouse, Stock, Batch, SerialNumber,
    StockTransfer, StockTransferItem,
    StockAdjustment, StockAdjustmentItem,
    CycleCount, CycleCountItem,
    ReorderRequest, InventoryForecast
)

class StockTransferItemInline(admin.TabularInline):
    model = StockTransferItem
    extra = 1
    raw_id_fields = ['product', 'variant']

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'type', 'city', 'state', 'is_active']
    list_filter = ['type', 'is_active', 'state']
    search_fields = ['code', 'name', 'city']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['warehouse', 'product', 'quantity', 'reserved_quantity', 
                   'available_quantity', 'reorder_point', 'is_low_stock']
    list_filter = ['warehouse', 'is_active']
    search_fields = ['product__name', 'product__sku']
    readonly_fields = ['available_quantity', 'created_at', 'updated_at']

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ['batch_number', 'product', 'warehouse', 'current_quantity', 
                   'manufacturing_date', 'expiry_date', 'status', 'days_until_expiry']
    list_filter = ['status', 'warehouse']
    search_fields = ['batch_number', 'product__name']
    readonly_fields = ['batch_number', 'status', 'days_until_expiry']

@admin.register(SerialNumber)
class SerialNumberAdmin(admin.ModelAdmin):
    list_display = ['serial_number', 'product', 'warehouse', 'status', 'sold_to']
    list_filter = ['status', 'warehouse']
    search_fields = ['serial_number', 'product__name']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = ['transfer_number', 'from_warehouse', 'to_warehouse', 
                   'transfer_date', 'status', 'requested_by']
    list_filter = ['status', 'transfer_date']
    search_fields = ['transfer_number']
    readonly_fields = ['transfer_number', 'transfer_date', 'created_at']
    inlines = [StockTransferItemInline]

class StockAdjustmentItemInline(admin.TabularInline):
    model = StockAdjustmentItem
    extra = 1
    readonly_fields = ['difference', 'cost_impact']

@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ['adjustment_number', 'warehouse', 'adjustment_type', 
                   'adjustment_date', 'status', 'total_cost_impact']
    list_filter = ['status', 'adjustment_type', 'adjustment_date']
    search_fields = ['adjustment_number']
    readonly_fields = ['adjustment_number', 'adjustment_date', 'total_cost_impact', 'created_at']
    inlines = [StockAdjustmentItemInline]

class CycleCountItemInline(admin.TabularInline):
    model = CycleCountItem
    extra = 1
    readonly_fields = ['difference', 'has_discrepancy']

@admin.register(CycleCount)
class CycleCountAdmin(admin.ModelAdmin):
    list_display = ['count_number', 'warehouse', 'scheduled_date', 'status', 
                   'counted_by', 'items_counted', 'total_items', 'discrepancy_value']
    list_filter = ['status', 'scheduled_date']
    search_fields = ['count_number']
    readonly_fields = ['count_number', 'total_items', 'items_counted', 
                      'items_matched', 'items_discrepancy', 'discrepancy_value']
    inlines = [CycleCountItemInline]

@admin.register(ReorderRequest)
class ReorderRequestAdmin(admin.ModelAdmin):
    list_display = ['product', 'warehouse', 'current_stock', 'suggested_quantity', 
                   'priority', 'status', 'generated_date']
    list_filter = ['priority', 'status', 'generated_date']
    search_fields = ['product__name']

@admin.register(InventoryForecast)
class InventoryForecastAdmin(admin.ModelAdmin):
    list_display = ['product', 'forecast_date', 'forecast_quantity', 'confidence_level']
    list_filter = ['forecast_date']
    search_fields = ['product__name']