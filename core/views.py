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
import logging
from django.conf import settings
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Product, Category, Brand, Cart, CartItem, Order, OrderItem, Payment, Address, Coupon, Refund, Employee, UserProfile, PriceHistory
from .serializers import ProductSerializer, CategorySerializer, BrandSerializer, CartSerializer, OrderSerializer, PaymentSerializer, AddressSerializer, CouponSerializer, RefundSerializer, EmployeeSerializer, UserProfileSerializer, UserSerializer
from django.contrib.auth.models import User
from .permissions import IsSeller, IsWarehouse, IsAccountant, IsAdmin
from .forms import UserForm, EmployeeForm, AddressForm
from django.db.models import Q
from django.core.serializers.json import DjangoJSONEncoder

# Configurar logging
logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        widgets = {'password': forms.PasswordInput()}

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['rut', 'first_name', 'last_name', 'role']

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
        return [permissions.AllowAny()]

    @action(detail=True, methods=['get'], permission_classes=[permissions.AllowAny])
    def details(self, request, pk=None):
        product = self.get_object()
        serializer = ProductSerializer(product)
        return Response({
            'Código del producto': product.code,
            'Marca': product.brand.name,
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

def index(request):
    featured_products = Product.objects.filter(stock__gt=0).order_by('-id')[:3]
    return render(request, 'index.html', {'featured_products': featured_products})

def register(request):
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

def login_view(request):
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, 'Bienvenido de nuevo.')
                return redirect('index')
        messages.error(request, 'Credenciales incorrectas. Por favor, intenta de nuevo.')
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
            messages.error(request, 'Por favor, corrige los errores en el formulario.')
    else:
        form = PasswordChangeForm(user=request.user)
    return render(request, 'change_password.html', {'form': form})

def customer_catalog(request):
    products = Product.objects.all()
    categories = Category.objects.all()
    brands = Brand.objects.all()
    
    search_query = request.GET.get('search')
    category_id = request.GET.get('category')
    brand_id = request.GET.get('brand')
    
    if search_query:
        products = products.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))
    if category_id:
        products = products.filter(category_id=category_id)
    if brand_id:
        products = products.filter(brand_id=brand_id)
    
    return render(request, 'customer/catalog.html', {
        'products': products,
        'categories': categories,
        'brands': brands
    })

def customer_product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    return render(request, 'customer/product_detail.html', {'product': product})

