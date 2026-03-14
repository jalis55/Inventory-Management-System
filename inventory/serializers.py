from rest_framework import serializers
from .models import (
    Warehouse, Stock, Batch, SerialNumber,
    StockTransfer, StockTransferItem,
    StockAdjustment, StockAdjustmentItem,
    CycleCount, CycleCountItem,
    ReorderRequest, InventoryForecast
)
from products.serializers import ProductListSerializer, ProductVariantSerializer

class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = '__all__'
        read_only_fields = ['id', 'code', 'created_at', 'updated_at']

class WarehouseListSerializer(serializers.ModelSerializer):
    stock_value = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Warehouse
        fields = ['id', 'code', 'name', 'type', 'city', 'state', 'is_active', 'stock_value', 'item_count']
    
    def get_stock_value(self, obj):
        # Calculate total stock value in this warehouse
        from django.db.models import Sum, F
        total = obj.stock_items.aggregate(
            total=Sum(F('quantity') * F('product__cost_price'))
        )['total']
        return total or 0
    
    def get_item_count(self, obj):
        return obj.stock_items.filter(quantity__gt=0).count()

class StockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    
    class Meta:
        model = Stock
        fields = '__all__'
        read_only_fields = ['id', 'available_quantity', 'created_at', 'updated_at']

class BatchSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    days_until_expiry = serializers.ReadOnlyField()
    
    class Meta:
        model = Batch
        fields = '__all__'
        read_only_fields = ['id', 'batch_number', 'status', 'created_at']

class SerialNumberSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    
    class Meta:
        model = SerialNumber
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

# Stock Transfer Serializers
class StockTransferItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    
    class Meta:
        model = StockTransferItem
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

class StockTransferSerializer(serializers.ModelSerializer):
    items = StockTransferItemSerializer(many=True, read_only=True)
    from_warehouse_name = serializers.CharField(source='from_warehouse.name', read_only=True)
    to_warehouse_name = serializers.CharField(source='to_warehouse.name', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    
    class Meta:
        model = StockTransfer
        fields = '__all__'
        read_only_fields = ['id', 'transfer_number', 'transfer_date', 'created_at', 'updated_at']

class StockTransferCreateSerializer(serializers.ModelSerializer):
    items = serializers.ListField(child=serializers.DictField(), write_only=True)
    
    class Meta:
        model = StockTransfer
        fields = [
            'from_warehouse', 'to_warehouse', 'expected_delivery',
            'reference_number', 'vehicle_number', 'driver_name',
            'driver_phone', 'notes', 'items'
        ]
    
    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required")
        return value

# Stock Adjustment Serializers
class StockAdjustmentItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    
    class Meta:
        model = StockAdjustmentItem
        fields = '__all__'
        read_only_fields = ['id', 'difference', 'cost_impact', 'created_at']

class StockAdjustmentSerializer(serializers.ModelSerializer):
    items = StockAdjustmentItemSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = StockAdjustment
        fields = '__all__'
        read_only_fields = ['id', 'adjustment_number', 'adjustment_date', 'total_cost_impact', 'created_at']

class StockAdjustmentCreateSerializer(serializers.ModelSerializer):
    items = serializers.ListField(child=serializers.DictField(), write_only=True)
    
    class Meta:
        model = StockAdjustment
        fields = ['warehouse', 'adjustment_type', 'reason', 'items']
    
    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required")
        return value

# Cycle Count Serializers
class CycleCountItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    
    class Meta:
        model = CycleCountItem
        fields = '__all__'
        read_only_fields = ['id', 'difference', 'has_discrepancy', 'created_at']

class CycleCountSerializer(serializers.ModelSerializer):
    items = CycleCountItemSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    counted_by_name = serializers.CharField(source='counted_by.get_full_name', read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.get_full_name', read_only=True)
    
    class Meta:
        model = CycleCount
        fields = '__all__'
        read_only_fields = [
            'id', 'count_number', 'total_items', 'items_counted',
            'items_matched', 'items_discrepancy', 'discrepancy_value',
            'created_at'
        ]

class CycleCountCreateSerializer(serializers.ModelSerializer):
    items = serializers.ListField(child=serializers.DictField(), write_only=True)
    
    class Meta:
        model = CycleCount
        fields = ['warehouse', 'scheduled_date', 'zone', 'category', 'notes', 'items']

class CycleCountUpdateSerializer(serializers.Serializer):
    """For updating counted quantities"""
    item_id = serializers.UUIDField()
    counted_quantity = serializers.IntegerField(min_value=0)
    bin_location = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

# Reorder Request Serializers
class ReorderRequestSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    supplier_name = serializers.CharField(source='suggested_supplier.company_name', read_only=True)
    
    class Meta:
        model = ReorderRequest
        fields = '__all__'
        read_only_fields = ['id', 'generated_date', 'created_at']

# Inventory Forecast Serializer
class InventoryForecastSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = InventoryForecast
        fields = '__all__'
        read_only_fields = ['id', 'created_at']