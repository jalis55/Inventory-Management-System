from decimal import Decimal
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import ActivityLog, User
from products.models import Brand, Category, Product, StockMovement, Unit
from suppliers.models import Supplier, SupplierProduct

from .models import (
    Batch,
    CycleCount,
    ReorderRequest,
    SerialNumber,
    Stock,
    StockAdjustment,
    StockTransfer,
    Warehouse,
)


class InventoryEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='inventory-user',
            email='inventory@example.com',
            password='StrongPass123!',
            first_name='Inventory',
            last_name='Manager',
        )
        self.client.force_authenticate(user=self.user)

        self.category = Category.objects.create(name='Electronics')
        self.brand = Brand.objects.create(name='Acme')
        self.unit = Unit.objects.create(name='Piece', abbreviation='pc')
        self.product = Product.objects.create(
            sku='INV-1000',
            barcode='INV-BAR-1000',
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
        self.supplier = Supplier.objects.create(
            company_name='Northwind Supplies',
            contact_person='Bob Supplier',
            email='supplier.inventory@example.com',
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
        SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_sku='SUP-INV-1000',
            price=Decimal('75.00'),
            lead_time_days=7,
            minimum_order_quantity=5,
            is_preferred=True,
        )

        self.main_warehouse = Warehouse.objects.create(
            code='WH-MAIN-1',
            name='Main Warehouse',
            type='main',
            address_line1='42 Market Street',
            city='Dhaka',
            state='Dhaka',
            postal_code='1207',
            country='Bangladesh',
            created_by=self.user,
        )
        self.branch_warehouse = Warehouse.objects.create(
            code='WH-BRN-1',
            name='Branch Warehouse',
            type='branch',
            address_line1='84 Lake Road',
            city='Dhaka',
            state='Dhaka',
            postal_code='1212',
            country='Bangladesh',
            created_by=self.user,
        )

        self.stock = Stock.objects.create(
            warehouse=self.main_warehouse,
            product=self.product,
            quantity=20,
            reserved_quantity=2,
            reorder_point=5,
            bin_location='A1',
        )
        self.low_stock = Stock.objects.create(
            warehouse=self.branch_warehouse,
            product=self.product,
            quantity=4,
            reserved_quantity=0,
            reorder_point=5,
            bin_location='B1',
        )
        self.batch = Batch.objects.create(
            batch_number='BATCH-100',
            product=self.product,
            manufacturing_date=timezone.now().date() - timedelta(days=30),
            expiry_date=timezone.now().date() + timedelta(days=20),
            initial_quantity=20,
            current_quantity=8,
            warehouse=self.main_warehouse,
            bin_location='A1',
            cost_price=Decimal('80.00'),
            selling_price=Decimal('120.00'),
        )
        self.serial = SerialNumber.objects.create(
            serial_number='SER-100',
            product=self.product,
            warehouse=self.main_warehouse,
            batch=self.batch,
            status='available',
        )
        self.movement = StockMovement.objects.create(
            product=self.product,
            movement_type='purchase',
            quantity=10,
            previous_quantity=10,
            new_quantity=20,
            reference_type='seed',
            notes='Seed movement',
            created_by=self.user,
        )

    def warehouse_payload(self, **overrides):
        payload = {
            'name': 'Overflow Warehouse',
            'type': 'store',
            'address_line1': '12 Warehouse Road',
            'address_line2': '',
            'city': 'Dhaka',
            'state': 'Dhaka',
            'postal_code': '1216',
            'country': 'Bangladesh',
            'contact_person': 'Store Manager',
            'phone': '01800000000',
            'email': 'overflow@example.com',
            'total_capacity': '1000.00',
            'used_capacity': '100.00',
            'is_active': True,
            'is_refrigerated': False,
            'notes': 'Overflow storage',
        }
        payload.update(overrides)
        return payload

    def test_inventory_endpoints_require_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse('inventory-dashboard'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_warehouse_crud_and_stock_guard(self):
        create_response = self.client.post(reverse('warehouse-list'), self.warehouse_payload(), format='json')

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        warehouse = Warehouse.objects.get(name='Overflow Warehouse')
        self.assertTrue(warehouse.code.startswith('WH-OVE-'))
        self.assertTrue(ActivityLog.objects.filter(action='WAREHOUSE_CREATED').exists())

        list_response = self.client.get(reverse('warehouse-list'), {'search': 'Overflow'})
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)

        detail_url = reverse('warehouse-detail', kwargs={'id': warehouse.id})
        update_response = self.client.patch(detail_url, {'city': 'Chattogram'}, format='json')

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        warehouse.refresh_from_db()
        self.assertEqual(warehouse.city, 'Chattogram')
        self.assertTrue(ActivityLog.objects.filter(action='WAREHOUSE_UPDATED').exists())

        blocked_delete = self.client.delete(reverse('warehouse-detail', kwargs={'id': self.main_warehouse.id}))
        self.assertEqual(blocked_delete.status_code, status.HTTP_400_BAD_REQUEST)

        empty_warehouse = Warehouse.objects.create(
            code='WH-EMPTY-1',
            name='Empty Warehouse',
            type='store',
            address_line1='1 Empty Street',
            city='Dhaka',
            state='Dhaka',
            postal_code='1200',
            country='Bangladesh',
            created_by=self.user,
        )
        delete_response = self.client.delete(reverse('warehouse-detail', kwargs={'id': empty_warehouse.id}))

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Warehouse.objects.filter(id=empty_warehouse.id).exists())
        self.assertTrue(ActivityLog.objects.filter(action='WAREHOUSE_DELETED').exists())

    def test_stock_batch_and_serial_endpoints(self):
        stock_list = self.client.get(reverse('stock-list'), {'warehouse': str(self.main_warehouse.id)})
        stock_detail = self.client.get(reverse('stock-detail', kwargs={'id': self.stock.id}))
        warehouse_stock = self.client.get(reverse('warehouse-stock', kwargs={'warehouse_id': self.main_warehouse.id}))
        low_stock = self.client.get(reverse('low-stock'))

        self.assertEqual(stock_list.status_code, status.HTTP_200_OK)
        self.assertEqual(stock_list.data['count'], 1)
        self.assertEqual(stock_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(stock_detail.data['warehouse_name'], 'Main Warehouse')
        self.assertEqual(warehouse_stock.status_code, status.HTTP_200_OK)
        self.assertEqual(warehouse_stock.data['count'], 1)
        self.assertEqual(low_stock.status_code, status.HTTP_200_OK)
        self.assertEqual(low_stock.data['count'], 1)

        batch_list = self.client.get(reverse('batch-list'), {'product': str(self.product.id)})
        expiring_batches = self.client.get(reverse('expiring-batches'))

        self.assertEqual(batch_list.status_code, status.HTTP_200_OK)
        self.assertEqual(batch_list.data['count'], 1)
        self.assertEqual(expiring_batches.status_code, status.HTTP_200_OK)
        self.assertEqual(expiring_batches.data['count'], 1)

        serial_create = self.client.post(
            reverse('serial-list'),
            {
                'serial_number': 'SER-101',
                'product': str(self.product.id),
                'warehouse': str(self.main_warehouse.id),
                'batch': str(self.batch.id),
                'status': 'available',
            },
            format='json',
        )
        serial_detail = self.client.get(reverse('serial-detail', kwargs={'id': self.serial.id}))

        self.assertEqual(serial_create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(serial_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(serial_detail.data['serial_number'], 'SER-100')

    def test_stock_transfer_flow_updates_warehouses(self):
        create_response = self.client.post(
            reverse('transfer-list'),
            {
                'from_warehouse': str(self.main_warehouse.id),
                'to_warehouse': str(self.branch_warehouse.id),
                'expected_delivery': (timezone.now().date() + timedelta(days=2)).isoformat(),
                'reference_number': 'TRF-REF-1',
                'vehicle_number': 'DHAKA-123',
                'driver_name': 'Driver One',
                'driver_phone': '01800000000',
                'notes': 'Move stock',
                'items': [
                    {
                        'product': str(self.product.id),
                        'variant': None,
                        'quantity': 3,
                    }
                ],
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        transfer = StockTransfer.objects.get(reference_number='TRF-REF-1')
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.reserved_quantity, 5)
        self.assertTrue(ActivityLog.objects.filter(action='STOCK_TRANSFER_CREATED').exists())

        approve_response = self.client.post(
            reverse('transfer-status', kwargs={'id': transfer.id}),
            {'action': 'approve', 'status': 'approved'},
            format='json',
        )
        complete_response = self.client.post(
            reverse('transfer-status', kwargs={'id': transfer.id}),
            {'action': 'complete', 'status': 'completed'},
            format='json',
        )

        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        transfer.refresh_from_db()
        self.stock.refresh_from_db()
        self.low_stock.refresh_from_db()
        self.assertEqual(transfer.status, 'completed')
        self.assertEqual(self.stock.quantity, 17)
        self.assertEqual(self.stock.reserved_quantity, 2)
        self.assertEqual(self.low_stock.quantity, 7)
        self.assertEqual(
            StockMovement.objects.filter(reference_id=transfer.id, reference_type='stock_transfer_out').count(),
            1,
        )
        self.assertEqual(
            StockMovement.objects.filter(reference_id=transfer.id, reference_type='stock_transfer_in').count(),
            1,
        )

    def test_stock_adjustment_create_and_approve(self):
        response = self.client.post(
            reverse('adjustment-list'),
            {
                'warehouse': str(self.main_warehouse.id),
                'adjustment_type': 'cycle_count',
                'reason': 'Monthly recount',
                'items': [
                    {
                        'product': str(self.product.id),
                        'variant': None,
                        'expected_quantity': 20,
                        'counted_quantity': 18,
                        'reason': 'Damaged units',
                    }
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        adjustment = StockAdjustment.objects.get(reason='Monthly recount')
        self.assertEqual(str(adjustment.total_cost_impact), '-160.00')
        self.assertTrue(ActivityLog.objects.filter(action='STOCK_ADJUSTMENT_CREATED').exists())

        approve_response = self.client.post(
            reverse('adjustment-approve', kwargs={'id': adjustment.id}),
            {'action': 'approve'},
            format='json',
        )

        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        adjustment.refresh_from_db()
        self.stock.refresh_from_db()
        self.assertEqual(adjustment.status, 'approved')
        self.assertEqual(self.stock.quantity, 18)
        self.assertTrue(StockMovement.objects.filter(reference_id=adjustment.id, movement_type='adjustment').exists())

    def test_cycle_count_flow_and_verification(self):
        create_response = self.client.post(
            reverse('cycle-count-list'),
            {
                'warehouse': str(self.main_warehouse.id),
                'scheduled_date': timezone.now().date().isoformat(),
                'zone': 'Zone A',
                'category': 'Electronics',
                'notes': 'Monthly count',
                'items': [
                    {
                        'product': str(self.product.id),
                        'variant': None,
                        'bin_location': 'A1',
                    }
                ],
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        cycle_count = CycleCount.objects.get(zone='Zone A')
        self.assertEqual(cycle_count.total_items, 1)
        self.assertTrue(ActivityLog.objects.filter(action='CYCLE_COUNT_CREATED').exists())

        start_response = self.client.post(reverse('cycle-count-start', kwargs={'id': cycle_count.id}), format='json')
        item = cycle_count.items.first()
        update_response = self.client.post(
            reverse('cycle-count-update', kwargs={'id': cycle_count.id}),
            {
                'item_id': str(item.id),
                'counted_quantity': 19,
                'bin_location': 'A1',
                'notes': 'One unit missing',
            },
            format='json',
        )
        complete_response = self.client.post(
            reverse('cycle-count-complete', kwargs={'id': cycle_count.id}),
            {'action': 'verify'},
            format='json',
        )

        self.assertEqual(start_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        cycle_count.refresh_from_db()
        self.stock.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(cycle_count.status, 'verified')
        self.assertEqual(cycle_count.items_discrepancy, 1)
        self.assertTrue(item.is_verified)
        self.assertEqual(self.stock.quantity, 19)
        self.assertTrue(StockMovement.objects.filter(reference_id=cycle_count.id, movement_type='cycle_count').exists())

    def test_reorder_generation_and_dashboard(self):
        response = self.client.post(
            reverse('reorder-generate'),
            {'warehouse_id': str(self.branch_warehouse.id)},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        reorder = ReorderRequest.objects.get(warehouse=self.branch_warehouse, product=self.product)
        self.assertEqual(reorder.priority, 'medium')
        self.assertEqual(reorder.suggested_quantity, 6)
        self.assertEqual(reorder.suggested_supplier, self.supplier)

        dashboard_response = self.client.get(reverse('inventory-dashboard'))

        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(dashboard_response.data['summary']['total_inventory_value']), '1920')
        self.assertEqual(dashboard_response.data['summary']['total_products_in_stock'], 2)
        self.assertEqual(dashboard_response.data['summary']['low_stock_items'], 1)
        self.assertEqual(dashboard_response.data['summary']['expiring_batches'], 1)
        self.assertEqual(len(dashboard_response.data['warehouse_stats']), 2)
        self.assertEqual(dashboard_response.data['top_products_by_value'][0]['product__sku'], 'INV-1000')
        self.assertGreaterEqual(len(dashboard_response.data['recent_movements']), 1)
