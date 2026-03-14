from django.urls import path
from . import views

urlpatterns = [
    # Supplier CRUD
    path('', views.SupplierListCreateView.as_view(), name='supplier-list'),
    path('<uuid:id>/', views.SupplierRetrieveUpdateDestroyView.as_view(), name='supplier-detail'),
    
    # Supplier Statistics
    path('statistics/', views.SupplierStatisticsView.as_view(), name='supplier-statistics'),
    
    # Supplier Search
    path('search/', views.SupplierSearchView.as_view(), name='supplier-search'),
    
    # Supplier Products
    path('<uuid:supplier_id>/products/', views.SupplierProductListCreateView.as_view(), name='supplier-product-list'),
    path('products/<uuid:id>/', views.SupplierProductRetrieveUpdateDestroyView.as_view(), name='supplier-product-detail'),
    
    # Supplier Products by Category
    path('<uuid:supplier_id>/products/by-category/', views.SupplierProductsByCategoryView.as_view(), name='supplier-products-category'),
    
    # Supplier Payments
    path('<uuid:supplier_id>/payments/', views.SupplierPaymentView.as_view(), name='supplier-payment'),
    
    # Bulk Operations
    path('bulk-upload/', views.SupplierBulkUploadView.as_view(), name='supplier-bulk-upload'),
    path('export/', views.SupplierExportView.as_view(), name='supplier-export'),
]