from rest_framework import generics, permissions, status, filters, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Sum, Count, Avg
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import timedelta
from .models import (
    PurchaseOrder, PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem,
    PurchasePayment, PurchaseReturn, PurchaseReturnItem, SupplierInvoice
)
from .serializers import (
    PurchaseOrderListSerializer, PurchaseOrderDetailSerializer, PurchaseOrderCreateSerializer,
    GoodsReceiptSerializer, GoodsReceiptCreateSerializer,
    PurchasePaymentSerializer, PurchasePaymentCreateSerializer,
    PurchaseReturnSerializer, PurchaseReturnCreateSerializer,
    SupplierInvoiceSerializer
)
from products.models import Product, StockMovement
from suppliers.models import Supplier
from accounts.models import ActivityLog
import django_filters

# Purchase Order Filters
class PurchaseOrderFilter(django_filters.FilterSet):
    min_amount = django_filters.NumberFilter(field_name="total_amount", lookup_expr='gte')
    max_amount = django_filters.NumberFilter(field_name="total_amount", lookup_expr='lte')
    from_date = django_filters.DateFilter(field_name="order_date", lookup_expr='gte')
    to_date = django_filters.DateFilter(field_name="order_date", lookup_expr='lte')
    supplier = django_filters.UUIDFilter(field_name="supplier__id")
    order_status = django_filters.ChoiceFilter(choices=PurchaseOrder.ORDER_STATUS)
    payment_status = django_filters.ChoiceFilter(choices=PurchaseOrder.PAYMENT_STATUS)
    overdue = django_filters.BooleanFilter(method='filter_overdue')
    
    class Meta:
        model = PurchaseOrder
        fields = ['order_status', 'payment_status', 'supplier']
    
    def filter_overdue(self, queryset, name, value):
        if value:
            today = timezone.now().date()
            return queryset.filter(
                expected_delivery_date__lt=today,
                payment_status__in=['pending', 'partial']
            )
        return queryset

# Purchase Order Views
class PurchaseOrderListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PurchaseOrderFilter
    search_fields = ['po_number', 'supplier__company_name']
    ordering_fields = ['order_date', 'total_amount', 'due_amount']
    
    def get_queryset(self):
        return PurchaseOrder.objects.select_related('supplier', 'requested_by').all()
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return PurchaseOrderListSerializer
        return PurchaseOrderCreateSerializer
    
    def perform_create(self, serializer):
        purchase_order = serializer.save(created_by=self.request.user)
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='PURCHASE_ORDER_CREATED',
            details={
                'po_number': purchase_order.po_number,
                'supplier': purchase_order.supplier.company_name,
                'amount': str(purchase_order.total_amount)
            }
        )

class PurchaseOrderRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return PurchaseOrder.objects.prefetch_related(
            'items__product', 'items__variant', 'payments', 'returns', 'goods_receipts'
        ).select_related('supplier', 'requested_by').all()
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return PurchaseOrderDetailSerializer
        return PurchaseOrderCreateSerializer
    
    def perform_update(self, serializer):
        purchase_order = serializer.save(updated_by=self.request.user)
        ActivityLog.objects.create(
            user=self.request.user,
            action='PURCHASE_ORDER_UPDATED',
            details={
                'po_number': purchase_order.po_number,
                'status': purchase_order.order_status
            }
        )
    
    def perform_destroy(self, instance):
        # Check if order can be deleted
        if instance.order_status not in ['draft', 'cancelled']:
            raise serializers.ValidationError("Cannot delete non-draft purchase order")
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='PURCHASE_ORDER_DELETED',
            details={'po_number': instance.po_number}
        )
        instance.delete()

