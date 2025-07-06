from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Configurar el router para las APIs
router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet)  # API para categorías
router.register(r'brands', views.BrandViewSet)  # API para marcas
router.register(r'products', views.ProductViewSet)  # API para productos
router.register(r'addresses', views.AddressViewSet)  # API para direcciones
router.register(r'carts', views.CartViewSet)  # API para carritos
router.register(r'orders', views.OrderViewSet)  # API para pedidos
router.register(r'payments', views.PaymentViewSet)  # API para pagos
router.register(r'coupons', views.CouponViewSet)  # API para cupones
router.register(r'refunds', views.RefundViewSet)  # API para reembolsos
router.register(r'employees', views.EmployeeViewSet)  # API para empleados
router.register(r'userprofiles', views.UserProfileViewSet)  # API para perfiles de usuario
router.register(r'users', views.UserViewSet)  # API para usuarios

# Rutas para vistas basadas en plantillas y APIs
urlpatterns = [
    # Vistas principales
    path('', views.index, name='index'),  # Página de inicio
    path('login/', views.login_view, name='login'),  # Página de login
    path('change-password/', views.change_password, name='change_password'),  # Página para cambiar contraseña

    # Vistas para clientes
    path('catalog/', views.customer_catalog, name='customer_catalog'),  # Catálogo de productos
    path('cart/', views.customer_cart, name='customer_cart'),  # Carrito de compras
    path('checkout/', views.customer_checkout, name='customer_checkout'),  # Página de checkout

    # Vistas para administradores
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),  # Dashboard de administrador
    path('admin/users/', views.admin_user_management, name='admin_user_management'),  # Gestión de usuarios
    path('admin/categories/', views.admin_category_management, name='admin_category_management'),  # Gestión de categorías
    path('admin/brands/', views.admin_brand_management, name='admin_brand_management'),  # Gestión de marcas
    path('admin/coupons/', views.admin_coupon_management, name='admin_coupon_management'),  # Gestión de cupones
    path('admin/refunds/', views.admin_refund_management, name='admin_refund_management'),  # Gestión de reembolsos

    # Vistas para vendedores
    path('seller/orders/', views.seller_orders, name='seller_orders'),  # Gestión de pedidos
    path('seller/products/', views.seller_products, name='seller_products'),  # Gestión de productos

    # Vistas para bodegueros
    path('warehouse/orders/', views.warehouse_orders, name='warehouse_orders'),  # Gestión de pedidos
    path('warehouse/inventory/', views.warehouse_inventory, name='warehouse_inventory'),  # Gestión de inventario

    # Vistas para contadores
    path('accountant/payments/', views.accountant_payments, name='accountant_payments'),  # Gestión de pagos

    # APIs
    path('api/', include(router.urls)),  # Incluye todas las rutas de las APIs
    path('api/create-payment-intent/', views.create_payment_intent, name='create_payment_intent'),  # Crear intento de pago con Stripe
    path('api/webhook/', views.stripe_webhook, name='stripe_webhook'),  # Webhook de Stripe
]