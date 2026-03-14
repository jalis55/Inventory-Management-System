from decimal import Decimal
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import ActivityLog, User
from customers.models import Customer
from purchases.models import PurchaseOrder, PurchaseOrderItem
from sales.models import SalesOrder, SalesOrderItem
from suppliers.models import Supplier
from products.models import Brand, Category, Product, Unit

from .models import (
    CustomerDue,
    DueReminder,
    PaymentCollection,
    PaymentDisbursement,
    SupplierDue,
    WriteOff,
)


class DuesEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='dues-user',
            email='dues@example.com',
            password='StrongPass123!',
            first_name='Dues',
            last_name='Manager',
        )
        self.admin_user = User.objects.create_superuser(
            username='dues-admin',
            email='dues-admin@example.com',
            password='StrongPass123!',
            first_name='Admin',
            last_name='Approver',
        )
        self.client.force_authenticate(user=self.user)

        self.category = Category.objects.create(name='Electronics')
        self.brand = Brand.objects.create(name='Acme')
        self.unit = Unit.objects.create(name='Piece', abbreviation='pc')
        self.product = Product.objects.create(
            sku='DUE-1000',
            barcode='DUE-BAR-1000',
            name='Industrial Router',
            description='Router',
            category=self.category,
            brand=self.brand,
            unit=self.unit,
            cost_price=Decimal('80.00'),
            selling_price=Decimal('120.00'),
            wholesale_price=Decimal('100.00'),
            mrp=Decimal('130.00'),
            tax_rate=Decimal('5.00'),
            current_stock=25,
            minimum_stock=2,
            maximum_stock=60,
            reorder_point=5,
            created_by=self.user,
        )

        self.customer = Customer.objects.create(
            customer_code='CUST-DUE-10001',
            customer_type='retail',
            company_name='Northwind Retail',
            first_name='Alice',
            last_name='Buyer',
            email='alice.dues@example.com',
            phone='1234567890',
            mobile='01700000000',
            address_line1='42 Market Street',
            address_line2='Floor 2',
            city='Dhaka',
            state='Dhaka',
            postal_code='1207',
            country='Bangladesh',
            gst_number='GSTNUMBER123456',
            pan_number='ABCDE1234F',
            tax_id='TAX-1',
            credit_limit=Decimal('5000.00'),
            outstanding_amount=Decimal('310.00'),
            payment_terms='net_30',
            preferred_communication='email',
            created_by=self.user,
        )
        self.supplier = Supplier.objects.create(
            company_name='Northwind Supplies',
            contact_person='Bob Supplier',
            email='supplier.dues@example.com',
            phone='1234567890',
            mobile='01700000000',
            website='https://supplier.example.com',
            address_line1='42 Market Street',
            address_line2='Floor 2',
            city='Dhaka',
            state='Dhaka',
            postal_code='1207',
            country='Bangladesh',
            gst_number='GSTNUMBER123456',
            pan_number='ABCDE1234F',
            tax_id='TAX-1',
            payment_terms='net_30',
            credit_limit=Decimal('5000.00'),
            outstanding_amount=Decimal('220.00'),
            bank_name='Bank',
            bank_account='123456',
            bank_ifsc='BANK0001',
            created_by=self.user,
        )

        self.sales_order = self.create_sales_order()
        self.purchase_order = self.create_purchase_order()
        self.customer_due, _ = CustomerDue.objects.get_or_create(
            sales_order=self.sales_order,
            defaults={'customer': self.customer, 'created_by': self.user},
        )
        self.customer_due.customer = self.customer
        self.customer_due.due_date = timezone.now().date() - timedelta(days=15)
        self.customer_due.original_amount = Decimal('310.00')
        self.customer_due.paid_amount = Decimal('0.00')
        self.customer_due.created_by = self.user
        self.customer_due.save()
        CustomerDue.objects.filter(id=self.customer_due.id).update(status='overdue', days_overdue=15)
        self.customer_due.refresh_from_db()

        self.supplier_due, _ = SupplierDue.objects.get_or_create(
            purchase_order=self.purchase_order,
            defaults={'supplier': self.supplier, 'created_by': self.user},
        )
        self.supplier_due.supplier = self.supplier
        self.supplier_due.due_date = timezone.now().date() - timedelta(days=40)
        self.supplier_due.original_amount = Decimal('220.00')
        self.supplier_due.paid_amount = Decimal('0.00')
        self.supplier_due.created_by = self.user
        self.supplier_due.save()
        SupplierDue.objects.filter(id=self.supplier_due.id).update(status='overdue', days_overdue=40)
        self.supplier_due.refresh_from_db()

    def create_sales_order(self):
        sales_order = SalesOrder.objects.create(
            customer=self.customer,
            sales_person=self.user,
            expected_delivery_date=timezone.now().date(),
            shipping_address='42 Market Street',
            billing_address='42 Market Street',
            payment_method='credit',
            payment_terms='Net 30',
            order_status='confirmed',
            payment_status='pending',
            created_by=self.user,
        )
        item = SalesOrderItem.objects.create(
            sales_order=sales_order,
            product=self.product,
            quantity=2,
            unit_price=Decimal('150.00'),
            discount_percent=Decimal('0.00'),
            tax_rate=Decimal('5.00'),
        )
        sales_order.subtotal = item.subtotal
        sales_order.tax_amount = item.tax_amount
        sales_order.total_amount = item.total
        sales_order.due_amount = item.total
        sales_order.save()
        return sales_order

    def create_purchase_order(self):
        purchase_order = PurchaseOrder.objects.create(
            supplier=self.supplier,
            requested_by=self.user,
            expected_delivery_date=timezone.now().date(),
            payment_terms='Net 30',
            order_status='approved',
            payment_status='pending',
            created_by=self.user,
        )
        item = PurchaseOrderItem.objects.create(
            purchase_order=purchase_order,
            product=self.product,
            quantity=2,
            unit_price=Decimal('100.00'),
            discount_percent=Decimal('0.00'),
            tax_rate=Decimal('5.00'),
        )
        purchase_order.subtotal = item.subtotal
        purchase_order.tax_amount = item.tax_amount
        purchase_order.total_amount = item.total
        purchase_order.due_amount = item.total
        purchase_order.save()
        return purchase_order

    def test_dues_endpoints_require_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse('dues-dashboard'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_and_supplier_due_list_and_detail_endpoints(self):
        customer_list = self.client.get(
            reverse('customer-due-list'),
            {'customer': str(self.customer.id)},
        )
        supplier_list = self.client.get(
            reverse('supplier-due-list'),
            {'supplier': str(self.supplier.id)},
        )

        self.assertEqual(customer_list.status_code, status.HTTP_200_OK)
        self.assertEqual(customer_list.data['count'], 1)
        self.assertEqual(customer_list.data['results'][0]['customer_details']['email'], 'alice.dues@example.com')

        self.assertEqual(supplier_list.status_code, status.HTTP_200_OK)
        self.assertEqual(supplier_list.data['count'], 1)
        self.assertEqual(supplier_list.data['results'][0]['supplier_details']['email'], 'supplier.dues@example.com')

        customer_detail = self.client.get(reverse('customer-due-detail', kwargs={'id': self.customer_due.id}))
        supplier_detail = self.client.get(reverse('supplier-due-detail', kwargs={'id': self.supplier_due.id}))

        self.assertEqual(customer_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(customer_detail.data['sales_order_details']['order_number'], self.sales_order.order_number)
        self.assertEqual(supplier_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(supplier_detail.data['purchase_order_details']['po_number'], self.purchase_order.po_number)

    def test_payment_collection_and_receipt_endpoints(self):
        response = self.client.post(
            reverse('collection-list'),
            {
                'customer_due': str(self.customer_due.id),
                'amount': '100.00',
                'payment_method': 'cash',
                'reference_number': 'COL-100',
                'transaction_id': 'TXN-100',
                'notes': 'Collected in cash',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        collection = PaymentCollection.objects.get(reference_number='COL-100')
        self.customer_due.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertTrue(collection.receipt_generated)
        self.assertEqual(str(self.customer_due.paid_amount), '100.00')
        self.assertEqual(str(self.customer_due.remaining_amount), '210.00')
        self.assertEqual(self.customer_due.status, 'overdue')
        self.assertEqual(str(self.customer.outstanding_amount), '210.00')
        self.assertTrue(ActivityLog.objects.filter(action='PAYMENT_COLLECTED').exists())

        list_response = self.client.get(reverse('collection-list'))
        receipt_response = self.client.get(reverse('collection-receipt', kwargs={'id': collection.id}))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)
        self.assertEqual(receipt_response.status_code, status.HTTP_200_OK)
        self.assertEqual(receipt_response.data['receipt_number'], collection.receipt_number)
        self.assertEqual(receipt_response.data['customer']['email'], 'alice.dues@example.com')

    def test_payment_disbursement_endpoint_updates_supplier_due(self):
        response = self.client.post(
            reverse('disbursement-list'),
            {
                'supplier_due': str(self.supplier_due.id),
                'amount': '120.00',
                'payment_method': 'bank_transfer',
                'reference_number': 'DIS-120',
                'transaction_id': 'TXN-200',
                'notes': 'Partial supplier payment',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        disbursement = PaymentDisbursement.objects.get(reference_number='DIS-120')
        self.supplier_due.refresh_from_db()
        self.supplier.refresh_from_db()
        self.assertEqual(str(self.supplier_due.paid_amount), '120.00')
        self.assertEqual(str(self.supplier_due.remaining_amount), '100.00')
        self.assertEqual(self.supplier_due.status, 'overdue')
        self.assertEqual(str(self.supplier.outstanding_amount), '100.00')
        self.assertTrue(disbursement.voucher_number)
        self.assertTrue(ActivityLog.objects.filter(action='PAYMENT_DISBURSED').exists())

    def test_due_reminder_create_and_send(self):
        response = self.client.post(
            reverse('reminder-list'),
            {
                'customer_due': str(self.customer_due.id),
                'supplier_due': None,
                'reminder_type': 'email',
                'scheduled_date': (timezone.now().date() + timedelta(days=1)).isoformat(),
                'subject': 'Payment reminder',
                'message': 'Please clear the outstanding amount.',
                'status': 'pending',
                'response_received': False,
                'response_notes': '',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        reminder = DueReminder.objects.get(customer_due=self.customer_due)
        self.customer_due.refresh_from_db()
        self.assertEqual(self.customer_due.reminder_count, 1)
        self.assertEqual(self.customer_due.last_reminder_sent, reminder.scheduled_date)
        self.assertTrue(ActivityLog.objects.filter(action='DUE_REMINDER_CREATED').exists())

        send_response = self.client.post(reverse('reminder-send', kwargs={'id': reminder.id}), format='json')

        self.assertEqual(send_response.status_code, status.HTTP_200_OK)
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, 'sent')
        self.assertIsNotNone(reminder.sent_at)
        self.assertTrue(ActivityLog.objects.filter(action='DUE_REMINDER_SENT').exists())

    def test_write_off_requires_admin_and_can_be_approved(self):
        create_url = reverse('writeoff-list')
        payload = {
            'customer_due': str(self.customer_due.id),
            'amount': '50.00',
            'reason': 'other',
            'notes': 'Small balance written off',
        }

        forbidden_response = self.client.post(create_url, payload, format='json')
        self.assertEqual(forbidden_response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.admin_user)

        create_response = self.client.post(create_url, payload, format='json')

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        write_off = WriteOff.objects.get(customer_due=self.customer_due)
        self.customer_due.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.customer_due.status, 'written_off')
        self.assertIn('Written off: 50.00', self.customer_due.notes)
        self.assertEqual(str(self.customer.outstanding_amount), '260.00')
        self.assertTrue(ActivityLog.objects.filter(action='WRITE_OFF_CREATED').exists())

        approve_response = self.client.post(
            reverse('writeoff-approve', kwargs={'id': write_off.id}),
            format='json',
        )

        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        write_off.refresh_from_db()
        self.assertEqual(write_off.approved_by, self.admin_user)
        self.assertIsNotNone(write_off.approved_at)
        self.assertTrue(ActivityLog.objects.filter(action='WRITE_OFF_APPROVED').exists())

    def test_dashboard_and_aging_reports(self):
        PaymentCollection.objects.create(
            customer_due=self.customer_due,
            amount=Decimal('100.00'),
            payment_method='cash',
            reference_number='COL-200',
            transaction_id='TXN-300',
            receipt_generated=True,
            collected_by=self.user,
        )
        PaymentDisbursement.objects.create(
            supplier_due=self.supplier_due,
            amount=Decimal('120.00'),
            payment_method='bank_transfer',
            reference_number='DIS-200',
            transaction_id='TXN-400',
            disbursed_by=self.user,
        )

        dashboard_response = self.client.get(reverse('dues-dashboard'))
        customer_aging_response = self.client.get(reverse('customer-aging'))
        supplier_aging_response = self.client.get(reverse('supplier-aging'))

        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(dashboard_response.data['summary']['total_customer_outstanding']), '310.00')
        self.assertEqual(str(dashboard_response.data['summary']['total_supplier_outstanding']), '220.00')
        self.assertEqual(str(dashboard_response.data['summary']['net_receivable']), '90.00')
        self.assertEqual(len(dashboard_response.data['recent_collections']), 1)
        self.assertEqual(len(dashboard_response.data['recent_disbursements']), 1)
        self.assertGreaterEqual(len(dashboard_response.data['overdue_customers']), 0)
        self.assertGreaterEqual(len(dashboard_response.data['overdue_suppliers']), 0)

        self.assertEqual(customer_aging_response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(customer_aging_response.data['totals']['days_1_30']), '310.00')
        self.assertEqual(customer_aging_response.data['report'][0]['company_name'], 'Northwind Retail')

        self.assertEqual(supplier_aging_response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(supplier_aging_response.data['totals']['days_31_60']), '220.00')
        self.assertEqual(supplier_aging_response.data['report'][0]['supplier_name'], 'Northwind Supplies')