@login_required
def customer_cart(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    logger.debug(f"Carrito para {request.user.username}: ID {cart.id}, Creado: {created}")

    if request.method == 'POST':
        logger.debug(f"Solicitud POST: {request.POST}")
        action = request.POST.get('action')
        if action == 'add':
            product_id = request.POST.get('product_id')
            quantity = request.POST.get('quantity', '1')
            try:
                quantity = int(quantity)
                product = get_object_or_404(Product, id=product_id)
                if quantity <= 0:
                    messages.error(request, 'La cantidad debe ser mayor a 0.')
                    logger.warning(f"Cantidad inválida: {quantity}")
                elif quantity <= product.stock:
                    cart_item, item_created = CartItem.objects.get_or_create(
                        cart=cart, product=product, defaults={'price': product.get_final_price(), 'quantity': quantity}
                    )
                    if not item_created:
                        new_quantity = cart_item.quantity + quantity
                        if new_quantity <= product.stock:
                            cart_item.quantity = new_quantity
                            cart_item.price = product.get_final_price()
                            cart_item.save()
                            messages.success(request, f'Se añadieron {quantity} unidad(es) de {product.name} al carrito.')
                            logger.debug(f"Actualizado {product.name}: Cantidad {cart_item.quantity}")
                        else:
                            messages.error(request, f'No hay suficiente stock para añadir {quantity} unidad(es) más.')
                            logger.warning(f"Stock insuficiente para {product.name}: Solicitado {new_quantity}, Disponible {product.stock}")
                    else:
                        messages.success(request, f'{product.name} añadido al carrito.')
                        logger.debug(f"Añadido nuevo ítem: {product.name}, Cantidad {quantity}")
                else:
                    messages.error(request, f'No hay suficiente stock. Solo hay {product.stock} unidad(es) disponibles.')
                    logger.warning(f"Stock insuficiente para {product.name}: Solicitado {quantity}, Disponible {product.stock}")
            except ValueError:
                messages.error(request, 'Cantidad inválida.')
                logger.error(f"Cantidad no válida: {quantity}")
            except Product.DoesNotExist:
                messages.error(request, 'Producto no encontrado.')
                logger.error(f"Producto no encontrado: ID {product_id}")
        elif action == 'remove':
            item_id = request.POST.get('item_id')
            try:
                cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
                product_name = cart_item.product.name
                cart_item.delete()
                messages.success(request, f'{product_name} eliminado del carrito.')
                logger.debug(f"Eliminado {product_name}: ID {item_id}")
            except CartItem.DoesNotExist:
                messages.error(request, 'Ítem no encontrado.')
                logger.error(f"Ítem no encontrado: ID {item_id}")
        elif action == 'update':
            item_id = request.POST.get('item_id')
            quantity = request.POST.get('quantity', '1')
            try:
                quantity = int(quantity)
                cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
                if quantity <= 0:
                    messages.error(request, 'La cantidad debe ser mayor a 0.')
                    logger.warning(f"Cantidad inválida: {quantity}")
                elif quantity <= cart_item.product.stock:
                    cart_item.quantity = quantity
                    cart_item.price = cart_item.product.get_final_price()
                    cart_item.save()
                    messages.success(request, f'Cantidad de {cart_item.product.name} actualizada.')
                    logger.debug(f"Actualizado {cart_item.product.name}: Nueva cantidad {quantity}")
                else:
                    messages.error(request, f'No hay suficiente stock. Solo hay {cart_item.product.stock} unidad(es) disponibles.')
                    logger.warning(f"Stock insuficiente para {cart_item.product.name}: Solicitado {quantity}, Disponible {cart_item.product.stock}")
            except ValueError:
                messages.error(request, 'Cantidad inválida.')
                logger.error(f"Cantidad no válida: {quantity}")
            except CartItem.DoesNotExist:
                messages.error(request, 'Ítem no encontrado.')
                logger.error(f"Ítem no encontrado: ID {item_id}")
        return redirect('customer_cart')

    items = cart.items.all()
    logger.debug(f"Ítems en carrito ID {cart.id}: {[f'{item.product.name} x {item.quantity}' for item in items]}")
    return render(request, 'customer/cart.html', {'cart': cart})

@login_required
def customer_add_address(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, 'Dirección añadida exitosamente.')
            return redirect('customer_checkout')
    else:
        form = AddressForm(initial={'country': 'CL'})
    return render(request, 'customer/add_address.html', {'form': form})

@login_required
def customer_checkout(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    addresses = Address.objects.filter(user=request.user)
    cart_items = [
        {
            'product_id': item.product.id,
            'quantity': item.quantity,
            'price': float(item.price),
            'total_price': float(item.get_total_price()),
            'name': item.product.name
        }
        for item in cart.items.all()
    ]
    cart_total_cents = int(cart.get_total() * 100)
    return render(request, 'customer/checkout.html', {
        'cart': cart,
        'addresses': addresses,
        'publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
        'cart_items_json': json.dumps(cart_items, cls=DjangoJSONEncoder),
        'cart_total_cents': cart_total_cents
    })

@csrf_exempt
def create_checkout_session(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        cart_items = data.get('cart_items')
        delivery_method = data.get('delivery_method')
        shipping_address_id = data.get('shipping_address_id')

        if not (cart_items and delivery_method and shipping_address_id):
            return JsonResponse({'error': 'Datos incompletos'}, status=400)

        shipping_address = get_object_or_404(Address, id=shipping_address_id, user=request.user)
        
        # Crear la orden
        order = Order.objects.create(
            user=request.user,
            delivery_method=delivery_method,
            shipping_address=shipping_address,
            status='pending'
        )

        # Añadir ítems a la orden
        for item in cart_items:
            product = get_object_or_404(Product, id=item['product_id'])
            if product.stock < item['quantity']:
                order.delete()
                return JsonResponse({'error': f'Stock insuficiente para {product.name}'}, status=400)
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item['quantity'],
                price=item['price']
            )

        # Crear la sesión de Stripe Checkout
        line_items = [{
            'price_data': {
                'currency': 'clp',
                'product_data': {
                    'name': item['name'],
                },
                'unit_amount': int(item['price'] * 100),
            },
            'quantity': item['quantity'],
        } for item in cart_items]

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=request.build_absolute_uri('/order/confirmation/') + f'{order.id}/',
            cancel_url=request.build_absolute_uri('/customer/checkout/'),
            metadata={'order_id': order.id},
            customer_email=request.user.email,
            shipping_address_collection={'allowed_countries': ['CL']},
        )

        return JsonResponse({'sessionId': session.id})
    except Exception as e:
        logger.error(f"Error al crear sesión de checkout: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

def contact_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')
        messages.success(request, 'Mensaje enviado. Nos pondremos en contacto pronto.')
        return redirect('contact')
    return render(request, 'contact.html')

@login_required
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'customer/order_confirmation.html', {'order': order})

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
            if user != request.user:
                user.delete()
                messages.success(request, 'Usuario eliminado exitosamente.')
            else:
                messages.error(request, 'No puedes eliminar tu propio usuario.')
            return redirect('admin_user_management')
        else:
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
    if not request.user.is_authenticated or not hasattr(request.user, 'employee') or request.user.employee.role != 'seller':
        messages.error(request, 'Acceso denegado.')
        return redirect('index')
    
    editing = False
    product_to_edit = None
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            product_id = request.POST.get('product_id')
            product = get_object_or_404(Product, id=product_id)
            product.delete()
            messages.success(request, 'Producto eliminado exitosamente.')
            return redirect('seller_products')
        else:
            product_id = request.POST.get('product_id')
            if product_id:
                product_to_edit = get_object_or_404(Product, id=product_id)
                form = ProductForm(request.POST, request.FILES, instance=product_to_edit)
                editing = True
            else:
                form = ProductForm(request.POST, request.FILES)
            if form.is_valid():
                product = form.save()
                messages.success(request, f'Producto {"actualizado" if product_id else "creado"} exitosamente.')
                return redirect('seller_products')
    else:
        edit_id = request.GET.get('edit')
        if edit_id:
            product_to_edit = get_object_or_404(Product, id=edit_id)
            form = ProductForm(instance=product_to_edit)
            editing = True
        else:
            form = ProductForm()
    
    products = Product.objects.all()
    return render(request, 'seller_products.html', {
        'form': form,
        'products': products,
        'editing': editing,
        'product_to_edit': product_to_edit
    })

@login_required
def warehouse_orders(request):
    if not hasattr(request.user, 'employee') or request.user.employee.role != 'warehouse':
        messages.error(request, 'Acceso denegado.')
        return redirect('index')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        order_id = request.POST.get('order_id')
        order = get_object_or_404(Order, id=order_id)
        if action == 'prepare' and order.status == 'approved':
            order.status = 'prepared'
            order.save()
            messages.success(request, 'Orden preparada exitosamente.')
        return redirect('warehouse_orders')
    
    orders = Order.objects.filter(status__in=['approved', 'prepared'])
    return render(request, 'warehouse/orders.html', {'orders': orders})

@login_required
def warehouse_order_detail(request, order_id):
    if not hasattr(request.user, 'employee') or request.user.employee.role != 'warehouse':
        messages.error(request, 'Acceso denegado.')
        return redirect('index')
    
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'warehouse/order_detail.html', {'order': order})

