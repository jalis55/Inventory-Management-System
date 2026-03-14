from decimal import Decimal

from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Sum, Count, F
from django.db.models import DecimalField
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import timedelta
from .models import (
    DuesSummary, CustomerDue, SupplierDue, 
    PaymentCollection, PaymentDisbursement,
    DueReminder, WriteOff
)
from .serializers import (
    DuesSummarySerializer, CustomerDueSerializer, SupplierDueSerializer,
    PaymentCollectionSerializer, PaymentCollectionCreateSerializer,
    PaymentDisbursementSerializer, PaymentDisbursementCreateSerializer,
    DueReminderSerializer, WriteOffSerializer,
    CustomerAgingReportSerializer
)
from customers.models import Customer
from suppliers.models import Supplier
from sales.models import SalesOrder, SalesPayment
from purchases.models import PurchaseOrder, PurchasePayment
from accounts.models import ActivityLog
import django_filters
from django.db.models.functions import Coalesce

# Customer Due Filters
class CustomerDueFilter(django_filters.FilterSet):
    min_amount = django_filters.NumberFilter(field_name="remaining_amount", lookup_expr='gte')
    max_amount = django_filters.NumberFilter(field_name="remaining_amount", lookup_expr='lte')
    due_date_from = django_filters.DateFilter(field_name="due_date", lookup_expr='gte')
    due_date_to = django_filters.DateFilter(field_name="due_date", lookup_expr='lte')
    customer = django_filters.UUIDFilter(field_name="customer__id")
    status = django_filters.ChoiceFilter(choices=CustomerDue.DUE_STATUS)
    overdue_only = django_filters.BooleanFilter(method='filter_overdue')
    
    class Meta:
        model = CustomerDue
        fields = ['status', 'customer']
    
    def filter_overdue(self, queryset, name, value):
        if value:
            return queryset.filter(status='overdue')
        return queryset

# Supplier Due Filters
class SupplierDueFilter(django_filters.FilterSet):
    min_amount = django_filters.NumberFilter(field_name="remaining_amount", lookup_expr='gte')
    max_amount = django_filters.NumberFilter(field_name="remaining_amount", lookup_expr='lte')
    due_date_from = django_filters.DateFilter(field_name="due_date", lookup_expr='gte')
    due_date_to = django_filters.DateFilter(field_name="due_date", lookup_expr='lte')
    supplier = django_filters.UUIDFilter(field_name="supplier__id")
    status = django_filters.ChoiceFilter(choices=SupplierDue.DUE_STATUS)
    overdue_only = django_filters.BooleanFilter(method='filter_overdue')
    
    class Meta:
        model = SupplierDue
        fields = ['status', 'supplier']
    
    def filter_overdue(self, queryset, name, value):
        if value:
            return queryset.filter(status='overdue')
        return queryset

# Customer Due Views
class CustomerDueListView(generics.ListAPIView):
    """List all customer dues with filtering"""
    serializer_class = CustomerDueSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CustomerDueFilter
    search_fields = ['customer__first_name', 'customer__last_name', 'customer__company_name', 'sales_order__order_number']
    ordering_fields = ['due_date', 'remaining_amount', 'days_overdue']
    
    def get_queryset(self):
        return CustomerDue.objects.select_related(
            'customer', 'sales_order'
        ).filter(remaining_amount__gt=0)

class CustomerDueDetailView(generics.RetrieveAPIView):
    """Get customer due details"""
    serializer_class = CustomerDueSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return CustomerDue.objects.select_related(
            'customer', 'sales_order'
        ).prefetch_related('collections', 'reminders')

# Supplier Due Views
class SupplierDueListView(generics.ListAPIView):
    """List all supplier dues with filtering"""
    serializer_class = SupplierDueSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SupplierDueFilter
    search_fields = ['supplier__company_name', 'purchase_order__po_number']
    ordering_fields = ['due_date', 'remaining_amount', 'days_overdue']
    
    def get_queryset(self):
        return SupplierDue.objects.select_related(
            'supplier', 'purchase_order'
        ).filter(remaining_amount__gt=0)

class SupplierDueDetailView(generics.RetrieveAPIView):
    """Get supplier due details"""
    serializer_class = SupplierDueSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return SupplierDue.objects.select_related(
            'supplier', 'purchase_order'
        ).prefetch_related('disbursements', 'reminders')

