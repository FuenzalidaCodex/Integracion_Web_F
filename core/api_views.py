from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import stripe
import json
import time
import requests
from core.models import Category, Brand, Product, Address, Cart, CartItem, Order, OrderItem, Payment, Coupon, Refund, Employee, UserProfile
from core.serializers import (
    CategorySerializer, BrandSerializer, ProductSerializer, AddressSerializer,
    CartSerializer, OrderSerializer, PaymentSerializer, CouponSerializer,
    RefundSerializer, EmployeeSerializer, UserProfileSerializer, UserSerializer
)
from rest_framework.decorators import action
from rest_framework.response import Response

# Configuración de la API de conversión de monedas
EXCHANGE_API_URL = "https://api.exchangerate-api.com/v4/latest/CLP"  # Alternativa para pruebas
# Para Banco Central de Chile: "https://api.sbif.cl/api-sbifv3/recursos_api/dolar"

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

class AddressViewSet(viewsets.ModelViewSet):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

class CartViewSet(viewsets.ModelViewSet):
    queryset = Cart.objects.all()
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def clear(self, request, pk=None):
        cart = self.get_object()
        if cart.user != request.user:
            return Response({'error': 'No tienes permiso para limpiar este carrito'}, status=403)
        cart.items.all().delete()
        return Response({'status': 'cart cleared'}, status=200)

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(order__user=self.request.user)

class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

class RefundViewSet(viewsets.ModelViewSet):
    queryset = Refund.objects.all()
    serializer_class = RefundSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Refund.objects.filter(order__user=self.request.user)

class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAdminUser]

class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserProfile.objects.filter(user=self.request.user)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]

@csrf_exempt
def create_payment_intent(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        order_id = data.get('order_id')
        try:
            order = Order.objects.get(id=order_id)
            intent = stripe.PaymentIntent.create(
                amount=int(order.get_total() * 100),
                currency='clp',
                metadata={'order_id': order.id}
            )
            return JsonResponse({'clientSecret': intent.client_secret})
        except Order.DoesNotExist:
            return JsonResponse({'error': 'Orden no encontrada'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return JsonResponse({'error': 'Payload inválido'}, status=400)
    except stripe.error.SignatureVerificationError:
        return JsonResponse({'error': 'Firma inválida'}, status=400)

    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        order_id = payment_intent['metadata']['order_id']
        order = Order.objects.get(id=order_id)
        payment = Payment.objects.get(order=order)
        payment.stripe_payment_intent_id = payment_intent['id']
        payment.confirmed = True
        payment.save()
        order.status = 'approved'
        order.save()

    return JsonResponse({'status': 'success'}, status=200)

@csrf_exempt
def convert_currency(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            amount_clp = data.get('amount_clp')
            target_currency = data.get('target_currency', 'USD')
            if not amount_clp:
                return JsonResponse({'error': 'Monto no proporcionado'}, status=400)

            # Llamada a la API de conversión de monedas
            response = requests.get(EXCHANGE_API_URL)
            if response.status_code != 200:
                return JsonResponse({'error': 'Error al obtener tasas de cambio'}, status=500)

            rates = response.json().get('rates', {})
            if target_currency not in rates:
                return JsonResponse({'error': f'Moneda {target_currency} no soportada'}, status=400)

            converted_amount = float(amount_clp) * rates[target_currency]
            return JsonResponse({
                'amount_clp': amount_clp,
                'target_currency': target_currency,
                'converted_amount': round(converted_amount, 2)
            }, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Método no permitido'}, status=405)