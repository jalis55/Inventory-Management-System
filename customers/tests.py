from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import ActivityLog, User
from .models import (
    Customer,
    CustomerAddress,
    CustomerContact,
    CustomerDocument,
    CustomerInteraction,
    CustomerLoyalty,
    CustomerPayment,
)


class CustomersEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='customer-user',
            email='customer@example.com',
            password='StrongPass123!',
            first_name='Customer',
            last_name='Manager',
        )
        self.admin = User.objects.create_superuser(
            username='customer-admin',
            email='customer-admin@example.com',
            password='StrongPass123!',
        )
        self.client.force_authenticate(user=self.user)

    def customer_payload(self, **overrides):
        payload = {
            'customer_type': 'retail',
            'company_name': 'Northwind Retail',
            'first_name': 'Alice',
            'last_name': 'Johnson',
            'email': 'alice.customer@example.com',
            'phone': '1234567890',
            'mobile': '01700000000',
            'address_line1': '42 Market Street',
            'address_line2': 'Floor 2',
            'city': 'Dhaka',
            'state': 'Dhaka',
            'postal_code': '1207',
            'country': 'Bangladesh',
            'gst_number': 'GSTNUMBER123456',
            'pan_number': 'ABCDE1234F',
            'tax_id': 'TAX-1',
            'credit_limit': '5000.00',
            'payment_terms': 'immediate',
            'preferred_communication': 'email',
            'do_not_disturb': False,
            'notes': 'VIP potential',
        }
        payload.update(overrides)
        return payload

    def create_customer(self, **overrides):
        data = self.customer_payload(**overrides)
        return Customer.objects.create(
            customer_code=data.pop('customer_code', f"CUST-{overrides.get('first_name', 'ALI')[:3].upper()}-10001"),
            created_by=self.user,
            **data,
        )

    def test_customer_endpoints_require_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse('customer-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_crud_search_and_reports(self):
        first = self.create_customer(
            customer_code='CUST-RET-10001',
            first_name='Zero',
            last_name='Balance',
            email='zero@example.com',
            company_name='Zero Corp',
            outstanding_amount='0.00',
            loyalty_points=0,
            loyalty_tier='bronze',
            state='Chittagong',
        )
        second = self.create_customer(
            customer_code='CUST-COR-10002',
            customer_type='corporate',
            first_name='Loyal',
            last_name='Buyer',
            email='loyal@example.com',
            company_name='Loyal Corp',
            outstanding_amount='300.00',
            loyalty_points=150,
            loyalty_tier='silver',
            state='Dhaka',
        )

        create_response = self.client.post(reverse('customer-list'), self.customer_payload(), format='json')

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        customer = Customer.objects.get(email='alice.customer@example.com')
        self.assertTrue(CustomerLoyalty.objects.filter(customer=customer).exists())
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_CREATED').exists())

        list_response = self.client.get(
            reverse('customer-list'),
            {'search': 'Alice', 'state': 'Dhaka', 'has_outstanding': 'false'},
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)
        self.assertEqual(list_response.data['results'][0]['email'], 'alice.customer@example.com')

        detail_url = reverse('customer-detail', kwargs={'id': customer.id})
        detail_response = self.client.get(detail_url)

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['full_name'], 'Alice Johnson')

        update_response = self.client.patch(detail_url, {'city': 'Sylhet'}, format='json')

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        customer.refresh_from_db()
        self.assertEqual(customer.city, 'Sylhet')
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_UPDATED').exists())

        search_response = self.client.get(reverse('customer-search'), {'q': 'Lo'})

        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        self.assertEqual(search_response.data['count'], 1)
        self.assertEqual(search_response.data['results'][0]['email'], 'loyal@example.com')

        outstanding_response = self.client.get(reverse('customer-outstanding-report'))

        self.assertEqual(outstanding_response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(outstanding_response.data['total_outstanding']), '300')
        self.assertEqual(outstanding_response.data['customer_count'], 1)
        self.assertEqual(outstanding_response.data['customers'][0]['email'], 'loyal@example.com')

        loyalty_response = self.client.get(reverse('customer-loyalty-report'))

        self.assertEqual(loyalty_response.status_code, status.HTTP_200_OK)
        self.assertEqual(loyalty_response.data['total_points'], 150)
        self.assertEqual(loyalty_response.data['customer_count'], 1)
        self.assertEqual(loyalty_response.data['customers'][0]['email'], 'loyal@example.com')

        delete_response = self.client.delete(detail_url)

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Customer.objects.filter(id=customer.id).exists())
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_DELETED').exists())
        self.assertTrue(Customer.objects.filter(id=first.id).exists())
        self.assertTrue(Customer.objects.filter(id=second.id).exists())

    def test_customer_address_endpoints_and_default_switching(self):
        customer = self.create_customer(customer_code='CUST-RET-20001')
        existing = CustomerAddress.objects.create(
            customer=customer,
            address_type='billing',
            address_line1='Old Address',
            city='Dhaka',
            state='Dhaka',
            postal_code='1207',
            country='Bangladesh',
            is_default=True,
        )

        list_url = reverse('customer-address-list', kwargs={'customer_id': customer.id})
        create_response = self.client.post(
            list_url,
            {
                'address_type': 'shipping',
                'address_line1': 'New Address',
                'address_line2': '',
                'city': 'Sylhet',
                'state': 'Sylhet',
                'postal_code': '3100',
                'country': 'Bangladesh',
                'is_default': True,
                'delivery_instructions': 'Leave at front desk',
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        existing.refresh_from_db()
        self.assertFalse(existing.is_default)
        address = CustomerAddress.objects.get(id=create_response.data['id'])
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_ADDRESS_ADDED').exists())

        detail_url = reverse('customer-address-detail', kwargs={'id': address.id})
        update_response = self.client.patch(detail_url, {'city': 'Chittagong'}, format='json')

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(CustomerAddress.objects.get(id=address.id).city, 'Chittagong')
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_ADDRESS_UPDATED').exists())

        delete_response = self.client.delete(detail_url)

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CustomerAddress.objects.filter(id=address.id).exists())
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_ADDRESS_DELETED').exists())

    def test_customer_contact_endpoints_and_primary_switching(self):
        customer = self.create_customer(customer_code='CUST-RET-30001')
        existing = CustomerContact.objects.create(
            customer=customer,
            name='Old Contact',
            email='old.contact@example.com',
            phone='12345',
            is_primary=True,
        )

        list_url = reverse('customer-contact-list', kwargs={'customer_id': customer.id})
        create_response = self.client.post(
            list_url,
            {
                'name': 'New Contact',
                'designation': 'Buyer',
                'email': 'new.contact@example.com',
                'phone': '99999',
                'mobile': '88888',
                'is_primary': True,
                'department': 'Procurement',
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        existing.refresh_from_db()
        self.assertFalse(existing.is_primary)
        contact = CustomerContact.objects.get(id=create_response.data['id'])
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_CONTACT_ADDED').exists())

        detail_url = reverse('customer-contact-detail', kwargs={'id': contact.id})
        update_response = self.client.patch(detail_url, {'designation': 'Senior Buyer'}, format='json')

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(CustomerContact.objects.get(id=contact.id).designation, 'Senior Buyer')
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_CONTACT_UPDATED').exists())

        delete_response = self.client.delete(detail_url)

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CustomerContact.objects.filter(id=contact.id).exists())
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_CONTACT_DELETED').exists())

    def test_customer_interaction_endpoints_update_loyalty_activity(self):
        customer = self.create_customer(customer_code='CUST-RET-40001')
        loyalty = CustomerLoyalty.objects.create(customer=customer)

        list_url = reverse('customer-interaction-list', kwargs={'customer_id': customer.id})
        create_response = self.client.post(
            list_url,
            {
                'interaction_type': 'call',
                'subject': 'Follow up call',
                'description': 'Discussed next purchase',
                'contact_person': 'Alice',
                'duration_minutes': 10,
                'outcome': 'Positive',
                'follow_up_required': True,
                'follow_up_date': '2026-03-20',
                'priority': 'medium',
                'status': 'open',
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        loyalty.refresh_from_db()
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_INTERACTION_LOGGED').exists())

        interaction = CustomerInteraction.objects.get(customer=customer, subject='Follow up call')
        detail_url = reverse('customer-interaction-detail', kwargs={'id': interaction.id})
        update_response = self.client.patch(
            detail_url,
            {'status': 'resolved', 'follow_up_required': True},
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        interaction.refresh_from_db()
        self.assertFalse(interaction.follow_up_required)
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_INTERACTION_UPDATED').exists())

        delete_response = self.client.delete(detail_url)

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CustomerInteraction.objects.filter(id=interaction.id).exists())
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_INTERACTION_DELETED').exists())

    def test_customer_payment_and_loyalty_endpoints(self):
        customer = self.create_customer(
            customer_code='CUST-RET-50001',
            outstanding_amount='1200.00',
            loyalty_points=0,
            loyalty_tier='bronze',
        )
        loyalty = CustomerLoyalty.objects.create(customer=customer)

        create_response = self.client.post(
            reverse('customer-payment-list', kwargs={'customer_id': customer.id}),
            {
                'payment_date': '2026-03-14',
                'amount': '250.00',
                'payment_method': 'cash',
                'reference_number': 'PAY-1',
                'notes': 'Partial payment',
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        payment = CustomerPayment.objects.get(customer=customer, reference_number='PAY-1')
        customer.refresh_from_db()
        loyalty.refresh_from_db()
        self.assertEqual(str(customer.outstanding_amount), '950.00')
        self.assertEqual(loyalty.points, 2)
        self.assertEqual(loyalty.lifetime_points, 2)
        self.assertEqual(str(loyalty.lifetime_purchase), '250.00')
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_PAYMENT_RECEIVED').exists())

        payment_detail = self.client.get(reverse('customer-payment-detail', kwargs={'id': payment.id}))

        self.assertEqual(payment_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(str(payment_detail.data['amount']), '250.00')

        loyalty_response = self.client.patch(
            reverse('customer-loyalty', kwargs={'customer_id': customer.id}),
            {'tier': 'silver', 'points': 300, 'lifetime_points': 300, 'points_to_next_tier': 700},
            format='json',
        )

        self.assertEqual(loyalty_response.status_code, status.HTTP_200_OK)
        customer.refresh_from_db()
        self.assertEqual(customer.loyalty_tier, 'silver')
        self.assertEqual(customer.loyalty_points, 300)
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_LOYALTY_UPDATED').exists())

    def test_customer_document_endpoints(self):
        customer = self.create_customer(customer_code='CUST-RET-60001')
        upload = SimpleUploadedFile('gst.pdf', b'file-content', content_type='application/pdf')

        create_response = self.client.post(
            reverse('customer-document-list', kwargs={'customer_id': customer.id}),
            {
                'document_type': 'gst',
                'document_number': 'GST-123',
                'document_file': upload,
                'notes': 'Uploaded',
            },
            format='multipart',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        document = CustomerDocument.objects.get(id=create_response.data['id'])
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_DOCUMENT_UPLOADED').exists())

        detail_url = reverse('customer-document-detail', kwargs={'id': document.id})
        update_response = self.client.patch(
            detail_url,
            {'is_verified': True},
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        document.refresh_from_db()
        self.assertEqual(document.verified_by, self.user)
        self.assertIsNotNone(document.verified_at)
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_DOCUMENT_UPDATED').exists())

        delete_response = self.client.delete(detail_url)

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CustomerDocument.objects.filter(id=document.id).exists())
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_DOCUMENT_DELETED').exists())

    def test_customer_statistics_and_export_endpoints(self):
        customer = self.create_customer(
            customer_code='CUST-RET-70001',
            first_name='Report',
            last_name='User',
            email='report@example.com',
            outstanding_amount='400.00',
            loyalty_points=50,
            loyalty_tier='silver',
        )
        CustomerLoyalty.objects.create(customer=customer, points=50, lifetime_points=50, lifetime_purchase='5000.00')
        CustomerInteraction.objects.create(
            customer=customer,
            interaction_type='email',
            subject='Welcome',
            description='Sent onboarding mail',
            created_by=self.user,
        )

        stats_response = self.client.get(reverse('customer-statistics'))

        self.assertEqual(stats_response.status_code, status.HTTP_200_OK)
        self.assertEqual(stats_response.data['total_customers'], 1)
        self.assertEqual(stats_response.data['active_customers'], 1)
        self.assertEqual(str(stats_response.data['total_outstanding']), '400')
        self.assertEqual(stats_response.data['customers_with_outstanding'], 1)
        self.assertEqual(stats_response.data['top_customers'][0]['first_name'], 'Report')
        self.assertEqual(stats_response.data['recent_interactions'][0]['subject'], 'Welcome')

        export_response = self.client.get(reverse('customer-export'))

        self.assertEqual(export_response.status_code, status.HTTP_200_OK)
        self.assertEqual(export_response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="customers.csv"', export_response['Content-Disposition'])
        self.assertIn('report@example.com', export_response.content.decode('utf-8'))
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_EXPORTED').exists())

    def test_customer_bulk_upload_permissions_and_csv_import(self):
        file = SimpleUploadedFile(
            'customers.csv',
            (
                'customer_type,first_name,last_name,email,phone,address,city,state,postal_code,country\n'
                'retail,Bulk,User,bulk@example.com,1234,Street,Dhaka,Dhaka,1207,Bangladesh\n'
            ).encode('utf-8'),
            content_type='text/csv',
        )
        forbidden = self.client.post(reverse('customer-bulk-upload'), {'file': file}, format='multipart')

        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.admin)
        admin_file = SimpleUploadedFile(
            'customers.csv',
            (
                'customer_type,first_name,last_name,email,phone,address,city,state,postal_code,country\n'
                'retail,Bulk,User,bulk@example.com,1234,Street,Dhaka,Dhaka,1207,Bangladesh\n'
                ',Missing,,missing@example.com,1234,Street,Dhaka,Dhaka,1207,Bangladesh\n'
            ).encode('utf-8'),
            content_type='text/csv',
        )

        response = self.client.post(reverse('customer-bulk-upload'), {'file': admin_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Successfully created 1 customers')
        self.assertEqual(len(response.data['errors']), 1)
        self.assertTrue(Customer.objects.filter(email='bulk@example.com').exists())
        self.assertTrue(CustomerLoyalty.objects.filter(customer__email='bulk@example.com').exists())
        self.assertTrue(ActivityLog.objects.filter(action='CUSTOMER_BULK_UPLOAD').exists())