# Purchase Order Status Update
class PurchaseOrderStatusUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, id):
        try:
            purchase_order = PurchaseOrder.objects.get(id=id)
        except PurchaseOrder.DoesNotExist:
            return Response({'error': 'Purchase order not found'}, status=404)
        
        new_status = request.data.get('status')
        if new_status not in dict(PurchaseOrder.ORDER_STATUS):
            return Response({'error': 'Invalid status'}, status=400)
        
        with transaction.atomic():
            old_status = purchase_order.order_status
            purchase_order.order_status = new_status
            purchase_order.updated_by = request.user
            
            if new_status == 'approved':
                purchase_order.approved_by = request.user
            
            purchase_order.save()
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='PURCHASE_ORDER_STATUS_UPDATED',
                details={
                    'po_number': purchase_order.po_number,
                    'old_status': old_status,
                    'new_status': new_status
                }
            )
            
            return Response({
                'message': f'Purchase order status updated to {new_status}',
                'po_number': purchase_order.po_number
            })

# Goods Receipt Views
class GoodsReceiptListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return GoodsReceiptCreateSerializer
        return GoodsReceiptSerializer
    
    def get_queryset(self):
        return GoodsReceipt.objects.select_related('purchase_order', 'received_by').prefetch_related('items').all()
    
    def perform_create(self, serializer):
        items_data = serializer.validated_data.pop('items')
        purchase_order = serializer.validated_data.get('purchase_order')
        
        with transaction.atomic():
            # Create goods receipt
            goods_receipt = serializer.save(
                received_by=self.request.user,
                status='partial'
            )
            
            total_received = 0
            total_items = purchase_order.items.count()
            
            # Process received items
            for item_data in items_data:
                po_item_id = item_data.get('purchase_order_item_id')
                received_qty = item_data.get('received_quantity', 0)
                rejected_qty = item_data.get('rejected_quantity', 0)
                
                try:
                    po_item = PurchaseOrderItem.objects.get(id=po_item_id, purchase_order=purchase_order)
                except PurchaseOrderItem.DoesNotExist:
                    raise serializers.ValidationError(f"PO Item {po_item_id} not found")
                
                # Create receipt item
                receipt_item = GoodsReceiptItem.objects.create(
                    goods_receipt=goods_receipt,
                    purchase_order_item=po_item,
                    ordered_quantity=po_item.quantity,
                    received_quantity=received_qty,
                    rejected_quantity=rejected_qty,
                    batch_number=item_data.get('batch_number', ''),
                    manufacturing_date=item_data.get('manufacturing_date'),
                    expiry_date=item_data.get('expiry_date'),
                    storage_location=item_data.get('storage_location', ''),
                    quality_notes=item_data.get('quality_notes', ''),
                    notes=item_data.get('notes', '')
                )
                
                # Update PO item received quantity
                po_item.received_quantity += receipt_item.accepted_quantity
                po_item.rejected_quantity += rejected_qty
                po_item.save()
                
                # Update stock for accepted items
                if receipt_item.accepted_quantity > 0:
                    product = po_item.product
                    old_stock = product.current_stock
                    product.current_stock += receipt_item.accepted_quantity
                    
                    # Update cost price if needed (weighted average)
                    new_total_value = (product.cost_price * old_stock) + (po_item.unit_price * receipt_item.accepted_quantity)
                    new_total_quantity = old_stock + receipt_item.accepted_quantity
                    if new_total_quantity > 0:
                        product.cost_price = new_total_value / new_total_quantity
                    
                    product.save()
                    
                    # Create stock movement record
                    StockMovement.objects.create(
                        product=product,
                        variant=po_item.variant,
                        movement_type='purchase',
                        quantity=receipt_item.accepted_quantity,
                        previous_quantity=old_stock,
                        new_quantity=product.current_stock,
                        reference_id=goods_receipt.id,
                        reference_type='goods_receipt',
                        notes=f"GRN: {goods_receipt.grn_number}",
                        created_by=self.request.user
                    )
                
                total_received += 1
            
            # Update purchase order status
            all_items_received = all(
                item.received_quantity >= item.quantity 
                for item in purchase_order.items.all()
            )
            
            if all_items_received:
                purchase_order.order_status = 'received'
                goods_receipt.status = 'completed'
            elif total_received > 0:
                purchase_order.order_status = 'partially_received'
            
            purchase_order.delivery_date = timezone.now().date()
            purchase_order.save()
            goods_receipt.save()
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='GOODS_RECEIPT_CREATED',
                details={
                    'grn_number': goods_receipt.grn_number,
                    'po_number': purchase_order.po_number,
                    'items_received': total_received
                }
            )

