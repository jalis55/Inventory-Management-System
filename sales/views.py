from rest_framework import generics, permissions, status, filters, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Sum, Count, Avg
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from .models import (
    SalesOrder, SalesOrderItem, SalesPayment, 
    SalesReturn, SalesReturnItem, Invoice,
    Quotation, QuotationItem
)
from .serializers import (
    SalesOrderListSerializer, SalesOrderDetailSerializer, SalesOrderCreateSerializer,
    SalesPaymentSerializer, SalesPaymentCreateSerializer,
    SalesReturnSerializer, SalesReturnCreateSerializer,
    InvoiceSerializer, QuotationSerializer, QuotationCreateSerializer
)
from products.models import Product, StockMovement
from accounts.models import ActivityLog
from customers.models import Customer, CustomerLoyalty
import django_filters

# Sales Order Filters
class SalesOrderFilter(django_filters.FilterSet):
    min_amount = django_filters.NumberFilter(field_name="total_amount", lookup_expr='gte')
    max_amount = django_filters.NumberFilter(field_name="total_amount", lookup_expr='lte')
    from_date = django_filters.DateFilter(field_name="order_date", lookup_expr='date__gte')
    to_date = django_filters.DateFilter(field_name="order_date", lookup_expr='date__lte')
    customer = django_filters.UUIDFilter(field_name="customer__id")
    sales_person = django_filters.UUIDFilter(field_name="sales_person__id")
    payment_status = django_filters.ChoiceFilter(choices=SalesOrder.PAYMENT_STATUS)
    order_status = django_filters.ChoiceFilter(choices=SalesOrder.ORDER_STATUS)
    overdue = django_filters.BooleanFilter(method='filter_overdue')
    
    class Meta:
        model = SalesOrder
        fields = ['order_status', 'payment_status', 'customer', 'sales_person']
    
    def filter_overdue(self, queryset, name, value):
        if value:
            today = timezone.now().date()
            return queryset.filter(
                expected_delivery_date__lt=today,
                payment_status__in=['pending', 'partial']
            )
        return queryset

# Sales Order Views
class SalesOrderListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SalesOrderFilter
    search_fields = ['order_number', 'invoice_number', 'customer__first_name', 'customer__last_name']
    ordering_fields = ['order_date', 'total_amount', 'due_amount']
    
    def get_queryset(self):
        return SalesOrder.objects.select_related('customer', 'sales_person').all()
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return SalesOrderListSerializer
        return SalesOrderCreateSerializer
    
    def perform_create(self, serializer):
        with transaction.atomic():
            sales_order = serializer.save(created_by=self.request.user)
            
            # Update stock levels
            for item in sales_order.items.all():
                product = item.product
                old_stock = product.current_stock
                
                # Reduce stock
                product.current_stock -= item.quantity
                product.save()
                
                # Create stock movement record
                StockMovement.objects.create(
                    product=product,
                    variant=item.variant,
                    movement_type='sale',
                    quantity=-item.quantity,
                    previous_quantity=old_stock,
                    new_quantity=product.current_stock,
                    reference_id=sales_order.id,
                    reference_type='sales_order',
                    notes=f"Sales Order: {sales_order.order_number}",
                    created_by=self.request.user
                )
            
            # Update customer loyalty points (if applicable)
            if hasattr(sales_order.customer, 'loyalty'):
                loyalty = sales_order.customer.loyalty
                points_earned = int(sales_order.total_amount / 100)  # 1 point per 100 spent
                loyalty.points += points_earned
                loyalty.lifetime_points += points_earned
                loyalty.lifetime_purchase += sales_order.total_amount
                loyalty.last_activity_date = timezone.now()
                
                # Update tier based on lifetime purchase
                if loyalty.lifetime_purchase >= 100000:
                    loyalty.tier = 'diamond'
                elif loyalty.lifetime_purchase >= 50000:
                    loyalty.tier = 'platinum'
                elif loyalty.lifetime_purchase >= 25000:
                    loyalty.tier = 'gold'
                elif loyalty.lifetime_purchase >= 10000:
                    loyalty.tier = 'silver'
                
                loyalty.save()
                
                # Update customer record
                customer = sales_order.customer
                customer.loyalty_points = loyalty.points
                customer.loyalty_tier = loyalty.tier
                customer.save()
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='SALES_ORDER_CREATED',
                details={
                    'order_number': sales_order.order_number,
                    'customer': sales_order.customer.get_full_name,
                    'amount': str(sales_order.total_amount)
                }
            )

class SalesOrderRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return SalesOrder.objects.prefetch_related(
            'items__product', 'items__variant', 'payments', 'returns'
        ).select_related('customer', 'sales_person').all()
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return SalesOrderDetailSerializer
        return SalesOrderCreateSerializer
    
    def perform_update(self, serializer):
        sales_order = serializer.save(updated_by=self.request.user)
        ActivityLog.objects.create(
            user=self.request.user,
            action='SALES_ORDER_UPDATED',
            details={
                'order_number': sales_order.order_number,
                'status': sales_order.order_status
            }
        )
    
    def perform_destroy(self, instance):
        # Check if order can be deleted
        if instance.payment_status != 'pending':
            raise serializers.ValidationError("Cannot delete order with payments")
        
        with transaction.atomic():
            # Restore stock
            for item in instance.items.all():
                product = item.product
                product.current_stock += item.quantity
                product.save()
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='SALES_ORDER_DELETED',
                details={'order_number': instance.order_number}
            )
            instance.delete()

# Sales Order Status Update
class SalesOrderStatusUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, id):
        try:
            sales_order = SalesOrder.objects.get(id=id)
        except SalesOrder.DoesNotExist:
            return Response({'error': 'Sales order not found'}, status=404)
        
        new_status = request.data.get('status')
        if new_status not in dict(SalesOrder.ORDER_STATUS):
            return Response({'error': 'Invalid status'}, status=400)
        
        with transaction.atomic():
            old_status = sales_order.order_status
            sales_order.order_status = new_status
            sales_order.updated_by = request.user
            
            # Generate invoice when order is confirmed
            if new_status == 'confirmed' and old_status == 'draft' and not hasattr(sales_order, 'invoice'):
                from django.template.loader import render_to_string
                import num2words
                
                # Create invoice
                invoice = Invoice.objects.create(
                    sales_order=sales_order,
                    due_date=sales_order.expected_delivery_date or timezone.now().date() + timedelta(days=7),
                    status='sent',
                    gst_type='cgst_sgst',
                    company_name="Your Company Name",
                    company_address="Your Company Address",
                    company_gst="GSTIN1234567890",
                    company_pan="PAN1234567",
                    company_email="company@email.com",
                    company_phone="+1234567890",
                    customer_name=sales_order.customer.get_full_name,
                    customer_address=sales_order.billing_address,
                    customer_gst=sales_order.customer.gst_number or "",
                    customer_email=sales_order.customer.email,
                    customer_phone=sales_order.customer.phone,
                    subtotal=sales_order.subtotal,
                    discount_total=sales_order.discount_amount,
                    tax_total=sales_order.tax_amount,
                    shipping_total=sales_order.shipping_charge,
                    grand_total=sales_order.total_amount,
                    amount_in_words=num2words.num2words(int(sales_order.total_amount), to='currency', currency='INR'),
                    created_by=request.user
                )
                
                sales_order.invoice_number = invoice.invoice_number
            
            sales_order.save()
            
            ActivityLog.objects.create(
                user=request.user,
                action='SALES_ORDER_STATUS_UPDATED',
                details={
                    'order_number': sales_order.order_number,
                    'old_status': old_status,
                    'new_status': new_status
                }
            )
            
            return Response({
                'message': f'Order status updated to {new_status}',
                'order_number': sales_order.order_number,
                'invoice_number': sales_order.invoice_number if new_status == 'confirmed' else None
            })

# Sales Payment Views
class SalesPaymentListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SalesPaymentCreateSerializer
        return SalesPaymentSerializer
    
    def get_queryset(self):
        order_id = self.kwargs.get('order_id')
        return SalesPayment.objects.filter(sales_order_id=order_id).select_related('received_by')
    
    def perform_create(self, serializer):
        order_id = self.kwargs.get('order_id')
        sales_order = SalesOrder.objects.get(id=order_id)
        
        with transaction.atomic():
            payment = serializer.save(
                sales_order=sales_order,
                received_by=self.request.user,
                status='completed'
            )
            
            # Update order payment status
            sales_order.paid_amount += payment.amount
            sales_order.due_amount = sales_order.total_amount - sales_order.paid_amount
            
            if sales_order.due_amount <= 0:
                sales_order.payment_status = 'paid'
            elif sales_order.paid_amount > 0:
                sales_order.payment_status = 'partial'
            
            sales_order.save()
            
            # Update customer outstanding
            customer = sales_order.customer
            customer.outstanding_amount = customer.outstanding_amount - payment.amount
            customer.save()
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='SALES_PAYMENT_RECEIVED',
                details={
                    'order_number': sales_order.order_number,
                    'amount': str(payment.amount),
                    'payment_method': payment.payment_method
                }
            )

