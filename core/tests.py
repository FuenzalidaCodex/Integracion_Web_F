from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group, Permission
from rest_framework.test import APIClient
from rest_framework import status
from .models import Product, Category, Brand, Cart, CartItem, Order, OrderItem, Payment, Address, Coupon, Refund, Employee, UserProfile
from django_countries.fields import Country
import stripe
from django.conf import settings
import json

class FerremasTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.api_client = APIClient()

        # Configurar Stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # Crear usuarios y empleados para cada rol
        self.admin_user = User.objects.create_user(username='admin1', password='123456789', email='admin@ferremas.cl')
        self.admin_employee = Employee.objects.create(user=self.admin_user, rut='12345678-9', role='admin', first_name='Admin', last_name='Ferremas')
        self.seller_user = User.objects.create_user(username='seller1', password='987654321', email='seller@ferremas.cl')
        self.seller_employee = Employee.objects.create(user=self.seller_user, rut='98765432-1', role='seller', first_name='Seller', last_name='Ferremas')
        self.warehouse_user = User.objects.create_user(username='warehouse1', password='876543210', email='warehouse@ferremas.cl')
        self.warehouse_employee = Employee.objects.create(user=self.warehouse_user, rut='87654321-0', role='warehouse', first_name='Warehouse', last_name='Ferremas')
        self.accountant_user = User.objects.create_user(username='accountant1', password='765432109', email='accountant@ferremas.cl')
        self.accountant_employee = Employee.objects.create(user=self.accountant_user, rut='76543210-9', role='accountant', first_name='Accountant', last_name='Ferremas')
        self.customer_user = User.objects.create_user(username='customer1', password='password123', email='customer@ferremas.cl')

        # Crear grupos y asignar permisos
        admin_group = Group.objects.create(name='Administrador')
        admin_group.permissions.set([
            p for p in Permission.objects.all() if p.content_type.app_label in ['auth', 'core', 'admin', 'contenttypes', 'sessions']
        ])
        seller_group = Group.objects.create(name='Vendedor')
        seller_group.permissions.set([
            p for p in Permission.objects.filter(content_type__app_label='core', codename__in=[
                'add_product', 'change_product', 'delete_product', 'view_product',
                'add_order', 'change_order', 'view_order',
                'add_orderitem', 'change_orderitem', 'view_orderitem',
                'view_cart', 'view_cartitem'
            ])
        ])
        warehouse_group = Group.objects.create(name='Bodeguero')
        warehouse_group.permissions.set([
            p for p in Permission.objects.filter(content_type__app_label='core', codename__in=[
                'change_product', 'view_product',
                'change_order', 'view_order',
                'view_orderitem'
            ])
        ])
        accountant_group = Group.objects.create(name='Contador')
        accountant_group.permissions.set([
            p for p in Permission.objects.filter(content_type__app_label='core', codename__in=[
                'change_payment', 'view_payment',
                'view_order', 'view_orderitem'
            ])
        ])
        self.admin_user.groups.add(admin_group)
        self.seller_user.groups.add(seller_group)
        self.warehouse_user.groups.add(warehouse_group)
        self.accountant_user.groups.add(accountant_group)

        # Crear datos de prueba
        self.category = Category.objects.create(name='Herramientas', description='Herramientas de construcción')
        self.brand = Brand.objects.create(name='Makita')
        self.product = Product.objects.create(
            name='Taladro', description='Taladro eléctrico', category=self.category, brand=self.brand,
            price=100000, discount_price=90000, stock=10, slug='taladro'
        )
        self.address = Address.objects.create(
            user=self.customer_user, street_address='Calle Falsa 123', country=Country('CL'), zip_code='12345', address_type='S'
        )
        self.cart = Cart.objects.create(user=self.customer_user)
        self.cart_item = CartItem.objects.create(cart=self.cart, product=self.product, quantity=2, price=self.product.get_final_price())
        self.coupon = Coupon.objects.create(code='DESC10', amount=10000, valid_from='2025-01-01', valid_to='2025-12-31', active=True)

    def test_customer_flow(self):
        # Iniciar sesión como cliente
        self.client.login(username='customer1', password='password123')

        # Añadir producto al carrito
        response = self.client.post(reverse('customer_cart'), {
            'product_id': self.product.id, 'quantity': 1
        })
        self.assertEqual(response.status_code, 302)  # Redirige tras añadir
        self.assertEqual(CartItem.objects.filter(cart__user=self.customer_user).count(), 2)

        # Crear orden
        self.api_client.force_authenticate(user=self.customer_user)
        order_data = {
            'user_id': self.customer_user.id,
            'delivery_method': 'home',
            'shipping_address_id': self.address.id,
            'items': [{'product_id': self.product.id, 'quantity': 1, 'price': self.product.get_final_price()}],
            'coupon': self.coupon.id
        }
        response = self.api_client.post('/api/orders/', order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(id=response.data['id'])
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.get_total(), self.product.get_final_price() - self.coupon.amount)

        # Crear intento de pago
        payment_data = {'order_id': order.id, 'amount': order.get_total()}
        response = self.api_client.post('/api/create-payment-intent/', payment_data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('clientSecret', response.data)
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.method, 'credit')
        self.assertFalse(payment.confirmed)

    def test_admin_password_change(self):
        # Iniciar sesión como administrador con contraseña inicial (RUT)
        self.client.login(username='admin1', password='123456789')
        response = self.client.get(reverse('index'))
        self.assertRedirects(response, reverse('change_password'))  # Debe redirigir

        # Cambiar contraseña
        response = self.client.post(reverse('change_password'), {
            'old_password': '123456789',
            'new_password1': 'newsecure123',
            'new_password2': 'newsecure123'
        })
        self.assertEqual(response.status_code, 302)
        self.client.logout()
        self.client.login(username='admin1', password='newsecure123')
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)  # No redirige tras cambio

    def test_seller_approve_order(self):
        # Crear orden
        order = Order.objects.create(user=self.customer_user, delivery_method='home', shipping_address=self.address)
        OrderItem.objects.create(order=order, product=self.product, quantity=1, price=self.product.get_final_price())

        # Iniciar sesión como vendedor
        self.api_client.force_authenticate(user=self.seller_user)
        response = self.api_client.post(f'/api/orders/{order.id}/approve/')
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'approved')

    def test_warehouse_prepare_order(self):
        # Crear orden aprobada
        order = Order.objects.create(user=self.customer_user, delivery_method='home', shipping_address=self.address, status='approved')
        OrderItem.objects.create(order=order, product=self.product, quantity=1, price=self.product.get_final_price())

        # Iniciar sesión como bodeguero
        self.api_client.force_authenticate(user=self.warehouse_user)
        response = self.api_client.post(f'/api/orders/{order.id}/prepare/')
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'prepared')

    def test_accountant_confirm_payment(self):
        # Crear orden y pago
        order = Order.objects.create(user=self.customer_user, delivery_method='home', shipping_address=self.address)
        payment = Payment.objects.create(order=order, amount=order.get_total(), method='credit', stripe_payment_intent_id='pi_test_123')

        # Iniciar sesión como contador
        self.api_client.force_authenticate(user=self.accountant_user)
        response = self.api_client.post(f'/api/payments/{payment.id}/confirm/')
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertTrue(payment.confirmed)
        self.assertEqual(payment.confirmed_by, self.accountant_user)

    def test_stripe_webhook(self):
        # Crear orden y pago
        order = Order.objects.create(user=self.customer_user, delivery_method='home', shipping_address=self.address)
        payment = Payment.objects.create(order=order, amount=order.get_total(), method='credit', stripe_payment_intent_id='pi_test_123')

        # Simular evento de Stripe
        event = {
            'type': 'payment_intent.succeeded',
            'data': {'object': {'id': 'pi_test_123', 'metadata': {'order_id': str(order.id)}}}
        }
        response = self.client.post(
            reverse('stripe_webhook'),
            data=json.dumps(event),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'  # Configurar webhook secret en pruebas
        )
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertTrue(payment.confirmed)
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')

    def test_permissions(self):
        # Intentar aprobar orden como cliente (debe fallar)
        order = Order.objects.create(user=self.customer_user, delivery_method='home', shipping_address=self.address)
        self.api_client.force_authenticate(user=self.customer_user)
        response = self.api_client.post(f'/api/orders/{order.id}/approve/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Intentar preparar orden como vendedor (debe fallar)
        self.api_client.force_authenticate(user=self.seller_user)
        response = self.api_client.post(f'/api/orders/{order.id}/prepare/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Intentar confirmar pago como bodeguero (debe fallar)
        payment = Payment.objects.create(order=order, amount=order.get_total(), method='credit')
        self.api_client.force_authenticate(user=self.warehouse_user)
        response = self.api_client.post(f'/api/payments/{payment.id}/confirm/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)