class GoodsReceiptRetrieveView(generics.RetrieveAPIView):
    serializer_class = GoodsReceiptSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return GoodsReceipt.objects.prefetch_related('items__purchase_order_item__product').all()

# Purchase Payment Views
class PurchasePaymentListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PurchasePaymentCreateSerializer
        return PurchasePaymentSerializer
    
    def get_queryset(self):
        order_id = self.kwargs.get('order_id')
        return PurchasePayment.objects.filter(purchase_order_id=order_id).select_related('paid_by')
    
    def perform_create(self, serializer):
        order_id = self.kwargs.get('order_id')
        purchase_order = PurchaseOrder.objects.get(id=order_id)
        
        with transaction.atomic():
            payment = serializer.save(
                purchase_order=purchase_order,
                paid_by=self.request.user,
                status='completed'
            )
            
            # Update order payment status
            purchase_order.paid_amount += payment.amount
            purchase_order.due_amount = purchase_order.total_amount - purchase_order.paid_amount
            
            if purchase_order.due_amount <= 0:
                purchase_order.payment_status = 'paid'
            elif purchase_order.paid_amount > 0:
                purchase_order.payment_status = 'partial'
            
            purchase_order.save()
            
            # Update supplier outstanding
            supplier = purchase_order.supplier
            supplier.outstanding_amount -= payment.amount
            supplier.save()
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='PURCHASE_PAYMENT_MADE',
                details={
                    'po_number': purchase_order.po_number,
                    'amount': str(payment.amount),
                    'payment_method': payment.payment_method
                }
            )

# Purchase Return Views
class PurchaseReturnListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PurchaseReturnCreateSerializer
        return PurchaseReturnSerializer
    
    def get_queryset(self):
        order_id = self.kwargs.get('order_id')
        return PurchaseReturn.objects.filter(purchase_order_id=order_id).prefetch_related('items')
    
    def perform_create(self, serializer):
        order_id = self.kwargs.get('order_id')
        purchase_order = PurchaseOrder.objects.get(id=order_id)
        items_data = serializer.validated_data.pop('items')
        
        with transaction.atomic():
            # Create return
            purchase_return = serializer.save(
                purchase_order=purchase_order,
                created_by=self.request.user,
                status='requested'
            )
            
            total_refund = 0
            
            # Process return items
            for item_data in items_data:
                receipt_item_id = item_data.get('receipt_item_id')
                quantity = item_data.get('quantity')
                
                try:
                    receipt_item = GoodsReceiptItem.objects.get(id=receipt_item_id)
                except GoodsReceiptItem.DoesNotExist:
                    raise serializers.ValidationError(f"Receipt item {receipt_item_id} not found")
                
                if quantity > receipt_item.accepted_quantity:
                    raise serializers.ValidationError(f"Cannot return more than {receipt_item.accepted_quantity} items")
                
                # Calculate refund amount
                refund_amount = receipt_item.purchase_order_item.unit_price * quantity
                
                return_item = PurchaseReturnItem.objects.create(
                    purchase_return=purchase_return,
                    receipt_item=receipt_item,
                    quantity=quantity,
                    unit_price=receipt_item.purchase_order_item.unit_price,
                    refund_amount=refund_amount,
                    condition=item_data.get('condition', 'damaged'),
                    notes=item_data.get('notes', '')
                )
                
                total_refund += refund_amount
                
                # Remove from stock
                product = receipt_item.purchase_order_item.product
                old_stock = product.current_stock
                product.current_stock -= quantity
                product.save()
                
                StockMovement.objects.create(
                    product=product,
                    variant=receipt_item.purchase_order_item.variant,
                    movement_type='return',
                    quantity=-quantity,
                    previous_quantity=old_stock,
                    new_quantity=product.current_stock,
                    reference_id=purchase_return.id,
                    reference_type='purchase_return',
                    notes=f"Return to Supplier: {purchase_order.supplier.company_name}",
                    created_by=self.request.user
                )
            
            # Update return with total refund amount
            purchase_return.refund_amount = total_refund
            purchase_return.save()
            
            # Update order totals
            purchase_order.total_amount -= total_refund
            purchase_order.due_amount -= total_refund
            if purchase_order.paid_amount > purchase_order.total_amount:
                purchase_order.paid_amount = purchase_order.total_amount
            purchase_order.save()
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='PURCHASE_RETURN_CREATED',
                details={
                    'return_number': purchase_return.return_number,
                    'po_number': purchase_order.po_number,
                    'refund_amount': str(total_refund)
                }
            )

class PurchaseReturnApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, id):
        try:
            purchase_return = PurchaseReturn.objects.get(id=id)
        except PurchaseReturn.DoesNotExist:
            return Response({'error': 'Return not found'}, status=404)
        
        action = request.data.get('action')  # approve or reject
        if action not in ['approve', 'reject']:
            return Response({'error': 'Invalid action'}, status=400)
        
        with transaction.atomic():
            old_status = purchase_return.status
            
            if action == 'approve':
                purchase_return.status = 'approved'
                purchase_return.approved_by = request.user
                purchase_return.approved_at = timezone.now()
                
                # Update supplier outstanding
                supplier = purchase_return.purchase_order.supplier
                supplier.outstanding_amount -= purchase_return.refund_amount
                supplier.save()
            
            else:  # reject
                purchase_return.status = 'rejected'
                purchase_return.notes += f"\nRejection reason: {request.data.get('rejection_reason', '')}"
            
            purchase_return.save()
            
            ActivityLog.objects.create(
                user=self.request.user,
                action=f'PURCHASE_RETURN_{action.upper()}D',
                details={
                    'return_number': purchase_return.return_number,
                    'old_status': old_status,
                    'new_status': purchase_return.status
                }
            )
            
            return Response({
                'message': f'Return {action}d successfully',
                'status': purchase_return.status
            })

# Supplier Invoice Views
class SupplierInvoiceListCreateView(generics.ListCreateAPIView):
    serializer_class = SupplierInvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return SupplierInvoice.objects.select_related('supplier', 'purchase_order', 'created_by').all()
    
    def perform_create(self, serializer):
        invoice = serializer.save(created_by=self.request.user)
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='SUPPLIER_INVOICE_CREATED',
            details={
                'invoice_number': invoice.invoice_number,
                'supplier': invoice.supplier.company_name,
                'amount': str(invoice.total_amount)
            }
        )

# Purchase Dashboard/Statistics
class PurchaseDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        
        # This month's purchases
        month_purchases = PurchaseOrder.objects.filter(
            order_date__gte=start_of_month,
            order_status='received'
        ).aggregate(
            total=Sum('total_amount'),
            count=Count('id')
        )
        
        # Pending orders
        pending_orders = PurchaseOrder.objects.filter(
            order_status__in=['approved', 'ordered']
        ).count()
        
        # Orders due this week
        week_end = today + timedelta(days=7)
        due_this_week = PurchaseOrder.objects.filter(
            expected_delivery_date__range=[today, week_end],
            order_status__in=['approved', 'ordered']
        ).count()
        
        # Overdue orders
        overdue_orders = PurchaseOrder.objects.filter(
            expected_delivery_date__lt=today,
            order_status__in=['approved', 'ordered', 'partially_received']
        ).count()
        
        # Outstanding payments
        outstanding = PurchaseOrder.objects.filter(
            payment_status__in=['pending', 'partial']
        ).aggregate(
            total=Sum('due_amount')
        )['total'] or 0
        
        # Top suppliers by purchase value
        top_suppliers = PurchaseOrder.objects.filter(
            order_status='received'
        ).values(
            'supplier__company_name'
        ).annotate(
            total=Sum('total_amount'),
            orders=Count('id')
        ).order_by('-total')[:10]
        
        # Purchase by status
        orders_by_status = PurchaseOrder.objects.values('order_status').annotate(
            count=Count('id'),
            total=Sum('total_amount')
        )
        
        # Recent POs
        recent_pos = PurchaseOrder.objects.select_related(
            'supplier'
        ).order_by('-order_date')[:10].values(
            'po_number', 'supplier__company_name',
            'total_amount', 'order_status', 'order_date'
        )
        
        return Response({
            'month': {
                'purchases': month_purchases['total'] or 0,
                'orders': month_purchases['count'] or 0
            },
            'pending_orders': pending_orders,
            'due_this_week': due_this_week,
            'overdue_orders': overdue_orders,
            'outstanding_payments': outstanding,
            'top_suppliers': top_suppliers,
            'orders_by_status': orders_by_status,
            'recent_pos': recent_pos
        })

