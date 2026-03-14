from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from .models import Category, Brand, Unit, Product, ProductVariant, StockMovement

class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = '__all__'
    
    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_children(self, obj):
        if obj.children.exists():
            return CategorySerializer(obj.children.all(), many=True).data
        return []

class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = '__all__'

class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = '__all__'

class ProductVariantSerializer(serializers.ModelSerializer):
    selling_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    cost_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = ProductVariant
        fields = '__all__'
        extra_kwargs = {
            'product': {'read_only': True},
        }

class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    unit_abbr = serializers.CharField(source='unit.abbreviation', read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'sku', 'name', 'category_name', 'brand_name',
            'selling_price', 'current_stock', 'unit_abbr',
            'is_active', 'is_low_stock', 'is_out_of_stock',
            'image', 'created_at'
        ]

class ProductDetailSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    profit_margin = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    
    class Meta:
        model = Product
        fields = '__all__'

class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'sku', 'barcode', 'name', 'description', 'category', 'brand',
            'unit', 'cost_price', 'selling_price', 'wholesale_price', 'mrp',
            'tax_rate', 'current_stock', 'minimum_stock', 'maximum_stock',
            'reorder_point', 'image', 'gallery', 'is_active', 'is_featured',
            'is_discounted', 'discount_percent', 'tags', 'attributes'
        ]
    
    def validate(self, data):
        if data.get('selling_price', 0) < data.get('cost_price', 0):
            raise serializers.ValidationError("Selling price cannot be less than cost price")
        return data

class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = StockMovement
        fields = '__all__'
        read_only_fields = ['previous_quantity', 'new_quantity', 'created_by']


class CategoryStatisticsSerializer(serializers.Serializer):
    name = serializers.CharField()
    product_count = serializers.IntegerField()


class ProductStatisticsSerializer(serializers.Serializer):
    total_products = serializers.IntegerField()
    active_products = serializers.IntegerField()
    out_of_stock = serializers.IntegerField()
    low_stock = serializers.IntegerField()
    category_stats = CategoryStatisticsSerializer(many=True)
