from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Sum, Count, Avg
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from .models import Supplier, SupplierProduct
from .serializers import (
    SupplierListSerializer, SupplierDetailSerializer, 
    SupplierCreateUpdateSerializer, SupplierProductSerializer,
    SupplierProductCreateSerializer, SupplierPaymentUpdateSerializer
)
from accounts.models import ActivityLog
import django_filters
import csv
from django.http import HttpResponse
from io import StringIO

# Supplier Filters
class SupplierFilter(django_filters.FilterSet):
    min_rating = django_filters.NumberFilter(field_name="rating", lookup_expr='gte')
    max_outstanding = django_filters.NumberFilter(field_name="outstanding_amount", lookup_expr='lte')
    has_outstanding = django_filters.BooleanFilter(method='filter_has_outstanding')
    state = django_filters.CharFilter(field_name="state", lookup_expr='icontains')
    city = django_filters.CharFilter(field_name="city", lookup_expr='icontains')
    
    class Meta:
        model = Supplier
        fields = ['is_active', 'payment_terms', 'rating']
    
    def filter_has_outstanding(self, queryset, name, value):
        if value:
            return queryset.filter(outstanding_amount__gt=0)
        return queryset.filter(outstanding_amount=0)

# Supplier Views
class SupplierListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SupplierFilter
    search_fields = ['company_name', 'contact_person', 'email', 'phone', 'gst_number']
    ordering_fields = ['company_name', 'created_at', 'rating', 'outstanding_amount']
    
    def get_queryset(self):
        return Supplier.objects.select_related('created_by').all()
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return SupplierListSerializer
        return SupplierCreateUpdateSerializer
    
    def perform_create(self, serializer):
        supplier = serializer.save(created_by=self.request.user)
        ActivityLog.objects.create(
            user=self.request.user,
            action='SUPPLIER_CREATED',
            details={
                'supplier_name': supplier.company_name,
                'supplier_id': str(supplier.id),
                'gst_number': supplier.gst_number
            }
        )

class SupplierRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return Supplier.objects.prefetch_related('supplier_products__product').all()
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return SupplierDetailSerializer
        return SupplierCreateUpdateSerializer
    
    def perform_update(self, serializer):
        supplier = serializer.save(updated_by=self.request.user)
        ActivityLog.objects.create(
            user=self.request.user,
            action='SUPPLIER_UPDATED',
            details={
                'supplier_name': supplier.company_name,
                'supplier_id': str(supplier.id)
            }
        )
    
    def perform_destroy(self, instance):
        ActivityLog.objects.create(
            user=self.request.user,
            action='SUPPLIER_DELETED',
            details={
                'supplier_name': instance.company_name,
                'supplier_id': str(instance.id)
            }
        )
        instance.delete()

# Supplier Product Views
class SupplierProductListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SupplierProductCreateSerializer
        return SupplierProductSerializer
    
    def get_queryset(self):
        supplier_id = self.kwargs.get('supplier_id')
        return SupplierProduct.objects.filter(supplier_id=supplier_id).select_related('product').order_by('-created_at')
    
    def perform_create(self, serializer):
        supplier_id = self.kwargs.get('supplier_id')
        supplier = Supplier.objects.get(id=supplier_id)
        
        with transaction.atomic():
            supplier_product = serializer.save(supplier=supplier)
            
            ActivityLog.objects.create(
                user=self.request.user,
                action='SUPPLIER_PRODUCT_ADDED',
                details={
                    'supplier': supplier.company_name,
                    'product': supplier_product.product.name,
                    'price': str(supplier_product.price)
                }
            )

class SupplierProductRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SupplierProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return SupplierProduct.objects.select_related('supplier', 'product').all()
    
    def perform_update(self, serializer):
        supplier_product = serializer.save()
        ActivityLog.objects.create(
            user=self.request.user,
            action='SUPPLIER_PRODUCT_UPDATED',
            details={
                'supplier': supplier_product.supplier.company_name,
                'product': supplier_product.product.name,
                'new_price': str(supplier_product.price)
            }
        )
    
    def perform_destroy(self, instance):
        ActivityLog.objects.create(
            user=self.request.user,
            action='SUPPLIER_PRODUCT_REMOVED',
            details={
                'supplier': instance.supplier.company_name,
                'product': instance.product.name
            }
        )
        instance.delete()

