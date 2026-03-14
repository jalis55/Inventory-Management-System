from rest_framework import generics, permissions, status, filters, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Sum, Count, F, Avg
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import timedelta, date
from .models import (
    Warehouse, Stock, Batch, SerialNumber,
    StockTransfer, StockTransferItem,
    StockAdjustment, StockAdjustmentItem,
    CycleCount, CycleCountItem,
    ReorderRequest, InventoryForecast
)
from .serializers import (
    WarehouseSerializer, WarehouseListSerializer,
    StockSerializer, BatchSerializer, SerialNumberSerializer,
    StockTransferSerializer, StockTransferCreateSerializer,
    StockAdjustmentSerializer, StockAdjustmentCreateSerializer,
    CycleCountSerializer, CycleCountCreateSerializer, CycleCountItemSerializer, CycleCountUpdateSerializer,
    ReorderRequestSerializer, InventoryForecastSerializer
)
from products.models import Product, ProductVariant, StockMovement
from accounts.models import ActivityLog
import django_filters

# Warehouse Views
class WarehouseListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'city', 'state']
    ordering_fields = ['name', 'created_at']
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return WarehouseListSerializer
        return WarehouseSerializer
    
    def get_queryset(self):
        return Warehouse.objects.all()
    
    def perform_create(self, serializer):
        warehouse = serializer.save(created_by=self.request.user)
        ActivityLog.objects.create(
            user=self.request.user,
            action='WAREHOUSE_CREATED',
            details={
                'warehouse_name': warehouse.name,
                'code': warehouse.code,
                'type': warehouse.type
            }
        )

class WarehouseRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WarehouseSerializer
    lookup_field = 'id'
    
    def get_queryset(self):
        return Warehouse.objects.all()
    
    def perform_update(self, serializer):
        warehouse = serializer.save(updated_by=self.request.user)
        ActivityLog.objects.create(
            user=self.request.user,
            action='WAREHOUSE_UPDATED',
            details={
                'warehouse_name': warehouse.name,
                'code': warehouse.code
            }
        )
    
    def perform_destroy(self, instance):
        # Check if warehouse has stock
        if instance.stock_items.filter(quantity__gt=0).exists():
            raise serializers.ValidationError("Cannot delete warehouse with stock")
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='WAREHOUSE_DELETED',
            details={
                'warehouse_name': instance.name,
                'code': instance.code
            }
        )
        instance.delete()

# Stock Views
class StockListView(generics.ListAPIView):
    """List all stock with filtering"""
    serializer_class = StockSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['warehouse', 'product', 'variant', 'is_active']
    search_fields = ['product__name', 'product__sku', 'warehouse__name', 'bin_location']
    ordering_fields = ['quantity', 'available_quantity', 'product__name']
    
    def get_queryset(self):
        return Stock.objects.select_related(
            'warehouse', 'product', 'variant'
        ).filter(quantity__gt=0)

class StockDetailView(generics.RetrieveAPIView):
    serializer_class = StockSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return Stock.objects.select_related('warehouse', 'product', 'variant').all()

class StockByWarehouseView(generics.ListAPIView):
    """Get stock for a specific warehouse"""
    serializer_class = StockSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        warehouse_id = self.kwargs.get('warehouse_id')
        return Stock.objects.filter(
            warehouse_id=warehouse_id,
            quantity__gt=0
        ).select_related('product', 'variant')

class LowStockListView(generics.ListAPIView):
    """List all low stock items"""
    serializer_class = StockSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Stock.objects.filter(
            available_quantity__lte=F('reorder_point')
        ).select_related('warehouse', 'product', 'variant').order_by('available_quantity')

# Batch Views
class BatchListCreateView(generics.ListCreateAPIView):
    serializer_class = BatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'warehouse', 'status']
    search_fields = ['batch_number', 'manufacturing_lot', 'product__name']
    ordering_fields = ['expiry_date', 'manufacturing_date']
    
    def get_queryset(self):
        return Batch.objects.select_related('product', 'warehouse').all()

class BatchDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return Batch.objects.select_related('product', 'warehouse').all()

class ExpiringBatchesView(generics.ListAPIView):
    """List batches expiring soon"""
    serializer_class = BatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        today = timezone.now().date()
        thirty_days_later = today + timedelta(days=30)
        
        return Batch.objects.filter(
            expiry_date__range=[today, thirty_days_later],
            current_quantity__gt=0
        ).select_related('product', 'warehouse').order_by('expiry_date')

