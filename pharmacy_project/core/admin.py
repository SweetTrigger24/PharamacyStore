from django.contrib import admin
from .models import Customer, Employee, Category, Product, Inventory, Cart, CartItem, Order, OrderItem

admin.site.register(Customer)
admin.site.register(Employee)
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Inventory)
admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(Order)
admin.site.register(OrderItem)