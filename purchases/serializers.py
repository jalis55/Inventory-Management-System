from rest_framework import serializers
from .models import (
    PurchaseOrder, PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem,
    PurchasePayment, PurchaseReturn, PurchaseReturnItem, SupplierInvoice
)
from products.models import Product
from products.serializers import ProductListSerializer
from suppliers.serializers import SupplierListSerializer

# Purchase Order Item Serializers
class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    
    class Meta:
        model = PurchaseOrderItem
        fields = '__all__'
        read_only_fields = ['id', 'subtotal', 'discount_amount', 'tax_amount', 'total', 'created_at']

class PurchaseOrderItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderItem
        fields = [
            'product', 'variant', 'quantity', 'unit_price',
            'discount_percent', 'tax_rate', 'notes'
        ]
    
    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value
    
    def validate_unit_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Unit price must be greater than 0")
        return value

# Goods Receipt Serializers
class GoodsReceiptItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='purchase_order_item.product.name', read_only=True)
    product_sku = serializers.CharField(source='purchase_order_item.product.sku', read_only=True)
    
    class Meta:
        model = GoodsReceiptItem
        fields = '__all__'
        read_only_fields = ['id', 'accepted_quantity', 'created_at']

class GoodsReceiptSerializer(serializers.ModelSerializer):
    items = GoodsReceiptItemSerializer(many=True, read_only=True)
    received_by_name = serializers.CharField(source='received_by.get_full_name', read_only=True)
    
    class Meta:
        model = GoodsReceipt
        fields = '__all__'
        read_only_fields = ['id', 'grn_number', 'receipt_date', 'created_at']

class GoodsReceiptCreateSerializer(serializers.ModelSerializer):
    items = serializers.ListField(child=serializers.DictField(), write_only=True)
    
    class Meta:
        model = GoodsReceipt
        fields = [
            'purchase_order', 'supplier_invoice_number', 'supplier_invoice_date',
            'transport_mode', 'vehicle_number', 'driver_name', 'driver_phone',
            'notes', 'items'
        ]
    
    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required")
        return value

# Purchase Payment Serializers
class PurchasePaymentSerializer(serializers.ModelSerializer):
    paid_by_name = serializers.CharField(source='paid_by.get_full_name', read_only=True)
    
    class Meta:
        model = PurchasePayment
        fields = '__all__'
        read_only_fields = ['id', 'voucher_number', 'created_at']

class PurchasePaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchasePayment
        fields = [
            'amount', 'payment_method', 'reference_number', 'transaction_id',
            'bank_name', 'cheque_number', 'cheque_date', 'notes'
        ]
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value

# Purchase Return Serializers
class PurchaseReturnItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='receipt_item.purchase_order_item.product.name', read_only=True)
    product_sku = serializers.CharField(source='receipt_item.purchase_order_item.product.sku', read_only=True)
    
    class Meta:
        model = PurchaseReturnItem
        fields = '__all__'

class PurchaseReturnSerializer(serializers.ModelSerializer):
    items = PurchaseReturnItemSerializer(many=True, read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = PurchaseReturn
        fields = '__all__'
        read_only_fields = ['id', 'return_number', 'return_date', 'created_at']

class PurchaseReturnCreateSerializer(serializers.ModelSerializer):
    items = serializers.ListField(child=serializers.DictField(), write_only=True)
    
    class Meta:
        model = PurchaseReturn
        fields = ['reason', 'notes', 'items']

# Supplier Invoice Serializer
class SupplierInvoiceSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.company_name', read_only=True)
    po_number = serializers.CharField(source='purchase_order.po_number', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = SupplierInvoice
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

# Main Purchase Order Serializers
class PurchaseOrderListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.company_name', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    
    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'po_number', 'supplier_name', 'requested_by_name', 'order_date',
            'expected_delivery_date', 'order_status', 'payment_status',
            'total_amount', 'paid_amount', 'due_amount',
            'is_fully_paid', 'is_overdue'
        ]

class PurchaseOrderDetailSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True, read_only=True)
    payments = PurchasePaymentSerializer(many=True, read_only=True)
    returns = PurchaseReturnSerializer(many=True, read_only=True)
    goods_receipts = GoodsReceiptSerializer(many=True, read_only=True)
    supplier_details = SupplierListSerializer(source='supplier', read_only=True)
    requested_by_details = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    
    class Meta:
        model = PurchaseOrder
        fields = '__all__'

class PurchaseOrderCreateSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemCreateSerializer(many=True)
    
    class Meta:
        model = PurchaseOrder
        fields = [
            'supplier', 'requested_by', 'expected_delivery_date',
            'discount_type', 'discount_value', 'tax_type', 'shipping_charge',
            'other_charges', 'payment_terms', 'notes', 'terms_conditions', 'items'
        ]
    
    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required")
        return value
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # Calculate totals
        subtotal = 0
        tax_total = 0
        discount_total = 0
        
        # Create order
        purchase_order = PurchaseOrder.objects.create(**validated_data)
        
        # Create items and calculate totals
        for item_data in items_data:
            item = PurchaseOrderItem.objects.create(purchase_order=purchase_order, **item_data)
            subtotal += item.subtotal
            discount_total += item.discount_amount
            tax_total += item.tax_amount
        
        # Update order totals
        purchase_order.subtotal = subtotal
        purchase_order.discount_amount = discount_total
        purchase_order.tax_amount = tax_total
        
        # Apply additional discounts
        if purchase_order.discount_type == 'percentage':
            purchase_order.discount_amount += (subtotal * purchase_order.discount_value / 100)
        elif purchase_order.discount_type == 'fixed':
            purchase_order.discount_amount += purchase_order.discount_value
        
        # Calculate final total
        after_discount = subtotal - purchase_order.discount_amount
        purchase_order.total_amount = after_discount + tax_total + purchase_order.shipping_charge + purchase_order.other_charges
        purchase_order.due_amount = purchase_order.total_amount
        
        purchase_order.save()
        
        return purchase_order