# Serial Number Views
class SerialNumberListCreateView(generics.ListCreateAPIView):
    serializer_class = SerialNumberSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['product', 'warehouse', 'status']
    search_fields = ['serial_number']
    
    def get_queryset(self):
        return SerialNumber.objects.select_related('product', 'warehouse', 'batch').all()

class SerialNumberDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SerialNumberSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return SerialNumber.objects.select_related('product', 'warehouse', 'batch').all()

# Stock Transfer Views
class StockTransferListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StockTransferCreateSerializer
        return StockTransferSerializer
    
    def get_queryset(self):
        return StockTransfer.objects.select_related(
            'from_warehouse', 'to_warehouse', 'requested_by', 'approved_by'
        ).prefetch_related('items__product').all()
    
    @transaction.atomic
    def perform_create(self, serializer):
        items_data = serializer.validated_data.pop('items')
        
        # Create transfer
        transfer = serializer.save(
            requested_by=self.request.user,
            status='pending'
        )
        
        total_items = 0
        
        for item_data in items_data:
            product_id = item_data.get('product')
            variant_id = item_data.get('variant')
            quantity = item_data.get('quantity')
            
            # Check stock availability
            stock = Stock.objects.filter(
                warehouse=transfer.from_warehouse,
                product_id=product_id,
                variant_id=variant_id
            ).first()
            
            if not stock or stock.available_quantity < quantity:
                product = Product.objects.get(id=product_id)
                raise serializers.ValidationError(
                    f"Insufficient stock for {product.name}"
                )
            
            # Reserve stock
            stock.reserved_quantity += quantity
            stock.save()
            
            # Create transfer item
            transfer_item = StockTransferItem.objects.create(
                transfer=transfer,
                product_id=product_id,
                variant_id=variant_id,
                quantity=quantity
            )
            
            total_items += 1
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='STOCK_TRANSFER_CREATED',
            details={
                'transfer_number': transfer.transfer_number,
                'from_warehouse': transfer.from_warehouse.name,
                'to_warehouse': transfer.to_warehouse.name,
                'items_count': total_items
            }
        )

class StockTransferDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = StockTransferSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return StockTransfer.objects.prefetch_related(
            'items__product', 'items__variant'
        ).select_related('from_warehouse', 'to_warehouse').all()
    
    @transaction.atomic
    def perform_update(self, serializer):
        transfer = serializer.save(updated_by=self.request.user)
        ActivityLog.objects.create(
            user=self.request.user,
            action='STOCK_TRANSFER_UPDATED',
            details={
                'transfer_number': transfer.transfer_number,
                'status': transfer.status
            }
        )

