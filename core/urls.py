from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core import views
from core import api_views

# Configurar el router para las APIs
router = DefaultRouter()
router.register(r'categories', api_views.CategoryViewSet)
router.register(r'brands', api_views.BrandViewSet)
router.register(r'products', api_views.ProductViewSet)
router.register(r'addresses', api_views.AddressViewSet)
router.register(r'carts', api_views.CartViewSet)
router.register(r'orders', api_views.OrderViewSet)
router.register(r'payments', api_views.PaymentViewSet)
router.register(r'coupons', api_views.CouponViewSet)
router.register(r'refunds', api_views.RefundViewSet)
router.register(r'employees', api_views.EmployeeViewSet)
router.register(r'userprofiles', api_views.UserProfileViewSet)
router.register(r'users', api_views.UserViewSet)

urlpatterns = [
    # Vistas principales
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password, name='change_password'),
    path('contact/', views.contact_view, name='contact'),
    # Vistas para clientes
    path('catalog/', views.customer_catalog, name='customer_catalog'),
    path('catalog/<slug:slug>/', views.customer_product_detail, name='customer_product_detail'),
    path('cart/', views.customer_cart, name='customer_cart'),
    path('checkout/', views.customer_checkout, name='customer_checkout'),
    path('add-address/', views.customer_add_address, name='customer_add_address'),
    path('order/confirmation/<int:order_id>/', views.order_confirmation, name='order_confirmation'),
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
    path('warehouse/orders/<int:order_id>/', views.warehouse_order_detail, name='warehouse_order_detail'),
    # Vistas para contadores
    path('accountant/payments/', views.accountant_payments, name='accountant_payments'),
    # APIs
    path('api/', include(router.urls)),
    path('api/create-payment-intent/', api_views.create_payment_intent, name='create_payment_intent'),
    path('api/webhook/', api_views.stripe_webhook, name='stripe_webhook'),
    path('api/convert-currency/', api_views.convert_currency, name='convert_currency'),
]