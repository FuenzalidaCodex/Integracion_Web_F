from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Configurar el router para las APIs
router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet)
router.register(r'brands', views.BrandViewSet)
router.register(r'products', views.ProductViewSet)
router.register(r'addresses', views.AddressViewSet)
router.register(r'carts', views.CartViewSet)
router.register(r'orders', views.OrderViewSet)
router.register(r'payments', views.PaymentViewSet)
router.register(r'coupons', views.CouponViewSet)
router.register(r'refunds', views.RefundViewSet)
router.register(r'employees', views.EmployeeViewSet)
router.register(r'userprofiles', views.UserProfileViewSet)
router.register(r'users', views.UserViewSet)

urlpatterns = [
    # Vistas principales
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password, name='change_password'),
    path('register/', views.register_view, name='register'),  # [NUEVO] Ruta para registro
    path('contact/', views.contact_view, name='contact'),  # [NUEVO] Ruta para contacto

    # Vistas para clientes
    path('catalog/', views.customer_catalog, name='customer_catalog'),
    path('catalog/<slug:slug>/', views.customer_product_detail, name='customer_product_detail'),  # [NUEVO] Ruta para detalle de producto
    path('cart/', views.customer_cart, name='customer_cart'),
    path('checkout/', views.customer_checkout, name='customer_checkout'),
    path('order/confirmation/<int:order_id>/', views.order_confirmation, name='order_confirmation'),  # [NUEVO] Ruta para confirmación de pedido

    # Vistas para administradores
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/users/', views.admin_user_management, name='admin_user_management'),
    path('admin/categories/', views.admin_category_management, name='admin_category_management'),
    path('admin/brands/', views.admin_brand_management, name='admin_brand_management'),
    path('admin/coupons/', views.admin_coupon_management, name='admin_coupon_management'),
    path('admin/refunds/', views.admin_refund_management, name='admin_refund_management'),

    # Vistas para vendedores
    path('seller/orders/', views.seller_orders, name='seller_orders'),
    path('seller/products/', views.seller_products, name='seller_products'),

    # Vistas para bodegueros
    path('warehouse/orders/', views.warehouse_orders, name='warehouse_orders'),
    path('warehouse/inventory/', views.warehouse_inventory, name='warehouse_inventory'),

    # Vistas para contadores
    path('accountant/payments/', views.accountant_payments, name='accountant_payments'),

    # APIs
    path('api/', include(router.urls)),
    path('api/create-payment-intent/', views.create_payment_intent, name='create_payment_intent'),
    path('api/webhook/', views.stripe_webhook, name='stripe_webhook'),
]