class StockTransferStatusUpdateView(APIView):
    """Update transfer status (approve, complete, cancel)"""
    permission_classes = [permissions.IsAuthenticated]
    
    @transaction.atomic
    def post(self, request, id):
        try:
            transfer = StockTransfer.objects.prefetch_related('items').get(id=id)
        except StockTransfer.DoesNotExist:
            return Response({'error': 'Transfer not found'}, status=404)
        
        new_status = request.data.get('status')
        action = request.data.get('action')  # approve, complete, cancel
        
        if action == 'approve' and new_status == 'approved':
            transfer.status = 'approved'
            transfer.approved_by = request.user
            transfer.approved_at = timezone.now()
            
        elif action == 'complete' and new_status == 'completed':
            # Process the transfer completion
            for item in transfer.items.all():
                # Remove from source warehouse
                from_stock = Stock.objects.get(
                    warehouse=transfer.from_warehouse,
                    product=item.product,
                    variant=item.variant
                )
                from_stock.quantity -= item.quantity
                from_stock.reserved_quantity -= item.quantity
                from_stock.last_shipped = timezone.now()
                from_stock.save()
                
                # Add to destination warehouse
                to_stock, created = Stock.objects.get_or_create(
                    warehouse=transfer.to_warehouse,
                    product=item.product,
                    variant=item.variant,
                    defaults={
                        'quantity': 0,
                        'reorder_point': item.product.reorder_point
                    }
                )
                to_stock.quantity += item.quantity
                to_stock.last_received = timezone.now()
                to_stock.save()
                
                # Create stock movement records
                StockMovement.objects.create(
                    product=item.product,
                    variant=item.variant,
                    movement_type='transfer',
                    quantity=-item.quantity,
                    previous_quantity=from_stock.quantity + item.quantity,
                    new_quantity=from_stock.quantity,
                    reference_id=transfer.id,
                    reference_type='stock_transfer_out',
                    notes=f"Transfer to {transfer.to_warehouse.name}",
                    created_by=request.user
                )
                
                StockMovement.objects.create(
                    product=item.product,
                    variant=item.variant,
                    movement_type='transfer',
                    quantity=item.quantity,
                    previous_quantity=to_stock.quantity - item.quantity,
                    new_quantity=to_stock.quantity,
                    reference_id=transfer.id,
                    reference_type='stock_transfer_in',
                    notes=f"Transfer from {transfer.from_warehouse.name}",
                    created_by=request.user
                )
            
            transfer.status = 'completed'
            transfer.completed_date = timezone.now().date()
            
        elif action == 'cancel' and new_status == 'cancelled':
            # Release reserved stock
            for item in transfer.items.all():
                from_stock = Stock.objects.get(
                    warehouse=transfer.from_warehouse,
                    product=item.product,
                    variant=item.variant
                )
                from_stock.reserved_quantity -= item.quantity
                from_stock.save()
            
            transfer.status = 'cancelled'
        
        else:
            return Response({'error': 'Invalid action or status'}, status=400)
        
        transfer.save()
        
        ActivityLog.objects.create(
            user=request.user,
            action=f'STOCK_TRANSFER_{action.upper()}D',
            details={
                'transfer_number': transfer.transfer_number,
                'new_status': transfer.status
            }
        )
        
        return Response({
            'message': f'Transfer {action}d successfully',
            'status': transfer.status
        })

# Stock Adjustment Views
class StockAdjustmentListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StockAdjustmentCreateSerializer
        return StockAdjustmentSerializer
    
    def get_queryset(self):
        return StockAdjustment.objects.select_related(
            'warehouse', 'approved_by', 'created_by'
        ).prefetch_related('items__product').all()
    
    @transaction.atomic
    def perform_create(self, serializer):
        items_data = serializer.validated_data.pop('items')
        
        # Create adjustment
        adjustment = serializer.save(
            created_by=self.request.user,
            status='pending'
        )
        
        total_cost_impact = 0
        
        for item_data in items_data:
            product_id = item_data.get('product')
            variant_id = item_data.get('variant')
            expected_qty = item_data.get('expected_quantity', 0)
            counted_qty = item_data.get('counted_quantity', 0)
            
            product = Product.objects.get(id=product_id)
            
            # Get current stock
            stock, created = Stock.objects.get_or_create(
                warehouse=adjustment.warehouse,
                product_id=product_id,
                variant_id=variant_id,
                defaults={
                    'quantity': 0,
                    'reorder_point': product.reorder_point
                }
            )
            
            # Use system quantity if expected not provided
            if expected_qty == 0:
                expected_qty = stock.quantity
            
            # Create adjustment item
            adj_item = StockAdjustmentItem.objects.create(
                adjustment=adjustment,
                product_id=product_id,
                variant_id=variant_id,
                expected_quantity=expected_qty,
                counted_quantity=counted_qty,
                unit_cost=product.cost_price,
                reason=item_data.get('reason', '')
            )
            
            total_cost_impact += adj_item.cost_impact
            
            # Update stock if adjustment is positive (counted > expected)
            # But we'll wait for approval to actually change stock
        
        # Update total cost impact
        adjustment.total_cost_impact = total_cost_impact
        adjustment.save()
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='STOCK_ADJUSTMENT_CREATED',
            details={
                'adjustment_number': adjustment.adjustment_number,
                'warehouse': adjustment.warehouse.name,
                'type': adjustment.adjustment_type,
                'cost_impact': str(total_cost_impact)
            }
        )

class StockAdjustmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = StockAdjustmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return StockAdjustment.objects.prefetch_related(
            'items__product'
        ).select_related('warehouse').all()

