from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Sum, Count, Avg, F, FloatField
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncQuarter, TruncYear
from django.utils import timezone
from datetime import timedelta, datetime
from collections import defaultdict
import csv
import io
from django.http import HttpResponse
import json

from .models import SavedReport, ReportGeneration, DashboardWidget
from .serializers import (
    SavedReportSerializer, ReportGenerationSerializer, DashboardWidgetSerializer,
    SalesReportSerializer, PurchaseReportSerializer, InventoryReportSerializer,
    CustomerReportSerializer, FinancialReportSerializer, DuesReportSerializer,
    DateRangeSerializer
)
from sales.models import SalesOrder, SalesOrderItem, SalesPayment
from purchases.models import PurchaseOrder, PurchaseOrderItem, PurchasePayment
from inventory.models import Stock, Batch
from customers.models import Customer, CustomerLoyalty
from suppliers.models import Supplier
from products.models import Product, Category, Brand, StockMovement
from dues.models import CustomerDue, SupplierDue
from accounts.models import ActivityLog
from django.contrib.auth import get_user_model

User = get_user_model()


# ==================== SALES REPORTS ====================

class SalesReportView(APIView):
    """Generate sales report"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = SalesReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        data = serializer.validated_data
        start_date = data['date_range']['start_date']
        end_date = data['date_range']['end_date']
        group_by = data.get('group_by', 'day')
        
        # Base queryset
        sales = SalesOrder.objects.filter(
            order_date__date__range=[start_date, end_date],
            order_status='delivered'
        )
        
        # Apply filters
        if data.get('customer_id'):
            sales = sales.filter(customer_id=data['customer_id'])
        
        if data.get('product_id'):
            sales = sales.filter(items__product_id=data['product_id'])
        
        if data.get('category_id'):
            sales = sales.filter(items__product__category_id=data['category_id'])
        
        if data.get('sales_person_id'):
            sales = sales.filter(sales_person_id=data['sales_person_id'])
        
        # Group by time period
        if group_by == 'day':
            sales = sales.annotate(period=TruncDay('order_date'))
        elif group_by == 'week':
            sales = sales.annotate(period=TruncWeek('order_date'))
        elif group_by == 'month':
            sales = sales.annotate(period=TruncMonth('order_date'))
        elif group_by == 'quarter':
            sales = sales.annotate(period=TruncQuarter('order_date'))
        elif group_by == 'year':
            sales = sales.annotate(period=TruncYear('order_date'))
        
        # Aggregate by period
        period_data = sales.values('period').annotate(
            order_count=Count('id'),
            total_sales=Sum('total_amount'),
            subtotal=Sum('subtotal'),
            discount_total=Sum('discount_amount'),
            tax_total=Sum('tax_amount'),
            shipping_total=Sum('shipping_charge'),
            avg_order_value=Avg('total_amount')
        ).order_by('period')
        
        # Product breakdown
        product_sales = SalesOrderItem.objects.filter(
            sales_order__in=sales
        ).values(
            'product__id', 'product__name', 'product__sku'
        ).annotate(
            quantity=Sum('quantity'),
            total=Sum('total'),
            avg_price=Avg('unit_price')
        ).order_by('-total')[:20]
        
        # Payment method breakdown
        payments = SalesPayment.objects.filter(
            sales_order__in=sales,
            status='completed'
        ).values('payment_method').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Customer breakdown
        customer_sales = sales.values(
            'customer__id', 'customer__first_name', 'customer__last_name'
        ).annotate(
            total=Sum('total_amount'),
            orders=Count('id')
        ).order_by('-total')[:10]
        
        # Summary statistics
        summary = sales.aggregate(
            total_orders=Count('id'),
            total_revenue=Sum('total_amount'),
            total_discounts=Sum('discount_amount'),
            total_tax=Sum('tax_amount'),
            avg_order_value=Avg('total_amount')
        )
        
        # Log report generation
        ActivityLog.objects.create(
            user=request.user,
            action='REPORT_GENERATED',
            details={
                'report_type': 'sales',
                'date_range': f"{start_date} to {end_date}"
            }
        )
        
        return Response({
            'period': group_by,
            'date_range': {'start': start_date, 'end': end_date},
            'summary': summary,
            'period_breakdown': period_data,
            'top_products': product_sales,
            'payment_methods': payments,
            'top_customers': customer_sales
        })


class SalesTrendReportView(APIView):
    """Sales trend analysis with YoY/MoM comparison"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Get last 12 months vs previous 12 months
        today = timezone.now().date()
        current_start = today.replace(day=1) - timedelta(days=365)
        current_end = today
        
        previous_start = current_start - timedelta(days=365)
        previous_end = current_start - timedelta(days=1)
        
        # Current period sales
        current_sales = SalesOrder.objects.filter(
            order_date__date__range=[current_start, current_end],
            order_status='delivered'
        ).aggregate(
            total=Sum('total_amount'),
            count=Count('id')
        )
        
        # Previous period sales
        previous_sales = SalesOrder.objects.filter(
            order_date__date__range=[previous_start, previous_end],
            order_status='delivered'
        ).aggregate(
            total=Sum('total_amount'),
            count=Count('id')
        )
        
        # Calculate growth
        revenue_growth = 0
        if previous_sales['total']:
            revenue_growth = ((current_sales['total'] - previous_sales['total']) / previous_sales['total']) * 100
        
        order_growth = 0
        if previous_sales['count']:
            order_growth = ((current_sales['count'] - previous_sales['count']) / previous_sales['count']) * 100
        
        # Monthly breakdown for current year
        year_start = today.replace(month=1, day=1)
        monthly_sales = SalesOrder.objects.filter(
            order_date__date__gte=year_start,
            order_status='delivered'
        ).annotate(
            month=TruncMonth('order_date')
        ).values('month').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('month')
        
        # Best selling day of week
        from django.db.models.functions import ExtractWeekDay
        weekday_sales = SalesOrder.objects.filter(
            order_date__date__gte=year_start,
            order_status='delivered'
        ).annotate(
            weekday=ExtractWeekDay('order_date')
        ).values('weekday').annotate(
            total=Sum('total_amount'),
            count=Count('id'),
            avg=Avg('total_amount')
        ).order_by('-total')
        
        weekday_names = {
            1: 'Sunday', 2: 'Monday', 3: 'Tuesday', 4: 'Wednesday',
            5: 'Thursday', 6: 'Friday', 7: 'Saturday'
        }
        
        for item in weekday_sales:
            item['weekday_name'] = weekday_names.get(item['weekday'], 'Unknown')
        
        return Response({
            'comparison': {
                'current_period': {
                    'start': current_start,
                    'end': current_end,
                    'revenue': current_sales['total'] or 0,
                    'orders': current_sales['count'] or 0
                },
                'previous_period': {
                    'start': previous_start,
                    'end': previous_end,
                    'revenue': previous_sales['total'] or 0,
                    'orders': previous_sales['count'] or 0
                },
                'growth': {
                    'revenue': round(revenue_growth, 2),
                    'orders': round(order_growth, 2)
                }
            },
            'monthly_trend': monthly_sales,
            'weekday_analysis': weekday_sales
        })


