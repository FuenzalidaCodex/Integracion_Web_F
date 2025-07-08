from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django import forms
from django.contrib import messages
import stripe
import json
from django.conf import settings
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Product, Category, Brand, Cart, CartItem, Order, OrderItem, Payment, Address, Coupon, Refund, Employee, UserProfile, PriceHistory
from .serializers import ProductSerializer, CategorySerializer, BrandSerializer, CartSerializer, OrderSerializer, PaymentSerializer, AddressSerializer, CouponSerializer, RefundSerializer, EmployeeSerializer, UserProfileSerializer, UserSerializer
from django.contrib.auth.models import User
from .permissions import IsSeller, IsWarehouse, IsAccountant, IsAdmin
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from core.forms import UserForm, EmployeeForm
from core.models import Employee
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from core.models import Cart, CartItem, Product

stripe.api_key = settings.STRIPE_SECRET_KEY

# Forms for Template-Based Views
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']

class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ['name']

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'category', 'brand', 'price', 'discount_price', 'stock', 'image', 'slug']

class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ['code', 'amount', 'valid_from', 'valid_to', 'active']

# Permission Classes
class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'employee') and request.user.employee.role == 'admin'

class IsSeller(permissions.BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'employee') and request.user.employee.role == 'seller'

class IsWarehouse(permissions.BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'employee') and request.user.employee.role == 'warehouse'

class IsAccountant(permissions.BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'employee') and request.user.employee.role == 'accountant'

# API ViewSets
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return [permissions.IsAuthenticated()]

class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return [permissions.IsAuthenticated()]

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsSeller() | IsAdmin()]
        return [permissions.AllowAny()]  # Public access for product listing and details

    @action(detail=True, methods=['get'], permission_classes=[permissions.AllowAny])
    def details(self, request, pk=None):
        product = self.get_object()
        serializer = ProductSerializer(product)
        return Response({
            'Código del producto': product.code,
            'Marca': product.brand.name,
            'Código': product.brand.name,
            'Nombre': product.name,
            'Precio': [
                {'Fecha': history.created_at.isoformat(), 'Valor': float(history.price)}
                for history in product.price_history.all()
            ]
        })

class AddressViewSet(viewsets.ModelViewSet):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

class CartViewSet(viewsets.ModelViewSet):
    queryset = Cart.objects.all()
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def add_item(self, request, pk=None):
        cart = self.get_object()
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))
        try:
            product = Product.objects.get(id=product_id)
            if product.stock < quantity:
                return Response({'error': 'Stock insuficiente'}, status=400)
            CartItem.objects.create(cart=cart, product=product, quantity=quantity, price=product.get_final_price())
            return Response({'status': 'item added'})
        except Product.DoesNotExist:
            return Response({'error': 'Producto no encontrado'}, status=404)

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        elif self.action in ['update', 'partial_update', 'approve', 'prepare']:
            return [IsSeller() | IsWarehouse()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if hasattr(self.request.user, 'employee') and self.request.user.employee.role in ['seller', 'warehouse', 'accountant']:
            return Order.objects.all()
        return Order.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsSeller])
    def approve(self, request, pk=None):
        order = self.get_object()
        order.status = 'approved'
        order.save()
        return Response({'status': 'order approved'})

    @action(detail=True, methods=['post'], permission_classes=[IsWarehouse])
    def prepare(self, request, pk=None):
        order = self.get_object()
        order.status = 'prepared'
        order.save()
        return Response({'status': 'order prepared'})

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAccountant]

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        payment = self.get_object()
        payment.confirmed = True
        payment.confirmed_by = request.user
        payment.save()
        return Response({'status': 'payment confirmed'})

class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [IsAdmin]

class RefundViewSet(viewsets.ModelViewSet):
    queryset = Refund.objects.all()
    serializer_class = RefundSerializer
    permission_classes = [IsAdmin]

class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAdmin]

class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserProfile.objects.filter(user=self.request.user)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]

# Template-Based Views
def index(request):
    return render(request, 'index.html')

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if hasattr(user, 'employee') and user.employee.role == 'admin' and user.check_password(user.employee.rut.replace('-', '')):
                return redirect('change_password')
            return redirect('index')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('index')

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Contraseña cambiada exitosamente.')
            return redirect('index')
    else:
        form = PasswordChangeForm(user=request.user)
    return render(request, 'change_password.html', {'form': form})

# [CAMBIO] Remove login_required for public product catalog
def customer_catalog(request):
    products = Product.objects.all()
    return render(request, 'customer/catalog.html', {'products': products})

# [NUEVO] Add product detail view (public access)
def customer_product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    return render(request, 'customer/product_detail.html', {'product': product})

