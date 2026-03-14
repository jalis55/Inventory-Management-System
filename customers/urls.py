from django.urls import path
from . import views

urlpatterns = [
    # Customer CRUD
    path('', views.CustomerListCreateView.as_view(), name='customer-list'),
    path('<uuid:id>/', views.CustomerRetrieveUpdateDestroyView.as_view(), name='customer-detail'),
    
    # Customer Statistics
    path('statistics/', views.CustomerStatisticsView.as_view(), name='customer-statistics'),
    
    # Customer Search
    path('search/', views.CustomerSearchView.as_view(), name='customer-search'),
    
    # Reports
    path('reports/outstanding/', views.CustomerOutstandingReportView.as_view(), name='customer-outstanding-report'),
    path('reports/loyalty/', views.CustomerLoyaltyReportView.as_view(), name='customer-loyalty-report'),
    
    # Bulk Operations
    path('bulk-upload/', views.CustomerBulkUploadView.as_view(), name='customer-bulk-upload'),
    path('export/', views.CustomerExportView.as_view(), name='customer-export'),
    
    # Customer Addresses
    path('<uuid:customer_id>/addresses/', views.CustomerAddressListCreateView.as_view(), name='customer-address-list'),
    path('addresses/<uuid:id>/', views.CustomerAddressRetrieveUpdateDestroyView.as_view(), name='customer-address-detail'),
    
    # Customer Contacts
    path('<uuid:customer_id>/contacts/', views.CustomerContactListCreateView.as_view(), name='customer-contact-list'),
    path('contacts/<uuid:id>/', views.CustomerContactRetrieveUpdateDestroyView.as_view(), name='customer-contact-detail'),
    
    # Customer Interactions
    path('<uuid:customer_id>/interactions/', views.CustomerInteractionListCreateView.as_view(), name='customer-interaction-list'),
    path('interactions/<uuid:id>/', views.CustomerInteractionRetrieveUpdateDestroyView.as_view(), name='customer-interaction-detail'),
    
    # Customer Payments
    path('<uuid:customer_id>/payments/', views.CustomerPaymentListCreateView.as_view(), name='customer-payment-list'),
    path('payments/<uuid:id>/', views.CustomerPaymentRetrieveView.as_view(), name='customer-payment-detail'),
    
    # Customer Loyalty
    path('<uuid:customer_id>/loyalty/', views.CustomerLoyaltyView.as_view(), name='customer-loyalty'),
    
    # Customer Documents
    path('<uuid:customer_id>/documents/', views.CustomerDocumentListCreateView.as_view(), name='customer-document-list'),
    path('documents/<uuid:id>/', views.CustomerDocumentRetrieveUpdateDestroyView.as_view(), name='customer-document-detail'),
]