class StockAdjustmentApproveView(APIView):
    """Approve or reject stock adjustment"""
    permission_classes = [permissions.IsAuthenticated]
    
    @transaction.atomic
    def post(self, request, id):
        try:
            adjustment = StockAdjustment.objects.prefetch_related('items').get(id=id)
        except StockAdjustment.DoesNotExist:
            return Response({'error': 'Adjustment not found'}, status=404)
        
        action = request.data.get('action')  # approve or reject
        
        if action == 'approve':
            # Apply the adjustments to stock
            for item in adjustment.items.all():
                stock, created = Stock.objects.get_or_create(
                    warehouse=adjustment.warehouse,
                    product=item.product,
                    variant=item.variant,
                    defaults={
                        'quantity': 0,
                        'reorder_point': item.product.reorder_point
                    }
                )
                
                old_quantity = stock.quantity
                stock.quantity = item.counted_quantity
                stock.last_counted = timezone.now()
                stock.save()
                
                # Create stock movement record
                StockMovement.objects.create(
                    product=item.product,
                    variant=item.variant,
                    movement_type='adjustment',
                    quantity=item.difference,
                    previous_quantity=old_quantity,
                    new_quantity=item.counted_quantity,
                    reference_id=adjustment.id,
                    reference_type='stock_adjustment',
                    notes=f"{adjustment.adjustment_type}: {item.reason}",
                    created_by=request.user
                )
            
            adjustment.status = 'approved'
            adjustment.approved_by = request.user
            adjustment.approved_at = timezone.now()
            
        elif action == 'reject':
            adjustment.status = 'rejected'
            adjustment.reason += f"\nRejection reason: {request.data.get('rejection_reason', '')}"
        
        else:
            return Response({'error': 'Invalid action'}, status=400)
        
        adjustment.save()
        
        ActivityLog.objects.create(
            user=request.user,
            action=f'STOCK_ADJUSTMENT_{action.upper()}D',
            details={
                'adjustment_number': adjustment.adjustment_number,
                'status': adjustment.status
            }
        )
        
        return Response({
            'message': f'Adjustment {action}d successfully',
            'status': adjustment.status
        })

# Cycle Count Views
class CycleCountListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CycleCountCreateSerializer
        return CycleCountSerializer
    
    def get_queryset(self):
        return CycleCount.objects.select_related(
            'warehouse', 'counted_by', 'verified_by'
        ).prefetch_related('items__product').all()
    
    @transaction.atomic
    def perform_create(self, serializer):
        items_data = serializer.validated_data.pop('items')
        
        # Create cycle count
        cycle_count = serializer.save(
            created_by=self.request.user,
            status='scheduled'
        )
        
        for item_data in items_data:
            product_id = item_data.get('product')
            variant_id = item_data.get('variant')
            
            # Get system quantity
            stock = Stock.objects.filter(
                warehouse=cycle_count.warehouse,
                product_id=product_id,
                variant_id=variant_id
            ).first()
            
            system_qty = stock.quantity if stock else 0
            
            CycleCountItem.objects.create(
                cycle_count=cycle_count,
                product_id=product_id,
                variant_id=variant_id,
                system_quantity=system_qty,
                bin_location=item_data.get('bin_location', '')
            )
        
        cycle_count.total_items = len(items_data)
        cycle_count.save()
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='CYCLE_COUNT_CREATED',
            details={
                'count_number': cycle_count.count_number,
                'warehouse': cycle_count.warehouse.name,
                'items': cycle_count.total_items
            }
        )

class CycleCountDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CycleCountSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return CycleCount.objects.prefetch_related('items__product').select_related('warehouse').all()

