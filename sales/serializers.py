from rest_framework import serializers
from .models import (
    SalesOrder, SalesOrderItem, SalesPayment, 
    SalesReturn, SalesReturnItem, Invoice,
    Quotation, QuotationItem
)
from products.models import Product
from products.serializers import ProductListSerializer
from customers.serializers import CustomerListSerializer

# Sales Order Item Serializers
class SalesOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    
    class Meta:
        model = SalesOrderItem
        fields = '__all__'
        read_only_fields = ['id', 'subtotal', 'discount_amount', 'tax_amount', 'total', 'created_at']

class SalesOrderItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesOrderItem
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

# Sales Payment Serializers
class SalesPaymentSerializer(serializers.ModelSerializer):
    received_by_name = serializers.CharField(source='received_by.get_full_name', read_only=True)
    
    class Meta:
        model = SalesPayment
        fields = '__all__'
        read_only_fields = ['id', 'receipt_number', 'created_at']

class SalesPaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesPayment
        fields = [
            'amount', 'payment_method', 'reference_number', 'transaction_id',
            'bank_name', 'cheque_number', 'cheque_date', 'card_last_four',
            'card_type', 'notes'
        ]
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value

# Sales Return Serializers
class SalesReturnItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='order_item.product.name', read_only=True)
    product_sku = serializers.CharField(source='order_item.product.sku', read_only=True)
    
    class Meta:
        model = SalesReturnItem
        fields = '__all__'

class SalesReturnSerializer(serializers.ModelSerializer):
    items = SalesReturnItemSerializer(many=True, read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = SalesReturn
        fields = '__all__'
        read_only_fields = ['id', 'return_number', 'return_date', 'created_at']

class SalesReturnCreateSerializer(serializers.ModelSerializer):
    items = serializers.ListField(child=serializers.DictField(), write_only=True)
    
    class Meta:
        model = SalesReturn
        fields = ['reason', 'customer_notes', 'items']
    
    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required")
        return value

# Invoice Serializer
class InvoiceSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ['id', 'invoice_number', 'invoice_date', 'created_at']

# Quotation Serializers
class QuotationItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    
    class Meta:
        model = QuotationItem
        fields = '__all__'

class QuotationSerializer(serializers.ModelSerializer):
    items = QuotationItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    sales_person_name = serializers.CharField(source='sales_person.get_full_name', read_only=True)
    
    class Meta:
        model = Quotation
        fields = '__all__'
        read_only_fields = ['id', 'quotation_number', 'quotation_date', 'created_at']

class QuotationCreateSerializer(serializers.ModelSerializer):
    items = serializers.ListField(child=serializers.DictField(), write_only=True)
    
    class Meta:
        model = Quotation
        fields = [
            'customer', 'sales_person', 'valid_until',
            'terms_conditions', 'customer_notes', 'items'
        ]

# Main Sales Order Serializers
class SalesOrderListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    sales_person_name = serializers.CharField(source='sales_person.get_full_name', read_only=True)
    
    class Meta:
        model = SalesOrder
        fields = [
            'id', 'order_number', 'invoice_number', 'customer_name', 'sales_person_name',
            'order_date', 'order_status', 'payment_status',
            'total_amount', 'paid_amount', 'due_amount',
            'is_fully_paid', 'is_overdue'
        ]

class SalesOrderDetailSerializer(serializers.ModelSerializer):
    items = SalesOrderItemSerializer(many=True, read_only=True)
    payments = SalesPaymentSerializer(many=True, read_only=True)
    returns = SalesReturnSerializer(many=True, read_only=True)
    customer_details = CustomerListSerializer(source='customer', read_only=True)
    sales_person_details = serializers.CharField(source='sales_person.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    
    class Meta:
        model = SalesOrder
        fields = '__all__'

class SalesOrderCreateSerializer(serializers.ModelSerializer):
    items = SalesOrderItemCreateSerializer(many=True)
    
    class Meta:
        model = SalesOrder
        fields = [
            'customer', 'sales_person', 'delivery_date', 'expected_delivery_date',
            'discount_type', 'discount_value', 'tax_type', 'shipping_charge',
            'other_charges', 'payment_method', 'payment_terms',
            'shipping_address', 'billing_address', 'customer_notes',
            'staff_notes', 'terms_conditions', 'items'
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
        sales_order = SalesOrder.objects.create(**validated_data)
        
        # Create items and calculate totals
        for item_data in items_data:
            item = SalesOrderItem.objects.create(sales_order=sales_order, **item_data)
            subtotal += item.subtotal
            discount_total += item.discount_amount
            tax_total += item.tax_amount
        
        # Update order totals
        sales_order.subtotal = subtotal
        sales_order.discount_amount = discount_total
        sales_order.tax_amount = tax_total
        
        # Apply additional discounts
        if sales_order.discount_type == 'percentage':
            sales_order.discount_amount += (subtotal * sales_order.discount_value / 100)
        elif sales_order.discount_type == 'fixed':
            sales_order.discount_amount += sales_order.discount_value
        
        # Calculate final total
        after_discount = subtotal - sales_order.discount_amount
        sales_order.total_amount = after_discount + tax_total + sales_order.shipping_charge + sales_order.other_charges
        sales_order.due_amount = sales_order.total_amount
        
        sales_order.save()
        
        return sales_order
