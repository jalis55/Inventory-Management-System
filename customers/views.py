from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Sum, Count, Avg
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from .models import (
    Customer, CustomerAddress, CustomerContact, 
    CustomerInteraction, CustomerLoyalty, CustomerDocument,
    CustomerPayment
)
from .serializers import (
    CustomerListSerializer, CustomerDetailSerializer,
    CustomerCreateUpdateSerializer, CustomerAddressSerializer,
    CustomerContactSerializer, CustomerInteractionSerializer,
    CustomerInteractionCreateSerializer, CustomerLoyaltySerializer,
    CustomerDocumentSerializer, CustomerPaymentSerializer,
    CustomerPaymentCreateSerializer
)
from accounts.models import ActivityLog
import django_filters
import csv
from django.http import HttpResponse
from io import StringIO

# Customer Filters
class CustomerFilter(django_filters.FilterSet):
    min_credit_limit = django_filters.NumberFilter(field_name="credit_limit", lookup_expr='gte')
    max_outstanding = django_filters.NumberFilter(field_name="outstanding_amount", lookup_expr='lte')
    has_outstanding = django_filters.BooleanFilter(method='filter_has_outstanding')
    state = django_filters.CharFilter(field_name="state", lookup_expr='icontains')
    city = django_filters.CharFilter(field_name="city", lookup_expr='icontains')
    min_loyalty_points = django_filters.NumberFilter(field_name="loyalty_points", lookup_expr='gte')
    joined_after = django_filters.DateFilter(field_name="created_at", lookup_expr='gte')
    joined_before = django_filters.DateFilter(field_name="created_at", lookup_expr='lte')
    
    class Meta:
        model = Customer
        fields = [
            'customer_type', 'loyalty_tier', 'is_active',
            'preferred_communication', 'payment_terms'
        ]
    
    def filter_has_outstanding(self, queryset, name, value):
        if value:
            return queryset.filter(outstanding_amount__gt=0)
        return queryset.filter(outstanding_amount=0)

# Customer Views
class CustomerListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CustomerFilter
    search_fields = [
        'customer_code', 'first_name', 'last_name', 'company_name',
        'email', 'phone', 'gst_number', 'city'
    ]
    ordering_fields = [
        'created_at', 'first_name', 'last_name', 'company_name',
        'outstanding_amount', 'loyalty_points', 'city'
    ]
    
    def get_queryset(self):
        return Customer.objects.select_related('created_by').all()
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return CustomerListSerializer
        return CustomerCreateUpdateSerializer
    
    def perform_create(self, serializer):
        with transaction.atomic():
            customer = serializer.save(created_by=self.request.user)
            
            # Create loyalty record
            CustomerLoyalty.objects.create(customer=customer)
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='CUSTOMER_CREATED',
                details={
                    'customer_name': customer.get_full_name,
                    'customer_code': customer.customer_code,
                    'customer_id': str(customer.id),
                    'customer_type': customer.customer_type
                }
            )

class CustomerRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return Customer.objects.prefetch_related(
            'addresses', 'contacts', 'interactions', 'loyalty', 'documents', 'payments'
        ).all()
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return CustomerDetailSerializer
        return CustomerCreateUpdateSerializer
    
    def perform_update(self, serializer):
        customer = serializer.save(updated_by=self.request.user)
        ActivityLog.objects.create(
            user=self.request.user,
            action='CUSTOMER_UPDATED',
            details={
                'customer_name': customer.get_full_name,
                'customer_id': str(customer.id),
                'customer_code': customer.customer_code
            }
        )
    
    def perform_destroy(self, instance):
        ActivityLog.objects.create(
            user=self.request.user,
            action='CUSTOMER_DELETED',
            details={
                'customer_name': instance.get_full_name,
                'customer_id': str(instance.id),
                'customer_code': instance.customer_code
            }
        )
        instance.delete()