class CycleCountStartView(APIView):
    """Start a cycle count"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, id):
        try:
            cycle_count = CycleCount.objects.get(id=id)
        except CycleCount.DoesNotExist:
            return Response({'error': 'Cycle count not found'}, status=404)
        
        if cycle_count.status != 'scheduled':
            return Response({'error': 'Count already started or completed'}, status=400)
        
        cycle_count.status = 'in_progress'
        cycle_count.counted_by = request.user
        cycle_count.counted_date = timezone.now().date()
        cycle_count.save()
        
        return Response({'message': 'Cycle count started', 'status': cycle_count.status})

class CycleCountUpdateItemView(APIView):
    """Update counted quantity for an item"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, id):
        serializer = CycleCountUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        try:
            cycle_count = CycleCount.objects.get(id=id)
        except CycleCount.DoesNotExist:
            return Response({'error': 'Cycle count not found'}, status=404)
        
        if cycle_count.status not in ['in_progress', 'completed']:
            return Response({'error': 'Count not in progress'}, status=400)
        
        item_id = serializer.validated_data['item_id']
        
        try:
            item = cycle_count.items.get(id=item_id)
        except CycleCountItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=404)
        
        item.counted_quantity = serializer.validated_data['counted_quantity']
        item.bin_location = serializer.validated_data.get('bin_location', item.bin_location)
        item.notes = serializer.validated_data.get('notes', item.notes)
        item.is_counted = True
        item.counted_at = timezone.now()
        item.save()
        
        # Update cycle count progress
        cycle_count.items_counted = cycle_count.items.filter(is_counted=True).count()
        cycle_count.items_matched = cycle_count.items.filter(
            is_counted=True,
            has_discrepancy=False
        ).count()
        cycle_count.items_discrepancy = cycle_count.items.filter(
            is_counted=True,
            has_discrepancy=True
        ).count()
        
        # Calculate discrepancy value
        discrepancy_value = cycle_count.items.filter(
            is_counted=True,
            has_discrepancy=True
        ).aggregate(
            total=Sum(F('difference') * F('product__cost_price'))
        )['total']
        cycle_count.discrepancy_value = discrepancy_value or 0
        
        if cycle_count.items_counted == cycle_count.total_items:
            cycle_count.status = 'completed'
        
        cycle_count.save()
        
        return Response({
            'message': 'Item updated',
            'item': CycleCountItemSerializer(item).data,
            'progress': {
                'counted': cycle_count.items_counted,
                'total': cycle_count.total_items,
                'matched': cycle_count.items_matched,
                'discrepancy': cycle_count.items_discrepancy
            }
        })

class CycleCountCompleteView(APIView):
    """Complete and verify cycle count"""
    permission_classes = [permissions.IsAuthenticated]
    
    @transaction.atomic
    def post(self, request, id):
        try:
            cycle_count = CycleCount.objects.prefetch_related('items').get(id=id)
        except CycleCount.DoesNotExist:
            return Response({'error': 'Cycle count not found'}, status=404)
        
        if cycle_count.status != 'completed':
            return Response({'error': 'Count not completed yet'}, status=400)
        
        action = request.data.get('action')  # verify or reject
        
        if action == 'verify':
            # Apply corrections for items with discrepancies
            for item in cycle_count.items.filter(has_discrepancy=True):
                stock, created = Stock.objects.get_or_create(
                    warehouse=cycle_count.warehouse,
                    product=item.product,
                    variant=item.variant,
                    defaults={'quantity': 0}
                )
                
                old_quantity = stock.quantity
                stock.quantity = item.counted_quantity
                stock.last_counted = timezone.now()
                stock.save()
                
                # Create stock movement
                StockMovement.objects.create(
                    product=item.product,
                    variant=item.variant,
                    movement_type='cycle_count',
                    quantity=item.difference,
                    previous_quantity=old_quantity,
                    new_quantity=item.counted_quantity,
                    reference_id=cycle_count.id,
                    reference_type='cycle_count',
                    notes=f"Cycle count correction",
                    created_by=request.user
                )
                
                item.is_verified = True
                item.verified_at = timezone.now()
                item.save()
            
            cycle_count.status = 'verified'
            cycle_count.verified_by = request.user
            cycle_count.verified_date = timezone.now().date()
            
        elif action == 'reject':
            cycle_count.status = 'scheduled'  # Reset to scheduled
            cycle_count.notes += f"\nRejected: {request.data.get('reason', '')}"
            
            # Reset counted quantities
            cycle_count.items.update(
                counted_quantity=None,
                is_counted=False,
                has_discrepancy=False
            )
            cycle_count.items_counted = 0
            cycle_count.items_matched = 0
            cycle_count.items_discrepancy = 0
            cycle_count.discrepancy_value = 0
        
        else:
            return Response({'error': 'Invalid action'}, status=400)
        
        cycle_count.save()
        
        ActivityLog.objects.create(
            user=request.user,
            action=f'CYCLE_COUNT_{action.upper()}D',
            details={
                'count_number': cycle_count.count_number,
                'status': cycle_count.status
            }
        )
        
        return Response({
            'message': f'Cycle count {action}d successfully',
            'status': cycle_count.status
        })

# Reorder Views
class ReorderRequestListView(generics.ListAPIView):
    """List and generate reorder requests"""
    serializer_class = ReorderRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return ReorderRequest.objects.select_related(
            'product', 'warehouse', 'suggested_supplier'
        ).all()