# [CAMBIO] Ensure cart requires login
@login_required
def customer_cart(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            product_id = request.POST.get('product_id')
            quantity = int(request.POST.get('quantity', 1))
            product = get_object_or_404(Product, id=product_id)
            if product.stock >= quantity:
                cart_item, item_created = CartItem.objects.get_or_create(
                    cart=cart, product=product, defaults={'price': product.get_final_price()}
                )
                if not item_created:
                    cart_item.quantity += quantity
                cart_item.save()
                messages.success(request, 'Producto añadido al carrito.')
            else:
                messages.error(request, 'No hay suficiente stock.')
        elif action == 'remove':
            item_id = request.POST.get('item_id')
            cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
            cart_item.delete()
            messages.success(request, 'Producto eliminado del carrito.')
        elif action == 'update':
            item_id = request.POST.get('item_id')
            quantity = int(request.POST.get('quantity', 1))
            cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
            if quantity <= cart_item.product.stock and quantity > 0:
                cart_item.quantity = quantity
                cart_item.save()
                messages.success(request, 'Cantidad actualizada en el carrito.')
            else:
                messages.error(request, 'Cantidad inválida o no hay suficiente stock.')
        return redirect('customer_cart')
    return render(request, 'customer/cart.html', {'cart': cart})

# [CAMBIO] Ensure checkout requires login
@login_required
def customer_checkout(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    addresses = Address.objects.filter(user=request.user)
    return render(request, 'customer/checkout.html', {
        'cart': cart,
        'addresses': addresses,
        'publishable_key': settings.STRIPE_PUBLISHABLE_KEY
    })

# [NUEVO] Add user registration view
def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registro exitoso. ¡Bienvenido!')
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

# [NUEVO] Add contact page view (public access, for Paso 2)
def contact_view(request):
    if request.method == 'POST':
        # Basic contact form handling (to be expanded in Paso 2)
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')
        # For now, just display a success message
        messages.success(request, 'Mensaje enviado. Nos pondremos en contacto pronto.')
        return redirect('contact')
    return render(request, 'contact.html')

# [NUEVO] Add order confirmation view
@login_required
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'customer/order_confirmation.html', {'order': order})

# Admin Views
from django.contrib.auth.models import User
from core.models import Product, Order, Refund

@login_required
def admin_dashboard(request):
    if not hasattr(request.user, 'employee') or request.user.employee.role != 'admin':
        messages.error(request, 'Acceso denegado.')
        return redirect('index')
    
    total_users = User.objects.count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()
    pending_refunds = Refund.objects.filter(accepted=False).count()
    
    return render(request, 'admin/dashboard.html', {
        'total_users': total_users,
        'total_products': total_products,
        'total_orders': total_orders,
        'pending_refunds': pending_refunds
    })

@login_required
def admin_user_management(request):
    if not hasattr(request.user, 'employee') or request.user.employee.role != 'admin':
        messages.error(request, 'Acceso denegado.')
        return redirect('index')
    
    editing = False
    user_to_edit = None
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            user_id = request.POST.get('user_id')
            user = get_object_or_404(User, id=user_id)
            if user != request.user:  # Prevent self-deletion
                user.delete()
                messages.success(request, 'Usuario eliminado exitosamente.')
            else:
                messages.error(request, 'No puedes eliminar tu propio usuario.')
            return redirect('admin_user_management')
        else:
            # Handle create or update
            user_id = request.POST.get('user_id')
            if user_id:
                user_to_edit = get_object_or_404(User, id=user_id)
                user_form = UserForm(request.POST, instance=user_to_edit)
                employee = getattr(user_to_edit, 'employee', None)
                employee_form = EmployeeForm(request.POST, instance=employee)
                editing = True
            else:
                user_form = UserForm(request.POST)
                employee_form = EmployeeForm(request.POST)
            if user_form.is_valid() and employee_form.is_valid():
                user = user_form.save()
                employee = employee_form.save(commit=False)
                employee.user = user
                employee.save()
                messages.success(request, f'Usuario {"actualizado" if user_id else "creado"} exitosamente.')
                return redirect('admin_user_management')
    else:
        # Handle GET with edit query parameter
        edit_id = request.GET.get('edit')
        if edit_id:
            user_to_edit = get_object_or_404(User, id=edit_id)
            user_form = UserForm(instance=user_to_edit)
            employee = getattr(user_to_edit, 'employee', None)
            employee_form = EmployeeForm(instance=employee)
            editing = True
        else:
            user_form = UserForm()
            employee_form = EmployeeForm()
    
    users = User.objects.all()
    return render(request, 'admin/user_management.html', {
        'users': users,
        'user_form': user_form,
        'employee_form': employee_form,
        'editing': editing,
        'user_to_edit': user_to_edit
    })

@login_required
def admin_category_management(request):
    if not hasattr(request.user, 'employee') or request.user.employee.role != 'admin':
        messages.error(request, 'Acceso denegado.')
        return redirect('index')
    
    editing = False
    category_to_edit = None
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            category_id = request.POST.get('category_id')
            category = get_object_or_404(Category, id=category_id)
            category.delete()
            messages.success(request, 'Categoría eliminada exitosamente.')
            return redirect('admin_category_management')
        else:
            # Handle create or update
            category_id = request.POST.get('category_id')
            if category_id:
                category_to_edit = get_object_or_404(Category, id=category_id)
                form = CategoryForm(request.POST, instance=category_to_edit)
                editing = True
            else:
                form = CategoryForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, f'Categoría {"actualizada" if category_id else "creada"} exitosamente.')
                return redirect('admin_category_management')
    else:
        # Handle GET with edit query parameter
        edit_id = request.GET.get('edit')
        if edit_id:
            category_to_edit = get_object_or_404(Category, id=edit_id)
            form = CategoryForm(instance=category_to_edit)
            editing = True
        else:
            form = CategoryForm()
    
    categories = Category.objects.all()
    return render(request, 'admin/category_management.html', {
        'form': form,
        'categories': categories,
        'editing': editing,
        'category_to_edit': category_to_edit
    })

