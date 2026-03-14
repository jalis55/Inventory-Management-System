from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Sum, Count, F
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import Category, Brand, Unit, Product, ProductVariant, StockMovement
from .serializers import (
    CategorySerializer, BrandSerializer, UnitSerializer,
    ProductListSerializer, ProductDetailSerializer, ProductCreateUpdateSerializer,
    ProductVariantSerializer, StockMovementSerializer, ProductStatisticsSerializer
)
from accounts.models import ActivityLog
import django_filters

# Category Views
@extend_schema_view(get=extend_schema(tags=['Catalog']), post=extend_schema(tags=['Catalog']))
class CategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    
    def perform_create(self, serializer):
        category = serializer.save()
        ActivityLog.objects.create(
            user=self.request.user,
            action='CATEGORY_CREATED',
            details={'category_name': category.name, 'category_id': str(category.id)}
        )

@extend_schema_view(
    get=extend_schema(tags=['Catalog']),
    put=extend_schema(tags=['Catalog']),
    patch=extend_schema(tags=['Catalog']),
    delete=extend_schema(tags=['Catalog']),
)
class CategoryRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def perform_update(self, serializer):
        category = serializer.save()
        ActivityLog.objects.create(
            user=self.request.user,
            action='CATEGORY_UPDATED',
            details={'category_name': category.name, 'category_id': str(category.id)}
        )
    
    def perform_destroy(self, instance):
        ActivityLog.objects.create(
            user=self.request.user,
            action='CATEGORY_DELETED',
            details={'category_name': instance.name, 'category_id': str(instance.id)}
        )
        instance.delete()

# Brand Views
@extend_schema_view(get=extend_schema(tags=['Catalog']), post=extend_schema(tags=['Catalog']))
class BrandListCreateView(generics.ListCreateAPIView):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    
    def perform_create(self, serializer):
        brand = serializer.save()
        ActivityLog.objects.create(
            user=self.request.user,
            action='BRAND_CREATED',
            details={'brand_name': brand.name, 'brand_id': str(brand.id)}
        )

@extend_schema_view(
    get=extend_schema(tags=['Catalog']),
    put=extend_schema(tags=['Catalog']),
    patch=extend_schema(tags=['Catalog']),
    delete=extend_schema(tags=['Catalog']),
)
class BrandRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

# Unit Views
@extend_schema_view(get=extend_schema(tags=['Catalog']), post=extend_schema(tags=['Catalog']))
class UnitListCreateView(generics.ListCreateAPIView):
    queryset = Unit.objects.order_by('name')
    serializer_class = UnitSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'abbreviation']
    ordering_fields = ['name']

@extend_schema_view(
    get=extend_schema(tags=['Catalog']),
    put=extend_schema(tags=['Catalog']),
    patch=extend_schema(tags=['Catalog']),
    delete=extend_schema(tags=['Catalog']),
)
class UnitRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

# Product Filters
class ProductFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name="selling_price", lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name="selling_price", lookup_expr='lte')
    category = django_filters.UUIDFilter(field_name="category__id")
    brand = django_filters.UUIDFilter(field_name="brand__id")
    in_stock = django_filters.BooleanFilter(method='filter_in_stock')
    low_stock = django_filters.BooleanFilter(method='filter_low_stock')
    
    class Meta:
        model = Product
        fields = ['is_active', 'is_featured', 'category', 'brand']
    
    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(current_stock__gt=0)
        return queryset.filter(current_stock=0)
    
    def filter_low_stock(self, queryset, name, value):
        if value:
            return queryset.filter(current_stock__lte=F('reorder_point'))
        return queryset

# Product Views
@extend_schema_view(get=extend_schema(tags=['Products']), post=extend_schema(tags=['Products']))
class ProductListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'sku', 'barcode', 'description']
    ordering_fields = ['name', 'created_at', 'selling_price', 'current_stock']
    
    def get_queryset(self):
        return Product.objects.select_related('category', 'brand', 'unit').all()
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ProductListSerializer
        return ProductCreateUpdateSerializer
    
    def perform_create(self, serializer):
        with transaction.atomic():
            product = serializer.save(created_by=self.request.user)
            
            # Create initial stock movement
            if product.current_stock > 0:
                StockMovement.objects.create(
                    product=product,
                    movement_type='adjustment',
                    quantity=product.current_stock,
                    previous_quantity=0,
                    new_quantity=product.current_stock,
                    notes='Initial stock',
                    created_by=self.request.user
                )
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='PRODUCT_CREATED',
                details={'product_name': product.name, 'product_id': str(product.id), 'sku': product.sku}
            )