# ==================== PURCHASE REPORTS ====================

class PurchaseReportView(APIView):
    """Generate purchase report"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = PurchaseReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        data = serializer.validated_data
        start_date = data['date_range']['start_date']
        end_date = data['date_range']['end_date']
        group_by = data.get('group_by', 'month')
        
        # Base queryset
        purchases = PurchaseOrder.objects.filter(
            order_date__range=[start_date, end_date],
            order_status='received'
        )
        
        # Apply filters
        if data.get('supplier_id'):
            purchases = purchases.filter(supplier_id=data['supplier_id'])
        
        if data.get('product_id'):
            purchases = purchases.filter(items__product_id=data['product_id'])
        
        if data.get('category_id'):
            purchases = purchases.filter(items__product__category_id=data['category_id'])
        
        if data.get('order_status'):
            purchases = purchases.filter(order_status__in=data['order_status'])
        
        # Group by time period
        if group_by == 'day':
            purchases = purchases.annotate(period=TruncDay('order_date'))
        elif group_by == 'week':
            purchases = purchases.annotate(period=TruncWeek('order_date'))
        elif group_by == 'month':
            purchases = purchases.annotate(period=TruncMonth('order_date'))
        elif group_by == 'quarter':
            purchases = purchases.annotate(period=TruncQuarter('order_date'))
        elif group_by == 'year':
            purchases = purchases.annotate(period=TruncYear('order_date'))
        
        # Aggregate by period
        period_data = purchases.values('period').annotate(
            order_count=Count('id'),
            total_purchases=Sum('total_amount'),
            subtotal=Sum('subtotal'),
            discount_total=Sum('discount_amount'),
            tax_total=Sum('tax_amount'),
            shipping_total=Sum('shipping_charge'),
            avg_order_value=Avg('total_amount')
        ).order_by('period')
        
        # Supplier breakdown
        supplier_purchases = purchases.values(
            'supplier__id', 'supplier__company_name'
        ).annotate(
            total=Sum('total_amount'),
            orders=Count('id'),
            avg_order=Avg('total_amount')
        ).order_by('-total')
        
        # Product breakdown
        product_purchases = PurchaseOrderItem.objects.filter(
            purchase_order__in=purchases
        ).values(
            'product__id', 'product__name', 'product__sku'
        ).annotate(
            quantity=Sum('quantity'),
            total=Sum('total'),
            avg_price=Avg('unit_price')
        ).order_by('-total')[:20]
        
        # Category breakdown
        category_purchases = PurchaseOrderItem.objects.filter(
            purchase_order__in=purchases
        ).values(
            'product__category__name'
        ).annotate(
            total=Sum('total'),
            quantity=Sum('quantity')
        ).order_by('-total')
        
        # Summary
        summary = purchases.aggregate(
            total_orders=Count('id'),
            total_spent=Sum('total_amount'),
            total_discounts=Sum('discount_amount'),
            total_tax=Sum('tax_amount'),
            avg_order_value=Avg('total_amount')
        )
        
        return Response({
            'period': group_by,
            'date_range': {'start': start_date, 'end': end_date},
            'summary': summary,
            'period_breakdown': period_data,
            'top_suppliers': supplier_purchases,
            'top_products': product_purchases,
            'category_breakdown': category_purchases
        })


# ==================== INVENTORY REPORTS ====================

class InventoryReportView(APIView):
    """Generate inventory report"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = InventoryReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        data = serializer.validated_data
        
        # Base queryset
        stock = Stock.objects.select_related('product', 'warehouse', 'variant')
        
        if data.get('warehouse_id'):
            stock = stock.filter(warehouse_id=data['warehouse_id'])
        
        if data.get('category_id'):
            stock = stock.filter(product__category_id=data['category_id'])
        
        if not data.get('include_zero_stock'):
            stock = stock.filter(quantity__gt=0)
        
        if data.get('low_stock_only'):
            stock = stock.filter(available_quantity__lte=F('reorder_point'))
        
        # Stock valuation
        total_value = stock.aggregate(
            total=Sum(F('quantity') * F('product__cost_price'))
        )['total'] or 0
        
        total_retail_value = stock.aggregate(
            total=Sum(F('quantity') * F('product__selling_price'))
        )['total'] or 0
        
        # Stock by warehouse
        warehouse_breakdown = stock.values(
            'warehouse__id', 'warehouse__name', 'warehouse__code'
        ).annotate(
            items=Count('id'),
            total_quantity=Sum('quantity'),
            total_value=Sum(F('quantity') * F('product__cost_price'))
        ).order_by('-total_value')
        
        # Stock by category
        category_breakdown = stock.values(
            'product__category__name'
        ).annotate(
            items=Count('id'),
            total_quantity=Sum('quantity'),
            total_value=Sum(F('quantity') * F('product__cost_price'))
        ).order_by('-total_value')
        
        # Low stock items
        low_stock = stock.filter(
            available_quantity__lte=F('reorder_point')
        ).values(
            'product__name', 'product__sku', 'warehouse__name',
            'available_quantity', 'reorder_point'
        )[:50]
        
        # Expiry report
        if data.get('expiring_only'):
            today = timezone.now().date()
            expiry_days = data.get('expiry_days', 30)
            expiry_date = today + timedelta(days=expiry_days)
            
            expiring_batches = Batch.objects.filter(
                expiry_date__range=[today, expiry_date],
                current_quantity__gt=0
            ).select_related('product', 'warehouse').values(
                'batch_number', 'product__name', 'product__sku',
                'warehouse__name', 'current_quantity', 'expiry_date'
            ).order_by('expiry_date')
        else:
            expiring_batches = []
        
        # Stock movement summary
        thirty_days_ago = timezone.now() - timedelta(days=30)
        movements = StockMovement.objects.filter(
            created_at__gte=thirty_days_ago
        ).values('movement_type').annotate(
            total_quantity=Sum('quantity'),
            count=Count('id')
        )
        
        return Response({
            'summary': {
                'total_items': stock.filter(quantity__gt=0).count(),
                'total_quantity': stock.aggregate(total=Sum('quantity'))['total'] or 0,
                'total_value': total_value,
                'total_retail_value': total_retail_value,
                'low_stock_count': low_stock.count()
            },
            'warehouse_breakdown': warehouse_breakdown,
            'category_breakdown': category_breakdown,
            'low_stock': low_stock,
            'expiring_batches': expiring_batches,
            'recent_movements': movements
        })


