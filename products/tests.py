from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import ActivityLog, User
from .models import Brand, Category, Product, ProductVariant, StockMovement, Unit


class ProductsEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='inventory-admin',
            email='inventory@example.com',
            password='StrongPass123!',
            first_name='Inventory',
            last_name='Admin',
        )
        self.client.force_authenticate(user=self.user)

        self.category = Category.objects.create(name='Electronics', description='Devices and gadgets')
        self.brand = Brand.objects.create(name='Acme', description='Trusted brand')
        self.unit = Unit.objects.create(name='Piece', abbreviation='pc')

    def product_payload(self, **overrides):
        payload = {
            'sku': 'SKU-1000',
            'barcode': 'BAR-1000',
            'name': 'Desk Lamp',
            'description': 'Adjustable LED desk lamp',
            'category': str(self.category.id),
            'brand': str(self.brand.id),
            'unit': str(self.unit.id),
            'cost_price': '50.00',
            'selling_price': '75.00',
            'wholesale_price': '65.00',
            'mrp': '80.00',
            'tax_rate': '5.00',
            'current_stock': 8,
            'minimum_stock': 2,
            'maximum_stock': 25,
            'reorder_point': 4,
            'gallery': ['lamp-front.jpg'],
            'is_active': True,
            'is_featured': True,
            'is_discounted': False,
            'discount_percent': '0.00',
            'tags': ['lighting', 'desk'],
            'attributes': {'color': 'black'},
        }
        payload.update(overrides)
        return payload

    def create_product(self, **overrides):
        data = self.product_payload(**overrides)
        category = data['category']
        brand = data['brand']
        unit = data['unit']

        if not isinstance(category, Category):
            category = Category.objects.get(id=category)
        if brand and not isinstance(brand, Brand):
            brand = Brand.objects.get(id=brand)
        if not isinstance(unit, Unit):
            unit = Unit.objects.get(id=unit)

        return Product.objects.create(
            sku=data['sku'],
            barcode=data['barcode'],
            name=data['name'],
            description=data['description'],
            category=category,
            brand=brand,
            unit=unit,
            cost_price=data['cost_price'],
            selling_price=data['selling_price'],
            wholesale_price=data['wholesale_price'],
            mrp=data['mrp'],
            tax_rate=data['tax_rate'],
            current_stock=data['current_stock'],
            minimum_stock=data['minimum_stock'],
            maximum_stock=data['maximum_stock'],
            reorder_point=data['reorder_point'],
            gallery=data['gallery'],
            is_active=data['is_active'],
            is_featured=data['is_featured'],
            is_discounted=data['is_discounted'],
            discount_percent=data['discount_percent'],
            tags=data['tags'],
            attributes=data['attributes'],
            created_by=self.user,
        )

    def test_endpoints_require_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse('product-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_category_crud_endpoints(self):
        list_url = reverse('category-list')

        create_response = self.client.post(
            list_url,
            {'name': 'Accessories', 'description': 'Optional add-ons', 'parent': str(self.category.id)},
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        created_id = create_response.data['id']
        self.assertTrue(
            ActivityLog.objects.filter(action='CATEGORY_CREATED', details__category_name='Accessories').exists()
        )

        list_response = self.client.get(list_url, {'search': 'Access'})

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)
        self.assertEqual(list_response.data['results'][0]['name'], 'Accessories')

        detail_url = reverse('category-detail', kwargs={'id': created_id})
        detail_response = self.client.get(detail_url)

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(detail_response.data['parent']), str(self.category.id))

        update_response = self.client.patch(detail_url, {'description': 'Updated description'}, format='json')

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertTrue(ActivityLog.objects.filter(action='CATEGORY_UPDATED').exists())

        delete_response = self.client.delete(detail_url)

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(ActivityLog.objects.filter(action='CATEGORY_DELETED').exists())

    def test_brand_crud_endpoints(self):
        list_url = reverse('brand-list')

        create_response = self.client.post(
            list_url,
            {'name': 'Northwind', 'description': 'Premium vendor', 'website': 'https://example.com'},
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        brand_id = create_response.data['id']
        self.assertTrue(ActivityLog.objects.filter(action='BRAND_CREATED').exists())

        list_response = self.client.get(list_url, {'ordering': '-name'})

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(list_response.data['count'], 2)

        detail_url = reverse('brand-detail', kwargs={'id': brand_id})
        detail_response = self.client.patch(detail_url, {'description': 'Updated vendor'}, format='json')

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['description'], 'Updated vendor')

        delete_response = self.client.delete(detail_url)

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Brand.objects.filter(id=brand_id).exists())

    def test_unit_crud_endpoints(self):
        list_url = reverse('unit-list')

        create_response = self.client.post(
            list_url,
            {'name': 'Box', 'abbreviation': 'bx', 'description': 'Sold in boxes'},
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        unit_id = create_response.data['id']

        list_response = self.client.get(list_url, {'search': 'Box'})

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)

        detail_url = reverse('unit-detail', kwargs={'id': unit_id})
        update_response = self.client.patch(detail_url, {'description': 'Updated unit'}, format='json')

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['description'], 'Updated unit')

        delete_response = self.client.delete(detail_url)

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Unit.objects.filter(id=unit_id).exists())

    def test_product_crud_filters_and_initial_stock_movement(self):
        second_category = Category.objects.create(name='Furniture')
        self.create_product(
            sku='SKU-2000',
            barcode='BAR-2000',
            name='Office Chair',
            category=str(second_category.id),
            current_stock=0,
            reorder_point=2,
            selling_price='120.00',
            cost_price='90.00',
            wholesale_price='100.00',
            mrp='130.00',
        )

        create_response = self.client.post(reverse('product-list'), self.product_payload(), format='json')

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        product_id = Product.objects.get(sku='SKU-1000').id

        product = Product.objects.get(id=product_id)
        initial_movement = StockMovement.objects.get(product=product, notes='Initial stock')
        self.assertEqual(product.created_by, self.user)
        self.assertEqual(initial_movement.previous_quantity, 0)
        self.assertEqual(initial_movement.new_quantity, 8)
        self.assertTrue(ActivityLog.objects.filter(action='PRODUCT_CREATED').exists())

        list_response = self.client.get(
            reverse('product-list'),
            {'category': str(self.category.id), 'in_stock': 'true', 'search': 'Lamp', 'min_price': 70},
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)
        self.assertEqual(list_response.data['results'][0]['id'], str(product_id))

        detail_url = reverse('product-detail', kwargs={'id': product_id})
        detail_response = self.client.get(detail_url)

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['category_name'], 'Electronics')
        self.assertEqual(detail_response.data['unit_name'], 'Piece')

        update_response = self.client.patch(
            detail_url,
            {'name': 'Desk Lamp Pro', 'selling_price': '85.00', 'cost_price': '50.00'},
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['name'], 'Desk Lamp Pro')
        self.assertTrue(ActivityLog.objects.filter(action='PRODUCT_UPDATED').exists())

        delete_response = self.client.delete(detail_url)

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(id=product_id).exists())
        self.assertTrue(ActivityLog.objects.filter(action='PRODUCT_DELETED').exists())

    def test_product_variant_nested_endpoints(self):
        product = self.create_product(current_stock=3)
        list_url = reverse('variant-list', kwargs={'product_id': product.id})

        create_response = self.client.post(
            list_url,
            {
                'sku': 'SKU-1000-RED',
                'name': 'Red Variant',
                'attributes': {'color': 'red'},
                'price_adjustment': '5.00',
                'cost_adjustment': '2.00',
                'stock': 6,
                'is_active': True,
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        variant_id = create_response.data['id']

        variant = ProductVariant.objects.get(id=variant_id)
        self.assertEqual(variant.product, product)
        self.assertTrue(ActivityLog.objects.filter(action='VARIANT_CREATED').exists())

        list_response = self.client.get(list_url)

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)
        self.assertEqual(list_response.data['results'][0]['name'], 'Red Variant')

        detail_url = reverse('variant-detail', kwargs={'id': variant_id})
        detail_response = self.client.patch(detail_url, {'stock': 10}, format='json')

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['stock'], 10)

        delete_response = self.client.delete(detail_url)

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProductVariant.objects.filter(id=variant_id).exists())

    def test_stock_movement_endpoints_update_product_stock(self):
        product = self.create_product(current_stock=5, sku='SKU-3000', barcode='BAR-3000', name='Router')
        list_url = reverse('stock-movement-list')

        create_response = self.client.post(
            list_url,
            {
                'product': str(product.id),
                'movement_type': 'purchase',
                'quantity': 4,
                'notes': 'Restock shipment',
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        movement = StockMovement.objects.get(id=create_response.data['id'])
        product.refresh_from_db()
        self.assertEqual(movement.previous_quantity, 5)
        self.assertEqual(movement.new_quantity, 9)
        self.assertEqual(product.current_stock, 9)
        self.assertTrue(ActivityLog.objects.filter(action='STOCK_MOVEMENT').exists())

        list_response = self.client.get(list_url, {'movement_type': 'purchase'})

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)

        product_history_response = self.client.get(
            reverse('product-stock-movements', kwargs={'product_id': product.id})
        )

        self.assertEqual(product_history_response.status_code, status.HTTP_200_OK)
        self.assertEqual(product_history_response.data['count'], 1)
        self.assertEqual(str(product_history_response.data['results'][0]['product']), str(product.id))

    def test_product_statistics_endpoint(self):
        second_category = Category.objects.create(name='Appliances')
        self.create_product(current_stock=0, sku='SKU-4000', barcode='BAR-4000', name='Toaster')
        Product.objects.create(
            sku='SKU-5000',
            barcode='BAR-5000',
            name='Fan',
            description='Cooling fan',
            category=second_category,
            brand=self.brand,
            unit=self.unit,
            cost_price='20.00',
            selling_price='30.00',
            wholesale_price='25.00',
            mrp='35.00',
            tax_rate='0.00',
            current_stock=2,
            minimum_stock=1,
            maximum_stock=10,
            reorder_point=5,
            gallery=[],
            is_active=False,
            is_featured=False,
            is_discounted=False,
            discount_percent='0.00',
            tags=[],
            attributes={},
            created_by=self.user,
        )

        response = self.client.get(reverse('product-statistics'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_products'], 2)
        self.assertEqual(response.data['active_products'], 1)
        self.assertEqual(response.data['out_of_stock'], 1)
        self.assertEqual(response.data['low_stock'], 2)

        category_stats = {item['name']: item['product_count'] for item in response.data['category_stats']}
        self.assertEqual(category_stats['Electronics'], 1)
        self.assertEqual(category_stats['Appliances'], 1)
