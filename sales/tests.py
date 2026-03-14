from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import ActivityLog, User
from customers.models import Customer, CustomerLoyalty
from products.models import Brand, Category, Product, StockMovement, Unit
from .models import Quotation, QuotationItem, SalesOrder, SalesOrderItem, SalesPayment, SalesReturn


class SalesEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='sales-user',
            email='sales@example.com',
            password='StrongPass123!',
            first_name='Sales',
            last_name='Rep',
        )
        self.client.force_authenticate(user=self.user)

        self.category = Category.objects.create(name='Electronics')
        self.brand = Brand.objects.create(name='Acme')
        self.unit = Unit.objects.create(name='Piece', abbreviation='pc')
        self.product = Product.objects.create(
            sku='SALE-1000',
            barcode='SALE-BAR-1000',
            name='Industrial Router',
            description='Router',
            category=self.category,
            brand=self.brand,
            unit=self.unit,
            cost_price='100.00',
            selling_price='150.00',
            wholesale_price='125.00',
            mrp='160.00',
            tax_rate='5.00',
            current_stock=20,
            minimum_stock=2,
            maximum_stock=50,
            reorder_point=5,
            created_by=self.user,
        )
        self.customer = Customer.objects.create(
            customer_code='CUST-SAL-10001',
            customer_type='retail',
            company_name='Northwind',
            first_name='Alice',
            last_name='Buyer',
            email='alice.sales@example.com',
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
            credit_limit='5000.00',
            outstanding_amount='1000.00',
            payment_terms='immediate',
            preferred_communication='email',
            created_by=self.user,
        )
        self.loyalty = CustomerLoyalty.objects.create(customer=self.customer)

    def sales_order_payload(self, **overrides):
        payload = {
            'customer': str(self.customer.id),
            'sales_person': str(self.user.id),
            'delivery_date': '2026-03-20',
            'expected_delivery_date': '2026-03-21',
            'discount_type': 'fixed',
            'discount_value': '10.00',
            'tax_type': 'exclusive',
            'shipping_charge': '5.00',
            'other_charges': '0.00',
            'payment_method': 'cash',
            'payment_terms': 'Due on receipt',
            'shipping_address': '42 Market Street',
            'billing_address': '42 Market Street',
            'customer_notes': 'Handle with care',
            'staff_notes': 'Priority order',
            'terms_conditions': 'Standard terms',
            'items': [
                {
                    'product': str(self.product.id),
                    'variant': None,
                    'quantity': 2,
                    'unit_price': '150.00',
                    'discount_percent': '0.00',
                    'tax_rate': '5.00',
                    'notes': 'Main item',
                }
            ],
        }
        payload.update(overrides)
        return payload

    def create_order(self, **overrides):
        order = SalesOrder.objects.create(
            customer=self.customer,
            sales_person=self.user,
            shipping_address='42 Market Street',
            billing_address='42 Market Street',
            payment_method='cash',
            payment_terms='Immediate',
            created_by=self.user,
            **overrides,
        )
        item = SalesOrderItem.objects.create(
            sales_order=order,
            product=self.product,
            quantity=2,
            unit_price=Decimal('150.00'),
            discount_percent=Decimal('0.00'),
            tax_rate=Decimal('5.00'),
        )
        order.subtotal = item.subtotal
        order.tax_amount = item.tax_amount
        order.total_amount = item.total
        order.due_amount = item.total
        order.save()
        return order

    def test_sales_endpoints_require_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse('sales-order-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_sales_order_crud_status_and_stock_updates(self):
        create_response = self.client.post(reverse('sales-order-list'), self.sales_order_payload(), format='json')

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        order = SalesOrder.objects.get(customer=self.customer)
        self.product.refresh_from_db()
        self.customer.refresh_from_db()
        self.loyalty.refresh_from_db()
        self.assertEqual(str(order.total_amount), '310.00')
        self.assertEqual(self.product.current_stock, 18)
        self.assertEqual(self.loyalty.points, 3)
        self.assertEqual(self.customer.loyalty_points, 3)
        self.assertTrue(StockMovement.objects.filter(reference_id=order.id, movement_type='sale').exists())
        self.assertTrue(ActivityLog.objects.filter(action='SALES_ORDER_CREATED').exists())

        detail_url = reverse('sales-order-detail', kwargs={'id': order.id})
        detail_response = self.client.get(detail_url)

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['customer_details']['email'], 'alice.sales@example.com')

        update_response = self.client.patch(detail_url, {'staff_notes': 'Updated note'}, format='json')

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.staff_notes, 'Updated note')
        self.assertTrue(ActivityLog.objects.filter(action='SALES_ORDER_UPDATED').exists())

        status_response = self.client.post(
            reverse('sales-order-status', kwargs={'id': order.id}),
            {'status': 'confirmed'},
            format='json',
        )

        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.order_status, 'confirmed')
        self.assertIsNotNone(order.invoice_number)
        self.assertTrue(ActivityLog.objects.filter(action='SALES_ORDER_STATUS_UPDATED').exists())

        deletable = self.create_order(order_status='draft', payment_status='pending')
        delete_response = self.client.delete(reverse('sales-order-detail', kwargs={'id': deletable.id}))

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SalesOrder.objects.filter(id=deletable.id).exists())
        self.assertTrue(ActivityLog.objects.filter(action='SALES_ORDER_DELETED').exists())

    def test_sales_payment_endpoint_updates_order_and_customer(self):
        order = self.create_order(order_status='confirmed', payment_status='pending')

        response = self.client.post(
            reverse('sales-payment-list', kwargs={'order_id': order.id}),
            {
                'amount': '100.00',
                'payment_method': 'cash',
                'reference_number': 'PAY-100',
                'notes': 'Deposit',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment = SalesPayment.objects.get(sales_order=order, reference_number='PAY-100')
        order.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(str(order.paid_amount), '100.00')
        self.assertEqual(order.payment_status, 'partial')
        self.assertEqual(str(order.due_amount), '215.00')
        self.assertEqual(str(self.customer.outstanding_amount), '900.00')
        self.assertEqual(payment.status, 'completed')
        self.assertTrue(ActivityLog.objects.filter(action='SALES_PAYMENT_RECEIVED').exists())

        list_response = self.client.get(reverse('sales-payment-list', kwargs={'order_id': order.id}))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)

    def test_sales_return_create_and_approve(self):
        order = self.create_order(order_status='delivered', payment_status='paid')
        order.paid_amount = order.total_amount
        order.save(update_fields=['paid_amount'])
        self.loyalty.points = 5
        self.loyalty.save(update_fields=['points'])

        create_response = self.client.post(
            reverse('sales-return-list', kwargs={'order_id': order.id}),
            {
                'reason': 'damaged',
                'customer_notes': 'Damaged in transit',
                'items': [
                    {
                        'order_item_id': str(order.items.first().id),
                        'quantity': 1,
                        'condition': 'damaged',
                        'notes': 'Box was crushed',
                    }
                ],
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        sales_return = SalesReturn.objects.get(sales_order=order)
        order_item = order.items.first()
        self.product.refresh_from_db()
        self.assertEqual(str(sales_return.refund_amount), '150.00')
        self.assertEqual(order_item.returned_quantity, 1)
        self.assertEqual(self.product.current_stock, 21)
        self.assertTrue(ActivityLog.objects.filter(action='SALES_RETURN_CREATED').exists())

        approve_response = self.client.post(
            reverse('sales-return-approve', kwargs={'id': sales_return.id}),
            {'action': 'approve'},
            format='json',
        )

        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        sales_return.refresh_from_db()
        order.refresh_from_db()
        self.loyalty.refresh_from_db()
        self.assertEqual(sales_return.status, 'approved')
        self.assertEqual(str(order.paid_amount), '165.00')
        self.assertEqual(self.loyalty.points, 4)
        self.assertTrue(SalesPayment.objects.filter(sales_order=order, status='refunded').exists())
        self.assertTrue(ActivityLog.objects.filter(action='SALES_RETURN_APPROVED').exists())

    def test_quotation_crud_and_convert_to_order(self):
        create_response = self.client.post(
            reverse('quotation-list'),
            {
                'customer': str(self.customer.id),
                'sales_person': str(self.user.id),
                'valid_until': '2026-03-31',
                'terms_conditions': 'Valid for 7 days',
                'customer_notes': 'Need quick dispatch',
                'items': [
                    {
                        'product': str(self.product.id),
                        'variant': None,
                        'quantity': 2,
                        'unit_price': '150.00',
                        'discount_percent': '10.00',
                        'tax_rate': '5.00',
                        'notes': 'Quoted item',
                    }
                ],
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        quotation = Quotation.objects.get(customer=self.customer)
        self.assertEqual(str(quotation.total_amount), '283.50')
        self.assertTrue(ActivityLog.objects.filter(action='QUOTATION_CREATED').exists())

        detail_response = self.client.get(reverse('quotation-detail', kwargs={'id': quotation.id}))

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['customer_name'], 'Alice Buyer')

        quotation.status = 'accepted'
        quotation.save(update_fields=['status'])
        convert_response = self.client.post(reverse('quotation-convert', kwargs={'id': quotation.id}), {}, format='json')

        self.assertEqual(convert_response.status_code, status.HTTP_200_OK)
        sales_order = SalesOrder.objects.get(id=convert_response.data['order_id'])
        quotation.refresh_from_db()
        self.assertEqual(quotation.status, 'converted')
        self.assertEqual(quotation.converted_to_order, sales_order)
        self.assertEqual(str(sales_order.total_amount), '283.50')
        self.assertTrue(ActivityLog.objects.filter(action='QUOTATION_CONVERTED').exists())

    def test_sales_dashboard_and_reports(self):
        delivered = self.create_order(order_status='delivered', payment_status='paid')
        SalesOrder.objects.filter(id=delivered.id).update(order_date=timezone.now())
        SalesPayment.objects.create(
            sales_order=delivered,
            amount='315.00',
            payment_method='cash',
            status='completed',
            received_by=self.user,
        )
        pending = self.create_order(order_status='processing', payment_status='pending')
        pending.expected_delivery_date = timezone.now().date().replace(day=max(1, timezone.now().date().day - 1))
        pending.save(update_fields=['expected_delivery_date'])

        dashboard_response = self.client.get(reverse('sales-dashboard'))

        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        self.assertEqual(dashboard_response.data['today']['orders'], 1)
        self.assertEqual(dashboard_response.data['pending_orders'], 1)
        self.assertEqual(dashboard_response.data['overdue_orders'], 1)
        self.assertEqual(dashboard_response.data['top_products'][0]['product__name'], 'Industrial Router')

        daily_report = self.client.get(reverse('sales-reports'), {'type': 'daily'})
        self.assertEqual(daily_report.status_code, status.HTTP_200_OK)
        self.assertEqual(daily_report.data['report_type'], 'daily')
        self.assertTrue(len(daily_report.data['data']) >= 1)

        custom_report = self.client.get(
            reverse('sales-reports'),
            {
                'type': 'custom',
                'from_date': timezone.now().date().isoformat(),
                'to_date': timezone.now().date().isoformat(),
            },
        )
        self.assertEqual(custom_report.status_code, status.HTTP_200_OK)
        self.assertEqual(custom_report.data['report_type'], 'custom')
        self.assertEqual(custom_report.data['summary']['total_orders'], 1)
        self.assertEqual(custom_report.data['top_customers'][0]['customer__first_name'], 'Alice')