# Payment Collection Views
class PaymentCollectionListCreateView(generics.ListCreateAPIView):
    """List and create payment collections"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PaymentCollectionCreateSerializer
        return PaymentCollectionSerializer
    
    def get_queryset(self):
        return PaymentCollection.objects.select_related(
            'customer_due__customer', 'collected_by'
        ).all()
    
    def perform_create(self, serializer):
        with transaction.atomic():
            collection = serializer.save(collected_by=self.request.user)
            
            # Update customer due
            customer_due = collection.customer_due
            customer_due.paid_amount += collection.amount
            customer_due.last_payment_date = collection.collection_date
            customer_due.last_payment_amount = collection.amount
            customer_due.save()
            
            # Update customer's outstanding amount
            customer = customer_due.customer
            customer.outstanding_amount -= collection.amount
            customer.save()
            
            # Generate receipt
            collection.receipt_generated = True
            collection.save()
            
            # Create activity log
            ActivityLog.objects.create(
                user=self.request.user,
                action='PAYMENT_COLLECTED',
                details={
                    'collection_number': collection.collection_number,
                    'customer': customer.get_full_name,
                    'amount': str(collection.amount),
                    'receipt_number': collection.receipt_number
                }
            )

class PaymentCollectionReceiptView(APIView):
    """Generate and get payment receipt"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, id):
        try:
            collection = PaymentCollection.objects.select_related(
                'customer_due__customer', 'collected_by'
            ).get(id=id)
        except PaymentCollection.DoesNotExist:
            return Response({'error': 'Collection not found'}, status=404)
        
        # Prepare receipt data
        receipt_data = {
            'receipt_number': collection.receipt_number,
            'collection_number': collection.collection_number,
            'date': collection.collection_date,
            'customer': {
                'name': collection.customer_due.customer.get_full_name,
                'company': collection.customer_due.customer.company_name,
                'phone': collection.customer_due.customer.phone,
                'email': collection.customer_due.customer.email,
                'address': f"{collection.customer_due.customer.address_line1}, {collection.customer_due.customer.city}"
            },
            'amount': collection.amount,
            'amount_in_words': self.number_to_words(collection.amount),
            'payment_method': collection.get_payment_method_display(),
            'reference_number': collection.reference_number,
            'transaction_id': collection.transaction_id,
            'collected_by': collection.collected_by.get_full_name() if collection.collected_by else 'N/A',
            'order_number': collection.customer_due.sales_order.order_number,
            'invoice_number': collection.customer_due.sales_order.invoice_number,
            'notes': collection.notes
        }
        
        return Response(receipt_data)
    
    def number_to_words(self, n):
        """Convert number to words (simplified)"""
        from num2words import num2words
        return num2words(int(n), to='currency', currency='INR')

# Payment Disbursement Views
class PaymentDisbursementListCreateView(generics.ListCreateAPIView):
    """List and create payment disbursements"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PaymentDisbursementCreateSerializer
        return PaymentDisbursementSerializer
    
    def get_queryset(self):
        return PaymentDisbursement.objects.select_related(
            'supplier_due__supplier', 'disbursed_by'
        ).all()
    
    def perform_create(self, serializer):
        with transaction.atomic():
            disbursement = serializer.save(disbursed_by=self.request.user)
            
            # Update supplier due
            supplier_due = disbursement.supplier_due
            supplier_due.paid_amount += disbursement.amount
            supplier_due.last_payment_date = disbursement.disbursement_date
            supplier_due.last_payment_amount = disbursement.amount
            supplier_due.save()
            
            # Update supplier's outstanding amount
            supplier = supplier_due.supplier
            supplier.outstanding_amount -= disbursement.amount
            supplier.save()
            
            # Create activity log
            ActivityLog.objects.create(
                user=self.request.user,
                action='PAYMENT_DISBURSED',
                details={
                    'disbursement_number': disbursement.disbursement_number,
                    'supplier': supplier.company_name,
                    'amount': str(disbursement.amount),
                    'voucher_number': disbursement.voucher_number
                }
            )

# Due Reminder Views
class DueReminderListCreateView(generics.ListCreateAPIView):
    """List and create due reminders"""
    serializer_class = DueReminderSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return DueReminder.objects.select_related(
            'customer_due__customer', 'supplier_due__supplier', 'created_by'
        ).all()
    
    def perform_create(self, serializer):
        reminder = serializer.save(created_by=self.request.user)
        
        # Update reminder count on the due
        if reminder.customer_due:
            reminder.customer_due.reminder_count += 1
            reminder.customer_due.last_reminder_sent = reminder.scheduled_date
            reminder.customer_due.save()
        elif reminder.supplier_due:
            reminder.supplier_due.reminder_count += 1
            reminder.supplier_due.last_reminder_sent = reminder.scheduled_date
            reminder.supplier_due.save()
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='DUE_REMINDER_CREATED',
            details={
                'reminder_id': str(reminder.id),
                'type': reminder.reminder_type,
                'scheduled_date': reminder.scheduled_date.isoformat()
            }
        )

class DueReminderSendView(APIView):
    """Send a due reminder"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, id):
        try:
            reminder = DueReminder.objects.get(id=id)
        except DueReminder.DoesNotExist:
            return Response({'error': 'Reminder not found'}, status=404)
        
        # In a real app, you would integrate with email/SMS service here
        # For now, just mark as sent
        reminder.status = 'sent'
        reminder.sent_at = timezone.now()
        reminder.save()
        
        ActivityLog.objects.create(
            user=request.user,
            action='DUE_REMINDER_SENT',
            details={'reminder_id': str(reminder.id)}
        )
        
        return Response({'message': 'Reminder sent successfully'})