class InventoryValuationReportView(APIView):
    """Detailed inventory valuation report"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Valuation by costing method (FIFO, Average, etc.)
        products = Product.objects.filter(is_active=True)
        
        valuation_data = []
        total_cost = 0
        total_selling = 0
        
        for product in products:
            total_qty = product.current_stock
            if total_qty > 0:
                cost_value = total_qty * product.cost_price
                selling_value = total_qty * product.selling_price
                potential_profit = selling_value - cost_value
                
                total_cost += cost_value
                total_selling += selling_value
                
                valuation_data.append({
                    'product_id': product.id,
                    'product_name': product.name,
                    'sku': product.sku,
                    'category': product.category.name,
                    'quantity': total_qty,
                    'cost_price': product.cost_price,
                    'selling_price': product.selling_price,
                    'cost_value': cost_value,
                    'selling_value': selling_value,
                    'potential_profit': potential_profit,
                    'margin_percent': (potential_profit / cost_value * 100) if cost_value > 0 else 0
                })
        
        # Sort by value
        valuation_data.sort(key=lambda x: x['cost_value'], reverse=True)
        
        return Response({
            'total_cost_value': total_cost,
            'total_selling_value': total_selling,
            'total_potential_profit': total_selling - total_cost,
            'overall_margin_percent': ((total_selling - total_cost) / total_cost * 100) if total_cost > 0 else 0,
            'items': valuation_data[:100]  # Top 100 items
        })


# ==================== CUSTOMER REPORTS ====================

class CustomerReportView(APIView):
    """Generate customer analysis report"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = CustomerReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        data = serializer.validated_data
        
        # Base queryset
        customers = Customer.objects.filter(is_active=True)
        
        if data.get('customer_type') and data['customer_type'] != 'all':
            customers = customers.filter(customer_type=data['customer_type'])
        
        if data.get('loyalty_tier') and data['loyalty_tier'] != 'all':
            customers = customers.filter(loyalty_tier=data['loyalty_tier'])
        
        # Date range for purchase analysis
        if data.get('date_range'):
            start_date = data['date_range']['start_date']
            end_date = data['date_range']['end_date']
            
            # Get sales in date range
            sales_in_period = SalesOrder.objects.filter(
                customer__in=customers,
                order_date__date__range=[start_date, end_date],
                order_status='delivered'
            )
            
            # Customer purchase stats in period
            customer_stats = sales_in_period.values('customer_id').annotate(
                period_purchases=Sum('total_amount'),
                period_orders=Count('id')
            )
            
            # Convert to dict for easy lookup
            stats_dict = {str(s['customer_id']): s for s in customer_stats}
        else:
            stats_dict = {}
        
        # Build customer list with metrics
        customer_list = []
        for customer in customers:
            # Lifetime stats
            lifetime_sales = SalesOrder.objects.filter(
                customer=customer,
                order_status='delivered'
            ).aggregate(
                total=Sum('total_amount'),
                count=Count('id')
            )
            
            stats = stats_dict.get(str(customer.id), {})
            
            customer_list.append({
                'id': customer.id,
                'name': customer.get_full_name,
                'company': customer.company_name,
                'type': customer.customer_type,
                'email': customer.email,
                'phone': customer.phone,
                'city': customer.city,
                'loyalty_tier': customer.loyalty_tier,
                'loyalty_points': customer.loyalty_points,
                'outstanding': customer.outstanding_amount,
                'lifetime_purchases': lifetime_sales['total'] or 0,
                'lifetime_orders': lifetime_sales['count'] or 0,
                'period_purchases': stats.get('period_purchases', 0),
                'period_orders': stats.get('period_orders', 0),
                'avg_order_value': (lifetime_sales['total'] or 0) / (lifetime_sales['count'] or 1)
            })
        
        # Sort by requested field
        sort_field = data.get('sort_by', 'total_purchases')
        reverse = True
        if sort_field == 'outstanding':
            reverse = True
        
        customer_list.sort(key=lambda x: x.get(sort_field, 0), reverse=reverse)
        
        # Get top N
        top_n = data.get('top_n', 10)
        top_customers = customer_list[:top_n]
        
        # Summary statistics
        summary = {
            'total_customers': len(customer_list),
            'active_in_period': len([c for c in customer_list if c['period_orders'] > 0]),
            'total_outstanding': sum(c['outstanding'] for c in customer_list),
            'avg_lifetime_value': sum(c['lifetime_purchases'] for c in customer_list) / len(customer_list) if customer_list else 0
        }
        
        # Tier breakdown
        tier_breakdown = defaultdict(lambda: {'count': 0, 'total_purchases': 0})
        for c in customer_list:
            tier_breakdown[c['loyalty_tier']]['count'] += 1
            tier_breakdown[c['loyalty_tier']]['total_purchases'] += c['lifetime_purchases']
        
        return Response({
            'summary': summary,
            'tier_breakdown': dict(tier_breakdown),
            'top_customers': top_customers
        })


