# Inventory Management API

A modular inventory and business operations backend built with Django, Django REST Framework, Knox token authentication, and DRF Spectacular.

This project centralizes product catalog management, suppliers, customers, sales, purchases, dues, inventory control, and reporting behind a documented REST API.

## What It Covers

- Authentication and user activity tracking
- Product catalog, variants, and stock movements
- Supplier management, supplier products, payments, CSV import/export
- Customer management, addresses, contacts, payments, loyalty, documents, CSV import/export
- Sales orders, quotations, returns, payments, dashboard, and reports
- Purchase orders, goods receipts, returns, payments, supplier invoices, dashboard, and reports
- Customer and supplier dues, collections, disbursements, reminders, and write-offs
- Warehouses, stock, batches, serial numbers, transfers, adjustments, cycle counts, and reorder requests
- Operational and financial reporting with saved reports and dashboard widgets
- OpenAPI schema with Swagger UI and ReDoc

## Tech Stack

- Python
- Django 6
- Django REST Framework
- Django REST Knox
- DRF Spectacular
- Django Filter
- SQLite by default

## Project Structure

```text
inventory/
├── backend/
│   ├── accounts/
│   ├── products/
│   ├── suppliers/
│   ├── customers/
│   ├── sales/
│   ├── purchases/
│   ├── dues/
│   ├── inventory/
│   ├── reports/
│   ├── core/
│   ├── manage.py
│   └── requirements.txt
├── customer_documents/
└── supplier_invoices/
```

## Installed Apps

- `accounts`: registration, login, logout, profile, password change, user listing, activity logs
- `products`: categories, brands, units, products, variants, stock movements, product statistics
- `suppliers`: suppliers, supplier products, supplier payments, bulk upload, export, statistics
- `customers`: customers, addresses, contacts, interactions, payments, loyalty, documents, bulk upload, export
- `sales`: sales orders, order items, payments, returns, quotations, dashboard, reports
- `purchases`: purchase orders, goods receipts, payments, returns, supplier invoices, dashboard, reports
- `dues`: receivables, payables, collections, disbursements, reminders, write-offs, aging reports
- `inventory`: warehouses, stock, batches, serials, transfers, adjustments, cycle counts, reorder requests
- `reports`: sales, purchase, inventory, valuation, customer, dues aging, profit/loss, saved reports, widgets

## API Base Paths

- `/api/auth/`
- `/api/products/`
- `/api/suppliers/`
- `/api/customers/`
- `/api/sales/`
- `/api/purchases/`
- `/api/dues/`
- `/api/inventory/`
- `/api/reports/`

## API Documentation

After starting the server:

- Swagger UI: `/api/docs/swagger/`
- ReDoc: `/api/docs/redoc/`
- Schema: `/api/schema/`
- Shortcut redirect: `/api/docs/`

Authentication uses Knox tokens. In Swagger, authorize with:

```text
Token <your-token>
```

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r backend/requirements.txt
```

3. Apply migrations:

```bash
python backend/manage.py migrate
```

4. Start the development server:

```bash
python backend/manage.py runserver
```

## Default Development Settings

- Database: SQLite at `backend/db.sqlite3`
- Auth model: custom `accounts.User`
- Default API auth: Knox token authentication
- Default API permission: authenticated users only
- Default pagination: page number pagination with page size `10`
- Allowed CORS origins:
  - `http://localhost:3000`
  - `http://127.0.0.1:3000`

## Common Commands

Run all tests:

```bash
python backend/manage.py test
```

Run a single app test suite:

```bash
python manage.py test products
python manage.py test suppliers
python manage.py test customers
python manage.py test sales
python manage.py test purchases
python manage.py test dues
python manage.py test inventory
python manage.py test reports
python bmanage.py test accounts
python manage.py test core
```

Generate the OpenAPI schema:

```bash
python backend/manage.py spectacular --file schema.yml
```

Create a superuser:

```bash
python backend/manage.py createsuperuser
```

## Notes

- The project is currently configured for local development with `DEBUG = True`.
- Some endpoints support file uploads and generate files such as customer documents and supplier invoices.
- Swagger/ReDoc are available, but some endpoints still rely on Spectacular fallback behavior until more explicit schema annotations are added.

## Admin Panel

- Django admin: `/admin/`

## License

Add your preferred license here if this project will be distributed.
