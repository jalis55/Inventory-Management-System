from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

admin.site.site_header = "Inventario Admin"
admin.site.site_title = "Inventario Admin Portal"
admin.site.index_title = "Welcome to inventario Portal"




urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/products/', include('products.urls')),
    path('api/suppliers/', include('suppliers.urls')),
    path('api/customers/', include('customers.urls')),
    path('api/sales/', include('sales.urls')),
    path('api/purchases/', include('purchases.urls')),
    path('api/dues/', include('dues.urls')),
    path('api/inventory/',include('inventory.urls')),
    # OpenAPI Schema
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', RedirectView.as_view(pattern_name='swagger-ui', permanent=False), name='api-docs'),
    path('api/docs/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/schema/swagger-ui/', RedirectView.as_view(pattern_name='swagger-ui', permanent=False)),
    path('api/schema/redoc/', RedirectView.as_view(pattern_name='redoc', permanent=False)),
    path('api/reports/', include('reports.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