class GenerateReorderRequestsView(APIView):
    """Generate automatic reorder requests based on stock levels"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        warehouse_id = request.data.get('warehouse_id')
        
        # Get all stock items below reorder point
        stocks = Stock.objects.filter(
            available_quantity__lte=F('reorder_point')
        )
        
        if warehouse_id:
            stocks = stocks.filter(warehouse_id=warehouse_id)
        
        stocks = stocks.select_related('product', 'warehouse')
        
        created_count = 0
        
        for stock in stocks:
            # Calculate suggested order quantity
            # Simple formula: (average daily sales * lead time) - current stock
            avg_daily_sales = 10  # This would come from sales history
            lead_time = 7  # This would come from supplier product info
            suggested_qty = max(
                stock.reorder_point * 2 - stock.available_quantity,
                0
            )
            
            if suggested_qty > 0:
                # Determine priority
                if stock.available_quantity <= 0:
                    priority = 'critical'
                elif stock.available_quantity <= stock.reorder_point / 2:
                    priority = 'high'
                elif stock.available_quantity <= stock.reorder_point:
                    priority = 'medium'
                else:
                    priority = 'low'
                
                # Check if already have pending request
                existing = ReorderRequest.objects.filter(
                    product=stock.product,
                    warehouse=stock.warehouse,
                    status='pending'
                ).first()
                
                if not existing:
                    # Get preferred supplier from product's supplier list
                    preferred_supplier = stock.product.supplier_products.filter(
                        is_preferred=True
                    ).first()
                    
                    ReorderRequest.objects.create(
                        product=stock.product,
                        variant=stock.variant,
                        warehouse=stock.warehouse,
                        current_stock=stock.available_quantity,
                        reorder_point=stock.reorder_point,
                        suggested_quantity=suggested_qty,
                        average_daily_sales=avg_daily_sales,
                        lead_time_days=lead_time,
                        priority=priority,
                        suggested_supplier=preferred_supplier.supplier if preferred_supplier else None
                    )
                    created_count += 1
        
        return Response({
            'message': f'Generated {created_count} reorder requests',
            'count': created_count
        })

# Inventory Dashboard
class InventoryDashboardView(APIView):
    """Inventory dashboard with key metrics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Total inventory value
        total_value = Stock.objects.aggregate(
            total=Sum(F('quantity') * F('product__cost_price'))
        )['total'] or 0
        
        # Total items in stock
        total_items = Stock.objects.filter(quantity__gt=0).count()
        
        # Low stock items
        low_stock_count = Stock.objects.filter(
            available_quantity__lte=F('reorder_point')
        ).count()
        
        # Out of stock items
        out_of_stock_count = Stock.objects.filter(available_quantity=0).count()
        
        # Expiring batches
        today = timezone.now().date()
        thirty_days_later = today + timedelta(days=30)
        expiring_count = Batch.objects.filter(
            expiry_date__range=[today, thirty_days_later],
            current_quantity__gt=0
        ).count()
        
        # Stock by warehouse
        warehouse_stats = Warehouse.objects.annotate(
            stock_value=Sum(F('stock_items__quantity') * F('stock_items__product__cost_price')),
            item_count=Count('stock_items', filter=Q(stock_items__quantity__gt=0))
        ).values('name', 'stock_value', 'item_count')
        
        # Top 5 products by value
        top_products = Stock.objects.filter(
            quantity__gt=0
        ).annotate(
            value=F('quantity') * F('product__selling_price')
        ).select_related('product').order_by('-value')[:10].values(
            'product__name', 'product__sku', 'quantity', 'value'
        )
        
        # Recent stock movements (last 10)
        recent_movements = StockMovement.objects.select_related(
            'product', 'created_by'
        ).order_by('-created_at')[:15]
        
        from products.serializers import StockMovementSerializer
        
        return Response({
            'summary': {
                'total_inventory_value': total_value,
                'total_products_in_stock': total_items,
                'low_stock_items': low_stock_count,
                'out_of_stock_items': out_of_stock_count,
                'expiring_batches': expiring_count,
            },
            'warehouse_stats': warehouse_stats,
            'top_products_by_value': top_products,
            'recent_movements': StockMovementSerializer(recent_movements, many=True).data
        })
