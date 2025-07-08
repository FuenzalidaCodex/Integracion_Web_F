from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Product, Category, Brand, Cart, CartItem, Order, OrderItem, Payment, Address, Coupon, Refund, Employee, UserProfile, PriceHistory  # [CAMBIO] Añadir PriceHistory a las importaciones

# [CAMBIO] Nuevo serializador para el historial de precios
class PriceHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceHistory
        fields = ['price', 'created_at']  # Serializa precio y fecha

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']  # Serializa datos básicos del usuario

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']  # Serializa categoría con descripción

class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ['id', 'name']  # Serializa marca

class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True)
    brand = BrandSerializer(read_only=True)
    brand_id = serializers.PrimaryKeyRelatedField(queryset=Brand.objects.all(), source='brand', write_only=True)
    final_price = serializers.SerializerMethodField()  # Campo calculado para precio final
    brand_code = serializers.CharField(source='brand.name', read_only=True)  # [CAMBIO] Campo para el "Código" (nombre de la marca)
    price_history = PriceHistorySerializer(many=True, read_only=True)  # [CAMBIO] Campo para el historial de precios

    class Meta:
        model = Product
        fields = ['id', 'code', 'name', 'description', 'category', 'category_id', 'brand', 'brand_id', 'brand_code', 'price', 'discount_price', 'final_price', 'stock', 'image', 'slug', 'created_at', 'updated_at', 'price_history']  # [CAMBIO] Añadir code, brand_code, price_history

    def get_final_price(self, obj):
        return obj.get_final_price()  # Usa el método del modelo

class AddressSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source='user', write_only=True)

    class Meta:
        model = Address
        fields = ['id', 'user', 'user_id', 'street_address', 'apartment_address', 'country', 'zip_code', 'address_type', 'default']  # Serializa dirección

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), source='product', write_only=True)
    total_price = serializers.SerializerMethodField()  # Campo calculado para precio total

    class Meta:
        model = CartItem
        fields = ['id', 'cart', 'product', 'product_id', 'quantity', 'price', 'total_price']  # Serializa ítem de carrito

    def get_total_price(self, obj):
        return obj.get_total_price()  # Usa el método del modelo

class CartSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    items = CartItemSerializer(many=True)
    total = serializers.SerializerMethodField()  # Campo calculado para total del carrito

    class Meta:
        model = Cart
        fields = ['id', 'user', 'items', 'created_at', 'updated_at', 'total']  # Serializa carrito

    def get_total(self, obj):
        return sum(item.get_total_price() for item in obj.items.all())  # Calcula total del carrito

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        cart = Cart.objects.create(**validated_data)
        for item_data in items_data:
            CartItem.objects.create(cart=cart, **item_data)
        return cart

class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), source='product', write_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'order', 'product', 'product_id', 'quantity', 'price', 'total_price']  # Serializa ítem de pedido

    def get_total_price(self, obj):
        return obj.get_total_price()  # Usa el método del modelo

class OrderSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source='user', write_only=True)
    items = OrderItemSerializer(many=True)
    shipping_address = AddressSerializer(read_only=True)
    shipping_address_id = serializers.PrimaryKeyRelatedField(queryset=Address.objects.all(), source='shipping_address', write_only=True, allow_null=True)
    billing_address = AddressSerializer(read_only=True)
    billing_address_id = serializers.PrimaryKeyRelatedField(queryset=Address.objects.all(), source='billing_address', write_only=True, allow_null=True)
    coupon = serializers.PrimaryKeyRelatedField(queryset=Coupon.objects.all(), allow_null=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'user', 'user_id', 'ref_code', 'status', 'delivery_method', 'shipping_address', 'shipping_address_id', 'billing_address', 'billing_address_id', 'coupon', 'created_at', 'updated_at', 'items', 'total']  # Serializa pedido

    def get_total(self, obj):
        return obj.get_total()  # Usa el método del modelo

    def create(self, validated_data):
        import uuid
        items_data = validated_data.pop('items', [])
        validated_data['ref_code'] = str(uuid.uuid4())[:20]  # Genera ref_code único
        order = Order.objects.create(**validated_data)
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        return order

class PaymentSerializer(serializers.ModelSerializer):
    order = OrderSerializer(read_only=True)
    order_id = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all(), source='order', write_only=True)
    confirmed_by = UserSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'order', 'order_id', 'amount', 'method', 'stripe_payment_intent_id', 'confirmed', 'confirmed_by', 'created_at']  # Serializa pago

class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ['id', 'code', 'amount', 'valid_from', 'valid_to', 'active']  # Serializa cupón

    def validate(self, data):
        if data['valid_from'] > data['valid_to']:
            raise serializers.ValidationError("valid_from debe ser anterior a valid_to")
        return data

class RefundSerializer(serializers.ModelSerializer):
    order = OrderSerializer(read_only=True)
    order_id = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all(), source='order', write_only=True)

    class Meta:
        model = Refund
        fields = ['id', 'order', 'order_id', 'reason', 'accepted', 'created_at']  # Serializa reembolso

class EmployeeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source='user', write_only=True)

    class Meta:
        model = Employee
        fields = ['id', 'user', 'user_id', 'rut', 'first_name', 'last_name', 'mother_last_name', 'role', 'created_at']  # Serializa empleado

class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source='user', write_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'user_id', 'stripe_customer_id', 'one_click_purchasing']  # Serializa perfil de usuario