@extend_schema_view(
    get=extend_schema(tags=['Products']),
    put=extend_schema(tags=['Products']),
    patch=extend_schema(tags=['Products']),
    delete=extend_schema(tags=['Products']),
)
class ProductRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return Product.objects.select_related('category', 'brand', 'unit').prefetch_related('variants').all()
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ProductDetailSerializer
        return ProductCreateUpdateSerializer
    
    def perform_update(self, serializer):
        product = serializer.save(updated_by=self.request.user)
        ActivityLog.objects.create(
            user=self.request.user,
            action='PRODUCT_UPDATED',
            details={'product_name': product.name, 'product_id': str(product.id)}
        )
    
    def perform_destroy(self, instance):
        ActivityLog.objects.create(
            user=self.request.user,
            action='PRODUCT_DELETED',
            details={'product_name': instance.name, 'product_id': str(instance.id), 'sku': instance.sku}
        )
        instance.delete()

# Product Variant Views
@extend_schema_view(get=extend_schema(tags=['Products']), post=extend_schema(tags=['Products']))
class ProductVariantListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductVariantSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        return ProductVariant.objects.filter(product_id=product_id).order_by('-created_at')
    
    def perform_create(self, serializer):
        product_id = self.kwargs.get('product_id')
        product = Product.objects.get(id=product_id)
        variant = serializer.save(product=product)
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='VARIANT_CREATED',
            details={'product_name': product.name, 'variant_name': variant.name}
        )

@extend_schema_view(
    get=extend_schema(tags=['Products']),
    put=extend_schema(tags=['Products']),
    patch=extend_schema(tags=['Products']),
    delete=extend_schema(tags=['Products']),
)
class ProductVariantRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductVariantSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return ProductVariant.objects.all()

# Stock Movement Views
@extend_schema_view(get=extend_schema(tags=['Products']), post=extend_schema(tags=['Products']))
class StockMovementListCreateView(generics.ListCreateAPIView):
    serializer_class = StockMovementSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['movement_type', 'product', 'created_by']
    ordering_fields = ['created_at']
    
    def get_queryset(self):
        return StockMovement.objects.select_related('product', 'created_by').all()
    
    def perform_create(self, serializer):
        with transaction.atomic():
            product = serializer.validated_data['product']
            old_stock = product.current_stock
            new_stock = old_stock + serializer.validated_data['quantity']
            movement = serializer.save(
                created_by=self.request.user,
                previous_quantity=old_stock,
                new_quantity=new_stock,
            )
            
            # Keep the product stock in sync with the recorded movement.
            product.current_stock = new_stock
            product.save(update_fields=['current_stock'])
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='STOCK_MOVEMENT',
                details={
                    'product': product.name,
                    'type': movement.movement_type,
                    'quantity': movement.quantity,
                    'previous': old_stock,
                    'new': product.current_stock
                }
            )

@extend_schema(tags=['Products'])
class ProductStockMovementsView(generics.ListAPIView):
    serializer_class = StockMovementSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        return StockMovement.objects.filter(product_id=product_id).select_related('created_by')

# Dashboard/Statistics Views
@extend_schema(tags=['Products'], responses={200: ProductStatisticsSerializer})
class ProductStatisticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        total_products = Product.objects.count()
        active_products = Product.objects.filter(is_active=True).count()
        out_of_stock = Product.objects.filter(current_stock=0).count()
        low_stock = Product.objects.filter(current_stock__lte=F('reorder_point')).count()
        
        category_stats = Category.objects.annotate(
            product_count=Count('products')
        ).values('name', 'product_count')
        
        return Response({
            'total_products': total_products,
            'active_products': active_products,
            'out_of_stock': out_of_stock,
            'low_stock': low_stock,
            'category_stats': category_stats
        })
