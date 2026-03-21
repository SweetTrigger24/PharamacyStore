from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Customer, Cart


@receiver(post_save, sender=Customer)
def ensure_customer_has_cart(sender, instance, created, **kwargs):
    Cart.objects.get_or_create(customer=instance)