# Write Off Views
class WriteOffListCreateView(generics.ListCreateAPIView):
    """List and create write-offs"""
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def get_serializer_class(self):
        return WriteOffSerializer
    
    def get_queryset(self):
        return WriteOff.objects.select_related(
            'customer_due__customer', 'approved_by', 'created_by'
        ).all()
    
    def perform_create(self, serializer):
        with transaction.atomic():
            write_off = serializer.save(created_by=self.request.user)
            
            # Update customer due
            customer_due = write_off.customer_due
            customer_due.status = 'written_off'
            customer_due.notes += f"\nWritten off: {write_off.amount} on {write_off.write_off_date}. Reason: {write_off.get_reason_display()}"
            customer_due.save()
            
            # Update customer's outstanding amount
            customer = customer_due.customer
            customer.outstanding_amount -= write_off.amount
            customer.save()
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='WRITE_OFF_CREATED',
                details={
                    'write_off_number': write_off.write_off_number,
                    'customer': customer.get_full_name,
                    'amount': str(write_off.amount),
                    'reason': write_off.reason
                }
            )

class WriteOffApproveView(APIView):
    """Approve a write-off"""
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def post(self, request, id):
        try:
            write_off = WriteOff.objects.get(id=id)
        except WriteOff.DoesNotExist:
            return Response({'error': 'Write off not found'}, status=404)
        
        if write_off.approved_by:
            return Response({'error': 'Write off already approved'}, status=400)
        
        write_off.approved_by = request.user
        write_off.approved_at = timezone.now()
        write_off.save()
        
        ActivityLog.objects.create(
            user=request.user,
            action='WRITE_OFF_APPROVED',
            details={'write_off_number': write_off.write_off_number}
        )
        
        return Response({'message': 'Write off approved successfully'})

