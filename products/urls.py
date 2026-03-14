from django.urls import path
from . import views

urlpatterns = [
    # Category URLs
    path('categories/', views.CategoryListCreateView.as_view(), name='category-list'),
    path('categories/<uuid:id>/', views.CategoryRetrieveUpdateDestroyView.as_view(), name='category-detail'),
    
    # Brand URLs
    path('brands/', views.BrandListCreateView.as_view(), name='brand-list'),
    path('brands/<uuid:id>/', views.BrandRetrieveUpdateDestroyView.as_view(), name='brand-detail'),
    
    # Unit URLs
    path('units/', views.UnitListCreateView.as_view(), name='unit-list'),
    path('units/<uuid:id>/', views.UnitRetrieveUpdateDestroyView.as_view(), name='unit-detail'),
    
    # Product URLs
    path('products/', views.ProductListCreateView.as_view(), name='product-list'),
    path('products/<uuid:id>/', views.ProductRetrieveUpdateDestroyView.as_view(), name='product-detail'),
    path('products/statistics/', views.ProductStatisticsView.as_view(), name='product-statistics'),
    
    # Product Variant URLs
    path('products/<uuid:product_id>/variants/', views.ProductVariantListCreateView.as_view(), name='variant-list'),
    path('variants/<uuid:id>/', views.ProductVariantRetrieveUpdateDestroyView.as_view(), name='variant-detail'),
    
    # Stock Movement URLs
    path('stock-movements/', views.StockMovementListCreateView.as_view(), name='stock-movement-list'),
    path('products/<uuid:product_id>/stock-movements/', views.ProductStockMovementsView.as_view(), name='product-stock-movements'),
]