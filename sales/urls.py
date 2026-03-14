from django.urls import path
from . import views

urlpatterns = [
    # Dashboard & Reports
    path('dashboard/', views.SalesDashboardView.as_view(), name='sales-dashboard'),
    path('reports/', views.SalesReportView.as_view(), name='sales-reports'),
    
    # Sales Orders
    path('orders/', views.SalesOrderListCreateView.as_view(), name='sales-order-list'),
    path('orders/<uuid:id>/', views.SalesOrderRetrieveUpdateDestroyView.as_view(), name='sales-order-detail'),
    path('orders/<uuid:id>/status/', views.SalesOrderStatusUpdateView.as_view(), name='sales-order-status'),
    
    # Sales Payments
    path('orders/<uuid:order_id>/payments/', views.SalesPaymentListCreateView.as_view(), name='sales-payment-list'),
    
    # Sales Returns
    path('orders/<uuid:order_id>/returns/', views.SalesReturnListCreateView.as_view(), name='sales-return-list'),
    path('returns/<uuid:id>/approve/', views.SalesReturnApproveView.as_view(), name='sales-return-approve'),
    
    # Quotations
    path('quotations/', views.QuotationListCreateView.as_view(), name='quotation-list'),
    path('quotations/<uuid:id>/', views.QuotationRetrieveUpdateDestroyView.as_view(), name='quotation-detail'),
    path('quotations/<uuid:id>/convert/', views.QuotationConvertToOrderView.as_view(), name='quotation-convert'),
]