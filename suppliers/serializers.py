from rest_framework import serializers
from .models import Supplier, SupplierProduct
from products.models import Product
from products.serializers import ProductListSerializer

class SupplierProductSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    
    class Meta:
        model = SupplierProduct
        fields = '__all__'

class SupplierProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierProduct
        fields = ['product', 'supplier_sku', 'price', 'lead_time_days', 
                 'minimum_order_quantity', 'is_preferred', 'notes']
    
    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0")
        return value

class SupplierListSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Supplier
        fields = [
            'id', 'company_name', 'contact_person', 'email', 'phone',
            'city', 'state', 'gst_number', 'outstanding_amount',
            'is_active', 'rating', 'product_count', 'created_at'
        ]
    
    def get_product_count(self, obj):
        return obj.supplier_products.count()

class SupplierDetailSerializer(serializers.ModelSerializer):
    supplier_products = SupplierProductSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    
    class Meta:
        model = Supplier
        fields = '__all__'

class SupplierCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            'company_name', 'contact_person', 'email', 'phone', 'mobile',
            'website', 'address_line1', 'address_line2', 'city', 'state',
            'postal_code', 'country', 'gst_number', 'pan_number', 'tax_id',
            'payment_terms', 'credit_limit', 'bank_name', 'bank_account',
            'bank_ifsc', 'notes', 'is_active', 'rating'
        ]
    
    def validate_gst_number(self, value):
        if value and len(value) != 15:
            raise serializers.ValidationError("GST number must be 15 characters long")
        return value.upper() if value else value
    
    def validate_pan_number(self, value):
        if value and len(value) != 10:
            raise serializers.ValidationError("PAN number must be 10 characters long")
        return value.upper() if value else value

class SupplierPaymentUpdateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_date = serializers.DateField()
    payment_method = serializers.ChoiceField(choices=['cash', 'bank_transfer', 'cheque', 'online'])
    reference_number = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)