# Purchase Report
class PurchaseReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        report_type = request.query_params.get('type', 'monthly')
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        
        if report_type == 'monthly':
            # Monthly purchases for last 12 months
            monthly_purchases = []
            current_date = timezone.now()
            
            for i in range(12):
                month_start = current_date.replace(day=1) - timedelta(days=30*i)
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                
                purchases = PurchaseOrder.objects.filter(
                    order_date__range=[month_start.date(), month_end.date()],
                    order_status='received'
                ).aggregate(
                    total=Sum('total_amount'),
                    count=Count('id')
                )
                
                monthly_purchases.append({
                    'month': month_start.strftime('%B %Y'),
                    'purchases': purchases['total'] or 0,
                    'orders': purchases['count'] or 0
                })
            
            return Response({
                'report_type': 'monthly',
                'data': monthly_purchases[::-1]
            })
        
        elif report_type == 'supplier':
            # Purchases by supplier
            supplier_purchases = PurchaseOrder.objects.filter(
                order_status='received'
            ).values(
                'supplier__company_name'
            ).annotate(
                total=Sum('total_amount'),
                orders=Count('id'),
                avg_order=Avg('total_amount')
            ).order_by('-total')
            
            return Response({
                'report_type': 'supplier',
                'data': supplier_purchases
            })
        
        elif report_type == 'product':
            # Purchases by product
            product_purchases = PurchaseOrderItem.objects.filter(
                purchase_order__order_status='received'
            ).values(
                'product__name', 'product__sku'
            ).annotate(
                total_quantity=Sum('quantity'),
                total_value=Sum('total'),
                avg_price=Avg('unit_price')
            ).order_by('-total_value')[:20]
            
            return Response({
                'report_type': 'product',
                'data': product_purchases
            })
        
        elif report_type == 'custom':
            if not from_date or not to_date:
                return Response({'error': 'from_date and to_date required'}, status=400)
            
            purchases = PurchaseOrder.objects.filter(
                order_date__range=[from_date, to_date],
                order_status='received'
            )
            
            total_purchases = purchases.aggregate(total=Sum('total_amount'))['total'] or 0
            total_orders = purchases.count()
            avg_order_value = total_purchases / total_orders if total_orders > 0 else 0
            
            # Purchases by supplier
            supplier_breakdown = purchases.values(
                'supplier__company_name'
            ).annotate(
                total=Sum('total_amount'),
                orders=Count('id')
            ).order_by('-total')
            
            # Purchases by category
            category_breakdown = PurchaseOrderItem.objects.filter(
                purchase_order__in=purchases
            ).values(
                'product__category__name'
            ).annotate(
                total=Sum('total'),
                quantity=Sum('quantity')
            ).order_by('-total')
            
            return Response({
                'report_type': 'custom',
                'period': {'from': from_date, 'to': to_date},
                'summary': {
                    'total_purchases': total_purchases,
                    'total_orders': total_orders,
                    'avg_order_value': avg_order_value
                },
                'supplier_breakdown': supplier_breakdown,
                'category_breakdown': category_breakdown
            })