# Customer Address Views
class CustomerAddressListCreateView(generics.ListCreateAPIView):
    serializer_class = CustomerAddressSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        customer_id = self.kwargs.get('customer_id')
        return CustomerAddress.objects.filter(customer_id=customer_id).order_by('-created_at')
    
    def perform_create(self, serializer):
        customer_id = self.kwargs.get('customer_id')
        customer = Customer.objects.get(id=customer_id)
        
        with transaction.atomic():
            # If this is set as default, unset other defaults
            if serializer.validated_data.get('is_default', False):
                CustomerAddress.objects.filter(
                    customer=customer, is_default=True
                ).update(is_default=False)
            
            address = serializer.save(customer=customer)
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='CUSTOMER_ADDRESS_ADDED',
                details={
                    'customer': customer.get_full_name,
                    'address_type': address.address_type,
                    'city': address.city
                }
            )

class CustomerAddressRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CustomerAddressSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return CustomerAddress.objects.all()
    
    def perform_update(self, serializer):
        address = serializer.save()
        
        # Handle default address logic
        if address.is_default:
            CustomerAddress.objects.filter(
                customer=address.customer, is_default=True
            ).exclude(id=address.id).update(is_default=False)
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='CUSTOMER_ADDRESS_UPDATED',
            details={
                'customer': address.customer.get_full_name,
                'address_id': str(address.id)
            }
        )
    
    def perform_destroy(self, instance):
        ActivityLog.objects.create(
            user=self.request.user,
            action='CUSTOMER_ADDRESS_DELETED',
            details={
                'customer': instance.customer.get_full_name,
                'address_id': str(instance.id)
            }
        )
        instance.delete()

# Customer Contact Views
class CustomerContactListCreateView(generics.ListCreateAPIView):
    serializer_class = CustomerContactSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        customer_id = self.kwargs.get('customer_id')
        return CustomerContact.objects.filter(customer_id=customer_id).order_by('-created_at')
    
    def perform_create(self, serializer):
        customer_id = self.kwargs.get('customer_id')
        customer = Customer.objects.get(id=customer_id)
        
        with transaction.atomic():
            # If this is set as primary, unset other primaries
            if serializer.validated_data.get('is_primary', False):
                CustomerContact.objects.filter(
                    customer=customer, is_primary=True
                ).update(is_primary=False)
            
            contact = serializer.save(customer=customer)
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='CUSTOMER_CONTACT_ADDED',
                details={
                    'customer': customer.get_full_name,
                    'contact_name': contact.name,
                    'is_primary': contact.is_primary
                }
            )

class CustomerContactRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CustomerContactSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return CustomerContact.objects.all()
    
    def perform_update(self, serializer):
        contact = serializer.save()
        
        # Handle primary contact logic
        if contact.is_primary:
            CustomerContact.objects.filter(
                customer=contact.customer, is_primary=True
            ).exclude(id=contact.id).update(is_primary=False)
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='CUSTOMER_CONTACT_UPDATED',
            details={
                'customer': contact.customer.get_full_name,
                'contact_name': contact.name
            }
        )
    
    def perform_destroy(self, instance):
        ActivityLog.objects.create(
            user=self.request.user,
            action='CUSTOMER_CONTACT_DELETED',
            details={
                'customer': instance.customer.get_full_name,
                'contact_name': instance.name
            }
        )
        instance.delete()

# Customer Interaction Views
class CustomerInteractionListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CustomerInteractionCreateSerializer
        return CustomerInteractionSerializer
    
    def get_queryset(self):
        customer_id = self.kwargs.get('customer_id')
        return CustomerInteraction.objects.filter(customer_id=customer_id).select_related('created_by').order_by('-created_at')
    
    def perform_create(self, serializer):
        customer_id = self.kwargs.get('customer_id')
        customer = Customer.objects.get(id=customer_id)
        
        interaction = serializer.save(
            customer=customer,
            created_by=self.request.user
        )
        
        # Update loyalty last activity
        if hasattr(customer, 'loyalty'):
            customer.loyalty.last_activity_date = timezone.now()
            customer.loyalty.save()
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='CUSTOMER_INTERACTION_LOGGED',
            details={
                'customer': customer.get_full_name,
                'interaction_type': interaction.interaction_type,
                'subject': interaction.subject
            }
        )

class CustomerInteractionRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CustomerInteractionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return CustomerInteraction.objects.select_related('customer', 'created_by').all()
    
    def perform_update(self, serializer):
        interaction = serializer.save()
        
        # If resolved/closed, update follow_up_required
        if interaction.status in ['resolved', 'closed']:
            interaction.follow_up_required = False
            interaction.save()
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='CUSTOMER_INTERACTION_UPDATED',
            details={
                'customer': interaction.customer.get_full_name,
                'interaction_id': str(interaction.id)
            }
        )
    
    def perform_destroy(self, instance):
        ActivityLog.objects.create(
            user=self.request.user,
            action='CUSTOMER_INTERACTION_DELETED',
            details={
                'customer': instance.customer.get_full_name,
                'interaction_id': str(instance.id)
            }
        )
        instance.delete()

# Customer Payment Views
class CustomerPaymentListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CustomerPaymentCreateSerializer
        return CustomerPaymentSerializer
    
    def get_queryset(self):
        customer_id = self.kwargs.get('customer_id')
        return CustomerPayment.objects.filter(customer_id=customer_id).select_related('received_by').order_by('-payment_date')
    
    def perform_create(self, serializer):
        customer_id = self.kwargs.get('customer_id')
        customer = Customer.objects.get(id=customer_id)
        
        with transaction.atomic():
            payment = serializer.save(
                customer=customer,
                received_by=self.request.user,
                status='completed'
            )
            
            # Update customer outstanding amount
            customer.outstanding_amount -= payment.amount
            customer.save()
            
            # Add loyalty points (1 point per 100 spent)
            if hasattr(customer, 'loyalty'):
                points_earned = int(payment.amount / 100)
                customer.loyalty.points += points_earned
                customer.loyalty.lifetime_points += points_earned
                customer.loyalty.lifetime_purchase += payment.amount
                
                # Update tier based on lifetime purchase
                if customer.loyalty.lifetime_purchase >= 100000:
                    customer.loyalty.tier = 'diamond'
                elif customer.loyalty.lifetime_purchase >= 50000:
                    customer.loyalty.tier = 'platinum'
                elif customer.loyalty.lifetime_purchase >= 25000:
                    customer.loyalty.tier = 'gold'
                elif customer.loyalty.lifetime_purchase >= 10000:
                    customer.loyalty.tier = 'silver'
                
                customer.loyalty.save()
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='CUSTOMER_PAYMENT_RECEIVED',
                details={
                    'customer': customer.get_full_name,
                    'amount': str(payment.amount),
                    'payment_method': payment.payment_method,
                    'new_outstanding': str(customer.outstanding_amount)
                }
            )

class CustomerPaymentRetrieveView(generics.RetrieveAPIView):
    serializer_class = CustomerPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return CustomerPayment.objects.select_related('customer', 'received_by').all()

# Customer Loyalty Views
class CustomerLoyaltyView(generics.RetrieveUpdateAPIView):
    serializer_class = CustomerLoyaltySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        customer_id = self.kwargs.get('customer_id')
        loyalty, created = CustomerLoyalty.objects.get_or_create(customer_id=customer_id)
        return loyalty
    
    def perform_update(self, serializer):
        loyalty = serializer.save()
        
        # Update customer's loyalty tier in main customer record
        customer = loyalty.customer
        customer.loyalty_tier = loyalty.tier
        customer.loyalty_points = loyalty.points
        customer.save()
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='CUSTOMER_LOYALTY_UPDATED',
            details={
                'customer': customer.get_full_name,
                'new_tier': loyalty.tier,
                'points': loyalty.points
            }
        )

# Customer Document Views
class CustomerDocumentListCreateView(generics.ListCreateAPIView):
    serializer_class = CustomerDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        customer_id = self.kwargs.get('customer_id')
        return CustomerDocument.objects.filter(customer_id=customer_id).order_by('-uploaded_at')
    
    def perform_create(self, serializer):
        customer_id = self.kwargs.get('customer_id')
        customer = Customer.objects.get(id=customer_id)
        
        document = serializer.save(customer=customer)
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='CUSTOMER_DOCUMENT_UPLOADED',
            details={
                'customer': customer.get_full_name,
                'document_type': document.document_type,
                'document_number': document.document_number
            }
        )

class CustomerDocumentRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CustomerDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return CustomerDocument.objects.all()
    
    def perform_update(self, serializer):
        document = serializer.save()
        
        if document.is_verified and not document.verified_by:
            document.verified_by = self.request.user
            document.verified_at = timezone.now()
            document.save()
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='CUSTOMER_DOCUMENT_UPDATED',
            details={
                'customer': document.customer.get_full_name,
                'document_id': str(document.id)
            }
        )
    
    def perform_destroy(self, instance):
        ActivityLog.objects.create(
            user=self.request.user,
            action='CUSTOMER_DOCUMENT_DELETED',
            details={
                'customer': instance.customer.get_full_name,
                'document_type': instance.document_type
            }
        )
        instance.delete()

# Customer Dashboard/Statistics
class CustomerStatisticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        total_customers = Customer.objects.count()
        active_customers = Customer.objects.filter(is_active=True).count()
        new_customers_this_month = Customer.objects.filter(
            created_at__month=timezone.now().month,
            created_at__year=timezone.now().year
        ).count()
        
        # Outstanding amounts
        total_outstanding = Customer.objects.aggregate(
            total=Sum('outstanding_amount')
        )['total'] or 0
        
        customers_with_outstanding = Customer.objects.filter(
            outstanding_amount__gt=0
        ).count()
        
        # Customer type distribution
        type_stats = Customer.objects.values('customer_type').annotate(
            count=Count('id')
        )
        
        # Loyalty tier distribution
        tier_stats = Customer.objects.values('loyalty_tier').annotate(
            count=Count('id')
        )
        
        # Top customers by purchase
        top_customers = Customer.objects.select_related('loyalty').filter(
            loyalty__lifetime_purchase__gt=0
        ).order_by('-loyalty__lifetime_purchase')[:10].values(
            'first_name', 'last_name', 'company_name', 'loyalty__lifetime_purchase'
        )
        
        # Recent interactions
        recent_interactions = CustomerInteraction.objects.select_related(
            'customer', 'created_by'
        ).order_by('-created_at')[:10].values(
            'customer__first_name', 'customer__last_name',
            'interaction_type', 'subject', 'created_at'
        )
        
        # State-wise distribution
        state_stats = Customer.objects.values('state').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return Response({
            'total_customers': total_customers,
            'active_customers': active_customers,
            'new_customers_this_month': new_customers_this_month,
            'total_outstanding': total_outstanding,
            'customers_with_outstanding': customers_with_outstanding,
            'average_outstanding': round(total_outstanding / total_customers, 2) if total_customers > 0 else 0,
            'customer_type_stats': type_stats,
            'loyalty_tier_stats': tier_stats,
            'top_customers': top_customers,
            'recent_interactions': recent_interactions,
            'state_stats': state_stats
        })

