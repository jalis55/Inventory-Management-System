from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.InventoryDashboardView.as_view(), name='inventory-dashboard'),
    
    # Warehouses
    path('warehouses/', views.WarehouseListCreateView.as_view(), name='warehouse-list'),
    path('warehouses/<uuid:id>/', views.WarehouseRetrieveUpdateDestroyView.as_view(), name='warehouse-detail'),
    
    # Stock
    path('stock/', views.StockListView.as_view(), name='stock-list'),
    path('stock/<uuid:id>/', views.StockDetailView.as_view(), name='stock-detail'),
    path('warehouses/<uuid:warehouse_id>/stock/', views.StockByWarehouseView.as_view(), name='warehouse-stock'),
    path('low-stock/', views.LowStockListView.as_view(), name='low-stock'),
    
    # Batches
    path('batches/', views.BatchListCreateView.as_view(), name='batch-list'),
    path('batches/<uuid:id>/', views.BatchDetailView.as_view(), name='batch-detail'),
    path('batches/expiring/', views.ExpiringBatchesView.as_view(), name='expiring-batches'),
    
    # Serial Numbers
    path('serials/', views.SerialNumberListCreateView.as_view(), name='serial-list'),
    path('serials/<uuid:id>/', views.SerialNumberDetailView.as_view(), name='serial-detail'),
    
    # Stock Transfers
    path('transfers/', views.StockTransferListCreateView.as_view(), name='transfer-list'),
    path('transfers/<uuid:id>/', views.StockTransferDetailView.as_view(), name='transfer-detail'),
    path('transfers/<uuid:id>/status/', views.StockTransferStatusUpdateView.as_view(), name='transfer-status'),
    
    # Stock Adjustments
    path('adjustments/', views.StockAdjustmentListCreateView.as_view(), name='adjustment-list'),
    path('adjustments/<uuid:id>/', views.StockAdjustmentDetailView.as_view(), name='adjustment-detail'),
    path('adjustments/<uuid:id>/approve/', views.StockAdjustmentApproveView.as_view(), name='adjustment-approve'),
    
    # Cycle Counts
    path('cycle-counts/', views.CycleCountListCreateView.as_view(), name='cycle-count-list'),
    path('cycle-counts/<uuid:id>/', views.CycleCountDetailView.as_view(), name='cycle-count-detail'),
    path('cycle-counts/<uuid:id>/start/', views.CycleCountStartView.as_view(), name='cycle-count-start'),
    path('cycle-counts/<uuid:id>/update-item/', views.CycleCountUpdateItemView.as_view(), name='cycle-count-update'),
    path('cycle-counts/<uuid:id>/complete/', views.CycleCountCompleteView.as_view(), name='cycle-count-complete'),
    
    # Reorder Requests
    path('reorder-requests/', views.ReorderRequestListView.as_view(), name='reorder-list'),
    path('reorder-requests/generate/', views.GenerateReorderRequestsView.as_view(), name='reorder-generate'),
]