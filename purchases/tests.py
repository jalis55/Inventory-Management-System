from decimal import Decimal
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import ActivityLog, User
from products.models import Brand, Category, Product, StockMovement, Unit
from suppliers.models import Supplier
from .models import GoodsReceipt, PurchaseOrder, PurchaseOrderItem, PurchasePayment, PurchaseReturn, SupplierInvoice


class PurchaseEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='purchase-user',
            email='purchase@example.com',
            password='StrongPass123!',
            first_name='Purchase',
            last_name='Manager',
        )
        self.client.force_authenticate(user=self.user)

        self.category = Category.objects.create(name='Electronics')
        self.brand = Brand.objects.create(name='Acme')
        self.unit = Unit.objects.create(name='Piece', abbreviation='pc')
        self.product = Product.objects.create(
            sku='PUR-1000',
            barcode='PUR-BAR-1000',
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
            current_stock=10,
            minimum_stock=2,
            maximum_stock=40,
            reorder_point=5,
            created_by=self.user,
        )
        self.supplier = Supplier.objects.create(
            company_name='Northwind Supplies',
            contact_person='Bob Supplier',
            email='supplier@example.com',
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
            outstanding_amount=Decimal('1000.00'),
            bank_name='Bank',
            bank_account='123456',
            bank_ifsc='BANK0001',
            created_by=self.user,
        )

    def purchase_order_payload(self, **overrides):
        payload = {
            'supplier': str(self.supplier.id),
            'requested_by': str(self.user.id),
            'expected_delivery_date': '2026-03-21',
            'discount_type': None,
            'discount_value': '0.00',
            'tax_type': 'exclusive',
            'shipping_charge': '10.00',
            'other_charges': '0.00',
            'payment_terms': 'Net 30',
            'notes': 'Handle carefully',
            'terms_conditions': 'Standard terms',
            'items': [
                {
                    'product': str(self.product.id),
                    'variant': None,
                    'quantity': 2,
                    'unit_price': '100.00',
                    'discount_percent': '0.00',
                    'tax_rate': '5.00',
                    'notes': 'Main line',
                }
            ],
        }
        payload.update(overrides)
        return payload

    def create_order(self, **overrides):
        order = PurchaseOrder.objects.create(
            supplier=self.supplier,
            requested_by=self.user,
            expected_delivery_date=overrides.pop('expected_delivery_date', timezone.now().date()),
            payment_terms='Net 30',
            created_by=self.user,
            **overrides,
        )
        item = PurchaseOrderItem.objects.create(
            purchase_order=order,
            product=self.product,
            quantity=2,
            unit_price=Decimal('100.00'),
            discount_percent=Decimal('0.00'),
            tax_rate=Decimal('5.00'),
        )
        order.subtotal = item.subtotal
        order.tax_amount = item.tax_amount
        order.total_amount = item.total
        order.due_amount = item.total
        order.save()
        return order

    def create_goods_receipt(self, order):
        goods_receipt = GoodsReceipt.objects.create(
            purchase_order=order,
            received_by=self.user,
            status='completed',
            supplier_invoice_number='INV-100',
        )
        item = order.items.first()
        goods_receipt.items.create(
            purchase_order_item=item,
            ordered_quantity=item.quantity,
            received_quantity=item.quantity,
            rejected_quantity=0,
            accepted_quantity=item.quantity,
        )
        return goods_receipt

    def test_purchase_endpoints_require_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse('purchase-order-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_purchase_order_crud_and_status_update(self):
        create_response = self.client.post(reverse('purchase-order-list'), self.purchase_order_payload(), format='json')

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        order = PurchaseOrder.objects.get(supplier=self.supplier)
        self.assertEqual(str(order.total_amount), '220.00')
        self.assertTrue(ActivityLog.objects.filter(action='PURCHASE_ORDER_CREATED').exists())

        detail_url = reverse('purchase-order-detail', kwargs={'id': order.id})
        detail_response = self.client.get(detail_url)

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['supplier_details']['email'], 'supplier@example.com')

        update_response = self.client.patch(detail_url, {'notes': 'Updated note'}, format='json')

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.notes, 'Updated note')
        self.assertTrue(ActivityLog.objects.filter(action='PURCHASE_ORDER_UPDATED').exists())

        status_response = self.client.post(
            reverse('purchase-order-status', kwargs={'id': order.id}),
            {'status': 'approved'},
            format='json',
        )

        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.order_status, 'approved')
        self.assertEqual(order.approved_by, self.user)
        self.assertTrue(ActivityLog.objects.filter(action='PURCHASE_ORDER_STATUS_UPDATED').exists())

        deletable = self.create_order(order_status='draft')
        delete_response = self.client.delete(reverse('purchase-order-detail', kwargs={'id': deletable.id}))

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(PurchaseOrder.objects.filter(id=deletable.id).exists())
        self.assertTrue(ActivityLog.objects.filter(action='PURCHASE_ORDER_DELETED').exists())

    def test_goods_receipt_endpoint_updates_stock_and_order(self):
        order = self.create_order(order_status='approved')

        response = self.client.post(
            reverse('goods-receipt-list'),
            {
                'purchase_order': str(order.id),
                'supplier_invoice_number': 'INV-100',
                'supplier_invoice_date': '2026-03-14',
                'transport_mode': 'Truck',
                'vehicle_number': 'DHAKA-123',
                'driver_name': 'Driver One',
                'driver_phone': '01800000000',
                'notes': 'All good',
                'items': [
                    {
                        'purchase_order_item_id': str(order.items.first().id),
                        'received_quantity': 2,
                        'rejected_quantity': 0,
                        'batch_number': 'BATCH-1',
                        'storage_location': 'A1',
                    }
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        receipt = GoodsReceipt.objects.get(purchase_order=order)
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.order_status, 'received')
        self.assertEqual(receipt.status, 'completed')
        self.assertEqual(self.product.current_stock, 12)
        self.assertTrue(StockMovement.objects.filter(reference_id=receipt.id, movement_type='purchase').exists())
        self.assertTrue(ActivityLog.objects.filter(action='GOODS_RECEIPT_CREATED').exists())

        list_response = self.client.get(reverse('goods-receipt-list'))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)

        detail_response = self.client.get(reverse('goods-receipt-detail', kwargs={'id': receipt.id}))
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['items'][0]['accepted_quantity'], 2)

    def test_purchase_payment_endpoint_updates_order_and_supplier(self):
        order = self.create_order(order_status='approved')

        response = self.client.post(
            reverse('purchase-payment-list', kwargs={'order_id': order.id}),
            {
                'amount': '100.00',
                'payment_method': 'cash',
                'reference_number': 'PAY-100',
                'notes': 'Advance payment',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment = PurchasePayment.objects.get(purchase_order=order, reference_number='PAY-100')
        order.refresh_from_db()
        self.supplier.refresh_from_db()
        self.assertEqual(str(order.paid_amount), '100.00')
        self.assertEqual(order.payment_status, 'partial')
        self.assertEqual(str(order.due_amount), '110.00')
        self.assertEqual(str(self.supplier.outstanding_amount), '900.00')
        self.assertEqual(payment.status, 'completed')
        self.assertTrue(ActivityLog.objects.filter(action='PURCHASE_PAYMENT_MADE').exists())

    def test_purchase_return_create_and_approve(self):
        order = self.create_order(order_status='received', payment_status='paid')
        order.paid_amount = order.total_amount
        order.save(update_fields=['paid_amount'])
        receipt = self.create_goods_receipt(order)
        self.product.current_stock = 12
        self.product.save(update_fields=['current_stock'])

        response = self.client.post(
            reverse('purchase-return-list', kwargs={'order_id': order.id}),
            {
                'reason': 'damaged',
                'notes': 'Damaged stock',
                'items': [
                    {
                        'receipt_item_id': str(receipt.items.first().id),
                        'quantity': 1,
                        'condition': 'damaged',
                        'notes': 'Broken seal',
                    }
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        purchase_return = PurchaseReturn.objects.get(purchase_order=order)
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(str(purchase_return.refund_amount), '100.00')
        self.assertEqual(self.product.current_stock, 11)
        self.assertEqual(str(order.total_amount), '110.00')
        self.assertTrue(ActivityLog.objects.filter(action='PURCHASE_RETURN_CREATED').exists())

        approve_response = self.client.post(
            reverse('purchase-return-approve', kwargs={'id': purchase_return.id}),
            {'action': 'approve'},
            format='json',
        )

        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        purchase_return.refresh_from_db()
        self.supplier.refresh_from_db()
        self.assertEqual(purchase_return.status, 'approved')
        self.assertEqual(self.supplier.outstanding_amount, Decimal('900.00'))
        self.assertTrue(ActivityLog.objects.filter(action='PURCHASE_RETURN_APPROVED').exists())

    def test_supplier_invoice_endpoint(self):
        order = self.create_order(order_status='received')
        upload = SimpleUploadedFile('invoice.pdf', b'file-content', content_type='application/pdf')

        response = self.client.post(
            reverse('supplier-invoice-list'),
            {
                'supplier': str(self.supplier.id),
                'purchase_order': str(order.id),
                'invoice_number': 'INV-200',
                'invoice_date': '2026-03-14',
                'due_date': '2026-03-31',
                'amount': '200.00',
                'tax_amount': '20.00',
                'total_amount': '220.00',
                'invoice_file': upload,
                'status': 'pending',
                'notes': 'Uploaded invoice',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        invoice = SupplierInvoice.objects.get(invoice_number='INV-200')
        self.assertEqual(invoice.created_by, self.user)
        self.assertTrue(ActivityLog.objects.filter(action='SUPPLIER_INVOICE_CREATED').exists())

    def test_purchase_dashboard_and_reports(self):
        received = self.create_order(order_status='received', expected_delivery_date=timezone.now().date())
        received.payment_status = 'paid'
        received.paid_amount = received.total_amount
        received.due_amount = Decimal('0.00')
        received.save(update_fields=['payment_status', 'paid_amount', 'due_amount'])
        PurchaseOrder.objects.filter(id=received.id).update(order_date=timezone.now().date())
        approved = self.create_order(order_status='approved', expected_delivery_date=timezone.now().date())
        overdue = self.create_order(order_status='ordered', expected_delivery_date=timezone.now().date() - timedelta(days=1))

        dashboard_response = self.client.get(reverse('purchase-dashboard'))

        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        self.assertEqual(dashboard_response.data['month']['orders'], 1)
        self.assertEqual(dashboard_response.data['pending_orders'], 2)
        self.assertEqual(dashboard_response.data['due_this_week'], 1)
        self.assertEqual(dashboard_response.data['overdue_orders'], 1)
        self.assertEqual(str(dashboard_response.data['outstanding_payments']), '420')
        self.assertEqual(dashboard_response.data['top_suppliers'][0]['supplier__company_name'], 'Northwind Supplies')

        monthly = self.client.get(reverse('purchase-reports'), {'type': 'monthly'})
        self.assertEqual(monthly.status_code, status.HTTP_200_OK)
        self.assertEqual(monthly.data['report_type'], 'monthly')

        supplier_report = self.client.get(reverse('purchase-reports'), {'type': 'supplier'})
        self.assertEqual(supplier_report.status_code, status.HTTP_200_OK)
        self.assertEqual(supplier_report.data['report_type'], 'supplier')

        custom = self.client.get(
            reverse('purchase-reports'),
            {
                'type': 'custom',
                'from_date': timezone.now().date().isoformat(),
                'to_date': timezone.now().date().isoformat(),
            },
        )
        self.assertEqual(custom.status_code, status.HTTP_200_OK)
        self.assertEqual(custom.data['report_type'], 'custom')
        self.assertEqual(custom.data['summary']['total_orders'], 1)