# Customer Bulk Operations
class CustomerBulkUploadView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def _load_rows(self, file):
        if file.name.endswith('.csv'):
            content = file.read().decode('utf-8')
            return list(csv.DictReader(StringIO(content)))

        if file.name.endswith(('.xls', '.xlsx')):
            try:
                import pandas as pd
            except ImportError as exc:
                raise ImportError('Excel upload requires pandas to be installed') from exc

            return pd.read_excel(file).to_dict(orient='records')

        raise ValueError('Unsupported file format')
    
    def post(self, request):
        if 'file' not in request.FILES:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        
        try:
            created_count = 0
            errors = []
            rows = self._load_rows(file)
            
            with transaction.atomic():
                for index, row in enumerate(rows):
                    try:
                        # Prepare customer data
                        customer_data = {
                            'customer_type': row.get('customer_type', 'retail'),
                            'first_name': str(row.get('first_name')),
                            'last_name': str(row.get('last_name')),
                            'email': str(row.get('email')),
                            'phone': str(row.get('phone')),
                            'address_line1': str(row.get('address')),
                            'city': str(row.get('city')),
                            'state': str(row.get('state')),
                            'postal_code': str(row.get('postal_code')),
                            'country': str(row.get('country', 'India')),
                        }
                        
                        # Validate required fields
                        required_fields = ['first_name', 'last_name', 'email', 'phone']
                        missing_fields = [f for f in required_fields if not customer_data.get(f)]
                        if missing_fields:
                            errors.append(f"Row {index + 2}: Missing required fields: {', '.join(missing_fields)}")
                            continue
                        
                        # Check if email exists
                        if Customer.objects.filter(email=customer_data['email']).exists():
                            errors.append(f"Row {index + 2}: Email {customer_data['email']} already exists")
                            continue
                        
                        serializer = CustomerCreateUpdateSerializer(data=customer_data)
                        if serializer.is_valid():
                            customer = serializer.save(created_by=request.user)
                            
                            # Create loyalty record
                            CustomerLoyalty.objects.create(customer=customer)
                            
                            created_count += 1
                        else:
                            errors.append(f"Row {index + 2}: {serializer.errors}")
                            
                    except Exception as e:
                        errors.append(f"Row {index + 2}: {str(e)}")
            
            ActivityLog.objects.create(
                user=request.user,
                action='CUSTOMER_BULK_UPLOAD',
                details={
                    'created': created_count,
                    'errors': len(errors)
                }
            )
            
            return Response({
                'message': f'Successfully created {created_count} customers',
                'errors': errors
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class CustomerExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Get all customers
        customers = Customer.objects.all()
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="customers.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Customer Code', 'Type', 'First Name', 'Last Name', 'Company',
            'Email', 'Phone', 'Mobile', 'Address', 'City', 'State',
            'Postal Code', 'Country', 'GST Number', 'PAN Number',
            'Credit Limit', 'Outstanding', 'Loyalty Points', 'Loyalty Tier',
            'Payment Terms', 'Status', 'Created At'
        ])
        
        for customer in customers:
            address = f"{customer.address_line1} {customer.address_line2}".strip()
            writer.writerow([
                customer.customer_code,
                customer.customer_type,
                customer.first_name,
                customer.last_name,
                customer.company_name,
                customer.email,
                customer.phone,
                customer.mobile,
                address,
                customer.city,
                customer.state,
                customer.postal_code,
                customer.country,
                customer.gst_number,
                customer.pan_number,
                customer.credit_limit,
                customer.outstanding_amount,
                customer.loyalty_points,
                customer.loyalty_tier,
                customer.payment_terms,
                'Active' if customer.is_active else 'Inactive',
                customer.created_at.strftime('%Y-%m-%d')
            ])
        
        # Log export activity
        ActivityLog.objects.create(
            user=request.user,
            action='CUSTOMER_EXPORTED',
            details={'count': customers.count()}
        )
        
        return response

# Customer Search/Autocomplete
class CustomerSearchView(generics.ListAPIView):
    serializer_class = CustomerListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        if len(query) < 2:
            return Customer.objects.none()
        
        return Customer.objects.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(company_name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(customer_code__icontains=query)
        ).filter(is_active=True)[:15]

# Customer Outstanding Report
class CustomerOutstandingReportView(generics.ListAPIView):
    serializer_class = CustomerListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Customer.objects.filter(
            outstanding_amount__gt=0
        ).order_by('-outstanding_amount')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        total_outstanding = queryset.aggregate(total=Sum('outstanding_amount'))['total'] or 0
        
        return Response({
            'total_outstanding': total_outstanding,
            'customer_count': queryset.count(),
            'customers': serializer.data
        })

# Customer Loyalty Report
class CustomerLoyaltyReportView(generics.ListAPIView):
    serializer_class = CustomerListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Customer.objects.filter(
            loyalty_points__gt=0
        ).order_by('-loyalty_points')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        total_points = queryset.aggregate(total=Sum('loyalty_points'))['total'] or 0
        tier_breakdown = queryset.values('loyalty_tier').annotate(
            count=Count('id'),
            total_points=Sum('loyalty_points')
        )
        
        return Response({
            'total_points': total_points,
            'customer_count': queryset.count(),
            'tier_breakdown': tier_breakdown,
            'customers': serializer.data
        })