# Sales Return Views
class SalesReturnListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SalesReturnCreateSerializer
        return SalesReturnSerializer
    
    def get_queryset(self):
        order_id = self.kwargs.get('order_id')
        return SalesReturn.objects.filter(sales_order_id=order_id).prefetch_related('items')
    
    def perform_create(self, serializer):
        order_id = self.kwargs.get('order_id')
        sales_order = SalesOrder.objects.get(id=order_id)
        items_data = serializer.validated_data.pop('items')
        
        with transaction.atomic():
            # Create return
            sales_return = serializer.save(
                sales_order=sales_order,
                created_by=self.request.user,
                status='requested',
                refund_amount=0
            )
            
            total_refund = 0
            
            # Process return items
            for item_data in items_data:
                order_item_id = item_data.get('order_item_id')
                quantity = item_data.get('quantity')
                
                try:
                    order_item = SalesOrderItem.objects.get(id=order_item_id, sales_order=sales_order)
                except SalesOrderItem.DoesNotExist:
                    raise serializers.ValidationError(f"Order item {order_item_id} not found")
                
                if quantity > order_item.quantity - order_item.returned_quantity:
                    raise serializers.ValidationError(f"Cannot return more than {order_item.quantity - order_item.returned_quantity} of {order_item.product.name}")
                
                # Calculate refund amount
                refund_amount = (order_item.unit_price * quantity) * (1 - order_item.discount_percent/100)
                
                return_item = SalesReturnItem.objects.create(
                    sales_return=sales_return,
                    order_item=order_item,
                    quantity=quantity,
                    unit_price=order_item.unit_price,
                    refund_amount=refund_amount,
                    condition=item_data.get('condition', 'used'),
                    notes=item_data.get('notes', '')
                )
                
                # Update order item
                order_item.returned_quantity += quantity
                order_item.save()
                
                # Restore stock
                product = order_item.product
                old_stock = product.current_stock
                product.current_stock += quantity
                product.save()
                
                StockMovement.objects.create(
                    product=product,
                    variant=order_item.variant,
                    movement_type='return',
                    quantity=quantity,
                    previous_quantity=old_stock,
                    new_quantity=product.current_stock,
                    reference_id=sales_return.id,
                    reference_type='sales_return',
                    notes=f"Return from Order: {sales_order.order_number}",
                    created_by=self.request.user
                )
                
                total_refund += refund_amount
            
            # Update return with total refund amount
            sales_return.refund_amount = total_refund
            sales_return.save()
            
            # Update order totals
            sales_order.total_amount -= total_refund
            sales_order.due_amount -= total_refund
            sales_order.save()
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='SALES_RETURN_CREATED',
                details={
                    'return_number': sales_return.return_number,
                    'order_number': sales_order.order_number,
                    'refund_amount': str(total_refund)
                }
            )

class SalesReturnApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, id):
        try:
            sales_return = SalesReturn.objects.get(id=id)
        except SalesReturn.DoesNotExist:
            return Response({'error': 'Return not found'}, status=404)
        
        action = request.data.get('action')  # approve or reject
        if action not in ['approve', 'reject']:
            return Response({'error': 'Invalid action'}, status=400)
        
        with transaction.atomic():
            old_status = sales_return.status
            
            if action == 'approve':
                sales_return.status = 'approved'
                sales_return.approved_by = request.user
                sales_return.approved_at = timezone.now()
                
                # Process refund if payment was made
                if sales_return.sales_order.paid_amount > 0:
                    # Create refund payment record
                    SalesPayment.objects.create(
                        sales_order=sales_return.sales_order,
                        amount=-sales_return.refund_amount,
                        payment_method='bank_transfer',
                        status='refunded',
                        notes=f"Refund for return {sales_return.return_number}",
                        received_by=request.user
                    )
                    
                    # Update order payment status
                    sales_return.sales_order.paid_amount -= sales_return.refund_amount
                    sales_return.sales_order.save()
                    
                    # Update customer loyalty points (deduct)
                    if hasattr(sales_return.sales_order.customer, 'loyalty'):
                        points_to_deduct = int(sales_return.refund_amount / 100)
                        loyalty = sales_return.sales_order.customer.loyalty
                        loyalty.points = max(0, loyalty.points - points_to_deduct)
                        loyalty.save()
            
            else:  # reject
                sales_return.status = 'rejected'
                sales_return.staff_notes = request.data.get('rejection_reason', '')
            
            sales_return.save()
            
            ActivityLog.objects.create(
                user=request.user,
                action=f'SALES_RETURN_{action.upper()}D',
                details={
                    'return_number': sales_return.return_number,
                    'old_status': old_status,
                    'new_status': sales_return.status
                }
            )
            
            return Response({
                'message': f'Return {action}d successfully',
                'status': sales_return.status
            })

