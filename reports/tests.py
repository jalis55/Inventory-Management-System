from decimal import Decimal
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import ActivityLog, User
from customers.models import Customer
from dues.models import CustomerDue, SupplierDue
from inventory.models import Batch, Stock, Warehouse
from products.models import Brand, Category, Product, StockMovement, Unit
from purchases.models import PurchaseOrder, PurchaseOrderItem, PurchasePayment
from reports.models import DashboardWidget, ReportGeneration, SavedReport
from sales.models import SalesOrder, SalesOrderItem, SalesPayment
from suppliers.models import Supplier


class ReportsEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='reports-user',
            email='reports@example.com',
            password='StrongPass123!',
            first_name='Report',
            last_name='Manager',
        )
        self.client.force_authenticate(user=self.user)

        self.category = Category.objects.create(name='Electronics')
        self.brand = Brand.objects.create(name='Acme')
        self.unit = Unit.objects.create(name='Piece', abbreviation='pc')
        self.product = Product.objects.create(
            sku='REP-1000',
            barcode='REP-BAR-1000',
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
            current_stock=20,
            minimum_stock=2,
            maximum_stock=60,
            reorder_point=5,
            created_by=self.user,
        )

        self.customer = Customer.objects.create(
            customer_code='CUST-REP-10001',
            customer_type='retail',
            company_name='Northwind Retail',
            first_name='Alice',
            last_name='Buyer',
            email='alice.reports@example.com',
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
            outstanding_amount=Decimal('210.00'),
            payment_terms='net_30',
            preferred_communication='email',
            loyalty_points=25,
            loyalty_tier='silver',
            created_by=self.user,
        )
        self.supplier = Supplier.objects.create(
            company_name='Northwind Supplies',
            contact_person='Bob Supplier',
            email='supplier.reports@example.com',
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
            outstanding_amount=Decimal('110.00'),
            bank_name='Bank',
            bank_account='123456',
            bank_ifsc='BANK0001',
            created_by=self.user,
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-REP-1',
            name='Reports Warehouse',
            type='main',
            address_line1='42 Market Street',
            city='Dhaka',
            state='Dhaka',
            postal_code='1207',
            country='Bangladesh',
            created_by=self.user,
        )
        self.stock = Stock.objects.create(
            warehouse=self.warehouse,
            product=self.product,
            quantity=20,
            reserved_quantity=2,
            reorder_point=5,
            bin_location='A1',
        )
        self.batch = Batch.objects.create(
            batch_number='REP-BATCH-1',
            product=self.product,
            manufacturing_date=timezone.now().date() - timedelta(days=30),
            expiry_date=timezone.now().date() + timedelta(days=20),
            initial_quantity=20,
            current_quantity=8,
            warehouse=self.warehouse,
            bin_location='A1',
            cost_price=Decimal('80.00'),
            selling_price=Decimal('120.00'),
        )
        self.stock_movement = StockMovement.objects.create(
            product=self.product,
            movement_type='purchase',
            quantity=10,
            previous_quantity=10,
            new_quantity=20,
            reference_type='seed',
            notes='Seed movement',
            created_by=self.user,
        )

        self.sales_order = self.create_sales_order()
        self.purchase_order = self.create_purchase_order()
        self.customer_due = CustomerDue.objects.update_or_create(
            sales_order=self.sales_order,
            defaults={
                'customer': self.customer,
                'due_date': timezone.now().date() - timedelta(days=15),
                'original_amount': Decimal('210.00'),
                'paid_amount': Decimal('0.00'),
                'remaining_amount': Decimal('210.00'),
                'created_by': self.user,
            },
        )[0]
        self.supplier_due = SupplierDue.objects.update_or_create(
            purchase_order=self.purchase_order,
            defaults={
                'supplier': self.supplier,
                'due_date': timezone.now().date() - timedelta(days=40),
                'original_amount': Decimal('110.00'),
                'paid_amount': Decimal('0.00'),
                'remaining_amount': Decimal('110.00'),
                'created_by': self.user,
            },
        )[0]

    def create_sales_order(self):
        order = SalesOrder.objects.create(
            customer=self.customer,
            sales_person=self.user,
            expected_delivery_date=timezone.now().date(),
            shipping_address='42 Market Street',
            billing_address='42 Market Street',
            payment_method='cash',
            payment_terms='Net 30',
            order_status='delivered',
            payment_status='partial',
            created_by=self.user,
        )
        item = SalesOrderItem.objects.create(
            sales_order=order,
            product=self.product,
            quantity=2,
            unit_price=Decimal('100.00'),
            discount_percent=Decimal('0.00'),
            tax_rate=Decimal('5.00'),
        )
        order.subtotal = item.subtotal
        order.tax_amount = item.tax_amount
        order.total_amount = item.total
        order.paid_amount = Decimal('0.00')
        order.due_amount = item.total
        order.save()
        SalesPayment.objects.create(
            sales_order=order,
            amount=Decimal('50.00'),
            payment_method='cash',
            status='completed',
            reference_number='RPT-SALE-PAY',
            received_by=self.user,
        )
        return order

    def create_purchase_order(self):
        order = PurchaseOrder.objects.create(
            supplier=self.supplier,
            requested_by=self.user,
            expected_delivery_date=timezone.now().date(),
            payment_terms='Net 30',
            order_status='received',
            payment_status='partial',
            created_by=self.user,
        )
        item = PurchaseOrderItem.objects.create(
            purchase_order=order,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100.00'),
            discount_percent=Decimal('0.00'),
            tax_rate=Decimal('10.00'),
        )
        order.subtotal = item.subtotal
        order.tax_amount = item.tax_amount
        order.total_amount = item.total
        order.paid_amount = Decimal('0.00')
        order.due_amount = item.total
        order.save()
        PurchasePayment.objects.create(
            purchase_order=order,
            amount=Decimal('25.00'),
            payment_method='cash',
            status='completed',
            reference_number='RPT-PUR-PAY',
            paid_by=self.user,
        )
        return order

    def date_range(self):
        today = timezone.now().date().isoformat()
        return {'start_date': today, 'end_date': today}

    def test_reports_endpoints_require_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(
            reverse('report-sales'),
            {'date_range': self.date_range(), 'group_by': 'day'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_sales_and_purchase_report_endpoints(self):
        sales_response = self.client.post(
            reverse('report-sales'),
            {
                'date_range': self.date_range(),
                'group_by': 'day',
                'customer_id': str(self.customer.id),
                'product_id': str(self.product.id),
                'category_id': str(self.category.id),
                'sales_person_id': str(self.user.id),
            },
            format='json',
        )
        purchase_response = self.client.post(
            reverse('report-purchases'),
            {
                'date_range': self.date_range(),
                'group_by': 'month',
                'supplier_id': str(self.supplier.id),
                'product_id': str(self.product.id),
                'category_id': str(self.category.id),
                'order_status': ['received'],
            },
            format='json',
        )
        trend_response = self.client.get(reverse('report-sales-trend'))

        self.assertEqual(sales_response.status_code, status.HTTP_200_OK)
        self.assertEqual(sales_response.data['summary']['total_orders'], 1)
        self.assertEqual(str(sales_response.data['summary']['total_revenue']), '210')
        self.assertEqual(sales_response.data['top_products'][0]['product__sku'], 'REP-1000')
        self.assertEqual(sales_response.data['payment_methods'][0]['payment_method'], 'cash')
        self.assertTrue(ActivityLog.objects.filter(action='REPORT_GENERATED', details__report_type='sales').exists())

        self.assertEqual(purchase_response.status_code, status.HTTP_200_OK)
        self.assertEqual(purchase_response.data['summary']['total_orders'], 1)
        self.assertEqual(str(purchase_response.data['summary']['total_spent']), '110')
        self.assertEqual(purchase_response.data['top_suppliers'][0]['supplier__company_name'], 'Northwind Supplies')

        self.assertEqual(trend_response.status_code, status.HTTP_200_OK)
        self.assertIn('comparison', trend_response.data)
        self.assertIn('monthly_trend', trend_response.data)

    def test_inventory_reports_endpoints(self):
        inventory_response = self.client.post(
            reverse('report-inventory'),
            {
                'warehouse_id': str(self.warehouse.id),
                'category_id': str(self.category.id),
                'include_zero_stock': False,
                'low_stock_only': False,
                'expiring_only': True,
                'expiry_days': 30,
            },
            format='json',
        )
        valuation_response = self.client.get(reverse('report-inventory-valuation'))

        self.assertEqual(inventory_response.status_code, status.HTTP_200_OK)
        self.assertEqual(inventory_response.data['summary']['total_items'], 1)
        self.assertEqual(str(inventory_response.data['summary']['total_value']), '1600')
        self.assertEqual(len(inventory_response.data['expiring_batches']), 1)
        self.assertEqual(inventory_response.data['warehouse_breakdown'][0]['warehouse__code'], 'WH-REP-1')

        self.assertEqual(valuation_response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(valuation_response.data['total_cost_value']), '1600.00')
        self.assertEqual(valuation_response.data['items'][0]['sku'], 'REP-1000')

    def test_customer_and_financial_report_endpoints(self):
        customer_response = self.client.post(
            reverse('report-customers'),
            {
                'date_range': self.date_range(),
                'customer_type': 'retail',
                'loyalty_tier': 'silver',
                'top_n': 5,
                'sort_by': 'outstanding',
            },
            format='json',
        )
        profit_loss_response = self.client.post(
            reverse('report-profit-loss'),
            {
                'date_range': self.date_range(),
                'report_type': 'profit_loss',
                'include_tax': True,
            },
            format='json',
        )
        dues_response = self.client.post(
            reverse('report-dues-aging'),
            {
                'as_of_date': timezone.now().date().isoformat(),
                'type': 'both',
                'aging_buckets': [0, 30, 60, 90],
            },
            format='json',
        )

        self.assertEqual(customer_response.status_code, status.HTTP_200_OK)
        self.assertEqual(customer_response.data['summary']['total_customers'], 1)
        self.assertEqual(customer_response.data['top_customers'][0]['email'], 'alice.reports@example.com')

        self.assertEqual(profit_loss_response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(profit_loss_response.data['income']['total_revenue']), '210')
        self.assertEqual(str(profit_loss_response.data['cogs']), '160.00')
        self.assertIn('monthly_breakdown', profit_loss_response.data)

        self.assertEqual(dues_response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(dues_response.data['receivables']['total']), '210.00')
        self.assertEqual(str(dues_response.data['payables']['total']), '110.00')

    def test_dashboard_widget_and_dashboard_data_endpoints(self):
        create_response = self.client.post(
            reverse('dashboard-widgets'),
            {
                'name': 'Today Sales',
                'widget_type': 'metric',
                'chart_type': None,
                'data_source': 'sales.today',
                'query_params': {},
                'color': '#3B82F6',
                'size': 'medium',
                'position_x': 0,
                'position_y': 0,
                'refresh_interval': 300,
                'is_active': True,
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        widget = DashboardWidget.objects.get(name='Today Sales')

        list_response = self.client.get(reverse('dashboard-widgets'))
        detail_response = self.client.patch(
            reverse('dashboard-widget-detail', kwargs={'id': widget.id}),
            {'position_x': 1},
            format='json',
        )
        data_response = self.client.get(reverse('dashboard-data'))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        widget.refresh_from_db()
        self.assertEqual(widget.position_x, 1)
        self.assertEqual(data_response.status_code, status.HTTP_200_OK)
        self.assertEqual(data_response.data[0]['name'], 'Today Sales')
        self.assertEqual(data_response.data[0]['data']['label'], "Today's Sales")

    def test_saved_report_generate_and_history_endpoints(self):
        saved_report = SavedReport.objects.create(
            name='Inventory Snapshot',
            report_type='inventory',
            description='Daily inventory',
            config={'warehouse_id': str(self.warehouse.id)},
            default_format='json',
            created_by=self.user,
        )

        list_response = self.client.get(reverse('saved-reports'))
        update_response = self.client.patch(
            reverse('saved-report-detail', kwargs={'id': saved_report.id}),
            {'description': 'Updated description'},
            format='json',
        )
        generate_response = self.client.post(
            reverse('generate-saved-report', kwargs={'id': saved_report.id}),
            {'format': 'json'},
            format='json',
        )
        history_response = self.client.get(reverse('report-history'))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        saved_report.refresh_from_db()
        self.assertEqual(saved_report.description, 'Updated description')
        self.assertEqual(generate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(generate_response['Content-Type'], 'application/json')
        self.assertTrue(ReportGeneration.objects.filter(saved_report=saved_report, status='completed').exists())
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertEqual(history_response.data['count'], 1)

    def test_dashboard_widget_delete_endpoint(self):
        widget = DashboardWidget.objects.create(
            user=self.user,
            name='Low Stock',
            widget_type='metric',
            data_source='inventory.low_stock',
            color='#F59E0B',
            size='small',
            position_x=0,
            position_y=0,
        )

        response = self.client.delete(reverse('dashboard-widget-detail', kwargs={'id': widget.id}))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DashboardWidget.objects.filter(id=widget.id).exists())