# ==================== FINANCIAL REPORTS ====================

class ProfitLossReportView(APIView):
    """Generate Profit & Loss statement"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = FinancialReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        data = serializer.validated_data
        start_date = data['date_range']['start_date']
        end_date = data['date_range']['end_date']
        
        # Revenue
        sales = SalesOrder.objects.filter(
            order_date__date__range=[start_date, end_date],
            order_status='delivered'
        )
        
        total_revenue = sales.aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Revenue by category
        revenue_by_category = SalesOrderItem.objects.filter(
            sales_order__in=sales
        ).values('product__category__name').annotate(
            revenue=Sum('total')
        ).order_by('-revenue')
        
        # Cost of Goods Sold
        # For sold items, we need to know their cost price at time of sale
        sold_items = SalesOrderItem.objects.filter(
            sales_order__in=sales
        ).select_related('product')
        
        cogs = 0
        for item in sold_items:
            # Use product's cost price (simplified - in reality would use batch cost)
            cogs += item.quantity * item.product.cost_price
        
        # Gross Profit
        gross_profit = total_revenue - cogs
        gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        # Expenses (Purchases, Operating Expenses, etc.)
        purchases = PurchaseOrder.objects.filter(
            order_date__range=[start_date, end_date],
            order_status='received'
        )
        total_purchases = purchases.aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Discounts given
        total_discounts = sales.aggregate(total=Sum('discount_amount'))['total'] or 0
        
        # Taxes
        total_tax = sales.aggregate(total=Sum('tax_amount'))['total'] or 0
        
        # Net Profit
        net_profit = gross_profit - total_purchases  # Simplified - would include other expenses
        
        # Monthly breakdown
        monthly_data = sales.annotate(
            month=TruncMonth('order_date')
        ).values('month').annotate(
            revenue=Sum('total_amount'),
            cogs=Sum(F('items__quantity') * F('items__product__cost_price')),
            discounts=Sum('discount_amount')
        ).order_by('month')
        
        return Response({
            'period': {'start': start_date, 'end': end_date},
            'income': {
                'total_revenue': total_revenue,
                'revenue_by_category': revenue_by_category
            },
            'cogs': cogs,
            'gross_profit': gross_profit,
            'gross_margin': round(gross_margin, 2),
            'expenses': {
                'purchases': total_purchases,
                'discounts': total_discounts,
                'taxes': total_tax
            },
            'net_profit': net_profit,
            'monthly_breakdown': monthly_data
        })


class DuesAgingReportView(APIView):
    """Generate aging report for receivables and payables"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = DuesReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        data = serializer.validated_data
        as_of_date = data.get('as_of_date', timezone.now().date())
        report_type = data.get('type', 'both')
        buckets = data.get('aging_buckets', [0, 30, 60, 90])
        
        result = {}
        
        # Receivables (Customer Dues)
        if report_type in ['receivables', 'both']:
            receivables = CustomerDue.objects.filter(
                remaining_amount__gt=0
            ).select_related('customer')
            
            aging = {
                'current': 0,
                '1_30': 0,
                '31_60': 0,
                '61_90': 0,
                '91_plus': 0
            }
            
            customer_aging = []
            total_receivables = 0
            
            for due in receivables:
                days = (as_of_date - due.due_date).days if due.due_date < as_of_date else 0
                amount = due.remaining_amount
                total_receivables += amount
                
                # Categorize
                if days <= 0:
                    aging['current'] += amount
                    bucket = 'current'
                elif days <= 30:
                    aging['1_30'] += amount
                    bucket = '1-30 days'
                elif days <= 60:
                    aging['31_60'] += amount
                    bucket = '31-60 days'
                elif days <= 90:
                    aging['61_90'] += amount
                    bucket = '61-90 days'
                else:
                    aging['91_plus'] += amount
                    bucket = '90+ days'
                
                customer_aging.append({
                    'customer': due.customer.get_full_name,
                    'company': due.customer.company_name,
                    'order_number': due.sales_order.order_number,
                    'due_date': due.due_date,
                    'days_overdue': days,
                    'amount': amount,
                    'bucket': bucket
                })
            
            result['receivables'] = {
                'total': total_receivables,
                'aging_summary': aging,
                'details': sorted(customer_aging, key=lambda x: x['days_overdue'], reverse=True)[:100]
            }
        
        # Payables (Supplier Dues)
        if report_type in ['payables', 'both']:
            payables = SupplierDue.objects.filter(
                remaining_amount__gt=0
            ).select_related('supplier')
            
            aging = {
                'current': 0,
                '1_30': 0,
                '31_60': 0,
                '61_90': 0,
                '91_plus': 0
            }
            
            supplier_aging = []
            total_payables = 0
            
            for due in payables:
                days = (as_of_date - due.due_date).days if due.due_date < as_of_date else 0
                amount = due.remaining_amount
                total_payables += amount
                
                if days <= 0:
                    aging['current'] += amount
                    bucket = 'current'
                elif days <= 30:
                    aging['1_30'] += amount
                    bucket = '1-30 days'
                elif days <= 60:
                    aging['31_60'] += amount
                    bucket = '31-60 days'
                elif days <= 90:
                    aging['61_90'] += amount
                    bucket = '61-90 days'
                else:
                    aging['91_plus'] += amount
                    bucket = '90+ days'
                
                supplier_aging.append({
                    'supplier': due.supplier.company_name,
                    'po_number': due.purchase_order.po_number,
                    'due_date': due.due_date,
                    'days_overdue': days,
                    'amount': amount,
                    'bucket': bucket
                })
            
            result['payables'] = {
                'total': total_payables,
                'aging_summary': aging,
                'details': sorted(supplier_aging, key=lambda x: x['days_overdue'], reverse=True)[:100]
            }
        
        return Response({
            'as_of_date': as_of_date,
            **result
        })