# Quotation Views
class QuotationListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return QuotationSerializer
        return QuotationCreateSerializer
    
    def get_queryset(self):
        return Quotation.objects.select_related('customer', 'sales_person').prefetch_related('items').all()
    
    def perform_create(self, serializer):
        items_data = serializer.validated_data.pop('items')
        
        with transaction.atomic():
            # Calculate totals
            subtotal = 0
            tax_total = 0
            discount_total = 0
            
            quotation = serializer.save(created_by=self.request.user)
            
            for item_data in items_data:
                product = Product.objects.get(id=item_data['product'])
                variant_id = item_data.get('variant')
                item = QuotationItem.objects.create(
                    quotation=quotation,
                    product=product,
                    variant_id=variant_id,
                    quantity=item_data['quantity'],
                    unit_price=Decimal(str(item_data['unit_price'])),
                    discount_percent=Decimal(str(item_data.get('discount_percent', 0))),
                    tax_rate=Decimal(str(item_data.get('tax_rate', 0))),
                    notes=item_data.get('notes', ''),
                )
                subtotal += item.subtotal
                discount_total += (item.subtotal * item.discount_percent / 100)
                tax_total += (item.total - (item.subtotal - (item.subtotal * item.discount_percent / 100)))
            
            quotation.subtotal = subtotal
            quotation.discount_amount = discount_total
            quotation.tax_amount = tax_total
            quotation.total_amount = subtotal - discount_total + tax_total
            quotation.save()
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='QUOTATION_CREATED',
                details={
                    'quotation_number': quotation.quotation_number,
                    'customer': quotation.customer.get_full_name
                }
            )

class QuotationRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = QuotationSerializer
    lookup_field = 'id'
    
    def get_queryset(self):
        return Quotation.objects.prefetch_related('items__product').all()

class QuotationConvertToOrderView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, id):
        try:
            quotation = Quotation.objects.get(id=id)
        except Quotation.DoesNotExist:
            return Response({'error': 'Quotation not found'}, status=404)
        
        if quotation.status != 'accepted':
            return Response({'error': 'Only accepted quotations can be converted to orders'}, status=400)
        
        with transaction.atomic():
            # Create sales order from quotation
            order_data = {
                'customer': quotation.customer,
                'sales_person': quotation.sales_person,
                'shipping_address': quotation.customer.address_line1,
                'billing_address': quotation.customer.address_line1,
                'customer_notes': quotation.customer_notes,
                'terms_conditions': quotation.terms_conditions,
            }
            
            sales_order = SalesOrder.objects.create(**order_data, created_by=request.user)
            
            # Copy items
            for q_item in quotation.items.all():
                SalesOrderItem.objects.create(
                    sales_order=sales_order,
                    product=q_item.product,
                    variant=q_item.variant,
                    quantity=q_item.quantity,
                    unit_price=q_item.unit_price,
                    discount_percent=q_item.discount_percent,
                    tax_rate=q_item.tax_rate
                )

            sales_order.subtotal = quotation.subtotal
            sales_order.discount_amount = quotation.discount_amount
            sales_order.tax_amount = quotation.tax_amount
            sales_order.total_amount = quotation.total_amount
            sales_order.due_amount = quotation.total_amount
            sales_order.save()
            
            # Update quotation
            quotation.status = 'converted'
            quotation.converted_to_order = sales_order
            quotation.save()
            
            ActivityLog.objects.create(
                user=request.user,
                action='QUOTATION_CONVERTED',
                details={
                    'quotation_number': quotation.quotation_number,
                    'order_number': sales_order.order_number
                }
            )
            
            return Response({
                'message': 'Quotation converted to order successfully',
                'order_id': sales_order.id,
                'order_number': sales_order.order_number
            })

