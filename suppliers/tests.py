from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import ActivityLog, User
from products.models import Brand, Category, Product, Unit
from .models import Supplier, SupplierProduct


class SuppliersEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='supplier-user',
            email='supplier@example.com',
            password='StrongPass123!',
            first_name='Supplier',
            last_name='Manager',
        )
        self.admin = User.objects.create_superuser(
            username='supplier-admin',
            email='supplier-admin@example.com',
            password='StrongPass123!',
        )
        self.client.force_authenticate(user=self.user)

        self.category = Category.objects.create(name='Networking')
        self.brand = Brand.objects.create(name='Acme Supplies')
        self.unit = Unit.objects.create(name='Piece', abbreviation='pc')
        self.product = Product.objects.create(
            sku='SUP-1000',
            barcode='SUP-BAR-1000',
            name='Industrial Router',
            description='Industrial grade router',
            category=self.category,
            brand=self.brand,
            unit=self.unit,
            cost_price='120.00',
            selling_price='180.00',
            wholesale_price='150.00',
            mrp='200.00',
            tax_rate='5.00',
            current_stock=5,
            minimum_stock=1,
            maximum_stock=20,
            reorder_point=3,
            created_by=self.user,
        )

    def supplier_payload(self, **overrides):
        payload = {
            'company_name': 'Northwind Traders',
            'contact_person': 'Alice Johnson',
            'email': 'alice@northwind.example',
            'phone': '1234567890',
            'mobile': '0987654321',
            'website': 'https://northwind.example',
            'address_line1': '42 Market Street',
            'address_line2': 'Suite 7',
            'city': 'Dhaka',
            'state': 'Dhaka',
            'postal_code': '1207',
            'country': 'Bangladesh',
            'gst_number': 'GSTNUMBER123456',
            'pan_number': 'ABCDE1234F',
            'tax_id': 'TAX-1',
            'payment_terms': 'net_30',
            'credit_limit': '5000.00',
            'bank_name': 'Test Bank',
            'bank_account': '123456789',
            'bank_ifsc': 'BANK0001',
            'notes': 'Preferred vendor',
            'is_active': True,
            'rating': 4,
        }
        payload.update(overrides)
        return payload

    def create_supplier(self, **overrides):
        data = self.supplier_payload(**overrides)
        return Supplier.objects.create(created_by=self.user, **data)

    def test_supplier_endpoints_require_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse('supplier-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_supplier_crud_filters_and_search(self):
        self.create_supplier(
            company_name='Zero Balance Inc',
            email='zero@example.com',
            gst_number='ZERO12345678901',
            outstanding_amount='0.00',
            rating=2,
            city='Chittagong',
            state='Chittagong',
            payment_terms='immediate',
        )

        create_response = self.client.post(reverse('supplier-list'), self.supplier_payload(), format='json')

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        supplier = Supplier.objects.get(company_name='Northwind Traders')
        self.assertEqual(supplier.created_by, self.user)
        self.assertTrue(ActivityLog.objects.filter(action='SUPPLIER_CREATED').exists())

        list_response = self.client.get(
            reverse('supplier-list'),
            {'search': 'Northwind', 'state': 'Dhaka', 'has_outstanding': 'false'},
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)
        self.assertEqual(list_response.data['results'][0]['company_name'], 'Northwind Traders')

        detail_url = reverse('supplier-detail', kwargs={'id': supplier.id})
        detail_response = self.client.get(detail_url)

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['company_name'], 'Northwind Traders')

        update_response = self.client.patch(
            detail_url,
            {'contact_person': 'Alice Updated', 'rating': 5},
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        supplier.refresh_from_db()
        self.assertEqual(supplier.contact_person, 'Alice Updated')
        self.assertTrue(ActivityLog.objects.filter(action='SUPPLIER_UPDATED').exists())

        search_response = self.client.get(reverse('supplier-search'), {'q': 'No'})

        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        self.assertEqual(search_response.data['count'], 1)
        self.assertEqual(search_response.data['results'][0]['company_name'], 'Northwind Traders')

        delete_response = self.client.delete(detail_url)

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Supplier.objects.filter(id=supplier.id).exists())
        self.assertTrue(ActivityLog.objects.filter(action='SUPPLIER_DELETED').exists())

    def test_supplier_product_endpoints_and_category_grouping(self):
        supplier = self.create_supplier(outstanding_amount='250.00')
        second_category = Category.objects.create(name='Power')
        second_product = Product.objects.create(
            sku='SUP-2000',
            barcode='SUP-BAR-2000',
            name='UPS Unit',
            description='Power backup',
            category=second_category,
            brand=self.brand,
            unit=self.unit,
            cost_price='200.00',
            selling_price='260.00',
            wholesale_price='230.00',
            mrp='280.00',
            tax_rate='5.00',
            current_stock=3,
            minimum_stock=1,
            maximum_stock=10,
            reorder_point=2,
            created_by=self.user,
        )

        list_url = reverse('supplier-product-list', kwargs={'supplier_id': supplier.id})
        create_response = self.client.post(
            list_url,
            {
                'product': str(self.product.id),
                'supplier_sku': 'NW-ROUTER',
                'price': '140.00',
                'lead_time_days': 5,
                'minimum_order_quantity': 2,
                'is_preferred': True,
                'notes': 'Fast delivery',
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        supplier_product = SupplierProduct.objects.get(supplier=supplier, product=self.product)
        self.assertTrue(ActivityLog.objects.filter(action='SUPPLIER_PRODUCT_ADDED').exists())

        SupplierProduct.objects.create(
            supplier=supplier,
            product=second_product,
            supplier_sku='NW-UPS',
            price='220.00',
            lead_time_days=8,
            minimum_order_quantity=1,
        )

        list_response = self.client.get(list_url)

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 2)

        detail_url = reverse('supplier-product-detail', kwargs={'id': supplier_product.id})
        update_response = self.client.patch(detail_url, {'price': '145.00'}, format='json')

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        supplier_product.refresh_from_db()
        self.assertEqual(str(supplier_product.price), '145.00')
        self.assertTrue(ActivityLog.objects.filter(action='SUPPLIER_PRODUCT_UPDATED').exists())

        category_response = self.client.get(
            reverse('supplier-products-category', kwargs={'supplier_id': supplier.id})
        )

        self.assertEqual(category_response.status_code, status.HTTP_200_OK)
        self.assertIn('Networking', category_response.data)
        self.assertIn('Power', category_response.data)
        self.assertEqual(category_response.data['Networking'][0]['name'], 'Industrial Router')

        delete_response = self.client.delete(detail_url)

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SupplierProduct.objects.filter(id=supplier_product.id).exists())
        self.assertTrue(ActivityLog.objects.filter(action='SUPPLIER_PRODUCT_REMOVED').exists())

    def test_supplier_payment_endpoint_updates_outstanding_amount(self):
        supplier = self.create_supplier(outstanding_amount='500.00')

        response = self.client.post(
            reverse('supplier-payment', kwargs={'supplier_id': supplier.id}),
            {
                'amount': '125.50',
                'payment_date': '2026-03-14',
                'payment_method': 'bank_transfer',
                'reference_number': 'PAY-100',
                'notes': 'Partial payment',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        supplier.refresh_from_db()
        self.assertEqual(str(supplier.outstanding_amount), '374.50')
        self.assertEqual(str(response.data['new_outstanding']), '374.50')
        self.assertTrue(ActivityLog.objects.filter(action='SUPPLIER_PAYMENT_MADE').exists())

    def test_supplier_statistics_endpoint(self):
        supplier_a = self.create_supplier(company_name='Stats One', email='stats1@example.com', gst_number='STATS1234567890', outstanding_amount='100.00', rating=5)
        supplier_b = self.create_supplier(
            company_name='Stats Two',
            email='stats2@example.com',
            gst_number='STATX1234567890',
            outstanding_amount='0.00',
            rating=3,
            is_active=False,
            state='Khulna',
            payment_terms='immediate',
        )
        SupplierProduct.objects.create(supplier=supplier_a, product=self.product, price='140.00')

        response = self.client.get(reverse('supplier-statistics'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_suppliers'], 2)
        self.assertEqual(response.data['active_suppliers'], 1)
        self.assertEqual(str(response.data['total_outstanding']), '100')
        self.assertEqual(response.data['suppliers_with_outstanding'], 1)
        self.assertEqual(response.data['average_rating'], 5.0)
        self.assertEqual(response.data['top_suppliers'][0]['company_name'], 'Stats One')
        self.assertEqual(response.data['payment_terms_stats'][0]['count'], 1)
        self.assertEqual(response.data['state_stats'][0]['count'], 1)
        self.assertFalse(Supplier.objects.filter(id=supplier_b.id, is_active=True).exists())

    def test_supplier_export_endpoint_returns_csv(self):
        self.create_supplier(company_name='Export Co', email='export@example.com', gst_number='EXPORT123456789')

        response = self.client.get(reverse('supplier-export'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="suppliers.csv"', response['Content-Disposition'])
        self.assertIn('Export Co', response.content.decode('utf-8'))
        self.assertTrue(ActivityLog.objects.filter(action='SUPPLIER_EXPORTED').exists())

    def test_supplier_bulk_upload_requires_admin(self):
        file = SimpleUploadedFile(
            'suppliers.csv',
            b'company_name,contact_person,email,phone,address_line1,city,state,postal_code,gst_number\n'
            b'Bulk Co,Bob,bulk@example.com,1234,Street,Dhaka,Dhaka,1207,BULK12345678901\n',
            content_type='text/csv',
        )

        response = self.client.post(reverse('supplier-bulk-upload'), {'file': file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_supplier_bulk_upload_creates_suppliers_from_csv(self):
        self.client.force_authenticate(user=self.admin)
        file = SimpleUploadedFile(
            'suppliers.csv',
            (
                'company_name,contact_person,email,phone,address_line1,city,state,postal_code,gst_number\n'
                'Bulk Co,Bob,bulk@example.com,1234,Street,Dhaka,Dhaka,1207,BULK12345678901\n'
                ',Missing,missing@example.com,1234,Street,Dhaka,Dhaka,1207,MISS12345678901\n'
            ).encode('utf-8'),
            content_type='text/csv',
        )

        response = self.client.post(reverse('supplier-bulk-upload'), {'file': file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Successfully created 1 suppliers')
        self.assertEqual(len(response.data['errors']), 1)
        self.assertTrue(Supplier.objects.filter(company_name='Bulk Co').exists())
        self.assertTrue(ActivityLog.objects.filter(action='SUPPLIER_BULK_UPLOAD').exists())