@login_required
def admin_brand_management(request):
    if not hasattr(request.user, 'employee') or request.user.employee.role != 'admin':
        messages.error(request, 'Acceso denegado.')
        return redirect('index')
    
    editing = False
    brand_to_edit = None
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            brand_id = request.POST.get('brand_id')
            brand = get_object_or_404(Brand, id=brand_id)
            brand.delete()
            messages.success(request, 'Marca eliminada exitosamente.')
            return redirect('admin_brand_management')
        else:
            # Handle create or update
            brand_id = request.POST.get('brand_id')
            if brand_id:
                brand_to_edit = get_object_or_404(Brand, id=brand_id)
                form = BrandForm(request.POST, instance=brand_to_edit)
                editing = True
            else:
                form = BrandForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, f'Marca {"actualizada" if brand_id else "creada"} exitosamente.')
                return redirect('admin_brand_management')
    else:
        # Handle GET with edit query parameter
        edit_id = request.GET.get('edit')
        if edit_id:
            brand_to_edit = get_object_or_404(Brand, id=edit_id)
            form = BrandForm(instance=brand_to_edit)
            editing = True
        else:
            form = BrandForm()
    
    brands = Brand.objects.all()
    return render(request, 'admin/brand_management.html', {
        'form': form,
        'brands': brands,
        'editing': editing,
        'brand_to_edit': brand_to_edit
    })

@login_required
def admin_coupon_management(request):
    if not hasattr(request.user, 'employee') or request.user.employee.role != 'admin':
        messages.error(request, 'Acceso denegado.')
        return redirect('index')
    
    editing = False
    coupon_to_edit = None
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            coupon_id = request.POST.get('coupon_id')
            coupon = get_object_or_404(Coupon, id=coupon_id)
            coupon.delete()
            messages.success(request, 'Cupón eliminado exitosamente.')
            return redirect('admin_coupon_management')
        else:
            # Handle create or update
            coupon_id = request.POST.get('coupon_id')
            if coupon_id:
                coupon_to_edit = get_object_or_404(Coupon, id=coupon_id)
                form = CouponForm(request.POST, instance=coupon_to_edit)
                editing = True
            else:
                form = CouponForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, f'Cupón {"actualizado" if coupon_id else "creado"} exitosamente.')
                return redirect('admin_coupon_management')
    else:
        # Handle GET with edit query parameter
        edit_id = request.GET.get('edit')
        if edit_id:
            coupon_to_edit = get_object_or_404(Coupon, id=edit_id)
            form = CouponForm(instance=coupon_to_edit)
            editing = True
        else:
            form = CouponForm()
    
    coupons = Coupon.objects.all()
    return render(request, 'admin/coupon_management.html', {
        'form': form,
        'coupons': coupons,
        'editing': editing,
        'coupon_to_edit': coupon_to_edit
    })

@login_required
def admin_refund_management(request):
    if not hasattr(request.user, 'employee') or request.user.employee.role != 'admin':
        messages.error(request, 'Acceso denegado.')
        return redirect('index')
    if request.method == 'POST':
        refund_id = request.POST.get('refund_id')
        action = request.POST.get('action')
        refund = get_object_or_404(Refund, id=refund_id)
        if action == 'accept':
            refund.accepted = True
            refund.save()
            messages.success(request, 'Reembolso aceptado exitosamente.')
        elif action == 'reject':
            refund.accepted = False
            refund.save()
            messages.success(request, 'Reembolso rechazado exitosamente.')
        elif action == 'delete':
            refund.delete()
            messages.success(request, 'Reembolso eliminado exitosamente.')
        return redirect('admin_refund_management')
    refunds = Refund.objects.all()
    return render(request, 'admin/refund_management.html', {'refunds': refunds})

