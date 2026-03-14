from django.urls import path
from . import views

urlpatterns = [
    # Dashboard & Reports
    path('dashboard/', views.PurchaseDashboardView.as_view(), name='purchase-dashboard'),
    path('reports/', views.PurchaseReportView.as_view(), name='purchase-reports'),
    
    # Purchase Orders
    path('orders/', views.PurchaseOrderListCreateView.as_view(), name='purchase-order-list'),
    path('orders/<uuid:id>/', views.PurchaseOrderRetrieveUpdateDestroyView.as_view(), name='purchase-order-detail'),
    path('orders/<uuid:id>/status/', views.PurchaseOrderStatusUpdateView.as_view(), name='purchase-order-status'),
    
    # Goods Receipts
    path('goods-receipts/', views.GoodsReceiptListCreateView.as_view(), name='goods-receipt-list'),
    path('goods-receipts/<uuid:id>/', views.GoodsReceiptRetrieveView.as_view(), name='goods-receipt-detail'),
    
    # Purchase Payments
    path('orders/<uuid:order_id>/payments/', views.PurchasePaymentListCreateView.as_view(), name='purchase-payment-list'),
    
    # Purchase Returns
    path('orders/<uuid:order_id>/returns/', views.PurchaseReturnListCreateView.as_view(), name='purchase-return-list'),
    path('returns/<uuid:id>/approve/', views.PurchaseReturnApproveView.as_view(), name='purchase-return-approve'),
    
    # Supplier Invoices
    path('supplier-invoices/', views.SupplierInvoiceListCreateView.as_view(), name='supplier-invoice-list'),
]