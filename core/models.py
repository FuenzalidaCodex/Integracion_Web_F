from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django_countries.fields import CountryField
from django.db.models.signals import post_save
from django.conf import settings
from django.utils.text import slugify

# Modelo para categorías de productos (ej: herramientas, pinturas)
class Category(models.Model):
    name = models.CharField(max_length=30, unique=True)  # Nombre único de la categoría
    description = models.TextField(blank=True, null=True)  # Descripción opcional

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'

# Modelo para marcas de productos (ej: Bosch, Makita)
class Brand(models.Model):
    name = models.CharField(max_length=50, unique=True)  # Nombre único de la marca

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Marca'
        verbose_name_plural = 'Marcas'

# Modelo para productos
class Product(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    description = models.TextField()
    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='products')
    brand = models.ForeignKey('Brand', on_delete=models.CASCADE, related_name='products')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    slug = models.SlugField(unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_final_price(self):
        return self.discount_price if self.discount_price else self.price

    def save(self, *args, **kwargs):
        if not self.code:
            # Use a temporary code if saving for the first time
            temp_code = f"FER-{Product.objects.count() + 1:05d}"
            self.code = temp_code
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
        # Update code with ID after saving
        if self.code == temp_code:
            self.code = f"FER-{self.id:05d}"
            super().save(update_fields=['code'])
        PriceHistory.objects.create(product=self, price=self.get_final_price())

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'

# Modelo para historial de precios
class PriceHistory(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='price_history')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} - {self.price} at {self.created_at}"

    class Meta:
        verbose_name = 'Historial de Precios'
        verbose_name_plural = 'Historial de Precios'

# Modelo para el perfil de usuario con integración de Stripe
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    stripe_customer_id = models.CharField(max_length=50, blank=True, null=True)
    one_click_purchasing = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username

    class Meta:
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuario'

# Modelo para direcciones de envío/facturación
class Address(models.Model):
    ADDRESS_TYPES = (
        ('B', 'Facturación'),
        ('S', 'Envío'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    street_address = models.CharField(max_length=100)
    apartment_address = models.CharField(max_length=100, blank=True, null=True)
    country = CountryField()
    zip_code = models.CharField(max_length=20)
    address_type = models.CharField(max_length=1, choices=ADDRESS_TYPES)
    default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.get_address_type_display()}"

    class Meta:
        verbose_name = 'Dirección'
        verbose_name_plural = 'Direcciones'

# Modelo para el carrito de compras
class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carts')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Carrito {self.id} - {self.user.username}"

    def get_total(self):
        return sum(item.get_total_price() for item in self.items.all())

    class Meta:
        verbose_name = 'Carrito'
        verbose_name_plural = 'Carritos'

# Modelo para ítems del carrito
class CartItem(models.Model):
    cart = models.ForeignKey('Cart', on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    def get_total_price(self):
        return self.quantity * self.price

    class Meta:
        verbose_name = 'Ítem de Carrito'
        verbose_name_plural = 'Ítems de Carrito'

# Modelo para pedidos
class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('prepared', 'Preparado'),
        ('delivered', 'Entregado'),
    )
    DELIVERY_CHOICES = (
        ('store', 'Retiro en Tienda'),
        ('home', 'Despacho a Domicilio'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    ref_code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    ordered_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_CHOICES)
    shipping_address = models.ForeignKey('Address', related_name='shipping_orders', on_delete=models.SET_NULL, blank=True, null=True)
    billing_address = models.ForeignKey('Address', related_name='billing_orders', on_delete=models.SET_NULL, blank=True, null=True)
    coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Orden {self.ref_code} - {self.user.username}"

    def get_total(self):
        total = sum(item.get_total_price() for item in self.items.all())
        if self.coupon and self.coupon.active:
            total -= self.coupon.amount
        return max(total, 0)

    def save(self, *args, **kwargs):
        if not self.ref_code:
            self.ref_code = f"ORD-{self.id or Order.objects.count() + 1:05d}"
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Orden'
        verbose_name_plural = 'Ordenes'

# Modelo para ítems de pedido
class OrderItem(models.Model):
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    def get_total_price(self):
        return self.quantity * self.price

    class Meta:
        verbose_name = 'Ítem de Orden'
        verbose_name_plural = 'Ítems de Orden'

# Modelo para pagos
class Payment(models.Model):
    PAYMENT_METHODS = (
        ('debit', 'Débito'),
        ('credit', 'Crédito'),
        ('transfer', 'Transferencia'),
    )
    order = models.OneToOneField('Order', on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    confirmed = models.BooleanField(default=False)
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='confirmed_payments')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pago para Orden {self.order.ref_code}"

    class Meta:
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'

# Modelo para cupones de descuento
class Coupon(models.Model):
    code = models.CharField(max_length=15, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = 'Cupón'
        verbose_name_plural = 'Cupones'

# Modelo para reembolsos
class Refund(models.Model):
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='refunds')
    reason = models.TextField()
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reembolso para Orden {self.order.ref_code}"

    class Meta:
        verbose_name = 'Reembolso'
        verbose_name_plural = 'Reembolsos'

# Modelo para empleados
class Employee(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Administrador'),
        ('seller', 'Vendedor'),
        ('warehouse', 'Bodeguero'),
        ('accountant', 'Contador'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee')
    rut = models.CharField(max_length=12, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    mother_last_name = models.CharField(max_length=50, blank=True, null=True)
    role = models.CharField(max_length=15, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_role_display()})"

    class Meta:
        verbose_name = 'Empleado'
        verbose_name_plural = 'Empleados'

# Signal para crear UserProfile automáticamente al crear un usuario
def userprofile_receiver(sender, instance, created, *args, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

post_save.connect(userprofile_receiver, sender=settings.AUTH_USER_MODEL)