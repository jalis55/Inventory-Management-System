from django.urls import path
from . import views

urlpatterns = [
    # Sales Reports
    path('sales/', views.SalesReportView.as_view(), name='report-sales'),
    path('sales/trend/', views.SalesTrendReportView.as_view(), name='report-sales-trend'),
    
    # Purchase Reports
    path('purchases/', views.PurchaseReportView.as_view(), name='report-purchases'),
    
    # Inventory Reports
    path('inventory/', views.InventoryReportView.as_view(), name='report-inventory'),
    path('inventory/valuation/', views.InventoryValuationReportView.as_view(), name='report-inventory-valuation'),
    
    # Customer Reports
    path('customers/', views.CustomerReportView.as_view(), name='report-customers'),
    
    # Financial Reports
    path('financial/profit-loss/', views.ProfitLossReportView.as_view(), name='report-profit-loss'),
    path('financial/dues-aging/', views.DuesAgingReportView.as_view(), name='report-dues-aging'),
    
    # Dashboard Widgets
    path('dashboard/widgets/', views.DashboardWidgetListCreateView.as_view(), name='dashboard-widgets'),
    path('dashboard/widgets/<uuid:id>/', views.DashboardWidgetRetrieveUpdateDestroyView.as_view(), name='dashboard-widget-detail'),
    path('dashboard/data/', views.DashboardDataView.as_view(), name='dashboard-data'),
    
    # Saved Reports
    path('saved/', views.SavedReportListCreateView.as_view(), name='saved-reports'),
    path('saved/<uuid:id>/', views.SavedReportRetrieveUpdateDestroyView.as_view(), name='saved-report-detail'),
    path('saved/<uuid:id>/generate/', views.GenerateSavedReportView.as_view(), name='generate-saved-report'),
    
    # Report History
    path('history/', views.ReportGenerationHistoryView.as_view(), name='report-history'),
]