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

# Modelo para marcas de productos (ej: Bosch, Makita)
class Brand(models.Model):
    name = models.CharField(max_length=50, unique=True)  # Nombre único de la marca

    def __str__(self):
        return self.name

# Modelo para productos
class Product(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='products')
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
            self.code = f"FER-{self.id or Product.objects.count() + 1:05d}"
        if not self.slug:  # [NUEVO] Generar slug si no existe
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
        PriceHistory.objects.create(product=self, price=self.price)

# [CAMBIO] Nuevo modelo para historial de precios
class PriceHistory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_history')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} - {self.price} at {self.created_at}"

# Modelo para el perfil de usuario con integración de Stripe
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)  # Relación uno a uno con usuario
    stripe_customer_id = models.CharField(max_length=50, blank=True, null=True)  # ID de cliente en Stripe
    one_click_purchasing = models.BooleanField(default=False)  # Opción de compra rápida

    def __str__(self):
        return self.user.username

# Modelo para direcciones de envío/facturación
class Address(models.Model):
    ADDRESS_TYPES = (
        ('B', 'Facturación'),
        ('S', 'Envío'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')  # Relación con usuario
    street_address = models.CharField(max_length=100)  # Dirección principal
    apartment_address = models.CharField(max_length=100, blank=True, null=True)  # Dirección secundaria
    country = CountryField()  # País (usando django-countries)
    zip_code = models.CharField(max_length=20)  # Código postal
    address_type = models.CharField(max_length=1, choices=ADDRESS_TYPES)  # Tipo de dirección
    default = models.BooleanField(default=False)  # Dirección predeterminada

    def __str__(self):
        return f"{self.user.username} - {self.address_type}"

    class Meta:
        verbose_name_plural = 'Addresses'

# Modelo para el carrito de compras
class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carts')  # Relación con usuario
    created_at = models.DateTimeField(default=timezone.now)  # Fecha de creación
    updated_at = models.DateTimeField(auto_now=True)  # Fecha de actualización

    def __str__(self):
        return f"Cart {self.id} - {self.user.username}"

# Modelo para ítems del carrito
class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')  # Relación con carrito
    product = models.ForeignKey(Product, on_delete=models.CASCADE)  # Relación con producto
    quantity = models.PositiveIntegerField(default=1)  # Cantidad de ítems
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Precio unitario al momento de añadir

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    def get_total_price(self):
        return self.quantity * self.price  # Calcula precio total del ítem

# Modelo para pedidos
class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('prepared', 'Preparado'),
        ('delivered', 'Entregado'),
    )
    DELIVERY_CHOICES = (
        ('store', 'Retiro en tienda'),
        ('home', 'Despacho a domicilio'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')  # Relación con usuario
    ref_code = models.CharField(max_length=20, unique=True, blank=True, null=True)  # Código de referencia único
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')  # Estado del pedido
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_CHOICES)  # Método de entrega
    shipping_address = models.ForeignKey(Address, related_name='shipping_orders', on_delete=models.SET_NULL, blank=True, null=True)  # Dirección de envío
    billing_address = models.ForeignKey(Address, related_name='billing_orders', on_delete=models.SET_NULL, blank=True, null=True)  # Dirección de facturación
    created_at = models.DateTimeField(auto_now_add=True)  # Fecha de creación
    updated_at = models.DateTimeField(auto_now=True)  # Fecha de actualización
    coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, blank=True, null=True)  # Cupón aplicado

    def __str__(self):
        return f"Order {self.ref_code} - {self.user.username}"

    def get_total(self):
        total = sum(item.get_total_price() for item in self.items.all())
        if self.coupon:
            total -= self.coupon.amount
        return max(total, 0)  # Asegura que el total no sea negativo

# Modelo para ítems de pedido
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')  # Relación con pedido
    product = models.ForeignKey(Product, on_delete=models.CASCADE)  # Relación con producto
    quantity = models.PositiveIntegerField(default=1)  # Cantidad
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Precio unitario al momento de la compra

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    def get_total_price(self):
        return self.quantity * self.price  # Calcula precio total del ítem

# Modelo para pagos
class Payment(models.Model):
    PAYMENT_METHODS = (
        ('debit', 'Débito'),
        ('credit', 'Crédito'),
        ('transfer', 'Transferencia'),
    )
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')  # Relación con pedido
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Monto del pago
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS)  # Método de pago
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, null=True)  # ID de transacción de Stripe
    confirmed = models.BooleanField(default=False)  # Estado de confirmación
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)  # Contador que confirma
    created_at = models.DateTimeField(auto_now_add=True)  # Fecha de creación

    def __str__(self):
        return f"Payment for Order {self.order.ref_code}"

# Modelo para cupones de descuento
class Coupon(models.Model):
    code = models.CharField(max_length=15, unique=True)  # Código único del cupón
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Monto del descuento
    valid_from = models.DateTimeField()  # Fecha de inicio de validez
    valid_to = models.DateTimeField()  # Fecha de fin de validez
    active = models.BooleanField(default=True)  # Estado del cupón

    def __str__(self):
        return self.code

# Modelo para reembolsos
class Refund(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='refunds')  # Relación con pedido
    reason = models.TextField()  # Motivo del reembolso
    accepted = models.BooleanField(default=False)  # Estado de aprobación
    created_at = models.DateTimeField(auto_now_add=True)  # Fecha de solicitud

    def __str__(self):
        return f"Refund for Order {self.order.ref_code}"

# Modelo para empleados
class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee')  # Relación con usuario
    rut = models.CharField(max_length=12, unique=True)  # RUT único
    first_name = models.CharField(max_length=50)  # Nombre
    last_name = models.CharField(max_length=50)  # Apellido paterno
    mother_last_name = models.CharField(max_length=50, blank=True, null=True)  # Apellido materno
    role = models.CharField(max_length=15, choices=(('admin', 'Administrador'), ('seller', 'Vendedor'), ('warehouse', 'Bodeguero'), ('accountant', 'Contador')))  # Rol del empleado
    created_at = models.DateTimeField(auto_now_add=True)  # Fecha de creación

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.role})"

# Signal para crear UserProfile automáticamente al crear un usuario
def userprofile_receiver(sender, instance, created, *args, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

post_save.connect(userprofile_receiver, sender=settings.AUTH_USER_MODEL)