# Dashboard Views
class DuesDashboardView(APIView):
    """Dues dashboard with summary and aging analysis"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Update summary
        summary = DuesSummary.objects.first()
        if summary is None:
            summary = DuesSummary.objects.create()
        
        # Calculate current totals
        customer_outstanding = CustomerDue.objects.filter(
            remaining_amount__gt=0
        ).aggregate(
            total=Coalesce(
                Sum('remaining_amount'),
                Decimal('0.00'),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            ),
            count=Count('id')
        )
        
        supplier_outstanding = SupplierDue.objects.filter(
            remaining_amount__gt=0
        ).aggregate(
            total=Coalesce(
                Sum('remaining_amount'),
                Decimal('0.00'),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            ),
            count=Count('id')
        )
        
        customer_overdue = CustomerDue.objects.filter(
            status='overdue'
        ).aggregate(
            total=Coalesce(
                Sum('remaining_amount'),
                Decimal('0.00'),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            )
        )
        
        supplier_overdue = SupplierDue.objects.filter(
            status='overdue'
        ).aggregate(
            total=Coalesce(
                Sum('remaining_amount'),
                Decimal('0.00'),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            )
        )
        
        # Update summary
        summary.total_customer_outstanding = customer_outstanding['total']
        summary.total_supplier_outstanding = supplier_outstanding['total']
        summary.total_customer_overdue = customer_overdue['total']
        summary.total_supplier_overdue = supplier_overdue['total']
        summary.customer_count_with_dues = customer_outstanding['count']
        summary.supplier_count_with_dues = supplier_outstanding['count']
        summary.net_receivable = customer_outstanding['total'] - supplier_outstanding['total']
        summary.save()
        
        # Recent collections
        recent_collections = PaymentCollection.objects.select_related(
            'customer_due__customer'
        ).order_by('-collection_date')[:10].values(
            'collection_number', 'customer_due__customer__first_name',
            'customer_due__customer__last_name', 'amount', 'collection_date'
        )
        
        # Recent disbursements
        recent_disbursements = PaymentDisbursement.objects.select_related(
            'supplier_due__supplier'
        ).order_by('-disbursement_date')[:10].values(
            'disbursement_number', 'supplier_due__supplier__company_name',
            'amount', 'disbursement_date'
        )
        
        # Overdue summary
        overdue_customers = CustomerDue.objects.filter(
            status='overdue'
        ).select_related('customer').order_by('-days_overdue')[:10]
        
        overdue_suppliers = SupplierDue.objects.filter(
            status='overdue'
        ).select_related('supplier').order_by('-days_overdue')[:10]
        
        return Response({
            'summary': DuesSummarySerializer(summary).data,
            'recent_collections': recent_collections,
            'recent_disbursements': recent_disbursements,
            'overdue_customers': CustomerDueSerializer(overdue_customers, many=True).data,
            'overdue_suppliers': SupplierDueSerializer(overdue_suppliers, many=True).data
        })

# Aging Reports
class CustomerAgingReportView(APIView):
    """Customer aging report (receivables)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        today = timezone.now().date()
        customers = Customer.objects.filter(outstanding_amount__gt=0)
        
        report_data = []
        
        for customer in customers:
            dues = CustomerDue.objects.filter(customer=customer, remaining_amount__gt=0)
            
            aging = {
                'current': 0,
                'days_1_30': 0,
                'days_31_60': 0,
                'days_61_90': 0,
                'days_91_plus': 0
            }
            
            for due in dues:
                days = (today - due.due_date).days
                
                if days <= 0:
                    aging['current'] += due.remaining_amount
                elif days <= 30:
                    aging['days_1_30'] += due.remaining_amount
                elif days <= 60:
                    aging['days_31_60'] += due.remaining_amount
                elif days <= 90:
                    aging['days_61_90'] += due.remaining_amount
                else:
                    aging['days_91_plus'] += due.remaining_amount
            
            report_data.append({
                'customer_id': customer.id,
                'customer_name': customer.get_full_name,
                'company_name': customer.company_name,
                'total_outstanding': customer.outstanding_amount,
                **aging
            })
        
        # Calculate totals
        totals = {
            'total_outstanding': sum(d['total_outstanding'] for d in report_data),
            'current': sum(d['current'] for d in report_data),
            'days_1_30': sum(d['days_1_30'] for d in report_data),
            'days_31_60': sum(d['days_31_60'] for d in report_data),
            'days_61_90': sum(d['days_61_90'] for d in report_data),
            'days_91_plus': sum(d['days_91_plus'] for d in report_data),
        }
        
        return Response({
            'as_of_date': today,
            'report': report_data,
            'totals': totals
        })