# Supplier Payment Views
class SupplierPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, supplier_id):
        try:
            supplier = Supplier.objects.get(id=supplier_id)
        except Supplier.DoesNotExist:
            return Response({'error': 'Supplier not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = SupplierPaymentUpdateSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                # Update supplier outstanding amount
                amount = serializer.validated_data['amount']
                supplier.outstanding_amount -= amount
                supplier.save()
                
                # Log the payment
                ActivityLog.objects.create(
                    user=request.user,
                    action='SUPPLIER_PAYMENT_MADE',
                    details={
                        'supplier': supplier.company_name,
                        'amount': str(amount),
                        'payment_method': serializer.validated_data['payment_method'],
                        'reference': serializer.validated_data.get('reference_number', ''),
                        'new_outstanding': str(supplier.outstanding_amount)
                    }
                )
                
                return Response({
                    'message': 'Payment recorded successfully',
                    'new_outstanding': supplier.outstanding_amount
                })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Supplier Dashboard/Statistics
class SupplierStatisticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        total_suppliers = Supplier.objects.count()
        active_suppliers = Supplier.objects.filter(is_active=True).count()
        
        # Outstanding amounts
        total_outstanding = Supplier.objects.aggregate(
            total=Sum('outstanding_amount')
        )['total'] or 0
        
        suppliers_with_outstanding = Supplier.objects.filter(
            outstanding_amount__gt=0
        ).count()
        
        # Average rating
        avg_rating = Supplier.objects.filter(
            is_active=True
        ).aggregate(avg=Avg('rating'))['avg'] or 0
        
        # Top suppliers by products
        top_suppliers = Supplier.objects.annotate(
            product_count=Count('supplier_products')
        ).order_by('-product_count')[:5].values('company_name', 'product_count')
        
        # Payment terms distribution
        payment_terms_stats = Supplier.objects.values('payment_terms').annotate(
            count=Count('id')
        )
        
        # State-wise distribution
        state_stats = Supplier.objects.values('state').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return Response({
            'total_suppliers': total_suppliers,
            'active_suppliers': active_suppliers,
            'total_outstanding': total_outstanding,
            'suppliers_with_outstanding': suppliers_with_outstanding,
            'average_rating': round(avg_rating, 2),
            'top_suppliers': top_suppliers,
            'payment_terms_stats': payment_terms_stats,
            'state_stats': state_stats
        })

# Supplier Bulk Operations
class SupplierBulkUploadView(APIView):
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
                        # Create supplier from row data
                        supplier_data = {
                            'company_name': row.get('company_name'),
                            'contact_person': row.get('contact_person'),
                            'email': row.get('email'),
                            'phone': str(row.get('phone')),
                            'address_line1': row.get('address_line1'),
                            'city': row.get('city'),
                            'state': row.get('state'),
                            'postal_code': str(row.get('postal_code')),
                            'gst_number': row.get('gst_number'),
                        }
                        
                        # Validate required fields
                        if not supplier_data['company_name']:
                            errors.append(f"Row {index + 2}: company_name is required")
                            continue
                        
                        serializer = SupplierCreateUpdateSerializer(data=supplier_data)
                        if serializer.is_valid():
                            serializer.save(created_by=request.user)
                            created_count += 1
                        else:
                            errors.append(f"Row {index + 2}: {serializer.errors}")
                            
                    except Exception as e:
                        errors.append(f"Row {index + 2}: {str(e)}")
            
            ActivityLog.objects.create(
                user=request.user,
                action='SUPPLIER_BULK_UPLOAD',
                details={
                    'created': created_count,
                    'errors': len(errors)
                }
            )
            
            return Response({
                'message': f'Successfully created {created_count} suppliers',
                'errors': errors
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class SupplierExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Get all suppliers with their data
        suppliers = Supplier.objects.all()
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="suppliers.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Company Name', 'Contact Person', 'Email', 'Phone', 'Mobile',
            'Address', 'City', 'State', 'Postal Code', 'Country',
            'GST Number', 'PAN Number', 'Payment Terms', 'Credit Limit',
            'Outstanding Amount', 'Rating', 'Status', 'Created At'
        ])
        
        for supplier in suppliers:
            address = f"{supplier.address_line1} {supplier.address_line2}".strip()
            writer.writerow([
                supplier.company_name,
                supplier.contact_person,
                supplier.email,
                supplier.phone,
                supplier.mobile,
                address,
                supplier.city,
                supplier.state,
                supplier.postal_code,
                supplier.country,
                supplier.gst_number,
                supplier.pan_number,
                supplier.payment_terms,
                supplier.credit_limit,
                supplier.outstanding_amount,
                supplier.rating,
                'Active' if supplier.is_active else 'Inactive',
                supplier.created_at.strftime('%Y-%m-%d')
            ])
        
        # Log export activity
        ActivityLog.objects.create(
            user=request.user,
            action='SUPPLIER_EXPORTED',
            details={'count': suppliers.count()}
        )
        
        return response

# Supplier Search/Autocomplete
class SupplierSearchView(generics.ListAPIView):
    serializer_class = SupplierListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        if len(query) < 2:
            return Supplier.objects.none()
        
        return Supplier.objects.filter(
            Q(company_name__icontains=query) |
            Q(contact_person__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(gst_number__icontains=query)
        ).filter(is_active=True)[:10]

# Supplier Products by Category
class SupplierProductsByCategoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, supplier_id):
        try:
            supplier = Supplier.objects.get(id=supplier_id)
        except Supplier.DoesNotExist:
            return Response({'error': 'Supplier not found'}, status=404)
        
        # Get all products from this supplier
        supplier_products = SupplierProduct.objects.filter(
            supplier=supplier
        ).select_related('product__category')
        
        # Group by category
        categories = {}
        for sp in supplier_products:
            category_name = sp.product.category.name
            if category_name not in categories:
                categories[category_name] = []
            
            categories[category_name].append({
                'id': sp.product.id,
                'name': sp.product.name,
                'sku': sp.product.sku,
                'supplier_sku': sp.supplier_sku,
                'price': sp.price,
                'lead_time': sp.lead_time_days,
                'min_order': sp.minimum_order_quantity,
                'is_preferred': sp.is_preferred
            })
        
        return Response(categories)