# Seller Views
@login_required
def seller_orders(request):
    if not hasattr(request.user, 'employee') or request.user.employee.role != 'seller':
        messages.error(request, 'Acceso denegado.')
        return redirect('index')
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        action = request.POST.get('action')
        order = get_object_or_404(Order, id=order_id)
        if action == 'approve':
            order.status = 'approved'
            order.save()
            messages.success(request, 'Pedido aprobado.')
        return redirect('seller_orders')
    orders = Order.objects.all()
    return render(request, 'seller/orders.html', {'orders': orders})

@login_required
def seller_products(request):
    if not hasattr(request.user, 'employee') or request.user.employee.role != 'seller':
        messages.error(request, 'Acceso denegado.')
        return redirect('index')
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto creado exitosamente.')
            return redirect('seller_products')
    else:
        form = ProductForm()
    products = Product.objects.all()
    return render(request, 'seller/products.html', {'form': form, 'products': products})

# Warehouse Views
@login_required
def warehouse_orders(request):
    if not hasattr(request.user, 'employee') or request.user.employee.role != 'warehouse':
        messages.error(request, 'Acceso denegado.')
        return redirect('index')
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        action = request.POST.get('action')
        order = get_object_or_404(Order, id=order_id)
        if action == 'prepare':
            order.status = 'prepared'
            order.save()
            messages.success(request, 'Pedido preparado.')
        return redirect('warehouse_orders')
    orders = Order.objects.filter(status__in=['approved', 'prepared'])
    return render(request, 'warehouse/orders.html', {'orders': orders})

@login_required
def warehouse_inventory(request):
    if not hasattr(request.user, 'employee') or request.user.employee.role != 'warehouse':
        messages.error(request, 'Acceso denegado.')
        return redirect('index')
    products = Product.objects.all()
    return render(request, 'warehouse/inventory.html', {'products': products})

# Accountant Views
@login_required
def accountant_payments(request):
    if not hasattr(request.user, 'employee') or request.user.employee.role != 'accountant':
        messages.error(request, 'Acceso denegado.')
        return redirect('index')
    if request.method == 'POST':
        payment_id = request.POST.get('payment_id')
        action = request.POST.get('action')
        payment = get_object_or_404(Payment, id=payment_id)
        if action == 'confirm':
            payment.confirmed = True
            payment.confirmed_by = request.user
            payment.save()
            messages.success(request, 'Pago confirmado.')
        return redirect('accountant_payments')
    payments = Payment.objects.all()
    return render(request, 'accountant/payments.html', {'payments': payments})

# Stripe Payment Views
@csrf_exempt
def create_payment_intent(request):
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        amount = data.get('amount')  # En centavos
        order = Order.objects.get(id=order_id)
        user = order.user

        user_profile, created = UserProfile.objects.get_or_create(user=user)
        if not user_profile.stripe_customer_id:
            customer = stripe.Customer.create(email=user.email)
            user_profile.stripe_customer_id = customer['id']
            user_profile.save()

        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convertir a centavos
            currency='clp',
            payment_method_types=['card'],
            customer=user_profile.stripe_customer_id,
            metadata={'order_id': order_id},
        )

        payment = Payment.objects.create(
            order=order,
            amount=amount,
            method='credit',
            stripe_payment_intent_id=intent['id']
        )

        return JsonResponse({
            'clientSecret': intent['client_secret'],
            'publishableKey': settings.STRIPE_PUBLISHABLE_KEY,
        })
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Orden no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except stripe.error.SignatureVerificationError:
        return JsonResponse({'status': 'invalid signature'}, status=400)
    except stripe.error.StripeError as e:
        return JsonResponse({'status': 'stripe error', 'error': str(e)}, status=400)

    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        order_id = payment_intent['metadata']['order_id']
        try:
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent['id'])
            payment.confirmed = True
            payment.confirmed_by = None  # Webhook confirma automáticamente
            payment.save()
            order = payment.order
            order.status = 'paid'
            order.save()
            return JsonResponse({'status': 'payment confirmed'})
        except Payment.DoesNotExist:
            return JsonResponse({'status': 'payment not found'}, status=404)
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        try:
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent['id'])
            payment.confirmed = False
            payment.save()
            return JsonResponse({'status': 'payment failed'})
        except Payment.DoesNotExist:
            return JsonResponse({'status': 'payment not found'}, status=404)

    return JsonResponse({'status': 'event handled'})