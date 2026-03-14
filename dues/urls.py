from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.DuesDashboardView.as_view(), name='dues-dashboard'),
    
    # Aging Reports
    path('reports/customer-aging/', views.CustomerAgingReportView.as_view(), name='customer-aging'),
    path('reports/supplier-aging/', views.SupplierAgingReportView.as_view(), name='supplier-aging'),
    
    # Customer Dues
    path('customer-dues/', views.CustomerDueListView.as_view(), name='customer-due-list'),
    path('customer-dues/<uuid:id>/', views.CustomerDueDetailView.as_view(), name='customer-due-detail'),
    
    # Supplier Dues
    path('supplier-dues/', views.SupplierDueListView.as_view(), name='supplier-due-list'),
    path('supplier-dues/<uuid:id>/', views.SupplierDueDetailView.as_view(), name='supplier-due-detail'),
    
    # Payment Collections (from customers)
    path('collections/', views.PaymentCollectionListCreateView.as_view(), name='collection-list'),
    path('collections/<uuid:id>/receipt/', views.PaymentCollectionReceiptView.as_view(), name='collection-receipt'),
    
    # Payment Disbursements (to suppliers)
    path('disbursements/', views.PaymentDisbursementListCreateView.as_view(), name='disbursement-list'),
    
    # Due Reminders
    path('reminders/', views.DueReminderListCreateView.as_view(), name='reminder-list'),
    path('reminders/<uuid:id>/send/', views.DueReminderSendView.as_view(), name='reminder-send'),
    
    # Write Offs
    path('write-offs/', views.WriteOffListCreateView.as_view(), name='writeoff-list'),
    path('write-offs/<uuid:id>/approve/', views.WriteOffApproveView.as_view(), name='writeoff-approve'),
]