@login_required
def warehouse_inventory(request):
    if not hasattr(request.user, 'employee') or request.user.employee.role != 'warehouse':
        messages.error(request, 'Acceso denegado.')
        return redirect('index')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'stock_update':
            product_id = request.POST.get('product_id')
            stock = int(request.POST.get('stock', '0'))
            product = get_object_or_404(Product, id=product_id)
            if stock >= 0:
                product.stock = stock
                product.save()
                messages.success(request, f'Stock actualizado para {product.name}.')
            else:
                messages.error(request, 'El stock debe ser mayor o igual a cero.')
            return redirect('warehouse_inventory')
    
    products = Product.objects.all()
    return render(request, 'warehouse/inventory.html', {'products': products})

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
            messages.success(request, 'Pago confirmado exitosamente.')
        return redirect('accountant_payments')
    
    payments = Payment.objects.all()
    return render(request, 'accountant/payments.html', {'payments': payments})

@csrf_exempt
def create_payment_intent(request):
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        amount = data.get('amount')
        order = get_object_or_404(Order, id=order_id)
        user = order.user

        user_profile, created = UserProfile.objects.get_or_create(user=user)
        if not user_profile.stripe_customer_id:
            customer = stripe.Customer.create(email=user.email)
            user_profile.stripe_customer_id = customer['id']
            user_profile.save()

        intent = stripe.PaymentIntent.create(
            amount=int(amount),
            currency='clp',
            payment_method_types=['card'],
            customer=user_profile.stripe_customer_id,
            metadata={'order_id': order_id},
        )

        payment = Payment.objects.create(
            order=order,
            amount=amount / 100,
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
        logger.error(f"Error creating payment intent: {str(e)}")
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
        logger.error("Invalid webhook signature")
        return JsonResponse({'status': 'invalid signature'}, status=400)
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        return JsonResponse({'status': 'stripe error', 'error': str(e)}, status=400)

    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        order_id = payment_intent.get('metadata', {}).get('order_id')
        try:
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent.id)
            payment.confirmed = True
            payment.confirmed_by = None
            payment.save()
            order = payment.order
            order.status = 'paid'
            order.save()

            # Reducir stock
            for item in order.items.all():
                product = item.product
                if product.stock >= item.quantity:
                    product.stock -= item.quantity
                    product.save()
                    logger.debug(f"Stock reducido para {product.name}: -{item.quantity}, Nuevo stock: {product.stock}")
                else:
                    logger.error(f"Stock insuficiente para {product.name} en orden {order_id}")
                    order.status = 'error'
                    order.save()
                    return JsonResponse({'status': 'insufficient stock'}, status=400)

            # Limpiar carrito
            cart = Cart.objects.get(user=order.user)
            cart.items.all().delete()
            logger.info(f"Carrito limpiado para usuario {order.user.username}")

            return JsonResponse({'status': 'payment confirmed'})
        except Payment.DoesNotExist:
            logger.error(f"Pago no encontrado: ID {payment_intent.id}")
            return JsonResponse({'status': 'payment not found'}, status=404)
        except Order.DoesNotExist:
            logger.error(f"Orden no encontrada: {order_id}")
            return JsonResponse({'status': 'order not found'}, status=404)
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        try:
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent.id)
            payment.confirmed = False
            payment.save()
            logger.info(f"Pago fallido: ID {payment_intent.id}")
            return JsonResponse({'status': 'payment failed'})
        except Payment.DoesNotExist:
            logger.error(f"Pago no encontrado: ID {payment_intent.id}")
            return JsonResponse({'status': 'payment not found'}, status=404)
    elif event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        order_id = session.get('metadata', {}).get('order_id')
        try:
            order = Order.objects.get(id=order_id)
            payment = Payment.objects.create(
                order=order,
                amount=order.get_total(),
                method='credit',
                stripe_payment_intent_id=session.payment_intent,
                confirmed=True
            )
            order.status = 'processing'
            order.save()

            # Reducir stock
            for item in order.items.all():
                product = item.product
                if product.stock >= item.quantity:
                    product.stock -= item.quantity
                    product.save()
                    logger.debug(f"Stock reducido para {product.name}: -{item.quantity}, Nuevo stock: {product.stock}")
                else:
                    logger.error(f"Stock insuficiente para {product.name} en orden {order_id}")
                    order.status = 'error'
                    order.save()
                    return JsonResponse({'status': 'insufficient stock'}, status=400)

            # Limpiar carrito
            cart = Cart.objects.get(user=order.user)
            cart.items.all().delete()
            logger.info(f"Carrito limpiado para: {order.user.username}")

            return JsonResponse({'status': 'payment processed'})
        except Order.DoesNotExist:
            logger.error(f"Orden no encontrada: {order_id}")
            return JsonResponse({'status': 'order not found'}, status=404)
        except Exception as e:
            logger.error(f"Error procesando webhook: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'status': 'event handled'})