# ==================== DASHBOARD WIDGETS ====================

class DashboardWidgetListCreateView(generics.ListCreateAPIView):
    """List and create dashboard widgets"""
    serializer_class = DashboardWidgetSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return DashboardWidget.objects.filter(user=self.request.user, is_active=True)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class DashboardWidgetRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, delete dashboard widgets"""
    serializer_class = DashboardWidgetSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return DashboardWidget.objects.filter(user=self.request.user)


class DashboardDataView(APIView):
    """Get data for all user's dashboard widgets"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        widgets = DashboardWidget.objects.filter(user=request.user, is_active=True)
        
        widget_data = []
        for widget in widgets:
            data = self.get_widget_data(widget)
            widget_data.append({
                'id': widget.id,
                'name': widget.name,
                'type': widget.widget_type,
                'chart_type': widget.chart_type,
                'size': widget.size,
                'position_x': widget.position_x,
                'position_y': widget.position_y,
                'color': widget.color,
                'data': data
            })
        
        return Response(widget_data)
    
    def get_widget_data(self, widget):
        """Fetch data for specific widget type"""
        source = widget.data_source
        
        try:
            if source == 'sales.today':
                today = timezone.now().date()
                sales = SalesOrder.objects.filter(
                    order_date__date=today,
                    order_status='delivered'
                ).aggregate(
                    total=Sum('total_amount'),
                    count=Count('id')
                )
                return {
                    'value': sales['total'] or 0,
                    'label': "Today's Sales",
                    'prefix': '₹',
                    'change': '+12%'  # This would come from comparison
                }
            
            elif source == 'sales.month':
                start_of_month = timezone.now().date().replace(day=1)
                sales = SalesOrder.objects.filter(
                    order_date__date__gte=start_of_month,
                    order_status='delivered'
                ).aggregate(
                    total=Sum('total_amount'),
                    count=Count('id')
                )
                return {
                    'value': sales['total'] or 0,
                    'label': "Month's Sales",
                    'prefix': '₹'
                }
            
            elif source == 'inventory.low_stock':
                count = Stock.objects.filter(
                    available_quantity__lte=F('reorder_point')
                ).count()
                return {
                    'value': count,
                    'label': 'Low Stock Items',
                    'color': 'warning' if count > 0 else 'success'
                }
            
            elif source == 'inventory.total_value':
                value = Stock.objects.aggregate(
                    total=Sum(F('quantity') * F('product__cost_price'))
                )['total'] or 0
                return {
                    'value': value,
                    'label': 'Inventory Value',
                    'prefix': '₹'
                }
            
            elif source == 'customers.total':
                count = Customer.objects.filter(is_active=True).count()
                new_this_month = Customer.objects.filter(
                    created_at__month=timezone.now().month
                ).count()
                return {
                    'value': count,
                    'label': 'Total Customers',
                    'subtext': f'+{new_this_month} this month'
                }
            
            elif source == 'dues.outstanding':
                total = CustomerDue.objects.filter(
                    remaining_amount__gt=0
                ).aggregate(total=Sum('remaining_amount'))['total'] or 0
                overdue = CustomerDue.objects.filter(
                    status='overdue'
                ).aggregate(total=Sum('remaining_amount'))['total'] or 0
                return {
                    'value': total,
                    'label': 'Outstanding Receivables',
                    'prefix': '₹',
                    'subtext': f'Overdue: ₹{overdue}'
                }
            
            elif source == 'sales.chart.monthly':
                # Last 30 days sales
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
                
                sales = SalesOrder.objects.filter(
                    order_date__date__range=[start_date, end_date],
                    order_status='delivered'
                ).annotate(
                    day=TruncDay('order_date')
                ).values('day').annotate(
                    total=Sum('total_amount')
                ).order_by('day')
                
                return {
                    'labels': [s['day'].strftime('%d %b') for s in sales],
                    'values': [float(s['total']) for s in sales],
                    'label': 'Daily Sales'
                }
            
            elif source == 'inventory.chart.category':
                # Stock by category
                categories = Category.objects.annotate(
                    stock_value=Sum(F('products__stock_items__quantity') * F('products__cost_price'))
                ).filter(stock_value__gt=0).values('name', 'stock_value')[:10]
                
                return {
                    'labels': [c['name'] for c in categories],
                    'values': [float(c['stock_value']) for c in categories],
                    'label': 'Inventory by Category'
                }
            
            elif source == 'sales.top_products':
                # Top selling products
                thirty_days_ago = timezone.now() - timedelta(days=30)
                products = SalesOrderItem.objects.filter(
                    sales_order__order_date__gte=thirty_days_ago
                ).values('product__name').annotate(
                    quantity=Sum('quantity'),
                    total=Sum('total')
                ).order_by('-total')[:10]
                
                return {
                    'labels': [p['product__name'][:20] + '...' if len(p['product__name']) > 20 else p['product__name'] for p in products],
                    'values': [float(p['total']) for p in products],
                    'label': 'Top Products (30 days)'
                }
            
            elif source == 'customers.recent':
                # Recent customers
                recent = Customer.objects.order_by('-created_at')[:10].values(
                    'first_name', 'last_name', 'email', 'created_at'
                )
                return {
                    'items': [
                        {
                            'name': f"{c['first_name']} {c['last_name']}",
                            'email': c['email'],
                            'date': c['created_at'].strftime('%d %b %Y')
                        }
                        for c in recent
                    ],
                    'label': 'Recent Customers'
                }
            
            else:
                return {'error': 'Unknown data source'}
                
        except Exception as e:
            return {'error': str(e)}