class SupplierAgingReportView(APIView):
    """Supplier aging report (payables)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        today = timezone.now().date()
        suppliers = Supplier.objects.filter(outstanding_amount__gt=0)
        
        report_data = []
        
        for supplier in suppliers:
            dues = SupplierDue.objects.filter(supplier=supplier, remaining_amount__gt=0)
            
            aging = {
                'current': 0,
                'days_1_30': 0,
                'days_31_60': 0,
                'days_61_90': 0,
                'days_91_plus': 0
            }
            
            for due in dues:
                days = (today - due.due_date).days
                
                if days <= 0:
                    aging['current'] += due.remaining_amount
                elif days <= 30:
                    aging['days_1_30'] += due.remaining_amount
                elif days <= 60:
                    aging['days_31_60'] += due.remaining_amount
                elif days <= 90:
                    aging['days_61_90'] += due.remaining_amount
                else:
                    aging['days_91_plus'] += due.remaining_amount
            
            report_data.append({
                'supplier_id': supplier.id,
                'supplier_name': supplier.company_name,
                'total_outstanding': supplier.outstanding_amount,
                **aging
            })
        
        # Calculate totals
        totals = {
            'total_outstanding': sum(d['total_outstanding'] for d in report_data),
            'current': sum(d['current'] for d in report_data),
            'days_1_30': sum(d['days_1_30'] for d in report_data),
            'days_31_60': sum(d['days_31_60'] for d in report_data),
            'days_61_90': sum(d['days_61_90'] for d in report_data),
            'days_91_plus': sum(d['days_91_plus'] for d in report_data),
        }
        
        return Response({
            'as_of_date': today,
            'report': report_data,
            'totals': totals
        })

# Auto-update dues from sales/purchase orders (signals)
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=SalesOrder)
def create_customer_due(sender, instance, created, **kwargs):
    """Create customer due when sales order is confirmed"""
    if instance.order_status == 'confirmed' and instance.due_amount > 0:
        due_date = instance.expected_delivery_date or timezone.now().date() + timedelta(days=7)
        
        CustomerDue.objects.update_or_create(
            sales_order=instance,
            defaults={
                'customer': instance.customer,
                'due_date': due_date,
                'original_amount': instance.due_amount,
                'paid_amount': instance.paid_amount,
                'remaining_amount': instance.due_amount
            }
        )
        
        # Update summary will be updated by separate process
    elif instance.order_status == 'cancelled':
        CustomerDue.objects.filter(sales_order=instance).delete()

@receiver(post_save, sender=PurchaseOrder)
def create_supplier_due(sender, instance, created, **kwargs):
    """Create supplier due when purchase order is approved"""
    if instance.order_status == 'approved' and instance.due_amount > 0:
        due_date = instance.expected_delivery_date or timezone.now().date() + timedelta(days=7)
        
        SupplierDue.objects.update_or_create(
            purchase_order=instance,
            defaults={
                'supplier': instance.supplier,
                'due_date': due_date,
                'original_amount': instance.due_amount,
                'paid_amount': instance.paid_amount,
                'remaining_amount': instance.due_amount
            }
        )
    elif instance.order_status == 'cancelled':
        SupplierDue.objects.filter(purchase_order=instance).delete()

@receiver(post_save, sender=SalesPayment)
def update_customer_due_from_payment(sender, instance, **kwargs):
    """Update customer due when payment is received"""
    if instance.status == 'completed':
        try:
            customer_due = CustomerDue.objects.get(sales_order=instance.sales_order)
            customer_due.paid_amount += instance.amount
            customer_due.last_payment_date = instance.payment_date
            customer_due.last_payment_amount = instance.amount
            customer_due.save()
        except CustomerDue.DoesNotExist:
            # Create due if it doesn't exist
            due_date = instance.sales_order.expected_delivery_date or timezone.now().date() + timedelta(days=7)
            CustomerDue.objects.create(
                customer=instance.sales_order.customer,
                sales_order=instance.sales_order,
                due_date=due_date,
                original_amount=instance.sales_order.total_amount,
                paid_amount=instance.amount,
                remaining_amount=instance.sales_order.total_amount - instance.amount
            )

@receiver(post_save, sender=PurchasePayment)
def update_supplier_due_from_payment(sender, instance, **kwargs):
    """Update supplier due when payment is made"""
    if instance.status == 'completed':
        try:
            supplier_due = SupplierDue.objects.get(purchase_order=instance.purchase_order)
            supplier_due.paid_amount += instance.amount
            supplier_due.last_payment_date = instance.payment_date
            supplier_due.last_payment_amount = instance.amount
            supplier_due.save()
        except SupplierDue.DoesNotExist:
            due_date = instance.purchase_order.expected_delivery_date or timezone.now().date() + timedelta(days=7)
            SupplierDue.objects.create(
                supplier=instance.purchase_order.supplier,
                purchase_order=instance.purchase_order,
                due_date=due_date,
                original_amount=instance.purchase_order.total_amount,
                paid_amount=instance.amount,
                remaining_amount=instance.purchase_order.total_amount - instance.amount
            )