# Sales Dashboard/Statistics
class SalesDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        
        # Today's sales
        today_sales = SalesOrder.objects.filter(
            order_date__date=today,
            order_status='delivered'
        ).aggregate(
            total=Sum('total_amount'),
            count=Count('id')
        )
        
        # This month's sales
        month_sales = SalesOrder.objects.filter(
            order_date__date__gte=start_of_month,
            order_status='delivered'
        ).aggregate(
            total=Sum('total_amount'),
            count=Count('id')
        )
        
        # Pending orders
        pending_orders = SalesOrder.objects.filter(
            order_status__in=['confirmed', 'processing']
        ).count()
        
        # Overdue orders
        overdue_orders = SalesOrder.objects.filter(
            expected_delivery_date__lt=today,
            payment_status__in=['pending', 'partial']
        ).count()
        
        # Sales by status
        orders_by_status = SalesOrder.objects.values('order_status').annotate(
            count=Count('id'),
            total=Sum('total_amount')
        )
        
        # Top products
        top_products = SalesOrderItem.objects.values(
            'product__name', 'product__sku'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_sales=Sum('total')
        ).order_by('-total_sales')[:10]
        
        # Recent orders
        recent_orders = SalesOrder.objects.select_related(
            'customer'
        ).order_by('-order_date')[:10].values(
            'order_number', 'customer__first_name', 'customer__last_name',
            'total_amount', 'order_status', 'order_date'
        )
        
        # Payment summary
        payment_summary = SalesPayment.objects.filter(
            payment_date__date=today
        ).aggregate(
            cash=Sum('amount', filter=Q(payment_method='cash')),
            card=Sum('amount', filter=Q(payment_method='card')),
            online=Sum('amount', filter=Q(payment_method='online'))
        )
        
        return Response({
            'today': {
                'sales': today_sales['total'] or 0,
                'orders': today_sales['count'] or 0
            },
            'month': {
                'sales': month_sales['total'] or 0,
                'orders': month_sales['count'] or 0
            },
            'pending_orders': pending_orders,
            'overdue_orders': overdue_orders,
            'orders_by_status': orders_by_status,
            'top_products': top_products,
            'recent_orders': recent_orders,
            'payment_summary': payment_summary
        })

# Sales Report
class SalesReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        report_type = request.query_params.get('type', 'daily')
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        
        if report_type == 'daily':
            # Daily sales for last 30 days
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
            
            daily_sales = []
            current_date = start_date
            
            while current_date <= end_date:
                sales = SalesOrder.objects.filter(
                    order_date__date=current_date,
                    order_status='delivered'
                ).aggregate(
                    total=Sum('total_amount'),
                    count=Count('id')
                )
                
                daily_sales.append({
                    'date': current_date,
                    'sales': sales['total'] or 0,
                    'orders': sales['count'] or 0
                })
                
                current_date += timedelta(days=1)
            
            return Response({
                'report_type': 'daily',
                'data': daily_sales
            })
        
        elif report_type == 'monthly':
            # Monthly sales for last 12 months
            monthly_sales = []
            current_date = timezone.now()
            
            for i in range(12):
                month_start = current_date.replace(day=1) - timedelta(days=30*i)
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                
                sales = SalesOrder.objects.filter(
                    order_date__date__range=[month_start.date(), month_end.date()],
                    order_status='delivered'
                ).aggregate(
                    total=Sum('total_amount'),
                    count=Count('id')
                )
                
                monthly_sales.append({
                    'month': month_start.strftime('%B %Y'),
                    'sales': sales['total'] or 0,
                    'orders': sales['count'] or 0
                })
            
            return Response({
                'report_type': 'monthly',
                'data': monthly_sales[::-1]
            })
        
        elif report_type == 'custom':
            if not from_date or not to_date:
                return Response({'error': 'from_date and to_date required'}, status=400)
            
            sales = SalesOrder.objects.filter(
                order_date__date__range=[from_date, to_date],
                order_status='delivered'
            )
            
            total_sales = sales.aggregate(total=Sum('total_amount'))['total'] or 0
            total_orders = sales.count()
            avg_order_value = total_sales / total_orders if total_orders > 0 else 0
            
            # Sales by customer
            customer_sales = sales.values(
                'customer__first_name', 'customer__last_name'
            ).annotate(
                total=Sum('total_amount'),
                orders=Count('id')
            ).order_by('-total')[:10]
            
            # Sales by product category
            category_sales = SalesOrderItem.objects.filter(
                sales_order__in=sales
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
                    'total_sales': total_sales,
                    'total_orders': total_orders,
                    'avg_order_value': avg_order_value
                },
                'top_customers': customer_sales,
                'category_breakdown': category_sales
            })