# ==================== SAVED REPORTS ====================

class SavedReportListCreateView(generics.ListCreateAPIView):
    """List and create saved reports"""
    serializer_class = SavedReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return SavedReport.objects.filter(
            Q(created_by=self.request.user) | Q(is_public=True) | Q(shared_with=self.request.user)
        ).distinct()
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class SavedReportRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, delete saved reports"""
    serializer_class = SavedReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return SavedReport.objects.filter(created_by=self.request.user)


class GenerateSavedReportView(APIView):
    """Generate a saved report"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, id):
        try:
            saved_report = SavedReport.objects.get(id=id)
        except SavedReport.DoesNotExist:
            return Response({'error': 'Report not found'}, status=404)
        
        format = request.data.get('format', saved_report.default_format)
        
        # Create generation record
        generation = ReportGeneration.objects.create(
            saved_report=saved_report,
            report_type=saved_report.report_type,
            parameters=saved_report.config,
            format=format,
            status='processing',
            generated_by=request.user
        )
        
        try:
            import time
            start_time = time.time()
            
            # Generate report based on type
            if saved_report.report_type == 'sales':
                data = self.generate_sales_report(saved_report.config)
            elif saved_report.report_type == 'inventory':
                data = self.generate_inventory_report(saved_report.config)
            elif saved_report.report_type == 'customer':
                data = self.generate_customer_report(saved_report.config)
            elif saved_report.report_type == 'financial':
                data = self.generate_financial_report(saved_report.config)
            else:
                data = {'message': 'Report type not implemented'}
            
            # Generate file based on format
            if format == 'csv':
                file_content = self.generate_csv(data)
                content_type = 'text/csv'
                file_ext = 'csv'
            elif format == 'excel':
                file_content = self.generate_excel(data)
                content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                file_ext = 'xlsx'
            elif format == 'pdf':
                file_content = self.generate_pdf(data, saved_report.name)
                content_type = 'application/pdf'
                file_ext = 'pdf'
            else:
                file_content = json.dumps(data, default=str)
                content_type = 'application/json'
                file_ext = 'json'
            
            # Save file
            filename = f"{saved_report.name}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}"
            
            # In production, save to file storage
            # For now, we'll just return the file
            
            execution_time = time.time() - start_time
            
            generation.status = 'completed'
            generation.completed_at = timezone.now()
            generation.execution_time = execution_time
            # generation.file.save(filename, ContentFile(file_content))
            generation.file_size = len(file_content)
            generation.save()
            
            saved_report.last_generated = timezone.now()
            saved_report.save()
            
            # Return file
            response = HttpResponse(file_content, content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
        except Exception as e:
            generation.status = 'failed'
            generation.error_message = str(e)
            generation.save()
            return Response({'error': str(e)}, status=500)
    
    def generate_sales_report(self, config):
        """Generate sales report data"""
        # Simplified implementation
        return {'message': 'Sales report data'}
    
    def generate_inventory_report(self, config):
        """Generate inventory report data"""
        return {'message': 'Inventory report data'}
    
    def generate_customer_report(self, config):
        """Generate customer report data"""
        return {'message': 'Customer report data'}
    
    def generate_financial_report(self, config):
        """Generate financial report data"""
        return {'message': 'Financial report data'}
    
    def generate_csv(self, data):
        """Generate CSV from data"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        if isinstance(data, dict) and 'items' in data:
            if data['items']:
                writer.writerow(data['items'][0].keys())
                for item in data['items']:
                    writer.writerow(item.values())
        
        return output.getvalue().encode('utf-8')
    
    def generate_excel(self, data):
        """Generate Excel file from data"""
        import xlsxwriter

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()
        
        # Write headers
        if isinstance(data, dict) and 'items' in data and data['items']:
            headers = list(data['items'][0].keys())
            for col, header in enumerate(headers):
                worksheet.write(0, col, header)
            
            # Write data
            for row, item in enumerate(data['items'], start=1):
                for col, header in enumerate(headers):
                    worksheet.write(row, col, item[header])
        
        workbook.close()
        output.seek(0)
        return output.getvalue()
    
    def generate_pdf(self, data, title):
        """Generate PDF from data"""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        
        # Title
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            alignment=TA_CENTER,
            spaceAfter=30
        )
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 0.2 * inch))
        
        # Date
        elements.append(Paragraph(f"Generated: {timezone.now().strftime('%d %B %Y %H:%M')}", styles['Normal']))
        elements.append(Spacer(1, 0.3 * inch))
        
        # Table data
        if isinstance(data, dict) and 'items' in data and data['items']:
            headers = list(data['items'][0].keys())
            table_data = [headers]
            
            for item in data['items'][:50]:  # Limit to 50 rows for PDF
                row = [str(item.get(h, '')) for h in headers]
                table_data.append(row)
            
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(table)
        
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()


# ==================== REPORT GENERATION HISTORY ====================

class ReportGenerationHistoryView(generics.ListAPIView):
    """List report generation history"""
    serializer_class = ReportGenerationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return ReportGeneration.objects.filter(
            generated_by=self.request.user
        ).order_by('-started_at')[:50]
