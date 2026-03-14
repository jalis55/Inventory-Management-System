from django.contrib import admin
from .models import Category, Product,Brand,Unit,ProductVariant,StockMovement

# Register your models here.
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Brand)
admin.site.register(Unit)
admin.site.register(ProductVariant)
admin.site.register(StockMovement)